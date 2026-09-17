import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ensure_raw import ensure_raw


def run(args):
    print(f"[CT] {' '.join(args)}")
    result = subprocess.run(args, check=False)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    if ensure_raw() is None:
        print("[CT] missing data/raw/kc_house_data.csv")
        print("[CT] copy CSV to %USERPROFILE%\\mlops-raw\\kc_house_data.csv")
        sys.exit(1)

    run(["dvc", "repro"])
    run([sys.executable, "src/training/train.py"])
    run([sys.executable, "scripts/validate_model.py"])
    print("[CT] training pipeline passed quality gate")


if __name__ == "__main__":
    main()
