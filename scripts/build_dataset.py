"""Pipeline Paderborn complet : .mat -> parquet + DB (signal + feature).

Usage :
    uv run python scripts/build_dataset.py                       # tout (32 roulements)
    uv run python scripts/build_dataset.py --codes K001 KA01      # sous-ensemble
    uv run python scripts/build_dataset.py --limit-per-bearing 4  # smoke test rapide
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.db import Feature, add_signal, get_engine, get_session
from src.data.loaders import (
    PADERBORN_SAMPLING_RATE_HZ,
    load_paderborn_measurement,
    parse_paderborn_filename,
    write_measurement_parquet,
)
from src.data.units import get_sensor_spec
from src.features.envelope import consensus_resonance_band, fault_frequency_energies
from src.features.fault_frequencies import all_fault_frequencies
from src.features.speed import speed_features
from src.features.time_domain import time_domain_features

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "paderborn"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed" / "paderborn"
MACHINE_ID = "paderborn_kat_rig"
SOURCE = "paderborn"

# features sans dimension physique (ratios) - pas d'unite, meme si le canal en a une
DIMENSIONLESS_FEATURES = {"kurtosis", "skewness", "crest_factor", "speed_cv", "is_variable_speed"}


def process_bearing(
    session, machine, asset, mat_files: list[Path], stats: dict, with_envelope: bool = False
) -> None:
    sessions_by_label = {s.label: s for s in machine.sessions}
    geometry = asset.bearing_attributes.geometry if asset.bearing_attributes else None

    # Chargement en un seul passage disque : necessaire pour calculer la bande
    # de resonance par CONSENSUS (toutes les mesures du roulement) avant de
    # calculer les features enveloppe de chaque mesure individuelle - voir
    # docs/known_issues.md ("kurtogramme instable"). Sert aussi a eviter de
    # relire chaque .mat deux fois.
    loaded = []
    for mat_path in mat_files:
        meta = parse_paderborn_filename(mat_path.name)
        test_session = sessions_by_label.get(meta["condition"])
        if test_session is None:
            print(f"  [skip] session inconnue {meta['condition']} ({mat_path.name})")
            continue
        try:
            channels, acquired_at, speed_signal = load_paderborn_measurement(mat_path)
        except Exception as e:
            print(f"  [skip] fichier illisible {mat_path.name} : {e}")
            stats.setdefault("skipped_files", []).append(str(mat_path))
            continue
        loaded.append((mat_path, meta, test_session, channels, acquired_at, speed_signal))

    # Bande de resonance CONSENSUS : une seule bande pour tout le roulement
    # (les 4 conditions/80 mesures), pas une bande par mesure individuelle.
    # Hypothese assumee : la resonance capteur/logement est une propriete
    # mecanique du montage, independante de la vitesse de rotation - grouper
    # sur les 4 conditions maximise le nombre de mesures moyennees (n=80 au
    # lieu de n=20 par condition) sans violer cette hypothese. A revoir si
    # une regression flagrante apparait entre conditions.
    resonance_band = None
    if with_envelope and geometry is not None and geometry.n_balls:
        vibration_signals = [c["vibration"] for *_, c, _, _ in loaded if "vibration" in c]
        if vibration_signals:
            consensus = consensus_resonance_band(vibration_signals, PADERBORN_SAMPLING_RATE_HZ)
            resonance_band = (consensus["low"], consensus["high"])
            best = consensus["best"]
            print(
                f"  [{asset.code}] bande resonance consensus ({consensus['n_signals']} mesures) : "
                f"{resonance_band[0]:.0f}-{resonance_band[1]:.0f} Hz "
                f"(niveau {best['level']}, kurtosis spectral moyen {best['kurt']:.2f})"
            )

    for mat_path, meta, test_session, channels, acquired_at, speed_signal in loaded:
        out_path = OUT_DIR / asset.code / f"{meta['condition']}_{meta['measurement_index']}.parquet"
        write_measurement_parquet(channels, out_path)

        rpm = test_session.rotational_speed_rpm
        fault_freqs = None
        if geometry is not None and geometry.n_balls and rpm:
            fault_freqs = all_fault_frequencies(
                geometry.n_balls, rpm, geometry.ball_diameter_mm,
                geometry.pitch_diameter_mm, geometry.contact_angle_deg or 0.0,
            )

        for channel_name, arr in channels.items():
            spec = get_sensor_spec(SOURCE, channel_name)
            sig = add_signal(
                session, asset, test_session,
                channel=channel_name,
                measurement_index=meta["measurement_index"],
                sampling_rate_hz=PADERBORN_SAMPLING_RATE_HZ,
                duration_s=len(arr) / PADERBORN_SAMPLING_RATE_HZ,
                n_samples=len(arr),
                file_path=str(out_path),
                unit=spec.raw_unit if spec else None,
                unit_confidence=spec.confidence if spec else "unknown",
            )
            session.flush()  # obtenir sig.id avant d'inserer les features

            for fname, val in time_domain_features(arr).items():
                session.add(Feature(
                    asset_id=asset.id, signal_id=sig.id, channel=channel_name,
                    feature_name=fname, value=val, timestamp=acquired_at,
                    unit=None if fname in DIMENSIONLESS_FEATURES else (spec.raw_unit if spec else None),
                ))
                stats["features"] += 1

            if with_envelope and channel_name == "vibration" and fault_freqs is not None and resonance_band is not None:
                energies = fault_frequency_energies(
                    arr, PADERBORN_SAMPLING_RATE_HZ, fault_freqs, resonance_band=resonance_band
                )
                for fname, val in energies.items():
                    session.add(Feature(
                        asset_id=asset.id, signal_id=sig.id, channel=channel_name,
                        feature_name=fname, value=val, timestamp=acquired_at,
                    ))
                    stats["features"] += 1

            stats["signals"] += 1

        if speed_signal is not None:
            speed_spec = get_sensor_spec(SOURCE, "speed")
            for fname, val in speed_features(speed_signal).items():
                session.add(Feature(
                    asset_id=asset.id, signal_id=None, channel="speed",
                    feature_name=fname, value=val, timestamp=acquired_at,
                    unit=None if fname in DIMENSIONLESS_FEATURES else (speed_spec.raw_unit if speed_spec else None),
                ))
                stats["features"] += 1

        session.commit()
        stats["measurements"] += 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", nargs="*", default=None, help="Sous-ensemble de codes roulement (ex. K001 KA01)")
    parser.add_argument("--limit-per-bearing", type=int, default=None, help="Limite de mesures par roulement (smoke test)")
    parser.add_argument(
        "--with-envelope", action="store_true",
        help="Calcule les energies BPFO/BPFI/BSF/FTF (desactive par defaut, voir docs/known_issues.md)",
    )
    args = parser.parse_args()

    engine = get_engine()
    stats = {"measurements": 0, "signals": 0, "features": 0, "skipped_files": []}
    t0 = time.time()

    with get_session(engine) as session:
        from src.data.db import Machine
        machine = session.get(Machine, MACHINE_ID)
        assets_by_code = {a.code: a for a in machine.assets if a.asset_type == "bearing"}

        codes = args.codes or sorted(assets_by_code.keys())
        for code in codes:
            if code not in assets_by_code:
                print(f"[skip] code inconnu en DB : {code}")
                continue
            asset = assets_by_code[code]
            bearing_dir = RAW_DIR / code
            mat_files = sorted(bearing_dir.glob("*.mat"))
            if args.limit_per_bearing:
                mat_files = mat_files[: args.limit_per_bearing]
            print(f"[{code}] {len(mat_files)} mesures")
            process_bearing(session, machine, asset, mat_files, stats, with_envelope=args.with_envelope)

    elapsed = time.time() - t0
    print(
        f"Termine en {elapsed:.1f}s - {stats['measurements']} mesures, "
        f"{stats['signals']} signaux, {stats['features']} features, "
        f"{len(stats['skipped_files'])} fichiers ignores (illisibles)."
    )
    for f in stats["skipped_files"]:
        print(f"  ignore : {f}")


if __name__ == "__main__":
    main()
