# Lecture du fichier — Déclaration du DAG project12_import_connection_check.
# Airflow tient le planning et le registre technique des exécutions. Les scripts appelés réalisent le
# travail ; les résultats métier et leur historique restent dans une autre base PostgreSQL.
#

"""Controle manuel de connexion importeur ; aucun chargement metier ni acces NAS."""

# On rend disponibles timedelta depuis datetime, pour les appels de ce fichier.
from datetime import timedelta
# On décrit les DAG et leurs tâches ; les fonctions métier restent dans les modules Python appelés.
from airflow.sdk import dag, task
# On construit des dates compatibles avec la configuration temporelle d’Airflow.
import pendulum


@dag(
    # On donne au DAG un identifiant stable dans l’interface Airflow.
    dag_id="project12_import_connection_check",
    description="Controle PostgreSQL importeur depuis Airflow, sans ecriture metier.",
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
    dagrun_timeout=timedelta(minutes=5),
    # On donne les paramètres communs aux tâches ; retries=0 évite ici une nouvelle tentative
    # automatique après échec.
    default_args={"retries": 0},
    tags=["projet12", "connexion-importeur", "controle-sans-chargement"],
)
def project12_import_connection_check():
    @task(execution_timeout=timedelta(minutes=3))
    def verifier_connexion_importeur():
        # On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
        import os
        # On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
        from pathlib import Path
        # On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours
        # l’exige.
        import subprocess
        # On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
        import sys

        # On garde dans script un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        script = Path("/opt/project/scripts/check_import_connection.py")
        # Cette branche traite le cas où la condition script.is_file() n’est pas remplie.
        if not script.is_file():
            # On interrompt cette branche avec RuntimeError : 'Script de controle absent du montage
            # scripts en lecture seule.'.
            raise RuntimeError(
                "Script de controle absent du montage scripts en lecture seule."
            )
        # On rassemble dans variables les 5 éléments explicitement indiqués, en conservant leur
        # structure.
        variables = (
            "PROJECT12_IMPORT_CONNECTION_MODE",
            "PROJECT12_IMPORT_HOST",
            "PROJECT12_IMPORT_PORT",
            "PROJECT12_IMPORT_USER",
            "PROJECT12_IMPORT_PASSWORD",
        )
        # Cette branche traite le cas où au moins un élément satisfait le test indiqué.
        if any(not os.environ.get(key) for key in variables):
            # On interrompt cette branche avec RuntimeError.
            raise RuntimeError(
                "Configuration importeur incomplete dans le service d execution ; aucun repli vers .env."
            )
        # On vérifie ce cas avant la suite : os.environ['PROJECT12_IMPORT_CONNECTION_MODE'] diffère de
        # le texte 'environment'.
        if os.environ["PROJECT12_IMPORT_CONNECTION_MODE"] != "environment":
            # On interrompt cette branche avec RuntimeError : 'Mode environment requis pour ce controle
            # Docker.'.
            raise RuntimeError("Mode environment requis pour ce controle Docker.")
        # On indexe environment par key ; chaque clé sera associée à os.environ[key]. Une même clé ne
        # peut garder qu’une valeur.
        environment = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "LANG", "LC_ALL", "TZ") + variables
            if key in os.environ
        }
        # On complète environment avec les valeurs indiquées ; une clé déjà présente prendra la
        # nouvelle valeur fournie.
        environment.update(
            PYTHONUNBUFFERED="1",
            PYTHONIOENCODING="utf-8",
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONUTF8="1",
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Controle importeur depuis une vraie tache Airflow ; aucun chargement metier.",
            flush=True,
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Sous-processus : seuls les parametres importeur et les variables techniques necessaires sont transmis.",
            flush=True,
        )
        # On tente ce bloc et on traite séparément les erreurs prévues : subprocess.TimeoutExpired.
        try:
            # On lance la commande puis on récupère son résultat ; son code de sortie sera interprété
            # par la suite.
            completed = subprocess.run(
                [sys.executable, str(script), "--project-root", "/opt/project"],
                # On impose le dossier de travail du processus enfant ; les chemins relatifs ne
                # dépendent ainsi pas du terminal de départ.
                cwd="/tmp",
                # On transmet cet environnement au processus plutôt que reprendre implicitement toutes
                # les variables du parent.
                env=environment,
                # On dirige la sortie normale vers la destination prévue pour les traces.
                stdout=subprocess.PIPE,
                # On indique où envoyer les erreurs ; STDOUT les rassemble avec la sortie normale.
                stderr=subprocess.STDOUT,
                # On fournit le texte de travail via le paramètre text de cet appel.
                text=True,
                # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas
                # être décodé selon un réglage implicite du poste.
                encoding="utf-8",
                # On définit ce que la conversion fera des valeurs invalides, au lieu de laisser ce cas
                # implicite.
                errors="replace",
                # On borne la durée d’attente de cet appel ; dépasser ce délai ne vaut pas confirmation
                # de réussite.
                timeout=120,
                # Ce réglage décide si un code de sortie non nul lève directement une exception dans
                # cet appel.
                check=False,
            )
        except subprocess.TimeoutExpired:
            # On interrompt cette branche avec RuntimeError.
            raise RuntimeError(
                "Controle interrompu apres 120 secondes ; aucun chargement lance. Verifier la disponibilite PostgreSQL."
            ) from None
        # On garde dans output le résultat du remplacement demandé sur completed.stdout or ''.
        output = (completed.stdout or "").replace(
            environment["PROJECT12_IMPORT_PASSWORD"], "[secret masque]"
        )
        # On affiche la sortie préparée dans la sortie du programme.
        print(output, flush=True)
        # On vérifie ce cas avant la suite : completed.returncode diffère de 0.
        if completed.returncode != 0:
            # On interrompt cette branche avec RuntimeError.
            raise RuntimeError(
                f"Controle importeur en echec : code {completed.returncode}. Lire les journaux, ne pas elargir les droits."
            )
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT : connexion et permissions importeur verifiees depuis Airflow.",
            flush=True,
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Aucune ecriture metier ; verrous temporaires liberes par le controle. Aucun acces NAS.",
            flush=True,
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Le pipeline complet, les chargements et le raccordement du journal restent a valider.",
            flush=True,
        )
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {"check": "import_connection", "status": "success"}

    # On appelle verifier_connexion_importeur sans argument positionnel.
    verifier_connexion_importeur()


# On appelle project12_import_connection_check sans argument positionnel.
project12_import_connection_check()
