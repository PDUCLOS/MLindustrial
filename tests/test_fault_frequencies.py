"""Valeurs verifiables a la main (voir docs/brief_projet.md section 6)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.fault_frequencies import (
    all_fault_frequencies,
    bpfi,
    bpfo,
    bsf,
    ftf,
    mains_separation_hz,
    rotational_frequency_hz,
)

# Geometrie "ronde" choisie pour verification manuelle simple (pas un roulement reel) :
# n=8 billes, d/D=0.2, phi=0 -> d/D*cos(phi)=0.2
N_BALLS = 8
D_MM = 5.0
BIG_D_MM = 25.0
PHI_DEG = 0.0
FR_HZ = 10.0  # 600 rpm


def test_rotational_frequency():
    assert rotational_frequency_hz(600) == pytest.approx(10.0)


def test_bpfo():
    # (8/2)*10*(1-0.2) = 4*10*0.8 = 32
    assert bpfo(N_BALLS, FR_HZ, D_MM, BIG_D_MM, PHI_DEG) == pytest.approx(32.0)


def test_bpfi():
    # (8/2)*10*(1+0.2) = 4*10*1.2 = 48
    assert bpfi(N_BALLS, FR_HZ, D_MM, BIG_D_MM, PHI_DEG) == pytest.approx(48.0)


def test_bsf():
    # (25/(2*5))*10*(1-0.2**2) = 2.5*10*0.96 = 24
    assert bsf(N_BALLS, FR_HZ, D_MM, BIG_D_MM, PHI_DEG) == pytest.approx(24.0)


def test_ftf():
    # (10/2)*(1-0.2) = 5*0.8 = 4
    assert ftf(N_BALLS, FR_HZ, D_MM, BIG_D_MM, PHI_DEG) == pytest.approx(4.0)


def test_bpfo_plus_bpfi_symmetry():
    # BPFO + BPFI = n * fr (propriete algebrique independante de la geometrie)
    o = bpfo(N_BALLS, FR_HZ, D_MM, BIG_D_MM, PHI_DEG)
    i = bpfi(N_BALLS, FR_HZ, D_MM, BIG_D_MM, PHI_DEG)
    assert o + i == pytest.approx(N_BALLS * FR_HZ)


def test_all_fault_frequencies_matches_individual_calls():
    freqs = all_fault_frequencies(N_BALLS, 600, D_MM, BIG_D_MM, PHI_DEG)
    assert freqs["BPFO"] == pytest.approx(32.0)
    assert freqs["BPFI"] == pytest.approx(48.0)
    assert freqs["BSF"] == pytest.approx(24.0)
    assert freqs["FTF"] == pytest.approx(4.0)


def test_mains_separation_zero_on_known_collision():
    # Roulement 6203 Paderborn (8 billes, d=6.75mm, D=29.05mm) a 1500 tr/min :
    # 2x la frequence de rotation (2*25=50Hz) tombe EXACTEMENT sur le secteur
    # EU - collision totale, ecart nul (voir docs/known_issues.md).
    gap = mains_separation_hz(
        n_balls=8, rpm=1500, d_mm=6.75, big_d_mm=29.05, phi_deg=0.0, mains_hz=50.0
    )
    assert gap == pytest.approx(0.0, abs=1e-9)


def test_mains_separation_positive_when_no_collision():
    gap = mains_separation_hz(
        n_balls=8, rpm=1730, d_mm=6.75, big_d_mm=29.05, phi_deg=0.0, mains_hz=50.0
    )
    assert gap > 5.0
