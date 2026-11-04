"""
Multi-PC Cloud Rate & Price Synchronization End-to-End Simulation Test.
Proves that rates changed on PC 1 (Accountant/HQ) are pushed to Supabase Cloud
and immediately pulled and visible on PC 2 (Cashier at Chikhali branch) without any local LAN dependency.
"""

import os
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uuid
import shutil
import sqlite3
from datetime import date, datetime, timezone

# Ensure stdout handles unicode/rupee symbols cleanly
sys.stdout.reconfigure(encoding="utf-8")

import supabase_sync

def setup_simulated_db(db_path: str):
    """Initializes a fresh isolated SQLite database mimicking a standalone PC."""
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Create minimal required tables matching schema
    cur.execute("""
        CREATE TABLE IF NOT EXISTS branches (
            id TEXT PRIMARY KEY,
            branch_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS commodities (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            standard_moisture_pct REAL DEFAULT 10.0,
            mandi_cess_pct REAL DEFAULT 0.0,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS parties (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            village TEXT,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            branch_id TEXT REFERENCES branches(id),
            is_active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
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
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            setting_key TEXT NOT NULL,
            setting_value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(scope, scope_id, setting_key)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue (
            id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            payload JSON,
            status TEXT DEFAULT 'PENDING',
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            synced_at TEXT
        );
    """)
    
    # Seed branch and commodities
    cur.execute("INSERT INTO branches (id, branch_code, name) VALUES ('br-chikhali', 'CHK', 'Chikhali Main Mandi')")
    cur.execute("INSERT INTO branches (id, branch_code, name) VALUES ('br-varvand', 'VAR', 'Varvand Rural Branch')")
    cur.execute("INSERT INTO commodities (id, name) VALUES ('c-soya', 'Soyabean (Yellow)')")
    cur.execute("INSERT INTO commodities (id, name) VALUES ('c-wheat', 'Wheat (Lokwan)')")
    cur.execute("INSERT INTO users (id, username, password_hash, role) VALUES ('u-acc', 'accountant', 'hash', 'ACCOUNTANT_HQ')")
    
    conn.commit()
    conn.close()


def run_multi_pc_simulation():
    print("=" * 70)
    print("STARTING MULTI-PC CLOUD RATE SYNCHRONIZATION SIMULATION")
    print("=" * 70)

    today_str = date.today().isoformat()
    pc1_db = "pc1_accountant.db"
    pc2_db = "pc2_cashier.db"

    try:
        # Step 0: Setup isolated local SQLite instances for PC 1 and PC 2
        print(f"\n[Step 0] Initializing isolated PC 1 ({pc1_db}) and PC 2 ({pc2_db})...")
        setup_simulated_db(pc1_db)
        setup_simulated_db(pc2_db)
        print("✓ Both PC SQLite databases successfully initialized.")

        # Override supabase_sync get_sqlite_connection to point to PC 1
        print("\n[Step 1] PC 1 (Accountant at HQ): Setting new market corridor rates for today...")
        def pc1_get_conn():
            c = sqlite3.connect(pc1_db)
            c.row_factory = sqlite3.Row
            return c

        supabase_sync.get_sqlite_connection = pc1_get_conn

        # PC 1 sets Global rate for Soyabean: Target ₹5,050 (4800 - 5300)
        conn1 = pc1_get_conn()
        cur1 = conn1.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        soya_id = f"r-{uuid.uuid4().hex[:8]}"
        cur1.execute("""
            INSERT INTO daily_commodity_rates (id, rate_date, branch_id, commodity_name, quality_grade, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl, updated_at)
            VALUES (?, ?, NULL, ?, 'STANDARD', ?, ?, ?, ?)
        """, (soya_id, today_str, 'Soyabean (Yellow)', 4800.0, 5050.0, 5300.0, now_iso))
        
        # PC 1 sets Global rate for Wheat: Target ₹2,950 (2800 - 3100)
        wheat_id = f"r-{uuid.uuid4().hex[:8]}"
        cur1.execute("""
            INSERT INTO daily_commodity_rates (id, rate_date, branch_id, commodity_name, quality_grade, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl, updated_at)
            VALUES (?, ?, NULL, ?, 'STANDARD', ?, ?, ?, ?)
        """, (wheat_id, today_str, 'Wheat (Lokwan)', 2800.0, 2950.0, 3100.0, now_iso))
        conn1.commit()
        conn1.close()

        print(f"✓ PC 1 recorded rates locally: Soyabean (Target ₹5,050), Wheat (Target ₹2,950)")

        # PC 1 pushes changes to Supabase Cloud
        print("\n[Step 2] PC 1: Pushing new daily rates to Supabase Cloud over Internet...")
        push_res = supabase_sync.push_local_to_supabase(["daily_commodity_rates"])
        print(f"  Push response: {push_res}")
        assert push_res["success"] is True, f"Push failed: {push_res}"
        assert push_res["pushed"] >= 2, f"Expected at least 2 records pushed, got {push_res['pushed']}"
        print("✓ PC 1 successfully pushed rates to Supabase Cloud.")

        # Verify rates exist in Supabase Cloud via REST client
        rest_client = supabase_sync.get_rest_client()
        if rest_client:
            resp = rest_client.get(f"/rest/v1/daily_commodity_rates?rate_date=eq.{today_str}&select=*")
            assert resp.status_code == 200
            cloud_rates = resp.json()
            cloud_soya = next((r for r in cloud_rates if r["commodity_name"] == "Soyabean (Yellow)" and r["branch_id"] is None), None)
            assert cloud_soya is not None, "Soyabean rate missing in Supabase Cloud"
            assert float(cloud_soya["target_rate_per_qtl"]) == 5050.0, f"Expected 5050.0 in cloud, got {cloud_soya['target_rate_per_qtl']}"
            print(f"✓ Verified Supabase Cloud has Soyabean Target Rate = ₹{cloud_soya['target_rate_per_qtl']}")

        # Step 3: PC 2 (Cashier at Chikhali branch) connects and pulls from Supabase Cloud
        print("\n[Step 3] Switching context to PC 2 (Cashier machine at Chikhali branch)...")
        def pc2_get_conn():
            c = sqlite3.connect(pc2_db)
            c.row_factory = sqlite3.Row
            return c

        supabase_sync.get_sqlite_connection = pc2_get_conn

        # Verify PC 2 starts with NO rates
        conn2 = pc2_get_conn()
        cur2 = conn2.cursor()
        cur2.execute("SELECT count(*) FROM daily_commodity_rates WHERE rate_date=?", (today_str,))
        count_before = cur2.fetchone()[0]
        assert count_before == 0, f"Expected 0 rates in PC 2 before pull, found {count_before}"
        print(f"  PC 2 current rates for today: {count_before} records (empty)")

        print("\n[Step 4] PC 2: Actively pulling latest rates from Supabase Cloud over Internet...")
        pull_res = supabase_sync.pull_supabase_to_local(["daily_commodity_rates"])
        print(f"  Pull response: {pull_res}")
        assert pull_res["success"] is True, f"Pull failed: {pull_res}"
        assert pull_res["pulled"] > 0, f"Expected records pulled, got {pull_res['pulled']}"
        assert len(pull_res["errors"]) == 0, f"Errors during pull: {pull_res['errors']}"

        # Verify PC 2 now has the rates published by PC 1
        cur2.execute("""
            SELECT commodity_name, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl 
            FROM daily_commodity_rates 
            WHERE rate_date=? AND branch_id IS NULL
            ORDER BY commodity_name
        """, (today_str,))
        pulled_rates = cur2.fetchall()
        rates_map = {r["commodity_name"]: dict(r) for r in pulled_rates}
        print("  PC 2 rates in SQLite after cloud pull:")
        for comm, r_dict in rates_map.items():
            print(f"    - {comm}: Min ₹{r_dict['min_rate_per_qtl']}, Target ₹{r_dict['target_rate_per_qtl']}, Max ₹{r_dict['max_rate_per_qtl']}")

        assert "Soyabean (Yellow)" in rates_map, "Soyabean rate missing on PC 2"
        assert rates_map["Soyabean (Yellow)"]["target_rate_per_qtl"] == 5050.0, f"Expected 5050.0 on PC 2, got {rates_map['Soyabean (Yellow)']['target_rate_per_qtl']}"
        assert "Wheat (Lokwan)" in rates_map, "Wheat rate missing on PC 2"
        assert rates_map["Wheat (Lokwan)"]["target_rate_per_qtl"] == 2950.0, f"Expected 2950.0 on PC 2, got {rates_map['Wheat (Lokwan)']['target_rate_per_qtl']}"
        print("✓ PC 2 successfully pulled and verified PC 1's rates!")

        # Step 5: Test Branch-Specific Rate Override
        print("\n[Step 5] Testing Branch-Specific Rate Override:")
        print("  PC 1 sets higher Soyabean rate specifically for Chikhali branch (Target ₹5,200)...")
        supabase_sync.get_sqlite_connection = pc1_get_conn
        chk_soya_id = f"r-{uuid.uuid4().hex[:8]}"
        now_iso2 = datetime.now(timezone.utc).isoformat()
        conn1 = pc1_get_conn()
        cur1 = conn1.cursor()
        cur1.execute("""
            INSERT INTO daily_commodity_rates (id, rate_date, branch_id, commodity_name, quality_grade, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl, updated_at)
            VALUES (?, ?, 'br-chikhali', 'Soyabean (Yellow)', 'STANDARD', 5000.0, 5200.0, 5450.0, ?)
        """, (chk_soya_id, today_str, now_iso2))
        conn1.commit()

        push_res2 = supabase_sync.push_local_to_supabase(["daily_commodity_rates"])
        assert push_res2["success"] is True

        print("  PC 2 pulls Chikhali rate override from Supabase Cloud...")
        supabase_sync.get_sqlite_connection = pc2_get_conn
        pull_res2 = supabase_sync.pull_supabase_to_local(["daily_commodity_rates"])
        assert pull_res2["success"] is True

        # Query effective rate for Chikhali
        cur2.execute("""
            SELECT commodity_name, quality_grade, min_rate_per_qtl, target_rate_per_qtl, max_rate_per_qtl 
            FROM daily_commodity_rates 
            WHERE rate_date=? AND (branch_id='br-chikhali' OR branch_id IS NULL)
            ORDER BY (branch_id IS NOT NULL) ASC, updated_at ASC
        """, (today_str,))
        effective_rows = cur2.fetchall()
        effective_map = {r["commodity_name"]: dict(r) for r in effective_rows}
        print("  PC 2 Effective Chikhali Rates:")
        for comm, r_dict in effective_map.items():
            print(f"    - {comm}: Target ₹{r_dict['target_rate_per_qtl']} (Min ₹{r_dict['min_rate_per_qtl']} – Max ₹{r_dict['max_rate_per_qtl']})")

        assert effective_map["Soyabean (Yellow)"]["target_rate_per_qtl"] == 5200.0, "Expected Chikhali branch override ₹5,200"
        print("✓ Branch-specific override correctly prioritized on PC 2!")

        conn2.close()

        print("\n" + "=" * 70)
        print("ALL MULTI-PC CLOUD RATE SYNCHRONIZATION TESTS PASSED WITH 100% SUCCESS!")
        print("=" * 70)

    finally:
        # Restore default connection
        supabase_sync.get_sqlite_connection = lambda: sqlite3.connect("commodity_mandi.db")
        # Cleanup temporary test databases
        for db in [pc1_db, pc2_db]:
            if os.path.exists(db):
                try:
                    os.remove(db)
                except Exception:
                    pass

if __name__ == "__main__":
    run_multi_pc_simulation()
