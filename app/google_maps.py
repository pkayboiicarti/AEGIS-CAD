import os
import math
import time
import logging
from typing import List, Dict, Tuple, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("cad.google_maps")

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

BASE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
BASE_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"

# In-memory cache with 5-minute TTL (300 seconds)
_cache: Dict[str, Tuple[float, any]] = {}
CACHE_TTL = 300

# Pre-seeded reference infrastructure POIs for fallback / offline simulation
PRESEEDED_POIS = [
    # --- HOSPITALS & TRAUMA CENTERS ---
    {
        "place_id": "POI-HOSP-01",
        "name": "Rajiv Gandhi Government General Hospital (RGGGH)",
        "type": "hospital",
        "latitude": 13.0818,
        "longitude": 80.2789,
        "vicinity": "EVR Periyar Salai, Park Town, Central Chennai"
    },
    {
        "place_id": "POI-HOSP-02",
        "name": "Apollo Hospitals Main Greams Road",
        "type": "hospital",
        "latitude": 13.0607,
        "longitude": 80.2514,
        "vicinity": "Greams Lane, Thousand Lights, Central Chennai"
    },
    {
        "place_id": "POI-HOSP-03",
        "name": "Government Stanley Medical College Hospital",
        "type": "hospital",
        "latitude": 13.1070,
        "longitude": 80.2863,
        "vicinity": "Old Jail Rd, Royapuram, North Chennai"
    },
    {
        "place_id": "POI-HOSP-04",
        "name": "MIOT International Emergency Care Center",
        "type": "hospital",
        "latitude": 13.0189,
        "longitude": 80.1874,
        "vicinity": "Mount-Poonamallee Rd, Manapakkam, South-West Chennai"
    },
    {
        "place_id": "POI-HOSP-05",
        "name": "Government Kilpauk Medical College Hospital (KMC)",
        "type": "hospital",
        "latitude": 13.0792,
        "longitude": 80.2432,
        "vicinity": "Poonamallee High Rd, Kilpauk, Central Chennai"
    },
    {
        "place_id": "POI-HOSP-06",
        "name": "Fortis Malar Hospital & Cardiac Emergency Hub",
        "type": "hospital",
        "latitude": 13.0063,
        "longitude": 80.2562,
        "vicinity": "1st Main Rd, Gandhi Nagar, Adyar, South Chennai"
    },
    {
        "place_id": "POI-HOSP-07",
        "name": "SIMS Hospital & Advanced Trauma Center",
        "type": "hospital",
        "latitude": 13.0514,
        "longitude": 80.2120,
        "vicinity": "Jawaharlal Nehru Salai, Vadapalani, West Chennai"
    },
    {
        "place_id": "POI-HOSP-08",
        "name": "Gleneagles Health City Emergency Center",
        "type": "hospital",
        "latitude": 12.9056,
        "longitude": 80.1983,
        "vicinity": "Cheran Nagar, Perumbakkam, OMR South Corridor"
    },
    {
        "place_id": "POI-HOSP-09",
        "name": "Dr. Kamakshi Memorial Hospital Multi-Specialty",
        "type": "hospital",
        "latitude": 12.9515,
        "longitude": 80.2038,
        "vicinity": "200 Feet Radial Rd, Pallikaranai, South Chennai"
    },
    {
        "place_id": "POI-HOSP-10",
        "name": "Apollo Speciality Hospital Vanagaram",
        "type": "hospital",
        "latitude": 13.0583,
        "longitude": 80.1472,
        "vicinity": "Vanagaram-Ambattur Main Rd, Porur Bypass, West Chennai"
    },

    # --- FIRE & RESCUE STATIONS ---
    {
        "place_id": "POI-FIRE-01",
        "name": "Egmore Fire & Rescue Operations Command Station",
        "type": "fire_station",
        "latitude": 13.0784,
        "longitude": 80.2604,
        "vicinity": "Pantheon Rd, Egmore, Central Chennai"
    },
    {
        "place_id": "POI-FIRE-02",
        "name": "Manali Petrochem Industrial Hazmat Fire Base",
        "type": "fire_station",
        "latitude": 13.1673,
        "longitude": 80.2644,
        "vicinity": "CPCL Industrial Corridor, Manali, North Chennai"
    },
    {
        "place_id": "POI-FIRE-03",
        "name": "Guindy Industrial Estate Fire Station",
        "type": "fire_station",
        "latitude": 13.0067,
        "longitude": 80.2024,
        "vicinity": "Inner Ring Rd, Guindy, South-Central Chennai"
    },
    {
        "place_id": "POI-FIRE-04",
        "name": "Mylapore Divisional Fire Station",
        "type": "fire_station",
        "latitude": 13.0336,
        "longitude": 80.2676,
        "vicinity": "Luz Church Rd, Mylapore, South Chennai"
    },
    {
        "place_id": "POI-FIRE-05",
        "name": "Ambattur Industrial Estate Heavy Fire Base",
        "type": "fire_station",
        "latitude": 13.0975,
        "longitude": 80.1610,
        "vicinity": "3rd Main Rd, Ambattur Industrial Estate, West Chennai"
    },
    {
        "place_id": "POI-FIRE-06",
        "name": "Tambaram Sub-Divisional Fire Station",
        "type": "fire_station",
        "latitude": 12.9249,
        "longitude": 80.1172,
        "vicinity": "GST Road, Tambaram Sanatorium, South Corridor"
    },
    {
        "place_id": "POI-FIRE-07",
        "name": "Koyambedu Wholesale Market Fire Station",
        "type": "fire_station",
        "latitude": 13.0694,
        "longitude": 80.1912,
        "vicinity": "Market Inner Rd, Koyambedu, West Chennai"
    },
    {
        "place_id": "POI-FIRE-08",
        "name": "Thiruvanmiyur Coastal Fire Post",
        "type": "fire_station",
        "latitude": 12.9830,
        "longitude": 80.2594,
        "vicinity": "East Coast Road (ECR), Thiruvanmiyur, Coastal South"
    },
    {
        "place_id": "POI-FIRE-09",
        "name": "T. Nagar Commercial Corridor Fire Station",
        "type": "fire_station",
        "latitude": 13.0418,
        "longitude": 80.2337,
        "vicinity": "Venkatnarayana Rd, T. Nagar, Central Chennai"
    },
    {
        "place_id": "POI-FIRE-10",
        "name": "Ennore Thermal & Port Fire Station",
        "type": "fire_station",
        "latitude": 13.2084,
        "longitude": 80.3255,
        "vicinity": "Ennore Express Highway, Ennore Port, North Chennai"
    },

    # --- POLICE STATIONS & TACTICAL HUBS ---
    {
        "place_id": "POI-POL-01",
        "name": "Greater Chennai Police Commissionerate HQ",
        "type": "police",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "vicinity": "EVK Sampath Rd, Vepery, Central Chennai"
    },
    {
        "place_id": "POI-POL-02",
        "name": "Anna Salai Law & Order Command Post",
        "type": "police",
        "latitude": 13.0550,
        "longitude": 80.2550,
        "vicinity": "Mount Road, Teynampet, Central Chennai"
    },
    {
        "place_id": "POI-POL-03",
        "name": "Velachery Emergency Response Police Substation",
        "type": "police",
        "latitude": 12.9791,
        "longitude": 80.2185,
        "vicinity": "100 Feet Bypass Rd, Velachery, South Chennai"
    },
    {
        "place_id": "POI-POL-04",
        "name": "Anna Nagar West Tactical Police Outpost",
        "type": "police",
        "latitude": 13.0850,
        "longitude": 80.2101,
        "vicinity": "2nd Avenue, Anna Nagar, West-Central Chennai"
    },
    {
        "place_id": "POI-POL-05",
        "name": "T. Nagar Police Station & Quick Reaction Hub",
        "type": "police",
        "latitude": 13.0392,
        "longitude": 80.2312,
        "vicinity": "Thyagaraya Rd, T. Nagar, Central Chennai"
    },
    {
        "place_id": "POI-POL-06",
        "name": "Adyar Law & Order Division Police Station",
        "type": "police",
        "latitude": 13.0033,
        "longitude": 80.2558,
        "vicinity": "Lattice Bridge Rd, Adyar, South Chennai"
    },
    {
        "place_id": "POI-POL-07",
        "name": "Koyambedu Inter-State Transit Police Post",
        "type": "police",
        "latitude": 13.0678,
        "longitude": 80.1985,
        "vicinity": "CMBT Bus Terminal Corridor, Koyambedu, West Chennai"
    },
    {
        "place_id": "POI-POL-08",
        "name": "Marina Coastal Security Police Station",
        "type": "police",
        "latitude": 13.0520,
        "longitude": 80.2825,
        "vicinity": "Kamarajar Salai, Marina Beach Promenade, Coastal Central"
    },
    {
        "place_id": "POI-POL-09",
        "name": "Royapettah Divisional Police Station",
        "type": "police",
        "latitude": 13.0565,
        "longitude": 80.2642,
        "vicinity": "Westcott Rd, Royapettah, Central Chennai"
    },
    {
        "place_id": "POI-POL-10",
        "name": "Tambaram Police Commissionerate Tactical Post",
        "type": "police",
        "latitude": 12.9260,
        "longitude": 80.1235,
        "vicinity": "Murasoli Maran Salai, Tambaram, South Corridor"
    },

    # --- SRIPERUMBUDUR & SIPCOT REGION ---
    {
        "place_id": "POI-FIRE-SPB",
        "name": "Sriperumbudur Fire & Rescue Operations Station",
        "type": "fire_station",
        "latitude": 12.9682,
        "longitude": 79.9431,
        "vicinity": "Bangalore Highway NH48, Sriperumbudur Central"
    },
    {
        "place_id": "POI-FIRE-IRK",
        "name": "Irungattukottai SIPCOT Industrial Fire & Hazmat Base",
        "type": "fire_station",
        "latitude": 12.9865,
        "longitude": 79.9925,
        "vicinity": "SIPCOT Industrial Complex, Irungattukottai"
    },
    {
        "place_id": "POI-POL-SPB",
        "name": "Sriperumbudur Police Station & Highway Cordon Hub",
        "type": "police",
        "latitude": 12.9668,
        "longitude": 79.9465,
        "vicinity": "Gandhi Road, Sriperumbudur"
    },
    {
        "place_id": "POI-POL-IRK",
        "name": "Irungattukottai SIPCOT Police Outpost",
        "type": "police",
        "latitude": 12.9840,
        "longitude": 79.9880,
        "vicinity": "NH48 Expressway Junction, Irungattukottai"
    },
    {
        "place_id": "POI-HOSP-SPB",
        "name": "Govt Taluk Hospital Sriperumbudur Trauma Care",
        "type": "hospital",
        "latitude": 12.9645,
        "longitude": 79.9490,
        "vicinity": "Taluk Office Road, Sriperumbudur"
    },

    # --- ORAGADAM INDUSTRIAL CORRIDOR ---
    {
        "place_id": "POI-FIRE-ORG",
        "name": "Oragadam Mega Industrial Fire Station",
        "type": "fire_station",
        "latitude": 12.8365,
        "longitude": 79.9545,
        "vicinity": "SH57, Oragadam Auto Corridor"
    },
    {
        "place_id": "POI-POL-ORG",
        "name": "Oragadam Police Station & Industrial Security Post",
        "type": "police",
        "latitude": 12.8380,
        "longitude": 79.9580,
        "vicinity": "Oragadam Junction, Kanchipuram"
    },
    {
        "place_id": "POI-HOSP-ORG",
        "name": "Oragadam Industrial Emergency Care Hospital",
        "type": "hospital",
        "latitude": 12.8350,
        "longitude": 79.9520,
        "vicinity": "Vallam Vadagal Industrial Area, Oragadam"
    },

    # --- POONAMALLEE & KUNDRATHUR SUBURBS ---
    {
        "place_id": "POI-FIRE-PNM",
        "name": "Poonamallee Fire & Rescue Station",
        "type": "fire_station",
        "latitude": 13.0489,
        "longitude": 80.1102,
        "vicinity": "Trunk Road, Poonamallee West"
    },
    {
        "place_id": "POI-POL-PNM",
        "name": "Poonamallee Police Station & Highway Patrol",
        "type": "police",
        "latitude": 13.0505,
        "longitude": 80.1080,
        "vicinity": "NH48 Junction, Poonamallee"
    },
    {
        "place_id": "POI-HOSP-PNM",
        "name": "Govt Hospital Poonamallee Trauma Center",
        "type": "hospital",
        "latitude": 13.0465,
        "longitude": 80.1125,
        "vicinity": "Hospital Road, Poonamallee"
    },
    {
        "place_id": "POI-POL-KND",
        "name": "Kundrathur Police Station",
        "type": "police",
        "latitude": 12.9980,
        "longitude": 80.0960,
        "vicinity": "Kundrathur Main Road, Chennai"
    },
    {
        "place_id": "POI-FIRE-KND",
        "name": "Kundrathur Suburban Fire & Water Rescue Post",
        "type": "fire_station",
        "latitude": 12.9960,
        "longitude": 80.0940,
        "vicinity": "Chembarambakkam Channel, Kundrathur"
    },

    # --- KANCHIPURAM & CHENGALPATTU HUBS ---
    {
        "place_id": "POI-FIRE-KPM",
        "name": "Kanchipuram Central Fire & Rescue Command",
        "type": "fire_station",
        "latitude": 12.8342,
        "longitude": 79.7036,
        "vicinity": "Gandhi Road, Kanchipuram Central"
    },
    {
        "place_id": "POI-HOSP-KPM",
        "name": "Kanchipuram District Headquarters Hospital",
        "type": "hospital",
        "latitude": 12.8380,
        "longitude": 79.7080,
        "vicinity": "Railway Station Road, Kanchipuram"
    },
    {
        "place_id": "POI-FIRE-CPT",
        "name": "Chengalpattu Fire & Rescue Station",
        "type": "fire_station",
        "latitude": 12.6840,
        "longitude": 79.9830,
        "vicinity": "GST Road, Chengalpattu"
    },
    {
        "place_id": "POI-HOSP-CPT",
        "name": "Chengalpattu Govt Medical College & Trauma Super-Specialty",
        "type": "hospital",
        "latitude": 12.6890,
        "longitude": 79.9880,
        "vicinity": "Medical College Road, Chengalpattu"
    },

    # --- COIMBATORE & KONGU HUB ---
    {
        "place_id": "POI-FIRE-CBE",
        "name": "Coimbatore South Central Fire Station",
        "type": "fire_station",
        "latitude": 11.0168,
        "longitude": 76.9558,
        "vicinity": "State Bank Rd, Coimbatore Central"
    },
    {
        "place_id": "POI-POL-CBE",
        "name": "Coimbatore City Police Commissionerate",
        "type": "police",
        "latitude": 11.0020,
        "longitude": 76.9630,
        "vicinity": "Huzur Rd, Gopalapuram, Coimbatore"
    },
    {
        "place_id": "POI-HOSP-CBE",
        "name": "Coimbatore Medical College Hospital (CMCH)",
        "type": "hospital",
        "latitude": 11.0015,
        "longitude": 76.9720,
        "vicinity": "Trichy Rd, Coimbatore"
    },

    # --- MADURAI & SOUTHERN COMMAND ---
    {
        "place_id": "POI-FIRE-MDU",
        "name": "Madurai Central Fire & Rescue Station",
        "type": "fire_station",
        "latitude": 9.9252,
        "longitude": 78.1198,
        "vicinity": "Periyar Bus Stand Rd, Madurai Central"
    },
    {
        "place_id": "POI-POL-MDU",
        "name": "Madurai City Police Commissionerate",
        "type": "police",
        "latitude": 9.9320,
        "longitude": 78.1380,
        "vicinity": "Alagar Kovil Rd, Madurai"
    },
    {
        "place_id": "POI-HOSP-MDU",
        "name": "Govt Rajaji Hospital & Trauma Care",
        "type": "hospital",
        "latitude": 9.9290,
        "longitude": 78.1340,
        "vicinity": "Panagal Rd, Shenoy Nagar, Madurai"
    },

    # --- TIRUCHIRAPPALLI / TRICHY & CAUVERY DELTA ---
    {
        "place_id": "POI-FIRE-TRY",
        "name": "Trichy Cantonment Fire Station",
        "type": "fire_station",
        "latitude": 10.7905,
        "longitude": 78.7047,
        "vicinity": "Collector Office Rd, Cantonment, Trichy"
    },
    {
        "place_id": "POI-HOSP-TRY",
        "name": "Mahatma Gandhi Memorial Govt Hospital Trichy",
        "type": "hospital",
        "latitude": 10.8120,
        "longitude": 78.6940,
        "vicinity": "Collectorate Rd, Trichy"
    },

    # --- SALEM & NORTH-CENTRAL HUB ---
    {
        "place_id": "POI-FIRE-SLM",
        "name": "Salem Central Fire & Rescue Station",
        "type": "fire_station",
        "latitude": 11.6643,
        "longitude": 78.1460,
        "vicinity": "Bretts Rd, Salem Central"
    },
    {
        "place_id": "POI-HOSP-SLM",
        "name": "Govt Mohan Kumaramangalam Medical College Hospital",
        "type": "hospital",
        "latitude": 11.6620,
        "longitude": 78.1480,
        "vicinity": "Fort Main Rd, Salem"
    },

    # --- TIRUNELVELI & DEEP SOUTH ---
    {
        "place_id": "POI-FIRE-TNV",
        "name": "Tirunelveli Junction Fire Station",
        "type": "fire_station",
        "latitude": 8.7139,
        "longitude": 77.7567,
        "vicinity": "Railway Station Rd, Tirunelveli"
    },
    {
        "place_id": "POI-HOSP-TNV",
        "name": "Tirunelveli Govt Medical College Hospital",
        "type": "hospital",
        "latitude": 8.7110,
        "longitude": 77.7420,
        "vicinity": "High Ground, Palayamkottai, Tirunelveli"
    },

    # --- TIRUPPUR & ERODE TEXTILE BELT ---
    {
        "place_id": "POI-FIRE-TPR",
        "name": "Tiruppur North Fire & Rescue Station",
        "type": "fire_station",
        "latitude": 11.1085,
        "longitude": 77.3411,
        "vicinity": "Avinashi Rd, Tiruppur"
    },
    {
        "place_id": "POI-FIRE-ERD",
        "name": "Erode Central Fire & Rescue Station",
        "type": "fire_station",
        "latitude": 11.3410,
        "longitude": 77.7172,
        "vicinity": "Brough Rd, Erode"
    },

    # --- VELLORE FORT & MEDICAL SECTOR ---
    {
        "place_id": "POI-FIRE-VEL",
        "name": "Vellore Central Fire Station",
        "type": "fire_station",
        "latitude": 12.9165,
        "longitude": 79.1325,
        "vicinity": "Officer's Line, Vellore Fort Sector"
    },
    {
        "place_id": "POI-HOSP-VEL",
        "name": "Christian Medical College (CMC) & Trauma Center",
        "type": "hospital",
        "latitude": 12.9240,
        "longitude": 79.1340,
        "vicinity": "Ida Scudder Rd, Vellore"
    },

    # --- THOOTHUKUDI / TUTICORIN PORT ---
    {
        "place_id": "POI-FIRE-TUT",
        "name": "Tuticorin Port & Industrial Fire Station",
        "type": "fire_station",
        "latitude": 8.7642,
        "longitude": 78.1348,
        "vicinity": "Harbour Estate, Tuticorin"
    },
    {
        "place_id": "POI-HOSP-TUT",
        "name": "Thoothukudi Govt Medical College Hospital",
        "type": "hospital",
        "latitude": 8.7710,
        "longitude": 78.1310,
        "vicinity": "3rd Mile, Kamaraj Nagar, Thoothukudi"
    },

    # --- CUDDALORE & NAGAPATTINAM COASTAL DELTA ---
    {
        "place_id": "POI-FIRE-CUD",
        "name": "Cuddalore Port & Coastal Fire Station",
        "type": "fire_station",
        "latitude": 11.7480,
        "longitude": 79.7714,
        "vicinity": "Sub Jail Rd, Cuddalore OT"
    },
    {
        "place_id": "POI-FIRE-NGP",
        "name": "Nagapattinam Cyclone & Coastal Rescue Station",
        "type": "fire_station",
        "latitude": 10.7672,
        "longitude": 79.8438,
        "vicinity": "Public Office Rd, Nagapattinam"
    },

    # --- HOSUR SIPCOT BELT ---
    {
        "place_id": "POI-FIRE-HOS",
        "name": "Hosur SIPCOT Industrial Fire Station",
        "type": "fire_station",
        "latitude": 12.7409,
        "longitude": 77.8253,
        "vicinity": "SIPCOT Phase 1, Hosur"
    },

    # --- SIVAKASI HAZARD BELT ---
    {
        "place_id": "POI-FIRE-SVK",
        "name": "Sivakasi Chemical & Pyrotechnic Fire Station",
        "type": "fire_station",
        "latitude": 9.4533,
        "longitude": 77.7967,
        "vicinity": "Sattur Rd, Sivakasi"
    },

    # --- KANYAKUMARI & NAGERCOIL ---
    {
        "place_id": "POI-FIRE-KK",
        "name": "Nagercoil Central Fire & Rescue Station",
        "type": "fire_station",
        "latitude": 8.1833,
        "longitude": 77.4119,
        "vicinity": "KP Rd, Nagercoil Central"
    },

    # --- NILGIRIS / OOTY HILL COMMAND ---
    {
        "place_id": "POI-FIRE-OTY",
        "name": "Ooty Mountain & Landslide Rescue Station",
        "type": "fire_station",
        "latitude": 11.4102,
        "longitude": 76.6950,
        "vicinity": "Commercial Rd, Ooty, Nilgiris"
    }
]



def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in kilometers."""
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def _cache_get(key: str):
    entry = _cache.get(key)
    if entry:
        ts, value = entry
        if time.time() - ts < CACHE_TTL:
            return value
        else:
            del _cache[key]
    return None

def _cache_set(key: str, value: any):
    _cache[key] = (time.time(), value)

def _is_valid_api_key() -> bool:
    return bool(GOOGLE_MAPS_API_KEY and not GOOGLE_MAPS_API_KEY.startswith("YOUR_") and len(GOOGLE_MAPS_API_KEY) > 10)

def fetch_poi(lat: float, lng: float, radius: int = 5000) -> List[Dict]:
    """
    Fetch nearby police, fire station, and hospital POIs using Google Places API.
    Falls back to pre-seeded geospatial POIs within radius if API key is not active.
    """
    cache_key = f"poi:{round(lat, 4)}:{round(lng, 4)}:{radius}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    results = []
    types = ["hospital", "police", "fire_station"]

    if _is_valid_api_key():
        try:
            for place_type in types:
                resp = requests.get(
                    BASE_PLACES_URL,
                    params={
                        "key": GOOGLE_MAPS_API_KEY,
                        "location": f"{lat},{lng}",
                        "radius": radius,
                        "type": place_type
                    },
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    if status in ["OK", "ZERO_RESULTS"]:
                        for p in data.get("results", []):
                            loc = p.get("geometry", {}).get("location", {})
                            p_lat = loc.get("lat", lat)
                            p_lng = loc.get("lng", lng)
                            dist = haversine_distance(lat, lng, p_lat, p_lng)
                            results.append({
                                "place_id": p.get("place_id"),
                                "name": p.get("name"),
                                "type": place_type,
                                "latitude": p_lat,
                                "longitude": p_lng,
                                "vicinity": p.get("vicinity") or p.get("formatted_address", ""),
                                "distance_km": round(dist, 2)
                            })
                    else:
                        logger.warning(f"Google Places API returned status {status}: {data.get('error_message')}")
        except Exception as e:
            logger.warning(f"Google Places request failed: {e}. Using pre-seeded dataset.")

    # If no results (or no key/network), filter preseeded POIs by radius or return closest
    if not results:
        for poi in PRESEEDED_POIS:
            dist = haversine_distance(lat, lng, poi["latitude"], poi["longitude"])
            radius_km = radius / 1000.0
            # Include if within radius or top 6 closest
            results.append({
                **poi,
                "distance_km": round(dist, 2)
            })
        results.sort(key=lambda x: x["distance_km"])
        # Filter within radius, or if none within radius, keep the closest 6
        filtered = [p for p in results if p["distance_km"] <= (radius / 1000.0)]
        results = filtered if filtered else results[:6]

    _cache_set(cache_key, results)
    return results

def generate_synthetic_polyline(origin: Tuple[float, float], destination: Tuple[float, float]) -> List[List[float]]:
    """Generates an interpolated multi-point road path between two coordinates."""
    lat1, lon1 = origin
    lat2, lon2 = destination
    steps = 6
    path = []
    for i in range(steps + 1):
        t = i / steps
        # Add slight realistic road deflection
        curve = math.sin(t * math.pi) * 0.002
        lat = lat1 + (lat2 - lat1) * t + curve
        lon = lon1 + (lon2 - lon1) * t - curve
        path.append([round(lat, 5), round(lon, 5)])
    return path

def get_route(origin: Tuple[float, float], destination: Tuple[float, float]) -> Dict:
    """
    Get directions between two points.
    Returns a dict with polyline (encoded or point array), distance (meters), duration (seconds), and human ETA.
    """
    cache_key = f"route:{round(origin[0],4)},{round(origin[1],4)}:{round(destination[0],4)},{round(destination[1],4)}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    dist_km = haversine_distance(origin[0], origin[1], destination[0], destination[1])
    # Estimate speed: 45 km/h for emergency vehicle in urban setting
    est_duration_sec = max(60, int((dist_km / 45.0) * 3600))
    est_distance_m = int(dist_km * 1000)

    result = {
        "polyline": "",
        "coordinates": generate_synthetic_polyline(origin, destination),
        "distance_m": est_distance_m,
        "duration_s": est_duration_sec,
        "eta_minutes": max(1, round(est_duration_sec / 60)),
        "distance_km": round(dist_km, 2)
    }

    if _is_valid_api_key():
        try:
            params = {
                "key": GOOGLE_MAPS_API_KEY,
                "origin": f"{origin[0]},{origin[1]}",
                "destination": f"{destination[0]},{destination[1]}",
                "mode": "driving"
            }
            resp = requests.get(BASE_DIRECTIONS_URL, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "OK" and data.get("routes"):
                    route = data["routes"][0]
                    leg = route["legs"][0]
                    result["polyline"] = route.get("overview_polyline", {}).get("points", "")
                    result["distance_m"] = leg.get("distance", {}).get("value", est_distance_m)
                    result["duration_s"] = leg.get("duration", {}).get("value", est_duration_sec)
                    result["eta_minutes"] = max(1, round(result["duration_s"] / 60))
                    result["distance_km"] = round(result["distance_m"] / 1000.0, 2)
                    if "overview_polyline" in route and "points" in route["overview_polyline"]:
                        result["polyline"] = route["overview_polyline"]["points"]
        except Exception as e:
            logger.warning(f"Google Directions API call failed: {e}. Using fallback calculated route.")

    _cache_set(cache_key, result)
    return result
