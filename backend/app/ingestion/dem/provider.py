import os
import rasterio
from typing import Any, Dict, Optional
from datetime import datetime
from ..base import DataProvider, ProviderStatus

class DEMProvider(DataProvider):
    pass

class LocalCartoDEMProvider(DEMProvider):
    """
    Ingests official CartoDEM GeoTIFFs downloaded from Bhuvan.
    """
    def __init__(self, file_path: str = "data/raw/dem/teesta_cartodem.tif"):
        super().__init__()
        self.source_name = "ISRO CartoDEM"
        self.source_type = "DEM"
        self.file_path = file_path

    def fetch_data(self, **kwargs) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            self.error_message = f"DEM file not found: {self.file_path}"
            return None
        
        try:
            with rasterio.open(self.file_path) as src:
                elevation = src.read(1)
                meta = src.meta
                bounds = src.bounds
                nodata = src.nodata
                
                # Check for nodata fraction
                nodata_mask = (elevation == nodata)
                nodata_fraction = nodata_mask.sum() / elevation.size if nodata is not None else 0.0
                
                # Calculate stats
                valid_data = elevation[~nodata_mask] if nodata is not None else elevation
                min_elev = float(valid_data.min()) if valid_data.size > 0 else 0.0
                max_elev = float(valid_data.max()) if valid_data.size > 0 else 0.0

                self.last_updated = datetime.utcnow()
                
                return {
                    "elevation": elevation,
                    "meta": meta,
                    "metadata": {
                        "dem_id": "CARTODEM_TEESTA",
                        "source": self.source_name,
                        "filename": os.path.basename(self.file_path),
                        "crs": str(src.crs),
                        "resolution": src.res,
                        "bbox": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                        "min_elevation": min_elev,
                        "max_elevation": max_elev,
                        "nodata_fraction": nodata_fraction,
                        "ingestion_timestamp": self.last_updated.isoformat(),
                        "checksum": "checksum_not_calculated_yet"
                    }
                }
        except Exception as e:
            self.error_message = f"Error reading DEM: {str(e)}"
            return None

    def get_status(self) -> str:
        if os.path.exists(self.file_path):
            return ProviderStatus.AVAILABLE_LOCALLY
        return ProviderStatus.NOT_CONFIGURED

class SyntheticDEMProvider(DEMProvider):
    """
    Fallback provider generating the synthetic V-valley DEM for Simulation Mode ONLY.
    """
    def __init__(self):
        super().__init__()
        self.source_name = "Synthetic V-Valley DEM"
        self.source_type = "DEM"

    def fetch_data(self, **kwargs) -> Any:
        from ...geospatial.dem import process_dem
        self.last_updated = datetime.utcnow()
        return process_dem()

    def get_status(self) -> str:
        return ProviderStatus.SIMULATED
