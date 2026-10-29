"""
Comprehensive automated tests for newly requested features:
1. Branch Physical Stock & Valuation Page (/branch/stock)
2. Settings Panels for all 3 tiers (Super Admin, Central Accounts, Branch)
3. Farmer Editing at any time with immutable database change logs (audit_change_logs)
4. Clickable Commodity Cards in Super Admin with Branch-specific Quantity and Rates breakdown
5. Outward Dispatch & Sales Entry with Cashier-typed Hamali input box
6. Merged Inward Entry & Cashier Desk in one unified workflow (Hamali ₹25/100kg, 0 Cess)
"""

import os
import sys
import json
import unittest
from fastapi.testclient import TestClient

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_support import setup_test_database
setup_test_database()

from server import app, create_session_token
from database import get_connection

class TestNewMandiFeatures(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        cls.client.cookies.set("mandi_session", token)

    def test_branch_stock_page(self):
        """Verify that branches can view their physical stock, quantities, and avg prices."""
        res = self.client.get("/branch/stock?branch_id=br-chikhali")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Mandi Yard Physical Stock & Valuation", res.text)
        self.assertIn("Total Physical Stock In Hand", res.text)
        self.assertIn("Yard Average Buying Price", res.text)
        self.assertIn("Total Inventory Valuation", res.text)
        self.assertIn("Branch Inventory Ledger Summary", res.text)

    def test_super_admin_settings(self):
        """Verify Super Admin settings page and update API."""
        get_res = self.client.get("/admin/settings")
        self.assertEqual(get_res.status_code, 200)
        self.assertIn("Super Admin Enterprise Configuration", get_res.text)
        self.assertIn("Corporate Enterprise Name", get_res.text)

        post_res = self.client.post("/api/admin/settings", data={
            "org_name": "Rajeshri Shahu Trading",
            "org_pan": "AACCK1234F",
            "org_gstin": "23AACCK1234F1Z5",
            "fiscal_year": "2026-2027",
            "multi_branch_sync": "ENABLED",
            "audit_retention_days": "365"
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)
        self.assertIn("Rajeshri Shahu Trading", post_res.text)

    def test_central_accounts_settings(self):
        """Verify Central Accounts settings page and update API."""
        get_res = self.client.get("/accounts/settings")
        self.assertEqual(get_res.status_code, 200)
        self.assertIn("Central Accounts Financial Governance", get_res.text)
        self.assertIn("Section 269ST Statutory Cash Ceiling", get_res.text)

        post_res = self.client.post("/api/accounts/settings", data={
            "sec_269st_cash_limit": "199999",
            "sec_40a3_cash_limit": "10000",
            "corridor_tolerance_pct": "6.5",
            "rtgs_auto_sms": "ENABLED",
            "default_bank_account": "State Bank of India (A/C: 40992388112)"
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)
        self.assertIn("6.5", post_res.text)

    def test_branch_settings(self):
        """Verify Branch settings page and update API."""
        get_res = self.client.get("/branch/settings?branch_id=br-chikhali")
        self.assertEqual(get_res.status_code, 200)
        self.assertIn("Branch Yard Configuration & Preferences", get_res.text)
        self.assertIn("Default Weighment Mode", get_res.text)

        post_res = self.client.post("/api/branch/settings", data={
            "branch_id": "br-chikhali",
            "default_weighment_mode": "MANUAL_YARD",
            "parchi_gate_no": "Gate No. 3",
            "auto_print_parchi": "ENABLED",
            "cash_drawer_warning_limit": "60000"
        }, follow_redirects=True)
        self.assertEqual(post_res.status_code, 200)
        self.assertIn("Gate No. 3", post_res.text)

    def test_farmer_edit_and_audit_change_logs(self):
        """Verify farmer can be edited any time and all diffs are logged in audit_change_logs."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, phone, village FROM parties WHERE party_type='FARMER' LIMIT 1")
        farmer = cur.fetchone()
        conn.close()

        farmer_id = farmer["id"]
        updated_phone = "9826099887"
        updated_village = "Sanwer Road Yard"
        reason = "Farmer changed SIM and village address"

        edit_res = self.client.post("/api/branch/farmers/edit", data={
            "party_id": farmer_id,
            "name": farmer["name"],
            "phone": updated_phone,
            "village": updated_village,
            "khasra_record_no": "KH-888/44",
            "aadhaar_number": "9999-8888-7777",
            "pan_number": "ABCDE1234F",
            "bank_name": "Bank of Baroda",
            "bank_account_no": "123456789012",
            "bank_ifsc": "BARB0INDORE",
            "change_reason": reason,
            "branch_id": "br-chikhali",
            "operator_name": "Chief Cashier"
        })
        self.assertEqual(edit_res.status_code, 200)
        data = edit_res.json()
        self.assertTrue(data["success"])

        # Verify audit logs endpoint returns the logged change
        log_res = self.client.get(f"/api/branch/farmers/{farmer_id}/audit-logs")
        self.assertEqual(log_res.status_code, 200)
        log_data = log_res.json()
        self.assertTrue(log_data["success"])
        self.assertGreater(len(log_data["logs"]), 0)
        latest_log = log_data["logs"][0]
        self.assertEqual(latest_log["entity_id"], farmer_id)
        self.assertIn(reason, latest_log["change_summary"])

    def test_outward_calculate_and_create_order(self):
        """Verify outward calculation with cashier-typed hamali and challan generation."""
        calc_res = self.client.post("/api/outward/calculate", params={
            "net_weight_kg": 15000,
            "rate_per_quintal": 5000,
            "hamali_per_100kg": 30.0
        })
        self.assertEqual(calc_res.status_code, 200)
        calc_d = calc_res.json()
        # 15,000 kg = 150 Quintals
        self.assertEqual(calc_d["net_quintals"], 150.0)
        self.assertEqual(calc_d["gross_amount"], 750000.0)
        # Hamali: 150 Qtl * 30.0 = 4,500.0
        self.assertEqual(calc_d["hamali_amount"], 4500.0)
        self.assertEqual(calc_d["total_bill_amount"], 754500.0)

        # Create outward order
        create_res = self.client.post("/api/branch/outward/create", data={
            "branch_id": "br-chikhali",
            "buyer_name": "Malwa Oil Refineries Pvt Ltd",
            "commodity_name": "Soyabean (Yellow)",
            "net_weight_kg": 15000,
            "rate_per_quintal": 5000,
            "hamali_per_100kg": 30.0,
            "vehicle_number": "MP-09-TR-7722",
            "cashier_user_id": "cashier-1"
        })
        self.assertEqual(create_res.status_code, 200)
        order_d = create_res.json()
        self.assertTrue(order_d["success"])
        challan_no = order_d["challan_number"]
        self.assertTrue(challan_no.startswith("OUT-"))

        # Verify challan gate pass slip rendering
        challan_res = self.client.get(f"/api/branch/outward/challan/{challan_no}")
        self.assertEqual(challan_res.status_code, 200)
        self.assertIn("OUTWARD COMMODITY DISPATCH CHALLAN & GATE PASS", challan_res.text)
        self.assertIn("Malwa Oil Refineries Pvt Ltd", challan_res.text)
        self.assertIn("MP-09-TR-7722", challan_res.text)
        self.assertIn("₹4,500.00", challan_res.text)

    def test_merged_inward_and_cashier_payout(self):
        """Verify merged inward produce intake and immediate cash payout in one transaction."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM parties WHERE party_type='FARMER' LIMIT 1")
        farmer_id = cur.fetchone()["id"]
        conn.close()

        res = self.client.post("/api/branch/invoices/create", data={
            "branch_id": "br-chikhali",
            "party_id": farmer_id,
            "inspector_name": "Mahesh Patidar",
            "commodity_name": "Soyabean (Yellow)",
            "rate_per_quintal": 4650,
            "weighment_mode": "MANUAL_YARD",
            "yard_weight_kg": 2500,
            "moisture_percentage": 10.0,
            "settlement_mode": "CASH",
            "notes_500": 232,
            "notes_200": 1,
            "notes_100": 0,
            "notes_50": 1,
            "notes_20": 0,
            "notes_10": 0,
            "coins": 0
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"), f"Failed with: {data}")
        self.assertEqual(data["payout_status"], "PAID")
        self.assertIsNotNone(data["voucher_id"])
        # 2,500 Kg = 25.00 Qtl
        # Gross: 25 * 4650 = 1,16,250
        # Hamali: 25 * 25.0 = 625 (deducted, 0 cess)
        # Net: 1,16,250 - 625 = 1,15,625
        self.assertEqual(data["hamali_charge"], 625.0)
        self.assertEqual(data["net_payable_amount"], 115625.0)

    def test_superadmin_clickable_cards_branch_breakdown(self):
        """Verify Super Admin commodity cards have branch breakdown with average rates."""
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn("clickable-card", res.text)
        self.assertIn("openBranchStockModal", res.text)
        self.assertIn("branchStockModal", res.text)
        self.assertIn("Branch Yard Inventory & Buying Rates Breakdown", res.text)

    def test_buyer_company_registration_and_outward_dispatch(self):
        """Verify company/trader registration and outward dispatch with registered buyer."""
        buyer_res = self.client.post("/api/branch/buyers/register", data={
            "name": "Narmada Solvent Extractions Ltd",
            "contact_person": "Pankaj Sethi",
            "phone": "9826019922",
            "address": "Industrial Area, Phase 1, Indore",
            "gstin": "23AAACN8822P1Z1",
            "pan_number": "AAACN8822P",
            "home_branch_id": "br-chikhali",
            "bank_name": "HDFC Bank",
            "bank_account_no": "50200088991122",
            "bank_ifsc": "HDFC0000456"
        })
        self.assertEqual(buyer_res.status_code, 200)
        buyer_d = buyer_res.json()
        self.assertTrue(buyer_d["success"])
        new_buyer_id = buyer_d["buyer"]["id"]
        self.assertEqual(buyer_d["buyer"]["name"], "Narmada Solvent Extractions Ltd")

        # Verify buyers list API returns the new buyer
        list_res = self.client.get("/api/branch/buyers")
        self.assertEqual(list_res.status_code, 200)
        list_d = list_res.json()
        self.assertTrue(list_d["success"])
        buyer_names = [b["name"] for b in list_d["buyers"]]
        self.assertIn("Narmada Solvent Extractions Ltd", buyer_names)

        # Create outward order using buyer_id
        outward_res = self.client.post("/api/branch/outward/create", data={
            "branch_id": "br-chikhali",
            "buyer_id": new_buyer_id,
            "commodity_name": "Soyabean (Yellow)",
            "net_weight_kg": 20000,
            "rate_per_quintal": 4900,
            "hamali_per_100kg": 28.0,
            "vehicle_number": "MP-09-HG-3344",
            "cashier_user_id": "u-chikhali-cashier"
        })
        self.assertEqual(outward_res.status_code, 200)
        outward_d = outward_res.json()
        self.assertTrue(outward_d["success"])
        self.assertTrue(outward_d["challan_number"].startswith("OUT-"))

    def test_branch_dashboard_polished_cards_and_confirm_modal_and_clean_farmer_dir(self):
        """Verify polished branch cards, confirmation modal, registered buyer dropdown, and clean farmer directory without logs."""
        res = self.client.get("/branch/dashboard?branch_id=br-chikhali")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. Branch commodity cards look clean & structured
        self.assertIn("commodity-card-top", html)
        self.assertIn("commodity-rates-box", html)
        self.assertIn("target-rate-col", html)
        self.assertIn("card-selected-badge", html)
        self.assertIn("Hamali: ₹25/100Kg", html)

        # 2. Confirmation modal before printing parchi
        self.assertIn("inwardConfirmModal", html)
        self.assertIn("Review & Confirm Inward Weighment & Payment", html)
        self.assertIn("btnFinalInwardConfirm", html)
        self.assertIn("Confirm & Disburse / Issue Parchi", html)

        # 3. Outward registered buyer dropdown & modal
        self.assertIn("outward_buyer_id", html)
        self.assertIn("registerBuyerModal", html)
        self.assertIn("Register Buyer Company / Trader", html)

        # 4. Clean farmer directory: no raw logs displayed in the view
        self.assertIn("Registered Farmers", html)
        self.assertNotIn("farmerAuditModal", html)
        self.assertNotIn("Farmer Edit Audit History", html)

        # 5. Prominent link to Branch physical stock page
        self.assertIn("/branch/stock?branch_id=br-chikhali", html)
        self.assertIn("Yard Stock", html)

if __name__ == "__main__":
    unittest.main()
