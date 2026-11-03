"""
Backend & Sync Verification Suite for Mandi ERP.
Tests:
1. Target date querying on Super Admin, Central Accounts, and Branch dashboards.
2. QC inspection submission via multipart Form data and JSON payload.
3. Pending ticket retrieval with automated Supabase cloud sync pull.
"""

import os
import sys
import unittest
from datetime import date
from fastapi.testclient import TestClient

# Ensure commoditi software is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from tests.test_support import setup_test_database
setup_test_database()

from server import app, create_session_token


class TestBackendSyncArchitecture(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_dashboard_target_date_querying(self):
        """Test target_date querying across all three dashboard tiers."""
        target_date = "2026-10-29"

        # 1. Super Admin Dashboard
        admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        self.client.cookies.set("mandi_session", admin_token)

        res_admin_today = self.client.get("/admin/dashboard")
        self.assertEqual(res_admin_today.status_code, 200)

        res_admin_date = self.client.get(f"/admin/dashboard?target_date={target_date}")
        self.assertEqual(res_admin_date.status_code, 200)
        self.assertIn(target_date, res_admin_date.text)

        # 2. Central Accounts Dashboard
        acc_token = create_session_token("accountant", "ACCOUNTANT_HQ", user_id="u-accountant")
        self.client.cookies.set("mandi_session", acc_token)

        res_acc_today = self.client.get("/accounts/dashboard")
        self.assertEqual(res_acc_today.status_code, 200)

        res_acc_date = self.client.get(f"/accounts/dashboard?target_date={target_date}")
        self.assertEqual(res_acc_date.status_code, 200)

        # 3. Branch Operations Dashboard
        cashier_token = create_session_token("chikhali", "BRANCH_CASHIER", branch_id="br-chikhali", user_id="u-indore-cashier")
        self.client.cookies.set("mandi_session", cashier_token)

        res_br_today = self.client.get("/branch/dashboard?branch_id=br-chikhali")
        self.assertEqual(res_br_today.status_code, 200)

        res_br_date = self.client.get(f"/branch/dashboard?branch_id=br-chikhali&target_date={target_date}")
        self.assertEqual(res_br_date.status_code, 200)

    def test_02_submit_qc_ticket_form_and_json(self):
        """Test submitting QC inspection tickets via both Form data and JSON payload."""
        qc_token = create_session_token("qc_chikhali", "QUALITY_INSPECTOR", branch_id="br-chikhali", user_id="u-qc-chikhali")
        self.client.cookies.set("mandi_session", qc_token)

        # 1. Multipart Form submission
        form_payload = {
            "branch_id": "br-chikhali",
            "farmer_name": "Kailash Patil (Form)",
            "farmer_phone": "9827011111",
            "vehicle_no": "MH-28-FM-7701",
            "commodity_name": "Soyabean (Yellow)",
            "moisture_pct": "11.2",
            "karda_pct": "0.9",
            "damaged_pct": "0.6"
        }
        res_form = self.client.post("/api/inspector/submit-qc", data=form_payload)
        self.assertEqual(res_form.status_code, 200)
        form_data = res_form.json()
        self.assertTrue(form_data.get("success"))
        form_ticket_no = form_data["ticket"]["ticket_no"]
        self.assertTrue(form_ticket_no.startswith("QC-"))

        # 2. JSON submission
        json_payload = {
            "branch_id": "br-chikhali",
            "farmer_name": "Santosh Deshmukh (JSON)",
            "farmer_phone": "9827022222",
            "vehicle_no": "MH-28-JS-8802",
            "commodity_name": "Soyabean (Yellow)",
            "moisture_pct": 10.5,
            "karda_pct": 0.7,
            "damaged_pct": 0.3,
            "breed_status": "PURE_BREED (Pure Lot)",
            "faq_grade": "FAQ_GRADE_1"
        }
        res_json = self.client.post("/api/inspector/submit-qc", json=json_payload)
        self.assertEqual(res_json.status_code, 200)
        json_data = res_json.json()
        self.assertTrue(json_data.get("success"))
        json_ticket_no = json_data["ticket"]["ticket_no"]
        self.assertTrue(json_ticket_no.startswith("QC-"))

        # 3. Retrieve Pending Tickets via /api/inspector/tickets/pending
        cashier_token = create_session_token("chikhali", "BRANCH_CASHIER", branch_id="br-chikhali", user_id="u-indore-cashier")
        self.client.cookies.set("mandi_session", cashier_token)

        res_pending = self.client.get("/api/inspector/tickets/pending?branch_id=br-chikhali")
        self.assertEqual(res_pending.status_code, 200)
        pending_result = res_pending.json()
        self.assertTrue(pending_result.get("success"))
        ticket_numbers = [t["ticket_no"] for t in pending_result.get("tickets", [])]

        self.assertIn(form_ticket_no, ticket_numbers)
        self.assertIn(json_ticket_no, ticket_numbers)


if __name__ == "__main__":
    unittest.main()
