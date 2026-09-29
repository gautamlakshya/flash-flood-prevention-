import json
import os
import numpy as np
from typing import Dict, Any

class FeatureScaler:
    """
    GATE 8: Explicit mathematical scaling.
    Replaces arbitrary *1000 or /100.
    """
    def __init__(self, name: str):
        self.name = name
        self.min_val = 0.0
        self.max_val = 1.0
        self.fitted = False

    def fit(self, data: np.ndarray):
        self.min_val = float(np.min(data))
        self.max_val = float(np.max(data))
        if self.max_val == self.min_val:
            self.max_val = self.min_val + 1.0 # Avoid division by zero
        self.fitted = True

    def transform(self, data: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise ValueError(f"Scaler {self.name} not fitted.")
        return (data - self.min_val) / (self.max_val - self.min_val)

    def inverse_transform(self, scaled_data: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise ValueError(f"Scaler {self.name} not fitted.")
        return (scaled_data * (self.max_val - self.min_val)) + self.min_val

class STGNNScalerRegistry:
    def __init__(self, study_area: str = "Teesta"):
        self.study_area = study_area
        self.scalers = {
            "rainfall": FeatureScaler("rainfall"),
            "runoff": FeatureScaler("runoff"),
            "discharge": FeatureScaler("discharge"),
            "slope": FeatureScaler("slope")
        }

    def save(self, filepath: str = None):
        if filepath is None:
            filepath = f"ml/checkpoints/scaler_{self.study_area}_v1.json"
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = {name: {"min": s.min_val, "max": s.max_val, "fitted": s.fitted} for name, s in self.scalers.items()}
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)

    def load(self, filepath: str = None):
        if filepath is None:
            filepath = f"ml/checkpoints/scaler_{self.study_area}_v1.json"
            
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Scaler configuration not found at {filepath}")
            
        with open(filepath, "r") as f:
            data = json.load(f)
            
        for name, props in data.items():
            if name in self.scalers:
                self.scalers[name].min_val = props["min"]
                self.scalers[name].max_val = props["max"]
                self.scalers[name].fitted = props["fitted"]
