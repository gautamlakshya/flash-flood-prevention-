import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from ..config import settings

def get_sqlite_db_path() -> str:
    """
    Returns the resolved filesystem path for the SQLite database.
    Checks SQLITE_DB_PATH env var, persistent /data directory, or project root.
    """
    custom_path = os.environ.get("SQLITE_DB_PATH", "").strip()
    if custom_path:
        return custom_path
    elif os.path.isdir("/data") and os.access("/data", os.W_OK):
        return "/data/flashflood.db"
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        return os.path.join(project_root, "flashflood.db")

def resolve_database_url() -> str:
    """
    Resolves the active database connection URL.
    Supports Render Managed PostgreSQL or persistent SQLite.
    """
    use_sqlite = os.environ.get("USE_SQLITE", "true").lower() in ("true", "1", "yes")
    if not use_sqlite and settings.DATABASE_URL and not settings.DATABASE_URL.startswith("sqlite"):
        return settings.DATABASE_URL
    path = get_sqlite_db_path()
    return f"sqlite:///{path}"

db_url = resolve_database_url()

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

class RainfallRecord(Base):
    __tablename__ = "rainfall_records"
    __table_args__ = (
        UniqueConstraint("source", "latitude", "longitude", "valid_time", name="uix_rainfall_record"),
    )
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, index=True)  # e.g. "OPEN_METEO"
    data_type = Column(String)           # e.g. "FORECAST", "OBSERVATION"
    latitude = Column(Float)
    longitude = Column(Float)
    valid_time = Column(DateTime, index=True)
    retrieval_time = Column(DateTime, default=datetime.utcnow)
    precipitation_mm = Column(Float)
    units = Column(String, default="mm")
    raw_metadata = Column(JSON, nullable=True)

class ProviderHealth(Base):
    __tablename__ = "provider_health"
    id = Column(Integer, primary_key=True, index=True)
    provider_name = Column(String, unique=True, index=True)
    status = Column(String)  # CONNECTED, STALE, UNAVAILABLE, ERROR, NOT CONFIGURED
    last_attempt_time = Column(DateTime, nullable=True)
    last_success_time = Column(DateTime, nullable=True)
    latest_data_time = Column(DateTime, nullable=True)
    consecutive_failures = Column(Integer, default=0)
    error_message = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)

class LiveAlertEvent(Base):
    __tablename__ = "live_alerts"
    id = Column(String, primary_key=True, index=True)
    alert_type = Column(String, default="LIVE", index=True)  # LIVE, SIMULATION, or TEST
    severity = Column(String, index=True)                   # NORMAL, WATCH, WARNING, CRITICAL, STALE, UNKNOWN
    zone = Column(String, default="Chungthang Basin (Teesta River)")
    headline = Column(String)
    description = Column(String)
    trigger_rule = Column(String)
    trigger_inputs = Column(JSON)
    threshold_config = Column(JSON)
    predicted_discharge = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    threshold_name = Column(String, nullable=True)
    data_freshness_minutes = Column(Float, nullable=True)
    status = Column(String, default="ACTIVE", index=True)   # ACTIVE, ACKNOWLEDGED, RESOLVED, EXPIRED
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String, nullable=True)
    acknowledgement_notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    cap_xml = Column(String, nullable=True)

    deliveries = relationship("NotificationDelivery", back_populates="alert")

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String, unique=True, index=True)
    p256dh = Column(String)
    auth = Column(String)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    last_delivery_at = Column(DateTime, nullable=True)

class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(String, ForeignKey("live_alerts.id"), nullable=True)
    channel = Column(String, default="WEB_PUSH")  # WEB_PUSH, SMS
    recipient_id = Column(String)
    status = Column(String)  # SENT, FAILED, EXPIRED, SKIPPED, NOT_CONFIGURED
    attempt_time = Column(DateTime, default=datetime.utcnow)
    idempotency_key = Column(String, index=True, nullable=True)
    error_message = Column(String, nullable=True)
    response_json = Column(JSON, nullable=True)

    alert = relationship("LiveAlertEvent", back_populates="deliveries")

class RecipientDevice(Base):
    __tablename__ = "recipient_devices"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    channel = Column(String, default="SMS")
    identifier = Column(String, index=True)
    is_active = Column(Boolean, default=True)
    registered_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)
