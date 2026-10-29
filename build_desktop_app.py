import os
import sys
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))
pyinstaller_exe = os.path.expandvars(r"%LOCALAPPDATA%\Python\pythoncore-3.14-64\Scripts\pyinstaller.exe")
if not os.path.exists(pyinstaller_exe):
    pyinstaller_exe = "pyinstaller"

cmd = [
    pyinstaller_exe,
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
    "--hidden-import", "clr",
    "--hidden-import", "clr_loader",
    "--hidden-import", "pythonnet",
    "--hidden-import", "webview.platforms.winforms",
    "--hidden-import", "sqlite3",
    "--hidden-import", "jinja2",
    "--hidden-import", "database",
    "--hidden-import", "calculations",
    "--hidden-import", "server",
    os.path.join(current_dir, "desktop_app.py")
]

print("Executing command:")
print(" ".join(cmd))
res = subprocess.run(cmd, cwd=current_dir)
sys.exit(res.returncode)
