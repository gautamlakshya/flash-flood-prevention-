import pytest
import asyncio
import json
from backend.app.models.database import SessionLocal, SimulationRun
from backend.app.api.routes.simulation import get_simulation_results
import uuid

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def is_near_chungthang(lon, lat):
    # Chungthang: 88.6475, 27.6033
    return 88.5 < lon < 88.8 and 27.5 < lat < 27.8

def is_near_assam(lon, lat):
    # Old Assam: 92.8, 26.3
    return 92.0 < lon < 93.5 and 26.0 < lat < 26.5

def test_chungthang_spatial_anchor(db_session):
    """TEST A & C: Assert GeoJSON is near Chungthang and NOT Assam."""
    run_id = "TEST-CHUNG-" + uuid.uuid4().hex[:6]
    run = SimulationRun(
        id=run_id,
        scenario="Extreme Cloudburst",
        data_mode="SIMULATION",
        status="COMPLETED"
    )
    db_session.add(run)
    db_session.commit()
    
    payload = asyncio.run(get_simulation_results(run_id, db_session))
    geojson = payload.get("inundation_geojson")
    assert geojson is not None
    features = geojson.get("features", [])
    assert len(features) > 0
    
    for feat in features:
        geom = feat["geometry"]
        coords = []
        if geom["type"] == "Polygon":
            coords = geom["coordinates"][0]
        elif geom["type"] == "MultiPolygon":
            coords = geom["coordinates"][0][0]
        
        for lon, lat in coords:
            assert is_near_chungthang(lon, lat), f"Coordinate {lon},{lat} is not near Chungthang!"
            assert not is_near_assam(lon, lat), f"Coordinate {lon},{lat} is near legacy Assam!"

def test_same_geography_different_stage(db_session):
    """TEST B: Same geography, different stage & inundation."""
    run_id_A = "TEST-MAP-A-" + uuid.uuid4().hex[:6]
    run_id_B = "TEST-MAP-B-" + uuid.uuid4().hex[:6]
    
    run_A = SimulationRun(id=run_id_A, scenario="Normal Monsoon", data_mode="SIMULATION", status="COMPLETED")
    run_B = SimulationRun(id=run_id_B, scenario="Extreme Cloudburst", data_mode="SIMULATION", status="COMPLETED")
    
    db_session.add_all([run_A, run_B])
    db_session.commit()
    
    payload_A = asyncio.run(get_simulation_results(run_id_A, db_session))
    payload_B = asyncio.run(get_simulation_results(run_id_B, db_session))
    
    stage_A = payload_A["metrics"]["stage_m"]
    stage_B = payload_B["metrics"]["stage_m"]
    assert stage_A != stage_B, "Stage should differ"
    
    str_A = json.dumps(payload_A.get("inundation_geojson"), sort_keys=True)
    str_B = json.dumps(payload_B.get("inundation_geojson"), sort_keys=True)
    assert str_A != str_B, "Inundation polygons should differ"
    
    # Assert they both use Chungthang coordinates
    coords_A = payload_A["inundation_geojson"]["features"][0]["geometry"]["coordinates"][0][0]
    coords_B = payload_B["inundation_geojson"]["features"][0]["geometry"]["coordinates"][0][0]
    
    assert is_near_chungthang(coords_A[0], coords_A[1])
    assert is_near_chungthang(coords_B[0], coords_B[1])

def test_cap_geometry(db_session):
    """TEST D: CAP geometry is derived from inundation and not Assam."""
    run_id = "TEST-CAP-" + uuid.uuid4().hex[:6]
    run = SimulationRun(
        id=run_id,
        scenario="Extreme Cloudburst",
        data_mode="SIMULATION",
        status="COMPLETED"
    )
    db_session.add(run)
    db_session.commit()
    
    payload = asyncio.run(get_simulation_results(run_id, db_session))
    cap_xml = payload.get("cap_xml")
    
    assert cap_xml is not None
    assert "92.8" not in cap_xml and "26.3" not in cap_xml, "CAP XML contains legacy Assam coordinates!"
    assert "88.6" in cap_xml and ("27.5" in cap_xml or "27.6" in cap_xml), "CAP XML should contain Chungthang coordinates derived from GeoJSON!"

