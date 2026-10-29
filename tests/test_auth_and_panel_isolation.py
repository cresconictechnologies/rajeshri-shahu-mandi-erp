"""
Automated Integration Tests for:
1. Owner Initial Setup & Commercial License Activation (/setup)
2. Staff Credential Generator (Central Accountant + 3 Branch Cashiers)
3. Terminal Single Sign-On (/login) and Role-Based Dispatch
4. Strict Panel Isolation & No Cross-Panel Navigation
5. Buldhana APMC Commodity Profile & Zero Quantity Auto-Hide
"""

import unittest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_support import setup_test_database
setup_test_database()

from fastapi.testclient import TestClient
from server import app, create_session_token
from database import get_connection

class TestAuthAndPanelIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app, follow_redirects=False)
        cls.following_client = TestClient(app, follow_redirects=True)

    def test_01_owner_setup_page_and_license_activation(self):
        """Owner setup page must display 3 steps: Profile, Commercial License, and Staff generator."""
        # Reset setup state for first-run simulation
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE system_settings SET setting_value='0' WHERE scope='SUPER_ADMIN' AND setting_key='is_setup_completed'")
            conn.commit()
        finally:
            conn.close()

        res = self.following_client.get("/setup")
        self.assertEqual(res.status_code, 200)
        content = res.text
        self.assertIn("Step 1: Business & Owner Profile", content)
        self.assertIn("Step 2: Commercial License Key Activation", content)
        self.assertIn("Step 3: Generate Staff Credentials", content)
        self.assertIn("Central HQ Accountant", content)
        self.assertIn("Chikhali Branch — Single Cashier", content)
        self.assertIn("Varvand Branch — Single Cashier", content)
        self.assertIn("Dhad Branch — Single Cashier", content)

        # POST /setup to activate license and generate credentials
        setup_res = self.following_client.post("/setup", data={
            "org_name": "Rajeshri Shahu Trading Co.",
            "owner_name": "Vikramaditya Singhal (Owner)",
            "owner_username": "admin",
            "owner_password": "adminpassword123",
            "owner_phone": "9826011111",
            "org_gstin": "23AACCK1234F1Z5",
            "license_key": "RST-PRO-2026-MH3B-89A12F",
            "license_valid_until": "31-March-2027",
            "acc_name": "Omprakash Agrawal (Chief Accountant)",
            "acc_username": "accountant",
            "acc_password": "accpassword123",
            "acc_phone": "9826022222",
            "chk_name": "Santosh V. Patil (Chikhali Lead)",
            "chk_username": "chikhali_cashier",
            "chk_password": "chkpassword123",
            "chk_phone": "9826033333",
            "vrv_name": "Mohanlal Soni (Varvand Cashier)",
            "vrv_username": "varvand_cashier",
            "vrv_password": "vrvpassword123",
            "vrv_phone": "9826044444",
            "dhd_name": "Kailash Tiwari (Dhad Cashier)",
            "dhd_username": "dhad_cashier",
            "dhd_password": "dhdpassword123",
            "dhd_phone": "9826055555"
        })
        self.assertEqual(setup_res.status_code, 200)
        self.assertIn("Commercial License activated and all staff credentials provisioned successfully", setup_res.text)
        self.assertIn("Handover & Physical Security Record", setup_res.text)
        self.assertIn("chkpassword123", setup_res.text)
        self.assertIn("Proceed to Staff & Owner Login", setup_res.text)

    def test_02_terminal_login_and_role_dispatch(self):
        """Login page validates staff credentials and dispatches by role with signed session cookie."""
        # 1. Invalid password rejection
        bad_res = self.client.post("/login", data={"username": "chikhali_cashier", "password": "wrongpassword"})
        self.assertEqual(bad_res.status_code, 401)
        self.assertIn("Invalid staff username or password", bad_res.text)

        # 2. Super Admin login -> /admin/dashboard
        admin_res = self.client.post("/login", data={"username": "admin", "password": "adminpassword123"})
        self.assertEqual(admin_res.status_code, 303)
        self.assertEqual(admin_res.headers["location"], "/admin/dashboard")
        self.assertIn("mandi_session", admin_res.headers.get("set-cookie", ""))

        # 3. Accountant login -> /accounts/dashboard
        acc_res = self.client.post("/login", data={"username": "accountant", "password": "accpassword123"})
        self.assertEqual(acc_res.status_code, 303)
        self.assertEqual(acc_res.headers["location"], "/accounts/dashboard")

        # 4. Branch Cashier login -> /branch/dashboard?branch_id=br-chikhali
        cashier_res = self.client.post("/login", data={"username": "chikhali_cashier", "password": "chkpassword123"})
        self.assertEqual(cashier_res.status_code, 303)
        self.assertEqual(cashier_res.headers["location"], "/branch/dashboard?branch_id=br-chikhali")

    def test_03_logout_clears_session(self):
        """Logout endpoint clears session cookie and redirects back to /login."""
        res = self.client.get("/logout")
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/login")
        cookie_header = res.headers.get("set-cookie", "")
        self.assertTrue("mandi_session=" in cookie_header or "Max-Age=0" in cookie_header or "expires=" in cookie_header.lower())

    def test_04_strict_panel_isolation(self):
        """Cross-panel navigation must be strictly blocked: Cashiers locked to own yard, Accountants locked to HQ."""
        # 1. Cashier attempting to enter Super Admin
        cashier_token = create_session_token("chikhali_cashier", "BRANCH_CASHIER", "br-chikhali")
        cashier_headers = {"Cookie": f"mandi_session={cashier_token}"}
        res_admin = self.client.get("/admin/dashboard", headers=cashier_headers)
        self.assertEqual(res_admin.status_code, 303)
        self.assertEqual(res_admin.headers["location"], "/branch/dashboard?branch_id=br-chikhali")

        # 2. Cashier attempting to enter Central Accounts
        res_accounts = self.client.get("/accounts/dashboard", headers=cashier_headers)
        self.assertEqual(res_accounts.status_code, 303)
        self.assertEqual(res_accounts.headers["location"], "/branch/dashboard?branch_id=br-chikhali")

        # 3. Cashier attempting to access another branch's yard
        res_other_branch = self.client.get("/branch/dashboard?branch_id=br-varvand", headers=cashier_headers)
        self.assertEqual(res_other_branch.status_code, 303)
        self.assertEqual(res_other_branch.headers["location"], "/branch/dashboard?branch_id=br-chikhali")

        # 4. Accountant attempting to access branch yard
        acc_token = create_session_token("accountant", "ACCOUNTANT_HQ", "")
        acc_headers = {"Cookie": f"mandi_session={acc_token}"}
        res_acc_branch = self.client.get("/branch/dashboard?branch_id=br-chikhali", headers=acc_headers)
        self.assertEqual(res_acc_branch.status_code, 303)
        self.assertEqual(res_acc_branch.headers["location"], "/accounts/dashboard")

    def test_05_zero_stock_auto_hide(self):
        """In yard stock view, commodities with 0 quantity must be automatically hidden."""
        token = create_session_token("chikhali_cashier", "BRANCH_CASHIER", branch_id="br-chikhali")
        self.following_client.cookies.set("mandi_session", token)
        res = self.following_client.get("/branch/stock?branch_id=br-chikhali")
        self.assertEqual(res.status_code, 200)
        content = res.text
        # Commodities with positive stock in DB must be present
        self.assertIn("Soyabean (Yellow)", content)
        self.assertIn("In Yard Stock", content)
        # Commodities with 0 stock must not show as in-stock rows in the active table
        self.assertNotIn("Nil Stock", content)

    def test_06_buldhana_apmc_commodities_registered(self):
        """Buldhana APMC major commodities (Soyabean, Cotton, Tur, Harbhara) must be active."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM commodities WHERE is_active=1")
            names = [r["name"] for r in cur.fetchall()]
            # Verify major Buldhana crops
            has_soya = any("Soyabean" in n for n in names)
            has_cotton = any("Cotton" in n or "Kapas" in n for n in names)
            has_tur = any("Tur" in n or "Arhar" in n for n in names)
            has_chana = any("Chana" in n or "Harbhara" in n for n in names)
            self.assertTrue(has_soya, "Soyabean must be active for Buldhana")
            self.assertTrue(has_cotton, "Cotton / Kapas must be active for Buldhana APMC")
            self.assertTrue(has_tur, "Tur / Arhar must be active for Buldhana APMC")
            self.assertTrue(has_chana, "Chana / Harbhara must be active for Buldhana APMC")
        finally:
            conn.close()

    def test_07_super_admin_settings_staff_credentials_and_password_assignment(self):
        """Super Admin settings must render Step 3 staff credential cards and allow batch password assignment with panel isolation."""
        # 1. Super Admin views settings
        admin_token = create_session_token("admin", "SUPER_ADMIN", "")
        admin_headers = {"Cookie": f"mandi_session={admin_token}"}
        res = self.client.get("/admin/settings", headers=admin_headers)
        self.assertEqual(res.status_code, 200)
        content = res.text
        self.assertIn("Step 3: Generate Staff Credentials (Accountant & Branch Cashiers)", content)
        self.assertIn("Central HQ Accountant", content)
        self.assertIn("Chikhali Branch — Single Cashier & Munim", content)
        self.assertIn("Varvand Branch — Single Cashier & Munim", content)
        self.assertIn("Dhad Branch — Single Cashier & Munim", content)
        self.assertIn("Save Staff Credentials & Enforce Panel Passwords", content)

        # 2. Super Admin updates all staff credentials and assigns new passwords
        update_res = self.client.post("/api/admin/staff/update-all", headers=admin_headers, data={
            "acc_name": "Omprakash Agrawal (Chief Accountant)",
            "acc_username": "accountant",
            "acc_phone": "9826022222",
            "acc_password": "acc123",
            "chk_name": "Santosh V. Patil (Chikhali Lead)",
            "chk_username": "chikhali_cashier",
            "chk_phone": "9826099999",
            "chk_password": "chk123",
            "vrv_name": "Mohanlal Soni (Varvand Cashier)",
            "vrv_username": "varvand_cashier",
            "vrv_phone": "9826044444",
            "vrv_password": "vrv123",
            "dhd_name": "Kailash Tiwari (Dhad Cashier)",
            "dhd_username": "dhad_cashier",
            "dhd_phone": "9826055555",
            "dhd_password": "dhd123"
        })
        self.assertEqual(update_res.status_code, 303)
        self.assertIn("/admin/settings", update_res.headers["location"])

        # 3. Verify Accountant logs in with new password 'acc123' and routes to /accounts/dashboard
        acc_login = self.client.post("/login", data={"username": "accountant", "password": "acc123"})
        self.assertEqual(acc_login.status_code, 303)
        self.assertEqual(acc_login.headers["location"], "/accounts/dashboard")

        # 4. Verify Chikhali Cashier logs in with 'chk123' and routes to /branch/dashboard?branch_id=br-chikhali
        chk_login = self.client.post("/login", data={"username": "chikhali_cashier", "password": "chk123"})
        self.assertEqual(chk_login.status_code, 303)
        self.assertEqual(chk_login.headers["location"], "/branch/dashboard?branch_id=br-chikhali")

        # 5. Verify Varvand Cashier logs in with 'vrv123' and routes to /branch/dashboard?branch_id=br-varvand
        vrv_login = self.client.post("/login", data={"username": "varvand_cashier", "password": "vrv123"})
        self.assertEqual(vrv_login.status_code, 303)
        self.assertEqual(vrv_login.headers["location"], "/branch/dashboard?branch_id=br-varvand")

        # 6. Verify Dhad Cashier logs in with 'dhd123' and routes to /branch/dashboard?branch_id=br-dhad
        dhd_login = self.client.post("/login", data={"username": "dhad_cashier", "password": "dhd123"})
        self.assertEqual(dhd_login.status_code, 303)
        self.assertEqual(dhd_login.headers["location"], "/branch/dashboard?branch_id=br-dhad")

if __name__ == "__main__":
    unittest.main()
