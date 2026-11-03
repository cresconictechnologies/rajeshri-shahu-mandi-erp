# Rajarshi Shahu Trading — Mandi ERP v1.0
# Audit Report 05: Business Workflow & Transaction Lifecycle Audit

**Document Reference:** `AUDIT/05_BUSINESS_WORKFLOW_AUDIT.md`  
**System Evaluated:** Rajarshi Shahu Mandi ERP (Commercial Mandi ERP v1.0)  
**Modules Audited:**
- `commoditi software/server.py` (FastAPI Central Application & Gateway)
- `commoditi software/database.py` (SQLite Database Layer & Schemas)
- `commoditi software/calculations.py` (Statutory & Financial Calculation Engine)
- `commoditi software/templates/` (`branch_dashboard.html`, `accounts_dashboard.html`, `inspector_portal.html`, `parchi_slip.html`, `outward_challan.html`)
- `mandi-erp-tracker/` (Mobile QC Inspector PWA & Vercel API Handlers)

**Audit Execution Date:** November 3, 2026  
**Auditor:** Lead Security Architect & Business Workflow Auditor  
**Scope:** Complete End-to-End Mandi Transaction Lifecycle (Quality Inspection → Cashier Desk → Weighbridge → Cash Drawer → Inventory / Yard Stock → General Ledger → Head Office Super Admin).

---

## 1. Executive Summary

This audit assesses the transactional integrity, regulatory compliance, internal controls, and state transitions of the Rajarshi Shahu Mandi ERP. The system facilitates grain procurement from agricultural cultivators (farmers) across three APMC physical branch yards (Chikhali, Varvand, Dhad), cash/RTGS disbursements, yard stock management, outward trading dispatches to commercial buyers, and central accounting oversight.

While the software features advanced visual assaying (computer vision grain segmentation, 7-segment moisture meter OCR, Sortex yield modeling) and offline-capable synchronization architecture, the operational audit identified **critical workflow disconnects, regulatory non-compliance vulnerabilities, and financial control bypasses**:

1. **QC Ticket Multi-Invoice Double-Spend**: Quality Inspection tickets lack database uniqueness and state enforcement, enabling the same QC ticket to be attached to multiple purchase invoices.
2. **Immediate Cash Settlement Rate Override Bypass**: Inward purchases created with rates outside the daily approved corridor bypass the Central Accounts rate approval gate when settled in immediate cash.
3. **Income Tax Section 269ST & Section 40A(3) Compliance Failure**: The unified invoice creation endpoint does not check cumulative daily cash payouts to farmers or traders, allowing single-day cash payments exceeding ₹2,00,000 (triggering 100% penalties under Section 271DA).
4. **Asymmetric & Broken Double-Entry Ledgers**: RTGS disbursements post single-sided bank credits without clearing farmer liabilities; deferred cashier payouts omit Hamali and advance credits; accounting dashboards bypass ledgers entirely.
5. **Simulated Cash Drawer Sessions**: Cash drawer balances do not represent physical drawer sessions or daily float carry-overs; instead, an unverified ₹5,00,000 float is auto-injected daily without reconciliation.
6. **Unconstrained Outward Dispatches**: Outward sales dispatches execute without validating physical stock availability, masking negative yard inventory behind zero-clamping math.

---

## 2. Mandi Transaction Lifecycle Architecture Trace

```
+----------------------------------------------------------------------------------------------------+
|                                RAJARSHI SHAHU MANDI ERP - TRANSACTION LIFECYCLE                    |
+----------------------------------------------------------------------------------------------------+
                                                  |
 [STAGE 1: GATE / INWARD ASSAYING]                v
 +--------------------------------------------------------------------------------------------------+
 | Physical Produce Enters APMC Yard -> Tractor / Truck / Bull-Cart                                 |
 | Quality Inspector captures Moisture Meter Photo & Grain Sample Tray                              |
 | Computer Vision Assayer / Normalized Chromaticity Engine runs (Moisture, Karda, Damaged, Sortex)|
 | System generates QC Inspection Ticket (e.g. QC-CHK-261103-A1F9) with suggested buying rate cut    |
 +--------------------------------------------------------------------------------------------------+
                                                  |
 [STAGE 2: WEIGHMENT & DESK ATTACHMENT]           v
 +--------------------------------------------------------------------------------------------------+
 | Cultivator presents QC Slip to Cashier / Munim Terminal                                          |
 | Weighment Mode Selected: 'MANUAL_YARD' (Platform Scale) vs 'WEIGHBRIDGE' (Gross/Tare Weighbridge)|
 | Gross Weight, Bag Count, Bag Tare, Moisture Cut, Karda Cut calculated via calculations.py        |
 | Net Billable Weight (Kg & Quintals) derived                                                      |
 +--------------------------------------------------------------------------------------------------+
                                                  |
 [STAGE 3: RATE DETERMINATION & DEDUCTIONS]       v
 +--------------------------------------------------------------------------------------------------+
 | Agreed Buying Rate entered -> Validated against Daily Corridor (daily_commodity_rates)           |
 | APMC Statutory Deductions applied: Farmer Mandi Cess = 0.0 (Zero Cess Rule)                      |
 | Hamali applied: Exactly ₹25.00 per 100 kg (per Quintal) deducted from Farmer                     |
 | Advance Loan & Interest deductions applied                                                       |
 | Net Payable Amount calculated & Rounded up to nearest Rupee (Paisa Round-off)                   |
 +--------------------------------------------------------------------------------------------------+
                                                  |
 [STAGE 4: SETTLEMENT & PAYOUT MODE]              v
 +--------------------------------------------------------------------------------------------------+
 | Settlement Choice: CASH vs RTGS_PENDING vs PENDING                                               |
 | Statutory Verification: Section 269ST (₹1,99,999 cash ceiling) & Section 40A(3)                  |
 | Physical Denomination Counting (500, 200, 100, 50, 20, 10, Coins)                                |
 | Printed Parchi Slip issued to Farmer with QR verification code                                   |
 +--------------------------------------------------------------------------------------------------+
                                                  |
 [STAGE 5: CASH DRAWER DISBURSEMENT]              v
 +--------------------------------------------------------------------------------------------------+
 | Cashier Drawer deducted by rounded payout amount                                                 |
 | Physical float balance reconciled                                                                |
 +--------------------------------------------------------------------------------------------------+
                                                  |
 [STAGE 6: INVENTORY & DISPATCH]                  v
 +--------------------------------------------------------------------------------------------------+
 | Yard Stock increased by Net Quintals                                                             |
 | Outward Order Dispatch to Buyer (Commercial Trader) -> Outward Challan generated                 |
 | Buyer billed for Produce + Hamali Recovery                                                       |
 +--------------------------------------------------------------------------------------------------+
                                                  |
 [STAGE 7: DOUBLE-ENTRY ACCOUNTING]               v
 +--------------------------------------------------------------------------------------------------+
 | Ledger Entries: Debit Purchase, Credit Cash/Bank, Credit Hamali Recovery, Credit Round-Off       |
 | RTGS transferred via Mandi Central Bank Account with UTR tracking                                |
 +--------------------------------------------------------------------------------------------------+
                                                  |
 [STAGE 8: HEAD OFFICE OVERSIGHT]                 v
 +--------------------------------------------------------------------------------------------------+
 | Super Admin & Central Accounts broadcast daily commodity rates to all yards                     |
 | Central Accounts reviews and approves/rejects out-of-corridor rate overrides                     |
 +--------------------------------------------------------------------------------------------------+
```

---

## 3. Detailed Stage-by-Stage Workflow Audit

### Stage 1: Farmer & Commodity Identification, QC Ticket Generation & Assaying Deductions
- **Implementation:** `quality_engine.py:analyze_grain_sample_image()`, `server.py:api_inspector_submit_qc()`, `mandi-erp-tracker/app.html:handleTrayFile()`, `mandi-erp-tracker/api/inspections-submit.js`.
- **Workflow Mechanics:**
  1. Inspector inputs cultivator name, mobile number, vehicle number, and commodity.
  2. Moisture meter display is captured; OCR extracts numeric moisture percentage.
  3. Grain tray photo is captured; Computer Vision performs watershed segmentation, color thresholding (damaged, green, broken, karda, foreign admixture), and Sortex clean yield prediction.
  4. Suggested buying rate is calculated based on deductions against APMC standard benchmarks (`COMMODITY_STANDARDS`).
  5. Ticket number is generated (`QC-{YARD}-{YYMMDD}-{HEX}`) and saved to `quality_inspections` table with status `PENDING`.
- **Identified Disconnects:**
  - *Unregistered Farmer Disconnect:* QC tickets do not link to the master `parties` table (`parties.id`). They store loose strings (`farmer_name`, `farmer_phone`).
  - *Payload Inflation:* The mobile PWA tracker transmits uncompressed base64 images directly inside `meter_photo_path` and `grain_photo_path` JSON fields, causing severe latency and memory exhaustion on SQLite and Supabase.
  - *Bypass of Assaying:* The endpoint `/api/inspector/submit-qc` accepts manually overridden refraction percentages (`moisture_pct`, `karda_pct`, `suggested_buying_rate_per_qtl`) without verifying whether an actual image was processed or whether the values match computer vision results.

### Stage 2: Cashier Ticket Attachment, Inward Purchase Creation & Weighment Mode
- **Implementation:** `server.py:api_branch_create_invoice()`, `branch_dashboard.html:attachQCInspectionModal()`, `database.py:link_qc_to_invoice()`.
- **Workflow Mechanics:**
  1. Cashier opens inward purchase modal, clicks "Attach QC Ticket", and views pending inspections.
  2. Selecting a ticket auto-populates commodity, moisture, karda, vehicle number, and suggested rate.
  3. Weighment mode is selected:
     - `MANUAL_YARD`: Produce weighed on platform yard scale. Vehicle tare is forced to 0.0.
     - `WEIGHBRIDGE`: Gross vehicle weight minus vehicle tare weight (Dharamkanta).
     - Bag tare deducted based on bag type (Jute 1.0 kg, HDPE 0.5 kg, Loose 0.0 kg).
  4. Inward purchase record is inserted into `purchase_invoices`.
- **Identified Disconnects:**
  - *Double-Claim Vulnerability (AUD-BWF-001):* `qc_ticket_no` in `purchase_invoices` has NO unique constraint. The server executes `UPDATE quality_inspections SET status='LINKED', invoice_id=? WHERE ticket_no=?` without verifying `AND status='PENDING'`. A single QC ticket can be used across multiple invoices.
  - *Un-awaited Farmer Registration (AUD-BWF-007):* In `branch_dashboard.html:2523`, selecting an unregistered farmer triggers an un-awaited background `fetch('/api/branch/farmers/register')`. If the cashier immediately clicks "Confirm & Print", `party_id` is empty or defaults to an unintended party.
  - *Weighbridge Slip Photo Dropped:* While the database schema defines `slip_photo_url TEXT`, the INSERT statement in `api_branch_create_invoice` completely omits `slip_photo_url`, preventing audit of external weighbridge slips.

### Stage 3: Rate Determination, Quality Deductions, Final Payable Amount & APMC Cess
- **Implementation:** `calculations.py:calculate_inward_invoice()`, `server.py:api_branch_create_invoice()`.
- **Workflow Mechanics:**
  1. Statutory Mandi Cess: Evaluated as 0.0 (`mandi_cess_amount = 0.0`). The system strictly adheres to the Mandi statutory rule where no APMC cess or market fee is deducted from primary cultivators.
  2. Mandi Hamali: Exactly ₹25.00 per 100 kg (`net_quintals * 25.0`) is deducted from the farmer.
  3. Quality Deductions:
     $$\text{Excess Moisture \%} = \max(0.0, \text{moisture\_percentage} - 10.0)$$
     $$\text{Moisture Cut (kg)} = \text{uncleaned\_produce\_kg} \times \left(\frac{\text{Excess Moisture \%}}{100}\right)$$
     $$\text{Karda Cut (kg)} = \text{uncleaned\_produce\_kg} \times \left(\frac{\text{karda\_percentage}}{100}\right)$$
     $$\text{Net Weight (kg)} = \text{uncleaned\_produce\_kg} - \text{Moisture Cut} - \text{Karda Cut}$$
     $$\text{Net Quintals} = \frac{\text{Net Weight (kg)}}{100.0}$$
     $$\text{Gross Amount} = \text{Net Quintals} \times \text{Rate per Quintal}$$
     $$\text{Net Payable Amount} = \text{Gross Amount} - \text{Hamali Charge} - \text{Advance Adjusted} - \text{Interest}$$
  4. Paisa Round-off: The net payable is rounded up to the nearest rupee via `math.ceil()`.
- **Identified Disconnects:**
  - *Rate Corridor Bypass on Cash Payouts (AUD-BWF-002):* If the rate exceeds the approved daily corridor, `rate_override_status = 'PENDING'` is flagged, but when `settlement_mode == 'CASH'`, cash is immediately disbursed before Central Accounts approval.

### Stage 4: Farmer Payment Vouchers (Cash vs RTGS, Section 269ST Enforcement)
- **Implementation:** `calculations.py:check_cash_compliance()`, `server.py:api_branch_create_invoice()`, `server.py:api_cashier_disburse_payout()`.
- **Workflow Mechanics:**
  - Under Section 269ST of the Income Tax Act 1961, no person shall receive cash of ₹2,00,000 or more from a person in a day or in respect of a single transaction.
  - Under Section 40A(3), cash payments to non-cultivators (traders/stockers) cannot exceed ₹10,000 per day.
- **Identified Disconnects:**
  - *Cumulative Daily Cash Limit Ignored (AUD-BWF-003):* In `api_branch_create_invoice`, the software only checks `if payable_rounded >= 200000.0:`. It completely omits the query for `today_cumulative_cash_to_party`. A farmer selling 3 loads of ₹1,50,000 in one day receives ₹4,50,000 in physical cash across 3 invoices, exposing the business to a 100% statutory penalty under Section 271DA.
  - *Stocker Cash Disallowance Bypassed:* `party_type == 'STOCKER'` is never checked in `api_branch_create_invoice`, permitting cash payouts up to ₹1,99,999 to traders in direct violation of Section 40A(3).

### Stage 5: Cash Drawer Sessions & Float Reconciliation
- **Implementation:** `database.py:branch_daily_cash_drawers`, `server.py:branch_dashboard_view()`, `server.py:api_branch_create_invoice()`.
- **Workflow Mechanics:**
  - Cashier desk must maintain physical drawer accountability: opening float, disbursements, collections, petty cash, and end-of-day closing count.
- **Identified Disconnects:**
  - *Hardcoded ₹5,00,000 Float Auto-Injection (AUD-BWF-005):* When a drawer record does not exist for the day, lines 2128-2132 and 2420-2425 auto-insert `opening_float = 500000.0` and `calculated_closing_cash = 500000.0`. There is no carry-forward of yesterday's physical closing cash, no cash-in-transit tracking, and no physical shift sign-off.
  - *Missing Session Management:* There are zero API endpoints to record cashier opening count, shift handover, physical cash tally, or cash-drop deposits to the bank.

### Stage 6: Physical Yard Stock Postings & Outward Order Management
- **Implementation:** `server.py:branch_stock_view()`, `server.py:api_branch_create_outward()`.
- **Workflow Mechanics:**
  - Inward purchases increase branch yard stock; outward dispatches to buyers decrease stock.
- **Identified Disconnects:**
  - *Unchecked Outward Dispatch (AUD-BWF-006):* Cashiers can dispatch outward orders without verifying whether physical stock is available. A branch with 10 Quintals of Soyabean can dispatch 500 Quintals.
  - *Negative Stock Masking:* `branch_stock_view` uses `net_qtl = max(0.0, inw_qtl - outw_qtl)`, silently concealing negative balances caused by unauthorized dispatches or unrecorded receipts.
  - *Lack of Physical Inventory Table:* Stock is calculated on-the-fly via `SUM(net_quintals)`. There is no ledger for warehouse shrinkage, storage moisture loss, bagging conversions, or physical inventory audits.

### Stage 7: Accounting Ledgers & Double-Entry Verification
- **Implementation:** `database.py:ledger_entries`, `server.py:api_branch_create_invoice()`, `server.py:api_cashier_disburse_payout()`, `server.py:api_accounts_process_rtgs()`.
- **Workflow Mechanics:**
  - Commercial ERPs require balanced double-entry journals: $\sum \text{Debits} = \sum \text{Credits}$.
- **Identified Disconnects:**
  - *Unbalanced Deferred Cash Payouts (AUD-BWF-004):* In `api_cashier_disburse_payout`, `gross_amount` is debited, `disbursed_amount` is credited, but `hamali_charge` and `advance_adjusted` are NEVER credited, throwing the ledger permanently out of balance.
  - *Single-Sided RTGS Settlements:* In `api_accounts_process_rtgs`, bank transfer settlement creates a credit to `Mandi Central Bank Account` with `debit_amount = 0`, without clearing the `Sundry Creditors (Farmer)` balance created at invoice time.
  - *Ledger Disconnect on Dashboard:* The Accounts Dashboard displays metrics calculated directly from `outward_orders` and `purchase_invoices` tables, rendering the `ledger_entries` table a disconnected, cosmetic artifact.

### Stage 8: Head Office Super Admin Oversight & Daily Rate Broadcast
- **Implementation:** `server.py:api_accounts_set_rate()`, `server.py:api_accounts_rate_override_action()`, `server.py:LiveSyncHub`.
- **Workflow Mechanics:**
  - Central Accounts sets daily price corridor (`min_rate`, `target_rate`, `max_rate`) per commodity.
  - Real-time WebSocket (`/ws/live`) and Supabase push propagate rates to yard terminals.
- **Identified Disconnects:**
  - *Inverted Corridor Acceptance (AUD-BWF-009):* `/api/accounts/rates` accepts `min_rate > max_rate` without validation, causing every subsequent transaction to be flagged as out-of-corridor.
  - *Orphaned Payouts on Override Rejection (AUD-BWF-008):* If Central Accounts rejects an out-of-corridor invoice, `payout_status` is marked `CANCELLED`, but previously disbursed cash in `cashier_payouts` is not reversed, and yard stock is dropped while physical grain remains in the yard.

---

## 4. Business Workflow Findings (AUD-BWF-001 through AUD-BWF-009)

---

### Finding AUD-BWF-001
- **Severity:** CRITICAL
- **Module:** Inward Procurement & QC Assaying Attachment
- **File / Line:** `commoditi software/server.py:2394-2396`, `commoditi software/database.py:294-302`, `commoditi software/database.py:366-410`
- **Observed:** Inward purchase invoices can reference arbitrary QC ticket numbers, and linking updates `quality_inspections` without verifying whether the ticket is already linked to another invoice.
- **Expected:** Each QC ticket must be unique, single-use, and strictly locked to a single inward purchase invoice. Once linked, any attempt to attach it to a subsequent invoice must be rejected.
- **Actual:** `purchase_invoices.qc_ticket_no` has no `UNIQUE` constraint or foreign key check. In `server.py`:
  ```python
  if qc_ticket_no and qc_ticket_no.strip():
      cur.execute("UPDATE quality_inspections SET status='LINKED', invoice_id=? WHERE ticket_no=?", (invoice_id, qc_ticket_no.strip()))
  ```
  The update does not check `WHERE ticket_no=? AND status='PENDING'`. A cashier or multiple cashiers can attach the exact same QC inspection slip to multiple farmer purchase invoices.
- **Evidence:**
  ```sql
  -- From commoditi software/database.py:366
  CREATE TABLE IF NOT EXISTS purchase_invoices (
      id TEXT PRIMARY KEY,
      branch_id TEXT NOT NULL REFERENCES branches(id),
      token_number TEXT UNIQUE NOT NULL,
      invoice_date TEXT NOT NULL,
      party_id TEXT NOT NULL REFERENCES parties(id),
      commodity_name TEXT NOT NULL,
      hsn_code TEXT NOT NULL,
      quality_grade TEXT DEFAULT 'STANDARD',
      vehicle_number TEXT,
      qc_ticket_no TEXT, -- NO UNIQUE CONSTRAINT
  ```
- **Business Impact:** High risk of internal fraud and double-claims. A single high-quality grain inspection slip can be reused to justify premium pricing across multiple truckloads of low-quality or adulterated grain, resulting in substantial financial loss to the mandi.
- **Correction:**
  1. Add a `UNIQUE` index on `purchase_invoices(qc_ticket_no) WHERE qc_ticket_no IS NOT NULL`.
  2. In `api_branch_create_invoice`, validate that the QC ticket exists, belongs to the same branch and commodity, and has `status = 'PENDING'`:
  ```python
  if qc_ticket_no and qc_ticket_no.strip():
      cur.execute("SELECT id, status, branch_id, commodity_name FROM quality_inspections WHERE ticket_no=?", (qc_ticket_no.strip(),))
      qc_row = cur.fetchone()
      if not qc_row:
          raise HTTPException(status_code=400, detail="Invalid QC ticket number.")
      if qc_row["status"] != "PENDING":
          raise HTTPException(status_code=400, detail=f"QC Ticket #{qc_ticket_no} has already been used and linked to another invoice.")
      if qc_row["branch_id"] != branch_id:
          raise HTTPException(status_code=400, detail="QC Ticket belongs to a different branch yard.")
      cur.execute("UPDATE quality_inspections SET status='LINKED', invoice_id=? WHERE ticket_no=? AND status='PENDING'", (invoice_id, qc_ticket_no.strip()))
      if cur.rowcount == 0:
          raise HTTPException(status_code=409, detail="Concurrent conflict: QC Ticket was just linked by another transaction.")
  ```
- **Tests:** Verify that attempting to create two invoices with the same `qc_ticket_no` raises HTTP 400 on the second attempt.
- **Dependencies:** `quality_inspections`, `purchase_invoices`.

---

### Finding AUD-BWF-002
- **Severity:** CRITICAL
- **Module:** Rate Corridor Governance & Cashier Settlement
- **File / Line:** `commoditi software/server.py:2308-2345`
- **Observed:** When a proposed purchase rate is outside the approved daily price corridor, the system flags `rate_override_status = 'PENDING'`, but if `settlement_mode == 'CASH'`, it immediately disburses cash to the farmer.
- **Expected:** Any transaction requiring a rate override must be blocked from immediate cash payout until Central Accounts approves the rate in the system.
- **Actual:** Lines 2308-2342 set `rate_override_status = "PENDING"` when `check["requires_override"]` is true. However, lines 2336-2342 immediately evaluate `if settlement_mode == "CASH": effective_payout_status = "PAID"`. The cash is recorded as disbursed, the cash drawer is reduced, and cash is given to the farmer. Central Accounts only receives an informational notification (`rate_override_requested`) after the physical cash has already left the building.
- **Evidence:**
  ```python
  # commoditi software/server.py:2308-2345
  if rate_row:
      check = check_rate_corridor(rate_per_quintal, rate_row["min_rate_per_qtl"], rate_row["max_rate_per_qtl"])
      if check["requires_override"]:
          is_rate_overridden = 1
          rate_override_status = "PENDING"
  ...
  effective_payout_status = "PENDING"
  if settlement_mode == "CASH":
      if payable_rounded >= 200000.0:
          settlement_mode = "RTGS"
          effective_payout_status = "RTGS_PENDING"
      else:
          effective_payout_status = "PAID"  # CASH IS DISBURSED EVEN IF RATE_OVERRIDE_STATUS == 'PENDING'!
  ```
- **Business Impact:** Complete failure of financial oversight. Cashiers can collude with sellers to pay inflated rates far above market value. Once cash is disbursed, subsequent rejection by Central Accounts cannot recover the funds.
- **Correction:** If `rate_override_status == "PENDING"`, force settlement mode to remain `PENDING` and disallow cash payout:
  ```python
  if rate_override_status == "PENDING":
      effective_payout_status = "PENDING"
      if settlement_mode == "CASH":
          logger.warning(f"Cash settlement blocked for invoice {token_number}: Rate override pending Central Accounts approval.")
  ```
- **Tests:** Submit an inward purchase with rate exceeding `max_rate_per_qtl` and `settlement_mode='CASH'`. Assert `effective_payout_status` is `PENDING`, no record is inserted into `cashier_payouts`, and drawer cash is not reduced.
- **Dependencies:** `daily_commodity_rates`, `purchase_invoices`, `branch_daily_cash_drawers`.

---

### Finding AUD-BWF-003
- **Severity:** CRITICAL
- **Module:** Income Tax Compliance (Section 269ST & Section 40A(3))
- **File / Line:** `commoditi software/server.py:2336-2342`, `commoditi software/calculations.py:86-118`
- **Observed:** The inward invoice creation endpoint only checks if the individual invoice exceeds ₹2,00,000, failing to check aggregate daily cash disbursements to the farmer or trader.
- **Expected:** Under Section 269ST of the Income Tax Act 1961, no person shall receive an amount of ₹2,00,000 or more in aggregate from a person in a day. The system must query cumulative cash disbursed to the party on the current date across all transactions before allowing a cash payout. Under Section 40A(3), cash payouts to stockers/merchants must be capped at ₹10,000 per day.
- **Actual:** The helper `check_cash_compliance` implements these checks, but it is ONLY called in `/api/cashier/payout`. In `api_branch_create_invoice`, it was omitted. The cashier can process multiple invoices of ₹1,80,000 each for the same farmer on the same day, disbursing ₹5,40,000 in physical cash.
- **Evidence:**
  ```python
  # In api_branch_create_invoice (server.py:2336-2342):
  if settlement_mode == "CASH":
      if payable_rounded >= 200000.0:
          settlement_mode = "RTGS"
          effective_payout_status = "RTGS_PENDING"
      else:
          effective_payout_status = "PAID"
  # Missing: call to check_cash_compliance() and query of today's cumulative cash!
  ```
- **Business Impact:** Direct violation of Section 269ST. Under Section 271DA of the Income Tax Act, the penalty for receiving cash in violation of Section 269ST is equal to 100% of the amount received in cash. A single day of split transactions could result in millions of rupees in statutory tax penalties and revocation of the mandi license.
- **Correction:** Integrate `check_cash_compliance` in `api_branch_create_invoice` before authorizing cash payout:
  ```python
  if settlement_mode == "CASH":
      cur.execute("SELECT party_type FROM parties WHERE id=?", (party_id,))
      p_row = cur.fetchone()
      p_type = p_row["party_type"] if p_row else "FARMER"
      
      cur.execute("""
          SELECT COALESCE(SUM(amount_paid), 0.0) 
          FROM cashier_payouts 
          WHERE party_id=? AND date(created_at)=? AND payout_mode='CASH'
      """, (party_id, today_str))
      cum_cash = cur.fetchone()[0]
      
      compliance = check_cash_compliance(
          party_type=p_type,
          payout_mode="CASH",
          payout_amount=payable_rounded,
          today_cumulative_cash_to_party=cum_cash
      )
      if not compliance["allowed"]:
          settlement_mode = "RTGS"
          effective_payout_status = "RTGS_PENDING"
  ```
- **Tests:** Create Invoice 1 for Farmer A with payout ₹1,50,000 in cash. Create Invoice 2 on the same day for Farmer A with payout ₹60,000 in cash. Verify Invoice 2 automatically converts to `RTGS_PENDING` with Section 269ST notice.
- **Dependencies:** `calculations.py:check_cash_compliance`, `cashier_payouts`, `parties`.

---

### Finding AUD-BWF-004
- **Severity:** HIGH
- **Module:** Accounting & Double-Entry Ledger Posting
- **File / Line:** `commoditi software/server.py:1584-1589`, `commoditi software/server.py:2434-2465`, `commoditi software/server.py:4082-4101`
- **Observed:** Ledger entries created across inward purchase invoices, deferred cashier payouts, and RTGS disbursements do not balance debits and credits, and RTGS posts single-sided entries.
- **Expected:** Every financial transaction must satisfy double-entry accounting:
  $$\sum \text{Debits} = \sum \text{Credits}$$
  In RTGS purchases:
  - At purchase: Debit Commodity Purchases (`gross_amount`), Credit Hamali Deduction (`hamali_charge`), Credit Sundry Creditors (`net_payable_amount`).
  - At disbursement: Debit Sundry Creditors (`net_payable_amount`), Credit Bank Account (`net_payable_amount`).
- **Actual:**
  1. In `api_accounts_process_rtgs:1586-1588`, the settlement entry records:
     `Credit Mandi Central Bank Account = net_payable_amount, Debit = 0`.
     There is NO corresponding Debit to `Sundry Creditors (Farmer)`. Farmer accounts remain credited as unpaid liabilities indefinitely.
  2. In `api_cashier_disburse_payout:4082-4101` (deferred payouts):
     Debit `Commodity Purchase Account` = `gross_amount`.
     Credit `Branch Cash Drawer` = `disbursed_amount` (`net_payable + round_off`).
     Debit `Round-Off Difference Account` = `round_off`.
     Credit to `Hamali Deduction Account` is OMITTED. Credit to `Loan Advances` is OMITTED.
     Therefore: $\text{Debit} - \text{Credit} = \text{hamali\_charge} + \text{advance\_adjusted} \neq 0$.
- **Evidence:**
  ```python
  # In api_accounts_process_rtgs (server.py:1586-1588):
  cur.execute("""
      INSERT INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, credit_amount, narration)
      VALUES (?, ?, ?, 'RTGS_PAYMENT', ?, 'Mandi Central Bank Account', ?, 0, ?, ?)
  """, (f"led-{uuid.uuid4().hex[:6]}", inv["branch_id"], today_str, inv["token_number"], inv["party_id"], inv["net_payable_amount"], ...))
  # Single-sided entry! No debit to Sundry Creditors!
  ```
- **Business Impact:** The trial balance and financial statements cannot balance. External audits by chartered accountants will fail, tax returns cannot be reconciled with books of accounts, and liability balances will be grossly distorted.
- **Correction:** Implement complete, balanced double-entry accounting transactions in both RTGS processing and deferred payouts, including proper clearing of `Sundry Creditors` and crediting of `Hamali Deduction Account` and `Advance Receivables`.
- **Tests:** Execute automated balance query:
  `SELECT SUM(debit_amount) - SUM(credit_amount) FROM ledger_entries;`
  Assert the difference is exactly `0.00` across all transactions.
- **Dependencies:** `ledger_entries`, `purchase_invoices`, `cashier_payouts`.

---

### Finding AUD-BWF-005
- **Severity:** HIGH
- **Module:** Cash Drawer Session Management & Custody
- **File / Line:** `commoditi software/server.py:2128-2133`, `commoditi software/server.py:2420-2425`
- **Observed:** Cash drawer records are created automatically with a hardcoded ₹5,00,000 opening float without cashier verification or carry-forward from previous dates.
- **Expected:** Cash drawer sessions must require an authenticated cashier to count and enter the opening float at the start of shift, verify carry-forward from the previous day's closing balance or bank withdrawal, and perform a physical count reconciliation at end of shift.
- **Actual:** If a record for the current date does not exist in `branch_daily_cash_drawers`, the server auto-inserts:
  `opening_float = 500000.0`, `calculated_closing_cash = 500000.0`, `physical_counted_cash = 500000.0`.
  No endpoint exists to count opening cash, record additions from bank, or reconcile physical closing cash.
- **Evidence:**
  ```python
  # commoditi software/server.py:2129-2132
  cur.execute("""
      INSERT OR IGNORE INTO branch_daily_cash_drawers 
      (id, branch_id, record_date, opening_float, total_cash_payouts, petty_expenses_cash, bank_withdrawals_inward, calculated_closing_cash, physical_counted_cash)
      VALUES (?, ?, ?, 500000.0, 0.0, 0.0, 0.0, 500000.0, 500000.0)
  """, (f"drw-{actual_branch_id}-{selected_date}", actual_branch_id, selected_date))
  ```
- **Business Impact:** Total absence of physical cash custody controls. In a mandi handling tens of lakhs of rupees daily, unverified phantom cash entries hide physical cash theft, unrecorded disbursements, and float shortages.
- **Correction:**
  1. Create explicit endpoints `/api/branch/cash-drawer/open` and `/api/branch/cash-drawer/close`.
  2. Carry forward the previous day's `physical_counted_cash` as today's expected opening float.
  3. Require denomination counting (notes of 500, 200, 100, 50, 20, 10, coins) during opening and closing, flagging any discrepancy between physical count and system calculation.
- **Tests:** Verify that accessing the branch dashboard without an opened drawer prompts the cashier to open the session and count float.
- **Dependencies:** `branch_daily_cash_drawers`, `cashier_payouts`.

---

### Finding AUD-BWF-006
- **Severity:** HIGH
- **Module:** Yard Inventory & Outward Sales Dispatch
- **File / Line:** `commoditi software/server.py:2545-2612`, `commoditi software/server.py:3006`
- **Observed:** Outward dispatches to buyers do not validate available yard stock, and stock calculations clamp negative inventory to zero.
- **Expected:** The system must verify that physical net stock for the specified commodity at the branch yard is greater than or equal to the outward dispatch quantity. Negative stock must be prevented.
- **Actual:** `api_branch_create_outward` directly inserts the dispatch record into `outward_orders` without querying inward purchases or current balance. In `branch_stock_view`:
  ```python
  net_qtl = max(0.0, inw_qtl - outw_qtl)
  ```
  If 200 Quintals are inward and 350 Quintals are dispatched, `net_qtl` silently displays `0.00 Qtl` rather than `-150.00 Qtl` (which would alert management to missing inward invoices or dispatch theft).
- **Evidence:**
  ```python
  # In server.py:3006
  net_qtl = max(0.0, inw_qtl - outw_qtl) # Masks negative stock!
  ```
- **Business Impact:** High inventory shrinkage risk. Dispatches can be issued for produce that was never received, or grain can be dispatched off-book without physical inventory validation.
- **Correction:**
  1. Add stock validation in `api_branch_create_outward`:
     ```python
     cur.execute("""
         SELECT (SELECT COALESCE(SUM(net_quintals), 0.0) FROM purchase_invoices WHERE branch_id=? AND commodity_name=? AND payout_status != 'CANCELLED')
              - (SELECT COALESCE(SUM(net_quintals), 0.0) FROM outward_orders WHERE branch_id=? AND commodity_name=? AND status != 'CANCELLED') as current_stock
     """, (branch_id, commodity_name, branch_id, commodity_name))
     available = cur.fetchone()["current_stock"]
     if calc["net_quintals"] > available:
         raise HTTPException(status_code=400, detail=f"Insufficient yard stock: Available {available:.2f} Qtl, requested dispatch {calc['net_quintals']:.2f} Qtl.")
     ```
  2. Remove `max(0.0, ...)` from `branch_stock_view` so negative balances are clearly flagged with red alerts.
- **Tests:** Attempt to create an outward dispatch of 100 Qtl when branch stock is 20 Qtl. Verify request is rejected with HTTP 400.
- **Dependencies:** `outward_orders`, `purchase_invoices`.

---

### Finding AUD-BWF-007
- **Severity:** MEDIUM
- **Module:** Cultivator Auto-Registration & QC Attachment UI
- **File / Line:** `commoditi software/templates/branch_dashboard.html:2523-2531`
- **Observed:** Selecting a QC ticket with an unregistered farmer triggers an un-awaited background registration fetch, causing race conditions during invoice submission.
- **Expected:** Farmer registration must be completed and confirmed before populating the form and enabling invoice submission.
- **Actual:** Lines 2523-2530 trigger `fetch('/api/branch/farmers/register')` as a floating promise. If the cashier submits the form before the network response arrives, `party_id` is sent as undefined or empty string, failing invoice creation or linking the invoice to an arbitrary farmer.
- **Evidence:**
  ```javascript
  // branch_dashboard.html:2523-2530
  fetch('/api/branch/farmers/register', {
      method: 'POST',
      body: regData
  }).then(r => r.json()).then(data => {
      if (data && data.party && data.party.id) {
          newOpt.value = data.party.id;
      }
  }).catch(e => console.warn('Farmer auto-registration note:', e));
  // Un-awaited asynchronous background call!
  ```
- **Business Impact:** Intermittent invoice creation failures, cashier frustration during peak yard rush, and risk of misattributing farmer payouts.
- **Correction:** Use `await` inside an `async` handler or disable the "Confirm & Print" button with a loading spinner until the farmer registration returns successfully.
- **Tests:** Simulate 500ms network delay on `/api/branch/farmers/register` and confirm form submission is blocked until registration completes.
- **Dependencies:** `branch_dashboard.html`, `/api/branch/farmers/register`.

---

### Finding AUD-BWF-008
- **Severity:** MEDIUM
- **Module:** Rate Override Rejection & Payout Invalidation
- **File / Line:** `commoditi software/server.py:1523-1529`
- **Observed:** Rejection of an out-of-corridor rate override marks `purchase_invoices.payout_status = 'CANCELLED'`, but leaves disbursed cash and ledger entries intact while dropping inventory.
- **Expected:** Rejection of an inward purchase must initiate a formal reversal workflow: reverse cashier payouts, debit cash drawer / account receivables from the party, reverse ledger entries, and manage physical return of grain.
- **Actual:** When Central Accounts clicks "Reject", line 1526 only executes:
  `UPDATE purchase_invoices SET rate_override_status='REJECTED', payout_status='CANCELLED'`.
  The cash payout record in `cashier_payouts` remains valid, the drawer balance remains depleted, ledger entries remain active, and the stock aggregate drops the quantity.
- **Evidence:**
  ```python
  # server.py:1523-1528
  cur.execute("""
      UPDATE purchase_invoices 
      SET rate_override_status='REJECTED', payout_status='CANCELLED', rate_override_reason = rate_override_reason || ' | HQ Rejected: ' || ?
      WHERE id=?
  """, (accountant_reason, invoice_id))
  ```
- **Business Impact:** Unreconciled physical inventory and cash discrepancies. The system shows cash was spent, but the associated invoice is cancelled, creating an audit violation for untracked disbursements.
- **Correction:** Disallow immediate cash payout while override is pending (AUD-BWF-002). If an unpaid invoice is rejected, cancel invoice and un-link the QC ticket. If a paid invoice is rejected, generate formal reversal debit/credit notes.
- **Tests:** Reject an invoice and verify state consistency across `purchase_invoices`, `cashier_payouts`, `ledger_entries`, and `quality_inspections`.
- **Dependencies:** `purchase_invoices`, `cashier_payouts`, `ledger_entries`.

---

### Finding AUD-BWF-009
- **Severity:** MEDIUM
- **Module:** Daily Price Corridor Master Setup
- **File / Line:** `commoditi software/server.py:1387-1420`
- **Observed:** The daily commodity rate setup endpoint accepts arbitrary float values for `min_rate`, `target_rate`, and `max_rate` without logical boundary validation.
- **Expected:** The server must enforce the invariant:
  $$0 < \text{min\_rate} \le \text{target\_rate} \le \text{max\_rate}$$
- **Actual:** An accountant entering `min_rate = 5500` and `max_rate = 4500` succeeds without error. When this happens, `check_rate_corridor` fails on all subsequent invoices because no rate can be simultaneously $\ge 5500$ and $\le 4500$.
- **Evidence:**
  ```python
  # server.py:1387-1420
  # No check for min_rate <= target_rate <= max_rate before INSERT / UPDATE
  ```
- **Business Impact:** Denial of normal yard checkout. All yard cashier terminals stall and require rate override approvals for every incoming truckload.
- **Correction:** Add validation in `api_accounts_set_rate`:
  ```python
  if min_rate <= 0 or target_rate <= 0 or max_rate <= 0:
      raise HTTPException(status_code=400, detail="Rates must be positive numbers.")
  if not (min_rate <= target_rate <= max_rate):
      raise HTTPException(status_code=400, detail=f"Invalid corridor boundary: Min (₹{min_rate}) must be <= Target (₹{target_rate}) <= Max (₹{max_rate}).")
  ```
- **Tests:** Send `min_rate=5000, target_rate=4000, max_rate=3000` to `/api/accounts/rates`. Assert HTTP 400.
- **Dependencies:** `daily_commodity_rates`.

---

## 5. Workflow Disconnect Summary Matrix

| Finding ID | Severity | Stage Affected | Root Cause | Business Impact |
|:---|:---|:---|:---|:---|
| **AUD-BWF-001** | CRITICAL | Stage 2: Attachment | Missing UNIQUE constraint & missing `status='PENDING'` check | Double-spending of quality certificates; low-grade grain bought at premium prices |
| **AUD-BWF-002** | CRITICAL | Stage 3: Rate Approval | Immediate cash payout ignores pending override flag | Unapproved purchase prices paid in cash without Central Accounts authorization |
| **AUD-BWF-003** | CRITICAL | Stage 4: Payout Limit | Omitted check for cumulative daily cash disbursements | Section 269ST violation; 100% statutory tax penalty under Section 271DA |
| **AUD-BWF-004** | HIGH | Stage 7: Accounting | Single-sided RTGS entries; missing Hamali/advance credits on deferred payout | Unbalanced books; distorted balance sheet; audit failure |
| **AUD-BWF-005** | HIGH | Stage 5: Cash Custody | Hardcoded ₹5,00,000 float injected daily without reconciliation | Physical cash theft or discrepancies concealed; no float accountability |
| **AUD-BWF-006** | HIGH | Stage 6: Yard Stock | No stock validation prior to outward dispatch; negative stock clamped to 0 | Dispatches issued for non-existent stock; physical stock shrinkage |
| **AUD-BWF-007** | MEDIUM | Stage 1/2: UI Flow | Floating asynchronous registration fetch in frontend | Race condition causing missing `party_id` on invoice submission |
| **AUD-BWF-008** | MEDIUM | Stage 8: HQ Rejection | Rejection marks invoice cancelled without reversing cash payouts or ledgers | Financial discrepancies; phantom expenses without corresponding produce |
| **AUD-BWF-009** | MEDIUM | Stage 8: Rate Setup | Missing invariant check `min_rate <= target_rate <= max_rate` | Broken rate corridor causing 100% of yard invoices to require manual overrides |

---
*End of Report 05: Business Workflow & Transaction Lifecycle Audit.*
