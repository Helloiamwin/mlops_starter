import json
import sys

import yaml


def load_thresholds(path="configs/thresholds.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_metrics(path="reports/evaluation.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_model():
    thresholds = load_thresholds()
    metrics = load_metrics()
    t = thresholds.get("model_validation") or {}
    tabular = thresholds.get("tabular") or {}

    min_r2 = t.get("min_r2", tabular.get("r2_min", 0.75))
    max_rmse = t.get("max_rmse", tabular.get("rmse_max", 200000))
    max_mae = t.get("max_mae", tabular.get("mae_max", 120000))

    r2 = metrics.get("test_r2", metrics.get("r2", 0))
    rmse = metrics.get("test_rmse", metrics.get("rmse", float("inf")))
    mae = metrics.get("test_mae", metrics.get("mae", float("inf")))

    checks = [
        (f"R2 >= {min_r2}", r2 >= min_r2, f"R2={r2:.4f}"),
        (f"RMSE <= {max_rmse}", rmse <= max_rmse, f"RMSE={rmse:.2f}"),
        (f"MAE <= {max_mae}", mae <= max_mae, f"MAE={mae:.2f}"),
    ]

    print("=" * 50)
    print("OFFLINE MODEL VALIDATION (evaluation.json)")
    print("=" * 50)
    all_passed = True
    for name, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name} -> {detail}")
        if not passed:
            all_passed = False
    print("=" * 50)
    if all_passed:
        print("Result: ALL CHECKS PASSED")
    else:
        print("Result: VALIDATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    validate_model()
