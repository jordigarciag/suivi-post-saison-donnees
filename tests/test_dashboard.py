# Lecture du fichier — Tests de dashboard.
#

# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd

# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
# On rend disponibles * depuis data_access, pour les appels de ce fichier.
from data_access import *
# On garde le petit jeu de règles indépendant des acquisitions de démonstration.
from mock_fixture import build_mock_state
# On rend disponibles display_records, render_content, serialise, summary_frame, make_app depuis
# dash_app, pour les appels de ce fichier.
from dash_app import display_records, render_content, serialise, summary_frame, make_app


class Rules(unittest.TestCase):
    def setUp(self):
        # On garde dans self.frames un état de démonstration construit avec des données synthétiques.
        self.frames = build_mock_state()
        # On garde dans self.aq la valeur renvoyée par unique_acquisitions.
        self.aq = unique_acquisitions(
            prepare_acquisitions(self.frames["reconciliation_acquisition_current"])
        )
        # On garde dans self.ps les passages préparés pour leur lecture dans le dashboard.
        self.ps = prepare_passages(self.frames["reconciliation_passage_current"])

    def test_paris_utc(self):
        # On vérifie que format_time('2026-10-21T08:29:00+00:00') correspond à '21/10/2026 à 10 h 29'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            format_time("2026-10-21T08:29:00+00:00"), "21/10/2026 à 10 h 29"
        )
        # On vérifie que format_time('2026-12-21T08:29:00+00:00') correspond à '21/12/2026 à 09 h 29'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            format_time("2026-12-21T08:29:00+00:00"), "21/12/2026 à 09 h 29"
        )

    def test_perimeter_not_technical_category(self):
        # On garde dans df la valeur renvoyée par prepare_acquisitions.
        df = prepare_acquisitions(
            pd.DataFrame([{"processing_business_category": "Preuve WEBP complète"}])
        )
        # On vérifie que df.iloc[0]['perimeter_normalized'] correspond à 'Inconnu'.
        self.assertEqual(df.iloc[0]["perimeter_normalized"], "Inconnu")

    def test_existing_normalized_perimeter(self):
        # On garde dans df la valeur renvoyée par prepare_acquisitions.
        df = prepare_acquisitions(
            pd.DataFrame([{"perimeter_normalized": "Test", "excel_needs_review": True}])
        )
        # On vérifie que df.iloc[0]['perimeter_normalized'] correspond à 'Test'.
        self.assertEqual(df.iloc[0]["perimeter_normalized"], "Test")
        # On attend que df.iloc[0]['needs_verification'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(df.iloc[0]["needs_verification"])

    def test_recorded_perimeter(self):
        # On garde dans df la valeur renvoyée par prepare_acquisitions.
        df = prepare_acquisitions(
            pd.DataFrame([{"recorded_excel_perimeter": "Production"}])
        )
        # On vérifie que df.iloc[0]['perimeter_normalized'] correspond à 'Production'.
        self.assertEqual(df.iloc[0]["perimeter_normalized"], "Production")

    def test_tests_not_business_anomalies(self):
        # On récupère self.aq[self.aq['acquisition_id_normalise'].eq('DEMO_A_003')].iloc[0] et on le
        # garde dans row pour la suite.
        row = self.aq[self.aq["acquisition_id_normalise"].eq("DEMO_A_003")].iloc[0]
        # On attend que row['needs_verification'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["needs_verification"])

    def test_test_real_error_kept(self):
        # On récupère self.aq[self.aq['acquisition_id_normalise'].eq('DEMO_B_003')].iloc[0] et on le
        # garde dans row pour la suite.
        row = self.aq[self.aq["acquisition_id_normalise"].eq("DEMO_B_003")].iloc[0]
        # On attend que row['needs_verification'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["needs_verification"])

    def test_production_subset(self):
        # On vérifie que len(metric_frame('production', self.aq, self.ps)) correspond à 4.
        self.assertEqual(len(metric_frame("production", self.aq, self.ps)), 4)
        # On vérifie que len(metric_frame('treated', self.aq, self.ps)) correspond à 2.
        self.assertEqual(len(metric_frame("treated", self.aq, self.ps)), 2)
        # On vérifie que len(metric_frame('outside', self.aq, self.ps)) correspond à 1.
        self.assertEqual(len(metric_frame("outside", self.aq, self.ps)), 1)
        # On garde dans summary la valeur renvoyée par summary_frame.
        summary = summary_frame(self.aq, self.ps)
        # On attend que (summary['Production traitée'] <= summary['Production · Excel']).all() soit
        # évalué comme vrai pour ce cas de test.
        self.assertTrue(
            (summary["Production traitée"] <= summary["Production · Excel"]).all()
        )

    def test_unknown_not_incomplete(self):
        # On récupère self.aq[self.aq['acquisition_id_normalise'].eq('DEMO_B_001')].iloc[0] et on le
        # garde dans r pour la suite.
        r = self.aq[self.aq["acquisition_id_normalise"].eq("DEMO_B_001")].iloc[0]
        # On attend que r['treatment_unknown'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(r["treatment_unknown"])
        # On attend que r['production_incomplete'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(r["production_incomplete"])

    def test_stocks_and_status_both_required(self):
        # On vérifie que len(metric_frame('parcel', self.aq, self.ps)) correspond à 1.
        self.assertEqual(len(metric_frame("parcel", self.aq, self.ps)), 1)
        # On récupère prepare_passages(pd.DataFrame([{'has_non_healthy_status': True, 'stocks_j… et on
        # le garde dans row pour la suite.
        row = prepare_passages(
            pd.DataFrame(
                [{"has_non_healthy_status": True, "stocks_json_exists": False}]
            )
        ).iloc[0]
        # On attend que row['vitiparcel_technical_criterion_satisfied'] soit évalué comme faux pour ce
        # cas de test.
        self.assertFalse(row["vitiparcel_technical_criterion_satisfied"])

    def test_unknown_stocks_not_zero(self):
        # On récupère prepare_passages(pd.DataFrame([{'has_non_healthy_status': True}])).iloc[0] et on
        # le garde dans row pour la suite.
        row = prepare_passages(pd.DataFrame([{"has_non_healthy_status": True}])).iloc[0]
        # On attend None pour row['vitiparcel_technical_criterion_satisfied'] : aucune valeur n’est
        # confirmée dans ce cas.
        self.assertIsNone(row["vitiparcel_technical_criterion_satisfied"])

    def test_focus_not_confused_with_criterion_false(self):
        # On répartit les valeurs renvoyées par focus_passages entre (work, unknown) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        work, unknown = focus_passages(self.ps, self.aq)
        # On vérifie que work['passage_name'].tolist() correspond à ['Passage 2'].
        self.assertEqual(work["passage_name"].tolist(), ["Passage 2"])
        # On vérifie que unknown['passage_name'].tolist() correspond à ['Passage 5'].
        self.assertEqual(unknown["passage_name"].tolist(), ["Passage 5"])

    def test_error_blocks_absence_conclusion(self):
        # On garde dans ps une copie de self.ps pour travailler sur cet objet séparément.
        ps = self.ps.copy()
        # On utilise ce texte pour ps.loc[ps['passage_name'].eq('Passage 2'), 'vitimap_error'] ; il ne
        # dépend pas d’une valeur récupérée ailleurs à cet endroit.
        ps.loc[ps["passage_name"].eq("Passage 2"), "vitimap_error"] = (
            "Permission denied"
        )
        # On répartit les valeurs renvoyées par focus_passages entre (work, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        work, _ = focus_passages(ps, self.aq)
        # On attend que work.empty soit évalué comme vrai pour ce cas de test.
        self.assertTrue(work.empty)

    def test_filters_apply_to_passages(self):
        # On répartit les valeurs renvoyées par filter_frames entre (a, p, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        a, p, _ = filter_frames(self.aq, self.ps, pd.DataFrame(), "__ALL__", "Test", "")
        # On vérifie que set(a['perimeter_normalized']) correspond à {'Test'}.
        self.assertEqual(set(a["perimeter_normalized"]), {"Test"})
        # On vérifie que p['passage_name'].tolist() correspond à ['Passage 3'].
        self.assertEqual(p["passage_name"].tolist(), ["Passage 3"])

    def test_search_acquisition_links_to_passage(self):
        # On répartit les valeurs renvoyées par filter_frames entre (_, p, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        _, p, _ = filter_frames(
            self.aq, self.ps, pd.DataFrame(), "__ALL__", "__ALL__", "DEMO_A_002"
        )
        # On vérifie que p['passage_name'].tolist() correspond à ['Passage 2'].
        self.assertEqual(p["passage_name"].tolist(), ["Passage 2"])

    def test_dedup_and_conflict_detection(self):
        # On garde dans duplicated l’assemblage des tableaux suivant l’axe et les options indiqués.
        duplicated = pd.concat([self.aq, self.aq.iloc[:1]], ignore_index=True)
        # On vérifie que len(unique_acquisitions(duplicated)) correspond à len(self.aq).
        self.assertEqual(len(unique_acquisitions(duplicated)), len(self.aq))
        # On garde dans conflict une copie de self.aq.iloc[:1] pour travailler sur cet objet
        # séparément.
        conflict = self.aq.iloc[:1].copy()
        # On utilise ce texte pour conflict['parcel_name'] ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        conflict["parcel_name"] = "Different"
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle unique_acquisitions avec pd.concat([self.aq, conflict], ignore_index=True).
            unique_acquisitions(pd.concat([self.aq, conflict], ignore_index=True))

    def test_comparison_human_dates_per_vineyard(self):
        # On répartit les valeurs renvoyées par build_comparison_summary entre (diff, messages) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        diff, messages = build_comparison_summary(
            self.frames["reconciliation_acquisition_history"]
        )
        # V4 demo's latest scan deliberately confirms an unchanged state.
        self.assertEqual(len(diff), 0)
        # On vérifie que 'du 21/10/2026 au 22/10/2026' figure dans messages[0].
        self.assertIn("du 21/10/2026 au 22/10/2026", messages[0])
        # On vérifie que 'demo_202610' ne figure pas dans ' '.join(messages).
        self.assertNotIn("demo_202610", " ".join(messages))

    def test_missing_proof_does_not_claim_no_change(self):
        # On garde dans df la valeur renvoyée par
        # self.frames['reconciliation_acquisition_history'].drop.
        df = self.frames["reconciliation_acquisition_history"].drop(
            # On décrit les colonnes à présenter, distinctes des lignes de données.
            columns=[
                "found_in_raw_live",
                "found_in_processing_live",
                "processing_has_webp_images",
                "found_in_parcel_mapping",
                "found_in_passage_mapping",
                "passage_created",
            ],
            # On définit ce que la conversion fera des valeurs invalides, au lieu de laisser ce cas
            # implicite.
            errors="ignore",
        )
        # On répartit les valeurs renvoyées par build_comparison_summary entre (_, messages) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        _, messages = build_comparison_summary(df)
        # On attend que all(('aucune preuve technique comparable' in m for m in messages)) soit évalué
        # comme vrai pour ce cas de test.
        self.assertTrue(
            all("aucune preuve technique comparable" in m for m in messages)
        )

    def test_safe_display_boolean_and_timestamp(self):
        # On récupère display_records(pd.DataFrame([{'proof': True, 'nas_checked_at': '2026-10-… et on
        # le garde dans r pour la suite.
        r = display_records(
            pd.DataFrame(
                [{"proof": True, "nas_checked_at": "2026-10-21T08:29:00+00:00"}]
            )
        )[0]
        # On vérifie que r['proof'] correspond à 'Oui'.
        self.assertEqual(r["proof"], "Oui")
        # On vérifie que '10 h 29' figure dans r['nas_checked_at'].
        self.assertIn("10 h 29", r["nas_checked_at"])

    def test_failure_never_switches_to_fake_business_counts(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(os.environ, {"DASHBOARD_USE_MOCK": "0"}),
            patch("data_access.DatabaseClient", side_effect=RuntimeError("offline")),
        ):
            # On garde dans s la valeur renvoyée par load_dashboard_state.
            s = load_dashboard_state()
            # On vérifie que s.mode correspond à 'unavailable'.
            self.assertEqual(s.mode, "unavailable")
            # On attend que s.frames soit évalué comme faux pour ce cas de test.
            self.assertFalse(s.frames)

    def test_tabs_render_empty_and_mock(self):
        # On parcourt [self.frames, {k: pd.DataFrame() for k in self.frames}] ; frames désigne
        # l’élément courant de ce scénario.
        for frames in [self.frames, {k: pd.DataFrame() for k in self.frames}]:
            # On garde dans payload la représentation sérialisable préparée pour ces données.
            payload = serialise(DashboardState("mock", "Fictif", frames))
            # On parcourt ['overview', 'search', 'focus'] ; tab désigne l’élément courant de ce
            # scénario.
            for tab in ["overview", "search", "focus"]:
                # On vérifie que render_content(tab, payload, '__ALL__', '__ALL__', 'test') n’est pas
                # None.
                self.assertIsNotNone(
                    render_content(tab, payload, "__ALL__", "__ALL__", "test")
                )

    def test_copy_all_filtered_rows_beyond_one_page(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {"DASHBOARD_USE_MOCK": "1"}):
            # On garde dans app l’application Dash construite avec ses composants et callbacks.
            app = make_app()
        # On garde dans callback le prochain élément de (v['callback'].__wrapped__ for k, v in
        # app.callback_map.items() if 'clipb….
        callback = next(
            v["callback"].__wrapped__
            for k, v in app.callback_map.items()
            if "clipboard" in k
        )
        # On construit data comme une liste à partir de {'acquisition': f'ID_{i:03}'}, pour chaque i de
        # range(125).
        data = [{"acquisition": f"ID_{i:03}"} for i in range(125)]
        # On garde dans filtered_sorted une liste matérialisée à partir de reversed(data[10:120]).
        filtered_sorted = list(reversed(data[10:120]))
        # On répartit les valeurs renvoyées par callback entre (content, message) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        content, message = callback(["acquisition"], filtered_sorted, data)
        # On vérifie que len(content.splitlines()) correspond à 110.
        self.assertEqual(len(content.splitlines()), 110)
        # On vérifie que content.splitlines()[0] correspond à 'ID_119'.
        self.assertEqual(content.splitlines()[0], "ID_119")
        # On vérifie que content.splitlines()[-1] correspond à 'ID_010'.
        self.assertEqual(content.splitlines()[-1], "ID_010")
        # On vérifie que '110' figure dans message.
        self.assertIn("110", message)

    def test_dash_endpoints_and_callbacks(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {"DASHBOARD_USE_MOCK": "1"}):
            # On garde dans app l’application Dash construite avec ses composants et callbacks.
            app = make_app()
        # On garde dans client la valeur renvoyée par app.server.test_client.
        client = app.server.test_client()
        # On vérifie que client.get('/_dash-layout').status_code correspond à 200.
        self.assertEqual(client.get("/_dash-layout").status_code, 200)
        # On vérifie que client.get('/_dash-dependencies').status_code correspond à 200.
        self.assertEqual(client.get("/_dash-dependencies").status_code, 200)
        # On garde dans response le champ '/assets/demo.svg' de client, ou None si la clé est absente.
        response = client.get("/assets/demo.svg")
        # On vérifie que response.status_code correspond à 200.
        self.assertEqual(response.status_code, 200)
        # On ferme response pour libérer la ressource associée après son utilisation.
        response.close()


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
