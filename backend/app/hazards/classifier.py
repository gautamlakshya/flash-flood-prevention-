def classify_hazard(q_pred: float, q_crit: float, q_trend: float) -> str:
    """
    Classify flash flood hazard based on bankfull capacity (q_crit).
    
    Qpred < 0.7 Qcrit
        -> NORMAL
    0.7 Qcrit <= Qpred < Qcrit
        -> WATCH
    Qpred >= Qcrit AND dQ/dt > 0
        -> FLASH FLOOD WARNING
    """
    if q_crit <= 0:
        return "UNKNOWN"
        
    ratio = q_pred / q_crit
    
    if ratio < 0.7:
        return "NORMAL"
    elif 0.7 <= ratio < 1.0:
        return "WATCH"
    else:
        # ratio >= 1.0
        if q_trend > 0:
            return "FLASH FLOOD WARNING"
        else:
            return "WATCH" # Over capacity but falling, maybe "WARNING" or "WATCH", sticking to WATCH per spec. 
            # Note: The spec says "Qpred >= Qcrit AND dQ/dt > 0 -> FLASH FLOOD WARNING"
