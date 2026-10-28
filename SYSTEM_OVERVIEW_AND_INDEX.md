# Commodity Trading & Mandi ERP — Master System Index
**Folder: `commoditi software` | Comprehensive System Blueprint & Documentation Index**

---

## 1. Overview of Gathered Documentation

This folder contains all research, system specifications, mathematical calculation formulas, accounting ledgers, database blueprints, and the **three-level governance architecture with dedicated login panels** for your **Commodity Purchase & Mandi Accounting ERP**.

```
commoditi software/
├── SYSTEM_OVERVIEW_AND_INDEX.md                 <-- (This master index & executive blueprint)
├── IMPLEMENTATION_PLAN.md                       <-- (Full 3-tier governance roadmap & 9-step workflow)
├── COMMODITY_TRADER_PAIN_POINTS_RESEARCH.md     <-- (Real field issues: double entry, cash scrutiny, deductions)
├── KHATAOS_AND_GST_BILLING_INSPECTION.md        <-- (KhataOS analysis, Rojmel denomination tally, GST/TDS rules)
├── CALCULATIONS_AND_FORMULAS_SPEC.md            <-- (Exact formulas: Manual Kanta, tare, nami, karda, net payable)
├── ACCOUNTING_LEDGERS_AND_REPORTS_PLAN.md       <-- (Chart of Accounts, journal entries, 7 essential reports)
├── MULTI_BRANCH_AND_RBAC_ARCHITECTURE.md        <-- (3+ Branches, Daily Min/Max Rate board, Admin/Cashier roles)
├── DATABASE_SCHEMA_BLUEPRINT.sql                <-- (Complete production SQL schema with all tables & constraints)
├── calculations.py                              <-- (Standalone Python reference implementation of all formulas)
├── database.py                                  <-- (SQLite setup with 3 branches, users, and seed data)
└── tests/
    └── test_calculations.py                    <-- (Unit test suite validating all calculations & tax checks)
```

---

## 2. Three Distinct Login Pages & Panels (Managed by Super Admin)

| Level / Panel | Dedicated Route | Purpose & Visual Distinction | Managing Authority |
| :--- | :--- | :--- | :--- |
| **Level 1: Super Admin** | `/admin/login`<br>`-> /admin/dashboard` | **Executive Command Center:** Dark slate UI, macro KPI summaries, cross-branch analytics, branch/commodity management, accountant user creation. | **Master Administrator:** Controls and creates all branches, commodities, and accountant accounts. |
| **Level 2: Central Accounts** | `/accounts/login`<br>`-> /accounts/dashboard` | **Financial Control Room:** Dense financial UI, daily buying price master board, sole rate override authorization queue, inspector dropdown master, BRS, journals, ledgers, and P&L. | Created and governed by Super Admin. Has exclusive authority over daily rates & overrides. |
| **Level 3: Branch Dashboard** | `/branch/login`<br>`-> /branch/dashboard` | **Yard Touch/Keypad Terminal:** Clean, high-contrast, large text, fast entry, zero financial distraction, 80mm thermal slip printing. Scoped strictly to assigned branch. | Created and governed by Super Admin. Follows rates published by Central Accounts. |

---

## 3. Quick Mapping to Core Workflow & Confirmed Decisions

| Confirmed Decision / Rule | Where It Is Documented & Defined | Summary of Solution |
| :--- | :--- | :--- |
| **Dedicated Login Pages & Panels** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 1 & 2) | Three distinct URL namespaces (`/admin`, `/accounts`, `/branch`) with customized UX layouts, all managed centrally under Super Admin. |
| **Sole Rate Override Authority** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 3 & 5) | **Central Accounts is the ONLY authority** that can approve out-of-corridor purchase rates. Branch Managers cannot self-approve; Super Admin does not handle operational rate tickets. |
| **Inspector Master & Dropdown** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 3 & 5) | Branch operators select the lot inspector from a **pre-approved dropdown**; Central Accounts maintains the master list of authorized inspectors. |
| **Inter-Branch Stock Transfer Pricing** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 6) | Dispatches between branches are accounted at **Internal Transfer Price (ITP)** with markups eliminated on consolidated Super Admin reporting. |
| **Weighbridge Photo Upload Policy** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 5, Step 4) | In manual external kanta mode, **uploading a slip photo is OPTIONAL**; entering external slip number and kanta name is mandatory. |
| **Cash Rounding Rule** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 5, Step 8) | Fractional paisa on cash payouts **round up to the nearest integer rupee**. The difference is automatically balanced via an explicit entry in `Round-Off Account`. |
| **Preservation of Financial History** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 7) | Master records (branches, commodities, parties, users) use soft deletion (`is_active = FALSE`). Historical invoices and ledgers remain immutable. |
| **Stock Valuation & P&L Rules** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 6) | P&L figures enforce **Weighted Average Cost (WAC)** valuation, deriving landed cost ($V_{\text{gross}} + \text{Hamali} + \text{Cess} - \text{Cuts}$) and factoring in storage shrinkage loss (*karda*). |
| **Farmer Search & Duplicate Check** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 5, Step 2) | Multi-attribute search (Phone, Aadhaar, Name, Village). Hard blocks on duplicate phone or Aadhaar numbers; warnings on duplicate names in same village. |
| **Invoice State Machine & Anti-Double Pay** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 5, Step 7 & 8) | States: `DRAFT` $\to$ `PENDING_APPROVAL` $\to$ `ISSUED_UNVERIFIED` $\to$ `VERIFIED` $\to$ `PAID`. Cashier verifies slip, records stamp, and locks against duplicate payouts. Reprints clearly watermarked. |
| **Section 269ST & 40A(3) Compliance** | [`CALCULATIONS_AND_FORMULAS_SPEC.md`](file:///c:/projects/tests/commoditi%20software/CALCULATIONS_AND_FORMULAS_SPEC.md) & [`calculations.py`](file:///c:/projects/tests/commoditi%20software/calculations.py) | Hard-blocks cash payouts $\ge ₹2,00,000$ to any farmer in a day (Sec 269ST). Hard-blocks cash payouts $> ₹10,000$ to registered stockers (Sec 40A(3)). |
| **Port Binding (Port 8080)** | [`IMPLEMENTATION_PLAN.md`](file:///c:/projects/tests/commoditi%20software/IMPLEMENTATION_PLAN.md) (Section 2) | Configured strictly to **Port 8080** (`http://127.0.0.1:8080`) to eliminate conflict with the host's existing restaurant app running on port 8000. |

---

## 4. How to Review and Run the Reference Validation Suite

All mathematical calculations and statutory checks have been verified with automated unit tests:

To run the calculation verification suite:
```powershell
python -m unittest "c:\projects\tests\commoditi software\tests\test_calculations.py"
```

To initialize or inspect the local reference SQLite database:
```powershell
python "c:\projects\tests\commoditi software\database.py"
```
