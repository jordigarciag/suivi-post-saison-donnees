# Lecture du fichier — Tests de excel nas live reconciler.
#

"""Tests synthétiques : aucun fichier métier réel, aucune lecture du NAS."""

# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
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
# On rend disponibles r depuis suivi_traitements_post_saison.reconciliation, pour les appels de ce
# fichier.
from suivi_traitements_post_saison.reconciliation import excel_nas_live_reconciler as r


class TestExcelNasLiveReconciler(unittest.TestCase):
    def setUp(self):
        # On utilise ce texte pour self.acquisition ; il ne dépend pas d’une valeur récupérée ailleurs
        # à cet endroit.
        self.acquisition = "VignobleTest_C01_V1_2026-06-04T10-01-30"
        # On utilise ce texte pour self.time ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        self.time = "2026-10-05T09:41:22Z"

    def excel(self):
        # On prépare records comme liste vide ; on la remplira au fil des opérations suivantes.
        records = []
        # On parcourt ['LEFT', 'RIGHT'] ; side désigne l’élément courant de ce scénario.
        for side in ["LEFT", "RIGHT"]:
            # On ajoute {'Vineyard': 'VignobleTest', 'Acquisition_ID': self.acquisition + '_' + side,
            # 'Acquisitio… à la fin de records ; les éléments précédents restent conservés.
            records.append(
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "VignobleTest",
                    # On associe la clé 'Acquisition_ID' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_ID": self.acquisition + "_" + side,
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'Acquisition_ID_normalise'.
                    "Acquisition_ID_normalise": self.acquisition,
                    # On associe la clé 'Acquisition_side' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_side": side,
                    # On associe la clé 'Acquisition_date' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_date": "2026-06-04",
                    # On associe la clé 'Acquisition_datetime' à cette valeur dans les données de ce
                    # scénario.
                    "Acquisition_datetime": "2026-06-04T10:01:30",
                    # On associe la clé 'Acquisition_timestamp_valid' à cette valeur dans les données
                    # de ce scénario.
                    "Acquisition_timestamp_valid": "True",
                    # On associe la clé 'Acquisition_timestamp_issue' à cette valeur dans les données
                    # de ce scénario.
                    "Acquisition_timestamp_issue": "",
                    "Périmètre": "Bloqué",
                    # On associe la clé 'Statut_pipeline' à cette valeur dans les données de ce
                    # scénario.
                    "Statut_pipeline": "En attente",
                    # On associe la clé 'is_test_candidate' à cette valeur dans les données de ce
                    # scénario.
                    "is_test_candidate": "False",
                    # On associe la clé 'has_waiting_step' à cette valeur dans les données de ce
                    # scénario.
                    "has_waiting_step": "True",
                    # On associe la clé 'needs_review' à cette valeur dans les données de ce scénario.
                    "needs_review": "False",
                    # On associe la clé 'is_blocked_candidate' à cette valeur dans les données de ce
                    # scénario.
                    "is_blocked_candidate": "True",
                    # On associe la clé 'source_file' à cette valeur dans les données de ce scénario.
                    "source_file": "synthetic.xlsx",
                    # On associe la clé 'source_sheet' à cette valeur dans les données de ce scénario.
                    "source_sheet": "Suivi_traitement",
                    # On associe la clé 'source_row_number' à cette valeur dans les données de ce
                    # scénario.
                    "source_row_number": "16" if side == "LEFT" else "17",
                    # On renseigne la date d’ingestion sous la clé 'ingested_at'.
                    "ingested_at": "2026-09-30T14:30:19Z",
                    # On associe la clé 'Commentaires' à cette valeur dans les données de ce scénario.
                    "Commentaires": "Images manquantes déjà signalées",
                    "Problématique": "TROUS_ACQUISITION",
                    # On associe la clé 'Statut_Resolution' à cette valeur dans les données de ce
                    # scénario.
                    "Statut_Resolution": "⚠️ Non statué",
                    # On associe la clé 'Traitement_visuel_images' à cette valeur dans les données de
                    # ce scénario.
                    "Traitement_visuel_images": "En attente",
                    # On associe la clé 'Segmentation_images' à cette valeur dans les données de ce
                    # scénario.
                    "Segmentation_images": "En attente",
                    # On associe la clé 'VitiMap' à cette valeur dans les données de ce scénario.
                    "VitiMap": "En attente",
                    # On associe la clé 'VitiParcel' à cette valeur dans les données de ce scénario.
                    "VitiParcel": "",
                }
            )
        # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
        return pd.DataFrame(records)

    def evidence(self):
        # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
        return pd.DataFrame(
            [
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "VignobleTest",
                    # On associe la clé 'project_year' à cette valeur dans les données de ce scénario.
                    "project_year": "2026",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'acquisition_id_normalise'.
                    "acquisition_id_normalise": self.acquisition,
                    # On renseigne la date du contrôle sous la clé 'checked_at'.
                    "checked_at": self.time,
                    # On renseigne la présence constatée dans les données brutes sous la clé
                    # 'found_in_raw_live'.
                    "found_in_raw_live": "True",
                    # On associe la clé 'raw_has_full_size_both_sides' à cette valeur dans les données
                    # de ce scénario.
                    "raw_has_full_size_both_sides": "True",
                    # On renseigne la présence dans les traitements sous la clé
                    # 'found_in_processing_live'.
                    "found_in_processing_live": "True",
                    # On renseigne la présence d’images WEBP sous la clé 'processing_has_webp_images'.
                    "processing_has_webp_images": "False",
                    # On associe la clé 'processing_has_webp_both_sides' à cette valeur dans les
                    # données de ce scénario.
                    "processing_has_webp_both_sides": "False",
                    # On renseigne la présence dans les correspondances de parcelles sous la clé
                    # 'found_in_parcel_mapping'.
                    "found_in_parcel_mapping": "True",
                    # On renseigne la présence dans les correspondances de passages sous la clé
                    # 'found_in_passage_mapping'.
                    "found_in_passage_mapping": "True",
                    # On associe la clé 'parcel_mapping_consistent' à cette valeur dans les données de
                    # ce scénario.
                    "parcel_mapping_consistent": "True",
                    # On associe la clé 'passage_link_count' à cette valeur dans les données de ce
                    # scénario.
                    "passage_link_count": "1",
                    # On renseigne le statut du suivi Excel sous la clé 'excel_pipeline_status'.
                    "excel_pipeline_status": "En attente",
                    **{column: "" for column in r.ERROR_COLUMNS},
                }
            ]
        )

    def associations(self):
        # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
        return pd.DataFrame(
            [
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "VignobleTest",
                    # On associe la clé 'project_year' à cette valeur dans les données de ce scénario.
                    "project_year": "2026",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'acquisition_id_normalise'.
                    "acquisition_id_normalise": self.acquisition,
                    # On associe la clé 'parcel_name' à cette valeur dans les données de ce scénario.
                    "parcel_name": "ParcelleA",
                    # On associe la clé 'passage_name' à cette valeur dans les données de ce scénario.
                    "passage_name": "ParcelleA_2026-06-04",
                    # On renseigne la date du contrôle sous la clé 'checked_at'.
                    "checked_at": self.time,
                    # On associe la clé 'parcel_mapping_consistent' à cette valeur dans les données de
                    # ce scénario.
                    "parcel_mapping_consistent": "True",
                }
            ]
        )

    def passages(self):
        # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
        return pd.DataFrame(
            [
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "VignobleTest",
                    # On associe la clé 'project_year' à cette valeur dans les données de ce scénario.
                    "project_year": "2026",
                    # On associe la clé 'parcel_name' à cette valeur dans les données de ce scénario.
                    "parcel_name": "ParcelleA",
                    # On associe la clé 'passage_name' à cette valeur dans les données de ce scénario.
                    "passage_name": "ParcelleA_2026-06-04",
                    # On renseigne la date du contrôle sous la clé 'checked_at'.
                    "checked_at": self.time,
                    # On associe la clé 'stocks_json_exists' à cette valeur dans les données de ce
                    # scénario.
                    "stocks_json_exists": "True",
                    # On associe la clé 'stock_status_count' à cette valeur dans les données de ce
                    # scénario.
                    "stock_status_count": "2",
                    # On associe la clé 'has_non_healthy_status' à cette valeur dans les données de ce
                    # scénario.
                    "has_non_healthy_status": "False",
                    # On associe la clé 'vitiparcel_created' à cette valeur dans les données de ce
                    # scénario.
                    "vitiparcel_created": "False",
                    # On associe la clé 'passage_created' à cette valeur dans les données de ce
                    # scénario.
                    "passage_created": "True",
                    # On associe la clé 'vitimap_created' à cette valeur dans les données de ce
                    # scénario.
                    "vitimap_created": "True",
                    # On associe la clé 'passage_error' à cette valeur dans les données de ce scénario.
                    "passage_error": "",
                    # On associe la clé 'vitimap_error' à cette valeur dans les données de ce scénario.
                    "vitimap_error": "",
                    # On associe la clé 'vitiparcel_error' à cette valeur dans les données de ce
                    # scénario.
                    "vitiparcel_error": "",
                }
            ]
        )

    def decision(self, expected="non"):
        # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
        return pd.DataFrame(
            [
                {
                    # On renseigne le domaine concerné sous la clé 'Vineyard'.
                    "Vineyard": "VignobleTest",
                    # On renseigne l’identifiant normalisé de l’acquisition sous la clé
                    # 'acquisition_id_normalise'.
                    "acquisition_id_normalise": self.acquisition,
                    # On associe la clé 'full_processing_expected' à cette valeur dans les données de
                    # ce scénario.
                    "full_processing_expected": expected,
                    # On associe la clé 'decision_reason' à cette valeur dans les données de ce
                    # scénario.
                    "decision_reason": "Cas validé par le métier",
                    # On associe la clé 'decision_source' à cette valeur dans les données de ce
                    # scénario.
                    "decision_source": "Décision de test synthétique",
                    # On associe la clé 'decision_at' à cette valeur dans les données de ce scénario.
                    "decision_at": "2026-10-05",
                }
            ]
        )

    def run_reconcile(
        self,
        excel=None,
        evidence=None,
        associations=None,
        passages=None,
        decisions=None,
    ):
        # On fournit à l’appelant la valeur renvoyée par r.reconcile.
        return r.reconcile(
            self.excel() if excel is None else excel,
            self.evidence() if evidence is None else evidence,
            self.associations() if associations is None else associations,
            self.passages() if passages is None else passages,
            decisions,
        )

    def unexplained_excel(self):
        # On garde dans excel le lot ou la ligne Excel synthétique produit par ce helper de test.
        excel = self.excel()
        # On utilise ce texte pour excel['Périmètre'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel["Périmètre"] = "Production"
        # On utilise ce texte pour excel['Statut_pipeline'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel["Statut_pipeline"] = "À déterminer"
        # On utilise ce texte pour excel['is_blocked_candidate'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        excel["is_blocked_candidate"] = "False"
        # On utilise ce texte pour excel['has_waiting_step'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel["has_waiting_step"] = "False"
        # On parcourt ['Commentaires', 'Problématique', 'Statut_Resolution', 'Traitement_visuel… ;
        # column désigne l’élément courant de ce scénario.
        for column in [
            "Commentaires",
            "Problématique",
            "Statut_Resolution",
            "Traitement_visuel_images",
            "Segmentation_images",
            "VitiMap",
            "VitiParcel",
        ]:
            # On commence excel[column] avec un texte vide, à compléter uniquement si la suite apporte
            # une information.
            excel[column] = ""
        # On remet excel à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
        return excel

    def test_known_problem_is_not_new_alert(self):
        # On garde dans excel le cas Excel dont le motif doit être interprété par la règle testée.
        excel = self.unexplained_excel()
        # On utilise ce texte pour excel['Problématique'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel["Problématique"] = "TROUS_ACQUISITION"
        # On récupère self.run_reconcile(excel=excel)[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile(excel=excel)[0].iloc[0]
        # On vérifie que 'Écart connu' figure dans row['processing_business_category'].
        self.assertIn("Écart connu", row["processing_business_category"])
        # On attend que row['processing_new_alert_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["processing_new_alert_candidate"])
        # On attend que row['processing_decision_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["processing_decision_required"])

    def test_non_statue_does_not_reopen_excel_exclusion(self):
        # On récupère self.run_reconcile()[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile()[0].iloc[0]
        # On vérifie que row['business_resolution_declaration'] correspond à '⚠️ Non statué'.
        self.assertEqual(row["business_resolution_declaration"], "⚠️ Non statué")
        # On vérifie que 'Hors contrôles' figure dans row['processing_expectation'].
        self.assertIn("Hors contrôles", row["processing_expectation"])
        # On attend que row['processing_decision_required'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["processing_decision_required"])

    def test_comments_and_two_sides_are_preserved(self):
        # On garde dans excel le lot ou la ligne Excel synthétique produit par ce helper de test.
        excel = self.excel()
        # On utilise ce texte pour excel.loc[1, 'Commentaires'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        excel.loc[1, "Commentaires"] = "Contexte RIGHT différent"
        # On récupère self.run_reconcile(excel=excel)[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile(excel=excel)[0].iloc[0]
        # On vérifie que 'Contexte RIGHT' figure dans row['excel_comments'].
        self.assertIn("Contexte RIGHT", row["excel_comments"])
        # On vérifie que 'Images manquantes' figure dans row['excel_comments'].
        self.assertIn("Images manquantes", row["excel_comments"])
        # On vérifie que len(json.loads(row['excel_side_context_json'])) correspond à 2.
        self.assertEqual(len(json.loads(row["excel_side_context_json"])), 2)

    def test_duplicate_comments_are_not_repeated(self):
        # On récupère r.prepare_context(self.excel()).iloc[0] et on le garde dans context pour la
        # suite.
        context = r.prepare_context(self.excel()).iloc[0]
        # On vérifie que context['excel_comments'] correspond à 'Images manquantes déjà signalées'.
        self.assertEqual(context["excel_comments"], "Images manquantes déjà signalées")
        # On vérifie que context['excel_row_count'] correspond à 2.
        self.assertEqual(context["excel_row_count"], 2)

    def test_side_stage_differences_are_visible(self):
        # On garde dans excel le lot ou la ligne Excel synthétique produit par ce helper de test.
        excel = self.excel()
        # On utilise ce texte pour excel.loc[1, 'Traitement_visuel_images'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        excel.loc[1, "Traitement_visuel_images"] = "Terminé"
        # On récupère self.run_reconcile(excel=excel)[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile(excel=excel)[0].iloc[0]
        # On attend que row['excel_stage_values_differ'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["excel_stage_values_differ"])
        # On vérifie que 'Hors contrôles' figure dans row['processing_business_category'].
        self.assertIn("Hors contrôles", row["processing_business_category"])
        # On attend que row['processing_new_alert_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["processing_new_alert_candidate"])

    def test_invariant_conflict_stops_instead_of_choosing_first(self):
        # On garde dans excel le lot ou la ligne Excel synthétique produit par ce helper de test.
        excel = self.excel()
        # On utilise ce texte pour excel.loc[1, 'Périmètre'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel.loc[1, "Périmètre"] = "Production"
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(excel=excel)

    def test_unexplained_gap_is_candidate_alert_not_reprocessing_order(self):
        # On récupère self.run_reconcile(excel=self.unexplained_excel())[0].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=self.unexplained_excel())[0].iloc[0]
        # On attend que row['processing_new_alert_candidate'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["processing_new_alert_candidate"])
        # On vérifie que 'non expliqué' figure dans row['processing_business_category'].
        self.assertIn("non expliqué", row["processing_business_category"])
        # On vérifie que 'Qualifier' figure dans row['processing_next_action'].
        self.assertIn("Qualifier", row["processing_next_action"])

    def test_unrelated_comment_does_not_prove_expected_gap(self):
        # On garde dans excel le cas Excel dont le motif doit être interprété par la règle testée.
        excel = self.unexplained_excel()
        # On utilise ce texte pour excel['Commentaires'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel["Commentaires"] = "Autre observation"
        # On récupère self.run_reconcile(excel=excel)[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile(excel=excel)[0].iloc[0]
        # On vérifie que 'lien explicatif à confirmer' figure dans
        # row['processing_business_category'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "lien explicatif à confirmer", row["processing_business_category"]
        )
        # On vérifie que row['processing_expectation'] correspond à 'À confirmer'.
        self.assertEqual(row["processing_expectation"], "À confirmer")

    def test_explicit_exemption_is_applied(self):
        # On récupère self.run_reconcile(excel=self.unexplained_excel(), decisions=self.decisio… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            excel=self.unexplained_excel(), decisions=self.decision()
        )[0].iloc[0]
        # On vérifie que 'Écart attendu' figure dans row['processing_business_category'].
        self.assertIn("Écart attendu", row["processing_business_category"])
        # On attend que row['processing_new_alert_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["processing_new_alert_candidate"])
        # On vérifie que 'non attendu' figure dans row['processing_expectation'].
        self.assertIn("non attendu", row["processing_expectation"])

    def test_missing_reason_prevents_confirmed_decision(self):
        # On garde dans decision la valeur renvoyée par self.decision.
        decision = self.decision()
        # On commence decision['decision_reason'] avec un texte vide, à compléter uniquement si la
        # suite apporte une information.
        decision["decision_reason"] = ""
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(decisions=decision)

    def test_invalid_decision_value_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(decisions=self.decision("peut_etre"))

    def test_decision_outside_scope_rejected(self):
        # On garde dans decision la valeur renvoyée par self.decision.
        decision = self.decision()
        # On utilise ce texte pour decision['acquisition_id_normalise'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        decision["acquisition_id_normalise"] = "inconnue"
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(decisions=decision)

    def test_test_acquisition_not_production_omission(self):
        # On garde dans excel le lot ou la ligne Excel synthétique produit par ce helper de test.
        excel = self.excel()
        # On utilise ce texte pour excel['is_test_candidate'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel["is_test_candidate"] = "True"
        # On récupère self.run_reconcile(excel=excel)[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile(excel=excel)[0].iloc[0]
        # On vérifie que 'test déclaré' figure dans row['processing_business_category'].
        self.assertIn("test déclaré", row["processing_business_category"])
        # On attend que row['processing_new_alert_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["processing_new_alert_candidate"])

    def test_completed_declaration_without_webp_is_divergence(self):
        # On garde dans excel le cas Excel dont le motif doit être interprété par la règle testée.
        excel = self.unexplained_excel()
        # On utilise ce texte pour excel['Traitement_visuel_images'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        excel["Traitement_visuel_images"] = "Terminé"
        # On récupère self.run_reconcile(excel=excel)[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile(excel=excel)[0].iloc[0]
        # On vérifie que 'Divergence' figure dans row['processing_business_category'].
        self.assertIn("Divergence", row["processing_business_category"])
        # On attend que row['processing_new_alert_candidate'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["processing_new_alert_candidate"])

    def test_access_error_not_absence_or_expected_gap(self):
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On utilise ce texte pour evidence['processing_error'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["processing_error"] = "Accès refusé"
        # On récupère self.run_reconcile(excel=self.unexplained_excel(), evidence=evidence, dec… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            excel=self.unexplained_excel(), evidence=evidence, decisions=self.decision()
        )[0].iloc[0]
        # On vérifie que 'Erreur technique' figure dans row['processing_business_category'].
        self.assertIn("Erreur technique", row["processing_business_category"])
        # On attend que row['has_technical_error'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["has_technical_error"])

    def test_missing_excel_does_not_drop_observed_acquisition(self):
        # On garde dans excel le lot ou la ligne Excel synthétique produit par ce helper de test.
        excel = self.excel()
        # On utilise ce texte pour excel['Acquisition_ID_normalise'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        excel["Acquisition_ID_normalise"] = "autre_id"
        # On récupère self.run_reconcile(excel=excel)[0] et on le garde dans result pour la suite.
        result = self.run_reconcile(excel=excel)[0]
        # On vérifie que len(result) correspond à 1.
        self.assertEqual(len(result), 1)
        # On vérifie que 'sans suivi Excel' figure dans
        # result.iloc[0]['processing_business_category'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "sans suivi Excel", result.iloc[0]["processing_business_category"]
        )

    def test_healthy_stocks_not_missing_output(self):
        # On récupère self.run_reconcile()[2].iloc[0] et on le garde dans passage pour la suite.
        passage = self.run_reconcile()[2].iloc[0]
        # On vérifie que 'Fichier de stocks présent' figure dans
        # passage['stocks_observation_interpretation'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "Fichier de stocks présent", passage["stocks_observation_interpretation"]
        )
        # On vérifie que 'règle confirmée' figure dans
        # passage['vitiparcel_business_rule_status'].casefold().
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "règle confirmée", passage["vitiparcel_business_rule_status"].casefold()
        )
        # On attend que passage['vitiparcel_ready_for_delivery'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(passage["vitiparcel_ready_for_delivery"])

    def test_exemption_does_not_exclude_shared_passage(self):
        # On répartit les valeurs renvoyées par self.run_reconcile entre (result, associations,
        # passages) ; leur ordre doit correspondre à celui prévu par cet appel.
        result, associations, passages = self.run_reconcile(decisions=self.decision())
        # On vérifie que len(passages) correspond à 1.
        self.assertEqual(len(passages), 1)
        # On vérifie que 'Fichier de stocks présent' figure dans
        # passages.iloc[0]['stocks_observation_interpretation'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "Fichier de stocks présent",
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            passages.iloc[0]["stocks_observation_interpretation"],
        )
        # On vérifie que 'processing_business_category' ne figure pas dans passages.columns.
        self.assertNotIn("processing_business_category", passages.columns)

    def test_technical_mapping_inconsistency_not_hidden_by_exemption(self):
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On utilise ce texte pour evidence['parcel_mapping_consistent'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        evidence["parcel_mapping_consistent"] = "False"
        # On récupère self.run_reconcile(excel=self.unexplained_excel(), evidence=evidence, dec… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            excel=self.unexplained_excel(), evidence=evidence, decisions=self.decision()
        )[0].iloc[0]
        # On attend que row['relationship_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["relationship_review_required"])

    def test_mixed_runs_rejected(self):
        # On garde dans passages les passages synthétiques du cas de test.
        passages = self.passages()
        # On utilise ce texte pour passages['checked_at'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        passages["checked_at"] = "2026-10-06T09:41:22Z"
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(passages=passages)

    def test_duplicate_evidence_rejected(self):
        # On garde dans evidence l’assemblage des tableaux suivant l’axe et les options indiqués.
        evidence = pd.concat([self.evidence(), self.evidence()], ignore_index=True)
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(evidence=evidence)

    def test_duplicate_association_rejected(self):
        # On garde dans associations l’assemblage des tableaux suivant l’axe et les options indiqués.
        associations = pd.concat(
            # On choisit si les index d’origine sont conservés ou reconstruits pendant l’assemblage.
            [self.associations(), self.associations()], ignore_index=True
        )
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(associations=associations)

    def test_missing_passage_report_row_rejected(self):
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(passages=self.passages().iloc[:0])

    def test_association_count_mismatch_rejected(self):
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On utilise ce texte pour evidence['passage_link_count'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["passage_link_count"] = "2"
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(evidence=evidence)

    def test_processing_in_progress_not_an_omission(self):
        # On garde dans excel le cas Excel dont le motif doit être interprété par la règle testée.
        excel = self.unexplained_excel()
        # On utilise ce texte pour excel['Traitement_visuel_images'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        excel["Traitement_visuel_images"] = "En cours"
        # On récupère self.run_reconcile(excel=excel)[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile(excel=excel)[0].iloc[0]
        # On vérifie que 'Avancement déclaré' figure dans row['processing_business_category'].
        self.assertIn("Avancement déclaré", row["processing_business_category"])
        # On attend que row['processing_new_alert_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["processing_new_alert_candidate"])

    def test_no_passage_link_is_not_technical_error(self):
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On utilise ce texte pour evidence['found_in_passage_mapping'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["found_in_passage_mapping"] = "False"
        # On utilise ce texte pour evidence['passage_link_count'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["passage_link_count"] = "0"
        # On utilise ce texte pour evidence['found_in_parcel_mapping'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["found_in_parcel_mapping"] = "False"
        # On récupère self.run_reconcile(excel=self.unexplained_excel(), evidence=evidence, ass… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            excel=self.unexplained_excel(),
            evidence=evidence,
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            associations=self.associations().iloc[:0],
            # On fournit les passages via le paramètre passages de cet appel.
            passages=self.passages().iloc[:0],
        )[0].iloc[0]
        # On attend que row['has_technical_error'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["has_technical_error"])
        # On attend que row['relationship_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["relationship_review_required"])

    def test_main_reads_only_csv_and_writes_local_outputs(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as folder:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(folder)
            # On prépare le dossier root / 'data' avec les règles de création indiquées ; aucun
            # résultat métier n’est encore produit par cette création.
            (root / "data").mkdir()
            # On rassemble dans frames les 4 éléments explicitement indiqués pour ce cas d’essai.
            frames = [
                self.excel(),
                self.evidence(),
                self.associations(),
                self.passages(),
            ]
            # On prépare paths comme liste vide ; on la remplira au fil des opérations suivantes.
            paths = []
            # On parcourt zip(['excel', 'evidence', 'associations', 'passages'], frames) ; (name,
            # frame) désigne l’élément courant de ce scénario.
            for name, frame in zip(
                ["excel", "evidence", "associations", "passages"], frames
            ):
                # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier
                # n’est créé par cette construction.
                path = root / f"{name}.csv"
                # On appelle frame.to_csv avec path.
                frame.to_csv(path, index=False)
                # On ajoute path à la fin de paths ; les éléments précédents restent conservés.
                paths.append(path)
            # On indexe before par p.name ; chaque clé sera associée à p.read_bytes(). Une même clé ne
            # peut garder qu’une valeur.
            before = {p.name: p.read_bytes() for p in paths}
            # On rassemble dans args les 12 éléments explicitement indiqués pour ce cas d’essai.
            args = [
                "--vineyard",
                "VignobleTest",
                "--reference",
                str(paths[0]),
                "--evidence",
                str(paths[1]),
                "--associations",
                str(paths[2]),
                "--passages",
                str(paths[3]),
                "--output-dir",
                str(root / "data/results"),
            ]
            # On remplace temporairement r dans ce bloc de test ; le réglage initial sera rétabli à sa
            # sortie.
            with patch.object(r, "PROJECT_ROOT", root), patch("builtins.print"):
                # On appelle r.main avec args.
                r.main(args)
            # On garde dans outputs une liste matérialisée à partir de (root /
            # 'data/results').glob('*.csv').
            outputs = list((root / "data/results").glob("*.csv"))
            # On vérifie que len(outputs) correspond à 3.
            self.assertEqual(len(outputs), 3)
            # On vérifie que before correspond à {p.name: p.read_bytes() for p in paths}.
            self.assertEqual(before, {p.name: p.read_bytes() for p in paths})

    def test_output_outside_project_data_rejected(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as folder:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(folder)
            # On prépare paths comme liste vide ; on la remplira au fil des opérations suivantes.
            paths = []
            # On parcourt zip(['excel', 'evidence', 'associations', 'passages'], [self.excel(), sel… ;
            # (name, frame) désigne l’élément courant de ce scénario.
            for name, frame in zip(
                ["excel", "evidence", "associations", "passages"],
                [self.excel(), self.evidence(), self.associations(), self.passages()],
            ):
                # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier
                # n’est créé par cette construction.
                path = root / f"{name}.csv"
                # On appelle frame.to_csv avec path.
                frame.to_csv(path, index=False)
                # On ajoute path à la fin de paths ; les éléments précédents restent conservés.
                paths.append(path)
            # On remplace temporairement r dans ce bloc de test ; le réglage initial sera rétabli à sa
            # sortie.
            with patch.object(r, "PROJECT_ROOT", root), self.assertRaises(ValueError):
                # On appelle r.main avec ['--vineyard', 'VignobleTest', '--reference', str(paths[0]),
                # '--evidence', str(paths[1]),….
                r.main(
                    [
                        "--vineyard",
                        "VignobleTest",
                        "--reference",
                        str(paths[0]),
                        "--evidence",
                        str(paths[1]),
                        "--associations",
                        str(paths[2]),
                        "--passages",
                        str(paths[3]),
                        "--output-dir",
                        str(root / "forbidden"),
                    ]
                )

    def test_completely_missing_excel_preserves_live_row(self):
        # On récupère self.run_reconcile(excel=self.excel().iloc[:0])[0] et on le garde dans result
        # pour la suite.
        result = self.run_reconcile(excel=self.excel().iloc[:0])[0]
        # On vérifie que len(result) correspond à 1.
        self.assertEqual(len(result), 1)
        # On vérifie que 'sans suivi Excel' figure dans
        # result.iloc[0]['processing_business_category'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "sans suivi Excel", result.iloc[0]["processing_business_category"]
        )

    def test_unknown_boolean_not_silently_missing_proof(self):
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On garde pd.NA sous le nom evidence['processing_has_webp_both_sides'] ; cette affectation ne
        # copie pas à elle seule un objet mutable.
        evidence["processing_has_webp_both_sides"] = pd.NA
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(evidence=evidence)

    def test_run_id_selects_exact_files_without_nas_access(self):
        # On utilise un dossier temporaire pour cet essai ; les fichiers produits ici ne sont pas ceux
        # de la production.
        with tempfile.TemporaryDirectory() as folder:
            # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le
            # fichier existe.
            root = Path(folder)
            # On prépare le dossier root / 'data' avec les règles de création indiquées ; aucun
            # résultat métier n’est encore produit par cette création.
            (root / "data").mkdir()
            # On assemble les morceaux du chemin reference avec l’opérateur / de pathlib ; aucun
            # fichier n’est créé par cette construction.
            reference = root / "reference.csv"
            # On appelle self.excel().to_csv avec reference.
            self.excel().to_csv(reference, index=False)
            # On parcourt zip(['evidence', 'associations', 'passages'], [self.evidence(), self.asso… ;
            # (label, frame) désigne l’élément courant de ce scénario.
            for label, frame in zip(
                ["evidence", "associations", "passages"],
                [self.evidence(), self.associations(), self.passages()],
            ):
                # On appelle frame.to_csv avec root /
                # f'vignobletest_live_nas_{label}_2026-10-05T09-41-22Z.csv'.
                frame.to_csv(
                    root / f"vignobletest_live_nas_{label}_2026-10-05T09-41-22Z.csv",
                    index=False,
                )
            # On remplace temporairement r dans ce bloc de test ; le réglage initial sera rétabli à sa
            # sortie.
            with patch.object(r, "PROJECT_ROOT", root), patch("builtins.print"):
                # On appelle r.main avec ['--vineyard', 'VignobleTest', '--reference', str(reference),
                # '--run-id', '2026-10-05T09-….
                r.main(
                    [
                        "--vineyard",
                        "VignobleTest",
                        "--reference",
                        str(reference),
                        "--run-id",
                        "2026-10-05T09-41-22Z",
                        "--input-dir",
                        str(root),
                        "--output-dir",
                        str(root / "data/results"),
                    ]
                )
            # On vérifie que len(list((root / 'data/results').glob('*.csv'))) correspond à 3.
            self.assertEqual(len(list((root / "data/results").glob("*.csv"))), 3)

    def test_waiting_status_excluded_even_with_non_statue(self):
        # On récupère self.run_reconcile()[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile()[0].iloc[0]
        # On attend que row['excluded_by_excel_status'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["excluded_by_excel_status"])
        # On attend que row['eligible_for_new_anomaly_checks'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["eligible_for_new_anomaly_checks"])
        # On attend que row['acquisition_new_anomaly_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["acquisition_new_anomaly_candidate"])
        # On attend que row['processing_decision_required'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["processing_decision_required"])
        # On vérifie que 'Aucune vérification' figure dans row['processing_next_action'].
        self.assertIn("Aucune vérification", row["processing_next_action"])

    def test_autre_status_excluded(self):
        # On garde dans excel le cas Excel dont le motif doit être interprété par la règle testée.
        excel = self.unexplained_excel()
        # On utilise ce texte pour excel['Statut_pipeline'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel["Statut_pipeline"] = "Autre"
        # On récupère self.run_reconcile(excel=excel)[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile(excel=excel)[0].iloc[0]
        # On attend que row['excluded_by_excel_status'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["excluded_by_excel_status"])
        # On attend que row['processing_new_alert_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["processing_new_alert_candidate"])

    def test_stage_waiting_excludes_even_if_pipeline_status_not_updated(self):
        # On garde dans excel le cas Excel dont le motif doit être interprété par la règle testée.
        excel = self.unexplained_excel()
        # On utilise ce texte pour excel['VitiMap'] ; il ne dépend pas d’une valeur récupérée ailleurs
        # à cet endroit.
        excel["VitiMap"] = "En attente"
        # On récupère self.run_reconcile(excel=excel)[0].iloc[0] et on le garde dans row pour la suite.
        row = self.run_reconcile(excel=excel)[0].iloc[0]
        # On attend que row['excluded_by_excel_status'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["excluded_by_excel_status"])

    def test_excluded_mapping_gap_not_sent_for_verification(self):
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On utilise ce texte pour evidence['parcel_mapping_consistent'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        evidence["parcel_mapping_consistent"] = "False"
        # On récupère self.run_reconcile(evidence=evidence)[0].iloc[0] et on le garde dans row pour la
        # suite.
        row = self.run_reconcile(evidence=evidence)[0].iloc[0]
        # On attend que row['relationship_review_required'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["relationship_review_required"])
        # On attend que row['acquisition_new_anomaly_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["acquisition_new_anomaly_candidate"])
        # On vérifie que row['parcel_mapping_consistent'] correspond à 'False'.
        self.assertEqual(row["parcel_mapping_consistent"], "False")

    def test_error_observation_preserved_but_no_follow_up_on_excluded_case(self):
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On utilise ce texte pour evidence['processing_error'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["processing_error"] = "Accès refusé"
        # On récupère self.run_reconcile(evidence=evidence)[0].iloc[0] et on le garde dans row pour la
        # suite.
        row = self.run_reconcile(evidence=evidence)[0].iloc[0]
        # On attend que row['has_technical_error'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["has_technical_error"])
        # On attend que row['technical_review_required'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["technical_review_required"])
        # On attend que row['acquisition_new_anomaly_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["acquisition_new_anomaly_candidate"])

    def test_waiting_rule_has_priority_over_explicit_yes_decision(self):
        # On récupère self.run_reconcile(decisions=self.decision('oui'))[0].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(decisions=self.decision("oui"))[0].iloc[0]
        # On attend que row['excluded_by_excel_status'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["excluded_by_excel_status"])
        # On vérifie que 'Hors contrôles' figure dans row['processing_expectation'].
        self.assertIn("Hors contrôles", row["processing_expectation"])

    def test_passage_only_linked_to_excluded_acquisitions_not_reviewed(self):
        # On garde dans passages les passages synthétiques du cas de test.
        passages = self.passages()
        # On utilise ce texte pour passages['stocks_json_exists'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        passages["stocks_json_exists"] = "False"
        # On récupère self.run_reconcile(passages=passages)[2].iloc[0] et on le garde dans row pour la
        # suite.
        row = self.run_reconcile(passages=passages)[2].iloc[0]
        # On vérifie que row['eligible_acquisitions_count'] correspond à 0.
        self.assertEqual(row["eligible_acquisitions_count"], 0)
        # On attend que row['passage_review_candidate'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["passage_review_candidate"])
        # On vérifie que row['stocks_json_exists'] correspond à 'False'.
        self.assertEqual(row["stocks_json_exists"], "False")

    def test_shared_passage_remains_eligible_with_one_non_excluded_acquisition(self):
        # On garde dans excel le lot ou la ligne Excel synthétique produit par ce helper de test.
        excel = self.excel()
        # On garde dans second le cas Excel dont le motif doit être interprété par la règle testée.
        second = self.unexplained_excel()
        # On utilise ce texte pour second['VitiParcel'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        second["VitiParcel"] = "Terminé"
        # On utilise ce texte pour other ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        other = "VignobleTest_C01_V1_2026-06-04T11-01-30"
        # On garde other sous le nom second['Acquisition_ID_normalise'] ; cette affectation ne copie
        # pas à elle seule un objet mutable.
        second["Acquisition_ID_normalise"] = other
        # On garde dans second['Acquisition_ID'] le résultat du remplacement demandé sur
        # second['Acquisition_ID'].str.
        second["Acquisition_ID"] = second["Acquisition_ID"].str.replace(
            self.acquisition, other, regex=False
        )
        # On garde dans excel l’assemblage des tableaux suivant l’axe et les options indiqués.
        excel = pd.concat([excel, second], ignore_index=True)
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On garde dans e2 les constats synthétiques construits pour cette acquisition.
        e2 = self.evidence()
        # On garde other sous le nom e2['acquisition_id_normalise'] ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        e2["acquisition_id_normalise"] = other
        # On garde dans evidence l’assemblage des tableaux suivant l’axe et les options indiqués.
        evidence = pd.concat([evidence, e2], ignore_index=True)
        # On garde dans associations les associations synthétiques entre acquisitions et passages.
        associations = self.associations()
        # On garde dans a2 les associations synthétiques entre acquisitions et passages.
        a2 = self.associations()
        # On garde other sous le nom a2['acquisition_id_normalise'] ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        a2["acquisition_id_normalise"] = other
        # On garde dans associations l’assemblage des tableaux suivant l’axe et les options indiqués.
        associations = pd.concat([associations, a2], ignore_index=True)
        # On garde dans passages les passages synthétiques du cas de test.
        passages = self.passages()
        # On utilise ce texte pour passages['stocks_json_exists'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        passages["stocks_json_exists"] = "False"
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations, passages=passages
        )[2].iloc[0]
        # On vérifie que row['eligible_acquisitions_count'] correspond à 1.
        self.assertEqual(row["eligible_acquisitions_count"], 1)
        # On vérifie que row['excluded_acquisitions_count'] correspond à 1.
        self.assertEqual(row["excluded_acquisitions_count"], 1)
        # On attend que row['passage_review_candidate'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["passage_review_candidate"])

    def mapping_case(self):
        # On garde dans excel le cas Excel dont le motif doit être interprété par la règle testée.
        excel = self.unexplained_excel()
        # On utilise ce texte pour excel.loc[0, 'Problématique'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        excel.loc[0, "Problématique"] = "ERREUR_MAPPING"
        # On utilise ce texte pour excel.loc[0, 'Commentaires'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        excel.loc[0, "Commentaires"] = (
            'Parcelle "ParcelleA" est mappée alors qu’il n’y a pas d’acquisition dessus'
        )
        # On utilise ce texte pour excel.loc[0, 'Statut_Resolution'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        excel.loc[0, "Statut_Resolution"] = "✅ Exploitable"
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On utilise ce texte pour evidence['processing_has_webp_images'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        evidence["processing_has_webp_images"] = "True"
        # On utilise ce texte pour evidence['processing_has_webp_both_sides'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        evidence["processing_has_webp_both_sides"] = "True"
        # On utilise ce texte pour evidence['parcel_mapping_consistent'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        evidence["parcel_mapping_consistent"] = "False"
        # On garde dans associations les associations synthétiques entre acquisitions et passages.
        associations = self.associations()
        # On utilise ce texte pour associations['parcel_mapping_consistent'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        associations["parcel_mapping_consistent"] = "False"
        # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return excel, evidence, associations

    def test_documented_same_mapping_not_new_alert(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On répartit les valeurs renvoyées par self.run_reconcile entre (result, links, _) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        result, links, _ = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations
        )
        # On récupère result.iloc[0] et on le garde dans row pour la suite.
        row = result.iloc[0]
        # On attend que row['relationship_known_documented'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["relationship_known_documented"])
        # On attend que row['relationship_review_required'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["relationship_review_required"])
        # On attend que row['acquisition_new_anomaly_candidate'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["acquisition_new_anomaly_candidate"])
        # On vérifie que row['parcel_mapping_consistent'] correspond à 'False'.
        self.assertEqual(row["parcel_mapping_consistent"], "False")
        # On vérifie que row['business_resolution_declaration'] correspond à '✅ Exploitable'.
        self.assertEqual(row["business_resolution_declaration"], "✅ Exploitable")
        # On attend que row['eligible_for_new_anomaly_checks'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["eligible_for_new_anomaly_checks"])
        # On vérifie que 'connu et documenté' figure dans
        # links.iloc[0]['relationship_business_category'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "connu et documenté", links.iloc[0]["relationship_business_category"]
        )

    def test_documented_mapping_does_not_hide_missing_png(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On utilise ce texte pour evidence['raw_has_full_size_both_sides'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        evidence["raw_has_full_size_both_sides"] = "False"
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations
        )[0].iloc[0]
        # On attend que row['relationship_review_required'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["relationship_review_required"])
        # On attend que row['raw_evidence_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["raw_evidence_review_required"])
        # On attend que row['acquisition_new_anomaly_candidate'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["acquisition_new_anomaly_candidate"])

    def test_documented_mapping_does_not_hide_webp_divergence(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On utilise ce texte pour excel['Traitement_visuel_images'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        excel["Traitement_visuel_images"] = "Terminé"
        # On utilise ce texte pour evidence['processing_has_webp_both_sides'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        evidence["processing_has_webp_both_sides"] = "False"
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations
        )[0].iloc[0]
        # On attend que row['processing_new_alert_candidate'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["processing_new_alert_candidate"])
        # On attend que row['acquisition_new_anomaly_candidate'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["acquisition_new_anomaly_candidate"])

    def test_documented_mapping_does_not_hide_read_error(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On utilise ce texte pour evidence['raw_error'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        evidence["raw_error"] = "Accès refusé"
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations
        )[0].iloc[0]
        # On attend que row['technical_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["technical_review_required"])
        # On attend que row['acquisition_new_anomaly_candidate'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["acquisition_new_anomaly_candidate"])

    def test_different_parcel_comment_does_not_cover_gap(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On garde dans excel['Commentaires'] le résultat du remplacement demandé sur
        # excel['Commentaires'].str.
        excel["Commentaires"] = excel["Commentaires"].str.replace(
            "ParcelleA", "ParcelleB"
        )
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations
        )[0].iloc[0]
        # On attend que row['relationship_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["relationship_review_required"])
        # On attend que row['relationship_known_documented'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["relationship_known_documented"])

    def test_exploitable_alone_does_not_cover_mapping(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On commence excel['Commentaires'] avec un texte vide, à compléter uniquement si la suite
        # apporte une information.
        excel["Commentaires"] = ""
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations
        )[0].iloc[0]
        # On attend que row['relationship_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["relationship_review_required"])

    def test_problem_and_comment_must_be_on_same_source_row(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On sélectionne dans excel.loc les éléments désignés par (0, 'Problématique') ; excel.loc[1,
        # 'Problématique'] recevra cette sélection.
        excel.loc[1, "Problématique"] = excel.loc[0, "Problématique"]
        # On commence excel.loc[0, 'Problématique'] avec un texte vide, à compléter uniquement si la
        # suite apporte une information.
        excel.loc[0, "Problématique"] = ""
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations
        )[0].iloc[0]
        # On attend que row['relationship_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["relationship_review_required"])

    def test_mapping_documentation_does_not_cover_missing_link(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On utilise ce texte pour evidence['found_in_parcel_mapping'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["found_in_parcel_mapping"] = "False"
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations
        )[0].iloc[0]
        # On attend que row['relationship_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["relationship_review_required"])

    def test_partial_documentation_keeps_new_mapping_gap(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On garde dans second une copie de associations pour travailler sur cet objet séparément.
        second = associations.copy()
        # On utilise ce texte pour second['parcel_name'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        second["parcel_name"] = "ParcelleB"
        # On utilise ce texte pour second['passage_name'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        second["passage_name"] = "ParcelleB_2026-06-04"
        # On garde dans associations l’assemblage des tableaux suivant l’axe et les options indiqués.
        associations = pd.concat([associations, second], ignore_index=True)
        # On garde dans passages les passages synthétiques du cas de test.
        passages = self.passages()
        # On garde dans second_passage une copie de passages pour travailler sur cet objet séparément.
        second_passage = passages.copy()
        # On utilise ce texte pour second_passage['parcel_name'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        second_passage["parcel_name"] = "ParcelleB"
        # On utilise ce texte pour second_passage['passage_name'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        second_passage["passage_name"] = "ParcelleB_2026-06-04"
        # On garde dans passages l’assemblage des tableaux suivant l’axe et les options indiqués.
        passages = pd.concat([passages, second_passage], ignore_index=True)
        # On utilise ce texte pour evidence['passage_link_count'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["passage_link_count"] = "2"
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations, passages=passages
        )[0].iloc[0]
        # On vérifie que json.loads(row['relationship_documented_parcels_json']) correspond à
        # ['ParcelleA'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            json.loads(row["relationship_documented_parcels_json"]), ["ParcelleA"]
        )
        # On attend que row['relationship_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["relationship_review_required"])
        # On attend que row['acquisition_new_anomaly_candidate'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["acquisition_new_anomaly_candidate"])

    def test_false_summary_without_detailed_gap_remains_review(self):
        # On répartit les valeurs renvoyées par self.mapping_case entre (excel, evidence, associations)
        # ; leur ordre doit correspondre à celui prévu par cet appel.
        excel, evidence, associations = self.mapping_case()
        # On utilise ce texte pour associations['parcel_mapping_consistent'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        associations["parcel_mapping_consistent"] = "True"
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=associati… et on
        # le garde dans row pour la suite.
        row = self.run_reconcile(
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            excel=excel, evidence=evidence, associations=associations
        )[0].iloc[0]
        # On attend que row['relationship_review_required'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["relationship_review_required"])

    def passage_case(self, status="Terminé", stocks=False, non_healthy=False, count=2):
        # On garde dans excel le cas Excel dont le motif doit être interprété par la règle testée.
        excel = self.unexplained_excel()
        # On garde l’état du traitement sous le nom excel['VitiParcel'] ; cette affectation ne copie
        # pas à elle seule un objet mutable.
        excel["VitiParcel"] = status
        # On garde dans passages les passages synthétiques du cas de test.
        passages = self.passages()
        # On garde dans passages['stocks_json_exists'] la représentation textuelle de stocks.
        passages["stocks_json_exists"] = str(stocks)
        # On garde dans passages['has_non_healthy_status'] la représentation textuelle de non_healthy.
        passages["has_non_healthy_status"] = str(non_healthy)
        # On garde dans passages['stock_status_count'] la représentation textuelle de count if stocks
        # else 0.
        passages["stock_status_count"] = str(count if stocks else 0)
        # On garde dans passages['vitiparcel_created'] la représentation textuelle de stocks and
        # non_healthy.
        passages["vitiparcel_created"] = str(stocks and non_healthy)
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return excel, passages

    def test_passage_done_missing_stocks_is_divergence(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case()
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['passage_excel_vitiparcel_done'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["passage_excel_vitiparcel_done"])
        # On attend que row['passage_vitiparcel_divergence'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["passage_vitiparcel_divergence"])
        # On attend que row['passage_review_candidate'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["passage_review_candidate"])
        # On vérifie que 'stocks absent' figure dans row['passage_business_category'].
        self.assertIn("stocks absent", row["passage_business_category"])
        # On attend que row['vitiparcel_ready_for_delivery'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["vitiparcel_ready_for_delivery"])
        # On vérifie que len(json.loads(row['passage_excel_done_sources_json'])) correspond à 1.
        self.assertEqual(len(json.loads(row["passage_excel_done_sources_json"])), 1)

    def test_passage_done_only_healthy_is_divergence(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case(stocks=True)
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['passage_vitiparcel_divergence'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["passage_vitiparcel_divergence"])
        # On vérifie que 'critère du livrable prêt non satisfait' figure dans
        # row['passage_business_category'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "critère du livrable prêt non satisfait", row["passage_business_category"]
        )
        # On vérifie que row['stocks_json_exists'] correspond à 'True'.
        self.assertEqual(row["stocks_json_exists"], "True")

    def test_passage_done_non_healthy_confirms_ready(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case(stocks=True, non_healthy=True)
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['vitiparcel_ready_for_delivery'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["vitiparcel_ready_for_delivery"])
        # On attend que row['passage_review_candidate'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["passage_review_candidate"])
        # On vérifie que row['vitiparcel_created'] correspond à 'True'.
        self.assertEqual(row["vitiparcel_created"], "True")

    def test_passage_empty_excel_missing_stocks_no_alert(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case(status="")
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On vérifie que row['eligible_acquisitions_count'] correspond à 1.
        self.assertEqual(row["eligible_acquisitions_count"], 1)
        # On attend que row['passage_review_candidate'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["passage_review_candidate"])
        # On vérifie que 'non renseignée' figure dans row['passage_business_category'].
        self.assertIn("non renseignée", row["passage_business_category"])

    def test_passage_ready_without_excel_declaration_keeps_proof(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case(status="", stocks=True, non_healthy=True)
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['vitiparcel_ready_for_delivery'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["vitiparcel_ready_for_delivery"])
        # On attend que row['passage_excel_vitiparcel_done'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["passage_excel_vitiparcel_done"])
        # On attend que row['passage_review_candidate'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["passage_review_candidate"])

    def test_passage_done_empty_statuses_not_ready(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case(stocks=True, count=0)
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['passage_vitiparcel_divergence'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["passage_vitiparcel_divergence"])
        # On vérifie que 'aucun statut reconnu' figure dans row['passage_business_category'].
        self.assertIn("aucun statut reconnu", row["passage_business_category"])

    def test_passage_read_error_not_reported_as_absence(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case()
        # On utilise ce texte pour passages['vitiparcel_error'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        passages["vitiparcel_error"] = "Accès refusé"
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['vitiparcel_ready_verifiable'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["vitiparcel_ready_verifiable"])
        # On attend que pd.isna(row['vitiparcel_ready_for_delivery']) soit évalué comme vrai pour ce
        # cas de test.
        self.assertTrue(pd.isna(row["vitiparcel_ready_for_delivery"]))
        # On attend que row['passage_vitiparcel_divergence'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["passage_vitiparcel_divergence"])
        # On attend que row['passage_technical_review_required'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["passage_technical_review_required"])

    def test_passage_excluded_done_does_not_trigger_alert(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case()
        # On utilise ce texte pour excel['Statut_pipeline'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel["Statut_pipeline"] = "En attente"
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['passage_excel_vitiparcel_done'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["passage_excel_vitiparcel_done"])
        # On attend que row['passage_review_candidate'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["passage_review_candidate"])
        # On vérifie que 'Hors contrôles' figure dans row['passage_business_category'].
        self.assertIn("Hors contrôles", row["passage_business_category"])

    def test_passage_done_on_one_side_blank_other_is_applicable(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case()
        # On commence excel.loc[1, 'VitiParcel'] avec un texte vide, à compléter uniquement si la suite
        # apporte une information.
        excel.loc[1, "VitiParcel"] = ""
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['passage_excel_vitiparcel_done'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["passage_excel_vitiparcel_done"])
        # On attend que row['passage_review_candidate'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["passage_review_candidate"])

    def test_passage_contradictory_side_status_is_ambiguous(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case()
        # On utilise ce texte pour excel.loc[1, 'VitiParcel'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        excel.loc[1, "VitiParcel"] = "En cours"
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['passage_excel_vitiparcel_ambiguous'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["passage_excel_vitiparcel_ambiguous"])
        # On attend que row['passage_excel_vitiparcel_done'] soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(row["passage_excel_vitiparcel_done"])
        # On attend que row['passage_review_candidate'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["passage_review_candidate"])

    def test_passage_multi_link_done_not_propagated(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case()
        # On garde dans associations les associations synthétiques entre acquisitions et passages.
        associations = self.associations()
        # On garde dans second_link une copie de associations pour travailler sur cet objet séparément.
        second_link = associations.copy()
        # On utilise ce texte pour second_link['parcel_name'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        second_link["parcel_name"] = "ParcelleB"
        # On utilise ce texte pour second_link['passage_name'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        second_link["passage_name"] = "ParcelleB_2026-06-04"
        # On garde dans second_passage une copie de passages pour travailler sur cet objet séparément.
        second_passage = passages.copy()
        # On utilise ce texte pour second_passage['parcel_name'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        second_passage["parcel_name"] = "ParcelleB"
        # On utilise ce texte pour second_passage['passage_name'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        second_passage["passage_name"] = "ParcelleB_2026-06-04"
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On utilise ce texte pour evidence['passage_link_count'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["passage_link_count"] = "2"
        # On récupère self.run_reconcile(excel=excel, evidence=evidence, associations=pd.concat… et on
        # le garde dans rows pour la suite.
        rows = self.run_reconcile(
            excel=excel,
            evidence=evidence,
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            associations=pd.concat([associations, second_link], ignore_index=True),
            # On fournit les passages via le paramètre passages de cet appel.
            passages=pd.concat([passages, second_passage], ignore_index=True),
        )[2]
        # On attend que rows['passage_excel_vitiparcel_ambiguous'].all() soit évalué comme vrai pour ce
        # cas de test.
        self.assertTrue(rows["passage_excel_vitiparcel_ambiguous"].all())
        # On attend que rows['passage_excel_vitiparcel_done'].any() soit évalué comme faux pour ce cas
        # de test.
        self.assertFalse(rows["passage_excel_vitiparcel_done"].any())
        # On attend que rows['passage_review_candidate'].any() soit évalué comme faux pour ce cas de
        # test.
        self.assertFalse(rows["passage_review_candidate"].any())

    def test_passage_missing_vitimap_remains_alert_without_done(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case(status="")
        # On utilise ce texte pour passages['vitimap_created'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        passages["vitimap_created"] = "False"
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['passage_structure_review_required'] soit évalué comme vrai pour ce cas de
        # test.
        self.assertTrue(row["passage_structure_review_required"])
        # On attend que row['passage_review_candidate'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["passage_review_candidate"])

    def test_passage_in_progress_missing_stocks_not_omission(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case(status="En cours")
        # On récupère self.run_reconcile(excel=excel, passages=passages)[2].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.run_reconcile(excel=excel, passages=passages)[2].iloc[0]
        # On attend que row['passage_review_candidate'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["passage_review_candidate"])
        # On vérifie que 'fin non déclarée' figure dans row['passage_business_category'].
        self.assertIn("fin non déclarée", row["passage_business_category"])

    def test_passage_unknown_boolean_rejected(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case()
        # On utilise ce texte pour passages['stocks_json_exists'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        passages["stocks_json_exists"] = "inconnu"
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(excel=excel, passages=passages)

    def test_passage_invalid_status_count_rejected(self):
        # On répartit les valeurs renvoyées par self.passage_case entre (excel, passages) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        excel, passages = self.passage_case()
        # On utilise ce texte pour passages['stock_status_count'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        passages["stock_status_count"] = "-1"
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle self.run_reconcile sans argument positionnel.
            self.run_reconcile(excel=excel, passages=passages)

    def test_console_summary_sections_and_counts_without_mutation(self):
        # On garde dans results les résultats du rapprochement sur les petits jeux de données du test.
        results = self.run_reconcile()
        # On construit before comme une liste à partir de frame.copy(deep=True), pour chaque frame de
        # results.
        before = [frame.copy(deep=True) for frame in results]
        # On construit paths comme une liste à partir de Path('/local/data') / f'{label}.csv', pour
        # chaque label de ('acquisitions', 'associations', 'passages').
        paths = [
            Path("/local/data") / f"{label}.csv"
            for label in ("acquisitions", "associations", "passages")
        ]
        # On garde dans capture un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        capture = io.StringIO()
        # On remplace temporairement 'sys.stdout' dans ce bloc de test ; le réglage initial sera
        # rétabli à sa sortie.
        with patch("sys.stdout", capture):
            # On appelle r.print_summary avec results.
            r.print_summary(results, paths, "VignobleTest", "2026-10-05T09-41-22Z")
        # On garde dans output la valeur renvoyée par capture.getvalue.
        output = capture.getvalue()
        # On vérifie que '1. ACQUISITIONS' figure dans output.
        self.assertIn("1. ACQUISITIONS", output)
        # On vérifie que '2. PASSAGES' figure dans output.
        self.assertIn("2. PASSAGES", output)
        # On vérifie que '1 acquisitions  |  1 associations  |  1 passages distincts' figure dans
        # output.
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "1 acquisitions  |  1 associations  |  1 passages distincts", output
        )
        # On vérifie que 'FICHIERS LOCAUX' figure dans output.
        self.assertIn("FICHIERS LOCAUX", output)
        # On vérifie que 'passages.csv' figure dans output.
        self.assertIn("passages.csv", output)
        # On parcourt zip(results, before) ; (frame, original) désigne l’élément courant de ce
        # scénario.
        for frame, original in zip(results, before):
            # On contrôle le résultat avec assert_frame_equal et les valeurs attendues indiquées juste
            # dessous.
            pd.testing.assert_frame_equal(frame, original)

    def test_console_summary_works_without_emoji_support(self):
        class AsciiCapture(io.StringIO):
            @property
            def encoding(self):
                # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
                return "cp1252"

            def write(self, value):
                # On appelle value.encode avec self.encoding.
                value.encode(self.encoding)
                # On fournit à l’appelant la valeur renvoyée par super().write.
                return super().write(value)

        # On garde dans capture la valeur renvoyée par AsciiCapture.
        capture = AsciiCapture()
        # On remplace temporairement 'sys.stdout' dans ce bloc de test ; le réglage initial sera
        # rétabli à sa sortie.
        with patch("sys.stdout", capture):
            # On appelle r.print_summary avec self.run_reconcile().
            r.print_summary(self.run_reconcile(), [], "VignobleTest")
        # On vérifie que 'RAPPROCHEMENT EXCEL' figure dans capture.getvalue().
        self.assertIn("RAPPROCHEMENT EXCEL", capture.getvalue())

    def test_console_ambiguity_label_explains_multiple_passages(self):
        # On garde dans results une liste matérialisée à partir de self.run_reconcile().
        results = list(self.run_reconcile())
        # On garde dans passages une copie de results[2] pour travailler sur cet objet séparément.
        passages = results[2].copy()
        # On utilise ce texte pour passages['passage_business_category'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        passages["passage_business_category"] = (
            "Déclaration Vitiparcel ambiguë — attente du passage non confirmée"
        )
        # On prépare une représentation JSON ; les options ci-dessous fixent les détails de
        # sérialisation.
        passages["passage_excel_ambiguous_sources_json"] = json.dumps(
            [{"ambiguity_reason": "Acquisition associée à plusieurs passages"}]
        )
        # On gardes passages sous le nom results[2] ; cette affectation ne copie pas à elle seule un
        # objet mutable.
        results[2] = passages
        # On garde dans capture un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        capture = io.StringIO()
        # On remplace temporairement 'sys.stdout' dans ce bloc de test ; le réglage initial sera
        # rétabli à sa sortie.
        with patch("sys.stdout", capture):
            # On appelle r.print_summary avec results.
            r.print_summary(results, [], "VignobleTest")
        # On garde dans output la valeur renvoyée par capture.getvalue.
        output = capture.getvalue()
        # On vérifie que 'Acquisitions avec un écart de mapping déjà documenté dans Excel' figure
        # dans output.
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "Acquisitions avec un écart de mapping déjà documenté dans Excel", output
        )
        # On vérifie que 'acquisition liée à plusieurs passages' figure dans output.
        self.assertIn("acquisition liée à plusieurs passages", output)
        # On vérifie que 'ne précise pas à quel passage' figure dans output.
        self.assertIn("ne précise pas à quel passage", output)
        # On vérifie que 'pas sur les acquisitions' figure dans output.
        self.assertIn("pas sur les acquisitions", output)

    def test_console_lists_mapping_acquisition_and_targeted_passages(self):
        # On garde dans results une liste matérialisée à partir de self.run_reconcile().
        results = list(self.run_reconcile())
        # On garde dans acquisitions une copie de results[0] pour travailler sur cet objet séparément.
        acquisitions = results[0].copy()
        # On initialise acquisitions['relationship_known_documented'] à True ; les branches suivantes
        # pourront modifier cet état.
        acquisitions["relationship_known_documented"] = True
        # On utilise ce texte pour acquisitions['relationship_documented_parcels_json'] ; il ne dépend
        # pas d’une valeur récupérée ailleurs à cet endroit.
        acquisitions["relationship_documented_parcels_json"] = '["ParcelleA"]'
        # On gardes acquisitions sous le nom results[0] ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        results[0] = acquisitions
        # On rassemble dans categories les 5 éléments explicitement indiqués pour ce cas d’essai.
        categories = [
            "Déclaration Vitiparcel ambiguë — attente du passage non confirmée",
            "Divergence — Vitiparcel terminé déclaré, stocks absent",
            "Hors contrôles — toutes les acquisitions associées sont exclues",
            "Critère Vitiparcel prêt à livrer satisfait",
            "Attente Vitiparcel non renseignée — aucune nouvelle alerte automatique",
        ]
        # On prépare rows comme liste vide ; on la remplira au fil des opérations suivantes.
        rows = []
        # On parcourt categories en gardant aussi sa position dans (index, category) ; le comptage
        # commence à zéro.
        for index, category in enumerate(categories):
            # On garde dans row une copie de results[2].iloc[0] pour travailler sur cet objet
            # séparément.
            row = results[2].iloc[0].copy()
            # On garde category sous le nom row['passage_business_category'] ; cette affectation ne
            # copie pas à elle seule un objet mutable.
            row["passage_business_category"] = category
            # On prépare row['passage_name'] avec cette expression pour l’utiliser dans la suite du
            # traitement.
            row["passage_name"] = f"Target{index}_2026-06-04"
            # On garde dans row['passage_review_candidate'] le résultat de cette comparaison : index
            # correspond à 1.
            row["passage_review_candidate"] = index == 1
            # On choisit la valeur de row['passage_excel_ambiguous_sources_json'] selon ce test : index
            # correspond à 0. Les deux résultats possibles restent définis explicitement ici.
            row["passage_excel_ambiguous_sources_json"] = (
                json.dumps(
                    [{"ambiguity_reason": "Acquisition associée à plusieurs passages"}]
                )
                if index == 0
                else "[]"
            )
            # On ajoute row à la fin de rows ; les éléments précédents restent conservés.
            rows.append(row)
        # On garde dans results[2] un tableau pandas construit avec les données indiquées.
        results[2] = pd.DataFrame(rows)
        # On construit originals comme une liste à partir de frame.copy(deep=True), pour chaque frame
        # de results.
        originals = [frame.copy(deep=True) for frame in results]
        # On garde dans capture un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        capture = io.StringIO()
        # On remplace temporairement 'sys.stdout' dans ce bloc de test ; le réglage initial sera
        # rétabli à sa sortie.
        with patch("sys.stdout", capture):
            # On appelle r.print_summary avec results.
            r.print_summary(results, [], "VignobleTest")
        # On garde dans output la valeur renvoyée par capture.getvalue.
        output = capture.getvalue()
        # On vérifie que self.acquisition figure dans output.
        self.assertIn(self.acquisition, output)
        # On vérifie que 'Parcelle(s) concernée(s) : ParcelleA' figure dans output.
        self.assertIn("Parcelle(s) concernée(s) : ParcelleA", output)
        # On parcourt range(4) ; index désigne l’élément courant de ce scénario.
        for index in range(4):
            # Le candidat apparaît dans sa catégorie ET dans le récapitulatif.
            expected_count = 2 if index == 1 else 1
            # On vérifie que output.count(f'Target{index}_2026-06-04') correspond à expected_count.
            self.assertEqual(output.count(f"Target{index}_2026-06-04"), expected_count)
        # On récupère output.split('Passages candidats à une nouvelle vérification', 1)[1] et on le
        # garde dans candidate_summary pour la suite.
        candidate_summary = output.split(
            "Passages candidats à une nouvelle vérification", 1
        )[1]
        # On vérifie que 'Target1_2026-06-04' figure dans candidate_summary.
        self.assertIn("Target1_2026-06-04", candidate_summary)
        # On vérifie que 'Motif : Divergence' figure dans candidate_summary.
        self.assertIn("Motif : Divergence", candidate_summary)
        # On parcourt (0, 2, 3, 4) ; index désigne l’élément courant de ce scénario.
        for index in (0, 2, 3, 4):
            # On vérifie que f'Target{index}_2026-06-04' ne figure pas dans candidate_summary.
            self.assertNotIn(f"Target{index}_2026-06-04", candidate_summary)
        # On vérifie que 'Target4_2026-06-04' ne figure pas dans output.
        self.assertNotIn("Target4_2026-06-04", output)
        # On vérifie que 'tests déclarés ou statuts En attente / Autre' figure dans output.
        self.assertIn("tests déclarés ou statuts En attente / Autre", output)
        # On parcourt zip(originals, results) ; (original, frame) désigne l’élément courant de ce
        # scénario.
        for original, frame in zip(originals, results):
            # On contrôle le résultat avec assert_frame_equal et les valeurs attendues indiquées juste
            # dessous.
            pd.testing.assert_frame_equal(original, frame)

    def console_capture(self, results, run_id=None):
        # On garde dans capture un flux texte en mémoire, utilisable comme un fichier par le lecteur
        # CSV.
        capture = io.StringIO()
        # On remplace temporairement 'sys.stdout' dans ce bloc de test ; le réglage initial sera
        # rétabli à sa sortie.
        with patch("sys.stdout", capture):
            # On appelle r.print_summary avec results.
            r.print_summary(results, [], "VignobleTest", run_id)
        # On fournit à l’appelant la valeur renvoyée par capture.getvalue.
        return capture.getvalue()

    def no_passage_result(self, excluded=False):
        # On garde dans evidence les constats synthétiques construits pour cette acquisition.
        evidence = self.evidence()
        # On utilise ce texte pour evidence['found_in_passage_mapping'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["found_in_passage_mapping"] = "False"
        # On utilise ce texte pour evidence['passage_link_count'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        evidence["passage_link_count"] = "0"
        # WEBP présents : la candidature doit venir du rattachement seul.
        evidence["processing_has_webp_images"] = "True"
        # On utilise ce texte pour evidence['processing_has_webp_both_sides'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        evidence["processing_has_webp_both_sides"] = "True"
        # On choisit la valeur de excel selon ce test : excluded est évalué comme vrai. Les deux
        # résultats possibles restent définis explicitement ici.
        excel = self.excel() if excluded else self.unexplained_excel()
        # On choisit la valeur de excel['VitiMap'] selon ce test : la condition excluded n’est pas
        # remplie. Les deux résultats possibles restent définis explicitement ici.
        excel["VitiMap"] = "Terminé" if not excluded else "En attente"
        # On fournit à l’appelant les résultats du rapprochement sur les petits jeux de données du
        # test.
        return self.run_reconcile(
            excel=excel,
            evidence=evidence,
            # On fournit les associations entre acquisitions et passages via le paramètre associations
            # de cet appel.
            associations=self.associations().iloc[:0],
            # On fournit les passages via le paramètre passages de cet appel.
            passages=self.passages().iloc[:0],
        )

    def test_console_candidate_with_webp_explains_missing_passage(self):
        # On garde dans results la valeur renvoyée par self.no_passage_result.
        results = self.no_passage_result()
        # On construit originals comme une liste à partir de frame.copy(deep=True), pour chaque frame
        # de results.
        originals = [frame.copy(deep=True) for frame in results]
        # On garde dans output la sortie console capturée pour la vérifier sans la confondre avec le
        # résultat métier.
        output = self.console_capture(results)
        # On vérifie que self.acquisition figure dans output.
        self.assertIn(self.acquisition, output)
        # On vérifie que 'Aucun rattachement à un passage démontré' figure dans output.
        self.assertIn("Aucun rattachement à un passage démontré", output)
        # On vérifie que 'Vitimap=Terminé' figure dans output.
        self.assertIn("Vitimap=Terminé", output)
        # On vérifie que 'Traitement WEBP LEFT et RIGHT non démontré' ne figure pas dans output.
        self.assertNotIn("Traitement WEBP LEFT et RIGHT non démontré", output)
        # On parcourt zip(originals, results) ; (original, frame) désigne l’élément courant de ce
        # scénario.
        for original, frame in zip(originals, results):
            # On contrôle le résultat avec assert_frame_equal et les valeurs attendues indiquées juste
            # dessous.
            pd.testing.assert_frame_equal(original, frame)

    def test_console_no_passages_explicitly_warns_non_verifiable(self):
        # On garde dans output la sortie console capturée pour la vérifier sans la confondre avec le
        # résultat métier.
        output = self.console_capture(self.no_passage_result())
        # On vérifie que 'AUCUN PASSAGE IDENTIFIÉ' figure dans output.
        self.assertIn("AUCUN PASSAGE IDENTIFIÉ", output)
        # On vérifie que 'sorties non vérifiables' figure dans output.
        self.assertIn("sorties non vérifiables", output)
        # On vérifie que 'pas une validation des livrables' figure dans output.
        self.assertIn("pas une validation des livrables", output)
        # On vérifie que 'ni leur absence physique' figure dans output.
        self.assertIn("ni leur absence physique", output)

    def test_console_excluded_acquisition_not_in_candidate_list(self):
        # On garde dans output la sortie console capturée pour la vérifier sans la confondre avec le
        # résultat métier.
        output = self.console_capture(self.no_passage_result(excluded=True))
        # On vérifie que self.acquisition ne figure pas dans output.
        self.assertNotIn(self.acquisition, output)
        # On vérifie que 'AUCUN PASSAGE IDENTIFIÉ' figure dans output.
        self.assertIn("AUCUN PASSAGE IDENTIFIÉ", output)

    def test_display_reasons_can_show_multiple_independent_gaps(self):
        # On garde dans results la valeur renvoyée par self.no_passage_result.
        results = self.no_passage_result()
        # On garde dans row une copie de results[0].iloc[0] pour travailler sur cet objet séparément.
        row = results[0].iloc[0].copy()
        # On initialise row['raw_evidence_review_required'] à True ; les branches suivantes pourront
        # modifier cet état.
        row["raw_evidence_review_required"] = True
        # On initialise row['raw_has_full_size_both_sides'] à False ; les branches suivantes pourront
        # modifier cet état.
        row["raw_has_full_size_both_sides"] = False
        # On initialise row['processing_new_alert_candidate'] à True ; les branches suivantes pourront
        # modifier cet état.
        row["processing_new_alert_candidate"] = True
        # On utilise ce texte pour row['processing_business_category'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        row["processing_business_category"] = "Divergence WEBP"
        # On garde dans reasons le texte formé en réunissant les éléments avec ' ' comme séparateur.
        reasons = " ".join(r.acquisition_display_reasons(row))
        # On vérifie que 'rattachement à un passage' figure dans reasons.
        self.assertIn("rattachement à un passage", reasons)
        # On vérifie que 'Sauvegarde PNG' figure dans reasons.
        self.assertIn("Sauvegarde PNG", reasons)
        # On vérifie que 'Traitement WEBP' figure dans reasons.
        self.assertIn("Traitement WEBP", reasons)

    def test_display_raw_error_not_labelled_as_physical_absence(self):
        # On garde dans row une copie de self.no_passage_result()[0].iloc[0] pour travailler sur cet
        # objet séparément.
        row = self.no_passage_result()[0].iloc[0].copy()
        # On initialise row['relationship_review_required'] à False ; les branches suivantes pourront
        # modifier cet état.
        row["relationship_review_required"] = False
        # On initialise row['raw_evidence_review_required'] à True ; les branches suivantes pourront
        # modifier cet état.
        row["raw_evidence_review_required"] = True
        # On initialise row['found_in_raw_live'] à False ; les branches suivantes pourront modifier cet
        # état.
        row["found_in_raw_live"] = False
        # On utilise ce texte pour row['raw_error'] ; il ne dépend pas d’une valeur récupérée ailleurs
        # à cet endroit.
        row["raw_error"] = "Accès refusé"
        # On initialise row['technical_review_required'] à True ; les branches suivantes pourront
        # modifier cet état.
        row["technical_review_required"] = True
        # On utilise ce texte pour row['technical_errors'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        row["technical_errors"] = "Accès refusé"
        # On garde dans reasons le texte formé en réunissant les éléments avec ' ' comme séparateur.
        reasons = " ".join(r.acquisition_display_reasons(row))
        # On vérifie que 'Erreur technique' figure dans reasons.
        self.assertIn("Erreur technique", reasons)
        # On vérifie que 'Présence du dossier Brut non démontrée' ne figure pas dans reasons.
        self.assertNotIn("Présence du dossier Brut non démontrée", reasons)

    def test_display_extracts_id_from_selected_evidence_filename(self):
        # On garde dans path un objet chemin local ; sa construction seule ne prouve pas que le fichier
        # existe.
        path = Path("runs/pilote_live_nas_evidence_2026-10-05T13-56-23Z.csv")
        # On vérifie que r.extraction_id_from_path(path) correspond à '2026-10-05T13-56-23Z'.
        self.assertEqual(r.extraction_id_from_path(path), "2026-10-05T13-56-23Z")
        # On attend None pour r.extraction_id_from_path(Path('renamed.csv')) : aucune valeur n’est
        # confirmée dans ce cas.
        self.assertIsNone(r.extraction_id_from_path(Path("renamed.csv")))
        # On vérifie que r.extraction_id_from_path(Path('x_live_nas_evidence_2026-13-05T13-56-23Z.…
        # vaut None.
        self.assertIsNone(
            r.extraction_id_from_path(
                Path("x_live_nas_evidence_2026-13-05T13-56-23Z.csv")
            )
        )

    def test_console_separates_run_id_from_exact_observation_time(self):
        # On garde dans output la sortie console capturée pour la vérifier sans la confondre avec le
        # résultat métier.
        output = self.console_capture(self.run_reconcile(), "2026-10-05T09-41-22Z")
        # On vérifie que 'Run-id NAS     : 2026-10-05T09-41-22Z' figure dans output.
        self.assertIn("Run-id NAS     : 2026-10-05T09-41-22Z", output)
        # On vérifie que 'Observation NAS: 2026-10-05T09:41:22Z' figure dans output.
        self.assertIn("Observation NAS: 2026-10-05T09:41:22Z", output)

    def grouped_candidate_results(self, count=3):
        # On garde dans results une liste matérialisée à partir de self.no_passage_result().
        results = list(self.no_passage_result())
        # On récupère results[0].iloc[0] et on le garde dans row pour la suite.
        row = results[0].iloc[0]
        # On garde dans results[0] un tableau pandas construit avec les données indiquées.
        results[0] = pd.DataFrame(
            [
                dict(row, acquisition_id_normalise=f"Candidate_{index}")
                for index in range(count)
            ]
        )
        # On remet les résultats regroupés à l’appelant ; les étapes suivantes de cette fonction ne
        # sont plus parcourues.
        return results

    def test_console_groups_identical_profiles_and_lists_every_id(self):
        # On garde dans results les résultats regroupés construits pour tester les candidats à
        # vérifier.
        results = self.grouped_candidate_results()
        # On construit before comme une liste à partir de frame.copy(deep=True), pour chaque frame de
        # results.
        before = [frame.copy(deep=True) for frame in results]
        # On garde dans output la sortie console capturée pour la vérifier sans la confondre avec le
        # résultat métier.
        output = self.console_capture(results)
        # On vérifie que 'Groupe 1 — 3 acquisition(s)' figure dans output.
        self.assertIn("Groupe 1 — 3 acquisition(s)", output)
        # On vérifie que 'Groupe 2' ne figure pas dans output.
        self.assertNotIn("Groupe 2", output)
        # On vérifie que output.count('Motif : Aucun rattachement') correspond à 1.
        self.assertEqual(output.count("Motif : Aucun rattachement"), 1)
        # On parcourt range(3) ; index désigne l’élément courant de ce scénario.
        for index in range(3):
            # On vérifie que output.count(f'- Candidate_{index}') correspond à 1.
            self.assertEqual(output.count(f"- Candidate_{index}"), 1)
        # On parcourt zip(results, before) ; (frame, original) désigne l’élément courant de ce
        # scénario.
        for frame, original in zip(results, before):
            # On contrôle le résultat avec assert_frame_equal et les valeurs attendues indiquées juste
            # dessous.
            pd.testing.assert_frame_equal(frame, original)

    def test_console_different_excel_completion_kept_in_separate_group(self):
        # On garde dans results les résultats regroupés construits pour tester les candidats à
        # vérifier.
        results = self.grouped_candidate_results()
        # On utilise ce texte pour results[0].loc[2, 'excel_vitiparcel'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        results[0].loc[2, "excel_vitiparcel"] = "Terminé"
        # On garde dans groups la valeur renvoyée par r.acquisition_display_groups.
        groups = r.acquisition_display_groups(results[0])
        # On vérifie que [len(group['rows']) for group in groups] correspond à [2, 1].
        self.assertEqual([len(group["rows"]) for group in groups], [2, 1])
        # On garde dans output la sortie console capturée pour la vérifier sans la confondre avec le
        # résultat métier.
        output = self.console_capture(results)
        # On vérifie que 'Groupe 2 — 1 acquisition(s)' figure dans output.
        self.assertIn("Groupe 2 — 1 acquisition(s)", output)
        # On vérifie que 'Vitiparcel=Terminé' figure dans output.
        self.assertIn("Vitiparcel=Terminé", output)

    def test_console_different_reasons_kept_in_separate_group(self):
        # On garde dans results les résultats regroupés construits pour tester les candidats à
        # vérifier.
        results = self.grouped_candidate_results(2)
        # On initialise results[0].loc[1, 'raw_evidence_review_required'] à True ; les branches
        # suivantes pourront modifier cet état.
        results[0].loc[1, "raw_evidence_review_required"] = True
        # On utilise ce texte pour results[0].loc[1, 'found_in_raw_live'] ; il ne dépend pas d’une
        # valeur récupérée ailleurs à cet endroit.
        results[0].loc[1, "found_in_raw_live"] = "False"
        # On garde dans groups la valeur renvoyée par r.acquisition_display_groups.
        groups = r.acquisition_display_groups(results[0])
        # On vérifie que len(groups) correspond à 2.
        self.assertEqual(len(groups), 2)
        # On garde dans output la sortie console capturée pour la vérifier sans la confondre avec le
        # résultat métier.
        output = self.console_capture(results)
        # On vérifie que 'Présence du dossier Brut non démontrée' figure dans output.
        self.assertIn("Présence du dossier Brut non démontrée", output)

    def test_console_group_preserves_individual_comments_and_problems(self):
        # On garde dans results les résultats regroupés construits pour tester les candidats à
        # vérifier.
        results = self.grouped_candidate_results(2)
        # On rassemble dans results[0]['excel_comments'] les 2 éléments explicitement indiqués pour ce
        # cas d’essai.
        results[0]["excel_comments"] = ["Commentaire A", "Commentaire B"]
        # On rassemble dans results[0]['excel_problems'] les 2 éléments explicitement indiqués pour ce
        # cas d’essai.
        results[0]["excel_problems"] = ["GPS", ""]
        # On rassemble dans results[0]['excel_resolution_statuses'] les 2 éléments explicitement
        # indiqués pour ce cas d’essai.
        results[0]["excel_resolution_statuses"] = ["Non statué", "Exploitable"]
        # On garde dans output la sortie console capturée pour la vérifier sans la confondre avec le
        # résultat métier.
        output = self.console_capture(results)
        # On vérifie que 'Commentaire Excel [Candidate_0] : Commentaire A' figure dans output.
        self.assertIn("Commentaire Excel [Candidate_0] : Commentaire A", output)
        # On vérifie que 'Commentaire Excel [Candidate_1] : Commentaire B' figure dans output.
        self.assertIn("Commentaire Excel [Candidate_1] : Commentaire B", output)
        # On vérifie que 'Problème Excel [Candidate_0] : GPS' figure dans output.
        self.assertIn("Problème Excel [Candidate_0] : GPS", output)
        # On vérifie que 'Résolution déclarée dans Excel [Candidate_0] : Non statué' figure dans
        # output.
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "Résolution déclarée dans Excel [Candidate_0] : Non statué", output
        )
        # On vérifie que len(r.acquisition_display_groups(results[0])) correspond à 1.
        self.assertEqual(len(r.acquisition_display_groups(results[0])), 1)

    def test_console_group_prints_shared_comment_only_once(self):
        # On garde dans results les résultats regroupés construits pour tester les candidats à
        # vérifier.
        results = self.grouped_candidate_results(3)
        # On utilise ce texte pour results[0]['excel_comments'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        results[0]["excel_comments"] = "Commentaire partagé"
        # On garde dans output la sortie console capturée pour la vérifier sans la confondre avec le
        # résultat métier.
        output = self.console_capture(results)
        # On vérifie que output.count('Commentaire partagé') correspond à 1.
        self.assertEqual(output.count("Commentaire partagé"), 1)
        # On vérifie que 'Commentaire Excel commun' figure dans output.
        self.assertIn("Commentaire Excel commun", output)

    def test_display_groups_empty_and_missing_context_values(self):
        # On garde dans results les résultats regroupés construits pour tester les candidats à
        # vérifier.
        results = self.grouped_candidate_results(2)
        # On rassemble dans results[0]['excel_vitiparcel'] les 2 éléments explicitement indiqués pour
        # ce cas d’essai.
        results[0]["excel_vitiparcel"] = [pd.NA, ""]
        # On vérifie que len(r.acquisition_display_groups(results[0])) correspond à 1.
        self.assertEqual(len(r.acquisition_display_groups(results[0])), 1)
        # On vérifie que r.acquisition_display_groups(results[0].iloc[:0]) correspond à [].
        self.assertEqual(r.acquisition_display_groups(results[0].iloc[:0]), [])


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
