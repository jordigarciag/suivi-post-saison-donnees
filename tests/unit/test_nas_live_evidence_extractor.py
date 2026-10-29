# Lecture du fichier — Tests de nas live evidence extractor.
#

"""Tests de l'extracteur NAS : données synthétiques, aucun accès au NAS réel.

Compatible avec pytest et unittest (bibliothèque standard).
Le cas sans passage est vérifié dans le CSV et dans les affichages.
"""

# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe tempfile. On prépare des fichiers ou dossiers temporaires pour les cas isolés.
import tempfile
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd
# On rend disponibles nas depuis suivi_traitements_post_saison.extraction, pour les appels de ce
# fichier.
from suivi_traitements_post_saison.extraction import nas_live_evidence_extractor as nas


class TestNasLiveEvidenceExtractor(unittest.TestCase):
    def setUp(self):
        # On garde dans self.temp un dossier temporaire distinct des données du projet.
        self.temp = tempfile.TemporaryDirectory()
        # On enregistre cette opération de nettoyage pour qu’elle soit appelée après le test, même si
        # celui-ci échoue.
        self.addCleanup(self.temp.cleanup)
        # On garde dans self.root un objet chemin local ; sa construction seule ne prouve pas que le
        # fichier existe.
        self.root = Path(self.temp.name)
        # On assemble les morceaux du chemin self.raw avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        self.raw = self.root / "brut"
        # On assemble les morceaux du chemin self.processing avec l’opérateur / de pathlib ; aucun
        # fichier n’est créé par cette construction.
        self.processing = self.root / "processing"
        # On utilise ce texte pour self.vineyard ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.vineyard = "VignobleTest"
        # On fixe self.year à 2026 pour cette étape du scénario de test.
        self.year = 2026
        # On utilise ce texte pour self.base ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        self.base = "C01_V1_2026-06-16T12-34-14"
        # On prépare self.acquisition avec cette expression pour l’utiliser dans la suite du
        # traitement.
        self.acquisition = f"{self.vineyard}_{self.base}"
        # On utilise ce texte pour self.passage ; il ne dépend pas d’une valeur récupérée ailleurs à
        # cet endroit.
        self.passage = "PARCELLE_2026-06-16"
        # On calcule ce quotient pour construire self.raw_path.
        self.raw_path = self.raw / self.vineyard / str(self.year) / self.base
        # On assemble les morceaux du chemin self.processing_path avec l’opérateur / de pathlib ; aucun
        # fichier n’est créé par cette construction.
        self.processing_path = (
            self.processing
            / self.vineyard
            / "acquisitions"
            / str(self.year)
            / self.acquisition
        )
        # On assemble les morceaux du chemin self.passage_path avec l’opérateur / de pathlib ; aucun
        # fichier n’est créé par cette construction.
        self.passage_path = (
            self.processing / self.vineyard / "passages" / str(self.year) / self.passage
        )

    def write(self, path, content="preuve synthetique"):
        # On prépare le dossier path.parent avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        path.parent.mkdir(parents=True, exist_ok=True)
        # On écrit le contenu préparé dans path ; cette opération remplace le contenu du fichier s’il
        # existe déjà.
        path.write_text(content, encoding="utf-8")
        # On remet le chemin de travail à l’appelant ; les étapes suivantes de cette fonction ne sont
        # plus parcourues.
        return path

    def write_json(self, path, data):
        # On fournit à l’appelant le fichier de fixture écrit pour cette vérification.
        return self.write(path, json.dumps(data))

    def raw_result(self):
        # On fournit à l’appelant la valeur renvoyée par nas.check_raw_evidence.
        return nas.check_raw_evidence(self.raw, self.vineyard, self.year, self.base)

    def processing_result(self):
        # On fournit à l’appelant la valeur renvoyée par nas.check_processing_evidence.
        return nas.check_processing_evidence(
            self.processing, self.vineyard, self.year, self.acquisition
        )

    def passage_result(self, name=None):
        # On fournit à l’appelant la valeur renvoyée par nas.check_passage_outputs.
        return nas.check_passage_outputs(
            self.processing,
            self.vineyard,
            self.year,
            self.passage if name is None else name,
        )

    def build_result(self, parcel="PARCELLE", passage_parcel="PARCELLE", cache=None):
        # On garde dans row une série pandas avec les valeurs et l’index fournis.
        row = pd.Series(
            {
                # On associe la clé 'Acquisition_ID_base' à cette valeur dans les données de ce
                # scénario.
                "Acquisition_ID_base": self.base,
                # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                # 'Acquisition_ID_normalise'.
                "Acquisition_ID_normalise": self.acquisition,
                # On associe la clé 'Statut_pipeline' à cette valeur dans les données de ce scénario.
                "Statut_pipeline": "Test",
            }
        )
        # On garde dans key la forme de self.acquisition adaptée aux comparaisons sans distinction de
        # casse.
        key = self.acquisition.casefold()
        # On fournit à l’appelant la valeur renvoyée par nas.build_result.
        return nas.build_result(
            row,
            self.raw,
            self.processing,
            self.vineyard,
            self.year,
            {key: [parcel]} if parcel else {},
            {key: [{"parcel_name": passage_parcel, "passage_name": self.passage}]}
            if passage_parcel
            else {},
            cache if cache is not None else {},
            "2026-10-05T08:40:22Z",
        )

    def test_raw_missing_is_not_a_read_error(self):
        # On garde dans result le résultat de contrôle brut préparé par ce test.
        result = self.raw_result()
        # On attend que result['found_in_raw_live'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["found_in_raw_live"])
        # On attend que result['raw_has_full_size_image'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["raw_has_full_size_image"])
        # On vérifie que result['raw_error'] correspond à ''.
        self.assertEqual(result["raw_error"], "")

    def test_raw_folder_without_png_is_not_backup_evidence(self):
        # On prépare le dossier self.raw_path avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        self.raw_path.mkdir(parents=True)
        # On garde dans result le résultat de contrôle brut préparé par ce test.
        result = self.raw_result()
        # On attend que result['found_in_raw_live'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["found_in_raw_live"])
        # On attend que result['raw_has_full_size_image'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["raw_has_full_size_image"])

    def test_native_png_left_only(self):
        # On garde dans evidence le fichier de fixture écrit pour cette vérification.
        evidence = self.write(
            self.raw_path / f"{self.base}_LEFT" / "12345" / "image.PNG"
        )
        # On garde dans result le résultat de contrôle brut préparé par ce test.
        result = self.raw_result()
        # On attend que result['raw_has_full_size_left'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["raw_has_full_size_left"])
        # On attend que result['raw_has_full_size_right'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["raw_has_full_size_right"])
        # On attend que result['raw_has_full_size_both_sides'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(result["raw_has_full_size_both_sides"])
        # On vérifie que result['raw_full_size_left_evidence_path'] correspond à str(evidence).
        self.assertEqual(result["raw_full_size_left_evidence_path"], str(evidence))

    def test_native_png_right_only(self):
        # On écrit self.raw_path / f'{self.base}_RIGHT' / '12345' / 'image.png' dans self ; le mode
        # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write(self.raw_path / f"{self.base}_RIGHT" / "12345" / "image.png")
        # On garde dans result le résultat de contrôle brut préparé par ce test.
        result = self.raw_result()
        # On attend que result['raw_has_full_size_right'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["raw_has_full_size_right"])
        # On attend que result['raw_has_full_size_left'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["raw_has_full_size_left"])

    def test_native_png_both_sides(self):
        # On parcourt ('LEFT', 'RIGHT') ; side désigne l’élément courant de ce scénario.
        for side in ("LEFT", "RIGHT"):
            # On écrit self.raw_path / f'{self.base}_{side}' / '12345' / 'image.png' dans self ; le
            # mode d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
            self.write(self.raw_path / f"{self.base}_{side}" / "12345" / "image.png")
        # On attend que self.raw_result()['raw_has_full_size_both_sides'] soit évalué comme vrai pour
        # ce cas de test.
        self.assertTrue(self.raw_result()["raw_has_full_size_both_sides"])

    def test_technical_png_paths_are_ignored(self):
        # On assemble les morceaux du chemin side_path avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        side_path = self.raw_path / f"{self.base}_LEFT"
        # On parcourt ('12345_resized', '12345_DEPTH', 'binaries', 'img_left', 'img_right', 'Ma… ;
        # folder désigne l’élément courant de ce scénario.
        for folder in (
            "12345_resized",
            "12345_DEPTH",
            "binaries",
            "img_left",
            "img_right",
            "Mail",
        ):
            # On écrit side_path / folder / 'image.png' dans self ; le mode d’ouverture du flux
            # détermine s’il s’agit d’un ajout ou d’un remplacement.
            self.write(side_path / folder / "image.png")
        # On écrit side_path / 'image.png' dans self ; le mode d’ouverture du flux détermine s’il
        # s’agit d’un ajout ou d’un remplacement.
        self.write(side_path / "image.png")
        # On écrit self.raw_path / f'{self.base}_Mail' / '12345' / 'image.png' dans self ; le mode
        # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write(self.raw_path / f"{self.base}_Mail" / "12345" / "image.png")
        # On attend que self.raw_result()['raw_has_full_size_image'] soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse(self.raw_result()["raw_has_full_size_image"])

    def test_numeric_camera_without_png_is_not_evidence(self):
        # On écrit self.raw_path / f'{self.base}_LEFT' / '12345' / 'image.jpg' dans self ; le mode
        # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write(self.raw_path / f"{self.base}_LEFT" / "12345" / "image.jpg")
        # On attend que self.raw_result()['raw_has_full_size_image'] soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse(self.raw_result()["raw_has_full_size_image"])

    def test_processing_folder_without_webp_is_not_processed(self):
        # On prépare le dossier self.processing_path avec les règles de création indiquées ; aucun
        # résultat métier n’est encore produit par cette création.
        self.processing_path.mkdir(parents=True)
        # On garde dans result la valeur renvoyée par self.processing_result.
        result = self.processing_result()
        # On attend que result['found_in_processing_live'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["found_in_processing_live"])
        # On attend que result['processing_has_webp_images'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(result["processing_has_webp_images"])
        # On vérifie que result['processing_error'] correspond à ''.
        self.assertEqual(result["processing_error"], "")

    def test_webp_each_side_and_both(self):
        # On parcourt ('LEFT', 'RIGHT') ; side désigne l’élément courant de ce scénario.
        for side in ("LEFT", "RIGHT"):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(side=side):
                # Réinitialiser les preuves entre les deux scénarios.
                for previous in self.processing_path.rglob("*.WEBP"):
                    # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas
                    # arbitrairement d’autres fichiers.
                    previous.unlink()
                # On écrit self.processing_path / 'processed_imgs' / side / 'image.WEBP' dans self ; le
                # mode d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
                self.write(
                    self.processing_path / "processed_imgs" / side / "image.WEBP"
                )
                # On garde dans result la valeur renvoyée par self.processing_result.
                result = self.processing_result()
                # On attend que result[f'processing_has_webp_{side.lower()}'] soit évalué comme vrai
                # pour ce cas de test.
                self.assertTrue(result[f"processing_has_webp_{side.lower()}"])
                # On attend que result['processing_has_webp_both_sides'] soit évalué comme faux pour ce
                # cas de test.
                self.assertFalse(result["processing_has_webp_both_sides"])
        # On écrit self.processing_path / 'processed_imgs' / 'LEFT' / 'image.WEBP' dans self ; le mode
        # d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write(self.processing_path / "processed_imgs" / "LEFT" / "image.WEBP")
        # On attend que self.processing_result()['processing_has_webp_both_sides'] soit évalué comme
        # vrai pour ce cas de test.
        self.assertTrue(self.processing_result()["processing_has_webp_both_sides"])

    def test_webp_outside_expected_directory_is_ignored(self):
        # On écrit self.processing_path / 'image.webp' dans self ; le mode d’ouverture du flux
        # détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write(self.processing_path / "image.webp")
        # On écrit self.processing_path / 'processed_imgs' / 'LEFT' / 'nested' / 'image.webp' dans self
        # ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write(
            self.processing_path / "processed_imgs" / "LEFT" / "nested" / "image.webp"
        )
        # On attend que self.processing_result()['processing_has_webp_images'] soit évalué comme faux
        # pour ce cas de test.
        self.assertFalse(self.processing_result()["processing_has_webp_images"])

    def test_read_error_is_reported(self):
        # On prépare le dossier self.processing_path avec les règles de création indiquées ; aucun
        # résultat métier n’est encore produit par cette création.
        self.processing_path.mkdir(parents=True)
        # On prépare le dossier self.processing_path / 'processed_imgs' / 'LEFT' avec les règles de
        # création indiquées ; aucun résultat métier n’est encore produit par cette création.
        (self.processing_path / "processed_imgs" / "LEFT").mkdir(parents=True)
        # On remplace temporairement nas.os dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(
            # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
            # suivre une fonction de test.
            nas.os, "scandir", side_effect=PermissionError("Acces refuse")
        ):
            # On garde dans result la valeur renvoyée par self.processing_result.
            result = self.processing_result()
        # On vérifie que 'Acces refuse' figure dans result['processing_error'].
        self.assertIn("Acces refuse", result["processing_error"])

    def test_json_valid_missing_and_invalid(self):
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.root / "mapping.json"
        # On répartit les valeurs renvoyées par nas.load_json_file entre (data, error) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        data, error = nas.load_json_file(path)
        # On attend None pour data : aucune valeur n’est confirmée dans ce cas.
        self.assertIsNone(data)
        # On attend que error soit évalué comme vrai pour ce cas de test.
        self.assertTrue(error)
        # On appelle self.write_json avec path.
        self.write_json(path, {"PARCELLE": [self.acquisition]})
        # On répartit les valeurs renvoyées par nas.load_json_file entre (data, error) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        data, error = nas.load_json_file(path)
        # On vérifie que data correspond à {'PARCELLE': [self.acquisition]}.
        self.assertEqual(data, {"PARCELLE": [self.acquisition]})
        # On vérifie que error correspond à ''.
        self.assertEqual(error, "")
        # On écrit path dans self ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout ou
        # d’un remplacement.
        self.write(path, "{JSON invalide")
        # On répartit les valeurs renvoyées par nas.load_json_file entre (data, error) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        data, error = nas.load_json_file(path)
        # On attend None pour data : aucune valeur n’est confirmée dans ce cas.
        self.assertIsNone(data)
        # On attend que error soit évalué comme vrai pour ce cas de test.
        self.assertTrue(error)

    def test_parcel_mapping_is_case_insensitive_and_trimmed(self):
        # On répartit les valeurs renvoyées par nas.build_parcel_mapping_index entre (index, error) ;
        # leur ordre doit correspondre à celui prévu par cet appel.
        index, error = nas.build_parcel_mapping_index(
            {"PARCELLE": [f" {self.acquisition.upper()} "]}
        )
        # On vérifie que error correspond à ''.
        self.assertEqual(error, "")
        # On garde dans result la valeur renvoyée par nas.check_parcel_mapping.
        result = nas.check_parcel_mapping(index, self.acquisition.lower())
        # On attend que result['found_in_parcel_mapping'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["found_in_parcel_mapping"])
        # On vérifie que result['parcel_name'] correspond à 'PARCELLE'.
        self.assertEqual(result["parcel_name"], "PARCELLE")
        # On attend que nas.check_parcel_mapping(index, 'inconnue')['found_in_parcel_mapping'] soit
        # évalué comme faux pour ce cas de test.
        self.assertFalse(
            nas.check_parcel_mapping(index, "inconnue")["found_in_parcel_mapping"]
        )

    def test_multiple_parcels_are_preserved_without_error(self):
        # On répartit les valeurs renvoyées par nas.build_parcel_mapping_index entre (index, error) ;
        # leur ordre doit correspondre à celui prévu par cet appel.
        index, error = nas.build_parcel_mapping_index(
            {"P1": [self.acquisition], "P2": [self.acquisition]}
        )
        # On vérifie que error correspond à ''.
        self.assertEqual(error, "")
        # On vérifie que index[self.acquisition.casefold()] correspond à ['P1', 'P2'].
        self.assertEqual(index[self.acquisition.casefold()], ["P1", "P2"])

    def test_passage_mapping_and_duplicates(self):
        # On regroupe dans data ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
        # leur position.
        data = {"PARCELLE": {self.passage: [self.acquisition]}}
        # On répartit les valeurs renvoyées par nas.build_passage_mapping_index entre (index, error) ;
        # leur ordre doit correspondre à celui prévu par cet appel.
        index, error = nas.build_passage_mapping_index(data)
        # On vérifie que error correspond à ''.
        self.assertEqual(error, "")
        # On garde dans result la valeur renvoyée par nas.check_passage_mapping.
        result = nas.check_passage_mapping(index, self.acquisition.upper())
        # On vérifie que result['passage_name'] correspond à self.passage.
        self.assertEqual(result["passage_name"], self.passage)
        # On vérifie que result['passage_parcel_name'] correspond à 'PARCELLE'.
        self.assertEqual(result["passage_parcel_name"], "PARCELLE")
        # On rassemble dans data['PARCELLE']['AUTRE_PASSAGE'] les 1 éléments explicitement indiqués
        # pour ce cas d’essai.
        data["PARCELLE"]["AUTRE_PASSAGE"] = [self.acquisition]
        # On répartit les valeurs renvoyées par nas.build_passage_mapping_index entre (index, error) ;
        # leur ordre doit correspondre à celui prévu par cet appel.
        index, error = nas.build_passage_mapping_index(data)
        # On vérifie que error correspond à ''.
        self.assertEqual(error, "")
        # On vérifie que len(index[self.acquisition.casefold()]) correspond à 2.
        self.assertEqual(len(index[self.acquisition.casefold()]), 2)

    def test_invalid_mapping_structures_are_reported(self):
        # On parcourt (nas.build_parcel_mapping_index, nas.build_passage_mapping_index) ; function
        # désigne l’élément courant de ce scénario.
        for function in (
            nas.build_parcel_mapping_index,
            nas.build_passage_mapping_index,
        ):
            # On identifie ce sous-cas avec les valeurs indiquées ; un échec restera rattaché à ce cas
            # précis de la boucle.
            with self.subTest(function=function.__name__):
                # On répartit les valeurs renvoyées par function entre (index, error) ; leur ordre doit
                # correspondre à celui prévu par cet appel.
                index, error = function([])
                # On vérifie que index correspond à {}.
                self.assertEqual(index, {})
                # On attend que error soit évalué comme vrai pour ce cas de test.
                self.assertTrue(error)

    def test_parcel_inconsistency_is_detected(self):
        # On garde dans result le résultat construit avec les valeurs explicites du scénario.
        result = self.build_result(parcel="P1", passage_parcel="P2")
        # On attend que result['parcel_mapping_consistent'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["parcel_mapping_consistent"])

    def test_missing_mapping_does_not_claim_consistency(self):
        # On garde dans result le résultat construit avec les valeurs explicites du scénario.
        result = self.build_result(parcel=None, passage_parcel=None)
        # On attend None pour result['parcel_mapping_consistent'] : aucune valeur n’est confirmée
        # dans ce cas.
        self.assertIsNone(result["parcel_mapping_consistent"])
        # On attend que result['found_in_passage_mapping'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["found_in_passage_mapping"])

    def test_healthy_statuses_are_not_non_healthy(self):
        # On garde dans result la valeur renvoyée par nas.analyze_stock_statuses.
        result = nas.analyze_stock_statuses(
            [{"status": " HEALTHY "}, {"statut": "sain"}]
        )
        # On vérifie que result['stock_status_count'] correspond à 2.
        self.assertEqual(result["stock_status_count"], 2)
        # On attend que result['has_non_healthy_status'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["has_non_healthy_status"])

    def test_nested_non_healthy_statuses(self):
        # On garde dans result la valeur renvoyée par nas.analyze_stock_statuses.
        result = nas.analyze_stock_statuses(
            {
                # On associe la clé 'stocks' à cette valeur dans les données de ce scénario.
                "stocks": [
                    {"status": "HEALTHY"},
                    {"status": "MISSING"},
                    {"details": {"Status": "SICK"}},
                    {"statut": "DEAD"},
                ]
            }
        )
        # On vérifie que result['stock_status_count'] correspond à 4.
        self.assertEqual(result["stock_status_count"], 4)
        # On vérifie que result['non_healthy_status_count'] correspond à 3.
        self.assertEqual(result["non_healthy_status_count"], 3)
        # On attend que result['has_non_healthy_status'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["has_non_healthy_status"])

    def test_empty_statuses_do_not_prove_vitiparcel(self):
        # On attend que nas.contains_non_healthy_status({'status': '', 'nested': {'status': None}})
        # soit évalué comme faux pour ce cas de test.
        self.assertFalse(
            nas.contains_non_healthy_status({"status": "", "nested": {"status": None}})
        )

    def test_missing_passage_folder_is_not_read_error(self):
        # On garde dans result le résultat de passage préparé pour le cas testé.
        result = self.passage_result()
        # On attend que result['passage_created'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["passage_created"])
        # On vérifie que result['passage_error'] correspond à ''.
        self.assertEqual(result["passage_error"], "")

    def test_geojson_exact_name_and_fallback(self):
        # On garde dans exact le fichier de fixture écrit pour cette vérification.
        exact = self.write(self.passage_path / f"{self.passage}_rep_map.geojson", "{}")
        # On garde dans result le résultat de passage préparé pour le cas testé.
        result = self.passage_result()
        # On attend que result['vitimap_created'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["vitimap_created"])
        # On vérifie que result['vitimap_geojson_path'] correspond à str(exact).
        self.assertEqual(result["vitimap_geojson_path"], str(exact))
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        exact.unlink()
        # On garde dans fallback le fichier de fixture écrit pour cette vérification.
        fallback = self.write(self.passage_path / "autre_rep_map.geojson", "{}")
        # On vérifie que self.passage_result()['vitimap_geojson_path'] correspond à str(fallback).
        self.assertEqual(self.passage_result()["vitimap_geojson_path"], str(fallback))

    def test_stocks_absent_does_not_prove_vitiparcel(self):
        # On prépare le dossier self.passage_path avec les règles de création indiquées ; aucun
        # résultat métier n’est encore produit par cette création.
        self.passage_path.mkdir(parents=True)
        # On garde dans result le résultat de passage préparé pour le cas testé.
        result = self.passage_result()
        # On attend que result['stocks_json_exists'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["stocks_json_exists"])
        # On attend que result['vitiparcel_created'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["vitiparcel_created"])

    def test_stocks_with_only_healthy_statuses(self):
        # On appelle self.write_json avec self.passage_path / f'{self.passage}_stocks.json'.
        self.write_json(
            self.passage_path / f"{self.passage}_stocks.json", [{"status": "HEALTHY"}]
        )
        # On garde dans result le résultat de passage préparé pour le cas testé.
        result = self.passage_result()
        # On attend que result['stocks_json_exists'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["stocks_json_exists"])
        # On attend que result['has_non_healthy_status'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["has_non_healthy_status"])
        # On attend que result['vitiparcel_created'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["vitiparcel_created"])

    def test_stocks_with_missing_status_proves_defined_criterion(self):
        # On appelle self.write_json avec self.passage_path / 'autre_stocks.json'.
        self.write_json(
            self.passage_path / "autre_stocks.json", [{"status": "MISSING"}]
        )
        # On garde dans result le résultat de passage préparé pour le cas testé.
        result = self.passage_result()
        # On attend que result['stocks_json_exists'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["stocks_json_exists"])
        # On attend que result['has_non_healthy_status'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["has_non_healthy_status"])
        # On attend que result['vitiparcel_created'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["vitiparcel_created"])

    def test_invalid_stocks_is_error_not_vitiparcel(self):
        # On écrit self.passage_path / f'{self.passage}_stocks.json' dans self ; le mode d’ouverture du
        # flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write(self.passage_path / f"{self.passage}_stocks.json", "{invalide")
        # On garde dans result le résultat de passage préparé pour le cas testé.
        result = self.passage_result()
        # On attend que result['stocks_json_exists'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["stocks_json_exists"])
        # On attend que result['vitiparcel_error'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["vitiparcel_error"])
        # On attend que result['vitiparcel_created'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["vitiparcel_created"])

    def test_shared_passage_is_checked_once(self):
        # On crée le dictionnaire vide cache pour y ranger ensuite les éléments par clé.
        cache = {}
        # On remplace temporairement nas dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(
            nas, "check_passage_outputs", wraps=nas.check_passage_outputs
        ) as check:
            # On garde dans first le résultat construit avec les valeurs explicites du scénario.
            first = self.build_result(cache=cache)
            # On utilise ce texte pour self.base ; il ne dépend pas d’une valeur récupérée ailleurs à
            # cet endroit.
            self.base = "C01_V1_2026-06-16T12-35-14"
            # On prépare self.acquisition avec cette expression pour l’utiliser dans la suite du
            # traitement.
            self.acquisition = f"{self.vineyard}_{self.base}"
            # On garde dans second le résultat construit avec les valeurs explicites du scénario.
            second = self.build_result(cache=cache)
        # On vérifie que check.call_count correspond à 1.
        self.assertEqual(check.call_count, 1)
        # On vérifie que first['passage_name'] correspond à second['passage_name'].
        self.assertEqual(first["passage_name"], second["passage_name"])

    def test_checks_leave_synthetic_source_tree_unchanged(self):
        # Contrôle limité à ce scénario : pas une preuve globale de lecture seule.
        self.write(self.raw_path / f"{self.base}_LEFT" / "12345" / "image.png")
        # On appelle self.write_json avec self.passage_path / f'{self.passage}_stocks.json'.
        self.write_json(
            self.passage_path / f"{self.passage}_stocks.json", {"status": "MISSING"}
        )

        # On prend une copie de l’état consulté pour pouvoir la comparer après l’essai.
        def snapshot():
            # On remet {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns) if… à
            # l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
            return {
                str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                if p.is_file()
                else None
                for p in self.root.rglob("*")
            }

        # On garde dans before l’état photographié pour les comparaisons de cet essai.
        before = snapshot()
        # On appelle self.build_result sans argument positionnel.
        self.build_result()
        # On vérifie que snapshot() correspond à before.
        self.assertEqual(snapshot(), before)

    def test_reference_filter_year_deduplication_and_limit(self):
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.root / "reference.csv"
        # On appelle pd.DataFrame([{'Vineyard': self.vineyard, 'Acquisition_ID_base': self.base,
        # 'Acquisition_ID_normalise': self.acquisition}, {'Vineyard': self.vineyard,
        # 'Acquisition_ID_base': self.base, 'Acquisition_ID_normalise': self.acquisition}, {'Vineyard':
        # self.vineyard, 'Acquisition_ID_base': 'ancien', 'Acquisition_ID_normalise':
        # 'VignobleTest_2025-06-16T12-34-14'}]).to_csv avec path.
        pd.DataFrame(
            [
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": self.vineyard,
                    # On associe la clé 'Acquisition_ID_base' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_ID_base": self.base,
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'Acquisition_ID_normalise'.
                    "Acquisition_ID_normalise": self.acquisition,
                },
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": self.vineyard,
                    # On associe la clé 'Acquisition_ID_base' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_ID_base": self.base,
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'Acquisition_ID_normalise'.
                    "Acquisition_ID_normalise": self.acquisition,
                },
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": self.vineyard,
                    # On associe la clé 'Acquisition_ID_base' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_ID_base": "ancien",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'Acquisition_ID_normalise'.
                    "Acquisition_ID_normalise": "VignobleTest_2025-06-16T12-34-14",
                },
            ]
        ).to_csv(path, index=False)
        # On garde dans result la valeur renvoyée par nas.load_reference.
        result = nas.load_reference(path, self.vineyard.lower(), self.year, [], None)
        # On vérifie que len(result) correspond à 1.
        self.assertEqual(len(result), 1)
        # On garde dans result la valeur renvoyée par nas.load_reference.
        result = nas.load_reference(
            path, self.vineyard, self.year, [self.acquisition.upper()], 1
        )
        # On vérifie que len(result) correspond à 1.
        self.assertEqual(len(result), 1)
        # On attend que nas.load_reference(path, self.vineyard, self.year, ['inconnue'], None).empty
        # soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            nas.load_reference(path, self.vineyard, self.year, ["inconnue"], None).empty
        )
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle nas.load_reference avec path.
            nas.load_reference(path, self.vineyard, self.year, [], 0)

    def test_missing_passage_link_is_not_a_technical_error(self):
        # Une absence de rattachement ne constitue pas une erreur de lecture.
        result = self.passage_result(name="")
        # On vérifie que result['passage_error'] correspond à ''.
        self.assertEqual(result["passage_error"], "")
        # On attend que result['passage_outputs_verifiable'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(result["passage_outputs_verifiable"])
        # On vérifie que 'passage non identifié' figure dans result['passage_verification_note'].
        self.assertIn("passage non identifié", result["passage_verification_note"])

    def test_missing_passage_is_non_verifiable_in_csv(self):
        # On garde dans result le résultat construit avec les valeurs explicites du scénario.
        result = self.build_result(parcel=None, passage_parcel=None)
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = self.root / "result.csv"
        # On appelle pd.DataFrame([result]).to_csv avec path.
        pd.DataFrame([result]).to_csv(path, index=False)
        # On garde dans loaded la valeur renvoyée par pd.read_csv.
        loaded = pd.read_csv(path)
        # On attend que bool(loaded.loc[0, 'passage_outputs_verifiable']) soit évalué comme faux pour
        # ce cas de test.
        self.assertFalse(bool(loaded.loc[0, "passage_outputs_verifiable"]))
        # On vérifie que 'passage non identifié' figure dans loaded.loc[0,
        # 'passage_verification_note'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "passage non identifié", loaded.loc[0, "passage_verification_note"]
        )
        # On vérifie que result['passage_error'] correspond à ''.
        self.assertEqual(result["passage_error"], "")

    def test_missing_passage_display_does_not_claim_absence(self):
        # On garde dans result le résultat construit avec les valeurs explicites du scénario.
        result = self.build_result(parcel=None, passage_parcel=None)
        # On prépare messages comme liste vide ; on la remplira au fil des opérations suivantes.
        messages = []
        # On remplace temporairement nas dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(nas, "log", side_effect=messages.append):
            # On appelle nas.print_acquisition_result avec 1.
            nas.print_acquisition_result(1, 1, result, verbose=True)
        # On garde dans output le texte formé en réunissant les éléments avec '\n' comme séparateur.
        output = "\n".join(messages)
        # On vérifie que 'non vérifiable — passage non identifié' figure dans output.
        self.assertIn("non vérifiable — passage non identifié", output)
        # On vérifie que 'GeoJSON absent' ne figure pas dans output.
        self.assertNotIn("GeoJSON absent", output)
        # On vérifie que 'aucun champ status trouvé' ne figure pas dans output.
        self.assertNotIn("aucun champ status trouvé", output)
        # On vérifie que 'Erreurs techniques' ne figure pas dans output.
        self.assertNotIn("Erreurs techniques", output)

    def test_missing_passage_compact_display(self):
        # On garde dans result le résultat construit avec les valeurs explicites du scénario.
        result = self.build_result(parcel=None, passage_parcel=None)
        # On prépare messages comme liste vide ; on la remplira au fil des opérations suivantes.
        messages = []
        # On remplace temporairement nas dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(nas, "log", side_effect=messages.append):
            # On appelle nas.print_acquisition_result avec 1.
            nas.print_acquisition_result(1, 1, result, verbose=False)
        # On vérifie que 'Passage=non vérifiable' figure dans '\n'.join(messages).
        self.assertIn("Passage=non vérifiable", "\n".join(messages))

    def test_summary_separates_non_verifiable_and_unsatisfied(self):
        # On garde dans result le résultat construit avec les valeurs explicites du scénario.
        result = self.build_result(parcel=None, passage_parcel=None)
        # On prépare messages comme liste vide ; on la remplira au fil des opérations suivantes.
        messages = []
        # On remplace temporairement nas dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(nas, "log", side_effect=messages.append):
            # On appelle nas.print_summary avec pd.DataFrame([result]).
            nas.print_summary(pd.DataFrame([result]), 0.1, self.root / "result.csv")
        # On garde dans output le texte formé en réunissant les éléments avec '\n' comme séparateur.
        output = "\n".join(messages)
        # On vérifie que 'non vérifiable, passage non identifié' figure dans output.
        self.assertIn("non vérifiable, passage non identifié", output)
        # On vérifie que 'ne satisfont pas le critère' ne figure pas dans output.
        self.assertNotIn("ne satisfont pas le critère", output)
        # On vérifie que 'Matthias' ne figure pas dans output.
        self.assertNotIn("Matthias", output)
        # On vérifie que 'observé : MISSING' ne figure pas dans output.
        self.assertNotIn("observé : MISSING", output)
        # On attend que any(('Acquisitions avec erreur technique' in line and line.endswith(': 0') for
        # line in messages)) soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            any(
                "Acquisitions avec erreur technique" in line and line.endswith(": 0")
                for line in messages
            )
        )

    def multi_result(self):
        # On garde dans row une série pandas avec les valeurs et l’index fournis.
        row = pd.Series(
            {
                # On associe la clé 'Acquisition_ID_base' à cette valeur dans les données de ce
                # scénario.
                "Acquisition_ID_base": self.base,
                # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                # 'Acquisition_ID_normalise'.
                "Acquisition_ID_normalise": self.acquisition,
            }
        )
        # On répartit les valeurs renvoyées par nas.build_parcel_mapping_index entre (parcels, _) ;
        # leur ordre doit correspondre à celui prévu par cet appel.
        parcels, _ = nas.build_parcel_mapping_index(
            {"Achille": [self.acquisition], "Chardonnay": [self.acquisition]}
        )
        # On répartit les valeurs renvoyées par nas.build_passage_mapping_index entre (passages, _) ;
        # leur ordre doit correspondre à celui prévu par cet appel.
        passages, _ = nas.build_passage_mapping_index(
            {
                # On associe la clé 'Achille' à cette valeur dans les données de ce scénario.
                "Achille": {"Achille_2026-07-21": [self.acquisition]},
                # On associe la clé 'Chardonnay' à cette valeur dans les données de ce scénario.
                "Chardonnay": {"Chardonnay_2026-07-21": [self.acquisition]},
            }
        )
        # On fournit à l’appelant la valeur renvoyée par nas.build_result.
        return nas.build_result(
            row,
            self.raw,
            self.processing,
            self.vineyard,
            self.year,
            parcels,
            passages,
            {},
            "2026-10-05T10:00:00Z",
        )

    def test_multiple_passages_are_checked_and_preserved(self):
        # On garde dans result la valeur renvoyée par self.multi_result.
        result = self.multi_result()
        # On vérifie que result['parcel_count'] correspond à 2.
        self.assertEqual(result["parcel_count"], 2)
        # On vérifie que result['passage_link_count'] correspond à 2.
        self.assertEqual(result["passage_link_count"], 2)
        # On attend que result['parcel_mapping_consistent'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(result["parcel_mapping_consistent"])
        # On vérifie que {r['parcel_name'] for r in result['_association_results']} correspond à
        # {'Achille', 'Chardonnay'}.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            {r["parcel_name"] for r in result["_association_results"]},
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            {"Achille", "Chardonnay"},
        )

    def test_one_complete_passage_does_not_make_all_outputs_complete(self):
        # On assemble les morceaux du chemin directory avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        directory = (
            self.processing
            / self.vineyard
            / "passages"
            / str(self.year)
            / "Achille_2026-07-21"
        )
        # On écrit directory / 'Achille_2026-07-21_rep_map.geojson' dans self ; le mode d’ouverture du
        # flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        self.write(directory / "Achille_2026-07-21_rep_map.geojson", "{}")
        # On appelle self.write_json avec directory / 'Achille_2026-07-21_stocks.json'.
        self.write_json(
            directory / "Achille_2026-07-21_stocks.json", {"status": "MISSING"}
        )
        # On garde dans result la valeur renvoyée par self.multi_result.
        result = self.multi_result()
        # On attend que result['vitimap_created'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["vitimap_created"])
        # On attend que result['vitiparcel_created'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(result["vitiparcel_created"])
        # On récupère result['_association_results'] et on le garde dans rows pour la suite.
        rows = result["_association_results"]
        # On attend que rows[0]['vitiparcel_created'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(rows[0]["vitiparcel_created"])
        # On attend que rows[1]['vitiparcel_created'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(rows[1]["vitiparcel_created"])

    def test_all_associated_passages_can_satisfy_criterion(self):
        # On parcourt ('Achille_2026-07-21', 'Chardonnay_2026-07-21') ; passage désigne l’élément
        # courant de ce scénario.
        for passage in ("Achille_2026-07-21", "Chardonnay_2026-07-21"):
            # On assemble les morceaux du chemin directory avec l’opérateur / de pathlib ; aucun
            # fichier n’est créé par cette construction.
            directory = (
                self.processing / self.vineyard / "passages" / str(self.year) / passage
            )
            # On appelle self.write_json avec directory / f'{passage}_stocks.json'.
            self.write_json(directory / f"{passage}_stocks.json", {"status": "MISSING"})
        # On attend que self.multi_result()['vitiparcel_created'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(self.multi_result()["vitiparcel_created"])

    def test_repeated_identical_links_are_deduplicated(self):
        # On répartit les valeurs renvoyées par nas.build_passage_mapping_index entre (index, error) ;
        # leur ordre doit correspondre à celui prévu par cet appel.
        index, error = nas.build_passage_mapping_index(
            {"P1": {"P1_2026-07-21": [self.acquisition, self.acquisition.upper()]}}
        )
        # On vérifie que error correspond à ''.
        self.assertEqual(error, "")
        # On vérifie que len(index[self.acquisition.casefold()]) correspond à 1.
        self.assertEqual(len(index[self.acquisition.casefold()]), 1)

    def test_passage_report_deduplicates_shared_passage(self):
        # On garde dans result le résultat construit avec les valeurs explicites du scénario.
        result = self.build_result()
        # On récupère result['_association_results'][0] et on le garde dans association pour la suite.
        association = result["_association_results"][0]
        # On regroupe dans other ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        other = {**association, "acquisition_id_normalise": "autre_acquisition"}
        # On garde dans report la valeur renvoyée par nas.build_passage_report.
        report = nas.build_passage_report(
            pd.DataFrame([association, other, association])
        )
        # On vérifie que len(report) correspond à 1.
        self.assertEqual(len(report), 1)
        # On vérifie que report.iloc[0]['acquisitions_controlled_count'] correspond à 2.
        self.assertEqual(report.iloc[0]["acquisitions_controlled_count"], 2)

    def test_passage_report_keeps_temporally_distinct_passages(self):
        # On garde dans result le résultat construit avec les valeurs explicites du scénario.
        result = self.build_result()
        # On récupère result['_association_results'][0] et on le garde dans association pour la suite.
        association = result["_association_results"][0]
        # On regroupe dans other ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        other = {**association, "passage_name": "PARCELLE_2026-08-18"}
        # On vérifie que len(nas.build_passage_report(pd.DataFrame([association, other]))) correspond à
        # 2.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            len(nas.build_passage_report(pd.DataFrame([association, other]))), 2
        )

    def test_passage_report_empty_when_no_link(self):
        # On garde dans result le résultat construit avec les valeurs explicites du scénario.
        result = self.build_result(parcel=None, passage_parcel=None)
        # On vérifie que result['_association_results'] correspond à [].
        self.assertEqual(result["_association_results"], [])
        # On attend que nas.build_passage_report(pd.DataFrame()).empty soit évalué comme vrai pour ce
        # cas de test.
        self.assertTrue(nas.build_passage_report(pd.DataFrame()).empty)

    def test_passage_report_separates_vineyards(self):
        # On récupère self.build_result()['_association_results'][0] et on le garde dans association
        # pour la suite.
        association = self.build_result()["_association_results"][0]
        # On regroupe dans other ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        other = {**association, "Vineyard": "AutreVignoble"}
        # On vérifie que len(nas.build_passage_report(pd.DataFrame([association, other]))) correspond à
        # 2.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            len(nas.build_passage_report(pd.DataFrame([association, other]))), 2
        )

    def test_multiple_passage_display_lists_both_associations(self):
        # On garde dans result la valeur renvoyée par self.multi_result.
        result = self.multi_result()
        # On prépare messages comme liste vide ; on la remplira au fil des opérations suivantes.
        messages = []
        # On remplace temporairement nas dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with patch.object(nas, "log", side_effect=messages.append):
            # On appelle nas.print_acquisition_result avec 1.
            nas.print_acquisition_result(1, 1, result, verbose=True)
        # On garde dans output le texte formé en réunissant les éléments avec '\n' comme séparateur.
        output = "\n".join(messages)
        # On vérifie que 'Achille / Achille_2026-07-21' figure dans output.
        self.assertIn("Achille / Achille_2026-07-21", output)
        # On vérifie que 'Chardonnay / Chardonnay_2026-07-21' figure dans output.
        self.assertIn("Chardonnay / Chardonnay_2026-07-21", output)

    def test_main_writes_three_local_reports_for_multiple_associations(self):
        # Exécution complète sur sources et sorties temporaires uniquement.
        import os
        # On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
        import sys

        # On prépare le dossier self.raw avec les règles de création indiquées ; aucun résultat métier
        # n’est encore produit par cette création.
        self.raw.mkdir(parents=True)
        # On prépare le dossier self.processing avec les règles de création indiquées ; aucun résultat
        # métier n’est encore produit par cette création.
        self.processing.mkdir(parents=True)
        # On assemble les morceaux du chemin reference avec l’opérateur / de pathlib ; aucun fichier
        # n’est créé par cette construction.
        reference = self.root / "reference.csv"
        # On appelle pd.DataFrame([{'Vineyard': self.vineyard, 'Acquisition_ID_base': self.base,
        # 'Acquisition_ID_normalise': self.acquisition}]).to_csv avec reference.
        pd.DataFrame(
            [
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": self.vineyard,
                    # On associe la clé 'Acquisition_ID_base' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_ID_base": self.base,
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'Acquisition_ID_normalise'.
                    "Acquisition_ID_normalise": self.acquisition,
                }
            ]
        ).to_csv(reference, index=False)
        # On appelle self.write_json avec self.processing / self.vineyard / 'parcels' /
        # f'{self.vineyard}_parcels_acquisitions_map.….
        self.write_json(
            self.processing
            / self.vineyard
            / "parcels"
            / f"{self.vineyard}_parcels_acquisitions_map.json",
            {"Achille": [self.acquisition], "Chardonnay": [self.acquisition]},
        )
        # On appelle self.write_json avec self.processing / self.vineyard / 'passages' /
        # f'{self.vineyard}_parcels_passages_acquisi….
        self.write_json(
            self.processing
            / self.vineyard
            / "passages"
            / f"{self.vineyard}_parcels_passages_acquisitions_map.json",
            {
                # On associe la clé 'Achille' à cette valeur dans les données de ce scénario.
                "Achille": {"Achille_2026-07-21": [self.acquisition]},
                # On associe la clé 'Chardonnay' à cette valeur dans les données de ce scénario.
                "Chardonnay": {"Chardonnay_2026-07-21": [self.acquisition]},
            },
        )
        # On assemble les morceaux du chemin output avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        output = self.root / "outputs"
        # On rassemble dans args les 7 éléments explicitement indiqués pour ce cas d’essai.
        args = [
            "extractor",
            "--vineyard",
            self.vineyard,
            "--reference",
            str(reference),
            "--output-dir",
            str(output),
        ]
        # On remplace temporairement sys dans ce bloc de test ; le réglage initial sera rétabli à sa
        # sortie.
        with (
            patch.object(sys, "argv", args),
            patch.dict(
                os.environ,
                {
                    # On associe la clé 'NAS_BRUT_ROOT' à cette valeur dans les données de ce scénario.
                    "NAS_BRUT_ROOT": str(self.raw),
                    # On associe la clé 'NAS_PROCESSING_ROOT' à cette valeur dans les données de ce
                    # scénario.
                    "NAS_PROCESSING_ROOT": str(self.processing),
                },
            ),
            patch.object(nas, "load_dotenv"),
            patch.object(nas, "log"),
        ):
            # On appelle nas.main sans argument positionnel.
            nas.main()
        # On garde dans reports une liste matérialisée à partir de output.glob('*.csv').
        reports = list(output.glob("*.csv"))
        # On vérifie que len(reports) correspond à 3.
        self.assertEqual(len(reports), 3)
        # On garde dans acquisitions la valeur renvoyée par pd.read_csv.
        acquisitions = pd.read_csv(next(output.glob("*_live_nas_evidence_*.csv")))
        # On garde dans associations la valeur renvoyée par pd.read_csv.
        associations = pd.read_csv(next(output.glob("*_live_nas_associations_*.csv")))
        # On garde dans passages la valeur renvoyée par pd.read_csv.
        passages = pd.read_csv(next(output.glob("*_live_nas_passages_*.csv")))
        # On vérifie que len(acquisitions) correspond à 1.
        self.assertEqual(len(acquisitions), 1)
        # On vérifie que len(associations) correspond à 2.
        self.assertEqual(len(associations), 2)
        # On vérifie que len(passages) correspond à 2.
        self.assertEqual(len(passages), 2)
        # On vérifie que '_association_results' ne figure pas dans acquisitions.columns.
        self.assertNotIn("_association_results", acquisitions.columns)
        # On vérifie que set(associations['parcel_name']) correspond à {'Achille', 'Chardonnay'}.
        self.assertEqual(set(associations["parcel_name"]), {"Achille", "Chardonnay"})


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
