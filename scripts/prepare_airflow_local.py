# Lecture du fichier — Génération de la configuration locale initiale d’Airflow.
# On prépare notamment des secrets locaux sans les afficher. La base technique d’Airflow conserve son
# orchestration ; elle n’est pas la base des résultats métier.
#

"""Prépare uniquement les secrets locaux Airflow et leur exclusion Git.
Aucun accès Docker, PostgreSQL, réseau, Excel ou NAS. Aucun secret affiché.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe base64. Ce module sera utilisé par les opérations de ce fichier.
import base64
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe secrets. Ce module sera utilisé par les opérations de ce fichier.
import secrets


def main() -> int:
    # On récupère Path(__file__).resolve().parents[1] et on le garde dans root pour la suite.
    root = Path(__file__).resolve().parents[1]
    # On construit ignore_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
    # crée ni dossier ni fichier.
    ignore_path = root / ".gitignore"
    # On choisit la valeur de ignore_text selon ce test : ignore_path existe. Les deux résultats
    # possibles restent définis explicitement ici.
    ignore_text = (
        ignore_path.read_text(encoding="utf-8-sig") if ignore_path.exists() else ""
    )
    # On utilise ce texte pour rule ; il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
    rule = "/.env.airflow.local"
    # On vérifie ce cas avant la suite : rule ne figure pas dans ignore_text.splitlines().
    if rule not in ignore_text.splitlines():
        # On ouvre en ajout pour conserver les lignes précédentes du journal ; ce bloc ne remet pas
        # le fichier à zéro.
        with ignore_path.open("a", encoding="utf-8", newline="\n") as handle:
            # Cette branche traite le cas où ignore_text est évalué comme vrai et la condition
            # ignore_text.endswith('\n') n’est pas remplie.
            if ignore_text and not ignore_text.endswith("\n"):
                # On écrit '\n' dans handle ; le mode d’ouverture du flux détermine s’il s’agit d’un
                # ajout ou d’un remplacement.
                handle.write("\n")
            # On écrit "\n# Secrets locaux de l'environnement Airflow\n" + rule + '\n' dans handle ; le
            # mode d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
            handle.write(
                "\n# Secrets locaux de l'environnement Airflow\n" + rule + "\n"
            )
        # On affiche le texte 'Exclusion Git ajoutee pour .env.airflow.local.' dans la sortie du
        # programme.
        print("Exclusion Git ajoutee pour .env.airflow.local.")

    # On construit env_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    env_path = root / ".env.airflow.local"
    # Cette branche traite le cas où env_path existe.
    if env_path.exists():
        # On affiche ce texte explicite dans la sortie du programme.
        print("Fichier Airflow local deja present : conserve sans modification.")
        # On affiche ce texte explicite dans la sortie du programme.
        print("Aucun secret affiche. Aucun acces a la base metier ou au NAS.")
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0

    # On prépare les réglages locaux des services Airflow ; ces paramètres techniques sont distincts
    # des données métier suivies dans PostgreSQL.
    values = {
        # On associe la clé 'PROJECT12_AIRFLOW_DB_PASSWORD' à cette valeur dans cet objet.
        "PROJECT12_AIRFLOW_DB_PASSWORD": secrets.token_hex(24),
        # On associe la clé 'PROJECT12_AIRFLOW_FERNET_KEY' à cette valeur dans cet objet.
        "PROJECT12_AIRFLOW_FERNET_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(
            "ascii"
        ),
        # On associe la clé 'PROJECT12_AIRFLOW_JWT_SECRET' à cette valeur dans cet objet.
        "PROJECT12_AIRFLOW_JWT_SECRET": secrets.token_hex(32),
        # On associe la clé 'PROJECT12_AIRFLOW_UI_PASSWORD' à cette valeur dans cet objet.
        "PROJECT12_AIRFLOW_UI_PASSWORD": secrets.token_hex(16),
    }
    # Mode x : ne jamais écraser des secrets créés entre le contrôle et l'écriture.
    with env_path.open("x", encoding="utf-8", newline="\n") as handle:
        # On écrit '# Secrets Airflow locaux : ne pas versionner ni communiquer.\n' dans handle ; le
        # mode d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        handle.write("# Secrets Airflow locaux : ne pas versionner ni communiquer.\n")
        # On parcourt les couples (key, value) de values : on garde ensemble la clé et sa valeur au
        # lieu des traiter dans deux listes séparées.
        for key, value in values.items():
            # On écrit f'{key}={value}\n' dans handle ; le mode d’ouverture du flux détermine s’il
            # s’agit d’un ajout ou d’un remplacement.
            handle.write(f"{key}={value}\n")
    # On vérifie ce cas avant la suite : os.name diffère du texte 'nt'.
    if os.name != "nt":
        # On appelle env_path.chmod avec 384.
        env_path.chmod(0o600)
    # On affiche ce texte explicite dans la sortie du programme.
    print("Secrets Airflow generes dans .env.airflow.local, sans les afficher.")
    # On affiche ce texte explicite dans la sortie du programme.
    print("Compte interface : projet12. Mot de passe conserve localement.")
    # On affiche le texte "Le fichier .env metier n'a pas ete lu ni modifie." dans la sortie du
    # programme.
    print("Le fichier .env metier n'a pas ete lu ni modifie.")
    # On affiche ce texte explicite dans la sortie du programme.
    print("Aucune connexion PostgreSQL, aucun acces NAS, aucun lancement Docker.")
    # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de retour.
    return 0


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
