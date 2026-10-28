# Technical Inspection: KhataOS & Indian GST Billing Engines
**Architectural Patterns, Cash Reconciliation, and Indirect Tax Compliance for Commodity Trading**
*Inspected Systems: KhataOS (khataos.org / khataos.com), Modern Mandi GST Engines*

---

## 1. Architectural Highlights from KhataOS Inspection

An inspection of **KhataOS** (`khataos.org` / `khataos.com`) reveals several architectural patterns critical for high-speed, local-first commodity trade management:

### A. Local-First Engine & Tamper-Evident Ledger
- **Zero-Latency Database:** KhataOS uses an embedded SQLite engine on local devices, avoiding web browser loading spinners and server timeouts during peak mandi arrival hours.
- **Hash-Chained Audit Trail:** Every voucher creation, modification, or cancellation generates a cryptographic SHA-256 hash linked to the prior entry:
  $$\text{Hash}_n = \text{SHA256}(\text{VoucherData}_n + \text{Hash}_{n-1})$$
  This prevents munims or cashiers from modifying invoice rates or cash amounts after the farmer leaves the yard.
- **Keyboard-First Workflow:** Standard numeric keypad navigation ensures a weighbridge clerk or munim can punch an inward slip in under 20 seconds.

### B. Daily Cash Drawer & Currency Note Tally (Rojmel / Galla Tally)
Traditional mercantile traders rely on **Rojmel** (Daily Cash Book). KhataOS implements a strict 4-step closing checklist with automated denomination counting:

$$\text{Calculated Closing Cash} = \text{Opening Float} + \text{Inward Bank Withdrawals} - \text{Cash Payouts} - \text{Petty Expenses}$$

- **Physical Note Denomination Breakdown:**
  The cashier physically counts and inputs note counts:
  $$\text{Physical Cash} = (N_{500} \times 500) + (N_{200} \times 200) + (N_{100} \times 100) + (N_{50} \times 50) + (N_{20} \times 20) + (N_{10} \times 10) + \text{Coins}$$
- **Variance Detection:**
  $$\text{Variance} = \text{Physical Counted Cash} - \text{Calculated Closing Cash}$$
  - A negative variance indicates cashier cash shortage (leakage/unrecorded payout).
  - A positive variance indicates unrecorded receipts or excess cash collected.
  - The day cannot be closed until the cashier and manager sign off on the variance.

### C. Thermal ESC/POS Bill Generation
- **58mm / 80mm ESC/POS Thermal Printing:** Fast, inkless receipts printed immediately at the weighbridge desk and cashier counter.
- **Key Elements on Thermal Cash Payout Slip:**
  - Token Number & QR Code.
  - Farmer Name, Village, and Contact.
  - Commodity, Net Quintals, and Rate/Qtl.
  - Gross Amount, Itemized Deductions (Hamali, Tulai, Nami, Advance).
  - Net Cash Paid and Cashier ID.
  - Farmer Signature / Thumb Impression Line (essential for Section 40A(3) / Rule 6DD audit defense).

---

## 2. Indian GST & Mandi Regulatory Architecture

### A. GST Classification on Agricultural Commodities

| Commodity Group | Common HSN | Unbranded / Loose Form | Pre-Packaged & Labeled |
| :--- | :--- | :--- | :--- |
| **Foodgrains (Wheat, Paddy, Maize)** | 1001, 1005, 1006 | **0% (Exempt)** | **5% GST** |
| **Oilseeds (Soyabean, Mustard, Groundnut)** | 1201, 1202, 1207 | **0% (Exempt)** | **5% GST** |
| **Pulses (Chana, Moong, Urad, Toor)** | 0713 | **0% (Exempt)** | **5% GST** |
| **Raw Cotton (Kapas)** | 5201 | **5% under RCM (Sec 9(3))** | **5% GST** |
| **Cashew nuts in shell** | 0801 | **5% under RCM (Sec 9(3))** | **5% GST** |

#### Reverse Charge Mechanism (RCM) under Section 9(3):
For specific agricultural commodities like **Raw Cotton** and **Cashew nuts in shell**, when purchased from an unregistered agriculturist (Farmer), the **registered buyer must pay 5% GST under RCM** and issue a self-invoice. For general grains and oilseeds sold loose, supplies by agriculturists are completely exempt from GST.

---

### B. Income Tax Section 194Q vs. Section 206C(1H) (High-Volume Purchases)

When purchasing from **Stockers / Merchants**:
- **Applicability:** Applies if the buyer's gross turnover exceeded **₹10 Crores** in the preceding financial year.
- **Threshold:** Applies when cumulative purchases from a single stocker exceed **₹50 Lakhs** in the current financial year.
- **TDS Deduction:** The buyer must deduct **0.1% TDS** under **Section 194Q** on the amount exceeding ₹50 Lakhs.
- **PAN Mismatch:** If the stocker does not furnish a valid PAN, the TDS rate jumps to **5%**.
- **Exemption:** Section 194Q does **NOT** apply to purchases from primary agricultural cultivators (Farmers).

---

### C. APMC Mandi Tax (Market Fee) & Cess

- **Nature:** Statutory fee levied by the state Agricultural Produce Market Committee (e.g., MP APMC Act, UP Mandi Adhiniyam, Rajasthan APMC Act).
- **Rates:** Typically ranges from **1.0% to 2.5%** of gross purchase value, plus **Krishi Kalyan Cess (0.5%)** or Rural Development Fund (RDF).
- **Single Point Levy Rule:** Mandi tax is paid only once in the state. 
  - When buying from a **Farmer**, the mandi fee is assessed.
  - When buying from a **Stocker**, the stocker must produce **Form M / Mandi Gate Pass / Anugya Patra** proving mandi tax was already discharged at the primary market.
