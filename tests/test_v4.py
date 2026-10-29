# Lecture du fichier — Tests de v4.
#

# On sépare les copies d’objets, notamment pour comparer un état avant et après une opération.
import copy
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
# On rend disponibles build_mock_state depuis mock_fixture, pour les appels de ce fichier.
from mock_fixture import build_mock_state
# On rend disponibles DashboardState, _flatten_row, prepare_passages, load_dashboard_state depuis
# data_access, pour les appels de ce fichier.
from data_access import (
    DashboardState,
    _flatten_row,
    prepare_passages,
    load_dashboard_state,
)
# On rend disponibles * depuis history_engine, pour les appels de ce fichier.
from history_engine import *
# On rend disponibles serialise, select_snapshot, prepared, render_content, make_app,
# filter_focus_population, METRICS depuis dash_app, pour les appels de ce fichier.
from dash_app import (
    serialise,
    select_snapshot,
    prepared,
    render_content,
    make_app,
    filter_focus_population,
    METRICS,
)


class HistoryV4(unittest.TestCase):
    def setUp(self):
        # On garde dans self.f un état de démonstration construit avec des données synthétiques.
        self.f = build_mock_state()
        # On garde dans self.p la représentation sérialisable préparée pour ces données.
        self.p = serialise(DashboardState("mock", "Données fictives", self.f))

    def change_latest(self, kind, field, value, identifier=None):
        # On sélectionne dans self.f les éléments désignés par HIST[kind] ; df recevra cette sélection.
        df = self.f[HIST[kind]]
        # On garde dans mask le masque d’égalité calculé pour df['pipeline_execution_id'].
        mask = df["pipeline_execution_id"].eq("demo_20261022")
        # Cette branche traite le cas où identifier est évalué comme vrai.
        if identifier:
            # On met à jour mask avec cette opération, plutôt que créer une variable séparée.
            mask &= df[
                "acquisition_id_normalise"
                if kind in {"acquisition", "association"}
                else "passage_name"
            ].eq(identifier)
        # On parcourt df[mask].index[:1] ; i désigne l’élément courant de ce scénario.
        for i in df[mask].index[:1]:
            # On garde la valeur reçue sous le nom df.at[i, field] ; cette affectation ne copie pas à
            # elle seule un objet mutable.
            df.at[i, field] = value

    def test_no_change_despite_dates_and_run_ids(self):
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On attend que r.details.empty soit évalué comme vrai pour ce cas de test.
        self.assertTrue(r.details.empty)
        # On vérifie que 'Aucun changement' figure dans r.headline().
        self.assertIn("Aucun changement", r.headline())
        # On vérifie que r.expected correspond à r.comparable.
        self.assertEqual(r.expected, r.comparable)
        # On vérifie que r.counts()['examined'] correspond à 19.
        self.assertEqual(r.counts()["examined"], 19)

    def test_status_comment_nas_and_deliverable_changes(self):
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(
            # On fournit la sélection retenue via le paramètre selected de cet appel.
            self.f, selected=["demo_20261015", "demo_20261019"], latest=False
        )
        # On vérifie que 'Excel · statuts' figure dans set(r.details['Famille']).
        self.assertIn("Excel · statuts", set(r.details["Famille"]))
        # On vérifie que 'Excel · commentaires' figure dans set(r.details['Famille']).
        self.assertIn("Excel · commentaires", set(r.details["Famille"]))
        # On vérifie que 'NAS · constats' figure dans set(r.details['Famille']).
        self.assertIn("NAS · constats", set(r.details["Famille"]))
        # On vérifie que 'NAS · livrables' figure dans set(r.details['Famille']).
        self.assertIn("NAS · livrables", set(r.details["Famille"]))
        # On vérifie que r.counts()['acquisitions'] correspond à 1.
        self.assertEqual(r.counts()["acquisitions"], 1)
        # On vérifie que r.counts()['comments'] correspond à 1.
        self.assertEqual(r.counts()["comments"], 1)
        # On vérifie que r.counts()['passages'] correspond à 1.
        self.assertEqual(r.counts()["passages"], 1)
        # On attend que r.details['Référence précédente'].str.contains('demo_20261015').all() soit
        # évalué comme vrai pour ce cas de test.
        self.assertTrue(
            r.details["Référence précédente"].str.contains("demo_20261015").all()
        )

    def test_comments_separate_from_other_business_changes(self):
        # On appelle self.change_latest avec 'acquisition'.
        self.change_latest(
            "acquisition", "excel_comments", "Nouveau commentaire", "DEMO_A_001"
        )
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On vérifie que r.counts()['comments'] correspond à 1.
        self.assertEqual(r.counts()["comments"], 1)
        # On vérifie que r.counts()['processing'] correspond à 0.
        self.assertEqual(r.counts()["processing"], 0)
        # On vérifie que len(r.details) correspond à 1.
        self.assertEqual(len(r.details), 1)

    def test_excel_category_change(self):
        # On appelle self.change_latest avec 'acquisition'.
        self.change_latest("acquisition", "excel_perimeter", "Test", "DEMO_A_001")
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On vérifie que 'Catégorie déduite' figure dans r.details.iloc[0]['Information'].
        self.assertIn("Catégorie déduite", r.details.iloc[0]["Information"])
        # On vérifie que r.details.iloc[0]['Avant'] correspond à 'Production'.
        self.assertEqual(r.details.iloc[0]["Avant"], "Production")
        # On vérifie que r.details.iloc[0]['Après'] correspond à 'Test'.
        self.assertEqual(r.details.iloc[0]["Après"], "Test")

    def test_new_and_removed_entities_are_not_physical_deletions(self):
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(
            # On fournit la sélection retenue via le paramètre selected de cet appel.
            self.f, selected=["demo_20261019", "demo_20261021"], latest=False
        )
        # On vérifie que r.counts()['acquisitions'] correspond à 1.
        self.assertEqual(r.counts()["acquisitions"], 1)
        # On vérifie que r.counts()['passages'] correspond à 1.
        self.assertEqual(r.counts()["passages"], 1)
        # On vérifie que r.counts()['relationships'] correspond à 1.
        self.assertEqual(r.counts()["relationships"], 1)
        # On attend que r.details['Lecture prudente'].str.contains('ne prouve').all() soit évalué comme
        # vrai pour ce cas de test.
        self.assertTrue(r.details["Lecture prudente"].str.contains("ne prouve").all())
        # Reverse timestamps to exercise removal independently of ordering input.
        for name in [META, *HIST.values()]:
            # On sélectionne dans self.f les éléments désignés par name ; df recevra cette sélection.
            df = self.f[name]
            # On garde dans mask le masque d’égalité calculé pour df.pipeline_execution_id.
            mask = df.pipeline_execution_id.eq("demo_20261019")
            # On utilise ce texte pour df.loc[mask, 'reconciled_at'] ; il ne dépend pas d’une valeur
            # récupérée ailleurs à cet endroit.
            df.loc[mask, "reconciled_at"] = "2026-10-23T08:00:00Z"
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(
            # On fournit la sélection retenue via le paramètre selected de cet appel.
            self.f, selected=["demo_20261019", "demo_20261021"], latest=False
        )
        # On attend que r.details['Après'].eq('Non recensé').all() soit évalué comme vrai pour ce cas
        # de test.
        self.assertTrue(r.details["Après"].eq("Non recensé").all())

    def test_unknown_not_false(self):
        # On appelle self.change_latest avec 'passage'.
        self.change_latest("passage", "vitimap_created", None, "Passage 1")
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On vérifie que 'vérifiabilité' figure dans ' '.join(r.details['Lecture prudente']).
        self.assertIn("vérifiabilité", " ".join(r.details["Lecture prudente"]))
        # On vérifie que 'Non renseigné' figure dans r.details.iloc[0]['Après'].
        self.assertIn("Non renseigné", r.details.iloc[0]["Après"])

    def test_read_error_kept_and_not_declared_deletion(self):
        # On appelle self.change_latest avec 'passage'.
        self.change_latest("passage", "vitimap_created", False, "Passage 1")
        # On appelle self.change_latest avec 'passage'.
        self.change_latest(
            "passage", "vitimap_error", "Permission refusée", "Passage 1"
        )
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On vérifie que 'Erreur de contrôle' figure dans ' '.join(r.details['Lecture prudente']).
        self.assertIn("Erreur de contrôle", " ".join(r.details["Lecture prudente"]))

    def test_changes_then_return_not_hidden(self):
        # On appelle self.change_latest avec 'acquisition'.
        self.change_latest(
            "acquisition", "excel_pipeline_status", "Terminé", "DEMO_A_001"
        )
        # On sélectionne dans self.f les éléments désignés par HIST['acquisition'] ; df recevra cette
        # sélection.
        df = self.f[HIST["acquisition"]]
        # On utilise ce texte pour df.loc[df.pipeline_execution_id.eq('demo_20261021') & df.acquisi… ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        df.loc[
            df.pipeline_execution_id.eq("demo_20261021")
            & df.acquisition_id_normalise.eq("DEMO_A_001"),
            "excel_pipeline_status",
        ] = "En cours"
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(
            self.f,
            # On fournit la sélection retenue via le paramètre selected de cet appel.
            selected=["demo_20261019", "demo_20261021", "demo_20261022"],
            latest=False,
        )
        # On sélectionne dans r.details les éléments désignés par r.details['Famille'].eq('Excel ·
        # statuts') ; statuses recevra cette sélection.
        statuses = r.details[r.details["Famille"].eq("Excel · statuts")]
        # On vérifie que len(statuses) correspond à 2.
        self.assertEqual(len(statuses), 2)
        # On vérifie que r.counts()['acquisitions'] correspond à 2.
        self.assertEqual(r.counts()["acquisitions"], 2)  # A004 also added on 21st
        # On vérifie que r.counts()['examined'] correspond à 19.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            r.counts()["examined"], 19
        )  # denominator union, not transition sum

    def test_relationship_changes_exact_not_cartesian_product(self):
        # On appelle self.change_latest avec 'association'.
        self.change_latest(
            "association", "passage_name", "Passage modifié", "DEMO_A_001"
        )
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On vérifie que r.counts()['relationships'] correspond à 2.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            r.counts()["relationships"], 2
        )  # removed old link + new exact link
        # On attend que r.details['Famille'].eq('Rattachements').all() soit évalué comme vrai pour ce
        # cas de test.
        self.assertTrue(r.details["Famille"].eq("Rattachements").all())

    def test_missing_view_is_partial_not_unchanged(self):
        # On retire self.f[HIST['passage']] de son emplacement ; la suite ne doit plus s’appuyer sur
        # cette entrée.
        del self.f[HIST["passage"]]
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On contrôle le résultat avec assertLess et les valeurs attendues indiquées juste dessous.
        self.assertLess(r.comparable, r.expected)
        # On vérifie que 'partielle' figure dans r.headline().
        self.assertIn("partielle", r.headline())
        # On attend que r.messages soit évalué comme vrai pour ce cas de test.
        self.assertTrue(r.messages)

    def test_missing_all_detail_views_suspends(self):
        # On parcourt HIST.values() ; name désigne l’élément courant de ce scénario.
        for name in HIST.values():
            # On retire self.f[name] de son emplacement ; la suite ne doit plus s’appuyer sur cette
            # entrée.
            del self.f[name]
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On vérifie que r.comparable correspond à 0.
        self.assertEqual(r.comparable, 0)
        # On vérifie que 'suspendue' figure dans r.headline().
        self.assertIn("suspendue", r.headline())

    def test_duplicate_or_lost_detail_blocks_grain(self):
        # On récupère HIST['acquisition'] et on le garde dans name pour la suite.
        name = HIST["acquisition"]
        # On sélectionne dans self.f les éléments désignés par name ; df recevra cette sélection.
        df = self.f[name]
        # On garde dans self.f[name] l’assemblage des tableaux suivant l’axe et les options indiqués.
        self.f[name] = pd.concat([df, df.tail(1)], ignore_index=True)
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On contrôle le résultat avec assertLess et les valeurs attendues indiquées juste dessous.
        self.assertLess(r.comparable, r.expected)
        # On vérifie que 'incohérent' figure dans ' '.join(r.messages).
        self.assertIn("incohérent", " ".join(r.messages))

    def test_reused_nas_still_compares_latest_excel_executions(self):
        # On utilise ce texte pour self.f[META].loc[self.f[META].pipeline_execution_id.eq('demo_202… ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.f[META].loc[
            self.f[META].pipeline_execution_id.eq("demo_20261022"),
            "nas_pipeline_execution_id",
        ] = "demo_20261021"
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On attend que r.timeline['Référence'].str.contains('demo_20261021|demo_20261022').all() soit
        # évalué comme vrai pour ce cas de test.
        self.assertTrue(
            r.timeline["Référence"].str.contains("demo_20261021|demo_20261022").all()
        )
        # On garde dans explicit la comparaison des deux états historiques demandés.
        explicit = compare_history(
            # On fournit la sélection retenue via le paramètre selected de cet appel.
            self.f, selected=["demo_20261021", "demo_20261022"], latest=False
        )
        # On vérifie que len(explicit.timeline) correspond à 4.
        self.assertEqual(len(explicit.timeline), 4)

    def test_partial_single_observation_vineyard_visible(self):
        # On sélectionne dans self.f les éléments désignés par META ; df recevra cette sélection.
        df = self.f[META]
        # On sélectionne dans df les éléments désignés par ~df.vineyard_key.eq('demo_b') |
        # df.pipeline_execution_id.eq('demo_20261022') ; self.f[META] recevra cette sélection.
        self.f[META] = df[
            ~df.vineyard_key.eq("demo_b") | df.pipeline_execution_id.eq("demo_20261022")
        ]
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On contrôle le résultat avec assertLess et les valeurs attendues indiquées juste dessous.
        self.assertLess(r.comparable, r.expected)
        # On vérifie que 'partielle' figure dans r.headline().
        self.assertIn("partielle", r.headline())

    def test_vineyard_filter_isolation(self):
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f, "Domaine démo A")
        # On vérifie que set(r.timeline.Vignoble) correspond à {'Domaine démo A'}.
        self.assertEqual(set(r.timeline.Vignoble), {"Domaine démo A"})
        # On vérifie que len(batch_options(self.f, 'Domaine démo A')) correspond à 4.
        self.assertEqual(len(batch_options(self.f, "Domaine démo A")), 4)

    def test_explicit_dates_selection_only(self):
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(
            # On fournit la sélection retenue via le paramètre selected de cet appel.
            self.f, selected=["demo_20261015", "demo_20261022"], latest=False
        )
        # On vérifie que len(r.timeline) correspond à 4.
        self.assertEqual(len(r.timeline), 4)
        # On vérifie que set(r.timeline['Observation NAS'].str[:10]) correspond à {'15/10/2026',
        # '22/10/2026'}.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            set(r.timeline["Observation NAS"].str[:10]), {"15/10/2026", "22/10/2026"}
        )

    def test_at_least_two_dates_needed(self):
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f, selected=["demo_20261022"], latest=False)
        # On vérifie que r.comparable correspond à 0.
        self.assertEqual(r.comparable, 0)
        # On vérifie que 'Aucun changement' ne figure pas dans r.headline().
        self.assertNotIn("Aucun changement", r.headline())

    def test_full_historical_state_not_current(self):
        # On répartit les valeurs renvoyées par select_snapshot entre (p, msg) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        p, msg = select_snapshot(self.p, "demo_20261015")
        # On vérifie que p['snapshot_run'] correspond à 'demo_20261015'.
        self.assertEqual(p["snapshot_run"], "demo_20261015")
        # On répartit les valeurs renvoyées par prepared entre (aq, ps, fr) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        aq, ps, fr = prepared(p, "__ALL__", "__ALL__", "")
        # On vérifie que len(aq) correspond à 6.
        self.assertEqual(len(aq), 6)
        # On vérifie que len(ps) correspond à 5.
        self.assertEqual(len(ps), 5)
        # On vérifie que 'DEMO_A_004' ne figure pas dans set(aq.acquisition_id_normalise).
        self.assertNotIn("DEMO_A_004", set(aq.acquisition_id_normalise))
        # On récupère aq[aq.acquisition_id_normalise.eq('DEMO_A_001')].iloc[0] et on le garde dans a
        # pour la suite.
        a = aq[aq.acquisition_id_normalise.eq("DEMO_A_001")].iloc[0]
        # On attend que a.treated_technical soit évalué comme faux pour ce cas de test.
        self.assertFalse(a.treated_technical)
        # On vérifie que a.excel_status_display correspond à 'En cours'.
        self.assertEqual(a.excel_status_display, "En cours")
        # On vérifie que a.parcel_name correspond à 'Parcelle 1'.
        self.assertEqual(a.parcel_name, "Parcelle 1")
        # On parcourt ['overview', 'search', 'focus', 'evolution'] ; tab désigne l’élément courant de
        # ce scénario.
        for tab in ["overview", "search", "focus", "evolution"]:
            # On vérifie que render_content(tab, p, '__ALL__', '__ALL__', None) n’est pas None.
            self.assertIsNotNone(render_content(tab, p, "__ALL__", "__ALL__", None))
        # On vérifie que 'État historique' figure dans msg.
        self.assertIn("État historique", msg)

    def test_historical_missing_detail_never_falls_back(self):
        # On rend p indépendant de self.p, y compris pour les listes et dictionnaires imbriqués ;
        # les modifications du scénario ne doivent pas contaminer l’état de départ.
        p = copy.deepcopy(self.p)
        # On retire p['frames'][HIST['association']] de son emplacement ; la suite ne doit plus
        # s’appuyer sur cette entrée.
        del p["frames"][HIST["association"]]
        # On répartit les valeurs renvoyées par select_snapshot entre (out, msg) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        out, msg = select_snapshot(p, "demo_20261015")
        # On vérifie que out['mode'] correspond à 'unavailable'.
        self.assertEqual(out["mode"], "unavailable")
        # On vérifie que 'suspendue' figure dans msg.
        self.assertIn("suspendue", msg)

    def test_historical_partial_batch_no_current_fill(self):
        # On parcourt [META, *HIST.values()] ; name désigne l’élément courant de ce scénario.
        for name in [META, *HIST.values()]:
            # On sélectionne dans self.f les éléments désignés par name ; df recevra cette sélection.
            df = self.f[name]
            # On sélectionne dans df les éléments désignés par
            # ~(df.pipeline_execution_id.eq('demo_20261015') & df.vineyard_key.eq('demo_b')) ;
            # self.f[name] recevra cette sélection.
            self.f[name] = df[
                ~(
                    df.pipeline_execution_id.eq("demo_20261015")
                    & df.vineyard_key.eq("demo_b")
                )
            ]
        # On répartit les valeurs renvoyées par historical_frames entre (frozen, names) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        frozen, names = historical_frames(self.f, "demo_20261015")
        # On vérifie que names correspond à ['Domaine démo A'].
        self.assertEqual(names, ["Domaine démo A"])
        # On vérifie que len(frozen['reconciliation_acquisition_current']) correspond à 3.
        self.assertEqual(len(frozen["reconciliation_acquisition_current"]), 3)

    def test_criterion_null_when_recorded_unverifiable(self):
        # On garde dans df les passages préparés pour leur lecture dans le dashboard.
        df = prepare_passages(
            pd.DataFrame(
                [
                    dict(
                        stocks_json_exists=True,
                        has_non_healthy_status=True,
                        vitiparcel_ready_verifiable=False,
                        vitiparcel_ready_for_delivery=False,
                    )
                ]
            )
        )
        # On attend None pour df.iloc[0].vitiparcel_technical_criterion_satisfied : aucune valeur
        # n’est confirmée dans ce cas.
        self.assertIsNone(df.iloc[0].vitiparcel_technical_criterion_satisfied)

    def test_unknown_recorded_verifiability_is_not_false(self):
        # On garde dans df les passages préparés pour leur lecture dans le dashboard.
        df = prepare_passages(
            pd.DataFrame(
                [
                    dict(
                        stocks_json_exists=False,
                        has_non_healthy_status=False,
                        vitiparcel_ready_verifiable=None,
                        vitiparcel_ready_for_delivery=False,
                    )
                ]
            )
        )
        # On attend None pour df.iloc[0].vitiparcel_technical_criterion_satisfied : aucune valeur
        # n’est confirmée dans ce cas.
        self.assertIsNone(df.iloc[0].vitiparcel_technical_criterion_satisfied)

    def test_restore_current_exactly(self):
        # On répartit les valeurs renvoyées par select_snapshot entre (p, msg) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        p, msg = select_snapshot(self.p, "__CURRENT__")
        # On vérifie l’identité de p avec self.p, et pas seulement une égalité de valeur.
        self.assertIs(p, self.p)
        # On vérifie que 'Bilans actifs' figure dans msg.
        self.assertIn("Bilans actifs", msg)

    def test_invalid_historical_run_is_not_current(self):
        # On répartit les valeurs renvoyées par select_snapshot entre (p, msg) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        p, msg = select_snapshot(self.p, "invalid")
        # On vérifie que p['mode'] correspond à 'unavailable'.
        self.assertEqual(p["mode"], "unavailable")

    def test_solid_hover_and_legend_updated(self):
        # On garde dans page la représentation textuelle de render_content('overview', self.p,
        # '__ALL__', '__ALL__', None).
        page = str(render_content("overview", self.p, "__ALL__", "__ALL__", None))
        # On vérifie que 'catégorie déduite des informations' figure dans page.
        self.assertIn("catégorie déduite des informations", page)
        # On vérifie que 'Ce second nombre' ne figure pas dans page.
        self.assertNotIn("Ce second nombre", page)
        # On vérifie que 'Pour Vitimap comme pour Vitiparcel' figure dans page.
        self.assertIn("Pour Vitimap comme pour Vitiparcel", page)
        # On vérifie que METRICS['all'][0] correspond à 'Acquisitions recensées'.
        self.assertEqual(METRICS["all"][0], "Acquisitions recensées")
        # On vérifie que 'Tous statuts confondus' figure dans page.
        self.assertIn("Tous statuts confondus", page)
        # On garde dans narrowed la représentation textuelle de render_content('overview', self.p,
        # '__ALL__', 'Test', None).
        narrowed = str(render_content("overview", self.p, "__ALL__", "Test", None))
        # On vérifie que 'Catégorie sélectionnée : Test' figure dans narrowed.
        self.assertIn("Catégorie sélectionnée : Test", narrowed)

    def test_local_focus_filter_no_side_effects(self):
        # On garde dans df un tableau pandas construit avec les données indiquées.
        df = pd.DataFrame({"vineyard_name": ["A", "B"], "id": [1, 2]})
        # On garde dans selected la valeur renvoyée par filter_focus_population.
        selected = filter_focus_population(df, "A")
        # On vérifie que selected.id.tolist() correspond à [1].
        self.assertEqual(selected.id.tolist(), [1])
        # On vérifie que len(df) correspond à 2.
        self.assertEqual(len(df), 2)
        # On vérifie que len(filter_focus_population(df, None)) correspond à 2.
        self.assertEqual(len(filter_focus_population(df, None)), 2)

    def test_history_payload_flatten(self):
        # On garde dans row la valeur renvoyée par _flatten_row.
        row = _flatten_row(
            {
                # On associe la clé 'recorded_excel_pipeline_status' à cette valeur dans les données de
                # ce scénario.
                "recorded_excel_pipeline_status": "En cours",
                # On renseigne le contenu détaillé sous la clé 'payload'.
                "payload": {
                    # On associe la clé 'excel_comments' à cette valeur dans les données de ce
                    # scénario.
                    "excel_comments": "Commentaire",
                    # On renseigne la présence dans les traitements sous la clé
                    # 'found_in_processing_live'.
                    "found_in_processing_live": True,
                },
            }
        )
        # On vérifie que row['excel_comments'] correspond à 'Commentaire'.
        self.assertEqual(row["excel_comments"], "Commentaire")
        # On attend que row['found_in_processing_live'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(row["found_in_processing_live"])

    def test_zero_snapshots_not_zero_business(self):
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history({})
        # On vérifie que 'indisponible' figure dans r.headline().
        self.assertIn("indisponible", r.headline())
        # On garde dans p la représentation sérialisable préparée pour ces données.
        p = serialise(DashboardState("unavailable", "Non disponible", {}))
        # On vérifie que 'Acquisitions recensées' ne figure pas dans str(render_content('overview',
        # p, '__ALL__', '__ALL__', None)).
        self.assertNotIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "Acquisitions recensées",
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            str(render_content("overview", p, "__ALL__", "__ALL__", None)),
        )

    def test_bundle_optional_warnings_no_mock(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with (
            patch.dict(os.environ, {"DASHBOARD_USE_MOCK": "0"}),
            patch("data_access.DatabaseClient") as db,
        ):
            # On regroupe dans db.return_value.healthcheck.return_value ces champs nommés ; on pourra
            # les retrouver par leur clé plutôt que par leur position.
            db.return_value.healthcheck.return_value = {
                # On associe la clé 'database_name' à cette valeur dans les données de ce scénario.
                "database_name": "suivi_acquisitions"
            }
            # On rassemble dans db.return_value.fetch_bundle.return_value les 2 éléments explicitement
            # indiqués pour ce cas d’essai.
            db.return_value.fetch_bundle.return_value = ({}, [HIST["passage"]])
            # On garde dans state la valeur renvoyée par load_dashboard_state.
            state = load_dashboard_state()
            # On vérifie que state.mode correspond à 'database'.
            self.assertEqual(state.mode, "database")
            # On vérifie que 'partiellement indisponible' figure dans state.status_message.
            self.assertIn("partiellement indisponible", state.status_message)
            # On vérifie que HIST['passage'] ne figure pas dans state.frames.
            self.assertNotIn(HIST["passage"], state.frames)

    def test_endpoints_and_no_secret_in_archive_sources(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {"DASHBOARD_USE_MOCK": "1"}):
            # On garde dans app l’application Dash construite avec ses composants et callbacks.
            app = make_app()
        # On garde dans client la valeur renvoyée par app.server.test_client.
        client = app.server.test_client()
        # On vérifie que client.get('/_dash-layout').status_code correspond à 200.
        self.assertEqual(client.get("/_dash-layout").status_code, 200)
        # On vérifie que 'V6' figure dans client.get('/').get_data(as_text=True).
        self.assertIn("V6", client.get("/").get_data(as_text=True))
        # On garde dans deps la valeur renvoyée par client.get('/_dash-dependencies').get_json.
        deps = client.get("/_dash-dependencies").get_json()
        # On attend que any(('focus-local' in c['output'] for c in deps)) soit évalué comme vrai pour
        # ce cas de test.
        self.assertTrue(any("focus-local" in c["output"] for c in deps))
        # On attend que any(('evolution-summary-results' in c['output'] for c in deps)) soit évalué
        # comme vrai pour ce cas de test.
        self.assertTrue(any("evolution-summary-results" in c["output"] for c in deps))


class RealSchemaShape(unittest.TestCase):
    def setUp(self):
        # On garde dans self.f un état de démonstration construit avec des données synthétiques.
        self.f = build_mock_state()

    def test_sql_011_payload_shapes(self):
        # Exercise the actual SQL contract rather than just flattened fixtures.
        identities = IDENTITY + [
            "vineyard_name",
            "nas_pipeline_execution_id",
            "nas_checked_at",
            "reconciled_at",
            "excel_version_id",
            "excel_publication_id",
        ]
        # On parcourt HIST.items() ; (kind, view) désigne l’élément courant de ce scénario.
        for kind, view in HIST.items():
            # On prépare rows comme liste vide ; on la remplira au fil des opérations suivantes.
            rows = []
            # On parcourt self.f[view].to_dict('records') ; raw désigne l’élément courant de ce
            # scénario.
            for raw in self.f[view].to_dict("records"):
                # On indexe exposed par k ; chaque clé sera associée à raw[k]. Une même clé ne peut
                # garder qu’une valeur.
                exposed = {k: raw[k] for k in identities + KEYS[kind] if k in raw}
                # On indexe exposed['payload'] par k ; chaque clé sera associée à v. Une même clé ne
                # peut garder qu’une valeur.
                exposed["payload"] = {
                    k: v for k, v in raw.items() if k not in identities
                }
                # On vérifie ce cas avant la suite : kind correspond au texte 'acquisition'.
                if kind == "acquisition":
                    # On garde dans exposed['recorded_excel_perimeter'] le champ 'excel_perimeter' de
                    # raw, ou None si la clé est absente.
                    exposed["recorded_excel_perimeter"] = raw.get("excel_perimeter")
                    # On garde dans exposed['recorded_excel_pipeline_status'] le champ
                    # 'excel_pipeline_status' de raw, ou None si la clé est absente.
                    exposed["recorded_excel_pipeline_status"] = raw.get(
                        "excel_pipeline_status"
                    )
                # On vérifie ce cas avant la suite : kind correspond au texte 'passage'.
                if kind == "passage":
                    # On distribue ces valeurs entre a, b, dans l’ordre de l’affectation. Chaque nom
                    # reçoit son propre élément.
                    a, b = (
                        raw.get("stocks_json_exists"),
                        raw.get("has_non_healthy_status"),
                    )
                    # On calcule exposed['vitiparcel_ready_verifiable'] avec ces conditions liées par
                    # and ; Python s’arrête dès qu’une valeur est évaluée comme fausse.
                    exposed["vitiparcel_ready_verifiable"] = (
                        a is not None and b is not None
                    )
                    # On calcule exposed['vitiparcel_ready_for_delivery'] avec ces conditions liées par
                    # and ; Python s’arrête dès qu’une valeur est évaluée comme fausse.
                    exposed["vitiparcel_ready_for_delivery"] = a is True and b is True
                # On ajoute exposed à la fin de rows ; les éléments précédents restent conservés.
                rows.append(exposed)
            # On garde dans self.f[view] un tableau pandas construit avec les données indiquées.
            self.f[view] = pd.DataFrame(rows)
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On attend que r.details.empty soit évalué comme vrai pour ce cas de test.
        self.assertTrue(r.details.empty)
        # On vérifie que r.comparable correspond à r.expected.
        self.assertEqual(r.comparable, r.expected)
        # On répartit les valeurs renvoyées par historical_frames entre (frozen, names) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        frozen, names = historical_frames(self.f, "demo_20261015")
        # On vérifie que len(frozen['reconciliation_acquisition_current']) correspond à 6.
        self.assertEqual(len(frozen["reconciliation_acquisition_current"]), 6)
        # On vérifie que int(yes(frozen['reconciliation_passage_current'], 'vitiparcel_technical_cri…
        # correspond à 0.
        self.assertEqual(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            int(
                yes(
                    frozen["reconciliation_passage_current"],
                    "vitiparcel_technical_criterion_satisfied",
                ).sum()
            ),
            # On fournit la valeur attendue ou la collection de comparaison pour cette assertion.
            0,
        )
        # On garde dans prev la comparaison des deux états historiques demandés.
        prev = compare_history(
            # On fournit la sélection retenue via le paramètre selected de cet appel.
            self.f, selected=["demo_20261015", "demo_20261022"], latest=False
        )
        # On attend que prev.details.empty soit évalué comme faux pour ce cas de test.
        self.assertFalse(prev.details.empty)

    def test_missing_vineyard_snapshot_not_zero(self):
        # On parcourt [META, *HIST.values()] ; name désigne l’élément courant de ce scénario.
        for name in [META, *HIST.values()]:
            # On sélectionne dans self.f les éléments désignés par name ; df recevra cette sélection.
            df = self.f[name]
            # On sélectionne dans df les éléments désignés par
            # ~(df.pipeline_execution_id.eq('demo_20261015') & df.vineyard_key.eq('demo_b')) ;
            # self.f[name] recevra cette sélection.
            self.f[name] = df[
                ~(
                    df.pipeline_execution_id.eq("demo_20261015")
                    & df.vineyard_key.eq("demo_b")
                )
            ]
        # On garde dans p la représentation sérialisable préparée pour ces données.
        p = serialise(DashboardState("mock", "Fictif", self.f))
        # On répartit les valeurs renvoyées par select_snapshot entre (hist, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        hist, _ = select_snapshot(p, "demo_20261015")
        # On garde dans content la représentation textuelle de render_content('overview', hist,
        # 'Domaine démo B', '__ALL__', None).
        content = str(
            render_content("overview", hist, "Domaine démo B", "__ALL__", None)
        )
        # On vérifie que 'Vignoble non couvert' figure dans content.
        self.assertIn("Vignoble non couvert", content)
        # On vérifie que 'metric-value' ne figure pas dans content.
        self.assertNotIn("metric-value", content)

    def test_zero_counts_are_valid_complete_snapshots(self):
        # On garde dans meta une copie de self.f[META] pour travailler sur cet objet séparément.
        meta = self.f[META].copy()
        # On parcourt [META, *HIST.values()] ; name désigne l’élément courant de ce scénario.
        for name in [META, *HIST.values()]:
            # On sélectionne dans self.f les éléments désignés par name ; df recevra cette sélection.
            df = self.f[name]
            # On garde dans self.f[name] une copie de df[~df.vineyard_key.eq('demo_b')] pour travailler
            # sur cet objet séparément.
            self.f[name] = df[~df.vineyard_key.eq("demo_b")].copy()
        # On garde dans meta une copie de meta[meta.vineyard_key.eq('demo_b')] pour travailler sur cet
        # objet séparément.
        meta = meta[meta.vineyard_key.eq("demo_b")].copy()
        # On parcourt ['acquisition_count', 'passage_count', 'association_count', 'declared_acq… ;
        # field_ désigne l’élément courant de ce scénario.
        for field_ in [
            "acquisition_count",
            "passage_count",
            "association_count",
            "declared_acquisition_count",
            "declared_passage_count",
            "declared_association_count",
        ]:
            # On fixe meta[field_] à 0 pour cette étape du scénario de test.
            meta[field_] = 0
        # On garde dans self.f[META] l’assemblage des tableaux suivant l’axe et les options indiqués.
        self.f[META] = pd.concat([self.f[META], meta], ignore_index=True)
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On vérifie que r.expected correspond à r.comparable.
        self.assertEqual(r.expected, r.comparable)
        # On attend que r.details.empty soit évalué comme vrai pour ce cas de test.
        self.assertTrue(r.details.empty)

    def test_readonly_bundle_uses_one_connection_and_safe_optional_error(self):
        # On rend disponibles DatabaseClient depuis database, pour les appels de ce fichier.
        from database import DatabaseClient

        class Cursor:
            def fetchall(self):
                # On renvoie ces 1 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
                # décompose.
                return [{"example": 1}]

        class Connection:
            def __init__(self):
                # On prépare self.queries comme liste vide ; on la remplira au fil des opérations
                # suivantes.
                self.queries = []
                # On initialise self.rolled à False ; les branches suivantes pourront modifier cet
                # état.
                self.rolled = False

            def __enter__(self):
                # On remet self à l’appelant ; les étapes suivantes de cette fonction ne sont plus
                # parcourues.
                return self

            def __exit__(self, *args):
                # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
                pass

            def execute(self, sql):
                # On ajoute sql à la fin de self.queries ; les éléments précédents restent conservés.
                self.queries.append(sql)
                # On vérifie ce cas avant la suite : le texte '"missing_view"' appartient à sql.
                if '"missing_view"' in sql:
                    # On interrompt cette branche avec RuntimeError : 'not available'.
                    raise RuntimeError("not available")
                # On fournit à l’appelant la valeur renvoyée par Cursor.
                return Cursor()

            def rollback(self):
                # On initialise self.rolled à True ; les branches suivantes pourront modifier cet état.
                self.rolled = True

        # On garde dans connection la valeur renvoyée par Connection.
        connection = Connection()
        # On remplace temporairement DatabaseClient dans ce bloc de test ; le réglage initial sera
        # rétabli à sa sortie.
        with (
            patch.object(DatabaseClient, "__init__", return_value=None),
            patch.object(
                # On fixe la réponse de ce double de test ; aucune vraie opération de la dépendance
                # n’est nécessaire pour obtenir cette valeur.
                DatabaseClient, "_connect", return_value=connection
            ) as connect,
        ):
            # On garde dans client la valeur renvoyée par DatabaseClient.
            client = DatabaseClient()
            # On répartit les valeurs renvoyées par client.fetch_bundle entre (rows, missing) ; leur
            # ordre doit correspondre à celui prévu par cet appel.
            rows, missing = client.fetch_bundle(
                ["required_view"], ["missing_view", "next_history"]
            )
            # On vérifie que connect.call_count correspond à 1.
            self.assertEqual(connect.call_count, 1)
        # On vérifie que 'READ ONLY' figure dans connection.queries[0].
        self.assertIn("READ ONLY", connection.queries[0])
        # On vérifie que 'REPEATABLE READ' figure dans connection.queries[0].
        self.assertIn("REPEATABLE READ", connection.queries[0])
        # On attend que connection.rolled soit évalué comme vrai pour ce cas de test.
        self.assertTrue(connection.rolled)
        # On vérifie que 'ROLLBACK TO SAVEPOINT optional_history' figure dans connection.queries.
        self.assertIn("ROLLBACK TO SAVEPOINT optional_history", connection.queries)
        # On vérifie que 'next_history' figure dans rows.
        self.assertIn("next_history", rows)
        # On vérifie que missing correspond à ['missing_view'].
        self.assertEqual(missing, ["missing_view"])
        # On attend que any((q.startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'TRUNCATE', 'DROP',
        # 'GRANT')) for q in connection.… soit évalué comme faux pour ce cas de test.
        self.assertFalse(
            any(
                q.startswith(
                    (
                        "INSERT",
                        "UPDATE",
                        "DELETE",
                        "CREATE",
                        "TRUNCATE",
                        "DROP",
                        "GRANT",
                    )
                )
                for q in connection.queries
            )
        )


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
