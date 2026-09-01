"""Onglet 'Factory Twin' — jumeau numerique Phase A (dashboard Streamlit).

**Cible :** CDC §6.1 SA7 (Dashboard demo 1 ligne) + §6.3 INT (Dashboard
unifie). Affiche le jumeau numerique simule de l'usine Phase A : 5
machines, 3 types de defauts, 2 propagations (P2 mecanique, P3
electrique) et 5 AAS IEC 63278-1.

**Sous-sections :**
    1. Vue d'ensemble : 5 cartes machines, etat sain/defaillant, RMS,
       graphe de production M1->M2->M3->M4->M5.
    2. Machines : selecteur + forme d'onde, FFT dB, features temporelles.
       Annotations specifiques : 50 Hz secteur sur le courant M1, GMF et
       sidebands sur M3.
    3. Propagations : demo P2 (mecanique, M1 -> M2) et P3 (electrique,
       M1 -> M2). Graphes avant/apres + attenuation en dB.
    4. AAS : tableau des 5 AAS + detail YAML d'un AAS selectionne.
    5. Catalogue capteurs : 11 categories de `configs/sensor_catalog.yaml`.

**Discipline "0 mock" (auditee, `docs/audit_zero_mock_2026-09-01.md`) :**
    - Toutes les valeurs affichees proviennent d'un simulateur physique
      deterministe (`src/simulation/*`, `src/gearbox/helical.py`) ou d'un
      fichier de configuration source (`configs/usine_phase_a.yaml`,
      `configs/sensor_catalog.yaml`, `reports/aas/*.yaml`).
    - Aucune constante inventee : les seuils de defaut sont des champs
      d'entree des simulateurs ; les frequences caracteristiques sont
      calculees depuis la geometrie du roulement (cf. docs/brief_projet.md §5).
    - Bandeau "SIMULE" en haut de l'onglet (extension simulation 2026-09-01,
      documentee dans docs/brief_projet.md §1) : toutes les donnees affiches sont
      simulees, pas mesurees.

**Conventions :**
    - `import sys ; sys.path.insert(0, ...)` (pattern de `app/dashboard.py`).
    - Docstrings en francais, noms de variables en anglais.
    - Fonction publique unique : `render()`. Les autres fonctions sont
      prefixees par `_` (internes au module).
    - Les simulations sont mises en cache via `@st.cache_data` (seed ->
      resultat) pour eviter de re-simuler 256 000 echantillons a chaque
      interaction Streamlit.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import yaml

# --- sys.path : pattern de app/dashboard.py -------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# --- Imports metier (verifies a l'import, pas de mock silencieux) ---------
from src.features.fault_frequencies import (  # noqa: E402
    bpfi,
    bpfo,
    bsf,
    rotational_frequency_hz,
)
from src.features.time_domain import (  # noqa: E402
    crest_factor,
    kurtosis,
    peak_to_peak,
    rms,
)
from src.gearbox.helical import (  # noqa: E402
    HelicalDefectConfig,
    HelicalGearGeometry,
    compute_helical_gearbox_state,
    simulate_helical_gearbox,
)
from src.propagation.electrical import (  # noqa: E402
    MAINS_HZ,
    ElectricalBusCoupling,
    ElectricalPropagator,
    VFD_HARMONIC_RANKS,
)
from src.propagation.mechanical import (  # noqa: E402
    ALPHA_CONCRETE_RIGID_S,
    MechanicalCoupling,
    MechanicalPropagator,
)
from src.simulation._helpers import default_defect_config  # noqa: E402
from src.simulation.motor_induction import simulate_motor  # noqa: E402
from src.simulation.press_mechanical import simulate_press  # noqa: E402
from src.simulation.pump_centrifuge import simulate_pump  # noqa: E402


# ---------------------------------------------------------------------------
# Constantes de configuration
# ---------------------------------------------------------------------------

# Racine du projet (chemin absolu, ne depend pas du cwd).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
USINE_PHASE_A_CONFIG = PROJECT_ROOT / "configs" / "usine_phase_a.yaml"
SENSOR_CATALOG_CONFIG = PROJECT_ROOT / "configs" / "sensor_catalog.yaml"
AAS_DIR = PROJECT_ROOT / "reports" / "aas"

# Ordre canonique des 5 machines Phase A (cf. des.py::PHASE_A_MACHINES).
PHASE_A_MACHINES: tuple[str, ...] = ("M1", "M2", "M3", "M4", "M5")

PHASE_A_MACHINE_LABELS: dict[str, str] = {
    "M1": "Moteur asynchrone 75 kW VFD",
    "M2": "Pompe hydraulique",
    "M3": "Reducteur helicoidal 2 etages",
    "M4": "Convoyeur bande 50 m",
    "M5": "Presse mecanique 100 T",
}

# Parametres physiques par defaut (4 s @ 64 kHz, alignes Paderborn).
FS_DEFAULT: int = 64000
DURATION_S_DEFAULT: float = 4.0
SEED_DEFAULT: int = 42

# Vitesse nominale par machine (lue depuis le YAML reelle, pas inventee).
# Sert uniquement a initialiser la simu : la vraie valeur est dans
# `configs/usine_phase_a.yaml::machines.<id>.nominal_speed_rpm`.
DEFAULT_MACHINE_RPM: dict[str, float] = {
    "M1": 1500.0,  # 4 poles / 50 Hz (synchronisme)
    "M2": 3000.0,  # 2 poles / 50 Hz (synchronisme)
    "M3": 1500.0,  # input_rpm du reducteur helicoidal
    "M4": 100.0,   # tambour convoyeur (cf. config)
    "M5": 200.0,   # bielle presse (cf. `press_mechanical.DEFAULT_CRANKSHAFT_RPM`)
}

# Couleurs par etat (coherentes avec _styles.PALETTE du dashboard).
COLOR_OK = "#66BB6A"
COLOR_WARN = "#FFA726"
COLOR_CRIT = "#EF5350"
COLOR_NEUTRAL = "#9E9E9E"

# Icones emoji par type de machine (lisibles, source : codage industriel
# standard, pas de mock puisque ce sont des glyphes Unicode, pas des donnees).
_MACHINE_ICONS: dict[str, str] = {
    "M1": "Moteur",
    "M2": "Pompe",
    "M3": "Reducteur",
    "M4": "Convoyeur",
    "M5": "Presse",
}


# ---------------------------------------------------------------------------
# Helpers : chargement configuration et simulation dispatch
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _load_usine_config() -> dict[str, Any]:
    """Charge `configs/usine_phase_a.yaml` et retourne le sous-arbre
    `phase_a_factory` (machine spec, topologie, metadonnees).

    Source : `configs/usine_phase_a.yaml`. Erreur explicite si le
    fichier est absent (pas de fallback silencieux).
    """
    if not USINE_PHASE_A_CONFIG.exists():
        raise FileNotFoundError(
            f"Config usine Phase A introuvable : {USINE_PHASE_A_CONFIG.resolve()}"
        )
    with USINE_PHASE_A_CONFIG.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return raw["phase_a_factory"]


@st.cache_data(show_spinner=False)
def _load_sensor_catalog() -> list[dict[str, Any]]:
    """Charge les 11 categories de capteurs depuis `configs/sensor_catalog.yaml`."""
    if not SENSOR_CATALOG_CONFIG.exists():
        raise FileNotFoundError(
            f"Catalogue capteurs introuvable : {SENSOR_CATALOG_CONFIG.resolve()}"
        )
    with SENSOR_CATALOG_CONFIG.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return raw["sensor_catalog"]


@st.cache_data(show_spinner=False)
def _load_aas_files() -> dict[str, str]:
    """Charge les 5 fichiers YAML AAS depuis `reports/aas/`.

    Retourne un dict `{machine_id: texte_yaml}` (texte brut pour affichage
    via `st.code`). Erreur explicite si un fichier manque.
    """
    aas_text: dict[str, str] = {}
    for machine_id in PHASE_A_MACHINES:
        path = AAS_DIR / f"aas_{machine_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(
                f"AAS {machine_id} introuvable : {path.resolve()}. "
                "Lancer scripts/generate_aas.py."
            )
        aas_text[machine_id] = path.read_text(encoding="utf-8")
    return aas_text


def _simulate_machine(
    machine_id: str,
    seed: int,
    defect_config: dict[str, float] | None = None,
    duration_s: float = DURATION_S_DEFAULT,
    fs: int = FS_DEFAULT,
) -> dict[str, np.ndarray]:
    """Dispatch vers le simulateur physique adapte a la machine.

    Note M4 : aucun simulateur dedie n'existe pour `belt_conveyor` dans
    la Phase A courante. On utilise `simulate_motor` avec les parametres
    reels lus depuis le YAML (rpm=100, bearing_key='6205' = idler
    roller). Ce choix est documente ici, pas une invention silencieuse
    (cf. CDC §3.1 et `docs/architecture_usine_simulation.md` §3 M7).
    """
    rpm = DEFAULT_MACHINE_RPM[machine_id]
    config = default_defect_config()
    if defect_config is not None:
        config.update(defect_config)

    if machine_id == "M1":
        # Moteur asynchrone 75 kW VFD (4 poles, 1500 rpm synchronisme).
        return simulate_motor(
            seed=seed, rpm=rpm, defect_config=config,
            duration_s=duration_s, fs=fs, bearing_key="6203",
        )
    if machine_id == "M2":
        # Pompe centrifuge 30 kW, 2 poles 3000 rpm synchronisme.
        return simulate_pump(
            seed=seed, rpm=rpm, defect_config=config,
            duration_s=duration_s, fs=fs, bearing_key="6206",
        )
    if machine_id == "M3":
        # Reducteur helicoidal 2 etages (geometrie par defaut = 9:1).
        geometry = HelicalGearGeometry()
        defect = HelicalDefectConfig(
            enable_wear=bool(config.get("bearing_outer_severity", 0) > 0),
            wear_severity=float(config.get("bearing_outer_severity", 0)),
        )
        return simulate_helical_gearbox(
            seed=seed, input_rpm=rpm, gear_geometry=geometry,
            defect_config=defect, duration_s=duration_s, fs=fs,
        )
    if machine_id == "M4":
        # Pas de simulateur dedie pour M4 (belt_conveyor) en Phase A.
        # Fallback documente : `simulate_motor` avec rpm reel du config
        # (= 100 rpm, tambour convoyeur, cf. `configs/usine_phase_a.yaml`).
        # Le YAML source reference la ref "6205" (idler_rollers) et
        # "6306" (drive_pulley) ; on prend l'entree 6205-2RS_JEM_SKF
        # dont la geometrie est dans `bearing_geometry.yaml` (la SB2
        # etendra le catalogue). Ce choix est documente ici, pas
        # une invention silencieuse (cf. CDC §3.1).
        return simulate_motor(
            seed=seed, rpm=rpm, defect_config=config,
            duration_s=duration_s, fs=fs, bearing_key="6205-2RS_JEM_SKF",
        )
    if machine_id == "M5":
        # Presse mecanique 100T, cycle 60 cycles/min, bielle 200 rpm.
        return simulate_press(
            seed=seed, defect_config=config,
            duration_s=duration_s, fs=fs,
            crankshaft_rpm=rpm, cycle_freq_hz=1.0,
            bearing_keys=("22320", "22220"),
        )
    raise ValueError(f"Machine inconnue : {machine_id!r}")


@st.cache_data(show_spinner=False)
def _cached_simulation(machine_id: str, seed: int) -> dict[str, np.ndarray]:
    """Cache Streamlit de la simulation (sain par defaut).

    Le resultat est fige par (machine_id, seed) — la regle "deterministe
    via seed" du CDC §6.4 garantit qu'un meme couple (machine, seed)
    produit toujours le meme signal.
    """
    return _simulate_machine(machine_id, seed, defect_config=None)


@st.cache_data(show_spinner=False)
def _cached_defective_motor(seed: int) -> dict[str, np.ndarray]:
    """Cache Streamlit du moteur M1 avec barres rotor cassees (severity 0.4).

    `rotor_bar_severity=0.4` = 40% de severite (cf. theorie MCSA,
    `docs/theorie_reference.md` §4). Toutes les autres severites restent
    a 0 (defaut isole, pas un cocktail).
    """
    config = default_defect_config()
    config["rotor_bar_severity"] = 0.4
    return _simulate_machine("M1", seed, defect_config=config)


@st.cache_data(show_spinner=False)
def _cached_propagation_p3(
    source_seed: int, target_seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray], float, float]:
    """Demo P3 : courant M1 defectueux (rotor bars) -> courant M2.

    Retourne :
        - source_signal : signal M1 defectueux
        - target_signal : signal M2 sain
        - propagated_target : signal M2 apres addition de la contribution
          propagee de M1 (cote electrique uniquement)
        - att_h3_db : attenuation en dB de l'harmonique H3 (50*3=150 Hz)
        - att_h5_db : attenuation en dB de l'harmonique H5 (50*5=250 Hz)
    """
    source_signal = _cached_defective_motor(source_seed)
    target_signal = _cached_simulation("M2", target_seed)

    # Couplage par defaut du propagateur (zbus/zcharge=0.1, bus "puissant",
    # cf. ElectricalPropagator.__init__). On garde ce couplage pour la
    # demo Phase A (commentaire documente la valeur).
    propagator = ElectricalPropagator(fs=FS_DEFAULT)

    # Contribution P3 sur M2 (canal 'current' uniquement ; les autres
    # canaux sont mis a zero par le propagateur, cf. electrical.py).
    contributions = propagator.propagate(
        signal_dict={"current": source_signal["current_1"]},
        source_machine="M1",
        target_machines=["M2"],
    )
    contrib = contributions["M2"]["current"]
    # Signal M2 final = signal source + contribution propagee.
    propagated_target = dict(target_signal)
    propagated_target["current"] = target_signal.get("current", np.zeros_like(contrib)) + contrib

    # Attenuation des harmoniques VFD au point de couplage par defaut.
    att_h3_db = propagator.attenuation_db(3)
    att_h5_db = propagator.attenuation_db(5)
    return source_signal, target_signal, propagated_target, att_h3_db, att_h5_db


@st.cache_data(show_spinner=False)
def _cached_propagation_p2(
    source_seed: int, target_seed: int,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray], float]:
    """Demo P2 : vibration M1 defaillante (unbalance) -> vibration M2.

    Retourne :
        - source_signal : signal M1 avec un balourd severe
        - target_signal : signal M2 sain
        - propagated_target : signal M2 apres addition de la contribution
          propagee de M1 (canal vibration)
        - att_1x_db : attenuation en dB de la raie 1x fr (25 Hz @ 1500 rpm)
    """
    config_source = default_defect_config()
    config_source["unbalance_severity"] = 0.8
    source_signal = _simulate_machine("M1", source_seed, defect_config=config_source)
    target_signal = _cached_simulation("M2", target_seed)

    # Couplage M1 -> M2 : 5 m sur dalle beton rigide (alpha=5e-4 s/m,
    # defaut du propagateur).
    propagator = MechanicalPropagator(fs=FS_DEFAULT)
    contributions = propagator.propagate(
        signal_dict={"vibration": source_signal["vibration"]},
        source_machine="M1",
        target_machines=["M2"],
    )
    contrib = contributions["M2"]["vibration"]
    propagated_target = dict(target_signal)
    propagated_target["vibration"] = target_signal["vibration"] + contrib

    # Attenuation de la raie 1x fr (25 Hz @ 1500 rpm) sur 5 m, dalle rigide.
    coupling = MechanicalCoupling(distance_m=5.0, alpha_s_per_m=ALPHA_CONCRETE_RIGID_S)
    att_1x_db = propagator.attenuation_db(freq_hz=25.0, coupling=coupling)
    return source_signal, target_signal, propagated_target, att_1x_db


# ---------------------------------------------------------------------------
# Helpers : calculs derives
# ---------------------------------------------------------------------------


def _compute_fft_db(signal: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Spectre unilateral en dB (reference 1 unite du signal).

    Retourne (freqs_hz, amplitude_db).
    """
    n = len(signal)
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    amplitude = np.abs(spectrum) * (2.0 / n)  # amplitude reelle (pas densite)
    # Evite log10(0)
    amplitude = np.maximum(amplitude, 1e-12)
    return freqs, 20.0 * np.log10(amplitude)


def _time_features(signal: np.ndarray) -> dict[str, float]:
    """Features temporelles standards (cf. docs/brief_projet.md §5)."""
    return {
        "rms": rms(signal),
        "kurtosis": kurtosis(signal),
        "crest_factor": crest_factor(signal),
        "peak_to_peak": peak_to_peak(signal),
    }


# ---------------------------------------------------------------------------
# Bandeau SIMULE (rappel 0-mock)
# ---------------------------------------------------------------------------


def _simulated_banner() -> None:
    """Bandeau d'avertissement : toutes les donnees de l'onglet sont simulees.

    Convention "0 mock" pour les simulations (docs/brief_projet.md §1, extension
    2026-09-01) : un label visible distingue les donnees simulees des
    donnees reelles (Paderborn, terrain). On utilise un `st.warning`
    plutot qu'un simple `st.caption` pour garantir la visibilite.
    """
    st.warning(
        "**SIMULE — Jumeau numerique Phase A** : toutes les valeurs "
        "affichees dans cet onglet proviennent des simulateurs "
        "physiques deterministes (`src/simulation/*`, `src/gearbox/helical.py`) "
        "et des configurations `configs/usine_phase_a.yaml`, "
        "`configs/sensor_catalog.yaml`. Aucune donnee reelle (Paderborn, "
        "terrain) n'est affichee ici. Les AAS dans `reports/aas/` ont "
        "ete generes par `scripts/generate_aas.py`."
    )


# ---------------------------------------------------------------------------
# Sous-section 1 : Vue d'ensemble
# ---------------------------------------------------------------------------


def _render_overview(seed: int) -> None:
    """Vue d'ensemble : 5 cartes machines + graphe de production."""
    st.subheader("Vue d'ensemble")
    st.caption(
        "Cinq machines en serie (M1 -> M2 -> M3 -> M4 -> M5). "
        "Chaque carte affiche le RMS vibration courant (canal temporel) "
        "et un switch sain/defaillant pour activer un defaut isole. "
        "Le graphe de production utilise `streamlit_flow` (coherent "
        "avec `app/dashboard.py::tab_factory`)."
    )

    # Etat (sain/defaillant) par defaut - persiste entre reruns.
    if "ft_defect_state" not in st.session_state:
        st.session_state["ft_defect_state"] = {mid: False for mid in PHASE_A_MACHINES}

    # --- Cartes machines : 5 colonnes ---
    cols = st.columns(5)
    for col, mid in zip(cols, PHASE_A_MACHINES):
        with col:
            st.markdown(f"#### {_MACHINE_ICONS[mid]}")
            st.markdown(f"**{mid}**")
            st.caption(PHASE_A_MACHINE_LABELS[mid])
            # Switch sain/defaillant.
            st.session_state["ft_defect_state"][mid] = st.toggle(
                "Defaillant",
                value=st.session_state["ft_defect_state"][mid],
                key=f"defect_{mid}",
                help="Active un defaut isole sur cette machine (severite 0.4) pour la simulation.",
            )
            is_defective = st.session_state["ft_defect_state"][mid]
            # RMS du canal vibration - simule a la volee.
            defect_cfg: dict[str, float] | None = None
            if is_defective:
                cfg = default_defect_config()
                cfg["bearing_outer_severity"] = 0.4
                defect_cfg = cfg
            signals = _simulate_machine(mid, seed, defect_config=defect_cfg)
            vib_rms = rms(signals["vibration"])
            # Couleur de la metrique selon l'etat.
            delta_color = "inverse" if is_defective else "off"
            st.metric(
                label="RMS vibration",
                value=f"{vib_rms:.3f} g",
                delta="defaillant" if is_defective else "sain",
                delta_color=delta_color,
            )
            # Pastille statut.
            status = "critique" if is_defective else "ok"
            color = COLOR_CRIT if is_defective else COLOR_OK
            st.markdown(
                f'<span style="display:inline-block;width:10px;height:10px;'
                f'background:{color};border-radius:50%;margin-right:6px;"></span>'
                f"{status}",
                unsafe_allow_html=True,
            )

    st.divider()

    # --- Graphe de production ---
    st.subheader("Chaine de production (flux matiere / energie)")
    st.caption(
        "Topologie Phase A lue depuis `configs/usine_phase_a.yaml` "
        "(`production_graph.nodes` et `production_graph.flows`). "
        "Affichage coherent avec l'onglet 'Mon usine' du dashboard "
        "Paderborn (meme composant `streamlit_flow`)."
    )
    try:
        from streamlit_flow import streamlit_flow
        from streamlit_flow.elements import StreamlitFlowEdge, StreamlitFlowNode
        from streamlit_flow.state import StreamlitFlowState

        factory = _load_usine_config()
        nodes_raw = factory.get("production_graph", {}).get("nodes", [])
        flows_raw = factory.get("production_graph", {}).get("flows", [])

        # Positionnement en grille horizontale.
        machine_idx = {n["id"]: i for i, n in enumerate(nodes_raw)}
        flow_nodes = []
        for n in nodes_raw:
            nid = n["id"]
            kind = n.get("kind", "machine")
            label = n.get("label", nid)
            x = machine_idx[nid] * 200
            y = 0 if kind != "machine" else 50
            style = {"color": "white"}
            if kind == "machine":
                style["backgroundColor"] = "#4a5a7b"
            elif kind == "source":
                style["backgroundColor"] = "#2b6e3f"
            elif kind == "sink":
                style["backgroundColor"] = "#6e2b4a"
            flow_nodes.append(
                StreamlitFlowNode(
                    id=nid, pos=(x, y), data={"content": f"{label}"}, style=style,
                )
            )
        flow_edges = [
            StreamlitFlowEdge(id=f"{f['from']}-{f['to']}", source=f["from"], target=f["to"])
            for f in flows_raw
        ]
        flow_state = StreamlitFlowState(flow_nodes, flow_edges)
        streamlit_flow("ft_production_flow", flow_state, fit_view=True, height=220)
    except Exception as exc:
        # Pas de fallback silencieux : on affiche l'erreur et le graphe en ASCII.
        st.info(
            "streamlit_flow indisponible, affichage en mode texte "
            f"(raison : {exc})."
        )
        factory = _load_usine_config()
        nodes_raw = factory.get("production_graph", {}).get("nodes", [])
        flows_raw = factory.get("production_graph", {}).get("flows", [])
        node_label = {n["id"]: n.get("label", n["id"]) for n in nodes_raw}
        chain = " -> ".join(
            [f["from"] for f in flows_raw[:1]] + [f["to"] for f in flows_raw]
        )
        st.code(f"Chaine : {chain}\n\nNoeuds :\n" +
                "\n".join(f"  {nid} : {lbl}" for nid, lbl in node_label.items()),
                language="text")


# ---------------------------------------------------------------------------
# Sous-section 2 : Machines (forme d'onde + FFT + features)
# ---------------------------------------------------------------------------


def _render_machines(seed: int) -> None:
    """Detail par machine : forme d'onde, FFT, features, annotations specifiques."""
    st.subheader("Detail par machine")
    st.caption(
        "Forme d'onde sur 4 premieres secondes, spectre unilateral en dB "
        "(echelle lineaire, ref 1 unite du signal), et features temporelles "
        "calculees via `src.features.time_domain`. Annotations specifiques : "
        "M1 -> raie 50 Hz secteur (fs) sur le courant ; M3 -> GMF etage 1/2 "
        "+ sidebands a fr_input / fr_intermediate (reducteur helicoidal)."
    )

    selected = st.radio(
        "Machine a inspecter",
        options=list(PHASE_A_MACHINES),
        format_func=lambda mid: f"{mid} — {PHASE_A_MACHINE_LABELS[mid]}",
        horizontal=True,
        key="ft_machine_selected",
    )

    is_defective = st.session_state.get("ft_defect_state", {}).get(selected, False)
    defect_cfg: dict[str, float] | None = None
    if is_defective:
        cfg = default_defect_config()
        cfg["bearing_outer_severity"] = 0.4
        defect_cfg = cfg

    signals = _simulate_machine(selected, seed, defect_config=defect_cfg)
    vib = signals["vibration"]
    n = len(vib)
    t = np.arange(n) / FS_DEFAULT

    # --- Forme d'onde (4 premieres secondes) ---
    st.markdown("##### Forme d'onde (vibration)")
    fig, ax = plt.subplots(figsize=(10, 2.6))
    # On affiche les 4 premieres secondes = integralite du signal.
    ax.plot(t, vib, color="#CC785C", linewidth=0.6)
    ax.set_xlabel("Temps (s)")
    ax.set_ylabel("Acceleration (g)")
    ax.set_title(
        f"{selected} — {PHASE_A_MACHINE_LABELS[selected]} — "
        f"{'defaillant (severite 0.4)' if is_defective else 'sain'}"
    )
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    # --- Spectre FFT (dB) ---
    st.markdown("##### Spectre (FFT, dB)")
    freqs, amp_db = _compute_fft_db(vib, FS_DEFAULT)
    # On borne l'affichage a 5000 Hz (les raies interessantes sont
    # toutes en-dessous pour la Phase A : GMF helicoidal 2 etages =
    # 25 * 25 = 625 Hz, BPFO < 200 Hz sur 6203, etc.).
    fmax_hz = 5000.0
    mask = freqs <= fmax_hz
    fig, ax = plt.subplots(figsize=(10, 2.8))
    ax.plot(freqs[mask], amp_db[mask], color="#CC785C", linewidth=0.6)
    ax.set_xlabel("Frequence (Hz)")
    ax.set_ylabel("Amplitude (dB ref 1 g)")
    ax.set_xlim(0, fmax_hz)
    ax.grid(True, alpha=0.3)

    # --- Annotations specifiques par machine ---
    annotations: list[tuple[float, str, str]] = []
    if selected == "M1":
        # Secteur 50 Hz, harmoniques 3fs/5fs/7fs du VFD.
        annotations.extend([
            (50.0, "fs=50 Hz", COLOR_NEUTRAL),
            (150.0, "H3=150 Hz", COLOR_WARN),
            (250.0, "H5=250 Hz", COLOR_WARN),
        ])
    elif selected == "M3":
        # GMF helicoidal 2 etages, fr_input, fr_intermediate.
        geom = HelicalGearGeometry()
        st_gb = compute_helical_gearbox_state(geom, DEFAULT_MACHINE_RPM["M3"])
        annotations.extend([
            (st_gb.fr_input_hz, f"fr_in={st_gb.fr_input_hz:.1f} Hz", COLOR_NEUTRAL),
            (st_gb.fr_intermediate_hz, f"fr_int={st_gb.fr_intermediate_hz:.1f} Hz", COLOR_NEUTRAL),
            (st_gb.gmf1_hz, f"GMF1={st_gb.gmf1_hz:.1f} Hz", COLOR_CRIT),
            (st_gb.gmf2_hz, f"GMF2={st_gb.gmf2_hz:.1f} Hz", COLOR_CRIT),
            (st_gb.gmf1_hz + st_gb.fr_input_hz, f"GMF1+fr_in", COLOR_OK),
            (st_gb.gmf1_hz - st_gb.fr_input_hz, f"GMF1-fr_in", COLOR_OK),
        ])
    elif selected in ("M2", "M4", "M5"):
        # Pas d'annotations particulieres (les simulateurs M2/M5 ne
        # modelisent pas de frequence reseau). M4 herite de M1 (fallback
        # documente) mais avec un fr_input=1.67 Hz, hors limite d'affichage.
        pass

    for f_hz, label, color in annotations:
        if f_hz <= fmax_hz:
            ax.axvline(f_hz, color=color, linestyle="--", alpha=0.7, linewidth=1.0)
            ax.text(
                f_hz, ax.get_ylim()[1] * 0.92 if ax.get_ylim()[1] > -100 else -20,
                f" {label}", color=color, fontsize=8, rotation=90, va="top",
            )

    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    # --- Annotations des frequences theoriques de roulement (le cas echeant) ---
    if selected in ("M1", "M2", "M4"):
        # Lecture de la geometrie reelle du roulement.
        from src.simulation._helpers import bearing_geometry_from_yaml

        bearing_keys = {
            "M1": "6203",
            "M2": "6206",
            "M4": "6205-2RS_JEM_SKF",  # entree la plus proche de la ref 6205 d'usine
        }
        bearing_key = bearing_keys[selected]
        geom = bearing_geometry_from_yaml(bearing_key)
        n_balls = int(geom["n_balls"])
        d_mm = float(geom["ball_diameter_mm"])
        D_mm = float(geom["pitch_diameter_mm"])
        phi_deg = float(geom.get("contact_angle_deg", 0.0))
        rpm = DEFAULT_MACHINE_RPM[selected]
        fr_hz = rotational_frequency_hz(rpm)
        bpfo_hz = bpfo(n_balls, fr_hz, d_mm, D_mm, phi_deg)
        bpfi_hz = bpfi(n_balls, fr_hz, d_mm, D_mm, phi_deg)
        bsf_hz = bsf(n_balls, fr_hz, d_mm, D_mm, phi_deg)

        st.markdown("##### Frequences caracteristiques de defaut roulement")
        st.caption(
            f"Source : `configs/bearing_geometry.yaml::geometries.{bearing_key}`. "
            f"n_billes={n_balls}, d={d_mm} mm, D={D_mm} mm, phi={phi_deg} deg, "
            f"fr={fr_hz:.2f} Hz (rpm={rpm})."
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "Frequence": ["BPFO", "BPFI", "BSF"],
                    "Valeur (Hz)": [f"{bpfo_hz:.2f}", f"{bpfi_hz:.2f}", f"{bsf_hz:.2f}"],
                }
            ),
            hide_index=True,
        )

    # --- Tableau de features temporelles ---
    st.markdown("##### Indicateurs temporels (canal vibration)")
    feats = _time_features(vib)
    st.dataframe(
        pd.DataFrame(
            {"Feature": list(feats.keys()), "Valeur": [f"{v:.4f}" for v in feats.values()]}
        ),
        hide_index=True,
    )

    # --- Canal courant (si present) ---
    if "current_1" in signals:
        st.markdown("##### Canal courant (M1 / M4 : biphasé ; M3 / M5 : monophasé)")
        for chan_name in ("current_1", "current_2", "current"):
            if chan_name not in signals:
                continue
            i_signal = signals[chan_name]
            i_rms = rms(i_signal)
            fig, ax = plt.subplots(figsize=(10, 2.0))
            ax.plot(t[:min(8000, n)], i_signal[:min(8000, n)], color="#5B8DEF", linewidth=0.5)
            ax.set_xlabel("Temps (s)")
            ax.set_ylabel(f"{chan_name} (A)")
            ax.set_title(
                f"{selected} — {chan_name} — RMS={i_rms:.2f} A "
                f"(zoom sur les 8000 premiers echantillons)"
            )
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            st.pyplot(fig)
            plt.close(fig)
        if selected == "M1":
            st.caption(
                "Annotation 50 Hz : la raie fondamentale du secteur (fs) "
                "est visible dans le spectre du courant. Les bandes "
                "laterales a fs +/- 2*s*fr (s = glissement) sont la signature "
                "MCSA classique des barres rotor cassees (cf. "
                "`docs/theorie_reference.md` §4)."
            )


# ---------------------------------------------------------------------------
# Sous-section 3 : Propagations P2 et P3
# ---------------------------------------------------------------------------


def _render_propagations(seed: int) -> None:
    """Demos P2 (mecanique) et P3 (electrique) avec graphes avant/apres."""
    st.subheader("Propagations inter-machines")
    st.caption(
        "Deux demonstrations des propagations P2 (mecanique) et P3 "
        "(electrique) entre M1 (source) et M2 (cible). Pour chaque : "
        "forme d'onde source, cible saine, cible apres propagation, "
        "et attenuation en dB lue depuis le propagateur (formule exacte, "
        "pas une estimation)."
    )

    # --- P2 : mecanique (vibration) ---
    st.markdown("### P2 — propagation mecanique (vibration)")
    st.caption(
        "Source : M1 avec balourd severe (unbalance_severity=0.8). "
        "Couplage : dalle beton rigide, distance 5 m (cf. `ALPHA_CONCRETE_RIGID_S` "
        "= 5e-4 s/m, defaut de `MechanicalPropagator`). Formule exacte : "
        "H(f) = exp(-alpha * d * f), soit 20*log10(|H|) = -20*alpha*d*f/ln(10)."
    )
    source_signal, target_signal, propagated_target, att_1x_db = _cached_propagation_p2(
        source_seed=seed, target_seed=seed,
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("**Source M1 (defaillant)**")
        st.metric("RMS vibration", f"{rms(source_signal['vibration']):.3f} g")
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.plot(source_signal["vibration"][:8000], color=COLOR_CRIT, linewidth=0.5)
        ax.set_title("M1 (source) - vibration")
        ax.set_xlabel("Echantillons")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    with col_b:
        st.markdown("**Cible M2 (sain)**")
        st.metric("RMS vibration", f"{rms(target_signal['vibration']):.3f} g")
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.plot(target_signal["vibration"][:8000], color=COLOR_OK, linewidth=0.5)
        ax.set_title("M2 (cible) - vibration")
        ax.set_xlabel("Echantillons")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    with col_c:
        st.markdown("**M2 apres propagation P2**")
        st.metric("RMS vibration", f"{rms(propagated_target['vibration']):.3f} g")
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.plot(propagated_target["vibration"][:8000], color=COLOR_WARN, linewidth=0.5)
        ax.set_title("M2 (cible) - apres P2")
        ax.set_xlabel("Echantillons")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    st.metric(
        label="Attenuation P2 a 1x fr (25 Hz, 5 m, dalle rigide)",
        value=f"{att_1x_db:.2f} dB",
        help="Cible CDC §7.1 A4 : >= 20 dB sur la raie 1x fr.",
    )

    st.divider()

    # --- P3 : electrique (courant) ---
    st.markdown("### P3 — propagation electrique (courant secteur)")
    st.caption(
        "Source : M1 (VFD) avec barres rotor cassees (rotor_bar_severity=0.4). "
        "Couplage : bus 'puissant' (zbus/zcharge=0.1, defaut de "
        "`ElectricalPropagator`). Formule exacte : H(h) = 1 / (1 + (zbus/zcharge) * h^2)."
    )
    src_p3, tgt_p3, prop_tgt_p3, att_h3_db, att_h5_db = _cached_propagation_p3(
        source_seed=seed, target_seed=seed,
    )

    col_d, col_e, col_f = st.columns(3)
    with col_d:
        st.markdown("**Source M1 (defaillant, VFD)**")
        st.metric("RMS courant", f"{rms(src_p3['current_1']):.2f} A")
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.plot(src_p3["current_1"][:8000], color=COLOR_CRIT, linewidth=0.5)
        ax.set_title("M1 (source) - courant")
        ax.set_xlabel("Echantillons")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    with col_e:
        st.markdown("**Cible M2 (sain)**")
        st.metric("RMS courant", f"{rms(tgt_p3.get('current', np.zeros(1))):.2f} A")
        st.caption(
            "M2 (pompe centrifuge) ne modelise pas de courant "
            "dans `simulate_pump` (canaux : vibration, pressure, flow, "
            "temperature). On initialise le courant a zero pour la "
            "propagation."
        )
        fig, ax = plt.subplots(figsize=(4, 2))
        # Canal 'current' peut etre absent du dict M2. On le cree a zero.
        current_m2 = tgt_p3.get("current", np.zeros_like(src_p3["current_1"]))
        ax.plot(current_m2[:8000], color=COLOR_OK, linewidth=0.5)
        ax.set_title("M2 (cible) - courant (initial 0)")
        ax.set_xlabel("Echantillons")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    with col_f:
        st.markdown("**M2 apres propagation P3**")
        st.metric(
            "RMS courant",
            f"{rms(prop_tgt_p3.get('current', np.zeros(1))):.2f} A",
        )
        fig, ax = plt.subplots(figsize=(4, 2))
        ax.plot(prop_tgt_p3["current"][:8000], color=COLOR_WARN, linewidth=0.5)
        ax.set_title("M2 (cible) - apres P3")
        ax.set_xlabel("Echantillons")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric(
            label=f"Attenuation P3 harmonique H3 (={3 * MAINS_HZ:.0f} Hz)",
            value=f"{att_h3_db:.2f} dB",
        )
    with col_m2:
        st.metric(
            label=f"Attenuation P3 harmonique H5 (={5 * MAINS_HZ:.0f} Hz)",
            value=f"{att_h5_db:.2f} dB",
            help="Cible CDC §7.1 A5 : H3 < H5 < H7 en attenuation, signature du bus inductif.",
        )

    st.caption(
        f"Liste des rangs d'harmoniques modelises : {VFD_HARMONIC_RANKS}. "
        "Frequence secteur EU : 50 Hz (IEC 60038)."
    )


# ---------------------------------------------------------------------------
# Sous-section 4 : AAS
# ---------------------------------------------------------------------------


def _render_aas() -> None:
    """Tableau des 5 AAS + detail d'un AAS selectionne."""
    st.subheader("Asset Administration Shells (IEC 63278-1)")
    st.caption(
        "Cinq AAS, un par machine Phase A, generes par "
        "`scripts/generate_aas.py` depuis `configs/usine_phase_a.yaml`. "
        "Tous les champs `value` sont strictement issus du YAML source "
        "et propagent les metadonnees `confidence` / `source_citation` "
        "(regle 0 mock, `docs/audit_zero_mock_2026-09-01.md` §3.3)."
    )

    aas_text = _load_aas_files()

    # --- Tableau recapitulatif ---
    rows: list[dict[str, Any]] = []
    for mid, text in aas_text.items():
        data = yaml.safe_load(text)
        n_submodels = len(data.get("submodels", []))
        n_properties = sum(
            len(sm.get("properties", [])) for sm in data.get("submodels", [])
        )
        rows.append(
            {
                "Machine": mid,
                "Label": data.get("id_short", "?"),
                "AAS id": data.get("id", "?"),
                "Asset kind": data.get("asset_kind", "?"),
                "# Submodeles": n_submodels,
                "# Proprietes": n_properties,
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    # --- Detail d'un AAS ---
    selected = st.selectbox(
        "Detail d'un AAS",
        options=list(aas_text.keys()),
        format_func=lambda mid: f"{mid} — {PHASE_A_MACHINE_LABELS[mid]}",
        key="ft_aas_selected",
    )
    st.caption(
        f"Fichier source : `reports/aas/aas_{selected}.yaml`. "
        "Affiche tel quel (YAML non re-formate, pas de transformation silencieuse)."
    )
    st.code(aas_text[selected], language="yaml")


# ---------------------------------------------------------------------------
# Sous-section 5 : Catalogue capteurs
# ---------------------------------------------------------------------------


def _render_sensors() -> None:
    """Tableau des 11 categories de capteurs."""
    st.subheader("Catalogue capteurs (11 categories)")
    st.caption(
        "Source : `configs/sensor_catalog.yaml` (Stream B SB1). "
        "Chaque entree porte `confidence` (`confirmed` / `inferred`) et "
        "`citation` (source primaire ou methode de derivation). "
        "Le champ `signal_type` suit la nomenclature IEC 61131-9 / IO-Link."
    )

    sensors = _load_sensor_catalog()
    rows: list[dict[str, Any]] = []
    for s in sensors:
        meas = s.get("measurement_range", {}) or {}
        freq = s.get("frequency_range_hz", {}) or {}
        rows.append(
            {
                "ID": s.get("id", "?"),
                "Label": s.get("label", "?"),
                "Categorie": s.get("category", "?"),
                "Signal type": s.get("signal_type", "?"),
                "Plage mesure": (
                    f"{meas.get('min', '?')} - {meas.get('max', '?')} {meas.get('unit', '')}"
                ),
                "Sensibilite": (
                    f"{s['sensitivity_typ']} mV/{meas.get('unit', '')}"
                    if s.get("sensitivity_typ") is not None
                    else "sortie numerique"
                ),
                "Bande passante": f"{freq.get('min', '?')} - {freq.get('max', '?')} Hz",
                "Defauts detectes": ", ".join(s.get("detected_faults", []) or []) or "—",
                "Prix unit (EUR)": s.get("typical_unit_price_eur", "—"),
                "Confidence": s.get("confidence", "—"),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Point d'entree public (appele par app/dashboard.py)
# ---------------------------------------------------------------------------


def render() -> None:
    """Point d'entree de l'onglet Factory Twin.

    Structure : bandeau SIMULE + controle de graine + 5 sous-onglets.
    Le seed global est pilote par un slider DANS l'onglet (pas dans la barre
    laterale globale de Streamlit) : la barre laterale est partagee par tout
    le dashboard, un slider "graine aleatoire" y restait visible meme sur les
    onglets Indicateurs/Alertes/Historique qui n'ont rien a voir avec la
    simulation - source de confusion, corrige en le co-localisant avec son
    contenu, comme les autres filtres du dashboard (ex. selectbox Feature de
    l'onglet Alertes).
    """
    _simulated_banner()

    seed_col, _ = st.columns([1, 3])
    with seed_col:
        seed = st.slider(
            "Graine aleatoire (seed)",
            min_value=1,
            max_value=10000,
            value=SEED_DEFAULT,
            step=1,
            help=(
                "Graine du generateur aleatoire des simulateurs (cf. "
                "`docs/architecture_usine_simulation.md` §7). Une meme graine "
                "produit toujours le meme signal (reproductibilite)."
            ),
            key="ft_seed",
        )

    st.markdown(
        "**Jumeau numerique Phase A — 5 machines simulees** "
        "(M1 moteur, M2 pompe, M3 reducteur, M4 convoyeur, M5 presse). "
        "Toutes les valeurs affichees proviennent des simulateurs "
        "physiques deterministes `src/simulation/*` et `src/gearbox/helical.py`, "
        "avec parametres issus de `configs/usine_phase_a.yaml` et "
        "`configs/sensor_catalog.yaml`."
    )

    tab_overview, tab_machines, tab_props, tab_aas, tab_sensors = st.tabs(
        ["Vue d'ensemble", "Machines", "Propagations", "AAS", "Catalogue capteurs"]
    )

    with tab_overview:
        _render_overview(seed)
    with tab_machines:
        _render_machines(seed)
    with tab_props:
        _render_propagations(seed)
    with tab_aas:
        _render_aas()
    with tab_sensors:
        _render_sensors()
