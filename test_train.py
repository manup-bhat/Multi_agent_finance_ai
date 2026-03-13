import pandas as pd
from prediction.training.trainer import XGBoostPredictor

# Generate test close series
idx = pd.date_range("2020-01-01", periods=1000, freq="B")
close = pd.Series(range(1000), index=idx) * 1.0
labels = XGBoostPredictor.make_labels(close, 5)
print(f"Total labels: {len(labels)}")
print(f"Valid labels: {labels.notna().sum()}")
