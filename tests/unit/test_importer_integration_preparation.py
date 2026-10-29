# Lecture du fichier — Tests de importer integration preparation.
#

"""Preparation et garde-fous locaux : aucune connexion PostgreSQL."""

# On rend disponibles Path, PureWindowsPath depuis pathlib, pour les appels de ce fichier.
from pathlib import Path, PureWindowsPath
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch
# On rend disponibles SimpleNamespace depuis types, pour les appels de ce fichier.
from types import SimpleNamespace

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On importe synthetic_import_fixtures sous le nom synthetic. Ce module sera utilisé par les opérations
# de ce fichier.
import synthetic_import_fixtures as synthetic
# On rend disponibles build_bundles, manifest_sibling depuis synthetic_import_fixtures, pour les appels
# de ce fichier.
from synthetic_import_fixtures import build_bundles, manifest_sibling
# On importe test_importer_postgres_integration sous le nom integration. Ce module sera utilisé par les
# opérations de ce fichier.
import test_importer_postgres_integration as integration
# On rend disponibles guard_test_database, PREFIX, IMPORT_TABLES depuis
# test_importer_postgres_integration, pour les appels de ce fichier.
from test_importer_postgres_integration import (
    guard_test_database,
    PREFIX,
    IMPORT_TABLES,
)


class TestImporterIntegrationPreparation(unittest.TestCase):
    def test_import_table_scope_is_explicit_and_excludes_journal(self):
        # On vérifie que len(IMPORT_TABLES) correspond à 20.
        self.assertEqual(len(IMPORT_TABLES), 20)
        # On vérifie que len(set(IMPORT_TABLES)) correspond à 20.
        self.assertEqual(len(set(IMPORT_TABLES)), 20)
        # On vérifie que 'core.workflow_execution_events' ne figure pas dans IMPORT_TABLES.
        self.assertNotIn("core.workflow_execution_events", IMPORT_TABLES)
        # On vérifie que 'core.excel_current_publication' figure dans IMPORT_TABLES.
        self.assertIn("core.excel_current_publication", IMPORT_TABLES)
        # On vérifie que 'core.current_vineyard_reconciliations' figure dans IMPORT_TABLES.
        self.assertIn("core.current_vineyard_reconciliations", IMPORT_TABLES)
        # On attend que all((name.startswith(('core.', 'staging.')) for name in IMPORT_TABLES)) soit
        # évalué comme vrai pour ce cas de test.
        self.assertTrue(
            all(name.startswith(("core.", "staging.")) for name in IMPORT_TABLES)
        )

    def test_run_checks_does_not_take_tables_from_general_connection_checker(self):
        class StopBeforeImports(Exception):
            # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe
            # parente.
            pass

        # On garde dans connection la valeur renvoyée par object.
        connection = object()
        # On regroupe dans modules ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        modules = {
            # On associe la clé 'check_import_connection' à cette valeur dans les données de ce
            # scénario.
            "check_import_connection": SimpleNamespace(
                TABLES=("core.workflow_execution_events",)
            ),
            # On associe la clé 'import_excel_publication' à cette valeur dans les données de ce
            # scénario.
            "import_excel_publication": SimpleNamespace(),
            # On associe la clé 'load_nas_reconciliation' à cette valeur dans les données de ce
            # scénario.
            "load_nas_reconciliation": SimpleNamespace(),
        }
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(sys.modules, modules),
            patch.object(
                # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
                # suivre une fonction de test.
                integration, "snapshot", side_effect=StopBeforeImports
            ) as snapshot,
        ):
            # On attend StopBeforeImports dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(StopBeforeImports):
                # On appelle integration.run_checks avec connection.
                integration.run_checks(connection, ({}, {}, {}, {}))
            # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ;
            # une valeur correcte obtenue par le mauvais appel ne suffirait pas.
            snapshot.assert_called_once_with(connection, IMPORT_TABLES)

    def test_main_database_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle guard_test_database avec 'suivi_acquisitions'.
            guard_test_database("suivi_acquisitions")

    def test_other_database_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle guard_test_database avec 'postgres'.
            guard_test_database("postgres")

    def test_injection_name_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle guard_test_database avec PREFIX + 'x;DROP'.
            guard_test_database(PREFIX + "x;DROP")

    def test_test_name_accepted(self):
        # On vérifie que guard_test_database(PREFIX + '20261008_120000_abcdef') correspond à PREFIX +
        # '20261008_120000_abcdef'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            guard_test_database(PREFIX + "20261008_120000_abcdef"),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            PREFIX + "20261008_120000_abcdef",
        )

    def test_manifest_sibling_stays_posix_with_windows_native_path(self):
        # On utilise ce texte pour path ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        path = "data/03_normalized/publications/synthetic/manifest.json"
        # On remplace temporairement synthetic dans ce bloc de test ; le réglage initial sera rétabli à
        # sa sortie.
        with patch.object(synthetic, "Path", PureWindowsPath):
            # On garde dans result la valeur renvoyée par manifest_sibling.
            result = manifest_sibling(path, "reference.csv")
        # On vérifie que result correspond à 'data/03_normalized/publications/synthetic/reference.csv'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            result, "data/03_normalized/publications/synthetic/reference.csv"
        )
        # On vérifie que '\\' ne figure pas dans result.
        self.assertNotIn("\\", result)

    def test_two_excel_and_nas_generations_are_coherent(self):
        # On répartit les valeurs renvoyées par build_bundles entre (fixtures, bundles) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        fixtures, bundles = build_bundles(Path(__file__).resolve().parents[2])
        # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
        try:
            # On répartit les éléments de bundles entre (e1, n1, e2, n2), dans l’ordre indiqué.
            e1, n1, e2, n2 = bundles
            # On vérifie que len(e1['reference_rows']) correspond à 2.
            self.assertEqual(len(e1["reference_rows"]), 2)
            # On vérifie que e1['publication']['versions']['domainedemob']['version_id'] correspond à
            # e2['publication']['versions']['domainedemob']['version_id'].
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                e1["publication"]["versions"]["domainedemob"]["version_id"],
                # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
                e2["publication"]["versions"]["domainedemob"]["version_id"],
            )
            # On vérifie que e1['publication']['publication_id'] diffère de
            # e2['publication']['publication_id'].
            self.assertNotEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                e1["publication"]["publication_id"], e2["publication"]["publication_id"]
            )
            # On parcourt ((e1, n1), (e2, n2)) ; (e, n) désigne l’élément courant de ce scénario.
            for e, n in ((e1, n1), (e2, n2)):
                # On vérifie que e['publication'] correspond à n['publication'].
                self.assertEqual(e["publication"], n["publication"])
                # On vérifie que len(n['records']['staging.reconciliation_acquisition_rows'])
                # correspond à 1.
                self.assertEqual(
                    # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                    len(n["records"]["staging.reconciliation_acquisition_rows"]), 1
                )
                # On vérifie que len(n['records']['staging.reconciliation_association_rows'])
                # correspond à 1.
                self.assertEqual(
                    # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                    len(n["records"]["staging.reconciliation_association_rows"]), 1
                )
                # On vérifie que len(n['records']['staging.reconciliation_passage_rows']) correspond à
                # 1.
                self.assertEqual(
                    # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                    len(n["records"]["staging.reconciliation_passage_rows"]), 1
                )
            # On vérifie que n1['report']['pipeline_execution_id'] diffère de
            # n2['report']['pipeline_execution_id'].
            self.assertNotEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                n1["report"]["pipeline_execution_id"],
                # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
                n2["report"]["pipeline_execution_id"],
            )

            # Verifier les chemins effectivement exportes dans chaque manifeste.
            def assert_manifest_paths(value):
                # On réserve cette branche à value lorsqu’il est de type dict.
                if isinstance(value, dict):
                    # On parcourt value.items() ; (key, item) désigne l’élément courant de ce scénario.
                    for key, item in value.items():
                        # Cette branche traite le cas où item est du type str et au moins un des cas
                        # regroupés ici est rencontré.
                        if isinstance(item, str) and (
                            key == "path"
                            # Ce cas est aussi retenu si la clé de l’élément se termine par le texte
                            # '_path'.
                            or key.endswith("_path")
                            # Ce cas est aussi retenu si la clé de l’élément appartient à
                            # ('reference_source', 'reference_snapshot', 'manifest',
                            # 'publication_manif….
                            or key
                            in (
                                "reference_source",
                                "reference_snapshot",
                                "manifest",
                                "publication_manifest",
                            )
                        ):
                            # On vérifie que '\\' ne figure pas dans item.
                            self.assertNotIn("\\", item)
                        # On appelle assert_manifest_paths avec item.
                        assert_manifest_paths(item)
                # On réserve cette branche à value lorsqu’il est de type list.
                elif isinstance(value, list):
                    # On parcourt la valeur reçue ; item désigne l’élément courant de ce scénario.
                    for item in value:
                        # On appelle assert_manifest_paths avec item.
                        assert_manifest_paths(item)

            # On parcourt fixtures ; fixture désigne l’élément courant de ce scénario.
            for fixture in fixtures:
                # On parcourt fixture.root.rglob('manifest.json') ; path désigne l’élément courant de
                # ce scénario.
                for path in fixture.root.rglob("manifest.json"):
                    # On importe json. On lit ou écrit les objets et manifestes au format JSON.
                    import json

                    # On appelle assert_manifest_paths avec
                    # json.loads(path.read_text(encoding='utf-8-sig')).
                    assert_manifest_paths(
                        json.loads(path.read_text(encoding="utf-8-sig"))
                    )
        finally:
            # On parcourt reversed(fixtures) ; f désigne l’élément courant de ce scénario.
            for f in reversed(fixtures):
                # On appelle f.doCleanups sans argument positionnel.
                f.doCleanups()


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
