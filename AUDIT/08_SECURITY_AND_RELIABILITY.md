# Rajarshi Shahu Trading — Mandi ERP v1.0
# Audit Report 08: Application Security, Credential Hygiene & Financial Integrity Audit

**Document Reference:** `AUDIT/08_SECURITY_AND_RELIABILITY.md`  
**System Evaluated:** Rajarshi Shahu Mandi ERP & Mobile QC Tracker  
**Target Codebase:**
- `commoditi software/server.py` (FastAPI Central Server & Gateway)
- `commoditi software/database.py` (Database Layer, Cryptography & Sessions)
- `commoditi software/supabase_sync.py` (Supabase Cloud Ingestion Engine)
- `commoditi software/calculations.py` (Financial Math & Tax Compliance Rules)
- `commoditi software/templates/` (Jinja2 HTML Templates)
- `mandi-erp-tracker/` (`api/inspections-submit.js`, `app.html`, `index.html`)

**Audit Execution Date:** November 3, 2026  
**Auditor:** Lead Security Architect & Business Workflow Auditor  
**Scope:** Application Security (AppSec), OWASP Top 10 (2021/2025), Cryptographic Key Hygiene, Authentication & Session Security, Role-Based Access Control (RBAC), Injection Defenses, Cross-Site Scripting (XSS), Financial Transaction Concurrency & Race Conditions.

---

## 1. Executive Summary & Security Posture Scorecard

An exhaustive security and data reliability assessment was conducted across the source code, API handlers, client applications, and database definitions of the Rajarshi Shahu Mandi ERP ecosystem.

The core desktop/server application demonstrates positive security engineering in several areas:
- Server-side password hashing uses modern **PBKDF2-HMAC-SHA256 with 600,000 iterations** and 16-byte cryptographically random salts, coupled with an automated upgrade path for legacy hashes.
- SQL parameterization with placeholder tuples (`?`) is enforced consistently across operational endpoints.
- Basic security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`) are injected via HTTP middleware.

However, the audit discovered **critical security vulnerabilities, severe credential exposures, and race-condition risks** across the cloud edge handlers, client trackers, and session lifecycle:

```
+--------------------------------------------------------------------------------------------------+
|                                    SECURITY POSTURE SCORECARD                                    |
+--------------------------------------------------------------------------------------------------+
| Security Dimension                  | Score (0-100) | Risk Level | Primary Vulnerability         |
+-------------------------------------+---------------+------------+-------------------------------+
| Credential & Secret Hygiene        |      22       |  CRITICAL  | Hardcoded service_role JWT    |
| Authentication & Identity           |      38       |  CRITICAL  | Plaintext staff credentials   |
| API Authorization & RBAC            |      54       |    HIGH    | Unauthenticated PII leakage   |
| Client-Side & Template Security     |      48       |    HIGH    | DOM XSS in cashier modal      |
| Financial Integrity & Concurrency   |      42       |    HIGH    | Missing idempotency tokens    |
| Cloud Architecture & Storage Hygiene|      50       |   MEDIUM   | Multi-MB base64 DB storage    |
+-------------------------------------+---------------+------------+-------------------------------+
```

### Critical Takeaways:
1. **Cloud Database Takeover (AUD-SEC-001):** A valid Supabase `service_role` JWT is embedded as a fallback literal in `mandi-erp-tracker/api/inspections-submit.js:17`. Possession of this token grants unrestricted administrative access to the entire cloud PostgreSQL instance, bypassing all Row Level Security (RLS) policies.
2. **Client-Side Credential Exposure (AUD-SEC-002):** The client-side PWA `app.html:526-531` contains hardcoded plaintext usernames and passwords (`admin: admin123`, `qc_chikhali: qc123`) in public JavaScript. Anyone viewing page source can harvest staff credentials, or bypass authentication entirely via `localStorage`.
3. **Unauthenticated Farmer PII Harvester (AUD-SEC-003):** The endpoint `/api/farmers/search` lacks authentication or rate limiting. Any unauthenticated caller can scrape farmer identities, mobile numbers, villages, khasra land records, and vehicle numbers.
4. **DOM Cross-Site Scripting (AUD-SEC-005):** Unsanitized farmer profile data is concatenated directly into template literals and rendered via `.innerHTML` in `branch_dashboard.html`, allowing stored script injection in the cashier's active session.
5. **Double-Spend & Sequence Race Conditions (AUD-SEC-006):** Inward purchase generation lacks idempotency keys or transaction tokens. Sequential invoice numbers are computed via non-atomic `SELECT count(*) + 1`, creating race condition collisions or duplicate cash payouts on network retries.

---

## 2. Threat Model & Attack Surface Map

```
                                      [EXTERNAL INTERNET]
                                               |
                   +---------------------------+---------------------------+
                   |                                                       |
                   v                                                       v
      +------------------------+                              +------------------------+
      |  Vercel Edge Functions |                              | Public PWA Tracker     |
      |  api/inspections-      |                              | mandi-erp-tracker/     |
      |  submit.js             |                              | app.html               |
      +------------------------+                              +------------------------+
          |               |                                                |
          | (Bypasses     | (Embedded service_role key)                    | (Client-side auth
          |  RLS)         v                                                |  Plaintext passwords)
          |    +------------------------+                                  v
          +--->| Supabase Cloud DB      |<---------------------------------+
               | (PostgreSQL / PostgREST|
               +------------------------+
                            ^
                            | (Sync Queue Push / Pull)
                            v
+--------------------------------------------------------------------------------------+
| APMC YARD LAN / LOCALHOST TERMINALS (192.168.0.140:8080)                            |
|                                                                                      |
|   +------------------------------------+      +------------------------------------+ |
|   | Cashier Desktop Terminal           |      | Inspector Tablet Portal            | |
|   | (branch_dashboard.html)            |      | (inspector_portal.html)            | |
|   +------------------------------------+      +------------------------------------+ |
|                     |                                            |                   |
|                     +---------------------+----------------------+                   |
|                                           v                                          |
|                          +----------------------------------+                        |
|                          | Central FastAPI Server (server.py)|                        |
|                          +----------------------------------+                        |
|                                           |                                          |
|                                           v                                          |
|                          +----------------------------------+                        |
|                          | SQLite (commodity_mandi.db)      |                        |
|                          +----------------------------------+                        |
+--------------------------------------------------------------------------------------+
```

### Threat Vectors:
- **Vector T1 (Cloud Root Compromise):** An attacker inspecting `inspections-submit.js` extracts the `service_role` JWT and executes arbitrary SQL queries, deletes tables, or exfiltrates all commercial mandi data from Supabase.
- **Vector T2 (PII & Land Record Harvesting):** Unauthenticated scrapers query `/api/farmers/search?q=%` to build structured databases of agricultural landowners, mobile numbers, and bank records.
- **Vector T3 (Cashier Session Hijacking via DOM XSS):** A malicious actor registers a farmer with a payload in the `name` or `village` field. When the cashier opens the "Review & Confirm" invoice modal, arbitrary JavaScript executes in the cashier's browser, hijacking the `mandi_session` cookie or issuing forged payout requests.
- **Vector T4 (Financial Double-Disbursement):** A cashier double-clicks "Confirm & Disburse" during high network latency, or an unhandled exception causes a retry, generating duplicate cash vouchers and depleting physical drawer cash.

---

## 3. Cryptographic Key Hygiene & Hardcoded Secrets Audit

### 3.1 Hardcoded Supabase `service_role` Key Analysis
- **File:** `mandi-erp-tracker/api/inspections-submit.js:17`
- **Discovered Token (Redacted):**
  `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.ey...[REDACTED_SERVICE_ROLE_TOKEN]...X4`
- **Decoded Header & Claims:**
  - `alg`: `HS256`
  - `typ`: `JWT`
  - `role`: `service_role`
  - `iss`: `supabase`
  - `ref`: `dbhcpebchoyjyffqjgih`
- **Vulnerability Analysis:**
  The `service_role` key is designed strictly for trusted server-side background processes. In Supabase, the `service_role` key explicitly instructs PostgREST to **bypass all Row Level Security (RLS) policies**. Embedding this key as a fallback literal in git-tracked source code creates a critical security breach:
  1. Any developer, contractor, CI/CD worker, or person with repository access gains complete administrative control.
  2. The function `inspections-submit.js` executes with `Access-Control-Allow-Origin: *`, allowing external clients to interact directly with the database through this privileged role.

### 3.2 Client-Side Plaintext Credentials
- **File:** `mandi-erp-tracker/app.html:526-531`
- **Discovered Configuration:**
  ```javascript
  const STAFF_CREDENTIALS = {
      'qc_chikhali': { pass: 'qc123', name: 'Sanjay Patil', yard: 'CHK', yardName: 'Chikhali APMC Yard' },
      'qc_varvand': { pass: 'qc123', name: 'Govind Solanki', yard: 'VRV', yardName: 'Varvand APMC Yard' },
      'qc_dhad': { pass: 'qc123', name: 'Narayan Sharma', yard: 'DHD', yardName: 'Dhad APMC Yard' },
      'admin': { pass: 'admin123', name: 'Super Admin', yard: 'CHK', yardName: 'Chikhali APMC Yard' }
  };
  ```
- **Vulnerability Analysis:**
  The mobile PWA performs authentication purely on the client side:
  ```javascript
  const staff = STAFF_CREDENTIALS[username];
  if (!staff || staff.pass !== password) { ... }
  ```
  1. Plaintext passwords for all yard inspectors and Super Admin are visible in DevTools or "View Source".
  2. The user session is stored directly into browser `localStorage`:
     `localStorage.setItem('mandi_qc_user', JSON.stringify(userSession));`
  3. No cryptographic signature, token exchange, or server-side session validation is performed by the PWA. Any user can type `localStorage.setItem('mandi_qc_user', JSON.stringify({username:'admin', role:'admin'}))` in the console to obtain administrative interface access.

### 3.3 Default Production Database Credentials
- **File:** `commoditi software/database.py:792-797`
- **Observed:**
  When `init_db()` initializes the database, it inserts default user accounts with pre-hashed default passwords:
  - `admin`: `admin123`
  - `accountant`: `acc123`
  - `cashier_chikhali`: `chk123`
  - `cashier_varvand`: `vrv123`
  - `cashier_dhad`: `dhd123`
  - `qc_chikhali`: `qc123`
- **Vulnerability Analysis:**
  While the passwords are hashed with salted PBKDF2-HMAC-SHA256, shipping with well-known default passwords allows immediate unauthorized access if an administrator deploys the software without immediately changing all default credentials.

---

## 4. Authentication, Session Management & RBAC Audit

### 4.1 Password Storage & Hash Migration
- **Implementation:** `database.py:hash_password()`, `database.py:verify_password()`.
- **Algorithm:** PBKDF2-HMAC-SHA256 with 600,000 iterations and a per-user 16-byte random salt (`os.urandom(16)`).
- **Format:** `pbkdf2_sha256$600000$<salt_hex>$<hash_hex>`.
- **Evaluation:** High-grade cryptographic implementation compliant with OWASP Password Storage Guidelines (2025/2026).
- **In-flight Migration:** The system verifies legacy unsalted SHA-256 hashes via `hmac.compare_digest(legacy_hash, stored_hash)` and flags `needs_rehash = True`, upgrading the user's record to PBKDF2 upon successful authentication.

### 4.2 FastAPI Session Management
- **Implementation:** `server.py:create_session_token()`, `server.py:verify_session_token()`.
- **Token Structure:**
  $$\text{Token} = \text{base64url}(\text{session\_id} \parallel \text{username} \parallel \text{role} \parallel \text{branch\_id} \parallel \text{expires\_at} \parallel \text{HMAC-SHA256}(\text{SECRET}, \text{payload}))$$
- **Session Store:** SQLite table `user_sessions(session_id, user_id, username, role, branch_id, expires_at, is_revoked)`.
- **Cookie Flags:**
  `resp.set_cookie(key="mandi_session", value=token, httponly=True, samesite="lax", path="/")`
- **Identified Weaknesses:**
  1. *Missing `Secure` Cookie Attribute (AUD-SEC-007):* The cookie omits `secure=True`. In production over HTTPS or mixed networks, the browser will send session tokens over unencrypted HTTP requests.
  2. *Excessive Session Lifetime:* Session lifetime is configured for 12 hours (`43200 seconds`). For financial systems handling cash disbursements, 12 hours without sliding re-authentication is excessive.
  3. *Instance Secret Persistence:* `instance_secret.key` is generated and saved locally in plaintext. If `instance_secret.key` is backed up or read, all historical session tokens can be forged.

### 4.3 Role-Based Access Control (RBAC) Matrix

The system implements 5 staff roles:
`SUPER_ADMIN`, `ACCOUNTANT_HQ`, `BRANCH_MUNIM`, `BRANCH_CASHIER`, `QUALITY_INSPECTOR`.

All 76 application routes were audited for authorization barriers:

```
+------------------------------------+--------------------------+---------------------+-------------------+
| Route / Endpoint                   | Allowed Roles            | Enforcement Method  | Audit Assessment  |
+------------------------------------+--------------------------+---------------------+-------------------+
| /api/admin/users                   | SUPER_ADMIN              | require_role()      | SECURE            |
| /api/admin/database/reset          | SUPER_ADMIN              | require_role()      | SECURE            |
| /api/admin/supabase/connect        | SUPER_ADMIN              | require_role()      | SECURE            |
| /api/accounts/rates                | ACCOUNTANT_HQ, SUPER_ADM | require_role()      | SECURE            |
| /api/accounts/rtgs/process         | ACCOUNTANT_HQ, SUPER_ADM | require_role()      | SECURE            |
| /api/branch/invoices/create        | BRANCH_CASHIER, SUPER_ADM| require_role()      | SECURE (Role only)|
| /api/cashier/payout                | BRANCH_CASHIER, SUPER_ADM| require_role()      | SECURE            |
| /api/farmers/search                | ANY (UNAUTHENTICATED)    | NONE                | VULNERABLE        |
| /api/supabase/status               | ANY (UNAUTHENTICATED)    | NONE                | INFO DISCLOSURE   |
| /api/system/updates/status         | ANY (UNAUTHENTICATED)    | NONE                | INFO DISCLOSURE   |
| /api/inspections-submit (Cloud)    | ANY (UNAUTHENTICATED)    | NONE                | VULNERABLE        |
+------------------------------------+--------------------------+---------------------+-------------------+
```

#### RBAC Disconnects Identified:
1. **Branch Cashier Isolation:** In `api_branch_create_invoice`, if a cashier account has `branch_id = NULL`, the server does not enforce branch scoping and allows the user to post transactions to any branch.
2. **Accountant vs Cashier Separation:** `ACCOUNTANT_HQ` cannot disburse cash payouts (enforced via `require_role(["BRANCH_CASHIER", "SUPER_ADMIN"])`). This represents proper segregation of duties.

---

## 5. Injection & Input Validation Audit

### 5.1 SQL Injection Analysis
- **Methodology:** AST parsing and regex pattern scanning for dynamic SQL formatting (`f-strings`, `.format()`, `%`) in `server.py`, `database.py`, and `supabase_sync.py`.
- **Finding:** The central server application (`server.py`) and database layer (`database.py`) consistently use parameterized SQL queries (`cur.execute("SELECT ... WHERE col=?", (val,))`).
- **Edge Cases Audited:**
  - `server.py:3496`: `del_sql = f"DELETE FROM [{t}]"`. The variable `t` is drawn strictly from a hardcoded list of internal table name strings (`wipe_tables`). Not exploitable.
  - `supabase_sync.py:219`: `ALTER TABLE {t} ADD COLUMN ...`. The table name `t` is drawn strictly from internal table definitions.
- **Verdict:** No raw SQL injection vulnerabilities identified in the core operational query paths.

### 5.2 Cross-Site Scripting (XSS) & Template Safety
- **Jinja2 Auto-Escaping:** Jinja2 auto-escapes HTML by default in FastAPI.
- **Audit of `| safe` Filters:**
  - `admin_dashboard.html:113`: `<script type="application/json" id="branch-data-{{ loop.index0 }}">{{ cs.branch_json|safe }}</script>`
  - `branch_dashboard.html:1427`: `<script type="application/json" id="daily-rates-data">{{ daily_rates_json | safe }}</script>`
  Both instances serialize structured Python dictionaries via `json.dumps()`. However, if dictionary values contain closing `</script>` tags, script context escape is possible.
- **DOM XSS Vulnerability (AUD-SEC-005):**
  In `branch_dashboard.html:1849-1897`:
  ```javascript
  const reviewHtml = `
      <div style="font-size:16px; font-weight:800; color:#0f172a;">${farmerName}</div>
      <div style="font-size:12px; color:#475569; margin-top:2px;">📱 ${farmerPhone} • 📍 ${farmerVillage}</div>
      <div style="font-size:11.5px; color:#64748b; margin-top:4px;">Khasra: ${farmerKhasra} • Aadhaar: ${farmerAadhaar}</div>
  `;
  document.getElementById('confirmReviewBody').innerHTML = reviewHtml;
  ```
  The values `${farmerName}`, `${farmerVillage}`, `${farmerKhasra}`, and `${farmerAadhaar}` are derived directly from user input or database records and concatenated into `reviewHtml` without HTML entity encoding, then rendered via `.innerHTML`.

---

## 6. Financial Integrity, ACID Guarantees & Concurrency Audit

### 6.1 Transaction Boundaries & Atomicity
- **Implementation:** `server.py:api_branch_create_invoice()` and `server.py:api_cashier_disburse_payout()`.
- **ACID Integrity Evaluation:**
  - In `api_branch_create_invoice`: The invoice insertion, QC ticket status update, cashier payout insertion (if cash), cash drawer deduction, and double-entry ledger postings are enclosed within a single `try ... except` block with `conn.commit()` at the end and `conn.rollback()` in the exception handler.
  - SQLite default transaction locking ensures that if any insert fails (e.g. FK violation), the entire inward purchase is rolled back.

### 6.2 Idempotency & Double-Click Vulnerability
- **Finding (AUD-SEC-006):** While database atomicity is preserved within a single request, the system **lacks application-level idempotency**:
  1. The API generates token numbers sequentially:
     `SELECT count(*) as cnt FROM purchase_invoices WHERE branch_id=? AND invoice_date=?`
     `token_number = f"{b_code}-{token_date}-{seq:04d}"`
  2. If a cashier submits an invoice, the server completes the write and returns a response.
  3. If a network interruption occurs before the client receives the response, or if the cashier double-clicks the button with a 200ms gap:
     - Request 1 creates invoice `CHK-20261103-0005`, disburses ₹45,000 cash, and deducts cash drawer.
     - Request 2 sees `cnt = 5`, creates invoice `CHK-20261103-0006`, disburses ₹45,000 cash AGAIN, and deducts cash drawer AGAIN.
  4. The client does not generate a client-side UUID idempotency key (`Idempotency-Key` header) to deduplicate incoming purchase creations.

---

## 7. Security & Reliability Findings (AUD-SEC-001 through AUD-SEC-010)

---

### Finding AUD-SEC-001
- **Severity:** CRITICAL
- **Module:** Cloud API & Cryptographic Key Hygiene
- **File / Line:** `mandi-erp-tracker/api/inspections-submit.js:17`, `commoditi software/.env:14`
- **Observed:** A valid Supabase `service_role` JWT is hardcoded into the source code as a fallback value.
- **Expected:** Privileged cloud service keys must never be hardcoded into source code or committed to revision control. They must be injected exclusively via secure runtime environment variables.
- **Actual:** Line 17 of `inspections-submit.js` contains:
  ```javascript
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY || process.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI...[REDACTED]';
  ```
  The fallback string contains an active JWT possessing the `service_role` claim for project `dbhcpebchoyjyffqjgih`.
- **Evidence:**
  Decoded JWT Header: `{"alg":"HS256","typ":"JWT"}`  
  Decoded JWT Payload: `{"role":"service_role","iss":"supabase","ref":"dbhcpebchoyjyffqjgih",...}`
- **Business Impact:** Total cloud database compromise. Anyone with read access to the file or repository can use the `service_role` key to bypass all Supabase RLS policies, execute arbitrary CRUD queries, drop tables, alter financial records, or exfiltrate all historical farmer, rate, and transaction data.
- **Correction:**
  1. Immediately revoke and regenerate the `service_role` key in the Supabase Dashboard.
  2. Remove the hardcoded string literal from `inspections-submit.js`.
  3. Enforce strict environment variable validation:
  ```javascript
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!serviceKey) {
      return res.status(500).json({ success: false, error: "Server configuration error: Missing SUPABASE_SERVICE_ROLE_KEY." });
  }
  ```
- **Tests:** Verify that running `inspections-submit.js` without the environment variable returns HTTP 500 without falling back to any hardcoded key.
- **Dependencies:** Supabase Cloud Project `dbhcpebchoyjyffqjgih`.

---

### Finding AUD-SEC-002
- **Severity:** CRITICAL
- **Module:** Mobile PWA Authentication & Credential Storage
- **File / Line:** `mandi-erp-tracker/app.html:526-531`
- **Observed:** Plaintext passwords for all quality inspectors and Super Admin are stored directly inside client-side JavaScript.
- **Expected:** Client applications must never store credentials. User authentication must be performed via server-side challenge/response with secure token issuance.
- **Actual:** Lines 526-531 embed `STAFF_CREDENTIALS`:
  ```javascript
  const STAFF_CREDENTIALS = {
      'qc_chikhali': { pass: 'qc123', name: 'Sanjay Patil', yard: 'CHK', yardName: 'Chikhali APMC Yard' },
      'qc_varvand': { pass: 'qc123', name: 'Govind Solanki', yard: 'VRV', yardName: 'Varvand APMC Yard' },
      'qc_dhad': { pass: 'qc123', name: 'Narayan Sharma', yard: 'DHD', yardName: 'Dhad APMC Yard' },
      'admin': { pass: 'admin123', name: 'Super Admin', yard: 'CHK', yardName: 'Chikhali APMC Yard' }
  };
  ```
  Authentication is evaluated in the browser: `if (!staff || staff.pass !== password)`.
- **Evidence:**
  Inspectable directly via "View Source" or browser DevTools on any device accessing the PWA URL.
- **Business Impact:** Unauthorized access to all inspector functions, ability to impersonate Super Admin across yard terminals, and complete trivialization of access controls.
- **Correction:**
  1. Remove `STAFF_CREDENTIALS` from `app.html`.
  2. Implement an authenticated `/api/auth/login` endpoint that validates credentials against salted PBKDF2 hashes in the database and returns a signed session token.
- **Tests:** Confirm that no plaintext password strings exist anywhere within `app.html` or client bundles.
- **Dependencies:** `mandi-erp-tracker/app.html`.

---

### Finding AUD-SEC-003
- **Severity:** HIGH
- **Module:** API Authorization & Data Privacy (PII)
- **File / Line:** `commoditi software/server.py:3865-3885`
- **Observed:** The farmer search endpoint requires zero authentication or role authorization.
- **Expected:** Endpoints exposing Personally Identifiable Information (PII) and agricultural land records must require authenticated staff sessions with appropriate role permissions (`BRANCH_CASHIER`, `ACCOUNTANT_HQ`, `SUPER_ADMIN`).
- **Actual:** `@app.get("/api/farmers/search")` takes `q: str = ""` and returns:
  `p.id, p.name, p.phone, p.village, p.khasra_record_no, vehicle_no`.
  There is NO `get_authenticated_user(request)` or `require_role(request, ...)`.
- **Evidence:**
  ```python
  # server.py:3865-3870
  @app.get("/api/farmers/search")
  def api_search_farmers(request: Request, q: str = ""):
      query = (q or "").strip()
      # ZERO AUTHENTICATION CHECKS!
  ```
- **Business Impact:** Serious data privacy breach. Competitors, fraudsters, or external scrapers can iterate through letters (`q=a`, `q=b`, ...) and extract the complete database of farmers, contact numbers, and land ownership records.
- **Correction:** Add authorization check at the top of `api_search_farmers`:
  ```python
  require_role(request, ["BRANCH_CASHIER", "BRANCH_MUNIM", "ACCOUNTANT_HQ", "SUPER_ADMIN"])
  ```
- **Tests:** Send an unauthenticated GET request to `/api/farmers/search?q=Ram`. Assert HTTP 401 Unauthorized.
- **Dependencies:** `server.py`, `parties`.

---

### Finding AUD-SEC-004
- **Severity:** HIGH
- **Module:** Cloud QC Ingestion & Public Write Access
- **File / Line:** `mandi-erp-tracker/api/inspections-submit.js:19-35`, `mandi-erp-tracker/api/inspections-submit.js:37-120`
- **Observed:** The serverless inspection submission API allows unauthenticated public GET and POST access.
- **Expected:** Submitting quality inspection tickets and viewing pending inspection slips must require valid staff authentication.
- **Actual:** `inspections-submit.js` sets `Access-Control-Allow-Origin: *` and executes GET and POST requests without validating any `Authorization` header, session cookie, or HMAC signature. Anyone on the internet can scrape pending tickets or inject forged inspection tickets into Supabase with arbitrary buying rates.
- **Evidence:**
  ```javascript
  // inspections-submit.js:1-14
  res.setHeader('Access-Control-Allow-Origin', '*');
  // No verification of Authorization header or token signature
  ```
- **Business Impact:** Data poisoning and inventory fraud. Malicious actors can flood the mandi system with hundreds of fake high-moisture or low-moisture inspection tickets, manipulating buying rates and disrupting yard operations.
- **Correction:**
  1. Enforce JWT bearer verification or shared HMAC pre-shared key header (`X-Mandi-Terminal-Key`) on all incoming requests.
  2. Reject requests lacking valid signatures.
- **Tests:** Send POST request without `Authorization` header. Assert HTTP 401 Unauthorized.
- **Dependencies:** `mandi-erp-tracker/api/inspections-submit.js`.

---

### Finding AUD-SEC-005
- **Severity:** HIGH
- **Module:** Cross-Site Scripting (DOM XSS)
- **File / Line:** `commoditi software/templates/branch_dashboard.html:1849-1897`
- **Observed:** Cultivator details (name, village, khasra, aadhaar) are concatenated into a template literal without sanitization and assigned to `.innerHTML`.
- **Expected:** All user-supplied strings rendered into HTML must be entity-encoded via a robust `escapeHtml()` utility to prevent script injection.
- **Actual:** Lines 1854-1856 interpolate raw variables:
  `${farmerName}`, `${farmerVillage}`, `${farmerKhasra}`, `${farmerAadhaar}`.
  Line 1897 renders the block:
  `document.getElementById('confirmReviewBody').innerHTML = reviewHtml;`.
- **Evidence:**
  ```javascript
  // branch_dashboard.html:1854-1856
  <div style="font-size:16px; font-weight:800; color:#0f172a;">${farmerName}</div>
  <div style="font-size:12px; color:#475569; margin-top:2px;">📱 ${farmerPhone} • 📍 ${farmerVillage}</div>
  ...
  document.getElementById('confirmReviewBody').innerHTML = reviewHtml;
  ```
- **Business Impact:** Stored Cross-Site Scripting (XSS). An attacker can register a farmer with a payload such as:
  `Ramesh <img src=x onerror="fetch('/api/admin/users').then(...)">`.
  When the branch cashier opens the inward purchase review modal, the script executes with the cashier's active session permissions.
- **Correction:** Wrap all interpolated variables with `escapeHtml()`:
  ```javascript
  ${escapeHtml(farmerName)}
  ${escapeHtml(farmerVillage)}
  ${escapeHtml(farmerKhasra)}
  ```
- **Tests:** Register a farmer with name `<script>window.xssTest=true</script>`. Open inward modal. Verify script is escaped as text and `window.xssTest` remains undefined.
- **Dependencies:** `branch_dashboard.html`.

---

### Finding AUD-SEC-006
- **Severity:** HIGH
- **Module:** Financial Concurrency & Idempotency
- **File / Line:** `commoditi software/server.py:2320-2324`, `commoditi software/server.py:2407-2417`, `commoditi software/templates/branch_dashboard.html:1905-1932`
- **Observed:** Inward purchase invoice and cash payout creation lacks idempotency keys, and sequence numbering is vulnerable to race condition collisions.
- **Expected:** Financial creation endpoints must accept an `Idempotency-Key` or request UUID generated prior to submission. Duplicate submissions with the same key must return the original cached response without re-executing transactions. Sequential numbering must be atomic.
- **Actual:** Token number generation executes:
  `SELECT count(*) as cnt FROM purchase_invoices WHERE branch_id=? AND invoice_date=?`
  `seq = cur.fetchone()["cnt"] + 1`
  If two requests occur concurrently, both read the same count and attempt to insert the same token, causing an unhandled 500 collision. More critically, if a cashier retries after a network timeout, a second distinct invoice and cash disbursement is created for the same physical lot.
- **Evidence:**
  ```python
  # server.py:2320-2322
  cur.execute("SELECT count(*) as cnt FROM purchase_invoices WHERE branch_id=? AND invoice_date=?", (branch_id, today_str))
  seq = cur.fetchone()["cnt"] + 1
  token_number = f"{b_code}-{token_date}-{seq:04d}"
  ```
- **Business Impact:** Duplicate cash disbursements, double-counted inventory, cashier drawer discrepancies, and accounting ledger corruption.
- **Correction:**
  1. Add an `idempotency_key TEXT UNIQUE` column to `purchase_invoices`.
  2. Generate a client-side UUID when opening the purchase modal and pass it in `FormData`.
  3. If the key already exists, return the existing invoice details instead of inserting a new record.
- **Tests:** Send two identical POST requests with the same `idempotency_key` concurrently. Verify only one invoice is created and both responses return the same `invoice_id`.
- **Dependencies:** `purchase_invoices`, `branch_dashboard.html`.

---

### Finding AUD-SEC-007
- **Severity:** MEDIUM
- **Module:** Session Cookie Security & CSRF Defenses
- **File / Line:** `commoditi software/server.py:779`, `commoditi software/server.py:102-108`
- **Observed:** The authentication session cookie omits the `Secure` attribute, and state-modifying POST endpoints lack anti-CSRF token verification.
- **Expected:** In production, session cookies must specify `secure=True`, `httponly=True`, and `samesite="lax"` or `"strict"`. State-changing POST endpoints must validate a synchronized anti-CSRF token.
- **Actual:** Line 779 sets:
  `resp.set_cookie(key="mandi_session", value=token, httponly=True, samesite="lax", path="/")`.
  No `secure=True` flag is present. No CSRF middleware exists.
- **Evidence:**
  ```python
  # server.py:779
  resp.set_cookie(key="mandi_session", value=token, httponly=True, samesite="lax", path="/")
  ```
- **Business Impact:** Session tokens can be sniffed if accessed over unencrypted connections on the APMC local network. Subdomains or cross-origin contexts can potentially trigger state-modifying requests.
- **Correction:**
  1. Enable `secure=True` dynamically when operating over HTTPS or in production.
  2. Implement anti-CSRF token verification on all POST/PUT/DELETE forms.
- **Tests:** Inspect Set-Cookie header on `/login` response. Verify `Secure; HttpOnly; SameSite=Lax`.
- **Dependencies:** `server.py:login_post`.

---

### Finding AUD-SEC-008
- **Severity:** MEDIUM
- **Module:** Default Credential Hygiene
- **File / Line:** `commoditi software/database.py:792-797`
- **Observed:** Initial database seeding creates accounts with well-known default passwords across all roles.
- **Expected:** Default passwords must be randomized upon initial setup, or the system must force a mandatory password change on first login before allowing access to operational functions.
- **Actual:** `init_db()` seeds:
  `admin123`, `acc123`, `chk123`, `vrv123`, `dhd123`, `qc123`.
  No `must_change_password` flag exists on the `users` table.
- **Evidence:**
  ```python
  # database.py:792-797
  admin_pw = hash_password("admin123")
  acc_pw = hash_password("acc123")
  chk_pw = hash_password("chk123")
  vrv_pw = hash_password("vrv123")
  dhd_pw = hash_password("dhd123")
  qc_pw = hash_password("qc123")
  ```
- **Business Impact:** Trivial unauthorized access if system is deployed without manual administrator intervention.
- **Correction:** Add a `must_change_password INTEGER DEFAULT 0` column to `users`. Force a password change modal on first login.
- **Tests:** Log in with default credentials. Verify user is redirected to password change view and blocked from accessing dashboards.
- **Dependencies:** `database.py`, `server.py`.

---

### Finding AUD-SEC-009
- **Severity:** MEDIUM
- **Module:** Information Disclosure & Infrastructure Leakage
- **File / Line:** `commoditi software/server.py:1461-1479`, `commoditi software/server.py:3551-3567`
- **Observed:** Endpoints `/api/system/updates/status` and `/api/supabase/status` are accessible without authentication and disclose internal IP addresses and cloud project identifiers.
- **Expected:** Diagnostic and infrastructure health endpoints must require staff authentication or return sanitized non-identifying telemetry.
- **Actual:** Calling `/api/system/updates/status` returns internal host `192.168.0.140:8080`, build dates, and patch levels. Calling `/api/supabase/status` returns project reference `dbhcpebchoyjyffqjgih`.
- **Evidence:**
  ```json
  {
    "success": true,
    "master_host": "192.168.0.140:8080",
    "cloud_pwa_url": "https://mandi-erp-tracker.vercel.app/app",
    "project_ref": "dbhcpebchoyjyffqjgih"
  }
  ```
- **Business Impact:** Provides attackers with targeted infrastructure mapping details, internal IP addressing schemes, and cloud identifiers.
- **Correction:** Require authentication (`get_authenticated_user`) or redact internal IP addresses and project references for unauthenticated responses.
- **Tests:** Verify unauthenticated requests to `/api/system/updates/status` receive sanitized output without LAN IP addresses.
- **Dependencies:** `server.py`.

---

### Finding AUD-SEC-010
- **Severity:** LOW
- **Module:** Storage Hygiene & Database Bloat
- **File / Line:** `mandi-erp-tracker/app.html:1180-1181`, `mandi-erp-tracker/api/inspections-submit.js:90-91`
- **Observed:** Raw multi-megabyte base64 image data URLs are saved directly into database text columns instead of using an object storage service.
- **Expected:** Binary image files must be saved to local disk storage (`/static/uploads/`) or cloud object storage (S3 / Supabase Storage), with only relative URL paths stored in database columns.
- **Actual:** When the PWA submits a ticket, `meterPhoto` and `grainPhoto` base64 strings (often 2 to 5 MB each) are pushed into `meter_photo_path` and `grain_photo_path` in PostgreSQL, causing extreme database size inflation and slow REST queries.
- **Evidence:**
  ```javascript
  // app.html:1180-1181
  meter_photo_path: (meterPhoto && meterPhoto.startsWith('data:image')) ? meterPhoto : null,
  grain_photo_path: (grainPhoto && grainPhoto.startsWith('data:image')) ? grainPhoto : null,
  ```
- **Business Impact:** Slow queries, connection timeouts on rural 3G/4G connections, and excessive database backup sizes.
- **Correction:** Upload binary files to Supabase Storage bucket (`qc-photos`) or FastAPI multipart endpoint `/static/uploads/`, and store only the resulting URL in the database.
- **Tests:** Verify that database records contain image URLs (`/static/uploads/...jpg` or `https://...`) instead of `data:image/jpeg;base64,...` strings.
- **Dependencies:** `quality_inspections`, Supabase Storage.

---

## 8. Remediation Roadmap & Prioritized Action Plan

```
+----------+-------------------------------------------------------------+----------+---------------+
| Phase    | Remediation Action                                          | Finding  | Priority      |
+----------+-------------------------------------------------------------+----------+---------------+
| Phase 1  | Revoke & regenerate Supabase service_role key; clean repo   | AUD-001  | IMMEDIATE P0  |
| (Day 1)  | Remove hardcoded STAFF_CREDENTIALS from app.html            | AUD-002  | IMMEDIATE P0  |
|          | Require authentication on /api/farmers/search               | AUD-003  | IMMEDIATE P0  |
+----------+-------------------------------------------------------------+----------+---------------+
| Phase 2  | Add UNIQUE index & PENDING check on QC ticket linking       | AUD-001b | CRITICAL P1   |
| (Week 1) | Block cash payout on pending rate overrides in server.py    | AUD-002b | CRITICAL P1   |
|          | Enforce Section 269ST cumulative cash check in invoices     | AUD-003b | CRITICAL P1   |
|          | Escape farmer fields in branch_dashboard.html (DOM XSS)     | AUD-005  | HIGH P1       |
+----------+-------------------------------------------------------------+----------+---------------+
| Phase 3  | Implement client-side idempotency keys for invoice creation | AUD-006  | HIGH P2       |
| (Week 2) | Fix unbalanced RTGS and deferred cashier payout ledgers     | AUD-004b | HIGH P2       |
|          | Replace auto-injected ₹5L drawer with shift sessions        | AUD-005b | HIGH P2       |
|          | Validate yard stock before outward dispatches               | AUD-006b | HIGH P2       |
+----------+-------------------------------------------------------------+----------+---------------+
| Phase 4  | Add Secure cookie attribute & CSRF token verification       | AUD-007  | MEDIUM P3     |
| (Month 1)| Add must_change_password flag for default seed accounts     | AUD-008  | MEDIUM P3     |
|          | Move camera photos to object storage instead of base64      | AUD-010  | LOW P3        |
+----------+-------------------------------------------------------------+----------+---------------+
```

---
*End of Report 08: Application Security, Credential Hygiene & Financial Integrity Audit.*
