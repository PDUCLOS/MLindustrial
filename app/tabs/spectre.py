"""Onglet 'Spectre' - navigation temporelle + spectre reel + alertes + correction.

Regle 0-mock enforcee : le spectre vient d'un vrai fichier parquet (jamais
simule), le seuil d'alerte vient d'un run mlflow reel (meme pattern que
app/tabs/alertes.py), et le texte "cause probable" ne cite que des faits
deja sources dans docs/known_issues.md - jamais un diagnostic invente.

Structure : colonne de navigation (asset, feature, mesure, caracteristiques
+ formulaire de correction) + colonne principale (serie temporelle avec
seuil, spectre de la mesure selectionnee, texte de cause probable).

La correction ecrit reellement en base (Asset.health_state,
BearingAttributes.defect_*) et journalise un MaintenanceEvent - jamais un
override silencieux, toujours une trace auditable (meme table que l'onglet
"Journal maintenance" du dashboard principal).
"""

from __future__ import annotations

from datetime import datetime

import mlflow
import numpy as np
import pandas as pd
import streamlit as st

from app.tabs._components import inject_css_once
from app.tabs._styles import PALETTE, STATUS_COLOR, style_figure
from app.tabs.alertes import CONFIG as ALERTES_CONFIG
from app.tabs.alertes import _read_threshold_from_run
from src.data.db import Asset, BearingAttributes, MaintenanceEvent, get_session
from src.features.fault_frequencies import all_fault_frequencies
from src.models.baseline import apply_threshold

HEALTH_STATES = ["healthy", "faulty", "degraded", "unknown"]
DEFECT_ORIGINS = ["na", "artificial", "real"]
DEFECT_LOCATIONS = ["none", "inner", "outer", "ball", "both"]

FAULT_LINE_COLORS = {"BPFO": "#EF5350", "BPFI": "#FFA726", "BSF": "#66BB6A", "FTF": "#8C4A32"}


# ---------------------------------------------------------------------------
# CHARGEMENT DES DONNEES
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60, show_spinner=False)
def _load_bearing_codes(_engine) -> list[str]:
    df = pd.read_sql(
        "select code from asset where asset_type = 'bearing' order by code", _engine
    )
    return df["code"].tolist()


def _load_asset_characteristics(_engine, code: str) -> pd.Series:
    """Toutes les caracteristiques connues d'un asset - une seule requete,
    pas de N+1 (asset + bearing_attributes + bearing_geometry + machine)."""
    df = pd.read_sql(
        """
        select a.id as asset_id, a.code, a.health_state, a.machine_id,
               ba.defect_origin, ba.defect_location, ba.defect_method, ba.geometry_model,
               bg.n_balls, bg.ball_diameter_mm, bg.pitch_diameter_mm, bg.contact_angle_deg,
               m.name as machine_name, m.source as machine_source
        from asset a
        left join bearing_attributes ba on ba.asset_id = a.id
        left join bearing_geometry bg on bg.model = ba.geometry_model
        left join machine m on m.id = a.machine_id
        where a.code = %(code)s
        """,
        _engine,
        params={"code": code},
    )
    if df.empty:
        raise ValueError(f"Asset introuvable pour code={code!r}.")
    return df.iloc[0]


@st.cache_data(ttl=60, show_spinner="Chargement de la serie temporelle...")
def _load_measurement_series(_engine, asset_id: str, feature_name: str) -> pd.DataFrame:
    """Une ligne par mesure : valeur de la feature + reference au signal brut
    (file_path, sampling_rate_hz) pour pouvoir tracer le spectre plus tard."""
    return pd.read_sql(
        """
        select f.timestamp, f.value, f.signal_id,
               s.file_path, s.sampling_rate_hz, s.measurement_index,
               ts.label as condition, ts.rotational_speed_rpm
        from feature f
        join signal s on s.id = f.signal_id
        join test_session ts on ts.id = s.test_session_id
        where f.asset_id = %(aid)s and f.channel = 'vibration' and f.feature_name = %(feat)s
        order by f.timestamp
        """,
        _engine,
        params={"aid": asset_id, "feat": feature_name},
    )


def _load_threshold(feature_name: str) -> tuple[float, str, str] | None:
    """Meme lecture mlflow que app/tabs/alertes.py (reutilise sa CONFIG et
    son parseur de run pour ne pas dupliquer la logique de seuil)."""
    run_suffix = next(
        (f[0] for f in ALERTES_CONFIG["features"] if f[2] == feature_name), None
    )
    if run_suffix is None:
        return None
    cfg = ALERTES_CONFIG["mlflow"]
    try:
        mlflow.set_tracking_uri(cfg["tracking_uri"])
        exp = mlflow.get_experiment_by_name(cfg["experiment"])
        if exp is None:
            return None
        target_run_name = f"threshold_cv_{run_suffix}"
        runs = mlflow.search_runs(
            [exp.experiment_id],
            filter_string=f"tags.mlflow.runName = '{target_run_name}'",
            order_by=["start_time DESC"],
        )
        if runs.empty:
            return None
        threshold, direction, _ = _read_threshold_from_run(runs.iloc[0])
        return threshold, direction, target_run_name
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CALCUL SPECTRE + CAUSE PROBABLE
# ---------------------------------------------------------------------------


def _compute_spectrum(file_path: str, sampling_rate_hz: float) -> tuple[np.ndarray, np.ndarray]:
    arr = pd.read_parquet(file_path)["vibration"].to_numpy()
    n = len(arr)
    freqs = np.fft.rfftfreq(n, d=1 / sampling_rate_hz)
    spectrum = np.abs(np.fft.rfft(arr)) / n
    return freqs, spectrum


def _theoretical_fault_frequencies(asset_info: pd.Series, rpm: float | None) -> dict[str, float]:
    if not rpm or pd.isna(asset_info.get("n_balls")):
        return {}
    return all_fault_frequencies(
        int(asset_info["n_balls"]), rpm,
        asset_info["ball_diameter_mm"], asset_info["pitch_diameter_mm"],
        asset_info.get("contact_angle_deg") or 0.0,
    )


def _probable_cause_text(row: pd.Series, asset_info: pd.Series, feature_name: str, is_alert: bool) -> str:
    """Texte de cause probable - UNIQUEMENT des faits deja sources dans
    docs/known_issues.md ou docs/theorie_reference.md, jamais une inference
    nouvelle. Objectif : la meme discipline qu'un rapport d'atelier, pas un
    modele de diagnostic automatique."""
    if not is_alert:
        return "Valeur dans la plage attendue par rapport au seuil - pas d'alerte sur cette mesure."

    reasons: list[str] = []

    rpm = row.get("rotational_speed_rpm")
    if rpm and abs(float(rpm) - 1500.0) < 1e-6:
        reasons.append(
            "Condition à 1500 tr/min : 2× la fréquence de rotation = 50 Hz = fréquence "
            "secteur EU exactement. Un désalignement (signature 2×) est indiscernable "
            "d'une contamination électrique dans le spectre vibratoire seul à cette "
            "vitesse (voir docs/known_issues.md)."
        )

    if feature_name == "kurtosis":
        reasons.append(
            "Sur ce dataset, la kurtosis brute est globalement INVERSEMENT corrélée à "
            "la sévérité du défaut (moyenne sain > artificiel > réel) — une valeur "
            "basse peut correspondre à un défaut réel actif, pas à un signal propre "
            "(voir docs/known_issues.md)."
        )

    origin = asset_info.get("defect_origin")
    if origin == "real":
        loc = asset_info.get("defect_location") or "non précisée"
        reasons.append(f"Roulement à défaut RÉEL confirmé (vérité terrain), localisation : {loc}.")
    elif origin == "artificial":
        reasons.append(
            "Roulement à défaut artificiel (usiné) — signature différente d'une usure "
            "naturelle diffuse, voir docs/theorie_reference.md §6 (généralisation "
            "artificiel→réel)."
        )
    elif origin == "na":
        reasons.append(
            "Roulement étiqueté SAIN — une alerte ici est probablement un artefact "
            "(contamination secteur/banc déjà documentée) plutôt qu'un vrai défaut, "
            "voir docs/known_issues.md."
        )

    if not reasons:
        reasons.append(
            "Pas d'hypothèse causale spécifique disponible pour cette mesure - voir "
            "docs/known_issues.md pour les pistes générales (contamination secteur, "
            "kurtogramme en cours de fiabilisation)."
        )
    return " ".join(reasons)


# ---------------------------------------------------------------------------
# RENDU
# ---------------------------------------------------------------------------


def _render_navigation(engine, codes: list[str]) -> tuple[str, str, pd.Series, pd.DataFrame, int]:
    st.markdown("### Navigation")
    asset_code = st.selectbox("Roulement", codes, key="spectre_asset")
    feature_name = st.selectbox(
        "Feature (série temporelle)",
        [f[2] for f in ALERTES_CONFIG["features"]],
        format_func=lambda f: next(lbl for _, lbl, ff in ALERTES_CONFIG["features"] if ff == f),
        key="spectre_feature",
    )

    asset_info = _load_asset_characteristics(engine, asset_code)
    series = _load_measurement_series(engine, asset_info["asset_id"], feature_name)

    if series.empty:
        st.warning(f"Aucune mesure '{feature_name}' pour {asset_code}.")
        return asset_code, feature_name, asset_info, series, -1

    threshold_info = _load_threshold(feature_name)
    default_idx = 0
    if threshold_info is not None:
        threshold, direction, _ = threshold_info
        preds = apply_threshold(series["value"].to_numpy(), threshold, direction)
        alert_positions = np.where(preds == 1)[0]
        if len(alert_positions) > 0:
            default_idx = int(alert_positions[0])

    idx = st.select_slider(
        "Mesure (navigation temporelle)",
        options=list(range(len(series))),
        value=default_idx,
        format_func=lambda i: f"#{i+1}/{len(series)} — {series['timestamp'].iloc[i]:%Y-%m-%d %H:%M} ({series['condition'].iloc[i]})",
        key="spectre_idx",
    )

    st.markdown("### Caractéristiques")
    st.markdown(
        f"**Code** : {asset_info['code']}  \n"
        f"**Machine** : {asset_info['machine_name']} ({asset_info['machine_source']})  \n"
        f"**État de santé** : {asset_info['health_state']}  \n"
        f"**Origine défaut** : {asset_info.get('defect_origin') or '—'}  \n"
        f"**Localisation défaut** : {asset_info.get('defect_location') or '—'}  \n"
        f"**Méthode défaut** : {asset_info.get('defect_method') or '—'}  \n"
        f"**Géométrie** : {asset_info.get('geometry_model') or '—'} "
        f"({int(asset_info['n_balls']) if pd.notna(asset_info.get('n_balls')) else '?'} billes, "
        f"⌀bille {asset_info.get('ball_diameter_mm', '?')} mm, "
        f"⌀primitif {asset_info.get('pitch_diameter_mm', '?')} mm)"
    )

    with st.expander("Corriger les caractéristiques"):
        st.caption(
            "Écrit réellement en base et journalise la correction dans le "
            "journal de maintenance (traçabilité, jamais un override silencieux)."
        )
        with st.form(f"correction_form_{asset_code}"):
            new_health = st.selectbox(
                "État de santé", HEALTH_STATES,
                index=HEALTH_STATES.index(asset_info["health_state"])
                if asset_info["health_state"] in HEALTH_STATES else 0,
            )
            new_origin = st.selectbox(
                "Origine défaut", DEFECT_ORIGINS,
                index=DEFECT_ORIGINS.index(asset_info["defect_origin"])
                if asset_info.get("defect_origin") in DEFECT_ORIGINS else 0,
            )
            new_location = st.selectbox(
                "Localisation défaut", DEFECT_LOCATIONS,
                index=DEFECT_LOCATIONS.index(asset_info["defect_location"])
                if asset_info.get("defect_location") in DEFECT_LOCATIONS else 0,
            )
            new_method = st.text_input("Méthode défaut", value=asset_info.get("defect_method") or "")
            corrector = st.text_input("Corrigé par")
            note = st.text_area("Motif de la correction")
            submitted = st.form_submit_button("Enregistrer la correction")

            if submitted:
                changes = []
                with get_session(engine) as s:
                    asset_obj = s.get(Asset, asset_info["asset_id"])
                    if asset_obj.health_state != new_health:
                        changes.append(f"health_state: {asset_obj.health_state} -> {new_health}")
                        asset_obj.health_state = new_health

                    ba = s.get(BearingAttributes, asset_info["asset_id"])
                    if ba is not None:
                        if (ba.defect_origin or "na") != new_origin:
                            changes.append(f"defect_origin: {ba.defect_origin} -> {new_origin}")
                            ba.defect_origin = new_origin
                        if (ba.defect_location or "none") != new_location:
                            changes.append(f"defect_location: {ba.defect_location} -> {new_location}")
                            ba.defect_location = new_location
                        if (ba.defect_method or "") != new_method:
                            changes.append(f"defect_method: {ba.defect_method} -> {new_method}")
                            ba.defect_method = new_method

                    if changes:
                        s.add(MaintenanceEvent(
                            asset_id=asset_info["asset_id"],
                            timestamp=datetime.now(),
                            event_type="system_modification",
                            description="Correction manuelle : " + "; ".join(changes)
                            + (f" — {note}" if note else ""),
                            reported_by=corrector or None,
                        ))
                        s.commit()
                        st.success(f"{len(changes)} champ(s) corrigé(s), journalisé dans le journal de maintenance.")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.info("Aucun changement détecté.")

    return asset_code, feature_name, asset_info, series, idx


def _render_timeseries(series: pd.DataFrame, feature_name: str, selected_idx: int) -> None:
    import plotly.graph_objects as go

    threshold_info = _load_threshold(feature_name)
    colors = [PALETTE.text_secondary] * len(series)
    is_alert = np.zeros(len(series), dtype=bool)

    if threshold_info is not None:
        threshold, direction, run_name = threshold_info
        preds = apply_threshold(series["value"].to_numpy(), threshold, direction)
        is_alert = preds == 1
        colors = [STATUS_COLOR["alerte"] if a else STATUS_COLOR["sain"] for a in is_alert]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=series["timestamp"], y=series["value"], mode="markers",
        marker=dict(color=colors, size=7),
        name=feature_name,
        hovertemplate="%{x}<br>valeur=%{y:.3f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[series["timestamp"].iloc[selected_idx]], y=[series["value"].iloc[selected_idx]],
        mode="markers", marker=dict(color=PALETTE.accent, size=14, symbol="star",
                                     line=dict(color=PALETTE.text_primary, width=1)),
        name="mesure sélectionnée",
        hovertemplate="Sélection : %{x}<br>valeur=%{y:.3f}<extra></extra>",
    ))
    if threshold_info is not None:
        threshold, direction, run_name = threshold_info
        fig.add_hline(
            y=threshold, line_dash="dash", line_color=PALETTE.warn,
            annotation_text=f"seuil {run_name} ({threshold:.3f})",
        )

    fig.update_layout(
        template="plotly_dark",
        title=f"Série temporelle — {feature_name}, chronologie réelle des mesures",
        xaxis_title="Date d'essai réelle", yaxis_title=feature_name,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color=PALETTE.text_primary),
        height=380, margin=dict(t=60, b=40, l=40, r=20),
    )
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
    st.plotly_chart(fig, width="stretch", theme=None)

    return is_alert


def _render_spectrum_and_cause(
    asset_info: pd.Series, feature_name: str, row: pd.Series, is_alert: bool,
) -> None:
    import matplotlib.pyplot as plt

    freqs, spectrum = _compute_spectrum(row["file_path"], row["sampling_rate_hz"])
    theo = _theoretical_fault_frequencies(asset_info, row.get("rotational_speed_rpm"))

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(freqs, spectrum, linewidth=0.7, color=PALETTE.text_primary)
    ax.set_xlim(0, 500)
    ax.set_xlabel("Fréquence (Hz)")
    ax.set_ylabel("Amplitude")
    ax.set_title(
        f"Spectre — {asset_info['code']} ({asset_info['health_state']}), "
        f"{row['condition']}, mesure #{int(row['measurement_index'])}"
    )
    for name, f in theo.items():
        ax.axvline(f, color=FAULT_LINE_COLORS.get(name, "gray"), linestyle="--", alpha=0.7,
                    label=f"{name} théo. ({f:.1f} Hz)")
    if theo:
        ax.legend()
    style_figure(fig, ax)
    st.pyplot(fig)

    st.caption(
        "Les raies théoriques sont une référence de calcul (géométrie réelle + "
        "vitesse de la condition), pas une détection — voir docs/theorie_reference.md §3 "
        "(le spectre brut ne montre pas nécessairement ces raies, d'où l'analyse d'enveloppe)."
    )

    st.markdown("#### Cause probable")
    cause = _probable_cause_text(row, asset_info, feature_name, is_alert)
    if is_alert:
        st.warning(cause)
    else:
        st.info(cause)


def render(engine) -> None:
    """Point d'entrée : app/dashboard.py appelle ça dans un `with tab_spectre:`."""
    inject_css_once()
    st.caption(
        "Navigation dans les mesures d'un roulement, seuil d'alerte entraîné (mlflow), "
        "spectre réel de la mesure sélectionnée avec fréquences caractéristiques "
        "théoriques, et cause probable sourcée depuis docs/known_issues.md."
    )

    codes = _load_bearing_codes(engine)
    if not codes:
        st.info("Aucun roulement en base. Lancer `scripts/build_dataset.py`.")
        return

    nav_col, main_col = st.columns([1, 2.2])

    with nav_col:
        asset_code, feature_name, asset_info, series, idx = _render_navigation(engine, codes)

    if series.empty or idx < 0:
        return

    with main_col:
        is_alert_arr = _render_timeseries(series, feature_name, idx)
        row = series.iloc[idx]
        is_alert = bool(is_alert_arr[idx]) if len(is_alert_arr) else False
        _render_spectrum_and_cause(asset_info, feature_name, row, is_alert)
