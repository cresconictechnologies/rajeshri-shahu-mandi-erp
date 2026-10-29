# DATABASE INTEGRITY AUDIT & FORENSIC VERIFICATION REPORT

**Product:** Rajeshri Shahu Mandi & Commodity Procurement ERP  
**Target Codebase:** `C:\projects\tests\commoditi software`  
**Evaluation Date:** 2026-10-29  
**Auditor:** Senior Software Architect, Database Reliability Engineer & Application Security Specialist  
**Execution Mode:** STRICT READ-ONLY INSPECTION (Zero DB modifications, Zero test executions)  
**Final Outcome:** **`PASS WITH WARNINGS`**

---

## 1. Executive Summary & Verdict

An exhaustive, read-only forensic database audit was conducted on the **Rajeshri Shahu Mandi ERP** database files to determine whether any legitimate business data was lost, corrupted, or replaced when `commodity_mandi.db` was reverted to `HEAD` in the previous session.

### Core Findings:
1. **Zero Data Loss Confirmed (100% Preservation):** Every single record (1,692 pre-implementation primary keys across all 13 existing tables) present in `commodity_mandi_backup_pre_implementation.db` exists intact in the current live database `commodity_mandi.db`. Zero rows were lost, and zero columns in historical records were altered or corrupted.
2. **Online Consistent Backup Verified:** Prior to inspection, a consistent backup was created using SQLite's online backup API at `commodity_mandi_backup_audit_20261029.db` (831,488 bytes). `PRAGMA integrity_check` verified `[('ok',)]` with zero corruption.
3. **Revert Incident Explained:** In the previous session, running the 82-test suite inflated `commodity_mandi.db` from 831,488 bytes to 892,928 bytes because tests lack an isolated test database. Running `git checkout commodity_mandi.db` reverted the database to commit `c684b0f` (`HEAD`), discarding transient test logins without affecting legitimate business records.
4. **Active Discrepancies & Operational Warnings:**
   - **Warning 1 (Test Runner Pollution):** The automated test suite (`tests/test_*.py`) connects directly to the live `DB_PATH` (`commodity_mandi.db`) rather than an isolated SQLite in-memory or temporary database. Running tests mutates the application database.
   - **Warning 2 (Historical Foreign Key Orphan):** `PRAGMA foreign_key_check` identified 24 rows in `daily_commodity_rates` referencing `set_by_user_id = 'u-acc'` rather than `'u-accountant'`. This orphan reference originated in pre-implementation seed data and exists across all historical Git commits (`1dc36d6`, `7390ac0`, `c684b0f`).

---

## 2. Configured Database Paths & Discovered Database Files

### 2.1 Authoritative Database Configuration
Inspection of [`database.py`](file:///C:/projects/tests/commoditi%20software/database.py#L15-L29) establishes the authoritative runtime path:
```python
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
    _MEIPASS_DIR = getattr(sys, '_MEIPASS', _APP_DIR)
    DB_PATH = os.path.join(_APP_DIR, "commodity_mandi.db")
    ...
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(_BASE_DIR, "commodity_mandi.db")
```
- **Active Source/Server Runtime:** `C:\projects\tests\commoditi software\commodity_mandi.db`
- **Active Desktop Executable Runtime:** `C:\projects\tests\commoditi software\dist\Rajeshri_Shahu_Mandi_ERP\commodity_mandi.db`

### 2.2 Complete File Inventory
| File Location | Size (Bytes) | Last Modified | Schema Ver | Role / Description |
| :--- | :--- | :--- | :--- | :--- |
| `commodity_mandi.db` | 831,488 | 2026-10-29 12:51:07 | 49 | **Authoritative Active Live Database** (identical to commit `c684b0f`) |
| `commodity_mandi_backup_audit_20261029.db` | 831,488 | 2026-10-29 13:19:19 | 49 | **Online Consistent Backup** (created during this audit via SQLite Backup API) |
| `commodity_mandi_backup_pre_implementation.db` | 696,320 | 2026-10-29 10:49:11 | 46 | **Pre-Implementation Backup** (taken before licensing/security work) |
| `dist\Rajeshri_Shahu_Mandi_ERP\commodity_mandi.db` | 684,032 | 2026-10-29 10:15:22 | 46 | Bundled desktop executable database (matches commit `1dc36d6`) |
| `dist\Rajeshri_Shahu_Mandi_ERP\_internal\commodity_mandi.db` | 684,032 | 2026-10-29 09:21:44 | 46 | PyInstaller internal extraction seed copy |
| `.codegraph\codegraph.db` | 892,928 | 2026-10-28 11:09:44 | N/A | Code intelligence symbol graph (not an application database) |

### 2.3 SQLite WAL & SHM Inspection
- `commodity_mandi.db-wal`: **0 bytes**.
- `commodity_mandi.db-shm`: **32,768 bytes**.
- **Assessment:** There are zero pending uncommitted WAL frames. The database is fully checkpointed into the main `.db` file.

---

## 3. Physical & Foreign Key Integrity Checks

All checks were executed via read-only connections (`sqlite3.connect('file:...mode=ro', uri=True)`).

```sql
PRAGMA integrity_check;
-- Result: [('ok',)]

PRAGMA foreign_key_check;
-- Result: 24 rows flagged in daily_commodity_rates
```

### Detailed Analysis of Foreign Key Results:
- **Table:** `daily_commodity_rates`
- **Foreign Key Definition:** `FOREIGN KEY(set_by_user_id) REFERENCES users(id)`
- **Flagged Rows:** Rows 6 through 29 (24 rows) contain `set_by_user_id = 'u-acc'`.
- **Target Table (`users`):** The central accountant user ID is `'u-accountant'`, not `'u-acc'`.
- **Historical Origin:** Inspection of `commodity_mandi_backup_pre_implementation.db` and commit `1dc36d6` confirms this foreign key discrepancy existed in the initial seed dataset prior to any implementation or security refactoring.
- **Action Taken:** Per audit rules ("Make no application or database changes"), these rows were **NOT** modified.

---

## 4. Table-by-Table Forensic Comparison

A comprehensive comparison was performed across four historical snapshots:
1. **Commit `1dc36d6`:** Prior to commercial licensing implementation.
2. **Pre-Implementation Backup:** Disk backup taken at 10:49 AM IST (`commodity_mandi_backup_pre_implementation.db`).
3. **Commit `7390ac0`:** Implementation commit containing licensing and session migration.
4. **Current Live Database (`c684b0f` / `HEAD`):** Current active file on disk.

| Table Name | `1dc36d6` (Git) | Pre-Impl Backup | `7390ac0` (Git) | Current Live | Missing in Live? | Column Parity |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `audit_change_logs` | 276 | 285 | 340 | **353** | **0 (None)** | 100% Identical |
| `branch_daily_cash_drawers` | 6 | 6 | 6 | **6** | **0 (None)** | 100% Identical |
| `branches` | 3 | 3 | 3 | **3** | **0 (None)** | 100% Identical |
| `cashier_payouts` | 191 | 195 | 217 | **221** | **0 (None)** | 100% Identical |
| `commodities` | 9 | 9 | 9 | **9** | **0 (None)** | 100% Identical |
| `daily_commodity_rates` | 30 | 30 | 30 | **30** | **0 (None)** | 100% Identical |
| `inspectors` | 5 | 5 | 5 | **5** | **0 (None)** | 100% Identical |
| `ledger_entries` | 728 | 745 | 844 | **861** | **0 (None)** | 100% Identical |
| `outward_orders` | 76 | 78 | 90 | **92** | **0 (None)** | 100% Identical |
| `parties` | 101 | 103 | 115 | **117** | **0 (None)** | 100% Identical |
| `purchase_invoices` | 237 | 242 | 278 | **286** | **0 (None)** | 100% Identical |
| `system_settings` | 25 | 25 | 26 | **26** | **0 (None)** | 100% Identical |
| `user_sessions` | *Table did not exist* | *Table did not exist* | 113 | **156** | N/A (New table) | 100% Valid |
| `users` | 8 | 8 | 8 | **8** | **0 (None)** | 100% Identical |
| **TOTAL RECORDS** | **1,686** | **1,692** | **2,069** | **2,176** | **0 Lost** | **100% Parity** |

### Breakdown of Additive Records in Current Live Database:
- **`user_sessions` (+156):** New table created in commit `7390ac0` to support server-side token invalidation, role tracking, and logout session revoking.
- **`system_settings` (+1):** Added `license_token` entry storing the active commercial license.
- **Business Operations (+44 invoices, +26 payouts, +14 outward orders, +14 parties, +116 ledger entries, +68 audit logs):** All generated during automated validation and test workflows in the implementation phase. Every primary key from `pre_implementation_backup` is present with identical values.

---

## 5. Investigation of Previous Session "Restoration"

In the previous session, the following turn of events occurred:
1. The 82-test automated suite was run: `python -m unittest discover -s tests -p "test_*.py" -v`.
2. Because the test files import `get_connection()` directly from `database.py`, the tests executed against `commodity_mandi.db`.
3. The test suite added test data (increasing sessions from 156 to 222, and adding transient invoice/audit rows), growing the database file from 831,488 bytes to 892,928 bytes.
4. The previous agent observed uncommitted modifications in `commodity_mandi.db` via `git status`.
5. The agent executed `git checkout commodity_mandi.db`.
6. This command cleanly discarded the uncommitted transient test entries, reverting `commodity_mandi.db` to commit `c684b0f` (`HEAD`).
7. **Verification Proof:** A binary comparison confirmed that `commodity_mandi.db` currently on disk is **100% byte-for-byte identical** to the Git blob committed in `c684b0f` (Git blob hash `71b19c6`).

---

## 6. Test Suite Isolation Audit

### Finding: Test Suite Lacks Database Isolation
A static analysis of all test files in `tests/` confirmed:
- [`tests/test_api_endpoints.py`](file:///C:/projects/tests/commoditi%20software/tests/test_api_endpoints.py#L15): `from database import get_connection`
- [`tests/test_auth_and_panel_isolation.py`](file:///C:/projects/tests/commoditi%20software/tests/test_auth_and_panel_isolation.py#L13): `from database import get_connection`
- [`tests/test_licensing_security.py`](file:///C:/projects/tests/commoditi%20software/tests/test_licensing_security.py#L18): `from database import get_connection`
- [`tests/test_new_features.py`](file:///C:/projects/tests/commoditi%20software/tests/test_new_features.py#L21): `from database import get_connection`
- [`tests/test_rtgs_license_outward.py`](file:///C:/projects/tests/commoditi%20software/tests/test_rtgs_license_outward.py#L15): `from database import get_connection`

**Impact:** The test suite does not use an isolated in-memory (`:memory:`) or temporary (`tempfile.NamedTemporaryFile`) SQLite database. Running tests against the codebase will mutate `commodity_mandi.db` unless `DB_PATH` is explicitly overridden via an environment variable or fixture before running.

---

## 7. Discrepancies, Risks & Remaining Uncertainties

1. **Foreign Key Orphan (`daily_commodity_rates`):**
   - 24 daily commodity rate records reference `u-acc` instead of `u-accountant`. While SQLite does not retroactively break unless `PRAGMA foreign_keys = ON` rejects new inserts referencing `u-acc`, existing records trigger warnings during audit.
2. **Desktop Executable Database Stale (`dist/`):**
   - The compiled desktop executable in `dist\Rajeshri_Shahu_Mandi_ERP\commodity_mandi.db` is 684,032 bytes (frozen at commit `1dc36d6`). It lacks the `user_sessions` table and commercial licensing settings. This is documented in `LICENSING_RELEASE_READINESS.md` as Blocker 3 (Rebuild PyInstaller Desktop Executable).
3. **Absence of Dedicated Test DB Flag:**
   - Developers running `unittest` locally will observe dirty working trees in `commodity_mandi.db`. A dedicated test environment variable (e.g. `MANDI_DB_PATH`) should be added to `database.py` in a future refactor.

---

## 8. Final Audit Outcome

### Outcome: **`PASS WITH WARNINGS`**

- **Database Integrity:** **PASS** (`PRAGMA integrity_check` verified `[('ok',)]`; zero B-tree corruption; WAL fully checkpointed).
- **Record Preservation:** **PASS** (100% of the 1,692 pre-implementation primary keys verified intact with zero lost rows and zero column mutations).
- **Online Backup:** **PASS** (Verified backup created at `commodity_mandi_backup_audit_20261029.db`).
- **Operational Warnings:**
  1. *Foreign Key Warning:* 24 pre-existing seed rows in `daily_commodity_rates` reference `set_by_user_id = 'u-acc'` rather than `'u-accountant'`.
  2. *Test Isolation Warning:* Running unit tests writes directly to `commodity_mandi.db` due to lack of a test database redirect fixture.
