import torch
import os
from models.stgnn import STGNN

def export_model():
    num_node_features = 5 # e.g. elevation, slope, Qsurf, rainfall, previous_Q
    hidden_dim = 16
    horizon = 1 # 1-step prediction for simplicity
    
    model = STGNN(num_node_features, hidden_dim, horizon)
    model.eval()
    
    # Dummy inputs for tracing
    # Let's say we have 10 river nodes
    num_nodes = 10
    x = torch.randn((num_nodes, num_node_features))
    
    # Fully connected graph for dummy
    edge_index = torch.tensor([[i, j] for i in range(num_nodes) for j in range(num_nodes)]).t().contiguous()
    
    export_path = "checkpoints/stgnn_demo.onnx"
    os.makedirs(os.path.dirname(export_path), exist_ok=True)
    
    torch.onnx.export(
        model, 
        (x, edge_index),
        export_path,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=['x', 'edge_index'],
        output_names=['q_pred'],
        dynamic_axes={
            'x': {0: 'num_nodes'},
            'edge_index': {1: 'num_edges'},
            'q_pred': {0: 'num_nodes'}
        }
    )
    print(f"Exported ONNX model to {export_path}")

if __name__ == "__main__":
    export_model()
