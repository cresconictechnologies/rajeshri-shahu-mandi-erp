# COMMERCIAL LICENSING, AUTHENTICATION & ROLE SECURITY AUDIT
**Product:** Rajeshri Shahu Mandi & Commodity Procurement ERP  
**Target Environment:** Local Standalone / Multi-Branch Network (Port 8080)  
**Audit Date:** 2026-10-29  
**Status:** AUDIT ONLY — DEFENSIVE ASSESSMENT & SECURITY BASELINE  
**Audit Report Location:** `c:\projects\tests\commoditi software\LICENSING_SECURITY_AUDIT.md`

---

## SECTION 1 — EXECUTIVE SUMMARY

### 1.1 Commercial Distribution Readiness Verdict
**VERDICT: CRITICALLY UNSAFE FOR COMMERCIAL DISTRIBUTION IN PRESENT STATE.**

The application in its current state cannot be distributed as a commercial software product. While the application possesses a functional domain model for commodity calculations (APMC mandi rules, tare, moisture deductions, and Indian Income Tax Section 269ST/40A(3) ceilings), its **commercial licensing, authentication, and authorization controls are fundamentally broken or absent**.

### 1.2 Primary Reasons for Rejection
1. **Zero License Enforcement or Cryptographic Verification:**  
   The commercial license is merely an unverified string in SQLite (`RST-PRO-2026-MH3B-89A12F`). There is no cryptographic signature, no public-key validation (Ed25519/RSA), no expiration check, and no branch limit enforcement. The software self-declares as "ACTIVE" without vendor control.
2. **Unauthenticated Access to Administrative Dashboards:**  
   Due to logic flaw in role-checking branches (`if user and user.get("role") != ...:`), requests with no authentication cookie evaluate this check to `False` and fall through to default fallback dictionaries (`logged_in_user = user or {"username": "admin", ...}`). An unauthenticated visitor accessing `/admin/dashboard`, `/admin/settings`, `/accounts/dashboard`, or `/branch/dashboard` receives **HTTP 200 OK** and full access.
3. **Zero Authentication on Mutating API Endpoints:**  
   Over 20 mutating `POST` endpoints—including staff credential resetting, branch creation, daily commodity rate posting, RTGS payouts, and inward purchasing—have no session checks or role guards. Anyone who sends a POST request directly to `/api/admin/staff/update-all` can rewrite owner, accountant, and cashier credentials.
4. **Permanent Exposure of the `/setup` Endpoint:**  
   The initial setup page (`/setup`) is prominently linked from the public login screen and remains completely unprotected even after setup is completed. Any unauthorized user can open `/setup`, view existing staff usernames and phone numbers, and submit a form that rewrites the Super Admin password and replaces the license key.
5. **Hardcoded Session Secret & Forgery Risk:**  
   The HMAC session secret falls back to a hardcoded string (`rajeshri-shahu-mandi-erp-2026-cresconic-secret`). Session tokens contain no expiration timestamp (`exp`) and cannot be revoked server-side.

---

## SECTION 2 — ARCHITECTURE DISCOVERED

### 2.1 Technology Stack Inventory
| Component | Discovered Technology | Version / Specification |
| :--- | :--- | :--- |
| **Runtime Environment** | Python (CPython on Windows 11 AMD64) | Python 3.14.5 |
| **Web & Application Server**| FastAPI + Starlette + Uvicorn | ASGI embedded server on `127.0.0.1:8080` |
| **Desktop Shell** | PyInstaller + pywebview (Microsoft Edge WebView2) | Standalone desktop GUI executable |
| **Database Engine** | SQLite 3 via Python `sqlite3` standard library | `commodity_mandi.db` (WAL Mode, `foreign_keys = ON`) |
| **Template Engine** | Jinja2 | Server-rendered HTML (`templates/*.html`) |
| **Styling & Design Tokens** | Native CSS Architecture | `static/theme.css` (Card-first responsive layout) |
| **Authentication System** | Custom HMAC-SHA256 Cookie Token (`mandi_session`) | URL-safe Base64 encoded payload: `username\|role\|branch_id\|signature` |
| **Password Storage** | Unsalted single-round SHA-256 | `hashlib.sha256(pwd.encode('utf-8')).hexdigest()` |
| **Testing Framework** | Python standard `unittest` + `TestClient` | 58 passing tests across 7 test modules |

### 2.2 Entry Points & File Mapping
- **Desktop Entry Point:** [`desktop_app.py`](file:///c:/projects/tests/commoditi%20software/desktop_app.py)  
  Spawns an embedded Uvicorn server thread on port 8080 and creates a `pywebview` window pointing to `http://127.0.0.1:8080`.
- **Backend Application Core:** [`server.py`](file:///c:/projects/tests/commoditi%20software/server.py) (2,708 lines)  
  Initializes FastAPI `app`, mounts `/static`, registers Jinja2 templates, defines authentication helpers, and registers 46 web and API endpoints.
- **Database & Data Layer:** [`database.py`](file:///c:/projects/tests/commoditi%20software/database.py) (551 lines)  
  Manages SQLite database connections, schema migrations (13 tables), password hashing, and initial data seeding.
- **Business Domain Logic:** [`calculations.py`](file:///c:/projects/tests/commoditi%20software/calculations.py) (274 lines)  
  Mandi gross/tare/net calculations, moisture and karda deductions, statutory cash ceilings (Sec 269ST, Sec 40A(3)), and denomination roundup.
- **Packaging Script:** [`build_desktop_app.py`](file:///c:/projects/tests/commoditi%20software/build_desktop_app.py)  
  Builds standalone binary via PyInstaller into `dist/Rajeshri_Shahu_Mandi_ERP/`.

---

## SECTION 3 — CURRENT ACCESS-FLOW DIAGRAM

```mermaid
flowchart TD
    Client(["Client HTTP Request\n(Browser / Script / Desktop App)"]) --> RouteCheck{"Target Route"}

    %% Setup Route
    RouteCheck -->|GET /setup or POST /setup| SetupHandler["setup_view / setup_post\n(server.py L155, L191)"]
    SetupHandler --> SetupFlaw["CRITICAL FLAW:\nNo Authentication\nNo Setup Lock Check\nAccepts arbitrary License String\nOverwrites Admin & Staff Credentials"]

    %% Login Route
    RouteCheck -->|POST /login| LoginHandler["login_post\n(server.py L304)"]
    LoginHandler --> DBAuthCheck{"DB Query:\nusername & sha256(pwd)"}
    DBAuthCheck -->|Match| IssueCookie["Issue Cookie 'mandi_session'\nFormat: user|role|branch|sig\n(Key: hardcoded default fallback)\n(No Expiry, No Server Session ID)"]
    DBAuthCheck -->|Mismatch| LoginReject["401 Unauthorized\n(login.html with error)"]

    %% View Routes
    RouteCheck -->|GET /admin/*\nGET /accounts/*\nGET /branch/*| ViewHandlers["View Handlers\n(admin_dashboard_view, etc.)"]
    ViewHandlers --> CookieCheck{"Cookie Present & Valid?"}
    CookieCheck -->|Yes, Role Mismatch| RedirectUser["303 Redirect to assigned role URL\n(Cross-panel isolation triggered)"]
    CookieCheck -->|Yes, Role Matches| AllowView["200 OK (Render Dashboard)"]
    CookieCheck -->|NO (Unauthenticated)| AuthBypass["CRITICAL FLAW:\n'if user and user.get(role) != ...' is skipped!\nFalls back to 'user or admin'\nRETURNS 200 OK TO ANONYMOUS USER!"]

    %% API Endpoints
    RouteCheck -->|POST /api/admin/*\nPOST /api/accounts/*\nPOST /api/branch/*| APIEndpoints["Mutating API Endpoints\n(21 Endpoints in server.py)"]
    APIEndpoints --> APIBypass["CRITICAL FLAW:\nNO Cookie Check\nNO get_current_user\nNO Role Guard\nDirect Execution on Database!"]

    %% License Verification Point
    RouteCheck -->|Any Business API\n(Invoice, Payout, Rate, Branch)| LicCheck{"License Verified?"}
    LicCheck -->|Verification Flow| NoLicCheck["CRITICAL FLAW:\nZERO License Checking Logic in any Business Endpoint!\nSoftware treats unverified license as ACTIVE forever."]
```

---

## SECTION 4 — FINDINGS AND EVIDENCE

### FINDING-01: Unauthenticated Full Access to Administrative and Operational Dashboards
- **Finding ID:** SEC-01
- **Severity:** CRITICAL
- **Affected File & Functions:** [`server.py`](file:///c:/projects/tests/commoditi%20software/server.py)
  - `admin_dashboard_view` (Lines 352–360)
  - `admin_settings_view` (Lines 2052–2060)
  - `accounts_dashboard_view` (Lines 664–670)
  - `accounts_settings_view` (Lines 2281–2286)
  - `branch_dashboard_view` (Lines 1052–1060)
  - `branch_stock_view` (Lines 1905–1912)
  - `branch_settings_view` (Lines 2335–2343)
- **What the Code Currently Does:**
  ```python
  def admin_dashboard_view(request: Request):
      user = get_current_user(request)
      if user and user.get("role") != "SUPER_ADMIN":
          # Only redirects if a user cookie exists AND role is not SUPER_ADMIN
          if user.get("role") == "ACCOUNTANT_HQ":
              return RedirectResponse(url="/accounts/dashboard", status_code=303)
          else:
              b_id = user.get("branch_id") or "br-chikhali"
              return RedirectResponse(url=f"/branch/dashboard?branch_id={b_id}", status_code=303)
      logged_in_user = user or {"username": "admin", "full_name": "Vikramaditya Singhal (Owner)", "role": "SUPER_ADMIN"}
      # Renders admin_dashboard.html with 200 OK!
  ```
- **Evidence:** Executing `client.get("/admin/dashboard")` without sending any session cookie returns `HTTP 200 OK` and renders the Super Admin dashboard containing enterprise financial metrics, P&L, and branch lists.
- **Exploitation:** Any person on the local network or accessing `http://127.0.0.1:8080/admin/dashboard` directly in an incognito window or via a script receives complete administrative visibility without entering a username or password.
- **Business Impact:** Total loss of confidentiality and governance. Sensitive farmer balances, turnover, ledger records, and corporate credentials are exposed to any unauthorized viewer.
- **Recommended Fix:** Enforce a strict session requirement dependency (`require_role("SUPER_ADMIN")`). If `user is None`, immediately redirect to `/login` with `status_code=303`. Never supply a default fallback admin dictionary.
- **Reproducible Safe Test:**
  ```python
  client = TestClient(app, follow_redirects=False)
  response = client.get("/admin/dashboard")
  assert response.status_code == 303, f"Expected redirect to /login, got {response.status_code}"
  assert response.headers["location"] == "/login"
  ```

---

### FINDING-02: Zero Authentication and Authorization on Mutating API Endpoints
- **Finding ID:** SEC-02
- **Severity:** CRITICAL
- **Affected File & Functions:** [`server.py`](file:///c:/projects/tests/commoditi%20software/server.py)
  - `api_admin_update_all_staff` (Line 2112)
  - `api_admin_update_credentials` (Line 2193)
  - `api_admin_add_branch` (Line 554)
  - `api_admin_toggle_branch` (Line 578)
  - `api_admin_add_user` (Line 589)
  - `api_accounts_set_rate` (Line 796)
  - `api_accounts_process_rtgs` (Line 861)
  - `api_accounts_receive_outward_payment` (Line 920)
  - `api_branch_create_invoice` (Line 1308)
  - `api_branch_create_outward` (Line 1581)
  - `api_branch_edit_farmer` (Line 1795)
  - `api_save_admin_settings` (Line 2246)
  - `api_save_accounts_settings` (Line 2302)
  - `api_save_branch_settings` (Line 2371)
  - `api_cashier_disburse_payout` (Line 2521)
- **What the Code Currently Does:**  
  Endpoints declare parameters using `Form(...)` and immediately open a database connection to execute SQL queries. Not a single line inspects `request.cookies`, calls `get_current_user`, or checks permissions.
- **Evidence:** Source code analysis of `api_admin_update_all_staff` shows signature `def api_admin_update_all_staff(acc_name: str = Form(...), ...)`. It does not even accept the `Request` object.
- **Exploitation:** Any script or rogue client can send an HTTP POST request to `/api/admin/staff/update-all` with arbitrary passwords, overwriting all staff credentials in SQLite instantly. Anyone can post to `/api/accounts/rates` to manipulate commodity prices.
- **Business Impact:** Complete integrity collapse. Unauthorized financial transactions, unauthorized cash drawer disbursements, and total denial of service via credential hijacking.
- **Recommended Fix:** Apply FastAPI `Depends(require_user)` and `Depends(require_role(...))` dependencies to every `/api/*` route. Derive the actor's user ID and assigned branch strictly from the validated session, rejecting unauthenticated requests with `HTTP 401 Unauthorized` or `403 Forbidden`.
- **Reproducible Safe Test:**
  ```python
  client = TestClient(app, follow_redirects=False)
  response = client.post("/api/admin/staff/update-all", data={"acc_name": "Test", "acc_username": "acc", "acc_phone": "1", "chk_name": "Test", "chk_username": "chk", "chk_phone": "1", "vrv_name": "Test", "vrv_username": "vrv", "vrv_phone": "1", "dhd_name": "Test", "dhd_username": "dhd", "dhd_phone": "1"})
  assert response.status_code in (401, 403), f"Expected 401/403, got {response.status_code}"
  ```

---

### FINDING-03: Complete Absence of Cryptographic Commercial License Verification
- **Finding ID:** SEC-03
- **Severity:** CRITICAL
- **Affected Files:** [`server.py`](file:///c:/projects/tests/commoditi%20software/server.py), [`database.py`](file:///c:/projects/tests/commoditi%20software/database.py), [`templates/setup.html`](file:///c:/projects/tests/commoditi%20software/templates/setup.html)
- **What the Code Currently Does:**
  1. The database seeds unverified strings in `system_settings`:
     `("SUPER_ADMIN", "GLOBAL", "license_status", "Active (Pro Tier - 3 Branches)")`,
     `("SUPER_ADMIN", "GLOBAL", "license_key", "RST-PRO-2026-MH3B-89A12F")`,
     `("SUPER_ADMIN", "GLOBAL", "license_valid_until", "31-March-2027")`.
  2. In `server.py`, the only license-related gate is `is_system_setup_done()` (L102), which merely queries `SELECT setting_value FROM system_settings WHERE setting_key='is_setup_completed'`.
  3. No cryptographic algorithm (Ed25519, RSA, HMAC) verifies the license string.
  4. There is no check comparing the current system date with `license_valid_until`.
  5. There is no code checking branch counts against `license_branch_limit` when adding branches.
- **Evidence:** Source code search across the entire repository reveals zero occurrences of public-key signature verification libraries (e.g. `cryptography.hazmat.primitives.asymmetric`).
- **Exploitation:** Any customer can edit the SQLite database, enter any string in `/setup`, or run the application past 2027 without paying for renewal.
- **Business Impact:** Complete inability to enforce commercial software licensing, subscription billing, or tier restrictions. Zero intellectual property protection.
- **Recommended Fix:** Implement asymmetric digital signature licensing (Ed25519). The vendor holds the private signing key offline. The distributed application embeds only the vendor's public verification key. The license token contains a signed JSON payload with `licensee_name`, `license_id`, `tier`, `max_branches`, `issued_at`, and `expires_at`. The application validates the signature and constraints on startup, during login, and during branch creation.
- **Reproducible Safe Test:**
  ```python
  # Attempting to load application with tampered or expired license token must raise a LicensingError
  # and block access to all business operations.
  ```

---

### FINDING-04: Unrestricted Public `/setup` Page Enables Unauthenticated Admin Account Hijacking
- **Finding ID:** SEC-04
- **Severity:** CRITICAL
- **Affected Files:** [`server.py`](file:///c:/projects/tests/commoditi%20software/server.py) (Lines 155–288), [`templates/login.html`](file:///c:/projects/tests/commoditi%20software/templates/login.html) (Line 115)
- **What the Code Currently Does:**
  - `login.html` features an open link: `<a href="/setup">Owner Setup & License Activation →</a>`.
  - `GET /setup` queries the database and pre-fills all current user usernames and mobile numbers.
  - `POST /setup` accepts new passwords for `SUPER_ADMIN`, `ACCOUNTANT_HQ`, and branch cashiers, commits them to the database, and returns the newly generated credentials in plain text.
  - Neither `setup_view` nor `setup_post` checks whether setup was already completed.
- **Evidence:** In `server.py` L155–288, there is no check for `is_system_setup_done()` inside `setup_view` or `setup_post`. Both endpoints execute for any incoming request.
- **Exploitation:** An unauthorized visitor opens `http://127.0.0.1:8080/setup`, inputs their own password in the `owner_password` field, and clicks submit. The real owner is instantly locked out, and the attacker takes full ownership of the system.
- **Business Impact:** Complete unauthorized system takeover.
- **Recommended Fix:**
  1. Once `is_setup_completed == '1'`, permanently disable `/setup` and return `404 Not Found` or redirect to `/login`.
  2. Initial setup must require an offline **Installation Setup Token** generated once during installation, or must be performed via a command-line setup wizard (`python setup_mandi.py --init`).
  3. Remove the setup link from `login.html`.
- **Reproducible Safe Test:**
  ```python
  client = TestClient(app, follow_redirects=False)
  # When setup is completed in DB:
  res = client.get("/setup")
  assert res.status_code in (303, 404), f"Setup page must not be accessible post-initialization, got {res.status_code}"
  ```

---

### FINDING-05: Hardcoded Fallback Session Secret and Non-Expiring Session Tokens
- **Finding ID:** SEC-05
- **Severity:** HIGH
- **Affected File:** [`server.py`](file:///c:/projects/tests/commoditi%20software/server.py) (Lines 74–96)
- **What the Code Currently Does:**
  ```python
  SESSION_SECRET = os.environ.get("SESSION_SECRET", "rajeshri-shahu-mandi-erp-2026-cresconic-secret")
  def create_session_token(username: str, role: str, branch_id: str = "") -> str:
      payload = f"{username}|{role}|{branch_id}"
      sig = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
      token_raw = f"{payload}|{sig}"
      return base64.urlsafe_b64encode(token_raw.encode("utf-8")).decode("utf-8")
  ```
- **Evidence:** The secret string is committed to source control and packaged inside the PyInstaller binary. The payload contains only `username|role|branch_id`, with no timestamp, no expiry (`exp`), and no unique session identifier (`jti`).
- **Exploitation:**
  1. Any attacker who decompiles the binary or views the repository can sign their own cookie as `admin|SUPER_ADMIN||<signature>`.
  2. Captured session cookies never expire. Logging out only instructs the browser to delete the cookie; the token itself remains mathematically valid indefinitely.
- **Business Impact:** Permanent session hijacking and trivial privilege escalation to Super Admin.
- **Recommended Fix:**
  1. Generate a cryptographically random `SESSION_SECRET` on first run and store it in an access-restricted local file or encrypted environment file.
  2. Include an explicit expiration timestamp (`exp`) and creation timestamp (`iat`) in the token payload.
  3. Store active session IDs in a `sessions` table in SQLite so sessions can be revoked on logout or password change.
- **Reproducible Safe Test:**
  ```python
  # Craft token using hardcoded secret:
  import hmac, hashlib, base64
  secret = "rajeshri-shahu-mandi-erp-2026-cresconic-secret"
  payload = "forged_admin|SUPER_ADMIN|"
  sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
  token = base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode()
  user = verify_session_token(token)
  assert user is not None, "Vulnerability confirmed: arbitrary token forged using default secret"
  ```

---

### FINDING-06: Un-salted Single-Round SHA-256 Password Hashing
- **Finding ID:** SEC-06
- **Severity:** HIGH
- **Affected File:** [`database.py`](file:///c:/projects/tests/commoditi%20software/database.py) (Lines 35–36)
- **What the Code Currently Does:**
  ```python
  def hash_password(pwd: str) -> str:
      return hashlib.sha256(pwd.encode('utf-8')).hexdigest()
  ```
- **Evidence:** Inspection of `database.py` line 35 confirms standard `hashlib.sha256` without per-user salt or computational work factor.
- **Exploitation:** Standard SHA-256 computes billions of hashes per second on modern consumer GPUs. If the database file is accessed from a backup or local disk, password hashes for all users can be cracked almost instantaneously using precomputed rainbow tables or dictionary attacks.
- **Business Impact:** High exposure of credentials across systems due to common password re-use.
- **Recommended Fix:** Migrate password hashing to `Argon2id` (RFC 9106) via the `argon2-cffi` package, or use `bcrypt` / `PBKDF2-HMAC-SHA256` with at least 600,000 iterations and per-user unique random 16-byte salts.
- **Reproducible Safe Test:**
  ```python
  # Verify that hash_password uses a memory-hard algorithm with unique salt rather than deterministic sha256
  h1 = hash_password("mypassword")
  h2 = hash_password("mypassword")
  assert h1 != h2, "Vulnerability confirmed: password hashing is deterministic and lacks random salt"
  ```

---

### FINDING-07: Hardcoded Default Credentials and Seed Data in Production Paths
- **Finding ID:** SEC-07
- **Severity:** HIGH
- **Affected Files:** [`database.py`](file:///c:/projects/tests/commoditi%20software/database.py) (Lines 426–444), [`templates/setup.html`](file:///c:/projects/tests/commoditi%20software/templates/setup.html)
- **What the Code Currently Does:**
  - `seed_initial_data()` in `database.py` seeds known default passwords:
    `admin123` for `admin`, `acc123` for `accountant`, `chk123` for `chikhali_cashier`, `vrv123` for `varvand_cashier`, `dhd123` for `dhad_cashier`.
  - `setup.html` renders pre-filled inputs containing `admin`, `acc123`, `chk123`, `vrv123`, `dhd123`.
- **Evidence:** Lines 426–444 of `database.py` explicitly list plaintext strings in calls to `hash_password(...)`.
- **Exploitation:** Any operator who deploys the software without explicitly resetting every single password leaves well-known backdoor accounts open.
- **Business Impact:** Unauthorized entry by internal or external actors using known factory defaults.
- **Recommended Fix:** Never seed active user passwords in production initialization. If seeds are needed for automated testing, isolate them strictly to test suites (`tests/conftest.py` or test fixtures). In production, enforce mandatory password initialization during secure provisioning.

---

### FINDING-08: Client-Controlled `branch_id` and Lack of Branch Limit Enforcement
- **Finding ID:** SEC-08
- **Severity:** HIGH
- **Affected File & Functions:** [`server.py`](file:///c:/projects/tests/commoditi%20software/server.py)
  - `api_branch_create_invoice` (Line 1308)
  - `api_branch_create_outward` (Line 1581)
  - `api_cashier_disburse_payout` (Line 2521)
  - `api_admin_add_branch` (Line 554)
- **What the Code Currently Does:**
  - In `api_branch_create_invoice`, `branch_id: str = Form(...)` is trusted directly from the client form payload. The backend never validates whether the authenticated user is actually assigned to that `branch_id`.
  - In `api_admin_add_branch`, new branches are inserted into the `branches` table without checking whether the total branch count exceeds `license_branch_limit`.
- **Evidence:** Source code analysis shows `branch_id` taken from form inputs without comparing against `user.get("branch_id")`.
- **Exploitation:**
  1. A cashier logged into Chikhali Yard can submit an invoice specifying `branch_id="br-varvand"`, corrupting Varvand's physical stock ledger and cash drawer.
  2. An administrator can add an arbitrary number of branches, circumventing the commercial license tier.
- **Business Impact:** Cross-branch data contamination, financial reconciliation discrepancies, and commercial tier limit evasion.
- **Recommended Fix:**
  1. In all branch endpoints, discard client-supplied `branch_id` for branch operators and derive the branch strictly from the authenticated session: `effective_branch_id = session_user["branch_id"]`.
  2. In `api_admin_add_branch`, query `SELECT count(*) FROM branches WHERE is_active=1` and abort with `HTTP 403 Forbidden` if the count meets or exceeds the cryptographically verified `max_branches` allowed by the license.

---

### FINDING-09: Conflation of License Issuer and Software Customer Roles
- **Finding ID:** SEC-09
- **Severity:** MEDIUM
- **Affected Files:** [`templates/setup.html`](file:///c:/projects/tests/commoditi%20software/templates/setup.html), [`templates/admin_settings.html`](file:///c:/projects/tests/commoditi%20software/templates/admin_settings.html)
- **What the Code Currently Does:** The application treats the customer (the business owner) as the entity that inputs and defines the license key and its parameters.
- **Evidence:** `setup.html` includes an editable `<input name="license_key">` field that accepts any text from the user.
- **Exploitation:** There is no actual licensing control. The customer self-proves their license status.
- **Business Impact:** The vendor has zero technical capability to monetize licenses, enforce expirations, or issue signed renewals.
- **Recommended Fix:** Completely decouple the software vendor from the customer. The vendor operates a separate, off-application keypair. The customer receives a signed license file or activation token (`license.lic`) and uploads/pastes it into the application. The application verifies the signature against the embedded public key.

---

### FINDING-10: Permissive CORS Configuration and Missing Security Headers
- **Finding ID:** SEC-10
- **Severity:** MEDIUM
- **Affected File:** [`server.py`](file:///c:/projects/tests/commoditi%20software/server.py) (Lines 49–55)
- **What the Code Currently Does:**
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **Evidence:** `server.py` line 51 allows all origins with credentials.
- **Exploitation:** A user running the application on `http://127.0.0.1:8080` who visits an arbitrary external website could be targeted by cross-origin requests that execute authenticated actions against the local ERP.
- **Business Impact:** Potential Cross-Site Request Forgery (CSRF) and credential compromise.
- **Recommended Fix:** Restrict `allow_origins` strictly to local origins (or remove CORS middleware entirely if the frontend is served solely by FastAPI), and add standard security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy`).

---

## SECTION 5 — LICENSING DESIGN ASSESSMENT

### 5.1 Clear Separation of Responsibilities
To transition this ERP into a legitimate commercial product, the architecture must strictly enforce four distinct operational stages:

```
[Software Vendor (Offline)]  ---> Generates Signed License Token (Ed25519)
                                          │
                                          ▼
[Customer / Super Admin]     ---> Pastes / Uploads Token into Application
                                          │
                                          ▼
[ERP Application Runtime]    ---> Verifies Signature via Vendor Public Key
                                          │
                                          ▼
[Enforcement Engine]         ---> Checks Expiry, Max Branches, Permitted Tier
```

| Operational Stage | Actor | Permitted Capabilities | Prohibited Capabilities |
| :--- | :--- | :--- | :--- |
| **1. License Issuance** | Software Vendor (Authorized Issuer) | Mint signed licenses, set validity dates, specify tier, set branch limits, hold private key | Never run inside client application; private key never distributed |
| **2. License Activation**| Super Admin / Business Owner | Upload/input signed license token; view active license status and expiry date | Cannot edit tier, change branch limit, extend expiry, or mint licenses |
| **3. License Validation**| Mandi ERP Backend Engine | Verify digital signature against embedded public key, enforce branch limits, enforce expiration | Cannot alter license parameters; fails closed on invalid/expired signatures |
| **4. Business Administration**| Super Admin / Business Owner | Manage staff accounts, configure business PAN/GSTIN, view audit logs | Cannot access private vendor keys or bypass license verification |

### 5.2 Recommended Cryptographic License Architecture
1. **Asymmetric Algorithm:** **Ed25519** (Edwards-curve Digital Signature Algorithm).  
   - Highly performant, compact signatures (64 bytes), compact public keys (32 bytes).
   - Immune to timing attacks and does not require complex padding schemes.
2. **Key Storage:**
   - **Private Signing Key:** Kept securely on the vendor's licensing server or offline air-gapped machine. Never present in the codebase, repo, or client executable.
   - **Public Verification Key:** Embedded directly as a constant string in the compiled application backend.
3. **License Payload Structure (Signed JSON Token):**
   ```json
   {
     "licensee_id": "ORG-RST-2026-MH",
     "licensee_name": "Rajeshri Shahu Trading Co.",
     "product": "SHAHU_MANDI_ERP",
     "tier": "PRO",
     "max_branches": 3,
     "issued_at": "2026-04-01T00:00:00Z",
     "expires_at": "2027-03-31T23:59:59Z",
     "features": ["MULTI_BRANCH", "RTGS_DESK", "OUTWARD_CHALLAN"]
   }
   ```
4. **Token Format:** `base64url(payload) . base64url(ed25519_signature)`.

### 5.3 Tamper Resistance & Threat Model for Local Applications
- **Database Modification:** If an operator manually edits SQLite (`UPDATE system_settings SET setting_value='999' WHERE setting_key='license_branch_limit'`), the application recalculates the signature on the stored license token. Because the signature does not match the altered data, the application **fails closed** and blocks operation.
- **Clock Manipulation:** To counter local system clock rollbacks, the application maintains a `last_seen_timestamp` in the database updated on every transaction. If `current_system_time < last_seen_timestamp`, the application detects time manipulation and halts.
- **Practical Boundary:** In a locally installed Python/PyInstaller application, a sophisticated reverse engineer with administrative access to their own OS can theoretically patch bytecode. However, asymmetric signature verification with code obfuscation and signature integrity checks raises the barrier from trivial text editing to complex binary reverse engineering, satisfying commercial software standards.

---

## SECTION 6 — ROLE AND PERMISSION MATRIX

The table below contrasts **Intended Commercial Policy** with the **Actual Current Enforcement** discovered during the audit:

| Feature / Endpoint | Super Admin (Owner) | Central Accountant | Branch Cashier | Actual Server-Side Enforcement Discovered |
| :--- | :--- | :--- | :--- | :--- |
| **Initial Setup (`/setup`)** | Restricted First-Run | DENIED | DENIED | **FAILED:** Completely open to the public; unauthenticated. |
| **Commercial License Minting** | DENIED (Vendor Only)| DENIED | DENIED | **FAILED:** Conflated; user inputs plain string. |
| **Commercial License Activation** | ALLOWED | DENIED | DENIED | **FAILED:** No role check; unauthenticated POST. |
| **Super Admin Dashboard (`/admin/dashboard`)**| ALLOWED | DENIED | DENIED | **FAILED:** 200 OK to unauthenticated users; redirects logged-in accountant/cashier. |
| **Super Admin Settings (`/admin/settings`)** | ALLOWED | DENIED | DENIED | **FAILED:** 200 OK to unauthenticated users. |
| **Manage Staff Logins (`/api/admin/staff/update-all`)**| ALLOWED | DENIED | DENIED | **FAILED:** Zero authentication; open to any HTTP POST. |
| **Create Branches (`/api/admin/branches`)**| ALLOWED (Up to License Limit) | DENIED | DENIED | **FAILED:** Zero authentication; no branch limit check. |
| **Central Accounts Dashboard (`/accounts/dashboard`)**| ALLOWED (View) | ALLOWED | DENIED | **FAILED:** 200 OK to unauthenticated users. |
| **Update Mandi Daily Rates (`/api/accounts/rates`)**| ALLOWED | ALLOWED | DENIED | **FAILED:** Zero authentication; open to any HTTP POST. |
| **Approve Rate Overrides (`/api/accounts/rate-overrides/action`)**| ALLOWED | ALLOWED | DENIED | **FAILED:** Zero authentication; open to any HTTP POST. |
| **Process RTGS Disbursal (`/api/accounts/rtgs/process`)**| ALLOWED | ALLOWED | DENIED | **FAILED:** Zero authentication; open to any HTTP POST. |
| **Receive Outward Payment (`/api/accounts/outward/receive-payment`)**| ALLOWED | ALLOWED | DENIED | **FAILED:** Zero authentication; open to any HTTP POST. |
| **Branch Dashboard (`/branch/dashboard`)**| ALLOWED (All Yards)| DENIED | ALLOWED (Assigned Yard Only) | **FAILED:** 200 OK to unauthenticated users. |
| **Create Purchase Invoice (`/api/branch/invoices/create`)**| ALLOWED | DENIED | ALLOWED (Assigned Yard Only) | **FAILED:** Zero authentication; accepts client `branch_id`. |
| **Immediate Cash Payout (`/api/cashier/payout`)**| ALLOWED | DENIED | ALLOWED (Assigned Yard Only) | **FAILED:** Zero authentication; open to any HTTP POST. |
| **Create Outward Dispatch (`/api/branch/outward/create`)**| ALLOWED | DENIED | ALLOWED (Assigned Yard Only) | **FAILED:** Zero authentication; accepts client `branch_id`. |
| **Edit Farmer Record (`/api/branch/farmers/edit`)**| ALLOWED | ALLOWED | ALLOWED (Assigned Yard Only) | **FAILED:** Zero authentication; open to any HTTP POST. |

---

## SECTION 7 — ATTACK SCENARIO RESULTS

| Attack Scenario | Vulnerability Status | Evidence & Actual Result |
| :--- | :--- | :--- |
| **1. Direct `/setup` Access Post-Initialization** | **DEMONSTRABLY VULNERABLE** | Accessing `GET /setup` returns `HTTP 200` with existing staff identities. Submitting `POST /setup` updates passwords and license without error. |
| **2. Unauthenticated Mutating API Requests** | **DEMONSTRABLY VULNERABLE** | Sending `POST /api/admin/staff/update-all` or `POST /api/accounts/rates` without cookies executes successfully and modifies database state. |
| **3. Unauthorized Owner Account Creation / Reset** | **DEMONSTRABLY VULNERABLE** | Any visitor can send a POST request to `/setup` or `/api/admin/users` with `role="SUPER_ADMIN"` and set a new password. |
| **4. Role Manipulation via Cookie Tampering** | **DEMONSTRABLY VULNERABLE** | The fallback `SESSION_SECRET` is known (`rajeshri-shahu-mandi-erp-2026-cresconic-secret`), allowing attackers to generate valid `SUPER_ADMIN` tokens. |
| **5. Cross-Branch Data Manipulation (`branch_id` tampering)** | **DEMONSTRABLY VULNERABLE** | Inward and outward APIs accept `branch_id` from the form payload without validating it against the session user's assigned branch. |
| **6. Arbitrary License Key Insertion** | **DEMONSTRABLY VULNERABLE** | The backend accepts any string in `license_key` and hardcodes `license_status = "Active"`. |
| **7. License Expiry Bypass via System Clock or Date Inaction** | **DEMONSTRABLY VULNERABLE** | The backend has zero date-comparison logic for `license_valid_until`. The app operates indefinitely after expiration. |
| **8. Default Factory Credentials Exploitation** | **DEMONSTRABLY VULNERABLE** | Default passwords (`admin123`, `acc123`, `chk123`, `vrv123`, `dhd123`) are pre-seeded in the database and pre-filled in frontend forms. |

---

## SECTION 8 — PRIORITIZED REMEDIATION PLAN

### Priority 0: Immediate Access Control & Licensing Bypasses (Must be resolved before any deployment)
1. **Fix View Route Fallbacks (`server.py`):**
   - Eliminate all `logged_in_user = user or {"username": "admin", ...}` patterns.
   - If `user is None`, immediately redirect unauthenticated requests to `/login`.
2. **Lock Down Mutating APIs (`server.py`):**
   - Create a reusable FastAPI dependency `get_authenticated_user` and role guards: `require_super_admin`, `require_accountant`, `require_cashier`.
   - Apply dependencies to all 21 mutating `POST` routes.
3. **Decommission Public `/setup` Page (`server.py`, `login.html`):**
   - If `is_system_setup_done()` is True, `/setup` must return `HTTP 404 Not Found`.
   - Remove the setup hyperlink from `login.html`.
   - Implement initial provisioning via a secure one-time setup secret or offline CLI wizard.

### Priority 1: Cryptographic Licensing & Branch Enforcement
1. **Implement Ed25519 License Validation Service (`licensing.py`):**
   - Embed vendor public verification key as a constant.
   - Implement `verify_license_token(token_str)` to validate signature, expiration timestamp, licensee name, and tier.
2. **License Gate Middleware / Dependency:**
   - Add a global check verifying that an active, cryptographically valid license exists before serving any non-setup, non-login route.
3. **Enforce Branch Count Limits (`server.py`):**
   - In `api_admin_add_branch`, count existing active branches and block creation if `count >= license.max_branches`.
4. **Enforce Strict Branch Scoping on Transactions (`server.py`):**
   - Force all branch purchase, payout, and outward endpoints to use `user["branch_id"]` from the verified session, rejecting client-submitted overrides.

### Priority 2: Cryptographic Hardening & Database Hygiene
1. **Upgrade Password Hashing (`database.py`):**
   - Migrate `hash_password` from plain SHA-256 to `Argon2id` or salted `PBKDF2-HMAC-SHA256` (600,000 iterations).
   - Implement automatic re-hashing upon successful login for legacy hashes.
2. **Dynamic Session Secret & Token Expiration (`server.py`):**
   - Generate a random 32-byte `SESSION_SECRET` on initial deployment stored in `.env` (file permissions 0600).
   - Add `exp` (12-hour validity) and `jti` to session tokens.
   - Implement a `sessions` table in SQLite for instant server-side revocation on logout.
3. **Purge Seed Credentials (`database.py`):**
   - Remove hardcoded default passwords from `database.py`. Users must be provisioned during initial setup or admin creation.

### Priority 3: Automated Quality & Regression Gates
1. **Implement License & Role Regression Test Suite (`tests/test_licensing_security.py`):**
   - Test expired license rejection.
   - Test forged license signature rejection.
   - Test branch limit enforcement.
   - Test unauthenticated API rejection (401/403).
   - Test cross-branch cashier access rejection.
2. **Desktop Packaging Hardening:**
   - Ensure compiled PyInstaller build bundles only necessary assets and strips debug symbols.

---

## SECTION 9 — ACCEPTANCE CRITERIA FOR FUTURE FIX

Before this ERP can be certified for commercial distribution, the following 14 automated acceptance criteria must pass:

1. **Unlicensed Application Access Block:**  
   Calling any authenticated dashboard or business API without an activated license returns an explicit `LicensingError` and redirects to the license activation screen.
2. **Cryptographic Signature Verification:**  
   Altering even a single character in the license token causes signature verification to fail immediately.
3. **Expiry Date Enforcement:**  
   A license token with an `expires_at` date in the past is rejected, disabling transaction creation while permitting read-only audit log export.
4. **Branch Ceiling Enforcement:**  
   Attempting to activate a 4th branch on a 3-branch license returns `HTTP 403 Forbidden: License branch limit reached`.
5. **Secure Initial Provisioning:**  
   `/setup` cannot be accessed without providing an installation setup secret generated at installation time.
6. **Post-Setup Lockdown:**  
   Once the owner account is initialized, calling `GET /setup` or `POST /setup` returns `HTTP 404 Not Found`.
7. **Strict Unauthenticated Route Protection:**  
   `GET /admin/dashboard`, `GET /admin/settings`, `GET /accounts/dashboard`, and `GET /branch/dashboard` return `HTTP 303 Redirect to /login` when called with no cookies.
8. **Strict API Authentication & Role Guarding:**  
   Direct HTTP `POST` requests to any mutating `/api/*` endpoint without a valid signed session cookie return `HTTP 401 Unauthorized`.
9. **Role Isolation Enforcement:**  
   An authenticated accountant attempting to access `/admin/dashboard` or `/api/admin/staff/update-all` receives `HTTP 403 Forbidden`.
10. **Branch Isolation Enforcement:**  
    A cashier authenticated to `br-chikhali` attempting to create an invoice or view stock for `br-varvand` is blocked server-side with `HTTP 403 Forbidden`.
11. **Client Parameter Tampering Immunity:**  
    Submitting `branch_id="br-varvand"` in a form body while logged in as a Chikhali cashier is ignored; the server binds the record strictly to `br-chikhali`.
12. **Cryptographic Password Security:**  
    Database audit confirms all passwords stored in `users.password_hash` use salted `Argon2id` or salted `PBKDF2`, and zero plaintext passwords exist.
13. **Session Token Expiration & Revocation:**  
    Session tokens older than 12 hours are rejected as expired. Calling `/logout` invalidates the session server-side.
14. **Business Continuity:**  
    All 58 existing functional tests (inward calculations, outward challans, RTGS workflows, mandi cess, Income Tax Section 269ST/40A(3) checks) continue to pass 100% OK after applying security controls.

---

## SECTION 10 — FINAL RECOMMENDATION

### Verdict: **RETAIN AND REPAIR (TARGETED SECURITY REFACTORING)**

**Justification:**
A total rewrite of this application is **unnecessary and discouraged**. The core architecture is sound:
1. The domain calculation engine ([`calculations.py`](file:///c:/projects/tests/commoditi%20software/calculations.py)) is clean, well-tested, and accurately handles APMC mandi statutory regulations.
2. The database schema ([`database.py`](file:///c:/projects/tests/commoditi%20software/database.py)) enforces SQLite WAL mode and foreign key constraints effectively.
3. The desktop integration ([`desktop_app.py`](file:///c:/projects/tests/commoditi%20software/desktop_app.py)) with Microsoft Edge WebView2 provides a clean native Windows experience.
4. The user interface design tokens ([`static/theme.css`](file:///c:/projects/tests/commoditi%20software/static/theme.css)) follow a clean, accessible card-first system.

The defects identified during this audit are strictly concentrated in **middleware authentication**, **API route guarding**, **session lifecycle**, and the **licensing verification layer**. 

These defects can be cleanly repaired through targeted refactoring of [`server.py`](file:///c:/projects/tests/commoditi%20software/server.py) and [`database.py`](file:///c:/projects/tests/commoditi%20software/database.py), accompanied by a dedicated licensing verification module ([`licensing.py`]), without disrupting working domain calculations or database models.

---
*Report generated and verified against live source code. Zero application code or database records were modified during this audit.*
