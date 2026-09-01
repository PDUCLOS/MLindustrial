# Trajectoire d'evolution si le perimetre grandit

Ce document repond a une question legitime ("et si ca doit scaler ?") sans
provisionner d'infra inutilisee dans le repo. Decision explicite (voir
docs/brief_projet.md) : ce projet reste sur Docker Compose + TimescaleDB tant qu'il
traite des datasets publics en batch. Ray et Kubernetes ne sont PAS mis en
place maintenant - ce document dit precisement a quel declencheur ils le
seraient, et ce qui changerait concretement.

## Hypotheses actuelles (valables tant que le projet reste dans ce perimetre)

- Sources = datasets publics statiques (Paderborn, XJTU-SY, NASA IMS...),
  telecharges une fois, traites en batch.
- Volumetrie : dizaines de Go, run complet en minutes sur une seule machine
  (86s pour 2560 mesures Paderborn, cf. `scripts/build_dataset.py`).
- Un seul utilisateur/demo, pas de trafic concurrent, pas de SLA de latence.
- Pas d'ingestion continue - les capteurs ne "streament" pas vers ce systeme.

Sous ces hypotheses, Ray et Kubernetes n'apportent rien : leur cout
operationnel (config, debug, maintenance) depasserait tout gain de vitesse ou
de fiabilite mesurable.

## Declencheurs qui changeraient la donne

### 1. Ingestion continue depuis de vrais capteurs (pas des datasets figes)

**Declencheur :** le projet passe de "j'analyse des enregistrements
historiques" a "je recois des mesures en continu depuis des machines reelles".

**Ce qui change :**
- `scripts/build_dataset.py` (batch, un run puis termine) devient un service
  d'ingestion permanent (ex. consommateur MQTT/Kafka si les capteurs publient
  sur un bus, ou un poller qui interroge des automates/variateurs).
- La table `feature` (deja hypertable Timescale, deja pensee pour ca) absorbe
  le flux sans changement de schema - c'est precisement pourquoi ce choix a
  ete fait des le depart (voir `docs/data_model.md`).
- **Kubernetes devient pertinent ici** : plusieurs services independants
  (ingestion par source/site, extraction de features, alerting) qui doivent
  tourner en continu, redemarrer seuls en cas de crash, et scaler
  independamment selon le nombre de sites raccordes. Docker Compose ne fait
  pas de redemarrage automatique ni d'autoscaling multi-machine.

### 2. Volumetrie ou charge de calcul qui depasse une seule machine

**Declencheur :** des centaines de capteurs reels sur plusieurs sites, ou un
besoin de retraiter tout l'historique frequemment (ex. recalcul de features
apres amelioration du kurtogramme sur des millions de signaux).

**Ce qui change :**
- **Ray devient pertinent ici** : paralleliser l'extraction de features
  (`src/features/`) sur un cluster plutot qu'un seul process. Le code actuel
  (fonctions pures sur un `np.ndarray`) se parallelise directement avec
  `ray.remote` sans reecriture de la logique metier - seul l'orchestrateur de
  boucle change (`scripts/build_dataset.py` reste presque identique).
- Recherche d'hyperparametres (GBM, CNN 1D) a grande echelle : `Ray Tune`
  plutot qu'une recherche sequentielle locale.

### 3. Service de production avec exigence de disponibilite

**Declencheur :** le systeme doit repondre a des requetes (dashboard,
alerting) avec un SLA, potentiellement plusieurs utilisateurs/sites
concurrents.

**Ce qui change :**
- Le dashboard Streamlit (actuellement un seul container) migre vers un
  service avec plusieurs replicas derriere un load balancer.
- Un service de serving de modele dedie (ex. FastAPI, ou KServe/Seldon si
  deja sur Kubernetes) remplace le chargement direct du modele dans le
  dashboard.
- Alerting temps reel (webhook, email, SMS) comme service independant,
  consommant la meme hypertable `feature`.

## Ce qui NE changerait PAS

- Le schema DB (`machine -> test_session -> asset -> signal` + `feature` en
  EAV) reste valable a toutes les echelles - c'est deja concu pour absorber
  de nouveaux capteurs/sources sans migration (voir `docs/data_model.md`).
- TimescaleDB reste le moteur de stockage - il scale par partitionnement et
  supporte le clustering multi-noeud natif si necessaire, pas besoin de
  changer de base pour absorber la croissance de volumetrie seule.
- La logique metier (`src/features/`, `src/models/`) reste la meme : ce qui
  change avec Ray/Kubernetes, c'est l'orchestration autour, pas les calculs.

## Vision "a terme" capturee (2026-09-01, pas construite maintenant)

Patrice a evoque, en marge du factory-builder (voir `app/dashboard.py` onglet
"Mon usine", Site/Zone/Machine) :
- **Charger une usine existante** (import) - pas juste creer a la main.
- **Usine demo avec generation de donnees** - pour demontrer le produit sans
  attendre une vraie source branchee. **Contrainte "0 mock" du projet
  s'applique integralement** : toute donnee generee devrait etre etiquetee de
  facon impossible a confondre avec du reel (bandeau/watermark explicite dans
  l'UI, colonne `is_synthetic` ou equivalent en base si jamais persiste) - pas
  une simple note en petit caractere. A concevoir avec le meme niveau de
  rigueur que le reste du projet avant d'implementer quoi que ce soit, pas a
  bricoler rapidement.
- **Tous types de capteurs Industrie 4.0** - deja prepare cote architecture
  (`src/data/units.py` registre extensible), reste a enrichir au fur et a
  mesure des sources reelles ajoutees (voir Partie B de
  `docs/plan_bearing_catalog_and_ingestion.md`), pas a pre-remplir un
  catalogue exhaustif hypothetique.
- **Seuils automatiques par ML ou regle metier** - extension naturelle du
  pattern deja construit (`src/models/baseline.py` + onglet Alertes du
  dashboard, seuil ML entraine et logue en mlflow) a n'importe quel
  machine/capteur cree via le factory-builder, une fois qu'une vraie source
  de donnees existe dessus - pas de sens sans donnees reelles a entrainer.

**Statut : note pour la roadmap, pas une tache en cours.** Rien ici ne doit
etre construit avant que le factory-builder de base (creation Site/Zone/
Machine, sans donnees) soit valide et qu'une vraie source y soit branchee -
meme logique YAGNI que le reste du document.

## Reseaux d'utilites (electrique/pneumatique/eau) - capture 2026-09-01

Idee : modeliser aussi les reseaux de cablage/tuyauterie (electrique,
pneumatique, eau) reliant les machines entre elles, avec des filtres de
lecture par type de reseau (afficher/masquer une couche).

**Different du modele actuel par nature, pas juste par ampleur** : le
factory-builder actuel (Site -> Zone -> Machine -> Asset) est une hierarchie
de CONTENANT (une machine EST DANS une zone). Un reseau d'utilite est un GRAPHE
de CONNEXION (une machine EST ALIMENTEE PAR tel circuit, PARTAGE tel reseau
pneumatique avec telle autre machine) - relation many-to-many entre machines
via un objet "reseau", pas un parent-enfant. Necessiterait une nouvelle
entite (`utility_network` : type electrique/pneumatique/eau, + table
d'association machine<->network) et une UI de filtrage par couche
(coherent avec l'outil de graphe deja introduit pour le factory-builder,
streamlit-flow-component gere nativement des edges typees/coloriees par
type de reseau - meme composant, edges supplementaires plutot qu'un nouvel
outil).

**Statut : idee capturee, pas de schema ni de code.** A construire seulement
apres que le factory-builder hierarchique de base soit termine et valide -
eviter de construire les deux modeles (contenant + reseau) en parallele au
risque de ne finir ni l'un ni l'autre proprement.

**Precisions ajoutees (2026-09-01, plus tard)** :

- **Flux anime et directionnel** : selectionner une canalisation doit montrer
  le sens de circulation anime (pompe -> machine, pas une simple ligne
  statique). React Flow (la lib sous-jacente a `streamlit-flow-component`)
  supporte nativement les "animated edges" - **a verifier que le wrapper
  Python les expose** avant de promettre la fonctionnalite (meme discipline
  que pour le drag-depuis-palette, deja verifie non supporte pour un autre
  usage - ne pas supposer que tout ce que fait React Flow est accessible via
  le wrapper).
- **Noeuds specifiques par type de reseau** : pompe et compresseur comme
  noeuds SOURCES du flux (pas juste des machines generiques) - la direction
  du flux part de ces noeuds vers les machines alimentees.
- **Metadonnee fluide par edge** : eau chaude vs eau froide (et par
  extension air comprime avec pression nominale pour le pneumatique, tension/
  intensite pour l'electrique) - chaque type de reseau a ses propres
  attributs, pas un schema generique unique. Prevoir une table d'attributs
  par type (meme logique deja appliquee pour `bearing_attributes` vs `asset`
  generique - table d'extension par type, pas des colonnes nulles empilees).
- **Jonctions Y (branches)** : une canalisation peut se separer en plusieurs
  (une pompe alimente 2+ machines, ou 2+ sources convergent) - le modele de
  graphe (pas un arbre) gere ca nativement des lors qu'on autorise plusieurs
  edges sortants/entrants par noeud reseau ; le point d'attention est
  l'UI (afficher clairement le point de jonction, pas juste des edges qui se
  croisent visuellement sans noeud explicite dessus) - prevoir un noeud
  "jonction/Y" dedie dans le modele, pas juste des aretes qui partagent un
  point geometrique par coincidence.
- **Meme modele pour electrique et pneumatique**, pas juste l'eau - le type
  de reseau (`utility_network.type`) determine quels attributs d'edge/noeud
  s'appliquent (cf. table d'extension par type ci-dessus).
- **Debit/pression dynamiques selon la consommation** : si une machine
  augmente sa consommation, le debit/pression sur le reseau qui l'alimente
  doit refleter ce changement (et potentiellement affecter les autres
  machines partageant le meme reseau - conservation de flux/perte de charge).
  **A nommer honnetement : c'est un vrai modele physique de reseau (bilan de
  flux, chute de pression), pas juste une valeur affichee** - portee bien
  plus grande qu'un graphe visuel statique, plus proche d'une simulation
  fluide/electrique que d'un dashboard. A chiffrer specifiquement le jour ou
  ce chantier est priorise, pas a sous-estimer comme "juste un attribut de
  plus".
- **Lien avec les alertes** : un ecart anormal de debit/pression (pas
  seulement un defaut roulement) devrait pouvoir declencher une alerte,
  meme mecanisme que l'onglet Alertes actuel (seuil reel entraine ou regle
  metier, jamais de seuil invente) mais applique a une nouvelle categorie de
  mesure (debit/pression) en plus de la vibration.
- **Detection de fuite** : cas specifique de l'ecart debit/pression -
  chute de pression ou debit qui ne s'explique PAS par une hausse de
  consommation connue = signature classique de fuite (pneumatique/eau
  surtout). Necessite de distinguer "variation normale liee a la
  consommation" de "variation non expliquee" - implique de connaitre/estimer
  la consommation attendue par machine (bilan), pas juste surveiller un
  seuil absolu de pression. Renforce le point ci-dessus : c'est un modele de
  bilan de reseau, pas une simple regle de seuil.
- **Heuristique de distinction (normal vs anomalie)** : si TOUS les
  parametres montent ensemble et de façon coherente (vitesse, debit,
  pression, consommation...), c'est probablement une hausse de cadence
  machine - normal, pas une alerte. Si un parametre devie SANS que les
  autres suivent (ex. pression qui chute alors que la cadence n'a pas
  change), c'est le signal d'anomalie (fuite, defaut...) - la coherence
  MULTI-parametres est le vrai signal, pas un seul chiffre isole. Rejoint
  directement le principe deja applique au projet pour les features
  vibratoires (une seule feature ne suffit jamais, voir Phase 2 GBM vs
  seuil unique) - meme logique, nouveau domaine (reseau plutot que
  vibration).

**Ancrages reels trouves (recherche 2026-09-01), pas juste une idee de zero** :

- **ISO 50001** (management de l'energie) est le referentiel normatif utilise
  en pratique pour le calcul/reporting de fuites d'air comprime - equivalent
  ISO 20816 pour les reseaux d'utilites. Voir `docs/theorie_reference.md` §1.
- **IFM (deja concurrent documente, §3.1 competitive_analysis.md) fait deja
  de la detection de fuite air comprime** avec des debitmetres IO-Link
  (SD compressed air flow meter) - pas une idee originale, un produit
  existant chez un acteur qu'on etudie deja. A creuser/citer si le chantier
  est un jour lance plutot que de re-inventer la methode.
- **Methode standard de calibrage** : mesurer le debit reseau quand l'usine
  est A L'ARRET (consommation nulle connue) jusqu'a une chute de pression de
  reference - donne une estimation directe du niveau de fuite, sans meme
  avoir besoin du modele de bilan complet. Rejoint l'heuristique
  multi-parametres ci-dessus : "consommation nulle attendue" est le cas le
  plus simple de coherence attendue vs mesuree.
- **Terminologie eau : NRW (Non-Revenue Water)** - standard secteur pour
  l'eau perdue (fuites, casse) non facturee. Un "digital twin" reduit le NRW
  de ~25% selon une source citee (a revalider si le chantier eau est
  priorise, chiffre marketing a l'origine non verifiee ici).
- **AAS (Asset Administration Shell, RAMI 4.0)** deja identifie ailleurs
  dans le projet (F-29 backlog) comme standard de representation d'actif
  Industrie 4.0 - possible format cible si le factory-builder + reseaux
  d'utilites doit un jour s'interfacer avec des systemes tiers.

## Cycle de refresh configurable par source - capture 2026-09-01

Idee : permettre a l'utilisateur de choisir la frequence de collecte par
source (ex. toutes les heures, tous les jours), avec Airflow evoque comme
orchestrateur.

**Airflow deja tranche hors scope** (`docs/feature_backlog.md` F-67, meme
raisonnement que Ray/K8s §1-2 ci-dessus : "Docker Compose + scripts CLI
suffisent" tant qu'on est dans le perimetre batch). Rien ne change cette
conclusion ici - le declencheur reste le meme (ingestion continue reelle,
pas encore le cas).

**Pre-requis non rempli avant meme de parler d'orchestrateur :** aucune
machine du factory-builder n'a de source de donnees reellement branchee
(toutes en etat `unknown`/vide, voir la contrainte "0 mock" appliquee au
factory-builder) - "choisir un cycle de refresh" n'a pas d'objet tant qu'il
n'y a rien a rafraichir. La bonne premiere brique n'est pas l'orchestrateur
mais le connecteur d'ingestion lui-meme (Partie B de
`docs/plan_bearing_catalog_and_ingestion.md`) - le refresh cycle est un
parametre de CE connecteur (ex. simple `schedule_seconds` sur `machine` ou
nouvelle table `data_source_config`), pas un DAG Airflow.

**Si le declencheur scaling_path.md (ingestion continue, plusieurs sources
reelles) est atteint un jour :** un simple cron (`schedule.py` ou
equivalent, meme approche que `scripts/build_dataset.py` relance
periodiquement) suffit tant qu'on reste sur quelques sources. Airflow ne
redevient pertinent qu'au meme seuil que deja documente (orchestration de
plusieurs DAGs interdependants, retry/backfill complexes) - pas juste "on
veut un refresh programmable".

## Inventaire capteurs + emplacement type (recherche 2026-09-01)

Pour le chantier reseaux d'utilites (electrique/pneumatique/eau, section
ci-dessus) - quels capteurs existent et OU les placer. Pas un catalogue
exhaustif, les principes qui structurent le placement (pertinent pour le
modele de graphe : ou accrocher un capteur sur une edge/un noeud reseau).

**Electrique :**
- Capteur de tension (AC pour moteurs/transfos/alimentation, DC pour
  batteries/armoires de controle) - place au niveau du tableau/disjoncteur,
  pas sur la machine elle-meme en general.
- Capteur de courant (pince ampèremetrique/CT) - au depart de circuit
  (disjoncteur) ou au plus pres du moteur pour isoler la consommation d'UNE
  machine specifiquement (pertinent pour le bilan de consommation §"debit/
  pression dynamiques" ci-dessus).

**Pression (pneumatique/eau) :**
- Placement par raccord en T (tee) pour ne pas perturber l'ecoulement -
  jamais en insertion directe dans la ligne principale si evitable.
- Eviter la proximite immediate d'une pompe (vibrations parasites) et des
  sources CEM/electromagnetiques (>5 m des gros moteurs/transformateurs -
  contamination du signal, meme categorie de probleme que la contamination
  secteur ~50Hz deja documentee en vibration, `docs/known_issues.md`).

**Debit (flowmetre) :**
- Necessite une portion de tuyau DROITE : 10 diametres de tuyau en amont,
  5 en aval, sans coude ni perturbation - sinon mesure faussee. Contrainte
  d'installation physique a anticiper des la conception du reseau modelise,
  pas ajoutable n'importe ou a posteriori.
- Position circonferentielle : dessus du tuyau pour un gaz (air comprime),
  cote pour liquide/vapeur, JAMAIS en dessous (sediments qui s'accumulent
  et faussent la mesure).

**Placement optimal pour detection de fuite - c'est un sujet de recherche a
part entiere**, pas un choix arbitraire : voir litterature "Optimal Pressure
Sensor Deployment for Leak Identification" (reseaux d'eau) - le nombre et
l'emplacement des capteurs de pression sur un reseau determine directement
la capacite a LOCALISER une fuite (pas juste detecter qu'il y en a une
quelque part). A revisiter serieusement si la detection de fuite localisee
(pas juste globale) devient un objectif du chantier.

**Consequence pour le modele de donnees (si construit)** : un capteur n'est
pas juste attache a un "noeud" du graphe reseau de façon generique - sa
position (amont/aval d'une jonction, sur quelle portion droite) est une
information structurelle a part entiere, pas un detail d'installation a
ignorer. Prevoir un champ de position/contrainte d'installation des la
conception du schema, pas a rajouter apres coup.
