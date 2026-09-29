import json
import yaml
import numpy as np
import rasterio
from pysheds.grid import Grid
from shapely.geometry import Point, mapping
import math

# Load config
with open("config/study_area.yaml", "r") as f:
    config = yaml.safe_load(f)
target_coords = config.get("target", {}).get("target_coordinates", [88.6475, 27.6033])
lon, lat = target_coords[0], target_coords[1]

# Load grids
dem_path = "data/processed/dem/chungthang_srtm_conditioned.tif"
fdir_path = "data/processed/terrain/flow_direction.tif"
acc_path = "data/processed/terrain/flow_accumulation.tif"
slope_path = "data/processed/terrain/slope.tif"

grid = Grid.from_raster(dem_path)
dem = grid.read_raster(dem_path)
fdir = grid.read_raster(fdir_path)
acc = grid.read_raster(acc_path)
slope = grid.read_raster(slope_path)
dirmap = (64, 128, 1, 2, 4, 8, 16, 32)

# Find cells within ~3km radius
# 1 deg approx 111km, so 3km is ~0.027 deg
radius_deg = 0.03
col_center, row_center = ~grid.affine * (lon, lat)
col_center, row_center = int(col_center), int(row_center)

# Search window
half_win = int(radius_deg / grid.affine.a) # a is pixel width in deg
row_min = max(0, row_center - half_win)
row_max = min(grid.shape[0], row_center + half_win)
col_min = max(0, col_center - half_win)
col_max = min(grid.shape[1], col_center + half_win)

acc_window = acc[row_min:row_max, col_min:col_max]
# Find candidate cells with high accumulation
# We want distinct streams, not just adjacent cells on the same river.
# We can find local maxima in the window or just take the absolute top cells.
# Let's take cells > 100,000 cells (approx 90 km2) 
candidate_threshold = 100000
y_idx, x_idx = np.where(acc_window > candidate_threshold)

candidates = []
for yi, xi in zip(y_idx, x_idx):
    r = row_min + yi
    c = col_min + xi
    x_coord, y_coord = grid.affine * (c, r)
    dist = math.sqrt((x_coord - lon)**2 + (y_coord - lat)**2)
    
    # only keep if within radius
    if dist <= radius_deg:
        candidates.append({
            "row": int(r),
            "col": int(c),
            "lon": float(x_coord),
            "lat": float(y_coord),
            "dist": float(dist),
            "acc": float(acc[r, c]),
            "elev": float(dem[r, c]),
            "slope": float(slope[r, c])
        })

# Sort by accumulation descending
candidates.sort(key=lambda x: x["acc"], reverse=True)

# Filter out adjacent cells on the same river stream (keep local maxima)
filtered_candidates = []
for cand in candidates:
    # Check if too close to an already selected candidate (e.g. < 0.005 deg ~ 500m)
    too_close = False
    for f_cand in filtered_candidates:
        d = math.sqrt((cand["lon"] - f_cand["lon"])**2 + (cand["lat"] - f_cand["lat"])**2)
        if d < 0.005:
            too_close = True
            break
    if not too_close:
        filtered_candidates.append(cand)
    if len(filtered_candidates) >= 5:
        break

# Delineate catchment for the top candidates
results = []
pixel_area_km2 = (30.0 * 30.0) / 1000000.0

for i, cand in enumerate(filtered_candidates):
    catch = grid.catchment(x=cand["lon"], y=cand["lat"], fdir=fdir, dirmap=dirmap, xytype='coordinate')
    catch_data = catch.astype(bool)
    
    area_km2 = float(np.sum(catch_data) * pixel_area_km2)
    catch_elev = dem[catch_data]
    mean_elev = float(catch_elev.mean()) if catch_elev.size > 0 else 0.0
    catch_slope = slope[catch_data]
    mean_slope = float(catch_slope.mean()) if catch_slope.size > 0 else 0.0
    
    touches_top = np.any(catch_data[0, :])
    touches_bottom = np.any(catch_data[-1, :])
    touches_left = np.any(catch_data[:, 0])
    touches_right = np.any(catch_data[:, -1])
    boundary_touch = bool(touches_top or touches_bottom or touches_left or touches_right)
    
    res = {
        "id": i + 1,
        "lon": cand["lon"],
        "lat": cand["lat"],
        "distance_deg": cand["dist"],
        "accumulation_cells": cand["acc"],
        "elevation_m": cand["elev"],
        "catchment_area_km2": area_km2,
        "mean_elevation_m": mean_elev,
        "mean_slope_deg": mean_slope,
        "touches_boundary": boundary_touch
    }
    results.append(res)

# Save candidates to GeoJSON
features = []
for res in results:
    pt = Point(res["lon"], res["lat"])
    features.append({
        "type": "Feature",
        "geometry": mapping(pt),
        "properties": res
    })

geojson_out = {
    "type": "FeatureCollection",
    "features": features
}
with open("data/processed/hydro/candidate_outlets.geojson", "w") as f:
    json.dump(geojson_out, f)

report = {
    "original_target": [lon, lat],
    "search_radius_deg": radius_deg,
    "candidates": results
}
with open("data/manifests/candidate_outlets_report.json", "w") as f:
    json.dump(report, f, indent=4)

print("Candidate analysis complete.")
