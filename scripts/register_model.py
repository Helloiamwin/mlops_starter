import argparse
import os
import subprocess
import sys
from pathlib import Path

import mlflow
import yaml
from mlflow.tracking import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_config(path="configs/params.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def pick_runs(client, experiment_name, n=2):
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        raise RuntimeError(f"Experiment not found: {experiment_name}. Train first.")
    runs = client.search_runs(
        experiment_ids=[exp.experiment_id],
        filter_string="attributes.status = 'FINISHED'",
        order_by=["metrics.test_r2 DESC"],
        max_results=max(n, 5),
    )
    usable = [run for run in runs if "test_r2" in run.data.metrics]
    if not usable:
        raise RuntimeError("No FINISHED runs with test_r2. Run train.py first.")
    return usable[:n]


def register_one(client, run, model_name, tags):
    model_uri = f"runs:/{run.info.run_id}/model"
    mv = mlflow.register_model(model_uri, model_name)
    for k, v in tags.items():
        client.set_model_version_tag(model_name, mv.version, k, str(v))
    client.set_model_version_tag(model_name, mv.version, "validation_status", "candidate")
    client.set_model_version_tag(model_name, mv.version, "lifecycle", "Candidate")
    print(f"[register] {model_name} v{mv.version} <- run={run.info.run_id}")
    print(f"  test_r2={run.data.metrics.get('test_r2')}")
    print(f"  test_rmse={run.data.metrics.get('test_rmse')}")
    return mv


def main():
    parser = argparse.ArgumentParser(description="Register best MLflow runs into Model Registry")
    parser.add_argument("--model-name", default="house-price-model")
    parser.add_argument("--n", type=int, default=2, help="register top-N runs by test_r2")
    args = parser.parse_args()

    config = load_config()
    tracking_uri = config.get("mlflow", {}).get("tracking_uri", "http://localhost:5000")
    experiment_name = (
        config.get("mlflow", {}).get("experiment_name")
        or config["training"]["experiment_name"]
    )
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    runs = pick_runs(client, experiment_name, n=args.n)
    commit = git_commit()
    for i, run in enumerate(runs):
        tags = {
            "source_run_id": run.info.run_id,
            "git_commit": commit,
            "dataset_version": "kc_house_data_session02",
            "created_by": os.environ.get("USERNAME", "ml-engineer"),
            "rank_by_test_r2": str(i + 1),
        }
        register_one(client, run, args.model_name, tags)

    print(f"[register] open UI: {tracking_uri}/#/models")


if __name__ == "__main__":
    main()
