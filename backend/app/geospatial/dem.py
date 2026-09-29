import numpy as np

def calculate_slope(elevation_grid: np.ndarray, cell_size_m: float) -> np.ndarray:
    y, x = np.gradient(elevation_grid, cell_size_m, cell_size_m)
    slope_rad = np.arctan(np.sqrt(x**2 + y**2))
    return np.degrees(slope_rad)

def generate_synthetic_dem(rows=50, cols=50, cell_size=30.0):
    """
    Generates a synthetic V-shaped valley with a downstream gradient.
    """
    dem = np.zeros((rows, cols))
    for i in range(rows):
        for j in range(cols):
            # Center stream at cols/2
            dist_to_stream = abs(j - cols/2)
            # Elevation increases away from stream (V-shape) and decreases downstream (along rows)
            elevation = 1000.0 + (dist_to_stream * 10.0) - (i * 5.0)
            dem[i, j] = max(0, elevation)
            
    # Add some noise, but ensure it is strictly deterministic geographically!
    # A given simulation environment must ALWAYS have the exact same DEM.
    np.random.seed(42)
    noise = np.random.normal(0, 1.0, (rows, cols))
    return dem + noise

def calculate_flow_accumulation(dem: np.ndarray):
    """
    Simplified flow accumulation simulation.
    Routes water to the lowest neighbor.
    """
    rows, cols = dem.shape
    accumulation = np.ones((rows, cols)) # Initial rain on every cell
    
    # Sort cells by elevation (highest first)
    flat_indices = np.argsort(dem, axis=None)[::-1]
    
    flow_dir = np.zeros((rows, cols), dtype=int)
    
    for idx in flat_indices:
        r, c = np.unravel_index(idx, (rows, cols))
        
        # Find lowest neighbor
        lowest_elev = dem[r, c]
        lowest_r, lowest_c = r, c
        
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0: continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if dem[nr, nc] < lowest_elev:
                        lowest_elev = dem[nr, nc]
                        lowest_r, lowest_c = nr, nc
                        
        if (lowest_r, lowest_c) != (r, c):
            accumulation[lowest_r, lowest_c] += accumulation[r, c]
            # simplified dir: 1 for downstream
            flow_dir[r, c] = 1 
            
    return flow_dir, accumulation

def process_dem(filepath: str = None):
    """
    Processes DEM. In DEMO mode, returns a synthetic valley.
    """
    # Always use synthetic for prototype if no real filepath is provided
    cell_size = 30.0 # meters
    dem = generate_synthetic_dem(50, 50, cell_size)
    slope = calculate_slope(dem, cell_size)
    flow_dir, flow_acc = calculate_flow_accumulation(dem)
    
    return {
        "elevation": dem,
        "slope": slope,
        "flow_direction": flow_dir,
        "flow_accumulation": flow_acc,
        "cell_size": cell_size
    }

def get_simulation_spatial_transform():
    import yaml
    import os
    from rasterio.transform import from_origin
    
    # Authoritative study-area configuration
    config_path = "config/study_area.yaml"
    
    # Fallback to 0,0 if not found, but it should be found
    lon, lat = 0.0, 0.0
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            study_config = yaml.safe_load(f)
            target = study_config.get("target", {})
            coords = target.get("target_coordinates", [0.0, 0.0])
            if len(coords) == 2:
                lon, lat = coords[0], coords[1]
    
    # We want the simulated grid to be roughly centered on the target coords.
    # The grid is 50x50 with cell_size=30m, which is small.
    # We'll use a fixed cell size in degrees (~0.0003 is roughly 30m).
    # To center a 50x50 grid at (lon, lat):
    # origin_lon = lon - (cols/2 * 0.0003) = lon - 25 * 0.0003 = lon - 0.0075
    # origin_lat = lat + (rows/2 * 0.0003) = lat + 25 * 0.0003 = lat + 0.0075
    
    origin_lon = lon - 0.0075
    origin_lat = lat + 0.0075
    
    return from_origin(origin_lon, origin_lat, 0.0003, 0.0003)

