# Lecture du fichier — Tests de dashboard connection.
#

"""Tests de configuration et de refus : aucun PostgreSQL ni secret reel."""

# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles SimpleNamespace depuis types, pour les appels de ce fichier.
from types import SimpleNamespace
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Mock, patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import Mock, patch

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On importe check_dashboard_connection sous le nom checker. Ce module sera utilisé par les opérations
# de ce fichier.
import check_dashboard_connection as checker


class TestDashboardConnection(unittest.TestCase):
    def config(self, values):
        # On garde dans fn un double de test dont les réponses et les appels pourront être contrôlés.
        fn = Mock(return_value=values)
        # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(sys.modules, {"dotenv": SimpleNamespace(dotenv_values=fn)}):
            # On garde dans result la valeur renvoyée par checker.database_config.
            result = checker.database_config(Path("/project"))
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

    def test_nineteen_unique_views(self):
        # On vérifie que len(checker.VIEWS) correspond à 19.
        self.assertEqual(len(checker.VIEWS), 19)
        # On vérifie que len(set(checker.VIEWS)) correspond à 19.
        self.assertEqual(len(set(checker.VIEWS)), 19)
        # On vérifie que 'reconciliation_field_provenance_current' figure dans checker.VIEWS.
        self.assertIn("reconciliation_field_provenance_current", checker.VIEWS)
        # On vérifie que 'reconciliation_association_history' figure dans checker.VIEWS.
        self.assertIn("reconciliation_association_history", checker.VIEWS)
        # On vérifie que 'reconciliation_proof_summary_current' figure dans checker.VIEWS.
        self.assertIn("reconciliation_proof_summary_current", checker.VIEWS)
        # On vérifie que 'workflow_event_history' figure dans checker.VIEWS.
        self.assertIn("workflow_event_history", checker.VIEWS)
        # On vérifie que 'workflow_execution_current' figure dans checker.VIEWS.
        self.assertIn("workflow_execution_current", checker.VIEWS)

    def test_dedicated_config(self):
        # On garde dans c la valeur renvoyée par self.config.
        c = self.config(
            {
                # On associe la clé 'PROJECT12_DASHBOARD_USER' à cette valeur dans les données de ce
                # scénario.
                "PROJECT12_DASHBOARD_USER": "projet12_dashboard",
                # On associe la clé 'PROJECT12_DASHBOARD_PASSWORD' à cette valeur dans les données de
                # ce scénario.
                "PROJECT12_DASHBOARD_PASSWORD": "synthetic",
            }
        )
        # On vérifie que (c['host'], c['port'], c['dbname'], c['user']) correspond à ('127.0.0.1',
        # 5433, 'suivi_acquisitions', 'projet12_dashboard').
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (c["host"], c["port"], c["dbname"], c["user"]),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ("127.0.0.1", 5433, "suivi_acquisitions", "projet12_dashboard"),
        )

    def test_no_admin_fallback(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.config avec {'PROJECT12_POSTGRES_PASSWORD': 'synthetic'}.
            self.config({"PROJECT12_POSTGRES_PASSWORD": "synthetic"})

    def test_wrong_account_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.config avec {'PROJECT12_DASHBOARD_USER': 'projet12_importer',
            # 'PROJECT12_DASHBOARD_PASSWORD': 'synthe….
            self.config(
                {
                    # On associe la clé 'PROJECT12_DASHBOARD_USER' à cette valeur dans les données de
                    # ce scénario.
                    "PROJECT12_DASHBOARD_USER": "projet12_importer",
                    # On associe la clé 'PROJECT12_DASHBOARD_PASSWORD' à cette valeur dans les données
                    # de ce scénario.
                    "PROJECT12_DASHBOARD_PASSWORD": "synthetic",
                }
            )

    def test_missing_password_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.config avec {'PROJECT12_DASHBOARD_USER': 'projet12_dashboard'}.
            self.config({"PROJECT12_DASHBOARD_USER": "projet12_dashboard"})

    def test_valid_identity(self):
        # On appelle checker.validate_identity avec ('suivi_acquisitions', 'projet12_dashboard',
        # 'projet12_dashboard').
        checker.validate_identity(
            ("suivi_acquisitions", "projet12_dashboard", "projet12_dashboard")
        )

    def test_session_user_mismatch_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle checker.validate_identity avec ('suivi_acquisitions', 'projet12_dashboard',
            # 'projet12_admin').
            checker.validate_identity(
                ("suivi_acquisitions", "projet12_dashboard", "projet12_admin")
            )

    def test_wrong_database_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle checker.validate_identity avec ('postgres', 'projet12_dashboard',
            # 'projet12_dashboard').
            checker.validate_identity(
                ("postgres", "projet12_dashboard", "projet12_dashboard")
            )

    def test_read_only_view_rights_accepted(self):
        # On appelle checker.validate_rights avec [('mart', 'synthetic_view', True, False, False,
        # False, False, False, False)].
        checker.validate_rights(
            [
                (
                    "mart",
                    "synthetic_view",
                    True,
                    False,
                    False,
                    False,
                    False,
                    False,
                    False,
                )
            ],
            [],
        )

    def test_table_write_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle checker.validate_rights avec [('mart', 'synthetic_view', True, True, False,
            # False, False, False, False)].
            checker.validate_rights(
                [
                    (
                        "mart",
                        "synthetic_view",
                        True,
                        True,
                        False,
                        False,
                        False,
                        False,
                        False,
                    )
                ],
                [],
            )

    def test_column_update_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle checker.validate_rights avec [('core', 'synthetic_table', False, False, True,
            # False, False, False, False)].
            checker.validate_rights(
                [
                    (
                        "core",
                        "synthetic_table",
                        False,
                        False,
                        True,
                        False,
                        False,
                        False,
                        False,
                    )
                ],
                [],
            )

    def test_direct_source_table_read_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle checker.validate_rights avec [('staging', 'synthetic_table', True, False,
            # False, False, False, False, False)].
            checker.validate_rights(
                [
                    (
                        "staging",
                        "synthetic_table",
                        True,
                        False,
                        False,
                        False,
                        False,
                        False,
                        False,
                    )
                ],
                [],
            )

    def test_direct_source_column_read_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle checker.validate_rights avec [].
            checker.validate_rights([], [("core",)])

    def test_excel_message_does_not_claim_nas_unloaded(self):
        # On garde dans source le texte lu depuis Path(__file__).resolve().parents[2] /
        # 'scripts/import_excel_publ… avec l’encodage indiqué.
        source = (
            Path(__file__).resolve().parents[2] / "scripts/import_excel_publication.py"
        # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
        # décodé selon un réglage implicite du poste.
        ).read_text(encoding="utf-8")
        # On vérifie que 'les donnees NAS et le dashboard ne sont pas encore charges' ne figure pas
        # dans source.
        self.assertNotIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "les donnees NAS et le dashboard ne sont pas encore charges", source
        )
        # On vérifie que 'aucun chargement NAS ni recalcul des rapprochements' figure dans source.
        self.assertIn("aucun chargement NAS ni recalcul des rapprochements", source)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
