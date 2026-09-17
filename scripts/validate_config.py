import os
import sys
from pathlib import Path

import yaml

PARAMS_PATH = Path("configs/params.yaml")
THRESHOLDS_PATH = Path("configs/thresholds.yaml")


def load_yaml(path):
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        raise ValueError(f"{path} is empty")
    return data


def require_keys(data, keys, name):
    missing = [k for k in keys if k not in data]
    if missing:
        raise KeyError(f"{name} missing keys: {missing}")


def validate_params(config):
    require_keys(config, ["project", "data", "features", "training"], "params.yaml")
    training = config["training"]
    params = training.get("params", training)
    n_estimators = params.get("n_estimators", 0)
    if n_estimators < 1:
        raise ValueError(f"n_estimators must be >= 1, got {n_estimators}")
    lr = params.get("learning_rate", 0)
    if not (0 < lr <= 1):
        raise ValueError(f"learning_rate must be in (0, 1], got {lr}")
    max_depth = params.get("max_depth", 1)
    if max_depth < 1:
        raise ValueError(f"max_depth must be >= 1, got {max_depth}")


def validate_thresholds(config):
    require_keys(config, ["model_validation"], "thresholds.yaml")
    mv = config["model_validation"]
    min_r2 = mv.get("min_r2")
    if min_r2 is None or not (0 <= min_r2 <= 1):
        raise ValueError(f"min_r2 must be in [0, 1], got {min_r2}")
    for key in ("max_rmse", "max_mae"):
        value = mv.get(key)
        if value is None or value <= 0:
            raise ValueError(f"{key} must be > 0, got {value}")
    perf = config.get("performance", {})
    latency = perf.get("max_latency_ms")
    if latency is not None and latency <= 0:
        raise ValueError(f"max_latency_ms must be > 0, got {latency}")


def validate_data_path(config):
    raw_path = Path(config.get("data", {}).get("raw_path", ""))
    if not raw_path.exists():
        raise FileNotFoundError(f"raw data path does not exist: {raw_path}")


def main():
    errors = []
    params = None

    try:
        params = load_yaml(PARAMS_PATH)
        validate_params(params)
        print("[OK] configs/params.yaml")
    except Exception as exc:
        errors.append(f"[FAIL] params.yaml: {exc}")

    try:
        thresholds = load_yaml(THRESHOLDS_PATH)
        validate_thresholds(thresholds)
        print("[OK] configs/thresholds.yaml")
    except Exception as exc:
        errors.append(f"[FAIL] thresholds.yaml: {exc}")

    try:
        if params is None:
            raise RuntimeError("skip data path because params.yaml failed")
        validate_data_path(params)
        print("[OK] raw data path exists")
    except Exception as exc:
        if os.environ.get("CI"):
            print(f"[WARN] data path: {exc}")
        else:
            errors.append(f"[FAIL] data path: {exc}")

    if errors:
        print("Config validation FAILED")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)

    print("All configs valid")


if __name__ == "__main__":
    main()
