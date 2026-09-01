"""Glossaire pedagogique - parsing et affichage.

Source unique : docs/glossaire_pedagogique.md (12 termes, format strict
"En une phrase / Analogie / Pourquoi ca compte / A ne pas confondre avec",
redige pour un operateur/chef d'atelier, pas un data scientist).

Regle 0-mock : help_text() et figure_for() retournent None si le terme ou
la figure n'existe pas - jamais de texte ou d'image de substitution invente.
"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit as st

_GLOSSAIRE_PATH = Path(__file__).resolve().parents[2] / "docs" / "glossaire_pedagogique.md"
_FIGURES_DIR = Path(__file__).resolve().parents[2] / "reports" / "glossaire_visuel" / "figures"

# Association terme -> figure generee par scripts/build_glossaire_visuel.py
# (a partir de vraies donnees Paderborn). Mapping explicite, pas devine par
# recherche floue de nom de fichier - si une figure est renommee, ce mapping
# doit etre mis a jour a la main plutot que de risquer une association fausse.
_TERM_FIGURES = {
    "rms-vibration": "fig_01_rms_K001_sain.png",
    "kurtosis": "fig_02_kurtosis_compare.png",
    "crest-factor-facteur-de-crete": "fig_03_crest_KA01_artificiel.png",
    "seuil-seuil-d-alerte": "fig_04_seuil_distribution.png",
    "f1-macro": "fig_05_f1_confusion.png",
    "validation-croisee-ecart-type-sur-les-folds": "fig_06_validation_croisee.png",
    "bpfo-bpfi-bsf-ftf-les-4-frequences-caracteristiques": "fig_07_bpfo_bpfi_geometrie.png",
    "analyse-d-enveloppe": "fig_08_enveloppe_KI04_reel.png",
    "unite-g-acceleration-vs-mm-s-vitesse": "fig_09_iso20816_zones.png",
    "health-state-defect-origin-sain-defaut-artificiel-defaut-reel": "fig_10_defect_origin_pie.png",
    "asset-machine-site-zone-vocabulaire-factory-builder": "fig_11_hierarchy.png",
}

_FIELD_PATTERN = re.compile(
    r"\*\*(En une phrase|Analogie|Pourquoi ça compte|A ne pas confondre avec)\s*:\*\*\s*(.+?)"
    r"(?=\n\*\*(?:En une phrase|Analogie|Pourquoi ça compte|A ne pas confondre avec)\s*:\*\*|\Z)",
    re.DOTALL,
)


def _slugify(title: str) -> str:
    slug = title.lower()
    slug = slug.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a")
    slug = slug.replace("î", "i").replace("ô", "o").replace("û", "u").replace("ç", "c")
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


@st.cache_data
def load_glossaire() -> dict[str, dict[str, str]]:
    """Parse docs/glossaire_pedagogique.md en dict {slug: {title, champs...}}.

    Une section ## qui ne porte pas les 4 champs attendus (ex. "Notes
    finales pour l'integration") est silencieusement ignoree plutot que de
    produire une entree incomplete.
    """
    if not _GLOSSAIRE_PATH.exists():
        return {}
    text = _GLOSSAIRE_PATH.read_text(encoding="utf-8")
    sections = re.split(r"\n## ", text)[1:]  # ignore le prologue avant le 1er titre

    terms: dict[str, dict[str, str]] = {}
    for section in sections:
        title, _, body = section.partition("\n")
        title = title.strip()
        fields = {m.group(1): m.group(2).strip() for m in _FIELD_PATTERN.finditer(body)}
        required = {"En une phrase", "Analogie", "Pourquoi ça compte", "A ne pas confondre avec"}
        if not required.issubset(fields):
            continue
        slug = _slugify(title)
        terms[slug] = {
            "title": title,
            "en_une_phrase": fields["En une phrase"],
            "analogie": fields["Analogie"],
            "pourquoi": fields["Pourquoi ça compte"],
            "confusion": fields["A ne pas confondre avec"],
        }
    return terms


def help_text(term_key: str) -> str | None:
    """Texte court (1 phrase) pour un tooltip help= Streamlit. None si absent."""
    entry = load_glossaire().get(term_key)
    return entry["en_une_phrase"] if entry else None


def figure_for(term_key: str) -> Path | None:
    """Chemin de la figure associee au terme, si elle existe reellement sur disque."""
    filename = _TERM_FIGURES.get(term_key)
    if not filename:
        return None
    path = _FIGURES_DIR / filename
    return path if path.exists() else None


def render() -> None:
    """Onglet '❓ Comprendre' : un expander par terme du glossaire."""
    terms = load_glossaire()
    if not terms:
        st.info(
            "Glossaire introuvable (docs/glossaire_pedagogique.md absent ou vide). "
            "Aucune definition a afficher."
        )
        return

    st.caption(
        "Definitions pensees pour un operateur/chef d'atelier, pas pour un data "
        "scientist. Source : docs/glossaire_pedagogique.md."
    )

    for slug, entry in terms.items():
        with st.expander(entry["title"]):
            st.markdown(f"**En une phrase :** {entry['en_une_phrase']}")
            st.markdown(f"**Analogie :** {entry['analogie']}")
            fig_path = figure_for(slug)
            if fig_path is not None:
                st.image(str(fig_path), width="stretch")
            st.markdown(f"**Pourquoi ça compte :** {entry['pourquoi']}")
            st.markdown(f"**A ne pas confondre avec :** {entry['confusion']}")
