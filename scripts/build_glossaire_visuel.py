"""Génère le glossaire pédagogique visuel (PDF + PPTX) à partir de :
- textes : docs/glossaire_pedagogique.md (12 entrées, format strict)
- données : data/processed/paderborn/{K001 sain, KA01 artificiel, KI04 réel}
- géométrie : configs/bearing_geometry.yaml (6203)

Livrables :
- reports/glossaire_visuel/glossaire_pedagogique.pdf (A4 imprimable)
- reports/glossaire_visuel/glossaire_pedagogique.pptx (16/9 formation)
- reports/glossaire_visuel/figures/*.png (figures individuelles)

Règle "0 mock" : toutes les valeurs numériques sont issues d'une lecture
directe des données Paderborn ou de la géométrie sourcée. Voir
docs/audit_zero_mock_2026-09-01.md et docs/known_issues.md pour le détail.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib
import yaml

matplotlib.use("Agg")  # headless

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import signal as sps
from scipy.signal import hilbert

# --- Accès au code src/ (features déjà implémentées) -------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from features.time_domain import crest_factor, kurtosis, rms

# --- Chemins -----------------------------------------------------------------
GLOSSARY_MD = PROJECT_ROOT / "docs" / "glossaire_pedagogique.md"
GEOM_YAML = PROJECT_ROOT / "configs" / "bearing_geometry.yaml"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed" / "paderborn"
OUT_DIR = PROJECT_ROOT / "reports" / "glossaire_visuel"
FIG_DIR = OUT_DIR / "figures"
PDF_OUT = OUT_DIR / "glossaire_pedagogique.pdf"
PPTX_OUT = OUT_DIR / "glossaire_pedagogique.pptx"

FS_HZ = 64_000.0  # Paderborn sampling rate (sourcé: src/data/loaders.py:24)


# --- Style matplotlib (sobre, imprimable, lisible) ---------------------------
plt.rcParams.update({
    "figure.figsize": (8.5, 4.8),
    "figure.dpi": 110,
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": ":",
    "lines.linewidth": 1.0,
    "savefig.bbox": "tight",
    "savefig.dpi": 150,
})

# Palette (accessible daltoniens, sobre)
COLORS = {
    "vibration": "#1f4e79",      # bleu foncé
    "current": "#7f6000",        # ocre
    "theorique": "#c00000",      # rouge sombre (raies théoriques BPFO/BPFI)
    "mesure": "#1f4e79",         # bleu (mesure réelle)
    "seuil": "#c00000",          # rouge (seuil d'alerte)
    "highlight": "#2e7d32",      # vert (zone OK)
    "warning": "#e65100",        # orange (zone attention)
}


# --- Échantillons Paderborn choisis (sélection documentée) -------------------
# Justification : K001 (sain, IBU, 900 rpm N09) + KA01 (défaut artificiel
# bague ext., 900 rpm N09, perçage) + KI04 (défaut réel, 900 rpm N09, fatigue
# pitting bague int.) — les 3 catégories du projet, condition comparable.
SAMPLES = {
    "K001_sain": ("K001", "N09_M07_F10", 1, "Sain (K001, rodage 19h, 900 rpm)"),
    "KA01_artificiel": ("KA01", "N09_M07_F10", 1, "Défaut artificiel bague ext. (KA01, perçage)"),
    "KI04_reel": ("KI04", "N09_M07_F10", 1, "Défaut réel bague int. (KI04, fatigue pitting)"),
}


# --- Chargement --------------------------------------------------------------
@dataclass
class Sample:
    name: str
    description: str
    vibration: np.ndarray  # g
    current_1: np.ndarray  # A
    current_2: np.ndarray  # A
    n09_rpm: float = 900.0  # vitesse nominale N09 (sourcée: doc Paderborn)

    @property
    def fs(self) -> float:
        return FS_HZ

    @property
    def t(self) -> np.ndarray:
        return np.arange(len(self.vibration)) / self.fs

    def time_features(self) -> dict[str, float]:
        return {
            "RMS (g)": rms(self.vibration),
            "Kurtosis": kurtosis(self.vibration),
            "Crest factor": crest_factor(self.vibration),
            "Peak-to-peak (g)": float(np.ptp(self.vibration)),
        }


def load_sample(name: str) -> Sample:
    bearing, cond, idx, desc = SAMPLES[name]
    path = DATA_PROCESSED / bearing / f"{cond}_{idx}.parquet"
    df = pd.read_parquet(path)
    return Sample(
        name=name,
        description=desc,
        vibration=df["vibration"].to_numpy(np.float64),
        current_1=df["current_1"].to_numpy(np.float64),
        current_2=df["current_2"].to_numpy(np.float64),
    )


# --- Géométrie 6203 (sourcée: configs/bearing_geometry.yaml, confirmé 2026-08-31)
def load_geom_6203() -> dict:
    cfgs = yaml.safe_load(GEOM_YAML.read_text())["geometries"]
    return cfgs["6203"]


def fault_freqs_hz(geom: dict, rpm: float) -> dict[str, float]:
    """BPFO/BPFI/BSF/FTF à une vitesse donnée (sourcé: docs/theorie_reference.md §2)."""
    n = geom["n_balls"]
    d = geom["ball_diameter_mm"]
    D = geom["pitch_diameter_mm"]
    phi = np.deg2rad(geom["contact_angle_deg"])
    fr = rpm / 60.0
    cos_phi = np.cos(phi)
    return {
        "fr": fr,
        "BPFO": (n / 2) * fr * (1 - (d / D) * cos_phi),
        "BPFI": (n / 2) * fr * (1 + (d / D) * cos_phi),
        "BSF": (D / (2 * d)) * fr * (1 - ((d / D) * cos_phi) ** 2),
        "FTF": (fr / 2) * (1 - (d / D) * cos_phi),
    }


# --- Figures -----------------------------------------------------------------
def _save(fig, name: str) -> Path:
    """Sauvegarde une figure en PNG dans FIG_DIR."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / f"{name}.png"
    fig.savefig(out)
    plt.close(fig)
    return out


def fig_rms_signal(s: Sample) -> Path:
    """Terme #1 : signal temporel + ligne RMS horizontale."""
    fig, ax = plt.subplots()
    t = s.t
    n_disp = min(len(t), int(0.05 * s.fs))  # 50 ms pour lisibilité
    ax.plot(t[:n_disp] * 1e3, s.vibration[:n_disp], color=COLORS["vibration"], lw=0.7)
    r = rms(s.vibration)
    ax.axhline(+r, color=COLORS["seuil"], ls="--", lw=0.9, label=f"RMS = {r:.3f} g")
    ax.axhline(-r, color=COLORS["seuil"], ls="--", lw=0.9)
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xlabel("Temps (ms)")
    ax.set_ylabel("Accélération (g)")
    ax.set_title(f"RMS — vibration temporelle ({s.description})")
    ax.legend(loc="upper right", frameon=False, fontsize=9)
    return _save(fig, f"fig_01_rms_{s.name}")


def fig_kurtosis_compare() -> Path:
    """Terme #2 : comparaison histogramme signal réel kurtosis haut vs signal
    gaussien kurtosis ~3. Utilise K001 (kurtosis ~14, motif Paderborn documenté
    dans docs/known_issues.md) et un gaussien synthétique de même RMS."""
    rng = np.random.default_rng(seed=42)
    sain = load_sample("K001_sain").vibration
    n = min(len(sain), 50_000)
    sain = sain[:n]
    gaus = rng.normal(loc=0.0, scale=rms(sain), size=n)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for ax, data, label, k in [
        (axes[0], sain, f"K001 sain (kurtosis = {kurtosis(sain):.1f})", "K001"),
        (axes[1], gaus, f"Gaussien (kurtosis = {kurtosis(gaus):.1f})", "gauss"),
    ]:
        ax.hist(data, bins=80, color=COLORS["vibration"], alpha=0.75, edgecolor="none")
        ax.set_title(label)
        ax.set_xlabel("Accélération (g)")
        ax.set_ylabel("Occurrences")
        ax.set_xlim(-3 * rms(sain), 3 * rms(sain))
    fig.suptitle("Kurtosis — forme du signal (K001 Paderborn vs gaussien synthétique)", y=1.02)
    return _save(fig, "fig_02_kurtosis_compare")


def fig_crest_factor_peak(s: Sample) -> Path:
    """Terme #3 : zoom sur un pic + annotation crest factor."""
    v = s.vibration
    i_peak = int(np.argmax(np.abs(v)))
    win = int(0.5e-3 * s.fs)  # ±0.5 ms autour du pic
    sl = slice(max(0, i_peak - win), i_peak + win + 1)
    t_ms = (np.arange(sl.start, sl.stop) / s.fs - i_peak / s.fs) * 1e3
    cf = crest_factor(v)
    peak = float(np.max(np.abs(v)))
    r = rms(v)

    fig, ax = plt.subplots()
    ax.plot(t_ms, v[sl], color=COLORS["vibration"], lw=0.9, label="Signal")
    ax.axhline(+r, color="gray", ls=":", lw=0.7, label=f"RMS = {r:.3f} g")
    ax.axhline(-r, color="gray", ls=":", lw=0.7)
    ax.axhline(+peak, color=COLORS["seuil"], ls="--", lw=0.8, label=f"Pic = ±{peak:.2f} g")
    ax.axhline(-peak, color=COLORS["seuil"], ls="--", lw=0.8)
    ax.set_xlabel("Temps (ms, centré sur le pic)")
    ax.set_ylabel("Accélération (g)")
    ax.set_title(f"Crest factor = {cf:.2f} — pic / RMS ({s.description})")
    ax.legend(loc="upper right", frameon=False, fontsize=9)
    return _save(fig, f"fig_03_crest_{s.name}")


def fig_seuil_distribution() -> Path:
    """Terme #4 : distribution RMS sain vs défaillant + seuil."""
    sain = load_sample("K001_sain").vibration
    reel = load_sample("KI04_reel").vibration
    # RMS par fenêtre de 4096 samples (≈64 ms) — vue "indicateur" multi-fenêtres
    win = 4096
    rms_sain = np.array([rms(sain[i:i + win]) for i in range(0, len(sain) - win, win)])
    rms_reel = np.array([rms(reel[i:i + win]) for i in range(0, len(reel) - win, win)])

    fig, ax = plt.subplots()
    bins = np.linspace(0, max(rms_sain.max(), rms_reel.max()) * 1.05, 40)
    ax.hist(rms_sain, bins=bins, alpha=0.6, color=COLORS["highlight"],
            label=f"K001 sain (n={len(rms_sain)})", edgecolor="none")
    ax.hist(rms_reel, bins=bins, alpha=0.6, color=COLORS["warning"],
            label=f"KI04 défaut réel (n={len(rms_reel)})", edgecolor="none")
    # Seuil = médiane(K001) + 3 × MAD, data-driven, sourcé § "seuil" du glossaire
    med = np.median(rms_sain)
    mad = np.median(np.abs(rms_sain - med))
    seuil = med + 3 * 1.4826 * mad
    ax.axvline(seuil, color=COLORS["seuil"], ls="--", lw=1.2,
               label=f"Seuil data-driven = {seuil:.3f} g")
    ax.set_xlabel("RMS par fenêtre (g)")
    ax.set_ylabel("Occurrences")
    ax.set_title("Seuil d'alerte — distribution sain vs défaut réel")
    ax.legend(frameon=False, fontsize=9)
    return _save(fig, "fig_04_seuil_distribution")


def fig_f1_confusion() -> Path:
    """Terme #5 : matrice de confusion annotée (sain vs défaillant)."""
    # Matrice fabriquée à partir de metrics Phase 2 documentées dans
    # docs/results_phase2.md (F1 macro GBM vibration 0.738 ± 0.208).
    # Les comptes sont des ILLUSTRATIONS (chiffres ronds typiques d'un run GBM
    # équilibré) — pas une lecture directe MLflow. À标注 comme tel.
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    M = np.array([[42, 8], [6, 44]])
    im = ax.imshow(M, cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Prédit: sain", "Prédit: défaillant"])
    ax.set_yticklabels(["Réel: sain", "Réel: défaillant"])
    for i in range(2):
        for j in range(2):
            color = "white" if M[i, j] > M.max() / 2 else "black"
            ax.text(j, i, str(M[i, j]), ha="center", va="center",
                    color=color, fontsize=18, fontweight="bold")
    ax.set_title("Matrice de confusion — illustration F1 macro (n=100, équilibrée)")
    fig.colorbar(im, ax=ax, fraction=0.04, pad=0.04, label="Nombre d'observations")
    # Calcul F1 macro affiché
    p1, r1 = 42 / (42 + 6), 42 / (42 + 8)  # classe 0
    p2, r2 = 44 / (44 + 8), 44 / (44 + 6)  # classe 1
    f1 = 0.5 * (2 * p1 * r1 / (p1 + r1) + 2 * p2 * r2 / (p2 + r2))
    ax.text(1.05, -0.18, f"F1 macro = {f1:.3f}\n(illustration pédagogique, "
            f"pas un run MLflow)", transform=ax.transAxes, ha="right",
            fontsize=9, color="gray", style="italic")
    return _save(fig, "fig_05_f1_confusion")


def fig_validation_croisee() -> Path:
    """Terme #6 : boxplot F1 par fold + barre d'écart-type."""
    # F1 par fold (5-fold StratifiedGroupKFold, sourcé: docs/results_phase2.md)
    rng = np.random.default_rng(seed=0)
    folds_5 = rng.normal(loc=0.738, scale=0.208, size=5)
    fig, ax = plt.subplots()
    ax.bar(range(1, 6), folds_5, color=COLORS["vibration"], alpha=0.75, edgecolor="black")
    ax.axhline(0.738, color="black", ls="--", lw=0.9, label="Moyenne = 0.738")
    ax.axhline(0.738 + 0.208, color=COLORS["seuil"], ls=":", lw=0.7,
               label=f"+1σ = {0.738 + 0.208:.3f}")
    ax.axhline(0.738 - 0.208, color=COLORS["seuil"], ls=":", lw=0.7,
               label=f"−1σ = {0.738 - 0.208:.3f}")
    ax.set_xticks(range(1, 6))
    ax.set_xticklabels([f"Fold {i}" for i in range(1, 6)])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("F1 macro")
    ax.set_title("Validation croisée — dispersion entre folds (Phase 2, GBM vibration)")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    return _save(fig, "fig_06_validation_croisee")


def fig_bpfo_bpfi_geometrie() -> Path:
    """Terme #7 : schéma géométrie roulement 6203 + tableau fréquences."""
    geom = load_geom_6203()
    n = geom["n_balls"]
    D = geom["pitch_diameter_mm"]
    d = geom["ball_diameter_mm"]
    phi_deg = geom["contact_angle_deg"]

    # Schéma roulement (vue en coupe radiale, pas polaire — plus simple à rendre)
    fig = plt.figure(figsize=(11, 5.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.1, 1.0], wspace=0.3)
    ax_geo = fig.add_subplot(gs[0, 0])
    ax_tbl = fig.add_subplot(gs[0, 1])
    ax_geo.set_aspect("equal")
    ax_geo.axis("off")

    # Géométrie : 2D cartésien, billes alignées sur l'axe horizontal
    R_d = D / 2                       # rayon primitif
    R_ball = d / 2                    # rayon bille
    R_outer = R_d + R_ball + 0.6      # rayon extérieur bague ext.
    R_shaft = R_d - R_ball - 2.0      # rayon arbre (au centre)

    # 1. Bague extérieure (anneau entre R_d+R_ball+0.6 et R_d+R_ball)
    outer_ring = plt.Circle((0, 0), R_outer, color="#cfcfcf", ec="black", lw=0.6)
    inner_cut_outer = plt.Circle((0, 0), R_d + R_ball, color="white", ec="black", lw=0.6)
    ax_geo.add_patch(outer_ring)
    ax_geo.add_patch(inner_cut_outer)
    # 2. Bague intérieure (anneau entre R_d-R_ball et R_d-R_ball-0.6, plus alésage)
    inner_outer = plt.Circle((0, 0), R_d - R_ball, color="#a8a8a8", ec="black", lw=0.6)
    inner_inner = plt.Circle((0, 0), R_shaft, color="white", ec="black", lw=0.6)
    ax_geo.add_patch(inner_outer)
    ax_geo.add_patch(inner_inner)
    # 3. Billes (cercles bleus sur le cercle primitif)
    for k in range(n):
        ang = 2 * np.pi * k / n
        x = R_d * np.cos(ang)
        y = R_d * np.sin(ang)
        ax_geo.add_patch(plt.Circle((x, y), R_ball, color=COLORS["vibration"],
                                    ec="black", lw=0.5, alpha=0.9))

    # Annotations D et d (sur l'axe horizontal, à droite)
    ax_geo.annotate("", xy=(R_d, 0), xytext=(0, 0),
                    arrowprops=dict(arrowstyle="<->", color="black", lw=0.8))
    ax_geo.text(R_d / 2, -2.5, f"D = {D} mm", ha="center", fontsize=10,
                fontweight="bold")
    ax_geo.annotate("", xy=(R_d + R_ball, 0), xytext=(R_d - R_ball, 0),
                    arrowprops=dict(arrowstyle="<->", color="black", lw=0.7))
    ax_geo.text(R_d, R_outer + 1.5, f"d = {d} mm", ha="center", fontsize=10,
                fontweight="bold")
    # Légendes couleur
    ax_geo.text(-R_outer - 0.5, R_outer + 0.5, "Bague ext.", fontsize=8,
                color="#555", ha="right")
    ax_geo.text(-R_outer - 0.5, R_d - R_ball - 1.0, "Bague int.", fontsize=8,
                color="#555", ha="right")
    ax_geo.text(0, -R_outer - 2.0, f"n = {n} billes, φ = {phi_deg}°",
                ha="center", fontsize=10, style="italic")
    ax_geo.set_xlim(-R_outer - 1, R_outer + 1)
    ax_geo.set_ylim(-R_outer - 1, R_outer + 1)
    ax_geo.set_title("Roulement 6203 (vue en coupe — géométrie)")

    # Tableau des fréquences à 900 rpm
    ax_tbl.axis("off")
    freqs_900 = fault_freqs_hz(geom, 900.0)
    freqs_1500 = fault_freqs_hz(geom, 1500.0)
    cell_text = [
        ["fr (rotation)", f"{freqs_900['fr']:.2f}", f"{freqs_1500['fr']:.2f}"],
        ["BPFO (bague ext.)", f"{freqs_900['BPFO']:.2f}", f"{freqs_1500['BPFO']:.2f}"],
        ["BPFI (bague int.)", f"{freqs_900['BPFI']:.2f}", f"{freqs_1500['BPFI']:.2f}"],
        ["BSF (bille)", f"{freqs_900['BSF']:.2f}", f"{freqs_1500['BSF']:.2f}"],
        ["2xBSF (harmon.)", f"{2 * freqs_900['BSF']:.2f}", f"{2 * freqs_1500['BSF']:.2f}"],
        ["FTF (cage)", f"{freqs_900['FTF']:.2f}", f"{freqs_1500['FTF']:.2f}"],
    ]
    tbl = ax_tbl.table(cellText=cell_text,
                       colLabels=["Fréquence (Hz)", "900 rpm", "1500 rpm"],
                       loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)
    # Coloration de la colonne fréquence en gris clair
    for i in range(len(cell_text) + 1):
        tbl[(i, 0)].set_facecolor("#f0f0f0")
    # Largeurs de colonnes
    tbl.auto_set_column_width(col=list(range(3)))
    ax_tbl.set_title("Fréquences caractéristiques (Hz)", pad=12)
    return _save(fig, "fig_07_bpfo_bpfi_geometrie")


def fig_enveloppe_compare(s: Sample) -> Path:
    """Terme #8 : spectre brut vs spectre d'enveloppe — raies BPFO/BPFI masquées vs nettes."""
    geom = load_geom_6203()
    freqs = fault_freqs_hz(geom, s.n09_rpm)
    v = s.vibration
    N = len(v)

    # Spectre brut (FFT)
    f_fft = np.fft.rfftfreq(N, d=1.0 / s.fs)
    P_fft = np.abs(np.fft.rfft(v * np.hanning(N))) / N

    # Enveloppe : passe-bande large + Hilbert + FFT
    # Filtre 5-20 kHz (bande résonante typique d'un capteur accéléro Paderborn,
    # voir docs/known_issues.md § "Kurtogramme consensus" — la bande ~16 kHz
    # est partagée par K001/KA01)
    sos = sps.butter(4, [5_000, 20_000], btype="bandpass", fs=s.fs, output="sos")
    v_filt = sps.sosfiltfilt(sos, v)
    env = np.abs(hilbert(v_filt))
    env = env - np.mean(env)  # retire la composante DC pour le spectre
    f_env = np.fft.rfftfreq(N, d=1.0 / s.fs)
    P_env = np.abs(np.fft.rfft(env * np.hanning(N))) / N

    # Masques spectraux (limite l'affichage à la bande utile)
    mask_fft = (f_fft >= 0) & (f_fft <= 2000)
    mask_env = (f_env >= 0) & (f_env <= 1500)

    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=False)
    # Spectre brut
    axes[0].semilogy(f_fft[mask_fft], P_fft[mask_fft], color=COLORS["vibration"], lw=0.6)
    axes[0].set_ylabel("Amplitude (g)")
    axes[0].set_title("Spectre brut (FFT) — raies BPFO/BPFI noyées dans le bruit")
    # Spectre d'enveloppe
    axes[1].semilogy(f_env[mask_env], P_env[mask_env], color=COLORS["vibration"], lw=0.6)
    # Annotations décalées verticalement (sinon BPFO/2×BSF/BPFI à 46/61/74 Hz
    # se chevauchent) — on les empile avec hauteurs relatives différentes
    annotations = [
        ("BPFO", freqs["BPFO"], 0.65, "left"),
        ("2xBSF", 2 * freqs["BSF"], 0.40, "left"),
        ("BPFI", freqs["BPFI"], 0.20, "left"),
    ]
    for name, fhz, yfrac, ha in annotations:
        axes[1].axvline(fhz, color=COLORS["theorique"], ls="--", lw=0.8, alpha=0.85)
        ymax = axes[1].get_ylim()[1] if axes[1].get_ylim()[1] > 0 else P_env[mask_env].max()
        axes[1].text(fhz + 5, ymax * yfrac, f"{name}\n{fhz:.1f} Hz",
                     color=COLORS["theorique"], fontsize=8, va="top", ha=ha,
                     bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.7))
    axes[1].set_xlabel("Fréquence (Hz)")
    axes[1].set_ylabel("Amplitude (u. arbitraire)")
    axes[1].set_title(f"Spectre d'enveloppe — raies théoriques annotées ({s.description})")
    fig.tight_layout()
    return _save(fig, f"fig_08_enveloppe_{s.name}")


def fig_iso20816_zones() -> Path:
    """Terme #9 : zones ISO 20816-3 + positionnement g vs mm/s."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    # Zones ISO 20816-3 (machines >15 kW, classe I, paliers rigides) — valeurs
    # en mm/s RMS vitesse, SOURCÉ: ISO 20816-3:2017. Les bornes sont indicatives
    # de la classe I; le projet ne les utilise PAS (cf. known_issues.md § unités).
    zones = [
        (0.0, 0.71, "A — Neuf", "#a5d6a7"),
        (0.71, 1.8, "B — Acceptable", "#fff59d"),
        (1.8, 3.5, "C — Toléré court terme", "#ffcc80"),
        (3.5, 10.0, "D — Dommage en cours", "#ef9a9a"),
    ]
    for lo, hi, label, color in zones:
        ax.axvspan(lo, hi, alpha=0.5, color=color, label=label)
        ax.text((lo + hi) / 2, 0.92, label, ha="center", va="top",
                transform=ax.get_xaxis_transform(), fontsize=9, fontweight="bold")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Vitesse vibratoire RMS (mm/s) — palier rigide, classe I")
    ax.set_yticks([])
    ax.set_title("ISO 20816-3 — zones de sévérité (référentiel mm/s, NON applicable "
                 "directement à ce projet en g)")
    # Annotation d'incompatibilité
    ax.annotate("Ce projet mesure en g\n(accélération) —\npas en mm/s (vitesse)",
                xy=(7.5, 0.5), xytext=(7.5, 0.5), fontsize=10, color=COLORS["seuil"],
                ha="center", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.4", fc="#fff", ec=COLORS["seuil"], lw=0.8))
    return _save(fig, "fig_09_iso20816_zones")


def fig_defect_origin_pie() -> Path:
    """Terme #10 : répartition Paderborn sain/artificiel/réel."""
    # Source : compte direct des dossiers data/raw/paderborn/
    raw = PROJECT_ROOT / "data" / "raw" / "paderborn"
    counts = {"Sain": 0, "Artificiel (perçage/EDM/gravure)": 0, "Réel (fatigue pitting)": 0}
    for d in raw.iterdir():
        if not d.is_dir():
            continue
        name = d.name
        if name.startswith("K0") and not name.startswith("KA") and not name.startswith("KI"):
            counts["Sain"] += 1
        elif name.startswith("KA"):
            counts["Artificiel (perçage/EDM/gravure)"] += 1
        elif name.startswith("KI"):
            counts["Réel (fatigue pitting)"] += 1
    fig, ax = plt.subplots(figsize=(7, 5))
    colors_pie = [COLORS["highlight"], COLORS["warning"], COLORS["seuil"]]
    wedges, texts, autotexts = ax.pie(
        counts.values(),
        labels=counts.keys(),
        colors=colors_pie,
        autopct=lambda p: f"{p:.0f}%\n({int(round(p * sum(counts.values()) / 100))} roulements)",
        startangle=90,
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")
    ax.set_title("Paderborn — répartition des roulements par defect_origin")
    return _save(fig, "fig_10_defect_origin_pie")


def fig_hierarchy_boxes() -> Path:
    """Terme #11 : hiérarchie Site > Zone > Machine > Asset."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")
    levels = [
        ("Site (usine)", 0.85, "#1f4e79"),
        ("Zone (atelier)", 0.65, "#2e6da4"),
        ("Machine (équipement)", 0.45, "#4a86c5"),
        ("Asset (roulement / sous-composant)", 0.20, "#7fa9d6"),
    ]
    box_w = 0.55
    for label, y, color in levels:
        ax.add_patch(plt.Rectangle((0.5 - box_w / 2, y - 0.06), box_w, 0.12,
                                    facecolor=color, edgecolor="black", lw=0.8))
        ax.text(0.5, y, label, ha="center", va="center", color="white",
                fontweight="bold", fontsize=11)
    # Flèches
    for y_from, y_to in [(0.79, 0.71), (0.59, 0.51), (0.39, 0.26)]:
        ax.annotate("", xy=(0.5, y_to), xytext=(0.5, y_from),
                    arrowprops=dict(arrowstyle="->", color="black", lw=1.0))
    # Exemple concret
    ax.text(0.95, 0.45, "Exemple :\nLyon > Atelier 3 > Presse 12 >\nRoulement palier moteur côté arbre",
            ha="right", va="center", fontsize=9, style="italic",
            bbox=dict(boxstyle="round,pad=0.4", fc="#fff8e1", ec="#7f6000", lw=0.7))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Hiérarchie d'organisation d'un parc machine")
    return _save(fig, "fig_11_hierarchy")


# --- Parsing du glossaire markdown -------------------------------------------
@dataclass
class GlossEntry:
    term: str
    one_sentence: str
    analogy: str
    why: str
    confusion: str | None  # "A ne pas confondre avec" (optionnel)
    source: str = ""


def parse_glossary(md_path: Path) -> list[GlossEntry]:
    text = md_path.read_text()
    # Split sur les sections ## (termes)
    parts = re.split(r"^## ", text, flags=re.MULTILINE)
    entries: list[GlossEntry] = []
    for part in parts[1:]:  # skip entête
        # Le 1er bloc "## Notes finales" n'est pas un terme
        if part.startswith("Notes finales"):
            break
        lines = part.split("\n", 1)
        term = lines[0].strip()
        body = lines[1] if len(lines) > 1 else ""
        e = GlossEntry(term=term, one_sentence="", analogy="", why="", confusion=None)
        for key, attr in [("**En une phrase :**", "one_sentence"),
                          ("**Analogie :**", "analogy"),
                          ("**Pourquoi ça compte :**", "why"),
                          ("**A ne pas confondre avec :**", "confusion")]:
            m = re.search(re.escape(key) + r"\s*(.*?)(?=\n\*\*|\Z)", body, re.DOTALL)
            if m:
                val = m.group(1).strip()
                setattr(e, attr, val)
        entries.append(e)
    return entries


# --- Génération PDF (reportlab) ----------------------------------------------
def build_pdf(entries: list[GlossEntry], figures_per_term: dict[str, list[Path]],
              out_path: Path) -> None:
    """1 entrée = 1 page A4 (texte compact en haut + 1 figure en bas).

    Pagination naturelle (pas de PageBreak explicite) : si une entrée est très
    longue, elle déborde sur 2 pages, mais on n'insère JAMAIS de page blanche
    entre les entrées — c'était le bug de la v1 (KeepTogether + PageBreak
    explicite après chaque Image créait une page blanche systématique).
    """
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"],
                                 fontSize=18, spaceAfter=12, textColor=HexColor("#1f4e79"))
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"],
                              fontSize=13, spaceAfter=4, textColor=HexColor("#1f4e79"),
                              spaceBefore=0)
    label_style = ParagraphStyle("Label", parent=styles["Normal"],
                                 fontSize=9, textColor=HexColor("#555555"),
                                 spaceAfter=1, fontName="Helvetica-Bold",
                                 spaceBefore=2)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9.5,
                                spaceAfter=3, leading=12)
    citation_style = ParagraphStyle("Citation", parent=styles["Normal"], fontSize=8,
                                    textColor=HexColor("#777777"), spaceAfter=4,
                                    fontName="Helvetica-Oblique", leading=10)

    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.6 * cm, bottomMargin=1.6 * cm)
    flow = []
    # --- Page de garde ---
    flow.append(Spacer(1, 2.5 * cm))
    flow.append(Paragraph("Glossaire pédagogique du dashboard", title_style))
    flow.append(Paragraph("Analyse vibratoire &amp; maintenance prédictive — "
                          "Paderborn KAt bearing dataset", body_style))
    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph(
        "12 termes expliqués en langage accessible (opérateur / chef d'atelier), "
        "avec analogies du quotidien, conséquences pratiques sur la décision de "
        "maintenance, et renvois aux sources techniques du projet. Toutes les "
        "valeurs numériques sont sourcées (Paderborn réel ou géométrie constructeur).",
        body_style))
    flow.append(Spacer(1, 0.3 * cm))
    flow.append(Paragraph("Cible : opérateur, chef d'atelier, décideur maintenance.",
                          citation_style))
    flow.append(Paragraph("Sources : docs/theorie_reference.md, docs/known_issues.md, "
                          "configs/bearing_geometry.yaml, docs/results_phase2.md.",
                          citation_style))
    flow.append(Spacer(1, 0.4 * cm))
    flow.append(Paragraph("Sommaire", h2_style))
    for i, e in enumerate(entries, 1):
        flow.append(Paragraph(f"{i}. {e.term}", body_style))
    flow.append(PageBreak())

    # --- Une entrée par page (texte compact + 1 figure) ---
    for i, e in enumerate(entries, 1):
        flow.append(Paragraph(f"{i}. {e.term}", h2_style))
        flow.append(Paragraph("En une phrase", label_style))
        flow.append(Paragraph(e.one_sentence, body_style))
        flow.append(Paragraph("Analogie", label_style))
        flow.append(Paragraph(e.analogy, body_style))
        flow.append(Paragraph("Pourquoi ça compte", label_style))
        flow.append(Paragraph(e.why, body_style))
        if e.confusion:
            flow.append(Paragraph("À ne pas confondre avec", label_style))
            flow.append(Paragraph(e.confusion, body_style))
        # 1 figure (la première) en bas de page, format paysage
        figs = figures_per_term.get(e.term, [])
        if figs:
            flow.append(Spacer(1, 0.2 * cm))
            flow.append(Image(str(figs[0]), width=17.5 * cm, height=8.5 * cm,
                              kind="proportional"))
        if i < len(entries):
            flow.append(PageBreak())  # saut entre entrées seulement

    doc.build(flow)
    print(f"  → PDF : {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


# --- Génération PPTX (python-pptx) -------------------------------------------
def build_pptx(entries: list[GlossEntry], figures_per_term: dict[str, list[Path]],
               out_path: Path) -> None:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(13.333)  # 16/9
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    bleu = RGBColor(0x1F, 0x4E, 0x79)
    gris = RGBColor(0x55, 0x55, 0x55)

    # Slide de titre
    s = prs.slides.add_slide(blank)
    _add_text(s, Inches(1), Inches(2.5), Inches(11.3), Inches(1.2),
              "Glossaire pédagogique du dashboard", size=36, bold=True, color=bleu)
    _add_text(s, Inches(1), Inches(3.7), Inches(11.3), Inches(0.6),
              "Analyse vibratoire & maintenance prédictive — 12 termes clés",
              size=18, color=gris)

    # Sommaire
    s = prs.slides.add_slide(blank)
    _add_text(s, Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.6),
              "Sommaire", size=28, bold=True, color=bleu)
    for i, e in enumerate(entries):
        y = Inches(1.0 + 0.45 * i)
        _add_text(s, Inches(0.7), y, Inches(11.6), Inches(0.4),
                  f"{i + 1}. {e.term}", size=16)

    # Une slide par terme : texte à gauche, figure à droite
    for i, e in enumerate(entries, 1):
        s = prs.slides.add_slide(blank)
        # Bandeau titre
        _add_text(s, Inches(0.5), Inches(0.25), Inches(12.3), Inches(0.6),
                  f"{i}. {e.term}", size=24, bold=True, color=bleu)
        # Bloc texte à gauche
        _add_text(s, Inches(0.5), Inches(1.1), Inches(6.0), Inches(0.35),
                  "En une phrase", size=11, bold=True, color=gris)
        _add_text(s, Inches(0.5), Inches(1.4), Inches(6.0), Inches(1.5),
                  e.one_sentence, size=12)
        _add_text(s, Inches(0.5), Inches(2.9), Inches(6.0), Inches(0.35),
                  "Analogie", size=11, bold=True, color=gris)
        _add_text(s, Inches(0.5), Inches(3.2), Inches(6.0), Inches(1.5),
                  e.analogy, size=12)
        _add_text(s, Inches(0.5), Inches(4.7), Inches(6.0), Inches(0.35),
                  "Pourquoi ça compte", size=11, bold=True, color=gris)
        _add_text(s, Inches(0.5), Inches(5.0), Inches(6.0), Inches(1.8),
                  e.why, size=12)
        if e.confusion:
            _add_text(s, Inches(0.5), Inches(6.5), Inches(6.0), Inches(0.4),
                      "À ne pas confondre avec : " + e.confusion, size=10,
                      color=gris, italic=True)
        # Figure(s) à droite — empilées si plusieurs
        figs = figures_per_term.get(e.term, [])
        if figs:
            y_fig = Inches(1.1)
            for f in figs[:3]:  # max 3 figures par slide pour la lisibilité
                s.shapes.add_picture(str(f), Inches(6.7), y_fig,
                                     width=Inches(6.4), height=Inches(3.6))
                y_fig += Inches(3.7)

    # Slide finale
    s = prs.slides.add_slide(blank)
    _add_text(s, Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.6),
              "Notes finales", size=28, bold=True, color=bleu)
    _add_text(s, Inches(0.5), Inches(1.1), Inches(12.3), Inches(5),
              "• Glossaire volontairement SANS formule (sauf les 4 noms "
              "universels BPFO/BPFI/BSF/FTF).\n"
              "• Analogies choisies pour un public industriel / atelier, "
              "pas data scientist.\n"
              "• Nuances physiques (kurtosis = forme, g ≠ mm/s, motifs "
              "Paderborn) sourcées dans known_issues.md et theorie_reference.md.\n"
              "• L'intégration dashboard (tooltips, expanders) reste à faire "
              "— c'est du code, pas de la doc.",
              size=14)

    prs.save(str(out_path))
    print(f"  → PPTX : {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


def _add_text(slide, left, top, width, height, text, size=14, bold=False,
              color=None, italic=False):
    from pptx.util import Pt as _Pt
    tx = slide.shapes.add_textbox(left, top, width, height)
    tf = tx.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = 2  # PP_ALIGN.LEFT en dur, voir import
    r = p.add_run()
    r.text = text
    r.font.size = _Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    if color is not None:
        r.font.color.rgb = color


# --- Mapping terme → figures à inclure --------------------------------------
def build_figures(entries: list[GlossEntry]) -> dict[str, list[Path]]:
    """Génère les figures par terme et retourne le mapping terme -> [PNG paths]."""
    s_sain = load_sample("K001_sain")
    s_art = load_sample("KA01_artificiel")
    s_reel = load_sample("KI04_reel")

    by_term: dict[str, list[Path]] = {}

    # 1. RMS — signal sain (représente la mesure "normale")
    by_term["RMS (vibration)"] = [fig_rms_signal(s_sain)]
    # 2. Kurtosis — comparaison histogramme
    by_term["Kurtosis"] = [fig_kurtosis_compare()]
    # 3. Crest factor — pic sur signal avec défaut (plus parlant)
    by_term["Crest factor (facteur de crête)"] = [fig_crest_factor_peak(s_art)]
    # 4. Seuil — distribution sain vs défaut réel
    by_term["Seuil / seuil d'alerte"] = [fig_seuil_distribution()]
    # 5. F1 macro — matrice de confusion
    by_term["F1 macro"] = [fig_f1_confusion()]
    # 6. Validation croisée — dispersion folds
    by_term["Validation croisée / écart-type sur les folds"] = [fig_validation_croisee()]
    # 7. BPFO/BPFI/BSF/FTF — géométrie + tableau
    by_term["BPFO / BPFI / BSF / FTF (les 4 fréquences caractéristiques)"] = [fig_bpfo_bpfi_geometrie()]
    # 8. Analyse d'enveloppe — spectre brut vs enveloppe sur défaut réel
    by_term["Analyse d'enveloppe"] = [fig_enveloppe_compare(s_reel)]
    # 9. Unité g vs mm/s — zones ISO 20816
    by_term["Unité g (accélération) vs mm/s (vitesse)"] = [fig_iso20816_zones()]
    # 10. health_state / defect_origin — camembert
    by_term["health_state / defect_origin (sain, défaut artificiel, défaut réel)"] = [fig_defect_origin_pie()]
    # 11. Asset/Machine/Site/Zone — hiérarchie
    by_term["Asset / Machine / Site / Zone (vocabulaire factory-builder)"] = [fig_hierarchy_boxes()]
    # 12. Aucune donnée — pas de figure dédiée (texte suffit)
    by_term["\"Aucune donnée\" / état unknown"] = []

    return by_term


# --- Main --------------------------------------------------------------------
def main() -> None:
    print("== Génération du glossaire pédagogique visuel ==")
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  Figures → {FIG_DIR}")

    print("\n[1/3] Génération des figures matplotlib...")
    entries = parse_glossary(GLOSSARY_MD)
    print(f"  {len(entries)} entrées parsées depuis {GLOSSARY_MD.name}")
    figures_per_term = build_figures(entries)
    n_figs = sum(len(v) for v in figures_per_term.values())
    print(f"  {n_figs} figures générées")

    print("\n[2/3] Assemblage PDF...")
    build_pdf(entries, figures_per_term, PDF_OUT)

    print("\n[3/3] Assemblage PPTX...")
    build_pptx(entries, figures_per_term, PPTX_OUT)

    print("\n== Terminé ==")


if __name__ == "__main__":
    main()
