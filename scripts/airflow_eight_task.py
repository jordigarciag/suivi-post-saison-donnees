# Lecture du fichier — Lien entre la tâche Airflow et le processus Python qui réalise le workflow.
# Airflow donne le départ et suit l’état de sa tâche ; le processus enfant exécute les étapes métier.
# On vérifie le reçu avant d’annoncer une réussite.
#

"""Adaptateur Airflow manuel ou programme du perimetre des huit vignobles ; aucun lancement a l'import."""

# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On gère les demandes d’interruption des processus lorsque la plateforme le permet.
import signal
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4
# On rend disponibles ROOT, BUSINESS_PYTHON, RUN_TIMEOUT, validate_trigger, result_from_receipt,
# require, EightControlError depuis airflow_eight_contract, pour les appels de ce fichier.
from airflow_eight_contract import (
    ROOT,
    BUSINESS_PYTHON,
    RUN_TIMEOUT,
    validate_trigger,
    result_from_receipt,
    require,
    EightControlError,
)


# On prépare et encadre le processus enfant du parcours complet, puis on contrôle son reçu.
def execute_eight(run_type, conf, scheduled_for=None):
    # On tente ce bloc et on traite séparément les erreurs prévues : EightControlError.
    try:
        # On vérifie si ce type de déclenchement est autorisé avant de préparer le moindre processus
        # métier.
        validate_trigger(run_type, conf, scheduled_for=scheduled_for)
    except EightControlError as exc:
        # On vérifie ce cas avant la suite : str(exc) correspond au texte
        # 'SCHEDULED_RUN_EXPIRED_NO_CATCHUP'.
        if str(exc) == "SCHEDULED_RUN_EXPIRED_NO_CATCHUP":
            # On rend disponibles AirflowSkipException depuis airflow.exceptions, pour les appels de ce
            # fichier.
            from airflow.exceptions import AirflowSkipException

            # On interrompt cette branche avec AirflowSkipException : 'Horaire depasse : aucun
            # rattrapage, aucun processus metier lance.'.
            raise AirflowSkipException(
                "Horaire depasse : aucun rattrapage, aucun processus metier lance."
            ) from None
        # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni en
        # fabriquer une autre.
        raise
    # Airflow peut fournir une valeur simple ou un objet portant value. On ramène les deux formes à
    # la même question : est-ce un run planifié ?
    scheduled = getattr(run_type, "value", run_type) == "scheduled"
    # On conserve l’origine du lancement dans le reçu ; un déclenchement manuel ne doit pas se faire
    # passer pour une exécution planifiée.
    mode = "airflow_scheduled" if scheduled else "airflow_manual"
    # Le lancement encadré utilise ici les groupes de processus Linux ; on ne prétend pas le rendre
    # équivalent sous Windows sans adaptation.
    require(os.name == "posix", "LINUX_EXECUTION_REQUIRED")
    # On exige cet interpréteur exécutable. Choisir un autre Python au hasard pourrait changer les
    # dépendances et le comportement du traitement.
    require(
        BUSINESS_PYTHON.is_file() and os.access(BUSINESS_PYTHON, os.X_OK),
        "BUSINESS_PYTHON_UNAVAILABLE_NO_FALLBACK",
    )
    # On rend disponibles child_environment, stop_group depuis airflow_pilote_task, pour les appels de
    # ce fichier.
    from airflow_pilote_task import child_environment, stop_group

    # On construit l’environnement autorisé du processus enfant au lieu de lui transmettre toutes
    # les variables Airflow, dont certaines sont sensibles.
    environment = child_environment(os.environ)
    # On construit script en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    script = ROOT / "scripts/run_airflow_eight_workflow.py"
    # Le script appelé doit exister avant de démarrer un processus ; on ne remplace pas cette entrée
    # par un autre lanceur.
    require(script.is_file(), "EIGHT_RUNNER_MISSING")
    # On construit folder en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    folder = ROOT / "logs/airflow_workflow"
    # Le dossier de traces doit exister et ne pas être redirigé ; on ne démarre pas un traitement
    # dont les traces partiraient ailleurs.
    require(
        folder.is_dir() and folder.resolve() == folder,
        "LOCAL_TASK_LOG_DIRECTORY_UNAVAILABLE",
    )
    # On assemble ces deux éléments pour construire stamp.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid4().hex
    # On construit log en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    log = folder / ("eight_child_" + stamp + ".log")
    # On construit receipt en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    receipt = folder / ("eight_execution_" + stamp + ".json")
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
    # Cette branche traite le cas où scheduled est évalué comme vrai.
    if scheduled:
        # On ajoute ['--trigger-mode', mode, '--scheduled-for', scheduled_for.isoformat()] à command et
        # on conserve ce nouvel état pour la suite.
        command += [
            "--trigger-mode",
            mode,
            "--scheduled-for",
            scheduled_for.isoformat(),
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
            # On écrit 'INTERPRETEUR ENFANT : ' + str(BUSINESS_PYTHON) + '\n' dans output ; le mode
            # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
            output.write("INTERPRETEUR ENFANT : " + str(BUSINESS_PYTHON) + "\n")
            # On écrit 'INTERPRETEUR PARENT AIRFLOW : ' + sys.executable + '\n' dans output ; le mode
            # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
            output.write("INTERPRETEUR PARENT AIRFLOW : " + sys.executable + "\n")
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
            # On attend la fin du processus, avec une limite de durée. Un dépassement lève une
            # exception et passe par la procédure d’arrêt, pas par une réussite implicite.
            code = process.wait(timeout=RUN_TIMEOUT)
        # Un code non nul signifie que le processus n’a pas confirmé sa fin normale ; on ne traite
        # donc pas sa sortie comme une réussite.
        require(code == 0, "EIGHT_CHILD_FAILED_NO_AUTOMATIC_RETRY")
        # On vérifie le contenu du reçu métier : le seul code de sortie du processus ne suffit pas à
        # confirmer toutes les étapes.
        result = result_from_receipt(
            json.loads(receipt.read_text(encoding="utf-8")),
            environment["PROJECT12_WORKFLOW_SHARE_ID"],
        )
        # L’origine annoncée dans le reçu doit être celle du lancement courant ; un ancien reçu
        # manuel ne valide pas un run planifié.
        require(result["trigger_mode"] == mode, "EIGHT_RECEIPT_TRIGGER_MODE_MISMATCH")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Workflow huit vignobles depuis Airflow : huit etapes confirmees ; perimetre approuve.",
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
                # On interrompt cette branche avec RuntimeError :
                # 'CHILD_STOP_NOT_CONFIRMED_CHECK_LOCAL_STATE'.
                raise RuntimeError(
                    "CHILD_STOP_NOT_CONFIRMED_CHECK_LOCAL_STATE"
                ) from None
        # On affiche le texte 'Execution non confirmee ; aucune relance automatique.' dans la sortie du
        # programme.
        print("Execution non confirmee ; aucune relance automatique.", flush=True)
        # On affiche 'Sortie locale : logs/airflow_workflow/' + log.name dans la sortie du programme.
        print("Sortie locale : logs/airflow_workflow/" + log.name, flush=True)
        # On interrompt cette branche avec RuntimeError : 'AIRFLOW_EIGHT_NOT_CONFIRMED'.
        raise RuntimeError("AIRFLOW_EIGHT_NOT_CONFIRMED") from None
    finally:
        # On remet le gestionnaire de signal d’origine, y compris après un échec : cette tâche ne
        # doit pas laisser ce réglage modifié.
        signal.signal(signal.SIGTERM, previous)
