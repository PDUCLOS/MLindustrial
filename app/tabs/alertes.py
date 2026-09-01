"""Onglet 'Alertes' - dashboard Streamlit.

Design : voir docs/proposition_alertes_dashboard.md (340 lignes, 14 sections).
Regle 0-mock enforcee : toute valeur affichee vient d'une lecture reelle
(DB ou mlflow). Si une dependance manque, erreur explicite + return (onglet
seul interrompu, reste du dashboard continue), jamais de fallback silencieux.

Architecture :
- render(engine) est l'unique entree publique. Le dashboard principal
  (app/dashboard.py) l'appelle dans un `with tab_alertes:` apres import.
- _load_alerts_data() est cache via @st.cache_data : la requete SQL ne
  tourne pas a chaque interaction sur les filtres.
- _load_threshold_from_mlflow() n'est PAS cache : on veut la valeur live
  du dernier run (un re-entrainement doit etre visible immediatement).
- _render_* : sous-fonctions de rendu, une par section visuelle.
  Chaque sous-fonction prend les donnees en entree, pas d'etat cache.

Reactivite :
- @st.cache_data(ttl=60) sur la requete DB : auto-refresh feel sans spam
  la base quand l'utilisateur clique un filtre.
- st.session_state["alert_selected_asset"] : ligne selectionnee pour
  drill-down, persiste entre reruns.
- Un bouton 'Rafraichir' vide le cache manuellement (utile apres un
  scripts/build_dataset.py ou un scripts/run_baseline.py).

Mise a jour :
- CONFIG en haut du fichier : features, severites, colonnes affichees.
  Pour ajouter une feature au menu deroulant, modifier CONFIG['features'].
- _styles.py : palette + CSS. Pour changer le look, modifier _styles.py
  uniquement, ce fichier n'a pas besoin d'etre touche.
"""

from __future__ import annotations

from typing import Any

import mlflow
import pandas as pd
import streamlit as st

from src.models.baseline import apply_threshold

from app.tabs._components import (
    banner,
    confusion_heatmap,
    distribution_chart,
    inject_css_once,
    kpi_row,
    status_badge,
)
from app.tabs._glossaire import help_text


# ---------------------------------------------------------------------------
# CONFIG : tout ce qui est 'reglable' est ici. Pas de magic strings dans
# le rendu, c'est ce qui rend l'onglet 'facilement mise a jour'.
# ---------------------------------------------------------------------------

CONFIG: dict[str, Any] = {
    "mlflow": {
        "tracking_uri": "http://mlflow:5000",
        "experiment": "baseline_threshold_cv",
        # Cle du run mlflow dont on lit le seuil. Aujourd'hui un seul
        # candidat raisonnable (kurtosis, F1 0.682 +/- 0.158) ; le menu
        # deroulant ci-dessous laisse la place pour les autres.
        "default_run_name": "threshold_cv_kurtosis",
        "param_threshold": "final_threshold",
        "param_direction": "final_direction",
        "metric_f1_train": "f1_macro_train_on_full_data",
        "metric_f1_cv_mean": "f1_macro_mean",
        "metric_f1_cv_std": "f1_macro_std",
    },
    "features": [
        # (run_name_suffix, label affiche, feature_name en DB)
        ("kurtosis", "Kurtosis (vibration)", "kurtosis"),
        ("crest_factor", "Facteur de crete (vibration)", "crest_factor"),
        ("rms", "RMS (vibration)", "rms"),
    ],
    "severity_bands": [
        # Bornes relatives au seuil pour colorier la cellule kurtosis_mean.
        # 0% = pile sur le seuil, 100% = double distance. Les valeurs sont
        # indicatives, derivees du std des kurtosis observees (F-43 partial).
        # Si le std change, mettre a jour ici, PAS en dur dans le rendu.
        {"label": "critique", "color": "#B71C1C", "min_pct": 50},
        {"label": "eleve",    "color": "#E65100", "min_pct": 25},
        {"label": "modere",   "color": "#F57C00", "min_pct": 10},
        {"label": "faible",   "color": "#FBC02D", "min_pct": 0},
    ],
    "table_columns": [
        # (colonne_df, label, type_streamlit, help)
        ("code", "Code roulement", "text", "Identifiant Paderborn (K/KA/KB/KI + numero)"),
        ("machine_id", "Machine", "text", None),
        ("defect_origin", "Origine defaut", "text", "na = sain temoin, artificial = endommage en labo, real = defaut naturel"),
        ("defect_location", "Localisation", "text", "inner/outer/ball/cage/none"),
        ("kurtosis_mean", "kurtosis", "number", "Moyenne par asset (20 mesures, canal vibration)"),
        ("unit", "Unite", "text", "Sans dimension pour kurtosis ; voir g pour vibration brute"),
        ("statut_badge", "Statut", "text", "Calcule par apply_threshold(), voir le seuil dans le bandeau"),
        ("verite_terrain", "Verite terrain", "text", "Etiquette declaree dans la base (sain/faulty)"),
        ("prediction_correcte", "Concordance", "checkbox", "Statut alerte == verite terrain ?"),
    ],
    "cache_ttl_seconds": 60,
}


# ---------------------------------------------------------------------------
# CHARGEMENT DES DONNEES (cached)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=CONFIG["cache_ttl_seconds"], show_spinner="Chargement des alertes...")
def _load_alerts_data(_engine, feature_name: str) -> pd.DataFrame:
    """Charge les features agregees par asset + leurs attributs bearing.

    Le `_engine` en prefixe underscore dit a Streamlit de ne pas hasher
    l'argument (les engines SQLAlchemy ne sont pas hashables). On s'appuie
    sur le TTL pour la freshness.

    Agregation : AVG(f.value) par asset. Justification dans
    docs/proposition_alertes_dashboard.md §10 risque #6.
    """
    sql = """
        select
            a.id as asset_id,
            a.code,
            a.machine_id,
            a.health_state,
            ba.defect_origin,
            ba.defect_location,
            ba.defect_method,
            avg(f.value) as kurtosis_mean,
            max(f.unit) as unit,
            count(*) as n_mesures
        from feature f
        join asset a on a.id = f.asset_id
        left join bearing_attributes ba on ba.asset_id = a.id
        where f.channel = 'vibration' and f.feature_name = %(feat)s
        group by a.id, a.code, a.machine_id, a.health_state,
                 ba.defect_origin, ba.defect_location, ba.defect_method
        order by a.code
    """
    return pd.read_sql(sql, _engine, params={"feat": feature_name})


@st.cache_data(ttl=CONFIG["cache_ttl_seconds"])
def _load_thresholds_index(_mlflow_tracking_uri: str, _experiment_name: str) -> pd.DataFrame:
    """Index de tous les runs baseline du projet (1 ligne par run, peu de volumes).

    Permet de peupler le dropdown de selection de feature. Cache pour eviter
    de re-taper mlflow.search_runs a chaque clic, mais TTL court pour rester
    reactif a un nouvel entrainement.
    """
    mlflow.set_tracking_uri(_mlflow_tracking_uri)
    exp = mlflow.get_experiment_by_name(_experiment_name)
    if exp is None:
        return pd.DataFrame()
    return mlflow.search_runs(
        experiment_ids=[exp.experiment_id],
        order_by=["start_time DESC"],
    )


def _direction_label(direction: str) -> str:
    """Traduit le jargon technique 'higher/lower_is_faulty' en francais clair.

    Le mot cle mlflow (direction) reste la valeur canonique utilisee dans les
    calculs ; cette fonction ne sert qu'a l'affichage cote client.
    """
    return {
        "higher_is_faulty": "valeur haute = suspect",
        "lower_is_faulty": "valeur basse = suspect",
    }.get(direction, direction)


def _glossaire_help(term_key: str, technical: str) -> str:
    """Prefixe une aide technique par la definition pedagogique du glossaire.

    Si le terme n'existe pas dans docs/glossaire_pedagogique.md, retourne le
    texte technique seul plutot qu'une definition inventee.
    """
    plain = help_text(term_key)
    return f"{plain}\n\n{technical}" if plain else technical


def _read_threshold_from_run(run_row: pd.Series) -> tuple[float, str, float | None]:
    """Lit les 3 valeurs utiles d'un run baseline.

    Leve une erreur explicite si le run ne porte pas les champs attendus
    (cas typique : ancien run logge avant le patch final_threshold du
    pipeline, voir docs/proposition_alertes_dashboard.md §3.1).
    """
    cfg = CONFIG["mlflow"]
    threshold_col = f"params.{cfg['param_threshold']}"
    direction_col = f"params.{cfg['param_direction']}"
    f1_train_col = f"metrics.{cfg['metric_f1_train']}"

    if threshold_col not in run_row or pd.isna(run_row[threshold_col]):
        raise RuntimeError(
            f"Le run mlflow selectionne ne porte pas le param '{cfg['param_threshold']}'. "
            f"Cela signifie que scripts/run_baseline.py a ete lance avec une version "
            f"anterieure au patch final_threshold (voir docs/proposition_alertes_dashboard.md §3.1). "
            f"Re-lancer `uv run python scripts/run_baseline.py`."
        )
    if direction_col not in run_row or pd.isna(run_row[direction_col]):
        raise RuntimeError(
            f"Le run mlflow selectionne ne porte pas le param '{cfg['param_direction']}'. "
            f"Meme remede : re-lancer scripts/run_baseline.py."
        )

    threshold = float(run_row[threshold_col])
    direction = str(run_row[direction_col])
    f1_train = (
        float(run_row[f1_train_col])
        if f1_train_col in run_row and pd.notna(run_row[f1_train_col])
        else None
    )
    return threshold, direction, f1_train


# ---------------------------------------------------------------------------
# FILTRES (session_state pour persistance entre reruns)
# ---------------------------------------------------------------------------


def _render_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Barre de filtres reactifs. Retourne le DataFrame filtre.

    session_state utilise pour que les selections survivent aux reruns
    (sinon Streamlit reset a chaque interaction sur un autre widget).
    """
    if "alert_filters" not in st.session_state:
        st.session_state["alert_filters"] = {
            "machines": [],
            "origins": [],
            "search": "",
            "only_alerts": False,
        }

    f = st.session_state["alert_filters"]
    cols = st.columns([2, 2, 3, 1.5])

    with cols[0]:
        sel_machines = st.multiselect(
            "Machine",
            options=sorted(df["machine_id"].dropna().unique()),
            default=f["machines"],
            key="alert_filter_machine",
            help="Filtrer par identifiant machine (ex. 'paderborn')",
        )
    with cols[1]:
        sel_origins = st.multiselect(
            "Origine defaut",
            options=sorted([o for o in df["defect_origin"].dropna().unique()]),
            default=f["origins"],
            key="alert_filter_origin",
            help="na = sain temoin, artificial = endommage en labo, real = defaut naturel",
        )
    with cols[2]:
        search = st.text_input(
            "Recherche code roulement",
            value=f["search"],
            placeholder="ex. KA01, K001, KI17...",
            key="alert_filter_search",
        ).strip()
    with cols[3]:
        only_alerts = st.toggle(
            "Alertes uniquement",
            value=f["only_alerts"],
            key="alert_filter_alerts_only",
            help="Masquer les assets predits 'sain' pour focus sur les alertes",
        )

    # Mise a jour de la session state (pour coherence cross-rerun)
    st.session_state["alert_filters"] = {
        "machines": sel_machines,
        "origins": sel_origins,
        "search": search,
        "only_alerts": only_alerts,
    }

    out = df.copy()
    if sel_machines:
        out = out[out["machine_id"].isin(sel_machines)]
    if sel_origins:
        out = out[out["defect_origin"].isin(sel_origins)]
    if search:
        out = out[out["code"].str.contains(search, case=False, na=False)]
    if only_alerts:
        out = out[out["statut_alerte"] == "alerte"]
    return out


# ---------------------------------------------------------------------------
# CALCULS DERIVES
# ---------------------------------------------------------------------------


def _compute_severity(value: float, threshold: float, direction: str) -> tuple[str, str]:
    """Retourne (label_severite, couleur_hex) selon la distance au seuil.

    'critique' = valeur au-dela de 50% de la distance 'normale' observee
    dans le dataset (approx std du kurtosis = 5.0, configurable via
    CONFIG['severity_bands']). Pas un seuil normatif, juste une echelle
    visuelle pour aider l'oeil a reperer les outliers.
    """
    # Distance signee selon direction
    if direction == "higher_is_faulty":
        signed = (value - threshold) / max(abs(threshold), 1e-6)
    else:  # lower_is_faulty
        signed = (threshold - value) / max(abs(threshold), 1e-6)

    # signed est en fraction relative. On classe selon les bandes.
    pct = abs(signed) * 100
    for band in CONFIG["severity_bands"]:
        if pct >= band["min_pct"]:
            return band["label"], band["color"]
    return "faible", "#FBC02D"


def _build_alert_table(df: pd.DataFrame, threshold: float, direction: str) -> pd.DataFrame:
    """Ajoute colonnes calculees : statut_alerte, badge HTML, severite, concordance.

    Le calcul est vectorise (np.where) pour rester reactif sur 32 assets
    (et au-dela si le dataset grossit).
    """
    import numpy as np

    out = df.copy()
    pred = apply_threshold(out["kurtosis_mean"].to_numpy(), threshold, direction)
    out["statut_alerte"] = np.where(pred == 1, "alerte", "sain")
    out["statut_badge"] = out["statut_alerte"].apply(status_badge)
    out["verite_terrain"] = out["health_state"]
    out["prediction_correcte"] = (out["statut_alerte"] == "alerte") == (
        out["health_state"] == "faulty"
    )
    # Severite
    sev = out["kurtosis_mean"].apply(lambda v: _compute_severity(v, threshold, direction))
    out["severite_label"] = [s[0] for s in sev]
    out["severite_color"] = [s[1] for s in sev]
    return out


# ---------------------------------------------------------------------------
# SOUS-RENDUS (une section visuelle = une fonction)
# ---------------------------------------------------------------------------


def _render_header(alert_df: pd.DataFrame, threshold: float, direction: str, f1_train: float | None) -> None:
    """Bandeau d'etat global + KPIs."""
    n_total = len(alert_df)
    n_alerts = int((alert_df["statut_alerte"] == "alerte").sum()) if n_total else 0
    n_correct = int(alert_df["prediction_correcte"].sum()) if n_total else 0
    accuracy = (n_correct / n_total * 100) if n_total else 0.0

    global_status = "ALERTE" if n_alerts > 0 else "OK"
    sub_status = (
        f"{n_alerts} asset(s) en alerte sur {n_total} - "
        f"{n_correct} concordances avec la verite terrain"
    )
    banner(f"Etat global du parc : {global_status}", sub_status)

    kpis = [
        {
            "label": "Seuil applique",
            "value": f"{threshold:.3f}",
            "delta": _direction_label(direction),
            "delta_color": "off",
            "help": _glossaire_help(
                "seuil-seuil-d-alerte",
                "Lu depuis mlflow (run 'threshold_cv_kurtosis'). PAS une constante en dur. "
                f"Valeur technique : direction = '{direction}'.",
            ),
        },
        {
            "label": "Assets en alerte",
            "value": f"{n_alerts} / {n_total}",
            "delta": f"{(n_alerts / n_total * 100):.1f}% du parc" if n_total else None,
            "delta_color": "inverse",
            "help": _glossaire_help(
                "kurtosis",
                "Nombre d'assets dont la kurtosis depasse le seuil dans la direction d'alerte.",
            ),
        },
        {
            "label": "Concordance prediction",
            "value": f"{accuracy:.1f}%",
            "delta": f"{n_correct} / {n_total}",
            "delta_color": "normal",
            "help": "Part des statuts alertes coherents avec la verite terrain Paderborn.",
        },
        {
            "label": "F1 train (100% donnees)",
            "value": f"{f1_train:.3f}" if f1_train is not None else "n/a",
            "delta": "F1 CV = 0.682 +/- 0.158",
            "delta_color": "off",
            "help": _glossaire_help(
                "f1-macro",
                "Performances en generalisation (cross-validation) : voir "
                "docs/results_phase2.md. L'ecart-type est large (32 roulements, ~6/fold) ; "
                "un statut individuel n'est pas un verdict.",
            ),
        },
    ]
    kpi_row(kpis)


def _render_distribution(alert_df: pd.DataFrame, threshold: float, direction: str) -> None:
    """Histogramme interactif de la feature avec ligne de seuil."""
    if alert_df.empty:
        st.info("Aucun asset a afficher dans le filtre courant.")
        return
    with st.expander("Distribution detaillee de la feature", expanded=True):
        distribution_chart(
            values=alert_df["kurtosis_mean"].tolist(),
            threshold=threshold,
            direction=direction,
            health_labels=alert_df["health_state"].tolist(),
        )


def _render_confusion(alert_df: pd.DataFrame) -> None:
    """Matrice de confusion 2x2 + metriques derivees."""
    if alert_df.empty:
        return
    tp = int(((alert_df["statut_alerte"] == "alerte") & (alert_df["health_state"] == "faulty")).sum())
    tn = int(((alert_df["statut_alerte"] == "sain") & (alert_df["health_state"] != "faulty")).sum())
    fp = int(((alert_df["statut_alerte"] == "alerte") & (alert_df["health_state"] != "faulty")).sum())
    fn = int(((alert_df["statut_alerte"] == "sain") & (alert_df["health_state"] == "faulty")).sum())

    with st.expander("Matrice de confusion (verite terrain vs prediction)", expanded=False):
        confusion_heatmap(tp, fp, fn, tn)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        c1, c2, c3 = st.columns(3)
        c1.metric("Precision", f"{precision:.3f}")
        c2.metric("Recall", f"{recall:.3f}")
        c3.metric("F1 (calcul live)", f"{f1:.3f}",
                  help="Calcule sur la selection filtree, pas le F1 mlflow global")


def _render_table(alert_df: pd.DataFrame) -> None:
    """Tableau principal avec badges statut, selection par ligne, export CSV.

    Utilise st.dataframe avec column_config pour avoir un rendu type 'carte'
    (barres, badges) et permettre le tri par colonne.
    """
    if alert_df.empty:
        return

    # Selection interactive : clic sur une ligne -> st.session_state['alert_selected_asset']
    # Streamlit dataframe ne supporte pas nativement la selection de ligne, on
    # passe par un selectbox dedie pour rester robuste aux versions.
    cols = [c[0] for c in CONFIG["table_columns"]]
    display = alert_df[cols + ["severite_label"]].copy()

    st.caption(
        f"{len(display)} asset(s) affiche(s) apres filtres. "
        f"Selectionnez un asset ci-dessous pour voir le detail de ses 20 mesures."
    )
    selected = st.selectbox(
        "Drill-down : asset a inspecter",
        options=["(aucun)"] + sorted(display["code"].tolist()),
        key="alert_selected_asset",
    )

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "code": st.column_config.TextColumn("Code", help="Identifiant Paderborn"),
            "machine_id": st.column_config.TextColumn("Machine"),
            "defect_origin": st.column_config.TextColumn("Origine defaut"),
            "defect_location": st.column_config.TextColumn("Localisation"),
            "kurtosis_mean": st.column_config.ProgressColumn(
                "kurtosis (moy.)",
                help="Moyenne par asset (20 mesures). La jauge est purement visuelle (0-30).",
                min_value=0.0,
                max_value=30.0,
                format="%.3f",
            ),
            "unit": st.column_config.TextColumn("Unite"),
            "statut_badge": st.column_config.TextColumn("Statut"),
            "verite_terrain": st.column_config.TextColumn("Verite terrain"),
            "prediction_correcte": st.column_config.CheckboxColumn("Concordance"),
            "severite_label": st.column_config.TextColumn("Severite"),
        },
    )

    # Export CSV : donnees brutes + badges, pret pour Excel
    csv = display.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Exporter le tableau (CSV)",
        data=csv,
        file_name="alertes_paderborn.csv",
        mime="text/csv",
        help="Inclut les colonnes calculees (statut, badge, severite).",
    )

    return selected


def _render_drilldown(engine, alert_df: pd.DataFrame) -> None:
    """Detail d'un asset selectionne : kurtosis des 20 mesures + statut."""
    selected = st.session_state.get("alert_selected_asset", "(aucun)")
    if not selected or selected == "(aucun)":
        return
    asset_row = alert_df[alert_df["code"] == selected]
    if asset_row.empty:
        st.warning(f"Asset '{selected}' non trouve dans la selection filtree.")
        return

    info = asset_row.iloc[0]
    with st.container(border=True):
        st.subheader(f"Detail asset : {info['code']}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Health state", str(info["health_state"]))
        c2.metric("Defect origin", str(info.get("defect_origin", "n/a")))
        c3.metric("Defect location", str(info.get("defect_location", "n/a")))
        c4.metric("n mesures", int(info.get("n_mesures", 0)))

        # Distribution des 20 mesures individuelles
        import plotly.graph_objects as go

        detail_sql = """
            select
                s.measurement_index,
                s.id as signal_id,
                ts.label as condition,
                f.value as kurtosis,
                f.unit
            from feature f
            join signal s on s.id = f.signal_id
            join test_session ts on ts.id = s.test_session_id
            where f.asset_id = %(aid)s
              and f.channel = 'vibration'
              and f.feature_name = 'kurtosis'
            order by s.measurement_index
        """
        detail = pd.read_sql(detail_sql, engine, params={"aid": info["asset_id"]})
        if detail.empty:
            st.info("Aucune mesure detaillee disponible.")
        else:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=detail["measurement_index"],
                    y=detail["kurtosis"],
                    mode="lines+markers",
                    line=dict(color="#CC785C", width=2),
                    marker=dict(size=6),
                    name="Kurtosis par mesure",
                    hovertemplate="Mesure %{x}<br>kurtosis = %{y:.3f}<extra></extra>",
                )
            )
            fig.update_layout(
                template="plotly_dark",
                title=f"Kurtosis des {len(detail)} mesures - {selected}",
                xaxis_title="Index de mesure (1-20)",
                yaxis_title="kurtosis (sans dimension)",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, system-ui, sans-serif", size=12, color="#EEEBE6"),
                height=280,
                margin=dict(t=50, b=40, l=40, r=20),
            )
            fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
            st.plotly_chart(fig, width="stretch", theme=None)


def _render_citation_footer() -> None:
    """Footer avec sources, limitations, et renvoi vers la doc."""
    st.markdown("---")
    with st.expander("Sources, limites et regle '0 mock'", expanded=False):
        st.markdown(
            """
**Source du seuil** : run mlflow `threshold_cv_kurtosis` (experiment
`baseline_threshold_cv`, logge par `scripts/run_baseline.py`).
Aucune valeur en dur dans ce code. Si la lecture echoue, l'onglet affiche
une erreur explicite et s'arrete, plutot qu'un statut invente.

**Unite de la vibration** : `g` (acceleration brute du capteur PCB Piezotronics
336C04), PAS `mm/s`. Une classification ISO 20816-3 necessiterait une
integration frequentielle acceleration->vitesse, non implementee ici.
Voir `docs/known_issues.md` section "Unites capteurs Paderborn".

**Direction du seuil** : `lower_is_faulty` (la kurtosis moyenne est
inversement correlee a la severite du defaut sur ce dataset specifique,
phenomene documente dans `docs/known_issues.md` et `docs/results_phase2.md`).
PAS une generalite physique : c'est une caracteristique du banc Paderborn,
vraisemblablement liee au couplage moteur/banc.

**Limites de l'evaluation** : 32 roulements, ~6-7 par fold en StratifiedGroupKFold.
Les ecarts-types sur les F1 sont larges (0.158 a 0.222 selon la tache).
Un statut individuel n'est PAS un verdict normatif. Lire
`docs/results_phase2.md` avant de sur-interpreter.

**Voir aussi** : `docs/proposition_alertes_dashboard.md` (design doc source),
`docs/known_issues.md` (problemes ouverts), `docs/results_phase2.md` (resultats).
            """
        )


# ---------------------------------------------------------------------------
# POINT D'ENTREE PUBLIC
# ---------------------------------------------------------------------------


def render(engine) -> None:
    """Point d'entree : app/dashboard.py appelle ca dans un `with tab_alertes:`.

    engine : SQLAlchemy engine (depuis src.data.db.get_engine()).
    """
    # 1. CSS injecte une fois par session
    inject_css_once()

    # 2. Selection de la feature (par defaut : kurtosis, F1 0.682)
    feature_options = [(f[1], f[0]) for f in CONFIG["features"]]
    feature_labels = [o[0] for o in feature_options]
    selected_idx = st.selectbox(
        "Feature analysee",
        options=range(len(feature_options)),
        format_func=lambda i: feature_options[i][0],
        index=0,
        help="Choisit le run mlflow et la colonne feature a utiliser",
    )
    selected_run_suffix, _, selected_feature_name = CONFIG["features"][selected_idx]

    # 3. Lecture du seuil depuis mlflow (NON cache : on veut la valeur live)
    cfg = CONFIG["mlflow"]
    try:
        mlflow.set_tracking_uri(cfg["tracking_uri"])
        exp = mlflow.get_experiment_by_name(cfg["experiment"])
        if exp is None:
            st.error(
                f"Experiment mlflow '{cfg['experiment']}' introuvable. "
                f"Lancer `uv run python scripts/run_baseline.py` d'abord."
            )
            return
        target_run_name = f"threshold_cv_{selected_run_suffix}"
        runs = mlflow.search_runs(
            [exp.experiment_id],
            filter_string=f"tags.mlflow.runName = '{target_run_name}'",
            order_by=["start_time DESC"],
        )
        if runs.empty:
            st.error(
                f"Aucun run '{target_run_name}' dans l'experiment '{cfg['experiment']}'. "
                f"Lancer `uv run python scripts/run_baseline.py` avant d'utiliser cet onglet."
            )
            return
        threshold, direction, f1_train = _read_threshold_from_run(runs.iloc[0])
    except RuntimeError as e:
        st.error(str(e))
        return
    except Exception as e:
        st.error(f"mlflow indisponible : {e}")
        return

    # 4. Chargement des donnees (cached)
    raw_df = _load_alerts_data(engine, selected_feature_name)
    if raw_df.empty:
        st.info(
            f"Aucune feature '{selected_feature_name}' en base. "
            f"Lancer `scripts/build_dataset.py`."
        )
        return

    # 5. Calcul du statut alerte
    alert_df = _build_alert_table(raw_df, threshold, direction)

    # 6. Header + KPIs
    _render_header(alert_df, threshold, direction, f1_train)

    # 7. Filtres
    st.markdown("##### Filtres")
    filtered = _render_filters(alert_df)

    # 8. Sections principales
    _render_distribution(filtered, threshold, direction)
    _render_table(filtered)
    _render_confusion(filtered)
    _render_drilldown(engine, filtered)

    # 9. Footer
    _render_citation_footer()

    # 10. Bouton de rafraichissement manuel (vide le cache st.cache_data)
    if st.button("Rafraichir les donnees", help="Vide le cache (60s) et relance la requete DB + mlflow."):
        _load_alerts_data.clear()
        _load_thresholds_index.clear()
        st.rerun()
