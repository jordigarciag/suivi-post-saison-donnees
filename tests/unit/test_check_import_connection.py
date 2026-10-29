# Lecture du fichier — Tests de check import connection.
#

"""Tests sans serveur : permissions simulees, aucune connexion PostgreSQL."""

# On importe contextlib. Ce module sera utilisé par les opérations de ce fichier.
import contextlib
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles SimpleNamespace depuis types, pour les appels de ce fichier.
from types import SimpleNamespace
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On importe check_import_connection sous le nom checker. Ce module sera utilisé par les opérations de
# ce fichier.
import check_import_connection as checker


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


class Template(str):
    def format(self, identifier):
        # On fournit à l’appelant le résultat du remplacement demandé sur str(self).
        return str(self).replace("{}", identifier)


# On garde dans FAKE_SQL un objet de test regroupant les attributs fournis.
FAKE_SQL = SimpleNamespace(SQL=Template, Identifier=lambda *parts: ".".join(parts))


class FakeConnection:
    def __init__(self):
        # On prépare self.calls comme liste vide ; on la remplira au fil des opérations suivantes.
        self.calls = []
        # On garde dans self.extra_insert un ensemble vide, qui servira à repérer les valeurs déjà
        # rencontrées.
        self.extra_insert = set()
        # On garde dans self.global_privileges un ensemble vide, qui servira à repérer les valeurs déjà
        # rencontrées.
        self.global_privileges = set()
        # On garde dans self.missing_insert un ensemble vide, qui servira à repérer les valeurs déjà
        # rencontrées.
        self.missing_insert = set()
        # On garde dans self.missing_select un ensemble vide, qui servira à repérer les valeurs déjà
        # rencontrées.
        self.missing_select = set()
        # On crée le dictionnaire vide self.extra_updates pour y ranger ensuite les éléments par clé.
        self.extra_updates = {}
        # On rassemble dans self.identity les 3 éléments explicitement indiqués pour ce cas d’essai.
        self.identity = ("suivi_acquisitions", "projet12_importer", "projet12_importer")
        # On initialise self.lock_available à True ; les branches suivantes pourront modifier cet état.
        self.lock_available = True
        # On fixe self.rollbacks à 0 pour cette étape du scénario de test.
        self.rollbacks = 0
        # On assemble ces deux éléments pour construire self.names.
        self.names = list(checker.TABLES) + ["mart.workflow_execution_current"]

    def execute(self, query, args=None):
        # On garde dans text le texte formé en réunissant les éléments avec ' ' comme séparateur.
        text = " ".join(str(query).split())
        # On ajoute (text, args) à la fin de self.calls ; les éléments précédents restent conservés.
        self.calls.append((text, args))
        # Cette branche traite le cas où le texte de travail commence par le texte 'SELECT
        # current_database()'.
        if text.startswith("SELECT current_database()"):
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [self.identity]
        # Cette branche traite le cas où le texte de travail commence par le texte 'SELECT
        # rolcanlogin'.
        elif text.startswith("SELECT rolcanlogin"):
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [
                (
                    "WHERE rolname=current_user" in text,
                    True,
                    False,
                    False,
                    False,
                    False,
                    False,
                )
            ]
        # Cette branche traite le cas où le texte de travail commence par le texte 'SELECT r.rolname'.
        elif text.startswith("SELECT r.rolname"):
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [("projet12_import_writer", False)]
        # Cette branche traite le cas où le texte de travail commence par le texte 'SELECT EXISTS'.
        elif text.startswith("SELECT EXISTS"):
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [(False,)]
        # On vérifie ce cas avant la suite : le texte de travail correspond au texte 'SHOW
        # transaction_read_only'.
        elif text == "SHOW transaction_read_only":
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [("off",)]
        # Cette branche traite le cas où le texte 'has_database_privilege' appartient au texte de
        # travail ou le texte 'has_schema_privilege' appartient au texte de travail.
        elif "has_database_privilege" in text or "has_schema_privilege" in text:
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [(False,)]
        # Cette branche traite le cas où le texte de travail commence par le texte 'SELECT c.oid'.
        elif text.startswith("SELECT c.oid"):
            # On construit rows comme une liste à partir de (i, name, False, False), pour chaque (i,
            # name) de enumerate(self.names).
            rows = [(i, name, False, False) for i, name in enumerate(self.names)]
        # On vérifie ce cas avant la suite : le texte 'has_table_privilege' appartient au texte de
        # travail.
        elif "has_table_privilege" in text:
            # On répartit les éléments de args entre (obj, privilege), dans l’ordre indiqué.
            obj, privilege = args
            # On choisit la valeur de name selon ce test : obj est du type int. Les deux résultats
            # possibles restent définis explicitement ici.
            name = self.names[obj] if isinstance(obj, int) else obj
            # On vérifie ce cas avant la suite : privilege correspond au texte 'SELECT'.
            if privilege == "SELECT":
                # On calcule allowed avec ces conditions liées par and ; Python s’arrête dès qu’une
                # valeur est évaluée comme fausse.
                allowed = name in checker.TABLES and name not in self.missing_select
            # On vérifie ce cas avant la suite : privilege correspond au texte 'INSERT'.
            elif privilege == "INSERT":
                # On calcule allowed avec ces conditions liées par and ; Python s’arrête dès qu’une
                # valeur est évaluée comme fausse.
                allowed = name in checker.TABLES and name not in self.missing_insert
            else:
                # On garde dans allowed le résultat de cette comparaison : (name, privilege) appartient
                # à self.global_privileges.
                allowed = (name, privilege) in self.global_privileges
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [(allowed,)]
        # Cette branche traite le cas où le texte de travail commence par le texte 'SELECT attname'.
        elif text.startswith("SELECT attname"):
            # On sélectionne dans self.names les éléments désignés par args[0] ; name recevra cette
            # sélection.
            name = self.names[args[0]]
            # On réunit ces masques avec | pour construire columns ; les parenthèses gardent les
            # comparaisons regroupées.
            columns = checker.ALLOWED_UPDATE.get(name, set()) | self.extra_updates.get(
                name, set()
            )
            # On construit rows comme une liste à partir de (col, True), pour chaque col de
            # sorted(columns).
            rows = [(col, True) for col in sorted(columns)]
        # On vérifie ce cas avant la suite : le texte 'has_any_column_privilege' appartient au texte
        # de travail.
        elif "has_any_column_privilege" in text:
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [(self.names[args[0]] in self.extra_insert,)]
        # On vérifie ce cas avant la suite : le texte 'pg_try_advisory_xact_lock' appartient au texte
        # de travail.
        elif "pg_try_advisory_xact_lock" in text:
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [(self.lock_available,)]
        # Cette branche traite le cas où le texte de travail commence par le texte 'SELECT COUNT' ou le
        # texte de travail commence par le texte 'SELECT (SELECT COUNT'.
        elif text.startswith("SELECT COUNT") or text.startswith("SELECT (SELECT COUNT"):
            # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
            rows = [(8, 522, 478)]
        # Cette branche traite le cas où le texte de travail commence par le texte 'SELECT 1 FROM' ou
        # le texte 'FOR UPDATE' appartient au texte de travail ou le texte de travail commence par le
        # texte 'SET LOCAL'.
        elif (
            text.startswith("SELECT 1 FROM")
            # Ce cas est aussi retenu si le texte 'FOR UPDATE' appartient au texte de travail.
            or "FOR UPDATE" in text
            # Ce cas est aussi retenu si le texte de travail commence par le texte 'SET LOCAL'.
            or text.startswith("SET LOCAL")
        ):
            # On prépare rows comme liste vide ; on la remplira au fil des opérations suivantes.
            rows = []
        else:
            # On interrompt cette branche avec AssertionError.
            raise AssertionError("Requete non prevue : " + text)
        # On fournit à l’appelant la valeur renvoyée par Result.
        return Result(rows)

    def rollback(self):
        # On ajoute 1 à self.rollbacks et on conserve ce nouvel état pour la suite.
        self.rollbacks += 1

    def __enter__(self):
        # On remet self à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
        return self

    def __exit__(self, *args):
        # On renvoie False comme résultat explicite de cette branche.
        return False


class TestCheckImportConnection(unittest.TestCase):
    def setUp(self):
        # On garde dans self.connection la valeur renvoyée par FakeConnection.
        self.connection = FakeConnection()
        # On garde dans guard la valeur renvoyée par patch.dict.
        guard = patch.dict(sys.modules, {"psycopg": SimpleNamespace(sql=FAKE_SQL)})
        # On appelle guard.start sans argument positionnel.
        guard.start()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(guard.stop)

    def test_journal_is_authorized_and_checked(self):
        # On vérifie que len(checker.TABLES) correspond à 21.
        self.assertEqual(len(checker.TABLES), 21)
        # On vérifie que 'core.workflow_execution_events' figure dans checker.TABLES.
        self.assertIn("core.workflow_execution_events", checker.TABLES)
        # On vérifie que checker.check(self.connection) correspond à (8, 522, 478).
        self.assertEqual(checker.check(self.connection), (8, 522, 478))
        # On parcourt ('SELECT', 'INSERT') ; privilege désigne l’élément courant de ce scénario.
        for privilege in ("SELECT", "INSERT"):
            # On attend que any((args == ('core.workflow_execution_events', privilege) for _, args in
            # self.connection.calls)) soit évalué comme vrai pour ce cas de test.
            self.assertTrue(
                any(
                    args == ("core.workflow_execution_events", privilege)
                    for _, args in self.connection.calls
                )
            )
        # On attend que all((query.startswith(('SELECT', 'SHOW', 'SET LOCAL')) for query, _ in
        # self.connection.calls)) soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            all(
                query.startswith(("SELECT", "SHOW", "SET LOCAL"))
                for query, _ in self.connection.calls
            )
        )

    def test_journal_missing_insert_rejected(self):
        # On ajoute 'core.workflow_execution_events' à self.connection.missing_insert ; comme il s’agit
        # d’un ensemble, une valeur déjà présente n’est pas comptée deux fois.
        self.connection.missing_insert.add("core.workflow_execution_events")
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(
            ValueError, "INSERT absent sur core.workflow_execution_events"
        ):
            # On appelle checker.check avec self.connection.
            checker.check(self.connection)

    def test_journal_missing_select_rejected(self):
        # On ajoute 'core.workflow_execution_events' à self.connection.missing_select ; comme il s’agit
        # d’un ensemble, une valeur déjà présente n’est pas comptée deux fois.
        self.connection.missing_select.add("core.workflow_execution_events")
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(
            ValueError, "SELECT absent sur core.workflow_execution_events"
        ):
            # On appelle checker.check avec self.connection.
            checker.check(self.connection)

    def test_journal_update_or_delete_rejected(self):
        # On parcourt ('UPDATE', 'DELETE', 'TRUNCATE') ; privilege désigne l’élément courant de ce
        # scénario.
        for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(privilege=privilege):
                # On rassemble dans self.connection.global_privileges les 1 éléments explicitement
                # indiqués pour ce cas d’essai.
                self.connection.global_privileges = {
                    ("core.workflow_execution_events", privilege)
                }
                # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit
                # échouer.
                with self.assertRaises(ValueError):
                    # On appelle checker.check avec self.connection.
                    checker.check(self.connection)

    def test_unexpected_insert_rejected(self):
        # On ajoute 'mart.workflow_execution_current' à self.connection.extra_insert ; comme il s’agit
        # d’un ensemble, une valeur déjà présente n’est pas comptée deux fois.
        self.connection.extra_insert.add("mart.workflow_execution_current")
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "Insertion inattendue"):
            # On appelle checker.check avec self.connection.
            checker.check(self.connection)

    def test_unexpected_column_update_rejected(self):
        # On rassemble dans self.connection.extra_updates['core.workflow_execution_events'] les 1
        # éléments explicitement indiqués pour ce cas d’essai.
        self.connection.extra_updates["core.workflow_execution_events"] = {"message"}
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(
            ValueError, "Permissions UPDATE de colonnes inattendues"
        ):
            # On appelle checker.check avec self.connection.
            checker.check(self.connection)

    def test_busy_lock_rejected(self):
        # On initialise self.connection.lock_available à False ; les branches suivantes pourront
        # modifier cet état.
        self.connection.lock_available = False
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "verrou commun"):
            # On appelle checker.check avec self.connection.
            checker.check(self.connection)

    def test_main_rolls_back_on_success_and_failure(self):
        # On regroupe dans cfg ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
        # leur position.
        cfg = {"password": "synthetic-only"}
        # On parcourt (False, True) ; fail désigne l’élément courant de ce scénario.
        for fail in (False, True):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(fail=fail):
                # On garde dans connection la valeur renvoyée par FakeConnection.
                connection = FakeConnection()
                # Cette branche traite le cas où fail est évalué comme vrai.
                if fail:
                    # On rassemble dans connection.identity les 3 éléments explicitement indiqués pour
                    # ce cas d’essai.
                    connection.identity = (
                        "wrong",
                        "projet12_importer",
                        "projet12_importer",
                    )
                # On garde dans module un objet de test regroupant les attributs fournis.
                module = SimpleNamespace(
                    sql=FAKE_SQL, connect=lambda **kwargs: connection
                )
                # On remplace temporairement sys.modules dans ce bloc de test ; le réglage initial sera
                # rétabli à sa sortie.
                with (
                    patch.dict(sys.modules, {"psycopg": module}),
                    patch.object(checker, "database_config", return_value=cfg),
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    # On vérifie que checker.main([]) correspond à 1 if fail else 0.
                    self.assertEqual(checker.main([]), 1 if fail else 0)
                # On vérifie que connection.rollbacks correspond à 1.
                self.assertEqual(connection.rollbacks, 1)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
