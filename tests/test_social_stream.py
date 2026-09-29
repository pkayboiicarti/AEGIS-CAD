import asyncio
import pytest
from fastapi.testclient import TestClient
from app.server import app
from app.services.social_ingestion import SocialMediaIngestionWorker
from app.models import SocialStreamItem, SocialStreamEvent
from app.triage_engine import TriageEngine
from app.database import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def ensure_db():
    asyncio.run(init_db())

def test_social_stream_ingest_ticket_generation():
    async def _test():
        engine = TriageEngine()
        worker = SocialMediaIngestionWorker(engine)
        
        import time
        t_unique = int(time.time() * 1000) % 10000
        # Valid Tamil Nadu crisis post with dynamic unique ID and coordinates
        item = SocialStreamItem(
            id=f"POST-TEST-{t_unique}",
            platform="TWITTER_X",
            author=f"@citizen_sos_{t_unique}",
            text=f"URGENT SOS #{t_unique}! Sudden boiler fire and structural collapse inside knitting mill near Nagercoil Highway Sector {t_unique}! 4 workers trapped inside cutting unit!",
            location_hint=f"Nagercoil Highway Sector {t_unique} (8.183{t_unique % 9}, 77.411{t_unique % 9})",
            source_url=f"https://x.com/test/status/{t_unique}"
        )
        
        event: SocialStreamEvent = await worker.process_item(item)
        
        assert event.action_taken in ["TICKET_GENERATED", "MERGED"]
        assert event.incident_id is not None
        assert "INC-" in event.incident_id
        assert event.item.platform == "TWITTER_X"

    asyncio.run(_test())

def test_social_stream_500m_geospatial_merge():
    async def _test():
        engine = TriageEngine()
        worker = SocialMediaIngestionWorker(engine)
        
        # 1st Post: Gas leak at Manali
        item1 = SocialStreamItem(
            id="POST-TEST-M1",
            platform="DISPATCH_112",
            author="CALLER_112",
            text="Major chemical gas leak at Manali Petrochem Industrial zone gate 3! Pungent ammonia smell everywhere, workers collapsing and choking.",
            location_hint="Manali Industrial Zone, Gate 3 (13.1673, 80.2644)"
        )
        evt1 = await worker.process_item(item1)
        assert evt1.action_taken in ["TICKET_GENERATED", "MERGED"]
        
        # 2nd Post within 200m/500m: Second caller at same location
        item2 = SocialStreamItem(
            id="POST-TEST-M2",
            platform="TWITTER_X",
            author="@manali_resident",
            text="Ammonia leak spreading fast near Manali petrochemicals gate 3! More than 5 people unconscious, ambulances needed!",
            location_hint="Manali Industrial Zone, Gate 3 (13.1675, 80.2646)"
        )
        evt2 = await worker.process_item(item2)
        assert evt2.action_taken == "MERGED"
        assert evt2.incident_id is not None
        assert evt2.distance_meters is not None
        assert evt2.distance_meters <= 500

    asyncio.run(_test())

def test_social_stream_out_of_jurisdiction_rejection():
    async def _test():
        engine = TriageEngine()
        worker = SocialMediaIngestionWorker(engine)
        
        # Post from Nepal
        item = SocialStreamItem(
            id="POST-TEST-NEPAL",
            platform="TWITTER_X",
            author="@nepal_alerts",
            text="URGENT SOS! Tremor and building collapse reported in Kathmandu Durbar Square! People trapped under bricks!",
            location_hint="Kathmandu, Nepal (27.7172, 85.3240)"
        )
        
        event: SocialStreamEvent = await worker.process_item(item)
        assert event.action_taken == "OUT_OF_JURISDICTION"
        assert event.incident_id is None

    asyncio.run(_test())

def test_social_stream_spam_discard():
    async def _test():
        engine = TriageEngine()
        worker = SocialMediaIngestionWorker(engine)
        
        # Non-emergency spam
        item = SocialStreamItem(
            id="POST-TEST-SPAM",
            platform="REDDIT",
            author="u/coffee_lover",
            text="Nice weather outside in Anna Nagar, drinking hot tea. Stay safe everyone!",
            location_hint="r/Chennai"
        )
        
        event: SocialStreamEvent = await worker.process_item(item)
        assert event.action_taken == "SPAM_DISCARDED"
        assert event.incident_id is None

    asyncio.run(_test())

def test_social_stream_in_memory_dedup_cache():
    async def _test():
        engine = TriageEngine()
        worker = SocialMediaIngestionWorker(engine)
        
        item = SocialStreamItem(
            id="POST-TEST-EXACT",
            platform="TWITTER_X",
            author="@resident",
            text="Severe fire breakout near Guindy flyover commercial complex! Multiple workers trapped inside!",
            location_hint="Guindy Flyover, Chennai (13.0067, 80.2024)"
        )
        
        evt1 = await worker.process_item(item)
        # Duplicate with same ID & content
        evt2 = await worker.process_item(item)
        
        assert evt2.action_taken == "SPAM_DISCARDED"
        assert "Duplicate post" in evt2.summary

    asyncio.run(_test())

def test_api_stream_endpoints():
    res_status = client.get("/api/stream/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert "running" in data
    assert "ingested_count" in data
    assert "recent_events" in data

    res_sim = client.post("/api/stream/simulate-now")
    assert res_sim.status_code == 200
    sim_data = res_sim.json()
    assert sim_data["status"] == "SUCCESS"
    assert "event" in sim_data
    assert sim_data["event"]["action_taken"] in ["TICKET_GENERATED", "MERGED", "SPAM_DISCARDED", "OUT_OF_JURISDICTION"]

    res_toggle = client.post("/api/stream/toggle", json={"enable": False})
    assert res_toggle.status_code == 200
    assert res_toggle.json()["running"] is False

    res_toggle_on = client.post("/api/stream/toggle", json={"enable": True})
    assert res_toggle_on.status_code == 200
    assert res_toggle_on.json()["running"] is True
