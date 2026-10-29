# Lecture du fichier — Déclaration du DAG project12_eight_vineyards_business.
# Airflow tient le planning et le registre technique des exécutions. Les scripts appelés réalisent le
# travail ; les résultats métier et leur historique restent dans une autre base PostgreSQL.
#

"""Huit vignobles 2026 : traitement manuel explicite ou quotidien a 10 h, sans rattrapage tardif."""

# On rend disponibles timedelta depuis datetime, pour les appels de ce fichier.
from datetime import timedelta
# On décrit les DAG et leurs tâches ; les fonctions métier restent dans les modules Python appelés.
from airflow.sdk import dag, task, Param
# On fixe les règles de déclenchement et le fuseau de la programmation.
from airflow.timetables.trigger import CronTriggerTimetable
# On construit des dates compatibles avec la configuration temporelle d’Airflow.
import pendulum


# Ce DAG lance une seule tâche Airflow. À l’intérieur, le script Python enchaîne les huit étapes
# métier : on ne les confond pas avec huit tâches visibles dans Airflow.
@dag(
    # On donne au DAG un identifiant stable dans l’interface Airflow.
    dag_id="project12_eight_vineyards_business",
    # On prévoit un déclenchement chaque jour à 10 h, heure de Paris ; le fuseau gère le changement d’heure.
    schedule=CronTriggerTimetable(
        "0 10 * * *", timezone="Europe/Paris", run_immediately=False
    ),
    # On fixe la borne de départ du planning ; elle ne constitue pas une demande de rejouer tous
    # les jours précédents.
    start_date=pendulum.datetime(2026, 1, 1, tz="Europe/Paris"),
    # Avec False, on ne demande pas le rattrapage automatique de tous les intervalles manqués.
    catchup=False,
    # On limite le nombre de runs simultanés de ce DAG. Le verrou métier local apporte un contrôle
    # complémentaire, à un autre niveau.
    max_active_runs=1,
    # On limite les tâches actives dans ce DAG ; ce nombre n’est pas le nombre d’étapes du
    # workflow Python.
    max_active_tasks=1,
    # On borne la durée du run Airflow ; les processus appelés disposent aussi de leurs propres
    # délais.
    dagrun_timeout=timedelta(minutes=200),
    # On donne les paramètres communs aux tâches ; retries=0 évite ici une nouvelle tentative
    # automatique après échec.
    default_args={"retries": 0},
    # On définit les options attendues au déclenchement ; les adaptateurs les recontrôlent avant
    # d’autoriser les écritures métier.
    params={
        # On associe la clé 'scope_id' à cette valeur dans cet objet.
        "scope_id": Param(
            "eight_vineyards_2026_v1", type="string", enum=["eight_vineyards_2026_v1"]
        ),
        # On associe la clé 'allow_business_writes' à cette valeur dans cet objet.
        "allow_business_writes": Param(False, type="boolean"),
        # On associe la clé 'confirm_nas_read_only' à cette valeur dans cet objet.
        "confirm_nas_read_only": Param(False, type="boolean"),
    },
    tags=["projet12", "metier", "huit-vignobles", "manuel-et-programme"],
    description="DomaineDemoA, DomaineDemoB, DomaineDemoC, DomaineDemoD, DomaineDemoE, DomaineDemoF, DomaineDemoG, DomaineDemoH ; 2026 ; NAS RO.",
)
def project12_eight_vineyards_business():
    @task(execution_timeout=timedelta(minutes=190))
    def executer_workflow_huit_vignobles():
        # On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
        import sys
        # On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
        from pathlib import Path
        # On décrit les DAG et leurs tâches ; les fonctions métier restent dans les modules Python
        # appelés.
        from airflow.sdk import get_current_context

        # On garde dans scripts un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        scripts = Path("/opt/project/scripts")
        # Cette branche traite le cas où la condition (scripts / 'airflow_eight_task.py').is_file()
        # n’est pas remplie.
        if not (scripts / "airflow_eight_task.py").is_file():
            # On interrompt cette branche avec RuntimeError : 'Adaptateur huit vignobles absent ; aucun
            # lancement.'.
            raise RuntimeError("Adaptateur huit vignobles absent ; aucun lancement.")
        # On vérifie ce cas avant la suite : str(scripts) ne figure pas dans sys.path.
        if str(scripts) not in sys.path:
            # On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux
            # importables dans ce contexte.
            sys.path.insert(0, str(scripts))
        # On rend disponibles execute_eight depuis airflow_eight_task, pour les appels de ce fichier.
        from airflow_eight_task import execute_eight

        # On récupère get_current_context()['dag_run'] et on le garde dans run pour la suite.
        run = get_current_context()["dag_run"]
        # On fournit à l’appelant la valeur renvoyée par execute_eight.
        return execute_eight(
            getattr(run, "run_type", None),
            getattr(run, "conf", None),
            scheduled_for=getattr(run, "data_interval_end", None),
        )

    # On appelle executer_workflow_huit_vignobles sans argument positionnel.
    executer_workflow_huit_vignobles()


# On appelle project12_eight_vineyards_business sans argument positionnel.
project12_eight_vineyards_business()
