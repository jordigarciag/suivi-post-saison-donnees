# Lecture du fichier — Adaptateur du parcours limité à un domaine et fonctions partagées avec le parcours principal.
# On encadre le processus enfant : environnement limité, délai d’attente, arrêt et contrôle du reçu.
# Le parcours principal réutilise notamment la préparation de l’environnement et l’arrêt du groupe.
#

"""Adaptateur de tache : enfant a environnement minimal, sortie brute locale, recu court."""

# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On gère les demandes d’interruption des processus lorsque la plateforme le permet.
import signal
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles UUID, uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import UUID, uuid4

# On garde dans IS_POSIX le résultat de cette comparaison : os.name correspond au texte 'posix'.
IS_POSIX = os.name == "posix"
# On garde dans ROOT un objet chemin local ; sa construction seule ne prouve pas que le fichier existe.
ROOT = Path("/opt/project")
# On garde dans BUSINESS_PYTHON un objet chemin local ; sa construction seule ne prouve pas que le
# fichier existe.
BUSINESS_PYTHON = Path("/home/airflow/.local/bin/python")
# On rassemble dans IMPORT_KEYS les 5 éléments explicitement indiqués, en conservant leur structure.
IMPORT_KEYS = (
    "PROJECT12_IMPORT_CONNECTION_MODE",
    "PROJECT12_IMPORT_HOST",
    "PROJECT12_IMPORT_PORT",
    "PROJECT12_IMPORT_USER",
    "PROJECT12_IMPORT_PASSWORD",
)
# On rassemble dans NAS_KEYS les 3 éléments explicitement indiqués, en conservant leur structure.
NAS_KEYS = ("PROJECT12_NAS_CONNECTION_MODE", "NAS_BRUT_ROOT", "NAS_PROCESSING_ROOT")
# On rassemble dans FLAGS les 2 éléments explicitement indiqués, en conservant leur structure.
FLAGS = ("PROJECT12_WORKFLOW_DOCKER", "PROJECT12_WORKFLOW_SHARE_ID")


class TaskControlError(RuntimeError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(ok, code):
    # On prévoit le cas où ok est évalué comme faux, par exemple une valeur vide selon son type.
    if not ok:
        # On interrompt cette branche avec TaskControlError.
        raise TaskControlError(code)


# On vérifie le type de déclenchement et les confirmations attendues avant d’autoriser la suite.
def validate_trigger(run_type, parameters):
    # Ce parcours attend un lancement manuel : on ne le laisse pas accepter un autre type de run par
    # défaut.
    require(getattr(run_type, "value", run_type) == "manual", "MANUAL_TRIGGER_REQUIRED")
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        isinstance(parameters, dict)
        # On exige aussi que parameters.get('vineyard') correspond au texte 'DomaineDemoD'.
        and parameters.get("vineyard") == "DomaineDemoD"
        # On exige aussi que parameters.get('allow_business_writes') est exactement la valeur vraie
        # (True).
        and parameters.get("allow_business_writes") is True
        # On exige aussi que parameters.get('confirm_nas_read_only') est exactement la valeur vraie
        # (True).
        and parameters.get("confirm_nas_read_only") is True,
        "EXPLICIT_PILOTE_CONFIRMATIONS_REQUIRED",
    )


# On transmet seulement les variables nécessaires au processus enfant, pas tout l’environnement du
# parent.
def child_environment(parent):
    # On assemble ces deux éléments pour construire keys.
    keys = IMPORT_KEYS + NAS_KEYS + FLAGS
    # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        all(
            isinstance(parent.get(k), str)
            and parent[k]
            # On exige aussi que la condition any((c in parent[k] for c in '\x00\r\n')) n’est pas
            # remplie.
            and not any(c in parent[k] for c in "\x00\r\n")
            for k in keys
        ),
        "CHILD_CONFIGURATION_INCOMPLETE",
    )
    # Dans le conteneur, les connexions doivent venir de l’environnement explicite ; le .env du
    # poste ne doit pas servir de solution de repli.
    require(
        parent[IMPORT_KEYS[0]] == "environment"
        # On exige aussi que parent[NAS_KEYS[0]] correspond au texte 'environment'.
        and parent[NAS_KEYS[0]] == "environment",
        "ENVIRONMENT_MODES_REQUIRED",
    )
    # On exige ici que parent['PROJECT12_IMPORT_USER'] correspond au texte 'projet12_importer' et
    # parent['PROJECT12_WORKFLOW_DOCKER'] correspond au texte '1'. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        parent["PROJECT12_IMPORT_USER"] == "projet12_importer"
        # On exige aussi que parent['PROJECT12_WORKFLOW_DOCKER'] correspond au texte '1'.
        and parent["PROJECT12_WORKFLOW_DOCKER"] == "1",
        "IMPORTER_AND_DOCKER_REQUIRED",
    )
    # On exige ici que (parent['NAS_BRUT_ROOT'], parent['NAS_PROCESSING_ROOT']) correspond à
    # ('/opt/nas/brute_v2025', '/opt/nas/data_processing_2025'). Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        (parent["NAS_BRUT_ROOT"], parent["NAS_PROCESSING_ROOT"])
        == ("/opt/nas/brute_v2025", "/opt/nas/data_processing_2025"),
        "NAS_CONTAINER_ROOTS_REQUIRED",
    )
    # On appelle UUID avec parent['PROJECT12_WORKFLOW_SHARE_ID'].
    UUID(parent["PROJECT12_WORKFLOW_SHARE_ID"])
    # On indexe le résultat par k, avec parent[k] comme valeur ; les contrôles d’unicité sont
    # importants car une même clé ne garde qu’une valeur dans un dictionnaire.
    result = {k: parent[k] for k in keys}
    # On complète result avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle valeur
    # fournie.
    result.update(
        PYTHONPATH=str(ROOT / "src"),
        PYTHONNOUSERSITE="1",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        PYTHONUNBUFFERED="1",
        PYTHONDONTWRITEBYTECODE="1",
        TMPDIR="/tmp",
        TEMP="/tmp",
        TMP="/tmp",
    )
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On tente d’arrêter le groupe de processus pour ne pas oublier un descendant encore actif.
def stop_group(process):
    # Le PID du chef peut etre termine alors qu'un descendant NAS est encore vivant.
    try:
        # On envoie le signal au groupe du processus pour ne pas viser seulement le parent et
        # laisser ses enfants poursuivre.
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont pas
        # exécutées.
        return
    # On tente ce bloc et on traite séparément les erreurs prévues : subprocess.TimeoutExpired.
    try:
        # On appelle process.wait sans argument positionnel.
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
        pass
    # On tente ce bloc et on traite séparément les erreurs prévues : ProcessLookupError.
    try:
        # On appelle os.killpg avec process.pid.
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
        pass
    # On attend la fin du processus avec les paramètres indiqués ; son code de retour sera contrôlé
    # avant de poursuivre.
    process.wait(timeout=5)


# On extrait seulement les informations du reçu qui respectent le contrat attendu.
def receipt_result(path, environment):
    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    data = json.loads(path.read_text(encoding="utf-8"))
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        data.get("kind") == "execution"
        # On exige aussi que data.get('status') correspond au texte 'success'.
        and data.get("status") == "success"
        # On exige aussi que data.get('trigger_mode') correspond au texte 'airflow_manual'.
        and data.get("trigger_mode") == "airflow_manual"
        # On exige aussi que data.get('completed_steps') correspond à 8.
        and data.get("completed_steps") == 8
        # On exige aussi que data.get('share_id') correspond à
        # environment['PROJECT12_WORKFLOW_SHARE_ID'].
        and data.get("share_id") == environment["PROJECT12_WORKFLOW_SHARE_ID"],
        "EXECUTION_RECEIPT_NOT_SUCCESS",
    )
    # On garde dans workflow_id la représentation textuelle de UUID(data['workflow_execution_id']).
    workflow_id = str(UUID(data["workflow_execution_id"]))
    # On assemble ces deux éléments pour construire expected.
    expected = (
        "data/03_normalized/workflow_runs/" + UUID(workflow_id).hex + "/events.jsonl"
    )
    # On exige ici que data.get('journal_relative_path') correspond au résultat attendu. Si ce n’est
    # pas le cas, le message associé bloque la suite.
    require(
        data.get("journal_relative_path") == expected, "EXECUTION_JOURNAL_PATH_MISMATCH"
    )
    # On remet {key: data[key] for key in ('workflow_execution_id', 'status', 'completed… à l’appelant
    # ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return {
        key: data[key]
        for key in (
            "workflow_execution_id",
            "status",
            "completed_steps",
            "journal_relative_path",
            "excel_publication_id",
            "pipeline_execution_id",
            "trigger_mode",
        )
    }


# On prépare et encadre le processus du périmètre pilote, puis on contrôle le résultat confirmé.
def execute_pilote(run_type, parameters):
    # On vérifie si ce type de déclenchement est autorisé avant de préparer le moindre processus
    # métier.
    validate_trigger(run_type, parameters)
    # Le lancement encadré utilise ici les groupes de processus Linux ; on ne prétend pas le rendre
    # équivalent sous Windows sans adaptation.
    require(IS_POSIX, "LINUX_EXECUTION_REQUIRED")
    # On exige cet interpréteur exécutable. Choisir un autre Python au hasard pourrait changer les
    # dépendances et le comportement du traitement.
    require(
        BUSINESS_PYTHON.is_file() and os.access(BUSINESS_PYTHON, os.X_OK),
        "BUSINESS_PYTHON_UNAVAILABLE_NO_FALLBACK",
    )
    # On construit l’environnement autorisé du processus enfant au lieu de lui transmettre toutes
    # les variables Airflow, dont certaines sont sensibles.
    environment = child_environment(os.environ)
    # On construit script en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    script = ROOT / "scripts/run_airflow_pilote_workflow.py"
    # On exige ici que script désigne un fichier. Si ce n’est pas le cas, le message associé bloque la
    # suite.
    require(script.is_file(), "AIRFLOW_BUSINESS_RUNNER_MISSING")
    # On assemble ces deux éléments pour construire stamp.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid4().hex
    # On construit folder en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    folder = ROOT / "logs/airflow_workflow"
    # Le dossier de traces doit exister et ne pas être redirigé ; on ne démarre pas un traitement
    # dont les traces partiraient ailleurs.
    require(
        folder.is_dir() and folder.resolve() == folder,
        "LOCAL_TASK_LOG_DIRECTORY_UNAVAILABLE",
    )
    # On construit log en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    log = folder / ("child_" + stamp + ".log")
    # On construit receipt en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    receipt = folder / ("execution_" + stamp + ".json")
    # On rassemble dans command les 7 éléments explicitement indiqués, en conservant leur structure.
    command = [
        str(BUSINESS_PYTHON),
        str(script),
        "--run",
        "--allow-business-writes",
        "--confirm-nas-read-only",
        "--receipt",
        str(receipt),
    ]
    # Le processus n’existe pas encore. Ce repère évite de tenter son arrêt si le lancement échoue
    # avant sa création.
    process = None
    # On gardu comportement précédent du signal d’arrêt pour le rétablir à la sortie de la tâche.
    previous = signal.getsignal(signal.SIGTERM)

    # On traite l’interruption pour ne pas laisser le processus enfant poursuivre sans son parent.
    def interrupted(signum, frame):
        # On interrompt cette branche avec InterruptedError : 'AIRFLOW_TASK_INTERRUPTED'.
        raise InterruptedError("AIRFLOW_TASK_INTERRUPTED")

    # On transforme la demande d’arrêt en interruption Python ; le bloc de nettoyage pourra alors
    # tenter d’arrêter aussi le processus enfant.
    signal.signal(signal.SIGTERM, interrupted)
    # On tente ce bloc et on traite séparément les erreurs prévues : BaseException.
    try:
        # On ouvre le fichier en création exclusive : s’il existe déjà, on s’arrête au lieu de
        # l’écraser. Le bloc ferme le fichier à la sortie.
        with log.open("x", encoding="utf-8") as output:
            # Metadonnees techniques seulement ; aucun environnement ni secret.
            output.write("INTERPRETEUR ENFANT : " + str(BUSINESS_PYTHON) + "\n")
            # On écrit 'INTERPRETEUR PARENT AIRFLOW : ' + sys.executable + '\n' dans output ; le mode
            # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
            output.write("INTERPRETEUR PARENT AIRFLOW : " + sys.executable + "\n")
            # On écrit 'VERSION PYTHON PARENT : ' + sys.version.split()[0] + '\n' dans output ; le mode
            # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
            output.write("VERSION PYTHON PARENT : " + sys.version.split()[0] + "\n")
            # On pousse les premières lignes vers le fichier de sortie sans attendre la fin du
            # traitement ; elles seront utiles si le processus s’arrête tôt.
            output.flush()
            # On démarre le processus enfant avec les paramètres contrôlés, sans construire ici une
            # commande de shell libre.
            process = subprocess.Popen(
                command,
                # On impose le dossier de travail du processus enfant ; les chemins relatifs ne
                # dépendent ainsi pas du terminal de départ.
                cwd=ROOT,
                # On transmet cet environnement au processus plutôt que reprendre implicitement toutes
                # les variables du parent.
                env=environment,
                # Ce réglage décide si la commande passe par un shell ; avec False, la liste
                # d’arguments reste séparée.
                shell=False,
                # On précise la source d’entrée du processus ; DEVNULL évite qu’il reste en attente
                # d’une saisie interactive.
                stdin=subprocess.DEVNULL,
                # On dirige la sortie normale vers la destination prévue pour les traces.
                stdout=output,
                # On indique où envoyer les erreurs ; STDOUT les rassemble avec la sortie normale.
                stderr=subprocess.STDOUT,
                # On choisit de fermer les descripteurs non nécessaires dans le processus enfant.
                close_fds=True,
                # On peut ainsi isoler le groupe de processus pour gérer ensuite son interruption.
                start_new_session=True,
            )
            # On attend la fin du processus avec les paramètres indiqués ; son code de retour sera
            # contrôlé avant de poursuivre.
            code = process.wait(timeout=3600)
        # Un code non nul signifie que le processus n’a pas confirmé sa fin normale ; on ne traite
        # donc pas sa sortie comme une réussite.
        require(code == 0, "WORKFLOW_CHILD_FAILED_NO_AUTOMATIC_RETRY")
        # On garde dans result la valeur renvoyée par receipt_result.
        result = receipt_result(receipt, environment)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Workflow DomaineDemoD depuis Airflow : huit etapes confirmees ; aucune sortie brute transmise en XCom.",
            flush=True,
        )
        # On affiche 'Workflow : ' + result['workflow_execution_id'] dans la sortie du programme.
        print("Workflow : " + result["workflow_execution_id"], flush=True)
        # On affiche 'Journal : ' + result['journal_relative_path'] dans la sortie du programme.
        print("Journal : " + result["journal_relative_path"], flush=True)
        # On affiche 'Recu local : logs/airflow_workflow/' + receipt.name dans la sortie du programme.
        print("Recu local : logs/airflow_workflow/" + receipt.name, flush=True)
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result
    except BaseException:
        # On vérifie ce cas avant la suite : le processus enfant est renseigné (différent de None).
        if process is not None:
            # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
            try:
                # On appelle stop_group avec process.
                stop_group(process)
            except Exception:
                # On interrompt cette branche avec TaskControlError :
                # 'CHILD_STOP_NOT_CONFIRMED_CHECK_LOCAL_STATE'.
                raise TaskControlError(
                    "CHILD_STOP_NOT_CONFIRMED_CHECK_LOCAL_STATE"
                ) from None
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Tache non confirmee ; examiner le journal et la sortie locale, sans relance automatique.",
            flush=True,
        )
        # On affiche 'Sortie locale : logs/airflow_workflow/' + log.name dans la sortie du programme.
        print("Sortie locale : logs/airflow_workflow/" + log.name, flush=True)
        # Pas de sortie brute ou message d'exception externe pouvant contenir un secret.
        raise TaskControlError("AIRFLOW_PILOTE_NOT_CONFIRMED") from None
    finally:
        # On remet le gestionnaire de signal d’origine, y compris après un échec : cette tâche ne
        # doit pas laisser ce réglage modifié.
        signal.signal(signal.SIGTERM, previous)
