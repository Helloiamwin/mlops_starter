"""Drift report bang PSI (Population Stability Index).

Mac dinh: reference = data/processed/train.csv, current = data/processed/test.csv (cung phan phoi -> khong drift).
Demo drift: --current data/interim/kc_house_data_2016.csv (file raw King County, script tu map cot).

Exit code: 0 = khong drift, 2 = co feature drift dang ke (>= 0.2) -> can retrain.
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ingestion.ingest import REQUIRED_KC_COLUMNS, map_king_county  # noqa: E402

FEATURES = ["area", "bedrooms", "bathrooms", "age", "floors", "price"]


def calculate_psi(expected, actual, bins=10):
    # Bin theo quantile cua reference (chuan PSI), bin dau/cuoi mo de bat gia tri ngoai vung
    breakpoints = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    breakpoints[0], breakpoints[-1] = -np.inf, np.inf
    expected_counts = np.histogram(expected, bins=breakpoints)[0] + 1
    actual_counts = np.histogram(actual, bins=breakpoints)[0] + 1
    expected_pct = expected_counts / expected_counts.sum()
    actual_pct = actual_counts / actual_counts.sum()
    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))


def load_features(path):
    df = pd.read_csv(path, dtype={"zipcode": str})
    if set(REQUIRED_KC_COLUMNS).issubset(df.columns):
        df = map_king_county(df)  # file raw -> map ve area/age/...
    return df


def generate_report(reference_path, current_path, output_dir="reports"):
    ref_df = load_features(reference_path)
    cur_df = load_features(current_path)

    report = {
        "generated_at": datetime.now().isoformat(),
        "reference": reference_path,
        "current": current_path,
        "reference_samples": len(ref_df),
        "current_samples": len(cur_df),
        "features": {},
        "drifted_features": [],
    }

    for col in FEATURES:
        if col not in ref_df.columns or col not in cur_df.columns:
            continue
        psi = calculate_psi(ref_df[col], cur_df[col])
        status = "no_drift" if psi < 0.1 else "moderate_drift" if psi < 0.2 else "significant_drift"
        report["features"][col] = {
            "psi": round(psi, 6),
            "status": status,
            "ref_mean": round(float(ref_df[col].mean()), 4),
            "cur_mean": round(float(cur_df[col].mean()), 4),
        }
        if status == "significant_drift":
            report["drifted_features"].append(col)

    report["retrain_recommended"] = bool(report["drifted_features"])

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "drift_report.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[Drift] Report saved to {output_path}")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", default="data/processed/train.csv")
    ap.add_argument("--current", default="data/processed/test.csv")
    a = ap.parse_args()

    # Neu current la file raw thi reference cung nen la raw de so cung thang do (chua scale)
    if a.current != "data/processed/test.csv" and a.reference == "data/processed/train.csv":
        a.reference = "data/raw/kc_house_data.csv"

    report = generate_report(a.reference, a.current)
    for feat, info in report["features"].items():
        print(f"  {feat:10s} PSI={info['psi']:.4f} ({info['status']})  mean {info['ref_mean']:,.1f} -> {info['cur_mean']:,.1f}")
    if report["retrain_recommended"]:
        print(f"[Drift] SIGNIFICANT DRIFT on {report['drifted_features']} -> RETRAIN RECOMMENDED")
        sys.exit(2)
    print("[Drift] No significant drift")
