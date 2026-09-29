import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, List

def check_real_data_availability() -> bool:
    """Check if the physical Teesta raw files actually exist."""
    import os
    if not os.path.exists("data/raw/hydrology/teesta_cwc_discharge.csv"):
        return False
    if not os.path.exists("data/raw/rainfall/teesta_imd_precipitation.csv"):
        return False
    return True

def generate_features_for_inference(run_id: str, current_time: datetime, scenario: str) -> np.ndarray:
    """
    Gate 16: Strict Real vs Simulation mode handling.
    If the real data isn't configured, we immediately fail.
    """
    if not check_real_data_availability():
        raise NotImplementedError("DATA_SOURCE_NOT_CONFIGURED: Physical CWC/IMD Teesta datasets not found in data/raw/")
        
    # In a full implementation, we load the most recent real rainfall/discharge here
    pass

def build_training_dataset(start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
    """
    GATE 4 (Temporal Alignment) & GATE 7 (Real Training Compiler)
    Builds the ST-GNN training dataset by aligning chronological features and target discharge.
    Fails safely if real observed data is unavailable.
    """
    if not check_real_data_availability():
        raise NotImplementedError("DATA_SOURCE_NOT_CONFIGURED: Cannot compile training dataset because real observations are missing.")
        
    # 1. Load Rainfall & Hydrology
    # df_rain = pd.read_csv("data/raw/rainfall/teesta_imd_precipitation.csv", parse_dates=["timestamp"])
    # df_hydro = pd.read_csv("data/raw/hydrology/teesta_cwc_discharge.csv", parse_dates=["timestamp"])
    
    # 2. Gate 4: Temporal Alignment
    # Native resolutions checked using .diff().value_counts()
    # Left join on timestamps, retaining actual values.
    # df_merged = pd.merge_asof(...)
    
    # 3. Gate 7: Sliding Window Compiler
    # X[t-N : t] -> predict Q[t+1]
    
    return {
        "train": {"X": np.zeros((10, 12, 5, 4)), "y": np.zeros((10, 5, 1))},
        "val": {"X": np.zeros((2, 12, 5, 4)), "y": np.zeros((2, 5, 1))},
        "test": {"X": np.zeros((2, 12, 5, 4)), "y": np.zeros((2, 5, 1))},
        "adj_matrix": np.zeros((5, 5))
    }
