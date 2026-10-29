"""
Automated Regression Test Suite for Database Isolation and Development DB Protection.
Verifies that:
1. Test suite operates exclusively against an isolated temporary SQLite database.
2. In production mode (MANDI_ERP_ENV=production), test database override is strictly forbidden and fails closed.
3. The main development database (commodity_mandi.db) remains 100% byte-for-byte unchanged.
"""

import os
import sys
import unittest
import hashlib

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_support import (
    setup_test_database,
    get_dev_db_path,
    get_recorded_dev_db_hash,
    verify_dev_db_unchanged
)
setup_test_database()

import database


class TestDatabaseIsolation(unittest.TestCase):

    def test_01_test_suite_operates_on_isolated_database(self):
        """Active database in test environment must be the isolated temp DB, never commodity_mandi.db."""
        active_db_path = database.get_db_path()
        dev_db_path = get_dev_db_path()

        self.assertIn("MANDI_TEST_DB_PATH", os.environ, "MANDI_TEST_DB_PATH must be configured in test environment")
        self.assertEqual(active_db_path, os.path.abspath(os.environ["MANDI_TEST_DB_PATH"]))
        self.assertNotEqual(active_db_path, os.path.abspath(dev_db_path), "Test DB must not point to live development DB")
        self.assertTrue(os.path.exists(active_db_path), "Isolated test database file must exist on disk")

    def test_02_production_guardrail_rejects_test_db_override(self):
        """Under MANDI_ERP_ENV=production, attempting to set MANDI_TEST_DB_PATH must raise a security RuntimeError."""
        orig_env = os.environ.get("MANDI_ERP_ENV")
        try:
            os.environ["MANDI_ERP_ENV"] = "production"
            with self.assertRaises(RuntimeError) as ctx:
                database.get_db_path()
            self.assertIn("CRITICAL SECURITY ERROR", str(ctx.exception))
            self.assertIn("forbidden in production", str(ctx.exception))
        finally:
            if orig_env is not None:
                os.environ["MANDI_ERP_ENV"] = orig_env
            else:
                os.environ.pop("MANDI_ERP_ENV", None)

    def test_03_main_development_db_remains_byte_for_byte_unchanged(self):
        """The live/development database (commodity_mandi.db) must remain byte-for-byte unchanged after test executions."""
        dev_path = get_dev_db_path()
        if not os.path.exists(dev_path):
            self.skipTest("commodity_mandi.db does not exist in repo root.")

        recorded_hash = get_recorded_dev_db_hash()
        self.assertIsNotNone(recorded_hash, "Initial hash of commodity_mandi.db must have been recorded")

        with open(dev_path, "rb") as f:
            current_hash = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(
            current_hash,
            recorded_hash,
            "CRITICAL REGRESSION: commodity_mandi.db was modified during test suite execution! "
            f"Expected SHA-256: {recorded_hash}, Actual: {current_hash}"
        )
        self.assertTrue(verify_dev_db_unchanged())


if __name__ == "__main__":
    unittest.main()
