# Architecture de communication de la donnée — trajectoire d'interopérabilité

**Date :** 2026-08-31
**Statut :** document de référence, pas un plan d'implémentation immédiat
**Hypothèse de cadrage :** ce projet reste sur datasets publics batch tant que l'objectif principal (généralisation artificiel→réel) n'est pas atteint. La trajectoire ci-dessous s'active à partir du moment où l'un des "déclencheurs" de `docs/scaling_path.md` §1 se réalise (ingestion continue depuis capteurs réels).

---

## 1. Pourquoi ce document

`docs/brief_projet.md §2` mentionne l'objectif tertiaire "publication du dataset sur Hugging Face" mais reste muet sur les **protocoles de communication de la donnée**. Or la donnée vibrante vit dans deux mondes qui parlent des langues différentes :

- **Monde capteur/edge** : IO-Link, Modbus, OPC-UA client, MQTT(S), Profinet, EtherNet/IP — protocoles industriels contraints par le temps réel, la latence, le déterminisme.
- **Monde cloud/IT** : REST API, JSON, parquet, data lake, message broker pub/sub — protocoles conçus pour le débit, la scalabilité, la consommation asynchrone.

Le projet est aujourd'hui 100 % côté IT (parquet, JSON, Postgres, MLflow). Quand l'ingestion continue se présentera, il faudra un plan pour traverser la frontière OT/IT. Ce document trace ce plan, en s'appuyant sur ce que font les éditeurs leaders (`docs/competitive_analysis.md`) et sur les standards IEC/ISO.

## 2. Cartographie des protocoles — qui fait quoi

### 2.1 Côté terrain (capteur → edge gateway)

| Protocole | Standard | Usage typique | Leaders qui l'utilisent | Forces | Limites |
|---|---|---|---|---|---|
| **IO-Link** | IEC 61131-9 | Capteur → maître IO-Link, point-à-point, mono-maître | IFM (VVB, VWV), Sick, Balluff, Banner | Câblage standard 3 fils, paramétrage à distance, données cycliques (process) + acycliques (BLOB, diagnostic). 230.4 kBaud (COM3) = suffisant pour v-RMS, a-Peak, kurtosis, mais pas pour signal brut haute fréquence en continu | Pas adapté au streaming continu haute fréquence, mono-fournisseur par capteur |
| **Modbus RTU/TCP** | Modicon (1979), IEC harmonisé | Capteur/automate → passerelle, polling maître/esclave | Très universel (capteurs legacy), Banner Engineering DXM, beaucoup de variateurs | Ultra-simple, ubiquitaire, interopérable partout | Pas de sécurité native, pas de modèle de données, pas d'event-driven, polling obligatoire |
| **Profinet / EtherNet/IP** | IEC 61158 / ODVA | Bus de terrain temps réel, automate → I/O distribués | Siemens (Profinet), Rockwell (EtherNet/IP) | Déterministe, haut débit, intégration automate native | Lourd à mettre en œuvre hors contexte automate |
| **OPC-UA Client/Server** | IEC 62541-1 à -14 | Lecture/écriture structurée, navigation dans un modèle d'information | Schaeffler (confirmé), Siemens, tous les éditeurs IT industriels | Modèle de données riche, sécurité native (signing/encryption), Companion Specifications par industrie | Plus lourd que MQTT, plus complexe à mettre en œuvre |
| **Capteurs sans fil propriétaires** | (variable) | Wireless mesh 2.4 GHz ISM, longue autonomie batterie | IFM VWV (mesh 2.4 GHz), SKF Axios, Augury Halo (cellulaire), Schaeffler OPTIME | Pas de câblage, déploiement rapide, idéal retrofit | Vendor lock-in, RSSI variable, latence réseau imprévisible |

### 2.2 Côté edge → cloud / IT

| Protocole | Standard | Usage typique | Leaders qui l'utilisent | Forces | Limites |
|---|---|---|---|---|---|
| **MQTT** | ISO/IEC 20922:2021 | Pub/sub léger, broker central, idéal WAN/contraint | HiveMQ, EMQX, AWS IoT Core, Azure IoT Hub, tous les éditeurs IIoT | Très léger, découplé, TLS, QoS 0/1/2, scale à des millions de devices | Payload opaque (à standardiser via Sparkplug B ou contrat JSON) |
| **MQTT + Sparkplug B** | Eclipse Tahu (open) | MQTT + namespace topic + birth/death certificates + Protobuf | Très adopté en UNS (Unified Namespace), beaucoup d'architectures 2025+ | MQTT + auto-discovery + structure de payload, idéal multi-fleet | Pas un standard IEC (mais de facto) |
| **OPC-UA Pub/Sub** | IEC 62541-14:2020 | OPC-UA sur UDP multicast ou MQTT | Siemens, gros industriels | Modèle sémantique OPC-UA + transport pub/sub | Plus complexe, deux implémentations à choisir (broker MQTT ou UDP multicast) |
| **REST API / OpenAPI** | (de facto) | Pull/push vers cloud, configuration, dashboard | IFM moneo REST, IBM Maximo REST, SKF Axios JSON over HTTPS | Universel, debuggable, cacheable, firewall-friendly | Pas de streaming, overhead HTTP, pas event-driven |
| **AWS Kinesis / Azure Event Hubs** | (vendor) | Streaming cloud-managed, haute fréquence | SKF Axios → AWS Kinesis (confirmé) | Scalabilité cloud native, intégration écosystème cloud | Vendor lock-in |
| **Kafka** | Apache | Streaming event-driven, haut débit, log distribué | Plateformes internes, gros industriels | Durabilité, relecture, découplage temporel | Lourd à opérer, surdimensionné pour quelques centaines de capteurs |
| **Parquet / CSV / JSON fichiers** | (de facto) | Batch export, archive, transport manuel | SKF Axios CSV, IFM moneo export, Augury dashboard export | Simple, durable, auditable, humain-lisible | Pas temps réel, taille fichier |

### 2.3 Côté modèle de données / sémantique

| Standard | Référence | Usage | Lien projet |
|---|---|---|---|
| **Asset Administration Shell (AAS)** | IEC 63278-1:2023 (anciennement DIN SPEC 91345) | Modèle d'information standardisé pour digital twin, submodèles sémantiques (MaintenanceSchedule, ConditionMonitoring, etc.) | Vocation long terme : décrire chaque `asset` Paderborn comme une AAS avec submodèle condition monitoring (BPFO/BPFI/BSF/FTF, RMS, kurtosis). Cf. §4.3 |
| **OPC-UA Companion Specifications** | Consortium OPC Foundation | Modèles d'information par industrie (Robotics, Machine Vision, Pumps, etc.) | Vocation moyen terme, conditionné à l'arrivée de vrais automates (hors scope actuel) |
| **ECLASS** | ECLASS e.V. | Standard de classification produit, ISO-conforme | Hors scope (catalogue produit, pas maintenance) |
| **ISO 13374** | ISO 13374 (condition monitoring architecture) | Architecture fonctionnelle 8 blocs : acquisition → manipulation → state → health → prognostic → decision → presentation → actioning | Cadrage déjà référencé dans `docs/theorie_reference.md` §1, l'arborescence `src/` suit ce cadre |

## 3. Architecture cible — modèle de référence

Le pattern qui revient chez **tous** les leaders (IFM edgeGateway, Schaeffler Smart EcoSystem, SKF Axios + AWS, Augury cloud, Senseye sur MindSphere, Siemens Insights Hub) est le suivant :

```
[Capteurs terrain]
    │  (IO-Link, Modbus, wireless proprio, Profinet, EtherNet/IP)
    ▼
[Edge gateway / local controller]
    │  - Extraction features (RMS, kurtosis, BPFO/BPFI, FFT)
    │  - Seuils ISO 20816-3 paramétrables
    │  - Détection locale d'alarmes
    │  - Cache local
    │  (OPC-UA Server, Modbus TCP Server, REST, fichier)
    ▼
[Bus de données OT-IT — UNS backbone]
    │  - Topic namespace standardisé
    │  - Pub/sub event-driven
    │  (MQTT + Sparkplug B sur broker type HiveMQ/EMQX/AWS IoT Core/Azure IoT Hub)
    ▼
[Cloud / data center / serveur on-prem]
    │  - Ingestion (consumer MQTT)
    │  - Stockage time-series (TimescaleDB / InfluxDB / PI System)
    │  - ML training (batch)
    │  - Inference (online ou batch)
    │  - Dashboarding (Streamlit / Grafana / app métier)
    │  - Alertes et work orders
    ▼
[Systèmes métier]
    │  (CMMS : SAP PM, IBM Maximo, Fiix, UpKeep — via REST ou IFACE tables)
    │  (Historien : AVEVA PI, OSIsoft — via OPC-UA ou fichiers)
    │  (ERP / MES — via REST)
    ▼
[Humain]
    - Tableau de bord
    - Application mobile
    - Email / SMS / webhook
```

**Le projet s'insère dans ce modèle de deux façons :**

- **Court terme (Phase 2-3 actuelle)** : le projet est un **consommateur de données batch** (parquet Paderborn). Il n'est pas dans la boucle ci-dessus, il alimente la couche "ML training" avec un dataset statique.

- **Moyen terme (déclencheur ingestion continue)** : le projet devient un **consommateur live** + un **producteur d'alertes JSON** + un **producteur d'export parquet/JSON** vers l'aval (CMMS, data lake, autres modèles).

## 4. Trajectoire d'intégration par phase

### 4.1 Phase actuelle (T0) — Datasets publics batch

**Périmètre :** Paderborn 32 assets + 4 conditions + courant moteur, ingestion via `scripts/build_dataset.py`, batch 86 s pour 2560 mesures, Postgres hypertable `feature`.

**Protocoles utilisés :**
- Lecture de fichiers `.mat` (HDF5) → pandas/polars
- Écriture parquet (PyArrow) sur disque + insertion Postgres via `src/data/db.py`
- Pas de protocole réseau, pas de streaming.

**Interface projet exposée :**
- Dashboard Streamlit lit la DB Postgres (Streamlit → psycopg2).
- MLflow local SQLite pour le tracking des runs.

**Verdict :** pas d'action. Le projet est dans son périmètre nominal, conforme à `docs/brief_projet.md §1` ("pas besoin d'empiler Kubernetes, Airflow et un feature store").

### 4.2 Phase T+1 — Activation des connecteurs données

**Déclencheur :** décision explicite de Patrice d'aller au-delà du périmètre portfolio (commercialisation, démo client, ou volonté de benchmarker sur des données live).

**Ajouts minimaux :**

1. **Connecteur OPC-UA Client** (Python `asyncua` ou `opcua`).
   - Lecture de variables depuis un edge gateway IFM/Schaeffler ou un automate Siemens/Schneider.
   - Modèle d'information simple : `ns=1;s=Machine.<asset_id>.<channel>.<feature_name>`.
   - Mapping direct vers le schéma `feature` EAV déjà en place (cf. `docs/data_model.md`).

2. **Connecteur MQTT Consumer** (Python `paho-mqtt` ou `aiomqtt`).
   - Subscription à un topic namespace, ex. `spBv1.0/PP/DB/<machine>/<asset>/<channel>/<feature>` (Sparkplug B) ou namespace propriétaire JSON.
   - Décodage du payload (JSON ou Protobuf) → insertion en base via la même API que les batch.

3. **Connecteur Modbus TCP poller** (Python `pymodbus`).
   - Pour les variateurs et automates qui n'exposent que Modbus (cas très fréquent en retrofit).
   - Polling périodique (1 Hz ou moins) sur des registres définis par config YAML.

4. **Producteur JSON structuré** (cf. format SKF Axios schema, `docs/competitive_analysis.md` §3.3).
   - Endpoint REST qui sérialise un `asset_id` + son dernier `state` + ses `maintenance_event` au format JSON.
   - Compatible avec un consommateur downstream (CMMS, dashboard custom, autre modèle ML).

**Architecture cible après T+1 :**

```
[Edge gateway client]    [Variateur]    [Capteur IO-Link direct]
       │                     │                  │
       │ OPC-UA              │ Modbus TCP       │ IO-Link via maître
       ▼                     ▼                  ▼
[Connecteur OPC-UA]   [Connecteur Modbus]   [Connecteur IO-Link]
       │                     │                  │
       └─────────────────────┴──────────────────┘
                              │
                              ▼
                  [Bus interne — files Python]
                              │
                              ▼
                  [API ingestion unifiée]
                              │
                              ▼
                  [DB Timescale hypertable feature]
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        [Dashboard]     [ML pipeline]   [Export JSON REST]
```

**Volumétrie visée :** quelques dizaines à quelques centaines de capteurs, polling 1 Hz, soit ~10M points/jour. TimescaleDB gère nativement (cf. `docs/data_model.md` §1). Pas de Kafka, pas de Kubernetes à ce stade (cf. `docs/scaling_path.md` §1 déclencheur 1).

**Coût d'implémentation :** ~2-3 semaines pour les 3 connecteurs + tests, plus 1 semaine pour l'export JSON structuré. ~80 % du code est de l'orchestration d'I/O, peu de logique métier nouvelle.

### 4.3 Phase T+2 — Modèle de données sémantique (AAS)

**Déclencheur :** volonté d'interopérer avec un écosystème Industrie 4.0 (plateforme Siemens, fournisseur AAS, ou projet vitrine).

**Ajouts :**

1. **Sérialisation AAS** de chaque `asset` Paderborn.
   - Submodèle **"ConditionMonitoring"** (spécification ZVEI / Platform Industrie 4.0) avec :
     - `vRMS`, `aPeak`, `aRMS` cycliques
     - `crestFactor`, `kurtosis`, `skewness` acycliques
     - `BPFO_Hz`, `BPFI_Hz`, `BSF_Hz`, `FTF_Hz` (calculés depuis `asset.bearing_attributes`)
     - `healthState` (enum : healthy, degraded, faulty)
     - `lastMaintenanceEvent`
   - Submodèle **"MaintenanceSchedule"** lié au `maintenance_event` (au lieu d'être dans le submodèle CM).
   - Sérialisation AASX (ZIP/OPC) pour échange de fichiers, REST AAS pour accès en ligne.

2. **Endpoint REST AAS** : `GET /aas/{asset_id}/submodels/ConditionMonitoring` retourne le submodèle sérialisé JSON.

**Pourquoi c'est pertinent :**
- L'AAS est la lingua franca de l'Industrie 4.0 allemande (et de plus en plus internationale).
- Décrire chaque roulement Paderborn comme une AAS transforme le projet portfolio en **artefact de référence** pour quiconque veut simuler/benchmark un écosystème AAS sans avoir les automates réels.
- Le coût d'implémentation est modéré : la spec est riche mais les submodèles standards sont réutilisables.

**Volumétrie / infra :** pas de changement, AAS est juste un autre format de sérialisation.

**Coût d'implémentation :** ~1 semaine pour le submodèle ConditionMonitoring + tests, ~2-3 jours pour l'endpoint REST.

### 4.4 Phase T+3 — Sparkplug B + multi-sites

**Déclencheur :** passage à l'échelle multi-sites ou ingestion d'un parc hétérogène (plusieurs clients/sites, plusieurs marques de capteurs).

**Ajouts :**

1. **Producteur Sparkplug B** : publier l'état actuel du système comme un Edge of Network Node (EoN), avec un Device par `machine` et des Metrics typées.
   - Topic namespace : `spBv1.0/<group_id>/DB/<machine_id>/<asset_id>/<channel>/<metric_name>`.
   - Protobuf payload typé (Float, Int, Boolean, String).
   - Birth certificate au démarrage, Death certificate à l'arrêt.
   - Reprise après déconnexion (re-publication des dernières valeurs).

2. **Consumer Sparkplug B** : s'abonner aux EoN d'autres sites (si on opère en mode multi-tenant ou en mode "consortium" où plusieurs sites remontent à un hub).

3. **MQTT broker** : HiveMQ ou EMQX self-hosted, ou AWS IoT Core / Azure IoT Hub si cloud-managed.

**Pourquoi Sparkplug B et pas MQTT nu :**
- Topic namespace standardisé (au lieu de se mettre d'accord topic-par-topic).
- Birth/Death certificates (l'équivalent industriel du "device online/offline").
- Protobuf typé (au lieu de JSON "wild west").
- C'est l'ossature de l'**Unified Namespace (UNS)** qui est devenue la référence 2024-2026 en architecture IIoT.

**Coût d'implémentation :** ~1 semaine (bibliothèques Python Sparkplug B matures : `sparkplug-b-payload` pour la sérialisation, `paho-mqtt` pour le transport, ou stack Eclipse Tahu complète).

### 4.5 Phase T+4 — Edge AI (optionnelle)

**Déclencheur :** besoin de calcul embarqué (edge), latence < 1 s sur site, ou volonté d'argumenter l'angle "edge-deployable" (cf. `docs/theorie_reference.md` §5).

**Ajouts :**
- Quantification d'un modèle GBM (scikit-learn → ONNX → TensorRT/ONNX Runtime).
- Export ONNX du modèle + script d'inférence embarqué (Raspberry Pi, NVIDIA Jetson, ou IFM edgeGateway si supporté).
- Boucle de feedback : remontée des features et prédictions vers le cloud, réentraînement batch périodique.

**Note :** c'est le prolongement naturel de l'argument "features physiques > CNN" du brief §9. Un GBM sur features physiques tient en quelques Mo et tourne sur CPU, un CNN 1D nécessite généralement GPU. Argument commercial fort pour la distribution B2B (coût de calcul, pas seulement coût de capteur).

## 5. Décisions et pièges à anticiper

### 5.1 Décisions à prendre par Patrice

1. **Quel(s) protocole(s) terrain supporter en premier ?**
   - Hypothèse par défaut : OPC-UA (le plus universel côté IT, déjà chez Schaeffler), MQTT/Sparkplug B (le plus moderne côté UNS), Modbus (l'ubiquitaire côté variateurs).
   - Alternative : un seul protocole d'abord (OPC-UA, le plus expressif) puis MQTT à T+3.
   - À trancher quand T+1 est activé.

2. **Broker MQTT : self-hosted ou cloud-managed ?**
   - HiveMQ / EMQX self-hosted : contrôle total, mais opération (mise à jour, monitoring, backup).
   - AWS IoT Core / Azure IoT Hub : zéro opération, mais vendor lock-in et coût à l'usage.
   - Hypothèse par défaut : EMQX self-hosted (Docker Compose déjà en place, ajout d'un service).

3. **Faut-il viser AAS dès T+2 ou plus tard ?**
   - Si positionnement "vitrine Industrie 4.0" → AAS dès T+2.
   - Si positionnement "utilitaire portfolio" → AAS plus tard, éventuellement jamais.

### 5.2 Pièges à éviter

1. **MQTT nu sans Sparkplug B = far west des topics.** On a vu des projets où chaque client invente son namespace, et plus personne ne s'y retrouve après 6 mois. Sparkplug B (ou un namespace maison très strict) est non négociable dès qu'on a plus de 2 producteurs.

2. **OPC-UA Client/Server quand Pub/Sub suffirait.** Pour de la simple télémétrie, OPC-UA Pub/Sub over MQTT est plus simple qu'OPC-UA Client/Server. Inversement, si on doit naviguer dans un modèle d'information riche (Companion Specs), Client/Server est plus expressif. Choisir selon le cas.

3. **Kafka quand MQTT suffit.** Kafka est conçu pour des millions d'events/s avec relecture. Pour quelques centaines de capteurs à 1 Hz, c'est surdimensionné. MQTT broker (HiveMQ/EMQX) gère 100K+ msg/s sur modeste hardware.

4. **Kubernetes quand Docker Compose suffit.** Cf. `docs/scaling_path.md` : K8s ne se justifie qu'à T+1 si on a plusieurs services à redémarrer indépendamment. Pour un seul service d'ingestion + un dashboard, Docker Compose + restart policy suffit.

5. **Modbus sans cryptographie.** Modbus TCP n'a aucune sécurité native. À n'utiliser que sur réseau isolé (OT), jamais exposé à l'IT. Si on doit traverser une frontière, mettre un convertisseur Modbus→MQTT dans une DMZ.

6. **IO-Link BLOB brut en continu.** Le BLOB 4 s synchrone d'IFM VVB est volumineux (~24 ko par trame). En polling 1 Hz sur 100 capteurs = 200 Mo/jour. Acceptable mais à anticiper dans le dimensionnement stockage. Le pattern habituel : BLOB à la demande (alarme ou inspection manuelle), features calculées en continu.

7. **AAS submodels maison au lieu de standards.** Le submodèle "ConditionMonitoring" existe (spec ZVEI / Plattform Industrie 4.0). Inutile d'en inventer un. Pareil pour "Nameplate", "MaintenanceSchedule", "CapabilityDescription" — tous sont déjà spécifiés.

### 5.3 Ce qu'on ne fait PAS

- **OPC-UA Client lourd avec navigation dans un serveur Siemens S7-1500 entier.** Le projet n'est pas un client HMI/SCADA, il consomme un sous-ensemble de variables, pas l'intégralité du modèle automate.
- **MQTT broker haute disponibilité multi-cluster.** Pour quelques centaines de capteurs, EMQX single-node avec restart policy suffit. Le HA multi-cluster est un projet à part entière.
- **Sparkplug B version 3.0 (nouveauté 2024) tant qu'elle n'est pas stabilisée.** Rester sur Sparkplug B v2.2 tant qu'on a pas de besoin explicite.
- **Time-series database alternative à TimescaleDB** (InfluxDB, QuestDB, Timescale). Le projet a fait ce choix, le coût de migration est élevé pour un gain marginal. Voir `docs/scaling_path.md` §"ce qui ne changerait pas".

## 6. Synthèse — ce qui change quand, et pourquoi

| Phase | Déclencheur | Ajouts projet | Coût | Bénéfice |
|---|---|---|---|---|
| T0 (actuel) | — | Aucun | — | Pipeline batch Paderborn fonctionnel, Phase 3 prête à lancer |
| T+1 | Ingestion continue depuis un client / démo | Connecteurs OPC-UA, MQTT, Modbus ; export JSON structuré | ~3-4 semaines | Compatibilité avec écosystème Schaeffler / IFM / Siemens / variateurs standard |
| T+2 | Volonté Industrie 4.0 / vitrine | Sérialisation AAS, submodèle ConditionMonitoring | ~1-2 semaines | Positionnement "digital twin standard", interop avec écosystème AAS |
| T+3 | Multi-sites / parc hétérogène | Producteur/Consumer Sparkplug B, broker EMQX | ~1-2 semaines | Architecture UNS, namespace standardisé, multi-fleet |
| T+4 | Edge AI / latence < 1 s | Modèle ONNX, inférence embarquée | ~2-3 semaines | Argument "edge-deployable" cohérent avec features physiques |

**Recommandation implicite :** T+1 et T+3 sont les deux phases les plus alignées avec la valeur métier du projet (vraies machines, vraies données, vrais capteurs). T+2 est un plus vitrine mais à coût modéré. T+4 est optionnel et ne se justifie que si Patrice vise explicitement le marché edge.

## 7. Sources

- IFM edgeGateway product page, IFM moneo API docs, VVB306 datasheet
- Schaeffler customer story Vietnam, Predictive Maintenance 4.0 brochure
- SKF Axios Data Export Schema Rev B
- Augury product pages, MfgTechReview "Features, Scored"
- IBM Maximo REST API, IFACE tables
- Wikipedia et Phoenix Contact sur AAS / IEC 63278-1
- EMQX "OPC-UA, Modbus, MQTT, Sparkplug, HTTP efficiency comparison"
- iotsnacks, powerfabric, cyntech, amotus, azymuth sur protocoles IIoT (cf. §2 du document)
- IO-Link Consortium / IEC 61131-9
- Eclipse Foundation / Sparkplug B spec (Tahu project)
- OPC Foundation / IEC 62541 series

## 8. Annexe — tableau de compatibilité croisée (protocoles × phases)

| Protocole | T0 | T+1 | T+2 | T+3 | T+4 |
|---|---|---|---|---|---|
| Lecture parquet / .mat | ✅ (entrant) | ✅ | ✅ | ✅ | ✅ |
| Écriture parquet | ✅ (sortant) | ✅ | ✅ | ✅ | ✅ |
| PostgreSQL / TimescaleDB | ✅ | ✅ | ✅ | ✅ | ✅ |
| OPC-UA Client | — | ✅ (entrant) | ✅ | ✅ | ✅ |
| OPC-UA Pub/Sub | — | option | option | option | option |
| MQTT Consumer | — | ✅ (entrant) | ✅ | ✅ | ✅ |
| MQTT + Sparkplug B | — | option | option | ✅ (north-bound) | ✅ |
| Modbus TCP poller | — | ✅ (entrant) | ✅ | ✅ | ✅ |
| IO-Link BLOB reader | — | option | option | option | option |
| REST API JSON | — | ✅ (sortant) | ✅ | ✅ | ✅ |
| AASX / AAS REST | — | — | ✅ (sortant) | option | option |
| ONNX edge inference | — | — | — | — | ✅ |
| MLflow tracking | ✅ | ✅ | ✅ | ✅ | ✅ |
| Streamlit dashboard | ✅ | ✅ | ✅ | ✅ | ✅ |
