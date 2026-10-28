"""
Database module for Mandi / Commodity Trading ERP.
Local-first SQLite with WAL mode, foreign keys, and seed data.
"""

import sqlite3
import os
import hashlib
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "commodity_mandi.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode('utf-8')).hexdigest()

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS branches (
        id TEXT PRIMARY KEY,
        branch_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        mandi_license_no TEXT,
        address TEXT,
        phone TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        branch_id TEXT REFERENCES branches(id),
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('SUPER_ADMIN', 'ACCOUNTANT_HQ', 'BRANCH_MUNIM', 'BRANCH_CASHIER')),
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS daily_commodity_rates (
        id TEXT PRIMARY KEY,
        rate_date TEXT NOT NULL,
        branch_id TEXT REFERENCES branches(id),
        commodity_name TEXT NOT NULL,
        quality_grade TEXT DEFAULT 'STANDARD',
        min_rate_per_qtl REAL NOT NULL,
        target_rate_per_qtl REAL NOT NULL,
        max_rate_per_qtl REAL NOT NULL,
        set_by_user_id TEXT REFERENCES users(id),
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(rate_date, branch_id, commodity_name, quality_grade)
    );

    CREATE TABLE IF NOT EXISTS parties (
        id TEXT PRIMARY KEY,
        home_branch_id TEXT REFERENCES branches(id),
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        party_type TEXT NOT NULL CHECK (party_type IN ('FARMER', 'STOCKER', 'BUYER')),
        village TEXT,
        pan_number TEXT,
        aadhaar_number TEXT,
        gstin TEXT,
        khasra_record_no TEXT,
        bank_name TEXT,
        bank_account_no TEXT,
        bank_ifsc TEXT,
        current_advance REAL DEFAULT 0.0,
        advance_interest_rate REAL DEFAULT 12.0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

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
        
        weighment_mode TEXT DEFAULT 'MANUAL_YARD' CHECK (weighment_mode IN ('MANUAL_EXTERNAL', 'DIGITAL_SCALE', 'MANUAL_YARD', 'WEIGHBRIDGE')),
        external_kanta_name TEXT,
        external_slip_number TEXT,
        slip_photo_url TEXT,
        
        bag_count INTEGER NOT NULL DEFAULT 0,
        bag_type TEXT DEFAULT 'LOOSE',
        gross_weight_kg REAL NOT NULL,
        vehicle_tare_kg REAL NOT NULL DEFAULT 0.0,
        bag_tare_kg REAL NOT NULL DEFAULT 0.0,
        
        moisture_percentage REAL DEFAULT 0.0,
        moisture_cut_kg REAL DEFAULT 0.0,
        karda_percentage REAL DEFAULT 0.0,
        karda_cut_kg REAL DEFAULT 0.0,
        net_weight_kg REAL NOT NULL,
        net_quintals REAL NOT NULL,
        
        rate_per_quintal REAL NOT NULL,
        is_rate_overridden INTEGER DEFAULT 0,
        rate_override_by TEXT REFERENCES users(id),
        rate_override_reason TEXT,
        
        gross_amount REAL NOT NULL,
        hamali_charge REAL DEFAULT 0.0,
        tulai_charge REAL DEFAULT 0.0,
        silai_charge REAL DEFAULT 0.0,
        bardana_deduction REAL DEFAULT 0.0,
        mandi_cess_amount REAL DEFAULT 0.0,
        advance_adjusted REAL DEFAULT 0.0,
        interest_adjusted REAL DEFAULT 0.0,
        gst_rate REAL DEFAULT 0.0,
        gst_amount REAL DEFAULT 0.0,
        tds_194q_amount REAL DEFAULT 0.0,
        
        net_payable_amount REAL NOT NULL,
        payout_status TEXT DEFAULT 'PENDING' CHECK (payout_status IN ('PENDING', 'PAID', 'CANCELLED', 'RTGS_PENDING')),
        created_by_user_id TEXT REFERENCES users(id),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS cashier_payouts (
        id TEXT PRIMARY KEY,
        branch_id TEXT NOT NULL REFERENCES branches(id),
        invoice_id TEXT NOT NULL REFERENCES purchase_invoices(id),
        party_id TEXT NOT NULL REFERENCES parties(id),
        payout_mode TEXT CHECK (payout_mode IN ('CASH', 'BANK_TRANSFER', 'UPI', 'CHEQUE')),
        amount_paid REAL NOT NULL,
        notes_500 INTEGER DEFAULT 0,
        notes_200 INTEGER DEFAULT 0,
        notes_100 INTEGER DEFAULT 0,
        notes_50 INTEGER DEFAULT 0,
        notes_20 INTEGER DEFAULT 0,
        notes_10 INTEGER DEFAULT 0,
        coins INTEGER DEFAULT 0,
        bank_utr_no TEXT,
        cashier_user_id TEXT NOT NULL REFERENCES users(id),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS branch_daily_cash_drawers (
        id TEXT PRIMARY KEY,
        branch_id TEXT NOT NULL REFERENCES branches(id),
        record_date TEXT NOT NULL,
        opening_float REAL NOT NULL,
        total_cash_payouts REAL DEFAULT 0.0,
        petty_expenses_cash REAL DEFAULT 0.0,
        bank_withdrawals_inward REAL DEFAULT 0.0,
        calculated_closing_cash REAL NOT NULL,
        physical_counted_cash REAL NOT NULL,
        closed_by_user_id TEXT REFERENCES users(id),
        closed_at TEXT,
        UNIQUE(branch_id, record_date)
    );

    CREATE TABLE IF NOT EXISTS commodities (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        hsn_code TEXT NOT NULL,
        standard_moisture_pct REAL DEFAULT 10.0,
        mandi_cess_pct REAL DEFAULT 1.5,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS inspectors (
        id TEXT PRIMARY KEY,
        branch_id TEXT REFERENCES branches(id),
        name TEXT NOT NULL,
        designation TEXT DEFAULT 'Assayer / Sampler',
        phone TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ledger_entries (
        id TEXT PRIMARY KEY,
        branch_id TEXT NOT NULL REFERENCES branches(id),
        transaction_date TEXT NOT NULL,
        voucher_type TEXT NOT NULL,
        voucher_id TEXT NOT NULL,
        account_name TEXT NOT NULL,
        party_id TEXT REFERENCES parties(id),
        debit_amount REAL DEFAULT 0.0,
        credit_amount REAL DEFAULT 0.0,
        narration TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS outward_orders (
        id TEXT PRIMARY KEY,
        branch_id TEXT NOT NULL REFERENCES branches(id),
        challan_number TEXT UNIQUE NOT NULL,
        order_date TEXT NOT NULL,
        buyer_name TEXT NOT NULL,
        commodity_name TEXT NOT NULL,
        vehicle_number TEXT,
        net_weight_kg REAL NOT NULL,
        net_quintals REAL NOT NULL,
        rate_per_quintal REAL NOT NULL,
        hamali_per_100kg REAL NOT NULL DEFAULT 25.0,
        hamali_amount REAL NOT NULL DEFAULT 0.0,
        gross_amount REAL NOT NULL,
        total_bill_amount REAL NOT NULL,
        status TEXT DEFAULT 'DISPATCHED',
        cashier_user_id TEXT,
        payment_status TEXT DEFAULT 'PENDING',
        payment_mode TEXT,
        utr_number TEXT,
        payment_branch_id TEXT REFERENCES branches(id),
        payment_received_date TEXT,
        payment_received_by TEXT,
        payment_notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS system_settings (
        scope TEXT NOT NULL,
        scope_id TEXT NOT NULL DEFAULT 'GLOBAL',
        setting_key TEXT NOT NULL,
        setting_value TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (scope, scope_id, setting_key)
    );

    CREATE INDEX IF NOT EXISTS idx_invoice_branch ON purchase_invoices(branch_id);
    CREATE INDEX IF NOT EXISTS idx_invoice_party ON purchase_invoices(party_id);
    CREATE INDEX IF NOT EXISTS idx_ledger_party ON ledger_entries(party_id);
    CREATE INDEX IF NOT EXISTS idx_ledger_branch ON ledger_entries(branch_id);
    CREATE INDEX IF NOT EXISTS idx_rates_date ON daily_commodity_rates(rate_date, commodity_name);
    CREATE INDEX IF NOT EXISTS idx_outward_branch ON outward_orders(branch_id);
    CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_change_logs(entity_type, entity_id);
    CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_change_logs(created_at);
    CREATE INDEX IF NOT EXISTS idx_audit_branch ON audit_change_logs(branch_id);
    """)

    # Safe migrations for columns in outward_orders using PRAGMA inspection
    cur.execute("PRAGMA table_info(outward_orders);")
    existing_outward_cols = {row['name'] for row in cur.fetchall()}
    for col, definition in [
        ("payment_status", "TEXT DEFAULT 'PENDING'"),
        ("payment_mode", "TEXT"),
        ("utr_number", "TEXT"),
        ("payment_branch_id", "TEXT REFERENCES branches(id)"),
        ("payment_received_date", "TEXT"),
        ("payment_received_by", "TEXT"),
        ("payment_notes", "TEXT")
    ]:
        if col not in existing_outward_cols:
            cur.execute(f"ALTER TABLE outward_orders ADD COLUMN {col} {definition}")

    # Safe migrations for columns in purchase_invoices using PRAGMA inspection
    cur.execute("PRAGMA table_info(purchase_invoices);")
    existing_invoice_cols = {row['name'] for row in cur.fetchall()}
    for col, definition in [
        ("inspector_name", "TEXT"),
        ("rate_override_status", "TEXT DEFAULT 'NONE'"),
        ("rounded_net_payable", "REAL"),
        ("round_off_amount", "REAL DEFAULT 0.0"),
        ("rtgs_bank_name", "TEXT"),
        ("rtgs_account_no", "TEXT"),
        ("rtgs_ifsc_code", "TEXT"),
        ("rtgs_beneficiary_name", "TEXT"),
        ("rtgs_utr_no", "TEXT"),
        ("rtgs_requested_at", "TEXT"),
        ("rtgs_completed_at", "TEXT"),
        ("rtgs_completed_by", "TEXT")
    ]:
        if col not in existing_invoice_cols:
            cur.execute(f"ALTER TABLE purchase_invoices ADD COLUMN {col} {definition}")

    # Check if branches exist, otherwise seed initial master data
    cur.execute("SELECT count(*) as cnt FROM branches")
    if cur.fetchone()['cnt'] == 0:
        seed_initial_data(cur)

    # Seed commodities if empty
    cur.execute("SELECT count(*) as cnt FROM commodities")
    if cur.fetchone()['cnt'] == 0:
        commodities = [
            ("c-soya", "Soyabean (Yellow)", "1201", 10.0, 1.5),
            ("c-wheat", "Wheat (Lokwan)", "1001", 10.0, 1.5),
            ("c-chana", "Chana (Desi)", "0713", 10.0, 1.5),
            ("c-mustard", "Mustard (Rayda)", "1207", 8.0, 1.5),
            ("c-maize", "Maize (Makka)", "1005", 12.0, 1.5),
        ]
        cur.executemany("INSERT INTO commodities (id, name, hsn_code, standard_moisture_pct, mandi_cess_pct) VALUES (?,?,?,?,?)", commodities)

    # Seed inspectors if empty
    cur.execute("SELECT count(*) as cnt FROM inspectors")
    if cur.fetchone()['cnt'] == 0:
        inspectors = [
            ("ins-1", None, "Mahesh Patidar", "Chief Assayer & Quality Lead", "9826011111"),
            ("ins-2", None, "Suresh Yadav", "Mandi Certified Inspector", "9826022222"),
            ("ins-3", "br-indore", "Babulal Meena", "Indore Yard Sampler", "9826033333"),
            ("ins-4", "br-ujjain", "Govind Solanki", "Ujjain Quality Inspector", "9826044444"),
            ("ins-5", "br-dewas", "Narayan Sharma", "Dewas Assayer", "9826055555"),
        ]
        cur.executemany("INSERT INTO inspectors (id, branch_id, name, designation, phone) VALUES (?,?,?,?,?)", inspectors)

    # Seed system settings if empty
    cur.execute("SELECT count(*) as cnt FROM system_settings")
    if cur.fetchone()['cnt'] == 0:
        default_settings = [
            # Super Admin
            ("SUPER_ADMIN", "GLOBAL", "org_name", "Rajeshri Shahu Trading"),
            ("SUPER_ADMIN", "GLOBAL", "org_pan", "AACCK1234F"),
            ("SUPER_ADMIN", "GLOBAL", "org_gstin", "23AACCK1234F1Z5"),
            ("SUPER_ADMIN", "GLOBAL", "fiscal_year", "2026-2027"),
            ("SUPER_ADMIN", "GLOBAL", "multi_branch_sync", "ENABLED"),
            ("SUPER_ADMIN", "GLOBAL", "audit_retention_days", "365"),
            ("SUPER_ADMIN", "GLOBAL", "license_status", "Active (Pro Tier - 3 Branches)"),
            ("SUPER_ADMIN", "GLOBAL", "license_valid_until", "31-March-2027"),
            ("SUPER_ADMIN", "GLOBAL", "license_key", "RST-PRO-2026-MH3B-89A12F"),
            ("SUPER_ADMIN", "GLOBAL", "license_tier", "Pro Tier (3 Branches: Chikhali, Varvand, Dhad)"),
            ("SUPER_ADMIN", "GLOBAL", "license_branch_limit", "3"),
            # Central Accounts
            ("CENTRAL_ACCOUNTS", "GLOBAL", "sec_269st_cash_limit", "199999"),
            ("CENTRAL_ACCOUNTS", "GLOBAL", "sec_40a3_cash_limit", "10000"),
            ("CENTRAL_ACCOUNTS", "GLOBAL", "corridor_tolerance_pct", "5.0"),
            ("CENTRAL_ACCOUNTS", "GLOBAL", "rtgs_auto_sms", "ENABLED"),
            ("CENTRAL_ACCOUNTS", "GLOBAL", "default_bank_account", "State Bank of India (A/C: 40992388112)"),
            # Branch (Global template)
            ("BRANCH", "GLOBAL", "default_weighment_mode", "MANUAL_YARD"),
            ("BRANCH", "GLOBAL", "parchi_gate_no", "Gate No. 2"),
            ("BRANCH", "GLOBAL", "auto_print_parchi", "ENABLED"),
            ("BRANCH", "GLOBAL", "cash_drawer_warning_limit", "50000")
        ]
        cur.executemany("INSERT OR IGNORE INTO system_settings (scope, scope_id, setting_key, setting_value) VALUES (?,?,?,?)", default_settings)

    # Seed default buyer companies/traders if none exist
    cur.execute("SELECT count(*) as cnt FROM parties WHERE party_type='BUYER'")
    if cur.fetchone()['cnt'] == 0:
        sample_buyers = [
            ("p-buyer-1", "br-indore", "Adani Wilmar Ltd.", "9827088881", "BUYER", "Pithampur Industrial Area, Sector 3, Dhar", "AAACA1234F", None, "23AAACA1234F1Z1", "Anand Sharma (Commercial)", "State Bank of India", "30987654399", "SBIN0004567", 0.0, 0.0),
            ("p-buyer-2", "br-indore", "Ruchi Soya Industries (Patanjali)", "9827099992", "BUYER", "Manglia Depot, AB Road, Indore", "AAACR5678P", None, "23AAACR5678P1Z8", "Sunil Jain (Purchase)", "ICICI Bank", "012305009999", "ICIC0000456", 0.0, 0.0),
            ("p-buyer-3", "br-ujjain", "ITC Limited (Choupal Sagar)", "9827012343", "BUYER", "Maksi Road Mandi Bypass, Ujjain", "AAACI9012T", None, "23AAACI9012T1Z4", "Vikram Rathore (Yard Lead)", "HDFC Bank", "50200098765432", "HDFC0000789", 0.0, 0.0),
            ("p-buyer-4", "br-dewas", "Godrej Agrovet Ltd.", "9827023454", "BUYER", "Industrial Area No. 1, Dewas", "AAACG3456K", None, "23AAACG3456K1Z3", "Pradeep Malviya (Manager)", "Axis Bank", "918020098765432", "UTIB0000189", 0.0, 0.0),
            ("p-buyer-5", "br-indore", "Kargil India Pvt Ltd", "9827034565", "BUYER", "Sanwer Industrial Area, Indore", "AAACK7890L", None, "23AAACK7890L1Z6", "Rajendra Varma (Agri Sourcing)", "Punjab National Bank", "4098001500012", "PUNB0409800", 0.0, 0.0),
        ]
        cur.executemany("""
        INSERT OR IGNORE INTO parties (id, home_branch_id, name, phone, party_type, village, pan_number, aadhaar_number, gstin, khasra_record_no, bank_name, bank_account_no, bank_ifsc, current_advance, advance_interest_rate)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, sample_buyers)

    conn.commit()
    conn.close()

def seed_initial_data(cur):
    today_str = date.today().isoformat()

    # 1. Seed 3 Branches
    branches = [
        ("br-chikhali", "BR-CHK", "Chikhali Branch", "MH/CHK/APMC-101", "APMC Market Yard, Chikhali (Buldhana)", "07264-242110"),
        ("br-varvand", "BR-VRV", "Varvand Branch", "MH/VRV/APMC-202", "Station Road, Varvand (Pune)", "02119-251220"),
        ("br-dhad", "BR-DHD", "Dhad Branch", "MH/DHD/APMC-303", "Main Market Yard, Dhad (Buldhana)", "07267-233330"),
    ]
    cur.executemany("INSERT INTO branches (id, branch_code, name, mandi_license_no, address, phone) VALUES (?,?,?,?,?,?)", branches)

    # 2. Seed Users for Multi-User Roles
    pw = hash_password("mandi123")
    admin_pw = hash_password("admin123")
    acc_pw = hash_password("acc123")

    users = [
        ("u-admin", None, "admin", admin_pw, "Vikramaditya Singhal (Owner)", "9826000001", "SUPER_ADMIN"),
        ("u-accountant", None, "accountant", acc_pw, "Omprakash Agrawal (Chief Accountant)", "9826000002", "ACCOUNTANT_HQ"),
        
        ("u-chikhali-munim", "br-chikhali", "chikhali_munim", pw, "Gopal Sharma (Chikhali Purchase)", "9826000003", "BRANCH_MUNIM"),
        ("u-chikhali-cashier", "br-chikhali", "chikhali_cashier", pw, "Santosh Verma (Chikhali Cashier)", "9826000004", "BRANCH_CASHIER"),
        
        ("u-varvand-munim", "br-varvand", "varvand_munim", pw, "Rakesh Joshi (Varvand Purchase)", "9826000005", "BRANCH_MUNIM"),
        ("u-varvand-cashier", "br-varvand", "varvand_cashier", pw, "Mohanlal Soni (Varvand Cashier)", "9826000006", "BRANCH_CASHIER"),
        
        ("u-dhad-munim", "br-dhad", "dhad_munim", pw, "Deepak Solanki (Dhad Purchase)", "9826000007", "BRANCH_MUNIM"),
        ("u-dhad-cashier", "br-dhad", "dhad_cashier", pw, "Kailash Tiwari (Dhad Cashier)", "9826000008", "BRANCH_CASHIER"),
    ]
    cur.executemany("INSERT INTO users (id, branch_id, username, password_hash, full_name, phone, role) VALUES (?,?,?,?,?,?,?)", users)

    # 3. Seed Daily Rates for Today (Central HQ Rate Board)
    rates = [
        ("r-1", today_str, None, "Soyabean (Yellow)", "STANDARD", 4400.0, 4650.0, 4800.0, "u-accountant"),
        ("r-2", today_str, None, "Wheat (Lokwan)", "STANDARD", 2600.0, 2750.0, 2900.0, "u-accountant"),
        ("r-3", today_str, None, "Chana (Desi)", "STANDARD", 5600.0, 5850.0, 6100.0, "u-accountant"),
        ("r-4", today_str, None, "Mustard (Rayda)", "STANDARD", 5200.0, 5400.0, 5650.0, "u-accountant"),
        ("r-5", today_str, None, "Maize (Makka)", "STANDARD", 2100.0, 2250.0, 2400.0, "u-accountant"),
    ]
    cur.executemany("INSERT INTO daily_commodity_rates (id, rate_date, branch_id, commodity_name, quality_grade, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl, set_by_user_id) VALUES (?,?,?,?,?,?,?,?,?)", rates)

    # 4. Seed Parties (Farmers & Stockers)
    parties = [
        # Farmers
        ("p-farmer-1", "br-chikhali", "Rameshwar Patel", "9827011111", "FARMER", "Village Chikhali Rural", "BKWPP1234F", "789012345678", None, "Khasra No. 142/2", "State Bank of India", "30987654321", "SBIN0001234", 15000.0, 12.0),
        ("p-farmer-2", "br-chikhali", "Balram Singh Rajput", "9827022222", "FARMER", "Village Kawhala, Chikhali", "CLFPS5678M", "890123456789", None, "Khasra No. 88/1", "Bank of Baroda", "12340100056789", "BARB0SANWER", 0.0, 12.0),
        ("p-farmer-3", "br-varvand", "Jagdish Chouhan", "9827033333", "FARMER", "Village Varvand Rural", "DFGPC9012K", "901234567890", None, "Khasra No. 219/3", "Punjab National Bank", "4567001500089", "PUNB0456700", 8000.0, 12.0),
        ("p-farmer-4", "br-dhad", "Radheshyam Malviya", "9827044444", "FARMER", "Village Dhad Rural", "ERTPS3456L", "678901234567", None, "Khasra No. 54/2", "Bank of Maharashtra", "78900012345", "MAHB0001234", 25000.0, 12.0),
        
        # Stockers
        ("p-stocker-1", "br-chikhali", "Kuber Agro Traders (Chikhali)", "9827055555", "STOCKER", "APMC Yard, Chikhali", "AABCK1234F", None, "27AABCK1234F1Z5", None, "HDFC Bank", "50200012345678", "HDFC0000123", 0.0, 0.0),
        ("p-stocker-2", "br-varvand", "Mahaveer Grain Merchants", "9827066666", "STOCKER", "Market Yard, Varvand", "AAGCM5678Q", None, "27AAGCM5678Q1Z9", None, "ICICI Bank", "012305001234", "ICIC0000123", 0.0, 0.0),
        ("p-stocker-3", "br-dhad", "Dhad Agri Stockists", "9827077777", "STOCKER", "Sub-Yard, Dhad", "AAECN9012R", None, "27AAECN9012R1Z2", None, "Axis Bank", "918020012345678", "UTIB0000189", 0.0, 0.0),
    ]
    cur.executemany("""
    INSERT INTO parties (id, home_branch_id, name, phone, party_type, village, pan_number, aadhaar_number, gstin, khasra_record_no, bank_name, bank_account_no, bank_ifsc, current_advance, advance_interest_rate)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, parties)

    # 5. Initialize Cash Float for today for each branch
    cash_floats = [
        ("cf-chikhali", "br-chikhali", today_str, 500000.0, 0.0, 0.0, 0.0, 500000.0, 500000.0),
        ("cf-varvand", "br-varvand", today_str, 400000.0, 0.0, 0.0, 0.0, 400000.0, 400000.0),
        ("cf-dhad", "br-dhad", today_str, 300000.0, 0.0, 0.0, 0.0, 300000.0, 300000.0),
    ]
    cur.executemany("""
    INSERT OR IGNORE INTO branch_daily_cash_drawers 
    (id, branch_id, record_date, opening_float, total_cash_payouts, petty_expenses_cash, bank_withdrawals_inward, calculated_closing_cash, physical_counted_cash)
    VALUES (?,?,?,?,?,?,?,?,?)
    """, cash_floats)

    # 6. Seed a sample paid invoice with manual kanta slip to provide instant analytics
    sample_invoice_id = "inv-seed-001"
    cur.execute("""
    INSERT OR IGNORE INTO purchase_invoices (
        id, branch_id, token_number, invoice_date, party_id, commodity_name, hsn_code, quality_grade,
        vehicle_number, weighment_mode, external_kanta_name, external_slip_number, bag_count, bag_type,
        gross_weight_kg, vehicle_tare_kg, bag_tare_kg, moisture_percentage, moisture_cut_kg, karda_percentage,
        karda_cut_kg, net_weight_kg, net_quintals, rate_per_quintal, is_rate_overridden, gross_amount,
        hamali_charge, tulai_charge, silai_charge, bardana_deduction, mandi_cess_amount, advance_adjusted,
        interest_adjusted, net_payable_amount, payout_status, created_by_user_id
    ) VALUES (
        ?, 'br-chikhali', 'CHK-20261028-001', ?, 'p-farmer-1', 'Soyabean (Yellow)', '1201', 'STANDARD',
        'MH-28-AB-1234', 'MANUAL_EXTERNAL', 'Shree Gajanand Kanta', 'SGK-4912', 60, 'HDPE_50KG',
        5200.0, 2100.0, 30.0, 11.5, 30.7, 1.0, 30.7, 3008.6, 30.086, 4650.0, 0, 139899.9,
        300.0, 120.0, 60.0, 0.0, 0.0, 5000.0, 50.0, 134369.9, 'PAID', 'u-chikhali-munim'
    )
    """, (sample_invoice_id, today_str))

    # Payout entry
    cur.execute("""
    INSERT OR IGNORE INTO cashier_payouts (
        id, branch_id, invoice_id, party_id, payout_mode, amount_paid,
        notes_500, notes_200, notes_100, notes_50, notes_20, notes_10, coins,
        cashier_user_id
    ) VALUES (
        'pay-seed-001', 'br-chikhali', ?, 'p-farmer-1', 'CASH', 134370.0,
        268, 1, 1, 1, 1, 0, 0, 'u-chikhali-cashier'
    )
    """, (sample_invoice_id,))

    # Ledger entries for seed invoice
    cur.execute("""
    INSERT OR IGNORE INTO ledger_entries (id, branch_id, transaction_date, voucher_type, voucher_id, account_name, party_id, debit_amount, credit_amount, narration)
    VALUES 
    ('led-1', 'br-chikhali', ?, 'PURCHASE', ?, 'Commodity Purchase A/c', 'p-farmer-1', 139899.9, 0, 'Purchase of 30.086 Qtl Soyabean from Rameshwar Patel'),
    ('led-2', 'br-chikhali', ?, 'PURCHASE', ?, 'Hamali Charges Payable', 'p-farmer-1', 0, 300.0, 'Labor deduction on 60 bags'),
    ('led-3', 'br-chikhali', ?, 'PURCHASE', ?, 'Tulai Charges Payable', 'p-farmer-1', 0, 120.0, 'Weighment charge'),
    ('led-4', 'br-chikhali', ?, 'PURCHASE', ?, 'Silai Charges Payable', 'p-farmer-1', 0, 60.0, 'Stitching deduction'),
    ('led-5', 'br-chikhali', ?, 'PURCHASE', ?, 'Farmer Advance Loan Recovery', 'p-farmer-1', 0, 5000.0, 'Recovery of seasonal advance'),
    ('led-6', 'br-chikhali', ?, 'PURCHASE', ?, 'Interest Income A/c', 'p-farmer-1', 0, 50.0, 'Interest on advance loan'),
    ('led-7', 'br-chikhali', ?, 'PURCHASE', ?, 'Sundry Creditors - Farmers', 'p-farmer-1', 0, 134369.9, 'Net payable to Rameshwar Patel'),
    ('led-8', 'br-chikhali', ?, 'PAYMENT', ?, 'Sundry Creditors - Farmers', 'p-farmer-1', 134370.0, 0, 'Cash settlement of token CHK-20261028-001'),
    ('led-9', 'br-chikhali', ?, 'PAYMENT', ?, 'Cashier Drawer - Cash in Hand', 'p-farmer-1', 0, 134370.0, 'Cash payout with denomination count')
    """, (today_str, sample_invoice_id, today_str, sample_invoice_id, today_str, sample_invoice_id, today_str, sample_invoice_id, today_str, sample_invoice_id, today_str, sample_invoice_id, today_str, sample_invoice_id, today_str, sample_invoice_id, today_str, sample_invoice_id))

    # Update drawer float
    cur.execute("""
    UPDATE branch_daily_cash_drawers 
    SET total_cash_payouts = total_cash_payouts + 134370.0,
        calculated_closing_cash = opening_float - 134370.0,
        physical_counted_cash = opening_float - 134370.0
    WHERE branch_id = 'br-indore' AND record_date = ?
    """, (today_str,))

    # Update farmer advance
    cur.execute("""
    UPDATE parties SET current_advance = current_advance - 5000.0 WHERE id = 'p-farmer-1'
    """)

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
