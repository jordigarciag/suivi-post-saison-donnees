# Lecture du fichier — Tests de excel publication check.
#

"""Tests du controle local : donnees fictives, aucune connexion PostgreSQL."""

# On importe csv. On transforme les tableaux entre lignes Python et fichiers CSV.
import csv
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe importlib.util. Ce module sera utilisé par les opérations de ce fichier.
import importlib.util
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours l’exige.
import subprocess
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest

# On assemble les morceaux du chemin SCRIPT avec l’opérateur / de pathlib ; aucun fichier n’est créé
# par cette construction.
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/load_excel_publication.py"
# On garde dans spec la valeur renvoyée par importlib.util.spec_from_file_location pour
# 'excel_publication_check'.
spec = importlib.util.spec_from_file_location("excel_publication_check", SCRIPT)
# On garde dans check la valeur renvoyée par importlib.util.module_from_spec.
check = importlib.util.module_from_spec(spec)
# On appelle spec.loader.exec_module avec check.
spec.loader.exec_module(check)


# On prépare les octets JSON avec les options de sérialisation prévues pour les empreintes et les
# fichiers.
def json_bytes(value):
    # On fournit à l’appelant les octets de json.dumps(value, ensure_ascii=False, indent=2) obtenus
    # avec l’encodage indiqué.
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


# On prépare le contenu CSV avant de l’archiver ou de calculer son empreinte.
def csv_bytes(rows, columns):
    # On garde dans out un flux texte en mémoire, utilisable comme un fichier par le lecteur CSV.
    out = io.StringIO(newline="")
    # On garde dans writer un outil d’écriture CSV avec les noms de colonnes explicitement indiqués.
    writer = csv.DictWriter(out, fieldnames=columns)
    # On appelle writer.writeheader sans argument positionnel.
    writer.writeheader()
    # On appelle writer.writerows avec rows.
    writer.writerows(rows)
    # On fournit à l’appelant les octets de out.getvalue() obtenus avec l’encodage indiqué.
    return out.getvalue().encode("utf-8-sig")


class TestExcelPublicationCheck(unittest.TestCase):
    def setUp(self):
        # On garde dans self.temp un dossier temporaire distinct des données du projet.
        self.temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(self.temp.name)
        # On regroupe dans self.identity ces champs nommés ; on pourra les retrouver par leur clé
        # plutôt que par leur position.
        self.identity = {
            # On associe la clé 'config_sha256' à cette valeur dans les données de ce scénario.
            "config_sha256": check.sha256(b"config"),
            # On associe la clé 'reader_sha256' à cette valeur dans les données de ce scénario.
            "reader_sha256": check.sha256(b"reader"),
            # On associe la clé 'versioning_sha256' à cette valeur dans les données de ce scénario.
            "versioning_sha256": check.sha256(b"versioning"),
            # On associe la clé 'python_version' à cette valeur dans les données de ce scénario.
            "python_version": "3.12.10",
            # On associe la clé 'packages' à cette valeur dans les données de ce scénario.
            "packages": {},
        }
        # On assemble ces deux éléments pour construire self.storage.
        self.storage = "v_" + check.sha256(b"domainedemob")[:10]
        # On utilise ce texte pour self.version_id ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.version_id = "20261006_11111111"
        # On utilise ce texte pour self.execution_id ; il ne dépend pas d’une valeur récupérée ailleurs
        # à cet endroit.
        self.execution_id = "20261006_22222222"
        # On utilise ce texte pour self.publication_id ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        self.publication_id = "20261006_33333333"
        # On utilise ce texte pour self.ingested ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.ingested = "2026-10-06T14:21:16+00:00"
        # On assemble ces deux éléments pour construire vd.
        vd = (
            "data/03_normalized/suivi_acquisitions_normalises/versions/"
            + self.storage
            + "/"
            + self.version_id
        )
        # On assemble ces deux éléments pour construire self.vm_path.
        self.vm_path = vd + "/manifest.json"
        # On assemble ces deux éléments pour construire self.pub_path.
        self.pub_path = (
            "data/03_normalized/suivi_acquisitions_normalises/publications/"
            + self.publication_id
            + "/manifest.json"
        )
        # On assemble ces deux éléments pour construire self.ref_path.
        self.ref_path = str(Path(self.pub_path).parent.as_posix()) + "/reference.csv"
        # On assemble ces deux éléments pour construire self.run_path.
        self.run_path = (
            "data/03_normalized/excel_ingestion_runs/"
            + self.execution_id
            + "/manifest.json"
        )
        # On assemble ces deux éléments pour construire self.source_path.
        self.source_path = (
            "data/02_raw_archive/suivi_acquisitions/"
            + self.storage
            + "/"
            + self.version_id
            + "/DomaineDemoB.xlsx"
        )
        # On prépare source avec cette expression pour l’utiliser dans la suite du traitement.
        source = b"opaque Excel fixture - not parsed by the checker"
        # On prépare self.rows comme liste vide ; on la remplira au fil des opérations suivantes.
        self.rows = []
        # On parcourt ['LEFT', 'RIGHT'] en gardant aussi sa position dans (index, side) ; le comptage
        # commence à 2.
        for index, side in enumerate(["LEFT", "RIGHT"], 2):
            # On ajoute {'Vineyard': 'DomaineDemoB', 'Acquisition_ID_normalise':
            # 'DomaineDemoB_C01_2026-06-01T10-… à la fin de self.rows ; les éléments précédents restent
            # conservés.
            self.rows.append(
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "DomaineDemoB",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'Acquisition_ID_normalise'.
                    "Acquisition_ID_normalise": "DomaineDemoB_C01_2026-06-01T10-00-00",
                    # On associe la clé 'Acquisition_side' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_side": side,
                    # On associe la clé 'Acquisition_row_key' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_row_key": "DomaineDemoB_C01_2026-06-01T10-00-00|" + side,
                    # On associe la clé 'source_file' à cette valeur dans les données de ce scénario.
                    "source_file": "DomaineDemoB.xlsx",
                    # On associe la clé 'source_sheet' à cette valeur dans les données de ce scénario.
                    "source_sheet": "Suivi_traitement",
                    # On associe la clé 'source_row_number' à cette valeur dans les données de ce
                    # scénario.
                    "source_row_number": str(index),
                    # On renseigne la date d’ingestion sous la clé 'ingested_at'.
                    "ingested_at": self.ingested,
                    # On associe la clé 'excel_reference_version_id' à cette valeur dans les données de
                    # ce scénario.
                    "excel_reference_version_id": self.version_id,
                    # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
                    "source_sha256": check.sha256(source),
                    # On associe la clé 'Commentaires' à cette valeur dans les données de ce scénario.
                    "Commentaires": "Donnees de test : éàç",
                }
            )
        # On garde dans normalized les octets CSV produits à partir des lignes de cet exemple.
        normalized = csv_bytes(self.rows, list(self.rows[0]))
        # On garde dans rejected les octets CSV produits à partir des lignes de cet exemple.
        rejected = csv_bytes(
            [], ["excel_reference_version_id", "source_sha256", "rejection_reason"]
        )
        # On crée le dictionnaire vide artifacts pour y ranger ensuite les éléments par clé.
        artifacts = {}
        # On parcourt [('source', self.source_path, source), ('normalized', vd + '/normalized.c… ;
        # (label, path, data) désigne l’élément courant de ce scénario.
        for label, path, data in [
            ("source", self.source_path, source),
            ("normalized", vd + "/normalized.csv", normalized),
            ("rejected", vd + "/rejected.csv", rejected),
            ("config", vd + "/tracking_files.yml", b"config"),
            ("reader", vd + "/excel_reader.py", b"reader"),
            ("versioning", vd + "/tracking_versioning.py", b"versioning"),
        ]:
            # On écrit path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout ou
            # d’un remplacement.
            self.write(path, data)
            # On regroupe dans artifacts[label] ces champs nommés ; on pourra les retrouver par leur
            # clé plutôt que par leur position.
            artifacts[label] = {"path": path, "sha256": check.sha256(data)}
        # On regroupe dans self.vm ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        self.vm = {
            # On marque la version du format pour ne pas interpréter un autre contrat de fichier par
            # erreur.
            "format_version": 1,
            # On renseigne l’identifiant de version sous la clé 'version_id'.
            "version_id": self.version_id,
            # On renseigne le domaine concerné sous la clé 'vineyard'.
            "vineyard": "DomaineDemoB",
            # On renseigne la date d’ingestion sous la clé 'ingested_at'.
            "ingested_at": self.ingested,
            # On associe la clé 'source_file' à cette valeur dans les données de ce scénario.
            "source_file": "DomaineDemoB.xlsx",
            # On renseigne la date de modification de la source sous la clé 'source_modified_at'.
            "source_modified_at": "2026-09-07T13:56:47+00:00",
            # On associe la clé 'source_size' à cette valeur dans les données de ce scénario.
            "source_size": len(source),
            # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
            "source_sha256": check.sha256(source),
            # On renseigne les éléments d’identité du lot sous la clé 'identity'.
            "identity": self.identity,
            # On renseigne le nombre de lignes normalisées sous la clé 'normalized_rows'.
            "normalized_rows": 2,
            # On renseigne le nombre d’acquisitions distinctes sous la clé 'logical_acquisitions'.
            "logical_acquisitions": 1,
            # On renseigne le nombre de lignes rejetées sous la clé 'rejected_rows'.
            "rejected_rows": 0,
            # On associe la clé 'artifacts' à cette valeur dans les données de ce scénario.
            "artifacts": artifacts,
        }
        # On écrit self.vm_path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un
        # ajout ou d’un remplacement.
        self.write(self.vm_path, json_bytes(self.vm))
        # On regroupe dans self.entry ces champs nommés ; on pourra les retrouver par leur clé plutôt
        # que par leur position.
        self.entry = {
            # On renseigne le domaine concerné sous la clé 'vineyard'.
            "vineyard": "DomaineDemoB",
            # On renseigne l’identifiant de version sous la clé 'version_id'.
            "version_id": self.version_id,
            # On renseigne la date d’ingestion sous la clé 'ingested_at'.
            "ingested_at": self.ingested,
            # On renseigne le nom du fichier source sous la clé 'source_filename'.
            "source_filename": "DomaineDemoB.xlsx",
            # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
            "source_sha256": check.sha256(source),
            # On renseigne les éléments d’identité du lot sous la clé 'identity'.
            "identity": self.identity,
            # On renseigne le nombre de lignes normalisées sous la clé 'normalized_rows'.
            "normalized_rows": 2,
            # On renseigne le nombre d’acquisitions distinctes sous la clé 'logical_acquisitions'.
            "logical_acquisitions": 1,
            # On renseigne le nombre de lignes rejetées sous la clé 'rejected_rows'.
            "rejected_rows": 0,
            # On renseigne le manifeste du lot sous la clé 'manifest'.
            "manifest": self.vm_path,
            # On renseigne l’empreinte du manifeste sous la clé 'manifest_sha256'.
            "manifest_sha256": check.sha256(json_bytes(self.vm)),
            # On renseigne le chemin du tableau normalisé sous la clé 'normalized_path'.
            "normalized_path": artifacts["normalized"]["path"],
        }
        # On écrit self.ref_path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un
        # ajout ou d’un remplacement.
        self.write(self.ref_path, normalized)
        # On écrit str(Path(self.pub_path).parent.as_posix()) + '/' + self.storage + '.csv' dans self ;
        # le mode d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write(
            str(Path(self.pub_path).parent.as_posix()) + "/" + self.storage + ".csv",
            normalized,
        )
        # On regroupe dans self.publication ces champs nommés ; on pourra les retrouver par leur clé
        # plutôt que par leur position.
        self.publication = {
            # On marque la version du format pour ne pas interpréter un autre contrat de fichier par
            # erreur.
            "format_version": 1,
            # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
            "publication_id": self.publication_id,
            # On associe la clé 'ingestion_execution_id' à cette valeur dans les données de ce
            # scénario.
            "ingestion_execution_id": self.execution_id,
            # On renseigne la date de publication sous la clé 'published_at'.
            "published_at": "2026-10-06T14:21:17+00:00",
            # On renseigne le repère utilisé pour les données Excel sous la clé 'reference'.
            "reference": {
                # On renseigne le chemin de travail sous la clé 'path'.
                "path": self.ref_path,
                # On conserve l’empreinte attendue pour retrouver la même version du contenu.
                "sha256": check.sha256(normalized),
                # On renseigne les lignes sous la clé 'rows'.
                "rows": 2,
            },
            # On associe la clé 'versions' à cette valeur dans les données de ce scénario.
            "versions": {"domainedemob": self.entry},
        }
        # On regroupe dans self.run ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        self.run = {
            # On marque la version du format pour ne pas interpréter un autre contrat de fichier par
            # erreur.
            "format_version": 1,
            # On renseigne l’identifiant d’exécution sous la clé 'execution_id'.
            "execution_id": self.execution_id,
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "success",
            # On renseigne le marqueur d’initialisation sous la clé 'initialization'.
            "initialization": True,
            # On renseigne la date de début sous la clé 'started_at'.
            "started_at": "2026-10-06T14:21:15+00:00",
            # On renseigne la date de fin sous la clé 'finished_at'.
            "finished_at": "2026-10-06T14:21:18+00:00",
            # On renseigne les éléments d’identité du lot sous la clé 'identity'.
            "identity": self.identity,
            # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
            "publication_id": self.publication_id,
            # On renseigne le chemin du tableau Excel regroupé sous la clé 'reference_path'.
            "reference_path": self.ref_path,
            # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
            "vineyards": [
                {
                    # On renseigne le domaine concerné sous la clé 'vineyard'.
                    "vineyard": "DomaineDemoB",
                    # On renseigne l’état du traitement sous la clé 'status'.
                    "status": "version_created",
                    # On associe la clé 'source_file' à cette valeur dans les données de ce scénario.
                    "source_file": "DomaineDemoB.xlsx",
                    # On renseigne la date du contrôle sous la clé 'checked_at'.
                    "checked_at": "2026-10-06T14:21:15.5+00:00",
                    # On renseigne la date d’ingestion sous la clé 'ingested_at'.
                    "ingested_at": self.ingested,
                    # On renseigne l’identifiant de version sous la clé 'version_id'.
                    "version_id": self.version_id,
                    # On renseigne les lignes sous la clé 'rows'.
                    "rows": 2,
                    # On renseigne le nombre d’acquisitions distinctes sous la clé
                    # 'logical_acquisitions'.
                    "logical_acquisitions": 1,
                    # On renseigne le nombre de lignes rejetées sous la clé 'rejected_rows'.
                    "rejected_rows": 0,
                }
            ],
        }
        # On écrit self.run_path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un
        # ajout ou d’un remplacement.
        self.write(self.run_path, json_bytes(self.run))
        # On remet les métadonnées de publication de la fixture en cohérence avec les fichiers de cet
        # essai.
        self.sync_publication()

    def write(self, path, data):
        # On calcule ce quotient pour construire target.
        target = self.root / path
        # On prépare le dossier target.parent avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        target.parent.mkdir(parents=True, exist_ok=True)
        # On écrit le contenu préparé dans target ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        target.write_bytes(data)

    def sync_publication(self):
        # On écrit self.pub_path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un
        # ajout ou d’un remplacement.
        self.write(self.pub_path, json_bytes(self.publication))
        # On garde dans registry un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        registry = dict(self.publication)
        # On garde self.pub_path sous le nom registry['publication_manifest'] ; cette affectation ne
        # copie pas à elle seule un objet mutable.
        registry["publication_manifest"] = self.pub_path
        # On récupère self.publication['reference']['sha256'] et on le garde dans
        # registry['compatibility_export_sha256'] pour la suite.
        registry["compatibility_export_sha256"] = self.publication["reference"][
            "sha256"
        ]
        # On écrit 'state/excel_ingestion/current.json' dans self ; le mode d’ouverture du flux
        # détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write("state/excel_ingestion/current.json", json_bytes(registry))

    def test_valid_publication_left_right_not_double_logical_acquisition(self):
        # On garde dans report la valeur renvoyée par check.check_publication.
        report = check.check_publication(self.root)
        # On vérifie que report['rows'] correspond à 2.
        self.assertEqual(report["rows"], 2)
        # On vérifie que report['logical_acquisitions'] correspond à 1.
        self.assertEqual(report["logical_acquisitions"], 1)
        # On vérifie que report['rejected_rows'] correspond à 0.
        self.assertEqual(report["rejected_rows"], 0)

    def test_control_writes_no_project_file(self):
        # On indexe before par p.relative_to(self.root) ; chaque clé sera associée à (p.read_bytes(),
        # p.stat().st_mtime_ns). Une même clé ne peut garder qu’une valeur.
        before = {
            p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in self.root.rglob("*")
            if p.is_file()
        }
        # On appelle check.check_publication avec self.root.
        check.check_publication(self.root)
        # On indexe after par p.relative_to(self.root) ; chaque clé sera associée à (p.read_bytes(),
        # p.stat().st_mtime_ns). Une même clé ne peut garder qu’une valeur.
        after = {
            p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in self.root.rglob("*")
            if p.is_file()
        }
        # On vérifie que before correspond à after.
        self.assertEqual(before, after)

    def test_corrupted_source_blocks_control(self):
        # On écrit self.source_path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un
        # ajout ou d’un remplacement.
        self.write(self.source_path, b"changed")
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "Empreinte differente"):
            # On appelle check.check_publication avec self.root.
            check.check_publication(self.root)

    def test_missing_archived_code_blocks_control(self):
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        (self.root / self.vm["artifacts"]["reader"]["path"]).unlink()
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "Fichier absent"):
            # On appelle check.check_publication avec self.root.
            check.check_publication(self.root)

    def test_registry_disagreement_blocks_control(self):
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.root / "state/excel_ingestion/current.json"
        # On garde dans registry les objets Python décodés depuis le JSON fourni.
        registry = json.loads(path.read_text())
        # On utilise ce texte pour registry['publication_id'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        registry["publication_id"] = "wrong"
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_bytes(json_bytes(registry))
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "registre courant"):
            # On appelle check.check_publication avec self.root.
            check.check_publication(self.root)

    def test_ingestion_lock_blocks_without_removing_lock(self):
        # On écrit 'state/excel_ingestion/ingestion.lock' dans self ; le mode d’ouverture du flux
        # détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write("state/excel_ingestion/ingestion.lock", b"active")
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "verrou"):
            # On appelle check.check_publication avec self.root.
            check.check_publication(self.root)
        # On attend que (self.root / 'state/excel_ingestion/ingestion.lock').exists() soit évalué comme
        # vrai pour ce cas de test.
        self.assertTrue((self.root / "state/excel_ingestion/ingestion.lock").exists())

    def test_pending_publication_blocks(self):
        # On écrit 'state/excel_ingestion/pending_publication.json' dans self ; le mode d’ouverture du
        # flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write("state/excel_ingestion/pending_publication.json", b"{}")
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "interrompue"):
            # On appelle check.check_publication avec self.root.
            check.check_publication(self.root)

    def test_path_traversal_blocks(self):
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "hors des dossiers"):
            # On appelle check.LocalFiles(self.root).read avec 'data/../../outside.csv'.
            check.LocalFiles(self.root).read("data/../../outside.csv")

    def test_invalid_reference_count_blocks(self):
        # On fixe self.publication['reference']['rows'] à 3 pour cette étape du scénario de test.
        self.publication["reference"]["rows"] = 3
        # On remet les métadonnées de publication de la fixture en cohérence avec les fichiers de cet
        # essai.
        self.sync_publication()
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "Nombre de lignes"):
            # On appelle check.check_publication avec self.root.
            check.check_publication(self.root)

    def test_rehashed_reference_with_wrong_provenance_blocks(self):
        # On construit rows comme une liste à partir de dict(row), pour chaque row de self.rows.
        rows = [dict(row) for row in self.rows]
        # On utilise ce texte pour rows[0]['excel_reference_version_id'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        rows[0]["excel_reference_version_id"] = "wrong-version"
        # On garde dans data les octets CSV produits à partir des lignes de cet exemple.
        data = csv_bytes(rows, list(rows[0]))
        # On écrit self.ref_path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un
        # ajout ou d’un remplacement.
        self.write(self.ref_path, data)
        # On garde dans self.publication['reference']['sha256'] la valeur renvoyée par check.sha256.
        self.publication["reference"]["sha256"] = check.sha256(data)
        # On remet les métadonnées de publication de la fixture en cohérence avec les fichiers de cet
        # essai.
        self.sync_publication()
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "Provenance incoherente"):
            # On appelle check.check_publication avec self.root.
            check.check_publication(self.root)

    def test_duplicate_json_keys_rejected(self):
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "dupliquee"):
            # On appelle check.json_object avec b'{"format_version":1,"a":1,"a":2}'.
            check.json_object(b'{"format_version":1,"a":1,"a":2}', "fixture")

    def test_source_change_during_control_detected(self):
        # On garde dans files la valeur renvoyée par check.LocalFiles.
        files = check.LocalFiles(self.root)
        # On appelle files.read avec self.source_path.
        files.read(self.source_path)
        # On écrit self.source_path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un
        # ajout ou d’un remplacement.
        self.write(self.source_path, b"new size")
        # On attend check.ValidationError avec un message correspondant au motif indiqué dans ce bloc ;
        # si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(check.ValidationError, "modifie pendant"):
            # On appelle files.unchanged sans argument positionnel.
            files.unchanged()

    def test_cli_runs_under_forced_windows_encoding(self):
        # On garde dans env un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        # On lance la commande puis on récupère son résultat ; son code de sortie sera interprété par
        # la suite.
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--check-only",
                "--project-root",
                str(self.root),
            ],
            # On transmet cet environnement au processus plutôt que reprendre implicitement toutes les
            # variables du parent.
            env=env,
            # On choisit de récupérer les sorties du processus en mémoire pour les contrôles qui
            # suivent.
            capture_output=True,
            # On fournit le texte de travail via le paramètre text de cet appel.
            text=True,
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8",
        )
        # On vérifie que result.returncode correspond à 0.
        self.assertEqual(result.returncode, 0, result.stderr)
        # On vérifie que 'RESULTAT : OK' figure dans result.stdout.
        self.assertIn("RESULTAT : OK", result.stdout)
        # On vérifie que 'aucune connexion, aucune ecriture' figure dans result.stdout.
        self.assertIn("aucune connexion, aucune ecriture", result.stdout)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
