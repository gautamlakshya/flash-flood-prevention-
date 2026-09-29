from fastapi import APIRouter
from typing import List, Dict, Any

from ...ingestion.dem.provider import LocalCartoDEMProvider
from ...ingestion.landslides.provider import GSILandslideProvider
from ...ingestion.imd.provider import IMDAWSProvider
from ...ingestion.sentinel1.provider import LocalSentinel1Provider
from ...ingestion.hydrology.provider import LocalCWCHydrologyProvider
from ...ingestion.static_data import StaticDataAudit

router = APIRouter()

@router.get("/")
async def get_data_sources_status() -> List[Dict[str, Any]]:
    """
    Returns the real-time status of all data ingestion providers.
    """
    providers = [
        LocalCartoDEMProvider(),
        GSILandslideProvider(),
        IMDAWSProvider(),
        LocalSentinel1Provider(),
        LocalCWCHydrologyProvider()
    ]
    
    statuses = [p.get_metadata() for p in providers]
    
    # Gate 18: Add Static Data sources explicitly
    static_audit = StaticDataAudit()
    static_report = static_audit.get_audit_report()
    for name, status in static_report.items():
        statuses.append({
            "name": name,
            "type": "STATIC_LAYER",
            "status": "NOT CONFIGURED" if status == "NOT_CONFIGURED" else "CONNECTED",
            "last_updated": None,
            "error": "Dataset missing from data/raw/static/" if status == "NOT_CONFIGURED" else None
        })
        
    return statuses
