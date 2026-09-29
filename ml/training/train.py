import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from datetime import datetime, timedelta

from backend.app.routing.saint_venant import calculate_physics_loss, calculate_physics_residual, generate_synthetic_river_graph
from ml.models.stgnn import STGNN

from backend.app.ingestion.simulator import SyntheticDataGenerator
from backend.app.hydrology.runoff import process_runoff_timeseries

def generate_synthetic_dataset(num_samples=100, seq_len=12, num_nodes=5, num_features=4):
    """
    Generate physically consistent temporal sequences mimicking runoff and routing.
    Features per node: [rainfall, runoff, current_Q, slope]
    """
    X = np.zeros((num_samples, seq_len, num_nodes, num_features))
    Y = np.zeros((num_samples, num_nodes, 1)) # predict next Q
    
    nodes, edges, adj = generate_synthetic_river_graph()
    sim = SyntheticDataGenerator(seed=42)
    start_time = datetime.utcnow()
    
    for i in range(num_samples):
        # Vary scenario and AMC parameters, no arbitrary Q targets
        scenarios = ["Normal Rainfall", "Heavy Rainfall", "Extreme Cloudburst", "Sustained Monsoon"]
        scenario = np.random.choice(scenarios)
        rain_data = sim.generate_rainfall(scenario, start_time, duration_hours=seq_len * 0.25)
        amc = sim.get_amc_condition(scenario)
        
        # Calculate physical runoff per node
        node_runoff = {}
        for n in range(num_nodes):
            # Vary CN2 slightly per node
            cn2 = 75.0 + (n * 2.0)
            slope = nodes[n]["slope"]
            area = 50.0
            runoff_ts = process_runoff_timeseries(rain_data, cn2, slope, amc, area)
            node_runoff[n] = runoff_ts
            
        for t in range(seq_len):
            for n in range(num_nodes):
                obs = node_runoff[n][t]
                rain_t = obs["rainfall_mm"]
                runoff_volume = obs["runoff_volume_m3"]
                runoff_q = runoff_volume / 900.0 # m3/s (assuming 15 min timestep)
                
                # Physical routing: Q flows downstream (runoff + upstream Q + routed prev Q)
                if t == 0:
                    current_Q = runoff_q + 10.0 # baseflow
                else:
                    prev_Q = X[i, t-1, n, 2] * 1000.0
                    upstream_Q = X[i, t, n-1, 2] * 1000.0 if n > 0 else 0.0
                    current_Q = runoff_q + 0.8 * prev_Q + 0.5 * upstream_Q
                
                # Normalize features for STGNN stability
                X[i, t, n, 0] = rain_t / 100.0
                X[i, t, n, 1] = runoff_q / 1000.0
                X[i, t, n, 2] = current_Q / 1000.0
                X[i, t, n, 3] = nodes[n]["slope"]
                
        # Target Y is next Q (t = seq_len)
        for n in range(num_nodes):
            rain_next_data = sim.generate_rainfall(scenario, start_time, duration_hours=(seq_len+1) * 0.25)
            next_obs = process_runoff_timeseries(rain_next_data, 75.0 + (n*2.0), nodes[n]["slope"], amc, 50.0)[-1]
            runoff_next_q = next_obs["runoff_volume_m3"] / 900.0
            
            prev_Q = X[i, -1, n, 2] * 1000.0
            upstream_Q = Y[i, n-1, 0] * 1000.0 if n > 0 else 0.0
            target_Q = runoff_next_q + 0.8 * prev_Q + 0.5 * upstream_Q
            
            Y[i, n, 0] = target_Q / 1000.0
            
    return torch.tensor(X, dtype=torch.float32), torch.tensor(Y, dtype=torch.float32), torch.tensor(adj, dtype=torch.float32)

def train_model():
    print("Generating synthetic dataset...")
    num_samples = 200
    seq_len = 12
    num_nodes = 5
    num_features = 4
    
    X, Y, adj = generate_synthetic_dataset(num_samples, seq_len, num_nodes, num_features)
    
    # Split
    train_size = int(0.8 * num_samples)
    X_train, Y_train = X[:train_size], Y[:train_size]
    X_val, Y_val = X[train_size:], Y[train_size:]
    
    print("Initializing ST-GNN + GRU Model...")
    hidden_dim = 16
    horizon = 1
    
    model = STGNN(num_nodes, num_features, hidden_dim, horizon)
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    mse_loss = nn.MSELoss()
    
    lambda_physics = 0.1
    epochs = 50
    
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        
        # Forward pass
        y_pred = model(X_train, adj)
        
        # Data Loss
        data_loss = mse_loss(y_pred, Y_train)
        
        # Physics Loss (using the residual formulation)
        # simplified for training: A ~ Q^0.6, dx=1000, dt=900 (15m)
        # We compute residual over the predicted Q batch
        # Ensure y_pred is positive for fractional power to avoid NaN
        y_pred_real = y_pred * 1000.0
        A_pred = torch.relu(y_pred_real) ** 0.6
        A_prev = torch.relu(X_train[:, -1, :, 2:3] * 1000.0) ** 0.6 # Q at t-1
        
        dA_dt = (A_pred - A_prev) / 900.0
        
        # dQ_dx: (Q_n - Q_n-1) / dx
        # shift predicted Q downstream
        Q_upstream_real = torch.cat([torch.zeros(train_size, 1, 1), y_pred_real[:, :-1, :]], dim=1)
        dQ_dx = (y_pred_real - Q_upstream_real) / 1000.0
        
        q_lat = (X_train[:, -1, :, 1:2] * 1000.0) / 1000.0 # Runoff per unit length
        
        residual = dA_dt + dQ_dx - q_lat
        physics_loss = torch.mean(residual ** 2)
        
        total_loss = data_loss + lambda_physics * physics_loss
        
        total_loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1}/{epochs} - Data Loss: {data_loss.item():.4f} - Physics Loss: {physics_loss.item():.4f} - Total Loss: {total_loss.item():.4f}")
            
    print("Training complete.")
    
    os.makedirs("ml/checkpoints", exist_ok=True)
    torch.save(model.state_dict(), "ml/checkpoints/stgnn_model.pth")
    print("Model saved to ml/checkpoints/stgnn_model.pth")

if __name__ == "__main__":
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    train_model()
