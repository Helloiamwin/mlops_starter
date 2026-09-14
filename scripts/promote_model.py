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


def set_production(client, model_name, version, approved_by, reason):
    try:
        client.transition_model_version_stage(
            name=model_name,
            version=str(version),
            stage="Production",
            archive_existing_versions=True,
        )
    except Exception as e:
        print(f"[promote] stage warning: {e}")
    try:
        client.set_registered_model_alias(model_name, "champion", str(version))
    except Exception as e:
        print(f"[promote] alias warning: {e}")
    client.set_model_version_tag(model_name, str(version), "approved_by", approved_by)
    client.set_model_version_tag(model_name, str(version), "approval_reason", reason)
    client.set_model_version_tag(model_name, str(version), "lifecycle", "Production")
    append_audit(
        {
            "action": "approve_production",
            "model_name": model_name,
            "version": str(version),
            "approved_by": approved_by,
            "reason": reason,
        }
    )
    print(f"[promote] {model_name} v{version} -> Production (alias=champion)")


def main():
    parser = argparse.ArgumentParser(description="Human approve Staging model to Production")
    parser.add_argument("--model-name", default="house-price-model")
    parser.add_argument("--version", required=True)
    parser.add_argument("--approved-by", default=os.environ.get("USERNAME", "ml-lead"))
    parser.add_argument("--reason", default="offline metrics passed + manual review")
    parser.add_argument("--tracking-uri", default="http://localhost:5000")
    parser.add_argument("--require-staging", action="store_true", default=True)
    args = parser.parse_args()

    client = MlflowClient(tracking_uri=args.tracking_uri)
    mv = client.get_model_version(args.model_name, args.version)
    tags = mv.tags or {}
    if tags.get("validation_status") != "passed":
        raise SystemExit(
            f"Refuse promote: validation_status={tags.get('validation_status')}. Run validate_and_promote first."
        )
    set_production(client, args.model_name, args.version, args.approved_by, args.reason)


if __name__ == "__main__":
    main()
