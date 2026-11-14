"""
Tally Prime & Mandi ERP Reports Engine
Rajarshi Shahu Trading Mandi ERP — Powered by Cresconic Technologies

Provides:
- Party-Wise Ledger Statement generation with Opening & Running Balance
- Daily Inward (Procurement) Register per branch & date
- Daily Outward (Sales/Dispatches) Register per branch & date
- Tally Prime / ERP 9 XML Export (Vouchers & Masters)
- Tally Excel / CSV Export
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, date
import re
from typing import Dict, List, Any, Optional

def escape_xml(text: Any) -> str:
    if text is None:
        return ""
    s = str(text)
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))

def format_tally_date(d_str: Optional[str]) -> str:
    """Converts ISO or YYYY-MM-DD or DD/MM/YYYY into YYYYMMDD for Tally."""
    if not d_str:
        return datetime.now().strftime("%Y%m%d")
    s = str(d_str).split("T")[0].strip()
    if "-" in s:
        parts = s.split("-")
        if len(parts) == 3:
            return f"{parts[0]:0>4}{parts[1]:0>2}{parts[2]:0>2}"
    elif "/" in s:
        parts = s.split("/")
        if len(parts) == 3:
            return f"{parts[2]:0>4}{parts[1]:0>2}{parts[0]:0>2}"
    return datetime.now().strftime("%Y%m%d")

def pretty_xml(elem: ET.Element) -> str:
    """Return pretty-printed XML string with proper Tally envelope header."""
    rough_string = ET.tostring(elem, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


# ============================================================================
# 1. TALLY MASTER GENERATION
# ============================================================================

def create_tally_ledger_master(name: str, parent: str, opening_bal: float = 0.0,
                               address: str = "", state: str = "Maharashtra",
                               pincode: str = "443201", gstin: str = "") -> ET.Element:
    """Builds a <LEDGER> master element for Tally import."""
    tm = ET.Element("TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
    led = ET.SubElement(tm, "LEDGER", {"NAME": name, "ACTION": "Create"})
    ET.SubElement(led, "NAME").text = name
    ET.SubElement(led, "PARENT").text = parent
    ET.SubElement(led, "OPENINGBALANCE").text = f"{opening_bal:.2f}"
    ET.SubElement(led, "ISBILLWISEON").text = "Yes" if "Sundry" in parent else "No"
    ET.SubElement(led, "AFFECTSSTOCK").text = "Yes" if "Purchase" in parent or "Sales" in parent else "No"
    
    if address:
        addr_list = ET.SubElement(led, "ADDRESS.LIST")
        ET.SubElement(addr_list, "ADDRESS").text = address
    ET.SubElement(led, "LEDSTATENAME").text = state
    ET.SubElement(led, "COUNTRYNAME").text = "India"
    if pincode:
        ET.SubElement(led, "PINCODE").text = pincode
    if gstin:
        reg_list = ET.SubElement(led, "LEDGERGSTREGDETAILS.LIST")
        ET.SubElement(reg_list, "APPLICABLEFROM").text = "20260401"
        ET.SubElement(reg_list, "GSTREGISTRATIONTYPE").text = "Regular"
        ET.SubElement(reg_list, "STATEPLACEOFSUPPLY").text = state
        ET.SubElement(reg_list, "GSTIN").text = gstin
    return tm


# ============================================================================
# 2. PARTY-WISE LEDGER STATEMENT CALCULATION
# ============================================================================

def calculate_party_ledger(party: Dict[str, Any],
                           all_invoices: List[Dict[str, Any]],
                           all_ledgers: List[Dict[str, Any]],
                           all_outward: List[Dict[str, Any]],
                           from_date: Optional[str] = None,
                           to_date: Optional[str] = None,
                           branch_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes party ledger statement:
    - Opening Balance (prior to from_date)
    - Chronological Transactions (debit, credit, running balance)
    - Closing Balance
    """
    p_id = party.get("id") or ""
    p_name = party.get("name") or "Party"
    p_type = party.get("party_type") or "FARMER"

    raw_txs = []

    # 1. Invoices for this party
    for inv in all_invoices:
        inv_party_id = inv.get("party_id") or ""
        inv_custom_name = inv.get("custom_farmer_name") or ""
        if inv_party_id == p_id or (inv_custom_name and inv_custom_name.lower() == p_name.lower()):
            if branch_id and branch_id != "all" and inv.get("branch_id") != branch_id:
                continue
            inv_date = (inv.get("invoice_date") or "").split("T")[0]
            net_amt = float(inv.get("net_payable_amount") or inv.get("rounded_net_payable") or 0.0)
            gross_amt = float(inv.get("gross_amount") or 0.0)
            hamali = float(inv.get("hamali_charge") or 0.0)
            tok = inv.get("token_number") or inv.get("id") or "INV"
            comm = inv.get("commodity_name") or "Commodity"
            qtl = float(inv.get("net_quintals") or 0.0)
            rate = float(inv.get("rate_per_quintal") or 0.0)

            # For a farmer/creditor, purchase invoice is a CREDIT (we owe them)
            raw_txs.append({
                "date": inv_date,
                "timestamp": inv.get("created_at") or f"{inv_date}T10:00:00Z",
                "voucher_type": "Purchase Invoice",
                "voucher_number": tok,
                "branch_id": inv.get("branch_id"),
                "particulars": f"Procured {qtl:.2f} Qtl {comm} @ Rs.{rate:,.2f}/Qtl (Bags: {inv.get('bag_count', 0)}, Hamali: Rs.{hamali:.2f})",
                "debit": 0.0,
                "credit": net_amt,
                "ref_id": inv.get("id"),
                "status": inv.get("payout_status") or "PENDING"
            })

            # If invoice is marked PAID or RTGS completed, record the payment transaction (Debit to farmer)
            payout_status = (inv.get("payout_status") or "").upper()
            if payout_status in ["PAID", "PAID_CASH", "RTGS_COMPLETED", "COMPLETED"]:
                pay_date = (inv.get("rtgs_completed_at") or inv.get("created_at") or inv_date).split("T")[0]
                utr = inv.get("rtgs_utr_no") or "CASH-COUNTER"
                mode = "RTGS Bank Transfer" if inv.get("weighment_mode") == "RTGS" or "RTGS" in payout_status else "Cash Payout"
                raw_txs.append({
                    "date": pay_date,
                    "timestamp": inv.get("rtgs_completed_at") or inv.get("created_at") or f"{pay_date}T16:00:00Z",
                    "voucher_type": "Payment",
                    "voucher_number": f"PAY-{tok}",
                    "branch_id": inv.get("branch_id"),
                    "particulars": f"{mode} settlement against Token #{tok} [UTR/Ref: {utr}]",
                    "debit": net_amt,
                    "credit": 0.0,
                    "ref_id": f"pay-{inv.get('id')}",
                    "status": "SETTLED"
                })

    # 2. Outward Orders (for buyers/millers)
    for out in all_outward:
        b_name = (out.get("buyer_name") or "").strip().lower()
        if b_name == p_name.lower() or out.get("party_id") == p_id:
            if branch_id and branch_id != "all" and out.get("branch_id") != branch_id:
                continue
            out_date = (out.get("order_date") or "").split("T")[0]
            total_bill = float(out.get("total_bill_amount") or out.get("gross_amount") or 0.0)
            challan = out.get("challan_number") or out.get("id") or "OUT"
            comm = out.get("commodity_name") or "Commodity"
            qtl = float(out.get("net_quintals") or 0.0)
            rate = float(out.get("rate_per_quintal") or 0.0)

            # For a buyer/debtor, sale is a DEBIT (they owe us)
            raw_txs.append({
                "date": out_date,
                "timestamp": out.get("created_at") or f"{out_date}T11:00:00Z",
                "voucher_type": "Sales Challan",
                "voucher_number": challan,
                "branch_id": out.get("branch_id"),
                "particulars": f"Dispatched {qtl:.2f} Qtl {comm} @ Rs.{rate:,.2f}/Qtl via Vehicle {out.get('vehicle_number', 'N/A')}",
                "debit": total_bill,
                "credit": 0.0,
                "ref_id": out.get("id"),
                "status": out.get("status") or "CONFIRMED"
            })

            # If buyer has paid (Payment Status = PAID or RECEIVED)
            pay_stat = (out.get("payment_status") or "").upper()
            if pay_stat in ["PAID", "RECEIVED"]:
                rec_date = (out.get("payment_received_date") or out_date).split("T")[0]
                raw_txs.append({
                    "date": rec_date,
                    "timestamp": out.get("payment_received_date") or out.get("created_at") or f"{rec_date}T17:00:00Z",
                    "voucher_type": "Receipt",
                    "voucher_number": f"REC-{challan}",
                    "branch_id": out.get("payment_branch_id") or out.get("branch_id"),
                    "particulars": f"Payment received from {p_name} via {out.get('payment_mode', 'BANK')} [UTR: {out.get('utr_number', 'N/A')}]",
                    "debit": 0.0,
                    "credit": total_bill,
                    "ref_id": f"rec-{out.get('id')}",
                    "status": "RECEIVED"
                })

    # Sort all raw transactions chronologically
    raw_txs.sort(key=lambda x: (x.get("date", ""), x.get("timestamp", "")))

    # Calculate Opening Balance and Filtered Transactions
    opening_balance = float(party.get("current_advance") or 0.0)  # advance given to farmer is Dr
    # If opening balance is given in party master:
    # A farmer with advance is Debit (we have an asset / receivable).

    period_txs = []
    total_period_debit = 0.0
    total_period_credit = 0.0

    for tx in raw_txs:
        t_date = tx["date"]
        if from_date and t_date < from_date:
            # Prior to from_date: accumulates into opening balance
            # Net = Debit - Credit
            opening_balance += (tx["debit"] - tx["credit"])
        elif to_date and t_date > to_date:
            continue
        else:
            period_txs.append(tx)
            total_period_debit += tx["debit"]
            total_period_credit += tx["credit"]

    # Calculate running balance row by row
    running_balance = opening_balance
    enriched_txs = []
    for tx in period_txs:
        running_balance += (tx["debit"] - tx["credit"])
        bal_type = "Dr" if running_balance > 0.001 else ("Cr" if running_balance < -0.001 else "Nil")
        enriched_txs.append({
            **tx,
            "running_balance": abs(running_balance),
            "balance_type": bal_type,
            "raw_balance": running_balance
        })

    closing_balance = running_balance
    closing_type = "Dr" if closing_balance > 0.001 else ("Cr" if closing_balance < -0.001 else "Nil")
    opening_type = "Dr" if opening_balance > 0.001 else ("Cr" if opening_balance < -0.001 else "Nil")

    # Determine human-friendly remaining balance status
    is_buyer = (p_type == "BUYER")
    remaining_balance_amount = abs(closing_balance)
    if remaining_balance_amount < 0.01:
        balance_status = "SETTLED"
        balance_status_text = "Fully Settled ✓ (हिशोब पूर्ण)"
        remaining_payable = 0.0
        remaining_receivable = 0.0
    elif is_buyer:
        if closing_balance > 0.001:
            balance_status = "PENDING_RECEIVABLE"
            balance_status_text = f"Payment Due from Buyer: Rs.{remaining_balance_amount:,.2f} (येणे बाकी)"
            remaining_payable = 0.0
            remaining_receivable = remaining_balance_amount
        else:
            balance_status = "ADVANCE_RECEIVED"
            balance_status_text = f"Advance from Buyer: Rs.{remaining_balance_amount:,.2f}"
            remaining_payable = 0.0
            remaining_receivable = 0.0
    else: # FARMER / SUPPLIER
        if closing_balance < -0.001:
            balance_status = "PENDING_PAYABLE"
            balance_status_text = f"Remaining Payable to Farmer: Rs.{remaining_balance_amount:,.2f} (देणे बाकी)"
            remaining_payable = remaining_balance_amount
            remaining_receivable = 0.0
        else:
            balance_status = "ADVANCE_PAID"
            balance_status_text = f"Advance Paid to Farmer: Rs.{remaining_balance_amount:,.2f}"
            remaining_payable = 0.0
            remaining_receivable = 0.0

    return {
        "party": party,
        "from_date": from_date,
        "to_date": to_date,
        "branch_id": branch_id or "all",
        "opening_balance": abs(opening_balance),
        "opening_balance_type": opening_type,
        "raw_opening_balance": opening_balance,
        "transactions": enriched_txs,
        "total_debit": total_period_debit,
        "total_credit": total_period_credit,
        "closing_balance": abs(closing_balance),
        "closing_balance_type": closing_type,
        "raw_closing_balance": closing_balance,
        "remaining_balance": remaining_balance_amount,
        "remaining_payable_to_farmer": remaining_payable,
        "remaining_receivable_from_buyer": remaining_receivable,
        "balance_status": balance_status,
        "balance_status_text": balance_status_text
    }


def calculate_all_party_balances(parties: List[Dict[str, Any]],
                                 all_invoices: List[Dict[str, Any]],
                                 all_ledgers: List[Dict[str, Any]],
                                 all_outward: List[Dict[str, Any]],
                                 branch_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes a consolidated Outstanding Balance Register for all parties:
    - Total Billed / Procured Amount
    - Total Paid / Settled Amount
    - Remaining Balance Due
    - Balance Status (Payable to Farmer / Receivable from Buyer / Fully Settled)
    """
    party_rows = []
    total_payable_farmers = 0.0
    total_receivable_buyers = 0.0
    total_parties_with_pending = 0
    total_settled_parties = 0

    for p in parties:
        ledger = calculate_party_ledger(p, all_invoices, all_ledgers, all_outward, branch_id=branch_id)
        raw_bal = ledger["raw_closing_balance"]
        bal_abs = ledger["closing_balance"]
        b_type = ledger["closing_balance_type"]
        p_type = (p.get("party_type") or "FARMER").upper()

        if bal_abs < 0.01:
            status = "SETTLED"
            status_label = "Fully Settled ✓"
            remaining_payable = 0.0
            remaining_receivable = 0.0
            total_settled_parties += 1
        elif p_type == "BUYER":
            if raw_bal > 0:
                status = "PENDING_RECEIVABLE"
                status_label = "Payment Due from Buyer (येणे बाकी)"
                remaining_payable = 0.0
                remaining_receivable = bal_abs
                total_receivable_buyers += bal_abs
                total_parties_with_pending += 1
            else:
                status = "ADVANCE_RECEIVED"
                status_label = "Advance from Buyer"
                remaining_payable = 0.0
                remaining_receivable = 0.0
        else: # FARMER
            if raw_bal < 0:
                status = "PENDING_PAYABLE"
                status_label = "Remaining Payable to Farmer (देणे बाकी)"
                remaining_payable = bal_abs
                remaining_receivable = 0.0
                total_payable_farmers += bal_abs
                total_parties_with_pending += 1
            else:
                status = "ADVANCE_PAID"
                status_label = "Advance Paid to Farmer"
                remaining_payable = 0.0
                remaining_receivable = 0.0

        party_rows.append({
            "party_id": p.get("id"),
            "party_name": p.get("name"),
            "party_type": p_type,
            "phone": p.get("phone") or "",
            "village": p.get("village") or "",
            "transaction_count": len(ledger["transactions"]),
            "total_procured_or_billed": ledger["total_credit"] if p_type == "FARMER" else ledger["total_debit"],
            "total_paid_or_received": ledger["total_debit"] if p_type == "FARMER" else ledger["total_credit"],
            "remaining_balance": bal_abs,
            "balance_type": b_type,
            "status": status,
            "status_label": status_label,
            "remaining_payable": remaining_payable,
            "remaining_receivable": remaining_receivable
        })

    # Sort so parties with pending balances come first, highest balance on top
    party_rows.sort(key=lambda r: (0 if r["status"].startswith("PENDING") else 1, -r["remaining_balance"]))

    return {
        "summary": {
            "total_parties": len(parties),
            "total_payable_to_farmers": total_payable_farmers,
            "total_receivable_from_buyers": total_receivable_buyers,
            "total_parties_with_pending": total_parties_with_pending,
            "total_settled_parties": total_settled_parties
        },
        "parties": party_rows
    }



# ============================================================================
# 3. TALLY XML EXPORTERS
# ============================================================================

def export_party_ledger_tally_xml(ledger_report: Dict[str, Any]) -> str:
    """
    Exports a single party's complete ledger statement to Tally XML.
    Includes the Party Master Ledger + all Vouchers.
    """
    party = ledger_report["party"]
    p_name = party.get("name") or "Party"
    p_type = party.get("party_type") or "FARMER"
    parent_group = "Sundry Creditors" if p_type == "FARMER" else "Sundry Debtors"

    root = ET.Element("ENVELOPE")
    hdr = ET.SubElement(root, "HEADER")
    ET.SubElement(hdr, "VERSION").text = "1"
    ET.SubElement(hdr, "TALLYREQUEST").text = "Import"
    ET.SubElement(hdr, "TYPE").text = "Data"
    ET.SubElement(hdr, "ID").text = "All Masters and Vouchers"

    body = ET.SubElement(root, "BODY")
    desc = ET.SubElement(body, "DESC")
    s_vars = ET.SubElement(desc, "STATICVARIABLES")
    ET.SubElement(s_vars, "SVCURRENTCOMPANY").text = "Rajarshi Shahu Trading Company"

    data = ET.SubElement(body, "DATA")

    # 1. Master Ledger for Party
    tm_master = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
    led = ET.SubElement(tm_master, "LEDGER", {"NAME": p_name, "ACTION": "Create"})
    ET.SubElement(led, "NAME").text = p_name
    ET.SubElement(led, "PARENT").text = parent_group
    # Tally convention: Sundry Creditor credit balance is negative or specified
    raw_op = ledger_report.get("raw_opening_balance", 0.0)
    ET.SubElement(led, "OPENINGBALANCE").text = f"{raw_op:.2f}"
    ET.SubElement(led, "ISBILLWISEON").text = "Yes"
    ET.SubElement(led, "AFFECTSSTOCK").text = "No"
    if party.get("village"):
        addr = ET.SubElement(led, "ADDRESS.LIST")
        ET.SubElement(addr, "ADDRESS").text = f"Village: {party.get('village')}, Dist: Buldhana"
    ET.SubElement(led, "LEDSTATENAME").text = "Maharashtra"
    ET.SubElement(led, "COUNTRYNAME").text = "India"
    if party.get("gstin"):
        reg = ET.SubElement(led, "LEDGERGSTREGDETAILS.LIST")
        ET.SubElement(reg, "GSTREGISTRATIONTYPE").text = "Regular"
        ET.SubElement(reg, "GSTIN").text = party.get("gstin")

    # 2. Vouchers
    for tx in ledger_report.get("transactions", []):
        tm_vch = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        vch_type = "Purchase" if "Purchase" in tx["voucher_type"] else (
            "Payment" if "Payment" in tx["voucher_type"] else (
                "Sales" if "Sales" in tx["voucher_type"] else "Receipt"
            )
        )
        v = ET.SubElement(tm_vch, "VOUCHER", {"VCHTYPE": vch_type, "ACTION": "Create"})
        ET.SubElement(v, "DATE").text = format_tally_date(tx["date"])
        ET.SubElement(v, "VOUCHERTYPENAME").text = vch_type
        ET.SubElement(v, "VOUCHERNUMBER").text = str(tx["voucher_number"])
        ET.SubElement(v, "PARTYLEDGERNAME").text = p_name
        ET.SubElement(v, "PERSISTEDVIEW").text = "Accounting Voucher View"
        ET.SubElement(v, "NARRATION").text = tx.get("particulars", "")

        debit = tx.get("debit", 0.0)
        credit = tx.get("credit", 0.0)

        if vch_type == "Purchase":
            # Party Credited (-), Purchase Debited (+)
            ple = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(ple, "LEDGERNAME").text = p_name
            ET.SubElement(ple, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(ple, "AMOUNT").text = f"-{credit:.2f}"

            pur_le = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(pur_le, "LEDGERNAME").text = "Grain Procurement Account"
            ET.SubElement(pur_le, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(pur_le, "AMOUNT").text = f"{credit:.2f}"

        elif vch_type == "Payment":
            # Party Debited (+), Bank/Cash Credited (-)
            ple = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(ple, "LEDGERNAME").text = p_name
            ET.SubElement(ple, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(ple, "AMOUNT").text = f"{debit:.2f}"

            bank_le = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(bank_le, "LEDGERNAME").text = "Cash / Bank Settlement Account"
            ET.SubElement(bank_le, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(bank_le, "AMOUNT").text = f"-{debit:.2f}"

        elif vch_type == "Sales":
            # Buyer Debited (+), Sales Credited (-)
            ble = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(ble, "LEDGERNAME").text = p_name
            ET.SubElement(ble, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(ble, "AMOUNT").text = f"{debit:.2f}"

            sale_le = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(sale_le, "LEDGERNAME").text = "Grain Sales Account"
            ET.SubElement(sale_le, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(sale_le, "AMOUNT").text = f"-{debit:.2f}"

        elif vch_type == "Receipt":
            # Bank Debited (+), Buyer Credited (-)
            bank_le = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(bank_le, "LEDGERNAME").text = "Bank RTGS Account"
            ET.SubElement(bank_le, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(bank_le, "AMOUNT").text = f"{credit:.2f}"

            ble = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(ble, "LEDGERNAME").text = p_name
            ET.SubElement(ble, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(ble, "AMOUNT").text = f"-{credit:.2f}"

    return pretty_xml(root)


def export_daily_inward_tally_xml(invoices: List[Dict[str, Any]], target_date: str, branch_name: str) -> str:
    """
    Exports Daily Inward Procurement Register into Tally Purchase Vouchers XML.
    """
    root = ET.Element("ENVELOPE")
    hdr = ET.SubElement(root, "HEADER")
    ET.SubElement(hdr, "VERSION").text = "1"
    ET.SubElement(hdr, "TALLYREQUEST").text = "Import"
    ET.SubElement(hdr, "TYPE").text = "Data"
    ET.SubElement(hdr, "ID").text = "Vouchers"

    body = ET.SubElement(root, "BODY")
    desc = ET.SubElement(body, "DESC")
    s_vars = ET.SubElement(desc, "STATICVARIABLES")
    ET.SubElement(s_vars, "SVCURRENTCOMPANY").text = "Rajarshi Shahu Trading Company"

    data = ET.SubElement(body, "DATA")

    # Collect unique farmers and commodities for Master creation
    unique_farmers = set()
    unique_commodities = set()
    for inv in invoices:
        f_name = inv.get("custom_farmer_name") or inv.get("party_name") or "Farmer"
        unique_farmers.add(f_name)
        c_name = inv.get("commodity_name") or "General Grain"
        unique_commodities.add(c_name)

    # 1. Farmer Masters
    for farmer in sorted(unique_farmers):
        tm = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        led = ET.SubElement(tm, "LEDGER", {"NAME": farmer, "ACTION": "Create"})
        ET.SubElement(led, "NAME").text = farmer
        ET.SubElement(led, "PARENT").text = "Sundry Creditors"
        ET.SubElement(led, "ISBILLWISEON").text = "Yes"
        ET.SubElement(led, "AFFECTSSTOCK").text = "No"
        ET.SubElement(led, "LEDSTATENAME").text = "Maharashtra"
        ET.SubElement(led, "COUNTRYNAME").text = "India"

    # 2. Commodity Purchase Ledgers
    for comm in sorted(unique_commodities):
        c_led_name = f"{comm} Purchase Account"
        tm = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        led = ET.SubElement(tm, "LEDGER", {"NAME": c_led_name, "ACTION": "Create"})
        ET.SubElement(led, "NAME").text = c_led_name
        ET.SubElement(led, "PARENT").text = "Purchase Accounts"
        ET.SubElement(led, "AFFECTSSTOCK").text = "Yes"

    # 3. Hamali Expense Ledger
    tm_ham = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
    led_ham = ET.SubElement(tm_ham, "LEDGER", {"NAME": "Mandi Hamali Deduction Account", "ACTION": "Create"})
    ET.SubElement(led_ham, "NAME").text = "Mandi Hamali Deduction Account"
    ET.SubElement(led_ham, "PARENT").text = "Direct Expenses"

    # 4. Inward Purchase Vouchers
    for inv in invoices:
        tm_vch = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        v = ET.SubElement(tm_vch, "VOUCHER", {"VCHTYPE": "Purchase", "ACTION": "Create"})
        inv_date = inv.get("invoice_date") or target_date
        ET.SubElement(v, "DATE").text = format_tally_date(inv_date)
        ET.SubElement(v, "VOUCHERTYPENAME").text = "Purchase"
        tok = inv.get("token_number") or inv.get("id") or "INV"
        ET.SubElement(v, "VOUCHERNUMBER").text = str(tok)
        f_name = inv.get("custom_farmer_name") or inv.get("party_name") or "Farmer"
        ET.SubElement(v, "PARTYLEDGERNAME").text = f_name
        ET.SubElement(v, "PERSISTEDVIEW").text = "Accounting Voucher View"

        comm = inv.get("commodity_name") or "Commodity"
        qtl = float(inv.get("net_quintals") or 0.0)
        rate = float(inv.get("rate_per_quintal") or 0.0)
        gross = float(inv.get("gross_amount") or 0.0)
        hamali = float(inv.get("hamali_charge") or 0.0)
        net_payable = float(inv.get("net_payable_amount") or inv.get("rounded_net_payable") or (gross - hamali))

        narration = f"Procured {qtl:.2f} Qtl {comm} @ Rs.{rate:,.2f}/Qtl from {f_name} at {branch_name} (Bags: {inv.get('bag_count', 0)}, Moisture: {inv.get('moisture_percentage', 0)}%)"
        ET.SubElement(v, "NARRATION").text = narration

        # Credit Farmer for Net Payable
        fle = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(fle, "LEDGERNAME").text = f_name
        ET.SubElement(fle, "ISDEEMEDPOSITIVE").text = "No"
        ET.SubElement(fle, "AMOUNT").text = f"-{net_payable:.2f}"

        # Debit Commodity Purchase Account for Gross
        cle = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(cle, "LEDGERNAME").text = f"{comm} Purchase Account"
        ET.SubElement(cle, "ISDEEMEDPOSITIVE").text = "Yes"
        ET.SubElement(cle, "AMOUNT").text = f"{gross:.2f}"

        # Credit Hamali Deduction if applicable
        if hamali > 0.001:
            hle = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(hle, "LEDGERNAME").text = "Mandi Hamali Deduction Account"
            ET.SubElement(hle, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(hle, "AMOUNT").text = f"-{hamali:.2f}"

    return pretty_xml(root)


def export_daily_outward_tally_xml(orders: List[Dict[str, Any]], target_date: str, branch_name: str) -> str:
    """
    Exports Daily Outward Dispatch Register into Tally Sales Vouchers XML.
    """
    root = ET.Element("ENVELOPE")
    hdr = ET.SubElement(root, "HEADER")
    ET.SubElement(hdr, "VERSION").text = "1"
    ET.SubElement(hdr, "TALLYREQUEST").text = "Import"
    ET.SubElement(hdr, "TYPE").text = "Data"
    ET.SubElement(hdr, "ID").text = "Vouchers"

    body = ET.SubElement(root, "BODY")
    desc = ET.SubElement(body, "DESC")
    s_vars = ET.SubElement(desc, "STATICVARIABLES")
    ET.SubElement(s_vars, "SVCURRENTCOMPANY").text = "Rajarshi Shahu Trading Company"

    data = ET.SubElement(body, "DATA")

    unique_buyers = set()
    unique_commodities = set()
    for o in orders:
        b = (o.get("buyer_name") or "Buyer").strip()
        unique_buyers.add(b)
        c = (o.get("commodity_name") or "General Grain").strip()
        unique_commodities.add(c)

    # 1. Buyer Masters
    for b in sorted(unique_buyers):
        tm = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        led = ET.SubElement(tm, "LEDGER", {"NAME": b, "ACTION": "Create"})
        ET.SubElement(led, "NAME").text = b
        ET.SubElement(led, "PARENT").text = "Sundry Debtors"
        ET.SubElement(led, "ISBILLWISEON").text = "Yes"
        ET.SubElement(led, "AFFECTSSTOCK").text = "No"
        ET.SubElement(led, "LEDSTATENAME").text = "Maharashtra"
        ET.SubElement(led, "COUNTRYNAME").text = "India"

    # 2. Sales Accounts
    for c in sorted(unique_commodities):
        c_led = f"{c} Sales Account"
        tm = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        led = ET.SubElement(tm, "LEDGER", {"NAME": c_led, "ACTION": "Create"})
        ET.SubElement(led, "NAME").text = c_led
        ET.SubElement(led, "PARENT").text = "Sales Accounts"
        ET.SubElement(led, "AFFECTSSTOCK").text = "Yes"

    # 3. Outward Sales Vouchers
    for o in orders:
        tm_vch = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        v = ET.SubElement(tm_vch, "VOUCHER", {"VCHTYPE": "Sales", "ACTION": "Create"})
        o_date = o.get("order_date") or target_date
        ET.SubElement(v, "DATE").text = format_tally_date(o_date)
        ET.SubElement(v, "VOUCHERTYPENAME").text = "Sales"
        challan = o.get("challan_number") or o.get("id") or "OUT"
        ET.SubElement(v, "VOUCHERNUMBER").text = str(challan)
        b_name = o.get("buyer_name") or "Buyer"
        ET.SubElement(v, "PARTYLEDGERNAME").text = b_name
        ET.SubElement(v, "PERSISTEDVIEW").text = "Accounting Voucher View"

        comm = o.get("commodity_name") or "Commodity"
        qtl = float(o.get("net_quintals") or 0.0)
        rate = float(o.get("rate_per_quintal") or 0.0)
        total_bill = float(o.get("total_bill_amount") or o.get("gross_amount") or 0.0)
        veh = o.get("vehicle_number") or "N/A"

        narration = f"Sales dispatch of {qtl:.2f} Qtl {comm} @ Rs.{rate:,.2f}/Qtl to {b_name} from {branch_name} via Vehicle {veh}"
        ET.SubElement(v, "NARRATION").text = narration

        # Debit Buyer for Total Bill Amount
        ble = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(ble, "LEDGERNAME").text = b_name
        ET.SubElement(ble, "ISDEEMEDPOSITIVE").text = "Yes"
        ET.SubElement(ble, "AMOUNT").text = f"{total_bill:.2f}"

        # Credit Sales Account
        sle = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(sle, "LEDGERNAME").text = f"{comm} Sales Account"
        ET.SubElement(sle, "ISDEEMEDPOSITIVE").text = "No"
        ET.SubElement(sle, "AMOUNT").text = f"-{total_bill:.2f}"

    return pretty_xml(root)


def export_consolidated_tally_daybook_xml(invoices: List[Dict[str, Any]],
                                          orders: List[Dict[str, Any]],
                                          ledgers: List[Dict[str, Any]],
                                          target_date: str,
                                          branch_name: str) -> str:
    """
    Exports complete Daybook package:
    - Master creation for all parties and nominal accounts
    - Purchase Vouchers for inward
    - Sales Vouchers for outward
    - Payment Vouchers for cashier payouts
    - Receipt Vouchers for buyer collections
    """
    root = ET.Element("ENVELOPE")
    hdr = ET.SubElement(root, "HEADER")
    ET.SubElement(hdr, "VERSION").text = "1"
    ET.SubElement(hdr, "TALLYREQUEST").text = "Import"
    ET.SubElement(hdr, "TYPE").text = "Data"
    ET.SubElement(hdr, "ID").text = "All Masters and Vouchers"

    body = ET.SubElement(root, "BODY")
    desc = ET.SubElement(body, "DESC")
    s_vars = ET.SubElement(desc, "STATICVARIABLES")
    ET.SubElement(s_vars, "SVCURRENTCOMPANY").text = "Rajarshi Shahu Trading Company"

    data = ET.SubElement(body, "DATA")

    # Collect masters
    creditors = set()
    debtors = set()
    pur_commodities = set()
    sale_commodities = set()

    for inv in invoices:
        creditors.add(inv.get("custom_farmer_name") or inv.get("party_name") or "Farmer")
        pur_commodities.add(inv.get("commodity_name") or "General Grain")

    for o in orders:
        debtors.add(o.get("buyer_name") or "Buyer")
        sale_commodities.add(o.get("commodity_name") or "General Grain")

    # 1. Masters
    for c in sorted(creditors):
        tm = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        led = ET.SubElement(tm, "LEDGER", {"NAME": c, "ACTION": "Create"})
        ET.SubElement(led, "NAME").text = c
        ET.SubElement(led, "PARENT").text = "Sundry Creditors"
        ET.SubElement(led, "ISBILLWISEON").text = "Yes"

    for d in sorted(debtors):
        tm = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        led = ET.SubElement(tm, "LEDGER", {"NAME": d, "ACTION": "Create"})
        ET.SubElement(led, "NAME").text = d
        ET.SubElement(led, "PARENT").text = "Sundry Debtors"
        ET.SubElement(led, "ISBILLWISEON").text = "Yes"

    for pc in sorted(pur_commodities):
        tm = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        led = ET.SubElement(tm, "LEDGER", {"NAME": f"{pc} Purchase Account", "ACTION": "Create"})
        ET.SubElement(led, "NAME").text = f"{pc} Purchase Account"
        ET.SubElement(led, "PARENT").text = "Purchase Accounts"

    for sc in sorted(sale_commodities):
        tm = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        led = ET.SubElement(tm, "LEDGER", {"NAME": f"{sc} Sales Account", "ACTION": "Create"})
        ET.SubElement(led, "NAME").text = f"{sc} Sales Account"
        ET.SubElement(led, "PARENT").text = "Sales Accounts"

    # 2. Inward Purchases
    for inv in invoices:
        tm_vch = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        v = ET.SubElement(tm_vch, "VOUCHER", {"VCHTYPE": "Purchase", "ACTION": "Create"})
        ET.SubElement(v, "DATE").text = format_tally_date(inv.get("invoice_date") or target_date)
        ET.SubElement(v, "VOUCHERTYPENAME").text = "Purchase"
        tok = inv.get("token_number") or inv.get("id") or "INV"
        ET.SubElement(v, "VOUCHERNUMBER").text = str(tok)
        f_name = inv.get("custom_farmer_name") or inv.get("party_name") or "Farmer"
        ET.SubElement(v, "PARTYLEDGERNAME").text = f_name
        ET.SubElement(v, "PERSISTEDVIEW").text = "Accounting Voucher View"

        comm = inv.get("commodity_name") or "Commodity"
        qtl = float(inv.get("net_quintals") or 0.0)
        rate = float(inv.get("rate_per_quintal") or 0.0)
        gross = float(inv.get("gross_amount") or 0.0)
        hamali = float(inv.get("hamali_charge") or 0.0)
        net_payable = float(inv.get("net_payable_amount") or inv.get("rounded_net_payable") or (gross - hamali))

        ET.SubElement(v, "NARRATION").text = f"Procured {qtl:.2f} Qtl {comm} @ Rs.{rate:,.2f}/Qtl from {f_name} (Bags: {inv.get('bag_count', 0)})"

        fle = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(fle, "LEDGERNAME").text = f_name
        ET.SubElement(fle, "ISDEEMEDPOSITIVE").text = "No"
        ET.SubElement(fle, "AMOUNT").text = f"-{net_payable:.2f}"

        cle = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(cle, "LEDGERNAME").text = f"{comm} Purchase Account"
        ET.SubElement(cle, "ISDEEMEDPOSITIVE").text = "Yes"
        ET.SubElement(cle, "AMOUNT").text = f"{gross:.2f}"

        if hamali > 0.001:
            hle = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(hle, "LEDGERNAME").text = "Mandi Hamali Deduction Account"
            ET.SubElement(hle, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(hle, "AMOUNT").text = f"-{hamali:.2f}"

        # If already paid, also generate Payment Voucher
        payout_status = (inv.get("payout_status") or "").upper()
        if payout_status in ["PAID", "PAID_CASH", "RTGS_COMPLETED", "COMPLETED"]:
            tm_pay = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
            vp = ET.SubElement(tm_pay, "VOUCHER", {"VCHTYPE": "Payment", "ACTION": "Create"})
            ET.SubElement(vp, "DATE").text = format_tally_date(inv.get("rtgs_completed_at") or inv.get("created_at") or target_date)
            ET.SubElement(vp, "VOUCHERTYPENAME").text = "Payment"
            ET.SubElement(vp, "VOUCHERNUMBER").text = f"PAY-{tok}"
            ET.SubElement(vp, "PARTYLEDGERNAME").text = f_name
            ET.SubElement(vp, "PERSISTEDVIEW").text = "Accounting Voucher View"
            ET.SubElement(vp, "NARRATION").text = f"Settlement against Token #{tok}"

            pfle = ET.SubElement(vp, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(pfle, "LEDGERNAME").text = f_name
            ET.SubElement(pfle, "ISDEEMEDPOSITIVE").text = "Yes"
            ET.SubElement(pfle, "AMOUNT").text = f"{net_payable:.2f}"

            bank_name = "Bank RTGS Account" if inv.get("weighment_mode") == "RTGS" else "Cash-in-Hand Account"
            pble = ET.SubElement(vp, "ALLLEDGERENTRIES.LIST")
            ET.SubElement(pble, "LEDGERNAME").text = bank_name
            ET.SubElement(pble, "ISDEEMEDPOSITIVE").text = "No"
            ET.SubElement(pble, "AMOUNT").text = f"-{net_payable:.2f}"

    # 3. Outward Sales
    for o in orders:
        tm_vch = ET.SubElement(data, "TALLYMESSAGE", {"xmlns:UDF": "TallyUDF"})
        v = ET.SubElement(tm_vch, "VOUCHER", {"VCHTYPE": "Sales", "ACTION": "Create"})
        ET.SubElement(v, "DATE").text = format_tally_date(o.get("order_date") or target_date)
        ET.SubElement(v, "VOUCHERTYPENAME").text = "Sales"
        challan = o.get("challan_number") or o.get("id") or "OUT"
        ET.SubElement(v, "VOUCHERNUMBER").text = str(challan)
        b_name = o.get("buyer_name") or "Buyer"
        ET.SubElement(v, "PARTYLEDGERNAME").text = b_name
        ET.SubElement(v, "PERSISTEDVIEW").text = "Accounting Voucher View"

        comm = o.get("commodity_name") or "Commodity"
        qtl = float(o.get("net_quintals") or 0.0)
        rate = float(o.get("rate_per_quintal") or 0.0)
        total_bill = float(o.get("total_bill_amount") or o.get("gross_amount") or 0.0)

        ET.SubElement(v, "NARRATION").text = f"Sales dispatch of {qtl:.2f} Qtl {comm} @ Rs.{rate:,.2f}/Qtl to {b_name}"

        ble = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(ble, "LEDGERNAME").text = b_name
        ET.SubElement(ble, "ISDEEMEDPOSITIVE").text = "Yes"
        ET.SubElement(ble, "AMOUNT").text = f"{total_bill:.2f}"

        sle = ET.SubElement(v, "ALLLEDGERENTRIES.LIST")
        ET.SubElement(sle, "LEDGERNAME").text = f"{comm} Sales Account"
        ET.SubElement(sle, "ISDEEMEDPOSITIVE").text = "No"
        ET.SubElement(sle, "AMOUNT").text = f"-{total_bill:.2f}"

    return pretty_xml(root)
