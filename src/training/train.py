import pandas as pd
import numpy as np
import yaml
import pickle
import os
import json
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

try:
    import mlflow
    import mlflow.sklearn
    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False

def load_config(path="configs/params.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def train(config=None):
    if config is None:
        config = load_config()

    processed_dir = config["data"]["processed_dir"]
    target = config["features"]["target"]
    model_params = config["training"]["params"]

    train_df = pd.read_csv(os.path.join(processed_dir, "train.csv"))
    val_df = pd.read_csv(os.path.join(processed_dir, "val.csv"))
    test_df = pd.read_csv(os.path.join(processed_dir, "test.csv"))

    X_train = train_df.drop(columns=[target])
    y_train = train_df[target]
    X_val = val_df.drop(columns=[target])
    y_val = val_df[target]
    X_test = test_df.drop(columns=[target])
    y_test = test_df[target]

    if HAS_MLFLOW:
        tracking_uri = config.get("mlflow", {}).get("tracking_uri", "http://localhost:5000")
        experiment_name = config["training"]["experiment_name"]
        try:
            mlflow.set_tracking_uri(tracking_uri)
        except Exception:
            pass
        try:
            mlflow.set_experiment(experiment_name)
        except Exception:
            pass

    model = GradientBoostingRegressor(**model_params)
    model.fit(X_train, y_train)

    y_pred_val = model.predict(X_val)
    y_pred_test = model.predict(X_test)

    metrics = {
        "val_rmse": float(np.sqrt(mean_squared_error(y_val, y_pred_val))),
        "val_mae": float(mean_absolute_error(y_val, y_pred_val)),
        "val_r2": float(r2_score(y_val, y_pred_val)),
        "test_rmse": float(np.sqrt(mean_squared_error(y_test, y_pred_test))),
        "test_mae": float(mean_absolute_error(y_test, y_pred_test)),
        "test_r2": float(r2_score(y_test, y_pred_test)),
    }

    print("[Training] Metrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")

    if HAS_MLFLOW:
        try:
            with mlflow.start_run():
                mlflow.log_params(model_params)
                mlflow.log_metrics(metrics)
                # MLflow 3.x mac dinh serialize bang skops va chan sklearn Tree -> dung cloudpickle
                mlflow.sklearn.log_model(model, name="model", serialization_format="cloudpickle")
        except Exception as e:
            print(f"[Training] MLflow logging failed: {e}")

    os.makedirs("models", exist_ok=True)
    model_path = os.path.join("models", "model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"[Training] Model saved to {model_path}")

    os.makedirs("reports", exist_ok=True)
    with open("reports/evaluation.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print("[Training] Evaluation saved to reports/evaluation.json")

    return model, metrics

if __name__ == "__main__":
    train()
