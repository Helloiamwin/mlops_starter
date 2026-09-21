import os

import pandas as pd
import yaml


REQUIRED_KC_COLUMNS = [
    "price",
    "bedrooms",
    "bathrooms",
    "sqft_living",
    "yr_built",
    "floors",
    "zipcode",
]


def load_config(path="configs/params.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def map_king_county(df: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED_KC_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing King County columns: {missing}")

    out = pd.DataFrame(
        {
            "area": df["sqft_living"],
            "bedrooms": df["bedrooms"],
            "bathrooms": df["bathrooms"],
            "age": 2015 - df["yr_built"],
            "floors": df["floors"].astype(float),
            "location": df["zipcode"].astype(str),
            "price": df["price"],
        }
    )
    out = out[(out["bedrooms"] >= 1) & (out["bedrooms"] <= 10)]
    out = out[(out["bathrooms"] >= 0.5) & (out["bathrooms"] <= 8)]
    out = out[(out["area"] >= 300) & (out["area"] <= 10000)]
    out = out[(out["price"] >= 50_000) & (out["price"] <= 3_000_000)]
    out = out[(out["age"] >= 0) & (out["age"] <= 120)]
    return out.drop_duplicates().reset_index(drop=True)


def ingest(config=None):
    if config is None:
        config = load_config()
    # Cho phep doi nguon du lieu khi retrain: $env:KC_RAW_PATH = "data/interim/kc_house_data_2014_2016.csv"
    raw_path = os.environ.get("KC_RAW_PATH") or config["data"]["raw_path"]
    print(f"[Ingestion] Reading data from {raw_path}")
    raw = pd.read_csv(raw_path)
    df = map_king_county(raw)
    print(f"[Ingestion] Loaded {len(raw)} raw rows -> {len(df)} mapped rows, {len(df.columns)} columns")
    return df


if __name__ == "__main__":
    df = ingest()
    print(df.head())
