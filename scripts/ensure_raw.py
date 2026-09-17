import os
import shutil
import sys
from pathlib import Path

DEST = Path("data/raw/kc_house_data.csv")


def candidates():
    paths = []
    env_path = os.environ.get("HOUSE_PRICE_RAW")
    if env_path:
        paths.append(Path(env_path))
    paths.append(Path.home() / "mlops-raw" / "kc_house_data.csv")
    return paths


def ensure_raw():
    if DEST.exists():
        print(f"[ensure_raw] found {DEST}")
        return DEST
    DEST.parent.mkdir(parents=True, exist_ok=True)
    for src in candidates():
        if src.exists():
            shutil.copy2(src, DEST)
            print(f"[ensure_raw] copied {src} -> {DEST}")
            return DEST
    return None


def main():
    path = ensure_raw()
    if path is None:
        print("[ensure_raw] missing kc_house_data.csv")
        print("[ensure_raw] copy it to %USERPROFILE%\\mlops-raw\\kc_house_data.csv")
        sys.exit(1)
    print(f"[ensure_raw] ready {path}")


if __name__ == "__main__":
    main()
