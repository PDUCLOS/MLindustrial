"""Lecture des .mat Paderborn -> tableaux numpy + parquet.

Format .mat (verifie sur les fichiers telecharges, structure MATLAB v5) :
un struct top-level nomme d'apres le fichier, avec un champ Y = liste de
struct-canaux {Name, Data, ...}. Canaux d'interet : vibration_1,
phase_current_1, phase_current_2 (256001 pts a 64 kHz). Les autres canaux
(force, speed, torque, temp_*) sont mecaniques/thermiques a raster plus bas
et ignores ici.
"""

import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio

PADERBORN_CHANNELS = {
    "vibration_1": "vibration",
    "phase_current_1": "current_1",
    "phase_current_2": "current_2",
}
PADERBORN_SAMPLING_RATE_HZ = 64000.0
PADERBORN_SPEED_CHANNEL_NAME = "speed"  # rpm, raster Mech_4kHz (verifie empiriquement : mean~=1499.6 pour condition N15)

_FILENAME_RE = re.compile(r"^(?P<condition>[A-Z0-9]+_[A-Z0-9]+_[A-Z0-9]+)_(?P<code>[A-Z]+\d+)_(?P<index>\d+)\.mat$")


def parse_paderborn_filename(filename: str) -> dict:
    """'N15_M07_F10_K001_1.mat' -> {'condition': 'N15_M07_F10', 'code': 'K001', 'measurement_index': 1}"""
    m = _FILENAME_RE.match(filename)
    if not m:
        raise ValueError(f"Nom de fichier Paderborn inattendu : {filename!r}")
    return {
        "condition": m.group("condition"),
        "code": m.group("code"),
        "measurement_index": int(m.group("index")),
    }


def load_paderborn_measurement(
    mat_path: Path,
) -> tuple[dict[str, np.ndarray], datetime, np.ndarray | None]:
    """Charge un fichier .mat Paderborn : canaux {vibration, current_1, current_2}
    + horodatage reel d'acquisition (Description.General.DateTime) + vitesse
    reelle mesuree (canal 'speed', rpm, raster different donc retournee a part
    plutot que fusionnee dans `out` - permet une detection automatique
    vitesse fixe/variable a partir du signal, voir src/features/speed.py)."""
    raw = sio.loadmat(str(mat_path), simplify_cells=True)
    top_keys = [k for k in raw.keys() if not k.startswith("__")]
    if len(top_keys) != 1:
        raise ValueError(f"{mat_path} : cle top-level ambigue ({top_keys})")
    record = raw[top_keys[0]]

    out: dict[str, np.ndarray] = {}
    speed: np.ndarray | None = None
    for ch in record["Y"]:
        name = ch.get("Name")
        if name in PADERBORN_CHANNELS:
            out[PADERBORN_CHANNELS[name]] = np.asarray(ch["Data"], dtype=np.float64)
        elif name == PADERBORN_SPEED_CHANNEL_NAME:
            speed = np.asarray(ch["Data"], dtype=np.float64)

    missing = set(PADERBORN_CHANNELS.values()) - set(out.keys())
    if missing:
        raise ValueError(f"{mat_path} : canaux manquants {missing}")

    date_str = record["Description"]["General"]["DateTime"]
    acquired_at = datetime.strptime(date_str, "%d.%m.%Y %H:%M:%S")

    return out, acquired_at, speed


def write_measurement_parquet(channels: dict[str, np.ndarray], out_path: Path) -> None:
    """Ecrit vibration/current_1/current_2 alignes par index dans un seul parquet."""
    lengths = {len(v) for v in channels.values()}
    if len(lengths) != 1:
        raise ValueError(f"Canaux de longueurs differentes : { {k: len(v) for k, v in channels.items()} }")
    n = lengths.pop()
    df = pd.DataFrame({"sample_index": np.arange(n), **channels})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
