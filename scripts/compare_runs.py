import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import mlflow
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

METRIC_KEYS = [
    "metrics.val_rmse",
    "metrics.val_mae",
    "metrics.val_r2",
    "metrics.test_rmse",
    "metrics.test_mae",
    "metrics.test_r2",
]


def load_config(path="configs/params.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_label(row):
    name = row.get("tags.mlflow.runName")
    if isinstance(name, str) and name.strip():
        return name
    return str(row["run_id"])[:8]


def fetch_runs(config, n=5):
    tracking_uri = config.get("mlflow", {}).get("tracking_uri", "http://localhost:5000")
    experiment_name = (
        config.get("mlflow", {}).get("experiment_name")
        or config["training"]["experiment_name"]
    )
    mlflow.set_tracking_uri(tracking_uri)
    exp = mlflow.get_experiment_by_name(experiment_name)
    if exp is None:
        raise RuntimeError(f"Experiment not found: {experiment_name}. Start mlflow ui and train first.")
    runs = mlflow.search_runs(
        experiment_ids=[exp.experiment_id],
        filter_string="attributes.status = 'FINISHED'",
        order_by=["start_time DESC"],
        max_results=n,
    )
    if runs.empty:
        raise RuntimeError("No FINISHED runs to compare.")
    runs = runs.copy()
    runs["label"] = runs.apply(run_label, axis=1)
    return runs, experiment_name, tracking_uri


def print_table(runs):
    cols = ["label", "run_id"] + [c for c in METRIC_KEYS if c in runs.columns]
    view = runs[cols].copy()
    view["run_id"] = view["run_id"].astype(str).str[:8]
    print(view.to_string(index=False))


def plot_metrics(runs, out_path):
    labels = list(runs["label"])
    metric_pairs = [
        ("metrics.test_rmse", "Test RMSE", False),
        ("metrics.test_mae", "Test MAE", False),
        ("metrics.test_r2", "Test R2", True),
        ("metrics.val_rmse", "Val RMSE", False),
        ("metrics.val_mae", "Val MAE", False),
        ("metrics.val_r2", "Val R2", True),
    ]
    available = [(k, title, higher) for k, title, higher in metric_pairs if k in runs.columns]
    if not available:
        raise RuntimeError("Runs have no comparable metrics.")

    n = len(available)
    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    axes = axes.flatten()
    x = range(len(labels))
    colors = plt.cm.tab10.colors

    for ax, (key, title, higher_better) in zip(axes, available):
        values = [float(v) for v in runs[key].tolist()]
        bars = ax.bar(x, values, color=[colors[i % len(colors)] for i in x])
        ax.set_title(title)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=20, ha="right")
        best_idx = values.index(max(values) if higher_better else min(values))
        bars[best_idx].set_edgecolor("black")
        bars[best_idx].set_linewidth(2)
        ax.set_ylabel("higher better" if higher_better else "lower better")

    for ax in axes[n:]:
        ax.axis("off")

    fig.suptitle("MLflow run comparison", fontsize=14)
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"[compare] saved {out_path}")


def plot_feature_importance(out_path):
    local = ROOT / "reports" / "features.json"
    if not local.is_file():
        print("[compare] skip feature importance (reports/features.json missing)")
        return
    with open(local, "r", encoding="utf-8") as f:
        payload = json.load(f)
    importances = payload.get("importances") or {}
    if not importances:
        print("[compare] skip feature importance (empty)")
        return
    items = sorted(importances.items(), key=lambda kv: kv[1])
    names = [k for k, _ in items]
    vals = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(names, vals, color="#4C78A8")
    ax.set_xlabel("importance")
    ax.set_title(f"Feature importance — {payload.get('run_name', 'latest')}")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    print(f"[compare] saved {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Compare MLflow training runs visually")
    parser.add_argument("--n", type=int, default=5, help="number of latest FINISHED runs")
    parser.add_argument(
        "--out",
        default="reports/run_comparison.png",
        help="metrics comparison chart path",
    )
    parser.add_argument(
        "--importance-out",
        default="reports/feature_importance.png",
        help="feature importance chart path",
    )
    args = parser.parse_args()

    config = load_config()
    runs, experiment_name, tracking_uri = fetch_runs(config, n=args.n)
    print(f"[compare] experiment={experiment_name} tracking={tracking_uri}")
    print_table(runs)
    plot_metrics(runs, args.out)
    plot_feature_importance(args.importance_out)
    print(f"[compare] open UI: {tracking_uri}/#/experiments")


if __name__ == "__main__":
    main()
