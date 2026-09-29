import numpy as np

def calculate_physics_residual(
    A_t: np.ndarray, A_prev: np.ndarray, 
    Q: np.ndarray, Q_prev_node: np.ndarray, 
    q_lat: np.ndarray, 
    dx: float, dt: float
) -> np.ndarray:
    """
    Calculates the 1D Saint-Venant mass continuity residual:
    dA/dt + dQ/dx - q_lat = 0
    
    A_t: Cross-sectional area at current timestep (per node)
    A_prev: Cross-sectional area at previous timestep (per node)
    Q: Discharge at current node
    Q_prev_node: Discharge at upstream node(s) entering this node
    q_lat: Lateral inflow (runoff) per unit length
    dx: Reach length
    dt: Timestep duration in seconds
    """
    # Time derivative of Area
    dA_dt = (A_t - A_prev) / dt
    
    # Spatial derivative of Discharge (simplified upstream finite difference)
    dQ_dx = (Q - Q_prev_node) / dx
    
    # Residual
    residual = dA_dt + dQ_dx - q_lat
    return residual

def calculate_physics_loss(residual: np.ndarray) -> float:
    """
    Mean Squared Error of the physics residual.
    """
    return np.mean(residual ** 2)

def generate_synthetic_river_graph():
    """
    Generates a simple synthetic river graph matching the V-shaped valley DEM.
    Returns nodes, edges, and a normalized adjacency matrix.
    """
    # Let's assume a main channel with 5 nodes
    num_nodes = 5
    nodes = []
    edges = []
    adj_matrix = np.zeros((num_nodes, num_nodes))
    
    for i in range(num_nodes):
        # Explicit synthetic hydraulic cross-section parameters
        channel_width = 15.0 + (i * 2.0)
        bankfull_depth = 2.0 + (i * 0.5)
        bed_slope = 0.05
        manning_n = 0.035
        
        # Hydraulic calculation using Manning's Equation for a rectangular channel
        # Q = (1/n) * A * R^(2/3) * S^(1/2)
        # R (Hydraulic radius) = A / P = (w*d) / (w + 2d)
        area = channel_width * bankfull_depth
        wetted_perimeter = channel_width + (2 * bankfull_depth)
        r_h = area / wetted_perimeter
        bankfull_capacity = (1.0 / manning_n) * area * (r_h**(2.0/3.0)) * (bed_slope**0.5)

        nodes.append({
            "id": f"NODE-{i}",
            "elevation": 1000 - (i * 10),
            "slope": bed_slope,
            "width": channel_width,
            "bankfull_depth": bankfull_depth,
            "bankfull_capacity": float(bankfull_capacity),
            "cross_section_area": area,
            "manning_n": manning_n
        })
        if i > 0:
            edges.append({
                "upstream": f"NODE-{i-1}",
                "downstream": f"NODE-{i}",
                "length_m": 1000.0
            })
            adj_matrix[i-1, i] = 1.0 # Directed flow
            
    # Add self loops
    np.fill_diagonal(adj_matrix, 1.0)
    
    # Normalize adjacency
    rowsum = adj_matrix.sum(1)
    d_inv = np.power(rowsum, -1).flatten()
    d_inv[np.isinf(d_inv)] = 0.
    d_mat_inv = np.diag(d_inv)
    adj_normalized = d_mat_inv.dot(adj_matrix)
    
    return nodes, edges, adj_normalized
