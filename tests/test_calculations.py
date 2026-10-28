"""
Unit tests for calculations and statutory compliance logic.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculations import (
    calculate_inward_invoice,
    check_cash_compliance,
    check_rate_corridor,
    calculate_cash_payout_with_roundup,
    validate_cash_denominations
)

class TestCommodityCalculations(unittest.TestCase):

    def test_standard_weighment_and_tare(self):
        # 5,000 kg gross, 2,000 kg tare vehicle, 60 bags of 0.5 kg (30 kg bag tare)
        # uncleaned produce = 2,970 kg
        # moisture 10% (standard 10% -> 0 cut), karda 0% -> net 2,970 kg -> 29.7000 quintals
        # rate 4,500/Qtl -> gross = 29.7 * 4500 = 133,650
        res = calculate_inward_invoice(
            gross_weight_kg=5000.0,
            vehicle_tare_kg=2000.0,
            bag_count=60,
            bag_type="HDPE_50KG",
            moisture_percentage=10.0,
            standard_moisture_percentage=10.0,
            karda_percentage=0.0,
            rate_per_quintal=4500.0,
            hamali_rate_per_bag=5.0,
            tulai_rate_per_bag=2.0,
            silai_rate_per_bag=1.0,
            bardana_rate_per_bag=0.0
        )
        self.assertEqual(res["vehicle_net_kg"], 3000.0)
        self.assertEqual(res["bag_tare_kg"], 30.0)
        self.assertEqual(res["uncleaned_produce_kg"], 2970.0)
        self.assertEqual(res["moisture_cut_kg"], 0.0)
        self.assertEqual(res["karda_cut_kg"], 0.0)
        self.assertEqual(res["net_weight_kg"], 2970.0)
        self.assertEqual(res["net_quintals"], 29.7)
        self.assertEqual(res["gross_amount"], 133650.0)
        self.assertEqual(res["hamali_charge"], 300.0)   # 60 * 5
        self.assertEqual(res["tulai_charge"], 120.0)    # 60 * 2
        self.assertEqual(res["silai_charge"], 60.0)     # 60 * 1
        self.assertEqual(res["total_mandi_deductions"], 480.0)
        self.assertEqual(res["net_payable_amount"], 133650.0 - 480.0)

    def test_moisture_and_karda_deduction(self):
        # 10,000 kg gross, 4,000 kg vehicle tare = 6,000 kg.
        # 100 Jute bags = 100 kg bag tare -> 5,900 kg uncleaned.
        # Moisture 13% with 10% standard = 3% cut on 5,900 = 177 kg.
        # Karda 1% on 5,900 = 59 kg.
        # Net weight = 5,900 - 177 - 59 = 5,664 kg = 56.6400 quintals.
        res = calculate_inward_invoice(
            gross_weight_kg=10000.0,
            vehicle_tare_kg=4000.0,
            bag_count=100,
            bag_type="JUTE_100KG",
            moisture_percentage=13.0,
            standard_moisture_percentage=10.0,
            karda_percentage=1.0,
            rate_per_quintal=2700.0
        )
        self.assertEqual(res["bag_tare_kg"], 100.0)
        self.assertEqual(res["uncleaned_produce_kg"], 5900.0)
        self.assertEqual(res["moisture_cut_kg"], 177.0)
        self.assertEqual(res["karda_cut_kg"], 59.0)
        self.assertEqual(res["net_weight_kg"], 5664.0)
        self.assertEqual(res["net_quintals"], 56.64)
        self.assertEqual(res["gross_amount"], round(56.64 * 2700.0, 2))

    def test_advance_and_interest_adjustment(self):
        # Gross 100,000, deductions 1,000, advance 20,000 with 12% interest for 60 days
        # interest = (20,000 * 0.12 * 60) / 365 = 394.52
        res = calculate_inward_invoice(
            gross_weight_kg=3000.0,
            vehicle_tare_kg=1000.0,
            bag_count=20,
            rate_per_quintal=5000.0,
            advance_to_deduct=20000.0,
            advance_interest_rate_annual=12.0,
            advance_days=60
        )
        self.assertEqual(res["advance_adjusted"], 20000.0)
        self.assertEqual(res["interest_adjusted"], 394.52)

    def test_sec_269st_cash_ceiling(self):
        # Cumulative today 150,000. New payout 60,000. Total = 210,000 > 199,999 -> Must Block!
        check = check_cash_compliance(
            party_type="FARMER",
            payout_mode="CASH",
            payout_amount=60000.0,
            today_cumulative_cash_to_party=150000.0
        )
        self.assertFalse(check["allowed"])
        self.assertEqual(check["rule"], "SECTION_269ST")

        # Below limit: Cumulative today 50,000. New payout 40,000. Total = 90,000 -> Allowed
        check_ok = check_cash_compliance(
            party_type="FARMER",
            payout_mode="CASH",
            payout_amount=40000.0,
            today_cumulative_cash_to_party=50000.0
        )
        self.assertTrue(check_ok["allowed"])

    def test_sec_40a3_stocker_cash_limit(self):
        # Stocker cash payout > 10,000 -> Blocked under 40A(3)
        check_stocker = check_cash_compliance(
            party_type="STOCKER",
            payout_mode="CASH",
            payout_amount=15000.0,
            today_cumulative_cash_to_party=0.0
        )
        self.assertFalse(check_stocker["allowed"])
        self.assertEqual(check_stocker["rule"], "SECTION_40A3")

        # Bank transfer for stocker -> Always allowed
        check_bank = check_cash_compliance(
            party_type="STOCKER",
            payout_mode="BANK_TRANSFER",
            payout_amount=500000.0,
            today_cumulative_cash_to_party=0.0
        )
        self.assertTrue(check_bank["allowed"])

    def test_rate_corridor(self):
        # Min 4400, Max 4800. Rate 4600 -> Valid
        self.assertTrue(check_rate_corridor(4600, 4400, 4800)["valid"])
        # Rate 4900 -> Exceeds max, requires override
        res_high = check_rate_corridor(4900, 4400, 4800)
        self.assertFalse(res_high["valid"])
        self.assertTrue(res_high["requires_override"])

    def test_cash_roundup(self):
        # 133,170.40 -> rounds UP to 133,171.00 with round_off 0.60
        res = calculate_cash_payout_with_roundup(133170.40)
        self.assertEqual(res["rounded_cash_payout"], 133171.0)
        self.assertEqual(res["round_off_amount"], 0.60)

        # Whole rupee stays intact
        res_exact = calculate_cash_payout_with_roundup(50000.00)
        self.assertEqual(res_exact["rounded_cash_payout"], 50000.0)
        self.assertEqual(res_exact["round_off_amount"], 0.0)

    def test_denomination_validation(self):
        # Payout 2,850: 5x500 (2500) + 1x200 (200) + 1x100 (100) + 1x50 (50) = 2850
        v = validate_cash_denominations(2850.0, notes_500=5, notes_200=1, notes_100=1, notes_50=1)
        self.assertTrue(v["valid"])
        self.assertEqual(v["total_counted"], 2850.0)
        self.assertEqual(v["difference"], 0.0)

        # Mismatch test
        v_err = validate_cash_denominations(2850.0, notes_500=4)
        self.assertFalse(v_err["valid"])
        self.assertEqual(v_err["difference"], -850.0)

if __name__ == "__main__":
    unittest.main()
