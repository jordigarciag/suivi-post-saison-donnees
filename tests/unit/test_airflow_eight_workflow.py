# Lecture du fichier — Tests de airflow eight workflow.
#

"""Essais synthetiques : aucun Docker, Airflow reel, NAS ou PostgreSQL."""

# On rend disponibles contextmanager, redirect_stdout, redirect_stderr depuis contextlib, pour les
# appels de ce fichier.
from contextlib import contextmanager, redirect_stdout, redirect_stderr
# On rend disponibles datetime depuis datetime, pour les appels de ce fichier.
from datetime import datetime
# On importe ast. On analyse la structure du code Python sans exécuter le texte analysé.
import ast
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe types. Ce module sera utilisé par les opérations de ce fichier.
import types
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Mock, patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import Mock, patch
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On récupère Path(__file__).resolve().parents[2] et on le garde dans ROOT_TEST pour la suite.
ROOT_TEST = Path(__file__).resolve().parents[2]
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(ROOT_TEST / "scripts"))
# On importe airflow_eight_contract sous le nom c. Ce module sera utilisé par les opérations de ce
# fichier.
import airflow_eight_contract as c
# On importe airflow_eight_runtime sous le nom runtime. Ce module sera utilisé par les opérations de ce
# fichier.
import airflow_eight_runtime as runtime
# On importe run_airflow_eight_workflow sous le nom runner. Ce module sera utilisé par les opérations
# de ce fichier.
import run_airflow_eight_workflow as runner
# On importe airflow_eight_task sous le nom task. Ce module sera utilisé par les opérations de ce
# fichier.
import airflow_eight_task as task


def conf():
    # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
    return dict(
        scope_id=c.SCOPE_ID, allow_business_writes=True, confirm_nas_read_only=True
    )


def receipt():
    # On garde dans wid la représentation textuelle de uuid4().
    wid = str(uuid4())
    # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
    return dict(
        kind="execution",
        # On fournit l’état du traitement via le paramètre status de cet appel.
        status="success",
        # On fournit les étapes terminées via le paramètre completed_steps de cet appel.
        completed_steps=8,
        # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
        trigger_mode="airflow_manual",
        scope_id=c.SCOPE_ID,
        share_id="test-share",
        # On transmet la sélection explicite des domaines concernés par cet appel.
        vineyards=list(c.VINEYARDS),
        # On fournit l’identifiant de l’exécution du workflow via le paramètre workflow_execution_id de
        # cet appel.
        workflow_execution_id=wid,
        journal_relative_path="data/03_normalized/workflow_runs/"
        + wid.replace("-", "")
        + "/events.jsonl",
        # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de cet appel.
        excel_publication_id="20261014_8d5de13f",
        # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de cet
        # appel.
        pipeline_execution_id="20261014_dd428ec1",
    )


class ContractTests(unittest.TestCase):
    def test_manual_valid(self):
        # On appelle c.validate_trigger avec 'manual'.
        c.validate_trigger("manual", conf())

    def test_scheduled_refused(self):
        # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(c.EightControlError):
            # On appelle c.validate_trigger avec 'scheduled'.
            c.validate_trigger("scheduled", conf())

    def test_confirmation_values_refused(self):
        # On parcourt ('allow_business_writes', 'confirm_nas_read_only') ; key désigne l’élément
        # courant de ce scénario.
        for key in ("allow_business_writes", "confirm_nas_read_only"):
            # On parcourt (False, 'true', 1, None) ; value désigne l’élément courant de ce scénario.
            for value in (False, "true", 1, None):
                # On garde dans d la valeur renvoyée par conf.
                d = conf()
                # On garde la valeur reçue sous le nom d[key] ; cette affectation ne copie pas à elle
                # seule un objet mutable.
                d[key] = value
                # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce
                # cas précis de la boucle.
                with (
                    self.subTest(key=key, value=value),
                    self.assertRaises(c.EightControlError),
                ):
                    # On appelle c.validate_trigger avec 'manual'.
                    c.validate_trigger("manual", d)

    def test_wrong_scope(self):
        # On garde dans d la valeur renvoyée par conf.
        d = conf()
        # On utilise ce texte pour d['scope_id'] ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        d["scope_id"] = "all"
        # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(c.EightControlError):
            # On appelle c.validate_trigger avec 'manual'.
            c.validate_trigger("manual", d)

    def test_extra_parameters_refused(self):
        # On garde dans d la valeur renvoyée par conf.
        d = conf()
        # On utilise ce texte pour d['vineyard'] ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        d["vineyard"] = "Other"
        # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(c.EightControlError):
            # On appelle c.validate_trigger avec 'manual'.
            c.validate_trigger("manual", d)

    def test_scope_cannot_mutate_constant(self):
        # On garde dans d la valeur renvoyée par c.scope.
        d = c.scope()
        # On appelle d['vineyards'].clear sans argument positionnel.
        d["vineyards"].clear()
        # On vérifie que len(c.VINEYARDS) correspond à 8.
        self.assertEqual(len(c.VINEYARDS), 8)

    def test_scope_exact(self):
        # On parcourt ([], list(c.VINEYARDS[:-1]), list(c.VINEYARDS) + ['Other'], list(reversed… ;
        # names désigne l’élément courant de ce scénario.
        for names in (
            [],
            list(c.VINEYARDS[:-1]),
            list(c.VINEYARDS) + ["Other"],
            list(reversed(c.VINEYARDS)),
            None,
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(names=names), self.assertRaises(c.EightControlError):
                # On appelle c.validate_names avec names.
                c.validate_names(names)

    def test_valid_receipt(self):
        # On vérifie que c.result_from_receipt(receipt(), 'test-share')['status'] correspond à
        # 'success'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            c.result_from_receipt(receipt(), "test-share")["status"], "success"
        )

    def test_receipt_fields_refused(self):
        # On parcourt [('status', 'failed'), ('completed_steps', 5), ('scope_id', 'wrong'), ('v… ;
        # (key, value) désigne l’élément courant de ce scénario.
        for key, value in [
            ("status", "failed"),
            ("completed_steps", 5),
            ("scope_id", "wrong"),
            ("vineyards", ["DomaineDemoD"]),
            ("share_id", "wrong"),
            ("trigger_mode", "unknown"),
            ("excel_publication_id", None),
            ("journal_relative_path", "../events.jsonl"),
        ]:
            # On garde dans d la valeur renvoyée par receipt.
            d = receipt()
            # On garde la valeur reçue sous le nom d[key] ; cette affectation ne copie pas à elle seule
            # un objet mutable.
            d[key] = value
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(key=key), self.assertRaises(c.EightControlError):
                # On appelle c.result_from_receipt avec d.
                c.result_from_receipt(d, "test-share")


class AssemblyGuardTests(unittest.TestCase):
    def plan(self, names):
        # On prépare actions comme liste vide ; on la remplira au fil des opérations suivantes.
        actions = []
        # On parcourt c.STEPS ; key désigne l’élément courant de ce scénario.
        for key in c.STEPS:
            # On vérifie ce cas avant la suite : la clé de l’élément correspond au texte
            # 'nas_scope_prepare'.
            if key == "nas_scope_prepare":
                # On ajoute (key, lambda ctx: dict(vineyards=tuple(names), year=2026)) à la fin de
                # actions ; les éléments précédents restent conservés.
                actions.append(
                    (key, lambda ctx: dict(vineyards=tuple(names), year=2026))
                )
            else:
                # On ajoute (key, Mock(name=key)) à la fin de actions ; les éléments précédents restent
                # conservés.
                actions.append((key, Mock(name=key)))
        # On fournit à l’appelant un objet simple portant les attributs indiqués.
        return types.SimpleNamespace(steps=actions)

    def context(self):
        # On fournit à l’appelant un objet simple portant les attributs indiqués.
        return types.SimpleNamespace(
            # On fournit les résultats regroupés via le paramètre results de cet appel.
            results={
                # On associe la clé 'excel_reference_pin' à cette valeur dans les données de ce
                # scénario.
                "excel_reference_pin": types.SimpleNamespace(
                    # On fournit le chemin du tableau Excel regroupé via le paramètre reference_path de
                    # cet appel.
                    reference_path=Path("/fake/reference.csv")
                )
            }
        )

    def test_reuses_seven_original_actions(self):
        # On garde dans plan la valeur renvoyée par self.plan.
        plan = self.plan(c.VINEYARDS)
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(
            sys.modules,
            {
                # On associe la clé 'run_local_pipeline' à cette valeur dans les données de ce
                # scénario.
                "run_local_pipeline": types.SimpleNamespace(
                    select_vineyards=Mock(return_value=list(c.VINEYARDS))
                )
            },
        ):
            # On garde dans steps la valeur renvoyée par runtime.guarded_steps.
            steps = runtime.guarded_steps(plan)
            # On parcourt zip(plan.steps, steps) ; ((key, old), (_, new)) désigne l’élément courant de
            # ce scénario.
            for (key, old), (_, new) in zip(plan.steps, steps):
                # On vérifie ce cas avant la suite : la clé de l’élément diffère du texte
                # 'nas_scope_prepare'.
                if key != "nas_scope_prepare":
                    # On vérifie l’identité de old avec new, et pas seulement une égalité de valeur.
                    self.assertIs(old, new)
            # On vérifie que steps[3][1](self.context())['vineyards'] correspond à c.VINEYARDS.
            self.assertEqual(steps[3][1](self.context())["vineyards"], c.VINEYARDS)

    def test_wrong_selected_scope_refused(self):
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(
            sys.modules,
            {"run_local_pipeline": types.SimpleNamespace(select_vineyards=Mock())},
        ):
            # On garde dans steps la valeur renvoyée par runtime.guarded_steps.
            steps = runtime.guarded_steps(self.plan(["DomaineDemoD"]))
            # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(c.EightControlError):
                # On appelle steps[3][1] avec self.context().
                steps[3][1](self.context())

    def test_new_vineyard_after_ingestion_refused(self):
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(
            sys.modules,
            {
                # On associe la clé 'run_local_pipeline' à cette valeur dans les données de ce
                # scénario.
                "run_local_pipeline": types.SimpleNamespace(
                    select_vineyards=Mock(return_value=list(c.VINEYARDS) + ["Other"])
                )
            },
        ):
            # On garde dans steps la valeur renvoyée par runtime.guarded_steps.
            steps = runtime.guarded_steps(self.plan(c.VINEYARDS))
            # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(c.EightControlError):
                # On appelle steps[3][1] avec self.context().
                steps[3][1](self.context())

    def test_changed_step_names_refused(self):
        # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(c.EightControlError):
            # On appelle runtime.guarded_steps avec types.SimpleNamespace(steps=[]).
            runtime.guarded_steps(types.SimpleNamespace(steps=[]))


class RunnerTests(unittest.TestCase):
    def test_run_requires_both_confirmations_and_receipt(self):
        # On parcourt (['--run'], ['--run', '--allow-business-writes'], ['--run', '--allow-busi… ; args
        # désigne l’élément courant de ce scénario.
        for args in (
            ["--run"],
            ["--run", "--allow-business-writes"],
            ["--run", "--allow-business-writes", "--confirm-nas-read-only"],
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with (
                self.subTest(args=args),
                redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                # On appelle runner.main avec args.
                runner.main(args)

    def test_diagnostic_refuses_business_flags(self):
        # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            # On appelle runner.main avec ['--diagnostic-only', '--allow-business-writes'].
            runner.main(["--diagnostic-only", "--allow-business-writes"])

    def test_receipt_outside_logs_refused(self):
        # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            # On appelle runner.main avec ['--run', '--allow-business-writes',
            # '--confirm-nas-read-only', '--receipt', '/tmp/eight_….
            runner.main(
                [
                    "--run",
                    "--allow-business-writes",
                    "--confirm-nas-read-only",
                    "--receipt",
                    "/tmp/eight_execution_bad.json",
                ]
            )

    @contextmanager
    def dependencies(self, root, fail_preflight=False):
        @contextmanager
        def lock(*a):
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield None

        # On garde dans run un double de test dont les réponses et les appels pourront être contrôlés.
        run = Mock()
        # On choisit la valeur de sources selon ce test : fail_preflight est évalué comme vrai. Les
        # deux résultats possibles restent définis explicitement ici.
        sources = (
            Mock(side_effect=c.EightControlError("EIGHT_SCOPE_MISMATCH"))
            if fail_preflight
            else Mock(return_value=("share", "publication"))
        )
        # On garde dans sql un double de test dont les réponses et les appels pourront être contrôlés.
        sql = Mock()
        # On garde dans write un double de test dont les réponses et les appels pourront être
        # contrôlés.
        write = Mock()
        # On garde dans build un double de test dont les réponses et les appels pourront être
        # contrôlés.
        build = Mock(return_value="plan")
        # On regroupe dans modules ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        modules = {
            # On associe la clé 'workflow_business_config' à cette valeur dans les données de ce
            # scénario.
            "workflow_business_config": types.SimpleNamespace(
                load_business_configuration=Mock(return_value="config")
            ),
            # On associe la clé 'workflow_business_wiring' à cette valeur dans les données de ce
            # scénario.
            "workflow_business_wiring": types.SimpleNamespace(
                build_business_plan=build
            ),
            # On associe la clé 'workflow_runtime' à cette valeur dans les données de ce scénario.
            "workflow_runtime": types.SimpleNamespace(
                workflow_lock=lock, run_workflow=run
            ),
            # On associe la clé 'run_workflow_business' à cette valeur dans les données de ce scénario.
            "run_workflow_business": types.SimpleNamespace(diagnose_importer=sql),
            # On associe la clé 'airflow_workflow_runtime_check' à cette valeur dans les données de ce
            # scénario.
            "airflow_workflow_runtime_check": types.SimpleNamespace(
                write_receipt=write
            ),
            # On associe la clé 'airflow_eight_runtime' à cette valeur dans les données de ce scénario.
            "airflow_eight_runtime": types.SimpleNamespace(
                check_eight_sources=sources, guarded_steps=Mock(return_value=[])
            ),
        }
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(sys.modules, modules), patch.object(runner, "ROOT", root):
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield run, sources, sql, write, build

    def test_diagnostic_never_runs_workflow(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with (
            tempfile.TemporaryDirectory() as tmp,
            self.dependencies(Path(tmp)) as (run, sources, sql, write, build),
            redirect_stdout(io.StringIO()),
        ):
            # On vérifie que runner.main(['--diagnostic-only']) correspond à 0.
            self.assertEqual(runner.main(["--diagnostic-only"]), 0)
            # On vérifie que run n’a pas été appelé dans ce scénario.
            run.assert_not_called()
            # On attend un seul appel à sql dans ce scénario, ni zéro ni plusieurs.
            sql.assert_called_once()
            # On attend un seul appel à write dans ce scénario, ni zéro ni plusieurs.
            write.assert_called_once()
            # On vérifie que build.call_args.kwargs['vineyards'] correspond à list(c.VINEYARDS).
            self.assertEqual(build.call_args.kwargs["vineyards"], list(c.VINEYARDS))

    def test_failed_preflight_no_sql_and_no_receipt(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with (
            tempfile.TemporaryDirectory() as tmp,
            self.dependencies(Path(tmp), True) as (run, sources, sql, write, build),
            redirect_stdout(io.StringIO()),
        ):
            # On vérifie que runner.main(['--diagnostic-only']) correspond à 1.
            self.assertEqual(runner.main(["--diagnostic-only"]), 1)
            # On vérifie que run n’a pas été appelé dans ce scénario.
            run.assert_not_called()
            # On vérifie que sql n’a pas été appelé dans ce scénario.
            sql.assert_not_called()
            # On vérifie que write n’a pas été appelé : le refus doit intervenir avant cette
            # opération.
            write.assert_not_called()

    def test_sensitive_error_message_not_printed(self):
        # On garde dans stream un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        stream = io.StringIO()
        # On utilise redirect_stdout(stream) dans son contexte de gestion ; les opérations de sortie
        # sont exécutées en quittant le bloc.
        with redirect_stdout(stream):
            # On appelle runner.safe_error avec RuntimeError('SECRET_PASSWORD').
            runner.safe_error(RuntimeError("SECRET_PASSWORD"), "plan_construction")
        # On vérifie que 'SECRET_PASSWORD' ne figure pas dans stream.getvalue().
        self.assertNotIn("SECRET_PASSWORD", stream.getvalue())


class TaskTests(unittest.TestCase):
    def test_windows_execution_refused_before_launch(self):
        # Le lancement métier reste réservé à Linux : rendre les tests portables ne change pas cela.
        # On simule Windows uniquement pour la tâche et on vérifie qu’aucun enfant n’est lancé.
        with (
            patch.object(task, "os", types.SimpleNamespace(name="nt")),
            patch.object(task.subprocess, "Popen") as launch,
            self.assertRaisesRegex(c.EightControlError, "LINUX_EXECUTION_REQUIRED"),
        ):
            task.execute_eight("manual", conf())
        launch.assert_not_called()

    def test_scheduled_refused_before_any_launch(self):
        # On remplace temporairement task.subprocess dans ce bloc de test ; le réglage initial sera
        # rétabli à sa sortie.
        with (
            patch.object(task.subprocess, "Popen") as launch,
            self.assertRaises(c.EightControlError),
        ):
            # On appelle task.execute_eight avec 'scheduled'.
            task.execute_eight("scheduled", conf())
        # On vérifie que launch n’a pas été appelé dans ce scénario.
        launch.assert_not_called()

    def test_no_interpreter_no_launch(self):
        # Le lancement du processus est remplacé pour observer ses paramètres sans démarrer le
        # programme métier.
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(task, "BUSINESS_PYTHON", Path(tmp) / "absent"),
            # On atteint le contrôle de l’interpréteur, même lorsque pytest tourne sous Windows.
            patch.object(task, "os", types.SimpleNamespace(name="posix")),
            patch.object(task.subprocess, "Popen") as launch,
        ):
            # On attend c.EightControlError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaisesRegex(c.EightControlError, "BUSINESS_PYTHON_UNAVAILABLE_NO_FALLBACK"):
                # On appelle task.execute_eight avec 'manual'.
                task.execute_eight("manual", conf())
            # On vérifie que launch n’a pas été appelé : le refus doit intervenir avant cette
            # opération.
            launch.assert_not_called()

    def exercise(self, returncode=0, bad_receipt=False):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as tmp:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(tmp)
            # On prépare le dossier root / 'scripts' avec les règles de création indiquées ; aucun
            # résultat métier n’est encore produit par cette création.
            (root / "scripts").mkdir()
            # On écrit le contenu préparé dans root / 'scripts/run_airflow_eight_workflow.py' ; cette
            # opération remplace le contenu du fichier s’il existe déjà.
            (root / "scripts/run_airflow_eight_workflow.py").write_text("")
            # On prépare le dossier root / 'logs/airflow_workflow' avec les règles de création
            # indiquées ; aucun résultat métier n’est encore produit par cette création.
            (root / "logs/airflow_workflow").mkdir(parents=True)
            # On garde dans stop un double de test dont les réponses et les appels pourront être
            # contrôlés.
            stop = Mock()
            # On regroupe dans seed ces champs nommés ; on pourra les retrouver par leur clé plutôt que
            # par leur position.
            seed = {"PROJECT12_WORKFLOW_SHARE_ID": "test-share"}

            def launch(command, **kwargs):
                # On vérifie que command[0] correspond à sys.executable.
                self.assertEqual(command[0], sys.executable)
                # On attend que kwargs['shell'] soit évalué comme faux pour ce cas de test.
                self.assertFalse(kwargs["shell"])
                # On attend que kwargs['start_new_session'] soit évalué comme vrai pour ce cas de test.
                self.assertTrue(kwargs["start_new_session"])
                # On attend que kwargs['close_fds'] soit évalué comme vrai pour ce cas de test.
                self.assertTrue(kwargs["close_fds"])
                # On vérifie que kwargs['env'] correspond à seed.
                self.assertEqual(kwargs["env"], seed)
                # On garde dans d la valeur renvoyée par receipt.
                d = receipt()
                # Cette branche traite le cas où bad_receipt est évalué comme vrai.
                if bad_receipt:
                    # On fixe d['completed_steps'] à 5 pour cette étape du scénario de test.
                    d["completed_steps"] = 5
                # On écrit le contenu préparé dans Path(command[-1]) ; cette opération remplace le
                # contenu du fichier s’il existe déjà.
                Path(command[-1]).write_text(json.dumps(d))
                # On fournit à l’appelant un objet simple portant les attributs indiqués.
                return types.SimpleNamespace(wait=Mock(return_value=returncode))

            # On garde dans helper un objet simple portant les attributs indiqués.
            helper = types.SimpleNamespace(
                child_environment=Mock(return_value=seed), stop_group=stop
            )
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
                patch.object(task.subprocess, "Popen", side_effect=launch),
                redirect_stdout(io.StringIO()),
            ):
                # Cette branche traite le cas où returncode est évalué comme vrai ou bad_receipt est
                # évalué comme vrai.
                if returncode or bad_receipt:
                    # On attend RuntimeError avec un message correspondant au motif indiqué dans ce
                    # bloc ; si aucune erreur n’est levée, le test doit échouer.
                    with self.assertRaisesRegex(
                        RuntimeError, "AIRFLOW_EIGHT_NOT_CONFIRMED"
                    ):
                        # On appelle task.execute_eight avec 'manual'.
                        task.execute_eight("manual", conf())
                    # On attend un seul appel à stop dans ce scénario, ni zéro ni plusieurs.
                    stop.assert_called_once()
                else:
                    # On vérifie que task.execute_eight('manual', conf())['status'] correspond à
                    # 'success'.
                    self.assertEqual(
                        # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                        task.execute_eight("manual", conf())["status"], "success"
                    )

    def test_success_receipt(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise()

    def test_nonzero_child_refused(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise(returncode=1)

    def test_partial_receipt_refused(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise(bad_receipt=True)


class DagTests(unittest.TestCase):
    def test_schedule_no_retry_and_one_run(self):
        # On garde dans tree la valeur renvoyée par ast.parse.
        tree = ast.parse(
            (ROOT_TEST / "dags/project12_eight_vineyards_business.py").read_text()
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
        # On indexe kws par k.arg ; chaque clé sera associée à k.value. Une même clé ne peut garder
        # qu’une valeur.
        kws = {k.arg: k.value for k in dag.keywords}
        # On parcourt [('catchup', False), ('max_active_runs', 1), ('max_active_tasks', 1)] ; (key,
        # value) désigne l’élément courant de ce scénario.
        for key, value in [
            ("catchup", False),
            ("max_active_runs", 1),
            ("max_active_tasks", 1),
        ]:
            # On vérifie que ast.literal_eval(kws[key]) correspond à value.
            self.assertEqual(ast.literal_eval(kws[key]), value)
        # On vérifie que ast.literal_eval(kws['default_args']) correspond à {'retries': 0}.
        self.assertEqual(ast.literal_eval(kws["default_args"]), {"retries": 0})

    def test_result_checker_read_only(self):
        # On garde dans source le texte lu depuis ROOT_TEST / 'scripts/check_airflow_eight_result.py'
        # avec l’encodage indiqué.
        source = (ROOT_TEST / "scripts/check_airflow_eight_result.py").read_text()
        # On vérifie que 'READ ONLY' figure dans source.
        self.assertIn("READ ONLY", source)
        # On vérifie que 'default_transaction_read_only=on' figure dans source.
        self.assertIn("default_transaction_read_only=on", source)
        # On vérifie que 'conn.rollback()' figure dans source.
        self.assertIn("conn.rollback()", source)
        # On vérifie que 'for vineyard in VINEYARDS:' figure dans source.
        self.assertIn("for vineyard in VINEYARDS:", source)
        # On vérifie que 'INSERT INTO' ne figure pas dans source.
        self.assertNotIn("INSERT INTO", source)
        # On vérifie que 'UPDATE ' ne figure pas dans source.
        self.assertNotIn("UPDATE ", source)


class SourcePreflightTests(unittest.TestCase):
    def exercise(self, missing=False, broken_json=False):
        # On rend disponibles nullcontext depuis contextlib, pour les appels de ce fichier.
        from contextlib import nullcontext

        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as tmp:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(tmp)
            # On assemble les morceaux du chemin incoming avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            incoming = root / "data/01_incoming/suivi_acquisitions"
            # On prépare le dossier incoming avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            incoming.mkdir(parents=True)
            # On crée le dictionnaire vide available pour y ranger ensuite les éléments par clé.
            available = {}
            # On parcourt c.VINEYARDS ; name désigne l’élément courant de ce scénario.
            for name in c.VINEYARDS:
                # On assemble les morceaux du chemin p avec l’opérateur / de pathlib ; aucun fichier
                # n’est créé par cette construction.
                p = incoming / (name + ".xlsx")
                # On écrit le contenu préparé dans p ; cette opération remplace le contenu du fichier
                # s’il existe déjà.
                p.write_bytes(b"PK\x03\x04synthetic")
                # On rassemble dans available[name.casefold()] les 2 éléments explicitement indiqués
                # pour ce cas d’essai.
                available[name.casefold()] = (name, p)
            # Cette branche traite le cas où missing est évalué comme vrai.
            if missing:
                # On retire de available l’élément demandé.
                available.pop(c.VINEYARDS[-1].casefold())
            # On garde dans files un objet simple portant les attributs indiqués.
            files = types.SimpleNamespace(unchanged=Mock())
            # On regroupe dans bundle ces champs nommés ; on pourra les retrouver par leur clé plutôt
            # que par leur position.
            bundle = {"files": files, "publication": {"publication_id": "pub"}}
            # On garde Path.open sous le nom real_open ; cette affectation ne copie pas à elle seule un
            # objet mutable.
            real_open = Path.open

            # On fournit la ressource ouverte dans le contexte prévu et on en gère la sortie.
            def opened(path, *a, **kw):
                # On reconnaît le NAS fictif avec des /, même si Windows affiche des antislashs.
                # Cette lecture reste simulée en mémoire ; aucun accès à un vrai NAS n’est nécessaire.
                if path.as_posix().startswith("/opt/nas/"):
                    # On fournit à l’appelant un flux texte en mémoire, utilisable comme un fichier par
                    # le lecteur CSV.
                    return io.StringIO("not json" if broken_json else "{}")
                # On fournit à l’appelant la valeur renvoyée par real_open.
                return real_open(path, *a, **kw)

            # On regroupe dans mods ces champs nommés ; on pourra les retrouver par leur clé plutôt que
            # par leur position.
            mods = {
                # On associe la clé 'airflow_workflow_runtime_check' à cette valeur dans les données de
                # ce scénario.
                "airflow_workflow_runtime_check": types.SimpleNamespace(
                    check_runtime=Mock(return_value="share")
                ),
                # On associe la clé 'suivi_traitements_post_saison.ingestion.tracking_versioning' à
                # cette valeur dans les données de ce scénario.
                "suivi_traitements_post_saison.ingestion.tracking_versioning": types.SimpleNamespace(
                    discover=Mock(return_value=available)
                ),
            }
            # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera
            # rétabli à sa sortie.
            with (
                patch.dict(sys.modules, mods),
                patch.object(runtime, "selected_from_publication", return_value=bundle),
                patch.object(Path, "open", opened),
                patch.object(
                    # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur
                    # ou suivre une fonction de test.
                    runtime.os, "scandir", side_effect=lambda p: nullcontext(iter([]))
                ),
            ):
                # Cette branche traite le cas où missing est évalué comme vrai ou broken_json est
                # évalué comme vrai.
                if missing or broken_json:
                    # On attend (c.EightControlError, json.JSONDecodeError) dans ce bloc ; si aucune
                    # erreur n’est levée, le test doit échouer.
                    with self.assertRaises((c.EightControlError, json.JSONDecodeError)):
                        # On appelle runtime.check_eight_sources avec root.
                        runtime.check_eight_sources(root)
                else:
                    # On vérifie que runtime.check_eight_sources(root) correspond à ('share', 'pub').
                    self.assertEqual(
                        # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                        runtime.check_eight_sources(root), ("share", "pub")
                    )
                    # On attend un seul appel à files.unchanged dans ce scénario, ni zéro ni plusieurs.
                    files.unchanged.assert_called_once()

    def test_all_eight_sources(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise()

    def test_missing_excel_refused(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise(missing=True)

    def test_unreadable_mapping_refused(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise(broken_json=True)


class ResultCheckerTests(unittest.TestCase):
    def exercise(self, bad_volume=False, missing_vineyard=False, wrong_manifest=False):
        # On importe check_airflow_eight_result sous le nom checker. Ce module sera utilisé par les
        # opérations de ce fichier.
        import check_airflow_eight_result as checker
        # On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des
        # mots de passe chiffrés.
        import hashlib

        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as tmp:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(tmp)
            # On assemble les morceaux du chemin logs avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            logs = root / "logs/airflow_workflow"
            # On prépare le dossier logs avec les règles de création indiquées ; aucun résultat métier
            # n’est encore produit par cette création.
            logs.mkdir(parents=True)
            # On assemble les morceaux du chemin state avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            state = root / "state/workflow_execution"
            # On prépare le dossier state avec les règles de création indiquées ; aucun résultat métier
            # n’est encore produit par cette création.
            state.mkdir(parents=True)
            # On écrit le contenu préparé dans state / 'airflow_share_identity.json' ; cette opération
            # remplace le contenu du fichier s’il existe déjà.
            (state / "airflow_share_identity.json").write_text(
                json.dumps({"share_id": "test-share"})
            )
            # On garde dans data la valeur renvoyée par receipt.
            data = receipt()
            # On récupère l’identifiant du lot Excel dans data et on le garde dans pub pour la suite.
            pub = data["excel_publication_id"]
            # On récupère l’identifiant du traitement NAS dans data et on le garde dans pipeline pour
            # la suite.
            pipeline = data["pipeline_execution_id"]
            # On assemble les morceaux du chemin rp avec l’opérateur / de pathlib ; aucun fichier n’est
            # créé par cette construction.
            rp = logs / "eight_execution_test.json"
            # On écrit le contenu préparé dans rp ; cette opération remplace le contenu du fichier s’il
            # existe déjà.
            rp.write_text(json.dumps(data))
            # On assemble les morceaux du chemin jp avec l’opérateur / de pathlib ; aucun fichier n’est
            # créé par cette construction.
            jp = root / data["journal_relative_path"]
            # On prépare le dossier jp.parent avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            jp.parent.mkdir(parents=True)
            # On écrit le contenu préparé dans jp ; cette opération remplace le contenu du fichier s’il
            # existe déjà.
            jp.write_text("journal bytes")
            # On assemble ces deux éléments pour construire relative.
            relative = "data/03_normalized/pipeline_runs/" + pipeline + "/manifest.json"
            # On calcule ce quotient pour construire mp.
            mp = root / relative
            # On prépare le dossier mp.parent avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            mp.parent.mkdir(parents=True)
            # On garde dans manifest un nouveau dictionnaire construit avec les valeurs indiquées.
            manifest = dict(
                # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de
                # cet appel.
                pipeline_execution_id=pipeline,
                # On fournit l’état du traitement via le paramètre status de cet appel.
                status="success",
                project_year=2026,
                # On transmet la sélection explicite des domaines concernés par cet appel.
                vineyards=[
                    dict(vineyard=name, status="success") for name in c.VINEYARDS
                ],
            )
            # Cette branche traite le cas où wrong_manifest est évalué comme vrai.
            if wrong_manifest:
                # On retire de manifest['vineyards'] l’élément demandé.
                manifest["vineyards"].pop()
            # On garde dans mb les octets de json.dumps(manifest) obtenus avec l’encodage indiqué.
            mb = json.dumps(manifest).encode()
            # On écrit le contenu préparé dans mp ; cette opération remplace le contenu du fichier s’il
            # existe déjà.
            mp.write_bytes(mb)
            # On rassemble dans seq les 1 éléments explicitement indiqués pour ce cas d’essai.
            seq = [("workflow", "workflow", "started")]
            # On parcourt c.STEPS ; step désigne l’élément courant de ce scénario.
            for step in c.STEPS:
                # On ajoute les éléments de [('step', step, 'started'), ('step', step, 'success')] à
                # seq ; on n’ajoute pas la collection comme un seul élément imbriqué.
                seq.extend([("step", step, "started"), ("step", step, "success")])
            # On ajoute ('workflow', 'workflow', 'success') à la fin de seq ; les éléments précédents
            # restent conservés.
            seq.append(("workflow", "workflow", "success"))
            # On construit events comme une liste à partir de dict(event_type=t, stage=s, status=z,
            # workflow_execution_id=data…, pour chaque (t, s, z) de seq.
            events = [
                dict(
                    event_type=t,
                    # On fournit l’étape concernée via le paramètre stage de cet appel.
                    stage=s,
                    # On fournit l’état du traitement via le paramètre status de cet appel.
                    status=z,
                    # On fournit l’identifiant de l’exécution du workflow via le paramètre
                    # workflow_execution_id de cet appel.
                    workflow_execution_id=data["workflow_execution_id"],
                    # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                    trigger_mode="airflow_manual",
                    # On fournit le périmètre détaillé enregistré via le paramètre scope_payload de cet
                    # appel.
                    scope_payload=c.scope(),
                    # On fournit le code du problème rencontré via le paramètre error_code de cet
                    # appel.
                    error_code=None,
                    # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de
                    # cet appel.
                    excel_publication_id=pub,
                    # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id
                    # de cet appel.
                    pipeline_execution_id=pipeline,
                    # On fournit les indicateurs détaillés enregistrés via le paramètre metrics_payload
                    # de cet appel.
                    metrics_payload={"completed_steps": 8},
                )
                for t, s, z in seq
            ]
            # On garde dans columns une séquence non modifiable construite à partir de events[0].
            columns = tuple(events[0])
            # On prépare calls comme liste vide ; on la remplira au fil des opérations suivantes.
            calls = []

            class Cursor:
                def __init__(self, rows):
                    # On gardes lignes sous le nom self.rows ; cette affectation ne copie pas à elle
                    # seule un objet mutable.
                    self.rows = rows

                def fetchall(self):
                    # On remet self.rows à l’appelant ; les étapes suivantes de cette fonction ne sont
                    # plus parcourues.
                    return self.rows

                def fetchone(self):
                    # On remet self.rows[0] à l’appelant ; les étapes suivantes de cette fonction ne
                    # sont plus parcourues.
                    return self.rows[0]

            class Connection:
                def __enter__(self):
                    # On remet self à l’appelant ; les étapes suivantes de cette fonction ne sont plus
                    # parcourues.
                    return self

                def __exit__(self, *args):
                    # On renvoie False comme résultat explicite de cette branche.
                    return False

                # On garde dans rollback un double de test dont les réponses et les appels pourront
                # être contrôlés.
                rollback = Mock()

                def execute(self, sql, params=None):
                    # On ajoute sql à la fin de calls ; les éléments précédents restent conservés.
                    calls.append(sql)
                    # Cette branche traite le cas où sql commence par le texte 'SET TRANSACTION'.
                    if sql.startswith("SET TRANSACTION"):
                        # On fournit à l’appelant la valeur renvoyée par Cursor.
                        return Cursor([])
                    # Cette branche traite le cas où sql commence par le texte 'SELECT
                    # current_database'.
                    if sql.startswith("SELECT current_database"):
                        # On fournit à l’appelant la valeur renvoyée par Cursor.
                        return Cursor(
                            [
                                (
                                    "suivi_acquisitions",
                                    "projet12_importer",
                                    "projet12_importer",
                                )
                            ]
                        )
                    # On vérifie ce cas avant la suite : le texte 'FROM core.workflow_execution_events'
                    # appartient à sql.
                    if "FROM core.workflow_execution_events" in sql:
                        # On fournit à l’appelant la valeur renvoyée par Cursor.
                        return Cursor([tuple(e[k] for k in columns) for e in events])
                    # On vérifie ce cas avant la suite : le texte 'FROM core.excel_current_publication'
                    # appartient à sql.
                    if "FROM core.excel_current_publication" in sql:
                        # On fournit à l’appelant la valeur renvoyée par Cursor.
                        return Cursor([(pub,)])
                    # On vérifie ce cas avant la suite : le texte 'FROM core.pipeline_runs' appartient
                    # à sql.
                    if "FROM core.pipeline_runs" in sql:
                        # On fournit à l’appelant la valeur renvoyée par Cursor.
                        return Cursor(
                            [
                                (
                                    2026,
                                    "success",
                                    pub,
                                    relative,
                                    hashlib.sha256(mb).hexdigest(),
                                    manifest,
                                )
                            ]
                        )
                    # On vérifie ce cas avant la suite : le texte 'FROM
                    # core.current_vineyard_reconciliations' appartient à sql.
                    if "FROM core.current_vineyard_reconciliations" in sql:
                        # Cette branche traite le cas où missing_vineyard est évalué comme vrai et
                        # params[0] correspond à c.VINEYARDS[-1].
                        if missing_vineyard and params[0] == c.VINEYARDS[-1]:
                            # On fournit à l’appelant la valeur renvoyée par Cursor.
                            return Cursor([])
                        # On fournit à l’appelant la valeur renvoyée par Cursor.
                        return Cursor(
                            [
                                (
                                    params[0].casefold(),
                                    "rec",
                                    pipeline,
                                    pipeline,
                                    pub,
                                    2,
                                    2,
                                    1,
                                )
                            ]
                        )
                    # On vérifie ce cas avant la suite : le texte 'SELECT COUNT(*) FROM staging.'
                    # appartient à sql.
                    if "SELECT COUNT(*) FROM staging." in sql:
                        # On fournit à l’appelant la valeur renvoyée par Cursor.
                        return Cursor(
                            [
                                (
                                    (
                                        999
                                        if bad_volume
                                        else (1 if "passage_rows" in sql else 2)
                                    ),
                                )
                            ]
                        )
                    # On interrompt cette branche avec AssertionError.
                    raise AssertionError("SQL inattendu : " + sql)

            # On garde dans conn la valeur renvoyée par Connection.
            conn = Connection()
            # On garde dans connect un double de test dont les réponses et les appels pourront être
            # contrôlés.
            connect = Mock(return_value=conn)
            # On regroupe dans mods ces champs nommés ; on pourra les retrouver par leur clé plutôt que
            # par leur position.
            mods = {
                # On associe la clé 'workflow_runtime' à cette valeur dans les données de ce scénario.
                "workflow_runtime": types.SimpleNamespace(
                    read_events=Mock(return_value=events)
                ),
                # On associe la clé 'workflow_journal_repository' à cette valeur dans les données de ce
                # scénario.
                "workflow_journal_repository": types.SimpleNamespace(
                    COLUMNS=columns, normalize_event=lambda e: e
                ),
                # On associe la clé 'import_connection_config' à cette valeur dans les données de ce
                # scénario.
                "import_connection_config": types.SimpleNamespace(
                    database_config=Mock(return_value={}), verify_import_identity=Mock()
                ),
                # On associe la clé 'psycopg' à cette valeur dans les données de ce scénario.
                "psycopg": types.SimpleNamespace(connect=connect),
            }
            # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera
            # rétabli à sa sortie.
            with (
                patch.dict(sys.modules, mods),
                patch.object(
                    checker,
                    "__file__",
                    str(root / "scripts/check_airflow_eight_result.py"),
                ),
                patch.dict(os.environ, {"PROJECT12_IMPORT_CONNECTION_MODE": "local"}),
                redirect_stdout(io.StringIO()),
            ):
                # On garde dans code la valeur renvoyée par checker.main.
                code = checker.main(["--receipt", str(rp)])
            # On vérifie que code correspond à 1 if bad_volume or missing_vineyard or wrong_manifest
            # else 0.
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                code, 1 if bad_volume or missing_vineyard or wrong_manifest else 0
            )
            # On prévoit le cas où wrong_manifest est évalué comme faux, par exemple une valeur vide
            # selon son type.
            if not wrong_manifest:
                # On contrôle le résultat avec assert_called et les valeurs attendues indiquées juste
                # dessous.
                conn.rollback.assert_called()
                # On vérifie que connect.call_args.kwargs['options'] correspond à '-c
                # default_transaction_read_only=on'.
                self.assertEqual(
                    # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                    connect.call_args.kwargs["options"],
                    # On fournit la valeur attendue ou la collection de comparaison pour cette
                    # assertion.
                    "-c default_transaction_read_only=on",
                )
            # On attend que all((q.startswith(('SELECT', 'SET TRANSACTION')) for q in calls)) soit
            # évalué comme vrai pour ce cas de test.
            self.assertTrue(
                all(q.startswith(("SELECT", "SET TRANSACTION")) for q in calls)
            )

    def test_eight_sql_results_confirmed(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise()

    def test_wrong_volume_refused(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise(bad_volume=True)

    def test_missing_active_vineyard_refused(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise(missing_vineyard=True)

    def test_manifest_missing_vineyard_refused(self):
        # On appelle self.exercise sans argument positionnel.
        self.exercise(wrong_manifest=True)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
