"""
Rajeshri Shahu Trading — Mandi ERP Desktop Application Launcher
Packages local FastAPI Mandi server with a dedicated standalone native desktop window.
"""

import sys
import os
import time
import threading
import subprocess
import webbrowser
import socket
import urllib.request

APP_TITLE = "Rajeshri Shahu Trading — Mandi ERP"
PORT = 8080
TARGET_URL = f"http://127.0.0.1:{PORT}"

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def wait_for_server(url, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False

def start_server():
    # Import and run server inside thread if not already running
    import uvicorn
    from server import app
    print(f"Starting embedded Mandi ERP server on port {PORT}...")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")

def launch_native_window(url):
    # Try Chrome App Mode first (looks like native desktop application without URL bar)
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
    ]
    for cp in chrome_paths:
        if os.path.exists(cp):
            try:
                subprocess.Popen([cp, f"--app={url}", "--window-size=1366,850"])
                return
            except Exception:
                pass

    # Try Edge App Mode (default on all Windows 10/11 PCs)
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe")
    ]
    for ep in edge_paths:
        if os.path.exists(ep):
            try:
                subprocess.Popen([ep, f"--app={url}", "--window-size=1366,850"])
                return
            except Exception:
                pass

    # Fallback to system default browser
    webbrowser.open(url)

def main():
    print("=" * 60)
    print("  " + APP_TITLE)
    print("  Enterprise Multi-Branch Mandi & Commodity Procurement ERP")
    print("=" * 60)

    if not is_port_in_use(PORT):
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        print("Waiting for local Mandi engine to initialize...")
        if not wait_for_server(TARGET_URL):
            print("Server took longer than expected to start. Launching window anyway...")
    else:
        print(f"Mandi ERP engine is already active on port {PORT}.")

    print(f"Opening native application window ({TARGET_URL})...")
    launch_native_window(TARGET_URL)

    # Keep background process alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Closing Mandi ERP...")

if __name__ == "__main__":
    main()
