# Lecture du fichier — Configuration explicite des racines NAS pour l’extracteur.
# On utilise le mode demandé plutôt qu’un repli silencieux vers les chemins d’un autre environnement.
#

"""Choix explicite des parametres NAS ; aucune lecture a l'import du module."""

# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path

# On fixe MODE_VARIABLE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
MODE_VARIABLE = "PROJECT12_NAS_CONNECTION_MODE"


# On expose les racines explicites selon le mode de connexion demandé.
def configure_nas_environment(project_root, *, local_loader=None):
    # On garde dans mode la valeur de la variable d’environnement demandée, ou son repli si elle est
    # absente.
    mode = os.environ.get(MODE_VARIABLE, "local")
    # On vérifie ce cas avant la suite : mode correspond au texte 'local'.
    if mode == "local":
        # Compatibilite exacte des anciennes commandes manuelles.
        if local_loader is None:
            # On rend disponibles load_dotenv depuis dotenv, pour les appels de ce fichier.
            from dotenv import load_dotenv

            # On garde load_dotenv sous le nom local_loader ; cette affectation ne copie pas à elle
            # seule un objet mutable.
            local_loader = load_dotenv
        # Cette branche traite le cas où la condition callable(local_loader) n’est pas remplie.
        if not callable(local_loader):
            # On interrompt cette branche avec ValueError : 'Chargeur local invalide.'.
            raise ValueError("Chargeur local invalide.")
        # On appelle local_loader avec Path(project_root) / '.env'.
        local_loader(Path(project_root) / ".env")
        # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont pas
        # exécutées.
        return
    # On vérifie ce cas avant la suite : mode diffère du texte 'environment'.
    if mode != "environment":
        # On interrompt cette branche avec ValueError : 'PROJECT12_NAS_CONNECTION_MODE invalide : local
        # ou environment requis.'.
        raise ValueError(
            "PROJECT12_NAS_CONNECTION_MODE invalide : local ou environment requis."
        )
    # Aucun dotenv, aucun repli local, aucun acces au NAS pour ce controle.
    for key in ("NAS_BRUT_ROOT", "NAS_PROCESSING_ROOT"):
        # On garde dans value la valeur de la variable d’environnement demandée, ou son repli si elle
        # est absente.
        value = os.environ.get(key)
        # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition
        # value.strip() n’est pas remplie ou au moins un élément satisfait le test indiqué.
        if (
            not isinstance(value, str)
            # Ce cas est aussi retenu si la condition value.strip() n’est pas remplie.
            or not value.strip()
            # Ce cas est aussi retenu si au moins un élément satisfait le test indiqué.
            or any(c in value for c in ("\x00", "\r", "\n"))
        ):
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                key + " absent ou invalide dans l environnement explicite."
            )
        # Cette branche traite le cas où la condition Path(value).is_absolute() n’est pas remplie.
        if not Path(value).is_absolute():
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                key + " doit etre un chemin absolu adapte au systeme d execution."
            )
