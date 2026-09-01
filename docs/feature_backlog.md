# Backlog features — matrice concurrentielle × projet

**Date :** 2026-08-31
**Sources :** `docs/competitive_analysis.md` (analyse détaillée des leaders) + `docs/communication_architecture.md` (trajectoire d'interopérabilité) + état actuel du repo (Phase 2 complétée, Phase 3 prête à lancer).
**Statut :** backlog vivant, à mettre à jour à chaque fin de phase.

---

## 1. Légende

**Statut dans le projet :**
- ✅ **Implémenté et validé** sur les données Paderborn actuelles
- 🟡 **Implémenté mais désactivé** ou en cours de fiabilisation
- ⏳ **Planifié** dans la roadmap actuelle
- ❌ **Hors scope assumé** (explicité dans `docs/competitive_analysis.md` §4.2)
- 🔵 **Piste future** (au-delà de la roadmap actuelle, conditionnée à un déclencheur)

**Priorité concurrentielle** = est-ce que les leaders le font (P0 = table-stakes, P1 = standard, P2 = différenciateur, P3 = nice-to-have) ?

**Effort projet** = estimation grossière, pas un chiffrage (T-shirt size : S/M/L/XL).

**Cohérence projet** = est-ce que c'est aligné avec l'angle "features physiques + rigueur méthodologique" de `docs/brief_projet.md §1` ?

## 2. Matrice — features de diagnostic (cœur métier)

| ID | Feature | Source(s) leader(s) | Priorité concurrentielle | Statut projet | Effort | Cohérence | Action |
|---|---|---|---|---|---|---|---|
| F-01 | RMS (vélocité vibratoire) | Tous (IFM, SKF, Augury, Schaeffler, CWRU) | P0 — table-stakes | ✅ Implémenté (`src/features/time_domain.py`) | — | ✅ | Maintenir ; corriger l'instabilité directionnelle documentée `docs/known_issues.md` |
| F-02 | Kurtosis | Tous, monitoring en continu (IFM cyclique, SKF AutoML) | P0 | ✅ Implémenté | — | ✅ | Maintenir ; interpréter le motif kurtosis sain > kurtosis défaut (cohérent avec `docs/known_issues.md`) |
| F-03 | Crest factor (facteur de crête) | Tous, IFM VVB acyclique | P0 | ✅ Implémenté | — | ✅ | Maintenir |
| F-04 | Skewness | SKF 18 paramètres, plupart plateformes | P1 | ✅ Implémenté | — | ✅ | Maintenir |
| F-05 | Peak-to-peak | SKF, IFM a-Peak cyclique | P0 | ✅ Implémenté | — | ✅ | Maintenir |
| F-06 | Analyse d'enveloppe (Hilbert) | Schaeffler ConditionAnalyzer, SKF, Augury | P0 | 🟡 Implémenté (`src/features/envelope.py`) mais **désactivé dans le pipeline** | M | ✅ | Réactiver après stabilisation kurtogramme (action F-07) |
| F-07 | Kurtogramme / spectral kurtosis (Antoni) | Schaeffler (ConditionAnalyzer), SKF, Augury (interne) | P0 | 🟡 Consensus multi-mesures implémenté (`average_kurtogram_map`/`consensus_resonance_band`, `src/features/envelope.py`) + bug de bord STFT corrigé (DC/Nyquist). Validé sur K001/KA01/KA04 : convergence K001↔KA01 confirmée (~15.9-16.1kHz partagé), mais KA04 porte 2 candidats concurrents non tranchés (voir `docs/known_issues.md` §F-07) | M | ✅ | Valider sur les 32 roulements avant activation par défaut. `--with-envelope` toujours désactivé dans `scripts/build_dataset.py` |
| F-08 | Énergie spectrale aux fréquences BPFO/BPFI/BSF/FTF | Schaeffler ConditionAnalyzer, SKF AutoML, Augury 100+ failure modes | P0 | ⏳ Calculé (`src/features/fault_frequencies.py`), `fault_frequency_energies` accepte maintenant `resonance_band` précalculé (consensus) - toujours désactivé (couplé à F-07, validation 32 roulements en attente) | M | ✅ | Activer une fois F-07 validé sur l'ensemble du dataset. Géométrie n_balls=9→8 déjà corrigée (`configs/bearing_geometry.yaml`) |
| F-09 | Bandes latérales (sidebands) autour de BPFO/BPFI | Schaeffler, SKF, avancé | P1 | ❌ Non implémenté | M | ✅ | À implémenter dans `envelope.py` une fois F-07/F-08 stables. Distingue défaut bague int. (modulé par fr) vs ext. (stable) |
| F-10 | Comparaison vibration seule / courant moteur seul / fusion (MCSA) | Objectif secondaire brief §2 | P1 | ✅ Implémenté Phase 2 (`scripts/run_gbm.py`), F1 0.738 / 0.542 / 0.726 (intervalles se chevauchent) | — | ✅ | À reconfirmer sur Phase 3 (objectif principal) avant de conclure l'argument coût capteur |
| F-11 | Détection défaut autre que roulement (balourd, désalignement, jeu, lubrification) | Augury 100+ modes, Schaeffler, Senseye failure mode library | P1 | 🟡 Documenté (`docs/theorie_reference.md` §4bis) mais pas implémenté en code | L | ✅ | Piste future : si on a des données avec défauts non-roulement (variateur, dataset complémentaire). Pas critique pour Phase 3 |
| F-12 | Classification défaut (bague ext/int/bille/cage) | Schaeffler ConditionAnalyzer, SKF, Augury | P0 | ⏳ GBM le permet techniquement (5 classes + healthy), pas encore formellement lancé | M | ✅ | Tester formellement sur Phase 3 si pertinent ; sinon laisser pour itération ultérieure |
| F-13 | RUL (Remaining Useful Life) | Schaeffler LifetimeAnalyzer, SKF Enlight AI, Senseye Prophet, C3.ai | P1 | ❌ Non implémenté (Phase 0 non tranchée) | XL | ✅ | Si bascule vers XJTU-SY, c'est un sous-projet à part entière. Décision `docs/brief_projet.md §8` Phase 0 |
| F-14 | Sévérité (grading 1-4) | Augury, SKF, Schaeffler | P1 | ❌ Non implémenté | L | ✅ | Mapper les classes saines/healthy/early/degraded/faulty de Paderborn sur une échelle de sévérité 1-4, à coupler avec F-12 |
| F-15 | Recommandation textuelle prescriptive ("remplacer roulement drive-end dans 2 semaines") | Augury (signature), IFM (moneo tickets) | P2 — différenciateur | ❌ Non implémenté | M | ✅ | Piste future ; s'appuierait sur F-12 + F-14. Aligné avec `docs/differentiation_strategy.md` angle #1 (calculateur ROI) |
| F-16 | Détection ultrason ultra-low RPM (1-150 tr/min) | Augury (mars 2025, industry first) | P2 | ❌ Non implémenté | XL | ➖ | Hors scope Paderborn (900-1500 RPM) ; utile si extension vers éolien / gros moteurs marins |

## 3. Matrice — features de données / ingestion

| ID | Feature | Source(s) leader(s) | Priorité concurrentielle | Statut projet | Effort | Cohérence | Action |
|---|---|---|---|---|---|---|---|
| F-20 | Loader `.mat` Paderborn (HDF5) | N/A (datasets publics) | N/A | ✅ Implémenté (`src/data/loaders.py`) | — | ✅ | Maintenir |
| F-21 | Loader CSV XJTU-SY | N/A | N/A | ❌ Non implémenté (Phase 0 diagnostic-only) | S | ✅ | Si bascule RUL en Phase 0 |
| F-22 | Loader format SKF Axios JSON | SKF | P1 | ❌ Non implémenté | S | ✅ | À activer si T+1 (cf. `docs/communication_architecture.md` §4.2) |
| F-23 | Connecteur OPC-UA Client | Schaeffler (confirmé), Siemens, IFM edgeGateway | P1 | ❌ Non implémenté | M | ✅ | T+1 si déclencheur ingestion continue |
| F-24 | Connecteur MQTT Consumer | IFM edgeGateway (MQTTs), UNS moderne | P1 | ❌ Non implémenté | M | ✅ | T+1 |
| F-25 | Connecteur Modbus TCP poller | Variateurs et automates partout (legacy) | P1 | ❌ Non implémenté | M | ✅ | T+1, indispensable pour retrofit variateurs existants |
| F-26 | Connecteur IO-Link BLOB reader | IFM VVB acyclique BLOB 4 s | P2 | ❌ Non implémenté | M | ➖ | T+1+ si déploiement chez un client avec matériel IFM |
| F-27 | Producteur Sparkplug B (EoN) | Eclipse Tahu, UNS moderne | P1 | ❌ Non implémenté | M | ✅ | T+3 (cf. `docs/communication_architecture.md` §4.4) |
| F-28 | Producteur JSON structuré (work orders / events) | SKF Axios schema, IFM moneo | P1 | ❌ Non implémenté | S | ✅ | T+1, basique, format documenté dans `docs/communication_architecture.md` §4.2 |
| F-29 | Sérialisation AAS (submodèle ConditionMonitoring) | IEC 63278-1:2023, ZVEI, Plattform Industrie 4.0 | P2 — différenciateur long terme | ❌ Non implémenté | M | ✅ | T+2 (cf. `docs/communication_architecture.md` §4.3). Fort potentiel vitrine |

## 4. Matrice — features de gouvernance / MLOps

| ID | Feature | Source(s) leader(s) | Priorité concurrentielle | Statut projet | Effort | Cohérence | Action |
|---|---|---|---|---|---|---|---|
| F-30 | Tracking d'expériences (MLflow) | Tous (MLflow est l'outil de facto) | P0 | ✅ Implémenté (`docker-compose.yml`, service `mlflow`) | — | ✅ | Maintenir ; SQLite local suffit tant qu'on est dans le périmètre |
| F-31 | Split par asset (jamais par signal) | Tous les papiers publiés (non explicité par les éditeurs) | P0 | ✅ Implémenté + testé (`tests/test_splits.py`, `src/data/splits.py`) | — | ✅ | Maintenir ; c'est la règle d'or (docs/brief_projet.md §4) |
| F-32 | Cross-condition evaluation (piege condition/charge) | Brealey et al. 2007 + tous les papiers sérieux | P0 | ⏳ À tester formellement | S | ✅ | Lancer sur Phase 3, voir `docs/known_issues.md` §"confusion date/asset" |
| F-33 | Baseline seuil (RMS/kurtosis) | Tous les éditeurs, mais rarement explicité | P0 | ✅ Implémenté (`src/models/baseline.py`, F1 0.682 kurtosis) | — | ✅ | Maintenir, c'est le "must beat" du brief §4 |
| F-34 | Validation croisée stratifiée par groupe | sklearn StratifiedGroupKFold | P0 | ✅ Implémenté (`scripts/run_baseline.py`, `scripts/run_gbm.py`, 5 folds) | — | ✅ | Maintenir ; protège contre l'overfit sur petit dataset |
| F-35 | F1 macro (balanced accuracy) | Tous sur datasets déséquilibrés | P0 | ✅ Implémenté | — | ✅ | Maintenir ; classe majoritaire serait trompeuse |
| F-36 | Normalisation post-split (jamais globale) | Bonne pratique standard | P0 | ✅ Implémenté (StandardScaler fit sur train uniquement) | — | ✅ | Maintenir ; docs/brief_projet.md §4 piège #5 |
| F-37 | Gestion du déséquilibre de classes | SKF, Augury, Schaeffler (interne) | P0 | ✅ Implémenté (stratification dans StratifiedGroupKFold) | — | ✅ | À renforcer avec class_weight si on bascule vers RUL (XJTU-SY très déséquilibré phase saine) |
| F-38 | Détection de drift temporel | SKF, Augury (entraînement continu) | P1 | 🟡 Implémenté (`src/evaluation/temporal_drift.py`) | — | ✅ | Maintenir ; cohérent avec `docs/known_issues.md` §"confusion date/asset" |
| F-39 | Tests unitaires (fréquences caractéristiques, splits) | Bonne pratique | P0 | ✅ Implémenté (`tests/test_fault_frequencies.py`, `tests/test_splits.py`) | — | ✅ | Maintenir ; docs/brief_projet.md §6 |
| F-40 | Configuration YAML (pas de constantes en dur) | Bonne pratique 12-factor | P1 | ✅ Implémenté (`configs/`) | — | ✅ | Maintenir ; docs/brief_projet.md §6 |
| F-41 | Publication dataset sur Hugging Face | Objectif tertiaire brief §2. Note 2026-08-31 : Forgis/Mechanical-Components existe deja sur HF (10k+ samples, 16 sources), mais Paderborn est dans son VAL set, pas en source d'entrainement. Valeur ajoutee du projet : distinction explicite artificiel/naturel, 2 canaux courant moteur (Forgis est vibration-only), geometries 6203/UER204 explicites, splits par condition (N09/N15) en plus de par source, splits par asset documentes et testes, documentation methodologique (docs/brief_projet.md + 11 docs). **Action : publier quand meme, positionne comme "Paderborn-KAt ML-ready : artificiel vs reel + courant moteur"**. Citer Forgis dans la dataset card comme "related work". Licence CC BY-NC 4.0 - non commercial, mail C. Lessmeier a initier. | P1 | ❌ Non implémenté | M | ✅ | T+ apres Phase 3, post-publication resultats. Voir `docs/forgis_dataset_analysis.md` pour l'analyse complete. |
| F-42 | Détection de fuite de données (sanity check) | Bonne pratique | P0 | ✅ Systématisé (`tests/test_no_leakage_integration.py`) | — | ✅ | Fait 2026-08-31 : teste directement `cross_validate_feature`/`cross_validate_sensor_set` (les vraies fonctions des scripts, pas une réimplémentation) + la config StratifiedGroupKFold rejouée indépendamment. 25/25 tests passent |
| F-43 | Rapport d'incertitude (intervalles de confiance) | SKF, Augury (intervalles sur les alertes) | P2 | 🟡 Ad hoc (écart-type sur les 5 folds Phase 2) | S | ✅ | Formaliser : moyenne ± std + intervalle 95% (bootstrap) systématique dans `scripts/` |
| F-44 | Reproductibilité (seed fixe, hash code+data) | Bonne pratique | P1 | 🟡 `uv.lock` généré + hash dataset loggé en mlflow (`src/data/dataset_hash.py`) | — | ✅ | Fait 2026-08-31 pour la partie code/data. **Bloquant restant : pas de repo git du tout** (`git status` → "not a git repository") — impossible de "vérifier que le lockfile est commité" sans repo. À arbitrer avec Patrice avant de git init soi-même |
| F-45 | Dashboarding analyste (Streamlit) | IFM moneo UI, SKF Enlight Centre, Augury UI | P1 | 🟡 Partiellement implémenté (`app/dashboard.py`) | L | ✅ | T+ après ingestion : ajouter onglets "alertes", "maintenance event entry", "dérive temporelle" (déjà spécifiés `docs/data_model.md`) |
| F-46 | Export PDF des résultats | SKF Enlight export | P2 | 🟡 Pattern déjà écrit (`scripts/build_glossaire_visuel.py`, PDF+PPTX depuis données réelles Paderborn) mais pas généralisé aux autres livrables | S | ✅ | Demande explicite de Patrice actée 2026-09-01. Réutiliser le pattern pour exporter `docs/results_phase3.md` une fois rempli (voir F-71 pour le detail) |
| F-47 | Rapport annuel de santé du parc (multi-asset summary) | IFM moneo dashboards, Maximo, Augury fleet view | P1 | 🟡 Partiellement (dashboard `app/dashboard.py`) | M | ✅ | Activer quand on aura ingestion multi-asset (T+1) |
| F-69 | Statut du dernier run pipeline visible dans le dashboard | Pattern "refresh monitor" générique (source : revue notes Evernote/Medium, 2026-09-01 — pas un pattern spécifique maintenance industrielle, un pattern d'automatisation générique transposé) | P1 | ❌ Non implémenté | S | ✅ | Exposer le dernier run mlflow par script (`run_baseline.py`/`run_gbm.py`/`build_dataset.py`) — succès/échec, timestamp — dans le dashboard. Source `mlflow.search_runs`, déjà utilisé ailleurs dans `app/tabs/alertes.py` ; pas de nouvelle infra. Demandé par Patrice 2026-09-01 ("gestion des saving en automatique") |
| F-70 | Garde-fou qualité avant affichage d'un résultat (pas seulement avant l'entraînement) | Pattern "data quality validator" générique (même source que F-69) | P1 | 🟡 Recouvre partiellement F-42 (détection fuite, côté train/test) et le pattern "erreur explicite + return" déjà dans `app/tabs/alertes.py` (run introuvable). Ce qui manque : un check sur la COMPLÉTUDE d'un run existant (tous les params/métriques attendus présents) avant de l'afficher, pas juste sur son existence | S | ✅ | Étendre `app/tabs/alertes.py::_read_threshold_from_run` (déjà lève une erreur si un champ manque) au reste du dashboard — même garde-fou partout, pas juste sur l'onglet Alertes. Demandé par Patrice 2026-09-01 |
| F-71 | Export PDF automatique des rapports de résultats | Pattern "automated report export" générique (même source que F-69) — fusionne avec F-46 | P2 | 🟡 Voir F-46 | S | ✅ | Action concrète : une fois `docs/results_phase3.md` rempli (post go/no-go F-07), générer son export PDF avec le même pattern que `scripts/build_glossaire_visuel.py`. Ne pas construire un nouveau système d'export générique tant qu'un 2e cas d'usage concret n'existe pas (YAGNI) |

## 5. Matrice — features de communication / interop

| ID | Feature | Source(s) leader(s) | Priorité concurrentielle | Statut projet | Effort | Cohérence | Action |
|---|---|---|---|---|---|---|---|
| F-50 | Export CSV | SKF Axios app, tous | P1 | ❌ Non implémenté (parquet seulement) | S | ✅ | T+ post-Phase 3, trivial à ajouter |
| F-51 | REST API ingestion (push) | IFM moneo, Maximo REST, tous | P1 | ❌ Non implémenté | S | ✅ | T+1, basique |
| F-52 | REST API exposition résultats | Tous (CMMS read API) | P1 | ❌ Non implémenté | S | ✅ | T+1, basique |
| F-53 | Webhook alertes | Augury, IFM, tous | P1 | ❌ Non implémenté | S | ✅ | T+1 |
| F-54 | Endpoint AAS REST | Phoenix Contact, Siemens, ZVEI | P2 | ❌ Non implémenté | M | ✅ | T+2 (cf. `docs/communication_architecture.md` §4.3) |
| F-55 | MQTT broker EMQX self-hosted | IFM edgeGateway, HiveMQ, EMQX | P1 | ❌ Non implémenté | S | ✅ | T+3 |
| F-56 | Namespace topic Sparkplug B | UNS, Eclipse Tahu | P1 | ❌ Non implémenté | M | ✅ | T+3 |
| F-57 | Intégration CMMS (SAP/Maximo/Fiix) | IFM moneo tickets, Maximo IFACE, SKF | P2 | ❌ Non implémenté | XL | ➖ | **Hors scope assumé.** Coût d'intégration démesuré vs valeur portfolio. Export JSON structuré suffit (F-28) |
| F-58 | Intégration ERP/MES | IFM, Maximo, AVEVA | P2 | ❌ Non implémenté | XL | ➖ | Hors scope assumé |
| F-59 | Connecteur cloud direct (AWS IoT Core, Azure IoT Hub) | IFM edgeGateway, SKF Axios, Augury cloud | P2 | ❌ Non implémenté | M | ➖ | T+1 si besoin client cloud spécifique, sinon T+3 avec EMQX self-hosted |

## 6. Matrice — features d'infrastructure / déploiement

| ID | Feature | Source(s) leader(s) | Priorité concurrentielle | Statut projet | Effort | Cohérence | Action |
|---|---|---|---|---|---|---|---|
| F-60 | Docker Compose (db + mlflow + app + dashboard) | Standard pour portfolio ML | P1 | ✅ Implémenté (`docker-compose.yml`) | — | ✅ | Maintenir tant qu'on est dans le périmètre |
| F-61 | Hypertable Timescale (time-series) | InfluxDB, Timescale, QuestDB | P1 | ✅ Implémenté (`feature` hypertable) | — | ✅ | Maintenir ; `docs/scaling_path.md` §"ce qui ne change pas" |
| F-62 | Schéma DB pensé pour scale (asset générique, EAV feature) | SKF Axios JSON, AAS | P1 | ✅ Implémenté (`docs/data_model.md`) | — | ✅ | Maintenir ; déjà différenciant (cf. `docs/differentiation_strategy.md` angle #4) |
| F-63 | Edge AI (modèle ONNX embarqué) | IFM DataScience, Schaeffler, Augury | P2 | ❌ Non implémenté | L | ✅ | T+4 (cf. `docs/communication_architecture.md` §4.5) |
| F-64 | Kubernetes / K8s | Tous à partir d'une certaine échelle | P1 | ❌ Non implémenté (assumé hors scope) | XL | ➖ | `docs/scaling_path.md` §1 : ne se justifie qu'à T+ avec ingestion continue multi-sites |
| F-65 | Ray / Ray Tune | SparkCognition, gros projets internes | P1 | ❌ Non implémenté (assumé hors scope) | L | ➖ | `docs/scaling_path.md` §2 : ne se justifie qu'à T+ avec volumétrie qui dépasse une machine |
| F-66 | Feature store (Feast, Tecton) | Maximo, Uber Michelangelo, etc. | P1 | ❌ Non implémenté | L | ➖ | Hors scope assumé ; tables `feature` en Postgres font le job |
| F-67 | Airflow / orchestration DAG | Tous à l'échelle enterprise | P1 | ❌ Non implémenté | M | ➖ | Hors scope ; Docker Compose + scripts CLI suffisent |
| F-68 | CI/CD (GitHub Actions, tests automatisés) | Tous | P1 | 🟡 Tests pytest locaux (pas de CI configuré) | S | ✅ | À ajouter si Patrice veut automatiser — pas bloquant pour le moment |

## 7. Décisions ouvertes — à arbitrer par Patrice

### 7.1 Avant Phase 3 (objectif principal)

- **F-07 (kurtogramme consensus)** : la décision d'activer l'enveloppe conditionne le potentiel du projet à dépasser la baseline kurtosis (F1 0.682) sur Phase 3. Priorité haute, mais c'est un sous-projet de recherche — peut être itéré.
- **F-32 (cross-condition)** : à tester formellement sur Phase 3, c'est une des pierres angulaires de la rigueur méthodologique (docs/brief_projet.md §4 règle #2).
- **F-42 (détection fuite)** : à systématiser en test unitaire. Effort S, gain immédiat en confiance sur les résultats.

### 7.2 Avant Phase 4 (restitution)

- **F-43 (intervalles de confiance)** : à formaliser pour les rapports Phase 4. Effort S, indispensable pour la crédibilité.
- **F-44 (reproductibilité)** : à formaliser (lock requirements, hash dataset en MLflow). Effort S.
- **F-41 (publication HF)** : à planifier post-Phase 3. Effort M, gros asset portfolio.
- **F-50 (export CSV)** : à ajouter pour publication HF (le HF Hub accepte parquet mais CSV est attendu par les utilisateurs classiques).

### 7.3 Décisions long terme (à considérer si projet évolue hors portfolio)

- **F-23/24/25/28 (connecteurs OPC-UA/MQTT/Modbus + JSON export)** : bloc cohérent à activer ensemble au T+1.
- **F-29 (AAS)** : à considérer si Patrice vise le marché Industrie 4.0 / vitrine européenne.
- **F-57 (intégration CMMS)** : ne pas faire, sauf demande explicite et chiffrée d'un client.
- **F-63 (edge AI)** : à considérer si argument commercial "edge-deployable" devient central.

## 8. Synthèse visuelle

**Ce que le projet a déjà (vert) :**
- Fondations de diagnostic (F-01 à F-05) ✅
- Architecture data pensée pour scale (F-20, F-31, F-34-37, F-60-62) ✅
- MLOps léger (F-30, F-39, F-40) ✅
- Comparaison vibration/courant posée (F-10) ✅
- Détection de drift (F-38) ✅

**Ce qui est implémenté mais désactivé (jaune) — à fiabiliser :**
- Analyse d'enveloppe (F-06)
- Kurtogramme (F-07)
- Énergie BPFO/BPFI/BSF/FTF (F-08)

**Ce qui est planifié (orange) — à exécuter dans la phase actuelle :**
- Cross-condition evaluation (F-32)
- Classification défaut formelle (F-12)
- Détection de fuite systématisée (F-42)
- Intervalles de confiance formalisés (F-43)
- Reproductibilité hash (F-44)
- Statut de run visible dashboard (F-69), garde-fou qualité affichage (F-70), export PDF résultats (F-46/F-71) — "gestion des saving en automatique", demandé 2026-09-01

**Ce qui est hors scope assumé (rouge) — ne pas faire :**
- Capteurs propriétaires (sauf dataset)
- Plateforme cloud SaaS
- Pricing enterprise
- AutoML "no data scientists"
- Intégration CMMS native (F-57)
- Kubernetes / Ray / Airflow (F-64, F-65, F-67)
- Feature store (F-66)

**Ce qui est une piste future (bleu) — conditionnée à un déclencheur :**
- Connecteurs ingestion (F-23 à F-28) — T+1
- AAS (F-29, F-54) — T+2
- Sparkplug B / UNS (F-27, F-55-56) — T+3
- Edge AI (F-63) — T+4
- RUL (F-13) — Phase 0 si bascule XJTU-SY

## 9. Notes finales

- Ce backlog est vivant. À chaque fin de phase (Phase 3, Phase 4), revoir les statuts et les actions.
- Les features "leaders" peuvent bouger vite (cf. Augury ultrason mars 2025). Re-vérifier la concurrence annuellement.
- L'ajout de features hors scope (F-23 et après) ne doit pas se faire tant que la Phase 3 n'est pas validée — c'est la règle `docs/scaling_path.md` §"hypothèses actuelles".
