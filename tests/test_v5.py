# Lecture du fichier — Tests de v5.
#

"""Contrats V5 : visibilité, choix explicites, cache borné et provenance."""

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
# On rend disponibles DashboardState depuis data_access, pour les appels de ce fichier.
from data_access import DashboardState
# On rend disponibles serialise, select_snapshot, render_content, make_app depuis dash_app, pour les
# appels de ce fichier.
from dash_app import serialise, select_snapshot, render_content, make_app
# On rend disponibles * depuis history_engine, pour les appels de ce fichier.
from history_engine import *
# On rend disponibles comparison_request, selection_feedback, comparison_for_store depuis evolution_ui,
# pour les appels de ce fichier.
from evolution_ui import comparison_request, selection_feedback, comparison_for_store
# On rend disponibles put_store, resolve_store, cached depuis state_store, pour les appels de ce
# fichier.
from state_store import put_store, resolve_store, cached


class V5(unittest.TestCase):
    def setUp(self):
        # On garde dans self.f un état de démonstration construit avec des données synthétiques.
        self.f = build_mock_state()
        # On garde dans self.p la représentation sérialisable préparée pour ces données.
        self.p = serialise(DashboardState("mock", "Données fictives", self.f))

    def add_run(self, date, names, run):
        # On garde dans template le contenu de self.f[META].iloc[-1] sous forme de dictionnaires, selon
        # l’orientation indiquée.
        template = self.f[META].iloc[-1].to_dict()
        # On prépare extra comme liste vide ; on la remplira au fil des opérations suivantes.
        extra = []
        # On parcourt names en gardant aussi sa position dans (i, name) ; le comptage commence à zéro.
        for i, name in enumerate(names):
            # On ajoute dict(template, vineyard_name=name, vineyard_key=name,
            # pipeline_execution_id=run, reconcil… à la fin de extra ; les éléments précédents restent
            # conservés.
            extra.append(
                dict(
                    template,
                    # On fournit le nom du domaine via le paramètre vineyard_name de cet appel.
                    vineyard_name=name,
                    # On fournit la clé du domaine via le paramètre vineyard_key de cet appel.
                    vineyard_key=name,
                    # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id
                    # de cet appel.
                    pipeline_execution_id=run,
                    reconciliation_run_id=run + "_" + str(i),
                    nas_pipeline_execution_id=run,
                    nas_checked_at=date,
                    # On fournit la date du rapprochement via le paramètre reconciled_at de cet appel.
                    reconciled_at=date,
                    reconciliation_loaded_at=date,
                )
            )
        # On garde dans self.f[META] l’assemblage des tableaux suivant l’axe et les options indiqués.
        self.f[META] = pd.concat([self.f[META], pd.DataFrame(extra)], ignore_index=True)

    def test_preproduction_tests_hidden_but_not_deleted(self):
        # On appelle self.add_run avec '2026-10-07T11:22:00Z'.
        self.add_run("2026-10-07T11:22:00Z", ["DomaineDemoD"], "test_oct7")
        # On appelle self.add_run avec '2026-10-14T12:12:00Z'.
        self.add_run("2026-10-14T12:12:00Z", ["DomaineDemoD"], "test_oct14")
        # On appelle self.add_run avec '2026-10-14T12:49:00Z'.
        self.add_run(
            "2026-10-14T12:49:00Z", sorted(APPROVED_VINEYARDS), "business_first"
        )
        # On garde dans count le nombre d’éléments de self.f[META].
        count = len(self.f[META])
        # On garde dans options les options de sélection des lots disponibles.
        options = batch_options(self.f)
        # On vérifie que 'business_first' figure dans {o['value'] for o in options}.
        self.assertIn("business_first", {o["value"] for o in options})
        # On attend que {'test_oct7', 'test_oct14'} & {o['value'] for o in options} soit évalué comme
        # faux pour ce cas de test.
        self.assertFalse({"test_oct7", "test_oct14"} & {o["value"] for o in options})
        # On vérifie que len(self.f[META]) correspond à count.
        self.assertEqual(len(self.f[META]), count)
        # A single-vineyard UI filter must not hide the valid eight-vineyard baseline.
        self.assertIn(
            # On fournit la valeur obtenue ou l’élément recherché pour cette assertion.
            "business_first", {o["value"] for o in batch_options(self.f, "DomaineDemoD")}
        )
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle historical_frames avec self.f.
            historical_frames(self.f, "test_oct14")

    def test_later_partial_runs_not_silently_removed(self):
        # On appelle self.add_run avec '2026-10-23T08:30:00Z'.
        self.add_run("2026-10-23T08:30:00Z", ["DomaineDemoD"], "later_partial")
        # On vérifie que batch_options(self.f)[0]['value'] correspond à 'later_partial'.
        self.assertEqual(batch_options(self.f)[0]["value"], "later_partial")

    def test_first_option_not_duplicated(self):
        # On garde dans opts les choix d’états historiques disponibles pour ce périmètre.
        opts = snapshot_options(self.f)
        # On vérifie que opts[0]['value'] correspond à '__LATEST__'.
        self.assertEqual(opts[0]["value"], "__LATEST__")
        # On vérifie que 'demo_20261022' ne figure pas dans {o['value'] for o in opts}.
        self.assertNotIn("demo_20261022", {o["value"] for o in opts})
        # On vérifie que sum(('Dernier scan' in o['label'] for o in opts)) correspond à 1.
        self.assertEqual(sum("Dernier scan" in o["label"] for o in opts), 1)
        # On vérifie que '__ACTIVE__' ne figure pas dans {o['value'] for o in opts}.
        self.assertNotIn("__ACTIVE__", {o["value"] for o in opts})
        # On vérifie que 'vignoble' ne figure pas dans opts[0]['label'].
        self.assertNotIn("vignoble", opts[0]["label"])
        # On vérifie que '22/10/2026 · 10h01–10h03 ⇒ Dernier scan' figure dans opts[0]['label'].
        self.assertIn("22/10/2026 · 10h01–10h03 ⇒ Dernier scan", opts[0]["label"])

    def test_active_mixed_state_explicit_not_fake_scan(self):
        # On utilise ce texte pour self.f['reconciliation_vineyard_current'].loc[0, 'pipeline_execu… ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        self.f["reconciliation_vineyard_current"].loc[0, "pipeline_execution_id"] = (
            "other"
        )
        # On garde dans opts les choix d’états historiques disponibles pour ce périmètre.
        opts = snapshot_options(self.f)
        # On vérifie que '__ACTIVE__' figure dans {o['value'] for o in opts}.
        self.assertIn("__ACTIVE__", {o["value"] for o in opts})
        # On garde dans p la représentation sérialisable préparée pour ces données.
        p = serialise(DashboardState("mock", "Fictif", self.f))
        # On répartit les valeurs renvoyées par select_snapshot entre (out, note) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        out, note = select_snapshot(p, "__LATEST__")
        # On attend que out['snapshot_latest'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(out["snapshot_latest"])
        # On vérifie que 'bilans actifs' figure dans note.
        self.assertIn("bilans actifs", note)

    def test_latest_real_frozen_data_and_no_technical_banner(self):
        # On répartit les valeurs renvoyées par select_snapshot entre (view, note) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        view, note = select_snapshot(self.p, "__LATEST__")
        # On vérifie que view['snapshot_run'] correspond à 'demo_20261022'.
        self.assertEqual(view["snapshot_run"], "demo_20261022")
        # On attend que view['snapshot_latest'] soit évalué comme vrai pour ce cas de test.
        self.assertTrue(view["snapshot_latest"])
        # On vérifie que note correspond à ''.
        self.assertEqual(note, "")
        # On vérifie que len(view['frames']['reconciliation_acquisition_current']) correspond à 7.
        self.assertEqual(len(view["frames"]["reconciliation_acquisition_current"]), 7)

    def test_latest_still_compares_excel_when_nas_reused(self):
        # On sélectionne dans self.f les éléments désignés par META ; meta recevra cette sélection.
        meta = self.f[META]
        # On utilise ce texte pour meta.loc[meta.pipeline_execution_id.eq('demo_20261022'), 'nas_pi… ;
        # il ne dépend pas d’une valeur récupérée ailleurs à cet endroit.
        meta.loc[
            meta.pipeline_execution_id.eq("demo_20261022"), "nas_pipeline_execution_id"
        ] = "demo_20261021"
        # On sélectionne dans self.f les éléments désignés par HIST['acquisition'] ; aq recevra cette
        # sélection.
        aq = self.f[HIST["acquisition"]]
        # On combine ces masques avec & pour construire mask ; les parenthèses gardent les comparaisons
        # regroupées.
        mask = aq.pipeline_execution_id.eq(
            "demo_20261022"
        ) & aq.acquisition_id_normalise.eq("DEMO_A_001")
        # On utilise ce texte pour aq.loc[mask, 'excel_comments'] ; il ne dépend pas d’une valeur
        # récupérée ailleurs à cet endroit.
        aq.loc[mask, "excel_comments"] = "Commentaire nouveau"
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(self.f)
        # On vérifie que r.counts()['comments'] correspond à 1.
        self.assertEqual(r.counts()["comments"], 1)
        # On vérifie que len(r.timeline) correspond à 4.
        self.assertEqual(len(r.timeline), 4)
        # On attend que r.timeline['Référence'].str.contains('demo_20261021|demo_20261022').all() soit
        # évalué comme vrai pour ce cas de test.
        self.assertTrue(
            r.timeline["Référence"].str.contains("demo_20261021|demo_20261022").all()
        )

    def test_default_request_latest_two_and_validation(self):
        # On garde dans req la demande de comparaison construite avec cette sélection.
        req = comparison_request(self.p, "__ALL__", "latest", [])
        # On vérifie que req['dates'] correspond à ['demo_20261022', 'demo_20261021'].
        self.assertEqual(req["dates"], ["demo_20261022", "demo_20261021"])
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle comparison_request avec self.p.
            comparison_request(self.p, "__ALL__", "selected", ["demo_20261022"])
        # On attend ValueError dans ce bloc ; si aucune erreur n’est levée, le test doit échouer.
        with self.assertRaises(ValueError):
            # On appelle comparison_request avec self.p.
            comparison_request(
                self.p, "__ALL__", "selected", ["invalid", "demo_20261022"]
            )

    def test_pending_selection_until_explicit_apply(self):
        # On garde dans req la demande de comparaison construite avec cette sélection.
        req = comparison_request(self.p, "__ALL__", "latest", [])
        # On répartit les valeurs renvoyées par selection_feedback entre (feedback, _) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        feedback, _ = selection_feedback(
            self.p, "__ALL__", "selected", ["demo_20261022", "demo_20261015"], req
        )
        # On vérifie que 'non appliquée' figure dans str(feedback).
        self.assertIn("non appliquée", str(feedback))
        # On garde dans applied la demande de comparaison construite avec cette sélection.
        applied = comparison_request(
            self.p, "__ALL__", "selected", ["demo_20261022", "demo_20261015"]
        )
        # On répartit les valeurs renvoyées par selection_feedback entre (feedback, _) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        feedback, _ = selection_feedback(
            self.p, "__ALL__", "selected", ["demo_20261015", "demo_20261022"], applied
        )
        # On vérifie que 'non appliquée' ne figure pas dans str(feedback).
        self.assertNotIn("non appliquée", str(feedback))

    def test_browser_store_is_tiny_not_historical_payload(self):
        # On garde dans ref le repère de l’état conservé par le stockage local du dashboard.
        ref = put_store(self.p)
        # On contrôle le résultat avec assertLess et les valeurs attendues indiquées juste dessous.
        self.assertLess(len(json.dumps(ref)), 1000)
        # On vérifie que 'frames' ne figure pas dans ref.
        self.assertNotIn("frames", ref)
        # On vérifie que resolve_store(ref)['frames'] correspond à self.p['frames'].
        self.assertEqual(resolve_store(ref)["frames"], self.p["frames"])
        # On remplace temporairement 'evolution_ui.compare_history' dans ce bloc de test ; le réglage
        # initial sera rétabli à sa sortie.
        with patch("evolution_ui.compare_history", wraps=compare_history) as compare:
            # On garde dans r1 le résultat de comparaison préparé pour l’état stocké du dashboard.
            r1 = comparison_for_store(ref, "__ALL__")
            # On garde dans r2 le résultat de comparaison préparé pour l’état stocké du dashboard.
            r2 = comparison_for_store(ref, "__ALL__")
            # On vérifie l’identité de r1 avec r2, et pas seulement une égalité de valeur.
            self.assertIs(r1, r2)
            # On vérifie que compare.call_count correspond à 1.
            self.assertEqual(compare.call_count, 1)
            # On appelle comparison_for_store avec ref.
            comparison_for_store(ref, "Domaine démo A")
            # On vérifie que compare.call_count correspond à 2.
            self.assertEqual(compare.call_count, 2)

    def test_reload_invalidates_cache(self):
        # On garde dans ref le repère de l’état conservé par le stockage local du dashboard.
        ref = put_store(self.p)
        # On garde dans r1 le résultat de comparaison préparé pour l’état stocké du dashboard.
        r1 = comparison_for_store(ref, "__ALL__")
        # On rend changed indépendant de self.p, y compris pour les listes et dictionnaires
        # imbriqués ; les modifications du scénario ne doivent pas contaminer l’état de départ.
        changed = copy.deepcopy(self.p)
        # On parcourt changed['frames'][HIST['acquisition']] ; row désigne l’élément courant de ce
        # scénario.
        for row in changed["frames"][HIST["acquisition"]]:
            # Cette branche traite le cas où l’identifiant du traitement NAS dans row correspond à le
            # texte 'demo_20261022' et l’identifiant normalisé de l’acquisition dans row correspond à
            # le texte 'DEMO_A_001'.
            if (
                row["pipeline_execution_id"] == "demo_20261022"
                # On exige aussi que l’identifiant normalisé de l’acquisition dans row correspond à le
                # texte 'DEMO_A_001'.
                and row["acquisition_id_normalise"] == "DEMO_A_001"
            ):
                # On utilise ce texte pour row['excel_comments'] ; il ne dépend pas d’une valeur
                # récupérée ailleurs à cet endroit.
                row["excel_comments"] = "Modification réelle"
        # On garde dans r2 le résultat de comparaison préparé pour l’état stocké du dashboard.
        r2 = comparison_for_store(put_store(changed), "__ALL__")
        # On vérifie que r1.counts()['comments'] correspond à 0.
        self.assertEqual(r1.counts()["comments"], 0)
        # On vérifie que r2.counts()['comments'] correspond à 1.
        self.assertEqual(r2.counts()["comments"], 1)

    def test_expired_state_no_fake_zeros(self):
        # On garde dans expired l’état du dashboard retrouvé à partir de son repère de stockage.
        expired = resolve_store({"_store_id": "invalid"})
        # On vérifie que expired['mode'] correspond à 'unavailable'.
        self.assertEqual(expired["mode"], "unavailable")
        # On vérifie que 'Actualiser' figure dans expired['status_message'].
        self.assertIn("Actualiser", expired["status_message"])
        # On garde dans content la représentation textuelle de render_content('overview', expired,
        # '__ALL__', '__ALL__', None).
        content = str(render_content("overview", expired, "__ALL__", "__ALL__", None))
        # On vérifie que 'metric-value' ne figure pas dans content.
        self.assertNotIn("metric-value", content)

    def test_no_date_pipeline_block_and_legend(self):
        # On garde dans page la représentation textuelle de render_content('overview', self.p,
        # '__ALL__', '__ALL__', None).
        page = str(render_content("overview", self.p, "__ALL__", "__ALL__", None))
        # On vérifie que 'Dates des données et fonctionnement du pipeline' ne figure pas dans page.
        self.assertNotIn("Dates des données et fonctionnement du pipeline", page)
        # On vérifie que 'Production selon Excel (catégorie' figure dans page.
        self.assertIn("Production selon Excel (catégorie", page)
        # On vérifie que 'Production selon Excel :' figure dans page.
        self.assertIn("Production selon Excel :", page)
        # On garde dans evo la représentation textuelle de render_content('evolution', self.p,
        # '__ALL__', '__ALL__', None).
        evo = str(render_content("evolution", self.p, "__ALL__", "__ALL__", None))
        # On vérifie que 'Comprendre les dates comparées' figure dans evo.
        self.assertIn("Comprendre les dates comparées", evo)
        # On vérifie que 'Comparer les scans sélectionnés' figure dans evo.
        self.assertIn("Comparer les scans sélectionnés", evo)

    def test_dates_only_state_no_computation_callback(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {"DASHBOARD_USE_MOCK": "1"}):
            # On garde dans app l’application Dash construite avec ses composants et callbacks.
            app = make_app()
        # On garde dans deps la valeur renvoyée par
        # app.server.test_client().get('/_dash-dependencies').get_json.
        deps = app.server.test_client().get("/_dash-dependencies").get_json()
        # On garde dans results le prochain élément de (d for d in deps if 'evolution-summary-results'
        # in d['output']).
        results = next(d for d in deps if "evolution-summary-results" in d["output"])
        # On vérifie que 'compare-dates' ne figure pas dans {i['id'] for i in results['inputs']}.
        self.assertNotIn("compare-dates", {i["id"] for i in results["inputs"]})
        # On vérifie que 'evolution-applied' figure dans {i['id'] for i in results['inputs']}.
        self.assertIn("evolution-applied", {i["id"] for i in results["inputs"]})
        # On garde dans apply le prochain élément de (d for d in deps if 'compare-validation' in
        # d['output']).
        apply = next(d for d in deps if "compare-validation" in d["output"])
        # On vérifie que [i['id'] for i in apply['inputs']] correspond à ['compare-apply'].
        self.assertEqual([i["id"] for i in apply["inputs"]], ["compare-apply"])

    def test_no_bridge_over_missing_selected_batch(self):
        # On sélectionne dans self.f les éléments désignés par META ; df recevra cette sélection.
        df = self.f[META]
        # On sélectionne dans df les éléments désignés par
        # ~(df.pipeline_execution_id.eq('demo_20261021') & df.vineyard_key.eq('demo_a')) ; self.f[META]
        # recevra cette sélection.
        self.f[META] = df[
            ~(
                df.pipeline_execution_id.eq("demo_20261021")
                & df.vineyard_key.eq("demo_a")
            )
        ]
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(
            self.f,
            # On fournit la sélection retenue via le paramètre selected de cet appel.
            selected=["demo_20261019", "demo_20261021", "demo_20261022"],
            latest=False,
        )
        # On vérifie que 'Domaine démo A' ne figure pas dans set(r.coverage.Vignoble).
        self.assertNotIn("Domaine démo A", set(r.coverage.Vignoble))
        # On contrôle le résultat avec assertLess et les valeurs attendues indiquées juste dessous.
        self.assertLess(r.comparable, r.expected)
        # On vérifie que 'état manquant' figure dans ' '.join(r.messages).
        self.assertIn("état manquant", " ".join(r.messages))


class V5Robustness(unittest.TestCase):
    def test_no_comparison_no_zero_cards(self):
        # On rend disponibles evolution_results depuis evolution_ui, pour les appels de ce fichier.
        from evolution_ui import evolution_results
        # On rend disponibles table_panel, section depuis dash_app, pour les appels de ce fichier.
        from dash_app import table_panel, section

        # On garde dans output la valeur renvoyée par evolution_results.
        output = evolution_results(
            {"frames": {}},
            "__ALL__",
            "latest",
            [],
            "Toutes",
            "Tous",
            "Acquisitions",
            table_panel,
            section,
        )
        # On vérifie que 'metric-value' ne figure pas dans str(output).
        self.assertNotIn("metric-value", str(output))
        # On vérifie que 'ne signifie pas zéro' figure dans str(output).
        self.assertIn("ne signifie pas zéro", str(output))

    def test_early_active_tests_not_exposed(self):
        # On garde dans f un état de démonstration construit avec des données synthétiques.
        f = build_mock_state()
        # On utilise ce texte pour f['reconciliation_vineyard_current']['nas_checked_at'] ; il ne
        # dépend pas d’une valeur récupérée ailleurs à cet endroit.
        f["reconciliation_vineyard_current"]["nas_checked_at"] = "2026-10-07T08:00:00Z"
        # On garde dans opts les choix d’états historiques disponibles pour ce périmètre.
        opts = snapshot_options(f)
        # On vérifie que '__ACTIVE__' ne figure pas dans {o['value'] for o in opts}.
        self.assertNotIn("__ACTIVE__", {o["value"] for o in opts})

    def test_empty_global_coverage_not_silent(self):
        # On garde dans f un état de démonstration construit avec des données synthétiques.
        f = build_mock_state()
        # On sélectionne dans f les éléments désignés par META ; meta recevra cette sélection.
        meta = f[META]
        # On sélectionne dans meta les éléments désignés par ~(meta.vineyard_key.eq('demo_b') &
        # meta.pipeline_execution_id.isin(['demo_20261021',… ; f[META] recevra cette sélection.
        f[META] = meta[
            ~(
                meta.vineyard_key.eq("demo_b")
                & meta.pipeline_execution_id.isin(["demo_20261021", "demo_20261022"])
            )
        ]
        # On garde dans r la comparaison des deux états historiques demandés.
        r = compare_history(f)
        # On contrôle le résultat avec assertLess et les valeurs attendues indiquées juste dessous.
        self.assertLess(r.comparable, r.expected)
        # On vérifie que 'Domaine démo B : aucun état' figure dans ' '.join(r.messages).
        self.assertIn("Domaine démo B : aucun état", " ".join(r.messages))

    def test_unexpected_computation_error_visible(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {"DASHBOARD_USE_MOCK": "1"}):
            # On garde dans app l’application Dash construite avec ses composants et callbacks.
            app = make_app()
        # On garde next((v['callback'] for k, v in app.callback_map.items() if
        # 'evolution-summary-results' in k)).__wrapped__ sous le nom callback ; cette affectation ne
        # copie pas à elle seule un objet mutable.
        callback = next(
            v["callback"]
            for k, v in app.callback_map.items()
            if "evolution-summary-results" in k
        ).__wrapped__
        # On remplace temporairement 'dash_app.evolution_results' dans ce bloc de test ; le réglage
        # initial sera rétabli à sa sortie.
        with (
            patch(
                "dash_app.evolution_results",
                # On définit le comportement simulé de l’appel, qui peut notamment lever une erreur ou
                # suivre une fonction de test.
                side_effect=RuntimeError("synthetic failure"),
            ),
            patch("dash_app.logging.exception"),
        ):
            # On garde dans output la valeur renvoyée par callback.
            output = callback(
                {"mode": "latest", "dates": ["a", "b"]},
                "Toutes",
                "Tous",
                "Acquisitions",
                {},
                "__ALL__",
            )
        # On vérifie que 'Comparaison interrompue' figure dans str(output).
        self.assertIn("Comparaison interrompue", str(output))
        # On vérifie que 'metric-value' ne figure pas dans str(output).
        self.assertNotIn("metric-value", str(output))

    def test_cache_expiry_and_capacity_are_bounded(self):
        # On importe state_store. Ce module sera utilisé par les opérations de ce fichier.
        import state_store

        # On regroupe dans p ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
        # leur position.
        p = {"mode": "mock", "frames": {}, "loaded_at": "test"}
        # On garde dans ref le repère de l’état conservé par le stockage local du dashboard.
        ref = put_store(p)
        # On remplace temporairement 'state_store.monotonic' dans ce bloc de test ; le réglage initial
        # sera rétabli à sa sortie.
        with patch("state_store.monotonic", return_value=10**20):
            # On attend que resolve_store(ref)['cache_expired'] soit évalué comme vrai pour ce cas de
            # test.
            self.assertTrue(resolve_store(ref)["cache_expired"])
        # On parcourt range(30) ; i désigne l’élément courant de ce scénario.
        for i in range(30):
            # On appelle put_store avec p.
            put_store(p)
        # On contrôle le résultat avec assertLessEqual et les valeurs attendues indiquées juste
        # dessous.
        self.assertLessEqual(len(state_store._STATES), state_store._MAX)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On confie la découverte et l’exécution des tests de ce fichier au lanceur unittest.
    unittest.main()
