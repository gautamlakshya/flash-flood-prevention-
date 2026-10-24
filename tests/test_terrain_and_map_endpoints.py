import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.database import SessionLocal, LiveAlertEvent
from datetime import datetime, timezone

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_terrain_summary_endpoint(test_client):
    res = test_client.get("/api/v1/terrain/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "READY"
    assert "Chungthang" in data["study_area"]
    assert data["layers"]["catchment"] is True
    assert data["layers"]["streams"] is True
    assert data["target_coordinates"]["cwc_reference_coordinate"] == [88.6475, 27.5833]
    assert data["target_coordinates"]["dem_snapped_outlet_coordinate"] == [88.6551, 27.5851]

def test_terrain_catchment_endpoint(test_client):
    res = test_client.get("/api/v1/terrain/catchment")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) >= 1
    feat = data["features"][0]
    assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert feat["properties"]["area_km2"] > 2500  # ~2,969 km2

def test_terrain_streams_endpoint(test_client):
    res = test_client.get("/api/v1/terrain/streams")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1413  # exact SRTM stream count
    assert data["features"][0]["geometry"]["type"] == "LineString"

def test_terrain_locations_endpoint(test_client):
    res = test_client.get("/api/v1/terrain/locations")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    features = data["features"]

    # Verify CWC Reference Station
    cwc_feats = [f for f in features if f["properties"]["id"] == "cwc_reference_station"]
    assert len(cwc_feats) == 1
    cwc = cwc_feats[0]
    assert cwc["geometry"]["coordinates"] == [88.6475, 27.5833]
    assert cwc["properties"]["is_operational_outlet"] is False

    # Verify DEM-Snapped Operational Outlet
    dem_feats = [f for f in features if f["properties"]["id"] == "dem_snapped_outlet"]
    assert len(dem_feats) == 1
    dem = dem_feats[0]
    assert dem["geometry"]["coordinates"] == [88.6551, 27.5851]
    assert dem["properties"]["is_operational_outlet"] is True
    assert dem["properties"]["flow_accumulation_cells"] > 3000000

    # Ensure CWC coord != DEM snapped coord
    assert cwc["geometry"]["coordinates"] != dem["geometry"]["coordinates"]

    # Verify settlements exist
    names = [f["properties"]["name"] for f in features]
    assert any("Chungthang Town" in n for n in names)
    assert any("Teesta III" in n for n in names)
    assert any("Lachen" in n for n in names)
    assert any("Lachung" in n for n in names)

def test_terrain_metadata_endpoint(test_client):
    res = test_client.get("/api/v1/terrain/metadata")
    assert res.status_code == 200
    data = res.json()
    assert data["crs"] == "EPSG:4326 (WGS 84)"
    assert data["catchment_area_km2"] == 2969.41
    assert data["target_coordinates"]["cwc_reference_coordinate"] == [88.6475, 27.5833]
    assert data["target_coordinates"]["dem_snapped_outlet_coordinate"] == [88.6551, 27.5851]
    assert "provenance" in data["coordinate_provenance_note"].lower() or "reference" in data["coordinate_provenance_note"].lower()

def test_alerts_active_and_detail_endpoints(test_client, db_session):
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    alert = LiveAlertEvent(
        id="TEST-ACTIVE-ALERT-001",
        alert_type="FORECAST",
        severity="WARNING",
        headline="FLASH FLOOD WARNING (FORECAST): Chungthang Basin",
        description="NWP precipitation accumulation exceeded warning threshold",
        zone="Chungthang Basin (Teesta River)",
        trigger_rule="3h rain 65.0mm >= Warning (60.0mm)",
        trigger_inputs={"p_3h_mm": 65.0},
        threshold_value=60.0,
        threshold_name="3h Rainfall Warning",
        data_freshness_minutes=15.0,
        status="ACTIVE",
        created_at=now_naive,
        is_active=True
    )
    db_session.add(alert)
    db_session.commit()

    # Test /api/v1/alerts/active
    res_active = test_client.get("/api/v1/alerts/active")
    assert res_active.status_code == 200
    active_data = res_active.json()
    assert active_data["has_active_threat"] is True
    assert active_data["alert"]["id"] == "TEST-ACTIVE-ALERT-001"
    assert active_data["alert"]["severity"] == "WARNING"
    assert active_data["alert"]["alert_type"] == "FORECAST"

    # Test /api/v1/alerts/detail/{id}
    res_detail = test_client.get("/api/v1/alerts/detail/TEST-ACTIVE-ALERT-001")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["id"] == "TEST-ACTIVE-ALERT-001"
    assert detail_data["trigger_inputs"]["p_3h_mm"] == 65.0

    # Cleanup
    db_session.delete(alert)
    db_session.commit()
