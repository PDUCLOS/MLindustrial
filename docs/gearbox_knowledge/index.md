# Diagnostic moto-réducteur — index

Base de connaissance (compatible Obsidian — ouvrir `docs/gearbox_knowledge/`
comme vault, les `[[liens]]` sont natifs) sur la détérioration de dent
d'engrenage et le manque de lubrification, en vue d'un algorithme de
détection. Construite pour ce projet le 2026-09-02, sourcée — voir chaque
note pour ses références.

**Lien code** : [[algorithme_propose]] s'appuie sur `src/features/gear_frequencies.py`
(rapport de réduction cinématique, GMF par étage) et sur le principe déjà
en place dans `src/features/fault_frequencies.py`/`envelope.py` pour les
roulements — même logique appliquée aux engrenages.

## Notes

- [[gear_mesh_frequency]] — la fréquence d'engrènement (GMF), fondement de tout le reste
- [[deterioration_dent]] — dent cassée/fissurée, piqûres (pitting), écaillage, usure, grippage
- [[manque_lubrification]] — signature vibratoire spécifique, distincte d'un défaut de dent
- [[indicateurs_condition]] — RMS, kurtosis, FM4, NA4, NB4, ratio d'énergie : lequel pour quoi
- [[algorithme_propose]] — pipeline de détection combinant tout ce qui précède
- [[arbre_decision]] — arborescence de diagnostic (type "atelier"), sourcée SEW-Eurodrive + littérature

## Ce qui n'est PAS couvert ici

- Train épicycloïdal (planétaire) — voir `src/features/gear_frequencies.py::PlanetaryNotImplementedError`, cinématique différente non traitée
- Défauts de roulement du réducteur — déjà couverts par `docs/theorie_reference.md` §2-3 (BPFO/BPFI/BSF/FTF, enveloppe, kurtogramme), le [[algorithme_propose]] les référence plutôt que de les redupliquer
