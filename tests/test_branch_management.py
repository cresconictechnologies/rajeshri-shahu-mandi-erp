import os
import sys
import unittest
from fastapi.testclient import TestClient

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from server import app, create_session_token
from database import get_connection, hash_password
import supabase_sync

class TestBranchAdminOperations(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        self.client.cookies.set("mandi_session", self.admin_token)

    def tearDown(self):
        # Guarantee Sarola Maruti is active
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE branches SET is_active=1 WHERE id='br-sarola'")
        cur.execute("UPDATE branches SET is_active=1 WHERE id='br-chikhali'")
        cur.execute("UPDATE branches SET is_active=1 WHERE id='br-varvand'")
        conn.commit()
        conn.close()

    def test_01_sarola_login_and_dashboard_access(self):
        """Verify Sarola Maruti Cashier logs in with srl123 and routes to Sarola branch dashboard."""
        login_res = self.client.post("/login", data={"username": "sarola", "password": "srl123"}, follow_redirects=False)
        self.assertEqual(login_res.status_code, 303)
        self.assertEqual(login_res.headers["location"], "/branch/dashboard?branch_id=br-sarola")

        # Also verify sarola_cashier
        sc_res = self.client.post("/login", data={"username": "sarola_cashier", "password": "srl123"}, follow_redirects=False)
        self.assertEqual(sc_res.status_code, 303)
        self.assertEqual(sc_res.headers["location"], "/branch/dashboard?branch_id=br-sarola")

    def test_02_three_official_branches_established(self):
        """Verify Chikhali, Varvand, and Sarola Maruti are active in SQLite."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, branch_code, name, is_active FROM branches WHERE is_active=1 ORDER BY branch_code ASC")
        active_branches = {r["id"]: dict(r) for r in cur.fetchall()}
        conn.close()

        self.assertIn("br-chikhali", active_branches)
        self.assertIn("br-varvand", active_branches)
        self.assertIn("br-sarola", active_branches)
        self.assertEqual(len(active_branches), 3)

    def test_03_create_toggle_and_delete_branch_json(self):
        """Test creating, toggling, and deleting a branch via Superadmin JSON API with zero 500 errors."""
        test_code = "BR-TMP"
        test_id = "br-br-tmp"

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM branches WHERE id=?", (test_id,))
        cur.execute("DELETE FROM users WHERE branch_id=?", (test_id,))
        # Temporarily deactivate Sarola so license limit permits creation
        cur.execute("UPDATE branches SET is_active=0 WHERE id='br-sarola'")
        conn.commit()
        conn.close()

        try:
            # 1. Add branch via JSON
            create_res = self.client.post(
                "/api/admin/branches/create",
                json={
                    "branch_code": test_code,
                    "name": "Temporary Test Yard",
                    "address": "MIDC Area",
                    "phone": "9826088888"
                },
                headers={"Accept": "application/json"}
            )
            self.assertEqual(create_res.status_code, 200, f"Expected 200, got: {create_res.text}")
            created_json = create_res.json()
            self.assertTrue(created_json.get("success"))
            created_bid = created_json.get("branch_id")

            # 2. Toggle branch status (Active -> Deactivated)
            toggle_res = self.client.post(
                "/api/admin/branches/toggle",
                json={"branch_id": created_bid},
                headers={"Accept": "application/json"}
            )
            self.assertEqual(toggle_res.status_code, 200, f"Expected 200, got: {toggle_res.text}")
            self.assertEqual(toggle_res.json().get("is_active"), 0)

            # 3. Insert child references to test FK cascade
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO daily_commodity_rates (id, rate_date, branch_id, commodity_name, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl) VALUES ('r-tmp-1', '2026-11-04', ?, 'Soyabean', 4000, 4200, 4400)", (created_bid,))
            cur.execute("INSERT OR REPLACE INTO branch_daily_cash_drawers (id, branch_id, record_date, opening_float, calculated_closing_cash, physical_counted_cash) VALUES ('dr-tmp-1', ?, '2026-11-04', 5000, 5000, 5000)", (created_bid,))
            cur.execute("INSERT OR REPLACE INTO inspectors (id, branch_id, name, designation, phone) VALUES ('ins-tmp-1', ?, 'Temp Assayer', 'Assayer', '9999999999')", (created_bid,))
            conn.commit()
            conn.close()

            # 4. Delete branch via JSON
            del_res = self.client.post(
                "/api/admin/branches/delete",
                json={"branch_id": created_bid},
                headers={"Accept": "application/json"}
            )
            self.assertEqual(del_res.status_code, 200, f"Expected 200, got: {del_res.text}")
            del_json = del_res.json()
            self.assertTrue(del_json.get("success"))

            # Verify it was completely removed from SQLite
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id FROM branches WHERE id=?", (created_bid,))
            self.assertIsNone(cur.fetchone())
            conn.close()

        finally:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE branches SET is_active=1 WHERE id='br-sarola'")
            cur.execute("DELETE FROM branches WHERE id=?", (test_id,))
            conn.commit()
            conn.close()

    def test_04_delete_branch_form_post_with_redirect(self):
        """Test creating and deleting a branch via HTML Form POST with 303 Redirect and zero 500 errors."""
        test_code = "BR-FORM"
        test_id = "br-br-form"

        # Temporarily deactivate Sarola for limit
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE branches SET is_active=0 WHERE id='br-sarola'")
        cur.execute("DELETE FROM branches WHERE id=?", (test_id,))
        cur.execute("DELETE FROM users WHERE branch_id=?", (test_id,))
        conn.commit()
        conn.close()

        try:
            # 1. Create via Form
            create_res = self.client.post(
                "/api/admin/branches/create",
                data={
                    "branch_code": test_code,
                    "name": "Form Test Yard",
                    "address": "Bazaar Yard",
                    "phone": "9826077777"
                },
                follow_redirects=False
            )
            self.assertEqual(create_res.status_code, 303)
            self.assertIn("/admin/settings", create_res.headers["location"])

            # 2. Delete via Form
            del_res = self.client.post(
                "/api/admin/branches/delete",
                data={"branch_id": test_id},
                follow_redirects=False
            )
            self.assertEqual(del_res.status_code, 303)
            self.assertIn("deleted+successfully", del_res.headers["location"])
        finally:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE branches SET is_active=1 WHERE id='br-sarola'")
            cur.execute("DELETE FROM branches WHERE id=?", (test_id,))
            conn.commit()
            conn.close()

    def test_05_delete_branch_with_invoices_fails_gracefully_and_deactivates(self):
        """Test deleting branch with active invoices returns clean 400 error and deactivates branch."""
        # Chikhali has 1 invoice
        del_res = self.client.post(
            "/api/admin/branches/delete",
            json={"branch_id": "br-chikhali"},
            headers={"Accept": "application/json"}
        )
        self.assertEqual(del_res.status_code, 400, f"Expected 400, got: {del_res.text}")
        res_json = del_res.json()
        self.assertFalse(res_json.get("success"))
        self.assertEqual(res_json.get("action"), "deactivated")
        self.assertIn("cannot delete branch", res_json.get("error", "").lower())
        self.assertIn("deactivated instead", res_json.get("error", "").lower())

        # Restore Chikhali to active for ongoing operations
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE branches SET is_active=1 WHERE id='br-chikhali'")
        conn.commit()
        conn.close()

if __name__ == "__main__":
    unittest.main()
