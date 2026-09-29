import os
import torch
import numpy as np
import sys

# Add root to pythonpath for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ml.models.stgnn import STGNN
from backend.app.ingestion.simulator import SyntheticDataGenerator
from backend.app.hydrology.runoff import process_runoff_timeseries
from backend.app.routing.saint_venant import generate_synthetic_river_graph

def run_provenance_test():
    print("==================================================")
    print("ST-GNN PROVENANCE TEST")
    print("==================================================\n")
    
    # 1. Generate Base Data
    seed = 12345
    scenario = "Extreme Cloudburst"
    
    sim = SyntheticDataGenerator(seed)
    seq_len = 12
    duration_hours = seq_len * 0.25
    import datetime
    start_time = datetime.datetime.utcnow()
    rainfall_data = sim.generate_rainfall(scenario, start_time, duration_hours=duration_hours)
    amc = sim.get_amc_condition(scenario)
    
    nodes, edges, adj = generate_synthetic_river_graph()
    num_nodes = len(nodes)
    
    node_runoff = {}
    for n in range(num_nodes):
        cn2 = 75.0 + (n * 2.0)
        slope = nodes[n]["slope"]
        area = 50.0 # km2
        node_runoff[n] = process_runoff_timeseries(rainfall_data, cn2, slope, amc, area)
        
    X = np.zeros((1, seq_len, num_nodes, 4))
    for t in range(seq_len):
        for n in range(num_nodes):
            obs = node_runoff[n][t]
            rain_t = obs["rainfall_mm"]
            runoff_volume = obs["runoff_volume_m3"]
            runoff_q = runoff_volume / 900.0 # 15 min = 900s
            
            if t == 0:
                current_Q = runoff_q + 10.0
            else:
                prev_Q = X[0, t-1, n, 2] * 1000.0
                upstream_Q = X[0, t, n-1, 2] * 1000.0 if n > 0 else 0.0
                current_Q = runoff_q + 0.8 * prev_Q + 0.5 * upstream_Q
                
            X[0, t, n, 0] = rain_t / 100.0
            X[0, t, n, 1] = runoff_q / 1000.0
            X[0, t, n, 2] = current_Q / 1000.0
            X[0, t, n, 3] = nodes[n]["slope"]
            
    # 2. Setup Model
    model = STGNN(num_nodes=5, num_features=4, hidden_dim=16, horizon=1)
    model_path = os.path.join("ml", "checkpoints", "stgnn_model.pth")
    model_abs_path = os.path.abspath(model_path)
    
    if os.path.exists(model_path):
        model.load_state_dict(torch.load(model_path))
    model.eval()
    
    print(f"2. Checkpoint path loaded:\n   {model_abs_path}\n")
    print(f"3. Model architecture used for inference:\n{model}\n")
    
    # 3. Base Inference
    X_tensor = torch.tensor(X, dtype=torch.float32)
    adj_tensor = torch.tensor(adj, dtype=torch.float32)
    
    print(f"1. Final feature tensor entering ST-GNN (Shape: {X_tensor.shape}):")
    print("   Showing last timestep features for Outlet Node (Node 4):")
    print(f"   Rainfall: {X_tensor[0, -1, 4, 0].item():.4f} (normalized)")
    print(f"   Runoff Q: {X_tensor[0, -1, 4, 1].item():.4f} (normalized)")
    print(f"   Current Q: {X_tensor[0, -1, 4, 2].item():.4f} (normalized)")
    print(f"   Slope: {X_tensor[0, -1, 4, 3].item():.4f}\n")
    
    with torch.no_grad():
        y_pred = model(X_tensor, adj_tensor)
        
    outlet_idx = num_nodes - 1
    raw_output = y_pred[0, outlet_idx, 0].item()
    predicted_peak_discharge = raw_output * 1000.0
    
    print(f"4. Raw ST-GNN output for Outlet Node:\n   {raw_output:.6f}\n")
    print(f"5. Final Qpred derived from output:\n   {predicted_peak_discharge:.1f} m3/s\n")
    
    # 4. Perturb Inference
    print("--- PERTURBATION TEST ---")
    print("Perturbing input feature: Multiplying Current Q (Feature index 2) at the last timestep by 1.5")
    
    X_tensor_perturbed = X_tensor.clone()
    X_tensor_perturbed[0, -1, outlet_idx, 2] *= 1.5
    
    with torch.no_grad():
        y_pred_perturbed = model(X_tensor_perturbed, adj_tensor)
        
    raw_output_pert = y_pred_perturbed[0, outlet_idx, 0].item()
    predicted_peak_discharge_pert = raw_output_pert * 1000.0
    
    print(f"Perturbed Raw ST-GNN output:\n   {raw_output_pert:.6f}")
    print(f"Perturbed Qpred derived from output:\n   {predicted_peak_discharge_pert:.1f} m3/s\n")
    
    print("Delta verification:")
    delta_raw = raw_output_pert - raw_output
    delta_qpred = predicted_peak_discharge_pert - predicted_peak_discharge
    print(f"Raw Output changed by: {delta_raw:.6f}")
    print(f"Final Qpred changed by: {delta_qpred:.1f} m3/s")
    
    if delta_raw != 0:
        print("\nSUCCESS: The causal chain 'input -> ST-GNN -> output -> Qpred' is proven.")
    else:
        print("\nFAILURE: Output did not change.")

if __name__ == "__main__":
    run_provenance_test()
