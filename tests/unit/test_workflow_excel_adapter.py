# Lecture du fichier — Tests de workflow excel adapter.
#

"""Adaptateur teste avec appels simules et fichiers fictifs temporaires uniquement."""

# On décrit les champs d’un objet de données sans écrire toute sa construction à la main.
from dataclasses import FrozenInstanceError
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Mock depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import Mock
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On récupère Path(__file__).resolve().parents[2] et on le garde dans PROJECT_ROOT pour la suite.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
# On importe workflow_excel_adapter sous le nom adapter. Ce module sera utilisé par les opérations de
# ce fichier.
import workflow_excel_adapter as adapter
# On rend disponibles WorkflowContext, run_workflow depuis workflow_runtime, pour les appels de ce
# fichier.
from workflow_runtime import WorkflowContext, run_workflow


class TestWorkflowExcelAdapter(unittest.TestCase):
    def setUp(self):
        # On garde dans temp un dossier temporaire distinct des données du projet.
        temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(temp.name)
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
        self.reference.write_bytes(b"Vineyard,Acquisition_ID\nSynthetic,fake\n")
        # On regroupe dans self.bundle ces champs nommés ; on pourra les retrouver par leur clé plutôt
        # que par leur position.
        self.bundle = {
            # On renseigne la publication Excel sous la clé 'publication'.
            "publication": {
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": "synthetic_pub",
                # On renseigne le repère utilisé pour les données Excel sous la clé 'reference'.
                "reference": {
                    # On renseigne le chemin de travail sous la clé 'path'.
                    "path": self.relative,
                    # On conserve l’empreinte attendue pour retrouver la même version du contenu.
                    "sha256": hashlib.sha256(self.reference.read_bytes()).hexdigest(),
                },
            }
        }
        # On regroupe dans self.outcome ces champs nommés ; on pourra les retrouver par leur clé plutôt
        # que par leur position.
        self.outcome = {
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "success",
            # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
            "publication_id": "synthetic_pub",
            # On renseigne le chemin du tableau Excel regroupé sous la clé 'reference_path'.
            "reference_path": self.relative,
        }
        # On garde dans self.ingest un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.ingest = Mock(return_value=self.outcome)
        # On garde dans self.prepare un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.prepare = Mock(return_value=self.bundle)
        # On garde dans self.current un double de test dont les réponses et les appels pourront être
        # contrôlés.
        self.current = Mock()

    def steps(self, **kwargs):
        # On regroupe dans options ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        options = {
            # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
            "vineyards": ["Synthetic"],
            # On associe la clé 'ingest' à cette valeur dans les données de ce scénario.
            "ingest": self.ingest,
            # On associe la clé 'prepare' à cette valeur dans les données de ce scénario.
            "prepare": self.prepare,
            # On associe la clé 'ensure_current' à cette valeur dans les données de ce scénario.
            "ensure_current": self.current,
        }
        # On complète options avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        options.update(kwargs)
        # On fournit à l’appelant la valeur renvoyée par adapter.build_excel_steps.
        return adapter.build_excel_steps(self.root, **options)

    def execute(self, steps=None):
        # On fournit à l’appelant le bilan du parcours après l’appel de ses étapes et de son journal.
        return run_workflow(
            self.root,
            self.steps() if steps is None else steps,
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="integration_test",
            # On fournit le périmètre du traitement via le paramètre scope de cet appel.
            scope={"year": 2026, "vineyards": ["Synthetic"]},
        )

    # On suit le parcours normal : les trois étapes doivent se terminer et garder le même
    # identifiant de publication.
    def test_three_stages_success_and_publication_pinned(self):
        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute()
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que result['completed_steps'] correspond à ['excel_ingestion',
        # 'excel_publication_check', 'excel_reference_pin'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            result["completed_steps"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ["excel_ingestion", "excel_publication_check", "excel_reference_pin"],
        )
        # On vérifie que result['excel_publication_id'] correspond à 'synthetic_pub'.
        self.assertEqual(result["excel_publication_id"], "synthetic_pub")
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        self.ingest.assert_called_once_with(
            # On transmet la sélection explicite des domaines concernés par cet appel.
            self.root, vineyards=["Synthetic"], all_vineyards=False
        )
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        self.prepare.assert_called_once_with(self.root)
        # On vérifie que self.current.call_count correspond à 2.
        self.assertEqual(self.current.call_count, 2)

    # Un Excel inchangé ne signifie pas que le NAS est inchangé. La suite du parcours doit donc
    # rester possible.
    def test_unchanged_does_not_skip_following_observation(self):
        # On utilise ce texte pour self.outcome['status'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        self.outcome["status"] = "unchanged"
        # On prépare observations comme liste vide ; on la remplira au fil des opérations suivantes.
        observations = []

        def fake_nas(ctx):
            # On garde dans pinned la valeur renvoyée par adapter.assert_excel_snapshot.
            pinned = adapter.assert_excel_snapshot(ctx, ensure_current=self.current)
            # On ajoute pinned.publication_id à la fin de observations ; les éléments précédents
            # restent conservés.
            observations.append(pinned.publication_id)

        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute(self.steps() + [("nas_simulated", fake_nas)])
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que observations correspond à ['synthetic_pub'].
        self.assertEqual(observations, ["synthetic_pub"])
        # On vérifie que self.current.call_count correspond à 3.
        self.assertEqual(self.current.call_count, 3)

    def test_all_vineyards_forwarded_explicitly(self):
        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute(self.steps(vineyards=None, all_vineyards=True))
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        self.ingest.assert_called_once_with(
            # On transmet la sélection explicite des domaines concernés par cet appel.
            self.root, vineyards=None, all_vineyards=True
        )

    # Les espaces et la casse ne doivent pas transformer un même domaine en deux domaines à traiter.
    def test_case_insensitive_selection_deduplicated(self):
        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute(self.steps(vineyards=[" Synthetic ", "SYNTHETIC"]))
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        self.ingest.assert_called_once_with(
            # On transmet la sélection explicite des domaines concernés par cet appel.
            self.root, vineyards=["Synthetic"], all_vineyards=False
        )

    def test_missing_selection_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.steps sans argument positionnel.
            self.steps(vineyards=None)
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()

    def test_conflicting_selection_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.steps sans argument positionnel.
            self.steps(all_vineyards=True)
        # On vérifie que self.ingest n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.ingest.assert_not_called()

    # Si la lecture Excel échoue, on ne doit pas préparer la publication suivante comme si elle
    # avait réussi.
    def test_ingestion_exception_stops_next_stages(self):
        # On garde dans self.ingest.side_effect la valeur renvoyée par ValueError pour
        # 'synthetic-ingestion-error'.
        self.ingest.side_effect = ValueError("synthetic-ingestion-error")
        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute()
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que result['completed_steps'] correspond à [].
        self.assertEqual(result["completed_steps"], [])
        # On vérifie que self.prepare n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare.assert_not_called()

    def test_failed_or_reporting_error_outcome_rejected(self):
        # On parcourt ('failed', 'reporting_error_after_publication') ; status désigne l’élément
        # courant de ce scénario.
        for status in ("failed", "reporting_error_after_publication"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(status=status):
                # On garde l’état du traitement sous le nom self.outcome['status'] ; cette affectation
                # ne copie pas à elle seule un objet mutable.
                self.outcome["status"] = status
                # On garde dans result le résultat de l’appel encadré par ce scénario de test.
                result = self.execute()
                # On vérifie que result['status'] correspond à 'failed'.
                self.assertEqual(result["status"], "failed")
                # On attend None pour result['excel_publication_id'] : aucune valeur n’est confirmée
                # dans ce cas.
                self.assertIsNone(result["excel_publication_id"])
        # On vérifie que self.prepare n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare.assert_not_called()

    def test_missing_ingestion_identifiers_rejected(self):
        # On regroupe dans self.ingest.return_value ces champs nommés ; on pourra les retrouver par
        # leur clé plutôt que par leur position.
        self.ingest.return_value = {"status": "success"}
        # On vérifie que self.execute()['status'] correspond à 'failed'.
        self.assertEqual(self.execute()["status"], "failed")
        # On vérifie que self.prepare n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        self.prepare.assert_not_called()

    def test_different_publication_rejected(self):
        # On utilise ce texte pour self.bundle['publication']['publication_id'] ; il ne dépend pas
        # d’une valeur récupérée ailleurs à cet endroit.
        self.bundle["publication"]["publication_id"] = "different_pub"
        # On garde dans self.bundle['publication']['reference']['path'] le résultat du remplacement
        # demandé sur self.relative.
        self.bundle["publication"]["reference"]["path"] = self.relative.replace(
            "synthetic_pub", "different_pub"
        )
        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute()
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que result['completed_steps'] correspond à ['excel_ingestion'].
        self.assertEqual(result["completed_steps"], ["excel_ingestion"])
        # On attend None pour result['excel_publication_id'] : aucune valeur n’est confirmée dans ce
        # cas.
        self.assertIsNone(result["excel_publication_id"])

    def test_different_ingestion_reference_rejected(self):
        # On utilise ce texte pour self.outcome['reference_path'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        self.outcome["reference_path"] = "data/other.csv"
        # On vérifie que self.execute()['status'] correspond à 'failed'.
        self.assertEqual(self.execute()["status"], "failed")

    # Le contrôle signale un changement de publication : on vérifie que le workflow ne continue pas
    # avec ce nouveau lot.
    def test_current_publication_guard_is_not_bypassed(self):
        # On garde dans self.current.side_effect la valeur renvoyée par ValueError pour
        # 'registry-changed'.
        self.current.side_effect = ValueError("registry-changed")
        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute()
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On attend None pour result['excel_publication_id'] : aucune valeur n’est confirmée dans ce
        # cas.
        self.assertIsNone(result["excel_publication_id"])

    # On modifie volontairement le fichier entre les contrôles. Son ancienne empreinte ne doit plus
    # être acceptée.
    def test_reference_modified_before_pin_rejected(self):
        # On prépare calls comme liste vide ; on la remplira au fil des opérations suivantes.
        calls = []

        def current(bundle):
            # On ajoute 1 à la fin de calls ; les éléments précédents restent conservés.
            calls.append(1)
            # On vérifie ce cas avant la suite : len(calls) correspond à 2.
            if len(calls) == 2:
                # On écrit le contenu préparé dans self.reference ; cette opération remplace le contenu
                # du fichier s’il existe déjà.
                self.reference.write_bytes(b"modified")

        # On garde current sous le nom self.current.side_effect ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        self.current.side_effect = current
        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute()
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que result['completed_steps'] correspond à ['excel_ingestion',
        # 'excel_publication_check'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            result["completed_steps"], ["excel_ingestion", "excel_publication_check"]
        )
        # On attend None pour result['excel_publication_id'] : aucune valeur n’est confirmée dans ce
        # cas.
        self.assertIsNone(result["excel_publication_id"])

    def test_reference_outside_immutable_publication_rejected(self):
        # On utilise ce texte pour self.outcome['reference_path'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        self.outcome["reference_path"] = "data/../outside.csv"
        # On utilise ce texte pour self.bundle['publication']['reference']['path'] ; il ne dépend pas
        # d’une valeur récupérée ailleurs à cet endroit.
        self.bundle["publication"]["reference"]["path"] = "data/../outside.csv"
        # On vérifie que self.execute()['status'] correspond à 'failed'.
        self.assertEqual(self.execute()["status"], "failed")

    def test_invalid_reference_hash_rejected(self):
        # On utilise ce texte pour self.bundle['publication']['reference']['sha256'] ; il ne dépend pas
        # d’une valeur récupérée ailleurs à cet endroit.
        self.bundle["publication"]["reference"]["sha256"] = "invalid"
        # On vérifie que self.execute()['status'] correspond à 'failed'.
        self.assertEqual(self.execute()["status"], "failed")

    def test_consumer_blocks_modified_reference_after_pin(self):
        # On prépare consumed comme liste vide ; on la remplira au fil des opérations suivantes.
        consumed = []

        def consume(ctx):
            # On contrôle le résultat avec assert_excel_snapshot et les valeurs attendues indiquées
            # juste dessous.
            adapter.assert_excel_snapshot(ctx, ensure_current=self.current)
            # On ajoute True à la fin de consumed ; les éléments précédents restent conservés.
            consumed.append(True)

        # On assemble ces deux éléments pour construire steps.
        steps = self.steps() + [
            ("modify_simulated", lambda ctx: self.reference.write_bytes(b"changed")),
            ("consume_simulated", consume),
        ]
        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute(steps)
        # On vérifie que result['status'] correspond à 'failed'.
        self.assertEqual(result["status"], "failed")
        # On vérifie que consumed correspond à [].
        self.assertEqual(consumed, [])
        # On vérifie que result['excel_publication_id'] correspond à 'synthetic_pub'.
        self.assertEqual(result["excel_publication_id"], "synthetic_pub")

    def test_consumer_blocks_registry_change_after_pin(self):
        # On prépare checks comme liste vide ; on la remplira au fil des opérations suivantes.
        checks = []

        def current(bundle):
            # On ajoute 1 à la fin de checks ; les éléments précédents restent conservés.
            checks.append(1)
            # On vérifie ce cas avant la suite : len(checks) correspond à 3.
            if len(checks) == 3:
                # On interrompt cette branche avec ValueError : 'registry-changed'.
                raise ValueError("registry-changed")

        # On garde current sous le nom self.current.side_effect ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        self.current.side_effect = current
        # On assemble ces deux éléments pour construire steps.
        steps = self.steps() + [
            (
                "consume_simulated",
                lambda ctx: adapter.assert_excel_snapshot(
                    # On fournit la vérification de stabilité du lot, réutilisable avant ses
                    # consommateurs.
                    ctx, ensure_current=self.current
                ),
            )
        ]
        # On vérifie que self.execute(steps)['status'] correspond à 'failed'.
        self.assertEqual(self.execute(steps)["status"], "failed")

    def test_reference_result_is_immutable_and_native_path(self):
        # On prépare observed comme liste vide ; on la remplira au fil des opérations suivantes.
        observed = []

        def inspect(ctx):
            # On récupère ctx.results['excel_reference_pin'] et on le garde dans pinned pour la suite.
            pinned = ctx.results["excel_reference_pin"]
            # On vérifie que pinned.reference_path correspond à self.reference.
            self.assertEqual(pinned.reference_path, self.reference)
            # On attend FrozenInstanceError dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(FrozenInstanceError):
                # On utilise ce texte pour pinned.publication_id ; il ne dépend pas d’une valeur
                # récupérée ailleurs à cet endroit.
                pinned.publication_id = "other"
            # On ajoute True à la fin de observed ; les éléments précédents restent conservés.
            observed.append(True)

        # On vérifie que self.execute(self.steps() + [('inspect_simulated', inspect)])['status']
        # correspond à 'success'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.execute(self.steps() + [("inspect_simulated", inspect)])["status"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            "success",
        )
        # On vérifie que observed correspond à [True].
        self.assertEqual(observed, [True])

    def test_result_payloads_are_not_written_to_journal(self):
        # On utilise ce texte pour self.bundle['private_debug'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        self.bundle["private_debug"] = "synthetic-value-not-for-journal"
        # On garde dans result le résultat de l’appel encadré par ce scénario de test.
        result = self.execute()
        # On garde dans raw le texte lu depuis self.root / result['journal_relative_path'] avec
        # l’encodage indiqué.
        raw = (self.root / result["journal_relative_path"]).read_text(encoding="utf-8")
        # On vérifie que 'synthetic-value-not-for-journal' ne figure pas dans raw.
        self.assertNotIn("synthetic-value-not-for-journal", raw)
        # On vérifie que json.loads(raw.splitlines()[-1])['excel_publication_id'] correspond à
        # 'synthetic_pub'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            json.loads(raw.splitlines()[-1])["excel_publication_id"], "synthetic_pub"
        )

    def test_real_prepared_synthetic_bundle_uses_existing_current_guard(self):
        # On rend disponibles build_bundles depuis synthetic_import_fixtures, pour les appels de ce
        # fichier.
        from synthetic_import_fixtures import build_bundles
        # On rend disponibles check_still_current depuis import_excel_publication, pour les appels de
        # ce fichier.
        from import_excel_publication import check_still_current

        # On répartit les valeurs renvoyées par build_bundles entre (fixtures, bundles) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        fixtures, bundles = build_bundles(PROJECT_ROOT)
        # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
        try:
            # On récupère bundles[0] et on le garde dans bundle pour la suite.
            bundle = bundles[0]
            # On garde dans root le chemin absolu résolu de fixtures[0].root, en tenant compte des
            # liens symboliques.
            root = fixtures[0].root.resolve()
            # On reprend les métadonnées de la publication dans bundle ; cet accès suppose que la
            # clé a été produite ou vérifiée auparavant.
            publication = bundle["publication"]
            # On regroupe dans outcome ces champs nommés ; on pourra les retrouver par leur clé plutôt
            # que par leur position.
            outcome = {
                # On renseigne l’état du traitement sous la clé 'status'.
                "status": "unchanged",
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": publication["publication_id"],
                # On renseigne le chemin du tableau Excel regroupé sous la clé 'reference_path'.
                "reference_path": publication["reference"]["path"],
            }
            # On garde dans steps la valeur renvoyée par adapter.build_excel_steps.
            steps = adapter.build_excel_steps(
                root,
                # On transmet la sélection explicite des domaines concernés par cet appel.
                vineyards=["DomaineDemoB"],
                ingest=lambda *args, **kwargs: outcome,
                prepare=lambda local_root: bundle,
                # On fournit la vérification de stabilité du lot, réutilisable avant ses consommateurs.
                ensure_current=check_still_current,
            )
            # On garde dans result le bilan du parcours après l’appel de ses étapes et de son journal.
            result = run_workflow(
                root,
                steps,
                # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                trigger_mode="integration_test",
                # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                scope={"year": 2026, "vineyards": ["DomaineDemoB"]},
            )
            # On vérifie que result['status'] correspond à 'success'.
            self.assertEqual(result["status"], "success")
            # On vérifie que result['excel_publication_id'] correspond à publication['publication_id'].
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                result["excel_publication_id"], publication["publication_id"]
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
