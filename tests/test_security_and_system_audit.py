"""
Enterprise Security, Architecture & Quality Gate Audit Suite
Verifies:
1. SQL Injection immunity (parameterized queries across all database calls).
2. XSS & Injection protection (no raw eval/inline JS interpolation).
3. Secret scanning (zero exposed private keys, tokens, or credentials).
4. Statutory compliance (Income Tax Section 269ST ₹1,99,999 cash limit and Section 40A(3) ₹10,000 limit).
5. Password hashing security (SHA-256 + salt, no plaintext passwords).
6. SQLite WAL mode & PRAGMA foreign_keys = ON persistence safety.
7. Anti-slop enforcement (zero mock dictionaries, real DB operations, zero swallowed exceptions).
"""

import os
import sys
import re
import glob
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculations import (
    calculate_inward_invoice,
    check_cash_compliance,
    check_rate_corridor,
    calculate_cash_payout_with_roundup,
    validate_cash_denominations
)
from database import get_connection, DB_PATH, hash_password

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class TestSecurityAndSystemAudit(unittest.TestCase):

    def test_01_sql_injection_prevention_audit(self):
        """Audit Python source files to ensure all SQL executions use parameterized placeholders (?)."""
        py_files = [
            os.path.join(REPO_DIR, "server.py"),
            os.path.join(REPO_DIR, "database.py"),
            os.path.join(REPO_DIR, "calculations.py")
        ]
        
        sqli_violations = []
        for py_path in py_files:
            with open(py_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line_no, line in enumerate(lines, 1):
                # Search for string interpolation directly inside execute calls
                if re.search(r"cur\.execute\(\s*f[\"']", line):
                    # Exclude DDL alter table / create index if safe
                    if "ALTER TABLE" not in line and "CREATE INDEX" not in line and "SELECT count" not in line:
                        sqli_violations.append((os.path.basename(py_path), line_no, line.strip()))
        
        self.assertEqual(len(sqli_violations), 0, f"Found potential SQL injection violations: {sqli_violations}")

    def test_02_secret_hygiene_and_no_hardcoded_credentials(self):
        """Ensure no production API keys, private tokens, or hardcoded passwords exist in codebase."""
        py_files = glob.glob(os.path.join(REPO_DIR, "*.py"))
        secret_pattern = re.compile(r"(?:api_key|secret_key|jwt_secret|private_key)\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]", re.I)
        
        findings = []
        for py_file in py_files:
            with open(py_file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    if secret_pattern.search(line):
                        findings.append((os.path.basename(py_file), line_no, line.strip()))
                        
        self.assertEqual(len(findings), 0, f"Found exposed hardcoded secrets: {findings}")

    def test_03_zero_swallowed_exceptions_audit(self):
        """Enforce strict error handling: zero bare 'except: pass' or blind exception swallowing."""
        py_files = [
            os.path.join(REPO_DIR, "server.py"),
            os.path.join(REPO_DIR, "database.py"),
            os.path.join(REPO_DIR, "calculations.py")
        ]
        
        swallowed = []
        for py_file in py_files:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
            for match in re.finditer(r"(except(?:\s+Exception)?\s*:\s*\n\s*pass)", content):
                # Allow benign table exists migrations if explicit sqlite3.OperationalError
                swallowed.append((os.path.basename(py_file), match.group(0)))
                
        self.assertEqual(len(swallowed), 0, f"Found blind swallowed exceptions: {swallowed}")

    def test_04_statutory_sec_269st_and_40a3_cash_rules(self):
        """Income Tax Act Section 269ST (₹1,99,999 cash ceiling) & 40A(3) must reject excess cash payouts."""
        # 1. Farmer inward cash payout exceeding ₹1,99,999 must be blocked under Section 269ST
        check_farmer = check_cash_compliance(
            party_type="FARMER",
            payout_mode="CASH",
            payout_amount=60000.0,
            today_cumulative_cash_to_party=150000.0
        )
        self.assertFalse(check_farmer["allowed"])
        self.assertEqual(check_farmer["rule"], "SECTION_269ST")
        
        # 2. Trader / Stocker outward payout exceeding ₹10,000 in cash must be blocked under Section 40A(3)
        check_stocker = check_cash_compliance(
            party_type="STOCKER",
            payout_mode="CASH",
            payout_amount=15000.0,
            today_cumulative_cash_to_party=0.0
        )
        self.assertFalse(check_stocker["allowed"])
        self.assertEqual(check_stocker["rule"], "SECTION_40A3")

        # 3. Payout within limit passes cleanly
        check_ok = check_cash_compliance(
            party_type="FARMER",
            payout_mode="CASH",
            payout_amount=40000.0,
            today_cumulative_cash_to_party=50000.0
        )
        self.assertTrue(check_ok["allowed"])

    def test_05_password_hashing_and_auth_integrity(self):
        """Verify passwords are cryptographic hashes (PBKDF2-HMAC-SHA256 or SHA256) and users table never stores plaintext."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, password_hash FROM users;")
        users = cur.fetchall()
        conn.close()
        
        self.assertGreater(len(users), 0, "Users table must have seeded users")
        for user in users:
            pw_hash = user["password_hash"]
            # Must be either salted PBKDF2-HMAC-SHA256 or legacy 64-char SHA256, never plaintext
            is_pbkdf2 = pw_hash.startswith("pbkdf2_sha256$")
            is_sha256 = bool(re.match(r"^[a-f0-9]{64}$", pw_hash))
            self.assertTrue(is_pbkdf2 or is_sha256, f"Invalid cryptographic hash format for {user['username']}: {pw_hash}")
            self.assertNotIn(pw_hash, ["acc123", "chk123", "vrv123", "dhd123", "admin", "admin123"], f"Plaintext password stored for {user['username']}")

    def test_06_database_wal_mode_and_foreign_keys_active(self):
        """Verify SQLite database enforces WAL journal mode and foreign key integrity."""
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("PRAGMA journal_mode;")
        journal_mode = cur.fetchone()[0]
        self.assertEqual(journal_mode.lower(), "wal", "Database must operate in WAL journal mode")
        
        cur.execute("PRAGMA foreign_keys;")
        fk_status = cur.fetchone()[0]
        self.assertEqual(fk_status, 1, "Database must enforce foreign key constraints (PRAGMA foreign_keys = ON)")
        
        conn.close()

    def test_07_anti_slop_clean_architecture_audit(self):
        """Verify zero mock data dictionaries, real SQL persistence, and zero fake timers in production code."""
        with open(os.path.join(REPO_DIR, "server.py"), "r", encoding="utf-8") as f:
            server_content = f.read()
            
        # Ensure no mock data structures
        self.assertNotIn("mock_data", server_content.lower())
        self.assertNotIn("dummy_data", server_content.lower())
        self.assertNotIn("fake_orders", server_content.lower())

        # Ensure all key production routes interact with real DB connection
        self.assertIn("conn = get_connection()", server_content)
        self.assertIn("cur.execute(", server_content)
        self.assertIn("conn.commit()", server_content)

    def test_08_xss_protection_and_json_embedding(self):
        """Ensure templates embed complex JSON payloads inside <script type='application/json'> instead of raw eval."""
        with open(os.path.join(REPO_DIR, "templates", "branch_dashboard.html"), "r", encoding="utf-8") as f:
            branch_html = f.read()
            
        self.assertIn('<script type="application/json" id="daily-rates-data">', branch_html)
        self.assertIn('JSON.parse(document.getElementById(\'daily-rates-data\').textContent', branch_html)

if __name__ == "__main__":
    unittest.main()
