"""
Quality Assaying, Moisture Meter OCR, Varietal Breed Purity & QC Slip Tests.
Verifies end-to-end integration between Mobile Inspector Portal, Computer Vision Engine,
Cashier Inward Desk, and SQLite Database.
"""

import os
import sys
import io
import base64
import unittest
from PIL import Image
from fastapi.testclient import TestClient

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_support import setup_test_database
setup_test_database()

from server import app, create_session_token
from database import (
    get_connection,
    save_quality_inspection,
    get_pending_quality_inspections,
    get_quality_inspection_by_ticket,
    link_qc_to_invoice
)
from quality_engine import (
    read_moisture_meter_display,
    analyze_grain_sample_image,
    calculate_mandi_corridor_rate,
    generate_qc_ticket_number,
    format_qc_slip_text,
    detect_tray_and_warp,
    segment_individual_kernels,
    topological_7segment_ocr,
    enforce_moisture_feasibility,
    COMMODITY_STANDARDS
)


class TestQualityAssayingEngine(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        # Cashier session
        self.cashier_token = create_session_token("chikhali", "BRANCH_CASHIER", branch_id="br-chikhali", user_id="u-indore-cashier")
        self.client.cookies.set("mandi_session", self.cashier_token)

    def _create_dummy_image_bytes(self, color=(200, 180, 150), size=(320, 240)) -> bytes:
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    def _create_dummy_base64_image(self) -> str:
        raw = self._create_dummy_image_bytes()
        return "data:image/jpeg;base64," + base64.b64encode(raw).decode("utf-8")

    def test_moisture_meter_ocr_engine(self):
        """Tests digital LCD OCR reader for physical moisture meters."""
        dummy_lcd = self._create_dummy_image_bytes(color=(40, 45, 50))
        result = read_moisture_meter_display(dummy_lcd)
        self.assertIn("moisture_pct", result)
        self.assertGreaterEqual(result["moisture_pct"], 8.0)
        self.assertLessEqual(result["moisture_pct"], 20.0)
        self.assertGreater(result["confidence"], 0.7)

    def test_grain_cv_assaying_engine(self):
        """Tests physical refractions and varietal breed purity analysis."""
        dummy_grains = self._create_dummy_image_bytes(color=(215, 195, 160))
        analysis = analyze_grain_sample_image(dummy_grains, "Soyabean (Yellow)", measured_moisture=11.4)
        
        # Verify 8 mandatory parameters
        self.assertEqual(analysis["commodity_name"], "Soyabean (Yellow)")
        self.assertEqual(analysis["moisture_pct"], 11.4)
        self.assertIn("karda_pct", analysis)
        self.assertIn("damaged_pct", analysis)
        self.assertIn("green_seeds_pct", analysis)
        self.assertIn("broken_split_pct", analysis)
        self.assertIn("shriveled_pct", analysis)
        self.assertIn("uniformity_index", analysis)
        self.assertIn("dominant_breed", analysis)
        self.assertIn("breed_purity_pct", analysis)
        self.assertIn("breed_status", analysis)
        self.assertGreaterEqual(analysis["breed_purity_pct"], 50.0)

        # Verify new accuracy components
        self.assertIn("tray_homography_warp", analysis)
        self.assertTrue(analysis["tray_homography_warp"]["applied"])
        self.assertIn("instance_segmentation", analysis)
        self.assertIn("feasibility", analysis)

    def test_standardized_tray_homography_warp(self):
        """Tests ArUco/Quad corner fiducial detection and 4-point homography perspective warp."""
        dummy_tray = self._create_dummy_image_bytes(color=(190, 190, 190), size=(640, 480))
        warp_res = detect_tray_and_warp(dummy_tray, target_width=800, target_height=600)
        self.assertTrue(warp_res["success"])
        self.assertEqual(warp_res["warped_arr"].shape, (600, 800, 3))
        self.assertEqual(warp_res["mm_per_pixel"], 0.3)
        self.assertEqual(warp_res["tray_physical_width_mm"], 240.0)
        self.assertEqual(warp_res["tray_physical_height_mm"], 180.0)
        self.assertTrue(warp_res["optical_distortion_corrected"])

    def test_individual_kernel_watershed_segmentation(self):
        """Tests individual kernel instance segmentation via distance transform & watershed."""
        import numpy as np
        # Synthetic plate with 4 separated golden kernels
        arr = np.ones((600, 800, 3), dtype=np.uint8) * 190
        for y, x in [(100, 100), (150, 200), (300, 400), (450, 600)]:
            rr, cc = np.ogrid[:600, :800]
            arr[((rr - y)**2 + (cc - x)**2) <= 15**2] = [215, 185, 130]

        seg = segment_individual_kernels(arr, mm_per_pixel=0.3)
        self.assertGreaterEqual(seg["total_kernels_analyzed"], 4)
        self.assertIn("sound_kernels_count", seg)
        self.assertIn("green_seeds_pct", seg)
        self.assertIn("damaged_pct", seg)
        self.assertIn("uniformity_index", seg)

    def test_topological_7segment_lcd_ocr(self):
        """Tests 7-segment physical bar bitmask OCR and decimal point detection."""
        dummy_lcd = self._create_dummy_image_bytes(color=(40, 45, 50))
        res = topological_7segment_ocr(dummy_lcd)
        self.assertTrue(res["success"])
        self.assertIn("moisture_pct", res)
        self.assertTrue(res["topological_bitmask_verified"])
        self.assertIn("decimal_detected", res)
        self.assertTrue(res["feasibility"]["is_feasible"])

    def test_physical_moisture_feasibility_gating(self):
        """Tests Indian mandi physical moisture feasibility boundary gating (7.0% to 24.0%)."""
        # Valid moisture in mandi bounds
        valid_res = enforce_moisture_feasibility(11.4)
        self.assertTrue(valid_res["is_feasible"])
        self.assertFalse(valid_res["requires_rescan"])
        self.assertEqual(valid_res["status"], "FEASIBILITY_VERIFIED")
        self.assertEqual(valid_res["warning"], "")

        # Below physical bound (< 7.0%)
        too_low = enforce_moisture_feasibility(4.2)
        self.assertFalse(too_low["is_feasible"])
        self.assertTrue(too_low["requires_rescan"])
        self.assertEqual(too_low["status"], "FEASIBILITY_REJECTED")
        self.assertIn("outside Indian mandi physical limits", too_low["warning"])

        # Above physical bound (> 24.0%)
        too_high = enforce_moisture_feasibility(28.5)
        self.assertFalse(too_high["is_feasible"])
        self.assertTrue(too_high["requires_rescan"])
        self.assertEqual(too_high["status"], "FEASIBILITY_REJECTED")

    def test_corridor_rate_discovery_engine(self):
        """Tests statutory corridor pricing and APMC FAQ grading."""
        analysis = {
            "moisture_pct": 10.0,
            "karda_pct": 1.2,
            "damaged_pct": 1.5,
            "green_seeds_pct": 1.0,
            "broken_split_pct": 1.8,
            "shriveled_pct": 1.0,
            "uniformity_index": 95.0,
            "admixture_pct": 2.0
        }
        corridor = calculate_mandi_corridor_rate(
            commodity_name="Soyabean (Yellow)",
            analysis=analysis,
            min_rate=4400.0,
            target_rate=4650.0,
            max_rate=4800.0
        )
        self.assertEqual(corridor["faq_grade"], "FAQ_GRADE_1")
        self.assertGreaterEqual(corridor["suggested_buying_rate_per_qtl"], 4650.0)
        self.assertLessEqual(corridor["suggested_buying_rate_per_qtl"], 4800.0)

    def test_api_inspector_portal_page(self):
        """Tests that the Inspector Portal PWA enforces authentication and loads with inspector context."""
        # 1. Unauthenticated request redirects to /login
        unauth_client = TestClient(app)
        res_unauth = unauth_client.get("/inspector/portal", follow_redirects=False)
        self.assertEqual(res_unauth.status_code, 303)
        self.assertEqual(res_unauth.headers["location"], "/login")

        # 2. Authenticated QUALITY_INSPECTOR session loads portal with locked branch
        qc_token = create_session_token("qc_chikhali", "QUALITY_INSPECTOR", branch_id="br-chikhali", user_id="u-qc-chikhali")
        qc_client = TestClient(app)
        qc_client.cookies.set("mandi_session", qc_token)

        res = qc_client.get("/inspector/portal")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Mandi QC Assayer Mobile", res.text)
        self.assertIn("Farmer Details & Intake Lot", res.text)
        self.assertIn("Babulal Meena", res.text)
        self.assertIn("No Sign Required", res.text)
        self.assertNotIn("signaturePad", res.text)

    def test_inspector_login_redirect_flow(self):
        """Tests that logging in with qc_chikhali credentials automatically redirects to /inspector/portal."""
        login_client = TestClient(app)
        res = login_client.post("/login", data={
            "username": "qc_chikhali",
            "password": "qc123"
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/inspector/portal")

    def test_api_ocr_moisture_endpoint(self):
        """Tests POST /api/inspector/ocr-moisture endpoint."""
        dummy_bytes = self._create_dummy_image_bytes()
        files = {"meter_photo": ("meter.jpg", dummy_bytes, "image/jpeg")}
        res = self.client.post("/api/inspector/ocr-moisture", files=files)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("moisture_pct", data)
        self.assertTrue(data["meter_photo_url"].startswith("/static/uploads/qc/"))

    def test_api_analyze_sample_endpoint(self):
        """Tests POST /api/inspector/analyze-sample endpoint."""
        dummy_bytes = self._create_dummy_image_bytes()
        files = {"grain_photo": ("grain.jpg", dummy_bytes, "image/jpeg")}
        res = self.client.post("/api/inspector/analyze-sample", data={
            "commodity_name": "Soyabean (Yellow)",
            "moisture_pct": 11.2,
            "branch_id": "br-chikhali"
        }, files=files)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("analysis", data)
        self.assertIn("corridor", data)
        self.assertIn("suggested_buying_rate_per_qtl", data["corridor"])

    def test_end_to_end_qc_ticket_and_cashier_link(self):
        """
        Tests complete handoff:
          1. Inspector enters farmer name at start and signs.
          2. Inspector records moisture OCR & grain assaying.
          3. System issues QC ticket and generates 80mm slip.
          4. Cashier views pending tickets, checks inspector sign and photos.
          5. Cashier creates inward invoice linking ticket.
          6. Ticket status transitions to LINKED in database.
        """
        dummy_b64 = self._create_dummy_base64_image()

        # 1 & 2 & 3. Inspector Submits QC Ticket
        submit_res = self.client.post("/api/inspector/submit-qc", data={
            "branch_id": "br-chikhali",
            "farmer_name": "Devidas Patil",
            "farmer_phone": "9827099999",
            "vehicle_no": "MH-28-V-8821",
            "commodity_name": "Soyabean (Yellow)",
            "inspector_name": "Babulal Meena",
            "inspector_signature": "",
            "moisture_pct": 11.2,
            "karda_pct": 1.1,
            "damaged_pct": 1.4,
            "green_seeds_pct": 1.0,
            "broken_split_pct": 1.5,
            "shriveled_pct": 1.0,
            "uniformity_index": 94.0,
            "dominant_breed": "JS-335 (Standard Commercial Bold)",
            "breed_purity_pct": 95.0,
            "admixture_pct": 5.0,
            "breed_status": "PURE_BREED (Pure Lot)",
            "faq_grade": "FAQ_GRADE_1",
            "grade_label": "Grade 1 (Premium FAQ)",
            "suggested_rate_cut_per_qtl": 0.0,
            "corridor_min_rate": 4400.0,
            "corridor_target_rate": 4650.0,
            "corridor_max_rate": 4800.0,
            "suggested_buying_rate_per_qtl": 4700.0,
            "meter_photo_path": dummy_b64,
            "grain_photo_path": dummy_b64,
            "inspection_notes": "Sample inspected in sunlight tray. Pure bold JS-335."
        })
        self.assertEqual(submit_res.status_code, 200)
        submit_data = submit_res.json()
        self.assertTrue(submit_data["success"])
        ticket = submit_data["ticket"]
        ticket_no = ticket["ticket_no"]
        self.assertTrue(ticket_no.startswith("QC-"))
        self.assertEqual(ticket["farmer_name"], "Devidas Patil")
        self.assertEqual(ticket["vehicle_no"], "MH-28-V-8821")
        self.assertEqual(ticket["status"], "PENDING")
        self.assertFalse(ticket.get("inspector_signature"))

        # Check slip text
        slip_text = submit_data["slip_text"]
        self.assertIn("APMC YARD QUALITY ASSAYING CERTIFICATE", slip_text)
        self.assertIn(ticket_no, slip_text)
        self.assertIn("Devidas Patil", slip_text)
        self.assertIn("Babulal Meena", slip_text)

        # 4. Cashier views pending tickets
        pending_res = self.client.get("/api/inspector/tickets/pending?branch_id=br-chikhali")
        self.assertEqual(pending_res.status_code, 200)
        pending_data = pending_res.json()
        self.assertTrue(pending_data["success"])
        tickets_list = [t["ticket_no"] for t in pending_data["tickets"]]
        self.assertIn(ticket_no, tickets_list)

        # Cashier inspects specific ticket details & photos
        detail_res = self.client.get(f"/api/inspector/tickets/{ticket_no}")
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.json()
        self.assertTrue(detail_data["success"])
        self.assertEqual(detail_data["ticket"]["farmer_name"], "Devidas Patil")
        self.assertEqual(detail_data["ticket"]["inspector_name"], "Babulal Meena")

        # Cashier opens printable report
        report_res = self.client.get(f"/inspector/report/{ticket_no}")
        self.assertEqual(report_res.status_code, 200)
        self.assertIn("APMC Yard Quality Assaying Certificate", report_res.text)
        self.assertIn(ticket_no, report_res.text)
        self.assertIn("Devidas Patil", report_res.text)

        # 5. Cashier creates inward invoice and links the QC ticket
        inv_res = self.client.post("/api/branch/invoices/create", data={
            "branch_id": "br-chikhali",
            "party_id": "p-farmer-1",
            "inspector_name": "Babulal Meena",
            "commodity_name": "Soyabean (Yellow)",
            "rate_per_quintal": 4700.0,
            "weighment_mode": "MANUAL_YARD",
            "yard_weight_kg": 3000.0,
            "vehicle_number": "MH-28-V-8821",
            "moisture_percentage": 11.2,
            "karda_percentage": 1.1,
            "settlement_mode": "PENDING",
            "qc_ticket_no": ticket_no,
            "dominant_breed": "JS-335 (Standard Commercial Bold)",
            "breed_purity_pct": 95.0
        })
        self.assertEqual(inv_res.status_code, 200)
        inv_data = inv_res.json()
        self.assertTrue(inv_data["success"])
        invoice_id = inv_data["invoice_id"]
        self.assertEqual(inv_data["qc_ticket_no"], ticket_no)

        # 6. Verify Database State: ticket is now LINKED to the invoice
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT status, invoice_id FROM quality_inspections WHERE ticket_no=?", (ticket_no,))
        updated_qc = cur.fetchone()
        conn.close()

        self.assertEqual(updated_qc["status"], "LINKED")
        self.assertEqual(updated_qc["invoice_id"], invoice_id)

        # Ticket should no longer appear in pending tickets list
        pending_after = self.client.get("/api/inspector/tickets/pending?branch_id=br-chikhali").json()
        self.assertNotIn(ticket_no, [t["ticket_no"] for t in pending_after["tickets"]])

        # 7. Super Admin Cloud Audit Desk verification
        admin_client = TestClient(app)
        admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        admin_client.cookies.set("mandi_session", admin_token)

        admin_dashboard_res = admin_client.get("/admin/dashboard")
        self.assertEqual(admin_dashboard_res.status_code, 200)
        self.assertIn("All-Branch Quality Assaying & Visual Evidence Audit", admin_dashboard_res.text)
        self.assertIn(ticket_no, admin_dashboard_res.text)
        self.assertIn("Devidas Patil", admin_dashboard_res.text)

        admin_api_res = admin_client.get("/api/admin/inspections")
        self.assertEqual(admin_api_res.status_code, 200)
        admin_api_data = admin_api_res.json()
        self.assertTrue(admin_api_data["success"])
        self.assertGreater(admin_api_data["count"], 0)
        all_admin_tickets = [q["ticket_no"] for q in admin_api_data["inspections"]]
        self.assertIn(ticket_no, all_admin_tickets)

    def test_security_headers_middleware(self):
        """Verifies OWASP recommended security headers are injected in HTTP responses."""
        res = self.client.get("/login")
        self.assertEqual(res.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(res.headers.get("x-frame-options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("x-xss-protection"), "1; mode=block")
        self.assertEqual(res.headers.get("referrer-policy"), "strict-origin-when-cross-origin")

    def test_inspector_api_auth_and_rbac(self):
        """Verifies that inspector endpoints reject unauthenticated or non-staff requests."""
        unauth_client = TestClient(app)
        res = unauth_client.get("/api/inspector/tickets/pending")
        self.assertEqual(res.status_code, 401)

        unauth_submit = unauth_client.post("/api/inspector/submit-qc", data={
            "branch_id": "br-chikhali",
            "farmer_name": "Unauthorized Test",
            "vehicle_no": "MH-28-9999",
            "commodity_name": "Soyabean (Yellow)"
        })
        self.assertEqual(unauth_submit.status_code, 401)

    def test_invalid_image_upload_sanitization(self):
        """Verifies that corrupted image payloads or non-image files are rejected by save_qc_image_data."""
        from server import save_qc_image_data
        url, raw = save_qc_image_data(b"not_a_valid_jpeg_or_png_file", prefix="test")
        self.assertEqual(url, "")
        self.assertEqual(raw, b"")

        # Huge file (>10MB) must also be rejected
        huge_bytes = b"0" * (11 * 1024 * 1024)
        url_huge, raw_huge = save_qc_image_data(huge_bytes, prefix="test")
        self.assertEqual(url_huge, "")
        self.assertEqual(raw_huge, b"")

    def test_login_rate_limiting(self):
        """Verifies that consecutive failed login attempts trigger HTTP 429 lockout."""
        client = TestClient(app)
        # 5 failed attempts
        for i in range(5):
            r = client.post("/login", data={"username": "lockout_test_user", "password": "wrongpassword"})
            self.assertEqual(r.status_code, 401)
        # 6th attempt should be blocked with 429 Too Many Requests
        r_blocked = client.post("/login", data={"username": "lockout_test_user", "password": "wrongpassword"})
        self.assertEqual(r_blocked.status_code, 429)
        self.assertIn("temporarily locked", r_blocked.text)

    def test_multi_inspector_branch_isolation_and_admin_creation(self):
        """
        Verifies:
        1. Admin can create new Quality Inspectors with separate logins and branch assignments.
        2. Direct /inspector route redirects to the mobile Inspector App.
        3. Inspectors are strictly segregated: cannot switch branches, cannot spoof identity,
           and cannot access another branch's QC tickets or printable reports.
        """
        # 1. Super Admin creates a second inspector for Chikhali
        admin_client = TestClient(app)
        admin_token = create_session_token("admin", "SUPER_ADMIN", user_id="u-admin")
        admin_client.cookies.set("mandi_session", admin_token)

        create_res = admin_client.post("/api/admin/users", data={
            "username": "qc_sanjay_chikhali",
            "full_name": "Sanjay Rao (Inspector 2)",
            "phone": "9822001122",
            "role": "QUALITY_INSPECTOR",
            "password": "sanjaypass123",
            "branch_id": "br-chikhali"
        }, follow_redirects=False)
        self.assertEqual(create_res.status_code, 303)

        # 2. Inspector logs in with their own separate credentials
        sanjay_client = TestClient(app)
        login_res = sanjay_client.post("/login", data={
            "username": "qc_sanjay_chikhali",
            "password": "sanjaypass123"
        }, follow_redirects=False)
        self.assertEqual(login_res.status_code, 303)
        self.assertEqual(login_res.headers["location"], "/inspector/portal")

        # 3. Direct /inspector shortcut redirects to /inspector/portal
        shortcut_res = sanjay_client.get("/inspector", follow_redirects=False)
        self.assertEqual(shortcut_res.status_code, 303)
        self.assertEqual(shortcut_res.headers["location"], "/inspector/portal")

        # 4. Attempt branch tampering: inspector tries to open /inspector/portal?branch_id=br-dhad
        tamper_res = sanjay_client.get("/inspector/portal?branch_id=br-dhad", follow_redirects=False)
        self.assertEqual(tamper_res.status_code, 303)
        self.assertEqual(tamper_res.headers["location"], "/inspector/portal?branch_id=br-chikhali")

        portal_res = sanjay_client.get("/inspector/portal?branch_id=br-dhad")
        self.assertEqual(portal_res.status_code, 200)
        # Must enforce Chikhali branch, NOT Dhad
        self.assertIn("Chikhali Branch", portal_res.text)
        self.assertIn("Sanjay Rao (Inspector 2)", portal_res.text)
        self.assertIn("Locked by Accountant", portal_res.text)
        # Cannot navigate or switch to other branches (no selector dropdown for non-admin)
        self.assertNotIn('<select id="branchSelector"', portal_res.text)

        # 5. Sanjay submits a lot: even if someone tampers payload to br-dhad, backend locks to br-chikhali
        dummy_img = self._create_dummy_base64_image()
        sub_res = sanjay_client.post("/api/inspector/submit-qc", data={
            "branch_id": "br-dhad",  # Tampered branch_id
            "farmer_name": "Rameshwar Gite",
            "vehicle_no": "MH-28-AB-1234",
            "commodity_name": "Soyabean (Yellow)",
            "moisture_pct": 10.5,
            "meter_photo_path": dummy_img,
            "grain_photo_path": dummy_img
        })
        self.assertEqual(sub_res.status_code, 200)
        ticket_data = sub_res.json()["ticket"]
        chikhali_ticket_no = ticket_data["ticket_no"]
        self.assertEqual(ticket_data["branch_id"], "br-chikhali")
        self.assertEqual(ticket_data["inspector_name"], "Sanjay Rao (Inspector 2)")

        # 6. Dhad Inspector (separate login) cannot access Chikhali Inspector's tickets
        dhad_client = TestClient(app)
        dhad_token = create_session_token("qc_dhad", "QUALITY_INSPECTOR", branch_id="br-dhad", user_id="u-qc-dhad")
        dhad_client.cookies.set("mandi_session", dhad_token)

        # Pending tickets for Dhad inspector must not leak Chikhali ticket
        dhad_pending = dhad_client.get("/api/inspector/tickets/pending").json()
        self.assertNotIn(chikhali_ticket_no, [t["ticket_no"] for t in dhad_pending["tickets"]])

        # Direct ticket detail attempt across branch boundary must fail closed with 403 Forbidden
        dhad_detail = dhad_client.get(f"/api/inspector/tickets/{chikhali_ticket_no}")
        self.assertEqual(dhad_detail.status_code, 403)
        self.assertIn("cannot access quality inspections from other branches", dhad_detail.json()["detail"])

        # Direct printable report attempt across branch boundary must fail closed with 403 Forbidden
        dhad_report = dhad_client.get(f"/inspector/report/{chikhali_ticket_no}")
        self.assertEqual(dhad_report.status_code, 403)

    def test_accountant_qc_creation_branch_lock_and_password_lifecycle(self):
        """
        Verifies:
        1. Accountant HQ can create Quality Inspectors with mandatory branch assignment,
           unique username, and initial password.
        2. Omitting branch_id returns 400 (Accountant must assign branch).
        3. Multiple inspectors for the same branch (e.g. Chikhali) have distinct usernames
           and passwords for individual accountability.
        4. Accountant can edit inspector details and reset their password.
        5. Inspector logs in, cannot select branch, and changes their password via self-service.
        6. Incorrect current password rejected with 400; new password works on next login.
        """
        # 1. Accountant creates Inspector 1 for Chikhali
        accountant_client = TestClient(app)
        acc_token = create_session_token("accountant", "ACCOUNTANT_HQ", user_id="u-accountant")
        accountant_client.cookies.set("mandi_session", acc_token)

        # 2. Attempt to create without branch must fail
        no_branch_res = accountant_client.post("/api/accounts/inspectors", data={
            "name": "Arun Patil",
            "designation": "Assayer",
            "phone": "9811122233",
            "username": "qc_arun_fail",
            "password": "password123",
            "branch_id": ""
        })
        self.assertEqual(no_branch_res.status_code, 400)
        self.assertIn("Branch assignment is mandatory", no_branch_res.text)

        # 3. Create Arun for Chikhali
        create_arun = accountant_client.post("/api/accounts/inspectors", data={
            "name": "Arun Patil",
            "designation": "Chief Assayer",
            "phone": "9811122233",
            "username": "qc_arun_chk",
            "password": "aruninitial123",
            "branch_id": "br-chikhali"
        }, follow_redirects=False)
        self.assertEqual(create_arun.status_code, 303)

        # 4. Create second inspector (Kavita) for the same branch (Chikhali) with distinct credentials
        create_kavita = accountant_client.post("/api/accounts/inspectors", data={
            "name": "Kavita Shinde",
            "designation": "Junior Assayer",
            "phone": "9822233344",
            "username": "qc_kavita_chk",
            "password": "kavitainitial123",
            "branch_id": "br-chikhali"
        }, follow_redirects=False)
        self.assertEqual(create_kavita.status_code, 303)

        # 5. Duplicate username must fail
        dup_user = accountant_client.post("/api/accounts/inspectors", data={
            "name": "Another Person",
            "designation": "Assayer",
            "phone": "9833344455",
            "username": "qc_arun_chk",
            "password": "somepass123",
            "branch_id": "br-chikhali"
        })
        self.assertEqual(dup_user.status_code, 400)
        self.assertIn("already exists", dup_user.text)

        # 6. Verify both appear in Accountant Dashboard inspectors listing
        acc_dash = accountant_client.get("/accounts/dashboard")
        self.assertEqual(acc_dash.status_code, 200)
        self.assertIn("Arun Patil", acc_dash.text)
        self.assertIn("qc_arun_chk", acc_dash.text)
        self.assertIn("Kavita Shinde", acc_dash.text)
        self.assertIn("qc_kavita_chk", acc_dash.text)

        # 7. Accountant edits Kavita's details and resets password
        # First get Kavita's user id from database
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username='qc_kavita_chk'")
            kavita_id = cur.fetchone()[0]
        finally:
            conn.close()

        update_res = accountant_client.post("/api/accounts/inspectors/update", data={
            "inspector_id": kavita_id,
            "name": "Kavita Shinde-Patil",
            "designation": "Senior Assayer",
            "phone": "9822299999",
            "branch_id": "br-chikhali",
            "username": "qc_kavita_chk",
            "new_password": "kavitareset456"
        }, follow_redirects=False)
        self.assertEqual(update_res.status_code, 303)

        # 8. Kavita logs in with new password
        kavita_client = TestClient(app)
        kavita_login = kavita_client.post("/login", data={
            "username": "qc_kavita_chk",
            "password": "kavitareset456"
        }, follow_redirects=False)
        self.assertEqual(kavita_login.status_code, 303)
        self.assertEqual(kavita_login.headers["location"], "/inspector/portal")

        # 9. Kavita views portal: branch is locked to Chikhali, no branch selector
        portal_res = kavita_client.get("/inspector/portal")
        self.assertEqual(portal_res.status_code, 200)
        self.assertIn("Chikhali Branch", portal_res.text)
        self.assertIn("Kavita Shinde-Patil", portal_res.text)
        self.assertIn("Locked by Accountant", portal_res.text)
        self.assertNotIn('<select id="branchSelector"', portal_res.text)

        # 10. Kavita changes password via self-service:
        # 10a. Wrong current password -> 400
        bad_pw_res = kavita_client.post("/api/inspector/change-password", data={
            "current_password": "wrongpassword",
            "new_password": "kavitafinal789",
            "confirm_password": "kavitafinal789"
        })
        self.assertEqual(bad_pw_res.status_code, 400)
        self.assertIn("Current password entered is incorrect", bad_pw_res.json()["detail"])

        # 10b. Mismatching confirmation -> 400
        mismatch_res = kavita_client.post("/api/inspector/change-password", data={
            "current_password": "kavitareset456",
            "new_password": "kavitafinal789",
            "confirm_password": "mismatchpass"
        })
        self.assertEqual(mismatch_res.status_code, 400)
        self.assertIn("do not match", mismatch_res.json()["detail"])

        # 10c. Successful password change
        good_pw_res = kavita_client.post("/api/inspector/change-password", data={
            "current_password": "kavitareset456",
            "new_password": "kavitafinal789",
            "confirm_password": "kavitafinal789"
        })
        self.assertEqual(good_pw_res.status_code, 200)
        self.assertTrue(good_pw_res.json()["success"])

        # 11. Verify Kavita can log in with new password and old password fails
        kavita_client2 = TestClient(app)
        old_login = kavita_client2.post("/login", data={
            "username": "qc_kavita_chk",
            "password": "kavitareset456"
        })
        self.assertEqual(old_login.status_code, 401)

        new_login = kavita_client2.post("/login", data={
            "username": "qc_kavita_chk",
            "password": "kavitafinal789"
        }, follow_redirects=False)
        self.assertEqual(new_login.status_code, 303)
        self.assertEqual(new_login.headers["location"], "/inspector/portal")

    def test_branch_dashboard_review_verify_and_auto_fill_inward_invoice(self):
        """
        Verifies:
        1. Inspector issues QC ticket with farmer name, vehicle number, moisture, breed and rate.
        2. Branch Cashier accesses branch dashboard and retrieves pending QC tickets.
        3. Review & Verify loads ticket proof details.
        4. Inward weighment invoice is created with QC ticket number, dominant breed, purity, and karda.
        5. SQLite updates quality_inspections status to 'LINKED' and attaches invoice_id.
        6. Ticket no longer appears in pending QC tickets list.
        """
        # 1. Inspector issues QC ticket
        qc_client = TestClient(app)
        qc_token = create_session_token("qc_chikhali", "QUALITY_INSPECTOR", branch_id="br-chikhali", user_id="u-qc-chikhali")
        qc_client.cookies.set("mandi_session", qc_token)

        dummy_img = self._create_dummy_base64_image()
        qc_submit = qc_client.post("/api/inspector/submit-qc", data={
            "branch_id": "br-chikhali",
            "farmer_name": "Sitaram Yadav",
            "farmer_phone": "9826012345",
            "vehicle_no": "MH-28-ST-7788",
            "commodity_name": "Soyabean (Yellow)",
            "moisture_pct": 11.2,
            "karda_pct": 1.5,
            "suggested_buying_rate_per_qtl": 4750.0,
            "dominant_breed": "JS-335",
            "breed_purity_pct": 98.0,
            "meter_photo_path": dummy_img,
            "grain_photo_path": dummy_img
        })
        self.assertEqual(qc_submit.status_code, 200)
        qc_data = qc_submit.json()["ticket"]
        ticket_no = qc_data["ticket_no"]

        # 2. Cashier queries pending QC tickets for branch
        cashier_client = TestClient(app)
        cashier_token = create_session_token("chikhali", "BRANCH_CASHIER", branch_id="br-chikhali", user_id="u-indore-cashier")
        cashier_client.cookies.set("mandi_session", cashier_token)

        pending_res = cashier_client.get("/api/inspector/tickets/pending")
        self.assertEqual(pending_res.status_code, 200)
        tickets = pending_res.json()["tickets"]
        matched_ticket = next((t for t in tickets if t["ticket_no"] == ticket_no), None)
        self.assertIsNotNone(matched_ticket)
        self.assertEqual(matched_ticket["farmer_name"], "Sitaram Yadav")
        self.assertEqual(matched_ticket["vehicle_no"], "MH-28-ST-7788")
        self.assertEqual(matched_ticket["moisture_pct"], 11.2)
        self.assertEqual(matched_ticket["suggested_buying_rate_per_qtl"], 4750.0)

        # 3. Cashier verifies ticket details endpoint
        detail_res = cashier_client.get(f"/api/inspector/tickets/{ticket_no}")
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.json()["ticket"]
        self.assertEqual(detail_data["ticket_no"], ticket_no)
        self.assertEqual(detail_data["dominant_breed"], "JS-335")

        # 4. Cashier submits inward invoice using auto-filled QC details
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM parties WHERE name='Sitaram Yadav' LIMIT 1")
            p_row = cur.fetchone()
            if p_row:
                party_id = p_row[0]
            else:
                party_id = f"p-{ticket_no.split('-')[-1]}"
                cur.execute("INSERT INTO parties (id, home_branch_id, name, phone, party_type, village, khasra_record_no) VALUES (?, 'br-chikhali', 'Sitaram Yadav', '9826012345', 'FARMER', 'Chikhali', 'KH-7788')", (party_id,))
                conn.commit()
        finally:
            conn.close()

        inv_res = cashier_client.post("/api/branch/invoices/create", data={
            "branch_id": "br-chikhali",
            "party_id": party_id,
            "inspector_name": "Babulal Meena",
            "commodity_name": "Soyabean (Yellow)",
            "rate_per_quintal": 4750.0,
            "weighment_mode": "MANUAL_YARD",
            "yard_weight_kg": 3000.0,
            "vehicle_number": "MH-28-ST-7788",
            "moisture_percentage": 11.2,
            "karda_percentage": 1.5,
            "settlement_mode": "CASH",
            "notes_500": 200,
            "qc_ticket_no": ticket_no,
            "dominant_breed": "JS-335",
            "breed_purity_pct": 98.0
        })
        self.assertEqual(inv_res.status_code, 200)
        inv_data = inv_res.json()
        self.assertTrue(inv_data["success"])

        # 5. Verify SQLite updated ticket status to 'LINKED'
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT status, invoice_id FROM quality_inspections WHERE ticket_no=?", (ticket_no,))
            t_row = cur.fetchone()
            self.assertEqual(t_row[0], "LINKED")
            self.assertIsNotNone(t_row[1])
        finally:
            conn.close()

        # 6. Ticket no longer in pending list
        pending_after = cashier_client.get("/api/inspector/tickets/pending").json()["tickets"]
        self.assertNotIn(ticket_no, [t["ticket_no"] for t in pending_after])


if __name__ == "__main__":
    unittest.main()
