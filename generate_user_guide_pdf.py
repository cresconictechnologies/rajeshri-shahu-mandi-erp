"""
Generate Comprehensive User Guide & SOP Manual PDF for Rajeshri Shahu Mandi ERP.
Uses Playwright Chromium to render a professional A4 multi-page manual with
embedded real software photos, diagrams, callouts, and step-by-step procedures.
"""

import os
import base64
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "dist", "doc_assets")
BRAIN_DIR = r"C:\Users\visha\.gemini\antigravity\brain\c36662ec-04b6-4f82-a5b5-3dc06da8f2a3"
OUTPUT_PDF = os.path.join(BASE_DIR, "dist", "Rajeshri_Shahu_Mandi_ERP_User_Guide.pdf")
TRACKER_COPY = os.path.join(os.path.dirname(BASE_DIR), "mandi-erp-tracker", "Rajeshri_Shahu_Mandi_ERP_User_Guide.pdf")

def get_b64(filepath):
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return ""

img_tracker = get_b64(os.path.join(ASSETS_DIR, "01_tracker_portal.png"))
img_captain = get_b64(os.path.join(ASSETS_DIR, "02_captain_tablet_app.png"))
img_branch = get_b64(os.path.join(ASSETS_DIR, "03_branch_cashier_desk.png"))
img_admin = get_b64(os.path.join(ASSETS_DIR, "05_super_admin_desk.png"))
img_qc = get_b64(os.path.join(ASSETS_DIR, "06_inspector_qc_portal.png"))
img_outward = get_b64(os.path.join(BRAIN_DIR, "outward_receive_payment_modal.png"))
img_rtgs = get_b64(os.path.join(BRAIN_DIR, "branch_rtgs_status.png"))

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Rajeshri Shahu Mandi ERP — Standard Operating Procedure & User Manual</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

        @page {{
            size: A4 portrait;
            margin: 20mm 18mm 20mm 18mm;
            @bottom-right {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                font-family: 'Plus Jakarta Sans', sans-serif;
                color: #64748b;
            }}
            @bottom-left {{
                content: "Rajeshri Shahu Mandi ERP v2.6.0 • Official User Manual";
                font-size: 9pt;
                font-family: 'Plus Jakarta Sans', sans-serif;
                color: #64748b;
            }}
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
            background: #ffffff;
            color: #0f172a;
            font-size: 10pt;
            line-height: 1.55;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}

        .page-break {{
            page-break-before: always;
        }}

        /* Document Header */
        .doc-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 2px solid #059669;
            padding-bottom: 12px;
            margin-bottom: 24px;
        }}
        .brand-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 18pt;
            font-weight: 800;
            color: #065f46;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .version-badge {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 8.5pt;
            font-weight: 700;
            background: #ecfdf5;
            color: #047857;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid #a7f3d0;
        }}

        /* Section Headings */
        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 20pt;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 12px;
        }}
        h2 {{
            font-family: 'Outfit', sans-serif;
            font-size: 14pt;
            font-weight: 700;
            color: #065f46;
            margin-top: 18px;
            margin-bottom: 8px;
            border-bottom: 1.5px solid #e2e8f0;
            padding-bottom: 4px;
        }}
        h3 {{
            font-family: 'Outfit', sans-serif;
            font-size: 11pt;
            font-weight: 700;
            color: #1e293b;
            margin-top: 12px;
            margin-bottom: 4px;
        }}

        p {{
            margin-bottom: 10px;
            color: #334155;
        }}

        /* Callout Boxes */
        .callout {{
            background: #f8fafc;
            border-left: 4px solid #059669;
            padding: 10px 14px;
            border-radius: 0 8px 8px 0;
            margin: 12px 0;
            font-size: 9.5pt;
        }}
        .callout-amber {{
            background: #fffbeb;
            border-left-color: #d97706;
            color: #92400e;
        }}
        .callout-title {{
            font-weight: 700;
            margin-bottom: 3px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 12px 0 16px 0;
            font-size: 9pt;
        }}
        th, td {{
            padding: 7px 10px;
            border: 1px solid #e2e8f0;
            text-align: left;
        }}
        th {{
            background: #f1f5f9;
            font-weight: 700;
            color: #0f172a;
        }}
        tr:nth-child(even) {{
            background: #f8fafc;
        }}

        /* Step List */
        .step-box {{
            display: flex;
            gap: 12px;
            margin-bottom: 12px;
            align-items: flex-start;
        }}
        .step-num {{
            width: 26px;
            height: 26px;
            border-radius: 50%;
            background: #059669;
            color: #ffffff;
            font-weight: 800;
            font-size: 9pt;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            margin-top: 2px;
        }}
        .step-content {{
            flex: 1;
        }}

        /* Image Display */
        .doc-img {{
            width: 100%;
            max-height: 200px;
            object-fit: cover;
            border: 1.5px solid #cbd5e1;
            border-radius: 8px;
            margin: 8px 0 14px 0;
            display: block;
        }}
        .caption {{
            font-size: 8pt;
            color: #64748b;
            text-align: center;
            margin-top: -8px;
            margin-bottom: 12px;
            font-style: italic;
        }}

        /* Code & Monospace */
        code {{
            font-family: 'JetBrains Mono', monospace;
            background: #f1f5f9;
            color: #0f172a;
            padding: 1px 4px;
            border-radius: 4px;
            font-size: 8.5pt;
        }}
    </style>
</head>
<body>

    <!-- =================================================================== -->
    <!-- SECTION 1: COVER & SYSTEM ARCHITECTURE -->
    <!-- =================================================================== -->
    <div class="doc-header">
        <div class="brand-title">
            <span>🌾</span> Rajeshri Shahu Trading Co.
        </div>
        <div class="version-badge">Production v2.6.0 • User Manual</div>
    </div>

    <h1>APMC Mandi ERP & AI Grain Assaying System</h1>
    <p style="font-size: 11pt; color: #475569; margin-bottom: 18px;">
        Standard Operating Procedure (SOP) & Operator Manual for Quality Inspectors, Weighbridge Operators, Branch Cashiers, Munims, and Central HQ Accountants.
    </p>

    <div class="callout">
        <div class="callout-title">🏛️ APMC Mandi Deregulation & Statutory Guarantees</div>
        <strong>Zero Mandi Cess (0.0%):</strong> Hardcoded across all inward purchase bills, trader sales orders, and accounting ledgers in compliance with modern APMC market deregulation.<br>
        <strong>Income Tax Section 269ST:</strong> Automated daily cash limit of ₹2,00,000 per farmer. Transactions meeting or exceeding this threshold are locked to RTGS/NEFT with mandatory Bank UTR recording, protecting trading firms from Section 271DA 100% penalties.
    </div>

    <h2>1. System Architecture & Role Topology</h2>
    <p>
        Rajeshri Shahu Mandi ERP operates on a 3-tier multi-branch topology connecting 3 active APMC market yards (<strong>Chikhali</strong>, <strong>Varvand</strong>, and <strong>Dhad</strong>) to a centralized HQ Audit Desk.
    </p>

    <table>
        <thead>
            <tr>
                <th>User Role</th>
                <th>Assigned System Surface</th>
                <th>Core Responsibilities</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Quality Inspector</strong></td>
                <td>Handheld Captain Tablet (`/app`)</td>
                <td>Sample photography, ArUco tray homography, 7-segment moisture OCR, and thermal slip printing.</td>
            </tr>
            <tr>
                <td><strong>Branch Cashier</strong></td>
                <td>Inward Weighbridge Desk (`/branch/dashboard`)</td>
                <td>Dharamkanta weighment, QC ticket linking, Section 269ST cash compliance, and farmer settlement.</td>
            </tr>
            <tr>
                <td><strong>Branch Munim</strong></td>
                <td>Stock Register & Outward Desk</td>
                <td>Commodity inventory tracking, vehicle dispatch, trader outward invoicing, and payment receipts.</td>
            </tr>
            <tr>
                <td><strong>HQ Accountant</strong></td>
                <td>Central Accountant Desk (`/accountant/dashboard`)</td>
                <td>Multi-branch ledger consolidation, RTGS payout clearance, and inspector yard assignments.</td>
            </tr>
            <tr>
                <td><strong>Super Admin</strong></td>
                <td>Central Cloud Governance (`/admin/dashboard`)</td>
                <td>Hardware-bound RSA-PSS 2048 licensing, daily mandi rate corridor discovery, and security audits.</td>
            </tr>
        </tbody>
    </table>

    <img src="data:image/png;base64,{img_tracker}" class="doc-img" alt="Public Tracker & Release Portal">
    <div class="caption">Figure 1.1: Live Mandi ERP Production Tracker & Telemetry Portal (https://mandi-erp-tracker.vercel.app)</div>

    <!-- =================================================================== -->
    <!-- SECTION 2: QUALITY INSPECTOR SOP (CAPTAIN TABLET) -->
    <!-- =================================================================== -->
    <div class="page-break"></div>

    <h2>2. Quality Inspector SOP (Captain Tablet App)</h2>
    <p>
        The Inspector Assaying Terminal is designed as a standalone handheld tablet and phone application, functioning like a restaurant captain order device for fast, single-purpose yard operation.
    </p>

    <img src="data:image/png;base64,{img_captain}" class="doc-img" style="max-height: 240px; object-fit: contain;" alt="Captain Handheld Tablet Terminal">
    <div class="caption">Figure 2.1: Handheld Captain Tablet Terminal UI (https://mandi-erp-tracker.vercel.app/app)</div>

    <h3>Step-by-Step Assaying Procedure:</h3>

    <div class="step-box">
        <div class="step-num">1</div>
        <div class="step-content">
            <strong>Inward Farmer & Vehicle Identification:</strong>
            Enter the Farmer Full Name (e.g. <code>Rameshwar Patil</code>), Vehicle Number (e.g. <code>MH-28-AB-1234</code>), and select the target commodity (Soyabean, Wheat, Chana, Tur, Cotton, or Maize).
        </div>
    </div>

    <div class="step-box">
        <div class="step-num">2</div>
        <div class="step-content">
            <strong>Moisture Meter Scanning (Topological 7-Segment OCR):</strong>
            Point camera at the digital display of the physical grain moisture tester (e.g., Indosaw, Kett, or Seedburo). Tap <strong>"Scan LCD"</strong>. The engine evaluates 7 physical bar bitmasks and searches the bottom quadrant for the decimal point.
            <div class="callout callout-amber" style="margin-top: 6px;">
                <strong>Physical Feasibility Gating:</strong> Indian mandi moisture must strictly be between <strong>7.0% and 24.0%</strong>. Any reading outside this range triggers an automated re-scan prompt.
            </div>
        </div>
    </div>

    <div class="step-box">
        <div class="step-num">3</div>
        <div class="step-content">
            <strong>Assaying Tray Capture (ArUco Homography & Watershed):</strong>
            Pour the 250g sample into the standardized 240mm × 180mm matte-grey assaying tray. Tap <strong>"Capture Tray & Run Assaying"</strong>. The engine automatically flattens camera tilt via the 4 ArUco corner fiducials and segments each touching grain into isolated Watershed polygon contours, computing:
            <ul style="padding-left: 18px; margin-top: 4px; font-size: 9pt;">
                <li>Foreign Matter / Karda % (Soil, stones, sand particles)</li>
                <li>Rain & Weather Damaged % (Fungal necrosis & mold stains)</li>
                <li>Immature Green Seeds % (Chlorophyll excess)</li>
                <li>Broken & Split Dal % (Fracture edge contrast & aspect ratio)</li>
                <li>Size Uniformity Index & Varietal Breed Purity score</li>
            </ul>
        </div>
    </div>

    <div class="step-box">
        <div class="step-num">4</div>
        <div class="step-content">
            <strong>Corridor Rate Discovery & Printable Slip Issuance:</strong>
            The system compares refractions against today's live Mandi Buying Rate Corridor and assigns Grade 1 (Premium FAQ), Grade 2 (Standard FAQ), or Grade 3 (Non-FAQ). Tap <strong>"Print 80mm Slip"</strong> for the thermal receipt, and tap <strong>"Sync to Weighbridge"</strong> to transmit data to the cashier desk.
        </div>
    </div>

    <!-- =================================================================== -->
    <!-- SECTION 3: WEIGHBRIDGE & CASHIER DESK SOP -->
    <!-- =================================================================== -->
    <div class="page-break"></div>

    <h2>3. Weighbridge Operator & Cashier Desk SOP</h2>
    <p>
        The Branch Cashier operates the primary inward desk (`/branch/dashboard`), executing vehicle weighments and farmer payment settlements.
    </p>

    <img src="data:image/png;base64,{img_branch}" class="doc-img" alt="Branch Inward Weighbridge Desk">
    <div class="caption">Figure 3.1: Branch Cashier Weighbridge Inward Desk & Payout Calculator</div>

    <h3>Step-by-Step Cashier Settlement Workflow:</h3>

    <div class="step-box">
        <div class="step-num">1</div>
        <div class="step-content">
            <strong>Gross Vehicle Weighment:</strong>
            Loaded vehicle drives onto Dharamkanta platform. Enter Gross Weight (e.g. <code>3,850 Kg</code>) or sync directly via serial RS-232 weighbridge indicator.
        </div>
    </div>

    <div class="step-box">
        <div class="step-num">2</div>
        <div class="step-content">
            <strong>Link Digital QC Ticket:</strong>
            Select the farmer's pending inspection ticket from the dropdown or click <strong>"Verify & Fill"</strong>. Moisture %, Karda %, Breed, and Suggested Rate auto-populate instantly.
        </div>
    </div>

    <div class="step-box">
        <div class="step-num">3</div>
        <div class="step-content">
            <strong>Tare Weighment & Net Calculation:</strong>
            After grain is unloaded into the yard stack, empty vehicle mounts the weighbridge for Tare Weight (e.g. <code>1,250 Kg</code>). System calculates Net Weight:
            <code>Net Weight = Gross (3,850) - Tare (1,250) = 2,600 Kg (26.00 Qtl)</code>
            Standard moisture and karda refractions are deducted automatically from payable weight.
        </div>
    </div>

    <div class="step-box">
        <div class="step-num">4</div>
        <div class="step-content">
            <strong>Section 269ST Compliance & Cashier Payout:</strong>
            Select payment mode (CASH or RTGS).
            <div class="callout callout-amber" style="margin-top: 6px;">
                <strong>Automated ₹2,00,000 Cash Gate:</strong> If today's cumulative payments to this farmer reach or exceed ₹2,00,000, CASH mode is locked. The cashier must record the Bank Name, Account Number, and 16-character RTGS/NEFT UTR Number.
            </div>
            For cash payments under ₹2,00,000, specify the exact currency denomination breakdown (₹500, ₹200, ₹100 notes) for automated register reconciliation.
        </div>
    </div>

    <!-- =================================================================== -->
    <!-- SECTION 4: MUNIM STOCK BOOK & TRADER OUTWARD SALES -->
    <!-- =================================================================== -->
    <div class="page-break"></div>

    <h2>4. Branch Munim Manual (Stock Register & Outward Sales)</h2>
    <p>
        The Branch Munim maintains commodity physical stock balances and invoices outward dispatches to oil mills, dal millers, and external trading firms.
    </p>

    <img src="data:image/png;base64,{img_outward}" class="doc-img" style="max-height: 220px; object-fit: contain;" alt="Trader Outward Payment Receipt Modal">
    <div class="caption">Figure 4.1: Outward Trader Invoicing & Payment Receipt Modal</div>

    <h3>Stock Book & Outward Billing SOP:</h3>
    <ul style="padding-left: 20px; margin-bottom: 14px; font-size: 9.5pt; line-height: 1.6;">
        <li><strong>Automated Stock Ledgers:</strong> Inward purchases automatically increment commodity stock registers. Unloading tare confirmations update physical godown bags in real time.</li>
        <li><strong>Outward Dispatch Invoicing:</strong> Enter buyer trader name, GSTIN, destination, transporter details, vehicle number, and agreed rate per quintal.</li>
        <li><strong>Payment Receipt Tracking:</strong> Munims record incoming trader payments (RTGS, Cash, Cheque) with transaction vouchers and issue printed outward dispatch passes.</li>
    </ul>

    <h2>5. HQ Accountant & Central Super Admin Governance</h2>

    <img src="data:image/png;base64,{img_admin}" class="doc-img" alt="Super Admin Central Cloud Governance">
    <div class="caption">Figure 5.1: Central Super Admin Governance, Licensing & Staff Role Segregation</div>

    <div class="callout">
        <div class="callout-title">🔐 Hardware-Bound RSA-PSS 2048 Licensing</div>
        The ERP license is cryptographically tied to the server CPU fingerprint and machine UUID. To activate a branch terminal, Super Admin generates a signed <code>.lic</code> key from the Central License Desk.
    </div>

    <h3>Staff Role Assignment SOP:</h3>
    <p style="font-size: 9.5pt;">
        Quality inspectors are assigned to specific branches by the Accountant HQ. When Chikhali yard has 2 or 3 inspectors, each inspector is provisioned with a distinct username and password, ensuring individual audit accountability for every issued QC certificate.
    </p>

    <h2>6. Technical Troubleshooting & Support</h2>
    <table>
        <thead>
            <tr>
                <th>Observed Issue</th>
                <th>Root Cause</th>
                <th>Recommended Resolution</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Moisture reading rejected</td>
                <td>Reading is &lt;7.0% or &gt;24.0%</td>
                <td>Wipe moisture sensor cell, re-insert grain cup, and tap re-scan.</td>
            </tr>
            <tr>
                <td>Tray corners not recognized</td>
                <td>Grain spilled over ArUco markers</td>
                <td>Ensure 4 corner fiducial markers on matte-grey tray are unblocked.</td>
            </tr>
            <tr>
                <td>Cash settlement disabled</td>
                <td>Section 269ST ₹2,00,000 threshold reached</td>
                <td>Select RTGS/NEFT mode and enter Bank UTR number. Cash is legally barred.</td>
            </tr>
        </tbody>
    </table>

</body>
</html>
"""

def generate_pdf():
    os.makedirs(os.path.dirname(OUTPUT_PDF), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        page.pdf(
            path=OUTPUT_PDF,
            format="A4",
            landscape=False,
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"}
        )
        browser.close()

    if os.path.exists(OUTPUT_PDF):
        import shutil
        shutil.copy(OUTPUT_PDF, TRACKER_COPY)
        print(f"User Guide PDF successfully generated at: {OUTPUT_PDF}")
        print(f"Copied to public tracker at: {TRACKER_COPY}")
        print(f"File size: {os.path.getsize(OUTPUT_PDF):,} bytes")

if __name__ == "__main__":
    generate_pdf()
