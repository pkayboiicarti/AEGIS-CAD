import os
import re
import json
import uuid
import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, FileResponse
from dotenv import load_dotenv

load_dotenv()

from app.models import (
    IngestRequest, TriageResult, IncidentRecord,
    DispatchRequest, StatusUpdateRequest, SystemStats,
    VictimSubmitRequest, EmergencyStation, ResponseUnit,
    NearestDispatchRequest, POIItem, ImageAnalysisResult, ImageIngestRequest
)
from app.database import (
    init_db, save_incident, get_incidents, get_incident_by_id,
    dispatch_units_to_incident, update_incident_status, add_victim_to_incident,
    get_all_units, get_system_stats, get_all_audit_logs,
    get_all_stations, get_all_response_units, get_station_by_id,
    get_response_unit_by_id, update_response_unit_assignment, get_after_action_report, DB_PATH
)
from app.dedup import find_duplicate_incident, merge_duplicate_alert
from app.geocoding import resolve_location_coordinates, search_landmarks, is_within_tamil_nadu
from app.triage_engine import TriageEngine
from app.simulator import get_all_scenarios, get_random_scenario
import app.google_maps as google_maps
import app.services.fleet_service as fleet_service
from app.services.social_ingestion import SocialMediaIngestionWorker


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("cad.server")

triage_engine = TriageEngine()
social_worker = SocialMediaIngestionWorker(triage_engine)

# WebSocket Connection Manager for live CAD dispatch terminals
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"CAD Dispatcher Terminal connected. Active terminals: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"CAD Dispatcher Terminal disconnected. Active terminals: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error broadcasting to terminal: {e}")
                dead_connections.append(connection)
        for dc in dead_connections:
            self.disconnect(dc)

ws_manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing CAD Database and schema (Live Real-Time Mode)...")
    await init_db()
    social_worker.set_broadcast_callback(ws_manager.broadcast)
    if not os.getenv("VERCEL"):
    social_worker.start(interval_seconds=30)
    yield
    # Shutdown
    logger.info("Shutting down CAD server and social media ingestion worker.")
    social_worker.stop()

app = FastAPI(
    title="AEGIS-CAD Disaster Ingestion & Command Center",
    description="Real-Time Emergency Dispatch and Multi-Channel Disaster Distress Ingestion Engine",
    version="2.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoints

@app.post("/api/ingest")
async def ingest_message(req: IngestRequest):
    """
    Ingests raw crowdsourced message/transcript, runs AI Triage,
    saves incident to database, and broadcasts to live dispatchers.
    """
    triage_result = await triage_engine.triage_message(req.raw_message, req.metadata_or_coordinates)
    
    incident_record = None
    if triage_result.is_relevant and triage_result.incident:
        inc_data = triage_result.incident
        lat, lon = resolve_location_coordinates(inc_data.locationName, req.metadata_or_coordinates)
        
        # Step 2: Geospatial Deduplication (within 200m of active incident)
        dup_incident, dist_km = await find_duplicate_incident(lat, lon, inc_data.type, threshold_km=0.2)
        if dup_incident:
            merged_record = await merge_duplicate_alert(
                dup_incident,
                inc_data,
                req.raw_message,
                req.channel or "WEB_CAD"
            )
            # Emit live socket alerts for deduplicated SOS
            await ws_manager.broadcast({
                "event": "incident:sos_triggered",
                "incidentId": merged_record.id,
                "newSosCount": merged_record.sosAlertsCount,
                "incident": merged_record.model_dump()
            })
            await ws_manager.broadcast({
                "event": "INCIDENT_UPDATED",
                "incident": merged_record.model_dump()
            })
            stats = await get_system_stats()
            await ws_manager.broadcast({
                "event": "STATS_UPDATED",
                "stats": stats.model_dump()
            })
            return {
                "status": "MERGED",
                "merged": True,
                "distance_meters": round(dist_km * 1000, 1),
                "triage_result": triage_result.model_dump(),
                "incident_record": merged_record.model_dump()
            }

        within_tn = is_within_tamil_nadu(lat, lon)
        is_out_of_jurisdiction = not within_tn
        jurisdiction_warning = "Out of Jurisdiction (Tamil Nadu SEOC Only)" if is_out_of_jurisdiction else None

        incident_record = IncidentRecord(
            raw_text=req.raw_message,
            channel=req.channel or "WEB_CAD",
            metadata_info=req.metadata_or_coordinates,
            is_relevant=True,
            confidence_score=triage_result.confidence_score,
            is_out_of_jurisdiction=is_out_of_jurisdiction,
            jurisdiction_warning=jurisdiction_warning,
            title=inc_data.title,
            type=inc_data.type,
            severity=inc_data.severity,
            urgency_score=inc_data.urgencyScore,
            urgencyScore=inc_data.urgencyScore,
            location_name=inc_data.locationName,
            locationName=inc_data.locationName,
            latitude=lat,
            longitude=lon,
            coordinates={"lat": lat, "lng": lon},
            affectedPeople=inc_data.affectedPeople,
            affected_injured=inc_data.affectedPeople.injured,
            affected_trapped=inc_data.affectedPeople.trapped,
            affected_evacuated=inc_data.affectedPeople.evacuated,
            affected_total=inc_data.affectedPeople.totalEstimated,
            casualty_summary=inc_data.casualtySummary,
            actionable_notes=inc_data.actionableNotes,
            currentStatus="REPORTED",
            status="PENDING",
            sosAlertsCount=1,
            timeline=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "AUTO_INGESTED",
                "notes": f"Ingested via {req.channel or 'WEB_CAD'} channel" + (f" - ⚠️ {jurisdiction_warning}" if is_out_of_jurisdiction else "")
            }]
        )
        saved_record = await save_incident(incident_record)
        
        # Broadcast real-time update to all connected CAD consoles
        await ws_manager.broadcast({
            "event": "INCIDENT_INGESTED",
            "incident": saved_record.model_dump(),
            "triage": triage_result.model_dump()
        })
        
        return {
            "status": "SUCCESS",
            "merged": False,
            "triage_result": triage_result.model_dump(),
            "incident_record": saved_record.model_dump()
        }
    else:
        # Save discarded message for audit
        discarded_record = IncidentRecord(
            raw_text=req.raw_message,
            channel=req.channel or "WEB_CAD",
            metadata_info=req.metadata_or_coordinates,
            is_relevant=False,
            confidence_score=triage_result.confidence_score,
            rejection_reason=triage_result.rejection_reason,
            title="Discarded / Non-Emergency",
            currentStatus="RESOLVED",
            status="RESOLVED",
            timeline=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "FILTERED_OUT",
                "notes": triage_result.rejection_reason or "Non-emergency content"
            }]
        )
        await save_incident(discarded_record)
        
        await ws_manager.broadcast({
            "event": "MESSAGE_DISCARDED",
            "triage": triage_result.model_dump(),
            "raw_text": req.raw_message
        })
        
        return {
            "status": "DISCARDED",
            "triage_result": triage_result.model_dump(),
            "incident_record": None
        }

@app.post("/api/ingest/image")
async def ingest_image_endpoint(
    request: Request,
    file: Optional[UploadFile] = File(None),
    caption: Optional[str] = Form(None),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    location_name: Optional[str] = Form(None),
    channel: Optional[str] = Form("IMAGE_UPLOAD")
):
    """
    Multimodal Disaster Image Ingestion:
    Accepts multipart file uploads or JSON base64 images, executes AI vision triage,
    extracts visual evidence & damage severity, and creates/merges live CAD incident records.
    """
    image_bytes = None
    mime_type = "image/jpeg"
    extracted_caption = caption
    extracted_lat = lat
    extracted_lng = lng
    extracted_loc_name = location_name
    extracted_channel = channel or "IMAGE_UPLOAD"

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body = await request.json()
            b64_str = body.get("image_base64") or body.get("image") or ""
            extracted_caption = body.get("caption") or extracted_caption
            extracted_lat = body.get("latitude") or body.get("lat") or extracted_lat
            extracted_lng = body.get("longitude") or body.get("lng") or extracted_lng
            extracted_loc_name = body.get("location_name") or body.get("locationName") or extracted_loc_name
            extracted_channel = body.get("channel") or extracted_channel

            if b64_str:
                # Strip base64 header if present
                clean_b64 = re.sub(r"^data:image\/[a-zA-Z]+;base64,", "", b64_str)
                image_bytes = base64.b64decode(clean_b64)
        except Exception as e:
            logger.error(f"Error parsing JSON image payload: {e}")
    elif file:
        image_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"

    if not image_bytes:
        raise HTTPException(status_code=400, detail="No valid image file or base64 payload provided")

    # Run Multimodal AI Vision Analysis
    analysis: ImageAnalysisResult = await triage_engine.analyze_image(
        image_bytes=image_bytes,
        mime_type=mime_type,
        caption=extracted_caption
    )

    if not analysis.is_disaster_related or analysis.disaster_category == "NONE":
        await ws_manager.broadcast({
            "event": "IMAGE_DISCARDED",
            "analysis": analysis.model_dump(),
            "caption": extracted_caption
        })
        return {
            "status": "DISCARDED",
            "is_disaster_related": False,
            "analysis": analysis.model_dump(),
            "incident": None
        }

    # Map category to DisasterType
    type_map = {
        "FLOOD": "FLOOD",
        "FIRE": "FIRE",
        "STRUCTURAL_COLLAPSE": "STRUCTURAL_COLLAPSE",
        "INDUSTRIAL": "INDUSTRIAL",
        "ROAD_ACCIDENT": "OTHER",
        "NONE": "OTHER"
    }
    disaster_type = type_map.get(analysis.disaster_category, "OTHER")

    # Resolve Geocoding Coordinates
    if extracted_lat is not None and extracted_lng is not None:
        lat, lon = float(extracted_lat), float(extracted_lng)
    else:
        lat, lon = resolve_location_coordinates(extracted_loc_name or extracted_caption or "Chennai")

    resolved_loc_name = extracted_loc_name or "Chennai Emergency Zone"

    # Calculate urgency score based on visual damage assessment
    base_urgency = 75
    if analysis.damage_severity == "CRITICAL":
        base_urgency = 90
    elif analysis.damage_severity == "HIGH":
        base_urgency = 75
    elif analysis.damage_severity == "MODERATE":
        base_urgency = 50
    else:
        base_urgency = 30

    final_urgency = min(100, max(15, base_urgency + analysis.suggested_urgency_adjustment))

    now_iso = datetime.now(timezone.utc).isoformat()
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"

    # Check Deduplication
    dup_incident, dist_km = await find_duplicate_incident(lat, lon, disaster_type, threshold_km=0.2)
    if dup_incident:
        from app.models import CADIncidentData, AffectedPeople
        inc_data = CADIncidentData(
            title=f"Visual: {analysis.damage_severity} {analysis.disaster_category.replace('_', ' ').title()} - {resolved_loc_name}",
            type=disaster_type,
            severity=analysis.damage_severity,
            urgencyScore=final_urgency,
            locationName=resolved_loc_name,
            affectedPeople=AffectedPeople(injured=2, trapped=0, evacuated=0, totalEstimated=2),
            casualtySummary=f"Visual triage: {analysis.estimated_casualty_risk} risk. {analysis.synopsis}",
            actionableNotes="Visual evidence: " + "; ".join(analysis.visual_evidence)
        )
        merged = await merge_duplicate_alert(
            dup_incident,
            inc_data,
            extracted_caption or analysis.synopsis,
            extracted_channel
        )
        stats = await get_system_stats()
        await ws_manager.broadcast({
            "event": "INCIDENT_UPDATED",
            "incident": merged.model_dump(),
            "stats": stats.model_dump()
        })
        return {
            "status": "MERGED",
            "is_disaster_related": True,
            "analysis": analysis.model_dump(),
            "incident": merged.model_dump(),
            "incident_id": merged.id
        }

    incident_record = IncidentRecord(
        id=incident_id,
        created_at=now_iso,
        raw_text=extracted_caption or f"Visual Emergency Submission: {analysis.synopsis}",
        channel=extracted_channel,
        metadata_info=f"GPS: ({lat}, {lon}) | Visual Confidence: {int(analysis.confidence_score*100)}%",
        is_relevant=True,
        confidence_score=analysis.confidence_score,
        title=f"Visual Assessment: {analysis.damage_severity} {analysis.disaster_category.replace('_', ' ').title()} - {resolved_loc_name}",
        type=disaster_type,
        severity=analysis.damage_severity,
        urgency_score=final_urgency,
        urgencyScore=final_urgency,
        location_name=resolved_loc_name,
        locationName=resolved_loc_name,
        latitude=lat,
        longitude=lon,
        coordinates={"lat": lat, "lng": lon},
        affected_injured=2 if analysis.estimated_casualty_risk in ["EXTREME", "HIGH"] else 0,
        affected_trapped=3 if analysis.disaster_category == "STRUCTURAL_COLLAPSE" or (analysis.disaster_category == "FLOOD" and analysis.damage_severity == "CRITICAL") else 0,
        affected_evacuated=10 if analysis.disaster_category in ["FIRE", "INDUSTRIAL"] else 0,
        affected_total=5,
        casualty_summary=f"Visual triage: {analysis.estimated_casualty_risk} risk. {analysis.synopsis}",
        actionable_notes="Visual evidence confirmed: " + "; ".join(analysis.visual_evidence),
        status="PENDING",
        currentStatus="PENDING",
        timeline=[{
            "id": f"UP-{uuid.uuid4().hex[:6].upper()}",
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M UTC"),
            "iso_timestamp": now_iso,
            "action": "VISUAL_DAMAGE_INGESTED",
            "notes": f"Multimodal AI Vision classified {analysis.disaster_category} ({analysis.damage_severity}) with {len(analysis.visual_evidence)} evidence points."
        }]
    )


    saved = await save_incident(incident_record)
    stats = await get_system_stats()

    await ws_manager.broadcast({
        "event": "INCIDENT_INGESTED",
        "incident": saved.model_dump(),
        "analysis": analysis.model_dump(),
        "stats": stats.model_dump()
    })

    return {
        "status": "SUCCESS",
        "is_disaster_related": True,
        "analysis": analysis.model_dump(),
        "incident": saved.model_dump(),
        "incident_id": saved.id
    }


@app.post("/api/incidents")
async def create_or_ingest_incident(request: Request):
    """
    Dual-mode endpoint: Ingests raw text or directly creates a structured CAD incident.
    """
    body = await request.json()
    if "raw_message" in body or "text" in body:
        raw_msg = body.get("raw_message") or body.get("text")
        meta = body.get("metadata_or_coordinates") or body.get("metadata")
        channel = body.get("channel", "API_INCIDENT")
        ingest_req = IngestRequest(
            raw_message=raw_msg,
            metadata_or_coordinates=meta,
            channel=channel
        )
        return await ingest_message(ingest_req)
    else:
        # Direct structured incident creation
        inc = IncidentRecord(**body)
        saved = await save_incident(inc)
        await ws_manager.broadcast({
            "event": "INCIDENT_INGESTED",
            "incident": saved.model_dump()
        })
        return saved

@app.get("/api/incidents")
async def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    disaster_type: Optional[str] = None,
    is_relevant: Optional[bool] = True,
    search: Optional[str] = None
):
    incidents = await get_incidents(
        status=status,
        severity=severity,
        disaster_type=disaster_type,
        is_relevant=is_relevant,
        search=search
    )
    return incidents

@app.get("/api/incidents/{incident_id}")
async def get_incident(incident_id: str):
    inc = await get_incident_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    units = await get_all_units()
    assigned_units = [u for u in units if u.id in inc.dispatched_units]
    return {
        "incident": inc,
        "assigned_units": assigned_units
    }

@app.get("/api/stations")
async def list_emergency_stations():
    """Returns all registered emergency stations (Police, Fire, Hospital, NDRF)"""
    stations = await fleet_service.list_stations()
    return [s.model_dump() for s in stations]

@app.get("/api/response_units")
async def list_all_response_units(unit_type: Optional[str] = None):
    """Returns all fleet response units with optional type filtering"""
    units = await fleet_service.list_response_units()
    if unit_type and unit_type != "ALL":
        units = [u for u in units if u.unit_type == unit_type]
    return [u.model_dump() for u in units]

@app.get("/api/pois")
async def get_nearby_pois(
    lat: float = Query(..., description="Latitude of incident or center point"),
    lng: float = Query(..., description="Longitude of incident or center point"),
    radius: int = Query(5000, description="Search radius in meters")
):
    """
    Returns nearby emergency infrastructure POIs (hospitals, police stations, fire stations)
    via Google Maps Places API (with cached offline pre-seeded fallback).
    """
    pois = google_maps.fetch_poi(lat, lng, radius)
    return pois

@app.post("/api/incidents/{incident_id}/nearest-dispatch")
async def recommend_nearest_dispatch(incident_id: str, request: Request):
    """
    Finds the closest available response unit for an incident,
    calculates optimal route, polyline, and estimated arrival time (ETA).
    """
    inc = await get_incident_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    if inc.is_out_of_jurisdiction or not is_within_tamil_nadu(inc.latitude, inc.longitude):
        raise HTTPException(
            status_code=400,
            detail="Out of Jurisdiction (Tamil Nadu SEOC Only): Automatic dispatch routing is restricted to Tamil Nadu sector boundaries."
        )

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    unit_type = body.get("unit_type")
    
    recommendation = await fleet_service.assign_nearest(
        incident_lat=inc.latitude,
        incident_lng=inc.longitude,
        unit_type=unit_type,
        incident_id=inc.id,
        disaster_type=inc.type
    )

    return {
        "status": "SUCCESS",
        "incident_id": inc.id,
        "incident_title": inc.title,
        "recommendation": recommendation
    }

@app.post("/api/incidents/{incident_id}/dispatch")
async def dispatch_units(incident_id: str, request: Request):
    """
    Dispatches specified unit IDs or automatically calculates and dispatches
    the nearest available response unit if unit_ids is omitted or empty.
    """
    inc = await get_incident_by_id(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    unit_ids = body.get("unit_ids") or []
    notes = body.get("notes")

    # If unit_ids omitted, automatically assign nearest unit
    if not unit_ids:
        if inc.is_out_of_jurisdiction or not is_within_tamil_nadu(inc.latitude, inc.longitude):
            raise HTTPException(
                status_code=400,
                detail="Auto-dispatch disabled: Incident is Out of Jurisdiction (Tamil Nadu SEOC Only)."
            )
        unit_type = body.get("unit_type")
        rec = await fleet_service.assign_nearest(
            incident_lat=inc.latitude,
            incident_lng=inc.longitude,
            unit_type=unit_type,
            incident_id=inc.id,
            disaster_type=inc.type
        )
        assigned_id = rec["unit"]["id"]
        unit_ids = [assigned_id]
        if not notes:
            notes = f"Auto-dispatched nearest {rec['assigned_unit_type']} ({assigned_id}) - ETA: {rec['eta_minutes']} mins (Dist: {rec['distance_km']} km)"

    updated_inc = await dispatch_units_to_incident(incident_id, unit_ids, notes)
    if not updated_inc:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    all_units = await get_all_units()
    stats = await get_system_stats()
    
    await ws_manager.broadcast({
        "event": "UNITS_DISPATCHED",
        "incident_id": incident_id,
        "incident": updated_inc.model_dump(),
        "dispatched_unit_ids": unit_ids,
        "units": [u.model_dump() for u in all_units],
        "stats": stats.model_dump()
    })
    return {"status": "SUCCESS", "incident": updated_inc, "dispatched_unit_ids": unit_ids}


@app.post("/api/incidents/{incident_id}/status")
@app.patch("/api/incidents/{incident_id}/status")
async def update_status_endpoint(incident_id: str, request: Request):
    body = await request.json()
    status = body.get("status")
    notes = body.get("notes") or body.get("note")
    author_name = body.get("authorName") or body.get("author_name") or "Field Responder (COMMAND-ALPHA)"
    author_role = body.get("authorRole") or body.get("author_role") or "FIELD_RESPONDER"
    
    if not status:
        raise HTTPException(status_code=400, detail="Status is required")

    updated_inc = await update_incident_status(
        incident_id=incident_id,
        status=status,
        notes=notes,
        author_name=author_name,
        author_role=author_role
    )
    if not updated_inc:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    all_units = await get_all_units()
    stats = await get_system_stats()
    
    await ws_manager.broadcast({
        "event": "STATUS_UPDATED",
        "incident_id": incident_id,
        "incident": updated_inc.model_dump(),
        "units": [u.model_dump() for u in all_units],
        "stats": stats.model_dump()
    })
    await ws_manager.broadcast({
        "event": "INCIDENT_UPDATED",
        "incident": updated_inc.model_dump()
    })
    return {"status": "SUCCESS", "incident": updated_inc}

@app.get("/api/incidents/{incident_id}/aar")
async def get_incident_aar_endpoint(incident_id: str):
    """
    Returns structured After-Action Report (AAR) for an incident,
    including duration, casualty tallies, responders deployed, and timeline log.
    """
    aar = await get_after_action_report(incident_id)
    if not aar:
        raise HTTPException(status_code=404, detail="Incident or AAR report not found")
    return {"status": "SUCCESS", "aar": aar}

@app.post("/api/incidents/{incident_id}/victims")

async def log_victim_endpoint(incident_id: str, request: Request):
    victim_data = await request.json()
    author = victim_data.get("authorName", "Field Medic")
    updated_inc = await add_victim_to_incident(incident_id, victim_data, author)
    if not updated_inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    stats = await get_system_stats()
    await ws_manager.broadcast({
        "event": "VICTIM_LOGGED",
        "incident_id": incident_id,
        "incident": updated_inc.model_dump(),
        "victim": victim_data,
        "stats": stats.model_dump()
    })
    await ws_manager.broadcast({
        "event": "INCIDENT_UPDATED",
        "incident": updated_inc.model_dump()
    })
    return {"status": "SUCCESS", "incident": updated_inc}

@app.get("/api/units")
@app.get("/api/teams")
async def list_units_and_teams():
    """Returns all emergency first responder teams / units"""
    units = await get_all_units()
    return [u.model_dump() for u in units]

@app.post("/api/teams/{team_id}/dispatch")
async def dispatch_single_team(team_id: str, request: Request):
    """
    Dispatches a single emergency response team to an incident.
    """
    body = await request.json()
    incident_id = body.get("incident_id") or body.get("incidentId")
    notes = body.get("notes") or f"Direct dispatch of unit {team_id}"

    if not incident_id:
        raise HTTPException(status_code=400, detail="incident_id is required")

    updated_inc = await dispatch_units_to_incident(incident_id, [team_id], notes)
    if not updated_inc:
        raise HTTPException(status_code=404, detail="Incident or Unit not found")

    all_units = await get_all_units()
    stats = await get_system_stats()

    # Broadcast updates across terminals
    await ws_manager.broadcast({
        "event": "TEAM_DISPATCHED",
        "team_id": team_id,
        "incident_id": incident_id,
        "incident": updated_inc.model_dump(),
        "units": [u.model_dump() for u in all_units],
        "stats": stats.model_dump()
    })
    await ws_manager.broadcast({
        "event": "UNITS_DISPATCHED",
        "incident_id": incident_id,
        "incident": updated_inc.model_dump(),
        "dispatched_unit_ids": [team_id],
        "units": [u.model_dump() for u in all_units],
        "stats": stats.model_dump()
    })
    return {
        "status": "SUCCESS",
        "team_id": team_id,
        "incident": updated_inc.model_dump()
    }

@app.get("/api/stats")
async def fetch_stats():
    return await get_system_stats()

@app.post("/api/simulate/feed")
async def trigger_simulation():
    """Trigger an incoming simulated live distress feed"""
    scenario = get_random_scenario()
    ingest_req = IngestRequest(
        raw_message=scenario["raw_message"],
        metadata_or_coordinates=scenario["metadata"],
        channel=scenario["channel"]
    )
    return await ingest_message(ingest_req)

@app.get("/api/export/session")
async def export_operational_session():
    """
    Step 12: Controlled System Standby & Session Export
    Exports complete CAD operational summary including incidents, timeline notes,
    casualties, and unit dispatch telemetry in clean structured JSON.
    """
    stats = await get_system_stats()
    incidents = await get_incidents(is_relevant=None)
    units = await get_all_units()
    audit_logs = await get_all_audit_logs()

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    export_payload = {
        "export_metadata": {
            "system_name": "AEGIS-CAD (AI Emergency Dispatch System)",
            "session_id": f"SESSION-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "operating_mode": "SYSTEM_STANDBY_ARCHIVE",
            "total_incidents_logged": len(incidents),
            "triaged_today": stats.triaged_today
        },
        "system_stats": stats.model_dump(),
        "incidents": [i.model_dump() for i in incidents],
        "responder_units": [u.model_dump() for u in units],
        "audit_logs": audit_logs
    }

    filename = f"cad_operational_summary_{today_str}.json"
    return JSONResponse(
        content=export_payload,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@app.get("/api/export/sitrep")
async def export_sitrep():
    """Generate official Situation Report (SITREP) for Disaster Authorities"""
    stats = await get_system_stats()
    incidents = await get_incidents(is_relevant=True)
    active_incidents = [i for i in incidents if i.status != "RESOLVED"]
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    
    report_lines = [
        f"# STATE DISASTER MANAGEMENT AUTHORITY (SDMA) / CAD SITREP",
        f"**Generated At**: {timestamp} | **Operating Mode**: ACTIVE EMERGENCY DISPATCH",
        f"---",
        f"## 1. Executive Summary & Telemetry",
        f"- **Active Incidents**: {len(active_incidents)} ({stats.active_critical} Critical, {stats.active_high} High)",
        f"- **Total Trapped Citizens**: {stats.trapped_count}",
        f"- **Total Confirmed Injured**: {stats.injured_count}",
        f"- **Units Deployed**: {stats.dispatched_units} | **Units Available**: {stats.available_units}",
        f"- **System Average Urgency Index**: {stats.average_urgency} / 100",
        f"",
        f"## 2. Priority Incident Matrix",
        f"| ID | Type | Severity | Urgency | Location | Trapped/Injured | Dispatched Units | Status |",
        f"|---|---|---|---|---|---|---|---|"
    ]
    
    for inc in active_incidents:
        units_str = ", ".join(inc.dispatched_units) if inc.dispatched_units else "None"
        report_lines.append(
            f"| {inc.id} | {inc.type} | {inc.severity} | {inc.urgency_score}/100 | {inc.location_name} | {inc.affected_trapped} trapped / {inc.affected_injured} inj | {units_str} | {inc.status} |"
        )
        
    report_lines.extend([
        f"",
        f"## 3. Critical Actionable Directives",
        f"1. Priority deployment of heavy boat tenders and life-support units to Sector 4 and coastal corridors.",
        f"2. Maintain strict safety perimeter around Manali Hazmat zones; ensure SCBA apparatus for all deployed personnel.",
        f"3. Coordinate with District Collectorate for secondary shelter and food distribution hubs.",
        f"",
        f"---",
        f"*End of Situation Report - Automated CAD System Engine*"
    ])
    
    return PlainTextResponse("\n".join(report_lines), media_type="text/markdown")

# WebSocket Endpoint
@app.websocket("/ws/cad")
async def websocket_cad_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        stats = await get_system_stats()
        units = await get_all_units()
        stations = await fleet_service.list_stations()
        await websocket.send_json({
            "event": "INITIAL_STATE",
            "stats": stats.model_dump(),
            "units": [u.model_dump() for u in units],
            "stations": [s.model_dump() for s in stations]
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)

@app.get("/api/geocode/search")
async def geocode_landmark_search(q: str = Query(..., min_length=2)):
    """
    Real-Time Autocomplete Search for Tamil Nadu Landmarks, Colleges, Universities,
    Hospitals, and Transit Hubs.
    """
    results = search_landmarks(q)
    return {"query": q, "results": results}

@app.post("/api/ingest/live")
async def live_ingest_webhook(request: Request):
    """
    Real-Time Public/Webhook Ingestion Endpoint.
    Receives: { rawText, source, lat, lng, senderContact, category, landmark }
    Runs live AI NLP triage, Haversine 200m deduplication, saves to DB,
    and broadcasts instant WebSocket updates (incident:new / incident:sos_triggered).
    """
    body = await request.json()
    raw_text = body.get("rawText") or body.get("raw_text") or body.get("raw_message") or ""
    source = body.get("source") or "PUBLIC_CITIZEN_PORTAL"
    lat_raw = body.get("lat") if body.get("lat") is not None else body.get("latitude")
    lng_raw = body.get("lng") if body.get("lng") is not None else body.get("longitude")
    sender_contact = body.get("senderContact") or body.get("sender_contact") or body.get("contact") or ""
    category_hint = body.get("category") or body.get("type") or ""
    landmark_hint = body.get("landmark") or body.get("locationName") or ""

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="rawText is required")

    meta_str = f"GPS: ({lat_raw}, {lng_raw})" if (lat_raw is not None and lng_raw is not None) else (landmark_hint or sender_contact or "Live Citizen Stream")
    if category_hint:
        meta_str += f" | Category: {category_hint}"

    triage_res = await triage_engine.triage_message(raw_text, meta_str)

    if not triage_res.is_relevant or not triage_res.incident:
        logger.warning(f"Live distress signal filtered out: {triage_res.rejection_reason}")
        return {
            "status": "DISCARDED",
            "is_relevant": False,
            "reason": triage_res.rejection_reason or "Non-emergency content",
            "triage": triage_res.model_dump()
        }

    inc_data = triage_res.incident
    if lat_raw is not None and lng_raw is not None:
        lat, lon = float(lat_raw), float(lng_raw)
    else:
        # Check explicit landmark hint first, then extracted locationName
        search_loc = landmark_hint if landmark_hint else inc_data.locationName
        lat, lon = resolve_location_coordinates(search_loc, f"{raw_text} {meta_str}")

    # Geospatial Deduplication (Haversine <= 200m)
    dup_incident, dist_km = await find_duplicate_incident(lat, lon, inc_data.type, threshold_km=0.2)
    if dup_incident:
        logger.info(f"Merging live alert into existing active incident {dup_incident.id} (dist: {dist_km*1000:.1f}m)")
        merged_record = await merge_duplicate_alert(dup_incident, inc_data, raw_text, source)
        all_units = await get_all_units()
        stats = await get_system_stats()

        await ws_manager.broadcast({
            "event": "incident:sos_triggered",
            "incidentId": merged_record.id,
            "newSosCount": merged_record.sosAlertsCount,
            "incident": merged_record.model_dump(),
            "units": [u.model_dump() for u in all_units],
            "stats": stats.model_dump()
        })
        await ws_manager.broadcast({
            "event": "INCIDENT_UPDATED",
            "incident": merged_record.model_dump()
        })
        return {
            "status": "MERGED",
            "merged": True,
            "incidentId": merged_record.id,
            "incident_id": merged_record.id,
            "sosAlertsCount": merged_record.sosAlertsCount,
            "incident": merged_record.model_dump(),
            "triage": triage_res.model_dump()
        }

    # Create New Incident
    new_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    new_record = IncidentRecord(
        id=new_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        raw_text=raw_text,
        channel=source,
        metadata_info=f"Contact: {sender_contact} | GPS: ({lat:.4f}, {lon:.4f})" if sender_contact else f"GPS: ({lat:.4f}, {lon:.4f})",
        is_relevant=True,
        confidence_score=triage_res.confidence_score,
        title=inc_data.title,
        type=inc_data.type,
        severity=inc_data.severity,
        urgency_score=inc_data.urgencyScore,
        urgencyScore=inc_data.urgencyScore,
        location_name=inc_data.locationName,
        locationName=inc_data.locationName,
        latitude=lat,
        longitude=lon,
        coordinates={"lat": lat, "lng": lon},
        affectedPeople=inc_data.affectedPeople,
        affected_injured=inc_data.affectedPeople.injured,
        affected_trapped=inc_data.affectedPeople.trapped,
        affected_evacuated=inc_data.affectedPeople.evacuated,
        affected_total=inc_data.affectedPeople.totalEstimated,
        casualty_summary=inc_data.casualtySummary,
        actionable_notes=inc_data.actionableNotes,
        currentStatus="REPORTED",
        status="PENDING",
        sosAlertsCount=1,
        accessRoutes=getattr(inc_data, 'accessRoutes', None) or getattr(inc_data, 'access_routes', None) or f"Access via {inc_data.locationName} arterial route.",
        emergencyInstructions=getattr(inc_data, 'emergencyInstructions', None) or getattr(inc_data, 'emergency_instructions', None) or inc_data.actionableNotes,
        timeline=[{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "LIVE_CITIZEN_INGESTED",
            "notes": f"Real-time live signal received via {source}."
        }]
    )
    saved_record = await save_incident(new_record)
    all_units = await get_all_units()
    stats = await get_system_stats()

    # Immediate Broadcast to Dispatch HUDs
    await ws_manager.broadcast({
        "event": "incident:new",
        "incident": saved_record.model_dump(),
        "triage": triage_res.model_dump(),
        "units": [u.model_dump() for u in all_units],
        "stats": stats.model_dump()
    })
    await ws_manager.broadcast({
        "event": "INCIDENT_INGESTED",
        "incident": saved_record.model_dump(),
        "triage": triage_res.model_dump(),
        "units": [u.model_dump() for u in all_units],
        "stats": stats.model_dump()
    })

    return {
        "status": "SUCCESS",
        "merged": False,
        "incidentId": saved_record.id,
        "incident_id": saved_record.id,
        "incident": saved_record.model_dump(),
        "triage": triage_res.model_dump()
    }


# =====================================================================
# REAL-TIME TAMIL NADU DATA & DISASTER TELEMETRY ENGINE
# =====================================================================
from app.services.realtime_feed import TamilNaduRealtimeCollector

@app.get("/api/realtime/tamilnadu-telemetry")
async def get_tamil_nadu_realtime_telemetry():
    """Fetches real-time meteorological and disaster risk telemetry across Tamil Nadu."""
    data = await TamilNaduRealtimeCollector.get_statewide_telemetry()
    return data

@app.post("/api/realtime/sync-tamilnadu-alerts")
async def sync_tamil_nadu_realtime_alerts():
    """Sync real-time detected weather/disaster risk anomalies across Tamil Nadu into CAD operational tasks."""
    telemetry = await TamilNaduRealtimeCollector.get_statewide_telemetry()
    ingested_alerts = []
    
    for report in telemetry.get("station_reports", []):
        t = report.get("telemetry", {})
        rain = t.get("precipitation_mm", 0.0)
        wind = t.get("wind_gust_kmh", 0.0)
        district = report.get("district", "Tamil Nadu")
        
        # If significant rainfall or wind, or randomly simulate severe weather warning during drill
        if rain >= 5.0 or wind >= 30.0 or report.get("risk_level") in ["SEVERE", "MODERATE"]:
            raw_sos = f"Real-Time Weather Alert: {district} ({report['station_name']}) recorded heavy precipitation {rain} mm/h and wind gusts {wind} km/h. Elevated inundation and structural hazard warning in effect."
            
            # Triage with engine
            triage_res = await triage_engine.triage_message(
                raw_message=raw_sos,
                metadata=f"Station: {report['station_name']}, District: {district}, GPS: ({report['latitude']}, {report['longitude']})"
            )
            if triage_res.is_relevant and triage_res.incident:

                inc_data = triage_res.incident
                lat, lon = report["latitude"], report["longitude"]
                
                # Check spatial dedup
                dup = await find_duplicate_incident(lat, lon, inc_data.type)
                if not dup:
                    new_id = f"INC-TN-RT-{uuid.uuid4().hex[:6].upper()}"
                    now_iso = datetime.now(timezone.utc).isoformat()
                    new_record = IncidentRecord(
                        id=new_id,
                        created_at=now_iso,
                        raw_text=raw_sos,
                        channel="TN_DISASTER_MONITORING_GRID",
                        metadata_info=f"Live Sensor Feed - {report['station_name']}",
                        is_relevant=True,
                        confidence_score=0.98,
                        title=f"Real-Time Sensor Alert: {inc_data.title} ({district})",
                        type=inc_data.type,
                        severity=inc_data.severity,
                        urgency_score=inc_data.urgencyScore,
                        location_name=f"{district}, Tamil Nadu",
                        latitude=lat,
                        longitude=lon,
                        affected_injured=0,
                        affected_trapped=0,
                        affected_evacuated=0,
                        affected_total=0,
                        casualty_summary=inc_data.casualtySummary,
                        actionable_notes=inc_data.actionableNotes,
                        currentStatus="REPORTED",
                        status="PENDING",
                        sosAlertsCount=1,
                        timeline=[{
                            "timestamp": now_iso,
                            "action": "REALTIME_TN_TELEMETRY_INGESTED",
                            "notes": f"Automated real-time sensor alert triggered for {district}."
                        }]
                    )
                    saved = await save_incident(new_record)
                    ingested_alerts.append(saved.model_dump())
    
    if ingested_alerts:
        all_units = await get_all_units()
        stats = await get_system_stats()
        await ws_manager.broadcast({
            "event": "INCIDENTS_BATCH_SYNCED",
            "count": len(ingested_alerts),
            "stats": stats.model_dump()
        })
    
    return {
        "status": "SUCCESS",
        "synced_alerts_count": len(ingested_alerts),
        "alerts": ingested_alerts,
        "telemetry_summary": telemetry
    }

@app.post("/api/database/reset-tamilnadu")
async def reset_database_to_tamil_nadu():
    """Resets the CAD database and initializes the 4 Chennai and 4 Tamil Nadu tasks."""
    from app.database import reset_database_clean_tamilnadu
    await reset_database_clean_tamilnadu()
    stats = await get_system_stats()
    all_units = await get_all_units()
    incidents = await get_incidents()
    
    await ws_manager.broadcast({
        "event": "DATABASE_RESET",
        "stats": stats.model_dump(),
        "units": [u.model_dump() for u in all_units]
    })
    
    return {
        "status": "SUCCESS",
        "message": "Database successfully aligned to 4 Chennai and 4 Tamil Nadu active operational tasks.",
        "incidents_count": len(incidents),
        "incidents": [inc.model_dump() for inc in incidents]
    }


# -------------------------------------------------------------
# REAL-TIME SOCIAL MEDIA INGESTION & LIVE STREAM CONTROLS
# -------------------------------------------------------------

@app.get("/api/stream/status")
async def get_stream_worker_status():
    """Returns the continuous real-time social media ingestion status and event feed."""
    return {
        "status": "SUCCESS",
        "running": social_worker.is_running(),
        "ingested_count": social_worker.ingested_count,
        "ticket_created_count": social_worker.ticket_created_count,
        "merged_count": social_worker.merged_count,
        "discarded_count": social_worker.discarded_count,
        "recent_events": social_worker.get_recent_stream_events()
    }

@app.post("/api/stream/toggle")
async def toggle_stream_worker(request: Request):
    """Starts or pauses the background social media ingestion loop."""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    
    enable = body.get("enable")
    if enable is None:
        enable = not social_worker.is_running()
        
    if enable:
        interval = body.get("interval_seconds", 25)
        social_worker.start(interval_seconds=interval)
    else:
        social_worker.stop()
        
    return {
        "status": "SUCCESS",
        "running": social_worker.is_running(),
        "message": "Social media ingestion worker is now " + ("ACTIVE" if social_worker.is_running() else "PAUSED")
    }

@app.post("/api/stream/simulate-now")
async def trigger_simulated_stream_post():
    """Manually triggers an instant simulated social media distress post for live demo."""
    event = await social_worker.simulate_single_post()
    return {
        "status": "SUCCESS",
        "event": event.model_dump()
    }

@app.post("/api/stream/clear-log")
async def clear_stream_events_log():
    """Clears the in-memory stream events feed."""
    social_worker.clear_events()
    return {
        "status": "SUCCESS",
        "message": "Stream event log cleared."
    }




# Mount Static Files
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/report", response_class=HTMLResponse)
async def serve_public_report_portal():
    """Public Citizen Distress SOS Portal"""
    report_path = os.path.join(static_dir, "report.html")
    if os.path.exists(report_path):
        return FileResponse(report_path)
    return HTMLResponse(content="<h1>Citizen SOS Portal Not Found</h1>")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse(content="<h1>CAD Triage System Initializing...</h1>")
