import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
os.environ.setdefault("MLFLOW_TRACKING_URI", "http://localhost:5000")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def ok(msg):
    print(f"[OK] {msg}")


def fail(msg):
    print(f"[FAIL] {msg}", file=sys.stderr)


def warn(msg):
    print(f"[WARN] {msg}")


def info(msg):
    print(f"[..] {msg}")


def which(cmd):
    return shutil.which(cmd)


def run(args, check=True, env=None):
    info(" ".join(str(a) for a in args))
    merged = os.environ.copy()
    if env:
        merged.update(env)
    result = subprocess.run(args, cwd=str(ROOT), check=False, env=merged)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(map(str, args))}")
    return result.returncode


def http_ok(uri, timeout=3.0):
    try:
        urlopen(uri.rstrip("/") + "/health", timeout=timeout)
        return True
    except Exception:
        try:
            urlopen(uri, timeout=timeout)
            return True
        except Exception:
            return False


def check_cli():
    required = {
        "python": [sys.executable, "--version"],
        "pip": [sys.executable, "-m", "pip", "--version"],
        "git": ["git", "--version"],
        "docker": ["docker", "--version"],
    }
    optional_bins = {
        "dvc": "dvc",
        "mlflow": "mlflow",
        "ruff": "ruff",
        "pytest": "pytest",
    }
    errors = []
    for name, cmd in required.items():
        exe = cmd[0] if name != "python" else sys.executable
        if name != "python" and which(name) is None and name != "pip":
            if name == "docker":
                errors.append("docker not found (install Docker Desktop)")
                continue
            if name == "git":
                errors.append("git not found")
                continue
        try:
            run(cmd, check=True)
            ok(name)
        except Exception as e:
            errors.append(f"{name}: {e}")

    for label, mod in optional_bins.items():
        code = run([sys.executable, "-c", f"import {mod}; print({mod}.__version__ if hasattr({mod}, '__version__') else 'ok')"], check=False)
        if code == 0:
            ok(f"python -m / import {label}")
        else:
            path = which(label)
            if path:
                ok(f"{label} on PATH ({path})")
            else:
                warn(f"{label} missing — will install via requirements.txt")

    return errors


def install_deps():
    req = ROOT / "requirements.txt"
    info("Installing requirements (may take a few minutes)...")
    run([sys.executable, "-m", "pip", "install", "-q", "-U", "pip"])
    run([sys.executable, "-m", "pip", "install", "-q", "-r", str(req)])
    for pkg in ("dvc", "mlflow", "skops", "ruff", "pytest"):
        code = run([sys.executable, "-c", f"import {pkg}"], check=False)
        if code != 0:
            raise RuntimeError(f"Package still missing after install: {pkg}")
        ok(f"import {pkg}")


def ensure_raw():
    sys.path.insert(0, str(ROOT / "scripts"))
    from ensure_raw import ensure_raw as _ensure

    path = _ensure()
    if path is None:
        raise RuntimeError(
            "Missing data/raw/kc_house_data.csv — copy to %USERPROFILE%\\mlops-raw\\kc_house_data.csv"
        )
    ok(f"raw data: {path}")


def ensure_mlflow(tracking_uri):
    if not tracking_uri.startswith("http"):
        ok(f"using file tracking: {tracking_uri}")
        return tracking_uri
    if http_ok(tracking_uri):
        ok(f"MLflow UI reachable: {tracking_uri}")
        return tracking_uri
    warn(f"MLflow UI not reachable at {tracking_uri}")
    warn("Start it in another terminal: mlflow ui --port 5000")
    warn("Falling back to sqlite:///mlflow.db for this bootstrap")
    return "sqlite:///mlflow.db"


def dvc_repro():
    dvc_bin = which("dvc")
    cmd = [dvc_bin, "repro"] if dvc_bin else [sys.executable, "-m", "dvc", "repro"]
    if not (ROOT / ".dvc").exists():
        init = [dvc_bin, "init", "--force", "--no-scm"] if dvc_bin else [sys.executable, "-m", "dvc", "init", "--force", "--no-scm"]
        run(init, check=True)
    run(cmd, check=True)
    ok("dvc repro")


def train_n(n, tracking_uri):
    env = {"MLFLOW_TRACKING_URI": tracking_uri}
    for i in range(1, n + 1):
        info(f"train run {i}/{n}")
        run([sys.executable, "src/training/train.py"], check=True, env=env)
    ok(f"trained {n} run(s)")


def validate():
    run([sys.executable, "scripts/validate_model.py"], check=True)
    ok("quality gate passed")


def register_and_promote(tracking_uri, model_name, alias, n_register):
    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient(tracking_uri=tracking_uri)

    import yaml

    with open(ROOT / "configs" / "params.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    experiment_name = (
        config.get("mlflow", {}).get("experiment_name")
        or config["training"]["experiment_name"]
    )
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        raise RuntimeError(f"Experiment not found: {experiment_name}")

    runs = client.search_runs(
        experiment_ids=[exp.experiment_id],
        filter_string="attributes.status = 'FINISHED'",
        order_by=["metrics.test_r2 DESC"],
        max_results=max(n_register * 3, 10),
    )

    usable = []
    for run in runs:
        if "test_r2" not in run.data.metrics:
            continue
        try:
            arts = client.list_artifacts(run.info.run_id, "model")
        except Exception:
            arts = []
        if not arts:
            continue
        usable.append(run)
        if len(usable) >= n_register:
            break

    if not usable:
        raise RuntimeError(
            "No FINISHED runs with model artifacts. Train again with MLflow up."
        )

    registered = []
    for i, run in enumerate(usable):
        model_uri = f"runs:/{run.info.run_id}/model"
        mv = mlflow.register_model(model_uri, model_name)
        client.set_model_version_tag(model_name, mv.version, "validation_status", "passed")
        client.set_model_version_tag(model_name, mv.version, "lifecycle", "Candidate")
        client.set_model_version_tag(model_name, mv.version, "rank_by_test_r2", str(i + 1))
        try:
            client.transition_model_version_stage(
                name=model_name,
                version=mv.version,
                stage="Staging",
                archive_existing_versions=False,
            )
        except Exception as e:
            warn(f"stage transition skipped: {e}")
        registered.append(mv)
        ok(f"registered {model_name} v{mv.version} (test_r2={run.data.metrics.get('test_r2'):.4f})")
        time.sleep(1)

    champion = registered[0]
    client.set_registered_model_alias(model_name, alias, champion.version)
    ok(f"alias '{alias}' -> {model_name} v{champion.version}")
    return champion


def verify_pull(tracking_uri, model_name, alias):
    env = {"MLFLOW_TRACKING_URI": tracking_uri}
    code = run(
        [sys.executable, "scripts/pull_model.py", "--alias", alias, "--model-name", model_name],
        check=False,
        env=env,
    )
    if code != 0:
        raise RuntimeError("pull_model verification failed")
    model_path = ROOT / "models" / "model.pkl"
    if not model_path.exists():
        raise RuntimeError("models/model.pkl missing after pull")
    ok(f"pull verified: {model_path}")


def check_docker_running():
    code = run(["docker", "info"], check=False)
    if code != 0:
        warn("Docker daemon not running — start Docker Desktop before CI deploy")
        return False
    ok("Docker daemon running")
    return True


def main():
    parser = argparse.ArgumentParser(description="Bootstrap lab: CLI checks, train, register, champion")
    parser.add_argument("--n-train", type=int, default=2)
    parser.add_argument("--n-register", type=int, default=2)
    parser.add_argument("--alias", default="champion")
    parser.add_argument("--model-name", default="house-price-model")
    parser.add_argument("--tracking-uri", default=None)
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--skip-train", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("ensure_lab — bootstrap MLOps starter")
    print("=" * 60)

    errors = check_cli()
    if errors and not args.skip_install:
        for e in errors:
            if "docker" in e.lower():
                warn(e)
            else:
                fail(e)

    if not args.skip_install:
        install_deps()
        errors = [e for e in check_cli() if "docker" not in e.lower()]
        if errors:
            for e in errors:
                fail(e)
            sys.exit(1)

    ensure_raw()

    import yaml

    with open(ROOT / "configs" / "params.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    tracking_uri = (
        args.tracking_uri
        or os.environ.get("MLFLOW_TRACKING_URI")
        or config.get("mlflow", {}).get("tracking_uri", "http://localhost:5000")
    )
    tracking_uri = ensure_mlflow(tracking_uri)
    os.environ["MLFLOW_TRACKING_URI"] = tracking_uri

    dvc_repro()

    if not args.skip_train:
        train_n(args.n_train, tracking_uri)
        validate()
        register_and_promote(tracking_uri, args.model_name, args.alias, args.n_register)

    verify_pull(tracking_uri, args.model_name, args.alias)
    check_docker_running()

    print("=" * 60)
    print("LAB READY")
    print(f"  MLflow:  {tracking_uri}")
    print(f"  Model:   {args.model_name}@{args.alias}")
    print(f"  Pickle:  models/model.pkl")
    print("  Next:    keep 'mlflow ui --port 5000' running, start runner, push session/06")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        fail(str(e))
        sys.exit(1)
