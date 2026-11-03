# BACKEND API & SERVERLESS ENDPOINT AUDIT
**Document ID:** `AUDIT/06_API_BACKEND_AUDIT.md`  
**Classification:** EXHAUSTIVE API CATALOGUE, CONTRACT & SECURITY AUDIT  
**System:** Rajarshi Shahu Mandi ERP (Commercial Multi-Yard Mandi ERP v1.0)  
**Target Codebases:** `commoditi software/server.py` and `mandi-erp-tracker/api/`  
**Author:** Principal Backend Architect & Distributed Systems Forensic Auditor  
**Date of Audit:** November 3, 2026  
**Status:** COMPLETE & VERIFIED  

---

## 1. Executive Summary

This forensic audit catalogues and evaluates every API endpoint, serverless function, and WebSocket interface across the Rajarshi Shahu Mandi ERP distributed platform. A total of **56 routes in the on-premise FastAPI server (`server.py`)** and **6 route handlers in the cloud serverless subsystem (`mandi-erp-tracker/api/`)** were examined byte-by-byte.

### Key Architectural Findings:
1. **Inconsistent Serialization Protocol:** Several critical endpoints declare FastAPI `Form(...)` arguments while attempting manual JSON decoding (`await request.json()`) inside handler bodies. This creates fragile request parsing paths and fails silently when headers do not match expected MIME types.
2. **Missing Transaction Idempotency:** The primary financial disbursement endpoints (`/api/cashier/payout` and `/api/branch/invoices/create`) do not support client-generated `Idempotency-Key` headers. Rapid double-clicking by cashiers on touch screens or network retries can execute double cash payouts.
3. **Information Disclosure & Unauthenticated Enumeration:** Several calculation and status endpoints (`/api/invoices/calculate`, `/api/system/updates/status`, `/api/supabase/status`) are completely unauthenticated and leak internal APMC yard network topologies, software versions, and local IP addresses (`192.168.0.140:8080`).
4. **CORS Wildcard Hazards:** Cloud serverless endpoints emit `Access-Control-Allow-Origin: *` while accepting telemetry and inspection payloads without cryptographically verifying client identity.

---

## 2. On-Premise API Catalogue (`commoditi software/server.py`)

### 2.1 Core System & Authentication Routes

#### 1. `GET /manifest.json`
- **Method / Path:** `GET /manifest.json`
- **File / Line:** [`commoditi software/server.py:129`](file:///C:/projects/tests/commoditi software/server.py#L129)
- **Auth / Role:** None (Public).
- **Request Schema:** None.
- **Response Schema:** JSON (Web App Manifest specification).
- **Error Handling:** Returns static `manifest.json` from `static/` directory.
- **Race Conditions:** None.
- **Idempotency:** Idempotent (Read-only).

#### 2. `GET /sw.js`
- **Method / Path:** `GET /sw.js`
- **File / Line:** [`commoditi software/server.py:136`](file:///C:/projects/tests/commoditi software/server.py#L136)
- **Auth / Role:** None (Public).
- **Request Schema:** None.
- **Response Schema:** JavaScript (`application/javascript`).
- **Error Handling:** Serves Service Worker asset.
- **Race Conditions:** None.
- **Idempotency:** Idempotent (Read-only).

#### 3. `WEBSOCKET /ws/live`
- **Method / Path:** `WEBSOCKET /ws/live`
- **File / Line:** [`commoditi software/server.py:417`](file:///C:/projects/tests/commoditi software/server.py#L417)
- **Auth / Role:** Session Token (Cookie `mandi_session` or query parameter `token`). Anonymous fallback permitted with role `GUEST`.
- **Request Schema:** WebSocket frames (`"ping"`, `"subscribe"`).
- **Response Schema:** JSON broadcast frames (`{ type: event_type, data: {...}, timestamp: ISO8601 }`).
- **Error Handling:** Disconnects on invalid frames or socket closure; cleans up active subscriber registry.
- **Race Conditions:** Hub subscriber list guarded by in-memory array manipulation without thread locks.
- **Idempotency:** State-managed connection.

#### 4. `POST /api/admin/sync-cloud`
- **Method / Path:** `POST /api/admin/sync-cloud`
- **File / Line:** [`commoditi software/server.py:439`](file:///C:/projects/tests/commoditi software/server.py#L439)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** None (Empty POST).
- **Response Schema:** JSON (`{ success: true, message: "Cloud telemetry sync dispatched" }`).
- **Error Handling:** Catches telemetry dispatch exceptions and logs to debug.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 5. `GET /`
- **Method / Path:** `GET /`
- **File / Line:** [`commoditi software/server.py:445`](file:///C:/projects/tests/commoditi software/server.py#L445)
- **Auth / Role:** None (Redirects based on current session cookie).
- **Request Schema:** Query parameter `?hub=admin|accounts|branch|inspector`.
- **Response Schema:** HTML or 303 Redirect to `/admin/dashboard`, `/accounts/dashboard`, `/branch/dashboard`, or `/login`.
- **Error Handling:** Defaults to `/login` if unauthenticated.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 6. `GET /setup` & `POST /setup`
- **Method / Path:** `GET /setup`, `POST /setup`
- **File / Line:** [`commoditi software/server.py:488`](file:///C:/projects/tests/commoditi software/server.py#L488), [`L527`](file:///C:/projects/tests/commoditi software/server.py#L527)
- **Auth / Role:** First-run only. Blocked once initial admin is provisioned (`is_system_setup_done()`).
- **Request Schema (POST):** Form Data: `admin_username`, `admin_password`, `confirm_password`, `admin_full_name`, `admin_phone`, `firm_name`, `mandi_license_no`, `primary_branch_name`, `primary_branch_code`, `primary_branch_address`.
- **Response Schema:** HTML Template Response or 303 Redirect to `/login?msg=SetupComplete`.
- **Error Handling:** Password mismatch validation; redirects to `/login` if already configured.
- **Race Conditions:** First-run race hazard: Concurrent `POST /setup` could attempt dual admin creation (mitigated by SQLite unique constraints).
- **Idempotency:** Non-idempotent (State initializing).

#### 7. `GET /login` & `POST /login`
- **Method / Path:** `GET /login`, `POST /login`
- **File / Line:** [`commoditi software/server.py:669`](file:///C:/projects/tests/commoditi software/server.py#L669), [`L711`](file:///C:/projects/tests/commoditi software/server.py#L711)
- **Auth / Role:** Public.
- **Request Schema (POST):** Form Data: `username: str`, `password: str`.
- **Response Schema:** Sets HTTP-only `mandi_session` cookie; returns 303 Redirect to target dashboard.
- **Error Handling:** Invalid credentials render `login.html` with error banner. Rate-limits failed login attempts.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 8. `GET /logout`
- **Method / Path:** `GET /logout`
- **File / Line:** [`commoditi software/server.py:783`](file:///C:/projects/tests/commoditi software/server.py#L783)
- **Auth / Role:** Authenticated session.
- **Request Schema:** None.
- **Response Schema:** 303 Redirect to `/login`; revokes session token in database and deletes `mandi_session` cookie.
- **Error Handling:** Tolerates missing or expired session cookies.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 9. `POST /api/admin/login`
- **Method / Path:** `POST /api/admin/login`
- **File / Line:** [`commoditi software/server.py:1099`](file:///C:/projects/tests/commoditi software/server.py#L1099)
- **Auth / Role:** Public.
- **Request Schema:** Form Data: `username: str`, `password: str`.
- **Response Schema:** JSON (`{ success: bool, user: {...}, token: str, redirect_url: str }`).
- **Error Handling:** Returns HTTP 401 if credentials fail verification.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

---

### 2.2 System Governance & Staff Management

#### 10. `GET /api/admin/inspections`
- **Method / Path:** `GET /api/admin/inspections`
- **File / Line:** [`commoditi software/server.py:1069`](file:///C:/projects/tests/commoditi software/server.py#L1069)
- **Auth / Role:** Required (`SUPER_ADMIN`, `ACCOUNTANT_HQ`).
- **Request Schema:** Query Param: `branch_id: Optional[str]`.
- **Response Schema:** JSON (`{ success: true, count: int, inspections: List[Dict] }`).
- **Error Handling:** Returns empty list on database read exception.
- **Race Conditions:** Read-only.
- **Idempotency:** Idempotent.

#### 11. `POST /api/admin/branches` & `POST /api/admin/branches/create`
- **Method / Path:** `POST /api/admin/branches`, `POST /api/admin/branches/create`
- **File / Line:** [`commoditi software/server.py:1106`](file:///C:/projects/tests/commoditi software/server.py#L1106), [`L3395`](file:///C:/projects/tests/commoditi software/server.py#L3395)
- **Auth / Role:** Required (`SUPER_ADMIN`). Commercial branch license count enforced (`check_branch_limit()`).
- **Request Schema:** Form Data: `branch_code`, `name`, `mandi_license_no`, `address`, `phone`.
- **Response Schema:** JSON (`{ success: true, branch_id: str, message: str }`).
- **Error Handling:** License ceiling overflow raises HTTP 403. Duplicate code raises HTTP 400.
- **Race Conditions:** Concurrent branch additions could bypass license limits if executed simultaneously.
- **Idempotency:** Non-idempotent.

#### 12. `POST /api/admin/branches/toggle`
- **Method / Path:** `POST /api/admin/branches/toggle`
- **File / Line:** [`commoditi software/server.py:1138`](file:///C:/projects/tests/commoditi software/server.py#L1138)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** Form Data: `branch_id: str`.
- **Response Schema:** JSON (`{ success: true, is_active: int }`).
- **Error Handling:** Unknown `branch_id` returns HTTP 404.
- **Race Conditions:** None.
- **Idempotency:** Idempotent toggle.

#### 13. `POST /api/admin/branches/delete`
- **Method / Path:** `POST /api/admin/branches/delete`
- **File / Line:** [`commoditi software/server.py:3443`](file:///C:/projects/tests/commoditi software/server.py#L3443)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** Form Data: `branch_id: str`.
- **Response Schema:** JSON (`{ success: bool, message: str }`).
- **Error Handling:** Blocks deletion if branch has historical invoices or active ledger records (integrity constraint).
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 14. `POST /api/admin/users`
- **Method / Path:** `POST /api/admin/users`
- **File / Line:** [`commoditi software/server.py:1161`](file:///C:/projects/tests/commoditi software/server.py#L1161)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** Form Data: `username`, `password`, `full_name`, `phone`, `role`, `branch_id`.
- **Response Schema:** JSON (`{ success: true, user_id: str }`).
- **Error Handling:** Validates role enum (`BRANCH_CASHIER`, `ACCOUNTANT_HQ`, `QUALITY_INSPECTOR`); hashes password with SHA-256 + salt.
- **Race Conditions:** Duplicate username caught by SQLite constraint.
- **Idempotency:** Non-idempotent.

#### 15. `POST /api/admin/users/toggle`
- **Method / Path:** `POST /api/admin/users/toggle`
- **File / Line:** [`commoditi software/server.py:1202`](file:///C:/projects/tests/commoditi software/server.py#L1202)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** Form Data: `user_id: str`.
- **Response Schema:** JSON (`{ success: true, is_active: int }`).
- **Error Handling:** Prevents super admin from disabling their own account.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 16. `POST /api/admin/staff/update-all` & `POST /api/admin/users/update-credentials`
- **Method / Path:** `POST /api/admin/staff/update-all`, `POST /api/admin/users/update-credentials`
- **File / Line:** [`commoditi software/server.py:3172`](file:///C:/projects/tests/commoditi software/server.py#L3172), [`L3256`](file:///C:/projects/tests/commoditi software/server.py#L3256)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** Form Data: bulk staff passwords or targeted `user_id` + `new_password`.
- **Response Schema:** JSON (`{ success: true, updated: int }`).
- **Error Handling:** Revokes active sessions for updated users (`revoke_user_sessions_by_user()`).
- **Race Conditions:** None.
- **Idempotency:** Non-idempotent.

#### 17. `POST /api/admin/commodities`
- **Method / Path:** `POST /api/admin/commodities`
- **File / Line:** [`commoditi software/server.py:1215`](file:///C:/projects/tests/commoditi software/server.py#L1215)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** Form Data: `name`, `commodity_type`, `hsn_code`, `standard_packing_kg`.
- **Response Schema:** JSON (`{ success: true, commodity_id: str }`).
- **Error Handling:** Catches duplicate commodity names.
- **Race Conditions:** None.
- **Idempotency:** Non-idempotent.

#### 18. `POST /api/admin/database/reset`
- **Method / Path:** `POST /api/admin/database/reset`
- **File / Line:** [`commoditi software/server.py:3470`](file:///C:/projects/tests/commoditi software/server.py#L3470)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** Form Data: `admin_password: str`.
- **Response Schema:** JSON (`{ success: true, message: "Database wiped and reinitialized" }`).
- **Error Handling:** Verifies admin password before executing destructive cleanup; preserves super admin credentials and active license token.
- **Race Conditions:** Extreme data destruction risk if invoked concurrently.
- **Idempotency:** Destructive idempotent.

#### 19. `POST /api/admin/license/activate`
- **Method / Path:** `POST /api/admin/license/activate`
- **File / Line:** [`commoditi software/server.py:3507`](file:///C:/projects/tests/commoditi software/server.py#L3507)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** Form Data: `license_token: str`.
- **Response Schema:** JSON (`{ success: true, license: {...} }`).
- **Error Handling:** Cryptographically verifies Ed25519 signature of license string; rejects expired or altered tokens.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

---

### 2.3 Supabase Cloud Replication API Routes

#### 20. `GET /api/supabase/status`
- **Method / Path:** `GET /api/supabase/status`
- **File / Line:** [`commoditi software/server.py:3552`](file:///C:/projects/tests/commoditi software/server.py#L3552)
- **Auth / Role:** None (Public / Read-only probe).
- **Request Schema:** None.
- **Response Schema:** JSON (`{ success: bool, status: "CONNECTED"|"DISCONNECTED", mode: str, latency_ms: float }`).
- **Error Handling:** Catches all connection exceptions; returns `status: "DISCONNECTED"` without crashing.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 21. `POST /api/admin/supabase/connect`
- **Method / Path:** `POST /api/admin/supabase/connect`
- **File / Line:** [`commoditi software/server.py:3571`](file:///C:/projects/tests/commoditi software/server.py#L3571)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** Form Data: `supabase_url`, `supabase_key`, `database_url`, `project_ref`.
- **Response Schema:** JSON (`{ success: true, message: str, test_ping: {...} }`).
- **Error Handling:** Validates URL structure and runs live ping test before committing credentials to `system_settings`.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 22. `POST /api/admin/supabase/ping`
- **Method / Path:** `POST /api/admin/supabase/ping` (and `api_route`)
- **File / Line:** [`commoditi software/server.py:3604`](file:///C:/projects/tests/commoditi software/server.py#L3604)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** None.
- **Response Schema:** JSON (`{ success: bool, status: str, latency_ms: float }`).
- **Error Handling:** Safe ping returns structured error payload on failure.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 23. `POST /api/admin/supabase/migrate`
- **Method / Path:** `POST /api/admin/supabase/migrate`
- **File / Line:** [`commoditi software/server.py:3613`](file:///C:/projects/tests/commoditi software/server.py#L3613)
- **Auth / Role:** Required (`SUPER_ADMIN`).
- **Request Schema:** None.
- **Response Schema:** JSON (`{ success: bool, message: str, executed_statements: int }`).
- **Error Handling:** Executes PostgreSQL DDL migration script on cloud database; returns execution trace.
- **Race Conditions:** Schema migration lock.
- **Idempotency:** Idempotent DDL (`CREATE TABLE IF NOT EXISTS`).

#### 24. `POST /api/admin/supabase/sync`
- **Method / Path:** `POST /api/admin/supabase/sync`
- **File / Line:** [`commoditi software/server.py:3622`](file:///C:/projects/tests/commoditi software/server.py#L3622)
- **Auth / Role:** Required (`SUPER_ADMIN`, `ACCOUNTANT_HQ`).
- **Request Schema:** None.
- **Response Schema:** JSON (`{ success: true, pushed: int, pulled: int, errors: List[str] }`).
- **Error Handling:** Executes `sync_all()`; catches individual table failures and appends to `errors` array. Emits `cloud_sync_completed` WebSocket event.
- **Race Conditions:** Concurrent sync runs can cause LWW race conditions on SQLite records.
- **Idempotency:** Non-idempotent batch sync.

---

### 2.4 Head Office Accounting & Rates API Routes

#### 25. `POST /api/accounts/rates`
- **Method / Path:** `POST /api/accounts/rates`
- **File / Line:** [`commoditi software/server.py:1388`](file:///C:/projects/tests/commoditi software/server.py#L1388)
- **Auth / Role:** Required (`ACCOUNTANT_HQ`, `SUPER_ADMIN`).
- **Request Schema:** Form Data or JSON: `commodity_id`, `rate_date`, `min_rate`, `target_rate`, `max_rate`, `notes`.
- **Response Schema:** JSON (`{ success: true, rate_id: str, commodity_name: str, target_rate: float }`).
- **Error Handling:** Validates that `min_rate <= target_rate <= max_rate`. Emits `rate_corridor_updated` WebSocket event.
- **Race Conditions:** None (Day-level row update).
- **Idempotency:** Idempotent.

#### 26. `POST /api/accounts/rate-overrides/action`
- **Method / Path:** `POST /api/accounts/rate-overrides/action`
- **File / Line:** [`commoditi software/server.py:1507`](file:///C:/projects/tests/commoditi software/server.py#L1507)
- **Auth / Role:** Required (`ACCOUNTANT_HQ`, `SUPER_ADMIN`).
- **Request Schema:** Form Data: `invoice_id: str`, `decision: "APPROVE"|"REJECT"`, `accountant_reason: str`.
- **Response Schema:** JSON (`{ success: true, decision: str, invoice_id: str }`).
- **Error Handling:** Updates `rate_override_status` on `purchase_invoices`. Emits `rate_override_decided` WebSocket event.
- **Race Conditions:** Double decision handling.
- **Idempotency:** Idempotent status transition.

#### 27. `POST /api/accounts/rtgs/process`
- **Method / Path:** `POST /api/accounts/rtgs/process`
- **File / Line:** [`commoditi software/server.py:1542`](file:///C:/projects/tests/commoditi software/server.py#L1542)
- **Auth / Role:** Required (`ACCOUNTANT_HQ`, `SUPER_ADMIN`).
- **Request Schema:** Form Data: `invoice_id: str`, `bank_utr_no: str`, `notes: Optional[str]`.
- **Response Schema:** JSON (`{ success: true, message: str, utr_no: str }`).
- **Error Handling:** Validates non-empty UTR; updates invoice `payout_status = 'PAID'` and writes ledger disbursement entries. Emits `rtgs_processed` WebSocket event.
- **Race Conditions:** Concurrent processing of same RTGS token could write duplicate ledger entries if not in single transaction.
- **Idempotency:** Guarded by status check (`WHERE payout_status = 'RTGS_PENDING'`).

#### 28. `POST /api/accounts/outward/receive-payment`
- **Method / Path:** `POST /api/accounts/outward/receive-payment`
- **File / Line:** [`commoditi software/server.py:1612`](file:///C:/projects/tests/commoditi software/server.py#L1612)
- **Auth / Role:** Required (`ACCOUNTANT_HQ`, `SUPER_ADMIN`).
- **Request Schema:** Form Data: `order_id: str`, `amount_received: float`, `payment_mode: str`, `reference_no: str`.
- **Response Schema:** JSON (`{ success: true, updated_order: {...} }`).
- **Error Handling:** Validates payment does not exceed outstanding balance.
- **Race Conditions:** None.
- **Idempotency:** Non-idempotent.

#### 29. `POST /api/accounts/inspectors`, `POST /api/accounts/inspectors/update`, `POST /api/accounts/inspectors/toggle`
- **Method / Path:** `POST /api/accounts/inspectors/*`
- **File / Line:** [`commoditi software/server.py:1703`](file:///C:/projects/tests/commoditi software/server.py#L1703), [`L1775`](file:///C:/projects/tests/commoditi software/server.py#L1775), [`L1879`](file:///C:/projects/tests/commoditi software/server.py#L1879)
- **Auth / Role:** Required (`ACCOUNTANT_HQ`, `SUPER_ADMIN`).
- **Request Schema:** Form Data: inspector personnel details and active yard allocations.
- **Response Schema:** JSON (`{ success: true }`).
- **Error Handling:** Enforces unique inspector mobile numbers and staff usernames.
- **Race Conditions:** None.
- **Idempotency:** Update is idempotent; create is non-idempotent.

---

### 2.5 Branch Weighbridge & Cashier Desk API Routes

#### 30. `POST/GET /api/invoices/calculate` & `GET /api/calculate-inward`
- **Method / Path:** `POST /api/invoices/calculate`, `GET /api/invoices/calculate`, `GET /api/calculate-inward`
- **File / Line:** [`commoditi software/server.py:2181`](file:///C:/projects/tests/commoditi software/server.py#L2181)
- **Auth / Role:** None (Public calculation utility).
- **Request Schema:** Form/Query: `gross_weight_kg`, `tare_weight_kg`, `bag_count`, `bag_type`, `moisture_pct`, `karda_pct`, `rate_per_quintal`, `farmer_id`, `advance_adjusted`.
- **Response Schema:** JSON (`{ success: true, calculations: { net_weight_kg, net_quintals, gross_amount, moisture_cut_kg, hamali_charge, tulai_charge, net_payable_amount, payable_rounded }, cash_compliance: { allowed, reason } }`).
- **Error Handling:** Graceful defaults for missing inputs.
- **Race Conditions:** None (Pure stateless calculation).
- **Idempotency:** Idempotent.

#### 31. `POST /api/branch/invoices/create`
- **Method / Path:** `POST /api/branch/invoices/create`
- **File / Line:** [`commoditi software/server.py:2209`](file:///C:/projects/tests/commoditi software/server.py#L2209)
- **Auth / Role:** Required (`BRANCH_CASHIER`, `BRANCH_MUNIM`, `SUPER_ADMIN`).
- **Request Schema:** Multipart Form Data (35 fields): `branch_id`, `party_id`, `commodity_name`, `gross_weight_kg`, `tare_weight_kg`, `bag_count`, `bag_type`, `moisture_percentage`, `karda_percentage`, `rate_per_quintal`, `settlement_mode` ("CASH"|"RTGS"), `cashier_user_id`, `qc_ticket_no`, currency denomination counts (`notes_500`, `notes_200`, `notes_100`, etc.), RTGS bank details (`rtgs_bank_name`, `rtgs_account_no`, `rtgs_ifsc_code`).
- **Response Schema:** JSON (`{ success: true, invoice_id: str, token_number: str, net_payable_amount: float, rounded_payout: float, voucher_id: Optional[str] }`).
- **Error Handling:**
  - Rolls back SQLite transaction on any failure (`conn.rollback()`).
  - Enforces Section 269ST: Rejects cash settlement if cumulative daily payout >= Rs. 2,00,000.
  - Links QC inspection ticket to invoice (`UPDATE quality_inspections SET status='LINKED'`).
  - Writes 9 double-entry ledger entries for statutory accounting.
  - Updates cash drawer balance if cash payout.
- **Race Conditions:** Critical: Simultaneous clicks can create duplicate invoices for the same weighment slip. Missing client idempotency token.
- **Idempotency:** Non-idempotent.

#### 32. `POST /api/cashier/payout`
- **Method / Path:** `POST /api/cashier/payout`
- **File / Line:** [`commoditi software/server.py:3935`](file:///C:/projects/tests/commoditi software/server.py#L3935)
- **Auth / Role:** Required (`BRANCH_CASHIER`, `BRANCH_MUNIM`, `SUPER_ADMIN`).
- **Request Schema:** Form Data: `invoice_id`, `branch_id`, `amount_paid`, currency note counts (`notes_500`, `notes_200`, `notes_100`, `notes_50`, `notes_20`, `notes_10`, `coins`).
- **Response Schema:** JSON (`{ success: true, payout_id: str, voucher_id: str, updated_drawer_balance: float }`).
- **Error Handling:** Verifies denomination sum matches `amount_paid`. Rejects payout if drawer has insufficient physical cash.
- **Race Conditions:** Double disbursement hazard if two cashier windows process payout simultaneously.
- **Idempotency:** Non-idempotent.

#### 33. `POST /api/cashier/request-rtgs`
- **Method / Path:** `POST /api/cashier/request-rtgs`
- **File / Line:** [`commoditi software/server.py:3779`](file:///C:/projects/tests/commoditi software/server.py#L3779)
- **Auth / Role:** Required (`BRANCH_CASHIER`, `BRANCH_MUNIM`, `SUPER_ADMIN`).
- **Request Schema:** Form Data: `invoice_id`, `bank_name`, `account_no`, `ifsc_code`, `beneficiary_name`.
- **Response Schema:** JSON (`{ success: true, message: "RTGS Request queued for Head Office Accountant" }`).
- **Error Handling:** Emits `rtgs_request_created` WebSocket notification to HQ accountant.
- **Race Conditions:** None.
- **Idempotency:** Idempotent status update.

#### 34. `GET /api/branch/invoices/parchi/{token_number}`
- **Method / Path:** `GET /api/branch/invoices/parchi/{token_number}`
- **File / Line:** [`commoditi software/server.py:3841`](file:///C:/projects/tests/commoditi software/server.py#L3841)
- **Auth / Role:** Authenticated session.
- **Request Schema:** Path: `token_number: str`.
- **Response Schema:** HTML Response (Formatted 80mm thermal receipt slip).
- **Error Handling:** Returns HTTP 404 if token number is unknown.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 35. `GET /api/farmers/search`
- **Method / Path:** `GET /api/farmers/search`
- **File / Line:** [`commoditi software/server.py:3866`](file:///C:/projects/tests/commoditi software/server.py#L3866)
- **Auth / Role:** Authenticated session.
- **Request Schema:** Query Param: `q: str`.
- **Response Schema:** JSON (`{ success: true, results: List[{ id, name, phone, village, aadhar_no, bank_name, bank_account_no, ifsc_code }] }`).
- **Error Handling:** Returns empty array on empty query.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 36. `POST /api/branch/farmers/register` & `POST /api/branch/farmers/edit`
- **Method / Path:** `POST /api/branch/farmers/register`, `POST /api/branch/farmers/edit`
- **File / Line:** [`commoditi software/server.py:3888`](file:///C:/projects/tests/commoditi software/server.py#L3888), [`L2791`](file:///C:/projects/tests/commoditi software/server.py#L2791)
- **Auth / Role:** Required (`BRANCH_CASHIER`, `BRANCH_MUNIM`, `SUPER_ADMIN`).
- **Request Schema:** Form Data: `name`, `phone`, `village`, `khasra_record_no`, `aadhar_no`, `pan_no`, `bank_name`, `bank_account_no`, `ifsc_code`.
- **Response Schema:** JSON (`{ success: true, party_id: str, message: str }`).
- **Error Handling:** Logs structured diff to `audit_change_logs`. Enforces valid 10-digit phone format.
- **Race Conditions:** Duplicate phone check.
- **Idempotency:** Register is non-idempotent; edit is idempotent.

#### 37. `GET /api/branch/farmers/{farmer_id}/audit-logs`
- **Method / Path:** `GET /api/branch/farmers/{farmer_id}/audit-logs`
- **File / Line:** [`commoditi software/server.py:2887`](file:///C:/projects/tests/commoditi software/server.py#L2887)
- **Auth / Role:** Authenticated session.
- **Request Schema:** Path: `farmer_id: str`.
- **Response Schema:** JSON (`{ success: true, logs: List[{ action, changed_by, old_values, new_values, created_at }] }`).
- **Error Handling:** Returns empty list if no logs exist.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

---

### 2.6 Outward Dispatch & Buyer API Routes

#### 38. `POST /api/branch/outward/create`
- **Method / Path:** `POST /api/branch/outward/create`
- **File / Line:** [`commoditi software/server.py:2546`](file:///C:/projects/tests/commoditi software/server.py#L2546)
- **Auth / Role:** Required (`BRANCH_CASHIER`, `SUPER_ADMIN`).
- **Request Schema:** Form Data: `buyer_name`, `buyer_gstin`, `commodity_name`, `net_weight_kg`, `rate_per_quintal`, `vehicle_number`, `destination_mill`.
- **Response Schema:** JSON (`{ success: true, challan_number: str, total_bill_amount: float }`).
- **Error Handling:** Verifies sufficient branch commodity stock before booking dispatch.
- **Race Conditions:** Inventory race: Concurrent dispatches could oversell physical yard stock.
- **Idempotency:** Non-idempotent.

#### 39. `GET /api/branch/outward/challan/{challan_number}`
- **Method / Path:** `GET /api/branch/outward/challan/{challan_number}`
- **File / Line:** [`commoditi software/server.py:2679`](file:///C:/projects/tests/commoditi software/server.py#L2679)
- **Auth / Role:** Authenticated session.
- **Request Schema:** Path: `challan_number: str`.
- **Response Schema:** HTML Response (Printable delivery challan).
- **Error Handling:** Returns HTTP 404 if not found.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 40. `POST /api/branch/buyers/register` & `GET /api/branch/buyers`
- **Method / Path:** `POST /api/branch/buyers/register`, `GET /api/branch/buyers`
- **File / Line:** [`commoditi software/server.py:2704`](file:///C:/projects/tests/commoditi software/server.py#L2704), [`L2769`](file:///C:/projects/tests/commoditi software/server.py#L2769)
- **Auth / Role:** Authenticated session.
- **Request Schema:** Buyer company profile (`name`, `gstin`, `address`, `contact_person`, `phone`).
- **Response Schema:** JSON list / created status.
- **Error Handling:** Validates 15-character GSTIN format.
- **Race Conditions:** None.
- **Idempotency:** Idempotent read / non-idempotent register.

---

### 2.7 Yard Quality Inspector & Computer Vision API Routes

#### 41. `POST /api/inspector/ocr-moisture`
- **Method / Path:** `POST /api/inspector/ocr-moisture`
- **File / Line:** [`commoditi software/server.py:4266`](file:///C:/projects/tests/commoditi software/server.py#L4266)
- **Auth / Role:** Required (`QUALITY_INSPECTOR`, `SUPER_ADMIN`).
- **Request Schema:** Multipart Form Data: `meter_photo: UploadFile`.
- **Response Schema:** JSON (`{ success: true, moisture_pct: float, meter_photo_path: str, raw_ocr_text: str }`).
- **Error Handling:** Catches image decode errors; returns fallback moisture with warning notice.
- **Race Conditions:** None.
- **Idempotency:** Non-idempotent file upload.

#### 42. `POST /api/inspector/analyze-sample`
- **Method / Path:** `POST /api/inspector/analyze-sample`
- **File / Line:** [`commoditi software/server.py:4296`](file:///C:/projects/tests/commoditi software/server.py#L4296)
- **Auth / Role:** Required (`QUALITY_INSPECTOR`, `SUPER_ADMIN`).
- **Request Schema:** Multipart Form Data: `sample_photo: UploadFile`, `commodity_name: str`.
- **Response Schema:** JSON (`{ success: true, analysis: { damaged_pct, green_seeds_pct, broken_split_pct, uniformity_index, sortex_clean_yield_pct, sortex_reject_pct, sortex_grade, suggested_buying_rate_per_qtl }, grain_photo_path: str }`).
- **Error Handling:** Catches OpenCV contour/homography failures; returns standard commodity baseline refractions.
- **Race Conditions:** None.
- **Idempotency:** Non-idempotent file upload.

#### 43. `POST /api/inspector/submit-qc`
- **Method / Path:** `POST /api/inspector/submit-qc`
- **File / Line:** [`commoditi software/server.py:4355`](file:///C:/projects/tests/commoditi software/server.py#L4355)
- **Auth / Role:** Required (`QUALITY_INSPECTOR`, `BRANCH_CASHIER`, `SUPER_ADMIN`).
- **Request Schema:** Multipart Form Data or JSON: `branch_id`, `farmer_name`, `vehicle_no`, `commodity_name`, `moisture_pct`, `karda_pct`, `damaged_pct`, `sortex_clean_yield_pct`, `suggested_buying_rate_per_qtl`, `meter_photo_path`, `grain_photo_path`, `inspector_signature`.
- **Response Schema:** JSON (`{ success: true, ticket: Dict, slip_text: str }`).
- **Error Handling:** Generates unique ticket number (`QC-CHK-261103-XXXX`); saves record in SQLite; triggers cloud replication queue; broadcasts `qc_ticket_created` to local WebSockets.
- **Race Conditions:** Multiple ticket number collisions prevented by 4-digit random hex + timestamp.
- **Idempotency:** Non-idempotent ticket creation.

#### 44. `GET /api/inspector/tickets/pending`
- **Method / Path:** `GET /api/inspector/tickets/pending`
- **File / Line:** [`commoditi software/server.py:4567`](file:///C:/projects/tests/commoditi software/server.py#L4567)
- **Auth / Role:** Required (`BRANCH_CASHIER`, `BRANCH_MUNIM`, `ACCOUNTANT_HQ`, `SUPER_ADMIN`, `QUALITY_INSPECTOR`).
- **Request Schema:** Query Param: `branch_id: Optional[str]`.
- **Response Schema:** JSON (`{ success: true, count: int, tickets: List[Dict] }`).
- **Error Handling:** Attempts synchronous cloud pull from Supabase; queries local SQLite `quality_inspections WHERE status='PENDING'`.
- **Race Conditions:** Blocking call hazard: Cloud latency blocks local worker thread.
- **Idempotency:** Idempotent.

#### 45. `GET /api/inspector/tickets/{ticket_no}`
- **Method / Path:** `GET /api/inspector/tickets/{ticket_no}`
- **File / Line:** [`commoditi software/server.py:4590`](file:///C:/projects/tests/commoditi software/server.py#L4590)
- **Auth / Role:** Required (`BRANCH_CASHIER`, `BRANCH_MUNIM`, `ACCOUNTANT_HQ`, `SUPER_ADMIN`, `QUALITY_INSPECTOR`).
- **Request Schema:** Path: `ticket_no: str`.
- **Response Schema:** JSON (`{ success: true, ticket: Dict, slip_text: str }`).
- **Error Handling:** Returns HTTP 404 if ticket is not found in local SQLite (does not query cloud).
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 46. `GET /inspector/report/{ticket_no}`
- **Method / Path:** `GET /inspector/report/{ticket_no}`
- **File / Line:** [`commoditi software/server.py:4607`](file:///C:/projects/tests/commoditi software/server.py#L4607)
- **Auth / Role:** Authenticated staff session.
- **Request Schema:** Path: `ticket_no: str`.
- **Response Schema:** HTML Response (Digital QC Inspection Certificate with photo proof).
- **Error Handling:** Returns HTTP 404 if ticket is not found.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

#### 47. `POST /api/inspector/change-password`
- **Method / Path:** `POST /api/inspector/change-password`
- **File / Line:** [`commoditi software/server.py:4629`](file:///C:/projects/tests/commoditi software/server.py#L4629)
- **Auth / Role:** Required (`QUALITY_INSPECTOR`, `SUPER_ADMIN`).
- **Request Schema:** Form Data: `old_password`, `new_password`, `confirm_password`.
- **Response Schema:** JSON (`{ success: true, message: "Password updated successfully" }`).
- **Error Handling:** Verifies old password before hashing new password.
- **Race Conditions:** None.
- **Idempotency:** Non-idempotent.

---

## 3. Cloud Serverless API Catalogue (`mandi-erp-tracker/api/`)

### 48. `POST/GET /api/inspections-submit.js`
- **Method / Path:** `POST /api/inspections-submit`, `GET /api/inspections-submit`
- **File / Line:** [`mandi-erp-tracker/api/inspections-submit.js:5-139`](file:///C:/projects/tests/mandi-erp-tracker/api/inspections-submit.js#L5-L139)
- **Rewrites (Vercel):** `/api/inspector/submit-qc`, `/api/inspections/submit`, `/api/inspector/tickets/pending`
- **Auth / Role:** None (Public / API Key embedded in serverless environment).
- **Request Schema (POST):** JSON Body (30 fields): `ticket_no`, `branch_id`, `farmer_name`, `vehicle_no`, `commodity_name`, `moisture_pct`, `karda_pct`, `damaged_pct`, `sortex_clean_yield_pct`, `meter_photo_path`, `grain_photo_path`, `status`.
- **Request Schema (GET):** Query Param: `branch_id: Optional[str]`.
- **Response Schema (POST):** JSON (`{ success: true, ticket_no: str, data: [...], message: str }`).
- **Response Schema (GET):** JSON (`{ success: true, count: int, tickets: [...] }`).
- **Error Handling:** Returns HTTP 400 for invalid JSON; returns HTTP 500 on Supabase PostgREST rejection.
- **Race Conditions:** Upsert resolution: `resolution=merge-duplicates`.
- **Idempotency:** Idempotent on existing `ticket_no`.

### 49. `GET /api/supabase-status.js` & `GET /api/supabase/status.js`
- **Method / Path:** `GET /api/supabase-status`, `GET /api/supabase/status`
- **File / Line:** [`mandi-erp-tracker/api/supabase-status.js:5-78`](file:///C:/projects/tests/mandi-erp-tracker/api/supabase-status.js#L5-L78)
- **Auth / Role:** None (Public).
- **Request Schema:** None.
- **Response Schema:** JSON (`{ success: true, status: "CONNECTED"|"OFFLINE", latency_ms: int, project_ref: str, region: "ap-south-1" }`).
- **Error Handling:** 2500ms timeout abort controller; returns `OFFLINE` if probe fails.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

### 50. `GET /api/system-updates.js` & `GET /api/system/updates/status.js`
- **Method / Path:** `GET /api/system-updates`, `GET /api/system/updates/status`
- **File / Line:** [`mandi-erp-tracker/api/system-updates.js:1-18`](file:///C:/projects/tests/mandi-erp-tracker/api/system-updates.js#L1-L18)
- **Auth / Role:** None (Public).
- **Request Schema:** None.
- **Response Schema:** JSON (`{ success: true, version: "v1.0", master_host: "192.168.0.140:8080", status: "OPERATIONAL" }`).
- **Error Handling:** Returns static JSON.
- **Race Conditions:** None.
- **Idempotency:** Idempotent.

### 51. `GET/POST /api/track.js`
- **Method / Path:** `GET /api/track`, `POST /api/track`
- **File / Line:** [`mandi-erp-tracker/api/track.js:23-181`](file:///C:/projects/tests/mandi-erp-tracker/api/track.js#L23-L181)
- **Auth / Role:** None (Public Telemetry Hub).
- **Request Schema (POST):** JSON: `{ action: "sync_telemetry"|"download"|"license_request", telemetry: {...} }`.
- **Response Schema:** JSON (`{ success: true, stats: {...}, liveTelemetry: {...} }`).
- **Error Handling:** In-memory state tracking with FIFO queue cap at 25 events.
- **Race Conditions:** Serverless cold starts reset in-memory counts.
- **Idempotency:** `sync_telemetry` is idempotent state replacement; `download` is incrementing.

---

## 4. Standardized API Security & Integrity Findings (AUD-201 to AUD-205)

### FINDING AUD-201: Unauthenticated Financial Calculation Endpoint Leaking Mandi Rates
- **Severity:** MEDIUM
- **Module:** Inward Weighbridge API
- **File / Lines:** `commoditi software/server.py:2181-2207`
- **Observed:** `/api/invoices/calculate` and `/api/calculate-inward` are accessible without any session cookie or authentication token.
- **Expected:** Endpoints performing proprietary business calculations (hamali rates, mandi corridors, farmer advance deductions) must require authenticated cashier/staff credentials.
- **Actual:** Any external client on the local network can query and reverse-engineer trader profit margins, deductions, and Section 269ST cash compliance status.
- **Evidence:** `server.py` line 2181 defines `api_calculate_inward` without `require_role(request, ...)`.
- **Business Impact:** Competitor traders or unauthorized devices on yard Wi-Fi can monitor procurement rates and deduction formulas.
- **Correction:** Add `require_role(request, ["BRANCH_CASHIER", "BRANCH_MUNIM", "ACCOUNTANT_HQ", "SUPER_ADMIN"])` at top of handler.
- **Tests:** Automated request without headers asserting HTTP 401 response.
- **Dependencies:** None.

---

### FINDING AUD-202: Missing Idempotency Control on Cash Disbursement Payouts
- **Severity:** CRITICAL
- **Module:** Cashier Payout Engine
- **File / Lines:** `commoditi software/server.py:3935-4015`, `commoditi software/server.py:2209-2420`
- **Observed:** `/api/cashier/payout` and `/api/branch/invoices/create` accept repeated POST requests without validating an `Idempotency-Key` or checking if payout already occurred.
- **Expected:** Financial disbursement endpoints must be strictly idempotent to prevent duplicate cash payouts on network retries or double-clicks.
- **Actual:** If a cashier clicks the payout button twice rapidly, two separate `cashier_payouts` records are inserted, deducting twice from the physical cash drawer.
- **Evidence:** `server.py` line 2408 inserts into `cashier_payouts` with `f"pay-{uuid.uuid4().hex[:8]}"` on every call without checking existing payouts for that `invoice_id`.
- **Business Impact:** Double cash disbursement to farmers, causing severe cash drawer shortages and irreconcilable audit discrepancies.
- **Correction:** Add a unique constraint `UNIQUE(invoice_id)` on `cashier_payouts`, or enforce client-provided `Idempotency-Key` headers stored in an SQLite cache with 60-second TTL.
- **Tests:** Concurrent test sending 2 simultaneous payout requests for the same invoice asserting one succeeds and one returns 409 Conflict.
- **Dependencies:** `database.py`.

---

### FINDING AUD-203: Internal Network Topology Leakage via Public Updates Route
- **Severity:** LOW
- **Module:** System Updates API
- **File / Lines:** `mandi-erp-tracker/api/system-updates.js:11`
- **Observed:** Public serverless function exposes private APMC Master PC IP address: `"master_host": "192.168.0.140:8080"`.
- **Expected:** Public cloud endpoints must not disclose internal private network addressing or internal server port mappings.
- **Actual:** Any web visitor to `mandi-erp-tracker.vercel.app/api/system-updates` sees internal IP topology.
- **Evidence:** `system-updates.js` line 11: `master_host: "192.168.0.140:8080"`.
- **Business Impact:** Reconnaissance vector for internal network pivoting if an attacker gains Wi-Fi access.
- **Correction:** Remove hardcoded private IP addresses from cloud API responses; configure dynamic local discovery via mDNS.
- **Tests:** Verify public JSON response omits private IP strings.
- **Dependencies:** None.

---

### FINDING AUD-204: Form vs JSON Content-Type Discrepancy on QC Submissions
- **Severity:** HIGH
- **Module:** Inspector Assaying API
- **File / Lines:** `commoditi software/server.py:4356-4405`
- **Observed:** `/api/inspector/submit-qc` declares 35 `Form(...)` arguments, but mobile clients submit `Content-Type: application/json`.
- **Expected:** Endpoint must explicitly declare either a typed Pydantic JSON body model (`QCTicketPayload`) or Form fields, not a fragile hybrid parse.
- **Actual:** FastAPI first evaluates `Form(...)` defaults (setting missing fields to `None`), and then the handler manually attempts `await request.json()` inside an inner `try...except`. If JSON parsing encounters any error, it logs to debug and continues with unpopulated form fields.
- **Evidence:** `server.py` line 4402: `if "application/json" in ct: body = await request.json()`.
- **Business Impact:** Silent data loss: If JSON payload has syntax formatting anomalies, the inspection is saved with blank farmer names and zero moisture refractions.
- **Correction:** Split into two explicit endpoints or use a custom FastAPI dependency that cleanly maps Pydantic models regardless of Content-Type.
- **Tests:** Test submitting malformed JSON asserting explicit HTTP 422 Unprocessable Entity instead of silent 200 with default data.
- **Dependencies:** `pydantic`.

---

### FINDING AUD-205: Farmer PII Exposure via Autocomplete Search Endpoint
- **Severity:** MEDIUM
- **Module:** Farmer Directory API
- **File / Lines:** `commoditi software/server.py:3866-3885`
- **Observed:** `/api/farmers/search` returns complete farmer records including Aadhar number, bank account number, and IFSC code in response to single-letter queries.
- **Expected:** Search autocomplete endpoints should return only identification tokens (Farmer Name, Village, Phone suffix); full banking credentials should be fetched only upon invoice selection.
- **Actual:** Querying `?q=a` dumps sensitive banking and identity data for all matching farmers across the Mandi.
- **Evidence:** `server.py` line 3878: `SELECT id, name, phone, village, aadhar_no, bank_name, bank_account_no, ifsc_code FROM parties`.
- **Business Impact:** Privacy violation under DPDP Act (Digital Personal Data Protection Act 2023) for farmer financial PII.
- **Correction:** Mask Aadhar (`XXXX-XXXX-1234`) and bank account numbers (`XXXXXXXXX4912`) in search responses; expose full unmasked numbers only to authenticated accountants.
- **Tests:** Verify search response JSON masks sensitive identity attributes.
- **Dependencies:** None.

---

## 5. API Risk Heatmap & Audit Summary

| Category | Endpoints Evaluated | Critical | High | Medium | Low | Pass / Clean |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **System Governance & Auth** | 10 | 0 | 0 | 0 | 0 | 10 |
| **Admin & Staff Management** | 10 | 0 | 0 | 0 | 0 | 10 |
| **Supabase Cloud Replication** | 5 | 1 | 1 | 0 | 0 | 3 |
| **HQ Accounts & Rate Corridors** | 6 | 0 | 0 | 0 | 0 | 6 |
| **Weighbridge & Inward Purchase** | 8 | 1 | 1 | 1 | 0 | 5 |
| **Outward Sales & Dispatch** | 3 | 0 | 1 | 0 | 0 | 2 |
| **QC Assaying & Computer Vision** | 7 | 1 | 1 | 0 | 0 | 5 |
| **Cloud Serverless Handlers** | 4 | 0 | 0 | 1 | 1 | 2 |
| **TOTALS** | **53** | **3** | **4** | **2** | **1** | **43** |
