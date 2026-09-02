# Algorithme proposé — détection dent/lubrification

Pipeline concret, construit sur ce qui existe déjà dans le projet
(`src/features/gear_frequencies.py`, `envelope.py`, `fault_frequencies.py`)
plutôt qu'une nouvelle stack. Respecte la même discipline que le reste du
projet : baseline simple d'abord, sourcé, pas de seuil inventé
(`docs/theorie_reference.md`, règle "0 mock").

## Étape 0 — Prérequis géométrie (déjà automatisé)

`GearStage` + `summarize_gear_train()` donnent, pour un réducteur donné,
le GMF de chaque étage et le rapport de réduction total. C'est le socle :
sans ces fréquences de référence, aucun indicateur ci-dessous n'a de sens.

## Étape 1 — Features par mesure (pas de TSA requis, cf. [[indicateurs_condition]])

Pour chaque étage `i` (GMF connu via `StageFrequencies.gmf_hz`) :

1. **Énergie de bande latérale** à GMF ± k×f_arbre(étage i), k=1..3 — même
   fonction que `envelope.py::band_energy`, appliquée directement au
   spectre brut autour de chaque GMF plutôt qu'après enveloppe (le GMF est
   déjà une porteuse identifiable, pas besoin de démodulation d'enveloppe
   comme pour un défaut de roulement).
2. **Ratio harmoniques/fondamentale** : (amplitude 2×GMF + 3×GMF) /
   amplitude GMF — indicateur de tendance pour [[manque_lubrification]].
3. **RMS et crest factor** globaux (déjà implémentés,
   `src/features/time_domain.py`) — première ligne de détection, peu
   spécifique mais gratuite.

## Étape 2 — Triage par signature (règles, pas un modèle)

```
SI choc dominant net à 1×f_arbre(étage i) dans la forme d'onde temporelle
   ET bandes latérales asymétriques fortes à GMF(i) ± f_arbre(i)
→ dent cassée/fissurée, étage i, ARRÊT MACHINE RECOMMANDÉ (voir [[arbre_decision]])

SINON SI ratio harmoniques/fondamentale en hausse sur PLUSIEURS étages
   ET pas de choc net localisé
   ET (si disponible) température en hausse / courant moteur (MCSA) anormal
→ suspicion manque de lubrification, VÉRIFIER NIVEAU/QUALITÉ HUILE D'ABORD
  (action la moins chère, voir [[manque_lubrification]])

SINON SI énergie de bande latérale en hausse progressive, diffuse, étage i
   (pas de choc net)
→ suspicion pitting/usure diffuse étage i, surveillance renforcée

SINON
→ pas de signature caractéristique reconnue, RMS/crest en veille standard
```

## Étape 3 — Tendance dans le temps (pas un seuil instantané)

Le [[manque_lubrification|manque de lubrification]] se lit en TENDANCE
(dose-réponse), pas sur une mesure isolée — nécessite un historique
comparable à ce que fait déjà `src/evaluation/temporal_drift.py` pour les
roulements (dérive temporelle par asset). Réutiliser le même principe
plutôt qu'écrire un module de tendance séparé.

## Où ça s'arrête (avant tout ML)

Ce pipeline est **entièrement basé sur des règles physiques sourcées**, pas
un modèle entraîné. Cohérent avec la philosophie du projet
(`docs/brief_projet.md` §1 : baseline avant modèle). Voir
[[arbre_decision_ml]] pour la question "est-ce qu'on a même besoin de ML
ici, et sur quelles données" — ne pas construire un modèle avant d'avoir
épuisé cette approche par règles ET d'avoir des données labellisées
suffisantes (aucun réducteur réel avec vérité terrain n'est encore dans ce
projet, voir `docs/known_issues.md`).
