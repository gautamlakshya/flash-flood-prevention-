import uuid
import asyncio
import os
import sys
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import numpy as np

import rasterio.features
from rasterio.transform import from_origin
from shapely.geometry import shape

from ...models.database import SessionLocal, SimulationRun
from ...workers.tasks import run_simulation_pipeline

router = APIRouter()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def find_file(relative_paths):
    for rel in relative_paths:
        if os.path.exists(rel):
            return rel
        abs_p = os.path.join(PROJECT_ROOT, rel.lstrip("/\\"))
        if os.path.exists(abs_p):
            return abs_p
    return None

def load_study_area_config():
    import yaml
    config_path = find_file(["config/study_area.yaml", "../config/study_area.yaml"])
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {
        "study_area": {"name": "Chungthang", "district": "Mangan District", "state": "Sikkim"},
        "target": {
            "name": "CWC Chungthang Station",
            "target_coordinates": [88.6475, 27.6033],
            "cwc_reference_coordinate": [88.6475, 27.5833],
            "dem_snapped_outlet_coordinate": [88.6551, 27.5851],
            "dem_catchment_area_km2": 2969.41
        }
    }

def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))

def numpy_stgnn_forward(x: np.ndarray, adj: np.ndarray, weights_path: str) -> np.ndarray:
    w = np.load(weights_path)
    batch_size, seq_len, num_nodes, num_features = x.shape

    # 1. GCN1: linear(4 -> 16), matmul(adj, out), relu
    x_reshaped = x.reshape(batch_size * seq_len, num_nodes, num_features)
    h1 = x_reshaped @ w['gcn1.linear.weight'].T + w['gcn1.linear.bias']
    h1 = adj @ h1
    h1 = np.maximum(0, h1)

    # 2. GCN2: linear(16 -> 16), matmul(adj, out), relu
    h2 = h1 @ w['gcn2.linear.weight'].T + w['gcn2.linear.bias']
    h2 = adj @ h2
    h2 = np.maximum(0, h2)

    # 3. Reshape for GRU: (batch_size * num_nodes, seq_len, hidden_dim)
    h2 = h2.reshape(batch_size, seq_len, num_nodes, 16)
    h_gru_in = np.transpose(h2, (0, 2, 1, 3)).reshape(-1, seq_len, 16)

    # 4. GRU over sequence
    W_ih, W_hh = w['gru.weight_ih_l0'], w['gru.weight_hh_l0']
    b_ih, b_hh = w['gru.bias_ih_l0'], w['gru.bias_hh_l0']

    N = h_gru_in.shape[0]
    hidden = np.zeros((N, 16), dtype=np.float32)

    for t in range(seq_len):
        x_t = h_gru_in[:, t, :]
        gi = x_t @ W_ih.T + b_ih
        gh = hidden @ W_hh.T + b_hh

        i_r, i_z, i_n = np.split(gi, 3, axis=1)
        h_r, h_z, h_n = np.split(gh, 3, axis=1)

        reset_gate = sigmoid(i_r + h_r)
        update_gate = sigmoid(i_z + h_z)
        new_gate = np.tanh(i_n + reset_gate * h_n)

        hidden = (1 - update_gate) * new_gate + update_gate * hidden

    # 5. Linear head: (N, 16) -> (N, 1)
    pred = hidden @ w['linear.weight'].T + w['linear.bias']

    # 6. Physical Skip Connection: add q_last (feature index 2 of last timestep)
    q_last = x[:, -1, :, 2].reshape(-1, 1)
    pred = pred + q_last

    return pred.reshape(batch_size, num_nodes, 1)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/map-config")
async def get_map_config():
    study_config = load_study_area_config()
    target = study_config.get("target", {})
    center = (
        target.get("target_coordinates")
        or target.get("cwc_reference_coordinate")
        or target.get("dem_snapped_outlet_coordinate")
        or [88.6475, 27.6033]
    )

    return {
        "status": "CONFIGURED",
        "ready": True,
        "study_area": study_config.get("study_area", {}).get("name", "Chungthang"),
        "target": target,
        "default_center": [float(center[0]), float(center[1])],
        "default_zoom": 11,
        "mode": "SIMULATION",
        "layers": [
            {"id": "inundation", "type": "geojson", "status": "READY"},
            {"id": "rivers", "type": "geojson", "status": "READY"}
        ],
        "provenance": {
            "dem": "Synthetic V-Valley (Centered at Chungthang)",
            "hydrology": "Slope-adjusted SCS-CN",
            "rainfall": "Synthetic IMD AWS Cloudburst",
            "model": "ST-GNN-v1.0 (GCN + GRU + Kinematic Skip)"
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
    db.expire_all()
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
    db.expire_all()
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
    from ...geospatial.dem import process_dem
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
        pass

    # Load model and infer (Hybrid PyTorch / Pure NumPy Engine)
    y_pred = None
    model_provenance_label = "ST-GNN-v1.0"

    # Try PyTorch if installed
    try:
        import torch
        from ml.models.stgnn import STGNN
        model = STGNN(num_nodes=num_nodes, num_features=4, hidden_dim=16, horizon=1)
        model_path = find_file(["ml/checkpoints/stgnn_model.pth", "../ml/checkpoints/stgnn_model.pth"]) if use_synthetic else find_file(["ml/checkpoints/stgnn_real_Teesta_v1.pth", "../ml/checkpoints/stgnn_real_Teesta_v1.pth"])
        if model_path and os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path, weights_only=True))
        model.eval()
        with torch.no_grad():
            X_tensor = torch.tensor(X, dtype=torch.float32)
            adj_tensor = torch.tensor(adj, dtype=torch.float32)
            y_pred_torch = model(X_tensor, adj_tensor)
            y_pred = y_pred_torch.detach().cpu().numpy()
            model_provenance_label = "stgnn_model.pth (PyTorch Engine)" if use_synthetic else "stgnn_real_Teesta_v1.pth"
    except Exception:
        # Fallback to pure NumPy ST-GNN runner with bundled weights (exact match, zero heavyweight dependencies)
        weights_path = find_file(["ml/checkpoints/stgnn_weights.npz", "../ml/checkpoints/stgnn_weights.npz"])
        if weights_path and os.path.exists(weights_path) and use_synthetic:
            try:
                y_pred = numpy_stgnn_forward(X, adj, weights_path)
                model_provenance_label = "stgnn_model.pth (NumPy Engine)"
            except Exception:
                y_pred = None

        if y_pred is None:
            # Kinematic physical routing fallback
            y_pred = np.zeros((1, num_nodes, 1), dtype=np.float32)
            for n in range(num_nodes):
                peak_runoff = max(obs["runoff_volume_m3"] for obs in node_runoff[n])
                y_pred[0, n, 0] = (100.0 + (peak_runoff / 3600.0)) / 1000.0
            model_provenance_label = "Kinematic Saint-Venant Fallback"

    study_config = load_study_area_config()

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
        raw_val = float(y_pred[0, outlet_idx, 0].item() if hasattr(y_pred[0, outlet_idx, 0], 'item') else y_pred[0, outlet_idx, 0])
        predicted_peak_discharge = raw_val * 1000.0
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
            "dem": "Synthetic V-Valley (Centered at Chungthang)" if use_synthetic else "CartoDEM",
            "model": model_provenance_label
        }
    }
