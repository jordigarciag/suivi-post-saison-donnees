# Lecture du fichier — Tests de workflow docker preparation.
#

"""Preparation locale du lanceur : aucune connexion a PostgreSQL ou au NAS."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
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
# On importe run_workflow_tests_docker sous le nom runner. Ce module sera utilisé par les opérations de
# ce fichier.
import run_workflow_tests_docker as runner
# On rend disponibles run_workflow, read_events depuis workflow_runtime, pour les appels de ce fichier.
from workflow_runtime import run_workflow, read_events
# On rend disponibles normalize_event depuis workflow_journal_repository, pour les appels de ce
# fichier.
from workflow_journal_repository import normalize_event


class TestWorkflowDockerPreparation(unittest.TestCase):
    def table_source(self):
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "CREATE TABLE core.workflow_execution_events (event_id uuid, duration_seconds numeric, UNIQUE (workflow_execution_id,event_sequence));\nCOMMENT ON TABLE core.workflow_execution_events IS 'test';\nGRANT SELECT ON core.workflow_execution_events TO wrong;"

    def test_only_journal_table_extracted(self):
        # On garde dans ddl la valeur renvoyée par runner.journal_table_source.
        ddl = runner.journal_table_source(self.table_source())
        # On vérifie que 'CREATE TABLE core.workflow_execution_events' figure dans ddl.
        self.assertIn("CREATE TABLE core.workflow_execution_events", ddl)
        # On vérifie que 'GRANT' ne figure pas dans ddl.
        self.assertNotIn("GRANT", ddl)
        # On vérifie que 'COMMENT' ne figure pas dans ddl.
        self.assertNotIn("COMMENT", ddl)

    def test_missing_or_wrong_journal_source_refused(self):
        # On parcourt ('', 'CREATE TABLE other (x int);', self.table_source().replace('duration… ;
        # source désigne l’élément courant de ce scénario.
        for source in (
            "",
            "CREATE TABLE other (x int);",
            self.table_source().replace(
                "duration_seconds numeric", "duration_seconds real"
            ),
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(source=source):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle runner.journal_table_source avec source.
                    runner.journal_table_source(source)

    def test_additional_table_in_extracted_section_refused(self):
        # On garde dans source le résultat du remplacement demandé sur self.table_source().
        source = self.table_source().replace(
            "COMMENT ON TABLE", "CREATE TABLE core.unexpected (x int); COMMENT ON TABLE"
        )
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle runner.journal_table_source avec source.
            runner.journal_table_source(source)

    def test_dangerous_statement_in_extracted_section_refused(self):
        # On parcourt ('GRANT', 'DROP', 'ALTER') ; word désigne l’élément courant de ce scénario.
        for word in ("GRANT", "DROP", "ALTER"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(word=word):
                # On garde dans source le résultat du remplacement demandé sur self.table_source().
                source = self.table_source().replace(
                    "COMMENT ON TABLE", word + " fake; COMMENT ON TABLE"
                )
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle runner.journal_table_source avec source.
                    runner.journal_table_source(source)

    def test_configs_ignore_real_credentials_and_use_fixed_server(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(
            os.environ,
            {
                # On associe la clé 'PROJECT12_IMPORT_TEST_ISOLATED' à cette valeur dans les données de
                # ce scénario.
                "PROJECT12_IMPORT_TEST_ISOLATED": "1",
                # On associe la clé 'PROJECT12_IMPORT_HOST' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_IMPORT_HOST": "real-host",
                # On associe la clé 'PROJECT12_IMPORT_PASSWORD' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_IMPORT_PASSWORD": "not-for-test",
            },
        ):
            # On répartit les valeurs renvoyées par runner.make_test_configs entre (admin, importer) ;
            # leur ordre doit correspondre à celui prévu par cet appel.
            admin, importer = runner.make_test_configs()
        # On vérifie que admin['host'] correspond à 'import-test-postgres'.
        self.assertEqual(admin["host"], "import-test-postgres")
        # On vérifie que importer['host'] correspond à 'import-test-postgres'.
        self.assertEqual(importer["host"], "import-test-postgres")
        # On vérifie que admin['user'] correspond à 'projet12_import_test_admin'.
        self.assertEqual(admin["user"], "projet12_import_test_admin")
        # On vérifie que importer['password'] diffère de 'not-for-test'.
        self.assertNotEqual(importer["password"], "not-for-test")

    def test_exact_isolation_flag_required(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {"PROJECT12_IMPORT_TEST_ISOLATED": "true"}):
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle runner.make_test_configs sans argument positionnel.
                runner.make_test_configs()

    def test_management_marker_required_before_preparation(self):
        # On garde dans c un double de test dont les réponses et les appels pourront être contrôlés.
        c = Mock()
        # On rassemble dans c.execute.return_value.fetchone.return_value les 3 éléments explicitement
        # indiqués pour ce cas d’essai.
        c.execute.return_value.fetchone.return_value = (
            "postgres",
            runner.ADMIN,
            runner.ADMIN,
        )
        # On prépare c.execute.return_value.fetchall.return_value comme liste vide ; on la remplira au
        # fil des opérations suivantes.
        c.execute.return_value.fetchall.return_value = []
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle runner.verify_management_identity avec c.
            runner.verify_management_identity(c)
        # On attend que all(('CREATE' not in call.args[0] for call in c.execute.call_args_list)) soit
        # évalué comme vrai pour ce cas de test.
        self.assertTrue(
            all("CREATE" not in call.args[0] for call in c.execute.call_args_list)
        )

    def test_main_requires_run_before_any_connection(self):
        # On remplace temporairement runner dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(runner, "make_test_configs") as configs, patch("sys.stderr"):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit):
                # On appelle runner.main avec [].
                runner.main([])
        # On vérifie que configs n’a pas été appelé dans ce scénario.
        configs.assert_not_called()

    def test_main_database_name_refused(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle runner.guard_test_database avec 'suivi_acquisitions'.
            runner.guard_test_database("suivi_acquisitions")

    def test_sql_sources_match_expected_21_tables(self):
        # On répartit les valeurs renvoyées par runner.load_sources entre (sources, journal) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        sources, journal = runner.load_sources(ROOT)
        # On vérifie que len(sources) correspond à 2.
        self.assertEqual(len(sources), 2)
        # On vérifie que 'CREATE TABLE core.workflow_execution_events' figure dans journal.
        self.assertIn("CREATE TABLE core.workflow_execution_events", journal)
        # On vérifie que 'CREATE VIEW' ne figure pas dans journal.
        self.assertNotIn("CREATE VIEW", journal)
        # On vérifie que 'projet12_admin' ne figure pas dans journal.
        self.assertNotIn("projet12_admin", journal)

    def test_prepared_synthetic_steps_preserve_excel_and_validate_nas(self):
        # On répartit les valeurs renvoyées par runner.build_bundles entre (fixtures, bundles) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        fixtures, bundles = runner.build_bundles(ROOT)
        # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
        try:
            # On récupère fixtures[0] et on le garde dans first pour la suite.
            first = fixtures[0]
            # On garde dans original les octets lus depuis first.root / first.pub_path, avant toute
            # conversion en texte. Les contrôles de contenu pourront ainsi repartir de cette
            # lecture.
            original = (first.root / first.pub_path).read_bytes()
            # On garde dans roots la valeur renvoyée par runner.prepare_fixture_roots.
            roots = runner.prepare_fixture_roots(fixtures, bundles)
            # On vérifie que (first.root / first.pub_path).read_bytes() correspond à original.
            self.assertEqual((first.root / first.pub_path).read_bytes(), original)
            # On parcourt roots ; (root, relative) désigne l’élément courant de ce scénario.
            for root, relative in roots:
                # On répartit les valeurs renvoyées par runner.prepared_steps entre (steps, eg, ng) ;
                # leur ordre doit correspondre à celui prévu par cet appel.
                steps, eg, ng = runner.prepared_steps(root, relative)

                def check(ctx):
                    # On garde dans bundle la valeur renvoyée par ng.
                    bundle = ng(ctx)
                    # On vérifie que bundle['report']['excel_publication_id'] correspond à
                    # eg(ctx).publication_id.
                    self.assertEqual(
                        # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                        bundle["report"]["excel_publication_id"], eg(ctx).publication_id
                    )

                # On garde dans result le bilan du parcours après l’appel de ses étapes et de son
                # journal.
                result = run_workflow(
                    root,
                    steps + [("validate_bound_bundle", check)],
                    # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                    trigger_mode="integration_test",
                    # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                    scope={"synthetic": True},
                )
                # On vérifie que result['status'] correspond à 'success'.
                self.assertEqual(result["status"], "success")
                # On vérifie que result['pipeline_execution_id'] correspond à bundles[1 if root ==
                # roots[0][0] else 3]['report']['pipeline_execution_id'].
                self.assertEqual(
                    # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                    result["pipeline_execution_id"],
                    # On fournit la valeur attendue ou la collection de comparaison pour cette
                    # assertion.
                    bundles[1 if root == roots[0][0] else 3]["report"][
                        "pipeline_execution_id"
                    ],
                )
        finally:
            # On parcourt reversed(fixtures) ; fixture désigne l’élément courant de ce scénario.
            for fixture in reversed(fixtures):
                # On appelle fixture.doCleanups sans argument positionnel.
                fixture.doCleanups()

    def test_cannot_overwrite_existing_artifacts(self):
        # On répartit les valeurs renvoyées par runner.build_bundles entre (fixtures, bundles) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        fixtures, bundles = runner.build_bundles(ROOT)
        # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
        try:
            # On appelle runner.prepare_fixture_roots avec fixtures.
            runner.prepare_fixture_roots(fixtures, bundles)
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle runner.prepare_fixture_roots avec fixtures.
                runner.prepare_fixture_roots(fixtures, bundles)
        finally:
            # On parcourt reversed(fixtures) ; fixture désigne l’élément courant de ce scénario.
            for fixture in reversed(fixtures):
                # On appelle fixture.doCleanups sans argument positionnel.
                fixture.doCleanups()

    def test_local_journal_archived_without_changes(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as temp:
            # On assemble les morceaux du chemin root avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            root = Path(temp) / "workspace"
            # On prépare le dossier root avec les règles de création indiquées ; aucun résultat métier
            # n’est encore produit par cette création.
            root.mkdir()
            # On garde dans result le bilan du parcours après l’appel de ses étapes et de son journal.
            result = run_workflow(
                root,
                [("synthetic", lambda ctx: None)],
                # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                trigger_mode="integration_test",
                # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                scope={},
            )
            # On assemble les morceaux du chemin source avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            source = root / result["journal_relative_path"]
            # On garde dans before les octets lus depuis source, avant toute conversion en texte.
            # Les contrôles de contenu pourront ainsi repartir de cette lecture.
            before = source.read_bytes()
            # On garde dans target la valeur renvoyée par runner.archive_result.
            target = runner.archive_result(root, result, Path(temp) / "retained")
            # On vérifie que target.read_bytes() correspond à before.
            self.assertEqual(target.read_bytes(), before)
            # On attend que (target.parent / 'result.json').is_file() soit évalué comme vrai pour ce
            # cas de test.
            self.assertTrue((target.parent / "result.json").is_file())

    def test_sql_journal_compares_all_normalized_events(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as temp:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(temp)
            # On garde dans result le bilan du parcours après l’appel de ses étapes et de son journal.
            result = run_workflow(
                root,
                [("synthetic", lambda ctx: None)],
                # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
                trigger_mode="integration_test",
                # On fournit le périmètre du traitement via le paramètre scope de cet appel.
                scope={},
            )
            # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            path = root / result["journal_relative_path"]
            # On garde dans events les événements du journal local après validation de leur ordre et de
            # leur identité.
            events = read_events(path)
            # On construit rows comme une liste à partir de tuple((normalize_event(e)[k] for k in
            # runner.COLUMNS)), pour chaque e de events.
            rows = [
                tuple(normalize_event(e)[k] for k in runner.COLUMNS) for e in events
            ]
            # On garde dans c un double de test dont les réponses et les appels pourront être
            # contrôlés.
            c = Mock()
            # On gardes lignes sous le nom c.execute.return_value.fetchall.return_value ; cette
            # affectation ne copie pas à elle seule un objet mutable.
            c.execute.return_value.fetchall.return_value = rows
            # On appelle runner.verify_journal avec c.
            runner.verify_journal(c, result, path)
            # On garde dans c.execute.return_value.fetchall.return_value la portion des lignes
            # sélectionnée par :-1 ; les bornes de fin sont exclues.
            c.execute.return_value.fetchall.return_value = rows[:-1]
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle runner.verify_journal avec c.
                runner.verify_journal(c, result, path)
