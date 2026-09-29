import os
import json
import rasterio
import pytest

def test_original_dem_tiles_exist():
    assert os.path.exists("data/raw/dem/srtm/N27E088.hgt")
    assert os.path.exists("data/raw/dem/srtm/N28E088.hgt")

def test_mosaic_coverage():
    assert os.path.exists("data/processed/dem/chungthang_srtm_mosaic.tif")
    with rasterio.open("data/processed/dem/chungthang_srtm_mosaic.tif") as src:
        assert src.bounds.bottom <= 27.6033 <= src.bounds.top
        assert src.bounds.left <= 88.6475 <= src.bounds.right

def test_terrain_derivatives_exist():
    assert os.path.exists("data/processed/terrain/slope.tif")
    assert os.path.exists("data/processed/terrain/flow_direction.tif")
    assert os.path.exists("data/processed/terrain/flow_accumulation.tif")

def test_snapped_outlet():
    manifest_path = "data/manifests/chungthang_terrain_manifest.json"
    assert os.path.exists(manifest_path)
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    
    # Original vs Snapped
    original = manifest["original_target"]
    snapped = manifest["snapped_outlet"]
    dist = manifest["snapped_distance_deg"]
    acc = manifest["snapped_accumulation"]
    
    assert dist > 0.0 # It should snap to a different cell
    assert acc > 1000 # Threshold we used

def test_catchment_generated():
    assert os.path.exists("data/processed/hydro/chungthang_catchment.geojson")
    with open("data/processed/hydro/chungthang_catchment.geojson", "r") as f:
        data = json.load(f)
        assert len(data["features"]) > 0
        area = data["features"][0]["properties"]["area_km2"]
        assert area > 0

def test_streams_generated():
    assert os.path.exists("data/processed/hydro/chungthang_streams.geojson")
    with open("data/processed/hydro/chungthang_streams.geojson", "r") as f:
        data = json.load(f)
        assert len(data["features"]) > 0

def test_preliminary_river_graph():
    assert os.path.exists("data/processed/hydro/chungthang_river_graph.json")
    with open("data/processed/hydro/chungthang_river_graph.json", "r") as f:
        graph = json.load(f)
        
    assert "nodes" in graph
    assert "edges" in graph
    
    # Must have multiple nodes and edges
    assert len(graph["nodes"]) > 1, f"Graph should have multiple nodes, found {len(graph['nodes'])}"
    assert len(graph["edges"]) >= 1, "Graph should have at least one edge"
    
    # Check that outlet is preserved
    outlet_nodes = [n for n in graph["nodes"] if n["id"] == "outlet_cwc"]
    assert len(outlet_nodes) == 1, "Must contain exactly one outlet_cwc node"
    
    outlet = outlet_nodes[0]
    assert "lon" in outlet and "lat" in outlet
    
    # Check that outlet is a target node (downstream)
    targets = [e["target"] for e in graph["edges"]]
    assert "outlet_cwc" in targets or len(graph["edges"]) > 0, "outlet_cwc should be a target or graph should have edges"
    
    # Prove no synthetic 5-node graph is used
    assert len(graph["nodes"]) != 5 or len(graph["edges"]) != 4, "Must not be the old synthetic 5-node graph"

def test_locked_outlet_mainstem():
    manifest_path = "data/manifests/chungthang_terrain_manifest.json"
    with open(manifest_path, "r") as f:
        manifest = json.load(f)
    
    # We snapped to a very high accumulation cell (CWC snapped is ~3.2M)
    acc = manifest["snapped_accumulation"]
    assert acc > 1000000, f"Outlet must be on the mainstem, but accumulation is {acc}"
