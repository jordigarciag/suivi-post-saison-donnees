# Lecture du fichier — Observation ciblée des fichiers et associations sur le NAS.
# On recherche des preuves de présence sans confondre dossier accessible, fichier présent et livrable
# exploitable. Une porte fermée ne prouve pas que la pièce est vide : une erreur de lecture reste une
# information distincte.
#

"""
Extraction en lecture seule des preuves techniques présentes sur le NAS actuel.

Le script part du référentiel Excel normalisé et contrôle, pour un vignoble :

1. prise en compte : dossier de l'acquisition présent dans Brut ;
2. sauvegarde native : PNG pleine taille détecté sous LEFT et/ou RIGHT ;
3. mapping parcelle : acquisition présente dans le mapping des parcelles ;
4. traitement d'images : WEBP détecté sous processed_imgs/LEFT et/ou RIGHT ;
5. lien vers un passage : acquisition présente dans le mapping des passages ;
6. passage : dossier du passage présent ;
7. Vitimap : fichier *_rep_map.geojson présent ;
8. fichier stocks : fichier *_stocks.json présent dans le dossier passage ;
9. Vitiparcel créé : stocks.json présent et au moins un champ status non sain.

Le script ne modifie jamais le NAS. Il écrit trois CSV locaux (acquisitions,
associations et passages distincts) dans :

    data/03_normalized/nas_live_evidence/

Les preuves restent factuelles : une absence de preuve ne signifie pas
automatiquement « échec », « test » ou « à retraiter ».
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe time. On mesure des durées ou on gère les attentes prévues par ce fichier.
import time
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles Any depuis typing, pour les appels de ce fichier.
from typing import Any

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd
# On rend disponibles load_dotenv depuis dotenv, pour les appels de ce fichier.
from dotenv import load_dotenv

# Choix explicite local/environnement, sans casser l'execution directe.
if __package__ in {None, ""}:
    # On rend disponibles configure_nas_environment depuis workflow_nas_environment, pour les appels de
    # ce fichier.
    from workflow_nas_environment import configure_nas_environment
else:
    # On rend disponibles configure_nas_environment depuis workflow_nas_environment, pour les appels de
    # ce fichier.
    from .workflow_nas_environment import configure_nas_environment


# On récupère Path(__file__).resolve().parents[3] et on le garde dans PROJECT_ROOT pour la suite.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# On assemble les morceaux du chemin DEFAULT_REFERENCE_PATH avec l’opérateur / de pathlib ; aucun
# fichier n’est créé par cette construction.
DEFAULT_REFERENCE_PATH = (
    PROJECT_ROOT
    / "data"
    / "03_normalized"
    / "suivi_acquisitions_normalises"
    / "toutes_acquisitions_normalisees.csv"
)
# On assemble les morceaux du chemin DEFAULT_OUTPUT_DIR avec l’opérateur / de pathlib ; aucun fichier
# n’est créé par cette construction.
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "03_normalized" / "nas_live_evidence"


def log(message: str = "") -> None:
    """Affiche immédiatement un message dans le terminal."""

    # On affiche message dans la sortie du programme.
    print(message, flush=True)


def parse_arguments() -> argparse.Namespace:
    """Lit les paramètres de ligne de commande."""

    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(
        description=(
            "Contrôle en lecture seule des preuves du pipeline sur le NAS actuel."
        )
    )
    # Option --vineyard : Nom du vignoble tel qu'il apparaît dans le référentiel et le NAS. Sa
    # déclaration ne déclenche pas l’action.
    parser.add_argument(
        "--vineyard",
        required=True,
        help="Nom du vignoble tel qu'il apparaît dans le référentiel et le NAS.",
    )
    # Option --year : Année métier à contrôler (défaut : 2026). Sa déclaration ne déclenche pas
    # l’action.
    parser.add_argument(
        "--year",
        type=int,
        default=2026,
        help="Année métier à contrôler (défaut : 2026).",
    )
    # Option --limit : Limite le nombre d'acquisitions pour un test rapide. Sa déclaration ne
    # déclenche pas l’action.
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limite le nombre d'acquisitions pour un test rapide.",
    )
    # Option --acquisition-id : Contrôle uniquement cet identifiant normalisé. L'option peut être
    # répétée. Sa déclaration ne déclenche pas l’action.
    parser.add_argument(
        "--acquisition-id",
        action="append",
        default=[],
        help=(
            "Contrôle uniquement cet identifiant normalisé. L'option peut être répétée."
        ),
    )
    # Option --verbose : Affiche le détail des preuves pour chaque acquisition. Sa déclaration ne
    # déclenche pas l’action.
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Affiche le détail des preuves pour chaque acquisition.",
    )
    # Option --reference : Chemin du référentiel Excel normalisé. Sa déclaration ne déclenche pas
    # l’action.
    parser.add_argument(
        "--reference",
        type=Path,
        default=DEFAULT_REFERENCE_PATH,
        help="Chemin du référentiel Excel normalisé.",
    )
    # Option --output-dir : Dossier local dans lequel enregistrer le bilan CSV. Sa déclaration ne
    # déclenche pas l’action.
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Dossier local dans lequel enregistrer le bilan CSV.",
    )
    # Option --parcel-mapping : Chemin facultatif du mapping parcelles. Sa déclaration ne déclenche
    # pas l’action.
    parser.add_argument(
        "--parcel-mapping",
        type=Path,
        default=None,
        help="Chemin facultatif du mapping parcelles.",
    )
    # Option --passage-mapping : Chemin facultatif du mapping passages. Sa déclaration ne déclenche
    # pas l’action.
    parser.add_argument(
        "--passage-mapping",
        type=Path,
        default=None,
        help="Chemin facultatif du mapping passages.",
    )
    # On récupère les options de ce lancement dans args ; les vérifications ci-dessous restent
    # nécessaires avant des utiliser.
    return parser.parse_args()


def extract_year_from_acquisition_id(
    acquisition_id: str,
    default_year: int,
) -> int:
    """Extrait l'année de l'identifiant ou retourne l'année demandée."""

    # On garde dans match la première correspondance du motif trouvée dans le texte.
    match = re.search(r"(20\d{2})-\d{2}-\d{2}T", str(acquisition_id))
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return int(match.group(1)) if match else default_year


def load_json_file(path: Path) -> tuple[Any | None, str]:
    """Charge un JSON sans interrompre tout le contrôle en cas d'erreur."""

    # On tente ce bloc et on traite séparément les erreurs prévues : (OSError, json.JSONDecodeError).
    try:
        # Cette branche traite le cas où la condition path.exists() n’est pas remplie.
        if not path.exists():
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return None, "Fichier JSON introuvable."
        # Cette branche traite le cas où la condition path.is_file() n’est pas remplie.
        if not path.is_file():
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return None, "Le chemin JSON n'est pas un fichier."
        # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la sortie,
        # y compris après une erreur.
        with path.open("r", encoding="utf-8") as file:
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return json.load(file), ""
    except (OSError, json.JSONDecodeError) as error:
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return None, str(error)


def first_file_with_suffix(
    directory: Path,
    suffix: str,
) -> tuple[Path | None, str]:
    """
    Recherche uniquement le premier fichier d'une extension dans un dossier.

    os.scandir permet d'arrêter la lecture dès la première preuve, ce qui évite
    de compter ou parcourir inutilement des milliers d'images sur le réseau.
    """

    # On tente ce bloc et on traite séparément les erreurs prévues : OSError.
    try:
        # Cette branche traite le cas où la condition directory.exists() n’est pas remplie ou la
        # condition directory.is_dir() n’est pas remplie.
        if not directory.exists() or not directory.is_dir():
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return None, ""
        # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
        # enregistré dans les données sources.
        expected_suffix = suffix.casefold()
        # On utilise os.scandir(directory) dans son contexte de gestion ; les opérations de sortie sont
        # exécutées en quittant le bloc.
        with os.scandir(directory) as entries:
            # On parcourt entries ; entry désigne l’élément courant à chaque passage dans la boucle.
            for entry in entries:
                # Cette branche traite le cas où entry désigne un fichier et entry.name.casefold() se
                # termine par expected_suffix.
                if entry.is_file(
                    follow_symlinks=False
                # On exige aussi que entry.name.casefold() se termine par expected_suffix.
                ) and entry.name.casefold().endswith(expected_suffix):
                    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il
                    # les décompose.
                    return Path(entry.path), ""
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return None, ""
    except OSError as error:
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return None, str(error)


def find_native_png_for_side(
    side_path: Path,
) -> tuple[Path | None, str]:
    """
    Recherche un PNG pleine taille sous un dossier caméra numérique.

    Structure attendue :
        Acquisition_LEFT/1000000001/*.png
        Acquisition_RIGHT/1000000002/*.png

    Les dossiers _resized, _DEPTH, binaries, img_left, img_right et Mail ne
    répondent pas à cette structure et ne sont donc jamais utilisés comme
    preuve de sauvegarde native.
    """

    # On tente ce bloc et on traite séparément les erreurs prévues : OSError.
    try:
        # Cette branche traite le cas où la condition side_path.exists() n’est pas remplie ou la
        # condition side_path.is_dir() n’est pas remplie.
        if not side_path.exists() or not side_path.is_dir():
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return None, ""
        # On utilise os.scandir(side_path) dans son contexte de gestion ; les opérations de sortie sont
        # exécutées en quittant le bloc.
        with os.scandir(side_path) as entries:
            # On parcourt entries ; entry désigne l’élément courant à chaque passage dans la boucle.
            for entry in entries:
                # Cette branche traite le cas où la condition entry.is_dir(follow_symlinks=False) n’est
                # pas remplie.
                if not entry.is_dir(follow_symlinks=False):
                    # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                    continue
                # Cette branche traite le cas où la condition entry.name.isdigit() n’est pas remplie.
                if not entry.name.isdigit():
                    # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                    continue
                # On répartit les valeurs renvoyées par first_file_with_suffix entre (evidence, error)
                # ; leur ordre doit correspondre à celui prévu par cet appel.
                evidence, error = first_file_with_suffix(Path(entry.path), ".png")
                # Cette branche traite le cas où error est évalué comme vrai.
                if error:
                    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il
                    # les décompose.
                    return None, error
                # On vérifie ce cas avant la suite : evidence est renseigné (différent de None).
                if evidence is not None:
                    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il
                    # les décompose.
                    return evidence, ""
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return None, ""
    except OSError as error:
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return None, str(error)


# On recherche les preuves attendues dans les images brutes du périmètre.
def check_raw_evidence(
    nas_raw_root: Path,
    vineyard: str,
    year: int,
    acquisition_id_base: str,
) -> dict[str, Any]:
    """Contrôle le dossier Brut et les PNG natifs LEFT/RIGHT."""

    # On calcule ce quotient pour construire acquisition_path.
    acquisition_path = nas_raw_root / vineyard / str(year) / acquisition_id_base
    # On regroupe dans result ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    result: dict[str, Any] = {
        # On associe la clé 'raw_path' à cette valeur dans cet objet.
        "raw_path": str(acquisition_path),
        # On renseigne la présence constatée dans les données brutes sous la clé 'found_in_raw_live'.
        "found_in_raw_live": False,
        # On associe la clé 'raw_has_full_size_left' à cette valeur dans cet objet.
        "raw_has_full_size_left": False,
        # On associe la clé 'raw_has_full_size_right' à cette valeur dans cet objet.
        "raw_has_full_size_right": False,
        # On renseigne la présence d’une image pleine taille sous la clé 'raw_has_full_size_image'.
        "raw_has_full_size_image": False,
        # On associe la clé 'raw_has_full_size_both_sides' à cette valeur dans cet objet.
        "raw_has_full_size_both_sides": False,
        # On associe la clé 'raw_full_size_left_evidence_path' à cette valeur dans cet objet.
        "raw_full_size_left_evidence_path": "",
        # On associe la clé 'raw_full_size_right_evidence_path' à cette valeur dans cet objet.
        "raw_full_size_right_evidence_path": "",
        # On renseigne l’erreur de lecture des données brutes sous la clé 'raw_error'.
        "raw_error": "",
    }

    # On tente ce bloc et on traite séparément les erreurs prévues : OSError.
    try:
        # Cette branche traite le cas où la condition acquisition_path.exists() n’est pas remplie.
        if not acquisition_path.exists():
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result
        # Cette branche traite le cas où la condition acquisition_path.is_dir() n’est pas remplie.
        if not acquisition_path.is_dir():
            # On utilise ce texte pour result['raw_error'] ; il ne dépend pas d’une valeur récupérée
            # ailleurs à cet endroit.
            result["raw_error"] = "Le chemin Brut existe mais n'est pas un dossier."
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result
        # On initialise result['found_in_raw_live'] à True ; les branches suivantes pourront modifier
        # cet état.
        result["found_in_raw_live"] = True
    except OSError as error:
        # On garde dans result['raw_error'] la représentation textuelle de error.
        result["raw_error"] = str(error)
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    # On construit left_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    left_path = acquisition_path / f"{acquisition_id_base}_LEFT"
    # On construit right_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    right_path = acquisition_path / f"{acquisition_id_base}_RIGHT"

    # On répartit les valeurs renvoyées par find_native_png_for_side entre (left_evidence, left_error)
    # ; leur ordre doit correspondre à celui prévu par cet appel.
    left_evidence, left_error = find_native_png_for_side(left_path)
    # On répartit les valeurs renvoyées par find_native_png_for_side entre (right_evidence,
    # right_error) ; leur ordre doit correspondre à celui prévu par cet appel.
    right_evidence, right_error = find_native_png_for_side(right_path)

    # On garde dans result['raw_has_full_size_left'] le résultat de cette comparaison : left_evidence
    # est renseigné (différent de None).
    result["raw_has_full_size_left"] = left_evidence is not None
    # On garde dans result['raw_has_full_size_right'] le résultat de cette comparaison : right_evidence
    # est renseigné (différent de None).
    result["raw_has_full_size_right"] = right_evidence is not None
    # On retient pour result['raw_has_full_size_image'] la première valeur évaluée comme vraie dans
    # cette chaîne de replis ; une valeur vide fera donc passer à la suivante.
    result["raw_has_full_size_image"] = (
        result["raw_has_full_size_left"] or result["raw_has_full_size_right"]
    )
    # On calcule result['raw_has_full_size_both_sides'] avec ces conditions liées par and ; Python
    # s’arrête dès qu’une valeur est évaluée comme fausse.
    result["raw_has_full_size_both_sides"] = (
        result["raw_has_full_size_left"] and result["raw_has_full_size_right"]
    )
    # On choisit la valeur de result['raw_full_size_left_evidence_path'] selon ce test : left_evidence
    # est évalué comme vrai. Les deux résultats possibles restent définis explicitement ici.
    result["raw_full_size_left_evidence_path"] = (
        str(left_evidence) if left_evidence else ""
    )
    # On choisit la valeur de result['raw_full_size_right_evidence_path'] selon ce test :
    # right_evidence est évalué comme vrai. Les deux résultats possibles restent définis explicitement
    # ici.
    result["raw_full_size_right_evidence_path"] = (
        str(right_evidence) if right_evidence else ""
    )
    # On garde dans result['raw_error'] le texte formé en réunissant les éléments avec ' | ' comme
    # séparateur.
    result["raw_error"] = " | ".join(
        message for message in [left_error, right_error] if message
    )
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On observe les fichiers attendus du côté des traitements.
def check_processing_evidence(
    nas_processing_root: Path,
    vineyard: str,
    year: int,
    acquisition_id_normalise: str,
) -> dict[str, Any]:
    """Contrôle le dossier Processing et les WEBP LEFT/RIGHT."""

    # On construit acquisition_path en assemblant les morceaux du chemin. L’opérateur / de pathlib
    # ne crée ni dossier ni fichier.
    acquisition_path = (
        nas_processing_root
        / vineyard
        / "acquisitions"
        / str(year)
        / acquisition_id_normalise
    )
    # On construit processed_imgs_path en assemblant les morceaux du chemin. L’opérateur / de
    # pathlib ne crée ni dossier ni fichier.
    processed_imgs_path = acquisition_path / "processed_imgs"
    # On regroupe dans result ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    result: dict[str, Any] = {
        # On associe la clé 'processing_path' à cette valeur dans cet objet.
        "processing_path": str(acquisition_path),
        # On renseigne la présence dans les traitements sous la clé 'found_in_processing_live'.
        "found_in_processing_live": False,
        # On associe la clé 'processing_has_processed_imgs' à cette valeur dans cet objet.
        "processing_has_processed_imgs": False,
        # On associe la clé 'processing_has_webp_left' à cette valeur dans cet objet.
        "processing_has_webp_left": False,
        # On associe la clé 'processing_has_webp_right' à cette valeur dans cet objet.
        "processing_has_webp_right": False,
        # On renseigne la présence d’images WEBP sous la clé 'processing_has_webp_images'.
        "processing_has_webp_images": False,
        # On associe la clé 'processing_has_webp_both_sides' à cette valeur dans cet objet.
        "processing_has_webp_both_sides": False,
        # On associe la clé 'processing_webp_left_evidence_path' à cette valeur dans cet objet.
        "processing_webp_left_evidence_path": "",
        # On associe la clé 'processing_webp_right_evidence_path' à cette valeur dans cet objet.
        "processing_webp_right_evidence_path": "",
        # On renseigne l’erreur de lecture des traitements sous la clé 'processing_error'.
        "processing_error": "",
    }

    # On tente ce bloc et on traite séparément les erreurs prévues : OSError.
    try:
        # Cette branche traite le cas où la condition acquisition_path.exists() n’est pas remplie.
        if not acquisition_path.exists():
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result
        # Cette branche traite le cas où la condition acquisition_path.is_dir() n’est pas remplie.
        if not acquisition_path.is_dir():
            # On utilise ce texte pour result['processing_error'] ; il ne dépend pas d’une valeur
            # récupérée ailleurs à cet endroit.
            result["processing_error"] = (
                "Le chemin Processing existe mais n'est pas un dossier."
            )
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result
        # On initialise result['found_in_processing_live'] à True ; les branches suivantes pourront
        # modifier cet état.
        result["found_in_processing_live"] = True

        # Cette branche traite le cas où la condition processed_imgs_path.exists() n’est pas remplie.
        if not processed_imgs_path.exists():
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result
        # Cette branche traite le cas où la condition processed_imgs_path.is_dir() n’est pas remplie.
        if not processed_imgs_path.is_dir():
            # On utilise ce texte pour result['processing_error'] ; il ne dépend pas d’une valeur
            # récupérée ailleurs à cet endroit.
            result["processing_error"] = (
                "processed_imgs existe mais n'est pas un dossier."
            )
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result
        # On initialise result['processing_has_processed_imgs'] à True ; les branches suivantes
        # pourront modifier cet état.
        result["processing_has_processed_imgs"] = True
    except OSError as error:
        # On garde dans result['processing_error'] la représentation textuelle de error.
        result["processing_error"] = str(error)
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    # On répartit les valeurs renvoyées par first_file_with_suffix entre (left_evidence, left_error) ;
    # leur ordre doit correspondre à celui prévu par cet appel.
    left_evidence, left_error = first_file_with_suffix(
        processed_imgs_path / "LEFT", ".webp"
    )
    # On répartit les valeurs renvoyées par first_file_with_suffix entre (right_evidence, right_error)
    # ; leur ordre doit correspondre à celui prévu par cet appel.
    right_evidence, right_error = first_file_with_suffix(
        processed_imgs_path / "RIGHT", ".webp"
    )

    # On garde dans result['processing_has_webp_left'] le résultat de cette comparaison : left_evidence
    # est renseigné (différent de None).
    result["processing_has_webp_left"] = left_evidence is not None
    # On garde dans result['processing_has_webp_right'] le résultat de cette comparaison :
    # right_evidence est renseigné (différent de None).
    result["processing_has_webp_right"] = right_evidence is not None
    # On retient pour result['processing_has_webp_images'] la première valeur évaluée comme vraie dans
    # cette chaîne de replis ; une valeur vide fera donc passer à la suivante.
    result["processing_has_webp_images"] = (
        result["processing_has_webp_left"] or result["processing_has_webp_right"]
    )
    # On calcule result['processing_has_webp_both_sides'] avec ces conditions liées par and ; Python
    # s’arrête dès qu’une valeur est évaluée comme fausse.
    result["processing_has_webp_both_sides"] = (
        result["processing_has_webp_left"] and result["processing_has_webp_right"]
    )
    # On choisit la valeur de result['processing_webp_left_evidence_path'] selon ce test :
    # left_evidence est évalué comme vrai. Les deux résultats possibles restent définis explicitement
    # ici.
    result["processing_webp_left_evidence_path"] = (
        str(left_evidence) if left_evidence else ""
    )
    # On choisit la valeur de result['processing_webp_right_evidence_path'] selon ce test :
    # right_evidence est évalué comme vrai. Les deux résultats possibles restent définis explicitement
    # ici.
    result["processing_webp_right_evidence_path"] = (
        str(right_evidence) if right_evidence else ""
    )
    # On garde dans result['processing_error'] le texte formé en réunissant les éléments avec ' | '
    # comme séparateur.
    result["processing_error"] = " | ".join(
        message for message in [left_error, right_error] if message
    )
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On prépare un index pour retrouver les associations de parcelles sans relire chaque fois tout le
# document.
def build_parcel_mapping_index(mapping_data: Any) -> tuple[dict[str, list[str]], str]:
    """Conserve toutes les parcelles d'une acquisition, sans écrasement."""
    # Cette branche traite le cas où le type reçu ne correspond pas à dict.
    if not isinstance(mapping_data, dict):
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return {}, "Structure du mapping parcelles inattendue."
    # On crée le dictionnaire vide index pour y ranger ensuite les éléments par clé.
    index: dict[str, list[str]] = {}
    # On prépare errors comme liste vide ; on la remplira au fil des opérations suivantes.
    errors = []
    # On parcourt les couples (parcel, acquisitions) de mapping_data : on garde ensemble la clé et
    # sa valeur au lieu des traiter dans deux listes séparées.
    for parcel, acquisitions in mapping_data.items():
        # Cette branche traite le cas où le type reçu ne correspond pas à list.
        if not isinstance(acquisitions, list):
            # On ajoute f"Liste d'acquisitions invalide pour {parcel}." à la fin de errors ; les
            # éléments précédents restent conservés.
            errors.append(f"Liste d'acquisitions invalide pour {parcel}.")
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On parcourt les acquisitions ; acquisition désigne l’élément courant à chaque passage dans la
        # boucle.
        for acquisition in acquisitions:
            # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition
            # acquisition.strip() n’est pas remplie.
            if not isinstance(acquisition, str) or not acquisition.strip():
                # On ajoute f'Identifiant invalide pour {parcel}.' à la fin de errors ; les éléments
                # précédents restent conservés.
                errors.append(f"Identifiant invalide pour {parcel}.")
                # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                continue
            # On garde dans values la valeur renvoyée par index.setdefault.
            values = index.setdefault(acquisition.strip().casefold(), [])
            # On vérifie ce cas avant la suite : str(parcel) ne figure pas dans les valeurs.
            if str(parcel) not in values:
                # On ajoute str(parcel) à la fin de values ; les éléments précédents restent conservés.
                values.append(str(parcel))
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return index, " | ".join(errors)


# On prépare un index des liens entre passages et acquisitions.
def build_passage_mapping_index(
    mapping_data: Any,
) -> tuple[dict[str, list[dict[str, str]]], str]:
    """Conserve chaque couple parcelle/passage associé à une acquisition."""
    # Cette branche traite le cas où le type reçu ne correspond pas à dict.
    if not isinstance(mapping_data, dict):
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return {}, "Structure du mapping passages inattendue."
    # On crée le dictionnaire vide index pour y ranger ensuite les éléments par clé.
    index: dict[str, list[dict[str, str]]] = {}
    # On prépare errors comme liste vide ; on la remplira au fil des opérations suivantes.
    errors = []
    # On parcourt les couples (parcel, passages) de mapping_data : on garde ensemble la clé et sa
    # valeur au lieu des traiter dans deux listes séparées.
    for parcel, passages in mapping_data.items():
        # Cette branche traite le cas où le type reçu ne correspond pas à dict.
        if not isinstance(passages, dict):
            # On ajoute f'Structure des passages invalide pour {parcel}.' à la fin de errors ; les
            # éléments précédents restent conservés.
            errors.append(f"Structure des passages invalide pour {parcel}.")
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On parcourt les couples (passage, acquisitions) de passages : on garde ensemble la clé et
        # sa valeur au lieu des traiter dans deux listes séparées.
        for passage, acquisitions in passages.items():
            # Cette branche traite le cas où le type reçu ne correspond pas à list.
            if not isinstance(acquisitions, list):
                # On ajoute f"Liste d'acquisitions invalide pour {passage}." à la fin de errors ; les
                # éléments précédents restent conservés.
                errors.append(f"Liste d'acquisitions invalide pour {passage}.")
                # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                continue
            # On parcourt les acquisitions ; acquisition désigne l’élément courant à chaque passage
            # dans la boucle.
            for acquisition in acquisitions:
                # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition
                # acquisition.strip() n’est pas remplie.
                if not isinstance(acquisition, str) or not acquisition.strip():
                    # On ajoute f'Identifiant invalide pour {passage}.' à la fin de errors ; les
                    # éléments précédents restent conservés.
                    errors.append(f"Identifiant invalide pour {passage}.")
                    # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                    continue
                # On regroupe dans value ces champs nommés ; on pourra les retrouver par leur clé
                # plutôt que par leur position.
                value = {"parcel_name": str(parcel), "passage_name": str(passage)}
                # On garde dans values la valeur renvoyée par index.setdefault.
                values = index.setdefault(acquisition.strip().casefold(), [])
                # On vérifie ce cas avant la suite : la valeur reçue ne figure pas dans les valeurs.
                if value not in values:
                    # On ajoute value à la fin de values ; les éléments précédents restent conservés.
                    values.append(value)
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return index, " | ".join(errors)


# On recherche les associations de parcelles dans l’index préparé.
def check_parcel_mapping(
    index: dict[str, list[str]], acquisition_id_normalise: str
) -> dict[str, Any]:
    # On garde dans names une liste matérialisée à partir de
    # index.get(acquisition_id_normalise.strip().casefold(), []).
    names = list(index.get(acquisition_id_normalise.strip().casefold(), []))
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On renseigne la présence dans les correspondances de parcelles sous la clé
        # 'found_in_parcel_mapping'.
        "found_in_parcel_mapping": bool(names),
        # On associe la clé 'parcel_names' à cette valeur dans cet objet.
        "parcel_names": names,
        # On associe la clé 'parcel_name' à cette valeur dans cet objet.
        "parcel_name": " | ".join(names),
        # On associe la clé 'parcel_count' à cette valeur dans cet objet.
        "parcel_count": len(names),
    }


# On recherche les associations de passages dans l’index préparé.
def check_passage_mapping(
    index: dict[str, list[dict[str, str]]], acquisition_id_normalise: str
) -> dict[str, Any]:
    # On construit links comme une liste à partir de dict(value), pour chaque value de
    # index.get(acquisition_id_normalise.strip().casefold(), []).
    links = [
        dict(value)
        for value in index.get(acquisition_id_normalise.strip().casefold(), [])
    ]
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On renseigne la présence dans les correspondances de passages sous la clé
        # 'found_in_passage_mapping'.
        "found_in_passage_mapping": bool(links),
        # On associe la clé 'passage_links' à cette valeur dans cet objet.
        "passage_links": links,
        # On associe la clé 'passage_parcel_name' à cette valeur dans cet objet.
        "passage_parcel_name": " | ".join(
            dict.fromkeys(value["parcel_name"] for value in links)
        ),
        # On associe la clé 'passage_name' à cette valeur dans cet objet.
        "passage_name": " | ".join(
            dict.fromkeys(value["passage_name"] for value in links)
        ),
        # On associe la clé 'passage_link_count' à cette valeur dans cet objet.
        "passage_link_count": len(links),
    }


def analyze_stock_statuses(data: Any) -> dict[str, Any]:
    """
    Analyse les champs ``status`` présents dans stocks.json.

    Critère technique retenu :
        Vitiparcel créé = stocks.json présent
                            + au moins un status non sain.

    Les valeurs HEALTHY et SAIN sont considérées comme saines. Toute autre
    valeur textuelle non vide (par exemple MISSING ou UNHEALTHY) est classée
    comme non saine. Les valeurs originales sont conservées pour la preuve.
    """

    # On prépare status_values comme liste vide ; on la remplira au fil des opérations suivantes.
    status_values: list[str] = []

    def collect(value: Any) -> None:
        # On réserve cette branche à value lorsqu’il est de type dict.
        if isinstance(value, dict):
            # On parcourt les couples (key, child) de value : on garde ensemble la clé et sa valeur
            # au lieu des traiter dans deux listes séparées.
            for key, child in value.items():
                # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici
                # le nom enregistré dans les données sources.
                normalized_key = str(key).strip().casefold()
                # On vérifie ce cas avant la suite : normalized_key appartient à {'status', 'statut'}.
                if normalized_key in {"status", "statut"}:
                    # On réserve cette branche à child lorsqu’il est de type (str, int, float, bool).
                    if isinstance(child, (str, int, float, bool)):
                        # On garde dans text le texte str(child) sans les caractères de bord indiqués,
                        # ou sans les espaces de bord par défaut.
                        text = str(child).strip()
                        # Cette branche traite le cas où le texte de travail est évalué comme vrai.
                        if text:
                            # On ajoute text à la fin de status_values ; les éléments précédents
                            # restent conservés.
                            status_values.append(text)
                    # On réserve cette branche à child lorsqu’il est de type list.
                    elif isinstance(child, list):
                        # On parcourt child ; item désigne l’élément courant à chaque passage dans la
                        # boucle.
                        for item in child:
                            # On réserve cette branche à item lorsqu’il est de type (str, int, float,
                            # bool).
                            if isinstance(item, (str, int, float, bool)):
                                # On garde dans text le texte str(item) sans les caractères de bord
                                # indiqués, ou sans les espaces de bord par défaut.
                                text = str(item).strip()
                                # Cette branche traite le cas où le texte de travail est évalué comme
                                # vrai.
                                if text:
                                    # On ajoute text à la fin de status_values ; les éléments précédents
                                    # restent conservés.
                                    status_values.append(text)
                # On appelle collect avec child.
                collect(child)
        # On réserve cette branche à value lorsqu’il est de type list.
        elif isinstance(value, list):
            # On parcourt la valeur reçue ; item désigne l’élément courant à chaque passage dans la
            # boucle.
            for item in value:
                # On appelle collect avec item.
                collect(item)

    # On appelle collect avec data.
    collect(data)

    # On rassemble dans healthy_values les 2 éléments explicitement indiqués, en conservant leur
    # structure.
    healthy_values = {"healthy", "sain"}
    # On construit non_healthy_values comme une liste à partir de value, pour chaque value de
    # status_values en ne gardant que les éléments qui passent le filtre.
    non_healthy_values = [
        value
        for value in status_values
        if value.strip().casefold().replace("-", "_") not in healthy_values
    ]
    # On garde dans unique_values les éléments triés de set(status_values) dans une nouvelle liste.
    unique_values = sorted(set(status_values), key=str.casefold)
    # On garde dans unique_non_healthy_values les éléments triés de set(non_healthy_values) dans une
    # nouvelle liste.
    unique_non_healthy_values = sorted(set(non_healthy_values), key=str.casefold)

    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'stock_status_count' à cette valeur dans cet objet.
        "stock_status_count": len(status_values),
        # On associe la clé 'stock_status_values' à cette valeur dans cet objet.
        "stock_status_values": " | ".join(unique_values),
        # On associe la clé 'non_healthy_status_count' à cette valeur dans cet objet.
        "non_healthy_status_count": len(non_healthy_values),
        # On associe la clé 'non_healthy_status_values' à cette valeur dans cet objet.
        "non_healthy_status_values": " | ".join(unique_non_healthy_values),
        # On associe la clé 'has_non_healthy_status' à cette valeur dans cet objet.
        "has_non_healthy_status": bool(non_healthy_values),
    }


def contains_non_healthy_status(data: Any) -> bool:
    """Compatibilité : retourne uniquement la présence d'un status non sain."""

    # On fournit à l’appelant la valeur de vérité Python de
    # analyze_stock_statuses(data)['has_non_healthy_status'] ; ce test ne distingue pas à lui seul tous
    # les états métier.
    return bool(analyze_stock_statuses(data)["has_non_healthy_status"])


def empty_passage_outputs() -> dict[str, Any]:
    """Valeurs non vérifiables sans lecture du NAS."""
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'passage_path' à cette valeur dans cet objet.
        "passage_path": "",
        # On associe la clé 'passage_outputs_verifiable' à cette valeur dans cet objet.
        "passage_outputs_verifiable": False,
        # On associe la clé 'passage_verification_note' à cette valeur dans cet objet.
        "passage_verification_note": ("Non vérifiable : passage non identifié."),
        # On associe la clé 'passage_created' à cette valeur dans cet objet.
        "passage_created": False,
        # On associe la clé 'vitimap_geojson_path' à cette valeur dans cet objet.
        "vitimap_geojson_path": "",
        # On associe la clé 'vitimap_created' à cette valeur dans cet objet.
        "vitimap_created": False,
        # On associe la clé 'stocks_json_path' à cette valeur dans cet objet.
        "stocks_json_path": "",
        # On associe la clé 'stocks_json_exists' à cette valeur dans cet objet.
        "stocks_json_exists": False,
        # On associe la clé 'stock_status_count' à cette valeur dans cet objet.
        "stock_status_count": 0,
        # On associe la clé 'stock_status_values' à cette valeur dans cet objet.
        "stock_status_values": "",
        # On associe la clé 'non_healthy_status_count' à cette valeur dans cet objet.
        "non_healthy_status_count": 0,
        # On associe la clé 'non_healthy_status_values' à cette valeur dans cet objet.
        "non_healthy_status_values": "",
        # On associe la clé 'has_non_healthy_status' à cette valeur dans cet objet.
        "has_non_healthy_status": False,
        # On associe la clé 'vitiparcel_output_present' à cette valeur dans cet objet.
        "vitiparcel_output_present": False,
        # On associe la clé 'vitiparcel_created' à cette valeur dans cet objet.
        "vitiparcel_created": False,
        # On associe la clé 'passage_error' à cette valeur dans cet objet.
        "passage_error": "",
        # On associe la clé 'vitimap_error' à cette valeur dans cet objet.
        "vitimap_error": "",
        # On associe la clé 'vitiparcel_error' à cette valeur dans cet objet.
        "vitiparcel_error": "",
    }


# On recherche les sorties liées à un passage et on conserve les erreurs rencontrées.
def check_passage_outputs(
    nas_processing_root: Path,
    vineyard: str,
    year: int,
    passage_name: str,
) -> dict[str, Any]:
    """Contrôle le dossier passage, Vitimap et la sortie Vitiparcel."""

    # On construit passage_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
    # crée ni dossier ni fichier.
    passage_path = (
        nas_processing_root / vineyard / "passages" / str(year) / passage_name
    )
    # On regroupe dans result ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    result: dict[str, Any] = {
        # On associe la clé 'passage_path' à cette valeur dans cet objet.
        "passage_path": str(passage_path) if passage_name else "",
        # On associe la clé 'passage_outputs_verifiable' à cette valeur dans cet objet.
        "passage_outputs_verifiable": bool(passage_name),
        # On associe la clé 'passage_verification_note' à cette valeur dans cet objet.
        "passage_verification_note": (
            "" if passage_name else "Non vérifiable : passage non identifié."
        ),
        # On associe la clé 'passage_created' à cette valeur dans cet objet.
        "passage_created": False,
        # On associe la clé 'vitimap_geojson_path' à cette valeur dans cet objet.
        "vitimap_geojson_path": "",
        # On associe la clé 'vitimap_created' à cette valeur dans cet objet.
        "vitimap_created": False,
        # On associe la clé 'stocks_json_path' à cette valeur dans cet objet.
        "stocks_json_path": "",
        # On associe la clé 'stocks_json_exists' à cette valeur dans cet objet.
        "stocks_json_exists": False,
        # On associe la clé 'stock_status_count' à cette valeur dans cet objet.
        "stock_status_count": 0,
        # On associe la clé 'stock_status_values' à cette valeur dans cet objet.
        "stock_status_values": "",
        # On associe la clé 'non_healthy_status_count' à cette valeur dans cet objet.
        "non_healthy_status_count": 0,
        # On associe la clé 'non_healthy_status_values' à cette valeur dans cet objet.
        "non_healthy_status_values": "",
        # On associe la clé 'has_non_healthy_status' à cette valeur dans cet objet.
        "has_non_healthy_status": False,
        # On associe la clé 'vitiparcel_output_present' à cette valeur dans cet objet.
        "vitiparcel_output_present": False,
        # On associe la clé 'vitiparcel_created' à cette valeur dans cet objet.
        "vitiparcel_created": False,
        # On associe la clé 'passage_error' à cette valeur dans cet objet.
        "passage_error": "",
        # On associe la clé 'vitimap_error' à cette valeur dans cet objet.
        "vitimap_error": "",
        # On associe la clé 'vitiparcel_error' à cette valeur dans cet objet.
        "vitiparcel_error": "",
    }

    # On prévoit le cas où passage_name est évalué comme faux, par exemple une valeur vide selon son
    # type.
    if not passage_name:
        # Absence de rattachement, pas erreur technique de lecture.
        # Les booléens restent False ; le drapeau de vérifiabilité doit être
        # consulté avant des interpréter comme des preuves absentes.
        return result

    # On tente ce bloc et on traite séparément les erreurs prévues : OSError.
    try:
        # Cette branche traite le cas où la condition passage_path.exists() n’est pas remplie.
        if not passage_path.exists():
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result
        # Cette branche traite le cas où la condition passage_path.is_dir() n’est pas remplie.
        if not passage_path.is_dir():
            # On utilise ce texte pour result['passage_error'] ; il ne dépend pas d’une valeur
            # récupérée ailleurs à cet endroit.
            result["passage_error"] = (
                "Le chemin du passage existe mais n'est pas un dossier."
            )
            # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return result
        # On initialise result['passage_created'] à True ; les branches suivantes pourront modifier cet
        # état.
        result["passage_created"] = True
    except OSError as error:
        # On garde dans result['passage_error'] la représentation textuelle de error.
        result["passage_error"] = str(error)
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    # On construit expected_geojson en assemblant les morceaux du chemin. L’opérateur / de pathlib
    # ne crée ni dossier ni fichier.
    expected_geojson = passage_path / f"{passage_name}_rep_map.geojson"
    # On tente ce bloc et on traite séparément les erreurs prévues : OSError.
    try:
        # On choisit la valeur de geojson_path selon ce test : expected_geojson désigne un fichier. Les
        # deux résultats possibles restent définis explicitement ici.
        geojson_path = (
            expected_geojson
            if expected_geojson.is_file()
            else next(
                (
                    path
                    for path in passage_path.glob("*_rep_map.geojson")
                    if path.is_file()
                ),
                None,
            )
        )
        # Cette branche traite le cas où geojson_path est évalué comme vrai.
        if geojson_path:
            # On garde dans result['vitimap_geojson_path'] la représentation textuelle de geojson_path.
            result["vitimap_geojson_path"] = str(geojson_path)
            # On initialise result['vitimap_created'] à True ; les branches suivantes pourront modifier
            # cet état.
            result["vitimap_created"] = True
    except OSError as error:
        # On garde dans result['vitimap_error'] la représentation textuelle de error.
        result["vitimap_error"] = str(error)

    # On construit expected_stocks en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
    # crée ni dossier ni fichier.
    expected_stocks = passage_path / f"{passage_name}_stocks.json"
    # On tente ce bloc et on traite séparément les erreurs prévues : OSError.
    try:
        # On choisit la valeur de stocks_path selon ce test : expected_stocks désigne un fichier. Les
        # deux résultats possibles restent définis explicitement ici.
        stocks_path = (
            expected_stocks
            if expected_stocks.is_file()
            else next(
                (path for path in passage_path.glob("*_stocks.json") if path.is_file()),
                None,
            )
        )
    except OSError as error:
        # On garde dans result['vitiparcel_error'] la représentation textuelle de error.
        result["vitiparcel_error"] = str(error)
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    # On vérifie ce cas avant la suite : stocks_path vaut None.
    if stocks_path is None:
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    # On garde dans result['stocks_json_path'] la représentation textuelle de stocks_path.
    result["stocks_json_path"] = str(stocks_path)
    # On initialise result['stocks_json_exists'] à True ; les branches suivantes pourront modifier cet
    # état.
    result["stocks_json_exists"] = True
    # On initialise result['vitiparcel_output_present'] à True ; les branches suivantes pourront
    # modifier cet état.
    result["vitiparcel_output_present"] = True

    # On répartit les valeurs renvoyées par load_json_file entre (stocks_data, error) ; leur ordre doit
    # correspondre à celui prévu par cet appel.
    stocks_data, error = load_json_file(stocks_path)
    # Cette branche traite le cas où error est évalué comme vrai.
    if error:
        # On garde error sous le nom result['vitiparcel_error'] ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        result["vitiparcel_error"] = error
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    # On garde dans status_analysis la valeur renvoyée par analyze_stock_statuses.
    status_analysis = analyze_stock_statuses(stocks_data)
    # On complète result avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle valeur
    # fournie.
    result.update(status_analysis)

    # Critère technique retenu : le fichier stocks doit exister
    # et contenir au moins un status non sain.
    result["vitiparcel_created"] = (
        result["stocks_json_exists"] and result["has_non_healthy_status"]
    )
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


def side_evidence_label(left: bool, right: bool, evidence_name: str) -> str:
    """Formate une preuve LEFT/RIGHT pour le terminal."""

    # Cette branche traite le cas où left est évalué comme vrai et right est évalué comme vrai.
    if left and right:
        # On remet f'{evidence_name} LEFT et RIGHT' à l’appelant ; les étapes suivantes de cette
        # fonction ne sont plus parcourues.
        return f"{evidence_name} LEFT et RIGHT"
    # Cette branche traite le cas où left est évalué comme vrai.
    if left:
        # On remet f'{evidence_name} LEFT uniquement' à l’appelant ; les étapes suivantes de cette
        # fonction ne sont plus parcourues.
        return f"{evidence_name} LEFT uniquement"
    # Cette branche traite le cas où right est évalué comme vrai.
    if right:
        # On remet f'{evidence_name} RIGHT uniquement' à l’appelant ; les étapes suivantes de cette
        # fonction ne sont plus parcourues.
        return f"{evidence_name} RIGHT uniquement"
    # On remet f'aucun {evidence_name}' à l’appelant ; les étapes suivantes de cette fonction ne sont
    # plus parcourues.
    return f"aucun {evidence_name}"


def determine_maximum_stage(result: dict[str, Any]) -> str:
    """Détermine la preuve la plus avancée, sans conclure à un succès métier."""

    # Cette branche traite le cas où le test result['vitiparcel_created'] est satisfait.
    if result["vitiparcel_created"]:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Vitiparcel créé"
    # Cette branche traite le cas où le test result['vitimap_created'] est satisfait.
    if result["vitimap_created"]:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Vitimap présent"
    # Cette branche traite le cas où le test result['passage_created'] est satisfait.
    if result["passage_created"]:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Passage présent"
    # Cette branche traite le cas où le test result['processing_has_webp_images'] est satisfait.
    if result["processing_has_webp_images"]:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Traitement d'images démontré"
    # Cette branche traite le cas où le test result['found_in_parcel_mapping'] est satisfait.
    if result["found_in_parcel_mapping"]:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Mapping parcelle présent"
    # Cette branche traite le cas où le test result['raw_has_full_size_image'] est satisfait.
    if result["raw_has_full_size_image"]:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Sauvegarde native démontrée"
    # Cette branche traite le cas où le test result['found_in_raw_live'] est satisfait.
    if result["found_in_raw_live"]:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Dossier Brut présent"
    # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
    return "Aucune preuve dans Brut"


def load_reference(
    path: Path,
    vineyard: str,
    year: int,
    acquisition_ids: list[str],
    limit: int | None,
) -> pd.DataFrame:
    """Charge et filtre le référentiel métier."""

    # Cette branche traite le cas où la condition path.exists() n’est pas remplie.
    if not path.exists():
        # On interrompt cette branche avec FileNotFoundError.
        raise FileNotFoundError(f"Référentiel introuvable : {path}")

    # On garde dans df la valeur renvoyée par pd.read_csv.
    df = pd.read_csv(path, dtype="string", low_memory=False)
    # On rassemble dans required les 3 éléments explicitement indiqués, en conservant leur structure.
    required = {
        "Vineyard",
        "Acquisition_ID_base",
        "Acquisition_ID_normalise",
    }
    # On calcule la différence entre ces deux valeurs pour construire missing.
    missing = required - set(df.columns)
    # Cette branche traite le cas où missing est évalué comme vrai.
    if missing:
        # On interrompt cette branche avec ValueError.
        raise ValueError(f"Colonnes absentes du référentiel : {sorted(missing)}")

    # On garde dans filtered une copie de
    # df.loc[df['Vineyard'].fillna('').str.casefold().eq(vineyard.case… pour travailler sur cet objet
    # séparément.
    filtered = df.loc[
        df["Vineyard"].fillna("").str.casefold().eq(vineyard.casefold())
    ].copy()
    # On retire les répétitions selon les colonnes choisies, pas selon une ressemblance visuelle.
    filtered = filtered.drop_duplicates(subset=["Acquisition_ID_normalise"])

    # On garde dans filtered['_year'] le résultat de la fonction appliquée aux éléments ou à l’axe
    # indiqué de filtered['Acquisition_ID_normalise'].
    filtered["_year"] = filtered["Acquisition_ID_normalise"].apply(
        lambda value: extract_year_from_acquisition_id(str(value), year)
    )
    # On garde dans filtered une copie de filtered.loc[filtered['_year'].eq(year)] pour travailler sur
    # cet objet séparément.
    filtered = filtered.loc[filtered["_year"].eq(year)].copy()

    # Cette branche traite le cas où acquisition_ids est évalué comme vrai.
    if acquisition_ids:
        # On construit requested comme un ensemble sans doublons à partir de value.strip().casefold(),
        # pour chaque value de acquisition_ids.
        requested = {value.strip().casefold() for value in acquisition_ids}
        # On garde dans filtered une copie de
        # filtered.loc[filtered['Acquisition_ID_normalise'].fillna('').str… pour travailler sur cet
        # objet séparément.
        filtered = filtered.loc[
            filtered["Acquisition_ID_normalise"]
            .fillna("")
            .str.strip()
            .str.casefold()
            .isin(requested)
        ].copy()

    # On garde dans filtered les lignes de filtered triées selon les colonnes indiquées.
    filtered = filtered.sort_values(
        "Acquisition_ID_normalise",
        # On fournit la clé de l’élément via le paramètre key de cet appel.
        key=lambda series: series.str.casefold(),
    )
    # On vérifie ce cas avant la suite : limit est renseigné (différent de None).
    if limit is not None:
        # On vérifie ce cas avant la suite : limit ne dépasse pas 0.
        if limit <= 0:
            # On interrompt cette branche avec ValueError : '--limit doit être strictement positif.'.
            raise ValueError("--limit doit être strictement positif.")
        # On garde dans filtered la valeur renvoyée par filtered.head.
        filtered = filtered.head(limit)

    # On fournit à l’appelant le tableau filtered avec un index reconstruit selon les options.
    return filtered.reset_index(drop=True)


def format_duration(seconds: float) -> str:
    """Affiche systématiquement une durée en secondes et en minutes."""

    # On remet f'{seconds:.2f} s ({seconds / 60:.2f} min)' à l’appelant ; les étapes suivantes de cette
    # fonction ne sont plus parcourues.
    return f"{seconds:.2f} s ({seconds / 60:.2f} min)"


def format_ratio(count: int, total: int) -> str:
    """Présente un compteur, son total et son pourcentage."""

    # On choisit la valeur de percentage selon ce test : total est évalué comme vrai. Les deux
    # résultats possibles restent définis explicitement ici.
    percentage = (count / total * 100) if total else 0.0
    # On remet f'{count}/{total} ({percentage:.1f} %)' à l’appelant ; les étapes suivantes de cette
    # fonction ne sont plus parcourues.
    return f"{count}/{total} ({percentage:.1f} %)"


def print_header(
    vineyard: str,
    year: int,
    total: int,
    nas_raw_root: Path,
    nas_processing_root: Path,
    verbose: bool,
) -> None:
    """Présente l'objectif, les preuves recherchées et leur interprétation."""

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("=" * 88)
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("🔎 CONTRÔLE EN LECTURE SEULE DU PIPELINE SUR LE NAS ACTUEL")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("=" * 88)
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Vignoble                    : {vineyard}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Année métier                : {year}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Acquisitions à contrôler    : {total}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Racine Brut                 : {nas_raw_root}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Racine Processing           : {nas_processing_root}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Affichage                    : {'détaillé' if verbose else 'compact'}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("OBJECTIF")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Vérifier, acquisition par acquisition, jusqu'où les preuves techniques")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  permettent de suivre la progression du pipeline actuel.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("PREUVES RECHERCHÉES")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  1. Dossier Brut       -> acquisition prise en compte sur le NAS.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  2. PNG LEFT/RIGHT     -> sauvegarde des images natives démontrée.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  3. Mapping parcelle   -> acquisition rattachée à une parcelle.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  4. WEBP LEFT/RIGHT    -> traitement d'images démontré.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  5. Mapping passage    -> acquisition rattachée à un passage.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  6. Dossier passage    -> passage matérialisé sur le NAS.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  7. *_rep_map.geojson  -> sortie Vitimap présente.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  8. *_stocks.json      -> fichier de stocks présent dans le dossier passage.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  9. status non sain    -> avec stocks.json, preuve que Vitiparcel est créé.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("LÉGENDE")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  🟢 preuve démontrée   🟠 preuve absente ou partielle")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  ⚪ information neutre 🔴 erreur technique de lecture")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("IMPORTANT")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Une preuve absente n'est pas automatiquement un échec ou un élément")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  à retraiter. Le NAS est lu sans création, modification ni suppression.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("=" * 88)


def print_acquisition_result(
    index: int,
    total: int,
    result: dict[str, Any],
    verbose: bool,
) -> None:
    """Affiche les preuves avec une interprétation courte et pédagogique."""

    # On garde dans png_label le libellé des constats disponibles pour ce côté.
    png_label = side_evidence_label(
        result["raw_has_full_size_left"],
        result["raw_has_full_size_right"],
        "PNG",
    )
    # On garde dans webp_label le libellé des constats disponibles pour ce côté.
    webp_label = side_evidence_label(
        result["processing_has_webp_left"],
        result["processing_has_webp_right"],
        "WEBP",
    )
    # On garde dans duration_label la valeur renvoyée par format_duration.
    duration_label = format_duration(result["check_duration_seconds"])

    # On prévoit le cas où verbose est évalué comme faux, par exemple une valeur vide selon son type.
    if not verbose:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(
            f"[{index:>3}/{total}] {result['acquisition_id_normalise']} | "
            f"Brut={'oui' if result['found_in_raw_live'] else 'non'} | "
            f"{png_label} | "
            f"Mapping={'oui' if result['found_in_parcel_mapping'] else 'non'} | "
            f"{webp_label} | "
            f"Passage={'non vérifiable' if not result['passage_outputs_verifiable'] else ('oui' if result['passage_created'] else 'non')} | "
            f"Vitimap={'non vérifiable' if not result['passage_outputs_verifiable'] else ('oui' if result['vitimap_created'] else 'non')} | "
            f"Vitiparcel={'non vérifiable' if not result['passage_outputs_verifiable'] else ('oui' if result['vitiparcel_created'] else 'non')} | "
            f"{duration_label}"
        )
        # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont pas
        # exécutées.
        return

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("-")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"ACQUISITION {index}/{total}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Identifiant : {result['acquisition_id_normalise']}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")

    # On choisit la valeur de raw_symbol selon ce test : le test result['found_in_raw_live'] est
    # satisfait. Les deux résultats possibles restent définis explicitement ici.
    raw_symbol = "🟢" if result["found_in_raw_live"] else "🟠"
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {raw_symbol} Prise en compte"
        f"       : {'démontrée — dossier Brut présent' if result['found_in_raw_live'] else 'non démontrée — dossier Brut absent'}"
    )

    # On choisit la valeur de png_symbol selon ce test : le test result['raw_has_full_size_both_sides']
    # est satisfait. Les deux résultats possibles restent définis explicitement ici.
    png_symbol = "🟢" if result["raw_has_full_size_both_sides"] else "🟠"
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  {png_symbol} Sauvegarde native    : {png_label}")

    # On choisit la valeur de mapping_symbol selon ce test : le test result['found_in_parcel_mapping']
    # est satisfait. Les deux résultats possibles restent définis explicitement ici.
    mapping_symbol = "🟢" if result["found_in_parcel_mapping"] else "🟠"
    # On choisit la valeur de mapping_text selon ce test : le test result['found_in_parcel_mapping']
    # est satisfait. Les deux résultats possibles restent définis explicitement ici.
    mapping_text = (
        f"démontrée — parcelle {result['parcel_name']}"
        if result["found_in_parcel_mapping"]
        else "non démontrée — acquisition absente du mapping parcelles"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  {mapping_symbol} Mapping parcelle     : {mapping_text}")

    # On choisit la valeur de webp_symbol selon ce test : le test
    # result['processing_has_webp_both_sides'] est satisfait. Les deux résultats possibles restent
    # définis explicitement ici.
    webp_symbol = "🟢" if result["processing_has_webp_both_sides"] else "🟠"
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  {webp_symbol} Traitement d'images  : {webp_label}")

    # On vérifie ce cas avant la suite : result['passage_link_count'] est supérieur à 1.
    if result["passage_link_count"] > 1:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(f"  Associations : {result['passage_link_count']} couples parcelle/passage")
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(
            "  Les preuves de passage ci-dessous sont une synthèse : tous doivent satisfaire le critère."
        )
        # On parcourt result['_association_results'] ; item désigne l’élément courant à chaque passage
        # dans la boucle.
        for item in result["_association_results"]:
            # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
            # associées.
            log(
                f"    {item['parcel_name']} / {item['passage_name']} : "
                f"dossier={item['passage_created']}, Vitimap={item['vitimap_created']}, "
                f"stocks={item['stocks_json_exists']}, critère Vitiparcel={item['vitiparcel_created']}"
            )
    # On choisit la valeur de passage_mapping_symbol selon ce test : le test
    # result['found_in_passage_mapping'] est satisfait. Les deux résultats possibles restent définis
    # explicitement ici.
    passage_mapping_symbol = "🟢" if result["found_in_passage_mapping"] else "🟠"
    # On choisit la valeur de passage_mapping_text selon ce test : le test
    # result['found_in_passage_mapping'] est satisfait. Les deux résultats possibles restent définis
    # explicitement ici.
    passage_mapping_text = (
        f"démontré — {result['passage_name']}"
        if result["found_in_passage_mapping"]
        else "non démontré — acquisition absente du mapping passages"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  {passage_mapping_symbol} Lien vers un passage : {passage_mapping_text}")

    # Cette branche traite le cas où la condition result['passage_outputs_verifiable'] n’est pas
    # remplie.
    if not result["passage_outputs_verifiable"]:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("  ⚪ Dossier passage      : non vérifiable — passage non identifié")
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("  ⚪ Sortie Vitimap       : non vérifiable — passage non identifié")
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("  ⚪ Fichier stocks       : non vérifiable — passage non identifié")
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("  ⚪ Status dans stocks   : non analysés — passage non identifié")
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("  ⚪ Critère Vitiparcel   : non vérifiable — passage non identifié")
    else:
        # On choisit la valeur de passage_symbol selon ce test : le test result['passage_created'] est
        # satisfait. Les deux résultats possibles restent définis explicitement ici.
        passage_symbol = "🟢" if result["passage_created"] else "🟠"
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(
            f"  {passage_symbol} Dossier passage      : "
            f"{'présent' if result['passage_created'] else 'non démontré pour tous les passages associés'}"
        )

        # On choisit la valeur de vitimap_symbol selon ce test : le test result['vitimap_created'] est
        # satisfait. Les deux résultats possibles restent définis explicitement ici.
        vitimap_symbol = "🟢" if result["vitimap_created"] else "🟠"
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(
            f"  {vitimap_symbol} Sortie Vitimap       : "
            f"{'présente — GeoJSON trouvé' if result['vitimap_created'] else 'non démontrée pour tous les passages associés'}"
        )

        # On choisit la valeur de stocks_symbol selon ce test : le test result['stocks_json_exists']
        # est satisfait. Les deux résultats possibles restent définis explicitement ici.
        stocks_symbol = "🟢" if result["stocks_json_exists"] else "🟠"
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(
            f"  {stocks_symbol} Fichier stocks.json   : "
            f"{'présent dans le dossier passage' if result['stocks_json_exists'] else 'non démontré pour tous les passages associés'}"
        )

        # On choisit la valeur de status_symbol selon ce test : le test
        # result['has_non_healthy_status'] est satisfait. Les deux résultats possibles restent définis
        # explicitement ici.
        status_symbol = "🟢" if result["has_non_healthy_status"] else "🟠"
        # On vérifie ce cas avant la suite : result['passage_link_count'] est supérieur à 1.
        if result["passage_link_count"] > 1:
            # On prépare status_text avec cette expression pour l’utiliser dans la suite du traitement.
            status_text = (
                f"{result['stock_status_count']} status analysé(s), "
                f"{result['non_healthy_status_count']} non sain(s) au total ; "
                "consulter le CSV associations pour le détail par passage"
            )
        # On vérifie ce cas avant la suite : result['stock_status_count'] correspond à 0.
        elif result["stock_status_count"] == 0:
            # On utilise ce texte pour status_text ; il ne dépend pas d’une valeur récupérée ailleurs à
            # cet endroit.
            status_text = "aucun champ status trouvé dans stocks.json"
        # Cette branche traite le cas où le test result['has_non_healthy_status'] est satisfait.
        elif result["has_non_healthy_status"]:
            # On prépare status_text avec cette expression pour l’utiliser dans la suite du traitement.
            status_text = (
                f"{result['non_healthy_status_count']} status non sain(s) — "
                f"valeur(s) : {result['non_healthy_status_values']}"
            )
        else:
            # On prépare status_text avec cette expression pour l’utiliser dans la suite du traitement.
            status_text = (
                f"{result['stock_status_count']} status analysé(s), tous sains — "
                f"valeur(s) : {result['stock_status_values']}"
            )
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(f"  {status_symbol} Status dans stocks    : {status_text}")

        # On choisit la valeur de vitiparcel_symbol selon ce test : le test
        # result['vitiparcel_created'] est satisfait. Les deux résultats possibles restent définis
        # explicitement ici.
        vitiparcel_symbol = "🟢" if result["vitiparcel_created"] else "🟠"
        # On choisit la valeur de vitiparcel_text selon ce test : le test result['vitiparcel_created']
        # est satisfait. Les deux résultats possibles restent définis explicitement ici.
        vitiparcel_text = (
            "oui — stocks.json présent et au moins un status non sain"
            if result["vitiparcel_created"]
            else "non démontré pour tous les passages associés"
        )
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(f"  {vitiparcel_symbol} Vitiparcel créé     : {vitiparcel_text}")

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  Preuve la plus avancée : {result['maximum_evidence_stage']}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Cette indication décrit la preuve la plus avancée observée ; elle ne")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  constitue pas à elle seule une validation métier de toute la chaîne.")

    # On rassemble dans errors les 5 éléments explicitement indiqués, en conservant leur structure.
    errors = [
        result.get("raw_error", ""),
        result.get("processing_error", ""),
        result.get("passage_error", ""),
        result.get("vitimap_error", ""),
        result.get("vitiparcel_error", ""),
    ]
    # On construit errors comme une liste à partir de error, pour chaque error de errors en ne gardant
    # que les éléments qui passent le filtre.
    errors = [error for error in errors if error]
    # Cette branche traite le cas où les erreurs relevées est évalué comme vrai.
    if errors:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("  🔴 Erreurs techniques : " + " | ".join(errors))

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  Durée du contrôle : {duration_label}")


def build_result(
    row: pd.Series,
    nas_raw_root: Path,
    nas_processing_root: Path,
    vineyard: str,
    default_year: int,
    parcel_mapping_index: dict[str, list[str]],
    passage_mapping_index: dict[str, list[dict[str, str]]],
    passage_cache: dict[tuple[str, int, str, str], dict[str, Any]],
    run_checked_at: str,
) -> dict[str, Any]:
    """Contrôle une acquisition et réunit toutes les preuves factuelles."""

    # On garde dans started_at la valeur renvoyée par time.perf_counter.
    started_at = time.perf_counter()
    # On garde dans acquisition_id_base la représentation textuelle de row['Acquisition_ID_base'].
    acquisition_id_base = str(row["Acquisition_ID_base"])
    # On garde dans acquisition_id_normalise la représentation textuelle de l’identifiant normalisé de
    # l’acquisition dans row.
    acquisition_id_normalise = str(row["Acquisition_ID_normalise"])
    # On garde dans year la valeur renvoyée par extract_year_from_acquisition_id.
    year = extract_year_from_acquisition_id(acquisition_id_normalise, default_year)

    # On garde dans raw la valeur renvoyée par check_raw_evidence.
    raw = check_raw_evidence(
        nas_raw_root,
        vineyard,
        year,
        acquisition_id_base,
    )
    # On garde dans processing la valeur renvoyée par check_processing_evidence.
    processing = check_processing_evidence(
        nas_processing_root,
        vineyard,
        year,
        acquisition_id_normalise,
    )
    # On garde dans parcel la valeur renvoyée par check_parcel_mapping.
    parcel = check_parcel_mapping(parcel_mapping_index, acquisition_id_normalise)
    # On garde dans passage_mapping la valeur renvoyée par check_passage_mapping.
    passage_mapping = check_passage_mapping(
        passage_mapping_index, acquisition_id_normalise
    )

    # On prépare associations comme liste vide ; on la remplira au fil des opérations suivantes.
    associations = []
    # On parcourt passage_mapping['passage_links'] ; link désigne l’élément courant à chaque passage
    # dans la boucle.
    for link in passage_mapping["passage_links"]:
        # On récupère link['passage_name'] et on le garde dans name pour la suite.
        name = link["passage_name"]
        # On rassemble dans cache_key les 4 éléments explicitement indiqués, en conservant leur
        # structure.
        cache_key = (vineyard, year, link["parcel_name"], name)
        # On vérifie ce cas avant la suite : cache_key ne figure pas dans passage_cache.
        if cache_key not in passage_cache:
            # On garde dans passage_cache[cache_key] la valeur renvoyée par check_passage_outputs.
            passage_cache[cache_key] = check_passage_outputs(
                nas_processing_root, vineyard, year, name
            )
        # On garde dans observation une copie de passage_cache[cache_key] pour travailler sur cet objet
        # séparément.
        observation = passage_cache[cache_key].copy()
        # On choisit la valeur de consistent selon ce test : le test parcel['found_in_parcel_mapping']
        # est satisfait. Les deux résultats possibles restent définis explicitement ici.
        consistent = (
            link["parcel_name"] in parcel["parcel_names"]
            if parcel["found_in_parcel_mapping"]
            else None
        )
        # On ajoute {'Vineyard': vineyard, 'project_year': year, 'acquisition_id_normalise':
        # acquisition_id_n… à la fin de associations ; les éléments précédents restent conservés.
        associations.append(
            {
                # On renseigne le domaine concerné sous la clé 'Vineyard'.
                "Vineyard": vineyard,
                # On associe la clé 'project_year' à cette valeur dans cet objet.
                "project_year": year,
                # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                # 'acquisition_id_normalise'.
                "acquisition_id_normalise": acquisition_id_normalise,
                # On associe la clé 'parcel_name' à cette valeur dans cet objet.
                "parcel_name": link["parcel_name"],
                # On associe la clé 'passage_name' à cette valeur dans cet objet.
                "passage_name": name,
                # On associe la clé 'parcel_mapping_consistent' à cette valeur dans cet objet.
                "parcel_mapping_consistent": consistent,
                # On renseigne la date du contrôle sous la clé 'checked_at'.
                "checked_at": run_checked_at,
                **observation,
            }
        )

    # Synthèse acquisition : True signifie que TOUS les passages associés
    # satisfont la preuve concernée. Les détails restent dans le CSV associations.
    passage = empty_passage_outputs()
    # Cette branche traite le cas où les associations entre acquisitions et passages est évalué comme
    # vrai.
    if associations:
        # On initialise passage['passage_outputs_verifiable'] à True ; les branches suivantes pourront
        # modifier cet état.
        passage["passage_outputs_verifiable"] = True
        # On utilise ce texte pour passage['passage_verification_note'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        passage["passage_verification_note"] = "Synthèse de tous les passages associés."
        # On parcourt ('passage_created', 'vitimap_created', 'stocks_json_exists', 'has_non_hea… ;
        # field désigne l’élément courant à chaque passage dans la boucle.
        for field in (
            "passage_created",
            "vitimap_created",
            "stocks_json_exists",
            "has_non_healthy_status",
            "vitiparcel_output_present",
            "vitiparcel_created",
        ):
            # On garde dans passage[field] un booléen indiquant si tous les éléments satisfont le test
            # de (bool(item[field]) for item in associations).
            passage[field] = all(bool(item[field]) for item in associations)
        # On parcourt ('passage_path', 'vitimap_geojson_path', 'stocks_json_path', 'passage_err… ;
        # field désigne l’élément courant à chaque passage dans la boucle.
        for field in (
            "passage_path",
            "vitimap_geojson_path",
            "stocks_json_path",
            "passage_error",
            "vitimap_error",
            "vitiparcel_error",
        ):
            # On garde dans passage[field] le texte formé en réunissant les éléments avec ' | ' comme
            # séparateur.
            passage[field] = " | ".join(
                dict.fromkeys(str(item[field]) for item in associations if item[field])
            )
        # On parcourt ('stock_status_count', 'non_healthy_status_count') ; field désigne l’élément
        # courant à chaque passage dans la boucle.
        for field in ("stock_status_count", "non_healthy_status_count"):
            # On garde dans passage[field] la somme des valeurs de (item[field] for item in
            # associations).
            passage[field] = sum(item[field] for item in associations)
        # On parcourt ('stock_status_values', 'non_healthy_status_values') ; field désigne l’élément
        # courant à chaque passage dans la boucle.
        for field in ("stock_status_values", "non_healthy_status_values"):
            # On garde dans passage[field] le texte formé en réunissant les éléments avec ' | ' comme
            # séparateur.
            passage[field] = " | ".join(
                sorted(
                    set(
                        value
                        for item in associations
                        for value in item[field].split(" | ")
                        if value
                    ),
                    # On fournit la clé de l’élément via le paramètre key de cet appel.
                    key=str.casefold,
                )
            )
    # On initialise mapping_consistent à None : aucune valeur n’a encore été retenue ici.
    mapping_consistent = None
    # Cette branche traite le cas où les associations entre acquisitions et passages est évalué comme
    # vrai et le test parcel['found_in_parcel_mapping'] est satisfait.
    if associations and parcel["found_in_parcel_mapping"]:
        # On garde dans mapping_consistent un booléen indiquant si tous les éléments satisfont le test
        # de (item['parcel_mapping_consistent'] is True for item in associations).
        mapping_consistent = all(
            item["parcel_mapping_consistent"] is True for item in associations
        )

    # On regroupe dans result ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    result: dict[str, Any] = {
        # On renseigne le domaine concerné sous la clé 'Vineyard'.
        "Vineyard": vineyard,
        # On associe la clé 'project_year' à cette valeur dans cet objet.
        "project_year": year,
        # On associe la clé 'acquisition_id_base' à cette valeur dans cet objet.
        "acquisition_id_base": acquisition_id_base,
        # On renseigne l’identifiant normalisé de l’acquisition sous la clé 'acquisition_id_normalise'.
        "acquisition_id_normalise": acquisition_id_normalise,
        # On renseigne le statut du suivi Excel sous la clé 'excel_pipeline_status'.
        "excel_pipeline_status": row.get("Statut_pipeline", pd.NA),
        **raw,
        **processing,
        # On renseigne la présence dans les correspondances de parcelles sous la clé
        # 'found_in_parcel_mapping'.
        "found_in_parcel_mapping": parcel["found_in_parcel_mapping"],
        # On associe la clé 'parcel_name' à cette valeur dans cet objet.
        "parcel_name": parcel["parcel_name"],
        # On associe la clé 'parcel_names_json' à cette valeur dans cet objet.
        "parcel_names_json": json.dumps(parcel["parcel_names"], ensure_ascii=False),
        # On associe la clé 'parcel_count' à cette valeur dans cet objet.
        "parcel_count": parcel["parcel_count"],
        # On associe la clé 'passage_link_count' à cette valeur dans cet objet.
        "passage_link_count": len(associations),
        # On associe la clé 'passage_links_json' à cette valeur dans cet objet.
        "passage_links_json": json.dumps(
            # On choisit ici si les caractères accentués doivent être échappés dans le JSON.
            passage_mapping["passage_links"], ensure_ascii=False
        ),
        # On associe la clé '_association_results' à cette valeur dans cet objet.
        "_association_results": associations,
        # On renseigne la présence dans les correspondances de passages sous la clé
        # 'found_in_passage_mapping'.
        "found_in_passage_mapping": passage_mapping["found_in_passage_mapping"],
        # On associe la clé 'passage_parcel_name' à cette valeur dans cet objet.
        "passage_parcel_name": passage_mapping["passage_parcel_name"],
        # On associe la clé 'passage_name' à cette valeur dans cet objet.
        "passage_name": passage_mapping["passage_name"],
        # On associe la clé 'parcel_mapping_consistent' à cette valeur dans cet objet.
        "parcel_mapping_consistent": mapping_consistent,
        **passage,
        # On renseigne la date du contrôle sous la clé 'checked_at'.
        "checked_at": run_checked_at,
    }
    # On garde dans result['native_backup_evidence'] le libellé des constats disponibles pour ce côté.
    result["native_backup_evidence"] = side_evidence_label(
        result["raw_has_full_size_left"],
        result["raw_has_full_size_right"],
        "PNG",
    )
    # On garde dans result['image_processing_evidence'] le libellé des constats disponibles pour ce
    # côté.
    result["image_processing_evidence"] = side_evidence_label(
        result["processing_has_webp_left"],
        result["processing_has_webp_right"],
        "WEBP",
    )
    # On garde dans result['maximum_evidence_stage'] la valeur renvoyée par determine_maximum_stage.
    result["maximum_evidence_stage"] = determine_maximum_stage(result)
    # On garde dans result['check_duration_seconds'] la valeur arrondie de time.perf_counter() -
    # started_at.
    result["check_duration_seconds"] = round(time.perf_counter() - started_at, 3)
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


def build_passage_report(associations_df: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par vignoble/année/parcelle/passage du périmètre contrôlé.

    Les observations d'un passage sont identiques grâce au cache ; on garde
    une observation et la liste dédupliquée des acquisitions contrôlées.
    Ce bilan n'inventorie pas les passages hors du référentiel sélectionné.
    """
    # On rassemble dans columns les 22 éléments explicitement indiqués, en conservant leur structure.
    columns = [
        "Vineyard",
        "project_year",
        "parcel_name",
        "passage_name",
        "acquisitions_controlled_count",
        "acquisition_ids_json",
        "passage_path",
        "passage_created",
        "vitimap_geojson_path",
        "vitimap_created",
        "stocks_json_path",
        "stocks_json_exists",
        "stock_status_count",
        "stock_status_values",
        "non_healthy_status_count",
        "non_healthy_status_values",
        "has_non_healthy_status",
        "vitiparcel_created",
        "passage_error",
        "vitimap_error",
        "vitiparcel_error",
        "checked_at",
    ]
    # On traite à part le tableau associations_df lorsqu’il est vide.
    if associations_df.empty:
        # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
        return pd.DataFrame(columns=columns)
    # On rassemble dans keys les 4 éléments explicitement indiqués, en conservant leur structure.
    keys = ["Vineyard", "project_year", "parcel_name", "passage_name"]
    # On prépare rows comme liste vide ; on la remplira au fil des opérations suivantes.
    rows = []
    # On parcourt associations_df.groupby(keys, sort=True, dropna=False) ; (_, group) désigne l’élément
    # courant à chaque passage dans la boucle.
    for _, group in associations_df.groupby(keys, sort=True, dropna=False):
        # On garde dans observation le contenu de group.iloc[0] sous forme de dictionnaires, selon
        # l’orientation indiquée.
        observation = group.iloc[0].to_dict()
        # On garde dans identifiers les éléments triés de
        # set(group['acquisition_id_normalise'].astype(str)) dans une nouvelle liste.
        identifiers = sorted(set(group["acquisition_id_normalise"].astype(str)))
        # On garde dans observation['acquisitions_controlled_count'] le nombre d’éléments de
        # identifiers.
        observation["acquisitions_controlled_count"] = len(identifiers)
        # On prépare une représentation JSON ; les options ci-dessous fixent les détails de
        # sérialisation.
        observation["acquisition_ids_json"] = json.dumps(
            # On choisit ici si les caractères accentués doivent être échappés dans le JSON.
            identifiers, ensure_ascii=False
        )
        # On ajoute observation à la fin de rows ; les éléments précédents restent conservés.
        rows.append(observation)
    # On fournit à l’appelant la valeur renvoyée par pd.DataFrame(rows).reindex.
    return pd.DataFrame(rows).reindex(columns=columns)


def print_passage_summary(
    acquisitions_df: pd.DataFrame,
    passages_df: pd.DataFrame,
    associations_path: Path,
    passages_path: Path,
) -> None:
    """Affiche des compteurs de passages, distincts des compteurs acquisition."""
    # On garde dans total le nombre d’éléments de passages_df.
    total = len(passages_df)
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("BILAN PAR PASSAGE DISTINCT — PÉRIMÈTRE DES ACQUISITIONS CONTRÔLÉES")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  Acquisitions contrôlées : {len(acquisitions_df)}")
    # On garde dans no_passage la conversion numérique de
    # (~acquisitions_df['found_in_passage_mapping'].astype(bool)).sum() en entier.
    no_passage = int((~acquisitions_df["found_in_passage_mapping"].astype(bool)).sum())
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  Acquisitions sans passage identifié : {no_passage}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  Passages distincts identifiés : {total}")
    # On parcourt (('Passages avec dossier', 'passage_created'), ('Passages avec Vitimap',… ; (label,
    # field) désigne l’élément courant à chaque passage dans la boucle.
    for label, field in (
        ("Passages avec dossier", "passage_created"),
        ("Passages avec Vitimap", "vitimap_created"),
        ("Passages avec fichier de stocks", "stocks_json_exists"),
        ("Passages avec status non sain", "has_non_healthy_status"),
        ("Passages satisfaisant le critère Vitiparcel", "vitiparcel_created"),
    ):
        # On choisit la valeur de positive selon ce test : total est évalué comme vrai. Les deux
        # résultats possibles restent définis explicitement ici.
        positive = (
            int(passages_df[field].fillna(False).astype(bool).sum()) if total else 0
        )
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(f"  {label} : {positive}/{total}")
    # On fixe error_count à 0 pour cette étape.
    error_count = 0
    # Cette branche traite le cas où total est évalué comme vrai.
    if total:
        # On garde dans error_count la conversion numérique de passages_df[['passage_error',
        # 'vitimap_error', 'vitiparcel_error']].filln… en entier.
        error_count = int(
            passages_df[["passage_error", "vitimap_error", "vitiparcel_error"]]
            .fillna("")
            # On indique l’axe de l’opération : sa valeur distingue le travail sur les lignes ou sur
            # les colonnes.
            .apply(lambda row: any(bool(value) for value in row), axis=1)
            .sum()
        )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  Passages avec erreur technique : {error_count}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        "  Plusieurs acquisitions peuvent partager un passage : celui-ci n'est compté qu'une fois."
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Un compteur positif ne constitue pas une validation de qualité du livrable.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  Détail des associations : {associations_path}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  Bilan des passages : {passages_path}")


def print_summary(
    results_df: pd.DataFrame,
    total_duration: float,
    output_path: Path,
) -> None:
    """Affiche une synthèse lisible, chiffrée et interprétée."""

    # On garde dans total le nombre d’éléments de results_df.
    total = len(results_df)

    def count(column: str) -> int:
        # On fournit à l’appelant la conversion numérique de
        # results_df[column].fillna(False).astype(bool).sum() en entier.
        return int(results_df[column].fillna(False).astype(bool).sum())

    # On garde dans both_png le comptage défini par ce module pour les données fournies.
    both_png = count("raw_has_full_size_both_sides")
    # On garde dans any_png le comptage défini par ce module pour les données fournies.
    any_png = count("raw_has_full_size_image")
    # On calcule la différence entre ces deux valeurs pour construire partial_png.
    partial_png = any_png - both_png
    # On calcule la différence entre ces deux valeurs pour construire no_png.
    no_png = total - any_png

    # On garde dans both_webp le comptage défini par ce module pour les données fournies.
    both_webp = count("processing_has_webp_both_sides")
    # On garde dans any_webp le comptage défini par ce module pour les données fournies.
    any_webp = count("processing_has_webp_images")
    # On calcule la différence entre ces deux valeurs pour construire partial_webp.
    partial_webp = any_webp - both_webp
    # On calcule la différence entre ces deux valeurs pour construire no_webp.
    no_webp = total - any_webp

    # On garde dans errors le résultat de la fonction appliquée aux éléments ou à l’axe indiqué de
    # results_df[['raw_error', 'processing_error', 'passage_error', 'v….
    errors = (
        results_df[
            [
                "raw_error",
                "processing_error",
                "passage_error",
                "vitimap_error",
                "vitiparcel_error",
            ]
        ]
        .fillna("")
        # On indique l’axe de l’opération : sa valeur distingue le travail sur les lignes ou sur les
        # colonnes.
        .apply(lambda row: any(bool(value) for value in row), axis=1)
    )

    # On garde dans raw_count le comptage défini par ce module pour les données fournies.
    raw_count = count("found_in_raw_live")
    # On garde dans mapping_count le comptage défini par ce module pour les données fournies.
    mapping_count = count("found_in_parcel_mapping")
    # On garde dans processing_count le comptage défini par ce module pour les données fournies.
    processing_count = count("found_in_processing_live")
    # On garde dans passage_mapping_count le comptage défini par ce module pour les données fournies.
    passage_mapping_count = count("found_in_passage_mapping")
    # On garde dans passage_count le comptage défini par ce module pour les données fournies.
    passage_count = count("passage_created")
    # On garde dans vitimap_count le comptage défini par ce module pour les données fournies.
    vitimap_count = count("vitimap_created")
    # On garde dans stocks_count le comptage défini par ce module pour les données fournies.
    stocks_count = count("stocks_json_exists")
    # On garde dans unhealthy_count le comptage défini par ce module pour les données fournies.
    unhealthy_count = count("has_non_healthy_status")
    # On garde dans vitiparcel_count le comptage défini par ce module pour les données fournies.
    vitiparcel_count = count("vitiparcel_created")
    # On garde dans inconsistent_count la conversion numérique de
    # results_df['parcel_mapping_consistent'].eq(False).sum() en entier.
    inconsistent_count = int(results_df["parcel_mapping_consistent"].eq(False).sum())
    # On garde dans error_count la conversion numérique de errors.sum() en entier.
    error_count = int(errors.sum())

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("=" * 88)
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("📊 RÉSUMÉ DES PREUVES OBSERVÉES")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("=" * 88)
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Acquisitions contrôlées : {total}")

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("1. PRISE EN COMPTE ET SAUVEGARDE NATIVE")
    # On choisit la valeur de raw_symbol selon ce test : raw_count correspond à total. Les deux
    # résultats possibles restent définis explicitement ici.
    raw_symbol = "🟢" if raw_count == total else "🟠"
    # On choisit la valeur de both_png_symbol selon ce test : both_png correspond à total. Les deux
    # résultats possibles restent définis explicitement ici.
    both_png_symbol = "🟢" if both_png == total else "🟠"
    # On choisit la valeur de partial_png_symbol selon ce test : partial_png est évalué comme vrai. Les
    # deux résultats possibles restent définis explicitement ici.
    partial_png_symbol = "🟠" if partial_png else "🟢"
    # On choisit la valeur de no_png_symbol selon ce test : no_png est évalué comme vrai. Les deux
    # résultats possibles restent définis explicitement ici.
    no_png_symbol = "🟠" if no_png else "🟢"
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {raw_symbol} Dossier Brut présent              : {format_ratio(raw_count, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {both_png_symbol} PNG natifs LEFT et RIGHT         : {format_ratio(both_png, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {partial_png_symbol} PNG natifs sur un seul côté      : {format_ratio(partial_png, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {no_png_symbol} Aucun PNG natif démontré         : {format_ratio(no_png, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Lecture : les PNG natifs constituent la preuve retenue de sauvegarde")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  des images pleine taille ; un dossier Brut seul ne suffit pas.")

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("2. MAPPING ET TRAITEMENT D'IMAGES")
    # On choisit la valeur de mapping_symbol selon ce test : mapping_count correspond à total. Les deux
    # résultats possibles restent définis explicitement ici.
    mapping_symbol = "🟢" if mapping_count == total else "🟠"
    # On choisit la valeur de processing_symbol selon ce test : processing_count correspond à total.
    # Les deux résultats possibles restent définis explicitement ici.
    processing_symbol = "🟢" if processing_count == total else "🟠"
    # On choisit la valeur de both_webp_symbol selon ce test : both_webp correspond à total. Les deux
    # résultats possibles restent définis explicitement ici.
    both_webp_symbol = "🟢" if both_webp == total else "🟠"
    # On choisit la valeur de partial_webp_symbol selon ce test : partial_webp est évalué comme vrai.
    # Les deux résultats possibles restent définis explicitement ici.
    partial_webp_symbol = "🟠" if partial_webp else "🟢"
    # On choisit la valeur de no_webp_symbol selon ce test : no_webp est évalué comme vrai. Les deux
    # résultats possibles restent définis explicitement ici.
    no_webp_symbol = "🟠" if no_webp else "🟢"
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {mapping_symbol} Mapping parcelle présent         : {format_ratio(mapping_count, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {processing_symbol} Dossier Processing présent       : {format_ratio(processing_count, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {both_webp_symbol} WEBP LEFT et RIGHT               : {format_ratio(both_webp, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {partial_webp_symbol} WEBP sur un seul côté            : {format_ratio(partial_webp, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {no_webp_symbol} Aucun WEBP démontré              : {format_ratio(no_webp, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Lecture : les WEBP sous processed_imgs constituent la preuve retenue")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  du traitement d'images ; le dossier Processing seul ne suffit pas.")

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("3. PASSAGES ET SORTIES MÉTIER — SYNTHÈSE PAR ACQUISITION")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Une preuve positive signifie que tous les passages associés la satisfont.")
    # On choisit la valeur de passage_mapping_symbol selon ce test : passage_mapping_count correspond à
    # total. Les deux résultats possibles restent définis explicitement ici.
    passage_mapping_symbol = "🟢" if passage_mapping_count == total else "🟠"
    # On choisit la valeur de passage_symbol selon ce test : passage_count correspond à total. Les deux
    # résultats possibles restent définis explicitement ici.
    passage_symbol = "🟢" if passage_count == total else "🟠"
    # On choisit la valeur de vitimap_symbol selon ce test : vitimap_count correspond à total. Les deux
    # résultats possibles restent définis explicitement ici.
    vitimap_symbol = "🟢" if vitimap_count == total else "🟠"
    # On choisit la valeur de stocks_symbol selon ce test : stocks_count correspond à total. Les deux
    # résultats possibles restent définis explicitement ici.
    stocks_symbol = "🟢" if stocks_count == total else "🟠"
    # On choisit la valeur de unhealthy_symbol selon ce test : unhealthy_count correspond à total. Les
    # deux résultats possibles restent définis explicitement ici.
    unhealthy_symbol = "🟢" if unhealthy_count == total else "🟠"
    # On choisit la valeur de vitiparcel_symbol selon ce test : vitiparcel_count correspond à total.
    # Les deux résultats possibles restent définis explicitement ici.
    vitiparcel_symbol = "🟢" if vitiparcel_count == total else "🟠"
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {passage_mapping_symbol} Lien acquisition vers passage   : {format_ratio(passage_mapping_count, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {passage_symbol} Dossier passage présent          : {format_ratio(passage_count, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {vitimap_symbol} GeoJSON Vitimap présent          : {format_ratio(vitimap_count, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {stocks_symbol} stocks.json présent               : {format_ratio(stocks_count, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {unhealthy_symbol} Au moins un status non sain     : {format_ratio(unhealthy_count, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {vitiparcel_symbol} Vitiparcel créé                 : {format_ratio(vitiparcel_count, total)}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Lecture : selon les critères définis, la création de Vitiparcel est")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  démontrée si un fichier *_stocks.json est présent et contient")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  au moins un status non sain dans chaque sortie de passage concernée.")
    # On calcule la différence entre ces deux valeurs pour construire non_verifiable_outputs.
    non_verifiable_outputs = total - count("passage_outputs_verifiable")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  ⚪ Sorties non vérifiables — passage non identifié : {non_verifiable_outputs}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Les compteurs indiquent les preuves positives sur tout le périmètre.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Leur complément inclut les cas non vérifiables, pas seulement les absences.")

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("4. QUALITÉ DU CONTRÔLE")
    # On choisit la valeur de inconsistency_symbol selon ce test : inconsistent_count correspond à 0.
    # Les deux résultats possibles restent définis explicitement ici.
    inconsistency_symbol = "🟢" if inconsistent_count == 0 else "🟠"
    # On choisit la valeur de error_symbol selon ce test : error_count correspond à 0. Les deux
    # résultats possibles restent définis explicitement ici.
    error_symbol = "🟢" if error_count == 0 else "🔴"
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(
        f"  {inconsistency_symbol} Mappings parcelle/passage incohérents : "
        f"{inconsistent_count}"
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  {error_symbol} Acquisitions avec erreur technique    : {error_count}")

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("5. DURÉE")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"  Durée totale  : {format_duration(total_duration)}")
    # Cette branche traite le cas où total est évalué comme vrai.
    if total:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(
            f"  Durée moyenne : {format_duration(total_duration / total)} par acquisition"
        )

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("CONCLUSION AUTOMATIQUE")
    # On vérifie ce cas avant la suite : raw_count correspond à total.
    if raw_count == total:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("  🟢 Toutes les acquisitions contrôlées possèdent un dossier Brut.")
    else:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(f"  🟠 {total - raw_count} acquisition(s) sans dossier Brut démontré.")
    # On vérifie ce cas avant la suite : both_png correspond à total.
    if both_png == total:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(
            "  🟢 La sauvegarde native LEFT et RIGHT est démontrée pour tout le périmètre."
        )
    # On vérifie ce cas avant la suite : any_png correspond à total.
    elif any_png == total:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("  🟠 Toutes ont des PNG, mais certaines n'en ont que sur un seul côté.")
    else:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(f"  🟠 {no_png} acquisition(s) sans preuve de PNG natif.")
    # On vérifie ce cas avant la suite : both_webp correspond à total.
    if both_webp == total:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(
            "  🟢 Le traitement WEBP LEFT et RIGHT est démontré pour tout le périmètre."
        )
    # On vérifie ce cas avant la suite : any_webp correspond à total.
    elif any_webp == total:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("  🟠 Toutes ont des WEBP, mais certaines n'en ont que sur un seul côté.")
    else:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(f"  🟠 {no_webp} acquisition(s) sans preuve de traitement WEBP.")
    # On garde dans verifiable_count le comptage défini par ce module pour les données fournies.
    verifiable_count = count("passage_outputs_verifiable")
    # On calcule la différence entre ces deux valeurs pour construire non_verifiable_count.
    non_verifiable_count = total - verifiable_count
    # On calcule la différence entre ces deux valeurs pour construire unsatisfied_count.
    unsatisfied_count = verifiable_count - vitiparcel_count
    # On vérifie ce cas avant la suite : vitiparcel_count correspond à total.
    if vitiparcel_count == total:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log(
            "  🟢 Le critère Vitiparcel est satisfait pour toutes les acquisitions contrôlées."
        )
    else:
        # Cette branche traite le cas où unsatisfied_count est évalué comme vrai.
        if unsatisfied_count:
            # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
            # associées.
            log(
                f"  🟠 {unsatisfied_count} acquisition(s) avec passage identifié "
                "ne satisfont pas le critère Vitiparcel."
            )
        # Cette branche traite le cas où non_verifiable_count est évalué comme vrai.
        if non_verifiable_count:
            # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
            # associées.
            log(
                f"  ⚪ {non_verifiable_count} acquisition(s) : critère Vitiparcel "
                "non vérifiable, passage non identifié."
            )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  Ces conclusions décrivent les preuves techniques observées, pas une")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("  validation métier définitive du pipeline.")

    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"📄 Bilan local : {output_path}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("🔒 NAS : aucune création, modification, suppression ou copie.")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("=" * 88)


def main() -> None:
    """Point d'entrée du contrôle en lecture seule."""

    # On garde dans args la valeur renvoyée par parse_arguments.
    args = parse_arguments()
    # On garde dans started_at la valeur renvoyée par time.perf_counter.
    started_at = time.perf_counter()
    # On garde dans run_datetime l’instant courant avec le fuseau indiqué, lorsqu’il est fourni.
    run_datetime = datetime.now(timezone.utc)
    # On garde dans run_checked_at la représentation ISO de run_datetime.
    run_checked_at = run_datetime.isoformat()

    # On appelle configure_nas_environment avec PROJECT_ROOT.
    configure_nas_environment(PROJECT_ROOT, local_loader=load_dotenv)
    # On garde dans nas_raw_root un objet chemin local ; sa construction seule ne prouve pas que le
    # fichier existe.
    nas_raw_root = Path(os.getenv("NAS_BRUT_ROOT", ""))
    # On garde dans nas_processing_root un objet chemin local ; sa construction seule ne prouve pas que
    # le fichier existe.
    nas_processing_root = Path(os.getenv("NAS_PROCESSING_ROOT", ""))

    # Cette branche traite le cas où la condition os.getenv('NAS_BRUT_ROOT') n’est pas remplie.
    if not os.getenv("NAS_BRUT_ROOT"):
        # On interrompt cette branche avec ValueError : 'NAS_BRUT_ROOT est absent du fichier .env.'.
        raise ValueError("NAS_BRUT_ROOT est absent du fichier .env.")
    # Cette branche traite le cas où la condition os.getenv('NAS_PROCESSING_ROOT') n’est pas remplie.
    if not os.getenv("NAS_PROCESSING_ROOT"):
        # On interrompt cette branche avec ValueError : 'NAS_PROCESSING_ROOT est absent du fichier
        # .env.'.
        raise ValueError("NAS_PROCESSING_ROOT est absent du fichier .env.")
    # Cette branche traite le cas où la condition nas_raw_root.is_dir() n’est pas remplie.
    if not nas_raw_root.is_dir():
        # On interrompt cette branche avec FileNotFoundError.
        raise FileNotFoundError(f"Racine Brut inaccessible : {nas_raw_root}")
    # Cette branche traite le cas où la condition nas_processing_root.is_dir() n’est pas remplie.
    if not nas_processing_root.is_dir():
        # On interrompt cette branche avec FileNotFoundError.
        raise FileNotFoundError(
            f"Racine Processing inaccessible : {nas_processing_root}"
        )

    # On choisit la valeur de reference_path selon ce test : args.reference est absolu. Les deux
    # résultats possibles restent définis explicitement ici.
    reference_path = (
        args.reference
        if args.reference.is_absolute()
        else PROJECT_ROOT / args.reference
    )
    # On choisit la valeur de output_dir selon ce test : args.output_dir est absolu. Les deux résultats
    # possibles restent définis explicitement ici.
    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else PROJECT_ROOT / args.output_dir
    )

    # On garde dans vineyard le texte args.vineyard sans les caractères de bord indiqués, ou sans les
    # espaces de bord par défaut.
    vineyard = args.vineyard.strip()
    # On retient pour parcel_mapping_file la première valeur évaluée comme vraie dans cette chaîne de
    # replis ; une valeur vide fera donc passer à la suivante.
    parcel_mapping_file = args.parcel_mapping or (
        nas_processing_root
        / vineyard
        / "parcels"
        / f"{vineyard}_parcels_acquisitions_map.json"
    )
    # On retient pour passage_mapping_file la première valeur évaluée comme vraie dans cette chaîne de
    # replis ; une valeur vide fera donc passer à la suivante.
    passage_mapping_file = args.passage_mapping or (
        nas_processing_root
        / vineyard
        / "passages"
        / f"{vineyard}_parcels_passages_acquisitions_map.json"
    )

    # On garde dans reference_df la valeur renvoyée par load_reference.
    reference_df = load_reference(
        reference_path,
        vineyard,
        args.year,
        args.acquisition_id,
        args.limit,
    )
    # On traite à part le tableau reference_df lorsqu’il est vide.
    if reference_df.empty:
        # On interrompt cette branche avec ValueError.
        raise ValueError(f"Aucune acquisition {args.year} trouvée pour {vineyard}.")

    # On répartit les valeurs renvoyées par load_json_file entre (parcel_data, parcel_load_error) ;
    # leur ordre doit correspondre à celui prévu par cet appel.
    parcel_data, parcel_load_error = load_json_file(parcel_mapping_file)
    # On répartit les valeurs renvoyées par load_json_file entre (passage_data, passage_load_error) ;
    # leur ordre doit correspondre à celui prévu par cet appel.
    passage_data, passage_load_error = load_json_file(passage_mapping_file)
    # On répartit les valeurs renvoyées par build_parcel_mapping_index entre (parcel_index,
    # parcel_index_error) ; leur ordre doit correspondre à celui prévu par cet appel.
    parcel_index, parcel_index_error = build_parcel_mapping_index(parcel_data)
    # On répartit les valeurs renvoyées par build_passage_mapping_index entre (passage_index,
    # passage_index_error) ; leur ordre doit correspondre à celui prévu par cet appel.
    passage_index, passage_index_error = build_passage_mapping_index(passage_data)

    # On construit mapping_errors comme une liste à partir de error, pour chaque error de
    # [parcel_load_error, parcel_index_error, passage_load_error, pass… en ne gardant que les éléments
    # qui passent le filtre.
    mapping_errors = [
        error
        for error in [
            parcel_load_error,
            parcel_index_error,
            passage_load_error,
            passage_index_error,
        ]
        if error
    ]

    # On appelle print_header avec vineyard.
    print_header(
        vineyard,
        args.year,
        len(reference_df),
        nas_raw_root,
        nas_processing_root,
        args.verbose,
    )
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Mapping parcelles : {parcel_mapping_file}")
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log(f"Mapping passages : {passage_mapping_file}")
    # Cette branche traite le cas où mapping_errors est évalué comme vrai.
    if mapping_errors:
        # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs
        # associées.
        log("Avertissements mapping : " + " | ".join(mapping_errors))
    # On transmet cette information à log pour garder une trace de l’étape et de ses valeurs associées.
    log("")

    # On prépare results comme liste vide ; on la remplira au fil des opérations suivantes.
    results: list[dict[str, Any]] = []
    # On crée le dictionnaire vide passage_cache pour y ranger ensuite les éléments par clé.
    passage_cache: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    # On garde dans total le nombre d’éléments de reference_df.
    total = len(reference_df)

    # On parcourt reference_df.iterrows() ; (index, row) désigne l’élément courant à chaque passage
    # dans la boucle.
    for index, row in reference_df.iterrows():
        # On garde dans result la valeur renvoyée par build_result.
        result = build_result(
            row,
            nas_raw_root,
            nas_processing_root,
            vineyard,
            args.year,
            parcel_index,
            passage_index,
            passage_cache,
            run_checked_at,
        )
        # On ajoute result à la fin de results ; les éléments précédents restent conservés.
        results.append(result)
        # On appelle print_acquisition_result avec index + 1.
        print_acquisition_result(index + 1, total, result, args.verbose)

    # On construit association_rows comme une liste à partir de item, pour chaque result de results.
    association_rows = [
        item for result in results for item in result.pop("_association_results")
    ]
    # On garde dans associations_df un tableau pandas construit avec les données indiquées.
    associations_df = pd.DataFrame(association_rows)
    # On traite à part le tableau associations_df lorsqu’il est vide.
    if associations_df.empty:
        # On garde dans associations_df un tableau pandas construit avec les données indiquées.
        associations_df = pd.DataFrame(
            # On décrit les colonnes à présenter, distinctes des lignes de données.
            columns=[
                "Vineyard",
                "project_year",
                "acquisition_id_normalise",
                "parcel_name",
                "passage_name",
                "parcel_mapping_consistent",
                "passage_created",
                "vitimap_created",
                "stocks_json_exists",
                "has_non_healthy_status",
                "vitiparcel_created",
                "checked_at",
            ]
        )
    # On garde dans passages_df la valeur renvoyée par build_passage_report.
    passages_df = build_passage_report(associations_df)
    # On garde dans results_df un tableau pandas construit avec les données indiquées.
    results_df = pd.DataFrame(results)
    # On prépare le dossier local nécessaire à cette sortie ; créer le dossier ne produit pas encore
    # le fichier qu’il contiendra.
    output_dir.mkdir(parents=True, exist_ok=True)
    # On garde dans safe_vineyard la version en minuscules de re.sub('[^A-Za-z0-9_-]+', '_',
    # vineyard).strip('_').
    safe_vineyard = re.sub(r"[^A-Za-z0-9_-]+", "_", vineyard).strip("_").lower()
    # On garde dans timestamp la date run_datetime mise en forme selon le modèle indiqué.
    timestamp = run_datetime.strftime("%Y-%m-%dT%H-%M-%SZ")
    # On construit output_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
    # crée ni dossier ni fichier.
    output_path = output_dir / (f"{safe_vineyard}_live_nas_evidence_{timestamp}.csv")
    # On appelle results_df.to_csv avec output_path.
    results_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    # On construit associations_path en assemblant les morceaux du chemin. L’opérateur / de pathlib
    # ne crée ni dossier ni fichier.
    associations_path = (
        output_dir / f"{safe_vineyard}_live_nas_associations_{timestamp}.csv"
    )
    # On construit passages_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
    # crée ni dossier ni fichier.
    passages_path = output_dir / f"{safe_vineyard}_live_nas_passages_{timestamp}.csv"
    # On appelle associations_df.to_csv avec associations_path.
    associations_df.to_csv(associations_path, index=False, encoding="utf-8-sig")
    # On appelle passages_df.to_csv avec passages_path.
    passages_df.to_csv(passages_path, index=False, encoding="utf-8-sig")

    # On appelle print_summary avec results_df.
    print_summary(
        results_df,
        time.perf_counter() - started_at,
        output_path,
    )
    # On appelle print_passage_summary avec results_df.
    print_passage_summary(results_df, passages_df, associations_path, passages_path)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On appelle main sans argument positionnel.
    main()
