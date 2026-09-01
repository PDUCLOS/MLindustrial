# Théorie de référence — analyse vibratoire & maintenance prédictive IoT 4.0

Note de synthèse pour prendre de la hauteur sur le projet. Compile les normes, méthodes et cadres conceptuels du domaine, avec pour chacun le lien vers ce que fait (ou devrait faire) ce repo. Sources en bas de section.

---

## 1. Normes de référence en analyse vibratoire

### ISO 20816 (ex-ISO 10816) — sévérité vibratoire
Norme d'évaluation globale des machines tournantes par la vitesse vibratoire RMS (mm/s, bande ~10–1000 Hz), mesurée sur les paliers. Classe la machine en 4 zones :
- **A** — état neuf
- **B** — fonctionnement acceptable long terme
- **C** — fonctionnement toléré à court terme, action à programmer
- **D** — dommage en cours, risque de casse

ISO 20816-3 s'applique aux machines >15 kW, 120–15 000 tr/min. Consolide l'ancien ISO 10816 (vibration sur parties fixes) et l'ISO 7919 (vibration d'arbre).

**Lien projet** : §5 du brief mentionne déjà les indicateurs ISO 10816 pour l'interprétabilité métier. C'est le seul point où le projet touche à une classification *absolue* (seuil universel) plutôt qu'*relative* (dérive par rapport à une baseline saine) — à documenter comme complément, pas comme méthode principale, puisque Paderborn ne fournit pas de vitesse vibratoire calibrée en mm/s exploitable telle quelle.

### ISO 13373 — procédures de traitement du signal
Deux parties utiles : 13373-1 (procédures générales de mesure) et 13373-2 (traitement, analyse, présentation des données vibratoires — FFT, enveloppe, cepstre). Cadre méthodologique de référence pour documenter la chaîne de traitement du §5 du brief de façon normée.

### ISO 13374 — architecture fonctionnelle de la surveillance d'état
Découpe tout système de condition monitoring en blocs fonctionnels enchaînés :
1. **Data acquisition** — capture brute + métadonnées
2. **Data manipulation** — traitement du signal
3. **State detection** — normal / anormal
4. **Health assessment** — diagnostic de défaut, sévérité
5. **Prognostic assessment** — durée de vie résiduelle
6. **Decision support** — recommandation d'action
7–8. **Presentation / Actioning**

**Lien projet** : cette architecture correspond presque trait pour trait à l'arborescence `src/features/` → `src/models/` → `src/evaluation/` du §7. Vaut la peine de citer ISO 13374 dans le README pour montrer que l'architecture logicielle suit un cadre reconnu, pas une structure ad hoc.

### ISO 18436 — qualification du personnel
Norme de certification humaine (analystes vibratoire niveaux I à IV), pas technique. Utile seulement en référence culture métier : signale que l'expertise que le projet cherche à encoder (raies BPFO/BPFI lisibles par un chef d'atelier) est un métier normé et certifié, pas un artisanat improvisé — argument pour le §9 du brief.

### ISO 50001 — management de l'énergie (référence pour les réseaux d'utilités, hors périmètre actuel)
Norme de système de management de l'énergie — utilisée en pratique pour le calcul et le reporting des fuites d'air comprimé (vérifié 2026-09-01 : IFM, déjà documenté §3.1 de `docs/competitive_analysis.md`, propose des débitmètres air comprimé IO-Link explicitement rattachés à une conformité ISO 50001). C'est l'équivalent, côté réseaux d'utilités (électrique/pneumatique/eau), de ce qu'ISO 20816 est côté vibration — un référentiel normatif à citer si le chantier "réseaux d'utilités" de `docs/scaling_path.md` est un jour construit, pas avant.

---

## 2. Fréquences caractéristiques de défaut — fondement physique

Rappel théorique derrière les formules déjà dans le brief (§5). Un défaut localisé (écaillage, piqûre) génère un choc mécanique périodique à chaque passage d'un élément roulant sur le défaut. La fréquence de ce choc dépend de la géométrie et de la cinématique du roulement, pas de sa sévérité — c'est ce qui permet de localiser le défaut (bague ext./int., bille, cage) uniquement à partir de la fréquence, indépendamment de l'amplitude.

- **BPFO** (Ball Pass Frequency Outer race) : passage des éléments roulants sur un défaut de bague extérieure — fixe par rapport au bâti, la fréquence est stable et son harmonique 1 domine généralement.
- **BPFI** (Ball Pass Frequency Inner race) : défaut de bague intérieure — tourne avec l'arbre, donc modulé en amplitude à la fréquence de rotation → bandes latérales (*sidebands*) espacées de `fr` autour de BPFI et ses harmoniques. Signature caractéristique à chercher.
- **BSF** (Ball Spin Frequency) : défaut sur un élément roulant — modulé par la FTF (le défaut ne touche les bagues qu'une fraction du temps), donc bandes latérales espacées de FTF autour de 2×BSF (le facteur 2 vient du double contact bague int./ext. par tour de bille).
- **FTF** (Fundamental Train Frequency) : défaut de cage — fréquence basse, rarement dominante seule, sert surtout de fréquence de modulation pour BSF.

Relation utile pour la vérification manuelle demandée en Phase 2 du brief : BPFO + BPFI = n × fr (nombre de billes × fréquence de rotation), et FTF ≈ BPFO/n. Ces identités sont un bon test unitaire indépendant du calcul direct.

**Piège classique** : à faible vitesse ou avec un fort bruit de fond, ces raies n'apparaissent quasiment jamais dans le spectre brut — elles sont noyées sous le spectre de la structure et des forces d'excitation basse fréquence. D'où la nécessité de l'analyse d'enveloppe (§3).

---

## 2bis. Paliers (logements) et types de roulements — catalogue metier

Contrairement a la geometrie interne d'un roulement (billes/rouleaux, non publiee par les
catalogues constructeur - voir §2 et `configs/bearing_geometry.yaml`), les types de PALIERS
(logements qui accueillent le roulement) et de ROULEMENTS (familles cinematiques) sont du
catalogue public standard SKF/Schaeffler/NTN-SNR - utile pour lire une installation reelle et
savoir quelle formule/quelle hypothese s'applique.

### Types de paliers (logements)

| Type | Designation catalogue | Usage | Points d'attention |
|---|---|---|---|
| **Palier a semelle (pillow block / plummer block)** | SKF SNL/SE, generique "P2xx" | Le plus courant - fixation au sol/chassis par 2 ou 4 boulons, axe parallele au support | Roulement sur portee cylindrique, souvent avec manchon de serrage - alignement initial critique (voir §4bis desalignement) |
| **Palier Y (Y-bearing / insert bearing unit)** | SKF SY/SYH/SYJ/SYM, roulement insert YAR | Applications legeres/agricoles, montage rapide | Blocage par vis pointeau (grub screw) ou bague excentrique - jeu de montage plus grand qu'un palier a semelle industriel, a surveiller en interpretation vibratoire (peut ajouter un jeu mecanique, voir §4bis) |
| **Palier a applique (flanged housing unit)** | SKF FNL, FYH, FYJ | Fixation sur face verticale/laterale (bout d'arbre, carter) | Charge axiale generalement mieux reprise qu'un palier a semelle standard selon le modele |
| **Palier a bride (flange block, rond/carre/ovale)** | SKF FYTB, FYRP... | Variante de l'applique, forme de bride adaptee a l'espace disponible | Idem applique |
| **Palier oscillant (take-up unit)** | SKF TU, TUCF | Convoyeurs - reglage de tension par glissiere | Prevoir le jeu de reglage dans l'analyse d'alignement |

### Types de roulements (familles cinematiques)

| Famille | Charge radiale | Charge axiale | Vitesse | Particularite pour le diagnostic vibratoire |
|---|---|---|---|---|
| **A billes a gorge profonde (deep groove ball)** | Bonne | Moyenne (2 sens) | Elevee | Le cas standard couvert par les formules BPFO/BPFI/BSF/FTF de §2 (6203, 6205, UER204, 6804 de ce projet) |
| **A contact oblique (angular contact ball)** | Bonne | Elevee (1 sens, souvent monte par paire) | Elevee | Meme formules, angle de contact phi non nul (a la difference des roulements ci-dessus, tous a phi=0 dans ce projet) |
| **A rouleaux cylindriques** | Tres bonne | Faible/nulle | Elevee | Formules identiques, d=diametre rouleau (pas bille) |
| **A rouleaux coniques (tapered roller)** | Bonne | Elevee (1 sens, monte par paire en opposition) | Moyenne | Angle de contact non nul obligatoire dans le calcul - ex. Rexnord ZA-2115 (NASA IMS, voir config) |
| **A rotule sur rouleaux (spherical roller)** | Tres bonne | Moyenne | Faible/moyenne | DOUBLE rangee generalement - appliquer les formules par rangee, pas globalement |
| **A aiguilles (needle roller)** | Bonne (encombrement radial minimal) | Faible/nulle | Moyenne | Grand nombre d'elements tres fins - BSF tres basse frequence, souvent noyee dans le bruit |
| **De butee (thrust, a billes ou rouleaux)** | Nulle/faible | Tres elevee (1 ou 2 sens) | Faible | Axe de calcul different (charge purement axiale) - formules BPFO/BPFI de §2 non directement applicables telles quelles |

**Application projet** : tous les roulements des 7 datasets references dans `configs/bearing_geometry.yaml`
sont a gorge profonde (deep groove ball, phi=0), SAUF le Rexnord ZA-2115 (NASA IMS) qui est un
roulement a rouleaux a DOUBLE rangee avec angle de contact 15.17 deg - la formule standard BPFO/BPFI/BSF/FTF
reste valable par rangee mais n'a pas ete testee dans ce projet (marque "estimated/a valider" dans le
config). Le type de palier (Y/semelle/applique) n'affecte pas le calcul des frequences de defaut
du roulement lui-meme, mais conditionne le risque de jeu mecanique/desalignement install (§4bis) -
a noter lors de toute inspection terrain, independamment du dataset.

## 2ter. Modes de defaillance roulement par apparence (ISO 15243)

ISO 15243:2017 classe les defauts de roulement en 6 modes principaux (fatigue,
usure, corrosion, courant electrique, deformation plastique, fracture/fissuration),
14 sous-modes au total, par APPARENCE visuelle du dommage plutot que par
localisation (bague int./ext./bille/cage) - complementaire, pas concurrente, de
la classification BPFO/BPFI/BSF/FTF utilisee ailleurs dans ce document.

**A assumer explicitement pour ce projet :** statistique SKF sur leur base BART
(Bearing Analysis Reporting Tool, empirique constructeur, pas un echantillon
aleatoire representatif de tout le parc industriel mondial - a lire comme un
ordre de grandeur, pas une valeur de reference universelle) : seulement ~16%
des defauts industriels observes sont des defauts classiques de fatigue de
piste (surface-initiated fatigue - le mode que Paderborn artificiel/reel modelise
principalement). Les ~84% restants se repartissent en usure abrasive (~26%),
corrosion humide (~14%), adhesive wear (~7%), erosion par fuite de courant
electrique (~7%), et autres modes non couverts par ce projet.

**Consequence pour le projet :** le perimetre Paderborn (defauts d'usinage/EDM
et fatigue de piste par vieillissement accelere) couvre une FRACTION du spectre
reel des modes de defaillance rencontres en usine - a assumer explicitement
dans la restitution finale (docs/brief_projet.md §9 : resultats honnetes), pas a presenter
comme une couverture generale "detection de defaut roulement" sans qualifier
le mode couvert.

**Lien avec l'erosion par courant electrique :** ce mode de defaut (7% BART)
est directement pertinent pour l'objectif secondaire du projet (comparaison
vibration/courant moteur, MCSA §4) - un roulement endommage par fuite de
courant (souvent lie a une alimentation variateur mal filtree) produirait un
signal DIFFERENT d'un defaut mecanique classique, piste non exploree ici.

### Detail des 14 sous-modes ISO 15243 (classification complete)

**Source :** ISO 15243:2017 (clause numbers), catalogues SKF/Schaeffler/Timken adaptes.

**5.1 Fatigue de contact (rolling contact fatigue)**

- **5.1.2 Subsurface initiated fatigue** : micro-fissures sous la surface qui
  remontent en spalling (ecaillage). C'est le mode predit par la duree de vie
  L10/L10mh, initie souvent sur une inclusion. Une surcharge temporaire peut
  faire chuter la duree a 5-10% de L10mh (SKF Evolution). Signature spectrale :
  **raies BPFO/BPFI/BSF discretes + harmoniques**, kurtosis eleve sur signal brut.
  C'est le mode principal que Paderborn modelise (defauts reels par vieillissement
  accelere).
- **5.1.3 Surface initiated fatigue** : amorce en surface, causee par lubrification
  inadequate (film trop mince) ou contamination. Signature similaire a 5.1.2 mais
  souvent plus progressive. Paderborn artificiel (percage, EDM) releve de cette
  categorie en termes d'apparence, meme si la creation est mecanique.

**5.2 Usure (wear)**

- **5.2.2 Abrasive wear** : enlvement progressif de matiere par particules
  contaminantes. Surface devient mate, le poli d'origine disparait. ~26% des
  defauts BART. Spectre large bande sans raies discretes, kurtosis modere.
- **5.2.3 Adhesive wear (smearing/galling)** : transfert de matiere entre surfaces
  en glissement relatif, typique d'un roulement trop legerement charge ou avec
  acceleration excessive a l'entree de la zone de charge. Surface "etalee",
  materiel deplace. ~7% BART.

**5.3 Corrosion**

- **5.3.2 Moisture corrosion** : oxydation classique en presence d'eau/humidite.
  ~14% BART. Pas de signature spectrale particuliere, mais augmentation du
  bruit de fond large bande avec le temps.
- **5.3.3.2 Fretting corrosion** : micro-mouvements a l'interface (bague/arbre
  ou bague/logement). Marque d'oxyde rouge/noire au siège. Commun a des
  roulements de presse/marine.
- **5.3.3.3 False brinelling** : usure a l'arret par oscillation micro-metrique
  des billes. Marques a l'espacement inter-billes (rolling element pitch), avec
  oxydation rouge/noire. Cf. `docs/known_issues.md` section "Hypothese false
  brinelling - NON CONFIRMEE" pour la discussion Paderborn.

**5.4 Erosion electrique (electrical erosion)**

- **5.4.2 Excessive current erosion** : passage d'un courant eleve (court-circuit,
  eclair, soudage mal mis a la terre). Crateres, zones discolorationnee
  (tempered/rehardened), aspect de soudure. Signature : pas de raies BPFO,
  stries axiales visibles.
- **5.4.3 Current leakage erosion** : courant de faible intensite continu (VFD
  mal mis a la terre, shaft non grounded). Petits crateres, pattern "washboard"
  gris. ~7% BART. **Particulierement pertinent pour MCSA** : la signature dans
  le courant moteur serait visible comme une modulation aux frequences
  caracteristiques du defaut, mais on ne l'a pas explore dans ce projet.

**5.5 Deformation plastique**

- **5.5.2 Overload deformation (true brinelling)** : choc ou surcharge statique
  qui enfonce les billes dans la piste. Le fini d'origine EST conserve dans
  la marque (pas d'usure, juste deplacement plastique). Cf. false brinelling
  pour la distinction.
- **5.5.3 Indentations from particles** : particules coincees entre bille et
  piste, laissant des empreintes circulaires. Spectre large bande, kurtosis
  ponctuellement eleve.

**5.6 Fissuration et rupture (cracking and fracture)**

- **5.6.2 Forced fracture** : rupture par sur-contrainte immediate (surcharge
  severe, choc). Pas un mode d'usure normal.
- **5.6.3 Fatigue fracture** : fissure progressive par depassement repete de
  la limite d'endurance. Visible comme une fissure qui se propage.
- **5.6.4 Thermal cracking** : fissure generee par echauffement local
  important (defaut de lubrification severe, friction excessive). Souvent
  perpendiculaire a la direction de glissement.

### Application au projet ML

- **Couvert par Paderborn** : 5.1.2, 5.1.3 (fatigue), partiellement 5.5.3 (indentations
  pour les roulements artificiels de type drilling/engraving). C'est ~16% du
  spectre reel des defauts.
- **Non couvert par Paderborn mais dans le scope "analyse vibratoire"** : 5.2.2,
  5.2.3 (usure), 5.3 (corrosion), 5.4 (erosion electrique), 5.5.2 (true brinelling),
  5.6 (fissuration). Ces modes demandent soit des datasets specifiques, soit
  des methodes d'analyse complementaires (analyse d'huile, thermographie,
  inspection visuelle).
- **A documenter explicitement dans le rapport final** : la couverture Paderborn
  est limitee a ~16% des defauts reels. Le projet n'est PAS un "detecteur
  universel de defaut roulement" mais un "detecteur de defaut de piste (fatigue
  initiee en surface ou sous-surface) sur 6203 dans des conditions de banc
  d'essai".

### Vocabulaire terrain (en plus de ce qui est deja dans le projet)

- **Raceway** : chemin de roulement (surface sur laquelle roule l'element)
- **Spalling** : ecaillage de fatigue (fragments qui se detachent)
- **Pitting** : petites piqures en surface
- **Frosting** : surface micro-pitted uniforme
- **Peeling** : ecaillage en plaques (surface initiated fatigue)
- **Brinelling** : deformation permanente par surcharge
- **Stribeck curve** : courbe friction vs vitesse/charge - determine le regime
  de lubrification (boundary / mixed / EHL/hydrodynamic)
- **Lambda ratio (λ)** : epaisseur du film de lubrification / rugosite composite.
  λ < 1 : boundary lubrication, defaut par fatigue de surface probable.
- **L10 life** : duree statistique nominale (90% de survie) en millions de tours
- **L10mh** : L10 modifiee pour conditions reelles (vs conditions catalogue)
- **Cage (retainer)** : porte-elements roulants, frequence FTF
- **Smearing** / **galling** / **scuffing** : termes d'usure adhesive selon severite

## 3. Analyse d'enveloppe — pourquoi et comment

Un choc mécanique bref excite une ou plusieurs fréquences de résonance structurelle du roulement/palier (typiquement 1–20 kHz selon la taille), qui sonnent comme une cloche frappée à répétition. Le signal vibratoire brut est donc la modulation d'amplitude d'une porteuse haute fréquence (la résonance) par un train d'impulsions basse fréquence (le taux de passage sur le défaut — BPFO/BPFI/BSF).

**Chaîne classique (déjà dans le brief §5)** :
1. Filtrage passe-bande autour de la bande résonante excitée
2. Transformée de Hilbert → enveloppe du signal filtré (démodulation d'amplitude)
3. FFT de l'enveloppe → spectre d'enveloppe, où BPFO/BPFI/BSF et harmoniques apparaissent nettement, débarrassés du bruit basse fréquence et des raies de rotation

**Difficulté pratique** : la bande résonante n'est pas connue a priori — elle dépend du roulement, du support, du capteur. C'est le problème que résout le kurtogramme.

### Kurtosis spectral et kurtogramme (Antoni)
Le kurtosis spectral (SK) mesure, fréquence par fréquence, à quel point le signal filtré autour de cette fréquence est impulsif (kurtosis élevé = chocs présents, kurtosis proche de 0 = bruit gaussien stationnaire). Antoni a formalisé le **kurtogramme** : une cartographie de SK en fonction de la fréquence centrale et de la bande passante d'un banc de filtres, qui permet de sélectionner automatiquement la bande optimale de démodulation sans expertise a priori. Le **fast kurtogram** (arbre binaire 1/3-octave) rend le calcul praticable en temps quasi réel.

**Lien projet** : c'est l'outil qui automatise le choix de bande pour `src/features/envelope.py`, remplaçant un réglage manuel bande-par-bande. Directement actionnable — `scipy.signal` + une implémentation maison du fast kurtogram (pas de dépendance dédiée mature en Python, à vérifier avant de coder from scratch).

### Hiérarchie de précocité de détection — scope assumé

Du plus précoce au plus tardif dans la vie d'un défaut roulement : **SPM (Shock
Pulse Method, 1969)** > **SEE/HD (Spectral Emitted Energy / High-frequency
Detection)** > **analyse d'enveloppe** > **indicateurs temporels seuls**
(RMS/kurtosis/crest factor bruts). SPM et SEE/HD nécessitent un capteur/mode
d'acquisition dédié (résonance piézo spécifique, bande ultrasonique) absent de
Paderborn et de la plupart des datasets publics de ce projet.

**Ce projet couvre les deux dernières cases** (enveloppe + temporel) — cohérent
avec le périmètre datasets publics (pas de capteur SPM disponible), mais à
assumer explicitement plutôt qu'à laisser implicite : ce projet ne prétend pas
détecter au stade le plus précoce possible, seulement au stade où l'analyse
vibratoire standard (accéléromètre générique + FFT/enveloppe) devient efficace.

---

## 4. Courant moteur — MCSA (Motor Current Signature Analysis)

Principe : un défaut mécanique (roulement, excentricité, barre cassée) module le couple résistant du moteur, donc le glissement, donc le champ magnétique — et se traduit par des bandes latérales autour de la fréquence fondamentale du réseau (50/60 Hz) dans le spectre du courant statorique. Pour un défaut de roulement, les fréquences caractéristiques (BPFO/BPFI/BSF) apparaissent comme bandes latérales autour de f_ligne : `f_ligne ± k·f_défaut`.

**Limites connues** (directement pertinentes pour l'objectif secondaire du brief) :
- Signature beaucoup plus faible en amplitude que côté vibratoire — un défaut de roulement module le courant de façon indirecte et atténuée
- Nécessite un couple de charge suffisant (généralement ≥ 40 %) pour que le glissement porte l'information — problématique si les essais Paderborn ne couvrent pas ce point
- Sensible aux harmoniques de l'alimentation (variateur de fréquence) qui peuvent masquer ou imiter les bandes latérales de défaut

**Lien projet** : ces limites doivent être posées *avant* de lancer l'objectif secondaire (§2), pas découvertes après coup — sinon un résultat "le courant ne marche pas" est indiscernable entre "le courant n'a pas l'info" et "les conditions de charge Paderborn sont défavorables au MCSA". Vérifier les niveaux de charge des 4 conditions Paderborn (K002 datasheet) avant de conclure quoi que ce soit sur l'argument coût du §9.

---

## 4bis. Taxonomie des defauts mecaniques courants (au-dela du roulement)

Objectif : un chef d'atelier doit pouvoir lire un spectre et distinguer un defaut de roulement
d'un probleme d'installation - desalignement, balourd, jeu mecanique, lubrification - AVANT
d'immobiliser la machine pour un remplacement de roulement qui ne resoudra rien. Chaque cause a
une signature spectrale distincte, largement independante des formules BPFO/BPFI/BSF/FTF du §2.

| Defaut | Signature vibratoire | Confusable avec |
|---|---|---|
| **Balourd (unbalance)** | Raie dominante a 1x (frequence de rotation), radiale, amplitude stable dans le temps | Rarement confondu seul, mais masque les autres raies si dominant |
| **Desalignement (misalignment)** | Raies a 1x ET 2x (parfois 3x), radiales ET axiales, dephasage caracteristique entre paliers | BSF/2xBSF (voir plus bas - collision d'ordre specifique a ce roulement) ; a 1500 tr/min sur le 6203 Paderborn, 2x=50Hz=secteur EXACTEMENT, indiscernable sans canal supplementaire |
| **Jeu mecanique (looseness)** | Harmoniques nombreuses de 1x (jusqu'a 5x-10x), plancher de bruit large-bande releve, souvent asymetrique (tronque d'un cote) | Defaut de roulement avance (spectre riche en harmoniques) |
| **Lubrification deficiente** | Bruit large-bande haute frequence SANS raie discrete, kurtosis eleve sans structure spectrale nette, souvent avant l'apparition de raies BPFO/BPFI franches | **Candidat serieux pour l'anomalie documentee ci-dessous (kurtosis sain > kurtosis defaut sur Paderborn)** - un roulement en rodage/lubrification non stabilisee peut afficher un kurtosis eleve sans defaut de piste |
| **Defaut de piste roulement (BPFO/BPFI/BSF/FTF)** | Raies discretes + harmoniques aux frequences caracteristiques (§2), bandes laterales de modulation | Voir tableau ci-dessus pour les collisions d'ordre specifiques a ce roulement |

**Application directe a `docs/known_issues.md`** : l'anomalie "kurtosis sain (14.63) > kurtosis
defaut reel (7.36)" reste non expliquee avec certitude, mais la piste lubrification/rodage est
maintenant une hypothese concrete a tester (pas seulement "contamination banc") - un roulement
Paderborn sain n'a jamais tourne avant l'essai (voir §6 doc K001 : lifetime >50h, mais roulements
a defaut reel ont subi un vieillissement accelere different) ; un etat de rodage different entre
groupes pourrait a lui seul produire ce motif, independamment de toute contamination secteur.

## 4ter. Choisir une vitesse de banc : ce que la geometrie impose vs ce qu'on peut regler

Deux categories de collision spectrale, a ne pas confondre :

1. **Collisions d'ORDRE (fixes, independantes du rpm)** - proprietes de la geometrie du roulement.
   Pour le 6203 Paderborn (n=8, d=6.75mm, D=29.05mm, phi=0) : BPFO=3.071x fr (a 2.4% du 3e
   harmonique arbre), BSF=2.036x fr (a 1.8% du 2e harmonique arbre). Aucun choix de vitesse ne
   separe ces raies - seule une resolution frequentielle fine ou un suivi d'ordre (tachymetrie)
   le permet.
2. **Collisions avec le SECTEUR (Hz absolus, reglables par le choix du rpm)** - le secteur EU
   (50/100/150/200 Hz) est fixe, mais les raies mecaniques (1x/2x/3x, BPFO/BPFI/BSF/FTF) sont
   proportionnelles au rpm. Un choix de vitesse judicieux les eloigne du secteur.

**Balayage (voir `src/features/fault_frequencies.py::mains_separation_hz`)**, ecart minimal entre
toute raie mecanique (1x/2x/3x + BPFO/BPFI/BSF/FTF) et le secteur EU, sur une plage industrielle
realiste (600-2000 tr/min), geometrie 6203 Paderborn confirmee (n=8, d=6.75mm, D=29.05mm) :

| Vitesse | Ecart min. au secteur EU |
|---|---|
| **750 tr/min - meilleur candidat de la plage balayee** | **11.62 Hz** |
| 900 tr/min (condition Paderborn N09) | 3.94 Hz |
| **1500 tr/min (condition Paderborn N15, la plus utilisee)** | **0.00 Hz - 2x=50Hz EXACTEMENT** |
| 1730 tr/min (proche vitesse en charge moteur 4 poles) | 7.67 Hz |

**Proposition** : 750 tr/min - proche de la vitesse en charge d'un moteur asynchrone 8 poles
standard sous 50 Hz (synchrone 750 tr/min, glissement typique -> ~730 tr/min en charge), donc
atteignable sans variateur exotique. Meilleur compromis de separation secteur trouve sur la plage
balayee ; 1730 tr/min (proche moteur 4 poles) reste une alternative correcte si la geometrie du
banc impose un moteur 4 poles plutot que 8 poles. Dans les deux cas : ne resout PAS les collisions
d'ordre du point 1 (BPFO~3x, BSF~2x) - c'est une limite de CE roulement, pas du choix de vitesse.
La condition Paderborn a 1500 tr/min (la plus testee dans le dataset) est au contraire le pire
choix possible pour separer desalignement (2x) et contamination secteur - a signaler
explicitement dans toute lecture de spectre issue de cette condition.

## 5. Cadre conceptuel maintenance 4.0

### Évolution des stratégies
1. **Corrective (réactive)** — on répare après panne
2. **Préventive systématique** — intervention calendaire/horaire, indépendante de l'état réel
3. **Conditionnelle (CBM)** — intervention déclenchée par un seuil sur un indicateur mesuré (ex. ISO 20816 zone C)
4. **Prédictive (PdM)** — modèle qui estime l'état de dégradation et/ou la durée de vie résiduelle (RUL), au-delà d'un simple seuil
5. **Prescriptive** — recommande l'action optimale (quand, quoi remplacer, impact planning) compte tenu du diagnostic

Le projet se positionne en diagnostic (classification de défaut), à la frontière basse de la PdM au sens strict — pas de RUL dans l'objectif principal. À noter explicitement dans le README pour ne pas sur-vendre : diagnostiquer un défaut existant ≠ prédire une panne future. La piste RUL sur XJTU-SY (roadmap Phase 0, alternative non tranchée) est ce qui ferait basculer vers la PdM au sens plein.

### Courbe P-F (Potential-to-Functional failure) — pourquoi l'ordre des symptômes compte

Représentation classique (reprise ici de la documentation IFM moneo, concept générique du domaine, pas propriétaire) : l'état d'un composant se dégrade selon une courbe, et les symptômes détectables apparaissent dans un ordre precis à mesure qu'on se rapproche de la panne — dérive vibratoire (mois d'avance) → frictions (semaines) → bruits (semaines/jours) → surchauffe/fumée (jours) → panne. Le temps de réaction disponible et la précision de la prédiction évoluent en sens inverse : plus on détecte tôt (vibration), plus le délai d'action est confortable mais moins la prédiction est précise sur l'échéance exacte ; plus on détecte tard (fumée), plus c'est précis mais il ne reste que des jours.

**Lien direct avec le projet** : l'analyse vibratoire (ce que fait ce projet) se positionne tout à gauche de cette courbe — c'est l'indicateur le plus précoce, avant friction/bruit/chaleur. Ça justifie concrètement pourquoi la vibration est le capteur de référence en maintenance prédictive (pas juste une convention) et renforce le point ci-dessus : ce projet détecte une dérive/un défaut existant à un stade précoce, ce qui est différent de prédire un instant de panne précis (RUL) - la courbe P-F montre pourquoi ces deux notions (détection précoce vs précision de l'échéance) sont en tension, pas juste une nuance de vocabulaire.

### CBM+ (Condition-Based Maintenance Plus, terminologie DoD/industrie)
Extension du CBM classique qui intègre le diagnostic (quel est le défaut) et le pronostic (combien de temps reste-t-il) dans une seule chaîne décisionnelle, avec retour d'expérience pour affiner les modèles. Correspond à l'architecture ISO 13374 ci-dessus.

### Architecture IoT typique (edge / fog / cloud)
- **Edge** — capteur + calcul embarqué : extraction de features légères en temps réel (RMS, kurtosis), réduction drastique du volume avant transmission. C'est là où la légèreté des features physiques du projet (par rapport à un CNN sur signal brut) devient un argument concret : un modèle GBM sur features physiques tourne sur edge, un CNN 1D rarement.
- **Fog** — agrégation intermédiaire, prétraitement, alerte locale
- **Cloud** — stockage long terme, réentraînement des modèles, tableaux de bord

**Lien projet** : le §9 du brief pose déjà l'argument coût capteur. L'argument coût de calcul (edge-déployable vs cloud-only) est le prolongement naturel côté MLOps léger — sans pour autant réintroduire l'infra que le brief exclut explicitement (§1). Une phrase chiffrée (latence d'inférence GBM vs CNN 1D sur CPU) suffit, pas une démo edge complète.

### PHM (Prognostics and Health Management) — les 3 familles de méthodes RUL
Utile seulement si la piste XJTU-SY/RUL est retenue (§8 Phase 0) :
1. **Physique** — modèle de propagation de fissure/usure (loi de Paris etc.), nécessite une connaissance fine du mode de défaillance
2. **Statistique** — modèles de dégradation probabilistes (Wiener, Gamma process), pas d'apprentissage profond
3. **Data-driven / IA** — régression sur indicateur de santé (HI) construit à partir de features, jusqu'aux réseaux profonds (LSTM, transformers) sur signal brut

Le choix cohérent avec la philosophie du projet (features physiques d'abord) serait un indicateur de santé construit à partir des mêmes features temporelles/enveloppe du §5, puis une régression simple dessus — pas un LSTM en premier réflexe.

---

## 6. Généralisation artificiel → réel : état de l'art (directement lié à l'objectif principal)

Le mur que le projet cherche à mesurer (défauts usinés → défauts naturels) est un sujet de recherche actif, pas une curiosité isolée. Résumé des approches publiées :
- **Domain-adversarial training** — le modèle apprend des features invariantes au domaine (artificiel vs réel) via un discriminateur adverse
- **MK-MMD / alignement de distribution** — minimise la distance statistique entre distributions de features source (artificiel) et cible (réel)
- **Meta-learning + adaptation de domaine** (ex. DAMRN) — transfert du diagnostic à partir de peu d'exemples réels
- Résultats publiés : forte dégradation de performance en transfert direct (sans adaptation), regain significatif avec les méthodes ci-dessus — confirme que l'écart mesuré au brut (sans aucune adaptation) sera probablement le résultat le plus intéressant à publier, précisément parce que la littérature le documente déjà comme non trivial.

**Lien projet** : pour la Phase 3, la baseline "train artificiel → test réel, zero adaptation" *est* la contribution scientifique visée par le brief (§9). Les méthodes de domain adaptation ci-dessus sont une extension possible mais hors scope initial — à mentionner en piste future dans le README plutôt qu'à implémenter, pour rester dans l'esprit "rigueur méthodologique" plutôt que "empiler des techniques".

### 6bis. Fuite de données en bearing ML — caution méthodologique pour Phase 3

Sujet de recherche actif en 2024-2025, pas une lubie du projet : trois publications
independantes convergent sur le split-par-entite comme SEULE methode rigoureuse
(deja la regle docs/brief_projet.md §4 piege #1, appliquee ici avant meme publication de ces
papiers) :

- **Wheat, von Mohrenschildt, Habibi, Al-Ani (2024)**, "Impact of Data Leakage in
  Vibration Signals Used for Bearing Fault Diagnosis" (SSRN/IEEE) — demontre
  empiriquement l'ecart d'accuracy entre split-par-fenetre et split-par-entite sur
  plusieurs methodes de diagnostic.
- **Matania, Cohen, Bechhoefer, Bortman (2024)**, "Test-Training Leakage in
  Evaluation of Machine Learning Algorithms for Condition-Based Maintenance",
  PHM Society European Conference (PHME) — formalise le probleme et propose un
  protocole d'evaluation "leakage-safe".
- **Bechhoefer (McMaster)**, corpus de travaux sur la conception d'essais CBM —
  souligne en particulier le risque d'auto-correlation intra-actif quand les
  mesures repetees d'un meme roulement sont trop rapprochees dans le temps
  (pertinent pour Paderborn : les 20 mesures par roulement/condition ne sont
  probablement PAS independantes entre elles, voir `docs/known_issues.md`).

**Le split-par-fenetre reste la pratique dominante dans ~80% des papiers publies
sur CWRU** (constat de la litterature, pas une estimation du projet) — gonfle
artificiellement l'accuracy en laissant fuiter la meme entite physique entre
train et test. C'est exactement l'erreur que docs/brief_projet.md §4 interdit depuis le
depart ; ces publications recentes donnent une caution academique citable pour
la defense methodologique en Phase 4, pas une nouvelle regle a appliquer.

**A ne pas oublier pour Phase 3 specifiquement :** le nombre de roulements
uniques disponibles pour l'entrainement (24 sur 32 avec le split actuel) est
reconnu dans cette litterature comme un facteur decisif de la fiabilite des
conclusions - limite structurelle du dataset Paderborn a assumer explicitement,
pas a masquer derriere un chiffre moyen sans intervalle (deja fait, voir
`docs/results_phase2.md` - ecarts-type larges sur les 5 folds).

---

## 7. Synthèse — ce que ça change concrètement pour le projet

| Constat de la recherche | Action projet |
|---|---|
| ISO 13374 formalise le pipeline acquisition→state→health→prognostic | Citer dans README, justifie l'arborescence `src/` |
| Le kurtogramme automatise le choix de bande d'enveloppe | À implémenter dans `src/features/envelope.py`, pas de réglage manuel |
| BPFO+BPFI=n·fr et FTF≈BPFO/n | Ajouter comme test unitaire de cohérence, en plus du calcul direct |
| MCSA nécessite charge ≥40 % et est sensible aux harmoniques réseau | Vérifier les conditions de charge Paderborn avant de conclure sur l'objectif secondaire |
| Domain adaptation artificiel→réel = sujet de recherche actif avec dégradation documentée | La baseline "zero adaptation" est le résultat principal ; adaptation de domaine = piste future, pas obligation |
| PdM 4.0 recouvre diagnostic + pronostic ; le projet ne fait que le diagnostic | Nommer précisément la portée dans le README pour ne pas sur-vendre vs la RUL |
| Edge/fog/cloud valorise les modèles légers | Argument coût de calcul en complément de l'argument coût capteur du §9 |

---

## Sources

**Geometrie roulements — datasets du projet (§2bis, `configs/bearing_geometry.yaml`)**
- [Case Bearing Data Center — bearing information (6205/6203 SKF, CWRU)](https://engineering.case.edu/bearingdatacenter/bearing-information)
- [MAFAULDA — page officielle dataset (UFRJ)](https://www02.smt.ufrj.br/~offshore/mfs/page_01.html)
- [Rexnord ZA-2115 double row bearing test rig (NASA IMS)](https://www.researchgate.net/figure/Bearing-test-rig-Four-Rexnord-ZA-2115-double-row-bearings-were-installed-on-one-shaft-as_fig4_221226818)
- [LDK UER204 bearing specification sheet (XJTU-SY)](https://www.researchgate.net/figure/LDK-UER204-bearing-specification-sheet_tbl1_370453378)
- [NSK 6804 datasheet (RS Online)](https://docs.rs-online.com/b5cd/A700000014623780.pdf)
- [6804 bearing specifications — 13 balls confirmation](https://www.bearingsrus.com/6804-2rs-fbj)

**Paliers et types de roulements**
- [SKF Split plummer block housings SNL/SE](https://www.skf.com/us/products/mounted-bearings/bearing-housings/split-pillow-block-housings-snl-2-3-5-6-series)
- [SKF Y-bearing Plummer Block Units (SY/SYH/SYJ/SYM)](https://www.qualitybearingsonline.com/skf/y-bearings/pillow-block)
- [Guide des roulements — ERIKS](https://eriks.fr/fr/societe/know-how-hub/blog/guide-roulements/)
- [NTN-SNR — Notions generales, types de roulements](https://www.ntn-snr.com/sites/default/files/2017-01/01-Notions_generales.pdf)

**Normes vibratoires**
- [ISO 20816-3 — Comprehensive Guide](https://dspanalytic.com/en/sin-categorizar/iso-20816-3-comprehensive-guide-for-the-evaluation-of-vibration-on-rotating-machinery/)
- [ISO 10816-3 Vibration Severity: Zones, Limits](https://www.fabrico.io/blog/iso-10816-3-vibration-severity/)
- [ISO 13373-1:2002 — General procedures](https://www.iso.org/standard/21831.html)
- [ISO 13373-2:2005 — Processing, analysis and presentation](https://www.iso.org/obp/ui/#iso:std:iso:13373:-2:ed-1:en)
- [ISO 18436-2:2014 — Qualification du personnel](https://www.iso.org/standard/50447.html)
- [ISO 13374 condition monitoring standard (architecture)](https://www.researchgate.net/figure/SO-13374-condition-monitoring-standard_fig3_268347497)

**Fréquences de défaut & analyse d'enveloppe**
- [Bearing Fault Frequencies: BPFO, BPFI, BSF & FTF Formulas](https://vibromera.eu/glossary/bearing-fault-frequencies/)
- [Bearing Fault Detection Vibration Analysis](https://ncd.io/blog/bearing-fault-detection-vibration-analysis/)
- [Rolling Element Bearing Fault Diagnosis — MATLAB](https://www.mathworks.com/help/predmaint/ug/Rolling-Element-Bearing-Fault-Diagnosis.html)

**Kurtosis spectral / kurtogramme**
- [The spectral kurtosis: Application to vibratory surveillance (Antoni)](https://www.researchgate.net/publication/229335575_The_spectral_kurtosis_Application_to_the_vibratory_surveillance_and_diagnostics_of_rotating_machines)
- [Optimised Spectral Kurtosis for bearing diagnostics](https://www.sciencedirect.com/science/article/abs/pii/S0888327015005993)
- [A Spectrum Detection Approach Based on Spectral Kurtosis](https://onlinelibrary.wiley.com/doi/10.1155/2017/6106103)

**MCSA**
- [Motor Current Signature Analysis (MCSA): A Complete Guide](https://tractian.com/en/glossary/motor-current-signature-analysis)
- [Motor Current Signature Analysis for Bearing Fault Detection — ScienceDirect](https://www.sciencedirect.com/science/article/pii/S2211812814003861)
- [Motor Current Signature Analysis (MCSA) for Predictive Maintenance](https://sensemore.io/motor-current-signature-analysis-mcsa-for-predictive-maintenance/)

**Maintenance 4.0 / PHM / IoT**
- [The Evolution of Maintenance Strategies](https://sensemore.io/the-evolution-of-maintenance-strategies/)
- [Predictive maintenance in Industry 4.0: survey of planning models and ML](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11157603/)
- [Standards for PHM Techniques within Manufacturing Operations](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=916376)
- [Analyzing the impact of edge, fog and cloud computing on predictive maintenance in IIoT](https://link.springer.com/article/10.1007/s10791-025-09653-8)

**RUL / pronostic**
- [A comprehensive overview of remaining useful life prediction](https://www.sciencedirect.com/science/article/pii/S2666827025000878)
- [Remaining Useful Life Prediction Method for Bearings — LSTM uncertainty](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9228128/)

**Généralisation artificiel → réel**
- [Domain Adaptation Meta-Relation Network — human-induced to natural faults](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11991577/)
- [Domain Adaptation from Simulation to Reality — GAN + MK-MMD](https://doi.org/10.3390/app16031407)
- [Domain Adversarial Transfer Learning Bearing Fault Diagnosis](https://doi.org/10.3390/s25061851)
