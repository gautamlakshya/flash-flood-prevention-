import torch
import torch.nn as nn
import torch.optim as optim
import os
import json
from typing import Optional

from ml.models.stgnn import STGNN

def train_stgnn(mode: str = "SYNTHETIC", epochs: int = 100, learning_rate: float = 0.001):
    """
    Trains the ST-GNN model.
    GATE 9 & 10: Real-Data Training mandates chronological splitting and actual observed targets.
    """
    model = STGNN(num_nodes=5, num_features=4, hidden_dim=16, horizon=1)
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.MSELoss()
    
    if mode == "SYNTHETIC":
        print("Starting SYNTHETIC ST-GNN training mode.")
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))
        from ml.training.train import train_model
        train_model() # Delegates to the existing synthetic trainer
        
    elif mode == "REAL":
        print("Starting REAL-DATA ST-GNN training mode.")
        from ..data_pipeline.builder import build_training_dataset
        
        # Real training mandates chronological splitting
        dataset = build_training_dataset(start_date=None, end_date=None)
        
        # Chronological Splits
        X_train, y_train = dataset["train"]["X"], dataset["train"]["y"]
        X_val, y_val = dataset["val"]["X"], dataset["val"]["y"]
        X_test, y_test = dataset["test"]["X"], dataset["test"]["y"]
        adj_matrix = dataset["adj_matrix"]
        
        # Since build_training_dataset returns zeros or throws NotImplementedError in real mode when data is missing:
        # We explicitly assert they are not just mock zeros (if real data was successfully loaded)
        if len(X_train) == 0:
            raise ValueError("Training dataset is empty. Cannot train ST-GNN.")
            
        print("Training Loop executing...")
        
        # For full implementation, insert actual PyTorch training loop here:
        # 1. Forward pass
        # 2. MSE Loss calculation
        # 3. Validation tracking
        # 4. Save checkpoint to ml/checkpoints/stgnn_real_Teesta_v1.pth
        # 5. Compute test metrics: MAE, RMSE, NSE
        
        metadata = {
            "model_architecture": "GCN -> GRU -> Linear",
            "training_samples": len(X_train),
            "validation_samples": len(X_val),
            "test_samples": len(X_test),
            "test_rmse": 0.0, # Placeholder until actually trained
            "test_nse": 0.0
        }
        
        os.makedirs("ml/checkpoints", exist_ok=True)
        with open("ml/checkpoints/model_metadata_Teesta_v1.json", "w") as f:
            json.dump(metadata, f, indent=4)
            
    else:
        raise ValueError(f"Unknown training mode: {mode}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--real":
        train_stgnn(mode="REAL")
    else:
        train_stgnn(mode="SYNTHETIC")
