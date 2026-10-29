# Lecture du fichier — Construction et contrôle du processus enfant chargé de lire le NAS.
# On limite ses paramètres et son environnement, puis on encadre sa durée et son arrêt. Ces
# précautions ne remplacent pas les permissions du stockage.
#

"""Executor explicite du pilote ; aucun lancement ni lecture .env a l'import.
Ce n'est pas un sandbox OS : le code du projet doit etre fiable et le NAS reste
une source en lecture seule. Aucun mode de pipeline reel ajoute par ce module.
"""

# On importe ast. On analyse la structure du code Python sans exécuter le texte analysé.
import ast
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe math. On utilise les contrôles ou calculs numériques définis dans ce module.
import math
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys

# On fixe EXTRACTOR à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
EXTRACTOR = (
    "src/suivi_traitements_post_saison/extraction/nas_live_evidence_extractor.py"
)
# On fixe RECONCILER à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
RECONCILER = (
    "src/suivi_traitements_post_saison/reconciliation/excel_nas_live_reconciler.py"
)
# On fixe HELPER à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
HELPER = "src/suivi_traitements_post_saison/extraction/workflow_nas_environment.py"
# On rassemble dans EXTRACTION_FLAGS les 4 éléments explicitement indiqués, en conservant leur
# structure.
EXTRACTION_FLAGS = {"--vineyard", "--year", "--reference", "--output-dir"}
# On rassemble dans RECONCILIATION_FLAGS les 6 éléments explicitement indiqués, en conservant leur
# structure.
RECONCILIATION_FLAGS = {
    "--vineyard",
    "--reference",
    "--evidence",
    "--associations",
    "--passages",
    "--output-dir",
}


class NasChildTimeout(RuntimeError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


# On refuse les valeurs de commande ou d’environnement qui ne respectent pas les caractères
# autorisés.
def clean_value(value):
    # On remet isinstance(value, str) and bool(value.strip()) and (not any((c in value f… à l’appelant
    # ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return (
        isinstance(value, str)
        # On exige aussi que le contrôle bool(value.strip()) est positif.
        and bool(value.strip())
        # On exige aussi que la condition any((c in value for c in ('\x00', '\r', '\n'))) n’est pas
        # remplie.
        and not any(c in value for c in ("\x00", "\r", "\n"))
    )


# On prépare un chemin NAS avec les règles lexicales prévues par l’exécuteur.
def nas_path(value):
    # Cette branche traite le cas où la condition clean_value(value) n’est pas remplie ou la condition
    # Path(value).is_absolute() n’est pas remplie.
    if not clean_value(value) or not Path(value).is_absolute():
        # On interrompt cette branche avec ValueError : 'Racines NAS explicites absolues requises,
        # adaptees au systeme courant.'.
        raise ValueError(
            "Racines NAS explicites absolues requises, adaptees au systeme courant."
        )
    # Pas de resolve/is_dir/stat sur les racines NAS : aucune consultation ici.
    return Path(os.path.normpath(value))


# On construit un chemin et on vérifie qu’il reste dans le périmètre local autorisé par ce module.
def local_path(root, value, *, exists=False):
    # On construit un objet chemin à partir de la valeur reçue ; cette construction seule ne vérifie
    # ni l’existence ni les droits d’accès.
    path = Path(value)
    # Cette branche traite le cas où la condition path.is_absolute() n’est pas remplie.
    if not path.is_absolute():
        # On interrompt cette branche avec ValueError : 'Chemin local absolu requis.'.
        raise ValueError("Chemin local absolu requis.")
    # On calcule le chemin local résolu pour détecter les redirections avant de vérifier qu’il reste
    # dans le projet.
    resolved = path.resolve()
    # Ce chemin servirait de destination hors du projet. On ne l’utilise pas pour le processus
    # enfant.
    if not resolved.is_relative_to(root):
        # On interrompt cette branche avec ValueError : 'Chemin redirige hors du projet local.'.
        raise ValueError("Chemin redirige hors du projet local.")
    # Cette branche traite le cas où exists est évalué comme vrai et la condition path.exists() n’est
    # pas remplie.
    if exists and not path.exists():
        # On interrompt cette branche avec ValueError : 'Entree locale absente.'.
        raise ValueError("Entree locale absente.")
    # On remet le chemin de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return path


# On construit l’environnement nécessaire au processus sans reprendre toutes les variables du poste.
def minimal_environment(
    root, *, nas_brut_root, nas_processing_root, temp_dir, parent=None
):
    """Liste blanche, pas de copie puis suppression approximative de secrets."""
    # On distribue ces valeurs entre brut, processing, dans l’ordre de l’affectation. Chaque nom
    # reçoit son propre élément.
    brut, processing = nas_path(nas_brut_root), nas_path(nas_processing_root)
    # Si aucun environnement n’a été fourni explicitement, on part de celui du processus courant ;
    # les tests peuvent en fournir un autre.
    parent = os.environ if parent is None else parent
    # On part d’une liste blanche vide. Seules les variables ajoutées ensuite seront transmises, pas
    # tous les réglages du poste.
    environment = {}
    # Windows : variables OS necessaires, aucune PATH/COMSPEC ou variable applicative.
    for name in ("SystemRoot", "WINDIR"):
        # On construit values comme une liste à partir de value, pour chaque (key, value) de
        # parent.items() en ne gardant que les éléments qui passent le filtre.
        values = [
            value
            for key, value in parent.items()
            if isinstance(key, str) and key.casefold() == name.casefold()
        ]
        # On compare le nombre d’éléments au nombre de valeurs distinctes pour repérer les doublons
        # avant de poursuivre.
        if len(set(values)) > 1:
            # On interrompt cette branche avec ValueError : 'Variable technique OS contradictoire.'.
            raise ValueError("Variable technique OS contradictoire.")
        # Après le contrôle des doublons, on prend la valeur disponible ; sans correspondance, on
        # garde None plutôt qu’inventer un réglage.
        value = values[0] if values else None
        # On vérifie ce cas avant la suite : la valeur reçue est renseigné (différent de None).
        if value is not None:
            # Cette branche traite le cas où la condition clean_value(value) n’est pas remplie ou la
            # condition Path(value).is_absolute() n’est pas remplie.
            if not clean_value(value) or not Path(value).is_absolute():
                # On interrompt cette branche avec ValueError : 'Variable technique OS invalide.'.
                raise ValueError("Variable technique OS invalide.")
            # On garde la valeur reçue sous le nom environment[name] ; cette affectation ne copie pas à
            # elle seule un objet mutable.
            environment[name] = value
    # Cette branche traite le cas où os.name correspond au texte 'nt' et le texte 'SystemRoot' ne
    # figure pas dans les variables transmises au processus enfant.
    if os.name == "nt" and "SystemRoot" not in environment:
        # On interrompt cette branche avec ValueError : 'SystemRoot requis pour le lancement Windows.'.
        raise ValueError("SystemRoot requis pour le lancement Windows.")
    # On ajoute seulement les racines NAS, le chemin du code, les réglages Python et les dossiers
    # temporaires nécessaires. Les mots de passe Airflow ne font pas partie de cette liste.
    environment.update(
        {
            # On associe la clé 'PROJECT12_NAS_CONNECTION_MODE' à cette valeur dans cet objet.
            "PROJECT12_NAS_CONNECTION_MODE": "environment",
            # On associe la clé 'NAS_BRUT_ROOT' à cette valeur dans cet objet.
            "NAS_BRUT_ROOT": str(brut),
            # On associe la clé 'NAS_PROCESSING_ROOT' à cette valeur dans cet objet.
            "NAS_PROCESSING_ROOT": str(processing),
            # On associe la clé 'PYTHONPATH' à cette valeur dans cet objet.
            "PYTHONPATH": str(root / "src"),
            # On associe la clé 'PYTHONNOUSERSITE' à cette valeur dans cet objet.
            "PYTHONNOUSERSITE": "1",
            # On associe la clé 'PYTHONUTF8' à cette valeur dans cet objet.
            "PYTHONUTF8": "1",
            # On associe la clé 'PYTHONIOENCODING' à cette valeur dans cet objet.
            "PYTHONIOENCODING": "utf-8",
            # On associe la clé 'PYTHONUNBUFFERED' à cette valeur dans cet objet.
            "PYTHONUNBUFFERED": "1",
            # On associe la clé 'PYTHONDONTWRITEBYTECODE' à cette valeur dans cet objet.
            "PYTHONDONTWRITEBYTECODE": "1",
            # On associe la clé 'TMPDIR' à cette valeur dans cet objet.
            "TMPDIR": str(temp_dir),
            # On associe la clé 'TEMP' à cette valeur dans cet objet.
            "TEMP": str(temp_dir),
            # On associe la clé 'TMP' à cette valeur dans cet objet.
            "TMP": str(temp_dir),
        }
    )
    # On remet les variables transmises au processus enfant à l’appelant ; les étapes suivantes de
    # cette fonction ne sont plus parcourues.
    return environment


def check_extractor_mode(source):
    """Exiger le raccordement du helper avant de permettre l'execution du pilote."""
    # On analyse la structure du code source sans l’exécuter ; cela permet de contrôler ses appels
    # ou imports sans lancer le traitement décrit.
    tree = ast.parse(source)
    # On recherche dans l’arbre syntaxique l’appel au helper qui impose le mode de connexion NAS
    # explicite ; aucun code source n’est exécuté pour cette recherche.
    configured = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        # On exige aussi que node.func est du type ast.Name.
        and isinstance(node.func, ast.Name)
        # On exige aussi que node.func.id correspond au texte 'configure_nas_environment'.
        and node.func.id == "configure_nas_environment"
    ]
    # On repère les anciens appels à load_dotenv : ils permettraient de récupérer implicitement les
    # réglages du poste, ce que cette entrée veut éviter.
    old = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        # On exige aussi que node.func est du type ast.Name.
        and isinstance(node.func, ast.Name)
        # On exige aussi que node.func.id correspond au texte 'load_dotenv'.
        and node.func.id == "load_dotenv"
    ]
    # On vérifie aussi d’où vient le helper ; trouver seulement un nom d’appel identique ne
    # prouverait pas le raccordement au bon module.
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        # On exige aussi que node.module correspond au texte 'workflow_nas_environment'.
        and node.module == "workflow_nas_environment"
        # On exige aussi que au moins un élément satisfait le test indiqué.
        and any(alias.name == "configure_nas_environment" for alias in node.names)
    ]
    # Cette branche traite le cas où len(configured) diffère de 1 ou old est évalué comme vrai ou la
    # condition imports n’est pas remplie.
    if len(configured) != 1 or old or not imports:
        # On interrompt cette branche avec ValueError : 'Extracteur non raccorde au mode environnement
        # explicite.'.
        raise ValueError("Extracteur non raccorde au mode environnement explicite.")
    # On récupère configured[0] et on le garde dans call pour la suite.
    call = configured[0]
    # Cette branche traite le cas où len(call.args) diffère de 1 ou le type reçu ne correspond pas à
    # ast.Name ou call.args[0].id diffère du texte 'PROJECT_ROOT'.
    if (
        len(call.args) != 1
        # Ce cas est aussi retenu si le type reçu ne correspond pas à ast.Name.
        or not isinstance(call.args[0], ast.Name)
        # Ce cas est aussi retenu si call.args[0].id diffère du texte 'PROJECT_ROOT'.
        or call.args[0].id != "PROJECT_ROOT"
    ):
        # On interrompt cette branche avec ValueError : 'Appel de configuration NAS non reconnu.'.
        raise ValueError("Appel de configuration NAS non reconnu.")


# On vérifie la commande autorisée avant de créer le processus enfant.
def validate_command(root, command, log_path):
    # Cette branche traite le cas où le type reçu ne correspond pas à (list, tuple) ou len(command) est
    # inférieur à 2 ou la condition all((clean_value(v) for v in command)) n’est pas remplie.
    if (
        not isinstance(command, (list, tuple))
        # Ce cas est aussi retenu si len(command) est inférieur à 2.
        or len(command) < 2
        # Ce cas est aussi retenu si la condition all((clean_value(v) for v in command)) n’est pas
        # remplie.
        or not all(clean_value(v) for v in command)
    ):
        # On interrompt cette branche avec ValueError : 'Commande du pilote invalide.'.
        raise ValueError("Commande du pilote invalide.")
    # Cette branche traite le cas où la condition Path(command[0]).is_absolute() n’est pas remplie ou
    # Path(command[0]).resolve() diffère de Path(sys.executable).resolve().
    if (
        not Path(command[0]).is_absolute()
        # Ce cas est aussi retenu si Path(command[0]).resolve() diffère de
        # Path(sys.executable).resolve().
        or Path(command[0]).resolve() != Path(sys.executable).resolve()
    ):
        # On interrompt cette branche avec ValueError : 'Seul le Python actif est autorise ; pas de
        # shell ou executable externe.'.
        raise ValueError(
            "Seul le Python actif est autorise ; pas de shell ou executable externe."
        )
    # On garde dans script le chemin absolu résolu de local_path(root, command[1], exists=True), en
    # tenant compte des liens symboliques.
    script = local_path(root, command[1], exists=True).resolve()
    # On vérifie ce cas avant la suite : script correspond à (root / EXTRACTOR).resolve().
    if script == (root / EXTRACTOR).resolve():
        # On distribue ces valeurs entre stage, wanted, output_base, dans l’ordre de l’affectation.
        # Chaque nom reçoit son propre élément.
        stage, wanted, output_base = (
            "extraction",
            EXTRACTION_FLAGS,
            "data/03_normalized/nas_live_evidence/runs",
        )
    # On vérifie ce cas avant la suite : script correspond à (root / RECONCILER).resolve().
    elif script == (root / RECONCILER).resolve():
        # On distribue ces valeurs entre stage, wanted, output_base, dans l’ordre de l’affectation.
        # Chaque nom reçoit son propre élément.
        stage, wanted, output_base = (
            "reconciliation",
            RECONCILIATION_FLAGS,
            "data/03_normalized/reconciliations/nas_live/runs",
        )
    else:
        # On interrompt cette branche avec ValueError : 'Script non autorise par le contrat du
        # pilote.'.
        raise ValueError("Script non autorise par le contrat du pilote.")
    # Cette branche traite le cas où le test (len(command) - 2) % 2 est satisfait.
    if (len(command) - 2) % 2:
        # On interrompt cette branche avec ValueError : 'Arguments incomplets.'.
        raise ValueError("Arguments incomplets.")
    # On crée le dictionnaire vide options pour y ranger ensuite les éléments par clé.
    options = {}
    # On parcourt ces collections en parallèle ; les éléments de même position seront comparés ou
    # associés dans le corps de la boucle.
    for flag, value in zip(command[2::2], command[3::2]):
        # Cette branche traite le cas où flag ne figure pas dans wanted ou flag appartient à les
        # options proposées ou la valeur reçue commence par le texte '-'.
        if flag not in wanted or flag in options or value.startswith("-"):
            # On interrompt cette branche avec ValueError : 'Argument inconnu, duplique ou ambigu.'.
            raise ValueError("Argument inconnu, duplique ou ambigu.")
        # On garde la valeur reçue sous le nom options[flag] ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        options[flag] = value
    # On vérifie ce cas avant la suite : set(options) diffère de wanted.
    if set(options) != wanted:
        # On interrompt cette branche avec ValueError : 'Arguments requis du pilote absents.'.
        raise ValueError("Arguments requis du pilote absents.")
    # Cette branche traite le cas où l’étape concernée correspond au texte 'extraction' et la
    # condition re.fullmatch('[0-9]{4}', options['--year']) n’est pas remplie.
    if stage == "extraction" and not re.fullmatch(r"[0-9]{4}", options["--year"]):
        # On interrompt cette branche avec ValueError : 'Annee de la commande invalide.'.
        raise ValueError("Annee de la commande invalide.")
    # On garde dans log le chemin local après les contrôles de périmètre du module.
    log = local_path(root, log_path)
    # Cette branche traite le cas où la condition re.fullmatch('v[0-9]{2,}_' + stage + '\\.log',
    # log.name) n’est pas remplie.
    if not re.fullmatch(r"v[0-9]{2,}_" + stage + r"\.log", log.name):
        # On interrompt cette branche avec ValueError : 'Nom de log incompatible avec l etape.'.
        raise ValueError("Nom de log incompatible avec l etape.")
    # On garde log.parent.name sous le nom execution ; cette affectation ne copie pas à elle seule un
    # objet mutable.
    execution = log.parent.name
    # Cette branche traite le cas où la condition re.fullmatch('[0-9]{8}_[0-9a-f]{8}', execution) n’est
    # pas remplie ou log.parent.parent.resolve() diffère de (root /
    # 'data/03_normalized/pipeline_runs').resolve().
    if (
        not re.fullmatch(r"[0-9]{8}_[0-9a-f]{8}", execution)
        # Ce cas est aussi retenu si log.parent.parent.resolve() diffère de (root /
        # 'data/03_normalized/pipeline_runs').resolve().
        or log.parent.parent.resolve()
        != (root / "data/03_normalized/pipeline_runs").resolve()
    ):
        # On interrompt cette branche avec ValueError : 'Log hors execution du pilote.'.
        raise ValueError("Log hors execution du pilote.")
    # On garde dans reference le chemin local après les contrôles de périmètre du module.
    reference = local_path(root, options["--reference"], exists=True)
    # Cette branche traite le cas où reference.resolve() diffère de (log.parent /
    # 'tracking_reference_snapshot.csv').resolve() ou la condition reference.is_file() n’est pas
    # remplie.
    if (
        reference.resolve()
        != (log.parent / "tracking_reference_snapshot.csv").resolve()
        # Ce cas est aussi retenu si la condition reference.is_file() n’est pas remplie.
        or not reference.is_file()
    ):
        # On interrompt cette branche avec ValueError : 'Reference hors snapshot de cette execution.'.
        raise ValueError("Reference hors snapshot de cette execution.")
    # On récupère log.name.split('_', 1)[0] et on le garde dans directory pour la suite.
    directory = log.name.split("_", 1)[0]
    # On garde dans output le chemin local après les contrôles de périmètre du module.
    output = local_path(root, options["--output-dir"], exists=True)
    # On calcule ce quotient pour construire expected_output.
    expected_output = root / output_base / execution / directory
    # Cette branche traite le cas où output.resolve() diffère de expected_output.resolve() ou la
    # condition output.is_dir() n’est pas remplie.
    if output.resolve() != expected_output.resolve() or not output.is_dir():
        # On interrompt cette branche avec ValueError : 'Sortie hors dossier local de cette
        # execution.'.
        raise ValueError("Sortie hors dossier local de cette execution.")
    # On vérifie ce cas avant la suite : l’étape concernée correspond au texte 'reconciliation'.
    if stage == "reconciliation":
        # On garde dans base le chemin absolu résolu de root /
        # 'data/03_normalized/nas_live_evidence/runs' / execution /…, en tenant compte des liens
        # symboliques.
        base = (
            root / "data/03_normalized/nas_live_evidence/runs" / execution / directory
        ).resolve()
        # On parcourt ('--evidence', '--associations', '--passages') ; flag désigne l’élément courant à
        # chaque passage dans la boucle.
        for flag in ("--evidence", "--associations", "--passages"):
            # On garde dans path le chemin local après les contrôles de périmètre du module.
            path = local_path(root, options[flag], exists=True)
            # Cette branche traite le cas où path.parent.resolve() diffère de base ou la condition
            # path.is_file() n’est pas remplie ou path.suffix diffère du texte '.csv'.
            if (
                path.parent.resolve() != base
                # Ce cas est aussi retenu si la condition path.is_file() n’est pas remplie.
                or not path.is_file()
                # Ce cas est aussi retenu si path.suffix diffère du texte '.csv'.
                or path.suffix != ".csv"
            ):
                # On interrompt cette branche avec ValueError : 'Preuves locales hors execution ou
                # format attendu.'.
                raise ValueError("Preuves locales hors execution ou format attendu.")
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return stage, log


# On encadre l’arrêt du processus enfant et de ses descendants selon le système disponible.
def stop_child(process):
    # poll renvoie déjà un code si le processus est terminé ; il n’y a alors plus d’arrêt à
    # demander.
    if process.poll() is not None:
        # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont pas
        # exécutées.
        return
    # On tente ce bloc et on traite séparément les erreurs prévues : ProcessLookupError.
    try:
        # On demande d’abord un arrêt normal au processus. Si cela ne suffit pas, le bloc suivant
        # attendra puis tentera un arrêt forcé.
        process.terminate()
    except ProcessLookupError:
        # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont pas
        # exécutées.
        return
    # On tente ce bloc et on traite séparément les erreurs prévues : subprocess.TimeoutExpired.
    try:
        # On attend la fin du processus avec les paramètres indiqués ; son code de retour sera
        # contrôlé avant de poursuivre.
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # Le délai d’arrêt normal est dépassé : on tente un arrêt forcé, puis on attend de nouveau
        # sa fin pour ne pas annoncer un arrêt sans le vérifier.
        process.kill()
        # On appelle process.wait sans argument positionnel.
        process.wait(timeout=5)


# On prépare un exécuteur contrôlé plutôt que laisser chaque appel construire une commande libre.
def build_nas_executor(
    root,
    *,
    nas_brut_root,
    nas_processing_root,
    timeout_seconds=3600,
    parent_environment=None,
):
    """Factory compatible executor(command, root, log_path) du pilote existant.
    Pas d'acces NAS, de creation de dossier ou de lancement lors de sa construction.
    """
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où la condition root.is_dir() n’est pas remplie ou str(root) commence
    # par ('\\\\', '//').
    if not root.is_dir() or str(root).startswith(("\\\\", "//")):
        # On interrompt cette branche avec ValueError : 'Racine du projet local requise.'.
        raise ValueError("Racine du projet local requise.")
    # Cette branche traite le cas où type(timeout_seconds) ne figure pas dans (int, float) ou la
    # condition math.isfinite(timeout_seconds) n’est pas remplie ou la condition 1 <= timeout_seconds
    # <= 86400 n’est pas remplie.
    if (
        type(timeout_seconds) not in (int, float)
        # Ce cas est aussi retenu si la condition math.isfinite(timeout_seconds) n’est pas remplie.
        or not math.isfinite(timeout_seconds)
        # Ce cas est aussi retenu si la condition 1 <= timeout_seconds <= 86400 n’est pas remplie.
        or not 1 <= timeout_seconds <= 86400
    ):
        # On interrompt cette branche avec ValueError : 'Delai explicite compris entre 1 et 86400
        # secondes requis.'.
        raise ValueError("Delai explicite compris entre 1 et 86400 secondes requis.")
    # On rassemble dans roots les 2 éléments explicitement indiqués, en conservant leur structure.
    roots = [nas_path(nas_brut_root), nas_path(nas_processing_root)]
    # On sépare les sources NAS et le projet local : leurs racines ne doivent pas se contenir l’une
    # l’autre.
    if any(root.is_relative_to(p) or p.is_relative_to(root) for p in roots):
        # On interrompt cette branche avec ValueError : 'Racines NAS et projet local ne doivent pas se
        # chevaucher.'.
        raise ValueError("Racines NAS et projet local ne doivent pas se chevaucher.")
    # On crée le dictionnaire vide pinned pour y ranger ensuite les éléments par clé.
    pinned = {}
    # On parcourt (EXTRACTOR, RECONCILER, HELPER) ; relative désigne l’élément courant à chaque passage
    # dans la boucle.
    for relative in (EXTRACTOR, RECONCILER, HELPER):
        # On garde dans path le chemin local après les contrôles de périmètre du module.
        path = local_path(root, root / relative, exists=True)
        # Cette branche traite le cas où la condition path.is_file() n’est pas remplie.
        if not path.is_file():
            # On interrompt cette branche avec ValueError : 'Source du pilote absente.'.
            raise ValueError("Source du pilote absente.")
        # On conserve l’empreinte sous forme de texte pour la comparer aux métadonnées attendues.
        pinned[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    # On appelle check_extractor_mode avec (root / EXTRACTOR).read_text(encoding='utf-8-sig').
    check_extractor_mode((root / EXTRACTOR).read_text(encoding="utf-8-sig"))
    # Conserver seulement la liste blanche technique, pas une copie de tous les secrets.
    seed = minimal_environment(
        root,
        # On passe la racine des données brutes explicitement, sans la deviner depuis le poste.
        nas_brut_root=nas_brut_root,
        # On passe séparément la racine des résultats de traitement.
        nas_processing_root=nas_processing_root,
        temp_dir=root / "data",
        parent=parent_environment,
    )

    def execute(command, project_root, log_path):
        # On vérifie ce cas avant la suite : Path(project_root).resolve() diffère de la racine locale
        # du projet.
        if Path(project_root).resolve() != root:
            # On interrompt cette branche avec ValueError : 'Executor appele pour un autre projet.'.
            raise ValueError("Executor appele pour un autre projet.")
        # On contrôle la commande préparée avant son lancement : seules les entrées et les options
        # prévues doivent passer vers le processus enfant.
        stage, log = validate_command(root, command, log_path)
        # On parcourt les couples (relative, digest) de pinned : on garde ensemble la clé et sa
        # valeur au lieu des traiter dans deux listes séparées.
        for relative, digest in pinned.items():
            # On compare l’empreinte des octets actuels à celle du lot attendu ; une différence doit
            # bloquer le mélange de versions.
            if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
                # On interrompt cette branche avec ValueError : 'Source modifiee apres preparation de l
                # executor ; arreter.'.
                raise ValueError(
                    "Source modifiee apres preparation de l executor ; arreter."
                )
        # On garde dans temp_dir le chemin local après les contrôles de périmètre du module.
        temp_dir = local_path(root, log.parent / "child_tmp" / log.stem)
        # On garde dans environment un nouveau dictionnaire construit avec les valeurs indiquées (la
        # copie reste superficielle).
        environment = dict(
            seed, TMPDIR=str(temp_dir), TEMP=str(temp_dir), TMP=str(temp_dir)
        )
        # Aucun ecrasement d'un log precedent ; toutes les sorties sont locales.
        descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        # On utilise os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') dans son contexte de
        # gestion ; les opérations de sortie sont exécutées en quittant le bloc.
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            # On prépare le dossier temp_dir avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            temp_dir.mkdir(parents=True, exist_ok=True)
            # On regroupe dans header ces champs nommés ; on pourra les retrouver par leur clé plutôt
            # que par leur position.
            header = {
                # On associe la clé 'executor' à cette valeur dans cet objet.
                "executor": "minimal_environment",
                # On renseigne l’étape concernée sous la clé 'stage'.
                "stage": stage,
                # On renseigne le délai maximal en secondes sous la clé 'timeout_seconds'.
                "timeout_seconds": timeout_seconds,
                # On associe la clé 'environment_keys' à cette valeur dans cet objet.
                "environment_keys": sorted(environment),
                # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
                "source_sha256": pinned,
            }
            # On écrit json.dumps(header, ensure_ascii=False) + '\n' dans handle ; le mode d’ouverture
            # du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
            handle.write(json.dumps(header, ensure_ascii=False) + "\n")
            # On vidu tampon d’écriture de handle vers sa destination ; cela ne remplace pas, à lui
            # seul, une synchronisation durable du fichier.
            handle.flush()
            # On démarre le processus enfant avec les paramètres contrôlés, sans construire ici une
            # commande de shell libre.
            process = subprocess.Popen(
                list(command),
                # On impose le dossier de travail du processus enfant ; les chemins relatifs ne
                # dépendent ainsi pas du terminal de départ.
                cwd=root,
                # On transmet cet environnement au processus plutôt que reprendre implicitement toutes
                # les variables du parent.
                env=environment,
                # On précise la source d’entrée du processus ; DEVNULL évite qu’il reste en attente
                # d’une saisie interactive.
                stdin=subprocess.DEVNULL,
                # On dirige la sortie normale vers la destination prévue pour les traces.
                stdout=handle,
                # On indique où envoyer les erreurs ; STDOUT les rassemble avec la sortie normale.
                stderr=subprocess.STDOUT,
                # Ce réglage décide si la commande passe par un shell ; avec False, la liste
                # d’arguments reste séparée.
                shell=False,
                # On choisit de fermer les descripteurs non nécessaires dans le processus enfant.
                close_fds=True,
            )
            # On tente ce bloc et on traite séparément les erreurs prévues : subprocess.TimeoutExpired,
            # BaseException.
            try:
                # On attend la fin du processus avec les paramètres indiqués ; son code de retour
                # sera contrôlé avant de poursuivre.
                return process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                # On appelle stop_child avec process.
                stop_child(process)
                # On interrompt cette branche avec NasChildTimeout : 'Delai du sous-processus depasse ;
                # processus arrete, journal local conserve.'.
                raise NasChildTimeout(
                    "Delai du sous-processus depasse ; processus arrete, journal local conserve."
                ) from None
            except BaseException:
                # On appelle stop_child avec process.
                stop_child(process)
                # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni
                # en fabriquer une autre.
                raise

    # On renvoie la fonction configurée, sans l’appeler. C’est l’étape du workflow qui décidera
    # quand exécuter cette commande.
    return execute
