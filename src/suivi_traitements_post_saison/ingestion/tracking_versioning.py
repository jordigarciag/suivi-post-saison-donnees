# Lecture du fichier — Archivage, versionnement et publication des données Excel de suivi.
# On ajoute des pages au carnet plutôt que réécrire les anciennes. Une exécution peut vérifier les
# mêmes données sans créer une nouvelle version ; la trace d’exécution et la version ont des rôles
# différents.
#

"""Versions locales des references Excel, sans consultation du NAS.

Les CSV courants restent des exports compatibles : les versions immuables
et leurs manifestes constituent la provenance. Une publication globale
assemble les versions retenues, sans redater les vignobles inchanges.

Un verrou empeche deux ingestions simultanees. Un journal de publication
permet de detecter une interruption brutale : elle bloque le lancement
suivant au lieu de pretendre que l'etat est coherent.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe importlib.metadata. Ce module sera utilisé par les opérations de ce fichier.
import importlib.metadata
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe platform. Ce module sera utilisé par les opérations de ce fichier.
import platform
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe uuid. Ce module sera utilisé par les opérations de ce fichier.
import uuid
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd

# On rend disponibles reader depuis None, pour les appels de ce fichier.
from . import excel_reader as reader

# On fixe FORMAT_VERSION à 1 pour cette étape.
FORMAT_VERSION = 1
# On rassemble dans GLOBAL_COLUMNS les 3 éléments explicitement indiqués, en conservant leur structure.
GLOBAL_COLUMNS = [
    "duplicate_row_key_global",
    "has_multiple_rows_same_acquisition_global",
    "has_mixed_side_granularity_global",
]


# On produit l’instant courant en UTC avec son fuseau pour éviter les heures locales ambiguës.
def utc_now():
    # On fournit à l’appelant la représentation ISO de datetime.now(timezone.utc).
    return datetime.now(timezone.utc).isoformat()


# On prépare un identifiant distinct pour relier les objets de cette tentative.
def new_id():
    # Repertoires courts pour reduire les risques de chemins longs Windows.
    return datetime.now(timezone.utc).strftime("%Y%m%d") + "_" + uuid.uuid4().hex[:8]


# On calcule une empreinte du contenu pour pouvoir détecter une différence.
def digest(data: bytes):
    # On fournit à l’appelant l’empreinte de hashlib.sha256(data) écrite en caractères hexadécimaux.
    return hashlib.sha256(data).hexdigest()


# On prépare les octets JSON avec les options de sérialisation prévues pour les empreintes et les
# fichiers.
def json_bytes(value):
    # On fournit à l’appelant les octets de json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    # obtenus avec l’encodage indiqué.
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


# On prépare le contenu CSV avant de l’archiver ou de calculer son empreinte.
def csv_bytes(frame):
    # On fournit à l’appelant les octets de frame.to_csv(index=False) obtenus avec l’encodage indiqué.
    return frame.to_csv(index=False).encode("utf-8-sig")


# On prépare un fichier temporaire puis on remplace sa destination selon les contrôles prévus.
def atomic_write(path: Path, data: bytes):
    """Remplacement d'un fichier seul, pas transaction multi-fichiers."""
    # On prépare le dossier local nécessaire à cette sortie ; créer le dossier ne produit pas encore
    # le fichier qu’il contiendra.
    path.parent.mkdir(parents=True, exist_ok=True)
    # On garde dans temporary la valeur renvoyée par path.with_name.
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex[:8] + ".tmp")
    # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
    try:
        # On écrit les octets préparés dans le fichier ciblé ; ce mode remplace son contenu s’il
        # existe déjà.
        temporary.write_bytes(data)
        # On appelle os.replace avec temporary.
        os.replace(temporary, path)
    finally:
        # Cette branche traite le cas où temporary existe.
        if temporary.exists():
            # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
            # d’autres fichiers.
            temporary.unlink()


# On vérifie le chemin avant de l’utiliser pour une lecture ou une écriture de ce module.
def checked_path(root: Path, relative: str):
    # On garde dans path le chemin absolu résolu de root / relative, en tenant compte des liens
    # symboliques.
    path = (root / relative).resolve()
    # Une archive Excel de ce projet doit rester sous data, même après résolution de son chemin.
    if not path.is_relative_to((root / "data").resolve()):
        # On interrompt cette branche avec ValueError.
        raise ValueError("Artefact hors du dossier data local : " + relative)
    # On remet le chemin de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return path


# On contrôle les contraintes de chemin pertinentes pour l’environnement Windows prévu.
def check_windows_path(path: Path):
    # Cette branche traite le cas où os.name correspond au texte 'nt' et len(str(path.resolve())) est
    # supérieur à 240.
    if os.name == "nt" and len(str(path.resolve())) > 240:
        # On interrompt cette branche avec ValueError.
        raise ValueError(
            "Chemin trop long pour notre budget Windows (240) : " + str(path)
        )


# On prépare une clé de rangement contrôlée à partir du nom fourni.
def safe_vineyard(name):
    # Evite collisions, noms Windows reserves et caracteres de chemin.
    return "v_" + digest(name.casefold().encode("utf-8"))[:10]


# On repère les sources attendues en contrôlant leurs chemins et leur sélection.
def discover(input_dir: Path, selection=None):
    # On garde dans files les éléments triés de (p for p in input_dir.glob('*.xlsx') if not
    # p.name.startswith('~$')) dans une nouvelle liste.
    files = sorted(p for p in input_dir.glob("*.xlsx") if not p.name.startswith("~$"))
    # On prévoit le cas où files est évalué comme faux, par exemple une valeur vide selon son type.
    if not files:
        # On interrompt cette branche avec ValueError.
        raise ValueError("Aucun Excel .xlsx disponible dans " + str(input_dir))
    # On crée le dictionnaire vide result pour y ranger ensuite les éléments par clé.
    result = {}
    # On parcourt files ; path désigne l’élément courant à chaque passage dans la boucle.
    for path in files:
        # On garde dans name la valeur renvoyée par reader.extract_vineyard_from_filename.
        name = reader.extract_vineyard_from_filename(path)
        # On prévoit le cas où name est évalué comme faux, par exemple une valeur vide selon son type.
        if not name:
            # On vérifie ce cas avant la suite : selection vaut None.
            if selection is None:
                # On interrompt cette branche avec ValueError.
                raise ValueError("Nom de fichier non reconnu : " + path.name)
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
        # enregistré dans les données sources.
        key = name.casefold()
        # Cette branche traite le cas où selection est renseigné (différent de None) et la clé de
        # l’élément ne figure pas dans selection.
        if selection is not None and key not in selection:
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On vérifie ce cas avant la suite : la clé de l’élément appartient au résultat de cette
        # opération.
        if key in result:
            # On interrompt cette branche avec ValueError.
            raise ValueError("Plusieurs Excel candidats pour le vignoble " + name)
        # On rassemble dans result[key] les 2 éléments explicitement indiqués, en conservant leur
        # structure.
        result[key] = (name, path)
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On prépare les informations permettant de rattacher le lot au code de traitement utilisé.
def code_identity(config_bytes):
    # On crée le dictionnaire vide packages pour y ranger ensuite les éléments par clé.
    packages = {}
    # On parcourt ('pandas', 'PyYAML', 'openpyxl') ; name désigne l’élément courant à chaque passage
    # dans la boucle.
    for name in ("pandas", "PyYAML", "openpyxl"):
        # On garde dans packages[name] la valeur renvoyée par importlib.metadata.version.
        packages[name] = importlib.metadata.version(name)
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'config_sha256' à cette valeur dans cet objet.
        "config_sha256": digest(config_bytes),
        # On associe la clé 'reader_sha256' à cette valeur dans cet objet.
        "reader_sha256": digest(Path(reader.__file__).read_bytes()),
        # On associe la clé 'versioning_sha256' à cette valeur dans cet objet.
        "versioning_sha256": digest(Path(__file__).read_bytes()),
        # On associe la clé 'python_version' à cette valeur dans cet objet.
        "python_version": platform.python_version(),
        # On associe la clé 'packages' à cette valeur dans cet objet.
        "packages": packages,
    }


# On contrôle les fichiers et empreintes associés à une version existante.
def verify_version(root, entry):
    # On garde dans path la valeur renvoyée par checked_path.
    path = checked_path(root, entry["manifest"])
    # On vérifie ce cas avant la suite : digest(path.read_bytes()) diffère de l’empreinte du manifeste
    # dans entry.
    if digest(path.read_bytes()) != entry["manifest_sha256"]:
        # On interrompt cette branche avec ValueError.
        raise ValueError("Manifeste de version modifie : " + entry["manifest"])
    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    manifest = json.loads(path.read_text(encoding="utf-8"))
    # On parcourt manifest['artifacts'].values() ; artifact désigne l’élément courant à chaque passage
    # dans la boucle.
    for artifact in manifest["artifacts"].values():
        # On garde dans p la valeur renvoyée par checked_path.
        p = checked_path(root, artifact["path"])
        # On vérifie ce cas avant la suite : digest(p.read_bytes()) diffère de artifact['sha256'].
        if digest(p.read_bytes()) != artifact["sha256"]:
            # On interrompt cette branche avec ValueError.
            raise ValueError("Artefact de version modifie : " + artifact["path"])
    # Cette branche traite le cas où l’identifiant de version dans manifest diffère de l’identifiant de
    # version dans entry ou le domaine concerné dans manifest diffère du domaine concerné dans
    # entry.
    if (
        manifest["version_id"] != entry["version_id"]
        # Ce cas est aussi retenu si le domaine concerné dans manifest diffère du domaine concerné
        # dans entry.
        or manifest["vineyard"] != entry["vineyard"]
    ):
        # On interrompt cette branche avec ValueError : 'Registre et manifeste incompatibles.'.
        raise ValueError("Registre et manifeste incompatibles.")
    # On remet le manifeste du lot à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return manifest


# On reconstruit le tableau à partir de l’entrée de version contrôlée.
def frame_from_entry(root, entry):
    # On fournit à l’appelant la valeur renvoyée par pd.read_csv.
    return pd.read_csv(
        checked_path(root, entry["normalized_path"]),
        # On impose les types lus ou construits pour éviter une interprétation automatique non
        # souhaitée.
        dtype="string",
        # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
        # décodé selon un réglage implicite du poste.
        encoding="utf-8-sig",
        low_memory=False,
    )


# On conserve les fichiers et métadonnées d’une version plutôt que modifier une version précédente.
def store_version(root, name, source_path, settings, config_bytes, identity):
    # On garde dans version_id la valeur renvoyée par new_id.
    version_id = new_id()
    # On construit directory en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    directory = (
        root
        / "data/03_normalized/suivi_acquisitions_normalises/versions"
        / safe_vineyard(name)
        / version_id
    )
    # On construit archive en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    archive = (
        root
        / "data/02_raw_archive/suivi_acquisitions"
        / safe_vineyard(name)
        / version_id
    )
    # On rassemble dans planned les 7 éléments explicitement indiqués, en conservant leur structure.
    planned = [
        archive / source_path.name,
        directory / "normalized.csv",
        directory / "rejected.csv",
        directory / "manifest.json",
        directory / "tracking_files.yml",
        directory / "excel_reader.py",
        directory / "tracking_versioning.py",
    ]
    # On parcourt planned ; path désigne l’élément courant à chaque passage dans la boucle.
    for path in planned:
        # On appelle checked_path avec root.
        checked_path(root, path.relative_to(root).as_posix())
        # On appelle check_windows_path avec path.
        check_windows_path(path)
    # On garde dans source_stat les métadonnées de source_path, distinctes du contenu du fichier.
    source_stat = source_path.stat()
    # On garde dans source_bytes les octets lus depuis source_path, avant toute conversion en texte.
    # Les contrôles de contenu pourront ainsi repartir de cette lecture.
    source_bytes = source_path.read_bytes()
    # On garde dans after les métadonnées de source_path, distinctes du contenu du fichier.
    after = source_path.stat()
    # On vérifie ce cas avant la suite : (source_stat.st_size, source_stat.st_mtime_ns) diffère de
    # (after.st_size, after.st_mtime_ns).
    if (source_stat.st_size, source_stat.st_mtime_ns) != (
        after.st_size,
        after.st_mtime_ns,
    ):
        # On interrompt cette branche avec ValueError.
        raise ValueError("Excel modifie pendant la lecture : " + source_path.name)
    # On crée ce dossier en refusant un emplacement déjà existant ; cela évite de réutiliser
    # silencieusement les sorties d’un ancien essai.
    archive.mkdir(parents=True, exist_ok=False)
    # On prépare le dossier directory avec les règles de création indiquées ; aucun résultat métier
    # n’est encore produit par cette création.
    directory.mkdir(parents=True, exist_ok=False)
    # On calcule ce quotient pour construire copied_source.
    copied_source = archive / source_path.name
    # On écrit les octets préparés dans le fichier ciblé ; ce mode remplace son contenu s’il existe
    # déjà.
    copied_source.write_bytes(source_bytes)
    # La normalisation lit cette copie exacte, pas une source mutable.
    try:
        # On répartit les valeurs renvoyées par reader.process_excel_file entre (frame, rejected,
        # actual) ; leur ordre doit correspondre à celui prévu par cet appel.
        frame, rejected, actual = reader.process_excel_file(copied_source, settings)
        # On vérifie ce cas avant la suite : actual.casefold() diffère de name.casefold().
        if actual.casefold() != name.casefold():
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                "Vignoble du contenu incompatible avec la selection : "
                + source_path.name
            )
        # On traite à part le tableau frame lorsqu’il est vide.
        if frame.empty:
            # On interrompt cette branche avec ValueError.
            raise ValueError("Aucune ligne normalisee utilisable pour " + name)
    except Exception as error:
        # On regroupe dans failure ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        failure = {
            # On renseigne l’identifiant de version sous la clé 'version_id'.
            "version_id": version_id,
            # On renseigne le domaine concerné sous la clé 'vineyard'.
            "vineyard": name,
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "failed",
            # On associe la clé 'source_path' à cette valeur dans cet objet.
            "source_path": copied_source.relative_to(root).as_posix(),
            # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
            "source_sha256": digest(source_bytes),
            # On renseigne les éléments d’identité du lot sous la clé 'identity'.
            "identity": identity,
            # On associe la clé 'failed_at' à cette valeur dans cet objet.
            "failed_at": utc_now(),
            # On associe la clé 'error' à cette valeur dans cet objet.
            "error": str(error),
        }
        # On écrit le contenu préparé dans directory / 'failure.json' ; cette opération remplace le
        # contenu du fichier s’il existe déjà.
        (directory / "failure.json").write_bytes(json_bytes(failure))
        # On interrompt cette branche avec ValueError. La cause initiale reste attachée grâce à from.
        raise ValueError(
            str(error)
            + " | trace : "
            + (directory / "failure.json").relative_to(root).as_posix()
        ) from error
    # On gardu résultat obtenu sous le nom name ; cette affectation ne copie pas à elle seule un
    # objet mutable.
    name = actual
    # On garde dans ingested_at la représentation textuelle de frame['ingested_at'].iloc[0].
    ingested_at = str(frame["ingested_at"].iloc[0])
    # On garde l’identifiant de version sous le nom frame['excel_reference_version_id'] ; cette
    # affectation ne copie pas à elle seule un objet mutable.
    frame["excel_reference_version_id"] = version_id
    # On garde dans frame['source_sha256'] l’empreinte calculée par le helper de ce module.
    frame["source_sha256"] = digest(source_bytes)
    # On garde l’identifiant de version sous le nom rejected['excel_reference_version_id'] ; cette
    # affectation ne copie pas à elle seule un objet mutable.
    rejected["excel_reference_version_id"] = version_id
    # On garde dans rejected['source_sha256'] l’empreinte calculée par le helper de ce module.
    rejected["source_sha256"] = digest(source_bytes)
    # On crée le dictionnaire vide artifacts pour y ranger ensuite les éléments par clé.
    artifacts = {}
    # On regroupe dans contents ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    contents = {
        # On renseigne la source sous la clé 'source'.
        "source": (copied_source, source_bytes),
        # On associe la clé 'normalized' à cette valeur dans cet objet.
        "normalized": (directory / "normalized.csv", csv_bytes(frame)),
        # On associe la clé 'rejected' à cette valeur dans cet objet.
        "rejected": (directory / "rejected.csv", csv_bytes(rejected)),
        # On renseigne les réglages sous la clé 'config'.
        "config": (directory / "tracking_files.yml", config_bytes),
        # On associe la clé 'reader' à cette valeur dans cet objet.
        "reader": (directory / "excel_reader.py", Path(reader.__file__).read_bytes()),
        # On associe la clé 'versioning' à cette valeur dans cet objet.
        "versioning": (
            directory / "tracking_versioning.py",
            Path(__file__).read_bytes(),
        ),
    }
    # On parcourt les couples (label, (path, data)) de contents : on garde ensemble la clé et sa
    # valeur au lieu des traiter dans deux listes séparées.
    for label, (path, data) in contents.items():
        # On vérifie ce cas avant la suite : le libellé diffère du texte 'source'.
        if label != "source":
            # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier
            # s’il existe déjà.
            path.write_bytes(data)
        # On regroupe dans artifacts[label] ces champs nommés ; on pourra les retrouver par leur clé
        # plutôt que par leur position.
        artifacts[label] = {
            # On renseigne le chemin de travail sous la clé 'path'.
            "path": path.relative_to(root).as_posix(),
            # On conserve l’empreinte attendue pour retrouver la même version du contenu.
            "sha256": digest(data),
        }
    # On regroupe dans manifest ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    manifest = {
        # On marque la version du format pour ne pas interpréter un autre contrat de fichier par
        # erreur.
        "format_version": FORMAT_VERSION,
        # On renseigne l’identifiant de version sous la clé 'version_id'.
        "version_id": version_id,
        # On renseigne le domaine concerné sous la clé 'vineyard'.
        "vineyard": name,
        # On renseigne la date d’ingestion sous la clé 'ingested_at'.
        "ingested_at": ingested_at,
        # On associe la clé 'source_file' à cette valeur dans cet objet.
        "source_file": source_path.name,
        # On renseigne la date de modification de la source sous la clé 'source_modified_at'.
        "source_modified_at": datetime.fromtimestamp(
            source_stat.st_mtime, timezone.utc
        ).isoformat(),
        # On associe la clé 'source_size' à cette valeur dans cet objet.
        "source_size": len(source_bytes),
        # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
        "source_sha256": digest(source_bytes),
        # On renseigne les éléments d’identité du lot sous la clé 'identity'.
        "identity": identity,
        # On renseigne le nombre de lignes normalisées sous la clé 'normalized_rows'.
        "normalized_rows": len(frame),
        # On renseigne le nombre de lignes rejetées sous la clé 'rejected_rows'.
        "rejected_rows": len(rejected),
        # On renseigne le nombre d’acquisitions distinctes sous la clé 'logical_acquisitions'.
        "logical_acquisitions": int(frame["Acquisition_ID_normalise"].nunique()),
        # On associe la clé 'artifacts' à cette valeur dans cet objet.
        "artifacts": artifacts,
    }
    # On construit manifest_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
    # crée ni dossier ni fichier.
    manifest_path = directory / "manifest.json"
    # On écrit le contenu préparé dans manifest_path ; cette opération remplace le contenu du fichier
    # s’il existe déjà.
    manifest_path.write_bytes(json_bytes(manifest))
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On renseigne le domaine concerné sous la clé 'vineyard'.
        "vineyard": name,
        # On renseigne l’identifiant de version sous la clé 'version_id'.
        "version_id": version_id,
        # On renseigne la date d’ingestion sous la clé 'ingested_at'.
        "ingested_at": ingested_at,
        # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
        "source_sha256": manifest["source_sha256"],
        # On renseigne les éléments d’identité du lot sous la clé 'identity'.
        "identity": identity,
        # On renseigne le nom du fichier source sous la clé 'source_filename'.
        "source_filename": source_path.name,
        # On renseigne le manifeste du lot sous la clé 'manifest'.
        "manifest": manifest_path.relative_to(root).as_posix(),
        # On renseigne l’empreinte du manifeste sous la clé 'manifest_sha256'.
        "manifest_sha256": digest(manifest_path.read_bytes()),
        # On renseigne le chemin du tableau normalisé sous la clé 'normalized_path'.
        "normalized_path": artifacts["normalized"]["path"],
        # On renseigne le nombre de lignes normalisées sous la clé 'normalized_rows'.
        "normalized_rows": len(frame),
        # On renseigne le nombre d’acquisitions distinctes sous la clé 'logical_acquisitions'.
        "logical_acquisitions": manifest["logical_acquisitions"],
        # On renseigne le nombre de lignes rejetées sous la clé 'rejected_rows'.
        "rejected_rows": len(rejected),
    }


# On publie les liens vers les versions retenues en conservant leur traçabilité.
def publish(root, entries, execution_id, state_dir):
    """Publie un assemblage ; conserve un journal et restaure sur erreur normale.

    En cas de crash brutal pendant plusieurs remplacements, le journal reste
    present et empeche une nouvelle ingestion jusqu'au diagnostic/recovery.
    Ne pas faire tourner le pilote consommateur pendant cette publication.
    """
    # On construit output en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    output = root / "data/03_normalized/suivi_acquisitions_normalises"
    # On construit frames comme une liste à partir de frame_from_entry(root, entries[k]), pour chaque k
    # de sorted(entries).
    frames = [frame_from_entry(root, entries[k]) for k in sorted(entries)]
    # On garde dans combined la valeur renvoyée par reader.add_global_identifier_flags.
    combined = reader.add_global_identifier_flags(pd.concat(frames, ignore_index=True))
    # On garde dans publication_id la valeur renvoyée par new_id.
    publication_id = new_id()
    # On construit directory en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    directory = output / "publications" / publication_id
    # On crée ce dossier en refusant un emplacement déjà existant ; cela évite de réutiliser
    # silencieusement les sorties d’un ancien essai.
    directory.mkdir(parents=True, exist_ok=False)
    # On garde dans global_data les octets CSV produits à partir des lignes de cet exemple.
    global_data = csv_bytes(combined)
    # On regroupe dans paths ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    paths = {"reference": (directory / "reference.csv", global_data)}
    # On parcourt les couples (k, entry) de entries : on garde ensemble la clé et sa valeur au lieu
    # des traiter dans deux listes séparées.
    for k, entry in entries.items():
        # On rassemble dans paths[k] les 2 éléments explicitement indiqués, en conservant leur
        # structure.
        paths[k] = (
            directory / (safe_vineyard(entry["vineyard"]) + ".csv"),
            checked_path(root, entry["normalized_path"]).read_bytes(),
        )
    # On parcourt paths.values() ; (path, data) désigne l’élément courant à chaque passage dans la
    # boucle.
    for path, data in paths.values():
        # On appelle check_windows_path avec path.
        check_windows_path(path)
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_bytes(data)
    # On regroupe dans publication ces champs nommés ; on pourra les retrouver par leur clé plutôt que
    # par leur position.
    publication = {
        # On marque la version du format pour ne pas interpréter un autre contrat de fichier par
        # erreur.
        "format_version": FORMAT_VERSION,
        # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
        "publication_id": publication_id,
        # On associe la clé 'ingestion_execution_id' à cette valeur dans cet objet.
        "ingestion_execution_id": execution_id,
        # On renseigne la date de publication sous la clé 'published_at'.
        "published_at": utc_now(),
        # On renseigne le repère utilisé pour les données Excel sous la clé 'reference'.
        "reference": {
            # On renseigne le chemin de travail sous la clé 'path'.
            "path": paths["reference"][0].relative_to(root).as_posix(),
            # On conserve l’empreinte attendue pour retrouver la même version du contenu.
            "sha256": digest(global_data),
            # On renseigne les lignes sous la clé 'rows'.
            "rows": len(combined),
        },
        # On associe la clé 'versions' à cette valeur dans cet objet.
        "versions": entries,
    }
    # On écrit les octets préparés dans le fichier ciblé ; ce mode remplace son contenu s’il existe
    # déjà.
    (directory / "manifest.json").write_bytes(json_bytes(publication))
    # On garde dans registry un nouveau dictionnaire construit avec les valeurs indiquées (la copie
    # reste superficielle).
    registry = dict(publication)
    # On garde dans registry['publication_manifest'] l’écriture de (directory /
    # 'manifest.json').relative_to(root) avec des / comme séparateurs.
    registry["publication_manifest"] = (
        (directory / "manifest.json").relative_to(root).as_posix()
    )
    # On garde dans registry['compatibility_export_sha256'] l’empreinte calculée par le helper de ce
    # module.
    registry["compatibility_export_sha256"] = digest(global_data)
    # Les aliases ne sont pas l'historique. Les snapshots ci-dessus le sont.
    targets = [(output / "toutes_acquisitions_normalisees.csv", global_data)]
    # On ajoute [(output / (entry['vineyard'] + '_nettoye.csv'), paths[k][1]) for k, entry in entrie… à
    # targets et on conserve ce nouvel état pour la suite.
    targets += [
        (output / (entry["vineyard"] + "_nettoye.csv"), paths[k][1])
        for k, entry in entries.items()
    ]
    # On ajoute (state_dir / 'current.json', json_bytes(registry)) à la fin de targets ; les éléments
    # précédents restent conservés.
    targets.append((state_dir / "current.json", json_bytes(registry)))
    # Ne pas reecrire les aliases des vignobles inchanges (y compris leur mtime).
    targets = [
        (path, data)
        for path, data in targets
        if not path.exists() or path.read_bytes() != data
    ]
    # On construit backup en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    backup = state_dir / "transactions" / execution_id
    # On prépare le dossier backup avec les règles de création indiquées ; aucun résultat métier n’est
    # encore produit par cette création.
    backup.mkdir(parents=True, exist_ok=False)
    # On prépare originals comme liste vide ; on la remplira au fil des opérations suivantes.
    originals = []
    # On parcourt targets en gardant aussi sa position dans (index, (path, _)) ; le comptage commence à
    # zéro.
    for index, (path, _) in enumerate(targets):
        # On appelle check_windows_path avec path.
        check_windows_path(path)
        # On choisit la valeur de data selon ce test : le chemin de travail existe. Les deux résultats
        # possibles restent définis explicitement ici.
        data = path.read_bytes() if path.exists() else None
        # On construit backup_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
        # crée ni dossier ni fichier.
        backup_path = backup / f"{index:02}.bak"
        # On vérifie ce cas avant la suite : les données en mémoire est renseigné (différent de None).
        if data is not None:
            # On écrit le contenu préparé dans backup_path ; cette opération remplace le contenu du
            # fichier s’il existe déjà.
            backup_path.write_bytes(data)
        # On ajoute {'path': path.relative_to(root).as_posix(), 'backup':
        # str(backup_path.relative_to(root).a… à la fin de originals ; les éléments précédents restent
        # conservés.
        originals.append(
            {
                # On renseigne le chemin de travail sous la clé 'path'.
                "path": path.relative_to(root).as_posix(),
                # On associe la clé 'backup' à cette valeur dans cet objet.
                "backup": str(backup_path.relative_to(root).as_posix())
                if data is not None
                else None,
            }
        )
    # On construit journal_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
    # crée ni dossier ni fichier.
    journal_path = state_dir / "pending_publication.json"
    # On appelle atomic_write avec journal_path.
    atomic_write(
        journal_path, json_bytes({"execution_id": execution_id, "originals": originals})
    )
    # On tente ce bloc et on traite séparément les erreurs prévues : BaseException.
    try:
        # On parcourt targets ; (path, data) désigne l’élément courant à chaque passage dans la boucle.
        for path, data in targets:
            # On appelle atomic_write avec path.
            atomic_write(path, data)
    except BaseException:
        # On tente ce bloc et on traite séparément les erreurs prévues : BaseException.
        try:
            # On parcourt originals ; original désigne l’élément courant à chaque passage dans la
            # boucle.
            for original in originals:
                # On garde dans path le chemin absolu résolu de root / original['path'], en tenant
                # compte des liens symboliques.
                path = (root / original["path"]).resolve()
                # Cette branche traite le cas où le test original['backup'] est satisfait.
                if original["backup"]:
                    # On appelle atomic_write avec path.
                    atomic_write(path, (root / original["backup"]).read_bytes())
                # Cette branche traite le cas où le chemin de travail existe.
                elif path.exists():
                    # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas
                    # arbitrairement d’autres fichiers.
                    path.unlink()
        except BaseException:
            # Garder le journal : une restauration incomplete doit rester visible.
            raise
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        journal_path.unlink()
        # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni en
        # fabriquer une autre.
        raise
    # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
    # d’autres fichiers.
    journal_path.unlink()
    # On remet registry à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return registry


# On lit les suivis du périmètre demandé et on prépare leurs versions et leur publication.
def run_ingestion(root: Path, vineyards=None, all_vineyards=False):
    # On garde dans root le chemin absolu résolu de root, en tenant compte des liens symboliques.
    root = root.resolve()
    # On parcourt ('data', 'data/01_incoming/suivi_acquisitions', 'data/02_raw_archive', 'd… ; relative
    # désigne l’élément courant à chaque passage dans la boucle.
    for relative in (
        "data",
        "data/01_incoming/suivi_acquisitions",
        "data/02_raw_archive",
        "data/03_normalized",
        "state",
        "config",
    ):
        # On gardes sources et les destinations locales dans le périmètre de données autorisé.
        if not (root / relative).resolve().is_relative_to(root):
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                "Chemin du projet redirige hors du projet local : " + relative
            )
    # On construit state_dir en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    state_dir = root / "state/excel_ingestion"
    # On prépare le dossier local nécessaire à cette sortie ; créer le dossier ne produit pas encore
    # le fichier qu’il contiendra.
    state_dir.mkdir(parents=True, exist_ok=True)
    # On construit lock en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    lock = state_dir / "ingestion.lock"
    # Cette branche traite le cas où state_dir / 'pending_publication.json' existe.
    if (state_dir / "pending_publication.json").exists():
        # On interrompt cette branche avec ValueError : 'Publication interrompue : diagnostic requis.
        # Ne pas effacer le journal.'.
        raise ValueError(
            "Publication interrompue : diagnostic requis. Ne pas effacer le journal."
        )
    # On tente ce bloc et on traite séparément les erreurs prévues : FileExistsError.
    try:
        # On ouvre le fichier en création exclusive : s’il existe déjà, on s’arrête au lieu de
        # l’écraser. Le bloc ferme le fichier à la sortie.
        with lock.open("x", encoding="utf-8") as f:
            # On écrit json.dumps({'pid': os.getpid(), 'started_at': utc_now()}) dans f ; le mode
            # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
            f.write(json.dumps({"pid": os.getpid(), "started_at": utc_now()}))
    except FileExistsError:
        # On interrompt cette branche avec ValueError.
        raise ValueError(
            "Verrou present : ingestion active ou interruption a diagnostiquer. Ne pas supprimer sans verification."
        )
    # On initialise attempt à None : aucune valeur n’a encore été retenue ici.
    attempt = None
    # On initialise attempt_path à None : aucune valeur n’a encore été retenue ici.
    attempt_path = None
    # On initialise published à False ; les branches suivantes pourront modifier cet état.
    published = False
    # On tente ce bloc et on traite séparément les erreurs prévues : BaseException.
    try:
        # On construit registry_path en assemblant les morceaux du chemin. L’opérateur / de pathlib
        # ne crée ni dossier ni fichier.
        registry_path = state_dir / "current.json"
        # On choisit la valeur de registry selon ce test : registry_path existe. Les deux résultats
        # possibles restent définis explicitement ici.
        registry = (
            json.loads(registry_path.read_text(encoding="utf-8"))
            if registry_path.exists()
            else None
        )
        # Cette branche traite le cas où la condition registry n’est pas remplie et la condition
        # all_vineyards n’est pas remplie.
        if not registry and not all_vineyards:
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                "Premiere initialisation : utiliser --all-vineyards. Les anciens CSV ne sont pas adoptes silencieusement."
            )
        # Cette branche traite le cas où registry est évalué comme vrai.
        if registry:
            # On vérifie ce cas avant la suite : registry.get('format_version') diffère de
            # FORMAT_VERSION.
            if registry.get("format_version") != FORMAT_VERSION:
                # On interrompt cette branche avec ValueError : 'Version de registre non reconnue.'.
                raise ValueError("Version de registre non reconnue.")
            # On parcourt registry['versions'].values() ; entry désigne l’élément courant à chaque
            # passage dans la boucle.
            for entry in registry["versions"].values():
                # On appelle verify_version avec root.
                verify_version(root, entry)
            # On construit exported en assemblant les morceaux du chemin. L’opérateur / de pathlib
            # ne crée ni dossier ni fichier.
            exported = (
                root
                / "data/03_normalized/suivi_acquisitions_normalises/toutes_acquisitions_normalisees.csv"
            )
            # On vérifie ce cas avant la suite : digest(exported.read_bytes()) diffère de
            # registry['compatibility_export_sha256'].
            if digest(exported.read_bytes()) != registry["compatibility_export_sha256"]:
                # On interrompt cette branche avec ValueError : 'Consolide courant modifie hors du
                # gestionnaire. Diagnostic requis.'.
                raise ValueError(
                    "Consolide courant modifie hors du gestionnaire. Diagnostic requis."
                )
        # On construit config_path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
        # crée ni dossier ni fichier.
        config_path = root / "config/tracking_files.yml"
        # On garde dans config_bytes les octets lus depuis config_path, avant toute conversion en
        # texte. Les contrôles de contenu pourront ainsi repartir de cette lecture.
        config_bytes = config_path.read_bytes()
        # On garde dans settings la valeur renvoyée par reader.load_settings.
        settings = reader.load_settings(config_path)
        # Refuser une configuration changeant pendant sa lecture.
        if config_path.read_bytes() != config_bytes:
            # On interrompt cette branche avec ValueError : 'Configuration modifiee pendant la
            # lecture.'.
            raise ValueError("Configuration modifiee pendant la lecture.")
        # On garde dans identity la valeur renvoyée par code_identity.
        identity = code_identity(config_bytes)
        # On choisit la valeur de requested selon ce test : le choix de tous les domaines est évalué
        # comme vrai. Les deux résultats possibles restent définis explicitement ici.
        requested = (
            None if all_vineyards else {v.strip().casefold() for v in vineyards or []}
        )
        # On garde dans available la valeur renvoyée par discover.
        available = discover(root / "data/01_incoming/suivi_acquisitions", requested)
        # Cette branche traite le cas où le choix de tous les domaines est évalué comme vrai.
        if all_vineyards:
            # On garde dans selected les éléments triés de available dans une nouvelle liste.
            selected = sorted(available)
            # Cette branche traite le cas où registry est évalué comme vrai et la condition
            # set(registry['versions']).issubset(available) n’est pas remplie.
            if registry and not set(registry["versions"]).issubset(available):
                # On interrompt cette branche avec ValueError : 'Un vignoble courant est absent des
                # Excel. Aucune suppression implicite autorisee.'.
                raise ValueError(
                    "Un vignoble courant est absent des Excel. Aucune suppression implicite autorisee."
                )
        else:
            # On garde dans selected les éléments triés de {v.strip().casefold() for v in vineyards or
            # []} dans une nouvelle liste.
            selected = sorted({v.strip().casefold() for v in vineyards or []})
            # On prévoit le cas où selected est évalué comme faux, par exemple une valeur vide selon
            # son type.
            if not selected:
                # On interrompt cette branche avec ValueError : 'Selection vide.'.
                raise ValueError("Selection vide.")
            # On calcule la différence entre ces deux valeurs pour construire unknown.
            unknown = set(selected) - set(available)
            # Cette branche traite le cas où unknown est évalué comme vrai.
            if unknown:
                # On interrompt cette branche avec ValueError.
                raise ValueError(
                    "Vignoble indisponible : " + ", ".join(sorted(unknown))
                )
        # On garde dans execution_id la valeur renvoyée par new_id.
        execution_id = new_id()
        # On construit attempt_dir en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
        # crée ni dossier ni fichier.
        attempt_dir = root / "data/03_normalized/excel_ingestion_runs" / execution_id
        # On crée ce dossier en refusant un emplacement déjà existant ; cela évite de réutiliser
        # silencieusement les sorties d’un ancien essai.
        attempt_dir.mkdir(parents=True, exist_ok=False)
        # On construit attempt_path en assemblant les morceaux du chemin. L’opérateur / de pathlib
        # ne crée ni dossier ni fichier.
        attempt_path = attempt_dir / "manifest.json"
        # On regroupe dans attempt ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        attempt = {
            # On marque la version du format pour ne pas interpréter un autre contrat de fichier par
            # erreur.
            "format_version": FORMAT_VERSION,
            # On renseigne l’identifiant d’exécution sous la clé 'execution_id'.
            "execution_id": execution_id,
            # On renseigne la date de début sous la clé 'started_at'.
            "started_at": utc_now(),
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "running",
            # On renseigne les éléments d’identité du lot sous la clé 'identity'.
            "identity": identity,
            # On renseigne le marqueur d’initialisation sous la clé 'initialization'.
            "initialization": not bool(registry),
            # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
            "vineyards": [],
        }
        # On appelle atomic_write avec attempt_path.
        atomic_write(attempt_path, json_bytes(attempt))
        # On choisit la valeur de entries selon ce test : registry est évalué comme vrai. Les deux
        # résultats possibles restent définis explicitement ici.
        entries = dict(registry["versions"]) if registry else {}
        # On prépare failures comme liste vide ; on la remplira au fil des opérations suivantes.
        failures = []
        # On initialise changed à False ; les branches suivantes pourront modifier cet état.
        changed = False
        # On parcourt la sélection retenue ; key désigne l’élément courant à chaque passage dans la
        # boucle.
        for key in selected:
            # On sélectionne dans available les éléments désignés par key ; (name, source) recevra
            # cette sélection.
            name, source = available[key]
            # On gardes sources et les destinations locales dans le périmètre de données
            # autorisé.
            if not source.resolve().is_relative_to((root / "data").resolve()):
                # On interrompt cette branche avec ValueError.
                raise ValueError(
                    "Excel redirige hors du dossier data local : " + source.name
                )
            # On regroupe dans item ces champs nommés ; on pourra les retrouver par leur clé plutôt que
            # par leur position.
            item = {
                # On renseigne le domaine concerné sous la clé 'vineyard'.
                "vineyard": name,
                # On associe la clé 'source_file' à cette valeur dans cet objet.
                "source_file": source.name,
                # On renseigne la date du contrôle sous la clé 'checked_at'.
                "checked_at": utc_now(),
            }
            # On ajoute item à la fin de attempt['vineyards'] ; les éléments précédents restent
            # conservés.
            attempt["vineyards"].append(item)
            # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
            try:
                # On garde dans previous le champ key de entries, ou None si la clé est absente.
                previous = entries.get(key)
                # On garde dans source_sha l’empreinte calculée par le helper de ce module.
                source_sha = digest(source.read_bytes())
                # Cette branche traite le cas où toutes les conditions regroupées ici sont remplies.
                if (
                    previous
                    # On exige aussi que source_sha correspond à l’empreinte du fichier source dans
                    # previous.
                    and source_sha == previous["source_sha256"]
                    # On exige aussi que les éléments d’identité du lot correspond aux éléments
                    # d’identité du lot dans previous.
                    and identity == previous["identity"]
                    # On exige aussi que source.name correspond au nom du fichier source dans
                    # previous.
                    and source.name == previous["source_filename"]
                ):
                    # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                    # nouvelle valeur fournie.
                    item.update(
                        # On fournit l’état du traitement via le paramètre status de cet appel.
                        status="unchanged",
                        # On fournit l’identifiant de version via le paramètre version_id de cet appel.
                        version_id=previous["version_id"],
                        # On fournit la date d’ingestion via le paramètre ingested_at de cet appel.
                        ingested_at=previous["ingested_at"],
                    )
                else:
                    # On garde dans entry la valeur renvoyée par store_version.
                    entry = store_version(
                        root, name, source, settings, config_bytes, identity
                    )
                    # On vérifie ce cas avant la suite : l’empreinte du fichier source dans entry
                    # diffère de source_sha.
                    if entry["source_sha256"] != source_sha:
                        # On interrompt cette branche avec ValueError : 'Source modifiee entre
                        # selection et archivage.'.
                        raise ValueError(
                            "Source modifiee entre selection et archivage."
                        )
                    # On garde entry sous le nom entries[key] ; cette affectation ne copie pas à elle
                    # seule un objet mutable.
                    entries[key] = entry
                    # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                    # nouvelle valeur fournie.
                    item.update(
                        # On fournit l’état du traitement via le paramètre status de cet appel.
                        status="version_created",
                        # On fournit l’identifiant de version via le paramètre version_id de cet appel.
                        version_id=entry["version_id"],
                        # On fournit la date d’ingestion via le paramètre ingested_at de cet appel.
                        ingested_at=entry["ingested_at"],
                        # On fournit les lignes via le paramètre rows de cet appel.
                        rows=entry["normalized_rows"],
                        # On fournit le nombre d’acquisitions distinctes via le paramètre
                        # logical_acquisitions de cet appel.
                        logical_acquisitions=entry["logical_acquisitions"],
                        # On fournit le nombre de lignes rejetées via le paramètre rejected_rows de cet
                        # appel.
                        rejected_rows=entry["rejected_rows"],
                    )
                    # On initialise changed à True ; les branches suivantes pourront modifier cet état.
                    changed = True
            except Exception as error:
                # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                item.update(status="failed", error=str(error))
                # On ajoute name à la fin de failures ; les éléments précédents restent conservés.
                failures.append(name)
            # On appelle atomic_write avec attempt_path.
            atomic_write(attempt_path, json_bytes(attempt))
        # Cette branche traite le cas où failures est évalué comme vrai.
        if failures:
            # Batch strict : aucune reference courante modifiee si un selectionne echoue.
            # Les versions deja creees restent des artefacts non selectionnes pour publication.
            details = "\n".join(
                "  " + item["vineyard"] + " : " + item["error"]
                for item in attempt["vineyards"]
                if item["status"] == "failed"
            )
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                "Publication annulee pour cette selection : "
                + ", ".join(failures)
                + "\n"
                + details
            )
        # Cette branche traite le cas où changed est évalué comme vrai.
        if changed:
            # On garde dans current la valeur renvoyée par publish.
            current = publish(root, entries, execution_id, state_dir)
            # On initialise published à True ; les branches suivantes pourront modifier cet état.
            published = True
            # On récupère l’identifiant de la publication Excel dans current et on le garde dans
            # attempt['publication_id'] pour la suite.
            attempt["publication_id"] = current["publication_id"]
            # On récupère le chemin de travail dans current['reference'] et on le garde dans
            # attempt['reference_path'] pour la suite.
            attempt["reference_path"] = current["reference"]["path"]
            # On utilise ce texte pour attempt['status'] ; il ne dépend pas d’une valeur récupérée
            # ailleurs à cet endroit.
            attempt["status"] = "success"
        else:
            # On utilise ce texte pour attempt['status'] ; il ne dépend pas d’une valeur récupérée
            # ailleurs à cet endroit.
            attempt["status"] = "unchanged"
            # On récupère l’identifiant de la publication Excel dans registry et on le garde dans
            # attempt['publication_id'] pour la suite.
            attempt["publication_id"] = registry["publication_id"]
            # On récupère le chemin de travail dans registry['reference'] et on le garde dans
            # attempt['reference_path'] pour la suite.
            attempt["reference_path"] = registry["reference"]["path"]
        # On garde dans attempt['finished_at'] la date courante en UTC sous la forme préparée par ce
        # module.
        attempt["finished_at"] = utc_now()
        # On appelle atomic_write avec attempt_path.
        atomic_write(attempt_path, json_bytes(attempt))
        # On remet attempt à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return attempt
    except BaseException as error:
        # On vérifie ce cas avant la suite : attempt est renseigné (différent de None).
        if attempt is not None:
            # On choisit la valeur de status selon ce test : published est évalué comme vrai. Les deux
            # résultats possibles restent définis explicitement ici.
            status = (
                "reporting_error_after_publication"
                if published
                else "interrupted"
                if isinstance(error, KeyboardInterrupt)
                else "failed"
            )
            # On complète attempt avec les valeurs indiquées ; une clé déjà présente prendra la
            # nouvelle valeur fournie.
            attempt.update(status=status, error=str(error), finished_at=utc_now())
            # On appelle atomic_write avec attempt_path.
            atomic_write(attempt_path, json_bytes(attempt))
        # Cette branche traite le cas où published est évalué comme vrai.
        if published:
            # On interrompt cette branche avec RuntimeError. La cause initiale reste attachée grâce à
            # from.
            raise RuntimeError(
                "Reference deja publiee, mais erreur de compte rendu : " + str(error)
            ) from error
        # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni en
        # fabriquer une autre.
        raise
    finally:
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        lock.unlink(missing_ok=True)


def configure_console():
    """Le CLI utilise UTF-8, y compris quand stdout est un pipe Windows.

    Les fonctions historiques du lecteur affichent parfois des emojis.
    Un echec d'encodage ne doit pas devenir un echec de normalisation.
    Le sous-processus doit etre lu explicitement en UTF-8 par ses appelants.
    """
    # On parcourt (sys.stdout, sys.stderr) ; stream désigne l’élément courant à chaque passage dans la
    # boucle.
    for stream in (sys.stdout, sys.stderr):
        # On garde dans reconfigure l’attribut 'reconfigure' de stream avec le repli indiqué s’il est
        # absent.
        reconfigure = getattr(stream, "reconfigure", None)
        # On vérifie ce cas avant la suite : reconfigure est renseigné (différent de None).
        if reconfigure is not None:
            # On appelle reconfigure sans argument positionnel.
            reconfigure(encoding="utf-8", errors="backslashreplace")


def main(argv=None):
    # On appelle configure_console sans argument positionnel.
    configure_console()
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On garde dans selection la valeur renvoyée par parser.add_mutually_exclusive_group.
    selection = parser.add_mutually_exclusive_group(required=True)
    # Option --vineyard : Un vignoble, repetable. Mise a jour ciblee. Sa déclaration ne déclenche
    # pas l’action.
    selection.add_argument(
        "--vineyard",
        action="append",
        help="Un vignoble, repetable. Mise a jour ciblee.",
    )
    # Option --all-vineyards : Tous les Excel locaux reconnus ; requis pour initialiser. Sa
    # déclaration ne déclenche pas l’action.
    selection.add_argument(
        "--all-vineyards",
        action="store_true",
        help="Tous les Excel locaux reconnus ; requis pour initialiser.",
    )
    # On garde dans args les options passées à la commande, après leur analyse par argparse.
    args = parser.parse_args(argv)
    # On tente ce bloc et on traite séparément les erreurs prévues : KeyboardInterrupt, Exception.
    try:
        # On garde dans result la valeur renvoyée par run_ingestion.
        result = run_ingestion(reader.PROJECT_ROOT, args.vineyard, args.all_vineyards)
    except KeyboardInterrupt:
        # On affiche ce texte explicite dans la sortie du programme.
        print(
            "\nIngestion interrompue. Consulter le manifeste avant de relancer.",
            file=sys.stderr,
        )
        # On termine cette branche avec la valeur 130 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 130
    except Exception as error:
        # On affiche 'ECHEC INGESTION : ' + str(error) dans la sortie du programme.
        print("ECHEC INGESTION : " + str(error), file=sys.stderr)
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    # On affiche le texte '\nINGESTION EXCEL VERSIONNEE - aucun acces au NAS' dans la sortie du
    # programme.
    print("\nINGESTION EXCEL VERSIONNEE - aucun acces au NAS")
    # On affiche 'Execution : ' + result['execution_id'] dans la sortie du programme.
    print("Execution : " + result["execution_id"])
    # On parcourt les domaines sélectionnés dans result ; item désigne l’élément courant à chaque
    # passage dans la boucle.
    for item in result["vineyards"]:
        # On choisit la valeur de label selon ce test : l’état du traitement dans item correspond à le
        # texte 'unchanged'. Les deux résultats possibles restent définis explicitement ici.
        label = (
            "Inchange - version conservee"
            if item["status"] == "unchanged"
            else "Nouvelle version"
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"  {item['vineyard']} : {label} | {item['version_id']} | ingestion {item['ingested_at']}"
        )
        # On vérifie ce cas avant la suite : l’état du traitement dans item diffère du texte
        # 'unchanged'.
        if item["status"] != "unchanged":
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"    Lignes normalisees : {item['rows']} | acquisitions logiques : {item['logical_acquisitions']} | rejets : {item['rejected_rows']}"
            )
    # On affiche 'Resultat : ' + result['status'] dans la sortie du programme.
    print("Resultat : " + result["status"])
    # On affiche 'Reference publiee : ' + result['reference_path'] dans la sortie du programme.
    print("Reference publiee : " + result["reference_path"])
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "Manifeste : data/03_normalized/excel_ingestion_runs/"
        + result["execution_id"]
        + "/manifest.json"
    )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "Les exports courants restent compatibles ; les anciennes versions sont conservees."
    )
    # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de retour.
    return 0
