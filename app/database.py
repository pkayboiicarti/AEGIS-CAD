import aiosqlite
import json
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.models import IncidentRecord, EmergencyUnit, SystemStats, DisasterType, SeverityLevel, EmergencyStation, ResponseUnit


if os.getenv("VERCEL"):
    DB_PATH = "/tmp/cad_disaster.db"
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "cad_disaster.db")

DEFAULT_UNITS = [
    {
        "id": "NDRF-TN-04",
        "name": "NDRF 04 Battalion Alpha SAR Team",
        "type": "NDRF_RESCUE",
        "status": "AVAILABLE",
        "station_name": "State Emergency Operations & NDRF HQ",
        "latitude": 13.0645,
        "longitude": 80.2812,
        "assigned_incident_id": None,
        "contact_callsign": "EAGLE-ALPHA",
        "personnel_count": 24
    },
    {
        "id": "NDRF-TN-09",
        "name": "NDRF Rapid Flood & Deep Water Unit",
        "type": "NDRF_RESCUE",
        "status": "AVAILABLE",
        "station_name": "Velachery Coastal Patrol Post",
        "latitude": 12.9791,
        "longitude": 80.2185,
        "assigned_incident_id": None,
        "contact_callsign": "EAGLE-BRAVO",
        "personnel_count": 18
    },
    {
        "id": "FIRE-BR-01",
        "name": "Heavy Skylift & Aerial Ladder Engine 101",
        "type": "FIRE_ENGINE",
        "status": "AVAILABLE",
        "station_name": "Egmore Central Fire Command",
        "latitude": 13.0784,
        "longitude": 80.2604,
        "assigned_incident_id": None,
        "contact_callsign": "BLAZE-RED",
        "personnel_count": 8
    },
    {
        "id": "FIRE-BR-02",
        "name": "Chemical Hazmat Foam Tender Unit 204",
        "type": "FIRE_ENGINE",
        "status": "AVAILABLE",
        "station_name": "Manali Industrial Hazmat Base",
        "latitude": 13.1673,
        "longitude": 80.2644,
        "assigned_incident_id": None,
        "contact_callsign": "HAZMAT-1",
        "personnel_count": 6
    },
    {
        "id": "FIRE-BR-03",
        "name": "Industrial Quick Response Fire Tender 303",
        "type": "FIRE_ENGINE",
        "status": "AVAILABLE",
        "station_name": "Guindy Industrial Fire Station",
        "latitude": 13.0067,
        "longitude": 80.2024,
        "assigned_incident_id": None,
        "contact_callsign": "BLAZE-SOUTH",
        "personnel_count": 7
    },
    {
        "id": "FIRE-BR-04",
        "name": "High-Volume Water Cannon Tender 402",
        "type": "FIRE_ENGINE",
        "status": "AVAILABLE",
        "station_name": "Ambattur Industrial Estate Base",
        "latitude": 13.0975,
        "longitude": 80.1610,
        "assigned_incident_id": None,
        "contact_callsign": "BLAZE-WEST",
        "personnel_count": 6
    },
    {
        "id": "EMS-ALS-08",
        "name": "108 Critical Care ALS Ambulance ALS-08",
        "type": "AMBULANCE_ALS",
        "status": "AVAILABLE",
        "station_name": "Rajiv Gandhi Govt General Hospital",
        "latitude": 13.0818,
        "longitude": 80.2789,
        "assigned_incident_id": None,
        "contact_callsign": "MEDIC-8",
        "personnel_count": 3
    },
    {
        "id": "EMS-ALS-14",
        "name": "108 Advanced Cardiac & Trauma ALS-14",
        "type": "AMBULANCE_ALS",
        "status": "AVAILABLE",
        "station_name": "Apollo Hospitals Emergency Center",
        "latitude": 13.0607,
        "longitude": 80.2514,
        "assigned_incident_id": None,
        "contact_callsign": "MEDIC-14",
        "personnel_count": 3
    },
    {
        "id": "SDRF-BOAT-02",
        "name": "SDRF Coastal & Flood Inflatable Boat Unit",
        "type": "BOAT_RESCUE",
        "status": "AVAILABLE",
        "station_name": "Velachery Coastal Patrol Post",
        "latitude": 12.9791,
        "longitude": 80.2185,
        "assigned_incident_id": None,
        "contact_callsign": "NEPTUNE-2",
        "personnel_count": 6
    },
    {
        "id": "DRONE-RECON-01",
        "name": "Thermal FLIR Disaster Recon Drone Squad",
        "type": "DRONE_RECON",
        "status": "AVAILABLE",
        "station_name": "State Emergency Operations & NDRF HQ",
        "latitude": 13.0645,
        "longitude": 80.2812,
        "assigned_incident_id": None,
        "contact_callsign": "SKYEYE-1",
        "personnel_count": 2
    },
    {
        "id": "POL-TAC-12",
        "name": "Law & Order Traffic Evacuation Patrol 12",
        "type": "POLICE_PATROL",
        "status": "AVAILABLE",
        "station_name": "Anna Salai Law & Order Hub",
        "latitude": 13.0550,
        "longitude": 80.2550,
        "assigned_incident_id": None,
        "contact_callsign": "DELTA-12",
        "personnel_count": 4
    },
    {
        "id": "POL-TAC-07",
        "name": "Metro Perimeter Cordon & Security Patrol 07",
        "type": "POLICE_PATROL",
        "status": "AVAILABLE",
        "station_name": "Greater Chennai Police Commissionerate",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "assigned_incident_id": None,
        "contact_callsign": "DELTA-07",
        "personnel_count": 4
    }
]


async def init_db():
    """Create tables and initialize standard CAD data schema"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            raw_text TEXT,
            channel TEXT,
            metadata_info TEXT,
            is_relevant INTEGER,
            confidence_score REAL,
            rejection_reason TEXT,
            title TEXT,
            type TEXT,
            severity TEXT,
            urgency_score INTEGER,
            location_name TEXT,
            latitude REAL,
            longitude REAL,
            affected_injured INTEGER,
            affected_trapped INTEGER,
            affected_evacuated INTEGER,
            affected_total INTEGER,
            casualty_summary TEXT,
            actionable_notes TEXT,
            status TEXT,
            dispatched_units TEXT,
            timeline TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS units (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            status TEXT,
            station_name TEXT,
            latitude REAL,
            longitude REAL,
            assigned_incident_id TEXT,
            contact_callsign TEXT,
            personnel_count INTEGER
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS stations (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            latitude REAL,
            longitude REAL,
            address TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS response_units (
            id TEXT PRIMARY KEY,
            call_sign TEXT,
            unit_type TEXT,
            station_id TEXT,
            latitude REAL,
            longitude REAL,
            status TEXT,
            assigned_incident_id TEXT,
            personnel_count INTEGER,
            equipment TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            incident_id TEXT,
            details TEXT
        )
        """)

        async with db.execute("SELECT COUNT(*) FROM units") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                for u in DEFAULT_UNITS:
                    await db.execute("""
                    INSERT INTO units (id, name, type, status, station_name, latitude, longitude, assigned_incident_id, contact_callsign, personnel_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        u["id"], u["name"], u["type"], u["status"], u["station_name"],
                        u["latitude"], u["longitude"], u["assigned_incident_id"],
                        u["contact_callsign"], u["personnel_count"]
                    ))

        # Seed comprehensive stations across Chennai Metropolitan, Sriperumbudur, Oragadam, Poonamallee, Kanchipuram & Chengalpattu
        default_stations = [
            # Central & Inner Chennai
            {"id": "STN-FIRE-01", "name": "Egmore Central Fire Command Station", "type": "FIRE", "latitude": 13.0784, "longitude": 80.2604, "address": "Pantheon Rd, Egmore, Central Chennai"},
            {"id": "STN-FIRE-02", "name": "Manali Industrial Hazmat Fire Base", "type": "FIRE", "latitude": 13.1673, "longitude": 80.2644, "address": "CPCL Industrial Corridor, Manali, North Chennai"},
            {"id": "STN-FIRE-03", "name": "Guindy Industrial Estate Fire Station", "type": "FIRE", "latitude": 13.0067, "longitude": 80.2024, "address": "Inner Ring Rd, Guindy, South-Central Chennai"},
            {"id": "STN-FIRE-04", "name": "Ambattur Industrial Estate Heavy Base", "type": "FIRE", "latitude": 13.0975, "longitude": 80.1610, "address": "3rd Main Rd, Ambattur Industrial Estate, West Chennai"},
            {"id": "STN-FIRE-05", "name": "Mylapore Divisional Fire Station", "type": "FIRE", "latitude": 13.0336, "longitude": 80.2676, "address": "Luz Church Rd, Mylapore, South Chennai"},
            {"id": "STN-FIRE-09", "name": "T. Nagar Fire & Rescue Station", "type": "FIRE", "latitude": 13.0418, "longitude": 80.2337, "address": "Venkatnarayana Rd, T. Nagar, Central Chennai"},
            
            # Sriperumbudur & SIPCOT Industrial Sector (West)
            {"id": "STN-FIRE-SPB-01", "name": "Sriperumbudur Fire & Rescue Station", "type": "FIRE", "latitude": 12.9682, "longitude": 79.9431, "address": "Bangalore Highway NH48, Sriperumbudur Central"},
            {"id": "STN-FIRE-IRK-01", "name": "Irungattukottai SIPCOT Hazmat Fire Base", "type": "FIRE", "latitude": 12.9865, "longitude": 79.9925, "address": "SIPCOT Industrial Complex, Irungattukottai"},
            {"id": "STN-POL-SPB-01", "name": "Sriperumbudur Police Station & Highway Patrol", "type": "POLICE", "latitude": 12.9668, "longitude": 79.9465, "address": "Gandhi Road, Sriperumbudur"},
            {"id": "STN-POL-IRK-01", "name": "Irungattukottai SIPCOT Police Outpost", "type": "POLICE", "latitude": 12.9840, "longitude": 79.9880, "address": "NH48 Expressway Junction, Irungattukottai"},
            {"id": "STN-HOSP-SPB-01", "name": "Govt Taluk Hospital Sriperumbudur Trauma Center", "type": "HOSPITAL", "latitude": 12.9645, "longitude": 79.9490, "address": "Taluk Office Road, Sriperumbudur"},
            {"id": "STN-NDRF-SPB-01", "name": "NDRF 4th Battalion Sriperumbudur Base", "type": "DISASTER_MGMT", "latitude": 12.9710, "longitude": 79.9380, "address": "SIPCOT Industrial Complex, Sriperumbudur"},

            # Oragadam Industrial Belt (South-West)
            {"id": "STN-FIRE-ORG-01", "name": "Oragadam Mega Industrial Fire Station", "type": "FIRE", "latitude": 12.8365, "longitude": 79.9545, "address": "State Highway 57, Oragadam Auto Hub"},
            {"id": "STN-POL-ORG-01", "name": "Oragadam Police Station & Industrial Command", "type": "POLICE", "latitude": 12.8380, "longitude": 79.9580, "address": "Oragadam Junction, Kanchipuram District"},
            {"id": "STN-HOSP-ORG-01", "name": "Oragadam Industrial Emergency Care Hospital", "type": "HOSPITAL", "latitude": 12.8350, "longitude": 79.9520, "address": "Vallam Vadagal Industrial Area, Oragadam"},

            # Poonamallee & Thirumazhisai Sector (West)
            {"id": "STN-FIRE-PNM-01", "name": "Poonamallee Fire & Rescue Station", "type": "FIRE", "latitude": 13.0489, "longitude": 80.1102, "address": "Trunk Road, Poonamallee West"},
            {"id": "STN-POL-PNM-01", "name": "Poonamallee Police Station & Traffic Post", "type": "POLICE", "latitude": 13.0505, "longitude": 80.1080, "address": "NH48 Junction, Poonamallee"},
            {"id": "STN-HOSP-PNM-01", "name": "Govt Hospital Poonamallee & Emergency Unit", "type": "HOSPITAL", "latitude": 13.0465, "longitude": 80.1125, "address": "Hospital Road, Poonamallee"},

            # Kundrathur & Chembarambakkam Sector
            {"id": "STN-FIRE-KND-01", "name": "Kundrathur Suburban Fire & Water Rescue Post", "type": "FIRE", "latitude": 12.9960, "longitude": 80.0940, "address": "Near Chembarambakkam Channel, Kundrathur"},
            {"id": "STN-POL-KND-01", "name": "Kundrathur Police Station", "type": "POLICE", "latitude": 12.9980, "longitude": 80.0960, "address": "Kundrathur Main Road, Chennai Suburban"},

            # Tambaram & Chromepet Sector (South)
            {"id": "STN-FIRE-TBM-01", "name": "Tambaram Fire & Rescue Station", "type": "FIRE", "latitude": 12.9249, "longitude": 80.1275, "address": "GST Road, Tambaram Sanatorium"},
            {"id": "STN-POL-TBM-01", "name": "Tambaram Police Commissionerate Tactical Hub", "type": "POLICE", "latitude": 12.9260, "longitude": 80.1300, "address": "Murasoli Maran Salai, Tambaram"},
            {"id": "STN-HOSP-TBM-01", "name": "Govt Hospital of Thoracic Medicine & Emergency", "type": "HOSPITAL", "latitude": 12.9310, "longitude": 80.1220, "address": "GST Road, Tambaram Sanatorium"},

            # Avadi & Pattabiram Sector (North-West)
            {"id": "STN-FIRE-AVD-01", "name": "Avadi Heavy Fire & Emergency Base", "type": "FIRE", "latitude": 13.1143, "longitude": 80.1000, "address": "CTH Road, Avadi West"},
            {"id": "STN-POL-AVD-01", "name": "Avadi Police Commissionerate Headquarters", "type": "POLICE", "latitude": 13.1180, "longitude": 80.1050, "address": "Avadi Heavy Vehicles Corridor"},

            # Kanchipuram District Central Command (West)
            {"id": "STN-FIRE-KPM-01", "name": "Kanchipuram Central Fire & Rescue Station", "type": "FIRE", "latitude": 12.8342, "longitude": 79.7036, "address": "Gandhi Road, Kanchipuram Central"},
            {"id": "STN-POL-KPM-01", "name": "Kanchipuram District Police Headquarters", "type": "POLICE", "latitude": 12.8360, "longitude": 79.7050, "address": "Collectorate Complex, Kanchipuram"},
            {"id": "STN-HOSP-KPM-01", "name": "Kanchipuram Govt District Headquarters Hospital", "type": "HOSPITAL", "latitude": 12.8380, "longitude": 79.7080, "address": "Railway Station Road, Kanchipuram"},

            # Chengalpattu Sector (South)
            {"id": "STN-FIRE-CPT-01", "name": "Chengalpattu Fire & Rescue Station", "type": "FIRE", "latitude": 12.6840, "longitude": 79.9830, "address": "GST Road, Chengalpattu"},
            {"id": "STN-POL-CPT-01", "name": "Chengalpattu Town Police Station", "type": "POLICE", "latitude": 12.6860, "longitude": 79.9850, "address": "Alagesan Nagar, Chengalpattu"},
            {"id": "STN-HOSP-CPT-01", "name": "Chengalpattu Govt Medical College & Super-Specialty", "type": "HOSPITAL", "latitude": 12.6890, "longitude": 79.9880, "address": "Medical College Road, Chengalpattu"},

            # OMR / ECR Technology Corridor (South-East)
            {"id": "STN-FIRE-OMR-01", "name": "Siruseri SIPCOT IT Corridor Fire Station", "type": "FIRE", "latitude": 12.8330, "longitude": 80.2180, "address": "SIPCOT IT Park, Siruseri, OMR"},
            {"id": "STN-POL-OMR-01", "name": "Sholinganallur Police Station & IT Command", "type": "POLICE", "latitude": 12.9010, "longitude": 80.2275, "address": "OMR Junction, Sholinganallur"},

            # Coimbatore District Central Command (West)
            {"id": "STN-FIRE-CBE-01", "name": "Coimbatore South Central Fire Station", "type": "FIRE", "latitude": 11.0168, "longitude": 76.9558, "address": "State Bank Rd, Coimbatore Central"},
            {"id": "STN-POL-CBE-01", "name": "Coimbatore City Police Commissionerate", "type": "POLICE", "latitude": 11.0020, "longitude": 76.9630, "address": "Huzur Rd, Gopalapuram, Coimbatore"},
            {"id": "STN-HOSP-CBE-01", "name": "Coimbatore Medical College Hospital (CMCH)", "type": "HOSPITAL", "latitude": 11.0015, "longitude": 76.9720, "address": "Trichy Rd, Coimbatore"},
            {"id": "STN-NDRF-CBE-01", "name": "SDRF Western Zone Quick Response Hub", "type": "DISASTER_MGMT", "latitude": 11.0280, "longitude": 77.0140, "address": "Peelamedu, Coimbatore"},

            # Madurai District Central Command (South)
            {"id": "STN-FIRE-MDU-01", "name": "Madurai Central Fire & Rescue Station", "type": "FIRE", "latitude": 9.9252, "longitude": 78.1198, "address": "Periyar Bus Stand Rd, Madurai Central"},
            {"id": "STN-POL-MDU-01", "name": "Madurai City Police Commissionerate", "type": "POLICE", "latitude": 9.9320, "longitude": 78.1380, "address": "Alagar Kovil Rd, Madurai"},
            {"id": "STN-HOSP-MDU-01", "name": "Govt Rajaji Hospital & Trauma Super-Specialty", "type": "HOSPITAL", "latitude": 9.9290, "longitude": 78.1340, "address": "Panagal Rd, Shenoy Nagar, Madurai"},
            {"id": "STN-NDRF-MDU-01", "name": "NDRF Southern Zone Response Post", "type": "DISASTER_MGMT", "latitude": 9.9190, "longitude": 78.1450, "address": "K.K. Nagar, Madurai"},

            # Tiruchirappalli / Trichy (Central)
            {"id": "STN-FIRE-TRY-01", "name": "Trichy Cantonment Fire & Rescue Station", "type": "FIRE", "latitude": 10.7905, "longitude": 78.7047, "address": "Collector Office Rd, Cantonment, Trichy"},
            {"id": "STN-POL-TRY-01", "name": "Tiruchirappalli City Police Commissionerate", "type": "POLICE", "latitude": 10.8050, "longitude": 78.6880, "address": "Subramaniapuram, Trichy"},
            {"id": "STN-HOSP-TRY-01", "name": "Mahatma Gandhi Memorial Govt Hospital", "type": "HOSPITAL", "latitude": 10.8120, "longitude": 78.6940, "address": "Collectorate Rd, Trichy"},

            # Salem District (North-Central)
            {"id": "STN-FIRE-SLM-01", "name": "Salem Central Fire & Rescue Station", "type": "FIRE", "latitude": 11.6643, "longitude": 78.1460, "address": "Bretts Rd, Salem Central"},
            {"id": "STN-POL-SLM-01", "name": "Salem City Police Commissionerate", "type": "POLICE", "latitude": 11.6580, "longitude": 78.1520, "address": "Linemedu, Salem"},
            {"id": "STN-HOSP-SLM-01", "name": "Govt Mohan Kumaramangalam Medical College Hospital", "type": "HOSPITAL", "latitude": 11.6620, "longitude": 78.1480, "address": "Fort Main Rd, Salem"},

            # Tirunelveli District (Deep South)
            {"id": "STN-FIRE-TNV-01", "name": "Tirunelveli Junction Fire & Rescue Station", "type": "FIRE", "latitude": 8.7139, "longitude": 77.7567, "address": "Railway Station Rd, Tirunelveli"},
            {"id": "STN-POL-TNV-01", "name": "Tirunelveli City Police Commissionerate", "type": "POLICE", "latitude": 8.7280, "longitude": 77.7310, "address": "Palayamkottai, Tirunelveli"},
            {"id": "STN-HOSP-TNV-01", "name": "Tirunelveli Govt Medical College Hospital", "type": "HOSPITAL", "latitude": 8.7110, "longitude": 77.7420, "address": "High Ground, Palayamkottai"},

            # Tiruppur & Erode Textile Corridor
            {"id": "STN-FIRE-TPR-01", "name": "Tiruppur North Fire & Rescue Station", "type": "FIRE", "latitude": 11.1085, "longitude": 77.3411, "address": "Avinashi Rd, Tiruppur"},
            {"id": "STN-POL-TPR-01", "name": "Tiruppur City Police Commissionerate", "type": "POLICE", "latitude": 11.1150, "longitude": 77.3520, "address": "Kumaran Rd, Tiruppur"},
            {"id": "STN-FIRE-ERD-01", "name": "Erode Central Fire & Rescue Station", "type": "FIRE", "latitude": 11.3410, "longitude": 77.7172, "address": "Brough Rd, Erode"},
            {"id": "STN-POL-ERD-01", "name": "Erode District Police Headquarters", "type": "POLICE", "latitude": 11.3450, "longitude": 77.7250, "address": "Panneerselvam Park, Erode"},

            # Vellore & Ranipet Industrial Belt
            {"id": "STN-FIRE-VEL-01", "name": "Vellore Central Fire Station", "type": "FIRE", "latitude": 12.9165, "longitude": 79.1325, "address": "Officer's Line, Vellore Fort Sector"},
            {"id": "STN-POL-VEL-01", "name": "Vellore District Police Headquarters", "type": "POLICE", "latitude": 12.9210, "longitude": 79.1380, "address": "Anna Salai, Vellore"},
            {"id": "STN-HOSP-VEL-01", "name": "Christian Medical College (CMC) & Trauma Center", "type": "HOSPITAL", "latitude": 12.9240, "longitude": 79.1340, "address": "Ida Scudder Rd, Vellore"},

            # Thoothukudi / Tuticorin Port City
            {"id": "STN-FIRE-TUT-01", "name": "Tuticorin Port & Industrial Fire Station", "type": "FIRE", "latitude": 8.7642, "longitude": 78.1348, "address": "Harbour Estate, Tuticorin"},
            {"id": "STN-POL-TUT-01", "name": "Thoothukudi Coastal Marine Police Post", "type": "POLICE", "latitude": 8.7580, "longitude": 78.1420, "address": "Beach Rd, Thoothukudi"},
            {"id": "STN-HOSP-TUT-01", "name": "Thoothukudi Govt Medical College Hospital", "type": "HOSPITAL", "latitude": 8.7710, "longitude": 78.1310, "address": "3rd Mile, Kamaraj Nagar, Thoothukudi"},

            # Cuddalore, Neyveli & Nagapattinam Coastal Delta
            {"id": "STN-FIRE-CUD-01", "name": "Cuddalore Port & Coastal Fire Station", "type": "FIRE", "latitude": 11.7480, "longitude": 79.7714, "address": "Sub Jail Rd, Cuddalore OT"},
            {"id": "STN-POL-CUD-01", "name": "Cuddalore District Police Headquarters", "type": "POLICE", "latitude": 11.7520, "longitude": 79.7650, "address": "Nellikuppam Main Rd, Cuddalore"},
            {"id": "STN-FIRE-NGP-01", "name": "Nagapattinam Cyclone & Coastal Rescue Station", "type": "FIRE", "latitude": 10.7672, "longitude": 79.8438, "address": "Public Office Rd, Nagapattinam"},
            {"id": "STN-POL-NGP-01", "name": "Nagapattinam Marine Police Command", "type": "POLICE", "latitude": 10.7710, "longitude": 79.8490, "address": "Beach Rd, Nagapattinam"},

            # Thanjavur & Delta Command
            {"id": "STN-FIRE-TNJ-01", "name": "Thanjavur Medical College Fire Station", "type": "FIRE", "latitude": 10.7870, "longitude": 79.1378, "address": "Medical College Rd, Thanjavur"},
            {"id": "STN-POL-TNJ-01", "name": "Thanjavur District Police Headquarters", "type": "POLICE", "latitude": 10.7920, "longitude": 79.1410, "address": "Court Rd, Thanjavur"},

            # Hosur SIPCOT Industrial Belt
            {"id": "STN-FIRE-HOS-01", "name": "Hosur SIPCOT Industrial Fire Station", "type": "FIRE", "latitude": 12.7409, "longitude": 77.8253, "address": "SIPCOT Phase 1, Hosur"},
            {"id": "STN-POL-HOS-01", "name": "Hosur Town Police Station & Highway Taskforce", "type": "POLICE", "latitude": 12.7350, "longitude": 77.8310, "address": "Bagalur Rd, Hosur"},

            # Dindigul & Kodaikanal Hill Command
            {"id": "STN-FIRE-DGL-01", "name": "Dindigul Central Fire & Rescue Base", "type": "FIRE", "latitude": 10.3673, "longitude": 77.9803, "address": "Salai Rd, Dindigul"},
            {"id": "STN-POL-DGL-01", "name": "Dindigul District Police Headquarters", "type": "POLICE", "latitude": 10.3710, "longitude": 77.9850, "address": "Trichy Rd, Dindigul"},

            # Sivakasi & Virudhunagar Pyrotechnic Hazard Belt
            {"id": "STN-FIRE-SVK-01", "name": "Sivakasi Heavy Chemical & Fire Station", "type": "FIRE", "latitude": 9.4533, "longitude": 77.7967, "address": "Sattur Rd, Sivakasi"},
            {"id": "STN-POL-SVK-01", "name": "Sivakasi Town Police Command", "type": "POLICE", "latitude": 9.4580, "longitude": 77.8010, "address": "Chairman Shanmuga Nadar Rd, Sivakasi"},

            # Kanyakumari / Nagercoil (Southern Tip)
            {"id": "STN-FIRE-KK-01", "name": "Nagercoil Central Fire & Rescue Station", "type": "FIRE", "latitude": 8.1833, "longitude": 77.4119, "address": "KP Rd, Nagercoil Central"},
            {"id": "STN-POL-KK-01", "name": "Kanyakumari District Police Headquarters", "type": "POLICE", "latitude": 8.1890, "longitude": 77.4200, "address": "Court Rd, Nagercoil"},

            # Nilgiris / Ooty Hill Disaster & Landslide Command
            {"id": "STN-FIRE-OTY-01", "name": "Ooty High-Altitude Fire & Landslide Rescue Station", "type": "FIRE", "latitude": 11.4102, "longitude": 76.6950, "address": "Commercial Rd, Ooty"},
            {"id": "STN-POL-OTY-01", "name": "Nilgiris District Police Headquarters", "type": "POLICE", "latitude": 11.4150, "longitude": 76.7020, "address": "Fingerpost, Ooty"},

            # Ramanathapuram & Rameswaram Coastal Command
            {"id": "STN-FIRE-RAM-01", "name": "Ramanathapuram Central Fire Station", "type": "FIRE", "latitude": 9.3639, "longitude": 78.8395, "address": "Vandikkara St, Ramanathapuram"},
            {"id": "STN-POL-RAM-01", "name": "Rameswaram Coastal & Marine Security Station", "type": "POLICE", "latitude": 9.2876, "longitude": 79.3129, "address": "Temple Rd, Rameswaram"},

            # Police & Hospital Central Base
            {"id": "STN-POL-01", "name": "Greater Chennai Police Commissionerate", "type": "POLICE", "latitude": 13.0827, "longitude": 80.2707, "address": "EVK Sampath Rd, Vepery, Central Chennai"},
            {"id": "STN-POL-02", "name": "Anna Salai Law & Order Command Post", "type": "POLICE", "latitude": 13.0550, "longitude": 80.2550, "address": "Mount Road, Teynampet, Central Chennai"},
            {"id": "STN-POL-03", "name": "Velachery Emergency Response Police Post", "type": "POLICE", "latitude": 12.9791, "longitude": 80.2185, "address": "100 Feet Bypass Rd, Velachery, South Chennai"},
            {"id": "STN-POL-04", "name": "Anna Nagar West Tactical Police Station", "type": "POLICE", "latitude": 13.0850, "longitude": 80.2101, "address": "2nd Avenue, Anna Nagar, West Chennai"},
            {"id": "STN-POL-05", "name": "Adyar Traffic & Law Enforcement Hub", "type": "POLICE", "latitude": 13.0033, "longitude": 80.2558, "address": "Lattice Bridge Rd, Adyar, South Chennai"},
            {"id": "STN-POL-06", "name": "T. Nagar Police Station & Reaction Hub", "type": "POLICE", "latitude": 13.0392, "longitude": 80.2312, "address": "Thyagaraya Rd, T. Nagar, Central Chennai"},
            {"id": "STN-HOSP-01", "name": "Rajiv Gandhi Govt General Hospital (RGGGH)", "type": "HOSPITAL", "latitude": 13.0818, "longitude": 80.2789, "address": "EVR Periyar Salai, Park Town, Central Chennai"},
            {"id": "STN-HOSP-02", "name": "Apollo Hospitals Main Greams Road", "type": "HOSPITAL", "latitude": 13.0607, "longitude": 80.2514, "address": "Greams Lane, Thousand Lights, Central Chennai"},
            {"id": "STN-HOSP-03", "name": "MIOT International Trauma Care Center", "type": "HOSPITAL", "latitude": 13.0189, "longitude": 80.1874, "address": "Mount-Poonamallee Rd, Manapakkam, South-West Chennai"},
            {"id": "STN-NDRF-01", "name": "State Emergency Operations & NDRF HQ", "type": "DISASTER_MGMT", "latitude": 13.0645, "longitude": 80.2812, "address": "Ezhilagam, Chepauk Coastal Hub, Chennai"}
        ]
        for s in default_stations:
            await db.execute("""
            INSERT OR REPLACE INTO stations (id, name, type, latitude, longitude, address)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (s["id"], s["name"], s["type"], s["latitude"], s["longitude"], s["address"]))

        # Seed response units across all regional stations
        default_resp_units = [
            # Sriperumbudur & SIPCOT Tactical Units
            {"id": "FIRE-BR-SPB-01", "call_sign": "BLAZE-SRIPERUMBUDUR", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-SPB-01", "latitude": 12.9682, "longitude": 79.9431, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Heavy Industrial Fire Tender, Foam Cannons, Thermal FLIR"},
            {"id": "POL-TAC-SPB-01", "call_sign": "DELTA-SRIPERUMBUDUR", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-SPB-01", "latitude": 12.9668, "longitude": 79.9465, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Highway Interceptor, Barrier Units, First Responder Kit"},
            {"id": "EMS-ALS-SPB-01", "call_sign": "MEDIC-SRIPERUMBUDUR", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-SPB-01", "latitude": 12.9645, "longitude": 79.9490, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Advanced Trauma Support, Oxygen Ventilator, Cardiac Monitor"},
            {"id": "NDRF-TN-SPB-01", "call_sign": "EAGLE-SRIPERUMBUDUR", "unit_type": "NDRF_RESCUE", "station_id": "STN-NDRF-SPB-01", "latitude": 12.9710, "longitude": 79.9380, "status": "AVAILABLE", "personnel_count": 20, "equipment": "Heavy Urban Search & Rescue, Extrication Cutters, Shoring Gear"},
            {"id": "FIRE-BR-IRK-01", "call_sign": "HAZMAT-IRUNGATTU", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-IRK-01", "latitude": 12.9865, "longitude": 79.9925, "status": "AVAILABLE", "personnel_count": 7, "equipment": "Chemical Gas Neutralizer, Heavy Foam Tender, SCBA Kits"},
            {"id": "POL-TAC-IRK-01", "call_sign": "DELTA-IRUNGATTU", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-IRK-01", "latitude": 12.9840, "longitude": 79.9880, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Industrial Corridor Patrol, Traffic Diversion Cordon"},

            # Oragadam Tactical Units
            {"id": "FIRE-BR-ORG-01", "call_sign": "BLAZE-ORAGADAM", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-ORG-01", "latitude": 12.8365, "longitude": 79.9545, "status": "AVAILABLE", "personnel_count": 8, "equipment": "High-Pressure Water Bowser, Industrial Hazmat Gear"},
            {"id": "POL-TAC-ORG-01", "call_sign": "DELTA-ORAGADAM", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-ORG-01", "latitude": 12.8380, "longitude": 79.9580, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Patrol Interceptor, Megaphones, Emergency Road Blocks"},

            # Poonamallee Tactical Units
            {"id": "FIRE-BR-PNM-01", "call_sign": "BLAZE-POONAMALLEE", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-PNM-01", "latitude": 13.0489, "longitude": 80.1102, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Rapid Fire Tender 501, High-Pressure Hoses, Thermal Sensor"},
            {"id": "POL-TAC-PNM-01", "call_sign": "DELTA-POONAMALLEE", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-PNM-01", "latitude": 13.0505, "longitude": 80.1080, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Highway Patrol Vehicle, Evacuation Escort Gear"},
            {"id": "EMS-ALS-PNM-01", "call_sign": "MEDIC-POONAMALLEE", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-PNM-01", "latitude": 13.0465, "longitude": 80.1125, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Trauma ALS, Portable Oxygen & Defibrillator"},

            # Kundrathur Tactical Units
            {"id": "FIRE-BR-KND-01", "call_sign": "BLAZE-KUNDRATHUR", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-KND-01", "latitude": 12.9960, "longitude": 80.0940, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Water Rescue Tender, High-Capacity Submersible Pumps"},
            {"id": "POL-TAC-KND-01", "call_sign": "DELTA-KUNDRATHUR", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-KND-01", "latitude": 12.9980, "longitude": 80.0960, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Suburban Cordon Vehicle, First Aid Kits"},
            {"id": "SDRF-BOAT-KND-01", "call_sign": "NEPTUNE-CHEMBARAM", "unit_type": "BOAT_RESCUE", "station_id": "STN-FIRE-KND-01", "latitude": 12.9960, "longitude": 80.0940, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Inflatable Zodiac Rescue Boats, Sonar, Diving Suits"},

            # Tambaram Tactical Units
            {"id": "FIRE-BR-TBM-01", "call_sign": "BLAZE-TAMBARAM", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-TBM-01", "latitude": 12.9249, "longitude": 80.1275, "status": "AVAILABLE", "personnel_count": 7, "equipment": "Heavy Water Bowser, 45m Turntable Ladder, Rescue Cutters"},
            {"id": "POL-TAC-TBM-01", "call_sign": "DELTA-TAMBARAM", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-TBM-01", "latitude": 12.9260, "longitude": 80.1300, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Commissionerate Patrol, Crowd Control & Tactical Barricades"},
            {"id": "EMS-ALS-TBM-01", "call_sign": "MEDIC-TAMBARAM", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-TBM-01", "latitude": 12.9310, "longitude": 80.1220, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Trauma & Respiratory Support ALS, Resuscitation Monitor"},

            # Avadi Tactical Units
            {"id": "FIRE-BR-AVD-01", "call_sign": "BLAZE-AVADI", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-AVD-01", "latitude": 13.1143, "longitude": 80.1000, "status": "AVAILABLE", "personnel_count": 6, "equipment": "High-Volume Water Tender 303, Smoke Extractors"},
            {"id": "POL-TAC-AVD-01", "call_sign": "DELTA-AVADI", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-AVD-01", "latitude": 13.1180, "longitude": 80.1050, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Patrol SUV, Traffic Control Gear, Megaphones"},

            # Kanchipuram Central Tactical Units
            {"id": "FIRE-BR-KPM-01", "call_sign": "BLAZE-KANCHIPURAM", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-KPM-01", "latitude": 12.8342, "longitude": 79.7036, "status": "AVAILABLE", "personnel_count": 7, "equipment": "Heavy District Fire Tender, Hydraulic Cutters"},
            {"id": "POL-TAC-KPM-01", "call_sign": "DELTA-KANCHIPURAM", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-KPM-01", "latitude": 12.8360, "longitude": 79.7050, "status": "AVAILABLE", "personnel_count": 4, "equipment": "District Taskforce Patrol, Perimeter Securing"},
            {"id": "EMS-ALS-KPM-01", "call_sign": "MEDIC-KANCHIPURAM", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-KPM-01", "latitude": 12.8380, "longitude": 79.7080, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Critical Care Ambulance, Defibrillator & Oxygen"},

            # Chengalpattu Tactical Units
            {"id": "FIRE-BR-CPT-01", "call_sign": "BLAZE-CHENGALPATTU", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-CPT-01", "latitude": 12.6840, "longitude": 79.9830, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Water Bowser & Rescue Tender, Thermal Scanners"},
            {"id": "POL-TAC-CPT-01", "call_sign": "DELTA-CHENGALPATTU", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-CPT-01", "latitude": 12.6860, "longitude": 79.9850, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Town Police Patrol, Emergency Flares & Cordon"},
            {"id": "EMS-ALS-CPT-01", "call_sign": "MEDIC-CHENGALPATTU", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-CPT-01", "latitude": 12.6890, "longitude": 79.9880, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Trauma & Resuscitation ALS, Mobile ECG"},

            # OMR / Siruseri Tactical Units
            {"id": "FIRE-BR-OMR-01", "call_sign": "BLAZE-SIRUSERI", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-OMR-01", "latitude": 12.8330, "longitude": 80.2180, "status": "AVAILABLE", "personnel_count": 6, "equipment": "IT Park Multi-Story Fire Tender, Foam Cannons"},
            {"id": "POL-TAC-OMR-01", "call_sign": "DELTA-SHOLINGANALLUR", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-OMR-01", "latitude": 12.9010, "longitude": 80.2275, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Expressway Patrol Interceptor, Speed Radar, Barricades"},

            # Coimbatore Tactical Units (West)
            {"id": "FIRE-BR-CBE-01", "call_sign": "BLAZE-COIMBATORE", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-CBE-01", "latitude": 11.0168, "longitude": 76.9558, "status": "AVAILABLE", "personnel_count": 8, "equipment": "Hydraulic Ladder 60m, High-Pressure Bowser, Foam Unit"},
            {"id": "POL-TAC-CBE-01", "call_sign": "DELTA-COIMBATORE", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-CBE-01", "latitude": 11.0020, "longitude": 76.9630, "status": "AVAILABLE", "personnel_count": 4, "equipment": "City Quick Reaction Team, Traffic Interceptor"},
            {"id": "EMS-ALS-CBE-01", "call_sign": "MEDIC-COIMBATORE", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-CBE-01", "latitude": 11.0015, "longitude": 76.9720, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Advanced Critical Care Ambulance, Defibrillator"},
            {"id": "SDRF-TN-CBE-01", "call_sign": "SDRF-KONGU", "unit_type": "SDRF_QUICK_RESPONSE", "station_id": "STN-NDRF-CBE-01", "latitude": 11.0280, "longitude": 77.0140, "status": "AVAILABLE", "personnel_count": 16, "equipment": "Hill & Urban Rescue Kit, Hydraulic Cutters, Quad Drones"},

            # Madurai Tactical Units (South)
            {"id": "FIRE-BR-MDU-01", "call_sign": "BLAZE-MADURAI", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-MDU-01", "latitude": 9.9252, "longitude": 78.1198, "status": "AVAILABLE", "personnel_count": 7, "equipment": "Heavy Water Tender, Rapid Rescue Equipment, High-Rise Foam"},
            {"id": "POL-TAC-MDU-01", "call_sign": "DELTA-MADURAI", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-MDU-01", "latitude": 9.9320, "longitude": 78.1380, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Commissionerate Patrol, Crowd Cordon Gear"},
            {"id": "EMS-ALS-MDU-01", "call_sign": "MEDIC-MADURAI", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-MDU-01", "latitude": 9.9290, "longitude": 78.1340, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Cardiac Trauma Support ALS, Portable Ventilator"},
            {"id": "NDRF-TN-MDU-01", "call_sign": "EAGLE-PANDYA", "unit_type": "NDRF_RESCUE", "station_id": "STN-NDRF-MDU-01", "latitude": 9.9190, "longitude": 78.1450, "status": "AVAILABLE", "personnel_count": 22, "equipment": "Heavy Collapsed Structure Search & Rescue, Acoustic Sensors"},

            # Tiruchirappalli / Trichy Tactical Units (Central)
            {"id": "FIRE-BR-TRY-01", "call_sign": "BLAZE-TRICHY", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-TRY-01", "latitude": 10.7905, "longitude": 78.7047, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Multi-Pressure Water Tender, Chemical Extinguisher Foam"},
            {"id": "POL-TAC-TRY-01", "call_sign": "DELTA-TRICHY", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-TRY-01", "latitude": 10.8050, "longitude": 78.6880, "status": "AVAILABLE", "personnel_count": 4, "equipment": "City Quick Reaction Team, Cordon Flares"},
            {"id": "EMS-ALS-TRY-01", "call_sign": "MEDIC-TRICHY", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-TRY-01", "latitude": 10.8120, "longitude": 78.6940, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Advanced Resuscitation Mobile Unit"},

            # Salem Tactical Units
            {"id": "FIRE-BR-SLM-01", "call_sign": "BLAZE-SALEM", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-SLM-01", "latitude": 11.6643, "longitude": 78.1460, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Heavy Water Bowser, Thermal Search Gear"},
            {"id": "POL-TAC-SLM-01", "call_sign": "DELTA-SALEM", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-SLM-01", "latitude": 11.6580, "longitude": 78.1520, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Law & Order Patrol, Riot & Traffic Cordon"},
            {"id": "EMS-ALS-SLM-01", "call_sign": "MEDIC-SALEM", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-SLM-01", "latitude": 11.6620, "longitude": 78.1480, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Trauma Life Support ALS, Mobile Oxygen"},

            # Tirunelveli Tactical Units
            {"id": "FIRE-BR-TNV-01", "call_sign": "BLAZE-TIRUNELVELI", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-TNV-01", "latitude": 8.7139, "longitude": 77.7567, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Flood & Fire Tender 601, River Rescue Kit"},
            {"id": "POL-TAC-TNV-01", "call_sign": "DELTA-TIRUNELVELI", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-TNV-01", "latitude": 8.7280, "longitude": 77.7310, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Highway Interceptor, First Aid Kit"},

            # Tiruppur & Erode Tactical Units
            {"id": "FIRE-BR-TPR-01", "call_sign": "BLAZE-TIRUPPUR", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-TPR-01", "latitude": 11.1085, "longitude": 77.3411, "status": "AVAILABLE", "personnel_count": 7, "equipment": "Industrial Textile Hazmat & Foam Tender"},
            {"id": "FIRE-BR-ERD-01", "call_sign": "BLAZE-ERODE", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-ERD-01", "latitude": 11.3410, "longitude": 77.7172, "status": "AVAILABLE", "personnel_count": 6, "equipment": "River Basin & Chemical Fire Tender"},

            # Vellore Tactical Units
            {"id": "FIRE-BR-VEL-01", "call_sign": "BLAZE-VELLORE", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-VEL-01", "latitude": 12.9165, "longitude": 79.1325, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Heavy Water Bowser, Skylift Ladder 45m"},
            {"id": "EMS-ALS-VEL-01", "call_sign": "MEDIC-VELLORE", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-VEL-01", "latitude": 12.9240, "longitude": 79.1340, "status": "AVAILABLE", "personnel_count": 3, "equipment": "CMC Trauma Super-Specialty Ambulance"},

            # Thoothukudi / Tuticorin Tactical Units
            {"id": "FIRE-BR-TUT-01", "call_sign": "BLAZE-TUTICORIN", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-TUT-01", "latitude": 8.7642, "longitude": 78.1348, "status": "AVAILABLE", "personnel_count": 8, "equipment": "Port Chemical & Oil Hazmat Fire Tender"},
            {"id": "SDRF-BOAT-TUT-01", "call_sign": "NEPTUNE-TUTICORIN", "unit_type": "BOAT_RESCUE", "station_id": "STN-POL-TUT-01", "latitude": 8.7580, "longitude": 78.1420, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Coastal Patrol Speedboats, Diving Gear"},

            # Cuddalore & Nagapattinam Coastal Tactical Units
            {"id": "FIRE-BR-CUD-01", "call_sign": "BLAZE-CUDDALORE", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-CUD-01", "latitude": 11.7480, "longitude": 79.7714, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Coastal Inundation & Industrial Fire Tender"},
            {"id": "SDRF-BOAT-NGP-01", "call_sign": "NEPTUNE-DELTA", "unit_type": "BOAT_RESCUE", "station_id": "STN-FIRE-NGP-01", "latitude": 10.7672, "longitude": 79.8438, "status": "AVAILABLE", "personnel_count": 8, "equipment": "Zodiac Flood Rescue Boats, Life Buoys, Sonar"},

            # Hosur Tactical Units
            {"id": "FIRE-BR-HOS-01", "call_sign": "BLAZE-HOSUR", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-HOS-01", "latitude": 12.7409, "longitude": 77.8253, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Automotive Industrial Fire Tender, Foam Cannons"},

            # Sivakasi Pyrotechnic Tactical Units
            {"id": "FIRE-BR-SVK-01", "call_sign": "HAZMAT-SIVAKASI", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-SVK-01", "latitude": 9.4533, "longitude": 77.7967, "status": "AVAILABLE", "personnel_count": 8, "equipment": "Chemical Blast Neutralizer, Heavy Foam Unit, SCBA"},

            # Kanyakumari Tactical Units
            {"id": "FIRE-BR-KK-01", "call_sign": "BLAZE-KANYAKUMARI", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-KK-01", "latitude": 8.1833, "longitude": 77.4119, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Coastal Wind Fire Tender, Heavy Pumps"},

            # Nilgiris / Ooty Hill Tactical Units
            {"id": "FIRE-BR-OTY-01", "call_sign": "BLAZE-NILGIRIS", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-OTY-01", "latitude": 11.4102, "longitude": 76.6950, "status": "AVAILABLE", "personnel_count": 8, "equipment": "All-Terrain 4x4 Mountain Rescue Tender, Landslide Cutters"},

            # Central Chennai Tactical Units
            {"id": "FIRE-BR-05", "call_sign": "BLAZE-TNAGAR", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-09", "latitude": 13.0418, "longitude": 80.2337, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Rapid Response Fire Tender, Foam Cannons, Thermal Camera"},
            {"id": "POL-TAC-05", "call_sign": "DELTA-TNAGAR", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-06", "latitude": 13.0392, "longitude": 80.2312, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Perimeter Cordon, Megaphones, Traffic Diversion Gear"},
            {"id": "EMS-ALS-05", "call_sign": "MEDIC-TNAGAR", "unit_type": "AMBULANCE_ALS", "station_id": "STN-FIRE-09", "latitude": 13.0410, "longitude": 80.2340, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Trauma ALS, Portable Oxygen & Defibrillator"},
            {"id": "NDRF-TN-04", "call_sign": "EAGLE-ALPHA", "unit_type": "NDRF_RESCUE", "station_id": "STN-NDRF-01", "latitude": 13.0645, "longitude": 80.2812, "status": "AVAILABLE", "personnel_count": 24, "equipment": "Heavy Extrication, Urban Search & Rescue, Inflatable Tents"},
            {"id": "NDRF-TN-09", "call_sign": "EAGLE-BRAVO", "unit_type": "NDRF_RESCUE", "station_id": "STN-POL-03", "latitude": 12.9791, "longitude": 80.2185, "status": "AVAILABLE", "personnel_count": 18, "equipment": "Flood Rescue Zodiac Boats, Sonar, Diving Gear"},
            {"id": "FIRE-BR-01", "call_sign": "BLAZE-RED", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-01", "latitude": 13.0784, "longitude": 80.2604, "status": "AVAILABLE", "personnel_count": 8, "equipment": "54m Hydraulic Skylift, Foam Cannon, Thermal Imaging FLIR"},
            {"id": "FIRE-BR-02", "call_sign": "HAZMAT-1", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-02", "latitude": 13.1673, "longitude": 80.2644, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Chemical Gas Scrubber, Heavy Hazmat Suits, SCBA Sets"},
            {"id": "FIRE-BR-03", "call_sign": "BLAZE-SOUTH", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-03", "latitude": 13.0067, "longitude": 80.2024, "status": "AVAILABLE", "personnel_count": 7, "equipment": "Water Bowsers, High-Pressure Pumping Gear, Cutting Torches"},
            {"id": "FIRE-BR-04", "call_sign": "BLAZE-WEST", "unit_type": "FIRE_ENGINE", "station_id": "STN-FIRE-04", "latitude": 13.0975, "longitude": 80.1610, "status": "AVAILABLE", "personnel_count": 6, "equipment": "High-Volume Water Tender 402, Smoke Extractors"},
            {"id": "EMS-ALS-08", "call_sign": "MEDIC-8", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-01", "latitude": 13.0818, "longitude": 80.2789, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Trauma ALS, Portable Ventilator, Defibrillator, Syringe Pumps"},
            {"id": "EMS-ALS-14", "call_sign": "MEDIC-14", "unit_type": "AMBULANCE_ALS", "station_id": "STN-HOSP-02", "latitude": 13.0607, "longitude": 80.2514, "status": "AVAILABLE", "personnel_count": 3, "equipment": "Cardiac Care ALS, Resuscitation Station, ECG Telemetry"},
            {"id": "SDRF-BOAT-02", "call_sign": "NEPTUNE-2", "unit_type": "BOAT_RESCUE", "station_id": "STN-POL-03", "latitude": 12.9791, "longitude": 80.2185, "status": "AVAILABLE", "personnel_count": 6, "equipment": "Inflatable Zodiac Boats, Life Jackets, Rescue Torpedo Buoys"},
            {"id": "DRONE-RECON-01", "call_sign": "SKYEYE-1", "unit_type": "DRONE_RECON", "station_id": "STN-NDRF-01", "latitude": 13.0645, "longitude": 80.2812, "status": "AVAILABLE", "personnel_count": 2, "equipment": "Dual Thermal/RGB FLIR Drones, Night-Vision LiDAR"},
            {"id": "POL-TAC-12", "call_sign": "DELTA-12", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-02", "latitude": 13.0550, "longitude": 80.2550, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Evacuation Route Escort, Barricades, Megaphones"},
            {"id": "POL-TAC-07", "call_sign": "DELTA-07", "unit_type": "POLICE_PATROL", "station_id": "STN-POL-01", "latitude": 13.0827, "longitude": 80.2707, "status": "AVAILABLE", "personnel_count": 4, "equipment": "Perimeter Cordon & Riot Control Gear, First Aid Kit"}
        ]



        for ru in default_resp_units:
            await db.execute("""
            INSERT OR REPLACE INTO response_units (id, call_sign, unit_type, station_id, latitude, longitude, status, assigned_incident_id, personnel_count, equipment)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """, (ru["id"], ru["call_sign"], ru["unit_type"], ru["station_id"], ru["latitude"], ru["longitude"], ru["status"], ru["personnel_count"], ru["equipment"]))
            # Also keep legacy units table aligned
            await db.execute("""
            INSERT OR REPLACE INTO units (id, name, type, status, station_name, latitude, longitude, assigned_incident_id, contact_callsign, personnel_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """, (ru["id"], ru["id"], ru["unit_type"], ru["status"], ru["station_id"], ru["latitude"], ru["longitude"], ru["call_sign"], ru["personnel_count"]))

        # Seed comprehensive active incidents (4 within Chennai, 4 across Tamil Nadu)
        now_iso = datetime.now(timezone.utc).isoformat()
        initial_incidents = [
            # ==================== 4 TASKS WITHIN CHENNAI ====================
            {
                "id": "INC-CHE-01",
                "title": "Severe 4-Alarm Fire at Mount Road Commercial High-Rise",
                "type": "FIRE",
                "severity": "CRITICAL",
                "urgency_score": 96,
                "location_name": "Mount Road near Guindy Flyover, Chennai",
                "latitude": 13.0067,
                "longitude": 80.2024,
                "affected_injured": 6,
                "affected_trapped": 22,
                "affected_evacuated": 34,
                "affected_total": 62,
                "casualty_summary": "6 workers suffering severe smoke inhalation; 22 trapped on 3rd & 4th floors near locked fire exits.",
                "actionable_notes": "Deploy 54m skylift ladder to south facade immediately. Cut roof ventilation and establish 150m cordon.",
                "status": "PENDING",
                "raw_text": "Severe 4-alarm fire raging inside commercial multi-story complex on Mount Road near Guindy Flyover. Thick black smoke engulfing 3rd and 4th floors. 22 workers trapped near fire exits! Send heavy fire tender now!",
                "channel": "SOS_CITIZEN_APP"
            },
            {
                "id": "INC-CHE-02",
                "title": "Major Petrochemical Ammonia Gas Leak at Manali Industrial Hub",
                "type": "INDUSTRIAL",
                "severity": "CRITICAL",
                "urgency_score": 94,
                "location_name": "Manali Petrochem Industrial Corridor Gate 3, Chennai",
                "latitude": 13.1673,
                "longitude": 80.2644,
                "affected_injured": 8,
                "affected_trapped": 4,
                "affected_evacuated": 45,
                "affected_total": 57,
                "casualty_summary": "8 workers unconscious with respiratory distress; ammonia gas plume drifting toward adjacent residential boundary.",
                "actionable_notes": "Mobilize Hazmat foam unit with neutralizer scrubbers. Mandatory Level-A SCBA gear for all entering crews.",
                "status": "PENDING",
                "raw_text": "Major chemical gas leak at Manali Petrochem Industrial zone gate 3! Pungent ammonia smell everywhere, workers collapsing and choking, at least 8 people unconscious. Need Hazmat unit and ALS ambulances immediately!",
                "channel": "EMERGENCY_TRANSCRIPT_112"
            },
            {
                "id": "INC-CHE-03",
                "title": "Deep Urban Inundation & Trapped Citizens in Velachery",
                "type": "FLOOD",
                "severity": "CRITICAL",
                "urgency_score": 88,
                "location_name": "Velachery Lake View Sector 4, South Chennai",
                "latitude": 12.9791,
                "longitude": 80.2185,
                "affected_injured": 2,
                "affected_trapped": 14,
                "affected_evacuated": 28,
                "affected_total": 44,
                "casualty_summary": "14 residents including elderly citizens and infants stranded on 2nd floor balconies without power or potable water.",
                "actionable_notes": "Deploy inflatable Zodiac boat units via Velachery 100ft road corridor. Establish medical triage post at bypass junction.",
                "status": "PENDING",
                "raw_text": "URGENT SOS! Water level has reached 2nd floor in Velachery Lake View Sector 4. Around 14 people including 4 elderly and babies trapped without food or power. Immediate boat rescue needed!",
                "channel": "TWITTER_FEED"
            },
            {
                "id": "INC-CHE-04",
                "title": "Metro Rail Viaduct Structural Beam Collapse at Anna Nagar",
                "type": "STRUCTURAL_COLLAPSE",
                "severity": "CRITICAL",
                "urgency_score": 92,
                "location_name": "Anna Nagar West Metro Junction, Chennai",
                "latitude": 13.0850,
                "longitude": 80.2101,
                "affected_injured": 11,
                "affected_trapped": 15,
                "affected_evacuated": 18,
                "affected_total": 44,
                "casualty_summary": "Reinforced concrete beam collapsed onto two transit vehicles; 15 passengers pinned inside passenger cabins.",
                "actionable_notes": "Deploy NDRF heavy hydraulic spreaders and cutters. Route all general traffic via 3rd Avenue detour.",
                "status": "PENDING",
                "raw_text": "Metro bridge girder collapsed onto 2 passenger buses at Anna Nagar West junction! Debris pinning vehicles, heavy screaming, minimum 15 passengers trapped. Critical extrication equipment required ASAP.",
                "channel": "TELEGRAM_DISASTER_HUB"
            },

            # ==================== 4 TASKS ACROSS TAMIL NADU ====================
            {
                "id": "INC-TN-01",
                "title": "Hazardous Chemical Warehouse Blaze at Sriperumbudur SIPCOT",
                "type": "INDUSTRIAL",
                "severity": "CRITICAL",
                "urgency_score": 95,
                "location_name": "Sriperumbudur SIPCOT Sector 2, Kanchipuram",
                "latitude": 12.9675,
                "longitude": 79.9431,
                "affected_injured": 7,
                "affected_trapped": 12,
                "affected_evacuated": 60,
                "affected_total": 79,
                "casualty_summary": "Solvent drum explosions triggering structural fire; 12 plant operators trapped in rear inventory wing.",
                "actionable_notes": "Deploy Sriperumbudur Hazmat Fire Tender and 4th Battalion NDRF extraction squad. Isolate adjacent chemical tanks.",
                "status": "PENDING",
                "raw_text": "Massive explosion and raging chemical solvent fire inside Sriperumbudur SIPCOT Sector 2 industrial facility. 12 workers trapped inside storage wing, secondary drum blasts occurring. Dispatch hazmat fire units urgently!",
                "channel": "SOS_CITIZEN_APP"
            },
            {
                "id": "INC-TN-02",
                "title": "Major Textile Factory Blaze & Structural Threat in Coimbatore",
                "type": "FIRE",
                "severity": "CRITICAL",
                "urgency_score": 90,
                "location_name": "Peelamedu Industrial Zone, Coimbatore",
                "latitude": 11.0168,
                "longitude": 76.9558,
                "affected_injured": 5,
                "affected_trapped": 18,
                "affected_evacuated": 75,
                "affected_total": 98,
                "casualty_summary": "Yarn spinning floor ablaze with toxic synthetic smoke; 18 night-shift workers trapped on roof terrace.",
                "actionable_notes": "Deploy 60m hydraulic turntable skylift from Coimbatore Central Fire Base. Cut perimeter fence for ambulance access.",
                "status": "PENDING",
                "raw_text": "Huge fire broken out at major textile spinning mill in Peelamedu, Coimbatore! Dense smoke billowing, 18 workers stuck on terrace. We need Coimbatore fire engine and ambulances right away!",
                "channel": "EMERGENCY_TRANSCRIPT_112"
            },
            {
                "id": "INC-TN-03",
                "title": "Vaigai River Flash Inundation & Colony Submersion in Madurai",
                "type": "FLOOD",
                "severity": "CRITICAL",
                "urgency_score": 91,
                "location_name": "Madurai Central River Basin Corridor, Madurai",
                "latitude": 9.9252,
                "longitude": 78.1198,
                "affected_injured": 3,
                "affected_trapped": 26,
                "affected_evacuated": 110,
                "affected_total": 139,
                "casualty_summary": "Vaigai river breached containment embankment; 26 residents cut off on rooftops in low-lying riverside settlement.",
                "actionable_notes": "Deploy SDRF flood rescue boats and air-drop life jackets. Establish emergency shelter at Madurai Central School.",
                "status": "PENDING",
                "raw_text": "Vaigai river water overflowed heavily into low-lying colony near Madurai Central! Over 25 people including children stranded on rooftops with water rising fast. Need emergency boat rescue immediately!",
                "channel": "TWITTER_FEED"
            },
            {
                "id": "INC-TN-04",
                "title": "High-Pressure Gas Pipeline Rupture at Thuvakudi Industrial Hub",
                "type": "INDUSTRIAL",
                "severity": "HIGH",
                "urgency_score": 86,
                "location_name": "Thuvakudi Industrial Estate, Tiruchirappalli",
                "latitude": 10.7905,
                "longitude": 78.7047,
                "affected_injured": 4,
                "affected_trapped": 8,
                "affected_evacuated": 50,
                "affected_total": 62,
                "casualty_summary": "Underground LPG feeder pipeline fractured during excavation; 4 workers injured by blast wave, 8 sheltered in control bunker.",
                "actionable_notes": "Activate emergency valve shutoff grid. Deploy Trichy Cantonment chemical fire tender with foam barrier.",
                "status": "PENDING",
                "raw_text": "Major gas pipeline rupture and fireball explosion at Thuvakudi Industrial Estate in Trichy. Gas hissing loudly with intense heat. 4 injured workers need urgent medical evacuation.",
                "channel": "WHATSAPP_DISTRESS"
            }
        ]

        for inc in initial_incidents:
            await db.execute("""
            INSERT OR REPLACE INTO incidents (
                id, created_at, raw_text, channel, metadata_info, is_relevant, confidence_score,
                rejection_reason, title, type, severity, urgency_score, location_name,
                latitude, longitude, affected_injured, affected_trapped, affected_evacuated,
                affected_total, casualty_summary, actionable_notes, status, dispatched_units, timeline
            ) VALUES (?, ?, ?, ?, ?, 1, 0.96, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?)
            """, (
                inc["id"], now_iso, inc["raw_text"], inc["channel"], f"GPS: ({inc['latitude']}, {inc['longitude']})",
                inc["title"], inc["type"], inc["severity"], inc["urgency_score"], inc["location_name"],
                inc["latitude"], inc["longitude"], inc["affected_injured"], inc["affected_trapped"],
                inc["affected_evacuated"], inc["affected_total"], inc["casualty_summary"],
                inc["actionable_notes"], inc["status"],
                json.dumps([{"timestamp": now_iso, "action": "INITIAL_ALERT_INGESTED", "notes": f"System pre-loaded verified incident via {inc['channel']}."}])
            ))

        # Remove any non-Tamil Nadu legacy incidents (clean database)
        valid_ids = tuple(inc["id"] for inc in initial_incidents)
        await db.execute(f"""
        DELETE FROM incidents 
        WHERE id NOT IN {valid_ids} 
          AND (latitude < 8.0 OR latitude > 13.6 OR longitude < 76.2 OR longitude > 80.5)
        """)

        await db.commit()


async def reset_database_clean_tamilnadu():
    """Wipes all temporary incidents and restores the clean 4 Chennai + 4 Tamil Nadu operational tasks."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM incidents")
        await db.execute("UPDATE units SET status = 'AVAILABLE', assigned_incident_id = NULL")
        await db.execute("UPDATE response_units SET status = 'AVAILABLE', assigned_incident_id = NULL")
        await db.commit()
    await init_db()





async def save_incident(inc: IncidentRecord) -> IncidentRecord:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        INSERT OR REPLACE INTO incidents (
            id, created_at, raw_text, channel, metadata_info, is_relevant, confidence_score,
            rejection_reason, title, type, severity, urgency_score, location_name,
            latitude, longitude, affected_injured, affected_trapped, affected_evacuated,
            affected_total, casualty_summary, actionable_notes, status, dispatched_units, timeline
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inc.id, inc.created_at, inc.raw_text, inc.channel, inc.metadata_info,
            1 if inc.is_relevant else 0, inc.confidence_score, inc.rejection_reason,
            inc.title, inc.type, inc.severity, inc.urgency_score, inc.location_name,
            inc.latitude, inc.longitude, inc.affected_injured, inc.affected_trapped,
            inc.affected_evacuated, inc.affected_total, inc.casualty_summary,
            inc.actionable_notes, inc.status, json.dumps(inc.dispatched_units),
            json.dumps(inc.timeline)
        ))
        
        await db.execute("""
        INSERT INTO audit_logs (timestamp, event_type, incident_id, details)
        VALUES (?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            "INCIDENT_INGESTED",
            inc.id,
            f"Ingested from {inc.channel} - Type: {inc.type}, Urgency: {inc.urgency_score}"
        ))
        
        await db.commit()
    return inc

async def get_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    disaster_type: Optional[str] = None,
    is_relevant: Optional[bool] = None,
    search: Optional[str] = None
) -> List[IncidentRecord]:
    await init_db()
    query = "SELECT * FROM incidents WHERE 1=1"
    params = []

    if is_relevant is not None:
        query += " AND is_relevant = ?"
        params.append(1 if is_relevant else 0)

    if status and status != "ALL":
        query += " AND status = ?"
        params.append(status)

    if severity and severity != "ALL":
        query += " AND severity = ?"
        params.append(severity)

    if disaster_type and disaster_type != "ALL":
        query += " AND type = ?"
        params.append(disaster_type)

    if search:
        query += " AND (title LIKE ? OR location_name LIKE ? OR raw_text LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])

    query += " ORDER BY urgency_score DESC, created_at DESC"

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            results = []
            for r in rows:
                results.append(IncidentRecord(
                    id=r["id"],
                    created_at=r["created_at"],
                    raw_text=r["raw_text"],
                    channel=r["channel"],
                    metadata_info=r["metadata_info"],
                    is_relevant=bool(r["is_relevant"]),
                    confidence_score=r["confidence_score"],
                    rejection_reason=r["rejection_reason"],
                    title=r["title"],
                    type=r["type"],
                    severity=r["severity"],
                    urgency_score=r["urgency_score"],
                    location_name=r["location_name"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    affected_injured=r["affected_injured"],
                    affected_trapped=r["affected_trapped"],
                    affected_evacuated=r["affected_evacuated"],
                    affected_total=r["affected_total"],
                    casualty_summary=r["casualty_summary"],
                    actionable_notes=r["actionable_notes"],
                    status=r["status"],
                    dispatched_units=json.loads(r["dispatched_units"] or "[]"),
                    timeline=json.loads(r["timeline"] or "[]")
                ))
            return results

async def get_incident_by_id(incident_id: str) -> Optional[IncidentRecord]:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)) as cursor:
            r = await cursor.fetchone()
            if not r:
                return None
            return IncidentRecord(
                id=r["id"],
                created_at=r["created_at"],
                raw_text=r["raw_text"],
                channel=r["channel"],
                metadata_info=r["metadata_info"],
                is_relevant=bool(r["is_relevant"]),
                confidence_score=r["confidence_score"],
                rejection_reason=r["rejection_reason"],
                title=r["title"],
                type=r["type"],
                severity=r["severity"],
                urgency_score=r["urgency_score"],
                location_name=r["location_name"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                affected_injured=r["affected_injured"],
                affected_trapped=r["affected_trapped"],
                affected_evacuated=r["affected_evacuated"],
                affected_total=r["affected_total"],
                casualty_summary=r["casualty_summary"],
                actionable_notes=r["actionable_notes"],
                status=r["status"],
                dispatched_units=json.loads(r["dispatched_units"] or "[]"),
                timeline=json.loads(r["timeline"] or "[]")
            )

async def dispatch_units_to_incident(incident_id: str, unit_ids: List[str], notes: Optional[str] = None) -> Optional[IncidentRecord]:
    await init_db()
    inc = await get_incident_by_id(incident_id)
    if not inc:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    
    async with aiosqlite.connect(DB_PATH) as db:
        for uid in unit_ids:
            await db.execute("""
            UPDATE units SET status = 'DISPATCHED', assigned_incident_id = ? WHERE id = ?
            """, (incident_id, uid))

        current_units = set(inc.dispatched_units)
        current_units.update(unit_ids)
        new_units_list = list(current_units)
        
        timeline_entry = {
            "timestamp": now_iso,
            "action": "UNITS_DISPATCHED",
            "units": unit_ids,
            "notes": notes or f"Dispatched {len(unit_ids)} CAD responder units to scene."
        }
        inc.timeline.append(timeline_entry)
        inc.dispatched_units = new_units_list
        inc.status = "DISPATCHED"

        await db.execute("""
        UPDATE incidents 
        SET status = 'DISPATCHED', dispatched_units = ?, timeline = ?
        WHERE id = ?
        """, (json.dumps(new_units_list), json.dumps(inc.timeline), incident_id))

        await db.execute("""
        INSERT INTO audit_logs (timestamp, event_type, incident_id, details)
        VALUES (?, ?, ?, ?)
        """, (now_iso, "DISPATCH_COMMITTED", incident_id, f"Units dispatched: {', '.join(unit_ids)}"))

        await db.commit()

    return inc

async def update_incident_status(
    incident_id: str,
    status: str,
    notes: Optional[str] = None,
    author_name: str = "Field Responder (COMMAND-ALPHA)",
    author_role: str = "FIELD_RESPONDER"
) -> Optional[IncidentRecord]:
    await init_db()
    inc = await get_incident_by_id(incident_id)
    if not inc:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    time_str = datetime.now(timezone.utc).strftime("%H:%M UTC")

    # Adjust urgency score dynamically based on tactical status
    if status == "ACCEPTED":
        inc.urgency_score = max(10, inc.urgency_score - 5)
    elif status == "EN_ROUTE":
        inc.urgency_score = max(10, inc.urgency_score - 10)
    elif status == "ON_SCENE":
        inc.urgency_score = max(10, inc.urgency_score - 20)
    elif status == "ASSISTANCE_REQUIRED":
        inc.urgency_score = min(100, inc.urgency_score + 25)
        inc.severity = "CRITICAL"
    elif status == "SITUATION_UNDER_CONTROL":
        inc.urgency_score = max(5, inc.urgency_score - 40)
        if inc.severity == "CRITICAL":
            inc.severity = "MODERATE"
    elif status == "RESOLVED":
        inc.urgency_score = 0

    inc.urgencyScore = inc.urgency_score
    inc.status = status
    inc.currentStatus = status

    timeline_entry = {
        "id": f"UP-{datetime.now(timezone.utc).strftime('%H%M%S')}",
        "timestamp": time_str,
        "iso_timestamp": now_iso,
        "authorName": author_name,
        "authorRole": author_role,
        "statusChange": status,
        "action": f"STATUS_CHANGED_{status}",
        "note": notes or f"Incident status transitioned to {status} (Urgency: {inc.urgency_score}/100)",
        "notes": notes or f"Incident status transitioned to {status}"
    }
    inc.timeline.append(timeline_entry)

    async with aiosqlite.connect(DB_PATH) as db:
        if status == "RESOLVED":
            for uid in inc.dispatched_units:
                await db.execute("""
                UPDATE units SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id = ?
                """, (uid,))
                await db.execute("""
                UPDATE response_units SET status = 'AVAILABLE', assigned_incident_id = NULL WHERE id = ?
                """, (uid,))

        await db.execute("""
        UPDATE incidents SET 
            status = ?,
            severity = ?,
            urgency_score = ?,
            timeline = ?
        WHERE id = ?
        """, (status, inc.severity, inc.urgency_score, json.dumps(inc.timeline), incident_id))
        
        await db.execute("""
        INSERT INTO audit_logs (timestamp, event_type, incident_id, details)
        VALUES (?, ?, ?, ?)
        """, (now_iso, f"STATUS_CHANGED_{status}", incident_id, f"Transitioned to {status} by {author_name}"))

        await db.commit()

    return inc

async def get_after_action_report(incident_id: str) -> Optional[dict]:
    """Generates structured After-Action Report (AAR) summary for resolved incidents."""
    inc = await get_incident_by_id(incident_id)
    if not inc:
        return None

    # Calculate operational duration
    start_time = None
    resolved_time = None
    try:
        start_time = datetime.fromisoformat(inc.created_at.replace("Z", "+00:00"))
    except Exception:
        pass

    for entry in inc.timeline:
        if entry.get("statusChange") == "RESOLVED" or entry.get("action") == "STATUS_CHANGED_RESOLVED":
            try:
                resolved_time = datetime.fromisoformat(entry.get("iso_timestamp", "").replace("Z", "+00:00"))
            except Exception:
                pass

    duration_min = 0
    if start_time and resolved_time:
        duration_min = max(1, round((resolved_time - start_time).total_seconds() / 60))
    elif start_time:
        duration_min = max(1, round((datetime.now(timezone.utc) - start_time).total_seconds() / 60))

    # Calculate victim tags breakdown
    victims = getattr(inc, "victims", None) or []
    tally = {"RED": 0, "YELLOW": 0, "GREEN": 0, "BLACK": 0}
    for v in victims:
        tag = (v.get("triageTag") or v.get("triage_tag") or v.get("category") or "YELLOW").upper()
        if tag in tally:
            tally[tag] += 1
        else:
            tally["YELLOW"] += 1

    for t in inc.timeline:
        if t.get("action") == "VICTIM_LOGGED":
            note = (t.get("note") or "") + " " + (t.get("notes") or "")
            for tag in ["RED", "YELLOW", "GREEN", "BLACK"]:
                if f"[{tag}]" in note or f"({tag})" in note:
                    tally[tag] += 1
                    break


    return {
        "incident_id": inc.id,
        "title": inc.title,
        "type": inc.type,
        "severity": inc.severity,
        "location_name": inc.location_name,
        "coordinates": {"lat": inc.latitude, "lng": inc.longitude},
        "created_at": inc.created_at,
        "resolved_at": resolved_time.isoformat() if resolved_time else datetime.now(timezone.utc).isoformat(),
        "duration_minutes": duration_min,
        "dispatched_units": inc.dispatched_units,
        "total_victims_logged": len(victims),
        "victim_triage_tally": tally,
        "casualties": {
            "injured": inc.affected_injured,
            "trapped": inc.affected_trapped,
            "evacuated": inc.affected_evacuated,
            "total": inc.affected_total
        },
        "casualty_summary": inc.casualty_summary,
        "actionable_notes": inc.actionable_notes,
        "timeline": inc.timeline
    }


async def add_victim_to_incident(
    incident_id: str,
    victim_data: dict,
    author_name: str = "Triage Medic"
) -> Optional[IncidentRecord]:
    await init_db()
    inc = await get_incident_by_id(incident_id)
    if not inc:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    time_str = datetime.now(timezone.utc).strftime("%H:%M UTC")

    victim_profile = {
        "id": victim_data.get("id") or f"VIC-{datetime.now(timezone.utc).strftime('%H%M%S')}",
        "name": victim_data.get("name", "Unknown Individual"),
        "category": victim_data.get("category", "RED"),
        "notes": victim_data.get("notes", ""),
        "rescued": bool(victim_data.get("rescued", False)),
        "timestamp": now_iso
    }

    inc.victims.append(victim_profile)

    # If category is RED/YELLOW, add to injured; if rescued, increment evacuated
    if victim_profile["rescued"]:
        inc.affected_evacuated += 1
        if inc.affected_trapped > 0:
            inc.affected_trapped -= 1
    else:
        if victim_profile["category"] in ["RED", "YELLOW"]:
            inc.affected_injured += 1
        elif victim_profile["category"] == "BLACK":
            pass

    inc.affected_total = inc.affected_injured + inc.affected_trapped + inc.affected_evacuated
    inc.affectedPeople.injured = inc.affected_injured
    inc.affectedPeople.trapped = inc.affected_trapped
    inc.affectedPeople.evacuated = inc.affected_evacuated
    inc.affectedPeople.totalEstimated = inc.affected_total

    timeline_entry = {
        "id": f"UP-VIC-{datetime.now(timezone.utc).strftime('%H%M%S')}",
        "timestamp": time_str,
        "iso_timestamp": now_iso,
        "authorName": author_name,
        "authorRole": "FIELD_MEDIC",
        "action": "VICTIM_LOGGED",
        "note": f"Logged victim [{victim_profile['category']}] {victim_profile['name']} - Rescued: {victim_profile['rescued']}",
        "notes": f"Victim logged: {victim_profile['name']} ({victim_profile['category']})"
    }
    inc.timeline.append(timeline_entry)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        UPDATE incidents SET
            affected_injured = ?,
            affected_trapped = ?,
            affected_evacuated = ?,
            affected_total = ?,
            timeline = ?
        WHERE id = ?
        """, (
            inc.affected_injured,
            inc.affected_trapped,
            inc.affected_evacuated,
            inc.affected_total,
            json.dumps(inc.timeline),
            incident_id
        ))
        await db.commit()

    return inc

async def get_all_units() -> List[EmergencyUnit]:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM units") as cursor:
            rows = await cursor.fetchall()
            return [
                EmergencyUnit(
                    id=r["id"],
                    name=r["name"],
                    type=r["type"],
                    status=r["status"],
                    station_name=r["station_name"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    assigned_incident_id=r["assigned_incident_id"],
                    contact_callsign=r["contact_callsign"],
                    personnel_count=r["personnel_count"]
                ) for r in rows
            ]

async def get_system_stats() -> SystemStats:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM incidents WHERE is_relevant = 1") as c:
            total = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM incidents WHERE is_relevant = 1 AND severity = 'CRITICAL' AND status != 'RESOLVED'") as c:
            critical = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM incidents WHERE is_relevant = 1 AND severity = 'HIGH' AND status != 'RESOLVED'") as c:
            high = (await c.fetchone())[0]
        async with db.execute("SELECT SUM(affected_trapped), SUM(affected_injured) FROM incidents WHERE is_relevant = 1 AND status != 'RESOLVED'") as c:
            row = await c.fetchone()
            trapped = row[0] or 0
            injured = row[1] or 0
        async with db.execute("SELECT AVG(urgency_score) FROM incidents WHERE is_relevant = 1 AND status != 'RESOLVED'") as c:
            avg_urgency = (await c.fetchone())[0] or 0.0
        async with db.execute("SELECT COUNT(*) FROM units WHERE status = 'AVAILABLE'") as c:
            avail_units = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM units WHERE status = 'DISPATCHED'") as c:
            disp_units = (await c.fetchone())[0]

        return SystemStats(
            total_incidents=total,
            active_critical=critical,
            active_high=high,
            trapped_count=trapped,
            injured_count=injured,
            available_units=avail_units,
            dispatched_units=disp_units,
            average_urgency=round(float(avg_urgency), 1),
            triaged_today=total
        )

async def get_all_audit_logs() -> List[dict]:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 200") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_all_stations() -> List[EmergencyStation]:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM stations ORDER BY type, name") as cursor:
            rows = await cursor.fetchall()
            return [
                EmergencyStation(
                    id=r["id"],
                    name=r["name"],
                    type=r["type"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    address=r["address"] or ""
                ) for r in rows
            ]

async def get_station_by_id(station_id: str) -> Optional[EmergencyStation]:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM stations WHERE id = ?", (station_id,)) as cursor:
            r = await cursor.fetchone()
            if not r:
                return None
            return EmergencyStation(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                address=r["address"] or ""
            )

async def get_all_response_units() -> List[ResponseUnit]:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM response_units ORDER BY unit_type, id") as cursor:
            rows = await cursor.fetchall()
            return [
                ResponseUnit(
                    id=r["id"],
                    call_sign=r["call_sign"],
                    unit_type=r["unit_type"],
                    station_id=r["station_id"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    status=r["status"],
                    assigned_incident_id=r["assigned_incident_id"],
                    personnel_count=r["personnel_count"],
                    equipment=r["equipment"]
                ) for r in rows
            ]

async def get_response_unit_by_id(unit_id: str) -> Optional[ResponseUnit]:
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM response_units WHERE id = ?", (unit_id,)) as cursor:
            r = await cursor.fetchone()
            if not r:
                return None
            return ResponseUnit(
                id=r["id"],
                call_sign=r["call_sign"],
                unit_type=r["unit_type"],
                station_id=r["station_id"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                status=r["status"],
                assigned_incident_id=r["assigned_incident_id"],
                personnel_count=r["personnel_count"],
                equipment=r["equipment"]
            )

async def update_response_unit_assignment(unit_id: str, status: str, incident_id: Optional[str] = None):
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        UPDATE response_units SET status = ?, assigned_incident_id = ? WHERE id = ?
        """, (status, incident_id, unit_id))
        # Keep legacy units table synchronized
        await db.execute("""
        UPDATE units SET status = ?, assigned_incident_id = ? WHERE id = ?
        """, (status, incident_id, unit_id))
        await db.commit()

