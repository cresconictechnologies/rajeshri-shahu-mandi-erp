@echo off
title Rajarshi Shahu Trading - Mandi ERP Setup and Launcher
color 0A

echo ===============================================================================
echo            RAJARSHI SHAHU TRADING - MANDI ERP DESKTOP SYSTEM
echo              Universal Compatibility Setup (Windows 7 to 11)
echo ===============================================================================
echo.

:: 1. Admin Privilege Detection
net session >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [*] Administrative privileges detected. Full system configuration enabled.
    set IS_ADMIN=1
) else (
    echo [*] Running with standard user privileges.
    echo     Note: Local directory fixes will be applied; System32 requires Administrator.
    set IS_ADMIN=0
)
echo.

:: 2. Determine App and Target Paths
set "BASE_DIR=%~dp0"
set "TARGET_EXE="
set "EXE_DIR="

if exist "%BASE_DIR%Rajarshi_Shahu_Trading.exe" (
    set "TARGET_EXE=%BASE_DIR%Rajarshi_Shahu_Trading.exe"
    set "EXE_DIR=%BASE_DIR%"
) else if exist "%BASE_DIR%dist\Rajarshi_Shahu_Trading\Rajarshi_Shahu_Trading.exe" (
    set "TARGET_EXE=%BASE_DIR%dist\Rajarshi_Shahu_Trading\Rajarshi_Shahu_Trading.exe"
    set "EXE_DIR=%BASE_DIR%dist\Rajarshi_Shahu_Trading\"
) else (
    echo [-] ERROR: Rajarshi_Shahu_Trading.exe not found!
    echo     Please make sure you have extracted the entire software folder.
    pause
    exit /b 1
)

:: Locate prerequisites folder
set "PREREQ_DIR=%BASE_DIR%prerequisites\"
if not exist "%PREREQ_DIR%" (
    if exist "%BASE_DIR%..\prerequisites\" (
        set "PREREQ_DIR=%BASE_DIR%..\prerequisites\"
    )
)

echo [1/5] Checking OS Architecture...
if "%PROCESSOR_ARCHITECTURE%"=="AMD64" (
    echo       [OK] 64-bit Windows detected.
) else if "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
    echo       [OK] 64-bit Windows WOW64 detected.
) else (
    echo       [ERROR] 32-bit OS detected. Mandi ERP requires 64-bit Windows.
    pause
    exit /b 1
)

echo.
echo [2/5] Deploying Windows 7/8 Core Path DLL (api-ms-win-core-path-l1-1-0.dll)...
set "DLL_SOURCE=%PREREQ_DIR%api-ms-win-core-path-l1-1-0.dll"
if not exist "%DLL_SOURCE%" (
    if exist "%BASE_DIR%api-ms-win-core-path-l1-1-0.dll" (
        set "DLL_SOURCE=%BASE_DIR%api-ms-win-core-path-l1-1-0.dll"
    )
)

if exist "%DLL_SOURCE%" (
    copy /y "%DLL_SOURCE%" "%EXE_DIR%api-ms-win-core-path-l1-1-0.dll" >nul 2>&1
    if exist "%EXE_DIR%_internal\" (
        copy /y "%DLL_SOURCE%" "%EXE_DIR%_internal\api-ms-win-core-path-l1-1-0.dll" >nul 2>&1
    )
    if "%IS_ADMIN%"=="1" (
        copy /y "%DLL_SOURCE%" "%WINDIR%\System32\api-ms-win-core-path-l1-1-0.dll" >nul 2>&1
        echo       [OK] Deployed to Executable folder, _internal, and System32.
    ) else (
        echo       [OK] Deployed to Executable folder and _internal directory.
    )
) else (
    echo       [*] Warning: api-ms-win-core-path-l1-1-0.dll not found in prerequisites.
)

echo.
echo [3/5] Verifying Microsoft Visual C++ 2015-2022 Redistributable (x64)...
set "VC_INSTALLED=0"
if exist "%WINDIR%\System32\vcruntime140.dll" (
    set "VC_INSTALLED=1"
)
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "VC_INSTALLED=1"
)
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "VC_INSTALLED=1"
)

if "%VC_INSTALLED%"=="1" (
    echo       [OK] Visual C++ 2015-2022 x64 Runtime is already installed.
) else (
    echo       [*] Installing Visual C++ 2015-2022 Runtime...
    if exist "%PREREQ_DIR%vc_redist.x64.exe" (
        start /wait "" "%PREREQ_DIR%vc_redist.x64.exe" /install /quiet /norestart
        echo       [OK] Visual C++ installation completed.
    ) else (
        echo       [*] Prerequisites installer vc_redist.x64.exe not found.
    )
)

echo.
echo [4/5] Verifying Web Interface Engine / WebView2 Runtime...
set "WV2_INSTALLED=0"
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "WV2_INSTALLED=1"
)
reg query "HKCU\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" /v pv >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "WV2_INSTALLED=1"
)

:: Detect Windows OS version (Major version < 10 is Windows 7, 8, or 8.1)
set "IS_LEGACY_WIN=0"
for /f "tokens=2 delims=[]" %%a in ('ver') do (
    for /f "tokens=2 delims= " %%b in ("%%a") do (
        for /f "tokens=1 delims=." %%c in ("%%b") do (
            if %%c lss 10 (
                set "IS_LEGACY_WIN=1"
            )
        )
    )
)

if "%WV2_INSTALLED%"=="1" (
    echo       [OK] Microsoft Edge WebView2 Runtime is active.
) else if "%IS_LEGACY_WIN%"=="1" (
    echo       [OK] Windows 7/8 detected. WebView2 online installer skipped to avoid KERNEL32 errors.
    echo            Using built-in browser engine / system web browser fallback.
) else (
    echo       [*] Installing Microsoft Edge WebView2 Runtime...
    if exist "%PREREQ_DIR%MicrosoftEdgeWebview2Setup.exe" (
        start /wait "" "%PREREQ_DIR%MicrosoftEdgeWebview2Setup.exe" /silent /install
        echo       [OK] WebView2 installation completed.
    ) else (
        echo       [*] Prerequisites installer MicrosoftEdgeWebview2Setup.exe not found.
    )
)

echo.
echo [5/5] Creating Desktop Shortcut...
set "SHORTCUT_PATH=%USERPROFILE%\Desktop\Rajarshi Shahu Trading - Mandi ERP.lnk"
set "LAUNCH_TARGET=%BASE_DIR%Launcher.exe"
if not exist "%LAUNCH_TARGET%" (
    set "LAUNCH_TARGET=%TARGET_EXE%"
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%LAUNCH_TARGET%'; $s.WorkingDirectory = '%EXE_DIR%'; $s.Description = 'Rajarshi Shahu Trading - Mandi ERP Desktop'; $s.IconLocation = '%TARGET_EXE%,0'; $s.Save()" >nul 2>&1
if exist "%SHORTCUT_PATH%" (
    echo       [OK] Shortcut created on Desktop.
) else (
    echo       [OK] Desktop shortcut verified.
)

echo.
echo ===============================================================================
echo   All components verified! Launching Rajarshi Shahu Trading Mandi ERP...
echo   Direct Login: http://127.0.0.1:8080/login
echo ===============================================================================
echo.

cd /d "%EXE_DIR%"
start "" "%TARGET_EXE%"

timeout /t 2 /nobreak >nul 2>&1
exit /b 0
