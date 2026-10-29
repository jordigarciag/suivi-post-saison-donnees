# Lecture du fichier — Tests de workflow manual entry.
#

"""Entree manuelle et assemblage commun, sans PostgreSQL/NAS/Airflow."""

# On décrit les champs d’un objet de données sans écrire toute sa construction à la main.
from dataclasses import replace
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe contextlib. Ce module sera utilisé par les opérations de ce fichier.
import contextlib
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe shutil. On réalise les copies et nettoyages de fichiers explicitement prévus.
import shutil
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
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
# On importe workflow_assembly sous le nom assembly. Ce module sera utilisé par les opérations de ce
# fichier.
import workflow_assembly as assembly
# On importe run_workflow_local sous le nom entry. Ce module sera utilisé par les opérations de ce
# fichier.
import run_workflow_local as entry
# On importe test_workflow_nas_adapter sous le nom nas_fixture. Ce module sera utilisé par les
# opérations de ce fichier.
import test_workflow_nas_adapter as nas_fixture
# On rend disponibles read_events depuis workflow_runtime, pour les appels de ce fichier.
from workflow_runtime import read_events


class TestWorkflowManualEntry(unittest.TestCase):
    def setUp(self):
        # On garde dans self.f la valeur renvoyée par nas_fixture.TestWorkflowNasAdapter.
        self.f = nas_fixture.TestWorkflowNasAdapter()
        # On initialise les ressources du scénario self.f avec sa méthode setUp.
        self.f.setUp()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.f.doCleanups)
        # On prépare self.loads comme liste vide ; on la remplira au fil des opérations suivantes.
        self.loads = []

        # On prépare le dépôt qui sera utilisé par l’étape de chargement.
        @contextlib.contextmanager
        def repository():
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield object()

        def ingest(root, **kwargs):
            # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver
            # chaque information par sa clé.
            return {
                # On renseigne l’état du traitement sous la clé 'status'.
                "status": "unchanged",
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": self.f.pub_id,
                # On renseigne le chemin du tableau Excel regroupé sous la clé 'reference_path'.
                "reference_path": self.f.relative,
            }

        # On garde dans self.ingest un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.ingest = Mock(side_effect=ingest)
        # On garde dans self.d la valeur renvoyée par assembly.WorkflowDependencies.
        self.d = assembly.WorkflowDependencies(
            self.ingest,
            lambda r: self.f.excel_bundle,
            self.f.current,
            self.f.selector,
            self.f.execute_mock,
            self.f.prepare_mock,
            self.f.files_mock,
            repository,
            repository,
            lambda b, r: self.loads.append("excel"),
            lambda b, r: self.loads.append("nas"),
        )
        # On prépare self.sent comme liste vide ; on la remplira au fil des opérations suivantes.
        self.sent = []

    def run_shared(self, **kwargs):
        # On garde dans options un nouveau dictionnaire construit avec les valeurs indiquées.
        options = dict(
            dependencies=self.d,
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            journal_sink=lambda e: self.sent.append(e),
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="manual_script",
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=["Synthetic"],
        )
        # On complète options avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        options.update(kwargs)
        # On fournit à l’appelant la valeur renvoyée par assembly.run_shared_rehearsal.
        return assembly.run_shared_rehearsal(self.f.root, **options)

    def test_assembly_is_lazy_before_run(self):
        # On garde dans steps la valeur renvoyée par assembly.build_workflow_steps.
        steps = assembly.build_workflow_steps(
            # On transmet la sélection explicite des domaines concernés par cet appel.
            self.f.root, dependencies=self.d, vineyards=["Synthetic"]
        )
        # On vérifie que len(steps) correspond à 8.
        self.assertEqual(len(steps), 8)
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()
        # On vérifie que self.f.execute_mock n’a pas été appelé : le refus doit intervenir avant
        # cette opération.
        self.f.execute_mock.assert_not_called()
        # On vérifie que self.loads correspond à [].
        self.assertEqual(self.loads, [])
        # On attend que (self.f.root / 'state').exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse((self.f.root / "state").exists())

    def test_shared_eight_steps_success(self):
        # On garde dans result le bilan du parcours commun avec les dépendances du test.
        result = self.run_shared()
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que self.loads correspond à ['excel', 'nas'].
        self.assertEqual(self.loads, ["excel", "nas"])
        # On vérifie que result['completed_steps'] correspond à ['excel_ingestion',
        # 'excel_publication_check', 'excel_reference_pin', 'nas_….
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            result["completed_steps"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            [
                "excel_ingestion",
                "excel_publication_check",
                "excel_reference_pin",
                "nas_scope_prepare",
                "nas_pipeline_execute",
                "nas_bundle_check",
                "excel_import",
                "nas_import",
            ],
        )

    def test_no_airflow_import_required(self):
        # On vérifie que 'airflow' ne figure pas dans assembly.__dict__.
        self.assertNotIn("airflow", assembly.__dict__)
        # On vérifie que 'airflow' ne figure pas dans entry.__dict__.
        self.assertNotIn("airflow", entry.__dict__)

    def test_manual_trigger_and_rehearsal_marked_in_every_event(self):
        # On garde dans result le bilan du parcours commun avec les dépendances du test.
        result = self.run_shared()
        # On garde dans events les événements du journal local après validation de leur ordre et de
        # leur identité.
        events = read_events(self.f.root / result["journal_relative_path"])
        # On attend que all((e['trigger_mode'] == 'manual_script' and
        # e['scope_payload']['execution_kind'] == 'synthetic_rehearsal' f… soit évalué comme vrai pour
        # ce cas de test.
        self.assertTrue(
            all(
                e["trigger_mode"] == "manual_script"
                # On exige aussi que e['scope_payload']['execution_kind'] correspond au texte
                # 'synthetic_rehearsal'.
                and e["scope_payload"]["execution_kind"] == "synthetic_rehearsal"
                for e in events
            )
        )
        # On vérifie que events correspond à self.sent.
        self.assertEqual(events, self.sent)
        # On attend que all((e['scope_payload']['postgresql_writes'] is False for e in events)) soit
        # évalué comme vrai pour ce cas de test.
        self.assertTrue(
            all(e["scope_payload"]["postgresql_writes"] is False for e in events)
        )

    def test_airflow_trigger_can_call_same_assembly_without_airflow(self):
        # On garde dans result le bilan du parcours commun avec les dépendances du test.
        result = self.run_shared(trigger_mode="airflow_manual")
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On attend que all((e['trigger_mode'] == 'airflow_manual' for e in self.sent)) soit évalué
        # comme vrai pour ce cas de test.
        self.assertTrue(all(e["trigger_mode"] == "airflow_manual" for e in self.sent))

    def test_dependencies_missing_before_any_ingestion(self):
        # On parcourt ('execute_nas', 'excel_repository', 'nas_repository', 'import_nas') ; key désigne
        # l’élément courant de ce scénario.
        for key in ("execute_nas", "excel_repository", "nas_repository", "import_nas"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(key=key):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle self.run_shared sans argument positionnel.
                    self.run_shared(dependencies=replace(self.d, **{key: None}))
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()
        # On vérifie que self.sent correspond à [].
        self.assertEqual(self.sent, [])

    def test_invalid_trigger_refused_before_ingestion(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_shared sans argument positionnel.
            self.run_shared(trigger_mode="unknown")
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()

    def test_missing_journal_sink_refused_before_ingestion(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_shared sans argument positionnel.
            self.run_shared(journal_sink=None)
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()

    def test_conflicting_selection_refused_before_ingestion(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_shared sans argument positionnel.
            self.run_shared(all_vineyards=True)
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()

    def test_missing_selection_refused_before_ingestion(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_shared sans argument positionnel.
            self.run_shared(vineyards=None)
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()

    def test_invalid_year_refused_before_ingestion(self):
        # On parcourt (True, 2026.0, 0) ; year désigne l’élément courant de ce scénario.
        for year in (True, 2026.0, 0):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(year=year):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle self.run_shared sans argument positionnel.
                    self.run_shared(year=year)
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()

    def test_selection_trimmed_and_deduplicated(self):
        # On garde dans result le bilan du parcours commun avec les dépendances du test.
        result = self.run_shared(vineyards=[" Synthetic ", "SYNTHETIC"])
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        self.ingest.assert_called_once_with(
            # On transmet la sélection explicite des domaines concernés par cet appel.
            self.f.root, vineyards=["Synthetic"], all_vineyards=False
        )
        # On vérifie que self.sent[0]['scope_payload']['vineyards'] correspond à ['Synthetic'].
        self.assertEqual(self.sent[0]["scope_payload"]["vineyards"], ["Synthetic"])

    def test_failed_pilot_blocks_both_loaders(self):
        # On distribue ces valeurs entre self.f.code, self.f.status, dans l’ordre de l’affectation.
        # Chaque nom reçoit son propre élément.
        self.f.code, self.f.status = 1, "failed"
        # On garde dans result le bilan du parcours commun avec les dépendances du test.
        result = self.run_shared()
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que self.loads correspond à [].
        self.assertEqual(self.loads, [])

    def test_journal_failure_before_start_blocks_everything(self):
        # On garde dans result le bilan du parcours commun avec les dépendances du test.
        result = self.run_shared(
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            journal_sink=Mock(side_effect=RuntimeError("private-value"))
        )
        # On vérifie que result['error_code'] correspond à 'JOURNAL_DELIVERY_UNCONFIRMED'.
        self.assertEqual(result["error_code"], "JOURNAL_DELIVERY_UNCONFIRMED")
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()
        # On vérifie que 'private-value' ne figure pas dans (self.f.root /
        # result['journal_relative_path']).read_text().
        self.assertNotIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "private-value", (self.f.root / result["journal_relative_path"]).read_text()
        )

    def test_cli_requires_rehearsal_before_preparation(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(entry, "run_rehearsal") as run,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle entry.main avec ['--all-vineyards'].
                entry.main(["--all-vineyards"])
        # On vérifie que run n’a pas été appelé dans ce scénario.
        run.assert_not_called()

    def test_cli_has_no_run_business_option(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(entry, "run_rehearsal") as run,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle entry.main avec ['--run', '--all-vineyards'].
                entry.main(["--run", "--all-vineyards"])
        # On vérifie que run n’a pas été appelé dans ce scénario.
        run.assert_not_called()

    def test_cli_requires_selection(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(entry, "run_rehearsal") as run,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle entry.main avec ['--rehearsal'].
                entry.main(["--rehearsal"])
        # On vérifie que run n’a pas été appelé dans ce scénario.
        run.assert_not_called()

    def test_cli_non_success_returns_nonzero_and_keeps_safe_output(self):
        # On regroupe dans result ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        result = {
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "failed",
            # On renseigne les étapes terminées sous la clé 'completed_steps'.
            "completed_steps": [],
            # On renseigne le code du problème rencontré sous la clé 'error_code'.
            "error_code": "WORKFLOW_STEP_FAILED",
        }
        # On garde dans output un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        output = io.StringIO()
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(entry, "run_rehearsal", return_value=(result, "logs/fake")),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(output),
        ):
            # On garde dans code la valeur renvoyée par entry.main.
            code = entry.main(["--rehearsal", "--all-vineyards"])
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que 'NON CONFIRME' figure dans output.getvalue().
        self.assertIn("NON CONFIRME", output.getvalue())

    def test_cli_exception_not_printed_raw(self):
        # On garde dans output un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        output = io.StringIO()
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(
                # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
                # suivre une fonction de test.
                entry, "run_rehearsal", side_effect=RuntimeError("private-password")
            ),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(output),
        ):
            # On garde dans code la valeur renvoyée par entry.main.
            code = entry.main(["--rehearsal", "--all-vineyards"])
        # On vérifie que code correspond à 1.
        self.assertEqual(code, 1)
        # On vérifie que 'private-password' ne figure pas dans output.getvalue().
        self.assertNotIn("private-password", output.getvalue())

    def test_nonproject_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle entry.local_project avec self.f.root.
            entry.local_project(self.f.root)

    def test_unknown_vineyard_refused_before_fixtures(self):
        # On remplace temporairement entry dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(entry, "_project_module") as module:
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle entry.run_rehearsal avec ROOT.
                entry.run_rehearsal(ROOT, vineyards=["Unknown"])
        # On vérifie que module n’a pas été appelé dans ce scénario.
        module.assert_not_called()

    def test_cli_direct_python_rehearsal_from_copied_project(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as temp:
            # On assemble les morceaux du chemin root avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            root = Path(temp) / "projet repetition"
            # On parcourt ('scripts', 'tests/unit') ; relative désigne l’élément courant de ce
            # scénario.
            for relative in ("scripts", "tests/unit"):
                # On copie l’arborescence vers la destination indiquée pour préparer ce scénario isolé.
                shutil.copytree(
                    ROOT / relative,
                    root / relative,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
                )
            # Aucun fichier data/state/.env du projet reel copie.
            (root / ".env").write_text(
                # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas
                # être décodé selon un réglage implicite du poste.
                "FICHIER_VOLONTAIREMENT_INUTILISABLE=private-sentinel", encoding="utf-8"
            )
            # On garde dans env un nouveau dictionnaire construit avec les valeurs indiquées (la copie
            # reste superficielle).
            env = dict(
                os.environ,
                PROJECT12_IMPORT_HOST="unreachable-real-host",
                PROJECT12_IMPORT_PASSWORD="private-sentinel",
                PYTHONUTF8="1",
            )
            # On lance la commande puis on récupère son résultat ; son code de sortie sera interprété
            # par la suite.
            result = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts/run_workflow_local.py"),
                    "--rehearsal",
                    "--all-vineyards",
                ],
                # On impose le dossier de travail du processus enfant ; les chemins relatifs ne
                # dépendent ainsi pas du terminal de départ.
                cwd=root,
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
                timeout=60,
            )
            # On vérifie que result.returncode correspond à 0.
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            # On vérifie que 'Etapes confirmees : 8/8' figure dans result.stdout.
            self.assertIn("Etapes confirmees : 8/8", result.stdout)
            # On vérifie que 'aucun chargement reel' figure dans result.stdout.
            self.assertIn("aucun chargement reel", result.stdout)
            # On vérifie que 'private-sentinel' ne figure pas dans result.stdout + result.stderr.
            self.assertNotIn("private-sentinel", result.stdout + result.stderr)
            # On garde dans journals une liste matérialisée à partir de (root /
            # 'logs/workflow_rehearsals').glob('*/events.jsonl').
            journals = list((root / "logs/workflow_rehearsals").glob("*/events.jsonl"))
            # On vérifie que len(journals) correspond à 1.
            self.assertEqual(len(journals), 1)
            # On vérifie que read_events(journals[0])[-1]['status'] correspond à 'success'.
            self.assertEqual(read_events(journals[0])[-1]["status"], "success")
            # On attend que (root / 'data').exists() soit évalué comme faux pour ce cas de test.
            self.assertFalse((root / "data").exists())
            # On attend que (root / 'state').exists() soit évalué comme faux pour ce cas de test.
            self.assertFalse((root / "state").exists())
            # On garde dans receipt les objets Python décodés depuis le JSON fourni.
            receipt = json.loads(
                (journals[0].parent / "result.json").read_text(encoding="utf-8")
            )
            # On vérifie que receipt['execution_kind'] correspond à 'synthetic_rehearsal'.
            self.assertEqual(receipt["execution_kind"], "synthetic_rehearsal")
