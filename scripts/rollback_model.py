import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from mlflow.tracking import MlflowClient

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "reports" / "governance_audit.jsonl"


def append_audit(event):
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = dict(event)
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def current_production(client, model_name):
    versions = client.search_model_versions(f"name='{model_name}'")
    prod = [v for v in versions if v.current_stage == "Production"]
    if prod:
        return prod[0]
    try:
        return client.get_model_version_by_alias(model_name, "champion")
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Rollback Production to a previous model version")
    parser.add_argument("--model-name", default="house-price-model")
    parser.add_argument("--to-version", required=True, help="stable version to restore")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--by", default=os.environ.get("USERNAME", "ml-lead"))
    parser.add_argument("--tracking-uri", default="http://localhost:5000")
    args = parser.parse_args()

    client = MlflowClient(tracking_uri=args.tracking_uri)
    before = current_production(client, args.model_name)
    before_version = before.version if before else None

    try:
        client.transition_model_version_stage(
            name=args.model_name,
            version=str(args.to_version),
            stage="Production",
            archive_existing_versions=True,
        )
    except Exception as e:
        print(f"[rollback] stage warning: {e}")
    try:
        client.set_registered_model_alias(args.model_name, "champion", str(args.to_version))
    except Exception as e:
        print(f"[rollback] alias warning: {e}")

    client.set_model_version_tag(args.model_name, str(args.to_version), "lifecycle", "Production")
    client.set_model_version_tag(args.model_name, str(args.to_version), "rollback_reason", args.reason)
    if before_version and str(before_version) != str(args.to_version):
        client.set_model_version_tag(args.model_name, str(before_version), "lifecycle", "Archived")

    append_audit(
        {
            "action": "rollback",
            "model_name": args.model_name,
            "from_version": before_version,
            "to_version": str(args.to_version),
            "reason": args.reason,
            "by": args.by,
        }
    )
    print(f"[rollback] Production: v{before_version} -> v{args.to_version}")
    print(f"[rollback] reason={args.reason}")
    print(f"[rollback] audit -> {AUDIT_PATH}")


if __name__ == "__main__":
    main()
