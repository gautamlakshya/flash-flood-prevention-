import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from ..config import settings

# Use SQLite for local execution without Docker if postgres URL fails
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql") and os.environ.get("USE_SQLITE", "true") == "true":
    db_url = "sqlite:///./flashflood.db"

# create_engine args for sqlite
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
engine = create_engine(db_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id = Column(String, primary_key=True, index=True)
    scenario = Column(String)
    seed = Column(Integer)
    status = Column(String, default="QUEUED")
    data_mode = Column(String)
    model_version = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class Watershed(Base):
    __tablename__ = "watersheds"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    area_km2 = Column(Float)
    nodes = relationship("RiverNode", back_populates="watershed")

class RiverNode(Base):
    __tablename__ = "river_nodes"
    id = Column(String, primary_key=True, index=True)
    watershed_id = Column(String, ForeignKey("watersheds.id"))
    name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    elevation = Column(Float)
    slope = Column(Float)
    bankfull_capacity = Column(Float)
    manning_n = Column(Float)
    cross_section_area = Column(Float)
    
    watershed = relationship("Watershed", back_populates="nodes")
    # For simplicity, we just store features

class RiverEdge(Base):
    __tablename__ = "river_edges"
    id = Column(Integer, primary_key=True, index=True)
    upstream_node_id = Column(String, ForeignKey("river_nodes.id"))
    downstream_node_id = Column(String, ForeignKey("river_nodes.id"))
    length_m = Column(Float)
    slope = Column(Float)

class DataSource(Base):
    __tablename__ = "data_sources"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    source_type = Column(String) # DEM, IMD, CWC, SENTINEL, GSI
    status = Column(String) # CONNECTED, AVAILABLE LOCALLY, SIMULATED, NOT CONFIGURED
    official_url = Column(String)
    last_updated = Column(DateTime)
    metadata_json = Column(JSON)

class RawObservation(Base):
    __tablename__ = "raw_observations"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String, ForeignKey("data_sources.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    location_id = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    value_type = Column(String) # RAINFALL, DISCHARGE, STAGE
    value = Column(Float)
    units = Column(String)
    quality_flag = Column(String)

class HydrologyObservation(Base):
    __tablename__ = "hydrology_observations"
    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    discharge_m3s = Column(Float)
    water_level_m = Column(Float)
    source = Column(String)
    quality_flag = Column(String)

class SoilMoisture(Base):
    __tablename__ = "soil_moisture"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    location_id = Column(String)
    sm_percent = Column(Float)
    amc_class = Column(Integer)
    source = Column(String)

class DEMMetadata(Base):
    __tablename__ = "dem_metadata"
    id = Column(String, primary_key=True, index=True)
    source = Column(String)
    crs = Column(String)
    resolution_m = Column(Float)
    bounds = Column(String)
    checksum = Column(String)
    ingested_at = Column(DateTime, default=datetime.utcnow)

class LandslideInventory(Base):
    __tablename__ = "landslide_inventory"
    id = Column(String, primary_key=True, index=True)
    source_id = Column(String)
    source = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    geometry = Column(String) # GeoJSON string
    occurrence_date = Column(DateTime, nullable=True)
    state = Column(String)
    district = Column(String)
    type = Column(String)

class RainfallObservation(Base):
    __tablename__ = "rainfall_observations"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String) # INSAT3DR, DWR, AWS
    timestamp = Column(DateTime, default=datetime.utcnow)
    latitude = Column(Float)
    longitude = Column(Float)
    rainfall_mm = Column(Float)
    quality = Column(Float)

class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String, ForeignKey("river_nodes.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    horizon_minutes = Column(Integer)
    predicted_discharge = Column(Float)
    model_version = Column(String)

class HazardStatus(Base):
    __tablename__ = "hazard_status"
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String, ForeignKey("river_nodes.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    current_discharge = Column(Float)
    predicted_discharge = Column(Float)
    capacity_utilization = Column(Float)
    trend = Column(String) # RISING, FALLING, STABLE
    status = Column(String) # NORMAL, WATCH, FLASH FLOOD WARNING

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    severity = Column(String)
    urgency = Column(String)
    certainty = Column(String)
    headline = Column(String)
    description = Column(String)
    affected_nodes = Column(JSON)
    xml_data = Column(String)

class FieldObservation(Base):
    __tablename__ = "field_observations"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    latitude = Column(Float)
    longitude = Column(Float)
    water_level_m = Column(Float)
    rainfall_mm = Column(Float)
    notes = Column(String)
    synced = Column(Boolean, default=False)

# Create tables
Base.metadata.create_all(bind=engine)
