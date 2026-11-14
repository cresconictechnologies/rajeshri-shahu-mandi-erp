from fastapi.testclient import TestClient
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import app

client = TestClient(app)

print("1. Testing GET /api/accounts/reports/party-balances (JSON)...")
res1 = client.get("/api/accounts/reports/party-balances")
assert res1.status_code == 200, f"Expected 200, got {res1.status_code}: {res1.text}"
data1 = res1.json()
assert data1.get("success") is True
summary = data1.get("summary", {})
parties = data1.get("parties", [])
print(f"   Success! Total Parties: {summary.get('total_parties')}, Parties with Activity: {len(parties)}")
print(f"   Payable to Farmers: Rs.{summary.get('total_payable_to_farmers'):,.2f}")
print(f"   Receivable from Buyers: Rs.{summary.get('total_receivable_from_buyers'):,.2f}")
print(f"   Settled Parties: {summary.get('total_settled_parties')}")

print("\n2. Testing GET /api/accounts/reports/party-balances?format=csv...")
res2 = client.get("/api/accounts/reports/party-balances?format=csv")
assert res2.status_code == 200, f"Expected 200, got {res2.status_code}: {res2.text}"
assert "text/csv" in res2.headers.get("content-type", "")
assert "Party Name" in res2.text
print(f"   Success! CSV length: {len(res2.text)} bytes")

print("\n3. Testing Party Ledger with enriched remaining balance fields...")
cur_party = parties[0] if parties else {"party_id": "test"}
p_id = cur_party.get("party_id")
res3 = client.get(f"/api/accounts/reports/party-ledger?party_id={p_id}")
assert res3.status_code == 200
rep = res3.json().get("report", {})
assert "remaining_balance" in rep
assert "balance_status" in rep
assert "balance_status_text" in rep
print(f"   Success! Party: {rep['party'].get('name')}")
print(f"   Remaining Balance: Rs.{rep['remaining_balance']:,.2f} ({rep['balance_status_text']})")

print("\nALL PARTY BALANCES TESTS PASSED WITH 100% SUCCESS!")
