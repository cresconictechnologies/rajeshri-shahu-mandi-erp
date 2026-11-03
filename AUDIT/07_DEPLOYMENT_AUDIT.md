# AUDIT/07: Deployment, Hosting & Serverless vs Stateful Daemon Hazards
**Project:** Rajarshi Shahu Trading Mandi ERP (Commercial Mandi ERP v1.0)  
**Auditor:** Lead DevOps & QA Reliability Auditor  
**Date:** 2026-11-03  
**Status:** COMPLETE / CRITICAL DEFECTS IDENTIFIED  

---

## 1. Executive Deployment Overview

The Rajarshi Shahu Mandi ERP architecture currently attempts to bridge two fundamentally incompatible paradigms:
1. **Cloud-Hosted Ephemeral Serverless (Vercel):** Hosts the static marketing page, the PWA inspector terminal (`app.html`), and serverless Edge functions (`/api/track.js`, `/api/supabase-status.js`, `/api/system-updates.js`, `/api/inspections-submit.js`).
2. **Stateful Local Desktop Daemon (Python FastAPI + SQLite):** Packaged via PyInstaller (`build_desktop_app.py`) into a standalone Windows application (`desktop_app.py`) intended to run on local yard workstations.

This dual-tier deployment model contains architectural conflicts, unhandled network partitions, mixed-content browser security blocks, leaked production credentials, and a dormant background daemon that fails to execute in desktop builds.

---

## 2. Detailed Findings

### AUD-DEP-001: Dormant Background Sync Daemon in Standalone Desktop Application
- **Severity:** CRITICAL
- **Module:** Desktop Application Launcher / Server Lifecycle
- **File/Line:** `commoditi software/desktop_app.py` L67-78, `commoditi software/server.py` L316-341
- **Observed:** In `desktop_app.py`, Uvicorn is instantiated with `lifespan="off"`:
  ```python
  config = uvicorn.Config(
      app=app,
      host="0.0.0.0",
      port=PORT,
      log_level="warning",
      loop="asyncio",
      lifespan="off",
      access_log=False
  )
  ```
  In `server.py`, the 15-second background sync loop (`_supabase_cloud_sync_daemon`) is registered exclusively inside `@app.on_event("startup")`:
  ```python
  @app.on_event("startup")
  async def startup_event():
      global MAIN_EVENT_LOOP
      MAIN_EVENT_LOOP = asyncio.get_running_loop()
      asyncio.create_task(_supabase_cloud_sync_daemon())
  ```
- **Expected:** The background sync daemon must continuously push local transactions and pull rates/tickets from Supabase Cloud every 15 seconds.
- **Actual:** Setting `lifespan="off"` instructs Uvicorn to completely bypass FastAPI startup and shutdown event handlers. As a result, `@app.on_event("startup")` NEVER executes. `MAIN_EVENT_LOOP` remains `None`, and `_supabase_cloud_sync_daemon` is never spawned. In all distributed desktop builds (`Rajarshi_Shahu_Trading.exe`), automatic background sync is completely dead.
- **Evidence:** 
  1. `commoditi software/desktop_app.py` lines 71-74.
  2. `commoditi software/server.py` lines 316-341.
  3. Starting `desktop_app.py` produces log entries showing Uvicorn initialization without startup event logs.
- **Business Impact:** Yard cashiers operating the desktop application never automatically receive QC inspection tickets submitted by mobile inspectors. Daily rates published by HQ do not propagate to branch workstations without manual user intervention or manual sync button presses.
- **Correction:** Enable lifespan processing in `desktop_app.py` (`lifespan="on"`), migrate from deprecated `@app.on_event("startup")` to FastAPI modern `@asynccontextmanager` lifespan handler, or run the sync worker as a dedicated Python `threading.Thread` independent of Uvicorn's event loop.
- **Tests:** Verify that upon launching `desktop_app.py`, the sync daemon thread logs initialization and completes periodic synchronization.
- **Dependencies:** `desktop_app.py`, `server.py`, `supabase_sync.py`.

---

### AUD-DEP-002: Ephemeral In-Memory State Loss on Vercel Serverless Functions
- **Severity:** CRITICAL
- **Module:** Serverless Telemetry & License Tracking
- **File/Line:** `mandi-erp-tracker/api/track.js` L5-21, L72-174
- **Observed:** `api/track.js` declares global JavaScript memory variables to store transaction metrics, license requests, download statistics, and live telemetry:
  ```javascript
  let inMemoryStats = {
    downloads: 0,
    appDownloads: 0,
    visitors: 0,
    activeLicenses: 0,
    recentEvents: [],
    licenseRequests: []
  };
  let liveTelemetry = {
    totalQuintals: 0,
    totalDisbursed: 0,
    activeBranches: 0,
    totalInspections: 0,
    lastSyncedAt: null,
    recentEvent: null
  };
  ```
- **Expected:** License requests and commercial telemetry must persist reliably to a database (Supabase PostgreSQL / Redis / DynamoDB).
- **Actual:** Vercel serverless execution environments are ephemeral and stateless. Container instances freeze or terminate immediately after completing requests. Across different AWS Edge regions, instances do not share state. Cold starts wipe all in-memory arrays.
- **Evidence:** `mandi-erp-tracker/api/track.js` lines 5-21. Invoking `POST /api/track` followed by an invocation from a different region or after a 5-minute idle period resets counts to 0 and clears `licenseRequests`.
- **Business Impact:** High-value commercial license inquiries submitted by prospective Mandi traders via the landing page modal are silently discarded upon lambda teardown, causing direct loss of enterprise sales leads.
- **Correction:** Store all license requests and telemetry events directly into the `license_inquiries` and `cloud_telemetry` tables in Supabase PostgreSQL via PostgREST with parameterized queries.
- **Tests:** Submit license request via `POST /api/track`, verify row insertion in Supabase `license_inquiries` table across cold starts.
- **Dependencies:** `mandi-erp-tracker/api/track.js`, Supabase database schema.

---

### AUD-DEP-003: Hardcoded Developer LAN IP and HTTPS Mixed-Content Security Failure
- **Severity:** CRITICAL
- **Module:** Mobile Inspector PWA / API Routing
- **File/Line:** `mandi-erp-tracker/api/system-updates.js` L11, `mandi-erp-tracker/app.html` L1207-1208, L1257, L1292, L1355
- **Observed:** The production Vercel system update endpoint and PWA HTML contain hardcoded private IP references:
  ```javascript
  // api/system-updates.js
  master_host: "192.168.0.140:8080"
  
  // app.html
  const host = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' ? '127.0.0.1' : (window.location.hostname || '192.168.0.140');
  const lanRes = await fetch(`http://${host}:8080/api/inspector/submit-qc`, { ... });
  fetch('http://192.168.0.140:8080/api/supabase/status', { cache: 'no-store' });
  ```
- **Expected:** Client PWA served over HTTPS (`https://mandi-erp-tracker.vercel.app/app`) must communicate via HTTPS endpoints or use dynamic LAN service discovery configured by the operator.
- **Actual:** 
  1. **Mixed-Content Blocking:** When `app.html` is loaded over HTTPS, modern browsers strictly prohibit cleartext HTTP requests to local IPs (`http://192.168.0.140:8080`). The browser console emits: `Blocked loading mixed active content "http://192.168.0.140:8080/api/inspector/submit-qc"`.
  2. **Non-Existent LAN Route:** `192.168.0.140` is a private home DHCP address from the original development machine. In actual APMC mandi yards (Chikhali, Varvand, Dhad), routers assign different subnets (`192.168.1.x`, `10.0.0.x`).
- **Evidence:** `mandi-erp-tracker/app.html` line 1207, 1257, 1292, 1355; `mandi-erp-tracker/api/system-updates.js` line 11.
- **Business Impact:** Mobile inspectors in the physical mandi yard are blocked from submitting QC tickets or checking system status when using the HTTPS PWA.
- **Correction:** 
  1. Remove all hardcoded IP addresses.
  2. Introduce user-configurable Master Host settings in PWA local storage (`localStorage.getItem('mandi_master_gateway')`).
  3. Default all cloud requests to same-origin HTTPS endpoints (`/api/...`) that proxy securely to Supabase Cloud.
- **Tests:** Load PWA via HTTPS in Chrome, verify zero Mixed Content console errors and successful submission of tickets via cloud API proxy.
- **Dependencies:** `mandi-erp-tracker/app.html`, `mandi-erp-tracker/api/system-updates.js`.

---

### AUD-DEP-004: Direct Secret Leakage & Plaintext PostgreSQL Credentials in Distributable Desktop Zip
- **Severity:** CRITICAL
- **Module:** Build Automation / Desktop Distribution
- **File/Line:** `commoditi software/build_desktop_app.py` L15-16, `commoditi software/.env` L10-15
- **Observed:** PyInstaller build script packages live secrets directly into the distributed Windows zip:
  ```python
  # build_desktop_app.py
  "--add-data", f"{os.path.join(current_dir, 'commodity_mandi.db')};.",
  "--add-data", f"{os.path.join(current_dir, '.env')};.",
  ```
  The packaged `.env` file contains:
  ```ini
  SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRiaGNwZWJjaG95anlmZnFqZ2loIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc5MzIwODA1NywiZXhwIjoyMTA4Nzg0MDU3fQ.X3zOVSoIDOsp6ppSJ4SvgQFfQTVJnBmPeKclXnzRaS0
  DATABASE_URL=postgresql://postgres.dbhcpebchoyjyffqjgih:RajarshiShahu2026MandiSecure@aws-0-ap-south-1.pooler.supabase.com:6543/postgres
  ```
- **Expected:** Desktop client applications distributed to third parties must NEVER contain administrative service-role tokens or direct PostgreSQL superuser connection strings.
- **Actual:** Anyone downloading `Rajarshi_Shahu_Trading_Windows_x64.zip` from GitHub Releases has full, unrestricted read/write/drop access to the entire AWS Supabase PostgreSQL database via the leaked service role key and direct database connection string.
- **Evidence:** `commoditi software/build_desktop_app.py` lines 15-16; `commoditi software/.env` lines 14-15; decompiled distribution directory `commoditi software/dist/Rajarshi_Shahu_Trading/_internal/.env`.
- **Business Impact:** Catastrophic data breach risk. Malicious actors or competitors can drop all production tables, falsify audit logs, corrupt invoice ledgers, and extract farmer KYC and payment account details.
- **Correction:** 
  1. Immediately revoke and regenerate the Supabase Service Role key and PostgreSQL database password in the Supabase Cloud Console.
  2. Remove `--add-data ".env;."` and `--add-data "commodity_mandi.db;."` from `build_desktop_app.py`.
  3. Desktop client must only authenticate via user login credentials against a cloud REST API or use branch-scoped anonymous tokens governed by PostgreSQL Row Level Security (RLS).
- **Tests:** Inspect PyInstaller build artifacts to verify absence of `.env` and `commodity_mandi.db`.
- **Dependencies:** `build_desktop_app.py`, `.env`, Supabase Cloud IAM.

---

### AUD-DEP-005: Multi-Branch Concurrency Dilemma & Isolated SQLite Data Silos
- **Severity:** HIGH
- **Module:** Multi-Branch Networking & Data Consistency
- **File/Line:** `commoditi software/server.py` L4690-4693, `commoditi software/database.py` L20-35, `commoditi software/supabase_sync.py` L1000-1015
- **Observed:** The FastAPI server binds to `0.0.0.0:8080` locally on a single workstation. When the ERP is deployed across multiple branches (Chikhali, Varvand, Dhad):
  1. Workstations at Branch 2 (Varvand) and Branch 3 (Dhad) cannot connect to Branch 1's LAN over standard internet connections without public static IPs, port forwarding, or site-to-site VPNs.
  2. Each branch must therefore execute its own local instance of `desktop_app.py` / `server.py`, with its own local `commodity_mandi.db` SQLite database.
- **Expected:** Multi-branch operations must either connect directly to a centralized cloud database or use robust multi-master asynchronous replication with distributed conflict resolution.
- **Actual:** 
  - Token numbers are generated via local count:
    ```python
    cur.execute("SELECT count(*) as cnt FROM purchase_invoices WHERE branch_id=? AND invoice_date=?", (branch_id, today_str))
    seq = cur.fetchone()["cnt"] + 1
    ```
    If two operators at the same branch create invoices concurrently, or if an offline branch syncs later, duplicate token numbers and invoice sequence collisions occur.
  - Cash drawers are maintained in local SQLite `branch_daily_cash_drawers`. Central Accounts at HQ has zero real-time visibility into branch cash balances until a sync cycle completes.
  - Sync conflict handling relies on string timestamp comparison (`loc_updated >= rem_updated`), which fails under local workstation clock skew.
- **Evidence:** `commoditi software/server.py` lines 2320-2322; `commoditi software/supabase_sync.py` lines 1142-1145.
- **Business Impact:** Statutory compliance failures under Income Tax Act (Section 269ST) if cumulative daily payouts across branches cannot be tracked in real-time; conflicting invoice numbers issued to farmers leading to accounting rejection during APMC audits.
- **Correction:** 
  1. Enforce branch-scoped invoice sequence numbering (`INV-{BRANCH}-{YYYYMMDD}-{SEQ}`) backed by central database sequences.
  2. Use UUIDv4 primary keys for all distributed entities.
  3. Centralize authoritative data in Supabase PostgreSQL; treat local SQLite strictly as an offline-read cache and write-ahead spool.
- **Tests:** Simulate concurrent invoice generation across two isolated instances with identical date and branch parameters; verify zero sequence collisions.
- **Dependencies:** `server.py`, `database.py`, `supabase_sync.py`.

---

### AUD-DEP-006: Out-of-Sync GitHub Release Binaries vs Codebase Evolution
- **Severity:** HIGH
- **Module:** Release Engineering / Distribution
- **File/Line:** `mandi-erp-tracker/api/track.js` L58-60, `commoditi software/build_desktop_app.py`
- **Observed:** `api/track.js` hardcodes download links to a pre-compiled GitHub release:
  `https://github.com/cresconictechnologies/rajarshi-shahu-mandi-erp/releases/download/v1.0/Rajarshi_Shahu_Trading_Windows_x64.zip`.
- **Expected:** Binary releases on GitHub Releases must be built automatically via GitHub Actions CI from tagged commits, ensuring parity between source code and distributed binaries.
- **Actual:** The binary was compiled manually on a local Windows machine. Recent fixes to calculations, licensing, and schema in `commoditi software/` are NOT reflected in the previously uploaded release zip on GitHub.
- **Evidence:** `mandi-erp-tracker/api/track.js` lines 58-60; presence of local build artifacts in `commoditi software/dist`.
- **Business Impact:** Clients downloading the executable from the landing page receive outdated code with known bugs and security vulnerabilities.
- **Correction:** Implement a GitHub Actions workflow (`.github/workflows/build_desktop.yml`) that builds, tests, packages, and attaches release artifacts upon git tag pushes (`v*.*.*`).
- **Tests:** Verify reproducible GitHub Actions build producing verified SHA-256 binary digests.
- **Dependencies:** GitHub Actions, `build_desktop_app.py`.

---

## 3. Deployment Topology Matrix

| Deployment Tier | Host Platform | Runtime / Engine | State Model | Critical Defect |
| :--- | :--- | :--- | :--- | :--- |
| **Landing & Marketing** | Vercel Edge CDN | Static HTML / Tailwind | Stateless | Points to unverified release zip |
| **Inspector PWA** | Vercel Edge CDN | Web PWA (`app.html`) | Client Cache | Mixed Content blocks cleartext LAN calls |
| **Serverless API** | Vercel Serverless | Node.js 18+ Lambda | Ephemeral | In-memory globals reset on cold start |
| **Cloud Database** | Supabase Cloud (AWS) | PostgreSQL 17 (Mumbai) | ACID Relational | Leaked Service Role key in desktop build |
| **Desktop Application** | Local Windows PC | PyInstaller / WebView2 | Local SQLite | Background sync daemon dead (`lifespan=off`) |

---

## 4. Verification Sign-Off
- **Auditor:** Lead DevOps & QA Reliability Auditor
- **Status:** FAIL — Critical Deployment & Credential Exposure Blockers
- **Recommended Action:** Execute Stage 1 (Security Revocation) and Stage 3 (Lifespan Remediation) of the Repair Roadmap immediately prior to any production deployment.
