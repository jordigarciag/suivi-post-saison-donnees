# Lecture du fichier — Tests de v6.
#

"""V6 : présentation, export brut et contrat métier inchangé depuis la V5."""

# On importe csv. On transforme les tableaux entre lignes Python et fichiers CSV.
import csv
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
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

# On récupère Path(__file__).resolve().parents[1] et on le garde dans ROOT pour la suite.
ROOT = Path(__file__).resolve().parents[1]
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(ROOT / "app"))
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(1, str(ROOT / "tests"))
# On rend disponibles * depuis presentation, pour les appels de ce fichier.
from presentation import *
# On rend disponibles format_time, format_scan_time, prepare_acquisitions, prepare_passages depuis
# data_access, pour les appels de ce fichier.
from data_access import (
    format_time,
    format_scan_time,
    prepare_acquisitions,
    prepare_passages,
)
# On rend disponibles enrich_acquisitions, focus_sections depuis business_rules, pour les appels de ce
# fichier.
from business_rules import enrich_acquisitions, focus_sections
# On rend disponibles batch_options, META depuis history_engine, pour les appels de ce fichier.
from history_engine import batch_options, META
# On rend disponibles build_mock_state depuis mock_fixture, pour les appels de ce fichier.
from mock_fixture import build_mock_state
# On rend disponibles display_records, table_panel, render_focus, make_app depuis dash_app, pour les
# appels de ce fichier.
from dash_app import display_records, table_panel, render_focus, make_app
# On rend disponibles collect_contract depuis business_contract, pour les appels de ce fichier.
from business_contract import collect_contract


def find_component(node, kind):
    # On prépare out comme liste vide ; on la remplira au fil des opérations suivantes.
    out = []
    # On vérifie ce cas avant la suite : node.__class__.__name__ correspond à kind.
    if node.__class__.__name__ == kind:
        # On ajoute node à la fin de out ; les éléments précédents restent conservés.
        out.append(node)
    # On garde dans children l’attribut 'children' de node avec le repli indiqué s’il est absent.
    children = getattr(node, "children", None)
    # On parcourt children if isinstance(children, list) else [children] ; child désigne l’élément
    # courant de ce scénario.
    for child in children if isinstance(children, list) else [children]:
        # Cette branche traite le cas où le contrôle hasattr(child, 'to_plotly_json') est positif.
        if hasattr(child, "to_plotly_json"):
            # On ajoute find_component(child, kind) à out et on conserve ce nouvel état pour la suite.
            out += find_component(child, kind)
    # On remet out à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return out


class PresentationV6(unittest.TestCase):
    def test_same_business_results_as_v5(self):
        # On garde dans expected les objets Python décodés depuis le JSON fourni.
        expected = json.loads(
            (ROOT / "tests/fixtures/v5_business_contract.json").read_text(
                # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas
                # être décodé selon un réglage implicite du poste.
                encoding="utf-8"
            )
        )
        # On garde dans actual les objets Python décodés depuis le JSON fourni.
        actual = json.loads(json.dumps(collect_contract(), default=str))
        # On vérifie que actual correspond à expected.
        self.assertEqual(actual, expected)

    def test_compact_scan_timezone_dst_and_general_time_unchanged(self):
        # On vérifie que format_scan_time('2026-10-21T08:29:00Z') correspond à '21/10/2026 à 10h29'.
        self.assertEqual(format_scan_time("2026-10-21T08:29:00Z"), "21/10/2026 à 10h29")
        # On vérifie que format_scan_time('2026-12-21T08:29:00Z') correspond à '21/12/2026 à 09h29'.
        self.assertEqual(format_scan_time("2026-12-21T08:29:00Z"), "21/12/2026 à 09h29")
        # On vérifie que format_time('2026-10-21T08:29:00Z') correspond à '21/10/2026 à 10 h 29'.
        self.assertEqual(format_time("2026-10-21T08:29:00Z"), "21/10/2026 à 10 h 29")
        # On vérifie que format_scan_time(None) correspond à 'Non renseignée'.
        self.assertEqual(format_scan_time(None), "Non renseignée")

    def test_scan_labels_compact_including_cross_midnight(self):
        # On garde dans f un état de démonstration construit avec des données synthétiques.
        f = build_mock_state()
        # On vérifie que batch_options(f)[0]['label'] correspond à '22/10/2026 · 10h01–10h03 ⇒ Dernier
        # scan'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            batch_options(f)[0]["label"], "22/10/2026 · 10h01–10h03 ⇒ Dernier scan"
        )
        # On sélectionne dans f les éléments désignés par META ; meta recevra cette sélection.
        meta = f[META]
        # On garde dans mask le masque d’égalité calculé pour meta.pipeline_execution_id.
        mask = meta.pipeline_execution_id.eq("demo_20261022")
        # On utilise ce texte pour meta.loc[mask & meta.vineyard_key.eq('demo_a'), 'nas_checked_at'] ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        meta.loc[mask & meta.vineyard_key.eq("demo_a"), "nas_checked_at"] = (
            "2026-10-21T21:59:00Z"
        )
        # On utilise ce texte pour meta.loc[mask & meta.vineyard_key.eq('demo_b'), 'nas_checked_at'] ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        meta.loc[mask & meta.vineyard_key.eq("demo_b"), "nas_checked_at"] = (
            "2026-10-21T22:01:00Z"
        )
        # On vérifie que '21/10/2026 · 23h59–22/10/2026 · 00h01' figure dans
        # batch_options(f)[0]['label'].
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "21/10/2026 · 23h59–22/10/2026 · 00h01", batch_options(f)[0]["label"]
        )

    def test_nas_plain_has_one_observation_per_line(self):
        # On récupère enrich_acquisitions(prepare_acquisitions(pd.DataFrame([{'excel_perimeter'… et on
        # le garde dans row pour la suite.
        row = enrich_acquisitions(
            prepare_acquisitions(
                pd.DataFrame(
                    [
                        {
                            # On renseigne le périmètre du suivi Excel sous la clé 'excel_perimeter'.
                            "excel_perimeter": "Production",
                            # On renseigne la présence constatée dans les données brutes sous la clé
                            # 'found_in_raw_live'.
                            "found_in_raw_live": True,
                            # On renseigne la présence d’une image pleine taille sous la clé
                            # 'raw_has_full_size_image'.
                            "raw_has_full_size_image": False,
                        }
                    ]
                )
            )
        ).iloc[0]
        # On garde dans lines les lignes de row[NAS_COLUMN] séparées sans dépendre du type de fin de
        # ligne.
        lines = row[NAS_COLUMN].splitlines()
        # On vérifie que len(lines) correspond à 6.
        self.assertEqual(len(lines), 6)
        # On vérifie que lines[0] correspond à 'Dossier Brut : présent'.
        self.assertEqual(lines[0], "Dossier Brut : présent")
        # On vérifie que lines[1] correspond à 'Image full size : absente'.
        self.assertEqual(lines[1], "Image full size : absente")
        # On vérifie que 'non renseigné' figure dans lines[-1].
        self.assertIn("non renseigné", lines[-1])
        # On vérifie que ' ; ' ne figure pas dans row[NAS_COLUMN].
        self.assertNotIn(" ; ", row[NAS_COLUMN])

    def test_error_information_preserved_distinct_from_statuses(self):
        # On récupère enrich_acquisitions(prepare_acquisitions(pd.DataFrame([{'excel_perimeter'… et on
        # le garde dans row pour la suite.
        row = enrich_acquisitions(
            prepare_acquisitions(
                pd.DataFrame(
                    [
                        {
                            # On renseigne le périmètre du suivi Excel sous la clé 'excel_perimeter'.
                            "excel_perimeter": "Production",
                            # On renseigne la présence constatée dans les données brutes sous la clé
                            # 'found_in_raw_live'.
                            "found_in_raw_live": False,
                            # On renseigne l’erreur de lecture des données brutes sous la clé
                            # 'raw_error'.
                            "raw_error": "Permission refusée",
                            # On associe la clé 'has_technical_error' à cette valeur dans les données
                            # de ce scénario.
                            "has_technical_error": True,
                        }
                    ]
                )
            )
        ).iloc[0]
        # On vérifie que 'Dossier Brut : absent' figure dans row[NAS_COLUMN].
        self.assertIn("Dossier Brut : absent", row[NAS_COLUMN])
        # On vérifie que 'Erreur de contrôle Brut : Permission refusée' figure dans row[NAS_COLUMN].
        self.assertIn("Erreur de contrôle Brut : Permission refusée", row[NAS_COLUMN])
        # On vérifie que 'Erreur technique enregistrée : signalée' figure dans row[NAS_COLUMN].
        self.assertIn("Erreur technique enregistrée : signalée", row[NAS_COLUMN])
        # On attend que row['found_in_raw_live'] soit évalué comme faux pour ce cas de test.
        self.assertFalse(row["found_in_raw_live"])

    def test_markdown_bold_labels_only_and_escaping(self):
        # On utilise ce texte pour raw ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        raw = "Dossier Brut : présent\nErreur : <script>alert(1)</script> [lien](https://example.org)"
        # On garde dans md la valeur renvoyée par nas_markdown.
        md = nas_markdown(raw)
        # On vérifie que '**Dossier Brut :** présent  \n' figure dans md.
        self.assertIn("**Dossier Brut :** présent  \n", md)
        # On vérifie que '\\<script\\>' figure dans md.
        self.assertIn("\\<script\\>", md)
        # On vérifie que '\\[lien\\]' figure dans md.
        self.assertIn("\\[lien\\]", md)
        # On vérifie que '[lien](' ne figure pas dans md.
        self.assertNotIn("[lien](", md)

    def test_screen_and_plain_copy_are_separate(self):
        # On utilise ce texte pour raw ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        raw = "Dossier Brut : présent\nImages WEBP : absent"
        # On garde dans rows la valeur renvoyée par display_records.
        rows = display_records(pd.DataFrame([{NAS_COLUMN: raw}]))
        # On vérifie que '**Dossier Brut' figure dans rows[0][NAS_COLUMN].
        self.assertIn("**Dossier Brut", rows[0][NAS_COLUMN])
        # On vérifie que rows[0][NAS_PLAIN] correspond à raw.
        self.assertEqual(rows[0][NAS_PLAIN], raw)
        # On vérifie que plain_column_value(rows[0], NAS_COLUMN) correspond à raw.
        self.assertEqual(plain_column_value(rows[0], NAS_COLUMN), raw)

    def test_clipboard_multiline_tsv_keeps_one_cell_per_source_row(self):
        # On utilise ce texte pour raw ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        raw = 'Dossier Brut : présent\nErreur : "A, B"'
        # On garde dans rows la valeur renvoyée par display_records.
        rows = display_records(
            pd.DataFrame([{NAS_COLUMN: raw}, {NAS_COLUMN: "Images WEBP : absentes"}])
        )
        # On garde dans copied la valeur renvoyée par plain_clipboard.
        copied = plain_clipboard(rows, NAS_COLUMN)
        # On compare list(csv.reader(io.StringIO(copied), delimiter='\t')) à [[raw], ['Images WEBP :
        # absentes']].
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            list(csv.reader(io.StringIO(copied), delimiter="\t")),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            [[raw], ["Images WEBP : absentes"]],
        )
        # On vérifie que '**' ne figure pas dans copied.
        self.assertNotIn("**", copied)
        # On vérifie que plain_clipboard([{'vineyard_name': 'A'}, {'vineyard_name': 'B'}], 'vineyard…
        # correspond à 'A\nB'.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            plain_clipboard(
                [{"vineyard_name": "A"}, {"vineyard_name": "B"}], "vineyard_name"
            ),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            "A\nB",
        )

    def test_csv_multiline_no_markdown_filtered_order_visible_columns(self):
        # On utilise ce texte pour raw1 ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        raw1 = 'Dossier Brut : présent\nErreur : "A, B"'
        # On utilise ce texte pour raw2 ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        raw2 = "Images WEBP : non renseigné"
        # On garde dans data la valeur renvoyée par display_records.
        data = display_records(
            pd.DataFrame(
                [
                    {"vineyard_name": "A", NAS_COLUMN: raw1},
                    {"vineyard_name": "B", NAS_COLUMN: raw2},
                ]
            )
        )
        # On garde dans output la valeur renvoyée par plain_csv.
        output = plain_csv(
            [data[1], data[0]], [{"id": NAS_COLUMN, "name": "Constats NAS"}]
        )
        # On garde dans parsed une liste matérialisée à partir de
        # csv.reader(io.StringIO(output.lstrip('\ufeff'))).
        parsed = list(csv.reader(io.StringIO(output.lstrip("\ufeff"))))
        # On vérifie que parsed correspond à [['Constats NAS'], [raw2], [raw1]].
        self.assertEqual(parsed, [["Constats NAS"], [raw2], [raw1]])
        # On vérifie que '**' ne figure pas dans output.
        self.assertNotIn("**", output)
        # On vérifie que 'vineyard_name' ne figure pas dans output.
        self.assertNotIn("vineyard_name", output)

    def test_column_reselection_keeps_markdown(self):
        # On garde dans cols la valeur renvoyée par table_columns.
        cols = table_columns([NAS_COLUMN, "vineyard_name"], lambda x: x)
        # On vérifie que cols[0]['presentation'] correspond à 'markdown'.
        self.assertEqual(cols[0]["presentation"], "markdown")
        # On vérifie que 'presentation' ne figure pas dans cols[1].
        self.assertNotIn("presentation", cols[1])

    def test_table_safe_markdown_top_alignment_width_export(self):
        # On garde dans panel le panneau de tableau construit pour ces données.
        panel = table_panel(
            pd.DataFrame([{NAS_COLUMN: "Brut : présent", "vineyard_name": "A"}]),
            "example",
            "Test",
        )
        # On récupère find_component(panel, 'DataTable')[0] et on le garde dans table pour la suite.
        table = find_component(panel, "DataTable")[0]
        # On vérifie que table.markdown_options correspond à {'html': False}.
        self.assertEqual(table.markdown_options, {"html": False})
        # On vérifie que table.style_cell['verticalAlign'] correspond à 'top'.
        self.assertEqual(table.style_cell["verticalAlign"], "top")
        # On vérifie que table.style_cell_conditional[0]['minWidth'] correspond à '320px'.
        self.assertEqual(table.style_cell_conditional[0]["minWidth"], "320px")
        # On vérifie que table.export_format correspond à 'none'.
        self.assertEqual(table.export_format, "none")
        # On vérifie que NAS_PLAIN ne figure pas dans str(find_component(panel,
        # 'Dropdown')[0].options).
        self.assertNotIn(NAS_PLAIN, str(find_component(panel, "Dropdown")[0].options))
        # On attend que any((getattr(c, 'id', {}).get('role') == 'plain-export' for c in
        # find_component(panel, 'Button'))) soit évalué comme vrai pour ce cas de test.
        self.assertTrue(
            any(
                getattr(c, "id", {}).get("role") == "plain-export"
                for c in find_component(panel, "Button")
            )
        )

    def test_other_tables_keep_native_csv(self):
        # On garde dans panel le panneau de tableau construit pour ces données.
        panel = table_panel(pd.DataFrame([{"vineyard_name": "A"}]), "example", "Test")
        # On vérifie que find_component(panel, 'DataTable')[0].export_format correspond à 'csv'.
        self.assertEqual(find_component(panel, "DataTable")[0].export_format, "csv")
        # On vérifie que len(find_component(panel, 'Download')) correspond à 0.
        self.assertEqual(len(find_component(panel, "Download")), 0)

    def test_focus_titles_order_and_separate_quality_area(self):
        # On garde dans f un état de démonstration construit avec des données synthétiques.
        f = build_mock_state()
        # On garde dans aq les acquisitions complétées avec les champs calculés de présentation.
        aq = enrich_acquisitions(
            prepare_acquisitions(f["reconciliation_acquisition_current"])
        )
        # On garde dans ps les passages préparés pour leur lecture dans le dashboard.
        ps = prepare_passages(f["reconciliation_passage_current"])
        # On garde dans node la valeur renvoyée par render_focus.
        node = render_focus(aq, ps)
        # On construit criteria comme une liste à partir de c.id, pour chaque c de find_component(node,
        # 'Details') en ne gardant que les éléments qui passent le filtre.
        criteria = [
            c.id
            for c in find_component(node, "Details")
            if isinstance(getattr(c, "id", None), str) and c.id.startswith("criterion-")
        ]
        # On vérifie que criteria correspond à ['criterion-' + k for k in ['raw', 'backup', 'mapping',
        # 'processing', 'link….
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            criteria,
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            [
                "criterion-" + k
                for k in [
                    "raw",
                    "backup",
                    "mapping",
                    "processing",
                    "link",
                    "passage",
                    "vitimap",
                    "stocks",
                    "both",
                    "status",
                ]
            ],
        )
        # On vérifie que 'Passages identifiés dont le dossier est absent' figure dans str(node).
        self.assertIn("Passages identifiés dont le dossier est absent", str(node))
        # On vérifie que 'Ces passages figurent déjà dans les deux listes précédentes' figure dans
        # str(node).
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "Ces passages figurent déjà dans les deux listes précédentes", str(node)
        )
        # On récupère [c for c in find_component(node, 'Section') if getattr(c, 'id', None) ==… et on
        # le garde dans quality pour la suite.
        quality = [
            c
            for c in find_component(node, "Section")
            if getattr(c, "id", None) == "data-clarification"
        ][0]
        # On vérifie que 'Passages dont le lien à la production reste à vérifier' figure dans
        # str(quality).
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "Passages dont le lien à la production reste à vérifier", str(quality)
        )
        # On vérifie que 'pas comptés comme du travail restant' figure dans str(quality).
        self.assertIn("pas comptés comme du travail restant", str(quality))

    def test_v6_endpoints_and_export_callback_registered(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {"DASHBOARD_USE_MOCK": "1"}):
            # On garde dans app l’application Dash construite avec ses composants et callbacks.
            app = make_app()
        # On garde dans client la valeur renvoyée par app.server.test_client.
        client = app.server.test_client()
        # On vérifie que 'V6' figure dans client.get('/').get_data(as_text=True).
        self.assertIn("V6", client.get("/").get_data(as_text=True))
        # On garde dans deps la valeur renvoyée par client.get('/_dash-dependencies').get_json.
        deps = client.get("/_dash-dependencies").get_json()
        # On attend que any(('plain-download' in x['output'] for x in deps)) soit évalué comme vrai
        # pour ce cas de test.
        self.assertTrue(any("plain-download" in x["output"] for x in deps))


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
