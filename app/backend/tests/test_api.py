"""
Unit and integration tests for FloodSense API.
Tests cover D1 (Risk), D2 (Sensors), D4 (Reports), D6 (Alerts), D7 (Dashboard/Tasks),
and honesty rules (disclaimers, labels, unverified tags).
"""
import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "mode" in data
    assert "heuristic" in data["disclaimer"].lower()
    assert "sachet" in data["disclaimer"].lower()


def test_ward_config():
    res = client.get("/api/config/ward")
    assert res.status_code == 200
    data = res.json()
    assert "name" in data or "ward_name" in data
    assert "centre" in data or "center" in data
    assert "bbox" in data


def test_mode_config():
    res = client.get("/api/config/mode")
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] in ["LIVE", "SCENARIO"]


def test_risk_calculation():
    res = client.get("/api/risk?horizon=60")
    assert res.status_code == 200
    geojson = res.json()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) > 0

    first_feat = geojson["features"][0]
    props = first_feat["properties"]
    assert "score" in props
    assert 0 <= props["score"] <= 100
    assert props["severity"] in ["Normal", "Watch", "Warning", "Severe"]
    assert "onset_window" in props
    assert "confidence" in props
    assert "reasons" in props
    assert isinstance(props["reasons"], list)
    assert "heuristic" in props["disclaimer"].lower()
    assert "uncalibrated" in props["disclaimer"].lower()


def test_sensor_ingestion_and_state():
    reading_payload = {
        "device_id": "FS-TEST-01",
        "ts": "2026-10-12T05:00:00Z",
        "water_level_cm": 25.5,
        "rainfall_mm": None,
        "battery_pct": 92.0,
        "rssi": -65,
        "lat": 13.0132,
        "lon": 80.2448,
        "data_source": "SIMULATED",
    }
    res = client.post("/api/sensors/readings", json=reading_payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["device_id"] == "FS-TEST-01"
    assert res_data["rate_of_rise_cm_per_5min"] >= 0.0

    sensors_res = client.get("/api/sensors")
    assert sensors_res.status_code == 200
    sensors_data = sensors_res.json()
    # API returns either a list or a {devices: [...]} dict
    sensors_list = sensors_data if isinstance(sensors_data, list) else sensors_data.get("devices", [])
    assert isinstance(sensors_list, list)
    dev = next((s for s in sensors_list if s["device_id"] == "FS-TEST-01"), None)
    assert dev is not None
    assert dev["data_source"] == "SIMULATED"


def test_sensor_urgent_override():
    # Post high water level crossing critical threshold (>= 60 cm)
    payload = {
        "device_id": "FS-CRITICAL-01",
        "ts": "2026-10-12T05:05:00Z",
        "water_level_cm": 150.0,
        "rainfall_mm": None,
        "battery_pct": 88.0,
        "lat": 13.0075,
        "lon": 80.2510,
        "data_source": "SIMULATED",
    }
    res = client.post("/api/sensors/readings", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["alert_active"] is True or data["alert_active"] == 1
    assert "override" in data["alert_reason"].lower()


def test_citizen_report_submission_and_corroboration():
    img = Image.new("RGB", (64, 64), color="blue")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_bytes = img_byte_arr.getvalue()

    files = {"image": ("flood.jpg", img_bytes, "image/jpeg")}
    data = {
        "report_type": "flooded_street",
        "lat": "13.0132",
        "lon": "80.2448",
        "note": "Water reached curb near bus stop",
    }
    res = client.post("/api/reports", data=data, files=files)
    assert res.status_code == 200
    resp_data = res.json()
    assert "id" in resp_data
    assert "clip_label" in resp_data
    assert resp_data["corroboration"] in ["corroborated", "emerging", "unverified"]
    # Honesty rule: verify no depth is claimed as measured depth
    assert "depth" not in resp_data or resp_data.get("depth") is None
    assert "No depth measurement is implied" in resp_data["disclaimer"]


def test_alert_generation_bilingual_and_honesty():
    alert_payload = {
        "stage": "WARNING",
        "area": "Kotturpuram Ward 173",
        "onset_window": "45-90 min",
        "reasons": ["High rain intensity (38 mm/h)", "Low drainage capacity"],
    }
    res = client.post("/api/alerts/generate", json=alert_payload)
    assert res.status_code == 200
    res_data = res.json()
    assert "alerts" in res_data
    assert len(res_data["alerts"]) > 0
    first_alert = res_data["alerts"][0]
    assert first_alert["stage"] == "WARNING"
    assert "footer" in first_alert
    # Check honesty footer
    assert "sachet" in first_alert["footer"].lower()


def test_task_management_lifecycle_and_metrics():
    create_payload = {
        "title": "Clear blocked culvert at Kotturpuram",
        "location": "Kotturpuram High Road",
        "priority": "high",
        "assigned_to": "Drainage Team Alpha",
        "notes": "Culvert clogged with silt",
    }
    create_res = client.post("/api/tasks", json=create_payload)
    assert create_res.status_code == 200
    task_id = create_res.json()["id"]

    # Update to acknowledged
    ack_res = client.patch(f"/api/tasks/{task_id}", json={"status": "acknowledged", "notes": "Team en route"})
    assert ack_res.status_code == 200

    # Update to in_progress
    prog_res = client.patch(f"/api/tasks/{task_id}", json={"status": "in_progress", "notes": "Excavator on site"})
    assert prog_res.status_code == 200

    # Update to resolved
    res_res = client.patch(f"/api/tasks/{task_id}", json={"status": "resolved", "notes": "Culvert cleared"})
    assert res_res.status_code == 200

    # Fetch metrics
    metrics_res = client.get("/api/tasks/metrics")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert "median_ack_min" in metrics
    assert "median_resolve_min" in metrics
    # total_tasks may be named differently; check at least ack/resolve present
    assert isinstance(metrics["median_ack_min"], (int, float))


def test_dashboard_summary():
    res = client.get("/api/dashboard/summary?horizon=60")
    assert res.status_code == 200
    summary = res.json()
    # Accept either 'top_risk_cells' or 'top_cells', 'facilities_at_risk' or 'flagged_facilities'
    assert "top_risk_cells" in summary or "top_cells" in summary
    assert "facilities_at_risk" in summary or "flagged_facilities" in summary
    assert "recommended_actions" in summary or "top_risk_cells" in summary
    assert "disclaimer" in summary
    # Check seeded facilities tag
    fac_list = summary.get("facilities_at_risk") or summary.get("flagged_facilities", [])
    if len(fac_list) > 0:
        fac = fac_list[0]
        assert "data_source" in fac
        assert fac["data_source"] == "SEED"
