# Indicateurs de condition — lequel pour quoi

Synthèse comparative, sourcée, pour choisir l'indicateur pertinent selon le
mode de [[deterioration_dent]] ou de [[manque_lubrification]] visé. Ne pas
tout calculer sans discernement — même discipline que
`docs/theorie_reference.md` (baseline avant modèle complexe).

| Indicateur | Calcul (principe) | Sensible à | Limite |
|---|---|---|---|
| **RMS** | racine carrée de la moyenne quadratique | dégradation globale avancée | peu sensible en phase précoce, "average à below average" pour le pitting spécifiquement |
| **Crest factor** | pic / RMS | chocs impulsifs (dent cassée) | dilué si plusieurs sources d'impulsion |
| **Kurtosis** | 4ᵉ moment normalisé | impulsivité (chocs) | déjà documenté comme piégeux sur roulements dans ce projet (`docs/known_issues.md`) — vérifier la même prudence ici |
| **FM0** | pic-à-pic / somme des amplitudes GMF+harmoniques | défaut global du train | grossier, sert de premier tri seulement |
| **FM4** | 4ᵉ moment du signal résiduel (après retrait GMF+harmoniques, nécessite TSA) | fissure limitée à peu de dents | nécessite un tachymètre/order tracking pour le TSA |
| **NA4** | FM4 amélioré, normalisé par la variance du signal résiduel accumulée dans le temps | **le plus sensible pour le pitting** (sourcé) | nécessite aussi TSA — nécessite un historique de référence sain |
| **NB4** | enveloppe (Hilbert) du signal filtré autour de GMF dominant | fissure localisée, alternative à NA4 sans décomposition harmonique complète | plus récent, moins de retour d'expérience industriel que NA4 |
| **Énergie des bandes latérales** | somme de l'énergie aux fréquences GMF ± k×f_arbre | localise l'ÉTAGE en cause (via `src/features/gear_frequencies.py`) | nécessite de connaître la géométrie (déjà en base pour ce projet) |
| **Ratio d'énergie GMF / harmoniques** | amplitude(2×GMF+3×GMF) / amplitude(GMF) dans le temps, en tendance | **manque de lubrification** (hausse cohérente multi-harmonique) | signal de tendance, pas un seuil instantané — nécessite plusieurs mesures dans le temps |

## Priorité TSA (Time Synchronous Averaging)

FM4/NA4/NB4 nécessitent un signal synchronisé à la rotation (moyennage sur
un nombre entier de tours, élimine tout ce qui n'est pas cohérent avec la
vitesse de rotation). Nécessite un top-tour ou un encodeur — **absent des
datasets actuels du projet** (Paderborn fournit un canal vitesse mais pas
un top-tour synchrone exploitable pour du TSA classique, voir
`src/features/speed.py`). À vérifier avant de promettre NA4/NB4 dans
l'algorithme — sinon rester sur RMS/Crest/énergie de bandes latérales
brutes (moins sensibles mais ne nécessitent rien de plus que le signal
vibratoire déjà disponible), voir [[algorithme_propose]].

## Sources

Voir [[deterioration_dent]] et [[manque_lubrification]] pour le détail par
mode — synthèse croisée notamment depuis :
- [A Review of Gearbox Condition Monitoring Based on Vibration Analysis Techniques — ResearchGate](https://www.researchgate.net/publication/226343571_A_Review_of_Gearbox_Condition_Monitoring_Based_on_vibration_Analysis_Techniques_Diagnostics_and_Prognostics)
- [An Enhancement to the NA4 Gear Vibration Diagnostic Parameter — ResearchGate](https://www.researchgate.net/publication/235011925_An_Enhancement_to_the_NA4_Gear_Vibration_Diagnostic_Parameter)
