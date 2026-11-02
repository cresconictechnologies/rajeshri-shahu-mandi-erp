"""
Test Sortex Optical Sorter Factors & Measure Accuracy Across Real Commodity Images.
Evaluates:
  1. Chana (Desi Gram) - Pure sample (Photo 1) vs Soybean Admixture (Photo 2)
  2. Soybean (Yellow) - 5-class multi-defect specimen (soybean_seeds_benchmark.png)
  3. Mustard (Rayda) - Real commercial lots with yellow sarson admixture (mustard_seeds1.jpg & seeds2.jpg)
  4. Wheat (Lokwan/Mill) - Real defect samples with black point & fusarium (wheat_01.jpg - 04.jpg)
"""

import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__)))

from quality_engine import analyze_grain_sample_image, COMMODITY_STANDARDS

def run_sortex_benchmark():
    test_cases = [
        {
            "id": "CHANA_PURE",
            "commodity": "Chana (Desi) / Harbhara (हरभरा)",
            "image_path": "C:/Users/visha/.gemini/antigravity/brain/8940d80f-5c6a-4a54-8376-f92e236fc388/photo1_sample.jpg",
            "ground_truth": "Pure Desi Chana lot, 0% Soybean Admixture, <2% Pod Chaff, Clean Floor",
            "expected_sortex_grade": "SORTEX Grade A (Export / Premium Mill Quality)"
        },
        {
            "id": "CHANA_ADMIXTURE",
            "commodity": "Chana (Desi) / Harbhara (हरभरा)",
            "image_path": "C:/Users/visha/.gemini/antigravity/brain/8940d80f-5c6a-4a54-8376-f92e236fc388/photo2_sample.jpg",
            "ground_truth": "Severe Admixture: ~80-100 yellow soybean seeds mixed in (~11-13% by count)",
            "expected_sortex_grade": "SORTEX Sub-Standard (Re-Pass Required / Heavy Dockage)"
        },
        {
            "id": "SOYBEAN_MULTI_DEFECT",
            "commodity": "Soyabean (Yellow)",
            "image_path": "commoditi software/soybean_seeds_benchmark.png",
            "ground_truth": "Standard benchmark with Intact, Broken, Green Immature, and Spotted/Damaged seeds",
            "expected_sortex_grade": "SORTEX Sub-Standard (Re-Pass Required / Heavy Dockage)"
        },
        {
            "id": "MUSTARD_SEEDS_MIXED",
            "commodity": "Mustard (Rayda)",
            "image_path": "commoditi software/mustard_seeds1.jpg",
            "ground_truth": "Commercial Mustard with ~18-20% Yellow Sarson/Toria seed admixture",
            "expected_sortex_grade": "SORTEX Grade B (Commercial Trading Standard) or Re-Pass"
        },
        {
            "id": "WHEAT_DEFECT_LOT",
            "commodity": "Wheat (Lokwan)",
            "image_path": "commoditi software/wheat_01.jpg",
            "ground_truth": "Wheat defect dataset: Black point (smudge) & Fusarium (chalky pink scab) seeds",
            "expected_sortex_grade": "SORTEX Sub-Standard (Re-Pass Required / Heavy Dockage)"
        }
    ]

    results = []

    print("=========================================================================================")
    print(" SORTEX OPTICAL SORTER DEFECT ACCURACY BENCHMARK ON REAL COMMODITY SPECIMENS")
    print("=========================================================================================\n")

    for tc in test_cases:
        img_p = tc["image_path"]
        if not os.path.exists(img_p):
            print(f"Skipping {tc['id']}: file {img_p} not found.")
            continue

        res = analyze_grain_sample_image(img_p, commodity_name=tc["commodity"])

        # Extract factors
        clean_yield = res.get("sortex_clean_yield_pct", 0.0)
        reject_pct = res.get("sortex_reject_pct", 0.0)
        grade = res.get("sortex_grade", "")
        admixture_pct = res.get("admixture_pct", 0.0)
        damaged_pct = res.get("damaged_pct", 0.0)
        broken_pct = res.get("broken_split_pct", 0.0)
        green_pct = res.get("green_seeds_pct", 0.0)
        karda_pct = res.get("karda_pct", 0.0)
        total_seeds = res.get("total_seeds_analyzed", 0)

        item = {
            "test_id": tc["id"],
            "commodity": tc["commodity"],
            "ground_truth": tc["ground_truth"],
            "total_seeds_analyzed": total_seeds,
            "sortex_factors_detected": {
                "clean_yield_pct": clean_yield,
                "total_reject_pct": reject_pct,
                "optical_admixture_pct": admixture_pct,
                "optical_damaged_pct": damaged_pct,
                "optical_green_immature_pct": green_pct,
                "profile_broken_split_pct": broken_pct,
                "foreign_matter_karda_pct": karda_pct
            },
            "assigned_sortex_grade": grade,
            "expected_sortex_grade": tc["expected_sortex_grade"],
            "grade_match": (tc["expected_sortex_grade"].split()[0] in grade)
        }
        results.append(item)

        print(f"[*] TEST: {tc['id']}")
        print(f"  Commodity: {tc['commodity'].encode('ascii', 'ignore').decode()}")
        print(f"  Ground Truth: {tc['ground_truth']}")
        print(f"  Kernels Analyzed: {total_seeds}")
        print(f"  Sortex Clean Yield: {clean_yield}% | Reject Eject Rate: {reject_pct}%")
        print(f"  Defect Breakdown: Admixture={admixture_pct}%, Damage={damaged_pct}%, Broken={broken_pct}%, Green={green_pct}%, FM={karda_pct}%")
        print(f"  Sortex Decision: {grade}")
        print("-" * 89)

    out_json = "commoditi software/sortex_accuracy_report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nAll Sortex accuracy benchmark results saved to: {out_json}")
    return results

if __name__ == "__main__":
    run_sortex_benchmark()
