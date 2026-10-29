# Lecture du fichier — Déclaration du DAG project12_airflow_smoke.
# Airflow tient le planning et le registre technique des exécutions. Les scripts appelés réalisent le
# travail ; les résultats métier et leur historique restent dans une autre base PostgreSQL.
#

"""DAG de vérification Airflow : aucune opération métier ni accès NAS."""

# On rend disponibles timedelta depuis datetime, pour les appels de ce fichier.
from datetime import timedelta

# On construit des dates compatibles avec la configuration temporelle d’Airflow.
import pendulum
# On décrit les DAG et leurs tâches ; les fonctions métier restent dans les modules Python appelés.
from airflow.sdk import dag, get_current_context, task


@dag(
    # On donne au DAG un identifiant stable dans l’interface Airflow.
    dag_id="project12_airflow_smoke",
    description="Test Airflow uniquement ; ne lance pas le pipeline métier.",
    # On prévoit un déclenchement chaque jour à 10 h, heure de Paris ; le fuseau gère le changement d’heure.
    schedule="0 10 * * *",
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
    dagrun_timeout=timedelta(minutes=5),
    # On donne les paramètres communs aux tâches ; retries=0 évite ici une nouvelle tentative
    # automatique après échec.
    default_args={"retries": 0},
    tags=["projet12", "test-sans-nas"],
)
def project12_airflow_smoke():
    @task
    def verifier_execution():
        # On garde dans context la valeur renvoyée par get_current_context.
        context = get_current_context()
        # On récupère context['dag_run'] et on le garde dans dag_run pour la suite.
        dag_run = context["dag_run"]
        # On affiche le texte 'Airflow execute correctement une tache Python.' dans la sortie du
        # programme.
        print("Airflow execute correctement une tache Python.")
        # On affiche f"Identifiant d'execution : {context['run_id']}" dans la sortie du programme.
        print(f"Identifiant d'execution : {context['run_id']}")
        # On affiche f'Type de declenchement Airflow : {dag_run.run_type}' dans la sortie du programme.
        print(f"Type de declenchement Airflow : {dag_run.run_type}")
        # On affiche f"Heure observee Paris : {pendulum.now('Europe/Paris').isoformat()}" dans la
        # sortie du programme.
        print(f"Heure observee Paris : {pendulum.now('Europe/Paris').isoformat()}")
        # On affiche le texte 'NAS : aucun acces. Base metier : aucune connexion.' dans la sortie du
        # programme.
        print("NAS : aucun acces. Base metier : aucune connexion.")
        # On affiche ce texte explicite dans la sortie du programme.
        print("Ce test ne valide ni le chargement metier ni son journal PostgreSQL.")

    # On appelle verifier_execution sans argument positionnel.
    verifier_execution()


# On appelle project12_airflow_smoke sans argument positionnel.
project12_airflow_smoke()
