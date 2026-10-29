# Lecture du fichier — Données et outils de comparaison utilisés par les tests.
# On garde de petits exemples maîtrisés pour connaître les résultats attendus. Les tests qui les
# importent peuvent ainsi se concentrer sur une règle précise.
#

"""Tests de controle NAS/rapprochement sur fichiers fictifs, sans reseau ni base."""

# On importe csv. On transforme les tableaux entre lignes Python et fichiers CSV.
import csv
# On sépare les copies d’objets, notamment pour comparer un état avant et après une opération.
import copy
# On rend disponibles redirect_stdout depuis contextlib, pour les appels de ce fichier.
from contextlib import redirect_stdout
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

# On assemble les morceaux du chemin SCRIPTS avec l’opérateur / de pathlib ; aucun fichier n’est créé
# par cette construction.
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(SCRIPTS))
# On importe import_nas_reconciliation sous le nom checker. Ce module sera utilisé par les opérations
# de ce fichier.
import import_nas_reconciliation as checker


# On prépare les octets JSON avec les options de sérialisation prévues pour les empreintes et les
# fichiers.
def json_bytes(value):
    # On fournit à l’appelant les octets de json.dumps(value, ensure_ascii=False, indent=2) obtenus
    # avec l’encodage indiqué.
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


# On prépare le contenu CSV avant de l’archiver ou de calculer son empreinte.
def csv_bytes(rows):
    # On garde dans stream un flux texte en mémoire, utilisable comme un fichier par le lecteur CSV.
    stream = io.StringIO(newline="")
    # On garde dans writer un outil d’écriture CSV avec les noms de colonnes explicitement indiqués.
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    # On appelle writer.writeheader sans argument positionnel.
    writer.writeheader()
    # On appelle writer.writerows avec rows.
    writer.writerows(rows)
    # On fournit à l’appelant les octets de stream.getvalue() obtenus avec l’encodage indiqué.
    return stream.getvalue().encode("utf-8-sig")


class TestNasReconciliationCheck(unittest.TestCase):
    def setUp(self):
        # On garde dans self.temp un dossier temporaire distinct des données du projet.
        self.temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(self.temp.name)
        # On utilise ce texte pour self.execution ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.execution = "20261007_12345678"
        # On utilise ce texte pour self.publication ; il ne dépend pas d’une valeur récupérée ailleurs
        # à cet endroit.
        self.publication = "20261006_87654321"
        # On utilise ce texte pour self.version ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.version = "20261006_11111111"
        # On assemble ces deux éléments pour construire self.manifest_path.
        self.manifest_path = (
            "data/03_normalized/pipeline_runs/" + self.execution + "/manifest.json"
        )
        # On assemble ces deux éléments pour construire self.reference_path.
        self.reference_path = (
            checker.PUB_ROOT + "/" + self.publication + "/reference.csv"
        )
        # On assemble ces deux éléments pour construire self.pub_path.
        self.pub_path = checker.PUB_ROOT + "/" + self.publication + "/manifest.json"
        # On assemble ces deux éléments pour construire self.snapshot_path.
        self.snapshot_path = (
            "data/03_normalized/pipeline_runs/"
            + self.execution
            + "/tracking_reference_snapshot.csv"
        )
        # On utilise ce texte pour self.ingested ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.ingested = "2026-10-06T14:21:16+00:00"
        # On utilise ce texte pour self.checked ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.checked = "2026-10-07T10:01:00+00:00"
        # On utilise ce texte pour self.reconciled ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.reconciled = "2026-10-07T10:02:00+00:00"
        # On indexe self.nas par kind ; chaque clé sera associée à []. Une même clé ne peut garder
        # qu’une valeur.
        self.nas = {kind: [] for kind in checker.KINDS}
        # On indexe self.results par kind ; chaque clé sera associée à []. Une même clé ne peut garder
        # qu’une valeur.
        self.results = {kind: [] for kind in checker.KINDS}
        # On prépare reference comme liste vide ; on la remplira au fil des opérations suivantes.
        reference = []
        # On construit ids comme une liste à partir de 'Alpha_A' + str(i) + '_2026-08-11T10-00-00',
        # pour chaque i de range(3).
        ids = ["Alpha_A" + str(i) + "_2026-08-11T10-00-00" for i in range(3)]
        # On parcourt ids en gardant aussi sa position dans (i, acquisition) ; le comptage commence à
        # zéro.
        for i, acquisition in enumerate(ids):
            # On garde dans positive le résultat de cette comparaison : i est inférieur à 2.
            positive = i < 2
            # On ajoute {'Vineyard': 'Alpha', 'project_year': '2026', 'acquisition_id_normalise':
            # acquisition, 'c… à la fin de self.nas['acquisitions'] ; les éléments précédents restent
            # conservés.
            self.nas["acquisitions"].append(
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "Alpha",
                    # On associe la clé 'project_year' à cette valeur dans les données de ce scénario.
                    "project_year": "2026",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'acquisition_id_normalise'.
                    "acquisition_id_normalise": acquisition,
                    # On renseigne la date du contrôle sous la clé 'checked_at'.
                    "checked_at": self.checked,
                    # On associe la clé 'parcel_names_json' à cette valeur dans les données de ce
                    # scénario.
                    "parcel_names_json": json.dumps(["P1"] if positive else []),
                    # On associe la clé 'parcel_count' à cette valeur dans les données de ce scénario.
                    "parcel_count": "1" if positive else "0",
                    # On associe la clé 'passage_links_json' à cette valeur dans les données de ce
                    # scénario.
                    "passage_links_json": json.dumps(
                        [{"parcel_name": "P1", "passage_name": "P1_2026-08-11"}]
                        if positive
                        else []
                    ),
                    # On associe la clé 'passage_link_count' à cette valeur dans les données de ce
                    # scénario.
                    "passage_link_count": "1" if positive else "0",
                    # On associe la clé 'passage_outputs_verifiable' à cette valeur dans les données de
                    # ce scénario.
                    "passage_outputs_verifiable": str(positive),
                    # On associe la clé 'vitiparcel_created' à cette valeur dans les données de ce
                    # scénario.
                    "vitiparcel_created": str(positive),
                    # On renseigne le statut du suivi Excel sous la clé 'excel_pipeline_status'.
                    "excel_pipeline_status": "À déterminer",
                    # On renseigne l’erreur de lecture des données brutes sous la clé 'raw_error'.
                    "raw_error": "",
                }
            )
            # On regroupe dans excel ces champs nommés ; on pourra les retrouver par leur clé plutôt
            # que par leur position.
            excel = {
                # On renseigne le domaine concerné sous la clé 'Vineyard'.
                "Vineyard": "Alpha",
                # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                # 'Acquisition_ID_normalise'.
                "Acquisition_ID_normalise": acquisition,
                # On associe la clé 'excel_reference_version_id' à cette valeur dans les données de ce
                # scénario.
                "excel_reference_version_id": self.version,
                # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
                "source_sha256": "a" * 64,
                # On associe la clé 'source_file' à cette valeur dans les données de ce scénario.
                "source_file": "Alpha.xlsx",
                # On renseigne la date d’ingestion sous la clé 'ingested_at'.
                "ingested_at": self.ingested,
                "Périmètre": "Production",
                # On associe la clé 'Statut_pipeline' à cette valeur dans les données de ce scénario.
                "Statut_pipeline": "À déterminer",
            }
            # On ajoute excel à la fin de reference ; les éléments précédents restent conservés.
            reference.append(excel)
            # On regroupe dans context ces champs nommés ; on pourra les retrouver par leur clé plutôt
            # que par leur position.
            context = {
                # On associe la clé 'excel_acquisition_id_normalise' à cette valeur dans les données de
                # ce scénario.
                "excel_acquisition_id_normalise": acquisition,
                # On associe la clé 'excel_vineyard' à cette valeur dans les données de ce scénario.
                "excel_vineyard": "Alpha",
                # On associe la clé 'excel_ingested_at' à cette valeur dans les données de ce scénario.
                "excel_ingested_at": self.ingested,
                # On associe la clé 'excel_source_files' à cette valeur dans les données de ce
                # scénario.
                "excel_source_files": "Alpha.xlsx",
                # On renseigne le périmètre du suivi Excel sous la clé 'excel_perimeter'.
                "excel_perimeter": "Production",
                # On renseigne le statut du suivi Excel sous la clé 'excel_pipeline_status'.
                "excel_pipeline_status": "À déterminer",
            }
            # On garde dans result un nouveau dictionnaire construit avec les valeurs indiquées (la
            # copie reste superficielle).
            result = dict(self.nas["acquisitions"][-1])
            # On garde dans result['extractor_excel_pipeline_status'] la valeur renvoyée par result.pop
            # pour 'excel_pipeline_status'.
            result["extractor_excel_pipeline_status"] = result.pop(
                "excel_pipeline_status"
            )
            # On complète result avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
            # valeur fournie.
            result.update(
                context,
                # On fournit la date du rapprochement via le paramètre reconciled_at de cet appel.
                reconciled_at=self.reconciled,
                # On fournit la catégorie métier du traitement via le paramètre
                # processing_business_category de cet appel.
                processing_business_category="Preuve WEBP complète"
                if positive
                else "Écart à vérifier",
                acquisition_new_anomaly_candidate=str(not positive),
            )
            # On ajoute result à la fin de self.results['acquisitions'] ; les éléments précédents
            # restent conservés.
            self.results["acquisitions"].append(result)
            # Cette branche traite le cas où positive est évalué comme vrai.
            if positive:
                # On regroupe dans association ces champs nommés ; on pourra les retrouver par leur clé
                # plutôt que par leur position.
                association = {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "Alpha",
                    # On associe la clé 'project_year' à cette valeur dans les données de ce scénario.
                    "project_year": "2026",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'acquisition_id_normalise'.
                    "acquisition_id_normalise": acquisition,
                    # On associe la clé 'parcel_name' à cette valeur dans les données de ce scénario.
                    "parcel_name": "P1",
                    # On associe la clé 'passage_name' à cette valeur dans les données de ce scénario.
                    "passage_name": "P1_2026-08-11",
                    # On renseigne la date du contrôle sous la clé 'checked_at'.
                    "checked_at": self.checked,
                    # On associe la clé 'passage_outputs_verifiable' à cette valeur dans les données de
                    # ce scénario.
                    "passage_outputs_verifiable": "True",
                    # On associe la clé 'vitiparcel_created' à cette valeur dans les données de ce
                    # scénario.
                    "vitiparcel_created": "True",
                    # On associe la clé 'passage_error' à cette valeur dans les données de ce scénario.
                    "passage_error": "",
                }
                # On ajoute association à la fin de self.nas['associations'] ; les éléments précédents
                # restent conservés.
                self.nas["associations"].append(association)
                # On ajoute dict(association, **context) à la fin de self.results['associations'] ; les
                # éléments précédents restent conservés.
                self.results["associations"].append(dict(association, **context))
        # On regroupe dans passage ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        passage = {
            # On renseigne le domaine concerné sous la clé 'Vineyard'.
            "Vineyard": "Alpha",
            # On associe la clé 'project_year' à cette valeur dans les données de ce scénario.
            "project_year": "2026",
            # On associe la clé 'parcel_name' à cette valeur dans les données de ce scénario.
            "parcel_name": "P1",
            # On associe la clé 'passage_name' à cette valeur dans les données de ce scénario.
            "passage_name": "P1_2026-08-11",
            # On renseigne la date du contrôle sous la clé 'checked_at'.
            "checked_at": self.checked,
            # On associe la clé 'acquisitions_controlled_count' à cette valeur dans les données de ce
            # scénario.
            "acquisitions_controlled_count": "2",
            # On associe la clé 'acquisition_ids_json' à cette valeur dans les données de ce scénario.
            "acquisition_ids_json": json.dumps(ids[:2]),
            # On associe la clé 'stocks_json_exists' à cette valeur dans les données de ce scénario.
            "stocks_json_exists": "True",
            # On associe la clé 'non_healthy_status_count' à cette valeur dans les données de ce
            # scénario.
            "non_healthy_status_count": "1",
            # On associe la clé 'vitiparcel_created' à cette valeur dans les données de ce scénario.
            "vitiparcel_created": "True",
            # On associe la clé 'passage_error' à cette valeur dans les données de ce scénario.
            "passage_error": "",
        }
        # On ajoute passage à la fin de self.nas['passages'] ; les éléments précédents restent
        # conservés.
        self.nas["passages"].append(passage)
        # On ajoute dict(passage, vitiparcel_ready_verifiable='True',
        # vitiparcel_ready_for_delivery='True', p… à la fin de self.results['passages'] ; les éléments
        # précédents restent conservés.
        self.results["passages"].append(
            dict(
                passage,
                vitiparcel_ready_verifiable="True",
                vitiparcel_ready_for_delivery="True",
                passage_review_candidate="False",
                passage_business_category="Critère satisfait",
            )
        )
        # On garde dans reference_data les octets CSV produits à partir des lignes de cet exemple.
        reference_data = csv_bytes(reference)
        # On écrit self.reference_path dans self ; le mode d’ouverture du flux détermine s’il s’agit
        # d’un ajout ou d’un remplacement.
        self.write(self.reference_path, reference_data)
        # On écrit self.snapshot_path dans self ; le mode d’ouverture du flux détermine s’il s’agit
        # d’un ajout ou d’un remplacement.
        self.write(self.snapshot_path, reference_data)
        # On regroupe dans publication ces champs nommés ; on pourra les retrouver par leur clé plutôt
        # que par leur position.
        publication = {
            # On marque la version du format pour ne pas interpréter un autre contrat de fichier par
            # erreur.
            "format_version": 1,
            # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
            "publication_id": self.publication,
            # On renseigne la date de publication sous la clé 'published_at'.
            "published_at": "2026-10-06T14:21:17+00:00",
            # On renseigne le repère utilisé pour les données Excel sous la clé 'reference'.
            "reference": {
                # On renseigne le chemin de travail sous la clé 'path'.
                "path": self.reference_path,
                # On conserve l’empreinte attendue pour retrouver la même version du contenu.
                "sha256": checker.sha256(reference_data),
                # On renseigne les lignes sous la clé 'rows'.
                "rows": 3,
            },
            # On associe la clé 'versions' à cette valeur dans les données de ce scénario.
            "versions": {
                # On associe la clé 'alpha' à cette valeur dans les données de ce scénario.
                "alpha": {
                    # On renseigne le domaine concerné sous la clé 'vineyard'.
                    "vineyard": "Alpha",
                    # On renseigne l’identifiant de version sous la clé 'version_id'.
                    "version_id": self.version,
                    # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
                    "source_sha256": "a" * 64,
                    # On renseigne le nom du fichier source sous la clé 'source_filename'.
                    "source_filename": "Alpha.xlsx",
                    # On renseigne la date d’ingestion sous la clé 'ingested_at'.
                    "ingested_at": self.ingested,
                }
            },
        }
        # On écrit self.pub_path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un
        # ajout ou d’un remplacement.
        self.write(self.pub_path, json_bytes(publication))
        # On regroupe dans item ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
        # leur position.
        item = {
            # On renseigne le domaine concerné sous la clé 'vineyard'.
            "vineyard": "Alpha",
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "success",
            # On renseigne la date de début sous la clé 'started_at'.
            "started_at": "2026-10-07T10:00:01+00:00",
            # On renseigne la date de fin sous la clé 'finished_at'.
            "finished_at": "2026-10-07T10:03:00+00:00",
            # On associe la clé 'directory_name' à cette valeur dans les données de ce scénario.
            "directory_name": "v01",
            # On associe la clé 'extraction_returncode' à cette valeur dans les données de ce scénario.
            "extraction_returncode": 0,
            # On associe la clé 'reconciliation_returncode' à cette valeur dans les données de ce
            # scénario.
            "reconciliation_returncode": 0,
            # On associe la clé 'extraction_run_id' à cette valeur dans les données de ce scénario.
            "extraction_run_id": "2026-10-07T10-01-00Z",
            # On associe la clé 'reconciliation_run_id' à cette valeur dans les données de ce scénario.
            "reconciliation_run_id": "2026-10-07T10-02-00-123456Z",
            # On associe la clé 'evidence_outputs' à cette valeur dans les données de ce scénario.
            "evidence_outputs": {},
            # On associe la clé 'reconciliation_outputs' à cette valeur dans les données de ce
            # scénario.
            "reconciliation_outputs": {},
            # On renseigne les constats à présenter sous la clé 'observations'.
            "observations": {
                # On renseigne la date du contrôle sous la clé 'checked_at'.
                "checked_at": self.checked,
                # On associe la clé 'volumes' à cette valeur dans les données de ce scénario.
                "volumes": {"evidence": 3, "associations": 2, "passages": 1},
                # On associe la clé 'rows_with_observation_errors' à cette valeur dans les données de
                # ce scénario.
                "rows_with_observation_errors": {
                    # On associe la clé 'evidence' à cette valeur dans les données de ce scénario.
                    "evidence": 0,
                    # On renseigne les associations entre acquisitions et passages sous la clé
                    # 'associations'.
                    "associations": 0,
                    # On renseigne les passages sous la clé 'passages'.
                    "passages": 0,
                },
            },
        }
        # On crée le dictionnaire vide self.output_paths pour y ranger ensuite les éléments par clé.
        self.output_paths = {}
        # On parcourt [('nas', self.nas, 'nas_live_evidence', item['extraction_run_id'], item['… ;
        # (stage, datasets, folder, run_id, outputs) désigne l’élément courant de ce scénario.
        for stage, datasets, folder, run_id, outputs in [
            (
                "nas",
                self.nas,
                "nas_live_evidence",
                item["extraction_run_id"],
                item["evidence_outputs"],
            ),
            (
                "result",
                self.results,
                "reconciliations/nas_live",
                item["reconciliation_run_id"],
                item["reconciliation_outputs"],
            ),
        ]:
            # On parcourt checker.KINDS ; kind désigne l’élément courant de ce scénario.
            for kind in checker.KINDS:
                # On assemble ces deux éléments pour construire path.
                path = (
                    "data/03_normalized/"
                    + folder
                    + "/runs/"
                    + self.execution
                    + "/v01/alpha_"
                    + kind
                    + "_"
                    + run_id
                    + ".csv"
                )
                # On gardu chemin de travail sous le nom outputs['evidence' if stage == 'nas' and
                # kind == 'acquisitions'… ; cette affectation ne copie pas à elle seule un objet
                # mutable.
                outputs[
                    "evidence" if stage == "nas" and kind == "acquisitions" else kind
                ] = path
                # On gardu chemin de travail sous le nom self.output_paths[stage, kind] ; cette
                # affectation ne copie pas à elle seule un objet mutable.
                self.output_paths[(stage, kind)] = path
                # On écrit path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un
                # ajout ou d’un remplacement.
                self.write(path, csv_bytes(datasets[kind]))
        # On regroupe dans self.manifest ces champs nommés ; on pourra les retrouver par leur clé
        # plutôt que par leur position.
        self.manifest = {
            # On renseigne l’identifiant du traitement NAS sous la clé 'pipeline_execution_id'.
            "pipeline_execution_id": self.execution,
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "success",
            # On associe la clé 'project_year' à cette valeur dans les données de ce scénario.
            "project_year": 2026,
            # On renseigne la date de début sous la clé 'started_at'.
            "started_at": "2026-10-07T10:00:00+00:00",
            # On renseigne la date de fin sous la clé 'finished_at'.
            "finished_at": "2026-10-07T10:03:01+00:00",
            # On associe la clé 'reference_source' à cette valeur dans les données de ce scénario.
            "reference_source": self.reference_path,
            # On associe la clé 'reference_snapshot' à cette valeur dans les données de ce scénario.
            "reference_snapshot": self.snapshot_path,
            # On renseigne l’empreinte du tableau Excel regroupé sous la clé 'reference_sha256'.
            "reference_sha256": checker.sha256(reference_data),
            # On associe la clé 'script_sha256' à cette valeur dans les données de ce scénario.
            "script_sha256": {"extractor.py": "b" * 64, "reconciler.py": "c" * 64},
            # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
            "vineyards": [item],
        }
        # On recalcule le manifeste de test après les modifications du scénario.
        self.sync_manifest()

    def write(self, relative, data):
        # On calcule ce quotient pour construire path.
        path = self.root / relative
        # On prépare le dossier path.parent avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        path.parent.mkdir(parents=True, exist_ok=True)
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_bytes(data)

    def sync_manifest(self):
        # On écrit self.manifest_path dans self ; le mode d’ouverture du flux détermine s’il s’agit
        # d’un ajout ou d’un remplacement.
        self.write(self.manifest_path, json_bytes(self.manifest))

    def sync_csv(self, stage, kind):
        # On écrit self.output_paths[stage, kind] dans self ; le mode d’ouverture du flux détermine
        # s’il s’agit d’un ajout ou d’un remplacement.
        self.write(
            self.output_paths[(stage, kind)],
            csv_bytes((self.nas if stage == "nas" else self.results)[kind]),
        )

    def run_check(self):
        # On fournit à l’appelant le résultat du contrôle de cohérence des sorties du parcours NAS.
        return checker.check_pipeline(self.root, self.manifest_path)

    def test_valid_bundle_and_separate_nonverifiable_status(self):
        # On garde dans report le bilan du contrôle lancé sur les données de ce scénario.
        report = self.run_check()
        # On vérifie que report['files_verified'] correspond à 10.
        self.assertEqual(report["files_verified"], 10)
        # On vérifie que len(report['artifacts']) correspond à 6.
        self.assertEqual(len(report["artifacts"]), 6)
        # On vérifie que report['vineyards'][0]['not_verifiable'] correspond à 1.
        self.assertEqual(report["vineyards"][0]["not_verifiable"], 1)
        # On vérifie que report['vineyards'][0]['acquisition_candidates'] correspond à 1.
        self.assertEqual(report["vineyards"][0]["acquisition_candidates"], 1)
        # On vérifie que report['vineyards'][0]['positive_passages'] correspond à 1.
        self.assertEqual(report["vineyards"][0]["positive_passages"], 1)

    def test_no_files_written(self):
        # On indexe before par p.relative_to(self.root) ; chaque clé sera associée à (p.read_bytes(),
        # p.stat().st_mtime_ns). Une même clé ne peut garder qu’une valeur.
        before = {
            p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in self.root.rglob("*")
            if p.is_file()
        }
        # On appelle self.run_check sans argument positionnel.
        self.run_check()
        # On indexe after par p.relative_to(self.root) ; chaque clé sera associée à (p.read_bytes(),
        # p.stat().st_mtime_ns). Une même clé ne peut garder qu’une valeur.
        after = {
            p.relative_to(self.root): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in self.root.rglob("*")
            if p.is_file()
        }
        # On vérifie que before correspond à after.
        self.assertEqual(before, after)

    def test_corrupted_reference_blocks(self):
        # On écrit self.reference_path dans self ; le mode d’ouverture du flux détermine s’il s’agit
        # d’un ajout ou d’un remplacement.
        self.write(self.reference_path, b"changed")
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "Empreinte differente"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_corrupted_snapshot_blocks(self):
        # On écrit self.snapshot_path dans self ; le mode d’ouverture du flux détermine s’il s’agit
        # d’un ajout ou d’un remplacement.
        self.write(self.snapshot_path, b"changed")
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "Empreinte differente"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_failed_pipeline_blocks(self):
        # On utilise ce texte pour self.manifest['status'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        self.manifest["status"] = "failed"
        # On recalcule le manifeste de test après les modifications du scénario.
        self.sync_manifest()
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "entierement reussie"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_duplicate_acquisition_key_blocks(self):
        # On ajoute dict(self.nas['acquisitions'][0]) à la fin de self.nas['acquisitions'] ; les
        # éléments précédents restent conservés.
        self.nas["acquisitions"].append(dict(self.nas["acquisitions"][0]))
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("nas", "acquisitions")
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "Cle dupliquee"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_unknown_association_blocks(self):
        # On utilise ce texte pour self.nas['associations'][0]['acquisition_id_normalise'] ; il ne
        # dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.nas["associations"][0]["acquisition_id_normalise"] = "unknown"
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("nas", "associations")
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "acquisition inconnue"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_changed_observed_fact_in_result_blocks(self):
        # On utilise ce texte pour self.results['acquisitions'][0]['vitiparcel_created'] ; il ne dépend
        # pas d’une valeur récupérée ailleurs à cet endroit.
        self.results["acquisitions"][0]["vitiparcel_created"] = "False"
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("result", "acquisitions")
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(
            checker.ValidationError, "Information source modifiee"
        ):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_wrong_excel_ingestion_date_blocks(self):
        # On utilise ce texte pour self.results['acquisitions'][0]['excel_ingested_at'] ; il ne dépend
        # pas d’une valeur récupérée ailleurs à cet endroit.
        self.results["acquisitions"][0]["excel_ingested_at"] = (
            "2020-01-01T00:00:00+00:00"
        )
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("result", "acquisitions")
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "Source/date Excel"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_unknown_boolean_is_not_silently_false(self):
        # On commence self.nas['acquisitions'][0]['passage_outputs_verifiable'] avec un texte vide, à
        # compléter uniquement si la suite apporte une information.
        self.nas["acquisitions"][0]["passage_outputs_verifiable"] = ""
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("nas", "acquisitions")
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "Booleen absent"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_invalid_json_cell_blocks(self):
        # On utilise ce texte pour self.nas['acquisitions'][0]['passage_links_json'] ; il ne dépend pas
        # d’une valeur récupérée ailleurs à cet endroit.
        self.nas["acquisitions"][0]["passage_links_json"] = "[invalid"
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("nas", "acquisitions")
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "JSON de cellule"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_wrong_manifest_count_blocks(self):
        # On fixe self.manifest['vineyards'][0]['observations']['volumes']['eviden… à 99 pour cette
        # étape du scénario de test.
        self.manifest["vineyards"][0]["observations"]["volumes"]["evidence"] = 99
        # On recalcule le manifeste de test après les modifications du scénario.
        self.sync_manifest()
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "Comptage NAS"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_local_ingestion_lock_blocks_without_deleting_it(self):
        # On écrit 'state/excel_ingestion/ingestion.lock' dans self ; le mode d’ouverture du flux
        # détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write("state/excel_ingestion/ingestion.lock", b"active")
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "verrous"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()
        # On attend que (self.root / 'state/excel_ingestion/ingestion.lock').exists() soit évalué comme
        # vrai pour ce cas de test.
        self.assertTrue((self.root / "state/excel_ingestion/ingestion.lock").exists())

    def test_external_windows_path_is_not_opened(self):
        # On utilise ce texte pour self.manifest['vineyards'][0]['evidence_outputs']['evidence'] ; il
        # ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.manifest["vineyards"][0]["evidence_outputs"]["evidence"] = (
            "D:\\NAS\\outside.csv"
        )
        # On recalcule le manifeste de test après les modifications du scénario.
        self.sync_manifest()
        # On attend checker.ValidationError avec un message correspondant au motif indiqué dans ce bloc
        # ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(checker.ValidationError, "Chemin absolu"):
            # On appelle self.run_check sans argument positionnel.
            self.run_check()

    def test_output_distinguishes_acquisitions_and_identified_passages(self):
        # On garde dans report le bilan du contrôle lancé sur les données de ce scénario.
        report = self.run_check()
        # On garde dans output un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        output = io.StringIO()
        # On utilise redirect_stdout(output) dans son contexte de gestion ; les opérations de sortie
        # sont exécutées en quittant le bloc.
        with redirect_stdout(output):
            # On appelle checker.render_report avec report.
            checker.render_report(report)
        # On garde dans text la valeur renvoyée par output.getvalue.
        text = output.getvalue()
        # On vérifie que 'Acquisitions à vérifier : 1 / 3' figure dans text.
        self.assertIn("Acquisitions à vérifier : 1 / 3", text)
        # On vérifie que 'sorties de passage ne sont pas vérifiables : 1 / 3' figure dans text.
        self.assertIn("sorties de passage ne sont pas vérifiables : 1 / 3", text)
        # On vérifie que 'Sans passage associé identifié : 1' figure dans text.
        self.assertIn("Sans passage associé identifié : 1", text)
        # On vérifie que 'Passages à vérifier selon le bilan enregistré : 0 / 1' figure dans text.
        self.assertIn("Passages à vérifier selon le bilan enregistré : 0 / 1", text)
        # On vérifie que 'Ce compteur ne porte QUE sur les passages identifiés.' figure dans text.
        self.assertIn("Ce compteur ne porte QUE sur les passages identifiés.", text)
        # On vérifie que 'Cela ne prouve PAS que VitiParcel est absent.' figure dans text.
        self.assertIn("Cela ne prouve PAS que VitiParcel est absent.", text)
        # On vérifie que 'ne pas les additionner' figure dans text.
        self.assertIn("ne pas les additionner", text)
        # On vérifie que '📋' figure dans text.
        self.assertIn("📋", text)
        # On vérifie que '✅ RESULTAT : OK' figure dans text.
        self.assertIn("✅ RESULTAT : OK", text)

    def test_pedagogical_rendering_does_not_change_results(self):
        # On garde dans report le bilan du contrôle lancé sur les données de ce scénario.
        report = self.run_check()
        # On rend before indépendant de report, y compris pour les listes et dictionnaires imbriqués
        # ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        before = copy.deepcopy(report)
        # On utilise redirect_stdout(io.StringIO()) dans son contexte de gestion ; les opérations de
        # sortie sont exécutées en quittant le bloc.
        with redirect_stdout(io.StringIO()):
            # On appelle checker.render_report avec report.
            checker.render_report(report)
        # On vérifie que report correspond à before.
        self.assertEqual(report, before)

    def render_text(self, report=None):
        # On garde dans output un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        output = io.StringIO()
        # On utilise redirect_stdout(output) dans son contexte de gestion ; les opérations de sortie
        # sont exécutées en quittant le bloc.
        with redirect_stdout(output):
            # On appelle checker.render_report avec self.run_check() if report is None else report.
            checker.render_report(self.run_check() if report is None else report)
        # On fournit à l’appelant la valeur renvoyée par output.getvalue.
        return output.getvalue()

    def test_lists_candidate_identifiers_and_recorded_context(self):
        # On garde dans report le bilan du contrôle lancé sur les données de ce scénario.
        report = self.run_check()
        # On garde dans text le texte rendu par l’interface pour ce scénario.
        text = self.render_text(report)
        # On garde dans candidate le prochain élément de (row for row in
        # report['vineyards'][0]['acquisition_details'] if row['rev….
        candidate = next(
            row
            for row in report["vineyards"][0]["acquisition_details"]
            if row["review"]
        )
        # On vérifie que '       - ' + candidate['id'] figure dans text.
        self.assertIn("       - " + candidate["id"], text)
        # On vérifie que 'Traitement d’images : ' + candidate['processing_category'] figure dans
        # text.
        self.assertIn("Traitement d’images : " + candidate["processing_category"], text)
        # On vérifie que 'périmètre=Production | statut=À déterminer' figure dans text.
        self.assertIn("périmètre=Production | statut=À déterminer", text)
        # On vérifie que 'exactement les mêmes que la liste à vérifier ci-dessus' figure dans text.
        self.assertIn("exactement les mêmes que la liste à vérifier ci-dessus", text)

    def test_lists_passage_names_in_all_three_categories(self):
        # On parcourt [(True, True, 'Critère technique satisfait : 1 / 1'), (True, False, 'Crit… ;
        # (verifiable, ready, title) désigne l’élément courant de ce scénario.
        for verifiable, ready, title in [
            (True, True, "Critère technique satisfait : 1 / 1"),
            (
                True,
                False,
                "Critère technique non démontré (évaluation possible) : 1 / 1",
            ),
            (False, False, "Critère non évaluable selon le bilan enregistré : 1 / 1"),
        ]:
            # On garde dans report le bilan du contrôle lancé sur les données de ce scénario.
            report = self.run_check()
            # On récupère report['vineyards'][0]['passage_details'][0] et on le garde dans detail pour
            # la suite.
            detail = report["vineyards"][0]["passage_details"][0]
            # On garde l’état de vérifiabilité sous le nom detail['verifiable'] ; cette affectation ne
            # copie pas à elle seule un objet mutable.
            detail["verifiable"] = verifiable
            # On garde ready sous le nom detail['ready'] ; cette affectation ne copie pas à elle seule
            # un objet mutable.
            detail["ready"] = ready
            # On garde dans report['vineyards'][0]['positive_passages'] la conversion numérique de
            # verifiable and ready en entier.
            report["vineyards"][0]["positive_passages"] = int(verifiable and ready)
            # On garde dans text le texte rendu par l’interface pour ce scénario.
            text = self.render_text(report)
            # On vérifie que title figure dans text.
            self.assertIn(title, text)
            # On vérifie que 'P1_2026-08-11 | parcelle=P1 | acquisitions associées=2' figure dans
            # text.
            self.assertIn(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                "P1_2026-08-11 | parcelle=P1 | acquisitions associées=2", text
            )

    def test_lists_ten_files_with_roles_names_directories_and_counts(self):
        # On garde dans report le bilan du contrôle lancé sur les données de ce scénario.
        report = self.run_check()
        # On garde dans text le texte rendu par l’interface pour ce scénario.
        text = self.render_text(report)
        # On vérifie que 'PREUVES NAS : ce qui a été observé — 3 CSV' figure dans text.
        self.assertIn("PREUVES NAS : ce qui a été observé — 3 CSV", text)
        # On vérifie que 'RAPPROCHEMENT : contexte Excel et conclusions enregistrées — 3 CSV' figure
        # dans text.
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "RAPPROCHEMENT : contexte Excel et conclusions enregistrées — 3 CSV", text
        )
        # On vérifie la présence de '10 fichiers locaux lus = 6 CSV de preuves/rapprochement + 2 CSV de
        # r… dans text.
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "10 fichiers locaux lus = 6 CSV de preuves/rapprochement + 2 CSV de référence Excel + 2 manifestes JSON",
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            text,
        )
        # On parcourt report['artifacts'] + report['common_files'] ; file désigne l’élément courant de
        # ce scénario.
        for file in report["artifacts"] + report["common_files"]:
            # On garde dans path un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            path = Path(file["path"])
            # On vérifie que 'Fichier : ' + path.name figure dans text.
            self.assertIn("Fichier : " + path.name, text)
            # On vérifie que 'Dossier : ' + path.parent.as_posix() figure dans text.
            self.assertIn("Dossier : " + path.parent.as_posix(), text)
        # On vérifie que '3 lignes dans la référence globale' figure dans text.
        self.assertIn("3 lignes dans la référence globale", text)

    def test_defines_and_lists_acquisition_parcel_passage_associations(self):
        # On garde dans report le bilan du contrôle lancé sur les données de ce scénario.
        report = self.run_check()
        # On garde dans text le texte rendu par l’interface pour ce scénario.
        text = self.render_text(report)
        # On vérifie que '2 associations acquisition-parcelle-passage' figure dans text.
        self.assertIn("2 associations acquisition-parcelle-passage", text)
        # On vérifie que 'Une association indique à quelle parcelle et à quel passage' figure dans
        # text.
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "Une association indique à quelle parcelle et à quel passage", text
        )
        # On parcourt report['vineyards'][0]['association_details'] ; association désigne l’élément
        # courant de ce scénario.
        for association in report["vineyards"][0]["association_details"]:
            # On vérifie la présence de association['acquisition'] + ' -> ' + association['parcel'] + '
            # -> '… dans text.
            self.assertIn(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                association["acquisition"]
                + " -> "
                + association["parcel"]
                + " -> "
                + association["passage"],
                # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
                text,
            )

    def test_cli_forced_windows_encoding(self):
        # On lance la commande puis on récupère son résultat ; son code de sortie sera interprété par
        # la suite.
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "import_nas_reconciliation.py"),
                "--check-only",
                "--manifest",
                self.manifest_path,
                "--project-root",
                str(self.root),
            ],
            # On transmet cet environnement au processus plutôt que reprendre implicitement toutes les
            # variables du parent.
            env=dict(os.environ, PYTHONIOENCODING="cp1252"),
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

    def make_empty_association_bundle(self):
        # On crée le dictionnaire vide headers pour y ranger ensuite les éléments par clé.
        headers = {}
        # On parcourt [('nas', self.nas), ('result', self.results)] ; (stage, datasets) désigne
        # l’élément courant de ce scénario.
        for stage, datasets in [("nas", self.nas), ("result", self.results)]:
            # On parcourt ('associations', 'passages') ; kind désigne l’élément courant de ce scénario.
            for kind in ("associations", "passages"):
                # On garde dans headers[stage, kind] une liste matérialisée à partir de
                # datasets[kind][0].
                headers[(stage, kind)] = list(datasets[kind][0])
            # On parcourt les acquisitions dans datasets ; row désigne l’élément courant de ce
            # scénario.
            for row in datasets["acquisitions"]:
                # On complète row avec les valeurs indiquées ; une clé déjà présente prendra la
                # nouvelle valeur fournie.
                row.update(
                    parcel_names_json="[]",
                    parcel_count="0",
                    passage_links_json="[]",
                    passage_link_count="0",
                    passage_outputs_verifiable="False",
                    vitiparcel_created="False",
                )
            # On parcourt ('associations', 'passages') ; kind désigne l’élément courant de ce scénario.
            for kind in ("associations", "passages"):
                # On prépare datasets[kind] comme liste vide ; on la remplira au fil des opérations
                # suivantes.
                datasets[kind] = []
                # On sélectionne dans headers les éléments désignés par (stage, kind) ; columns recevra
                # cette sélection.
                columns = headers[(stage, kind)]
                # On vérifie ce cas avant la suite : kind correspond au texte 'associations'.
                if kind == "associations":
                    # On appelle columns.remove avec 'passage_outputs_verifiable'.
                    columns.remove("passage_outputs_verifiable")
                # On garde dans stream un flux texte en mémoire, utilisable comme un fichier par le
                # lecteur CSV.
                stream = io.StringIO(newline="")
                # On appelle csv.DictWriter(stream, fieldnames=columns).writeheader sans argument
                # positionnel.
                csv.DictWriter(stream, fieldnames=columns).writeheader()
                # On écrit self.output_paths[stage, kind] dans self ; le mode d’ouverture du flux
                # détermine s’il s’agit d’un ajout ou d’un remplacement.
                self.write(
                    self.output_paths[(stage, kind)],
                    stream.getvalue().encode("utf-8-sig"),
                )
            # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant
            # de relancer le contrôle.
            self.sync_csv(stage, "acquisitions")
        # On complète self.manifest['vineyards'][0]['observations']['volumes'] avec les valeurs
        # indiquées ; une clé déjà présente prendra la nouvelle valeur fournie.
        self.manifest["vineyards"][0]["observations"]["volumes"].update(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            associations=0, passages=0
        )
        # On recalcule le manifeste de test après les modifications du scénario.
        self.sync_manifest()

    def test_legacy_empty_associations_accepted_without_writing(self):
        # On appelle self.make_empty_association_bundle sans argument positionnel.
        self.make_empty_association_bundle()
        # On indexe before par str(p) ; chaque clé sera associée à p.read_bytes(). Une même clé ne peut
        # garder qu’une valeur.
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        # On garde dans report le résultat du contrôle de cohérence des sorties du parcours NAS.
        report = checker.check_pipeline(self.root, self.manifest_path)
        # On vérifie que len(report['empty_association_compatibility']) correspond à 2.
        self.assertEqual(len(report["empty_association_compatibility"]), 2)
        # On vérifie que report['vineyards'][0]['associations'] correspond à 0.
        self.assertEqual(report["vineyards"][0]["associations"], 0)
        # On vérifie que report['vineyards'][0]['passages'] correspond à 0.
        self.assertEqual(report["vineyards"][0]["passages"], 0)
        # On vérifie que report['vineyards'][0]['not_verifiable'] correspond à 3.
        self.assertEqual(report["vineyards"][0]["not_verifiable"], 3)
        # On vérifie que before correspond à {str(p): p.read_bytes() for p in self.root.rglob('*') if
        # p.is_file()}.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            before,
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()},
        )

    def test_nonempty_associations_missing_required_boolean_rejected(self):
        # On parcourt ('nas', 'result') ; stage désigne l’élément courant de ce scénario.
        for stage in ("nas", "result"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(stage=stage):
                # On construit rows comme une liste à partir de dict(row), pour chaque row de (self.nas
                # if stage == 'nas' else self.results)['associations'].
                rows = [
                    dict(row)
                    for row in (self.nas if stage == "nas" else self.results)[
                        "associations"
                    ]
                ]
                # On parcourt les lignes ; row désigne l’élément courant de ce scénario.
                for row in rows:
                    # On retire de row l’élément demandé.
                    row.pop("passage_outputs_verifiable")
                # On écrit self.output_paths[stage, 'associations'] dans self ; le mode d’ouverture du
                # flux détermine s’il s’agit d’un ajout ou d’un remplacement.
                self.write(self.output_paths[(stage, "associations")], csv_bytes(rows))
                # On attend checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le
                # test doit échouer.
                with self.assertRaises(checker.ValidationError):
                    # On appelle checker.check_pipeline avec self.root.
                    checker.check_pipeline(self.root, self.manifest_path)
                # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées
                # avant de relancer le contrôle.
                self.sync_csv(stage, "associations")

    def test_empty_associations_with_nonzero_declared_count_rejected(self):
        # On appelle self.make_empty_association_bundle sans argument positionnel.
        self.make_empty_association_bundle()
        # On fixe self.manifest['vineyards'][0]['observations']['volumes']['associ… à 1 pour cette
        # étape du scénario de test.
        self.manifest["vineyards"][0]["observations"]["volumes"]["associations"] = 1
        # On recalcule le manifeste de test après les modifications du scénario.
        self.sync_manifest()
        # On attend checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(checker.ValidationError):
            # On appelle checker.check_pipeline avec self.root.
            checker.check_pipeline(self.root, self.manifest_path)

    def test_empty_associations_with_other_missing_column_rejected(self):
        # On appelle self.make_empty_association_bundle sans argument positionnel.
        self.make_empty_association_bundle()
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.root / self.output_paths[("nas", "associations")]
        # On garde dans text le résultat du remplacement demandé sur
        # path.read_text(encoding='utf-8-sig').
        text = path.read_text(encoding="utf-8-sig").replace("parcel_name,", "")
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_text(text, encoding="utf-8-sig")
        # On attend checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(checker.ValidationError):
            # On appelle checker.check_pipeline avec self.root.
            checker.check_pipeline(self.root, self.manifest_path)

    def test_empty_associations_with_acquisition_links_rejected(self):
        # On appelle self.make_empty_association_bundle sans argument positionnel.
        self.make_empty_association_bundle()
        # On récupère self.nas['acquisitions'][0] et on le garde dans row pour la suite.
        row = self.nas["acquisitions"][0]
        # On complète row avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle valeur
        # fournie.
        row.update(
            parcel_names_json='["P1"]',
            parcel_count="1",
            passage_links_json='[{"parcel_name":"P1","passage_name":"P1_2026-08-11"}]',
            passage_link_count="1",
        )
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("nas", "acquisitions")
        # On attend checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(checker.ValidationError):
            # On appelle checker.check_pipeline avec self.root.
            checker.check_pipeline(self.root, self.manifest_path)

    def test_parcel_identified_without_passage_is_valid_and_preserved(self):
        # On appelle self.make_empty_association_bundle sans argument positionnel.
        self.make_empty_association_bundle()
        # On parcourt [('nas', self.nas), ('result', self.results)] ; (stage, datasets) désigne
        # l’élément courant de ce scénario.
        for stage, datasets in [("nas", self.nas), ("result", self.results)]:
            # On complète datasets['acquisitions'][0] avec les valeurs indiquées ; une clé déjà
            # présente prendra la nouvelle valeur fournie.
            datasets["acquisitions"][0].update(
                parcel_names_json='["P1"]', parcel_count="1"
            )
            # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant
            # de relancer le contrôle.
            self.sync_csv(stage, "acquisitions")
        # On garde dans report le résultat du contrôle de cohérence des sorties du parcours NAS.
        report = checker.check_pipeline(self.root, self.manifest_path)
        # On vérifie que report['vineyards'][0]['associations'] correspond à 0.
        self.assertEqual(report["vineyards"][0]["associations"], 0)
        # On vérifie que report['vineyards'][0]['passages'] correspond à 0.
        self.assertEqual(report["vineyards"][0]["passages"], 0)
        # On vérifie que report['vineyards'][0]['not_verifiable'] correspond à 3.
        self.assertEqual(report["vineyards"][0]["not_verifiable"], 3)

    def test_association_parcel_outside_declared_parcels_rejected(self):
        # On parcourt [('nas', self.nas), ('result', self.results)] ; (stage, datasets) désigne
        # l’élément courant de ce scénario.
        for stage, datasets in [("nas", self.nas), ("result", self.results)]:
            # On complète datasets['acquisitions'][0] avec les valeurs indiquées ; une clé déjà
            # présente prendra la nouvelle valeur fournie.
            datasets["acquisitions"][0].update(
                parcel_names_json='["OtherParcel"]', parcel_count="1"
            )
            # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant
            # de relancer le contrôle.
            self.sync_csv(stage, "acquisitions")
        # On attend checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(checker.ValidationError):
            # On appelle checker.check_pipeline avec self.root.
            checker.check_pipeline(self.root, self.manifest_path)

    def make_recorded_mapping_gap(self):
        # On parcourt [('nas', self.nas), ('result', self.results)] ; (stage, datasets) désigne
        # l’élément courant de ce scénario.
        for stage, datasets in [("nas", self.nas), ("result", self.results)]:
            # On complète datasets['acquisitions'][0] avec les valeurs indiquées ; une clé déjà
            # présente prendra la nouvelle valeur fournie.
            datasets["acquisitions"][0].update(
                parcel_names_json='["OtherParcel"]',
                parcel_count="1",
                parcel_mapping_consistent="False",
            )
            # On parcourt les associations entre acquisitions et passages dans datasets ; link désigne
            # l’élément courant de ce scénario.
            for link in datasets["associations"]:
                # On choisit la valeur de link['parcel_mapping_consistent'] selon ce test :
                # l’identifiant normalisé de l’acquisition dans link correspond à l’identifiant
                # normalisé de l’acquisition dans datasets['acquisitions'][0]. Les deux résultats
                # possibles restent définis explicitement ici.
                link["parcel_mapping_consistent"] = (
                    "False"
                    if link["acquisition_id_normalise"]
                    == datasets["acquisitions"][0]["acquisition_id_normalise"]
                    else "True"
                )
            # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant
            # de relancer le contrôle.
            self.sync_csv(stage, "acquisitions")
            # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant
            # de relancer le contrôle.
            self.sync_csv(stage, "associations")

    def test_explicit_source_mapping_gap_preserved_and_reported(self):
        # On appelle self.make_recorded_mapping_gap sans argument positionnel.
        self.make_recorded_mapping_gap()
        # On indexe before par str(p) ; chaque clé sera associée à p.read_bytes(). Une même clé ne peut
        # garder qu’une valeur.
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        # On garde dans report le résultat du contrôle de cohérence des sorties du parcours NAS.
        report = checker.check_pipeline(self.root, self.manifest_path)
        # On récupère report['vineyards'][0]['recorded_mapping_gaps'] et on le garde dans gaps pour la
        # suite.
        gaps = report["vineyards"][0]["recorded_mapping_gaps"]
        # On vérifie que len(gaps) correspond à 1.
        self.assertEqual(len(gaps), 1)
        # On vérifie que gaps[0]['parcel_mapping'] correspond à ['OtherParcel'].
        self.assertEqual(gaps[0]["parcel_mapping"], ["OtherParcel"])
        # On vérifie que gaps[0]['outside_parcels'] correspond à ['P1'].
        self.assertEqual(gaps[0]["outside_parcels"], ["P1"])
        # On vérifie que before correspond à {str(p): p.read_bytes() for p in self.root.rglob('*') if
        # p.is_file()}.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            before,
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()},
        )

    def test_mapping_gap_claimed_consistent_at_acquisition_rejected(self):
        # On appelle self.make_recorded_mapping_gap sans argument positionnel.
        self.make_recorded_mapping_gap()
        # On utilise ce texte pour self.nas['acquisitions'][0]['parcel_mapping_consistent'] ; il ne
        # dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.nas["acquisitions"][0]["parcel_mapping_consistent"] = "True"
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("nas", "acquisitions")
        # On attend checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(checker.ValidationError):
            # On appelle checker.check_pipeline avec self.root.
            checker.check_pipeline(self.root, self.manifest_path)

    def test_mapping_gap_claimed_consistent_at_association_rejected(self):
        # On appelle self.make_recorded_mapping_gap sans argument positionnel.
        self.make_recorded_mapping_gap()
        # On utilise ce texte pour self.nas['associations'][0]['parcel_mapping_consistent'] ; il ne
        # dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.nas["associations"][0]["parcel_mapping_consistent"] = "True"
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("nas", "associations")
        # On attend checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(checker.ValidationError):
            # On appelle checker.check_pipeline avec self.root.
            checker.check_pipeline(self.root, self.manifest_path)

    def test_mapping_gap_flag_missing_or_unknown_rejected(self):
        # On appelle self.make_recorded_mapping_gap sans argument positionnel.
        self.make_recorded_mapping_gap()
        # On parcourt ['', 'unknown'] ; value désigne l’élément courant de ce scénario.
        for value in ["", "unknown"]:
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(value=value):
                # On garde la valeur reçue sous le nom
                # self.nas['associations'][0]['parcel_mapping_consistent'] ; cette affectation ne copie
                # pas à elle seule un objet mutable.
                self.nas["associations"][0]["parcel_mapping_consistent"] = value
                # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées
                # avant de relancer le contrôle.
                self.sync_csv("nas", "associations")
                # On attend checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le
                # test doit échouer.
                with self.assertRaises(checker.ValidationError):
                    # On appelle checker.check_pipeline avec self.root.
                    checker.check_pipeline(self.root, self.manifest_path)

    def test_mapping_gap_altered_in_reconciliation_rejected(self):
        # On appelle self.make_recorded_mapping_gap sans argument positionnel.
        self.make_recorded_mapping_gap()
        # On utilise ce texte pour self.results['associations'][0]['parcel_mapping_consistent'] ; il ne
        # dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.results["associations"][0]["parcel_mapping_consistent"] = "True"
        # On remet les fichiers CSV de cette fixture en cohérence avec ses données modifiées avant de
        # relancer le contrôle.
        self.sync_csv("result", "associations")
        # On attend checker.ValidationError dans ce bloc ; si aucune erreur n’est levée, le test doit
        # échouer.
        with self.assertRaises(checker.ValidationError):
            # On appelle checker.check_pipeline avec self.root.
            checker.check_pipeline(self.root, self.manifest_path)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
