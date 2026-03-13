from prediction.training.trainer import IndiaMLTrainer
from scripts.train_initial_models import _generate_synthetic_data

feature_df, close_series, nifty_returns, vix_series = _generate_synthetic_data(n_rows=1500)

trainer = IndiaMLTrainer(ticker="TEST", horizon=5, run_optuna=True, use_mlflow=False)
result = trainer.train(feature_df, close_series, nifty_returns, vix_series)
print("done")
