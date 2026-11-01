import os
import sys
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "Rajeshri_Shahu_Mandi_ERP",
    "--add-data", f"{os.path.join(current_dir, 'templates')};templates",
    "--add-data", f"{os.path.join(current_dir, 'static')};static",
    "--add-data", f"{os.path.join(current_dir, 'commodity_mandi.db')};.",
    "--collect-all", "webview",
    "--collect-all", "uvicorn",
    "--collect-all", "fastapi",
    "--collect-all", "starlette",
    "--collect-all", "PIL",
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
    "--hidden-import", "server",
    os.path.join(current_dir, "desktop_app.py")
]

print("Executing command:")
print(" ".join(cmd))
res = subprocess.run(cmd, cwd=current_dir)
if res.returncode == 0:
    import shutil
    dist_dir = os.path.join(current_dir, "dist", "Rajeshri_Shahu_Mandi_ERP")
    zip_target = os.path.join(current_dir, "dist", "Rajeshri_Shahu_Mandi_ERP_v2.6_Windows_x64")
    print(f"Creating release archive: {zip_target}.zip ...")
    shutil.make_archive(zip_target, "zip", dist_dir)
    print(f"Successfully packaged: {zip_target}.zip")
sys.exit(res.returncode)
