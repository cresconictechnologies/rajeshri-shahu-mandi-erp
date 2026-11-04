"""
Consolidated Audit Test Suite:
1. Staff and Admin Login Credentials Verification (Database Hashes + FastAPI /login Endpoint)
2. Realtime Supabase Cloud Synchronization (Ping, Status, Tables Push/Pull, Sync Queue)

Rajarshi Shahu Trading (Commercial Mandi ERP)
"""

import os
import sys
import unittest
import sqlite3
from fastapi.testclient import TestClient

# Path resolution
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, APP_DIR)

import database
import server
import supabase_sync


class TestLoginCredentialsAndRealtimeSync(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db_path = os.path.join(APP_DIR, "commodity_mandi.db")
        cls.client = TestClient(server.app, follow_redirects=False)

        cls.credential_matrix = [
            ("admin", "admin123", "SUPER_ADMIN", "/admin/dashboard"),
            ("Suraj", "Suraj@123", "ACCOUNTANT_HQ", "/accounts/dashboard"),
            ("accountant", "acc123", "ACCOUNTANT_HQ", "/accounts/dashboard"),
            ("chikhali", "chk123", "BRANCH_CASHIER", "/branch/dashboard?branch_id=br-chikhali"),
            ("varvand", "vrv123", "BRANCH_CASHIER", "/branch/dashboard?branch_id=br-varvand"),
            ("dhad", "dhd123", "BRANCH_CASHIER", "/branch/dashboard?branch_id=br-dhad"),
            ("qc_chikhali", "qc123", "QUALITY_INSPECTOR", "/inspector/portal"),
            ("qc_varvand", "qc123", "QUALITY_INSPECTOR", "/inspector/portal"),
            ("qc_dhad", "qc123", "QUALITY_INSPECTOR", "/inspector/portal"),
            ("qc_head", "qc123", "QUALITY_INSPECTOR", "/inspector/portal"),
            ("qc_sanjay_chikhali", "qc123", "QUALITY_INSPECTOR", "/inspector/portal"),
        ]

    # --------------------------------------------------------------------------
    # 1. DATABASE HASH VERIFICATION
    # --------------------------------------------------------------------------

    def test_01_database_password_hashes_direct(self):
        """Verifies all password hashes directly in commodity_mandi.db."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        for uname, pwd, exp_role, exp_target in self.credential_matrix:
            for test_case in [uname, uname.lower(), uname.upper()]:
                cur.execute(
                    "SELECT id, username, password_hash, role, branch_id, is_active FROM users WHERE LOWER(username) = LOWER(?)",
                    (test_case.strip(),)
                )
                user = cur.fetchone()
                self.assertIsNotNone(user, f"User {test_case} not found in commodity_mandi.db")
                self.assertEqual(user["is_active"], 1, f"User {test_case} is inactive")
                self.assertEqual(user["role"], exp_role, f"Role mismatch for {test_case}")

                is_valid, _ = database.verify_password(pwd, user["password_hash"])
                self.assertTrue(is_valid, f"Password verification failed for user '{test_case}' with password '{pwd}'")

        conn.close()

    # --------------------------------------------------------------------------
    # 2. FASTAPI /login HTTP ENDPOINT VERIFICATION
    # --------------------------------------------------------------------------

    def test_02_login_endpoint_redirects_and_sessions(self):
        """Verifies HTTP POST /login sets mandi_session cookie and redirects correctly for both case variations."""
        for uname, pwd, exp_role, exp_target in self.credential_matrix:
            for test_case in [uname, uname.lower()]:
                res = self.client.post("/login", data={"username": test_case, "password": pwd})
                self.assertEqual(
                    res.status_code, 303,
                    f"Expected 303 redirect for {test_case}, got {res.status_code}"
                )
                self.assertEqual(
                    res.headers.get("location"), exp_target,
                    f"Redirect URL mismatch for {test_case}: expected {exp_target}, got {res.headers.get('location')}"
                )
                self.assertIn(
                    "mandi_session", res.cookies,
                    f"Session cookie mandi_session not set for {test_case}"
                )

    # --------------------------------------------------------------------------
    # 3. SUPABASE CONFIGURATION & PING STATUS
    # --------------------------------------------------------------------------

    def test_03_supabase_configuration_and_ping(self):
        """Verifies Supabase credentials resolution and live connectivity probe."""
        cfg = supabase_sync.get_supabase_config()
        self.assertIsNotNone(cfg.get("supabase_url"), "supabase_url missing")
        self.assertIsNotNone(cfg.get("supabase_key"), "supabase_key missing")
        self.assertEqual(cfg.get("project_ref"), "dbhcpebchoyjyffqjgih")

        # Test ping_supabase() function
        ping = supabase_sync.ping_supabase()
        self.assertTrue(ping.get("success"), f"ping_supabase failed: {ping.get('message')}")
        self.assertEqual(ping.get("status"), "CONNECTED")
        self.assertGreater(ping.get("latency_ms", 0), 0)

        # Test get_sync_status() function
        status = supabase_sync.get_sync_status()
        self.assertTrue(status.get("online"))
        self.assertEqual(status.get("status"), "CONNECTED")

    # --------------------------------------------------------------------------
    # 4. SUPABASE HTTP API ENDPOINTS
    # --------------------------------------------------------------------------

    def test_04_supabase_api_endpoints(self):
        """Verifies /api/supabase/status, /api/admin/supabase/ping, and /api/admin/supabase/sync."""
        admin_token = server.create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")

        # GET /api/supabase/status (Public)
        res_status = self.client.get("/api/supabase/status")
        self.assertEqual(res_status.status_code, 200)
        data_status = res_status.json()
        self.assertTrue(data_status.get("success"))
        self.assertEqual(data_status.get("status"), "CONNECTED")

        # POST /api/admin/supabase/ping (Authenticated)
        client_auth = TestClient(server.app)
        client_auth.cookies.set("mandi_session", admin_token)

        res_ping = client_auth.post("/api/admin/supabase/ping")
        self.assertEqual(res_ping.status_code, 200)
        data_ping = res_ping.json()
        self.assertEqual(data_ping.get("status"), "CONNECTED")

        # POST /api/admin/supabase/sync (Authenticated)
        res_sync = client_auth.post("/api/admin/supabase/sync")
        self.assertEqual(res_sync.status_code, 200)
        data_sync = res_sync.json()
        self.assertTrue(data_sync.get("success"))

    # --------------------------------------------------------------------------
    # 5. SUPABASE REALTIME SYNC QUEUE & TABLE PUSH/PULL
    # --------------------------------------------------------------------------

    def test_05_sync_queue_lifecycle_and_table_replication(self):
        """Verifies enqueueing, background processing, and table replication to Supabase."""
        # 1. Test queue lifecycle
        evt_id = supabase_sync.queue_sync_event(
            entity_type="commodities",
            entity_id="audit-sync-test-01",
            action="UPSERT",
            payload={"name": "Soybean", "status": "ACTIVE"}
        )
        self.assertTrue(len(evt_id) > 0, "Failed to queue sync event")

        # Verify pending count
        pending = supabase_sync.get_pending_queue_count()
        self.assertGreaterEqual(pending, 1)

        # Process sync queue
        proc_res = supabase_sync.process_sync_queue()
        self.assertTrue(proc_res.get("success"), f"process_sync_queue failed: {proc_res}")

        # Check queue item status
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT status, synced_at FROM sync_queue WHERE id=?", (evt_id,))
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "COMPLETED")
        self.assertIsNotNone(row["synced_at"])

        # Cleanup test event
        cur.execute("DELETE FROM sync_queue WHERE id=?", (evt_id,))
        conn.commit()
        conn.close()

        # 2. Test push_local_to_supabase on core tables
        push_res = supabase_sync.push_local_to_supabase(["branches", "commodities", "purchase_invoices", "cashier_payouts"])
        self.assertTrue(push_res.get("success"), f"Push failed: {push_res}")
        self.assertEqual(len(push_res.get("errors", [])), 0)

        # 3. Test pull_supabase_to_local on core tables
        pull_res = supabase_sync.pull_supabase_to_local(["branches", "commodities", "purchase_invoices"])
        self.assertTrue(pull_res.get("success"), f"Pull failed: {pull_res}")
        self.assertEqual(len(pull_res.get("errors", [])), 0)


if __name__ == "__main__":
    unittest.main()
