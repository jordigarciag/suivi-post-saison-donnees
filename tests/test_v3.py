# Lecture du fichier — Tests de v3.
#

# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
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
# On rend disponibles prepare_acquisitions, prepare_passages, build_mock_state depuis data_access, pour
# les appels de ce fichier.
from data_access import prepare_acquisitions, prepare_passages
from mock_fixture import build_mock_state
# On rend disponibles * depuis business_rules, pour les appels de ce fichier.
from business_rules import *
# On rend disponibles make_app, render_content, serialise, search_results, chart, dossier depuis
# dash_app, pour les appels de ce fichier.
from dash_app import make_app, render_content, serialise, search_results, chart, dossier
# On rend disponibles DashboardState depuis data_access, pour les appels de ce fichier.
from data_access import DashboardState


class V3(unittest.TestCase):
    def setUp(self):
        # On garde dans self.frames un état de démonstration construit avec des données synthétiques.
        self.frames = build_mock_state()
        # On garde dans self.aq les acquisitions complétées avec les champs calculés de présentation.
        self.aq = enrich_acquisitions(
            prepare_acquisitions(self.frames["reconciliation_acquisition_current"])
        )
        # On garde dans self.ps les passages préparés pour leur lecture dans le dashboard.
        self.ps = prepare_passages(self.frames["reconciliation_passage_current"])
        # On garde dans self.payload la représentation sérialisable préparée pour ces données.
        self.payload = serialise(DashboardState("mock", "Fictif", self.frames))

    def test_classification_preserves_status_and_comment(self):
        # On récupère self.aq[self.aq['perimeter_normalized'].eq('Bloqué')].iloc[0] et on le garde dans
        # row pour la suite.
        row = self.aq[self.aq["perimeter_normalized"].eq("Bloqué")].iloc[0]
        # On vérifie que row['excel_status_display'] correspond à 'En attente'.
        self.assertEqual(row["excel_status_display"], "En attente")
        # On vérifie que 'Attente de décision' figure dans row['excel_comment_display'].
        self.assertIn("Attente de décision", row["excel_comment_display"])
        # On vérifie que 'En attente' figure dans row['classification_explanation'].
        self.assertIn("En attente", row["classification_explanation"])
        # On vérifie que 'Hors contrôles' figure dans row['decision_reason_display'].
        self.assertIn("Hors contrôles", row["decision_reason_display"])

    def test_missing_comment_not_invented(self):
        # On garde dans df les acquisitions complétées avec les champs calculés de présentation.
        df = enrich_acquisitions(
            prepare_acquisitions(pd.DataFrame([{"excel_perimeter": "Bloqué"}]))
        )
        # On vérifie que df.iloc[0]['excel_comment_display'] correspond à ''.
        self.assertEqual(df.iloc[0]["excel_comment_display"], "")
        # On vérifie que df.iloc[0]['decision_reason_display'] correspond à ''.
        self.assertEqual(df.iloc[0]["decision_reason_display"], "")
        # On vérifie que 'non renseigné' figure dans df.iloc[0]['classification_explanation'].
        self.assertIn("non renseigné", df.iloc[0]["classification_explanation"])

    def test_review_has_source_and_origin(self):
        # On récupère self.aq[self.aq['acquisition_id_normalise'].eq('DEMO_A_002')].iloc[0] et on le
        # garde dans row pour la suite.
        row = self.aq[self.aq["acquisition_id_normalise"].eq("DEMO_A_002")].iloc[0]
        # On vérifie que 'Suivi Excel' figure dans row['review_origin'].
        self.assertIn("Suivi Excel", row["review_origin"])
        # On vérifie que 'Croisement Excel / NAS' figure dans row['review_origin'].
        self.assertIn("Croisement Excel / NAS", row["review_origin"])
        # On vérifie que 'processing_decision_required' figure dans row['review_source_fields'].
        self.assertIn("processing_decision_required", row["review_source_fields"])
        # On vérifie que 'Détail enregistré' figure dans row['review_reason'].
        self.assertIn("Détail enregistré", row["review_reason"])

    def test_ambiguous_processing_flag_not_automatically_crossing(self):
        # On garde dans df les acquisitions complétées avec les champs calculés de présentation.
        df = enrich_acquisitions(
            prepare_acquisitions(
                pd.DataFrame(
                    [
                        {
                            # On renseigne le périmètre du suivi Excel sous la clé 'excel_perimeter'.
                            "excel_perimeter": "Production",
                            # On associe la clé 'processing_decision_required' à cette valeur dans les
                            # données de ce scénario.
                            "processing_decision_required": True,
                        }
                    ]
                )
            )
        )
        # On vérifie que 'Croisement Excel / NAS' ne figure pas dans df.iloc[0]['review_origin'].
        self.assertNotIn("Croisement Excel / NAS", df.iloc[0]["review_origin"])
        # On vérifie que 'seul ne permet pas' figure dans df.iloc[0]['review_reason'].
        self.assertIn("seul ne permet pas", df.iloc[0]["review_reason"])

    def test_tests_do_not_become_tasks(self):
        # On répartit les valeurs renvoyées par focus_sections entre (sections, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        sections, _ = focus_sections(self.aq, self.ps)
        # On parcourt sections.items() ; (key, entry) désigne l’élément courant de ce scénario.
        for key, entry in sections.items():
            # Cette branche traite le cas où entry['grain'] correspond au texte 'acq' et la condition
            # entry['missing'].empty n’est pas remplie.
            if entry["grain"] == "acq" and not entry["missing"].empty:
                # On attend que entry['missing']['perimeter_normalized'].eq('Production').all() soit
                # évalué comme vrai pour ce cas de test.
                self.assertTrue(
                    entry["missing"]["perimeter_normalized"].eq("Production").all()
                )

    def test_focus_sections_have_independent_criteria(self):
        # On répartit les valeurs renvoyées par focus_sections entre (sections, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        sections, _ = focus_sections(self.aq, self.ps)
        # On vérifie que len(sections) correspond à 10.
        self.assertEqual(len(sections), 10)
        # On vérifie que sections['backup']['missing']['acquisition_id_normalise'].tolist() correspond
        # à ['DEMO_A_002'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            sections["backup"]["missing"]["acquisition_id_normalise"].tolist(),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ["DEMO_A_002"],
        )
        # On vérifie que sections['raw']['missing']['acquisition_id_normalise'].tolist() correspond à
        # ['DEMO_B_002'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            sections["raw"]["missing"]["acquisition_id_normalise"].tolist(),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ["DEMO_B_002"],
        )
        # On vérifie que sections['processing']['missing']['acquisition_id_normalise'].tolist()
        # correspond à ['DEMO_A_002'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            sections["processing"]["missing"]["acquisition_id_normalise"].tolist(),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            ["DEMO_A_002"],
        )
        # On vérifie que 'DEMO_B_001' figure dans
        # sections['processing']['unknown']['acquisition_id_normalise'].tolist().
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "DEMO_B_001",
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            sections["processing"]["unknown"]["acquisition_id_normalise"].tolist(),
        )

    def test_stocks_present_without_unhealthy_not_a_missing_file(self):
        # On répartit les valeurs renvoyées par focus_sections entre (sections, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        sections, _ = focus_sections(self.aq, self.ps)
        # On vérifie que sections['stocks']['missing']['passage_name'].tolist() correspond à ['Passage
        # 2'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            sections["stocks"]["missing"]["passage_name"].tolist(), ["Passage 2"]
        )
        # On vérifie que sections['status']['missing']['passage_name'].tolist() correspond à ['Passage
        # 6'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            sections["status"]["missing"]["passage_name"].tolist(), ["Passage 6"]
        )
        # On vérifie que sections['both']['missing']['passage_name'].tolist() correspond à ['Passage
        # 2'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            sections["both"]["missing"]["passage_name"].tolist(), ["Passage 2"]
        )

    def test_control_error_is_not_file_absence(self):
        # On garde dans ps une copie de self.ps pour travailler sur cet objet séparément.
        ps = self.ps.copy()
        # On utilise ce texte pour ps.loc[ps['passage_name'].eq('Passage 2'), 'vitimap_error'] ; il ne
        # dépend pas d’une valeur récupérée ailleurs à cet endroit.
        ps.loc[ps["passage_name"].eq("Passage 2"), "vitimap_error"] = (
            "Permission refusée"
        )
        # On répartit les valeurs renvoyées par focus_sections entre (sections, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        sections, _ = focus_sections(self.aq, ps)
        # On vérifie que sections['vitimap']['missing']['passage_name'].tolist() correspond à ['Passage
        # 6'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            sections["vitimap"]["missing"]["passage_name"].tolist(), ["Passage 6"]
        )
        # On vérifie que 'Passage 2' figure dans
        # sections['vitimap']['unknown']['passage_name'].tolist().
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "Passage 2", sections["vitimap"]["unknown"]["passage_name"].tolist()
        )

    def test_no_passage_folder_not_counted_as_missing_livrable(self):
        # On garde dans ps une copie de self.ps pour travailler sur cet objet séparément.
        ps = self.ps.copy()
        # On initialise ps.loc[ps['passage_name'].eq('Passage 2'), 'passage_created'] à False ; les
        # branches suivantes pourront modifier cet état.
        ps.loc[ps["passage_name"].eq("Passage 2"), "passage_created"] = False
        # On répartit les valeurs renvoyées par focus_sections entre (sections, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        sections, _ = focus_sections(self.aq, ps)
        # On vérifie que sections['passage']['missing']['passage_name'].tolist() correspond à ['Passage
        # 2'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            sections["passage"]["missing"]["passage_name"].tolist(), ["Passage 2"]
        )
        # On vérifie que sections['vitimap']['missing']['passage_name'].tolist() correspond à ['Passage
        # 6'].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            sections["vitimap"]["missing"]["passage_name"].tolist(), ["Passage 6"]
        )

    def test_search_partial_accent_case(self):
        # On garde dans f les éléments du catalogue correspondant à la recherche.
        f = search_catalog(self.aq, self.ps, "demo_a_00", "acquisition")
        # On vérifie que len(f) correspond à 4.
        self.assertEqual(len(f), 4)
        # On vérifie que len(search_catalog(self.aq, self.ps, 'PARCELLE 1', 'parcel')) correspond à 1.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            len(search_catalog(self.aq, self.ps, "PARCELLE 1", "parcel")), 1
        )
        # On attend que search_catalog(self.aq, self.ps, 'not-existing').empty soit évalué comme vrai
        # pour ce cas de test.
        self.assertTrue(search_catalog(self.aq, self.ps, "not-existing").empty)
        # On vérifie que len(search_catalog(self.aq, self.ps, 'domaine demo a', 'acquisition'))
        # correspond à 4.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            len(search_catalog(self.aq, self.ps, "domaine demo a", "acquisition")), 4
        )

    def test_search_without_keyword_does_not_dump_everything(self):
        # On attend que search_catalog(self.aq, self.ps, '').empty soit évalué comme vrai pour ce cas
        # de test.
        self.assertTrue(search_catalog(self.aq, self.ps, "").empty)

    def test_search_scope_independent(self):
        # Search callback reads the full payload, not the global category filters.
        result = search_results(self.payload, "DEMO_A_004", "acquisition", "__ALL__")
        # On vérifie que result n’est pas None.
        self.assertIsNotNone(result)
        # On garde dans f les éléments du catalogue correspondant à la recherche.
        f = search_catalog(self.aq, self.ps, "DEMO_A_004")
        # On répartit les valeurs renvoyées par related entre (a, p) ; leur ordre doit correspondre à
        # celui prévu par cet appel.
        a, p = related(f.iloc[0]["entity_key"], self.aq, self.ps)
        # On vérifie que a.iloc[0]['perimeter_normalized'] correspond à 'Bloqué'.
        self.assertEqual(a.iloc[0]["perimeter_normalized"], "Bloqué")
        # On vérifie que p['passage_name'].tolist() correspond à ['Passage 4'].
        self.assertEqual(p["passage_name"].tolist(), ["Passage 4"])

    def test_parcel_and_passage_dossiers(self):
        # On parcourt [('Parcelle 1', 'parcel'), ('Passage 1', 'passage')] ; (q, kind) désigne
        # l’élément courant de ce scénario.
        for q, kind in [("Parcelle 1", "parcel"), ("Passage 1", "passage")]:
            # On récupère search_catalog(self.aq, self.ps, q, kind).iloc[0] et on le garde dans hit
            # pour la suite.
            hit = search_catalog(self.aq, self.ps, q, kind).iloc[0]
            # On répartit les valeurs renvoyées par related entre (a, p) ; leur ordre doit correspondre
            # à celui prévu par cet appel.
            a, p = related(hit["entity_key"], self.aq, self.ps)
            # On vérifie que a['acquisition_id_normalise'].tolist() correspond à ['DEMO_A_001'].
            self.assertEqual(a["acquisition_id_normalise"].tolist(), ["DEMO_A_001"])
            # On vérifie que p['passage_name'].tolist() correspond à ['Passage 1'].
            self.assertEqual(p["passage_name"].tolist(), ["Passage 1"])
            # On vérifie que dossier(hit['entity_key'], self.payload) n’est pas None.
            self.assertIsNotNone(dossier(hit["entity_key"], self.payload))

    def test_no_fabricated_alignment_for_multiple_links(self):
        # On garde dans row une série pandas avec les valeurs et l’index fournis.
        row = pd.Series({"parcel_name": "A | B", "passage_name": "X | Y"})
        # On vérifie que acquisition_links(row) correspond à [].
        self.assertEqual(acquisition_links(row), [])
        # On vérifie que parcel_names(row) correspond à ['A', 'B'].
        self.assertEqual(parcel_names(row), ["A", "B"])

    def test_plot_hover_solid_and_counts(self):
        # On garde dans component la valeur renvoyée par chart.
        component = chart(
            pd.DataFrame({"Vignoble": ["A"], "N": [4]}),
            [("N", "Vitimap (GeoJSON présent)", "#245DC4")],
            "Test",
        )
        # On sélectionne dans component.children les éléments désignés par -1 ; graph recevra cette
        # sélection.
        graph = component.children[-1]
        # On vérifie que graph.figure.data[0].hoverlabel.bgcolor correspond à '#FFFFFF'.
        self.assertEqual(graph.figure.data[0].hoverlabel.bgcolor, "#FFFFFF")
        # On vérifie que 'Quantité :' figure dans graph.figure.data[0].hovertemplate.
        self.assertIn("Quantité :", graph.figure.data[0].hovertemplate)
        # On attend que graph.figure.layout.showlegend soit évalué comme faux pour ce cas de test.
        self.assertFalse(graph.figure.layout.showlegend)

    def test_no_global_search_and_no_manual_copy_control(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {"DASHBOARD_USE_MOCK": "1"}):
            # On garde dans app l’application Dash construite avec ses composants et callbacks.
            app = make_app()
        # On garde dans layout la valeur renvoyée par
        # app.server.test_client().get('/_dash-layout').get_data.
        layout = app.server.test_client().get("/_dash-layout").get_data(as_text=True)
        # On vérifie que 'search-filter' ne figure pas dans layout.
        self.assertNotIn("search-filter", layout)
        # On vérifie que 'copy-text' ne figure pas dans layout.
        self.assertNotIn("copy-text", layout)
        # On parcourt ['overview', 'search', 'focus'] ; tab désigne l’élément courant de ce scénario.
        for tab in ["overview", "search", "focus"]:
            # On garde dans rendered la valeur renvoyée par render_content.
            rendered = render_content(tab, self.payload, "__ALL__", "__ALL__", None)
            # On garde dans value la représentation textuelle de rendered.
            value = str(rendered)
            # On vérifie que 'Afficher le texte à copier manuellement' ne figure pas dans value.
            self.assertNotIn("Afficher le texte à copier manuellement", value)
            # On vérifie que 'présence au bureau' ne figure pas dans value.
            self.assertNotIn("présence au bureau", value)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
