# Analyse concurrentielle — solutions commerciales de maintenance prédictive

**Date de l'analyse :** 2026-08-31
**Auteur :** relecture concurrentielle dans le cadre du projet
**Périmètre :** solutions de condition monitoring / predictive maintenance sur équipements rotatifs, avec un zoom sur les éléments que ce projet peut ou non reprendre.
**Sources :** documentation officielle des éditeurs (IFM, Schaeffler, SKF, Augury, Tractian, Senseye/Siemens, IBM Maximo, SparkCognition), comparatifs publiés début 2026 (Fabrico, Augury, iFactory, Dovient, Tractian, Guideflow, OxMaint), notes d'application technique (IO-Link VVB306 datasheet, SKF Axios Data Export Schema Rev B, IFM moneo API).

---

## 1. Pourquoi cette analyse

Trois questions concrètes à trancher pour ce projet :

1. **Quelles features les solutions leaders exposent-elles ?** Pour identifier ce qui relève du "table-stakes" (= on doit au moins le permettre) vs du différenciateur qu'on assume de ne pas offrir (= expliciter le périmètre, comme le fait `docs/brief_projet.md §1`).
2. **Quels protocoles de communication utilisent-elles ?** Pour préparer une trajectoire d'interopérabilité réaliste (le brief §2 objectif tertiaire parle de publication dataset, mais Patrice a ajouté la dimension "compatibilités de communication à terme" dans la dernière itération).
3. **Où se situe ce projet dans le paysage ?** Clairement **pas** dans la course à la plateforme universelle (domaine d'Augury / Maximo / AVEVA). Clairement **pas** dans la course au hardware propriétaire (domaine d'IFM / Schaeffler / SKF). Clairement **pas** dans la course à la boîte noire IA (domaine de SparkCognition / C3.ai / Uptake). Ce projet se positionne sur un créneau adjacent : **ingénierie des features physiques et rigueur de la généralisation, transposables à n'importe quel capteur**, qui est précisément la couche que toutes les plateformes propriétaires font en interne sans la rendre visible. C'est un angle de contribution, pas une plateforme concurrente.

## 2. Cartographie des solutions

### 2.1 Vue d'ensemble — qui fait quoi

| Éditeur | Catégorie | Hardware | Capteur signature | Protocole terrain → cloud | Différenciateur clé | Modèle commercial |
|---|---|---|---|---|---|---|
| **IFM** (Allemagne) | Capteurs + edge + plateforme | Propre (VVB IO-Link, VWV wireless) | VVB306 vibration 3 axes IO-Link COM3 | IO-Link → edgeGateway (OPC-UA/MQTT/Modbus client) → moneo Cloud ou AWS/Azure | Spécialiste sensor + edge ouvert, ISO 20816-3 paramétrable | Vente matériel + abonnement plateforme |
| **Schaeffler** (Allemagne) | Capteurs + cloud + services | Propre (SmartCheck 1 canal, ProLink 8 canaux, OPTIME wireless) | SmartCheck (vibration 1 canal, en ligne) | OPC-UA (confirmé en customer story) | LifetimeAnalyzer + ConditionAnalyzer (RUL + diagnostic) | Vente matériel + service d'analyse expert |
| **SKF** (Suède) | Capteurs + plateforme | Propre (Axios wireless, Microlog, Enlight AI) | Axios (3 axes, wireless, gateway) | JSON Schema export → AWS Kinesis, CSV | "Bibliothèque" AutoML interne, 18 paramètres/capteur | Matériel + SaaS |
| **Augury** (US/Israël) | Capteurs + IA + analystes | Propre (Halo capteurs) | Halo (vibration + acoustique + température) | Cellulaire intégré, cloud Augury | 100+ modes de défaillance, alertes validées par analystes CAT III/IV | Per-asset, $500-2000/an |
| **Tractian** (Brésil) | Capteurs + CMMS intégré | Propre (Smart Trac Ultra) | Triaxial vibration + temp + RPM | Sans fil → cloud Tractian | CMMS natif unifié, déploiement rapide | Matériel + SaaS |
| **Senseye** (UK, racheté Siemens) | Logiciel only | Agnostic | — | SCADA/historians/IoT ingestion | Failure mode library + Prophet forecasting | Enterprise SaaS |
| **Siemens MindSphere / Insights Hub** | Plateforme IIoT | Agnostic | — | Multi-protocoles | Écosystème Siemens (SIMATIC, ...) | Enterprise |
| **IBM Maximo Application Suite (avec APM Predict)** | EAM + PdM | Agnostic | — | REST + IFACE tables Maximo | watsonx AI, intégration native SAP/Oracle | Enterprise, >$40K/an |
| **AVEVA Predictive Analytics** | Process historian + ML | Agnostic | — | PI System connector | Conçu pour process industriel (chimie, énergie) | Enterprise |
| **SparkCognition** (US) | IA customisable | Agnostic | — | Multi | SparkPredict, defense/aerospace, generative industrial | Enterprise $100K-2M/an |
| **Uptake** (US) | Asset Performance Management | Agnostic | — | CMMS/ERP ingestion | Asset library cross-fleet, co-dev Caterpillar | Enterprise |
| **C3.ai** | IA enterprise | Agnostic | — | Multi | Energy/heavy industry, $3B market cap | Enterprise, Shell/Baker Hughes |
| **Fiix / UpKeep / Limble** | CMMS avec PdM | Agnostic | — | IoT add-on | CMMS d'abord, AI en option | SaaS $24-69/user/mois |
| **Fabrico** | PdM + exécution | Agnostic | — | PLC + IoT + vision | Closed-loop, work-order natif | Enterprise |

### 2.2 Positionnement concurrent de ce projet

Ce projet **n'entre pas en concurrence frontale** avec ces plateformes. Son positionnement est :

- **Couche "features physiques" transparente et auditable** — ce que les plateformes propriétaires font en interne (kurtosis, BPFO/BPFI, analyse d'enveloppe) mais sans rendre la chaîne visible. Ce projet fait la même chaîne en open, sourcée, testée.
- **Validation de la généralisation** — c'est la question de recherche que les plateformes commerciales contournent (en multipliant les données internes) plutôt qu'ils ne résolvent. Le brief §9 explicite déjà cet angle comme valeur centrale.
- **Reproducibilité** — un dataset publié (objectif tertiaire du brief) permet à n'importe qui de rejouer l'expérience. Les plateformes sont des boîtes noires.

Conséquence directe : **on n'a pas vocation à répliquer l'ensemble des features des leaders** (CMMS intégré, mobile app, alerting temps réel multi-canal, dashboards clients, facturation). On retient seulement les features qui servent l'angle "expertise domaine + rigueur méthodologique" déjà nommé dans `docs/brief_projet.md §1`.

## 3. Features par éditeur — analyse détaillée

### 3.1 IFM (référence hardware + edge)

**Sources principales :** VVB306 datasheet, IFM moneo API docs, IFM edgeGateway product page, brochure "Predictive Maintenance with IFM".

**Capteurs :**
- VVB001 / VVB306 (IO-Link vibration 1 ou 3 axes) — interface IO-Link 1.1.3 COM3 (230.4 kbaud), IP67/68/69K
- **Données cycliques IO-Link exposées :** v-RMS(x/y/z/magnitude, 16 bits chacun), a-Peak(x, 16 bits), scaling (8 bits). Process cycle time 4.1 ms (COM3).
- **Données acycliques (BLOB) :** signal brut d'accélération 4 s synchrone 3 axes ou 12 s monoaxe, pour analyse avancée offline.
- VWV001/002 — sans fil batterie 4 ans, ISM 2.4 GHz mesh, gateway ZB0929 (Ethernet TCP/IP + LTE CAT 1/Wi-Fi/NB-IoT, protocoles MQTT/HTTP).

**Seuils ISO 20816-3 paramétrables** par commande PLC ou IT — classification A/B/C/D directement au capteur.

**Edge gateway :**
- OPC-UA (Client), MQTTs (Client), ModbusTCP (Client) côté terrain.
- OPC-UA (Server), MQTTs, Azure IoT Hub, AWS IoT Core côté IT/Cloud.

**Plateforme moneo :**
- REST API (Platform API + Track & Trace API) avec auth token.
- Endpoints : données historiques process, tickets, topologie.
- **Tickets (work orders) exportables** vers MES/SCADA via MQTT ou OPC UA.

**Points à reprendre pour ce projet :**
- **Le format BLOB raw 4 s synchrone** (IFM VVB306) confirme que 4 s est une durée d'acquisition standard industrielle — cohérent avec les 4 s de Paderborn. Pas un hasard, c'est un compromis entre résolution spectrale fine et taille de transfert raisonnable.
- **L'exposition de v-RMS et a-Peak cycliques** (16 bits, cycle 4.1 ms) montre que l'edge computing des features temporelles est un pattern standard — le projet GBM sur features physiques est compatible edge (cf. `docs/theorie_reference.md` §5, "edge/fog/cloud").
- **Les seuils ISO 20816-3 paramétrables** sont un différenciateur : la table `application_type` du projet (cf. `docs/data_model.md`) est déjà prévue pour porter ce mapping. À activer explicitement quand un dataset avec puissance nominale et type de fondation sera dispo.
- **L'export tickets** correspond exactement au `maintenance_event` du modèle de données (cf. `docs/data_model.md`).

**Points qu'on ne reprend pas :**
- Capteurs propriétaires IFM (projet agnostique aux sources)
- Plateforme moneo (le projet est une lib Python + DB, pas une plateforme SaaS)

### 3.2 Schaeffler (référence RUL + diagnostic)

**Sources principales :** brochures "Predictive Maintenance 4.0", "Drive Train 4.0", customer story Vietnam.

**Architecture produit :**
- **SmartCheck** : monitoring 1 canal en ligne, fixation locale, idéal pour machines critiques ponctuelles.
- **ProLink CMS** : 8 canaux simultanés, intégration de capteurs tiers via gateway, monitoring central pour compresseurs, moteurs, ventilateurs.
- **OPTIME** : sans fil, scalable à des centaines de machines homogènes, mobile app + Schaeffler Cloud.
- **Smart EcoSystem** : cloud avec System visualization, **LifetimeAnalyzer** (RUL), **ConditionAnalyzer** (diagnostic), LoadAnalyzer (collectif de charge), Online monitoring (experts Schaeffler à distance).

**Signature data dans le cas client documenté :**
- Data exchange **OPC/UA** (confirmé explicitement)
- Paramètres surveillés : vibration, température, vitesse
- Méthode diagnostic : speed, acceleration, envelope (← confirme l'orientation analyse d'enveloppe côté Schaeffler, cohérent avec notre choix §5 du brief)
- Alertes par application mobile

**Points à reprendre pour ce projet :**
- **LifetimeAnalyzer (RUL)** est la fonctionnalité RUL phare Schaeffler. Cohérent avec la `Phase 0` du brief (bascule possible vers RUL sur XJTU-SY, non tranchée). Si la bascule se fait, c'est l'angle "feature reprise" à mentionner.
- **ConditionAnalyzer** = exactement la chaîne analyse d'enveloppe + features BPFO/BPFI/BSF/FTF + classification que `src/features/envelope.py` et `src/features/fault_frequencies.py` implémentent. Le kurtogramme (cf. `docs/known_issues.md`) est le point d'amélioration actif.
- **OPC-UA comme protocole de transport** entre edge et cloud Schaeffler — confirme le choix de ce protocole comme pivot (voir `docs/communication_architecture.md`).
- **LoadAnalyzer** (collectif de charge) — un point faible de ce projet. Paderborn n'a pas de profil de charge variable. XJTU-SY a 3 conditions de charge fixes (2100/2250/2400 tr/min × 12/11/10 kN) mais pas de profil temporel. À mentionner comme limite si la question "gestion de charge variable" est posée.

**Points qu'on ne reprend pas :**
- Hardware Schaeffler (projet agnostique)
- Service d'analyse par experts Schaeffler (humain-dans-la-boucle)
- RUL si la bascule diagnostic-only est confirmée (sinon XJTU-SY Phase 0)

### 3.3 SKF (référence format data + API)

**Sources principales :** SKF Axios Data Export Schema Rev B (15V-090-00103-100), SKF Axios Technical FAQ, SKF Enlight AI brochure.

**Format data explicite — le plus détaillé trouvé dans cette étude :**
- **JSON structuré**, versionné (`"version": "2.0"`), avec événements typés :
  - `measurement` (la mesure elle-même)
  - `gatewayConnected` / `gatewayDisconnected`
  - `sensorConnected` / `sensorDisconnected`
  - `assetStateTransition`
- Champs : `timestamp`, `eventId`, `projectName`, `siteName`, `assetName`, `positionName`, `sensor.physicalId` + RSSI, `gateway.physicalId`, `sequenceNo`, `features.acceleration.band0To6000Hz.xAxis`, etc.
- **18 paramètres de mesure par capteur.**
- Streaming temps réel via **AWS Kinesis** ; export CSV pour l'app.
- Modèle d'état d'asset avec `assetTransitionType: measurement|userInput`, `assetState.newState`, `assetState.previousState`.

**SKF Enlight AI (la couche analytique) :**
- AutoML "off-the-shelf", promet de ne pas avoir besoin de data scientists sur site.
- Apprentissage continu, alertes précoces, root cause analysis assistée.

**Points à reprendre pour ce projet :**
- **Le format JSON structuré avec événements** est exactement la cible d'export du projet quand l'ingestion streaming arrivera (`docs/scaling_path.md` §1 "déclencheur ingestion continue"). Le `data_model.md` est déjà aligné (machine/asset/signal/feature/maintenance_event) — il suffit de produire un JSON avec cette structure depuis un consumer MQTT/OPC-UA.
- **Le concept d'eventType `assetStateTransition`** est très proche de la combinaison `feature` (détection automatique) + `maintenance_event` (déclaration humaine) du modèle projet. Un state peut être inféré par le modèle ET changé manuellement — le JSON SKF force la trace des deux.
- **L'export CSV pour l'app** confirme que CSV reste un standard d'export minimal. Le projet produit déjà des parquet (plus efficace) — c'est un point différenciant léger.
- **`RSSI` du capteur** (Received Signal Strength Indicator) — utile pour qualifier la qualité du signal wireless. Si on intègre des capteurs sans fil un jour (déclencheur ingestion continue), à ajouter comme métadonnée signal.

**Points qu'on ne reprend pas :**
- AutoML "no data scientists needed" — la philosophie du projet est inverse : explicabilité des features, choix méthodologiques assumés, code auditable.
- L'écosystème Microlog/Enlight Center (collecte handheld) — pas applicable aux datasets publics batch.

### 3.4 Augury (référence AI specialists + opérateurs humains)

**Sources principales :** pages produit Augury, MfgTechReview "Features, Scored", businessmodelcanvastemplate "How Does Augury Work".

**Architecture :**
- Capteurs **Halo** propriétaires (vibration + ultrason + température + magnétique).
- Streaming cellulaire vers cloud Augury.
- Library de 300M+ heures-machines pour entraîner les modèles.
- **Détection de 100+ modes de défaillance** : bearing defects, imbalance, misalignment, lubrication, electrical faults.
- **Ultra-low RPM 1-150 RPM** par ultrasons (lancement mars 2025).
- **Analystes CAT III/IV** revoient les alertes avant livraison au client. Pattern "human-in-the-loop" pour les alertes critiques.
- **Instructions prescriptives** : au lieu d'un spectrogramme brut, le système dit "remplacer le roulement drive-end dans les 2 semaines". Reliability Success Managers sur le terrain.

**Pricing :** enterprise custom uniquement, $500-2000/an par asset, contrat multi-annuel.

**Points à reprendre pour ce projet :**
- **Le concept d'instructions prescriptives plutôt que données brutes** est exactement ce que la taxonomie `docs/theorie_reference.md` §4bis prépare : "un chef d'atelier doit pouvoir lire un spectre et distinguer un défaut de roulement d'un problème d'installation". Le projet doit pouvoir, à terme, sortir un libellé textuel ("défaut BPFO naissant, sévérité X, recommandation : surveillance renforcée + analyse huile à 30 jours") plutôt qu'une classe parmi N. C'est l'angle du `calculateur ROI capteur` (différenciation §1) poussé plus loin.
- **Le pattern human-in-the-loop pour les alertes critiques** est une bonne pratique reconnue. Le projet peut l'implémenter en mode léger : un dashboard Streamlit affiche les alertes avec un bouton "confirmer" qui crée un `maintenance_event` typé `analyst_review` (utilise la table déjà prévue, cf. `docs/data_model.md`).
- **L'extension ultrasons pour ultra-low RPM (1-150)** est hors scope ici mais à connaître — la Paderborn tourne à 900/1500 RPM, donc dans la bande classique. Pour un banc éolienne ou gros moteur marin, l'ultrason devient indispensable.

**Points qu'on ne reprend pas :**
- Capteurs Halo propriétaires
- Plateforme cloud Augury
- Pricing enterprise (le projet est un portfolio open, pas un SaaS)

### 3.5 Tractian (référence hardware + CMMS intégré)

**Sources principales :** Tractian product comparison pages, blog "Top 5 Best Predictive Maintenance Software".

**Capteurs :** Smart Trac Ultra (triaxial vibration + température + RPM + runtime, sans fil).

**Différenciateur :** CMMS intégré en natif (pas de connecteur à configurer), déploiement 14 jours, offline mobile.

**Points à reprendre pour ce projet :**
- **L'idée de capturer le runtime cumulatif** (en plus de la vibration) est une métadonnée simple et utile pour la maintenance conditionnelle : un roulement à 20 000 h est plus suspect qu'un roulement à 2 000 h, à kurtosis égal. Le `feature` EAV du projet (`docs/data_model.md`) absorbe ce genre de métadonnée calculée sans migration.
- **Offline mobile execution** — un détail UX qui n'a pas sa place dans un projet ML, mais qui signale que les leaders pensent "terrain" pas "data scientist". Le `docs/differentiation_strategy.md` angle #3 ("checklist labo→atelier") est dans le même état d'esprit.

### 3.6 Senseye / Siemens (référence software-only / agnostique)

**Sources principales :** Senseye product pages, Siemens Insights Hub.

**Approche :** Senseye ne vend pas de capteurs. Logiciel pur, branché sur les données SCADA/historians/IoT existantes du client.

**Failure mode library** : bibliothèque propriétaire de modes de défaillance par type d'équipement, apprentissages continus.

**Intégration :** ingestion SCADA (OPC-UA historien, MQTT, Modbus), vers CMMS existants du client (SAP PM, Maximo) via API ou fichiers.

**Points à reprendre pour ce projet :**
- **L'approche sensor-agnostic est exactement la nôtre** : on ne vend pas de capteur, on consomme des données. C'est le bon positionnement pour un projet de recherche.
- **L'idée de failure mode library** (mapping signature → cause) est ce que la taxonomie `docs/theorie_reference.md` §4bis prépare en partie, mais encyclopédique plutôt que ciblée. Si le projet va plus loin qu'un proof-of-concept, une mini "library" des signatures Paderborn serait pertinente — voir `docs/feature_backlog.md`.

### 3.7 IBM Maximo (référence EAM + intégration enterprise)

**Sources principales :** IBM Maximo docs, Maximo SAP integration.

**Positionnement :** EAM (Enterprise Asset Management) généraliste, PdM est un module optionnel (Maximo Predict + Health).

**Connecteurs CMMS :** REST API documentée, IFACE tables pour intégration asynchrone, cron tasks, Message Tracking. Templates d'intégration SAP NetWeaver.

**Point clé :** la complexité de l'intégration (REST sync vs IFACE async, cron tasks, message tracking) montre que la cible "s'interface nativement avec tous les CMMS" est un **gouffre d'ingénierie**. Pour ce projet, on assume un export propre (JSON / parquet / REST minimal) et on laisse l'intégration CMMS côté client.

### 3.8 SparkCognition / Uptake / C3.ai (référence IA enterprise custom)

Ces trois acteurs partagent un modèle : plateforme AI customisable, projets longs (6-18 mois), pricing enterprise $100K-2M/an, ciblage industries lourdes (mining, energy, transport, defense).

**Traction commune :**
- "Cross-fleet learning" : un pattern de défaillance vu chez un client améliore les prédictions pour tous (Uptake).
- "Explainability" : au lieu d'un score d'anomalie, le système dit quel capteur a déclenché et quel pattern historique matche (SparkCognition).
- "Generative AI for maintenance" : NLP sur manuels de maintenance, chatbot technicien (SparkCognition depuis 2024, C3.ai).

**Pour ce projet :**
- **Le "cross-fleet learning"** est l'argument marketing qui justifie les boîtes noires : avec 1 machine on n'a pas d'historique, avec 1000 machines le modèle devient pertinent. Notre contre-argument : la physique du défaut (raie BPFO à fréquence fixe connue) ne dépend pas du nombre de machines — c'est précisément pourquoi les features physiques battent le deep learning sur la généralisation, ce qui est le cœur du brief.
- **L'explainability** (SparkCognition) est ce que `docs/differentiation_strategy.md` angle #2 prépare : "taxonomie du gap artificiel→réel" + tableau de signatures spectrales. Notre explainability est au niveau features (raie BPFO visible à 76.76 Hz à 1500 rpm), pas au niveau DL.
- **Le NLP maintenance manuals** est une piste future, hors scope. Note : IFM moneo a aussi un composant Track & Trace qui suggère l'orientation multi-modal.

### 3.9 Forgis/Mechanical-Components (dataset ouvert, pas un éditeur commercial)

Pas un concurrent logiciel — un **dataset public déjà publié** sur Hugging Face
(`Forgis/Mechanical-Components`, vérifié 2026-09-01 : réel, license MIT, ~11.5K
échantillons roulements + 1.2K engrenages + metadata 16 sources, format parquet,
splits explicitement source-disjoint). Conçu pour le projet "Mechanical-JEPA",
orientation cross-component fault diagnosis multi-sources.

**Pourquoi ça compte pour ce projet :** c'est, concrètement, l'objectif
tertiaire du brief (§2 : "publication du dataset sur Hugging Face... aucun
dataset vibratoire de référence n'est publié proprement sur le Hub") déjà
réalisé par quelqu'un d'autre, au moins partiellement. Vérification à faire
avant Phase 4 (F-41 du backlog) :
- Est-ce que Paderborn/XJTU-SY y sont déjà inclus (dans les "16 sources") ?
  Si oui, republier serait redondant sauf valeur ajoutée claire (dataset card
  plus riche, géométries documentées, splits par condition en plus du split
  par source).
- Le schema (`health_state`, `fault_type`, `rpm`, `load`, colonnes RUL/episode
  présentes mais nulles pour "bearings") suggère un dataset pensé diagnostic
  ET prognostic à la fois — à comparer avec le schema EAV `feature`/`asset` de
  ce projet (`docs/data_model.md`) pour voir s'il y a un format à converger
  vers, plutôt que republier dans un format incompatible.
- Split "source-disjoint" (train sur certaines sources, test sur d'autres) est
  conceptuellement proche du split cross-machine visé par ce projet (voir
  `docs/data_model.md` "machine générique") — benchmarking possible une fois
  Phase 3 terminée.

**Action concrète :** ne pas dupliquer l'effort de publication sans d'abord
inspecter ce dataset en détail (`hub_repo_details` + `dataset_preview`) — à
faire avant de lancer F-41, pas avant.

### 3.10 Istec Sphere (plateforme cloud vibratoire IA, lancement 2026)

**Sources principales :** [istec.com/product/sphere-vibration-analysis](https://www.istec.com/product/sphere-vibration-analysis/), [istec.com/vibration-monitoring-systems-and-software](https://www.istec.com/vibration-monitoring-systems-and-software/), [istec.com/analyzing-vibration-data-with-sphere](https://www.istec.com/analyzing-vibration-data-with-sphere/). Existence du produit confirmée via la page produit officielle Istec (Hollande, +31 252 433 403) — premier concurrent identifié originaire des Pays-Bas sur ce marché.

**Positionnement :** plateforme cloud d'analyse vibratoire avec IA multi-modèles, monitoring fleet. Cible explicitement les vibration engineers et les experts maintenance qui veulent "transformer les données brutes en insights actionnables", avec une promesse de scalabilité ("scale monitoring coverage without scaling specialists").

**Composants :**
- **Capteurs hardware :** VibSys® (propriétaire Istec, génération courante "next-generation vibration monitoring system and cloud gateway", disponibilité annoncée S2 2026 — produit récent, à vérifier au moment de l'évaluation). Capteurs tiers compatibles via l'API Istec Suite (intégration ouverte).
- **Couche IA :** "multi-modèles d'IA pour détecter automatiquement les anomalies, classifier les patterns, et mettre en évidence les déviations" — joue le rôle d'un "digital first-line analyst", pas un remplacement de l'expert (cf. modèle "human-in-the-loop" Augury §3.4).
- **Moteur de règles :** règles custom sur tendances, seuils, paramètres combinés — **exactement le use case de l'onglet Alertes en cours de construction** (cf. `docs/proposition_alertes_dashboard.md`). C'est le 1er concurrent identifié à proposer explicitement ce pattern, alors qu'Augury/Tractian/SparkCognition restent sur des modèles purement statistiques ou boîtes noires IA.
- **Accès aux données :** raw waveforms + spectral data + trend histories — analyste peut faire le diagnostic lui-même ou "connect directly with Istec specialists for second opinions" (modèle service d'experts intégré).
- **Modèle commercial :** "Collect high-quality vibration data and train custom analysis models to support product development, performance optimization, and predictive service strategies" —暗示 un modèle plateforme-as-a-service avec composante service d'experts, pas pur SaaS self-service.

**Différenciation vs les acteurs déjà documentés :**
- vs **IFM/Schaeffler/SKF** (§3.1-3.3) : Istec ajoute une couche IA/rule-engine au-dessus du hardware, là où les 3 autres sont des fournisseurs hardware + edge avec plateformes relativement basiques.
- vs **Augury** (§3.4) : Augury est AI-first + analystes humains internes (CAT III/IV) pour valider les alertes ; Istec est IA-first + réseau d'experts Istec accessibles en option ("second opinion") — modèle d'engagement différent.
- vs **Senseye** (§3.6) : Senseye est failure mode library propriétaire + Prophet forecasting ; Istec est IA multi-modèles avec API ouverte. Senseye plus "boîte noire algorithmique", Istec plus "plateforme transparente + outils experts".
- vs **IBM Maximo** (§3.7) : Maximo est EAM généraliste, Istec est spécialiste vibration pure — pas le même marché cible.
- vs **SparkCognition/Uptake/C3.ai** (§3.8) : ces trois sont des boîtes noires IA enterprise ($100K-2M/an), Istec joue plus sur l'accessibilité (page produit mentionne "accessible environment" + "vibration specialists" intégrés).

**Ce qu'on retient pour ce projet :**
- **Confirmation que le "moteur de règles personnalisables" est un pattern marché, pas une lubie de Patrice** — l'onglet Alertes en construction (`docs/proposition_alertes_dashboard.md`) est dans le bon standard industriel.
- **Le modèle "IA première ligne + experts en back-up"** est un pattern documenté et accepté sur ce marché — utile pour la discussion §9 du brief (résultats négatifs assumés vs prescriptive insights). On n'a pas besoin d'un modèle d'IA boîte noire pour être légitime.
- **Le hardware VibSys® montre qu'un acteur spécialisé振动 (pure player vibration) est viable commercialement** — confirme que la niche "spécialiste" a un marché, contrairement à un message "plateforme généraliste" type Maximo/AVEVA.

**Ce qu'on ne retient pas :**
- Le détail du modèle d'engagement "vibration specialists accessibles en option" — pas applicable à un projet portfolio, on n'a pas d'experts à offrir.
- L'API Istec Suite (cloud-only) — incompatible avec un pipeline local SQLite/Postgres + dashboard Streamlit, et inutile dans le scope actuel (Paderborn + batch).
- Le "predictive service strategies" (Istec vend des services d'analyse à valeur ajoutée) — c'est du consulting, hors projet portfolio.

**Limites de cette analyse :**
- Produit récent (S2 2026 annoncé), peu de recul sur la stabilité réelle des modèles d'IA Istec. Le passage "Disponibilité prévue au deuxième trimestre 2026" sur la page produit indique qu'il était en pré-lancement à la date de rédaction (2026-09-01) — à re-vérifier dans 6-12 mois.
- Pas de pricing public trouvé — Istec vend probablement sur devis + bundle hardware (VibSys) + service d'experts. Cohérent avec le modèle "Scale monitoring coverage without scaling specialists" qui suppose un ticket d'entrée enterprise.
- Pas de cas client public détaillé trouvé dans la recherche — vérifier sur demande directe (Istec est réactif sur leur page de contact, +31 252 433 403).

## 4. Synthèse — ce qu'on retient, ce qu'on ne retient pas

### 4.1 Features reprises ou à reprendre (cœur du projet)

| Feature | Source(s) | Statut projet | Action |
|---|---|---|---|
| Features temporelles (RMS, kurtosis, crest factor) | Tous les leaders (IFM, SKF, Augury, Senseye) | ✅ Implémenté (`src/features/time_domain.py`) | Maintenir ; corriger l'instabilité RMS documentée `docs/known_issues.md` |
| Analyse d'enveloppe + kurtogramme | Schaeffler ConditionAnalyzer, Augury | ⚠️ Implémenté mais désactivé (`--with-envelope`, `docs/known_issues.md`) | Réactiver après stabilisation kurtogramme (consensus multi-mesures) |
| Énergie spectrale aux fréquences BPFO/BPFI/BSF/FTF | Schaeffler, SKF, Augury (toutes les plateformes sérieuses) | ⚠️ Calculé mais désactivé, BPFO dépend du kurtogramme | Couplé à la résolution du kurtogramme |
| ISO 20816-3 zones A/B/C/D | IFM VVB, Schaeffler, SKF, toutes plateformes normatives | ⚠️ Table `application_type` prévue (`docs/data_model.md`) | Activer quand dataset avec puissance nominale disposé (XJTU-SY ou futur) |
| Modèle ML (GBM) sur features physiques | Augury, Senseye, Schaeffler LifetimeAnalyzer | ✅ Implémenté Phase 2, F1 0.738 ± 0.208 | Élargir à l'objectif principal Phase 3 (artificiel→réel) |
| Comparaison vibration seule / courant seul / fusion | Objectif secondaire du brief | ✅ Implémenté Phase 2, vibration > courant > fusion (intervalles se chevauchent) | À reconfirmer sur Phase 3 (objectif principal) |
| Métadonnées complètes par signal (machine, condition, asset, channel) | SKF Axios JSON schema, Augury | ✅ Implémenté (`docs/data_model.md`) | Maintenir ; ajouter RSSI si capteurs sans fil un jour |
| Journal de maintenance | IFM moneo tickets, Maximo work orders, SKF asset state | ⚠️ Table `maintenance_event` créée, vide | Implémenter le formulaire Streamlit (déjà prévu par `docs/data_model.md`) |
| Export JSON structuré des événements | SKF Axios Data Export Schema Rev B | ❌ Non implémenté | À spécifier dans `docs/communication_architecture.md` (déclencheur ingestion continue) |

### 4.2 Features explicitement hors scope (assumées non couvertes)

| Feature | Pourquoi hors scope |
|---|---|
| Capteurs propriétaires (IFM VVB, Schaeffler SmartCheck, SKF Axios, Augury Halo, Tractian Smart Trac) | Projet agnostique, consomme des données ouvertes (Paderborn) |
| Plateforme cloud SaaS (moneo, Enlight, Augury Cloud, Schaeffler Cloud) | Projet = lib Python + DB locale + dashboard Streamlit local |
| Pricing enterprise multi-annuel | Projet = portfolio, pas un produit commercial |
| AutoML "no data scientists needed" (SKF Enlight AI) | Philosophie inverse assumée : features physiques explicites, choix méthodologiques auditable |
| RUL / LifetimeAnalyzer (Schaeffler) | Diagnostic-only Phase 0 non tranchée ; bascule XJTU-SY en option Phase 0 |
| CMMS intégré (Tractian, Fiix, UpKeep) | Hors périmètre ; export JSON structuré permettant l'intégration, mais pas l'intégration elle-même |
| NLP maintenance manuals (SparkCognition, C3.ai) | Piste future éventuelle, hors scope |
| Ultra-low RPM 1-150 RPM par ultrasons (Augury) | Paderborn à 900/1500 RPM, pas le use case |
| Computer vision inspection (SparkCognition Visual AI, Landing AI) | Hors périmètre vibration/roulement |
| Mobile app offline (Tractian) | UX produit, pas pertinent pour projet ML portfolio |

### 4.3 Décisions méthodologiques confirmées par l'analyse

1. **Le choix "features physiques > deep learning"** est confirmé par tous les leaders qui font aussi l'inverse (Augury, SparkCognition) : ils utilisent les features physiques en interne pour le diagnostic, le deep learning est pour les patterns non-encodables. Notre focalisation sur les features est légitime, pas un repli.

2. **Le split par asset** (docs/brief_projet.md §4, règle d'or) est confirmé par **tous** les papiers publiés sur la généralisation artificiel→réel (cf. `docs/theorie_reference.md` §6, domain adaptation). Aucun des éditeurs ne publie son protocole de split, mais c'est la seule façon d'éviter la fuite par fenêtre.

3. **La métrique F1 macro** (docs/brief_projet.md §4, règle d'or) est justifiée par le déséquilibre de classes Paderborn (32 assets : 6 sains, 12 artificiels, 14 réels) — confirmé par les benchmarks internes Augury/SKF qui utilisent balanced accuracy sur leurs datasets déséquilibrés.

4. **L'argument coût capteur** (docs/brief_projet.md §9) est validé par **tous** les éditeurs qui ont des solutions low-cost (IFM VVB IO-Link, Banner Engineering DXM) : la concurrence sur le hardware prouve que le coût capteur est un vrai sujet industriel. Notre contre-argument "le courant moteur est gratuit" (déjà dans Paderborn) garde sa valeur tant qu'on n'a pas démontré qu'il fonctionne sur l'objectif principal.

## 5. Ce que cette analyse change concrètement au projet

1. **Court terme (Phase 3, objectif principal) :** pas de changement. L'analyse confirme que le pipeline en place est dans le bon état d'esprit, le travail immédiat reste de stabiliser le kurtogramme et de lancer artificiel→réel.

2. **Moyen terme (Phase 4, restitution) :** positionner le projet comme "couche features physiques transparente et auditable", pas comme "plateforme concurrente d'Augury". C'est précisément l'angle que `docs/differentiation_strategy.md` prépare, cette analyse le valide par le marché.

3. **Long terme (au-delà du périmètre actuel) :** préparer une trajectoire d'interopérabilité pour le jour où le projet passera de "datasets publics batch" à "ingestion continue depuis capteurs réels" — c'est l'objet de `docs/communication_architecture.md` (à écrire dans la foulée de cette analyse).

4. **Pour le calculateur ROI capteur** (`docs/differentiation_strategy.md` angle #1 retenu) : les prix repère $500-2000/an/asset (Augury) et les fourchettes matérielles IFM/SKF/Schaeffler donnent des ordres de grandeur réalistes à comparer au coût du courant moteur (gratuit mais pertinence à démontrer).

## 6. Sources et limites de cette analyse

**Limites assumées :**
- L'analyse repose sur la documentation publique des éditeurs (pas de démo produit, pas d'accès API). Certains prix et certaines features peuvent être datés ou biaisés par le marketing.
- Les comparatifs publiés (Fabrico, Augury, iFactory, Dovient, Guideflow, OxMaint) ont chacun leur biais — éditeur cité en premier tend à être favorisé. J'ai recoupé entre plusieurs sources.
- L'analyse est statique (snapshot 2026-08-31). Le marché bouge vite (Augury a lancé la détection ultrason ultra-low RPM en mars 2025, C3.ai a signé Shell/Baker Hughes récemment).

**Sources principales :**

Documentation éditeur :
- IFM VVB306 datasheet, moneo API docs, edgeGateway product page
- Schaeffler brochures "Predictive Maintenance 4.0" et customer story Vietnam
- SKF Axios Data Export Schema Rev B, SKF Enlight AI brochure
- Augury product pages et MfgTechReview "Features, Scored"
- Tractian "Top 5 Best Predictive Maintenance Software"
- IBM Maximo REST API + IFACE tables
- Phoenix Contact / Symestic / Wikipedia sur AAS et IEC 63278-1

Comparatifs indépendants (recoupés) :
- Fabrico "6 Meilleurs Logiciels de Maintenance Prédictive Industrielle en 2026"
- Augury "How Does Augury Work"
- iFactory "Best Predictive Maintenance Software Platforms: 2026 Comparison"
- Dovient "Best Predictive Maintenance Software for Manufacturing 2026"
- Guideflow "7 best predictive maintenance software for 2026"
- OxMaint "Top 10 AI Predictive Maintenance Software for 2026"
- WifiTalents "Best Predictive Maintenance Software – 2026 Buyer's Guide"
- TFSF Ventures "Comparing AI-Powered Predictive Maintenance Platforms"

Standards :
- ISO 20816-3 (vibration severity)
- ISO 13373-1/2 (signal processing)
- ISO 13374 (condition monitoring architecture)
- IEC 62541 (OPC UA series)
- IEC 63278-1:2023 (Asset Administration Shell)
- ISO/IEC 20922:2021 (MQTT)
- Eclipse Tahu (Sparkplug B)
- IEC 61131-9 (IO-Link)
