import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...models.database import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
from ...ingestion.base import ProviderStatus
from ...ingestion.dem.provider import LocalCartoDEMProvider
from ...ingestion.landslides.provider import GSILandslideProvider
from ...ingestion.imd.provider import IMDAWSProvider
from ...ingestion.sentinel1.provider import LocalSentinel1Provider
from ...ingestion.hydrology.provider import LocalCWCHydrologyProvider
from ...ingestion.rainfall.open_meteo import OpenMeteoRainfallProvider
from ...ingestion.rainfall.gpm_imerg import GPMIMERGProvider

router = APIRouter()

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

def _check_local_file(rel_path: str, min_bytes: int = 100) -> Dict[str, Any]:
    """
    Verifies that a local file exists on disk, has non-zero size, and can be read.
    """
    candidates = [
        os.path.abspath(os.path.join(PROJECT_ROOT, rel_path.lstrip("/\\"))),
        os.path.abspath(rel_path)
    ]
    target = None
    for c in candidates:
        if os.path.exists(c):
            target = c
            break

    if target and os.path.exists(target) and os.path.getsize(target) >= min_bytes:
        try:
            # Read first 64 bytes to verify readability
            with open(target, "rb") as f:
                f.read(64)
            stat = os.stat(target)
            mod_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            return {
                "available": True,
                "path": rel_path,
                "size_bytes": stat.st_size,
                "last_modified": mod_time,
                "error": None
            }
        except Exception as e:
            return {
                "available": False,
                "path": rel_path,
                "size_bytes": 0,
                "last_modified": None,
                "error": f"File exists but is unreadable: {str(e)}"
            }

    return {
        "available": False,
        "path": rel_path,
        "size_bytes": 0,
        "last_modified": None,
        "error": f"Required dataset file missing at {rel_path}"
    }

@router.get("/")
@router.get("")
async def get_data_sources_status(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Returns the audited real-time status of all external telemetry feeds,
    local geospatial datasets, and simulation engines.
    """
    statuses: List[Dict[str, Any]] = []

    # 1. Open-Meteo NWP Forecast (External Service)
    om_provider = OpenMeteoRainfallProvider()
    om_meta = om_provider.get_metadata(db=db)
    statuses.append(om_meta)

    # 2. NASA GPM IMERG (Satellite Precipitation Observation)
    gpm_provider = GPMIMERGProvider()
    statuses.append(gpm_provider.get_metadata())

    # 3. IMD AWS In-situ Rainfall (Observation - Restricted)
    imd_provider = IMDAWSProvider()
    statuses.append(imd_provider.get_metadata())

    # 4. CWC River Discharge & Stage (Observation - Restricted)
    cwc_provider = LocalCWCHydrologyProvider()
    cwc_meta = cwc_provider.get_metadata()
    # Explicitly show restricted status in data sources dashboard
    cwc_meta["status"] = ProviderStatus.RESTRICTED if not os.path.exists(cwc_provider.file_path) else ProviderStatus.AVAILABLE_LOCALLY
    statuses.append(cwc_meta)

    # 5. SRTM 30m Conditioned DEM (Local Dataset)
    srtm_check = _check_local_file("data/processed/dem/chungthang_srtm_conditioned.tif")
    srtm_raw1 = _check_local_file("data/raw/dem/srtm/N27E088.hgt")
    srtm_raw2 = _check_local_file("data/raw/dem/srtm/N28E088.hgt")
    srtm_avail = srtm_check["available"] and srtm_raw1["available"] and srtm_raw2["available"]
    statuses.append({
        "name": "SRTM 30m Conditioned DEM (Chungthang)",
        "type": "DEM",
        "data_category": "STATIC_GEO",
        "status": ProviderStatus.AVAILABLE_LOCALLY if srtm_avail else ProviderStatus.NOT_CONFIGURED,
        "last_updated": srtm_check["last_modified"],
        "expected_path": "data/processed/dem/chungthang_srtm_conditioned.tif",
        "error": None if srtm_avail else srtm_check["error"],
        "notes": (
            "Conditioned 1 arc-second (~30m) SRTM digital elevation model with hydrodynamic pit-filling and breach conditioning. "
            f"Verified files: conditioned DEM ({round(srtm_check['size_bytes'] / (1024*1024), 1)} MB), tiles N27E088 and N28E088."
            if srtm_avail else srtm_check["error"]
        )
    })

    # 6. ISRO CartoDEM v3 (Local Dataset)
    carto_check = _check_local_file("data/raw/dem/cdnh45w.tif")
    statuses.append({
        "name": "ISRO CartoDEM (30m cdnh45w.tif)",
        "type": "DEM",
        "data_category": "STATIC_GEO",
        "status": ProviderStatus.AVAILABLE_LOCALLY if carto_check["available"] else ProviderStatus.NOT_CONFIGURED,
        "last_updated": carto_check["last_modified"],
        "expected_path": "data/raw/dem/cdnh45w.tif",
        "error": None if carto_check["available"] else carto_check["error"],
        "notes": (
            f"Official CartoDEM v3 R1 GeoTIFF ({round(carto_check['size_bytes'] / (1024*1024), 1)} MB) downloaded from Bhuvan covering the Chungthang quadrangle."
            if carto_check["available"] else carto_check["error"]
        )
    })

    # 7. Teesta River Stream Network (Local Hydrography)
    streams_check = _check_local_file("data/processed/hydro/chungthang_streams.geojson")
    graph_check = _check_local_file("data/processed/hydro/chungthang_river_graph.json")
    streams_avail = streams_check["available"] and graph_check["available"]
    statuses.append({
        "name": "Teesta River Stream Network (Vector Hydrography)",
        "type": "HYDRO_NETWORK",
        "data_category": "STATIC_GEO",
        "status": ProviderStatus.AVAILABLE_LOCALLY if streams_avail else ProviderStatus.NOT_CONFIGURED,
        "last_updated": streams_check["last_modified"],
        "expected_path": "data/processed/hydro/chungthang_streams.geojson",
        "error": None if streams_avail else streams_check["error"],
        "notes": (
            f"Hydrologically derived stream network (1,413 segments, {round(streams_check['size_bytes'] / (1024*1024), 1)} MB) "
            "and topological routing graph thresholded at 10,000 cells (~9 km² accumulation)."
            if streams_avail else streams_check["error"]
        )
    })

    # 8. Chungthang Delineated Catchment (Local Boundary)
    catchment_check = _check_local_file("data/processed/hydro/chungthang_catchment.geojson")
    mask_check = _check_local_file("data/processed/hydro/chungthang_catchment_mask.tif")
    catchment_avail = catchment_check["available"] and mask_check["available"]
    statuses.append({
        "name": "Chungthang Delineated Catchment Boundary",
        "type": "CATCHMENT_BOUNDARY",
        "data_category": "STATIC_GEO",
        "status": ProviderStatus.AVAILABLE_LOCALLY if catchment_avail else ProviderStatus.NOT_CONFIGURED,
        "last_updated": catchment_check["last_modified"],
        "expected_path": "data/processed/hydro/chungthang_catchment.geojson",
        "error": None if catchment_avail else catchment_check["error"],
        "notes": (
            "Hydrologically delineated watershed polygon (~2,969.4 km²) draining to the DEM-snapped operational outlet at 27.5851°N, 88.6551°E."
            if catchment_avail else catchment_check["error"]
        )
    })

    # 9. Topographic Terrain Derivatives (Slope & Flow Accumulation)
    facc_check = _check_local_file("data/processed/terrain/flow_accumulation.tif")
    slope_check = _check_local_file("data/processed/terrain/slope.tif")
    terrain_avail = facc_check["available"] and slope_check["available"]
    statuses.append({
        "name": "Terrain Derivatives (Flow Accumulation & Slope)",
        "type": "TERRAIN_DERIVATIVES",
        "data_category": "STATIC_GEO",
        "status": ProviderStatus.AVAILABLE_LOCALLY if terrain_avail else ProviderStatus.NOT_CONFIGURED,
        "last_updated": facc_check["last_modified"],
        "expected_path": "data/processed/terrain/flow_accumulation.tif",
        "error": None if terrain_avail else facc_check["error"],
        "notes": (
            f"Conditioned D8 flow accumulation raster ({round(facc_check['size_bytes'] / (1024*1024), 1)} MB, max 3,299,343 cells) "
            f"and degree slope raster ({round(slope_check['size_bytes'] / (1024*1024), 1)} MB) for hydraulic routing."
            if terrain_avail else facc_check["error"]
        )
    })

    # 10. GSI Bhukosh Landslide Inventory (Local Hazard Context)
    gsi_provider = GSILandslideProvider()
    gsi_meta = gsi_provider.get_metadata()
    if gsi_meta["status"] == ProviderStatus.NOT_CONFIGURED:
        gsi_meta["error"] = "GSI landslide inventory GeoJSON missing at data/raw/landslides/teesta_gsi_inventory.geojson"
    statuses.append(gsi_meta)

    # 11. Sentinel-1 SAR Backscatter (Soil Moisture)
    s1_provider = LocalSentinel1Provider()
    s1_meta = s1_provider.get_metadata()
    if s1_meta["status"] == ProviderStatus.NOT_CONFIGURED:
        s1_meta["error"] = "Sentinel-1 SAR GeoTIFFs missing at data/sentinel1/vv.tif and vh.tif (Requires Copernicus Data Space access)"
    statuses.append(s1_meta)

    # 12. Land Use / Land Cover (LULC - Static)
    lulc_check = _check_local_file("data/raw/static/lulc.tif")
    statuses.append({
        "name": "Land Use / Land Cover (LULC)",
        "type": "STATIC_LAYER",
        "data_category": "STATIC_GEO",
        "status": ProviderStatus.AVAILABLE_LOCALLY if lulc_check["available"] else ProviderStatus.NOT_CONFIGURED,
        "last_updated": lulc_check["last_modified"],
        "expected_path": "data/raw/static/lulc.tif",
        "error": lulc_check["error"],
        "notes": "Surface roughness and Manning's n coefficient layer. Awaiting placement in data/raw/static/lulc.tif."
    })

    # 13. Hydrologic Soil Groups (HSG - Static)
    hsg_check = _check_local_file("data/raw/static/soil_hsg.tif")
    statuses.append({
        "name": "Hydrologic Soil Groups (HSG)",
        "type": "STATIC_LAYER",
        "data_category": "STATIC_GEO",
        "status": ProviderStatus.AVAILABLE_LOCALLY if hsg_check["available"] else ProviderStatus.NOT_CONFIGURED,
        "last_updated": hsg_check["last_modified"],
        "expected_path": "data/raw/static/soil_hsg.tif",
        "error": hsg_check["error"],
        "notes": "NRCS/SCS soil classification layer (A/B/C/D) for runoff curve number estimation. Awaiting placement in data/raw/static/soil_hsg.tif."
    })

    # 14. Channel Cross Sections / Geometry (Static)
    xs_check = _check_local_file("data/raw/static/cross_sections.csv")
    statuses.append({
        "name": "Channel Geometry & Cross Sections",
        "type": "STATIC_LAYER",
        "data_category": "STATIC_GEO",
        "status": ProviderStatus.AVAILABLE_LOCALLY if xs_check["available"] else ProviderStatus.NOT_CONFIGURED,
        "last_updated": xs_check["last_modified"],
        "expected_path": "data/raw/static/cross_sections.csv",
        "error": xs_check["error"],
        "notes": "Surveyed river cross-section geometries for 1D hydrodynamic routing. Awaiting placement in data/raw/static/cross_sections.csv."
    })

    # 15. Synthetic Weather & Hydro Generator (Simulation Engine)
    statuses.append({
        "name": "Synthetic Weather & Hydro Generator",
        "type": "SIMULATION_ENGINE",
        "data_category": "SIMULATION",
        "status": ProviderStatus.CONNECTED,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "error": None,
        "notes": "Deterministic synthetic cloudburst and dam-breach scenario generator for offline simulation and stress testing."
    })

    return statuses
