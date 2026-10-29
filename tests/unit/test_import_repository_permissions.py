# Lecture du fichier — Tests de import repository permissions.
#

"""Tests des requetes emises, avec SQL/connexion simules : pas une integration PostgreSQL."""

# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles ModuleType depuis types, pour les appels de ce fichier.
from types import ModuleType
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On importe import_excel_publication sous le nom excel. Ce module sera utilisé par les opérations de
# ce fichier.
import import_excel_publication as excel
# On importe load_nas_reconciliation sous le nom nas. Ce module sera utilisé par les opérations de ce
# fichier.
import load_nas_reconciliation as nas


class Statement(str):
    def format(self, *args, **kwargs):
        # On fournit à l’appelant la valeur renvoyée par Statement.
        return Statement(super().format(*args, **kwargs))

    def join(self, items):
        # On fournit à l’appelant la valeur renvoyée par Statement.
        return Statement(super().join(items))


# On garde dans sql la valeur renvoyée par ModuleType pour 'psycopg.sql'.
sql = ModuleType("psycopg.sql")
# On garde Statement sous le nom sql.SQL ; cette affectation ne copie pas à elle seule un objet
# mutable.
sql.SQL = Statement
# On prépare pour sql.Identifier une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
# appelée, pas lors de cette affectation.
sql.Identifier = lambda *parts: Statement(".".join(parts))
# On prépare pour sql.Placeholder une fonction courte ; elle ne sera exécutée que lorsqu’elle sera
# appelée, pas lors de cette affectation.
sql.Placeholder = lambda: Statement("%s")
# On garde dans psycopg la valeur renvoyée par ModuleType pour 'psycopg'.
psycopg = ModuleType("psycopg")
# On prépare psycopg.__path__ comme liste vide ; on la remplira au fil des opérations suivantes.
psycopg.__path__ = []
# On garde sql sous le nom psycopg.sql ; cette affectation ne copie pas à elle seule un objet mutable.
psycopg.sql = sql
# On garde dans types la valeur renvoyée par ModuleType pour 'psycopg.types'.
types = ModuleType("psycopg.types")
# On prépare types.__path__ comme liste vide ; on la remplira au fil des opérations suivantes.
types.__path__ = []
# On garde dans json la valeur renvoyée par ModuleType pour 'psycopg.types.json'.
json = ModuleType("psycopg.types.json")
# On prépare pour json.Jsonb une fonction courte ; elle ne sera exécutée que lorsqu’elle sera appelée,
# pas lors de cette affectation.
json.Jsonb = lambda value: value
# On regroupe dans MODULES ces champs nommés ; on pourra les retrouver par leur clé plutôt que par leur
# position.
MODULES = {
    # On associe la clé 'psycopg' à cette valeur dans les données de ce scénario.
    "psycopg": psycopg,
    # On associe la clé 'psycopg.sql' à cette valeur dans les données de ce scénario.
    "psycopg.sql": sql,
    # On associe la clé 'psycopg.types' à cette valeur dans les données de ce scénario.
    "psycopg.types": types,
    # On associe la clé 'psycopg.types.json' à cette valeur dans les données de ce scénario.
    "psycopg.types.json": json,
}


class Result:
    def __init__(self, rows):
        # On gardes lignes sous le nom self.rows ; cette affectation ne copie pas à elle seule un
        # objet mutable.
        self.rows = rows

    def fetchone(self):
        # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour
        # ce cas.
        return self.rows[0] if self.rows else None

    def fetchall(self):
        # On remet self.rows à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return self.rows


class Connection:
    def __init__(self, rows=()):
        # On garde dans self.rows une liste matérialisée à partir des lignes.
        self.rows = list(rows)
        # On prépare self.queries comme liste vide ; on la remplira au fil des opérations suivantes.
        self.queries = []

    def execute(self, query, parameters=None):
        # On ajoute str(query) à la fin de self.queries ; les éléments précédents restent conservés.
        self.queries.append(str(query))
        # On vérifie ce cas avant la suite : le texte 'to_regclass' appartient à str(query).
        if "to_regclass" in str(query):
            # On fournit à l’appelant la valeur renvoyée par Result.
            return Result([("existing",)])
        # On fournit à l’appelant la valeur renvoyée par Result.
        return Result(self.rows)

    @contextmanager
    def transaction(self):
        # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après ce
        # point si son itération continue.
        yield


class TestImportRepositoryPermissions(unittest.TestCase):
    def setUp(self):
        # On garde dans self.modules la valeur renvoyée par patch.dict.
        self.modules = patch.dict(sys.modules, MODULES)
        # On appelle self.modules.start sans argument positionnel.
        self.modules.start()

    def tearDown(self):
        # On appelle self.modules.stop sans argument positionnel.
        self.modules.stop()

    def test_excel_existing_history_read_without_for_update(self):
        # On regroupe dans record ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        record = {
            # On renseigne la clé du domaine sous la clé 'vineyard_key'.
            "vineyard_key": "synthetic",
            # On renseigne le nom du domaine sous la clé 'vineyard_name'.
            "vineyard_name": "Synthetic",
            # On renseigne le nom technique de rangement sous la clé 'storage_key'.
            "storage_key": "v_0000000000",
        }
        # On garde dans c la valeur renvoyée par Connection.
        c = Connection([tuple(record.values())])
        # On garde dans repo la valeur renvoyée par excel.PostgresRepository.
        repo = excel.PostgresRepository(c)
        # On attend que repo.put_immutable('core.vineyards', record) soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse(repo.put_immutable("core.vineyards", record))
        # On vérifie que 'FOR UPDATE' ne figure pas dans c.queries[0].
        self.assertNotIn("FOR UPDATE", c.queries[0])
        # On attend que any((q.startswith(('INSERT', 'UPDATE')) for q in c.queries)) soit évalué comme
        # faux pour ce cas de test.
        self.assertFalse(any(q.startswith(("INSERT", "UPDATE")) for q in c.queries))

    def test_excel_new_history_insert_without_update(self):
        # On garde dans c la valeur renvoyée par Connection.
        c = Connection()
        # On garde dans repo la valeur renvoyée par excel.PostgresRepository.
        repo = excel.PostgresRepository(c)
        # On attend que repo.put_immutable('core.vineyards', {'vineyard_key': 'synthetic',
        # 'vineyard_name': 'Synthetic', 'storage_key… soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            repo.put_immutable(
                "core.vineyards",
                {
                    # On renseigne la clé du domaine sous la clé 'vineyard_key'.
                    "vineyard_key": "synthetic",
                    # On renseigne le nom du domaine sous la clé 'vineyard_name'.
                    "vineyard_name": "Synthetic",
                    # On renseigne le nom technique de rangement sous la clé 'storage_key'.
                    "storage_key": "v_0000000000",
                },
            )
        )
        # On attend que c.queries[-1].startswith('INSERT') soit évalué comme vrai pour ce cas de test.
        self.assertTrue(c.queries[-1].startswith("INSERT"))
        # On attend que any((q.startswith('UPDATE') or 'FOR UPDATE' in q for q in c.queries)) soit
        # évalué comme faux pour ce cas de test.
        self.assertFalse(
            any(q.startswith("UPDATE") or "FOR UPDATE" in q for q in c.queries)
        )

    def test_nas_history_read_without_for_update(self):
        # On garde dans c la valeur renvoyée par Connection.
        c = Connection()
        # On garde dans repo la valeur renvoyée par nas.PostgresRepository.
        repo = nas.PostgresRepository(c)
        # On appelle repo.read avec 'core.pipeline_runs'.
        repo.read(
            "core.pipeline_runs",
            ("pipeline_execution_id",),
            {"pipeline_execution_id": "synthetic"},
        )
        # On vérifie que 'FOR UPDATE' ne figure pas dans c.queries[-1].
        self.assertNotIn("FOR UPDATE", c.queries[-1])

    def test_nas_pointer_keeps_for_update(self):
        # On garde dans c la valeur renvoyée par Connection.
        c = Connection()
        # On garde dans repo la valeur renvoyée par nas.PostgresRepository.
        repo = nas.PostgresRepository(c)
        # On appelle repo.read avec nas.POINTER.
        repo.read(nas.POINTER, ("vineyard_key",), {"vineyard_key": "synthetic"})
        # On vérifie que 'FOR UPDATE' figure dans c.queries[-1].
        self.assertIn("FOR UPDATE", c.queries[-1])

    def test_excel_identical_activation_keeps_pointer_lock_without_update(self):
        # On garde dans c la valeur renvoyée par Connection.
        c = Connection([("synthetic-publication", None)])
        # On garde dans repo la valeur renvoyée par excel.PostgresRepository.
        repo = excel.PostgresRepository(c)
        # On vérifie que repo.activate('synthetic-publication', None) correspond à 'unchanged'.
        self.assertEqual(repo.activate("synthetic-publication", None), "unchanged")
        # On vérifie que 'FOR UPDATE OF c' figure dans c.queries[0].
        self.assertIn("FOR UPDATE OF c", c.queries[0])
        # On attend que any((q.startswith('UPDATE') for q in c.queries)) soit évalué comme faux pour ce
        # cas de test.
        self.assertFalse(any(q.startswith("UPDATE") for q in c.queries))

    def test_both_importers_keep_common_advisory_lock(self):
        # On parcourt (excel, nas) ; importer désigne l’élément courant de ce scénario.
        for importer in (excel, nas):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(importer=importer.__name__):
                # On garde dans c la valeur renvoyée par Connection.
                c = Connection()
                # On garde dans repo la valeur renvoyée par importer.PostgresRepository.
                repo = importer.PostgresRepository(c)
                # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne
                # couvre pas tout le workflow.
                with repo.transaction():
                    # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
                    pass
                # On attend que any(('pg_advisory_xact_lock' in q for q in c.queries)) soit évalué
                # comme vrai pour ce cas de test.
                self.assertTrue(any("pg_advisory_xact_lock" in q for q in c.queries))


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
