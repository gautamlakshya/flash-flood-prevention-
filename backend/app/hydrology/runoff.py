from typing import List, Dict

def calculate_slope_adjusted_cn(cn2: float, slope_degrees: float) -> float:
    """
    Adjusts the Curve Number based on slope using the equation:
    CN2a = CN2 * [(322.79 + 15.63a) / (a + 323.52)]
    """
    if slope_degrees <= 0:
        return cn2
    adjusted = cn2 * ((322.79 + 15.63 * slope_degrees) / (slope_degrees + 323.52))
    return min(100.0, adjusted)

def adjust_cn_for_amc(cn2: float, amc_class: int) -> float:
    """
    Adjusts CN2 for Antecedent Moisture Condition (AMC).
    AMC I (Dry), AMC II (Normal), AMC III (Wet)
    """
    if amc_class == 1:
        return (4.2 * cn2) / (10 - 0.058 * cn2)
    elif amc_class == 3:
        return (23 * cn2) / (10 + 0.13 * cn2)
    return cn2 # Default to AMC II

def calculate_retention(cn: float) -> float:
    """
    Calculates potential maximum retention S in mm.
    S = (25400 / CN) - 254
    """
    if cn <= 0:
        return float('inf')
    return (25400.0 / cn) - 254.0

def calculate_runoff_depth(rainfall_mm: float, s_mm: float) -> float:
    """
    Calculates surface runoff depth using SCS-CN.
    If P > 0.2S: Q = (P - 0.2S)^2 / (P + 0.8S)
    else Q = 0
    """
    ia = 0.2 * s_mm
    if rainfall_mm > ia:
        return ((rainfall_mm - ia) ** 2) / (rainfall_mm + 0.8 * s_mm)
    return 0.0

def process_runoff_timeseries(rainfall_data: List[Dict], cn2: float, slope_deg: float, amc: int, catchment_area_km2: float) -> List[Dict]:
    """
    Takes a time-series of rainfall dictionaries and calculates the resulting runoff depth and volume over time.
    """
    cn2_slope = calculate_slope_adjusted_cn(cn2, slope_deg)
    final_cn = adjust_cn_for_amc(cn2_slope, amc)
    s_mm = calculate_retention(final_cn)
    
    results = []
    for obs in rainfall_data:
        p = obs["cumulative_rainfall"]
        total_q = calculate_runoff_depth(p, s_mm)
        
        # Calculate volume in cubic meters (depth in mm * area in km2 * 1000)
        volume_m3 = total_q * catchment_area_km2 * 1000.0
        
        results.append({
            "timestamp": obs["timestamp"],
            "rainfall_mm": obs["rainfall_mm_15min"],
            "cumulative_rainfall": p,
            "runoff_mm": total_q,
            "runoff_volume_m3": volume_m3,
            "cn": final_cn,
            "s_mm": s_mm
        })
        
    return results
