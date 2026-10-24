import sys
from sqlalchemy import inspect, text
from backend.app.models.database import Base, engine

def migrate_db(custom_engine_or_url=None):
    should_dispose = False
    if custom_engine_or_url is None:
        target_engine = engine
    elif isinstance(custom_engine_or_url, str):
        from sqlalchemy import create_engine
        connect_args = {"check_same_thread": False} if custom_engine_or_url.startswith("sqlite") else {}
        target_engine = create_engine(custom_engine_or_url, connect_args=connect_args)
        should_dispose = True
    else:
        target_engine = custom_engine_or_url

    print(f"Running database schema migration for engine: {target_engine.url}...")
    Base.metadata.create_all(bind=target_engine)

    inspector = inspect(target_engine)
    tables = inspector.get_table_names()

    expected_tables = [
        "data_sources",
        "raw_observations",
        "hydrology_observations",
        "dem_metadata",
        "soil_moisture",
        "landslide_inventory",
        "rainfall_records",
        "provider_health",
        "live_alerts",
        "notification_deliveries",
        "recipient_devices",
        "push_subscriptions"
    ]

    missing = [t for t in expected_tables if t not in tables]
    for t in expected_tables:
        if t in tables:
            print(f"Table '{t}' verified.")
        else:
            print(f"ERROR: Table '{t}' missing!")

    # Check and migrate columns in live_alerts if needed
    if "live_alerts" in tables:
        existing_cols = [c["name"] for c in inspector.get_columns("live_alerts")]
        column_defs = {
            "zone": "VARCHAR(255) DEFAULT 'Chungthang Basin (Teesta River)'",
            "predicted_discharge": "FLOAT",
            "threshold_value": "FLOAT",
            "threshold_name": "VARCHAR(255)",
            "data_freshness_minutes": "FLOAT",
            "status": "VARCHAR(50) DEFAULT 'ACTIVE'",
            "acknowledged_at": "TIMESTAMP",
            "acknowledged_by": "VARCHAR(255)",
            "acknowledgement_notes": "TEXT"
        }

        with target_engine.begin() as conn:
            for col_name, col_type in column_defs.items():
                if col_name not in existing_cols:
                    print(f"Adding column '{col_name}' to 'live_alerts'...")
                    conn.execute(text(f"ALTER TABLE live_alerts ADD COLUMN {col_name} {col_type}"))

    if should_dispose:
        target_engine.dispose()

    if missing:
        print("Migration failed. Missing tables:", missing)
        return False
    else:
        print("Migration successful. All tables and columns verified.")
        return True

if __name__ == "__main__":
    success = migrate_db()
    if not success:
        sys.exit(1)
