import rasterio
import numpy as np

file_path = "data/raw/dem/cdnh45w.tif"
with rasterio.open(file_path) as src:
    data = src.read(1)
    # Mask out NoData
    nodata = src.nodata
    if nodata is not None:
        valid_data = data[data != nodata]
    else:
        valid_data = data
        
    print(f"File: {file_path}")
    print(f"CRS: {src.crs}")
    print(f"Bounds: {src.bounds}")
    print(f"Resolution: {src.res}")
    print(f"Dimensions: Width={src.width}, Height={src.height}")
    print(f"NoData: {nodata}")
    if valid_data.size > 0:
        print(f"Min Elevation: {np.min(valid_data)}")
        print(f"Max Elevation: {np.max(valid_data)}")
    else:
        print("No valid elevation data found.")
