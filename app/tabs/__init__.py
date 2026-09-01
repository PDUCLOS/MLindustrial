"""Package tabs : onglets du dashboard, un fichier par onglet.

Chaque onglet expose une fonction render() qui prend les ressources partagees
(engine mlflow/db, session state) en parametre. Le fichier dashboard.py
orchestre juste les appels : un onglet = un import + un appel render().

Ce package permet :
- d'isoler le code de chaque onglet pour limiter les collisions en
  developpement parallele (un fichier par onglet, pas un fichier unique de
  600 lignes)
- de tester un onglet en isolation (les fonctions render sont des fonctions
  ordinaires qui prennent leurs deps en parametre)
- d'ajouter/retirer un onglet sans toucher au reste du dashboard
"""
