# Lecture du fichier — Tests de excel postgres import.
#

"""Tests unitaires du flux d'import avec depot en memoire, pas un serveur PostgreSQL.

Les tests SQL reels et les comptages seront verifies lors du premier import sur le PC.
"""

# On rend disponibles Counter depuis collections, pour les appels de ce fichier.
from collections import Counter
# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On sépare les copies d’objets, notamment pour comparer un état avant et après une opération.
import copy
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On importe importlib.util. Ce module sera utilisé par les opérations de ce fichier.
import importlib.util
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest

# On assemble les morceaux du chemin SCRIPTS avec l’opérateur / de pathlib ; aucun fichier n’est créé
# par cette construction.
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(SCRIPTS))
# On importe import_excel_publication sous le nom importer. Ce module sera utilisé par les opérations
# de ce fichier.
import import_excel_publication as importer
# On importe test_excel_publication_check sous le nom fixtures. Ce module sera utilisé par les
# opérations de ce fichier.
import test_excel_publication_check as fixtures


class MemoryRepository:
    # Ce dépôt en mémoire permet d’observer les écritures sans serveur PostgreSQL.
    def __init__(self):
        # On crée le dictionnaire vide self.records pour y ranger ensuite les éléments par clé.
        self.records = {}
        # On initialise self.current à None : aucune valeur n’a encore été retenue ici.
        self.current = None
        # On garde dans self.inserted les effectifs de chaque valeur rencontrée.
        self.inserted = Counter()
        # On garde dans self.reused les effectifs de chaque valeur rencontrée.
        self.reused = Counter()
        # On initialise self.fail_table à None : aucune valeur n’a encore été retenue ici.
        self.fail_table = None
        # On initialise self.fail_activation à False ; les branches suivantes pourront modifier cet
        # état.
        self.fail_activation = False
        # On garde dans self.now la valeur renvoyée par datetime pour 2026.
        self.now = datetime(2026, 10, 7, tzinfo=timezone.utc)

    @contextmanager
    def transaction(self):
        # On rend before indépendant de (self.records, self.current, self.inserted, self.reused), y
        # compris pour les listes et dictionnaires imbriqués ; les modifications du scénario ne
        # doivent pas contaminer l’état de départ.
        before = copy.deepcopy((self.records, self.current, self.inserted, self.reused))
        # On tente ce bloc et on traite séparément les erreurs prévues : BaseException.
        try:
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield self
        except BaseException:
            # On répartit les éléments de before entre (self.records, self.current, self.inserted,
            # self.reused), dans l’ordre indiqué.
            self.records, self.current, self.inserted, self.reused = before
            # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni en
            # fabriquer une autre.
            raise

    # On conserve la donnée historique ou on vérifie qu’une donnée déjà présente est identique.
    def put_immutable(self, table, record):
        # On vérifie ce cas avant la suite : table correspond à self.fail_table.
        if table == self.fail_table:
            # On interrompt cette branche avec RuntimeError : 'Injected failure'.
            raise RuntimeError("Injected failure")
        # On sélectionne dans importer.TABLE_KEYS les éléments désignés par table ; keys recevra cette
        # sélection.
        keys = importer.TABLE_KEYS[table]
        # On garde dans identity une séquence non modifiable construite à partir de (record[k] for k in
        # keys).
        identity = tuple(record[k] for k in keys)
        # On garde dans target la valeur renvoyée par self.records.setdefault.
        target = self.records.setdefault(table, {})
        # On vérifie ce cas avant la suite : les éléments d’identité du lot appartient à la
        # destination.
        if identity in target:
            # On appelle importer.require avec target[identity] == record.
            importer.require(
                target[identity] == record,
                "Contenu different pour un identifiant deja charge",
            )
            # On ajoute 1 à self.reused[table] et on conserve ce nouvel état pour la suite.
            self.reused[table] += 1
            # On renvoie False comme résultat explicite de cette branche.
            return False
        # On rend target[identity] indépendant de record, y compris pour les listes et dictionnaires
        # imbriqués ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        target[identity] = copy.deepcopy(record)
        # On ajoute 1 à self.inserted[table] et on conserve ce nouvel état pour la suite.
        self.inserted[table] += 1
        # On renvoie True comme résultat explicite de cette branche.
        return True

    def put_rows(self, table, filters, identity_columns, records, *, new_parent):
        # On vérifie ce cas avant la suite : table correspond à self.fail_table.
        if table == self.fail_table:
            # On interrompt cette branche avec RuntimeError : 'Injected failure'.
            raise RuntimeError("Injected failure")
        # On garde dans target la valeur renvoyée par self.records.setdefault.
        target = self.records.setdefault(table, {})
        # On indexe existing par k ; chaque clé sera associée à v. Une même clé ne peut garder qu’une
        # valeur.
        existing = {
            k: v
            for k, v in target.items()
            if all(v.get(key) == value for key, value in filters.items())
        }
        # On indexe expected par tuple((row[k] for k in identity_columns)) ; chaque clé sera associée à
        # row. Une même clé ne peut garder qu’une valeur.
        expected = {tuple(row[k] for k in identity_columns): row for row in records}
        # On prévoit le cas où new_parent est évalué comme faux, par exemple une valeur vide selon son
        # type.
        if not new_parent:
            # On appelle importer.require avec existing == expected.
            importer.require(
                existing == expected, "Lignes historiques modifiees ou incompletes"
            )
            # On ajoute len(records) à self.reused[table] et on conserve ce nouvel état pour la suite.
            self.reused[table] += len(records)
            # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont
            # pas exécutées.
            return
        # On appelle importer.require avec not existing.
        importer.require(not existing, "Lignes inattendues")
        # On complète target avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        target.update(copy.deepcopy(expected))
        # On ajoute len(records) à self.inserted[table] et on conserve ce nouvel état pour la suite.
        self.inserted[table] += len(records)

    def verify_members(self, table, filters, expected_records):
        # On construit existing comme une liste à partir de v, pour chaque v de self.records.get(table,
        # {}).values() en ne gardant que les éléments qui passent le filtre.
        existing = [
            v
            for v in self.records.get(table, {}).values()
            if all(v.get(k) == val for k, val in filters.items())
        ]
        # On sélectionne dans importer.TABLE_KEYS les éléments désignés par table ; keys recevra cette
        # sélection.
        keys = importer.TABLE_KEYS[table]
        # On construit actual comme un ensemble sans doublons à partir de tuple((v[k] for k in keys)),
        # pour chaque v de existing.
        actual = {tuple(v[k] for k in keys) for v in existing}
        # On construit expected comme un ensemble sans doublons à partir de tuple((v[k] for k in
        # keys)), pour chaque v de expected_records.
        expected = {tuple(v[k] for k in keys) for v in expected_records}
        # On appelle importer.require avec actual == expected.
        importer.require(actual == expected, "Composition historique differente")

    # On gère le lien vers le résultat à consulter actuellement, sans assimiler ce lien à tout
    # l’historique.
    def activate(self, publication_id, published_at):
        # Cette branche traite le cas où le test self.fail_activation est satisfait.
        if self.fail_activation:
            # On interrompt cette branche avec RuntimeError : 'Injected activation failure'.
            raise RuntimeError("Injected activation failure")
        # Cette branche traite le cas où le test self.current est satisfait.
        if self.current:
            # On vérifie ce cas avant la suite : l’identifiant de la publication Excel dans
            # self.current correspond à l’identifiant de la publication Excel.
            if self.current["publication_id"] == publication_id:
                # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
                return "unchanged"
            # On appelle importer.require avec published_at > self.current['published_at'].
            importer.require(
                published_at > self.current["published_at"],
                "Refus publication plus ancienne",
            )
        # On regroupe dans self.current ces champs nommés ; on pourra les retrouver par leur clé plutôt
        # que par leur position.
        self.current = {
            # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
            "publication_id": publication_id,
            # On renseigne la date de publication sous la clé 'published_at'.
            "published_at": published_at,
            # On associe la clé 'activated_at' à cette valeur dans les données de ce scénario.
            "activated_at": self.now,
        }
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "activated"


class TestExcelPostgresImport(unittest.TestCase):
    def setUp(self):
        # On garde dans self.fixture la valeur renvoyée par fixtures.TestExcelPublicationCheck pour
        # 'test_valid_publication_left_right_not_double_l….
        self.fixture = fixtures.TestExcelPublicationCheck(
            "test_valid_publication_left_right_not_double_logical_acquisition"
        )
        # On initialise les ressources du scénario self.fixture avec sa méthode setUp.
        self.fixture.setUp()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.fixture.doCleanups)
        # On garde dans self.bundle le lot préparé et contrôlé par le module appelé.
        self.bundle = importer.prepare_bundle(self.fixture.root)
        # On garde dans self.repo la valeur renvoyée par MemoryRepository.
        self.repo = MemoryRepository()

    def test_first_import_loads_rows_and_current_pointer(self):
        # On garde dans result le bilan du chargement du lot via le repository fourni.
        result = importer.import_bundle(self.bundle, self.repo)
        # On vérifie que result['activation'] correspond à 'activated'.
        self.assertEqual(result["activation"], "activated")
        # On vérifie que len(self.repo.records['core.excel_versions']) correspond à 1.
        self.assertEqual(len(self.repo.records["core.excel_versions"]), 1)
        # On vérifie que len(self.repo.records['staging.excel_version_rows']) correspond à 2.
        self.assertEqual(len(self.repo.records["staging.excel_version_rows"]), 2)
        # On vérifie que len(self.repo.records['staging.excel_publication_rows']) correspond à 2.
        self.assertEqual(len(self.repo.records["staging.excel_publication_rows"]), 2)
        # On vérifie que self.repo.current['publication_id'] correspond à self.fixture.publication_id.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.repo.current["publication_id"], self.fixture.publication_id
        )

    def test_second_identical_import_reuses_and_preserves_activation_date(self):
        # On appelle importer.import_bundle avec self.bundle.
        importer.import_bundle(self.bundle, self.repo)
        # On rend before indépendant de (self.repo.records, self.repo.current), y compris pour les
        # listes et dictionnaires imbriqués ; les modifications du scénario ne doivent pas
        # contaminer l’état de départ.
        before = copy.deepcopy((self.repo.records, self.repo.current))
        # On appelle self.repo.inserted.clear sans argument positionnel.
        self.repo.inserted.clear()
        # On appelle self.repo.reused.clear sans argument positionnel.
        self.repo.reused.clear()
        # On garde dans self.repo.now la valeur renvoyée par datetime pour 2027.
        self.repo.now = datetime(2027, 1, 1, tzinfo=timezone.utc)
        # On garde dans result le bilan du chargement du lot via le repository fourni.
        result = importer.import_bundle(self.bundle, self.repo)
        # On vérifie que (self.repo.records, self.repo.current) correspond à before.
        self.assertEqual((self.repo.records, self.repo.current), before)
        # On vérifie que sum(result['inserted'].values()) correspond à 0.
        self.assertEqual(sum(result["inserted"].values()), 0)
        # On vérifie que result['activation'] correspond à 'unchanged'.
        self.assertEqual(result["activation"], "unchanged")

    def test_failure_mid_import_rolls_back_every_record(self):
        # On utilise ce texte pour self.repo.fail_table ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        self.repo.fail_table = "staging.excel_version_rows"
        # On attend RuntimeError avec un message correspondant au motif indiqué dans ce bloc ; si
        # aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(RuntimeError, "Injected"):
            # On appelle importer.import_bundle avec self.bundle.
            importer.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.records correspond à {}.
        self.assertEqual(self.repo.records, {})
        # On attend None pour self.repo.current : aucune valeur n’est confirmée dans ce cas.
        self.assertIsNone(self.repo.current)

    def test_activation_failure_rolls_back_every_record(self):
        # On initialise self.repo.fail_activation à True ; les branches suivantes pourront modifier cet
        # état.
        self.repo.fail_activation = True
        # On attend RuntimeError avec un message correspondant au motif indiqué dans ce bloc ; si
        # aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(RuntimeError, "activation"):
            # On appelle importer.import_bundle avec self.bundle.
            importer.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.records correspond à {}.
        self.assertEqual(self.repo.records, {})
        # On attend None pour self.repo.current : aucune valeur n’est confirmée dans ce cas.
        self.assertIsNone(self.repo.current)

    def test_divergent_existing_metadata_rejected_not_overwritten(self):
        # On appelle importer.import_bundle avec self.bundle.
        importer.import_bundle(self.bundle, self.repo)
        # On garde dans key le prochain élément de iter(self.repo.records['core.excel_versions']).
        key = next(iter(self.repo.records["core.excel_versions"]))
        # On utilise ce texte pour self.repo.records['core.excel_versions'][key]['source_filename'] ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.repo.records["core.excel_versions"][key]["source_filename"] = (
            "tampered.xlsx"
        )
        # On rend before indépendant de self.repo.records, y compris pour les listes et
        # dictionnaires imbriqués ; les modifications du scénario ne doivent pas contaminer l’état
        # de départ.
        before = copy.deepcopy(self.repo.records)
        # On attend importer.ValidationError avec un message correspondant au motif indiqué dans ce
        # bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(importer.ValidationError, "Contenu different"):
            # On appelle importer.import_bundle avec self.bundle.
            importer.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.records correspond à before.
        self.assertEqual(self.repo.records, before)

    def test_modified_existing_payload_rejected_not_repaired(self):
        # On appelle importer.import_bundle avec self.bundle.
        importer.import_bundle(self.bundle, self.repo)
        # On garde dans key le prochain élément de
        # iter(self.repo.records['staging.excel_publication_rows']).
        key = next(iter(self.repo.records["staging.excel_publication_rows"]))
        # On utilise ce texte pour self.repo.records['staging.excel_publication_rows'][key]['payloa… ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.repo.records["staging.excel_publication_rows"][key]["payload"][
            "Commentaires"
        ] = "tampered"
        # On rend before indépendant de self.repo.records, y compris pour les listes et
        # dictionnaires imbriqués ; les modifications du scénario ne doivent pas contaminer l’état
        # de départ.
        before = copy.deepcopy(self.repo.records)
        # On attend importer.ValidationError avec un message correspondant au motif indiqué dans ce
        # bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(importer.ValidationError, "historiques"):
            # On appelle importer.import_bundle avec self.bundle.
            importer.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.records correspond à before.
        self.assertEqual(self.repo.records, before)

    def test_missing_existing_rows_rejected_not_repaired(self):
        # On appelle importer.import_bundle avec self.bundle.
        importer.import_bundle(self.bundle, self.repo)
        # On retire de self.repo.records['staging.excel_version_rows'] l’élément demandé.
        self.repo.records["staging.excel_version_rows"].pop(
            next(iter(self.repo.records["staging.excel_version_rows"]))
        )
        # On rend before indépendant de self.repo.records, y compris pour les listes et
        # dictionnaires imbriqués ; les modifications du scénario ne doivent pas contaminer l’état
        # de départ.
        before = copy.deepcopy(self.repo.records)
        # On attend importer.ValidationError avec un message correspondant au motif indiqué dans ce
        # bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(importer.ValidationError, "historiques"):
            # On appelle importer.import_bundle avec self.bundle.
            importer.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.records correspond à before.
        self.assertEqual(self.repo.records, before)

    def test_missing_existing_member_rejected_not_repaired(self):
        # On appelle importer.import_bundle avec self.bundle.
        importer.import_bundle(self.bundle, self.repo)
        # On appelle self.repo.records['core.excel_publication_versions'].clear sans argument
        # positionnel.
        self.repo.records["core.excel_publication_versions"].clear()
        # On rend before indépendant de self.repo.records, y compris pour les listes et
        # dictionnaires imbriqués ; les modifications du scénario ne doivent pas contaminer l’état
        # de départ.
        before = copy.deepcopy(self.repo.records)
        # On attend importer.ValidationError avec un message correspondant au motif indiqué dans ce
        # bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(importer.ValidationError, "incomplete"):
            # On appelle importer.import_bundle avec self.bundle.
            importer.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.records correspond à before.
        self.assertEqual(self.repo.records, before)

    def test_extra_existing_publication_member_rejected(self):
        # On appelle importer.import_bundle avec self.bundle.
        importer.import_bundle(self.bundle, self.repo)
        # On récupère self.repo.records['core.excel_publication_versions'] et on le garde dans table
        # pour la suite.
        table = self.repo.records["core.excel_publication_versions"]
        # On regroupe dans table[self.fixture.publication_id, 'unexpected'] ces champs nommés ; on
        # pourra les retrouver par leur clé plutôt que par leur position.
        table[(self.fixture.publication_id, "unexpected")] = {
            # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
            "publication_id": self.fixture.publication_id,
            # On renseigne la clé du domaine sous la clé 'vineyard_key'.
            "vineyard_key": "unexpected",
            # On renseigne l’identifiant de version sous la clé 'version_id'.
            "version_id": "other",
        }
        # On attend importer.ValidationError avec un message correspondant au motif indiqué dans ce
        # bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(importer.ValidationError, "Composition historique"):
            # On appelle importer.import_bundle avec self.bundle.
            importer.import_bundle(self.bundle, self.repo)

    def test_file_change_after_preparation_blocks_import(self):
        # On écrit self.fixture.source_path dans self.fixture ; le mode d’ouverture du flux détermine
        # s’il s’agit d’un ajout ou d’un remplacement.
        self.fixture.write(self.fixture.source_path, b"changed after validation")
        # On attend importer.ValidationError avec un message correspondant au motif indiqué dans ce
        # bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(importer.ValidationError, "modifie pendant"):
            # On appelle importer.import_bundle avec self.bundle.
            importer.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.records correspond à {}.
        self.assertEqual(self.repo.records, {})

    def test_older_publication_cannot_replace_newer_current(self):
        # On regroupe dans self.repo.current ces champs nommés ; on pourra les retrouver par leur clé
        # plutôt que par leur position.
        self.repo.current = {
            # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
            "publication_id": "newer",
            # On renseigne la date de publication sous la clé 'published_at'.
            "published_at": datetime(2026, 10, 8, tzinfo=timezone.utc),
            # On associe la clé 'activated_at' à cette valeur dans les données de ce scénario.
            "activated_at": self.repo.now,
        }
        # On rend before indépendant de self.repo.current, y compris pour les listes et
        # dictionnaires imbriqués ; les modifications du scénario ne doivent pas contaminer l’état
        # de départ.
        before = copy.deepcopy(self.repo.current)
        # On attend importer.ValidationError avec un message correspondant au motif indiqué dans ce
        # bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(importer.ValidationError, "plus ancienne"):
            # On appelle importer.import_bundle avec self.bundle.
            importer.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.current correspond à before.
        self.assertEqual(self.repo.current, before)
        # On vérifie que self.repo.records correspond à {}.
        self.assertEqual(self.repo.records, {})

    def test_payload_preserves_text_and_converts_only_empty_cells(self):
        # On vérifie que importer.payload({'a': '', 'b': 'False', 'c': 'N/A', 'd': 'éà'}) correspond à
        # {'a': None, 'b': 'False', 'c': 'N/A', 'd': 'éà'}.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            importer.payload({"a": "", "b": "False", "c": "N/A", "d": "éà"}),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            {"a": None, "b": "False", "c": "N/A", "d": "éà"},
        )


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
