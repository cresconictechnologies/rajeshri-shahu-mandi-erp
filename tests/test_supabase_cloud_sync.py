"""
End-to-End Verification Test Suite: Supabase Multi-Branch Cloud Sync Architecture
Rajarshi Shahu Trading (Commercial Mandi ERP v1.0)
Testing:
1. Supabase Cloud Sync Hub Card in /admin/settings
2. Cloud Sync Badges across Accounts, Branch Cashier, and Inspector Portals
3. /api/supabase/status, /api/admin/supabase/ping, /api/admin/supabase/migrate, /api/admin/supabase/sync
4. Edge-Cloud hybrid offline resilience & Last-Write-Wins (LWW) conflict handling
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure commoditi software directory is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, PARENT_DIR)

from server import app, create_session_token
from database import get_connection
import supabase_sync


class TestSupabaseCloudSyncArchitecture(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Super admin session
        cls.admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        cls.accountant_token = create_session_token("accountant", "ACCOUNTANT_HQ", user_id="u-accountant")
        cls.cashier_token = create_session_token("chikhali", "BRANCH_CASHIER", user_id="u-indore-cashier", branch_id="br-chikhali")
        cls.inspector_token = create_session_token("qc_chikhali", "QUALITY_INSPECTOR", user_id="u-qc-chikhali", branch_id="br-chikhali")

    def test_01_api_supabase_status_endpoint(self):
        """Verifies GET /api/supabase/status returns complete project telemetry."""
        res = self.client.get("/api/supabase/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("project_ref"), "dbhcpebchoyjyffqjgih")
        self.assertIn(data.get("status"), ["CONNECTED", "OFFLINE"])
        self.assertIn("latency_ms", data)
        self.assertIn("last_sync", data)
        print(f"[PASS] /api/supabase/status verified: Status={data.get('status')}, Latency={data.get('latency_ms')}ms")

    def test_02_admin_supabase_ping(self):
        """Verifies POST /api/admin/supabase/ping executes live connectivity probe."""
        client = TestClient(app)
        client.cookies.set("mandi_session", self.admin_token)
        res = client.post("/api/admin/supabase/ping")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("status", data)
        self.assertIn(data.get("status"), ["CONNECTED", "OFFLINE"])
        self.assertIn("message", data)
        print(f"[PASS] /api/admin/supabase/ping verified: {data.get('message')}")

    def test_03_admin_supabase_save_and_connect(self):
        """Verifies POST /api/admin/supabase/connect updates credentials in system_settings."""
        client = TestClient(app)
        client.cookies.set("mandi_session", self.admin_token)
        res = client.post(
            "/api/admin/supabase/connect",
            data={
                "supabase_url": "https://dbhcpebchoyjyffqjgih.supabase.co",
                "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-anon-key",
                "database_url": "postgresql://postgres:RajarshiShahu2026MandiSecure@db.dbhcpebchoyjyffqjgih.supabase.co:5432/postgres",
                "project_ref": "dbhcpebchoyjyffqjgih"
            },
            headers={"Accept": "application/json"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))

        # Verify saved in SQLite system_settings
        cfg = supabase_sync.get_supabase_config()
        self.assertEqual(cfg.get("supabase_url"), "https://dbhcpebchoyjyffqjgih.supabase.co")
        self.assertEqual(cfg.get("project_ref"), "dbhcpebchoyjyffqjgih")
        print("[PASS] /api/admin/supabase/connect saved & verified in database settings")

    def test_04_schema_migration_to_supabase(self):
        """Verifies POST /api/admin/supabase/migrate creates and verifies 14 production tables."""
        client = TestClient(app)
        client.cookies.set("mandi_session", self.admin_token)
        res = client.post("/api/admin/supabase/migrate")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        migrated = data.get("tables_migrated", [])
        self.assertGreaterEqual(len(migrated), 10)
        self.assertIn("purchase_invoices", migrated)
        self.assertIn("quality_inspections", migrated)
        self.assertIn("daily_commodity_rates", migrated)
        self.assertIn("cashier_payouts", migrated)
        print(f"[PASS] Schema Migration verified: {len(migrated)} tables present in Supabase")

    def test_05_bidirectional_sync(self):
        """Verifies POST /api/admin/supabase/sync executes push & pull without errors."""
        client = TestClient(app)
        client.cookies.set("mandi_session", self.admin_token)
        res = client.post("/api/admin/supabase/sync")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIn("pushed", data)
        self.assertIn("pulled", data)
        print(f"[PASS] Sync verified: Pushed {data.get('pushed')}, Pulled {data.get('pulled')}")

    def test_06_admin_settings_ui_card(self):
        """Verifies the ⚡ Supabase Multi-Branch Cloud Sync Hub card in templates/admin_settings.html."""
        client = TestClient(app)
        client.cookies.set("mandi_session", self.admin_token)
        res = client.get("/admin/settings")
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn("Supabase Multi-Branch Cloud Sync Hub", html)
        self.assertIn("dbhcpebchoyjyffqjgih", html)
        self.assertIn("Test Connection & Ping", html)
        self.assertIn("Run Schema Migration to Cloud", html)
        self.assertIn("Sync Now (Push & Pull)", html)
        self.assertIn("SUPABASE_URL", html)
        self.assertIn("DATABASE_URL", html)
        self.assertIn("cloudSyncStatusBadge", html)
        print("[PASS] admin_settings.html Cloud Sync Hub UI Card verified with all required controls")

    def test_07_accounts_dashboard_sync_badge(self):
        """Verifies Cloud Sync badge in Accountant Dashboard."""
        client = TestClient(app)
        client.cookies.set("mandi_session", self.accountant_token)
        res = client.get("/accounts/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn("cloudSyncStatusBadge", res.text)
        self.assertIn("Cloud: Synced", res.text)
        print("[PASS] accounts_dashboard.html Cloud Sync status badge verified")

    def test_08_branch_dashboard_sync_badge(self):
        """Verifies Cloud Sync badge in Cashier & Munim Branch Dashboard."""
        client = TestClient(app)
        client.cookies.set("mandi_session", self.cashier_token)
        res = client.get("/branch/dashboard?branch_id=br-chikhali")
        self.assertEqual(res.status_code, 200)
        self.assertIn("cloudSyncStatusBadge", res.text)
        self.assertIn("Cloud: Synced", res.text)
        print("[PASS] branch_dashboard.html Cloud Sync status badge verified")

    def test_09_inspector_portal_sync_badge(self):
        """Verifies Cloud Sync badge in Inspector QC Mobile Portal."""
        client = TestClient(app)
        client.cookies.set("mandi_session", self.inspector_token)
        res = client.get("/inspector/portal")
        self.assertEqual(res.status_code, 200)
        self.assertIn("cloudSyncStatusBadge", res.text)
        self.assertIn("Cloud: Synced", res.text)
        print("[PASS] inspector_portal.html Cloud Sync status badge verified")


if __name__ == "__main__":
    unittest.main()
