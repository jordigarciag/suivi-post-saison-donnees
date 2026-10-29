# Lecture du fichier — Tests de workflow nas adapter.
#

"""Raccordement pilote : appels et donnees fictifs, aucun NAS ni PostgreSQL."""

# On importe contextlib. Ce module sera utilisé par les opérations de ce fichier.
import contextlib
# On sépare les copies d’objets, notamment pour comparer un état avant et après une opération.
import copy
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe shutil. On réalise les copies et nettoyages de fichiers explicitement prévus.
import shutil
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Mock depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import Mock

# On récupère Path(__file__).resolve().parents[2] et on le garde dans PROJECT_ROOT pour la suite.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
# On importe workflow_nas_adapter sous le nom adapter. Ce module sera utilisé par les opérations de ce
# fichier.
import workflow_nas_adapter as adapter
# On rend disponibles build_excel_steps, assert_excel_snapshot depuis workflow_excel_adapter, pour les
# appels de ce fichier.
from workflow_excel_adapter import build_excel_steps, assert_excel_snapshot
# On rend disponibles run_workflow depuis workflow_runtime, pour les appels de ce fichier.
from workflow_runtime import run_workflow


class TestWorkflowNasAdapter(unittest.TestCase):
    def setUp(self):
        # On garde dans temp un dossier temporaire distinct des données du projet.
        temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(temp.name)
        # On utilise ce texte pour self.pub_id ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        self.pub_id = "synthetic_pub"
        # On utilise ce texte pour self.relative ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.relative = "data/03_normalized/suivi_acquisitions_normalises/publications/synthetic_pub/reference.csv"
        # On calcule ce quotient pour construire self.reference.
        self.reference = self.root / self.relative
        # On prépare le dossier self.reference.parent avec les règles de création indiquées ; aucun
        # résultat métier n’est encore produit par cette création.
        self.reference.parent.mkdir(parents=True)
        # On écrit le contenu préparé dans self.reference ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        self.reference.write_bytes(
            b"Vineyard,Acquisition_ID_normalise\nSynthetic,Synthetic_C01_V1_2026-06-01T10-00-00\n"
        )
        # On conserve l’empreinte sous forme de texte pour la comparer aux métadonnées attendues.
        self.sha = hashlib.sha256(self.reference.read_bytes()).hexdigest()
        # On regroupe dans self.excel_bundle ces champs nommés ; on pourra les retrouver par leur clé
        # plutôt que par leur position.
        self.excel_bundle = {
            # On renseigne la publication Excel sous la clé 'publication'.
            "publication": {
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": self.pub_id,
                # On renseigne le repère utilisé pour les données Excel sous la clé 'reference'.
                "reference": {"path": self.relative, "sha256": self.sha},
            }
        }
        # On garde dans self.current un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.current = Mock()
        # On garde dans self.selector un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.selector = Mock(return_value=["Synthetic"])
        # On utilise ce texte pour self.execution ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.execution = "20261013_abcd1234"
        # On assemble les morceaux du chemin self.manifest avec l’opérateur / de pathlib ; aucun
        # fichier n’est créé par cette construction.
        self.manifest = (
            self.root
            / "data/03_normalized/pipeline_runs"
            / self.execution
            / "manifest.json"
        )
        # On fixe self.code à 0 pour cette étape du scénario de test.
        self.code = 0
        # On utilise ce texte pour self.status ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        self.status = "success"
        # On initialise self.mutate à None : aucune valeur n’a encore été retenue ici.
        self.mutate = None
        # On garde dans self.execute_mock un double de test dont les réponses et les appels pourront
        # être contrôlés.
        self.execute_mock = Mock(side_effect=self.fake_execute)
        # On garde dans self.prepare_mock un double de test dont les réponses et les appels pourront
        # être contrôlés.
        self.prepare_mock = Mock(side_effect=self.fake_prepare)
        # On garde dans self.files_mock un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.files_mock = Mock()

    def excel_steps(self):
        # On regroupe dans result ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        result = {
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "unchanged",
            # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
            "publication_id": self.pub_id,
            # On renseigne le chemin du tableau Excel regroupé sous la clé 'reference_path'.
            "reference_path": self.relative,
        }
        # On fournit à l’appelant les fonctions des étapes Excel, construites sans les exécuter encore.
        return build_excel_steps(
            self.root,
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=["Synthetic"],
            ingest=lambda *args, **kwargs: result,
            prepare=lambda root: self.excel_bundle,
            # On fournit la vérification de stabilité du lot, réutilisable avant ses consommateurs.
            ensure_current=self.current,
        )

    def nas_steps(self, **kwargs):
        # On garde dans options un nouveau dictionnaire construit avec les valeurs indiquées.
        options = dict(
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=["Synthetic"],
            select=self.selector,
            execute=self.execute_mock,
            prepare=self.prepare_mock,
            # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
            ensure_excel=self.excel_guard,
            # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
            ensure_nas=self.files_mock,
        )
        # On complète options avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        options.update(kwargs)
        # On fournit à l’appelant la valeur renvoyée par adapter.build_nas_steps.
        return adapter.build_nas_steps(self.root, **options)

    def excel_guard(self, ctx):
        # On fournit à l’appelant la valeur renvoyée par assert_excel_snapshot.
        return assert_excel_snapshot(ctx, ensure_current=self.current)

    def fake_execute(self, root, reference, vineyards, year, *, stop_on_error):
        # On prépare le dossier self.manifest.parent avec les règles de création indiquées ; aucun
        # résultat métier n’est encore produit par cette création.
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        # On assemble les morceaux du chemin snapshot avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        snapshot = self.manifest.parent / "tracking_reference_snapshot.csv"
        # On écrit le contenu préparé dans snapshot ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        snapshot.write_bytes(reference.read_bytes())
        # On regroupe dans manifest ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        manifest = {
            # On renseigne l’identifiant du traitement NAS sous la clé 'pipeline_execution_id'.
            "pipeline_execution_id": self.execution,
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": self.status,
            # On associe la clé 'project_year' à cette valeur dans les données de ce scénario.
            "project_year": year,
            # On associe la clé 'reference_source' à cette valeur dans les données de ce scénario.
            "reference_source": str(reference),
            # On associe la clé 'reference_snapshot' à cette valeur dans les données de ce scénario.
            "reference_snapshot": str(snapshot),
            # On renseigne l’empreinte du tableau Excel regroupé sous la clé 'reference_sha256'.
            "reference_sha256": self.sha,
            # On renseigne la date de début sous la clé 'started_at'.
            "started_at": "2026-10-13T08:00:00+00:00",
            # On renseigne la date de fin sous la clé 'finished_at'.
            "finished_at": "2026-10-13T08:01:00+00:00",
            # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
            "vineyards": [
                {"vineyard": name, "status": self.status} for name in vineyards
            ],
        }
        # Cette branche traite le cas où le test self.mutate est satisfait.
        if self.mutate:
            # On appelle self.mutate avec manifest.
            self.mutate(manifest, snapshot)
        # On écrit le contenu préparé dans self.manifest ; cette opération remplace le contenu du
        # fichier s’il existe déjà.
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return self.code, self.manifest

    def fake_prepare(self, root, relative):
        # On garde dans manifest les objets Python décodés depuis le JSON fourni.
        manifest = json.loads((root / relative).read_text(encoding="utf-8"))
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On renseigne le bilan sous la clé 'report'.
            "report": {
                # On renseigne l’identifiant du traitement NAS sous la clé 'pipeline_execution_id'.
                "pipeline_execution_id": manifest["pipeline_execution_id"],
                # On renseigne l’identifiant du lot Excel sous la clé 'excel_publication_id'.
                "excel_publication_id": self.pub_id,
            },
            # On renseigne la publication Excel sous la clé 'publication'.
            "publication": copy.deepcopy(self.excel_bundle["publication"]),
            # On renseigne le manifeste du lot sous la clé 'manifest'.
            "manifest": manifest,
        }

    def execute_flow(self, nas=None, tail=None):
        # On assemble ces deux éléments pour construire steps.
        steps = (
            self.excel_steps()
            + (self.nas_steps() if nas is None else nas)
            + (tail or [])
        )
        # On fournit à l’appelant le bilan du parcours après l’appel de ses étapes et de son journal.
        return run_workflow(
            self.root,
            steps,
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="integration_test",
            # On fournit le périmètre du traitement via le paramètre scope de cet appel.
            scope={"year": 2026, "vineyards": ["Synthetic"]},
        )

    def test_success_exact_reference_scope_and_stop_on_error(self):
        # On garde dans result le bilan du parcours exécuté avec les dépendances de cet essai.
        result = self.execute_flow()
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que result['pipeline_execution_id'] correspond à self.execution.
        self.assertEqual(result["pipeline_execution_id"], self.execution)
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        self.execute_mock.assert_called_once_with(
            # On décide si le parcours s’arrête dès la première erreur, au lieu de laisser ce choix
            # implicite.
            self.root, self.reference, ["Synthetic"], 2026, stop_on_error=True
        )
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        self.prepare_mock.assert_called_once_with(
            self.root, self.manifest.relative_to(self.root).as_posix()
        )
        # On attend un seul appel à self.files_mock dans ce scénario, ni zéro ni plusieurs.
        self.files_mock.assert_called_once()
        # On vérifie que result['completed_steps'][-3:] correspond à ['nas_scope_prepare',
        # 'nas_pipeline_execute', 'nas_bundle_check'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            result["completed_steps"][-3:],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ["nas_scope_prepare", "nas_pipeline_execute", "nas_bundle_check"],
        )

    def test_all_vineyards_selection_receives_year_and_pinned_reference(self):
        # On vérifie que self.execute_flow(self.nas_steps(vineyards=None, all_vineyards=True))['stat…
        # correspond à 'success'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.execute_flow(self.nas_steps(vineyards=None, all_vineyards=True))[
                "status"
            ],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            "success",
        )
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        self.selector.assert_called_once_with(self.reference, [], True, 2026)

    def test_failure_stops_before_bundle_and_keeps_pipeline_id(self):
        # On distribue ces valeurs entre self.code, self.status, dans l’ordre de l’affectation. Chaque
        # nom reçoit son propre élément.
        self.code, self.status = 1, "failed"
        # On garde dans result le bilan du parcours exécuté avec les dépendances de cet essai.
        result = self.execute_flow()
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que result['pipeline_execution_id'] correspond à self.execution.
        self.assertEqual(result["pipeline_execution_id"], self.execution)
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()

    def test_interruption_is_not_success(self):
        # On distribue ces valeurs entre self.code, self.status, dans l’ordre de l’affectation. Chaque
        # nom reçoit son propre élément.
        self.code, self.status = 130, "interrupted"
        # On garde dans result le bilan du parcours exécuté avec les dépendances de cet essai.
        result = self.execute_flow()
        # On vérifie que result['status'] correspond à 'interrupted'.
        self.assertEqual(result["status"], "interrupted")
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()
        # On attend que (self.root / 'state/workflow_execution/workflow.lock').exists() soit évalué
        # comme faux pour ce cas de test.
        self.assertFalse(
            (self.root / "state/workflow_execution/workflow.lock").exists()
        )

    def test_zero_code_with_failed_manifest_rejected(self):
        # On utilise ce texte pour self.status ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        self.status = "failed"
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()

    def test_partial_vineyard_success_rejected(self):
        # On prépare pour self.mutate une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
        # appelée, pas lors de cette affectation.
        self.mutate = lambda m, snapshot: m["vineyards"][0].update(status="failed")
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()

    def test_empty_selection_prevents_execution(self):
        # On prépare self.selector.return_value comme liste vide ; on la remplira au fil des opérations
        # suivantes.
        self.selector.return_value = []
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")
        # On vérifie que self.execute_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.execute_mock.assert_not_called()

    def test_manifest_id_must_match_directory(self):
        # On prépare pour self.mutate une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
        # appelée, pas lors de cette affectation.
        self.mutate = lambda m, snapshot: m.update(
            # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de cet
            # appel.
            pipeline_execution_id="20261013_ffffffff"
        )
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()

    def test_manifest_year_must_match_requested_year(self):
        # On prépare pour self.mutate une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
        # appelée, pas lors de cette affectation.
        self.mutate = lambda m, snapshot: m.update(project_year=2025)
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")

    def test_manifest_scope_must_match_selected_vineyards(self):
        # On prépare pour self.mutate une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
        # appelée, pas lors de cette affectation.
        self.mutate = lambda m, snapshot: m["vineyards"][0].update(vineyard="Other")
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")

    def test_other_reference_source_rejected(self):
        # On prépare pour self.mutate une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
        # appelée, pas lors de cette affectation.
        self.mutate = lambda m, snapshot: m.update(reference_source="data/other.csv")
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")

    def test_wrong_snapshot_content_rejected(self):
        # On prépare pour self.mutate une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
        # appelée, pas lors de cette affectation.
        self.mutate = lambda m, snapshot: snapshot.write_bytes(b"other-content")
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()

    def test_manifest_outside_run_folder_rejected(self):
        # On garde dans result le bilan du parcours exécuté avec les dépendances de cet essai.
        result = self.execute_flow(
            self.nas_steps(
                execute=lambda *args, **kwargs: (0, self.root / "outside.json")
            )
        )
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()

    def test_missing_manifest_rejected(self):
        # On vérifie que self.execute_flow(self.nas_steps(execute=lambda *args, **kwargs: (0, self.m…
        # correspond à 'failed'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.execute_flow(
                self.nas_steps(execute=lambda *args, **kwargs: (0, self.manifest))
            )["status"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            "failed",
        )
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()

    def test_existing_run_cannot_be_returned_as_new_run(self):
        # On appelle self.fake_execute avec self.root.
        self.fake_execute(
            # On décide si le parcours s’arrête dès la première erreur, au lieu de laisser ce choix
            # implicite.
            self.root, self.reference, ["Synthetic"], 2026, stop_on_error=True
        )
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()

    def test_malformed_return_code_rejected(self):
        # On vérifie que self.execute_flow(self.nas_steps(execute=lambda *args, **kwargs: (True, sel…
        # correspond à 'failed'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.execute_flow(
                self.nas_steps(execute=lambda *args, **kwargs: (True, self.manifest))
            )["status"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            "failed",
        )

    def test_bundle_preparation_failure_stops_consumer(self):
        # On garde dans self.prepare_mock.side_effect la valeur renvoyée par ValueError pour
        # 'synthetic-control-error'.
        self.prepare_mock.side_effect = ValueError("synthetic-control-error")
        # On prépare consumed comme liste vide ; on la remplira au fil des opérations suivantes.
        consumed = []
        # On garde dans result le bilan du parcours exécuté avec les dépendances de cet essai.
        result = self.execute_flow(
            tail=[("load_simulated", lambda ctx: consumed.append(1))]
        )
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que consumed correspond à [].
        self.assertEqual(consumed, [])

    def test_bundle_pipeline_id_mismatch_rejected(self):
        def bad(root, relative):
            # On garde dans bundle le lot préparé par le double utilisé dans cet essai.
            bundle = self.fake_prepare(root, relative)
            # On utilise ce texte pour bundle['report']['pipeline_execution_id'] ; il ne dépend pas
            # d’une valeur récupérée ailleurs à cet endroit.
            bundle["report"]["pipeline_execution_id"] = "20261013_ffffffff"
            # On remet le lot préparé à l’appelant ; les étapes suivantes de cette fonction ne sont
            # plus parcourues.
            return bundle

        # On garde bad sous le nom self.prepare_mock.side_effect ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        self.prepare_mock.side_effect = bad
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")

    def test_bundle_excel_id_mismatch_rejected(self):
        def bad(root, relative):
            # On garde dans bundle le lot préparé par le double utilisé dans cet essai.
            bundle = self.fake_prepare(root, relative)
            # On utilise ce texte pour bundle['report']['excel_publication_id'] ; il ne dépend pas
            # d’une valeur récupérée ailleurs à cet endroit.
            bundle["report"]["excel_publication_id"] = "other"
            # On remet le lot préparé à l’appelant ; les étapes suivantes de cette fonction ne sont
            # plus parcourues.
            return bundle

        # On garde bad sous le nom self.prepare_mock.side_effect ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        self.prepare_mock.side_effect = bad
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")

    def test_bundle_publication_payload_mismatch_rejected(self):
        def bad(root, relative):
            # On garde dans bundle le lot préparé par le double utilisé dans cet essai.
            bundle = self.fake_prepare(root, relative)
            # On utilise ce texte pour bundle['publication']['extra'] ; il ne dépend pas d’une valeur
            # récupérée ailleurs à cet endroit.
            bundle["publication"]["extra"] = "different"
            # On remet le lot préparé à l’appelant ; les étapes suivantes de cette fonction ne sont
            # plus parcourues.
            return bundle

        # On garde bad sous le nom self.prepare_mock.side_effect ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        self.prepare_mock.side_effect = bad
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")

    def test_file_control_not_bypassed(self):
        # On garde dans self.files_mock.side_effect la valeur renvoyée par ValueError pour
        # 'changed-artifact'.
        self.files_mock.side_effect = ValueError("changed-artifact")
        # On vérifie que self.execute_flow()['status'] correspond à 'failed'.
        self.assertEqual(self.execute_flow()["status"], "failed")

    def test_future_consumer_blocks_modified_manifest(self):
        # On prépare consumed comme liste vide ; on la remplira au fil des opérations suivantes.
        consumed = []

        def consume(ctx):
            # On contrôle le résultat avec assert_nas_snapshot et les valeurs attendues indiquées juste
            # dessous.
            adapter.assert_nas_snapshot(
                # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
                ctx, ensure_excel=self.excel_guard, ensure_nas=self.files_mock
            )
            # On ajoute 1 à la fin de consumed ; les éléments précédents restent conservés.
            consumed.append(1)

        # On rassemble dans tail les 2 éléments explicitement indiqués pour ce cas d’essai.
        tail = [
            (
                "modify_simulated",
                lambda ctx: self.manifest.write_text(self.manifest.read_text() + "\n"),
            ),
            ("consume_simulated", consume),
        ]
        # On garde dans result le bilan du parcours exécuté avec les dépendances de cet essai.
        result = self.execute_flow(tail=tail)
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que consumed correspond à [].
        self.assertEqual(consumed, [])

    def test_default_real_executor_is_not_enabled(self):
        # On garde dans result le bilan du parcours exécuté avec les dépendances de cet essai.
        result = self.execute_flow(self.nas_steps(execute=None))
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On attend que self.manifest.exists() soit évalué comme faux pour ce cas de test.
        self.assertFalse(self.manifest.exists())
        # On vérifie que self.prepare_mock n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare_mock.assert_not_called()

    def test_success_does_not_rewrite_pilot_manifest(self):
        # On prépare content comme liste vide ; on la remplira au fil des opérations suivantes.
        content = []

        # On prépare les éléments du lot ou de la configuration définis dans ce module ; cela ne
        # constitue pas à soi seul une exécution métier réussie.
        def prepare(root, relative):
            # On ajoute self.manifest.read_bytes() à la fin de content ; les éléments précédents
            # restent conservés.
            content.append(self.manifest.read_bytes())
            # On fournit à l’appelant le lot préparé par le double utilisé dans cet essai.
            return self.fake_prepare(root, relative)

        # On garde prepare sous le nom self.prepare_mock.side_effect ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        self.prepare_mock.side_effect = prepare
        # On vérifie que self.execute_flow()['status'] correspond à 'success'.
        self.assertEqual(self.execute_flow()["status"], "success")
        # On vérifie que self.manifest.read_bytes() correspond à content[0].
        self.assertEqual(self.manifest.read_bytes(), content[0])

    def test_real_pilot_with_simulated_children(self):
        # On rend disponibles TestRunLocalPipeline, p depuis test_run_local_pipeline, pour les appels
        # de ce fichier.
        from test_run_local_pipeline import TestRunLocalPipeline, p

        # On garde dans fixture la valeur renvoyée par TestRunLocalPipeline.
        fixture = TestRunLocalPipeline()
        # On initialise les ressources du scénario fixture avec sa méthode setUp.
        fixture.setUp()
        # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
        try:
            # On garde dans root le chemin absolu résolu de fixture.root, en tenant compte des liens
            # symboliques.
            root = fixture.root.resolve()
            # On utilise ce texte pour relative ; il ne dépend pas d’une valeur récupérée ailleurs à
            # cet endroit.
            relative = "data/03_normalized/suivi_acquisitions_normalises/publications/synthetic_pub/reference.csv"
            # On calcule ce quotient pour construire reference.
            reference = root / relative
            # On prépare le dossier reference.parent avec les règles de création indiquées ; aucun
            # résultat métier n’est encore produit par cette création.
            reference.parent.mkdir(parents=True)
            # On écrit le contenu préparé dans reference ; cette opération remplace le contenu du
            # fichier s’il existe déjà.
            reference.write_bytes(fixture.reference.read_bytes())
            # On regroupe dans publication ces champs nommés ; on pourra les retrouver par leur clé
            # plutôt que par leur position.
            publication = {
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": "synthetic_pub",
                # On renseigne le repère utilisé pour les données Excel sous la clé 'reference'.
                "reference": {
                    # On renseigne le chemin de travail sous la clé 'path'.
                    "path": relative,
                    # On conserve l’empreinte attendue pour retrouver la même version du contenu.
                    "sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
                },
            }
            # On regroupe dans outcome ces champs nommés ; on pourra les retrouver par leur clé plutôt
            # que par leur position.
            outcome = {
                # On renseigne l’état du traitement sous la clé 'status'.
                "status": "unchanged",
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": "synthetic_pub",
                # On renseigne le chemin du tableau Excel regroupé sous la clé 'reference_path'.
                "reference_path": relative,
            }
            # On garde dans current un double de test dont les réponses et les appels pourront être
            # contrôlés.
            current = Mock()
            # On prépare pour guard une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
            # appelée, pas lors de cette affectation.
            guard = lambda ctx: assert_excel_snapshot(ctx, ensure_current=current)
            # On garde dans excel les fonctions des étapes Excel, construites sans les exécuter encore.
            excel = build_excel_steps(
                root,
                # On transmet la sélection explicite des domaines concernés par cet appel.
                vineyards=["DomaineDemoB"],
                ingest=lambda *args, **kwargs: outcome,
                prepare=lambda r: {"publication": publication},
                # On fournit la vérification de stabilité du lot, réutilisable avant ses consommateurs.
                ensure_current=current,
            )

            # On prépare les éléments du lot ou de la configuration définis dans ce module ; cela ne
            # constitue pas à soi seul une exécution métier réussie.
            def prepare(r, rel):
                # On garde dans manifest les objets Python décodés depuis le JSON fourni.
                manifest = json.loads((r / rel).read_text(encoding="utf-8"))
                # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver
                # chaque information par sa clé.
                return {
                    # On renseigne le manifeste du lot sous la clé 'manifest'.
                    "manifest": manifest,
                    # On renseigne la publication Excel sous la clé 'publication'.
                    "publication": publication,
                    # On renseigne le bilan sous la clé 'report'.
                    "report": {
                        # On renseigne l’identifiant du traitement NAS sous la clé
                        # 'pipeline_execution_id'.
                        "pipeline_execution_id": manifest["pipeline_execution_id"],
                        # On renseigne l’identifiant du lot Excel sous la clé 'excel_publication_id'.
                        "excel_publication_id": "synthetic_pub",
                    },
                }

            # On garde dans nas la valeur renvoyée par adapter.build_nas_steps.
            nas = adapter.build_nas_steps(
                root,
                # On transmet la sélection explicite des domaines concernés par cet appel.
                vineyards=["DomaineDemoB"],
                select=p.select_vineyards,
                execute=lambda r, ref, names, y, **kwargs: p.execute_pipeline(
                    r, ref, names, y, executor=fixture.fake, **kwargs
                ),
                prepare=prepare,
                # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
                ensure_excel=guard,
                # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
                ensure_nas=Mock(),
            )
            # On utilise contextlib.redirect_stdout(io.StringIO()) dans son contexte de gestion ; les
            # opérations de sortie sont exécutées en quittant le bloc.
            with contextlib.redirect_stdout(io.StringIO()):
                # On garde dans result le bilan du parcours après l’appel de ses étapes et de son
                # journal.
                result = run_workflow(
                    root,
                    excel + nas,
                    # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                    trigger_mode="integration_test",
                    # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                    scope={"year": 2026, "vineyards": ["DomaineDemoB"]},
                )
            # On vérifie que result['status'] correspond à 'success'.
            self.assertEqual(result["status"], "success")
            # On vérifie que len(fixture.calls) correspond à 2.
            self.assertEqual(len(fixture.calls), 2)
            # On vérifie que result['excel_publication_id'] correspond à 'synthetic_pub'.
            self.assertEqual(result["excel_publication_id"], "synthetic_pub")
            # On vérifie que result['pipeline_execution_id'] n’est pas None.
            self.assertIsNotNone(result["pipeline_execution_id"])
        finally:
            # On appelle fixture.doCleanups sans argument positionnel.
            fixture.doCleanups()

    def test_real_preparation_of_synthetic_nas_bundle(self):
        # On rend disponibles build_bundles depuis synthetic_import_fixtures, pour les appels de ce
        # fichier.
        from synthetic_import_fixtures import build_bundles
        # On rend disponibles check_still_current depuis import_excel_publication, pour les appels de
        # ce fichier.
        from import_excel_publication import check_still_current
        # On rend disponibles prepare_bundle, check_files depuis load_nas_reconciliation, pour les
        # appels de ce fichier.
        from load_nas_reconciliation import prepare_bundle, check_files

        # On répartit les valeurs renvoyées par build_bundles entre (fixtures, bundles) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        fixtures, bundles = build_bundles(PROJECT_ROOT)
        # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
        try:
            # On distribue ces valeurs entre excel_bundle, nas_bundle, dans l’ordre de l’affectation.
            # Chaque nom reçoit son propre élément.
            excel_bundle, nas_bundle = bundles[0], bundles[1]
            # On garde dans root le chemin absolu résolu de fixtures[0].root, en tenant compte des
            # liens symboliques.
            root = fixtures[0].root.resolve()
            # On garde fixtures[2].root sous le nom source ; cette affectation ne copie pas à elle
            # seule un objet mutable.
            source = fixtures[2].root
            # On garde fixtures[2].manifest_path sous le nom relative ; cette affectation ne copie pas
            # à elle seule un objet mutable.
            relative = fixtures[2].manifest_path
            # On reprend les métadonnées de la publication dans excel_bundle ; cet accès suppose que
            # la clé a été produite ou vérifiée auparavant.
            pub = excel_bundle["publication"]
            # On regroupe dans outcome ces champs nommés ; on pourra les retrouver par leur clé plutôt
            # que par leur position.
            outcome = {
                # On renseigne l’état du traitement sous la clé 'status'.
                "status": "unchanged",
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": pub["publication_id"],
                # On renseigne le chemin du tableau Excel regroupé sous la clé 'reference_path'.
                "reference_path": pub["reference"]["path"],
            }
            # On garde dans excel les fonctions des étapes Excel, construites sans les exécuter encore.
            excel = build_excel_steps(
                root,
                # On transmet la sélection explicite des domaines concernés par cet appel.
                vineyards=["DomaineDemoB"],
                ingest=lambda *args, **kwargs: outcome,
                prepare=lambda r: excel_bundle,
                # On fournit la vérification de stabilité du lot, réutilisable avant ses consommateurs.
                ensure_current=check_still_current,
            )

            def execute(r, reference, names, y, **kwargs):
                # Copier uniquement les sorties NAS de cette execution.
                # Ne jamais remplacer les publications Excel deja controlees.
                needed = [relative, nas_bundle["manifest"]["reference_snapshot"]]
                # On ajoute [item['path'] for item in nas_bundle['report']['artifacts']] à needed et on
                # conserve ce nouvel état pour la suite.
                needed += [item["path"] for item in nas_bundle["report"]["artifacts"]]
                # On parcourt needed ; path désigne l’élément courant de ce scénario.
                for path in needed:
                    # On calcule ce quotient pour construire destination.
                    destination = root / path
                    # On prépare le dossier destination.parent avec les règles de création indiquées ;
                    # aucun résultat métier n’est encore produit par cette création.
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    # On appelle shutil.copyfile avec source / path.
                    shutil.copyfile(source / path, destination)
                # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
                # décompose.
                return 0, root / relative

            # On prépare pour guard une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
            # appelée, pas lors de cette affectation.
            guard = lambda ctx: assert_excel_snapshot(
                # On fournit la vérification de stabilité du lot, réutilisable avant ses consommateurs.
                ctx, ensure_current=check_still_current
            )
            # On garde dans nas la valeur renvoyée par adapter.build_nas_steps.
            nas = adapter.build_nas_steps(
                root,
                # On transmet la sélection explicite des domaines concernés par cet appel.
                vineyards=["DomaineDemoB"],
                select=lambda *args: ["DomaineDemoB"],
                execute=execute,
                prepare=prepare_bundle,
                # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
                ensure_excel=guard,
                # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
                ensure_nas=check_files,
            )
            # On garde dans result le bilan du parcours après l’appel de ses étapes et de son journal.
            result = run_workflow(
                root,
                excel + nas,
                # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                trigger_mode="integration_test",
                # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                scope={"year": 2026, "vineyards": ["DomaineDemoB"]},
            )
            # On vérifie que result['status'] correspond à 'success'.
            self.assertEqual(result["status"], "success")
            # On vérifie que result['pipeline_execution_id'] correspond à
            # nas_bundle['report']['pipeline_execution_id'].
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                result["pipeline_execution_id"],
                # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
                nas_bundle["report"]["pipeline_execution_id"],
            )
        finally:
            # On parcourt reversed(fixtures) ; fixture désigne l’élément courant de ce scénario.
            for fixture in reversed(fixtures):
                # On appelle fixture.doCleanups sans argument positionnel.
                fixture.doCleanups()


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
