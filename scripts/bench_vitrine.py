"""Banc de mesure de la vitrine : generalisation artificiel -> reel + temps d'inference.

Mesures (toutes ecrites dans reports/bench/bench_results.json) :

1. Generalisation artificiel -> reel (question centrale du projet, Phase 3-B,
   version exploratoire sur features temporelles seules) :
   - train = 12 roulements a defaut ARTIFICIEL + 3 roulements sains
   - test  = 14 roulements a defaut REEL + les 3 autres roulements sains
   - repete sur les 20 partitions possibles des 6 roulements sains (3/3).
   Controle "meme monde" : memes roulements sains de test, mais entrainement
   sur des defauts reels (CV groupee 5 folds sur les 14 reels), pour isoler
   l'effet du passage artificiel -> reel.
2. Temps d'inference CPU : extraction des 5 indicateurs sur une mesure de
   4 s (256 000 points), prediction XGBoost unitaire et par lot, bout en bout
   via l'API (TestClient FastAPI, sans reseau).
3. Entrainement XGBoost CPU vs GPU (CUDA) sur le jeu complet, pour
   documenter si le GPU est pertinent a cette echelle.

Usage : uv run python scripts/bench_vitrine.py   (DATABASE_URL requis)
"""

import itertools
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, recall_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_gbm import load_wide_features
from src.data.db import get_engine
from src.data.splits import assert_no_asset_leakage
from src.features.time_domain import time_domain_features
from src.models.gbm import train_gbm
from src.serving.predictor import FEATURE_ORDER

OUT = ROOT / "reports" / "bench" / "bench_results.json"


def scores(y_true, y_pred) -> dict:
    return {
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "recall_faulty": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "recall_healthy": float(recall_score(y_true, y_pred, pos_label=0, zero_division=0)),
    }


def summarize(rows: list[dict]) -> dict:
    return {k: {"mean": float(np.mean([r[k] for r in rows])), "std": float(np.std([r[k] for r in rows]))}
            for k in rows[0]}


def artificial_to_real(df: pd.DataFrame) -> dict:
    healthy = sorted(df.loc[df["origin"] == "na", "code"].unique())
    art = df[df["origin"] == "artificial"]
    real = df[df["origin"] == "real"]
    transfer, control = [], []
    for train_h in itertools.combinations(healthy, 3):
        h_train = df[df["code"].isin(train_h)]
        h_test = df[(df["origin"] == "na") & ~df["code"].isin(train_h)]

        # (a) artificiel -> reel
        train = pd.concat([art, h_train])
        test = pd.concat([real, h_test])
        assert_no_asset_leakage(train, test, asset_col="asset_id")
        m = train_gbm(train[FEATURE_ORDER].to_numpy(), train["label"].to_numpy())
        transfer.append(scores(test["label"], m.predict(test[FEATURE_ORDER].to_numpy())))

        # (b) controle reel -> reel : memes sains, defauts reels en CV groupee
        preds = np.zeros(len(real), dtype=int)
        cv = GroupKFold(n_splits=5)  # une seule classe ici : pas de stratification
        for tr, te in cv.split(real, groups=real["code"]):
            tr_df = pd.concat([real.iloc[tr], h_train])
            mm = train_gbm(tr_df[FEATURE_ORDER].to_numpy(), tr_df["label"].to_numpy())
            preds[te] = mm.predict(real.iloc[te][FEATURE_ORDER].to_numpy())
        mm = train_gbm(pd.concat([real, h_train])[FEATURE_ORDER].to_numpy(),
                       pd.concat([real, h_train])["label"].to_numpy())
        y = np.concatenate([real["label"].to_numpy(), h_test["label"].to_numpy()])
        p = np.concatenate([preds, mm.predict(h_test[FEATURE_ORDER].to_numpy())])
        control.append(scores(y, p))
    return {
        "n_partitions": len(transfer),
        "n_test_measurements": int(len(real) + len(h_test)),
        "n_train_measurements": int(len(art) + len(h_train)),
        "artificial_to_real": summarize(transfer),
        "real_to_real_control": summarize(control),
    }


def timing(df: pd.DataFrame) -> dict:
    sig = pd.read_parquet(next((ROOT / "data/processed/paderborn/KA04").glob("*.parquet")),
                          columns=["vibration"])["vibration"].to_numpy()
    for _ in range(3):
        time_domain_features(sig)
    t = []
    for _ in range(50):
        t0 = time.perf_counter()
        time_domain_features(sig)
        t.append((time.perf_counter() - t0) * 1000)
    feat_ms = float(np.median(t))

    model = train_gbm(df[FEATURE_ORDER].to_numpy(), df["label"].to_numpy())
    row = df[FEATURE_ORDER].to_numpy()[:1]
    for _ in range(10):
        model.predict_proba(row)
    t = []
    for _ in range(200):
        t0 = time.perf_counter()
        model.predict_proba(row)
        t.append((time.perf_counter() - t0) * 1000)
    single_ms = float(np.median(t))
    X = df[FEATURE_ORDER].to_numpy()
    t0 = time.perf_counter()
    model.predict_proba(X)
    batch_ms = (time.perf_counter() - t0) * 1000

    from fastapi.testclient import TestClient

    from api.main import app
    client = TestClient(app)
    payload = {"signal": sig.tolist(), "sampling_rate_hz": 64000}
    client.post("/predict", json=payload)
    t = []
    for _ in range(20):
        t0 = time.perf_counter()
        r = client.post("/predict", json=payload)
        t.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200
    return {
        "signal_points": int(len(sig)),
        "feature_extraction_ms_median": round(feat_ms, 3),
        "xgb_predict_single_ms_median": round(single_ms, 3),
        "xgb_predict_batch": {"rows": int(len(X)), "total_ms": round(batch_ms, 3)},
        "api_predict_end_to_end_ms_median": round(float(np.median(t)), 2),
        "api_note": "TestClient in-process : inclut parsing JSON de 256 000 flottants, pas le reseau",
    }


def train_cpu_vs_gpu(df: pd.DataFrame) -> dict:
    X, y = df[FEATURE_ORDER].to_numpy(), df["label"].to_numpy()
    out = {}
    for device in ("cpu", "cuda"):
        try:
            train_gbm(X, y, device=device)
            t0 = time.perf_counter()
            for _ in range(5):
                train_gbm(X, y, device=device)
            out[device] = round((time.perf_counter() - t0) / 5 * 1000, 1)
        except Exception as e:  # GPU absent ou build sans CUDA : documente, pas masque
            out[device] = f"indisponible : {e.__class__.__name__}"
    return {"train_ms_mean_of_5": out, "rows": int(len(X)), "features": len(FEATURE_ORDER)}


def main() -> None:
    engine = get_engine()
    df = load_wide_features(engine)
    meta = pd.read_sql(
        "select a.id as asset_id, a.code, b.defect_origin as origin from asset a "
        "join bearing_attributes b on b.asset_id = a.id",
        engine,
    )
    df = df.merge(meta, on="asset_id")
    print(f"{len(df)} mesures, {df['code'].nunique()} roulements")

    res = {"machine": f"{platform.processor()} / {platform.python_version()}",
           "n_measurements": int(len(df)), "n_bearings": int(df["code"].nunique())}
    res["generalization"] = artificial_to_real(df)
    print(json.dumps(res["generalization"], indent=1))
    res["inference"] = timing(df)
    print(json.dumps(res["inference"], indent=1))
    res["training"] = train_cpu_vs_gpu(df)
    print(json.dumps(res["training"], indent=1))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
