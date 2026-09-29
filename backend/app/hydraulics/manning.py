def calculate_water_stage(discharge: float, manning_n: float, slope: float, bottom_width: float, side_slope: float = 1.0) -> float:
    """
    Estimates water stage (depth) using Manning's equation for a trapezoidal channel.
    Q = (1/n) * A * R^(2/3) * S^(1/2)
    This requires iterative solving in reality, but we use a simplified approximation for the demo
    or a numerical solver.
    """
    if discharge <= 0:
        return 0.0
    if slope <= 0 or manning_n <= 0:
        raise ValueError("Slope and Manning's n must be positive")
    
    # We will use a simple fixed-point iteration or Newton-Raphson to solve for depth y.
    # A = y * (bottom_width + side_slope * y)
    # P = bottom_width + 2 * y * sqrt(1 + side_slope**2)
    # R = A / P
    # f(y) = A * R^(2/3) - Q * n / sqrt(S) = 0
    
    target = (discharge * manning_n) / (slope ** 0.5)
    
    y = 1.0 # initial guess
    tolerance = 1e-4
    max_iter = 100
    
    for _ in range(max_iter):
        A = y * (bottom_width + side_slope * y)
        P = bottom_width + 2 * y * ((1 + side_slope**2)**0.5)
        R = A / P
        
        # Current flow capacity factor
        K = A * (R ** (2/3))
        
        error = K - target
        if abs(error) < tolerance:
            break
            
        # Numerical derivative df/dy
        dy = 1e-5
        y_plus = y + dy
        A_plus = y_plus * (bottom_width + side_slope * y_plus)
        P_plus = bottom_width + 2 * y_plus * ((1 + side_slope**2)**0.5)
        R_plus = A_plus / P_plus
        K_plus = A_plus * (R_plus ** (2/3))
        
        df_dy = (K_plus - K) / dy
        
        if df_dy == 0:
            break
            
        y = y - error / df_dy
        
        if y <= 0:
            y = 0.01 # prevent negative depth
            
    return y
