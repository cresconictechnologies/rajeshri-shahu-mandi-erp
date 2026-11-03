"""
Unit Tests for New Commodity Standards & Assaying Profiles.
Tests the 8 newly added commodities:
1. Dollar Chana (Kabuli / डॉलर चना)
2. Rajma (Red Kidney Beans / राजमा)
3. Masoor (Red Lentil / मसूर)
4. Groundnut / Bhuimug (भुईमूग)
5. Jowar / Sorghum (ज्वारी)
6. Bajra / Pearl Millet (बाजरी)
7. Moong (Green Gram)
8. Urad (Black Gram)
"""

import os
import sys
import io
import unittest
from PIL import Image

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quality_engine import (
    COMMODITY_STANDARDS,
    get_standards_for_commodity,
    analyze_grain_sample_image,
    calculate_mandi_corridor_rate,
    format_qc_slip_text,
    generate_qc_ticket_number
)


class TestNewCommodityStandards(unittest.TestCase):

    REQUIRED_COMMODITIES = [
        "Dollar Chana (Kabuli / डॉलर चना)",
        "Rajma (Red Kidney Beans / राजमा)",
        "Masoor (Red Lentil / मसूर)",
        "Groundnut / Bhuimug (भुईमूग)",
        "Jowar / Sorghum (ज्वारी)",
        "Bajra / Pearl Millet (बाजरी)",
        "Moong (Green Gram)",
        "Urad (Black Gram)"
    ]

    REQUIRED_FIELDS = [
        ("standard_moisture_pct", float),
        ("max_moisture_limit_pct", float),
        ("max_karda_pct", float),
        ("max_damaged_pct", float),
        ("max_green_seeds_pct", float),
        ("max_broken_split_pct", float),
        ("max_shriveled_pct", float),
        ("max_admixture_pct", float),
        ("standard_breeds", list),
        ("default_breed", str),
        ("default_min_rate", float),
        ("default_target_rate", float),
        ("default_max_rate", float),
        ("sortex_profile", dict)
    ]

    REQUIRED_SORTEX_FIELDS = [
        ("target_appearance", str),
        ("optical_color_defects", list),
        ("profile_shape_defects", list),
        ("foreign_matter_defects", list),
        ("sortex_clean_yield_target_pct", float),
        ("sortex_reject_ceiling_pct", float)
    ]

    def _create_synthetic_grain_image(self, color=(210, 190, 160), size=(640, 480)) -> bytes:
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    def test_01_all_8_commodities_exist_in_standards_dict(self):
        """Task 1 Verification: All 8 commodities must exist in COMMODITY_STANDARDS with full schemas."""
        for comm in self.REQUIRED_COMMODITIES:
            self.assertIn(comm, COMMODITY_STANDARDS, f"Commodity '{comm}' is missing from COMMODITY_STANDARDS!")
            std = COMMODITY_STANDARDS[comm]

            # Verify top-level fields and types
            for field_name, expected_type in self.REQUIRED_FIELDS:
                self.assertIn(field_name, std, f"Field '{field_name}' missing for commodity '{comm}'")
                val = std[field_name]
                if expected_type in (float, int):
                    self.assertTrue(isinstance(val, (float, int)), f"Field '{field_name}' must be numeric, got {type(val)}")
                else:
                    self.assertIsInstance(val, expected_type, f"Field '{field_name}' must be {expected_type}, got {type(val)}")

            # Check logical value boundaries
            self.assertGreater(std["standard_moisture_pct"], 0.0)
            self.assertGreater(std["max_moisture_limit_pct"], std["standard_moisture_pct"])
            self.assertGreater(std["max_karda_pct"], 0.0)
            self.assertGreater(std["max_damaged_pct"], 0.0)
            self.assertGreater(std["default_min_rate"], 1000.0)
            self.assertGreater(std["default_target_rate"], std["default_min_rate"])
            self.assertGreater(std["default_max_rate"], std["default_target_rate"])

            # Verify standard_breeds non-empty and default_breed belongs to standard_breeds
            self.assertGreaterEqual(len(std["standard_breeds"]), 3, f"At least 3 breeds expected for '{comm}'")
            self.assertIn(std["default_breed"], std["standard_breeds"])

            # Verify sortex_profile structure
            sortex = std["sortex_profile"]
            for s_field, s_type in self.REQUIRED_SORTEX_FIELDS:
                self.assertIn(s_field, sortex, f"Sortex field '{s_field}' missing for '{comm}'")
                s_val = sortex[s_field]
                if s_type in (float, int):
                    self.assertTrue(isinstance(s_val, (float, int)))
                else:
                    self.assertIsInstance(s_val, s_type)

            self.assertGreaterEqual(len(sortex["optical_color_defects"]), 2)
            self.assertGreaterEqual(len(sortex["profile_shape_defects"]), 2)
            self.assertGreaterEqual(len(sortex["foreign_matter_defects"]), 2)
            self.assertGreaterEqual(sortex["sortex_clean_yield_target_pct"], 90.0)
            self.assertLessEqual(sortex["sortex_reject_ceiling_pct"], 10.0)

    def test_02_get_standards_resolves_all_8_without_soybean_fallback(self):
        """Task 2 Verification: get_standards_for_commodity(...) must resolve each commodity without falling back to Soyabean."""
        soya_std = COMMODITY_STANDARDS["Soyabean (Yellow)"]
        soya_default_breed = soya_std["default_breed"]

        for comm in self.REQUIRED_COMMODITIES:
            resolved = get_standards_for_commodity(comm)
            self.assertIsNotNone(resolved, f"Failed to resolve standards for '{comm}'")
            # Must not fall back to Soyabean
            self.assertNotEqual(
                resolved["default_breed"],
                soya_default_breed,
                f"Commodity '{comm}' incorrectly fell back to Soyabean!"
            )
            # Default breed must match the commodity's own standard
            expected_breed = COMMODITY_STANDARDS[comm]["default_breed"]
            self.assertEqual(resolved["default_breed"], expected_breed)

    def test_03_get_standards_disambiguation_and_aliases(self):
        """Verifies that short names and aliases resolve to the correct commodity."""
        aliases = [
            ("Dollar Chana", "Dollar / Mexican Bold (11-12mm Export Grade)"),
            ("Kabuli Chana", "Dollar / Mexican Bold (11-12mm Export Grade)"),
            ("डॉलर चना", "Dollar / Mexican Bold (11-12mm Export Grade)"),
            ("Chana (Desi)", "Vijay (विजय हरभरा / Desi Brown)"),
            ("Rajma", "Red Kidney (Lal Bold Kidney Variety)"),
            ("Red Kidney Beans", "Red Kidney (Lal Bold Kidney Variety)"),
            ("राजमा", "Red Kidney (Lal Bold Kidney Variety)"),
            ("Masoor", "DPL-62 (Sheri Bold Brown)"),
            ("Red Lentil", "DPL-62 (Sheri Bold Brown)"),
            ("मसूर", "DPL-62 (Sheri Bold Brown)"),
            ("Groundnut", "TAG-24 (Semi-Dwarf Early Bold)"),
            ("Bhuimug", "TAG-24 (Semi-Dwarf Early Bold)"),
            ("भुईमूग", "TAG-24 (Semi-Dwarf Early Bold)"),
            ("Jowar", "Maldandi M-35-1 (Pearly White Roti King)"),
            ("Sorghum", "Maldandi M-35-1 (Pearly White Roti King)"),
            ("ज्वारी", "Maldandi M-35-1 (Pearly White Roti King)"),
            ("Bajra", "ICTP-8203 (Dhanshakti High-Iron Bold)"),
            ("Pearl Millet", "ICTP-8203 (Dhanshakti High-Iron Bold)"),
            ("बाजरी", "ICTP-8203 (Dhanshakti High-Iron Bold)"),
            ("Moong", "Vaibhav (BM-2002-1 Shiny Green)"),
            ("Green Gram", "Vaibhav (BM-2002-1 Shiny Green)"),
            ("Urad", "TAU-1 (Maharashtra High Yield Standard Bold)"),
            ("Black Gram", "TAU-1 (Maharashtra High Yield Standard Bold)")
        ]
        for alias, expected_breed in aliases:
            resolved = get_standards_for_commodity(alias)
            self.assertEqual(
                resolved["default_breed"],
                expected_breed,
                f"Alias '{alias}' resolved to '{resolved['default_breed']}' instead of '{expected_breed}'"
            )

    def test_04_mock_analysis_and_corridor_rate_for_dollar_chana(self):
        """Task 3 Verification (Part A): Mock sample analysis and corridor rate deduction for Dollar Chana."""
        dummy_img = self._create_synthetic_grain_image(color=(230, 220, 200)) # Light cream color
        comm_name = "Dollar Chana (Kabuli / डॉलर चना)"
        std = COMMODITY_STANDARDS[comm_name]

        # 1. Run full CV sample analysis
        analysis = analyze_grain_sample_image(dummy_img, comm_name, measured_moisture=11.5)
        self.assertEqual(analysis["commodity_name"], comm_name)
        self.assertEqual(analysis["moisture_pct"], 11.5)
        self.assertEqual(analysis["dominant_breed"], std["default_breed"])
        self.assertIn("karda_pct", analysis)
        self.assertIn("damaged_pct", analysis)
        self.assertIn("sortex_clean_yield_pct", analysis)
        self.assertIn("sortex_grade", analysis)

        # 2. Test corridor calculation with clean grain (no excess defects -> FAQ_GRADE_1)
        clean_analysis = {
            "moisture_pct": 9.5,
            "karda_pct": 0.8,      # Under 1.0% limit
            "damaged_pct": 1.5,    # Under 2.0% limit
            "green_seeds_pct": 1.0,# Under 1.5% limit
            "broken_split_pct": 1.5,
            "shriveled_pct": 1.8,
            "admixture_pct": 1.5   # Under 3.0% limit
        }
        res_clean = calculate_mandi_corridor_rate(comm_name, clean_analysis)
        self.assertEqual(res_clean["faq_grade"], "FAQ_GRADE_1")
        self.assertEqual(res_clean["total_quality_deduction_per_qtl"], 0.0)
        self.assertGreaterEqual(res_clean["suggested_buying_rate_per_qtl"], std["default_target_rate"])

        # 3. Test corridor calculation with excess karda & damaged (quality deduction)
        # Limit: karda 1.0%, damaged 2.0%
        # excess karda = 2.5 - 1.0 = 1.5% -> deduction = 1.5 * 35.0 = 52.50
        # excess damaged = 4.0 - 2.0 = 2.0% -> deduction = 2.0 * 28.0 = 56.00
        # total deduction = 108.50
        docked_analysis = {
            "moisture_pct": 11.0,
            "karda_pct": 2.5,
            "damaged_pct": 4.0,
            "green_seeds_pct": 1.0,
            "broken_split_pct": 1.5,
            "shriveled_pct": 2.0,
            "admixture_pct": 2.0
        }
        res_docked = calculate_mandi_corridor_rate(comm_name, docked_analysis)
        self.assertAlmostEqual(res_docked["total_quality_deduction_per_qtl"], 108.50, places=2)
        self.assertEqual(len(res_docked["refraction_alerts"]), 3) # Excess karda, excess damaged, excess moisture (11.0 > 10.0)
        self.assertIn("Excess Foreign Matter: 2.5% (Limit: 1.0%, -Rs.52.5/Qtl)", res_docked["refraction_alerts"][0])
        self.assertIn("Rain Damage / Fungal: 4.0% (Limit: 2.0%, -Rs.56.0/Qtl)", res_docked["refraction_alerts"][1])

    def test_05_mock_analysis_and_corridor_rate_for_rajma(self):
        """Task 3 Verification (Part B): Mock sample analysis and corridor rate deduction for Rajma."""
        dummy_img = self._create_synthetic_grain_image(color=(140, 50, 40)) # Deep crimson
        comm_name = "Rajma (Red Kidney Beans / राजमा)"
        std = COMMODITY_STANDARDS[comm_name]

        # 1. Run full CV sample analysis
        analysis = analyze_grain_sample_image(dummy_img, comm_name, measured_moisture=12.0)
        self.assertEqual(analysis["commodity_name"], comm_name)
        self.assertEqual(analysis["dominant_breed"], std["default_breed"])
        self.assertIn("sortex_profile", analysis)
        self.assertEqual(analysis["sortex_profile"]["target_appearance"], std["sortex_profile"]["target_appearance"])

        # 2. Test Grade 2 (FAQ_GRADE_2: <= 2 alerts, karda <= 3.5%, moisture <= max_limit)
        # Limits: karda 1.0%, damaged 2.5%
        # Sample: karda 2.0% (excess 1.0% * 35.0 = 35.00)
        #         damaged 3.5% (excess 1.0% * 28.0 = 28.00)
        # Total deduction = 35.00 + 28.00 = 63.00
        sample_faq2 = {
            "moisture_pct": 11.0, # <= 11.0 standard
            "karda_pct": 2.0,     # alert 1
            "damaged_pct": 3.5,   # alert 2
            "green_seeds_pct": 0.8,
            "broken_split_pct": 1.2,
            "shriveled_pct": 1.5,
            "admixture_pct": 2.5  # <= 3.0 limit (no alert)
        }
        res_faq2 = calculate_mandi_corridor_rate(comm_name, sample_faq2)
        self.assertEqual(res_faq2["faq_grade"], "FAQ_GRADE_2")
        self.assertAlmostEqual(res_faq2["total_quality_deduction_per_qtl"], 63.00, places=2)
        self.assertEqual(res_faq2["corridor_target_rate"], std["default_target_rate"])
        self.assertAlmostEqual(res_faq2["suggested_buying_rate_per_qtl"], std["default_target_rate"] - 63.00, places=2)

        # 3. Test Grade 3 (NON_FAQ: > 2 alerts)
        # Adding excess admixture (4.5% > 3.0% -> alert 3: 1.5% * 18 = 27.00)
        # Total deduction = 63.00 + 27.00 = 90.00
        sample_non_faq = {
            "moisture_pct": 11.0,
            "karda_pct": 2.0,
            "damaged_pct": 3.5,
            "green_seeds_pct": 0.8,
            "broken_split_pct": 1.2,
            "shriveled_pct": 1.5,
            "admixture_pct": 4.5
        }
        res_non_faq = calculate_mandi_corridor_rate(comm_name, sample_non_faq)
        self.assertEqual(res_non_faq["faq_grade"], "NON_FAQ")
        self.assertAlmostEqual(res_non_faq["total_quality_deduction_per_qtl"], 90.00, places=2)
        # For non-faq, suggested rate is max(min_rate - 150, min_rate - deduction)
        expected_non_faq_rate = max(std["default_min_rate"] - 150.0, std["default_min_rate"] - 90.00)
        self.assertAlmostEqual(res_non_faq["suggested_buying_rate_per_qtl"], expected_non_faq_rate, places=2)

    def test_06_qc_ticket_and_slip_generation_for_new_commodities(self):
        """Verifies QC thermal slip generation formatting for new commodities."""
        for comm in ["Dollar Chana (Kabuli / डॉलर चना)", "Rajma (Red Kidney Beans / राजमा)", "Groundnut / Bhuimug (भुईमूग)"]:
            std = COMMODITY_STANDARDS[comm]
            qc_data = {
                "ticket_no": generate_qc_ticket_number("BHD"),
                "vehicle_no": "MH-28-AB-9921",
                "farmer_name": "Gajanan Patil",
                "commodity_name": comm,
                "moisture_pct": std["standard_moisture_pct"],
                "karda_pct": std["max_karda_pct"],
                "damaged_pct": std["max_damaged_pct"],
                "green_seeds_pct": std["max_green_seeds_pct"],
                "broken_split_pct": std["max_broken_split_pct"],
                "shriveled_pct": std["max_shriveled_pct"],
                "uniformity_index": 94.5,
                "dominant_breed": std["default_breed"],
                "breed_purity_pct": 98.0,
                "admixture_pct": 1.0,
                "breed_status": "FAQ Grade 1 (Pure Lot)",
                "sortex_clean_yield_pct": 96.5,
                "sortex_reject_pct": 3.5,
                "sortex_grade": "SORTEX Grade A (Export / Premium Mill Quality)",
                "corridor_min_rate": std["default_min_rate"],
                "corridor_max_rate": std["default_max_rate"],
                "grade_label": "Grade 1 (Premium FAQ)",
                "suggested_buying_rate_per_qtl": std["default_target_rate"]
            }
            slip = format_qc_slip_text(qc_data)
            self.assertIn("RAJARSHI SHAHU TRADING", slip)
            self.assertIn(comm, slip)
            self.assertIn(std["default_breed"], slip)
            self.assertIn(f"Rs. {std['default_target_rate']:,.2f}", slip)


if __name__ == "__main__":
    unittest.main()
