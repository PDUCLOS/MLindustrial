# Fréquence d'engrènement (GMF)

## Définition

À chaque instant, un nombre entier de dents est en contact entre le pignon
menant et la roue menée. La fréquence à laquelle une paire de dents entre
en prise est la **Gear Mesh Frequency (GMF)** :

```
GMF = N_menant × f_menant = N_mené × f_mené
```

Identité invariante le long de l'engrènement (les deux formulations donnent
le même nombre) — implémentée et testée dans
`src/features/gear_frequencies.py::compute_gear_train` (voir
`test_gmf_invariant_driving_equals_driven`). Valable pour tous les types
d'engrenages à axes fixes : droits (spur), hélicoïdaux, coniques droits,
spiro-coniques. Pour une **roue et vis**, `N_menant` = nombre de filets de
la vis (1, 2 ou 4 typiquement, pas un nombre de dents ordinaire) — même
formule.

Le [[deterioration_dent|train épicycloïdal]] suit une loi différente (non
implémentée, voir index).

## Signature spectrale saine

Un engrenage sain montre des raies nettes à GMF, 2×GMF, 3×GMF, avec de
petites bandes latérales symétriques à ±1×f_arbre autour de chaque
harmonique — c'est la modulation résiduelle normale (jeu de fabrication,
excentricité résiduelle), pas un défaut. C'est le niveau de référence par
rapport auquel on juge une dégradation ([[deterioration_dent]]) ou un
[[manque_lubrification]].

## Lien avec le premier train de roulement

L'arbre d'entrée du réducteur (le plus rapide) porte généralement le
premier roulement surveillé. `src/features/gear_frequencies.py::first_stage_input_bearing_frequencies`
délègue directement à `src/features/fault_frequencies.py::all_fault_frequencies`
— même physique BPFO/BPFI/BSF/FTF que pour un roulement Paderborn, juste
appliquée à la vitesse d'entrée du réducteur.

## Sources

- [Gear Mesh Frequency: Formula, Sidebands, and Fault Signs — Fabrico](https://www.fabrico.io/blog/gear-mesh-frequency/)
- [A Review of Gearbox Condition Monitoring Based on Vibration Analysis Techniques — ResearchGate](https://www.researchgate.net/publication/226343571_A_Review_of_Gearbox_Condition_Monitoring_Based_on_vibration_Analysis_Techniques_Diagnostics_and_Prognostics)
