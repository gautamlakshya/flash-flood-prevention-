import os
import json
from typing import Any, List, Dict
from datetime import datetime
from ..base import DataProvider, ProviderStatus

class LandslideProvider(DataProvider):
    pass

class GSILandslideProvider(LandslideProvider):
    """
    Ingests official GSI Bhukosh Landslide Inventory (GeoJSON or Shapefile exports).
    GATE 12: Used strictly as spatial hazard context/vulnerability, NOT as discharge observations.
    """
    def __init__(self, file_path: str = "data/raw/landslides/teesta_gsi_inventory.geojson"):
        super().__init__()
        self.source_name = "GSI Bhukosh Landslide Inventory"
        self.source_type = "HAZARD_CONTEXT"
        self.file_path = file_path

    def fetch_data(self, **kwargs) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            self.error_message = f"File not found: {self.file_path}"
            return []
            
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            normalized_records = []
            features = data.get("features", [])
            for feat in features:
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                
                normalized_records.append({
                    "landslide_id": str(props.get("id", "UNKNOWN")),
                    "geometry": json.dumps(geom),
                    "event_date": props.get("date"),
                    "location": props.get("location"),
                    "state": props.get("state"),
                    "district": props.get("district"),
                    "source": "GSI",
                    "inventory_type": props.get("inventory_type", "Historical"),
                    "attributes": json.dumps(props)
                })
                
            self.last_updated = datetime.utcnow()
            return normalized_records
            
        except Exception as e:
            self.error_message = str(e)
            return []

    def get_status(self) -> str:
        if os.path.exists(self.file_path):
            return ProviderStatus.AVAILABLE_LOCALLY
        return ProviderStatus.NOT_CONFIGURED
