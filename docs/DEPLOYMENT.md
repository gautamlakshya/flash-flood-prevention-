# Deployment Guidelines

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
