import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.ingestion.ingest import ingest
import pickle
import os
import yaml
from sklearn.preprocessing import LabelEncoder, StandardScaler

def load_config(path="configs/params.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def preprocess(df, config=None, fit=True, artifacts_dir="models"):
    if config is None:
        config = load_config()

    os.makedirs(artifacts_dir, exist_ok=True)
    df = df.copy()

    le = LabelEncoder()
    if fit:
        df["location"] = le.fit_transform(df["location"])
        with open(os.path.join(artifacts_dir, "label_encoder.pkl"), "wb") as f:
            pickle.dump(le, f)
    else:
        with open(os.path.join(artifacts_dir, "label_encoder.pkl"), "rb") as f:
            le = pickle.load(f)
        df["location"] = le.transform(df["location"])

    numeric_cols = ["area", "bedrooms", "bathrooms", "age", "floors"]
    scaler = StandardScaler()
    if fit:
        df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
        with open(os.path.join(artifacts_dir, "scaler.pkl"), "wb") as f:
            pickle.dump(scaler, f)
    else:
        with open(os.path.join(artifacts_dir, "scaler.pkl"), "rb") as f:
            scaler = pickle.load(f)
        df[numeric_cols] = scaler.transform(df[numeric_cols])

    print(f"[Preprocessing] Processed {len(df)} rows")
    return df

if __name__ == "__main__":
    df = ingest()
    processed = preprocess(df)
    os.makedirs("data/processed", exist_ok=True)
    processed.to_csv("data/processed/processed.csv", index=False)
    print("[Preprocessing] Saved to data/processed/processed.csv")
