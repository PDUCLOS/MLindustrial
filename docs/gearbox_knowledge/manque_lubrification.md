# Manque de lubrification (starvation)

## Pourquoi c'est un mode à part, pas une variante de [[deterioration_dent]]

Un manque de lubrification n'endommage pas une dent en particulier — il
dégrade le film d'huile qui sépare TOUTES les surfaces en contact
simultanément. La signature vibratoire est donc **globale**, pas localisée
sur un arbre/étage précis, contrairement à une dent cassée.

## Mécanisme

Rupture ou amincissement du film lubrifiant → frottement de glissement
accru entre les flancs de dent en prise (au lieu du roulement quasi pur
attendu) → rigidité de contact modifiée → l'énergie vibratoire à GMF et ses
harmoniques augmente.

## Signature vibratoire (sourcée)

> "Vibration levels increase consistently with lubricant volume reduction,
> indicating higher friction between meshing teeth" — hausse **cohérente**
> des amplitudes aux harmoniques de GMF **ET** de leurs bandes latérales,
> pas un pic isolé.

Différence clé avec la [[deterioration_dent|dent cassée]] : la hausse
touche plusieurs harmoniques et bandes latérales **en même temps** et de
façon **globalement proportionnelle** à la sévérité du manque d'huile
(dose-réponse), alors qu'une dent cassée produit un choc dominant unique,
localisé à un arbre précis.

## Piste complémentaire : courant moteur (MCSA)

Une méthode dédiée existe pour diagnostiquer un manque de lubrification via
l'analyse du courant statorique du moteur (MCSA) — cohérent avec l'angle
coût-capteur déjà présent dans ce projet (`docs/theorie_reference.md` §4) :
le courant moteur est déjà disponible sur tout variateur, sans capteur
vibratoire supplémentaire. Le couple résistant augmente avec le
frottement accru → signature détectable côté électrique, pas seulement
vibratoire.

## Indices terrain complémentaires (non vibratoires)

- Élévation de température (thermographie, sonde) — le frottement accru
  dissipe de la chaleur.
- Analyse d'huile — comptage de particules, viscosité, teneur en eau :
  détecte la cause AVANT que la vibration ne bouge, utilisé en
  complément du vibratoire dans l'industrie (délai d'anticipation cité :
  3 à 10 semaines avant défaillance en combinant les deux méthodes).

## Sources

- [Influence of Lubricant Starvation on Gearbox Vibration Signatures for Condition Monitoring — Academia/Huddersfield](https://www.academia.edu/80947748/Influence_of_Lubricant_Starvation_on_Gearbox_Vibration_Signatures_for_Condition_Monitoring)
- [Condition Monitoring of Lubricant Starvation Based on Gearbox Vibration Signature — University of Huddersfield](https://pure.hud.ac.uk/en/publications/condition-monitoring-of-lubricant-starvation-based-on-gearbox-vib/)
- [Novel Diagnosis Technologies for a Lack of Oil Lubrication in Gearmotor Systems, Based on Motor Current Signature Analysis — PMC](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9736848/)
- [Gearbox Condition Monitoring: Oil Analysis & Vibration — Oxmaint](https://oxmaint.com/industries/manufacturing-plant/gearbox-condition-monitoring-oil-analysis-vibration)
