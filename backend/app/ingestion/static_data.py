import os
from typing import Dict, Any

class StaticDataAudit:
    """
    Audits the availability of actual static hydrological data.
    Gate 2 compliance.
    """
    
    def __init__(self, base_path: str = "data/raw/static"):
        candidates = [
            base_path,
            "../" + base_path.lstrip("/\\") if not base_path.startswith("..") else base_path
        ]
        self.base_path = base_path
        for c in candidates:
            if os.path.exists(c):
                self.base_path = c
                break
        
    def check_lulc(self) -> str:
        if os.path.exists(os.path.join(self.base_path, "lulc.tif")):
            return "CONFIGURED"
        return "NOT_CONFIGURED"
        
    def check_soil_hsg(self) -> str:
        if os.path.exists(os.path.join(self.base_path, "soil_hsg.tif")) or os.path.exists(os.path.join(self.base_path, "soil_hsg.shp")):
            return "CONFIGURED"
        return "NOT_CONFIGURED"
        
    def check_river_network(self) -> str:
        if os.path.exists(os.path.join(self.base_path, "river_network.shp")):
            return "CONFIGURED"
        return "NOT_CONFIGURED"
        
    def check_channel_geometry(self) -> str:
        if os.path.exists(os.path.join(self.base_path, "cross_sections.csv")):
            return "CONFIGURED"
        return "NOT_CONFIGURED"
        
    def check_watershed_boundaries(self) -> str:
        if os.path.exists(os.path.join(self.base_path, "watershed.shp")):
            return "CONFIGURED"
        return "NOT_CONFIGURED"

    def get_audit_report(self) -> Dict[str, str]:
        return {
            "LULC": self.check_lulc(),
            "Hydrologic Soil Groups": self.check_soil_hsg(),
            "River Network": self.check_river_network(),
            "Channel Geometry/Cross Sections": self.check_channel_geometry(),
            "Watershed Boundaries": self.check_watershed_boundaries()
        }
