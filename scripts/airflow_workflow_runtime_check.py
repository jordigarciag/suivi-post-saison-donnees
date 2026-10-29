# Lecture du fichier — Vérification des montages Docker, des destinations locales et de quelques sources ciblées.
# On contrôle avant d’ingérer. Ce diagnostic lit des sources et crée puis supprime des sondes locales
# ; il ne faut pas le confondre avec une opération sans aucun effet.
#

"""Garde-fous Docker, partage local et lecture ciblee du NAS ; pas d'ingestion."""

# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On rend disponibles UUID, uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import UUID, uuid4

# On raisonne sur les chemins vus dans le conteneur, pas sur les chemins Windows du poste.
ROOT = Path("/opt/project")
# On attend deux sous-dossiers sous la même racine /opt/nas : images brutes et résultats de
# traitement.
NAS = (Path("/opt/nas/brute_v2025"), Path("/opt/nas/data_processing_2025"))
# RO signifie read-only : on doit pouvoir lire ces sources sans autoriser leur modification par ces
# montages.
RO_MOUNTS = (
    "/opt/project/src",
    "/opt/project/scripts",
    "/opt/project/config/tracking_files.yml",
    "/opt/project/data/01_incoming/suivi_acquisitions",
    "/opt/nas",
)
# Les résultats, l’état et les journaux ont au contraire besoin de destinations locales accessibles
# en écriture.
RW_MOUNTS = ("/opt/project/data", "/opt/project/state", "/opt/project/logs")


class RuntimeCheckError(ValueError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(ok, code):
    # On prévoit le cas où ok est évalué comme faux, par exemple une valeur vide selon son type.
    if not ok:
        # On interrompt cette branche avec RuntimeCheckError.
        raise RuntimeCheckError(code)


# On lit les chemins et les options de montage à partir du texte fourni par Linux.
def mount_options(content):
    # On prépare le dictionnaire chemin → ensemble d’options. Exemple : {"/opt/nas": {"ro",
    # "relatime"}}.
    result = {}
    # On traite le texte ligne par ligne pour conserver la séparation des enregistrements.
    for line in content.splitlines():
        # Les champs sont séparés par des espaces ; les espaces à l’intérieur des chemins sont
        # encodés par Linux.
        fields = line.split()
        # On ignore une ligne incomplète avant de lire les positions précises des champs.
        if len(fields) < 7 or "-" not in fields:
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # Le champ d’indice 4 contient le chemin. On décodes séquences octales : par exemple \040
        # représente un espace.
        point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), fields[4])
        # Plusieurs entrees pour le meme point : refus plutot que choisir un montage cache.
        require(point not in result, "DUPLICATE_MOUNT_POINT")
        # Le champ suivant porte les options séparées par des virgules. On les range dans un ensemble
        # pour rechercher ro ou rw.
        result[point] = set(fields[5].split(","))
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On exige les modes de lecture et d’écriture prévus pour chaque point de montage.
def validate_mounts(content):
    # On garde dans mounts la valeur renvoyée par mount_options.
    mounts = mount_options(content)
    # On contrôle chaque montage qui doit rester en lecture seule, dont la racine du NAS.
    for name in RO_MOUNTS:
        # Le montage de cette source doit annoncer la lecture seule. La simple présence du dossier
        # ne prouve pas que l’écriture y est interdite.
        require(
            name in mounts and "ro" in mounts[name] and "rw" not in mounts[name],
            "READ_ONLY_MOUNT_NOT_CONFIRMED:" + name,
        )
    # On vérifie séparément les destinations locales qui doivent permettre les écritures du
    # traitement.
    for name in RW_MOUNTS:
        # Les sorties et l’état doivent être accessibles en écriture dans le partage prévu ; un
        # montage de source en lecture seule ne peut pas remplir ce rôle.
        require(
            name in mounts and "rw" in mounts[name] and "ro" not in mounts[name],
            "SHARED_WRITE_MOUNT_NOT_CONFIRMED:" + name,
        )


# On contrôle le conteneur, les destinations locales et les sources ciblées avant toute ingestion.
def check_runtime(root=ROOT):
    # Ce contrôle est prévu pour le conteneur Linux et sa racine /opt/project ; le lancer sur un
    # autre emplacement ne validerait pas le même environnement.
    require(os.name == "posix" and Path(root) == ROOT, "DOCKER_LINUX_ROOT_REQUIRED")
    # On demandu marqueur explicite de ce conteneur de workflow pour éviter de valider par erreur
    # un terminal quelconque.
    require(
        os.environ.get("PROJECT12_WORKFLOW_DOCKER") == "1",
        "DOCKER_WORKFLOW_FLAG_REQUIRED",
    )
    # Dans le conteneur, les connexions doivent venir de l’environnement explicite ; le .env du
    # poste ne doit pas servir de solution de repli.
    require(
        os.environ.get("PROJECT12_IMPORT_CONNECTION_MODE") == "environment"
        # On exige aussi que os.environ.get('PROJECT12_NAS_CONNECTION_MODE') correspond au texte
        # 'environment'.
        and os.environ.get("PROJECT12_NAS_CONNECTION_MODE") == "environment",
        "ENVIRONMENT_MODES_REQUIRED",
    )
    # On attend les chemins NAS internes au conteneur, pas les chemins Windows ou WSL utilisés pour
    # monter la source à l’extérieur.
    require(
        tuple(os.environ.get(k) for k in ("NAS_BRUT_ROOT", "NAS_PROCESSING_ROOT"))
        == tuple(str(p) for p in NAS),
        "NAS_CONTAINER_ROOTS_MISMATCH",
    )
    # Le .env local ne doit pas être exposé dans ce conteneur ; les variables nécessaires lui sont
    # transmises explicitement.
    require(not (ROOT / ".env").exists(), "LOCAL_ENV_MUST_NOT_BE_MOUNTED")
    # On appelle validate_mounts avec Path('/proc/self/mountinfo').read_text(encoding='utf-8').
    validate_mounts(Path("/proc/self/mountinfo").read_text(encoding="utf-8"))
    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    identity = json.loads(
        (ROOT / "state/workflow_execution/airflow_share_identity.json").read_text(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8"
        )
    )
    # Les services doivent reconnaître le même espace d’état local ; sinon leurs verrous et reçus ne
    # protégeraient pas le même parcours.
    require(
        set(identity) == {"share_id"}
        # On exige aussi que str(UUID(identity['share_id'])) correspond à identity['share_id'].
        and str(UUID(identity["share_id"])) == identity["share_id"]
        # On exige aussi que identity['share_id'] correspond à
        # os.environ.get('PROJECT12_WORKFLOW_SHARE_ID').
        and identity["share_id"] == os.environ.get("PROJECT12_WORKFLOW_SHARE_ID"),
        "SHARED_STATE_IDENTITY_MISMATCH",
    )
    # Ecritures de sondes exclusivement dans les destinations locales, puis suppression.
    for relative in (
        "state/workflow_execution",
        "data/02_raw_archive",
        "data/03_normalized",
        "data/04_rejected",
        "logs/airflow_workflow",
    ):
        # On calcule ce quotient pour construire folder.
        folder = ROOT / relative
        # Ce contrôle porte sur la destination résolue ; un chemin textuellement situé sous le
        # projet pourrait encore pointer ailleurs par un lien symbolique.
        require(folder.resolve().is_relative_to(ROOT), "LOCAL_DESTINATION_REDIRECTED")
        # On construit probe en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
        # ni dossier ni fichier.
        probe = folder / (".airflow_probe_" + uuid4().hex)
        # On ouvre le fichier en création exclusive : s’il existe déjà, on s’arrête au lieu de
        # l’écraser. Le bloc ferme le fichier à la sortie.
        with probe.open("x", encoding="ascii") as f:
            # On écrit 'local-write-probe' dans f ; le mode d’ouverture du flux détermine s’il s’agit
            # d’un ajout ou d’un remplacement.
            f.write("local-write-probe")
        # La sonde doit pouvoir être écrite puis relue avec le contenu prévu ; le seul droit affiché
        # sur un dossier ne suffit pas au démontrer.
        require(
            probe.read_text(encoding="ascii") == "local-write-probe",
            "LOCAL_WRITE_PROBE_FAILED",
        )
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        probe.unlink()
    # On construit incoming en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    incoming = ROOT / "data/01_incoming/suivi_acquisitions"
    # On construit candidates comme une liste à partir de p, pour chaque p de incoming.glob('*.xlsx')
    # en ne gardant que les éléments qui passent le filtre.
    candidates = [
        p
        for p in incoming.glob("*.xlsx")
        if "domainedemod" in p.name.casefold() and not p.name.startswith("~$")
    ]
    # Le diagnostic pilote attend un seul classeur pour ce domaine. Zéro ou plusieurs fichiers
    # laisseraient la source à utiliser indéterminée.
    require(
        len(candidates) == 1 and candidates[0].is_file(),
        "PILOTE_EXCEL_SOURCE_NOT_UNIQUE",
    )
    # Un fichier xlsx est une archive ZIP. Sa signature est un premier contrôle de format, pas une
    # validation complète du classeur.
    with candidates[0].open("rb") as f:
        # On vérifie d’abord que le fichier a bien la structure ZIP d’un classeur .xlsx, avant de le
        # confier au lecteur Excel.
        require(f.read(4) == b"PK\x03\x04", "PILOTE_EXCEL_NOT_ZIP_WORKBOOK")
    # Seulement les deux repertoires de saison et les deux JSON canoniques.
    for folder in (NAS[0] / "DomaineDemoD/2026", NAS[1] / "DomaineDemoD/acquisitions/2026"):
        # Le dossier de saison doit être accessible pour ce domaine. Un accès impossible ne permet
        # pas de conclure que les acquisitions sont absentes.
        require(folder.is_dir(), "PILOTE_NAS_SEASON_DIRECTORY_UNAVAILABLE")
        # On utilise os.scandir(folder) dans son contexte de gestion ; les opérations de sortie sont
        # exécutées en quittant le bloc.
        with os.scandir(folder) as entries:
            # On appelle next avec entries.
            next(entries, None)
    # On parcourt (NAS[1] / 'DomaineDemoD/parcels/DomaineDemoD_parcels_acquisitions_map.jso… ; path
    # désigne l’élément courant à chaque passage dans la boucle.
    for path in (
        NAS[1] / "DomaineDemoD/parcels/DomaineDemoD_parcels_acquisitions_map.json",
        NAS[1] / "DomaineDemoD/passages/DomaineDemoD_parcels_passages_acquisitions_map.json",
    ):
        # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la sortie,
        # y compris après une erreur.
        with path.open("r", encoding="utf-8-sig") as f:
            # On garde dans payload les objets Python lus dans ce flux JSON.
            payload = json.load(f)
        # Le diagnostic doit pouvoir lire les correspondances NAS sous la forme attendue avant
        # d’annoncer que les sources sont prêtes.
        require(isinstance(payload, (dict, list)), "PILOTE_MAPPING_JSON_INVALID")
    # On remet identity['share_id'] à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return identity["share_id"]


# On prépare un nom de reçu local distinct pour cette tentative.
def receipt_path(root, kind):
    # On distingue le reçu de diagnostic du reçu d’exécution ; les deux ne prouvent pas la même
    # chose.
    require(kind in ("diagnostic", "execution"), "RECEIPT_KIND_INVALID")
    # On remet Path(root) / 'logs/airflow_workflow' / (kind + '_' + datetime.now(timezon… à l’appelant
    # ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return (
        Path(root)
        / "logs/airflow_workflow"
        / (
            kind
            + "_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            + "_"
            + uuid4().hex
            + ".json"
        )
    )


# On crée un nouveau reçu JSON sans écraser un fichier du même nom.
def write_receipt(path, payload):
    # On ouvre le fichier en création exclusive : s’il existe déjà, on s’arrête au lieu de
    # l’écraser. Le bloc ferme le fichier à la sortie.
    with Path(path).open("x", encoding="utf-8") as f:
        # On appelle json.dump avec payload.
        json.dump(payload, f, ensure_ascii=False)
