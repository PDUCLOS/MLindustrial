"""Cree les tables et seed machines/sessions/geometries/roulements depuis configs/*.yaml.

Usage : uv run python scripts/init_db.py
"""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.db import (
    ApplicationType,
    Asset,
    BearingAttributes,
    BearingGeometry,
    Machine,
    TestSession,
    get_engine,
    get_session,
    init_db,
    make_feature_hypertable,
)

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name) as f:
        return yaml.safe_load(f)


def seed(session) -> None:
    machines_cfg = load_yaml("machines.yaml")["machines"]
    geometries_cfg = load_yaml("bearing_geometry.yaml")["geometries"]
    paderborn_bearings_cfg = load_yaml("paderborn_bearings.yaml")
    application_types_cfg = load_yaml("application_types.yaml")["application_types"]

    for at in application_types_cfg:
        session.merge(
            ApplicationType(
                code=at["code"],
                label=at["label"],
                iso_reference=at.get("iso_reference"),
                description=at.get("description"),
            )
        )

    for model, geo in geometries_cfg.items():
        session.merge(
            BearingGeometry(
                model=model,
                n_balls=geo.get("n_balls"),
                ball_diameter_mm=geo.get("ball_diameter_mm"),
                pitch_diameter_mm=geo.get("pitch_diameter_mm"),
                contact_angle_deg=geo.get("contact_angle_deg"),
                citation=geo.get("citation"),
            )
        )

    for m in machines_cfg:
        session.merge(
            Machine(
                id=m["id"],
                source=m["source"],
                application_type_code=m.get("application_type"),
                name=m["name"],
                description=m.get("description"),
                citation=m.get("citation"),
            )
        )
        for s in m.get("sessions", []):
            session.merge(
                TestSession(
                    id=f"{m['id']}::{s['id']}",
                    machine_id=m["id"],
                    label=s["id"],
                    rotational_speed_rpm=s.get("rotational_speed_rpm"),
                    load_torque_nm=s.get("load_torque_nm"),
                    radial_force_n=s.get("radial_force_n"),
                )
            )

    machine_id = paderborn_bearings_cfg["machine"]
    geometry_model = "6203"
    for b in paderborn_bearings_cfg["bearings"]:
        asset_id = f"{machine_id}::{b['code']}"
        session.merge(
            Asset(
                id=asset_id,
                machine_id=machine_id,
                asset_type="bearing",
                code=b["code"],
                health_state=b["health_state"],
            )
        )
        session.merge(
            BearingAttributes(
                asset_id=asset_id,
                geometry_model=geometry_model,
                defect_origin=b.get("defect_origin"),
                defect_location=b.get("defect_location"),
                defect_method=b.get("defect_method"),
            )
        )

    session.commit()


def main() -> None:
    engine = get_engine()
    init_db(engine)
    make_feature_hypertable(engine)
    with get_session(engine) as session:
        seed(session)
    print("DB initialisee et seedee (machines, sessions, geometries, roulements Paderborn).")


if __name__ == "__main__":
    main()
