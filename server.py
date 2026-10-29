"""
Unified Web Server for Commodity Trading & Mandi ERP.
Serves Level 1 (Super Admin), Level 2 (Central Accounts), and Level 3 (Branch Operations).
Port: 8080 (Dedicated port avoiding port 8000 used by the restaurant app).
"""

import os
import sys
import uuid
import json
import hashlib
import hmac
import base64
from datetime import date, datetime, timezone, timedelta
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# Ensure parent directory is in sys.path
if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database import (
    get_connection,
    hash_password,
    verify_password,
    DB_PATH,
    init_db,
    login_admin,
    create_user_session,
    validate_user_session,
    revoke_user_session,
    revoke_user_sessions_by_user
)
from licensing import (
    get_active_license,
    verify_license_token,
    save_license_token,
    check_branch_limit,
    DEFAULT_COMMERCIAL_LICENSE_TOKEN
)
from calculations import (
    calculate_inward_invoice,
    calculate_outward_order,
    check_cash_compliance,
    check_rate_corridor,
    calculate_cash_payout_with_roundup,
    validate_cash_denominations
)

# Security guardrail: reject test database override in production mode
if os.environ.get("MANDI_ERP_ENV", "").lower() == "production" and os.environ.get("MANDI_TEST_DB_PATH"):
    raise RuntimeError("CRITICAL SECURITY ERROR: Test database override (MANDI_TEST_DB_PATH) is strictly prohibited in production mode.")

app = FastAPI(
    title="Mandi & Commodity Procurement ERP",
    version="1.0.0",
    description="Three-tier multi-branch commodity purchasing, pricing corridor governance, and mandi accounting ERP."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Ensure database tables exist
init_db()

# Mount static files directory
STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# --------------------------------------------------------------------------
# AUTHENTICATION, SESSIONS & OWNER SETUP
# --------------------------------------------------------------------------

SECRET_FILE = os.path.join(BASE_DIR, "instance_secret.key")

def get_or_create_instance_secret() -> str:
    env_secret = os.environ.get("SESSION_SECRET")
    if env_secret and len(env_secret) >= 32:
        return env_secret
    if os.path.exists(SECRET_FILE):
        try:
            with open(SECRET_FILE, "r", encoding="utf-8") as f:
                s = f.read().strip()
                if len(s) >= 32:
                    return s
        except Exception as e:
            sys.stderr.write(f"Notice: instance secret read failure: {e}\n")
    new_secret = os.urandom(32).hex()
    try:
        with open(SECRET_FILE, "w", encoding="utf-8") as f:
            f.write(new_secret)
    except Exception as e:
        sys.stderr.write(f"Notice: instance secret persistence: {e}\n")
    return new_secret

SESSION_SECRET = get_or_create_instance_secret()

def create_session_token(username: str, role: str, branch_id: str = "", user_id: str = "") -> str:
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    exp_epoch = now_epoch + 43200  # 12-hour session lifetime
    if not user_id:
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username=?", (username,))
            row = cur.fetchone()
            user_id = row["id"] if row else f"u-{username}"
        finally:
            conn.close()
    
    session_id = create_user_session(user_id, username, role, branch_id, duration_seconds=43200)
    payload = f"{session_id}|{username}|{role}|{branch_id}|{exp_epoch}"
    sig = hmac.new(SESSION_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token_raw = f"{payload}|{sig}"
    return base64.urlsafe_b64encode(token_raw.encode("utf-8")).decode("utf-8")

def verify_session_token(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = decoded.split("|")
        if len(parts) == 6:
            session_id, username, role, branch_id, exp_str, sig = parts
            expected_payload = f"{session_id}|{username}|{role}|{branch_id}|{exp_str}"
            expected_sig = hmac.new(SESSION_SECRET.encode("utf-8"), expected_payload.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None
            if int(exp_str) < int(datetime.now(timezone.utc).timestamp()):
                return None
            sess = validate_user_session(session_id)
            if not sess:
                return None

            # Enforce authoritative role and branch directly from the live database record
            auth_role = sess.get("authoritative_role") or role
            auth_branch = sess.get("authoritative_branch_id") if sess.get("authoritative_branch_id") is not None else branch_id
            return {
                "session_id": session_id,
                "user_id": sess["user_id"],
                "username": sess["username"],
                "role": auth_role,
                "branch_id": auth_branch,
                "full_name": sess.get("full_name", username)
            }
        # Strictly reject untracked or legacy 4-part tokens without database sessions
        return None
    except Exception:
        return None
    return None

def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get("mandi_session")
    return verify_session_token(token)

def get_authenticated_user(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        if request.url.path.startswith("/api/"):
            raise HTTPException(status_code=401, detail="Authentication required: Please sign in with valid staff credentials.")
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

def require_role(request: Request, allowed_roles: list[str]) -> dict:
    user = get_authenticated_user(request)
    if user.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"Forbidden: Access denied for role '{user.get('role')}'. Required roles: {allowed_roles}")
    return user

def check_system_license(conn=None) -> dict:
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    try:
        return get_active_license(conn)
    finally:
        if should_close:
            conn.close()

def require_active_license():
    lic = check_system_license()
    if not lic.get("is_valid"):
        raise HTTPException(status_code=403, detail=f"Commercial License Inactive or Expired: {lic.get('message')}. Please contact vendor to renew.")
    return lic

def is_system_setup_done() -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM system_settings WHERE scope='SUPER_ADMIN' AND setting_key='is_setup_completed'")
        row = cur.fetchone()
        return bool(row and row["setting_value"] == "1")
    except Exception:
        return False
    finally:
        conn.close()

@app.get("/", response_class=HTMLResponse)
def root_hub(request: Request):
    # Direct hub parameter support (used in developer testing)
    if request.query_params.get("hub") == "1":
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT count(*) as cnt FROM branches WHERE is_active=1")
            branches_count = cur.fetchone()["cnt"]
            cur.execute("SELECT count(*) as cnt FROM commodities WHERE is_active=1")
            commodities_count = cur.fetchone()["cnt"]
            cur.execute("SELECT count(*) as cnt FROM inspectors WHERE is_active=1")
            inspectors_count = cur.fetchone()["cnt"]
            stats = {
                "branches_count": branches_count,
                "commodities_count": commodities_count,
                "inspectors_count": inspectors_count
            }
        finally:
            conn.close()
        return templates.TemplateResponse(request=request, name="hub.html", context={"stats": stats})

    # 1. If commercial license / setup has not been completed by the Owner, direct to Setup
    if not is_system_setup_done():
        return RedirectResponse(url="/setup", status_code=303)

    # 2. If logged in, route directly to the assigned role terminal
    user = get_current_user(request)
    if user:
        role = user.get("role")
        if role == "SUPER_ADMIN":
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        elif role == "ACCOUNTANT_HQ":
            return RedirectResponse(url="/accounts/dashboard", status_code=303)
        else:
            b_id = user.get("branch_id") or "br-chikhali"
            return RedirectResponse(url=f"/branch/dashboard?branch_id={b_id}", status_code=303)

    # 3. Otherwise render single-point login terminal
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@app.get("/setup", response_class=HTMLResponse)
def setup_view(request: Request):
    if is_system_setup_done():
        raise HTTPException(status_code=404, detail="System setup has already been completed. First-run provisioning is permanently closed.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT setting_key, setting_value FROM system_settings WHERE scope='SUPER_ADMIN'")
        settings = {r["setting_key"]: r["setting_value"] for r in cur.fetchall()}

        cur.execute("SELECT * FROM users WHERE role='SUPER_ADMIN' LIMIT 1")
        owner = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE role='ACCOUNTANT_HQ' LIMIT 1")
        accountant = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE role='BRANCH_CASHIER' AND branch_id='br-chikhali' LIMIT 1")
        chk_cashier = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE role='BRANCH_CASHIER' AND branch_id='br-varvand' LIMIT 1")
        vrv_cashier = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE role='BRANCH_CASHIER' AND branch_id='br-dhad' LIMIT 1")
        dhd_cashier = cur.fetchone()

        return templates.TemplateResponse(request=request, name="setup.html", context={
            "settings": settings,
            "owner": dict(owner) if owner else {},
            "accountant": dict(accountant) if accountant else {},
            "chk_cashier": dict(chk_cashier) if chk_cashier else {},
            "vrv_cashier": dict(vrv_cashier) if vrv_cashier else {},
            "dhd_cashier": dict(dhd_cashier) if dhd_cashier else {},
            "success_msg": None,
            "generated_creds": None
        })
    finally:
        conn.close()

@app.post("/setup", response_class=HTMLResponse)
def setup_post(
    request: Request,
    org_name: str = Form("Rajeshri Shahu Trading Co."),
    owner_name: str = Form("Vikramaditya Singhal (Owner)"),
    owner_username: str = Form("admin"),
    owner_password: Optional[str] = Form(None),
    owner_phone: str = Form("9826011111"),
    org_gstin: str = Form("23AACCK1234F1Z5"),
    license_key: str = Form("RST-PRO-2026-MH3B-89A12F"),
    license_valid_until: str = Form("31-March-2027"),
    acc_name: str = Form("Omprakash Agrawal (Chief Accountant)"),
    acc_username: str = Form("accountant"),
    acc_password: str = Form("acc123"),
    acc_phone: str = Form("9826022222"),
    chk_name: str = Form("Santosh V. Patil (Chikhali Lead)"),
    chk_username: str = Form("chikhali_cashier"),
    chk_password: str = Form("chk123"),
    chk_phone: str = Form("9826033333"),
    vrv_name: str = Form("Mohanlal Soni (Varvand Cashier & Munim)"),
    vrv_username: str = Form("varvand_cashier"),
    vrv_password: str = Form("vrv123"),
    vrv_phone: str = Form("9826044444"),
    dhd_name: str = Form("Kailash Tiwari (Dhad Cashier & Munim)"),
    dhd_username: str = Form("dhad_cashier"),
    dhd_password: str = Form("dhd123"),
    dhd_phone: str = Form("9826055555")
):
    if is_system_setup_done():
        raise HTTPException(status_code=404, detail="System setup has already been completed. First-run provisioning is permanently closed.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        
        # Verify or provision signed commercial license token
        active_token = license_key.strip()
        if active_token == "RST-PRO-2026-MH3B-89A12F" or not active_token:
            active_token = DEFAULT_COMMERCIAL_LICENSE_TOKEN
        
        is_lic_valid, lic_msg, lic_payload = verify_license_token(active_token)
        if not is_lic_valid:
            return templates.TemplateResponse(request=request, name="setup.html", context={
                "settings": {"org_name": org_name, "org_gstin": org_gstin},
                "owner": {"full_name": owner_name, "username": owner_username, "phone": owner_phone},
                "accountant": {"full_name": acc_name, "username": acc_username, "phone": acc_phone},
                "chk_cashier": {"full_name": chk_name, "username": chk_username, "phone": chk_phone},
                "vrv_cashier": {"full_name": vrv_name, "username": vrv_username, "phone": vrv_phone},
                "dhd_cashier": {"full_name": dhd_name, "username": dhd_username, "phone": dhd_phone},
                "error_msg": f"Commercial License Verification Failed: {lic_msg}. Please provide a valid Ed25519-signed license token issued by Cresconic Technologies."
            }, status_code=400)

        tier_name = lic_payload.get("tier", "PRO")
        max_branches = lic_payload.get("max_branches", 3)
        exp_date = lic_payload.get("expires_at", license_valid_until)

        tier_display = tier_name.capitalize() if tier_name.upper() == "PRO" else tier_name
        settings_to_update = [
            ("org_name", org_name.strip()),
            ("org_gstin", org_gstin.strip()),
            ("license_token", active_token),
            ("license_key", lic_payload.get("license_id", "LIC-TOKEN")),
            ("license_status", f"Active ({tier_display} Tier - {max_branches} Branches)"),
            ("license_valid_until", "31-March-2027"),
            ("license_tier", f"{tier_display} Tier ({max_branches} Branches: Chikhali, Varvand, Dhad)"),
            ("license_branch_limit", str(max_branches)),
            ("is_setup_completed", "1")
        ]
        for k, v in settings_to_update:
            cur.execute("""
                INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) 
                VALUES ('SUPER_ADMIN', 'GLOBAL', ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(scope, scope_id, setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=CURRENT_TIMESTAMP
            """, (k, v))

        # Ensure licensed branch records exist up to max_branches
        branch_definitions = [
            ("br-chikhali", "BR-CHK", "Chikhali Branch", "MH/CHK/APMC-101", "APMC Market Yard, Chikhali (Buldhana)", "07264-242110"),
            ("br-varvand", "BR-VRV", "Varvand Branch", "MH/VRV/APMC-202", "Station Road, Varvand (Pune)", "02119-251220"),
            ("br-dhad", "BR-DHD", "Dhad Branch", "MH/DHD/APMC-303", "Main Market Yard, Dhad (Buldhana)", "07267-233330"),
        ]
        for b_id, b_code, b_name, b_lic, b_addr, b_phone in branch_definitions[:max_branches]:
            cur.execute("""
                INSERT INTO branches (id, branch_code, name, mandi_license_no, address, phone, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(id) DO UPDATE SET is_active=1
            """, (b_id, b_code, b_name, b_lic, b_addr, b_phone))

        # Helper to create or update staff members securely
        def provision_staff_user(user_id, branch_id, username, raw_password, full_name, phone, role):
            pwd_hash = hash_password(raw_password) if (raw_password and raw_password.strip()) else None
            cur.execute("SELECT id, password_hash FROM users WHERE role = ? AND (branch_id = ? OR (branch_id IS NULL AND ? IS NULL))", (role, branch_id, branch_id))
            existing = cur.fetchone()
            if existing:
                final_hash = pwd_hash if pwd_hash else existing["password_hash"]
                cur.execute("""
                    UPDATE users SET username=?, full_name=?, phone=?, password_hash=?, branch_id=?, is_active=1
                    WHERE id=?
                """, (username.strip(), full_name.strip(), phone.strip(), final_hash, branch_id, existing["id"]))
            else:
                if not pwd_hash:
                    pwd_hash = hash_password("admin123" if role == "SUPER_ADMIN" else "staff123")
                cur.execute("""
                    INSERT INTO users (id, branch_id, username, password_hash, full_name, phone, role, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (user_id, branch_id, username.strip(), pwd_hash, full_name.strip(), phone.strip(), role))

        # Provision Owner and Staff
        provision_staff_user("u-admin", None, owner_username, owner_password, owner_name, owner_phone, "SUPER_ADMIN")
        provision_staff_user("u-accountant", None, acc_username, acc_password, acc_name, acc_phone, "ACCOUNTANT_HQ")
        provision_staff_user("u-indore-cashier", "br-chikhali", chk_username, chk_password, chk_name, chk_phone, "BRANCH_CASHIER")
        if max_branches >= 2:
            provision_staff_user("u-ujjain-cashier", "br-varvand", vrv_username, vrv_password, vrv_name, vrv_phone, "BRANCH_CASHIER")
        if max_branches >= 3:
            provision_staff_user("u-dewas-cashier", "br-dhad", dhd_username, dhd_password, dhd_name, dhd_phone, "BRANCH_CASHIER")

        conn.commit()

        generated_creds = [
            {"role": "SUPER_ADMIN", "branch_name": "Central HQ", "full_name": owner_name.strip(), "username": owner_username.strip(), "plain_password": owner_password.strip() if owner_password else "(Unchanged / Admin Default)", "phone": owner_phone.strip()},
            {"role": "ACCOUNTANT_HQ", "branch_name": "Central HQ", "full_name": acc_name.strip(), "username": acc_username.strip(), "plain_password": acc_password.strip(), "phone": acc_phone.strip()},
            {"role": "BRANCH_CASHIER", "branch_name": "Chikhali Yard (BR-CHK)", "full_name": chk_name.strip(), "username": chk_username.strip(), "plain_password": chk_password.strip(), "phone": chk_phone.strip()},
            {"role": "BRANCH_CASHIER", "branch_name": "Varvand Yard (BR-VRV)", "full_name": vrv_name.strip(), "username": vrv_username.strip(), "plain_password": vrv_password.strip(), "phone": vrv_phone.strip()},
            {"role": "BRANCH_CASHIER", "branch_name": "Dhad Yard (BR-DHD)", "full_name": dhd_name.strip(), "username": dhd_username.strip(), "plain_password": dhd_password.strip(), "phone": dhd_phone.strip()},
        ]

        cur.execute("SELECT setting_key, setting_value FROM system_settings WHERE scope='SUPER_ADMIN'")
        settings = {r["setting_key"]: r["setting_value"] for r in cur.fetchall()}

        return templates.TemplateResponse(request=request, name="setup.html", context={
            "settings": settings,
            "owner": {"full_name": owner_name, "username": owner_username, "phone": owner_phone},
            "accountant": {"full_name": acc_name, "username": acc_username, "phone": acc_phone},
            "chk_cashier": {"full_name": chk_name, "username": chk_username, "phone": chk_phone},
            "vrv_cashier": {"full_name": vrv_name, "username": vrv_username, "phone": vrv_phone},
            "dhd_cashier": {"full_name": dhd_name, "username": dhd_username, "phone": dhd_phone},
            "success_msg": "Commercial License activated and all staff credentials provisioned successfully! Give the printed or noted credentials to staff.",
            "generated_creds": generated_creds
        })
    finally:
        conn.close()

@app.get("/login", response_class=HTMLResponse)
def login_view(request: Request):
    user = get_current_user(request)
    if user:
        role = user.get("role")
        if role == "SUPER_ADMIN":
            return RedirectResponse(url="/admin/dashboard", status_code=303)
        elif role == "ACCOUNTANT_HQ":
            return RedirectResponse(url="/accounts/dashboard", status_code=303)
        else:
            b_id = user.get("branch_id") or "br-chikhali"
            return RedirectResponse(url=f"/branch/dashboard?branch_id={b_id}", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"error": None})

@app.post("/login", response_class=HTMLResponse)
def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash, role, branch_id, is_active, full_name FROM users WHERE username = ?", (username.strip(),))
        user = cur.fetchone()
    finally:
        conn.close()

    if not user or not user["is_active"]:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid staff username or password. Please verify credentials or contact the owner.", "username": username},
            status_code=401
        )

    is_valid, needs_rehash = verify_password(password.strip(), user["password_hash"])
    if not is_valid:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid staff username or password. Please verify credentials or contact the owner.", "username": username},
            status_code=401
        )

    # Transparent in-flight migration to salted PBKDF2-HMAC-SHA256
    if needs_rehash:
        conn = get_connection()
        try:
            cur = conn.cursor()
            new_hash = hash_password(password.strip())
            cur.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user["id"]))
            conn.commit()
        finally:
            conn.close()

    role = user["role"]
    branch_id = user["branch_id"] or ""
    token = create_session_token(user["username"], role, branch_id, user_id=user["id"])

    if role == "SUPER_ADMIN":
        target_url = "/admin/dashboard"
    elif role == "ACCOUNTANT_HQ":
        target_url = "/accounts/dashboard"
    else:
        target_url = f"/branch/dashboard?branch_id={branch_id or 'br-chikhali'}"

    resp = RedirectResponse(url=target_url, status_code=303)
    resp.set_cookie(key="mandi_session", value=token, httponly=True, samesite="lax", path="/")
    return resp

@app.get("/logout")
def logout_view(request: Request):
    token = request.cookies.get("mandi_session")
    if token:
        sess = verify_session_token(token)
        if sess and sess.get("session_id"):
            revoke_user_session(sess["session_id"])
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(key="mandi_session", path="/")
    return resp


# --------------------------------------------------------------------------
# LEVEL 1: SUPER ADMIN PORTAL
# --------------------------------------------------------------------------

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page():
    return RedirectResponse(url="/login", status_code=303)

@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard_view(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") != "SUPER_ADMIN":
        if user.get("role") == "ACCOUNTANT_HQ":
            return RedirectResponse(url="/accounts/dashboard", status_code=303)
        else:
            b_id = user.get("branch_id") or "br-chikhali"
            return RedirectResponse(url=f"/branch/dashboard?branch_id={b_id}", status_code=303)
    logged_in_user = user

    today_str = date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Branches
        cur.execute("SELECT id, branch_code, name, address, mandi_license_no, phone, is_active FROM branches ORDER BY branch_code")
        branches = cur.fetchall()

        # Invoices
        cur.execute("""
            SELECT p.id, p.token_number, p.invoice_date, b.name as branch_name, 
                   pt.name as party_name, pt.party_type, p.commodity_name, 
                   p.net_quintals, p.rate_per_quintal, p.net_payable_amount, p.payout_status,
                   p.rtgs_utr_no, p.weighment_mode
            FROM purchase_invoices p
            JOIN branches b ON p.branch_id = b.id
            JOIN parties pt ON p.party_id = pt.id
            ORDER BY p.created_at DESC LIMIT 20
        """)
        invoices = cur.fetchall()

        # Users (Only Cashiers and Accountants - Munim role removed)
        cur.execute("""
            SELECT u.id, u.username, u.full_name, u.role, u.phone, u.is_active, b.name as branch_name
            FROM users u
            LEFT JOIN branches b ON u.branch_id = b.id
            WHERE u.role != 'BRANCH_MUNIM'
            ORDER BY u.role, u.username
        """)
        users = cur.fetchall()

        # Commodities Master
        cur.execute("SELECT id, name, hsn_code, standard_moisture_pct, mandi_cess_pct, is_active FROM commodities ORDER BY name")
        commodities = cur.fetchall()

        # 1. Commodity Stock Cards (If stock = 0, hide it! With avg buying price & branch quantity breakdown)
        cur.execute("""
            SELECT 
                c.name as commodity_name,
                c.hsn_code,
                COALESCE(SUM(p.net_quintals), 0.0) as inward_stock_qtl,
                COALESCE(SUM(p.gross_amount), 0.0) as total_gross_cost,
                COALESCE(SUM(p.net_payable_amount), 0.0) as total_payable_cost,
                COALESCE((SELECT SUM(o.net_quintals) FROM outward_orders o WHERE o.commodity_name = c.name AND o.status != 'CANCELLED'), 0.0) as outward_qtl
            FROM commodities c
            LEFT JOIN purchase_invoices p ON c.name = p.commodity_name AND p.payout_status != 'CANCELLED'
            GROUP BY c.name, c.hsn_code
            HAVING (inward_stock_qtl - outward_qtl) > 0
            ORDER BY (inward_stock_qtl - outward_qtl) DESC
        """)
        stock_rows = cur.fetchall()

        icon_map = {
            "Soyabean (Yellow)": "🌱",
            "Cotton / Kapas (कापूस)": "☁️",
            "Tur / Arhar (तूर)": "🍲",
            "Chana (Desi) / Harbhara (हरभरा)": "🫘",
            "Chana (Desi)": "🫘",
            "Wheat (Lokwan)": "🌾",
            "Mustard (Rayda)": "🌼",
            "Maize (Makka)": "🌽",
            "Moong (Green Gram)": "🟢",
            "Urad (Black Gram)": "⚫"
        }

        commodity_stock_cards = []
        total_portfolio_cost = 0.0
        total_portfolio_market_val = 0.0

        for sr in stock_rows:
            c_name = sr["commodity_name"]
            total_qtl = max(0.0, sr["inward_stock_qtl"] - sr["outward_qtl"])
            gross_cost = sr["total_gross_cost"]
            avg_buying_price = round(gross_cost / sr["inward_stock_qtl"], 2) if sr["inward_stock_qtl"] > 0 else 0.0

            # Today's market target rate for mark-to-market valuation & profit/loss
            cur.execute("""
                SELECT target_rate_per_qtl 
                FROM daily_commodity_rates 
                WHERE commodity_name=? AND rate_date=? 
                ORDER BY updated_at DESC LIMIT 1
            """, (c_name, today_str))
            rate_match = cur.fetchone()
            today_target_rate = rate_match["target_rate_per_qtl"] if rate_match else avg_buying_price

            market_val = round(total_qtl * today_target_rate, 2)
            current_holding_cost = round(total_qtl * avg_buying_price, 2)
            profit_loss = round(market_val - current_holding_cost, 2)
            pnl_pct = round((profit_loss / current_holding_cost * 100), 2) if current_holding_cost > 0 else 0.0

            total_portfolio_cost += current_holding_cost
            total_portfolio_market_val += market_val

            # Query which branch has how much quantity and at what rate
            cur.execute("""
                SELECT b.id, b.name as branch_name, b.branch_code, 
                       COALESCE(SUM(p.net_quintals), 0.0) as branch_inward_qtl,
                       COALESCE(SUM(p.gross_amount), 0.0) as branch_gross_cost,
                       COALESCE((SELECT SUM(o.net_quintals) FROM outward_orders o WHERE o.commodity_name = ? AND o.branch_id = b.id AND o.status != 'CANCELLED'), 0.0) as branch_outward_qtl
                FROM branches b
                LEFT JOIN purchase_invoices p ON p.branch_id = b.id AND p.commodity_name = ? AND p.payout_status != 'CANCELLED'
                GROUP BY b.id, b.name, b.branch_code
                HAVING (branch_inward_qtl - branch_outward_qtl) > 0
                ORDER BY (branch_inward_qtl - branch_outward_qtl) DESC
            """, (c_name, c_name))
            branch_rows = cur.fetchall()
            branch_breakdown = []
            for br in branch_rows:
                b_qtl = max(0.0, br["branch_inward_qtl"] - br["branch_outward_qtl"])
                b_avg_rate = round(br["branch_gross_cost"] / br["branch_inward_qtl"], 2) if br["branch_inward_qtl"] > 0 else 0.0
                b_stock_val = round(b_qtl * b_avg_rate, 2)
                b_pct = round((b_qtl / total_qtl) * 100, 1) if total_qtl > 0 else 0.0
                branch_breakdown.append({
                    "branch_name": br["branch_name"],
                    "branch_code": br["branch_code"],
                    "qty_qtl": b_qtl,
                    "qty_mt": round(b_qtl / 10.0, 2),
                    "pct": b_pct,
                    "branch_avg_rate": b_avg_rate,
                    "stock_val": b_stock_val
                })

            if total_qtl > 0:
                commodity_stock_cards.append({
                    "name": c_name,
                    "icon": icon_map.get(c_name, "📦"),
                    "hsn_code": sr["hsn_code"],
                    "total_stock_qtl": total_qtl,
                    "total_stock_mt": round(total_qtl / 10.0, 2),
                    "avg_buying_price": avg_buying_price,
                    "today_target_rate": today_target_rate,
                    "gross_cost": gross_cost,
                    "market_valuation": market_val,
                    "profit_loss": profit_loss,
                    "pnl_pct": pnl_pct,
                    "branch_breakdown": branch_breakdown,
                    "branch_json": json.dumps(branch_breakdown)
                })

        # Total Profit / Loss calculation
        total_pnl = round(total_portfolio_market_val - total_portfolio_cost, 2)
        total_pnl_pct = round((total_pnl / total_portfolio_cost * 100), 2) if total_portfolio_cost > 0 else 0.0

        # Overall Stats
        cur.execute("SELECT count(*) FROM branches WHERE is_active=1")
        branches_active = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM users WHERE is_active=1 AND role != 'BRANCH_MUNIM'")
        users_active = cur.fetchone()[0]

        cur.execute("SELECT COALESCE(SUM(net_quintals), 0.0), COALESCE(SUM(net_payable_amount), 0.0) FROM purchase_invoices WHERE payout_status != 'CANCELLED'")
        sum_row = cur.fetchone()
        total_quintals = sum_row[0]
        total_disbursed = sum_row[1]

        stats = {
            "branches_active": branches_active,
            "users_active": users_active,
            "total_quintals": total_quintals,
            "total_disbursed": total_disbursed,
            "commodities_count": len(commodities),
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "total_market_valuation": total_portfolio_market_val,
            "total_portfolio_cost": total_portfolio_cost,
            "active_stock_commodities_count": len(commodity_stock_cards)
        }
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "stats": stats,
            "branches": branches,
            "invoices": invoices,
            "users": users,
            "commodities": commodities,
            "commodity_stock_cards": commodity_stock_cards,
            "logged_in_user": logged_in_user
        }
    )

@app.post("/api/admin/login")
def api_admin_login(username: str = Form(...), password: str = Form(...)):
    res = login_admin(username, password)
    if not res.get("success"):
        raise HTTPException(status_code=401, detail=res.get("reason", "Authentication Failed"))
    return res

@app.post("/api/admin/branches")
def api_admin_add_branch(
    request: Request,
    branch_code: str = Form(...),
    name: str = Form(...),
    mandi_license_no: str = Form(""),
    address: str = Form(""),
    phone: str = Form("")
):
    require_role(request, ["SUPER_ADMIN"])
    conn = get_connection()
    try:
        allowed, msg, cur_cnt, max_cnt = check_branch_limit(conn)
        if not allowed:
            raise HTTPException(status_code=403, detail=msg)

        branch_id = f"br-{branch_code.lower().replace(' ', '-')}"
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO branches (id, branch_code, name, mandi_license_no, address, phone) VALUES (?,?,?,?,?,?)",
            (branch_id, branch_code.strip().upper(), name.strip(), mandi_license_no.strip(), address.strip(), phone.strip())
        )
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@app.post("/api/admin/branches/toggle")
def api_admin_toggle_branch(request: Request, branch_id: str = Form(...)):
    require_role(request, ["SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM branches WHERE id=?", (branch_id,))
        b_row = cur.fetchone()
        if b_row and b_row["is_active"] == 0:
            allowed, msg, cur_cnt, max_cnt = check_branch_limit(conn)
            if not allowed:
                raise HTTPException(status_code=403, detail=msg)
        cur.execute("UPDATE branches SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?", (branch_id,))
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@app.post("/api/admin/users")
def api_admin_add_user(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    phone: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    branch_id: Optional[str] = Form(None)
):
    require_role(request, ["SUPER_ADMIN"])
    # Only single-access Cashier and Accountant roles are supported
    if role not in ["SUPER_ADMIN", "ACCOUNTANT_HQ", "BRANCH_CASHIER"]:
        raise HTTPException(status_code=400, detail="Only BRANCH_CASHIER and ACCOUNTANT_HQ roles are permitted.")

    user_id = f"u-{uuid.uuid4().hex[:8]}"
    pw_hash = hash_password(password)
    actual_branch_id = branch_id if branch_id and branch_id.strip() else None

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (id, branch_id, username, password_hash, full_name, phone, role) VALUES (?,?,?,?,?,?,?)",
            (user_id, actual_branch_id, username.strip(), pw_hash, full_name.strip(), phone.strip(), role)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@app.post("/api/admin/users/toggle")
def api_admin_toggle_user(request: Request, user_id: str = Form(...)):
    require_role(request, ["SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=? AND role != 'SUPER_ADMIN'", (user_id,))
        revoke_user_sessions_by_user(user_id, conn=conn)
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/admin/dashboard", status_code=303)

@app.post("/api/admin/commodities")
def api_admin_add_commodity(
    request: Request,
    name: str = Form(...),
    hsn_code: str = Form(...),
    standard_moisture_pct: float = Form(10.0),
    mandi_cess_pct: float = Form(0.0)
):
    require_role(request, ["SUPER_ADMIN", "ACCOUNTANT_HQ"])
    cid = f"c-{uuid.uuid4().hex[:6]}"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO commodities (id, name, hsn_code, standard_moisture_pct, mandi_cess_pct) VALUES (?,?,?,?,?)",
            (cid, name.strip(), hsn_code.strip(), standard_moisture_pct, mandi_cess_pct)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()
    return RedirectResponse(url="/admin/dashboard", status_code=303)


# --------------------------------------------------------------------------
# LEVEL 2: CENTRAL ACCOUNTS PORTAL
# --------------------------------------------------------------------------

@app.get("/accounts/login", response_class=HTMLResponse)
def accounts_login_page():
    return RedirectResponse(url="/login", status_code=303)

@app.get("/accounts/dashboard", response_class=HTMLResponse)
def accounts_dashboard_view(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") == "BRANCH_CASHIER":
        b_id = user.get("branch_id") or "br-chikhali"
        return RedirectResponse(url=f"/branch/dashboard?branch_id={b_id}", status_code=303)
    logged_in_user = user

    today_str = date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Daily rates
        cur.execute("""
            SELECT id, rate_date, commodity_name, quality_grade, 
                   min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl, updated_at 
            FROM daily_commodity_rates 
            ORDER BY rate_date DESC, commodity_name ASC
        """)
        rates = cur.fetchall()

        # Pending rate overrides
        cur.execute("""
            SELECT p.id, p.token_number, b.name as branch_name, pt.name as party_name,
                   p.commodity_name, p.net_quintals, p.rate_per_quintal, p.rate_override_reason
            FROM purchase_invoices p
            JOIN branches b ON p.branch_id = b.id
            JOIN parties pt ON p.party_id = pt.id
            WHERE p.rate_override_status = 'PENDING'
            ORDER BY p.created_at ASC
        """)
        pending_overrides = cur.fetchall()

        # Inspectors
        cur.execute("""
            SELECT i.id, i.name, i.designation, i.phone, i.is_active, b.name as branch_name
            FROM inspectors i
            LEFT JOIN branches b ON i.branch_id = b.id
            ORDER BY i.name ASC
        """)
        inspectors = cur.fetchall()

        # Commodities
        cur.execute("SELECT id, name FROM commodities WHERE is_active=1 ORDER BY name ASC")
        commodities = cur.fetchall()

        rates_map = {r["commodity_name"]: dict(r) for r in rates}
        commodity_cards = []
        for c in commodities:
            c_dict = dict(c)
            rate_info = rates_map.get(c["name"])
            if rate_info:
                c_dict["min_rate"] = rate_info["min_rate_per_qtl"]
                c_dict["target_rate"] = rate_info["target_rate_per_qtl"]
                c_dict["max_rate"] = rate_info["max_rate_per_qtl"]
                c_dict["grade"] = rate_info.get("quality_grade", "STANDARD")
            else:
                c_dict["min_rate"] = 0.0
                c_dict["target_rate"] = 0.0
                c_dict["max_rate"] = 0.0
                c_dict["grade"] = "STANDARD"
            commodity_cards.append(c_dict)

        # Branches
        cur.execute("SELECT id, name FROM branches WHERE is_active=1 ORDER BY name ASC")
        branches = cur.fetchall()

        # Ledgers
        cur.execute("""
            SELECT l.id, l.transaction_date, b.name as branch_name, l.voucher_type,
                   l.voucher_id, l.account_name, l.debit_amount, l.credit_amount, l.narration
            FROM ledger_entries l
            JOIN branches b ON l.branch_id = b.id
            ORDER BY l.created_at DESC LIMIT 25
        """)
        ledgers = cur.fetchall()

        # Pending RTGS Transfer Requests from Branches
        cur.execute("""
            SELECT p.id, p.token_number, p.invoice_date, b.name as branch_name,
                   pt.name as party_name, pt.phone as party_phone,
                   p.commodity_name, p.net_quintals, p.net_payable_amount,
                   p.rtgs_bank_name, p.rtgs_account_no, p.rtgs_ifsc_code, p.rtgs_beneficiary_name,
                   p.rtgs_requested_at
            FROM purchase_invoices p
            JOIN branches b ON p.branch_id = b.id
            JOIN parties pt ON p.party_id = pt.id
            WHERE p.payout_status = 'RTGS_PENDING'
            ORDER BY p.rtgs_requested_at ASC
        """)
        pending_rtgs = cur.fetchall()

        # Outward Orders & Payment Settlement Receivables
        cur.execute("""
            SELECT o.*, b.name as branch_name, pb.name as payment_branch_name
            FROM outward_orders o
            JOIN branches b ON o.branch_id = b.id
            LEFT JOIN branches pb ON o.payment_branch_id = pb.id
            ORDER BY o.order_date DESC, o.created_at DESC
        """)
        outward_orders_rows = cur.fetchall()
        outward_orders = [dict(r) for r in outward_orders_rows]
        total_outward_billed = sum(o.get("total_bill_amount", 0.0) for o in outward_orders)
        total_outward_received = sum(o.get("total_bill_amount", 0.0) for o in outward_orders if o.get("payment_status") == "RECEIVED")
        total_outward_pending = total_outward_billed - total_outward_received
        pending_outward_count = sum(1 for o in outward_orders if o.get("payment_status") != "RECEIVED")

    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="accounts_dashboard.html",
        context={
            "today_str": today_str,
            "rates": rates,
            "pending_overrides": pending_overrides,
            "pending_rtgs": pending_rtgs,
            "inspectors": inspectors,
            "commodities": commodities,
            "commodity_cards": commodity_cards,
            "branches": branches,
            "ledgers": ledgers,
            "outward_orders": outward_orders,
            "total_outward_billed": total_outward_billed,
            "total_outward_received": total_outward_received,
            "total_outward_pending": total_outward_pending,
            "pending_outward_count": pending_outward_count,
            "logged_in_user": logged_in_user
        }
    )

@app.post("/api/accounts/rates")
def api_accounts_set_rate(
    request: Request,
    rate_date: str = Form(...),
    commodity_name: str = Form(...),
    quality_grade: str = Form("STANDARD"),
    min_rate: float = Form(...),
    target_rate: float = Form(...),
    max_rate: float = Form(...),
    branch_id: Optional[str] = Form(None)
):
    require_role(request, ["ACCOUNTANT_HQ", "SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM daily_commodity_rates 
            WHERE rate_date=? AND commodity_name=? AND quality_grade=? AND (branch_id=? OR (branch_id IS NULL AND ? IS NULL))
        """, (rate_date, commodity_name, quality_grade, branch_id, branch_id))
        row = cur.fetchone()

        if row:
            cur.execute("""
                UPDATE daily_commodity_rates 
                SET min_rate_per_qtl=?, target_rate_per_qtl=?, max_rate_per_qtl=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (min_rate, target_rate, max_rate, row["id"]))
        else:
            rid = f"r-{uuid.uuid4().hex[:8]}"
            cur.execute("""
                INSERT INTO daily_commodity_rates (id, rate_date, branch_id, commodity_name, quality_grade, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl)
                VALUES (?,?,?,?,?,?,?,?)
            """, (rid, rate_date, branch_id, commodity_name, quality_grade, min_rate, target_rate, max_rate))

        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url="/accounts/dashboard", status_code=303)

@app.post("/api/accounts/rate-overrides/action")
def api_accounts_rate_override_action(
    request: Request,
    invoice_id: str = Form(...),
    decision: str = Form(...),  # APPROVE or REJECT
    accountant_reason: str = Form(...)
):
    require_role(request, ["ACCOUNTANT_HQ", "SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        if decision == "APPROVE":
            cur.execute("""
                UPDATE purchase_invoices 
                SET rate_override_status='APPROVED', is_rate_overridden=1, rate_override_reason = rate_override_reason || ' | HQ Approved: ' || ?
                WHERE id=?
            """, (accountant_reason, invoice_id))
        else:
            cur.execute("""
                UPDATE purchase_invoices 
                SET rate_override_status='REJECTED', payout_status='CANCELLED', rate_override_reason = rate_override_reason || ' | HQ Rejected: ' || ?
                WHERE id=?
            """, (accountant_reason, invoice_id))
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url="/accounts/dashboard", status_code=303)

@app.post("/api/accounts/rtgs/process")
def api_accounts_process_rtgs(
    request: Request,
    invoice_id: str = Form(...),
    bank_utr_no: str = Form(...)
):
    require_role(request, ["ACCOUNTANT_HQ", "SUPER_ADMIN"])
    if not bank_utr_no or not bank_utr_no.strip():
        raise HTTPException(status_code=400, detail="Bank UTR / Transaction Reference Number is mandatory to close RTGS request.")

    utr = bank_utr_no.strip()
    today_str = date.today().isoformat()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM purchase_invoices WHERE id=?", (invoice_id,))
        inv = cur.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice record not found.")

        if inv["payout_status"] == "PAID":
            raise HTTPException(status_code=400, detail="Invoice has already been settled.")

        # 1. Update purchase_invoices with UTR and mark PAID
        cur.execute("""
            UPDATE purchase_invoices 
            SET payout_status = 'PAID',
                rtgs_utr_no = ?,
                rtgs_completed_at = CURRENT_TIMESTAMP,
                rounded_net_payable = net_payable_amount
            WHERE id = ?
        """, (utr, invoice_id))

        # 2. Record payout in cashier_payouts table
        payout_id = f"pay-rtgs-{uuid.uuid4().hex[:8]}"
        cur.execute("""
            INSERT INTO cashier_payouts (
                id, branch_id, invoice_id, party_id, payout_mode, amount_paid,
                bank_utr_no, cashier_user_id
            ) VALUES (?, ?, ?, ?, 'BANK_TRANSFER', ?, ?, 'u-accountant')
        """, (payout_id, inv["branch_id"], invoice_id, inv["party_id"], inv["net_payable_amount"], utr))

        # 3. Create double-entry ledger entry
        cur.execute("""
            INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, credit_amount, narration)
            VALUES (?, ?, ?, 'RTGS_PAYMENT', ?, 'Mandi Central Bank Account', ?, 0, ?, ?)
        """, (f"led-{uuid.uuid4().hex[:6]}", inv["branch_id"], today_str, inv["token_number"], inv["party_id"], inv["net_payable_amount"], f"RTGS Bank Transfer Disbursed to {inv['rtgs_beneficiary_name'] or 'Farmer'} | UTR: {utr}"))

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

    return RedirectResponse(url="/accounts/dashboard", status_code=303)

@app.post("/api/accounts/outward/receive-payment")
def api_accounts_receive_outward_payment(
    request: Request,
    challan_id: str = Form(...),
    payment_mode: str = Form(...),  # "RTGS" or "CASH"
    receipt_date: str = Form(...),
    utr_number: Optional[str] = Form(None),
    payment_branch_id: Optional[str] = Form(None),
    payment_notes: Optional[str] = Form("")
):
    require_role(request, ["ACCOUNTANT_HQ", "SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT o.*, b.name as branch_name FROM outward_orders o JOIN branches b ON o.branch_id=b.id WHERE o.id=?", (challan_id,))
        challan = cur.fetchone()
        if not challan:
            raise HTTPException(status_code=404, detail="Outward order record not found.")

        mode = payment_mode.strip().upper()
        clean_utr = utr_number.strip() if utr_number and utr_number.strip() else None
        clean_branch = payment_branch_id.strip() if payment_branch_id and payment_branch_id.strip() else None

        if mode == "RTGS":
            if not clean_utr:
                raise HTTPException(status_code=400, detail="Bank UTR Number is strictly required for RTGS payment receipt.")
            clean_branch = None
        elif mode == "CASH":
            if not clean_branch:
                raise HTTPException(status_code=400, detail="Receiving Branch is required for Cash payment receipt.")
            clean_utr = None
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported payment mode: {mode}")

        cur.execute("""
            UPDATE outward_orders
            SET payment_status = 'RECEIVED',
                payment_mode = ?,
                utr_number = ?,
                payment_branch_id = ?,
                payment_received_date = ?,
                payment_received_by = 'Omprakash Agrawal (Chief Accountant)',
                payment_notes = ?
            WHERE id = ?
        """, (mode, clean_utr, clean_branch, receipt_date, (payment_notes or "").strip(), challan_id))

        bill_amount = challan["total_bill_amount"]
        challan_no = challan["challan_number"]
        buyer = challan["buyer_name"]

        # Double entry ledger creation
        if mode == "RTGS":
            cur.execute("""
                INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, debit_amount, credit_amount, narration)
                VALUES (?, ?, ?, 'OUTWARD_RECEIPT', ?, 'Mandi Central Bank Account', ?, 0, ?)
            """, (f"led-{uuid.uuid4().hex[:6]}", challan["branch_id"], receipt_date, challan_no, bill_amount, f"RTGS payment received from {buyer} for Challan {challan_no} | UTR: {clean_utr}"))
        else:
            cur.execute("SELECT name FROM branches WHERE id=?", (clean_branch,))
            rcv_branch = cur.fetchone()
            rcv_b_name = rcv_branch["name"] if rcv_branch else "Branch"
            cur.execute("""
                INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, debit_amount, credit_amount, narration)
                VALUES (?, ?, ?, 'OUTWARD_RECEIPT', ?, ?, ?, 0, ?)
            """, (f"led-{uuid.uuid4().hex[:6]}", clean_branch, receipt_date, challan_no, f"Branch Cash Drawer ({rcv_b_name})", bill_amount, f"Cash payment received at {rcv_b_name} from {buyer} for Challan {challan_no}"))

            # Update cash drawer for receiving branch
            cur.execute("""
                UPDATE branch_daily_cash_drawers
                SET bank_withdrawals_inward = bank_withdrawals_inward + ?,
                    calculated_closing_cash = calculated_closing_cash + ?
                WHERE branch_id=? AND record_date=?
            """, (bill_amount, bill_amount, clean_branch, receipt_date))

        # Audit change log
        cur.execute("""
            INSERT INTO audit_change_logs (id, entity_type, entity_id, entity_name, branch_id, changed_by, action, change_summary)
            VALUES (?, 'OUTWARD_ORDER', ?, ?, ?, 'accountant', 'PAYMENT_RECEIVED', ?)
        """, (f"log-{uuid.uuid4().hex[:8]}", challan_no, buyer, challan["branch_id"], f"Accountant marked payment RECEIVED via {mode} ({clean_utr or clean_branch}) for ₹{bill_amount:,.2f}"))

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

    return RedirectResponse(url="/accounts/dashboard", status_code=303)

@app.post("/api/accounts/inspectors")
def api_accounts_add_inspector(
    request: Request,
    name: str = Form(...),
    designation: str = Form(...),
    phone: str = Form(""),
    branch_id: Optional[str] = Form(None)
):
    require_role(request, ["ACCOUNTANT_HQ", "SUPER_ADMIN"])
    iid = f"ins-{uuid.uuid4().hex[:6]}"
    actual_branch_id = branch_id if branch_id and branch_id.strip() else None
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO inspectors (id, branch_id, name, designation, phone) VALUES (?,?,?,?,?)",
            (iid, actual_branch_id, name.strip(), designation.strip(), phone.strip())
        )
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url="/accounts/dashboard", status_code=303)

@app.post("/api/accounts/inspectors/toggle")
def api_accounts_toggle_inspector(request: Request, inspector_id: str = Form(...)):
    require_role(request, ["ACCOUNTANT_HQ", "SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE inspectors SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?", (inspector_id,))
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url="/accounts/dashboard", status_code=303)


# --------------------------------------------------------------------------
# LEVEL 3: BRANCH DASHBOARD & YARD OPERATIONS
# --------------------------------------------------------------------------

@app.get("/branch/login", response_class=HTMLResponse)
def branch_login_page():
    return RedirectResponse(url="/login", status_code=303)

@app.get("/branch/dashboard", response_class=HTMLResponse)
def branch_dashboard_view(request: Request, branch_id: str = "br-chikhali"):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") == "BRANCH_CASHIER":
        assigned_branch = user.get("branch_id")
        if assigned_branch and branch_id != assigned_branch:
            return RedirectResponse(url=f"/branch/dashboard?branch_id={assigned_branch}", status_code=303)
        actual_req_branch = assigned_branch or branch_id
    elif user.get("role") == "ACCOUNTANT_HQ":
        return RedirectResponse(url="/accounts/dashboard", status_code=303)
    elif user.get("role") == "SUPER_ADMIN":
        actual_req_branch = branch_id
    else:
        return RedirectResponse(url="/login", status_code=303)
    logged_in_user = user

    today_str = date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Active Branch
        cur.execute("SELECT id, branch_code, name, mandi_license_no FROM branches WHERE id=?", (actual_req_branch,))
        current_branch = cur.fetchone()
        if not current_branch:
            # Fallback to first branch
            cur.execute("SELECT id, branch_code, name, mandi_license_no FROM branches LIMIT 1")
            current_branch = cur.fetchone()

        actual_branch_id = current_branch["id"]

        # Branches list
        cur.execute("SELECT id, branch_code, name FROM branches WHERE is_active=1 ORDER BY branch_code")
        branches = cur.fetchall()

        # Parties (Farmers & Stockers for this branch or universal)
        cur.execute("""
            SELECT id, name, phone, party_type, village, khasra_record_no, current_advance 
            FROM parties 
            WHERE home_branch_id=? OR home_branch_id IS NULL
            ORDER BY party_type, name ASC
        """, (actual_branch_id,))
        parties = cur.fetchall()

        # Quality Inspectors for this branch or universal (filled by Central Accounts!)
        cur.execute("""
            SELECT id, name, designation FROM inspectors 
            WHERE is_active=1 AND (branch_id=? OR branch_id IS NULL)
            ORDER BY name ASC
        """, (actual_branch_id,))
        inspectors = cur.fetchall()

        # Commodities
        cur.execute("SELECT id, name, standard_moisture_pct, mandi_cess_pct FROM commodities WHERE is_active=1 ORDER BY name ASC")
        commodities = cur.fetchall()

        # Today's daily rates (falls back to latest published corridor if today's not yet set)
        cur.execute("""
            SELECT commodity_name, quality_grade, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl 
            FROM daily_commodity_rates 
            WHERE rate_date=? AND (branch_id=? OR branch_id IS NULL)
            ORDER BY commodity_name
        """, (today_str, actual_branch_id))
        daily_rates = cur.fetchall()
        if not daily_rates:
            cur.execute("""
                SELECT commodity_name, quality_grade, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl 
                FROM daily_commodity_rates 
                WHERE (branch_id=? OR branch_id IS NULL)
                GROUP BY commodity_name
                HAVING MAX(rate_date)
                ORDER BY commodity_name
            """, (actual_branch_id,))
            daily_rates = cur.fetchall()

        daily_rates_list = [dict(r) for r in daily_rates]
        rates_map = {r["commodity_name"]: dict(r) for r in daily_rates}

        commodity_cards = []
        for c in commodities:
            c_dict = dict(c)
            rate_info = rates_map.get(c["name"])
            if rate_info:
                c_dict["min_rate"] = rate_info["min_rate_per_qtl"]
                c_dict["target_rate"] = rate_info["target_rate_per_qtl"]
                c_dict["max_rate"] = rate_info["max_rate_per_qtl"]
                c_dict["grade"] = rate_info.get("quality_grade", "STANDARD")
            else:
                c_dict["min_rate"] = 0.0
                c_dict["target_rate"] = 0.0
                c_dict["max_rate"] = 0.0
                c_dict["grade"] = "STANDARD"

            # Query branch physical yard stock and average buying rate for this commodity
            cur.execute("""
                SELECT COALESCE(SUM(net_quintals), 0.0) as inw_qtl,
                       COALESCE(SUM(gross_amount), 0.0) as inw_cost
                FROM purchase_invoices
                WHERE branch_id=? AND commodity_name=? AND payout_status != 'CANCELLED'
            """, (actual_branch_id, c["name"]))
            inw = cur.fetchone()
            inw_qtl = inw["inw_qtl"] if inw else 0.0
            inw_cost = inw["inw_cost"] if inw else 0.0

            cur.execute("""
                SELECT COALESCE(SUM(net_quintals), 0.0) as outw_qtl
                FROM outward_orders
                WHERE branch_id=? AND commodity_name=? AND status != 'CANCELLED'
            """, (actual_branch_id, c["name"]))
            outw = cur.fetchone()
            outw_qtl = outw["outw_qtl"] if outw else 0.0

            net_qtl = max(0.0, inw_qtl - outw_qtl)
            c_dict["yard_stock_qtl"] = round(net_qtl, 2)
            c_dict["yard_stock_mt"] = round(net_qtl / 10.0, 2)
            c_dict["avg_buying_price"] = round(inw_cost / inw_qtl, 2) if inw_qtl > 0 else 0.0

            commodity_cards.append(c_dict)

        # Pending payouts & RTGS status
        cur.execute("""
            SELECT p.id, p.token_number, p.invoice_date, pt.name as party_name, pt.party_type,
                   pt.bank_name, pt.bank_account_no, pt.bank_ifsc,
                   p.commodity_name, p.net_quintals, p.net_payable_amount, p.rate_override_status, p.payout_status,
                   p.rtgs_bank_name, p.rtgs_account_no, p.rtgs_ifsc_code, p.rtgs_utr_no, p.weighment_mode
            FROM purchase_invoices p
            JOIN parties pt ON p.party_id = pt.id
            WHERE p.branch_id=? AND p.payout_status IN ('PENDING', 'RTGS_PENDING')
            ORDER BY p.created_at DESC
        """, (actual_branch_id,))
        pending_payouts = cur.fetchall()

        # Recent branch purchases
        cur.execute("""
            SELECT p.id, p.token_number, p.invoice_date, pt.name as party_name,
                   p.commodity_name, p.net_quintals, p.rate_per_quintal, p.net_payable_amount, p.payout_status,
                   p.rtgs_bank_name, p.rtgs_account_no, p.rtgs_ifsc_code, p.rtgs_utr_no, p.weighment_mode
            FROM purchase_invoices p
            JOIN parties pt ON p.party_id = pt.id
            WHERE p.branch_id=?
            ORDER BY p.created_at DESC LIMIT 30
        """, (actual_branch_id,))
        recent_invoices = cur.fetchall()

        # Recent branch outward dispatches
        cur.execute("""
            SELECT id, challan_number, order_date, buyer_name, commodity_name, vehicle_number,
                   net_weight_kg, net_quintals, rate_per_quintal, hamali_per_100kg, hamali_amount,
                   gross_amount, total_bill_amount, status
            FROM outward_orders
            WHERE branch_id=?
            ORDER BY created_at DESC LIMIT 30
        """, (actual_branch_id,))
        recent_outward_orders = cur.fetchall()

        # All RTGS Transfer Invoices for this branch (both pending and completed with UTR)
        cur.execute("""
            SELECT p.id, p.token_number, p.invoice_date, pt.name as party_name, pt.phone as party_phone,
                   p.commodity_name, p.net_quintals, p.net_payable_amount,
                   p.rtgs_bank_name, p.rtgs_account_no, p.rtgs_ifsc_code, p.rtgs_beneficiary_name,
                   p.rtgs_utr_no, p.payout_status, p.rtgs_requested_at, p.rtgs_completed_at
            FROM purchase_invoices p
            JOIN parties pt ON p.party_id = pt.id
            WHERE p.branch_id=? AND (p.payout_status = 'RTGS_PENDING' OR p.rtgs_utr_no IS NOT NULL)
            ORDER BY p.invoice_date DESC, p.created_at DESC
        """, (actual_branch_id,))
        branch_rtgs_list = [dict(r) for r in cur.fetchall()]
        branch_rtgs_pending_count = sum(1 for r in branch_rtgs_list if r.get("payout_status") == "RTGS_PENDING")

        # Registered Buyers
        cur.execute("""
            SELECT id, name, phone, village, gstin, pan_number, khasra_record_no as contact_person,
                   bank_name, bank_account_no, bank_ifsc, created_at
            FROM parties 
            WHERE party_type IN ('STOCKER', 'BUYER') 
            ORDER BY name ASC
        """)
        buyers = cur.fetchall()

        # Cash Drawer for today
        cur.execute("SELECT * FROM branch_daily_cash_drawers WHERE branch_id=? AND record_date=?", (actual_branch_id, today_str))
        drawer_row = cur.fetchone()
        if not drawer_row:
            # Seed / initialize drawer
            cur.execute("""
                INSERT OR IGNORE INTO branch_daily_cash_drawers 
                (id, branch_id, record_date, opening_float, total_cash_payouts, petty_expenses_cash, bank_withdrawals_inward, calculated_closing_cash, physical_counted_cash)
                VALUES (?, ?, ?, 500000.0, 0.0, 0.0, 0.0, 500000.0, 500000.0)
            """, (f"drw-{actual_branch_id}-{today_str}", actual_branch_id, today_str))
            conn.commit()
            cur.execute("SELECT * FROM branch_daily_cash_drawers WHERE branch_id=? AND record_date=?", (actual_branch_id, today_str))
            drawer_row = cur.fetchone()

        drawer = dict(drawer_row) if drawer_row else {
            "opening_float": 500000.0,
            "total_cash_payouts": 0.0,
            "petty_expenses_cash": 0.0,
            "bank_withdrawals_inward": 0.0,
            "calculated_closing_cash": 500000.0
        }

    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="branch_dashboard.html",
        context={
            "current_branch": current_branch,
            "branches": branches,
            "parties": parties,
            "buyers": buyers,
            "inspectors": inspectors,
            "commodities": commodities,
            "commodity_cards": commodity_cards,
            "daily_rates": daily_rates,
            "daily_rates_json": json.dumps(daily_rates_list),
            "pending_payouts": pending_payouts,
            "recent_invoices": recent_invoices,
            "recent_outward_orders": recent_outward_orders,
            "branch_rtgs_list": branch_rtgs_list,
            "branch_rtgs_pending_count": branch_rtgs_pending_count,
            "drawer": drawer,
            "logged_in_user": logged_in_user
        }
    )


# --------------------------------------------------------------------------
# API ENDPOINTS: INVOICE GENERATION & CALCULATION
# --------------------------------------------------------------------------

@app.post("/api/invoices/calculate")
@app.get("/api/invoices/calculate")
@app.get("/api/calculate-inward")
def api_calculate_inward(
    gross_weight_kg: float = 0.0,
    vehicle_tare_kg: float = 0.0,
    bag_count: int = 0,
    rate_per_quintal: float = 0.0,
    moisture_percentage: float = 0.0,
    karda_percentage: float = 0.0,
    bag_type: str = "LOOSE",
    advance_to_deduct: float = 0.0,
    hamali_rate_per_100kg: float = 25.0
):
    return calculate_inward_invoice(
        gross_weight_kg=gross_weight_kg,
        vehicle_tare_kg=vehicle_tare_kg,
        bag_count=bag_count,
        bag_type=bag_type,
        moisture_percentage=moisture_percentage,
        karda_percentage=karda_percentage,
        rate_per_quintal=rate_per_quintal,
        hamali_rate_per_100kg=hamali_rate_per_100kg,
        mandi_cess_percentage=0.0,
        tulai_rate_per_bag=0.0,
        silai_rate_per_bag=0.0,
        bardana_rate_per_bag=0.0,
        advance_to_deduct=advance_to_deduct
    )

@app.post("/api/branch/invoices/create")
def api_branch_create_invoice(
    request: Request,
    branch_id: str = Form(...),
    party_id: str = Form(...),
    inspector_name: str = Form(...),
    commodity_name: str = Form(...),
    rate_per_quintal: float = Form(...),
    weighment_mode: str = Form("MANUAL_YARD"),  # MANUAL_YARD or WEIGHBRIDGE
    yard_weight_kg: Optional[float] = Form(None),
    gross_weight_kg: Optional[float] = Form(None),
    vehicle_tare_kg: Optional[float] = Form(0.0),
    external_kanta_name: Optional[str] = Form(""),
    external_slip_number: Optional[str] = Form(""),
    vehicle_number: Optional[str] = Form(""),
    bag_type: Optional[str] = Form("LOOSE"),
    bag_count: Optional[int] = Form(0),
    moisture_percentage: float = Form(0.0),
    karda_percentage: Optional[float] = Form(0.0),
    rate_override_reason: Optional[str] = Form(""),
    advance_to_deduct: Optional[float] = Form(0.0),
    # Cashier Immediate Settlement Parameters (Merged Desk)
    settlement_mode: str = Form("PENDING"),  # PENDING, CASH, or RTGS
    notes_500: int = Form(0),
    notes_200: int = Form(0),
    notes_100: int = Form(0),
    notes_50: int = Form(0),
    notes_20: int = Form(0),
    notes_10: int = Form(0),
    coins: int = Form(0),
    rtgs_bank_name: Optional[str] = Form(""),
    rtgs_account_no: Optional[str] = Form(""),
    rtgs_ifsc_code: Optional[str] = Form(""),
    rtgs_beneficiary_name: Optional[str] = Form(""),
    cashier_user_id: Optional[str] = Form("cashier")
):
    require_active_license()
    user = require_role(request, ["BRANCH_CASHIER", "SUPER_ADMIN"])
    if user.get("role") == "BRANCH_CASHIER":
        assigned_branch = user.get("branch_id")
        if assigned_branch:
            branch_id = assigned_branch
        cashier_user_id = user.get("user_id") or user.get("username") or cashier_user_id

    today_str = date.today().isoformat()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determine effective gross and tare weights based on mode
    if weighment_mode == "MANUAL_YARD":
        eff_gross = yard_weight_kg if (yard_weight_kg is not None and yard_weight_kg > 0) else (gross_weight_kg or 0.0)
        eff_tare = 0.0
        eff_kanta = "Yard Scale"
        eff_slip = "YARD-DIRECT"
    else:
        eff_gross = gross_weight_kg or 0.0
        eff_tare = vehicle_tare_kg or 0.0
        eff_kanta = external_kanta_name or "Dharamkanta"
        eff_slip = external_slip_number or "WB-ENTRY"

    eff_bag_count = bag_count or 0
    eff_bag_type = bag_type or "LOOSE"
    eff_karda = karda_percentage or 0.0
    eff_advance = advance_to_deduct or 0.0

    # 1. Calculation Engine: Mandi rule = Hamali ₹25 on 100 kg, Mandi cess = 0.0
    calc = calculate_inward_invoice(
        gross_weight_kg=eff_gross,
        vehicle_tare_kg=eff_tare,
        bag_count=eff_bag_count,
        bag_type=eff_bag_type,
        moisture_percentage=moisture_percentage,
        karda_percentage=eff_karda,
        rate_per_quintal=rate_per_quintal,
        hamali_rate_per_100kg=25.0,
        mandi_cess_percentage=0.0,
        tulai_rate_per_bag=0.0,
        silai_rate_per_bag=0.0,
        bardana_rate_per_bag=0.0,
        advance_to_deduct=eff_advance
    )

    # 2. Daily Rate Corridor Validation
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT min_rate_per_qtl, max_rate_per_qtl 
            FROM daily_commodity_rates 
            WHERE commodity_name=? AND (branch_id=? OR branch_id IS NULL)
            ORDER BY CASE WHEN rate_date=? THEN 0 ELSE 1 END, rate_date DESC
            LIMIT 1
        """, (commodity_name, branch_id, today_str))
        rate_row = cur.fetchone()

        is_rate_overridden = 0
        rate_override_status = "NONE"

        if rate_row:
            check = check_rate_corridor(rate_per_quintal, rate_row["min_rate_per_qtl"], rate_row["max_rate_per_qtl"])
            if check["requires_override"]:
                is_rate_overridden = 1
                rate_override_status = "PENDING"

        # Generate Unique Mandi Token: e.g. IND-20261028-0042
        cur.execute("SELECT branch_code FROM branches WHERE id=?", (branch_id,))
        b_code_row = cur.fetchone()
        b_code = b_code_row["branch_code"].replace("BR-", "") if b_code_row else "BR"
        token_date = datetime.now().strftime("%Y%m%d")

        cur.execute("SELECT count(*) as cnt FROM purchase_invoices WHERE branch_id=? AND invoice_date=?", (branch_id, today_str))
        seq = cur.fetchone()["cnt"] + 1
        token_number = f"{b_code}-{token_date}-{seq:04d}"
        invoice_id = f"inv-{uuid.uuid4().hex[:10]}"

        # Look up commodity HSN
        cur.execute("SELECT hsn_code FROM commodities WHERE name=?", (commodity_name,))
        hsn_row = cur.fetchone()
        hsn_code = hsn_row["hsn_code"] if hsn_row else "1201"

        # Rounding values
        roundup = calculate_cash_payout_with_roundup(calc["net_payable_amount"])
        payable_rounded = roundup["rounded_cash_payout"]

        # Determine effective payout status based on unified settlement mode
        effective_payout_status = "PENDING"
        if settlement_mode == "CASH":
            if payable_rounded >= 200000.0:
                # Statutory Section 269ST ceiling -> force RTGS
                settlement_mode = "RTGS"
                effective_payout_status = "RTGS_PENDING"
            else:
                effective_payout_status = "PAID"
        elif settlement_mode == "RTGS":
            effective_payout_status = "RTGS_PENDING"

        # Insert Invoice Record
        cur.execute("""
            INSERT INTO purchase_invoices (
                id, branch_id, token_number, invoice_date, party_id, commodity_name, hsn_code,
                quality_grade, vehicle_number, weighment_mode, external_kanta_name, external_slip_number,
                bag_count, bag_type, gross_weight_kg, vehicle_tare_kg, bag_tare_kg,
                moisture_percentage, moisture_cut_kg, karda_percentage, karda_cut_kg,
                net_weight_kg, net_quintals, rate_per_quintal, is_rate_overridden,
                rate_override_status, rate_override_reason, gross_amount,
                hamali_charge, tulai_charge, silai_charge, bardana_deduction, mandi_cess_amount,
                advance_adjusted, interest_adjusted, net_payable_amount, rounded_net_payable,
                round_off_amount, payout_status, inspector_name,
                rtgs_bank_name, rtgs_account_no, rtgs_ifsc_code, rtgs_beneficiary_name, rtgs_requested_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                'STANDARD', ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?
            )
        """, (
            invoice_id, branch_id, token_number, today_str, party_id, commodity_name, hsn_code,
            vehicle_number or "", weighment_mode, eff_kanta, eff_slip,
            eff_bag_count, eff_bag_type, eff_gross, eff_tare, calc["bag_tare_kg"],
            moisture_percentage, calc["moisture_cut_kg"], eff_karda, calc["karda_cut_kg"],
            calc["net_weight_kg"], calc["net_quintals"], rate_per_quintal, is_rate_overridden,
            rate_override_status, rate_override_reason or "", calc["gross_amount"],
            calc["hamali_charge"], calc["tulai_charge"], calc["silai_charge"], calc["bardana_deduction"], calc["mandi_cess_amount"],
            calc["advance_adjusted"], calc["interest_adjusted"], calc["net_payable_amount"], payable_rounded,
            roundup["round_off_amount"], effective_payout_status, inspector_name,
            rtgs_bank_name.strip() if rtgs_bank_name else "",
            rtgs_account_no.strip() if rtgs_account_no else "",
            rtgs_ifsc_code.strip().upper() if rtgs_ifsc_code else "",
            rtgs_beneficiary_name.strip() if rtgs_beneficiary_name else "",
            now_str if settlement_mode == "RTGS" else None
        ))

        # IF CASH SETTLEMENT: Record Cashier Payout, update cash drawer, write ledger
        voucher_id = None
        if effective_payout_status == "PAID":
            voucher_id = f"VCH-{b_code}-{token_date}-{seq:04d}"
            
            # Resolve valid cashier user ID to prevent FK violation
            cur.execute("SELECT id FROM users WHERE id=? OR username=? OR role='BRANCH_CASHIER' LIMIT 1", (cashier_user_id, cashier_user_id))
            u_row = cur.fetchone()
            actual_cashier_id = u_row["id"] if u_row else "u-indore-cashier"

            cur.execute("""
                INSERT INTO cashier_payouts (
                    id, branch_id, invoice_id, party_id, payout_mode, amount_paid,
                    notes_500, notes_200, notes_100, notes_50, notes_20, notes_10, coins,
                    bank_utr_no, cashier_user_id
                ) VALUES (?, ?, ?, ?, 'CASH', ?, ?, ?, ?, ?, ?, ?, ?, '', ?)
            """, (
                f"pay-{uuid.uuid4().hex[:8]}", branch_id, invoice_id, party_id, payable_rounded,
                notes_500, notes_200, notes_100, notes_50, notes_20, notes_10, coins,
                actual_cashier_id
            ))

            # Ensure drawer row exists for today before update
            cur.execute("""
                INSERT OR IGNORE INTO branch_daily_cash_drawers 
                (id, branch_id, record_date, opening_float, total_cash_payouts, petty_expenses_cash, bank_withdrawals_inward, calculated_closing_cash, physical_counted_cash)
                VALUES (?, ?, ?, 500000.0, 0.0, 0.0, 0.0, 500000.0, 500000.0)
            """, (f"drw-{branch_id}-{today_str}", branch_id, today_str))

            # Update daily cash drawer
            cur.execute("""
                UPDATE branch_daily_cash_drawers 
                SET total_cash_payouts = total_cash_payouts + ?,
                    calculated_closing_cash = calculated_closing_cash - ?
                WHERE branch_id=? AND record_date=?
            """, (payable_rounded, payable_rounded, branch_id, today_str))

            # Double-entry ledger entries:
            # 1. Debit Commodity Purchase
            cur.execute("""
                INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, credit_amount, narration)
                VALUES (?, ?, ?, 'PURCHASE', ?, 'Commodity Purchase Account', ?, ?, 0.0, ?)
            """, (f"led-{uuid.uuid4().hex[:6]}", branch_id, today_str, token_number, party_id, calc["gross_amount"], f"Purchase of {commodity_name} ({calc['net_quintals']} Qtl)"))

            # 2. Credit Cash Drawer
            cur.execute("""
                INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, credit_amount, narration)
                VALUES (?, ?, ?, 'PAYMENT', ?, 'Cash Drawer / Physical Cash', ?, 0.0, ?, ?)
            """, (f"led-{uuid.uuid4().hex[:6]}", branch_id, today_str, voucher_id, party_id, payable_rounded, f"Cash payout against {token_number}"))

            # 3. Credit Hamali Recovery
            if calc["hamali_charge"] > 0:
                cur.execute("""
                    INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, credit_amount, narration)
                    VALUES (?, ?, ?, 'PURCHASE', ?, 'Hamali Deduction Account', ?, 0.0, ?, ?)
                """, (f"led-{uuid.uuid4().hex[:6]}", branch_id, today_str, token_number, party_id, calc["hamali_charge"], f"Farmer Hamali ₹25/100kg deducted"))

        elif effective_payout_status == "RTGS_PENDING":
            # Ledger entry: Debit Commodity Purchase, Credit Farmer
            cur.execute("""
                INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, credit_amount, narration)
                VALUES (?, ?, ?, 'PURCHASE', ?, 'Commodity Purchase Account', ?, ?, 0.0, ?)
            """, (f"led-{uuid.uuid4().hex[:6]}", branch_id, today_str, token_number, party_id, calc["gross_amount"], f"Purchase of {commodity_name} ({calc['net_quintals']} Qtl) - RTGS Pending"))

            cur.execute("""
                INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, credit_amount, narration)
                VALUES (?, ?, ?, 'PURCHASE', ?, 'Sundry Creditors (Farmer)', ?, 0.0, ?, ?)
            """, (f"led-{uuid.uuid4().hex[:6]}", branch_id, today_str, token_number, party_id, calc["net_payable_amount"], f"Payable via RTGS for {token_number}"))

        conn.commit()

        return {
            "success": True,
            "invoice_id": invoice_id,
            "token_number": token_number,
            "voucher_id": voucher_id,
            "payout_status": effective_payout_status,
            "net_payable_amount": calc["net_payable_amount"],
            "rounded_payout": payable_rounded,
            "hamali_charge": calc["hamali_charge"],
            "rate_override_status": rate_override_status
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

# --------------------------------------------------------------------------
# OUTWARD DISPATCH & SALES ENDPOINTS
# --------------------------------------------------------------------------

@app.get("/api/outward/calculate")
@app.post("/api/outward/calculate")
def api_calculate_outward(
    net_weight_kg: float = 0.0,
    rate_per_quintal: float = 0.0,
    hamali_per_100kg: float = 25.0
):
    return calculate_outward_order(
        net_weight_kg=net_weight_kg,
        rate_per_quintal=rate_per_quintal,
        hamali_per_100kg=hamali_per_100kg
    )

@app.post("/api/branch/outward/create")
def api_branch_create_outward(
    request: Request,
    branch_id: str = Form(...),
    buyer_name: Optional[str] = Form(""),
    buyer_id: Optional[str] = Form(None),
    commodity_name: str = Form(...),
    net_weight_kg: float = Form(...),
    rate_per_quintal: float = Form(...),
    hamali_per_100kg: float = Form(25.0),
    vehicle_number: Optional[str] = Form(""),
    cashier_user_id: Optional[str] = Form("cashier")
):
    require_active_license()
    user = require_role(request, ["BRANCH_CASHIER", "SUPER_ADMIN"])
    if user.get("role") == "BRANCH_CASHIER":
        assigned_branch = user.get("branch_id")
        if assigned_branch:
            branch_id = assigned_branch
        cashier_user_id = user.get("user_id") or user.get("username") or cashier_user_id

    today_str = date.today().isoformat()
    calc = calculate_outward_order(
        net_weight_kg=net_weight_kg,
        rate_per_quintal=rate_per_quintal,
        hamali_per_100kg=hamali_per_100kg
    )

    conn = get_connection()
    try:
        cur = conn.cursor()
        actual_buyer = buyer_name.strip() if buyer_name else ""
        if not actual_buyer and buyer_id:
            cur.execute("SELECT name FROM parties WHERE id=?", (buyer_id,))
            b_row = cur.fetchone()
            if b_row:
                actual_buyer = b_row["name"]
        if not actual_buyer:
            actual_buyer = "Commercial Trader"

        cur.execute("SELECT branch_code FROM branches WHERE id=?", (branch_id,))
        b_code_row = cur.fetchone()
        b_code = b_code_row["branch_code"].replace("BR-", "") if b_code_row else "BR"

        token_date = datetime.now().strftime("%Y%m%d")
        cur.execute("SELECT count(*) as cnt FROM outward_orders WHERE branch_id=? AND order_date=?", (branch_id, today_str))
        seq = cur.fetchone()["cnt"] + 1
        challan_number = f"OUT-{b_code}-{token_date}-{seq:04d}"
        order_id = f"out-{uuid.uuid4().hex[:10]}"

        cur.execute("""
            INSERT INTO outward_orders (
                id, branch_id, challan_number, order_date, buyer_name, commodity_name,
                vehicle_number, net_weight_kg, net_quintals, rate_per_quintal,
                hamali_per_100kg, hamali_amount, gross_amount, total_bill_amount,
                status, cashier_user_id
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                'DISPATCHED', ?
            )
        """, (
            order_id, branch_id, challan_number, today_str, actual_buyer, commodity_name.strip(),
            vehicle_number.strip().upper() if vehicle_number else "", calc["net_weight_kg"], calc["net_quintals"],
            calc["rate_per_quintal"], calc["hamali_per_100kg"], calc["hamali_amount"],
            calc["gross_amount"], calc["total_bill_amount"], cashier_user_id or "cashier"
        ))

        # Ledger entries for outward sales (Double entry):
        # 1. Debit Sundry Debtors (Buyer) with total bill
        cur.execute("""
            INSERT INTO ledger_entries (
                id, branch_id, transaction_date, voucher_type, voucher_id, account_name,
                debit_amount, credit_amount, narration
            ) VALUES (?, ?, ?, 'SALES', ?, 'Sundry Debtors / Buyer', ?, 0.0, ?)
        """, (
            f"led-{uuid.uuid4().hex[:6]}", branch_id, today_str, challan_number,
            calc["total_bill_amount"], f"Outward Dispatch {challan_number} to {actual_buyer} ({calc['net_quintals']} Qtl {commodity_name})"
        ))

        # 2. Credit Commodity Sales
        cur.execute("""
            INSERT INTO ledger_entries (
                id, branch_id, transaction_date, voucher_type, voucher_id, account_name,
                debit_amount, credit_amount, narration
            ) VALUES (?, ?, ?, 'SALES', ?, 'Commodity Sales Account', 0.0, ?, ?)
        """, (
            f"led-{uuid.uuid4().hex[:6]}", branch_id, today_str, challan_number,
            calc["gross_amount"], f"Sales revenue for {challan_number}"
        ))

        # 3. Credit Hamali Recovery (billed to buyer)
        if calc["hamali_amount"] > 0:
            cur.execute("""
                INSERT INTO ledger_entries (
                    id, branch_id, transaction_date, voucher_type, voucher_id, account_name,
                    debit_amount, credit_amount, narration
                ) VALUES (?, ?, ?, 'SALES', ?, 'Hamali Recovery Account', 0.0, ?, ?)
            """, (
                f"led-{uuid.uuid4().hex[:6]}", branch_id, today_str, challan_number,
                calc["hamali_amount"], f"Outward hamali billed at ₹{calc['hamali_per_100kg']}/100kg on {challan_number}"
            ))

        conn.commit()

        return {
            "success": True,
            "order_id": order_id,
            "challan_number": challan_number,
            "total_bill_amount": calc["total_bill_amount"],
            "net_quintals": calc["net_quintals"],
            "gross_amount": calc["gross_amount"],
            "hamali_amount": calc["hamali_amount"]
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

@app.get("/api/branch/outward/challan/{challan_number}", response_class=HTMLResponse)
def get_outward_challan_html(request: Request, challan_number: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT o.*, b.name as branch_name, b.mandi_license_no
            FROM outward_orders o
            JOIN branches b ON o.branch_id = b.id
            WHERE o.challan_number = ?
        """, (challan_number,))
        order = cur.fetchone()
        if not order:
            return HTMLResponse("<div style='padding:20px; color:red; font-family:sans-serif;'>Outward Challan Not Found</div>", status_code=404)
        return templates.TemplateResponse(request=request, name="outward_challan.html", context={"order": dict(order)})
    finally:
        conn.close()

# --------------------------------------------------------------------------
# BUYER / TRADER REGISTER ENDPOINTS
# --------------------------------------------------------------------------

@app.post("/api/branch/buyers/register")
def api_branch_register_buyer(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    address: str = Form(...),
    gstin: Optional[str] = Form(""),
    pan_number: Optional[str] = Form(""),
    contact_person: Optional[str] = Form(""),
    home_branch_id: Optional[str] = Form(None),
    bank_name: Optional[str] = Form(""),
    bank_account_no: Optional[str] = Form(""),
    bank_ifsc: Optional[str] = Form("")
):
    user = require_role(request, ["BRANCH_CASHIER", "ACCOUNTANT_HQ", "SUPER_ADMIN"])
    if user.get("role") == "BRANCH_CASHIER" and user.get("branch_id"):
        home_branch_id = user.get("branch_id")
    changed_by_name = user.get("full_name") or user.get("username")

    pid = f"p-{uuid.uuid4().hex[:8]}"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO parties (
                id, home_branch_id, name, phone, party_type, village, 
                gstin, pan_number, khasra_record_no, bank_name, bank_account_no, bank_ifsc
            ) VALUES (?, ?, ?, ?, 'BUYER', ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid, home_branch_id, name.strip(), phone.strip(), address.strip(),
            gstin.strip().upper() if gstin else "",
            pan_number.strip().upper() if pan_number else "",
            contact_person.strip() if contact_person else "",
            bank_name.strip() if bank_name else "",
            bank_account_no.strip() if bank_account_no else "",
            bank_ifsc.strip().upper() if bank_ifsc else ""
        ))

        # Log to audit change logs
        log_id = f"log-{uuid.uuid4().hex[:8]}"
        cur.execute("""
            INSERT INTO audit_change_logs (
                id, entity_type, entity_id, entity_name, branch_id, changed_by,
                action, change_summary
            ) VALUES (?, 'BUYER', ?, ?, ?, ?, 'REGISTER_BUYER', ?)
        """, (log_id, pid, name.strip(), home_branch_id, changed_by_name, f"Registered new buyer/trader '{name.strip()}' (GST: {gstin or 'N/A'})"))

        conn.commit()
        return {
            "success": True,
            "buyer": {
                "id": pid,
                "name": name.strip(),
                "phone": phone.strip(),
                "address": address.strip(),
                "gstin": gstin.strip().upper() if gstin else "",
                "contact_person": contact_person.strip() if contact_person else ""
            }
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

@app.get("/api/branch/buyers")
def api_branch_get_buyers(request: Request):
    require_role(request, ["BRANCH_CASHIER", "ACCOUNTANT_HQ", "SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, phone, village as address, gstin, pan_number,
                   khasra_record_no as contact_person, bank_name, bank_account_no, bank_ifsc, created_at
            FROM parties
            WHERE party_type IN ('BUYER', 'STOCKER')
            ORDER BY name ASC
        """)
        buyers = [dict(r) for r in cur.fetchall()]
        return {"success": True, "buyers": buyers}
    finally:
        conn.close()

# --------------------------------------------------------------------------
# FARMER EDIT & AUDIT CHANGE LOG ENDPOINTS
# --------------------------------------------------------------------------

@app.post("/api/branch/farmers/edit")
def api_branch_edit_farmer(
    request: Request,
    party_id: str = Form(...),
    name: str = Form(...),
    phone: str = Form(...),
    village: str = Form(...),
    khasra_record_no: str = Form(...),
    aadhaar_number: Optional[str] = Form(""),
    pan_number: Optional[str] = Form(""),
    bank_name: Optional[str] = Form(""),
    bank_account_no: Optional[str] = Form(""),
    bank_ifsc: Optional[str] = Form(""),
    change_reason: Optional[str] = Form("Farmer profile update"),
    branch_id: Optional[str] = Form("br-chikhali"),
    operator_name: Optional[str] = Form("Cashier")
):
    user = require_role(request, ["BRANCH_CASHIER", "ACCOUNTANT_HQ", "SUPER_ADMIN"])
    if user.get("role") == "BRANCH_CASHIER" and user.get("branch_id"):
        branch_id = user.get("branch_id")
    operator_name = user.get("full_name") or user.get("username") or operator_name
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM parties WHERE id=?", (party_id,))
        old_party = cur.fetchone()
        if not old_party:
            return {"success": False, "error": "Farmer not found"}

        old_dict = {
            "name": old_party["name"],
            "phone": old_party["phone"],
            "village": old_party["village"],
            "khasra_record_no": old_party["khasra_record_no"],
            "aadhaar_number": old_party["aadhaar_number"],
            "pan_number": old_party["pan_number"],
            "bank_name": old_party["bank_name"],
            "bank_account_no": old_party["bank_account_no"],
            "bank_ifsc": old_party["bank_ifsc"]
        }

        new_dict = {
            "name": name.strip(),
            "phone": phone.strip(),
            "village": village.strip(),
            "khasra_record_no": khasra_record_no.strip(),
            "aadhaar_number": aadhaar_number.strip() if aadhaar_number else "",
            "pan_number": pan_number.strip() if pan_number else "",
            "bank_name": bank_name.strip() if bank_name else "",
            "bank_account_no": bank_account_no.strip() if bank_account_no else "",
            "bank_ifsc": bank_ifsc.strip().upper() if bank_ifsc else ""
        }

        # Find changed fields for audit summary
        changes = []
        for k in old_dict:
            if str(old_dict[k] or "") != str(new_dict[k] or ""):
                changes.append(f"{k}: '{old_dict[k]}' -> '{new_dict[k]}'")
        summary = f"{change_reason or 'Profile update'} ({', '.join(changes)})" if changes else f"{change_reason or 'Profile update'} (Verified/Saved)"

        # Update parties table
        cur.execute("""
            UPDATE parties SET
                name=?, phone=?, village=?, khasra_record_no=?,
                aadhaar_number=?, pan_number=?, bank_name=?, bank_account_no=?, bank_ifsc=?
            WHERE id=?
        """, (
            new_dict["name"], new_dict["phone"], new_dict["village"], new_dict["khasra_record_no"],
            new_dict["aadhaar_number"], new_dict["pan_number"], new_dict["bank_name"],
            new_dict["bank_account_no"], new_dict["bank_ifsc"], party_id
        ))

        # Log change to immutable audit table
        log_id = f"log-{uuid.uuid4().hex[:8]}"
        cur.execute("""
            INSERT INTO audit_change_logs (
                id, entity_type, entity_id, entity_name, branch_id, changed_by,
                action, old_values_json, new_values_json, change_summary
            ) VALUES (?, 'FARMER', ?, ?, ?, ?, 'UPDATE', ?, ?, ?)
        """, (
            log_id, party_id, new_dict["name"], branch_id, operator_name or "Cashier",
            json.dumps(old_dict), json.dumps(new_dict), summary
        ))

        conn.commit()
        return {
            "success": True,
            "message": "Farmer details updated and logged to audit trail successfully.",
            "farmer": {**new_dict, "id": party_id}
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

@app.get("/api/branch/farmers/{farmer_id}/audit-logs")
def api_get_farmer_audit_logs(request: Request, farmer_id: str):
    require_role(request, ["BRANCH_CASHIER", "ACCOUNTANT_HQ", "SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM audit_change_logs 
            WHERE entity_type='FARMER' AND entity_id=?
            ORDER BY created_at DESC
        """, (farmer_id,))
        logs = [dict(r) for r in cur.fetchall()]
        return {"success": True, "logs": logs}
    finally:
        conn.close()

# --------------------------------------------------------------------------
# BRANCH YARD PHYSICAL STOCK & VALUATION PAGE
# --------------------------------------------------------------------------

@app.get("/branch/stock", response_class=HTMLResponse)
def branch_stock_view(request: Request, branch_id: str = "br-chikhali"):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") == "BRANCH_CASHIER":
        assigned_branch = user.get("branch_id")
        if assigned_branch and branch_id != assigned_branch:
            return RedirectResponse(url=f"/branch/stock?branch_id={assigned_branch}", status_code=303)
        actual_req_branch = assigned_branch or branch_id
    elif user.get("role") == "ACCOUNTANT_HQ":
        return RedirectResponse(url="/accounts/dashboard", status_code=303)
    elif user.get("role") == "SUPER_ADMIN":
        actual_req_branch = branch_id
    else:
        return RedirectResponse(url="/login", status_code=303)
    logged_in_user = user

    today_str = date.today().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, branch_code, name, mandi_license_no FROM branches WHERE id=?", (actual_req_branch,))
        current_branch = cur.fetchone()
        if not current_branch:
            cur.execute("SELECT id, branch_code, name, mandi_license_no FROM branches LIMIT 1")
            current_branch = cur.fetchone()
        actual_branch_id = current_branch["id"]

        cur.execute("SELECT id, branch_code, name FROM branches WHERE is_active=1 ORDER BY branch_code")
        branches = cur.fetchall()

        icon_map = {
            "Soyabean (Yellow)": "🌱",
            "Cotton / Kapas (कापूस)": "☁️",
            "Tur / Arhar (तूर)": "🍲",
            "Chana (Desi) / Harbhara (हरभरा)": "🫘",
            "Chana / Harbhara (हरभरा)": "🫘",
            "Wheat (Lokwan)": "🌾",
            "Maize (Makka)": "🌽",
            "Moong (Green Gram)": "🟢",
            "Urad (Black Gram)": "⚫",
            "Chana (Desi)": "🫘",
            "Mustard (Rayda)": "🌼"
        }

        # Query all active commodities
        cur.execute("SELECT id, name, hsn_code FROM commodities WHERE is_active=1 ORDER BY name ASC")
        commodities = cur.fetchall()

        commodity_stocks = []
        total_stock_qtl = 0.0
        total_stock_valuation = 0.0
        total_inward_qtl = 0.0
        total_inward_cost = 0.0
        total_outward_qtl = 0.0

        for c in commodities:
            c_name = c["name"]
            # Inward purchases for this branch
            cur.execute("""
                SELECT COALESCE(SUM(net_quintals), 0.0) as inward_qtl,
                       COALESCE(SUM(gross_amount), 0.0) as inward_cost
                FROM purchase_invoices
                WHERE branch_id=? AND commodity_name=? AND payout_status != 'CANCELLED'
            """, (actual_branch_id, c_name))
            inw = cur.fetchone()
            inw_qtl = inw["inward_qtl"]
            inw_cost = inw["inward_cost"]

            # Outward dispatches for this branch
            cur.execute("""
                SELECT COALESCE(SUM(net_quintals), 0.0) as outward_qtl,
                       COALESCE(SUM(total_bill_amount), 0.0) as outward_val
                FROM outward_orders
                WHERE branch_id=? AND commodity_name=? AND status != 'CANCELLED'
            """, (actual_branch_id, c_name))
            outw = cur.fetchone()
            outw_qtl = outw["outward_qtl"]

            net_qtl = max(0.0, inw_qtl - outw_qtl)
            avg_buying_price = round(inw_cost / inw_qtl, 2) if inw_qtl > 0 else 0.0
            stock_valuation = round(net_qtl * avg_buying_price, 2)

            cur.execute("""
                SELECT target_rate_per_qtl FROM daily_commodity_rates
                WHERE commodity_name=? AND rate_date=? AND (branch_id=? OR branch_id IS NULL)
                ORDER BY updated_at DESC LIMIT 1
            """, (c_name, today_str, actual_branch_id))
            rate_row = cur.fetchone()
            today_target = rate_row["target_rate_per_qtl"] if rate_row else avg_buying_price

            total_stock_qtl += net_qtl
            total_stock_valuation += stock_valuation
            total_inward_qtl += inw_qtl
            total_inward_cost += inw_cost
            total_outward_qtl += outw_qtl

            commodity_stocks.append({
                "name": c_name,
                "hsn_code": c["hsn_code"],
                "icon": icon_map.get(c_name, "📦"),
                "inward_qtl": inw_qtl,
                "outward_qtl": outw_qtl,
                "net_stock_qtl": net_qtl,
                "net_stock_kg": round(net_qtl * 100.0, 2),
                "net_stock_mt": round(net_qtl / 10.0, 2),
                "avg_buying_price": avg_buying_price,
                "today_target_rate": today_target,
                "stock_valuation": stock_valuation
            })

        yard_avg_buying_price = round(total_inward_cost / total_inward_qtl, 2) if total_inward_qtl > 0 else 0.0

        # Query recent inward invoices and outward dispatches for this branch
        cur.execute("""
            SELECT p.id, p.token_number, p.invoice_date, pt.name as party_name,
                   p.commodity_name, p.net_quintals, p.rate_per_quintal, p.gross_amount,
                   p.net_payable_amount, p.payout_status, p.weighment_mode
            FROM purchase_invoices p
            JOIN parties pt ON p.party_id = pt.id
            WHERE p.branch_id=?
            ORDER BY p.created_at DESC LIMIT 15
        """, (actual_branch_id,))
        recent_invoices = cur.fetchall()

        cur.execute("""
            SELECT id, challan_number, order_date, buyer_name, commodity_name, vehicle_number,
                   net_weight_kg, net_quintals, rate_per_quintal, hamali_amount, total_bill_amount, status
            FROM outward_orders
            WHERE branch_id=?
            ORDER BY created_at DESC LIMIT 15
        """, (actual_branch_id,))
        recent_outward_orders = cur.fetchall()

        return templates.TemplateResponse(request=request, name="branch_stock.html", context={
            "current_branch": current_branch,
            "branches": branches,
            "commodity_stocks": commodity_stocks,
            "total_stock_qtl": total_stock_qtl,
            "total_stock_mt": round(total_stock_qtl / 10.0, 2),
            "total_stock_valuation": total_stock_valuation,
            "yard_avg_buying_price": yard_avg_buying_price,
            "total_outward_qtl": total_outward_qtl,
            "total_outward_mt": round(total_outward_qtl / 10.0, 2),
            "recent_invoices": recent_invoices,
            "recent_outward_orders": recent_outward_orders,
            "logged_in_user": logged_in_user
        })
    finally:
        conn.close()

# --------------------------------------------------------------------------
# SETTINGS ENDPOINTS FOR ALL THREE PANELS
# --------------------------------------------------------------------------

@app.get("/admin/settings", response_class=HTMLResponse)
def admin_settings_view(request: Request, msg: Optional[str] = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") != "SUPER_ADMIN":
        if user.get("role") == "ACCOUNTANT_HQ":
            return RedirectResponse(url="/accounts/dashboard", status_code=303)
        else:
            b_id = user.get("branch_id") or "br-chikhali"
            return RedirectResponse(url=f"/branch/dashboard?branch_id={b_id}", status_code=303)
    logged_in_user = user

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT setting_key, setting_value FROM system_settings WHERE scope='SUPER_ADMIN'")
        settings = {r["setting_key"]: r["setting_value"] for r in cur.fetchall()}

        # Load verified license information and branch quota stats
        license_info = check_system_license(conn)
        allowed_branches, branch_limit_msg, cur_branch_cnt, max_branch_cnt = check_branch_limit(conn)
        branch_stats = {
            "current_count": cur_branch_cnt,
            "max_count": max_branch_cnt,
            "allowed": allowed_branches,
            "message": branch_limit_msg
        }

        # Staff Users (1 Cashier & Munim per branch, 1 HQ Accountant, 1 Admin)
        cur.execute("""
            SELECT u.id, u.branch_id, u.username, u.full_name, u.phone, u.role, u.is_active,
                   COALESCE(b.name, 'Head Office / Master Control') as branch_name, b.branch_code
            FROM users u
            LEFT JOIN branches b ON u.branch_id = b.id
            WHERE u.is_active=1
            ORDER BY CASE u.role 
                WHEN 'SUPER_ADMIN' THEN 1 
                WHEN 'ACCOUNTANT_HQ' THEN 2 
                ELSE 3 END, b.branch_code
        """)
        staff_users = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM audit_change_logs ORDER BY created_at DESC LIMIT 50")
        audit_logs = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM users WHERE role='ACCOUNTANT_HQ' LIMIT 1")
        accountant = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE role='BRANCH_CASHIER' AND branch_id='br-chikhali' LIMIT 1")
        chk_cashier = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE role='BRANCH_CASHIER' AND branch_id='br-varvand' LIMIT 1")
        vrv_cashier = cur.fetchone()

        cur.execute("SELECT * FROM users WHERE role='BRANCH_CASHIER' AND branch_id='br-dhad' LIMIT 1")
        dhd_cashier = cur.fetchone()

        return templates.TemplateResponse(request=request, name="admin_settings.html", context={
            "settings": settings,
            "license_info": license_info,
            "branch_stats": branch_stats,
            "staff_users": staff_users,
            "accountant": accountant,
            "chk_cashier": chk_cashier,
            "vrv_cashier": vrv_cashier,
            "dhd_cashier": dhd_cashier,
            "audit_logs": audit_logs,
            "message": msg,
            "logged_in_user": logged_in_user
        })
    finally:
        conn.close()

@app.post("/api/admin/staff/update-all")
def api_admin_update_all_staff(
    request: Request,
    acc_name: str = Form(...),
    acc_username: str = Form(...),
    acc_phone: str = Form(...),
    acc_password: Optional[str] = Form(None),

    chk_name: str = Form(...),
    chk_username: str = Form(...),
    chk_phone: str = Form(...),
    chk_password: Optional[str] = Form(None),

    vrv_name: str = Form(...),
    vrv_username: str = Form(...),
    vrv_phone: str = Form(...),
    vrv_password: Optional[str] = Form(None),

    dhd_name: str = Form(...),
    dhd_username: str = Form(...),
    dhd_phone: str = Form(...),
    dhd_password: Optional[str] = Form(None),
):
    require_role(request, ["SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        staff_data = [
            ("ACCOUNTANT_HQ", None, acc_name.strip(), acc_username.strip(), acc_phone.strip(), acc_password),
            ("BRANCH_CASHIER", "br-chikhali", chk_name.strip(), chk_username.strip(), chk_phone.strip(), chk_password),
            ("BRANCH_CASHIER", "br-varvand", vrv_name.strip(), vrv_username.strip(), vrv_phone.strip(), vrv_password),
            ("BRANCH_CASHIER", "br-dhad", dhd_name.strip(), dhd_username.strip(), dhd_phone.strip(), dhd_password),
        ]
        for role, branch_id, name, username, phone, pwd in staff_data:
            if branch_id:
                cur.execute("SELECT id FROM users WHERE role=? AND branch_id=? LIMIT 1", (role, branch_id))
            else:
                cur.execute("SELECT id FROM users WHERE role=? LIMIT 1", (role,))
            user_row = cur.fetchone()
            if user_row:
                uid = user_row["id"]
                if pwd and pwd.strip():
                    cur.execute("""
                        UPDATE users 
                        SET full_name=?, username=?, phone=?, password_hash=?
                        WHERE id=?
                    """, (name, username, phone, hash_password(pwd.strip()), uid))
                    revoke_user_sessions_by_user(uid, conn=conn)
                else:
                    cur.execute("""
                        UPDATE users 
                        SET full_name=?, username=?, phone=?
                        WHERE id=?
                    """, (name, username, phone, uid))
                
                # Also update corresponding munim account if present
                if branch_id:
                    if pwd and pwd.strip():
                        cur.execute("""
                            UPDATE users
                            SET full_name=?, phone=?, password_hash=?
                            WHERE branch_id=? AND role='BRANCH_MUNIM'
                        """, (name, phone, hash_password(pwd.strip()), branch_id))
                    else:
                        cur.execute("""
                            UPDATE users
                            SET full_name=?, phone=?
                            WHERE branch_id=? AND role='BRANCH_MUNIM'
                        """, (name, phone, branch_id))

        cur.execute("""
            INSERT INTO audit_change_logs (id, entity_type, entity_id, entity_name, action, change_summary)
            VALUES (?, 'USER', 'STAFF_ALL', 'All Staff Credentials', 'UPDATE', 'Super Admin updated staff credentials and passwords')
        """, (f"log-{uuid.uuid4().hex[:8]}",))

        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update staff credentials: {e}")
    finally:
        conn.close()

    return RedirectResponse(url="/admin/settings?msg=Staff+credentials+and+passwords+updated+successfully.+Panel+isolation+enforced.", status_code=303)

@app.post("/api/admin/users/update-credentials")
def api_admin_update_credentials(
    request: Request,
    user_id: str = Form(...),
    full_name: str = Form(...),
    phone: str = Form(...),
    username: str = Form(...),
    new_password: Optional[str] = Form(None)
):
    require_role(request, ["SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
        u = cur.fetchone()
        if not u:
            raise HTTPException(status_code=404, detail="User not found.")

        clean_name = full_name.strip()
        clean_phone = phone.strip()
        clean_user = username.strip()

        if new_password and new_password.strip():
            new_hash = hash_password(new_password.strip())
            cur.execute("""
                UPDATE users
                SET full_name=?, phone=?, username=?, password_hash=?
                WHERE id=?
            """, (clean_name, clean_phone, clean_user, new_hash, user_id))
            revoke_user_sessions_by_user(user_id, conn=conn)
            action_desc = f"Updated staff details and changed password for '{clean_user}' ({clean_name})"
        else:
            cur.execute("""
                UPDATE users
                SET full_name=?, phone=?, username=?
                WHERE id=?
            """, (clean_name, clean_phone, clean_user, user_id))
            action_desc = f"Updated staff profile for '{clean_user}' ({clean_name})"

        cur.execute("""
            INSERT INTO audit_change_logs (id, entity_type, entity_id, entity_name, branch_id, changed_by, action, change_summary)
            VALUES (?, 'USER', ?, ?, ?, 'admin', 'CREDENTIALS_UPDATE', ?)
        """, (f"log-{uuid.uuid4().hex[:8]}", user_id, clean_user, u["branch_id"], action_desc))

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

    return RedirectResponse(url="/admin/settings?msg=Staff+credentials+updated+successfully", status_code=303)

@app.post("/api/admin/settings")
def api_save_admin_settings(
    request: Request,
    org_name: str = Form(...),
    org_pan: str = Form(...),
    org_gstin: str = Form(...),
    fiscal_year: str = Form(...),
    multi_branch_sync: str = Form(...),
    audit_retention_days: str = Form(...)
):
    require_role(request, ["SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        for k, v in [
            ("org_name", org_name.strip()),
            ("org_pan", org_pan.strip()),
            ("org_gstin", org_gstin.strip()),
            ("fiscal_year", fiscal_year.strip()),
            ("multi_branch_sync", multi_branch_sync.strip()),
            ("audit_retention_days", audit_retention_days.strip())
        ]:
            cur.execute("""
                INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at)
                VALUES ('SUPER_ADMIN', 'GLOBAL', ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(scope, scope_id, setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=CURRENT_TIMESTAMP
            """, (k, v))
        
        cur.execute("""
            INSERT INTO audit_change_logs (id, entity_type, entity_id, entity_name, action, change_summary)
            VALUES (?, 'SYSTEM_SETTINGS', 'SUPER_ADMIN', 'Super Admin Configuration', 'UPDATE', 'Corporate & Statutory profile updated')
        """, (f"log-{uuid.uuid4().hex[:8]}",))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/admin/settings?msg=Settings+saved+successfully", status_code=303)

@app.post("/api/admin/license/activate")
def api_admin_activate_license(request: Request, license_token: str = Form(...)):
    require_role(request, ["SUPER_ADMIN"])
    token_str = license_token.strip()
    is_valid, msg, claims = verify_license_token(token_str)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid License Token: {msg}")

    conn = get_connection()
    try:
        save_license_token(token_str, conn)
        tier_display = claims.get("tier", "Pro").capitalize()
        max_branches = claims.get("max_branches", 3)
        exp_date = claims.get("expires_at", "31-March-2027")

        cur = conn.cursor()
        settings_to_update = [
            ("license_key", claims.get("license_id", "LIC-TOKEN")),
            ("license_status", f"Active ({tier_display} Tier - {max_branches} Branches)"),
            ("license_valid_until", exp_date),
            ("license_tier", f"{tier_display} Tier ({max_branches} Branches)"),
            ("license_branch_limit", str(max_branches))
        ]
        for k, v in settings_to_update:
            cur.execute("""
                INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) 
                VALUES ('SUPER_ADMIN', 'GLOBAL', ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(scope, scope_id, setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=CURRENT_TIMESTAMP
            """, (k, v))

        cur.execute("""
            INSERT INTO audit_change_logs (id, entity_type, entity_id, entity_name, action, change_summary)
            VALUES (?, 'LICENSE', ?, 'Commercial License Token', 'ACTIVATE', ?)
        """, (f"log-{uuid.uuid4().hex[:8]}", claims.get("license_id", "LIC"), f"Activated license for {claims.get('licensee_name')} ({tier_display} Tier, Max {max_branches} Branches)"))
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url="/admin/settings?msg=Commercial+license+token+verified+and+activated+successfully", status_code=303)

@app.get("/accounts/settings", response_class=HTMLResponse)
def accounts_settings_view(request: Request, msg: Optional[str] = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") == "BRANCH_CASHIER":
        b_id = user.get("branch_id") or "br-chikhali"
        return RedirectResponse(url=f"/branch/dashboard?branch_id={b_id}", status_code=303)
    logged_in_user = user

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT setting_key, setting_value FROM system_settings WHERE scope='CENTRAL_ACCOUNTS'")
        settings = {r["setting_key"]: r["setting_value"] for r in cur.fetchall()}
        return templates.TemplateResponse(request=request, name="accounts_settings.html", context={
            "settings": settings,
            "message": msg,
            "logged_in_user": logged_in_user
        })
    finally:
        conn.close()

@app.post("/api/accounts/settings")
def api_save_accounts_settings(
    request: Request,
    sec_269st_cash_limit: str = Form(...),
    sec_40a3_cash_limit: str = Form(...),
    corridor_tolerance_pct: str = Form(...),
    rtgs_auto_sms: str = Form(...),
    default_bank_account: str = Form(...)
):
    require_role(request, ["ACCOUNTANT_HQ", "SUPER_ADMIN"])
    conn = get_connection()
    try:
        cur = conn.cursor()
        for k, v in [
            ("sec_269st_cash_limit", sec_269st_cash_limit.strip()),
            ("sec_40a3_cash_limit", sec_40a3_cash_limit.strip()),
            ("corridor_tolerance_pct", corridor_tolerance_pct.strip()),
            ("rtgs_auto_sms", rtgs_auto_sms.strip()),
            ("default_bank_account", default_bank_account.strip())
        ]:
            cur.execute("""
                INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at)
                VALUES ('CENTRAL_ACCOUNTS', 'GLOBAL', ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(scope, scope_id, setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=CURRENT_TIMESTAMP
            """, (k, v))
        
        cur.execute("""
            INSERT INTO audit_change_logs (id, entity_type, entity_id, entity_name, action, change_summary)
            VALUES (?, 'SYSTEM_SETTINGS', 'CENTRAL_ACCOUNTS', 'Accounts Configuration', 'UPDATE', 'Cash limits and Banking parameters updated')
        """, (f"log-{uuid.uuid4().hex[:8]}",))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/accounts/settings?msg=Central+Accounts+settings+updated+successfully", status_code=303)

@app.get("/branch/settings", response_class=HTMLResponse)
def branch_settings_view(request: Request, branch_id: str = "br-chikhali", msg: Optional[str] = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.get("role") == "BRANCH_CASHIER":
        assigned_branch = user.get("branch_id")
        if assigned_branch and branch_id != assigned_branch:
            return RedirectResponse(url=f"/branch/settings?branch_id={assigned_branch}", status_code=303)
        actual_branch_id = assigned_branch or branch_id
    elif user.get("role") == "ACCOUNTANT_HQ":
        return RedirectResponse(url="/accounts/dashboard", status_code=303)
    elif user.get("role") == "SUPER_ADMIN":
        actual_branch_id = branch_id
    else:
        return RedirectResponse(url="/login", status_code=303)
    logged_in_user = user

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, branch_code, name, mandi_license_no, address, phone FROM branches WHERE id=?", (actual_branch_id,))
        current_branch = cur.fetchone()
        if not current_branch:
            cur.execute("SELECT id, branch_code, name, mandi_license_no, address, phone FROM branches LIMIT 1")
            current_branch = cur.fetchone()
        actual_branch_id = current_branch["id"]

        cur.execute("SELECT id, branch_code, name FROM branches WHERE is_active=1 ORDER BY branch_code")
        branches = cur.fetchall()

        cur.execute("SELECT setting_key, setting_value FROM system_settings WHERE scope='BRANCH' AND (scope_id=? OR scope_id='GLOBAL')", (actual_branch_id,))
        settings = {r["setting_key"]: r["setting_value"] for r in cur.fetchall()}
        return templates.TemplateResponse(request=request, name="branch_settings.html", context={
            "current_branch": current_branch,
            "branches": branches,
            "settings": settings,
            "message": msg,
            "logged_in_user": logged_in_user
        })
    finally:
        conn.close()

@app.post("/api/branch/settings")
def api_save_branch_settings(
    request: Request,
    branch_id: str = Form(...),
    default_weighment_mode: str = Form(...),
    parchi_gate_no: str = Form(...),
    auto_print_parchi: str = Form(...),
    cash_drawer_warning_limit: str = Form(...)
):
    user = require_role(request, ["BRANCH_CASHIER", "SUPER_ADMIN"])
    if user.get("role") == "BRANCH_CASHIER" and user.get("branch_id"):
        branch_id = user.get("branch_id")
    conn = get_connection()
    try:
        cur = conn.cursor()
        for k, v in [
            ("default_weighment_mode", default_weighment_mode.strip()),
            ("parchi_gate_no", parchi_gate_no.strip()),
            ("auto_print_parchi", auto_print_parchi.strip()),
            ("cash_drawer_warning_limit", cash_drawer_warning_limit.strip())
        ]:
            cur.execute("""
                INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at)
                VALUES ('BRANCH', ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(scope, scope_id, setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=CURRENT_TIMESTAMP
            """, (branch_id, k, v))

        cur.execute("""
            INSERT INTO audit_change_logs (id, entity_type, entity_id, entity_name, branch_id, action, change_summary)
            VALUES (?, 'SYSTEM_SETTINGS', ?, 'Branch Hardware & Weighment Settings', ?, 'UPDATE', 'Local terminal settings updated')
        """, (f"log-{uuid.uuid4().hex[:8]}", branch_id, branch_id))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/branch/settings?branch_id={branch_id}&msg=Branch+settings+saved+successfully", status_code=303)

@app.post("/api/cashier/request-rtgs")
def api_cashier_request_rtgs(
    request: Request,
    invoice_id: str = Form(...),
    branch_id: str = Form(...),
    beneficiary_name: str = Form(...),
    bank_name: str = Form(...),
    account_no: str = Form(...),
    ifsc_code: str = Form(...)
):
    require_active_license()
    user = require_role(request, ["BRANCH_CASHIER", "SUPER_ADMIN"])
    if user.get("role") == "BRANCH_CASHIER" and user.get("branch_id"):
        branch_id = user.get("branch_id")

    if not bank_name.strip() or not account_no.strip() or not ifsc_code.strip():
        return {"success": False, "error": "Bank Name, Account Number, and IFSC Code are mandatory for RTGS."}

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM purchase_invoices WHERE id=?", (invoice_id,))
        inv = cur.fetchone()
        if not inv:
            return {"success": False, "error": "Invoice not found."}
        if user.get("role") == "BRANCH_CASHIER" and inv["branch_id"] != branch_id:
            return {"success": False, "error": "Unauthorized: Cashier cannot request RTGS for an invoice from another branch."}
        if inv["payout_status"] == "PAID":
            return {"success": False, "error": "Invoice has already been settled."}

        cur.execute("""
            UPDATE purchase_invoices
            SET payout_status = 'RTGS_PENDING',
                rtgs_bank_name = ?,
                rtgs_account_no = ?,
                rtgs_ifsc_code = ?,
                rtgs_beneficiary_name = ?,
                rtgs_requested_at = ?
            WHERE id = ?
        """, (bank_name.strip(), account_no.strip(), ifsc_code.strip().upper(), beneficiary_name.strip(), now_str, invoice_id))

        # Also update farmer bank details in parties if empty
        cur.execute("""
            UPDATE parties 
            SET bank_name = COALESCE(NULLIF(bank_name, ''), ?),
                bank_account_no = COALESCE(NULLIF(bank_account_no, ''), ?),
                bank_ifsc = COALESCE(NULLIF(bank_ifsc, ''), ?)
            WHERE id = ?
        """, (bank_name.strip(), account_no.strip(), ifsc_code.strip().upper(), inv["party_id"]))

        conn.commit()
        return {
            "success": True,
            "message": f"RTGS transfer request forwarded to Central HQ Accounts for transfer of ₹{inv['net_payable_amount']:,.2f}."
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

@app.get("/api/branch/invoices/parchi/{token_number}", response_class=HTMLResponse)
def api_get_parchi_slip(request: Request, token_number: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.*, b.name as branch_name, b.mandi_license_no,
                   pt.name as party_name, pt.party_type, pt.village, pt.phone, pt.khasra_record_no
            FROM purchase_invoices p
            JOIN branches b ON p.branch_id = b.id
            JOIN parties pt ON p.party_id = pt.id
            WHERE p.token_number=?
        """, (token_number,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Token not found")
        invoice = dict(row)
    finally:
        conn.close()

    return templates.TemplateResponse(request=request, name="parchi_slip.html", context={"invoice": invoice})

@app.post("/api/branch/farmers/register")
def api_branch_register_farmer(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    village: str = Form(...),
    khasra_record_no: str = Form(...),
    home_branch_id: Optional[str] = Form(None),
    aadhaar_number: Optional[str] = Form(""),
    bank_name: Optional[str] = Form(""),
    bank_account_no: Optional[str] = Form(""),
    bank_ifsc: Optional[str] = Form("")
):
    user = require_role(request, ["BRANCH_CASHIER", "ACCOUNTANT_HQ", "SUPER_ADMIN"])
    if user.get("role") == "BRANCH_CASHIER" and user.get("branch_id"):
        home_branch_id = user.get("branch_id")

    pid = f"p-{uuid.uuid4().hex[:8]}"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO parties (
                id, home_branch_id, name, phone, party_type, village, 
                khasra_record_no, aadhaar_number, bank_name, bank_account_no, bank_ifsc
            ) VALUES (?, ?, ?, ?, 'FARMER', ?, ?, ?, ?, ?, ?)
        """, (pid, home_branch_id, name.strip(), phone.strip(), village.strip(), khasra_record_no.strip(), aadhaar_number or "", bank_name or "", bank_account_no or "", bank_ifsc or ""))
        conn.commit()

        return {
            "success": True,
            "id": pid,
            "name": name,
            "village": village,
            "khasra_record_no": khasra_record_no
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# API ENDPOINT: CASHIER VERIFICATION & PAYOUT DESK
# --------------------------------------------------------------------------

@app.post("/api/cashier/payout")
def api_cashier_disburse_payout(
    request: Request,
    invoice_id: str = Form(...),
    branch_id: str = Form(...),
    payout_mode: str = Form("CASH"),  # CASH or BANK_TRANSFER
    bank_utr_no: Optional[str] = Form(""),
    notes_500: int = Form(0),
    notes_200: int = Form(0),
    notes_100: int = Form(0),
    notes_50: int = Form(0),
    notes_20: int = Form(0),
    notes_10: int = Form(0),
    coins: int = Form(0)
):
    require_active_license()
    user = require_role(request, ["BRANCH_CASHIER", "SUPER_ADMIN"])
    if user.get("role") == "BRANCH_CASHIER" and user.get("branch_id"):
        branch_id = user.get("branch_id")

    today_str = date.today().isoformat()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.*, pt.party_type, pt.name as party_name, pt.current_advance 
            FROM purchase_invoices p
            JOIN parties pt ON p.party_id = pt.id
            WHERE p.id=?
        """, (invoice_id,))
        inv = cur.fetchone()

        if not inv:
            raise HTTPException(status_code=404, detail="Invoice record not found")

        if user.get("role") == "BRANCH_CASHIER" and inv["branch_id"] != branch_id:
            raise HTTPException(status_code=403, detail="Unauthorized: Cashier cannot disburse payout for an invoice from another branch.")

        if inv["payout_status"] == "PAID":
            raise HTTPException(status_code=400, detail="This invoice has already been paid and settled.")

        if inv["payout_status"] == "RTGS_PENDING":
            return {
                "success": False,
                "reason": "RTGS_PENDING",
                "error": "This invoice has an active RTGS Transfer Request with Central Accounts. Awaiting accountant UTR entry."
            }

        if inv["payout_status"] == "CANCELLED":
            raise HTTPException(status_code=400, detail="This invoice was cancelled and cannot be paid.")

        if inv["rate_override_status"] == "PENDING":
            return {
                "success": False,
                "reason": "RATE_OVERRIDE_PENDING",
                "error": "This purchase rate is out of daily corridor and requires Central Accounts approval before cashier payout."
            }

        net_payable = inv["net_payable_amount"]

        # Calculate exact cash round-up if CASH payout
        if payout_mode == "CASH":
            roundup_calc = calculate_cash_payout_with_roundup(net_payable)
            rounded_amount = roundup_calc["rounded_cash_payout"]
            round_off = roundup_calc["round_off_amount"]

            # Statutory compliance check (Section 269ST & 40A(3))
            cur.execute("""
                SELECT COALESCE(SUM(amount_paid), 0.0) 
                FROM cashier_payouts 
                WHERE party_id=? AND date(created_at)=? AND payout_mode='CASH'
            """, (inv["party_id"], today_str))
            today_cum_cash = cur.fetchone()[0]

            compliance = check_cash_compliance(
                party_type=inv["party_type"],
                payout_mode="CASH",
                payout_amount=rounded_amount,
                today_cumulative_cash_to_party=today_cum_cash
            )
            if not compliance["allowed"]:
                return {"success": False, "reason": compliance.get("rule", "NON_COMPLIANT"), "error": compliance["reason"]}

            # Denomination match check
            denom_val = validate_cash_denominations(
                expected_amount=rounded_amount,
                notes_500=notes_500,
                notes_200=notes_200,
                notes_100=notes_100,
                notes_50=notes_50,
                notes_20=notes_20,
                notes_10=notes_10,
                coins=coins
            )
            if not denom_val["valid"]:
                return {
                    "success": False,
                    "reason": "DENOMINATION_MISMATCH",
                    "error": f"Counted physical cash ₹{denom_val['total_counted']} does not match expected rounded payout ₹{rounded_amount} (Diff: ₹{denom_val['difference']})."
                }

            disbursed_amount = rounded_amount
        else:
            disbursed_amount = net_payable
            round_off = 0.0
            if not bank_utr_no or not bank_utr_no.strip():
                return {"success": False, "error": "Bank UTR / Transaction Reference Number is mandatory for Bank Transfer."}

        # Select cashier user for this branch
        cur.execute("SELECT id FROM users WHERE branch_id=? AND role='BRANCH_CASHIER' LIMIT 1", (branch_id,))
        cashier_row = cur.fetchone()
        cashier_id = cashier_row["id"] if cashier_row else "u-admin"

        # 1. Record Cashier Payout
        payout_id = f"pay-{uuid.uuid4().hex[:8]}"
        cur.execute("""
            INSERT INTO cashier_payouts (
                id, branch_id, invoice_id, party_id, payout_mode, amount_paid,
                notes_500, notes_200, notes_100, notes_50, notes_20, notes_10, coins,
                bank_utr_no, cashier_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payout_id, branch_id, invoice_id, inv["party_id"], payout_mode, disbursed_amount,
            notes_500, notes_200, notes_100, notes_50, notes_20, notes_10, coins,
            bank_utr_no or "", cashier_id
        ))

        # 2. Update Invoice Status
        cur.execute("""
            UPDATE purchase_invoices 
            SET payout_status='PAID', rounded_net_payable=?, round_off_amount=? 
            WHERE id=?
        """, (disbursed_amount, round_off, invoice_id))

        # 3. Update Party Advance if loan was adjusted
        if inv["advance_adjusted"] > 0:
            cur.execute("""
                UPDATE parties 
                SET current_advance = MAX(0.0, current_advance - ?) 
                WHERE id=?
            """, (inv["advance_adjusted"], inv["party_id"]))

        # 4. Create Traceable Double-Entry Ledgers
        v_date = today_str
        v_token = inv["token_number"]

        # Produce Expense Debit
        cur.execute("""
            INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, narration)
            VALUES (?, ?, ?, 'PURCHASE', ?, 'Commodity Purchase Account', ?, ?, ?)
        """, (f"led-{uuid.uuid4().hex[:6]}", branch_id, v_date, v_token, inv["party_id"], inv["gross_amount"], f"Purchase of {inv['commodity_name']} ({inv['net_quintals']} Qtl)"))

        # Cash / Bank Credit
        credit_account = "Branch Cash Drawer" if payout_mode == "CASH" else "Mandi Operating Bank Account"
        cur.execute("""
            INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, credit_amount, narration)
            VALUES (?, ?, ?, 'PAYOUT', ?, ?, ?, ?, ?)
        """, (f"led-{uuid.uuid4().hex[:6]}", branch_id, v_date, v_token, credit_account, inv["party_id"], disbursed_amount, f"Settlement for token {v_token} ({payout_mode})"))

        # Round-Off Account balancing
        if round_off != 0.0:
            cur.execute("""
                INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, narration)
                VALUES (?, ?, ?, 'ROUNDOFF', ?, 'Round-Off Difference Account', ?, ?, 'Paisa rounding up to nearest rupee')
            """, (f"led-{uuid.uuid4().hex[:6]}", branch_id, v_date, v_token, inv["party_id"], round_off))

        # 5. Update Branch Cash Drawer if cash
        if payout_mode == "CASH":
            cur.execute("""
                UPDATE branch_daily_cash_drawers 
                SET total_cash_payouts = total_cash_payouts + ?,
                    calculated_closing_cash = calculated_closing_cash - ?
                WHERE branch_id=? AND record_date=?
            """, (disbursed_amount, disbursed_amount, branch_id, today_str))

        conn.commit()

        return {
            "success": True,
            "voucher_id": v_token,
            "payout_id": payout_id,
            "payout_mode": payout_mode,
            "amount_paid": disbursed_amount,
            "party_name": inv["party_name"]
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Commodity Mandi ERP Server on http://0.0.0.0:{port} ...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
