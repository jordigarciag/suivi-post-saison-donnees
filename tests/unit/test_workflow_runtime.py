# Lecture du fichier — Tests de workflow runtime.
#

"""Socle commun : fichiers et etapes fictifs, aucune connexion PostgreSQL ou NAS."""

# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles UUID, uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import UUID, uuid4

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On importe workflow_runtime sous le nom runtime. Ce module sera utilisé par les opérations de ce
# fichier.
import workflow_runtime as runtime


class TestWorkflowRuntime(unittest.TestCase):
    def setUp(self):
        # On garde dans temp un dossier temporaire distinct des données du projet.
        temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(temp.name)
        # On regroupe dans self.scope ces champs nommés ; on pourra les retrouver par leur clé plutôt
        # que par leur position.
        self.scope = {"year": 2026, "vineyards": ["Synthetic"]}

    def run_flow(self, steps, **kwargs):
        # On fournit à l’appelant la valeur renvoyée par runtime.run_workflow.
        return runtime.run_workflow(
            self.root,
            steps,
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode=kwargs.pop("trigger_mode", "integration_test"),
            # On fournit le périmètre du traitement via le paramètre scope de cet appel.
            scope=kwargs.pop("scope", self.scope),
            **kwargs,
        )

    def events(self, result):
        # On fournit à l’appelant la valeur renvoyée par runtime.read_events.
        return runtime.read_events(self.root / result["journal_relative_path"])

    def test_success_order_and_consecutive_events(self):
        # On prépare calls comme liste vide ; on la remplira au fil des opérations suivantes.
        calls = []
        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow(
            [
                ("excel", lambda ctx: calls.append("excel")),
                ("nas", lambda ctx: calls.append("nas")),
            ]
        )
        # On vérifie que calls correspond à ['excel', 'nas'].
        self.assertEqual(calls, ["excel", "nas"])
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que result['completed_steps'] correspond à calls.
        self.assertEqual(result["completed_steps"], calls)
        # On garde dans events les événements relus dans les traces de ce scénario.
        events = self.events(result)
        # On vérifie que [e['event_sequence'] for e in events] correspond à list(range(1, 7)).
        self.assertEqual([e["event_sequence"] for e in events], list(range(1, 7)))
        # On vérifie que events[-1]['status'] correspond à 'success'.
        self.assertEqual(events[-1]["status"], "success")
        # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.LOCK_RELATIVE).exists())

    def test_one_workflow_uuid_and_distinct_event_uuids(self):
        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("dummy", lambda ctx: None)])
        # On garde dans events les événements relus dans les traces de ce scénario.
        events = self.events(result)
        # On appelle UUID avec result['workflow_execution_id'].
        UUID(result["workflow_execution_id"])
        # On vérifie que {e['workflow_execution_id'] for e in events} correspond à
        # {result['workflow_execution_id']}.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            {e["workflow_execution_id"] for e in events},
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            {result["workflow_execution_id"]},
        )
        # On vérifie que len({e['event_id'] for e in events}) correspond à len(events).
        self.assertEqual(len({e["event_id"] for e in events}), len(events))
        # On attend que all((e['occurred_at'].endswith('+00:00') for e in events)) soit évalué comme
        # vrai pour ce cas de test.
        self.assertTrue(all(e["occurred_at"].endswith("+00:00") for e in events))

    def test_scope_is_frozen(self):
        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow(
            [("dummy", lambda ctx: self.scope["vineyards"].append("Other"))]
        )
        # On attend que all((e['scope_payload'] == {'year': 2026, 'vineyards': ['Synthetic']} for e in
        # self.events(result))) soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            all(
                e["scope_payload"] == {"year": 2026, "vineyards": ["Synthetic"]}
                for e in self.events(result)
            )
        )

    def test_serialized_log_paths_are_posix(self):
        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("dummy", lambda ctx: None)])
        # On vérifie que '\\' ne figure pas dans result['journal_relative_path'].
        self.assertNotIn("\\", result["journal_relative_path"])
        # On attend que result['journal_relative_path'].startswith('data/') soit évalué comme vrai pour
        # ce cas de test.
        self.assertTrue(result["journal_relative_path"].startswith("data/"))
        # On attend que all((e['log_relative_path'] == result['journal_relative_path'] for e in
        # self.events(result))) soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            all(
                e["log_relative_path"] == result["journal_relative_path"]
                for e in self.events(result)
            )
        )

    def test_failed_step_stops_next_and_does_not_log_exception_secret(self):
        # On prépare calls comme liste vide ; on la remplira au fil des opérations suivantes.
        calls = []

        def fail(ctx):
            # On interrompt cette branche avec RuntimeError : 'synthetic-secret-in-exception'.
            raise RuntimeError("synthetic-secret-in-exception")

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow(
            [("bad", fail), ("next", lambda ctx: calls.append("next"))]
        )
        # On vérifie que calls correspond à [].
        self.assertEqual(calls, [])
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que result['error_code'] correspond à 'WORKFLOW_STEP_FAILED'.
        self.assertEqual(result["error_code"], "WORKFLOW_STEP_FAILED")
        # On garde dans raw le texte lu depuis self.root / result['journal_relative_path'] avec
        # l’encodage indiqué.
        raw = (self.root / result["journal_relative_path"]).read_text(encoding="utf-8")
        # On vérifie que 'synthetic-secret-in-exception' ne figure pas dans raw.
        self.assertNotIn("synthetic-secret-in-exception", raw)
        # On vérifie que self.events(result)[-1]['status'] correspond à 'failed'.
        self.assertEqual(self.events(result)[-1]["status"], "failed")
        # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.LOCK_RELATIVE).exists())

    def test_completed_steps_not_erased_when_next_fails(self):
        # On prépare done comme liste vide ; on la remplira au fil des opérations suivantes.
        done = []

        def fail(ctx):
            # On interrompt cette branche avec ValueError : 'synthetic'.
            raise ValueError("synthetic")

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow(
            [("first", lambda ctx: done.append("already_done")), ("second", fail)]
        )
        # On vérifie que done correspond à ['already_done'].
        self.assertEqual(done, ["already_done"])
        # On vérifie que result['completed_steps'] correspond à ['first'].
        self.assertEqual(result["completed_steps"], ["first"])
        # On vérifie que self.events(result)[-1]['metrics_payload'] correspond à {'completed_steps':
        # 1}.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.events(result)[-1]["metrics_payload"], {"completed_steps": 1}
        )

    def test_keyboard_interrupt_recorded_and_lock_released(self):
        def interrupt(ctx):
            # On interrompt cette branche avec KeyboardInterrupt.
            raise KeyboardInterrupt()

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("dummy", interrupt)])
        # On vérifie que result['status'] correspond à 'interrupted'.
        self.assertEqual(result["status"], "interrupted")
        # On vérifie que self.events(result)[-1]['status'] correspond à 'interrupted'.
        self.assertEqual(self.events(result)[-1]["status"], "interrupted")
        # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.LOCK_RELATIVE).exists())

    def test_existing_lock_blocks_without_overwrite(self):
        # On calcule ce quotient pour construire lock.
        lock = self.root / runtime.LOCK_RELATIVE
        # On prépare le dossier lock.parent avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        lock.parent.mkdir(parents=True)
        # On écrit le contenu préparé dans lock ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        lock.write_text("previous-owner", encoding="utf-8")
        # On attend runtime.WorkflowBusy dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(runtime.WorkflowBusy):
            # On appelle self.run_flow avec [('dummy', lambda ctx: None)].
            self.run_flow([("dummy", lambda ctx: None)])
        # On vérifie que lock.read_text() correspond à 'previous-owner'.
        self.assertEqual(lock.read_text(), "previous-owner")
        # On attend que (self.root / 'data').exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.root / "data").exists())

    def test_manual_and_airflow_modes_share_same_lock(self):
        def action(ctx):
            # On attend runtime.WorkflowBusy dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(runtime.WorkflowBusy):
                # On appelle self.run_flow avec [('other', lambda ctx: None)].
                self.run_flow(
                    # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                    [("other", lambda ctx: None)], trigger_mode="airflow_manual"
                )

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("dummy", action)], trigger_mode="manual_script")
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")

    def test_lock_owner_change_is_not_deleted(self):
        # On calcule ce quotient pour construire path.
        path = self.root / runtime.LOCK_RELATIVE
        # On attend RuntimeError avec un message correspondant au motif indiqué dans ce bloc ; si
        # aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(RuntimeError, "Proprietaire"):
            # On prend le verrou avant les contrôles et les étapes ; sa libération est gérée en
            # sortant du bloc, sans permettre à deux runs locaux du partager.
            with runtime.workflow_lock(self.root, str(uuid4())):
                # On écrit le contenu préparé dans path ; cette opération remplace le contenu du
                # fichier s’il existe déjà.
                path.write_text("foreign-owner", encoding="utf-8")
        # On vérifie que path.read_text() correspond à 'foreign-owner'.
        self.assertEqual(path.read_text(), "foreign-owner")

    def test_lock_conflict_between_two_real_python_processes(self):
        # On garde dans source la représentation textuelle de Path(runtime.__file__).parent.
        source = str(Path(runtime.__file__).parent)
        # On indexe env par k ; chaque clé sera associée à os.environ[k]. Une même clé ne peut garder
        # qu’une valeur.
        env = {
            k: os.environ[k]
            for k in (
                "PATH",
                "HOME",
                "SystemRoot",
                "WINDIR",
                "TEMP",
                "TMP",
                "USERPROFILE",
            )
            if k in os.environ
        }
        # On complète env avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle valeur
        # fournie.
        env.update(PYTHONPATH=source, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        # On utilise ce texte pour code ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        code = "from pathlib import Path\nfrom uuid import uuid4\nfrom workflow_runtime import workflow_lock, WorkflowBusy\nimport sys\ntry:\n with workflow_lock(Path(sys.argv[1]),str(uuid4())):\n  pass\nexcept WorkflowBusy:\n sys.exit(17)\nsys.exit(0)\n"
        # On prend le verrou avant les contrôles et les étapes ; sa libération est gérée en sortant
        # du bloc, sans permettre à deux runs locaux du partager.
        with runtime.workflow_lock(self.root, str(uuid4())):
            # On lance la commande puis on récupère son résultat ; son code de sortie sera interprété
            # par la suite.
            completed = subprocess.run(
                [sys.executable, "-c", code, str(self.root)],
                # On transmet cet environnement au processus plutôt que reprendre implicitement toutes
                # les variables du parent.
                env=env,
                # On choisit de récupérer les sorties du processus en mémoire pour les contrôles qui
                # suivent.
                capture_output=True,
                # On fournit le texte de travail via le paramètre text de cet appel.
                text=True,
                # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas
                # être décodé selon un réglage implicite du poste.
                encoding="utf-8",
                # On borne la durée d’attente de cet appel ; dépasser ce délai ne vaut pas confirmation
                # de réussite.
                timeout=15,
            )
            # On vérifie que completed.returncode correspond à 17.
            self.assertEqual(completed.returncode, 17, completed.stderr)
            # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme vrai pour ce
            # cas de test.
            self.assertTrue((self.root / runtime.LOCK_RELATIVE).exists())
        # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.LOCK_RELATIVE).exists())

    def test_journal_delivery_failure_before_action_stops_work(self):
        # On prépare actions comme liste vide ; on la remplira au fil des opérations suivantes.
        actions = []

        # On transmet l’événement au destinataire fourni pour ce journal.
        def sink(event):
            # On interrompt cette branche avec RuntimeError : 'synthetic-sink-secret'.
            raise RuntimeError("synthetic-sink-secret")

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow(
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            [("dummy", lambda ctx: actions.append("started"))], journal_sink=sink
        )
        # On vérifie que actions correspond à [].
        self.assertEqual(actions, [])
        # On vérifie que result['error_code'] correspond à 'JOURNAL_DELIVERY_UNCONFIRMED'.
        self.assertEqual(result["error_code"], "JOURNAL_DELIVERY_UNCONFIRMED")
        # On vérifie que len(self.events(result)) correspond à 2.
        self.assertEqual(len(self.events(result)), 2)
        # On vérifie que 'synthetic-sink-secret' ne figure pas dans json.dumps(self.events(result)).
        self.assertNotIn("synthetic-sink-secret", json.dumps(self.events(result)))

    def test_journal_delivery_failure_after_action_preserves_success_of_step(self):
        # On transmet l’événement au destinataire fourni pour ce journal.
        def sink(event):
            # On vérifie ce cas avant la suite : le numéro d’ordre de l’événement dans event correspond
            # à 3.
            if event["event_sequence"] == 3:
                # On interrompt cette branche avec RuntimeError : 'synthetic'.
                raise RuntimeError("synthetic")

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow(
            [
                ("done", lambda ctx: None),
                ("next", lambda ctx: self.fail("must not run")),
            ],
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            journal_sink=sink,
        )
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que result['completed_steps'] correspond à ['done'].
        self.assertEqual(result["completed_steps"], ["done"])
        # On garde dans events les événements relus dans les traces de ce scénario.
        events = self.events(result)
        # On vérifie que events[2]['status'] correspond à 'success'.
        self.assertEqual(events[2]["status"], "success")
        # On vérifie que events[-1]['error_code'] correspond à 'JOURNAL_DELIVERY_UNCONFIRMED'.
        self.assertEqual(events[-1]["error_code"], "JOURNAL_DELIVERY_UNCONFIRMED")
        # On attend que any((e['event_type'] == 'step' and e['status'] == 'failed' for e in events))
        # soit évalué comme faux pour ce cas de test.
        self.assertFalse(
            any(e["event_type"] == "step" and e["status"] == "failed" for e in events)
        )

    def test_terminal_delivery_failure_is_not_reported_as_success(self):
        # On transmet l’événement au destinataire fourni pour ce journal.
        def sink(event):
            # Cette branche traite le cas où event['event_type'] correspond au texte 'workflow' et
            # l’état du traitement dans event correspond au texte 'success'.
            if event["event_type"] == "workflow" and event["status"] == "success":
                # On interrompt cette branche avec RuntimeError : 'synthetic'.
                raise RuntimeError("synthetic")

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("done", lambda ctx: None)], journal_sink=sink)
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que result['completed_steps'] correspond à ['done'].
        self.assertEqual(result["completed_steps"], ["done"])
        # On vérifie que self.events(result)[-1]['status'] correspond à 'failed'.
        self.assertEqual(self.events(result)[-1]["status"], "failed")

    def test_delivered_events_equal_local_events(self):
        # On prépare delivered comme liste vide ; on la remplira au fil des opérations suivantes.
        delivered = []
        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow(
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            [("dummy", lambda ctx: None)], journal_sink=delivered.append
        )
        # On vérifie que delivered correspond à self.events(result).
        self.assertEqual(delivered, self.events(result))

    def test_sink_cannot_modify_local_event(self):
        # On transmet l’événement au destinataire fourni pour ce journal.
        def sink(event):
            # On ajoute 'Modified' à la fin de event['scope_payload']['vineyards'] ; les éléments
            # précédents restent conservés.
            event["scope_payload"]["vineyards"].append("Modified")

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("dummy", lambda ctx: None)], journal_sink=sink)
        # On attend que all((e['scope_payload']['vineyards'] == ['Synthetic'] for e in
        # self.events(result))) soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            all(
                e["scope_payload"]["vineyards"] == ["Synthetic"]
                for e in self.events(result)
            )
        )

    def test_replay_preserves_file_ids_and_dates(self):
        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("dummy", lambda ctx: None)])
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.root / result["journal_relative_path"]
        # On garde dans before les octets lus depuis path, avant toute conversion en texte. Les
        # contrôles de contenu pourront ainsi repartir de cette lecture.
        before = path.read_bytes()
        # On prépare une liste distincte pour chacun de ces résultats : first, second. Elles seront
        # alimentées au même rythme dans la boucle.
        first, second = [], []
        # On vérifie que runtime.replay_events(path, first.append) correspond à 4.
        self.assertEqual(runtime.replay_events(path, first.append), 4)
        # On vérifie que runtime.replay_events(path, second.append) correspond à 4.
        self.assertEqual(runtime.replay_events(path, second.append), 4)
        # On vérifie que first correspond à second.
        self.assertEqual(first, second)
        # On vérifie que path.read_bytes() correspond à before.
        self.assertEqual(path.read_bytes(), before)

    def test_truncated_journal_rejected_before_delivery(self):
        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("dummy", lambda ctx: None)])
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.root / result["journal_relative_path"]
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_bytes(path.read_bytes()[:-1])
        # On prépare received comme liste vide ; on la remplira au fil des opérations suivantes.
        received = []
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle runtime.replay_events avec path.
            runtime.replay_events(path, received.append)
        # On vérifie que received correspond à [].
        self.assertEqual(received, [])

    def test_bad_sequence_rejected_before_delivery(self):
        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("dummy", lambda ctx: None)])
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.root / result["journal_relative_path"]
        # On garde dans records les événements relus dans les traces de ce scénario.
        records = self.events(result)
        # On fixe records[-1]['event_sequence'] à 9 pour cette étape du scénario de test.
        records[-1]["event_sequence"] = 9
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_text(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            "".join(json.dumps(e) + "\n" for e in records), encoding="utf-8"
        )
        # On prépare received comme liste vide ; on la remplira au fil des opérations suivantes.
        received = []
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle runtime.replay_events avec path.
            runtime.replay_events(path, received.append)
        # On vérifie que received correspond à [].
        self.assertEqual(received, [])

    def test_linked_ids_pinned_and_present_on_later_events(self):
        def pin(ctx):
            # On rattache le contexte à ce lot pour empêcher un changement silencieux d’identifiant
            # en cours de traitement.
            ctx.pin_ids(
                # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de cet
                # appel.
                excel_publication_id="synthetic-pub",
                # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de
                # cet appel.
                pipeline_execution_id="synthetic-pipeline",
            )

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("pin", pin), ("next", lambda ctx: None)])
        # On vérifie que result['excel_publication_id'] correspond à 'synthetic-pub'.
        self.assertEqual(result["excel_publication_id"], "synthetic-pub")
        # On attend que all((e['excel_publication_id'] == 'synthetic-pub' for e in
        # self.events(result)[2:])) soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            all(
                e["excel_publication_id"] == "synthetic-pub"
                for e in self.events(result)[2:]
            )
        )

    def test_pinned_id_cannot_be_replaced(self):
        def pin(ctx):
            # On rattache le contexte à ce lot pour empêcher un changement silencieux d’identifiant
            # en cours de traitement.
            ctx.pin_ids(excel_publication_id="synthetic-pub")

        def replace(ctx):
            # On rattache le contexte à ce lot pour empêcher un changement silencieux d’identifiant
            # en cours de traitement.
            ctx.pin_ids(excel_publication_id="other")

        # On garde dans result le bilan du workflow lancé avec les étapes fictives du scénario.
        result = self.run_flow([("pin", pin), ("replace", replace)])
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que result['excel_publication_id'] correspond à 'synthetic-pub'.
        self.assertEqual(result["excel_publication_id"], "synthetic-pub")

    def test_invalid_pin_does_not_partially_change_ids(self):
        # On garde dans context la valeur renvoyée par runtime.WorkflowContext.
        context = runtime.WorkflowContext(self.root, str(uuid4()))
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On rattache le contexte à ce lot pour empêcher un changement silencieux d’identifiant
            # en cours de traitement.
            context.pin_ids(
                # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de cet
                # appel.
                excel_publication_id="synthetic-pub", pipeline_execution_id=123
            )
        # On compare context.linked_ids() à {'excel_publication_id': None, 'pipeline_execution_id':
        # None}.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            context.linked_ids(),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            {"excel_publication_id": None, "pipeline_execution_id": None},
        )

    def test_output_outside_project_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle runtime.local_path avec self.root.
            runtime.local_path(self.root, "../outside")

    def test_invalid_steps_rejected_before_writes(self):
        # On parcourt ([], [('duplicate', lambda ctx: None), ('duplicate', lambda ctx: None)],… ; steps
        # désigne l’élément courant de ce scénario.
        for steps in (
            [],
            [("duplicate", lambda ctx: None), ("duplicate", lambda ctx: None)],
            [("bad/name", lambda ctx: None)],
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(invalid=True):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle self.run_flow avec steps.
                    self.run_flow(steps)
        # On attend que (self.root / 'state').exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.root / "state").exists())

    def test_invalid_scope_prevents_actions_and_releases_lock(self):
        # On prépare calls comme liste vide ; on la remplira au fil des opérations suivantes.
        calls = []
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_flow avec [('dummy', lambda ctx: calls.append(1))].
            self.run_flow(
                [("dummy", lambda ctx: calls.append(1))],
                # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                scope={"invalid": float("nan")},
            )
        # On vérifie que calls correspond à [].
        self.assertEqual(calls, [])
        # On attend que (self.root / runtime.LOCK_RELATIVE).exists() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse((self.root / runtime.LOCK_RELATIVE).exists())


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
