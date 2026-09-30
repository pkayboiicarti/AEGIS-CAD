# 🚨 AEGIS-CAD - AI-Powered Disaster Ingestion & Triage Command Center

**AEGIS-CAD** is an emergency Computer-Aided Dispatch (CAD) and Disaster Distress Ingestion platform built for Smart India Hackathon (SIH), State Emergency Operations Centers (SEOC), and First Responders (NDRF, Fire & Rescue, SDRF, EMS, and Police).

---

## ⚡ Core Capabilities

1. **Multi-Channel Distress Ingestion**
   - Ingests unstructured streams from social media (X/Twitter, Telegram), Citizen SOS Apps, SMS, and 911/112 Emergency Call Audio transcripts.
   
2. **AI Triage & Noise Filtering Engine**
   - Powered by Google Gemini (`google-genai`) with an embedded deterministic heuristic fallback engine.
   - Strictly enforces the CAD schema:
     - **Relevance Filtering**: Automatically discards spam, prayers, past news, and non-emergency banter.
     - **Classification**: `INDUSTRIAL`, `FIRE`, `FLOOD`, `EARTHQUAKE`, `CYCLONE`, `STRUCTURAL_COLLAPSE`, `OTHER`.
     - **Urgency Scoring**: Integer scale ($0\text{--}100$) dynamically weighted by threat to human life and trapped citizen counts.
     - **Casualty Estimation**: Counts for injured, trapped, evacuated, and total estimated victims.
     - **Actionable Notes**: Immediate hazards, tactical equipment requirements, and perimeter advice.

3. **Interactive Tactical GIS Command Map**
   - Dark-mode tactical Leaflet GIS map with custom animated pulsing severity pins (`CRITICAL`, `HIGH`, `MODERATE`, `LOW`).
   - Hazard radius zones (e.g., ammonia plume perimeter, flood inundation).
   - Real-time Responder Unit tracking with active dispatch route lines.

4. **CAD Dispatcher Triage Matrix & Situation Room**
   - Real-time CAD dispatch board sorted by Urgency Score.
   - 1-Click Responder Mobilization (NDRF Battalions, Heavy Skylift Fire Engines, ALS Ambulances, Flood Boats).
   - Live telemetry charts (Chart.js) and one-click exportable **SITREP** (Situation Report) for District Authorities / DDMA.

---

## 🏗️ System Architecture

```
Code/
├── app/
│   ├── __init__.py
│   ├── models.py           # Strict Pydantic models for CAD schema and telemetry
│   ├── database.py         # Async SQLite DB for incidents, units, and audit logs
│   ├── triage_engine.py    # AI Ingestion Engine (Gemini 2.5 Flash + Heuristic Fallback)
│   ├── geocoding.py        # Tactical gazetteer and GPS coordinate resolver
│   ├── simulator.py        # Multi-scenario disaster & noise feed generator
│   └── server.py           # FastAPI server with WebSocket broadcast hub
├── static/
│   ├── index.html          # Modern Tactical Command Center UI (Outfit + JetBrains Mono)
│   ├── css/
│   │   └── style.css       # MIL-SPEC Glassmorphism CAD theme & glow aesthetics
│   └── js/
│       ├── audio.js        # Web Audio API emergency siren & dispatch tone synthesizer
│       ├── map.js          # Leaflet GIS Tactical Map controller
│       └── app.js          # Main CAD controller, WebSockets, Charts & Dispatch modals
├── tests/
│   ├── test_triage.py      # Triage schema & heuristic validation tests
│   └── test_api.py         # REST API & integration tests
├── run.py                  # Server entrypoint launcher
├── requirements.txt        # Python dependencies
└── README.md
```

---

## 🚀 Setup & Quickstart Guide

### Prerequisites
* **Python**: Python 3.10, 3.11, or 3.12+ (tested up to Python 3.14)
* **OS**: Windows, macOS, or Linux
* **Browser**: Modern web browser (Chrome, Edge, Firefox)

---

### Step 1: Create and Activate a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS / Git Bash:**
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 3: Configure Environment Variables

Create your local `.env` file from the provided template:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

Edit `.env` if you wish to provide optional cloud API keys:
```env
# Optional: Google Gemini API Key for Zero-Shot LLM Triage & Vision Analysis
# Obtain at: https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Google Maps API Key for Live Turn-by-Turn Routing & Dynamic POI Overlays
# Obtain at: https://console.cloud.google.com/google/maps-apis
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# Server Bindings
HOST=127.0.0.1
PORT=8000
```

> [!TIP]
> **Zero-Cloud Offline Fallback (No Keys Needed!):**  
> If neither API key is provided, **AEGIS-CAD functions 100% locally with zero downtime**:
> - **Triage Engine**: Automatically falls back to an embedded high-speed deterministic regex & gazetteer rule engine with distress scoring and casualty estimation.
> - **Routing & GIS**: Automatically falls back to the pre-seeded Tamil Nadu spatial gazetteer, local Haversine calculations, and pre-seeded emergency POIs (hospitals, fire stations, helipads).

---

### Step 4: Run the Command Center Server

```bash
python run.py
```

Once the terminal outputs `[*] Launching on: http://0.0.0.0:8000`, open your browser:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

### Step 5: Run Automated Tests

To verify schema validation, heuristic fallback triage, fleet dispatch, and REST API endpoints:
```bash
python -m pytest -v
```
All 41 tests execute without requiring any external internet connectivity or live API keys.

---

## 📡 CAD API Endpoints

- `POST /api/ingest`: Ingest raw crowdsourced/social message, run AI triage, save, and broadcast to dispatchers.
- `GET /api/incidents`: Filter incidents by `status`, `severity`, `disaster_type`, or keyword search.
- `GET /api/incidents/{id}`: Detailed incident telemetry and assigned first responder units.
- `POST /api/incidents/{id}/dispatch`: Dispatch responder units (`NDRF`, `FIRE`, `EMS`, etc.) to scene.
- `POST /api/incidents/{id}/status`: Transition incident operational status (`PENDING`, `TRIAGED`, `DISPATCHED`, `ON_SCENE`, `RESOLVED`).
- `GET /api/units`: List all emergency responder units and their status.
- `GET /api/stats`: Real-time aggregate statistics (trapped citizens, active critical incidents, units ready).
- `POST /api/simulate/feed`: Trigger a simulated live emergency stream.
- `GET /api/export/sitrep`: Export formatted Markdown Situation Report for Disaster Authorities.
- `WS /ws/cad`: Real-time WebSocket connection for live CAD dispatcher terminals.
