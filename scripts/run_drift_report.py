"""Rapport Evidently de data drift / target drift sur le dataset Paderborn.

Genere un rapport HTML dans reports/drift/ a partir de la comparaison
train/test (split par asset, F-31 du backlog). Permet de detecter les
features qui derivement entre train et test -- un signal d'alerte avant
meme l'entrainement.

Regle "0 mock" : toutes les valeurs viennent directement de la DB ou des
parquet. Le seuil de drift (0.1 par defaut sur le test de Kolmogorov-Smirnov
2-samples) est parametre evident, pas une valeur inventee.

Usage:
    uv run python scripts/run_drift_report.py
    uv run python scripts/run_drift_report.py --output reports/drift/custom.html
    uv run python scripts/run_drift_report.py --ks-threshold 0.05
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Acces au code src/ (meme pattern que les autres scripts)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.data.db import get_engine
from src.data.splits import split_by_asset


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/drift/drift_report.html"),
        help="Chemin du rapport HTML genere (defaut: reports/drift/drift_report.html)",
    )
    parser.add_argument(
        "--ks-threshold",
        type=float,
        default=0.1,
        help="Seuil KS p-value pour alerter un drift (defaut: 0.1)",
    )
    args = parser.parse_args()

    # Import differe pour eviter d'ecraser l'erreur si evidently n'est pas
    # installe -- le script est appele par GitHub Actions avec evidently
    # explicitement installe (cf. .github/workflows/ml-pipeline.yml).
    try:
        from evidently import ColumnMapping
        from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
        from evidently.report import Report
    except ImportError as e:
        print(f"::warning::evidently non disponible : {e}")
        print("::warning::Skipping drift report (installer evidently>=0.4)")
        return 0  # Pas une erreur -- le pipeline continue

    # --- Chargement des features depuis la DB ---
    # Schema EAV de la table `feature` (cf. docs/data_model.md)
    engine = get_engine()
    df = pd.read_sql(
        """
        select a.code as asset_code, f.feature_name, f.value, f.timestamp
        from feature f
        join asset a on a.id = f.asset_id
        where f.feature_name in ('rms', 'kurtosis', 'crest_factor', 'peak_to_peak', 'skewness')
        """,
        engine,
    )

    if df.empty:
        print("::warning::Aucune feature en base. Lance d'abord scripts/build_dataset.py")
        return 0

    # Pivot large-format (1 ligne = asset + mesure, colonnes = features).
    # `timestamp` (pas measurement_index, absent de `feature` - c'est une
    # colonne de `signal`) identifie une mesure de facon unique : chaque
    # acquisition a un horodatage reel distinct (voir
    # src/evaluation/temporal_drift.py, meme principe deja valide).
    wide = df.pivot_table(
        index=["asset_code", "timestamp"],
        columns="feature_name",
        values="value",
        aggfunc="mean",
    ).reset_index()

    if len(wide) < 4:
        print(
            f"::warning::Trop peu de mesures ({len(wide)}) pour un rapport de drift "
            f"fiable (min 4, recommande > 20). Skipping."
        )
        return 0

    n_assets = wide["asset_code"].nunique()
    if n_assets < 2:
        print(
            f"::warning::Un seul asset ({n_assets}) en base - un split train/test "
            f"n'a pas de sens (comparerait un asset a lui-meme). Skipping."
        )
        return 0

    # Split train/test PAR ASSET (F-31 du backlog, regle d'or - piege
    # methodologique #1, voir docs/brief_projet.md). train_test_split(wide, ...)
    # splitterait des LIGNES DE MESURE au hasard - le meme asset se
    # retrouverait alors des deux cotes (fuite), ce qui minimise artificiellement
    # le drift mesure ici (fausse confiance, pas juste un bug cosmetique).
    # split_by_asset() est la meme fonction que scripts/run_baseline.py et
    # scripts/run_gbm.py, pas une reimplementation.
    train_ids, test_ids = split_by_asset(
        wide["asset_code"].tolist(), test_size=0.5, random_state=42
    )
    train_df = wide[wide["asset_code"].isin(train_ids)]
    test_df = wide[wide["asset_code"].isin(test_ids)]

    # Colonnes numeriques (features) a inclure dans le drift report
    feature_cols = [c for c in ["rms", "kurtosis", "crest_factor", "peak_to_peak", "skewness"] if c in wide.columns]
    if not feature_cols:
        print("::warning::Aucune feature reconnue en colonnes du wide-format")
        return 0

    # --- Generation du rapport Evidently ---
    column_mapping = ColumnMapping(
        numerical_features=feature_cols,
    )

    report = Report(metrics=[
        DataDriftPreset(stattest_threshold=args.ks_threshold),
        TargetDriftPreset(),
    ])

    report.run(reference_data=train_df, current_data=test_df, column_mapping=column_mapping)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    report.save_html(str(args.output))

    # Resume stdout (visible dans les logs GitHub Actions)
    result = report.as_dict()
    n_drifted = sum(
        1
        for m in result.get("metrics", [])
        if "DriftedColumns" in m.get("metric", "")
        and m.get("value", 0) > 0
    )
    print(f"Drift report genere : {args.output}")
    print(f"  - {len(feature_cols)} features analysees")
    print(f"  - {n_drifted} feature(s) avec drift detecte (KS p < {args.ks_threshold})")
    print(f"  - train: {len(train_df)} mesures / test: {len(test_df)} mesures")

    return 0


if __name__ == "__main__":
    sys.exit(main())
