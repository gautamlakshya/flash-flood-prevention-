import time
import requests
import json
import urllib.parse

def run_scenario(scenario_name):
    print(f"\n=============================================")
    print(f"RUNNING SCENARIO: {scenario_name}")
    print(f"=============================================")
    try:
        # Start simulation
        url = f"http://localhost:8000/api/v1/simulation/start?scenario={urllib.parse.quote(scenario_name)}"
        res = requests.post(url)
        res.raise_for_status()
        data = res.json()
        run_id = data['run_id']
        print(f"Simulation started. Run ID: {run_id}")
        
        # Poll status
        while True:
            time.sleep(1)
            status_res = requests.get(f'http://localhost:8000/api/v1/simulation/{run_id}/status')
            status_data = status_res.json()
            status = status_data['status']
            
            if status in ['COMPLETED', 'FAILED']:
                break
                
        if status == 'COMPLETED':
            # Get results
            results_res = requests.get(f'http://localhost:8000/api/v1/simulation/{run_id}/results')
            results_data = results_res.json()
            
            print("\n--- RESULTS ---")
            metrics = results_data['metrics']
            print(f"Rainfall (Total): {sum([x['rainfall_mm'] for x in results_data['timeseries']]):.1f} mm")
            print(f"AMC: {metrics['amc']}")
            print(f"Runoff (Peak Volume): {metrics['peak_runoff_volume']:.1f} m3")
            print(f"Qpred (from ST-GNN): {metrics['predicted_discharge']:.1f} m3/s")
            print(f"Qcrit (from hydraulic parameters): {metrics['qcrit']:.1f} m3/s")
            print(f"dQ/dt (calculated from hydrograph): {metrics.get('dq_dt', 0):.4f} m3/s2")
            print(f"Hazard Level: {metrics['hazard']}")
            print(f"Manning Stage (Water Depth): {metrics['stage_m']:.2f} m")
            print(f"Flooded Cell Count (from DEM): {metrics.get('flooded_cells', 0)}")
            
            inundation = results_data.get('inundation_geojson', {})
            features = inundation.get('features', [])
            print(f"Inundation Polygon Count: {len(features)}")
            
            cap = results_data.get('cap_xml', '')
            print(f"CAP Alert Generated: {'Yes' if cap else 'No'}")
            
            return results_data
        else:
            print("Simulation failed.")
            return None
            
    except Exception as e:
        print(f"Test failed: {e}")
        return None

if __name__ == "__main__":
    run_scenario("Normal Monsoon")
    run_scenario("Extreme Cloudburst")
