"""Analyse temporelle (date d'essai reelle) plutot que boxplot par etat.

Sur Paderborn, chaque asset est teste sur UN SEUL jour calendaire (verifie :
min(timestamp) == max(timestamp)::date pour 31/32 roulements). asset_id,
date d'essai et defect_origin sont donc largement confondus - un boxplot
kurtosis par health_state ne peut pas distinguer "effet defaut" de "effet
date/banc/session". Voir docs/known_issues.md pour la lecture complete.

Toute correlation doit etre calculee au niveau ASSET (n=32), jamais au niveau
mesure (n~2500, pseudo-replication : ~80 mesures par asset ne sont pas 80
observations independantes, voir docs/brief_projet.md piege methodologique #1 applique
ici a l'analyse exploratoire et pas seulement au split).
"""

import pandas as pd

ASSET_LEVEL_QUERY = """
select
    a.id as asset_id,
    a.health_state,
    ba.defect_origin,
    ba.defect_location,
    ba.defect_method,
    min(f.timestamp) as test_date,
    avg(f.value) as mean_value,
    count(*) as n_measurements
from feature f
join asset a on a.id = f.asset_id
left join bearing_attributes ba on ba.asset_id = a.id
where f.channel = %(channel)s and f.feature_name = %(feature_name)s
group by a.id, a.health_state, ba.defect_origin, ba.defect_location, ba.defect_method
"""


def load_asset_level_series(engine, feature_name: str, channel: str = "vibration") -> pd.DataFrame:
    """Une ligne par asset (pas par mesure) : date d'essai + valeur moyenne de la feature.

    C'est le niveau correct pour toute analyse de derive temporelle sur ce
    dataset - voir docstring du module."""
    df = pd.read_sql(
        ASSET_LEVEL_QUERY,
        engine,
        params={"channel": channel, "feature_name": feature_name},
    )
    df["defect_origin"] = df["defect_origin"].fillna("na")
    df["test_date"] = pd.to_datetime(df["test_date"])
    return df.sort_values("test_date").reset_index(drop=True)


def correlation_by_group(df: pd.DataFrame, group_col: str = "defect_origin") -> pd.DataFrame:
    """Correlation (valeur moyenne asset) vs date d'essai, par groupe.

    n petit (6 a 14 par groupe sur Paderborn) : a lire comme indicatif, pas
    comme une preuve statistique - annoter le n a chaque fois que ce chiffre
    est cite (docs/brief_projet.md section 9)."""
    rows = []
    for group, sub in df.groupby(group_col):
        n = len(sub)
        corr = sub["mean_value"].corr(sub["test_date"].astype("int64")) if n >= 3 else float("nan")
        rows.append({"group": group, "n": n, "corr_vs_test_date": corr})
    return pd.DataFrame(rows).sort_values("group").reset_index(drop=True)


def same_day_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Assets testes le meme jour calendaire : le seul levier du dataset pour
    separer un effet "jour d'essai" d'un effet "roulement individuel".

    Si deux assets du meme jour et du meme label/methode/localisation
    divergent autant que deux assets de jours differents, la variance
    inter-roulement domine et la derive temporelle n'explique pas grand
    chose a elle seule."""
    df = df.copy()
    df["test_day"] = df["test_date"].dt.date
    pairs = []
    for day, sub in df.groupby("test_day"):
        if len(sub) < 2:
            continue
        sub = sub.sort_values("asset_id")
        ids = sub["asset_id"].tolist()
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = sub.iloc[i], sub.iloc[j]
                pairs.append(
                    {
                        "test_day": day,
                        "asset_a": a["asset_id"],
                        "asset_b": b["asset_id"],
                        "value_a": a["mean_value"],
                        "value_b": b["mean_value"],
                        "ratio": max(a["mean_value"], b["mean_value"])
                        / max(min(a["mean_value"], b["mean_value"]), 1e-9),
                        "same_defect_origin": a["defect_origin"] == b["defect_origin"],
                        "same_defect_location": a["defect_location"] == b["defect_location"],
                        "same_defect_method": a["defect_method"] == b["defect_method"],
                    }
                )
    return pd.DataFrame(pairs)


def defect_type_crosstab(df: pd.DataFrame) -> pd.DataFrame:
    """Repartition defect_origin x defect_method x defect_location.

    Sur Paderborn, defect_method determine quasiment defect_origin (real =
    fatigue_pitting/plastic_deform, artificial = drilling/edm/engraving) -
    a verifier avant toute conclusion sur la generalisation artificiel->reel
    (Phase 3) : le modele generalise-t-il "artificiel -> reel" ou bien
    "endommagement localise et net -> usure diffuse" ? Les deux causes sont
    confondues dans ce dataset, voir docs/known_issues.md."""
    return (
        df.groupby(["defect_origin", "defect_method", "defect_location"], dropna=False)
        .size()
        .reset_index(name="n_assets")
        .sort_values(["defect_origin", "defect_method"])
    )
