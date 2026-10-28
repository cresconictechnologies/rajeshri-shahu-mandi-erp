-- ==========================================================================
-- Rajeshri Shahu Trading — Mandi ERP Cloud Database Schema for Supabase
-- Target: PostgreSQL 15+ (100% Compatible with Free Supabase Tier)
-- ==========================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


CREATE TABLE IF NOT EXISTS branches (
    id TEXT PRIMARY KEY,
    branch_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    mandi_license_no TEXT,
    address TEXT,
    phone TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    branch_id TEXT REFERENCES branches(id),
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    role TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS commodities (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    hsn_code TEXT NOT NULL,
    standard_moisture_pct DOUBLE PRECISION DEFAULT 10.0,
    mandi_cess_pct DOUBLE PRECISION DEFAULT 1.5,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS daily_commodity_rates (
    id TEXT PRIMARY KEY,
    rate_date DATE NOT NULL,
    branch_id TEXT REFERENCES branches(id),
    commodity_name TEXT NOT NULL,
    quality_grade TEXT DEFAULT 'STANDARD',
    min_rate_per_qtl DOUBLE PRECISION NOT NULL,
    target_rate_per_qtl DOUBLE PRECISION NOT NULL,
    max_rate_per_qtl DOUBLE PRECISION NOT NULL,
    set_by_user_id TEXT REFERENCES users(id),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rate_date, branch_id, commodity_name, quality_grade)
);


CREATE TABLE IF NOT EXISTS parties (
    id TEXT PRIMARY KEY,
    home_branch_id TEXT REFERENCES branches(id),
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    party_type TEXT NOT NULL,
    village TEXT,
    pan_number TEXT,
    aadhaar_number TEXT,
    gstin TEXT,
    khasra_record_no TEXT,
    bank_name TEXT,
    bank_account_no TEXT,
    bank_ifsc TEXT,
    current_advance DOUBLE PRECISION DEFAULT 0.0,
    advance_interest_rate DOUBLE PRECISION DEFAULT 12.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS inspectors (
    id TEXT PRIMARY KEY,
    branch_id TEXT REFERENCES branches(id),
    name TEXT NOT NULL,
    designation TEXT DEFAULT 'Assayer / Sampler',
    phone TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS purchase_invoices (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id),
    token_number TEXT UNIQUE NOT NULL,
    invoice_date DATE NOT NULL,
    party_id TEXT NOT NULL REFERENCES parties(id),
    commodity_name TEXT NOT NULL,
    hsn_code TEXT NOT NULL,
    quality_grade TEXT DEFAULT 'STANDARD',
    vehicle_number TEXT,
    weighment_mode TEXT DEFAULT 'MANUAL_YARD',
    external_kanta_name TEXT,
    external_slip_number TEXT,
    slip_photo_url TEXT,
    bag_count INTEGER NOT NULL DEFAULT 0,
    bag_type TEXT NOT NULL,
    gross_weight_kg DOUBLE PRECISION NOT NULL,
    vehicle_tare_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    bag_tare_kg DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    moisture_percentage DOUBLE PRECISION DEFAULT 10.0,
    moisture_cut_kg DOUBLE PRECISION DEFAULT 0.0,
    karda_percentage DOUBLE PRECISION DEFAULT 0.0,
    karda_cut_kg DOUBLE PRECISION DEFAULT 0.0,
    net_weight_kg DOUBLE PRECISION NOT NULL,
    net_quintals DOUBLE PRECISION NOT NULL,
    rate_per_quintal DOUBLE PRECISION NOT NULL,
    is_rate_overridden INTEGER DEFAULT 0,
    rate_override_by TEXT,
    rate_override_reason TEXT,
    rate_override_status TEXT DEFAULT 'NONE',
    gross_amount DOUBLE PRECISION NOT NULL,
    hamali_charge DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    tulai_charge DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    silai_charge DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    bardana_deduction DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    mandi_cess_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    advance_adjusted DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    interest_adjusted DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    gst_rate DOUBLE PRECISION DEFAULT 0.0,
    gst_amount DOUBLE PRECISION DEFAULT 0.0,
    tds_194q_amount DOUBLE PRECISION DEFAULT 0.0,
    net_payable_amount DOUBLE PRECISION NOT NULL,
    rounded_net_payable DOUBLE PRECISION,
    round_off_amount DOUBLE PRECISION DEFAULT 0.0,
    payout_status TEXT DEFAULT 'PENDING',
    created_by_user_id TEXT REFERENCES users(id),
    inspector_name TEXT,
    rtgs_bank_name TEXT,
    rtgs_account_no TEXT,
    rtgs_ifsc_code TEXT,
    rtgs_beneficiary_name TEXT,
    rtgs_utr_no TEXT,
    rtgs_requested_at TEXT,
    rtgs_completed_at TEXT,
    rtgs_completed_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS cashier_payouts (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id),
    invoice_id TEXT NOT NULL REFERENCES purchase_invoices(id),
    party_id TEXT NOT NULL REFERENCES parties(id),
    payout_mode TEXT,
    amount_paid DOUBLE PRECISION NOT NULL,
    notes_500 INTEGER DEFAULT 0,
    notes_200 INTEGER DEFAULT 0,
    notes_100 INTEGER DEFAULT 0,
    notes_50 INTEGER DEFAULT 0,
    notes_20 INTEGER DEFAULT 0,
    notes_10 INTEGER DEFAULT 0,
    coins INTEGER DEFAULT 0,
    bank_utr_no TEXT,
    cashier_user_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS branch_daily_cash_drawers (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id),
    record_date DATE NOT NULL,
    opening_float DOUBLE PRECISION NOT NULL,
    total_cash_payouts DOUBLE PRECISION DEFAULT 0.0,
    petty_expenses_cash DOUBLE PRECISION DEFAULT 0.0,
    bank_withdrawals_inward DOUBLE PRECISION DEFAULT 0.0,
    calculated_closing_cash DOUBLE PRECISION NOT NULL,
    physical_counted_cash DOUBLE PRECISION NOT NULL,
    closed_by_user_id TEXT REFERENCES users(id),
    closed_at TEXT,
    UNIQUE(branch_id, record_date)
);


CREATE TABLE IF NOT EXISTS ledger_entries (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id),
    transaction_date DATE NOT NULL,
    voucher_type TEXT NOT NULL,
    voucher_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    party_id TEXT REFERENCES parties(id),
    debit_amount DOUBLE PRECISION DEFAULT 0.0,
    credit_amount DOUBLE PRECISION DEFAULT 0.0,
    narration TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS outward_orders (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id),
    challan_number TEXT UNIQUE NOT NULL,
    order_date DATE NOT NULL,
    buyer_name TEXT NOT NULL,
    commodity_name TEXT NOT NULL,
    vehicle_number TEXT,
    net_weight_kg DOUBLE PRECISION NOT NULL,
    net_quintals DOUBLE PRECISION NOT NULL,
    rate_per_quintal DOUBLE PRECISION NOT NULL,
    hamali_per_100kg DOUBLE PRECISION NOT NULL DEFAULT 25.0,
    hamali_amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    gross_amount DOUBLE PRECISION NOT NULL,
    total_bill_amount DOUBLE PRECISION NOT NULL,
    status TEXT DEFAULT 'DISPATCHED',
    cashier_user_id TEXT,
    payment_status TEXT DEFAULT 'PENDING',
    payment_mode TEXT,
    utr_number TEXT,
    payment_branch_id TEXT REFERENCES branches(id),
    payment_received_date TEXT,
    payment_received_by TEXT,
    payment_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS audit_change_logs (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    entity_name TEXT,
    branch_id TEXT,
    changed_by TEXT DEFAULT 'cashier',
    action TEXT NOT NULL,
    old_values_json TEXT,
    new_values_json TEXT,
    change_summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS system_settings (
    scope TEXT NOT NULL,
    scope_id TEXT NOT NULL DEFAULT 'GLOBAL',
    setting_key TEXT NOT NULL,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (scope, scope_id, setting_key)
);


-- Initial seed data for branches
INSERT INTO branches (id, branch_code, name, mandi_license_no, address, phone, is_active, created_at) VALUES ('br-chikhali', 'BR-CHK', 'Chikhali Branch', 'MH/CHK/APMC-101', 'APMC Market Yard, Chikhali (Buldhana)', '07264-242110', 1, '2026-10-28 06:55:31') ON CONFLICT DO NOTHING;
INSERT INTO branches (id, branch_code, name, mandi_license_no, address, phone, is_active, created_at) VALUES ('br-varvand', 'BR-VRV', 'Varvand Branch', 'MH/VRV/APMC-202', 'Station Road, Varvand (Pune)', '02119-251220', 1, '2026-10-28 06:55:31') ON CONFLICT DO NOTHING;
INSERT INTO branches (id, branch_code, name, mandi_license_no, address, phone, is_active, created_at) VALUES ('br-dhad', 'BR-DHD', 'Dhad Branch', 'MH/DHD/APMC-303', 'Main Market Yard, Dhad (Buldhana)', '07267-233330', 1, '2026-10-28 06:55:31') ON CONFLICT DO NOTHING;

-- Initial seed data for commodities
INSERT INTO commodities (id, name, hsn_code, standard_moisture_pct, mandi_cess_pct, is_active, created_at) VALUES ('c-soya', 'Soyabean (Yellow)', '1201', 10.0, 1.5, 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;
INSERT INTO commodities (id, name, hsn_code, standard_moisture_pct, mandi_cess_pct, is_active, created_at) VALUES ('c-wheat', 'Wheat (Lokwan)', '1001', 10.0, 1.5, 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;
INSERT INTO commodities (id, name, hsn_code, standard_moisture_pct, mandi_cess_pct, is_active, created_at) VALUES ('c-chana', 'Chana (Desi)', '0713', 10.0, 1.5, 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;
INSERT INTO commodities (id, name, hsn_code, standard_moisture_pct, mandi_cess_pct, is_active, created_at) VALUES ('c-mustard', 'Mustard (Rayda)', '1207', 8.0, 1.5, 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;
INSERT INTO commodities (id, name, hsn_code, standard_moisture_pct, mandi_cess_pct, is_active, created_at) VALUES ('c-maize', 'Maize (Makka)', '1005', 12.0, 1.5, 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;

-- Initial seed data for inspectors
INSERT INTO inspectors (id, branch_id, name, designation, phone, is_active, created_at) VALUES ('ins-1', NULL, 'Mahesh Patidar', 'Chief Assayer & Quality Lead', '9826011111', 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;
INSERT INTO inspectors (id, branch_id, name, designation, phone, is_active, created_at) VALUES ('ins-2', NULL, 'Suresh Yadav', 'Mandi Certified Inspector', '9826022222', 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;
INSERT INTO inspectors (id, branch_id, name, designation, phone, is_active, created_at) VALUES ('ins-3', 'br-chikhali', 'Babulal Meena', 'Indore Yard Sampler', '9826033333', 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;
INSERT INTO inspectors (id, branch_id, name, designation, phone, is_active, created_at) VALUES ('ins-4', 'br-varvand', 'Govind Solanki', 'Ujjain Quality Inspector', '9826044444', 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;
INSERT INTO inspectors (id, branch_id, name, designation, phone, is_active, created_at) VALUES ('ins-5', 'br-dhad', 'Narayan Sharma', 'Dewas Assayer', '9826055555', 1, '2026-10-28 11:09:34') ON CONFLICT DO NOTHING;

-- Initial seed data for system_settings
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'org_name', 'Rajeshri Shahu Trading', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'org_pan', 'AACCK1234F', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'org_gstin', '23AACCK1234F1Z5', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'fiscal_year', '2026-2027', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'multi_branch_sync', 'ENABLED', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'audit_retention_days', '365', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('CENTRAL_ACCOUNTS', 'GLOBAL', 'sec_269st_cash_limit', '199999', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('CENTRAL_ACCOUNTS', 'GLOBAL', 'sec_40a3_cash_limit', '10000', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('CENTRAL_ACCOUNTS', 'GLOBAL', 'corridor_tolerance_pct', '6.5', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('CENTRAL_ACCOUNTS', 'GLOBAL', 'rtgs_auto_sms', 'ENABLED', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('CENTRAL_ACCOUNTS', 'GLOBAL', 'default_bank_account', 'State Bank of India (A/C: 40992388112)', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('BRANCH', 'GLOBAL', 'default_weighment_mode', 'MANUAL_YARD', '2026-10-28 14:46:24') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('BRANCH', 'GLOBAL', 'parchi_gate_no', 'Gate No. 2', '2026-10-28 14:46:24') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('BRANCH', 'GLOBAL', 'auto_print_parchi', 'ENABLED', '2026-10-28 14:46:24') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('BRANCH', 'GLOBAL', 'cash_drawer_warning_limit', '50000', '2026-10-28 14:46:24') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('BRANCH', 'br-chikhali', 'default_weighment_mode', 'MANUAL_YARD', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('BRANCH', 'br-chikhali', 'parchi_gate_no', 'Gate No. 3', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('BRANCH', 'br-chikhali', 'auto_print_parchi', 'ENABLED', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('BRANCH', 'br-chikhali', 'cash_drawer_warning_limit', '60000', '2026-10-28 18:33:27') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'license_status', 'Active (Pro Tier - 3 Branches)', '2026-10-28 18:20:50') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'license_valid_until', '31-March-2027', '2026-10-28 18:20:50') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'license_key', 'RST-PRO-2026-MH3B-89A12F', '2026-10-28 18:20:50') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'license_tier', 'Pro Tier (3 Branches: Chikhali, Varvand, Dhad)', '2026-10-28 18:20:50') ON CONFLICT DO NOTHING;
INSERT INTO system_settings (scope, scope_id, setting_key, setting_value, updated_at) VALUES ('SUPER_ADMIN', 'GLOBAL', 'license_branch_limit', '3', '2026-10-28 18:20:50') ON CONFLICT DO NOTHING;