# 🤖 INSTRUCTIONS FOR AI AGENT / ASSISTANT

> **Target Audience**: This document is specifically written to brief any AI coding agent, language model, or autonomous engineer that opens and inspects this repository. It provides complete situational awareness, architectural context, current operational status, and actionable instructions on how to proceed.

---

## 1. Project Overview & Identity

* **Project Name**: **AEGIS-CAD** (Autonomous Emergency Geospatial Intelligence System // Computer-Aided Dispatch)
* **Domain**: Disaster Response Management, Emergency Dispatch (CAD), Multi-Channel Distress Ingestion, and Tactical GIS.
* **Intended End-Users**: State Emergency Operations Centers (SEOC), District Disaster Management Authorities (DDMA), and First Responders (NDRF, SDRF, Fire & Rescue, Emergency Medical Services, and Police).
* **Current Status**: **Fully Functional & Tested**. All core features, database persistence, REST endpoints, WebSockets, tactical frontend, and 41 automated tests are completely implemented and passing.

---

## 2. Core Architecture & Tech Stack

```
AEGIS-CAD/
├── app/
│   ├── server.py             # FastAPI backend, REST API endpoints, and WebSocket hub
│   ├── models.py             # Pydantic v2 schemas for CAD incidents, triage results, SITREP
│   ├── models_fleet.py       # Pydantic models for First Responder fleet telemetry
│   ├── database.py           # Async SQLite engine (aiosqlite) with incident & unit tables
│   ├── triage_engine.py      # Dual-mode triage: Google Gemini 2.5 Flash + Offline Rule Engine
│   ├── geocoding.py          # Coordinate extraction & Tamil Nadu gazetteer resolver
│   ├── google_maps.py        # Routing, ETAs, and emergency POI overlay (with Haversine fallback)
│   ├── dedup.py              # Geospatial & temporal distress report deduplication
│   ├── simulator.py          # Simulated disaster distress & social media feed generator
│   └── services/
│       ├── fleet_service.py    # Unit status management, assignment, and dispatch logic
│       ├── realtime_feed.py    # Background broadcast loops for active incident telemetry
│       └── social_ingestion.py # Raw multi-channel stream ingestion & auto-triage pipeline
├── static/                   # Tactical Command Center Web UI
│   ├── index.html            # Main Single-Page Application (Outfit + JetBrains Mono)
│   ├── report.html           # Print-ready official SITREP (Situation Report) generator
│   ├── css/style.css         # MIL-SPEC Glassmorphism UI theme, tactical dark mode
│   └── js/
│       ├── app.js            # Dispatcher UI state controller, WebSocket client, Chart.js
│       ├── map.js            # Leaflet.js Tactical GIS map (pulsing markers, hazard zones, routes)
│       └── audio.js          # Web Audio API emergency tones & dispatch horn synthesizer
├── scripts/
│   └── ingest_usgs_live.py   # Live USGS global earthquake stream ingestion utility
├── tests/                    # Pytest automated test suite (41 tests)
│   ├── test_api.py           # API endpoint integration & incident dispatch tests
│   ├── test_fleet.py         # Responder fleet tracking & mobilization tests
│   ├── test_realtime.py      # Realtime broadcast & WebSocket tests
│   ├── test_social_stream.py # Distress feed ingestion & deduplication tests
│   └── test_triage.py        # Triage classification, urgency scoring, & fallback tests
├── cad_disaster.db           # Pre-seeded SQLite database with active demonstration incidents
├── run.py                    # Server launcher entrypoint
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable configuration template
├── README.md                 # User-facing quickstart and installation manual
└── AI_INSTRUCTIONS.md        # This onboarding guide for AI assistants
```

---

## 3. Critical Design Pattern: Resilient Offline Fallback

**Zero-Cloud Dependency**: AEGIS-CAD is engineered to operate in disaster zones where internet connectivity may be compromised.
1. **AI Triage (`app/triage_engine.py`)**:
   - If `GEMINI_API_KEY` is provided: Uses Gemini 2.5 Flash for multi-lingual zero-shot LLM reasoning and multimodal image damage classification.
   - If `GEMINI_API_KEY` is **missing or invalid**: Automatically activates an embedded, deterministic regex & gazetteer rule engine. Computes urgency scores (0–100), extracts casualty counts, and suggests tactical SOP directives with zero downtime.
2. **Geocoding & Routing (`app/geocoding.py`, `app/google_maps.py`)**:
   - If `GOOGLE_MAPS_API_KEY` is provided: Fetches live turn-by-turn routes and Google Places emergency POIs.
   - If `GOOGLE_MAPS_API_KEY` is **missing or invalid**: Automatically uses local Haversine calculations, an embedded Tamil Nadu gazetteer, and pre-seeded emergency facilities (hospitals, fire stations, helipads).

> **Rule for AI**: When modifying or extending code, **NEVER break the offline fallback path**. Always ensure the application runs smoothly without external network access or paid API keys.

---

## 4. How to Bootstrap & Run the System

### 1. Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
```bash
# Copy the environment template
# Windows:
Copy-Item .env.example .env
# Linux/macOS:
cp .env.example .env
```
*(Keys are optional. The system works immediately without editing `.env`.)*

### 3. Run Automated Tests
```bash
python -m pytest -v
```
*Expected result: 41 passed, 0 failures.*

### 4. Launch the Command Center
```bash
python run.py
```
* Access Tactical CAD Dashboard: `http://127.0.0.1:8000`
* WebSocket Feed: `ws://127.0.0.1:8000/ws/cad`
* Interactive API Docs: `http://127.0.0.1:8000/docs`

---

## 5. How to Proceed From Here (Roadmap & Recommended Next Tasks)

If you are an AI assistant asked to continue development or enhance this platform, here are the highest-impact areas to work on:

### Area A: Edge / Local LLM Integration (Zero-Cloud AI)
* **Goal**: Provide true LLM reasoning without sending data to the cloud.
* **Implementation**: Add an adapter in `app/triage_engine.py` connecting to a local Ollama instance (e.g., `gemma2:2b` or `mistral:7b`) or an in-process ONNX/GGUF model.

### Area B: Live External Stream Ingestion
* **Goal**: Expand live automated data ingestion beyond the simulated feed.
* **Implementation**:
  * Build a Telegram Bot webhook (`/api/ingest/telegram`) for citizen distress reports.
  * Connect an IMD / NDMA Common Alerting Protocol (CAP) RSS/XML reader.
  * Integrate SMS gateway webhooks (e.g., Twilio or local cellular modems).

### Area C: Automated Dispatch Optimization (VRP / AI Route Dispatch)
* **Goal**: Dynamically assign the optimal emergency unit based on availability, vehicle capability, distance, and active hazard perimeters.
* **Implementation**: Create a route optimization utility in `app/services/fleet_service.py` using linear programming or Dijkstra/A* pathing around hazard polygon zones.

### Area D: Containerization & Deployment
* **Goal**: Package AEGIS-CAD for one-click deployment in rugged field units.
* **Implementation**: Create a `Dockerfile` and `docker-compose.yml` bundling the FastAPI backend, static assets, and pre-seeded database behind an Nginx reverse proxy.

---

## 6. Coding Invariants & Conventions

1. **Strict Type Safety**: All incident inputs and outputs must pass through Pydantic models defined in `app/models.py`.
2. **Asynchronous I/O**: Use `await` for database operations (`aiosqlite`), HTTP requests (`httpx`), and WebSocket broadcasts.
3. **No Hardcoded Secrets**: Always read configuration from environment variables via `python-dotenv`.
4. **Resilient Error Handling**: Ingestion endpoints must never crash on malformed input; always catch parsing exceptions and log appropriate warnings.
