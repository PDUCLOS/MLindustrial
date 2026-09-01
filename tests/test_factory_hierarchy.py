"""Tests du niveau site/zone (recreation d'usine utilisateur) - invariants
purement structurels, pas besoin de DB reelle (verifie sur des objets Python
non persistes, comme deja fait pour add_signal via des mocks legers)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.db import Site, Zone, add_machine


def test_add_machine_without_zone_or_site():
    session_calls = []

    class FakeSession:
        def add(self, obj):
            session_calls.append(obj)

    m = add_machine(FakeSession(), "m1", name="Machine test")
    assert m.zone_id is None
    assert m.site_id is None
    assert session_calls == [m]


def test_add_machine_with_zone_derives_site():
    class FakeSession:
        def add(self, obj):
            pass

    zone = Zone(id="z1", site_id="s1", name="Zone test")
    m = add_machine(FakeSession(), "m1", zone=zone, name="Machine test")
    assert m.zone_id == "z1"
    assert m.site_id == "s1"


def test_add_machine_rejects_mismatched_site_and_zone():
    class FakeSession:
        def add(self, obj):
            pass

    zone = Zone(id="z1", site_id="s1", name="Zone test")
    with pytest.raises(ValueError):
        add_machine(FakeSession(), "m1", zone=zone, site_id="s2", name="Machine test")


def test_add_machine_accepts_consistent_site_and_zone():
    class FakeSession:
        def add(self, obj):
            pass

    zone = Zone(id="z1", site_id="s1", name="Zone test")
    m = add_machine(FakeSession(), "m1", zone=zone, site_id="s1", name="Machine test")
    assert m.site_id == "s1"
    assert m.zone_id == "z1"


def test_site_and_zone_construct_without_error():
    site = Site(id="s1", name="Usine test")
    zone = Zone(id="z1", site_id=site.id, name="Zone test")
    assert zone.site_id == site.id
