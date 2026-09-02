"""Composants UI reutilisables pour les onglets du dashboard.

Objectif : eviter la duplication de widgets Streamlit entre onglets, garder
un rendu homogene, et permettre de faire evoluer le look (palette, CSS)
depuis un seul endroit.

Tous les composants sont des fonctions pures : ils prennent les donnees en
entree et produisent du HTML/Streamlit en sortie, sans etat cache propre.
L'etat partage (filtres, selections) reste dans st.session_state au niveau
de l'onglet appelant.
"""

from __future__ import annotations

import html
from collections.abc import Iterable, Sequence

import pandas as pd
import streamlit as st

from app.tabs._styles import PALETTE, STATUS_COLOR


def inject_css_once() -> None:
    """Injecte le CSS global une seule fois par session Streamlit.

    Le flag session_state evite la reinjection a chaque rerun, qui ferait
    scintiller l'UI.
    """
    if st.session_state.get("_alertes_css_injected"):
        return
    from app.tabs._styles import CARD_CSS
    st.html(CARD_CSS)
    st.session_state["_alertes_css_injected"] = True


def banner(title: str, subtitle: str = "") -> None:
    """Bandeau d'en-tete colore (utilise pour 'etat global du parc')."""
    sub_html = (
        f'<p class="alert-banner-sub">{html.escape(subtitle)}</p>' if subtitle else ""
    )
    st.markdown(
        f'<div class="alert-banner">'
        f'<p class="alert-banner-title">{html.escape(title)}</p>'
        f"{sub_html}"
        f"</div>",
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    """Retourne le HTML d'un badge statut (alerte / sain / warning).

    Le resultat est destine a etre injecte dans une cellule de dataframe via
    st.column_config.TextColumn ou directement via du HTML si Streamlit ne
    le supporte pas (cf. l'usage dans render_table).
    """
    status_norm = status.lower().strip()
    color_class = {
        "alerte": "alert-badge-crit",
        "sain": "alert-badge-ok",
        "warning": "alert-badge-warn",
    }.get(status_norm, "alert-badge-ok")
    label = {
        "alerte": "Alerte",
        "sain": "Sain",
        "warning": "Surveillance",
    }.get(status_norm, status_norm.capitalize())
    return f'<span class="alert-badge {color_class}">{html.escape(label)}</span>'


def kpi_row(metrics: Sequence[dict]) -> None:
    """Affiche une rangee de KPIs (cartes Streamlit natives, style custom).

    metrics : liste de dicts {"label": str, "value": str, "delta": str|None,
    "delta_color": "normal"|"inverse"|"off", "help": str|None}.
    """
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            st.metric(
                label=m["label"],
                value=m["value"],
                delta=m.get("delta"),
                delta_color=m.get("delta_color", "normal"),
                help=m.get("help"),
            )


def confusion_heatmap(tp: int, fp: int, fn: int, tn: int) -> None:
    """Affiche une matrice de confusion 2x2 sous forme de barplot empile.

    Streamlit natif n'a pas de heatmap conf matrix ; on utilise plotly via
    st.plotly_chart pour avoir une viz interactive (hover = valeur exacte).
    """
    import plotly.graph_objects as go

    fig = go.Figure(
        data=[
            go.Bar(
                x=["Predit sain", "Predit faulty"],
                y=[tn, fn],
                name="Verite terrain : sain",
                marker_color=PALETTE.ok,
                text=[f"VN={tn}", f"FN={fn}"],
                textposition="inside",
                hovertemplate="<b>%{x}</b><br>Sain reel : %{y}<extra></extra>",
            ),
            go.Bar(
                x=["Predit sain", "Predit faulty"],
                y=[fp, tp],
                name="Verite terrain : faulty",
                marker_color=PALETTE.crit,
                text=[f"FP={fp}", f"VP={tp}"],
                textposition="inside",
                hovertemplate="<b>%{x}</b><br>Faulty reel : %{y}<extra></extra>",
            ),
        ]
    )
    fig.update_layout(
        template="plotly_dark",
        barmode="stack",
        title="Matrice de confusion (verite terrain vs prediction)",
        xaxis_title="Prediction",
        yaxis_title="Nombre d'assets",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color=PALETTE.text_primary),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40, l=40, r=20),
        height=320,
    )
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
    st.plotly_chart(fig, width="stretch", theme=None)


def distribution_chart(
    values: Iterable[float],
    threshold: float,
    direction: str,
    health_labels: Iterable[str] | None = None,
) -> None:
    """Histogramme interactif de la feature avec ligne de seuil.

    Affiche aussi (en couleur de fond) la zone d'alerte selon la direction :
    - higher_is_faulty : zone droite (>= seuil) en rouge clair
    - lower_is_faulty  : zone gauche (<= seuil) en rouge clair
    """
    import plotly.graph_objects as go

    arr = list(values)
    if not arr:
        st.info("Aucune valeur a afficher.")
        return

    is_alert = (
        (pd.Series(arr) >= threshold).to_numpy()
        if direction == "higher_is_faulty"
        else (pd.Series(arr) <= threshold).to_numpy()
    )

    # Couleur par point selon statut (sain reel = vert, faulty reel = rouge, etc.)
    point_colors = []
    if health_labels is not None:
        for hl in health_labels:
            hl_norm = (hl or "").lower()
            if hl_norm == "faulty":
                point_colors.append(PALETTE.crit)
            elif hl_norm == "healthy":
                point_colors.append(PALETTE.ok)
            else:
                point_colors.append(PALETTE.neutral)
    else:
        point_colors = [STATUS_COLOR["alerte"] if a else STATUS_COLOR["sain"] for a in is_alert]

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=arr,
            nbinsx=20,
            marker_color=PALETTE.accent_light,
            marker_line_color=PALETTE.accent,
            marker_line_width=1,
            opacity=0.85,
            name="Distribution",
            hovertemplate="Borne : %{x}<br>Nb assets : %{y}<extra></extra>",
        )
    )
    # Points individuels (rugplot-like) colores par verite terrain
    fig.add_trace(
        go.Scatter(
            x=arr,
            y=[0] * len(arr),
            mode="markers",
            marker=dict(
                color=point_colors,
                size=10,
                line=dict(color="white", width=1.5),
                symbol="diamond",
            ),
            name="Assets (couleur = verite terrain)",
            hovertemplate="Valeur : %{x:.3f}<br>Sain/faulty : %{marker.color}<extra></extra>",
            showlegend=True,
        )
    )
    # Ligne de seuil verticale
    fig.add_vline(
        x=threshold,
        line=dict(color=PALETTE.crit, width=2.5, dash="dash"),
        annotation_text=f"Seuil = {threshold:.3f}",
        annotation_position="top right",
        annotation_font=dict(color=PALETTE.crit, size=12, family="Inter, system-ui, sans-serif"),
    )
    direction_label = {
        "higher_is_faulty": "valeur haute = suspect",
        "lower_is_faulty": "valeur basse = suspect",
    }.get(direction, direction)
    fig.update_layout(
        template="plotly_dark",
        title=f"Distribution de la feature et seuil d'alerte ({direction_label})",
        xaxis_title="Valeur de la feature",
        yaxis_title="Nombre d'assets",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color=PALETTE.text_primary),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=80, b=40, l=40, r=20),
        height=360,
        bargap=0.05,
    )
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
    st.plotly_chart(fig, width="stretch", theme=None)
