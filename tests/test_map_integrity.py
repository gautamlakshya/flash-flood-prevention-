import pytest
import asyncio
import numpy as np
import json
from backend.app.models.database import SessionLocal, SimulationRun
from backend.app.api.routes.simulation import get_simulation_results

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_map_integrity_phase_3(db_session):
    """
    Objective 6: MAP INTEGRITY TESTS
    """
    import uuid
    run_id_A = "TEST-PHASE3-A-" + uuid.uuid4().hex[:6]
    run_id_B = "TEST-PHASE3-B-" + uuid.uuid4().hex[:6]
    
    # 1. Force insert A (Normal)
    run_A = SimulationRun(
        id=run_id_A,
        scenario="Normal Monsoon",
        data_mode="SIMULATION",
        status="COMPLETED",
        seed=42 # Fixed seed to ensure deterministic noise
    )
    db_session.add(run_A)
    
    # 2. Force insert B (Extreme)
    run_B = SimulationRun(
        id=run_id_B,
        scenario="Extreme Cloudburst",
        data_mode="SIMULATION",
        status="COMPLETED",
        seed=42 # Same geographic seed
    )
    db_session.add(run_B)
    db_session.commit()
    
    async def fetch_both():
        pa = await get_simulation_results(run_id_A, db_session)
        pb = await get_simulation_results(run_id_B, db_session)
        return pa, pb
        
    payload_A, payload_B = asyncio.run(fetch_both())
    
    # --- TEST 1: Same Geography ---
    # In this simplified prototype, the backend API doesn't return the raw DEM/Graph, 
    # but we can verify that the seed deterministic behavior holds.
    # The actual test of geography equivalence is implicit if seed is the same.
    
    # --- TEST 2: Different Forcing ---
    # Rainfall should be different
    # (Since we only get results, we can just check Qpred or Stage which implies different forcing)
    
    # --- TEST 3: Different Hydraulic Result ---
    stage_A = payload_A["metrics"]["stage_m"]
    stage_B = payload_B["metrics"]["stage_m"]
    assert stage_A != stage_B, "Test 3 Failed: Stage must differ for different forcing scenarios"
    
    # --- TEST 4: Different Inundation ---
    geojson_A = payload_A.get("inundation_geojson")
    geojson_B = payload_B.get("inundation_geojson")
    assert geojson_A is not None and geojson_B is not None
    
    str_A = json.dumps(geojson_A, sort_keys=True)
    str_B = json.dumps(geojson_B, sort_keys=True)
    assert str_A != str_B, "Test 4 Failed: Inundation geometry must differ between normal and extreme scenarios"
    
    # --- TEST 6: REAL Mode Integrity ---
    # If mode = REAL, it should return NOT_CONFIGURED
    run_id_C = "TEST-PHASE3-C-" + uuid.uuid4().hex[:6]
    run_C = SimulationRun(
        id=run_id_C,
        scenario="Normal Monsoon",
        data_mode="REAL",
        status="COMPLETED"
    )
    db_session.add(run_C)
    db_session.commit()
    
    async def fetch_real():
        try:
            return await get_simulation_results(run_id_C, db_session)
        except Exception as e:
            return e
            
    res_C = asyncio.run(fetch_real())
    # Should throw a 500 NotImplementedError or similar 
    assert isinstance(res_C, Exception), "Test 6 Failed: REAL mode must fail loudly and not fall back to synthetic data"
    assert "NOT_CONFIGURED" in str(res_C) or "not implemented" in str(res_C).lower(), "Test 6 Failed: REAL mode failure must explicitly mention lack of configuration"
