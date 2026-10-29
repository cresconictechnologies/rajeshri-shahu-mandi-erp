# PRODUCTION RELEASE RUNBOOK — RAJESHRI SHAHU MANDI ERP

**Product:** Rajeshri Shahu Mandi & Commodity Procurement ERP  
**Target Architecture:** Windows Desktop Application (Embedded Uvicorn + FastAPI + PyWebView / Edge WebView2)  
**Distribution File:** `Rajeshri_Shahu_Mandi_ERP.exe`  
**Document Version:** 1.0 (Production Release Guide)  
**Security Standard:** NIST SP 800-63B, OWASP ASVS v4.0, Ed25519 Commercial Licensing, Maharashtra APMC Rules  

---

## 1. Release Architecture & Key Separation Overview

The software enforces a strict mathematical separation between the **Commercial Software Vendor** (Cresconic Technologies) and the **Licensed Mandi Yard Operator** (Super Admin / Owner):

```
+-------------------------------------------------------------------+
|               OFFLINE AIR-GAPPED VENDOR ENVIRONMENT               |
|                                                                   |
|   1. Vendor Private Key (Kept offline in HSM / Vault)             |
|   2. vendor_license_issuer.py (Internal vendor CLI tool)          |
|   3. Outputs Signed Commercial License Tokens                     |
+---------------------------------+---------------------------------+
                                  | Token String (Base64URL)
                                  v
+-------------------------------------------------------------------+
|               DISTRIBUTED CLIENT APPLICATION (ERP)                |
|                                                                   |
|   1. Embedded Vendor Public Key (Injected in licensing.py)        |
|   2. PyInstaller Frozen Bundle (Rajeshri_Shahu_Mandi_ERP.exe)     |
|   3. Local SQLite Database (commodity_mandi.db)                   |
|   4. Zero Vendor Private Keys or Issuance Tools Included          |
+-------------------------------------------------------------------+
```

---

## 2. Step-by-Step Operator Release Procedure

### Phase 1: Official Vendor Air-Gapped Key Ceremony

> [!IMPORTANT]
> The vendor private signing key must **NEVER** be created on or transferred to developer laptops, cloud build agents, or the customer deployment environment.

On a secure, disconnected, air-gapped vendor workstation:

1. **Generate the Production Ed25519 Key Pair:**
   ```bash
   python -c "
   from cryptography.hazmat.primitives.asymmetric import ed25519
   from cryptography.hazmat.primitives import serialization

   priv = ed25519.Ed25519PrivateKey.generate()
   pub = priv.public_key()

   priv_bytes = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
   pub_bytes = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

   print('=== VENDOR PRODUCTION PUBLIC KEY (EMBED IN CLIENT APP) ===')
   print(pub_bytes.hex())

   print('=== VENDOR PRODUCTION PRIVATE KEY (STORE IN VAULT ONLY) ===')
   # Securely store priv_bytes.hex() in vendor HSM / Key Vault
   "
   ```

2. **Secure the Private Key:**
   - Save the private key hex into a hardware-backed password vault or HSM.
   - Do **NOT** commit this key to Git or send via email/chat.

3. **Record the Public Key:**
   - Copy the 64-character public key hex for injection in Phase 2.

---

### Phase 2: Inject Production Public Key into Client Codebase

On the release engineering build workstation:

1. **Open `licensing.py`:**
   Locate line 25:
   ```python
   PRODUCTION_VENDOR_PUBLIC_KEY_HEX: Optional[str] = os.environ.get("VENDOR_PRODUCTION_PUBLIC_KEY_HEX", None)
   ```
2. **Inject the Production Public Key:**
   Replace `None` with the 64-character public key hex generated in Phase 1:
   ```python
   PRODUCTION_VENDOR_PUBLIC_KEY_HEX: Optional[str] = os.environ.get(
       "VENDOR_PRODUCTION_PUBLIC_KEY_HEX",
       "<PASTE_64_HEX_OFFICIAL_PRODUCTION_PUBLIC_KEY_HERE>"
   )
   ```
   *(Or set `export VENDOR_PRODUCTION_PUBLIC_KEY_HEX="<HEX>"` in the CI/CD release build environment).*

3. **Set Production Environment Mode:**
   ```bash
   $env:MANDI_ERP_ENV = "production"
   ```

---

### Phase 3: Mint the Customer's Commercial License Token

On the offline vendor workstation (using `vendor_license_issuer.py`):

1. **Run the Offline Issuer Tool:**
   ```bash
   python vendor_license_issuer.py `
       --key-hex "<VENDOR_PRIVATE_KEY_HEX>" `
       --name "Rajeshri Shahu Trading Co." `
       --id "LIC-RSM-2026-MH3B-PRO" `
       --tier "PRO" `
       --branches 3 `
       --days 730
   ```
2. **Copy the Output Token:**
   The output string is in format `payload_b64.signature_b64`.
   Provide this token string to the customer along with their software delivery package.

---

### Phase 4: Compile and Package the Windows Executable

On the Windows build machine:

1. **Verify Prerequisites:**
   - Python 3.11+ 64-bit
   - PyInstaller 6.0+
   - WebView2 Runtime (pre-installed on Windows 10/11)
2. **Clean Previous Artifacts:**
   ```bash
   Remove-Item -Recurse -Force build, dist
   ```
3. **Execute Build:**
   ```bash
   python build_desktop_app.py
   ```
4. **Audit Packaged Artifacts:**
   Verify that `dist/Rajeshri_Shahu_Mandi_ERP/` contains:
   - `Rajeshri_Shahu_Mandi_ERP.exe`
   - `commodity_mandi.db`
   - `templates/` and `static/`
   - **ZERO** occurrences of `vendor_license_issuer.py`
   - **ZERO** `.key` or private credential files

---

### Phase 5: Installation & First-Run Setup at Customer Site

1. **Deploy to Customer Host PC:**
   Copy the `dist/Rajeshri_Shahu_Mandi_ERP` folder to the customer's desired installation directory (e.g. `C:\Rajeshri_Shahu_Mandi_ERP\`).
2. **Launch Application:**
   Double-click `Rajeshri_Shahu_Mandi_ERP.exe`.
   The native standalone WebView2 window opens automatically without launching Chrome or external browsers.
3. **First-Run Provisioning (`/setup`):**
   - The setup screen prompts for:
     1. Business Profile (Org Name, GSTIN, Owner Details).
     2. Commercial License Token (Customer pastes the vendor-signed token).
     3. Initial Staff Passwords (Central Accountant and Branch Cashiers).
   - Click **Activate License & Generate Staff Credentials**.
4. **Permanent Lockdown:**
   - The setup engine validates the Ed25519 digital signature.
   - Hashes passwords using NIST-compliant salted `PBKDF2-HMAC-SHA256` (600,000 iterations).
   - Writes `is_setup_completed = '1'` to `system_settings`.
   - Displays the printable Staff Credential Handover Slip.
   - Permanently locks `/setup` to **HTTP 404 Not Found**.

---

### Phase 6: Post-Deployment Administration & License Renewal

1. **Routine Access:**
   All users sign in at `http://127.0.0.1:8080/login`:
   - Super Admin: Redirected to `/admin/dashboard`.
   - Accountant: Redirected to `/accounts/dashboard`.
   - Cashiers: Redirected to their assigned branch yard (e.g. `/branch/dashboard?branch_id=br-chikhali`).
2. **Renewing or Upgrading Commercial License:**
   - When the customer purchases a validity extension or additional branch quota:
   - Vendor issues an updated signed token string using `vendor_license_issuer.py`.
   - Super Admin visits **Admin Settings** (`/admin/settings`).
   - Pastes the new token string into the **Renew Commercial License** box and clicks **Activate License**.
   - The backend validates the Ed25519 signature and updates branch quotas dynamically without restarting the server or interrupting yard operations.
