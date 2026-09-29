import asyncio
import pytest
from fastapi.testclient import TestClient
from app.server import app
from app.google_maps import haversine_distance, fetch_poi, get_route
import app.services.fleet_service as fleet_service

def test_haversine_distance():
    # Test distance between Central Chennai (13.0827, 80.2707) and Guindy (13.0067, 80.2024)
    dist = haversine_distance(13.0827, 80.2707, 13.0067, 80.2024)
    # Approx 11-12 km
    assert 10.0 <= dist <= 13.0
    # Same point distance should be 0
    assert haversine_distance(13.0, 80.0, 13.0, 80.0) == 0.0

def test_fetch_poi():
    pois = fetch_poi(13.0827, 80.2707, radius=5000)
    assert isinstance(pois, list)
    assert len(pois) > 0
    first_poi = pois[0]
    assert "name" in first_poi
    assert "type" in first_poi
    assert "latitude" in first_poi
    assert "longitude" in first_poi
    assert "distance_km" in first_poi

def test_get_route():
    origin = (13.0784, 80.2604)
    destination = (13.0827, 80.2707)
    route = get_route(origin, destination)
    assert "distance_m" in route
    assert "duration_s" in route
    assert "eta_minutes" in route
    assert "distance_km" in route
    assert route["distance_km"] > 0
    assert route["eta_minutes"] >= 1

def test_fleet_service_list_stations():
    async def _test():
        stations = await fleet_service.list_stations()
        assert len(stations) > 0
        types = [s.type for s in stations]
        assert "FIRE" in types or "POLICE" in types
    asyncio.run(_test())

def test_fleet_service_list_response_units():
    async def _test():
        units = await fleet_service.list_response_units()
        assert len(units) > 0
        assert any(u.unit_type == "FIRE_ENGINE" for u in units)
    asyncio.run(_test())

def test_fleet_service_assign_nearest():
    async def _test():
        # Incident near Egmore (13.0780, 80.2600)
        rec = await fleet_service.assign_nearest(
            incident_lat=13.0780,
            incident_lng=80.2600,
            unit_type="FIRE_ENGINE",
            disaster_type="FIRE"
        )
        assert "unit" in rec
        assert "route" in rec
        assert "eta_minutes" in rec
        assert rec["distance_km"] >= 0
    asyncio.run(_test())

def test_api_stations_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/stations")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]
        assert "latitude" in data[0]

def test_api_response_units_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/response_units")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) > 0

def test_api_pois_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/pois?lat=13.0827&lng=80.2707&radius=5000")
        assert res.status_code == 200
        pois = res.json()
        assert isinstance(pois, list)
        assert len(pois) > 0

def test_api_nearest_dispatch_recommendation():
    with TestClient(app) as client:
        # Create an incident
        inc_payload = {
            "title": "Industrial Tanker Fire at Manali Gate 2",
            "type": "FIRE",
            "severity": "CRITICAL",
            "locationName": "Manali Industrial Corridor, Chennai",
            "latitude": 13.1670,
            "longitude": 80.2640,
            "urgencyScore": 95
        }
        create_res = client.post("/api/incidents", json=inc_payload)
        assert create_res.status_code == 200
        inc = create_res.json()
        inc_id = inc["id"]

        # Call nearest dispatch recommendation
        rec_res = client.post(f"/api/incidents/{inc_id}/nearest-dispatch", json={"unit_type": "FIRE_ENGINE"})
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        assert rec_data["status"] == "SUCCESS"
        assert "recommendation" in rec_data
        assert rec_data["recommendation"]["eta_minutes"] >= 1

        # Test automatic nearest dispatch when unit_ids omitted
        auto_disp = client.post(f"/api/incidents/{inc_id}/dispatch", json={})
        assert auto_disp.status_code == 200
        disp_data = auto_disp.json()
        assert disp_data["status"] == "SUCCESS"
        assert len(disp_data["dispatched_unit_ids"]) > 0

def test_sriperumbudur_local_station_mapping():
    with TestClient(app) as client:
        # Sriperumbudur Emergency (12.9675, 79.9400)
        inc_payload = {
            "title": "Industrial Collapse at Sriperumbudur SIPCOT",
            "type": "INDUSTRIAL",
            "severity": "CRITICAL",
            "locationName": "Sriperumbudur SIPCOT Sector 2",
            "latitude": 12.9675,
            "longitude": 79.9400,
            "urgencyScore": 100
        }
        create_res = client.post("/api/incidents", json=inc_payload)
        assert create_res.status_code == 200
        inc_id = create_res.json()["id"]

        rec_res = client.post(f"/api/incidents/{inc_id}/nearest-dispatch", json={"unit_type": "FIRE_ENGINE"})
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        assert rec_data["status"] == "SUCCESS"
        rec = rec_data["recommendation"]
        
        # Must map to the local Sriperumbudur station and unit (< 1 km), NOT a 40km distant station!
        assert "Sriperumbudur" in rec["station"]["name"]
        assert rec["distance_km"] < 2.0
        assert rec["eta_minutes"] <= 5
        assert rec["unit"]["id"] == "FIRE-BR-SPB-01"

        # Check nearby POIs in Sriperumbudur
        poi_res = client.get("/api/pois?lat=12.9675&lng=79.9400&radius=5000")
        assert poi_res.status_code == 200
        pois = poi_res.json()
        assert len(pois) >= 2
        # Nearest POI must be under 2km
        assert pois[0]["distance_km"] < 2.0

def test_tamil_nadu_statewide_emergency_mapping():
    with TestClient(app) as client:
        # Test 1: Coimbatore (11.0168, 76.9558)
        cbe_res = client.post("/api/incidents", json={
            "title": "Textile Mill Fire at Peelamedu, Coimbatore",
            "type": "FIRE",
            "severity": "CRITICAL",
            "locationName": "Peelamedu, Coimbatore",
            "latitude": 11.0168,
            "longitude": 76.9558,
            "urgencyScore": 90
        })
        cbe_id = cbe_res.json()["id"]
        cbe_rec = client.post(f"/api/incidents/{cbe_id}/nearest-dispatch", json={"unit_type": "FIRE_ENGINE"}).json()["recommendation"]
        assert "Coimbatore" in cbe_rec["station"]["name"]
        assert cbe_rec["distance_km"] < 2.0
        assert cbe_rec["unit"]["id"] == "FIRE-BR-CBE-01"

        # Test 2: Madurai (9.9252, 78.1198)
        mdu_res = client.post("/api/incidents", json={
            "title": "Flash Flooding at Vaigai River Bank, Madurai",
            "type": "FLOOD",
            "severity": "CRITICAL",
            "locationName": "Madurai Central",
            "latitude": 9.9252,
            "longitude": 78.1198,
            "urgencyScore": 95
        })
        mdu_id = mdu_res.json()["id"]
        mdu_rec = client.post(f"/api/incidents/{mdu_id}/nearest-dispatch", json={"unit_type": "FIRE_ENGINE"}).json()["recommendation"]
        assert "Madurai" in mdu_rec["station"]["name"]
        assert mdu_rec["distance_km"] < 2.0
        assert mdu_rec["unit"]["id"] == "FIRE-BR-MDU-01"

        # Test 3: Trichy (10.7905, 78.7047)
        try_res = client.post("/api/incidents", json={
            "title": "Gas Leak at Thuvakudi Industrial Estate, Trichy",
            "type": "INDUSTRIAL",
            "severity": "HIGH",
            "locationName": "Tiruchirappalli",
            "latitude": 10.7905,
            "longitude": 78.7047,
            "urgencyScore": 85
        })
        try_id = try_res.json()["id"]
        try_rec = client.post(f"/api/incidents/{try_id}/nearest-dispatch", json={"unit_type": "FIRE_ENGINE"}).json()["recommendation"]
        assert "Trichy" in try_rec["station"]["name"]
        assert try_rec["distance_km"] < 2.0
        assert try_rec["unit"]["id"] == "FIRE-BR-TRY-01"


