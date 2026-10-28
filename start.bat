@echo off
title Mandi & Commodity Procurement ERP - Port 8080
cd /d "%~dp0"

echo ======================================================================
echo    MANDI & COMMODITY PROCUREMENT ERP - THREE-TIER GOVERNANCE SYSTEM
echo ======================================================================
echo.
echo Host Port: 8080 (Dedicated, isolated from Restaurant App on Port 8000)
echo Database:  commodity_mandi.db (SQLite WAL Mode Active)
echo.
echo Login Credentials:
echo   - Level 1 (Super Admin):      admin / admin123
echo   - Level 2 (Central Accounts): accountant / acc123
echo   - Level 3 (Branch Munim):     indore_munim / mandi123
echo   - Level 3 (Branch Cashier):   indore_cashier / mandi123
echo.
echo Launching Default Web Browser to http://127.0.0.1:8080 ...
start "" "http://127.0.0.1:8080"
echo.
echo Starting Web Server on http://0.0.0.0:8080 ...
python server.py
pause
