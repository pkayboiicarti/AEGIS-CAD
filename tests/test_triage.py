import asyncio
from app.triage_engine import TriageEngine
from app.geocoding import resolve_location_coordinates, search_landmarks
from app.models import TriageResult

def test_triage_critical_flood():
    async def _test():
        engine = TriageEngine()
        msg = "URGENT SOS! Water level has reached 2nd floor in Velachery Lake View Sector 4. Around 14 people including 4 elderly and babies trapped without food or power. Immediate boat rescue needed!"
        meta = "Velachery, Chennai"
        
        result = await engine.triage_message(msg, meta)
        
        assert isinstance(result, TriageResult)
        assert result.is_relevant is True
        assert result.incident is not None
        assert result.incident.type == "FLOOD"
        assert result.incident.severity in ["CRITICAL", "HIGH"]
        assert result.incident.urgencyScore >= 70
        assert result.incident.affectedPeople.trapped >= 5
        assert "Velachery" in result.incident.locationName
    asyncio.run(_test())

def test_triage_industrial_gas_leak():
    async def _test():
        engine = TriageEngine()
        msg = "Major chemical gas leak at Manali Petrochem Industrial zone gate 3! Pungent ammonia smell everywhere, workers collapsing and choking, at least 8 people unconscious and bleeding from nose."
        meta = "Manali Industrial Zone"
        
        result = await engine.triage_message(msg, meta)
        
        assert result.is_relevant is True
        assert result.incident is not None
        assert result.incident.type == "INDUSTRIAL"
        assert result.incident.severity in ["CRITICAL", "HIGH"]
        assert result.incident.urgencyScore >= 75
        assert result.incident.affectedPeople.injured >= 5
    asyncio.run(_test())

def test_triage_negative_spam():
    async def _test():
        engine = TriageEngine()
        msg = "Heartbreaking images coming in from Chennai. Praying for everyone's safety and well-being. Stay strong guys! #PrayForChennai"
        
        result = await engine.triage_message(msg)
        
        assert result.is_relevant is False
        assert result.incident is None
        assert result.rejection_reason is not None
    asyncio.run(_test())

def test_triage_empty_placeholder():
    async def _test():
        engine = TriageEngine()
        msg = '"""{RAW_TEXT_OR_TRANSCRIPT}"""'
        
        result = await engine.triage_message(msg)
        
        assert result.is_relevant is False
        assert result.incident is None
        assert "placeholder" in result.rejection_reason.lower()
    asyncio.run(_test())

def test_geocoding_resolution():
    lat, lon = resolve_location_coordinates("Velachery Lake View")
    assert lat is not None
    assert lon is not None
    assert 12.8 <= lat <= 13.2
    assert 80.1 <= lon <= 80.4

    lat_cbe, lon_cbe = resolve_location_coordinates("Peelamedu, Coimbatore")
    assert 10.8 <= lat_cbe <= 11.3
    assert 76.8 <= lon_cbe <= 77.2

    lat_mdu, lon_mdu = resolve_location_coordinates("Meenakshi Amman Temple, Madurai")
    assert 9.8 <= lat_mdu <= 10.1
    assert 78.0 <= lon_mdu <= 78.3

    # College Geocoding Tests
    lat_snu, lon_snu = resolve_location_coordinates("SNUC Campus, Kalavakkam")
    assert 12.7 <= lat_snu <= 12.85
    assert 80.15 <= lon_snu <= 80.25

    lat_ssn, lon_ssn = resolve_location_coordinates("SSN College of Engineering")
    assert 12.7 <= lat_ssn <= 12.85
    assert 80.15 <= lon_ssn <= 80.25

    lat_iit, lon_iit = resolve_location_coordinates("IIT Madras, Adyar")
    assert 12.95 <= lat_iit <= 13.05
    assert 80.2 <= lon_iit <= 80.3

    lat_kcbt, lon_kcbt = resolve_location_coordinates("Kilambakkam Bus Terminus (KCBT)")
    assert 12.8 <= lat_kcbt <= 12.92
    assert 80.0 <= lon_kcbt <= 80.15

    # Autocomplete Search Test
    results = search_landmarks("snu")
    assert len(results) >= 1
    assert any("snu" in r["name"].lower() for r in results)



def test_multimodal_image_analysis():
    async def _test():
        engine = TriageEngine()
        mock_bytes = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
        
        # 1. Flood Vision Test
        flood_res = await engine.analyze_image(
            image_bytes=mock_bytes,
            mime_type="image/jpeg",
            caption="Heavy waist-high floodwaters submerging ground floor houses and vehicles on Velachery Main Road."
        )
        assert flood_res.is_disaster_related is True
        assert flood_res.disaster_category == "FLOOD"
        assert flood_res.damage_severity in ["CRITICAL", "HIGH"]
        assert len(flood_res.visual_evidence) >= 1
        assert flood_res.suggested_urgency_adjustment >= 10

        # 2. Fire Vision Test
        fire_res = await engine.analyze_image(
            image_bytes=mock_bytes,
            mime_type="image/jpeg",
            caption="Massive industrial warehouse fire with thick black smoke plume and active flames."
        )
        assert fire_res.is_disaster_related is True
        assert fire_res.disaster_category == "FIRE"
        assert fire_res.damage_severity == "CRITICAL"
        assert fire_res.estimated_casualty_risk == "EXTREME"

        # 3. Non-Disaster Rejection Test
        neg_res = await engine.analyze_image(
            image_bytes=mock_bytes,
            mime_type="image/jpeg",
            caption="Sunny afternoon peaceful day at public park with cute dog playing."
        )
        assert neg_res.is_disaster_related is False
        assert neg_res.disaster_category == "NONE"
        assert neg_res.suggested_urgency_adjustment == 0

    asyncio.run(_test())


def test_out_of_jurisdiction_rejection():
    async def _test():
        engine = TriageEngine()
        
        # Out-of-country / out-of-state disaster report (Kathmandu, Nepal)
        msg = "URGENT SOS! Heavy earthquake struck Kathmandu valley! Multiple historic buildings collapsed, dozens of people trapped under rubble in Durbar Square!"
        meta = "Kathmandu, Nepal (27.7172, 85.3240)"
        
        result = await engine.triage_message(msg, meta)
        
        assert result.is_relevant is False
        assert result.incident is None
        assert result.is_out_of_jurisdiction is True
        assert "OUT_OF_JURISDICTION" in (result.rejection_reason or "")
        assert result.jurisdiction_warning == "Out of Jurisdiction (Tamil Nadu SEOC Only)"

    asyncio.run(_test())


def test_is_within_tamil_nadu_geofence():
    from app.geocoding import is_within_tamil_nadu
    
    # Valid Tamil Nadu coordinates
    assert is_within_tamil_nadu(13.0827, 80.2707) is True  # Chennai
    assert is_within_tamil_nadu(11.0168, 76.9558) is True  # Coimbatore
    assert is_within_tamil_nadu(9.9252, 78.1198) is True   # Madurai
    assert is_within_tamil_nadu(8.7139, 77.7567) is True   # Tirunelveli
    assert is_within_tamil_nadu(12.7532, 80.1983) is True  # SNU Chennai (Kelambakkam)

    # Invalid / Out of Jurisdiction coordinates
    assert is_within_tamil_nadu(27.7172, 85.3240) is False # Kathmandu, Nepal
    assert is_within_tamil_nadu(28.6139, 77.2090) is False # New Delhi
    assert is_within_tamil_nadu(19.0760, 72.8777) is False # Mumbai
    assert is_within_tamil_nadu(37.7749, -122.4194) is False # California


