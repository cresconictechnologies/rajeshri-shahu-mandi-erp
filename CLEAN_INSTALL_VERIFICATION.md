# CLEAN COMMERCIAL CUSTOMER INSTALLATION VERIFICATION REPORT

**Product:** Rajeshri Shahu Mandi & Commodity Procurement ERP  
**Target Codebase:** `C:\projects\tests\commoditi software`  
**Evaluation Date:** 2026-10-29  
**Auditor / Architect:** Senior Software Architect, Security & Database Reliability Engineer  
**Status:** **VERIFIED & CERTIFIED** (91 / 91 Tests Passing)

---

## 1. Executive Summary

The application has been restructured and certified for commercial customer deployment. Schema initialization has been completely decoupled from demo/development seeding. 

Every new customer installation now begins with a **squeaky-clean, unpopulated database** containing zero default credentials, zero fake parties, zero demo transactions, and zero pre-baked license tokens.

---

## 2. Clean Installation Database Audit

When a new commercial customer launches the application for the first time, `database.init_db()` creates the SQLite tables and migrations. 

### 2.1 Table Counts on Fresh Installation
| Table Name | Clean Customer Install | Classification | Purpose |
| :--- | :--- | :--- | :--- |
| `users` | **0** | Customer Identity | **Zero default credentials**. Owner & staff provisioned in first-run setup. |
| `branches` | **0** | Licensed Yard Hierarchy | Created up to license limit upon valid license activation. |
| `parties` | **0** | Customer Counterparties | **Zero fake farmers, stockers, or buyers**. |
| `purchase_invoices` | **0** | Financial Transactions | **Zero demo invoices**. |
| `cashier_payouts` | **0** | Financial Transactions | **Zero demo payouts**. |
| `branch_daily_cash_drawers` | **0** | Financial Reconciliation | **Zero pre-filled cash floats**. Initialized daily by cashiers. |
| `ledger_entries` | **0** | General Ledger | **Zero demo ledger vouchers**. |
| `outward_orders` | **0** | Sales & Dispatch | **Zero demo outward orders**. |
| `inspectors` | **0** | Quality Assurance | **Zero demo inspectors**. Added by authorized central accountant. |
| `daily_commodity_rates` | **0** | Pricing Governance | **Zero mock rates**. Set daily by Central Accountant rate board. |
| `user_sessions` | **0** | Authentication State | **Zero pre-existing sessions**. |
| `audit_change_logs` | **0** | Regulatory Audit Trail | **Zero test change logs**. |
| `commodities` | **9** | **Application Master Data** | Statutory APMC commodities (Soyabean, Cotton, Tur, Chana, Wheat, Mustard, Maize, Moong, Urad). |
| `system_settings` | **6** | **Application Configuration** | Statutory APMC calculation parameters (Sec 269ST ₹1,99,999 cash limit, Sec 40A(3) ₹10,000 cash limit, Hamali ₹25/100kg, is_setup_completed='0'). |

---

## 3. First-Run Setup & Provisioning Workflow

### 3.1 Initial Route Gating
1. Upon cold startup, if `system_settings.is_setup_completed != '1'`, accessing root `/` immediately redirects (HTTP 303) to `/setup`.
2. Direct access to `/admin/dashboard`, `/accounts/dashboard`, or `/branch/dashboard` fails closed and redirects to `/login` (which redirects to `/setup`).

### 3.2 Setup Wizard Execution (`/setup`)
1. **Business Profile:** Collects legal entity name, APMC license, owner full name, login username, strong password, and mobile number.
2. **Commercial License Key Activation:**
   - Requires an Ed25519-signed license token issued by Cresconic Technologies.
   - Rejects missing, invalid, tampered, expired, or wrong-product tokens with HTTP 400 and an explicit error alert.
   - Extracts `tier` and `max_branches` from the cryptographic payload.
3. **Staff Credential Generation:**
   - Central HQ Accountant (Name, Username, Password, Mobile).
   - Branch Cashiers (1 Cashier per licensed branch yard: Chikhali, Varvand, Dhad) with individual passwords.
4. **Provisioning Execution:**
   - Inserts branches into `branches` table (`is_active=1`) up to `max_branches`.
   - Hashes all passwords using NIST-compliant PBKDF2-HMAC-SHA256 (600,000 iterations, 16-byte random salt).
   - Writes `users` records for Super Admin, Accountant, and Branch Cashiers.
   - Sets `is_setup_completed = '1'`.
   - Renders a printable/notable **Staff Credential Handover Record**.

### 3.3 Permanent Lockout of First-Run Provisioning
- Once `is_setup_completed = '1'`, both `GET /setup` and `POST /setup` permanently return **HTTP 404 Not Found**.
- Staff additions, credential changes, or password resets must be performed exclusively by the authenticated Super Admin via `/admin/settings` or `/api/admin/users/update-credentials`.

---

## 4. Full Automated Test Suite Results

The automated test suite was executed against the isolated test database:

```
python -m unittest discover -s tests -p "test_*.py" -v
```

### Test Results Breakdown:
| Test Module | Tests | Passing | Failing | Description |
| :--- | :--- | :--- | :--- | :--- |
| [`test_api_endpoints.py`](file:///C:/projects/tests/commoditi%20software/tests/test_api_endpoints.py) | 10 | 10 | 0 | Mandi calculations, three-tier dashboards, weighment desks. |
| [`test_auth_and_panel_isolation.py`](file:///C:/projects/tests/commoditi%20software/tests/test_auth_and_panel_isolation.py) | 7 | 7 | 0 | Setup wizard, terminal login, strict role & panel isolation. |
| [`test_calculations.py`](file:///C:/projects/tests/commoditi%20software/tests/test_calculations.py) | 8 | 8 | 0 | Moisture/karda deduction, Hamali ₹25/100kg, Sec 269ST & 40A(3). |
| [`test_clean_installation.py`](file:///C:/projects/tests/commoditi%20software/tests/test_clean_installation.py) | 6 | 6 | 0 | Zero-demo DB verification, first-run wizard, credential provisioning. |
| [`test_database_isolation.py`](file:///C:/projects/tests/commoditi%20software/tests/test_database_isolation.py) | 3 | 3 | 0 | Isolated temp DB verification, production guardrail, byte-for-byte dev DB integrity. |
| [`test_design_audit.py`](file:///C:/projects/tests/commoditi%20software/tests/test_design_audit.py) | 9 | 9 | 0 | Card-first UI architecture, design tokens, responsive layout. |
| [`test_licensing_security.py`](file:///C:/projects/tests/commoditi%20software/tests/test_licensing_security.py) | 24 | 24 | 0 | Ed25519 signature checks, replay defense, session revocation, key separation. |
| [`test_new_features.py`](file:///C:/projects/tests/commoditi%20software/tests/test_new_features.py) | 8 | 8 | 0 | Branch stock page, settings panels, immutable farmer audit logs. |
| [`test_rtgs_license_outward.py`](file:///C:/projects/tests/commoditi%20software/tests/test_rtgs_license_outward.py) | 5 | 5 | 0 | RTGS payout tracker, UTR closures, outward payment settlement. |
| [`test_security_and_system_audit.py`](file:///C:/projects/tests/commoditi%20software/tests/test_security_and_system_audit.py) | 8 | 8 | 0 | SQL injection immunity, secret hygiene, zero swallowed exceptions, WAL mode. |
| **TOTAL** | **91** | **91** | **0** | **100% Passing in 28.755s** |

---

## 5. Development Database Protection & Preservation

- **File:** `C:\projects\tests\commoditi software\commodity_mandi.db`
- **Initial File Size:** 831,488 bytes
- **Post-Test File Size:** 831,488 bytes
- **SHA-256 Digest:** `8dcdc82568d5858b28a187643974cd4d96bd6e696f2b15c8195fd631bec6adc3`
- **Integrity Status:** **100% UNCHANGED** (Zero bytes written to the development database).

---

## 6. Pre-Production Release Gates (Remaining Blockers)

With database isolation and clean commercial initialization complete, the remaining human operator blockers for final customer release remain:

1. **Official Air-Gapped Vendor Key Ceremony:** Follow [`PRODUCTION_RELEASE_RUNBOOK.md`](file:///c:/projects/tests/commoditi%20software/PRODUCTION_RELEASE_RUNBOOK.md) to generate the official production Ed25519 keypair and set `PRODUCTION_VENDOR_PUBLIC_KEY_HEX`.
2. **Git History Secret Scrubbing:** Follow [`GIT_SECRET_CLEANUP_RUNBOOK.md`](file:///c:/projects/tests/commoditi%20software/GIT_SECRET_CLEANUP_RUNBOOK.md) to purge historical commit `7390ac0` from remote repository history.
3. **Rebuild PyInstaller Desktop Executable:** Run `python build_desktop_app.py` after Blockers 1 and 2 to compile the clean production binary.
