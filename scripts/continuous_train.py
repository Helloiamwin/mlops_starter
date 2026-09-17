import subprocess
import sys
from pathlib import Path


def run(args):
    print(f"[CT] {' '.join(args)}")
    result = subprocess.run(args)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    raw = Path("data/raw/kc_house_data.csv")
    if not raw.exists():
        print("[CT] missing data/raw/kc_house_data.csv")
        print("[CT] run session 02 prepare_data or copy the CSV before CT")
        sys.exit(1)

    run(["dvc", "repro"])
    run([sys.executable, "src/training/train.py"])
    run([sys.executable, "scripts/validate_model.py"])
    print("[CT] training pipeline passed quality gate")


if __name__ == "__main__":
    main()
