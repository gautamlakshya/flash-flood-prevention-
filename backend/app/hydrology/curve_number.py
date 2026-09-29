import numpy as np

def calculate_cn2_alpha(cn2: float, slope_degrees: float) -> float:
    """
    Calculates slope-adjusted Curve Number.
    Equation: CN2_alpha = CN2 * ((322.79 + 15.63 * alpha) / (alpha + 323.52))
    """
    if slope_degrees < 0:
        raise ValueError("Slope cannot be negative")
    
    alpha = slope_degrees
    multiplier = (322.79 + 15.63 * alpha) / (alpha + 323.52)
    cn2_alpha = cn2 * multiplier
    
    # Cap at 100
    return min(cn2_alpha, 100.0)

def calculate_retention(cn: float) -> float:
    """
    Calculates potential maximum retention (S) in mm.
    S = 25400 / CN - 254
    """
    if cn <= 0:
        return float('inf') # Infinite retention
    return (25400.0 / cn) - 254.0

def calculate_runoff_depth(rainfall_mm: float, s_mm: float) -> float:
    """
    Calculates surface runoff depth (Q_surf) in mm.
    Q_surf = (P - 0.2S)^2 / (P + 0.8S) for P > 0.2S
    """
    if rainfall_mm > 0.2 * s_mm:
        return ((rainfall_mm - 0.2 * s_mm) ** 2) / (rainfall_mm + 0.8 * s_mm)
    return 0.0

def adjust_amc(cn2: float, amc_class: str) -> float:
    """
    Adjusts CN2 based on Antecedent Moisture Condition.
    AMC I: Dry
    AMC II: Normal
    AMC III: Wet
    """
    if amc_class == "AMC I":
        cn1 = cn2 / (2.281 - 0.01281 * cn2)
        return min(max(cn1, 0), 100)
    elif amc_class == "AMC III":
        cn3 = cn2 / (0.427 + 0.00573 * cn2)
        return min(max(cn3, 0), 100)
    return cn2 # AMC II
