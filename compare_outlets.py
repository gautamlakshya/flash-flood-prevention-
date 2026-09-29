import json
import yaml
import numpy as np
import rasterio
from pysheds.grid import Grid
import math

# Target definitions
targets = [
    {
        "name": "Candidate 5",
        "original_coord": (88.6562, 27.5934)
    },
    {
        "name": "CWC Chungthang Station",
        "original_coord": (88.6475, 27.5833)
    }
]

# Load grids
dem_path = "data/processed/dem/chungthang_srtm_conditioned.tif"
fdir_path = "data/processed/terrain/flow_direction.tif"
acc_path = "data/processed/terrain/flow_accumulation.tif"

grid = Grid.from_raster(dem_path)
dem = grid.read_raster(dem_path, nodata=-32768.0)
fdir = grid.read_raster(fdir_path)
acc = grid.read_raster(acc_path)
dirmap = (64, 128, 1, 2, 4, 8, 16, 32)

pixel_area_km2 = (30.0 * 30.0) / 1000000.0

# Define what constitutes the "mainstem" (e.g. > 1,000,000 cells ~ 900km2)
# Since the CWC area is ~2700 km2, the mainstem should have > 2,000,000 cells.
# We'll use 1,000,000 cells just to be safe.
mainstem_mask = acc > 1000000

results = []

for tgt in targets:
    lon, lat = tgt["original_coord"]
    
    # Snap to mask
    x_snap, y_snap = grid.snap_to_mask(mainstem_mask, (lon, lat), return_dist=False)
    
    # distance
    dist_deg = math.sqrt((x_snap - lon)**2 + (y_snap - lat)**2)
    dist_km = dist_deg * 111.0 # approx conversion
    
    # get acc
    col, row = ~grid.affine * (x_snap, y_snap)
    row, col = int(row), int(col)
    snapped_acc = float(acc[row, col])
    
    # delineate
    catch = grid.catchment(x=x_snap, y=y_snap, fdir=fdir, dirmap=dirmap, xytype='coordinate')
    catch_data = catch.astype(bool)
    
    area_km2 = float(np.sum(catch_data) * pixel_area_km2)
    
    touches_top = np.any(catch_data[0, :])
    touches_bottom = np.any(catch_data[-1, :])
    touches_left = np.any(catch_data[:, 0])
    touches_right = np.any(catch_data[:, -1])
    boundary_touch = bool(touches_top or touches_bottom or touches_left or touches_right)
    
    results.append({
        "Candidate": tgt["name"],
        "Original_coord": f"{lat}, {lon}",
        "Snapped_coord": f"{y_snap:.4f}, {x_snap:.4f}",
        "Snap_distance_km": f"{dist_km:.2f}",
        "Flow_accumulation": snapped_acc,
        "Catchment_km2": f"{area_km2:.2f}",
        "Boundary_touch": boundary_touch,
        "Mainstem_connectivity": True
    })

print(json.dumps(results, indent=2))
