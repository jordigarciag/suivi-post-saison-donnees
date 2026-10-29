# Lecture du fichier — Construction du dashboard : composants, tableaux et réactions aux actions de navigation.
# On sépare les valeurs affichées des fonctions qui les calculent. Les callbacks relient une action
# de l’utilisateur aux composants à mettre à jour.
#

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe datetime sous le nom dt. Ce module sera utilisé par les opérations de ce fichier.
import datetime as dt
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe html sous le nom html_escape. Ce module sera utilisé par les opérations de ce fichier.
import html as html_escape
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Any depuis typing, pour les appels de ce fichier.
from typing import Any

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd
# On importe plotly.graph_objects sous le nom go. On décrit les traces et la présentation des
# graphiques.
import plotly.graph_objects as go
# On rend disponibles ALL, MATCH, Dash, Input, Output, State, ctx, dash_table, dcc, html depuis dash,
# pour les appels de ce fichier.
from dash import ALL, MATCH, Dash, Input, Output, State, ctx, dash_table, dcc, html
# On rend disponibles PreventUpdate depuis dash.exceptions, pour les appels de ce fichier.
from dash.exceptions import PreventUpdate

# On rend disponibles load_dotenv depuis dotenv, pour les appels de ce fichier.
from dotenv import load_dotenv
# On rend disponibles locate_project_root depuis database, pour les appels de ce fichier.
from database import locate_project_root

# On appelle load_dotenv avec locate_project_root() / '.env'.
load_dotenv(
    locate_project_root() / ".env",
    override=False,
    interpolate=False,
    # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être décodé
    # selon un réglage implicite du poste.
    encoding="utf-8-sig",
)

# On rend disponibles METRICS, TZ, DashboardState, filter_frames, focus_passages, format_time,
# freshness_rows, list_vineyards, passage_linked, load_dashboard_state, metric_frame,
# prepare_acquisitions, prepare_passages, unique_acquisitions, yes, boolean depuis data_access, pour
# les appels de ce fichier.
from data_access import (
    METRICS,
    TZ,
    DashboardState,
    filter_frames,
    focus_passages,
    format_time,
    freshness_rows,
    list_vineyards,
    passage_linked,
    load_dashboard_state,
    metric_frame,
    prepare_acquisitions,
    prepare_passages,
    unique_acquisitions,
    yes,
    boolean,
)
# On rend disponibles enrich_acquisitions, focus_sections, search_catalog, related, text depuis
# business_rules, pour les appels de ce fichier.
from business_rules import (
    enrich_acquisitions,
    focus_sections,
    search_catalog,
    related,
    text,
)
# On rend disponibles compare_history, batch_options, historical_frames, HIST, META depuis
# history_engine, pour les appels de ce fichier.
from history_engine import compare_history, batch_options, historical_frames, HIST, META
# On rend disponibles evolution_page, evolution_results, overview_evolution, comparison_request,
# selection_feedback depuis evolution_ui, pour les appels de ce fichier.
from evolution_ui import (
    evolution_page,
    evolution_results,
    overview_evolution,
    comparison_request,
    selection_feedback,
)
# On rend disponibles snapshot_options, active_matches_latest depuis history_engine, pour les appels de
# ce fichier.
from history_engine import snapshot_options, active_matches_latest
# On rend disponibles put_store, resolve_store, cached depuis state_store, pour les appels de ce
# fichier.
from state_store import put_store, resolve_store, cached
# On importe logging. Ce module sera utilisé par les opérations de ce fichier.
import logging
# On rend disponibles NAS_COLUMN, NAS_PLAIN, nas_markdown, table_columns, plain_column_value,
# plain_csv, plain_clipboard depuis presentation, pour les appels de ce fichier.
from presentation import (
    NAS_COLUMN,
    NAS_PLAIN,
    nas_markdown,
    table_columns,
    plain_column_value,
    plain_csv,
    plain_clipboard,
)

# On fixe TITLE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
TITLE = "Suivi post-saison 2026"
# On rassemble dans ACQ_COLUMNS les 11 éléments explicitement indiqués, en conservant leur structure.
ACQ_COLUMNS = [
    "vineyard_name",
    "acquisition_id_normalise",
    "perimeter_normalized",
    "excel_perimeter_display",
    "excel_status_display",
    "excel_comment_display",
    "classification_explanation",
    "excel_acquisition_date",
    "parcel_name",
    "passage_name",
    "treated_technical",
]
# On rassemble dans REVIEW_COLUMNS les 9 éléments explicitement indiqués, en conservant leur structure.
REVIEW_COLUMNS = [
    "vineyard_name",
    "acquisition_id_normalise",
    "perimeter_normalized",
    "review_origin",
    "review_reason",
    "excel_status_display",
    "excel_comment_display",
    "nas_observations_display",
    "review_source_fields",
]
# On rassemble dans PASSAGE_COLUMNS les 10 éléments explicitement indiqués, en conservant leur
# structure.
PASSAGE_COLUMNS = [
    "vineyard_name",
    "parcel_name",
    "passage_name",
    "passage_created",
    "vitimap_created",
    "stocks_json_exists",
    "vitiparcel_technical_criterion_satisfied",
    "has_non_healthy_status",
    "eligible_acquisitions_count",
    "passage_next_action",
]
# On regroupe dans LABELS ces champs nommés ; on pourra les retrouver par leur clé plutôt que par leur
# position.
LABELS = {
    # On renseigne le nom du domaine sous la clé 'vineyard_name'.
    "vineyard_name": "Vignoble",
    # On renseigne l’identifiant normalisé de l’acquisition sous la clé 'acquisition_id_normalise'.
    "acquisition_id_normalise": "Acquisition",
    # On associe la clé 'perimeter_normalized' à cette valeur dans cet objet.
    "perimeter_normalized": "Catégorie · Excel",
    # On associe la clé 'excel_acquisition_date' à cette valeur dans cet objet.
    "excel_acquisition_date": "Date d’acquisition · Excel",
    # On associe la clé 'parcel_name' à cette valeur dans cet objet.
    "parcel_name": "Parcelle",
    # On associe la clé 'passage_name' à cette valeur dans cet objet.
    "passage_name": "Rattachée au passage",
    # On associe la clé 'treated_technical' à cette valeur dans cet objet.
    "treated_technical": "Processing + WEBP",
    # On associe la clé 'treated_production' à cette valeur dans cet objet.
    "treated_production": "Production traitée",
    # On renseigne la nécessité d’une vérification sous la clé 'needs_verification'.
    "needs_verification": "Point à examiner",
    # On associe la clé 'vitimap_created' à cette valeur dans cet objet.
    "vitimap_created": "Vitimap · GeoJSON présent",
    # On associe la clé 'stocks_json_exists' à cette valeur dans cet objet.
    "stocks_json_exists": "JSON de stocks présent",
    # On associe la clé 'vitiparcel_technical_criterion_satisfied' à cette valeur dans cet objet.
    "vitiparcel_technical_criterion_satisfied": "Critère Vitiparcel satisfait",
    # On associe la clé 'has_non_healthy_status' à cette valeur dans cet objet.
    "has_non_healthy_status": "Statut non sain détecté",
    # On associe la clé 'eligible_acquisitions_count' à cette valeur dans cet objet.
    "eligible_acquisitions_count": "Acquisitions éligibles",
    # On associe la clé 'acquisitions_controlled_count' à cette valeur dans cet objet.
    "acquisitions_controlled_count": "Acquisitions contrôlées",
    # On associe la clé 'acquisition_count' à cette valeur dans cet objet.
    "acquisition_count": "Acquisitions liées",
    # On associe la clé 'has_technical_error' à cette valeur dans cet objet.
    "has_technical_error": "Erreur technique enregistrée",
    # On associe la clé 'excel_needs_review' à cette valeur dans cet objet.
    "excel_needs_review": "Examen du suivi Excel demandé par le pipeline",
    # On renseigne le statut du suivi Excel sous la clé 'excel_pipeline_status'.
    "excel_pipeline_status": "Statut déclaré · Excel",
    # On associe la clé 'excel_comments' à cette valeur dans cet objet.
    "excel_comments": "Commentaires · Excel",
    # On renseigne le statut Excel présenté sous la clé 'excel_status_display'.
    "excel_status_display": "Statut dans le suivi Excel",
    # On renseigne le commentaire Excel présenté sous la clé 'excel_comment_display'.
    "excel_comment_display": "Commentaires du suivi Excel",
    # On renseigne le motif d’exclusion Excel présenté sous la clé 'excel_exclusion_display'.
    "excel_exclusion_display": "Motif d’exclusion · Excel",
    # On renseigne le périmètre Excel présenté sous la clé 'excel_perimeter_display'.
    "excel_perimeter_display": "Périmètre d’origine · Excel",
    # On associe la clé 'classification_explanation' à cette valeur dans cet objet.
    "classification_explanation": "Origine de la catégorie",
    # On renseigne le motif de décision présenté sous la clé 'decision_reason_display'.
    "decision_reason_display": "Motif de décision enregistré",
    # On renseigne la note de classement présentée sous la clé 'classification_note_display'.
    "classification_note_display": "Note de classement enregistrée",
    # On associe la clé 'decision_source' à cette valeur dans cet objet.
    "decision_source": "Source de la décision",
    # On associe la clé 'review_origin' à cette valeur dans cet objet.
    "review_origin": "Origine du point à examiner",
    # On associe la clé 'review_reason' à cette valeur dans cet objet.
    "review_reason": "Pourquoi cette acquisition apparaît",
    # On associe la clé 'review_source_fields' à cette valeur dans cet objet.
    "review_source_fields": "Drapeaux enregistrés utilisés",
    # On associe la clé 'nas_observations_display' à cette valeur dans cet objet.
    "nas_observations_display": "Constats enregistrés sur le NAS",
    # On renseigne la catégorie métier du traitement sous la clé 'processing_business_category'.
    "processing_business_category": "Interprétation du traitement",
    # On renseigne la prochaine action indiquée pour le traitement sous la clé
    # 'processing_next_action'.
    "processing_next_action": "Action suggérée · traitement",
    # On associe la clé 'passage_next_action' à cette valeur dans cet objet.
    "passage_next_action": "Action suggérée · passage",
    # On associe la clé 'passage_created' à cette valeur dans cet objet.
    "passage_created": "Dossier de passage présent",
    # On associe la clé 'nas_checked_at' à cette valeur dans cet objet.
    "nas_checked_at": "Vérification du NAS",
    # On renseigne la date du rapprochement sous la clé 'reconciled_at'.
    "reconciled_at": "Croisement Excel / NAS",
    # On renseigne la date du contrôle sous la clé 'checked_at'.
    "checked_at": "Contrôle enregistré",
    # On associe la clé 'focus_reason' à cette valeur dans cet objet.
    "focus_reason": "Critère appliqué à cette liste",
    # On associe la clé 'production_link_confirmed' à cette valeur dans cet objet.
    "production_link_confirmed": "Lien à la production confirmé",
    # On associe la clé 'treatment_unknown' à cette valeur dans cet objet.
    "treatment_unknown": "Traitement non concluant",
    # On associe la clé 'treated_outside_production' à cette valeur dans cet objet.
    "treated_outside_production": "Traité hors production",
    # On associe la clé 'production_incomplete' à cette valeur dans cet objet.
    "production_incomplete": "Traitement à compléter",
    # On associe la clé 'entity_key' à cette valeur dans cet objet.
    "entity_key": "Clé de recherche",
    # On associe la clé 'excel_source_files' à cette valeur dans cet objet.
    "excel_source_files": "Fichier Excel source",
    # On associe la clé 'excel_source_sheets' à cette valeur dans cet objet.
    "excel_source_sheets": "Feuille Excel source",
    # On associe la clé 'excel_source_row_numbers' à cette valeur dans cet objet.
    "excel_source_row_numbers": "Lignes Excel sources",
}
# On garde dans METRICS un nouveau dictionnaire construit avec les valeurs indiquées (la copie reste
# superficielle).
METRICS = dict(METRICS)
# On rassemble dans METRICS['review'] les 3 éléments explicitement indiqués, en conservant leur
# structure.
METRICS["review"] = (
    "Points à examiner",
    "Indicateurs de contrôle enregistrés par le pipeline : suivi Excel, contrôle NAS ou décision de traitement. Chaque ligne précise son origine, son motif et les champs utilisés. Un test déclaré seul n’est pas une anomalie.",
    "acq",
)
# On fixe BLUE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
BLUE = "#245DC4"
# On fixe ORANGE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
ORANGE = "#BA500A"


# On prépare un libellé lisible à partir des valeurs prévues dans ce module.
def label(key):
    # On fournit à l’appelant le champ key de LABELS avec le repli indiqué si la clé est absente.
    return LABELS.get(
        key,
        key if " " in key or key[:1].isupper() else key.replace("_", " ").capitalize(),
    )


# On prépare des valeurs compatibles avec la présentation et la sérialisation attendues ici.
def clean(value):
    # On réserve cette branche à value lorsqu’il est de type (dict, list, tuple).
    if isinstance(value, (dict, list, tuple)):
        # On prépare une représentation JSON des données ; ce format permettra des relire sans
        # dépendre des objets Python en mémoire.
        return json.dumps(value, ensure_ascii=False, default=str)
    # On réserve cette branche à value lorsqu’il est de type (pd.Timestamp, dt.datetime, dt.date).
    if isinstance(value, (pd.Timestamp, dt.datetime, dt.date)):
        # On fournit à l’appelant la représentation ISO de value.
        return value.isoformat()
    # On tente ce bloc et on traite séparément les erreurs prévues : (TypeError, ValueError).
    try:
        # On reconnaît aussi les valeurs manquantes propres à pandas, comme NaN ; elles ne doivent pas
        # s’afficher comme le texte "nan".
        if pd.isna(value):
            # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
            return None
    except (TypeError, ValueError):
        # Si pandas ne sait pas traiter cette valeur comme un scalaire, on laisse la conversion
        # textuelle située après le bloc prendre le relais.
        pass
    # On remet la valeur reçue à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return value


# On transforme les lignes du tableau en enregistrements utilisables par les composants.
def records(df):
    # On remet [{key: clean(value) for key, value in row.items()} for row in df.to_dict(… à l’appelant
    # ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return [
        {key: clean(value) for key, value in row.items()}
        for row in df.to_dict("records")
    ]


# On prépare une représentation transportable des données pour les échanges de ce module.
def serialise(state):
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'mode' à cette valeur dans cet objet.
        "mode": state.mode,
        # On associe la clé 'status_message' à cette valeur dans cet objet.
        "status_message": state.status_message,
        # On associe la clé 'loaded_at' à cette valeur dans cet objet.
        "loaded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        # On associe la clé 'frames' à cette valeur dans cet objet.
        "frames": {key: records(df) for key, df in state.frames.items()},
    }


# On retrouve un tableau à partir de la représentation reçue.
def frame(payload, name):
    # On garde dans payload l’état du dashboard retrouvé à partir de son repère de stockage.
    payload = resolve_store(payload)
    # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
    return pd.DataFrame(payload.get("frames", {}).get(name, []))


# On prépare les cellules affichées, sans modifier les valeurs métier d’origine.
def display_records(df):
    # On garde dans out une copie de df pour travailler sur cet objet séparément.
    out = df.copy()
    # On parcourt out ; col désigne l’élément courant à chaque passage dans la boucle.
    for col in out:
        # Cette branche traite le cas où col se termine par le texte '_at'.
        if col.endswith("_at"):
            # On garde dans out[col] les valeurs de out[col] transformées par la fonction ou la
            # correspondance indiquée.
            out[col] = out[col].map(format_time)
        else:
            # On garde dans out[col] les valeurs de out[col] transformées par la fonction ou la
            # correspondance indiquée.
            out[col] = out[col].map(
                lambda v: "Oui"
                if v is True
                else "Non"
                if v is False
                else (
                    "Non renseigné" if clean(v) is None or clean(v) == "" else clean(v)
                )
            )
    # On vérifie ce cas avant la suite : NAS_COLUMN appartient à out.
    if NAS_COLUMN in out:
        # On sélectionne dans out les éléments désignés par NAS_COLUMN ; out[NAS_PLAIN] recevra cette
        # sélection.
        out[NAS_PLAIN] = out[NAS_COLUMN]
        # On garde dans out[NAS_COLUMN] les valeurs de out[NAS_COLUMN] transformées par la fonction ou
        # la correspondance indiquée.
        out[NAS_COLUMN] = out[NAS_COLUMN].map(nas_markdown)
    # On fournit à l’appelant la valeur renvoyée par records.
    return records(out)


# On assemble le tableau et les commandes qui lui sont associées.
def table_panel(df, key, title, columns=None, intro=None):
    # On construit visible comme une liste à partir de c, pour chaque c de columns or list(df.columns)
    # en ne gardant que les éléments qui passent le filtre.
    visible = [
        c for c in (columns or list(df.columns)) if c in df and c != "entity_key"
    ]
    # On construit all_cols comme une liste à partir de c, pour chaque c de df.columns en ne gardant
    # que les éléments qui passent le filtre.
    all_cols = [
        c for c in df.columns if c not in {"entity_key", "kind", "payload", NAS_PLAIN}
    ]
    # On prévoit le cas où visible est évalué comme faux, par exemple une valeur vide selon son type.
    if not visible:
        # On garde dans visible la portion de all_cols sélectionnée par :8 ; les bornes de fin sont
        # exclues.
        visible = all_cols[:8]
    # On rassemble dans body les 1 éléments explicitement indiqués, en conservant leur structure.
    body = [html.H3(title)]
    # Cette branche traite le cas où intro est évalué comme vrai.
    if intro:
        # On ajoute html.P(intro, className='muted') à la fin de body ; les éléments précédents restent
        # conservés.
        body.append(html.P(intro, className="muted"))
    # On traite à part le tableau df lorsqu’il est vide.
    if df.empty:
        # On ajoute html.P('Aucune ligne pour ce périmètre ou ce critère.', className='empty-state') à
        # la fin de body ; les éléments précédents restent conservés.
        body.append(
            html.P(
                # On rattache ce composant aux règles CSS de cette classe.
                "Aucune ligne pour ce périmètre ou ce critère.", className="empty-state"
            )
        )
    # On garde dans has_nas le résultat de cette comparaison : NAS_COLUMN appartient à df.columns.
    has_nas = NAS_COLUMN in df.columns
    # On ajoute [html.Label('Colonnes à afficher', htmlFor=json.dumps({'role': 'columns', 'key': key… à
    # body et on conserve ce nouvel état pour la suite.
    body += [
        html.Label(
            "Colonnes à afficher", htmlFor=json.dumps({"role": "columns", "key": key})
        ),
        dcc.Dropdown(
            # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
            # sélecteurs.
            id={"role": "columns", "key": key},
            # On fournit les choix que ce contrôle doit proposer à l’utilisateur.
            options=[{"label": label(c), "value": c} for c in all_cols],
            # On fixe la valeur initiale ou courante de cette propriété.
            value=visible,
            # On précise si ce sélecteur accepte plusieurs choix simultanés.
            multi=True,
        ),
        html.P(
            "50 lignes par page · trier ou filtrer dans le tableau · cliquer sur le sélecteur d’une colonne pour la copier.",
            # On rattache ce composant aux règles CSS de cette classe.
            className="table-help",
        ),
        html.Div(
            [
                html.Button(
                    "Exporter en CSV",
                    # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                    # sélecteurs.
                    id={"role": "plain-export", "key": key},
                    n_clicks=0,
                    # On rattache ce composant aux règles CSS de cette classe.
                    className="secondary-button export",
                ),
                dcc.Download(id={"role": "plain-download", "key": key}),
            ]
        )
        if has_nas
        else html.Div(),
        dash_table.DataTable(
            # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
            # sélecteurs.
            id={"role": "table", "key": key},
            # On fournit les données de ce composant ou de ce tableau dans le format attendu.
            data=display_records(df),
            # On décrit les colonnes à présenter, distinctes des lignes de données.
            columns=table_columns(visible, label),
            markdown_options={"html": False},
            column_selectable="single",
            selected_columns=visible[:1],
            row_selectable="single",
            # On fixe le nombre de lignes affichées par page, pas le nombre total d’enregistrements.
            page_size=50,
            page_action="native",
            # On configure le filtrage du tableau affiché ; il ne s’agit pas d’un nouveau scan NAS.
            filter_action="native",
            # On indique comment le tableau affiché peut être trié.
            sort_action="native",
            sort_mode="multi",
            export_format="none" if has_nas else "csv",
            export_headers="display",
            export_columns="visible",
            filter_options={"placeholder_text": "Filtrer…"},
            tooltip_header={c: {"value": c, "type": "text"} for c in visible},
            tooltip_duration=None,
            css=[{"selector": ".dash-spreadsheet-menu", "rule": "padding:8px 0;"}],
            style_table={"overflowX": "auto", "maxWidth": "100%"},
            style_cell={
                # On associe la clé 'textAlign' à cette valeur dans cet objet.
                "textAlign": "left",
                # On associe la clé 'whiteSpace' à cette valeur dans cet objet.
                "whiteSpace": "normal",
                # On associe la clé 'height' à cette valeur dans cet objet.
                "height": "auto",
                # On associe la clé 'minWidth' à cette valeur dans cet objet.
                "minWidth": "135px",
                # On associe la clé 'maxWidth' à cette valeur dans cet objet.
                "maxWidth": "300px",
                # On associe la clé 'padding' à cette valeur dans cet objet.
                "padding": "12px",
                # On associe la clé 'verticalAlign' à cette valeur dans cet objet.
                "verticalAlign": "top",
                # On associe la clé 'fontFamily' à cette valeur dans cet objet.
                "fontFamily": "Arial, sans-serif",
                # On associe la clé 'fontSize' à cette valeur dans cet objet.
                "fontSize": "14px",
            },
            style_cell_conditional=[
                {
                    # On associe la clé 'if' à cette valeur dans cet objet.
                    "if": {"column_id": NAS_COLUMN},
                    # On associe la clé 'minWidth' à cette valeur dans cet objet.
                    "minWidth": "320px",
                    # On associe la clé 'width' à cette valeur dans cet objet.
                    "width": "360px",
                    # On associe la clé 'maxWidth' à cette valeur dans cet objet.
                    "maxWidth": "420px",
                    # On associe la clé 'lineHeight' à cette valeur dans cet objet.
                    "lineHeight": "1.6",
                }
            ],
            style_header={
                # On associe la clé 'fontWeight' à cette valeur dans cet objet.
                "fontWeight": "600",
                # On associe la clé 'backgroundColor' à cette valeur dans cet objet.
                "backgroundColor": "#f0f5f2",
                # On associe la clé 'color' à cette valeur dans cet objet.
                "color": "#183d2b",
            },
            style_filter={"backgroundColor": "#fafbf9"},
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#fafbf9"}
            ],
        ),
        html.Div(
            # On rattache ce composant aux règles CSS de cette classe.
            className="copy-bar",
            # On fournit le contenu enfant de ce composant d’interface.
            children=[
                dcc.Clipboard(
                    # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                    # sélecteurs.
                    id={"role": "clipboard", "key": key},
                    content="",
                    title="Copier toute la colonne filtrée, toutes pages confondues",
                    # On applique ces styles à ce composant, sans changer les données métier.
                    style={"fontSize": "23px"},
                ),
                html.Span(id={"role": "copy-label", "key": key}),
            ],
        ),
        html.Details(
            [
                html.Summary("Consulter la ligne sélectionnée et ses liens"),
                html.Div(id={"role": "row-detail", "key": key}, className="row-detail"),
            ]
        ),
    ]
    # On fournit à l’appelant le composant html.Section avec le contenu et les propriétés indiqués.
    return html.Section(body, className="panel")


# On prépare le composant graphique à partir du résultat déjà calculé.
def chart(summary, specs, title, explanation=None, graph_id=None):
    # On garde dans fig le graphique ou la trace go.Figure défini avec les données indiquées.
    fig = go.Figure()
    # On parcourt specs ; (field, name, color) désigne l’élément courant à chaque passage dans la
    # boucle.
    for field, name, color in specs:
        # On garde dans hover_name le résultat du remplacement demandé sur html_escape.escape(name).
        hover_name = html_escape.escape(name).replace(" (", "<br>(")
        # On appelle fig.add_trace avec go.Bar(x=summary.get('Vignoble', []), y=summary.get(field, []),
        # name=name, marker_color=c….
        fig.add_trace(
            go.Bar(
                x=summary.get("Vignoble", []),
                y=summary.get(field, []),
                # On fournit le nom en cours via le paramètre name de cet appel.
                name=name,
                marker_color=color,
                opacity=1,
                hoverlabel={
                    # On associe la clé 'bgcolor' à cette valeur dans cet objet.
                    "bgcolor": "#FFFFFF",
                    # On associe la clé 'bordercolor' à cette valeur dans cet objet.
                    "bordercolor": "#172B24",
                    # On associe la clé 'font' à cette valeur dans cet objet.
                    "font": {"color": "#172B24", "size": 14},
                },
                hovertemplate="<b>%{x}</b><br>"
                + hover_name
                + "<br><b>Quantité : %{y:,.0f}</b><extra></extra>",
            )
        )
    # On garde dans max_value la plus grande valeur parmi (max(summary[f].fillna(0), default=0) for f,
    # _, _ in specs if f in summar….
    max_value = max(
        (max(summary[f].fillna(0), default=0) for f, _, _ in specs if f in summary),
        default=0,
    )
    # On appelle fig.update_layout sans argument positionnel.
    fig.update_layout(
        template="plotly_white",
        barmode="group",
        title=None,
        showlegend=False,
        margin={"l": 40, "r": 16, "t": 12, "b": 24},
        font={"family": "Arial, sans-serif", "size": 14, "color": "#24382e"},
        xaxis={"title": None, "automargin": True},
        yaxis={
            # On associe la clé 'title' à cette valeur dans cet objet.
            "title": None,
            # On associe la clé 'rangemode' à cette valeur dans cet objet.
            "rangemode": "tozero",
            # On associe la clé 'dtick' à cette valeur dans cet objet.
            "dtick": 1 if max_value < 6 else None,
        },
        hoverlabel={
            # On associe la clé 'bgcolor' à cette valeur dans cet objet.
            "bgcolor": "#FFFFFF",
            # On associe la clé 'bordercolor' à cette valeur dans cet objet.
            "bordercolor": "#172B24",
            # On associe la clé 'font' à cette valeur dans cet objet.
            "font": {"color": "#172B24", "size": 14},
        },
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        height=320,
    )
    # On garde dans legend le composant html.Div avec le contenu et les propriétés indiqués.
    legend = html.Div(
        [
            html.Div(
                [
                    html.Span(className="legend-key", style={"backgroundColor": color}),
                    html.Span(name),
                ]
            )
            for _, name, color in specs
        ],
        # On rattache ce composant aux règles CSS de cette classe.
        className="chart-legend",
    )
    # On rassemble dans body les 1 éléments explicitement indiqués, en conservant leur structure.
    body = [html.H3(title)]
    # Cette branche traite le cas où explanation est évalué comme vrai.
    if explanation:
        # On ajoute html.Div(explanation, className='chart-explanation') à la fin de body ; les
        # éléments précédents restent conservés.
        body.append(html.Div(explanation, className="chart-explanation"))
    # On ajoute [legend, dcc.Graph(**{'id': graph_id} if graph_id else {}, figure=fig, config={'disp… à
    # body et on conserve ce nouvel état pour la suite.
    body += [
        legend,
        dcc.Graph(
            **({"id": graph_id} if graph_id else {}),
            # On fournit le graphique via le paramètre figure de cet appel.
            figure=fig,
            # On fournit les réglages via le paramètre config de cet appel.
            config={"displayModeBar": False, "locale": "fr"},
            responsive=True,
        ),
    ]
    # On fournit à l’appelant le composant html.Section avec le contenu et les propriétés indiqués.
    return html.Section(body, className="panel chart-panel")


# On prépare les lignes de synthèse utilisées dans cette vue.
def summary_frame(aq, ps):
    # On garde dans vineyards les éléments triés de set(aq.get('vineyard_name', [])) |
    # set(ps.get('vineyard_name', [])) dans une nouvelle liste.
    vineyards = sorted(
        set(aq.get("vineyard_name", [])) | set(ps.get("vineyard_name", []))
    )
    # On prépare rows comme liste vide ; on la remplira au fil des opérations suivantes.
    rows = []
    # On parcourt les domaines sélectionnés ; v désigne l’élément courant à chaque passage dans la
    # boucle.
    for v in vineyards:
        # On choisit la valeur de a selon ce test : la condition aq.empty n’est pas remplie. Les deux
        # résultats possibles restent définis explicitement ici.
        a = aq[aq["vineyard_name"].eq(v)] if not aq.empty else aq
        # On choisit la valeur de p selon ce test : la condition ps.empty n’est pas remplie. Les deux
        # résultats possibles restent définis explicitement ici.
        p = ps[ps["vineyard_name"].eq(v)] if not ps.empty else ps
        # On ajoute {'Vignoble': v, 'Production · Excel': len(metric_frame('production', a, p)),
        # 'Production… à la fin de rows ; les éléments précédents restent conservés.
        rows.append(
            {
                # On associe la clé 'Vignoble' à cette valeur dans cet objet.
                "Vignoble": v,
                "Production · Excel": len(metric_frame("production", a, p)),
                "Production traitée": len(metric_frame("treated", a, p)),
                "Tests · Excel": len(metric_frame("test", a, p)),
                "Bloqué · Excel": len(metric_frame("blocked", a, p)),
                # On associe la clé 'Traitements hors production' à cette valeur dans cet objet.
                "Traitements hors production": len(metric_frame("outside", a, p)),
                # On associe la clé 'Vitimap' à cette valeur dans cet objet.
                "Vitimap": len(metric_frame("map", a, p)),
                "Vitiparcel · critère": len(metric_frame("parcel", a, p)),
            }
        )
    # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
    return pd.DataFrame(rows)


# On prépare les tableaux et les indicateurs nécessaires à cet affichage.
def prepared(store, vineyard, perimeter, search):
    # On garde dans aq les acquisitions complétées avec les champs calculés de présentation.
    aq = enrich_acquisitions(
        unique_acquisitions(
            prepare_acquisitions(frame(store, "reconciliation_acquisition_current"))
        )
    )
    # On garde dans ps les passages préparés pour leur lecture dans le dashboard.
    ps = prepare_passages(frame(store, "reconciliation_passage_current"))
    # On garde dans fr la valeur renvoyée par frame.
    fr = frame(store, "reconciliation_freshness_current")
    # On fournit à l’appelant les tableaux filtrés selon les choix demandés.
    return filter_frames(aq, ps, fr, vineyard, perimeter, search)


# On regroupe un titre et un contenu dans un bloc de présentation.
def panel(title, text):
    # On fournit à l’appelant le composant html.Section avec le contenu et les propriétés indiqués.
    return html.Section([html.H3(title), html.P(text)], className="panel")


# On rassemble les composants d’une même partie de la page.
def section(title, children, key=None):
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return (
        html.Details(
            [html.Summary(title), html.Div(children, className="disclosure-body")],
            # On rattache ce composant aux règles CSS de cette classe.
            className="disclosure",
            # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
            # sélecteurs.
            id=key,
        )
        if key
        else html.Details(
            [html.Summary(title), html.Div(children, className="disclosure-body")],
            # On rattache ce composant aux règles CSS de cette classe.
            className="disclosure",
        )
    )


# On présente la date et la provenance des observations plutôt qu’une promesse de mise à jour en
# direct.
def freshness_section(store, fr):
    # On fournit à l’appelant la valeur renvoyée par section pour 'Dates des données et fonctionnement
    # du pipelin….
    return section(
        "Dates des données et fonctionnement du pipeline",
        [
            html.P(
                "Le pipeline croise, pour chaque vignoble, les informations des fichiers Excel de suivi des acquisitions avec ce qui a été trouvé sur le NAS : dossiers d’acquisition, images traitées, passages et fichiers livrables. Ce croisement permet de dresser l’état des lieux des traitements et des livrables."
            ),
            html.P(
                f"« Vérification du NAS » correspond à la date de vérification des dossiers et fichiers sur le NAS. « Croisement Excel / NAS » correspond à la date du croisement avec les informations des fichiers de suivi. Les heures sont affichées dans le fuseau {TZ}. Le bouton « Actualiser les données » recharge les résultats enregistrés, sans relancer le pipeline."
            ),
            table_panel(freshness_rows(fr), "freshness", "Dates par vignoble"),
            html.P("Écran actualisé le " + format_time(store.get("loaded_at"))),
        ],
    )


# On prépare les compteurs d’un critère pour le graphique correspondant.
def criterion_chart(entry, key):
    # On récupère entry['missing'] et on le garde dans population pour la suite.
    population = entry["missing"]
    # Zero means no candidate in the current eligible scope, not missing evidence.
    if population.empty:
        # On fournit à l’appelant le panneau de présentation construit à partir de ces éléments.
        return panel(
            "Répartition par vignoble",
            "Aucun élément répondant à ce critère dans le périmètre examiné. Les observations non concluantes, s’il y en a, sont séparées ci-dessous.",
        )
    # On garde dans data les données de
    # population.groupby('vineyard_name').size().reset_index(name='Qua… avec les noms modifiés selon la
    # correspondance.
    data = (
        population.groupby("vineyard_name")
        .size()
        # On fournit le nom en cours via le paramètre name de cet appel.
        .reset_index(name="Quantité")
        # On décrit les colonnes à présenter, distinctes des lignes de données.
        .rename(columns={"vineyard_name": "Vignoble"})
    )
    # On choisit la valeur de unit selon ce test : entry['grain'] correspond au texte 'acq'. Les deux
    # résultats possibles restent définis explicitement ici.
    unit = (
        "Acquisitions concernées" if entry["grain"] == "acq" else "Passages concernés"
    )
    # On fournit à l’appelant la valeur renvoyée par chart.
    return chart(
        data,
        [("Quantité", unit, ORANGE)],
        "Répartition par vignoble",
        html.P("Cliquer sur une barre pour filtrer uniquement le tableau ci-dessous."),
        graph_id={"role": "focus-chart", "key": key},
    )


# On construit la vue des points à vérifier à partir du périmètre sélectionné.
def render_focus(aq, ps):
    # On répartit les valeurs renvoyées par focus_sections entre (entries, unknown_scope) ; leur ordre
    # doit correspondre à celui prévu par cet appel.
    entries, unknown_scope = focus_sections(aq, ps)
    # On prépare disclosures comme liste vide ; on la remplira au fil des opérations suivantes.
    disclosures = []
    # Only the visual order changes; the ten criterion masks stay unchanged.
    order = [
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
    # On parcourt order ; key désigne l’élément courant à chaque passage dans la boucle.
    for key in order:
        # On sélectionne dans entries les éléments désignés par key ; item recevra cette sélection.
        item = entries[key]
        # On choisit la valeur de unit selon ce test : item['grain'] correspond au texte 'acq'. Les
        # deux résultats possibles restent définis explicitement ici.
        unit = "acquisition" if item["grain"] == "acq" else "passage"
        # On distribue ces valeurs entre n, unknown, dans l’ordre de l’affectation. Chaque nom reçoit
        # son propre élément.
        n, unknown = len(item["missing"]), len(item["unknown"])
        # On prépare heading avec cette expression pour l’utiliser dans la suite du traitement.
        heading = f"{item['title']} — {n} {unit}{'s' if n != 1 else ''}"
        # Cette branche traite le cas où unknown est évalué comme vrai.
        if unknown:
            # On ajoute f' · {unknown} non concluant' + ('s' if unknown != 1 else '') à heading et on
            # conserve ce nouvel état pour la suite.
            heading += f" · {unknown} non concluant" + ("s" if unknown != 1 else "")
        # On choisit la valeur de columns selon ce test : item['grain'] correspond au texte 'acq'.
        # Les deux résultats possibles restent définis explicitement ici.
        columns = (
            ACQ_COLUMNS
            + ["nas_observations_display", "processing_next_action", "focus_reason"]
            if item["grain"] == "acq"
            else PASSAGE_COLUMNS + ["focus_reason"]
        )
        # On rassemble dans body les 5 éléments explicitement indiqués, en conservant leur structure.
        body = [
            html.P(item["rule"], className="criterion-rule"),
            html.P(
                f"Périmètre examiné : {item['eligible']} {unit}{'s' if item['eligible'] != 1 else ''} de production ou liés à la production. Les tests et les acquisitions en attente ne sont pas comptés comme du travail restant.",
                # On rattache ce composant aux règles CSS de cette classe.
                className="muted",
            ),
            criterion_chart(item, key),
            html.Button(
                "Afficher tous les vignobles du périmètre",
                # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                # sélecteurs.
                id={"role": "focus-clear", "key": key},
                n_clicks=0,
                disabled=item["missing"].empty,
                # On rattache ce composant aux règles CSS de cette classe.
                className="secondary-button",
            ),
            html.Div(
                table_panel(
                    item["missing"],
                    "focus-" + key,
                    "Éléments concernés",
                    columns,
                    "Tous les vignobles du périmètre sélectionné en haut de page. Le graphique et les autres critères restent indépendants.",
                ),
                # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                # sélecteurs.
                id={"role": "focus-local", "key": key},
            ),
        ]
        # Cette branche traite le cas où unknown est évalué comme vrai.
        if unknown:
            # On ajoute section(f'Observations non concluantes · {unknown}', [html.P('Information non
            # renseignée… à la fin de body ; les éléments précédents restent conservés.
            body.append(
                section(
                    f"Observations non concluantes · {unknown}",
                    [
                        html.P(
                            "Information non renseignée ou erreur de contrôle : ces lignes ne sont pas comptées comme absences confirmées."
                        ),
                        table_panel(
                            item["unknown"],
                            "focus-unknown-" + key,
                            "Lignes sans conclusion suffisante",
                            ACQ_COLUMNS if item["grain"] == "acq" else PASSAGE_COLUMNS,
                        ),
                    ],
                )
            )
        # On ajoute section(heading, body, key='criterion-' + key) à la fin de disclosures ; les
        # éléments précédents restent conservés.
        disclosures.append(section(heading, body, key="criterion-" + key))
    # On fournit à l’appelant le composant html.Div avec le contenu et les propriétés indiqués.
    return html.Div(
        [
            panel(
                "Ce qui resterait à faire",
                "Les nombres ci-dessous indiquent les acquisitions ou passages dont un critère n’est pas satisfait selon les données enregistrées. Ce sont des pistes de travail à confirmer, pas des retards certains. Un même élément peut apparaître dans plusieurs critères : les nombres ne doivent pas être additionnés.",
            ),
            *disclosures,
            html.Section(
                [
                    html.H2("Données à clarifier"),
                    html.P(
                        "Ces contrôles concernent la qualification des données, pas des fichiers ou des livrables déclarés manquants.",
                        # On rattache ce composant aux règles CSS de cette classe.
                        className="muted",
                    ),
                    section(
                        f"Passages dont le lien à la production reste à vérifier — {len(unknown_scope)} passage"
                        + ("s" if len(unknown_scope) != 1 else ""),
                        [
                            html.P(
                                "Ces passages ne sont pas comptés comme du travail restant, car leur rattachement à la production n’est pas suffisamment documenté.",
                                # On rattache ce composant aux règles CSS de cette classe.
                                className="criterion-rule",
                            ),
                            table_panel(
                                unknown_scope,
                                "unknown-scope",
                                "Lien à la production à vérifier",
                                PASSAGE_COLUMNS,
                            ),
                        ],
                        # On fournit la clé de l’élément via le paramètre key de cet appel.
                        key="production-scope-clarification",
                    ),
                ],
                # On rattache ce composant aux règles CSS de cette classe.
                className="data-clarification",
                # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                # sélecteurs.
                id="data-clarification",
            ),
        ]
    )


# On choisit le contenu de l’onglet à partir des filtres et des tableaux préparés.
def render_content(active_tab, store, vineyard, perimeter, selected_metric):
    # On garde dans store l’état du dashboard retrouvé à partir de son repère de stockage.
    store = resolve_store(store)
    # On vérifie ce cas avant la suite : active_tab correspond au texte 'evolution'.
    if active_tab == "evolution":
        # On fournit à l’appelant la valeur renvoyée par evolution_page.
        return evolution_page(store, vineyard, table_panel, section)
    # On vérifie ce cas avant la suite : store.get('mode') correspond au texte 'unavailable'.
    if store.get("mode") == "unavailable":
        # On fournit à l’appelant le panneau de présentation construit à partir de ces éléments.
        return panel(
            "Données non disponibles",
            store.get("status_message", "")
            + " Vérifier la disponibilité de PostgreSQL et les identifiants du fichier .env, puis cliquer sur « Actualiser les données ». Aucune donnée fictive ne remplace les données indisponibles.",
        )
    # On vérifie ce cas avant la suite : active_tab correspond au texte 'search'.
    if active_tab == "search":
        # On fournit à l’appelant le composant html.Section avec le contenu et les propriétés indiqués.
        return html.Section(
            [
                html.H2("Rechercher"),
                html.P(
                    "Retrouver une acquisition, une parcelle ou un passage dans l’état sélectionné enregistré dans PostgreSQL. Cette recherche est indépendante des filtres de la vue d’ensemble et ne consulte pas directement le NAS."
                ),
                html.Div(
                    # On rattache ce composant aux règles CSS de cette classe.
                    className="search-controls",
                    # On fournit le contenu enfant de ce composant d’interface.
                    children=[
                        html.Div(
                            [
                                html.Label(
                                    "Identifiant, nom ou mots-clés",
                                    htmlFor="search-query",
                                ),
                                dcc.Input(
                                    # On donne au composant son identifiant, utilisé ensuite pour les
                                    # callbacks et les sélecteurs.
                                    id="search-query",
                                    type="search",
                                    debounce=True,
                                    placeholder="Ex. identifiant d’acquisition, parcelle ou passage…",
                                    # On rattache ce composant aux règles CSS de cette classe.
                                    className="search-input",
                                    persistence=True,
                                    persistence_type="session",
                                ),
                            ]
                        ),
                        html.Div(
                            [
                                html.Label("Type d’élément", htmlFor="search-kind"),
                                dcc.Dropdown(
                                    # On donne au composant son identifiant, utilisé ensuite pour les
                                    # callbacks et les sélecteurs.
                                    id="search-kind",
                                    # On fournit les choix que ce contrôle doit proposer à
                                    # l’utilisateur.
                                    options=[
                                        {"label": n, "value": v}
                                        for n, v in [
                                            ("Tous", "all"),
                                            ("Acquisitions", "acquisition"),
                                            ("Parcelles", "parcel"),
                                            ("Passages", "passage"),
                                        ]
                                    ],
                                    # On fixe la valeur initiale ou courante de cette propriété.
                                    value="all",
                                    clearable=False,
                                ),
                            ]
                        ),
                        html.Div(
                            [
                                html.Label(
                                    "Vignoble de la recherche",
                                    htmlFor="search-vineyard",
                                ),
                                dcc.Dropdown(
                                    # On donne au composant son identifiant, utilisé ensuite pour les
                                    # callbacks et les sélecteurs.
                                    id="search-vineyard",
                                    # On fournit les choix que ce contrôle doit proposer à
                                    # l’utilisateur.
                                    options=vineyard_options(store),
                                    # On fixe la valeur initiale ou courante de cette propriété.
                                    value="__ALL__",
                                    clearable=False,
                                ),
                            ]
                        ),
                    ],
                ),
                dcc.Loading(
                    html.Div(id="search-results"),
                    type="circle",
                    target_components={"search-results": "children"},
                ),
            ],
            # On rattache ce composant aux règles CSS de cette classe.
            className="search-page",
        )
    # Cette branche traite le cas où store.get('mode') correspond au texte 'database' et la condition
    # store.get('snapshot_run') n’est pas remplie et frame(store, 'reconciliation_vineyard_current')
    # est un tableau vide.
    if (
        store.get("mode") == "database"
        # On exige aussi que la condition store.get('snapshot_run') n’est pas remplie.
        and not store.get("snapshot_run")
        and frame(store, "reconciliation_vineyard_current").empty
    ):
        # On fournit à l’appelant le panneau de présentation construit à partir de ces éléments.
        return panel(
            "Aucun bilan actif disponible",
            "La connexion fonctionne, mais aucun bilan métier actif n’est disponible pour dresser un état des lieux. Aucun indicateur à zéro n’est fabriqué.",
        )
    # Cette branche traite le cas où le champ 'snapshot_run' de store est évalué comme vrai et le
    # domaine concerné ne figure pas dans {None, '__ALL__'}.
    if store.get("snapshot_run") and vineyard not in {None, "__ALL__"}:
        # On garde dans covered la valeur renvoyée par frame.
        covered = frame(store, "reconciliation_vineyard_current")
        # Cette branche traite le cas où covered est un tableau vide ou le domaine concerné ne figure
        # pas dans set(covered.get('vineyard_name', [])).
        if covered.empty or vineyard not in set(covered.get("vineyard_name", [])):
            # On fournit à l’appelant le panneau de présentation construit à partir de ces éléments.
            return panel(
                "Vignoble non couvert par cette exécution",
                "Aucun bilan historique pour ce vignoble dans l’exécution sélectionnée. Aucun indicateur à zéro ni aucune donnée actuelle ne remplace cet état manquant. Choisir une autre exécution ou revenir à État courant.",
            )
    # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
    try:
        # On répartit les valeurs renvoyées par prepared entre (aq, ps, fr) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        aq, ps, fr = prepared(store, vineyard, perimeter, "")
    except ValueError as exc:
        # On fournit à l’appelant le panneau de présentation construit à partir de ces éléments.
        return panel("Comptage suspendu", str(exc))
    # On vérifie ce cas avant la suite : active_tab correspond au texte 'focus'.
    if active_tab == "focus":
        # On fournit à l’appelant la valeur renvoyée par render_focus.
        return render_focus(aq, ps)
    # On garde dans summary la valeur renvoyée par summary_frame.
    summary = summary_frame(aq, ps)
    # On garde dans graphs le composant html.Div avec le contenu et les propriétés indiqués.
    graphs = html.Div(
        # On rattache ce composant aux règles CSS de cette classe.
        className="charts-grid overview-charts",
        # On fournit le contenu enfant de ce composant d’interface.
        children=[
            chart(
                summary,
                [
                    (
                        "Production · Excel",
                        "Production selon Excel (catégorie déduite des informations du suivi Excel)",
                        BLUE,
                    ),
                    (
                        "Production traitée",
                        "Production traitée (Processing + WEBP trouvés sur le NAS)",
                        ORANGE,
                    ),
                ],
                "Production et traitement démontré",
                [
                    html.P(
                        [
                            html.Strong("Production selon Excel : "),
                            "acquisitions classées en production à partir des informations présentes dans les fichiers Excel de suivi des acquisitions, sans que cela implique qu’elles soient déjà traitées.",
                        ]
                    ),
                    html.P(
                        [
                            html.Strong("Production traitée : "),
                            "acquisitions classées en production dans le suivi Excel, pour lesquelles un dossier Processing et des images WEBP ont été trouvés sur le NAS.",
                        ]
                    ),
                ],
            ),
            chart(
                summary,
                [
                    ("Vitimap", "Vitimap (GeoJSON présent dans le passage)", BLUE),
                    (
                        "Vitiparcel · critère",
                        "Vitiparcel (JSON de stocks présent + au moins un statut non sain)",
                        ORANGE,
                    ),
                ],
                "Livrables observés · passages",
                [
                    html.P(
                        "Un passage est compté une seule fois, quel que soit le nombre d’acquisitions rattachées."
                    ),
                    html.P(
                        "Pour Vitimap comme pour Vitiparcel, ces critères attestent les constats techniques enregistrés. Ils ne confirment ni la qualité du livrable, ni sa validation, ni sa livraison au client."
                    ),
                ],
            ),
        ],
    )
    # On prépare cards comme liste vide ; on la remplira au fil des opérations suivantes.
    cards = []
    # On parcourt les couples (key, (name, rule, grain)) de METRICS : on garde ensemble la clé et sa
    # valeur au lieu des traiter dans deux listes séparées.
    for key, (name, rule, grain) in METRICS.items():
        # On ajoute html.Button(id={'role': 'metric', 'key': key}, n_clicks=0, title=rule,
        # className='metric-… à la fin de cards ; les éléments précédents restent conservés.
        cards.append(
            html.Button(
                # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                # sélecteurs.
                id={"role": "metric", "key": key},
                n_clicks=0,
                title=rule,
                # On rattache ce composant aux règles CSS de cette classe.
                className="metric-card"
                + (" selected" if selected_metric == key else ""),
                # On fournit le contenu enfant de ce composant d’interface.
                children=[
                    html.Span(name, className="metric-label"),
                    html.Strong(
                        # On rattache ce composant aux règles CSS de cette classe.
                        str(len(metric_frame(key, aq, ps))), className="metric-value"
                    ),
                    html.Span(
                        (
                            "Tous statuts confondus"
                            if perimeter in {None, "__ALL__"}
                            else "Catégorie sélectionnée : " + perimeter
                        )
                        if key == "all"
                        else "Passages uniques"
                        if grain == "passage"
                        else "Acquisitions uniques",
                        # On rattache ce composant aux règles CSS de cette classe.
                        className="metric-subtitle",
                    ),
                    html.Span("Voir la liste →", className="metric-link"),
                ],
            )
        )
    # On garde dans details le composant html.Div avec le contenu et les propriétés indiqués.
    details = html.Div()
    # On vérifie ce cas avant la suite : selected_metric appartient à METRICS.
    if selected_metric in METRICS:
        # On sélectionne dans METRICS les éléments désignés par selected_metric ; (name, rule, grain)
        # recevra cette sélection.
        name, rule, grain = METRICS[selected_metric]
        # On garde dans chosen la valeur renvoyée par metric_frame.
        chosen = metric_frame(selected_metric, aq, ps)
        # On choisit la valeur de cols selon ce test : grain correspond au texte 'passage'. Les deux
        # résultats possibles restent définis explicitement ici.
        cols = (
            PASSAGE_COLUMNS
            if grain == "passage"
            else REVIEW_COLUMNS
            if selected_metric == "review"
            else ACQ_COLUMNS
            + [
                "excel_exclusion_display",
                "decision_reason_display",
                "decision_source",
                "classification_note_display",
            ]
        )
        # On rassemble dans children les 1 éléments explicitement indiqués, en conservant leur
        # structure.
        children = [
            table_panel(chosen, "metric-detail", "Détail — " + name, cols, rule)
        ]
        # Cette branche traite le cas où grain correspond au texte 'passage' et la condition
        # chosen.empty n’est pas remplie et la condition aq.empty n’est pas remplie.
        if grain == "passage" and not chosen.empty and not aq.empty:
            # On garde dans mask le résultat de la fonction appliquée aux éléments ou à l’axe indiqué
            # de aq.
            mask = aq.apply(
                lambda a: any(
                    passage_linked(p, a.to_frame().T) for _, p in chosen.iterrows()
                ),
                # On indique l’axe de l’opération : sa valeur distingue le travail sur les lignes ou
                # sur les colonnes.
                axis=1,
            )
            # On ajoute section('Acquisitions rattachées à ces passages', [table_panel(aq[mask],
            # 'metric-linked',… à la fin de children ; les éléments précédents restent conservés.
            children.append(
                section(
                    "Acquisitions rattachées à ces passages",
                    [
                        table_panel(
                            aq[mask], "metric-linked", "Liens enregistrés", ACQ_COLUMNS
                        )
                    ],
                )
            )
        # On garde dans details le composant html.Div avec le contenu et les propriétés indiqués.
        details = html.Div(children, id="metric-detail-section")
    # On choisit la valeur de trend selon ce test : la condition store.get('snapshot_run') n’est pas
    # remplie ou le champ 'snapshot_latest' de store est évalué comme vrai. Les deux résultats
    # possibles restent définis explicitement ici.
    trend = (
        overview_evolution(store, vineyard)
        if not store.get("snapshot_run") or store.get("snapshot_latest")
        else panel(
            "État historique",
            "Les données affichées correspondent à l’exécution sélectionnée. L’onglet Évolution permet de comparer ses dates aux autres observations conservées.",
        )
    )
    # On fournit à l’appelant le composant html.Div avec le contenu et les propriétés indiqués.
    return html.Div(
        [
            graphs,
            trend,
            html.P(
                "Production, Test et Bloqué / en attente sont des catégories déduites des informations des fichiers Excel de suivi des acquisitions, pas des tags NAS. Les filtres ci-dessus s’appliquent à cet état des lieux ; les passages filtrés sont limités aux liens identifiés.",
                # On rattache ce composant aux règles CSS de cette classe.
                className="scope-note",
            ),
            html.P(
                "Cliquer sur un indicateur pour consulter sa liste et le critère appliqué.",
                # On rattache ce composant aux règles CSS de cette classe.
                className="muted",
            ),
            html.Div(cards, className="metrics-grid"),
            details,
            section(
                "Synthèse par vignoble",
                [table_panel(summary, "summary", "Chiffres par vignoble")],
                # On fournit la clé de l’élément via le paramètre key de cet appel.
                key="vineyard-summary",
            ),
            section(
                "Définitions des indicateurs",
                [
                    html.Dl(
                        [
                            html.Div([html.Dt(name), html.Dd(rule)])
                            for name, rule, _ in METRICS.values()
                        ]
                    )
                ],
            ),
        ]
    )


# On prépare les choix du filtre de domaine à partir des données disponibles.
def vineyard_options(store):
    # On garde dans store l’état du dashboard retrouvé à partir de son repère de stockage.
    store = resolve_store(store)
    # On garde dans names la valeur renvoyée par list_vineyards.
    names = list_vineyards(
        {k: pd.DataFrame(v) for k, v in store.get("frames", {}).items()}
    )
    # On remet [{'label': 'Tous les vignobles', 'value': '__ALL__'}] + [{'label': v, 'va… à l’appelant
    # ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return [{"label": "Tous les vignobles", "value": "__ALL__"}] + [
        {"label": v, "value": v} for v in names
    ]


# On prépare les résultats de recherche dans les données déjà chargées.
def search_results(store, query, kind, vineyard):
    # Cette branche traite le cas où la condition (query or '').strip() n’est pas remplie.
    if not (query or "").strip():
        # On fournit à l’appelant le composant html.P avec le contenu et les propriétés indiqués.
        return html.P(
            "Saisir un identifiant ou des mots-clés. Valider avec Entrée ou quitter le champ pour lancer la recherche.",
            # On rattache ce composant aux règles CSS de cette classe.
            className="empty-state",
        )
    # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
    try:
        # On répartit les valeurs renvoyées par prepared entre (aq, ps, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        aq, ps, _ = prepared(store, "__ALL__", "__ALL__", "")
        # On garde dans found les éléments du catalogue correspondant à la recherche.
        found = search_catalog(aq, ps, query, kind or "all", vineyard or "__ALL__")
    except ValueError as exc:
        # On fournit à l’appelant le panneau de présentation construit à partir de ces éléments.
        return panel("Recherche suspendue", str(exc))
    # On traite à part le tableau found lorsqu’il est vide.
    if found.empty:
        # On fournit à l’appelant le composant html.P avec le contenu et les propriétés indiqués.
        return html.P(
            "Aucun résultat dans les données de l’état sélectionné pour cette recherche. Cela ne prouve pas que l’élément est absent du NAS.",
            # On rattache ce composant aux règles CSS de cette classe.
            className="empty-state",
        )
    # On prépare groups comme liste vide ; on la remplira au fil des opérations suivantes.
    groups = []
    # On parcourt [('acquisition', 'Acquisitions'), ('parcel', 'Parcelles'), ('passage', 'P… ; (type_,
    # title) désigne l’élément courant à chaque passage dans la boucle.
    for type_, title in [
        ("acquisition", "Acquisitions"),
        ("parcel", "Parcelles"),
        ("passage", "Passages"),
    ]:
        # On sélectionne dans found les éléments désignés par found['kind'].eq(type_) ; rows recevra
        # cette sélection.
        rows = found[found["kind"].eq(type_)]
        # On vérifie ce cas avant la suite : kind ne figure pas dans {'all', None, type_}.
        if kind not in {"all", None, type_}:
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On ajoute section(f'{title} · {len(rows)} résultat' + ('s' if len(rows) != 1 else ''),
        # [table_panel… à la fin de groups ; les éléments précédents restent conservés.
        groups.append(
            section(
                f"{title} · {len(rows)} résultat" + ("s" if len(rows) != 1 else ""),
                [
                    table_panel(
                        rows,
                        "search-" + type_,
                        title,
                        ["Vignoble", "Parcelle", "Identifiant ou nom"],
                        "Sélectionner le rond à gauche d’une ligne, puis ouvrir « Consulter la ligne sélectionnée et ses liens ».",
                    )
                ],
            )
        )
    # On fournit à l’appelant le composant html.Div avec le contenu et les propriétés indiqués.
    return html.Div(
        [
            html.P(
                f"{len(found)} résultat"
                + ("s" if len(found) != 1 else "")
                + " dans l’état sélectionné."
            ),
            *groups,
        ]
    )


# On rassemble les informations liées à l’élément choisi pour son détail.
def dossier(entity_key, store):
    # On répartit les valeurs renvoyées par prepared entre (aq, ps, _) ; leur ordre doit correspondre à
    # celui prévu par cet appel.
    aq, ps, _ = prepared(store, "__ALL__", "__ALL__", "")
    # On répartit les valeurs renvoyées par related entre (linked_aq, linked_ps) ; leur ordre doit
    # correspondre à celui prévu par cet appel.
    linked_aq, linked_ps = related(entity_key, aq, ps)
    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    kind, vineyard, parcel, name = json.loads(entity_key)
    # On garde dans suffix la portion de hashlib.sha1(entity_key.encode()).hexdigest() sélectionnée par
    # :12 ; les bornes de fin sont exclues.
    suffix = hashlib.sha1(entity_key.encode()).hexdigest()[:12]
    # On fournit à l’appelant le composant html.Div avec le contenu et les propriétés indiqués.
    return html.Div(
        [
            html.H3(name),
            html.P(vineyard + (" · " + parcel if parcel else "")),
            html.P(
                "Les liens ci-dessous sont ceux enregistrés dans les données. Un rattachement à un passage ne confirme ni la présence de son dossier ni la création de ses livrables."
            ),
            table_panel(
                linked_aq,
                "dossier-acq-" + suffix,
                "Acquisitions et informations du suivi Excel",
                ACQ_COLUMNS
                + [
                    "excel_exclusion_display",
                    "decision_reason_display",
                    "decision_source",
                    "classification_note_display",
                    "review_origin",
                    "review_reason",
                    "nas_observations_display",
                ],
            ),
            table_panel(
                linked_ps,
                "dossier-passage-" + suffix,
                "Passages et livrables associés",
                PASSAGE_COLUMNS,
            ),
        ]
    )


# On applique le filtre propre à cette liste sans le confondre avec les filtres globaux.
def filter_focus_population(df, selected):
    # Cette branche traite le cas où la sélection retenue vaut None ou df est un tableau vide.
    if selected is None or df.empty:
        # On fournit à l’appelant une copie de df pour travailler sur cet objet séparément.
        return df.copy()
    # On fournit à l’appelant une copie de df[df['vineyard_name'].eq(selected)] pour travailler sur cet
    # objet séparément.
    return df[df["vineyard_name"].eq(selected)].copy()


# On sélectionne l’état enregistré demandé pour cette consultation.
def select_snapshot(payload, run):
    # On garde dans payload l’état du dashboard retrouvé à partir de son repère de stockage.
    payload = resolve_store(payload)
    # On indexe frames par k ; chaque clé sera associée à pd.DataFrame(v). Une même clé ne peut garder
    # qu’une valeur.
    frames = {k: pd.DataFrame(v) for k, v in payload.get("frames", {}).items()}
    # On garde dans options les options de sélection des lots disponibles.
    options = batch_options(frames)
    # On vérifie ce cas avant la suite : run appartient à {'__ACTIVE__', '__CURRENT__'}.
    if run in {"__ACTIVE__", "__CURRENT__"}:
        # Cette branche traite le cas où le champ 'cache_expired' du contenu détaillé est évalué
        # comme vrai.
        if payload.get("cache_expired"):
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return payload, payload["status_message"]
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return (
            payload,
            "Bilans actifs : cet état diffère du dernier scan conservé. Les dates et la couverture peuvent varier selon les vignobles.",
        )
    # On garde dans latest le résultat de cette comparaison : run appartient à {None, '__LATEST__'}.
    latest = run in {None, "__LATEST__"}
    # Cette branche traite le cas où latest est évalué comme vrai et les options proposées est évalué
    # comme vrai.
    if latest and options:
        # On récupère la valeur reçue dans options[0] et on le garde dans run pour la suite.
        run = options[0]["value"]
    # Cette branche traite le cas où les options proposées est évalué comme vrai et run correspond à la
    # valeur reçue dans options[0].
    elif options and run == options[0]["value"]:
        # On initialise latest à True ; les branches suivantes pourront modifier cet état.
        latest = True
    # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
    try:
        # On répartit les valeurs renvoyées par historical_frames entre (frozen, names) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        frozen, names = historical_frames(frames, run)
        # Retain shared history references in memory; only current rows change.
        data = dict(payload.get("frames", {}))
        # On parcourt ['reconciliation_acquisition_current', 'reconciliation_passage_current',… ; name
        # désigne l’élément courant à chaque passage dans la boucle.
        for name in [
            "reconciliation_acquisition_current",
            "reconciliation_passage_current",
            "reconciliation_vineyard_current",
            "reconciliation_freshness_current",
        ]:
            # On garde dans data[name] la valeur renvoyée par records.
            data[name] = records(frozen[name])
        # On garde dans out un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        out = dict(payload, frames=data, snapshot_run=run, snapshot_latest=latest)
        # On garde dans missing les éléments triés de set(list_vineyards(frames)) - set(names) dans une
        # nouvelle liste.
        missing = sorted(set(list_vineyards(frames)) - set(names))
        # On choisit la valeur de message selon ce test : latest est évalué comme vrai. Les deux
        # résultats possibles restent définis explicitement ici.
        message = (
            ""
            if latest
            else "État historique — données enregistrées lors de l’exécution sélectionnée."
        )
        # Cette branche traite le cas où missing est évalué comme vrai.
        if missing:
            # On ajoute ' Attention : vignobles non couverts par cette exécution : ' + ',
            # '.join(missing) +… à message et on conserve ce nouvel état pour la suite.
            message += (
                " Attention : vignobles non couverts par cette exécution : "
                + ", ".join(missing)
                + "."
            )
        # Cette branche traite le cas où toutes les conditions regroupées ici sont remplies.
        if (
            latest
            # On exige aussi que la condition active_matches_latest(frames) n’est pas remplie.
            and not active_matches_latest(frames)
            # On exige aussi que la condition frames.get('reconciliation_vineyard_current',
            # pd.DataFrame()).empty n’est pas remplie.
            and not frames.get("reconciliation_vineyard_current", pd.DataFrame()).empty
        ):
            # On ajoute ' Les bilans actifs en base diffèrent de ce scan. Ils sont accessibles
            # séparément da… à message et on conserve ce nouvel état pour la suite.
            message += " Les bilans actifs en base diffèrent de ce scan. Ils sont accessibles séparément dans la liste."
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return out, message
    except ValueError as exc:
        # On garde dans out un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        out = dict(
            payload, mode="unavailable", snapshot_run=run, snapshot_latest=latest
        )
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return out, "Consultation suspendue : " + str(
            exc
        ) + " Choisir un autre scan ou actualiser les données."


# On construit les composants et les callbacks du dashboard ; démarrer le serveur reste une opération
# distincte.
def make_app():
    # On garde dans app la valeur renvoyée par Dash.
    app = Dash(
        __name__,
        title=TITLE + " · V6",
        suppress_callback_exceptions=True,
        update_title="Chargement…",
    )
    # On garde dans initial_payload la représentation sérialisable préparée pour ces données.
    initial_payload = serialise(load_dashboard_state())
    # On garde dans initial le repère de l’état conservé par le stockage local du dashboard.
    initial = put_store(initial_payload)

    # On prépare les paramètres initiaux de la consultation.
    def initial_view():
        # On répartit les valeurs renvoyées par select_snapshot entre (view, message) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        view, message = select_snapshot(initial_payload, "__LATEST__")
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return put_store(view), message

    # On répartit les valeurs renvoyées par cached entre (initial_view_ref, initial_note) ; leur ordre
    # doit correspondre à celui prévu par cet appel.
    initial_view_ref, initial_note = cached(
        resolve_store(initial), ("view", "__LATEST__"), initial_view
    )

    # On prépare l’indication visuelle du mode de données utilisé.
    def badge(mode):
        # On fournit à l’appelant le champ mode de {'database': 'Données PostgreSQL', 'mock':
        # 'DÉMONSTRATION · donn… avec le repli indiqué si la clé est absente.
        return {
            # On associe la clé 'database' à cette valeur dans cet objet.
            "database": "Données PostgreSQL",
            # On associe la clé 'mock' à cette valeur dans cet objet.
            "mock": "DÉMONSTRATION · données fictives",
            # On associe la clé 'unavailable' à cette valeur dans cet objet.
            "unavailable": "Connexion indisponible",
        }.get(mode, "")

    # On garde dans app.index_string le résultat du remplacement demandé sur app.index_string.
    app.index_string = app.index_string.replace(
        "</head>",
        '<script>document.addEventListener("DOMContentLoaded",function(){new MutationObserver(function(){document.querySelectorAll("button.export").forEach(function(b){if(b.textContent==="Export")b.textContent="Exporter en CSV";});}).observe(document.body,{childList:true,subtree:true});});</script></head>',
    )
    # On garde dans app.layout le composant html.Main avec le contenu et les propriétés indiqués.
    app.layout = html.Main(
        # On rattache ce composant aux règles CSS de cette classe.
        className="page-shell",
        # On fournit le contenu enfant de ce composant d’interface.
        children=[
            dcc.Store(id="dashboard-store", data=initial),
            dcc.Store(id="view-store", data=initial_view_ref),
            dcc.Store(id="selected-metric", data=None),
            html.Header(
                # On rattache ce composant aux règles CSS de cette classe.
                className="hero",
                # On fournit le contenu enfant de ce composant d’interface.
                children=[
                    html.Div(
                        [
                            html.Img(
                                src=app.get_asset_url("demo.svg"),
                                alt="Demo",
                                # On rattache ce composant aux règles CSS de cette classe.
                                className="brand-logo",
                            ),
                            html.H1(TITLE),
                            html.P(
                                "Les suivis Excel croisés avec les dossiers et fichiers observés sur le NAS.",
                                # On rattache ce composant aux règles CSS de cette classe.
                                className="hero-subtitle",
                            ),
                        ]
                    ),
                    html.Div(
                        # On rattache ce composant aux règles CSS de cette classe.
                        className="hero-actions",
                        # On fournit le contenu enfant de ce composant d’interface.
                        children=[
                            html.Button(
                                "Actualiser les données",
                                # On donne au composant son identifiant, utilisé ensuite pour les
                                # callbacks et les sélecteurs.
                                id="reload-button",
                                n_clicks=0,
                                # On rattache ce composant aux règles CSS de cette classe.
                                className="primary-button",
                                title="Recharge les résultats PostgreSQL sans relancer le pipeline.",
                            ),
                            html.Span(
                                badge(initial["mode"]),
                                # On donne au composant son identifiant, utilisé ensuite pour les
                                # callbacks et les sélecteurs.
                                id="mode-badge",
                                # On rattache ce composant aux règles CSS de cette classe.
                                className="mode-badge",
                            ),
                            html.Small(
                                "Lecture des résultats enregistrés, sans nouveau contrôle du NAS."
                            ),
                        ],
                    ),
                ],
            ),
            dcc.Loading(
                html.Div(
                    initial["status_message"],
                    # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                    # sélecteurs.
                    id="status-banner",
                    # On rattache ce composant aux règles CSS de cette classe.
                    className="status-banner",
                ),
                type="circle",
            ),
            html.Section(
                # On rattache ce composant aux règles CSS de cette classe.
                className="snapshot-controls",
                # On fournit le contenu enfant de ce composant d’interface.
                children=[
                    html.Div(
                        [
                            html.Label(
                                "Date de l’état des données", htmlFor="snapshot-select"
                            ),
                            dcc.Dropdown(
                                # On donne au composant son identifiant, utilisé ensuite pour les
                                # callbacks et les sélecteurs.
                                id="snapshot-select",
                                # On fournit les choix que ce contrôle doit proposer à l’utilisateur.
                                options=snapshot_options(
                                    {
                                        k: pd.DataFrame(v)
                                        for k, v in initial_payload["frames"].items()
                                    }
                                ),
                                # On fixe la valeur initiale ou courante de cette propriété.
                                value="__LATEST__",
                                clearable=False,
                            ),
                        ]
                    ),
                    html.P(
                        "La date choisie détermine les données affichées dans « Vue d’ensemble », « Rechercher » et « Ce qui resterait à faire ». Dans « Évolution », les dates à comparer se choisissent séparément.",
                        # On rattache ce composant aux règles CSS de cette classe.
                        className="snapshot-help",
                    ),
                    html.Div(initial_note, id="snapshot-banner", role="status"),
                ],
            ),
            dcc.Tabs(
                # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                # sélecteurs.
                id="main-tabs",
                # On fixe la valeur initiale ou courante de cette propriété.
                value="overview",
                # On fournit le contenu enfant de ce composant d’interface.
                children=[
                    dcc.Tab(label="Vue d’ensemble", value="overview"),
                    dcc.Tab(label="Rechercher", value="search"),
                    dcc.Tab(label="Ce qui resterait à faire", value="focus"),
                    dcc.Tab(label="Évolution", value="evolution"),
                ],
            ),
            html.Section(
                # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                # sélecteurs.
                id="global-filters",
                # On rattache ce composant aux règles CSS de cette classe.
                className="filters",
                # On fournit le contenu enfant de ce composant d’interface.
                children=[
                    html.Div(
                        [
                            html.Label("Vignoble", htmlFor="vineyard-filter"),
                            dcc.Dropdown(
                                # On donne au composant son identifiant, utilisé ensuite pour les
                                # callbacks et les sélecteurs.
                                id="vineyard-filter",
                                # On fournit les choix que ce contrôle doit proposer à l’utilisateur.
                                options=vineyard_options(initial),
                                # On fixe la valeur initiale ou courante de cette propriété.
                                value="__ALL__",
                                clearable=False,
                            ),
                        ]
                    ),
                    html.Div(
                        # On donne au composant son identifiant, utilisé ensuite pour les callbacks et
                        # les sélecteurs.
                        id="perimeter-filter-wrap",
                        # On fournit le contenu enfant de ce composant d’interface.
                        children=[
                            html.Label(
                                "Catégorie issue du suivi Excel",
                                htmlFor="perimeter-filter",
                            ),
                            dcc.Dropdown(
                                # On donne au composant son identifiant, utilisé ensuite pour les
                                # callbacks et les sélecteurs.
                                id="perimeter-filter",
                                # On fournit les choix que ce contrôle doit proposer à l’utilisateur.
                                options=[
                                    {"label": v, "value": v}
                                    for v in ["Production", "Test", "Bloqué", "Inconnu"]
                                ]
                                + [
                                    {
                                        # On renseigne le libellé sous la clé 'label'.
                                        "label": "Toutes les catégories",
                                        # On renseigne la valeur reçue sous la clé 'value'.
                                        "value": "__ALL__",
                                    }
                                ],
                                # On fixe la valeur initiale ou courante de cette propriété.
                                value="__ALL__",
                                clearable=False,
                            ),
                        ],
                    ),
                ],
            ),
            dcc.Loading(
                html.Div(id="tab-content", className="tab-content"),
                custom_spinner=html.Div(
                    "Chargement de l’onglet…",
                    # On rattache ce composant aux règles CSS de cette classe.
                    className="loading-message",
                    role="status",
                ),
                target_components={"tab-content": "children"},
            ),
            html.Footer(
                "Consultation uniquement · aucune écriture dans PostgreSQL · aucun accès direct au NAS · aucun déclenchement Airflow"
            ),
        ],
    )

    # On recharge les données du dashboard selon le mode configuré pour cette session.
    @app.callback(
        Output("dashboard-store", "data"),
        Output("status-banner", "children"),
        Output("mode-badge", "children"),
        Output("vineyard-filter", "options"),
        Output("snapshot-select", "options"),
        Output("snapshot-select", "value"),
        Input("reload-button", "n_clicks"),
        State("snapshot-select", "value"),
        # On choisit si Dash doit appeler ce callback dès l’initialisation de la page.
        prevent_initial_call=True,
    )
    def reload_data(_, selected_run):
        # On garde dans payload la représentation sérialisable préparée pour ces données.
        payload = serialise(load_dashboard_state())
        # On garde dans options les choix d’états historiques disponibles pour ce périmètre.
        options = snapshot_options(
            {k: pd.DataFrame(v) for k, v in payload["frames"].items()}
        )
        # On choisit la valeur de selected_run selon ce test : selected_run appartient à {o['value']
        # for o in options}. Les deux résultats possibles restent définis explicitement ici.
        selected_run = (
            selected_run
            if selected_run in {o["value"] for o in options}
            else "__LATEST__"
        )
        # On renvoie ces 6 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return (
            put_store(payload),
            payload["status_message"],
            badge(payload["mode"]),
            vineyard_options(payload),
            options,
            selected_run,
        )

    # On applique le choix d’un état enregistré à la consultation.
    @app.callback(
        Output("view-store", "data"),
        Output("snapshot-banner", "children"),
        Input("snapshot-select", "value"),
        Input("dashboard-store", "data"),
    )
    def choose_snapshot(run, payload):
        # On garde dans source l’état du dashboard retrouvé à partir de son repère de stockage.
        source = resolve_store(payload)

        # On assemble les éléments de présentation prévus par ce bloc local.
        def build():
            # On répartit les valeurs renvoyées par select_snapshot entre (view, message) ; leur ordre
            # doit correspondre à celui prévu par cet appel.
            view, message = select_snapshot(source, run)
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return put_store(view), message

        # On fournit à l’appelant les données fournies par cet accès au cache.
        return cached(source, ("view", run), build)

    # On met à jour les critères propres à la liste des points à vérifier.
    @app.callback(
        Output({"role": "focus-local", "key": MATCH}, "children"),
        Input({"role": "focus-chart", "key": MATCH}, "clickData"),
        Input({"role": "focus-clear", "key": MATCH}, "n_clicks"),
        State("view-store", "data"),
        State("vineyard-filter", "value"),
        # On choisit si Dash doit appeler ce callback dès l’initialisation de la page.
        prevent_initial_call=True,
    )
    def local_focus(click, clear_clicks, store, vineyard):
        # On garde ctx.triggered_id sous le nom trigger ; cette affectation ne copie pas à elle seule
        # un objet mutable.
        trigger = ctx.triggered_id
        # Cette action ne désigne pas un composant exploitable. On laisse les filtres en place.
        if not isinstance(trigger, dict):
            # On lève cette exception au lieu de continuer avec un résultat non confirmé.
            raise PreventUpdate
        # On récupère la clé de l’élément dans trigger et on le garde dans key pour la suite.
        key = trigger["key"]
        # On initialise selected à None : aucune valeur n’a encore été retenue ici.
        selected = None
        # Cette branche traite le cas où trigger['role'] correspond au texte 'focus-chart' et click
        # est évalué comme vrai et le champ 'points' de click est évalué comme vrai.
        if trigger["role"] == "focus-chart" and click and click.get("points"):
            # On garde dans selected le champ 'x' de click['points'][0], ou None si la clé est absente.
            selected = click["points"][0].get("x")
        # On répartit les valeurs renvoyées par prepared entre (aq, ps, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        aq, ps, _ = prepared(store, vineyard, "__ALL__", "")
        # On répartit les valeurs renvoyées par focus_sections entre (entries, _) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        entries, _ = focus_sections(aq, ps)
        # On sélectionne dans entries les éléments désignés par key ; item recevra cette sélection.
        item = entries[key]
        # On garde dans rows la valeur renvoyée par filter_focus_population.
        rows = filter_focus_population(item["missing"], selected)
        # On choisit la valeur de cols selon ce test : item['grain'] correspond au texte 'acq'. Les
        # deux résultats possibles restent définis explicitement ici.
        cols = (
            ACQ_COLUMNS
            + ["nas_observations_display", "processing_next_action", "focus_reason"]
            if item["grain"] == "acq"
            else PASSAGE_COLUMNS + ["focus_reason"]
        )
        # On choisit la valeur de note selon ce test : la sélection retenue est évalué comme vrai. Les
        # deux résultats possibles restent définis explicitement ici.
        note = (
            (
                "Filtre local : "
                + str(selected)
                + " · "
                + str(len(rows))
                + " ligne(s). Le graphique et les autres critères restent inchangés."
            )
            if selected
            else "Tous les vignobles du périmètre sélectionné en haut de page."
        )
        # On fournit à l’appelant le panneau de tableau construit pour ces données.
        return table_panel(rows, "focus-" + key, "Éléments concernés", cols, note)

    # On prépare la remise à zéro des filtres locaux concernés.
    @app.callback(
        Output({"role": "focus-chart", "key": MATCH}, "clickData"),
        Input({"role": "focus-clear", "key": MATCH}, "n_clicks"),
        # On choisit si Dash doit appeler ce callback dès l’initialisation de la page.
        prevent_initial_call=True,
    )
    def reset_local_click(_):
        # Reset the event too: clicking the same bar after clearing must work.
        return None

    # On enregistre les choix validés pour déclencher une comparaison sur ces paramètres.
    @app.callback(
        Output("evolution-applied", "data"),
        Output("compare-validation", "children"),
        Input("compare-apply", "n_clicks"),
        State("compare-mode", "value"),
        State("compare-dates", "value"),
        State("dashboard-store", "data"),
        State("vineyard-filter", "value"),
        # On choisit si Dash doit appeler ce callback dès l’initialisation de la page.
        prevent_initial_call=True,
    )
    def apply_comparison(clicks, mode, dates, store, vineyard):
        # On rend disponibles no_update depuis dash, pour les appels de ce fichier.
        from dash import no_update

        # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
        try:
            # On garde dans request la demande de comparaison construite avec cette sélection.
            request = comparison_request(store, vineyard, mode, dates)
            # On garde clicks sous le nom request['applied_click'] ; cette affectation ne copie pas à
            # elle seule un objet mutable.
            request["applied_click"] = clicks
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return request, ""
        except ValueError as exc:
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return no_update, html.P(str(exc), className="history-warning")

    # On présente le retour sur les dates choisies avant ou après application.
    @app.callback(
        Output("compare-selection-note", "children"),
        Output("compare-apply", "disabled"),
        Input("compare-mode", "value"),
        Input("compare-dates", "value"),
        Input("evolution-applied", "data"),
        State("dashboard-store", "data"),
        State("vineyard-filter", "value"),
    )
    def compare_feedback(mode, dates, applied, store, vineyard):
        # On fournit à l’appelant le retour de présentation correspondant à la sélection.
        return selection_feedback(store, vineyard, mode, dates, applied)

    # On met à jour les deux sorties de comparaison, y compris dans le chemin d’erreur.
    @app.callback(
        Output("evolution-summary-results", "children"),
        Output("evolution-chart-results", "children"),
        Output("evolution-detail-results", "children"),
        Input("evolution-applied", "data"),
        Input("evolution-family", "value"),
        Input("evolution-kind", "value"),
        Input("evolution-measure", "value"),
        State("dashboard-store", "data"),
        State("vineyard-filter", "value"),
    )
    def update_evolution(applied, family, kind, measure, store, vineyard):
        # Sans sélection appliquée, on ne lance pas une nouvelle comparaison.
        if not applied:
            # On lève cette exception au lieu de continuer avec un résultat non confirmé.
            raise PreventUpdate
        # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
        try:
            # On fournit à l’appelant la valeur renvoyée par evolution_results.
            return evolution_results(
                store,
                vineyard,
                applied["mode"],
                applied["dates"],
                family,
                kind,
                measure,
                table_panel,
                section,
            )
        except Exception:
            # On appelle logging.exception avec 'Comparaison V6 interrompue'.
            logging.exception("Comparaison V6 interrompue")
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return (
                panel(
                    "Comparaison interrompue",
                    "Les résultats ne peuvent pas être calculés. Actualiser les données puis réessayer. Si le problème persiste, consulter le journal du terminal. Aucun résultat « sans changement » n’est déduit de cette erreur.",
                ),
                html.Div(),
            )

    # On active les choix de dates adaptés au mode de comparaison.
    @app.callback(
        Output("compare-dates", "options"),
        Output("compare-dates-wrap", "style"),
        Input("compare-mode", "value"),
        State("dashboard-store", "data"),
        State("vineyard-filter", "value"),
    )
    def compare_dates_enabled(mode, store, vineyard):
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return (
            [
                dict(o, disabled=mode != "selected")
                for o in batch_options(
                    {
                        k: pd.DataFrame(v)
                        for k, v in resolve_store(store).get("frames", {}).items()
                    },
                    vineyard,
                )
            ],
            {} if mode == "selected" else {"display": "none"},
        )

    # On adapte les filtres visibles au contexte de consultation.
    @app.callback(
        Output("global-filters", "style"),
        Output("perimeter-filter-wrap", "style"),
        Input("main-tabs", "value"),
    )
    def filter_visibility(tab):
        # Work-remaining counts always use the production scope, not a Test filter.
        return ({"display": "none"} if tab == "search" else {}), (
            {"display": "none"} if tab in {"focus", "evolution"} else {}
        )

    # On applique le choix de l’indicateur à présenter.
    @app.callback(
        Output("selected-metric", "data"),
        Input({"role": "metric", "key": ALL}, "n_clicks"),
        # On choisit si Dash doit appeler ce callback dès l’initialisation de la page.
        prevent_initial_call=True,
    )
    def select_metric(clicks):
        # On ne change l’indicateur qu’après un clic associé à un composant identifié.
        if not any(clicks) or not isinstance(ctx.triggered_id, dict):
            # On lève cette exception au lieu de continuer avec un résultat non confirmé.
            raise PreventUpdate
        # On remet la clé de l’élément dans ctx.triggered_id à l’appelant ; les étapes suivantes de
        # cette fonction ne sont plus parcourues.
        return ctx.triggered_id["key"]

    # On reconstruit le contenu demandé avec les paramètres courants.
    @app.callback(
        Output("tab-content", "children"),
        Input("main-tabs", "value"),
        Input("view-store", "data"),
        Input("vineyard-filter", "value"),
        Input("perimeter-filter", "value"),
        Input("selected-metric", "data"),
        Input("dashboard-store", "data"),
    )
    def render(tab, store, vineyard, perimeter, selected, source):
        # Cette branche traite le cas où tab diffère du texte 'evolution' et ctx.triggered_id
        # correspond au texte 'dashboard-store'.
        if tab != "evolution" and ctx.triggered_id == "dashboard-store":
            # Wait for the matching frozen view, rather than painting old rows
            # beneath the status of a just-refreshed source bundle.
            raise PreventUpdate
        # Cette branche traite le cas où tab correspond au texte 'evolution' et ctx.triggered_id
        # appartient à {'view-store', 'perimeter-filter', 'selected-metric'}.
        if tab == "evolution" and ctx.triggered_id in {
            "view-store",
            "perimeter-filter",
            "selected-metric",
        }:
            # On lève cette exception au lieu de continuer avec un résultat non confirmé.
            raise PreventUpdate
        # On garde dans content la valeur renvoyée par render_content.
        content = render_content(
            tab,
            source if tab == "evolution" else store,
            vineyard,
            "__ALL__" if tab == "focus" else perimeter,
            selected,
        )
        # On fournit à l’appelant le composant html.Div avec le contenu et les propriétés indiqués.
        return html.Div(content, **{"data-rendered-tab": tab})

    # On applique les critères de recherche au catalogue disponible.
    @app.callback(
        Output("search-results", "children"),
        Input("search-query", "value"),
        Input("search-kind", "value"),
        Input("search-vineyard", "value"),
        Input("view-store", "data"),
    )
    def search(query, kind, vineyard, store):
        # On fournit à l’appelant la valeur renvoyée par search_results.
        return search_results(store, query, kind, vineyard)

    # On met à jour les colonnes visibles sans changer les résultats métier sous-jacents.
    @app.callback(
        Output({"role": "table", "key": MATCH}, "columns"),
        Output({"role": "table", "key": MATCH}, "selected_columns"),
        Input({"role": "columns", "key": MATCH}, "value"),
    )
    def change_columns(cols):
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return table_columns(cols, label), (cols or [])[:1]

    # On prépare la copie d’une colonne dans une forme lisible hors du tableau.
    @app.callback(
        Output({"role": "clipboard", "key": MATCH}, "content"),
        Output({"role": "copy-label", "key": MATCH}, "children"),
        Input({"role": "table", "key": MATCH}, "selected_columns"),
        Input({"role": "table", "key": MATCH}, "derived_virtual_data"),
        State({"role": "table", "key": MATCH}, "data"),
    )
    def copy_column(columns, virtual_rows, data):
        # On prévoit le cas où columns est évalué comme faux, par exemple une valeur vide selon son
        # type.
        if not columns:
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return "", "Sélectionner une colonne dans le tableau."
        # On récupère columns[0] et on le garde dans col pour la suite.
        col = columns[0]
        # On choisit la valeur de rows selon ce test : virtual_rows vaut None. Les deux résultats
        # possibles restent définis explicitement ici.
        rows = data if virtual_rows is None else virtual_rows
        # On garde dans value la valeur renvoyée par plain_clipboard.
        value = plain_clipboard(rows or [], col)
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return (
            value,
            f"{label(col)} — {len(rows or [])} valeur(s), toutes pages filtrées et triées. Copier avec l’icône ; l’export CSV est également disponible.",
        )

    # On prépare le téléchargement avec des valeurs sans mise en forme Markdown.
    @app.callback(
        Output({"role": "plain-download", "key": MATCH}, "data"),
        Input({"role": "plain-export", "key": MATCH}, "n_clicks"),
        State({"role": "table", "key": MATCH}, "derived_virtual_data"),
        State({"role": "table", "key": MATCH}, "data"),
        State({"role": "table", "key": MATCH}, "columns"),
        # On choisit si Dash doit appeler ce callback dès l’initialisation de la page.
        prevent_initial_call=True,
    )
    def export_plain(clicks, virtual_rows, rows, columns):
        # Sans demande de téléchargement, il n’y a pas de CSV à préparer.
        if not clicks:
            # On lève cette exception au lieu de continuer avec un résultat non confirmé.
            raise PreventUpdate
        # On choisit la valeur de data selon ce test : virtual_rows vaut None. Les deux résultats
        # possibles restent définis explicitement ici.
        data = rows if virtual_rows is None else virtual_rows
        # On récupère la clé de l’élément dans ctx.triggered_id et on le garde dans key pour la suite.
        key = ctx.triggered_id["key"]
        # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
        return dict(
            content=plain_csv(data, columns or []),
            # On fournit le nom de fichier via le paramètre filename de cet appel.
            filename="suivi_" + key + ".csv",
            type="text/csv;charset=utf-8",
        )

    # On affiche le détail de la ligne sélectionnée lorsque cette sélection reste valide.
    @app.callback(
        Output({"role": "row-detail", "key": MATCH}, "children"),
        Input({"role": "table", "key": MATCH}, "derived_virtual_selected_rows"),
        Input({"role": "table", "key": MATCH}, "derived_virtual_data"),
        State("view-store", "data"),
    )
    def row_detail(selected, rows, store):
        # Cette branche traite le cas où la condition selected n’est pas remplie ou la condition rows
        # n’est pas remplie ou selected[0] est au moins égal à len(rows).
        if not selected or not rows or selected[0] >= len(rows):
            # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
            return "Sélectionner une ligne du tableau pour consulter ses informations."
        # On sélectionne dans rows les éléments désignés par selected[0] ; row recevra cette sélection.
        row = rows[selected[0]]
        # Cette branche traite le cas où le champ 'entity_key' de la ligne en cours est évalué comme
        # vrai.
        if row.get("entity_key"):
            # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
            try:
                # On fournit à l’appelant la valeur renvoyée par dossier.
                return dossier(row["entity_key"], store)
            except ValueError as exc:
                # On fournit à l’appelant le composant html.P avec le contenu et les propriétés
                # indiqués.
                return html.P("Consultation suspendue : " + str(exc))
        # On fournit à l’appelant le composant html.Dl avec le contenu et les propriétés indiqués.
        return html.Dl(
            [
                html.Div(
                    [
                        html.Dt(label(k)),
                        html.Dd(plain_column_value(row, k) or "Non renseigné"),
                    ]
                )
                for k, v in row.items()
                if k not in {"payload", "kind", "entity_key", NAS_PLAIN}
            ]
        )

    # On remet app à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return app


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On appelle make_app().run sans argument positionnel.
    make_app().run(
        host=os.getenv("DASHBOARD_HOST", "127.0.0.1"),
        port=int(os.getenv("DASHBOARD_PORT", "8050")),
        debug=False,
    )
