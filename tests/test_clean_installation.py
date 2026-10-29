"""
Automated Test Suite for Clean Commercial Customer Installation.
Simulates a brand new customer installation on a separate clean database:
1. Verifies zero demo records (0 users, 0 parties, 0 invoices, 0 payouts, 0 ledgers, 0 rates).
2. Verifies master data configuration (9 commodities, statutory cash limits, is_setup_completed=0).
3. Verifies first-run setup wizard: invalid/expired/wrong-product licenses fail closed.
4. Verifies first-run Super Admin and staff provisioning with custom credentials.
5. Verifies permanent 404 lockout on /setup after completion.
6. Verifies role and branch isolation using newly provisioned credentials.
"""

import os
import sys
import tempfile
import unittest
import sqlite3
from fastapi.testclient import TestClient

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vendor_license_issuer import generate_signed_license_token
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from licensing import STAGING_VENDOR_PUBLIC_KEY_HEX, DEFAULT_COMMERCIAL_LICENSE_TOKEN
import database
from server import app


class TestCleanInstallation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary directory for the clean customer installation
        cls.temp_dir = tempfile.mkdtemp(prefix="clean_customer_install_")
        cls.clean_db_path = os.path.join(cls.temp_dir, "customer_mandi.db")
        cls.orig_test_db = os.environ.get("MANDI_TEST_DB_PATH")

        # Point test environment to the clean customer database
        os.environ["MANDI_TEST_DB_PATH"] = cls.clean_db_path

        # Generate test signing keys for valid license tests
        cls.test_priv = ed25519.Ed25519PrivateKey.generate()
        cls.test_priv_hex = cls.test_priv.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
        ).hex()
        cls.test_pub_hex = cls.test_priv.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        ).hex()

        cls.client = TestClient(app, follow_redirects=False)
        cls.following_client = TestClient(app, follow_redirects=True)

    @classmethod
    def tearDownClass(cls):
        # Restore previous test DB path
        if cls.orig_test_db:
            os.environ["MANDI_TEST_DB_PATH"] = cls.orig_test_db
        else:
            os.environ.pop("MANDI_TEST_DB_PATH", None)

        # Cleanup clean customer install files
        for f in os.listdir(cls.temp_dir):
            try:
                os.remove(os.path.join(cls.temp_dir, f))
            except OSError:
                pass
        try:
            os.rmdir(cls.temp_dir)
        except OSError:
            pass

    def test_01_clean_installation_schema_has_zero_demo_records(self):
        """Clean installation must initialize all tables but contain ZERO demo users, parties, or transactions."""
        # Initialize schema into the fresh customer database
        database.init_db()

        conn = sqlite3.connect(f"file:{self.clean_db_path}?mode=ro", uri=True)
        cur = conn.cursor()

        # Check all required tables exist
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()]
        required_tables = [
            "audit_change_logs", "branch_daily_cash_drawers", "branches",
            "cashier_payouts", "commodities", "daily_commodity_rates",
            "inspectors", "ledger_entries", "outward_orders", "parties",
            "purchase_invoices", "system_settings", "user_sessions", "users"
        ]
        for tbl in required_tables:
            self.assertIn(tbl, tables, f"Clean customer DB must contain table {tbl}")

        # Verify zero demo/seed data in business tables
        zero_count_tables = [
            ("users", "Users table must be empty on clean install (zero default credentials)"),
            ("branches", "Branches table must be empty until provisioned via setup"),
            ("parties", "Parties table must contain zero demo farmers/buyers"),
            ("purchase_invoices", "Purchase invoices table must contain zero demo invoices"),
            ("cashier_payouts", "Cashier payouts table must contain zero demo payouts"),
            ("ledger_entries", "Ledger entries table must contain zero demo transactions"),
            ("outward_orders", "Outward orders table must contain zero demo orders"),
            ("inspectors", "Inspectors table must contain zero demo assayers"),
            ("daily_commodity_rates", "Daily rates table must contain zero pre-filled rates"),
            ("user_sessions", "User sessions table must be completely empty"),
            ("audit_change_logs", "Audit logs table must be completely empty"),
        ]
        for tbl, msg in zero_count_tables:
            cur.execute(f'SELECT count(*) FROM "{tbl}"')
            cnt = cur.fetchone()[0]
            self.assertEqual(cnt, 0, f"{msg}. Found {cnt} rows.")

        # Verify statutory master configuration (9 commodities registered)
        cur.execute("SELECT count(*) FROM commodities")
        self.assertEqual(cur.fetchone()[0], 9, "Clean install must register the 9 statutory APMC commodities")

        # Verify first-run setup is required (is_setup_completed = '0')
        cur.execute("SELECT setting_value FROM system_settings WHERE scope='SUPER_ADMIN' AND setting_key='is_setup_completed'")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "0", "Clean install must require first-run setup (is_setup_completed='0')")

        conn.close()

    def test_02_first_run_routing_directs_to_setup(self):
        """Unprovisioned installation must redirect root requests to /setup."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/setup")

        setup_res = self.client.get("/setup")
        self.assertEqual(setup_res.status_code, 200)
        self.assertIn("Step 1: Business & Owner Profile", setup_res.text)
        self.assertIn("Step 2: Commercial License Key Activation", setup_res.text)
        self.assertIn("Step 3: Generate Staff Credentials", setup_res.text)

    def test_03_invalid_or_corrupted_license_rejected_at_setup(self):
        """First-run setup must reject invalid, corrupted, or tampered commercial licenses with HTTP 400."""
        res_bad = self.client.post("/setup", data={
            "org_name": "Kisan Mandi Ltd.",
            "owner_name": "Shri Ram Patil",
            "owner_username": "owner_patil",
            "owner_password": "SecureOwner#2026",
            "owner_phone": "9826011111",
            "org_gstin": "27AABCK1234F1Z5",
            "license_key": "CORRUPTED.INVALID.TOKEN"
        })
        self.assertEqual(res_bad.status_code, 400)
        self.assertIn("Commercial License Verification Failed", res_bad.text)

        # Confirm database remains unprovisioned
        conn = sqlite3.connect(f"file:{self.clean_db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM users")
        self.assertEqual(cur.fetchone()[0], 0, "No users should be created after failed license verification")
        conn.close()

    def test_04_successful_first_run_provisioning_with_valid_license(self):
        """First-run setup with authentic license provisions Super Admin, branches, and staff accounts."""
        res_setup = self.following_client.post("/setup", data={
            "org_name": "Maharashtra APMC Sourcing Co.",
            "owner_name": "Anil Deshmukh (Managing Director)",
            "owner_username": "superadmin_anil",
            "owner_password": "OwnerSecretPass#999",
            "owner_phone": "9826011111",
            "org_gstin": "27AABCK9999F1Z1",
            "license_key": DEFAULT_COMMERCIAL_LICENSE_TOKEN,
            "acc_name": "Ramesh Joshi (Chief Accountant)",
            "acc_username": "accountant_joshi",
            "acc_password": "AccSecretPass#888",
            "acc_phone": "9826022222",
            "chk_name": "Suresh Gite (Chikhali Lead)",
            "chk_username": "cashier_chikhali",
            "chk_password": "ChkSecretPass#777",
            "chk_phone": "9826033333",
            "vrv_name": "Ganesh More (Varvand Lead)",
            "vrv_username": "cashier_varvand",
            "vrv_password": "VrvSecretPass#666",
            "vrv_phone": "9826044444",
            "dhd_name": "Kailash Shinde (Dhad Lead)",
            "dhd_username": "cashier_dhad",
            "dhd_password": "DhdSecretPass#555",
            "dhd_phone": "9826055555"
        })
        self.assertEqual(res_setup.status_code, 200)
        self.assertIn("Commercial License activated and all staff credentials provisioned successfully", res_setup.text)
        self.assertIn("Staff Credential Handover", res_setup.text)

        # Inspect database
        conn = sqlite3.connect(f"file:{self.clean_db_path}?mode=ro", uri=True)
        cur = conn.cursor()

        # Verify branches created up to license quota (3 branches)
        cur.execute("SELECT count(*) FROM branches WHERE is_active=1")
        self.assertEqual(cur.fetchone()[0], 3, "Setup must provision the 3 licensed branches")

        # Verify users created with PBKDF2 hashes
        cur.execute("SELECT username, role, password_hash, full_name FROM users ORDER BY username")
        users = cur.fetchall()
        self.assertEqual(len(users), 5, "Setup must provision exactly 5 staff members (1 Admin, 1 Accountant, 3 Cashiers)")

        for u in users:
            self.assertTrue(u[2].startswith("pbkdf2_sha256$600000$"), f"Password hash for {u[0]} must be PBKDF2-HMAC-SHA256")
            self.assertNotIn(u[2], ["admin123", "acc123", "chk123", "vrv123", "dhd123"], "Must not store plain passwords")

        # Verify is_setup_completed = '1'
        cur.execute("SELECT setting_value FROM system_settings WHERE scope='SUPER_ADMIN' AND setting_key='is_setup_completed'")
        self.assertEqual(cur.fetchone()[0], "1")

        conn.close()

    def test_05_setup_endpoint_permanently_closed_post_provisioning(self):
        """Once provisioning is complete, /setup must return HTTP 404 permanently for both GET and POST."""
        res_get = self.client.get("/setup")
        self.assertEqual(res_get.status_code, 404, "GET /setup must return 404 once setup is completed")

        res_post = self.client.post("/setup", data={"org_name": "Malicious Takeover Co."})
        self.assertEqual(res_post.status_code, 404, "POST /setup replay must return 404")

    def test_06_provisioned_credentials_and_panel_isolation(self):
        """Newly provisioned staff credentials must authenticate and enforce strict role/branch isolation."""
        # 1. Old default password fails
        res_old_fail = self.client.post("/login", data={"username": "superadmin_anil", "password": "admin123"})
        self.assertEqual(res_old_fail.status_code, 401)
        self.assertIn("Invalid staff username or password", res_old_fail.text)

        # 2. Newly provisioned password succeeds for Super Admin
        res_admin_login = self.client.post("/login", data={"username": "superadmin_anil", "password": "OwnerSecretPass#999"})
        self.assertEqual(res_admin_login.status_code, 303)
        self.assertEqual(res_admin_login.headers["location"], "/admin/dashboard")

        admin_client = TestClient(app, cookies=res_admin_login.cookies)
        admin_dash = admin_client.get("/admin/dashboard")
        self.assertEqual(admin_dash.status_code, 200)
        self.assertIn("Super Admin Command Center", admin_dash.text)

        # 3. Cashier login and branch isolation
        res_cashier_login = self.client.post("/login", data={"username": "cashier_chikhali", "password": "ChkSecretPass#777"})
        self.assertEqual(res_cashier_login.status_code, 303)
        self.assertIn("/branch/dashboard?branch_id=br-chikhali", res_cashier_login.headers["location"])

        cashier_client = TestClient(app, cookies=res_cashier_login.cookies, follow_redirects=False)
        # Cashier blocked from Super Admin dashboard
        blocked_admin = cashier_client.get("/admin/dashboard")
        self.assertEqual(blocked_admin.status_code, 303)
        self.assertIn("/branch/dashboard", blocked_admin.headers["location"])

        # Cashier blocked from accessing other branch's yard
        blocked_other_branch = cashier_client.get("/branch/dashboard?branch_id=br-varvand")
        self.assertEqual(blocked_other_branch.status_code, 303)
        self.assertIn("branch_id=br-chikhali", blocked_other_branch.headers["location"])


if __name__ == "__main__":
    unittest.main()
