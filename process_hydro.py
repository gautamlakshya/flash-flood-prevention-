import os
import glob
import json
import yaml
import numpy as np
import rasterio
from rasterio.merge import merge
import geopandas as gpd
from shapely.geometry import shape, Point, LineString
import pysheds
from pysheds.grid import Grid
from datetime import datetime

# Setup paths
os.makedirs("data/processed/dem", exist_ok=True)
os.makedirs("data/processed/terrain", exist_ok=True)
os.makedirs("data/processed/hydro", exist_ok=True)
os.makedirs("data/manifests", exist_ok=True)

# 1. Mosaic
dem_files = glob.glob("data/raw/dem/srtm/*.hgt")
src_files_to_mosaic = []
for fp in dem_files:
    src = rasterio.open(fp)
    src_files_to_mosaic.append(src)

mosaic, out_trans = merge(src_files_to_mosaic)
out_meta = src_files_to_mosaic[0].meta.copy()

out_meta.update({
    "driver": "GTiff",
    "height": mosaic.shape[1],
    "width": mosaic.shape[2],
    "transform": out_trans,
    "crs": src_files_to_mosaic[0].crs,
    "nodata": -32768.0
})

mosaic_path = "data/processed/dem/chungthang_srtm_mosaic.tif"
with rasterio.open(mosaic_path, "w", **out_meta) as dest:
    dest.write(mosaic)

for src in src_files_to_mosaic:
    src.close()

print(f"Mosaicked DEM saved to {mosaic_path}")

# 2. PySheds Processing
grid = Grid.from_raster(mosaic_path)
dem = grid.read_raster(mosaic_path, nodata=-32768.0)

# Conditioning (resolve pits and depressions)
dem_filled_pits = grid.fill_pits(dem)
dem_filled_depressions = grid.fill_depressions(dem_filled_pits)
dem_resolved_flats = grid.resolve_flats(dem_filled_depressions)

grid.to_raster(dem_resolved_flats, "data/processed/dem/chungthang_srtm_conditioned.tif")

# Flow Direction (D8)
# D8 directional mapping in pysheds:
dirmap = (64, 128, 1, 2, 4, 8, 16, 32)
fdir = grid.flowdir(dem_resolved_flats, dirmap=dirmap)
grid.to_raster(fdir, "data/processed/terrain/flow_direction.tif")

# Flow Accumulation
acc = grid.accumulation(fdir, dirmap=dirmap)
grid.to_raster(acc, "data/processed/terrain/flow_accumulation.tif")

# Calculate Slope
from backend.app.geospatial.dem import calculate_slope
# Cell size approx 30m for SRTM 1-arcsec
slope_deg = calculate_slope(dem_resolved_flats.astype(np.float32), cell_size_m=30.0)
grid.to_raster(slope_deg, "data/processed/terrain/slope.tif")

# Read target from config
with open("config/study_area.yaml", "r") as f:
    config = yaml.safe_load(f)
target_coords = config.get("target", {}).get("dem_snapped_outlet_coordinate", [88.6551, 27.5851])
lon, lat = target_coords[0], target_coords[1]

# Snap outlet
# We want to snap to a cell with a reasonably high flow accumulation, e.g. > 1000
snap_threshold = 1000
mask = acc > snap_threshold
x_snap, y_snap = grid.snap_to_mask(mask, (lon, lat), return_dist=False)
col, row = ~grid.affine * (x_snap, y_snap)
row, col = int(row), int(col)
snapped_acc = acc[row, col]
snapped_elev = dem_resolved_flats[row, col]

# Extract Catchment
catch = grid.catchment(x=x_snap, y=y_snap, fdir=fdir, dirmap=dirmap, xytype='coordinate')
catch = catch.astype(np.uint8)
grid.to_raster(catch, "data/processed/hydro/chungthang_catchment_mask.tif")

# Is catchment touching boundaries?
catch_data = catch.astype(bool)
touches_top = np.any(catch_data[0, :])
touches_bottom = np.any(catch_data[-1, :])
touches_left = np.any(catch_data[:, 0])
touches_right = np.any(catch_data[:, -1])
boundary_touch = touches_top or touches_bottom or touches_left or touches_right

# Catchment area
pixel_area_km2 = (30.0 * 30.0) / 1000000.0
catchment_area_km2 = float(np.sum(catch_data) * pixel_area_km2)

catch_elev = dem_resolved_flats[catch_data]
catch_min = float(catch_elev.min())
catch_max = float(catch_elev.max())
catch_mean = float(catch_elev.mean())

catch_slope = slope_deg[catch_data]
catch_slope_mean = float(catch_slope.mean())

# Polygonize catchment
shapes = grid.polygonize(catch)
catchment_geom = None
for s, val in shapes:
    if val == 1:
        catchment_geom = shape(s)
        break

catchment_geojson = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "geometry": catchment_geom.__geo_interface__,
        "properties": {
            "area_km2": catchment_area_km2,
            "mean_elevation": catch_mean,
            "min_elevation": catch_min,
            "max_elevation": catch_max
        }
    }]
}
with open("data/processed/hydro/chungthang_catchment.geojson", "w") as f:
    json.dump(catchment_geojson, f)

# Stream Extraction Threshold testing
thresholds = [1000, 5000, 10000]
stream_stats = {}
for thresh in thresholds:
    branches = grid.extract_river_network(fdir, acc > thresh, dirmap=dirmap)
    lines = []
    for branch in branches['features']:
        lines.append(shape(branch['geometry']))
    stream_stats[thresh] = {
        "num_segments": len(lines),
        "total_length": sum([l.length for l in lines]) * 100000 # Approx length in meters rough
    }

# Choose 10000 as preliminary
selected_threshold = 10000
branches = grid.extract_river_network(fdir, acc > selected_threshold, dirmap=dirmap)
with open("data/processed/hydro/chungthang_streams.geojson", "w") as f:
    json.dump(branches, f)
    
# Produce preliminary graph from branches
graph = {
    "nodes": [],
    "edges": []
}

node_map = {}
node_counter = 1

# Add snapped outlet explicitly
outlet_id = "outlet_cwc"
graph["nodes"].append({
    "id": outlet_id,
    "lon": float(x_snap),
    "lat": float(y_snap),
    "elevation": float(snapped_elev),
    "accumulation": float(snapped_acc)
})
# We'll map the snapped coordinates to the outlet_id with some tolerance
def get_node_id(lon, lat):
    # check if close to outlet
    if abs(lon - x_snap) < 1e-4 and abs(lat - y_snap) < 1e-4:
        return outlet_id
    # check if exists
    for (nlon, nlat), nid in node_map.items():
        if abs(lon - nlon) < 1e-4 and abs(lat - nlat) < 1e-4:
            return nid
    return None

for branch in branches['features']:
    coords = branch['geometry']['coordinates']
    for i in range(len(coords) - 1):
        u_lon, u_lat = coords[i]
        v_lon, v_lat = coords[i+1]
        
        uid = get_node_id(u_lon, u_lat)
        if not uid:
            uid = f"node_{node_counter}"
            node_counter += 1
            node_map[(u_lon, u_lat)] = uid
            graph["nodes"].append({
                "id": uid,
                "lon": float(u_lon),
                "lat": float(u_lat)
            })
            
        vid = get_node_id(v_lon, v_lat)
        if not vid:
            vid = f"node_{node_counter}"
            node_counter += 1
            node_map[(v_lon, v_lat)] = vid
            graph["nodes"].append({
                "id": vid,
                "lon": float(v_lon),
                "lat": float(v_lat)
            })
            
        graph["edges"].append({
            "source": uid,
            "target": vid,
            "type": "flow"
        })

with open("data/processed/hydro/chungthang_river_graph.json", "w") as f:
    json.dump(graph, f)

report = {
    "files_used": dem_files,
    "mosaic": {
        "bounds": list(out_meta["transform"] * (0,0)) + list(out_meta["transform"] * (out_meta["width"], out_meta["height"])),
        "width": out_meta["width"],
        "height": out_meta["height"]
    },
    "original_target": [lon, lat],
    "snapped_outlet": [float(x_snap), float(y_snap)],
    "snapped_distance_deg": float(np.sqrt((lon - x_snap)**2 + (lat - y_snap)**2)),
    "snapped_accumulation": float(snapped_acc),
    "boundary_touch": bool(boundary_touch),
    "catchment": {
        "area_km2": catchment_area_km2,
        "mean_elevation": catch_mean,
        "mean_slope": catch_slope_mean
    },
    "stream_thresholds": stream_stats,
    "selected_threshold": selected_threshold
}

with open("data/manifests/chungthang_terrain_manifest.json", "w") as f:
    json.dump(report, f, indent=4)

print("Hydrological Processing Complete.")
