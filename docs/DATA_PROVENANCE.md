# Data Provenance & Scaling Audit

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
