import pytest
from fastapi.testclient import TestClient
from app.server import app
from app.services.realtime_feed import TamilNaduRealtimeCollector, TN_MONITORING_STATIONS


def test_tamilnadu_realtime_collector_stations():
    assert len(TN_MONITORING_STATIONS) >= 8
    districts = [s["district"] for s in TN_MONITORING_STATIONS]
    assert "Chennai" in districts
    assert "Coimbatore" in districts
    assert "Madurai" in districts
    assert "Tiruchirappalli" in districts
    assert "Kanchipuram" in districts


import asyncio

def test_tamilnadu_statewide_telemetry_fetch():
    async def _test():
        telemetry = await TamilNaduRealtimeCollector.get_statewide_telemetry()
        assert telemetry["region"] == "Tamil Nadu, India"
        assert telemetry["active_sensor_nodes"] >= 8
        assert len(telemetry["station_reports"]) >= 8
        for report in telemetry["station_reports"]:
            assert report["latitude"] > 8.0
            assert report["latitude"] < 14.0
            assert report["longitude"] > 76.0
            assert report["longitude"] < 81.0
            assert "telemetry" in report
            assert "temperature_c" in report["telemetry"]
    asyncio.run(_test())



def test_api_realtime_telemetry_and_reset_endpoints():
    with TestClient(app) as client:
        # 1. Test Database Reset (4 Chennai + 4 TN tasks)
        reset_res = client.post("/api/database/reset-tamilnadu")
        assert reset_res.status_code == 200
        reset_data = reset_res.json()
        assert reset_data["status"] == "SUCCESS"
        assert reset_data["incidents_count"] == 8

        # Verify exact 4 Chennai + 4 Tamil Nadu Tasks
        inc_res = client.get("/api/incidents")
        assert inc_res.status_code == 200
        incidents = inc_res.json()
        assert len(incidents) == 8

        chennai_tasks = [inc for inc in incidents if inc["id"].startswith("INC-CHE")]
        tn_tasks = [inc for inc in incidents if inc["id"].startswith("INC-TN")]

        assert len(chennai_tasks) == 4, f"Expected 4 Chennai tasks, found {len(chennai_tasks)}"
        assert len(tn_tasks) == 4, f"Expected 4 Tamil Nadu tasks, found {len(tn_tasks)}"

        # Verify all coordinates are strictly within Tamil Nadu bounds (Lat: 8.0 - 13.6, Lng: 76.2 - 80.5)
        for inc in incidents:
            lat = inc["latitude"]
            lng = inc["longitude"]
            assert 8.0 <= lat <= 13.6, f"Incident {inc['id']} lat {lat} outside Tamil Nadu!"
            assert 76.2 <= lng <= 80.5, f"Incident {inc['id']} lng {lng} outside Tamil Nadu!"

        # 2. Test Real-time Telemetry Endpoint
        tel_res = client.get("/api/realtime/tamilnadu-telemetry")
        assert tel_res.status_code == 200
        tel_data = tel_res.json()
        assert tel_data["region"] == "Tamil Nadu, India"
        assert len(tel_data["station_reports"]) >= 8

        # 3. Test Real-time Alert Sync
        sync_res = client.post("/api/realtime/sync-tamilnadu-alerts")
        assert sync_res.status_code == 200
        sync_data = sync_res.json()
        assert sync_data["status"] == "SUCCESS"
