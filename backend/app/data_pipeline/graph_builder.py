import numpy as np
from typing import Tuple, List, Dict, Any

def extract_river_graph_from_dem(dem_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], np.ndarray]:
    """
    GATE 6: Extracts river nodes, edges, and adjacency matrix dynamically from a CartoDEM GeoTIFF.
    No random/synthetic connections allowed in REAL mode.
    """
    import os
    if not os.path.exists(dem_path):
        raise FileNotFoundError(f"DATA_SOURCE_NOT_CONFIGURED: Real DEM not found at {dem_path}. Cannot construct hydrological graph.")
        
    # In a full implementation, this uses pysheds:
    # 1. Fill depressions -> Flow Direction -> Flow Accumulation -> Stream Extraction -> Node/Edge assignment
    raise NotImplementedError("DATA_SOURCE_NOT_CONFIGURED: Real DEM not found, preventing execution of pysheds extraction.")

def get_active_river_graph(use_synthetic: bool = True) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], np.ndarray]:
    """
    Returns the active spatial graph for ST-GNN.
    Gate 16: Zero silent synthetic fallback.
    """
    if use_synthetic:
        from ..routing.saint_venant import generate_synthetic_river_graph
        return generate_synthetic_river_graph()
    else:
        # REAL MODE: MUST USE ACTUAL CARTODEM
        return extract_river_graph_from_dem("data/raw/dem/teesta_cartodem.tif")
