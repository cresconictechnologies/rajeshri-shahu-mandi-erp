import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

print("1. Testing GET /api/accounts/data...")
res = client.get("/api/accounts/data")
assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
data = res.json()
assert data["success"] is True
assert len(data["parties"]) > 0
assert len(data["branches"]) > 0
assert len(data["invoices"]) > 0
print(f"   Success! Invoices: {len(data['invoices'])}, Parties: {len(data['parties'])}, Ledgers: {len(data['ledgers'])}")

test_party = data["parties"][0]["id"]
print(f"2. Testing GET /api/accounts/reports/party-ledger for {test_party}...")
res_pl = client.get(f"/api/accounts/reports/party-ledger?party_id={test_party}")
assert res_pl.status_code == 200
pl_data = res_pl.json()
assert pl_data["success"] is True
print(f"   Success! Opening Bal: {pl_data['report']['opening_balance']}, Tx Count: {len(pl_data['report']['transactions'])}")

print("3. Testing GET /api/accounts/reports/party-ledger format=xml...")
res_xml = client.get(f"/api/accounts/reports/party-ledger?party_id={test_party}&format=xml")
assert res_xml.status_code == 200
assert "<ENVELOPE>" in res_xml.text
print(f"   Success! Party XML length: {len(res_xml.text)}")

print("4. Testing GET /api/accounts/reports/party-ledger format=csv...")
res_csv = client.get(f"/api/accounts/reports/party-ledger?party_id={test_party}&format=csv")
assert res_csv.status_code == 200
assert "Running Balance" in res_csv.text
print(f"   Success! CSV length: {len(res_csv.text)}")

print("5. Testing GET /api/accounts/reports/daily-inward...")
sample_date = data["invoices"][0]["invoice_date"]
res_inw = client.get(f"/api/accounts/reports/daily-inward?date={sample_date}")
assert res_inw.status_code == 200
inw_data = res_inw.json()
assert inw_data["success"] is True
print(f"   Success! Date: {sample_date}, Lots: {inw_data['report']['total_lots']}, Net Qtl: {inw_data['report']['total_net_quintals']}")

print("6. Testing GET /api/accounts/reports/daily-inward format=xml...")
res_inw_xml = client.get(f"/api/accounts/reports/daily-inward?date={sample_date}&format=xml")
assert res_inw_xml.status_code == 200
assert "<ENVELOPE>" in res_inw_xml.text
print(f"   Success! Inward XML length: {len(res_inw_xml.text)}")

print("7. Testing GET /api/accounts/reports/daily-outward...")
res_out = client.get("/api/accounts/reports/daily-outward")
assert res_out.status_code == 200
out_data = res_out.json()
assert out_data["success"] is True
print(f"   Success! Outward count: {out_data['report']['total_dispatches']}")

print("8. Testing GET /api/accounts/reports/tally-daybook...")
res_day = client.get(f"/api/accounts/reports/tally-daybook?date={sample_date}")
assert res_day.status_code == 200
assert "<ENVELOPE>" in res_day.text
print(f"   Success! Daybook XML length: {len(res_day.text)}")

print("\nALL 8 BACKEND REPORT ENDPOINTS PASSED WITH 100% SUCCESS!")
