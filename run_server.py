#!/usr/bin/env python3
"""UEBA FastAPI Server Launcher - Auto-opens browser"""

import subprocess
import time
import webbrowser
import threading
import sys
import os

def open_browser():
    """Open browser after server starts"""
    time.sleep(3)  # Wait for server startup
    webbrowser.open("http://127.0.0.1:8000/docs")
    print("\n🚀 Browser opened: http://127.0.0.1:8000/docs")
    print("📱 Test signup/login in Swagger UI")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    python_exe = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = "python"
        
    cmd = f'"{python_exe}" -m uvicorn app.main:app --host {host} --port {port}'
    
    print(f"🔧 Starting UEBA Security Server on {host}:{port}...")
    
    if os.getenv("OPEN_BROWSER", "false").lower() == "true":
        threading.Timer(2.0, open_browser).start()
        
    os.system(cmd)


