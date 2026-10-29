# Lecture du fichier — Déclaration du DAG project12_excel_synthetic.
# Airflow tient le planning et le registre technique des exécutions. Les scripts appelés réalisent le
# travail ; les résultats métier et leur historique restent dans une autre base PostgreSQL.
#

"""Essai manuel Excel depuis Airflow : 37 tests synthétiques, aucun accès métier."""

# On rend disponibles timedelta depuis datetime, pour les appels de ce fichier.
from datetime import timedelta

# On décrit les DAG et leurs tâches ; les fonctions métier restent dans les modules Python appelés.
from airflow.sdk import dag, task
# On construit des dates compatibles avec la configuration temporelle d’Airflow.
import pendulum


@dag(
    # On donne au DAG un identifiant stable dans l’interface Airflow.
    dag_id="project12_excel_synthetic",
    description="37 tests Excel synthétiques depuis Airflow ; aucun chargement métier.",
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
    dagrun_timeout=timedelta(minutes=10),
    # On donne les paramètres communs aux tâches ; retries=0 évite ici une nouvelle tentative
    # automatique après échec.
    default_args={"retries": 0},
    tags=["projet12", "excel-synthetique", "test-sans-nas"],
)
def project12_excel_synthetic():
    @task(execution_timeout=timedelta(minutes=6))
    def verifier_ingestion_excel_synthetique():
        # On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
        import os
        # On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
        from pathlib import Path
        # On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours
        # l’exige.
        import subprocess
        # On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
        import sys
        # On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
        import tempfile

        # On garde dans launcher un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        launcher = Path("/opt/project-test-tools/run_excel_tests_isolated.py")
        # Cette branche traite le cas où la condition launcher.is_file() n’est pas remplie.
        if not launcher.is_file():
            # On interrompt cette branche avec RuntimeError : 'Lanceur absent : utiliser l image metier
            # reconstruite apres la correction.'.
            raise RuntimeError(
                "Lanceur absent : utiliser l image metier reconstruite apres la correction."
            )
        # On parcourt ('/opt/project/src/suivi_traitements_post_saison/ingestion/excel_reader.p… ;
        # expected désigne l’élément courant à chaque passage dans la boucle.
        for expected in (
            "/opt/project/src/suivi_traitements_post_saison/ingestion/excel_reader.py",
            "/opt/project/tests/test_tracking_versioning.py",
        ):
            # Cette branche traite le cas où la condition Path(expected).is_file() n’est pas remplie.
            if not Path(expected).is_file():
                # On interrompt cette branche avec RuntimeError : 'Code ou tests absents du montage en
                # lecture seule.'.
                raise RuntimeError("Code ou tests absents du montage en lecture seule.")

        # Ne pas transmettre les variables de connexion Airflow au sous-processus.
        environment = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "LANG", "LC_ALL", "TZ")
            if key in os.environ
        }
        # On complète environment avec les valeurs indiquées ; une clé déjà présente prendra la
        # nouvelle valeur fournie.
        environment.update(
            PYTHONUNBUFFERED="1",
            PYTHONIOENCODING="utf-8",
            PYTHONDONTWRITEBYTECODE="1",
        )
        # On affiche le texte 'Essai Excel depuis une vraie tache Airflow.' dans la sortie du
        # programme.
        print("Essai Excel depuis une vraie tache Airflow.", flush=True)
        # On affiche ce texte explicite dans la sortie du programme.
        print(
            "Excel fictifs ; aucun montage data/config/state du projet Windows.",
            flush=True,
        )
        # On affiche le texte 'Aucune connexion a la base metier ; aucun acces au NAS.' dans la sortie
        # du programme.
        print("Aucune connexion a la base metier ; aucun acces au NAS.", flush=True)
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory(
            prefix="project12-airflow-excel-"
        ) as directory:
            # On garde directory sous le nom environment['TMPDIR'] ; cette affectation ne copie pas à
            # elle seule un objet mutable.
            environment["TMPDIR"] = directory
            # On lance la commande puis on récupère son résultat ; son code de sortie sera interprété
            # par la suite.
            completed = subprocess.run(
                [sys.executable, str(launcher)],
                # On impose le dossier de travail du processus enfant ; les chemins relatifs ne
                # dépendent ainsi pas du terminal de départ.
                cwd=directory,
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
                timeout=300,
                # Ce réglage décide si un code de sortie non nul lève directement une exception dans
                # cet appel.
                check=False,
            )
            # On affiche completed.stdout dans la sortie du programme.
            print(completed.stdout, flush=True)
            # On vérifie ce cas avant la suite : completed.returncode diffère de 0.
            if completed.returncode != 0:
                # On interrompt cette branche avec RuntimeError.
                raise RuntimeError(
                    f"Suite Excel en echec : code de sortie {completed.returncode}. Lire les journaux de cette tache."
                )
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT : suite Excel reussie depuis Airflow ; fichiers temporaires nettoyes.",
            flush=True,
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Ce test ne valide pas encore le pipeline complet, sa programmation ou le journal metier.",
            flush=True,
        )
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {"test_suite": "test_tracking_versioning", "status": "success"}

    # On appelle verifier_ingestion_excel_synthetique sans argument positionnel.
    verifier_ingestion_excel_synthetique()


# On appelle project12_excel_synthetic sans argument positionnel.
project12_excel_synthetic()
