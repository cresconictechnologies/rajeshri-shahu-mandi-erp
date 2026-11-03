"""
Production Clean Slate Reset Script for Rajarshi Shahu Trading.
Safely wipes development/test transactions and dummy parties while preserving:
- Super Admin, Accountant & Branch Cashier user credentials
- Branches master configuration
- Commodities & Sortex quality standards
- System licensing & company settings
"""

import os
import shutil
import sqlite3
from datetime import datetime

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commodity_mandi.db")
backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

print(f"[*] Creating pre-wipe safety backup: {backup_path}")
shutil.copy2(db_path, backup_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

try:
    # 1. Inspect pre-wipe counts
    wipe_tables = [
        "purchase_invoices",
        "outward_orders",
        "cashier_payouts",
        "quality_inspections",
        "ledger_entries",
        "branch_daily_cash_drawers",
        "audit_change_logs",
        "parties",
        "user_sessions"
    ]
    
    print("\n--- PRE-WIPE TRANSACTION COUNTS ---")
    for t in wipe_tables:
        cur.execute(f"SELECT count(*) FROM [{t}]")
        cnt = cur.fetchone()[0]
        print(f"  • {t}: {cnt} records")

    # 2. Execute Clean Wipe
    cur.execute("PRAGMA foreign_keys = OFF")
    for t in wipe_tables:
        cur.execute(f"DELETE FROM [{t}]")
    
    # Reset AUTOINCREMENT counters if sqlite_sequence exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'")
    if cur.fetchone():
        for t in wipe_tables:
            cur.execute(f"DELETE FROM sqlite_sequence WHERE name='{t}'")

    cur.execute("PRAGMA foreign_keys = ON")
    conn.commit()

    print("\n--- POST-WIPE VERIFICATION ---")
    for t in wipe_tables:
        cur.execute(f"SELECT count(*) FROM [{t}]")
        cnt = cur.fetchone()[0]
        print(f"  [OK] {t}: {cnt} records (Clean Slate)")

    cur.execute("SELECT count(*) FROM branches")
    print(f"  [OK] branches preserved: {cur.fetchone()[0]}")
    cur.execute("SELECT count(*) FROM commodities")
    print(f"  [OK] commodities preserved: {cur.fetchone()[0]}")
    cur.execute("SELECT count(*) FROM users")
    print(f"  [OK] users preserved: {cur.fetchone()[0]}")
    cur.execute("SELECT count(*) FROM system_settings")
    print(f"  [OK] system_settings preserved: {cur.fetchone()[0]}")

    print("\n[OK] Database successfully reset to clean production v1.0 state!")
    print(f"[OK] Safety backup retained at: {backup_path}")

finally:
    conn.close()
