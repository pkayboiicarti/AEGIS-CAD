import logging
from typing import List, Optional, Tuple, Dict, Any
from app.models import EmergencyStation, ResponseUnit
from app.database import (
    get_all_stations, get_station_by_id,
    get_all_response_units, get_response_unit_by_id,
    update_response_unit_assignment
)
from app.google_maps import haversine_distance, get_route

logger = logging.getLogger("cad.fleet_service")

# Fallback hierarchy for emergency unit assignments
UNIT_FALLBACK_HIERARCHY = {
    "FIRE_ENGINE": ["FIRE_ENGINE", "NDRF_RESCUE", "SDRF_QUICK_RESPONSE", "POLICE_PATROL", "AMBULANCE_ALS"],
    "BOAT_RESCUE": ["BOAT_RESCUE", "NDRF_RESCUE", "SDRF_QUICK_RESPONSE", "FIRE_ENGINE", "POLICE_PATROL"],
    "NDRF_RESCUE": ["NDRF_RESCUE", "SDRF_QUICK_RESPONSE", "FIRE_ENGINE", "BOAT_RESCUE", "POLICE_PATROL"],
    "AMBULANCE_ALS": ["AMBULANCE_ALS", "NDRF_RESCUE", "SDRF_QUICK_RESPONSE", "POLICE_PATROL"],
    "DRONE_RECON": ["DRONE_RECON", "POLICE_PATROL", "NDRF_RESCUE", "SDRF_QUICK_RESPONSE"],
    "POLICE_PATROL": ["POLICE_PATROL", "SDRF_QUICK_RESPONSE", "NDRF_RESCUE", "FIRE_ENGINE", "AMBULANCE_ALS"],
    "SDRF_QUICK_RESPONSE": ["SDRF_QUICK_RESPONSE", "NDRF_RESCUE", "POLICE_PATROL", "FIRE_ENGINE"]
}

DISASTER_TO_UNIT_MAP = {
    "FIRE": "FIRE_ENGINE",
    "FLOOD": "BOAT_RESCUE",
    "INDUSTRIAL": "FIRE_ENGINE",
    "STRUCTURAL_COLLAPSE": "NDRF_RESCUE",
    "CYCLONE": "NDRF_RESCUE",
    "EARTHQUAKE": "NDRF_RESCUE",
    "OTHER": "POLICE_PATROL"
}

def haversine(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Helper function to compute distance in km between two (lat, lon) coordinates."""
    return haversine_distance(coord1[0], coord1[1], coord2[0], coord2[1])

async def list_stations() -> List[EmergencyStation]:
    """Returns all registered emergency stations."""
    return await get_all_stations()

async def list_response_units() -> List[ResponseUnit]:
    """Returns all fleet response units."""
    return await get_all_response_units()

async def available_units(unit_type: Optional[str] = None) -> List[ResponseUnit]:
    """Filter units with status == 'AVAILABLE', optionally matching unit_type."""
    all_units = await get_all_response_units()
    avail = [u for u in all_units if u.status == "AVAILABLE"]
    if unit_type and unit_type != "ALL":
        avail = [u for u in avail if u.unit_type == unit_type]
    return avail

async def assign_nearest(
    incident_lat: float,
    incident_lng: float,
    unit_type: Optional[str] = None,
    incident_id: Optional[str] = None,
    disaster_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Finds the closest emergency station and response unit to an incident location.
    Prioritizes local physical proximity and compatibility.
    Computes road route polyline, distance in km, and estimated arrival time (ETA).
    """
    # 1. Determine target unit type
    target_type = unit_type
    if not target_type or target_type == "ALL":
        target_type = DISASTER_TO_UNIT_MAP.get(disaster_type or "OTHER", "POLICE_PATROL")

    # 2. Get fallback chain
    fallback_chain = UNIT_FALLBACK_HIERARCHY.get(target_type, [target_type, "POLICE_PATROL", "NDRF_RESCUE"])

    all_units = await get_all_response_units()
    stations = await get_all_stations()
    stations_map = {s.id: s for s in stations}

    # 3. Categorized nearest stations
    nearest_station: Optional[EmergencyStation] = None
    nearest_station_dist_km: float = 99999.0
    nearest_by_type = {}

    if stations:
        sorted_stns = sorted(stations, key=lambda s: haversine((s.latitude, s.longitude), (incident_lat, incident_lng)))
        nearest_station = sorted_stns[0]
        nearest_station_dist_km = round(haversine((nearest_station.latitude, nearest_station.longitude), (incident_lat, incident_lng)), 2)

        for stn_type in ["FIRE", "POLICE", "HOSPITAL", "DISASTER_MGMT"]:
            type_stns = [s for s in sorted_stns if s.type == stn_type]
            if type_stns:
                closest_of_type = type_stns[0]
                dist_km = round(haversine((closest_of_type.latitude, closest_of_type.longitude), (incident_lat, incident_lng)), 2)
                eta_min = max(1, round((dist_km / 45.0) * 60))
                nearest_by_type[stn_type] = {
                    "id": closest_of_type.id,
                    "name": closest_of_type.name,
                    "type": closest_of_type.type,
                    "latitude": closest_of_type.latitude,
                    "longitude": closest_of_type.longitude,
                    "address": closest_of_type.address,
                    "distance_km": dist_km,
                    "eta_minutes": eta_min
                }

    chosen_unit: Optional[ResponseUnit] = None
    fallback_used = False

    avail_units = [u for u in all_units if u.status == "AVAILABLE"]
    pool = avail_units if avail_units else all_units

    # 4. Proximity-weighted search:
    # First check if there is an exact matching unit type
    matching_avail = [u for u in pool if u.unit_type == target_type]
    if matching_avail:
        matching_avail.sort(key=lambda u: haversine((u.latitude, u.longitude), (incident_lat, incident_lng)))
        chosen_unit = matching_avail[0]
        dist_chosen = haversine((chosen_unit.latitude, chosen_unit.longitude), (incident_lat, incident_lng))

        # Check if there's a compatible local first responder significantly closer (e.g. within 2.5km vs 5+km)
        closest_any = sorted(pool, key=lambda u: haversine((u.latitude, u.longitude), (incident_lat, incident_lng)))[0]
        dist_closest = haversine((closest_any.latitude, closest_any.longitude), (incident_lat, incident_lng))
        if dist_closest < 2.5 and dist_chosen > 4.0 and closest_any.unit_type in fallback_chain:
            chosen_unit = closest_any
            fallback_used = (chosen_unit.unit_type != target_type)
    else:
        # Fallback through compatible unit hierarchy
        for candidate_type in fallback_chain:
            cand_units = [u for u in pool if u.unit_type == candidate_type]
            if cand_units:
                cand_units.sort(key=lambda u: haversine((u.latitude, u.longitude), (incident_lat, incident_lng)))
                chosen_unit = cand_units[0]
                fallback_used = (candidate_type != target_type)
                break

    if not chosen_unit and pool:
        pool_sorted = sorted(pool, key=lambda u: haversine((u.latitude, u.longitude), (incident_lat, incident_lng)))
        chosen_unit = pool_sorted[0]
        fallback_used = True

    if not chosen_unit:
        raise RuntimeError("No emergency response units configured in fleet registry")

    # 5. Calculate route & ETA from unit's station/location to incident
    origin_coord = (chosen_unit.latitude, chosen_unit.longitude)
    route_data = get_route(origin_coord, (incident_lat, incident_lng))

    unit_station = stations_map.get(chosen_unit.station_id) if chosen_unit.station_id else nearest_station

    return {
        "unit": chosen_unit.model_dump(),
        "station": unit_station.model_dump() if unit_station else None,
        "nearest_station": nearest_station.model_dump() if nearest_station else None,
        "nearest_station_distance_km": nearest_station_dist_km,
        "nearest_by_type": nearest_by_type,
        "route": route_data,
        "distance_km": route_data["distance_km"],
        "duration_s": route_data["duration_s"],
        "eta_minutes": route_data["eta_minutes"],
        "target_unit_type": target_type,
        "assigned_unit_type": chosen_unit.unit_type,
        "fallback_used": fallback_used,
        "is_available": (chosen_unit.status == "AVAILABLE")
    }


