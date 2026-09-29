import random
from typing import List, Dict

SIMULATED_DISASTER_FEEDS = [
    {
        "channel": "TWITTER_FEED",
        "raw_message": "URGENT SOS! Water level has reached 2nd floor in Velachery Lake View Sector 4. Around 14 people including 4 elderly and babies trapped without food or power. Immediate boat rescue needed! Please help @NDRFHQ @chennaicorp",
        "metadata": "Velachery Lake View Sector 4, Chennai (12.9791, 80.2185)",
        "expected_type": "FLOOD",
        "expected_severity": "CRITICAL"
    },
    {
        "channel": "EMERGENCY_TRANSCRIPT_112",
        "raw_message": "[CALLER 112 DISPATCH]: Major chemical gas leak at Manali Petrochem Industrial zone gate 3! Pungent ammonia smell everywhere, workers collapsing and choking, at least 8 people unconscious and bleeding from nose. Need Hazmat unit and ALS ambulances immediately!",
        "metadata": "Manali Industrial Zone, Gate 3 (13.1673, 80.2644)",
        "expected_type": "INDUSTRIAL",
        "expected_severity": "CRITICAL"
    },
    {
        "channel": "SOS_CITIZEN_APP",
        "raw_message": "Severe 4-alarm fire raging inside commercial multi-story complex on Mount Road near Guindy Flyover. Thick black smoke engulfing 3rd and 4th floors. 22 workers trapped near fire exits which are locked! Send heavy fire tender and ladder trucks now!",
        "metadata": "Mount Road near Guindy Flyover (13.0067, 80.2024)",
        "expected_type": "FIRE",
        "expected_severity": "CRITICAL"
    },
    {
        "channel": "TELEGRAM_DISASTER_HUB",
        "raw_message": "Metro construction bridge girder collapsed onto 2 passenger buses at Anna Nagar West junction! Debris pinning vehicles, heavy screaming, minimum 15 passengers trapped and heavily injured. Critical extrication equipment required ASAP.",
        "metadata": "Anna Nagar West Junction (13.0850, 80.2101)",
        "expected_type": "STRUCTURAL_COLLAPSE",
        "expected_severity": "CRITICAL"
    },
    {
        "channel": "WHATSAPP_DISTRESS",
        "raw_message": "Cyclone storm surge has flooded GST Road Tambaram near railway bridge. Water current is very strong, 3 cars washed away, 6 people clinging to electricity pole. Send rescue team fast!",
        "metadata": "GST Road Tambaram Bridge (12.9249, 80.1000)",
        "expected_type": "CYCLONE",
        "expected_severity": "HIGH"
    },
    {
        "channel": "TWITTER_FEED",
        "raw_message": "Severe seismic tremor felt across Old Mahabalipuram Road (OMR) tech corridor. Cracked walls in naval quarters, 2 security guards injured from falling glass panes at Navalur.",
        "metadata": "OMR Navalur Sector (12.8797, 80.2280)",
        "expected_type": "EARTHQUAKE",
        "expected_severity": "MODERATE"
    },
    {
        "channel": "EMERGENCY_APP",
        "raw_message": "CRITICAL ALARM! Multi-vehicle pileup and petrol tanker fire on Chennai Bypass Porur Toll corridor! Giant fireball engulfing toll lanes, 8 vehicles burning, multiple motorists trapped inside.",
        "metadata": "Porur Toll Gate, Chennai Bypass (13.0382, 80.1565)",
        "expected_type": "FIRE",
        "expected_severity": "CRITICAL"
    },
    {
        "channel": "POLICE_RADIO_TRANSCRIPT",
        "raw_message": "Subsea crude oil and naphtha pipeline rupture near Ennore Port pier 4! Flammable vapor cloud expanding across coastline, 5 dockworkers overcome by hydrocarbon fumes.",
        "metadata": "Ennore Port Pier 4 (13.2084, 80.3255)",
        "expected_type": "INDUSTRIAL",
        "expected_severity": "CRITICAL"
    },
    {
        "channel": "CITIZEN_SOS",
        "raw_message": "Massive coastal storm surge breach at Foreshore Estate fishing hamlet! Seawater inundated 60 houses, 12 fishermen trapped on church terrace, strong undertow.",
        "metadata": "Foreshore Estate Coastal Hub (13.0280, 80.2780)",
        "expected_type": "FLOOD",
        "expected_severity": "CRITICAL"
    },
    # Non-emergency noise / spam / news posts for negative testing

    {
        "channel": "TWITTER_FEED",
        "raw_message": "Heartbreaking images coming in from Chennai. Praying for everyone's safety and well-being. Stay strong guys! #PrayForChennai #CycloneAlert",
        "metadata": "Twitter Web Client",
        "expected_type": "OTHER",
        "expected_severity": "LOW"
    },
    {
        "channel": "NEWS_RSS",
        "raw_message": "Daily Weather Bulletin: Regional Meteorological Department predicts moderate showers across northern coastal districts over next 48 hours. Fishermen advised not to venture into deep sea.",
        "metadata": "IMD Weather Feed",
        "expected_type": "OTHER",
        "expected_severity": "LOW"
    },
    {
        "channel": "TELEGRAM_CHAT",
        "raw_message": "Anyone knows if metro trains are running tomorrow from Central to Airport? Have a flight at 6 AM.",
        "metadata": "Public Transit Group",
        "expected_type": "OTHER",
        "expected_severity": "LOW"
    }
]

def get_random_scenario() -> Dict[str, str]:
    return random.choice(SIMULATED_DISASTER_FEEDS)

def get_all_scenarios() -> List[Dict[str, str]]:
    return SIMULATED_DISASTER_FEEDS
