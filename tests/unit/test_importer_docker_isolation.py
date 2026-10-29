# Lecture du fichier — Tests de importer docker isolation.
#

"""Tests de garde-fous locaux ; aucune connexion PostgreSQL."""

# On importe contextlib. Ce module sera utilisé par les opérations de ce fichier.
import contextlib
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
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
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On importe run_importer_tests_docker sous le nom runner. Ce module sera utilisé par les opérations de
# ce fichier.
import run_importer_tests_docker as runner


class Result:
    def __init__(self, rows):
        # On gardes lignes sous le nom self.rows ; cette affectation ne copie pas à elle seule un
        # objet mutable.
        self.rows = rows

    def fetchone(self):
        # On remet self.rows[0] à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return self.rows[0]

    def fetchall(self):
        # On remet self.rows à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return self.rows


class Management:
    def __init__(self, identity=None, marker=None):
        # On retient pour self.identity la première valeur évaluée comme vraie dans cette chaîne de
        # replis ; une valeur vide fera donc passer à la suivante.
        self.identity = identity or ("postgres", runner.ADMIN, runner.ADMIN)
        # On choisit la valeur de self.marker selon ce test : marker vaut None. Les deux résultats
        # possibles restent définis explicitement ici.
        self.marker = [(runner.MARKER,)] if marker is None else marker
        # On prépare self.calls comme liste vide ; on la remplira au fil des opérations suivantes.
        self.calls = []

    def execute(self, query):
        # On ajoute query à la fin de self.calls ; les éléments précédents restent conservés.
        self.calls.append(query)
        # On fournit à l’appelant la valeur renvoyée par Result.
        return Result([self.identity] if "current_database" in query else self.marker)


class TestImporterDockerIsolation(unittest.TestCase):
    def setUp(self):
        # On garde dans guard la valeur renvoyée par patch.dict.
        guard = patch.dict(os.environ, {}, clear=True)
        # On appelle guard.start sans argument positionnel.
        guard.start()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(guard.stop)

    def test_explicit_isolation_flag_required(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle runner.make_test_configs sans argument positionnel.
            runner.make_test_configs()

    def test_invalid_isolation_flag_rejected(self):
        # On parcourt ('', '0', 'true') ; value désigne l’élément courant de ce scénario.
        for value in ("", "0", "true"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {"PROJECT12_IMPORT_TEST_ISOLATED": value}),
            ):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle runner.make_test_configs sans argument positionnel.
                    runner.make_test_configs()

    def test_destination_fixed_and_real_credentials_ignored(self):
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
                "PROJECT12_IMPORT_HOST": "projet12-suivi-postgres-1",
                # On associe la clé 'PROJECT12_IMPORT_PASSWORD' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_IMPORT_PASSWORD": "synthetic-not-for-tests",
                # On associe la clé 'PROJECT12_POSTGRES_PASSWORD' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_POSTGRES_PASSWORD": "synthetic-not-for-admin-tests",
            },
        ):
            # On répartit les valeurs renvoyées par runner.make_test_configs entre (admin, importer) ;
            # leur ordre doit correspondre à celui prévu par cet appel.
            admin, importer = runner.make_test_configs()
        # On vérifie que (admin['host'], admin['port'], admin['dbname'], admin['user']) correspond à
        # ('import-test-postgres', 5432, 'postgres', 'projet12_import_test_admin').
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (admin["host"], admin["port"], admin["dbname"], admin["user"]),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ("import-test-postgres", 5432, "postgres", "projet12_import_test_admin"),
        )
        # On vérifie que importer['host'] correspond à 'import-test-postgres'.
        self.assertEqual(importer["host"], "import-test-postgres")
        # On vérifie que importer['user'] correspond à 'projet12_importer'.
        self.assertEqual(importer["user"], "projet12_importer")
        # On vérifie que admin['password'] correspond à runner.ADMIN_PASSWORD.
        self.assertEqual(admin["password"], runner.ADMIN_PASSWORD)
        # On vérifie que importer['password'] correspond à runner.IMPORT_PASSWORD.
        self.assertEqual(importer["password"], runner.IMPORT_PASSWORD)
        # On vérifie que 'dbname' ne figure pas dans importer.
        self.assertNotIn("dbname", importer)

    def test_main_requires_run_before_any_preparation(self):
        # On remplace temporairement runner dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(runner, "build_bundles") as fixtures,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(SystemExit) as exc:
                # On appelle runner.main avec [].
                runner.main([])
        # On vérifie que exc.exception.code correspond à 2.
        self.assertEqual(exc.exception.code, 2)
        # On vérifie que fixtures n’a pas été appelé : le refus doit intervenir avant cette
        # opération.
        fixtures.assert_not_called()

    def test_correct_server_marker_accepted(self):
        # On garde dans connection la valeur renvoyée par Management.
        connection = Management()
        # On appelle runner.verify_management_identity avec connection.
        runner.verify_management_identity(connection)
        # On vérifie que len(connection.calls) correspond à 2.
        self.assertEqual(len(connection.calls), 2)
        # On attend que all((q.startswith('SELECT') for q in connection.calls)) soit évalué comme vrai
        # pour ce cas de test.
        self.assertTrue(all(q.startswith("SELECT") for q in connection.calls))

    def test_metier_admin_identity_rejected_before_marker(self):
        # On garde dans connection la valeur renvoyée par Management.
        connection = Management(
            # On fournit les éléments d’identité du lot via le paramètre identity de cet appel.
            identity=("postgres", "projet12_admin", "projet12_admin")
        )
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle runner.verify_management_identity avec connection.
            runner.verify_management_identity(connection)
        # On vérifie que len(connection.calls) correspond à 1.
        self.assertEqual(len(connection.calls), 1)

    def test_missing_or_wrong_marker_rejected(self):
        # On parcourt ([], [('not-the-test-server',)]) ; marker désigne l’élément courant de ce
        # scénario.
        for marker in ([], [("not-the-test-server",)]):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(marker=marker):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle runner.verify_management_identity avec Management(marker=marker).
                    runner.verify_management_identity(Management(marker=marker))

    def test_expected_schema_sources_accepted_without_env(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as directory:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(directory)
            # On prépare le dossier root / 'sql' avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            (root / "sql").mkdir()
            # On parcourt zip(runner.SQL_FILES, (runner.IMPORT_TABLES[:9], runner.IMPORT_TABLES[9:]… ;
            # (filename, tables) désigne l’élément courant de ce scénario.
            for filename, tables in zip(
                runner.SQL_FILES, (runner.IMPORT_TABLES[:9], runner.IMPORT_TABLES[9:])
            ):
                # On écrit le contenu préparé dans root / 'sql' / filename ; cette opération remplace
                # le contenu du fichier s’il existe déjà.
                (root / "sql" / filename).write_text(
                    "\n".join(
                        "CREATE TABLE IF NOT EXISTS " + t + " (dummy text);"
                        for t in tables
                    ),
                    # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit
                    # pas être décodé selon un réglage implicite du poste.
                    encoding="utf-8",
                )
            # On vérifie que len(runner.load_schema_sources(root)) correspond à 2.
            self.assertEqual(len(runner.load_schema_sources(root)), 2)
            # On attend que (root / '.env').exists() soit évalué comme faux pour ce cas de test.
            self.assertFalse((root / ".env").exists())

    def test_missing_schema_rejected(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as directory:
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle runner.load_schema_sources avec Path(directory).
                runner.load_schema_sources(Path(directory))

    def test_unexpected_or_missing_table_rejected(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as directory:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(directory)
            # On prépare le dossier root / 'sql' avec les règles de création indiquées ; aucun résultat
            # métier n’est encore produit par cette création.
            (root / "sql").mkdir()
            # On parcourt runner.SQL_FILES ; filename désigne l’élément courant de ce scénario.
            for filename in runner.SQL_FILES:
                # On écrit le contenu préparé dans root / 'sql' / filename ; cette opération remplace
                # le contenu du fichier s’il existe déjà.
                (root / "sql" / filename).write_text(
                    "CREATE TABLE IF NOT EXISTS core.unexpected (dummy text);",
                    # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit
                    # pas être décodé selon un réglage implicite du poste.
                    encoding="utf-8",
                )
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle runner.load_schema_sources avec root.
                runner.load_schema_sources(root)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
