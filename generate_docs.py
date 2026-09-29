import os

docs = {
    "REAL_MODE.md": """# Real Mode Operation

## Overview
REAL Mode strictly enforces a data-driven pipeline utilizing observed physical data. 
**Status: IMPLEMENTED, but NOT_CONFIGURED.**

## Rules of Engagement
- **Zero Fabrication:** The system explicitly refuses to simulate or forward-fill data if physical observations are missing.
- **Fail-Closed Architecture:** If CartoDEM, CWC Discharge, or IMD Rainfall files are absent for the configured study area (currently Teesta), the ST-GNN prediction pipeline aborts and throws `DATA_SOURCE_NOT_CONFIGURED`.
- **Synthetic Fallback Blocked:** The `SyntheticDataGenerator` and synthetic river graphs are entirely disabled under this mode.

## Data States
Components will reflect the following states explicitly:
- **CONNECTED:** Real data is physically present, validated, and aligned.
- **NOT_CONFIGURED:** The required files (e.g. `data/raw/dem/teesta_cartodem.tif`) are missing.
- **ERROR:** Files are present but corrupt, or spatial alignment (CRS mismatch) fails.
- **SIMULATION_ONLY:** Features like exact 15-minute operational telemetry, which do not currently exist in the Teesta dataset.
""",
    "DATA_PROVENANCE.md": """# Data Provenance & Scaling Audit

## Pipeline Provenance
- **Rainfall:** IMD AWS observations (`data/raw/rainfall/teesta_imd_precipitation.csv`).
- **Hydrology (Target Q):** CWC Historical Discharge (`data/raw/hydrology/teesta_cwc_discharge.csv`).
- **Terrain:** CartoDEM 30m GeoTIFF.
- **Status:** **NOT_CONFIGURED** (0 real observations physically present).

## Feature Normalization (Scaling Audit)
The arbitrary `*1000.0` or `/1000.0` manual scalers have been removed.

### Dimensional Transformation Pipeline
1. **Raw Source:** Streamflow (m³/s), Rainfall (mm/hr), Slope (dimensionless).
2. **Scaler:** `scikit-learn` fitted `MinMaxScaler` or `StandardScaler`.
3. **Training Tensor:** Normalized range `[0, 1]`.
4. **Prediction:** Normalized Qpred output `[0, 1]`.
5. **Inverse Transformation:** `inverse_transform(Qpred)` -> Restores the physical m³/s value.

### dQ/dt Calculation
Computed physically: `(predicted_Q_m3s - current_Q_m3s) / dt_seconds`.
""",
    "TRAINING_PROTOCOL.md": """# ST-GNN Training Protocol (Real Data)

## Real Training Constraints
- **Target Variable:** The model is trained exclusively to predict the actual CWC-observed discharge target (`y`), not an algebraic substitution.
- **Chronological Split:** The train, validation, and test datasets are split purely by chronological date (e.g., Train: 2018-2020, Val: 2021). Random shuffling (`train_test_split(shuffle=True)`) is strictly forbidden to prevent temporal data leakage.
- **Current Status:** **BLOCKED - REAL DATA REQUIRED**. The training module evaluates the `data/raw/` directory and aborts execution due to the absence of the Teesta hydrometeorological dataset.

## Metric Evaluation
Only the held-out Chronological Test Set is used to calculate:
- RMSE (Root Mean Squared Error)
- MAE (Mean Absolute Error)
- NSE (Nash-Sutcliffe Efficiency)
""",
    "MODEL_LIMITATIONS.md": """# Model Limitations

## Disclaimer: Model Accuracy & Predictability
- **Accuracy Unverified:** The system does NOT claim model accuracy at this stage because there is no held-out real test set to evaluate against.
- **15-Minute Operational Forecasting:** The system currently simulates a 15-minute cadence. True 15-minute forecasting is **UNVERIFIED** until IMD/CWC data matching that native temporal resolution is acquired and ingested.
- **Current Row Count:** `0 real observations`.
- **Operational Readiness:** NOT ready for operational deployment. The system requires extensive retrospective training on Indian historical flood events to determine ST-GNN's real-world Nash-Sutcliffe efficiency.
""",
    "DEPLOYMENT.md": """# Deployment Guidelines

## Current State
The backend and frontend are structurally complete and architected to support physical FFEWS logic.

## Prerequisites for Real Deployment
Before declaring this deployment "Operational", the following must be satisfied:
1. Physical CSV and GeoTIFF datasets must be placed in `data/raw/` reflecting the bounds defined in `config/study_area.yaml`.
2. The Database Migrations must be verified (completed).
3. The spatial and temporal alignment tests must pass on the actual physical data.
4. The ST-GNN model must successfully compile a chronologically split dataset.
5. The model must produce a `stgnn_real_Teesta_v1.pth` checkpoint with an NSE > 0.6 on the held-out test set.

**Deployment is currently conditionally accepted as a Prototype, pending real data acquisition.**
"""
}

os.makedirs("docs", exist_ok=True)
for filename, content in docs.items():
    with open(f"docs/{filename}", "w") as f:
        f.write(content)
