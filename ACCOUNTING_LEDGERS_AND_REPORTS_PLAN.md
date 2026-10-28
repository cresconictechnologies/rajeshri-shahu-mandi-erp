# Accounting Ledgers & Financial Reports Plan
**Double-Entry Matrix, Chart of Accounts, and Mandatory Mandi Statements**

---

## 1. Chart of Accounts (Mandi & Commodity Specific)

```
Chart of Accounts
├── 1000 - ASSETS
│   ├── 1100 - Current Assets
│   │   ├── 1110 - Cash-in-Hand (Branch Cashier Drawer / Galla)
│   │   ├── 1120 - Bank Accounts (Current A/c, Settlement A/c)
│   │   ├── 1130 - Commodity Inventory (Soyabean, Wheat, Chana, Mustard)
│   │   ├── 1140 - Packing Material Inventory (Empty Bardana / Gunny Bags)
│   │   └── 1150 - Loans & Advances to Farmers (Peshgi Bahi)
├── 2000 - LIABILITIES
│   ├── 2100 - Current Liabilities
│   │   ├── 2110 - Sundry Creditors - Farmers (Kisan Payable)
│   │   ├── 2120 - Sundry Creditors - Stockers (Vyapari B2B Payable)
│   │   ├── 2130 - Mandi Board Cess / Samiti Shulk Payable
│   │   ├── 2140 - Krishi Kalyan Fee / RDF Payable
│   │   ├── 2150 - Labor Payables (Hamali Payable, Tulai Payable)
│   │   ├── 2160 - GST Payables (CGST, SGST, IGST, RCM Liability)
│   │   └── 2170 - TDS Payable u/s 194Q
├── 3000 - DIRECT EXPENSES & PURCHASES
│   ├── 3100 - Commodity Purchases (Farmer Inwards)
│   ├── 3200 - Commodity Purchases (Stocker B2B Inwards)
│   ├── 3300 - Hamali / Unloading Expenses
│   ├── 3400 - Weighbridge / Tulai Expenses
│   └── 3500 - Mandi Cess Expense (if buyer-borne)
├── 4000 - DIRECT & INDIRECT REVENUES
│   ├── 4100 - Sales of Agricultural Commodities (Wholesale/Millers)
│   ├── 4200 - Interest Income on Farmer Advances
│   └── 4300 - Commission / Arhat Income (if acting as Commission Agent)
```

---

## 2. Double-Entry Accounting Journal Entries

### Transaction 1: Farmer Inward Purchase Bill (Patti Generated)
*When a farmer delivers produce and the settlement slip is approved at the desk:*
* **Debit:** `3100 - Commodity Purchases` (Gross Value of Produce)
* **Credit:** `2150 - Hamali Payable` (Labor charges deducted)
* **Credit:** `2150 - Tulai Payable` (Weighment charges deducted)
* **Credit:** `2130 - Mandi Cess Payable` (If deducted from seller)
* **Credit:** `1150 - Loans & Advances to Farmers` (Principal loan deducted)
* **Credit:** `4200 - Interest Income on Advances` (Accrued interest deducted)
* **Credit:** `2110 - Sundry Creditors - Farmers` (Net Payable to Farmer)

### Transaction 2: Cashier Disburses Cash Payout
*When the cashier hands physical currency notes to the farmer:*
* **Debit:** `2110 - Sundry Creditors - Farmers` (Net Payable Amount)
* **Credit:** `1110 - Cash-in-Hand (Branch Cashier Drawer)` (Cash disbursed)

### Transaction 3: Cashier Disburses Bank Transfer (RTGS / NEFT / IMPS)
*When paid digitally (or forced due to Section 269ST ₹2L limit):*
* **Debit:** `2110 - Sundry Creditors - Farmers`
* **Credit:** `1120 - Bank Settlement Account`

### Transaction 4: Stocker B2B Purchase (Taxable with TDS)
*When purchasing from a registered merchant with GST and Section 194Q:*
* **Debit:** `3200 - Commodity Purchases (Stocker)` (Taxable Base Value)
* **Debit:** `1160 - Input GST Credit (CGST + SGST or IGST)`
* **Credit:** `2170 - TDS Payable u/s 194Q` (0.1% TDS)
* **Credit:** `2120 - Sundry Creditors - Stockers` (Net Invoice Amount)

### Transaction 5: Stocker Bank Payout
*Mandatory banking channel payout under Section 40A(3):*
* **Debit:** `2120 - Sundry Creditors - Stockers`
* **Credit:** `1120 - Bank Current Account`

---

## 3. Mandatory Reporting Suite

### Report 1: Farmer Settlement Register (*J-Form / Patti Book*)
- **Columns:** Date, Token No, Farmer Name, Village, Commodity, Gross Wt (kg), Vehicle Tare, Bag Tare, Moisture Cut, Karda Cut, Net Quintals, Rate/Qtl, Gross Amount, Hamali, Tulai, Advance Deducted, Net Payable, Cashier Payout Status, Payment Mode.
- **Use Case:** Daily audit of all inward agricultural procurement.

### Report 2: Stocker / Merchant B2B Purchase Register
- **Columns:** Date, Bill No, Stocker Name, GSTIN, Commodity, HSN, Net Quintals, Rate, Taxable Value, CGST, SGST, IGST, TDS 194Q, Total Bill Value, Payment Ref / UTR.
- **Use Case:** Monthly filing of GSTR-2B reconciliation and TDS Form 26Q quarterly returns.

### Report 3: Daily Mandi Day Book (*Rojmel / Rokad Bahi*)
- **Sections:**
  1. Opening Cash Float (Morning galla balance).
  2. Cash Inward (Bank cash withdrawals / counter receipts).
  3. Cash Outward (Farmer purchase payouts, labor payments, petty mandi expenses).
  4. Closing Calculated Balance vs. Physical Counted Denomination Table.
  5. Shortage / Excess Variance Note.

### Report 4: Lot-Wise Commodity Stock Ledger
- **Tracking:**
  - Commodity Name & Variety (e.g., Soyabean Yellow, Lokwan Wheat).
  - Inward Bags & Net Quintals.
  - Processing / Moisture Shrinkage (*Karda Loss*).
  - Outward Sales / Dispatches to Millers.
  - Closing Stock on Hand (Godown-wise & Branch-wise).
  - Weighted Average Procurement Cost per Quintal.

### Report 5: Farmer Advance & Loan Register (*Peshgi Khata*)
- **Tracking:**
  - Date Advance Given, Cash/Bank Ref, Principal Disbursed.
  - Seasonal Recoveries against Inward Bills.
  - Interest Accrued and Collected.
  - Outstanding Farmer Debt Aging (> 90 days, > 180 days).

### Report 6: APMC Mandi Cess / Levy Statement
- **Tracking:**
  - Total Monthly Commodity Value Purchased from Farmers.
  - Mandi Fee @ 1.5% (or applicable state rate).
  - Krishi Kalyan Cess @ 0.5%.
  - Total Cess Deposited with APMC Challan Number and Date.

### Report 7: Income Tax Section 269ST & Section 40A(3) Compliance Dossier
- **Automated Audit File for Tax Scrutiny:**
  - **Section 269ST Filter:** Lists any single day where cumulative cash payouts to any person exceeded or approached ₹1,50,000 (with proof that no transaction crossed ₹1,99,999).
  - **Rule 6DD Cultivator Dossier:** Compiles the complete audit trail for all cash purchases:
    - Farmer Name & Address.
    - Land Revenue *Khasra* Record Number.
    - Weighment Slip Number & Dharamkanta Name.
    - Signed / Thumb-impressed Settlement Voucher.
    - Validates 100% compliance with Income Tax Rule 6DD(e).
