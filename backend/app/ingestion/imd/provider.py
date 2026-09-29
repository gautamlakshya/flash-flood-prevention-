import os
import json
import requests
from typing import Any, List, Dict
from datetime import datetime
from ..base import DataProvider, ProviderStatus
from ...config import settings

class IMDProvider(DataProvider):
    pass

class IMDAWSProvider(IMDProvider):
    """
    Ingests live weather data from IMD AWS (Automatic Weather Stations) API.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "IMD AWS API"
        self.source_type = "HYDROMET"
        self.api_url = os.environ.get("IMD_API_URL", "")
        self.api_key = os.environ.get("IMD_API_KEY", "")

    def fetch_data(self, **kwargs) -> List[Dict[str, Any]]:
        if not self.api_url or not self.api_key:
            self.error_message = "IMD API credentials not configured."
            return []
            
        try:
            response = requests.get(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            response.raise_for_status()
            raw_data = response.json()
            
            # GATE 1: Store raw response before transformation
            raw_path = f"data/raw/rainfall/imd_raw_{int(datetime.utcnow().timestamp())}.json"
            os.makedirs(os.path.dirname(raw_path), exist_ok=True)
            with open(raw_path, "w") as f:
                json.dump(raw_data, f)
            
            normalized_records = []
            for obs in raw_data.get("observations", []):
                normalized_records.append({
                    "source": "IMD_AWS",
                    "station_id": str(obs.get("station_id")),
                    "timestamp": obs.get("timestamp"),
                    "parameter": "rainfall",
                    "value": float(obs.get("rainfall_mm", 0.0)),
                    "unit": "mm",
                    "quality_flag": str(obs.get("qc_flag", "UNKNOWN")),
                    "raw_record_id": str(obs.get("id", "N/A")),
                    # Extra fields explicitly requested
                    "latitude": float(obs.get("lat", 0.0)),
                    "longitude": float(obs.get("lon", 0.0)),
                    "temperature_c": float(obs.get("temp_c", 0.0)) if "temp_c" in obs else None,
                    "humidity": float(obs.get("rh", 0.0)) if "rh" in obs else None,
                    "wind": float(obs.get("wind", 0.0)) if "wind" in obs else None
                })
                
            self.last_updated = datetime.utcnow()
            return normalized_records
            
        except requests.RequestException as e:
            self.error_message = f"IMD API Request failed: {str(e)}"
            return []
        except Exception as e:
            self.error_message = f"Failed to parse IMD response: {str(e)}"
            return []

    def get_status(self) -> str:
        if self.api_url and self.api_key:
            if self.last_updated:
                return ProviderStatus.CONNECTED
            elif self.error_message:
                return ProviderStatus.ERROR
            return ProviderStatus.CONNECTED
        return ProviderStatus.NOT_CONFIGURED
