import os
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# In-memory cache for processed GeoJSON layers to ensure fast delivery
_CATCHMENT_CACHE: Optional[Dict[str, Any]] = None
_STREAMS_CACHE: Optional[Dict[str, Any]] = None
_MANIFEST_CACHE: Optional[Dict[str, Any]] = None

def _resolve_path(rel_path: str) -> str:
    direct = os.path.join(PROJECT_ROOT, rel_path.lstrip("/\\"))
    if os.path.exists(direct):
        return direct
    if os.path.exists(rel_path):
        return rel_path
    return direct

# Settled critical points in Chungthang / Teesta Corridor
# Explicitly distinguishes Original CWC station vs DEM-snapped operational outlet
CRITICAL_LOCATIONS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "cwc_reference_station",
            "geometry": {
                "type": "Point",
                "coordinates": [88.6475, 27.5833]
            },
            "properties": {
                "id": "cwc_reference_station",
                "name": "CWC Chungthang Station (Reference)",
                "category": "cwc_reference_station",
                "category_label": "Official CWC Reference Gauge",
                "latitude": 27.5833,
                "longitude": 88.6475,
                "elevation_m": 1540.0,
                "catchment_area_km2": 2792.25,
                "description": (
                    "Official historical Central Water Commission (CWC) reference station coordinate. "
                    "Published catchment area is ~2,792 km². Retained as official ground reference benchmark."
                ),
                "is_operational_outlet": False,
                "color": "#F59E0B",
                "badge": "CWC REFERENCE"
            }
        },
        {
            "type": "Feature",
            "id": "dem_snapped_outlet",
            "geometry": {
                "type": "Point",
                "coordinates": [88.6551, 27.5851]
            },
            "properties": {
                "id": "dem_snapped_outlet",
                "name": "DEM-Snapped Operational Outlet",
                "category": "operational_outlet",
                "category_label": "Operational Model Outlet (Snapped)",
                "latitude": 27.5851,
                "longitude": 88.6551,
                "elevation_m": 1554.0,
                "flow_accumulation_cells": 3299343.0,
                "catchment_area_km2": 2969.41,
                "snap_distance_deg": 0.007845,
                "description": (
                    "Operationally snapped hydrological outlet derived from 30m SRTM DEM. "
                    "Located on the verified Teesta river mainstem with flow accumulation of ~3.3M cells "
                    "(~2,969.4 km²). Used for hydrological routing and model boundary conditions."
                ),
                "is_operational_outlet": True,
                "color": "#10B981",
                "badge": "DEM SNAPPED"
            }
        },
        {
            "type": "Feature",
            "id": "chungthang_confluence",
            "geometry": {
                "type": "Point",
                "coordinates": [88.6475, 27.6033]
            },
            "properties": {
                "id": "chungthang_confluence",
                "name": "Chungthang Town & River Confluence",
                "category": "settlement_confluence",
                "category_label": "Primary Settlement & Confluence",
                "latitude": 27.6033,
                "longitude": 88.6475,
                "elevation_m": 1600.0,
                "description": (
                    "Strategic mountain settlement and geographic confluence where Lachen Chu meets Lachung Chu "
                    "to form the Teesta River mainstem. High population and transport vulnerability."
                ),
                "is_operational_outlet": False,
                "color": "#8B5CF6",
                "badge": "CONFLUENCE"
            }
        },
        {
            "type": "Feature",
            "id": "teesta_3_dam",
            "geometry": {
                "type": "Point",
                "coordinates": [88.6515, 27.6040]
            },
            "properties": {
                "id": "teesta_3_dam",
                "name": "Teesta III Hydroelectric Dam (Barrage)",
                "category": "critical_infrastructure",
                "category_label": "Critical Hydro Infrastructure",
                "latitude": 27.6040,
                "longitude": 88.6515,
                "elevation_m": 1590.0,
                "capacity_mw": 1200,
                "description": (
                    "1,200 MW Teesta Stage-III Hydroelectric Project barrage site. "
                    "Severe damage sustained during the catastrophic South Lhonak GLOF event of October 2023."
                ),
                "is_operational_outlet": False,
                "color": "#EF4444",
                "badge": "INFRASTRUCTURE"
            }
        },
        {
            "type": "Feature",
            "id": "lachen_settlement",
            "geometry": {
                "type": "Point",
                "coordinates": [88.5500, 27.7167]
            },
            "properties": {
                "id": "lachen_settlement",
                "name": "Lachen Settlement (Upstream)",
                "category": "settlement_upstream",
                "category_label": "Upstream Mountain Settlement",
                "latitude": 27.7167,
                "longitude": 88.5500,
                "elevation_m": 2750.0,
                "tributary": "Lachen Chu",
                "description": (
                    "Major northern settlement along the Lachen Chu corridor; "
                    "critical early warning sensory and transit node for glacial lake outburst flow path."
                ),
                "is_operational_outlet": False,
                "color": "#38BDF8",
                "badge": "UPSTREAM"
            }
        },
        {
            "type": "Feature",
            "id": "lachung_settlement",
            "geometry": {
                "type": "Point",
                "coordinates": [88.7433, 27.6891]
            },
            "properties": {
                "id": "lachung_settlement",
                "name": "Lachung Settlement (Upstream)",
                "category": "settlement_upstream",
                "category_label": "Upstream Mountain Settlement",
                "latitude": 27.6891,
                "longitude": 88.7433,
                "elevation_m": 2700.0,
                "tributary": "Lachung Chu",
                "description": (
                    "Major northeastern valley settlement along the Lachung Chu tributary corridor."
                ),
                "is_operational_outlet": False,
                "color": "#38BDF8",
                "badge": "UPSTREAM"
            }
        },
        {
            "type": "Feature",
            "id": "tung_bridge",
            "geometry": {
                "type": "Point",
                "coordinates": [88.6520, 27.5450]
            },
            "properties": {
                "id": "tung_bridge",
                "name": "Tung Bridge / Corridor Bottleneck",
                "category": "downstream_corridor",
                "category_label": "Downstream Bottleneck Corridor",
                "latitude": 27.5450,
                "longitude": 88.6520,
                "elevation_m": 1350.0,
                "description": (
                    "Narrow river canyon constriction on the Teesta corridor south of Chungthang. "
                    "Critical highway lifeline and high backwater inundation risk zone."
                ),
                "is_operational_outlet": False,
                "color": "#F97316",
                "badge": "CORRIDOR"
            }
        },
        {
            "type": "Feature",
            "id": "mangan_hq",
            "geometry": {
                "type": "Point",
                "coordinates": [88.5300, 27.5100]
            },
            "properties": {
                "id": "mangan_hq",
                "name": "Mangan District Headquarters (DDMA)",
                "category": "administrative_center",
                "category_label": "Emergency Management Authority",
                "latitude": 27.5100,
                "longitude": 88.5300,
                "elevation_m": 1300.0,
                "description": (
                    "Headquarters of Mangan District and District Disaster Management Authority (DDMA). "
                    "Incident command center for Sikkim flash flood responses."
                ),
                "is_operational_outlet": False,
                "color": "#64748B",
                "badge": "DISASTER HQ"
            }
        }
    ]
}

@router.get("/")
async def get_terrain_summary():
    """
    Returns available terrain derivatives and status of processed geospatial datasets.
    """
    catchment_path = _resolve_path("data/processed/hydro/chungthang_catchment.geojson")
    streams_path = _resolve_path("data/processed/hydro/chungthang_streams.geojson")
    graph_path = _resolve_path("data/processed/hydro/chungthang_river_graph.json")
    manifest_path = _resolve_path("data/manifests/chungthang_terrain_manifest.json")

    return {
        "status": "READY",
        "study_area": "Chungthang Basin (Teesta River, Sikkim)",
        "layers": {
            "catchment": os.path.exists(catchment_path),
            "streams": os.path.exists(streams_path),
            "river_graph": os.path.exists(graph_path),
            "terrain_manifest": os.path.exists(manifest_path)
        },
        "target_coordinates": {
            "cwc_reference_coordinate": [88.6475, 27.5833],
            "dem_snapped_outlet_coordinate": [88.6551, 27.5851]
        },
        "notes": (
            "Accurate 30m SRTM-derived hydrography for Chungthang basin (~2,969 km²). "
            "Original CWC reference station and DEM-snapped operational outlet coordinates are preserved independently."
        )
    }

@router.get("/catchment")
async def get_catchment_geojson():
    """
    Returns the real delineated Chungthang watershed catchment polygon.
    """
    global _CATCHMENT_CACHE
    if _CATCHMENT_CACHE is not None:
        return _CATCHMENT_CACHE

    catchment_path = _resolve_path("data/processed/hydro/chungthang_catchment.geojson")
    if not os.path.exists(catchment_path):
        raise HTTPException(
            status_code=404,
            detail=f"Catchment GeoJSON file not found at {catchment_path}"
        )

    try:
        with open(catchment_path, "r", encoding="utf-8") as f:
            _CATCHMENT_CACHE = json.load(f)
        return _CATCHMENT_CACHE
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read catchment GeoJSON: {str(e)}")

@router.get("/streams")
async def get_streams_geojson():
    """
    Returns the real SRTM DEM-derived stream network geometry (1,413 segments).
    """
    global _STREAMS_CACHE
    if _STREAMS_CACHE is not None:
        return _STREAMS_CACHE

    streams_path = _resolve_path("data/processed/hydro/chungthang_streams.geojson")
    if not os.path.exists(streams_path):
        raise HTTPException(
            status_code=404,
            detail=f"Streams GeoJSON file not found at {streams_path}"
        )

    try:
        with open(streams_path, "r", encoding="utf-8") as f:
            _STREAMS_CACHE = json.load(f)
        return _STREAMS_CACHE
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read streams GeoJSON: {str(e)}")

@router.get("/locations")
async def get_critical_locations():
    """
    Returns verified settlements, critical infrastructure, CWC reference station,
    and DEM-snapped operational outlet locations for the Chungthang/Teesta corridor.
    """
    return CRITICAL_LOCATIONS

@router.get("/metadata")
async def get_terrain_metadata():
    """
    Returns topographic and hydrological metadata for Chungthang study area.
    """
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        manifest_path = _resolve_path("data/manifests/chungthang_terrain_manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    _MANIFEST_CACHE = json.load(f)
            except Exception:
                _MANIFEST_CACHE = {}
        else:
            _MANIFEST_CACHE = {}

    return {
        "study_area": "Chungthang Basin",
        "river": "Teesta",
        "district": "Mangan District",
        "state": "Sikkim",
        "crs": "EPSG:4326 (WGS 84)",
        "elevation_source": "SRTM 30m Conditioned Mosaic (N27E088, N28E088)",
        "bounding_box": [88.1171, 27.5699, 88.8882, 28.1268],
        "center": [88.6500, 27.5950],
        "default_zoom": 11.5,
        "catchment_area_km2": 2969.41,
        "mean_elevation_m": 4546.1,
        "mean_slope_deg": 27.55,
        "stream_segments_count": 1413,
        "target_coordinates": {
            "cwc_reference_coordinate": [88.6475, 27.5833],
            "cwc_reference_elevation_m": 1540.0,
            "cwc_catchment_area_km2": 2792.25,
            "dem_snapped_outlet_coordinate": [88.6551, 27.5851],
            "dem_snapped_outlet_elevation_m": 1554.0,
            "dem_flow_accumulation_cells": 3299343.0,
            "dem_catchment_area_km2": 2969.41,
            "snap_distance_deg": 0.007845,
            "snap_distance_approx_m": 870
        },
        "coordinate_provenance_note": (
            "The CWC Chungthang gauge station coordinate (27.5833°N, 88.6475°E) is preserved as an official reference benchmark. "
            "The DEM-snapped operational outlet (27.5851°N, 88.6551°E) is snapped to the maximum flow accumulation channel "
            "for physical model consistency. Neither replaces the other."
        ),
        "manifest": _MANIFEST_CACHE
    }
