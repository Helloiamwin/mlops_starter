"""Sinh du lieu 'nam 2016' de demo data drift + retrain.

So voi du lieu goc (2014-2015):
  - gia tang ~30% (thi truong len)
  - dien tich lon hon ~20%, nha xay moi hon (yr_built dich len)
  - nhieu nha 2 tang hon
Ghi ra data/interim/ (thu muc nay bi .gitignore).
"""
import argparse
import os

import numpy as np
import pandas as pd


def simulate(raw_path, out_dir, price_up=0.30, area_up=0.20, seed=42):
    rng = np.random.default_rng(seed)
    df = pd.read_csv(raw_path, dtype={"zipcode": str})
    new = df.copy()

    new["price"] = (new["price"] * (1 + price_up) * rng.normal(1.0, 0.05, len(new))).round(0)
    new["sqft_living"] = (new["sqft_living"] * (1 + area_up) * rng.normal(1.0, 0.05, len(new))).round(0)
    new["yr_built"] = np.minimum(new["yr_built"] + rng.integers(0, 15, len(new)), 2015)
    more_floors = rng.random(len(new)) < 0.25
    new.loc[more_floors & (new["floors"] < 2), "floors"] = 2.0
    months = pd.Series(rng.integers(1, 10, len(new)), index=new.index).astype(str)
    new["date"] = "20160" + months + "15T000000"
    new["id"] = new["id"].astype(str) + "16"

    os.makedirs(out_dir, exist_ok=True)
    new_path = os.path.join(out_dir, "kc_house_data_2016.csv")
    all_path = os.path.join(out_dir, "kc_house_data_2014_2016.csv")
    new.to_csv(new_path, index=False)
    pd.concat([df, new]).to_csv(all_path, index=False)

    print(f"[Simulate] {len(new)} rows nam 2016 -> {new_path}")
    print(f"[Simulate] {len(df) + len(new)} rows 2014-2016 (gop) -> {all_path}")
    print(f"[Simulate] price mean {df['price'].mean():,.0f} -> {new['price'].mean():,.0f}")
    print(f"[Simulate] sqft_living mean {df['sqft_living'].mean():,.0f} -> {new['sqft_living'].mean():,.0f}")
    return new_path, all_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw/kc_house_data.csv")
    ap.add_argument("--out-dir", default="data/interim")
    ap.add_argument("--price-up", type=float, default=0.30)
    ap.add_argument("--area-up", type=float, default=0.20)
    a = ap.parse_args()
    simulate(a.raw, a.out_dir, a.price_up, a.area_up)
