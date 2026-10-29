"""
Comprehensive Automated Test Suite for Commercial Licensing, Authentication,
and Multi-Yard Role Isolation in Rajeshri Shahu Mandi & Commodity Procurement ERP.
"""

import os
import sys
import unittest
import base64
import json
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app, create_session_token, verify_session_token
from database import get_connection, hash_password, verify_password, login_admin
from licensing import (
    verify_license_token,
    save_license_token,
    get_active_license,
    check_branch_limit,
    DEFAULT_COMMERCIAL_LICENSE_TOKEN
)
from vendor_license_issuer import generate_signed_license_token
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


class TestLicensingAndSecurity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.unauth_client = TestClient(app, follow_redirects=False)
        cls.test_priv = ed25519.Ed25519PrivateKey.generate()
        cls.test_priv_hex = cls.test_priv.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
        ).hex()
        cls.test_pub_hex = cls.test_priv.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ).hex()

    def test_01_unauthenticated_admin_dashboard_redirects_to_login(self):
        """Unauthenticated GET /admin/dashboard must fail closed and redirect to /login."""
        res = self.unauth_client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/login")

    def test_02_unauthenticated_staff_update_api_returns_401(self):
        """Unauthenticated POST to administrative staff update API must return HTTP 401."""
        res = self.unauth_client.post("/api/admin/staff/update-all", data={
            "acc_name": "Test Accountant",
            "acc_username": "accountant",
            "acc_phone": "9826022222",
            "chk_name": "Test Cashier",
            "chk_username": "chikhali_cashier",
            "chk_phone": "9826033333",
            "vrv_name": "Test Varvand",
            "vrv_username": "varvand_cashier",
            "vrv_phone": "9826044444",
            "dhd_name": "Test Dhad",
            "dhd_username": "dhad_cashier",
            "dhd_phone": "9826055555"
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json().get("detail", ""))

    def test_03_unauthenticated_commodity_rates_api_returns_401(self):
        """Unauthenticated POST to central accounts daily rate corridor API must return HTTP 401."""
        res = self.unauth_client.post("/api/accounts/rates", data={
            "rate_date": "2026-10-29",
            "commodity_name": "Soyabean (Yellow)",
            "quality_grade": "FAQ (Standard Mandi Lot)",
            "min_rate": 4500,
            "target_rate": 4650,
            "max_rate": 4800
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json().get("detail", ""))

    def test_04_unauthenticated_invoice_create_api_returns_401(self):
        """Unauthenticated POST to inward invoice creation API must return HTTP 401."""
        res = self.unauth_client.post("/api/branch/invoices/create", data={
            "branch_id": "br-chikhali",
            "party_id": "p-farmer-1",
            "inspector_name": "Mahesh Patidar",
            "commodity_name": "Soyabean (Yellow)",
            "rate_per_quintal": 4650
        })
        self.assertEqual(res.status_code, 401)
        self.assertIn("Authentication required", res.json().get("detail", ""))

    def test_05_role_isolation_cashier_blocked_from_admin_and_accounts(self):
        """Branch Cashier must be strictly blocked from Super Admin and Central Accounts portals."""
        cashier_token = create_session_token("chikhali_cashier", "BRANCH_CASHIER", branch_id="br-chikhali")
        client = TestClient(app, follow_redirects=False)
        client.cookies.set("mandi_session", cashier_token)

        # Cashier trying to access Super Admin dashboard -> redirected to own branch dashboard
        res_admin = client.get("/admin/dashboard")
        self.assertEqual(res_admin.status_code, 303)
        self.assertIn("/branch/dashboard", res_admin.headers["location"])

        # Cashier trying to access Central Accounts dashboard -> redirected to own branch dashboard
        res_acc = client.get("/accounts/dashboard")
        self.assertEqual(res_acc.status_code, 303)
        self.assertIn("/branch/dashboard", res_acc.headers["location"])

        # Cashier trying to invoke admin branch-creation API -> HTTP 403 Forbidden
        res_add_branch = client.post("/api/admin/branches", data={
            "branch_code": "BR-TEST",
            "name": "Unauthorized Yard"
        })
        self.assertEqual(res_add_branch.status_code, 403)
        self.assertIn("Forbidden", res_add_branch.json().get("detail", ""))

    def test_06_branch_isolation_parameter_tampering_overridden(self):
        """Cashier attempting to submit an invoice for another branch yard has branch_id forced to assigned yard."""
        cashier_token = create_session_token("chikhali_cashier", "BRANCH_CASHIER", branch_id="br-chikhali")
        client = TestClient(app, follow_redirects=False)
        client.cookies.set("mandi_session", cashier_token)

        # Chikhali cashier attempts to create invoice for Varvand yard
        res = client.post("/api/branch/invoices/create", data={
            "branch_id": "br-varvand",  # Tampered parameter
            "party_id": "p-farmer-1",
            "inspector_name": "Mahesh Patidar",
            "commodity_name": "Wheat (Lokwan)",
            "rate_per_quintal": 2750,
            "weighment_mode": "MANUAL_YARD",
            "yard_weight_kg": 2000
        })
        self.assertIn(res.status_code, [200, 303])
        data = res.json()
        self.assertTrue(data["success"])
        invoice_id = data["invoice_id"]

        # Verify in database that invoice was stored under br-chikhali, NOT br-varvand
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT branch_id FROM purchase_invoices WHERE id=?", (invoice_id,))
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row["branch_id"], "br-chikhali", "Server must override tampered branch_id with cashier's session branch")

    def test_07_setup_endpoint_returns_404_when_setup_completed(self):
        """Once initial system provisioning is marked complete, /setup must return HTTP 404 permanently."""
        # Ensure is_setup_completed is 1
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE system_settings SET setting_value='1' WHERE scope='SUPER_ADMIN' AND setting_key='is_setup_completed'")
        conn.commit()
        conn.close()

        res_get = self.unauth_client.get("/setup")
        self.assertEqual(res_get.status_code, 404)
        self.assertIn("First-run provisioning is permanently closed", res_get.json().get("detail", ""))

        res_post = self.unauth_client.post("/setup", data={"org_name": "Attacker Enterprise"})
        self.assertEqual(res_post.status_code, 404)

    def test_08_valid_ed25519_signed_license_token_accepted(self):
        """Valid vendor-signed Ed25519 commercial license token must verify successfully with all claims."""
        # 1. Verify default commercial license token against active vendor public key
        valid, msg, claims = verify_license_token(DEFAULT_COMMERCIAL_LICENSE_TOKEN)
        self.assertTrue(valid, f"Default commercial license token failed verification: {msg}")
        self.assertEqual(claims["tier"], "PRO")
        self.assertEqual(claims["max_branches"], 3)

        # 2. Verify dynamically generated license token signed with isolated test key
        token = generate_signed_license_token(
            licensee_name="Rajeshri Shahu Trading Co.",
            tier="ENTERPRISE",
            max_branches=10,
            valid_days=365,
            private_key_hex=self.test_priv_hex
        )
        is_valid, msg, claims = verify_license_token(token, custom_public_key_hex=self.test_pub_hex)
        self.assertTrue(is_valid, f"Signature verification failed: {msg}")
        self.assertEqual(claims["tier"], "ENTERPRISE")
        self.assertEqual(claims["max_branches"], 10)
        self.assertEqual(claims["licensee_name"], "Rajeshri Shahu Trading Co.")

    def test_09_tampered_or_invalid_license_token_rejected(self):
        """A tampered license token (e.g. modified claims or invalid signature) must fail closed."""
        valid_token = DEFAULT_COMMERCIAL_LICENSE_TOKEN
        payload_b64, sig_b64 = valid_token.split(".")

        # Decode payload, modify branch limit from 3 to 999, re-encode without vendor's private key
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))
        payload["max_branches"] = 999
        tampered_payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        tampered_token = f"{tampered_payload_b64}.{sig_b64}"

        is_valid, msg, claims = verify_license_token(tampered_token)
        self.assertFalse(is_valid)
        self.assertIn("Digital signature verification failed", msg)

        # Super Admin API must also reject tampered token
        admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        client = TestClient(app, follow_redirects=False)
        client.cookies.set("mandi_session", admin_token)

        res = client.post("/api/admin/license/activate", data={"license_token": tampered_token})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid License Token", res.json().get("detail", ""))

    def test_10_expired_license_blocks_business_operations(self):
        """An expired commercial license token must block inward produce intake with HTTP 403."""
        # Generate an expired license token (-10 days)
        expired_token = generate_signed_license_token(
            licensee_name="Rajeshri Shahu Trading Co.",
            tier="PRO",
            max_branches=3,
            valid_days=-10,
            private_key_hex=self.test_priv_hex
        )
        # Directly store expired token into database to simulate elapsed validity
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE system_settings SET setting_value=? WHERE scope='SUPER_ADMIN' AND setting_key='license_token'", (expired_token,))
        conn.commit()
        conn.close()

        cashier_token = create_session_token("chikhali_cashier", "BRANCH_CASHIER", branch_id="br-chikhali")
        client = TestClient(app, follow_redirects=False)
        client.cookies.set("mandi_session", cashier_token)

        res_inv = client.post("/api/branch/invoices/create", data={
            "branch_id": "br-chikhali",
            "party_id": "p-farmer-1",
            "inspector_name": "Mahesh Patidar",
            "commodity_name": "Soyabean (Yellow)",
            "rate_per_quintal": 4650
        })
        self.assertEqual(res_inv.status_code, 403)
        self.assertIn("Commercial License Inactive or Expired", res_inv.json().get("detail", ""))

        # Restore valid commercial license for subsequent tests
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE system_settings SET setting_value=? WHERE scope='SUPER_ADMIN' AND setting_key='license_token'", (DEFAULT_COMMERCIAL_LICENSE_TOKEN,))
        conn.commit()
        conn.close()

    def test_11_branch_creation_beyond_license_limit_rejected(self):
        """Attempting to add active branches beyond the licensed max_branches quota must return HTTP 403."""
        admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        client = TestClient(app, follow_redirects=False)
        client.cookies.set("mandi_session", admin_token)

        # Default license allows max 3 branches. Current active branches = 3.
        res = client.post("/api/admin/branches", data={
            "branch_code": "BR-EXCESS",
            "name": "Excess Yard 4",
            "address": "Buldhana Road"
        })
        self.assertEqual(res.status_code, 403)
        self.assertIn("branch limit reached", res.json().get("detail", "").lower())

    def test_12_logout_revokes_session_in_database(self):
        """Calling /logout must revoke the active session row in SQLite and prevent token reuse."""
        client = TestClient(app, follow_redirects=False)
        login_res = client.post("/login", data={"username": "accountant", "password": "accpassword123"})
        if login_res.status_code != 303:
            login_res = client.post("/login", data={"username": "accountant", "password": "acc123"})
        self.assertEqual(login_res.status_code, 303)
        cookie = login_res.cookies.get("mandi_session")
        self.assertIsNotNone(cookie)

        # Parse token to extract session_id
        session_info = verify_session_token(cookie)
        self.assertIsNotNone(session_info)
        session_id = session_info["session_id"]
        self.assertIsNotNone(session_id)

        # Verify session is initially active
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_revoked FROM user_sessions WHERE session_id=?", (session_id,))
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row["is_revoked"], 0)

        # Perform logout
        logout_res = client.get("/logout")
        self.assertEqual(logout_res.status_code, 303)

        # Verify session is revoked in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_revoked FROM user_sessions WHERE session_id=?", (session_id,))
        row = cur.fetchone()
        conn.close()
        self.assertEqual(row["is_revoked"], 1)

        # Attempting to use the revoked cookie token must fail validation
        self.assertIsNone(verify_session_token(cookie))

    def test_13_legacy_password_transparently_rehashed_on_login(self):
        """Logging in with a legacy unsalted SHA-256 password must transparently migrate it to salted PBKDF2."""
        conn = get_connection()
        cur = conn.cursor()
        import hashlib
        legacy_pass = "temporary_migration_pass_999"
        legacy_hash = hashlib.sha256(legacy_pass.encode("utf-8")).hexdigest()
        test_user_id = "u-migration-test"
        cur.execute("DELETE FROM user_sessions WHERE user_id=?", (test_user_id,))
        cur.execute("DELETE FROM users WHERE id=?", (test_user_id,))
        cur.execute(
            "INSERT INTO users (id, username, password_hash, role, full_name, phone, is_active) VALUES (?, ?, ?, 'BRANCH_CASHIER', 'Migration Test User', '9826000000', 1)",
            (test_user_id, "migration_user", legacy_hash)
        )
        conn.commit()
        conn.close()

        # Login with plaintext password
        client = TestClient(app, follow_redirects=False)
        res = client.post("/login", data={"username": "migration_user", "password": legacy_pass})
        self.assertEqual(res.status_code, 303)

        # Verify that the password_hash was automatically re-hashed to PBKDF2
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id=?", (test_user_id,))
        new_hash = cur.fetchone()["password_hash"]
        cur.execute("DELETE FROM user_sessions WHERE user_id=?", (test_user_id,))
        cur.execute("DELETE FROM users WHERE id=?", (test_user_id,))
        conn.commit()
        conn.close()

        self.assertTrue(new_hash.startswith("pbkdf2_sha256$600000$"), f"Expected PBKDF2 hash, got: {new_hash}")
        is_valid, needs_rehash = verify_password(legacy_pass, new_hash)
        self.assertTrue(is_valid)
        self.assertFalse(needs_rehash, "Migrated PBKDF2 hash should not need further rehashing")

    def test_14_retired_compromised_signer_strictly_rejected(self):
        """Tokens signed by the retired or compromised vendor key must be explicitly rejected with revocation reason."""
        old_compromised_token = (
            "eyJleHBpcmVzX2F0IjoiMjAyNy0wMy0zMVQyMzo1OTo1OVoiLCJmZWF0dXJlcyI6WyJNVUxUSV9CUkFOQ0giLCJSVEdTX0RFU0siLCJPVVRXQVJEX0NIQUxMQU4iLCJBVURJVF9MT0dTIl0sImlzc3VlZF9hdCI6IjIwMjYtMDQtMDFUMDA6MDA6MDBaIiwibGljZW5zZV9pZCI6IkxJQy1SU1QtMjAyNi1NSDNCLTg5QTEyRiIsImxpY2Vuc2VlX25hbWUiOiJSYWplc2hyaSBTaGFodSBUcmFkaW5nIENvLiIsIm1heF9icmFuY2hlcyI6MywicHJvZHVjdCI6IlNIQUhVX01BTkRJX0VSUCIsInRpZXIiOiJQUk8ifQ==."
            "Zd0k1Lz8JRi8C33R0lx_iVX9vZFwSJsr9G1QRx-US0jor8EtUtbjEfEVyihQrgr0cwUvk29Kp50Dsf__4n6HCQ=="
        )
        is_valid, msg, claims = verify_license_token(old_compromised_token)
        self.assertFalse(is_valid)
        self.assertIn("retired or revoked vendor key", msg.lower())

    def test_15_future_dated_not_yet_valid_license_rejected(self):
        """A license with a future valid_from date must be rejected as not yet valid."""
        future_start = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        future_token = generate_signed_license_token(
            licensee_name="Rajeshri Shahu Trading Co.",
            tier="PRO",
            max_branches=3,
            valid_days=365,
            private_key_hex=self.test_priv_hex
        )
        # Re-encode with future valid_from
        p_b64, s_b64 = future_token.split(".")
        payload = json.loads(base64.urlsafe_b64decode(p_b64.encode("utf-8")).decode("utf-8"))
        payload["valid_from"] = future_start
        p_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sig = self.test_priv.sign(p_bytes)
        tok = base64.urlsafe_b64encode(p_bytes).decode("utf-8") + "." + base64.urlsafe_b64encode(sig).decode("utf-8")

        is_valid, msg, _ = verify_license_token(tok, custom_public_key_hex=self.test_pub_hex)
        self.assertFalse(is_valid)
        self.assertIn("not yet valid", msg.lower())

    def test_16_disabled_account_session_rejected_immediately(self):
        """When an account is deactivated in the database, its active sessions must be rejected immediately."""
        conn = get_connection()
        cur = conn.cursor()
        test_uid = "u-deactivate-test"
        cur.execute("DELETE FROM user_sessions WHERE user_id=?", (test_uid,))
        cur.execute("DELETE FROM users WHERE id=?", (test_uid,))
        cur.execute(
            "INSERT INTO users (id, username, password_hash, role, full_name, phone, is_active) VALUES (?, 'deact_user', 'somehash', 'BRANCH_CASHIER', 'Deact User', '9826000000', 1)",
            (test_uid,)
        )
        conn.commit()
        conn.close()

        token = create_session_token("deact_user", "BRANCH_CASHIER", branch_id="br-chikhali", user_id=test_uid)
        self.assertIsNotNone(verify_session_token(token))

        # Admin deactivates account
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_active=0 WHERE id=?", (test_uid,))
        conn.commit()
        conn.close()

        # Session must now be rejected
        self.assertIsNone(verify_session_token(token), "Disabled user session must be rejected immediately")

        # Cleanup
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM user_sessions WHERE user_id=?", (test_uid,))
        cur.execute("DELETE FROM users WHERE id=?", (test_uid,))
        conn.commit()
        conn.close()

    def test_17_role_change_reflected_immediately_from_database(self):
        """Role changes in SQLite must take effect immediately on active sessions."""
        conn = get_connection()
        cur = conn.cursor()
        test_uid = "u-rolechange-test"
        cur.execute("DELETE FROM user_sessions WHERE user_id=?", (test_uid,))
        cur.execute("DELETE FROM users WHERE id=?", (test_uid,))
        cur.execute(
            "INSERT INTO users (id, username, password_hash, role, full_name, phone, is_active) VALUES (?, 'role_user', 'somehash', 'BRANCH_CASHIER', 'Role User', '9826000000', 1)",
            (test_uid,)
        )
        conn.commit()
        conn.close()

        token = create_session_token("role_user", "BRANCH_CASHIER", branch_id="br-chikhali", user_id=test_uid)
        sess = verify_session_token(token)
        self.assertEqual(sess["role"], "BRANCH_CASHIER")

        # Super Admin promotes user to ACCOUNTANT_HQ in the database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET role='ACCOUNTANT_HQ' WHERE id=?", (test_uid,))
        conn.commit()
        conn.close()

        # Existing token must reflect the authoritative role
        sess_updated = verify_session_token(token)
        self.assertIsNotNone(sess_updated)
        self.assertEqual(sess_updated["role"], "ACCOUNTANT_HQ", "Authoritative role must be derived from live database")

        # Cleanup
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM user_sessions WHERE user_id=?", (test_uid,))
        cur.execute("DELETE FROM users WHERE id=?", (test_uid,))
        conn.commit()
        conn.close()

    def test_18_password_reset_revokes_active_sessions(self):
        """When an admin updates a staff password, active sessions for that user must be revoked."""
        client = TestClient(app, follow_redirects=False)
        # Login accountant
        login_res = client.post("/login", data={"username": "accountant", "password": "accpassword123"})
        if login_res.status_code != 303:
            login_res = client.post("/login", data={"username": "accountant", "password": "acc123"})
        acc_cookie = login_res.cookies.get("mandi_session")
        self.assertIsNotNone(acc_cookie)
        self.assertIsNotNone(verify_session_token(acc_cookie))

        # Admin updates accountant's credentials with new password
        admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        admin_client = TestClient(app, follow_redirects=False)
        admin_client.cookies.set("mandi_session", admin_token)

        res = admin_client.post("/api/admin/users/update-credentials", data={
            "user_id": "u-accountant",
            "full_name": "Omprakash Agrawal",
            "phone": "9826022222",
            "username": "accountant",
            "new_password": "new_secure_password_777"
        })
        self.assertIn(res.status_code, [200, 303])

        # Accountant's earlier session must now be revoked
        self.assertIsNone(verify_session_token(acc_cookie), "Earlier session must be revoked after password change")

        # Restore original password for accountant
        admin_client.post("/api/admin/users/update-credentials", data={
            "user_id": "u-accountant",
            "full_name": "Omprakash Agrawal",
            "phone": "9826022222",
            "username": "accountant",
            "new_password": "accpassword123"
        })

    def test_19_invalid_password_does_not_trigger_hash_upgrade(self):
        """Failed authentication with invalid password must never trigger hash re-hash or database changes."""
        conn = get_connection()
        cur = conn.cursor()
        import hashlib
        legacy_pass = "secret_pass_123"
        legacy_hash = hashlib.sha256(legacy_pass.encode("utf-8")).hexdigest()
        test_uid = "u-pw-upgrade-test"
        cur.execute("DELETE FROM user_sessions WHERE user_id=?", (test_uid,))
        cur.execute("DELETE FROM users WHERE id=?", (test_uid,))
        cur.execute(
            "INSERT INTO users (id, username, password_hash, role, full_name, phone, is_active) VALUES (?, 'upgrade_user', ?, 'BRANCH_CASHIER', 'Upgrade User', '9826000000', 1)",
            (test_uid, legacy_hash)
        )
        conn.commit()
        conn.close()

        # Submit wrong password
        client = TestClient(app, follow_redirects=False)
        res = client.post("/login", data={"username": "upgrade_user", "password": "WRONG_PASSWORD"})
        self.assertEqual(res.status_code, 401)

        # Confirm hash in database is still legacy unsalted SHA-256
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT password_hash FROM users WHERE id=?", (test_uid,))
        current_hash = cur.fetchone()["password_hash"]
        self.assertEqual(current_hash, legacy_hash, "Hash must remain unchanged upon failed login")

        # Cleanup
        cur.execute("DELETE FROM user_sessions WHERE user_id=?", (test_uid,))
        cur.execute("DELETE FROM users WHERE id=?", (test_uid,))
        conn.commit()
        conn.close()

    def test_20_branch_activation_toggle_checks_license_quota(self):
        """Activating an inactive branch via toggle API must enforce licensed branch quota."""
        admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        client = TestClient(app, follow_redirects=False)
        client.cookies.set("mandi_session", admin_token)

        # Create an inactive branch
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM branches WHERE id='br-inactive-test'")
        cur.execute(
            "INSERT INTO branches (id, branch_code, name, is_active) VALUES ('br-inactive-test', 'BR-INACT', 'Inactive Yard', 0)"
        )
        conn.commit()
        conn.close()

        # Currently 3 active branches exist (Chikhali, Varvand, Dhad), max_branches = 3.
        # Toggling inactive branch to active must return HTTP 403 Forbidden
        res = client.post("/api/admin/branches/toggle", data={"branch_id": "br-inactive-test"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("branch limit reached", res.json().get("detail", "").lower())

        # Cleanup
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM branches WHERE id='br-inactive-test'")
        conn.commit()
        conn.close()

    def test_21_login_admin_does_not_leak_password_hash(self):
        """database.login_admin() response must sanitize and omit password_hash."""
        res = login_admin("admin", "admin123")
        if not res.get("success"):
            res = login_admin("admin", "adminpassword123")
        self.assertTrue(res.get("success"))
        user_data = res.get("user", {})
        self.assertNotIn("password_hash", user_data, "API user payload must never expose password_hash")

    def test_22_production_key_separation_and_staging_rejection(self):
        """Under MANDI_ERP_ENV=production, staging tokens must be rejected and fail closed if no prod key is configured."""
        orig_env = os.environ.get("MANDI_ERP_ENV")
        orig_prod_key = os.environ.get("VENDOR_PRODUCTION_PUBLIC_KEY_HEX")
        try:
            # 1. Switch to strict production without configured production key
            os.environ["MANDI_ERP_ENV"] = "production"
            if "VENDOR_PRODUCTION_PUBLIC_KEY_HEX" in os.environ:
                del os.environ["VENDOR_PRODUCTION_PUBLIC_KEY_HEX"]

            valid, msg, _ = verify_license_token(DEFAULT_COMMERCIAL_LICENSE_TOKEN)
            self.assertFalse(valid, "Staging token must not be accepted in production mode")
            self.assertIn("not configured", msg.lower())

            # 2. Inject official production public key in environment and verify production token
            prod_priv = ed25519.Ed25519PrivateKey.generate()
            prod_pub_hex = prod_priv.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            ).hex()
            os.environ["VENDOR_PRODUCTION_PUBLIC_KEY_HEX"] = prod_pub_hex

            prod_priv_hex = prod_priv.private_bytes(
                serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
            ).hex()
            prod_token = generate_signed_license_token(
                licensee_name="Rajeshri Shahu Commercial Mandi",
                tier="ENTERPRISE",
                max_branches=5,
                valid_days=730,
                private_key_hex=prod_priv_hex
            )

            valid_prod, msg_prod, claims_prod = verify_license_token(prod_token)
            self.assertTrue(valid_prod, f"Production token verification failed: {msg_prod}")
            self.assertEqual(claims_prod["tier"], "ENTERPRISE")
            self.assertEqual(claims_prod["max_branches"], 5)

            # Staging token must still be rejected under production key configuration
            valid_staging, _, _ = verify_license_token(DEFAULT_COMMERCIAL_LICENSE_TOKEN)
            self.assertFalse(valid_staging, "Staging token must fail verification under production public key")
        finally:
            if orig_env is not None:
                os.environ["MANDI_ERP_ENV"] = orig_env
            else:
                os.environ.pop("MANDI_ERP_ENV", None)
            if orig_prod_key is not None:
                os.environ["VENDOR_PRODUCTION_PUBLIC_KEY_HEX"] = orig_prod_key
            else:
                os.environ.pop("VENDOR_PRODUCTION_PUBLIC_KEY_HEX", None)

    def test_23_isolated_clean_database_first_run_activation(self):
        """Verify first-run setup flow on a clean database: invalid license rejected, valid license activates, replay blocked with 404."""
        # Test the first-run logic via database state simulation
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key='is_setup_completed'")
        prev_setup_state = cur.fetchone()["setting_value"]

        try:
            # Simulate uncompleted setup state
            cur.execute("UPDATE system_settings SET setting_value='0' WHERE setting_key='is_setup_completed'")
            conn.commit()

            # 1. First-run setup page renders
            res_get = self.unauth_client.get("/setup")
            self.assertEqual(res_get.status_code, 200)

            # 2. Submitting invalid license fails
            res_bad = self.unauth_client.post("/setup", data={
                "org_name": "Test Yard Mandi",
                "owner_name": "Test Owner",
                "owner_username": "admin",
                "owner_password": "ownerpassword123",
                "license_key": "INVALID-CORRUPTED-LICENSE-STRING"
            })
            self.assertEqual(res_bad.status_code, 400)
            self.assertIn("License Verification Failed", res_bad.text)

            # 3. Submitting valid license completes setup
            res_good = self.unauth_client.post("/setup", data={
                "org_name": "Test Yard Mandi",
                "owner_name": "Test Owner",
                "owner_username": "admin",
                "owner_password": "ownerpassword123",
                "license_key": DEFAULT_COMMERCIAL_LICENSE_TOKEN
            })
            self.assertIn(res_good.status_code, [200, 303])

            # 4. Replay attempt on POST /setup must immediately return HTTP 404
            res_replay = self.unauth_client.post("/setup", data={"org_name": "Hacker Yard"})
            self.assertEqual(res_replay.status_code, 404)

            # 5. GET /setup must now return HTTP 404 permanently
            res_get_closed = self.unauth_client.get("/setup")
            self.assertEqual(res_get_closed.status_code, 404)
        finally:
            cur.execute("UPDATE system_settings SET setting_value=? WHERE setting_key='is_setup_completed'", (prev_setup_state,))
            conn.commit()
            conn.close()

    def test_24_build_script_excludes_vendor_issuer_and_secrets(self):
        """Verify build_desktop_app.py explicitly excludes vendor_license_issuer and bundles zero secrets."""
        build_script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build_desktop_app.py")
        self.assertTrue(os.path.exists(build_script_path))
        with open(build_script_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("--exclude-module", content)
        self.assertIn("vendor_license_issuer", content)

        # Check gitignore
        gitignore_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".gitignore")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            gi_content = f.read()
        self.assertIn("vendor_license_issuer.py", gi_content)
        self.assertIn("instance_secret.key", gi_content)


if __name__ == "__main__":
    unittest.main()
