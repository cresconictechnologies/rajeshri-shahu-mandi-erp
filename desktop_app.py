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
TARGET_URL = f"http://127.0.0.1:{PORT}/login"
CLOUD_URL = os.environ.get("MANDI_CLOUD_URL", "https://mandi-erp-tracker.vercel.app")
server_error = None

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
    # 1. Fast socket probe first to avoid Windows IE proxy resolution delay on Windows 7
    try:
        with socket.create_connection(('127.0.0.1', PORT), timeout=0.5):
            pass
    except Exception:
        return False

    # 2. HTTP probe using explicit empty proxy handler to bypass Windows 7 system proxy delay
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(url, headers={"User-Agent": "MandiERPDesktop/1.0"})
        with opener.open(req, timeout=1.5) as response:
            return response.status in (200, 302, 303, 307)
    except Exception:
        # If socket connection succeeded, server is bound and accepting TCP connections
        return True

def wait_for_server(url: str, timeout: float = 60.0, server_thread: threading.Thread = None) -> bool:
    start = time.time()
    last_log = start
    while time.time() - start < timeout:
        if server_error:
            log(f"Server thread encountered fatal startup error: {server_error}")
            return False
        if server_thread and not server_thread.is_alive():
            log("Server thread terminated prematurely during startup.")
            return False
        if is_server_responding(url):
            return True
        now = time.time()
        if now - last_log >= 5.0:
            elapsed = int(now - start)
            log(f"Waiting for backend engine to become ready ({elapsed}s / {int(timeout)}s elapsed)...")
            last_log = now
        time.sleep(0.3)
    return False

def start_server():
    global server_error
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
        server_error = traceback.format_exc()
        log(f"CRITICAL ERROR inside start_server:\n{server_error}")

def on_closed():
    log("Main window closed by user. Terminating Mandi ERP.")
    os._exit(0)

def main():
    log(f"Starting {APP_TITLE}. Frozen={getattr(sys, 'frozen', False)}, Executable={sys.executable}")

    # Check for Cloud Mode switch
    cloud_mode = "--cloud" in sys.argv or os.environ.get("MANDI_CLOUD_MODE", "0") == "1"
    target_url = CLOUD_URL if cloud_mode else TARGET_URL

    if cloud_mode:
        log(f"Cloud-Only Mode requested. Pointing GUI directly to live Cloud Web App: {target_url}")
    else:
        # 1. Start embedded engine if port not responding
        if not is_server_responding(target_url):
            log(f"Starting embedded backend server on port {PORT}...")
            server_thread = threading.Thread(target=start_server, daemon=True)
            server_thread.start()
            
            log(f"Waiting for backend engine to become ready ({target_url}, timeout=60s)...")
            if not wait_for_server(target_url, timeout=60.0, server_thread=server_thread):
                detail = f"\n\nDiagnostic Error:\n{server_error}" if server_error else ""
                err_msg = (
                    f"The local Mandi ERP engine failed to respond within 60 seconds.{detail}\n\n"
                    f"Please check '{LOG_FILE}' for technical diagnostic details.\n\n"
                    f"Tip: You can also use the live Cloud Mandi ERP directly at:\n{CLOUD_URL}"
                )
                show_error("Startup Error — Mandi ERP", err_msg)
                sys.exit(1)
            log("Backend engine is ready and responding.")
        else:
            log(f"Mandi ERP engine is already running and responding on port {PORT}.")

    # 2. Launch true native desktop window
    log(f"Creating native desktop window pointing to {target_url}...")
    webview.settings['ALLOW_DOWNLOADS'] = True
    webview.settings['ALLOW_FILE_URLS'] = True

    window = webview.create_window(
        title=APP_TITLE if not cloud_mode else f"{APP_TITLE} (Cloud Portal)",
        url=target_url,
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
            log(f"Native GUI unavailable ({e2}). Launching in default web browser fallback...")
            try:
                import webbrowser
                webbrowser.open(target_url)
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Rajarshi Shahu Trading Mandi ERP is running in your web browser ({target_url}).\n\nKeep this dialog open while using the Mandi ERP system.\nClick OK when you want to stop the server.",
                    APP_TITLE,
                    0x40
                )
            except Exception:
                while True:
                    time.sleep(1)
            sys.exit(0)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
