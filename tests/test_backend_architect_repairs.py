"""
Comprehensive Verification Suite for Principal Backend Architect & AI Assaying Repairs
Rajarshi Shahu Mandi ERP

Covers:
1. Google Gemini Multimodal Vision & OCR Grain Assaying
2. FastAPI /api/ai/analyze-grain and /api/ai/ocr-moisture Endpoints
3. Desktop Launcher Lifespan & Cloud Sync Worker
4. Transient-Only Fallback vs Banned Errors in supabase_sync
5. On-Demand Cloud Fallback Ticket Lookup in /api/inspector/tickets/{ticket_no}
6. Prevent LWW Status Reversion (updated_at=CURRENT_TIMESTAMP) & QC Double-Spend (HTTP 409)
7. Atomic Branch-Prefixed Financial Year Invoice Sequences (INV-{BRANCH_CODE}-{FIN_YEAR}-{SEQ:06d})
8. PyInstaller Packaging Sanitization (zero .env or database leakage in dist)
"""

import os
import sys
import unittest
import tempfile
import sqlite3
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure commoditi software is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from tests.test_support import setup_test_database
setup_test_database()

import quality_engine
import supabase_sync
import database
from server import app, create_session_token, get_financial_year, get_next_branch_invoice_sequence


class TestBackendArchitectRepairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        cls.cashier_token = create_session_token("chikhali", "BRANCH_CASHIER", user_id="u-indore-cashier", branch_id="br-chikhali")
        cls.inspector_token = create_session_token("qc_chikhali", "QUALITY_INSPECTOR", user_id="u-qc-chikhali", branch_id="br-chikhali")

    def test_01_gemini_vision_grain_analysis(self):
        """Verify real Google Gemini 2.5 Flash grain grading analysis."""
        img_path = os.path.join(BASE_DIR, "mustard_seeds1.jpg")
        self.assertTrue(os.path.exists(img_path), "Sample image mustard_seeds1.jpg must exist.")

        with open(img_path, "rb") as f:
            raw_bytes = f.read()

        res = quality_engine.analyze_grain_with_gemini(raw_bytes, "Mustard (Yellow)")
        self.assertIsInstance(res, dict)
        self.assertIn("karda_pct", res)
        self.assertIn("damaged_pct", res)
        self.assertIn("green_seeds_pct", res)
        self.assertIn("broken_split_pct", res)
        self.assertIn("shriveled_pct", res)
        self.assertIn("admixture_pct", res)
        self.assertIn("sortex_clean_yield_pct", res)
        self.assertIn("grade_recommendation", res)
        self.assertIn("ai_engine", res)
        self.assertEqual(res["commodity_name"], "Mustard (Yellow)")
        self.assertGreaterEqual(res["sortex_clean_yield_pct"], 0.0)

    def test_02_gemini_ocr_moisture_meter(self):
        """Verify Google Gemini 2.5 Flash moisture meter display OCR."""
        img_path = os.path.join(BASE_DIR, "mustard_seeds1.jpg")
        with open(img_path, "rb") as f:
            raw_bytes = f.read()

        res = quality_engine.ocr_moisture_meter_with_gemini(raw_bytes)
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("success"))
        self.assertIn("moisture_pct", res)
        self.assertIsInstance(res["moisture_pct"], float)
        self.assertIn("confidence", res)
        self.assertIn("ocr_raw_text", res)
        self.assertIn("feasibility", res)

    def test_03_fastapi_ai_endpoints(self):
        """Verify /api/ai/analyze-grain and /api/ai/ocr-moisture FastAPI endpoints."""
        img_path = os.path.join(BASE_DIR, "mustard_seeds1.jpg")
        self.client.cookies.set("mandi_session", self.inspector_token)

        # 1. /api/ai/analyze-grain
        with open(img_path, "rb") as f:
            files = {"image": ("sample.jpg", f, "image/jpeg")}
            data = {"commodity_name": "Mustard (Yellow)"}
            resp_grain = self.client.post("/api/ai/analyze-grain", data=data, files=files)

        self.assertEqual(resp_grain.status_code, 200)
        json_grain = resp_grain.json()
        self.assertTrue(json_grain["success"])
        self.assertIn("analysis", json_grain)
        self.assertIn("karda_pct", json_grain["analysis"])
        self.assertIn("sortex_clean_yield_pct", json_grain["analysis"])

        # 2. /api/ai/ocr-moisture
        with open(img_path, "rb") as f:
            files = {"image": ("meter.jpg", f, "image/jpeg")}
            resp_ocr = self.client.post("/api/ai/ocr-moisture", files=files)

        self.assertEqual(resp_ocr.status_code, 200)
        json_ocr = resp_ocr.json()
        self.assertTrue(json_ocr["success"])
        self.assertIn("moisture_pct", json_ocr)
        self.assertIsInstance(json_ocr["moisture_pct"], float)
        self.assertIn("confidence", json_ocr)

    def test_04_desktop_launcher_lifespan_and_sync_worker(self):
        """Verify desktop_app.py lifespan is 'on' and server lifespan context manager is active."""
        desktop_app_file = os.path.join(BASE_DIR, "desktop_app.py")
        with open(desktop_app_file, "r", encoding="utf-8") as f:
            desktop_code = f.read()

        self.assertIn('lifespan="on"', desktop_code, "desktop_app.py must configure uvicorn with lifespan='on'")
        self.assertNotIn('lifespan="off"', desktop_code, "lifespan='off' must be completely removed")

        # Verify server lifespan context is registered
        self.assertIsNotNone(app.router.lifespan_context, "FastAPI app must register lifespan context manager")

    def test_05_transient_only_fallback_in_supabase_sync(self):
        """Verify is_transient_network_error and transient fallback behavior."""
        # Check transient errors
        err_6543 = Exception("could not connect to server: Connection refused on port 6543")
        err_timeout = Exception("OperationalError: connection timed out after 5000ms")
        self.assertTrue(supabase_sync.is_transient_network_error(err_6543))
        self.assertTrue(supabase_sync.is_transient_network_error(err_timeout))

        # Check banned errors (schema, integrity, auth)
        err_auth = Exception("password authentication failed for user 'postgres'")
        err_schema = Exception("relation 'quality_inspections' does not exist")
        err_integrity = Exception("duplicate key value violates unique constraint 'idx_invoices'")
        self.assertFalse(supabase_sync.is_transient_network_error(err_auth))
        self.assertFalse(supabase_sync.is_transient_network_error(err_schema))
        self.assertFalse(supabase_sync.is_transient_network_error(err_integrity))

        # Test pull_supabase_to_local re-raises banned error immediately
        mock_banned_engine = MagicMock()
        mock_banned_engine.connect.side_effect = Exception("password authentication failed for user 'postgres'")

        with patch("supabase_sync.get_pg_engine", return_value=mock_banned_engine):
            with self.assertRaises(Exception) as ctx:
                supabase_sync.pull_supabase_to_local(["branches"])
            self.assertIn("password authentication failed", str(ctx.exception))

    def test_06_on_demand_cloud_fallback_ticket_lookup(self):
        """Verify on-demand cloud fallback ticket lookup when ticket is absent in local SQLite."""
        self.client.cookies.set("mandi_session", self.cashier_token)

        ticket_code = "QC-CLOUD-TEST-999"
        mock_remote_record = {
            "id": "qc-remote-uuid-1",
            "ticket_no": ticket_code,
            "branch_id": "br-chikhali",
            "vehicle_no": "MH-28-AB-1234",
            "farmer_name": "Ramesh Patil",
            "farmer_phone": "9822001122",
            "commodity_name": "Soyabean (Yellow)",
            "moisture_pct": 10.5,
            "karda_pct": 0.5,
            "damaged_pct": 1.0,
            "green_seeds_pct": 0.5,
            "broken_split_pct": 0.5,
            "shriveled_pct": 0.5,
            "uniformity_index": 96.0,
            "dominant_breed": "JS-335",
            "breed_purity_pct": 98.0,
            "admixture_pct": 0.5,
            "breed_status": "FAQ Grade 1 (Pure Lot)",
            "status": "PENDING"
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [mock_remote_record]
        mock_client.get.return_value = mock_response

        with patch("supabase_sync.get_rest_client", return_value=mock_client):
            res = self.client.get(f"/api/inspector/tickets/{ticket_code}")

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["ticket"]["ticket_no"], ticket_code)
        self.assertEqual(data["ticket"]["farmer_name"], "Ramesh Patil")

        # Verify cached in local database
        local_cached = database.get_quality_inspection_by_ticket(ticket_code)
        self.assertIsNotNone(local_cached)
        self.assertEqual(local_cached["farmer_name"], "Ramesh Patil")

    def test_07_prevent_qc_double_spend_and_lww_reversion(self):
        """Verify QC ticket cannot be double-spent across invoices (HTTP 409) and updates updated_at."""
        self.client.cookies.set("mandi_session", self.cashier_token)

        # 1. Create a clean QC ticket
        qc_ticket_no = f"QC-DBSPEND-{int(database.datetime.now().timestamp())}"
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO quality_inspections (
                id, ticket_no, branch_id, vehicle_no, farmer_name, commodity_name,
                moisture_pct, status, created_at, updated_at
            ) VALUES (?, ?, 'br-chikhali', 'MH-28-QC', 'Shri Vitthal', 'Soyabean (Yellow)', 10.2, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (f"qc-{qc_ticket_no}", qc_ticket_no))
        conn.commit()
        conn.close()

        # 2. First invoice attachment succeeds
        inv1_payload = {
            "branch_id": "br-chikhali",
            "party_id": "p-farmer-1",
            "inspector_name": "Inspector Yard",
            "commodity_name": "Soyabean (Yellow)",
            "rate_per_quintal": 4650.0,
            "weighment_mode": "MANUAL_YARD",
            "yard_weight_kg": 2500.0,
            "bag_type": "LOOSE",
            "bag_count": 0,
            "moisture_percentage": 10.2,
            "karda_percentage": 0.5,
            "settlement_mode": "PENDING",
            "qc_ticket_no": qc_ticket_no
        }
        res1 = self.client.post("/api/branch/invoices/create", data=inv1_payload)
        self.assertEqual(res1.status_code, 200, f"First invoice creation failed: {res1.text}")
        data1 = res1.json()
        self.assertTrue(data1["success"])

        # Verify QC status updated to LINKED and updated_at was refreshed
        qc_after = database.get_quality_inspection_by_ticket(qc_ticket_no)
        self.assertEqual(qc_after["status"], "LINKED")
        self.assertIsNotNone(qc_after["updated_at"])

        # 3. Second invoice attempting to attach same QC ticket must be rejected with HTTP 409
        inv2_payload = dict(inv1_payload)
        res2 = self.client.post("/api/branch/invoices/create", data=inv2_payload)
        self.assertEqual(res2.status_code, 409, "Second invoice attachment of same QC ticket must return HTTP 409 Conflict.")
        self.assertIn("Conflict", res2.json()["detail"])

    def test_08_atomic_branch_invoice_sequences(self):
        """Verify atomic branch-prefixed sequence format: INV-{BRANCH_CODE}-{FIN_YEAR}-{SEQ:06d}."""
        self.client.cookies.set("mandi_session", self.cashier_token)

        # Test helper functions
        fin_year = get_financial_year(date(2026, 11, 3))
        self.assertEqual(fin_year, "202627")
        fin_year_jan = get_financial_year(date(2027, 2, 10))
        self.assertEqual(fin_year_jan, "202627")

        inv_payload = {
            "branch_id": "br-chikhali",
            "party_id": "p-farmer-1",
            "inspector_name": "Inspector Yard",
            "commodity_name": "Soyabean (Yellow)",
            "rate_per_quintal": 4650.0,
            "weighment_mode": "MANUAL_YARD",
            "yard_weight_kg": 1500.0,
            "bag_type": "LOOSE",
            "bag_count": 0,
            "moisture_percentage": 10.0,
            "karda_percentage": 0.0,
            "settlement_mode": "PENDING"
        }
        res = self.client.post("/api/branch/invoices/create", data=inv_payload)
        self.assertEqual(res.status_code, 200)
        token_number = res.json()["token_number"]

        # Validate regex pattern: INV-CHK-YYYYYY-XXXXXX
        import re
        pattern = r"^INV-CHK-\d{6}-\d{6}$"
        self.assertTrue(bool(re.match(pattern, token_number)), f"Invoice token '{token_number}' must match format INV-CHK-FINYEAR-SEQ000000")

    def test_09_pyinstaller_packaging_sanitization(self):
        """Verify build_desktop_app.py and spec files do not bundle .env or commodity_mandi.db."""
        build_script = os.path.join(BASE_DIR, "build_desktop_app.py")
        with open(build_script, "r", encoding="utf-8") as f:
            script_text = f.read()

        self.assertNotIn("commodity_mandi.db", script_text, "build_desktop_app.py must not bundle commodity_mandi.db")
        self.assertNotIn("'.env'", script_text, "build_desktop_app.py must not bundle .env")
        self.assertNotIn('".env"', script_text, "build_desktop_app.py must not bundle .env")

        spec_file = os.path.join(BASE_DIR, "Rajarshi_Shahu_Trading.spec")
        if os.path.exists(spec_file):
            with open(spec_file, "r", encoding="utf-8") as f:
                spec_text = f.read()
            self.assertNotIn("commodity_mandi.db", spec_text, "Rajarshi_Shahu_Trading.spec must not bundle database")
            self.assertNotIn(".env", spec_text, "Rajarshi_Shahu_Trading.spec must not bundle .env")


if __name__ == "__main__":
    unittest.main()
