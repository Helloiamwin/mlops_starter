import pandas as pd
import numpy as np
import yaml
import pickle
import os
import json
from urllib.request import urlopen
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


def _http_reachable(uri, timeout=2.0):
    try:
        urlopen(uri.rstrip("/") + "/health", timeout=timeout)
        return True
    except Exception:
        try:
            urlopen(uri, timeout=timeout)
            return True
        except Exception:
            return False


def _setup_mlflow(config):
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI") or config.get("mlflow", {}).get(
        "tracking_uri", "sqlite:///mlflow.db"
    )
    if tracking_uri.startswith("http") and not _http_reachable(tracking_uri):
        print(f"[Training] MLflow unreachable at {tracking_uri}, using sqlite:///mlflow.db")
        tracking_uri = "sqlite:///mlflow.db"
    mlflow.set_tracking_uri(tracking_uri)
    experiment_name = config.get("training", {}).get("experiment_name") or config.get(
        "mlflow", {}
    ).get("experiment_name", "house-price-prediction")
    mlflow.set_experiment(experiment_name)
    return tracking_uri


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

    use_mlflow = False
    tracking_uri = None
    if HAS_MLFLOW:
        try:
            tracking_uri = _setup_mlflow(config)
            use_mlflow = True
        except Exception as e:
            print(f"[Training] MLflow setup skipped: {e}")

    print("[Training] Fitting GradientBoostingRegressor...")
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

    if use_mlflow:
        try:
            with mlflow.start_run():
                mlflow.log_params(model_params)
                mlflow.log_metrics(metrics)
                if tracking_uri and tracking_uri.startswith("http"):
                    mlflow.sklearn.log_model(model, "model")
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
