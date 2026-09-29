import uvicorn
import os
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

if __name__ == "__main__":
    print("=" * 70)
    print("[*] AEGIS-CAD // AI Disaster Ingestion & Triage Command Center")
    print("[*] Launching on: http://0.0.0.0:8000 (Available on local network)")
    print("[*] WebSocket Feed: ws://0.0.0.0:8000/ws/cad")
    print("=" * 70)
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=False)
