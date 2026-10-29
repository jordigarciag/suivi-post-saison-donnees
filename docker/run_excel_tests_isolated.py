# Lecture du fichier — Lancement des tests Excel dans l’image de test prévue.
# On conserve le code de sortie des tests pour que leur échec ne soit pas annoncé comme une réussite
# du conteneur.
#

"""Lance la suite Excel sans transmettre le chemin du code monté aux sous-processus.

Le parent importe le code métier monté en lecture seule. Les sous-processus CLI
créés par les tests doivent utiliser leur copie temporaire, pas ce code monté.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest


# On garde dans PROJECT un objet chemin local ; sa construction seule ne prouve pas que le fichier
# existe.
PROJECT = Path("/opt/project")


def main() -> int:
    # On construit source en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    source = PROJECT / "src"
    # On construit tests en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    tests = PROJECT / "tests"
    # Cette branche traite le cas où la condition (source /
    # 'suivi_traitements_post_saison/ingestion/excel_reader.py').is_file() n’est pas remplie.
    if not (
        source / "suivi_traitements_post_saison/ingestion/excel_reader.py"
    ).is_file():
        # On interrompt cette branche avec RuntimeError : 'Code Excel attendu absent du montage en
        # lecture seule.'.
        raise RuntimeError("Code Excel attendu absent du montage en lecture seule.")
    # Cette branche traite le cas où la condition (tests / 'test_tracking_versioning.py').is_file()
    # n’est pas remplie.
    if not (tests / "test_tracking_versioning.py").is_file():
        # On interrompt cette branche avec RuntimeError : 'Fichier de tests Excel absent du montage en
        # lecture seule.'.
        raise RuntimeError("Fichier de tests Excel absent du montage en lecture seule.")
    # sys.path ne se transmet pas aux processus fils ; PYTHONPATH, lui, se transmet.
    os.environ.pop("PYTHONPATH", None)
    # On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables
    # dans ce contexte.
    sys.path.insert(0, str(source))
    # On garde dans suite la valeur renvoyée par unittest.defaultTestLoader.discover.
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(tests), pattern="test_tracking_versioning.py"
    )
    # On garde dans count la valeur renvoyée par suite.countTestCases.
    count = suite.countTestCases()
    # On vérifie ce cas avant la suite : count diffère de 37.
    if count != 37:
        # On interrompt cette branche avec RuntimeError.
        raise RuntimeError(
            f"Suite inattendue : {count} tests au lieu de 37 ; verifier les imports et le fichier fourni."
        )
    # On affiche ce texte explicite dans la sortie du programme.
    print("Essai Excel isole : 37 tests ; code monte en lecture seule.", flush=True)
    # On affiche ce texte explicite dans la sortie du programme.
    print("Chemin source du parent non transmis aux sous-processus CLI.", flush=True)
    # On garde dans result la valeur renvoyée par unittest.TextTestRunner(verbosity=2).run.
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return 0 if result.wasSuccessful() else 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
