# Mathematical Calculations & Formulas Specification
**Complete Field-by-Field Engineering Guide for Mandi Purchase & Settlement Billing**

---

## 1. Weighbridge (*Dharamkanta*) & Tare Math

In rural yards and mandis, the weighing machine may belong to a third-party public weighbridge. The system must support manual entry of the external slip alongside connected scales.

### Input Parameters:
- $W_{\text{gross}}$: Gross vehicle weight on weighbridge (kg)
- $W_{\text{tare}}$: Empty vehicle tare weight on weighbridge (kg)
- $B_{\text{count}}$: Number of bags (*Bori*)
- $B_{\text{type}}$: Bag type (`HDPE_50KG`, `JUTE_100KG`, `LOOSE`)
- $T_{\text{bag}}$: Tare weight per empty bag (kg):
  - Standard HDPE / Plastic sack: $0.50\text{ kg}$
  - Standard Jute / Hessian gunny sack: $1.00\text{ kg}$
  - Loose load (Trolley / Tipper): $0.00\text{ kg}$

### Formulas:
$$\text{Vehicle Net Weight (kg)} = W_{\text{net\_vehicle}} = \max(0, W_{\text{gross}} - W_{\text{tare}})$$

$$\text{Total Bag Tare Weight (kg)} = W_{\text{bag\_tare}} = B_{\text{count}} \times T_{\text{bag}}$$

$$\text{Uncleaned Produce Weight (kg)} = W_{\text{uncleaned}} = \max(0, W_{\text{net\_vehicle}} - W_{\text{bag\_tare}})$$

### Manual Input Validation Guardrails:
1. **Tare Ratio Warning:** If $W_{\text{tare}} > 0.60 \times W_{\text{gross}}$ or $W_{\text{tare}} < 0.15 \times W_{\text{gross}}$, trigger validation alert.
2. **Average Bag Weight Sanity Check:**
   $$\text{Avg Bag Weight} = \frac{W_{\text{uncleaned}}}{B_{\text{count}}}$$
   - Flag if $\text{Avg Bag Weight} < 30\text{ kg}$ or $\text{Avg Bag Weight} > 115\text{ kg}$.

---

## 2. Quality Cut Deductions (*Kaat / Katoti*)

### A. Moisture Cut (*Nami*):
Moisture meters provide a moisture percentage $M_{\text{actual}}$. Mandi standard baseline is typically $M_{\text{std}} = 10.0\%$ (or $12.0\%$ for paddy/wheat).
Deduction applies only to the excess moisture:

$$\text{Excess Moisture \%} = M_{\text{excess}} = \max(0, M_{\text{actual}} - M_{\text{std}})$$

$$\text{Moisture Cut (kg)} = W_{\text{moisture\_cut}} = W_{\text{uncleaned}} \times \left(\frac{M_{\text{excess}}}{100}\right)$$

### B. Dust & Refraction Cut (*Mitti / Karda / Chhanai*):
Evaluated through sieving percentage $K_{\text{pct}}$:

$$\text{Karda Cut (kg)} = W_{\text{karda\_cut}} = W_{\text{uncleaned}} \times \left(\frac{K_{\text{pct}}}{100}\right)$$

---

## 3. Net Billable Weight & Gross Value

$$\text{Net Billable Weight (kg)} = W_{\text{net}} = \max(0, W_{\text{uncleaned}} - W_{\text{moisture\_cut}} - W_{\text{karda\_cut}})$$

$$\text{Net Quintals (Qtl)} = Q_{\text{net}} = \frac{W_{\text{net}}}{100.0} \quad (\text{stored to 4 decimal places})$$

$$\text{Gross Produce Value (₹)} = V_{\text{gross}} = \text{Round}\left(Q_{\text{net}} \times R_{\text{qtl}}, 2\right)$$
*(where $R_{\text{qtl}}$ is the agreed purchase rate per quintal)*

---

## 4. Statutory & Mandi Deductions

| Charge Name | Formula | Default Benchmark |
| :--- | :--- | :--- |
| **Hamali (Unloading Labor)** | $C_{\text{hamali}} = B_{\text{count}} \times R_{\text{hamali}}$ | ₹5.00 per bag |
| **Tulai (Weighment Fee)** | $C_{\text{tulai}} = B_{\text{count}} \times R_{\text{tulai}}$ | ₹2.00 per bag |
| **Silai (Bag Stitching)** | $C_{\text{silai}} = B_{\text{count}} \times R_{\text{silai}}$ | ₹1.00 per bag |
| **Bardana (Packing Sack)** | $C_{\text{bardana}} = B_{\text{count}} \times R_{\text{bardana}}$ | ₹0.00 (or ₹50/bag if trader provides) |
| **Mandi Tax / Cess** | $C_{\text{cess}} = \text{Round}\left(V_{\text{gross}} \times \frac{\text{Cess \%}}{100}, 2\right)$ | 0% if buyer-borne, 1.5% if seller-borne |

$$\text{Total Mandi Deductions} = D_{\text{mandi}} = C_{\text{hamali}} + C_{\text{tulai}} + C_{\text{silai}} + C_{\text{bardana}} + C_{\text{cess}}$$

---

## 5. Advance (*Peshgi*) Loan Recovery & Interest

When a farmer has an existing advance loan balance:
- $A_{\text{deduct}}$: Principal advance amount agreed to be recovered from this bill.
- $I_{\text{annual}}$: Annual interest rate (e.g., 12.0% p.a.).
- $D_{\text{days}}$: Number of elapsed days since the advance was disbursed.

$$\text{Accrued Interest (₹)} = I_{\text{adj}} = \text{Round}\left(\frac{A_{\text{deduct}} \times \left(\frac{I_{\text{annual}}}{100}\right) \times D_{\text{days}}}{365.0}, 2\right)$$

$$\text{Total Loan Recovery} = D_{\text{loan}} = A_{\text{deduct}} + I_{\text{adj}}$$

---

## 6. Taxes & Final Net Payable

### For Farmers (Exempt Raw Produce):
$$\text{Net Payable (₹)} = \text{Round}(V_{\text{gross}} - D_{\text{mandi}} - D_{\text{loan}}, 2)$$

### For Stockers (Taxable / TDS Applicable):
- GST Amount: $G = \text{Round}\left(V_{\text{gross}} \times \frac{\text{GST \%}}{100}, 2\right)$
- TDS u/s 194Q: $T_{194Q} = \text{Round}\left(V_{\text{gross}} \times \frac{0.1}{100}, 2\right)$ *(if cumulative FY purchase > ₹50 Lakhs)*

$$\text{Net Payable to Stocker (₹)} = \text{Round}(V_{\text{gross}} - D_{\text{mandi}} + G - T_{194Q}, 2)$$

---

## 7. Cashier Denomination Tally Math

When paying cash at the counter:
$$\text{Total Paid} = (500 \times C_{500}) + (200 \times C_{200}) + (100 \times C_{100}) + (50 \times C_{50}) + (20 \times C_{20}) + (10 \times C_{10}) + \text{Coins}$$
The software asserts:
$$\text{Total Paid} == \text{Net Payable Amount}$$
*(Or flags an exact petty round-off difference $\le ₹0.50$)*
