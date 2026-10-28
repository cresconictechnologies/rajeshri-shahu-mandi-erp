-- ============================================================================
-- COMMODITY TRADING & MANDI PROCUREMENT ERP - DATABASE SCHEMA BLUEPRINT
-- Dialect: ANSI SQL / PostgreSQL & SQLite WAL Compatible
-- ============================================================================

-- 1. Branches / Purchasing Centers Master
CREATE TABLE IF NOT EXISTS branches (
    id VARCHAR(36) PRIMARY KEY,
    branch_code VARCHAR(10) UNIQUE NOT NULL, -- e.g., 'BR-IND', 'BR-UJN', 'BR-DWS'
    name VARCHAR(100) NOT NULL,
    mandi_license_no VARCHAR(50),
    address TEXT,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Users & Role-Based Authentication
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    branch_id VARCHAR(36) REFERENCES branches(id), -- NULL for Super Admin / Accounts HQ
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ', 'BRANCH_MUNIM', 'BRANCH_CASHIER')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Daily Commodity Price Master (Min/Max Rate Corridor set by Accounts HQ)
CREATE TABLE IF NOT EXISTS daily_commodity_rates (
    id VARCHAR(36) PRIMARY KEY,
    rate_date DATE NOT NULL,
    branch_id VARCHAR(36) REFERENCES branches(id), -- NULL applies to all branches
    commodity_name VARCHAR(100) NOT NULL,
    quality_grade VARCHAR(20) DEFAULT 'STANDARD',
    min_rate_per_qtl DECIMAL(10, 2) NOT NULL,
    target_rate_per_qtl DECIMAL(10, 2) NOT NULL,
    max_rate_per_qtl DECIMAL(10, 2) NOT NULL,
    set_by_user_id VARCHAR(36) REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rate_date, branch_id, commodity_name, quality_grade)
);

-- 4. Parties Master (Separating Farmers vs Stockers per Branch)
CREATE TABLE IF NOT EXISTS parties (
    id VARCHAR(36) PRIMARY KEY,
    home_branch_id VARCHAR(36) REFERENCES branches(id),
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    party_type VARCHAR(20) NOT NULL CHECK (party_type IN ('FARMER', 'STOCKER', 'BUYER')),
    village VARCHAR(100),
    pan_number VARCHAR(10),
    aadhaar_number VARCHAR(12),
    gstin VARCHAR(15),
    khasra_record_no VARCHAR(50), -- Farmer cultivator land proof for Rule 6DD audit
    bank_name VARCHAR(100),
    bank_account_no VARCHAR(30),
    bank_ifsc VARCHAR(15),
    current_advance DECIMAL(12, 2) DEFAULT 0.00,
    advance_interest_rate DECIMAL(5, 2) DEFAULT 12.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Inward Commodity Lots & Purchase Invoices (Supporting Manual Kanta Entry)
CREATE TABLE IF NOT EXISTS purchase_invoices (
    id VARCHAR(36) PRIMARY KEY,
    branch_id VARCHAR(36) NOT NULL REFERENCES branches(id),
    token_number VARCHAR(30) UNIQUE NOT NULL, -- e.g., 'IND-20261028-001'
    invoice_date DATE NOT NULL,
    party_id VARCHAR(36) NOT NULL REFERENCES parties(id),
    commodity_name VARCHAR(100) NOT NULL,
    hsn_code VARCHAR(10) NOT NULL,
    quality_grade VARCHAR(20) DEFAULT 'STANDARD',
    vehicle_number VARCHAR(50),
    
    -- Weighbridge Parameters (Supports 3rd-Party External Dharamkanta)
    weighment_mode VARCHAR(20) DEFAULT 'MANUAL_EXTERNAL' CHECK (weighment_mode IN ('MANUAL_EXTERNAL', 'DIGITAL_SCALE')),
    external_kanta_name VARCHAR(100), -- e.g., 'Shree Ram Dharamkanta'
    external_slip_number VARCHAR(50),  -- e.g., 'SRK-4912'
    slip_photo_url TEXT,
    
    bag_count INT NOT NULL,
    bag_type VARCHAR(20) CHECK (bag_type IN ('HDPE_50KG', 'JUTE_100KG', 'LOOSE')),
    gross_weight_kg DECIMAL(10, 2) NOT NULL,
    vehicle_tare_kg DECIMAL(10, 2) NOT NULL,
    bag_tare_kg DECIMAL(10, 2) NOT NULL,
    
    -- Quality Deductions (Nami & Karda)
    moisture_percentage DECIMAL(4, 2) DEFAULT 0.00,
    moisture_cut_kg DECIMAL(10, 2) DEFAULT 0.00,
    karda_percentage DECIMAL(4, 2) DEFAULT 0.00,
    karda_cut_kg DECIMAL(10, 2) DEFAULT 0.00,
    net_weight_kg DECIMAL(10, 2) NOT NULL,
    net_quintals DECIMAL(10, 4) NOT NULL,
    
    -- Pricing & HQ Governance
    rate_per_quintal DECIMAL(10, 2) NOT NULL,
    is_rate_overridden BOOLEAN DEFAULT FALSE,
    rate_override_by VARCHAR(36) REFERENCES users(id),
    rate_override_reason TEXT,
    
    gross_amount DECIMAL(12, 2) NOT NULL,
    hamali_charge DECIMAL(10, 2) DEFAULT 0.00,
    tulai_charge DECIMAL(10, 2) DEFAULT 0.00,
    silai_charge DECIMAL(10, 2) DEFAULT 0.00,
    bardana_deduction DECIMAL(10, 2) DEFAULT 0.00,
    mandi_cess_amount DECIMAL(10, 2) DEFAULT 0.00,
    advance_adjusted DECIMAL(12, 2) DEFAULT 0.00,
    interest_adjusted DECIMAL(10, 2) DEFAULT 0.00,
    gst_rate DECIMAL(5, 2) DEFAULT 0.00,
    gst_amount DECIMAL(10, 2) DEFAULT 0.00,
    tds_194q_amount DECIMAL(10, 2) DEFAULT 0.00,
    
    net_payable_amount DECIMAL(12, 2) NOT NULL,
    payout_status VARCHAR(20) DEFAULT 'PENDING' CHECK (payout_status IN ('PENDING', 'PAID', 'CANCELLED')),
    created_by_user_id VARCHAR(36) REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Cashier Payouts & Denomination Ledger
CREATE TABLE IF NOT EXISTS cashier_payouts (
    id VARCHAR(36) PRIMARY KEY,
    branch_id VARCHAR(36) NOT NULL REFERENCES branches(id),
    invoice_id VARCHAR(36) NOT NULL REFERENCES purchase_invoices(id),
    party_id VARCHAR(36) NOT NULL REFERENCES parties(id),
    payout_mode VARCHAR(20) CHECK (payout_mode IN ('CASH', 'BANK_TRANSFER', 'UPI', 'CHEQUE')),
    amount_paid DECIMAL(12, 2) NOT NULL,
    
    -- Currency Denominations for Cash Drawer Reconciliations
    notes_500 INT DEFAULT 0,
    notes_200 INT DEFAULT 0,
    notes_100 INT DEFAULT 0,
    notes_50 INT DEFAULT 0,
    notes_20 INT DEFAULT 0,
    notes_10 INT DEFAULT 0,
    coins INT DEFAULT 0,
    
    bank_utr_no VARCHAR(100),
    cashier_user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Daily Branch Cash Drawer Balance (Rojmel / Galla Tally)
CREATE TABLE IF NOT EXISTS branch_daily_cash_drawers (
    id VARCHAR(36) PRIMARY KEY,
    branch_id VARCHAR(36) NOT NULL REFERENCES branches(id),
    record_date DATE NOT NULL,
    opening_float DECIMAL(12, 2) NOT NULL,
    total_cash_payouts DECIMAL(12, 2) DEFAULT 0.00,
    petty_expenses_cash DECIMAL(12, 2) DEFAULT 0.00,
    bank_withdrawals_inward DECIMAL(12, 2) DEFAULT 0.00,
    calculated_closing_cash DECIMAL(12, 2) NOT NULL,
    physical_counted_cash DECIMAL(12, 2) NOT NULL,
    closed_by_user_id VARCHAR(36) REFERENCES users(id),
    closed_at TIMESTAMP,
    UNIQUE(branch_id, record_date)
);

-- 8. General Ledger Entries (Double-Entry Matrix)
CREATE TABLE IF NOT EXISTS ledger_entries (
    id VARCHAR(36) PRIMARY KEY,
    branch_id VARCHAR(36) NOT NULL REFERENCES branches(id),
    transaction_date DATE NOT NULL,
    voucher_type VARCHAR(20) NOT NULL,
    voucher_id VARCHAR(36) NOT NULL,
    account_name VARCHAR(100) NOT NULL,
    party_id VARCHAR(36) REFERENCES parties(id),
    debit_amount DECIMAL(12, 2) DEFAULT 0.00,
    credit_amount DECIMAL(12, 2) DEFAULT 0.00,
    narration TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indices
CREATE INDEX IF NOT EXISTS idx_inv_branch ON purchase_invoices(branch_id);
CREATE INDEX IF NOT EXISTS idx_inv_party ON purchase_invoices(party_id);
CREATE INDEX IF NOT EXISTS idx_led_party ON ledger_entries(party_id);
CREATE INDEX IF NOT EXISTS idx_led_branch ON ledger_entries(branch_id);
CREATE INDEX IF NOT EXISTS idx_rates_daily ON daily_commodity_rates(rate_date, commodity_name);
