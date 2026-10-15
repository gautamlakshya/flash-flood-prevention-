import pytest
import asyncio
import uuid
from backend.app.models.database import SessionLocal, SimulationRun
from backend.app.api.routes.simulation import get_map_config, get_simulation_results

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_map_config_endpoint_resilience():
    """Verify map-config returns a valid CONFIGURED response for Chungthang."""
    res = asyncio.run(get_map_config())
    assert res["status"] in ["CONFIGURED", "READY"]
    assert res["study_area"] == "Chungthang"
    lon, lat = res["default_center"]
    assert 88.5 < lon < 88.8 and 27.5 < lat < 27.8
    assert res["default_zoom"] >= 10

def test_simulation_workflow_end_to_end(db_session):
    """Verify full end-to-end simulation returns expected schema and results."""
    run_id = f"TEST-RESILIENCE-{uuid.uuid4().hex[:6]}"
    run = SimulationRun(
        id=run_id,
        scenario="Extreme Cloudburst",
        data_mode="SIMULATION",
        status="COMPLETED"
    )
    db_session.add(run)
    db_session.commit()

    payload = asyncio.run(get_simulation_results(run_id, db_session))

    assert payload["run_id"] == run_id
    assert payload["scenario"] == "Extreme Cloudburst"
    metrics = payload["metrics"]
    assert metrics["predicted_discharge"] > 0
    assert metrics["hazard"] in ["FLASH FLOOD WARNING", "WATCH", "NORMAL"]
    assert metrics["stage_m"] > 0
    assert len(payload["timeseries"]) > 0
    assert "features" in payload["inundation_geojson"]
    assert payload["provenance"]["model"] is not None
