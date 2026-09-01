# Problemes connus / decisions en suspens

## Kurtogramme / energie BPFO-BPFI instable (2026-08-31)

**Constat** (sur K001/KA01/KA04, condition N09_M07_F10, 900 rpm) :

- Energie BPFO (enveloppe) : K001 (sain) = 0.000235 > KA01 (artificiel, bague ext.) = 0.000016 > KA04 (reel, bague ext.) = 0.000005. Sens inverse de l'attendu physique.
- K001 (sain) montre un pic de spectre d'enveloppe exactement a 52.58 Hz. Note initiale (2026-08-31) : "colle sur le BPFO theorique (51.51 Hz)" - **corrige le 2026-08-31 (voir plus bas) : ce calcul de BPFO utilisait n_balls=9, une valeur non sourcee. Avec la geometrie officielle Paderborn (n_balls=8, confirmee sur PDF constructeur), BPFO@900rpm=46.06 Hz, a 6.5 Hz du pic observe - la coincidence n'existe plus.** Le pic a 52.58 Hz n'est probablement pas une raie de defaut du tout.
- Le kurtogramme (balayage multi-resolution, voir `src/features/envelope.py::kurtogram`) selectionne une bande totalement differente par mesure : 15.8 kHz (K001), 17.9 kHz (KA01), 504 Hz (KA04). Pas de convergence vers une resonance structurelle stable, alors que la resonance capteur/logement devrait etre une propriete mecanique fixe du montage, pas du defaut.

**Hypotheses non tranchees :**

1. Contamination electrique/mecanique du banc pres de 50-52 Hz (secteur EU, engrenage/accouplement), presente sur TOUS les roulements independamment de leur etat, pas un signal de defaut. **Renforcee par la correction de geometrie ci-dessous** : le pic a 52.58 Hz ne correspond a AUCUNE frequence de defaut theorique pour ce roulement (n_balls=8 confirme), ce n'est plus une simple coincidence troublante mais l'explication qui reste sur la table.
2. Le kurtogramme par-signal (cherche le maximum global de kurtosis spectral independamment sur chaque mesure) est instable : il capte "ce qui est le plus impulsif" mesure par mesure, ce qui peut etre un artefact ponctuel plutot que la resonance structurelle reelle.

**Correction de geometrie (2026-08-31) - impact sur tous les calculs BPFO/BPFI/BSF/FTF :**
`configs/bearing_geometry.yaml` indiquait n_balls=9 pour le 6203, annote "a confirmer". La fiche
constructeur officielle Paderborn (bundled avec chaque asset, ex. `data/raw/paderborn/K001/K001.pdf`)
donne : 8 elements roulants, diametre bille 6.75 mm, diametre primitif 29.05 mm, angle 0 deg -
verifie identique sur K001 (fabricant IBU) et KA01 (fabricant MTK). Corrige dans le config et
re-seede en base (`scripts/init_db.py`). Toute frequence BPFO/BPFI/BSF/FTF calculee avant cette
date avec n_balls=9 est fausse et ne doit pas etre reutilisee. Nouvelles valeurs :

| Condition | fr | BPFO | BPFI | BSF | 2xBSF | FTF |
|---|---|---|---|---|---|---|
| 900 rpm (N09) | 15.00 Hz | 46.06 Hz | 73.94 Hz | 30.54 Hz | 61.07 Hz | 5.76 Hz |
| 1500 rpm (N15) | 25.00 Hz | 76.76 Hz | 123.24 Hz | 50.89 Hz | 101.78 Hz | 9.60 Hz |

**Limite structurelle independante de la vitesse (pas corrigible en changeant le rpm) :** pour ce
roulement, BPFO = 3.071x fr et BSF = 2.036x fr - a n'importe quelle vitesse, BPFO tombe a 2.4% du
3e harmonique de rotation (desalignement/jeu mecanique) et BSF a 1.8% du 2e harmonique. Un
desalignement ou un jeu mecanique peut donc mimer une raie BPFO/BSF a l'oeil, quelle que soit la
vitesse choisie - seule une resolution frequentielle fine (grande duree d'acquisition) ou un suivi
d'ordre (tachymetrie) separe les deux. Voir `src/features/fault_frequencies.py::mains_separation_hz`
et `docs/theorie_reference.md` section RPM.

**Collision secteur specifique a 1500 tr/min (la condition la plus utilisee sur Paderborn) :**
2x la frequence de rotation = 2 x 25 Hz = 50.0 Hz = frequence secteur EU EXACTEMENT. A cette
vitesse, un desalignement (signature 2x) est indiscernable d'une contamination electrique secteur
dans le spectre vibratoire seul - il faudrait un canal supplementaire (courant, ou mesure a vide
moteur coupe) pour trancher. A 900 tr/min, 2x=30 Hz, pas de collision.

**Decision (2026-08-31) :** ne pas bloquer sur ce point. Le run complet Paderborn
(`scripts/build_dataset.py`) est lance avec uniquement les features temporelles
(RMS, kurtosis, crest factor, skewness, peak-to-peak) - `src/features/envelope.py`
reste implemente mais son appel est desactive dans le pipeline (`--with-envelope`
a reactiver explicitement). Les features BPFO/BPFI/BSF/FTF ne sont PAS encore
fiables et ne doivent pas etre utilisees en l'etat pour un resultat rapporte.

## Hypothese "false brinelling" pour le motif kurtosis sain > defaut - NON CONFIRMEE (2026-09-01)

Piste suggeree pour expliquer le motif documente ci-dessus et dans
`docs/results_phase2.md` (kurtosis moyenne : sain 14.63 > artificiel 13.47 >
reel 7.36, sens inverse de l'attendu physique) : le **false brinelling** est un
mode de degradation specifique des roulements soumis a des vibrations a
l'ARRET (billes qui oscillent micrometriquement dans la piste sans rotation,
usure localisee aux points d'espacement inter-billes, souvent avec oxydation).
Un roulement K001-K006 stocke/manipule sur ou pres d'un banc vibrant entre les
sessions d'essai pourrait accumuler ce defaut sans qu'il s'agisse d'un defaut
de fabrication - ce qui gonflerait la kurtosis des roulements "sains" par un
mecanisme different des defauts artificiels/reels etudies.

**Verification faite (2026-09-01) :** lecture complete de `data/raw/paderborn/K00{1,2,3,4,5,6}/K00X.pdf`
(6 factsheets constructeur officielles) avec `pdftotext`. Synthese :

| Asset | Manufacturer | Lifetime (h) | Load (N) | Speed (RPM) | Comment |
|---|---|---|---|---|---|
| K001 | IBU | (a verifier - a completer) | 3000 | (a verifier) | vide |
| K002 | IBU | **19** | 3000 | **2900** | vide |
| K003 | IBU | **1** | 3000 | **3000** | vide |
| K004 | IBU | **5** | 3000 | **3000** | vide |
| K005 | IBU | **10** | 3000 | **3000** | vide |
| K006 | IBU | **16** | 3000 | **2900** | vide |

Observations :
- **Tous Manufacturer = IBU** (Industriewerk Bad Nauheim, sous-traitant allemand) - pas
  d'identifiant de lot ("Sample number" vide sur les 6).
- **Geometrie 6203 identique sur les 6** : 8 billes, 6.75 mm bille, 29.05 mm pitch, 0 deg - coherent
  avec `configs/bearing_geometry.yaml`.
- **Lifetime tres variable (1h, 5h, 10h, 16h, 19h, ...)** - chaque roulement a ete rode
  pendant une duree differente, mais sans details sur les conditions intermediaires
  (stockage, manipulation, environnement entre rodage et essai final).
- **Aucun "Comment" rempli sur les 6** - aucun indice textuel.
- **Pas de date de fabrication, pas de date d'installation, pas de mention
  transport/stockage** - les factsheets ne documentent QUE les conditions de rodage
  (lifetime cumule, vitesse de rodage, charge appliquee pour qualifier le roulement
  comme "sain").
- **Load 3000 N constant** sur les 6 (charge de rodage, pas la charge d'essai finale).
- **Speed 2900-3000 RPM** (vitesse de rodage, pas la vitesse d'essai finale qui sera
  900 RPM pour N09 ou 1500 RPM pour N15).

**Conclusion :** les factsheets Paderborn **ne permettent PAS de tester l'hypothese
false brinelling**. Le champ "Comment" qui aurait pu mentionner stockage/transport est
vide sur les 6 roulements. Pas de date de fabrication, donc pas de calcul d'age du
roulement a l'instant de l'essai. Pas de mention de la Chaine logistique (fournisseur
-> Paderborn -> banc d'essai).

**Statut : hypothese a considerer comme **non testable** avec la documentation
Paderborn officielle.** Ne pas presenter comme explication etablie dans un rapport
final. Pour reprendre cette piste serieusement, il faudrait :
- Interview de C. Lessmeier (Paderborn, contact dans la factsheet) sur la logistique
- Inspection visuelle des 6 roulements K001-K006 apres essais (s'ils sont encore dispo)
- Comparaison avec un dataset neuf (CWRU ou autre) pour isoler l'effet Paderborn
- Recherche d'un signal caracteristique (raie a la BPFO ou ses harmoniques MEME sur
  roulement "sain", amplitude modulee differemment d'un vrai defaut actif) - methode
  spectrale, pas seulement kurtosis globale.
Ne pas presenter comme explication etablie dans un rapport final. Si reprise :
chercher un signal caracteristique du false brinelling (usure periodique a
l'espacement inter-billes -> raie a la frequence BPFO ou ses harmoniques MEME
sur roulement "sain", amplitude modulee differemment d'un vrai defaut actif)
plutot que de se contenter de la kurtosis globale, qui ne permet pas de
distinguer cette hypothese des autres (contamination secteur ~50Hz, deja
documentee ci-dessus, kurtogramme instable).

## Pieges methodologiques supplementaires a checker avant Phase 3 (2026-09-01)

Releves lors d'une revue de litterature recente (data leakage bearing ML, voir
`docs/theorie_reference.md` §6bis), pas encore verifies sur ce dataset :

- **Auto-correlation intra-actif** (Bechhoefer) : les 20 mesures Paderborn par
  roulement/condition ne sont probablement PAS independantes (meme session
  d'essai, quelques minutes d'ecart) - a garder en tete pour l'interpretation
  des ecarts-type Phase 2 (deja larges, voir `docs/results_phase2.md`), et
  pour Phase 3 si le decoupage par mesure plutot que par roulement est
  reintroduit ailleurs.
- **Defauts co-occurrents** (Matania 2024) : Paderborn a des roulements
  `defect_location=both` (KB23/24/27, bague int.+ext. simultanement, voir
  `configs/paderborn_bearings.yaml`) - une classification 5 classes (sain,
  bague int., bague ext., bille, cage) les force dans une seule case et perd
  l'info. A checker si Phase 3 fait de la classification multi-classe fine
  (F-12 du backlog) plutot que binaire sain/faulty.
- **Sequential overfitting** : si plusieurs modeles/variantes sont evalues sur
  le MEME test set (ex. essayer plusieurs seuils de kurtogramme jusqu'a
  obtenir un resultat propre), la selection elle-meme devient une fuite -
  utiliser un test set unique fixe pour la comparaison finale Phase 3, pas
  un jeu de test reutilise pour choisir entre versions du pipeline.
- **Sensibilite a l'initialisation** (deep learning) : pertinent seulement si
  le CNN 1D (brief §5) est lance - necessiterait plusieurs seeds repetees, pas
  un seul entrainement, pour toute comparaison avec le GBM.

**Confirmation sur le dataset complet (2026-08-31, apres run complet 2559 mesures) :**
Le motif tient sur l'ensemble, pas seulement l'echantillon de 3 roulements :
kurtosis vibration moyen = sain (na) 14.63, artificiel 13.47, reel 7.36. La
kurtosis brute est donc INVERSEMENT correlee a la severite du defaut sur ce
dataset avec ces conditions - confirmation que c'est un phenomene systematique
(coherent avec l'hypothese "domine par l'accouplement moteur/banc"), pas un
artefact de petit echantillon. C'est un resultat honnete a garder tel quel :
la baseline kurtosis brute ne marche pas dans le sens naif attendu sur
Paderborn, ce qui justifie la necessite de l'enveloppe/kurtogramme (une fois
celui-ci fiabilise) plutot que de l'invalider.

**A faire avant de re-activer l'enveloppe :**

- Determiner une bande de demodulation par CONSENSUS sur plusieurs mesures
  (ex. moyenne des kurtogrammes sur tout un roulement, ou sur toute une
  condition) plutot qu'un choix independant par mesure.
- Verifier la contamination ~50 Hz : inspecter le spectre brut (pas juste
  l'enveloppe) pres de 50/100/150 Hz sur plusieurs roulements sains, comparer
  a la frequence secteur EU.
- Revoir la question sur un plus grand echantillon (les 32 roulements, pas 3)
  avant de conclure quoi que ce soit definitivement - l'echantillon actuel est
  trop petit pour distinguer un vrai probleme structurel d'un artefact des 3
  fichiers choisis.

## F-07 : kurtogramme consensus - resultat (2026-09-01)

**Regle d'arret pour la validation sur 32 roulements (actee 2026-09-01,
avant lancement)** : soit le motif converge de facon reproductible sur la
majorite des roulements a defaut reel restants -> active F-06/F-07/F-08 par
defaut ; soit l'ambiguite multi-candidats type KA04 se repete sans regle de
discrimination fiable -> desactive F-07/F-08 definitivement, documente en
resultat negatif (meme logique que docs/brief_projet.md regle 4 : baseline/resultat
honnete plutot qu'un raffinement sans fin). Pas de troisieme issue "on
creuse encore" - 0.5-1 jour, une des deux conclusions, pas de prolongation
sans nouvelle decision explicite.

**Deux corrections apportees, distinctes :**

1. **Bug de bord STFT** (trouve en validant la correction ci-dessous, pas
   cherche a priori) : le kurtogramme convergeait vers les bins DC (0 Hz) et
   Nyquist (32000 Hz exact a 64 kHz) - kurtosis spectral artificiellement
   gonfle par la fuite spectrale du fenetrage aux bords, pas une resonance
   physique. Corrige dans `kurtogram()` : exclut desormais tout bin dont la
   bande [fc-bandwidth, fc+bandwidth] deborderait de [min_freq_hz, Nyquist[.
2. **Consensus multi-mesures** : `average_kurtogram_map` / `consensus_resonance_band`
   (`src/features/envelope.py`) moyennent le kurtosis spectral sur TOUTES les
   mesures d'un roulement (80 mesures, 4 conditions confondues - hypothese :
   la resonance capteur/logement est independante de la vitesse) au lieu
   d'un choix independant par mesure. `fault_frequency_energies` accepte
   maintenant un `resonance_band` precalcule ; `scripts/build_dataset.py`
   calcule le consensus une fois par roulement avant la boucle de features.

**Validation empirique sur le meme trio K001/KA01/KA04 documente ci-dessus**
(apres les deux corrections) :

| Roulement | Bande par-signal (1 mesure) | Bande CONSENSUS (80 mesures) |
|---|---|---|
| K001 (sain) | 15616-16128 Hz | 15616-16128 Hz |
| KA01 (artificiel, bague ext.) | 17664-18176 Hz | 15872-16384 Hz |
| KA04 (reel, bague ext.) | 544-560 Hz | 672-704 Hz (voir nuance ci-dessous) |

**Ce qui marche** : K001 et KA01 convergent maintenant vers une bande quasi
identique (~15872-16128 Hz, chevauchement direct) - physiquement coherent
avec l'hypothese "resonance fixe du montage capteur/logement, partagee entre
roulements testes sur le meme banc". C'est exactement le motif que le
consensus etait cense retablir, et il le fait.

**Nuance non resolue - KA04 porte DEUX candidats concurrents** : l'inspection
des kurtogrammes par niveau montre que KA04 a en realite deux bandes fortes -
~688 Hz (dominant aux niveaux 2-4, resolution grossiere) ET ~15872-16128 Hz
(dominant aux niveaux 6-8, MEME bande que K001/KA01). Le consensus actuel
choisit le maximum global toutes resolutions confondues et retient 688 Hz
(kurtosis moyen 17.4) de justesse devant 15872 Hz (16.08) - un ecart etroit,
pas une victoire franche. La bande partagee ~16 kHz EST bien presente dans
KA04, l'algorithme actuel la masque simplement en ne gardant qu'un seul
candidat par roulement. Piste ouverte, deux lectures possibles : (a) 688 Hz
est un artefact propre a la session KA04 (cf. confusion date/asset deja
documentee - remontage capteur different ce jour-la) ; (b) 688 Hz est un vrai
signal de defaut (KA04 = defaut reel bague exterieure) - a rapprocher des
frequences caracteristiques de defaut (voir `configs/bearing_geometry.yaml`,
BPFO@900rpm=46.06Hz - 688/46.06~14.9, harmonique elevee mais pas absurde pour
un defaut avec beaucoup de contenu impulsif). PAS TRANCHE - ne pas publier de
conclusion sur cette frequence sans creuser davantage (energie d'enveloppe
aux deux bandes, comparaison sur plus de roulements a defaut reel bague ext.).

**Decision** : le consensus corrige le probleme original documente plus haut
(instabilite PAR MESURE au sein d'un meme roulement - resolu, K001 est
identique entre 1ere mesure et moyenne sur 80). Le probleme DE FOND
(convergence K001/KA01 vs divergence KA04) est ameliore mais pas clos - a
tester sur l'ensemble des 32 roulements avant de considerer F-07/F-08
pleinement fiables et de les activer par defaut dans le pipeline. Tests
synthetiques dans `tests/test_envelope.py` (reproduisent le motif d'artefact
documente ici et verifient que le consensus le corrige). `--with-envelope`
reste desactive par defaut dans `scripts/build_dataset.py` en attendant cette
validation plus large.

## Confusion date d'essai / asset / defect_origin (2026-08-31)

**Constat (analyse temporelle, pas boxplot - voir dashboard "Derive
temporelle" et `src/evaluation/temporal_drift.py`) :**

Chaque asset Paderborn est teste sur UN SEUL jour calendaire (min(timestamp)
== max(timestamp)::date pour 31/32 roulements ; le seul qui deborde, KI04,
deborde de quelques heures a cheval sur minuit). Consequence directe :
`asset_id`, date d'essai et `defect_origin` sont largement confondus sur ce
dataset -

- real : 10/14 assets testes juin-aout 2014
- artificial : 10/12 testes nov 2014 - sep 2015
- healthy (na) : 6/6 testes mars-oct 2015 UNIQUEMENT (jamais avant)

**Correlation valeur moyenne (kurtosis, vibration) vs date d'essai, calculee
au niveau ASSET (n=32, pas au niveau mesure - 80 mesures/asset ne sont pas
80 observations independantes, pseudo-replication a eviter) :**

| Groupe | n assets | corr vs date d'essai |
|---|---|---|
| tous | 32 | +0.49 |
| artificial | 12 | +0.72 |
| real | 14 | +0.46 |
| healthy (na) | 6 | -0.76 (n=6, quasi non interpretable) |

**Verification "meme jour" (le seul levier du dataset pour separer effet
jour / effet roulement) :** deux roulements REELS, meme localisation (inner),
meme methode (fatigue_pitting), meme jour (2014-06-17) - KI17 (5.94) vs KI18
(10.48), ratio 1.8x. La variance inter-roulement individuel est donc du meme
ordre de grandeur que la variance inter-jour observee ailleurs. Autre paire
meme jour (2015-03-27), origines differentes : KI08 artificial (13.08) vs
KA30 real (10.89), ecart plus faible que KI17/KI18 pourtant du meme groupe.

**Lecture honnete :** la correlation date/kurtosis existe et n'est pas
negligeable (+0.49 a +0.72 selon le groupe), mais le design d'acquisition
(un jour = un roulement = une seule etiquette) rend `defect_origin`, date
d'essai et identite du roulement structurellement inseparables au niveau
asset. Impossible avec ce dataset de trancher entre "le banc derive dans le
temps" et "32 roulements physiquement differents ont une variance intrinseque
large" - la paire KI17/KI18 (meme jour, meme defaut, 1.8x d'ecart) montre que
la seconde explication a elle seule pourrait deja expliquer une bonne partie
du signal. Les deux causes coexistent probablement, non decomposables ici.

**Consequence directe sur la Phase 3 (objectif principal, artificiel->reel) :**
entrainer sur artificiel et tester sur reel revient AUSSI a entrainer sur les
essais precoces (2014) et tester sur des essais plus tardifs (2015) pour la
plupart des roulements reels. Tout ecart de performance mesure en Phase 3
melangera "nature du defaut" et "epoque d'acquisition", sans moyen de les
separer avec ce seul dataset. A formuler explicitement dans le rapport final
(pas un "l'ecart artificiel->reel coute X points de F1" non qualifie) - une
limite methodologique a assumer, pas a cacher (docs/brief_projet.md section 9).

**Confusion supplementaire, defect_method quasi = defect_origin :** sur
Paderborn, real = fatigue_pitting (13/14) + plastic_deform (1/14) ; artificial
= drilling/edm/engraving (12/12, sauf 1 "drilling?_to_verify" a clarifier
aupres de la doc Paderborn). La generalisation artificiel->reel teste donc
aussi, implicitement, un transfert "endommagement localise a bord net
(perce/grave/EDM) -> usure diffuse multi-points (piqures de fatigue)" - motif
deja documente dans la litterature (voir `docs/theorie_reference.md` section
6, domain adaptation) comme une cause connue de mauvaise generalisation,
independamment de toute question de date d'essai.

## Unites capteurs Paderborn - vibration en g (acceleration), PAS en mm/s (2026-09-01)

**Constat :** le capteur vibration Paderborn est un accelerometre PCB
Piezotronics 336C04 (100 mV/g), charge amplifier Kistler type 5015 - voir
`data/raw/paderborn/K001/measuring_log_K001.pdf`. Le canal `vibration` mesure
donc de l'**acceleration**, pas de la vitesse. Les zones ISO 20816-3 (A/B/C/D,
`docs/theorie_reference.md` §1) sont definies en **mm/s RMS de vitesse**, une
grandeur physique differente - pas juste une conversion d'unite, une
integration frequentielle (acceleration -> vitesse, typiquement 1/jω dans le
domaine frequentiel) est necessaire avant toute classification ISO. **Non
implementee dans ce projet.**

**Incertitude residuelle :** le champ `Unit` du .mat est vide (non documente
par le format d'export lui-meme) - l'hypothese "l'export est deja en g" est
**inferee** de l'ordre de grandeur observe (mediane ~0.07, max ~4.88 sur
K001), physiquement plausible pour un banc de roulement, mais PAS confirmee
par une source explicite. Voir `src/data/units.py::SENSOR_REGISTRY` pour le
detail et la citation - `confidence="inferred"`, pas `"confirmed"`.

**Consequence :** toutes les features `rms`/`peak_to_peak` sur le canal
vibration sont en g, pas en mm/s. Aucune comparaison directe avec un seuil
ISO 20816 publie n'est valide en l'etat. Le dashboard n'affiche aucune alerte
basee sur un seuil absolu pour cette raison - seul le seuil data-driven
(`src/models/baseline.py`, entraine sur les donnees Paderborn elles-memes,
sans reference a une norme externe) est utilisable actuellement.

**Normalisation multi-sources (2026-09-01) :** `src/data/units.py` centralise
desormais un registre (source, channel) -> unite canonique + niveau de
confiance, pour que `signal.unit`/`feature.unit` restent comparables entre
sources futures (pression, debit, temperature - voir `docs/scaling_path.md`).

**Nuance importante (2026-09-01, ref. methodologie IFM moneo) :** l'absence de
mm/s n'est PAS une limitation pour l'objectif de ce projet. Le choix
vitesse/acceleration depend du TYPE de defaut cible, pas d'une preference
arbitraire :
- **Vitesse (mm/s, basse frequence <1 kHz)** : balourd, jeu mecanique,
  desalignement, courroie - defauts cinematiques basse frequence. C'est le
  domaine des zones ISO 20816.
- **Acceleration (g, jusqu'a 10 kHz)** : roulements, frottement, engrenage,
  encrassement, cavitation, choc/impact, lubrification - defauts a fort
  contenu haute frequence. C'est exactement le domaine de ce projet
  (diagnostic roulement) ET exactement ce que mesure le capteur Paderborn.

Consequence : integrer acceleration->vitesse pour calculer une zone ISO 20816
n'apporterait PAS un diagnostic roulement plus fin - ISO 20816 sert a
qualifier la sante globale machine (bande basse frequence), pas a diagnostiquer
un defaut roulement specifique (bande haute frequence, deja couverte par
kurtosis/enveloppe/kurtogramme). Les deux approches sont complementaires, pas
substituables l'une a l'autre - ne pas presenter l'absence de zones ISO comme
un manque a combler en priorite, c'est un choix d'outil coherent avec l'objectif.
Chaque nouvelle source doit y etre enregistree AVANT tout calcul de feature
cross-source, avec la meme rigueur de citation (mesure documentee vs inferee).
