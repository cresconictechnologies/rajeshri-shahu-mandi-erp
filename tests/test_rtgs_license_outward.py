"""
Automated Integration Tests for:
1. Branch RTGS Payout Status Tracker (viewing pending & completed with UTR)
2. Central Accountant Outward Payment Settlement Desk (RTGS with UTR or Cash with Branch)
3. Super Admin Commercial License Box (Pro Tier 3 Branches, Valid Until 31-March-2027)
4. Staff & Branch Logins Management (Single Cashier & Munim per branch, credential updates)
"""

import unittest
from fastapi.testclient import TestClient
import sqlite3
import os
import hashlib
from server import app
from database import DB_PATH, get_connection

class TestRtgsLicenseOutward(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_branch_dashboard_has_rtgs_tracker_tab_and_data(self):
        """Branch dashboard must feature the RTGS status tracker tab and show live UTRs."""
        res = self.client.get("/branch/dashboard?branch_id=br-chikhali")
        self.assertEqual(res.status_code, 200)
        content = res.text
        self.assertIn("tab-rtgs-tracker", content)
        self.assertIn("RTGS Payout Status", content)
        self.assertIn("branchRtgsTable", content)

    def test_02_accountant_outward_receivables_and_payment_rtgs(self):
        """Accountant can view outward receivables and receive payment via RTGS with UTR."""
        # 1. Fetch accounts dashboard and verify tab exists
        res = self.client.get("/accounts/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn("tab-outward-receivables", res.text)
        self.assertIn("Record Outward Payment Receipt", res.text)

        # 2. Pick a pending outward order from database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, challan_number, buyer_name, total_bill_amount FROM outward_orders WHERE payment_status='PENDING' LIMIT 1")
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row, "At least one outward order must exist for testing")
        challan_id = row["id"]
        challan_no = row["challan_number"]

        # 3. Post payment receipt via RTGS
        test_utr = "TESTUTR20261028X"
        res_post = self.client.post("/api/accounts/outward/receive-payment", data={
            "challan_id": challan_id,
            "payment_mode": "RTGS",
            "utr_number": test_utr,
            "receipt_date": "2026-10-28",
            "payment_notes": "RTGS settlement verified from bank statement"
        }, follow_redirects=False)
        self.assertEqual(res_post.status_code, 303)

        # 4. Verify in database that outward order is marked RECEIVED with UTR
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT payment_status, payment_mode, utr_number FROM outward_orders WHERE id=?", (challan_id,))
        updated = cur.fetchone()
        self.assertEqual(updated["payment_status"], "RECEIVED")
        self.assertEqual(updated["payment_mode"], "RTGS")
        self.assertEqual(updated["utr_number"], test_utr)

        # 5. Verify ledger entry was created
        cur.execute("SELECT account_name, debit_amount FROM ledger_entries WHERE voucher_id=? AND voucher_type='OUTWARD_RECEIPT'", (challan_no,))
        led = cur.fetchone()
        self.assertIsNotNone(led)
        self.assertEqual(led["account_name"], "Mandi Central Bank Account")
        self.assertEqual(led["debit_amount"], row["total_bill_amount"])
        conn.close()

    def test_03_accountant_outward_payment_cash_at_branch(self):
        """Accountant can receive outward payment in Cash, crediting the branch drawer."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, challan_number, buyer_name, total_bill_amount FROM outward_orders WHERE payment_status='PENDING' LIMIT 1")
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        challan_id = row["id"]
        challan_no = row["challan_number"]

        # Post cash receipt at Varvand branch
        res_post = self.client.post("/api/accounts/outward/receive-payment", data={
            "challan_id": challan_id,
            "payment_mode": "CASH",
            "payment_branch_id": "br-varvand",
            "receipt_date": "2026-10-28",
            "payment_notes": "Cash collected in hand at Varvand yard"
        }, follow_redirects=False)
        self.assertEqual(res_post.status_code, 303)

        # Verify in database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT payment_status, payment_mode, payment_branch_id FROM outward_orders WHERE id=?", (challan_id,))
        updated = cur.fetchone()
        self.assertEqual(updated["payment_status"], "RECEIVED")
        self.assertEqual(updated["payment_mode"], "CASH")
        self.assertEqual(updated["payment_branch_id"], "br-varvand")

        # Verify ledger has Branch Cash Drawer
        cur.execute("SELECT account_name, debit_amount FROM ledger_entries WHERE voucher_id=? AND voucher_type='OUTWARD_RECEIPT'", (challan_no,))
        led = cur.fetchone()
        self.assertIsNotNone(led)
        self.assertIn("Branch Cash Drawer", led["account_name"])
        conn.close()

    def test_04_super_admin_license_box_and_staff_management(self):
        """Super Admin settings displays the License Box and Staff Credential editor."""
        res = self.client.get("/admin/settings")
        self.assertEqual(res.status_code, 200)
        content = res.text

        # Verify License Key Box requirements
        self.assertIn("Active (Pro Tier - 3 Branches)", content)
        self.assertIn("31-March-2027", content)
        self.assertIn("Software License & Subscription", content)

        # Verify Staff Management Table exists
        self.assertIn("Branch Logins & Staff Credential Management", content)
        self.assertIn("chikhali_cashier", content)
        self.assertIn("varvand_cashier", content)
        self.assertIn("dhad_cashier", content)
        self.assertIn("accountant", content)

    def test_05_admin_updates_staff_credentials_and_password(self):
        """Super Admin can update cashier name, phone, and reset password with audit logging."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM users WHERE username='chikhali_cashier'")
        cashier = cur.fetchone()
        conn.close()
        self.assertIsNotNone(cashier)
        uid = cashier["id"]

        new_test_pass = "Chikhali@NewPass2026"
        res = self.client.post("/api/admin/users/update-credentials", data={
            "user_id": uid,
            "full_name": "Santosh V. Patil (Chikhali Lead)",
            "phone": "9826099999",
            "username": "chikhali_cashier",
            "new_password": new_test_pass
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 303)

        # Verify password hash updated in users
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT full_name, phone, password_hash FROM users WHERE id=?", (uid,))
        u = cur.fetchone()
        self.assertEqual(u["full_name"], "Santosh V. Patil (Chikhali Lead)")
        self.assertEqual(u["phone"], "9826099999")
        expected_hash = hashlib.sha256(new_test_pass.encode("utf-8")).hexdigest()
        self.assertEqual(u["password_hash"], expected_hash)

        # Verify audit log entry
        cur.execute("SELECT * FROM audit_change_logs WHERE entity_type='USER' AND entity_id=? ORDER BY created_at DESC LIMIT 1", (uid,))
        audit = cur.fetchone()
        self.assertIsNotNone(audit)
        self.assertEqual(audit["action"], "CREDENTIALS_UPDATE")
        conn.close()

if __name__ == "__main__":
    unittest.main()
