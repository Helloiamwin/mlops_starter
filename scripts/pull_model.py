import argparse
import json
import os
import pickle
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
import yaml
from mlflow.tracking import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
SKOPS_TRUSTED = ["sklearn.tree._tree.Tree"]


def load_config(path="configs/params.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_mv(client, model_name, version=None, alias=None, stage=None):
    if version:
        return client.get_model_version(model_name, str(version))

    if alias:
        try:
            return client.get_model_version_by_alias(model_name, alias)
        except Exception as e:
            print(f"[pull] alias '{alias}' not found: {e}")

    stages = [stage] if stage else ["Production", "Staging", "None"]
    for s in stages:
        versions = client.get_latest_versions(model_name, stages=[s])
        if versions:
            return max(versions, key=lambda v: int(v.version))

    all_versions = client.search_model_versions(f"name='{model_name}'")
    if not all_versions:
        raise RuntimeError(
            f"No versions for '{model_name}'. Run: python scripts/ensure_lab.py"
        )
    return max(all_versions, key=lambda v: int(v.version))


def run_has_model(client, run_id):
    if not run_id:
        return False
    try:
        return bool(client.list_artifacts(run_id, "model"))
    except Exception:
        return False


def _load_skops_file(path):
    import skops.io as sio

    return sio.load(path, trusted=SKOPS_TRUSTED)


def load_sklearn_model(model_uri):
    try:
        return mlflow.sklearn.load_model(model_uri)
    except Exception as first:
        try:
            local = Path(mlflow.artifacts.download_artifacts(model_uri))
            skops_path = local / "model.skops" if local.is_dir() else local
            if local.is_dir() and not skops_path.exists():
                matches = list(local.rglob("model.skops"))
                skops_path = matches[0] if matches else skops_path
            if skops_path.exists():
                print(f"[pull] skops trusted load: {skops_path}")
                return _load_skops_file(skops_path)
        except Exception as skops_err:
            first = RuntimeError(f"{first}; skops fallback: {skops_err}")
        try:
            pyfunc = mlflow.pyfunc.load_model(model_uri)
        except Exception as second:
            raise RuntimeError(f"Cannot load model from {model_uri}: {first}; {second}") from second
        inner = getattr(pyfunc, "_model_impl", None)
        if inner is not None and hasattr(inner, "sklearn_model"):
            return inner.sklearn_model
        if hasattr(pyfunc, "get_raw_model"):
            return pyfunc.get_raw_model()
        raise RuntimeError(f"Cannot extract sklearn model from {model_uri}") from first


def candidate_uris(mv, model_name):
    uris = []
    if mv.run_id:
        uris.append(f"runs:/{mv.run_id}/model")
    uris.append(f"models:/{model_name}/{mv.version}")
    if mv.source and mv.source not in uris:
        uris.append(mv.source)
    return uris


def metrics_from_run(client, run_id):
    if not run_id:
        return {}
    run = client.get_run(run_id)
    raw = run.data.metrics or {}
    out = {}
    for key in ("val_rmse", "val_mae", "val_r2", "test_rmse", "test_mae", "test_r2"):
        if key in raw:
            out[key] = float(raw[key])
    return out


def pull_model(
    model_name="house-price-model",
    tracking_uri=None,
    version=None,
    alias="champion",
    stage=None,
    output="models/model.pkl",
    report="reports/evaluation.json",
):
    config = load_config()
    tracking_uri = (
        tracking_uri
        or os.environ.get("MLFLOW_TRACKING_URI")
        or config.get("mlflow", {}).get("tracking_uri", "http://localhost:5000")
    )
    model_name = model_name or config.get("mlflow", {}).get("model_name", "house-price-model")

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    mv = resolve_mv(client, model_name, version=version, alias=alias, stage=stage)
    print(f"[pull] tracking_uri={tracking_uri}")
    print(f"[pull] {model_name} v{mv.version} run_id={mv.run_id} stage={mv.current_stage}")
    print(f"[pull] source={mv.source}")

    errors = []
    model = None
    used_uri = None
    for uri in candidate_uris(mv, model_name):
        if uri.startswith("runs:/") and not run_has_model(client, mv.run_id):
            errors.append(f"{uri}: no model/ artifacts on run")
            continue
        try:
            print(f"[pull] trying {uri}")
            model = load_sklearn_model(uri)
            used_uri = uri
            break
        except Exception as e:
            errors.append(f"{uri}: {e}")
            print(f"[pull] failed {uri}: {e}")

    if model is None:
        raise RuntimeError(
            "Could not load model. Tried:\n  - "
            + "\n  - ".join(errors)
            + "\nFix: python scripts/ensure_lab.py"
        )

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(model, f)
    print(f"[pull] loaded from {used_uri}")
    print(f"[pull] saved {out_path}")

    metrics = metrics_from_run(client, mv.run_id)
    report_path = Path(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print(f"[pull] metrics -> {report_path}: {metrics}")

    manifest = {
        "model_name": model_name,
        "version": str(mv.version),
        "model_uri": used_uri,
        "run_id": mv.run_id,
        "stage": mv.current_stage,
        "tracking_uri": tracking_uri,
        "output": str(out_path),
    }
    manifest_path = out_path.parent / "pull_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"[pull] manifest -> {manifest_path}")

    os.environ["MODEL_VERSION"] = str(mv.version)
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Pull latest/champion model from MLflow Model Registry"
    )
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--tracking-uri", default=None)
    parser.add_argument("--version", default=None)
    parser.add_argument("--alias", default="champion")
    parser.add_argument("--stage", default=None)
    parser.add_argument("--output", default="models/model.pkl")
    parser.add_argument("--report", default="reports/evaluation.json")
    parser.add_argument("--no-alias", action="store_true")
    args = parser.parse_args()

    try:
        pull_model(
            model_name=args.model_name,
            tracking_uri=args.tracking_uri,
            version=args.version,
            alias=None if args.no_alias else args.alias,
            stage=args.stage,
            output=args.output,
            report=args.report,
        )
    except Exception as e:
        print(f"[pull] FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
