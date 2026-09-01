import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.splits import (
    assert_no_asset_leakage,
    split_artificial_to_real,
    split_by_asset,
    split_cross_condition,
)


def test_split_by_asset_no_overlap():
    asset_ids = [f"bearing_{i}" for i in range(20)]
    train_ids, test_ids = split_by_asset(asset_ids, test_size=0.25, random_state=42)
    assert set(train_ids) & set(test_ids) == set()
    assert len(train_ids) + len(test_ids) == 20


def test_split_by_asset_deduplicates_repeated_ids():
    # simule plusieurs signaux (mesures) par asset - ne doit pas fuiter
    asset_ids = ["a", "a", "a", "b", "b", "c", "c", "c", "c"]
    train_ids, test_ids = split_by_asset(asset_ids, test_size=1 / 3, random_state=0)
    assert set(train_ids) & set(test_ids) == set()
    assert len(train_ids) + len(test_ids) == 3  # 3 assets uniques, pas 9 signaux


def test_assert_no_asset_leakage_raises_on_overlap():
    train_df = pd.DataFrame({"asset_id": ["a", "a", "b"]})
    test_df = pd.DataFrame({"asset_id": ["b", "c"]})
    with pytest.raises(ValueError):
        assert_no_asset_leakage(train_df, test_df)


def test_assert_no_asset_leakage_passes_when_disjoint():
    train_df = pd.DataFrame({"asset_id": ["a", "b"]})
    test_df = pd.DataFrame({"asset_id": ["c", "d"]})
    assert_no_asset_leakage(train_df, test_df) is None


def test_split_cross_condition_disjoint_sessions():
    df = pd.DataFrame(
        {
            "asset_id": ["a", "a", "b", "b"],
            "test_session_id": ["S1", "S2", "S1", "S2"],
        }
    )
    train_df, test_df = split_cross_condition(df, train_sessions=["S1"], test_sessions=["S2"])
    assert set(train_df["test_session_id"]) == {"S1"}
    assert set(test_df["test_session_id"]) == {"S2"}


def test_split_cross_condition_rejects_overlapping_sessions():
    df = pd.DataFrame({"asset_id": ["a"], "test_session_id": ["S1"]})
    with pytest.raises(ValueError):
        split_cross_condition(df, train_sessions=["S1"], test_sessions=["S1"])


def test_split_artificial_to_real():
    df = pd.DataFrame(
        {
            "asset_id": ["k1", "ka1", "ka4"],
            "defect_origin": ["na", "artificial", "real"],
        }
    )
    train_df, test_df = split_artificial_to_real(df)
    assert set(train_df["asset_id"]) == {"k1", "ka1"}
    assert set(test_df["asset_id"]) == {"ka4"}
