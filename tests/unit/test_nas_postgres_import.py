# Lecture du fichier — Tests de nas postgres import.
#

"""Tests d'orchestration avec depot en memoire : aucune connexion PostgreSQL.
L'integration PostgreSQL reelle reste a executer dans le projet Windows.
"""

# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On sépare les copies d’objets, notamment pour comparer un état avant et après une opération.
import copy
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
# On importe load_nas_reconciliation sous le nom loader. Ce module sera utilisé par les opérations de
# ce fichier.
import load_nas_reconciliation as loader
# On importe test_nas_reconciliation_check sous le nom fixtures. Ce module sera utilisé par les
# opérations de ce fichier.
import test_nas_reconciliation_check as fixtures
# On rend disponibles ValidationError depuis load_excel_publication, pour les appels de ce fichier.
from load_excel_publication import ValidationError


class MemoryRepository:
    # Ce dépôt en mémoire permet d’observer les écritures sans serveur PostgreSQL.
    def __init__(self, bundle):
        # On indexe self.data par table ; chaque clé sera associée à []. Une même clé ne peut garder
        # qu’une valeur.
        self.data = {table: [] for table in loader.COLUMNS}
        # On prépare self.data[loader.POINTER] comme liste vide ; on la remplira au fil des opérations
        # suivantes.
        self.data[loader.POINTER] = []
        # On reprend les métadonnées de la publication dans bundle ; cet accès suppose que la clé a
        # été produite ou vérifiée auparavant.
        pub = bundle["publication"]
        # On rassemble dans self.data['core.excel_publications'] les 1 éléments explicitement indiqués
        # pour ce cas d’essai.
        self.data["core.excel_publications"] = [
            dict(
                # On fournit l’identifiant de la publication Excel via le paramètre publication_id de
                # cet appel.
                publication_id=pub["publication_id"],
                # On fournit l’empreinte du tableau Excel regroupé via le paramètre reference_sha256 de
                # cet appel.
                reference_sha256=pub["reference"]["sha256"],
                # On fournit le nombre de lignes du tableau regroupé via le paramètre reference_rows de
                # cet appel.
                reference_rows=pub["reference"]["rows"],
                # On fournit le chemin du tableau Excel regroupé via le paramètre reference_path de cet
                # appel.
                reference_path=pub["reference"]["path"],
                # On fournit le chemin du manifeste via le paramètre manifest_path de cet appel.
                manifest_path=bundle["pub_path"],
                # On fournit l’empreinte du manifeste via le paramètre manifest_sha256 de cet appel.
                manifest_sha256=loader.sha256(bundle["files"].read(bundle["pub_path"])),
                # On fournit le contenu du manifeste via le paramètre manifest_payload de cet appel.
                manifest_payload=copy.deepcopy(pub),
            )
        ]
        # On construit self.data['staging.excel_publication_rows'] comme une liste à partir de
        # dict(publication_id=pub['publication_id'], row_ordinal=i, payloa…, pour chaque (i, r) de
        # enumerate(bundle['reference'], 1).
        self.data["staging.excel_publication_rows"] = [
            dict(
                # On fournit l’identifiant de la publication Excel via le paramètre publication_id de
                # cet appel.
                publication_id=pub["publication_id"],
                # On fournit la position de la ligne dans le lot via le paramètre row_ordinal de cet
                # appel.
                row_ordinal=i,
                # On fournit le contenu détaillé via le paramètre payload de cet appel.
                payload=loader.payload(r),
            )
            for i, r in enumerate(bundle["reference"], 1)
        ]
        # On construit self.data['core.excel_publication_versions'] comme une liste à partir de
        # dict(publication_id=pub['publication_id'], vineyard_key=k, versi…, pour chaque (k, e) de
        # pub['versions'].items().
        self.data["core.excel_publication_versions"] = [
            dict(
                # On fournit l’identifiant de la publication Excel via le paramètre publication_id de
                # cet appel.
                publication_id=pub["publication_id"],
                # On fournit la clé du domaine via le paramètre vineyard_key de cet appel.
                vineyard_key=k,
                # On fournit l’identifiant de version via le paramètre version_id de cet appel.
                version_id=e["version_id"],
            )
            for k, e in pub["versions"].items()
        ]
        # On construit self.data['core.excel_versions'] comme une liste à partir de
        # dict(vineyard_key=k, version_id=e['version_id'], ingested_at=loa…, pour chaque (k, e) de
        # pub['versions'].items().
        self.data["core.excel_versions"] = [
            dict(
                # On fournit la clé du domaine via le paramètre vineyard_key de cet appel.
                vineyard_key=k,
                # On fournit l’identifiant de version via le paramètre version_id de cet appel.
                version_id=e["version_id"],
                # On fournit la date d’ingestion via le paramètre ingested_at de cet appel.
                ingested_at=loader.timestamp(e["ingested_at"]),
                # On fournit l’empreinte du fichier source via le paramètre source_sha256 de cet appel.
                source_sha256=e["source_sha256"],
                # On fournit le nom du fichier source via le paramètre source_filename de cet appel.
                source_filename=e["source_filename"],
            )
            for k, e in pub["versions"].items()
        ]
        # On initialise self.fail_table à None : aucune valeur n’a encore été retenue ici.
        self.fail_table = None
        # On initialise self.fail_pointer à False ; les branches suivantes pourront modifier cet état.
        self.fail_pointer = False
        # On initialise self.mutate à None : aucune valeur n’a encore été retenue ici.
        self.mutate = None
        # On fixe self.tick à 0 pour cette étape du scénario de test.
        self.tick = 0

    @contextmanager
    def transaction(self):
        # On garde dans before une copie indépendante, y compris pour les objets imbriqués.
        before = copy.deepcopy(self.data)
        # On garde self.tick sous le nom tick ; cette affectation ne copie pas à elle seule un objet
        # mutable.
        tick = self.tick
        # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
        try:
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield
        except Exception:
            # On garde l’état relevé avant l’opération sous le nom self.data ; cette affectation ne
            # copie pas à elle seule un objet mutable.
            self.data = before
            # On garde tick sous le nom self.tick ; cette affectation ne copie pas à elle seule un
            # objet mutable.
            self.tick = tick
            # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni en
            # fabriquer une autre.
            raise

    def read(self, table, columns, filters):
        # On remet [{c: r[c] for c in columns} for r in self.data.get(table, []) if all((r[k… à
        # l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
        return [
            {c: r[c] for c in columns}
            for r in self.data.get(table, [])
            if all(r[k] == v for k, v in filters.items())
        ]

    def insert(self, table, columns, rows):
        # On vérifie ce cas avant la suite : table correspond à self.fail_table.
        if table == self.fail_table:
            # On interrompt cette branche avec RuntimeError : 'Erreur simulee insertion'.
            raise RuntimeError("Erreur simulee insertion")
        # On ajoute les éléments de copy.deepcopy(rows) à self.data[table] ; on n’ajoute pas la
        # collection comme un seul élément imbriqué.
        self.data[table].extend(copy.deepcopy(rows))
        # On vérifie ce cas avant la suite : table correspond à loader.POINTER.
        if table == loader.POINTER:
            # Cette branche traite le cas où le test self.fail_pointer est satisfait.
            if self.fail_pointer:
                # On interrompt cette branche avec RuntimeError : 'Erreur simulee activation'.
                raise RuntimeError("Erreur simulee activation")
            # On ajoute 1 à self.tick et on conserve ce nouvel état pour la suite.
            self.tick += 1
            # On garde self.tick sous le nom self.data[table][-1]['activated_in_database_at'] ; cette
            # affectation ne copie pas à elle seule un objet mutable.
            self.data[table][-1]["activated_in_database_at"] = self.tick
            # Cette branche traite le cas où le test self.mutate est satisfait.
            if self.mutate:
                # On appelle self.mutate sans argument positionnel.
                self.mutate()

    # On change le lien courant selon le contrat de ce dépôt ; les anciennes observations restent
    # distinctes.
    def replace_pointer(self, record):
        # Cette branche traite le cas où le test self.fail_pointer est satisfait.
        if self.fail_pointer:
            # On interrompt cette branche avec RuntimeError : 'Erreur simulee activation'.
            raise RuntimeError("Erreur simulee activation")
        # On ajoute 1 à self.tick et on conserve ce nouvel état pour la suite.
        self.tick += 1
        # On garde dans row le prochain élément de (r for r in self.data[loader.POINTER] if
        # r['vineyard_key'] == record['vin….
        row = next(
            r
            for r in self.data[loader.POINTER]
            if r["vineyard_key"] == record["vineyard_key"]
        )
        # On complète row avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle valeur
        # fournie.
        row.update(record, activated_in_database_at=self.tick)


class TestNasPostgresImport(unittest.TestCase):
    def setUp(self):
        # On garde dans self.fixture la valeur renvoyée par fixtures.TestNasReconciliationCheck pour
        # 'test_no_files_written'.
        self.fixture = fixtures.TestNasReconciliationCheck("test_no_files_written")
        # On initialise les ressources du scénario self.fixture avec sa méthode setUp.
        self.fixture.setUp()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.fixture.doCleanups)
        # On garde dans self.bundle le lot préparé et contrôlé par le module appelé.
        self.bundle = loader.prepare_bundle(
            self.fixture.root, self.fixture.manifest_path
        )
        # On garde dans self.repo la valeur renvoyée par MemoryRepository.
        self.repo = MemoryRepository(self.bundle)

    # Au premier chargement, on attend les observations et le lien vers leur bilan actif.
    def test_first_import_loads_snapshots_and_pointer(self):
        # On garde dans result le bilan du chargement du lot via le repository fourni.
        result = loader.import_bundle(self.bundle, self.repo)
        # On vérifie que result['inserted']['staging.nas_acquisition_observations'] correspond à 3.
        self.assertEqual(result["inserted"]["staging.nas_acquisition_observations"], 3)
        # On vérifie que result['inserted']['staging.nas_association_observations'] correspond à 2.
        self.assertEqual(result["inserted"]["staging.nas_association_observations"], 2)
        # On vérifie que result['inserted']['staging.nas_passage_observations'] correspond à 1.
        self.assertEqual(result["inserted"]["staging.nas_passage_observations"], 1)
        # On vérifie que result['inserted']['core.pipeline_artifacts'] correspond à 6.
        self.assertEqual(result["inserted"]["core.pipeline_artifacts"], 6)
        # On vérifie que result['activations'] correspond à {'alpha': 'active'}.
        self.assertEqual(result["activations"], {"alpha": "active"})
        # On vérifie que len(self.repo.data[loader.POINTER]) correspond à 1.
        self.assertEqual(len(self.repo.data[loader.POINTER]), 1)

    # Un deuxième import identique ne doit pas faire passer les mêmes observations pour un bilan
    # plus récent.
    def test_second_identical_import_preserves_activation_date(self):
        # On appelle loader.import_bundle avec self.bundle.
        loader.import_bundle(self.bundle, self.repo)
        # On rend before indépendant de self.repo.data, y compris pour les listes et dictionnaires
        # imbriqués ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        before = copy.deepcopy(self.repo.data)
        # On garde dans result le bilan du chargement du lot via le repository fourni.
        result = loader.import_bundle(self.bundle, self.repo)
        # On attend que result['inserted'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["inserted"])
        # On vérifie que result['reused']['core.pipeline_artifacts'] correspond à 6.
        self.assertEqual(result["reused"]["core.pipeline_artifacts"], 6)
        # On vérifie que result['activations'] correspond à {'alpha': 'inchange'}.
        self.assertEqual(result["activations"], {"alpha": "inchange"})
        # On vérifie que self.repo.data correspond à before.
        self.assertEqual(self.repo.data, before)

    # On interrompt un chargement en cours. Le dépôt de test doit retrouver son état d’avant la
    # transaction.
    def test_failure_mid_import_rolls_back_every_record(self):
        # On rend before indépendant de self.repo.data, y compris pour les listes et dictionnaires
        # imbriqués ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        before = copy.deepcopy(self.repo.data)
        # On utilise ce texte pour self.repo.fail_table ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        self.repo.fail_table = "staging.reconciliation_passage_rows"
        # On attend RuntimeError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(RuntimeError):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.data correspond à before.
        self.assertEqual(self.repo.data, before)

    # On fait échouer la mise à jour du bilan actif : les autres écritures de cette transaction ne
    # doivent pas rester seules.
    def test_activation_failure_rolls_back_every_record(self):
        # On rend before indépendant de self.repo.data, y compris pour les listes et dictionnaires
        # imbriqués ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        before = copy.deepcopy(self.repo.data)
        # On initialise self.repo.fail_pointer à True ; les branches suivantes pourront modifier cet
        # état.
        self.repo.fail_pointer = True
        # On attend RuntimeError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(RuntimeError):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.data correspond à before.
        self.assertEqual(self.repo.data, before)

    # On retire une ligne d’un historique déjà chargé. Le réimport doit signaler la différence, pas
    # la réparer discrètement.
    def test_existing_missing_rows_rejected_not_repaired(self):
        # On appelle loader.import_bundle avec self.bundle.
        loader.import_bundle(self.bundle, self.repo)
        # On retire de self.repo.data['staging.nas_acquisition_observations'] l’élément demandé.
        self.repo.data["staging.nas_acquisition_observations"].pop()
        # On rend before indépendant de self.repo.data, y compris pour les listes et dictionnaires
        # imbriqués ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        before = copy.deepcopy(self.repo.data)
        # On attend ValidationError avec un message correspondant au motif indiqué dans ce bloc ; si
        # aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValidationError, "Historique different"):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.data correspond à before.
        self.assertEqual(self.repo.data, before)

    # On altère une donnée historique pour vérifier que le réimport ne l’écrase pas silencieusement.
    def test_existing_changed_payload_rejected_not_overwritten(self):
        # On appelle loader.import_bundle avec self.bundle.
        loader.import_bundle(self.bundle, self.repo)
        # On utilise ce texte pour self.repo.data['staging.reconciliation_acquisition_rows'][0]['pa… ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.repo.data["staging.reconciliation_acquisition_rows"][0]["payload"][
            "vitiparcel_created"
        ] = "False"
        # On rend before indépendant de self.repo.data, y compris pour les listes et dictionnaires
        # imbriqués ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        before = copy.deepcopy(self.repo.data)
        # On attend Exception dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(Exception):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.data correspond à before.
        self.assertEqual(self.repo.data, before)

    def test_existing_extra_artifact_rejected(self):
        # On appelle loader.import_bundle avec self.bundle.
        loader.import_bundle(self.bundle, self.repo)
        # On rend extra indépendant de self.repo.data['core.pipeline_artifacts'][0], y compris pour
        # les listes et dictionnaires imbriqués ; les modifications du scénario ne doivent pas
        # contaminer l’état de départ.
        extra = copy.deepcopy(self.repo.data["core.pipeline_artifacts"][0])
        # On utilise ce texte pour extra['vineyard_key'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        extra["vineyard_key"] = "unexpected"
        # On ajoute extra à la fin de self.repo.data['core.pipeline_artifacts'] ; les éléments
        # précédents restent conservés.
        self.repo.data["core.pipeline_artifacts"].append(extra)
        # On attend Exception dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(Exception):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)

    def test_missing_excel_publication_blocks_before_insert(self):
        # On prépare self.repo.data['core.excel_publications'] comme liste vide ; on la remplira au fil
        # des opérations suivantes.
        self.repo.data["core.excel_publications"] = []
        # On attend Exception dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(Exception):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)
        # On attend que self.repo.data['core.pipeline_runs'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(self.repo.data["core.pipeline_runs"])

    def test_modified_excel_reference_payload_blocks(self):
        # On utilise ce texte pour self.repo.data['staging.excel_publication_rows'][0]['payload']['… ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.repo.data["staging.excel_publication_rows"][0]["payload"]["Périmètre"] = (
            "Test"
        )
        # On attend Exception dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(Exception):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)
        # On attend que self.repo.data['core.pipeline_runs'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(self.repo.data["core.pipeline_runs"])

    def test_file_change_after_preparation_blocks(self):
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.fixture.root / self.fixture.output_paths[("nas", "acquisitions")]
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_bytes(path.read_bytes() + b"\n")
        # On attend Exception dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(Exception):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)
        # On attend que self.repo.data['core.pipeline_runs'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(self.repo.data["core.pipeline_runs"])

    def test_file_change_during_transaction_rolls_back(self):
        # On rend before indépendant de self.repo.data, y compris pour les listes et dictionnaires
        # imbriqués ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        before = copy.deepcopy(self.repo.data)
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.fixture.root / self.fixture.output_paths[("nas", "acquisitions")]
        # On prépare pour self.repo.mutate une fonction courte ; elle ne sera exécutée que lorsqu’elle
        # sera appelée, pas lors de cette affectation.
        self.repo.mutate = lambda: path.write_bytes(path.read_bytes() + b"\n")
        # On attend Exception dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(Exception):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.data correspond à before.
        self.assertEqual(self.repo.data, before)

    def test_nonverifiable_false_preserved_not_reclassified(self):
        # On appelle loader.import_bundle avec self.bundle.
        loader.import_bundle(self.bundle, self.repo)
        # On récupère self.repo.data['staging.nas_acquisition_observations'][2] et on le garde dans row
        # pour la suite.
        row = self.repo.data["staging.nas_acquisition_observations"][2]
        # On vérifie l’identité de row['passage_outputs_verifiable'] avec False, et pas seulement une
        # égalité de valeur.
        self.assertIs(row["passage_outputs_verifiable"], False)
        # On vérifie l’identité de row['vitiparcel_created'] avec False, et pas seulement une égalité
        # de valeur.
        self.assertIs(row["vitiparcel_created"], False)
        # On vérifie que row['payload']['vitiparcel_created'] correspond à 'False'.
        self.assertEqual(row["payload"]["vitiparcel_created"], "False")
        # On récupère self.repo.data['staging.reconciliation_acquisition_rows'][2] et on le garde dans
        # result pour la suite.
        result = self.repo.data["staging.reconciliation_acquisition_rows"][2]
        # On vérifie l’identité de result['acquisition_review_candidate'] avec True, et pas seulement
        # une égalité de valeur.
        self.assertIs(result["acquisition_review_candidate"], True)
        # On vérifie que result['payload']['processing_business_category'] correspond à 'Écart à
        # vérifier'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            result["payload"]["processing_business_category"], "Écart à vérifier"
        )

    def test_older_reconciliation_cannot_replace_current(self):
        # On appelle loader.import_bundle avec self.bundle.
        loader.import_bundle(self.bundle, self.repo)
        # On rend future indépendant de self.repo.data['core.reconciliation_runs'][0], y compris
        # pour les listes et dictionnaires imbriqués ; les modifications du scénario ne doivent pas
        # contaminer l’état de départ.
        future = copy.deepcopy(self.repo.data["core.reconciliation_runs"][0])
        # On utilise ce texte pour future['pipeline_execution_id'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        future["pipeline_execution_id"] = "future_run"
        # On utilise ce texte pour future['reconciliation_run_id'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        future["reconciliation_run_id"] = "future_calculation"
        # On garde dans future['reconciled_at'] la valeur renvoyée par loader.timestamp pour
        # '2026-10-08T10:00:00+00:00'.
        future["reconciled_at"] = loader.timestamp("2026-10-08T10:00:00+00:00")
        # On ajoute future à la fin de self.repo.data['core.reconciliation_runs'] ; les éléments
        # précédents restent conservés.
        self.repo.data["core.reconciliation_runs"].append(future)
        # On récupère self.repo.data[loader.POINTER][0] et on le garde dans pointer pour la suite.
        pointer = self.repo.data[loader.POINTER][0]
        # On complète pointer avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        pointer.update(
            # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de cet
            # appel.
            pipeline_execution_id="future_run",
            reconciliation_run_id="future_calculation",
        )
        # On garde dans before une copie indépendante, y compris pour les objets imbriqués.
        before = copy.deepcopy(self.repo.data)
        # On attend Exception dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(Exception):
            # On appelle loader.import_bundle avec self.bundle.
            loader.import_bundle(self.bundle, self.repo)
        # On vérifie que self.repo.data correspond à before.
        self.assertEqual(self.repo.data, before)

    def test_newer_reconciliation_can_replace_current(self):
        # On appelle loader.import_bundle avec self.bundle.
        loader.import_bundle(self.bundle, self.repo)
        # On rend previous indépendant de self.repo.data['core.reconciliation_runs'][0], y compris
        # pour les listes et dictionnaires imbriqués ; les modifications du scénario ne doivent pas
        # contaminer l’état de départ.
        previous = copy.deepcopy(self.repo.data["core.reconciliation_runs"][0])
        # On utilise ce texte pour previous['pipeline_execution_id'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        previous["pipeline_execution_id"] = "previous_run"
        # On utilise ce texte pour previous['reconciliation_run_id'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        previous["reconciliation_run_id"] = "previous_calc"
        # On garde dans previous['reconciled_at'] la valeur renvoyée par loader.timestamp pour
        # '2026-10-07T10:01:30+00:00'.
        previous["reconciled_at"] = loader.timestamp("2026-10-07T10:01:30+00:00")
        # On ajoute previous à la fin de self.repo.data['core.reconciliation_runs'] ; les éléments
        # précédents restent conservés.
        self.repo.data["core.reconciliation_runs"].append(previous)
        # On récupère self.repo.data[loader.POINTER][0] et on le garde dans pointer pour la suite.
        pointer = self.repo.data[loader.POINTER][0]
        # On complète pointer avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        pointer.update(
            # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de cet
            # appel.
            pipeline_execution_id="previous_run", reconciliation_run_id="previous_calc"
        )
        # On récupère pointer['activated_in_database_at'] et on le garde dans old_date pour la suite.
        old_date = pointer["activated_in_database_at"]
        # On garde dans result le bilan du chargement du lot via le repository fourni.
        result = loader.import_bundle(self.bundle, self.repo)
        # On vérifie que result['activations'] correspond à {'alpha': 'active'}.
        self.assertEqual(result["activations"], {"alpha": "active"})
        # On contrôle le résultat avec assertGreater et les valeurs attendues indiquées juste dessous.
        self.assertGreater(pointer["activated_in_database_at"], old_date)

    def test_unknown_boolean_rejected_during_preparation(self):
        # On utilise ce texte pour self.fixture.nas['passages'][0]['stocks_json_exists'] ; il ne dépend
        # pas d’une valeur récupérée ailleurs à cet endroit.
        self.fixture.nas["passages"][0]["stocks_json_exists"] = "unknown"
        # On utilise ce texte pour self.fixture.results['passages'][0]['stocks_json_exists'] ; il ne
        # dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.fixture.results["passages"][0]["stocks_json_exists"] = "unknown"
        # On parcourt [('nas', self.fixture.nas['passages']), ('result', self.fixture.results['… ;
        # (stage, rows) désigne l’élément courant de ce scénario.
        for stage, rows in [
            ("nas", self.fixture.nas["passages"]),
            ("result", self.fixture.results["passages"]),
        ]:
            # On écrit self.fixture.output_paths[stage, 'passages'] dans self.fixture ; le mode
            # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
            self.fixture.write(
                self.fixture.output_paths[(stage, "passages")], fixtures.csv_bytes(rows)
            )
        # On attend Exception dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(Exception):
            # On appelle loader.prepare_bundle avec self.fixture.root.
            loader.prepare_bundle(self.fixture.root, self.fixture.manifest_path)

    def test_cli_check_only_no_dotenv_or_postgres_required(self):
        # On lance la commande puis on récupère son résultat ; son code de sortie sera interprété par
        # la suite.
        result = subprocess.run(
            [
                sys.executable,
                str(loader.Path(loader.__file__)),
                "--check-only",
                "--manifest",
                self.fixture.manifest_path,
                "--project-root",
                str(self.fixture.root),
            ],
            # On choisit de récupérer les sorties du processus en mémoire pour les contrôles qui
            # suivent.
            capture_output=True,
            # On fournit le texte de travail via le paramètre text de cet appel.
            text=True,
        )
        # On vérifie que result.returncode correspond à 0.
        self.assertEqual(result.returncode, 0, result.stderr)
        # On vérifie que 'aucune connexion' figure dans result.stdout.
        self.assertIn("aucune connexion", result.stdout)

    def test_empty_associations_imported_without_synthetic_rows(self):
        # On appelle self.fixture.make_empty_association_bundle sans argument positionnel.
        self.fixture.make_empty_association_bundle()
        # On garde dans bundle le lot préparé et contrôlé par le module appelé.
        bundle = loader.prepare_bundle(self.fixture.root, self.fixture.manifest_path)
        # On garde dans repo la valeur renvoyée par MemoryRepository.
        repo = MemoryRepository(bundle)
        # On garde dans result le bilan du chargement du lot via le repository fourni.
        result = loader.import_bundle(bundle, repo)
        # On vérifie que result['inserted']['staging.nas_acquisition_observations'] correspond à 3.
        self.assertEqual(result["inserted"]["staging.nas_acquisition_observations"], 3)
        # On parcourt ['staging.nas_association_observations', 'staging.nas_passage_observation… ;
        # table désigne l’élément courant de ce scénario.
        for table in [
            "staging.nas_association_observations",
            "staging.nas_passage_observations",
            "staging.reconciliation_association_rows",
            "staging.reconciliation_passage_rows",
        ]:
            # On vérifie que repo.data[table] correspond à [].
            self.assertEqual(repo.data[table], [])
        # On rend before indépendant de repo.data, y compris pour les listes et dictionnaires
        # imbriqués ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        before = copy.deepcopy(repo.data)
        # On garde dans repeat le bilan du chargement du lot via le repository fourni.
        repeat = loader.import_bundle(bundle, repo)
        # On attend que repeat['inserted'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(repeat["inserted"])
        # On vérifie que repo.data correspond à before.
        self.assertEqual(repo.data, before)

    def test_empty_existing_snapshot_extra_association_rejected(self):
        # On appelle self.fixture.make_empty_association_bundle sans argument positionnel.
        self.fixture.make_empty_association_bundle()
        # On garde dans bundle le lot préparé et contrôlé par le module appelé.
        bundle = loader.prepare_bundle(self.fixture.root, self.fixture.manifest_path)
        # On garde dans repo la valeur renvoyée par MemoryRepository.
        repo = MemoryRepository(bundle)
        # On appelle loader.import_bundle avec bundle.
        loader.import_bundle(bundle, repo)
        # On garde dans row un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        row = dict(bundle["records"]["staging.nas_acquisition_observations"][0])
        # On ajoute dict(pipeline_execution_id=row['pipeline_execution_id'],
        # vineyard_key=row['vineyard_key']… à la fin de
        # repo.data['staging.nas_association_observations'] ; les éléments précédents restent
        # conservés.
        repo.data["staging.nas_association_observations"].append(
            dict(
                # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de
                # cet appel.
                pipeline_execution_id=row["pipeline_execution_id"],
                # On fournit la clé du domaine via le paramètre vineyard_key de cet appel.
                vineyard_key=row["vineyard_key"],
                # On fournit l’identifiant normalisé de l’acquisition via le paramètre
                # acquisition_id_normalise de cet appel.
                acquisition_id_normalise=row["acquisition_id_normalise"],
                parcel_name="P1",
                passage_name="P1_2026-08-11",
                # On fournit le contenu détaillé via le paramètre payload de cet appel.
                payload={},
            )
        )
        # On attend ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValidationError):
            # On appelle loader.import_bundle avec bundle.
            loader.import_bundle(bundle, repo)

    def test_explicit_mapping_gap_loaded_without_rewriting_source(self):
        # On appelle self.fixture.make_recorded_mapping_gap sans argument positionnel.
        self.fixture.make_recorded_mapping_gap()
        # On garde dans bundle le lot préparé et contrôlé par le module appelé.
        bundle = loader.prepare_bundle(self.fixture.root, self.fixture.manifest_path)
        # On garde dans repo la valeur renvoyée par MemoryRepository.
        repo = MemoryRepository(bundle)
        # On appelle loader.import_bundle avec bundle.
        loader.import_bundle(bundle, repo)
        # On récupère le contenu détaillé dans repo.data['staging.nas_acquisition_ob… et on le garde
        # dans nas pour la suite.
        nas = repo.data["staging.nas_acquisition_observations"][0]["payload"]
        # On récupère le contenu détaillé dans repo.data['staging.reconciliation_acq… et on le garde
        # dans rec pour la suite.
        rec = repo.data["staging.reconciliation_acquisition_rows"][0]["payload"]
        # On vérifie que nas['parcel_names_json'] correspond à '["OtherParcel"]'.
        self.assertEqual(nas["parcel_names_json"], '["OtherParcel"]')
        # On vérifie que nas['parcel_mapping_consistent'] correspond à 'False'.
        self.assertEqual(nas["parcel_mapping_consistent"], "False")
        # On vérifie que rec['parcel_names_json'] correspond à nas['parcel_names_json'].
        self.assertEqual(rec["parcel_names_json"], nas["parcel_names_json"])
        # On vérifie que rec['parcel_mapping_consistent'] correspond à 'False'.
        self.assertEqual(rec["parcel_mapping_consistent"], "False")
        # On récupère le contenu détaillé dans repo.data['staging.nas_association_ob… et on le garde
        # dans link pour la suite.
        link = repo.data["staging.nas_association_observations"][0]["payload"]
        # On vérifie que link['parcel_name'] correspond à 'P1'.
        self.assertEqual(link["parcel_name"], "P1")
        # On vérifie que link['parcel_mapping_consistent'] correspond à 'False'.
        self.assertEqual(link["parcel_mapping_consistent"], "False")


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
