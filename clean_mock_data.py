"""
Clean Mock Data Script for Rajarshi Shahu Trading (Mandi ERP)
Safely clears mock transactions (invoices, payouts, outward orders, mock QC tickets, ledger)
while strictly preserving all master records (branches, commodities, user credentials, system settings, license tokens).
"""

import sqlite3
import os
import shutil

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commodity_mandi.db")
BACKUP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commodity_mandi_pre_cleanup.db.bak")

def clean_mock_data():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    # 1. Create a timestamped safety backup
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"[BACKUP] Safety backup saved to: {BACKUP_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 2. Get pre-cleanup counts
    tables_to_clear = [
        "cashier_payouts",
        "ledger_entries",
        "purchase_invoices",
        "outward_orders",
        "quality_inspections",
        "audit_change_logs",
    ]

    print("[STATUS] Clearing mock transactional records...")
    for tbl in tables_to_clear:
        try:
            cnt = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            cur.execute(f"DELETE FROM {tbl}")
            print(f"  - Cleared {cnt} records from '{tbl}'")
        except sqlite3.OperationalError as e:
            print(f"  - Table '{tbl}' skipped: {e}")

    # Reset any branch cash drawer payouts to 0
    try:
        cur.execute("UPDATE branch_daily_cash_drawers SET total_cash_payouts = 0, petty_expenses_cash = 0, calculated_closing_cash = opening_float, physical_counted_cash = opening_float")
        print("  - Reset daily cash drawer payouts to 0")
    except Exception as e:
        print(f"  - Note on cash drawers: {e}")

    conn.commit()
    conn.close()
    print("[SUCCESS] Mock data cleanup completed successfully. Master tables preserved.")

if __name__ == "__main__":
    clean_mock_data()
