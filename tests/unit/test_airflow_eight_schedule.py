# Lecture du fichier — Tests de airflow eight schedule.
#

"""Tests sans NAS, SQL, Docker ni traitement metier."""

# On importe ast. On analyse la structure du code Python sans exécuter le texte analysé.
import ast
# On rend disponibles datetime, timedelta, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timedelta, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe types. Ce module sera utilisé par les opérations de ce fichier.
import types
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch
# On utilise les règles du fuseau demandé, notamment lors des changements d’heure.
from zoneinfo import ZoneInfo

# On récupère Path(__file__).resolve().parents[2] et on le garde dans ROOT pour la suite.
ROOT = Path(__file__).resolve().parents[2]
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(ROOT / "scripts"))
# On importe airflow_eight_contract sous le nom c. Ce module sera utilisé par les opérations de ce
# fichier.
import airflow_eight_contract as c
# On importe airflow_eight_task sous le nom task. Ce module sera utilisé par les opérations de ce
# fichier.
import airflow_eight_task as task
# On importe run_airflow_eight_workflow sous le nom runner. Ce module sera utilisé par les opérations
# de ce fichier.
import run_airflow_eight_workflow as runner


class ScheduleTests(unittest.TestCase):
    def due(self, month=10):
        # On fournit à l’appelant la valeur renvoyée par datetime pour 2026.
        return datetime(2026, month, 14, 10, tzinfo=ZoneInfo("Europe/Paris"))

    def test_on_time(self):
        # On garde dans d la date de déclenchement construite pour le test de planning.
        d = self.due()
        # On appelle c.validate_trigger avec 'scheduled'.
        c.validate_trigger("scheduled", {}, d, now=d)

    def test_two_minutes_inclusive(self):
        # On garde dans d la date de déclenchement construite pour le test de planning.
        d = self.due()
        # On appelle c.validate_scheduled_time avec d.
        c.validate_scheduled_time(d, now=d + timedelta(seconds=120))

    def test_late_refused(self):
        # On garde dans d la date de déclenchement construite pour le test de planning.
        d = self.due()
        # On parcourt (121, 900, 86400) ; seconds désigne l’élément courant de ce scénario.
        for seconds in (121, 900, 86400):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with (
                self.subTest(seconds=seconds),
                self.assertRaisesRegex(c.EightControlError, "EXPIRED"),
            ):
                # On appelle c.validate_scheduled_time avec d.
                c.validate_scheduled_time(d, now=d + timedelta(seconds=seconds))

    def test_early_refused(self):
        # On garde dans d la date de déclenchement construite pour le test de planning.
        d = self.due()
        # On attend c.EightControlError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(c.EightControlError, "TOO_EARLY"):
            # On appelle c.validate_scheduled_time avec d.
            c.validate_scheduled_time(d, now=d - timedelta(seconds=1))

    def test_missing_deadline_refused(self):
        # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(c.EightControlError):
            # On appelle c.validate_trigger avec 'scheduled'.
            c.validate_trigger("scheduled", {})

    def test_wrong_hour_refused(self):
        # On garde dans d le résultat du remplacement demandé sur self.due().
        d = self.due().replace(hour=9)
        # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(c.EightControlError):
            # On appelle c.validate_scheduled_time avec d.
            c.validate_scheduled_time(d, now=d)

    def test_naive_deadline_refused(self):
        # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(c.EightControlError):
            # On appelle c.validate_scheduled_time avec datetime(2026, 10, 14, 10).
            c.validate_scheduled_time(datetime(2026, 10, 14, 10))

    def test_timezone_winter_and_summer(self):
        # On parcourt (1, 7) ; month désigne l’élément courant de ce scénario.
        for month in (1, 7):
            # On garde dans d la date de déclenchement construite pour le test de planning.
            d = self.due(month)
            # On appelle c.validate_scheduled_time avec d.astimezone(timezone.utc).
            c.validate_scheduled_time(d.astimezone(timezone.utc), now=d)

    def test_scheduled_override_refused(self):
        # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(c.EightControlError):
            # On appelle c.validate_trigger avec 'scheduled'.
            c.validate_trigger(
                "scheduled", {"scope_id": "all"}, self.due(), now=self.due()
            )

    def test_manual_confirmation_preserved(self):
        # On appelle c.validate_trigger avec 'manual'.
        c.validate_trigger(
            "manual",
            {
                # On associe la clé 'scope_id' à cette valeur dans les données de ce scénario.
                "scope_id": c.SCOPE_ID,
                # On associe la clé 'allow_business_writes' à cette valeur dans les données de ce
                # scénario.
                "allow_business_writes": True,
                # On associe la clé 'confirm_nas_read_only' à cette valeur dans les données de ce
                # scénario.
                "confirm_nas_read_only": True,
            },
        )
        # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(c.EightControlError):
            # On appelle c.validate_trigger avec 'manual'.
            c.validate_trigger("manual", {})

    def test_expired_parent_never_launches(self):
        class Skip(Exception):
            # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe
            # parente.
            pass

        # On garde dans fake la valeur renvoyée par types.ModuleType pour 'airflow.exceptions'.
        fake = types.ModuleType("airflow.exceptions")
        # On garde Skip sous le nom fake.AirflowSkipException ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        fake.AirflowSkipException = Skip
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with (
            patch.dict(sys.modules, {"airflow.exceptions": fake}),
            patch.object(
                task,
                "validate_trigger",
                # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
                # suivre une fonction de test.
                side_effect=c.EightControlError("SCHEDULED_RUN_EXPIRED_NO_CATCHUP"),
            ),
            patch.object(task.subprocess, "Popen") as launch,
        ):
            # On attend Skip dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(Skip):
                # On appelle task.execute_eight avec 'scheduled'.
                task.execute_eight("scheduled", {}, self.due())
            # On vérifie que launch n’a pas été appelé : le refus doit intervenir avant cette
            # opération.
            launch.assert_not_called()

    def test_expired_child_before_imports(self):
        # On garde dans d la date de déclenchement construite pour le test de planning.
        d = self.due()
        # On remplace temporairement runner dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(
            runner,
            "validate_scheduled_time",
            # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
            # suivre une fonction de test.
            side_effect=c.EightControlError("SCHEDULED_RUN_EXPIRED_NO_CATCHUP"),
        ):
            # On vérifie que runner.main(['--run', '--allow-business-writes',
            # '--confirm-nas-read-only',… correspond à 1.
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                runner.main(
                    [
                        "--run",
                        "--allow-business-writes",
                        "--confirm-nas-read-only",
                        "--receipt",
                        "/opt/project/logs/airflow_workflow/eight_execution_20261014T100000_"
                        + "a" * 32
                        + ".json",
                        "--trigger-mode",
                        "airflow_scheduled",
                        "--scheduled-for",
                        d.isoformat(),
                    ]
                ),
                # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
                1,
            )

    def test_scheduled_child_command_and_receipt(self):
        # On importe tempfile, json. On prépare des fichiers ou dossiers temporaires pour les cas
        # isolés.
        import tempfile, json
        # On rend disponibles Mock depuis unittest.mock, pour les appels de ce fichier.
        from unittest.mock import Mock
        # On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
        from uuid import uuid4

        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as tmp:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(tmp)
            # On prépare le dossier root / 'scripts' avec les règles de création indiquées ; aucun
            # résultat métier n’est encore produit par cette création.
            (root / "scripts").mkdir()
            # On appelle (root / 'scripts/run_airflow_eight_workflow.py').touch sans argument
            # positionnel.
            (root / "scripts/run_airflow_eight_workflow.py").touch()
            # On prépare le dossier root / 'logs/airflow_workflow' avec les règles de création
            # indiquées ; aucun résultat métier n’est encore produit par cette création.
            (root / "logs/airflow_workflow").mkdir(parents=True)
            # On garde dans helper un objet simple portant les attributs indiqués.
            helper = types.SimpleNamespace(
                child_environment=Mock(
                    # On fixe la réponse de ce double de test ; aucune vraie opération de la dépendance
                    # n’est nécessaire pour obtenir cette valeur.
                    return_value={"PROJECT12_WORKFLOW_SHARE_ID": "test"}
                ),
                stop_group=Mock(),
            )
            # On garde dans wid la représentation textuelle de uuid4().
            wid = str(uuid4())

            def launch(cmd, **kwargs):
                # On vérifie que cmd[cmd.index('--trigger-mode') + 1] correspond à 'airflow_scheduled'.
                self.assertEqual(
                    # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                    cmd[cmd.index("--trigger-mode") + 1], "airflow_scheduled"
                )
                # On vérifie que cmd[cmd.index('--scheduled-for') + 1] correspond à
                # self.due().isoformat().
                self.assertEqual(
                    # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                    cmd[cmd.index("--scheduled-for") + 1], self.due().isoformat()
                )
                # On garde dans receipt un nouveau dictionnaire construit avec les valeurs indiquées.
                receipt = dict(
                    kind="execution",
                    # On fournit l’état du traitement via le paramètre status de cet appel.
                    status="success",
                    # On fournit les étapes terminées via le paramètre completed_steps de cet appel.
                    completed_steps=8,
                    scope_id=c.SCOPE_ID,
                    share_id="test",
                    # On transmet la sélection explicite des domaines concernés par cet appel.
                    vineyards=list(c.VINEYARDS),
                    # On fournit l’identifiant de l’exécution du workflow via le paramètre
                    # workflow_execution_id de cet appel.
                    workflow_execution_id=wid,
                    # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                    trigger_mode="airflow_scheduled",
                    journal_relative_path="data/03_normalized/workflow_runs/"
                    + wid.replace("-", "")
                    + "/events.jsonl",
                    # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de
                    # cet appel.
                    excel_publication_id="pub",
                    # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id
                    # de cet appel.
                    pipeline_execution_id="pipeline",
                )
                # On écrit le contenu préparé dans Path(cmd[cmd.index('--receipt') + 1]) ; cette
                # opération remplace le contenu du fichier s’il existe déjà.
                Path(cmd[cmd.index("--receipt") + 1]).write_text(json.dumps(receipt))
                # On fournit à l’appelant un objet simple portant les attributs indiqués.
                return types.SimpleNamespace(wait=Mock(return_value=0))

            # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
            # programme métier.
            with (
                patch.dict(sys.modules, {"airflow_pilote_task": helper}),
                patch.object(task, "ROOT", root),
                patch.object(task, "BUSINESS_PYTHON", Path(sys.executable)),
                # Le processus enfant est déjà simulé : on décrit ici son environnement Linux.
                # On ne change pas os.name globalement, sinon pathlib utiliserait les mauvais chemins.
                patch.object(task, "os", types.SimpleNamespace(
                    name="posix", access=task.os.access,
                    X_OK=task.os.X_OK, environ=task.os.environ,
                )),
                patch.object(task, "validate_trigger"),
                patch.object(task.subprocess, "Popen", side_effect=launch),
            ):
                # On vérifie que task.execute_eight('scheduled', {}, self.due())['trigger_mode']
                # correspond à 'airflow_scheduled'.
                self.assertEqual(
                    # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                    task.execute_eight("scheduled", {}, self.due())["trigger_mode"],
                    # On fournit la valeur attendue ou la collection de comparaison pour cette
                    # assertion.
                    "airflow_scheduled",
                )

    def test_timetable_is_trigger_not_interval(self):
        # On garde dans tree la valeur renvoyée par ast.parse.
        tree = ast.parse(
            (ROOT / "dags/project12_eight_vineyards_business.py").read_text()
        )
        # On garde dans dag le prochain élément de (n for n in ast.walk(tree) if isinstance(n,
        # ast.Call) and isinstance(n.fu….
        dag = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            # On exige aussi que n.func est du type ast.Name.
            and isinstance(n.func, ast.Name)
            # On exige aussi que n.func.id correspond au texte 'dag'.
            and n.func.id == "dag"
        )
        # On indexe kw par k.arg ; chaque clé sera associée à k.value. Une même clé ne peut garder
        # qu’une valeur.
        kw = {k.arg: k.value for k in dag.keywords}
        # On vérifie que kw['schedule'].func.id correspond à 'CronTriggerTimetable'.
        self.assertEqual(kw["schedule"].func.id, "CronTriggerTimetable")
        # On vérifie que ast.literal_eval(kw['schedule'].args[0]) correspond à '0 10 * * *'.
        self.assertEqual(ast.literal_eval(kw["schedule"].args[0]), "0 10 * * *")
        # On attend que ast.literal_eval(next((k.value for k in kw['schedule'].keywords if k.arg ==
        # 'run_immediately'))) soit évalué comme faux pour ce cas de test.
        self.assertFalse(
            ast.literal_eval(
                next(
                    k.value
                    for k in kw["schedule"].keywords
                    if k.arg == "run_immediately"
                )
            )
        )
        # On attend que ast.literal_eval(kw['catchup']) soit évalué comme faux pour ce cas de test.
        self.assertFalse(ast.literal_eval(kw["catchup"]))
        # On vérifie que ast.literal_eval(kw['default_args']) correspond à {'retries': 0}.
        self.assertEqual(ast.literal_eval(kw["default_args"]), {"retries": 0})


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
