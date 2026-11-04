"""
Test live API endpoints for rates:
1. GET /api/branch/rates
2. GET /api/accounts/rates
3. POST /api/accounts/rates
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date
from starlette.testclient import TestClient
from server import app, create_session_token

client = TestClient(app)

def get_auth_cookies(role="SUPER_ADMIN", username="admin"):
    import database
    conn = database.get_connection()
    try:
        user = dict(conn.execute("SELECT * FROM users WHERE role=? LIMIT 1", (role,)).fetchone())
        token = create_session_token(user["username"], user["role"], user.get("branch_id") or "", user["id"])
        return {"mandi_session": token}
    finally:
        conn.close()

def test_endpoints():
    print("Testing GET /api/branch/rates...")
    cashier_cookies = get_auth_cookies(role="BRANCH_CASHIER")
    resp = client.get("/api/branch/rates?branch_id=br-chikhali", cookies=cashier_cookies)
    print("Status:", resp.status_code)
    data = resp.json()
    print("Response keys:", list(data.keys()))
    assert data["success"] is True
    print(f"Returned {len(data['rates'])} rate corridors for branch {data['branch_id']}.")
    for r in data["rates"][:3]:
        print(f"  - {r['commodity_name']}: Target ₹{r['target_rate_per_qtl']} (Min ₹{r['min_rate_per_qtl']} - Max ₹{r['max_rate_per_qtl']})")

    print("\nTesting GET /api/accounts/rates...")
    accountant_cookies = get_auth_cookies(role="ACCOUNTANT_HQ")
    resp2 = client.get("/api/accounts/rates", cookies=accountant_cookies)
    print("Status:", resp2.status_code)
    data2 = resp2.json()
    assert data2["success"] is True
    print(f"Returned {len(data2['rates'])} rates for accounts dashboard.")

    print("\nTesting POST /api/accounts/rates...")
    today_str = date.today().isoformat()
    post_payload = {
        "rate_date": today_str,
        "commodity_name": "Soyabean (Yellow)",
        "quality_grade": "STANDARD",
        "min_rate": 4850.0,
        "target_rate": 5100.0,
        "max_rate": 5350.0,
        "branch_id": ""
    }
    resp3 = client.post("/api/accounts/rates", data=post_payload, cookies=accountant_cookies, headers={"accept": "application/json"})
    print("Status:", resp3.status_code)
    data3 = resp3.json()
    print("Response:", data3)
    assert data3["success"] is True
    assert data3["target_rate"] == 5100.0

    print("\nTesting GET /api/branch/rates after update...")
    resp4 = client.get("/api/branch/rates?branch_id=br-chikhali", cookies=cashier_cookies)
    data4 = resp4.json()
    soya_rate = data4["rates_map"].get("Soyabean (Yellow)")
    print(f"Cashier saw updated Soyabean rate: Target ₹{soya_rate['target_rate_per_qtl']}")

    print("\n✓ ALL API ENDPOINT TESTS PASSED CLEANLY!")

if __name__ == "__main__":
    test_endpoints()
