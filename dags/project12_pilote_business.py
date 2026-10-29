# Lecture du fichier — Déclaration du DAG project12_pilote_business.
# Airflow tient le planning et le registre technique des exécutions. Les scripts appelés réalisent le
# travail ; les résultats métier et leur historique restent dans une autre base PostgreSQL.
#

"""Premier workflow metier Airflow : manuel, DomaineDemoD, confirmations obligatoires."""

# On rend disponibles timedelta depuis datetime, pour les appels de ce fichier.
from datetime import timedelta
# On décrit les DAG et leurs tâches ; les fonctions métier restent dans les modules Python appelés.
from airflow.sdk import dag, task, Param
# On construit des dates compatibles avec la configuration temporelle d’Airflow.
import pendulum


@dag(
    # On donne au DAG un identifiant stable dans l’interface Airflow.
    dag_id="project12_pilote_business",
    # On laisse ce DAG sans calendrier automatique : son lancement doit être demandé explicitement.
    schedule=None,
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
    dagrun_timeout=timedelta(minutes=75),
    # On donne les paramètres communs aux tâches ; retries=0 évite ici une nouvelle tentative
    # automatique après échec.
    default_args={"retries": 0},
    # On définit les options attendues au déclenchement ; les adaptateurs les recontrôlent avant
    # d’autoriser les écritures métier.
    params={
        # On renseigne le domaine concerné sous la clé 'vineyard'.
        "vineyard": Param("DomaineDemoD", type="string", enum=["DomaineDemoD"]),
        # On associe la clé 'allow_business_writes' à cette valeur dans cet objet.
        "allow_business_writes": Param(False, type="boolean"),
        # On associe la clé 'confirm_nas_read_only' à cette valeur dans cet objet.
        "confirm_nas_read_only": Param(False, type="boolean"),
    },
    tags=["projet12", "metier", "pilote", "manuel"],
    description="Meme plan metier que le lancement local ; NAS RO ; aucune planification.",
)
def project12_pilote_business():
    @task(execution_timeout=timedelta(minutes=65))
    def executer_workflow_pilote():
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
        # Cette branche traite le cas où la condition (scripts / 'airflow_pilote_task.py').is_file()
        # n’est pas remplie.
        if not (scripts / "airflow_pilote_task.py").is_file():
            # On interrompt cette branche avec RuntimeError : 'Adaptateur metier absent ; aucun
            # lancement.'.
            raise RuntimeError("Adaptateur metier absent ; aucun lancement.")
        # On vérifie ce cas avant la suite : str(scripts) ne figure pas dans sys.path.
        if str(scripts) not in sys.path:
            # On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux
            # importables dans ce contexte.
            sys.path.insert(0, str(scripts))
        # On rend disponibles execute_pilote depuis airflow_pilote_task, pour les appels de ce fichier.
        from airflow_pilote_task import execute_pilote

        # On garde dans context la valeur renvoyée par get_current_context.
        context = get_current_context()
        # On récupère context['dag_run'] et on le garde dans run pour la suite.
        run = context["dag_run"]
        # La confirmation doit appartenir a cette tentative, pas a un defaut du DAG.
        return execute_pilote(
            getattr(run, "run_type", None), getattr(run, "conf", None)
        )

    # On appelle executer_workflow_pilote sans argument positionnel.
    executer_workflow_pilote()


# On appelle project12_pilote_business sans argument positionnel.
project12_pilote_business()
