# ST-GNN Training Protocol (Real Data)

## Real Training Constraints
- **Target Variable:** The model is trained exclusively to predict the actual CWC-observed discharge target (`y`), not an algebraic substitution.
- **Chronological Split:** The train, validation, and test datasets are split purely by chronological date (e.g., Train: 2018-2020, Val: 2021). Random shuffling (`train_test_split(shuffle=True)`) is strictly forbidden to prevent temporal data leakage.
- **Current Status:** **BLOCKED - REAL DATA REQUIRED**. The training module evaluates the `data/raw/` directory and aborts execution due to the absence of the Teesta hydrometeorological dataset.

## Metric Evaluation
Only the held-out Chronological Test Set is used to calculate:
- RMSE (Root Mean Squared Error)
- MAE (Mean Absolute Error)
- NSE (Nash-Sutcliffe Efficiency)
