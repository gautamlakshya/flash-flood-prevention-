import torch
import torch.nn as nn

class GCNLayer(nn.Module):
    def __init__(self, in_features, out_features):
        super(GCNLayer, self).__init__()
        self.linear = nn.Linear(in_features, out_features)

    def forward(self, x, adj):
        """
        x: (batch_size, num_nodes, in_features)
        adj: (num_nodes, num_nodes) - normalized adjacency matrix
        """
        # Linear transformation
        out = self.linear(x) # (batch_size, num_nodes, out_features)
        # Message passing: multiply by adjacency matrix
        # out is (batch, nodes, features), adj is (nodes, nodes)
        # We need (batch, nodes, features) = torch.matmul(adj, out)
        out = torch.matmul(adj, out)
        return torch.relu(out)

class STGNN(nn.Module):
    def __init__(self, num_nodes, num_features, hidden_dim, horizon=1):
        super(STGNN, self).__init__()
        self.num_nodes = num_nodes
        self.hidden_dim = hidden_dim
        self.horizon = horizon
        
        # Spatial Graph Convolutions
        self.gcn1 = GCNLayer(num_features, hidden_dim)
        self.gcn2 = GCNLayer(hidden_dim, hidden_dim)
        
        # Temporal GRU
        # GRU expects input of shape (batch, seq_len, features)
        self.gru = nn.GRU(hidden_dim, hidden_dim, batch_first=True)
        
        # Final prediction head
        self.linear = nn.Linear(hidden_dim, horizon)

    def forward(self, x, adj):
        """
        x: (batch_size, seq_len, num_nodes, num_features)
        adj: (num_nodes, num_nodes)
        Returns: (batch_size, num_nodes, horizon)
        """
        batch_size, seq_len, num_nodes, num_features = x.shape
        
        # Reshape to process all timesteps through GCN
        # (batch_size * seq_len, num_nodes, num_features)
        x_reshaped = x.view(batch_size * seq_len, num_nodes, num_features)
        
        # Spatial feature extraction
        h = self.gcn1(x_reshaped, adj)
        h = self.gcn2(h, adj) # (batch*seq_len, num_nodes, hidden_dim)
        
        # Reshape for GRU: (batch_size, seq_len, num_nodes, hidden_dim)
        h = h.view(batch_size, seq_len, num_nodes, self.hidden_dim)
        
        # We need to run GRU for each node independently over time
        # Permute to (batch_size * num_nodes, seq_len, hidden_dim)
        h_gru_in = h.permute(0, 2, 1, 3).contiguous().view(-1, seq_len, self.hidden_dim)
        
        out, _ = self.gru(h_gru_in) # out: (batch*nodes, seq_len, hidden_dim)
        
        # Take the output of the last timestep
        last_out = out[:, -1, :] # (batch*nodes, hidden_dim)
        
        # Prediction
        pred = self.linear(last_out) # (batch*nodes, horizon)
        
        # Physical Skip Connection: add the last known Q (feature index 2)
        q_last = x[:, -1, :, 2].contiguous().view(-1, 1)
        pred = pred + q_last
        
        # Reshape back to (batch_size, num_nodes, horizon)
        return pred.view(batch_size, num_nodes, self.horizon)
