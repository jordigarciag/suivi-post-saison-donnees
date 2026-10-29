# Lecture du fichier — Tests de airflow import connection task.
#

"""Tests simules du corps de tache, sans installer Airflow ni contacter PostgreSQL."""

# On importe ast. On analyse la structure du code Python sans exécuter le texte analysé.
import ast
# On importe contextlib. Ce module sera utilisé par les opérations de ce fichier.
import contextlib
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On rend disponibles SimpleNamespace depuis types, pour les appels de ce fichier.
from types import SimpleNamespace
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch

# On assemble les morceaux du chemin DAG_PATH avec l’opérateur / de pathlib ; aucun fichier n’est créé
# par cette construction.
DAG_PATH = (
    Path(__file__).resolve().parents[2]
    / "dags"
    / "project12_import_connection_check.py"
)


def load_task_body():
    # On garde dans tree la valeur renvoyée par ast.parse.
    tree = ast.parse(DAG_PATH.read_text(encoding="utf-8"))
    # On garde dans factory le prochain élément de (n for n in tree.body if isinstance(n,
    # ast.FunctionDef)).
    factory = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    # On garde dans task le prochain élément de (n for n in factory.body if isinstance(n,
    # ast.FunctionDef)).
    task = next(n for n in factory.body if isinstance(n, ast.FunctionDef))
    # On prépare task.decorator_list comme liste vide ; on la remplira au fil des opérations suivantes.
    task.decorator_list = []
    # On crée le dictionnaire vide namespace pour y ranger ensuite les éléments par clé.
    namespace = {}
    # On appelle exec avec compile(ast.fix_missing_locations(ast.Module(body=[task], type_ignores=[])),
    # str(DAG_PATH….
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[task], type_ignores=[])),
            str(DAG_PATH),
            "exec",
        ),
        namespace,
    )
    # On remet namespace[task.name] à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return namespace[task.name]


class TestAirflowImportConnectionTask(unittest.TestCase):
    def setUp(self):
        # On garde dans self.task la valeur renvoyée par load_task_body.
        self.task = load_task_body()
        # On regroupe dans self.env ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        self.env = {
            # On associe la clé 'PATH' à cette valeur dans les données de ce scénario.
            "PATH": "synthetic-path",
            # On associe la clé 'HOME' à cette valeur dans les données de ce scénario.
            "HOME": "/tmp",
            # On associe la clé 'TZ' à cette valeur dans les données de ce scénario.
            "TZ": "Europe/Paris",
            # On associe la clé 'PROJECT12_IMPORT_CONNECTION_MODE' à cette valeur dans les données de
            # ce scénario.
            "PROJECT12_IMPORT_CONNECTION_MODE": "environment",
            # On associe la clé 'PROJECT12_IMPORT_HOST' à cette valeur dans les données de ce scénario.
            "PROJECT12_IMPORT_HOST": "projet12-suivi-postgres-1",
            # On associe la clé 'PROJECT12_IMPORT_PORT' à cette valeur dans les données de ce scénario.
            "PROJECT12_IMPORT_PORT": "5432",
            # On associe la clé 'PROJECT12_IMPORT_USER' à cette valeur dans les données de ce scénario.
            "PROJECT12_IMPORT_USER": "projet12_importer",
            # On associe la clé 'PROJECT12_IMPORT_PASSWORD' à cette valeur dans les données de ce
            # scénario.
            "PROJECT12_IMPORT_PASSWORD": "synthetic-import-secret",
            # On associe la clé 'AIRFLOW__DATABASE__SQL_ALCHEMY_CONN' à cette valeur dans les données
            # de ce scénario.
            "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN": "synthetic-airflow-secret",
            # On associe la clé 'AIRFLOW__API_AUTH__JWT_SECRET' à cette valeur dans les données de ce
            # scénario.
            "AIRFLOW__API_AUTH__JWT_SECRET": "synthetic-jwt-secret",
            # On associe la clé 'PROJECT12_POSTGRES_PASSWORD' à cette valeur dans les données de ce
            # scénario.
            "PROJECT12_POSTGRES_PASSWORD": "synthetic-admin-secret",
            # On associe la clé 'PROJECT12_DASHBOARD_PASSWORD' à cette valeur dans les données de ce
            # scénario.
            "PROJECT12_DASHBOARD_PASSWORD": "synthetic-reader-secret",
            # On associe la clé 'PYTHONPATH' à cette valeur dans les données de ce scénario.
            "PYTHONPATH": "/should-not-be-forwarded",
        }
        # On garde dans guard la valeur renvoyée par patch.dict.
        guard = patch.dict(os.environ, self.env, clear=True)
        # On appelle guard.start sans argument positionnel.
        guard.start()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(guard.stop)

    def test_manual_only_and_no_retries(self):
        # On garde dans tree la valeur renvoyée par ast.parse.
        tree = ast.parse(DAG_PATH.read_text(encoding="utf-8"))
        # On garde dans factory le prochain élément de (n for n in tree.body if isinstance(n,
        # ast.FunctionDef)).
        factory = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
        # On indexe options par k.arg ; chaque clé sera associée à k.value. Une même clé ne peut garder
        # qu’une valeur.
        options = {k.arg: k.value for k in factory.decorator_list[0].keywords}
        # On attend None pour ast.literal_eval(options['schedule']) : aucune valeur n’est confirmée
        # dans ce cas.
        self.assertIsNone(ast.literal_eval(options["schedule"]))
        # On attend que ast.literal_eval(options['catchup']) soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(ast.literal_eval(options["catchup"]))
        # On vérifie que ast.literal_eval(options['max_active_runs']) correspond à 1.
        self.assertEqual(ast.literal_eval(options["max_active_runs"]), 1)
        # On vérifie que ast.literal_eval(options['max_active_tasks']) correspond à 1.
        self.assertEqual(ast.literal_eval(options["max_active_tasks"]), 1)
        # On vérifie que ast.literal_eval(options['default_args']) correspond à {'retries': 0}.
        self.assertEqual(ast.literal_eval(options["default_args"]), {"retries": 0})

    def test_success_uses_existing_checker_without_forwarding_other_secrets(self):
        # On remplace temporairement Path dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(Path, "is_file", return_value=True),
            patch(
                "subprocess.run",
                # On fixe la réponse de ce double de test ; aucune vraie opération de la dépendance
                # n’est nécessaire pour obtenir cette valeur.
                return_value=SimpleNamespace(stdout="RESULTAT OK", returncode=0),
            ) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            # On garde dans result la valeur renvoyée par self.task.
            result = self.task()
        # On vérifie que result correspond à {'check': 'import_connection', 'status': 'success'}.
        self.assertEqual(result, {"check": "import_connection", "status": "success"})
        # On récupère run.call_args.args[0] et on le garde dans command pour la suite.
        command = run.call_args.args[0]
        # La tache est simulee dans l OS du test : Path rend des separateurs
        # Windows sur le PC, POSIX dans le conteneur Linux.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            command[1:],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            [
                str(Path("/opt/project/scripts/check_import_connection.py")),
                "--project-root",
                "/opt/project",
            ],
        )
        # On récupère run.call_args.kwargs['env'] et on le garde dans passed pour la suite.
        passed = run.call_args.kwargs["env"]
        # On vérifie que passed['PROJECT12_IMPORT_PASSWORD'] correspond à 'synthetic-import-secret'.
        self.assertEqual(passed["PROJECT12_IMPORT_PASSWORD"], "synthetic-import-secret")
        # On parcourt ('AIRFLOW__DATABASE__SQL_ALCHEMY_CONN', 'AIRFLOW__API_AUTH__JWT_SECRET',… ;
        # forbidden désigne l’élément courant de ce scénario.
        for forbidden in (
            "AIRFLOW__DATABASE__SQL_ALCHEMY_CONN",
            "AIRFLOW__API_AUTH__JWT_SECRET",
            "PROJECT12_POSTGRES_PASSWORD",
            "PROJECT12_DASHBOARD_PASSWORD",
            "PYTHONPATH",
        ):
            # On vérifie que forbidden ne figure pas dans passed.
            self.assertNotIn(forbidden, passed)
        # On vérifie que run.call_args.kwargs['timeout'] correspond à 120.
        self.assertEqual(run.call_args.kwargs["timeout"], 120)
        # On vérifie que run.call_args.kwargs['cwd'] correspond à '/tmp'.
        self.assertEqual(run.call_args.kwargs["cwd"], "/tmp")

    def test_missing_script_rejected(self):
        # On remplace temporairement Path dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(Path, "is_file", return_value=False),
            patch("subprocess.run") as run,
        ):
            # On attend RuntimeError avec un message correspondant au motif indiqué dans ce bloc ; si
            # aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(RuntimeError, "Script de controle absent"):
                # On appelle self.task sans argument positionnel.
                self.task()
            # On vérifie que run n’a pas été appelé dans ce scénario.
            run.assert_not_called()

    def test_missing_configuration_rejected(self):
        # On parcourt ('PROJECT12_IMPORT_PASSWORD', 'PROJECT12_IMPORT_HOST', 'PROJECT12_IMPORT_… ; key
        # désigne l’élément courant de ce scénario.
        for key in (
            "PROJECT12_IMPORT_PASSWORD",
            "PROJECT12_IMPORT_HOST",
            "PROJECT12_IMPORT_PORT",
            "PROJECT12_IMPORT_USER",
            "PROJECT12_IMPORT_CONNECTION_MODE",
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with (
                self.subTest(key=key),
                patch.dict(os.environ, {key: ""}),
                patch.object(Path, "is_file", return_value=True),
                patch("subprocess.run") as run,
            ):
                # On attend RuntimeError avec un message correspondant au motif indiqué dans ce bloc ;
                # si aucune erreur n’est levée, le test doit échouer.
                with self.assertRaisesRegex(RuntimeError, "incomplete"):
                    # On appelle self.task sans argument positionnel.
                    self.task()
                # On vérifie que run n’a pas été appelé : le refus doit intervenir avant cette
                # opération.
                run.assert_not_called()

    def test_local_mode_rejected(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(os.environ, {"PROJECT12_IMPORT_CONNECTION_MODE": "local"}),
            patch.object(Path, "is_file", return_value=True),
            patch("subprocess.run") as run,
        ):
            # On attend RuntimeError avec un message correspondant au motif indiqué dans ce bloc ; si
            # aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(RuntimeError, "Mode environment requis"):
                # On appelle self.task sans argument positionnel.
                self.task()
            # On vérifie que run n’a pas été appelé dans ce scénario.
            run.assert_not_called()

    def test_failure_is_not_success_and_secret_is_masked(self):
        # On garde dans log un flux texte en mémoire, utilisable comme un fichier par le lecteur CSV.
        log = io.StringIO()
        # On remplace temporairement Path dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(Path, "is_file", return_value=True),
            patch(
                "subprocess.run",
                # On fixe la réponse de ce double de test ; aucune vraie opération de la dépendance
                # n’est nécessaire pour obtenir cette valeur.
                return_value=SimpleNamespace(
                    # On dirige la sortie normale vers la destination prévue pour les traces.
                    stdout="error synthetic-import-secret", returncode=1
                ),
            ),
            contextlib.redirect_stdout(log),
        ):
            # On attend RuntimeError avec un message correspondant au motif indiqué dans ce bloc ; si
            # aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(RuntimeError, "code 1"):
                # On appelle self.task sans argument positionnel.
                self.task()
        # On vérifie que 'synthetic-import-secret' ne figure pas dans log.getvalue().
        self.assertNotIn("synthetic-import-secret", log.getvalue())
        # On vérifie que '[secret masque]' figure dans log.getvalue().
        self.assertIn("[secret masque]", log.getvalue())

    def test_timeout_does_not_print_partial_output(self):
        # On garde dans log un flux texte en mémoire, utilisable comme un fichier par le lecteur CSV.
        log = io.StringIO()
        # On garde dans timeout la valeur renvoyée par subprocess.TimeoutExpired pour 'synthetic'.
        timeout = subprocess.TimeoutExpired(
            # On fournit la sortie préparée via le paramètre output de cet appel.
            "synthetic", 120, output="synthetic-import-secret"
        )
        # On remplace temporairement Path dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(Path, "is_file", return_value=True),
            patch("subprocess.run", side_effect=timeout),
            contextlib.redirect_stdout(log),
        ):
            # On attend RuntimeError avec un message correspondant au motif indiqué dans ce bloc ; si
            # aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(RuntimeError, "120 secondes"):
                # On appelle self.task sans argument positionnel.
                self.task()
        # On vérifie que 'synthetic-import-secret' ne figure pas dans log.getvalue().
        self.assertNotIn("synthetic-import-secret", log.getvalue())

    def test_success_output_is_also_masked(self):
        # On garde dans log un flux texte en mémoire, utilisable comme un fichier par le lecteur CSV.
        log = io.StringIO()
        # On remplace temporairement Path dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(Path, "is_file", return_value=True),
            patch(
                "subprocess.run",
                # On fixe la réponse de ce double de test ; aucune vraie opération de la dépendance
                # n’est nécessaire pour obtenir cette valeur.
                return_value=SimpleNamespace(
                    # On dirige la sortie normale vers la destination prévue pour les traces.
                    stdout="synthetic-import-secret", returncode=0
                ),
            ),
            contextlib.redirect_stdout(log),
        ):
            # On appelle self.task sans argument positionnel.
            self.task()
        # On vérifie que 'synthetic-import-secret' ne figure pas dans log.getvalue().
        self.assertNotIn("synthetic-import-secret", log.getvalue())


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
