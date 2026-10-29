# Lecture du fichier — Tests de workflow journal preparation.
#

"""Tests locaux : aucun fichier reel, aucune connexion PostgreSQL, aucun NAS."""

# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On rend disponibles normalize_event depuis workflow_journal_repository, pour les appels de ce
# fichier.
from workflow_journal_repository import normalize_event
# On rend disponibles guard_test_database, journal_schema, PREFIX depuis
# test_workflow_journal_postgres_integration, pour les appels de ce fichier.
from test_workflow_journal_postgres_integration import (
    guard_test_database,
    journal_schema,
    PREFIX,
)


class TestWorkflowJournalPreparation(unittest.TestCase):
    def valid(self):
        # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
        return dict(
            # On fournit l’identifiant stable de l’événement via le paramètre event_id de cet appel.
            event_id=str(uuid4()),
            # On fournit l’identifiant de l’exécution du workflow via le paramètre
            # workflow_execution_id de cet appel.
            workflow_execution_id=str(uuid4()),
            # On fournit le numéro d’ordre de l’événement via le paramètre event_sequence de cet appel.
            event_sequence=1,
            # On fournit la date de l’événement via le paramètre occurred_at de cet appel.
            occurred_at=datetime.now(timezone.utc).isoformat(),
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="integration_test",
            event_type="workflow",
            # On fournit l’étape concernée via le paramètre stage de cet appel.
            stage="workflow",
            # On fournit l’état du traitement via le paramètre status de cet appel.
            status="started",
        )

    def test_valid_event(self):
        # On vérifie que normalize_event(self.valid())['attempt_number'] correspond à 1.
        self.assertEqual(normalize_event(self.valid())["attempt_number"], 1)

    def test_naive_date_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle normalize_event avec dict(self.valid(), occurred_at='2026-10-08T10:00:00').
            normalize_event(dict(self.valid(), occurred_at="2026-10-08T10:00:00"))

    def test_boolean_sequence_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle normalize_event avec dict(self.valid(), event_sequence=True).
            normalize_event(dict(self.valid(), event_sequence=True))

    def test_invalid_uuid_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle normalize_event avec dict(self.valid(), event_id='bad').
            normalize_event(dict(self.valid(), event_id="bad"))

    def test_unknown_mode_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle normalize_event avec dict(self.valid(), trigger_mode='admin').
            normalize_event(dict(self.valid(), trigger_mode="admin"))

    def test_non_object_metrics_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle normalize_event avec dict(self.valid(), metrics_payload=[]).
            normalize_event(dict(self.valid(), metrics_payload=[]))

    def test_log_escape_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle normalize_event avec dict(self.valid(), log_relative_path='logs/../secret').
            normalize_event(dict(self.valid(), log_relative_path="logs/../secret"))

    def test_local_log_allowed(self):
        # On vérifie que normalize_event(dict(self.valid(), log_relative_path='logs/test.log'))['log…
        # correspond à 'logs/test.log'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            normalize_event(dict(self.valid(), log_relative_path="logs/test.log"))[
                "log_relative_path"
            ],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            "logs/test.log",
        )

    def test_main_database_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle guard_test_database avec 'suivi_acquisitions'.
            guard_test_database("suivi_acquisitions")

    def test_injection_name_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle guard_test_database avec PREFIX + 'test;DROP'.
            guard_test_database(PREFIX + "test;DROP")

    def test_generated_test_name_accepted(self):
        # On vérifie que guard_test_database(PREFIX + '20261008_123456_abcdef') correspond à PREFIX +
        # '20261008_123456_abcdef'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            guard_test_database(PREFIX + "20261008_123456_abcdef"),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            PREFIX + "20261008_123456_abcdef",
        )

    def test_ddl_extraction_without_main_guard(self):
        # On utilise ce texte pour s ; il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        s = "DO $$ main guard $$; CREATE TABLE core.workflow_execution_events (id int); CREATE VIEW mart.workflow_execution_current AS SELECT 1; COMMIT;"
        # On attend que journal_schema(s).startswith('CREATE TABLE') soit évalué comme vrai pour ce cas
        # de test.
        self.assertTrue(journal_schema(s).startswith("CREATE TABLE"))
        # On vérifie que 'main guard' ne figure pas dans journal_schema(s).
        self.assertNotIn("main guard", journal_schema(s))

    def test_missing_ddl_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle journal_schema avec 'SELECT 1;'.
            journal_schema("SELECT 1;")

    def test_negative_duration_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle normalize_event avec dict(self.valid(), duration_seconds=-1).
            normalize_event(dict(self.valid(), duration_seconds=-1))


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
