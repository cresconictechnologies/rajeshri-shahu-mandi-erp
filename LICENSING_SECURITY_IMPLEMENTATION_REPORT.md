# MASTER IMPLEMENTATION REPORT — Rajeshri Shahu Mandi ERP: Commercial Licensing, Authentication & Role Security

**Project:** Rajeshri Shahu Mandi & Commodity Procurement ERP  
**Target Directory:** `c:\projects\tests\commoditi software`  
**Execution Date:** 2026-10-29  
**Status:** FULLY IMPLEMENTED & VERIFIED (71/71 Automated Tests Passing)  
**Standard Compliance:** Commercial Asymmetric Licensing (Ed25519), NIST PBKDF2 Password Hashing, Session Invalidation (RFC 6749/OWASP ASVS), APMC Compliance (Hamali \u20b925/100kg, Section 269ST & 40A(3)).

---

## 1. Executive Summary & System Transformation

The **Rajeshri Shahu Mandi & Commodity Procurement ERP** has been systematically upgraded from an unauthenticated, single-tenant local prototype with decorative badge displays into a **hardened, multi-tenant-ready, commercially licensed commodity trading platform**.

### Core Transformations Executed:
1. **Asymmetric Cryptographic Licensing Engine:** Replaced client-modifiable badge logic with real Ed25519 digital signature verification. Software cannot operate without a cryptographically valid vendor token.
2. **True Separation of Powers:**
   - **Commercial Vendor:** Holds private key offline, dictates edition tier, expiry date, and licensed branch limits.
   - **Super Admin (Business Owner):** Activates vendor tokens, administers branches within licensed quota, provisions staff, views central financials.
   - **Central Accountant:** Manages daily APMC MSP/corridor rates, processes RTGS settlements, receives outward trader payments.
   - **Branch Cashier / Munim:** Restricted to yard-level weighment entry, inward purchase slips, and cash payouts strictly within assigned branch boundaries.
3. **Permanent Lockout of Provisioning Gate (`/setup`):** Removed public setup links from login. The setup wizard permanently serves **HTTP 404** once initial provisioning is recorded in the database.
4. **Stateful Session Architecture & Server-Side Revocation:** Implemented `user_sessions` SQLite persistence. Tokens use a 6-part HMAC format tied to per-instance rotating secrets and explicit database revocation upon logout.
5. **In-Flight Transparent Password Migration:** Automatically upgrades legacy unsalted SHA-256 hashes to NIST-compliant `PBKDF2-HMAC-SHA256` (600,000 iterations, 16-byte random salt) upon user authentication without operational interruption.
6. **Comprehensive Route Defense:** Protected all 32 HTML endpoints and JSON APIs with strict role-based access control (`require_user`, `require_role`, `require_active_license`). Unauthenticated API calls return HTTP 401; unauthenticated UI navigation redirects with HTTP 303 to `/login`.
7. **Branch Isolation & Parameter Forgery Prevention:** Eliminated cross-yard injection vulnerabilities. Branch cashier endpoints force `branch_id = user["branch_id"]`, ignoring any caller-supplied query or form parameters.

---

## 2. Cryptographic Licensing Engine (Ed25519)

### 2.1 Cryptographic Design & Standards
The commercial licensing model uses **Ed25519** (Edwards-curve Digital Signature Algorithm), providing 128-bit security with high verification speeds and compact signatures.

- **Algorithm:** `ed25519`
- **Vendor Public Key (Embedded in ERP `licensing.py`):**  
  `1b6daad3bf761546b3c7433dbf823b6a696483868f8425eab6779f28310dfda8`
- **Vendor Private Key (Offline Air-Gapped Key):**  
  `[REDACTED_VENDOR_PRIVATE_KEY_HELD_OFFLINE]`
- **Token Format:**  
  `base64url(canonical_payload_json).base64url(ed25519_signature)`

### 2.2 Payload Schema & Validation Claims
Each signed token encapsulates the following claims:
```json
{
  "customer_id": "CUST-RSM-MAH-001",
  "business_name": "Rajeshri Shahu Mandi & Commodity Traders",
  "license_key": "RSM-PRO-2026-X892",
  "tier": "pro",
  "max_branches": 3,
  "features": ["apmc_inward", "weighbridge", "outward_dispatch", "rtgs_payments", "audit_trail"],
  "valid_from": "2026-01-01T00:00:00Z",
  "expires_at": "2028-12-31T23:59:59Z",
  "issued_at": "2026-10-29T00:00:00Z"
}
```

### 2.3 Verification Pipeline (`licensing.py`)
1. **Structural Check:** Validates token format (`payload_b64.sig_b64`).
2. **Signature Verification:** Uses `Ed25519PublicKey.from_public_bytes()` to verify `signature` against `payload_bytes`. Any byte modification immediately raises a cryptographic error.
3. **Temporal Validity:** Compares `datetime.now(timezone.utc)` against `valid_from` and `expires_at`. Tokens that are not yet valid or have expired fail closed.
4. **Branch Quota Enforcement:** Dynamically queries `branches WHERE is_active = 1`. If `active_branch_count > max_branches`, access is blocked with HTTP 403.
5. **Persistence:** Verified tokens are stored in `system_settings` table under keys `license_token` and `license_signature`.

---

## 3. Separation of Powers & Responsibility Model

| Role | Issuing Authority | Permitted Operations | Restricted / Forbidden Operations |
| :--- | :--- | :--- | :--- |
| **Commercial Vendor** | Vendor Offline Master Key | Generates signed license tokens via CLI (`vendor_license_issuer.py`); defines tier, expiry, and max branch quota. | Does not access customer operational mandi data or local credentials. |
| **Super Admin / Business Owner** | Licensed Customer Principal | Activates vendor license tokens; registers branches up to licensed limit; sets staff passwords; views consolidated P&L. | Cannot mint licenses, modify tier, extend validity dates, or create branches beyond quota. |
| **Central Accountant** | Super Admin Provisioned | Updates daily mandi rates within corridor; approves RTGS transfers; enters bank UTR numbers; receives outward payments. | Cannot change staff credentials, register branches, delete audit logs, or issue purchases. |
| **Branch Cashier / Munim** | Super Admin Provisioned | Enters inward produce intake; generates weighment parchi; executes cash payouts under \u20b91,99,999; dispatches outward trucks. | Locked to assigned yard; cannot view other branches, modify mandi rates, or bypass cash ceilings. |

---

## 4. Initial Provisioning Hardening & `/setup` Permanent Lockdown

### 4.1 Vulnerability Remediated
The legacy system allowed any visitor navigating to `/setup` to re-enter setup values, create administrator credentials, and display arbitrary decorative active badges.

### 4.2 Security Architecture Implemented
1. **Database Flag:** `system_settings` tracks `is_setup_completed = '1'`.
2. **Controller Guard (`is_system_setup_done()`):**  
   - `GET /setup`: If `is_system_setup_done(conn)` evaluates to `True`, the server immediately returns **HTTP 404 Not Found** with a generic "Page Not Found" template.
   - `POST /setup`: If already completed, returns **HTTP 404** to prevent replay attacks.
3. **UI Link Removal:** Completely removed `<a href="/setup">` from `templates/login.html`.
4. **First-Run Completion:** Initial setup atomically provisions the Super Admin password (salted PBKDF2), seeds initial branches, validates and stores the commercial license token, sets `is_setup_completed = '1'`, and redirects to `/login`.

---

## 5. Authentication & Session Revocation (`user_sessions` Table)

### 5.1 Architecture & Schema
To prevent session replay and enable instant administrative revocation, stateful session tracking was added directly to SQLite:

```sql
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    branch_id TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    is_revoked INTEGER DEFAULT 0,
    revoked_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON user_sessions(session_id, is_revoked, expires_at);
```

### 5.2 Token Format & HMAC Integrity
Session cookies (`mandi_session`) are constructed as:
`session_id:username:role:branch_id:expiry_timestamp:signature`

The signature is computed as:
`HMAC-SHA256(key=instance_secret, data=f"{session_id}:{username}:{role}:{branch_id}:{expiry_timestamp}")`

### 5.3 Validation Pipeline
On every incoming request:
1. Parses cookie structure and verifies HMAC signature using constant-time comparison (`hmac.compare_digest`).
2. Checks clock expiration against `expiry_timestamp`.
3. Queries SQLite `user_sessions WHERE session_id = ? AND is_revoked = 0 AND expires_at > CURRENT_TIMESTAMP`.
4. If missing, revoked, or expired, clears the cookie and terminates the session.
5. On `GET /logout`: Marks `is_revoked = 1, revoked_at = CURRENT_TIMESTAMP` in `user_sessions`, and clears the cookie via HTTP response headers.

---

## 6. In-Flight Transparent Password Migration

### 6.1 Cryptographic Standards
- **Algorithm:** `PBKDF2-HMAC-SHA256`
- **Iterations:** 600,000 (exceeds OWASP 2026 recommended minimum)
- **Salt:** 16 bytes of cryptographically secure randomness via `os.urandom(16)`
- **Stored Representation:** `pbkdf2_sha256$600000$<salt_hex>$<hash_hex>`

### 6.2 Transparent Migration Logic (`database.py` & `server.py`)
```python
def verify_password(stored_hash: str, provided_password: str) -> tuple[bool, bool]:
    # Returns (is_valid, needs_rehash)
    if stored_hash.startswith("pbkdf2_sha256$"):
        # Verify PBKDF2 with constant-time comparison
        ...
        return is_valid, False
    else:
        # Legacy unsalted SHA-256 fallback
        legacy_valid = hmac.compare_digest(hashlib.sha256(provided_password.encode()).hexdigest(), stored_hash)
        return legacy_valid, legacy_valid  # needs_rehash=True if password matches
```
When a staff member or administrator logs in with a legacy password:
1. `verify_password` authenticates the credentials against the SHA-256 hash.
2. Flag `needs_rehash` triggers an immediate background `UPDATE users SET password_hash = ?` with the new 600,000 iteration PBKDF2 hash.
3. No user disruption, no bulk credential resets, and no downtime.

---

## 7. Comprehensive Route & API Guard Matrix

Every registered endpoint in `server.py` enforces explicit authentication and role checks:

| Endpoint Path | HTTP Method | Permitted Roles | Unauthenticated Behavior | Unauthorized Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `/login` | GET, POST | Public | Renders login page / authenticates | N/A |
| `/logout` | GET | All authenticated | Redirects 303 to `/login` | N/A |
| `/setup` | GET, POST | First-run setup | HTTP 404 (when completed) | HTTP 404 |
| `/admin/dashboard` | GET | `admin` | Redirect 303 -> `/login` | Redirect 303 / 403 |
| `/admin/branches` | GET | `admin` | Redirect 303 -> `/login` | HTTP 403 |
| `/admin/branches/toggle` | POST | `admin` | HTTP 401 | HTTP 403 |
| `/admin/users` | GET | `admin` | Redirect 303 -> `/login` | HTTP 403 |
| `/admin/users/toggle` | POST | `admin` | HTTP 401 | HTTP 403 |
| `/admin/commodities` | GET | `admin` | Redirect 303 -> `/login` | HTTP 403 |
| `/admin/settings` | GET | `admin` | Redirect 303 -> `/login` | HTTP 403 |
| `/api/admin/settings` | POST | `admin` | HTTP 401 | HTTP 403 |
| `/api/admin/staff/update-all`| POST | `admin` | HTTP 401 | HTTP 403 |
| `/api/admin/users/update-credentials` | POST | `admin` | HTTP 401 | HTTP 403 |
| `/api/admin/license/activate` | POST | `admin` | HTTP 401 | HTTP 403 |
| `/accounts/dashboard` | GET | `accountant`, `admin` | Redirect 303 -> `/login` | HTTP 403 |
| `/accounts/settings` | GET | `accountant`, `admin` | Redirect 303 -> `/login` | HTTP 403 |
| `/api/accounts/rates` | POST | `accountant`, `admin` | HTTP 401 | HTTP 403 |
| `/api/accounts/rate-overrides/action` | POST | `accountant`, `admin` | HTTP 401 | HTTP 403 |
| `/api/accounts/rtgs/process` | POST | `accountant`, `admin` | HTTP 401 | HTTP 403 |
| `/api/accounts/outward/receive-payment` | POST | `accountant`, `admin` | HTTP 401 | HTTP 403 |
| `/api/accounts/inspectors` | POST | `accountant`, `admin` | HTTP 401 | HTTP 403 |
| `/api/accounts/inspectors/toggle` | POST | `accountant`, `admin` | HTTP 401 | HTTP 403 |
| `/branch/dashboard` | GET | `cashier`, `admin` | Redirect 303 -> `/login` | HTTP 403 |
| `/branch/stock` | GET | `cashier`, `admin` | Redirect 303 -> `/login` | HTTP 403 |
| `/branch/settings` | GET | `cashier`, `admin` | Redirect 303 -> `/login` | HTTP 403 |
| `/api/branch/invoices/create` | POST | `cashier`, `admin` | HTTP 401 | HTTP 403 |
| `/api/cashier/payout` | POST | `cashier`, `admin` | HTTP 401 | HTTP 403 |
| `/api/cashier/request-rtgs` | POST | `cashier`, `admin` | HTTP 401 | HTTP 403 |
| `/api/branch/outward/create` | POST | `cashier`, `admin` | HTTP 401 | HTTP 403 |
| `/api/branch/buyers/register`| POST | `cashier`, `admin` | HTTP 401 | HTTP 403 |
| `/api/branch/farmers/register`| POST | `cashier`, `admin` | HTTP 401 | HTTP 403 |
| `/api/branch/farmers/edit` | POST | `cashier`, `admin` | HTTP 401 | HTTP 403 |

---

## 8. Branch Isolation & Cross-Yard Anti-Tampering Protections

### 8.1 Cross-Yard Injection Exploit Remediated
Previously, a cashier assigned to Chikhali Yard (`BR-CHK`) could submit a POST payload containing `branch_id: "BR-VRV"` (Varvand Yard) and corrupt inventory and drawer balances of an unauthorized branch.

### 8.2 Architectural Enforcement
In `server.py`:
```python
# For cashiers, strictly enforce session branch_id - ignore any client spoofing
if user.get("role") == "cashier":
    effective_branch_id = user.get("branch_id")
else:
    effective_branch_id = branch_id or user.get("branch_id")
```
- For all branch mutating endpoints (`/api/branch/invoices/create`, `/api/cashier/payout`, `/api/branch/outward/create`, `/api/cashier/request-rtgs`), the user's cryptographically signed session token strictly dictates the operating `branch_id`.
- Any conflicting `branch_id` passed in JSON, form bodies, or query parameters is discarded.

---

## 9. Template & UI Enhancements

### 9.1 Login Portal (`templates/login.html`)
- Removed the public link to `/setup`.
- Displays clean, secure credentials input with role dispatch indicators.

### 9.2 Super Admin Settings (`templates/admin_settings.html`)
- **Commercial License Card:** Displays verified token metadata, including Cryptographic Issuer Signature status (`\u2714 Asymmetric Ed25519 Verified`), Customer ID, License Key, Active Tier (`PRO`), Expiry Date, and Active Branch Quota usage (`3 / 3 Branches Used`).
- **License Renewal & Activation Modal:** Allows the Super Admin to paste a new vendor-signed license token string and submit it to `POST /api/admin/license/activate` without restarting the server.
- **Staff Credentials Card:** Step 3 credential manager allows assigning names, mobile numbers, and updating passwords for Central Accountant and Branch Cashiers.

---

## 10. Complete Verification Evidence (71/71 Tests Passing)

### 10.1 Execution Command
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### 10.2 Test Suite Breakdown
1. **`test_licensing_security.py` (13 tests):**
   - Unauthenticated API access returns HTTP 401.
   - Unauthenticated browser page access redirects to `/login`.
   - Accountant blocked from admin endpoints (HTTP 403).
   - Cashier blocked from accountant/admin endpoints (HTTP 403).
   - Cashier cross-yard parameter spoofing overridden by session `branch_id`.
   - Setup page permanently returns HTTP 404 once completed.
   - Valid Ed25519 license token activates successfully.
   - Tampered signature license token rejected.
   - Modified payload claims license token rejected.
   - Expired license token blocked at route boundary.
   - Branch creation beyond license quota rejected (HTTP 403).
   - Session revoked in `user_sessions` table upon logout.
   - Legacy SHA-256 password automatically upgraded to PBKDF2-HMAC-SHA256.
2. **`test_security_and_system_audit.py` (8 tests):**
   - Parameterized SQL injection defense.
   - Zero hardcoded production secrets or private keys in source control.
   - Zero swallowed exceptions.
   - Section 269ST (\u20b91,99,999 cash ceiling) & 40A(3) compliance.
   - Cryptographic password hashing integrity.
   - SQLite WAL mode and foreign key enforcement.
   - Zero mock data dictionaries in production code.
   - XSS sanitization & JSON embedding security.
3. **`test_auth_and_panel_isolation.py` (7 tests):**
   - Owner setup page rendering and first-run flow.
   - Terminal login and role dispatch.
   - Logout clears session cookies.
   - Strict panel isolation.
   - Zero-stock auto-hide logic.
   - Buldhana APMC commodities registered.
   - Staff credentials batch update.
4. **`test_calculations.py` (8 tests):**
   - Hamali deduction (\u20b925/100kg standard APMC).
   - Moisture and karda dockage calculations.
   - Cash rounding.
   - Denomination counting.
   - Section 269ST ceiling compliance.
   - Rate corridor validations.
5. **`test_api_endpoints.py` (10 tests):**
   - Dashboard endpoints for Admin, Accountant, and Branch.
   - Inward parchi generation.
   - RTGS workflow closure.
   - Super admin commodity P&L visibility.
6. **`test_design_audit.py` (9 tests):**
   - Master theme CSS encapsulation.
   - Card-first design tokens.
   - Color gradients for 3 tiers.
7. **`test_new_features.py` (11 tests):**
   - Physical stock views.
   - Buyer trader registrations.
   - Farmer profile edits and audit logs.
   - Inward produce intake + cash payout atomic workflows.
8. **`test_rtgs_license_outward.py` (5 tests):**
   - Live UTR tracking.
   - Outward receivables management.
   - Staff credential update audit logging.

### 10.3 Verification Output Summary
```
Ran 71 tests in 15.433s
OK
```

---

## 11. Deployment & Operator Runbook

### 11.1 Generating New Commercial Licenses (Vendor Offline Tool)
Vendors issue license tokens using `vendor_license_issuer.py` from their secure workstation:
```bash
python vendor_license_issuer.py --customer "CUST-RSM-MAH-001" --name "Rajeshri Shahu Mandi & Commodity Traders" --key "RSM-PRO-2026-X892" --tier "pro" --branches 5 --days 730
```
**Output:** Generates a signed base64url license string:
`<payload_b64>.<signature_b64>`

### 11.2 Customer License Activation
1. The customer Super Admin signs in to `http://127.0.0.1:8080/admin/settings`.
2. Pastes the token string into the **Renew Commercial License** box.
3. Clicks **Activate License**.
4. The backend verifies the Ed25519 digital signature, validates expiry dates, updates `system_settings`, and displays the new branch limit immediately.

### 11.3 Database Backup & Maintenance
- Database file: `commodity_mandi.db`.
- Automatic WAL mode is enabled: writes are high-speed and non-blocking.
- Regular backups can be taken safely using SQLite online backup API or file copy when server is idle.

---

## 12. Residual Risks & Ponytail Scope Disclosures

- **What Was Skipped / Not Checked:**
  - Hardware fingerprinting (e.g. CPU ID / Motherboard serial / MAC locking) was intentionally omitted to prevent brittle failures in local virtualized environments, Docker containers, or upon hardware upgrades.
  - Multi-factor authentication (MFA / SMS OTP) was not implemented for local mandi yard operations as cashiers frequently operate in rural APMC yards with intermittent cellular connectivity.
- **Residual Risks the User Must Know:**
  - Because `commodity_mandi.db` is stored locally on the host machine, anyone with root/administrator filesystem access to the local machine can read the SQLite file directly or modify records outside the application runtime. Filesystem-level encryption (BitLocker) should be enabled on the host PC.
  - The vendor signing key in `vendor_license_issuer.py` must never be deployed to the customer's production host. It must remain strictly on the software vendor's private development machine.
