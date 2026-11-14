"""
Rajarshi Shahu Trading Co. - Mandi ERP PDF & Excel Export Engine
Generates:
- Professional A4 PDF statements and registers using ReportLab
- Styled Microsoft Excel (.xlsx) workbooks using openpyxl
"""

import io
from datetime import datetime
from typing import Dict, List, Any, Optional

# ReportLab imports
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch

# openpyxl imports
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ============================================================================
# COLOR PALETTE & STYLES (Professional Mandi Green & Slate Theme)
# ============================================================================
PRIMARY_GREEN = colors.HexColor("#047857")
DARK_GREEN = colors.HexColor("#064e3b")
LIGHT_GREEN = colors.HexColor("#ecfdf5")
ACCENT_AMBER = colors.HexColor("#d97706")
LIGHT_AMBER = colors.HexColor("#fffbeb")
ALERT_RED = colors.HexColor("#dc2626")
LIGHT_RED = colors.HexColor("#fef2f2")
ACCENT_BLUE = colors.HexColor("#0284c7")
LIGHT_BLUE = colors.HexColor("#f0f9ff")
NEUTRAL_DARK = colors.HexColor("#0f172a")
NEUTRAL_MUTED = colors.HexColor("#64748b")
NEUTRAL_LIGHT = colors.HexColor("#f8fafc")
BORDER_COLOR = colors.HexColor("#cbd5e1")


def get_base_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='MandiTitle',
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=DARK_GREEN,
        alignment=1 # Centered
    ))
    styles.add(ParagraphStyle(
        name='MandiSubtitle',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=NEUTRAL_MUTED,
        alignment=1
    ))
    styles.add(ParagraphStyle(
        name='ReportHeading',
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=PRIMARY_GREEN,
        alignment=1
    ))
    styles.add(ParagraphStyle(
        name='MetaLabel',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=NEUTRAL_DARK
    ))
    styles.add(ParagraphStyle(
        name='MetaVal',
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=NEUTRAL_MUTED
    ))
    styles.add(ParagraphStyle(
        name='CellText',
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=NEUTRAL_DARK
    ))
    styles.add(ParagraphStyle(
        name='CellTextBold',
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=NEUTRAL_DARK
    ))
    styles.add(ParagraphStyle(
        name='CellNum',
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=NEUTRAL_DARK,
        alignment=2 # Right
    ))
    styles.add(ParagraphStyle(
        name='CellNumBold',
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=NEUTRAL_DARK,
        alignment=2 # Right
    ))
    styles.add(ParagraphStyle(
        name='FooterNote',
        fontName='Helvetica-Oblique',
        fontSize=7,
        leading=9,
        textColor=NEUTRAL_MUTED,
        alignment=1
    ))
    return styles


# ============================================================================
# 1. PARTY LEDGER (KHATA) -> PDF
# ============================================================================
def generate_party_ledger_pdf(report: Dict[str, Any]) -> bytes:
    party = report.get("party") or {}
    p_name = party.get("name") or "Party"
    p_type = (party.get("party_type") or "FARMER").upper()
    is_farmer = (p_type != "BUYER")
    from_date = report.get("from_date") or "Commencement"
    to_date = report.get("to_date") or datetime.now().strftime("%Y-%m-%d")
    branch_id = report.get("branch_id") or "All Branches"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=12*mm,
        rightMargin=12*mm,
        topMargin=12*mm,
        bottomMargin=12*mm
    )
    styles = get_base_styles()
    story = []

    # Letterhead Header
    story.append(Paragraph("RAJARSHI SHAHU TRADING COMPANY", styles['MandiTitle']))
    story.append(Paragraph("Govt. Licensed Mandi Merchant & Commission Agent | APMC Market Yard, Chikhali, Dist. Buldhana", styles['MandiSubtitle']))
    story.append(Paragraph("Phone: +91 94221 00000 | Email: accounts@rajarshishahu.com | GSTIN: 27AABCR1234F1Z8", styles['MandiSubtitle']))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY_GREEN, spaceBefore=0, spaceAfter=8))

    # Statement Title
    sub_title = "FARMER PROCUREMENT KHATA STATEMENT" if is_farmer else "BUYER SALES & RECEIVABLES LEDGER"
    story.append(Paragraph(f"<b>{sub_title}</b>", styles['ReportHeading']))
    story.append(Paragraph(f"Statement Period: <b>{from_date}</b> to <b>{to_date}</b> | Branch: <b>{branch_id}</b>", styles['MandiSubtitle']))
    story.append(Spacer(1, 4*mm))

    # Party Details Meta Grid
    party_meta = [
        [
            Paragraph(f"<b>Party Name:</b> {p_name}", styles['MetaLabel']),
            Paragraph(f"<b>Account Type:</b> {'Sundry Creditor (Farmer)' if is_farmer else 'Sundry Debtor (Buyer)'}", styles['MetaLabel']),
            Paragraph(f"<b>Phone:</b> {party.get('phone') or 'Not Registered'}", styles['MetaLabel']),
        ],
        [
            Paragraph(f"<b>Village/Location:</b> {party.get('village') or 'Buldhana Mandi Zone'}", styles['MetaLabel']),
            Paragraph(f"<b>Bank A/C:</b> {party.get('bank_account_no') or 'RTGS Master Verified'}", styles['MetaLabel']),
            Paragraph(f"<b>IFSC:</b> {party.get('bank_ifsc') or 'SBIN0000354'}", styles['MetaLabel']),
        ]
    ]
    t_meta = Table(party_meta, colWidths=[65*mm, 65*mm, 56*mm])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NEUTRAL_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 4*mm))

    # KPI Summary Cards (Opening, Debit, Credit, Remaining Closing)
    opening_bal = report.get("opening_balance", 0.0)
    op_type = report.get("opening_balance_type", "Nil")
    total_debit = report.get("total_debit", 0.0)
    total_credit = report.get("total_credit", 0.0)
    closing_bal = report.get("closing_balance", 0.0)
    cl_type = report.get("closing_balance_type", "Nil")
    raw_closing = report.get("raw_closing_balance", 0.0)

    is_pending_due = (is_farmer and raw_closing < -0.01) or (not is_farmer and raw_closing > 0.01)
    status_color = ALERT_RED if is_pending_due else (PRIMARY_GREEN if closing_bal < 0.01 else ACCENT_AMBER)
    status_label = "REMAINING DUE: Rs." + f"{closing_bal:,.2f}" if is_pending_due else ("FULLY SETTLED" if closing_bal < 0.01 else f"ADVANCE: Rs.{closing_bal:,.2f}")

    kpi_data = [
        [
            Paragraph("<b>OPENING BALANCE</b>", styles['MandiSubtitle']),
            Paragraph("<b>TOTAL DEBIT (PAID)</b>", styles['MandiSubtitle']),
            Paragraph("<b>TOTAL CREDIT (BILLED)</b>", styles['MandiSubtitle']),
            Paragraph("<b>REMAINING BALANCE DUE</b>", styles['MandiSubtitle'])
        ],
        [
            Paragraph(f"<b>Rs. {opening_bal:,.2f} {op_type}</b>", styles['ReportHeading']),
            Paragraph(f"<font color='#0284c7'><b>Rs. {total_debit:,.2f}</b></font>", styles['ReportHeading']),
            Paragraph(f"<font color='#d97706'><b>Rs. {total_credit:,.2f}</b></font>", styles['ReportHeading']),
            Paragraph(f"<font color='{status_color.hexval()}'><b>Rs. {closing_bal:,.2f} {cl_type}</b></font>", styles['ReportHeading'])
        ],
        [
            Paragraph("Prior to start date", styles['FooterNote']),
            Paragraph("Settlements made", styles['FooterNote']),
            Paragraph("Procured / Invoiced", styles['FooterNote']),
            Paragraph(status_label, styles['FooterNote'])
        ]
    ]
    t_kpi = Table(kpi_data, colWidths=[46*mm, 46*mm, 46*mm, 48*mm])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREEN),
        ('BOX', (0, 0), (-1, -1), 1, PRIMARY_GREEN),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 4*mm))

    # Transactions Table
    tx_headers = [
        Paragraph("<b>#</b>", styles['CellTextBold']),
        Paragraph("<b>Date</b>", styles['CellTextBold']),
        Paragraph("<b>Voucher Type</b>", styles['CellTextBold']),
        Paragraph("<b>Voucher #</b>", styles['CellTextBold']),
        Paragraph("<b>Particulars / Narration</b>", styles['CellTextBold']),
        Paragraph("<b>Debit (Rs)</b>", styles['CellNumBold']),
        Paragraph("<b>Credit (Rs)</b>", styles['CellNumBold']),
        Paragraph("<b>Balance (Rs)</b>", styles['CellNumBold']),
    ]
    tx_rows = [tx_headers]

    # Opening balance row
    tx_rows.append([
        Paragraph("—", styles['CellText']),
        Paragraph(from_date, styles['CellTextBold']),
        Paragraph("Opening Bal", styles['CellTextBold']),
        Paragraph("—", styles['CellText']),
        Paragraph("Cumulative balance brought forward", styles['CellText']),
        Paragraph("—", styles['CellNum']),
        Paragraph("—", styles['CellNum']),
        Paragraph(f"{opening_bal:,.2f} {op_type}", styles['CellNumBold']),
    ])

    txs = report.get("transactions", [])
    for idx, tx in enumerate(txs):
        debit_str = f"{tx.get('debit', 0):,.2f}" if tx.get('debit', 0) > 0 else "—"
        credit_str = f"{tx.get('credit', 0):,.2f}" if tx.get('credit', 0) > 0 else "—"
        bal_str = f"{tx.get('running_balance', 0):,.2f} {tx.get('balance_type', '')}"

        tx_rows.append([
            Paragraph(str(idx + 1), styles['CellText']),
            Paragraph(str(tx.get("date", "")), styles['CellText']),
            Paragraph(str(tx.get("voucher_type", "")), styles['CellText']),
            Paragraph(str(tx.get("voucher_number", "")), styles['CellTextBold']),
            Paragraph(str(tx.get("particulars", ""))[:65], styles['CellText']),
            Paragraph(debit_str, styles['CellNum']),
            Paragraph(credit_str, styles['CellNum']),
            Paragraph(bal_str, styles['CellNumBold']),
        ])

    # Footer Totals Row
    tx_rows.append([
        Paragraph("", styles['CellText']),
        Paragraph("<b>TOTALS</b>", styles['CellTextBold']),
        Paragraph("", styles['CellText']),
        Paragraph("", styles['CellText']),
        Paragraph("Period Grand Totals", styles['CellTextBold']),
        Paragraph(f"<b>Rs.{total_debit:,.2f}</b>", styles['CellNumBold']),
        Paragraph(f"<b>Rs.{total_credit:,.2f}</b>", styles['CellNumBold']),
        Paragraph(f"<b>Rs.{closing_bal:,.2f} {cl_type}</b>", styles['CellNumBold']),
    ])

    # Table Widths: 8 + 18 + 24 + 20 + 52 + 21 + 21 + 22 = 186 mm (Fits A4 portrait 186mm printable)
    t_tx = Table(tx_rows, colWidths=[8*mm, 18*mm, 24*mm, 20*mm, 52*mm, 21*mm, 21*mm, 22*mm], repeatRows=1)
    t_tx.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, NEUTRAL_LIGHT]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
        ('LINEABOVE', (0, -1), (-1, -1), 1, PRIMARY_GREEN),
    ]))
    story.append(t_tx)
    story.append(Spacer(1, 6*mm))

    # Outstanding Status Callout Box & Signatures
    stat_msg = (
        f"<b>OFFICIAL ACCOUNT STATUS:</b> Full and final remaining balance payable to <b>{p_name}</b> is <b>Rs. {closing_bal:,.2f}</b>. "
        f"Awaiting cashier payout / RTGS transfer."
        if is_pending_due else
        f"<b>OFFICIAL ACCOUNT STATUS:</b> Account is <b>FULLY SETTLED</b> with zero remaining balance as on {to_date}."
    )
    story.append(Paragraph(stat_msg, styles['MetaLabel']))
    story.append(Spacer(1, 10*mm))

    sig_data = [
        [
            Paragraph("Prepared By: <b>Accountant Desk</b>", styles['MetaVal']),
            Paragraph("Verified By: <b>Branch Manager</b>", styles['MetaVal']),
            Paragraph("Authorized Signatory: <b>Rajarshi Shahu Trading Co.</b>", styles['MetaVal'])
        ]
    ]
    t_sig = Table(sig_data, colWidths=[62*mm, 62*mm, 62*mm])
    t_sig.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_sig)

    doc.build(story)
    return buf.getvalue()


# ============================================================================
# 2. PARTY LEDGER (KHATA) -> EXCEL (.XLSX)
# ============================================================================
def generate_party_ledger_xlsx(report: Dict[str, Any]) -> bytes:
    party = report.get("party") or {}
    p_name = party.get("name") or "Party"
    p_type = (party.get("party_type") or "FARMER").upper()
    is_farmer = (p_type != "BUYER")
    from_date = report.get("from_date") or "Commencement"
    to_date = report.get("to_date") or datetime.now().strftime("%Y-%m-%d")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Statement of Account"
    ws.views.sheetView[0].showGridLines = True

    # Styling helper
    header_fill = PatternFill(start_color="047857", end_color="047857", fill_type="solid")
    sub_fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
    total_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    white_font_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=16, bold=True, color="064E3B")
    bold_font = Font(name="Calibri", size=10, bold=True, color="0F172A")
    normal_font = Font(name="Calibri", size=10, color="0F172A")
    muted_font = Font(name="Calibri", size=9, color="64748B")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Header Titles
    ws.merge_cells("A1:H1")
    ws["A1"] = "RAJARSHI SHAHU TRADING COMPANY"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:H2")
    ws["A2"] = "APMC Market Yard, Chikhali, Dist. Buldhana | GSTIN: 27AABCR1234F1Z8"
    ws["A2"].font = muted_font
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:H3")
    sub_name = "Farmer Procurement Khata Statement" if is_farmer else "Buyer Sales & Receivables Statement"
    ws["A3"] = f"{sub_name}: {p_name} ({'Sundry Creditor' if is_farmer else 'Sundry Debtor'})"
    ws["A3"].font = Font(name="Calibri", size=12, bold=True, color="047857")
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A4:H4")
    ws["A4"] = f"Period: {from_date} to {to_date} | Phone: {party.get('phone', 'N/A')} | Village: {party.get('village', 'N/A')}"
    ws["A4"].font = muted_font
    ws["A4"].alignment = Alignment(horizontal="center", vertical="center")

    # Metrics Summary Row (Row 6)
    opening_bal = report.get("opening_balance", 0.0)
    op_type = report.get("opening_balance_type", "Nil")
    total_debit = report.get("total_debit", 0.0)
    total_credit = report.get("total_credit", 0.0)
    closing_bal = report.get("closing_balance", 0.0)
    cl_type = report.get("closing_balance_type", "Nil")

    ws["A6"] = "Opening Balance:"
    ws["B6"] = f"₹{opening_bal:,.2f} {op_type}"
    ws["C6"] = "Total Paid (Debit):"
    ws["D6"] = total_debit
    ws["E6"] = "Total Billed (Credit):"
    ws["F6"] = total_credit
    ws["G6"] = "Remaining Balance:"
    ws["H6"] = f"₹{closing_bal:,.2f} {cl_type}"

    for col in ["A", "C", "E", "G"]:
        ws[f"{col}6"].font = bold_font
    for col in ["B", "D", "F", "H"]:
        ws[f"{col}6"].font = bold_font
        if col in ["D", "F"]:
            ws[f"{col}6"].number_format = '₹#,##0.00'

    # Table Column Headers (Row 8)
    headers = ["#", "Date", "Branch", "Voucher Type", "Voucher / Ref #", "Particulars / Narration", "Debit (₹)", "Credit (₹)", "Running Balance (₹)"]
    row_num = 8
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=row_num, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = white_font_bold
        cell.alignment = Alignment(horizontal="center" if col_idx <= 5 else "right", vertical="center")
        cell.border = thin_border

    # Opening balance line
    row_num += 1
    ws.append(["—", from_date, "All Branches", "Opening Bal", "—", "Cumulative opening balance brought forward", None, None, opening_bal])
    for c in range(1, 10):
        cell = ws.cell(row=row_num, column=c)
        cell.font = bold_font
        cell.border = thin_border

    # Transactions
    for idx, tx in enumerate(report.get("transactions", []), 1):
        row_num += 1
        d_val = tx.get("debit", 0) if tx.get("debit", 0) > 0 else None
        c_val = tx.get("credit", 0) if tx.get("credit", 0) > 0 else None
        r_val = tx.get("running_balance", 0)
        bal_str = f"{r_val:,.2f} {tx.get('balance_type', '')}"

        ws.append([
            idx,
            tx.get("date"),
            tx.get("branch_name") or tx.get("branch_id"),
            tx.get("voucher_type"),
            tx.get("voucher_number"),
            tx.get("particulars"),
            d_val,
            c_val,
            bal_str
        ])
        for c in range(1, 10):
            cell = ws.cell(row=row_num, column=c)
            cell.font = normal_font
            cell.border = thin_border
            if c in [7, 8]:
                cell.number_format = '₹#,##0.00'

    # Totals Row
    row_num += 1
    ws.append(["", "TOTALS", "", "", "", "Period Grand Totals", total_debit, total_credit, f"{closing_bal:,.2f} {cl_type}"])
    for c in range(1, 10):
        cell = ws.cell(row=row_num, column=c)
        cell.fill = total_fill
        cell.font = bold_font
        cell.border = thin_border
        if c in [7, 8]:
            cell.number_format = '₹#,##0.00'

    # Auto-adjust column widths
    column_widths = {1: 6, 2: 12, 3: 18, 4: 16, 5: 16, 6: 42, 7: 15, 8: 15, 9: 18}
    for col_idx, width in column_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    x_buf = io.BytesIO()
    wb.save(x_buf)
    return x_buf.getvalue()


# ============================================================================
# 3. DAILY INWARD PROCUREMENT REGISTER -> PDF & EXCEL
# ============================================================================
def generate_daily_inward_pdf(invoices: List[Dict[str, Any]], target_date: str, branch_name: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=10*mm, rightMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = get_base_styles()
    story = []

    story.append(Paragraph("RAJARSHI SHAHU TRADING COMPANY", styles['MandiTitle']))
    story.append(Paragraph(f"DAILY INWARD PROCUREMENT REGISTER | Date: <b>{target_date}</b> | Branch: <b>{branch_name}</b>", styles['ReportHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_GREEN, spaceBefore=4, spaceAfter=8))

    total_gross = sum(float(i.get("gross_amount") or 0.0) for i in invoices)
    total_hamali = sum(float(i.get("hamali_charge") or 0.0) for i in invoices)
    total_net = sum(float(i.get("net_payable_amount") or i.get("rounded_net_payable") or 0.0) for i in invoices)
    total_qtl = sum(float(i.get("net_quintals") or 0.0) for i in invoices)
    total_bags = sum(int(i.get("bag_count") or 0) for i in invoices)
    paid_amt = sum(float(i.get("net_payable_amount") or 0.0) for i in invoices if (i.get("payout_status") or "").upper() in ["PAID", "PAID_CASH", "RTGS_COMPLETED", "COMPLETED"])
    pending_amt = total_net - paid_amt

    # KPI summary
    kpis = [
        [
            Paragraph(f"<b>Total Lots:</b> {len(invoices)}", styles['MetaLabel']),
            Paragraph(f"<b>Total Bags:</b> {total_bags:,}", styles['MetaLabel']),
            Paragraph(f"<b>Net Volume:</b> {total_qtl:.2f} Qtl ({(total_qtl/10.0):.2f} MT)", styles['MetaLabel']),
            Paragraph(f"<b>Gross Outlay:</b> Rs.{total_gross:,.2f}", styles['MetaLabel']),
            Paragraph(f"<b>Farmer Payable:</b> Rs.{total_net:,.2f}", styles['MetaLabel']),
            Paragraph(f"<b>Paid:</b> Rs.{paid_amt:,.2f} | <b>Due:</b> Rs.{pending_amt:,.2f}", styles['MetaLabel']),
        ]
    ]
    t_k = Table(kpis, colWidths=[40*mm, 35*mm, 52*mm, 48*mm, 50*mm, 52*mm])
    t_k.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREEN),
        ('BOX', (0, 0), (-1, -1), 1, PRIMARY_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_k)
    story.append(Spacer(1, 4*mm))

    # Table
    headers = [
        Paragraph("<b>#</b>", styles['CellTextBold']),
        Paragraph("<b>Token #</b>", styles['CellTextBold']),
        Paragraph("<b>Farmer Name</b>", styles['CellTextBold']),
        Paragraph("<b>Phone</b>", styles['CellTextBold']),
        Paragraph("<b>Commodity</b>", styles['CellTextBold']),
        Paragraph("<b>Bags</b>", styles['CellNumBold']),
        Paragraph("<b>Moist %</b>", styles['CellNumBold']),
        Paragraph("<b>Net Qtl</b>", styles['CellNumBold']),
        Paragraph("<b>Rate (Rs)</b>", styles['CellNumBold']),
        Paragraph("<b>Gross (Rs)</b>", styles['CellNumBold']),
        Paragraph("<b>Hamali</b>", styles['CellNumBold']),
        Paragraph("<b>Net Payable</b>", styles['CellNumBold']),
        Paragraph("<b>Status</b>", styles['CellTextBold']),
    ]
    rows = [headers]

    for idx, inv in enumerate(invoices, 1):
        f_name = inv.get("custom_farmer_name") or inv.get("party_name") or "Farmer"
        rows.append([
            Paragraph(str(idx), styles['CellText']),
            Paragraph(str(inv.get("token_number") or inv.get("id")), styles['CellTextBold']),
            Paragraph(f_name[:20], styles['CellText']),
            Paragraph(str(inv.get("party_phone") or "")[-10:], styles['CellText']),
            Paragraph(str(inv.get("commodity_name") or "")[:12], styles['CellText']),
            Paragraph(str(inv.get("bag_count") or 0), styles['CellNum']),
            Paragraph(f"{float(inv.get('moisture_percentage') or 0):.1f}%", styles['CellNum']),
            Paragraph(f"{float(inv.get('net_quintals') or 0):.2f}", styles['CellNum']),
            Paragraph(f"{float(inv.get('rate_per_quintal') or 0):,.0f}", styles['CellNum']),
            Paragraph(f"{float(inv.get('gross_amount') or 0):,.2f}", styles['CellNum']),
            Paragraph(f"{float(inv.get('hamali_charge') or 0):,.0f}", styles['CellNum']),
            Paragraph(f"{float(inv.get('net_payable_amount') or 0):,.2f}", styles['CellNumBold']),
            Paragraph(str(inv.get("payout_status") or "PENDING"), styles['CellTextBold']),
        ])

    rows.append([
        Paragraph("", styles['CellText']),
        Paragraph("<b>TOTALS</b>", styles['CellTextBold']),
        Paragraph("", styles['CellText']),
        Paragraph("", styles['CellText']),
        Paragraph("", styles['CellText']),
        Paragraph(f"<b>{total_bags}</b>", styles['CellNumBold']),
        Paragraph("", styles['CellText']),
        Paragraph(f"<b>{total_qtl:.2f}</b>", styles['CellNumBold']),
        Paragraph("", styles['CellText']),
        Paragraph(f"<b>{total_gross:,.2f}</b>", styles['CellNumBold']),
        Paragraph(f"<b>{total_hamali:,.0f}</b>", styles['CellNumBold']),
        Paragraph(f"<b>{total_net:,.2f}</b>", styles['CellNumBold']),
        Paragraph("", styles['CellText']),
    ])

    t = Table(rows, colWidths=[8*mm, 18*mm, 35*mm, 20*mm, 24*mm, 14*mm, 15*mm, 18*mm, 18*mm, 25*mm, 16*mm, 26*mm, 20*mm], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
        ('LINEABOVE', (0, -1), (-1, -1), 1, PRIMARY_GREEN),
    ]))
    story.append(t)
    doc.build(story)
    return buf.getvalue()


def generate_daily_inward_xlsx(invoices: List[Dict[str, Any]], target_date: str, branch_name: str) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Daily Inward Register"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="047857", end_color="047857", fill_type="solid")
    total_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    white_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    bold_font = Font(name="Calibri", size=10, bold=True)
    normal_font = Font(name="Calibri", size=10)
    thin_border = Border(left=Side(style='thin', color='CBD5E1'), right=Side(style='thin', color='CBD5E1'), top=Side(style='thin', color='CBD5E1'), bottom=Side(style='thin', color='CBD5E1'))

    ws.merge_cells("A1:M1")
    ws["A1"] = f"RAJARSHI SHAHU TRADING CO. - DAILY INWARD PROCUREMENT REGISTER ({target_date})"
    ws["A1"].font = Font(name="Calibri", size=15, bold=True, color="064E3B")
    ws["A1"].alignment = Alignment(horizontal="center")

    ws.merge_cells("A2:M2")
    ws["A2"] = f"Branch: {branch_name} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ws["A2"].font = Font(name="Calibri", size=10, color="64748B")
    ws["A2"].alignment = Alignment(horizontal="center")

    headers = ["#", "Token #", "Date", "Branch", "Farmer Name", "Phone", "Commodity", "Bags", "Moisture %", "Net Qtl", "Rate (₹)", "Gross (₹)", "Hamali (₹)", "Net Farmer Payable (₹)", "Status", "UTR / Ref"]
    row_num = 4
    for idx, h in enumerate(headers, 1):
        c = ws.cell(row=row_num, column=idx, value=h)
        c.fill = header_fill
        c.font = white_font
        c.border = thin_border
        c.alignment = Alignment(horizontal="center" if idx <= 7 else "right")

    for idx, inv in enumerate(invoices, 1):
        row_num += 1
        f_name = inv.get("custom_farmer_name") or inv.get("party_name") or "Farmer"
        ws.append([
            idx,
            str(inv.get("token_number") or inv.get("id")),
            str(inv.get("invoice_date")),
            str(inv.get("branch_name") or branch_name),
            f_name,
            str(inv.get("party_phone") or ""),
            str(inv.get("commodity_name")),
            int(inv.get("bag_count") or 0),
            float(inv.get("moisture_percentage") or 0.0),
            float(inv.get("net_quintals") or 0.0),
            float(inv.get("rate_per_quintal") or 0.0),
            float(inv.get("gross_amount") or 0.0),
            float(inv.get("hamali_charge") or 0.0),
            float(inv.get("net_payable_amount") or 0.0),
            str(inv.get("payout_status") or "PENDING"),
            str(inv.get("rtgs_utr_no") or "")
        ])
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.font = normal_font
            cell.border = thin_border
            if col_idx in [10, 11, 12, 13, 14]:
                cell.number_format = '₹#,##0.00'

    # Auto widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(max_len + 3, 10)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ============================================================================
# 4. ALL PARTIES REMAINING BALANCES -> PDF & EXCEL
# ============================================================================
def generate_party_balances_pdf(balances_data: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12*mm, rightMargin=12*mm, topMargin=12*mm, bottomMargin=12*mm)
    styles = get_base_styles()
    story = []

    story.append(Paragraph("RAJARSHI SHAHU TRADING COMPANY", styles['MandiTitle']))
    story.append(Paragraph("OUTSTANDING PARTY BALANCES & REMAINING DUES REGISTER", styles['ReportHeading']))
    story.append(Paragraph(f"Generated as on: <b>{datetime.now().strftime('%d-%m-%Y %H:%M')}</b>", styles['MandiSubtitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_GREEN, spaceBefore=4, spaceAfter=8))

    summary = balances_data.get("summary", {})
    tot_pay = summary.get("total_payable_to_farmers", 0.0)
    tot_rec = summary.get("total_receivable_from_buyers", 0.0)
    due_cnt = summary.get("total_parties_with_pending", 0)
    set_cnt = summary.get("total_settled_parties", 0)

    kpis = [
        [
            Paragraph(f"<b>Payable to Farmers:</b><br/><font color='#dc2626'><b>Rs. {tot_pay:,.2f}</b></font>", styles['MetaLabel']),
            Paragraph(f"<b>Receivable from Buyers:</b><br/><font color='#0284c7'><b>Rs. {tot_rec:,.2f}</b></font>", styles['MetaLabel']),
            Paragraph(f"<b>Parties with Due:</b><br/><b>{due_cnt} Accounts</b>", styles['MetaLabel']),
            Paragraph(f"<b>Fully Settled:</b><br/><b>{set_cnt} Accounts</b>", styles['MetaLabel']),
        ]
    ]
    t_k = Table(kpis, colWidths=[46*mm, 46*mm, 46*mm, 48*mm])
    t_k.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREEN),
        ('BOX', (0, 0), (-1, -1), 1, PRIMARY_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_k)
    story.append(Spacer(1, 4*mm))

    headers = [
        Paragraph("<b>#</b>", styles['CellTextBold']),
        Paragraph("<b>Party Name</b>", styles['CellTextBold']),
        Paragraph("<b>Type</b>", styles['CellTextBold']),
        Paragraph("<b>Village</b>", styles['CellTextBold']),
        Paragraph("<b>Total Billed (Rs)</b>", styles['CellNumBold']),
        Paragraph("<b>Total Paid (Rs)</b>", styles['CellNumBold']),
        Paragraph("<b>Remaining Due (Rs)</b>", styles['CellNumBold']),
        Paragraph("<b>Status</b>", styles['CellTextBold']),
    ]
    rows = [headers]

    parties = balances_data.get("parties", [])
    for idx, r in enumerate(parties, 1):
        rem_str = f"Rs.{r.get('remaining_balance', 0):,.2f} {r.get('balance_type', '')}"
        status_text = r.get("status_label") or "Settled"
        rows.append([
            Paragraph(str(idx), styles['CellText']),
            Paragraph(str(r.get("party_name"))[:24], styles['CellTextBold']),
            Paragraph(str(r.get("party_type")), styles['CellText']),
            Paragraph(str(r.get("village") or "")[:15], styles['CellText']),
            Paragraph(f"{r.get('total_procured_or_billed', 0):,.2f}", styles['CellNum']),
            Paragraph(f"{r.get('total_paid_or_received', 0):,.2f}", styles['CellNum']),
            Paragraph(rem_str, styles['CellNumBold']),
            Paragraph(status_text[:20], styles['CellTextBold']),
        ])

    t = Table(rows, colWidths=[8*mm, 45*mm, 18*mm, 25*mm, 25*mm, 25*mm, 25*mm, 15*mm], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t)
    doc.build(story)
    return buf.getvalue()


def generate_party_balances_xlsx(balances_data: Dict[str, Any]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Party Balances"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="047857", end_color="047857", fill_type="solid")
    white_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    normal_font = Font(name="Calibri", size=10)
    thin_border = Border(left=Side(style='thin', color='CBD5E1'), right=Side(style='thin', color='CBD5E1'), top=Side(style='thin', color='CBD5E1'), bottom=Side(style='thin', color='CBD5E1'))

    ws.merge_cells("A1:I1")
    ws["A1"] = "RAJARSHI SHAHU TRADING CO. - PARTY BALANCES & OUTSTANDING DUES"
    ws["A1"].font = Font(name="Calibri", size=15, bold=True, color="064E3B")
    ws["A1"].alignment = Alignment(horizontal="center")

    headers = ["#", "Party Name", "Type", "Village", "Phone", "Total Billed / Procured (₹)", "Total Paid / Settled (₹)", "Remaining Balance (₹)", "Status"]
    row_num = 3
    for idx, h in enumerate(headers, 1):
        c = ws.cell(row=row_num, column=idx, value=h)
        c.fill = header_fill
        c.font = white_font
        c.border = thin_border
        c.alignment = Alignment(horizontal="center" if idx <= 5 else "right")

    for idx, r in enumerate(balances_data.get("parties", []), 1):
        row_num += 1
        ws.append([
            idx,
            r.get("party_name"),
            r.get("party_type"),
            r.get("village"),
            r.get("phone"),
            float(r.get("total_procured_or_billed") or 0.0),
            float(r.get("total_paid_or_received") or 0.0),
            float(r.get("remaining_balance") or 0.0),
            r.get("status_label")
        ])
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.font = normal_font
            cell.border = thin_border
            if col_idx in [6, 7, 8]:
                cell.number_format = '₹#,##0.00'

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(max_len + 3, 11)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ============================================================================
# 5. DAILY OUTWARD SALES REGISTER -> PDF & EXCEL
# ============================================================================
def generate_daily_outward_pdf(orders: List[Dict[str, Any]], target_date: str, branch_name: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=10*mm, rightMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = get_base_styles()
    story = []

    story.append(Paragraph("RAJARSHI SHAHU TRADING COMPANY", styles['MandiTitle']))
    story.append(Paragraph(f"DAILY OUTWARD SALES & DISPATCH REGISTER | Date: <b>{target_date}</b> | Branch: <b>{branch_name}</b>", styles['ReportHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_GREEN, spaceBefore=4, spaceAfter=8))

    total_bill = sum(float(o.get("total_bill_amount") or o.get("gross_amount") or 0.0) for o in orders)
    total_qtl = sum(float(o.get("net_quintals") or 0.0) for o in orders)
    paid_amt = sum(float(o.get("total_bill_amount") or 0.0) for o in orders if (o.get("payment_status") or "").upper() in ["PAID", "RECEIVED"])
    pending_amt = total_bill - paid_amt

    kpis = [
        [
            Paragraph(f"<b>Total Dispatches:</b> {len(orders)}", styles['MetaLabel']),
            Paragraph(f"<b>Dispatched Volume:</b> {total_qtl:.2f} Qtl ({(total_qtl/10.0):.2f} MT)", styles['MetaLabel']),
            Paragraph(f"<b>Total Billed:</b> Rs.{total_bill:,.2f}", styles['MetaLabel']),
            Paragraph(f"<b>Realized:</b> Rs.{paid_amt:,.2f} | <b>Due:</b> Rs.{pending_amt:,.2f}", styles['MetaLabel']),
        ]
    ]
    t_k = Table(kpis, colWidths=[55*mm, 75*mm, 75*mm, 72*mm])
    t_k.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GREEN),
        ('BOX', (0, 0), (-1, -1), 1, PRIMARY_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_k)
    story.append(Spacer(1, 4*mm))

    headers = [
        Paragraph("<b>#</b>", styles['CellTextBold']),
        Paragraph("<b>Challan #</b>", styles['CellTextBold']),
        Paragraph("<b>Buyer / Mill Name</b>", styles['CellTextBold']),
        Paragraph("<b>Commodity</b>", styles['CellTextBold']),
        Paragraph("<b>Vehicle #</b>", styles['CellTextBold']),
        Paragraph("<b>Net MT</b>", styles['CellNumBold']),
        Paragraph("<b>Rate/Qtl</b>", styles['CellNumBold']),
        Paragraph("<b>Total Bill (Rs)</b>", styles['CellNumBold']),
        Paragraph("<b>Status</b>", styles['CellTextBold']),
        Paragraph("<b>UTR / Mode</b>", styles['CellTextBold']),
    ]
    rows = [headers]

    for idx, o in enumerate(orders, 1):
        q = float(o.get("net_quintals") or 0.0)
        mt = q / 10.0
        rows.append([
            Paragraph(str(idx), styles['CellText']),
            Paragraph(str(o.get("challan_number") or o.get("id")), styles['CellTextBold']),
            Paragraph(str(o.get("buyer_name") or "Buyer")[:24], styles['CellText']),
            Paragraph(str(o.get("commodity_name") or "")[:15], styles['CellText']),
            Paragraph(str(o.get("vehicle_number") or "N/A"), styles['CellText']),
            Paragraph(f"{mt:.2f}", styles['CellNumBold']),
            Paragraph(f"{float(o.get('rate_per_quintal') or 0):,.0f}", styles['CellNum']),
            Paragraph(f"{float(o.get('total_bill_amount') or 0):,.2f}", styles['CellNumBold']),
            Paragraph(str(o.get("payment_status") or "PENDING"), styles['CellTextBold']),
            Paragraph(str(o.get("utr_number") or o.get("payment_mode") or "—"), styles['CellText']),
        ])

    rows.append([
        Paragraph("", styles['CellText']),
        Paragraph("<b>TOTALS</b>", styles['CellTextBold']),
        Paragraph("", styles['CellText']),
        Paragraph("", styles['CellText']),
        Paragraph("", styles['CellText']),
        Paragraph(f"<b>{(total_qtl/10.0):.2f} MT</b>", styles['CellNumBold']),
        Paragraph("", styles['CellText']),
        Paragraph(f"<b>Rs.{total_bill:,.2f}</b>", styles['CellNumBold']),
        Paragraph("", styles['CellText']),
        Paragraph("", styles['CellText']),
    ])

    t = Table(rows, colWidths=[8*mm, 24*mm, 52*mm, 30*mm, 26*mm, 22*mm, 22*mm, 35*mm, 28*mm, 30*mm], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
        ('LINEABOVE', (0, -1), (-1, -1), 1, PRIMARY_GREEN),
    ]))
    story.append(t)
    doc.build(story)
    return buf.getvalue()


def generate_daily_outward_xlsx(orders: List[Dict[str, Any]], target_date: str, branch_name: str) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Daily Outward Register"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="047857", end_color="047857", fill_type="solid")
    white_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    normal_font = Font(name="Calibri", size=10)
    thin_border = Border(left=Side(style='thin', color='CBD5E1'), right=Side(style='thin', color='CBD5E1'), top=Side(style='thin', color='CBD5E1'), bottom=Side(style='thin', color='CBD5E1'))

    ws.merge_cells("A1:K1")
    ws["A1"] = f"RAJARSHI SHAHU TRADING CO. - DAILY OUTWARD SALES & DISPATCH REGISTER ({target_date})"
    ws["A1"].font = Font(name="Calibri", size=15, bold=True, color="064E3B")
    ws["A1"].alignment = Alignment(horizontal="center")

    headers = ["#", "Challan #", "Date", "Branch", "Buyer / Mill Name", "Commodity", "Vehicle #", "Net Qtl", "Net MT", "Rate/Qtl (₹)", "Total Billed (₹)", "Status", "Payment Mode / UTR"]
    row_num = 3
    for idx, h in enumerate(headers, 1):
        c = ws.cell(row=row_num, column=idx, value=h)
        c.fill = header_fill
        c.font = white_font
        c.border = thin_border
        c.alignment = Alignment(horizontal="center" if idx <= 7 else "right")

    for idx, o in enumerate(orders, 1):
        row_num += 1
        q = float(o.get("net_quintals") or 0.0)
        ws.append([
            idx,
            str(o.get("challan_number") or o.get("id")),
            str(o.get("order_date")),
            str(o.get("branch_name") or branch_name),
            str(o.get("buyer_name")),
            str(o.get("commodity_name")),
            str(o.get("vehicle_number") or "N/A"),
            q,
            q / 10.0,
            float(o.get("rate_per_quintal") or 0.0),
            float(o.get("total_bill_amount") or 0.0),
            str(o.get("payment_status") or "PENDING"),
            str(o.get("utr_number") or o.get("payment_mode") or "")
        ])
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.font = normal_font
            cell.border = thin_border
            if col_idx in [8, 9, 10, 11]:
                cell.number_format = '₹#,##0.00'

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(max_len + 3, 11)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
