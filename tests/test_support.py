"""
Test Support & Database Isolation Framework for Rajeshri Shahu Mandi ERP.
Ensures automated tests execute against an isolated temporary SQLite database,
strictly protecting the main database (commodity_mandi.db) from write pollution.
"""

import os
import sys
import tempfile
import atexit
import hashlib
import sqlite3

_TEST_DB_PATH = None
_DEV_DB_HASH_BEFORE = None
_DEV_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "commodity_mandi.db")


def get_dev_db_path() -> str:
    """Returns absolute path to the live/development database."""
    return _DEV_DB_PATH


def record_dev_db_hash() -> str:
    """Computes and caches the SHA-256 digest of the development database before tests run."""
    global _DEV_DB_HASH_BEFORE
    if os.path.exists(_DEV_DB_PATH):
        with open(_DEV_DB_PATH, "rb") as f:
            _DEV_DB_HASH_BEFORE = hashlib.sha256(f.read()).hexdigest()
    return _DEV_DB_HASH_BEFORE


def get_recorded_dev_db_hash() -> str:
    """Returns the recorded initial SHA-256 hash."""
    global _DEV_DB_HASH_BEFORE
    if _DEV_DB_HASH_BEFORE is None:
        record_dev_db_hash()
    return _DEV_DB_HASH_BEFORE


def verify_dev_db_unchanged() -> bool:
    """Verifies that the main database on disk is byte-for-byte identical to its pre-test state."""
    if not os.path.exists(_DEV_DB_PATH):
        return True
    with open(_DEV_DB_PATH, "rb") as f:
        current_hash = hashlib.sha256(f.read()).hexdigest()
    return current_hash == get_recorded_dev_db_hash()


def setup_test_database() -> str:
    """
    Initializes an isolated temporary database for test execution.
    Sets MANDI_TEST_DB_PATH in os.environ and populates clean schema + test fixtures.
    """
    global _TEST_DB_PATH
    if _TEST_DB_PATH and os.path.exists(_TEST_DB_PATH):
        os.environ["MANDI_TEST_DB_PATH"] = _TEST_DB_PATH
        return _TEST_DB_PATH

    # Ensure pre-test hash is recorded before anything touches the system
    record_dev_db_hash()

    # Create temporary isolated SQLite database
    temp_dir = tempfile.gettempdir()
    _TEST_DB_PATH = os.path.join(temp_dir, f"mandi_isolated_test_{os.getpid()}.db")
    os.environ["MANDI_TEST_DB_PATH"] = _TEST_DB_PATH

    # Remove any stale test db file
    for p in [_TEST_DB_PATH, _TEST_DB_PATH + "-wal", _TEST_DB_PATH + "-shm"]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

    # Import database module and initialize schema + test fixtures
    import database
    database.init_db()
    database.seed_test_fixtures()

    return _TEST_DB_PATH


def cleanup_test_database():
    """Removes the temporary test database file upon process termination."""
    global _TEST_DB_PATH
    if _TEST_DB_PATH and os.path.exists(_TEST_DB_PATH):
        try:
            os.remove(_TEST_DB_PATH)
        except OSError:
            pass
        for ext in ["-wal", "-shm"]:
            aux = _TEST_DB_PATH + ext
            if os.path.exists(aux):
                try:
                    os.remove(aux)
                except OSError:
                    pass
        _TEST_DB_PATH = None


atexit.register(cleanup_test_database)
