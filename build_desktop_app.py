import os
import sys
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "Rajarshi_Shahu_Trading",
    "--add-data", f"{os.path.join(current_dir, 'templates')};templates",
    "--add-data", f"{os.path.join(current_dir, 'static')};static",
    "--add-data", f"{os.path.join(current_dir, 'commodity_mandi.db')};.",
    "--add-binary", f"{os.path.join(current_dir, 'api-ms-win-core-path-l1-1-0.dll')};.",
    "--add-binary", f"{os.path.join(current_dir, 'api-ms-win-core-path-l1-1-0.dll')};_internal",
    "--collect-all", "webview",
    "--collect-all", "uvicorn",
    "--collect-all", "fastapi",
    "--collect-all", "starlette",
    "--collect-all", "PIL",
    "--collect-all", "numpy",
    "--collect-all", "requests",
    "--collect-all", "urllib3",
    "--collect-all", "multipart",
    "--exclude-module", "vendor_license_issuer",
    "--hidden-import", "clr",
    "--hidden-import", "clr_loader",
    "--hidden-import", "pythonnet",
    "--hidden-import", "webview.platforms.winforms",
    "--hidden-import", "sqlite3",
    "--hidden-import", "jinja2",
    "--hidden-import", "database",
    "--hidden-import", "calculations",
    "--hidden-import", "quality_engine",
    "--hidden-import", "licensing",
    "--hidden-import", "cryptography",
    "--hidden-import", "PIL",
    "--hidden-import", "numpy",
    "--hidden-import", "scipy",
    "--hidden-import", "scipy.ndimage",
    "--hidden-import", "supabase_sync",
    "--hidden-import", "httpx",
    "--hidden-import", "requests",
    "--hidden-import", "multipart",
    "--hidden-import", "sqlalchemy",
    "--hidden-import", "server",
    os.path.join(current_dir, "desktop_app.py")
]

print("Executing command:")
print(" ".join(cmd))
res = subprocess.run(cmd, cwd=current_dir)
if res.returncode == 0:
    import shutil
    dist_dir = os.path.join(current_dir, "dist", "Rajarshi_Shahu_Trading")
    
    # Copy Launcher, batch scripts, and prerequisites into dist folder
    launcher_src = os.path.join(current_dir, "Launcher.exe")
    if os.path.exists(launcher_src):
        shutil.copy2(launcher_src, os.path.join(dist_dir, "Launcher.exe"))
        print("Bundled Launcher.exe")

    bat_src = os.path.join(current_dir, "Setup_and_Launch.bat")
    if os.path.exists(bat_src):
        shutil.copy2(bat_src, os.path.join(dist_dir, "Setup_and_Launch.bat"))
        print("Bundled Setup_and_Launch.bat")

    dll_src = os.path.join(current_dir, "api-ms-win-core-path-l1-1-0.dll")
    if os.path.exists(dll_src):
        shutil.copy2(dll_src, os.path.join(dist_dir, "api-ms-win-core-path-l1-1-0.dll"))
        internal_dir = os.path.join(dist_dir, "_internal")
        if os.path.exists(internal_dir):
            shutil.copy2(dll_src, os.path.join(internal_dir, "api-ms-win-core-path-l1-1-0.dll"))
        print("Bundled Win7 core path DLL")

    db_src = os.path.join(current_dir, "commodity_mandi.db")
    if os.path.exists(db_src):
        shutil.copy2(db_src, os.path.join(dist_dir, "commodity_mandi.db"))
        print("Bundled pre-seeded commodity_mandi.db into dist folder")

    prereq_src = os.path.join(current_dir, "prerequisites")
    prereq_dst = os.path.join(dist_dir, "prerequisites")
    if os.path.exists(prereq_src):
        if os.path.exists(prereq_dst):
            shutil.rmtree(prereq_dst)
        shutil.copytree(prereq_src, prereq_dst)
        print("Bundled prerequisites folder (VC++ Redist, WebView2, Win7 DLL)")

    zip_target = os.path.join(current_dir, "dist", "Rajarshi_Shahu_Trading_Windows_x64")
    print(f"Creating release archive: {zip_target}.zip ...")
    shutil.make_archive(zip_target, "zip", dist_dir)
    print(f"Successfully packaged: {zip_target}.zip")

    tracker_candidates = [
        os.path.join(current_dir, "mandi-erp-tracker", "Rajarshi_Shahu_Trading_Windows_x64.zip"),
        os.path.abspath(os.path.join(current_dir, "..", "mandi-erp-tracker", "Rajarshi_Shahu_Trading_Windows_x64.zip"))
    ]
    for tracker_zip in tracker_candidates:
        if os.path.exists(os.path.dirname(tracker_zip)):
            shutil.copy2(f"{zip_target}.zip", tracker_zip)
            print(f"Updated portal zip: {tracker_zip}")
sys.exit(res.returncode)
