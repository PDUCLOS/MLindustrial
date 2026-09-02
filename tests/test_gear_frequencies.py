"""Valeurs verifiables a la main (meme discipline que test_fault_frequencies.py)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.fault_frequencies import all_fault_frequencies
from src.features.gear_frequencies import (
    GearStage,
    compute_gear_train,
    first_stage_input_bearing_frequencies,
    summarize_gear_train,
)


def test_single_helical_stage_matches_hand_calc():
    # 1800 tr/min = 30 Hz. Pignon 20 dents, roue 60 dents -> ratio 3:1.
    # GMF = 20 * 30 = 600 Hz. f_out = 30/3 = 10 Hz. Verifie aussi
    # GMF = driven_teeth * f_out = 60 * 10 = 600 Hz (coherence).
    stage = GearStage(reduction_type="helical", driving_teeth=20, driven_teeth=60)
    result = compute_gear_train(1800.0, [stage])
    assert len(result) == 1
    r = result[0]
    assert r.f_in_hz == pytest.approx(30.0)
    assert r.f_out_hz == pytest.approx(10.0)
    assert r.gmf_hz == pytest.approx(600.0)
    assert r.ratio == pytest.approx(3.0)
    assert r.gmf_harmonics_hz[2] == pytest.approx(1200.0)
    assert r.gmf_harmonics_hz[3] == pytest.approx(1800.0)


def test_gmf_invariant_driving_equals_driven():
    # GMF = N_menant * f_in == N_mene * f_out, pour tout type/geometrie -
    # c'est l'identite physique centrale du module (meme role que
    # BPFO+BPFI=n*fr dans fault_frequencies.py).
    stage = GearStage(reduction_type="spiral_bevel", driving_teeth=17, driven_teeth=43)
    result = compute_gear_train(1450.0, [stage])[0]
    gmf_from_driven = stage.driven_teeth * result.f_out_hz
    assert result.gmf_hz == pytest.approx(gmf_from_driven)


def test_two_stage_cascade_matches_helical_module_defaults():
    # Reproduit src/gearbox/helical.py::HelicalGearGeometry par defaut
    # (z1=20,z2=60,z3=20,z4=60 -> ratio total 9:1) a 1500 tr/min.
    stages = [
        GearStage(reduction_type="helical", driving_teeth=20, driven_teeth=60),
        GearStage(reduction_type="helical", driving_teeth=20, driven_teeth=60),
    ]
    result = compute_gear_train(1500.0, stages)
    assert len(result) == 2

    fr_input = 1500.0 / 60.0  # 25 Hz
    fr_intermediate = fr_input / 3.0  # 8.333 Hz
    fr_output = fr_intermediate / 3.0  # 2.778 Hz

    assert result[0].f_in_hz == pytest.approx(fr_input)
    assert result[0].f_out_hz == pytest.approx(fr_intermediate)
    assert result[0].gmf_hz == pytest.approx(20 * fr_input)

    # cascade automatique : l'etage 2 prend en entree la sortie de l'etage 1
    assert result[1].f_in_hz == pytest.approx(fr_intermediate)
    assert result[1].f_out_hz == pytest.approx(fr_output)
    assert result[1].gmf_hz == pytest.approx(20 * fr_intermediate)


def test_worm_gear_single_start():
    # Vis 1 filet ("single start"), roue 40 dents -> ratio 40:1 (demultiplication
    # forte, typique roue-et-vis). A 1450 tr/min (24.1667 Hz) :
    # GMF = 1 * 24.1667 = 24.1667 Hz (meme loi que les autres types).
    stage = GearStage(reduction_type="worm", driving_teeth=1, driven_teeth=40)
    result = compute_gear_train(1450.0, [stage])[0]
    assert result.ratio == pytest.approx(40.0)
    assert result.f_out_hz == pytest.approx(1450.0 / 60.0 / 40.0)
    assert result.gmf_hz == pytest.approx(1450.0 / 60.0)


def test_worm_gear_multi_start():
    # Vis 2 filets, roue 50 dents -> ratio 25:1, GMF = 2 * f_in.
    stage = GearStage(reduction_type="worm", driving_teeth=2, driven_teeth=50)
    result = compute_gear_train(3000.0, [stage])[0]
    fr_in = 3000.0 / 60.0
    assert result.ratio == pytest.approx(25.0)
    assert result.gmf_hz == pytest.approx(2 * fr_in)


def test_mixed_train_worm_then_bevel():
    # Train mixte : roue-et-vis (1er etage) puis spiro-conique (2e etage) -
    # exactement le cas d'usage vise ("essayer de le faire en automatique").
    stages = [
        GearStage(reduction_type="worm", driving_teeth=2, driven_teeth=50),  # 25:1
        GearStage(reduction_type="spiral_bevel", driving_teeth=15, driven_teeth=30),  # 2:1
    ]
    result = compute_gear_train(1450.0, stages)
    fr_in = 1450.0 / 60.0
    fr_after_worm = fr_in / 25.0
    fr_after_bevel = fr_after_worm / 2.0

    assert result[0].f_out_hz == pytest.approx(fr_after_worm)
    assert result[1].f_in_hz == pytest.approx(fr_after_worm)  # cascade
    assert result[1].f_out_hz == pytest.approx(fr_after_bevel)
    assert result[1].gmf_hz == pytest.approx(15 * fr_after_worm)


def test_unsupported_reduction_type_rejected():
    with pytest.raises(ValueError, match="non supporte"):
        GearStage(reduction_type="planetary", driving_teeth=20, driven_teeth=60)


def test_non_positive_teeth_rejected():
    with pytest.raises(ValueError, match="strictement positifs"):
        GearStage(reduction_type="helical", driving_teeth=0, driven_teeth=60)


def test_empty_stages_rejected():
    with pytest.raises(ValueError, match="Au moins un etage"):
        compute_gear_train(1500.0, [])


def test_non_positive_rpm_rejected():
    stage = GearStage(reduction_type="helical", driving_teeth=20, driven_teeth=60)
    with pytest.raises(ValueError, match="strictement positif"):
        compute_gear_train(0.0, [stage])


def test_summarize_gear_train_total_ratio_is_product_not_sum():
    # 3:1 puis 3:1 -> total 9:1 (produit), PAS 6:1 (somme) - reproduit
    # exactement src/gearbox/helical.py::HelicalGearGeometry.reduction_ratio
    # par defaut (9:1) pour rester coherent avec le simulateur Factory Twin.
    stages = [
        GearStage(reduction_type="helical", driving_teeth=20, driven_teeth=60),
        GearStage(reduction_type="helical", driving_teeth=20, driven_teeth=60),
    ]
    report = summarize_gear_train(1500.0, stages)
    assert report.total_ratio == pytest.approx(9.0)
    assert report.n_stages == 2
    assert report.output_rpm == pytest.approx(1500.0 / 9.0)
    assert report.input_rpm == pytest.approx(1500.0)


def test_summarize_gear_train_output_rpm_matches_stage_cascade():
    # La sortie du rapport global doit correspondre EXACTEMENT a la sortie
    # du dernier etage calcule par compute_gear_train (pas un calcul
    # independant qui pourrait diverger).
    stages = [
        GearStage(reduction_type="worm", driving_teeth=2, driven_teeth=50),
        GearStage(reduction_type="spiral_bevel", driving_teeth=15, driven_teeth=30),
    ]
    report = summarize_gear_train(1450.0, stages)
    last_stage_f_out_rpm = report.stages[-1].f_out_hz * 60.0
    assert report.output_rpm == pytest.approx(last_stage_f_out_rpm)


def test_summarize_gear_train_all_gmf_hz_view():
    stages = [
        GearStage(reduction_type="helical", driving_teeth=20, driven_teeth=60),
        GearStage(reduction_type="helical", driving_teeth=20, driven_teeth=60),
    ]
    report = summarize_gear_train(1500.0, stages)
    gmf_view = report.all_gmf_hz
    assert set(gmf_view.keys()) == {1, 2}
    assert gmf_view[1] == pytest.approx(report.stages[0].gmf_hz)
    assert gmf_view[2] == pytest.approx(report.stages[1].gmf_hz)


def test_first_stage_bearing_frequencies_delegates_to_fault_frequencies():
    # Doit etre un simple passe-plat vers all_fault_frequencies - aucune
    # formule dupliquee (le roulement d'entree du reducteur suit exactement
    # la meme physique qu'un roulement Paderborn).
    expected = all_fault_frequencies(8, 1450.0, 6.75, 29.05, 0.0)
    actual = first_stage_input_bearing_frequencies(1450.0, 8, 6.75, 29.05, 0.0)
    assert actual == expected
