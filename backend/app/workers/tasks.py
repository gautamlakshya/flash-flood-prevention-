import asyncio
from datetime import datetime
from ..models.database import SessionLocal, SimulationRun
from ..ingestion.simulator import SyntheticDataGenerator
from ..geospatial.dem import process_dem
from ..hydrology.runoff import process_runoff_timeseries
from ..routing.saint_venant import generate_synthetic_river_graph
from ..hazards.classifier import classify_hazard
from ..hydraulics.manning import calculate_water_stage
from ..alerts.cap import generate_cap_xml

# For ML we import the required things once we have the ONNX or Torch fallback
# We will do Torch fallback for now since ONNX requires export

async def run_simulation_pipeline(run_id: str, scenario: str, seed: int):
    """
    Executes the end-to-end flash flood prediction pipeline.
    """
    db = SessionLocal()
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run:
        db.close()
        return

    def update_status(status_str):
        print(f"[{run_id}] {status_str}")
        run.status = status_str
        db.commit()

    try:
        update_status("DATA_INGESTION")
        await asyncio.sleep(0.5) # Simulate slight delay for UI observability
        
        sim = SyntheticDataGenerator(seed)
        start_time = datetime.utcnow()
        rainfall_data = sim.generate_rainfall(scenario, start_time)
        
        update_status("TERRAIN_PROCESSING")
        await asyncio.sleep(0.5)
        dem_data = process_dem() # synthetic valley
        
        update_status("HYDROLOGY")
        await asyncio.sleep(0.5)
        amc = sim.get_amc_condition(scenario)
        # We assume a fixed slope of 5.0 deg and cn2 of 75 for the whole catchment for simplicity
        cn2 = 75.0
        slope_deg = 5.0
        catchment_area = 50.0 # km2
        
        runoff_timeseries = process_runoff_timeseries(rainfall_data, cn2, slope_deg, amc, catchment_area)
        
        update_status("RIVER_ROUTING")
        await asyncio.sleep(0.5)
        nodes, edges, adj = generate_synthetic_river_graph()
        
        update_status("ML_INFERENCE")
        await asyncio.sleep(0.5)
        
        # Build features for ST-GNN prediction
        # For prototype simplicity, we will calculate the final predicted Q directly 
        # using our fallback logic if the torch model isn't loaded yet.
        # Let's say Qpred is based on the peak runoff volume mapped to a discharge rate over 1 hour
        peak_runoff_m3 = max(obs["runoff_volume_m3"] for obs in runoff_timeseries)
        
        # Simplified routing: 1 hour = 3600 seconds. peak_discharge ~ volume / time
        base_discharge = 100.0
        predicted_peak_discharge = base_discharge + (peak_runoff_m3 / 3600.0)
        
        update_status("HYDRAULICS")
        await asyncio.sleep(0.5)
        # Calculate for the most vulnerable node (the outlet)
        outlet_node = nodes[-1]
        manning_n = outlet_node["manning_n"]
        slope = outlet_node["slope"]
        width = 20.0 # simple rectangular channel assumption
        
        stage = calculate_water_stage(predicted_peak_discharge, manning_n, slope, width)
        
        update_status("HAZARD_CLASSIFICATION")
        await asyncio.sleep(0.5)
        q_crit = outlet_node["bankfull_capacity"]
        # Dummy dQdt, assuming it's rising because it's the peak
        dq_dt = 1.0 
        hazard_level = classify_hazard(predicted_peak_discharge, q_crit, dq_dt)
        
        update_status("INUNDATION")
        await asyncio.sleep(0.5)
        # Create a simplified GeoJSON for the inundation (this is just for task progression, actual comes from results endpoint)
        if hazard_level == "FLASH FLOOD WARNING":
            inundation_geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [88.64, 27.60],
                            [88.65, 27.60],
                            [88.65, 27.61],
                            [88.64, 27.61],
                            [88.64, 27.60]
                        ]]
                    },
                    "properties": {
                        "hazard": hazard_level,
                        "stage_m": round(stage, 2)
                    }
                }]
            }
        else:
            inundation_geojson = {"type": "FeatureCollection", "features": []}
            
        update_status("ALERT_GENERATION")
        await asyncio.sleep(0.5)
        if hazard_level == "FLASH FLOOD WARNING":
            cap_xml = generate_cap_xml(
                identifier=run_id,
                sender="FFEWS-DEMO",
                event="Flash Flood Warning",
                urgency="Immediate",
                severity="Extreme",
                certainty="Observed",
                headline="Flash Flood Warning for Chungthang Basin",
                description=f"Predicted peak discharge {predicted_peak_discharge:.1f} m3/s exceeds critical capacity {q_crit:.1f} m3/s.",
                instruction="Evacuate immediately to higher ground.",
                polygon_coordinates="27.60,88.64 27.60,88.65 27.61,88.65 27.61,88.64 27.60,88.64",
                area_desc="Chungthang Basin"
            )
        else:
            cap_xml = ""

        # Store all results back into the run entity (would typically go to specific tables)
        # For now, just completing the task
        update_status("COMPLETED")
        run.completed_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        print(f"Error in simulation {run_id}: {e}")
        update_status("FAILED")
    finally:
        db.close()
