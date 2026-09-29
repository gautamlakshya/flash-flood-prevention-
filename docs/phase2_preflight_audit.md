# Phase 2 Preflight Audit

This document answers the preflight audit questions required before modifying the core model for Phase 2 (Real Data Validation).

### 1. Which provider classes actually retrieve/read real data?
- `LocalCartoDEMProvider`: Reads actual GeoTIFF files using rasterio (if present).
- `GSILandslideProvider`: Reads real GSI GeoJSON files (if present).
- `IMDAWSProvider`: Currently makes a mock HTTP request that is structured to parse real IMD responses, assuming real credentials exist.
- `LocalSentinel1Provider`: Reads real Sentinel-1 raster files using rasterio.
- `LocalCWCHydrologyProvider`: Reads real pandas CSV data.

### 2. Which providers are only interfaces/placeholders?
- `DataProvider`: Abstract base class.
- The `fetch_data` method inside `IMDAWSProvider` currently parses mock fields expecting an IMD-like JSON structure; it requires the actual IMD parameters to be truly operational.
- The datasets themselves (e.g., `cartodem.tif`, `cwc_discharge.csv`) are currently placeholders and are missing from the `data/` directory, causing these classes to return their error states.

### 3. Which providers currently return synthetic data?
- `SyntheticDEMProvider`: Calls `process_dem()` which returns a mathematically generated V-valley grid.
- `SyntheticDataGenerator`: Generates synthetic rainfall time series and random AMC conditions.

### 4. Which database tables are populated?
- `simulation_runs`: 32 rows

### 5. Which database tables are currently empty?
- `watersheds`, `river_nodes`, `river_edges`, `rainfall_observations`, `predictions`, `hazard_status`, `alerts`, `field_observations`.
- The new tables added during Phase 1 (`data_sources`, `raw_observations`, `hydrology_observations`, `dem_metadata`, `soil_moisture`, `landslide_inventory`) have not yet been migrated into the SQLite database.

### 6. Where is synthetic data still generated?
- `backend/app/ingestion/simulator.py`: `SyntheticDataGenerator` (Rainfall, AMC).
- `backend/app/geospatial/dem.py`: `process_dem()` (Terrain).
- `backend/app/routing/saint_venant.py`: `generate_synthetic_river_graph()` (Nodes, Edges, Adjacency, Channel characteristics).

### 7. Where is synthetic data still allowed to enter REAL mode?
- In `backend/app/api/routes/simulation.py`, while `data_mode == "REAL"` correctly invokes real inference features (and faults correctly because it's not implemented yet), the **inundation module** unconditionally calls `process_dem()` (the synthetic DEM generator) to render GeoJSON polygons regardless of `data_mode`.
- The `generate_synthetic_river_graph()` is also technically allowed to be called if `get_active_river_graph(use_synthetic=use_synthetic)` falls back incorrectly.

### 8. Where is the ST-GNN checkpoint loaded?
- `backend/app/api/routes/simulation.py` at line 146: `model_path = "ml/checkpoints/stgnn_model.pth"`.

### 9. What exact tensor reaches the ST-GNN?
- Tensor `X` of shape `(1, 12, 5, 4)`:
  - 1 batch
  - 12 timesteps (sequence length)
  - 5 river nodes
  - 4 features:
    - [0] Rainfall (scaled)
    - [1] Runoff Q (scaled)
    - [2] Current Q (kinematic wave approximated, scaled)
    - [3] Slope (raw)

### 10. What exact tensor/output becomes Qpred?
- `y_pred` has shape `(1, 5, 1)`. 
- `predicted_peak_discharge = float(y_pred[0, 4, 0].item()) * 1000.0` (Index 4 is the outlet node).

### 11. What scaling/normalization is applied to:
- **rainfall:** Raw `rainfall_mm` / 100.0
- **runoff:** Runoff volume converted to `runoff_q` (m3/s) then scaled by `/ 1000.0`
- **discharge:** `current_Q` (m3/s) / 1000.0. The output `y_pred` is inversely scaled by `* 1000.0`.
- **slope:** Raw value, no scaling.

### 12. What exact dataset is used for ST-GNN training?
- `ml/training/train.py` creates a purely synthetic dataset of 200 samples by iterating over random scenario generation (Normal, Heavy, Extreme, Monsoon) using `SyntheticDataGenerator`.

### 13. What is the prediction target?
- `Y[i, n, 0] = target_Q / 1000.0`
- `target_Q` is generated algebraically: `runoff_next_q + 0.8 * prev_Q + 0.5 * upstream_Q`

### 14. What is the temporal resolution?
- 15 minutes (`duration_hours = seq_len * 0.25`)

### 15. What is the prediction horizon?
- 1 timestep (15 minutes).

### 16. What is the spatial graph?
- 5 synthetically generated nodes.

### 17. What are the graph nodes?
- Synthetic points representing a linear cascade of catchments. Attributes include latitude, longitude, elevation, slope, bankfull_capacity, manning_n, width, etc.

### 18. What are the graph edges?
- Simple linear directed edges: Node 0 -> Node 1 -> Node 2 -> Node 3 -> Node 4.

### 19. What are the observed target values?
- Currently, NO actual observed target values are used. The training script (`train.py`) invents the targets mathematically.

### 20. Are train/validation/test splits chronological?
- **No.** `train.py` generates 200 random scenarios independently and simply slices `X[:train_size]` (80/20 split), which means there is no true chronological time series split.

### 21. Is there any temporal leakage?
- Because the 200 samples are generated as independent "events" rather than a continuous chronological timeline, there isn't strict temporal leakage between samples. However, in a real-world continuous time series, using an 80/20 random split would cause severe temporal leakage.

### 22. Is the dashboard displaying real observations or simulation values?
- The dashboard is currently displaying simulated values triggered by `/api/v1/simulation/start`, labeled by the system state.
