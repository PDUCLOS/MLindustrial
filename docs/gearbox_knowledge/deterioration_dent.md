# Détérioration de dent d'engrenage

Quatre modes principaux, signatures vibratoires distinctes. Toutes se lisent
par rapport à la référence [[gear_mesh_frequency|GMF saine]].

## Dent cassée / fissurée (broken / cracked tooth)

**Mécanisme** : une dent perd sa capacité à transmettre l'effort normalement
— rupture nette (cassée) ou fissure progressive à la base de la dent
(fatigue).

**Signature** :
- **Domaine temporel** : un choc net, répété une fois par tour de l'arbre
  porteur de la dent défectueuse — un pic dominant unique dans la forme
  d'onde temporelle, à la période exacte de rotation de cet arbre.
- **Domaine fréquentiel** : bandes latérales fortes et **asymétriques**
  autour de GMF, 2×GMF, espacées de ±1×f_arbre (parfois harmoniques
  d'ordre supérieur : ±2×, ±3×f_arbre selon la sévérité).
- **Localisation** : le choc identifie SANS ambiguïté l'arbre porteur (donc
  l'étage) via `src/features/gear_frequencies.py` — chaque étage a son
  propre f_arbre, la fréquence de répétition du choc pointe directement
  vers l'étage en cause.

Une fissure progresse généralement en 3 phases : initiation (peu ou pas
visible en vibratoire), propagation (croissance mesurable de l'énergie des
bandes latérales, cf. [[indicateurs_condition]]), rupture finale (RMS/crête
augmentent brutalement juste avant la casse).

## Piqûres de fatigue (pitting)

**Mécanisme** : fatigue de contact en surface — micro-fissures sous la
surface active qui débouchent en piqûres, généralement réparties sur
plusieurs dents plutôt que localisées sur une seule (contrairement à la
dent cassée).

**Signature** : dégradation plus **diffuse** que la dent cassée — hausse
progressive du niveau de bandes latérales sur plusieurs dents, pas un choc
unique dominant. **NA4 identifié comme l'indicateur le plus sensible pour
ce mode précis** (voir [[indicateurs_condition]] et sources ci-dessous) —
RMS et FM4 nettement moins sensibles pour le pitting spécifiquement.

## Écaillage (spalling)

**Mécanisme** : détachement de plaques de matière en surface, généralement
une évolution avancée du pitting (les piqûres coalescent). Génère des
chocs répétés à chaque passage sur la zone écaillée, mais sur une zone
plus étendue qu'une dent cassée unique.

**Signature** : proche de la dent cassée (chocs périodiques) mais énergie
supplémentaire concentrée sur une bande haute fréquence (souvent autour de
2-3×GMF ou d'une résonance structurelle excitée par le choc) — même
principe que l'analyse d'enveloppe pour les roulements
(`src/features/envelope.py`, `docs/theorie_reference.md` §3).

## Grippage / usure adhésive (scuffing / scoring)

**Mécanisme** : rupture locale du film lubrifiant sous forte charge/vitesse
→ soudure micro puis arrachement de matière. **Directement lié au
[[manque_lubrification]]** — c'est souvent la conséquence mécanique d'un
défaut de lubrification prolongé, pas un mode indépendant.

**Signature** : hausse de bruit large bande + élévation de température
(thermographie complémentaire utile) + dégradation progressive du niveau
GMF, sans choc net localisé (contrairement à la dent cassée).

## Sources

- [An Enhancement to the NA4 Gear Vibration Diagnostic Parameter — ResearchGate](https://www.researchgate.net/publication/235011925_An_Enhancement_to_the_NA4_Gear_Vibration_Diagnostic_Parameter)
- [Evaluation of gear pitting severity by using various condition monitoring indicators — ResearchGate](https://www.researchgate.net/publication/362519308_EVALUATION_OF_GEAR_PITTING_SEVERITY_BY_USING_VARIOUS_CONDITION_MONITORING_INDICATORS)
- [An Analysis of Gear Fault Detection Methods as Applied to Pitting Fatigue Failure Data — ResearchGate/NASA](https://www.researchgate.net/publication/24298069_An_Analysis_of_Gear_Fault_Detection_Methods_as_Applied_to_Pitting_Fatigue_Failure_Data)
- [Development of crack induced impulse-based condition indicators — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0888327021006865)
- SEW-Eurodrive, notice d'exploitation réducteurs : usure de couronne annulaire et desserrage de moyeu cités comme causes de changement du bruit/vibration de fonctionnement (voir [[arbre_decision]] pour la synthèse pratique)
