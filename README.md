# NBA Stats Predictor

Predicts NBA player stats (points, rebounds, assists) using engineered features
and gradient-boosted trees (XGBoost, Random Forest).

## Architecture
- Layer 1: Data ingestion (nba_api)
- Layer 2: Storage (DuckDB)
- Layer 3: Feature engineering (rolling averages, rest days, opponent stats)
- Layer 4: Modeling (Random Forest, XGBoost)
- Layer 5: Serving (prediction output)

## Status
🚧 In progress
