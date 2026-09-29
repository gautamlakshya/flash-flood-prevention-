# Phase 2 Detailed Execution Plan: Real Data Validation (Gates 1-22)

This plan details the exact files, functions, inputs, outputs, validation tests, and execution strategies for Gates 1-22 to ensure a scientifically sound, data-driven real mode for the Flash Flood Early Warning System (FFEWS). The Teesta Basin is configured as the initial study area. 

## GATE 1 - Real Data Sources
- **Files Created/Modified:** `config/study_area.yaml`, `backend/app/ingestion/base.py`, `backend/app/ingestion/dem/provider.py`, `backend/app/ingestion/imd/provider.py`, `backend/app/ingestion/hydrology/provider.py`, `backend/app/ingestion/landslides/provider.py`
- **Implementation:** 
  - Create `study_area.yaml` defining Teesta basin BBOX, CRS (EPSG:4326/32645), and target temporal cadence.
  - Implement parsing for actual CartoDEM TIFFs via `rasterio` (checking CRS and nodata).
  - Implement CSV loading for CWC discharge data using `pandas`, retaining missing data (NaN) without arbitrary interpolation.
- **Validation Tests:** Provider initialization fails cleanly with `DATA_SOURCE_NOT_CONFIGURED` if actual data files for Teesta do not exist.
- **Affected Mode:** REAL.

## GATE 2 - Static Hydrologic Data
- **Files Created/Modified:** `backend/app/ingestion/static_data.py`
- **Implementation:**
  - Create an audit tool that checks the existence of real LULC, HSG (Soil), river channel geometry, and cross sections in `data/raw/static/`.
  - Set the state to `NOT_CONFIGURED` for any missing variable. 
- **Validation Tests:** Explicit checks returning `NOT_CONFIGURED` without generating synthetic channel width or LULC grids.
- **Affected Mode:** REAL.

## GATE 3 - Raw Data Storage
- **Files Created/Modified:** Directory structure `data/raw/*`, `data/processed/*`, `data/manifests/`
- **Implementation:** Script to generate a JSON manifest (`manifest_<dataset_id>.json`) calculating SHA256 checksums, temporal ranges (start/end), bbox, and variable units for all ingested files.
- **Validation Tests:** Ensure ingestion rejects files lacking a valid metadata manifest.
- **Affected Mode:** REAL.

## GATE 4 - Temporal Alignment
- **Files Created/Modified:** `backend/app/data_pipeline/builder.py`, `docs/temporal_resolution_report.md`
- **Implementation:**
  - Load rainfall, soil moisture, and discharge time series using pandas.
  - Report native frequencies using `.index.to_series().diff().value_counts()`.
  - Perform temporal alignment via left joins based on the coarsest overlapping cadence (e.g., hourly), without inventing higher frequency data via naive forward fill.
- **Validation Tests:** Check for duplicated timestamps and explicitly assert `DataFrame.index.is_unique`.
- **Affected Mode:** REAL.

## GATE 5 - Spatial Alignment
- **Files Created/Modified:** `backend/app/data_pipeline/spatial.py`, `docs/spatial_alignment_report.md`
- **Implementation:**
  - Reproject all spatial datasets to the CRS defined in `study_area.yaml` using `geopandas` and `rasterio`.
  - Map IMD stations and CWC gauges to graph nodes using nearest neighbor distance bounded by a specific catchment threshold.
- **Validation Tests:** CRS validation function that raises a `ValueError` if sources cannot be reprojected to the common datum.
- **Affected Mode:** REAL.

## GATE 6 - Real River Graph
- **Files Created/Modified:** `backend/app/data_pipeline/graph_builder.py`
- **Implementation:**
  - Extract DEM using `whitebox` or PySheds (if dependencies allow), or perform a documented vector network extraction from pre-existing flow line shapefiles.
  - Convert river segments into PyTorch Geometric format (`edge_index` and `edge_attr`), mapping CWC stations to nodes.
- **Validation Tests:** If DEM/Flow network is unavailable, fail graph construction with `NotImplementedError`, preventing fallback to the random 5-node synthetic graph.
- **Affected Mode:** REAL.

## GATE 7 - Training Dataset Compiler
- **Files Created/Modified:** `backend/app/data_pipeline/builder.py`, `docs/training_dataset_spec.md`
- **Implementation:**
  - Create strict sliding window generators mapping `X[t-N : t]` -> `Q[t+H]`.
  - Drop samples where targets (`Q[t+H]`) are NaN.
- **Validation Tests:** Ensure dataset dimensions are exactly `(num_samples, seq_len, num_nodes, num_features)`.
- **Affected Mode:** REAL.

## GATE 8 - Normalization / Scaling Audit
- **Files Created/Modified:** `backend/app/models/scalers.py`, `docs/scaling_audit.md`
- **Implementation:**
  - Replace the arbitrary `/1000.0` and `*1000.0` scaling.
  - Implement `scikit-learn` `StandardScaler` or `MinMaxScaler` for each feature column (Rainfall, Runoff, Discharge, Slope).
  - Save fitted scalers to `ml/checkpoints/scaler_Teesta_v1.json`.
  - Implement precise inverse transforms for model outputs.
- **Validation Tests:** Assert `inverse_transform(transform(X)) == approx(X)`.
- **Affected Mode:** BOTH (Real will use fitted scalers, Synthetic will maintain scaling clarity).

## GATE 9 - Chronological Split
- **Files Created/Modified:** `backend/app/models/train.py`, `docs/data_leakage_audit.md`
- **Implementation:**
  - Split dataset based on date indices (e.g., Train: 2018-2020, Val: 2021, Test: 2022).
  - Reject `train_test_split(shuffle=True)`.
- **Validation Tests:** Verify `max(train_dates) < min(val_dates) < min(test_dates)`.
- **Affected Mode:** REAL.

## GATE 10 - ST-GNN Training on Real Data
- **Files Created/Modified:** `backend/app/models/train.py`
- **Implementation:**
  - Execute training loop on the chronological real dataset using observed CWC targets.
  - Calculate actual NSE, MAE, and RMSE. Save `model_metadata_Teesta_v1.json`.
- **Validation Tests:** Training aborts if validation dataset is empty or NaN.
- **Affected Mode:** REAL.

## GATE 11 - Real ST-GNN Provenance Test
- **Files Created/Modified:** `tests/test_real_stgnn_provenance.py`
- **Implementation:**
  - Pytest module confirming that modifying one input feature in the real dataset explicitly alters the unscaled `Qpred`, and that Qpred is not bypassed algebraically.
- **Validation Tests:** Delta check on output > 0 when input is perturbed.
- **Affected Mode:** REAL.

## GATE 12 - Hydrological Consistency
- **Files Created/Modified:** `backend/app/hydrology/runoff.py`
- **Implementation:**
  - Differentiate `observed_rainfall` and `scs_cn_estimated_runoff`. Document how AMC is derived (either from soil moisture or preceding 5-day rainfall).
- **Validation Tests:** Traceable CN calculation logs.
- **Affected Mode:** BOTH.

## GATE 13 & 14 - Qcrit & dQ/dt
- **Files Created/Modified:** `backend/app/api/routes/simulation.py`, `backend/app/hazards/classifier.py`
- **Implementation:**
  - **Qcrit:** Remove `500 + i*100`. Fetch from real cross-sections or return `NOT_CONFIGURED`.
  - **dQ/dt:** Calculate via `(Qpred - Q[t-1])/dt` utilizing real time differences.
- **Validation Tests:** Hazard classifier correctly handles `Qcrit = None` gracefully.
- **Affected Mode:** REAL.

## GATE 15 - Real Inundation
- **Files Created/Modified:** `backend/app/api/routes/simulation.py`
- **Implementation:**
  - Calculate WSE (Water Surface Elevation).
  - Mask real CartoDEM with WSE. Polygonize using `rasterio.features.shapes`.
- **Validation Tests:** Ensure GeoJSON coordinates match CartoDEM CRS boundaries.
- **Affected Mode:** REAL.

## GATE 16 - Real vs Simulation Isolation
- **Files Created/Modified:** `backend/app/api/routes/simulation.py`
- **Implementation:**
  - Hard fault `HTTPException(500)` if a requested real asset is missing during `REAL` mode simulation, preventing silent fallback to `SyntheticDataGenerator`.
  - Return provenance dict in the API response.
- **Validation Tests:** Start simulation API test with empty real datasets to guarantee 500 Failure.
- **Affected Mode:** BOTH.

## GATE 17 - Data Source Dashboard
- **Files Created/Modified:** `backend/app/api/routes/data_sources.py`
- **Implementation:**
  - Ensure status logic explicitly checks database/disk for actual records, not just class instantiation.
- **Validation Tests:** Status shows `NOT_CONFIGURED` if `data/raw/` is empty.
- **Affected Mode:** BOTH.

## GATE 18 & 19 - Dashboard Validation & Demonstration
- **Files Created/Modified:** `docs/phase2_real_data_validation.md`, Frontend UI components
- **Implementation:**
  - Generate the markdown report reflecting all counts, dates, and metrics based on Teesta basin data (or lack thereof).
  - Ensure dashboard displays `NOT_CONFIGURED` labels clearly without faking values.

## GATE 20, 21, 22 - Testing, Claims & Final Acceptance
- **Files Created/Modified:** `tests/test_real_mode_failures.py`, `tests/test_temporal_alignment.py`, `tests/test_scaling.py`, `tests/test_dqdt.py`, `tests/test_inundation_provenance.py`
- **Implementation:** 
  - Comprehensive Pytest suite covering all 14 failure conditions outlined in Gate 20.
  - Review all frontend tooltip texts to remove unsubstantiated claims ("15-min operational prediction" -> "Simulated 15-min prediction").
  - Final end-to-end execution script verifying exact data paths.
- **Affected Mode:** REAL.
