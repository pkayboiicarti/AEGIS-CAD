import asyncio
import hashlib
import json
import logging
import random
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Set, Dict, Any, Callable

from app.models import (
    SocialStreamItem, SocialStreamEvent, IncidentRecord,
    TriageResult, CADIncidentData, AffectedPeople
)
from app.triage_engine import TriageEngine
from app.geocoding import resolve_location_coordinates, is_within_tamil_nadu
from app.dedup import find_duplicate_incident, merge_duplicate_alert
from app.database import save_incident, get_system_stats

logger = logging.getLogger("cad.social_worker")

# Rich dataset of realistic Tamil Nadu live social media distress broadcasts and edge cases
SIMULATED_CRISIS_POSTS = [
    # Scenario 1: High-Priority Disasters in Tamil Nadu
    {
        "platform": "TWITTER_X",
        "author": "@chennai_weather_live",
        "text": "CRITICAL SOS! Water level rapidly rising above 5 feet near Velachery Lake View Sector 4. At least 12 people including toddlers stranded on 1st floor balcony without drinking water or power. Urgent boat rescue needed! @TNDRF @NDRFHQ",
        "location_hint": "Velachery Lake View Sector 4, Chennai (12.9791, 80.2185)",
        "source_url": "https://x.com/chennai_weather_live/status/1788204928192"
    },
    {
        "platform": "REDDIT",
        "author": "u/madurai_citizen_99",
        "text": "Flash flooding alert in Madurai! Vaigai river has breached its embankment near Goripalayam junction. 8 low-lying huts submerged, families scrambling to rooftops. Need SDRF emergency rescue boats immediately.",
        "location_hint": "Goripalayam Junction, Madurai (9.9252, 78.1198)",
        "source_url": "https://reddit.com/r/TamilNadu/comments/1c90q3k/flash_floods_goripalayam"
    },
    {
        "platform": "TWITTER_X",
        "author": "@kovai_alert",
        "text": "Massive 4-alarm fire erupting inside commercial textile warehouse at Peelamedu industrial sector, Coimbatore! Heavy black toxic smoke billowing, workers crying for help from fire escape stairs. Send fire tenders now!",
        "location_hint": "Peelamedu, Coimbatore (11.0168, 76.9558)",
        "source_url": "https://x.com/kovai_alert/status/1788219482012"
    },
    {
        "platform": "DISPATCH_112",
        "author": "112_CAD_DISPATCH",
        "text": "[CALLER 112 DISPATCH]: Hazardous chemical pipeline burst at Sriperumbudur SIPCOT Sector 2. Pungent vapor cloud spreading, multiple factory staff collapsing and having breathing seizures. Hazmat & ALS ambulances requested urgently!",
        "location_hint": "Sriperumbudur SIPCOT Sector 2 (12.9698, 79.9406)",
        "source_url": "https://tndrf.gov.in/dispatch/112-SRI-9021"
    },
    {
        "platform": "TELEGRAM",
        "author": "@trichy_emergency_network",
        "text": "High-pressure LPG pipeline rupture with localized explosion hazard near Thuvakudi Industrial Hub, Trichy! 5 workers overcome with dizziness, road access blocked by debris. Immediate extrication required.",
        "location_hint": "Thuvakudi Industrial Hub, Tiruchirappalli (10.7554, 78.7889)",
        "source_url": "https://t.me/trichy_emergency/4819"
    },
    {
        "platform": "CITIZEN_PORTAL",
        "author": "@cuddalore_resident",
        "text": "Coastal storm surge in Cuddalore Old Town port sector! Sea wall partially breached, seawater inundating 20+ fishermen households. Urgent evacuation and relief shelter needed.",
        "location_hint": "Cuddalore Old Town Port (11.7480, 79.7714)",
        "source_url": "https://tndisaster.org/citizen-portal/report-4902"
    },
    {
        "platform": "TWITTER_X",
        "author": "@anna_nagar_voice",
        "text": "Metro construction girder slipped and collapsed onto roadway at Anna Nagar West junction! 2 passenger vans crushed beneath debris, at least 10 commuters trapped inside screaming. Send heavy crane ASAP!",
        "location_hint": "Anna Nagar West Junction, Chennai (13.0850, 80.2101)",
        "source_url": "https://x.com/anna_nagar_voice/status/1788241029412"
    },

    # Scenario 2: Nearby Duplicate Reports within 500m (Demonstrating Cluster Merging)
    {
        "platform": "TWITTER_X",
        "author": "@velachery_resident_sos",
        "text": "URGENT UPDATE: Water level has entered our 1st floor at Velachery Lake View 3rd Main Road! 6 more neighbors joining us on terrace. Please send rescue boat right away!",
        "location_hint": "Velachery Lake View 3rd Main Road, Chennai (12.9793, 80.2188)",
        "source_url": "https://x.com/velachery_resident_sos/status/178826190123"
    },
    {
        "platform": "REDDIT",
        "author": "u/madurai_local",
        "text": "Second report from Goripalayam Madurai - water rising fast near the river bridge. Another 4 people stranded inside tea shop!",
        "location_hint": "Goripalayam Bridge, Madurai (9.9255, 78.1202)",
        "source_url": "https://reddit.com/r/TamilNadu/comments/1c90q3k/goripalayam_update"
    },

    # Scenario 3: Non-Emergency Noise / Spam (Demonstrating Noise Filtering)
    {
        "platform": "TWITTER_X",
        "author": "@peace_advocate",
        "text": "Heartbreaking images coming in from Chennai rains. Thoughts and prayers for everyone's safety! Stay indoors and keep warm folks. #ChennaiRains #SafeTN",
        "location_hint": "Twitter Web App",
        "source_url": "https://x.com/peace_advocate/status/1788250019283"
    },
    {
        "platform": "REDDIT",
        "author": "u/chennai_foodie",
        "text": "Best places to get hot filter coffee and samosas during rainy evenings in Anna Nagar? Drop your suggestions below!",
        "location_hint": "r/Chennai",
        "source_url": "https://reddit.com/r/Chennai/comments/1c91f0z/rainy_day_coffee"
    },

    # Scenario 4: Geographic Boundary Tests Outside Tamil Nadu (Demonstrating Geofence Rejection)
    {
        "platform": "TWITTER_X",
        "author": "@global_disaster_recon",
        "text": "URGENT SOS! Major 6.8 magnitude earthquake hit Kathmandu valley, Nepal! Multi-story buildings collapsed in Patan Durbar Square, dozens trapped under concrete slabs!",
        "location_hint": "Kathmandu, Nepal (27.7172, 85.3240)",
        "source_url": "https://x.com/global_disaster_recon/status/1788299102911"
    },
    {
        "platform": "TWITTER_X",
        "author": "@mumbai_express_news",
        "text": "Severe waterlogging near Kurla railway station Mumbai. Central line trains halted. Local municipal workers diverting traffic.",
        "location_hint": "Kurla, Mumbai, Maharashtra (19.0728, 72.8797)",
        "source_url": "https://x.com/mumbai_express_news/status/1788301192812"
    }
]


class SocialMediaIngestionWorker:
    """
    Continuous real-time social media and multichannel ingestion worker for AEGIS-CAD.
    Performs in-memory content hash deduplication, Gemini 2.5 Flash / Heuristic CAD extraction,
    Tamil Nadu geofencing validation, and 500m geospatial cluster deduplication.
    """

    def __init__(self, triage_engine: Optional[TriageEngine] = None):
        self.triage_engine = triage_engine or TriageEngine()
        self.processed_ids: Set[str] = set()
        self.processed_hashes: Set[str] = set()
        self.recent_events: List[SocialStreamEvent] = []
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._broadcast_callback: Optional[Callable[[Dict[str, Any]], Any]] = None
        self.ingested_count: int = 0
        self.ticket_created_count: int = 0
        self.merged_count: int = 0
        self.discarded_count: int = 0

    def set_broadcast_callback(self, callback: Callable[[Dict[str, Any]], Any]):
        self._broadcast_callback = callback

    def is_running(self) -> bool:
        return self._running

    def start(self, interval_seconds: int = 15):
        """Starts the continuous background ingestion loop."""
        if self._running:
            logger.info("Social media ingestion worker is already running.")
            return

        self._running = True
        self._task = asyncio.create_task(self._worker_loop(interval_seconds))
        logger.info(f"🚀 Continuous Social Media Ingestion Worker started (Interval: 12-20s).")

    def stop(self):
        """Stops the background ingestion loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("🛑 Continuous Social Media Ingestion Worker stopped.")

    async def _worker_loop(self, interval_seconds: int):
        # Initial short delay so server startup finishes
        await asyncio.sleep(2)
        while self._running:
            try:
                await self.simulate_single_post()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in social ingestion worker loop: {e}", exc_info=True)
            
            # Emit a distress post every 12 to 20 seconds
            wait_time = random.uniform(12.0, 20.0)
            await asyncio.sleep(wait_time)

    async def simulate_single_post(self) -> SocialStreamEvent:
        """Picks a random post from the crisis stream dataset and processes it."""
        post_data = random.choice(SIMULATED_CRISIS_POSTS)
        
        # Add random suffix or variation to avoid instant hash collision when cycling
        post_id = f"POST-{uuid.uuid4().hex[:8]}"
        item = SocialStreamItem(
            id=post_id,
            platform=post_data["platform"],
            author=post_data["author"],
            text=post_data["text"],
            location_hint=post_data.get("location_hint"),
            source_url=post_data.get("source_url")
        )
        return await self.process_item(item)

    async def process_item(self, item: SocialStreamItem) -> SocialStreamEvent:
        """
        Executes the full stream processing pipeline on an incoming post:
        1. Deduplication Cache check (Post ID & Text Hash)
        2. Gemini CAD Extraction & Tamil Nadu Geofence Validation
        3. Geospatial Cluster Deduplication (500m radius)
        4. CAD Ticket Generation / Merge
        5. WebSocket Broadcast
        """
        self.ingested_count += 1
        
        # Step 1: In-Memory Deduplication Cache Check
        content_hash = hashlib.md5(item.text.strip().lower().encode("utf-8")).hexdigest()
        if item.id in self.processed_ids or content_hash in self.processed_hashes:
            logger.debug(f"Duplicate social post detected ({item.id}) - skipping processing.")
            evt = SocialStreamEvent(
                item=item,
                action_taken="SPAM_DISCARDED",
                summary="Duplicate post content previously processed in this operational session."
            )
            self._record_event(evt)
            return evt

        self.processed_ids.add(item.id)
        self.processed_hashes.add(content_hash)

        # Step 2: AI Triage Extraction
        triage_res: TriageResult = await self.triage_engine.triage_message(
            item.text,
            item.location_hint
        )

        # Step 3: Check Geofence & Relevance
        if triage_res.is_out_of_jurisdiction or (triage_res.rejection_reason and "OUT_OF_JURISDICTION" in triage_res.rejection_reason):
            self.discarded_count += 1
            evt = SocialStreamEvent(
                item=item,
                action_taken="OUT_OF_JURISDICTION",
                triage_result=triage_res.model_dump(),
                summary=f"⚠️ Out of Jurisdiction: {triage_res.rejection_reason or 'Location outside Tamil Nadu sector'}"
            )
            self._record_event(evt)
            await self._broadcast_stream_event(evt)
            return evt

        if not triage_res.is_relevant or not triage_res.incident:
            self.discarded_count += 1
            evt = SocialStreamEvent(
                item=item,
                action_taken="SPAM_DISCARDED",
                triage_result=triage_res.model_dump(),
                summary=f"🗑️ Discarded Noise/Spam: {triage_res.rejection_reason or 'Non-emergency commentary'}"
            )
            self._record_event(evt)
            await self._broadcast_stream_event(evt)
            return evt

        inc_data: CADIncidentData = triage_res.incident
        lat, lon = resolve_location_coordinates(inc_data.locationName, item.location_hint)

        # Validate coordinate bounding box strictly
        if not is_within_tamil_nadu(lat, lon):
            self.discarded_count += 1
            evt = SocialStreamEvent(
                item=item,
                action_taken="OUT_OF_JURISDICTION",
                triage_result=triage_res.model_dump(),
                summary=f"⚠️ Out of Jurisdiction ({lat}, {lon}): Outside Tamil Nadu operational boundaries."
            )
            self._record_event(evt)
            await self._broadcast_stream_event(evt)
            return evt

        # Step 4: Geospatial Cluster Deduplication (within 500m radius of active incident)
        dup_incident, dist_km = await find_duplicate_incident(lat, lon, inc_data.type, threshold_km=0.5)
        
        if dup_incident:
            # Merge with existing active incident
            merged_record = await merge_duplicate_alert(
                dup_incident,
                inc_data,
                item.text,
                item.platform
            )
            self.merged_count += 1
            dist_m = round(dist_km * 1000, 1)
            evt = SocialStreamEvent(
                item=item,
                action_taken="MERGED",
                incident_id=merged_record.id,
                incident_title=merged_record.title,
                distance_meters=dist_m,
                triage_result=triage_res.model_dump(),
                summary=f"🔗 Merged with {merged_record.id} ({dist_m}m away). SOS count incremented to {merged_record.sosAlertsCount}."
            )
            self._record_event(evt)

            # Broadcast live updates
            await self._broadcast_ws({
                "event": "INCIDENT_UPDATED",
                "incident": merged_record.model_dump()
            })
            await self._broadcast_ws({
                "event": "incident:sos_triggered",
                "incidentId": merged_record.id,
                "newSosCount": merged_record.sosAlertsCount,
                "incident": merged_record.model_dump()
            })
            await self._broadcast_stream_event(evt)
            await self._broadcast_stats()
            return evt

        # Step 5: Generate Unique New CAD Incident Record
        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        new_incident = IncidentRecord(
            id=incident_id,
            raw_text=item.text,
            channel=item.platform,
            metadata_info=item.location_hint,
            source_url=item.source_url,
            author_handle=item.author,
            channel_icon=item.platform,
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
            timeline=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "SOCIAL_STREAM_INGESTED",
                "notes": f"Ingested via live {item.platform} stream ({item.author})"
            }]
        )
        saved_record = await save_incident(new_incident)
        self.ticket_created_count += 1

        evt = SocialStreamEvent(
            item=item,
            action_taken="TICKET_GENERATED",
            incident_id=saved_record.id,
            incident_title=saved_record.title,
            triage_result=triage_res.model_dump(),
            summary=f"✅ New Ticket {saved_record.id} ({saved_record.severity} {saved_record.type}) dispatched to PROPOSED queue."
        )
        self._record_event(evt)

        # Broadcast live updates to all connected dispatcher consoles
        await self._broadcast_ws({
            "event": "INCIDENT_INGESTED",
            "incident": saved_record.model_dump(),
            "triage": triage_res.model_dump()
        })
        await self._broadcast_stream_event(evt)
        await self._broadcast_stats()
        return evt

    def _record_event(self, event: SocialStreamEvent):
        self.recent_events.insert(0, event)
        if len(self.recent_events) > 60:
            self.recent_events = self.recent_events[:60]

    def get_recent_stream_events(self) -> List[Dict[str, Any]]:
        return [e.model_dump() for e in self.recent_events]

    def clear_events(self):
        self.recent_events.clear()

    async def _broadcast_stream_event(self, event: SocialStreamEvent):
        payload = {
            "event": "STREAM_ACTIVITY",
            "stream_event": event.model_dump()
        }
        await self._broadcast_ws(payload)
        # Also emit specific socket.io standard event name
        await self._broadcast_ws({
            "event": "cad:incident_streamed",
            "stream_event": event.model_dump()
        })

    async def _broadcast_stats(self):
        try:
            stats = await get_system_stats()
            await self._broadcast_ws({
                "event": "STATS_UPDATED",
                "stats": stats.model_dump()
            })
            await self._broadcast_ws({
                "event": "cad:kpi_updated",
                "stats": stats.model_dump()
            })
        except Exception as e:
            logger.debug(f"Failed to broadcast system stats: {e}")

    async def _broadcast_ws(self, payload: Dict[str, Any]):
        if self._broadcast_callback:
            try:
                res = self._broadcast_callback(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.debug(f"WebSocket broadcast callback error: {e}")
