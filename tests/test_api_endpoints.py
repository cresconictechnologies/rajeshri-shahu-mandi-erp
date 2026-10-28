"""
Integration tests for API endpoints, three-tier portals, invoice creation,
rate override workflow, and cashier denomination payouts.
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app
from database import get_connection

class TestMandiAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_hub_endpoint(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Mandi & Commodity Procurement ERP", res.text)
        self.assertIn("Port 8080", res.text)

    def test_admin_dashboard_endpoint(self):
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Super Admin Command Center", res.text)
        self.assertIn("Configured Branches", res.text)

    def test_accounts_dashboard_endpoint(self):
        res = self.client.get("/accounts/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Central Accounts & Rate Authority Desk", res.text)
        self.assertIn("Published Daily Mandi Rates", res.text)

    def test_branch_dashboard_endpoint(self):
        res = self.client.get("/branch/dashboard?branch_id=br-chikhali")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Chikhali Branch", res.text)
        self.assertIn("Simplified Inward Purchase Entry", res.text)

    def test_api_calculate(self):
        res = self.client.post("/api/invoices/calculate", params={
            "gross_weight_kg": 5000,
            "vehicle_tare_kg": 2000,
            "bag_count": 60,
            "rate_per_quintal": 4650,
            "moisture_percentage": 10.0,
            "karda_percentage": 0.0,
            "bag_type": "HDPE_50KG"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["vehicle_net_kg"], 3000.0)
        self.assertEqual(data["bag_tare_kg"], 30.0)
        self.assertEqual(data["net_weight_kg"], 2970.0)
        self.assertEqual(data["net_quintals"], 29.7)

    def test_farmer_registration_and_invoice_workflow(self):
        # 1. Register a new farmer
        res_farmer = self.client.post("/api/branch/farmers/register", data={
            "name": "Devendra Patidar",
            "phone": "9826099999",
            "village": "Village Hatod",
            "khasra_record_no": "Khasra No. 312/1",
            "home_branch_id": "br-chikhali"
        })
        self.assertEqual(res_farmer.status_code, 200)
        f_data = res_farmer.json()
        self.assertTrue(f_data["success"])
        farmer_id = f_data["id"]

        # 2. Create Inward Invoice within corridor (Soyabean @ 4650)
        res_inv = self.client.post("/api/branch/invoices/create", data={
            "branch_id": "br-chikhali",
            "party_id": farmer_id,
            "inspector_name": "Mahesh Patidar",
            "commodity_name": "Soyabean (Yellow)",
            "external_kanta_name": "Shree Ram Dharamkanta",
            "external_slip_number": "K-7711",
            "bag_type": "HDPE_50KG",
            "gross_weight_kg": 4000,
            "vehicle_tare_kg": 1500,
            "bag_count": 50,
            "moisture_percentage": 10.0,
            "karda_percentage": 0.0,
            "rate_per_quintal": 4650,
            "advance_to_deduct": 0
        })
        self.assertEqual(res_inv.status_code, 200)
        inv_data = res_inv.json()
        self.assertTrue(inv_data["success"])
        token = inv_data["token_number"]
        invoice_id = inv_data["invoice_id"]
        self.assertEqual(inv_data["rate_override_status"], "NONE")

        # 3. Check parchi slip renders
        res_parchi = self.client.get(f"/api/branch/invoices/parchi/{token}")
        self.assertEqual(res_parchi.status_code, 200)
        self.assertIn(token, res_parchi.text)
        self.assertIn("Devendra Patidar", res_parchi.text)

        # 4. Cashier Payout with Cash Round-up & Note Denominations
        # Net weight: 4000 - 1500 = 2500 - (50*0.5=25) = 2475 kg = 24.75 Qtl
        # Gross amount: 24.75 * 4650 = 115,087.50
        # Hamali: 50*5=250, Tulai: 50*2=100, Silai: 50*1=50, Cess 1.5%: 1726.31
        # Net payable ~ 112,961.19 -> Rounded cash payout = 112,962.00
        net_payable = inv_data["net_payable_amount"]
        import math
        rounded_payout = math.ceil(net_payable)

        # First, test mismatch: note counts don't equal rounded_payout
        res_mismatch = self.client.post("/api/cashier/payout", data={
            "invoice_id": invoice_id,
            "branch_id": "br-chikhali",
            "payout_mode": "CASH",
            "notes_500": 10  # 5000 != rounded_payout
        })
        self.assertEqual(res_mismatch.status_code, 200)
        self.assertFalse(res_mismatch.json()["success"])
        self.assertEqual(res_mismatch.json()["reason"], "DENOMINATION_MISMATCH")

        # Now, calculate exact note breakdown
        rem = rounded_payout
        n500 = rem // 500
        rem = rem % 500
        n200 = rem // 200
        rem = rem % 200
        n100 = rem // 100
        rem = rem % 100
        n50 = rem // 50
        rem = rem % 50
        n20 = rem // 20
        rem = rem % 20
        n10 = rem // 10
        rem = rem % 10
        coins = rem

        res_payout = self.client.post("/api/cashier/payout", data={
            "invoice_id": invoice_id,
            "branch_id": "br-chikhali",
            "payout_mode": "CASH",
            "notes_500": n500,
            "notes_200": n200,
            "notes_100": n100,
            "notes_50": n50,
            "notes_20": n20,
            "notes_10": n10,
            "coins": coins
        })
        self.assertEqual(res_payout.status_code, 200)
        payout_data = res_payout.json()
        self.assertTrue(payout_data["success"])
        self.assertEqual(payout_data["amount_paid"], rounded_payout)

    def test_rate_override_workflow(self):
        # Create an out-of-corridor invoice (rate = 5200, when max is 4800)
        res_inv = self.client.post("/api/branch/invoices/create", data={
            "branch_id": "br-chikhali",
            "party_id": "p-farmer-1",
            "inspector_name": "Mahesh Patidar",
            "commodity_name": "Soyabean (Yellow)",
            "external_kanta_name": "Shree Ram Dharamkanta",
            "external_slip_number": "K-8822",
            "bag_type": "HDPE_50KG",
            "gross_weight_kg": 3000,
            "vehicle_tare_kg": 1000,
            "bag_count": 40,
            "rate_per_quintal": 5200,  # Exceeds max 4800!
            "rate_override_reason": "High protein variety certified by Mandi Assayer"
        })
        self.assertEqual(res_inv.status_code, 200)
        inv_data = res_inv.json()
        self.assertTrue(inv_data["success"])
        self.assertEqual(inv_data["rate_override_status"], "PENDING")
        inv_id = inv_data["invoice_id"]

        # Attempt payout while override is PENDING -> Must be BLOCKED
        res_pay_blocked = self.client.post("/api/cashier/payout", data={
            "invoice_id": inv_id,
            "branch_id": "br-chikhali",
            "payout_mode": "BANK_TRANSFER",
            "bank_utr_no": "UTR998877"
        })
        self.assertEqual(res_pay_blocked.status_code, 200)
        self.assertFalse(res_pay_blocked.json()["success"])
        self.assertEqual(res_pay_blocked.json()["reason"], "RATE_OVERRIDE_PENDING")

        # Central Accounts approves the override
        res_approve = self.client.post("/api/accounts/rate-overrides/action", data={
            "invoice_id": inv_id,
            "decision": "APPROVE",
            "accountant_reason": "Approved: Premium certified lot for export dispatch."
        }, follow_redirects=False)
        self.assertEqual(res_approve.status_code, 303)

        # Now payout succeeds!
        res_pay_ok = self.client.post("/api/cashier/payout", data={
            "invoice_id": inv_id,
            "branch_id": "br-chikhali",
            "payout_mode": "BANK_TRANSFER",
            "bank_utr_no": "UTR9988776655"
        })
        self.assertEqual(res_pay_ok.status_code, 200)
        self.assertTrue(res_pay_ok.json()["success"])

    def test_manual_yard_scale_invoice_workflow(self):
        """Test simplified Manual Yard Scale entry without external weighbridge tare."""
        res_inv = self.client.post("/api/branch/invoices/create", data={
            "branch_id": "br-chikhali",
            "party_id": "p-farmer-1",
            "inspector_name": "Mahesh Patidar",
            "commodity_name": "Wheat (Lokwan)",
            "weighment_mode": "MANUAL_YARD",
            "yard_weight_kg": 3500,
            "moisture_percentage": 10.0,
            "rate_per_quintal": 2750
        })
        self.assertEqual(res_inv.status_code, 200)
        data = res_inv.json()
        self.assertTrue(data["success"])
        token = data["token_number"]

        # Check slip displays Yard Scale
        res_slip = self.client.get(f"/api/branch/invoices/parchi/{token}")
        self.assertEqual(res_slip.status_code, 200)
        self.assertIn("Yard Scale", res_slip.text)
        self.assertIn("3500", res_slip.text)

    def test_rtgs_transfer_request_and_central_utr_closure(self):
        """Test full RTGS bank transfer workflow: Cashier requests, Accountant enters UTR to close."""
        # 1. Create high-value invoice (> ₹2,00,000 for Section 269ST mandate)
        res_inv = self.client.post("/api/branch/invoices/create", data={
            "branch_id": "br-chikhali",
            "party_id": "p-farmer-1",
            "inspector_name": "Mahesh Patidar",
            "commodity_name": "Soyabean (Yellow)",
            "weighment_mode": "WEIGHBRIDGE",
            "external_kanta_name": "Dewas Naka Dharamkanta",
            "external_slip_number": "SLIP-9901",
            "gross_weight_kg": 8500,
            "vehicle_tare_kg": 2500,
            "moisture_percentage": 10.0,
            "rate_per_quintal": 4650
        })
        self.assertEqual(res_inv.status_code, 200)
        inv_data = res_inv.json()
        self.assertTrue(inv_data["success"])
        inv_id = inv_data["invoice_id"]
        token = inv_data["token_number"]
        self.assertGreater(inv_data["net_payable_amount"], 200000)

        # 2. Cashier submits RTGS Request to Central Accounts
        res_rtgs_req = self.client.post("/api/cashier/request-rtgs", data={
            "invoice_id": inv_id,
            "branch_id": "br-chikhali",
            "beneficiary_name": "Rameshwar Patel",
            "bank_name": "State Bank of India",
            "account_no": "30987654321",
            "ifsc_code": "SBIN0001234"
        })
        self.assertEqual(res_rtgs_req.status_code, 200)
        req_data = res_rtgs_req.json()
        self.assertTrue(req_data["success"])
        self.assertIn("forwarded to Central HQ Accounts", req_data["message"])

        # 3. Cashier direct cash payout must now be blocked because status is RTGS_PENDING
        res_block = self.client.post("/api/cashier/payout", data={
            "invoice_id": inv_id,
            "branch_id": "br-chikhali",
            "payout_mode": "CASH"
        })
        self.assertEqual(res_block.status_code, 200)
        self.assertFalse(res_block.json()["success"])
        self.assertEqual(res_block.json()["reason"], "RTGS_PENDING")

        # 4. Central Accounts attempts to close without UTR -> Must fail (400)
        res_empty_utr = self.client.post("/api/accounts/rtgs/process", data={
            "invoice_id": inv_id,
            "bank_utr_no": "   "
        })
        self.assertEqual(res_empty_utr.status_code, 400)

        # 5. Central Accounts enters valid UTR -> Request closes and invoice marked PAID
        res_settle = self.client.post("/api/accounts/rtgs/process", data={
            "invoice_id": inv_id,
            "bank_utr_no": "SBINR52026102800998811"
        }, follow_redirects=False)
        self.assertEqual(res_settle.status_code, 303)

        # 6. Verify slip now reflects UTR settlement
        res_slip = self.client.get(f"/api/branch/invoices/parchi/{token}")
        self.assertEqual(res_slip.status_code, 200)
        self.assertIn("SBINR52026102800998811", res_slip.text)
        self.assertIn("Settled via RTGS Bank Transfer", res_slip.text)

    def test_super_admin_commodity_cards_and_pnl_visibility(self):
        """Test Super Admin cards show active stock, avg buying price, and total P&L."""
        res_admin = self.client.get("/admin/dashboard")
        self.assertEqual(res_admin.status_code, 200)
        html = res_admin.text
        self.assertIn("Total Estimated Profit / Loss", html)
        self.assertIn("Live Commodity Stock & Branch Inventory Allocation", html)
        self.assertIn("Avg Buying Price", html)
        self.assertIn("Branch Quantity Breakdown:", html)

if __name__ == "__main__":
    unittest.main()
