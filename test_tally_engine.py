import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tally_reports

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'commodity_mandi.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT * FROM parties WHERE party_type='FARMER' LIMIT 1")
party = dict(c.fetchone())
print('Testing Party:', party['name'])

c.execute("SELECT * FROM purchase_invoices")
invoices = [dict(r) for r in c.fetchall()]

c.execute("SELECT * FROM outward_orders")
outward = [dict(r) for r in c.fetchall()]

c.execute("SELECT * FROM ledger_entries")
ledgers = [dict(r) for r in c.fetchall()]

report = tally_reports.calculate_party_ledger(party, invoices, ledgers, outward)
print('Party Report calculated!')
print('  Opening Bal:', report['opening_balance'], report['opening_balance_type'])
print('  Transactions count:', len(report['transactions']))
print('  Total Debit:', report['total_debit'], 'Total Credit:', report['total_credit'])
print('  Closing Bal:', report['closing_balance'], report['closing_balance_type'])

xml_out = tally_reports.export_party_ledger_tally_xml(report)
print('Party XML generated successfully! Length:', len(xml_out))
assert "<ENVELOPE>" in xml_out
assert party['name'] in xml_out

inward_xml = tally_reports.export_daily_inward_tally_xml(invoices[:5], '2026-10-28', 'Chikhali APMC Main Yard')
print('Daily Inward XML generated successfully! Length:', len(inward_xml))
assert "<ENVELOPE>" in inward_xml

daybook_xml = tally_reports.export_consolidated_tally_daybook_xml(invoices[:5], outward, ledgers[:10], '2026-10-28', 'Chikhali APMC Main Yard')
print('Consolidated Daybook XML generated successfully! Length:', len(daybook_xml))
assert "<ENVELOPE>" in daybook_xml

print("All Tally XML assertions PASSED!")
