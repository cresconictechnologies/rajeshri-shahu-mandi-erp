"""
Rajarshi Shahu Trading — Mandi ERP Desktop Application Launcher (Powered by Cresconic)
Runs embedded Uvicorn server in background thread and presents
a 100% native standalone Windows GUI window via pywebview (WebView2).
Zero external Chrome or browser popups.
"""

import sys
import os
import time
import threading
import socket
import urllib.request
import traceback
import multiprocessing
import ctypes
import webview

APP_TITLE = "Rajarshi Shahu Trading — Mandi ERP (Powered by Cresconic)"
PORT = 8080
TARGET_URL = f"http://127.0.0.1:{PORT}"

# Determine app directory for persistent logs and database
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_FILE = os.path.join(APP_DIR, "desktop_startup.log")

def log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def show_error(title: str, message: str):
    log(f"ERROR DIALOG: {title} - {message}")
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        pass

def is_server_responding(url: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MandiERPDesktop/1.0"})
        with urllib.request.urlopen(req, timeout=1.5) as response:
            return response.status in (200, 302, 303, 307)
    except Exception:
        return False

def wait_for_server(url: str, timeout: float = 20.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if is_server_responding(url):
            return True
        time.sleep(0.25)
    return False

def start_server():
    try:
        log("Importing uvicorn and server.app...")
        import uvicorn
        from server import app
        log(f"Configuring embedded Mandi ERP engine on 0.0.0.0:{PORT} (Local & Yard Wi-Fi)...")
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=PORT,
            log_level="warning",
            loop="asyncio",
            lifespan="on",
            access_log=False
        )
        server = uvicorn.Server(config)
        log("Embedded server loop starting...")
        server.run()
        log("Embedded server loop terminated.")
    except Exception:
        err = traceback.format_exc()
        log(f"CRITICAL ERROR inside start_server: {err}")

def on_closed():
    log("Main window closed by user. Terminating Mandi ERP.")
    os._exit(0)

def main():
    log(f"Starting {APP_TITLE}. Frozen={getattr(sys, 'frozen', False)}, Executable={sys.executable}")

    # 1. Start embedded engine if port not responding
    if not is_server_responding(TARGET_URL):
        log(f"Starting embedded backend server on port {PORT}...")
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        
        log(f"Waiting for backend engine to become ready ({TARGET_URL})...")
        if not wait_for_server(TARGET_URL, timeout=20.0):
            err_msg = (
                "The local Mandi ERP engine failed to respond within 20 seconds.\n\n"
                f"Please check '{LOG_FILE}' for technical diagnostic details."
            )
            show_error("Startup Error — Mandi ERP", err_msg)
            sys.exit(1)
        log("Backend engine is ready and responding.")
    else:
        log(f"Mandi ERP engine is already running and responding on port {PORT}.")

    # 2. Launch true native desktop window
    log(f"Creating native desktop window pointing to {TARGET_URL}...")
    webview.settings['ALLOW_DOWNLOADS'] = True
    webview.settings['ALLOW_FILE_URLS'] = True

    window = webview.create_window(
        title=APP_TITLE,
        url=TARGET_URL,
        width=1366,
        height=850,
        min_size=(1024, 680),
        confirm_close=False,
        text_select=True,
        zoomable=True
    )
    window.events.closed += on_closed

    try:
        log("Starting native Edge WebView2 runtime...")
        webview.start(gui="edgechromium")
    except Exception as e:
        log(f"Native WebView2 start failed: {e}. Trying default GUI...")
        try:
            webview.start()
        except Exception as e2:
            log(f"Fatal GUI launch error: {e2}")
            show_error("GUI Error", f"Unable to display application window:\n{e2}")
            sys.exit(1)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
