import os
import urllib.request
import gzip
import rasterio
import shutil
import hashlib

def download_and_verify(url, dest_dir, filename_base):
    gz_path = os.path.join(dest_dir, f"{filename_base}.gz")
    hgt_path = os.path.join(dest_dir, filename_base)

    print(f"Downloading from {url}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(gz_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        
        with gzip.open(gz_path, 'rb') as f_in:
            with open(hgt_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        with open(hgt_path, 'rb') as f:
            checksum = hashlib.md5(f.read()).hexdigest()
        
        with rasterio.open(hgt_path) as src:
            print(f"--- Metadata for {filename_base} ---")
            print(f"CRS: {src.crs}")
            print(f"Bounds: {src.bounds}")
            print(f"Resolution: {src.res}")
            print(f"Dimensions: {src.width}x{src.height}")
            print(f"NoData: {src.nodata}")
            print(f"Checksum: {checksum}")
            data = src.read(1)
            valid = data[data != src.nodata] if src.nodata is not None else data
            print(f"Min Elev: {valid.min()}")
            print(f"Max Elev: {valid.max()}")
            
    except Exception as e:
        print(f"Error: {e}")

os.makedirs("data/raw/dem/srtm", exist_ok=True)
download_and_verify("https://s3.amazonaws.com/elevation-tiles-prod/skadi/N27/N27E088.hgt.gz", "data/raw/dem/srtm", "N27E088.hgt")
download_and_verify("https://s3.amazonaws.com/elevation-tiles-prod/skadi/N28/N28E088.hgt.gz", "data/raw/dem/srtm", "N28E088.hgt")
