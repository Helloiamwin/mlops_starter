import argparse
from mlflow.tracking import MlflowClient


def main():
    parser = argparse.ArgumentParser(description="Show MLflow Model Registry state")
    parser.add_argument("--model-name", default="house-price-model")
    parser.add_argument("--tracking-uri", default="http://localhost:5000")
    args = parser.parse_args()

    client = MlflowClient(tracking_uri=args.tracking_uri)
    versions = client.search_model_versions(f"name='{args.model_name}'")
    if not versions:
        print(f"No versions for {args.model_name}")
        return

    print(f"MODEL REGISTRY: {args.model_name}")
    print("-" * 72)
    for v in sorted(versions, key=lambda x: int(x.version)):
        tags = v.tags or {}
        print(
            f"v{v.version}  stage={v.current_stage:<12} "
            f"run={v.run_id[:8]}  "
            f"lifecycle={tags.get('lifecycle', '-'):<12} "
            f"validation={tags.get('validation_status', '-')}"
        )
        if tags.get("validation_reason"):
            print(f"         reason={tags['validation_reason']}")
        if tags.get("approved_by"):
            print(f"         approved_by={tags['approved_by']}")
        if tags.get("rollback_reason"):
            print(f"         rollback_reason={tags['rollback_reason']}")

    for alias in ("staging", "champion"):
        try:
            mv = client.get_model_version_by_alias(args.model_name, alias)
            print(f"alias:{alias} -> v{mv.version}")
        except Exception:
            print(f"alias:{alias} -> (none)")


if __name__ == "__main__":
    main()
