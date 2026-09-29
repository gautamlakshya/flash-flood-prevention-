from fastapi import FastAPI
import os
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import health, rainfall, terrain, runoff, prediction, hazards, inundation, alerts, observations

app = FastAPI(
    title="Flash Flood Early Warning System API",
    description="Backend API for the SIH 2026 Flash Flood Warning System",
    version="1.0.0"
)

# CORS configuration
origins = os.environ.get("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router, tags=["Health"])
app.include_router(rainfall.router, prefix="/api/v1/rainfall", tags=["Rainfall"])
app.include_router(terrain.router, prefix="/api/v1/terrain", tags=["Terrain"])
app.include_router(runoff.router, prefix="/api/v1/runoff", tags=["Hydrology"])
app.include_router(prediction.router, prefix="/api/v1/predictions", tags=["Predictions"])
app.include_router(hazards.router, prefix="/api/v1/hazards", tags=["Hazards"])
app.include_router(inundation.router, prefix="/api/v1/inundation", tags=["Inundation"])
app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["Alerts"])
app.include_router(observations.router, prefix="/api/v1/observations", tags=["Field Operations"])

from .api.routes import simulation, data_sources
app.include_router(simulation.router, prefix="/api/v1/simulation", tags=["Simulation"])
app.include_router(data_sources.router, prefix="/api/v1/data_sources", tags=["Data Sources"])
