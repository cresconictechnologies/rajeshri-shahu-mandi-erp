"""
Test suite package initialization.
Ensures the isolated test database is configured before any test module is imported.
"""

from .test_support import setup_test_database, record_dev_db_hash

record_dev_db_hash()
setup_test_database()
