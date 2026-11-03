# SYSTEM ARCHITECTURE AUDIT: DISTRIBUTED TOPOLOGY & DUAL-DATABASE HAZARDS
**Document ID:** `AUDIT/01_PROJECT_ARCHITECTURE.md`  
**Classification:** SYSTEM ARCHITECTURE & TOPOLOGY ASSESSMENT  
**System:** Rajarshi Shahu Mandi ERP (Commercial Multi-Yard Mandi ERP v1.0)  
**Target Codebases:** `commoditi software/` (Local FastAPI + SQLite Edge) and `mandi-erp-tracker/` (Cloud Vercel PWA + Supabase PostgreSQL)  
**Author:** Principal Backend Architect & Distributed Systems Forensic Auditor  
**Date of Audit:** November 3, 2026  
**Status:** COMPLETE & VERIFIED  

---

## 1. System Overview & Core Purpose

Rajarshi Shahu Trading Mandi ERP is a commercial multi-yard commodity trading platform designed for agricultural produce aggregation (primarily Soyabean, Chana, Wheat, and Maize) across Agricultural Produce Market Committee (APMC) market yards in Maharashtra (Chikhali, Varvand, Dhad).

The system serves three primary functional operational pillars:
1. **Field Yard QC Assaying:** Yard inspectors use mobile tablets/smartphones at the entry gate to evaluate physical grain quality (moisture meter display, computer vision grain tray defect analysis, breed varietal purity, Sortex clean yield).
2. **Weighbridge & Inward Purchase Settlement:** Branch cashiers weigh incoming tractor trolleys and trucks (gross and tare on external or internal weighbridges), apply moisture cuts and karda deductions, enforce Section 269ST statutory cash limits (Rs. 1,99,999/day ceiling), disburse cash with exact rupee denomination tracking, or generate RTGS bank payout requests.
3. **Head Office Central Accounts & Inventory Dispatches:** Head office accountants manage daily published rate corridors (min, target, max rate), approve or reject cashier rate override requests, process bank RTGS transfers with bank UTR reconciliation, and record outward bulk dispatches to industrial processing mills (e.g., Adani Wilmar Ltd.).

---

## 2. Distributed Split Topology

The platform does **not** operate as a single monolithic web application or a clean cloud microservice. Instead, it exists as a **hybrid, bifurcated split architecture**:

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PUBLIC CLOUD TIER                                      │
│                                                                                 │
│   ┌──────────────────────────────┐        ┌─────────────────────────────────┐  │
│   │   Vercel Serverless PWA      │        │    Supabase Cloud PostgreSQL    │  │
│   │   (mandi-erp-tracker)        │───────>│    (AWS Mumbai ap-south-1)      │  │
│   │   - app.html (QC Inspector)  │        │    - 11 Core Relational Tables  │  │
│   │   - api/inspections-submit.js│        │    - PostgreSQL 17 / PostgREST  │  │
│   │   - api/track.js             │        │    - Pooler Port 6543 (PgBouncer)│ │
│   └──────────────────────────────┘        └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────┬───────────────────────────┘
                                                      │
                                                      │ Unreliable Internet / 4G
                                                      │ (15s Poll / Pull)
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       LOCAL ON-PREMISE MANDI YARD TIER                          │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ Local Python FastAPI Server (commoditi software / port 8080)             │   │
│   │ - server.py: Business Rules, Invoices, Cashier Payouts, Ledger Engine    │   │
│   │ - LiveSyncHub: Local WebSockets (/ws/live)                              │   │
│   │ - _supabase_cloud_sync_daemon: Background Pull/Push Worker (15s loop)   │   │
│   │ - licensing.py: Ed25519 Cryptographic Commercial License Verification   │   │
│   │ - calculations.py: Section 269ST & Zero Mandi Cess Regulatory Invariants│   │
│   └────────────────────────────────────┬────────────────────────────────────┘   │
│                                        │                                        │
│                                        ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ Local Edge Database: SQLite (commodity_mandi.db)                        │   │
│   │ - Full offline durability                                               │   │
│   │ - 14 Relational Tables, Double-Entry Ledger, Cash Drawers               │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                        ▲                                        │
│                                        │ Local Intranet LAN (192.168.0.x)       │
│                                        │                                        │
│   ┌────────────────────────────────────┴────────────────────────────────────┐   │
│   │ Local Operator Web Clients (Edge Browser / Chromium Desktop App)        │   │
│   │ - branch_dashboard.html (Branch Cashier & Kanta Weighbridge Desk)       │   │
│   │ - accounts_dashboard.html (HQ Central Accountant & RTGS Processing Desk)│   │
│   │ - admin_dashboard.html (Super Admin Settings & Multi-Branch Governance) │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 The Two Disconnected Environments

#### Environment A: Public Cloud (Vercel + Supabase)
- **Codebase:** `c:\projects\tests\mandi-erp-tracker`
- **Hosting:** Vercel Serverless Platform (`mandi-erp-tracker.vercel.app`)
- **Backend Storage:** Supabase Cloud Database (Project Ref: `dbhcpebchoyjyffqjgih`, AWS Region: `ap-south-1` Mumbai).
- **Core Role:** Hosts the mobile-first Progressive Web App (PWA) accessed by field inspectors over cellular 4G/5G at the mandi entry gate.
- **Data Access:** Direct HTTPS PostgREST REST calls from Vercel Node.js serverless functions using Supabase `service_role` or `anon` keys.

#### Environment B: On-Premise APMC Yard Edge (Python FastAPI + SQLite)
- **Codebase:** `c:\projects\tests\commoditi software`
- **Hosting:** On-premise PC (Windows 10/11 Pro, Master PC at `192.168.0.140:8080` or packaged standalone `.exe` via PyInstaller).
- **Backend Storage:** Local SQLite 3 embedded database (`commodity_mandi.db`).
- **Core Role:** Authoritative transactional engine for weighing gross/tare trucks, executing cash disbursements, computing cash rounding, managing daily cash drawers, and generating 80mm thermal paper receipts.
- **Networking:** Local APMC office LAN (Wi-Fi router / Ethernet switch).

---

## 3. Technology Stack & Runtime Dependencies

### 3.1 Python On-Premise Environment
| Component | Actual Installed Version | Purpose |
| :--- | :--- | :--- |
| **Python Runtime** | `3.14.5 (64-bit Windows)` | Core backend execution runtime |
| **FastAPI** | `0.143.0` | High-performance asynchronous REST & WebSocket framework |
| **Uvicorn** | `0.49.0` | ASGI production server |
| **Jinja2** | `3.1.6` | Server-side template rendering for UI dashboards and 80mm receipts |
| **Pydantic** | `2.13.5` | Data validation and settings models |
| **HTTPX** | `0.28.1` | Asynchronous/synchronous HTTP client for Supabase REST queries |
| **SQLAlchemy** | `2.1.5` | PostgreSQL connection pooler interface for Supabase |
| **psycopg2** | `2.9.13` | Low-level PostgreSQL database driver |
| **SQLite 3** | `3.45+ (bundled)` | Local edge ACID transactional persistence engine |
| **PyCryptodome** | Standard library | Cryptographic license signature verification |

### 3.2 Cloud Serverless Environment
| Component | Actual Version / Platform | Purpose |
| :--- | :--- | :--- |
| **Vercel Serverless** | Node.js 18.x / 20.x runtime | Serverless API routes (`api/*.js`) |
| **Supabase PostgreSQL** | PostgreSQL 17 (AWS Mumbai `ap-south-1`) | Cloud master database for cross-branch consolidation |
| **Supabase PostgREST** | PostgREST v12 | RESTful JSON API wrapping PostgreSQL tables |
| **TailwindCSS** | 3.4.1 (CDN distribution) | Mobile inspector UI layout |

---

## 4. Dual-Database Replication Engine (`supabase_sync.py`)

Replication between the local SQLite database and Supabase Cloud PostgreSQL is managed by `commoditi software/supabase_sync.py` and invoked periodically by `_supabase_cloud_sync_daemon` in `server.py`.

### 4.1 Replication Topology & Monitored Tables
The system tracks 11 core domain tables for bidirectional replication:
1. `branches`: APMC market yard locations (Chikhali, Varvand, Dhad)
2. `users`: System operators (Cashiers, Munims, Accountants, Quality Inspectors)
3. `commodities`: Standard commodity specifications and HSN tax codes
4. `parties`: Registered farmers (cultivators) and institutional buyers (mills)
5. `daily_commodity_rates`: Daily published price corridors (min, target, max rate per quintal)
6. `inspectors`: Authenticated yard inspectors and credentials
7. `quality_inspections`: Mobile assay certificates with moisture, karda, and Sortex metrics
8. `purchase_invoices`: Inward farmer purchase transactions and weighment records
9. `cashier_payouts`: Cash and RTGS disbursement records with currency denomination tracking
10. `branch_daily_cash_drawers`: Physical cash drawer reconciliation ledgers
11. `outward_orders`: Bulk dispatch orders to external commercial buyers

### 4.2 Replication Mechanisms

#### 1. Push Pipeline (Local SQLite -> Supabase Cloud)
- When a record is inserted or updated locally (e.g. `api_inspector_submit_qc`), the code calls `trigger_async_sync(table, entity_id, payload)`.
- If online, it pushes immediately via `push_local_to_supabase()`.
- If offline, it records an entry in the local SQLite table `sync_queue` with status `'PENDING'`.
- The daemon periodically calls `process_sync_queue()` to drain pending records using idempotent PostgREST upserts (`Prefer: resolution=merge-duplicates`).

#### 2. Pull Pipeline (Supabase Cloud -> Local SQLite)
- The daemon periodically invokes `pull_supabase_to_local(["quality_inspections", ...])`.
- It executes:
  `SELECT * FROM {table} ORDER BY updated_at DESC LIMIT 500;`
- For each record, it compares `updated_at` against the existing local SQLite record.
- If remote `updated_at > local_updated_at`, it executes an SQLite upsert:
  `INSERT INTO {table} (...) VALUES (...) ON CONFLICT(id) DO UPDATE SET ...`

---

## 5. Dual-Database Replication Hazards & Invariant Violations

The dual-database architecture introduces severe distributed consistency hazards that undermine critical business and regulatory invariants.

### 5.1 Hazard 1: Dual-Master Divergence & Out-of-Band Mutations
Because field inspectors write directly to Supabase via Vercel without coordinating with local SQLite, and cashiers write directly to SQLite without waiting for Supabase:
- **There is no distributed coordinator, Raft cluster, or two-phase commit (2PC).**
- Supabase and SQLite act as two independent masters.
- If the APMC broadband connection drops for 3 hours during peak morning trading (10:00 AM – 1:00 PM), local cashiers create invoices in SQLite while inspectors create tickets in Supabase.
- Neither system is aware of the other's state until reconnection, creating reconciliation collisions.

### 5.2 Hazard 2: Inadvertent Reversion of Status via LWW
- **Scenario:** A cashier links a pending QC ticket `QC-CHK-261103-8F8A` to Purchase Invoice `CHK-20261103-0012` and disburses Rs. 1,45,000 cash to the farmer.
- **The Defect:** In `server.py:2395`, the code executes:
  `cur.execute("UPDATE quality_inspections SET status='LINKED', invoice_id=? WHERE ticket_no=?", (invoice_id, qc_ticket_no))`
  It does **not** update `updated_at`, and does **not** push the update to Supabase.
- **The Consequence:** Supabase still retains `status='PENDING'`. On the next daemon cycle, `pull_supabase_to_local` pulls the cloud record. Because local `updated_at` was never bumped, the cloud record overwrites local SQLite. The ticket is reverted to `PENDING` and unlinked from the invoice.
- **Business Impact:** Fraudulent re-use of QC tickets for duplicate payouts; audit log detachment.

### 5.3 Hazard 3: Section 269ST Statutory Cash Limit Evasion
- **Statutory Rule:** Section 269ST of the Indian Income Tax Act prohibits cash transactions of **Rs. 2,00,000 or more** to any single person in a single day. Penalty for violation is 100% of the transacted amount under Section 271DA.
- **Local Implementation:** `calculations.py:check_cash_compliance()` checks total cash paid to a farmer across all invoices on the current date in local SQLite.
- **Cloud Implementation:** `supabase_sync.py:get_migration_sql()` defines a PostgreSQL trigger `fn_enforce_section_269st_cash_limit()` that raises an exception if cumulative cash on `purchase_invoices` reaches Rs. 2,00,000.
- **The Hazard:** If a farmer sells a lot at Yard A (Chikhali) for Rs. 1,20,000 cash, and another lot at Yard B (Varvand) for Rs. 1,10,000 cash:
  - While offline or partitioned, both local SQLite databases approve the cash payouts because each sees < Rs. 2,00,000.
  - When the databases attempt to sync to Supabase, the second invoice triggers a PostgreSQL trigger violation (`ERRCODE 269ST: Section 269ST Violation: Cumulative cash payout exceeds Rs. 200,000 limit`).
  - **Replication of that invoice halts permanently with a hard trigger abort!** The transaction exists locally as paid cash, but cannot be synchronized to the central cloud ledger.

### 5.4 Hazard 4: Zero Mandi Cess Invariant Conflicts
- Under the Maharashtra APMC Deregulation Act 2020, private commercial yards (such as Rajarshi Shahu Trading) are legally exempted from Mandi Cess (0.00%).
- `supabase_schema.sql` line 221 and `supabase_sync.py` line 448 enforce:
  `mandi_cess_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (mandi_cess_amount = 0.00)`
- In local SQLite, `mandi_cess_amount` is calculated as `0.0`. However, if any legacy invoice row or third-party client passes non-zero or null values, the PostgreSQL check constraint rejects the entire sync batch.

---

## 6. Architectural Weaknesses in On-Premise Core (`commoditi software`)

### 6.1 Synchronous Network Calls Inside Async Endpoints
In `server.py:4568`:
`api_get_pending_qc_tickets` is defined as a synchronous function (`def`). When the browser dashboard polls this endpoint every 10 seconds, it calls `supabase_sync.pull_supabase_to_local(["quality_inspections"])`. This executes synchronous network I/O against AWS Mumbai pooler or REST API. If the connection hangs or latency increases, FastAPI's default worker threadpool (`ThreadPoolExecutor`) is exhausted, stalling incoming local requests.

### 6.2 SQLite Single-Writer Lock Contention
During peak hours, multiple background threads and API handlers access SQLite:
1. `_supabase_cloud_sync_daemon` writing pulled records.
2. `api_inspector_submit_qc` writing inspection records.
3. Cashiers creating purchase invoices and cash payouts.
4. Weighbridge kanta workers updating truck gross/tare weights.  
Because SQLite in standard mode acquires an exclusive table lock during write transactions, concurrent writes trigger `sqlite3.OperationalError: database is locked`. `WAL` (Write-Ahead Logging) mode is activated in `database.py`, but long-running transactions in `pull_supabase_to_local` (which loops through up to 500 rows per table) still block local cashier commits.

---

## 7. Standardized Architectural Findings (AUD-101 to AUD-104)

### FINDING AUD-101: Dual-Master Split Brain Without Distributed Consensus
- **Severity:** CRITICAL
- **Module:** System Architecture & Topology
- **File / Lines:** `commoditi software/server.py:322-341`, `mandi-erp-tracker/api/inspections-submit.js:107-116`
- **Observed:** Two separate master databases (Supabase Cloud PostgreSQL vs Local APMC SQLite) accept concurrent writes for the same domain entities without a distributed transaction protocol.
- **Expected:** A clear primary-replica or single-master topology where all mutations flow through an authoritative consensus coordinator.
- **Actual:** Concurrent disconnected writes occur in public cloud and on-premise edge; conflict resolution relies on simple, non-monotonic Last-Write-Wins timestamps.
- **Evidence:** `inspections-submit.js` writes to Supabase without touching SQLite; `server.py` writes to SQLite without immediate Supabase confirmation.
- **Business Impact:** High probability of split-brain state, duplicate payments, and irreconcilable ledger discrepancies during network partitions.
- **Correction:** Designate Local APMC Edge as the authoritative master for all yard transactions (inspections, invoices, payouts). Route field mobile devices to the local edge when in the yard, using cloud strictly as an asynchronous reporting and multi-branch replica.
- **Tests:** Simulated network partition test verifying data reconciliation without record loss.
- **Dependencies:** `supabase_sync`.

---

### FINDING AUD-102: Blocking Cloud Network I/O Inside Local Cashier Polling Path
- **Severity:** HIGH
- **Module:** API Performance & Thread Safety
- **File / Lines:** `commoditi software/server.py:4567-4587`
- **Observed:** Endpoint `/api/inspector/tickets/pending` performs a synchronous network pull from Supabase Cloud on every call.
- **Expected:** Endpoints serving the cashier desk must read strictly from the local edge cache and return in < 15ms.
- **Actual:** Every 10-second cashier dashboard poll blocks for 1–8 seconds waiting for cloud network responses.
- **Evidence:** `server.py` line 4578: `supabase_sync.pull_supabase_to_local(["quality_inspections"])` inside `api_get_pending_qc_tickets`.
- **Business Impact:** Degraded user experience, UI freezing, and server threadpool exhaustion when internet is slow.
- **Correction:** Remove `pull_supabase_to_local()` from the HTTP GET handler. Rely entirely on the background sync daemon or Supabase Realtime WebSocket listener.
- **Tests:** Benchmark response times of `/api/inspector/tickets/pending` during simulated network drop.
- **Dependencies:** None.

---

### FINDING AUD-103: Section 269ST Statutory Ceiling Evasion Across Multiple APMC Yards
- **Severity:** HIGH
- **Module:** Regulatory Compliance Engine
- **File / Lines:** `commoditi software/calculations.py:67-71`, `commoditi software/supabase_sync.py:586-608`
- **Observed:** Local edge nodes validate cash limits against local history only; cross-yard daily cash aggregation is checked only after replication.
- **Expected:** Multi-yard cash aggregation must prevent cumulative daily payouts exceeding Rs. 1,99,999 across all company yards.
- **Actual:** A farmer can receive Rs. 1,50,000 cash at Chikhali and Rs. 1,50,000 cash at Varvand on the same day without either local cashier being alerted.
- **Evidence:** `calculations.py` line 67 checks local SQLite `purchase_invoices` for `party_id` on `today_str`.
- **Business Impact:** Severe statutory non-compliance. Company faces 100% financial penalty under Section 271DA (Rs. 3,00,000 penalty on a Rs. 3,00,000 cash transaction).
- **Correction:** Before approving cash payout > Rs. 50,000, cashier desk must perform a low-latency cloud query for the farmer's global daily cash total, or automatically force RTGS mode when connectivity is partitioned.
- **Tests:** Multi-branch transaction simulation asserting rejection of cumulative cash across yards.
- **Dependencies:** `calculations.py`, `supabase_sync.py`.

---

### FINDING AUD-104: Long-Running Replication Transactions Holding SQLite Write Lock
- **Severity:** MEDIUM
- **Module:** Database Concurrency
- **File / Lines:** `commoditi software/supabase_sync.py:1089-1178`
- **Observed:** `pull_supabase_to_local()` opens a single SQLite transaction and loops through hundreds of remote rows across multiple tables before committing.
- **Expected:** Replication upserts should be batched in small chunks or performed with short-lived transactions to minimize SQLite write lock hold times.
- **Actual:** Single transaction holds SQLite lock for hundreds of milliseconds, triggering `database is locked` errors on cashier invoice saves.
- **Evidence:** `supabase_sync.py` line 1089 opens `local_cur` and commits only at line 1178 after iterating through all target tables.
- **Business Impact:** Cashiers encounter intermittent `"Internal Server Error: database is locked"` when finalizing purchase invoices.
- **Correction:** Commit after each table or batch of 50 records; utilize immediate release and WAL checkpoint tuning.
- **Tests:** Concurrent load test running `pull_supabase_to_local` while issuing 10 simultaneous cashier invoice saves.
- **Dependencies:** `sqlite3`.

---

## 8. Summary & Strategic Architecture Recommendations

1. **Establish Local Edge as Authority (Edge-First Principle):**  
   The physical Mandi yard must never depend on public cloud availability for primary trade execution. Field tablets, weighbridges, and cashier terminals must communicate primarily with the local Mandi edge server on the yard LAN (`192.168.0.x`).
2. **Implement Supabase Realtime Outbound Bridge:**  
   To allow remote inspectors outside the yard Wi-Fi to submit tickets via Vercel/Supabase, the local edge server must maintain an outbound persistent WebSocket to Supabase Realtime (`wss://.../realtime/v1/websocket`). This eliminates polling latency and delivers remote tickets to local SQLite in under 250ms.
3. **Formalize State Transitions & Idempotent Upserts:**  
   Replace naïve Last-Write-Wins timestamp comparisons with explicit state machine guards (e.g., `PENDING` -> `LINKED` -> `PAID`). Once a ticket is marked `LINKED`, it must be immutable against cloud pull overwrites.
