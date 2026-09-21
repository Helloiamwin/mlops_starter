"""Danh gia model dang co (models/*.pkl) tren mot file du lieu moi, so voi configs/thresholds.yaml.

  python scripts/evaluate_model.py --data data/interim/kc_house_data_2016.csv

Exit code 1 neu vi pham nguong -> trigger retrain (performance degradation).
"""
import argparse
import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ingestion.ingest import map_king_county  # noqa: E402
from src.preprocessing.preprocess import preprocess  # noqa: E402


def evaluate(data_path, model_dir="models", thresholds_path="configs/thresholds.yaml", out="reports/evaluation_new_data.json"):
    raw = pd.read_csv(data_path, dtype={"zipcode": str})
    df = map_king_county(raw)
    df = preprocess(df, fit=False, artifacts_dir=model_dir)  # dung scaler/encoder da fit

    with open(os.path.join(model_dir, "model.pkl"), "rb") as f:
        model = pickle.load(f)

    X, y = df.drop(columns=["price"]), df["price"]
    pred = model.predict(X)
    metrics = {
        "data": data_path,
        "samples": int(len(df)),
        "r2": float(r2_score(y, pred)),
        "rmse": float(np.sqrt(mean_squared_error(y, pred))),
        "mae": float(mean_absolute_error(y, pred)),
        "mean_error": float(np.mean(pred - y)),  # am = model du doan thap hon thuc te
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(metrics, f, indent=2)

    t = yaml.safe_load(open(thresholds_path))["model_validation"]
    checks = [
        (f"R2 >= {t['min_r2']}", metrics["r2"] >= t["min_r2"], f"R2={metrics['r2']:.4f}"),
        (f"RMSE <= {t['max_rmse']}", metrics["rmse"] <= t["max_rmse"], f"RMSE={metrics['rmse']:.0f}"),
        (f"MAE <= {t['max_mae']}", metrics["mae"] <= t["max_mae"], f"MAE={metrics['mae']:.0f}"),
        (f"|bias| <= {t.get('max_bias', 50000)}", abs(metrics["mean_error"]) <= t.get("max_bias", 50000), f"bias={metrics['mean_error']:,.0f}"),
    ]
    print("=" * 50)
    print(f"EVALUATE CURRENT MODEL ON {data_path}")
    print("=" * 50)
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name} -> {detail}")
        ok &= passed
    print("=" * 50)
    print("Result:", "OK" if ok else "PERFORMANCE DEGRADED -> RETRAIN RECOMMENDED")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/interim/kc_house_data_2016.csv")
    a = ap.parse_args()
    sys.exit(evaluate(a.data))
