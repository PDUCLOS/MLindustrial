# Arborescence de diagnostic (atelier)

Arbre de décision pratique, format "chef d'atelier" — cohérent avec
`docs/brief_projet.md` §9 (interprétabilité). Sources : synthèse de
[[deterioration_dent]] + [[manque_lubrification]], recoupée avec la notice
d'exploitation réducteurs SEW-Eurodrive (consultée le 2026-09-02 —
recommandations génériques de mise à l'arrêt sur changement de bruit/
vibration/température, usure de couronne annulaire citée comme cause de
changement de bruit, desserrage de moyeu, risque de brinelling par choc sur
arbre).

```
Changement de bruit / vibration / température signalé sur un moto-réducteur
│
├─ Choc net, répétitif, période = 1 tour d'un arbre précis (temporel) ?
│  └─ OUI → [[deterioration_dent|dent cassée/fissurée]] probable, étage
│           identifié par la fréquence du choc (src/features/gear_frequencies.py)
│           → ARRÊT RECOMMANDÉ, inspection avant reprise (SEW : éviter la
│             propagation d'un choc mécanique en fonctionnement)
│
├─ Hausse cohérente des harmoniques GMF + bandes latérales, PLUSIEURS étages,
│  pas de choc net ?
│  ├─ Température également en hausse ? → [[manque_lubrification]] probable
│  │  → VÉRIFIER NIVEAU/QUALITÉ HUILE (action la moins chère, faire AVANT
│  │    de condamner un composant mécanique)
│  └─ Température stable → vérifier fixation/serrage (SEW : desserrage de
│     moyeu cité comme cause de changement de bruit), fondation rigide
│
├─ Énergie de bande latérale en hausse progressive, diffuse, un seul étage,
│  pas de choc net ?
│  └─ OUI → [[deterioration_dent|pitting/usure diffuse]] probable, étage
│           identifié → surveillance renforcée, pas d'arrêt immédiat sauf
│           tendance qui s'accélère (voir [[algorithme_propose]] étape 3)
│
├─ Roulement d'entrée (premier train) suspecté plutôt que l'engrenage ?
│  └─ Basculer sur `docs/theorie_reference.md` §2-3 (BPFO/BPFI/BSF/FTF,
│     enveloppe, kurtogramme) — physique différente, pipeline déjà en place
│     pour ce projet (roulements Paderborn)
│
└─ Aucune signature reconnue → RMS/crest en veille standard, pas d'action
   → si le doute persiste, ne PAS inventer un diagnostic : documenter
     "cause non identifiée" plutôt qu'une hypothèse non vérifiée (règle
     "0 mock" appliquée au diagnostic, pas seulement aux données)
```

## Facteur aggravant : marge de conception (facteur de service)

Le **facteur de service (Service Factor, AGMA)** = rapport entre la
capacité nominale du réducteur (couple/puissance) et le besoin réel de
l'application. C'est une **marge de dimensionnement, pas une tolérance de
surcharge** — un facteur de service de 2.0 signifie que le réducteur est
dimensionné pour 2× le besoin en fonctionnement NORMAL, pas qu'il supporte
200% de surcharge ponctuelle sans dommage (précision importante, souvent
mal comprise — voir sources).

**Deux signaux de contexte qui aggravent la criticité d'une détection** :

1. **Vitesse/couple d'entrée proche de la valeur limite catalogue** → le
   réducteur fonctionne déjà en haut de sa plage nominale, moins de marge
   avant qu'une dégradation ([[deterioration_dent]], [[manque_lubrification]])
   ne devienne critique.
2. **Facteur de service faible** (proche de 1) → peu de marge de
   dimensionnement dès l'origine — une dégradation qui serait tolérable sur
   un réducteur largement dimensionné (SF élevé) devient rapidement
   critique ici.

**Combinaison des deux** (fonctionnement proche des limites d'entrée + SF
faible) = situation à traiter en priorité absolue dans
[[arbre_decision|l'arbre ci-dessus]] — même signature vibratoire, urgence
différente selon ce contexte. À capturer comme métadonnée machine (voir
la demande de flexibilité du modèle de données évoquée en session — champ
`service_factor` et limites catalogue à ajouter au modèle machine/asset
si ce sujet est repris).

## Sources (facteur de service)

- [Service Factor — ScienceDirect topic overview](https://www.sciencedirect.com/topics/engineering/service-factor)
- [Gearbox service factor and service class explained — Motion Control Tips](https://www.motioncontroltips.com/gearbox-service-factor-and-service-class-explained/)
- [Selecting an Appropriate Gear Reducer — WorldWide Electric](https://worldwideelectric.com/articles/selecting-an-appropriate-gear-reducer/)

## Limite assumée

Cet arbre est un outil de PREMIER tri, pas un remplacement du jugement d'un
analyste vibratoire certifié (`docs/theorie_reference.md` §1, ISO 18436).
Il n'a pas encore été validé sur un vrai réducteur avec vérité terrain — le
projet n'en a pas encore, voir [[arbre_decision_ml]] pour ce que ça implique
sur la pertinence de tenter du ML sur ce sujet précis aujourd'hui.
