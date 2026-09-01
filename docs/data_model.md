# Modele de donnees

## Principe

Stockage mixte, un seul moteur (Postgres/TimescaleDB) :

- **Metadonnees relationnelles** (machine, session, asset, signal) : structure fixe, peu de lignes, integrite referentielle critique (ne pas melanger un roulement Paderborn avec une session XJTU-SY, voir `add_signal()`).
- **Features calculees** (`feature`) : format long (EAV), volumetrie potentiellement grande (des centaines de capteurs x features x fenetres temporelles), partitionnee en hypertable Timescale sur `timestamp`.
- **Signaux bruts** : jamais en base — parquet sur disque (`data/processed/`), la DB ne garde que `signal.file_path`. Un `array` 256 000 points par ligne SQL serait une erreur de modelisation, pas juste une question de performance.

Pas de moteur NoSQL/graphe (Neo4j etc.) : aucun acces de type "traversee de graphe" n'est requis pour l'instant (voir decision du 2026-08-31). A reconsiderer seulement si le projet modelise explicitement une topologie d'installation (cascade de pannes entre equipements dependants).

## Schema entite-relation

```mermaid
erDiagram
    MACHINE ||--o{ TEST_SESSION : "a pour conditions"
    MACHINE ||--o{ ASSET : "porte"
    TEST_SESSION ||--o{ SIGNAL : "mesure sous"
    ASSET ||--o{ SIGNAL : "genere"
    ASSET ||--o{ FEATURE : "genere"
    ASSET ||--o| BEARING_ATTRIBUTES : "specialise si roulement"
    BEARING_GEOMETRY ||--o{ BEARING_ATTRIBUTES : "definit geometrie"
    SIGNAL ||--o{ FEATURE : "calcule depuis"

    MACHINE {
        string id PK
        string source
        string name
        string citation
    }
    TEST_SESSION {
        string id PK
        string machine_id FK
        string label
        float rotational_speed_rpm
        float load_torque_nm
        float radial_force_n
    }
    ASSET {
        string id PK
        string machine_id FK
        string asset_type "bearing | pump | compressor..."
        string code
        string health_state "healthy | faulty | degraded"
    }
    BEARING_GEOMETRY {
        string model PK
        int n_balls
        float ball_diameter_mm
        float pitch_diameter_mm
        float contact_angle_deg
    }
    BEARING_ATTRIBUTES {
        string asset_id PK_FK
        string geometry_model FK
        string defect_origin "na | artificial | real"
        string defect_location "none | inner | outer | ball | both"
        string defect_method
    }
    SIGNAL {
        int id PK
        string asset_id FK
        string test_session_id FK
        string channel "vibration | current_1 | pressure..."
        int measurement_index
        float sampling_rate_hz
        string file_path "vers parquet"
        bool is_sanity_check_only
    }
    FEATURE {
        int id PK
        datetime timestamp PK
        string asset_id FK
        int signal_id FK
        string channel
        string feature_name "rms | kurtosis | bpfo_energy..."
        float value
    }
```

## Pourquoi `asset` generique plutot que `bearing`

Le projet doit accueillir des sources non-roulement (MetroPT-3, hydraulic systems : pression/debit/temperature sur pompes/compresseurs). Plutot que dupliquer le schema par type d'equipement, `asset` porte les attributs communs (machine, type, code, etat de sante) et une table d'extension (`bearing_attributes`) porte les attributs specifiques roulement (geometrie, localisation defaut). Un `asset_type = "pump"` n'aura simplement pas de ligne `bearing_attributes` — pattern table-par-type, pas de colonnes nulles qui s'accumulent sur `asset`.

## Pourquoi `feature` en format long (EAV) plutot que large

Une table large (une colonne par feature) impose une migration de schema a chaque nouveau capteur ou nouvelle feature. En format long, un nouveau capteur ou une nouvelle feature physique = de nouvelles lignes, jamais une ALTER TABLE. C'est la condition pour rester pret a "des centaines de capteurs" sans dette de migration. Cout : jointures un peu plus verbeuses pour reconstruire une vue large (pivot) au moment de l'entrainement — acceptable, ce pivot se fait cote pandas/polars au chargement, pas en base.

## Regle de split (rappel docs/brief_projet.md)

Le split train/test se fait TOUJOURS au niveau `asset.id`, jamais au niveau `signal` ou `feature`. Toute jointure d'entrainement doit remonter jusqu'a `asset_id` pour construire les folds.

## Classification "type d'application" (ISO 20816-3)

`application_type` (table de reference, voir `configs/application_types.yaml`) :
taxonomie ISO 20816-3 (moteur/generateur electrique, pompe centrifuge,
ventilateur/soufflante, compresseur centrifuge, groupe d'engrenages) + une
categorie hors-norme `bearing_test_rig` pour les bancs de laboratoire (aucun
des 6 machines actuelles n'est une machine de production reelle). `machine.application_type_code`
reference cette table. Permet, a terme, l'interpretation normative (zones
A/B/C/D) une fois une source avec puissance nominale/type de fondation
documentee - pas encore le cas des datasets publics geres ici.

## Vitesse de rotation : mesuree vs config vs saisie manuelle

`test_session.rotational_speed_rpm` reste la vitesse NOMINALE de la condition
(config `machines.yaml`). Quand une source fournit un canal tachymetrique reel
(Paderborn : canal `speed`, raster propre, voir `src/data/loaders.py`), la
vitesse REELLE mesuree est extraite par mesure et stockee comme `feature`
(channel=`speed`, feature_name in `mean_rpm`/`speed_cv`/`is_variable_speed`) -
memes tables, pas de colonne ajoutee (le format EAV de `feature` absorbe ce
nouveau capteur sans migration, exactement l'usage prevu). `is_variable_speed`
est calcule (coefficient de variation > 1%, voir `src/features/speed.py`),
pas suppose : sur les 2559 mesures Paderborn, 1 seule depasse ce seuil (CV
16.6%), le reste est vitesse fixe par design du banc (coherent avec
l'attendu). Pour une source sans canal vitesse dedie (XJTU-SY, et toute
source future en saisie manuelle), seule la valeur nominale de config existe -
un champ de saisie utilisateur est a prevoir au niveau formulaire (pas encore
construit, priorite actuelle = classification des sources existantes plutot
que formulaire live, voir `docs/scaling_path.md`).

## Journal de maintenance

`maintenance_event` (table relationnelle classique, PAS une hypertable : volume
attendu faible et epars, a l'oppose de `feature`) : permet a un utilisateur de
declarer un evenement horodate sur un asset (`fault_detected`,
`bearing_replacement`, `sensor_replacement`, `sensor_relocation`,
`system_modification`, `other`) avec description libre. Formulaire de saisie +
table dans le dashboard (onglet "Journal maintenance"). Objectif : correlation
future avec la derive des features dans le temps (onglet "Derive temporelle") -
ex. un saut de kurtosis qui coincide avec un `bearing_replacement` s'explique
autrement qu'un saut sans evenement associe.

## Etat actuel (2026-08-31)

- Implemente : `machine`, `application_type`, `test_session`, `asset`, `bearing_attributes`, `bearing_geometry`, `signal`, `feature` (hypertable Timescale active), `maintenance_event`.
- Seede : 6 machines (1 pleinement definie : Paderborn ; 5 stubs a completer), 32 assets Paderborn, 6 types d'application ISO 20816-3.
- Peuple : `signal` (7677 lignes), `feature` (46062 lignes : temporel + vitesse).
- Vide : `maintenance_event` (aucun evenement reel a ce jour - pas de donnees fictives inserees).
