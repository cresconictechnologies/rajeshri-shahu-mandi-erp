-- ==============================================================================
-- RAJARSHI SHAHU MANDI ERP — PRODUCTION SUPABASE / POSTGRESQL SCHEMA
-- Powered by Cresconic Technologies
-- APMC Mandi Procurement, Multi-Branch Weighbridge & AI Grain Assaying System
-- Target: PostgreSQL 15+ / Supabase
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. EXTENSIONS & PREREQUISITES
-- ------------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------------------------
-- 2. ENUMS & DOMAIN TYPES
-- ------------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE user_role_t AS ENUM (
        'SUPER_ADMIN',
        'ACCOUNTANT_HQ',
        'BRANCH_MUNIM',
        'BRANCH_CASHIER',
        'QUALITY_INSPECTOR'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE party_type_t AS ENUM (
        'FARMER',
        'STOCKER',
        'BUYER'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE weighment_mode_t AS ENUM (
        'MANUAL_EXTERNAL',
        'DIGITAL_SCALE',
        'MANUAL_YARD',
        'WEIGHBRIDGE'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE payout_status_t AS ENUM (
        'PENDING',
        'PAID',
        'CANCELLED',
        'RTGS_PENDING'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE payout_mode_t AS ENUM (
        'CASH',
        'BANK_TRANSFER',
        'UPI',
        'CHEQUE'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE qc_status_t AS ENUM (
        'PENDING',
        'ACCEPTED',
        'REJECTED',
        'INVOICED'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ------------------------------------------------------------------------------
-- 3. CORE MULTI-BRANCH ENTITIES
-- ------------------------------------------------------------------------------

-- Branches / APMC Yards (e.g. Chikhali, Varvand, Dhad, Mehkar)
CREATE TABLE IF NOT EXISTS branches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    mandi_license_no TEXT,
    address TEXT,
    phone TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Users / Operators (Linked to local credentials or Supabase Auth UUID)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    role user_role_t NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Commodities (Agricultural crops handled in yards)
CREATE TABLE IF NOT EXISTS commodities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    hsn_code TEXT NOT NULL,
    standard_moisture_pct NUMERIC(5, 2) NOT NULL DEFAULT 10.00,
    mandi_cess_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00 CHECK (mandi_cess_pct = 0.00), -- Statutory Zero Cess Invariant
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Daily Commodity Rate Corridors (Established per yard/day)
CREATE TABLE IF NOT EXISTS daily_commodity_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rate_date DATE NOT NULL DEFAULT CURRENT_DATE,
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    commodity_name TEXT NOT NULL,
    quality_grade TEXT NOT NULL DEFAULT 'STANDARD',
    min_rate_per_qtl NUMERIC(10, 2) NOT NULL CHECK (min_rate_per_qtl > 0),
    target_rate_per_qtl NUMERIC(10, 2) NOT NULL CHECK (target_rate_per_qtl >= min_rate_per_qtl),
    max_rate_per_qtl NUMERIC(10, 2) NOT NULL CHECK (max_rate_per_qtl >= target_rate_per_qtl),
    set_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_daily_rates UNIQUE (rate_date, branch_id, commodity_name, quality_grade)
);

-- Parties: Farmers, Stockers, and Buyers
CREATE TABLE IF NOT EXISTS parties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    home_branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    party_type party_type_t NOT NULL DEFAULT 'FARMER',
    village TEXT,
    pan_number VARCHAR(10),
    aadhaar_number VARCHAR(12),
    gstin VARCHAR(15),
    khasra_record_no TEXT,
    bank_name TEXT,
    bank_account_no TEXT,
    bank_ifsc VARCHAR(11),
    current_advance NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    advance_interest_rate NUMERIC(5, 2) NOT NULL DEFAULT 12.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Inspectors (Assayers conducting computer vision and physical QC)
CREATE TABLE IF NOT EXISTS inspectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    designation TEXT DEFAULT 'Assayer / Sampler',
    phone TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- ------------------------------------------------------------------------------
-- 4. PROCUREMENT, WEIGHMENT & INVOICING
-- ------------------------------------------------------------------------------

-- Inward Purchase Invoices (Dharamkanta weighment, cuts, charges, net payable)
CREATE TABLE IF NOT EXISTS purchase_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE RESTRICT,
    token_number TEXT UNIQUE NOT NULL,
    invoice_date DATE NOT NULL DEFAULT CURRENT_DATE,
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
    commodity_name TEXT NOT NULL,
    hsn_code TEXT NOT NULL,
    quality_grade TEXT NOT NULL DEFAULT 'STANDARD',
    vehicle_number TEXT,
    qc_ticket_no TEXT,
    
    -- Weighment mode and external slip capture
    weighment_mode weighment_mode_t NOT NULL DEFAULT 'MANUAL_YARD',
    external_kanta_name TEXT,
    external_slip_number TEXT,
    slip_photo_url TEXT, -- Supabase Storage URL
    
    -- Tare and gross weights (in kg)
    bag_count INTEGER NOT NULL DEFAULT 0 CHECK (bag_count >= 0),
    bag_type TEXT DEFAULT 'LOOSE',
    gross_weight_kg NUMERIC(12, 2) NOT NULL CHECK (gross_weight_kg >= 0),
    vehicle_tare_kg NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (vehicle_tare_kg >= 0),
    bag_tare_kg NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (bag_tare_kg >= 0),
    
    -- Quality cuts (Moisture & Karda)
    moisture_percentage NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    moisture_cut_kg NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (moisture_cut_kg >= 0),
    karda_percentage NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    karda_cut_kg NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (karda_cut_kg >= 0),
    net_weight_kg NUMERIC(12, 2) NOT NULL CHECK (net_weight_kg >= 0),
    net_quintals NUMERIC(12, 4) NOT NULL CHECK (net_quintals >= 0),
    
    -- Pricing and manual rate override controls
    rate_per_quintal NUMERIC(10, 2) NOT NULL CHECK (rate_per_quintal > 0),
    is_rate_overridden BOOLEAN NOT NULL DEFAULT FALSE,
    rate_override_by UUID REFERENCES users(id) ON DELETE SET NULL,
    rate_override_reason TEXT,
    
    -- Line item additions and deductions
    gross_amount NUMERIC(14, 2) NOT NULL CHECK (gross_amount >= 0),
    hamali_charge NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    tulai_charge NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    silai_charge NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    bardana_deduction NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    
    -- Statutory 0% Mandi Cess Enforcement
    mandi_cess_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (mandi_cess_amount = 0.00),
    
    -- Advance & Loan adjustments
    advance_adjusted NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    interest_adjusted NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    
    -- Taxation
    gst_rate NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    gst_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    tds_194q_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    
    -- Net final payable
    net_payable_amount NUMERIC(14, 2) NOT NULL,
    payout_status payout_status_t NOT NULL DEFAULT 'PENDING',
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- ------------------------------------------------------------------------------
-- 5. CASHIER DISBURSEMENT & SECTION 269ST ENFORCEMENT
-- ------------------------------------------------------------------------------

-- Cashier Payouts (Farmer settlements with denomination counts & Sec 269ST triggers)
CREATE TABLE IF NOT EXISTS cashier_payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE RESTRICT,
    invoice_id UUID NOT NULL REFERENCES purchase_invoices(id) ON DELETE RESTRICT,
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
    payout_mode payout_mode_t NOT NULL DEFAULT 'CASH',
    amount_paid NUMERIC(14, 2) NOT NULL CHECK (amount_paid > 0),
    
    -- Currency denomination breakdown
    notes_500 INTEGER NOT NULL DEFAULT 0 CHECK (notes_500 >= 0),
    notes_200 INTEGER NOT NULL DEFAULT 0 CHECK (notes_200 >= 0),
    notes_100 INTEGER NOT NULL DEFAULT 0 CHECK (notes_100 >= 0),
    notes_50 INTEGER NOT NULL DEFAULT 0 CHECK (notes_50 >= 0),
    notes_20 INTEGER NOT NULL DEFAULT 0 CHECK (notes_20 >= 0),
    notes_10 INTEGER NOT NULL DEFAULT 0 CHECK (notes_10 >= 0),
    coins INTEGER NOT NULL DEFAULT 0 CHECK (coins >= 0),
    
    bank_utr_no TEXT,
    cashier_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Branch Daily Cash Drawer Float Reconciliation
CREATE TABLE IF NOT EXISTS branch_daily_cash_drawers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE RESTRICT,
    record_date DATE NOT NULL DEFAULT CURRENT_DATE,
    opening_float NUMERIC(14, 2) NOT NULL CHECK (opening_float >= 0),
    total_cash_payouts NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    petty_expenses_cash NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    bank_withdrawals_inward NUMERIC(14, 2) NOT NULL DEFAULT 0.00,
    calculated_closing_cash NUMERIC(14, 2) NOT NULL,
    physical_counted_cash NUMERIC(14, 2) NOT NULL,
    closed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    closed_at TIMESTAMPTZ,
    CONSTRAINT uq_branch_daily_drawer UNIQUE (branch_id, record_date)
);

-- ------------------------------------------------------------------------------
-- 6. OUTWARD ORDERS & GENERAL LEDGER
-- ------------------------------------------------------------------------------

-- Outward Sales Orders (Dispatched to grain processors / mills / buyers)
CREATE TABLE IF NOT EXISTS outward_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE RESTRICT,
    challan_number TEXT UNIQUE NOT NULL,
    order_date DATE NOT NULL DEFAULT CURRENT_DATE,
    buyer_name TEXT NOT NULL,
    commodity_name TEXT NOT NULL,
    vehicle_number TEXT,
    net_weight_kg NUMERIC(12, 2) NOT NULL CHECK (net_weight_kg > 0),
    net_quintals NUMERIC(12, 4) NOT NULL CHECK (net_quintals > 0),
    rate_per_quintal NUMERIC(10, 2) NOT NULL CHECK (rate_per_quintal > 0),
    hamali_per_100kg NUMERIC(10, 2) NOT NULL DEFAULT 25.00,
    hamali_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    gross_amount NUMERIC(14, 2) NOT NULL CHECK (gross_amount >= 0),
    total_bill_amount NUMERIC(14, 2) NOT NULL CHECK (total_bill_amount >= 0),
    status TEXT NOT NULL DEFAULT 'DISPATCHED',
    cashier_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    payment_status TEXT NOT NULL DEFAULT 'PENDING',
    payment_mode TEXT,
    utr_number TEXT,
    payment_branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    payment_received_date DATE,
    payment_received_by TEXT,
    payment_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Double-Entry Accounting Ledger Entries
CREATE TABLE IF NOT EXISTS ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE RESTRICT,
    transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    voucher_type TEXT NOT NULL,
    voucher_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    party_id UUID REFERENCES parties(id) ON DELETE SET NULL,
    debit_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00 CHECK (debit_amount >= 0),
    credit_amount NUMERIC(14, 2) NOT NULL DEFAULT 0.00 CHECK (credit_amount >= 0),
    narration TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- ------------------------------------------------------------------------------
-- 7. AI QUALITY ASSAYING & CAPTAIN TABLET APP
-- ------------------------------------------------------------------------------

-- Quality Inspections (ArUco calibration, 8-factor vision, 7-segment moisture OCR)
CREATE TABLE IF NOT EXISTS quality_inspections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_no TEXT UNIQUE NOT NULL,
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE RESTRICT,
    inspector_id UUID REFERENCES inspectors(id) ON DELETE SET NULL,
    inspector_name TEXT,
    vehicle_no TEXT NOT NULL,
    farmer_name TEXT NOT NULL,
    farmer_phone TEXT,
    commodity_id UUID REFERENCES commodities(id) ON DELETE SET NULL,
    commodity_name TEXT NOT NULL,
    
    -- Primary physical metrics
    moisture_pct NUMERIC(5, 2) NOT NULL CHECK (moisture_pct >= 0),
    moisture_cut_kg NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    karda_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    
    -- 8-factor computer vision analysis
    damaged_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    green_seeds_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    broken_split_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    shriveled_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    uniformity_index NUMERIC(5, 2) NOT NULL DEFAULT 95.00,
    
    -- Varietal purity & Admixture
    dominant_breed TEXT,
    breed_purity_pct NUMERIC(5, 2) NOT NULL DEFAULT 100.00,
    admixture_pct NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    breed_status TEXT NOT NULL DEFAULT 'PURE_BREED',
    
    -- Recommended grading and pricing
    faq_grade TEXT NOT NULL DEFAULT 'FAQ_GRADE_1',
    grade_label TEXT NOT NULL DEFAULT 'Grade 1 (Premium FAQ)',
    suggested_rate_cut_per_qtl NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    corridor_min_rate NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    corridor_target_rate NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    corridor_max_rate NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    suggested_buying_rate_per_qtl NUMERIC(10, 2) NOT NULL DEFAULT 0.00,
    
    -- Sample details & photo evidence (Stored in Supabase Storage)
    sample_weight_grams NUMERIC(8, 2) NOT NULL DEFAULT 250.00,
    total_seeds_analyzed INTEGER NOT NULL DEFAULT 500,
    meter_photo_url TEXT,
    grain_photo_url TEXT,
    photo_url TEXT,
    inspector_signature TEXT,
    
    -- Lifecycle state and linkage to Purchase Invoice
    status qc_status_t NOT NULL DEFAULT 'PENDING',
    invoice_id UUID REFERENCES purchase_invoices(id) ON DELETE SET NULL,
    inspection_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- ------------------------------------------------------------------------------
-- 8. AUDIT LOGS, SYSTEM SETTINGS & USER SESSIONS
-- ------------------------------------------------------------------------------

-- Forensic Audit Change Log (JSONB structured state diffs)
CREATE TABLE IF NOT EXISTS audit_change_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    entity_name TEXT,
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    changed_by TEXT NOT NULL DEFAULT 'system',
    action TEXT NOT NULL,
    old_values JSONB,
    new_values JSONB,
    change_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Distributed System Settings (Global and Per-Branch overrides)
CREATE TABLE IF NOT EXISTS system_settings (
    scope TEXT NOT NULL,
    scope_id TEXT NOT NULL DEFAULT 'GLOBAL',
    setting_key TEXT NOT NULL,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (scope, scope_id, setting_key)
);

-- User Sessions (Stateful tracking with revocation)
CREATE TABLE IF NOT EXISTS user_sessions (
    session_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    username TEXT NOT NULL,
    role user_role_t NOT NULL,
    branch_id UUID REFERENCES branches(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE
);

-- ------------------------------------------------------------------------------
-- 9. PERFORMANCE INDEXES
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_users_branch ON users(branch_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

CREATE INDEX IF NOT EXISTS idx_rates_branch_date ON daily_commodity_rates(branch_id, rate_date);
CREATE INDEX IF NOT EXISTS idx_rates_commodity ON daily_commodity_rates(commodity_name, rate_date);

CREATE INDEX IF NOT EXISTS idx_parties_branch ON parties(home_branch_id);
CREATE INDEX IF NOT EXISTS idx_parties_phone ON parties(phone);
CREATE INDEX IF NOT EXISTS idx_parties_pan ON parties(pan_number);

CREATE INDEX IF NOT EXISTS idx_invoices_branch ON purchase_invoices(branch_id);
CREATE INDEX IF NOT EXISTS idx_invoices_party ON purchase_invoices(party_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON purchase_invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_payout_status ON purchase_invoices(payout_status);
CREATE INDEX IF NOT EXISTS idx_invoices_qc_ticket ON purchase_invoices(qc_ticket_no);

CREATE INDEX IF NOT EXISTS idx_payouts_branch ON cashier_payouts(branch_id);
CREATE INDEX IF NOT EXISTS idx_payouts_invoice ON cashier_payouts(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payouts_party_mode_date ON cashier_payouts(party_id, payout_mode, created_at);

CREATE INDEX IF NOT EXISTS idx_qc_branch ON quality_inspections(branch_id);
CREATE INDEX IF NOT EXISTS idx_qc_status ON quality_inspections(status);
CREATE INDEX IF NOT EXISTS idx_qc_vehicle ON quality_inspections(vehicle_no);
CREATE INDEX IF NOT EXISTS idx_qc_invoice ON quality_inspections(invoice_id);

CREATE INDEX IF NOT EXISTS idx_outward_branch ON outward_orders(branch_id);
CREATE INDEX IF NOT EXISTS idx_outward_date ON outward_orders(order_date);

CREATE INDEX IF NOT EXISTS idx_ledger_branch ON ledger_entries(branch_id);
CREATE INDEX IF NOT EXISTS idx_ledger_party ON ledger_entries(party_id);
CREATE INDEX IF NOT EXISTS idx_ledger_voucher ON ledger_entries(voucher_type, voucher_id);

CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_change_logs(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);

-- ------------------------------------------------------------------------------
-- 10. STATUTORY COMPLIANCE & BUSINESS INTEGRITY TRIGGERS
-- ------------------------------------------------------------------------------

-- TRIGGER 1: Statutory Section 269ST Income Tax Compliance
-- Prohibits:
-- 1. Any single CASH disbursement >= Rs. 2,00,000.
-- 2. Aggregate CASH disbursement to the same recipient across all branches on the same calendar day >= Rs. 2,00,000.
CREATE OR REPLACE FUNCTION fn_enforce_section_269st_cash_limit()
RETURNS TRIGGER AS $$
DECLARE
    v_daily_cash_aggregate NUMERIC(14, 2);
    v_party_name TEXT;
BEGIN
    IF NEW.payout_mode = 'CASH' THEN
        -- Condition 1: Single payout limit
        IF NEW.amount_paid >= 200000.00 THEN
            RAISE EXCEPTION 'Section 269ST Statutory Violation: Single cash payment of Rs. % exceeds statutory ceiling of Rs. 1,99,999. Mandatory settlement via BANK_TRANSFER / RTGS.',
                NEW.amount_paid
                USING ERRCODE = 'check_violation';
        END IF;

        -- Condition 2: Aggregate daily cash payout per party across all branches
        SELECT COALESCE(SUM(amount_paid), 0.00)
        INTO v_daily_cash_aggregate
        FROM cashier_payouts
        WHERE party_id = NEW.party_id
          AND payout_mode = 'CASH'
          AND DATE(created_at AT TIME ZONE 'Asia/Kolkata') = CURRENT_DATE
          AND id <> COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000'::uuid);

        IF (v_daily_cash_aggregate + NEW.amount_paid) >= 200000.00 THEN
            SELECT name INTO v_party_name FROM parties WHERE id = NEW.party_id;
            RAISE EXCEPTION 'Section 269ST Statutory Violation: Recipient "%" has already received Rs. % in cash today across APMC yards. Additional cash payment of Rs. % breaches the Rs. 2,00,000 daily threshold.',
                v_party_name, v_daily_cash_aggregate, NEW.amount_paid
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_section_269st ON cashier_payouts;
CREATE TRIGGER trg_enforce_section_269st
    BEFORE INSERT OR UPDATE ON cashier_payouts
    FOR EACH ROW
    EXECUTE FUNCTION fn_enforce_section_269st_cash_limit();

-- TRIGGER 2: Mandatory Zero Mandi Cess Enforcement
CREATE OR REPLACE FUNCTION fn_enforce_zero_mandi_cess()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.mandi_cess_amount <> 0.00 THEN
        RAISE EXCEPTION 'Statutory Zero Mandi Cess Invariant: Mandi cess amount must strictly be 0.00 (Attempted: Rs. %).',
            NEW.mandi_cess_amount
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_zero_mandi_cess ON purchase_invoices;
CREATE TRIGGER trg_enforce_zero_mandi_cess
    BEFORE INSERT OR UPDATE ON purchase_invoices
    FOR EACH ROW
    EXECUTE FUNCTION fn_enforce_zero_mandi_cess();

-- TRIGGER 3: Automatic QC Ticket Lifecycle Linkage
CREATE OR REPLACE FUNCTION fn_link_qc_inspection_to_invoice()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.qc_ticket_no IS NOT NULL AND NEW.qc_ticket_no <> '' THEN
        UPDATE quality_inspections
        SET status = 'INVOICED',
            invoice_id = NEW.id,
            updated_at = clock_timestamp()
        WHERE ticket_no = NEW.qc_ticket_no
          AND status IN ('PENDING', 'ACCEPTED');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_link_qc_inspection ON purchase_invoices;
CREATE TRIGGER trg_link_qc_inspection
    AFTER INSERT ON purchase_invoices
    FOR EACH ROW
    EXECUTE FUNCTION fn_link_qc_inspection_to_invoice();

-- ------------------------------------------------------------------------------
-- 11. SUPABASE REALTIME CDC PUBLICATION
-- ------------------------------------------------------------------------------
-- Publish critical operational tables for instant WebSocket broadcasting to:
-- 1. Munim Desks (Instant weighbridge slip alerts)
-- 2. Cashier Windows (Live payout queue notifications)
-- 3. Captain Tablets (Rate corridor updates & ticket status changes)
-- ------------------------------------------------------------------------------
ALTER PUBLICATION supabase_realtime ADD TABLE 
    purchase_invoices, 
    quality_inspections, 
    daily_commodity_rates, 
    cashier_payouts;

-- Set replica identity to FULL so realtime events transmit complete before/after records
ALTER TABLE purchase_invoices REPLICA IDENTITY FULL;
ALTER TABLE quality_inspections REPLICA IDENTITY FULL;
ALTER TABLE daily_commodity_rates REPLICA IDENTITY FULL;
ALTER TABLE cashier_payouts REPLICA IDENTITY FULL;

-- ------------------------------------------------------------------------------
-- 12. ROW LEVEL SECURITY (RLS) POLICIES
-- ------------------------------------------------------------------------------
-- Multi-Tenant APMC Yard Isolation & Role-Based Access Control

-- Enable RLS on all operational and financial tables
ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE commodities ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_commodity_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE parties ENABLE ROW LEVEL SECURITY;
ALTER TABLE inspectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchase_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE cashier_payouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE branch_daily_cash_drawers ENABLE ROW LEVEL SECURITY;
ALTER TABLE outward_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE ledger_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality_inspections ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_change_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;

-- Helper Functions to read authenticated JWT claims
CREATE OR REPLACE FUNCTION auth_user_role()
RETURNS TEXT AS $$
    SELECT COALESCE(
        current_setting('request.jwt.claims', true)::jsonb -> 'app_metadata' ->> 'role',
        current_setting('request.jwt.claims', true)::jsonb ->> 'role',
        'ANONYMOUS'
    );
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION auth_user_branch_id()
RETURNS UUID AS $$
    SELECT NULLIF(
        COALESCE(
            current_setting('request.jwt.claims', true)::jsonb -> 'app_metadata' ->> 'branch_id',
            current_setting('request.jwt.claims', true)::jsonb ->> 'branch_id'
        ),
        ''
    )::uuid;
$$ LANGUAGE sql STABLE;

-- RLS: branches (Everyone authenticated can read active branches; admins can manage)
CREATE POLICY "Allow authenticated users to view active branches"
    ON branches FOR SELECT
    TO authenticated
    USING (is_active = TRUE OR auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ'));

CREATE POLICY "Allow super admin to modify branches"
    ON branches FOR ALL
    TO authenticated
    USING (auth_user_role() = 'SUPER_ADMIN')
    WITH CHECK (auth_user_role() = 'SUPER_ADMIN');

-- RLS: commodities (Publicly readable; manageable by HQ)
CREATE POLICY "Allow all authenticated users to read commodities"
    ON commodities FOR SELECT
    TO authenticated
    USING (TRUE);

CREATE POLICY "Allow HQ roles to manage commodities"
    ON commodities FOR ALL
    TO authenticated
    USING (auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ'))
    WITH CHECK (auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ'));

-- RLS: daily_commodity_rates
CREATE POLICY "Users can view daily rates for their branch or all branches if HQ"
    ON daily_commodity_rates FOR SELECT
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR branch_id = auth_user_branch_id()
    );

CREATE POLICY "Munims and Admins can update daily rates"
    ON daily_commodity_rates FOR ALL
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR (auth_user_role() = 'BRANCH_MUNIM' AND branch_id = auth_user_branch_id())
    )
    WITH CHECK (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR (auth_user_role() = 'BRANCH_MUNIM' AND branch_id = auth_user_branch_id())
    );

-- RLS: purchase_invoices
CREATE POLICY "Users view invoices of their own branch or all if HQ"
    ON purchase_invoices FOR SELECT
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR branch_id = auth_user_branch_id()
    );

CREATE POLICY "Munims and Admins can create and edit invoices"
    ON purchase_invoices FOR ALL
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR (auth_user_role() = 'BRANCH_MUNIM' AND branch_id = auth_user_branch_id())
    )
    WITH CHECK (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR (auth_user_role() = 'BRANCH_MUNIM' AND branch_id = auth_user_branch_id())
    );

-- RLS: cashier_payouts
CREATE POLICY "Users view payouts for their branch or HQ"
    ON cashier_payouts FOR SELECT
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR branch_id = auth_user_branch_id()
    );

CREATE POLICY "Cashiers and Admins can insert payouts"
    ON cashier_payouts FOR INSERT
    TO authenticated
    WITH CHECK (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR (auth_user_role() = 'BRANCH_CASHIER' AND branch_id = auth_user_branch_id())
    );

-- RLS: quality_inspections
CREATE POLICY "Inspectors and Yard staff view inspections for their branch or HQ"
    ON quality_inspections FOR SELECT
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR branch_id = auth_user_branch_id()
    );

CREATE POLICY "Inspectors and Munims create and update quality inspections"
    ON quality_inspections FOR ALL
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR (auth_user_role() IN ('QUALITY_INSPECTOR', 'BRANCH_MUNIM') AND branch_id = auth_user_branch_id())
    )
    WITH CHECK (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR (auth_user_role() IN ('QUALITY_INSPECTOR', 'BRANCH_MUNIM') AND branch_id = auth_user_branch_id())
    );

-- RLS: parties
CREATE POLICY "All authenticated users can search parties"
    ON parties FOR SELECT
    TO authenticated
    USING (TRUE);

CREATE POLICY "Staff can insert or update parties"
    ON parties FOR ALL
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ', 'BRANCH_MUNIM', 'BRANCH_CASHIER')
    )
    WITH CHECK (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ', 'BRANCH_MUNIM', 'BRANCH_CASHIER')
    );

-- RLS: ledger_entries & outward_orders
CREATE POLICY "Branch staff and HQ view branch ledger"
    ON ledger_entries FOR SELECT
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR branch_id = auth_user_branch_id()
    );

CREATE POLICY "Branch staff and HQ view outward orders"
    ON outward_orders FOR SELECT
    TO authenticated
    USING (
        auth_user_role() IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ')
        OR branch_id = auth_user_branch_id()
    );

-- ------------------------------------------------------------------------------
-- 13. SUPABASE STORAGE BUCKETS (SLIPS & GRAIN ASSAYING PHOTOS)
-- ------------------------------------------------------------------------------
-- Note: Insert storage buckets if storage schema is available in Supabase
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES 
    ('mandi-slips', 'mandi-slips', FALSE, 10485760, ARRAY['image/jpeg', 'image/png', 'image/webp', 'application/pdf']),
    ('grain-photos', 'grain-photos', FALSE, 26214400, ARRAY['image/jpeg', 'image/png', 'image/webp'])
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: Authorized staff can view and upload slips
CREATE POLICY "Allow authenticated staff to upload mandi slips"
    ON storage.objects FOR INSERT
    TO authenticated
    WITH CHECK (bucket_id IN ('mandi-slips', 'grain-photos'));

CREATE POLICY "Allow staff to read mandi slips and grain photos"
    ON storage.objects FOR SELECT
    TO authenticated
    USING (bucket_id IN ('mandi-slips', 'grain-photos'));

-- ==============================================================================
-- END OF SUPABASE SCHEMA SPECIFICATION
-- ==============================================================================
