from fastapi.testclient import TestClient
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import app

client = TestClient(app)

print("1. Testing Party Ledger PDF & XLSX...")
res_pdf = client.get("/api/accounts/reports/party-ledger?party_id=party-akshay-nikas&format=pdf")
assert res_pdf.status_code == 200, f"Expected 200, got {res_pdf.status_code}"
assert res_pdf.headers.get("content-type") == "application/pdf"
assert res_pdf.content.startswith(b"%PDF")
print(f"   Success! Party PDF size: {len(res_pdf.content)} bytes")

res_xlsx = client.get("/api/accounts/reports/party-ledger?party_id=party-akshay-nikas&format=xlsx")
assert res_xlsx.status_code == 200
assert "openxmlformats" in res_xlsx.headers.get("content-type", "")
print(f"   Success! Party XLSX size: {len(res_xlsx.content)} bytes")

print("\n2. Testing Daily Inward PDF & XLSX...")
res_in_pdf = client.get("/api/accounts/reports/daily-inward?date=2026-11-02&format=pdf")
assert res_in_pdf.status_code == 200
assert res_in_pdf.headers.get("content-type") == "application/pdf"
assert res_in_pdf.content.startswith(b"%PDF")
print(f"   Success! Daily Inward PDF size: {len(res_in_pdf.content)} bytes")

res_in_xlsx = client.get("/api/accounts/reports/daily-inward?date=2026-11-02&format=xlsx")
assert res_in_xlsx.status_code == 200
assert "openxmlformats" in res_in_xlsx.headers.get("content-type", "")
print(f"   Success! Daily Inward XLSX size: {len(res_in_xlsx.content)} bytes")

print("\n3. Testing Party Balances PDF & XLSX...")
res_bal_pdf = client.get("/api/accounts/reports/party-balances?format=pdf")
assert res_bal_pdf.status_code == 200
assert res_bal_pdf.headers.get("content-type") == "application/pdf"
assert res_bal_pdf.content.startswith(b"%PDF")
print(f"   Success! Party Balances PDF size: {len(res_bal_pdf.content)} bytes")

res_bal_xlsx = client.get("/api/accounts/reports/party-balances?format=xlsx")
assert res_bal_xlsx.status_code == 200
assert "openxmlformats" in res_bal_xlsx.headers.get("content-type", "")
print(f"   Success! Party Balances XLSX size: {len(res_bal_xlsx.content)} bytes")

print("\n4. Testing Daily Outward PDF & XLSX...")
res_out_pdf = client.get("/api/accounts/reports/daily-outward?format=pdf")
assert res_out_pdf.status_code == 200
assert res_out_pdf.headers.get("content-type") == "application/pdf"
assert res_out_pdf.content.startswith(b"%PDF")
print(f"   Success! Daily Outward PDF size: {len(res_out_pdf.content)} bytes")

res_out_xlsx = client.get("/api/accounts/reports/daily-outward?format=xlsx")
assert res_out_xlsx.status_code == 200
assert "openxmlformats" in res_out_xlsx.headers.get("content-type", "")
print(f"   Success! Daily Outward XLSX size: {len(res_out_xlsx.content)} bytes")

print("\nALL SERVER PDF & XLSX ENDPOINTS PASSED WITH 100% SUCCESS!")
