import math
import json
from typing import Optional, Tuple
from datetime import datetime, timezone
from app.models import IncidentRecord, CADIncidentData
from app.database import get_incidents, save_incident, update_incident_status, DB_PATH
import aiosqlite

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees).
    Returns distance in kilometers.
    """
    R = 6371.0  # Earth radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

async def find_duplicate_incident(
    lat: float,
    lon: float,
    disaster_type: str,
    threshold_km: float = 0.2
) -> Tuple[Optional[IncidentRecord], float]:
    """
    Searches for an active (non-resolved) incident of the same type 
    within threshold_km (default 200m = 0.2km).
    """
    active_incidents = await get_incidents(is_relevant=True)
    for inc in active_incidents:
        if inc.status == "RESOLVED":
            continue
        if inc.type == disaster_type or disaster_type == "OTHER":
            dist = haversine_distance(lat, lon, inc.latitude, inc.longitude)
            if dist <= threshold_km:
                return (inc, dist)
    return (None, 0.0)

async def merge_duplicate_alert(
    existing: IncidentRecord,
    new_inc_data: CADIncidentData,
    raw_message: str,
    channel: str = "WEB_CAD"
) -> IncidentRecord:
    """
    Merges incoming alert data into existing incident:
    1. Increments sosAlertsCount
    2. Merges victim counts
    3. Updates timeline and urgency score
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    time_str = datetime.now(timezone.utc).strftime("%H:%M UTC")

    existing.sosAlertsCount = getattr(existing, "sosAlertsCount", 1) + 1
    existing.sos_alerts_count = existing.sosAlertsCount

    # Merge victims
    add_inj = new_inc_data.affectedPeople.injured
    add_trap = new_inc_data.affectedPeople.trapped
    add_evac = new_inc_data.affectedPeople.evacuated
    add_tot = new_inc_data.affectedPeople.totalEstimated

    existing.affected_injured += add_inj
    existing.affected_trapped += add_trap
    existing.affected_evacuated += add_evac
    existing.affected_total += add_tot

    existing.affectedPeople.injured = existing.affected_injured
    existing.affectedPeople.trapped = existing.affected_trapped
    existing.affectedPeople.evacuated = existing.affected_evacuated
    existing.affectedPeople.totalEstimated = existing.affected_total

    # Bump urgency score slightly for repeated alarms (up to 100)
    existing.urgency_score = min(100, max(existing.urgency_score, new_inc_data.urgencyScore) + 2)
    existing.urgencyScore = existing.urgency_score

    # Append timeline entry
    timeline_entry = {
        "id": f"UP-SOS-{datetime.now(timezone.utc).strftime('%H%M%S')}",
        "timestamp": time_str,
        "iso_timestamp": now_iso,
        "action": "SOS_DUPLICATE_MERGED",
        "authorName": "Geospatial Deduplication Engine",
        "authorRole": "SYSTEM",
        "statusChange": existing.status,
        "note": f"Merged duplicate alert from {channel} within 200m. Total SOS alarms: {existing.sosAlertsCount}. Added +{add_trap} trapped, +{add_inj} injured.",
        "notes": f"Merged duplicate alert from {channel} within 200m. Total SOS alarms: {existing.sosAlertsCount}."
    }
    existing.timeline.append(timeline_entry)

    # Persist in SQLite
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        UPDATE incidents SET
            urgency_score = ?,
            affected_injured = ?,
            affected_trapped = ?,
            affected_evacuated = ?,
            affected_total = ?,
            timeline = ?
        WHERE id = ?
        """, (
            existing.urgency_score,
            existing.affected_injured,
            existing.affected_trapped,
            existing.affected_evacuated,
            existing.affected_total,
            json.dumps(existing.timeline),
            existing.id
        ))
        await db.execute("""
        INSERT INTO audit_logs (timestamp, event_type, incident_id, details)
        VALUES (?, ?, ?, ?)
        """, (now_iso, "SOS_DUPLICATE_MERGED", existing.id, f"Merged alert. New SOS Count: {existing.sosAlertsCount}"))
        await db.commit()

    return existing
