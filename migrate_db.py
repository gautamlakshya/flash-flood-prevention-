from backend.app.models.database import Base, engine
import sqlite3

def migrate_db():
    print("Creating all tables in SQLite database...")
    Base.metadata.create_all(bind=engine)
    
    # Verify tables
    conn = sqlite3.connect("flashflood.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    
    expected_tables = [
        "data_sources",
        "raw_observations",
        "hydrology_observations",
        "dem_metadata",
        "soil_moisture",
        "landslide_inventory"
    ]
    
    missing = []
    for t in expected_tables:
        if t in tables:
            print(f"Table '{t}' verified.")
        else:
            missing.append(t)
            print(f"ERROR: Table '{t}' missing!")
            
    if missing:
        print("Migration failed. Missing tables:", missing)
    else:
        print("Migration successful. All new tables created.")
        
    conn.close()

if __name__ == "__main__":
    migrate_db()
