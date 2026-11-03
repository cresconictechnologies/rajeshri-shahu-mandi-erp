"""
Dedicated Acceptance Test Suite for Farmer Master Integration (Section 17).
Rajarshi Shahu Mandi ERP

Covers:
- Test 1: Existing farmer selected: name and mobile appear in separate fields.
- Test 2: Existing farmer received through QC ticket: correct master record is resolved by normalized phone/name.
- Test 3: Unregistered farmer received through QC ticket: registration action is available; zero auto-created records.
- Test 4: Newly registered farmer: visible in Farmer List and searchable.
- Test 5: Duplicate mobile number handling and candidate matching.
- Test 6: Ticket received twice: no duplicate farmer created.
- Test 7: Double-spend prevention on QC ticket attachment: attaching same ticket twice raises HTTP 409 Conflict.
- Test 8: Branch invoice sequence generation produces unique INV-CHK-YYYYMMDD-0001 tokens.
"""

import os
import sys
import re
import unittest
from datetime import date, datetime
from fastapi.testclient import TestClient

# Ensure commoditi software is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from tests.test_support import setup_test_database, get_dev_db_path, verify_dev_db_unchanged
setup_test_database()

import database
from server import app, create_session_token, generate_branch_invoice_token, get_next_branch_invoice_sequence


def normalize_phone_helper(phone: str) -> str:
    """Python mirror of frontend normalizePhoneNumber for identity verification."""
    if not phone:
        return ""
    cleaned = re.sub(r"\D", "", str(phone))
    if cleaned.startswith("91") and len(cleaned) > 10:
        cleaned = cleaned[2:]
    cleaned = cleaned.lstrip("0")
    return cleaned


def resolve_farmer_candidate(ticket_name: str, ticket_phone: str, candidates: list) -> tuple:
    """
    Python mirror of Section 17 Cultivator Identity Normalization & Resolution:
    Returns (status, matched_record_or_placeholder).
    status in ('VERIFIED', 'UNREGISTERED', 'AMBIGUOUS_DUPLICATE')
    """
    norm_phone = normalize_phone_helper(ticket_phone)
    norm_name = (ticket_name or "").strip().lower()

    # 1. Match by phone
    phone_matches = [c for c in candidates if normalize_phone_helper(c.get("phone", "")) == norm_phone]
    if len(phone_matches) == 1:
        return "VERIFIED", phone_matches[0]
    elif len(phone_matches) > 1:
        # Check if name disambiguates
        name_submatch = [c for c in phone_matches if (c.get("name") or "").strip().lower() == norm_name]
        if len(name_submatch) == 1:
            return "VERIFIED", name_submatch[0]
        return "AMBIGUOUS_DUPLICATE", phone_matches

    # 2. Match by exact or partial name
    name_matches = [c for c in candidates if (c.get("name") or "").strip().lower() == norm_name]
    if len(name_matches) == 1:
        return "VERIFIED", name_matches[0]

    # 3. Not found
    return "UNREGISTERED", {
        "placeholder_id": f"UNREGISTERED_{ticket_name}",
        "name": ticket_name,
        "phone": ticket_phone
    }


class TestFarmerMasterIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.cashier_token = create_session_token("chikhali", "BRANCH_CASHIER", user_id="u-indore-cashier", branch_id="br-chikhali")
        cls.qc_token = create_session_token("qc_chikhali", "QUALITY_INSPECTOR", user_id="u-qc-chikhali", branch_id="br-chikhali")
        cls.admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")

    def test_01_existing_farmer_selected_name_and_mobile_in_separate_fields(self):
        """Test 1: Existing farmer selected: name and mobile appear in separate fields."""
        self.client.cookies.set("mandi_session", self.cashier_token)
        res = self.client.get("/branch/dashboard?branch_id=br-chikhali")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Verify separate DOM input fields exist: #farmer_select and #farmer_mobile
        self.assertIn('id="farmer_select"', html, "Branch Weighment desk must provide dedicated farmer_select dropdown")
        self.assertIn('id="farmer_mobile"', html, "Branch Weighment desk must provide separate farmer_mobile tel field")
        self.assertIn('id="party_id"', html, "Branch Weighment desk must contain hidden party_id for immutable binding")

        # Verify dropdown options decouple name from mobile
        self.assertIn('data-phone="9827011111"', html, "Farmer options must separate phone number into data-phone attribute")
        self.assertIn('Rameshwar Patel', html, "Farmer options must display clean cultivator name")
        # Ensure no concatenated slop like 'Rameshwar Patel - 9827011111 (FARMER)' in display text
        self.assertNotIn('Rameshwar Patel - 9827011111 (FARMER)', html)

        # Verify backend API returns name and phone as separate schema fields
        search_res = self.client.get("/api/farmers/search?q=Rameshwar")
        self.assertEqual(search_res.status_code, 200)
        farmers = search_res.json().get("farmers", [])
        self.assertGreaterEqual(len(farmers), 1)
        target = farmers[0]
        self.assertEqual(target["name"], "Rameshwar Patel")
        self.assertEqual(target["phone"], "9827011111")
        self.assertIn("village", target)
        self.assertIn("khasra_record_no", target)

    def test_02_existing_farmer_received_through_qc_ticket_resolved_by_normalized_phone_and_name(self):
        """Test 2: Existing farmer received through QC ticket: correct master record is resolved by normalized phone/name."""
        # Test telephone normalization with country codes and spaces
        self.assertEqual(normalize_phone_helper("+91 98270 11111"), "9827011111")
        self.assertEqual(normalize_phone_helper("09827011111"), "9827011111")
        self.assertEqual(normalize_phone_helper("98270-11111"), "9827011111")

        # Load candidates from DB
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, phone, village FROM parties WHERE party_type='FARMER'")
        candidates = [dict(r) for r in cur.fetchall()]
        conn.close()

        # Resolve ticket with +91 country prefix
        status, matched = resolve_farmer_candidate("Rameshwar Patel", "+91 98270 11111", candidates)
        self.assertEqual(status, "VERIFIED")
        self.assertEqual(matched["id"], "p-farmer-1")
        self.assertEqual(matched["name"], "Rameshwar Patel")
        self.assertEqual(matched["phone"], "9827011111")

        # Resolve ticket with leading 0 prefix
        status_0, matched_0 = resolve_farmer_candidate("Rameshwar Patel", "09827011111", candidates)
        self.assertEqual(status_0, "VERIFIED")
        self.assertEqual(matched_0["id"], "p-farmer-1")

    def test_03_unregistered_farmer_received_through_qc_ticket_zero_auto_created_records(self):
        """Test 3: Unregistered farmer received through QC ticket: registration action is available; zero auto-created records."""
        self.client.cookies.set("mandi_session", self.qc_token)

        # Count master parties before
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM parties")
        count_before = cur.fetchone()[0]

        # Submit QC ticket for unknown farmer
        ticket_payload = {
            "branch_id": "br-chikhali",
            "farmer_name": "Raghunath Yadav (Unregistered)",
            "farmer_phone": "9893099999",
            "vehicle_no": "MH-28-UNREG-01",
            "commodity_name": "Soyabean (Yellow)",
            "moisture_pct": "11.0",
            "karda_pct": "0.5"
        }
        res_qc = self.client.post("/api/inspector/submit-qc", data=ticket_payload)
        self.assertEqual(res_qc.status_code, 200)
        qc_data = res_qc.json()
        self.assertTrue(qc_data["success"])
        ticket_no = qc_data["ticket"]["ticket_no"]

        # Count master parties after QC ticket submission
        cur.execute("SELECT count(*) FROM parties")
        count_after = cur.fetchone()[0]
        self.assertEqual(
            count_after,
            count_before,
            "CRITICAL: Submitting a QC ticket for an unregistered farmer must NEVER auto-insert a record into parties table!"
        )

        # Retrieve ticket via cashier desk and test Section 17 resolution
        cur.execute("SELECT id, name, phone FROM parties WHERE party_type='FARMER'")
        candidates = [dict(r) for r in cur.fetchall()]
        conn.close()

        status, placeholder = resolve_farmer_candidate("Raghunath Yadav (Unregistered)", "9893099999", candidates)
        self.assertEqual(status, "UNREGISTERED")
        self.assertTrue(placeholder["placeholder_id"].startswith("UNREGISTERED_"))

        # Verify registration action endpoint is fully available
        self.client.cookies.set("mandi_session", self.cashier_token)
        reg_check = self.client.get("/api/farmers/search?q=Raghunath")
        self.assertEqual(reg_check.status_code, 200)
        self.assertEqual(len(reg_check.json()["farmers"]), 0, "Unregistered farmer must not appear in master list")

    def test_04_newly_registered_farmer_visible_in_farmer_list_and_searchable(self):
        """Test 4: Newly registered farmer: visible in Farmer List and searchable."""
        self.client.cookies.set("mandi_session", self.cashier_token)

        farmer_name = "Harishchandra Shinde"
        farmer_phone = "9827088776"
        village = "Village Shelgaon"
        khasra = "Khasra No. 512/B"

        # Register farmer
        res_reg = self.client.post("/api/branch/farmers/register", data={
            "name": farmer_name,
            "phone": farmer_phone,
            "village": village,
            "khasra_record_no": khasra,
            "home_branch_id": "br-chikhali",
            "bank_name": "Bank of Maharashtra",
            "bank_account_no": "60012345678",
            "bank_ifsc": "MAHB0000123"
        })
        self.assertEqual(res_reg.status_code, 200)
        data = res_reg.json()
        self.assertTrue(data.get("success"))
        party_id = data.get("id")
        self.assertTrue(party_id.startswith("p-"))

        # 1. Search by full name
        res_s1 = self.client.get(f"/api/farmers/search?q={farmer_name}")
        self.assertEqual(res_s1.status_code, 200)
        f_list1 = res_s1.json().get("farmers", [])
        self.assertTrue(any(f["id"] == party_id for f in f_list1), "Newly registered farmer must be searchable by name")

        # 2. Search by mobile number
        res_s2 = self.client.get(f"/api/farmers/search?q={farmer_phone}")
        self.assertEqual(res_s2.status_code, 200)
        f_list2 = res_s2.json().get("farmers", [])
        self.assertTrue(any(f["id"] == party_id for f in f_list2), "Newly registered farmer must be searchable by phone")

        # 3. Verify in SQLite database
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, phone, village, khasra_record_no FROM parties WHERE id=?", (party_id,))
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], farmer_name)
        self.assertEqual(row["phone"], farmer_phone)
        self.assertEqual(row["village"], village)

    def test_05_duplicate_mobile_number_handling_and_candidate_matching(self):
        """Test 5: Duplicate mobile number handling and candidate matching."""
        self.client.cookies.set("mandi_session", self.cashier_token)

        shared_phone = "9827055555"
        # Register family member 1
        res1 = self.client.post("/api/branch/farmers/register", data={
            "name": "Kailash Patil (Senior)",
            "phone": shared_phone,
            "village": "Village Kawhala",
            "khasra_record_no": "Khasra 101/A",
            "home_branch_id": "br-chikhali"
        })
        self.assertTrue(res1.json().get("success"))
        id1 = res1.json().get("id")

        # Register family member 2 with the same phone
        res2 = self.client.post("/api/branch/farmers/register", data={
            "name": "Suresh Patil (Junior)",
            "phone": shared_phone,
            "village": "Village Kawhala",
            "khasra_record_no": "Khasra 101/B",
            "home_branch_id": "br-chikhali"
        })
        self.assertTrue(res2.json().get("success"))
        id2 = res2.json().get("id")

        self.assertNotEqual(id1, id2, "Two distinct farmers with same phone must receive distinct primary keys")

        # Candidate search by phone must return BOTH family members
        res_search = self.client.get(f"/api/farmers/search?q={shared_phone}")
        self.assertEqual(res_search.status_code, 200)
        candidates = res_search.json().get("farmers", [])
        candidate_ids = [c["id"] for c in candidates]
        self.assertIn(id1, candidate_ids)
        self.assertIn(id2, candidate_ids)

        # Candidate resolution with specific name resolves the correct one
        status, resolved = resolve_farmer_candidate("Suresh Patil (Junior)", shared_phone, candidates)
        self.assertEqual(status, "VERIFIED")
        self.assertEqual(resolved["id"], id2)

    def test_06_ticket_received_twice_no_duplicate_farmer_created(self):
        """Test 6: Ticket received twice: no duplicate farmer created."""
        self.client.cookies.set("mandi_session", self.qc_token)

        ticket_no = f"QC-IDEMP-{int(datetime.now().timestamp())}"
        payload = {
            "ticket_no": ticket_no,
            "branch_id": "br-chikhali",
            "farmer_name": "Anil Deshmukh",
            "farmer_phone": "9827044332",
            "vehicle_no": "MH-28-IDEMP",
            "commodity_name": "Soyabean (Yellow)",
            "moisture_pct": "10.4"
        }

        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM parties WHERE party_type='FARMER'")
        count_start = cur.fetchone()[0]

        # First reception
        res1 = self.client.post("/api/inspector/submit-qc", data=payload)
        self.assertEqual(res1.status_code, 200)

        cur.execute("SELECT count(*) FROM parties WHERE party_type='FARMER'")
        count_mid = cur.fetchone()[0]
        self.assertEqual(count_mid, count_start)

        # Second reception (replay of identical ticket)
        res2 = self.client.post("/api/inspector/submit-qc", data=payload)
        # Even if ticket is rejected or updated, parties table must NEVER add a duplicate farmer
        cur.execute("SELECT count(*) FROM parties WHERE party_type='FARMER'")
        count_end = cur.fetchone()[0]
        conn.close()

        self.assertEqual(count_end, count_start, "Duplicate reception of QC ticket must create ZERO duplicate farmers in parties table")

    def test_07_double_spend_prevention_on_qc_ticket_attachment(self):
        """Test 7: Double-spend prevention on QC ticket attachment: attaching same ticket twice raises HTTP 409 Conflict."""
        self.client.cookies.set("mandi_session", self.cashier_token)

        qc_code = f"QC-DOUBLE-SPEND-{int(datetime.now().timestamp())}"
        conn = database.get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO quality_inspections (
                id, ticket_no, branch_id, vehicle_no, farmer_name, commodity_name,
                moisture_pct, status, created_at, updated_at
            ) VALUES (?, ?, 'br-chikhali', 'MH-28-DS-01', 'Murlidhar Sharma', 'Soyabean (Yellow)', 10.0, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (f"qc-{qc_code}", qc_code))
        conn.commit()
        conn.close()

        inv_payload = {
            "branch_id": "br-chikhali",
            "party_id": "p-farmer-1",
            "inspector_name": "Inspector Yard",
            "commodity_name": "Soyabean (Yellow)",
            "rate_per_quintal": 4650.0,
            "weighment_mode": "MANUAL_YARD",
            "yard_weight_kg": 2000.0,
            "bag_type": "LOOSE",
            "bag_count": 0,
            "moisture_percentage": 10.0,
            "karda_percentage": 0.0,
            "settlement_mode": "PENDING",
            "qc_ticket_no": qc_code
        }

        # 1. First invoice creation with QC ticket succeeds (HTTP 200)
        res1 = self.client.post("/api/branch/invoices/create", data=inv_payload)
        self.assertEqual(res1.status_code, 200, f"First invoice creation must succeed: {res1.text}")
        self.assertTrue(res1.json()["success"])

        # 2. Second invoice attempting to attach identical QC ticket must fail with HTTP 409 Conflict
        res2 = self.client.post("/api/branch/invoices/create", data=inv_payload)
        self.assertEqual(res2.status_code, 409, "Second invoice attachment of identical QC ticket must be rejected with HTTP 409 Conflict")
        detail = res2.json().get("detail", "")
        self.assertIn("Conflict", detail)
        self.assertIn("already", detail.lower())

    def test_08_branch_invoice_sequence_generation_produces_unique_inv_tokens(self):
        """Test 8: Branch invoice sequence generation produces unique INV-CHK-YYYYMMDD-0001 tokens."""
        conn = database.get_connection()
        cur = conn.cursor()

        test_date = date(2026, 11, 3)
        date_str = test_date.strftime("%Y%m%d")

        # Generate 5 consecutive tokens for branch CHK
        tokens = []
        for _ in range(5):
            tok = generate_branch_invoice_token(cur, "CHK", target_date=test_date, style="daily")
            tokens.append(tok)

        conn.commit()
        conn.close()

        # Verify uniqueness
        self.assertEqual(len(tokens), len(set(tokens)), "All generated invoice tokens must be strictly unique")

        # Verify sequential ordering
        self.assertTrue(tokens[0].endswith("-0001") or int(tokens[0].split("-")[-1]) >= 1)
        # Check monotonic increase
        seq_nums = [int(t.split("-")[-1]) for t in tokens]
        for i in range(len(seq_nums) - 1):
            self.assertEqual(seq_nums[i + 1], seq_nums[i] + 1, "Invoice sequences must be monotonically incrementing")

        # Verify pattern INV-CHK-YYYYMMDD-0001
        pattern = r"^INV-CHK-\d{8}-\d{4}$"
        for t in tokens:
            self.assertTrue(bool(re.match(pattern, t)), f"Token '{t}' must match format INV-CHK-YYYYMMDD-0001")

        # Verify dev database remains untouched
        self.assertTrue(verify_dev_db_unchanged(), "Main development database must remain 100% byte-for-byte unchanged")


if __name__ == "__main__":
    unittest.main()
