# Real Mode Operation

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
