# Strategie de differentiation

Reflexion du 2026-08-31, apres la mise en place du socle (data Paderborn, DB,
Docker). Question : au-dela de §9 docs/brief_projet.md (deja solide : ecart artificiel/reel
chiffre, argument cout capteur, resultats negatifs assumes), quels angles
supplementaires exploitent reellement les ~20 ans d'experience IoT maintenance
predictive (IFM, Schaeffler, SKF) plutot que de refaire un projet ML generique ?

## Angles identifies

1. **Calculateur ROI capteur** — etant donne un budget / une criticite machine,
   quel jeu de capteurs minimal atteint quel niveau de detection. Direct produit
   de l'experience terrain distribution industrielle ; un profil ML pur ne peut
   pas l'ecrire de facon credible (pas de reference prix/installation reelle).

2. **Taxonomie du gap artificiel -> reel** — ne pas se limiter au chiffre
   (ex. "accuracy -23%"), expliquer le mecanisme : contenu frequentiel different,
   defauts multiples simultanes en conditions reelles vs defaut unique controle
   en artificiel, SNR, severite progressive vs instantanee. C'est l'expertise
   metier qui transforme un score en explication.

3. **Checklist deploiement labo -> atelier** — contraintes reelles de terrain :
   frequence d'echantillonnage disponible cote variateur, bruit EMI sur le signal
   courant moteur, cout retrofit accelerometre vs lecture logicielle deja
   disponible sur variateur existant. Contenu de nature quasi-consulting.

4. **L'architecture multi-source / multi-asset elle-meme** — la plupart des
   projets "bearing fault" publics sont un seul dataset + un CNN + un score.
   Le choix fait ici (generalisation cross-dataset, cross-machine, schema DB
   pret a accueillir pompes/compresseurs via `asset` generique) raconte une
   demarche "pense scalabilite industrielle des la conception", pas seulement
   "un modele qui tourne".

## Decision

- **Angle #1 (calculateur ROI capteur) retenu comme livrable construit** —
  concret, demontrable, differenciant, mobilisable directement en entretien.
  A construire apres le socle features/modeles (Phase 2-3), une fois qu'on a
  de vraies courbes perf/capteur a partir desquelles calculer le ROI (pas de
  chiffres inventes — coherent avec la regle docs/brief_projet.md §9 : jamais de resultat
  sans verification).
- **Angles #2 et #3 retenus comme contenu narratif**, pas de developpement
  logiciel dedie — alimentent le README final et la serie de posts LinkedIn
  (Phase 4), a rediger a partir des resultats reels obtenus en Phase 3.
- **Angle #4 deja en place** — pas d'action supplementaire, juste le nommer
  explicitement comme argument de differentiation dans la restitution finale.

## A ne pas faire

Ne pas disperser l'effort sur les 4 angles en parallele. Le calculateur ROI
n'a de sens qu'une fois les resultats de generalisation (Phase 3) disponibles :
construire un ROI sur des chiffres non verifies serait exactement l'erreur que
docs/brief_projet.md §9 interdit.
