# Mandi & Commodity Procurement ERP - Windows PowerShell Launcher
$Host.UI.RawUI.WindowTitle = "Mandi & Commodity Procurement ERP - Port 8080"
Set-Location -Path $PSScriptRoot

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   MANDI & COMMODITY PROCUREMENT ERP - THREE-TIER GOVERNANCE SYSTEM" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Host Port: 8080 (Dedicated, isolated from Restaurant App on Port 8000)" -ForegroundColor Green
Write-Host "Database:  commodity_mandi.db (SQLite WAL Mode Active)" -ForegroundColor Gray
Write-Host ""
Write-Host "Login Credentials:" -ForegroundColor White
Write-Host "  - Level 1 (Super Admin):      admin / admin123" -ForegroundColor White
Write-Host "  - Level 2 (Central Accounts): accountant / acc123" -ForegroundColor White
Write-Host "  - Level 3 (Branch Munim):     indore_munim / mandi123" -ForegroundColor White
Write-Host "  - Level 3 (Branch Cashier):   indore_cashier / mandi123" -ForegroundColor White
Write-Host ""
Write-Host "Opening Default Browser at http://127.0.0.1:8080 ..." -ForegroundColor Cyan
Start-Process "http://127.0.0.1:8080"
Write-Host ""
Write-Host "Starting Uvicorn Server on http://0.0.0.0:8080 ..." -ForegroundColor Green
python server.py
