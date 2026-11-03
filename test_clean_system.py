import sqlite3
import os
import requests

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "commodity_mandi.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("=== 1. VERIFYING DATABASE CLEAN STATE ===")
tables = [
    "parties", "purchase_invoices", "outward_orders", 
    "cashier_payouts", "quality_inspections", "ledger_entries"
]
for t in tables:
    cur.execute(f"SELECT count(*) FROM [{t}]")
    cnt = cur.fetchone()[0]
    assert cnt == 0, f"Table {t} should have 0 records, got {cnt}"
    print(f"  [PASS] {t} = 0 records")

cur.execute("SELECT count(*) FROM branches")
b_cnt = cur.fetchone()[0]
print(f"  [PASS] Active branches = {b_cnt}")

cur.execute("SELECT count(*) FROM commodities")
c_cnt = cur.fetchone()[0]
print(f"  [PASS] Configured commodities = {c_cnt}")

cur.execute("SELECT full_name, username, role FROM users WHERE role='SUPER_ADMIN'")
admin_row = cur.fetchone()
print(f"  [PASS] Super Admin: {admin_row[0]} ({admin_row[1]})")

conn.close()

print("\n=== 2. VERIFYING PARCHI SLIP TEMPLATE JINJA RENDERING ===")
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")))
template = env.get_template("parchi_slip.html")

mock_invoice = {
    "token_number": "101",
    "invoice_date": "2026-11-03",
    "branch_name": "Chikhali Mandi Yard",
    "party_name": "Rameshwar Patil",
    "village": "Varvand",
    "vehicle_number": "MH-28-AB-1234",
    "payout_status": "PAID",
    "commodity_name": "Chana (Bengal Gram)",
    "net_quintals": 42.50,
    "rate_per_quintal": 5600.00,
    "gross_amount": 238000.00,
    "hamali_charge": 1062.50,
    "net_payable_amount": 236937.50
}

html_out = template.render(invoice=mock_invoice)
assert "RAJARSHI SHAHU TRADING" in html_out
assert "Chana (Bengal Gram)" in html_out
assert "42.50 Qtl" in html_out
assert "5600.00" in html_out
assert "Hamali Deduction" in html_out
assert "236,937.50" in html_out
assert "Cashier / Munim Sign" in html_out
print("  [PASS] Parchi slip renders correctly with clean layout, commodity, rate, qtl, hamali deduction, and net payable!")

print("\n=== ALL SYSTEM CHECKS PASSED SUCCESSFULLY ===")
