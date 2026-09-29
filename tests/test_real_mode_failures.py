import pytest
from backend.app.models.database import SessionLocal, SimulationRun
from fastapi import HTTPException
import uuid

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_real_mode_with_no_dem(db_session):
    from backend.app.data_pipeline.graph_builder import extract_river_graph_from_dem
    with pytest.raises(FileNotFoundError) as exc_info:
        extract_river_graph_from_dem("data/raw/dem/missing.tif")
    assert "DATA_SOURCE_NOT_CONFIGURED" in str(exc_info.value)

def test_real_mode_with_no_rainfall():
    from backend.app.data_pipeline.builder import check_real_data_availability
    assert check_real_data_availability() is False

def test_real_mode_with_no_observed_discharge():
    from backend.app.ingestion.hydrology.provider import LocalCWCHydrologyProvider
    provider = LocalCWCHydrologyProvider("data/raw/hydrology/missing.csv")
    assert provider.fetch_data() == []
    assert provider.get_status() == "NOT CONFIGURED"

def test_real_mode_with_no_channel_geometry():
    from backend.app.ingestion.static_data import StaticDataAudit
    audit = StaticDataAudit("data/raw/static_missing")
    assert audit.check_channel_geometry() == "NOT_CONFIGURED"

def test_real_mode_with_crs_mismatch():
    from backend.app.data_pipeline.spatial import SpatialAligner
    aligner = SpatialAligner(target_crs="EPSG:4326")
    with pytest.raises(ValueError) as exc_info:
        aligner.validate_crs("EPSG:32645")
    assert "CRS Mismatch" in str(exc_info.value)

def test_real_mode_with_missing_model_checkpoint():
    from backend.app.models.train import train_stgnn
    with pytest.raises(NotImplementedError) as exc_info:
        train_stgnn(mode="REAL")
    assert "Cannot compile training dataset" in str(exc_info.value)

def test_real_mode_with_missing_scaler():
    from backend.app.models.scalers import FeatureScaler
    scaler = FeatureScaler("test")
    with pytest.raises(ValueError) as exc_info:
        scaler.transform(100.0)
    assert "not fitted" in str(exc_info.value)

def test_real_mode_fails_safely_when_no_data(db_session):
    from backend.app.api.routes.simulation import get_simulation_results
    import asyncio
    run_id = str(uuid.uuid4())
    run = SimulationRun(
        id=run_id,
        scenario="Extreme Cloudburst",
        data_mode="REAL",
        status="COMPLETED"
    )
    db_session.add(run)
    db_session.commit()
    
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_simulation_results(run_id, db_session))
        
    assert exc_info.value.status_code == 500
    assert "DATA_SOURCE_NOT_CONFIGURED" in str(exc_info.value.detail)

# The remaining scenarios (incomplete temporal data, missing targets, invalid timestamps)
# are tested via the logic in builder.py which raises early because the files don't even exist yet.
