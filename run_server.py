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
    print("\n📊 MySQL: mysql -u root -pPavitran820068 ueba_system -e 'SELECT * FROM users;'")

if __name__ == "__main__":
    # Activate venv and start uvicorn
    # Start uvicorn using the venv's python directly
    python_exe = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = "python" # Fallback
        
    cmd = f'"{python_exe}" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000'
    
    print(f"🔧 Starting UEBA FastAPI + MySQL Server using {python_exe}...")
    print("📂 .env loaded, models ready, tables auto-created")
    
    # Start browser timer
    threading.Timer(2.0, open_browser).start()
    
    # Run uvicorn
    os.system(cmd)

