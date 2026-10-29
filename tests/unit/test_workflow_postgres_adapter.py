# Lecture du fichier — Tests de workflow postgres adapter.
#

"""Tests simules : aucune connexion PostgreSQL, aucun NAS, aucun .env."""

# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On sépare les copies d’objets, notamment pour comparer un état avant et après une opération.
import copy
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles SimpleNamespace depuis types, pour les appels de ce fichier.
from types import SimpleNamespace
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Mock, patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import Mock, patch

# On récupère Path(__file__).resolve().parents[2] et on le garde dans ROOT pour la suite.
ROOT = Path(__file__).resolve().parents[2]
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(ROOT / "scripts"))
# On importe workflow_postgres_adapter sous le nom adapter. Ce module sera utilisé par les opérations
# de ce fichier.
import workflow_postgres_adapter as adapter
# On rend disponibles run_workflow, read_events, replay_events, JournalDeliveryError depuis
# workflow_runtime, pour les appels de ce fichier.
from workflow_runtime import (
    run_workflow,
    read_events,
    replay_events,
    JournalDeliveryError,
)
# On importe test_workflow_nas_adapter sous le nom nas_fixture. Ce module sera utilisé par les
# opérations de ce fichier.
import test_workflow_nas_adapter as nas_fixture


class TestWorkflowPostgresAdapter(unittest.TestCase):
    def setUp(self):
        # On garde dans self.fixture la valeur renvoyée par nas_fixture.TestWorkflowNasAdapter.
        self.fixture = nas_fixture.TestWorkflowNasAdapter()
        # On initialise les ressources du scénario self.fixture avec sa méthode setUp.
        self.fixture.setUp()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.fixture.doCleanups)
        # On garde self.fixture.root sous le nom self.root ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        self.root = self.fixture.root
        # On prépare self.calls comme liste vide ; on la remplira au fil des opérations suivantes.
        self.calls = []
        # On garde dans self.excel un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.excel = Mock(side_effect=lambda b, r: self.calls.append("excel"))
        # On garde dans self.nas un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.nas = Mock(side_effect=lambda b, r: self.calls.append("nas"))
        # On garde dans self.excel_repo la valeur renvoyée par object.
        self.excel_repo = object()
        # On garde dans self.nas_repo la valeur renvoyée par object.
        self.nas_repo = object()

    @contextmanager
    def excel_repository(self):
        # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après ce
        # point si son itération continue.
        yield self.excel_repo

    @contextmanager
    def nas_repository(self):
        # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après ce
        # point si son itération continue.
        yield self.nas_repo

    def nas_guard(self, ctx):
        # On rend disponibles assert_nas_snapshot depuis workflow_nas_adapter, pour les appels de ce
        # fichier.
        from workflow_nas_adapter import assert_nas_snapshot

        # On fournit à l’appelant la valeur renvoyée par assert_nas_snapshot.
        return assert_nas_snapshot(
            ctx,
            # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
            ensure_excel=self.fixture.excel_guard,
            # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
            ensure_nas=self.fixture.files_mock,
        )

    def steps(self):
        # On fournit à l’appelant la valeur renvoyée par adapter.build_import_steps.
        return adapter.build_import_steps(
            self.root,
            excel_repository=self.excel_repository,
            nas_repository=self.nas_repository,
            import_excel=self.excel,
            import_nas=self.nas,
            # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
            ensure_excel=self.fixture.excel_guard,
            # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
            ensure_nas=self.nas_guard,
        )

    def flow(self, *, steps=None, sink=None):
        # On assemble ces deux éléments pour construire actions.
        actions = (
            self.fixture.excel_steps()
            + self.fixture.nas_steps()
            + (self.steps() if steps is None else steps)
        )
        # On fournit à l’appelant le bilan du parcours après l’appel de ses étapes et de son journal.
        return run_workflow(
            self.root,
            actions,
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="integration_test",
            # On fournit le périmètre du traitement via le paramètre scope de cet appel.
            scope={"year": 2026},
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            journal_sink=sink,
        )

    def test_success_loads_exact_bundles_in_order(self):
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow()
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que self.calls correspond à ['excel', 'nas'].
        self.assertEqual(self.calls, ["excel", "nas"])
        # On vérifie l’identité de self.excel.call_args.args[0] avec self.fixture.excel_bundle, et
        # pas seulement une égalité de valeur.
        self.assertIs(self.excel.call_args.args[0], self.fixture.excel_bundle)
        # On vérifie l’identité de self.excel.call_args.args[1] avec self.excel_repo, et pas
        # seulement une égalité de valeur.
        self.assertIs(self.excel.call_args.args[1], self.excel_repo)
        # On vérifie l’identité de self.nas.call_args.args[1] avec self.nas_repo, et pas seulement
        # une égalité de valeur.
        self.assertIs(self.nas.call_args.args[1], self.nas_repo)
        # On vérifie que self.nas.call_args.args[0]['report']['pipeline_execution_id'] correspond à
        # self.fixture.execution.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.nas.call_args.args[0]["report"]["pipeline_execution_id"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            self.fixture.execution,
        )

    def test_failed_excel_blocks_nas(self):
        # On garde dans self.excel.side_effect la valeur renvoyée par RuntimeError pour
        # 'private-password'.
        self.excel.side_effect = RuntimeError("private-password")
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow()
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que self.nas n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.nas.assert_not_called()
        # On vérifie que 'excel_import' ne figure pas dans result['completed_steps'].
        self.assertNotIn("excel_import", result["completed_steps"])
        # On vérifie que 'private-password' ne figure pas dans (self.root /
        # result['journal_relative_path']).read_text().
        self.assertNotIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "private-password",
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            (self.root / result["journal_relative_path"]).read_text(),
        )

    def test_failed_nas_keeps_confirmed_excel_step(self):
        # On garde dans self.nas.side_effect la valeur renvoyée par RuntimeError pour
        # 'private-password'.
        self.nas.side_effect = RuntimeError("private-password")
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow()
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que 'excel_import' figure dans result['completed_steps'].
        self.assertIn("excel_import", result["completed_steps"])
        # On vérifie que 'nas_import' ne figure pas dans result['completed_steps'].
        self.assertNotIn("nas_import", result["completed_steps"])
        # On vérifie que self.excel.call_count correspond à 1.
        self.assertEqual(self.excel.call_count, 1)

    def test_nas_cannot_run_before_excel(self):
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow(steps=[self.steps()[1]])
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que self.nas n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.nas.assert_not_called()

    def test_wrong_excel_receipt_blocks_nas(self):
        def wrong(ctx):
            # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver
            # chaque information par sa clé.
            return {"status": "success", "excel_publication_id": "other"}

        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow(steps=[("excel_import", wrong), self.steps()[1]])
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que self.nas n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.nas.assert_not_called()

    def test_changed_reference_before_import_blocks_writes(self):
        def mutate(ctx):
            # On écrit le contenu préparé dans self.fixture.reference ; cette opération remplace le
            # contenu du fichier s’il existe déjà.
            self.fixture.reference.write_bytes(b"changed")

        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow(steps=[("mutate", mutate)] + self.steps())
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que self.excel n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.excel.assert_not_called()

    def test_changed_manifest_before_import_blocks_excel_too(self):
        def mutate(ctx):
            # On écrit le contenu préparé dans self.fixture.manifest ; cette opération remplace le
            # contenu du fichier s’il existe déjà.
            self.fixture.manifest.write_text("{}")

        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow(steps=[("mutate", mutate)] + self.steps())
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que self.excel n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.excel.assert_not_called()

    def test_guard_rechecked_after_repository_open(self):
        @contextmanager
        def altered():
            # On écrit le contenu préparé dans self.fixture.reference ; cette opération remplace le
            # contenu du fichier s’il existe déjà.
            self.fixture.reference.write_bytes(b"changed")
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield object()

        # On garde dans steps la valeur renvoyée par adapter.build_import_steps.
        steps = adapter.build_import_steps(
            self.root,
            excel_repository=altered,
            nas_repository=self.nas_repository,
            import_excel=self.excel,
            import_nas=self.nas,
            # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
            ensure_excel=self.fixture.excel_guard,
            # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
            ensure_nas=self.nas_guard,
        )
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow(steps=steps)
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que self.excel n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.excel.assert_not_called()

    def test_explicit_factories_required(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle adapter.build_import_steps avec self.root.
            adapter.build_import_steps(
                self.root, excel_repository=None, nas_repository=self.nas_repository
            )

    def test_other_project_context_refused(self):
        # On rend disponibles WorkflowContext depuis workflow_runtime, pour les appels de ce fichier.
        from workflow_runtime import WorkflowContext

        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.steps()[0][1] avec WorkflowContext(ROOT, 'unused').
            self.steps()[0][1](WorkflowContext(ROOT, "unused"))
        # On vérifie que self.excel n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.excel.assert_not_called()

    def test_interrupt_stops_following_load(self):
        # On garde KeyboardInterrupt sous le nom self.excel.side_effect ; cette affectation ne copie
        # pas à elle seule un objet mutable.
        self.excel.side_effect = KeyboardInterrupt
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow()
        # On vérifie que result['status'] correspond à 'interrupted'.
        self.assertEqual(result["status"], "interrupted")
        # On vérifie que self.nas n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.nas.assert_not_called()

    def journal_sink(self, write):
        # On fournit la ressource ouverte dans le contexte prévu et on en gère la sortie.
        @contextmanager
        def opened():
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield object()

        # On fournit à l’appelant la valeur renvoyée par adapter.build_journal_sink.
        return adapter.build_journal_sink(ROOT, opened=opened, append=write)

    def test_journal_passes_same_event_to_existing_contract(self):
        # On prépare sent comme liste vide ; on la remplira au fil des opérations suivantes.
        sent = []
        # On garde dans sink la valeur renvoyée par self.journal_sink.
        sink = self.journal_sink(
            lambda c, e: sent.append(copy.deepcopy(e)) or "inserted"
        )
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow(sink=sink)
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On garde dans events les événements du journal local après validation de leur ordre et de
        # leur identité.
        events = read_events(self.root / result["journal_relative_path"])
        # On vérifie que sent correspond à events.
        self.assertEqual(sent, events)
        # On vérifie que sent[-1]['excel_publication_id'] correspond à self.fixture.pub_id.
        self.assertEqual(sent[-1]["excel_publication_id"], self.fixture.pub_id)
        # On vérifie que sent[-1]['pipeline_execution_id'] correspond à self.fixture.execution.
        self.assertEqual(sent[-1]["pipeline_execution_id"], self.fixture.execution)

    def test_journal_failure_at_start_blocks_all_actions(self):
        # On garde dans sink la valeur renvoyée par self.journal_sink.
        sink = self.journal_sink(Mock(side_effect=RuntimeError("private-password")))
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow(sink=sink)
        # On vérifie que result['error_code'] correspond à 'JOURNAL_DELIVERY_UNCONFIRMED'.
        self.assertEqual(result["error_code"], "JOURNAL_DELIVERY_UNCONFIRMED")
        # On vérifie que self.fixture.execute_mock n’a pas été appelé : le refus doit intervenir
        # avant cette opération.
        self.fixture.execute_mock.assert_not_called()
        # On vérifie que self.excel n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.excel.assert_not_called()

    def test_journal_failure_after_excel_keeps_completed_step(self):
        def write(c, e):
            # Cette branche traite le cas où l’étape concernée dans e correspond au texte
            # 'excel_import' et l’état du traitement dans e correspond au texte 'success'.
            if e["stage"] == "excel_import" and e["status"] == "success":
                # On interrompt cette branche avec RuntimeError : 'private-password'.
                raise RuntimeError("private-password")
            # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
            return "inserted"

        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow(sink=self.journal_sink(write))
        # On vérifie que result['error_code'] correspond à 'JOURNAL_DELIVERY_UNCONFIRMED'.
        self.assertEqual(result["error_code"], "JOURNAL_DELIVERY_UNCONFIRMED")
        # On vérifie que 'excel_import' figure dans result['completed_steps'].
        self.assertIn("excel_import", result["completed_steps"])
        # On vérifie que self.nas n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.nas.assert_not_called()
        # On vérifie que 'private-password' ne figure pas dans (self.root /
        # result['journal_relative_path']).read_text().
        self.assertNotIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "private-password",
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            (self.root / result["journal_relative_path"]).read_text(),
        )

    def test_explicit_replay_preserves_ids_dates_and_local_file(self):
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow()
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.root / result["journal_relative_path"]
        # On garde dans before les octets lus depuis path, avant toute conversion en texte. Les
        # contrôles de contenu pourront ainsi repartir de cette lecture.
        before = path.read_bytes()
        # On prépare sent comme liste vide ; on la remplira au fil des opérations suivantes.
        sent = []
        # On garde dans sink la valeur renvoyée par self.journal_sink.
        sink = self.journal_sink(lambda c, e: sent.append(copy.deepcopy(e)) or "reused")
        # On garde dans count la valeur renvoyée par replay_events.
        count = replay_events(path, sink)
        # On vérifie que count correspond à len(read_events(path)).
        self.assertEqual(count, len(read_events(path)))
        # On vérifie que sent correspond à read_events(path).
        self.assertEqual(sent, read_events(path))
        # On vérifie que path.read_bytes() correspond à before.
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_event_refused_before_open(self):
        # On garde dans opened un double de test dont les réponses et les appels pourront être
        # contrôlés.
        opened = Mock()
        # On garde dans sink la valeur renvoyée par adapter.build_journal_sink.
        sink = adapter.build_journal_sink(ROOT, opened=opened, append=Mock())
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle sink avec {}.
            sink({})
        # On vérifie que opened n’a pas été appelé dans ce scénario.
        opened.assert_not_called()

    def test_unconfirmed_journal_result_fails_delivery(self):
        # On garde dans result le résultat du parcours préparé par ce helper de test.
        result = self.flow(sink=self.journal_sink(lambda c, e: "unknown"))
        # On vérifie que result['error_code'] correspond à 'JOURNAL_DELIVERY_UNCONFIRMED'.
        self.assertEqual(result["error_code"], "JOURNAL_DELIVERY_UNCONFIRMED")

    def connection(self, identity=None, attributes=None, autocommit=True, state=0):
        # On garde dans c un double de test dont les réponses et les appels pourront être contrôlés.
        c = Mock()
        # On garde autocommit sous le nom c.autocommit ; cette affectation ne copie pas à elle seule un
        # objet mutable.
        c.autocommit = autocommit
        # On garde dans c.info un objet de test regroupant les attributs fournis.
        c.info = SimpleNamespace(transaction_status=state)
        # On rassemble dans c.execute.return_value.fetchone.side_effect les 2 éléments explicitement
        # indiqués pour ce cas d’essai.
        c.execute.return_value.fetchone.side_effect = [
            identity or ("suivi_acquisitions", adapter.USER, adapter.USER),
            attributes if attributes is not None else (False,) * 5,
        ]
        # On remet c à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
        return c

    def test_valid_importer_connection_closed(self):
        # On garde dans c la connexion de test fournie par ce helper.
        c = self.connection()
        # On utilise adapter.connection_scope(lambda: c, 'suivi_acquisitions')() dans son contexte de
        # gestion ; les opérations de sortie sont exécutées en quittant le bloc.
        with adapter.connection_scope(lambda: c, "suivi_acquisitions")() as received:
            # On vérifie l’identité de received avec c, et pas seulement une égalité de valeur.
            self.assertIs(received, c)
        # On attend un seul appel à c.close dans ce scénario, ni zéro ni plusieurs.
        c.close.assert_called_once()

    def test_admin_or_session_identity_rejected_and_closed(self):
        # On parcourt [('suivi_acquisitions', 'projet12_admin', 'projet12_admin'), ('suivi_acqu… ;
        # identity désigne l’élément courant de ce scénario.
        for identity in [
            ("suivi_acquisitions", "projet12_admin", "projet12_admin"),
            ("suivi_acquisitions", adapter.USER, "projet12_admin"),
        ]:
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(identity=identity):
                # On garde dans c la connexion de test fournie par ce helper.
                c = self.connection(identity=identity)
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On utilise adapter.connection_scope(lambda: c, 'suivi_acquisitions')() dans son
                    # contexte de gestion ; les opérations de sortie sont exécutées en quittant le
                    # bloc.
                    with adapter.connection_scope(lambda: c, "suivi_acquisitions")():
                        # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce
                        # bloc.
                        pass
                # On attend un seul appel à c.close dans ce scénario, ni zéro ni plusieurs.
                c.close.assert_called_once()

    def test_other_database_rejected(self):
        # On garde dans c la connexion de test fournie par ce helper.
        c = self.connection(identity=("airflow_meta", adapter.USER, adapter.USER))
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle adapter.verify_connection avec c.
            adapter.verify_connection(c, "suivi_acquisitions")

    def test_privileged_importer_rejected(self):
        # On garde dans c la connexion de test fournie par ce helper.
        c = self.connection(attributes=(False, True, False, False, False))
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle adapter.verify_connection avec c.
            adapter.verify_connection(c, "suivi_acquisitions")

    def test_external_transaction_rejected_before_query(self):
        # On parcourt [(False, 0), (True, 2)] ; (autocommit, state) désigne l’élément courant de ce
        # scénario.
        for autocommit, state in [(False, 0), (True, 2)]:
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(autocommit=autocommit, state=state):
                # On garde dans c la connexion de test fournie par ce helper.
                c = self.connection(autocommit=autocommit, state=state)
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle adapter.verify_connection avec c.
                    adapter.verify_connection(c, "suivi_acquisitions")
                # On vérifie que c.execute n’a pas été appelé : le refus doit intervenir avant cette
                # opération.
                c.execute.assert_not_called()

    def test_allowed_synthetic_database_identity(self):
        # On utilise ce texte pour db ; il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        db = "suivi_acquisitions_import_test_synthetic"
        # On garde dans c la connexion de test fournie par ce helper.
        c = self.connection(identity=(db, adapter.USER, adapter.USER))
        # On appelle adapter.verify_connection avec c.
        adapter.verify_connection(c, db)

    def test_arbitrary_expected_database_rejected_without_open(self):
        # On garde dans connect un double de test dont les réponses et les appels pourront être
        # contrôlés.
        connect = Mock()
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle adapter.connection_scope avec connect.
            adapter.connection_scope(connect, "airflow_meta")
        # On vérifie que connect n’a pas été appelé dans ce scénario.
        connect.assert_not_called()

    def test_connection_closed_on_load_error(self):
        # On garde dans c la connexion de test fournie par ce helper.
        c = self.connection()
        # On attend RuntimeError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(RuntimeError):
            # On utilise adapter.connection_scope(lambda: c, 'suivi_acquisitions')() dans son contexte
            # de gestion ; les opérations de sortie sont exécutées en quittant le bloc.
            with adapter.connection_scope(lambda: c, "suivi_acquisitions")():
                # On interrompt cette branche avec RuntimeError : 'simulated'.
                raise RuntimeError("simulated")
        # On attend un seul appel à c.close dans ce scénario, ni zéro ni plusieurs.
        c.close.assert_called_once()

    def test_repository_kind_rejected_without_connect(self):
        # On garde dans opened un double de test dont les réponses et les appels pourront être
        # contrôlés.
        opened = Mock()
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle adapter.repository_scope avec ROOT.
            adapter.repository_scope(ROOT, opened, "admin")
        # On vérifie que opened n’a pas été appelé dans ce scénario.
        opened.assert_not_called()

    def test_default_load_functions_are_existing_importers(self):
        def module(root, name, relative):
            # On fournit à l’appelant un objet de test regroupant les attributs fournis.
            return SimpleNamespace(
                import_bundle=self.excel
                if name == "import_excel_publication"
                else self.nas
            )

        # On garde dans steps la valeur renvoyée par adapter.build_import_steps.
        steps = adapter.build_import_steps(
            self.root,
            excel_repository=self.excel_repository,
            nas_repository=self.nas_repository,
            # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
            ensure_excel=self.fixture.excel_guard,
            # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
            ensure_nas=self.nas_guard,
        )
        # On remplace temporairement adapter dans ce bloc de test ; le réglage initial sera rétabli à
        # sa sortie.
        with patch.object(adapter, "_project_module", side_effect=module) as modules:
            # On garde dans result le résultat du parcours préparé par ce helper de test.
            result = self.flow(steps=steps)
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que [call.args[1] for call in modules.call_args_list] correspond à
        # ['import_excel_publication', 'load_nas_reconciliation'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            [call.args[1] for call in modules.call_args_list],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ["import_excel_publication", "load_nas_reconciliation"],
        )

    def test_repository_wraps_connection_with_existing_class(self):
        # On garde dans c la valeur renvoyée par object.
        c = object()
        # On garde dans repository la valeur renvoyée par object.
        repository = object()

        # On fournit la ressource ouverte dans le contexte prévu et on en gère la sortie.
        @contextmanager
        def opened():
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield c

        # On garde dans factory un double de test dont les réponses et les appels pourront être
        # contrôlés.
        factory = Mock(return_value=repository)
        # On remplace temporairement adapter dans ce bloc de test ; le réglage initial sera rétabli à
        # sa sortie.
        with patch.object(
            adapter,
            "_project_module",
            # On fixe la réponse de ce double de test ; aucune vraie opération de la dépendance n’est
            # nécessaire pour obtenir cette valeur.
            return_value=SimpleNamespace(PostgresRepository=factory),
        ):
            # On utilise adapter.repository_scope(ROOT, opened, 'nas')() dans son contexte de gestion ;
            # les opérations de sortie sont exécutées en quittant le bloc.
            with adapter.repository_scope(ROOT, opened, "nas")() as got:
                # On vérifie l’identité de got avec repository, et pas seulement une égalité de
                # valeur.
                self.assertIs(got, repository)
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        factory.assert_called_once_with(c)

    def test_factories_are_lazy(self):
        # On garde dans connect un double de test dont les réponses et les appels pourront être
        # contrôlés.
        connect = Mock()
        # On garde dans opened la valeur renvoyée par adapter.connection_scope.
        opened = adapter.connection_scope(connect, "suivi_acquisitions")
        # On appelle adapter.repository_scope avec ROOT.
        adapter.repository_scope(ROOT, opened, "excel")
        # On appelle adapter.build_journal_sink avec ROOT.
        adapter.build_journal_sink(ROOT, opened=opened)
        # On vérifie que connect n’a pas été appelé dans ce scénario.
        connect.assert_not_called()
