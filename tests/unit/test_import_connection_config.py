# Lecture du fichier — Tests de import connection config.
#

# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles SimpleNamespace depuis types, pour les appels de ce fichier.
from types import SimpleNamespace
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Mock, patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import Mock, patch

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On rend disponibles database_config, verify_import_identity depuis import_connection_config, pour les
# appels de ce fichier.
from import_connection_config import database_config, verify_import_identity


class TestImportConnectionConfig(unittest.TestCase):
    def setUp(self):
        # On garde dans guard la valeur renvoyée par patch.dict.
        guard = patch.dict(os.environ, {}, clear=True)
        # On appelle guard.start sans argument positionnel.
        guard.start()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(guard.stop)

    def config(self, values):
        # On garde dans fn un double de test dont les réponses et les appels pourront être contrôlés.
        fn = Mock(return_value=values)
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(sys.modules, {"dotenv": SimpleNamespace(dotenv_values=fn)}):
            # On garde dans result les paramètres du compte PostgreSQL prévus par ce module.
            result = database_config(Path("/project"))
        # On vérifie que ce double a reçu un seul appel avec exactement les arguments indiqués ; une
        # valeur correcte obtenue par le mauvais appel ne suffirait pas.
        fn.assert_called_once_with(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            Path("/project/.env"), encoding="utf-8-sig", interpolate=False
        )
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    def test_dedicated_account_and_local_connection(self):
        # On garde dans cfg la valeur renvoyée par self.config.
        cfg = self.config(
            {
                # On associe la clé 'PROJECT12_IMPORT_USER' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_IMPORT_USER": "projet12_importer",
                # On associe la clé 'PROJECT12_IMPORT_PASSWORD' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_IMPORT_PASSWORD": "synthetic-only",
            }
        )
        # On vérifie que cfg['user'] correspond à 'projet12_importer'.
        self.assertEqual(cfg["user"], "projet12_importer")
        # On vérifie que (cfg['host'], cfg['port'], cfg['dbname']) correspond à ('127.0.0.1', 5433,
        # 'suivi_acquisitions').
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (cfg["host"], cfg["port"], cfg["dbname"]),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ("127.0.0.1", 5433, "suivi_acquisitions"),
        )

    def test_no_admin_fallback(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.config avec {'PROJECT12_POSTGRES_PASSWORD': 'synthetic-admin-only'}.
            self.config({"PROJECT12_POSTGRES_PASSWORD": "synthetic-admin-only"})

    def test_admin_account_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.config avec {'PROJECT12_IMPORT_USER': 'projet12_admin',
            # 'PROJECT12_IMPORT_PASSWORD': 'synthetic-only'}.
            self.config(
                {
                    # On associe la clé 'PROJECT12_IMPORT_USER' à cette valeur dans les données de ce
                    # scénario.
                    "PROJECT12_IMPORT_USER": "projet12_admin",
                    # On associe la clé 'PROJECT12_IMPORT_PASSWORD' à cette valeur dans les données de
                    # ce scénario.
                    "PROJECT12_IMPORT_PASSWORD": "synthetic-only",
                }
            )

    def test_missing_password_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.config avec {'PROJECT12_IMPORT_USER': 'projet12_importer'}.
            self.config({"PROJECT12_IMPORT_USER": "projet12_importer"})

    def test_empty_password_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.config avec {'PROJECT12_IMPORT_USER': 'projet12_importer',
            # 'PROJECT12_IMPORT_PASSWORD': ''}.
            self.config(
                {
                    # On associe la clé 'PROJECT12_IMPORT_USER' à cette valeur dans les données de ce
                    # scénario.
                    "PROJECT12_IMPORT_USER": "projet12_importer",
                    # On associe la clé 'PROJECT12_IMPORT_PASSWORD' à cette valeur dans les données de
                    # ce scénario.
                    "PROJECT12_IMPORT_PASSWORD": "",
                }
            )

    def test_valid_identity(self):
        # On appelle verify_import_identity avec ('suivi_acquisitions', 'projet12_importer',
        # 'projet12_importer').
        verify_import_identity(
            ("suivi_acquisitions", "projet12_importer", "projet12_importer")
        )

    def test_unexpected_session_user_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle verify_import_identity avec ('suivi_acquisitions', 'projet12_importer',
            # 'projet12_admin').
            verify_import_identity(
                ("suivi_acquisitions", "projet12_importer", "projet12_admin")
            )

    def test_wrong_database_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle verify_import_identity avec ('other', 'projet12_importer',
            # 'projet12_importer').
            verify_import_identity(("other", "projet12_importer", "projet12_importer"))


class TestEnvironmentImportConnection(unittest.TestCase):
    def setUp(self):
        # On garde dans guard la valeur renvoyée par patch.dict.
        guard = patch.dict(
            os.environ,
            {
                # On associe la clé 'PROJECT12_IMPORT_CONNECTION_MODE' à cette valeur dans les données
                # de ce scénario.
                "PROJECT12_IMPORT_CONNECTION_MODE": "environment",
                # On associe la clé 'PROJECT12_IMPORT_HOST' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_IMPORT_HOST": "business-postgres",
                # On associe la clé 'PROJECT12_IMPORT_PORT' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_IMPORT_PORT": "5432",
                # On associe la clé 'PROJECT12_IMPORT_USER' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_IMPORT_USER": "projet12_importer",
                # On associe la clé 'PROJECT12_IMPORT_PASSWORD' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_IMPORT_PASSWORD": "synthetic-only",
            },
            # On indique si les anciennes entrées doivent être retirées pendant ce remplacement
            # temporaire de dictionnaire.
            clear=True,
        )
        # On appelle guard.start sans argument positionnel.
        guard.start()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(guard.stop)

    def test_environment_does_not_read_dotenv(self):
        # On garde dans fn un double de test dont les réponses et les appels pourront être contrôlés.
        fn = Mock(side_effect=AssertionError(".env must not be read"))
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(sys.modules, {"dotenv": SimpleNamespace(dotenv_values=fn)}):
            # On garde dans cfg les paramètres du compte PostgreSQL prévus par ce module.
            cfg = database_config(Path("/absent"))
        # On vérifie que fn n’a pas été appelé dans ce scénario.
        fn.assert_not_called()
        # On vérifie que (cfg['host'], cfg['port'], cfg['dbname'], cfg['user']) correspond à
        # ('business-postgres', 5432, 'suivi_acquisitions', 'projet12_importer').
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (cfg["host"], cfg["port"], cfg["dbname"], cfg["user"]),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ("business-postgres", 5432, "suivi_acquisitions", "projet12_importer"),
        )
        # On vérifie que cfg['connect_timeout'] correspond à 5.
        self.assertEqual(cfg["connect_timeout"], 5)

    def test_invalid_modes_rejected(self):
        # On parcourt ('', 'docker', 'Environment') ; mode désigne l’élément courant de ce scénario.
        for mode in ("", "docker", "Environment"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with (
                self.subTest(mode=mode),
                patch.dict(os.environ, {"PROJECT12_IMPORT_CONNECTION_MODE": mode}),
            ):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle database_config avec Path('/project').
                    database_config(Path("/project"))

    def test_missing_host_rejected(self):
        # On retire os.environ['PROJECT12_IMPORT_HOST'] de son emplacement ; la suite ne doit plus
        # s’appuyer sur cette entrée.
        del os.environ["PROJECT12_IMPORT_HOST"]
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle database_config avec Path('/project').
            database_config(Path("/project"))

    def test_invalid_hosts_rejected(self):
        # On parcourt ('', ' business-postgres', 'postgres://host', 'host:5432', 'host/path') ; host
        # désigne l’élément courant de ce scénario.
        for host in (
            "",
            " business-postgres",
            "postgres://host",
            "host:5432",
            "host/path",
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with (
                self.subTest(host=host),
                patch.dict(os.environ, {"PROJECT12_IMPORT_HOST": host}),
            ):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle database_config avec Path('/project').
                    database_config(Path("/project"))

    def test_missing_port_rejected(self):
        # On retire os.environ['PROJECT12_IMPORT_PORT'] de son emplacement ; la suite ne doit plus
        # s’appuyer sur cette entrée.
        del os.environ["PROJECT12_IMPORT_PORT"]
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle database_config avec Path('/project').
            database_config(Path("/project"))

    def test_invalid_ports_rejected(self):
        # On parcourt ('', '0', '65536', '-1', '5432.0', ' 5432', 'abc', '999999999999') ; port désigne
        # l’élément courant de ce scénario.
        for port in ("", "0", "65536", "-1", "5432.0", " 5432", "abc", "999999999999"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with (
                self.subTest(port=port),
                patch.dict(os.environ, {"PROJECT12_IMPORT_PORT": port}),
            ):
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle database_config avec Path('/project').
                    database_config(Path("/project"))

    def test_admin_rejected(self):
        # On utilise ce texte pour os.environ['PROJECT12_IMPORT_USER'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        os.environ["PROJECT12_IMPORT_USER"] = "projet12_admin"
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle database_config avec Path('/project').
            database_config(Path("/project"))

    def test_no_admin_password_fallback(self):
        # On retire os.environ['PROJECT12_IMPORT_PASSWORD'] de son emplacement ; la suite ne doit plus
        # s’appuyer sur cette entrée.
        del os.environ["PROJECT12_IMPORT_PASSWORD"]
        # On utilise ce texte pour os.environ['PROJECT12_POSTGRES_PASSWORD'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        os.environ["PROJECT12_POSTGRES_PASSWORD"] = "synthetic-admin-only"
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle database_config avec Path('/project').
            database_config(Path("/project"))

    def test_missing_user_rejected(self):
        # On retire os.environ['PROJECT12_IMPORT_USER'] de son emplacement ; la suite ne doit plus
        # s’appuyer sur cette entrée.
        del os.environ["PROJECT12_IMPORT_USER"]
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle database_config avec Path('/project').
            database_config(Path("/project"))

    def test_empty_password_rejected_without_disclosure(self):
        # On commence os.environ['PROJECT12_IMPORT_PASSWORD'] avec un texte vide, à compléter
        # uniquement si la suite apporte une information.
        os.environ["PROJECT12_IMPORT_PASSWORD"] = ""
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle database_config avec Path('/project').
            database_config(Path("/project"))

    def test_password_preserved_without_interpolation(self):
        # On utilise ce texte pour os.environ['PROJECT12_IMPORT_PASSWORD'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        os.environ["PROJECT12_IMPORT_PASSWORD"] = "synthetic-${VAR}-with spaces"
        # On vérifie que database_config(Path('/project'))['password'] correspond à
        # 'synthetic-${VAR}-with spaces'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            database_config(Path("/project"))["password"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            "synthetic-${VAR}-with spaces",
        )

    def test_database_cannot_be_redirected_by_environment(self):
        # On utilise ce texte pour os.environ['PROJECT12_IMPORT_DATABASE'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        os.environ["PROJECT12_IMPORT_DATABASE"] = "other"
        # On vérifie que database_config(Path('/project'))['dbname'] correspond à 'suivi_acquisitions'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            database_config(Path("/project"))["dbname"], "suivi_acquisitions"
        )


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
