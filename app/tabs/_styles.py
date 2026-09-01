"""Constantes de style partagees entre les onglets.

Theme sombre chaud, coherent avec la palette deja validee dans
`.streamlit/config.toml` et injectee globalement par `app/dashboard.py`
(accent terracotta #CC785C, fond #1A1815/#26221D, texte #EEEBE6). Le CSS
Streamlit est global au document : une palette differente ici repeindrait
TOUT le dashboard, pas seulement cet onglet - ne jamais definir de couleurs
independantes du theme central.

Note 0-mock : aucune couleur n'est "plausible" sans raison ; les valeurs de
severite (rouge/ambre/vert) proviennent de codes hex cites (Material Design
3, variantes 400 choisies pour le contraste sur fond sombre). Si on change
un code, on documente ici la source.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """Palette centralisee pour eviter les magic strings dans le JSX-like."""

    # Severite (rouge ambre vert, semantique universelle en supervision) -
    # variantes 400 (plus claires que les 700 d'origine) pour rester lisibles
    # sur fond sombre, pas juste une preference esthetique.
    crit: str = "#EF5350"          # Material Red 400
    warn: str = "#FFA726"          # Material Orange 400
    ok: str = "#66BB6A"            # Material Green 400
    neutral: str = "#9E9E9E"       # Material Grey 500

    # Texte - repris de .streamlit/config.toml, pas de valeur independante
    text_primary: str = "#EEEBE6"
    text_secondary: str = "#A8A296"
    text_inverse: str = "#1A1815"

    # Fond - repris de .streamlit/config.toml
    bg_card: str = "#26221D"
    bg_subtle: str = "#211D19"
    bg_overlay: str = "#FFFFFF11"  # overlay blanc 7% pour hover sur fond sombre

    # Accent - terracotta du theme central, pas un bleu independant
    accent: str = "#CC785C"
    accent_light: str = "rgba(204, 120, 92, 0.12)"


PALETTE = Palette()


# Card CSS : utilise les memes variables que le theme central. L'injection se
# fait via st.html() (pas st.markdown(unsafe_allow_html=True) - coherent avec
# le fix applique dans app/dashboard.py pour eviter l'interpretation
# Markdown de l'indentation comme bloc de code).
CARD_CSS = """
<style>
/* Cards KPI : ombre douce, coins arrondis, padding leger - complementaire au
   style deja injecte globalement par dashboard.py, pas une redefinition. */
div[data-testid="stMetric"] {
    box-shadow: 0 1px 3px rgba(0,0,0,0.24), 0 1px 2px rgba(0,0,0,0.16);
    transition: box-shadow 0.18s ease, transform 0.18s ease;
}
div[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 8px rgba(0,0,0,0.32), 0 2px 4px rgba(0,0,0,0.20);
    transform: translateY(-1px);
}

/* Badge statut : pillule arrondie, fond translucide + texte de la couleur
   pleine (lisible sur fond sombre, contrairement a un fond pastel clair). */
.alert-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    line-height: 1.6;
}
.alert-badge-crit { background: rgba(239, 83, 80, 0.16); color: #EF5350; }
.alert-badge-ok   { background: rgba(102, 187, 106, 0.16); color: #66BB6A; }
.alert-badge-warn { background: rgba(255, 167, 38, 0.16); color: #FFA726; }

/* Bandeau d'en-tete : degrade sombre + accent terracotta, coherent avec le
   theme central plutot qu'un bleu/violet independant. */
.alert-banner {
    background: linear-gradient(135deg, rgba(204, 120, 92, 0.14) 0%, rgba(204, 120, 92, 0.04) 100%);
    border-left: 4px solid #CC785C;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 12px;
}
.alert-banner-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #EEEBE6;
    margin: 0 0 2px 0;
}
.alert-banner-sub {
    font-size: 0.85rem;
    color: #A8A296;
    margin: 0;
}

/* Tableau : cellules compactes + separation douce. */
div[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow: hidden;
}
</style>
"""
# Note : la regle "onglet actif" (button[role="tab"][aria-selected="true"])
# a ete retiree d'ici volontairement - le style des onglets appartient a
# app/dashboard.py (defini une seule fois, globalement), la dupliquer ici
# avec !important aurait ecrase l'accent terracotta du theme central sur
# les 9 onglets du dashboard, pas seulement celui-ci.


# Mapping statut -> couleur (utilise par les composants et plotly).
STATUS_COLOR = {
    "alerte": PALETTE.crit,
    "sain": PALETTE.ok,
    "warning": PALETTE.warn,
}

# Mapping defect_origin -> couleur (aligne sur STATUS_COLOR : reel = crit,
# artificiel = warn, sain/na = ok - meme semantique que partout ailleurs
# dans le dashboard, pas une palette matplotlib generique tab:red/tab:orange).
DEFECT_ORIGIN_COLOR = {
    "real": PALETTE.crit,
    "artificial": PALETTE.warn,
    "na": PALETTE.ok,
}


def style_figure(fig, *axes) -> None:
    """Applique le theme sombre du dashboard a une figure matplotlib.

    Sans ca, un graphique matplotlib garde son fond blanc par defaut - un
    contraste violent au milieu d'un dashboard sombre partout ailleurs
    (c'etait le cas des onglets Indicateurs et Historique avant ce fix).

    Fond transparent (pas une couleur PALETTE hardcodee) : la figure peut se
    retrouver sur le fond de page (#1A1815) ou dans un conteneur different
    (#26221D) selon l'endroit du dashboard - la transparence s'adapte aux
    deux sans qu'il faille deviner laquelle. Appeler avec
    `st.pyplot(fig, transparent=True)` cote appelant pour que Streamlit
    respecte cette transparence a l'export.
    """
    fig.patch.set_alpha(0.0)
    for ax in axes:
        ax.patch.set_alpha(0.0)
        ax.tick_params(colors=PALETTE.text_secondary, labelsize=9)
        ax.xaxis.label.set_color(PALETTE.text_primary)
        ax.yaxis.label.set_color(PALETTE.text_primary)
        ax.title.set_color(PALETTE.text_primary)
        for spine in ax.spines.values():
            spine.set_color(PALETTE.text_secondary)
            spine.set_alpha(0.3)
        ax.grid(True, color=PALETTE.text_secondary, alpha=0.15, linewidth=0.6)
        legend = ax.get_legend()
        if legend is not None:
            frame = legend.get_frame()
            frame.set_facecolor(PALETTE.bg_card)
            frame.set_edgecolor(PALETTE.text_secondary)
            legend.get_title().set_color(PALETTE.text_primary)
            for text in legend.get_texts():
                text.set_color(PALETTE.text_primary)


BOXPLOT_PROPS = {
    # A passer directement a DataFrame.boxplot(**BOXPLOT_PROPS, ...) - plus
    # fiable qu'un recoloriage a posteriori (matplotlib expose ces dicts de
    # style nativement, pas besoin de deviner quelle Line2D est la mediane).
    # Sans ca, boites/mediane/moustaches restent noires par defaut - quasi
    # invisibles sur le fond sombre applique par style_figure().
    "boxprops": {"color": PALETTE.text_secondary},
    "whiskerprops": {"color": PALETTE.text_secondary},
    "capprops": {"color": PALETTE.text_secondary},
    "medianprops": {"color": PALETTE.accent, "linewidth": 2},
    "flierprops": {
        "markeredgecolor": PALETTE.text_secondary,
        "markerfacecolor": "none",
        "markersize": 4,
    },
}
