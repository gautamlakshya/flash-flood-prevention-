# Repair Audit

## Backend Ingestion
* Current implementation: Returns hardcoded simulated data (e.g., rainfall amounts).
* Functional / Partial / Placeholder / Missing: Placeholder
* Where it is implemented: `backend/app/ingestion/simulator.py`
* What needs to change: Build a true synthetic scenario generator that outputs actual rainfall and spatial time series based on a scenario seed. Implement abstract interfaces for external APIs so they can be switched to real connections.

## DEM Processing
* Current implementation: `dem.py` returns zeros for flow direction and 100 for accumulation.
* Functional / Partial / Placeholder / Missing: Placeholder
* Where it is implemented: `backend/app/geospatial/dem.py`
* What needs to change: Process a real (or coherent synthetic) DEM grid using geospatial tools to derive actual slope, valid flow direction, and connected river segments.

## Hydrology (Curve Number & Runoff)
* Current implementation: Basic formulas implemented, but returns single scalar values instead of a time series.
* Functional / Partial / Placeholder / Missing: Partial
* Where it is implemented: `backend/app/hydrology/curve_number.py`, `backend/app/hydrology/runoff.py`
* What needs to change: Runoff depth must be calculated per time step using P(t) over an entire simulated event.

## Routing / River Graph
* Current implementation: Fully-connected dense graphs generated arbitrarily.
* Functional / Partial / Placeholder / Missing: Placeholder
* Where it is implemented: `ml/training/train.py`, `backend/app/routing`
* What needs to change: The graph must be built from the DEM flow network and must represent actual directed downstream river topology.

## ST-GNN Model & Training
* Current implementation: Random targets `y_true = torch.randn()`. Dummy loss.
* Functional / Partial / Placeholder / Missing: Placeholder
* Where it is implemented: `ml/models/stgnn.py`, `ml/training/train.py`
* What needs to change: Implement temporal sequence processing properly (e.g., sequences of length 12). Train on a generated synthetic dataset. Export the actually trained model to ONNX.

## PINN Constraints
* Current implementation: `dummy_residual = np.random.randn(...)`
* Functional / Partial / Placeholder / Missing: Placeholder
* Where it is implemented: `backend/app/routing/saint_venant.py`, `ml/training/train.py`
* What needs to change: Implement the true finite-difference calculation of the mass continuity equation: dA/dt + dQ/dx - qlat = 0 based on model outputs, and backpropagate through it.

## API Simulation Endpoint
* Current implementation: Waits with `setTimeout()` and returns hardcoded progress strings.
* Functional / Partial / Placeholder / Missing: Placeholder
* Where it is implemented: `backend/app/api/routes/` and `frontend/src/App.tsx`
* What needs to change: Create a real `POST /simulation/start` endpoint that creates a `run_id` and actually runs the Python pipeline asynchronously, returning real intermediate statuses.

## Frontend UI Data Binding
* Current implementation: Hardcoded `Q = 1080` if `demoMode == true`.
* Functional / Partial / Placeholder / Missing: Placeholder
* Where it is implemented: `frontend/src/App.tsx`
* What needs to change: The UI must fetch the backend predictions and display them dynamically.

## Inundation Mapping
* Current implementation: Hardcoded geojson polygon in MapLibre.
* Functional / Partial / Placeholder / Missing: Placeholder
* Where it is implemented: `frontend/src/map/FloodMap.tsx`
* What needs to change: Backend must produce GeoJSON representing the flood extent based on modeled water surface elevation over terrain. Frontend must render this dynamic GeoJSON.
