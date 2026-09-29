# Chungthang Flash Flood Early Warning System (FFEWS) Data Requirements

## Overview
This document specifies the exact dataset parameters required to transition the FFEWS prototype into operational capability for the Chungthang, Sikkim region.

* **Target Location:** Chungthang, Sikkim (Approximate coord: 27.6033° N, 88.6475° E)
* **Model Domain:** Upstream Teesta contributing catchment
* **Impact Domain:** Chungthang settlement and local downstream corridor

**CRITICAL RULE:** No simulated data will be accepted into the REAL pipeline. 

## 1. Digital Elevation Model (DEM)
* **Description:** Topographic foundation for river extraction, catchment boundary delineation, and 2D flood inundation generation.
* **Source:** CartoDEM (NRSC/ISRO) or SRTM/ALOS-PALSAR
* **Format:** GeoTIFF (.tif)
* **Spatial Resolution:** 30m or better (10m CartoDEM preferred)
* **Temporal Resolution:** Static (latest available epoch)
* **Expected Location:** `data/raw/dem/teesta_cartodem.tif`
* **REAL Status:** **NOT_CONFIGURED**

## 2. Rainfall Observations
* **Description:** Continuous precipitation data for hydrological runoff computation (SCS-CN model input).
* **Source:** Indian Meteorological Department (IMD) Automatic Weather Stations (AWS) or GPM IMERG (satellite-derived)
* **Format:** CSV or NetCDF
* **Spatial Resolution:** Point-based stations mapping to Chungthang catchment area, or gridded raster (0.1° x 0.1°)
* **Temporal Resolution:** 15-minute or 1-hour cadence
* **Units:** mm/hr
* **Expected Location:** `data/raw/rainfall/teesta_imd_precipitation.csv`
* **REAL Status:** **NOT_CONFIGURED**

## 3. Hydrological Observations
* **Description:** Observed streamflow and stage (water level) used as the true target variable for ST-GNN training and critical threshold (Qcrit) calibration.
* **Source:** Central Water Commission (CWC) or NHPC Dam Telemetry
* **Format:** CSV
* **Temporal Resolution:** 15-minute or 1-hour cadence matching rainfall
* **Units:** Discharge (m³/s), Stage (m)
* **Expected Location:** `data/raw/hydrology/teesta_cwc_discharge.csv`
* **REAL Status:** **NOT_CONFIGURED**

## 4. Channel Geometry & Cross Sections
* **Description:** Physical properties of the Teesta River bed at Chungthang to determine hydraulic capacity (Qcrit) and accurately convert discharge to stage using Manning's equation.
* **Source:** Bathymetric surveys, CWC field reports, or high-res DEM extraction
* **Format:** CSV (Tabular geometry profiles)
* **Required Columns:** Node ID, Bankfull Capacity (m³/s), Manning's n, Slope (m/m), Channel Width (m), Bottom Elevation (m)
* **Expected Location:** `data/raw/static/cross_sections.csv`
* **REAL Status:** **NOT_CONFIGURED**

## 5. Land Use / Land Cover (LULC)
* **Description:** Land cover classification to derive Curve Number (CN) values for the rainfall-runoff model.
* **Source:** Bhuvan (NRSC) LULC 
* **Format:** GeoTIFF or Shapefile
* **Spatial Resolution:** 50m or 30m
* **Expected Location:** `data/raw/static/lulc.tif`
* **REAL Status:** **NOT_CONFIGURED**

## 6. Hydrologic Soil Groups (HSG)
* **Description:** Soil permeability classification (A, B, C, D) critical for SCS-CN computations.
* **Source:** NBSS&LUP or Harmonized World Soil Database (HWSD)
* **Format:** GeoTIFF or Shapefile
* **Expected Location:** `data/raw/static/soil_groups.tif`
* **REAL Status:** **NOT_CONFIGURED**

## 7. Landslide Inventory (Optional/Contextual)
* **Description:** Historical landslide polygons to determine cascading hazard risks (e.g. LLOF - Landslide Lake Outburst Floods) intersecting with flash floods.
* **Source:** GSI Bhukosh
* **Format:** GeoJSON or Shapefile
* **Expected Location:** `data/raw/landslides/gsi_landslides.geojson`
* **REAL Status:** **NOT_CONFIGURED**
