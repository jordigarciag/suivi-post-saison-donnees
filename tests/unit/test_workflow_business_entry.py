# Lecture du fichier — Tests de workflow business entry.
#

"""Tests de l'entree metier : configuration et processus fictifs, aucun NAS/SQL."""

# On importe contextlib. Ce module sera utilisé par les opérations de ce fichier.
import contextlib
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles SimpleNamespace depuis types, pour les appels de ce fichier.
from types import SimpleNamespace
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Mock, patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import Mock, patch

# On récupère Path(__file__).resolve().parents[2] et on le garde dans ROOT pour la suite.
ROOT = Path(__file__).resolve().parents[2]
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(ROOT / "scripts"))
# On importe run_workflow_business sous le nom entry. Ce module sera utilisé par les opérations de ce
# fichier.
import run_workflow_business as entry
# On importe workflow_runtime sous le nom runtime. Ce module sera utilisé par les opérations de ce
# fichier.
import workflow_runtime as runtime
# On rend disponibles BusinessPlan depuis workflow_business_wiring, pour les appels de ce fichier.
from workflow_business_wiring import BusinessPlan


class TestWorkflowBusinessEntry(unittest.TestCase):
    def setUp(self):
        # On garde dans temp un dossier temporaire distinct des données du projet.
        temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(temp.name)
        # On garde dans self.config un objet de test regroupant les attributs fournis.
        self.config = SimpleNamespace(
            # On fournit la racine locale du projet via le paramètre root de cet appel.
            root=self.root, importer={"password": "private-sentinel"}
        )
        # On garde dans self.action un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.action = Mock(return_value=None)
        # On garde dans self.sink un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.sink = Mock(return_value="inserted")
        # On garde dans self.plan la valeur renvoyée par BusinessPlan.
        self.plan = BusinessPlan(
            None, (("synthetic", self.action),), self.sink, ("Synthetic",), False, 2026
        )
        # On garde dans self.output un flux texte en mémoire, utilisable comme un fichier par le
        # lecteur CSV.
        self.output = io.StringIO()

    def execute(self, **kwargs):
        # On garde dans opts un nouveau dictionnaire construit avec les valeurs indiquées.
        opts = dict(
            # On fournit le domaine concerné via le paramètre vineyard de cet appel.
            vineyard="Synthetic", allow_business_writes=True, confirm_nas_read_only=True
        )
        # On complète opts avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        opts.update(kwargs)
        # On fournit à l’appelant la valeur renvoyée par entry.execute_business.
        return entry.execute_business(self.config, self.plan, **opts)

    def cli(self, args):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(
                # On fixe la réponse de ce double de test ; aucune vraie opération de la dépendance
                # n’est nécessaire pour obtenir cette valeur.
                entry, "load_business_configuration", return_value=self.config
            ),
            patch.object(entry, "build_business_plan", return_value=self.plan),
            contextlib.redirect_stdout(self.output),
            contextlib.redirect_stderr(self.output),
        ):
            # On fournit à l’appelant la valeur renvoyée par entry.main.
            return entry.main(args)

    def test_runtime_preflight_runs_under_lock_before_journal(self):
        # On prépare order comme liste vide ; on la remplira au fil des opérations suivantes.
        order = []

        # On réalise les contrôles préalables avant d’autoriser le lancement des étapes métier.
        def preflight(ctx):
            # On attend que (self.root / runtime.LOCK_RELATIVE).is_file() soit évalué comme vrai pour
            # ce cas de test.
            self.assertTrue((self.root / runtime.LOCK_RELATIVE).is_file())
            # On attend que (self.root / runtime.RUNS_RELATIVE).exists() soit évalué comme faux pour ce
            # cas de test.
            self.assertFalse((self.root / runtime.RUNS_RELATIVE).exists())
            # On ajoute 'diagnostic' à la fin de order ; les éléments précédents restent conservés.
            order.append("diagnostic")

        # On garde dans result la valeur renvoyée par runtime.run_workflow.
        result = runtime.run_workflow(
            self.root,
            [("step", lambda c: order.append("action"))],
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="manual_script",
            # On fournit le périmètre du traitement via le paramètre scope de cet appel.
            scope={},
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            journal_sink=lambda e: order.append("journal"),
            # On fournit le contrôle qui doit passer sous verrou avant le démarrage des étapes.
            preflight=preflight,
        )
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que order[0] correspond à 'diagnostic'.
        self.assertEqual(order[0], "diagnostic")
        # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.LOCK_RELATIVE).exists())

    def test_runtime_failed_preflight_creates_no_journal_and_calls_no_action(self):
        # On garde dans before un double de test dont les réponses et les appels pourront être
        # contrôlés.
        before = Mock(side_effect=RuntimeError("private-sentinel"))
        # On attend RuntimeError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(RuntimeError):
            # On appelle runtime.run_workflow avec self.root.
            runtime.run_workflow(
                self.root,
                [("step", self.action)],
                # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                trigger_mode="manual_script",
                # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                scope={},
                # On fournit le destinataire des événements du workflow ; ce n’est pas la base
                # technique des runs Airflow.
                journal_sink=self.sink,
                # On fournit le contrôle qui doit passer sous verrou avant le démarrage des étapes.
                preflight=before,
            )
        # On vérifie que self.action n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.action.assert_not_called()
        # On vérifie que self.sink n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.sink.assert_not_called()
        # On attend que (self.root / runtime.RUNS_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.RUNS_RELATIVE).exists())
        # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.LOCK_RELATIVE).exists())

    def test_runtime_busy_blocks_preflight(self):
        # On prend le verrou avant les contrôles et les étapes ; sa libération est gérée en sortant
        # du bloc, sans permettre à deux runs locaux du partager.
        with runtime.workflow_lock(self.root, "00000000-0000-0000-0000-000000000001"):
            # On garde dans preflight un double de test dont les réponses et les appels pourront être
            # contrôlés.
            preflight = Mock()
            # On attend runtime.WorkflowBusy dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(runtime.WorkflowBusy):
                # On appelle runtime.run_workflow avec self.root.
                runtime.run_workflow(
                    self.root,
                    [("step", self.action)],
                    # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                    trigger_mode="manual_script",
                    # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                    scope={},
                    # On fournit le contrôle qui doit passer sous verrou avant le démarrage des étapes.
                    preflight=preflight,
                )
            # On vérifie que preflight n’a pas été appelé : le refus doit intervenir avant cette
            # opération.
            preflight.assert_not_called()

    def test_runtime_invalid_preflight_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle runtime.run_workflow avec self.root.
            runtime.run_workflow(
                self.root,
                [("step", self.action)],
                # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                trigger_mode="manual_script",
                # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                scope={},
                # On fournit le contrôle qui doit passer sous verrou avant le démarrage des étapes.
                preflight="invalid",
            )
        # On attend que (self.root / 'state').exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.root / "state").exists())

    def test_business_diagnostic_before_sink_and_action(self):
        # On prépare order comme liste vide ; on la remplira au fil des opérations suivantes.
        order = []
        # On prépare pour self.action.side_effect une fonction courte ; elle ne sera exécutée que
        # lorsqu’elle sera appelée, pas lors de cette affectation.
        self.action.side_effect = lambda ctx: order.append("action")
        # On prépare pour self.sink.side_effect une fonction courte ; elle ne sera exécutée que
        # lorsqu’elle sera appelée, pas lors de cette affectation.
        self.sink.side_effect = lambda event: order.append("journal")
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(
            entry,
            "diagnose_importer",
            # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
            # suivre une fonction de test.
            side_effect=lambda cfg: order.append("diagnostic"),
        ):
            # On garde dans result le résultat de l’appel encadré par ce scénario de test.
            result = self.execute()
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que order[0] correspond à 'diagnostic'.
        self.assertEqual(order[0], "diagnostic")
        # On garde dans events la valeur renvoyée par runtime.read_events.
        events = runtime.read_events(self.root / result["journal_relative_path"])
        # On vérifie que events[0]['scope_payload']['execution_kind'] correspond à 'business'.
        self.assertEqual(events[0]["scope_payload"]["execution_kind"], "business")
        # On vérifie que events[0]['scope_payload']['vineyards'] correspond à ['Synthetic'].
        self.assertEqual(events[0]["scope_payload"]["vineyards"], ["Synthetic"])

    def test_business_failed_diagnostic_stops_before_journal_and_action(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(
            entry,
            "diagnose_importer",
            # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
            # suivre une fonction de test.
            side_effect=entry.ImporterDiagnosticError("IMPORT_DIAGNOSTIC_FAILED"),
        ):
            # On attend entry.ImporterDiagnosticError dans ce bloc ; si aucune erreur n’est levée, le
            # test doit échouer.
            with self.assertRaises(entry.ImporterDiagnosticError):
                # On lance l’opération prévue par self.execute avec les paramètres de ce cas.
                self.execute()
        # On vérifie que self.sink n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.sink.assert_not_called()
        # On vérifie que self.action n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.action.assert_not_called()

    def test_business_both_authorizations_required(self):
        # On parcourt ('allow_business_writes', 'confirm_nas_read_only') ; key désigne l’élément
        # courant de ce scénario.
        for key in ("allow_business_writes", "confirm_nas_read_only"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(key=key):
                # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera
                # rétabli à sa sortie.
                with patch.object(entry, "diagnose_importer") as diagnose:
                    # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                    # échouer.
                    with self.assertRaises(ValueError):
                        # On lance l’opération prévue par self.execute avec les paramètres de ce cas.
                        self.execute(**{key: False})
                    # On vérifie que diagnose n’a pas été appelé : le refus doit intervenir avant
                    # cette opération.
                    diagnose.assert_not_called()
        # On attend que (self.root / 'state').exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.root / "state").exists())

    def test_business_wrong_plan_scope_refused(self):
        # On parcourt (BusinessPlan(None, self.plan.steps, self.sink, ('Other',), False, 2026),… ; plan
        # désigne l’élément courant de ce scénario.
        for plan in (
            BusinessPlan(None, self.plan.steps, self.sink, ("Other",), False, 2026),
            BusinessPlan(None, self.plan.steps, self.sink, (), True, 2026),
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(plan=plan):
                # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera
                # rétabli à sa sortie.
                with patch.object(entry, "diagnose_importer") as diagnose:
                    # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                    # échouer.
                    with self.assertRaises(ValueError):
                        # On appelle entry.execute_business avec self.config.
                        entry.execute_business(
                            self.config,
                            plan,
                            # On fournit le domaine concerné via le paramètre vineyard de cet appel.
                            vineyard="Synthetic",
                            allow_business_writes=True,
                            confirm_nas_read_only=True,
                        )
                # On vérifie que diagnose n’a pas été appelé : le refus doit intervenir avant cette
                # opération.
                diagnose.assert_not_called()

    def test_business_wrong_year_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On lance l’opération prévue par self.execute avec les paramètres de ce cas.
            self.execute(year=2025)
        # On vérifie que self.action n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.action.assert_not_called()

    def test_checker_reused_and_rollback_on_success(self):
        # On garde dans connection un double de test dont les réponses et les appels pourront être
        # contrôlés.
        connection = Mock()
        # On garde dans checker un objet de test regroupant les attributs fournis.
        checker = SimpleNamespace(check=Mock(return_value=(8, 522, 478)))

        # On fournit la ressource ouverte dans le contexte prévu et on en gère la sortie.
        @contextlib.contextmanager
        def opened(cfg):
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield connection

        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(entry, "_project_module", return_value=checker),
            patch.object(entry, "diagnostic_connection", side_effect=opened),
        ):
            # On vérifie que entry.diagnose_importer(self.config) correspond à (8, 522, 478).
            self.assertEqual(entry.diagnose_importer(self.config), (8, 522, 478))
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        checker.check.assert_called_once_with(connection)
        # On attend un seul appel à connection.rollback dans ce scénario, ni zéro ni plusieurs.
        connection.rollback.assert_called_once()

    def test_checker_rollback_on_failure_no_raw_secret(self):
        # On garde dans connection un double de test dont les réponses et les appels pourront être
        # contrôlés.
        connection = Mock()
        # On garde dans checker un objet de test regroupant les attributs fournis.
        checker = SimpleNamespace(
            # Ce réglage décide si un code de sortie non nul lève directement une exception dans cet
            # appel.
            check=Mock(side_effect=ValueError("private-sentinel"))
        )

        # On fournit la ressource ouverte dans le contexte prévu et on en gère la sortie.
        @contextlib.contextmanager
        def opened(cfg):
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield connection

        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(entry, "_project_module", return_value=checker),
            patch.object(entry, "diagnostic_connection", side_effect=opened),
        ):
            # On attend entry.ImporterDiagnosticError dans ce bloc ; si aucune erreur n’est levée, le
            # test doit échouer.
            with self.assertRaises(entry.ImporterDiagnosticError) as error:
                # On appelle entry.diagnose_importer avec self.config.
                entry.diagnose_importer(self.config)
        # On attend un seul appel à connection.rollback dans ce scénario, ni zéro ni plusieurs.
        connection.rollback.assert_called_once()
        # On vérifie que 'private-sentinel' ne figure pas dans str(error.exception).
        self.assertNotIn("private-sentinel", str(error.exception))

    def test_diagnostic_connection_uses_transactional_importer_config(self):
        # On garde dans connect un double de test dont les réponses et les appels pourront être
        # contrôlés.
        connect = Mock()
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(sys.modules, {"psycopg": SimpleNamespace(connect=connect)}):
            # On appelle entry.diagnostic_connection avec self.config.
            entry.diagnostic_connection(self.config)
        # On vérifie l’identité de connect.call_args.kwargs['autocommit'] avec False, et pas
        # seulement une égalité de valeur.
        self.assertIs(connect.call_args.kwargs["autocommit"], False)
        # On vérifie que connect.call_args.kwargs['password'] correspond à 'private-sentinel'.
        self.assertEqual(connect.call_args.kwargs["password"], "private-sentinel")

    def test_checker_connection_context_closed_after_refusal(self):
        # On garde dans connection un double de test dont les réponses et les appels pourront être
        # contrôlés.
        connection = Mock()
        # On prépare closed comme liste vide ; on la remplira au fil des opérations suivantes.
        closed = []
        # On garde dans checker un objet de test regroupant les attributs fournis.
        checker = SimpleNamespace(
            # Ce réglage décide si un code de sortie non nul lève directement une exception dans cet
            # appel.
            check=Mock(side_effect=ValueError("synthetic-failure"))
        )

        # On fournit la ressource ouverte dans le contexte prévu et on en gère la sortie.
        @contextlib.contextmanager
        def opened(cfg):
            # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
            try:
                # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra
                # après ce point si son itération continue.
                yield connection
            finally:
                # On ajoute True à la fin de closed ; les éléments précédents restent conservés.
                closed.append(True)

        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(entry, "_project_module", return_value=checker),
            patch.object(entry, "diagnostic_connection", side_effect=opened),
        ):
            # On attend entry.ImporterDiagnosticError dans ce bloc ; si aucune erreur n’est levée, le
            # test doit échouer.
            with self.assertRaises(entry.ImporterDiagnosticError):
                # On appelle entry.diagnose_importer avec self.config.
                entry.diagnose_importer(self.config)
        # On vérifie que closed correspond à [True].
        self.assertEqual(closed, [True])
        # On attend un seul appel à connection.rollback dans ce scénario, ni zéro ni plusieurs.
        connection.rollback.assert_called_once()

    def test_cli_missing_authorizations_refused_before_config(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(entry, "load_business_configuration") as load,
            contextlib.redirect_stderr(self.output),
        ):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle entry.main avec ['--run', '--vineyard', 'Synthetic'].
                entry.main(["--run", "--vineyard", "Synthetic"])
        # On vérifie que load n’a pas été appelé dans ce scénario.
        load.assert_not_called()

    def test_cli_all_vineyards_run_refused(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(entry, "load_business_configuration") as load,
            contextlib.redirect_stderr(self.output),
        ):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle entry.main avec ['--run', '--all-vineyards', '--allow-business-writes',
                # '--confirm-nas-read-only'].
                entry.main(
                    [
                        "--run",
                        "--all-vineyards",
                        "--allow-business-writes",
                        "--confirm-nas-read-only",
                    ]
                )
        # On vérifie que load n’a pas été appelé dans ce scénario.
        load.assert_not_called()

    def test_cli_diagnostic_does_not_execute_plan_or_sink(self):
        def diagnose(cfg):
            # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme vrai pour ce
            # cas de test.
            self.assertTrue((self.root / runtime.LOCK_RELATIVE).exists())
            # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return (8, 522, 478)

        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(entry, "diagnose_importer", side_effect=diagnose):
            # On garde dans codu code et les sorties du point d’entrée appelé par ce scénario.
            code = self.cli(["--diagnostic-only", "--all-vineyards"])
        # On vérifie que code correspond à 0.
        self.assertEqual(code, 0)
        # On vérifie que self.action n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.action.assert_not_called()
        # On vérifie que self.sink n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.sink.assert_not_called()
        # On attend que (self.root / runtime.RUNS_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.RUNS_RELATIVE).exists())
        # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.LOCK_RELATIVE).exists())
        # On vérifie que 'private-sentinel' ne figure pas dans self.output.getvalue().
        self.assertNotIn("private-sentinel", self.output.getvalue())

    def test_cli_failed_diagnostic_no_business_start(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(
            entry,
            "diagnose_importer",
            # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
            # suivre une fonction de test.
            side_effect=entry.ImporterDiagnosticError("IMPORT_DIAGNOSTIC_FAILED"),
        ):
            # On garde dans codu code et les sorties du point d’entrée appelé par ce scénario.
            code = self.cli(["--diagnostic-only", "--all-vineyards"])
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que self.action n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.action.assert_not_called()
        # On vérifie que self.sink n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.sink.assert_not_called()

    def test_cli_no_implicit_mode(self):
        # On utilise contextlib.redirect_stderr(self.output) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with contextlib.redirect_stderr(self.output):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle entry.main avec ['--vineyard', 'Synthetic'].
                entry.main(["--vineyard", "Synthetic"])

    def test_cli_diagnostic_rejects_run_confirmation_flags(self):
        # On utilise contextlib.redirect_stderr(self.output) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with contextlib.redirect_stderr(self.output):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle entry.main avec ['--diagnostic-only', '--all-vineyards',
                # '--allow-business-writes'].
                entry.main(
                    ["--diagnostic-only", "--all-vineyards", "--allow-business-writes"]
                )

    def test_cli_successful_run_returns_zero(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(entry, "diagnose_importer", return_value=(8, 522, 478)):
            # On garde dans codu code et les sorties du point d’entrée appelé par ce scénario.
            code = self.cli(
                [
                    "--run",
                    "--vineyard",
                    "Synthetic",
                    "--allow-business-writes",
                    "--confirm-nas-read-only",
                ]
            )
        # On vérifie que code correspond à 0.
        self.assertEqual(code, 0)
        # On attend un seul appel à self.action dans ce scénario, ni zéro ni plusieurs.
        self.action.assert_called_once()
        # On vérifie que 'RESULTAT METIER : success' figure dans self.output.getvalue().
        self.assertIn("RESULTAT METIER : success", self.output.getvalue())

    def test_cli_failed_step_returns_nonzero_and_keeps_local_journal(self):
        # On garde dans self.action.side_effect la valeur renvoyée par RuntimeError pour
        # 'private-sentinel'.
        self.action.side_effect = RuntimeError("private-sentinel")
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(entry, "diagnose_importer", return_value=(8, 522, 478)):
            # On garde dans codu code et les sorties du point d’entrée appelé par ce scénario.
            code = self.cli(
                [
                    "--run",
                    "--vineyard",
                    "Synthetic",
                    "--allow-business-writes",
                    "--confirm-nas-read-only",
                ]
            )
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que 'private-sentinel' ne figure pas dans self.output.getvalue().
        self.assertNotIn("private-sentinel", self.output.getvalue())
        # On vérifie que len(list((self.root / runtime.RUNS_RELATIVE).glob('*/events.jsonl')))
        # correspond à 1.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            len(list((self.root / runtime.RUNS_RELATIVE).glob("*/events.jsonl"))), 1
        )

    def test_invalid_vineyard_refused(self):
        # On parcourt ('', 'bad/name', 'bad\nname', None) ; name désigne l’élément courant de ce
        # scénario.
        for name in ("", "bad/name", "bad\nname", None):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(name=name):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle entry.validate_one_vineyard avec name.
                    entry.validate_one_vineyard(name)

    def test_cli_exception_redacted(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(
                entry,
                "load_business_configuration",
                # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
                # suivre une fonction de test.
                side_effect=RuntimeError("private-sentinel"),
            ),
            contextlib.redirect_stdout(self.output),
        ):
            # On garde dans code la valeur renvoyée par entry.main.
            code = entry.main(["--diagnostic-only", "--all-vineyards"])
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que 'private-sentinel' ne figure pas dans self.output.getvalue().
        self.assertNotIn("private-sentinel", self.output.getvalue())

    def test_cli_interrupt_not_success(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(entry, "diagnose_importer", side_effect=KeyboardInterrupt):
            # On garde dans codu code et les sorties du point d’entrée appelé par ce scénario.
            code = self.cli(["--diagnostic-only", "--all-vineyards"])
        # On vérifie que code correspond à 130.
        self.assertEqual(code, 130)
        # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.LOCK_RELATIVE).exists())
