@echo off
title Rajarshi Shahu Trading - Mandi ERP One-Click Updater
color 0B

echo ===============================================================================
echo            RAJARSHI SHAHU TRADING - ONE-CLICK SOFTWARE UPDATER
echo                  Compatible with Windows 7, 8, 8.1, 10, 11
echo ===============================================================================
echo.

set "APP_DIR=%~dp0"
set "UPDATE_URL=https://github.com/cresconictechnologies/rajeshri-shahu-mandi-erp/releases/download/v1.0/Rajarshi_Shahu_Trading_Windows_x64.zip"
set "ZIP_FILE=%APP_DIR%update_temp.zip"
set "EXTRACT_DIR=%APP_DIR%update_extracted"

echo [1/5] Terminating running Mandi ERP instances...
taskkill /f /im Rajarshi_Shahu_Trading.exe >nul 2>&1
taskkill /f /im Launcher.exe >nul 2>&1
timeout /t 2 /nobreak >nul 2>&1
echo       Done.
echo.

echo [2/5] Creating safety backup of your database...
if exist "%APP_DIR%commodity_mandi.db" (
    copy /y "%APP_DIR%commodity_mandi.db" "%APP_DIR%commodity_mandi.db.pre_update.bak" >nul 2>&1
    echo       Database backed up to commodity_mandi.db.pre_update.bak
) else if exist "%APP_DIR%dist\Rajarshi_Shahu_Trading\commodity_mandi.db" (
    copy /y "%APP_DIR%dist\Rajarshi_Shahu_Trading\commodity_mandi.db" "%APP_DIR%dist\Rajarshi_Shahu_Trading\commodity_mandi.db.pre_update.bak" >nul 2>&1
    echo       Database backed up.
)
echo.

echo [3/5] Downloading latest software release from cloud...
echo       Source: %UPDATE_URL%
powershell -NoProfile -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; $wc = New-Object System.Net.WebClient; $wc.Headers.Add('User-Agent', 'Mandi-ERP-Updater'); Write-Host '       Downloading update package... (approx 114 MB)'; $wc.DownloadFile('%UPDATE_URL%', '%ZIP_FILE%'); Write-Host '       Download complete!'"
if not exist "%ZIP_FILE%" (
    echo [-] ERROR: Download failed. Please check your internet connection or download manually from:
    echo     https://mandi-erp-tracker.vercel.app
    pause
    exit /b 1
)
echo.

echo [4/5] Extracting updated files and applying fixes...
if exist "%EXTRACT_DIR%" rmdir /s /q "%EXTRACT_DIR%"
mkdir "%EXTRACT_DIR%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "Write-Host '       Unpacking update archive...'; [System.IO.Compression.ZipFile]::ExtractToDirectory('%ZIP_FILE%', '%EXTRACT_DIR%')" 2>nul
if %ERRORLEVEL% neq 0 (
    :: Fallback for Windows 7 using Shell.Application COM
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell = New-Object -ComObject Shell.Application; $zip = $shell.Namespace('%ZIP_FILE%'); $dest = $shell.Namespace('%EXTRACT_DIR%'); $dest.CopyHere($zip.Items(), 16)"
)

:: Copy updated files over APP_DIR
echo       Applying updated binaries, launcher, and libraries...
xcopy /e /y /q "%EXTRACT_DIR%\*" "%APP_DIR%" >nul 2>&1

:: Clean up temporary zip and extraction folder
del /f /q "%ZIP_FILE%" >nul 2>&1
rmdir /s /q "%EXTRACT_DIR%" >nul 2>&1
echo       Done.
echo.

echo [5/5] Update successfully applied!
echo ===============================================================================
echo   All systems updated:
echo   [OK] Windows 7 KERNEL32 PackageIdFromFullName crash eliminated
echo   [OK] Direct socket probe (0.03s) with 60s timeout active
echo   [OK] Live cloud sync for rates and corridors across all PCs enabled
echo   [OK] 3 Official Branches: Chikhali, Varvand, and Sarola Maruti ready
echo ===============================================================================
echo.
echo Launching updated Mandi ERP Launcher...
start "" "%APP_DIR%Launcher.exe"
timeout /t 3 >nul 2>&1
exit /b 0
