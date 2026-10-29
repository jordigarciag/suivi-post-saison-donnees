# Lecture du fichier — Présentation des comparaisons entre les états déjà enregistrés.
# On distingue les dates sélectionnées des dates effectivement appliquées, pour ne pas afficher une
# comparaison qui ne correspond plus au choix annoncé.
#

"""Présentation de l'historique ; aucune connexion ou écriture."""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations
# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd
# On importe plotly.graph_objects sous le nom go. On décrit les traces et la présentation des
# graphiques.
import plotly.graph_objects as go
# On rend disponibles dcc, html depuis dash, pour les appels de ce fichier.
from dash import dcc, html
# On rend disponibles compare_history, batch_options depuis history_engine, pour les appels de ce
# fichier.
from history_engine import compare_history, batch_options
# On rend disponibles resolve_store, cached depuis state_store, pour les appels de ce fichier.
from state_store import resolve_store, cached
# On rend disponibles format_time depuis data_access, pour les appels de ce fichier.
from data_access import format_scan_time as format_time

# On rassemble dans FAMILIES les 9 éléments explicitement indiqués, en conservant leur structure.
FAMILIES = [
    "Périmètre recensé",
    "Excel · statuts",
    "Excel · catégories",
    "Excel · commentaires",
    "Excel · autres informations",
    "NAS · constats",
    "NAS · livrables",
    "Rattachements",
    "Contrôles · vérifiabilité",
]
# On rassemble dans MEASURES les 8 éléments explicitement indiqués, en conservant leur structure.
MEASURES = [
    "Acquisitions",
    "Production",
    "Tests",
    "Bloqué / en attente",
    "Production traitée",
    "Passages",
    "Vitimap",
    "Vitiparcel",
]
# On rassemble dans COLORS les 8 éléments explicitement indiqués, en conservant leur structure.
COLORS = [
    "#245DC4",
    "#BA500A",
    "#23764F",
    "#7C3BA0",
    "#9D244A",
    "#087C86",
    "#685B18",
    "#414B68",
]


# On retrouve les tableaux nécessaires à partir de l’état stocké côté serveur.
def frames_of(store):
    # On garde dans store l’état du dashboard retrouvé à partir de son repère de stockage.
    store = resolve_store(store)
    # On remet {k: pd.DataFrame(v) for k, v in store.get('frames', {}).items()} à l’appelant ; les
    # étapes suivantes de cette fonction ne sont plus parcourues.
    return {k: pd.DataFrame(v) for k, v in store.get("frames", {}).items()}


# On prépare la comparaison correspondant à l’état de données disponible.
def comparison_for_store(store, vineyard, mode="latest", dates=None):
    # On garde dans store l’état du dashboard retrouvé à partir de son repère de stockage.
    store = resolve_store(store)
    # On rassemble dans key les 4 éléments explicitement indiqués, en conservant leur structure.
    key = (
        "comparison",
        vineyard,
        mode,
        tuple(sorted(dates or [])) if mode == "selected" else (),
    )
    # On fournit à l’appelant les données fournies par cet accès au cache.
    return cached(
        store,
        key,
        lambda: compare_history(
            frames_of(store), vineyard, dates, latest=mode != "selected"
        ),
    )


# On distingue la sélection en cours de la comparaison réellement appliquée.
def comparison_request(store, vineyard, mode, dates):
    # On garde dans options les options de sélection des lots disponibles.
    options = batch_options(frames_of(store), vineyard)
    # On construit allowed comme un ensemble sans doublons à partir de o['value'], pour chaque o de
    # options.
    allowed = {o["value"] for o in options}
    # On choisit la valeur de chosen selon ce test : mode correspond au texte 'latest'. Les deux
    # résultats possibles restent définis explicitement ici.
    chosen = (
        [o["value"] for o in options[:2]]
        if mode == "latest"
        else [o["value"] for o in options if o["value"] in set(dates or [])]
    )
    # Comparer un seul état n’aurait pas de sens : il faut au moins deux dates.
    if len(chosen) < 2:
        # On interrompt cette branche avec ValueError : 'Choisir au moins deux scans, puis cliquer sur
        # « Comparer les scans sélectionnés ».'.
        raise ValueError(
            "Choisir au moins deux scans, puis cliquer sur « Comparer les scans sélectionnés »."
        )
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {"mode": mode, "dates": chosen, "vineyard": vineyard}


# On explique la sélection courante et les conditions nécessaires pour l’appliquer.
def selection_feedback(store, vineyard, mode, dates, applied):
    # On garde dans options les options de sélection des lots disponibles.
    options = batch_options(frames_of(store), vineyard)
    # On choisit la valeur de chosen selon ce test : mode correspond au texte 'selected'. Les deux
    # résultats possibles restent définis explicitement ici.
    chosen = (
        [o for o in options if o["value"] in set(dates or [])]
        if mode == "selected"
        else options[:2]
    )
    # On extrait o['label'].split(' ⇒ ')[0] pour chaque élément retenu ; labels rassemble ces
    # valeurs sans modifier les objets d’origine.
    labels = [o["label"].split(" ⇒ ")[0] for o in chosen]
    # On prépare selection avec cette expression pour l’utiliser dans la suite du traitement.
    selection = f"{len(chosen)} scans sélectionnés"
    # Cette branche traite le cas où labels est évalué comme vrai.
    if labels:
        # On ajoute ' · du ' + labels[-1] + ' au ' + labels[0] à selection et on conserve ce nouvel
        # état pour la suite.
        selection += " · du " + labels[-1] + " au " + labels[0]
    # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
    try:
        # On garde dans request la demande de comparaison construite avec cette sélection.
        request = comparison_request(store, vineyard, mode, dates)
        # On retient pour dirty la première valeur évaluée comme vraie dans cette chaîne de replis ;
        # une valeur vide fera donc passer à la suivante.
        dirty = not applied or any(
            request.get(k) != applied.get(k) for k in ["mode", "dates", "vineyard"]
        )
    except ValueError:
        # On initialise dirty à True ; les branches suivantes pourront modifier cet état.
        dirty = True
    # On choisit la valeur de note selon ce test : dirty est évalué comme vrai. Les deux résultats
    # possibles restent définis explicitement ici.
    note = (
        "Sélection non appliquée. Cliquer sur « Comparer les scans sélectionnés ». Les résultats ci-dessous correspondent encore à la comparaison précédente."
        if dirty
        else "La sélection correspond aux résultats affichés ci-dessous."
    )
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return html.Div(
        [html.Strong(selection), html.P(note)],
        # On rattache ce composant aux règles CSS de cette classe.
        className="selection-state pending" if dirty else "selection-state applied",
    ), len(chosen) < 2


# On transforme les avertissements en éléments de présentation sans en déduire un résultat métier.
def warning_list(result):
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return (
        html.Div(
            [
                html.Strong("Limites de la comparaison"),
                html.Ul([html.Li(m) for m in result.messages]),
            ],
            # On rattache ce composant aux règles CSS de cette classe.
            className="history-warning",
        )
        if result.messages
        else html.Div()
    )


# On prépare la synthèse visuelle des évolutions disponibles.
def overview_evolution(store, vineyard):
    # On garde dans result le résultat de comparaison préparé pour l’état stocké du dashboard.
    result = comparison_for_store(store, vineyard)
    # On garde result.timeline sous le nom rows ; cette affectation ne copie pas à elle seule un objet
    # mutable.
    rows = result.timeline
    # On prépare dates comme liste vide ; on la remplira au fil des opérations suivantes.
    dates = []
    # Cette branche traite le cas où la condition rows.empty n’est pas remplie.
    if not rows.empty:
        # On parcourt rows.groupby('Vignoble', sort=True) ; (v, g) désigne l’élément courant à chaque
        # passage dans la boucle.
        for v, g in rows.groupby("Vignoble", sort=True):
            # On ajoute html.Li(v + ' : ' + ' → '.join(g['Observation NAS'].tolist())) à la fin de
            # dates ; les éléments précédents restent conservés.
            dates.append(html.Li(v + " : " + " → ".join(g["Observation NAS"].tolist())))
    # On commence range_note avec un texte vide, à compléter uniquement si la suite apporte une
    # information.
    range_note = ""
    # Cette branche traite le cas où la condition rows.empty n’est pas remplie.
    if not rows.empty:
        # On garde dans dates_ts la conversion en dates avec les règles indiquées, notamment pour les
        # valeurs invalides.
        dates_ts = pd.to_datetime(rows["_time"], utc=True, errors="coerce")
        # On assemble ces deux éléments pour construire range_note.
        range_note = (
            "Plage des observations comparées : "
            + format_time(dates_ts.min())
            + " → "
            + format_time(dates_ts.max())
            + "."
        )
    # On fournit à l’appelant le composant html.Section avec le contenu et les propriétés indiqués.
    return html.Section(
        [
            html.H3("Depuis le scan précédent"),
            html.P(result.headline(), className="evolution-headline"),
            html.P(range_note, className="table-help"),
            html.P(
                "Comparaison des deux dernières exécutions disponibles, tous statuts confondus. Le filtre de catégorie ne s’applique pas à ce résumé.",
                # On rattache ce composant aux règles CSS de cette classe.
                className="muted",
            ),
            html.Details(
                [
                    html.Summary("Dates comparées et limites"),
                    html.Ul(dates),
                    warning_list(result),
                ]
            ),
            html.P(
                "Ouvrir l’onglet Évolution pour choisir d’autres dates et consulter les valeurs avant / après.",
                # On rattache ce composant aux règles CSS de cette classe.
                className="muted",
            ),
        ],
        # On rattache ce composant aux règles CSS de cette classe.
        className="panel evolution-summary",
    )


# On construit les composants de sélection et de résultat de la page de comparaison.
def evolution_page(store, vineyard, table_panel, section):
    # On garde dans options les options de sélection des lots disponibles.
    options = batch_options(frames_of(store), vineyard)
    # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
    try:
        # On garde dans applied la demande de comparaison construite avec cette sélection.
        applied = comparison_request(store, vineyard, "latest", [])
    except ValueError:
        # On regroupe dans applied ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        applied = {"mode": "latest", "dates": [], "vineyard": vineyard}
    # On fournit à l’appelant le composant html.Div avec le contenu et les propriétés indiqués.
    return html.Div(
        [
            dcc.Store(id="evolution-applied", data=applied),
            html.Section(
                [
                    html.H2("Quels changements entre les scans ?"),
                    html.P(
                        "Comparer les acquisitions recensées, les statuts et commentaires Excel, les constats NAS et les livrables."
                    ),
                    html.P(
                        "Le filtre Vignoble en haut de page s’applique à cette comparaison. La date choisie pour « Vue d’ensemble », « Rechercher » et « Ce qui resterait à faire » ne la modifie pas.",
                        # On rattache ce composant aux règles CSS de cette classe.
                        className="scope-note",
                    ),
                ],
                # On rattache ce composant aux règles CSS de cette classe.
                className="panel evolution-intro",
            ),
            html.Section(
                [
                    html.H3("1. Choisir les scans à comparer"),
                    dcc.RadioItems(
                        # On donne au composant son identifiant, utilisé ensuite pour les callbacks et
                        # les sélecteurs.
                        id="compare-mode",
                        # On fournit les choix que ce contrôle doit proposer à l’utilisateur.
                        options=[
                            {"label": " Dernier scan / précédent", "value": "latest"},
                            {"label": " Choisir les dates", "value": "selected"},
                        ],
                        # On fixe la valeur initiale ou courante de cette propriété.
                        value="latest",
                        # On rattache ce composant aux règles CSS de cette classe.
                        className="compare-radio",
                    ),
                    html.Div(
                        [
                            html.Label("Scans disponibles", htmlFor="compare-dates"),
                            dcc.Checklist(
                                # On donne au composant son identifiant, utilisé ensuite pour les
                                # callbacks et les sélecteurs.
                                id="compare-dates",
                                # On fournit les choix que ce contrôle doit proposer à l’utilisateur.
                                options=[dict(o, disabled=True) for o in options],
                                # On fixe la valeur initiale ou courante de cette propriété.
                                value=[o["value"] for o in options[:2]],
                                # On rattache ce composant aux règles CSS de cette classe.
                                className="scan-checklist",
                            ),
                        ],
                        # On donne au composant son identifiant, utilisé ensuite pour les callbacks et
                        # les sélecteurs.
                        id="compare-dates-wrap",
                    ),
                    html.Div(
                        # On donne au composant son identifiant, utilisé ensuite pour les callbacks et
                        # les sélecteurs.
                        id="compare-selection-note",
                        role="status",
                        **{"aria-live": "polite"},
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Comparer les scans sélectionnés",
                                # On donne au composant son identifiant, utilisé ensuite pour les
                                # callbacks et les sélecteurs.
                                id="compare-apply",
                                n_clicks=0,
                                # On rattache ce composant aux règles CSS de cette classe.
                                className="primary-button",
                            ),
                            html.Span(
                                "Les deux derniers scans sont comparés automatiquement à l’ouverture.",
                                # On rattache ce composant aux règles CSS de cette classe.
                                className="table-help",
                            ),
                        ],
                        # On rattache ce composant aux règles CSS de cette classe.
                        className="compare-actions",
                    ),
                    html.Div(id="compare-validation", role="alert"),
                ],
                # On rattache ce composant aux règles CSS de cette classe.
                className="panel comparison-setup",
            ),
            dcc.Loading(
                html.Div(
                    [
                        html.Div(id="evolution-summary-results"),
                        html.Section(
                            [
                                html.H3("2. Suivre les volumes"),
                                html.Div(
                                    [
                                        html.Label(
                                            "Volume à afficher",
                                            htmlFor="evolution-measure",
                                        ),
                                        dcc.Dropdown(
                                            # On donne au composant son identifiant, utilisé ensuite pour les
                                            # callbacks et les sélecteurs.
                                            id="evolution-measure",
                                            # On fournit les choix que ce contrôle doit proposer à
                                            # l’utilisateur.
                                            options=MEASURES,
                                            # On fixe la valeur initiale ou courante de cette propriété.
                                            value="Acquisitions",
                                            clearable=False,
                                        ),
                                    ],
                                    # On rattache ce composant aux règles CSS de cette classe.
                                    className="measure-control",
                                ),
                                html.Div(id="evolution-chart-results"),
                            ],
                            # On rattache ce composant aux règles CSS de cette classe.
                            className="panel evolution-volume",
                        ),
                        html.Section(
                            [
                                html.H3("3. Consulter les changements en détail"),
                                html.P(
                                    "Ces deux filtres agissent uniquement sur la liste des changements, pas sur les compteurs ni sur les volumes.",
                                    # On rattache ce composant aux règles CSS de cette classe.
                                    className="table-help",
                                ),
                                html.Div(
                                    # On rattache ce composant aux règles CSS de cette classe.
                                    className="detail-filters",
                                    # On fournit le contenu enfant de ce composant d’interface.
                                    children=[
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Famille de changements",
                                                    htmlFor="evolution-family",
                                                ),
                                                dcc.Dropdown(
                                                    # On donne au composant son identifiant, utilisé ensuite pour les
                                                    # callbacks et les sélecteurs.
                                                    id="evolution-family",
                                                    # On fournit les choix que ce contrôle doit proposer à
                                                    # l’utilisateur.
                                                    options=["Toutes"] + FAMILIES,
                                                    # On fixe la valeur initiale ou courante de cette propriété.
                                                    value="Toutes",
                                                    clearable=False,
                                                ),
                                            ]
                                        ),
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Type d’élément",
                                                    htmlFor="evolution-kind",
                                                ),
                                                dcc.Dropdown(
                                                    # On donne au composant son identifiant, utilisé ensuite pour les
                                                    # callbacks et les sélecteurs.
                                                    id="evolution-kind",
                                                    # On fournit les choix que ce contrôle doit proposer à
                                                    # l’utilisateur.
                                                    options=[
                                                        "Tous",
                                                        "Acquisition",
                                                        "Passage",
                                                        "Rattachement",
                                                    ],
                                                    # On fixe la valeur initiale ou courante de cette propriété.
                                                    value="Tous",
                                                    clearable=False,
                                                ),
                                            ]
                                        ),
                                    ],
                                ),
                                html.Div(id="evolution-detail-results"),
                            ],
                            # On rattache ce composant aux règles CSS de cette classe.
                            className="panel evolution-detail",
                        ),
                    ],
                    # On donne au composant son identifiant, utilisé ensuite pour les callbacks et les
                    # sélecteurs.
                    id="evolution-results",
                ),
                custom_spinner=html.Div(
                    # On rattache ce composant aux règles CSS de cette classe.
                    "Comparaison en cours…", className="loading-message", role="status"
                ),
                target_components={
                    # On associe la clé 'evolution-summary-results' à cette valeur dans cet objet.
                    "evolution-summary-results": "children",
                    # On associe la clé 'evolution-chart-results' à cette valeur dans cet objet.
                    "evolution-chart-results": "children",
                    # On associe la clé 'evolution-detail-results' à cette valeur dans cet objet.
                    "evolution-detail-results": "children",
                },
            ),
            section(
                "Comprendre les dates comparées",
                [
                    html.P(
                        "Les heures de la liste correspondent à la première et à la dernière observation NAS enregistrées pour les vignobles de l’exécution. Elles ne sont pas les heures exactes de début et de fin du traitement complet. Fuseau : Europe/Paris."
                    ),
                    html.P(
                        "Chaque exécution associe une référence Excel aux constats NAS conservés. Un même scan NAS peut être réutilisé lors d’un nouveau croisement avec Excel : les deux exécutions restent comparables, y compris lorsque seul le suivi Excel a changé."
                    ),
                    html.P(
                        "Avec plusieurs dates, les états sélectionnés sont comparés dans l’ordre chronologique, deux à deux. Un changement ensuite annulé reste visible. Les tests antérieurs à la première exécution complète des huit vignobles du 14/10/2026 ne sont pas proposés."
                    ),
                    html.P(
                        "« Dernier scan » repère l’exécution conservée la plus récente. Cela ne signifie pas que des informations ont changé. « Actualiser les données » relit PostgreSQL sans lancer un scan ni une ingestion."
                    ),
                ],
            ),
        ]
    )


# On prépare un graphique temporel à partir des observations enregistrées.
def timeline_chart(result, measure):
    # On garde dans fig le graphique ou la trace go.Figure défini avec les données indiquées.
    fig = go.Figure()
    # Cette branche traite le cas où la condition result.timeline.empty n’est pas remplie.
    if not result.timeline.empty:
        # On parcourt result.timeline.groupby('Vignoble', sort=True) en gardant aussi sa position dans
        # (i, (v, g)) ; le comptage commence à zéro.
        for i, (v, g) in enumerate(result.timeline.groupby("Vignoble", sort=True)):
            # Order by state chronology, not a mutable label or a textual ID.
            vals = [
                None if pd.isna(x) else int(x)
                for x in pd.to_numeric(
                    g.get(measure, pd.Series(None, index=g.index, dtype=object)),
                    # On définit ce que la conversion fera des valeurs invalides, au lieu de laisser ce
                    # cas implicite.
                    errors="coerce",
                )
            ]
            # On appelle fig.add_trace avec go.Scatter(x=list(range(1, len(g) + 1)), y=vals,
            # mode='lines+markers', name=v, line={'col….
            fig.add_trace(
                go.Scatter(
                    x=list(range(1, len(g) + 1)),
                    y=vals,
                    mode="lines+markers",
                    # On fournit le nom en cours via le paramètre name de cet appel.
                    name=v,
                    line={"color": COLORS[i % len(COLORS)], "width": 3},
                    marker={"size": 9},
                    connectgaps=False,
                    customdata=g[
                        ["Observation NAS", "Croisement Excel / NAS", "Version Excel"]
                    ].values,
                    hoverlabel={
                        # On associe la clé 'bgcolor' à cette valeur dans cet objet.
                        "bgcolor": "#fff",
                        # On associe la clé 'font' à cette valeur dans cet objet.
                        "font": {"color": "#172b24"},
                        # On associe la clé 'bordercolor' à cette valeur dans cet objet.
                        "bordercolor": "#172b24",
                    },
                    hovertemplate="<b>"
                    + v
                    + " · "
                    + measure
                    + "</b><br>NAS : %{customdata[0]}<br>Croisement : %{customdata[1]}<br>Version Excel : %{customdata[2]}<br><b>Quantité : %{y}</b><extra></extra>",
                )
            )
    # On choisit la valeur de max_points selon ce test : la condition result.timeline.empty n’est pas
    # remplie. Les deux résultats possibles restent définis explicitement ici.
    max_points = (
        int(result.timeline.groupby("Vignoble").size().max())
        if not result.timeline.empty
        else 0
    )
    # On appelle fig.update_layout sans argument positionnel.
    fig.update_layout(
        template="plotly_white",
        height=360,
        margin={"l": 45, "r": 20, "t": 12, "b": 50},
        paper_bgcolor="#fff",
        plot_bgcolor="#fff",
        font={"family": "Arial", "color": "#243f31"},
        xaxis={
            # On associe la clé 'title' à cette valeur dans cet objet.
            "title": "États de chaque vignoble, du plus ancien au plus récent · dates au survol et dans le tableau",
            # On associe la clé 'tickmode' à cette valeur dans cet objet.
            "tickmode": "array",
            # On associe la clé 'tickvals' à cette valeur dans cet objet.
            "tickvals": list(range(1, max_points + 1)),
            # On associe la clé 'ticktext' à cette valeur dans cet objet.
            "ticktext": [f"État {i}" for i in range(1, max_points + 1)],
        },
        yaxis={"title": measure, "rangemode": "tozero"},
        legend={"orientation": "h", "y": -0.35},
        hoverlabel={
            # On associe la clé 'bgcolor' à cette valeur dans cet objet.
            "bgcolor": "#fff",
            # On associe la clé 'font' à cette valeur dans cet objet.
            "font": {"color": "#172b24"},
            # On associe la clé 'bordercolor' à cette valeur dans cet objet.
            "bordercolor": "#172b24",
        },
    )
    # On fournit à l’appelant le composant html.Section avec le contenu et les propriétés indiqués.
    return html.Section(
        [
            html.H3("Évolution des volumes · " + measure),
            html.P(
                "Chaque courbe suit un vignoble. Les dates peuvent différer entre vignobles ; un état absent n’est pas remplacé par zéro. Les volumes de livrables comptent des passages uniques satisfaisant le critère, pas des fichiers ni des acquisitions.",
                # On rattache ce composant aux règles CSS de cette classe.
                className="table-help",
            ),
            dcc.Graph(figure=fig, config={"displayModeBar": False}, responsive=True),
        ],
        # On rattache ce composant aux règles CSS de cette classe.
        className="panel",
    )


# On prépare un bloc de présentation pour cet indicateur.
def stat(title, value, note, denominator=None):
    # On choisit la valeur de ratio selon ce test : denominator est renseigné (différent de None). Les
    # deux résultats possibles restent définis explicitement ici.
    ratio = (
        (
            f"{100 * value / denominator:.1f} % des éléments comparés"
            if denominator
            else "Part non calculable"
        )
        if denominator is not None
        else ""
    )
    # On fournit à l’appelant le composant html.Div avec le contenu et les propriétés indiqués.
    return html.Div(
        [
            html.Span(title, className="metric-label"),
            html.Strong(str(value), className="metric-value"),
            html.Span(ratio, className="metric-ratio"),
            html.Span(note, className="metric-subtitle"),
        ],
        # On rattache ce composant aux règles CSS de cette classe.
        className="metric-card static-card",
    )


# On prépare les composants de résultat de la comparaison demandée.
def evolution_results(
    store, vineyard, mode, dates, family, kind, measure, table_panel, section
):
    # On garde dans result le résultat de comparaison préparé pour l’état stocké du dashboard.
    result = comparison_for_store(store, vineyard, mode, dates)
    # Cette branche traite le cas où la condition result.comparable n’est pas remplie.
    if not result.comparable:
        # On garde dans unavailable le composant html.Section avec le contenu et les propriétés
        # indiqués.
        unavailable = html.Section(
            [
                html.H3(result.headline()),
                warning_list(result),
                html.P(
                    "Aucun compteur de changement n’est affiché : une comparaison impossible ne signifie pas zéro changement."
                ),
            ],
            # On rattache ce composant aux règles CSS de cette classe.
            className="panel evolution-summary",
        )
        # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return (
            unavailable,
            html.P("Volumes comparés non disponibles.", className="empty-state"),
            html.P(
                # On rattache ce composant aux règles CSS de cette classe.
                "Aucun détail calculable pour cette sélection.", className="empty-state"
            ),
        )
    # On garde dans c la valeur renvoyée par result.counts.
    c = result.counts()
    # On importe json. On lit ou écrit les objets et manifestes au format JSON.
    import json

    # On indexe denominators par kind ; chaque clé sera associée à sum((json.loads(e)[1] == kind for e
    # in result.examined_entities)). Une même clé ne peut garder qu’une valeur.
    denominators = {
        kind: sum(json.loads(e)[1] == kind for e in result.examined_entities)
        for kind in ["acquisition", "passage", "association"]
    }
    # On garde dans details une copie de result.details pour travailler sur cet objet séparément.
    details = result.details.copy()
    # On vérifie ce cas avant la suite : family diffère du texte 'Toutes'.
    if family != "Toutes":
        # On sélectionne dans details les éléments désignés par details['Famille'].eq(family) ; details
        # recevra cette sélection.
        details = details[details["Famille"].eq(family)]
    # On vérifie ce cas avant la suite : kind diffère du texte 'Tous'.
    if kind != "Tous":
        # On sélectionne dans details les éléments désignés par details['Type'].eq(kind) ; details
        # recevra cette sélection.
        details = details[details["Type"].eq(kind)]
    # On garde dans details la valeur renvoyée par details.drop.
    details = details.drop(columns=["_entity"], errors="ignore")
    # On garde dans options les options de sélection des lots disponibles.
    options = batch_options(frames_of(store), vineyard)
    # On choisit la valeur de chosen selon ce test : mode diffère du texte 'selected'. Les deux
    # résultats possibles restent définis explicitement ici.
    chosen = (
        options[:2]
        if mode != "selected"
        else [o for o in options if o["value"] in set(dates or [])]
    )
    # On garde dans applied_dates le texte formé en réunissant les éléments avec ' → ' comme
    # séparateur.
    applied_dates = " → ".join(o["label"].split(" ⇒ ")[0] for o in reversed(chosen))
    # On garde dans headline le composant html.Section avec le contenu et les propriétés indiqués.
    headline = html.Section(
        [
            html.P("Scans comparés : " + applied_dates, className="applied-dates"),
            html.H3(result.headline()),
            html.P(
                "Les changements sont recherchés entre chaque état successif sélectionné. Un élément modifié puis revenu à sa valeur initiale reste donc identifiable. Les compteurs dédupliquent les éléments sur toute la sélection.",
                # On rattache ce composant aux règles CSS de cette classe.
                className="muted",
            ),
            warning_list(result),
        ],
        # On rattache ce composant aux règles CSS de cette classe.
        className="panel evolution-summary",
    )
    # On garde dans cards le composant html.Div avec le contenu et les propriétés indiqués.
    cards = html.Div(
        [
            stat(
                "Acquisitions avec changement",
                c["acquisitions"],
                "Tous types de changements, commentaires inclus",
                denominators["acquisition"],
            ),
            stat(
                "Passages avec changement",
                c["passages"],
                "Critères de livrables et contrôles enregistrés",
                denominators["passage"],
            ),
            stat(
                "Commentaires Excel modifiés",
                c["comments"],
                "Sous-ensemble séparé ; pas un changement de traitement",
                denominators["acquisition"],
            ),
            stat(
                "Rattachements modifiés",
                c["relationships"],
                "Liens exacts acquisition · parcelle · passage",
                denominators["association"],
            ),
        ],
        # On rattache ce composant aux règles CSS de cette classe.
        className="metrics-grid evolution-cards",
    )
    # Rates use separate grains; do not divide unique acquisitions by a sum of
    # acquisitions + passage files or multiple transition counts.
    rows = []
    # On parcourt [('Acquisition', 'acquisition', c['acquisitions']), ('Passage', 'passage'… ; (typ,
    # key, n) désigne l’élément courant à chaque passage dans la boucle.
    for typ, key, n in [
        ("Acquisition", "acquisition", c["acquisitions"]),
        ("Passage", "passage", c["passages"]),
        ("Rattachement", "association", c["relationships"]),
    ]:
        # On importe json. On lit ou écrit les objets et manifestes au format JSON.
        import json

        # On garde dans denominator la somme des valeurs de (json.loads(e)[1] == key for e in
        # result.examined_entities).
        denominator = sum(json.loads(e)[1] == key for e in result.examined_entities)
        # On ajoute {'Type': typ, 'Éléments distincts comparés (union)': denominator, 'Éléments
        # modifiés': n,… à la fin de rows ; les éléments précédents restent conservés.
        rows.append(
            {
                # On associe la clé 'Type' à cette valeur dans cet objet.
                "Type": typ,
                "Éléments distincts comparés (union)": denominator,
                "Éléments modifiés": n,
                "Part modifiée": f"{100 * n / denominator:.1f} %"
                if denominator
                else "Non calculable",
            }
        )
    # On rassemble dans visible_cols les 12 éléments explicitement indiqués, en conservant leur
    # structure.
    visible_cols = [
        "Vignoble",
        "Type",
        "Acquisition",
        "Parcelle",
        "Passage",
        "Famille",
        "Information",
        "Avant",
        "Après",
        "Observation précédente",
        "Observation récente",
        "Lecture prudente",
    ]
    # On garde dans timeline la valeur renvoyée par result.timeline.drop.
    timeline = result.timeline.drop(columns=["_time"], errors="ignore")
    # On garde dans status_changes la valeur renvoyée par
    # result.details[result.details['Famille'].isin(['Excel · statuts', 'Excel · catégories'])].drop.
    status_changes = result.details[
        result.details["Famille"].isin(["Excel · statuts", "Excel · catégories"])
    # On décrit les colonnes à présenter, distinctes des lignes de données.
    ].drop(columns=["_entity"], errors="ignore")
    # On garde dans summary le composant html.Div avec le contenu et les propriétés indiqués.
    summary = html.Div(
        [
            headline,
            cards,
            section(
                "Importance des changements · détail du calcul",
                [
                    table_panel(
                        pd.DataFrame(rows),
                        "evolution-rates",
                        "Éléments comparés et parts modifiées",
                        intro="Union des éléments recensés dans les paires effectivement comparables. Les trois types ne doivent pas être additionnés. Un volume net stable peut masquer des changements.",
                    )
                ],
            ),
        ]
    )
    # On garde dans volumes le composant html.Div avec le contenu et les propriétés indiqués.
    volumes = html.Div(
        [
            timeline_chart(result, measure),
            section(
                "Consulter les volumes, dates et références",
                [table_panel(timeline, "evolution-timeline", "États comparés")],
            ),
        ]
    )
    # On garde dans detail le composant html.Div avec le contenu et les propriétés indiqués.
    detail = html.Div(
        [
            table_panel(
                details,
                "evolution-diff",
                "Détail des changements · avant / après",
                visible_cols,
                f"{len(details)} modification(s) de champ ou de présence avec les filtres de détail. Un même élément peut apparaître plusieurs fois. Export CSV et copie suivent les lignes filtrées.",
            ),
            section(
                "Transitions de statuts et de catégories Excel",
                [
                    table_panel(
                        status_changes,
                        "evolution-status",
                        "Statuts et catégories modifiés",
                        visible_cols,
                    )
                ],
            ),
            section(
                "Couverture et règles de lecture",
                [
                    table_panel(
                        result.coverage,
                        "evolution-coverage",
                        "Paires effectivement comparées",
                    ),
                    html.P(
                        "« Non recensé » signifie absent de cet état enregistré, pas supprimé du NAS. Une erreur ou une valeur inconnue n’est jamais assimilée à une absence confirmée. Une nouvelle date ou un nouvel identifiant d’exécution ne compte pas comme changement métier."
                    ),
                    html.P(
                        "Vitimap et Vitiparcel : critères techniques enregistrés, sans preuve de validation qualité, de commande ou de livraison client. Les modifications de fichiers non observées par le pipeline ne peuvent pas être détectées par ce dashboard."
                    ),
                    html.P(
                        "Les versions Excel et les références NAS sont conservées pour chaque comparaison. Une différence de résultats ne permet pas, à elle seule, de distinguer un changement des sources d’un changement des règles du pipeline. L’historique n’expose pas une empreinte complète de toutes les règles."
                    ),
                    html.P(
                        "Le mode historique des trois autres onglets restitue une exécution conservée, pas l’état exact des pointeurs actifs de la base à une heure passée. Il ne complète jamais un vignoble manquant avec des données d’aujourd’hui."
                    ),
                ],
            ),
        ]
    )

    # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return summary, volumes, detail
