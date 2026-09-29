# Flash Flood Early Warning System (FFEWS) - NER

Smart India Hackathon 2026 - Problem Statement ID: 26192
Flash Flood Prediction System for Hilly Regions Using Multi-Source Data.

## Overview

This project is an end-to-end AI-powered platform for flash flood early warning, specifically designed for the vulnerable mountainous basins of India's North Eastern Region (NER).

It implements a physics-guided machine learning pipeline combining:
- Geospatial processing (DEM, Slope, River Networks)
- Multi-source data ingestion (Sentinel-1 SAR, INSAT-3DR, DWR, IMD AWS)
- Slope-adjusted SCS-CN hydrology
- Spatio-Temporal Graph Neural Networks (ST-GNN) & GRU
- Physics-Informed Neural Network (PINN) constraints (Saint-Venant mass continuity)
- Manning's equation for hydraulic stage and inundation
- CAP v1.2 Alert generation
- Offline-first Progressive Web App (PWA) with MapLibre visualizations.

## Architecture

1. **Ingestion Layer:** Connects to satellite and weather APIs (with mock fallback for demo mode).
2. **Hydrology Layer:** Computes antecedent moisture condition (AMC) and slope-adjusted runoff.
3. **ML Routing Layer:** Routes runoff through a river DAG using PyTorch ST-GNN models, exported to ONNX for fast inference.
4. **Hazard & Alerting Layer:** Classifies hazard levels against bankfull capacities and generates standard CAP XML alerts.
5. **Frontend Application:** React-based PWA dashboard.

## Running Locally

1. Setup environment:
   ```bash
   cp .env.example .env
   ```
2. Start all services using Docker Compose:
   ```bash
   make build
   make up
   ```
3. Access the dashboard at `http://localhost:3000`.

## Simulation Mode (Demo)

For demonstration purposes, if real APIs are unavailable:
- Click **Start Simulation** on the dashboard.
- This triggers a `CLOUDBURST` scenario generating mock rainfall data.
- The pipeline processes the rainfall, increases river discharge predictions, triggers a `FLASH FLOOD WARNING`, and updates the inundation map and CAP alerts.

## Repository Structure
- `backend/`: FastAPI server, Celery workers, ML inference, Hydrology algorithms.
- `ml/`: PyTorch models, Training pipeline, ONNX export scripts.
- `frontend/`: React + Vite PWA Dashboard.

## Model Details
The underlying AI model is a Spatio-Temporal Graph Neural Network (ST-GNN) that learns the river topology using GCN layers and temporal dynamics using GRU. It is constrained during training by a physics loss based on the 1D Saint-Venant mass continuity equation.
