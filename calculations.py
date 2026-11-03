"""
Core calculation engine for Commodity / Mandi ERP.
Exact field formulas for tare, moisture cuts, karda, statutory deductions,
advance loan adjustments, daily min/max bounds, and Section 269ST / 40A(3) compliance.
"""

from typing import Dict, Any, Optional
import math

def calculate_inward_invoice(
    gross_weight_kg: float,
    vehicle_tare_kg: float = 0.0,
    bag_count: int = 0,
    bag_type: str = "LOOSE",
    custom_bag_tare_per_bag: Optional[float] = None,
    moisture_percentage: float = 0.0,
    standard_moisture_percentage: float = 10.0,
    karda_percentage: float = 0.0,
    rate_per_quintal: float = 0.0,
    hamali_rate_per_100kg: Optional[float] = None, # Default Mandi rule: ₹25 on 100 kg from farmer
    hamali_rate_per_bag: float = 0.0,
    tulai_rate_per_bag: float = 0.0,
    silai_rate_per_bag: float = 0.0,
    bardana_rate_per_bag: float = 0.0,
    mandi_cess_percentage: float = 0.0, # No mandi cess or extra charges
    advance_to_deduct: float = 0.0,
    advance_interest_rate_annual: float = 12.0,
    advance_days: int = 0,
    gst_rate: float = 0.0,
    tds_194q_percentage: float = 0.0,
    weighment_mode: str = "MANUAL_YARD",
    weighbridge_cut_per_100kg: float = 0.30  # Exactly 300g (0.30 kg) per 100 kg if measured by weighbridge
) -> Dict[str, Any]:
    """
    Computes exact weighbridge & purchase invoice calculations.
    Standard Mandi rule: Hamali ₹25 on 100 kg from farmer.
    Weighbridge deduction: 300g per 100 kg produce when weighed by weighbridge.
    """
    # 1. Vehicle net weight
    vehicle_net_kg = max(0.0, gross_weight_kg - vehicle_tare_kg)

    # 2. Bag tare deduction
    if custom_bag_tare_per_bag is not None and custom_bag_tare_per_bag >= 0:
        tare_per_bag = custom_bag_tare_per_bag
    elif bag_type == "JUTE_100KG":
        tare_per_bag = 1.0  # 1.0 kg for jute / hessian sack
    elif bag_type == "HDPE_50KG":
        tare_per_bag = 0.5  # 0.5 kg for plastic / woven poly sack
    else:
        tare_per_bag = 0.0  # Loose bulk load
    
    bag_tare_kg = round(bag_count * tare_per_bag, 2)
    uncleaned_produce_kg = max(0.0, vehicle_net_kg - bag_tare_kg)

    # 3. Quality cuts: Moisture (Nami) & Karda (Dust / foreign matter)
    # Moisture deduction applies only on excess above standard threshold
    excess_moisture = max(0.0, moisture_percentage - standard_moisture_percentage)
    moisture_cut_kg = round(uncleaned_produce_kg * (excess_moisture / 100.0), 2)
    
    karda_cut_kg = round(uncleaned_produce_kg * (max(0.0, karda_percentage) / 100.0), 2)

    # 4. Weighbridge Scale Allowance Deduction (300g per 100 kg)
    if "WEIGHBRIDGE" in str(weighment_mode).upper():
        weighbridge_cut_kg = round(uncleaned_produce_kg * (weighbridge_cut_per_100kg / 100.0), 2)
    else:
        weighbridge_cut_kg = 0.0

    # 5. Net Billable Weight in Kg & Quintals (1 Quintal = 100 Kg)
    net_weight_kg = round(max(0.0, uncleaned_produce_kg - moisture_cut_kg - karda_cut_kg - weighbridge_cut_kg), 2)
    net_quintals = round(net_weight_kg / 100.0, 4)

    # 5. Gross Produce Amount
    gross_amount = round(net_quintals * rate_per_quintal, 2)

    # 6. Hamali & Deductions: Exactly ₹25 on 100 kg (per Quintal) from farmer
    if hamali_rate_per_100kg is not None:
        hamali_charge = round(net_quintals * hamali_rate_per_100kg, 2)
    elif hamali_rate_per_bag > 0 and bag_count > 0:
        hamali_charge = round(bag_count * hamali_rate_per_bag, 2)
    else:
        hamali_charge = round(net_quintals * 25.0, 2) # Standard Mandi farmer hamali: ₹25 on 100 kg

    tulai_charge = round(bag_count * tulai_rate_per_bag, 2)
    silai_charge = round(bag_count * silai_rate_per_bag, 2)
    bardana_deduction = round(bag_count * bardana_rate_per_bag, 2)
    mandi_cess_amount = 0.0  # Mandi cess removed across entire software

    # 7. Advance Loan & Interest
    advance_deducted = round(max(0.0, advance_to_deduct), 2)
    if advance_deducted > 0 and advance_days > 0 and advance_interest_rate_annual > 0:
        interest_adjusted = round((advance_deducted * (advance_interest_rate_annual / 100.0) * advance_days) / 365.0, 2)
    else:
        interest_adjusted = 0.0

    # 8. Tax & TDS
    gst_amount = round(gross_amount * (gst_rate / 100.0), 2)
    tds_194q_amount = round(gross_amount * (tds_194q_percentage / 100.0), 2)

    # 9. Total Deductions & Net Payable
    total_mandi_deductions = round(hamali_charge + tulai_charge + silai_charge + bardana_deduction, 2)
    total_loan_deductions = round(advance_deducted + interest_adjusted, 2)
    
    net_payable_amount = round(
        gross_amount - total_mandi_deductions - total_loan_deductions + gst_amount - tds_194q_amount, 
        2
    )

    return {
        "vehicle_net_kg": vehicle_net_kg,
        "bag_tare_kg": bag_tare_kg,
        "uncleaned_produce_kg": uncleaned_produce_kg,
        "excess_moisture_pct": excess_moisture,
        "moisture_cut_kg": moisture_cut_kg,
        "karda_cut_kg": karda_cut_kg,
        "weighbridge_cut_kg": weighbridge_cut_kg,
        "net_weight_kg": net_weight_kg,
        "net_quintals": net_quintals,
        "gross_amount": gross_amount,
        "hamali_charge": hamali_charge,
        "tulai_charge": tulai_charge,
        "silai_charge": silai_charge,
        "bardana_deduction": bardana_deduction,
        "mandi_cess_amount": mandi_cess_amount,
        "total_mandi_deductions": total_mandi_deductions,
        "advance_adjusted": advance_deducted,
        "interest_adjusted": interest_adjusted,
        "total_loan_deductions": total_loan_deductions,
        "gst_rate": gst_rate,
        "gst_amount": gst_amount,
        "tds_194q_amount": tds_194q_amount,
        "net_payable_amount": max(0.0, net_payable_amount)
    }

def calculate_outward_order(
    net_weight_kg: float,
    rate_per_quintal: float,
    hamali_per_100kg: float = 25.0
) -> Dict[str, Any]:
    """
    Computes exact outward sales/dispatch invoice calculations.
    The cashier types the price of hamali per 100 kg (per Quintal).
    """
    net_quintals = round(net_weight_kg / 100.0, 4)
    gross_amount = round(net_quintals * rate_per_quintal, 2)
    hamali_amount = round(net_quintals * max(0.0, hamali_per_100kg), 2)
    total_bill_amount = round(gross_amount + hamali_amount, 2)

    return {
        "net_weight_kg": net_weight_kg,
        "net_quintals": net_quintals,
        "rate_per_quintal": rate_per_quintal,
        "gross_amount": gross_amount,
        "hamali_per_100kg": hamali_per_100kg,
        "hamali_amount": hamali_amount,
        "total_bill_amount": total_bill_amount
    }

def check_cash_compliance(
    party_type: str,
    payout_mode: str,
    payout_amount: float,
    today_cumulative_cash_to_party: float
) -> Dict[str, Any]:
    """
    Enforces statutory Income Tax cash limits:
    - Section 269ST: Max ₹1,99,999 cash per person per day.
    - Section 40A(3): Max ₹10,000 cash to non-cultivators (Stockers/Traders).
    """
    if payout_mode != "CASH":
        return {"allowed": True, "reason": "Non-cash banking payment is fully compliant."}

    # Rule 1: Section 269ST applies to ALL persons (including farmers)
    potential_total = today_cumulative_cash_to_party + payout_amount
    if potential_total >= 200000.0:
        return {
            "allowed": False,
            "rule": "SECTION_269ST",
            "reason": (
                f"Statutory Cash Limit Exceeded (Section 269ST): "
                f"Total cash to this party today would reach ₹{potential_total:,.2f} (Ceiling is ₹1,99,999). "
                f"Must disburse via Bank Transfer (NEFT/RTGS/IMPS) or Account Payee Cheque."
            )
        }

    # Rule 2: Section 40A(3) applies strictly to Stockers/Traders (Farmers exempt under Rule 6DD(e))
    if party_type == "STOCKER" and payout_amount > 10000.0:
        return {
            "allowed": False,
            "rule": "SECTION_40A3",
            "reason": (
                f"Section 40A(3) Disallowance Alert: "
                f"Cash payment to a registered Stocker/Merchant cannot exceed ₹10,000 per day. "
                f"Rule 6DD exemption applies only to primary agricultural cultivators (Farmers). "
                f"Must disburse via Bank Transfer."
            )
        }

    return {"allowed": True, "reason": "Compliant"}

def check_rate_corridor(
    rate_per_quintal: float,
    min_rate: float,
    max_rate: float
) -> Dict[str, Any]:
    """
    Validates if proposed purchase rate is within daily bounds set by Central Accounts.
    """
    if min_rate <= rate_per_quintal <= max_rate:
        return {"valid": True, "requires_override": False, "message": "Rate is within daily approved corridor."}
    
    if rate_per_quintal > max_rate:
        return {
            "valid": False,
            "requires_override": True,
            "message": f"Proposed rate ₹{rate_per_quintal:,.2f} exceeds Central Accounts Max limit of ₹{max_rate:,.2f}/Qtl."
        }
    else:
        return {
            "valid": False,
            "requires_override": True,
            "message": f"Proposed rate ₹{rate_per_quintal:,.2f} is below Central Accounts Min limit of ₹{min_rate:,.2f}/Qtl."
        }

def calculate_cash_payout_with_roundup(net_payable: float) -> Dict[str, Any]:
    """
    Rounds up fractional cash payout paisa to the nearest rupee,
    balancing via Round-Off Account.
    Example: 133,170.40 -> rounded payout = 133,171.00, round_off = +0.60
             133,170.00 -> rounded payout = 133,170.00, round_off = 0.00
    """
    rounded = float(math.ceil(net_payable))
    round_off = round(rounded - net_payable, 2)
    return {
        "net_payable": net_payable,
        "rounded_cash_payout": rounded,
        "round_off_amount": round_off
    }

def validate_cash_denominations(
    expected_amount: float,
    notes_500: int = 0,
    notes_200: int = 0,
    notes_100: int = 0,
    notes_50: int = 0,
    notes_20: int = 0,
    notes_10: int = 0,
    coins: int = 0
) -> Dict[str, Any]:
    """
    Validates physical cash note counts against the expected rounded cash payout.
    """
    total = (
        notes_500 * 500 +
        notes_200 * 200 +
        notes_100 * 100 +
        notes_50 * 50 +
        notes_20 * 20 +
        notes_10 * 10 +
        coins
    )
    diff = round(total - expected_amount, 2)
    return {
        "valid": diff == 0.0,
        "total_counted": float(total),
        "expected_amount": float(expected_amount),
        "difference": diff,
        "notes_breakdown": {
            500: notes_500,
            200: notes_200,
            100: notes_100,
            50: notes_50,
            20: notes_20,
            10: notes_10,
            "coins": coins
        }
    }

def number_to_inr_words(amount: float) -> str:
    """
    Converts a numerical INR currency amount into standard Indian currency words
    (Crores, Lakhs, Thousands, Hundreds, Rupees, and Paise).
    Example: 245600.50 -> 'Two Lakh Forty Five Thousand Six Hundred Rupees and Fifty Paise Only'
    """
    try:
        amount = round(float(amount or 0.0), 2)
        if amount == 0:
            return "Zero Rupees Only"
        
        ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                "Seventeen", "Eighteen", "Nineteen"]
        tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
        
        def two_digits(n: int) -> str:
            if n < 20:
                return ones[n]
            return tens[n // 10] + (" " + ones[n % 10] if n % 10 != 0 else "")
            
        def three_digits(n: int) -> str:
            res = ""
            if n >= 100:
                res += ones[n // 100] + " Hundred "
                n %= 100
            if n > 0:
                res += two_digits(n)
            return res.strip()
            
        rupees = int(amount)
        paise = int(round((amount - rupees) * 100))
        
        parts = []
        crores = rupees // 10000000
        rupees %= 10000000
        if crores:
            parts.append(two_digits(crores) + " Crore")
            
        lakhs = rupees // 100000
        rupees %= 100000
        if lakhs:
            parts.append(two_digits(lakhs) + " Lakh")
            
        thousands = rupees // 1000
        rupees %= 1000
        if thousands:
            parts.append(two_digits(thousands) + " Thousand")
            
        if rupees:
            parts.append(three_digits(rupees))
            
        words = " ".join(parts).strip()
        words = words + " Rupees"
        if paise > 0:
            words += " and " + two_digits(paise) + " Paise"
        words += " Only"
        return words
    except Exception:
        return ""


