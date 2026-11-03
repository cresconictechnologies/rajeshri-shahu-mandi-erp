# AUDIT/11: Prioritized 6-Stage Concrete Repair Roadmap
**Project:** Rajarshi Shahu Trading Mandi ERP (Commercial Mandi ERP v1.0)  
**Auditor:** Lead DevOps & QA Reliability Auditor  
**Date:** 2026-11-03  
**Status:** ACTIONABLE ENGINEERING ROADMAP  

---

## 1. Roadmap Overview & Sequencing

This roadmap specifies the 6 sequential stages required to remediate all critical, high, and medium vulnerabilities identified across the deployment, testing, and performance audits. The stages are ordered strictly by **risk reduction priority**:

1. **Stage 1 (Immediate / Day 1):** Critical Security, Secret Revocation & Distribution Sanitization.
2. **Stage 2 (Days 2–3):** Database Schema, Distributed Identity & Atomic Sequence Hardening.
3. **Stage 3 (Days 4–5):** Lifespan Execution, Realtime Architecture & Batch Sync Engine.
4. **Stage 4 (Days 6–7):** Frontend PWA Cloud-Native Alignment & Mixed Content Elimination.
5. **Stage 5 (Days 8–9):** Test Suite Modernization, Test Isolation & Network Mocking.
6. **Stage 6 (Days 10–12):** Cloud Container Deployment & Automated GitHub Actions CI/CD.

---

## 2. Stage-by-Stage Implementation Plans

### Stage 1: Critical Security, Secret Revocation & Distribution Sanitization
- **Primary Objective:** Contain the severe credential exposure vulnerability and prevent public leakage of database superuser credentials.
- **Files to Change:**
  - `commoditi software/.env`
  - `commoditi software/build_desktop_app.py`
  - `mandi-erp-tracker/api/inspections-submit.js`
  - `mandi-erp-tracker/api/supabase-status.js`
  - `mandi-erp-tracker/api/system-updates.js`
  - GitHub Releases / Artifact Storage
- **Functions & Modifications:**
  1. **Credential Revocation (Supabase Console):**
     - Rotate the PostgreSQL database password immediately in Supabase Project Settings.
     - Revoke and regenerate the `service_role` and `anon` API keys.
  2. **Sanitize `build_desktop_app.py`:**
     - Remove lines 15 and 16 (`--add-data "...commodity_mandi.db;."` and `--add-data "...env;."`).
     - Remove decompiled `.env` and `commodity_mandi.db` from `commoditi software/dist/`.
  3. **Remove Hardcoded Service Role Key from Vercel Edge:**
     - In `mandi-erp-tracker/api/inspections-submit.js`, remove hardcoded fallback string on line 17. Bind exclusively to `process.env.SUPABASE_SERVICE_ROLE_KEY`.
  4. **Purge LAN IP References:**
     - In `mandi-erp-tracker/api/system-updates.js`, remove `master_host: "192.168.0.140:8080"`.
- **SQL Migrations:** None.
- **Rollback Strategy:** If key rotation breaks existing unpatched desktop clients, deploy updated `.env` keys via encrypted configuration profile.
- **Acceptance Criteria:**
  - Distributed zip archive contains zero `.env` or `.db` files.
  - Public repository and Vercel functions contain zero hardcoded plaintext JWT service keys.
  - Supabase database rejects old password and old service role token.

---

### Stage 2: Database Schema, Distributed Identity & Atomic Sequence Hardening
- **Primary Objective:** Eliminate multi-branch invoice collisions, non-atomic counter sequences, and implement Row-Level Security (RLS).
- **Files to Change:**
  - `commoditi software/database.py`
  - `commoditi software/server.py`
  - `commoditi software/supabase_sync.py`
- **Functions & Modifications:**
  1. **UUIDv4 Primary Keys:**
     - Update invoice and transaction creation in `server.py` (line 2323) from `f"inv-{uuid.uuid4().hex[:10]}"` to full `str(uuid.uuid4())`.
  2. **Atomic Branch-Scoped Token Generation:**
     - Replace non-atomic `SELECT count(*) + 1` in `server.py` (lines 2320-2322) with a dedicated branch sequence table in SQLite:
       ```sql
       CREATE TABLE IF NOT EXISTS branch_sequences (
           branch_code TEXT NOT NULL,
           sequence_date TEXT NOT NULL,
           last_seq INTEGER NOT NULL DEFAULT 0,
           PRIMARY KEY (branch_code, sequence_date)
       );
       ```
     - Use atomic SQL increment: `UPDATE branch_sequences SET last_seq = last_seq + 1 WHERE ... RETURNING last_seq;`.
     - Standardize token format: `INV-{BRANCH}-{YYYYMMDD}-{SEQ:05d}`.
  3. **Implement PostgreSQL Row Level Security (RLS) on Supabase:**
     - Enable RLS on all 14 production tables.
     - Define branch isolation policies based on `auth.jwt() ->> 'branch_id'`.
- **SQL Migration Script (`migrations/002_atomic_sequences_and_rls.sql`):**
  ```sql
  -- Atomic sequences and RLS policy rollout
  ALTER TABLE purchase_invoices ADD COLUMN IF NOT EXISTS branch_sequence_no INTEGER;
  CREATE INDEX IF NOT EXISTS idx_invoices_branch_date_seq ON purchase_invoices(branch_id, invoice_date, branch_sequence_no);

  -- Enable RLS
  ALTER TABLE quality_inspections ENABLE ROW LEVEL SECURITY;
  ALTER TABLE purchase_invoices ENABLE ROW LEVEL SECURITY;
  ALTER TABLE cashier_payouts ENABLE ROW LEVEL SECURITY;

  CREATE POLICY branch_isolation_invoices ON purchase_invoices
      FOR ALL TO authenticated
      USING (
          auth.jwt() ->> 'role' IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ') OR
          branch_id = auth.jwt() ->> 'branch_id'
      );
  ```
- **Rollback Strategy:** Preserve existing `id` and `token_number` columns. Revert `server.py` sequence allocation logic to read previous counts if migration fails.
- **Acceptance Criteria:**
  - Concurrent requests generate monotonic, collision-free token numbers across simultaneous transactions.
  - Cashier from `br-chikhali` cannot query or insert records belonging to `br-varvand`.

---

### Stage 3: Lifespan Execution, Realtime Architecture & Batch Sync Engine
- **Primary Objective:** Fix dormant background sync on desktop app, eliminate synchronous blocking HTTP calls from route handlers, and refactor sync push into high-speed batch operations.
- **Files to Change:**
  - `commoditi software/desktop_app.py`
  - `commoditi software/server.py`
  - `commoditi software/supabase_sync.py`
- **Functions & Modifications:**
  1. **Fix Uvicorn Lifespan in `desktop_app.py`:**
     - In `desktop_app.py` line 73, change `lifespan="off"` to `lifespan="on"`.
     - Migrate FastAPI `server.py` from deprecated `@app.on_event("startup")` to the modern `@asynccontextmanager` lifespan handler.
     - Add explicit logging upon daemon thread activation.
  2. **Refactor `push_local_to_supabase` into Chunked Batch Upserts:**
     - Replace the $O(N)$ row loop in `supabase_sync.py` (lines 1016-1037) with SQLAlchemy multi-row batch execution or bulk array PostgREST POSTs in chunks of 250 rows:
       ```python
       for chunk in chunk_rows(sanitized_rows, 250):
           with engine.begin() as pg_conn:
               pg_conn.execute(text(batch_upsert_sql), chunk)
       ```
     - Add watermark filtering: `WHERE updated_at > :last_synced_at` so only genuinely modified rows are pushed.
  3. **Remove Blocking Cloud Pulls from Route Handlers:**
     - In `server.py`, delete line 1962 (`supabase_sync.pull_supabase_to_local(["daily_commodity_rates"])`) and line 4578 (`supabase_sync.pull_supabase_to_local(["quality_inspections"])`).
     - Route handlers must return local SQLite data instantly (< 20ms).
- **SQL Migrations:** None.
- **Rollback Strategy:** Maintain previous single-record fallback in `supabase_sync.py` guarded by `MANDI_BATCH_SYNC_ENABLED=1`.
- **Acceptance Criteria:**
  - Launching `desktop_app.py` spawns and logs the background sync worker.
  - Cloud push sync of 1,000 records executes in under 2.5 seconds (previously > 50 seconds).
  - Cashier pending ticket page loads in < 50ms even if cloud network is offline.

---

### Stage 4: Frontend PWA Cloud-Native Alignment & Mixed Content Elimination
- **Primary Objective:** Eliminate Mixed Content browser blocks, remove hardcoded IP addresses, and enable true offline-capable PWA operations.
- **Files to Change:**
  - `mandi-erp-tracker/app.html`
  - `mandi-erp-tracker/sw.js`
  - `mandi-erp-tracker/manifest.json`
- **Functions & Modifications:**
  1. **Eliminate Cleartext LAN Calls:**
     - In `app.html`, remove all references to `http://192.168.0.140:8080`.
     - Route all remote requests to relative HTTPS paths (`/api/inspections-submit`, `/api/supabase/status`).
  2. **Operator Gateway Configuration:**
     - Add a settings modal in `app.html` allowing the yard manager to input a custom local gateway URL if running an on-premise local server (`https://mandi-local.lan:8080`), saving to `localStorage`.
  3. **IndexedDB Offline Spool in Service Worker:**
     - In `sw.js` and `app.html`, when `navigator.onLine === false` or fetch fails, serialize the QC ticket into an IndexedDB object store (`offline_qc_spool`).
     - Register for Background Sync (`SyncManager.register('sync-qc-tickets')`) to replay submissions automatically when connectivity returns.
- **SQL Migrations:** None.
- **Rollback Strategy:** Retain existing `localStorage` ticket caching as fallback.
- **Acceptance Criteria:**
  - Chrome console reports ZERO Mixed Content warnings when loading `https://mandi-erp-tracker.vercel.app/app`.
  - Creating a QC ticket in Airplane mode stores it in IndexedDB; turning off Airplane mode automatically posts the ticket to Supabase Cloud.

---

### Stage 5: Test Suite Modernization, Test Isolation & Network Mocking
- **Primary Objective:** Eliminate development database pollution, make the test suite 100% hermetic/offline, and fix test runner discovery from the repository root.
- **Files to Change:**
  - `commoditi software/tests/__init__.py`
  - `commoditi software/tests/test_support.py`
  - `commoditi software/tests/test_backend_sync_verification.py`
  - `commoditi software/tests/test_supabase_cloud_sync.py`
  - `commoditi software/tests/test_new_commodity_standards.py`
  - `commoditi software/tests/test_live_sync.py`
- **Functions & Modifications:**
  1. **Universal Path Resolution in `tests/__init__.py`:**
     - Add repository root and package directory to `sys.path` unconditionally.
  2. **Mandatory Test Isolation Hook in `test_support.py`:**
     - Refactor `setup_test_database()` to execute automatically on test module loading.
     - Modify `database.get_connection()` to assert that `MANDI_TEST_DB_PATH` is set whenever `PYTEST_CURRENT_TEST` or `unittest` is detected.
  3. **Mock External Cloud Calls:**
     - In `test_supabase_cloud_sync.py`, mock `httpx.Client` and `sqlalchemy.create_engine` so that tests `test_04_schema_migration_to_supabase` and `test_05_bidirectional_sync` verify payload structure without opening live external network sockets.
     - Move live network tests to `tests/e2e/test_live_cloud.py` gated by an environment flag.
- **SQL Migrations:** None.
- **Rollback Strategy:** Revert test modifications without touching application source files.
- **Acceptance Criteria:**
  - `python -m unittest discover -s "commoditi software/tests"` passes 100% of tests with ZERO failures.
  - `commodity_mandi.db` SHA-256 hash is byte-for-byte identical before and after full test execution.
  - Full test suite runs in under 8.0 seconds (down from 92.65 seconds).

---

### Stage 6: Production Cloud Hosting & Automated CI/CD Pipeline
- **Primary Objective:** Deploy authoritative FastAPI backend to cloud container infrastructure, establish multi-environment configuration, and automate desktop release packaging.
- **Files to Change:**
  - `.github/workflows/ci.yml` (New)
  - `.github/workflows/release_desktop.yml` (New)
  - `Dockerfile` (New)
  - `fly.toml` or `docker-compose.prod.yml` (New)
  - `mandi-erp-tracker/api/track.js`
- **Functions & Modifications:**
  1. **Containerize Mandi ERP Backend (`Dockerfile`):**
     - Multi-stage Python 3.11/3.12 Dockerfile with non-root user.
     - Configured for Fly.io (Mumbai region `bom`) or AWS ECS Fargate.
  2. **Automated CI Workflow (`.github/workflows/ci.yml`):**
     - Runs linting (Ruff), typechecking (Mypy), and hermetic unit tests on every PR.
  3. **Secure Desktop Release Automation (`.github/workflows/release_desktop.yml`):**
     - Triggers on git tags `v*.*.*`.
     - Executes PyInstaller on Windows runner without embedding `.env` or development databases.
     - Signs the binary with Authenticode / signtool.
     - Uploads `Rajarshi_Shahu_Trading_Windows_x64.zip` directly to GitHub Releases with verifiable SHA-256 checksums.
  4. **Dynamic Release Metadata in `api/track.js`:**
     - Fetch the latest release asset download URL dynamically via GitHub API (`/repos/.../releases/latest`) instead of hardcoded v1.0 URL.
- **SQL Migrations:** None.
- **Rollback Strategy:** Blue/Green container deployment with instant rollback via `fly deploy --image <previous_tag>` or AWS ECS task definition rollback.
- **Acceptance Criteria:**
  - Automated PR builds execute in GitHub Actions within 2 minutes.
  - Pushing a version tag generates an untampered, credential-free desktop release binary.

---

## 3. Implementation Schedule & Resource Allocation

```text
Day 1:   [Stage 1] Secret Revocation & Build Sanitization (CRITICAL HOTFIX)
Day 2-3: [Stage 2] Schema Hardening, UUIDs, Atomic Sequences & RLS
Day 4-5: [Stage 3] Lifespan Fix, Batch Sync Engine & Realtime WebSockets
Day 6-7: [Stage 4] PWA Direct HTTPS Proxy, Mixed-Content Fix & IndexedDB
Day 8-9: [Stage 5] Universal Test Isolation & Mocked CI Suite
Day 10-12:[Stage 6] Containerized Cloud Deployment & GitHub Actions CI/CD
```

---

## 4. Verification Sign-Off
- **Auditor:** Lead DevOps & QA Reliability Auditor
- **Status:** APPROVED FOR STAGED EXECUTION
- **Next Step:** Verify all test scenarios in `AUDIT/12_TEST_COVERAGE_MATRIX.md`.
