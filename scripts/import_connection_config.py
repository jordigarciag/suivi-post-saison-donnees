# Lecture du fichier — Préparation des paramètres de connexion du compte importeur.
# On exige une identité dédiée plutôt que réutiliser silencieusement un compte d’administration. Les
# valeurs sensibles ne doivent pas être affichées.
#

"""Connexion importeur Windows ou environnement explicite ; aucun repli admin."""

# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re

# On fixe IMPORT_USER à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
IMPORT_USER = "projet12_importer"
# On fixe DATABASE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
DATABASE = "suivi_acquisitions"
# On fixe MODE_VARIABLE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
MODE_VARIABLE = "PROJECT12_IMPORT_CONNECTION_MODE"


# On prépare les paramètres PostgreSQL nécessaires au contrôle défini par ce module.
def database_config(root):
    # On garde dans mode la valeur de la variable d’environnement demandée, ou son repli si elle est
    # absente.
    mode = os.environ.get(MODE_VARIABLE, "local")
    # On vérifie ce cas avant la suite : mode correspond au texte 'local'.
    if mode == "local":
        # On rend disponibles dotenv_values depuis dotenv, pour les appels de ce fichier.
        from dotenv import dotenv_values

        # On garde dans config les réglages lus sans modifier automatiquement l’environnement global.
        config = dotenv_values(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            Path(root) / ".env", encoding="utf-8-sig", interpolate=False
        )
        # En mode local, on vise le port publié sur le poste. Ce n’est pas le nom du service utilisé
        # entre conteneurs Docker.
        host, port = "127.0.0.1", 5433
        # On utilise ce texte pour source ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        source = "du .env"
    # On vérifie ce cas avant la suite : mode correspond au texte 'environment'.
    elif mode == "environment":
        # Dans ce mode, les réglages viennent uniquement de l’environnement fourni au processus ; on
        # ne recharge pas discrètement le .env du poste.
        config = os.environ
        # On garde dans host le champ 'PROJECT12_IMPORT_HOST' de config avec le repli indiqué si la clé
        # est absente.
        host = config.get("PROJECT12_IMPORT_HOST", "")
        # Cette branche traite le cas où la condition re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]*', host)
        # n’est pas remplie.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", host):
            # On interrompt cette branche avec ValueError : 'PROJECT12_IMPORT_HOST absent ou invalide :
            # nom DNS ou IPv4 requis.'.
            raise ValueError(
                "PROJECT12_IMPORT_HOST absent ou invalide : nom DNS ou IPv4 requis."
            )
        # On garde dans raw_port le champ 'PROJECT12_IMPORT_PORT' de config avec le repli indiqué si la
        # clé est absente.
        raw_port = config.get("PROJECT12_IMPORT_PORT", "")
        # Cette branche traite le cas où la condition re.fullmatch('[0-9]{1,5}', raw_port) n’est pas
        # remplie ou la condition 1 <= int(raw_port) <= 65535 n’est pas remplie.
        if not re.fullmatch(r"[0-9]{1,5}", raw_port) or not 1 <= int(raw_port) <= 65535:
            # On interrompt cette branche avec ValueError : 'PROJECT12_IMPORT_PORT absent ou invalide :
            # entier de 1 a 65535 requis.'.
            raise ValueError(
                "PROJECT12_IMPORT_PORT absent ou invalide : entier de 1 a 65535 requis."
            )
        # La plage du port a déjà été vérifiée ; on convertit maintenant le texte en entier pour le
        # pilote PostgreSQL.
        port = int(raw_port)
        # On utilise ce texte pour source ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        source = "de l environnement"
    else:
        # On interrompt cette branche avec ValueError : 'PROJECT12_IMPORT_CONNECTION_MODE invalide :
        # local ou environment requis.'.
        raise ValueError(
            "PROJECT12_IMPORT_CONNECTION_MODE invalide : local ou environment requis."
        )

    # On vérifie ce cas avant la suite : config.get('PROJECT12_IMPORT_USER') diffère de IMPORT_USER.
    if config.get("PROJECT12_IMPORT_USER") != IMPORT_USER:
        # On interrompt cette branche avec ValueError : 'PROJECT12_IMPORT_USER absent ou incorrect :
        # utiliser projet12_importer.'.
        raise ValueError(
            "PROJECT12_IMPORT_USER absent ou incorrect : utiliser projet12_importer."
        )
    # On garde dans password le champ 'PROJECT12_IMPORT_PASSWORD' de config, ou None si la clé est
    # absente.
    password = config.get("PROJECT12_IMPORT_PASSWORD")
    # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition password
    # n’est pas remplie.
    if not isinstance(password, str) or not password:
        # On interrompt cette branche avec ValueError.
        raise ValueError("PROJECT12_IMPORT_PASSWORD absent " + source + ".")
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'host' à cette valeur dans cet objet.
        "host": host,
        # On associe la clé 'port' à cette valeur dans cet objet.
        "port": port,
        # On associe la clé 'dbname' à cette valeur dans cet objet.
        "dbname": DATABASE,
        # On associe la clé 'user' à cette valeur dans cet objet.
        "user": IMPORT_USER,
        # On associe la clé 'password' à cette valeur dans cet objet.
        "password": password,
        # On associe la clé 'connect_timeout' à cette valeur dans cet objet.
        "connect_timeout": 5,
    }


# On vérifie que la connexion utilise bien le compte importeur attendu.
def verify_import_identity(identity):
    # On vérifie ce cas avant la suite : tuple(identity) diffère de (DATABASE, IMPORT_USER,
    # IMPORT_USER).
    if tuple(identity) != (DATABASE, IMPORT_USER, IMPORT_USER):
        # On interrompt cette branche avec ValueError : 'Base, role effectif ou compte de connexion
        # inattendu : chargement refuse.'.
        raise ValueError(
            "Base, role effectif ou compte de connexion inattendu : chargement refuse."
        )
