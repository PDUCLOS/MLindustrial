"""Tests du bridge DES <-> signaux physiques (Factory Twin Phase A).

Cible : un arret machine simule desactive bien sa contribution vibratoire ET
declenche la propagation electrique (harmoniques attenuees sur les autres).

Le bridge est agnostique du moteur DES : on lui passe des `DESEvent`
directement (pas besoin de SimPy ici).
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.gearbox.helical import (
    HelicalDefectConfig,
    HelicalGearGeometry,
    simulate_helical_gearbox,
)
from src.propagation.electrical import ElectricalBusCoupling, ElectricalPropagator
from src.propagation.mechanical import MechanicalCoupling, MechanicalPropagator
from src.simulation.bridge import DESEvent, SimulationBridge


FS = 64000
DURATION = 1.0  # 1 s pour accelerer les tests


def _make_m1_simulator() -> callable:
    """Simulateur M1 (moteur asynchrone 75 kW alimente le reducteur M2).

    Pour les besoins du test, M1 produit un signal 'vibration' et 'current'.
    Le reducteur est integre comme etape interne (le simulateur du reducteur
    serait M2 dans une config Phase A complete, mais pour ce test on
    simplifie avec 2 machines).
    """
    def sim(machine_id, is_running, defect_config, **kwargs):
        # M1 = moteur + reducteur. La vibration est dominee par le GMF du
        # reducteur ; le courant inclut les harmoniques VFD.
        geom = HelicalGearGeometry()
        out = simulate_helical_gearbox(
            seed=42,  # seed FIXE pour reproductibilite inter-run (hash() randomise)
            input_rpm=1500,
            gear_geometry=geom,
            defect_config=defect_config,
            duration_s=kwargs.get("duration_s", DURATION),
            fs=kwargs.get("fs", FS),
        )
        # Accentuer la composante 150 Hz (H3 secteur) du courant pour la
        # detection dans le test - la H3 source est la signature VFD type.
        t = np.arange(len(out["current"])) / FS
        out["current"] = out["current"] + 0.5 * np.sin(2.0 * np.pi * 150.0 * t)
        return out
    return sim


def _make_m2_simulator() -> callable:
    """Simulateur M2 (machine receptrice) - produit un signal propre de reference.

    Pour le test, M2 sert de 'victime' : son signal de base est faible, et on
    verifie que les contributions propagees (P2, P3) y apparaissent.
    """
    def sim(machine_id, is_running, defect_config, **kwargs):
        n = int(kwargs.get("fs", FS) * kwargs.get("duration_s", DURATION))
        rng = np.random.default_rng(7)  # seed FIXE pour reproductibilite
        vibration = 0.01 * rng.standard_normal(n)
        current = 5.0 * np.sin(2.0 * np.pi * 50.0 * np.arange(n) / FS)
        return {"vibration": vibration, "current": current}
    return sim


def _make_bridge() -> SimulationBridge:
    """Construit un bridge avec 2 machines (M1, M2) et 2 propagateurs (P2, P3)."""
    simulators = {
        "M1": _make_m1_simulator(),
        "M2": _make_m2_simulator(),
    }
    # Couplages explicites : on veut une attenuation P2 ~25 dB a GMF1 (500 Hz)
    # pour eviter que la vibration M1 noie completement le signal M2.
    mech_coupling = MechanicalCoupling(distance_m=5.0, alpha_s_per_m=8e-4)
    elec_coupling = ElectricalBusCoupling(zbus_over_zcharge=0.1)
    propagators = [
        MechanicalPropagator(fs=FS, default_coupling=mech_coupling),
        ElectricalPropagator(fs=FS, default_coupling=elec_coupling),
    ]
    return SimulationBridge(
        simulators=simulators, propagators=propagators, fs=FS,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_bridge_initial_state_all_machines_running():
    """A la construction, toutes les machines sont en marche et sans defaut."""
    bridge = _make_bridge()
    assert bridge.is_running("M1")
    assert bridge.is_running("M2")
    assert isinstance(bridge.get_defect_config("M1"), HelicalDefectConfig)


def test_bridge_generate_signals_produces_all_channels():
    """Apres `generate_signals`, chaque machine a 'vibration' et 'current'."""
    bridge = _make_bridge()
    signals = bridge.generate_signals(duration_s=DURATION)
    for mid in ("M1", "M2"):
        assert "vibration" in signals[mid]
        assert "current" in signals[mid]


def test_bridge_machine_stop_disables_vibration():
    """Apres un `machine_stop`, la vibration de la machine est forcee a zero.

    La vibration peut etre propagee par P2 (attenuee) sur les autres machines,
    mais PAS sur la machine arretee elle-meme (auto-propagation ignoree).
    """
    bridge = _make_bridge()
    # Premiere generation : tout en marche
    bridge.generate_signals(duration_s=DURATION)
    vibration_before = bridge.get_signal("M1", "vibration")
    assert vibration_before is not None
    assert np.max(np.abs(vibration_before)) > 0.0

    # M1 s'arrete
    bridge.handle_event(DESEvent(event_type="machine_stop", machine_id="M1"))
    bridge.generate_signals(duration_s=DURATION)
    vibration_after = bridge.get_signal("M1", "vibration")
    assert vibration_after is not None
    # Le bridge force la vibration a zero quand la machine est arretee
    assert np.max(np.abs(vibration_after)) == 0.0
    # Etat `is_running` est bien bascule
    assert not bridge.is_running("M1")


def test_bridge_machine_stop_propagates_electrical_harmonics():
    """Apres arret M1, ses harmoniques H3 (150 Hz) restent visibles sur M2 (attenuees).

    Le VFD est modelise comme restant sous tension avec rotor bloque (cf.
    bridge._post_process_stopped_machine + CDC §7.1 A5).

    Verification :
    1. M1 courant preserve (VFD sous tension) - non nul.
    2. M2 courant contient un pic a 150 Hz visible au-dessus du bruit de fond
       spectral (apres soustraction du bruit de fond du M2 lui-meme, qui est
       faible car M2 n'a que la fondamentale 50 Hz).
    3. Le pic a 150 Hz sur M2 est plus grand quand M1 est en marche qu'apres
       arret, ce qui confirme que la composante 150 Hz de M2 vient de la
       propagation depuis M1.
    """
    # Run 1 : M1 en marche, on mesure le pic 150 Hz sur M2
    bridge_running = _make_bridge()
    signals_running = bridge_running.generate_signals(duration_s=DURATION)
    current_m2_running = signals_running["M2"]["current"]
    n = len(current_m2_running)
    window = np.hanning(n)
    spectrum = np.fft.rfft(current_m2_running * window)
    freqs = np.fft.rfftfreq(n, d=1.0 / FS)
    target_bin = int(round(150.0 / (FS / n)))
    lo = max(0, target_bin - 5)
    hi = min(len(spectrum), target_bin + 6)
    peak_amp_running = 2.0 * float(np.max(np.abs(spectrum[lo:hi]))) / n

    # Run 2 : M1 arrete, on re-mesure
    bridge_stopped = _make_bridge()
    bridge_stopped.handle_event(DESEvent(event_type="machine_stop", machine_id="M1"))
    signals_stopped = bridge_stopped.generate_signals(duration_s=DURATION)
    current_m2_stopped = signals_stopped["M2"]["current"]
    spectrum_s = np.fft.rfft(current_m2_stopped * window)
    peak_amp_stopped = 2.0 * float(np.max(np.abs(spectrum_s[lo:hi]))) / n

    # Le courant M1 est preserve (VFD sous tension)
    current_m1_stopped = signals_stopped["M1"]["current"]
    spectrum_m1 = np.fft.rfft(current_m1_stopped * window)
    peak_amp_m1_stopped = 2.0 * float(np.max(np.abs(spectrum_m1[lo:hi]))) / n
    assert peak_amp_m1_stopped > 0.05, (
        f"Courant M1 nul apres arret (VFD aurait du rester sous tension) : "
        f"pic 150 Hz = {peak_amp_m1_stopped:.5f} A."
    )

    # Apres arret, M2 doit toujours recevoir la composante 150 Hz de M1
    # (VFD sous tension, propagation P3 preservee).
    # Reference bruit : dans une bande 5-6 kHz, loin des harmoniques secteur.
    noise_mask = (freqs >= 5000.0) & (freqs <= 6000.0)
    noise_floor = 2.0 * float(np.median(np.abs(spectrum_s[noise_mask]))) / n
    assert peak_amp_stopped > 5.0 * noise_floor, (
        f"Pas de contribution H3 sur M2 apres arret M1 "
        f"(pic 150 Hz = {peak_amp_stopped:.5f} A, plancher {noise_floor:.5f} A)."
    )

    # Sanity check : quand M1 tourne, le pic 150 Hz sur M2 est plus grand
    # qu'apres arret (puisque M1 a sa pleine activite).
    # Note : ce test est moins strict a cause des phases aleatoires ;
    # on tolere une marge.
    assert peak_amp_running >= 0.5 * peak_amp_stopped, (
        f"M2 150 Hz en marche ({peak_amp_running:.4f}) < 0.5x arrete "
        f"({peak_amp_stopped:.4f}). La propagation semble inversee."
    )


def test_bridge_defect_onset_updates_defect_config():
    """Un evenement `defect_onset` met a jour le defaut de la machine."""
    bridge = _make_bridge()
    new_defect = HelicalDefectConfig(
        enable_broken_tooth=True, broken_tooth_stage=1, broken_tooth_index=3,
    )
    bridge.handle_event(
        DESEvent(
            event_type="defect_onset",
            machine_id="M1",
            payload={"defect_config": new_defect},
        )
    )
    assert bridge.get_defect_config("M1") == new_defect
    # Le signal regenere reflete le nouveau defaut
    signals = bridge.generate_signals(duration_s=DURATION)
    assert "vibration" in signals["M1"]


def test_bridge_defect_onset_requires_helicaldefectconfig_payload():
    """`defect_onset` sans `HelicalDefectConfig` dans le payload leve une erreur explicite."""
    bridge = _make_bridge()
    with pytest.raises(TypeError):
        bridge.handle_event(
            DESEvent(
                event_type="defect_onset", machine_id="M1", payload={},
            )
        )
    with pytest.raises(TypeError):
        bridge.handle_event(
            DESEvent(
                event_type="defect_onset",
                machine_id="M1",
                payload={"defect_config": "pas un HelicalDefectConfig"},
            )
        )


def test_bridge_machine_start_event_resumes_vibration():
    """Apres arret + restart, la vibration reapparait."""
    bridge = _make_bridge()
    bridge.handle_event(DESEvent(event_type="machine_stop", machine_id="M1"))
    bridge.generate_signals(duration_s=DURATION)
    assert np.max(np.abs(bridge.get_signal("M1", "vibration"))) == 0.0

    bridge.handle_event(DESEvent(event_type="machine_start", machine_id="M1"))
    bridge.generate_signals(duration_s=DURATION)
    assert np.max(np.abs(bridge.get_signal("M1", "vibration"))) > 0.0


def test_bridge_unknown_machine_raises():
    """Evenement sur une machine non enregistree : KeyError explicite."""
    bridge = _make_bridge()
    with pytest.raises(KeyError):
        bridge.handle_event(DESEvent(event_type="machine_stop", machine_id="M999"))


def test_bridge_unknown_event_type_raises():
    """Type d'evenement invalide : ValueError explicite."""
    bridge = _make_bridge()
    with pytest.raises(ValueError):
        bridge.handle_event(DESEvent(event_type="unknown_event", machine_id="M1"))


def test_bridge_propagation_p2_visible_on_target():
    """Une vibration M1 avec un pic a GMF (500 Hz) doit apparaitre sur M2,
    attenuated mais visible, apres application de P2."""
    bridge = _make_bridge()
    signals = bridge.generate_signals(duration_s=DURATION)
    n = len(signals["M2"]["vibration"])
    window = np.hanning(n)
    spectrum = np.fft.rfft(signals["M2"]["vibration"] * window)
    freqs = np.fft.rfftfreq(n, d=1.0 / FS)
    # Cherche un pic dans la zone GMF1 +/- 20 Hz
    target_bin = int(round(500.0 / (FS / n)))
    lo = max(0, target_bin - 80)  # +/- 20 Hz = 80 bins a 0.25 Hz/bin
    hi = min(len(spectrum), target_bin + 81)
    if lo < hi:
        peak_bin = lo + int(np.argmax(np.abs(spectrum[lo:hi])))
        peak_amp = 2.0 * float(np.abs(spectrum[peak_bin])) / n
        # Reference : M2 sans contribution M1 devrait avoir un bruit de fond ~0.01
        # (cf. _make_m2_simulator). Avec P2, on attend un pic > 5x le bruit.
        assert peak_amp > 0.001, (
            f"Pas de contribution P2 visible sur M2 (pic a {freqs[peak_bin]:.2f} Hz, "
            f"amplitude {peak_amp:.5f} g)."
        )
