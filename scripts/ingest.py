"""Build the restaurant catalog from the Hugging Face training split.

Usage (from the repository root):

    python scripts/ingest.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
from datasets import load_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.catalog.cleaning import merge_with_stats  # noqa: E402
from app.catalog.models import Restaurant  # noqa: E402
from app.config import Settings  # noqa: E402

DATASET_ID = "ManikaSaini/zomato-restaurant-recommendation"
CSV_NAME = "zomato.csv"
CSV_URL = f"https://huggingface.co/datasets/{DATASET_ID}/resolve/main/{CSV_NAME}"
RAW_CSV = REPO_ROOT / "data" / "raw" / CSV_NAME
SOURCE_COLUMNS = (
    "url",
    "address",
    "name",
    "online_order",
    "book_table",
    "rate",
    "votes",
    "location",
    "rest_type",
    "dish_liked",
    "cuisines",
    "approx_cost(for two people)",
    "reviews_list",
    "listed_in(type)",
)


def ensure_source_csv() -> Path:
    """Download the train CSV, resuming if a previous copy was interrupted."""
    RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    if RAW_CSV.exists() and RAW_CSV.stat().st_size >= 500_000_000:
        print(f"Using cached {RAW_CSV}", flush=True)
        return RAW_CSV
    curl = "curl.exe" if os.name == "nt" else "curl"
    print(f"Fetching {DATASET_ID} train split...", flush=True)
    subprocess.check_call(
        [
            curl,
            "-L",
            "--fail",
            "--retry",
            "8",
            "--retry-all-errors",
            "-C",
            "-",
            "-o",
            str(RAW_CSV),
            CSV_URL,
        ]
    )
    return RAW_CSV


def load_train_listings():
    csv_path = ensure_source_csv()
    print(f"Reading {csv_path} with datasets...", flush=True)
    dataset = load_dataset("csv", data_files=str(csv_path), split="train")
    extra = [column for column in dataset.column_names if column not in SOURCE_COLUMNS]
    if extra:
        dataset = dataset.remove_columns(extra)
    return dataset


def restaurants_frame(restaurants: list[Restaurant]) -> pd.DataFrame:
    columns = list(Restaurant.model_fields)
    frame = pd.DataFrame([item.model_dump() for item in restaurants], columns=columns)
    if frame.empty:
        frame = pd.DataFrame(columns=columns)
    frame["cost_for_two"] = pd.array(frame["cost_for_two"], dtype="Int64")
    frame["rating"] = pd.array(frame["rating"], dtype="Float64")
    frame["votes"] = frame["votes"].astype("int64")
    return frame


def write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        frame.to_parquet(tmp_path, index=False)
        tmp_path.replace(path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def iter_rows(dataset):
    total = len(dataset)
    for index, row in enumerate(dataset, start=1):
        if index % 5000 == 0 or index == total:
            print(f"  processed {index}/{total} listings", flush=True)
        yield row


def main() -> None:
    settings = Settings()
    dataset = load_train_listings()
    raw_count = len(dataset)
    print("Cleaning and merging listings...", flush=True)
    stats = merge_with_stats(iter_rows(dataset))
    frame = restaurants_frame(stats.restaurants)
    write_parquet(frame, settings.catalog_path)
    print(f"raw listings: {raw_count}", flush=True)
    print(f"merged restaurants: {len(stats.restaurants)}", flush=True)
    print(f"dropped: {stats.dropped}", flush=True)
    print(f"Wrote {settings.catalog_path}", flush=True)


if __name__ == "__main__":
    main()
