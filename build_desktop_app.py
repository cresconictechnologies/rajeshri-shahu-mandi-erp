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
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols",
    "--hidden-import", "uvicorn.protocols.http",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.lifespan",
    "--hidden-import", "uvicorn.lifespan.on",
    os.path.join(current_dir, "desktop_app.py")
]

print("Executing command:")
print(" ".join(cmd))
res = subprocess.run(cmd, cwd=current_dir)
sys.exit(res.returncode)
