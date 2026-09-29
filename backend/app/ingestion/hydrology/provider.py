import os
import pandas as pd
from typing import Any, List, Dict
from datetime import datetime
from ..base import DataProvider, ProviderStatus

class HydrologyObservationProvider(DataProvider):
    pass

class LocalCWCHydrologyProvider(HydrologyObservationProvider):
    """
    Ingests locally downloaded CWC/India-WRIS historical discharge observations.
    CRITICAL: The ST-GNN target MUST originate from these actual observations.
    """
    def __init__(self, file_path: str = "data/raw/hydrology/teesta_cwc_discharge.csv"):
        super().__init__()
        self.source_name = "CWC Historical Discharge"
        self.source_type = "HYDROLOGY"
        self.file_path = file_path

    def fetch_data(self, **kwargs) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            self.error_message = f"Hydrology CSV not found: {self.file_path}"
            return []
            
        try:
            df = pd.read_csv(self.file_path)
            
            normalized_records = []
            for _, row in df.iterrows():
                # Extract observed targets
                # If discharge is missing, we append None instead of inventing a value
                q = float(row["discharge_m3s"]) if pd.notna(row.get("discharge_m3s")) else None
                wl = float(row["water_level_m"]) if pd.notna(row.get("water_level_m")) else None
                
                normalized_records.append({
                    "station_id": str(row.get("station_id", "UNKNOWN")),
                    "timestamp": row.get("timestamp"),
                    "discharge_m3s": q,
                    "water_level_m": wl,
                    "unit": "m3/s",
                    "source": "CWC_LOCAL",
                    "quality_flag": str(row.get("quality_flag", "GOOD"))
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
