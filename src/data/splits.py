"""Splits train/test par entite physique (asset), jamais par fenetre/signal.

Voir docs/brief_projet.md piege methodologique #1 : segmenter un signal en fenetres puis
melanger train/test fait fuiter la meme entite dans les deux ensembles.
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


def split_by_asset(
    asset_ids: list[str],
    test_size: float = 0.2,
    random_state: int | None = None,
    stratify: list | None = None,
) -> tuple[list[str], list[str]]:
    """Split au niveau asset_id (entite unique, dedupliquee avant split)."""
    unique_ids = sorted(set(asset_ids))
    strat = None
    if stratify is not None:
        label_by_id = dict(zip(asset_ids, stratify))
        strat = [label_by_id[i] for i in unique_ids]
    train_ids, test_ids = train_test_split(
        unique_ids, test_size=test_size, random_state=random_state, stratify=strat
    )
    return train_ids, test_ids


def split_cross_condition(
    df: pd.DataFrame,
    train_sessions: list[str],
    test_sessions: list[str],
    session_col: str = "test_session_id",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Entraine sur certaines conditions de fonctionnement, teste sur d'autres.

    Piege docs/brief_projet.md #2 : un modele qui n'apprend que la charge/condition plutot
    que le defaut s'ecroule ici. Ne PAS utiliser un split aleatoire des sessions
    pour ce test - train_sessions/test_sessions doivent etre disjoints et fournis
    explicitement.
    """
    overlap = set(train_sessions) & set(test_sessions)
    if overlap:
        raise ValueError(f"Sessions partagees entre train et test : {overlap}")
    train_df = df[df[session_col].isin(train_sessions)]
    test_df = df[df[session_col].isin(test_sessions)]
    return train_df, test_df


def assert_no_asset_leakage(
    train_df: pd.DataFrame, test_df: pd.DataFrame, asset_col: str = "asset_id"
) -> None:
    """Garde-fou : leve une erreur si un asset_id apparait dans train ET test."""
    leaked = set(train_df[asset_col]) & set(test_df[asset_col])
    if leaked:
        raise ValueError(f"Fuite de donnees : assets presents dans train ET test : {leaked}")


def split_artificial_to_real(
    df: pd.DataFrame, defect_origin_col: str = "defect_origin"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Objectif principal du projet : entraine sur sain (defect_origin='na') et
    defauts artificiels, evalue sur defauts reels (voir docs/brief_projet.md section 2)."""
    train_df = df[df[defect_origin_col].isin(["na", "artificial"])]
    test_df = df[df[defect_origin_col] == "real"]
    return train_df, test_df
