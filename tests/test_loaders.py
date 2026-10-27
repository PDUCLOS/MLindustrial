"""Tests pour src/data/loaders.py — regex parsing des noms de fichier Paderborn
+ ecriture parquet.

Couvre :
- parse_paderborn_filename : cas valides (K sain, KA artificial, KI inner, KB both) + cas invalides
- write_measurement_parquet : alignement des canaux, erreur si longueurs differentes

Comble un trou identifie par l'audit du 2026-08-31 (cf. docs/test_coverage_audit_2026-08-31.md) :
loaders.py etait ecrit sans tests, le regex de parsing casserait silencieusement sur un
nom de fichier inattendu (pas de ValueError, ou mauvaise extraction silencieuse).

Note : load_paderborn_measurement (lecture .mat) n'est pas testee ici — c'est un test
d'integration (necessite un vrai .mat, fichiers gitignored, ~8 MB chacun). A tester
explicitement avec pytest.mark.integration quand on dispose d'un environnement adapte.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data.loaders import (
    PADERBORN_CHANNELS,
    PADERBORN_SAMPLING_RATE_HZ,
    PADERBORN_SPEED_CHANNEL_NAME,
    load_paderborn_measurement,
    parse_paderborn_filename,
    write_measurement_parquet,
)

# ---------- parse_paderborn_filename : cas valides ----------

@pytest.mark.parametrize("filename,expected", [
    # Roulements sains (K)
    ("N15_M07_F10_K001_1.mat", {"condition": "N15_M07_F10", "code": "K001", "measurement_index": 1}),
    ("N09_M07_F10_K002_20.mat", {"condition": "N09_M07_F10", "code": "K002", "measurement_index": 20}),
    ("N15_M07_F10_K006_1.mat", {"condition": "N15_M07_F10", "code": "K006", "measurement_index": 1}),
    # Defauts artificiels (KA)
    ("N15_M07_F10_KA01_1.mat", {"condition": "N15_M07_F10", "code": "KA01", "measurement_index": 1}),
    ("N15_M07_F10_KA22_15.mat", {"condition": "N15_M07_F10", "code": "KA22", "measurement_index": 15}),
    # Defauts reels - bague interieure (KI)
    ("N15_M07_F10_KI17_1.mat", {"condition": "N15_M07_F10", "code": "KI17", "measurement_index": 1}),
    ("N15_M07_F10_KI21_20.mat", {"condition": "N15_M07_F10", "code": "KI21", "measurement_index": 20}),
    # Defauts reels - bagues int+ext (KB)
    ("N15_M07_F10_KB24_10.mat", {"condition": "N15_M07_F10", "code": "KB24", "measurement_index": 10}),
    ("N15_M07_F10_KB27_5.mat", {"condition": "N15_M07_F10", "code": "KB27", "measurement_index": 5}),
    # Conditions differentes
    ("N09_M07_F10_K001_1.mat", {"condition": "N09_M07_F10", "code": "K001", "measurement_index": 1}),
])
def test_parse_paderborn_filename_valid(filename, expected):
    """Tous les formats attendus (K/KA/KI/KB + 4 conditions + 20 mesures) sont parses correctement."""
    result = parse_paderborn_filename(filename)
    assert result == expected


def test_parse_paderborn_filename_returns_native_types():
    """measurement_index est un int natif (pas une str issue du regex)."""
    result = parse_paderborn_filename("N15_M07_F10_K001_5.mat")
    assert isinstance(result["measurement_index"], int)
    assert isinstance(result["condition"], str)
    assert isinstance(result["code"], str)


# ---------- parse_paderborn_filename : cas invalides ----------

@pytest.mark.parametrize("bad_filename", [
    # Pas d'extension
    "N15_M07_F10_K001_1",
    # Mauvaise extension
    "N15_M07_F10_K001_1.txt",
    "N15_M07_F10_K001_1.csv",
    "N15_M07_F10_K001_1.parquet",
    # Manque le code roulement
    "N15_M07_F10_1.mat",
    # Manque l'index
    "N15_M07_F10_K001.mat",
    # Manque la condition
    "K001_1.mat",
    # Code lowercase (mauvais case)
    "N15_M07_F10_k001_1.mat",
    # Index non numerique
    "N15_M07_F10_K001_X.mat",
    "N15_M07_F10_K001_1a.mat",
    # Trop de segments
    "N15_M07_F10_K001_1_extra.mat",
    "N15_M07_F10_K001_1_2.mat",
    # Pas de soulignements entre segments
    "N15M07F10K001_1.mat",
    # Code avec caractere invalide
    "N15_M07_F10_K-01_1.mat",
    # Vide
    "",
    # Que des underscores
    "____.mat",
])
def test_parse_paderborn_filename_invalid_raises(bad_filename):
    """Tout nom de fichier qui ne matche pas le pattern strict leve ValueError,
    jamais de fallback silencieux."""
    with pytest.raises(ValueError, match="[Pp]aderborn"):
        parse_paderborn_filename(bad_filename)


def test_parse_paderborn_filename_error_message_includes_filename():
    """Le message d'erreur contient le nom de fichier problematique (debugging)."""
    with pytest.raises(ValueError, match=r"K001_1\.mat"):
        parse_paderborn_filename("K001_1.mat")


# ---------- Constantes exportees ----------

def test_paderborn_channels_dict_has_three_channels():
    """Les 3 canaux d'interet sont declares (vibration + 2 courants)."""
    assert set(PADERBORN_CHANNELS.keys()) == {"vibration_1", "phase_current_1", "phase_current_2"}
    assert set(PADERBORN_CHANNELS.values()) == {"vibration", "current_1", "current_2"}


def test_paderborn_sampling_rate_is_64khz():
    """Documentation du brief §3 : 64 kHz sur les 3 canaux principaux."""
    assert PADERBORN_SAMPLING_RATE_HZ == 64000.0


def test_paderborn_speed_channel_name():
    """Le canal speed est declare separement (raster different, ~4 kHz, pas 64 kHz)."""
    assert PADERBORN_SPEED_CHANNEL_NAME == "speed"


# ---------- write_measurement_parquet ----------

def test_write_measurement_parquet_basic(tmp_path):
    """Ecrit un parquet aligne sur sample_index avec 3 canaux, verifie qu'on peut le relire."""
    n = 100
    channels = {
        "vibration": np.arange(n, dtype=np.float64),
        "current_1": np.arange(n, dtype=np.float64) * 0.1,
        "current_2": np.arange(n, dtype=np.float64) * 0.2,
    }
    out = tmp_path / "test.parquet"
    write_measurement_parquet(channels, out)

    assert out.exists()
    df = pd.read_parquet(out)
    assert list(df.columns) == ["sample_index", "vibration", "current_1", "current_2"]
    assert len(df) == n
    assert df["sample_index"].iloc[0] == 0
    assert df["sample_index"].iloc[-1] == n - 1
    np.testing.assert_array_equal(df["vibration"].to_numpy(), np.arange(n))


def test_write_measurement_parquet_creates_parent_directory(tmp_path):
    """Le dossier parent est cree si besoin (cas typique : data/processed/paderborn/CODE/ inexistant)."""
    out = tmp_path / "deep" / "nested" / "path" / "test.parquet"
    n = 10
    channels = {"vibration": np.zeros(n), "current_1": np.zeros(n), "current_2": np.zeros(n)}
    write_measurement_parquet(channels, out)
    assert out.exists()


def test_write_measurement_parquet_mismatched_lengths_raises(tmp_path):
    """Si les canaux n'ont pas la meme longueur, leve ValueError (pas d'ecriture partielle)."""
    channels = {
        "vibration": np.zeros(100),
        "current_1": np.zeros(100),
        "current_2": np.zeros(50),  # longueur differente
    }
    out = tmp_path / "bad.parquet"
    with pytest.raises(ValueError, match="[Ll]ongueu"):
        write_measurement_parquet(channels, out)
    # Aucune ecriture partielle ne doit avoir eu lieu
    assert not out.exists()


def test_write_measurement_parquet_only_one_channel():
    """Cas limite : 1 seul canal (vibration). Le test verifie que le sample_index
    est bien la premiere colonne et que le format est stable."""
    n = 50
    channels = {"vibration": np.ones(n) * 42.0}
    out = Path("/tmp/test_one_channel.parquet")  # /tmp autorise pour test_isole
    try:
        write_measurement_parquet(channels, out)
        df = pd.read_parquet(out)
        assert list(df.columns) == ["sample_index", "vibration"]
        assert (df["vibration"] == 42.0).all()
    finally:
        if out.exists():
            out.unlink()


# ---------- load_paderborn_measurement (test d'integration) ----------

@pytest.mark.integration
def test_load_paderborn_measurement_integration(tmp_path):
    """Test d'integration : necessite un vrai .mat Paderborn (gitignored, ~8 MB).
    Skip par defaut — lancer explicitement avec `pytest -m integration`
    dans un environnement ou les donnees sont disponibles.

    Note : pour ce test, voir scripts/build_dataset.py pour la structure attendue.
    Le canal speed est retourne separement (raster different) et n'est pas fusionne
    dans le dict des canaux principaux.
    """
    mat = (
        Path(__file__).resolve().parents[1]
        / "data" / "raw" / "paderborn" / "K001" / "N15_M07_F10_K001_1.mat"
    )
    if not mat.exists():
        pytest.skip("Test d'integration : necessite un .mat Paderborn reel (download_paderborn.sh)")
    channels, acquired_at, speed = load_paderborn_measurement(mat)
    assert set(channels) == {"vibration", "current_1", "current_2"}
    n = {len(v) for v in channels.values()}
    assert len(n) == 1 and n.pop() > 200_000  # 4 s a 64 kHz
    assert all(np.isfinite(v).all() for v in channels.values())
    assert acquired_at.year >= 2014
    assert speed is not None and 1000 < float(np.median(speed)) < 2000  # N15 = 1500 tr/min
