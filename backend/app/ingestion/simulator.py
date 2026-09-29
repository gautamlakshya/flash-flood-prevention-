import numpy as np
from datetime import datetime, timedelta

class SyntheticDataGenerator:
    """
    Generates deterministic synthetic time-series data based on a given scenario and seed.
    This provides reproducible, physically-coherent data for the pipeline when live APIs are unavailable.
    """
    def __init__(self, seed: int):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        
    def generate_rainfall(self, scenario: str, start_time: datetime, duration_hours: float = 6.0, interval_minutes: int = 15):
        """
        Generates a rainfall time series for a specified scenario.
        Returns a list of dictionaries with timestamp and rainfall_mm.
        """
        num_steps = int((duration_hours * 60) // interval_minutes)
        times = [start_time + timedelta(minutes=i*interval_minutes) for i in range(num_steps)]
        
        # Base patterns
        if scenario == "Extreme Cloudburst":
            # Sharp peak, extreme intensity
            base_curve = np.exp(-((np.linspace(-3, 3, num_steps) - 0.5) ** 2) / 0.5) * 80.0
            noise = self.rng.normal(0, 5, num_steps)
            rain_pattern = np.maximum(0, base_curve + noise)
            
        elif scenario == "Heavy Rainfall":
            # Sustained high intensity
            base_curve = np.sin(np.linspace(0, np.pi, num_steps)) * 30.0
            noise = self.rng.normal(0, 3, num_steps)
            rain_pattern = np.maximum(0, base_curve + noise)
            
        elif scenario == "Normal Rainfall":
            # Gentle, typical rain
            base_curve = np.sin(np.linspace(0, np.pi, num_steps)) * 5.0
            noise = self.rng.normal(0, 1, num_steps)
            rain_pattern = np.maximum(0, base_curve + noise)
            
        elif scenario == "Sustained Monsoon":
            # Continuous moderate-to-heavy
            base_curve = np.ones(num_steps) * 15.0
            noise = self.rng.normal(0, 4, num_steps)
            rain_pattern = np.maximum(0, base_curve + noise)
            
        elif scenario == "Upstream Tributary Surge":
            # Dry locally, meaning rainfall is 0, but upstream flow will be high
            rain_pattern = np.zeros(num_steps)
            
        else:
            # Default to normal
            rain_pattern = np.maximum(0, self.rng.normal(2, 1, num_steps))

        results = []
        cum_rain = 0.0
        for t, r in zip(times, rain_pattern):
            cum_rain += float(r)
            results.append({
                "timestamp": t.isoformat(),
                "station_id": "SYNTH-01",
                "rainfall_mm_15min": float(r),
                "cumulative_rainfall": cum_rain,
                "data_quality": "GOOD"
            })
            
        return results

    def get_amc_condition(self, scenario: str) -> int:
        """
        Determines Antecedent Moisture Condition (I, II, III).
        """
        if scenario in ["Extreme Cloudburst", "Sustained Monsoon", "Heavy Rainfall"]:
            return 3 # AMC III (Wet)
        elif scenario == "Normal Rainfall":
            return 2 # AMC II (Average)
        else:
            return 1 # AMC I (Dry)
