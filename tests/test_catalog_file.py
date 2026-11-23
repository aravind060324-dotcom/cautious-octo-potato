"""Full Parquet catalog checks. Skips when the ingest output is absent."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.config import REPO_ROOT, Settings

CATALOG_PATH = Settings(_env_file=None).catalog_path
RAW_ROW_CEILING = 51_717

pytestmark = pytest.mark.skipif(
    not Path(CATALOG_PATH).is_file(),
    reason=f"Catalog file is missing: {CATALOG_PATH}",
)


@pytest.fixture(scope="module")
def catalog_frame() -> pd.DataFrame:
    return pd.read_parquet(CATALOG_PATH)


def test_catalog_file_exists_under_repo_root():
    path = Path(CATALOG_PATH)
    assert path.is_file()
    assert path.resolve().is_relative_to(REPO_ROOT.resolve())


def test_ids_are_unique(catalog_frame: pd.DataFrame):
    ids = catalog_frame["id"].astype(str)
    assert ids.is_unique
    assert len(ids) < RAW_ROW_CEILING


def test_ratings_are_between_zero_and_five(catalog_frame: pd.DataFrame):
    ratings = catalog_frame["rating"].dropna()
    assert (ratings >= 0).all()
    assert (ratings <= 5).all()


def test_present_costs_are_positive_integers(catalog_frame: pd.DataFrame):
    costs = catalog_frame["cost_for_two"].dropna()
    assert len(costs) > 0
    assert (costs == costs.astype(int)).all()
    assert (costs.astype(int) > 0).all()
