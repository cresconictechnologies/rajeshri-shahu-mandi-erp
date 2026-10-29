"""
Rajeshri Shahu Trading — Mandi ERP Desktop Application Launcher
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
import webview

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
                if response.status in (200, 303, 307):
                    return True
        except Exception:
            time.sleep(0.3)
    return False

def start_server():
    import uvicorn
    from server import app
    print(f"Starting embedded Mandi ERP server on port {PORT}...")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")

def on_closed():
    print("Window closed by user. Terminating Mandi ERP desktop application.")
    os._exit(0)

def main():
    print("=" * 60)
    print("  " + APP_TITLE)
    print("  Standalone Multi-Branch Mandi & Commodity Procurement ERP")
    print("=" * 60)

    # 1. Start local embedded engine if not already active
    if not is_port_in_use(PORT):
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        print("Waiting for local Mandi engine to initialize...")
        wait_for_server(TARGET_URL)
    else:
        print(f"Mandi ERP engine is active on port {PORT}.")

    # 2. Launch true native desktop window (no Chrome, no external browser)
    print(f"Launching native application window ({TARGET_URL})...")
    
    # Configure webview settings
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
        # Uses Windows native Edge WebView2 runtime embedded in a native WinForms window
        webview.start(gui="edgechromium")
    except Exception as e:
        print(f"Native WebView2 start failed: {e}. Attempting default native gui...")
        try:
            webview.start()
        except Exception as e2:
            print(f"GUI launch error: {e2}")
            os._exit(1)

if __name__ == "__main__":
    main()
