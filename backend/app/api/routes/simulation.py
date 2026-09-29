import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import numpy as np
import torch

import rasterio.features
from rasterio.transform import from_origin
from shapely.geometry import shape

from ...models.database import SessionLocal, SimulationRun
from ...workers.tasks import run_simulation_pipeline

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/map-config")
async def get_map_config():
    import yaml
    import os
    config_path = "config/study_area.yaml"
    if not os.path.exists(config_path):
        return {"status": "NOT_CONFIGURED", "reason": "study_area.yaml missing"}
    
    with open(config_path, "r") as f:
        study_config = yaml.safe_load(f)
        
    return {
        "status": "READY",
        "study_area": study_config.get("study_area", {}).get("name", "Unknown"),
        "target": study_config.get("target", {}),
        "default_center": study_config.get("target", {}).get("target_coordinates", [88.6475, 27.6033]),
        "default_zoom": 11,
        "mode": "SIMULATION",
        "layers": [
            {"id": "inundation", "type": "geojson", "status": "READY"}
        ],
        "provenance": {
            "dem": "Synthetic V-Valley",
            "hydrology": "Synthetic",
            "rainfall": "Synthetic",
            "model": "stgnn_model.pth"
        }
    }

@router.post("/start")
async def start_simulation(scenario: str = "Extreme Cloudburst", data_mode: str = "SIMULATION", db: Session = Depends(get_db)):
    """
    Start an end-to-end simulation.
    """
    run_id = f"DEMO-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    
    # Create run entity
    new_run = SimulationRun(
        id=run_id,
        scenario=scenario,
        seed=int(datetime.utcnow().timestamp()),
        status="QUEUED",
        data_mode=data_mode,
        model_version="ST-GNN-v1.0"
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    
    # We trigger the task in the background (using asyncio tasks since Celery might not be up locally)
    asyncio.create_task(run_simulation_pipeline(run_id, scenario, new_run.seed))
    
    return {"run_id": run_id, "status": "QUEUED"}

@router.get("/{run_id}/status")
async def get_simulation_status(run_id: str, db: Session = Depends(get_db)):
    """
    Get the status of a simulation.
    """
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    return {
        "run_id": run.id,
        "status": run.status,
        "scenario": run.scenario
    }

@router.get("/{run_id}/results")
async def get_simulation_results(run_id: str, db: Session = Depends(get_db)):
    """
    Get the full results of a COMPLETED simulation.
    Since we don't have separate tables fully populated yet, we'll return a calculated view.
    """
    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run or run.status != "COMPLETED":
        raise HTTPException(status_code=404, detail="Run not completed or not found")
    
    # We rebuild the simulation results deterministically from the seed to return them to the UI
    # In a full production app, these would be queried from the `predictions`, `hazard_status`, etc. tables
    from ...ingestion.simulator import SyntheticDataGenerator
    from ...hydrology.runoff import process_runoff_timeseries
    from ...routing.saint_venant import generate_synthetic_river_graph
    from ...hazards.classifier import classify_hazard
    from ...hydraulics.manning import calculate_water_stage
    from ...alerts.cap import generate_cap_xml
    from ml.models.stgnn import STGNN
    from ...geospatial.dem import process_dem
    import os
    
    from ...data_pipeline.graph_builder import get_active_river_graph
    
    use_synthetic = run.data_mode != "REAL"
    
    if not use_synthetic:
        # In real mode, we need real features
        try:
            from ...data_pipeline.builder import generate_features_for_inference
            X = generate_features_for_inference(run.id, run.created_at, run.scenario)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"REAL Data pipeline failed: {str(e)}")
            
    sim = SyntheticDataGenerator(run.seed)
    seq_len = 12
    duration_hours = seq_len * 0.25
    rainfall_data = sim.generate_rainfall(run.scenario, run.created_at, duration_hours=duration_hours)
    amc = sim.get_amc_condition(run.scenario)
    
    try:
        nodes, edges, adj = get_active_river_graph(use_synthetic=use_synthetic)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    num_nodes = len(nodes)
    
    # Runoff calculation (Gate 12)
    node_runoff = {}
    for n in range(num_nodes):
        cn2 = 75.0 + (n * 2.0)
        slope = nodes[n].get("slope", 0.01)
        area = 50.0 # km2
        node_runoff[n] = process_runoff_timeseries(rainfall_data, cn2, slope, amc, area)
        
    # Phase 1 & Gate 8: Inference with explicit scalers
    from ...models.scalers import STGNNScalerRegistry
    scaler_registry = STGNNScalerRegistry()
    
    # In a full implementation we load the fitted scalers here
    # scaler_registry.load(f"ml/checkpoints/scaler_{study_area}_v1.json")
    # For prototype, since it's unconfigured, we simulate the registry having default 0-1 values.
    
    X = np.zeros((1, seq_len, num_nodes, 4))
    if use_synthetic:
        for t in range(seq_len):
            for n in range(num_nodes):
                obs = node_runoff[n][t]
                rain_t = obs["rainfall_mm"]
                runoff_q = obs["runoff_volume_m3"] / 900.0
                
                if t == 0:
                    current_Q = runoff_q + 10.0
                else:
                    prev_Q = X[0, t-1, n, 2] * 1000.0 # Legacy fallback for simulated mode
                    upstream_Q = X[0, t, n-1, 2] * 1000.0 if n > 0 else 0.0
                    current_Q = runoff_q + 0.8 * prev_Q + 0.5 * upstream_Q
                    
                X[0, t, n, 0] = rain_t / 100.0
                X[0, t, n, 1] = runoff_q / 1000.0
                X[0, t, n, 2] = current_Q / 1000.0
                X[0, t, n, 3] = nodes[n].get("slope", 0.01)
    else:
        # REAL MODE: X was populated by generate_features_for_inference
        # Which currently safely throws 500 NotImplemented since data is missing
        pass
            
    # Load model and infer
    model = STGNN(num_nodes=num_nodes, num_features=4, hidden_dim=16, horizon=1)
    model_path = "ml/checkpoints/stgnn_model.pth" if use_synthetic else "ml/checkpoints/stgnn_real_Teesta_v1.pth"
    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path))
    model.eval()
    
    with torch.no_grad():
        X_tensor = torch.tensor(X, dtype=torch.float32)
        adj_tensor = torch.tensor(adj, dtype=torch.float32)
        y_pred = model(X_tensor, adj_tensor)
        
    # Objective 3: Make the target location a real system concept
    import yaml
    with open("config/study_area.yaml", "r") as f:
        study_config = yaml.safe_load(f)
    
    target_name = study_config.get("target", {}).get("name", "Unknown")
    
    if run.data_mode == "REAL":
        # In real mode, we must resolve the target_name to an actual graph node
        # Since we don't have a real river network dataset yet, this cannot be resolved.
        raise NotImplementedError("TARGET_NODE_NOT_CONFIGURED: Cannot resolve target location '" + target_name + "' to a physical river graph node.")
    else:
        # SIMULATION mode fallback
        outlet_idx = num_nodes - 1
    
    # Gate 8 Inverse Transform
    if use_synthetic:
        predicted_peak_discharge = float(y_pred[0, outlet_idx, 0].item()) * 1000.0
        last_Q = X[0, -1, outlet_idx, 2] * 1000.0
    else:
        # Real Mode uses fitted scaler
        predicted_norm = np.array([y_pred[0, outlet_idx, 0].item()])
        predicted_peak_discharge = float(scaler_registry.scalers["discharge"].inverse_transform(predicted_norm)[0])
        last_Q_norm = np.array([X[0, -1, outlet_idx, 2]])
        last_Q = float(scaler_registry.scalers["discharge"].inverse_transform(last_Q_norm)[0])
    
    # Gate 14: dQ/dt calculated physically
    dt_seconds = 3600.0 if not use_synthetic else 900.0
    dq_dt = (predicted_peak_discharge - last_Q) / dt_seconds
    
    # Gate 13: Qcrit Hydraulics
    outlet_node = nodes[outlet_idx]
    if use_synthetic:
        q_crit = outlet_node.get("bankfull_capacity", 900.0)
        manning_n = outlet_node.get("manning_n", 0.035)
        slope = outlet_node.get("slope", 0.01)
        width = outlet_node.get("width", 50.0)
        stage = calculate_water_stage(predicted_peak_discharge, manning_n, slope, width)
        hazard_level = classify_hazard(predicted_peak_discharge, q_crit, dq_dt)
    else:
        if "bankfull_capacity" not in outlet_node:
            q_crit = None
            stage = None
            hazard_level = "NOT_CONFIGURED"
        else:
            q_crit = outlet_node["bankfull_capacity"]
            manning_n = outlet_node["manning_n"]
            slope = outlet_node["slope"]
            width = outlet_node["width"]
            stage = calculate_water_stage(predicted_peak_discharge, manning_n, slope, width)
            hazard_level = classify_hazard(predicted_peak_discharge, q_crit, dq_dt)
    
    # CAP Generation moved after GeoJSON generation
    
    # Gate 15: Real Inundation
    flooded_cells = 0
    inundation_features = []
    
    if use_synthetic:
        dem_data = process_dem()
        dem_grid = dem_data["elevation"]
        rows, cols = dem_grid.shape
        outlet_r, outlet_c = rows - 1, cols // 2
        reference_elevation = dem_grid[outlet_r, outlet_c]
        water_surface_elevation = reference_elevation + stage
        flooded_mask = (dem_grid < water_surface_elevation).astype('uint8')
        from ...geospatial.dem import get_simulation_spatial_transform
        transform = get_simulation_spatial_transform()
        shapes = list(rasterio.features.shapes(flooded_mask, transform=transform))
        
        for geom, value in shapes:
            if value == 1:
                inundation_features.append({
                    "type": "Feature",
                    "geometry": shape(geom).__geo_interface__,
                    "properties": {"hazard": hazard_level, "stage_m": round(stage, 2)}
                })
        flooded_cells = int(np.sum(flooded_mask))
    else:
        # Real DEM
        dem_path = "data/raw/dem/teesta_cartodem.tif"
        if not os.path.exists(dem_path):
            # NO_DATA fallback for inundation in real mode
            pass
        else:
            with rasterio.open(dem_path) as src:
                dem_grid = src.read(1)
                nodata = src.nodata
                
                # Assume reference elevation is known from node
                reference_elevation = outlet_node.get("elevation", 0)
                if stage is not None:
                    water_surface_elevation = reference_elevation + stage
                    valid_mask = dem_grid != nodata
                    flooded_mask = np.logical_and(valid_mask, dem_grid < water_surface_elevation).astype('uint8')
                    
                    shapes = list(rasterio.features.shapes(flooded_mask, transform=src.transform))
                    for geom, value in shapes:
                        if value == 1:
                            inundation_features.append({
                                "type": "Feature",
                                "geometry": shape(geom).__geo_interface__,
                                "properties": {"hazard": hazard_level, "stage_m": round(stage, 2)}
                            })
                    flooded_cells = int(np.sum(flooded_mask))

    inundation_geojson = {
        "type": "FeatureCollection",
        "features": inundation_features
    }
    
    cap_xml = ""
    if hazard_level == "FLASH FLOOD WARNING":
        polygon_str = ""
        all_coords = []
        for feat in inundation_features:
            geom = feat["geometry"]
            if geom["type"] == "Polygon":
                all_coords.extend(geom["coordinates"][0])
            elif geom["type"] == "MultiPolygon":
                for p in geom["coordinates"]:
                    all_coords.extend(p[0])
                    
        if all_coords:
            lons = [c[0] for c in all_coords]
            lats = [c[1] for c in all_coords]
            min_lon, min_lat = min(lons), min(lats)
            max_lon, max_lat = max(lons), max(lats)
            polygon_str = f"{min_lat},{min_lon} {min_lat},{max_lon} {max_lat},{max_lon} {max_lat},{min_lon} {min_lat},{min_lon}"
        else:
            polygon_str = "NOT_GENERATED"
            
        if polygon_str != "NOT_GENERATED":
            cap_xml = generate_cap_xml(
                identifier=run.id,
                sender="FFEWS",
                event="Flash Flood Warning",
                urgency="Immediate",
                severity="Extreme",
                certainty="Observed" if not use_synthetic else "Simulated",
                headline="Flash Flood Warning for Basin",
                description=f"Predicted peak discharge {predicted_peak_discharge:.1f} m3/s.",
                instruction="Evacuate immediately to higher ground.",
                polygon_coordinates=polygon_str,
                area_desc=f"{target_name} Basin"
            )
        else:
            cap_xml = "NOT_GENERATED"
    
    return {
        "run_id": run.id,
        "scenario": run.scenario,
        "data_mode": run.data_mode,
        "model_version": run.model_version,
        "metrics": {
            "predicted_discharge": round(predicted_peak_discharge, 1),
            "qcrit": round(q_crit, 1) if q_crit is not None else "NOT_CONFIGURED",
            "capacity_utilization": round((predicted_peak_discharge / q_crit) * 100, 1) if q_crit and q_crit > 0 else 0,
            "hazard": hazard_level,
            "stage_m": round(stage, 2) if stage is not None else "NOT_CONFIGURED",
            "peak_runoff_volume": round(max([obs["runoff_volume_m3"] for obs in node_runoff[0]]), 1) if node_runoff else 0,
            "cn": round(node_runoff[0][0]["cn"], 1) if node_runoff else 0,
            "s_mm": round(node_runoff[0][0]["s_mm"], 1) if node_runoff else 0,
            "amc": amc if use_synthetic else "OBSERVED",
            "dq_dt": round(dq_dt, 4),
            "flooded_cells": flooded_cells,
            "inundation_polygons": len(inundation_geojson["features"])
        },
        "timeseries": node_runoff[0] if node_runoff else [],
        "inundation_geojson": inundation_geojson,
        "cap_xml": cap_xml,
        "provenance": {
            "rainfall": "Synthetic" if use_synthetic else "IMD AWS",
            "hydrology": "Synthetic" if use_synthetic else "CWC Historical",
            "dem": "Synthetic V-Valley" if use_synthetic else "CartoDEM",
            "model": "stgnn_model.pth" if use_synthetic else "stgnn_real_Teesta_v1.pth"
        }
    }
