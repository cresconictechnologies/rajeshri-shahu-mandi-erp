# Comprehensive Database Schema & Integrity Audit
**System:** Rajarshi Shahu Mandi ERP (APMC Procurement & Multi-Branch Trading System)  
**Author:** Database Optimizer & Multi-Tenant Specialist  
**Audit Target:** Dual Database Architecture — Local SQLite (`commodity_mandi.db`) & Supabase Cloud PostgreSQL 17 (`dbhcpebchoyjyffqjgih`)  
**Audit Date:** November 3, 2026  
**Status:** COMPLETE — HIGH RISK (Multiple P0 & P1 Critical Deficiencies Identified)

---

## 1. Executive Summary & Architecture Overview

The Rajarshi Shahu Mandi ERP operates an **offline-first dual-database architecture**:
1. **Edge Node Engine:** Embedded SQLite 3 database (`commoditi software/commodity_mandi.db`) running in Write-Ahead Logging (`WAL`) mode with `PRAGMA foreign_keys = ON;`, serving local APMC yard weighing scales, cashier desks, and grain inspection terminals.
2. **Cloud Central Engine:** Hosted PostgreSQL 17.11 on Supabase (AWS `ap-south-1`, Mumbai region, project ref: `dbhcpebchoyjyffqjgih`), intended as the authoritative data warehouse for Central Accounts (HQ), multi-branch aggregation, and remote reporting.
3. **Replication Daemon:** Custom Python sync module (`commoditi software/supabase_sync.py`) providing bidirectional push/pull with Last-Write-Wins (LWW) resolution and an offline SQLite event queue (`sync_queue`).

### Key Audit Metrics
| Metric | SQLite (Edge) | Supabase PostgreSQL 17 (Cloud) | Status |
| :--- | :--- | :--- | :--- |
| **Total Public Tables** | 16 tables | 14 tables | Divergent (`sync_queue`, `user_sessions` missing in PG) |
| **Row Level Security (RLS)** | N/A (Embedded) | **0 of 14 Tables Enabled (100% UNPROTECTED)** | **CRITICAL P0 SECURITY FLAW** |
| **Public Grants (`anon`)** | N/A | **FULL READ / WRITE / DELETE / TRUNCATE on all 14 tables** | **CRITICAL P0 EXPLOIT RISK** |
| **Foreign Key Integrity** | **27 Active Violations** (2 Invoices, 2 Payouts, 23 Inspections) | Enforced on write (Divergent schema) | **CRITICAL DATA CORRUPTION** |
| **Currency Precision** | IEEE 754 `REAL` (Float64) | Mixed `double precision` / `numeric` | **FINANCIAL AUDIT RISK** |
| **Duplicate / Divergent Records** | 4 Parties | 25 Parties (24 Duplicate Rows across 3 phone numbers) | **SEVERE DATA DIVERGENCE** |
| **Non-PK Indexes in Cloud** | 14 Indexes | **0 Indexes on Foreign Keys or Filter Columns** | **PERFORMANCE BOTTLENECK** |
| **Multi-Tenancy Isolation** | None (`organization_id` absent) | None (`organization_id` absent) | Single-Tenant Hardcoded |

---

## 2. Table-by-Table Deep Audit (All 16 Tables)

Below is the detailed comparative audit of all database entities across SQLite (`database.py`) and Supabase PostgreSQL (`supabase_schema.sql` / live database introspection).

---

### Table 1: `branches`
- **Purpose:** Master registry of APMC procurement yards (Chikhali, Varvand, Dhad).
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `branch_code TEXT UNIQUE NOT NULL`, `name TEXT NOT NULL`, `mandi_license_no TEXT`, `address TEXT`, `phone TEXT`, `is_active INTEGER DEFAULT 1`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`, `updated_at TEXT`.
- **PostgreSQL Definition:** `id text PRIMARY KEY`, `branch_code text UNIQUE NOT NULL`, `name text NOT NULL`, `mandi_license_no text`, `address text`, `phone text`, `is_active integer DEFAULT 1`, `created_at timestamptz DEFAULT CURRENT_TIMESTAMP`, `updated_at timestamptz DEFAULT clock_timestamp()`.
- **Row Count:** SQLite: 3 | Supabase PG: 3.
- **Audit Findings:**
  1. `is_active` is modeled as `INTEGER` in SQLite and `integer/int4` in PG, despite `supabase_schema.sql` specifying `BOOLEAN NOT NULL DEFAULT TRUE`.
  2. Missing geographical hierarchy: Lacks `district_id`, `state`, `pincode`, `market_committee_name`, and APMC jurisdiction codes required under the Maharashtra Agricultural Produce Marketing (Development and Regulation) Act.
  3. Lacks `organization_id` / `tenant_id` for multi-firm or multi-licensee operations.

---

### Table 2: `users`
- **Purpose:** User authentication, role assignments, and branch associations.
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `branch_id TEXT REFERENCES branches(id)`, `username TEXT UNIQUE NOT NULL`, `password_hash TEXT NOT NULL`, `full_name TEXT NOT NULL`, `phone TEXT NOT NULL`, `role TEXT NOT NULL CHECK (role IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ', 'BRANCH_MUNIM', 'BRANCH_CASHIER', 'QUALITY_INSPECTOR'))`, `is_active INTEGER DEFAULT 1`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`.
- **PostgreSQL Definition:** Identical columns plus `updated_at timestamptz DEFAULT clock_timestamp()`.
- **Row Count:** SQLite: 12 | Supabase PG: 15.
- **Audit Findings:**
  1. **Username Divergence:** User `u-indore-cashier` is named `chikhali` in SQLite but `chikhali_cashier` in PostgreSQL. User `u-indore-munim` is named `indore_munim` in SQLite but `chikhali_munim` in PostgreSQL. User `u-ujjain-munim` is named `ujjain_munim` in SQLite but `varvand_munim` in PostgreSQL.
  2. **Phantom Cloud Users:** 3 inspector users exist in PostgreSQL (`u-qc-d7934b`, `u-qc-6b29e9`, `u-b78466d9`) that do NOT exist in local SQLite.
  3. **Catastrophic Credential Exposure:** Table is completely exposed over Supabase REST API. Role `anon` can execute `SELECT username, password_hash FROM users` and obtain all 600,000-round PBKDF2 password hashes.
  4. Lacks `failed_login_attempts`, `locked_until`, `last_login_at`, and `password_changed_at`.

---

### Table 3: `commodities`
- **Purpose:** Master agricultural commodities traded in yards (Soybean, Cotton, Wheat, Chana, etc.).
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `name TEXT UNIQUE NOT NULL`, `hsn_code TEXT NOT NULL`, `standard_moisture_pct REAL DEFAULT 10.0`, `mandi_cess_pct REAL DEFAULT 0.0`, `is_active INTEGER DEFAULT 1`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`, `updated_at TEXT`.
- **PostgreSQL Definition:** Identical plus `updated_at timestamptz DEFAULT clock_timestamp()`.
- **Row Count:** SQLite: 15 | Supabase PG: 15.
- **Audit Findings:**
  1. `mandi_cess_pct` is hardcoded to `0.0` in SQLite and checked via `CHECK (mandi_cess_pct = 0.00)` in PG. While farmer procurement in Maharashtra carries 0% cess, buyer outward dispatches and inter-state trade carry statutory market fees (0.5%–1.05%). Hardcoding a zero check at table level prevents lawful cess collection on trade buyers.
  2. `standard_moisture_pct` uses `REAL` (Float64) in SQLite and `numeric/numeric` in PG.
  3. No commodity grading parameters or Sortex specifications are stored relationally in this table; Sortex thresholds are hardcoded in application logic.

---

### Table 4: `parties`
- **Purpose:** Farmer sellers, stockers, and trade buyers.
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `home_branch_id TEXT REFERENCES branches(id)`, `name TEXT NOT NULL`, `phone TEXT NOT NULL`, `party_type TEXT NOT NULL CHECK (party_type IN ('FARMER', 'STOCKER', 'BUYER'))`, `village TEXT`, `pan_number TEXT`, `aadhaar_number TEXT`, `gstin TEXT`, `khasra_record_no TEXT`, `bank_name TEXT`, `bank_account_no TEXT`, `bank_ifsc TEXT`, `current_advance REAL DEFAULT 0.0`, `advance_interest_rate REAL DEFAULT 12.0`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`, `updated_at TEXT`.
- **PostgreSQL Definition:** Identical columns with `double precision` for `current_advance` and `advance_interest_rate`.
- **Row Count:** SQLite: 4 | Supabase PG: 25.
- **Audit Findings:**
  1. **Massive Cloud Record Duplication:** There is NO unique constraint on `phone` or `(home_branch_id, phone)` or `pan_number` or `aadhaar_number`. In Supabase PG, there are 8 duplicate records for Sitaram Yadav (`9826012345`), 8 duplicate records for Devendra Patidar (`9826099999`), and 8 duplicate records for Narmada Solvent Extractions Ltd (`9826019922`).
  2. **Data Divergence on Primary Key:** `p-farmer-1` has phone `9827011111` in SQLite, but `9826099887` in PostgreSQL.
  3. **Unencrypted Statutory PII Exposure:** Bank account numbers, IFSC codes, Aadhaar numbers, and PAN cards are stored in plaintext and readable by unauthenticated `anon` users over public REST.
  4. Advance balances (`current_advance`) stored as floating point instead of fixed-point numeric.

---

### Table 5: `daily_commodity_rates`
- **Purpose:** Mandi price corridor (Minimum, Target, Maximum rate per quintal) set per yard and quality grade.
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `rate_date TEXT NOT NULL`, `branch_id TEXT REFERENCES branches(id)`, `commodity_name TEXT NOT NULL`, `quality_grade TEXT DEFAULT 'STANDARD'`, `min_rate_per_qtl REAL NOT NULL`, `target_rate_per_qtl REAL NOT NULL`, `max_rate_per_qtl REAL NOT NULL`, `set_by_user_id TEXT REFERENCES users(id)`, `updated_at TEXT DEFAULT CURRENT_TIMESTAMP`, `UNIQUE(rate_date, branch_id, commodity_name, quality_grade)`.
- **PostgreSQL Definition:** Identical columns with `double precision` rates and matching unique constraint `uq_daily_rates`.
- **Row Count:** SQLite: 39 | Supabase PG: 39.
- **Audit Findings:**
  1. Rates stored as `REAL` / `double precision`. Financial prices per quintal must be stored as `NUMERIC(10, 2)`.
  2. Missing index on `(branch_id, rate_date)` in PostgreSQL. Only the composite unique constraint index exists.
  3. SQLite allows `set_by_user_id` to be NULL without tracking who established the statutory price corridor when modified offline.

---

### Table 6: `inspectors`
- **Purpose:** Quality inspectors and assayers certified for grain analysis and weighbridge sample evaluation.
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `branch_id TEXT REFERENCES branches(id)`, `name TEXT NOT NULL`, `designation TEXT DEFAULT 'Assayer / Sampler'`, `phone TEXT`, `is_active INTEGER DEFAULT 1`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`, `updated_at TEXT`.
- **PostgreSQL Definition:** Identical columns plus `updated_at timestamptz`.
- **Row Count:** SQLite: 10 | Supabase PG: 31.
- **Audit Findings:**
  1. **Schema Duplication / Entity Collision:** The application maintains both `users` with role `QUALITY_INSPECTOR` AND an independent `inspectors` table. In `database.py`, user IDs (e.g. `u-qc-chikhali`) are dual-inserted into both `users` and `inspectors`.
  2. **Orphan Records:** 21 inspector records in PostgreSQL do not exist in local SQLite.
  3. `quality_inspections` in SQLite references `inspectors(id)`, whereas in PostgreSQL `quality_inspections` references `users(id)`. This foreign key mismatch breaks cross-database consistency.

---

### Table 7: `quality_inspections`
- **Purpose:** Physical and computer-vision grain assaying records (moisture, karda, foreign matter, sortex yield, breed classification).
- **SQLite Definition:** 40 columns including `id TEXT PRIMARY KEY`, `ticket_no TEXT UNIQUE NOT NULL`, `branch_id TEXT NOT NULL REFERENCES branches(id)`, `inspector_id TEXT REFERENCES inspectors(id)`, `invoice_id TEXT REFERENCES purchase_invoices(id)`, etc.
- **PostgreSQL Definition:** **52 columns**! Contains 12 legacy columns not present in SQLite: `token_number`, `sample_code`, `cleanliness_score`, `foreign_matter_pct`, `weevilled_pct`, `immature_pct`, `suggested_rate`, `calculated_rate`, `approved_rate`, `rate_reason`, `image_path`, `lot_photo_path`.
- **Row Count:** SQLite: 49 | Supabase PG: 49.
- **Audit Findings:**
  1. **Severe Foreign Key Violations in SQLite:** 22 records reference deleted `invoice_id` values (e.g., `inv-52418c7b57`, `inv-5e3ccc1b02`), and 1 record (`qc-d8014822`) references inspector `u-b78466d9` which does not exist in SQLite's `inspectors` table!
  2. **Severe Schema Drift:** 12 columns exist in PostgreSQL that do not exist in SQLite. `supabase_sync.py` must filter out these columns on pull, creating hidden technical debt.
  3. **Zero Indexes on Search/Filter Columns in PG:** In PostgreSQL, there are no indexes on `branch_id`, `vehicle_no`, `status`, or `commodity_id`. SQLite has 3 explicit indexes (`idx_qc_branch`, `idx_qc_vehicle`, `idx_qc_status`).
  4. Floating-point `REAL` used for moisture percentage, karda percentage, damaged percentage, and suggested rates.

---

### Table 8: `purchase_invoices`
- **Purpose:** Primary procurement contract and weighment voucher for farmer grain purchases.
- **SQLite Definition:** 46 columns covering weighment mode, tare, gross weight, net weight, cuts, hamali, cess, advances, TDS 194Q, and net payable.
- **PostgreSQL Definition:** 46 columns matching SQLite, with monetary amounts mapped to `double precision` / `float8`.
- **Row Count:** SQLite: 9 | Supabase PG: 9.
- **Audit Findings:**
  1. **Active Foreign Key Violations in SQLite:** Two invoices (`inv-d345a2c902` with token `CHK-20261103-0008` and `inv-6509512ebd` with token `CHK-20261103-0002`) reference non-existent party IDs `p-B516` and `p-cbcbd71e`!
  2. **Floating-Point Financial Data:** Net payable, gross amount, deductions, and weighbridge weights are stored as `REAL` (SQLite) and `double precision` (PG). Round-off discrepancies directly affect cashier payouts and ledger balance sheets.
  3. **Missing Foreign Key Indexes in PG:** PostgreSQL lacks indexes on `branch_id`, `party_id`, `invoice_date`, and `qc_ticket_no`.
  4. **Unauthenticated Public Receipt Slip:** `/api/branch/invoices/parchi/{token_number}` serves full financial procurement vouchers to any requester without authentication.

---

### Table 9: `cashier_payouts`
- **Purpose:** Cash disbursements, denomination breakdowns, and RTGS settlement records.
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `branch_id TEXT NOT NULL REFERENCES branches(id)`, `invoice_id TEXT NOT NULL REFERENCES purchase_invoices(id)`, `party_id TEXT NOT NULL REFERENCES parties(id)`, `payout_mode TEXT CHECK (payout_mode IN ('CASH', 'BANK_TRANSFER', 'UPI', 'CHEQUE'))`, `amount_paid REAL NOT NULL`, notes breakdowns (`notes_500`, `notes_200`, etc.), `bank_utr_no TEXT`, `cashier_user_id TEXT NOT NULL REFERENCES users(id)`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`, `updated_at TEXT`.
- **PostgreSQL Definition:** Identical columns with `double precision` for `amount_paid`.
- **Row Count:** SQLite: 5 | Supabase PG: 5.
- **Audit Findings:**
  1. **Active Foreign Key Violations in SQLite:** Payout `pay-c19266b5` (₹1,37,923.00) references orphan party `p-B516`. Payout `pay-87f4255e` (₹1,83,844.00) references orphan party `p-cbcbd71e`.
  2. **Statutory 269ST Trigger Inconsistency:** PostgreSQL has trigger `trg_enforce_section_269st_cash_limit` which raises an exception if aggregate daily cash to a party reaches ₹2,00,000. SQLite has NO database-level trigger; enforcement is purely application-level in `server.py` and is evaluated only against local branch payouts.
  3. No index on `(party_id, created_at)` in PostgreSQL, forcing sequential table scans on every cash payout to calculate the daily 269ST aggregate.

---

### Table 10: `branch_daily_cash_drawers`
- **Purpose:** Cash drawer opening float, disbursements, petty expenses, and closing physical counts.
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `branch_id TEXT NOT NULL REFERENCES branches(id)`, `record_date TEXT NOT NULL`, `opening_float REAL NOT NULL`, `total_cash_payouts REAL DEFAULT 0.0`, `petty_expenses_cash REAL DEFAULT 0.0`, `bank_withdrawals_inward REAL DEFAULT 0.0`, `calculated_closing_cash REAL NOT NULL`, `physical_counted_cash REAL NOT NULL`, `closed_by_user_id TEXT REFERENCES users(id)`, `closed_at TEXT`, `UNIQUE(branch_id, record_date)`.
- **PostgreSQL Definition:** Identical columns with `double precision` and matching unique constraint.
- **Row Count:** SQLite: 3 | Supabase PG: 4.
- **Audit Findings:**
  1. **Single-Shift Architectural Bottleneck:** The constraint `UNIQUE(branch_id, record_date)` strictly prohibits more than one cash drawer session per branch per day. In real Mandi peak season, yards operate multiple cash counters (Counter 1 & 2) or morning and evening shifts.
  2. Floating point `REAL` used for physical counted cash and calculated closing cash.
  3. 1 orphan drawer session exists in PG that is not in SQLite.

---

### Table 11: `outward_orders`
- **Purpose:** Sales dispatches of procured commodities to processing mills and institutional buyers.
- **SQLite Definition:** 25 columns including `challan_number TEXT UNIQUE NOT NULL`, `buyer_name TEXT NOT NULL`, `net_quintals REAL NOT NULL`, `rate_per_quintal REAL NOT NULL`, `hamali_amount REAL NOT NULL`, `gross_amount REAL NOT NULL`, `total_bill_amount REAL NOT NULL`, payment tracking fields, and branch references.
- **PostgreSQL Definition:** Identical columns with `double precision` for monetary amounts.
- **Row Count:** SQLite: 1 | Supabase PG: 3.
- **Audit Findings:**
  1. Missing foreign key reference to `parties(id)`: Uses loose `buyer_name TEXT` instead of mandatory `buyer_party_id REFERENCES parties(id)`.
  2. 2 outward orders exist in PostgreSQL that do not exist in SQLite.
  3. No index on `(branch_id, order_date)` in PostgreSQL.

---

### Table 12: `ledger_entries`
- **Purpose:** Double-entry accounting vouchers (Debit/Credit) for farmer accounts, cash drawers, and sales.
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `branch_id TEXT NOT NULL REFERENCES branches(id)`, `transaction_date TEXT NOT NULL`, `voucher_type TEXT NOT NULL`, `voucher_id TEXT NOT NULL`, `account_name TEXT NOT NULL`, `party_id TEXT REFERENCES parties(id)`, `debit_amount REAL DEFAULT 0.0`, `credit_amount REAL DEFAULT 0.0`, `narration TEXT`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`, `updated_at TEXT`.
- **PostgreSQL Definition:** Identical columns with `double precision` for debit and credit amounts.
- **Row Count:** SQLite: 9 | Supabase PG: 149.
- **Audit Findings:**
  1. **Massive Cloud Desynchronization:** 140 historical ledger entries in PostgreSQL were wiped from local SQLite during `reset_production_data.py`. If `supabase_sync.py` executes `pull_supabase_to_local()`, all 140 old entries will be re-injected into local SQLite.
  2. **Absence of Trial Balance Enforcements:** No composite transaction identifier or database trigger exists to verify that `SUM(debit_amount) == SUM(credit_amount)` per voucher.
  3. Floating-point debit/credit amounts violate basic GAAP accounting standards.

---

### Table 13: `system_settings`
- **Purpose:** Master configuration key-values (statutory APMC hamali rates, round-off policies, Supabase sync credentials).
- **SQLite Definition:** `scope TEXT NOT NULL`, `scope_id TEXT NOT NULL DEFAULT 'GLOBAL'`, `setting_key TEXT NOT NULL`, `setting_value TEXT NOT NULL`, `updated_at TEXT DEFAULT CURRENT_TIMESTAMP`, `PRIMARY KEY (scope, scope_id, setting_key)`.
- **PostgreSQL Definition:** Identical composite primary key and columns.
- **Row Count:** SQLite: 31 | Supabase PG: 31.
- **Audit Findings:**
  1. Plaintext storage of sensitive infrastructure secrets (`supabase_key`, `supabase_service_role_key`, `database_url`) in `system_settings` with `scope='SUPER_ADMIN'`.
  2. Table is publicly exposed via `anon` Supabase REST endpoint without RLS.

---

### Table 14: `audit_change_logs`
- **Purpose:** Entity change audit trail (farmer edits, rate overrides, invoice cancellations).
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `entity_type TEXT NOT NULL`, `entity_id TEXT NOT NULL`, `entity_name TEXT`, `branch_id TEXT`, `changed_by TEXT DEFAULT 'cashier'`, `action TEXT NOT NULL`, `old_values_json TEXT`, `new_values_json TEXT`, `change_summary TEXT`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`.
- **PostgreSQL Definition:** Identical columns plus `updated_at timestamptz`.
- **Row Count:** SQLite: 0 | Supabase PG: 105.
- **Audit Findings:**
  1. Completely empty in SQLite (0 rows), but contains 105 historical records in PostgreSQL.
  2. Not tamper-proof: Rows can be deleted or updated by any user because PostgreSQL lacks immutability rules and RLS is disabled.
  3. Missing indexes in PostgreSQL on `(entity_type, entity_id)` and `created_at`.

---

### Table 15: `user_sessions` (SQLite Only)
- **Purpose:** Server-side user authentication session tracking.
- **SQLite Definition:** `session_id TEXT PRIMARY KEY`, `user_id TEXT NOT NULL REFERENCES users(id)`, `username TEXT NOT NULL`, `role TEXT NOT NULL`, `branch_id TEXT`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`, `expires_at TEXT NOT NULL`, `is_revoked INTEGER DEFAULT 0`.
- **PostgreSQL Definition:** **TABLE DOES NOT EXIST IN POSTGRESQL.**
- **Row Count:** SQLite: 12 | Supabase PG: Missing.
- **Audit Findings:**
  1. Architectural omission in cloud schema: Sessions are purely local to SQLite. A user authenticated at Yard A has no session representation in Supabase.
  2. Sessions cannot be revoked globally from Central Accounts across physical branches without manual database updates.

---

### Table 16: `sync_queue` (SQLite Only)
- **Purpose:** Offline change data capture (CDC) queue for outbound synchronization to Supabase.
- **SQLite Definition:** `id TEXT PRIMARY KEY`, `entity_type TEXT NOT NULL`, `entity_id TEXT NOT NULL`, `action TEXT NOT NULL DEFAULT 'UPSERT'`, `payload_json TEXT NOT NULL`, `status TEXT NOT NULL DEFAULT 'PENDING'`, `error_message TEXT`, `retry_count INTEGER NOT NULL DEFAULT 0`, `created_at TEXT DEFAULT CURRENT_TIMESTAMP`, `synced_at TEXT`.
- **PostgreSQL Definition:** **TABLE DOES NOT EXIST IN POSTGRESQL.**
- **Row Count:** SQLite: 4 | Supabase PG: Missing.
- **Audit Findings:**
  1. **Critical Sync Daemon Flaw:** In `supabase_sync.py` (lines 925–933), the sync daemon marks `sync_queue` items as `COMPLETED` **without ever extracting or transmitting `payload_json` to Supabase**! The daemon then falls back to a blind `SELECT * FROM {table}` table scan.
  2. Unidirectional design: Does not record remote cloud changes for downstream edge distribution.

---

## 3. Financial Precision & Floating-Point Risk Analysis

In `database.py`, monetary amounts, weight measurements, and statutory percentages are defined as SQLite `REAL` (IEEE 754 64-bit floating point). In PostgreSQL, these have been replicated as `double precision` (`float8`).

### Exact Vulnerable Columns
| Table | Column | Stored Type | Required Type | Risk Description |
| :--- | :--- | :--- | :--- | :--- |
| `purchase_invoices` | `net_payable_amount` | `REAL` / `float8` | `NUMERIC(14, 2)` | Penny discrepancies in RTGS disbursements and cash rounding. |
| `purchase_invoices` | `gross_amount` | `REAL` / `float8` | `NUMERIC(14, 2)` | Cumulative rounding error across daily APMC turnover. |
| `purchase_invoices` | `tds_194q_amount` | `REAL` / `float8` | `NUMERIC(12, 2)` | Inaccurate Income Tax statutory filing under Section 194Q. |
| `purchase_invoices` | `net_quintals` | `REAL` / `float8` | `NUMERIC(12, 4)` | Inaccurate grain weight calculation; 0.0001 quintal = 10 grams. |
| `cashier_payouts` | `amount_paid` | `REAL` / `float8` | `NUMERIC(14, 2)` | Float drift breaks denomination reconciliation (`validate_cash_denominations`). |
| `parties` | `current_advance` | `REAL` / `float8` | `NUMERIC(14, 2)` | Compound interest calculation drift on farmer advance accounts. |
| `daily_commodity_rates`| `min_rate_per_qtl` | `REAL` / `float8` | `NUMERIC(10, 2)` | Floor price threshold rounding bugs in QC buy suggestions. |

**Evidence of Float Inaccuracy:**
In Python / IEEE 754:
```python
>>> 134369.90 + 0.05
134369.95000000002
>>> round(183843.755, 2)
183843.75  # Banker's rounding drops half paisa unpredictably
```
For a business processing ₹50,00,000+ daily in grain procurement, binary floating-point representation causes reconciliation discrepancies between cash drawer physical balances, bank RTGS statements, and internal double-entry ledgers.

---

## 4. Critical Data Discrepancies & Orphan Records

### 4.1. Active Foreign Key Violations in SQLite
Running `PRAGMA foreign_key_check` on `commodity_mandi.db` reveals **27 active integrity violations**:
1. `purchase_invoices` (Row 3, Token `CHK-20261103-0008`): References `party_id = 'p-B516'` which DOES NOT EXIST in `parties`.
2. `purchase_invoices` (Row 9, Token `CHK-20261103-0002`): References `party_id = 'p-cbcbd71e'` which DOES NOT EXIST in `parties`.
3. `cashier_payouts` (Row 2, ID `pay-c19266b5`, ₹1,37,923): References orphan party `p-B516`.
4. `cashier_payouts` (Row 5, ID `pay-87f4255e`, ₹1,83,844): References orphan party `p-cbcbd71e`.
5. `quality_inspections`: 22 rows reference deleted `purchase_invoices(id)` values, and 1 row (`qc-d8014822`) references inspector `u-b78466d9` which does not exist in `inspectors`.

**Root Cause:**
`commoditi software/reset_production_data.py` disabled foreign keys (`PRAGMA foreign_keys = OFF`), executed `DELETE FROM parties`, and repopulated only 4 parties while leaving existing invoices, payouts, and QC tickets untouched!

### 4.2. Phantom Duplication & Cloud Desync
1. **Party Duplication:** While SQLite has only 4 parties, Supabase PostgreSQL has 25 parties. Devendra Patidar (`9826099999`) is duplicated 8 times with different random IDs (`p-ee482a0b`, `p-cbcbd71e`, `p-f4fa661a`, `p-90292e54`, `p-acd70ce9`, `p-6ffdadd2`, `p-e0036670`, `p-871d39ef`). Sitaram Yadav (`9826012345`) is duplicated 8 times.
2. **Primary Key Attribute Mismatch:** In SQLite, party `p-farmer-1` has phone `9827011111`. In Supabase PostgreSQL, `p-farmer-1` has phone `9826099887`.
3. **Re-Injection Risk:** If `pull_supabase_to_local()` runs, it will immediately re-populate the 21 wiped parties and 140 wiped ledger entries into local SQLite because the LWW conflict resolution checks `loc_row is None` and treats missing local records as insertions!

---

## 5. Missing Commercial Mandi ERP Tables

To meet statutory APMC compliance, multi-user physical yard operations, and commercial ERP standards, the following core tables are currently missing:

1. **`organizations` / `tenants`:** Multi-tenant hierarchy holding Mandi license holder legal identity, corporate PAN, CIN, and registered head office.
2. **`districts` & `apmc_jurisdictions`:** State and district regulatory rules (e.g. Buldhana District APMC vs Pune District APMC), defining statutory market fee schedules.
3. **`bank_accounts`:** Mandi firm bank accounts used for RTGS disbursements, cheque issuance, and inward cash withdrawals. (Currently, RTGS bank details are loose text fields on invoices).
4. **`cash_drawer_sessions` / `cashier_shifts`:** To support multiple cash counters and shift handovers during peak harvest season.
5. **`inventory_stocks` / `commodity_batches` / `warehouse_lots`:** Real-time stock ledger tracking physical bags and quintals in yard godowns, preventing negative stock dispatches.
6. **`weighbridge_scale_tickets`:** Raw gross and tare weight indicator capture logs with weighbridge serial number, scale calibration certificate number, and operator timestamp.

---

## 6. `supabase_sync.py` Architectural & Operational Defects

1. **Fake Queue Processing:** Lines 925–933 fetch `sync_queue` records and immediately execute `UPDATE sync_queue SET status='COMPLETED'`, incrementing `total_pushed` without ever dispatching the queued payload to PostgreSQL.
2. **Blind Table Scans:** Step 2 executes `SELECT * FROM {table}` for all tables on every sync run. As invoices grow to 100,000+ records, this will exhaust memory and cause timeout failures.
3. **Foreign Key Nullification Crash:** Lines 983–989 set `cleaned["branch_id"] = None` and `cleaned["party_id"] = None` if foreign keys are not locally resolved. In PostgreSQL, `purchase_invoices.branch_id` and `party_id` are `NOT NULL`, causing runtime `NotNullViolation` database errors.
4. **Timestamp String Comparison Bug:** Line 1143 performs raw lexicographical string comparison between SQLite UTC strings (`2026-11-03 12:00:00`) and PostgreSQL ISO timestamps with timezone offsets (`2026-11-03 12:00:00.123456+00:00`), leading to invalid Last-Write-Wins decisions.

---

## 7. Structured Findings Ledger (Database Integrity)

### Finding AUD-001
- **Severity:** P0
- **Module:** Cloud Database Infrastructure / Security
- **File and line:** Supabase PostgreSQL Database Configuration
- **Observed implementation:** `pg_tables.rowsecurity` is `False` on all 14 public tables. `pg_policies` contains 0 policies.
- **Expected behavior:** RLS must be enabled on every table (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`) with strict policies restricting read/write access by authenticated role and tenant/branch.
- **Actual problem:** All 14 tables in Supabase are completely open. The public `anon` role has full `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE` grants.
- **Evidence:** Verified live: Unauthenticated GET request to `https://dbhcpebchoyjyffqjgih.supabase.co/rest/v1/users?select=password_hash` using `SUPABASE_ANON_KEY` returned HTTP 200 with raw PBKDF2 password hashes.
- **Business impact:** Total data breach. Any third party or rogue competitor can dump farmer PII, alter commodity corridor prices, delete purchase invoices, or truncate cash drawers.
- **Recommended correction:** Execute immediate emergency SQL: Revoke all public grants from `anon` and `authenticated`. Enable RLS on all 14 tables. Define restrictive policies.
- **Required tests:** Automated security scan verifying HTTP 401/403 for `anon` queries on `/rest/v1/users` and `/rest/v1/purchase_invoices`.
- **Dependencies:** None. Immediate priority.

---

### Finding AUD-002
- **Severity:** P0
- **Module:** SQLite Edge Database Integrity
- **File and line:** `commoditi software/commodity_mandi.db` / `reset_production_data.py:45`
- **Observed implementation:** Foreign keys disabled during deletion scripts; records deleted in parent tables without cascading or cleaning child tables.
- **Expected behavior:** Database must enforce foreign key integrity at all times. No invoice or payout may reference a nonexistent party.
- **Actual problem:** 27 foreign key violations exist in SQLite (`purchase_invoices` rows 3 & 9, `cashier_payouts` rows 2 & 5, and 23 in `quality_inspections`).
- **Evidence:** `PRAGMA foreign_key_check` output:
  `purchase_invoices: ('inv-d345a2c902', 'CHK-20261103-0008', 'p-B516')`
  `cashier_payouts: ('pay-c19266b5', 'inv-d345a2c902', 'p-B516')`
- **Business impact:** Cashier settlement crashes on invoice lookup, audit reports show payouts made to ghost farmers, accounting ledgers cannot resolve party accounts.
- **Recommended correction:** Run a cleanup script restoring missing referenced party stubs or re-assigning valid party IDs before re-enabling strict foreign key checks.
- **Required tests:** `PRAGMA foreign_key_check;` must return 0 rows in CI/CD pipeline.
- **Dependencies:** `parties`, `purchase_invoices`, `cashier_payouts`.

---

### Finding AUD-003
- **Severity:** P1
- **Module:** Financial Precision / Data Types
- **File and line:** `commoditi software/database.py:385-413` & `supabase_schema.sql:461-486`
- **Observed implementation:** In SQLite, currency and weights use `REAL`. In Supabase PostgreSQL, currency and weights use `double precision` (`float8`).
- **Expected behavior:** Financial ERP software must use fixed-point decimal arithmetic: `NUMERIC(14, 2)` for currency and `NUMERIC(12, 4)` for quintal weights.
- **Actual problem:** IEEE 754 binary floating-point rounding errors accumulate across multi-ton weighments and multi-lakh farmer payouts.
- **Evidence:** PostgreSQL column types in `purchase_invoices`: `gross_amount float8`, `net_payable_amount float8`, `hamali_charge float8`.
- **Business impact:** Cash-drawer end-of-day balances fail to reconcile with physical cash; Income Tax Section 194Q TDS calculations drift by fractional paisa; legal disputes with audit authorities.
- **Recommended correction:** Migrate SQLite table definitions to store amounts as scaled integers (paisa) or text-represented decimals, and migrate PostgreSQL columns to `NUMERIC(14, 2)`.
- **Required tests:** Unit tests asserting exact decimal arithmetic on 10,000 randomized weight/rate calculation cycles with zero float drift.
- **Dependencies:** `calculations.py`, `database.py`, `supabase_sync.py`.

---

### Finding AUD-004
- **Severity:** P1
- **Module:** Cloud Synchronization Daemon
- **File and line:** `commoditi software/supabase_sync.py:925-933`
- **Observed implementation:** `push_local_to_supabase()` updates `sync_queue` rows to `COMPLETED` without sending their payload to Supabase.
- **Expected behavior:** Queued events in `sync_queue` must be read, validated, and replicated to the remote PostgreSQL database before marking status `COMPLETED`.
- **Actual problem:** The offline event queue is an inert dummy implementation. Synchronization relies entirely on blind full-table scans.
- **Evidence:** Code in `supabase_sync.py`:
  ```python
  for q in queue_rows:
      local_cur.execute("UPDATE sync_queue SET status='COMPLETED', synced_at=CURRENT_TIMESTAMP WHERE id=?", (q["id"],))
      total_pushed += 1
  ```
- **Business impact:** Misleading sync dashboard status; events that fail in the table scan are marked completed in the queue, creating false confidence in disaster recovery readiness.
- **Recommended correction:** Rewrite `push_local_to_supabase` to iterate through pending queue items, execute targeted upserts using `payload_json`, and only mark `COMPLETED` upon confirmed remote commit.
- **Required tests:** Offline simulation test: create 10 invoices while offline, bring sync online, verify exactly 10 invoices pushed via queue events without full table scan.
- **Dependencies:** `sync_queue`, `supabase_sync.py`.

---

### Finding AUD-005
- **Severity:** P1
- **Module:** Master Data Integrity / Party Registry
- **File and line:** `commoditi software/database.py:347-364`
- **Observed implementation:** `parties` table lacks unique constraints on natural business identifiers (`phone`, `pan_number`, `aadhaar_number`).
- **Expected behavior:** A farmer or buyer must not have multiple active records with identical phone numbers in the same APMC yard.
- **Actual problem:** 24 duplicate records exist in PostgreSQL across phone numbers `9826012345`, `9826099999`, and `9826019922`.
- **Evidence:** SQL query `SELECT phone, count(*) FROM parties GROUP BY phone HAVING count(*) > 1` returned 3 groups with 8 duplicates each in Supabase PostgreSQL.
- **Business impact:** Farmer advance balances become fragmented across duplicate accounts; Income Tax Section 269ST cash ceiling checks fail to aggregate across duplicates; credit risks when advancing loans.
- **Recommended correction:** Deduplicate `parties` table in PostgreSQL, establish unique constraint on `(home_branch_id, phone)`, and enforce validation in `server.py`.
- **Required tests:** Test attempting to insert a duplicate farmer with identical phone in the same branch must raise integrity error.
- **Dependencies:** `parties`, `server.py`, `database.py`.

---

### Finding AUD-006
- **Severity:** P2
- **Module:** Cloud Database Performance & Indexing
- **File and line:** `commoditi software/supabase_sync.py:301-620`
- **Observed implementation:** PostgreSQL schema generator creates primary keys and unique constraints, but omits non-unique indexes.
- **Expected behavior:** Foreign keys (`branch_id`, `party_id`, `inspector_id`) and frequent filter fields (`invoice_date`, `status`, `created_at`) must have explicit B-tree indexes.
- **Actual problem:** PostgreSQL runs sequential table scans on `purchase_invoices`, `ledger_entries`, `quality_inspections`, and `audit_change_logs`.
- **Evidence:** `pg_indexes` query confirms 0 indexes on `purchase_invoices.branch_id`, `purchase_invoices.party_id`, `ledger_entries.branch_id`, etc.
- **Business impact:** Severe query latency degradation on Central Accounts dashboards as transaction volumes grow to tens of thousands of rows.
- **Recommended correction:** Execute DDL creating indexes:
  `CREATE INDEX idx_pi_branch_date ON purchase_invoices(branch_id, invoice_date);`
  `CREATE INDEX idx_pi_party ON purchase_invoices(party_id);`
  `CREATE INDEX idx_le_branch ON ledger_entries(branch_id, transaction_date);`
- **Required tests:** Query plan inspection (`EXPLAIN ANALYZE`) confirming index scans on branch dashboard queries.
- **Dependencies:** None.

---

### Finding AUD-007
- **Severity:** P2
- **Module:** Multi-Shift Cash Operations
- **File and line:** `commoditi software/database.py:450`
- **Observed implementation:** `branch_daily_cash_drawers` enforces `UNIQUE(branch_id, record_date)`.
- **Expected behavior:** Cash drawers must support multiple operational sessions per day (e.g., Morning Shift / Evening Shift or multiple cashier windows).
- **Actual problem:** A branch cannot open a second cash drawer session on the same date. If Cashier 1 closes their shift at 2:00 PM, Cashier 2 cannot open a drawer for the afternoon session.
- **Evidence:** Schema constraint: `UNIQUE(branch_id, record_date)` in `database.py:450`.
- **Business impact:** Yard cashier desks cannot operate multiple shifts or multi-counter setups during peak harvest season without violating database constraints.
- **Recommended correction:** Replace `UNIQUE(branch_id, record_date)` with `session_id TEXT PRIMARY KEY`, `shift_number INTEGER`, and `status TEXT CHECK (status IN ('OPEN', 'CLOSED'))`.
- **Required tests:** Verify that two consecutive cash drawer sessions can be opened and closed on the same calendar day for the same branch.
- **Dependencies:** `branch_daily_cash_drawers`, `server.py`.
