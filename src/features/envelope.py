"""Analyse d'enveloppe (Hilbert) et kurtogramme pour la selection de bande
resonante (voir docs/brief_projet.md section 5).

Le kurtogramme implemente ici balaie plusieurs resolutions temps/frequence
(STFT a plusieurs longueurs de fenetre) et garde le (fc, bandwidth) qui
maximise le kurtosis spectral - c'est le meme principe que le Fast Kurtogram
d'Antoni (2007), mais via un balayage STFT multi-niveaux plutot que l'arbre
recursif de filtres 1/3-binaire de l'article original. Choix assume : plus
simple a verifier correct sans reference pour valider un portage de l'arbre
recursif, au prix d'un cout calcul plus eleve (negligeable ici, <1s/signal).

Premiere version (une seule resolution fixe, nperseg=256) testee sur un
sous-ensemble Paderborn donnait un classement sain > defaut artificiel >
defaut reel sur l'energie BPFO - physiquement incoherent. Cause identifiee :
une resolution unique ne separe pas la resonance roulement du bruit
large-bande de l'accouplement moteur/banc. Le balayage multi-niveaux vise a
corriger ca ; a reverifier sur le meme sous-ensemble avant de faire confiance
aux resultats.
"""

import numpy as np
from scipy import signal, stats


def bandpass_filter(x: np.ndarray, fs: float, low_hz: float, high_hz: float, order: int = 4) -> np.ndarray:
    nyq = fs / 2
    low = max(low_hz / nyq, 1e-6)
    high = min(high_hz / nyq, 0.999999)
    sos = signal.butter(order, [low, high], btype="bandpass", output="sos")
    return signal.sosfiltfilt(sos, x)


def envelope(x: np.ndarray) -> np.ndarray:
    """Enveloppe temporelle via transformee de Hilbert."""
    return np.abs(signal.hilbert(x))


def envelope_spectrum(x: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
    """Spectre de l'enveloppe (apres retrait de la composante continue)."""
    env = envelope(x)
    env = env - np.mean(env)
    n = len(env)
    spectrum = np.abs(np.fft.rfft(env)) / n
    freqs = np.fft.rfftfreq(n, d=1 / fs)
    return freqs, spectrum


def spectral_kurtosis(x: np.ndarray, fs: float, nperseg: int) -> tuple[np.ndarray, np.ndarray]:
    """Kurtosis spectral a UNE resolution donnee : kurtosis temporelle de la
    magnitude STFT, par bin de frequence. Brique de base du kurtogramme."""
    f, _, Zxx = signal.stft(x, fs=fs, nperseg=nperseg)
    mag = np.abs(Zxx)
    sk = stats.kurtosis(mag, axis=1, fisher=False)
    return f, sk


def kurtogram(
    x: np.ndarray,
    fs: float,
    levels: tuple[int, ...] = (2, 3, 4, 5, 6, 7, 8),
    min_freq_hz: float = 500.0,
) -> dict:
    """Balaie plusieurs resolutions (nperseg = fs / 2**level) et retourne la
    combinaison (niveau, frequence centrale) qui maximise le kurtosis spectral,
    plus la carte complete (pour diagnostic/visualisation).

    Exclut les bins dont la bande [fc-bandwidth, fc+bandwidth] deborderait de
    [min_freq_hz, Nyquist[ - les bins DC et Nyquist d'une STFT ont une
    variance/kurtosis artificiellement gonflee par les effets de bord du
    fenetrage (fuite spectrale), pas une resonance physique. Verifie sur
    Paderborn K001 : sans cette exclusion, le kurtogramme convergeait vers
    fc=32000 Hz (Nyquist exact a 64 kHz) avec un score a peine superieur a la
    bande 15872-16128 Hz qui, elle, ressort systematiquement forte a TOUS les
    niveaux 2 a 8 - signature typique d'une vraie resonance structurelle
    (robuste au changement de resolution) contre un artefact de bord
    (uniquement dominant a la resolution la plus fine). Voir docs/known_issues.md."""
    best = {"kurt": -np.inf, "fc": None, "bandwidth": None, "level": None}
    kurtogram_map = []
    nyquist = fs / 2

    for level in levels:
        nperseg = max(int(fs / (2**level)), 16)
        if nperseg >= len(x) // 4:
            continue
        f, sk = spectral_kurtosis(x, fs, nperseg=nperseg)
        bandwidth = fs / nperseg
        valid = (f - bandwidth >= min_freq_hz) & (f + bandwidth <= nyquist)
        if not np.any(valid):
            continue
        kurtogram_map.append({"level": level, "nperseg": nperseg, "freqs": f, "sk": sk, "valid": valid})

        idx = int(np.argmax(np.where(valid, sk, -np.inf)))
        if sk[idx] > best["kurt"]:
            best = {"kurt": float(sk[idx]), "fc": float(f[idx]), "bandwidth": float(bandwidth), "level": level}

    if best["fc"] is None:
        raise ValueError("Kurtogramme : aucune resolution valide (signal trop court ou min_freq_hz trop haut).")
    return {"best": best, "map": kurtogram_map}


def select_resonance_band(x: np.ndarray, fs: float, min_freq_hz: float = 500.0) -> tuple[float, float]:
    """Bande [low, high] autour du (fc, bandwidth) retenu par le kurtogramme.

    INSTABLE par signal individuel (voir docs/known_issues.md : sur
    K001/KA01/KA04, chaque mesure convergeait vers une bande differente -
    15.8 kHz / 17.9 kHz / 504 Hz - au lieu de la resonance structurelle
    fixe attendue). Preferer `consensus_resonance_band` sur un groupe de
    signaux (meme roulement ou meme condition) pour un resultat exploitable."""
    result = kurtogram(x, fs, min_freq_hz=min_freq_hz)
    best = result["best"]
    low = max(best["fc"] - best["bandwidth"], min_freq_hz)
    high = best["fc"] + best["bandwidth"]
    return low, high


def average_kurtogram_map(
    signals: list[np.ndarray],
    fs: float,
    levels: tuple[int, ...] = (2, 3, 4, 5, 6, 7, 8),
    min_freq_hz: float = 500.0,
    max_length_mismatch_ratio: float = 0.1,
) -> list[dict]:
    """Kurtogramme moyenne sur un groupe de signaux (meme fs).

    La resonance structurelle capteur/logement est une propriete MECANIQUE
    FIXE du montage (docs/brief_projet.md section 5) - elle ne doit pas changer d'une
    mesure a l'autre. Moyenner le kurtosis spectral sur plusieurs mesures
    (ex. les 20 mesures d'un roulement pour une condition) lisse les
    artefacts ponctuels (transitoire d'accouplement, bruit isole) qui
    faisaient diverger le choix de bande par-signal - voir
    docs/known_issues.md.

    Les signaux du monde reel n'ont PAS tous exactement la meme longueur -
    verifie sur Paderborn : les mesures "4 s a 64 kHz" varient en realite de
    256000 a ~261000 echantillons (gigue d'acquisition, ~2%). Tronques au
    minimum commun du groupe pour aligner les grilles de frequence par
    niveau - une troncature de quelques % en fin de signal ne change pas la
    resonance structurelle mesuree. Leve une erreur si l'ecart depasse
    max_length_mismatch_ratio (10% par defaut) : au-dela, ce n'est plus de la
    gigue d'acquisition mais un probleme de donnees a investiguer, pas a
    tronquer silencieusement."""
    if not signals:
        raise ValueError("average_kurtogram_map : liste de signaux vide.")
    lengths = [len(s) for s in signals]
    min_len, max_len = min(lengths), max(lengths)
    if min_len == 0:
        raise ValueError("average_kurtogram_map : signal de longueur nulle dans le groupe.")
    if (max_len - min_len) / min_len > max_length_mismatch_ratio:
        raise ValueError(
            f"average_kurtogram_map : ecart de longueur trop grand entre signaux "
            f"({min_len} a {max_len}, {100*(max_len-min_len)/min_len:.1f}%) - "
            f"pas de la gigue d'acquisition normale, a investiguer avant de tronquer."
        )
    signals = [s[:min_len] for s in signals]

    per_signal_maps = [kurtogram(s, fs, levels=levels, min_freq_hz=min_freq_hz)["map"] for s in signals]
    n_levels = {len(m) for m in per_signal_maps}
    if len(n_levels) != 1:
        raise ValueError("average_kurtogram_map : nombre de niveaux valides different entre signaux - grilles non alignees.")

    averaged = []
    for level_idx in range(n_levels.pop()):
        level = per_signal_maps[0][level_idx]["level"]
        nperseg = per_signal_maps[0][level_idx]["nperseg"]
        freqs = per_signal_maps[0][level_idx]["freqs"]
        valid = per_signal_maps[0][level_idx]["valid"]  # ne depend que de freqs/bandwidth, identique pour tous les signaux
        sk_stack = np.stack([m[level_idx]["sk"] for m in per_signal_maps])
        averaged.append(
            {
                "level": level,
                "nperseg": nperseg,
                "freqs": freqs,
                "valid": valid,
                "sk": sk_stack.mean(axis=0),
                "sk_std": sk_stack.std(axis=0),
                "n_signals": len(signals),
            }
        )
    return averaged


def consensus_resonance_band(
    signals: list[np.ndarray],
    fs: float,
    levels: tuple[int, ...] = (2, 3, 4, 5, 6, 7, 8),
    min_freq_hz: float = 500.0,
) -> dict:
    """Bande de demodulation stable pour un groupe de signaux - maximise le
    kurtosis spectral MOYEN du groupe (voir average_kurtogram_map) plutot
    que le kurtosis d'un signal isole. A appeler une fois par groupe
    (roulement, ou roulement x condition) et reutiliser la meme bande pour
    calculer fault_frequency_energies sur chaque mesure du groupe - voir
    docs/known_issues.md."""
    avg_map = average_kurtogram_map(signals, fs, levels=levels, min_freq_hz=min_freq_hz)
    best = {"kurt": -np.inf, "fc": None, "bandwidth": None, "level": None}
    for m in avg_map:
        valid = m["valid"]
        if not np.any(valid):
            continue
        idx = int(np.argmax(np.where(valid, m["sk"], -np.inf)))
        if m["sk"][idx] > best["kurt"]:
            best = {
                "kurt": float(m["sk"][idx]),
                "fc": float(m["freqs"][idx]),
                "bandwidth": float(fs / m["nperseg"]),
                "level": m["level"],
            }

    if best["fc"] is None:
        raise ValueError("consensus_resonance_band : aucune resolution valide (signaux trop courts ou min_freq_hz trop haut).")

    low = max(best["fc"] - best["bandwidth"], min_freq_hz)
    high = best["fc"] + best["bandwidth"]
    return {"low": low, "high": high, "best": best, "n_signals": len(signals)}


def band_energy(freqs: np.ndarray, spectrum: np.ndarray, target_freq_hz: float, tolerance_hz: float = 5.0) -> float:
    """Energie du spectre d'enveloppe autour d'une frequence cible (defaut/harmonique)."""
    mask = np.abs(freqs - target_freq_hz) <= tolerance_hz
    return float(np.sum(spectrum[mask] ** 2))


def fault_frequency_energies(
    x: np.ndarray,
    fs: float,
    fault_freqs_hz: dict[str, float],
    n_harmonics: int = 3,
    tolerance_hz: float = 5.0,
    resonance_band: tuple[float, float] | None = None,
) -> dict[str, float]:
    """Energie du spectre d'enveloppe (apres bande resonante) aux frequences
    de defaut et a leurs harmoniques (1x, 2x, 3x...).

    resonance_band : bande [low, high] deja choisie (typiquement par
    consensus_resonance_band sur le groupe de mesures du roulement/de la
    condition - voir docs/known_issues.md). Si None, retombe sur le
    kurtogramme par-signal (select_resonance_band) - INSTABLE, a n'utiliser
    que pour des tests/comparaisons, pas pour un resultat publie."""
    low, high = resonance_band if resonance_band is not None else select_resonance_band(x, fs)
    filtered = bandpass_filter(x, fs, low, high)
    freqs, spectrum = envelope_spectrum(filtered, fs)

    energies: dict[str, float] = {}
    for name, base_freq in fault_freqs_hz.items():
        for h in range(1, n_harmonics + 1):
            key = f"{name}_h{h}_energy"
            energies[key] = band_energy(freqs, spectrum, base_freq * h, tolerance_hz)
    return energies
