# Lecture du fichier — Tests de tracking versioning.
#

"""Tests synthetiques : Excel temporaires, aucun NAS ni base PostgreSQL."""

# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles redirect_stdout depuis contextlib, pour les appels de ce fichier.
from contextlib import redirect_stdout
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd
# On importe yaml. Ce module sera utilisé par les opérations de ce fichier.
import yaml

# On rend disponibles reader depuis suivi_traitements_post_saison.ingestion, pour les appels de ce
# fichier.
from suivi_traitements_post_saison.ingestion import excel_reader as reader
# On rend disponibles versioning depuis suivi_traitements_post_saison.ingestion, pour les appels de ce
# fichier.
from suivi_traitements_post_saison.ingestion import tracking_versioning as versioning


class TestTrackingVersioning(unittest.TestCase):
    def setUp(self):
        # On garde dans self.temp un dossier temporaire distinct des données du projet.
        self.temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(self.temp.name)
        # On assemble les morceaux du chemin self.input avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.input = self.root / "data/01_incoming/suivi_acquisitions"
        # On prépare le dossier self.input avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        self.input.mkdir(parents=True)
        # On prépare le dossier self.root / 'config' avec les règles de création indiquées ; aucun
        # résultat métier n’est encore produit par cette création.
        (self.root / "config").mkdir()
        # On assemble les morceaux du chemin self.config avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.config = self.root / "config/tracking_files.yml"
        # On regroupe dans self.settings ces champs nommés ; on pourra les retrouver par leur clé
        # plutôt que par leur position.
        self.settings = {
            # On associe la clé 'target_sheet' à cette valeur dans les données de ce scénario.
            "target_sheet": "Suivi_traitement",
            # On associe la clé 'required_columns' à cette valeur dans les données de ce scénario.
            "required_columns": ["Vineyard", "Acquisition_ID"],
            # On associe la clé 'optional_columns' à cette valeur dans les données de ce scénario.
            "optional_columns": [
                "Commentaires",
                "Problématique",
                "Statut_Resolution",
                "Annotation_rangs",
                "Construction_JSON_Correction",
                "Traitement_visuel_images",
                "Segmentation_images",
                "VitiMap",
                "VitiParcel",
                "Parcel_ID",
                "Date",
            ],
            # On associe la clé 'test_search_columns' à cette valeur dans les données de ce scénario.
            "test_search_columns": ["Parcel_ID", "Commentaires", "Problématique"],
            # On associe la clé 'technical_step_columns' à cette valeur dans les données de ce
            # scénario.
            "technical_step_columns": [
                "Annotation_rangs",
                "Construction_JSON_Correction",
                "Traitement_visuel_images",
                "Segmentation_images",
                "VitiMap",
                "VitiParcel",
            ],
            # On associe la clé 'waiting_values' à cette valeur dans les données de ce scénario.
            "waiting_values": ["en attente"],
            # On associe la clé 'review_values' à cette valeur dans les données de ce scénario.
            "review_values": ["autre"],
        }
        # On écrit le contenu préparé dans self.config ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.config.write_text(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            yaml.safe_dump({"tracking_settings": self.settings}), encoding="utf-8"
        )
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha")
        # On appelle self.excel avec 'Beta'.
        self.excel("Beta")
        # On assemble les morceaux du chemin self.out avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.out = self.root / "data/03_normalized/suivi_acquisitions_normalises"
        # On assemble les morceaux du chemin self.state avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.state = self.root / "state/excel_ingestion"

    def excel(
        self,
        name,
        comment="",
        suffix="LEFT",
        timestamp="2026-06-04T10-00-30",
        extras=None,
    ):
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.input / f"Suivi_acquisitions_{name}_2026.xlsx"
        # On rassemble dans rows les 1 éléments explicitement indiqués pour ce cas d’essai.
        rows = [
            {
                # On renseigne le domaine concerné sous la clé 'Vineyard'.
                "Vineyard": name,
                # On associe la clé 'Acquisition_ID' à cette valeur dans les données de ce scénario.
                "Acquisition_ID": f"C01_V1_{timestamp}_{suffix}",
                # On associe la clé 'Commentaires' à cette valeur dans les données de ce scénario.
                "Commentaires": comment,
            }
        ]
        # Cette branche traite le cas où extras est évalué comme vrai.
        if extras:
            # On ajoute extras à rows et on conserve ce nouvel état pour la suite.
            rows += extras
        # On appelle pd.DataFrame(rows).to_excel avec path.
        pd.DataFrame(rows).to_excel(path, sheet_name="Suivi_traitement", index=False)
        # On remet le chemin de travail à l’appelant ; les étapes suivantes de cette fonction ne sont
        # plus parcourues.
        return path

    # On lit les suivis du périmètre demandé et on prépare leurs versions et leur publication.
    def run_ingestion(self, names=None, all=False):
        # On utilise redirect_stdout(io.StringIO()) dans son contexte de gestion ; les opérations de
        # sortie sont exécutées en quittant le bloc.
        with redirect_stdout(io.StringIO()):
            # On fournit à l’appelant la valeur renvoyée par versioning.run_ingestion.
            return versioning.run_ingestion(self.root, names, all)

    def registry(self):
        # On fournit à l’appelant les objets Python décodés depuis le JSON fourni.
        return json.loads((self.state / "current.json").read_text(encoding="utf-8"))

    def initialize(self):
        # On fournit à l’appelant la valeur renvoyée par self.run_ingestion.
        return self.run_ingestion(all=True)

    def test_initialization_archives_and_publishes_both_vineyards(self):
        # On indexe sources par p ; chaque clé sera associée à p.read_bytes(). Une même clé ne peut
        # garder qu’une valeur.
        sources = {p: p.read_bytes() for p in self.input.glob("*.xlsx")}
        # On garde dans result la valeur renvoyée par self.initialize.
        result = self.initialize()
        # On vérifie que result['status'] correspond à 'success'.
        self.assertEqual(result["status"], "success")
        # On garde dans reg l’état du registre de versions utilisé dans ce test.
        reg = self.registry()
        # On vérifie que set(reg['versions']) correspond à {'alpha', 'beta'}.
        self.assertEqual(set(reg["versions"]), {"alpha", "beta"})
        # On parcourt reg['versions'].items() ; (key, entry) désigne l’élément courant de ce scénario.
        for key, entry in reg["versions"].items():
            # On garde dans m la valeur renvoyée par versioning.verify_version.
            m = versioning.verify_version(self.root, entry)
            # On vérifie que m['normalized_rows'] correspond à 1.
            self.assertEqual(m["normalized_rows"], 1)
            # On attend que (self.root / m['artifacts']['source']['path']).exists() soit évalué comme
            # vrai pour ce cas de test.
            self.assertTrue((self.root / m["artifacts"]["source"]["path"]).exists())
            # On attend que (self.out / f"{entry['vineyard']}_nettoye.csv").exists() soit évalué comme
            # vrai pour ce cas de test.
            self.assertTrue((self.out / f"{entry['vineyard']}_nettoye.csv").exists())
        # On parcourt sources.items() ; (p, data) désigne l’élément courant de ce scénario.
        for p, data in sources.items():
            # On vérifie que p.read_bytes() correspond à data.
            self.assertEqual(p.read_bytes(), data)
        # On vérifie que len(pd.read_csv(self.out / 'toutes_acquisitions_normalisees.csv')) correspond
        # à 2.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            len(pd.read_csv(self.out / "toutes_acquisitions_normalisees.csv")), 2
        )

    def test_first_partial_selection_rejected_preserves_legacy_outputs(self):
        # On prépare le dossier self.out avec les règles de création indiquées ; aucun résultat métier
        # n’est encore produit par cette création.
        self.out.mkdir(parents=True)
        # On assemble les morceaux du chemin legacy avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        legacy = self.out / "toutes_acquisitions_normalisees.csv"
        # On écrit le contenu préparé dans legacy ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        legacy.write_bytes(b"legacy")
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "Premiere initialisation"):
            # On appelle self.run_ingestion avec ['Alpha'].
            self.run_ingestion(["Alpha"])
        # On vérifie que legacy.read_bytes() correspond à b'legacy'.
        self.assertEqual(legacy.read_bytes(), b"legacy")
        # On attend que (self.state / 'current.json').exists() soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse((self.state / "current.json").exists())

    def test_unchanged_source_keeps_version_ingestion_date_and_publication(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans before l’état du registre de versions utilisé dans ce test.
        before = self.registry()
        # On garde dans csv_before les octets lus depuis self.out /
        # 'toutes_acquisitions_normalisees.csv', avant toute conversion en texte. Les contrôles de
        # contenu pourront ainsi repartir de cette lecture.
        csv_before = (self.out / "toutes_acquisitions_normalisees.csv").read_bytes()
        # On remplace temporairement reader dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(
            reader, "process_excel_file", wraps=reader.process_excel_file
        ) as process:
            # On garde dans result la valeur renvoyée par self.run_ingestion.
            result = self.run_ingestion(["Alpha"])
        # On vérifie que result['status'] correspond à 'unchanged'.
        self.assertEqual(result["status"], "unchanged")
        # On vérifie que process n’a pas été appelé dans ce scénario.
        process.assert_not_called()
        # On vérifie que self.registry() correspond à before.
        self.assertEqual(self.registry(), before)
        # On vérifie que (self.out / 'toutes_acquisitions_normalisees.csv').read_bytes() correspond à
        # csv_before.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (self.out / "toutes_acquisitions_normalisees.csv").read_bytes(), csv_before
        )

    def test_partial_update_keeps_other_version_and_old_snapshots(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans before l’état du registre de versions utilisé dans ce test.
        before = self.registry()
        # On assemble les morceaux du chemin old avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        old = self.root / before["reference"]["path"]
        # On garde dans old_bytes les octets lus depuis old, avant toute conversion en texte. Les
        # contrôles de contenu pourront ainsi repartir de cette lecture.
        old_bytes = old.read_bytes()
        # On assemble les morceaux du chemin old_alpha avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        old_alpha = self.root / before["versions"]["alpha"]["normalized_path"]
        # On garde dans old_alpha_bytes les octets originaux de old_alpha, sans conversion en texte.
        old_alpha_bytes = old_alpha.read_bytes()
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="Nouveau commentaire")
        # On appelle self.run_ingestion avec ['Alpha'].
        self.run_ingestion(["Alpha"])
        # On garde dans after l’état du registre de versions utilisé dans ce test.
        after = self.registry()
        # On vérifie que before['versions']['alpha']['version_id'] diffère de
        # after['versions']['alpha']['version_id'].
        self.assertNotEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            before["versions"]["alpha"]["version_id"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            after["versions"]["alpha"]["version_id"],
        )
        # On vérifie que before['versions']['beta'] correspond à after['versions']['beta'].
        self.assertEqual(before["versions"]["beta"], after["versions"]["beta"])
        # On vérifie que old.read_bytes() correspond à old_bytes.
        self.assertEqual(old.read_bytes(), old_bytes)
        # On vérifie que old_alpha.read_bytes() correspond à old_alpha_bytes.
        self.assertEqual(old_alpha.read_bytes(), old_alpha_bytes)
        # On garde dans current la valeur renvoyée par pd.read_csv.
        current = pd.read_csv(self.out / "toutes_acquisitions_normalisees.csv")
        # On vérifie que set(current['Vineyard']) correspond à {'Alpha', 'Beta'}.
        self.assertEqual(set(current["Vineyard"]), {"Alpha", "Beta"})
        # On vérifie que str(current.loc[current.Vineyard.eq('Beta'), 'ingested_at'].iloc[0])
        # correspond à before['versions']['beta']['ingested_at'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            str(current.loc[current.Vineyard.eq("Beta"), "ingested_at"].iloc[0]),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            before["versions"]["beta"]["ingested_at"],
        )

    def test_case_insensitive_selection_deduplicated(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="modifie")
        # On garde dans result la valeur renvoyée par self.run_ingestion.
        result = self.run_ingestion(["alpha", "ALPHA"])
        # On vérifie que len(result['vineyards']) correspond à 1.
        self.assertEqual(len(result["vineyards"]), 1)

    def test_configuration_change_creates_new_selected_version(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans before l’état du registre de versions utilisé dans ce test.
        before = self.registry()
        # On ajoute 'pause' à la fin de self.settings['waiting_values'] ; les éléments précédents
        # restent conservés.
        self.settings["waiting_values"].append("pause")
        # On écrit le contenu préparé dans self.config ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        self.config.write_text(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            yaml.safe_dump({"tracking_settings": self.settings}), encoding="utf-8"
        )
        # On appelle self.run_ingestion avec ['Alpha'].
        self.run_ingestion(["Alpha"])
        # On garde dans after l’état du registre de versions utilisé dans ce test.
        after = self.registry()
        # On vérifie que before['versions']['alpha']['version_id'] diffère de
        # after['versions']['alpha']['version_id'].
        self.assertNotEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            before["versions"]["alpha"]["version_id"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            after["versions"]["alpha"]["version_id"],
        )
        # On vérifie que before['versions']['beta'] correspond à after['versions']['beta'].
        self.assertEqual(before["versions"]["beta"], after["versions"]["beta"])

    def test_code_identity_change_creates_new_version(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans before l’état du registre de versions utilisé dans ce test.
        before = self.registry()
        # On garde versioning.code_identity sous le nom original ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        original = versioning.code_identity

        def changed(data):
            # On garde dans identity la valeur renvoyée par original.
            identity = original(data)
            # On utilise ce texte pour identity['reader_sha256'] ; il ne dépend pas d’une valeur
            # récupérée ailleurs à cet endroit.
            identity["reader_sha256"] = "new-code"
            # On remet les éléments d’identité du lot à l’appelant ; les étapes suivantes de cette
            # fonction ne sont plus parcourues.
            return identity

        # On remplace temporairement versioning dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.object(versioning, "code_identity", side_effect=changed):
            # On appelle self.run_ingestion avec ['Alpha'].
            self.run_ingestion(["Alpha"])
        # On vérifie que self.registry()['versions']['alpha']['version_id'] diffère de
        # before['versions']['alpha']['version_id'].
        self.assertNotEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            self.registry()["versions"]["alpha"]["version_id"],
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            before["versions"]["alpha"]["version_id"],
        )

    def test_failed_partial_ingestion_preserves_registry_and_global(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans before les octets lus depuis self.state / 'current.json', avant toute
        # conversion en texte. Les contrôles de contenu pourront ainsi repartir de cette lecture.
        before = (self.state / "current.json").read_bytes()
        # On garde dans global_before les octets originaux de self.out /
        # 'toutes_acquisitions_normalisees.csv', sans conversion en texte.
        global_before = (self.out / "toutes_acquisitions_normalisees.csv").read_bytes()
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="changed")
        # On remplace temporairement reader dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(
            # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
            # suivre une fonction de test.
            reader, "process_excel_file", side_effect=ValueError("synthetic failure")
        ):
            # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si
            # aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(ValueError, "Publication annulee"):
                # On appelle self.run_ingestion avec ['Alpha'].
                self.run_ingestion(["Alpha"])
        # On vérifie que (self.state / 'current.json').read_bytes() correspond à before.
        self.assertEqual((self.state / "current.json").read_bytes(), before)
        # On vérifie que (self.out / 'toutes_acquisitions_normalisees.csv').read_bytes() correspond à
        # global_before.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (self.out / "toutes_acquisitions_normalisees.csv").read_bytes(),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            global_before,
        )
        # On garde dans runs une liste matérialisée à partir de (self.root /
        # 'data/03_normalized/excel_ingestion_runs').glob('*/manifest.….
        runs = list(
            (self.root / "data/03_normalized/excel_ingestion_runs").glob(
                "*/manifest.json"
            )
        )
        # On attend que any((json.loads(p.read_text())['status'] == 'failed' for p in runs)) soit
        # évalué comme vrai pour ce cas de test.
        self.assertTrue(
            any(json.loads(p.read_text())["status"] == "failed" for p in runs)
        )

    def test_initial_batch_failure_publishes_nothing(self):
        # On garde reader.process_excel_file sous le nom original ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        original = reader.process_excel_file

        def process(path, settings):
            # On vérifie ce cas avant la suite : le texte 'Beta' appartient à path.name.
            if "Beta" in path.name:
                # On interrompt cette branche avec ValueError : 'failure Beta'.
                raise ValueError("failure Beta")
            # On fournit à l’appelant la valeur renvoyée par original.
            return original(path, settings)

        # On remplace temporairement reader dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(reader, "process_excel_file", side_effect=process):
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle self.initialize sans argument positionnel.
                self.initialize()
        # On attend que (self.state / 'current.json').exists() soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse((self.state / "current.json").exists())
        # On attend que (self.out / 'toutes_acquisitions_normalisees.csv').exists() soit évalué comme
        # faux pour ce cas de test.
        self.assertFalse((self.out / "toutes_acquisitions_normalisees.csv").exists())

    def test_multiple_selected_failure_keeps_all_previous_current_versions(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans old l’état du registre de versions utilisé dans ce test.
        old = self.registry()
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="change")
        # On appelle self.excel avec 'Beta'.
        self.excel("Beta", comment="change")
        # On garde reader.process_excel_file sous le nom original ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        original = reader.process_excel_file

        def process(path, settings):
            # On vérifie ce cas avant la suite : le texte 'Beta' appartient à path.name.
            if "Beta" in path.name:
                # On interrompt cette branche avec ValueError : 'failure'.
                raise ValueError("failure")
            # On fournit à l’appelant la valeur renvoyée par original.
            return original(path, settings)

        # On remplace temporairement reader dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(reader, "process_excel_file", side_effect=process):
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle self.run_ingestion avec ['Alpha', 'Beta'].
                self.run_ingestion(["Alpha", "Beta"])
        # On vérifie que self.registry() correspond à old.
        self.assertEqual(self.registry(), old)

    def test_unknown_vineyard_rejected(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "indisponible"):
            # On appelle self.run_ingestion avec ['Gamma'].
            self.run_ingestion(["Gamma"])

    def test_duplicate_source_for_same_vineyard_rejected(self):
        # On assemble les morceaux du chemin duplicate avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        duplicate = self.input / "Suivi_acquisition_Alpha_2026.xlsx"
        # On écrit le contenu préparé dans duplicate ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        duplicate.write_bytes(
            (self.input / "Suivi_acquisitions_Alpha_2026.xlsx").read_bytes()
        )
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "Plusieurs Excel"):
            # On appelle self.initialize sans argument positionnel.
            self.initialize()

    def test_temporary_excel_files_ignored(self):
        # On écrit le contenu préparé dans self.input / '~$Suivi_acquisitions_Alpha_2026.xlsx' ; cette
        # opération remplace le contenu du fichier s’il existe déjà.
        (self.input / "~$Suivi_acquisitions_Alpha_2026.xlsx").write_bytes(b"not excel")
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On vérifie que len(self.registry()['versions']) correspond à 2.
        self.assertEqual(len(self.registry()["versions"]), 2)

    def test_filename_and_content_mismatch_blocks_publication(self):
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.input / "Suivi_acquisitions_Alpha_2026.xlsx"
        # On appelle pd.DataFrame([{'Vineyard': 'Gamma', 'Acquisition_ID':
        # 'C01_V1_2026-06-04T10-00-30'}]).to_excel avec path.
        pd.DataFrame(
            [{"Vineyard": "Gamma", "Acquisition_ID": "C01_V1_2026-06-04T10-00-30"}]
        ).to_excel(path, sheet_name="Suivi_traitement", index=False)
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.initialize sans argument positionnel.
            self.initialize()
        # On attend que (self.state / 'current.json').exists() soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse((self.state / "current.json").exists())

    def test_zero_normalized_rows_blocks_publication(self):
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.input / "Suivi_acquisitions_Alpha_2026.xlsx"
        # On appelle pd.DataFrame([{'Vineyard': 'Alpha', 'Acquisition_ID': None, 'Commentaires': 'Sans
        # ID'}]).to_excel avec path.
        pd.DataFrame(
            [{"Vineyard": "Alpha", "Acquisition_ID": None, "Commentaires": "Sans ID"}]
        ).to_excel(path, sheet_name="Suivi_traitement", index=False)
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.initialize sans argument positionnel.
            self.initialize()
        # On attend que (self.state / 'current.json').exists() soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse((self.state / "current.json").exists())

    def test_rejections_archived_and_not_deleted_on_next_version(self):
        # On appelle self.excel avec 'Alpha'.
        self.excel(
            "Alpha",
            extras=[
                {"Vineyard": "Alpha", "Acquisition_ID": None, "Commentaires": "sans ID"}
            ],
        )
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans old_manifest la valeur renvoyée par versioning.verify_version.
        old_manifest = versioning.verify_version(
            self.root, self.registry()["versions"]["alpha"]
        )
        # On assemble les morceaux du chemin rejected_path avec l’opérateur / de pathlib ; aucun
        # fichier n’est créé par cette construction.
        rejected_path = self.root / old_manifest["artifacts"]["rejected"]["path"]
        # On garde dans before les octets lus depuis rejected_path, avant toute conversion en texte.
        # Les contrôles de contenu pourront ainsi repartir de cette lecture.
        before = rejected_path.read_bytes()
        # On vérifie que old_manifest['rejected_rows'] correspond à 1.
        self.assertEqual(old_manifest["rejected_rows"], 1)
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="version sans rejet")
        # On appelle self.run_ingestion avec ['Alpha'].
        self.run_ingestion(["Alpha"])
        # On vérifie que rejected_path.read_bytes() correspond à before.
        self.assertEqual(rejected_path.read_bytes(), before)
        # On garde dans new_manifest la valeur renvoyée par versioning.verify_version.
        new_manifest = versioning.verify_version(
            self.root, self.registry()["versions"]["alpha"]
        )
        # On vérifie que new_manifest['rejected_rows'] correspond à 0.
        self.assertEqual(new_manifest["rejected_rows"], 0)

    def test_invalid_timestamp_preserved_and_flagged(self):
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", timestamp="2026-06-04T10-00-66")
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans frame la valeur renvoyée par versioning.frame_from_entry.
        frame = versioning.frame_from_entry(
            self.root, self.registry()["versions"]["alpha"]
        )
        # On vérifie que '10-00-66' figure dans frame.iloc[0]['Acquisition_ID_normalise'].
        self.assertIn("10-00-66", frame.iloc[0]["Acquisition_ID_normalise"])
        # On vérifie que frame.iloc[0]['Acquisition_timestamp_valid'] correspond à 'False'.
        self.assertEqual(frame.iloc[0]["Acquisition_timestamp_valid"], "False")
        # On vérifie que frame.iloc[0]['Acquisition_timestamp_issue'] correspond à 'Secondes hors
        # plage'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            frame.iloc[0]["Acquisition_timestamp_issue"], "Secondes hors plage"
        )

    def test_business_rules_unchanged(self):
        # On appelle self.excel avec 'Alpha'.
        self.excel(
            "Alpha",
            comment="test",
            extras=[
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "Alpha",
                    # On associe la clé 'Acquisition_ID' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_ID": "C01_V1_2026-06-04T11-00-30",
                    # On associe la clé 'VitiMap' à cette valeur dans les données de ce scénario.
                    "VitiMap": "en attente",
                },
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "Alpha",
                    # On associe la clé 'Acquisition_ID' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_ID": "C01_V1_2026-06-04T12-00-30",
                    # On associe la clé 'VitiMap' à cette valeur dans les données de ce scénario.
                    "VitiMap": "autre",
                },
            ],
        )
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans frame la valeur renvoyée par versioning.frame_from_entry.
        frame = versioning.frame_from_entry(
            self.root, self.registry()["versions"]["alpha"]
        )
        # On vérifie que list(frame['Périmètre']) correspond à ['Test', 'Bloqué', 'Bloqué'].
        self.assertEqual(list(frame["Périmètre"]), ["Test", "Bloqué", "Bloqué"])
        # On vérifie que list(frame['Statut_pipeline']) correspond à ['Hors périmètre', 'En attente',
        # 'Autre'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            list(frame["Statut_pipeline"]), ["Hors périmètre", "En attente", "Autre"]
        )

    def test_corrupted_version_rejected_before_update(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On récupère self.registry()['versions']['beta'] et on le garde dans entry pour la suite.
        entry = self.registry()["versions"]["beta"]
        # On écrit le contenu préparé dans self.root / entry['normalized_path'] ; cette opération
        # remplace le contenu du fichier s’il existe déjà.
        (self.root / entry["normalized_path"]).write_bytes(b"corrupted")
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "modifie"):
            # On appelle self.run_ingestion avec ['Alpha'].
            self.run_ingestion(["Alpha"])

    def test_modified_compatibility_export_rejected(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On écrit le contenu préparé dans self.out / 'toutes_acquisitions_normalisees.csv' ; cette
        # opération remplace le contenu du fichier s’il existe déjà.
        (self.out / "toutes_acquisitions_normalisees.csv").write_bytes(
            b"changed outside manager"
        )
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "hors du gestionnaire"):
            # On appelle self.run_ingestion avec ['Alpha'].
            self.run_ingestion(["Alpha"])

    def test_existing_lock_blocks_execution(self):
        # On prépare le dossier self.state avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        self.state.mkdir(parents=True)
        # On écrit le contenu préparé dans self.state / 'ingestion.lock' ; cette opération remplace le
        # contenu du fichier s’il existe déjà.
        (self.state / "ingestion.lock").write_text("other process")
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "Verrou"):
            # On appelle self.initialize sans argument positionnel.
            self.initialize()
        # On attend que (self.state / 'ingestion.lock').exists() soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue((self.state / "ingestion.lock").exists())

    def test_pending_publication_blocks_execution(self):
        # On prépare le dossier self.state avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        self.state.mkdir(parents=True)
        # On écrit le contenu préparé dans self.state / 'pending_publication.json' ; cette opération
        # remplace le contenu du fichier s’il existe déjà.
        (self.state / "pending_publication.json").write_text("{}")
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "interrompue"):
            # On appelle self.initialize sans argument positionnel.
            self.initialize()

    def test_publication_write_error_rolls_back_previous_exports(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans before les octets lus depuis self.state / 'current.json', avant toute
        # conversion en texte. Les contrôles de contenu pourront ainsi repartir de cette lecture.
        before = (self.state / "current.json").read_bytes()
        # On garde dans csv_before les octets originaux de self.out /
        # 'toutes_acquisitions_normalisees.csv', sans conversion en texte.
        csv_before = (self.out / "toutes_acquisitions_normalisees.csv").read_bytes()
        # On garde dans alpha_before les octets originaux de self.out / 'Alpha_nettoye.csv', sans
        # conversion en texte.
        alpha_before = (self.out / "Alpha_nettoye.csv").read_bytes()
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="changed")
        # On garde versioning.atomic_write sous le nom original ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        original = versioning.atomic_write
        # On initialise failed à False ; les branches suivantes pourront modifier cet état.
        failed = False

        def write(path, data):
            nonlocal failed
            # Cette branche traite le cas où le chemin de travail correspond à self.out /
            # 'Alpha_nettoye.csv' et la condition failed n’est pas remplie.
            if path == self.out / "Alpha_nettoye.csv" and not failed:
                # On initialise failed à True ; les branches suivantes pourront modifier cet état.
                failed = True
                # On interrompt cette branche avec OSError : 'synthetic write error'.
                raise OSError("synthetic write error")
            # On fournit à l’appelant la valeur renvoyée par original.
            return original(path, data)

        # On remplace temporairement versioning dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.object(versioning, "atomic_write", side_effect=write):
            # On attend OSError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(OSError):
                # On appelle self.run_ingestion avec ['Alpha'].
                self.run_ingestion(["Alpha"])
        # On vérifie que (self.state / 'current.json').read_bytes() correspond à before.
        self.assertEqual((self.state / "current.json").read_bytes(), before)
        # On vérifie que (self.out / 'toutes_acquisitions_normalisees.csv').read_bytes() correspond à
        # csv_before.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (self.out / "toutes_acquisitions_normalisees.csv").read_bytes(), csv_before
        )
        # On vérifie que (self.out / 'Alpha_nettoye.csv').read_bytes() correspond à alpha_before.
        self.assertEqual((self.out / "Alpha_nettoye.csv").read_bytes(), alpha_before)
        # On attend que (self.state / 'pending_publication.json').exists() soit évalué comme faux pour
        # ce cas de test.
        self.assertFalse((self.state / "pending_publication.json").exists())

    def test_missing_current_vineyard_source_blocks_all_not_partial(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        (self.input / "Suivi_acquisitions_Beta_2026.xlsx").unlink()
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "absent"):
            # On appelle self.run_ingestion sans argument positionnel.
            self.run_ingestion(all=True)
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="changed")
        # On appelle self.run_ingestion avec ['Alpha'].
        self.run_ingestion(["Alpha"])
        # On vérifie que 'beta' figure dans self.registry()['versions'].
        self.assertIn("beta", self.registry()["versions"])

    def test_unchanged_vineyard_export_not_rewritten(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On assemble les morceaux du chemin other avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        other = self.out / "Beta_nettoye.csv"
        # On rassemble dans before les 2 éléments explicitement indiqués pour ce cas d’essai.
        before = (other.read_bytes(), other.stat().st_mtime_ns)
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="changed")
        # On appelle self.run_ingestion avec ['Alpha'].
        self.run_ingestion(["Alpha"])
        # On vérifie que (other.read_bytes(), other.stat().st_mtime_ns) correspond à before.
        self.assertEqual((other.read_bytes(), other.stat().st_mtime_ns), before)

    def test_unrelated_invalid_incoming_does_not_block_targeted_update(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On écrit le contenu préparé dans self.input / 'unrelated.xlsx' ; cette opération remplace le
        # contenu du fichier s’il existe déjà.
        (self.input / "unrelated.xlsx").write_bytes(b"not an excel")
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="changed")
        # On appelle self.run_ingestion avec ['Alpha'].
        self.run_ingestion(["Alpha"])
        # On vérifie que set(self.registry()['versions']) correspond à {'alpha', 'beta'}.
        self.assertEqual(set(self.registry()["versions"]), {"alpha", "beta"})

    def test_failed_source_is_archived_with_failure_trace(self):
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", extras=[{"Vineyard": "Alpha", "Acquisition_ID": None}])
        # On assemble les morceaux du chemin source avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        source = self.input / "Suivi_acquisitions_Alpha_2026.xlsx"
        # On garde dans source_bytes les octets lus depuis source, avant toute conversion en texte.
        # Les contrôles de contenu pourront ainsi repartir de cette lecture.
        source_bytes = source.read_bytes()
        # On garde reader.process_excel_file sous le nom original ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        original = reader.process_excel_file

        def process(path, settings):
            # On vérifie ce cas avant la suite : le texte 'Alpha' appartient à path.name.
            if "Alpha" in path.name:
                # On interrompt cette branche avec ValueError : 'synthetic failure'.
                raise ValueError("synthetic failure")
            # On fournit à l’appelant la valeur renvoyée par original.
            return original(path, settings)

        # On remplace temporairement reader dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(reader, "process_excel_file", side_effect=process):
            # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
            with self.assertRaises(ValueError):
                # On appelle self.initialize sans argument positionnel.
                self.initialize()
        # On garde dans failures une liste matérialisée à partir de (self.out /
        # 'versions').glob('*/*/failure.json').
        failures = list((self.out / "versions").glob("*/*/failure.json"))
        # On vérifie que len(failures) correspond à 1.
        self.assertEqual(len(failures), 1)
        # On garde dans failure les objets Python décodés depuis le JSON fourni.
        failure = json.loads(failures[0].read_text())
        # On vérifie que (self.root / failure['source_path']).read_bytes() correspond à source_bytes.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            (self.root / failure["source_path"]).read_bytes(), source_bytes
        )

    def test_cli_runs_from_project_root_with_direct_python_path(self):
        # On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours
        # l’exige.
        import subprocess
        # On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
        import sys

        # On assemble les morceaux du chemin destination avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        destination = self.root / "src/suivi_traitements_post_saison/ingestion"
        # On prépare le dossier destination avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        destination.mkdir(parents=True)
        # On écrit le contenu préparé dans destination / 'excel_reader.py' ; cette opération remplace
        # le contenu du fichier s’il existe déjà.
        (destination / "excel_reader.py").write_bytes(
            Path(reader.__file__).read_bytes()
        )
        # On écrit le contenu préparé dans destination / 'tracking_versioning.py' ; cette opération
        # remplace le contenu du fichier s’il existe déjà.
        (destination / "tracking_versioning.py").write_bytes(
            Path(versioning.__file__).read_bytes()
        )
        # On lance la commande puis on récupère son résultat ; son code de sortie sera interprété par
        # la suite.
        completed = subprocess.run(
            [sys.executable, str(destination / "excel_reader.py"), "--all-vineyards"],
            # On impose le dossier de travail du processus enfant ; les chemins relatifs ne dépendent
            # ainsi pas du terminal de départ.
            cwd=self.root,
            # On choisit de récupérer les sorties du processus en mémoire pour les contrôles qui
            # suivent.
            capture_output=True,
            # On fournit le texte de travail via le paramètre text de cet appel.
            text=True,
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8",
        )
        # On vérifie que completed.returncode correspond à 0.
        self.assertEqual(completed.returncode, 0, completed.stderr)
        # On vérifie que 'INGESTION EXCEL VERSIONNEE' figure dans completed.stdout.
        self.assertIn("INGESTION EXCEL VERSIONNEE", completed.stdout)
        # On vérifie que set(self.registry()['versions']) correspond à {'alpha', 'beta'}.
        self.assertEqual(set(self.registry()["versions"]), {"alpha", "beta"})

    def test_cli_with_windows_pipe_encoding_handles_reader_unicode_output(self):
        # On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
        import os
        # On importe subprocess. On lance et surveille les programmes enfants lorsqu’un parcours
        # l’exige.
        import subprocess
        # On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
        import sys

        # On assemble les morceaux du chemin destination avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        destination = self.root / "src/suivi_traitements_post_saison/ingestion"
        # On prépare le dossier destination avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        destination.mkdir(parents=True)
        # On écrit le contenu préparé dans destination / 'excel_reader.py' ; cette opération remplace
        # le contenu du fichier s’il existe déjà.
        (destination / "excel_reader.py").write_bytes(
            Path(reader.__file__).read_bytes()
        )
        # On écrit le contenu préparé dans destination / 'tracking_versioning.py' ; cette opération
        # remplace le contenu du fichier s’il existe déjà.
        (destination / "tracking_versioning.py").write_bytes(
            Path(versioning.__file__).read_bytes()
        )
        # On garde dans environment une copie de os.environ pour travailler sur cet objet séparément.
        environment = os.environ.copy()
        # On utilise ce texte pour environment['PYTHONIOENCODING'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        environment["PYTHONIOENCODING"] = "cp1252"
        # On lance la commande puis on récupère son résultat ; son code de sortie sera interprété par
        # la suite.
        completed = subprocess.run(
            [sys.executable, str(destination / "excel_reader.py"), "--all-vineyards"],
            # On impose le dossier de travail du processus enfant ; les chemins relatifs ne dépendent
            # ainsi pas du terminal de départ.
            cwd=self.root,
            # On transmet cet environnement au processus plutôt que reprendre implicitement toutes les
            # variables du parent.
            env=environment,
            # On choisit de récupérer les sorties du processus en mémoire pour les contrôles qui
            # suivent.
            capture_output=True,
            # On fournit le texte de travail via le paramètre text de cet appel.
            text=True,
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8",
        )
        # On vérifie que completed.returncode correspond à 0.
        self.assertEqual(completed.returncode, 0, completed.stderr)
        # On vérifie que 'Colonnes facultatives absentes' figure dans completed.stdout.
        self.assertIn("Colonnes facultatives absentes", completed.stdout)
        # On vérifie que 'INGESTION EXCEL VERSIONNEE' figure dans completed.stdout.
        self.assertIn("INGESTION EXCEL VERSIONNEE", completed.stdout)
        # On vérifie que set(self.registry()['versions']) correspond à {'alpha', 'beta'}.
        self.assertEqual(set(self.registry()["versions"]), {"alpha", "beta"})

    def test_consolidated_export_accepted_by_existing_reference_preparer(self):
        # On rend disponibles prepare_excel_reference depuis
        # suivi_traitements_post_saison.reconciliation.excel_tracking_reference, pour les appels de ce
        # fichier.
        from suivi_traitements_post_saison.reconciliation.excel_tracking_reference import (
            prepare_excel_reference,
        )

        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans combined la valeur renvoyée par pd.read_csv.
        combined = pd.read_csv(
            self.out / "toutes_acquisitions_normalisees.csv",
            # On impose les types lus ou construits pour éviter une interprétation automatique non
            # souhaitée.
            dtype="string",
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8-sig",
        )
        # On garde dans prepared la valeur renvoyée par prepare_excel_reference.
        prepared = prepare_excel_reference(combined)
        # On vérifie que len(prepared) correspond à 2.
        self.assertEqual(len(prepared), 2)
        # On vérifie que set(prepared['excel_vineyard']) correspond à {'Alpha', 'Beta'}.
        self.assertEqual(set(prepared["excel_vineyard"]), {"Alpha", "Beta"})

    def test_source_hash_and_ingestion_metadata_match_saved_version(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On parcourt self.registry()['versions'].values() ; entry désigne l’élément courant de ce
        # scénario.
        for entry in self.registry()["versions"].values():
            # On garde dans manifest la valeur renvoyée par versioning.verify_version.
            manifest = versioning.verify_version(self.root, entry)
            # On assemble les morceaux du chemin source avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            source = self.root / manifest["artifacts"]["source"]["path"]
            # On garde dans frame la valeur renvoyée par versioning.frame_from_entry.
            frame = versioning.frame_from_entry(self.root, entry)
            # On vérifie que versioning.digest(source.read_bytes()) correspond à
            # entry['source_sha256'].
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                versioning.digest(source.read_bytes()), entry["source_sha256"]
            )
            # On vérifie que set(frame['source_sha256']) correspond à {entry['source_sha256']}.
            self.assertEqual(set(frame["source_sha256"]), {entry["source_sha256"]})
            # On vérifie que set(frame['excel_reference_version_id']) correspond à
            # {entry['version_id']}.
            self.assertEqual(
                # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
                set(frame["excel_reference_version_id"]), {entry["version_id"]}
            )
            # On vérifie que set(frame['ingested_at']) correspond à {entry['ingested_at']}.
            self.assertEqual(set(frame["ingested_at"]), {entry["ingested_at"]})

    def test_keyboard_interrupt_keeps_previous_publication(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans before l’état du registre de versions utilisé dans ce test.
        before = self.registry()
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="changed")
        # On remplace temporairement reader dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(reader, "process_excel_file", side_effect=KeyboardInterrupt):
            # On attend KeyboardInterrupt dans ce bloc ; si aucune erreur n’est levée, le test doit
            # échouer.
            with self.assertRaises(KeyboardInterrupt):
                # On appelle self.run_ingestion avec ['Alpha'].
                self.run_ingestion(["Alpha"])
        # On vérifie que self.registry() correspond à before.
        self.assertEqual(self.registry(), before)
        # On attend que (self.state / 'ingestion.lock').exists() soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse((self.state / "ingestion.lock").exists())
        # On garde dans runs une liste matérialisée à partir de (self.root /
        # 'data/03_normalized/excel_ingestion_runs').glob('*/manifest.….
        runs = list(
            (self.root / "data/03_normalized/excel_ingestion_runs").glob(
                "*/manifest.json"
            )
        )
        # On attend que any((json.loads(p.read_text())['status'] == 'interrupted' for p in runs)) soit
        # évalué comme vrai pour ce cas de test.
        self.assertTrue(
            any(json.loads(p.read_text())["status"] == "interrupted" for p in runs)
        )

    def test_symlink_source_outside_local_data_rejected(self):
        # On assemble les morceaux du chemin outside avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        outside = self.root / "external.xlsx"
        # On assemble les morceaux du chemin source avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        source = self.input / "Suivi_acquisitions_Alpha_2026.xlsx"
        # On écrit le contenu préparé dans outside ; cette opération remplace le contenu du fichier
        # s’il existe déjà.
        outside.write_bytes(source.read_bytes())
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        source.unlink()
        # On tente ce bloc et on traite séparément les erreurs prévues : (OSError,
        # NotImplementedError).
        try:
            # On appelle source.symlink_to avec outside.
            source.symlink_to(outside)
        except (OSError, NotImplementedError):
            # On appelle self.skipTest avec 'Creation de liens symboliques non autorisee.'.
            self.skipTest("Creation de liens symboliques non autorisee.")
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "hors du dossier data"):
            # On appelle self.initialize sans argument positionnel.
            self.initialize()
        # On attend que (self.state / 'current.json').exists() soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse((self.state / "current.json").exists())

    def test_vineyard_reject_count_and_logical_count_recorded(self):
        # On appelle self.excel avec 'Alpha'.
        self.excel(
            "Alpha",
            extras=[
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "Alpha",
                    # On associe la clé 'Acquisition_ID' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_ID": "C01_V1_2026-06-04T10-00-30_RIGHT",
                },
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "Alpha",
                    # On associe la clé 'Acquisition_ID' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_ID": None,
                    # On associe la clé 'Commentaires' à cette valeur dans les données de ce scénario.
                    "Commentaires": "sans ID",
                },
            ],
        )
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On récupère self.registry()['versions']['alpha'] et on le garde dans entry pour la suite.
        entry = self.registry()["versions"]["alpha"]
        # On vérifie que entry['normalized_rows'] correspond à 2.
        self.assertEqual(entry["normalized_rows"], 2)
        # On vérifie que entry['logical_acquisitions'] correspond à 1.
        self.assertEqual(entry["logical_acquisitions"], 1)
        # On vérifie que entry['rejected_rows'] correspond à 1.
        self.assertEqual(entry["rejected_rows"], 1)

    def test_reporting_failure_after_commit_is_not_labelled_unpublished(self):
        # On appelle self.initialize sans argument positionnel.
        self.initialize()
        # On garde dans before l’état du registre de versions utilisé dans ce test.
        before = self.registry()
        # On appelle self.excel avec 'Alpha'.
        self.excel("Alpha", comment="changed")
        # On garde versioning.atomic_write sous le nom original ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        original = versioning.atomic_write
        # On initialise failed à False ; les branches suivantes pourront modifier cet état.
        failed = False

        def write(path, data):
            nonlocal failed
            # Cette branche traite le cas où path.name correspond au texte 'manifest.json' et
            # b'"status": "success"' appartient aux données en mémoire et la condition failed n’est
            # pas remplie.
            if (
                path.name == "manifest.json"
                # On exige aussi que b'"status": "success"' appartient aux données en mémoire.
                and b'"status": "success"' in data
                # On exige aussi que la condition failed n’est pas remplie.
                and not failed
            ):
                # On initialise failed à True ; les branches suivantes pourront modifier cet état.
                failed = True
                # On interrompt cette branche avec OSError : 'reporting error'.
                raise OSError("reporting error")
            # On fournit à l’appelant la valeur renvoyée par original.
            return original(path, data)

        # On remplace temporairement versioning dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.object(versioning, "atomic_write", side_effect=write):
            # On attend RuntimeError avec un message correspondant au motif indiqué dans ce bloc ; si
            # aucune erreur n’est levée, le test doit échouer.
            with self.assertRaisesRegex(RuntimeError, "deja publiee"):
                # On appelle self.run_ingestion avec ['Alpha'].
                self.run_ingestion(["Alpha"])
        # On vérifie que self.registry()['publication_id'] diffère de before['publication_id'].
        self.assertNotEqual(self.registry()["publication_id"], before["publication_id"])
        # On garde dans manifests une liste matérialisée à partir de (self.root /
        # 'data/03_normalized/excel_ingestion_runs').glob('*/manifest.….
        manifests = list(
            (self.root / "data/03_normalized/excel_ingestion_runs").glob(
                "*/manifest.json"
            )
        )
        # On attend que any((json.loads(p.read_text())['status'] == 'reporting_error_after_publication'
        # for p in manifests)) soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            any(
                json.loads(p.read_text())["status"]
                == "reporting_error_after_publication"
                for p in manifests
            )
        )

    def test_paths_outside_data_rejected(self):
        # On attend ValueError avec un message correspondant au motif indiqué dans ce bloc ; si aucune
        # erreur n’est levée, le test doit échouer.
        with self.assertRaisesRegex(ValueError, "hors"):
            # On appelle versioning.checked_path avec self.root.
            versioning.checked_path(self.root, "../outside.csv")

    def test_cli_no_selection_is_rejected(self):
        # On attend SystemExit dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(SystemExit) as caught:
            # On appelle versioning.main avec [].
            versioning.main([])
        # On vérifie que caught.exception.code correspond à 2.
        self.assertEqual(caught.exception.code, 2)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
