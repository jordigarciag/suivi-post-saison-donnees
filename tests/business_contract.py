# Lecture du fichier — Données et outils de comparaison utilisés par les tests.
# On garde de petits exemples maîtrisés pour connaître les résultats attendus. Les tests qui les
# importent peuvent ainsi se concentrer sur une règle précise.
#

"""Small synthetic business signature, independent of UI wording/formatting."""

# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles build_mock_state depuis mock_fixture, pour les appels de ce fichier.
from mock_fixture import build_mock_state
# On rend disponibles prepare_acquisitions, prepare_passages, DashboardState, metric_frame depuis
# data_access, pour les appels de ce fichier.
from data_access import (
    prepare_acquisitions,
    prepare_passages,
    DashboardState,
    metric_frame,
)
# On rend disponibles enrich_acquisitions, focus_sections depuis business_rules, pour les appels de ce
# fichier.
from business_rules import enrich_acquisitions, focus_sections
# On rend disponibles compare_history, batch_options depuis history_engine, pour les appels de ce
# fichier.
from history_engine import compare_history, batch_options
# On rend disponibles serialise, select_snapshot, prepared, METRICS depuis dash_app, pour les appels de
# ce fichier.
from dash_app import serialise, select_snapshot, prepared, METRICS


def collect_contract():
    # On crée le dictionnaire vide out pour y ranger ensuite les éléments par clé.
    out = {}
    # On parcourt ['base', 'unknown', 'folder_absent', 'raw_error', 'processing_error', 'al… ; case
    # désigne l’élément courant de ce scénario.
    for case in [
        "base",
        "unknown",
        "folder_absent",
        "raw_error",
        "processing_error",
        "all_outputs",
        "unknown_scope",
        "zero_eligible",
    ]:
        # On garde dans f un état de démonstration construit avec des données synthétiques.
        f = build_mock_state()
        # On garde dans aq les acquisitions complétées avec les champs calculés de présentation.
        aq = enrich_acquisitions(
            prepare_acquisitions(f["reconciliation_acquisition_current"])
        )
        # On garde dans ps les passages préparés pour leur lecture dans le dashboard.
        ps = prepare_passages(f["reconciliation_passage_current"])
        # On vérifie ce cas avant la suite : case correspond au texte 'unknown'.
        if case == "unknown":
            # On parcourt ['passage_created', 'vitimap_created', 'stocks_json_exists', 'has_non_hea… ;
            # col désigne l’élément courant de ce scénario.
            for col in [
                "passage_created",
                "vitimap_created",
                "stocks_json_exists",
                "has_non_healthy_status",
            ]:
                # On initialise ps[col] à None : aucune valeur n’a encore été retenue ici.
                ps[col] = None
        # On vérifie ce cas avant la suite : case correspond au texte 'folder_absent'.
        if case == "folder_absent":
            # On initialise ps['passage_created'] à False ; les branches suivantes pourront modifier
            # cet état.
            ps["passage_created"] = False
        # On vérifie ce cas avant la suite : case correspond au texte 'raw_error'.
        if case == "raw_error":
            # On utilise ce texte pour aq['raw_error'] ; il ne dépend pas d’une valeur récupérée
            # ailleurs à cet endroit.
            aq["raw_error"] = "Permission refusée"
        # On vérifie ce cas avant la suite : case correspond au texte 'processing_error'.
        if case == "processing_error":
            # On utilise ce texte pour aq['processing_error'] ; il ne dépend pas d’une valeur récupérée
            # ailleurs à cet endroit.
            aq["processing_error"] = "Permission refusée"
        # On vérifie ce cas avant la suite : case correspond au texte 'all_outputs'.
        if case == "all_outputs":
            # On parcourt ['passage_created', 'vitimap_created', 'stocks_json_exists', 'has_non_hea… ;
            # col désigne l’élément courant de ce scénario.
            for col in [
                "passage_created",
                "vitimap_created",
                "stocks_json_exists",
                "has_non_healthy_status",
            ]:
                # On initialise ps[col] à True ; les branches suivantes pourront modifier cet état.
                ps[col] = True
        # On vérifie ce cas avant la suite : case correspond au texte 'unknown_scope'.
        if case == "unknown_scope":
            # On initialise ps['eligible_acquisitions_count'] à None : aucune valeur n’a encore été
            # retenue ici.
            ps["eligible_acquisitions_count"] = None
            # On initialise ps['passage_business_category'] à None : aucune valeur n’a encore été
            # retenue ici.
            ps["passage_business_category"] = None
            # On garde dans aq la portion de aq.iloc sélectionnée par 0:0 ; les bornes de fin sont
            # exclues.
            aq = aq.iloc[0:0]
        # On vérifie ce cas avant la suite : case correspond au texte 'zero_eligible'.
        if case == "zero_eligible":
            # On fixe ps['eligible_acquisitions_count'] à 0 pour cette étape du scénario de test.
            ps["eligible_acquisitions_count"] = 0
        # On répartit les valeurs renvoyées par focus_sections entre (sections, unknown) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        sections, unknown = focus_sections(aq, ps)

        def ids(rows, grain):
            # On choisit la valeur de keys selon ce test : grain correspond au texte 'acq'. Les deux
            # résultats possibles restent définis explicitement ici.
            keys = (
                ["acquisition_id_normalise"]
                if grain == "acq"
                else ["vineyard_name", "parcel_name", "passage_name"]
            )
            # On fournit à l’appelant les éléments triés de ('|'.join((str(r.get(k, '')) for k in
            # keys)) for r in rows.to_dict('recor… dans une nouvelle liste.
            return sorted(
                "|".join(str(r.get(k, "")) for k in keys)
                for r in rows.to_dict("records")
            )

        # On indexe out[case] par k ; chaque clé sera associée à {'eligible': v['eligible'], 'missing':
        # ids(v['missing'], v['grain']), 'unk…. Une même clé ne peut garder qu’une valeur.
        out[case] = {
            k: {
                # On associe la clé 'eligible' à cette valeur dans les données de ce scénario.
                "eligible": v["eligible"],
                # On associe la clé 'missing' à cette valeur dans les données de ce scénario.
                "missing": ids(v["missing"], v["grain"]),
                # On associe la clé 'unknown' à cette valeur dans les données de ce scénario.
                "unknown": ids(v["unknown"], v["grain"]),
            }
            for k, v in sections.items()
        }
        # On garde dans out[case]['unknown_scope'] la valeur renvoyée par ids.
        out[case]["unknown_scope"] = ids(unknown, "passage")
    # On garde dans f un état de démonstration construit avec des données synthétiques.
    f = build_mock_state()
    # On garde dans p la représentation sérialisable préparée pour ces données.
    p = serialise(DashboardState("mock", "Fictif", f))
    # On crée le dictionnaire vide out['historical_metrics'] pour y ranger ensuite les éléments par
    # clé.
    out["historical_metrics"] = {}
    # On parcourt batch_options(f) ; o désigne l’élément courant de ce scénario.
    for o in batch_options(f):
        # On répartit les valeurs renvoyées par select_snapshot entre (view, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        view, _ = select_snapshot(p, o["value"])
        # On répartit les valeurs renvoyées par prepared entre (aq, ps, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        aq, ps, _ = prepared(view, "__ALL__", "__ALL__", "")
        # On indexe out['historical_metrics'][o['value']] par k ; chaque clé sera associée à
        # len(metric_frame(k, aq, ps)). Une même clé ne peut garder qu’une valeur.
        out["historical_metrics"][o["value"]] = {
            k: len(metric_frame(k, aq, ps)) for k in METRICS
        }
    # On garde dans result la comparaison des deux états historiques demandés.
    result = compare_history(
        # On fournit la sélection retenue via le paramètre selected de cet appel.
        f, selected=[o["value"] for o in batch_options(f)], latest=False
    )
    # On garde dans out['comparison_counts'] la valeur renvoyée par result.counts.
    out["comparison_counts"] = result.counts()
    # On garde dans out['comparison_details'] le contenu de result.details[['Vignoble', 'Type',
    # 'Acquisition', 'Parcelle', '… sous forme de dictionnaires, selon l’orientation indiquée.
    out["comparison_details"] = result.details[
        [
            "Vignoble",
            "Type",
            "Acquisition",
            "Parcelle",
            "Passage",
            "Famille",
            "Information",
            "Avant",
            "Après",
        ]
    ].to_dict("records")
    # On remet out à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return out
