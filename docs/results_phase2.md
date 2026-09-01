# Resultats Phase 2 - baseline seuil et GBM

2026-08-31. Split par asset (jamais par signal). Toutes les evaluations
ci-dessous utilisent une validation croisee **StratifiedGroupKFold, 5 folds,
groupe = asset_id** (`scripts/run_baseline.py`, `scripts/run_gbm.py`) -
metrique F1 macro (classes desequilibrees, docs/brief_projet.md regle #6).

## Pourquoi cross-validation et pas un split unique

Premiere version de ce document (evaluation sur un seul split 24/8 assets)
donnait des chiffres tres differents. En testant ce split sur 5 seeds
differents, le classement vibration/courant/fusion changeait a chaque fois -
avec seulement 32 roulements, un split unique est trop bruite pour conclure.
Corrige avant publication (voir docs/brief_projet.md section 9 : ne jamais presenter un
resultat sans verifier qu'il ne provient pas d'un artefact).

## Baseline seuil (temporel brut, canal vibration)

| Feature | F1 macro (moyenne 5-fold) | Ecart-type | Direction |
|---|---|---|---|
| kurtosis | 0.682 | ± 0.158 | lower_is_faulty (stable sur tous les folds) |
| crest_factor | 0.576 | ± 0.174 | lower_is_faulty (stable) |
| rms | 0.430 | ± 0.090 | INSTABLE - change de sens selon le fold |

## Gradient boosting (XGBoost), comparaison vibration / courant / fusion

| Sensor set | Features | F1 macro (moyenne 5-fold) | Ecart-type |
|---|---|---|---|
| vibration seule | 5 | 0.738 | ± 0.208 |
| fusion (vibration+courant) | 15 | 0.726 | ± 0.222 |
| courant seul | 10 | 0.542 | ± 0.121 |

## Lecture honnete

- **Ecarts-type enormes** (0.12 a 0.22 pour un F1 macro moyen de 0.5 a 0.7) :
  32 roulements, ~6-7 par fold de test, c'est la limite structurelle du
  dataset pour ce genre de comparaison. Aucune conclusion forte ne peut etre
  tiree d'un seul chiffre moyen ici - les intervalles se chevauchent
  largement entre les 3 sensor sets.
- **GBM vibration seule (0.738±0.208) vs baseline kurtosis (0.682±0.158)** :
  le GBM est au-dessus en moyenne mais les intervalles se recouvrent
  largement - PAS un gain "franc" au sens de la regle docs/brief_projet.md #4. Le GBM
  ne bat pas clairement la baseline sur ce dataset avec ces features.
- **Courant seul (0.542±0.121) est la moins bonne option ici**, et la moins
  variable. Ca ne valide PAS l'argument cout capteur (courant moins cher que
  vibration) sur cette tache precise (health_state intra-condition) - a ne
  pas confondre avec l'objectif principal du projet (generalisation
  artificiel->reel, Phase 3), pas encore teste.
- **rms change de direction selon le fold** (parfois "plus haut = defaut",
  parfois l'inverse) : feature non fiable en l'etat, coherente avec le
  constat deja documente dans `docs/known_issues.md`.

## Ce que ces resultats ne disent PAS (a ne pas sur-interpreter)

- Rien sur la generalisation artificiel -> reel (objectif principal, Phase 3
  - health_state seul ici, pas defect_origin).
- Rien sur le cross-condition (piege docs/brief_projet.md #2 - conditions melangees ici).
- L'enveloppe/kurtogramme (BPFO/BPFI...) est desactivee dans ce pipeline
  (voir `docs/known_issues.md`) - ces resultats reposent uniquement sur des
  indicateurs temporels bruts.
- La comparaison vibration/courant n'est valide QUE pour cette tache precise
  et ce dataset - ne pas en tirer une conclusion generale sur l'argument cout
  capteur avant de l'avoir testee sur l'objectif principal.

## Prochaine etape naturelle

Reparer le kurtogramme (bande stable par consensus, voir known_issues.md)
avant de conclure quoi que ce soit sur les features physiques BPFO/BPFI, et
lancer le test artificiel -> reel (Phase 3, objectif principal) plutot que de
continuer a raffiner sur health_state intra-condition qui n'est pas
l'objectif du projet.
