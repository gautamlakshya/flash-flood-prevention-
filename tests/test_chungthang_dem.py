import os
import pytest
import rasterio

def test_srtm_dem_files_exist():
    assert os.path.exists("data/raw/dem/srtm/N27E088.hgt"), "N27E088.hgt is missing"
    assert os.path.exists("data/raw/dem/srtm/N28E088.hgt"), "N28E088.hgt is missing"

def test_srtm_dem_metadata():
    with rasterio.open("data/raw/dem/srtm/N27E088.hgt") as src:
        assert src.crs == "EPSG:4326"
        assert src.width == 3601
        assert src.height == 3601
        assert src.bounds.left <= 88.6475 <= src.bounds.right
        assert src.bounds.bottom <= 27.6033 <= src.bounds.top

def test_srtm_dem_catchment_coverage():
    # Catchment expected to go up to 28+ latitude
    with rasterio.open("data/raw/dem/srtm/N28E088.hgt") as src:
        assert src.bounds.left <= 88.6475 <= src.bounds.right
        assert src.bounds.bottom <= 28.01 <= src.bounds.top
