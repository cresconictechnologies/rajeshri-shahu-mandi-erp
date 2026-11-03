# COMMODITI GRAIN INTELLIGENCE ENGINE (CGIE)
## Scientific Master Implementation Directive & Architecture Plan
**Project:** Commoditi Mandi ERP — Scientific Grain Quality Intelligence Platform  
**System Version:** 2.0.0-PROD  
**Deployment Target:** Hybrid Desktop Mandi ERP & Smartphone PWA Inspection Station  

---

## 1. Executive Summary & Core Architectural Law

The **Commoditi Grain Intelligence Engine (CGIE)** is a measurement-led, AI-assisted scientific grading platform engineered for agricultural trading firms, seed suppliers, and grain processors.

### The Foundational Rule: Single Core, Three Decision Engines
> **"Never build three separate AI systems. Build one common grain observation and measurement engine, then three independent decision engines."**

```
                     ┌──────────────────────────────────────────────┐
                     │         STANDARDIZED SMARTPHONE CAPTURE      │
                     │   Diffused 5000K Lightbox + ArUco Calibration │
                     └──────────────────────┬───────────────────────┘
                                            │
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │    COMMON GRAIN OBSERVATION & MEASUREMENT    │
                     │  Tray Warp · Watershed/YOLO · CIELAB · Shape │
                     │   Uncertainty Detection · Quality Gate       │
                     └──────────────────────┬───────────────────────┘
                                            │ Physical Measurements (Observations Only)
            ┌───────────────────────────────┼───────────────────────────────┐
            ▼                               ▼                               ▼
┌──────────────────────┐        ┌──────────────────────┐        ┌──────────────────────┐
│  MANDI TRADING       │        │  SEED QUALITY        │        │  MILL & PROCESSING   │
│  DECISION ENGINE     │        │  DECISION ENGINE     │        │  DECISION ENGINE     │
├──────────────────────┤        ├──────────────────────┤        ├──────────────────────┤
│ • APMC & AGMARK Grade│        │ • Physical Purity %  │        │ • Usable Material %  │
│ • Statutory Deductions│       │ • Visual Seed Health │        │ • Sortex Clean Yield │
│ • Net Buying Rate/Qtl│        │ • Weed / Crop Contam.│        │ • Oil / Dal Recovery │
│ • Commercial Invoice │        │ • (Screening Only)   │        │ • Mill Loss Profile  │
└──────────────────────┘        └──────────────────────┘        └──────────────────────┘
```

The analytical observation core **never** knows what business transaction is occurring. It produces raw physical observations first; each business engine interprets those observations independently.

---

## 2. Epistemological Policy: Observations vs. Inferences vs. Lab Truth

In the absence of an initial accredited laboratory dataset, the engine enforces strict truth boundaries:

| Class | Category | System Capability & Provenance |
| :--- | :--- | :--- |
| **Observed** | What the camera & sensors directly record | Tray geometry, 2D projected grain area, CIELAB/HSV color metrics, kernel count, aspect ratio, digital moisture meter reading. |
| **Inferred** | What AI / models estimate from observations | Defect candidate tags (mold-like appearance, chlorophyll discoloration, chipped cotyledons), Sortex optical yield estimate. |
| **Requires Lab** | What CANNOT be claimed from phone photographs | Seed germination %, genetic cultivar purity (e.g. JS-335 vs JS-9560 DNA), exact oil/protein %, mycotoxin (Aflatoxin) ppm. |

### Provenance Tracking
Every data point persisted in the database must record its provenance:
* `AI_SUGGESTED`: Proposed by Gemini Vision or Groq reasoning.
* `HUMAN_REVIEWED`: Verified by Mandi yard supervisor.
* `PHYSICAL_VERIFIED`: Physically weighed using calibrated 0.01g / trade scale.
* `LAB_VERIFIED`: Calibrated Karl-Fischer oven moisture or accredited laboratory assay.

---

## 3. Layered System Architecture

### Layer 1: Standardized Sample Acquisition
* **Physical Station:**
  * Fixed overhead smartphone mount (12MP+ camera).
  * 40cm diffused 5000K LED lightbox to eliminate specular glare and harsh yard shadows.
  * Neutral matte-grey inspection tray (ArUco 4x4 fiducial corners for exact millimeter scaling).
  * Color calibration target (neutral grey patch).
* **Two Required Photographs per Sample:**
  * **Image A (Overview):** Full tray view for foreign matter, total kernel population, and distribution.
  * **Image B (Macro):** Close-up detail for surface texture, insect boreholes, and micro-cracks.
* **Mandatory Capture Validation Gate:**
  * Evaluates blur (Laplacian variance), exposure clipping, glare saturation, and grain overlap density.
  * If validation fails: Returns `REQUIRES_REVIEW` and requests a new photo rather than guessing.

### Layer 2: Scientific Observation Engine
1. **Module A — Image Calibration:** ArUco homography, perspective rectification, mm-per-pixel scaling, and CIELAB white balance normalization.
2. **Module B — Grain Instance Segmentation:** Discrete kernel isolation via Watershed distance transform & YOLO segmentation baseline. Calculates count, 2D boundary, area ($mm^2$), length, width, and aspect ratio.
3. **Module C — Color & Appearance Profiling:** Measures CIELAB ($L^*, a^*, b^*$), HSV, and local surface contrast (avoiding rigid single-threshold green masks).
4. **Module D — Defect Observation:** Classifies visual anomalies into mutually exclusive primary refractions (Karda, Damaged, Immature, Broken, Shrivelled) and secondary attributes.
5. **Module E — Variety & Admixture Intelligence:** Measures morphological distribution against curated reference seeds; flags candidate mixtures.
6. **Module F — Statistical Quantification:**
   $$P_{\text{count},i} = \frac{N_i}{N_{\text{total}}} \times 100 \quad \text{vs} \quad P_{\text{area},i} = \frac{A_i}{A_{\text{total}}} \times 100 \quad \text{vs} \quad P_{\text{weight},i} = \frac{W_i}{W_{\text{total}}} \times 100$$
   *Never substitutes area or count for physical weight without calibration.*
7. **Module G — Uncertainty & Quality Gates:** Outputs model version, confidence interval, and verification status.

### Layer 3: Dual-AI Intelligence Engine (Gemini + Groq)
* **Google Gemini 2.5 Flash:** High-resolution Multimodal Vision OCR and secondary visual defect verification.
* **Groq LPU (Ultra-Low Latency Inference):** Rapid JSON schema enforcement, APMC rule engine execution, statistical reconciliation, and cross-engine decision calculations in under 200 milliseconds.

---

## 4. The Three Independent Decision Engines

### Engine 1: Mandi Trading Engine
* **Purpose:** Determine commercial acceptability, statutory refractions, and fair purchasing price for farmers.
* **Formula:**
  $$P_{\text{buy}} = P_{\text{reference}} - D_{\text{moisture}} - D_{\text{refractions}} + B_{\text{quality}}$$
* **Output:** Mandi Quality Grade (FAQ Grade 1, FAQ Grade 2, Non-FAQ), breakdown of ₹/Qtl deductions, and commercial purchase ticket.

### Engine 2: Seed Quality Engine (Screening Only)
* **Purpose:** Determine suitability for sowing/planting and lot uniformity.
* **Parameters Evaluated:** Visual physical purity, seed size uniformity index, defective/damaged seed discard %, candidate weed/other crop presence.
* **Legal Disclaimer:** Strictly labelled as **"Visual Seed Quality Screening Report"**. Disclaims that official seed certification requires ISTA / Indian Seed Act germination and grow-out testing.

### Engine 3: Mill & Processing Recovery Engine
* **Purpose:** Predict industrial recovery, cleaning losses, and milling output.
* **Commodity Projections:**
  * **Soybean:** Cleaning dockage %, usable seed input %, estimated solvent oil extraction range (17.5% - 19.5%), de-oiled cake (DOC) yield (78% - 80%).
  * **Wheat:** Cleaning loss %, hectolitre weight estimate, flour extraction potential (Maida/Suji/Atta).
  * **Chana:** Dal recovery %, broken chuni/khanda %, husk loss %.
* **Tracking:** Eventually records actual mill run results against predictions to refine the recovery model.

---

## 5. Strategic First Milestone: Soybean-First Execution

Soybean (Yellow) is designated as the primary reference commodity for initial end-to-end validation:
1. **Existing Assets:** Pre-existing real trading benchmark photos (`soybean_seeds_benchmark.png`) and APMC parameters (JS-335, JS-9560).
2. **Commercial Value:** High stakes in Indian Mandis (Maharashtra/MP) around moisture cuts, green seeds (chlorophyll dark-oil penalty), and cleaning loss.
3. **Double Verification:** Directly feeds both Mandi Trading (farmer purchase) and Mill Processing (crushing plants).

---

## 6. Implementation Roadmap

* [x] **Phase 0:** Forensic audit of existing `quality_engine.py` and identification of heuristic vs. real logic.
* [x] **Phase 1:** Dual API Key Configuration (Google Gemini + Groq LPU) in production environment.
* [ ] **Phase 2:** Capture validation gate & CIELAB color normalization integration.
* [ ] **Phase 3:** Three independent decision engines implementation (`MandiTradingEngine`, `SeedQualityEngine`, `MillProcessingEngine`).
* [ ] **Phase 4:** Normalized Database Entities for physical sample weights and observation provenance.
* [ ] **Phase 5:** Soybean-first validation and physical weight ground-truth dataset acquisition.
