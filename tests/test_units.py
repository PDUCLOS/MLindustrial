import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.units import (
    CANONICAL_UNITS,
    SensorSpec,
    canonical_unit_for,
    get_sensor_spec,
    to_canonical,
)


def test_get_sensor_spec_known_paderborn_vibration():
    spec = get_sensor_spec("paderborn", "vibration")
    assert spec is not None
    assert spec.quantity == "vibration_acceleration"
    assert spec.raw_unit == "g"


def test_get_sensor_spec_unknown_returns_none():
    assert get_sensor_spec("unknown_source", "unknown_channel") is None


def test_to_canonical_identity_scale():
    spec = SensorSpec(quantity="current", raw_unit="A", scale_to_canonical=1.0)
    assert to_canonical(5.0, spec) == pytest.approx(5.0)


def test_to_canonical_applies_scale_and_offset():
    spec = SensorSpec(quantity="temperature", raw_unit="degF", scale_to_canonical=5 / 9, offset_to_canonical=-32 * 5 / 9)
    assert to_canonical(32.0, spec) == pytest.approx(0.0, abs=1e-9)  # 32F = 0C
    assert to_canonical(212.0, spec) == pytest.approx(100.0, abs=1e-9)  # 212F = 100C


def test_canonical_unit_for_known_quantity():
    assert canonical_unit_for("vibration_acceleration") == "g"
    assert canonical_unit_for("current") == "A"


def test_canonical_unit_for_unknown_raises():
    with pytest.raises(ValueError):
        canonical_unit_for("not_a_real_quantity")


def test_every_registry_entry_quantity_is_canonical():
    from src.data.units import SENSOR_REGISTRY

    for (source, channel), spec in SENSOR_REGISTRY.items():
        assert spec.quantity in CANONICAL_UNITS, f"{source}/{channel} : quantity {spec.quantity!r} non enregistree"
