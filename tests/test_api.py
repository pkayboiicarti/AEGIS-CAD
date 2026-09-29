import pytest
from fastapi.testclient import TestClient
from app.server import app

def test_api_health_and_stats():
    with TestClient(app) as client:
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_incidents" in data
        assert "active_critical" in data
        assert "available_units" in data

def test_api_ingest_disaster_emergency():
    with TestClient(app) as client:
        payload = {
            "raw_message": "CRITICAL EMERGENCY! Chemical tanker explosion and fire at Guindy Industrial Estate. 6 workers burned and 4 trapped inside warehouse. Need emergency fire tenders and ambulances!",
            "metadata_or_coordinates": "Guindy Industrial Estate, Chennai",
            "channel": "EMERGENCY_APP"
        }
        response = client.post("/api/ingest", json=payload)
        assert response.status_code == 200
        res = response.json()
        assert res["status"] in ["SUCCESS", "MERGED"]
        assert res["triage_result"]["is_relevant"] is True
        assert res["incident_record"] is not None
        
        inc = res["incident_record"]
        assert inc["type"] in ["FIRE", "INDUSTRIAL"]
        assert inc["urgency_score"] >= 70
        assert inc["urgencyScore"] >= 70
        assert "coordinates" in inc
        assert "lat" in inc["coordinates"] and "lng" in inc["coordinates"]
        assert inc["currentStatus"] in ["REPORTED", "PENDING"]
        assert "affectedPeople" in inc
        assert inc["affectedPeople"]["trapped"] >= 4
        assert inc["locationName"] != ""

def test_api_create_incident_endpoint():
    with TestClient(app) as client:
        payload = {
            "title": "Severe Flash Flood near Adyar Bridge",
            "type": "FLOOD",
            "severity": "CRITICAL",
            "currentStatus": "REPORTED",
            "locationName": "Adyar Bridge, Chennai",
            "coordinates": { "lat": 13.0067, "lng": 80.2570 },
            "urgencyScore": 92,
            "sosAlertsCount": 3,
            "affectedPeople": { "injured": 1, "trapped": 8, "evacuated": 12, "totalEstimated": 21 }
        }
        response = client.post("/api/incidents", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Severe Flash Flood near Adyar Bridge"
        assert data["type"] == "FLOOD"
        assert data["severity"] == "CRITICAL"
        assert data["coordinates"]["lat"] == 13.0067
        assert data["affectedPeople"]["trapped"] == 8

def test_api_list_incidents():
    with TestClient(app) as client:
        response = client.get("/api/incidents")
        assert response.status_code == 200
        incidents = response.json()
        assert isinstance(incidents, list)
        if len(incidents) > 0:
            first = incidents[0]
            assert "coordinates" in first
            assert "locationName" in first or "location_name" in first

def test_api_list_units():
    with TestClient(app) as client:
        response = client.get("/api/units")
        assert response.status_code == 200
        units = response.json()
        assert len(units) >= 5

def test_api_sitrep_export():
    with TestClient(app) as client:
        response = client.get("/api/export/sitrep")
        assert response.status_code == 200
        text = response.text
        assert "STATE DISASTER MANAGEMENT AUTHORITY" in text
        assert "Priority Incident Matrix" in text

def test_api_geospatial_deduplication():
    with TestClient(app) as client:
        # 1. Create base incident in Velachery
        payload1 = {
            "title": "Severe Flash Flood near Velachery Lake View",
            "type": "FLOOD",
            "severity": "CRITICAL",
            "locationName": "Velachery Lake View Sector 4, Chennai",
            "coordinates": { "lat": 12.9791, "lng": 80.2185 },
            "urgencyScore": 90,
            "sosAlertsCount": 1,
            "affectedPeople": { "injured": 2, "trapped": 5, "evacuated": 0, "totalEstimated": 7 }
        }
        res1 = client.post("/api/incidents", json=payload1)
        assert res1.status_code == 200
        inc_id = res1.json()["id"]

        # 2. Ingest duplicate report within 200m (same location)
        dup_payload = {
            "raw_message": "URGENT SOS! Floods in Velachery Lake View sector 4! 3 more people trapped on rooftop! Send help!",
            "metadata_or_coordinates": "Velachery Lake View Sector 4 (12.9791, 80.2185)",
            "channel": "TWITTER_SOS"
        }
        res2 = client.post("/api/ingest", json=dup_payload)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "MERGED"
        assert data2["merged"] is True
        assert data2["incident_record"]["sosAlertsCount"] >= 2
        assert data2["incident_record"]["affectedPeople"]["trapped"] >= 5

def test_api_field_responder_status_patch_and_victims():
    with TestClient(app) as client:
        # Create an incident
        inc_res = client.post("/api/incidents", json={
            "title": "Industrial Hazmat Gas Leak at Manali",
            "type": "INDUSTRIAL",
            "severity": "CRITICAL",
            "locationName": "Manali Industrial Zone Gate 3",
            "coordinates": { "lat": 13.1673, "lng": 80.2644 },
            "urgencyScore": 95,
            "affectedPeople": { "injured": 4, "trapped": 2, "evacuated": 0, "totalEstimated": 6 }
        })
        inc_id = inc_res.json()["id"]

        # 1. Test PATCH status to ON_SCENE
        patch_res = client.patch(f"/api/incidents/{inc_id}/status", json={
            "status": "ON_SCENE",
            "notes": "Responder units arrived at Gate 3. SCBA units deployed.",
            "authorName": "Capt. Marcus Vance (COMMAND-ALPHA)",
            "authorRole": "FIELD_RESPONDER"
        })
        assert patch_res.status_code == 200
        assert patch_res.json()["incident"]["status"] == "ON_SCENE"

        # 2. Test Logging a Victim
        victim_res = client.post(f"/api/incidents/{inc_id}/victims", json={
            "name": "Ramesh Kumar (Worker)",
            "category": "RED",
            "notes": "Severe ammonia inhalation, administered emergency oxygen",
            "rescued": True,
            "authorName": "Capt. Marcus Vance"
        })
        assert victim_res.status_code == 200
        data = victim_res.json()
        assert data["status"] == "SUCCESS"
        assert len(data["incident"]["victims"]) >= 1
        assert data["incident"]["affected_evacuated"] >= 1

def test_api_teams_dispatch_and_session_export():
    with TestClient(app) as client:
        # 1. Fetch available teams
        teams_res = client.get("/api/teams")
        assert teams_res.status_code == 200
        teams = teams_res.json()
        assert len(teams) > 0
        avail_team = next((t for t in teams if t["status"] == "AVAILABLE"), teams[0])

        # 2. Create incident
        inc_res = client.post("/api/incidents", json={
            "title": "Structural Collapse in T. Nagar Commercial Complex",
            "type": "STRUCTURAL_COLLAPSE",
            "severity": "HIGH",
            "locationName": "T. Nagar Ranganathan St",
            "coordinates": { "lat": 13.0405, "lng": 80.2337 },
            "urgencyScore": 85
        })
        inc_id = inc_res.json()["id"]

        # 3. Dispatch single team
        disp_res = client.post(f"/api/teams/{avail_team['id']}/dispatch", json={
            "incident_id": inc_id,
            "notes": "Direct mobilization for heavy extrication"
        })
        assert disp_res.status_code == 200
        disp_data = disp_res.json()
        assert disp_data["status"] == "SUCCESS"
        assert avail_team["id"] in disp_data["incident"]["dispatched_units"]

        # 4. Test Session Export JSON
        export_res = client.get("/api/export/session")
        assert export_res.status_code == 200
        export_json = export_res.json()
        assert "export_metadata" in export_json
        assert "system_stats" in export_json
        assert "incidents" in export_json
        assert "responder_units" in export_json
        assert len(export_json["incidents"]) > 0

def test_api_live_ingest_and_public_portal():
    with TestClient(app) as client:
        # 1. Test public report page GET /report
        rep_page = client.get("/report")
        assert rep_page.status_code == 200
        assert "State Emergency Operations Center" in rep_page.text

        # 2. Test live real-time ingestion webhook (POST /api/ingest/live)
        payload = {
            "rawText": "URGENT SOS! Severe chemical tank leak at Ennore Thermal Station gate 2! Workers choking, at least 6 people collapsed.",
            "source": "CITIZEN_PORTAL",
            "lat": 13.2084,
            "lng": 80.3255,
            "senderContact": "+91 98840 99881",
            "category": "INDUSTRIAL"
        }
        res = client.post("/api/ingest/live", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["SUCCESS", "MERGED"]
        incident_id = data.get("incidentId") or data.get("incident_id")
        assert incident_id.startswith("INC-")
        assert data["incident"]["type"] == "INDUSTRIAL"
        assert data["incident"]["urgency_score"] >= 70


        # 3. Test non-emergency message rejection
        junk_payload = {
            "rawText": "Good morning, looking for local bus timetable from Central station to airport.",
            "source": "PUBLIC_CITIZEN_PORTAL"
        }
        junk_res = client.post("/api/ingest/live", json=junk_payload)
        assert junk_res.status_code == 200
        junk_data = junk_res.json()
        assert junk_data["status"] == "DISCARDED"
        assert junk_data["is_relevant"] is False

def test_api_aar_and_resolution_unit_release():
    with TestClient(app) as client:
        # 1. Create a test incident
        inc_res = client.post("/api/incidents", json={
            "id": "INC-TEST-AAR-99",
            "title": "AAR Test Warehouse Fire",
            "type": "FIRE",
            "severity": "HIGH",
            "urgency_score": 85,
            "location_name": "Ambattur Industrial Estate",
            "latitude": 13.1143,
            "longitude": 80.1548,
            "affected_injured": 4,
            "affected_trapped": 2,
            "affected_evacuated": 20,
            "affected_total": 26,
            "raw_text": "Warehouse chemical fire in Ambattur Estate Sector 3.",
            "status": "PENDING"
        })
        assert inc_res.status_code == 200

        # 2. Dispatch a unit to it
        disp_res = client.post("/api/incidents/INC-TEST-AAR-99/dispatch", json={
            "unit_ids": ["FIRE-BR-01"],
            "notes": "Testing unit assignment for AAR lifecycle"
        })
        assert disp_res.status_code == 200

        # 3. Add a triage victim
        v_res = client.post("/api/incidents/INC-TEST-AAR-99/victims", json={
            "name": "Arun Kumar",
            "triageTag": "RED",
            "condition": "Severe smoke inhalation",
            "notes": "Administered oxygen"
        })
        assert v_res.status_code == 200

        # 4. Resolve the incident
        res_res = client.post("/api/incidents/INC-TEST-AAR-99/status", json={
            "status": "RESOLVED",
            "notes": "Fire extinguished, victims evacuated, all clear."
        })
        assert res_res.status_code == 200

        # 5. Verify unit is released back to AVAILABLE
        units_res = client.get("/api/units")
        assert units_res.status_code == 200
        all_units = units_res.json()
        u1 = next((u for u in all_units if u["id"] == "FIRE-BR-01"), None)
        assert u1 is not None
        assert u1["status"] == "AVAILABLE"
        assert u1["assigned_incident_id"] is None

        # 6. Test GET /api/incidents/INC-TEST-AAR-99/aar
        aar_res = client.get("/api/incidents/INC-TEST-AAR-99/aar")
        assert aar_res.status_code == 200
        aar_data = aar_res.json()
        assert aar_data["status"] == "SUCCESS"
        aar = aar_data["aar"]
        assert aar["incident_id"] == "INC-TEST-AAR-99"
        assert aar["type"] == "FIRE"
        assert "victim_triage_tally" in aar
        assert aar["victim_triage_tally"]["RED"] >= 1
        assert "duration_minutes" in aar
        assert len(aar["timeline"]) >= 3

def test_api_ingest_image_multipart_and_json():
    with TestClient(app) as client:
        # Mock 1x1 GIF byte payload
        mock_gif = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"
        
        # 1. Test multipart/form-data image upload
        files = {"file": ("flood_recon.jpg", mock_gif, "image/jpeg")}
        data = {
            "caption": "Waist-high floodwater in Velachery Lake View Sector with stranded families.",
            "location_name": "Velachery Sector 4",
            "lat": "12.9791",
            "lng": "80.2185"
        }
        res = client.post("/api/ingest/image", files=files, data=data)
        assert res.status_code == 200
        res_data = res.json()
        assert res_data["status"] in ["SUCCESS", "MERGED"]
        assert res_data["is_disaster_related"] is True
        assert res_data["analysis"]["disaster_category"] == "FLOOD"
        assert len(res_data["analysis"]["visual_evidence"]) >= 1

        # 2. Test JSON base64 image upload
        import base64
        b64_str = base64.b64encode(mock_gif).decode("utf-8")
        json_payload = {
            "image_base64": f"data:image/jpeg;base64,{b64_str}",
            "caption": "Massive structural blaze and heavy smoke at industrial plant.",
            "location_name": "Guindy Industrial Estate"
        }
        json_res = client.post("/api/ingest/image", json=json_payload)
        assert json_res.status_code == 200
        json_data = json_res.json()
        assert json_data["status"] in ["SUCCESS", "MERGED"]
        assert json_data["is_disaster_related"] is True
        assert json_data["analysis"]["disaster_category"] == "FIRE"

        # 3. Test non-emergency image rejection
        neg_payload = {
            "image_base64": f"data:image/jpeg;base64,{b64_str}",
            "caption": "Sunny peaceful afternoon at coffee cafe with pets."
        }
        neg_res = client.post("/api/ingest/image", json=neg_payload)
        assert neg_res.status_code == 200
        neg_data = neg_res.json()
        assert neg_data["status"] == "DISCARDED"
        assert neg_data["is_disaster_related"] is False


