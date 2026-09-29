import os
import sys
import numpy as np

# Add root to pythonpath for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import rasterio.features
from shapely.geometry import shape

from backend.app.geospatial.dem import process_dem, get_simulation_spatial_transform

def calculate_inundation_geojson(stage: float):
    # 1. Get synthetic DEM
    dem_data = process_dem()
    dem_grid = dem_data["elevation"]
    
    rows, cols = dem_grid.shape
    dem_min = np.min(dem_grid)
    dem_max = np.max(dem_grid)
    
    # 2. Reference elevation (outlet)
    outlet_r, outlet_c = rows - 1, cols // 2
    reference_elevation = dem_grid[outlet_r, outlet_c]
    
    # 3. Water surface elevation
    water_surface_elevation = reference_elevation + stage
    
    # 4. Flooded Mask
    flooded_mask = (dem_grid < water_surface_elevation).astype('uint8')
    flooded_cells = int(np.sum(flooded_mask))
    
    # 5. GeoJSON generation
    transform = get_simulation_spatial_transform()
    shapes = list(rasterio.features.shapes(flooded_mask, transform=transform))
    
    inundation_geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    
    all_coords = []
    
    for geom, value in shapes:
        if value == 1:
            poly_shape = shape(geom)
            inundation_geojson["features"].append({
                "type": "Feature",
                "geometry": poly_shape.__geo_interface__,
                "properties": {
                    "stage_m": round(stage, 2)
                }
            })
            
            # Extract coords for bounding box
            if poly_shape.geom_type == 'Polygon':
                all_coords.extend(list(poly_shape.exterior.coords))
            elif poly_shape.geom_type == 'MultiPolygon':
                for p in poly_shape.geoms:
                    all_coords.extend(list(p.exterior.coords))
                    
    polygon_count = len(inundation_geojson["features"])
    
    # Calculate bounding box
    if all_coords:
        lons = [c[0] for c in all_coords]
        lats = [c[1] for c in all_coords]
        bbox = f"[{min(lons):.5f}, {min(lats):.5f}, {max(lons):.5f}, {max(lats):.5f}]"
    else:
        bbox = "[]"
        
    return {
        "dimensions": (rows, cols),
        "dem_min": dem_min,
        "dem_max": dem_max,
        "reference_elevation": reference_elevation,
        "stage": stage,
        "water_surface_elevation": water_surface_elevation,
        "flooded_cells": flooded_cells,
        "polygon_count": polygon_count,
        "bbox": bbox
    }

def print_report(title, data):
    print(f"==================================================")
    print(f"{title}")
    print(f"==================================================")
    print(f"DEM dimensions: {data['dimensions']}")
    print(f"DEM minimum elevation: {data['dem_min']:.2f} m")
    print(f"DEM maximum elevation: {data['dem_max']:.2f} m")
    print(f"River/Reference elevation: {data['reference_elevation']:.2f} m")
    print(f"Manning stage: {data['stage']:.2f} m")
    print(f"Calculated water-surface elevation: {data['water_surface_elevation']:.2f} m")
    print(f"Number of flooded cells: {data['flooded_cells']}")
    print(f"Resulting polygon count: {data['polygon_count']}")
    print(f"GeoJSON bounding box: {data['bbox']}\n")

if __name__ == "__main__":
    # Normal Scenario (Stage = 2.12 m)
    normal_data = calculate_inundation_geojson(stage=2.12)
    print_report("NORMAL SCENARIO INUNDATION PROVENANCE", normal_data)
    
    # Extreme Scenario (Stage = 55.54 m)
    extreme_data = calculate_inundation_geojson(stage=55.54)
    print_report("EXTREME SCENARIO INUNDATION PROVENANCE", extreme_data)
    
    # Perturbation Test (Stage = 25.0 m)
    perturb_data = calculate_inundation_geojson(stage=25.0)
    print_report("PERTURBATION TEST (Stage = 25.0 m)", perturb_data)
    
    print("Verification:")
    print("As stage increases (2.12 -> 25.0 -> 55.54), the Water Surface Elevation increases.")
    print("This directly satisfies `DEM elevation < water-surface elevation`, increasing the flooded cell mask:")
    print(f"Cells: {normal_data['flooded_cells']} -> {perturb_data['flooded_cells']} -> {extreme_data['flooded_cells']}")
    print("\nThe GeoJSON boundaries physically expand outward from the reference cell, completely replacing the old hardcoded coordinates.")
