"""
Unit & Integration Tests for Mandi Live Sync Engine (/ws/live & Telemetry Push).
"""

import os
import sys
import unittest

# Ensure commoditi software is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_support import setup_test_database
setup_test_database()

from starlette.testclient import TestClient
from server import app, live_sync_hub, create_session_token

class TestLiveSyncEngine(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_websocket_connection_and_ping_pong(self):
        """Tests that a client connects to /ws/live, receives greeting, and exchanges ping-pong."""
        with self.client.websocket_connect("/ws/live") as websocket:
            # First frame is connection greeting
            greeting = websocket.receive_json()
            self.assertEqual(greeting["type"], "connected")
            self.assertIn("Established", greeting["message"])

            # Test heartbeat ping
            websocket.send_text("ping")
            pong = websocket.receive_text()
            self.assertEqual(pong, "pong")

    def test_websocket_broadcast_event(self):
        """Tests that broadcast dispatches JSON payloads to active WebSocket listeners."""
        with self.client.websocket_connect("/ws/live") as websocket:
            # Drain connection greeting
            greeting = websocket.receive_json()
            self.assertEqual(greeting["type"], "connected")

            # Send live event
            import asyncio
            asyncio.run(live_sync_hub.broadcast({
                "type": "qc_ticket_created",
                "data": {
                    "ticket_no": "QC-TEST-001",
                    "farmer_name": "Rameshwar Patel",
                    "commodity_name": "Soyabean (Yellow)",
                    "branch_id": "br-chikhali"
                }
            }))
            payload = websocket.receive_json()
            self.assertEqual(payload["type"], "qc_ticket_created")
            self.assertEqual(payload["data"]["ticket_no"], "QC-TEST-001")
            self.assertEqual(payload["data"]["farmer_name"], "Rameshwar Patel")

    def test_cloud_sync_telemetry_endpoint(self):
        """Tests POST /api/admin/sync-cloud triggers telemetry push with valid session."""
        admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        self.client.cookies.set("mandi_session", admin_token)

        res = self.client.post("/api/admin/sync-cloud")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIn("pushed", data.get("message", "").lower())

if __name__ == "__main__":
    unittest.main()
