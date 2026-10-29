# Lecture du fichier — Enchaînement local de la sélection, de l’extraction et du rapprochement.
# On conserve les sorties et leur manifeste pour relier les résultats à une exécution. Lancer ce
# programme peut lire les sources et écrire des fichiers locaux.
#

"""Pilote local : extraction NAS puis rapprochement Excel, sans saisie du run-id.

À placer dans scripts/run_local_pipeline.py, à la racine du projet.
Utilise les options --output-dir et --reference déjà présentes dans les scripts.
Dossiers courts (AAAAMMJJ_identifiant / v01, v02...) pour limiter les chemins Windows.
Aucune lecture directe des images/JSON NAS ni écriture sur le NAS par ce pilote.
Les erreurs d'observation restent dans les CSV : succès technique != conformité métier.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On importe csv. On transforme les tableaux entre lignes Python et fichiers CSV.
import csv
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe time. On mesure des durées ou on gère les attentes prévues par ce fichier.
import time
# On importe uuid. Ce module sera utilisé par les opérations de ce fichier.
import uuid
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path

# On récupère Path(__file__).resolve().parents[1] et on le garde dans PROJECT_ROOT pour la suite.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# On garde dans PACKAGE_PATH un objet chemin local ; sa construction seule ne prouve pas que le fichier
# existe.
PACKAGE_PATH = Path("src/suivi_traitements_post_saison")
# On garde dans REFERENCE_PATH un objet chemin local ; sa construction seule ne prouve pas que le
# fichier existe.
REFERENCE_PATH = Path(
    "data/03_normalized/suivi_acquisitions_normalises/toutes_acquisitions_normalisees.csv"
)
# On rassemble dans LABELS les 3 éléments explicitement indiqués, en conservant leur structure.
LABELS = ("evidence", "associations", "passages")
# On rassemble dans OUTPUT_LABELS les 3 éléments explicitement indiqués, en conservant leur structure.
OUTPUT_LABELS = ("acquisitions", "associations", "passages")


# On produit l’instant courant en UTC avec son fuseau pour éviter les heures locales ambiguës.
def utc_now():
    # On fournit à l’appelant la représentation ISO de datetime.now(timezone.utc).
    return datetime.now(timezone.utc).isoformat()


def local_data_path(root: Path, path: Path) -> Path:
    """Interdit de placer les écritures hors du dossier data du projet local."""
    # On calcule le chemin local résolu pour détecter les redirections avant de vérifier qu’il reste
    # dans le projet.
    resolved = path.resolve()
    # Les sorties de ce parcours sont attendues sous data. Un chemin qui en sort n’est pas une
    # destination autorisée.
    if not resolved.is_relative_to((root / "data").resolve()):
        # On interrompt cette branche avec ValueError.
        raise ValueError(f"Chemin hors du dossier data local : {path}")
    # On remet le chemin résolu à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return resolved


def safe_stem(vineyard: str) -> str:
    # On garde dans stem la version en minuscules de re.sub('[^A-Za-z0-9_-]+', '_',
    # vineyard).strip('_').
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", vineyard).strip("_").lower()
    # On prévoit le cas où stem est évalué comme faux, par exemple une valeur vide selon son type.
    if not stem:
        # On interrompt cette branche avec ValueError : 'Nom de vignoble sans caractère utilisable pour
        # les fichiers.'.
        raise ValueError("Nom de vignoble sans caractère utilisable pour les fichiers.")
    # On remet stem à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return stem


def read_csv(path: Path):
    # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la sortie, y
    # compris après une erreur.
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        # On associe les cellules CSV aux noms des colonnes, pour ne pas dépendre uniquement de leur
        # position.
        reader = csv.DictReader(stream)
        # Cette branche traite le cas où la condition reader.fieldnames n’est pas remplie.
        if not reader.fieldnames:
            # On interrompt cette branche avec ValueError.
            raise ValueError(f"CSV sans en-tête : {path.name}")
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return reader.fieldnames, list(reader)


# On retrouve les domaines demandés dans les données disponibles et on évite les doublons de
# sélection.
def select_vineyards(
    reference: Path, requested: list[str], all_vineyards: bool, year: int
):
    # On répartit les valeurs renvoyées par read_csv entre (fields, rows) ; leur ordre doit
    # correspondre à celui prévu par cet appel.
    fields, rows = read_csv(reference)
    # Cette branche traite le cas où la condition {'Vineyard',
    # 'Acquisition_ID_normalise'}.issubset(fields) n’est pas remplie.
    if not {"Vineyard", "Acquisition_ID_normalise"}.issubset(fields):
        # On interrompt cette branche avec ValueError : 'Référentiel : Vineyard et
        # Acquisition_ID_normalise obligatoires.'.
        raise ValueError(
            "Référentiel : Vineyard et Acquisition_ID_normalise obligatoires."
        )
    # On crée le dictionnaire vide available pour y ranger ensuite les éléments par clé.
    available = {}
    # On parcourt les lignes ; row désigne l’élément courant à chaque passage dans la boucle.
    for row in rows:
        # Cette branche traite le cas où la condition re.search(f'(?<!\\d){year}-\\d{{2}}-\\d{{2}}T',
        # row['Acquisition_ID_normalise'] or '') n’est pas remplie.
        if not re.search(
            rf"(?<!\d){year}-\d{{2}}-\d{{2}}T", row["Acquisition_ID_normalise"] or ""
        ):
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On garde dans vineyard le texte row['Vineyard'] or '' sans les caractères de bord indiqués,
        # ou sans les espaces de bord par défaut.
        vineyard = (row["Vineyard"] or "").strip()
        # On prévoit le cas où vineyard est évalué comme faux, par exemple une valeur vide selon son
        # type.
        if not vineyard:
            # On interrompt cette branche avec ValueError : 'Vignoble vide dans le référentiel du
            # périmètre.'.
            raise ValueError("Vignoble vide dans le référentiel du périmètre.")
        # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
        # enregistré dans les données sources.
        key = vineyard.casefold()
        # Cette branche traite le cas où la clé de l’élément appartient à available et available[key]
        # diffère du domaine concerné.
        if key in available and available[key] != vineyard:
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                f"Noms de vignoble contradictoires : {available[key]} / {vineyard}"
            )
        # On gardu domaine concerné sous le nom available[key] ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        available[key] = vineyard
    # On prévoit le cas où available est évalué comme faux, par exemple une valeur vide selon son type.
    if not available:
        # On interrompt cette branche avec ValueError.
        raise ValueError(f"Aucune acquisition {year} dans le référentiel.")
    # On choisit explicitement la valeur selon all_vineyards ; les deux cas restent visibles ici
    # plutôt que dépendre d’un réglage implicite.
    selected = sorted(available.values(), key=str.casefold) if all_vineyards else []
    # On prévoit le cas où all_vineyards est évalué comme faux, par exemple une valeur vide selon son
    # type.
    if not all_vineyards:
        # On parcourt requested ; name désigne l’élément courant à chaque passage dans la boucle.
        for name in requested:
            # On garde dans key la forme de name.strip() adaptée aux comparaisons sans distinction de
            # casse.
            key = name.strip().casefold()
            # On vérifie ce cas avant la suite : la clé de l’élément ne figure pas dans available.
            if key not in available:
                # On interrompt cette branche avec ValueError.
                raise ValueError(f"Vignoble absent du référentiel {year} : {name}")
            # On vérifie ce cas avant la suite : available[key] ne figure pas dans la sélection
            # retenue.
            if available[key] not in selected:
                # On ajoute available[key] à la fin de selected ; les éléments précédents restent
                # conservés.
                selected.append(available[key])
    # On construit stems comme une liste à partir de safe_stem(name), pour chaque name de selected.
    stems = [safe_stem(name) for name in selected]
    # On compare le nombre d’éléments au nombre de valeurs distinctes pour repérer les doublons
    # avant de poursuivre.
    if len(stems) != len(set(stems)):
        # On interrompt cette branche avec ValueError : 'Deux noms de vignoble produisent le même nom
        # de fichier.'.
        raise ValueError("Deux noms de vignoble produisent le même nom de fichier.")
    # On remet la sélection retenue à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return selected


# On conserve les métadonnées de cette tentative pour relier les fichiers produits à leur exécution.
def write_manifest(path: Path, payload: dict):
    # On garde dans temporary la valeur renvoyée par path.with_suffix pour '.json.tmp'.
    temporary = path.with_suffix(".json.tmp")
    # On écrit le texte préparé avec l’encodage indiqué ; cette opération remplace le contenu de ce
    # fichier.
    temporary.write_text(
        # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
        # décodé selon un réglage implicite du poste.
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # On remplace la destination avec le fichier temporaire préparé, pour éviter de publier
    # directement un contenu en cours d’écriture.
    temporary.replace(path)


def console(message):
    # Évite qu'une console Windows ancienne interrompe le traitement d'un log.
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    # On tente ce bloc et on traite séparément les erreurs prévues : UnicodeEncodeError.
    try:
        # On écrit message + '\n' dans sys.stdout ; le mode d’ouverture du flux détermine s’il s’agit
        # d’un ajout ou d’un remplacement.
        sys.stdout.write(message + "\n")
    except UnicodeEncodeError:
        # On écrit message.encode(encoding, errors='replace').decode(encoding) + '\n' dans sys.stdout ;
        # le mode d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        sys.stdout.write(
            message.encode(encoding, errors="replace").decode(encoding) + "\n"
        )
    # On vidu tampon d’écriture de sys.stdout vers sa destination ; cela ne remplace pas, à lui
    # seul, une synchronisation durable du fichier.
    sys.stdout.flush()


def run_command(command: list[str], root: Path, log_path: Path) -> int:
    """Même Python que le venv actif ; pas de shell ; logs UTF-8 et terminal."""
    # On garde dans environment une copie de os.environ pour travailler sur cet objet séparément.
    environment = os.environ.copy()
    # On utilise ce texte pour environment['PYTHONIOENCODING'] ; il ne dépend pas d’une valeur
    # récupérée ailleurs à cet endroit.
    environment["PYTHONIOENCODING"] = "utf-8"
    # On utilise ce texte pour environment['PYTHONUNBUFFERED'] ; il ne dépend pas d’une valeur
    # récupérée ailleurs à cet endroit.
    environment["PYTHONUNBUFFERED"] = "1"
    # On ouvre cette sortie en écriture ; le contenu précédent serait remplacé. La fermeture du
    # fichier est gérée à la sortie du bloc.
    with log_path.open("w", encoding="utf-8") as log:
        # On démarre le processus enfant avec les paramètres contrôlés, sans construire ici une
        # commande de shell libre.
        process = subprocess.Popen(
            command,
            # On impose le dossier de travail du processus enfant ; les chemins relatifs ne dépendent
            # ainsi pas du terminal de départ.
            cwd=root,
            # On transmet cet environnement au processus plutôt que reprendre implicitement toutes les
            # variables du parent.
            env=environment,
            # On dirige la sortie normale vers la destination prévue pour les traces.
            stdout=subprocess.PIPE,
            # On indique où envoyer les erreurs ; STDOUT les rassemble avec la sortie normale.
            stderr=subprocess.STDOUT,
            # On fournit le texte de travail via le paramètre text de cet appel.
            text=True,
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8",
            # On définit ce que la conversion fera des valeurs invalides, au lieu de laisser ce cas
            # implicite.
            errors="replace",
        )
        # On tente ce bloc et on traite séparément les erreurs prévues : BaseException.
        try:
            # On doit disposer du flux de sortie avant du parcourir et du recopier dans le
            # journal.
            assert process.stdout is not None
            # On parcourt process.stdout ; line désigne l’élément courant à chaque passage dans la
            # boucle.
            for line in process.stdout:
                # On écrit line dans log ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout
                # ou d’un remplacement.
                log.write(line)
                # On vidu tampon d’écriture de log vers sa destination ; cela ne remplace pas, à lui
                # seul, une synchronisation durable du fichier.
                log.flush()
                # On transmet cette information à console pour garder une trace de l’étape et de ses
                # valeurs associées.
                console(line.rstrip("\r\n"))
            # On attend la fin du processus avec les paramètres indiqués ; son code de retour sera
            # contrôlé avant de poursuivre.
            return process.wait()
        except BaseException:
            # On demande d’abord un arrêt normal au processus. Si cela ne suffit pas, le bloc
            # suivant attendra puis tentera un arrêt forcé.
            process.terminate()
            # On tente ce bloc et on traite séparément les erreurs prévues : subprocess.TimeoutExpired.
            try:
                # On appelle process.wait sans argument positionnel.
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Le délai d’arrêt normal est dépassé : on tente un arrêt forcé, puis on attend de
                # nouveau sa fin pour ne pas annoncer un arrêt sans le vérifier.
                process.kill()
                # On appelle process.wait sans argument positionnel.
                process.wait()
            # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni en
            # fabriquer une autre.
            raise
        finally:
            # Cette branche traite le cas où le test process.stdout est satisfait.
            if process.stdout:
                # On ferme process.stdout pour libérer la ressource associée après son utilisation.
                process.stdout.close()


def collect_triplet(folder: Path, vineyard: str, kind: str):
    """Cherche uniquement dans le dossier neuf de cette étape, jamais les derniers CSV."""
    # On garde dans stem la valeur renvoyée par safe_stem.
    stem = safe_stem(vineyard)
    # On choisit la valeur de labels selon ce test : kind correspond au texte 'extraction'. Les deux
    # résultats possibles restent définis explicitement ici.
    labels = LABELS if kind == "extraction" else OUTPUT_LABELS
    # On choisit la valeur de prefix selon ce test : kind correspond au texte 'extraction'. Les deux
    # résultats possibles restent définis explicitement ici.
    prefix = f"{stem}_live_nas_" if kind == "extraction" else f"{stem}_excel_nas_live_"
    # On distribue ces valeurs entre timestamps, paths, dans l’ordre de l’affectation. Chaque nom
    # reçoit son propre élément.
    timestamps, paths = set(), {}
    # On parcourt labels ; label désigne l’élément courant à chaque passage dans la boucle.
    for label in labels:
        # On garde dans files une liste matérialisée à partir de folder.glob(f'{prefix}{label}_*.csv').
        files = list(folder.glob(f"{prefix}{label}_*.csv"))
        # On vérifie ce cas avant la suite : len(files) diffère de 1.
        if len(files) != 1:
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                f"{kind} : exactement un CSV {label} attendu, trouvé {len(files)}."
            )
        # On récupère files[0] et on le garde dans path pour la suite.
        path = files[0]
        # On garde dans timestamp la portion de path.name sélectionnée par len(f'{prefix}{label}_'):-4
        # ; les bornes de fin sont exclues.
        timestamp = path.name[len(f"{prefix}{label}_") : -4]
        # On choisit la valeur de pattern selon ce test : kind correspond au texte 'extraction'. Les
        # deux résultats possibles restent définis explicitement ici.
        pattern = (
            r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z"
            if kind == "extraction"
            else r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}Z"
        )
        # Cette branche traite le cas où la condition re.fullmatch(pattern, timestamp) n’est pas
        # remplie.
        if not re.fullmatch(pattern, timestamp):
            # On interrompt cette branche avec ValueError.
            raise ValueError(f"Horodatage de fichier invalide : {path.name}")
        # On appelle datetime.strptime avec timestamp.
        datetime.strptime(
            timestamp,
            "%Y-%m-%dT%H-%M-%SZ" if kind == "extraction" else "%Y-%m-%dT%H-%M-%S-%fZ",
        )
        # On ajoute timestamp à timestamps ; comme il s’agit d’un ensemble, une valeur déjà présente
        # n’est pas comptée deux fois.
        timestamps.add(timestamp)
        # On garde dans paths[label] la représentation textuelle de path.resolve().
        paths[label] = str(path.resolve())
    # On vérifie ce cas avant la suite : len(timestamps) diffère de 1.
    if len(timestamps) != 1:
        # On interrompt cette branche avec ValueError : 'Les trois fichiers ont des horodatages
        # différents.'.
        raise ValueError("Les trois fichiers ont des horodatages différents.")
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return timestamps.pop(), paths


# On contrôle le résultat de l’extraction avant d’autoriser son utilisation dans le rapprochement.
def validate_extraction(paths: dict, vineyard: str, year: int):
    # On garde dans observation_times un ensemble vide, qui servira à repérer les valeurs déjà
    # rencontrées.
    observation_times = set()
    # On distribue ces valeurs entre volumes, observed_errors, dans l’ordre de l’affectation. Chaque
    # nom reçoit son propre élément.
    volumes, observed_errors = {}, {}
    # On parcourt les couples (label, filename) de paths : on garde ensemble la clé et sa valeur au
    # lieu des traiter dans deux listes séparées.
    for label, filename in paths.items():
        # On répartit les valeurs renvoyées par read_csv entre (fields, rows) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        fields, rows = read_csv(Path(filename))
        # On rassemble dans required les 3 éléments explicitement indiqués, en conservant leur
        # structure.
        required = {"Vineyard", "project_year", "checked_at"}
        # Cette branche traite le cas où la condition required.issubset(fields) n’est pas remplie.
        if not required.issubset(fields):
            # On interrompt cette branche avec ValueError.
            raise ValueError(f"Colonnes d’observation manquantes dans {label}.")
        # Cette branche traite le cas où le libellé correspond au texte 'evidence' et la condition
        # rows n’est pas remplie.
        if label == "evidence" and not rows:
            # On interrompt cette branche avec ValueError : 'Extraction sans acquisition :
            # rapprochement non lancé.'.
            raise ValueError("Extraction sans acquisition : rapprochement non lancé.")
        # On parcourt les lignes ; row désigne l’élément courant à chaque passage dans la boucle.
        for row in rows:
            # On vérifie ce cas avant la suite : (row['Vineyard'] or '').strip().casefold() diffère de
            # vineyard.casefold().
            if (row["Vineyard"] or "").strip().casefold() != vineyard.casefold():
                # On interrompt cette branche avec ValueError.
                raise ValueError(f"Mauvais vignoble dans {label}.")
            # On vérifie ce cas avant la suite : str(row['project_year']) diffère de str(year).
            if str(row["project_year"]) != str(year):
                # On interrompt cette branche avec ValueError.
                raise ValueError(f"Mauvaise année dans {label}.")
            # On interprète la date ISO reçue ; les vérifications de fuseau et de cohérence restent
            # nécessaires après cette conversion.
            instant = datetime.fromisoformat(row["checked_at"].replace("Z", "+00:00"))
            # On vérifie ce cas avant la suite : instant.tzinfo vaut None.
            if instant.tzinfo is None:
                # On interrompt cette branche avec ValueError : 'Date checked_at sans fuseau horaire.'.
                raise ValueError("Date checked_at sans fuseau horaire.")
            # On ajoute instant.astimezone(timezone.utc).isoformat() à observation_times ; comme il
            # s’agit d’un ensemble, une valeur déjà présente n’est pas comptée deux fois.
            observation_times.add(instant.astimezone(timezone.utc).isoformat())
        # On garde dans volumes[label] le nombre d’éléments des lignes.
        volumes[label] = len(rows)
        # On construit error_fields comme une liste à partir de field, pour chaque field de fields en
        # ne gardant que les éléments qui passent le filtre.
        error_fields = [field for field in fields if field.endswith("_error")]
        # On garde dans observed_errors[label] la somme des valeurs de (any(((row.get(field) or
        # '').strip() for field in error_fields)) for row….
        observed_errors[label] = sum(
            any((row.get(field) or "").strip() for field in error_fields)
            for row in rows
        )
    # On vérifie ce cas avant la suite : len(observation_times) diffère de 1.
    if len(observation_times) != 1:
        # On interrompt cette branche avec ValueError : 'Les CSV mélangent plusieurs observations
        # NAS.'.
        raise ValueError("Les CSV mélangent plusieurs observations NAS.")
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'volumes' à cette valeur dans cet objet.
        "volumes": volumes,
        # On associe la clé 'rows_with_observation_errors' à cette valeur dans cet objet.
        "rows_with_observation_errors": observed_errors,
        # On renseigne la date du contrôle sous la clé 'checked_at'.
        "checked_at": next(iter(observation_times)),
    }


def check_windows_path_lengths(paths, windows=None):
    """Budget prudent sans supposer que les chemins longs Windows sont activés."""
    # On choisit la valeur de windows selon ce test : windows vaut None. Les deux résultats possibles
    # restent définis explicitement ici.
    windows = os.name == "nt" if windows is None else windows
    # On prévoit le cas où windows est évalué comme faux, par exemple une valeur vide selon son type.
    if not windows:
        # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont pas
        # exécutées.
        return
    # On parcourt paths ; path désigne l’élément courant à chaque passage dans la boucle.
    for path in paths:
        # On vérifie ce cas avant la suite : len(str(path)) est supérieur à 240.
        if len(str(path)) > 240:
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                f"Chemin local trop long pour le budget Windows ({len(str(path))} caractères) : {path}. "
                "Raccourcir le chemin du projet local ; aucun traitement NAS lancé pour cette étape."
            )


# On enchaîne les opérations locales et on conserve leur résultat dans le manifeste de cette
# tentative.
def execute_pipeline(
    root: Path,
    reference: Path,
    vineyards: list[str],
    year: int,
    stop_on_error=False,
    executor=None,
):
    # On retient pour executor la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    executor = executor or run_command
    # On garde dans root le chemin absolu résolu de root, en tenant compte des liens symboliques.
    root = root.resolve()
    # On construit extraction_script en assemblant les morceaux du chemin. L’opérateur / de pathlib
    # ne crée ni dossier ni fichier.
    extraction_script = (
        root / PACKAGE_PATH / "extraction/nas_live_evidence_extractor.py"
    )
    # On construit reconciliation_script en assemblant les morceaux du chemin. L’opérateur / de
    # pathlib ne crée ni dossier ni fichier.
    reconciliation_script = (
        root / PACKAGE_PATH / "reconciliation/excel_nas_live_reconciler.py"
    )
    # On parcourt (extraction_script, reconciliation_script) ; script désigne l’élément courant à
    # chaque passage dans la boucle.
    for script in (extraction_script, reconciliation_script):
        # Cette branche traite le cas où la condition script.is_file() n’est pas remplie.
        if not script.is_file():
            # On interrompt cette branche avec FileNotFoundError.
            raise FileNotFoundError(f"Script absent : {script}")
    # On assemble ces deux éléments pour construire execution_id.
    execution_id = (
        datetime.now(timezone.utc).strftime("%Y%m%d") + "_" + uuid.uuid4().hex[:8]
    )
    # On garde dans state_dir le chemin de données local contrôlé pour ce traitement.
    state_dir = local_data_path(
        root, root / "data/03_normalized/pipeline_runs" / execution_id
    )
    # On appelle check_windows_path_lengths avec [state_dir / 'manifest.json.tmp', state_dir /
    # 'tracking_reference_snapshot.csv'].
    check_windows_path_lengths(
        [state_dir / "manifest.json.tmp", state_dir / "tracking_reference_snapshot.csv"]
    )
    # On crée ce dossier en refusant un emplacement déjà existant ; cela évite de réutiliser
    # silencieusement les sorties d’un ancien essai.
    state_dir.mkdir(parents=True, exist_ok=False)
    # Fige le référentiel CSV local utilisé par les deux étapes de tous les vignobles.
    snapshot = state_dir / "tracking_reference_snapshot.csv"
    # On garde dans contents les octets lus depuis reference, avant toute conversion en texte. Les
    # contrôles de contenu pourront ainsi repartir de cette lecture.
    contents = reference.read_bytes()
    # On écrit les octets préparés dans le fichier ciblé ; ce mode remplace son contenu s’il existe
    # déjà.
    snapshot.write_bytes(contents)
    # On construit manifest_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
    # crée ni dossier ni fichier.
    manifest_path = state_dir / "manifest.json"
    # On regroupe dans manifest ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    manifest = {
        # On renseigne l’identifiant du traitement NAS sous la clé 'pipeline_execution_id'.
        "pipeline_execution_id": execution_id,
        # On renseigne l’état du traitement sous la clé 'status'.
        "status": "running",
        # On renseigne la date de début sous la clé 'started_at'.
        "started_at": utc_now(),
        # On associe la clé 'project_year' à cette valeur dans cet objet.
        "project_year": year,
        # On associe la clé 'reference_source' à cette valeur dans cet objet.
        "reference_source": str(reference.resolve()),
        # On associe la clé 'reference_snapshot' à cette valeur dans cet objet.
        "reference_snapshot": str(snapshot),
        # On renseigne l’empreinte du tableau Excel regroupé sous la clé 'reference_sha256'.
        "reference_sha256": hashlib.sha256(contents).hexdigest(),
        # On associe la clé 'script_sha256' à cette valeur dans cet objet.
        "script_sha256": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (extraction_script, reconciliation_script)
        },
        # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
        "vineyards": [{"vineyard": name, "status": "pending"} for name in vineyards],
    }
    # On appelle write_manifest avec manifest_path.
    write_manifest(manifest_path, manifest)
    # On relève un temps monotone pour mesurer une durée, indépendamment d’un changement de l’heure
    # du poste.
    overall_start = time.monotonic()
    # On tente ce bloc et on traite séparément les erreurs prévues : KeyboardInterrupt, Exception.
    try:
        # On parcourt les domaines sélectionnés dans manifest en gardant aussi sa position dans (index,
        # item) ; le comptage commence à zéro.
        for index, item in enumerate(manifest["vineyards"], start=1):
            # On récupère le domaine concerné dans item et on le garde dans vineyard pour la suite.
            vineyard = item["vineyard"]
            # On garde dans stem la valeur renvoyée par safe_stem.
            stem = safe_stem(vineyard)
            # Dossier court ; le manifeste associe v01, v02... aux noms complets.
            directory_name = f"v{index:02d}"
            # On garde dans evidence_dir le chemin de données local contrôlé pour ce traitement.
            evidence_dir = local_data_path(
                root,
                root
                / "data/03_normalized/nas_live_evidence/runs"
                / execution_id
                / directory_name,
            )
            # On garde dans results_dir le chemin de données local contrôlé pour ce traitement.
            results_dir = local_data_path(
                root,
                root
                / "data/03_normalized/reconciliations/nas_live/runs"
                / execution_id
                / directory_name,
            )
            # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
            # valeur fournie.
            item.update(
                # On fournit l’état du traitement via le paramètre status de cet appel.
                status="running",
                # On fournit l’étape concernée via le paramètre stage de cet appel.
                stage="preparation",
                # On fournit la date de début via le paramètre started_at de cet appel.
                started_at=utc_now(),
                directory_name=directory_name,
                evidence_directory=str(evidence_dir),
                reconciliation_directory=str(results_dir),
            )
            # On démarre un chronomètre monotone pour mesurer une durée : une correction de
            # l’horloge système ne doit pas fausser ce calcul.
            started = time.monotonic()
            # On appelle write_manifest avec manifest_path.
            write_manifest(manifest_path, manifest)
            # On transmet cette information à console pour garder une trace de l’étape et de ses
            # valeurs associées.
            console(f"\n=== {vineyard} : extraction NAS puis rapprochement ===")
            # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
            try:
                # Contrôle préventif des CSV attendus, logs et référence, avant le NAS.
                planned = [
                    state_dir / f"{directory_name}_extraction.log",
                    state_dir / f"{directory_name}_reconciliation.log",
                    snapshot,
                ]
                # On ajoute [evidence_dir / f'{stem}_live_nas_{label}_2026-10-06T08-00-00Z.csv' for
                # label in LAB… à planned et on conserve ce nouvel état pour la suite.
                planned += [
                    evidence_dir / f"{stem}_live_nas_{label}_2026-10-06T08-00-00Z.csv"
                    for label in LABELS
                ]
                # On ajoute [results_dir /
                # f'{stem}_excel_nas_live_{label}_2026-10-06T08-00-00-123456Z.csv' for… à planned et on
                # conserve ce nouvel état pour la suite.
                planned += [
                    results_dir
                    / f"{stem}_excel_nas_live_{label}_2026-10-06T08-00-00-123456Z.csv"
                    for label in OUTPUT_LABELS
                ]
                # On appelle check_windows_path_lengths avec planned.
                check_windows_path_lengths(planned)
                # On prépare le dossier evidence_dir avec les règles de création indiquées ; aucun
                # résultat métier n’est encore produit par cette création.
                evidence_dir.mkdir(parents=True, exist_ok=False)
                # On prépare le dossier results_dir avec les règles de création indiquées ; aucun
                # résultat métier n’est encore produit par cette création.
                results_dir.mkdir(parents=True, exist_ok=False)
                # On utilise ce texte pour item['stage'] ; il ne dépend pas d’une valeur récupérée
                # ailleurs à cet endroit.
                item["stage"] = "extraction"
                # On appelle write_manifest avec manifest_path.
                write_manifest(manifest_path, manifest)
                # On rassemble dans command les 10 éléments explicitement indiqués, en conservant leur
                # structure.
                command = [
                    sys.executable,
                    str(extraction_script),
                    "--vineyard",
                    vineyard,
                    "--year",
                    str(year),
                    "--reference",
                    str(snapshot),
                    "--output-dir",
                    str(evidence_dir),
                ]
                # On construit log en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
                # crée ni dossier ni fichier.
                log = state_dir / f"{directory_name}_extraction.log"
                # On garde dans item['extraction_log'] la représentation textuelle de la trace locale.
                item["extraction_log"] = str(log)
                # On gardes arguments de la commande sous le nom item['extraction_command'] ; cette
                # affectation ne copie pas à elle seule un objet mutable.
                item["extraction_command"] = command
                # On garde dans item['extraction_returncode'] la valeur renvoyée par executor.
                item["extraction_returncode"] = executor(command, root, log)
                # On vérifie ce cas avant la suite : item['extraction_returncode'] diffère de 0.
                if item["extraction_returncode"] != 0:
                    # On interrompt cette branche avec RuntimeError.
                    raise RuntimeError(
                        f"Extraction terminée avec le code {item['extraction_returncode']}."
                    )
                # On répartit les valeurs renvoyées par collect_triplet entre (extraction_id,
                # evidence_paths) ; leur ordre doit correspondre à celui prévu par cet appel.
                extraction_id, evidence_paths = collect_triplet(
                    evidence_dir, vineyard, "extraction"
                )
                # On garde extraction_id sous le nom item['extraction_run_id'] ; cette affectation ne
                # copie pas à elle seule un objet mutable.
                item["extraction_run_id"] = extraction_id
                # On garde evidence_paths sous le nom item['evidence_outputs'] ; cette affectation ne
                # copie pas à elle seule un objet mutable.
                item["evidence_outputs"] = evidence_paths
                # On garde dans item['observations'] la valeur renvoyée par validate_extraction.
                item["observations"] = validate_extraction(
                    evidence_paths, vineyard, year
                )
                # On utilise ce texte pour item['stage'] ; il ne dépend pas d’une valeur récupérée
                # ailleurs à cet endroit.
                item["stage"] = "reconciliation"
                # On appelle write_manifest avec manifest_path.
                write_manifest(manifest_path, manifest)
                # On rassemble dans command les 14 éléments explicitement indiqués, en conservant leur
                # structure.
                command = [
                    sys.executable,
                    str(reconciliation_script),
                    "--vineyard",
                    vineyard,
                    "--reference",
                    str(snapshot),
                    "--evidence",
                    evidence_paths["evidence"],
                    "--associations",
                    evidence_paths["associations"],
                    "--passages",
                    evidence_paths["passages"],
                    "--output-dir",
                    str(results_dir),
                ]
                # On assemble les morceaux du chemin log avec l’opérateur / de pathlib ; aucun fichier
                # n’est créé par cette construction.
                log = state_dir / f"{directory_name}_reconciliation.log"
                # On garde dans item['reconciliation_log'] la représentation textuelle de la trace
                # locale.
                item["reconciliation_log"] = str(log)
                # On gardes arguments de la commande sous le nom item['reconciliation_command'] ;
                # cette affectation ne copie pas à elle seule un objet mutable.
                item["reconciliation_command"] = command
                # On garde dans item['reconciliation_returncode'] la valeur renvoyée par executor.
                item["reconciliation_returncode"] = executor(command, root, log)
                # On vérifie ce cas avant la suite : item['reconciliation_returncode'] diffère de 0.
                if item["reconciliation_returncode"] != 0:
                    # On interrompt cette branche avec RuntimeError.
                    raise RuntimeError(
                        f"Rapprochement terminé avec le code {item['reconciliation_returncode']}."
                    )
                # On répartit les valeurs renvoyées par collect_triplet entre (result_id, outputs) ;
                # leur ordre doit correspondre à celui prévu par cet appel.
                result_id, outputs = collect_triplet(
                    results_dir, vineyard, "reconciliation"
                )
                # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                item.update(
                    # On fournit l’état du traitement via le paramètre status de cet appel.
                    status="success",
                    reconciliation_run_id=result_id,
                    reconciliation_outputs=outputs,
                )
            except Exception as error:
                # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                item.update(status="failed", error=f"{type(error).__name__}: {error}")
                # On transmet cette information à console pour garder une trace de l’étape et de ses
                # valeurs associées.
                console(f"ECHEC {vineyard} / {item['stage']} : {error}")
            finally:
                # On garde dans item['finished_at'] la date courante en UTC sous la forme préparée par
                # ce module.
                item["finished_at"] = utc_now()
                # On garde dans item['duration_seconds'] la valeur arrondie de time.monotonic() -
                # started.
                item["duration_seconds"] = round(time.monotonic() - started, 3)
                # On appelle write_manifest avec manifest_path.
                write_manifest(manifest_path, manifest)
            # Cette branche traite le cas où l’état du traitement dans item correspond au texte
            # 'failed' et stop_on_error est évalué comme vrai.
            if item["status"] == "failed" and stop_on_error:
                # On quitte cette boucle dès que ce cas est rencontré ; on ne parcourt pas les éléments
                # suivants.
                break
        # On parcourt les domaines sélectionnés dans manifest ; item désigne l’élément courant à chaque
        # passage dans la boucle.
        for item in manifest["vineyards"]:
            # On vérifie ce cas avant la suite : l’état du traitement dans item correspond au texte
            # 'pending'.
            if item["status"] == "pending":
                # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                item.update(status="skipped", reason="Arrêt après un échec précédent.")
        # On renseigne ici l’état annoncé pour ce résultat dans manifest ; ce champ restera associé
        # au lot ou à l’élément en cours.
        manifest["status"] = (
            "success"
            if all(item["status"] == "success" for item in manifest["vineyards"])
            else "failed"
        )
    except KeyboardInterrupt:
        # On utilise ce texte pour manifest['status'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        manifest["status"] = "interrupted"
        # On parcourt les domaines sélectionnés dans manifest ; item désigne l’élément courant à chaque
        # passage dans la boucle.
        for item in manifest["vineyards"]:
            # On vérifie ce cas avant la suite : l’état du traitement dans item correspond au texte
            # 'running'.
            if item["status"] == "running":
                # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                item.update(status="interrupted", finished_at=utc_now())
            # On vérifie ce cas avant la suite : l’état du traitement dans item correspond au texte
            # 'pending'.
            elif item["status"] == "pending":
                # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                item.update(status="skipped", reason="Interruption utilisateur.")
    except Exception as error:
        # On complète manifest avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        # On parcourt les domaines sélectionnés dans manifest ; item désigne l’élément courant à chaque
        # passage dans la boucle.
        for item in manifest["vineyards"]:
            # On vérifie ce cas avant la suite : l’état du traitement dans item correspond au texte
            # 'running'.
            if item["status"] == "running":
                # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                item.update(status="failed", error=str(error), finished_at=utc_now())
            # On vérifie ce cas avant la suite : l’état du traitement dans item correspond au texte
            # 'pending'.
            elif item["status"] == "pending":
                # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                item.update(
                    # On fournit l’état du traitement via le paramètre status de cet appel.
                    status="skipped", reason="Erreur de préparation d’une étape."
                )
    finally:
        # On complète manifest avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        manifest.update(
            # On fournit la date de fin via le paramètre finished_at de cet appel.
            finished_at=utc_now(),
            # On fournit la durée en secondes via le paramètre duration_seconds de cet appel.
            duration_seconds=round(time.monotonic() - overall_start, 3),
        )
        # On appelle write_manifest avec manifest_path.
        write_manifest(manifest_path, manifest)
    # On transmet cette information à console pour garder une trace de l’étape et de ses valeurs
    # associées.
    console("\n=== BILAN DU PILOTE ===")
    # On parcourt les domaines sélectionnés dans manifest ; item désigne l’élément courant à chaque
    # passage dans la boucle.
    for item in manifest["vineyards"]:
        # On transmet cette information à console pour garder une trace de l’étape et de ses valeurs
        # associées.
        console(f"  {item['vineyard']} : {item['status']}")
    # On transmet cette information à console pour garder une trace de l’étape et de ses valeurs
    # associées.
    console(f"  Manifeste : {manifest_path}")
    # On transmet cette information à console pour garder une trace de l’étape et de ses valeurs
    # associées.
    console("  Succès technique ne signifie pas que tous les livrables sont conformes.")
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return (
        0
        if manifest["status"] == "success"
        else 130
        if manifest["status"] == "interrupted"
        else 1
    ), manifest_path


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On déclare des options incompatibles entre elles : le parseur rejettera leur emploi simultané
    # avant le traitement.
    group = parser.add_mutually_exclusive_group(required=True)
    # Option --vineyard : Répétable pour plusieurs vignobles. Sa déclaration ne déclenche pas
    # l’action.
    group.add_argument(
        "--vineyard", action="append", help="Répétable pour plusieurs vignobles."
    )
    # Option --all-vineyards : Tous les vignobles de l’année dans le référentiel Excel normalisé. Sa
    # déclaration ne déclenche pas l’action.
    group.add_argument(
        "--all-vineyards",
        action="store_true",
        help="Tous les vignobles de l’année dans le référentiel Excel normalisé.",
    )
    # On appelle parser.add_argument avec '--year'.
    parser.add_argument("--year", type=int, default=2026)
    # On appelle parser.add_argument avec '--reference'.
    parser.add_argument("--reference", type=Path, default=REFERENCE_PATH)
    # Option --stop-on-error : Sinon, poursuit les autres vignobles en signalant les échecs. Sa
    # déclaration ne déclenche pas l’action.
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Sinon, poursuit les autres vignobles en signalant les échecs.",
    )
    # On récupère le périmètre, la saison et les fichiers à croiser ; leur validation précède les
    # appels à l’extracteur et au rapprochement.
    args = parser.parse_args(argv)
    # On tente ce bloc et on traite séparément les erreurs prévues : (OSError, ValueError).
    try:
        # On garde dans root le chemin absolu résolu de PROJECT_ROOT, en tenant compte des liens
        # symboliques.
        root = PROJECT_ROOT.resolve()
        # On choisit la valeur de reference selon ce test : args.reference est absolu. Les deux
        # résultats possibles restent définis explicitement ici.
        reference = (
            args.reference if args.reference.is_absolute() else root / args.reference
        )
        # On garde dans reference le chemin de données local contrôlé pour ce traitement.
        reference = local_data_path(root, reference)
        # On garde dans vineyards la valeur renvoyée par select_vineyards.
        vineyards = select_vineyards(
            reference, args.vineyard or [], args.all_vineyards, args.year
        )
        # On répartit les valeurs renvoyées par execute_pipeline entre (code, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        code, _ = execute_pipeline(
            root, reference, vineyards, args.year, args.stop_on_error
        )
        # On remet le code de retour à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return code
    except (OSError, ValueError) as error:
        # On transmet cette information à console pour garder une trace de l’étape et de ses valeurs
        # associées.
        console(f"ERREUR DE PREPARATION : {error}")
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
