"""Schema relationnel : machine -> test_session -> asset -> signal.

`asset` est l'entite physique testee (roulement, pompe, compresseur...) et
l'unite de split train/test (jamais au niveau `signal`, voir docs/brief_projet.md piege
methodologique #1). Les specificites par type d'equipement vivent dans des
tables d'extension (ex. `bearing_attributes`) plutot que des colonnes nulles
sur `asset` - un roulement a une geometrie et une localisation de defaut,
une pompe non.

Les tableaux de signal brut et de features restent en parquet
(data/processed/) ; cette base ne stocke que les metadonnees et les chemins
vers ces fichiers.
"""

import os

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship


class Base(DeclarativeBase):
    pass


class ApplicationType(Base):
    """Taxonomie ISO 20816-3 (voir configs/application_types.yaml) : type
    d'application (pompe, moteur, compresseur...) pour la classification et
    l'interpretation normative (zones A/B/C/D)."""

    __tablename__ = "application_type"

    code = Column(String, primary_key=True)  # ex. "centrifugal_pump"
    label = Column(String, nullable=False)
    iso_reference = Column(String)
    description = Column(String)

    machines = relationship("Machine", back_populates="application_type")


class Site(Base):
    """Site/usine physique - niveau racine pour un utilisateur qui modelise sa
    propre installation (par opposition aux bancs d'essai de laboratoire des
    datasets publics, qui n'appartiennent a aucun site - site_id NULL sur
    `machine` pour ceux-la, c'est la distinction naturelle, pas un flag dedie)."""

    __tablename__ = "site"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    description = Column(String)

    zones = relationship("Zone", back_populates="site")
    machines = relationship("Machine", back_populates="site")


class Zone(Base):
    """Zone/pole au sein d'un site (ex. 'Ligne conditionnement', 'Salle des
    machines') - optionnel, un site peut avoir des machines directement
    rattachees sans zone intermediaire."""

    __tablename__ = "zone"

    id = Column(String, primary_key=True)
    site_id = Column(String, ForeignKey("site.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)

    site = relationship("Site", back_populates="zones")
    machines = relationship("Machine", back_populates="zone")


class Machine(Base):
    __tablename__ = "machine"

    id = Column(String, primary_key=True)  # ex. "paderborn_kat_rig"
    source = Column(String, nullable=False)  # ex. "paderborn" | "user_defined"
    application_type_code = Column(String, ForeignKey("application_type.code"))
    site_id = Column(String, ForeignKey("site.id"))  # NULL pour les bancs d'essai labo
    zone_id = Column(String, ForeignKey("zone.id"))  # NULL si pas de zone intermediaire
    name = Column(String, nullable=False)
    description = Column(String)
    citation = Column(String)

    application_type = relationship("ApplicationType", back_populates="machines")
    site = relationship("Site", back_populates="machines")
    zone = relationship("Zone", back_populates="machines")
    sessions = relationship("TestSession", back_populates="machine")
    assets = relationship("Asset", back_populates="machine")


class TestSession(Base):
    """Une condition de fonctionnement mesuree sur une machine (vitesse, charge...)."""

    __tablename__ = "test_session"

    id = Column(String, primary_key=True)  # ex. "paderborn_kat_rig::N15_M07_F10"
    machine_id = Column(String, ForeignKey("machine.id"), nullable=False)
    label = Column(String, nullable=False)  # ex. "N15_M07_F10"
    rotational_speed_rpm = Column(Float)
    load_torque_nm = Column(Float)
    radial_force_n = Column(Float)

    machine = relationship("Machine", back_populates="sessions")
    signals = relationship("Signal", back_populates="test_session")


class BearingGeometry(Base):
    __tablename__ = "bearing_geometry"

    model = Column(String, primary_key=True)  # ex. "6203"
    n_balls = Column(Integer)
    ball_diameter_mm = Column(Float)
    pitch_diameter_mm = Column(Float)
    contact_angle_deg = Column(Float)
    citation = Column(String)

    bearing_attributes = relationship("BearingAttributes", back_populates="geometry")


class Asset(Base):
    """Entite physique testee (roulement, pompe, compresseur...). Unite de split train/test."""

    __tablename__ = "asset"

    id = Column(String, primary_key=True)  # ex. "paderborn_kat_rig::KA01"
    machine_id = Column(String, ForeignKey("machine.id"), nullable=False)
    asset_type = Column(String, nullable=False)  # bearing | pump | compressor | valve | ...
    code = Column(String, nullable=False)  # ex. "KA01", "APU_compressor_1"
    # healthy | faulty | degraded (verite terrain connue, datasets de recherche)
    # unknown (asset reel cree via le factory-builder, aucun diagnostic encore
    # etabli - ne JAMAIS mettre healthy/faulty par defaut ici, ce serait une
    # verite terrain inventee, voir regle "0 mock")
    health_state = Column(String, nullable=False)

    machine = relationship("Machine", back_populates="assets")
    signals = relationship("Signal", back_populates="asset")
    bearing_attributes = relationship(
        "BearingAttributes", back_populates="asset", uselist=False
    )


class BearingAttributes(Base):
    """Extension de Asset pour asset_type == 'bearing' (pattern table-par-type)."""

    __tablename__ = "bearing_attributes"

    asset_id = Column(String, ForeignKey("asset.id"), primary_key=True)
    geometry_model = Column(String, ForeignKey("bearing_geometry.model"))
    defect_origin = Column(String)  # na | artificial | real
    defect_location = Column(String)  # none | inner | outer | ball | both
    defect_method = Column(String)

    asset = relationship("Asset", back_populates="bearing_attributes")
    geometry = relationship("BearingGeometry", back_populates="bearing_attributes")


class Signal(Base):
    """Un enregistrement individuel (une mesure, un canal).

    asset_id et test_session_id doivent reference la MEME machine : la FK seule
    ne le garantit pas (deux chemins de jointure independants), voir add_signal()
    qui verifie l'invariant a l'insertion.
    """

    __tablename__ = "signal"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "test_session_id", "channel", "measurement_index",
            name="uq_signal_identity",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(String, ForeignKey("asset.id"), nullable=False)
    test_session_id = Column(String, ForeignKey("test_session.id"), nullable=False)
    # vibration | current_1 | current_2 | pressure | temperature | flow | ...
    channel = Column(String, nullable=False)
    measurement_index = Column(Integer)  # ex. 1..20 pour Paderborn
    sampling_rate_hz = Column(Float, nullable=False)
    duration_s = Column(Float)
    n_samples = Column(Integer)
    file_path = Column(String, nullable=False)  # chemin vers le parquet du signal
    is_sanity_check_only = Column(Boolean, default=False)  # CWRU notamment
    unit = Column(String)  # unite canonique de la valeur brute (voir src/data/units.py)
    unit_confidence = Column(String)  # confirmed | inferred | unknown

    asset = relationship("Asset", back_populates="signals")
    test_session = relationship("TestSession", back_populates="signals")


class Feature(Base):
    """Feature calculee, format long (EAV) : un nouveau capteur/feature = des lignes,
    jamais une migration de schema. Table candidate a l'hypertable Timescale
    (partitionnee sur `timestamp`), voir make_feature_hypertable().

    Volontairement PAS de FK stricte vers signal/test_session pour rester valide
    y compris pour des sources en flux continu sans notion de mesure figee - la
    tracabilite se fait via asset_id + channel + timestamp.
    """

    __tablename__ = "feature"

    # PK composite (id, timestamp) : Timescale exige que toute cle unique/primaire
    # inclue la colonne de partitionnement temporel.
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, primary_key=True, nullable=False)
    asset_id = Column(String, ForeignKey("asset.id"), nullable=False)
    signal_id = Column(Integer, ForeignKey("signal.id"))  # tracabilite optionnelle
    channel = Column(String, nullable=False)  # vibration | pressure | temperature | ...
    feature_name = Column(String, nullable=False)  # rms | kurtosis | bpfo_energy | ...
    value = Column(Float, nullable=False)
    unit = Column(String)  # unite canonique de `value` (voir src/data/units.py) - null pour les
    # features sans dimension physique (kurtosis, skewness, crest_factor : ratios sans unite)

    asset = relationship("Asset")
    signal = relationship("Signal")


class MaintenanceEvent(Base):
    """Journal d'evenements sur un asset (defaut signale, remplacement de
    roulement, remplacement/deplacement de capteur, modification systeme...),
    horodate pour correlation avec la derive des features dans le temps.

    Table relationnelle classique, PAS une hypertable : le volume attendu est
    faible et epars (quelques evenements par asset sur sa vie entiere), a
    l'oppose de `feature` (haute frequence, un hypertable a du sens la-bas
    mais serait une sur-ingenierie ici).
    """

    __tablename__ = "maintenance_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(String, ForeignKey("asset.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    # fault_detected | bearing_replacement | sensor_replacement |
    # sensor_relocation | system_modification | other
    event_type = Column(String, nullable=False)
    description = Column(String)
    reported_by = Column(String)

    asset = relationship("Asset")


def make_feature_hypertable(engine) -> bool:
    """Convertit `feature` en hypertable Timescale (idempotent). A appeler apres init_db().

    Si l'extension timescaledb n'est pas installee sur le serveur (PostgreSQL
    natif, ex. poste Windows sans Docker), `feature` reste une table classique :
    le schema est identique, seul le partitionnement temporel manque. Retourne
    True si l'hypertable est active, False sinon (avertissement explicite).
    """
    with engine.connect() as conn:
        available = conn.execute(
            text("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
        ).first()
        if available is None:
            print(
                "[warn] extension timescaledb absente : `feature` reste une table "
                "PostgreSQL classique (pas d'hypertable)."
            )
            return False
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))
        conn.execute(
            text(
                "SELECT create_hypertable('feature', by_range('timestamp'), "
                "if_not_exists => TRUE);"
            )
        )
        conn.commit()
    return True


def add_machine(session: Session, machine_id: str, zone: Zone | None = None, **kwargs) -> Machine:
    """Insere une Machine en verifiant que zone (si fournie) et site (si fourni
    dans kwargs) sont coherents - meme pattern que add_signal()."""
    site_id = kwargs.pop("site_id", None)
    if zone is not None:
        if site_id is not None and zone.site_id != site_id:
            raise ValueError(
                f"zone {zone.id!r} (site={zone.site_id!r}) et site_id={site_id!r} "
                "fourni ne correspondent pas."
            )
        site_id = zone.site_id
    machine = Machine(id=machine_id, zone_id=zone.id if zone else None, site_id=site_id, **kwargs)
    session.add(machine)
    return machine


def add_signal(session: Session, asset: Asset, test_session: TestSession, **kwargs) -> Signal:
    """Insere un Signal en verifiant que asset et test_session partagent la meme machine."""
    if asset.machine_id != test_session.machine_id:
        raise ValueError(
            f"asset {asset.id!r} (machine={asset.machine_id!r}) et "
            f"test_session {test_session.id!r} (machine={test_session.machine_id!r}) "
            "n'appartiennent pas a la meme machine."
        )
    signal = Signal(asset_id=asset.id, test_session_id=test_session.id, **kwargs)
    session.add(signal)
    return signal


def get_engine(database_url: str | None = None):
    """Cree l'engine SQLAlchemy depuis DATABASE_URL (ou l'argument fourni)."""
    url = database_url or os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://vibration:vibration@localhost:5432/vibration",
    )
    return create_engine(url)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def get_session(engine) -> Session:
    return Session(engine)
