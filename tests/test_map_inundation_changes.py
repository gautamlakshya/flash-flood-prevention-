import pytest
import asyncio
from backend.app.models.database import SessionLocal, SimulationRun
from backend.app.api.routes.simulation import get_simulation_results, start_simulation

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_map_geometry_changes_with_backend_output(db_session):
    """
    Objective 11: CRITICAL MAP TEST
    Proves that the map geometry (inundation) actually changes when the backend 
    hydrological output (stage/scenario) changes, and isn't just a static mockup.
    """
    import uuid
    
    # We will simulate two different scenarios in SIMULATION mode
    # since REAL mode is safely blocked without data.
    run_id_A = "TEST-MAP-A-" + uuid.uuid4().hex[:6]
    run_id_B = "TEST-MAP-B-" + uuid.uuid4().hex[:6]
    
    # Force insert A
    run_A = SimulationRun(
        id=run_id_A,
        scenario="Normal Monsoon",
        data_mode="SIMULATION",
        status="COMPLETED"
    )
    db_session.add(run_A)
    
    # Force insert B
    run_B = SimulationRun(
        id=run_id_B,
        scenario="Extreme Cloudburst",
        data_mode="SIMULATION",
        status="COMPLETED"
    )
    db_session.add(run_B)
    db_session.commit()
    
    # Fetch payloads (which executes the pipeline inside)
    async def fetch_both():
        pa = await get_simulation_results(run_id_A, db_session)
        pb = await get_simulation_results(run_id_B, db_session)
        return pa, pb
        
    payload_A, payload_B = asyncio.run(fetch_both())
    
    stage_A = payload_A["metrics"]["stage_m"]
    stage_B = payload_B["metrics"]["stage_m"]
    
    # 1. Ensure the stage is different
    assert stage_A != stage_B, "Stage should differ between scenarios"
    
    geojson_A = payload_A.get("inundation_geojson")
    geojson_B = payload_B.get("inundation_geojson")
    
    # 2. Ensure both generated GeoJSON
    assert geojson_A is not None, "Scenario A failed to generate GeoJSON"
    assert geojson_B is not None, "Scenario B failed to generate GeoJSON"
    
    # 3. Ensure they are actually different geometries
    # We can hash the features or just compare the string representations
    import json
    str_A = json.dumps(geojson_A, sort_keys=True)
    str_B = json.dumps(geojson_B, sort_keys=True)
    
    assert str_A != str_B, "CRITICAL FAILURE: Map GeoJSON payload did not change between scenarios. Map behaves like a mockup."
    
    # 4. Check feature counts or actual coordinates to be extra certain
    features_A = len(geojson_A.get("features", []))
    features_B = len(geojson_B.get("features", []))
    
    print(f"Scenario A: Stage={stage_A:.2f}m, Polygons={features_A}")
    print(f"Scenario B: Stage={stage_B:.2f}m, Polygons={features_B}")
    
    # One of the scenarios should produce a significantly different flood extent
    # Cloudburst is guaranteed to produce higher stage and larger extent
    assert stage_B > stage_A, "Cloudburst stage should be higher than normal monsoon"
