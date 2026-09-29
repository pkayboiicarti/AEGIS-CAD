import re
import hashlib
import logging
import urllib.request
import urllib.parse
import json
from typing import Tuple, Optional, List, Dict, Any

logger = logging.getLogger("cad.geocoding")

# In-memory LRU-style cache for online geocode lookups
_GEOCODE_CACHE: Dict[str, Tuple[float, float]] = {}

# Comprehensive Tamil Nadu Statewide Gazetteer (Colleges, Universities, Tech Hubs, Hospitals, Districts)
GAZETTEER: Dict[str, Tuple[float, float]] = {
    # --- UNIVERSITIES & HIGHER EDUCATION INSTITUTIONS (TAMIL NADU) ---
    "snu": (12.7533, 80.1970),
    "snuc": (12.7533, 80.1970),
    "snu chennai": (12.7533, 80.1970),
    "shiv nadar": (12.7533, 80.1970),
    "shiv nadar university": (12.7533, 80.1970),
    "shiv nadar university chennai": (12.7533, 80.1970),
    "ssn": (12.7509, 80.1973),
    "ssn college": (12.7509, 80.1973),
    "ssn college of engineering": (12.7509, 80.1973),
    "ssnce": (12.7509, 80.1973),
    "iit madras": (12.9915, 80.2337),
    "iitm": (12.9915, 80.2337),
    "anna university": (13.0102, 80.2354),
    "ceg": (13.0125, 80.2350),
    "college of engineering guindy": (13.0125, 80.2350),
    "mit chromepet": (12.9482, 80.1400),
    "madras institute of technology": (12.9482, 80.1400),
    "srm": (12.8230, 80.0450),
    "srm university": (12.8230, 80.0450),
    "srm kattankulathur": (12.8230, 80.0450),
    "srm ist": (12.8230, 80.0450),
    "srm ramapuram": (13.0322, 80.1805),
    "vit chennai": (12.8406, 80.1534),
    "vit vellore": (12.9692, 79.1559),
    "vellore institute of technology": (12.9692, 79.1559),
    "sathyabama": (12.8719, 80.2195),
    "sathyabama university": (12.8719, 80.2195),
    "sathyabama institute": (12.8719, 80.2195),
    "hindustan university": (12.8398, 80.2223),
    "hindustan institute of technology": (12.8398, 80.2223),
    "hits padur": (12.8398, 80.2223),
    "crescent": (12.8753, 80.0844),
    "crescent university": (12.8753, 80.0844),
    "bs abdur rahman": (12.8753, 80.0844),
    "st joseph": (12.8687, 80.2185),
    "st. joseph": (12.8687, 80.2185),
    "st joseph's college of engineering": (12.8687, 80.2185),
    "panimalar": (13.0532, 80.0768),
    "panimalar engineering college": (13.0532, 80.0768),
    "saveetha": (13.0280, 80.0170),
    "saveetha university": (13.0280, 80.0170),
    "saveetha engineering college": (13.0280, 80.0170),
    "simats": (13.0280, 80.0170),
    "rajalakshmi": (13.0085, 79.9705),
    "rajalakshmi engineering college": (13.0085, 79.9705),
    "rec thandalam": (13.0085, 79.9705),
    "svce": (12.9880, 79.9720),
    "sri venkateswara college of engineering": (12.9880, 79.9720),
    "loyola": (13.0645, 80.2330),
    "loyola college": (13.0645, 80.2330),
    "madras christian college": (12.9213, 80.1228),
    "mcc tambaram": (12.9213, 80.1228),
    "dg vaishnav": (13.0760, 80.2140),
    "presidency college": (13.0570, 80.2810),
    "ethiraj college": (13.0610, 80.2560),
    "stella maris": (13.0470, 80.2520),
    "psg tech": (11.0244, 77.0028),
    "psg college of technology": (11.0244, 77.0028),
    "cit coimbatore": (11.0290, 77.0270),
    "coimbatore institute of technology": (11.0290, 77.0270),
    "amrita coimbatore": (10.9000, 76.9000),
    "amrita university": (10.9000, 76.9000),
    "thiagarajar": (9.8820, 78.0820),
    "thiagarajar college of engineering": (9.8820, 78.0820),
    "tce madurai": (9.8820, 78.0820),
    "sastra": (10.7280, 79.0180),
    "sastra university": (10.7280, 79.0180),
    "nit trichy": (10.7600, 78.8140),
    "national institute of technology trichy": (10.7600, 78.8140),
    "bharathidasan university": (10.6970, 78.7430),
    "alagappa university": (10.0760, 78.7840),
    "madurai kamaraj university": (9.9400, 78.0100),
    "manonmaniam sundaranar university": (8.7180, 77.6700),
    "bharathiar university": (11.0370, 76.8770),
    "chettinad health city": (12.7930, 80.2190),
    "care hospital kelambakkam": (12.7930, 80.2190),

    # --- MAJOR TRANSIT & LOGISTICS HUBS ---
    "kilambakkam": (12.8630, 80.0760),
    "kcbt": (12.8630, 80.0760),
    "kalaignar centenary bus terminus": (12.8630, 80.0760),
    "koyambedu": (13.0694, 80.1912),
    "cmbt": (13.0694, 80.1912),
    "koyambedu bus stand": (13.0694, 80.1912),
    "chennai central": (13.0823, 80.2755),
    "mgr central": (13.0823, 80.2755),
    "puratchi thalaivar dr mgr central": (13.0823, 80.2755),
    "egmore": (13.0784, 80.2604),
    "egmore railway station": (13.0784, 80.2604),
    "chennai airport": (12.9941, 80.1709),
    "meenambakkam airport": (12.9941, 80.1709),
    "tambaram railway": (12.9250, 80.1200),
    "guindy metro": (13.0090, 80.2130),
    "airport metro": (12.9940, 80.1700),
    "ennore port": (13.2667, 80.3333),
    "kamarajar port": (13.2667, 80.3333),
    "chennai port": (13.0850, 80.2980),

    # --- IT CORRIDORS & INDUSTRIAL PARKS ---
    "siruseri": (12.8330, 80.2180),
    "siruseri sipcot": (12.8330, 80.2180),
    "sipcot siruseri": (12.8330, 80.2180),
    "tidel park": (12.9890, 80.2480),
    "taramani": (12.9860, 80.2430),
    "ascendas": (12.9870, 80.2450),
    "international tech park chennai": (12.9870, 80.2450),
    "olympia tech park": (13.0130, 80.2070),
    "dlf porur": (13.0290, 80.1690),
    "dlf cybercity": (13.0290, 80.1690),
    "ramanujan it city": (12.9880, 80.2460),
    "elcot sezone": (12.9000, 80.2280),
    "elcot sholinganallur": (12.9000, 80.2280),
    "mahindra world city": (12.7480, 80.0050),
    "oragadam": (12.8365, 79.9545),
    "sriperumbudur sipcot": (12.9675, 79.9431),
    "irungattukottai sipcot": (12.9865, 79.9925),
    "manali petrochem": (13.1673, 80.2644),
    "manali industrial": (13.1673, 80.2644),

    # --- MAJOR HOSPITALS ---
    "apollo greams road": (13.0610, 80.2520),
    "apollo hospital": (13.0610, 80.2520),
    "apollo omr": (12.9450, 80.2350),
    "apollo speciality vanagaram": (13.0450, 80.1450),
    "miot hospital": (13.0220, 80.1870),
    "miot international": (13.0220, 80.1870),
    "sims hospital": (13.0510, 80.2120),
    "fortis malar": (13.0060, 80.2570),
    "kauvery hospital": (13.0370, 80.2540),
    "gleneagles global health city": (12.8980, 80.1980),
    "stanley medical college": (13.1070, 80.2870),
    "rajiv gandhi hospital": (13.0800, 80.2780),
    "rgggh": (13.0800, 80.2780),
    "kilpauk medical college": (13.0780, 80.2430),
    "cmc vellore": (12.9250, 79.1350),
    "christian medical college": (12.9250, 79.1350),

    # --- GREATER CHENNAI LOCALITIES ---
    "chennai": (13.0827, 80.2707),
    "velachery": (12.9791, 80.2185),
    "tambaram": (12.9249, 80.1275),
    "chromepet": (12.9516, 80.1462),
    "pallavaram": (12.9675, 80.1491),
    "omr": (12.8797, 80.2280),
    "ecr": (12.8452, 80.2458),
    "sholinganallur": (12.9010, 80.2275),
    "perungudi": (12.9650, 80.2420),
    "thoraipakkam": (12.9370, 80.2330),
    "navalur": (12.8460, 80.2260),
    "kelambakkam": (12.7870, 80.2190),
    "kalavakkam": (12.7533, 80.1970),
    "thiruporur": (12.7230, 80.1870),
    "kovalam": (12.7920, 80.2520),
    "guindy": (13.0067, 80.2024),
    "adyar": (13.0012, 80.2565),
    "marina beach": (13.0500, 80.2824),
    "besant nagar": (12.9980, 80.2700),
    "eliots beach": (12.9980, 80.2700),
    "anna nagar": (13.0850, 80.2101),
    "t nagar": (13.0418, 80.2341),
    "mylapore": (13.0336, 80.2676),
    "alwarpet": (13.0340, 80.2500),
    "nungambakkam": (13.0590, 80.2420),
    "vadapalani": (13.0500, 80.2120),
    "porur": (13.0382, 80.1565),
    "porur toll gate": (13.0382, 80.1565),
    "ramapuram": (13.0300, 80.1800),
    "valasaravakkam": (13.0400, 80.1700),
    "virugambakkam": (13.0490, 80.1920),
    "kk nagar": (13.0380, 80.1970),
    "ashok nagar": (13.0360, 80.2120),
    "saidapet": (13.0210, 80.2230),
    "triplicane": (13.0580, 80.2770),
    "royapettah": (13.0550, 80.2620),
    "purasawalkam": (13.0900, 80.2560),
    "perambur": (13.1120, 80.2400),
    "villivakkam": (13.1070, 80.2050),
    "kolathur": (13.1230, 80.2170),
    "madhavaram": (13.1480, 80.2310),
    "manali": (13.1673, 80.2644),
    "ennore": (13.2084, 80.3255),
    "red hills": (13.1970, 80.1860),
    "ambattur": (13.0975, 80.1610),
    "avadi": (13.1143, 80.1000),
    "pattabiram": (13.1220, 80.0580),
    "thiruninravur": (13.1180, 80.0240),
    "poonamallee": (13.0489, 80.1102),
    "thirumazhisai": (13.0560, 80.0600),
    "kundrathur": (12.9980, 80.0960),
    "mangadu": (13.0260, 80.1130),
    "madipakkam": (12.9640, 80.1980),
    "medavakkam": (12.9180, 80.1920),
    "perumbakkam": (12.8980, 80.1880),
    "kovilambakkam": (12.9400, 80.1900),
    "guduvanchery": (12.8450, 80.0640),
    "maraimalai nagar": (12.7930, 80.0250),
    "singaperumal koil": (12.7630, 80.0020),
    "chengalpattu": (12.6840, 79.9830),
    "kanchipuram": (12.8342, 79.7036),
    "sriperumbudur": (12.9675, 79.9431),
    "mahabalipuram": (12.6208, 80.1944),
    "mamallapuram": (12.6208, 80.1944),
    "kalpakkam": (12.5030, 80.1620),

    # --- NORTHERN TAMIL NADU ---
    "tiruvallur": (13.1438, 79.9080),
    "gummidipoondi": (13.4072, 80.1292),
    "ponneri": (13.3220, 80.2000),
    "vellore": (12.9165, 79.1325),
    "ranipet": (12.9270, 79.3330),
    "walajapet": (12.9300, 79.3800),
    "arakkonam": (13.0780, 79.6680),
    "arcot": (12.9050, 79.3350),
    "tirupathur": (12.4950, 78.5670),
    "vaniyambadi": (12.6820, 78.6180),
    "ambur": (12.7900, 78.7160),
    "tiruvannamalai": (12.2253, 79.0747),
    "arani": (12.6680, 79.2840),
    "cheyyar": (12.6580, 79.5420),

    # --- WESTERN / KONGU TAMIL NADU ---
    "coimbatore": (11.0168, 76.9558),
    "gandhipuram": (11.0183, 76.9644),
    "peelamedu": (11.0280, 77.0140),
    "saravanampatti": (11.0780, 76.9980),
    "rs puram": (11.0080, 76.9500),
    "singanallur": (10.9990, 77.0250),
    "saibaba colony": (11.0340, 76.9460),
    "pollachi": (10.6609, 77.0048),
    "mettupalayam": (11.3000, 76.9500),
    "tiruppur": (11.1085, 77.3411),
    "avanshi": (11.1920, 77.2710),
    "avinashi": (11.1920, 77.2710),
    "palladam": (10.9990, 77.2880),
    "dharapuram": (10.7300, 77.5300),
    "kangeyam": (11.0050, 77.5600),
    "erode": (11.3410, 77.7172),
    "perundurai": (11.2770, 77.5830),
    "gobichettipalayam": (11.4550, 77.4370),
    "bhavani": (11.4480, 77.6830),
    "sathyamangalam": (11.5030, 77.2340),
    "salem": (11.6643, 78.1460),
    "mettur": (11.7960, 77.8000),
    "mettur dam": (11.8020, 77.8050),
    "attur": (11.5970, 78.5990),
    "edappadi": (11.5830, 77.8480),
    "namakkal": (11.2189, 78.1674),
    "rasipuram": (11.4640, 78.1750),
    "tiruchengode": (11.3780, 77.8930),
    "kumarapalayam": (11.4420, 77.7180),
    "dharmapuri": (12.1211, 78.1582),
    "harur": (12.0600, 78.4900),
    "hogenakkal": (12.1180, 77.7770),
    "krishnagiri": (12.5186, 78.2138),
    "hosur": (12.7409, 77.8253),
    "denkanikottai": (12.5270, 77.7850),
    "nilgiris": (11.4102, 76.6950),
    "ooty": (11.4102, 76.6950),
    "udhagamandalam": (11.4102, 76.6950),
    "coonoor": (11.3530, 76.7959),
    "kotagiri": (11.4200, 76.8800),
    "gudalur": (11.5050, 76.4950),

    # --- CENTRAL & CAUVERY DELTA REGION ---
    "tiruchirappalli": (10.7905, 78.7047),
    "trichy": (10.7905, 78.7047),
    "srirangam": (10.8620, 78.6900),
    "thuvakudi": (10.7550, 78.8050),
    "bhel trichy": (10.7700, 78.7900),
    "manapparai": (10.6080, 78.4170),
    "thanjavur": (10.7870, 79.1378),
    "kumbakonam": (10.9602, 79.3845),
    "papanasam": (10.9230, 79.2770),
    "pattukkottai": (10.4280, 79.3170),
    "karur": (10.9601, 78.0766),
    "kulithalai": (10.9320, 78.4230),
    "perambalur": (11.2342, 78.8817),
    "ariyalur": (11.1401, 79.0786),
    "jayankondam": (11.2150, 79.3480),
    "pudukkottai": (10.3797, 78.8208),
    "aranthangi": (10.1650, 78.9950),
    "cuddalore": (11.7480, 79.7714),
    "cuddalore port": (11.7100, 79.7700),
    "neyveli": (11.5975, 79.4861),
    "chidambaram": (11.3992, 79.6934),
    "virudhachalam": (11.5030, 79.3280),
    "panruti": (11.7700, 79.5530),
    "nagapattinam": (10.7672, 79.8438),
    "velankanni": (10.6811, 79.8434),
    "nagore": (10.8200, 79.8440),
    "mayiladuthurai": (11.1075, 79.6523),
    "sirkazhi": (11.2380, 79.7330),
    "poompuhar": (11.1460, 79.8550),
    "tiruvarur": (10.7725, 79.6365),
    "mannargudi": (10.6650, 79.4450),
    "thiruthuraipoondi": (10.5330, 79.6450),
    "kallakurichi": (11.7380, 78.9600),
    "tirukkoyilur": (11.9560, 79.2000),
    "ulundurpet": (11.6900, 79.2900),

    # --- SOUTHERN TAMIL NADU ---
    "madurai": (9.9252, 78.1198),
    "meenakshi amman temple": (9.9195, 78.1193),
    "thiruparankundram": (9.8800, 78.0700),
    "mattuthavani": (9.9440, 78.1560),
    "goripalayam": (9.9320, 78.1300),
    "anna nagar madurai": (9.9230, 78.1480),
    "dindigul": (10.3673, 77.9803),
    "kodaikanal": (10.2381, 77.4892),
    "palani": (10.4500, 77.5200),
    "oddanchatram": (10.4780, 77.7470),
    "theni": (10.0104, 77.4768),
    "bodinayakanur": (10.0100, 77.3500),
    "periyakulam": (10.1180, 77.5450),
    "cumbum": (9.7340, 77.2830),
    "virudhunagar": (9.5680, 77.9624),
    "sivakasi": (9.4533, 77.7967),
    "rajapalayam": (9.4530, 77.5540),
    "srivilliputhur": (9.5100, 77.6330),
    "aruppukkottai": (9.5120, 78.0980),
    "ramanathapuram": (9.3639, 78.8395),
    "rameswaram": (9.2876, 79.3129),
    "dhanushkodi": (9.1770, 79.4180),
    "paramakudi": (9.5440, 78.5900),
    "kilakarai": (9.2310, 78.7840),
    "thoothukudi": (8.7642, 78.1348),
    "tuticorin": (8.7642, 78.1348),
    "tuticorin port": (8.7500, 78.1800),
    "tiruchendur": (8.4980, 78.1250),
    "kovilpatti": (9.1740, 77.8680),
    "kayalpattinam": (8.5680, 78.1290),
    "tirunelveli": (8.7139, 77.7567),
    "palayamkottai": (8.7190, 77.7400),
    "ambasamudram": (8.7070, 77.4570),
    "tenkasi": (8.9594, 77.3149),
    "courtallam": (8.9320, 77.2760),
    "sankarankovil": (9.1720, 77.5350),
    "kadayanallur": (9.0740, 77.3480),
    "kanyakumari": (8.0883, 77.5385),
    "nagercoil": (8.1833, 77.4119),
    "padmanabhapuram": (8.2430, 77.3990),
    "marthandam": (8.3050, 77.2280),
    "colachel": (8.1750, 77.2560),
    "thuckalay": (8.2430, 77.3610)
}


def extract_coordinates_from_text(text: str) -> Optional[Tuple[float, float]]:
    """Extract explicit GPS coordinates from string like '13.0827, 80.2707' or 'lat: 13.0, lon: 80.2'"""
    if not text:
        return None
    coord_pattern = r'[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)'
    match = re.search(coord_pattern, text)
    if match:
        parts = match.group(0).replace('(', '').replace(')', '').split(',')
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            return (lat, lon)
        except ValueError:
            pass
    return None


def search_landmarks(query: str, limit: int = 6) -> List[Dict[str, Any]]:
    """Search gazetteer landmarks and colleges matching user query for frontend autocomplete"""
    if not query or len(query.strip()) < 2:
        return []
    
    q = query.lower().strip()
    results = []
    seen = set()

    # Exact or prefix matches first
    for key, (lat, lng) in GAZETTEER.items():
        if key.startswith(q) or q in key:
            label = key.title()
            if label not in seen:
                seen.add(label)
                results.append({
                    "name": label,
                    "lat": lat,
                    "lng": lng,
                    "category": "COLLEGE" if any(w in key for w in ["college", "university", "iit", "snu", "ssn", "mit", "srm", "vit", "ceg", "institute"]) else "LANDMARK"
                })
                if len(results) >= limit:
                    return results

    # Substring token match
    q_tokens = [t for t in q.split() if len(t) > 1]
    for key, (lat, lng) in GAZETTEER.items():
        if any(t in key for t in q_tokens):
            label = key.title()
            if label not in seen:
                seen.add(label)
                results.append({
                    "name": label,
                    "lat": lat,
                    "lng": lng,
                    "category": "COLLEGE" if any(w in key for w in ["college", "university", "iit", "snu", "ssn", "mit", "srm", "vit", "ceg", "institute"]) else "LANDMARK"
                })
                if len(results) >= limit:
                    break

    return results


def _lookup_nominatim_online(location_query: str) -> Optional[Tuple[float, float]]:
    """Query OpenStreetMap Nominatim API with Tamil Nadu bounding box bias (cached)"""
    clean_q = location_query.strip()
    if clean_q in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[clean_q]

    try:
        # Bias search to Tamil Nadu (south 8.0, north 13.6, west 76.2, east 80.4)
        params = urllib.parse.urlencode({
            "q": f"{clean_q}, Tamil Nadu, India",
            "format": "json",
            "limit": "1",
            "countrycodes": "in",
            "viewbox": "76.2,13.6,80.4,8.0",
            "bounded": "0"
        })
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AegisCAD-DisasterIngestion/2.5 (DisasterRescueTN)"}
        )
        with urllib.request.urlopen(req, timeout=1.8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data and len(data) > 0:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    _GEOCODE_CACHE[clean_q] = (lat, lon)
                    logger.info(f"Nominatim Geocoded '{clean_q}' -> ({lat}, {lon})")
                    return (lat, lon)
    except Exception as e:
        logger.debug(f"Nominatim lookup skipped for '{clean_q}': {e}")
    return None


def resolve_location_coordinates(location_name: str, metadata: Optional[str] = None) -> Tuple[float, float]:
    """
    Resolve location to latitude and longitude.
    Checks:
    1. Raw coordinates in metadata/location_name
    2. Exact word boundary or substring match against extensive Tamil Nadu Gazetteer (colleges, landmarks, hubs)
    3. Online OSM Nominatim lookup with Tamil Nadu bias
    4. Deterministic localized hash spread
    """
    # 1. Check if metadata contains raw coordinates
    if metadata:
        meta_coords = extract_coordinates_from_text(metadata)
        if meta_coords:
            return meta_coords
            
    # 2. Check if location_name contains raw coordinates
    loc_coords = extract_coordinates_from_text(location_name)
    if loc_coords:
        return loc_coords

    combined_text = f"{(location_name or '')} {(metadata or '')}".lower().strip()

    # 3. Match Gazetteer with priority for longest matching key and exact word tokens
    clean_loc = (location_name or "").lower().strip()
    
    # Sort gazetteer keys by length descending to match specific institutions first (e.g., 'snu chennai' before 'chennai')
    sorted_keys = sorted(GAZETTEER.keys(), key=lambda k: len(k), reverse=True)
    
    for key in sorted_keys:
        # Check whole word match or key contained in location
        if key in clean_loc or key in combined_text:
            coords = GAZETTEER[key]
            # Add micro jitter (within 200m) so multiple distinct reports don't stack completely
            hash_val = int(hashlib.md5(clean_loc.encode()).hexdigest()[:6], 16)
            jitter_lat = ((hash_val % 100) - 50) * 0.00015
            jitter_lon = (((hash_val >> 8) % 100) - 50) * 0.00015
            return (round(coords[0] + jitter_lat, 5), round(coords[1] + jitter_lon, 5))

    # 4. Check online Nominatim if location query looks like a valid landmark/address
    if len(clean_loc) >= 4 and not clean_loc.startswith("unspecified") and not clean_loc.startswith("least"):
        online_coords = _lookup_nominatim_online(clean_loc)
        if online_coords:
            return online_coords

    # 5. Default anchor (Chennai CAD Sector) with deterministic spread
    hash_val = int(hashlib.md5((clean_loc or "default").encode()).hexdigest()[:8], 16)
    base_lat, base_lon = 13.0827, 80.2707
    offset_lat = ((hash_val % 1000) - 500) * 0.0001
    offset_lon = (((hash_val >> 10) % 1000) - 500) * 0.0001
    return (round(base_lat + offset_lat, 5), round(base_lon + offset_lon, 5))


def is_within_tamil_nadu(lat: float, lon: float) -> bool:
    """
    Checks if coordinates fall strictly within Tamil Nadu operational bounding box:
    Latitude: 8.0° N to 13.6° N
    Longitude: 76.2° E to 80.4° E
    """
    try:
        return 8.0 <= float(lat) <= 13.6 and 76.2 <= float(lon) <= 80.4
    except (ValueError, TypeError):
        return False

