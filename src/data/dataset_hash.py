"""Hash de reproductibilite pour un dossier de donnees processed.

Pas de DVC : un hash de manifest (chemin relatif + taille + sha256 de chaque
fichier, tries, combines) suffit pour pouvoir dire "ce resultat mlflow vient
exactement de cette version du dataset" - traçabilite, pas versioning complet.
"""

import hashlib
from pathlib import Path


def hash_directory(directory: Path, pattern: str = "**/*.parquet") -> str:
    """Sha256 d'un manifest (chemin relatif, taille, sha256 contenu) sur tous
    les fichiers correspondant a `pattern`, tries pour un resultat deterministe
    independant de l'ordre du systeme de fichiers."""
    directory = Path(directory)
    if not directory.exists():
        return "MISSING:" + str(directory)

    files = sorted(directory.glob(pattern))
    manifest = hashlib.sha256()
    for f in files:
        rel = f.relative_to(directory).as_posix()
        content_hash = hashlib.sha256(f.read_bytes()).hexdigest()
        manifest.update(f"{rel}:{f.stat().st_size}:{content_hash}\n".encode())

    if not files:
        return "EMPTY:" + str(directory)
    return manifest.hexdigest()
