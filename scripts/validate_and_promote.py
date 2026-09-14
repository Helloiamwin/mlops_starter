import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from mlflow.tracking import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "reports" / "governance_audit.jsonl"

METRIC_ALIASES = {
    "r2": ["test_r2", "r2", "val_r2"],
    "rmse": ["test_rmse", "rmse", "val_rmse"],
    "mae": ["test_mae", "mae", "val_mae"],
}


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_metric(metrics, base_name):
    for key in METRIC_ALIASES.get(base_name, [base_name]):
        if key in metrics:
            return key, metrics[key]
    return None, None


def load_thresholds(path, track):
    data = load_yaml(path)
    if track in data:
        return data[track]
    if "model_validation" in data and track == "tabular":
        mv = data["model_validation"]
        return {
            "r2_min": mv.get("min_r2"),
            "rmse_max": mv.get("max_rmse"),
            "mae_max": mv.get("max_mae"),
        }
    return data.get("model_quality", {})


def check_thresholds(metrics, thresholds):
    failures = []
    for key, bound in thresholds.items():
        if bound is None:
            continue
        if key.endswith("_min"):
            base = key[: -len("_min")]
            name, value = resolve_metric(metrics, base)
            if name is None:
                failures.append(f"missing {base}")
            elif value < bound:
                failures.append(f"{name}={value} < {bound}")
        elif key.endswith("_max"):
            base = key[: -len("_max")]
            name, value = resolve_metric(metrics, base)
            if name is None:
                failures.append(f"missing {base}")
            elif value > bound:
                failures.append(f"{name}={value} > {bound}")
    return failures


def append_audit(event):
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = dict(event)
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def set_stage(client, model_name, version, stage):
    try:
        client.transition_model_version_stage(
            name=model_name,
            version=str(version),
            stage=stage,
            archive_existing_versions=(stage == "Production"),
        )
    except Exception as e:
        print(f"[validate] stage transition warning: {e}")
    alias = {"Staging": "staging", "Production": "champion", "Archived": "archived"}.get(stage)
    if alias:
        try:
            client.set_registered_model_alias(model_name, alias, str(version))
        except Exception as e:
            print(f"[validate] alias warning: {e}")


def main():
    parser = argparse.ArgumentParser(description="Validate registry model version and promote to Staging")
    parser.add_argument("--model-name", default="house-price-model")
    parser.add_argument("--version", required=True)
    parser.add_argument("--track", default="tabular")
    parser.add_argument("--thresholds", default="configs/thresholds.yaml")
    parser.add_argument("--tracking-uri", default="http://localhost:5000")
    args = parser.parse_args()

    client = MlflowClient(tracking_uri=args.tracking_uri)
    mv = client.get_model_version(args.model_name, args.version)
    run = client.get_run(mv.run_id)
    metrics = run.data.metrics
    thresholds = load_thresholds(args.thresholds, args.track)

    print("=" * 56)
    print(f"VALIDATE {args.model_name} v{args.version}")
    print(f"run_id={mv.run_id}")
    print(f"thresholds={thresholds}")
    print("=" * 56)
    for k in sorted(metrics):
        if any(x in k for x in ("rmse", "mae", "r2")):
            print(f"  {k}: {metrics[k]}")

    failures = check_thresholds(metrics, thresholds)
    if failures:
        client.set_model_version_tag(args.model_name, args.version, "validation_status", "rejected")
        client.set_model_version_tag(args.model_name, args.version, "validation_reason", "; ".join(failures))
        client.set_model_version_tag(args.model_name, args.version, "lifecycle", "Rejected")
        append_audit(
            {
                "action": "validate",
                "model_name": args.model_name,
                "version": str(args.version),
                "result": "rejected",
                "failures": failures,
                "run_id": mv.run_id,
            }
        )
        print("Automated validation FAILED:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    set_stage(client, args.model_name, args.version, "Staging")
    client.set_model_version_tag(args.model_name, args.version, "validation_status", "passed")
    client.set_model_version_tag(args.model_name, args.version, "validated_by", "automated_pipeline")
    client.set_model_version_tag(args.model_name, args.version, "lifecycle", "Staging")
    append_audit(
        {
            "action": "validate",
            "model_name": args.model_name,
            "version": str(args.version),
            "result": "passed",
            "stage": "Staging",
            "run_id": mv.run_id,
            "validated_by": "automated_pipeline",
        }
    )
    print(f"Version {args.version} promoted to Staging (alias=staging)")


if __name__ == "__main__":
    main()
