# Glossaire pédagogique du dashboard

**Date :** 2026-09-01
**Cible :** opérateur / chef d'atelier qui regarde le dashboard, pas analyste ni data scientist.
**Sources :** `docs/theorie_reference.md` (normes et physique), `docs/known_issues.md`
(limites observées sur Paderborn). Les nuances techniques citées sont signalées
explicitement — un opérateur qui voit un chiffre bizarre doit pouvoir comprendre
pourquoi sans qu'on lui cache la complexité.

Chaque entrée suit un format strict pour permettre l'intégration dans `app/dashboard.py`.

---

## RMS (vibration)

**En une phrase :** c'est la "puissance moyenne" de la vibration sur la durée
de la mesure, en g (accélération).

**Analogie :** imaginez un seau qu'on remplit d'eau pendant une seconde en
ouvrant un robinet dont le débit oscille. Le RMS, c'est la hauteur d'eau
STABLE qu'on aurait si le débit était constant et produisait la même quantité
totale. Un signal avec de gros pics brefs mais peu de signal entre les pics
peut avoir le même RMS qu'un signal plus régulier et plus "continu" — d'où
l'utilité des autres indicateurs (kurtosis, crest factor) pour compléter.

**Pourquoi ça compte :** le RMS est l'indicateur de base qu'on suit dans le
temps. Quand il monte progressivement, la machine "vibre plus en moyenne" —
souvent le premier signe qu'un défaut s'installe (jeu qui s'agrandit,
lubrification qui se dégrade, etc.).

**A ne pas confondre avec :** le RMS en vitesse (mm/s) des normes ISO 20816
utilisées en conventionnel — ce projet mesure en g (accélération), voir
l'entrée "Unité g vs mm/s".

---

## Kurtosis

**En une phrase :** la kurtosis mesure à quel point le signal a des "pics
violents" par rapport à son niveau moyen, indépendamment de l'amplitude
globale.

**Analogie :** comparez deux salles de concert, l'une avec une acoustique
régulière (son stable) et l'autre où quelqu'un tape périodiquement sur une
tambour. Les deux peuvent avoir la même "puissance moyenne" (même RMS), mais
la seconde a des CHOCS très visibles. La kurtosis, c'est ce qui distingue
"régulier" de "régulier avec des claques dedans" — un nombre sans dimension
(autour de 3 pour un signal purement aléatoire, bien plus haut quand il y a
des impulsions).

**Pourquoi ça compte :** c'est l'indicateur qui réagit le plus tôt à un
défaut naissant sur roulement — bien avant que le RMS ne bouge. Un défaut
d'écaillage crée des micro-chocs à chaque passage d'un élément roulant sur
l'aspérité, et la kurtosis les voit immédiatement, là où le RMS lisse tout
sur la durée de mesure.

**A ne pas confondre avec :** "niveau de vibration". La kurtosis est une
mesure de FORME du signal (y a-t-il des pics ou non ?), pas d'amplitude (le
signal est-il fort ou faible ?). Sur Paderborn, on observe même l'inverse
du sens naïf : les roulements "sains" ont une kurtosis moyenne plus haute
(14.6) que les défauts artificiels (13.5) ou réels (7.4) — pas un bug,
juste que la kurtosis brute ne marche pas dans le sens attendu sur ce
dataset précis (cf. `docs/known_issues.md` § "Confirmation sur le dataset
complet"). Pour exploiter la kurtosis il faut l'analyse d'enveloppe, qui
isole la signature impulsionnelle du défaut du bruit de fond.

---

## Crest factor (facteur de crête)

**En une phrase :** c'est le rapport entre la valeur maximale instantanée du
signal et son RMS — il mesure à quel point les pics dépassent le niveau moyen.

**Analogie :** si le RMS est la "hauteur d'eau moyenne dans le seau", le
crest factor, c'est "combien la vague la plus haute dépasse la surface
calme". Un sinus pur a un crest factor autour de 1.4 ; un signal avec des
chocs brefs peut avoir un crest factor de 5, 10, ou plus. C'est un
indicateur "low-cost" (une seule formule) de la présence d'impulsions.

**Pourquoi ça compte :** c'est l'indicateur le plus immédiat pour détecter
qu'un roulement commence à avoir des chocs — il est sur le dashboard parce
que c'est un bon premier filtre, peu coûteux à calculer, réagit vite. En
complément de la kurtosis (qui dit "il y a des impulsions" avec une mesure
statistique) et du RMS (qui dit "ça vibre plus en moyenne"), le crest
factor répond à "ça tape fort par rapport au niveau normal ?".

**A ne pas confondre avec :** la kurtosis. Les deux mesurent "ça tape", mais
la kurtosis est une moyenne statistique sur tout le signal, alors que le
crest factor ne regarde que LE plus gros pic. Très sensible au bruit
parasite (un seul coup dans le microphone fait monter le crest factor sans
rien dire de la machine).

---

## Seuil / seuil d'alerte

**En une phrase :** c'est la valeur de l'indicateur au-dessus de laquelle on
décide que la machine "sort de l'ordinaire" et qu'il faut agir (programmer
une intervention, alerter, etc.).

**Analogie :** le thermostat d'un four. Vous réglez 180°C ; au-dessus, il
clignote. La valeur du seuil n'a pas de sens physique en soi — c'est un
CHOIX qui dépend de combien de fausses alertes vous tolérez (trop bas = on
croit à un défaut qui n'existe pas, trop haut = on rate un défaut réel). Sur
ce projet, le seuil est data-driven : on le calibre sur les données Paderborn
elles-mêmes (les roulements "sains" donnent une distribution, le seuil est
placé pour séparer au mieux sain et défaillant), PAS un seuil universel
type norme ISO.

**Pourquoi ça compte :** le seuil, c'est la frontière entre "tout va bien" et
"agir". Mal calibré, on a soit trop de fausses alertes (l'opérateur finit
par ignorer le dashboard, aussi dangereux que de ne pas en avoir), soit on
rate des défauts. C'est pourquoi on en voit plusieurs par indicateur dans
certains tableaux — plusieurs compromis faux-alerte / défaut-manqué, à
choisir selon la criticité de la machine.

**A ne pas confondre avec :** un seuil de norme. La norme ISO 20816 (voir
"Unité g vs mm/s") propose des seuils absolus en mm/s pour des classes de
machines, mais on ne peut PAS les utiliser ici directement — il faudrait
convertir l'accélération g en vitesse mm/s par intégration fréquentielle,
ce qui n'est pas implémenté dans ce projet.

---

## F1 macro

**En une phrase :** c'est une note de fiabilité du modèle entre 0 et 1, qui
répond à "sur 100 alertes que le modèle déclenche, combien sont correctes
en tenant compte qu'il y a beaucoup plus de cas sains que de cas en
défaut".

**Analogie :** imaginez un détecteur de fumée qui se déclenche 100 fois. Si
90 fois c'est pour de vrai (un feu) et 10 fois c'est une fausse alerte (le
rôti du four), c'est un bon détecteur. L'accuracy classique dirait "90/100
= 90 % de bien", mais ça ne dit rien sur l'asymétrie : si dans la vraie vie
il y a 1000 cuissons sans feu et 1 feu, le détecteur peut avoir 99 %
d'accuracy juste en criant au feu TOUJOURS (et en ayant raison 1 fois sur
1001). La F1 macro pénalise ce comportement en regardant la qualité des
alarmes, pas le taux global.

**Pourquoi ça compte :** sur Paderborn il y a 6 roulements "sains", 12
défauts artificiels, 14 défauts réels — pas 50/50. Une F1 macro de 0.74
(vibration seule, GBM) est un résultat CORRECT dans ce contexte, pas un
"74 % de réussite au hasard". Mais ça veut aussi dire que le modèle rate
1 défaut sur 4 en moyenne — à interpréter selon la criticité de la machine
concernée.

**A ne pas confondre avec :** l'accuracy (le taux global de bonnes
prédictions), qui surclasserait artificiellement un modèle qui se contente
de dire "sain" tout le temps. Voir `docs/known_issues.md` § 4 du brief
(règle "F1 macro ou balanced accuracy, pas accuracy") pour la justification.

---

## Validation croisée / écart-type sur les folds

**En une phrase :** on ne donne pas un seul chiffre de performance mais une
FOURCHETTE, parce que la valeur dépend de quels roulements on a mis dans
l'ensemble de test — et il faut le savoir pour ne pas se raconter
d'histoires.

**Analogie :** vous mesurez le temps de trajet domicile-travail sur une
semaine. Vous trouvez 22, 25, 27, 31, 35 minutes. Le temps "moyen" ne
suffit pas — la plage (de 22 à 35) vous dit s'il faut partir 30 min plus
tôt ou si une marge de 5 min suffit. La validation croisée, c'est pareil
pour un score de modèle : au lieu d'un seul trajet, on répète la mesure
plusieurs fois avec des trajets différents (différents découpages
train/test), et on regarde la moyenne ET la dispersion.

**Pourquoi ça compte :** sur ce projet, Phase 2 a donné F1 macro = 0.738 ±
0.208 (vibration seule). L'écart-type 0.208 est ÉNORME — le modèle passe
de "aussi bon qu'on espère" à "à peine mieux qu'un tirage à pile ou face"
selon le fold. C'est une information aussi importante que la moyenne :
prétendre "F1 = 0.74" sans la fourchette, c'est comme dire "mon trajet
dure 28 minutes" en cachant qu'il varie du simple au double. Le choix du
fold (quels roulements) influence le résultat — il faut le savoir avant
de comparer deux modèles entre eux.

**A ne pas confondre avec :** un intervalle de confiance statistique. Les
folds ne sont pas forcément indépendants (cf. `docs/known_issues.md` §
"Auto-corrélation intra-actif" — Bechhoefer : 20 mesures sur un même
roulement ne sont pas 20 observations indépendantes), donc la dispersion
observée sous-estime probablement la vraie incertitude.

---

## BPFO / BPFI / BSF / FTF (les 4 fréquences caractéristiques)

**En une phrase :** ce sont les 4 "notes" que fait un défaut de roulement
selon l'endroit où il se trouve — chacune vaut la bague extérieure (BPFO),
la bague intérieure (BPFI), un élément roulant (BSF) ou la cage (FTF).

**Analogie :** un roulement, c'est un orchestre. La fréquence de rotation
est la mesure, et chaque instrument (bague extérieure, bague intérieure,
bille, cage) joue sa propre "fréquence de passage" sur le défaut. Si vous
entendez un La répété 46 fois par seconde, c'est une bague extérieure
(BPFO) qui a un éclat à 900 tr/min. Un La légèrement différent à 74 Hz,
c'est la bague intérieure. Reconnaître la "note" vous dit OÙ regarder
quand vous démontez le roulement.

**Pourquoi ça compte :** ces 4 fréquences sont calculables UNIQUEMENT à
partir de la géométrie du roulement (nombre de billes, diamètres, angle de
contact) et de la vitesse de rotation — pas besoin de mesurer pour les
connaître à l'avance. Sur le dashboard, elles servent de "fréquences
cibles" où aller chercher les raies dans le spectre vibratoire. Une raie
nette à BPFO@900rpm=46.06 Hz sur ce projet dit "bague extérieure, vérifie".

**A ne pas confondre avec :** des seuils d'alerte. Ce ne sont pas des
"valeurs normales / anormales" mais des FRÉQUENCES THÉORIQUES. L'amplitude
de la raie à cette fréquence est ce qui compte pour le diagnostic, pas
la fréquence elle-même. Relations utiles à connaître pour vérifier un
calcul à la main : `BPFO + BPFI = n × fr` (n = nombre de billes) et
`FTF ≈ BPFO / n` (cf. `docs/theorie_reference.md` § 2).

---

## Analyse d'enveloppe

**En une phrase :** c'est une technique pour rendre visibles les "tics-tacs"
cachés d'un défaut de roulement dans un signal vibratoire complexe.

**Analogie :** vous êtes dans un train et vous entendez un bruit sourd
régulier, sans pouvoir dire si c'est une roue voilée ou un défaut de
boîte. Si vous prenez un micro qui n'écoute que les hautes fréquences et
que vous "extrait" le volume de ces hautes fréquences au cours du temps,
vous obtenez une "enveloppe" — et sur cette enveloppe, les tics-tacs
d'un défaut (BPFO par exemple) apparaissent clairement, alors qu'ils
étaient noyés dans le bruit global. C'est exactement ce que fait la
chaîne : filtre passe-bande → transformée de Hilbert (extraction du
"volume" du signal filtré) → FFT de ce volume.

**Pourquoi ça compte :** sans analyse d'enveloppe, les défauts naissants
de roulement sont quasi invisibles dans le spectre brut (cf.
`docs/theorie_reference.md` § 3 : "à faible vitesse ou avec un fort bruit
de fond, ces raies n'apparaissent quasiment jamais dans le spectre brut").
L'enveloppe est ce qui fait la différence entre "on voit le défaut" et
"on ne voit rien". Le kurtogramme, c'est l'automatisation du choix de la
bonne bande de fréquences à écouter — sans lui, il faut régler "à l'oreille"
pour chaque roulement.

**A ne pas confondre avec :** la simple FFT. La FFT du signal brut montre
surtout le bruit de fond, les forces d'excitation basses fréquences, et
masque les raies de défaut. L'enveloppe isole ces raies en deux étapes
(démodulation d'amplitude), c'est une technique différente, complémentaire
de la FFT.

---

## Unité g (accélération) vs mm/s (vitesse)

**En une phrase :** ce projet mesure en g (accélération), pas en mm/s
(vitesse) — ce n'est pas une conversion d'unité mais un changement de
grandeur physique, et ça change à quoi correspondent les seuils.

**Analogie :** imaginez un compteur de vitesse de voiture en km/h (vitesse)
contre un accéléromètre qui mesure les à-coups au démarrage en m/s²
(accélération). Les deux bougent quand la voiture bouge, mais ne disent
pas la même chose : le premier dit "vous roulez vite", le second dit "vous
avez freiné fort". Un défaut de roulement (qui crée des micro-chocs) se
voit beaucoup mieux en accélération — d'où le choix de ce projet.

**Pourquoi ça compte :** les normes ISO 20816 qui classent les machines en
zones A/B/C/D s'expriment en mm/s RMS de VITESSE, sur la bande 10-1000 Hz.
On ne peut PAS appliquer directement ces seuils à un signal en g — il
faudrait intégrer l'accélération en vitesse par fréquence (1/jω), ce qui
n'est pas implémenté dans ce projet. Conséquence pratique : les seuils du
dashboard sont calibrés sur les données Paderborn elles-mêmes (data-driven),
pas sur un référentiel normatif universel.

**A ne pas confondre avec :** un changement d'unité gratuit. 1 g = 9.81
m/s², mais passer de g à mm/s demande une opération physique
(intégration), pas une multiplication. Voir
`docs/known_issues.md` § "Unités capteurs Paderborn - vibration en g" pour
le détail et l'incertitude résiduelle (capteur Paderborn = accéléromètre
PCB 336C04 100 mV/g, calibration non confirmée par le format .mat lui-même).

---

## health_state / defect_origin (sain, défaut artificiel, défaut réel)

**En une phrase :** "health_state" dit si le roulement est considéré comme
fonctionnant normalement ou non, et "defect_origin" dit COMMENT le défaut a
été créé — les deux sont des ÉTIQUETTES dataset, pas des diagnostics.

**Analogie :** imaginez un test de crash automobile. "health_state" c'est
"intact / accidenté". "defect_origin" c'est "accidenté volontairement par
un marteau (artificiel) vs accidenté par 200 000 km de route sur autoroute
(réel)". Les deux disent "accidenté", mais savoir COMMENT ça s'est passé
change ce qu'on attend du diagnostic. Un défaut créé au marteau en usine a
un bord net, géométriquement parfait ; un défaut "réel" par fatigue
accumulée est diffus, progressif, souvent multiple. Un capteur qui
détecte très bien le premier n'est pas garanti de voir le second.

**Pourquoi ça compte :** sur ce projet, l'objectif principal Phase 3 est
EXACTEMENT cette question — "est-ce qu'un modèle entraîné sur défauts
artificiels (bord net) marche sur défauts réels (diffus) ?". Réponse
courte : c'est le mur rencontré en production, et c'est ce qu'on veut
chiffrer. C'est aussi pour ça qu'on a 14 défauts réels (vieillissement
accéléré) et 12 défauts artificiels (perçage, EDM, gravure) — pas
seulement pour avoir plus de données, pour tester ce transfert.

**A ne pas confondre avec :** un vrai diagnostic. Ce sont des étiquettes
dataset, pas un avis sur l'état réel de VOTRE machine. Un roulement étiqueté
"sain" dans Paderborn était "sain" au sens de l'expérimentateur
(qualification par rodage) — pas une garantie qu'il le reste en service chez
vous.

---

## Asset / Machine / Site / Zone (vocabulaire factory-builder)

**En une phrase :** ce sont les 4 niveaux d'organisation d'un parc machine
— du plus large au plus précis : Site (l'usine) > Zone (l'atelier dans
l'usine) > Machine (l'équipement) > Asset (le roulement ou sous-composant
surveillé dans la machine).

**Analogie :** c'est comme l'adresse d'un composant. "Lyon" c'est le site,
"Atelier 3" c'est la zone, "Presse 12" c'est la machine, "roulement
palier moteur côté arbre" c'est l'asset. Sur une presse, on peut avoir 5
ou 6 assets différents (un par roulement ou par engrenage important) qui
vivent et meurent indépendamment — chacun a son historique vibratoire,
son seuil, son alerte.

**Pourquoi ça compte :** la valeur métier, c'est de pouvoir dire "le
roulement X de la machine Y de la zone Z du site W a une alerte depuis
3 jours" — pas juste "il y a une vibration anormale quelque part". C'est
aussi ce qui permet de mutualiser les modèles (un modèle appris sur les
roulements du site A peut servir de base pour le site B), ou de spécialiser
(un modèle par type de machine). C'est le vocabulaire de base du
factory-builder utilisé dans le dashboard, à maîtriser pour naviguer.

**A ne pas confondre avec :** un asset = une machine. Un asset peut être
un sous-composant (roulement, engrenage, moteur) ; une machine peut
contenir plusieurs assets. Sur Paderborn, l'asset est le roulement, pas
la machine (qui est partagée entre tous les roulements testés).

---

## "Aucune donnée" / état unknown

**En une phrase :** quand un asset vient d'être créé et n'a pas encore été
mesuré, son état est "inconnu" — NI sain, NI défaillant, juste pas
encore diagnostiqué.

**Analogie :** vous voyez un voyant "contrôle moteur" allumé sur le
tableau de bord d'une voiture. Le voyant est "allumé" — il NE vous dit
PAS que le moteur est cassé, il vous dit que le système a détecté quelque
qu'il veut faire vérifier. "Aucune donnée" sur le dashboard, c'est
l'équivalent d'un voyant qui n'a jamais été testé : on ne peut RIEN en
déduire sur l'état de la machine, il faut une mesure pour avoir un
diagnostic. Afficher "sain" par défaut serait mentir ; afficher
"défaillant" par défaut serait aussi mentir.

**Pourquoi ça compte :** l'opérateur qui regarde le dashboard doit savoir
faire la différence entre "machine connue, RAS" et "machine pas encore
mesurée, on ne sait pas". Mélanger les deux mènerait à des décisions
fausses (arrêter une machine qui n'a jamais été mesurée "au cas où", ou
ignorer un asset fraîchement créé qui attend sa première mesure). Le
dashboard affiche explicitement un état "inconnu" / "aucune donnée" pour
éviter cette confusion.

**A ne pas confondre avec :** "sain". L'état "unknown" est un état
provisoire normal sur un asset fraîchement créé, pas un diagnostic
défavorable. Voir `app/dashboard.py` (section "Aucune donnée") pour
l'affichage.

---

## Notes finales pour l'intégration

- Ce glossaire est volontairement SANS référence explicite à des formules
  mathématiques (sauf les 4 fréquences caractéristiques BPFO/BPFI/BSF/FTF
  qui sont nommées par convention universelle). Si une formule est utile
  pour l'intégration dashboard, voir `docs/theorie_reference.md`.
- Les analogies sont choisies pour quelqu'un qui connaît le monde
  industriel / atelier mais pas la science des données. Si la cible change
  (ex. présentation à un comité de direction), une variante "executive
  summary" serait à rédiger séparément.
- Les nuances physiques (kurtosis = forme pas amplitude, g ≠ mm/s,
  Paderborn en g pas mm/s, motifs kurtosis inversés, false brinelling
  NON CONFIRMÉ) sont toutes sourcées dans `docs/known_issues.md` et
  `docs/theorie_reference.md` — ne pas les simplifier davantage sans
  contresigner Patrice.
