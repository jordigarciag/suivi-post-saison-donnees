# Lecture du fichier — Préparation des données pour le dashboard, depuis PostgreSQL ou le mode fictif explicite.
# On conserve la différence entre vrai, faux et inconnu. Une erreur de lecture ne doit pas devenir
# une absence de livrable.
#

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On décrit les champs d’un objet de données sans écrire toute sa construction à la main.
from dataclasses import dataclass
# On rend disponibles Any depuis typing, pour les appels de ce fichier.
from typing import Any
# On utilise les règles du fuseau demandé, notamment lors des changements d’heure.
from zoneinfo import ZoneInfo

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd
# On rend disponibles DatabaseClient depuis database, pour les appels de ce fichier.
from database import DatabaseClient
# On rend disponibles build_mock_state depuis mock_data, pour les appels de ce fichier.
from mock_data import build_mock_state

# On garde dans TZ la valeur renvoyée par os.getenv pour 'DASHBOARD_TIMEZONE'.
TZ = os.getenv("DASHBOARD_TIMEZONE", "Europe/Paris")
# Ces vues décrivent les bilans courants consultés par le dashboard.
CURRENT_VIEWS = [
    "reconciliation_vineyard_current",
    "reconciliation_freshness_current",
    "reconciliation_acquisition_current",
    "reconciliation_passage_current",
]
# Ces autres vues permettent de retrouver les observations déjà conservées pour les comparaisons.
HISTORY_VIEWS = [
    "reconciliation_vineyard_history",
    "reconciliation_acquisition_history",
    "reconciliation_passage_history",
    "reconciliation_association_history",
]


@dataclass
class DashboardState:
    # On déclare le champ mode avec le type attendu str ; sa valeur sera fournie lors de la
    # construction de l’objet.
    mode: str
    # On déclare le champ status_message avec le type attendu str ; sa valeur sera fournie lors de la
    # construction de l’objet.
    status_message: str
    # On déclare le champ frames avec le type attendu dict[str, pd.DataFrame] ; sa valeur sera fournie
    # lors de la construction de l’objet.
    frames: dict[str, pd.DataFrame]


# On accepte plusieurs écritures de vrai et faux ; une valeur non reconnue reste inconnue (None), pas
# fausse.
def _to_bool(value: Any) -> bool | None:
    # On traite d’abord les valeurs manquantes pour ne pas tenter des convertir en vrai ou faux.
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None
    # Si la valeur est déjà un booléen, on garde sa signification telle quelle.
    if isinstance(value, bool):
        # On remet la valeur reçue à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return value
    # On garde dans text la version en minuscules de str(value).strip().
    text = str(value).strip().lower()
    # Ces écritures sont acceptées comme une preuve positive dans cette conversion.
    if text in {"true", "t", "1", "1.0", "yes", "oui", "__yes__"}:
        # On renvoie True comme résultat explicite de cette branche.
        return True
    # Ces écritures sont explicitement négatives ; on ne les confond pas avec une cellule vide.
    if text in {"false", "f", "0", "0.0", "no", "non", "__no__"}:
        # On renvoie False comme résultat explicite de cette branche.
        return False
    # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
    return None


# On applique la conversion sur une colonne complète ; si elle manque, on prépare des valeurs
# inconnues.
def boolean(df, field):
    # On fournit à l’appelant les valeurs de df.get(field, pd.Series(None, index=df.index,
    # dtype=object)) transformées par la fonction ou la correspondance indiquée.
    return df.get(field, pd.Series(None, index=df.index, dtype=object)).map(_to_bool)


# On sélectionne les valeurs explicitement reconnues comme vraies.
def yes(df, field):
    # On fournit à l’appelant le masque d’égalité calculé pour boolean(df, field).
    return boolean(df, field).eq(True)


# On sélectionne les valeurs explicitement reconnues comme fausses ; une valeur inconnue n’est pas
# une preuve d’absence.
def no(df, field):
    # On fournit à l’appelant le masque d’égalité calculé pour boolean(df, field).
    return boolean(df, field).eq(False)


# On prépare un libellé de date dans le fuseau du dashboard ; la valeur enregistrée reste distincte
# du texte affiché.
def format_time(value, date_only=False):
    # On traite d’abord les valeurs manquantes pour ne pas tenter des convertir en vrai ou faux.
    if value is None or str(value) in {"", "NaT", "None"}:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Non renseignée"
    # On tente ce bloc et on traite séparément les erreurs prévues : (ValueError, TypeError).
    try:
        # On garde dans ts la valeur renvoyée par pd.Timestamp.
        ts = pd.Timestamp(value)
        # On reconnaît aussi les valeurs manquantes propres à pandas, comme NaN ; elles ne doivent pas
        # s’afficher comme le texte "nan".
        if pd.isna(ts):
            # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
            return "Non renseignée"
        # PostgreSQL timestamptz is supplied in UTC. Naive source timestamps are
        # interpreted as UTC, never as the browser's or workstation's local time.
        if ts.tzinfo is None:
            # On garde dans ts la valeur renvoyée par ts.tz_localize pour 'UTC'.
            ts = ts.tz_localize("UTC")
        # On garde dans local la valeur renvoyée par ts.tz_convert.
        local = ts.tz_convert(ZoneInfo(TZ))
        # On fournit à l’appelant la date local mise en forme selon le modèle indiqué.
        return local.strftime("%d/%m/%Y" if date_only else "%d/%m/%Y à %H h %M")
    except (ValueError, TypeError):
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Non renseignée"


# On prépare une date compacte pour les listes tout en conservant les règles du fuseau horaire.
def format_scan_time(value, date_only=False):
    """Compact scan labels without changing timestamps or their timezone."""
    # On fournit à l’appelant le résultat du remplacement demandé sur format_time(value, date_only).
    return format_time(value, date_only).replace(" h ", "h")


# On harmonise les libellés de périmètre pour pouvoir les comparer entre sources.
def _normalise_perimeter(value):
    # On choisit la valeur de text selon ce test : la valeur reçue vaut None ou le contrôle
    # pd.isna(value) est positif. Les deux résultats possibles restent définis explicitement ici.
    text = "" if value is None or pd.isna(value) else str(value).strip()
    # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
    # enregistré dans les données sources.
    lower = text.casefold()
    # On vérifie ce cas avant la suite : le texte 'test' appartient à lower.
    if "test" in lower:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Test"
    # Cette branche traite le cas où le texte 'bloqu' appartient à lower ou le texte 'attente'
    # appartient à lower ou lower correspond au texte 'autre'.
    if "bloqu" in lower or "attente" in lower or lower == "autre":
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Bloqué"
    # On vérifie ce cas avant la suite : lower appartient à {'production', 'prod'}.
    if lower in {"production", "prod"}:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Production"
    # On remet text or 'Inconnu' à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return text or "Inconnu"


# On remet les champs nécessaires au même niveau pour préparer le tableau de consultation.
def _flatten_row(row):
    # On garde dans result un nouveau dictionnaire construit avec les valeurs indiquées (la copie reste
    # superficielle).
    result = dict(row)
    # On garde dans payload le champ 'payload' de row, ou None si la clé est absente.
    payload = row.get("payload")
    # On réserve cette branche à payload lorsqu’il est de type str.
    if isinstance(payload, str):
        # On tente ce bloc et on traite séparément les erreurs prévues : (ValueError, TypeError).
        try:
            # On décodu texte JSON en objets Python ; les contrôles de structure viennent
            # ensuite, car un JSON lisible n’est pas forcément un lot valide.
            payload = json.loads(payload)
        except (ValueError, TypeError):
            # On initialise payload à None : aucune valeur n’a encore été retenue ici.
            payload = None
    # On réserve cette branche à payload lorsqu’il est de type dict.
    if isinstance(payload, dict):
        # On parcourt les couples (key, value) de payload : on garde ensemble la clé et sa valeur au
        # lieu des traiter dans deux listes séparées.
        for key, value in payload.items():
            # Cette branche traite le cas où la clé de l’élément ne figure pas dans le résultat de
            # cette opération ou result[key] vaut None.
            if key not in result or result[key] is None:
                # On garde la valeur reçue sous le nom result[key] ; cette affectation ne copie pas à
                # elle seule un objet mutable.
                result[key] = value
    # Cette branche traite le cas où la condition result.get('vineyard_name') n’est pas remplie et le
    # champ 'Vineyard' du résultat de cette opération est évalué comme vrai.
    if not result.get("vineyard_name") and result.get("Vineyard"):
        # On récupère le domaine concerné dans result et on le garde dans result['vineyard_name'] pour
        # la suite.
        result["vineyard_name"] = result["Vineyard"]
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On transforme les lignes lues dans la vue demandée en tableau pandas.
def _load_view(client, name):
    # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
    return pd.DataFrame([_flatten_row(r) for r in client.fetch_rows(name)])


# On choisit explicitement entre démonstration fictive et lecture PostgreSQL ; une panne ne déclenche
# pas de repli fictif.
def load_dashboard_state(force_mock=False):
    # Cette branche traite le cas où force_mock est évalué comme vrai ou
    # os.getenv('DASHBOARD_USE_MOCK') correspond au texte '1'.
    if force_mock or os.getenv("DASHBOARD_USE_MOCK") == "1":
        # On fournit à l’appelant la valeur renvoyée par DashboardState pour 'mock'.
        return DashboardState(
            "mock",
            "Démonstration — données fictives, aucune lecture PostgreSQL.",
            build_mock_state(),
        )
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On garde dans client la valeur renvoyée par DatabaseClient.
        client = DatabaseClient()
        # On garde dans health la valeur renvoyée par client.healthcheck.
        health = client.healthcheck()
        # On répartit les valeurs renvoyées par client.fetch_bundle entre (bundle, missing) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        bundle, missing = client.fetch_bundle(CURRENT_VIEWS, HISTORY_VIEWS)
        # On indexe frames par name ; chaque clé sera associée à pd.DataFrame([_flatten_row(r) for r in
        # rows]). Une même clé ne peut garder qu’une valeur.
        frames = {
            name: pd.DataFrame([_flatten_row(r) for r in rows])
            for name, rows in bundle.items()
        }
    except Exception:
        # Ne pas afficher les paramètres techniques d’une connexion dans l’interface.
        return DashboardState(
            "unavailable",
            "Données PostgreSQL indisponibles. Aucun indicateur métier affiché. Code : DATABASE_UNAVAILABLE.",
            {},
        )
    # On garde dans warnings une liste matérialisée à partir de missing.
    warnings = list(missing)
    # On prépare status avec cette expression pour l’utiliser dans la suite du traitement.
    status = (
        f"Source : PostgreSQL · {health['database_name']} · consultation uniquement."
    )
    # Cette branche traite le cas où les avertissements est évalué comme vrai.
    if warnings:
        # On ajoute ' Historique partiellement indisponible : ' + ', '.join(warnings) à status et on
        # conserve ce nouvel état pour la suite.
        status += " Historique partiellement indisponible : " + ", ".join(warnings)
    # On fournit à l’appelant la valeur renvoyée par DashboardState pour 'database'.
    return DashboardState("database", status, frames)


# On choisit la première valeur renseignée selon l’ordre prévu, sans confondre automatiquement faux
# et vide.
def coalesce(df, names, default=None):
    # On garde dans result une série pandas avec les valeurs et l’index fournis.
    result = pd.Series(None, index=df.index, dtype=object)
    # On parcourt names ; name désigne l’élément courant à chaque passage dans la boucle.
    for name in names:
        # On vérifie ce cas avant la suite : le nom en cours appartient au tableau de travail.
        if name in df:
            # On combine ces masques avec & pour construire valid ; les parenthèses gardent les
            # comparaisons regroupées.
            valid = df[name].notna() & df[name].astype(str).str.strip().ne("")
            # On réunit ces masques avec | pour construire missing ; les parenthèses gardent les
            # comparaisons regroupées.
            missing = result.isna() | result.astype(str).str.strip().eq("")
            # On sélectionne dans df.loc les éléments désignés par (missing & valid, name) ;
            # result.loc[missing & valid] recevra cette sélection.
            result.loc[missing & valid] = df.loc[missing & valid, name]
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return result.fillna(default) if default is not None else result


# On prépare les valeurs et indicateurs des acquisitions pour la consultation.
def prepare_acquisitions(frame):
    # Cette branche traite le cas où frame vaut None ou frame est un tableau vide.
    if frame is None or frame.empty:
        # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
        return pd.DataFrame()
    # On garde dans df une copie de frame pour travailler sur cet objet séparément.
    df = frame.copy()
    # On garde dans df['vineyard_name'] les valeurs retenues parmi les colonnes candidates dans leur
    # ordre de priorité.
    df["vineyard_name"] = coalesce(df, ["vineyard_name", "Vineyard"], "Inconnu")
    # On garde dans df['acquisition_id_normalise'] les valeurs retenues parmi les colonnes candidates
    # dans leur ordre de priorité.
    df["acquisition_id_normalise"] = coalesce(
        df, ["acquisition_id_normalise", "acquisition_id_base"], ""
    )
    # Only Excel-derived perimeter fields, never a technical processing category.
    df["perimeter_normalized"] = coalesce(
        df,
        [
            "perimeter_normalized",
            "recorded_excel_perimeter",
            "excel_perimeter",
            "perimeter",
        ],
    ).map(_normalise_perimeter)
    # On parcourt ['found_in_processing_live', 'processing_has_webp_images', 'has_technical… ; field
    # désigne l’élément courant à chaque passage dans la boucle.
    for field in [
        "found_in_processing_live",
        "processing_has_webp_images",
        "has_technical_error",
        "excel_needs_review",
        "excel_acquisition_timestamp_issue",
        "raw_evidence_review_required",
        "processing_decision_required",
        "stocks_json_exists",
        "found_in_passage_mapping",
    ]:
        # On garde dans df[field] la conversion booléenne définie par ce module, avec sa gestion des
        # valeurs inconnues.
        df[field] = boolean(df, field)
    # On garde dans processing la conversion booléenne définie par ce module, avec sa gestion des
    # valeurs inconnues.
    processing = boolean(df, "found_in_processing_live")
    # On garde dans webp la conversion booléenne définie par ce module, avec sa gestion des valeurs
    # inconnues.
    webp = boolean(df, "processing_has_webp_images")
    # On construit df['treated_technical'] comme une liste à partir de True if a is True and b is True
    # else False if a is False or b is…, pour chaque (a, b) de zip(processing, webp).
    df["treated_technical"] = [
        True if a is True and b is True else False if a is False or b is False else None
        for a, b in zip(processing, webp)
    ]
    # On garde dans production le masque d’égalité calculé pour df['perimeter_normalized'].
    production = df["perimeter_normalized"].eq("Production")
    # On rassemble dans review_fields les 4 éléments explicitement indiqués, en conservant leur
    # structure.
    review_fields = [
        "excel_needs_review",
        "excel_acquisition_timestamp_issue",
        "raw_evidence_review_required",
        "processing_decision_required",
    ]
    # On garde dans business_review une série pandas avec les valeurs et l’index fournis.
    business_review = pd.Series(False, index=df.index)
    # On parcourt review_fields ; field désigne l’élément courant à chaque passage dans la boucle.
    for field in review_fields:
        # On réunit les valeurs ou masques dans business_review avec |, en conservant le résultat dans
        # ce même emplacement.
        business_review |= yes(df, field)
    # A known Test/Bloqué is not a new business anomaly; independent technical
    # errors stay explicit and accessible across all categories.
    df["needs_verification"] = (production & business_review) | yes(
        df, "has_technical_error"
    )
    # On combine ces masques avec & pour construire df['treated_production'] ; les parenthèses gardent
    # les comparaisons regroupées.
    df["treated_production"] = production & yes(df, "treated_technical")
    # On combine ces masques avec & pour construire df['treated_outside_production'] ; les parenthèses
    # gardent les comparaisons regroupées.
    df["treated_outside_production"] = ~production & yes(df, "treated_technical")
    # On combine ces masques avec & pour construire df['production_incomplete'] ; les parenthèses
    # gardent les comparaisons regroupées.
    df["production_incomplete"] = production & no(df, "treated_technical")
    # On combine ces masques avec & pour construire df['treatment_unknown'] ; les parenthèses gardent
    # les comparaisons regroupées.
    df["treatment_unknown"] = production & df["treated_technical"].isna()
    # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return df


# On évite de compter plusieurs lignes comme plusieurs acquisitions lorsqu’elles désignent le même
# élément logique.
def unique_acquisitions(df):
    # On traite à part le tableau df lorsqu’il est vide.
    if df.empty:
        # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont
        # plus parcourues.
        return df
    # On rassemble dans keys les 2 éléments explicitement indiqués, en conservant leur structure.
    keys = ["vineyard_name", "acquisition_id_normalise"]
    # Current acquisition views are expected to be unique. Only exact repeated
    # records are removed; conflicting rows raise a visible diagnostic.
    df = df.drop_duplicates(
        subset=[
            c
            for c in df.columns
            if c != "payload"
            # On exige aussi que la condition df[c].map(lambda v: isinstance(v, (dict, list))).any()
            # n’est pas remplie.
            and not df[c].map(lambda v: isinstance(v, (dict, list))).any()
        ]
    )
    # Deux lignes différentes portent la même clé : les compter telles quelles pourrait gonfler les
    # indicateurs.
    if df.duplicated(keys).any():
        # On interrompt cette branche avec ValueError.
        raise ValueError(
            "Plusieurs lignes différentes pour une même acquisition : vérifier la granularité de reconciliation_acquisition_current avant de compter."
        )
    # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return df


# On prépare les valeurs et indicateurs des passages pour la consultation.
def prepare_passages(frame):
    # Cette branche traite le cas où frame vaut None ou frame est un tableau vide.
    if frame is None or frame.empty:
        # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
        return pd.DataFrame()
    # On garde dans df une copie de frame pour travailler sur cet objet séparément.
    df = frame.copy()
    # On garde dans df['vineyard_name'] les valeurs retenues parmi les colonnes candidates dans leur
    # ordre de priorité.
    df["vineyard_name"] = coalesce(df, ["vineyard_name", "Vineyard"], "Inconnu")
    # On parcourt ['vitimap_created', 'vitiparcel_technical_criterion_satisfied', 'has_non_… ; name
    # désigne l’élément courant à chaque passage dans la boucle.
    for name in [
        "vitimap_created",
        "vitiparcel_technical_criterion_satisfied",
        "has_non_healthy_status",
        "stocks_json_exists",
        "passage_created",
        "passage_outputs_verifiable",
    ]:
        # On garde dans df[name] la conversion booléenne définie par ce module, avec sa gestion des
        # valeurs inconnues.
        df[name] = boolean(df, name)
    # Missing criterion in the mart payload: derive it from its two documented
    # inputs, NOT from non-healthy status alone or vitiparcel_created.
    explicit = boolean(df, "vitiparcel_technical_criterion_satisfied")
    # On garde dans verified la conversion booléenne définie par ce module, avec sa gestion des valeurs
    # inconnues.
    verified = boolean(df, "vitiparcel_ready_verifiable")
    # On garde dans stored la conversion booléenne définie par ce module, avec sa gestion des valeurs
    # inconnues.
    stored = boolean(df, "vitiparcel_ready_for_delivery")
    # On garde dans explicit la valeur renvoyée par explicit.where.
    explicit = explicit.where(explicit.notna(), stored.where(verified.eq(True)))
    # On garde dans stocks la conversion booléenne définie par ce module, avec sa gestion des valeurs
    # inconnues.
    stocks = boolean(df, "stocks_json_exists")
    # On garde dans unhealthy la conversion booléenne définie par ce module, avec sa gestion des
    # valeurs inconnues.
    unhealthy = boolean(df, "has_non_healthy_status")
    # On garde dans derived une série pandas avec les valeurs et l’index fournis.
    derived = pd.Series(
        [
            True
            if a is True and b is True
            else False
            if a is False or b is False
            else None
            for a, b in zip(stocks, unhealthy)
        ],
        index=df.index,
        # On impose les types lus ou construits pour éviter une interprétation automatique non
        # souhaitée.
        dtype=object,
    )
    # On garde dans df['vitiparcel_technical_criterion_satisfied'] la valeur renvoyée par
    # explicit.where.
    df["vitiparcel_technical_criterion_satisfied"] = explicit.where(
        explicit.notna(), derived
    )
    # Recorded non-verifiability takes precedence over a misleading FALSE or a
    # reconstructed criterion. Same policy for current and historical snapshots.
    if "vitiparcel_ready_verifiable" in frame:
        # On initialise df.loc[~verified.eq(True), 'vitiparcel_technical_criterion_satis… à None :
        # aucune valeur n’a encore été retenue ici.
        # On autorise explicitement True, False et None dans cette colonne. Un type bool strict
        # ne peut pas représenter une observation inconnue sans conversion implicite de pandas.
        df["vitiparcel_technical_criterion_satisfied"] = df[
            "vitiparcel_technical_criterion_satisfied"
        ].astype(object)
        df.loc[~verified.eq(True), "vitiparcel_technical_criterion_satisfied"] = None
    # On garde dans df['passage_business_category'] les valeurs retenues parmi les colonnes candidates
    # dans leur ordre de priorité.
    df["passage_business_category"] = coalesce(
        df, ["passage_business_category", "recorded_passage_category"]
    )
    # On construit keys comme une liste à partir de c, pour chaque c de ['vineyard_name',
    # 'parcel_name', 'passage_name'] en ne gardant que les éléments qui passent le filtre.
    keys = [c for c in ["vineyard_name", "parcel_name", "passage_name"] if c in df]
    # On vérifie ce cas avant la suite : len(keys) correspond à 3.
    if len(keys) == 3:
        # On retire les répétitions selon les colonnes choisies, pas selon une ressemblance visuelle.
        df = df.drop_duplicates(
            subset=[
                c
                for c in df.columns
                if c != "payload"
                # On exige aussi que la condition df[c].map(lambda v: isinstance(v, (dict,
                # list))).any() n’est pas remplie.
                and not df[c].map(lambda v: isinstance(v, (dict, list))).any()
            ]
        )
        # Un passage ne doit pas être compté deux fois à cause de lignes contradictoires dans la
        # vue.
        if df.duplicated(keys).any():
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                "Plusieurs lignes différentes pour un passage : vérifier la vue courante avant de compter."
            )
    # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return df


# On prépare la provenance et les dates utiles pour juger l’ancienneté des observations.
def prepare_freshness(frame):
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return frame.copy() if frame is not None else pd.DataFrame()


# On prépare la liste des domaines disponibles dans les tableaux reçus.
def list_vineyards(frames):
    # On garde dans names un ensemble vide, qui servira à repérer les valeurs déjà rencontrées.
    names = set()
    # On parcourt frames.values() ; df désigne l’élément courant à chaque passage dans la boucle.
    for df in frames.values():
        # On vérifie ce cas avant la suite : le texte 'vineyard_name' appartient au tableau de
        # travail.
        if "vineyard_name" in df:
            # On complète cet ensemble avec les éléments fournis ; les doublons restent éliminés, sans
            # notion de clé à remplacer.
            names.update(df["vineyard_name"].dropna().astype(str))
    # On fournit à l’appelant les éléments triés de names dans une nouvelle liste.
    return sorted(names)


# On interprète les valeurs structurées reçues sous forme de JSON selon les cas acceptés.
def parse_json(value):
    # On réserve cette branche à value lorsqu’il est de type str.
    if isinstance(value, str):
        # On tente ce bloc et on traite séparément les erreurs prévues : (TypeError, ValueError).
        try:
            # On décodu texte JSON en objets Python ; les contrôles de structure viennent
            # ensuite, car un JSON lisible n’est pas forcément un lot valide.
            return json.loads(value)
        except (TypeError, ValueError):
            # On renvoie ces 0 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return []
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return value if isinstance(value, (list, dict)) else []


# On vérifie si les informations disponibles confirment le rattachement au passage.
def passage_linked(row, acquisitions):
    # On choisit la valeur de aq selon ce test : la condition acquisitions.empty n’est pas remplie. Les
    # deux résultats possibles restent définis explicitement ici.
    aq = (
        acquisitions[acquisitions["vineyard_name"].eq(row.get("vineyard_name"))]
        if not acquisitions.empty
        else acquisitions
    )
    # On traite à part le tableau aq lorsqu’il est vide.
    if aq.empty:
        # On renvoie False comme résultat explicite de cette branche.
        return False
    # On garde dans ids le contenu interprété par le lecteur JSON du projet.
    ids = parse_json(row.get("acquisition_ids_json"))
    # Cette branche traite le cas où ids est du type list et ids est évalué comme vrai et tous les
    # éléments satisfont le test indiqué.
    if isinstance(ids, list) and ids and all(isinstance(x, str) for x in ids):
        # On fournit à l’appelant le résultat indiquant si au moins une valeur de
        # aq['acquisition_id_normalise'].isin(ids) est vraie.
        return aq["acquisition_id_normalise"].isin(ids).any()
    # On parcourt aq.iterrows() ; (_, a) désigne l’élément courant à chaque passage dans la boucle.
    for _, a in aq.iterrows():
        # Cette branche traite le cas où toutes les conditions regroupées ici sont remplies.
        if (
            a.get("passage_name")
            # On exige aussi que a.get('passage_name') correspond à row.get('passage_name').
            and a.get("passage_name") == row.get("passage_name")
            # On exige aussi que le champ 'parcel_name' de a est évalué comme vrai.
            and a.get("parcel_name")
            # On exige aussi que a.get('parcel_name') correspond à row.get('parcel_name').
            and a.get("parcel_name") == row.get("parcel_name")
        ):
            # On renvoie True comme résultat explicite de cette branche.
            return True
        # On garde dans links le contenu interprété par le lecteur JSON du projet.
        links = parse_json(a.get("passage_links_json"))
        # On réserve cette branche à links lorsqu’il est de type list.
        if isinstance(links, list):
            # On parcourt links ; link désigne l’élément courant à chaque passage dans la boucle.
            for link in links:
                # Cette branche traite le cas où link est du type dict et link.get('passage_name')
                # correspond à row.get('passage_name') et link.get('parcel_name') correspond à
                # row.get('parcel_name').
                if (
                    isinstance(link, dict)
                    # On exige aussi que link.get('passage_name') correspond à row.get('passage_name').
                    and link.get("passage_name") == row.get("passage_name")
                    # On exige aussi que link.get('parcel_name') correspond à row.get('parcel_name').
                    and link.get("parcel_name") == row.get("parcel_name")
                ):
                    # On renvoie True comme résultat explicite de cette branche.
                    return True
    # On renvoie False comme résultat explicite de cette branche.
    return False


# On applique la sélection aux tableaux utilisés pour cette consultation.
def filter_frames(acquisitions, passages, freshness, vineyard, perimeter, search):
    # On distribue ces valeurs entre aq, ps, fr, dans l’ordre de l’affectation. Chaque nom reçoit son
    # propre élément.
    aq, ps, fr = acquisitions.copy(), passages.copy(), freshness.copy()
    # Cette branche traite le cas où le domaine concerné est évalué comme vrai et le domaine concerné
    # diffère du texte '__ALL__'.
    if vineyard and vineyard != "__ALL__":
        # On choisit la valeur de aq selon ce test : la condition aq.empty n’est pas remplie. Les deux
        # résultats possibles restent définis explicitement ici.
        aq = aq[aq["vineyard_name"].eq(vineyard)] if not aq.empty else aq
        # On choisit la valeur de ps selon ce test : la condition ps.empty n’est pas remplie. Les deux
        # résultats possibles restent définis explicitement ici.
        ps = ps[ps["vineyard_name"].eq(vineyard)] if not ps.empty else ps
        # On choisit la valeur de fr selon ce test : la condition fr.empty n’est pas remplie et le
        # texte 'vineyard_name' appartient à fr. Les deux résultats possibles restent définis
        # explicitement ici.
        fr = (
            fr[fr["vineyard_name"].eq(vineyard)]
            if not fr.empty and "vineyard_name" in fr
            else fr
        )
    # On retient pour narrowed la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    narrowed = perimeter not in {None, "__ALL__"} or bool((search or "").strip())
    # Cette branche traite le cas où perimeter est évalué comme vrai et perimeter diffère du texte
    # '__ALL__' et la condition aq.empty n’est pas remplie.
    if perimeter and perimeter != "__ALL__" and not aq.empty:
        # On sélectionne dans aq les éléments désignés par aq['perimeter_normalized'].eq(perimeter) ;
        # aq recevra cette sélection.
        aq = aq[aq["perimeter_normalized"].eq(perimeter)]
    # Cette branche traite le cas où le contrôle (search or '').strip() est positif.
    if (search or "").strip():
        # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
        # enregistré dans les données sources.
        needle = search.strip().casefold()

        # On compare la valeur au critère demandé pour ce filtre.
        def matches(df, fields):
            # On garde dans mask une série pandas avec les valeurs et l’index fournis.
            mask = pd.Series(False, index=df.index)
            # On parcourt les champs ; name désigne l’élément courant à chaque passage dans la boucle.
            for name in fields:
                # On vérifie ce cas avant la suite : le nom en cours appartient au tableau de
                # travail.
                if name in df:
                    # On réunit les valeurs ou masques dans mask avec |, en conservant le résultat dans
                    # ce même emplacement.
                    mask |= (
                        df[name]
                        .fillna("")
                        .astype(str)
                        .str.casefold()
                        .str.contains(needle, regex=False)
                    )
            # On remet mask à l’appelant ; les étapes suivantes de cette fonction ne sont plus
            # parcourues.
            return mask

        # On choisit la valeur de aq selon ce test : la condition aq.empty n’est pas remplie. Les deux
        # résultats possibles restent définis explicitement ici.
        aq = (
            aq[
                matches(
                    aq,
                    [
                        "acquisition_id_normalise",
                        "parcel_name",
                        "passage_name",
                        "vineyard_name",
                    ],
                )
            ]
            if not aq.empty
            else aq
        )
        # Cette branche traite le cas où la condition ps.empty n’est pas remplie.
        if not ps.empty:
            # On garde dans direct la valeur renvoyée par matches.
            direct = matches(ps, ["parcel_name", "passage_name", "vineyard_name"])
            # On garde dans linked le résultat de la fonction appliquée aux éléments ou à l’axe indiqué
            # de ps.
            linked = ps.apply(lambda r: passage_linked(r, aq), axis=1)
            # On choisit la valeur de ps selon ce test : perimeter appartient à {None, '__ALL__'}. Les
            # deux résultats possibles restent définis explicitement ici.
            ps = ps[direct | linked] if perimeter in {None, "__ALL__"} else ps[linked]
    # Cette branche traite le cas où narrowed est évalué comme vrai et la condition ps.empty n’est pas
    # remplie et perimeter ne figure pas dans {None, '__ALL__'}.
    if narrowed and not ps.empty and perimeter not in {None, "__ALL__"}:
        # On sélectionne dans ps les éléments désignés par ps.apply(lambda r: passage_linked(r, aq),
        # axis=1) ; ps recevra cette sélection.
        ps = ps[ps.apply(lambda r: passage_linked(r, aq), axis=1)]
    # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return aq, ps, fr


# On regroupe dans METRICS ces champs nommés ; on pourra les retrouver par leur clé plutôt que par leur
# position.
METRICS = {
    # On associe la clé 'all' à cette valeur dans cet objet.
    "all": (
        "Acquisitions recensées",
        "Acquisitions uniques recensées dans le périmètre enregistré, tous statuts confondus avant application des filtres. Ne garantit pas leur présence sur le NAS.",
        "acq",
    ),
    # On renseigne l’appartenance au périmètre Production sous la clé 'production'.
    "production": (
        "Production · Excel",
        "Catégorie Production déduite des informations présentes dans les fichiers Excel de suivi des acquisitions. Ce n’est pas un tag NAS.",
        "acq",
    ),
    # On associe la clé 'treated' à cette valeur dans cet objet.
    "treated": (
        "Production traitée · preuves NAS",
        "Parmi les acquisitions de production : dossier Processing présent ET images WEBP présentes.",
        "acq",
    ),
    # On renseigne la demande de vérification sous la clé 'review'.
    "review": (
        "Vérifications signalées",
        "Production : signal de revue Excel, date, Brut ou décision Processing ; toutes catégories : erreur technique explicite. Un test déclaré seul n’est pas une anomalie.",
        "acq",
    ),
    # On associe la clé 'map' à cette valeur dans cet objet.
    "map": (
        "Vitimap détectés",
        "Passages uniques dont vitimap_created est vrai : preuve GeoJSON. Ne compte pas les acquisitions.",
        "passage",
    ),
    # On associe la clé 'parcel' à cette valeur dans cet objet.
    "parcel": (
        "Vitiparcel · critère satisfait",
        "Passages uniques : critère explicite de la vue, sinon JSON de stocks présent ET au moins un statut non sain. Critère technique, pas une validation de livraison.",
        "passage",
    ),
    # On associe la clé 'test' à cette valeur dans cet objet.
    "test": (
        "Tests déclarés · Excel",
        "Catégorie Test dans le suivi Excel normalisé, sans exiger des preuves de production complètes.",
        "acq",
    ),
    # On associe la clé 'blocked' à cette valeur dans cet objet.
    "blocked": (
        "Bloqué / en attente · Excel",
        "Catégorie Bloqué dans le suivi Excel normalisé (En attente / Autre). Ce n’est pas un blocage déduit du NAS.",
        "acq",
    ),
    # On associe la clé 'outside' à cette valeur dans cet objet.
    "outside": (
        "Traitements hors production",
        "Processing ET WEBP présents pour une acquisition classée Test, Bloqué ou autre catégorie non Production.",
        "acq",
    ),
}


def metric_frame(key, aq, ps):
    # On vérifie ce cas avant la suite : la clé de l’élément appartient à {'map', 'parcel'}.
    if key in {"map", "parcel"}:
        # On choisit la valeur de field selon ce test : la clé de l’élément correspond au texte
        # 'map'. Les deux résultats possibles restent définis explicitement ici.
        field = (
            "vitimap_created"
            if key == "map"
            else "vitiparcel_technical_criterion_satisfied"
        )
        # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour
        # ce cas.
        return ps[yes(ps, field)] if not ps.empty else ps
    # Cette branche traite le cas où aq est un tableau vide ou la clé de l’élément correspond à le
    # texte 'all'.
    if aq.empty or key == "all":
        # On remet les acquisitions à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return aq
    # On regroupe dans masks ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    masks = {
        # On renseigne l’appartenance au périmètre Production sous la clé 'production'.
        "production": aq["perimeter_normalized"].eq("Production"),
        # On associe la clé 'treated' à cette valeur dans cet objet.
        "treated": yes(aq, "treated_production"),
        # On renseigne la demande de vérification sous la clé 'review'.
        "review": yes(aq, "needs_verification"),
        # On associe la clé 'test' à cette valeur dans cet objet.
        "test": aq["perimeter_normalized"].eq("Test"),
        # On associe la clé 'blocked' à cette valeur dans cet objet.
        "blocked": aq["perimeter_normalized"].eq("Bloqué"),
        # On associe la clé 'outside' à cette valeur dans cet objet.
        "outside": yes(aq, "treated_outside_production"),
    }
    # On remet aq[masks.get(key, pd.Series(True, index=aq.index))] à l’appelant ; les étapes suivantes
    # de cette fonction ne sont plus parcourues.
    return aq[masks.get(key, pd.Series(True, index=aq.index))]


# On prépare la population de passages concernée par ce point de vérification.
def focus_passages(ps, all_aq):
    # On traite à part le tableau ps lorsqu’il est vide.
    if ps.empty:
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return ps, ps
    # On garde dans df une copie de ps pour travailler sur cet objet séparément.
    df = ps.copy()
    # On choisit la valeur de production selon ce test : la condition all_aq.empty n’est pas remplie.
    # Les deux résultats possibles restent définis explicitement ici.
    production = (
        all_aq[all_aq["perimeter_normalized"].eq("Production")]
        if not all_aq.empty
        else all_aq
    )

    # On évalue ici les conditions d’appartenance au périmètre considéré.
    def eligible(r):
        # On garde dans val la conversion en nombres avec le traitement d’erreur indiqué.
        val = pd.to_numeric(r.get("eligible_acquisitions_count"), errors="coerce")
        # Cette branche traite le cas où le contrôle pd.notna(val) est positif.
        if pd.notna(val):
            # On renvoie le booléen obtenu par cette comparaison : val est supérieur à 0.
            return val > 0
        # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
        # enregistré dans les données sources.
        category = str(r.get("passage_business_category", "")).casefold()
        # On vérifie ce cas avant la suite : category appartient à {'production', 'prod'}.
        if category in {"production", "prod"}:
            # On renvoie True comme résultat explicite de cette branche.
            return True
        # On fournit à l’appelant la valeur renvoyée par passage_linked.
        return passage_linked(r, production)

    # On garde dans df['production_link_confirmed'] le résultat de la fonction appliquée aux éléments
    # ou à l’axe indiqué de df.
    df["production_link_confirmed"] = df.apply(eligible, axis=1)
    # On garde dans errors une série pandas avec les valeurs et l’index fournis.
    errors = pd.Series(False, index=df.index)
    # On parcourt ['passage_error', 'vitimap_error', 'vitiparcel_error'] ; name désigne l’élément
    # courant à chaque passage dans la boucle.
    for name in ["passage_error", "vitimap_error", "vitiparcel_error"]:
        # On vérifie ce cas avant la suite : le nom en cours appartient au tableau de travail.
        if name in df:
            # On réunit les valeurs ou masques dans errors avec |, en conservant le résultat dans ce
            # même emplacement.
            errors |= df[name].map(
                lambda x: str(x).strip().lower()
                not in {"", "none", "nan", "false", "0", "[]", "{}"}
            )
    # On réunit ces masques avec | pour construire verifiable ; les parenthèses gardent les
    # comparaisons regroupées.
    verifiable = yes(df, "passage_outputs_verifiable") | yes(df, "passage_created")
    # On combine ces masques avec & pour construire complete_check ; les parenthèses gardent les
    # comparaisons regroupées.
    complete_check = (
        boolean(df, "vitimap_created").notna()
        & boolean(df, "stocks_json_exists").notna()
        & verifiable
        & ~errors
    )
    # On utilise ce texte pour df['focus_reason'] ; il ne dépend pas d’une valeur récupérée ailleurs à
    # cet endroit.
    df["focus_reason"] = (
        "Périmètre de production ou observation des deux fichiers non confirmé"
    )
    # On combine ces masques avec & pour construire candidate ; les parenthèses gardent les
    # comparaisons regroupées.
    candidate = (
        df["production_link_confirmed"]
        & complete_check
        & no(df, "vitimap_created")
        & no(df, "stocks_json_exists")
    )
    # On utilise ce texte pour df.loc[candidate, 'focus_reason'] ; il ne dépend pas d’une valeur
    # récupérée ailleurs à cet endroit.
    df.loc[candidate, "focus_reason"] = (
        "GeoJSON Vitimap et JSON de stocks non observés ; attente métier à confirmer"
    )
    # On garde dans excluded le masque d’égalité calculé pour
    # pd.to_numeric(df.get('eligible_acquisitions_count', pd.Series(No….
    excluded = pd.to_numeric(
        df.get(
            "eligible_acquisitions_count", pd.Series(None, index=df.index, dtype=object)
        ),
        # On définit ce que la conversion fera des valeurs invalides, au lieu de laisser ce cas
        # implicite.
        errors="coerce",
    ).eq(0)
    # On combine ces masques avec & pour construire uncertain ; les parenthèses gardent les
    # comparaisons regroupées.
    uncertain = (~df["production_link_confirmed"] | ~complete_check) & ~excluded
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return df[candidate], df[uncertain]


# On extrait les lignes de provenance utilisées par la présentation de la fraîcheur.
def freshness_rows(fr):
    # On prépare rows comme liste vide ; on la remplira au fil des opérations suivantes.
    rows = []
    # On parcourt fr.iterrows() ; (_, r) désigne l’élément courant à chaque passage dans la boucle.
    for _, r in fr.iterrows():
        # On ajoute {'Vignoble': r.get('vineyard_name', '—'), 'Observation NAS':
        # format_time(r.get('nas_check… à la fin de rows ; les éléments précédents restent conservés.
        rows.append(
            {
                # On associe la clé 'Vignoble' à cette valeur dans cet objet.
                "Vignoble": r.get("vineyard_name", "—"),
                # On associe la clé 'Observation NAS' à cette valeur dans cet objet.
                "Observation NAS": format_time(r.get("nas_checked_at")),
                # On associe la clé 'Rapprochement Excel / NAS' à cette valeur dans cet objet.
                "Rapprochement Excel / NAS": format_time(r.get("reconciled_at")),
                # On associe la clé 'Fuseau' à cette valeur dans cet objet.
                "Fuseau": TZ,
            }
        )
    # On fournit à l’appelant un tableau pandas construit avec les données indiquées.
    return pd.DataFrame(rows)


# On rassemble les éléments de synthèse de la comparaison demandée.
def build_comparison_summary(history, vineyard_name=None):
    # Cette branche traite le cas où history vaut None ou history est un tableau vide.
    if history is None or history.empty:
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return pd.DataFrame(), [
            "Historique indisponible : aucune comparaison possible."
        ]
    # On garde dans df une copie de history pour travailler sur cet objet séparément.
    df = history.copy()
    # Cette branche traite le cas où le nom du domaine est évalué comme vrai et le nom du domaine
    # diffère du texte '__ALL__'.
    if vineyard_name and vineyard_name != "__ALL__":
        # On sélectionne dans df les éléments désignés par df['vineyard_name'].eq(vineyard_name) ; df
        # recevra cette sélection.
        df = df[df["vineyard_name"].eq(vineyard_name)]
    # On garde dans run le prochain élément de (c for c in ['nas_pipeline_execution_id',
    # 'pipeline_execution_id'] if c i… ou la valeur de repli indiquée si l’itérateur est épuisé.
    run = next(
        (
            c
            for c in ["nas_pipeline_execution_id", "pipeline_execution_id"]
            if c in df and df[c].notna().any()
        ),
        None,
    )
    # Cette branche traite le cas où au moins un des cas regroupés ici est rencontré.
    if not run or "nas_checked_at" not in df or "acquisition_id_normalise" not in df:
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return pd.DataFrame(), [
            "Comparaison indisponible : identifiant d’observation NAS, date ou identifiant d’acquisition manquant."
        ]
    # On garde dans df['_ts'] les valeurs de df['nas_checked_at'] transformées par la fonction ou la
    # correspondance indiquée.
    df["_ts"] = df["nas_checked_at"].map(
        lambda x: pd.to_datetime(x, errors="coerce", utc=True)
    )
    # On prépare une liste distincte pour chacun de ces résultats : rows, messages. Elles seront
    # alimentées au même rythme dans la boucle.
    rows, messages = [], []
    # On regroupe dans fields ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    fields = {
        # On renseigne la présence constatée dans les données brutes sous la clé 'found_in_raw_live'.
        "found_in_raw_live": "présence dans le Brut",
        # On renseigne la présence dans les traitements sous la clé 'found_in_processing_live'.
        "found_in_processing_live": "présence dans Processing",
        # On renseigne la présence d’images WEBP sous la clé 'processing_has_webp_images'.
        "processing_has_webp_images": "images WEBP",
        # On renseigne la présence dans les correspondances de parcelles sous la clé
        # 'found_in_parcel_mapping'.
        "found_in_parcel_mapping": "mapping des parcelles",
        # On renseigne la présence dans les correspondances de passages sous la clé
        # 'found_in_passage_mapping'.
        "found_in_passage_mapping": "mapping des passages",
        # On associe la clé 'passage_created' à cette valeur dans cet objet.
        "passage_created": "dossier de passage",
    }
    # On parcourt df.groupby('vineyard_name', sort=True) ; (vineyard, group) désigne l’élément courant
    # à chaque passage dans la boucle.
    for vineyard, group in df.groupby("vineyard_name", sort=True):
        # On garde dans runs les lignes de group.dropna(subset=[run, '_ts']).groupby(run)['_ts'].max()
        # triées selon les colonnes indiquées.
        runs = (
            group.dropna(subset=[run, "_ts"])
            .groupby(run)["_ts"]
            .max()
            # On définit le sens du tri ; il ne faut pas confondre le premier résultat avec le plus
            # récent sans ce réglage.
            .sort_values(ascending=False)
        )
        # On vérifie ce cas avant la suite : len(runs) est inférieur à 2.
        if len(runs) < 2:
            # On ajoute f'{vineyard} : aucune observation NAS précédente disponible.' à la fin de
            # messages ; les éléments précédents restent conservés.
            messages.append(
                f"{vineyard} : aucune observation NAS précédente disponible."
            )
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On garde dans (latest_id, prev_id) la portion de runs.index sélectionnée par :2 ; les bornes
        # de fin sont exclues.
        latest_id, prev_id = runs.index[:2]
        # On distribue ces valeurs entre latest, previous, dans l’ordre de l’affectation. Chaque nom
        # reçoit son propre élément.
        latest, previous = (
            group[group[run].eq(latest_id)],
            group[group[run].eq(prev_id)],
        )
        # On prépare scope avec cette expression pour l’utiliser dans la suite du traitement.
        scope = f"{vineyard} — du {format_time(runs.iloc[1], True)} au {format_time(runs.iloc[0], True)}"
        # Cette branche traite le cas où le contrôle
        # latest.duplicated('acquisition_id_normalise').any() est positif ou le contrôle
        # previous.duplicated('acquisition_id_normalise').any() est positif.
        if (
            latest.duplicated("acquisition_id_normalise").any()
            # Ce cas est aussi retenu si le contrôle
            # previous.duplicated('acquisition_id_normalise').any() est positif.
            or previous.duplicated("acquisition_id_normalise").any()
        ):
            # On ajoute scope + ' : comparaison suspendue, identifiants dupliqués dans une
            # observation.' à la fin de messages ; les éléments précédents restent conservés.
            messages.append(
                scope
                + " : comparaison suspendue, identifiants dupliqués dans une observation."
            )
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On construit common_fields comme une liste à partir de f, pour chaque f de fields en ne
        # gardant que les éléments qui passent le filtre.
        common_fields = [
            f for f in fields if f in group and group[f].map(_to_bool).notna().any()
        ]
        # On prévoit le cas où common_fields est évalué comme faux, par exemple une valeur vide selon
        # son type.
        if not common_fields:
            # On ajoute scope + ' : aucune preuve technique comparable renseignée.' à la fin de
            # messages ; les éléments précédents restent conservés.
            messages.append(scope + " : aucune preuve technique comparable renseignée.")
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On distribue ces valeurs entre new, old, dans l’ordre de l’affectation. Chaque nom reçoit
        # son propre élément.
        new, old = (
            latest.set_index("acquisition_id_normalise"),
            previous.set_index("acquisition_id_normalise"),
        )
        # On garde dans n_before le nombre d’éléments des lignes.
        n_before = len(rows)
        # On fixe comparable_count à 0 pour cette étape.
        comparable_count = 0

        # On prépare la valeur textuelle utilisée par la comparaison locale.
        def word(v):
            # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction
            # pour ce cas.
            return (
                "présent" if v is True else "absent" if v is False else "non renseigné"
            )

        # On parcourt sorted(set(new.index) | set(old.index)) ; key désigne l’élément courant à chaque
        # passage dans la boucle.
        for key in sorted(set(new.index) | set(old.index)):
            # Cette branche traite le cas où la clé de l’élément ne figure pas dans old.index ou la clé
            # de l’élément ne figure pas dans new.index.
            if key not in old.index or key not in new.index:
                # On ajoute {'Vignoble': vineyard, 'Acquisition': key, 'Différence observée': 'Présente
                # seulement dan… à la fin de rows ; les éléments précédents restent conservés.
                rows.append(
                    {
                        # On associe la clé 'Vignoble' à cette valeur dans cet objet.
                        "Vignoble": vineyard,
                        # On associe la clé 'Acquisition' à cette valeur dans cet objet.
                        "Acquisition": key,
                        "Différence observée": "Présente seulement dans la dernière observation"
                        if key in new.index
                        else "Présente seulement dans l’observation précédente",
                        "Observation précédente": format_time(runs.iloc[1], True),
                        "Observation récente": format_time(runs.iloc[0], True),
                    }
                )
                # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                continue
            # On ajoute 1 à comparable_count et on conserve ce nouvel état pour la suite.
            comparable_count += 1
            # On prépare changes comme liste vide ; on la remplira au fil des opérations suivantes.
            changes = []
            # On parcourt common_fields ; field désigne l’élément courant à chaque passage dans la
            # boucle.
            for field in common_fields:
                # On distribue ces valeurs entre before, after, dans l’ordre de l’affectation. Chaque
                # nom reçoit son propre élément.
                before, after = (
                    _to_bool(old.at[key, field]),
                    _to_bool(new.at[key, field]),
                )
                # On vérifie ce cas avant la suite : l’état relevé avant l’opération diffère de l’état
                # relevé après l’opération.
                if before != after:
                    # On ajoute f'{fields[field]} : {word(before)} → {word(after)}' à la fin de changes
                    # ; les éléments précédents restent conservés.
                    changes.append(f"{fields[field]} : {word(before)} → {word(after)}")
            # Cette branche traite le cas où changes est évalué comme vrai.
            if changes:
                # On ajoute {'Vignoble': vineyard, 'Acquisition': key, 'Différence observée': ' ;
                # '.join(changes), 'O… à la fin de rows ; les éléments précédents restent conservés.
                rows.append(
                    {
                        # On associe la clé 'Vignoble' à cette valeur dans cet objet.
                        "Vignoble": vineyard,
                        # On associe la clé 'Acquisition' à cette valeur dans cet objet.
                        "Acquisition": key,
                        "Différence observée": " ; ".join(changes),
                        "Observation précédente": format_time(runs.iloc[1], True),
                        "Observation récente": format_time(runs.iloc[0], True),
                    }
                )
        # On calcule la différence entre ces deux valeurs pour construire changes_count.
        changes_count = len(rows) - n_before
        # On choisit la valeur de tail selon ce test : changes_count est évalué comme vrai. Les deux
        # résultats possibles restent définis explicitement ici.
        tail = (
            f"{changes_count} acquisition(s) avec une différence de preuve ou de présence dans les observations."
            if changes_count
            else f"Aucun changement sur les preuves comparées de {comparable_count} acquisition(s) commune(s)."
        )
        # Cette branche traite le cas où comparable_count correspond à 0 et changes_count correspond à
        # 0.
        if comparable_count == 0 and changes_count == 0:
            # On utilise ce texte pour tail ; il ne dépend pas d’une valeur récupérée ailleurs à cet
            # endroit.
            tail = "Aucune acquisition comparable."
        # On ajoute scope + ' : ' + tail à la fin de messages ; les éléments précédents restent
        # conservés.
        messages.append(scope + " : " + tail)
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return pd.DataFrame(rows), messages or ["Aucun historique pour ce vignoble."]
