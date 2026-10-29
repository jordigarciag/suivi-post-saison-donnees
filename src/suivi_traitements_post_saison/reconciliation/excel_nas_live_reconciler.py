# Lecture du fichier — Rapprochement du tableau des suivis Excel avec les preuves NAS préparées.
# On relie acquisitions, parcelles et passages puis on interprète les écarts. L’absence d’un livrable
# ne signifie pas à elle seule qu’il était commandé pour ce périmètre.
#

"""Enrichit les CSV de preuves NAS actuelles par le suivi Excel déjà ingéré.

Aucune lecture du NAS ni de fichiers images/JSON de production : uniquement
les CSV locaux fournis. Le scan historique reste séparé et inchangé.

Règle métier : En attente / Autre dans le suivi Excel exclut l'acquisition
 des vérifications d'anomalies à ce stade. Non statué n'annule pas cette
 exclusion ; il reste conservé comme déclaration, sans devenir Résolu.
Au niveau passage, le critère Vitiparcel prêt à livrer reste : fichier de
stocks présent ET au moins un statut non sain. Une absence seule ne crée
pas d'alerte : elle est croisée avec une déclaration Excel Terminé applicable.
Les passages couvrent deux semaines depuis leur date de début ; les liens
proviennent du mapping, sans reconstruction par journée ni contrôle de délai.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations
# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe unicodedata. On peut distinguer les lettres et leurs marques d’accent pour normaliser le
# texte.
import unicodedata
# On importe textwrap. Ce module sera utilisé par les opérations de ce fichier.
import textwrap
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd

# On vérifie ce cas avant la suite : __package__ appartient à {None, ''}.
if __package__ in {None, ""}:
    # On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables
    # dans ce contexte.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
# On rend disponibles prepare_excel_reference, normalize_join_key, unique_non_empty_values,
# join_unique_values, value_to_boolean, validate_required_columns depuis
# suivi_traitements_post_saison.reconciliation.excel_tracking_reference, pour les appels de ce fichier.
from suivi_traitements_post_saison.reconciliation.excel_tracking_reference import (
    prepare_excel_reference,
    normalize_join_key,
    unique_non_empty_values,
    join_unique_values,
    value_to_boolean,
    validate_required_columns,
)

# On récupère Path(__file__).resolve().parents[3] et on le garde dans PROJECT_ROOT pour la suite.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
# On assemble les morceaux du chemin DEFAULT_REFERENCE avec l’opérateur / de pathlib ; aucun fichier
# n’est créé par cette construction.
DEFAULT_REFERENCE = (
    PROJECT_ROOT
    / "data/03_normalized/suivi_acquisitions_normalises/toutes_acquisitions_normalisees.csv"
)
# On assemble les morceaux du chemin DEFAULT_OUTPUT avec l’opérateur / de pathlib ; aucun fichier n’est
# créé par cette construction.
DEFAULT_OUTPUT = PROJECT_ROOT / "data/03_normalized/reconciliations/nas_live"
# On rassemble dans ACQUISITION_KEYS les 2 éléments explicitement indiqués, en conservant leur
# structure.
ACQUISITION_KEYS = ["vineyard_key", "acquisition_join_key"]
# On rassemble dans PASSAGE_KEYS les 4 éléments explicitement indiqués, en conservant leur structure.
PASSAGE_KEYS = ["vineyard_key", "project_year", "parcel_name", "passage_name"]
# On rassemble dans ERROR_COLUMNS les 5 éléments explicitement indiqués, en conservant leur structure.
ERROR_COLUMNS = [
    "raw_error",
    "processing_error",
    "passage_error",
    "vitimap_error",
    "vitiparcel_error",
]
# On rassemble dans EVIDENCE_COLUMNS les 14 éléments explicitement indiqués, en conservant leur
# structure.
EVIDENCE_COLUMNS = [
    "Vineyard",
    "acquisition_id_normalise",
    "project_year",
    "checked_at",
    "found_in_raw_live",
    "raw_has_full_size_both_sides",
    "found_in_processing_live",
    "processing_has_webp_images",
    "processing_has_webp_both_sides",
    "found_in_parcel_mapping",
    "found_in_passage_mapping",
    "parcel_mapping_consistent",
    "passage_link_count",
    *ERROR_COLUMNS,
]
# On rassemble dans DECISION_COLUMNS les 6 éléments explicitement indiqués, en conservant leur
# structure.
DECISION_COLUMNS = [
    "Vineyard",
    "acquisition_id_normalise",
    "full_processing_expected",
    "decision_reason",
    "decision_source",
    "decision_at",
]


def read_csv(path: Path) -> pd.DataFrame:
    # On fournit à l’appelant la valeur renvoyée par pd.read_csv.
    return pd.read_csv(path, dtype="string", encoding="utf-8-sig", low_memory=False)


def text(value) -> str:
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return "" if pd.isna(value) else str(value).strip()


# On construit un accès par clé en respectant les contrôles d’unicité du module.
def keyed(df: pd.DataFrame, id_column: str | None = None) -> pd.DataFrame:
    # On garde dans result une copie de df pour travailler sur cet objet séparément.
    result = df.copy()
    # On garde dans result['vineyard_key'] le résultat de la fonction appliquée aux éléments ou à l’axe
    # indiqué de result['Vineyard'].
    result["vineyard_key"] = result["Vineyard"].apply(normalize_join_key)
    # Cette branche traite le cas où le contrôle result['vineyard_key'].isna().any() est positif.
    if result["vineyard_key"].isna().any():
        # On interrompt cette branche avec ValueError : 'Vignoble vide dans les entrées.'.
        raise ValueError("Vignoble vide dans les entrées.")
    # Cette branche traite le cas où id_column est évalué comme vrai.
    if id_column:
        # On garde dans result['acquisition_join_key'] le résultat de la fonction appliquée aux
        # éléments ou à l’axe indiqué de result[id_column].
        result["acquisition_join_key"] = result[id_column].apply(normalize_join_key)
        # Cette branche traite le cas où le contrôle result['acquisition_join_key'].isna().any() est
        # positif.
        if result["acquisition_join_key"].isna().any():
            # On interrompt cette branche avec ValueError : 'Identifiant acquisition vide dans les
            # entrées.'.
            raise ValueError("Identifiant acquisition vide dans les entrées.")
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


def flag(value) -> bool:
    # On fournit à l’appelant la valeur renvoyée par value_to_boolean.
    return value_to_boolean(value)


# On prépare les tableaux et liens nécessaires au rapprochement.
def prepare_context(excel_rows: pd.DataFrame) -> pd.DataFrame:
    """Réutilise la consolidation historique et ajoute date/valeurs par côté."""
    # On traite à part le tableau excel_rows lorsqu’il est vide.
    if excel_rows.empty:
        # Un vignoble peut être observé sans aucune ligne de suivi disponible.
        return pd.DataFrame(
            # On décrit les colonnes à présenter, distinctes des lignes de données.
            columns=[
                "acquisition_join_key",
                "excel_vineyard_key",
                "excel_vineyard",
                "excel_acquisition_id_normalise",
                "excel_pipeline_status",
                "excel_perimeter",
                "excel_is_test_candidate",
                "excel_is_blocked_candidate",
                "excel_comments",
                "excel_problems",
                "excel_resolution_statuses",
                "excel_visual_processing",
                "excel_segmentation",
                "excel_vitimap",
                "excel_vitiparcel",
                "excel_ingested_at",
                "excel_side_context_json",
                "excel_stage_values_differ",
            ]
        )
    # On garde dans result la valeur renvoyée par prepare_excel_reference.
    result = prepare_excel_reference(excel_rows)
    # On garde dans prepared les lignes indexées par leur clé après vérification de l’unicité.
    prepared = keyed(excel_rows, "Acquisition_ID_normalise")
    # On prépare extra comme liste vide ; on la remplira au fil des opérations suivantes.
    extra = []
    # On parcourt prepared.groupby(ACQUISITION_KEYS, sort=False) ; ((vineyard, acquisition), group)
    # désigne l’élément courant à chaque passage dans la boucle.
    for (vineyard, acquisition), group in prepared.groupby(
        ACQUISITION_KEYS, sort=False
    ):
        # On rassemble dans fields les 15 éléments explicitement indiqués, en conservant leur
        # structure.
        fields = [
            "Acquisition_ID",
            "Acquisition_side",
            "Commentaires",
            "Problématique",
            "Statut_Resolution",
            "Traitement_visuel_images",
            "Segmentation_images",
            "VitiMap",
            "VitiParcel",
            "Périmètre",
            "Statut_pipeline",
            "source_file",
            "source_sheet",
            "source_row_number",
            "ingested_at",
        ]
        # On construit records comme une liste à partir de {column: text(row.get(column, pd.NA)) for
        # column in fields}, pour chaque (_, row) de group.iterrows().
        records = [
            {column: text(row.get(column, pd.NA)) for column in fields}
            for _, row in group.iterrows()
        ]
        # On ajoute {'acquisition_join_key': acquisition, 'excel_vineyard_key': vineyard,
        # 'excel_ingested_at'… à la fin de extra ; les éléments précédents restent conservés.
        extra.append(
            {
                # On associe la clé 'acquisition_join_key' à cette valeur dans cet objet.
                "acquisition_join_key": acquisition,
                # On associe la clé 'excel_vineyard_key' à cette valeur dans cet objet.
                "excel_vineyard_key": vineyard,
                # On associe la clé 'excel_ingested_at' à cette valeur dans cet objet.
                "excel_ingested_at": join_unique_values(group["ingested_at"])
                if "ingested_at" in group
                else "",
                # On associe la clé 'excel_side_context_json' à cette valeur dans cet objet.
                "excel_side_context_json": json.dumps(records, ensure_ascii=False),
                # On associe la clé 'excel_stage_values_differ' à cette valeur dans cet objet.
                "excel_stage_values_differ": any(
                    len(unique_non_empty_values(group[column])) > 1
                    for column in (
                        "Traitement_visuel_images",
                        "Segmentation_images",
                        "VitiMap",
                        "VitiParcel",
                    )
                    if column in group
                ),
            }
        )
    # On rapproche les tableaux avec les clés et le type de jointure indiqués ; ces paramètres
    # déterminent quelles lignes sont conservées.
    return result.merge(
        # On donne les clés communes utilisées pour rapprocher les deux tableaux.
        pd.DataFrame(extra), on="acquisition_join_key", validate="one_to_one"
    )


# On contrôle les entrées avant d’effectuer les rapprochements.
def validate_inputs(evidence, associations, passages):
    """Contrôle grain, clés, cohérence de périmètre et même observation NAS."""
    # On appelle validate_required_columns avec evidence.
    validate_required_columns(evidence, EVIDENCE_COLUMNS, "preuves acquisitions")
    # On appelle validate_required_columns avec associations.
    validate_required_columns(
        associations,
        [
            "Vineyard",
            "acquisition_id_normalise",
            "project_year",
            "parcel_name",
            "passage_name",
            "checked_at",
            "parcel_mapping_consistent",
        ],
        "associations",
    )
    # On appelle validate_required_columns avec passages.
    validate_required_columns(
        passages,
        [
            "Vineyard",
            "project_year",
            "parcel_name",
            "passage_name",
            "checked_at",
            "stocks_json_exists",
            "stock_status_count",
            "has_non_healthy_status",
            "vitiparcel_created",
            "passage_created",
            "vitimap_created",
            "passage_error",
            "vitimap_error",
            "vitiparcel_error",
        ],
        "passages",
    )
    # On garde dans e les lignes indexées par leur clé après vérification de l’unicité.
    e = keyed(evidence, "acquisition_id_normalise")
    # On garde dans a les lignes indexées par leur clé après vérification de l’unicité.
    a = keyed(associations, "acquisition_id_normalise")
    # On garde dans p les lignes indexées par leur clé après vérification de l’unicité.
    p = keyed(passages)
    # On doit résoudre ces doublons avant de compter ou de rapprocher les lignes.
    if e.duplicated(ACQUISITION_KEYS).any():
        # On interrompt cette branche avec ValueError : 'Plusieurs observations pour une acquisition :
        # sélectionner un seul run.'.
        raise ValueError(
            "Plusieurs observations pour une acquisition : sélectionner un seul run."
        )
    # On doit résoudre ces doublons avant de compter ou de rapprocher les lignes.
    if a.duplicated(
        ACQUISITION_KEYS + ["project_year", "parcel_name", "passage_name"]
    ).any():
        # On interrompt cette branche avec ValueError : 'Association acquisition/parcelle/passage
        # répétée.'.
        raise ValueError("Association acquisition/parcelle/passage répétée.")
    # On doit résoudre ces doublons avant de compter ou de rapprocher les lignes.
    if p.duplicated(PASSAGE_KEYS).any():
        # On interrompt cette branche avec ValueError : 'Passage répété dans le bilan distinct.'.
        raise ValueError("Passage répété dans le bilan distinct.")
    # On parcourt (e, a, p) ; frame désigne l’élément courant à chaque passage dans la boucle.
    for frame in (e, a, p):
        # On garde dans times la conversion en dates avec les règles indiquées, notamment pour les
        # valeurs invalides.
        times = pd.to_datetime(frame["checked_at"], utc=True, errors="coerce")
        # Cette branche traite le cas où le contrôle times.isna().any() est positif.
        if times.isna().any():
            # On interrompt cette branche avec ValueError : 'Date de contrôle manquante ou invalide.'.
            raise ValueError("Date de contrôle manquante ou invalide.")
        # Cette branche traite le cas où le contrôle frame['project_year'].isna().any() est positif.
        if frame["project_year"].isna().any():
            # On interrompt cette branche avec ValueError : 'Année manquante.'.
            raise ValueError("Année manquante.")
    # On vérifie ce cas avant la suite : len(e) correspond à 0.
    if len(e) == 0:
        # On interrompt cette branche avec ValueError : 'Aucune acquisition dans le périmètre
        # demandé.'.
        raise ValueError("Aucune acquisition dans le périmètre demandé.")
    # On parcourt ['found_in_raw_live', 'raw_has_full_size_both_sides', 'found_in_processin… ; column
    # désigne l’élément courant à chaque passage dans la boucle.
    for column in [
        "found_in_raw_live",
        "raw_has_full_size_both_sides",
        "found_in_processing_live",
        "processing_has_webp_images",
        "processing_has_webp_both_sides",
        "found_in_parcel_mapping",
        "found_in_passage_mapping",
    ]:
        # Cette branche traite le cas où le contrôle e[column].isna().any() est positif.
        if e[column].isna().any():
            # On interrompt cette branche avec ValueError.
            raise ValueError(f"Preuve booléenne manquante : {column}.")
        # On appelle e[column].map avec flag.
        e[column].map(flag)  # Rejeter une valeur invalide, pas la convertir en absence.
    # On parcourt ('stocks_json_exists', 'has_non_healthy_status', 'vitiparcel_created', 'p… ; column
    # désigne l’élément courant à chaque passage dans la boucle.
    for column in (
        "stocks_json_exists",
        "has_non_healthy_status",
        "vitiparcel_created",
        "passage_created",
        "vitimap_created",
    ):
        # Cette branche traite le cas où le contrôle p[column].isna().any() est positif.
        if p[column].isna().any():
            # On interrompt cette branche avec ValueError.
            raise ValueError(f"Preuve booléenne passage manquante : {column}.")
        # On appelle p[column].map avec flag.
        p[column].map(flag)
    # On garde dans status_counts la conversion en nombres avec le traitement d’erreur indiqué.
    status_counts = pd.to_numeric(p["stock_status_count"], errors="coerce")
    # Cette branche traite le cas où le contrôle status_counts.isna().any() est positif ou le contrôle
    # ((status_counts < 0) | (status_counts % 1 != 0)).any() est positif.
    if (
        status_counts.isna().any()
        # Ce cas est aussi retenu si le contrôle ((status_counts < 0) | (status_counts % 1 != 0)).any()
        # est positif.
        or ((status_counts < 0) | (status_counts % 1 != 0)).any()
    ):
        # On interrompt cette branche avec ValueError : 'Nombre de statuts passage invalide.'.
        raise ValueError("Nombre de statuts passage invalide.")
    # On garde dans reference_times les valeurs distinctes de pd.to_datetime(e['checked_at'],
    # utc=True).
    reference_times = set(pd.to_datetime(e["checked_at"], utc=True))
    # On vérifie ce cas avant la suite : len(reference_times) diffère de 1.
    if len(reference_times) != 1:
        # On interrompt cette branche avec ValueError : 'Le fichier acquisitions mélange plusieurs
        # runs.'.
        raise ValueError("Le fichier acquisitions mélange plusieurs runs.")
    # On parcourt (a, p) ; frame désigne l’élément courant à chaque passage dans la boucle.
    for frame in (a, p):
        # Cette branche traite le cas où la condition set(pd.to_datetime(frame['checked_at'],
        # utc=True)).issubset(reference_times) n’est pas remplie.
        if not set(pd.to_datetime(frame["checked_at"], utc=True)).issubset(
            reference_times
        ):
            # On interrompt cette branche avec ValueError : 'Les trois CSV ne proviennent pas du même
            # run.'.
            raise ValueError("Les trois CSV ne proviennent pas du même run.")
    # Cette branche traite le cas où le contrôle len(a) est positif.
    if len(a):
        # On rapproche les tableaux avec les clés précisées ; le type de jointure ci-dessous décide
        # quelles lignes sont conservées.
        membership = a.merge(
            e[ACQUISITION_KEYS + ["project_year"]],
            # On donne les clés communes utilisées pour rapprocher les deux tableaux.
            on=ACQUISITION_KEYS + ["project_year"],
            # On fixe le type de jointure ; ce choix détermine quelles lignes sans correspondance
            # restent présentes.
            how="left",
            indicator=True,
            # On demandu contrôle de cardinalité indiqué pour ne pas accepter un rapprochement
            # inattendu.
            validate="many_to_one",
        )
        # Cette branche traite le cas où la condition membership['_merge'].eq('both').all() n’est pas
        # remplie.
        if not membership["_merge"].eq("both").all():
            # On interrompt cette branche avec ValueError : 'Association sans acquisition
            # correspondante.'.
            raise ValueError("Association sans acquisition correspondante.")
    # On choisit la valeur de counts selon ce test : le contrôle len(a) est positif. Les deux résultats
    # possibles restent définis explicitement ici.
    counts = a.groupby(ACQUISITION_KEYS).size() if len(a) else pd.Series(dtype=int)
    # On parcourt e.iterrows() ; (_, row) désigne l’élément courant à chaque passage dans la boucle.
    for _, row in e.iterrows():
        # On garde dans observed la conversion numérique de counts.get((row['vineyard_key'],
        # row['acquisition_join_key']), 0) en entier.
        observed = int(
            counts.get((row["vineyard_key"], row["acquisition_join_key"]), 0)
        )
        # On vérifie ce cas avant la suite : observed diffère de int(row['passage_link_count']).
        if observed != int(row["passage_link_count"]):
            # On interrompt cette branche avec ValueError : 'Nombre d’associations différent du
            # compteur acquisition.'.
            raise ValueError("Nombre d’associations différent du compteur acquisition.")
        # On vérifie ce cas avant la suite : flag(row['found_in_passage_mapping']) diffère de
        # bool(observed).
        if flag(row["found_in_passage_mapping"]) != bool(observed):
            # On interrompt cette branche avec ValueError : 'Indicateur de rattachement incompatible
            # avec les associations.'.
            raise ValueError(
                "Indicateur de rattachement incompatible avec les associations."
            )
    # On garde dans associated_passages les valeurs distinctes de map(tuple,
    # a[PASSAGE_KEYS].to_numpy()).
    associated_passages = set(map(tuple, a[PASSAGE_KEYS].to_numpy()))
    # On garde dans reported_passages les valeurs distinctes de map(tuple, p[PASSAGE_KEYS].to_numpy()).
    reported_passages = set(map(tuple, p[PASSAGE_KEYS].to_numpy()))
    # On vérifie ce cas avant la suite : associated_passages diffère de reported_passages.
    if associated_passages != reported_passages:
        # On interrompt cette branche avec ValueError : 'Les associations et le bilan distinct ne
        # couvrent pas les mêmes passages.'.
        raise ValueError(
            "Les associations et le bilan distinct ne couvrent pas les mêmes passages."
        )
    # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return e, a, p


def prepare_decisions(decisions: pd.DataFrame | None) -> pd.DataFrame | None:
    """Décision explicite, jamais inférée d'un commentaire ou de Non statué."""
    # On vérifie ce cas avant la suite : decisions vaut None.
    if decisions is None:
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None
    # On appelle validate_required_columns avec decisions.
    validate_required_columns(decisions, DECISION_COLUMNS, "décisions métier")
    # On garde dans d les lignes indexées par leur clé après vérification de l’unicité.
    d = keyed(decisions, "acquisition_id_normalise")
    # On doit résoudre ces doublons avant de compter ou de rapprocher les lignes.
    if d.duplicated(ACQUISITION_KEYS).any():
        # On interrompt cette branche avec ValueError : 'Plusieurs décisions pour une acquisition.'.
        raise ValueError("Plusieurs décisions pour une acquisition.")
    # On garde dans values les valeurs de d['full_processing_expected'] transformées par la fonction ou
    # la correspondance indiquée.
    values = d["full_processing_expected"].map(lambda value: text(value).casefold())
    # Cette branche traite le cas où la condition values.isin(['oui', 'non', 'a_confirmer']).all()
    # n’est pas remplie.
    if not values.isin(["oui", "non", "a_confirmer"]).all():
        # On interrompt cette branche avec ValueError : 'full_processing_expected : utiliser oui, non
        # ou a_confirmer.'.
        raise ValueError("full_processing_expected : utiliser oui, non ou a_confirmer.")
    # On gardes valeurs sous le nom d['decision_full_processing_expected'] ; cette affectation ne
    # copie pas à elle seule un objet mutable.
    d["decision_full_processing_expected"] = values
    # On parcourt ('decision_reason', 'decision_source', 'decision_at') ; field désigne l’élément
    # courant à chaque passage dans la boucle.
    for field in ("decision_reason", "decision_source", "decision_at"):
        # On garde dans d[field] les valeurs de d[field] transformées par la fonction ou la
        # correspondance indiquée.
        d[field] = d[field].map(text)
    # On garde dans explicit le masque indiquant quels éléments de values figurent dans les valeurs
    # fournies.
    explicit = values.isin(["oui", "non"])
    # Cette branche traite le cas où le contrôle d.loc[explicit, ['decision_reason', 'decision_source',
    # 'decision_at']].eq… est positif.
    if (
        d.loc[explicit, ["decision_reason", "decision_source", "decision_at"]]
        .eq("")
        .any()
        .any()
    ):
        # On interrompt cette branche avec ValueError : 'Décision confirmée : motif, source et date
        # obligatoires.'.
        raise ValueError("Décision confirmée : motif, source et date obligatoires.")
    # Cette branche traite le cas où le contrôle pd.to_datetime(d.loc[explicit, 'decision_at'],
    # utc=True, errors='coerce')… est positif.
    if (
        pd.to_datetime(d.loc[explicit, "decision_at"], utc=True, errors="coerce")
        .isna()
        .any()
    ):
        # On interrompt cette branche avec ValueError : 'Date de décision invalide.'.
        raise ValueError("Date de décision invalide.")
    # On remet d[ACQUISITION_KEYS + ['decision_full_processing_expected', 'decision_reas… à l’appelant
    # ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return d[
        ACQUISITION_KEYS
        + [
            "decision_full_processing_expected",
            "decision_reason",
            "decision_source",
            "decision_at",
        ]
    ]


def mapping_documentation(row: pd.Series) -> dict:
    """Reconnaissance prudente d'un même écart, jamais exemption globale.

    Seule la formulation explicite « Parcelle X est mappée alors qu'il
    n'y a pas d'acquisition dessus », avec ERREUR_MAPPING sur la même
    ligne Excel, couvre X. Les autres formulations restent à examiner.
    Une déclaration Exploitable seule ne suffit pas ; aucun statut n'est modifié.
    """

    def normalized(value):
        # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
        # enregistré dans les données sources.
        value = unicodedata.normalize("NFKD", text(value)).casefold()
        # On fournit à l’appelant le texte formé en réunissant les éléments avec '' comme séparateur.
        return "".join(c for c in value if not unicodedata.combining(c))

    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    records = json.loads(text(row.get("excel_side_context_json")) or "[]")
    # On garde dans gaps les objets Python décodés depuis le JSON fourni.
    gaps = json.loads(text(row.get("relationship_observed_gaps_json")) or "[]")
    # On garde dans documented un ensemble vide, qui servira à repérer les valeurs déjà rencontrées.
    documented = set()
    # On utilise ce texte pour pattern ; il ne dépend pas d’une valeur récupérée ailleurs à cet
    # endroit.
    pattern = r"parcelle\s+[\"'«]([^\"'»]+)[\"'»]\s+est\s+mappee\s+alors\s+qu['’]il\s+n['’]y\s+a\s+pas\s+d['’]acquisition\s+dessus"
    # On parcourt records ; record désigne l’élément courant à chaque passage dans la boucle.
    for record in records:
        # On construit codes comme un ensemble sans doublons à partir de v.strip().upper(), pour chaque
        # v de record.get('Problématique', '').split(' | ').
        codes = {
            v.strip().upper() for v in record.get("Problématique", "").split(" | ")
        }
        # On vérifie ce cas avant la suite : le texte 'ERREUR_MAPPING' ne figure pas dans codes.
        if "ERREUR_MAPPING" not in codes:
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On parcourt re.finditer(pattern, normalized(record.get('Commentaires', ''))) ; match désigne
        # l’élément courant à chaque passage dans la boucle.
        for match in re.finditer(pattern, normalized(record.get("Commentaires", ""))):
            # On ajoute normalized(match.group(1)) à documented ; comme il s’agit d’un ensemble, une
            # valeur déjà présente n’est pas comptée deux fois.
            documented.add(normalized(match.group(1)))
    # On construit covered comme une liste à partir de parcel, pour chaque parcel de gaps en ne gardant
    # que les éléments qui passent le filtre.
    covered = [parcel for parcel in gaps if normalized(parcel) in documented]
    # On calcule complete avec ces conditions liées par and ; Python s’arrête dès qu’une valeur est
    # évaluée comme fausse.
    complete = bool(gaps) and len(covered) == len(gaps)
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'relationship_documented_parcels_json' à cette valeur dans cet objet.
        "relationship_documented_parcels_json": json.dumps(covered, ensure_ascii=False),
        # On associe la clé 'relationship_known_documented' à cette valeur dans cet objet.
        "relationship_known_documented": complete,
    }


# On interprète les preuves de traitement disponibles, en gardant les situations incertaines.
def classify_processing(row: pd.Series) -> dict:
    """Applique le périmètre Excel, puis qualifie les écarts du périmètre actif."""
    # On construit errors comme une liste à partir de text(row.get(column)), pour chaque column de
    # ERROR_COLUMNS en ne gardant que les éléments qui passent le filtre.
    errors = [
        text(row.get(column)) for column in ERROR_COLUMNS if text(row.get(column))
    ]
    # On inverse la valeur de vérité de flag(row['processing_has_webp_both_sides']) pour obtenir
    # webp_gap.
    webp_gap = not flag(row["processing_has_webp_both_sides"])
    # On garde dans matches_excel le résultat de cette comparaison : row['excel_match_status']
    # correspond au texte 'both'.
    matches_excel = row["excel_match_status"] == "both"
    # On garde dans decision la forme textuelle préparée par text pour
    # row.get('decision_full_processing_expected', pd.NA).
    decision = text(row.get("decision_full_processing_expected", pd.NA))
    # On garde dans comment la forme textuelle préparée par text pour row.get('excel_comments', pd.NA).
    comment = text(row.get("excel_comments", pd.NA))
    # On garde dans problems la forme textuelle préparée par text pour row.get('excel_problems',
    # pd.NA).
    problems = text(row.get("excel_problems", pd.NA))
    # On garde dans resolution la forme textuelle préparée par text pour
    # row.get('excel_resolution_statuses', pd.NA).
    resolution = text(row.get("excel_resolution_statuses", pd.NA))
    # On garde dans stage_values la forme textuelle préparée par text pour
    # row.get('excel_visual_processing', pd.NA).
    stage_values = text(row.get("excel_visual_processing", pd.NA))
    # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
    # enregistré dans les données sources.
    normalized_stage = stage_values.casefold()
    # On garde dans declared_done un booléen indiquant si au moins un élément satisfait le test de
    # (v.strip().casefold() == 'terminé' for v in stage_values.split(' | ')).
    declared_done = any(
        v.strip().casefold() == "terminé" for v in stage_values.split(" | ")
    )
    # On garde dans is_test la valeur de l’indicateur interprétée par le helper de ce module.
    is_test = flag(row.get("excel_is_test_candidate", pd.NA))
    # On garde dans blocked la valeur de l’indicateur interprétée par le helper de ce module.
    blocked = flag(row.get("excel_is_blocked_candidate", pd.NA))
    # On retient pour known la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    known = bool(problems) or blocked
    # Règle prioritaire demandée : une étape explicitement En attente / Autre
    # suffit à sortir l'acquisition des vérifications à ce stade. La présence
    # d'un commentaire ou Non statué ne rouvre pas le contrôle.
    exclusion_fields = (
        "excel_pipeline_status",
        "excel_annotation_rangs",
        "excel_json_correction",
        "excel_visual_processing",
        "excel_segmentation",
        "excel_vitimap",
        "excel_vitiparcel",
    )
    # On prépare exclusion_matches comme liste vide ; on la remplira au fil des opérations suivantes.
    exclusion_matches = []
    # On parcourt exclusion_fields ; field désigne l’élément courant à chaque passage dans la boucle.
    for field in exclusion_fields:
        # On parcourt text(row.get(field, pd.NA)).split(' | ') ; value désigne l’élément courant à
        # chaque passage dans la boucle.
        for value in text(row.get(field, pd.NA)).split(" | "):
            # On vérifie ce cas avant la suite : value.strip().casefold() appartient à {'en attente',
            # 'autre'}.
            if value.strip().casefold() in {"en attente", "autre"}:
                # On ajoute f'{field}={value.strip()}' à la fin de exclusion_matches ; les éléments
                # précédents restent conservés.
                exclusion_matches.append(f"{field}={value.strip()}")
    # On calcule excluded_by_status avec ces conditions liées par and ; Python s’arrête dès qu’une
    # valeur est évaluée comme fausse.
    excluded_by_status = matches_excel and bool(exclusion_matches)
    # On calcule excluded_by_test avec ces conditions liées par and ; Python s’arrête dès qu’une valeur
    # est évaluée comme fausse.
    excluded_by_test = matches_excel and is_test
    # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
    # endroit.
    category = "Preuve WEBP complète"
    # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
    # endroit.
    next_action = (
        "Aucune action déduite de la présence WEBP ; qualité métier non évaluée."
    )
    # On initialise new_alert à False ; les branches suivantes pourront modifier cet état.
    new_alert = False
    # On utilise ce texte pour expected ; il ne dépend pas d’une valeur récupérée ailleurs à cet
    # endroit.
    expected = "À confirmer"
    # On initialise decision_required à False ; les branches suivantes pourront modifier cet état.
    decision_required = False
    # Cette branche traite le cas où matches_excel est évalué comme vrai et is_test est évalué comme
    # vrai.
    if matches_excel and is_test:
        # On utilise ce texte pour expected ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        expected = "Hors périmètre production — test déclaré"
    # On vérifie ce cas avant la suite : decision correspond au texte 'non'.
    if decision == "non":
        # On utilise ce texte pour expected ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        expected = "Traitement complet non attendu — décision explicite"
    # On vérifie ce cas avant la suite : decision correspond au texte 'oui'.
    elif decision == "oui":
        # On utilise ce texte pour expected ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        expected = "Traitement complet attendu — décision explicite"
    # Cette branche traite le cas où excluded_by_test est évalué comme vrai.
    if excluded_by_test:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Hors périmètre production — test déclaré"
        # On utilise ce texte pour expected ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        expected = "Hors contrôles — test déclaré dans Excel"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = (
            "Aucune vérification à faire à ce stade ; conserver les observations."
        )
    # Cette branche traite le cas où excluded_by_status est évalué comme vrai.
    elif excluded_by_status:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Hors contrôles — En attente / Autre dans Excel"
        # On utilise ce texte pour expected ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        expected = "Hors contrôles à ce stade — règle Excel"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = (
            "Aucune vérification à faire à ce stade ; exclusion selon le suivi Excel."
        )
    # Cette branche traite le cas où le contrôle text(row['processing_error']) est positif.
    elif text(row["processing_error"]):
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Erreur technique — traitement non vérifiable"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = "Vérifier l’accès ou la lecture ; ne pas conclure à une absence."
    # On prévoit le cas où webp_gap est évalué comme faux, par exemple une valeur vide selon son type.
    elif not webp_gap:
        # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
        pass
    # On prévoit le cas où matches_excel est évalué comme faux, par exemple une valeur vide selon son
    # type.
    elif not matches_excel:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Écart sans suivi Excel — à vérifier"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = "Identifier le contexte métier avant de décider du traitement."
        # On initialise new_alert à True ; les branches suivantes pourront modifier cet état.
        new_alert = True
    # On vérifie ce cas avant la suite : decision correspond au texte 'non'.
    elif decision == "non":
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Écart attendu — traitement non attendu confirmé"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = "Conserver la preuve manquante ; pas de nouvelle alerte pour cet écart WEBP."
    # Cette branche traite le cas où is_test est évalué comme vrai et decision diffère du texte
    # 'oui'.
    elif is_test and decision != "oui":
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Hors périmètre production — test déclaré"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = "Conserver les observations ; ne pas compter cet écart WEBP comme oubli de production."
    # Cette branche traite le cas où declared_done est évalué comme vrai.
    elif declared_done:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Divergence — terminé déclaré, preuve WEBP incomplète"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = (
            "Vérifier la fraîcheur du suivi, le stockage ou la déclaration de fin."
        )
        # On initialise new_alert à True ; les branches suivantes pourront modifier cet état.
        new_alert = True
    # Cette branche traite le cas où known est évalué comme vrai.
    elif known:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Écart connu et documenté — décision à vérifier"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = "Consulter la décision existante ou statuer ; ne pas créer un doublon d’alerte."
        # On initialise decision_required à True ; les branches suivantes pourront modifier cet état.
        decision_required = True
    # Cette branche traite le cas où le texte 'en cours' appartient à normalized_stage ou le texte 'non
    # commencé' appartient à normalized_stage.
    elif "en cours" in normalized_stage or "non commencé" in normalized_stage:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Avancement déclaré — pas un oubli démontré"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = "Suivre l’avancement ; aucun retard déduit sans règle de délai."
    # Cette branche traite le cas où comment est évalué comme vrai.
    elif comment:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Écart avec commentaire — lien explicatif à confirmer"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = "Vérifier que le commentaire explique bien l’absence WEBP."
        # On initialise decision_required à True ; les branches suivantes pourront modifier cet état.
        decision_required = True
    else:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Écart non expliqué — à vérifier"
        # On utilise ce texte pour next_action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        next_action = "Qualifier l’écart avant de conclure à un traitement oublié."
        # On initialise new_alert à True ; les branches suivantes pourront modifier cet état.
        new_alert = True
    # Conserver les observations, mais ne demander aucune vérification pour
    # une acquisition exclue par la règle Excel. Une exemption --decisions
    # concerne le WEBP : elle ne masque pas les autres contrôles.
    mapping_false = text(row.get("parcel_mapping_consistent", pd.NA)).casefold() in {
        "false",
        "0",
        "non",
    }
    # On retient pour relationship_review la première valeur évaluée comme vraie dans cette chaîne de
    # replis ; une valeur vide fera donc passer à la suivante.
    relationship_review = (
        not flag(row["found_in_parcel_mapping"])
        # Ce cas est aussi retenu si la condition flag(row['found_in_passage_mapping']) n’est pas
        # remplie.
        or not flag(row["found_in_passage_mapping"])
        or mapping_false
    )
    # On garde dans documentation la valeur renvoyée par mapping_documentation.
    documentation = mapping_documentation(row)
    # On calcule known_mapping avec ces conditions liées par and ; Python s’arrête dès qu’une valeur
    # est évaluée comme fausse.
    known_mapping = (
        mapping_false
        and documentation["relationship_known_documented"]
        # On exige aussi que le contrôle flag(row['found_in_parcel_mapping']) est positif.
        and flag(row["found_in_parcel_mapping"])
        # On exige aussi que le contrôle flag(row['found_in_passage_mapping']) est positif.
        and flag(row["found_in_passage_mapping"])
    )
    # Cette branche traite le cas où known_mapping est évalué comme vrai.
    if known_mapping:
        # On initialise relationship_review à False ; les branches suivantes pourront modifier cet
        # état.
        relationship_review = False
    # On choisit la valeur de relationship_category selon ce test : known_mapping est évalué comme
    # vrai. Les deux résultats possibles restent définis explicitement ici.
    relationship_category = (
        "Écart de mapping connu et documenté"
        if known_mapping
        else "Écart de relation à vérifier"
        if relationship_review
        else "Aucun écart de relation signalé"
    )
    # On choisit la valeur de relationship_action selon ce test : known_mapping est évalué comme vrai.
    # Les deux résultats possibles restent définis explicitement ici.
    relationship_action = (
        "Aucune nouvelle vérification pour ce même écart ; conserver la documentation Excel."
        if known_mapping
        else "Examiner les rattachements non expliqués."
        if relationship_review
        else "Aucune vérification de relation demandée."
    )
    # On retient pour raw_review la première valeur évaluée comme vraie dans cette chaîne de replis ;
    # une valeur vide fera donc passer à la suivante.
    raw_review = not flag(row["found_in_raw_live"]) or not flag(
        row["raw_has_full_size_both_sides"]
    )
    # Cette branche traite le cas où excluded_by_status est évalué comme vrai ou excluded_by_test est
    # évalué comme vrai.
    if excluded_by_status or excluded_by_test:
        # On initialise relationship_review à False ; les branches suivantes pourront modifier cet
        # état.
        relationship_review = False
        # On utilise ce texte pour relationship_category ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        relationship_category = "Hors contrôles — règle Excel"
        # On utilise ce texte pour relationship_action ; il ne dépend pas d’une valeur récupérée
        # ailleurs à cet endroit.
        relationship_action = "Aucune vérification de relation demandée à ce stade."
        # On initialise raw_review à False ; les branches suivantes pourront modifier cet état.
        raw_review = False
    # On calcule technical_review avec ces conditions liées par and ; Python s’arrête dès qu’une valeur
    # est évaluée comme fausse.
    technical_review = bool(errors) and not (excluded_by_status or excluded_by_test)
    # On calcule acquisition_candidate avec ces conditions liées par and ; Python s’arrête dès qu’une
    # valeur est évaluée comme fausse.
    acquisition_candidate = not (excluded_by_status or excluded_by_test) and (
        new_alert or relationship_review or raw_review or technical_review
    )
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'excluded_by_excel_status' à cette valeur dans cet objet.
        "excluded_by_excel_status": excluded_by_status,
        # On associe la clé 'excluded_by_excel_test' à cette valeur dans cet objet.
        "excluded_by_excel_test": excluded_by_test,
        # On associe la clé 'excel_exclusion_reason' à cette valeur dans cet objet.
        "excel_exclusion_reason": " | ".join(exclusion_matches),
        # On associe la clé 'eligible_for_new_anomaly_checks' à cette valeur dans cet objet.
        "eligible_for_new_anomaly_checks": not (excluded_by_status or excluded_by_test),
        # On associe la clé 'acquisition_new_anomaly_candidate' à cette valeur dans cet objet.
        "acquisition_new_anomaly_candidate": acquisition_candidate,
        # On associe la clé 'technical_review_required' à cette valeur dans cet objet.
        "technical_review_required": technical_review,
        # On associe la clé 'processing_evidence_gap' à cette valeur dans cet objet.
        "processing_evidence_gap": webp_gap,
        # On renseigne la catégorie métier du traitement sous la clé 'processing_business_category'.
        "processing_business_category": category,
        # On associe la clé 'processing_new_alert_candidate' à cette valeur dans cet objet.
        "processing_new_alert_candidate": new_alert,
        # On associe la clé 'processing_expectation' à cette valeur dans cet objet.
        "processing_expectation": expected,
        # On associe la clé 'processing_decision_required' à cette valeur dans cet objet.
        "processing_decision_required": decision_required,
        # On associe la clé 'business_resolution_declaration' à cette valeur dans cet objet.
        "business_resolution_declaration": resolution,
        # On renseigne la prochaine action indiquée pour le traitement sous la clé
        # 'processing_next_action'.
        "processing_next_action": next_action,
        # On associe la clé 'has_technical_error' à cette valeur dans cet objet.
        "has_technical_error": bool(errors),
        # On renseigne le détail des erreurs techniques sous la clé 'technical_errors'.
        "technical_errors": " | ".join(errors),
        **documentation,
        # On associe la clé 'relationship_business_category' à cette valeur dans cet objet.
        "relationship_business_category": relationship_category,
        # On associe la clé 'relationship_next_action' à cette valeur dans cet objet.
        "relationship_next_action": relationship_action,
        # On associe la clé 'relationship_review_required' à cette valeur dans cet objet.
        "relationship_review_required": relationship_review,
        # On associe la clé 'raw_evidence_review_required' à cette valeur dans cet objet.
        "raw_evidence_review_required": raw_review,
        # On associe la clé 'classification_note' à cette valeur dans cet objet.
        "classification_note": "Preuves conservées. En attente / Autre et tests Excel : aucune vérification demandée à ce stade, sans déclarer le cas résolu.",
    }


# On prépare l’interprétation métier d’un passage, distincte de la simple présence de fichiers.
def passage_interpretation(row):
    # On garde dans error un booléen indiquant si au moins un élément satisfait le test de
    # (text(row.get(c)) for c in ['passage_error', 'vitimap_error', 'vitiparcel_error']).
    error = any(
        text(row.get(c)) for c in ["passage_error", "vitimap_error", "vitiparcel_error"]
    )
    # Cette branche traite le cas où error est évalué comme vrai.
    if error:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Erreur technique — preuves à vérifier"
    # Cette branche traite le cas où la condition flag(row['stocks_json_exists']) n’est pas remplie.
    if not flag(row["stocks_json_exists"]):
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Fichier de stocks non détecté"
    # Cette branche traite le cas où le contrôle flag(row['has_non_healthy_status']) est positif.
    if flag(row["has_non_healthy_status"]):
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Fichier de stocks présent ; critère technique non sain satisfait"
    # On vérifie ce cas avant la suite : int(float(text(row['stock_status_count']) or '0')) correspond
    # à 0.
    if int(float(text(row["stock_status_count"]) or "0")) == 0:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Fichier de stocks présent ; aucun statut reconnu"
    # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
    return "Fichier de stocks présent ; aucun statut non sain détecté"


def passage_excel_context(group: pd.DataFrame) -> dict:
    """Déclarations traçables, provenant seulement des acquisitions éligibles.

    Terminé n'est applicable que si l'acquisition est rattachée à un seul
    passage, avec une association cohérente et sans statuts explicites
    contradictoires entre côtés. Vide ne contredit pas Terminé.
    """
    # On prépare une liste distincte pour chacun de ces résultats : done_sources, ambiguous_sources,
    # declarations. Elles seront alimentées au même rythme dans la boucle.
    done_sources, ambiguous_sources, declarations = [], [], []
    # On parcourt group.drop_duplicates(ACQUISITION_KEYS).iterrows() ; (_, link) désigne l’élément
    # courant à chaque passage dans la boucle.
    for _, link in group.drop_duplicates(ACQUISITION_KEYS).iterrows():
        # Cette branche traite le cas où la condition flag(link['eligible_for_new_anomaly_checks'])
        # n’est pas remplie.
        if not flag(link["eligible_for_new_anomaly_checks"]):
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On construit values comme une liste à partir de v.strip(), pour chaque v de
        # text(link.get('excel_vitiparcel')).split(' | ') en ne gardant que les éléments qui passent le
        # filtre.
        values = [
            v.strip()
            for v in text(link.get("excel_vitiparcel")).split(" | ")
            if v.strip()
        ]
        # On ajoute les éléments de values à declarations ; on n’ajoute pas la collection comme un seul
        # élément imbriqué.
        declarations.extend(values)
        # Cette branche traite le cas où la condition any((v.casefold() == 'terminé' for v in values))
        # n’est pas remplie.
        if not any(v.casefold() == "terminé" for v in values):
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On regroupe dans source ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        source = {
            # On renseigne l’identifiant normalisé de l’acquisition sous la clé
            # 'acquisition_id_normalise'.
            "acquisition_id_normalise": text(link["acquisition_id_normalise"]),
            # On associe la clé 'excel_vitiparcel' à cette valeur dans cet objet.
            "excel_vitiparcel": text(link.get("excel_vitiparcel")),
            # On associe la clé 'source_files' à cette valeur dans cet objet.
            "source_files": text(link.get("excel_source_files")),
            # On associe la clé 'source_rows' à cette valeur dans cet objet.
            "source_rows": text(link.get("excel_source_row_numbers")),
        }
        # On prépare reasons comme liste vide ; on la remplira au fil des opérations suivantes.
        reasons = []
        # On vérifie ce cas avant la suite : int(link['acquisition_passage_count']) diffère de 1.
        if int(link["acquisition_passage_count"]) != 1:
            # On ajoute 'Acquisition associée à plusieurs passages' à la fin de reasons ; les éléments
            # précédents restent conservés.
            reasons.append("Acquisition associée à plusieurs passages")
        # Cette branche traite le cas où la condition flag(link['parcel_mapping_consistent']) n’est pas
        # remplie.
        if not flag(link["parcel_mapping_consistent"]):
            # On ajoute 'Association de mapping incohérente' à la fin de reasons ; les éléments
            # précédents restent conservés.
            reasons.append("Association de mapping incohérente")
        # Cette branche traite le cas où au moins un élément satisfait le test indiqué.
        if any(v.casefold() != "terminé" for v in values):
            # On ajoute 'Statuts Vitiparcel contradictoires entre lignes Excel' à la fin de reasons ;
            # les éléments précédents restent conservés.
            reasons.append("Statuts Vitiparcel contradictoires entre lignes Excel")
        # Cette branche traite le cas où les explications regroupées est évalué comme vrai.
        if reasons:
            # On garde dans source['ambiguity_reason'] le texte formé en réunissant les éléments avec '
            # | ' comme séparateur.
            source["ambiguity_reason"] = " | ".join(reasons)
            # On ajoute source à la fin de ambiguous_sources ; les éléments précédents restent
            # conservés.
            ambiguous_sources.append(source)
        else:
            # On ajoute source à la fin de done_sources ; les éléments précédents restent conservés.
            done_sources.append(source)
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'passage_excel_vitiparcel_values' à cette valeur dans cet objet.
        "passage_excel_vitiparcel_values": " | ".join(dict.fromkeys(declarations)),
        # On associe la clé 'passage_excel_vitiparcel_done' à cette valeur dans cet objet.
        "passage_excel_vitiparcel_done": bool(done_sources),
        # On associe la clé 'passage_excel_vitiparcel_ambiguous' à cette valeur dans cet objet.
        "passage_excel_vitiparcel_ambiguous": bool(ambiguous_sources),
        # On associe la clé 'passage_excel_done_sources_json' à cette valeur dans cet objet.
        "passage_excel_done_sources_json": json.dumps(done_sources, ensure_ascii=False),
        # On associe la clé 'passage_excel_ambiguous_sources_json' à cette valeur dans cet objet.
        "passage_excel_ambiguous_sources_json": json.dumps(
            # On choisit ici si les caractères accentués doivent être échappés dans le JSON.
            ambiguous_sources, ensure_ascii=False
        ),
    }


# On interprète le passage à partir de son contexte Excel et des preuves qui lui sont rattachées.
def classify_passage(row: pd.Series) -> dict:
    """Sépare les preuves, la déclaration de fin et la demande de vérification."""
    # On garde dans eligible le résultat de cette comparaison : int(row['eligible_acquisitions_count'])
    # est supérieur à 0.
    eligible = int(row["eligible_acquisitions_count"]) > 0
    # On garde dans done la valeur de l’indicateur interprétée par le helper de ce module.
    done = flag(row["passage_excel_vitiparcel_done"])
    # On garde dans ambiguous la valeur de l’indicateur interprétée par le helper de ce module.
    ambiguous = flag(row["passage_excel_vitiparcel_ambiguous"])
    # On construit errors comme une liste à partir de text(row.get(c)), pour chaque c de
    # ('passage_error', 'vitimap_error', 'vitiparcel_error') en ne gardant que les éléments qui passent
    # le filtre.
    errors = [
        text(row.get(c))
        for c in ("passage_error", "vitimap_error", "vitiparcel_error")
        if text(row.get(c))
    ]
    # Une erreur stocks/passage rend le critère non vérifiable, jamais absent.
    ready_verifiable = not (
        text(row.get("passage_error")) or text(row.get("vitiparcel_error"))
    )
    # On garde dans stocks la valeur de l’indicateur interprétée par le helper de ce module.
    stocks = flag(row["stocks_json_exists"])
    # On garde dans non_healthy la valeur de l’indicateur interprétée par le helper de ce module.
    non_healthy = flag(row["has_non_healthy_status"])
    # On garde dans count la conversion numérique de float(text(row['stock_status_count']) or '0') en
    # entier.
    count = int(float(text(row["stock_status_count"]) or "0"))
    # On choisit la valeur de ready selon ce test : ready_verifiable est évalué comme vrai. Les deux
    # résultats possibles restent définis explicitement ici.
    ready = (stocks and non_healthy) if ready_verifiable else pd.NA
    # On prévoit le cas où ready_verifiable est évalué comme faux, par exemple une valeur vide selon
    # son type.
    if not ready_verifiable:
        # On utilise ce texte pour observation ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        observation = "Non vérifiable — erreur de lecture"
    # On prévoit le cas où stocks est évalué comme faux, par exemple une valeur vide selon son type.
    elif not stocks:
        # On utilise ce texte pour observation ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        observation = "Création non démontrée — fichier de stocks non détecté"
    # Cette branche traite le cas où non_healthy est évalué comme vrai.
    elif non_healthy:
        # On utilise ce texte pour observation ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        observation = "Critère du livrable prêt à livrer satisfait"
    # On vérifie ce cas avant la suite : count correspond à 0.
    elif count == 0:
        # On utilise ce texte pour observation ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        observation = (
            "Fichier présent — aucun statut reconnu, livrable prêt non démontré"
        )
    else:
        # On utilise ce texte pour observation ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        observation = (
            "Fichier présent — aucun statut non sain, livrable prêt non démontré"
        )
    # On calcule divergence avec ces conditions liées par and ; Python s’arrête dès qu’une valeur est
    # évaluée comme fausse.
    divergence = eligible and done and ready_verifiable and not bool(ready)
    # On calcule technical_review avec ces conditions liées par and ; Python s’arrête dès qu’une valeur
    # est évaluée comme fausse.
    technical_review = eligible and bool(errors)
    # On calcule structure_gap avec ces conditions liées par and ; Python s’arrête dès qu’une valeur
    # est évaluée comme fausse.
    structure_gap = eligible and (
        not flag(row["passage_created"]) or not flag(row["vitimap_created"])
    )
    # On prévoit le cas où eligible est évalué comme faux, par exemple une valeur vide selon son type.
    if not eligible:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Hors contrôles — toutes les acquisitions associées sont exclues"
        # On utilise ce texte pour action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        action = "Aucune vérification demandée à ce stade ; observations conservées."
    # Cette branche traite le cas où technical_review est évalué comme vrai.
    elif technical_review:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Erreur technique — preuves du passage non vérifiables"
        # On utilise ce texte pour action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        action = "Vérifier la lecture ; ne pas conclure à une absence ni lancer un retraitement."
    # Cette branche traite le cas où divergence est évalué comme vrai.
    elif divergence:
        # On prévoit le cas où stocks est évalué comme faux, par exemple une valeur vide selon son
        # type.
        if not stocks:
            # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à
            # cet endroit.
            category = "Divergence — Vitiparcel terminé déclaré, stocks absent"
        # On vérifie ce cas avant la suite : count correspond à 0.
        elif count == 0:
            # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à
            # cet endroit.
            category = "Divergence — Vitiparcel terminé déclaré, aucun statut reconnu"
        else:
            # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à
            # cet endroit.
            category = "Divergence — Vitiparcel terminé déclaré, critère du livrable prêt non satisfait"
        # On utilise ce texte pour action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        action = "Vérifier la divergence entre déclaration Excel et preuves du passage ; aucun retraitement automatique."
    # Cette branche traite le cas où structure_gap est évalué comme vrai.
    elif structure_gap:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Écart de structure — dossier passage ou Vitimap non démontré"
        # On utilise ce texte pour action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        action = "Examiner les preuves de dossier et Vitimap manquantes."
    # Cette branche traite le cas où ready_verifiable est évalué comme vrai et le contrôle bool(ready)
    # est positif.
    elif ready_verifiable and bool(ready):
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Critère Vitiparcel prêt à livrer satisfait"
        # On utilise ce texte pour action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        action = "Aucune vérification supplémentaire déduite de ce critère."
    # Cette branche traite le cas où ambiguous est évalué comme vrai.
    elif ambiguous:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Déclaration Vitiparcel ambiguë — attente du passage non confirmée"
        # On utilise ce texte pour action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        action = "Conserver l’ambiguïté ; ne pas propager Terminé à tous les passages ni créer une alerte automatique."
    # Cette branche traite le cas où le contrôle text(row['passage_excel_vitiparcel_values']) est
    # positif.
    elif text(row["passage_excel_vitiparcel_values"]):
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = "Avancement Vitiparcel déclaré — fin non déclarée"
        # On utilise ce texte pour action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        action = "Conserver l’avancement ; aucun oubli ni retard déduit."
    else:
        # On utilise ce texte pour category ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        category = (
            "Attente Vitiparcel non renseignée — aucune nouvelle alerte automatique"
        )
        # On utilise ce texte pour action ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        action = "Conserver les preuves ; ne pas interpréter un statut vide comme Terminé ou comme exclusion."
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'vitiparcel_ready_verifiable' à cette valeur dans cet objet.
        "vitiparcel_ready_verifiable": ready_verifiable,
        # On associe la clé 'vitiparcel_ready_for_delivery' à cette valeur dans cet objet.
        "vitiparcel_ready_for_delivery": ready,
        # On associe la clé 'vitiparcel_delivery_observation' à cette valeur dans cet objet.
        "vitiparcel_delivery_observation": observation,
        # On associe la clé 'passage_business_category' à cette valeur dans cet objet.
        "passage_business_category": category,
        # On associe la clé 'passage_next_action' à cette valeur dans cet objet.
        "passage_next_action": action,
        # On associe la clé 'passage_vitiparcel_divergence' à cette valeur dans cet objet.
        "passage_vitiparcel_divergence": divergence,
        # On associe la clé 'passage_technical_review_required' à cette valeur dans cet objet.
        "passage_technical_review_required": technical_review,
        # On associe la clé 'passage_structure_review_required' à cette valeur dans cet objet.
        "passage_structure_review_required": structure_gap,
        # On associe la clé 'passage_review_candidate' à cette valeur dans cet objet.
        "passage_review_candidate": divergence or technical_review or structure_gap,
    }


# On rapproche les suivis et les observations pour produire les résultats par acquisition et passage.
def reconcile(excel_rows, evidence, associations, passages, decisions=None):
    # On répartit les valeurs renvoyées par validate_inputs entre (e, a, p) ; leur ordre doit
    # correspondre à celui prévu par cet appel.
    e, a, p = validate_inputs(evidence, associations, passages)
    # On garde dans context la valeur renvoyée par prepare_context.
    context = prepare_context(excel_rows)
    # On récupère context['excel_vineyard_key'] et on le garde dans context['vineyard_key'] pour la
    # suite.
    context["vineyard_key"] = context["excel_vineyard_key"]
    # Le statut repris par l'extracteur ne doit pas écraser la consolidation actuelle.
    if "excel_pipeline_status" in e:
        # On garde dans e les données de e avec les noms modifiés selon la correspondance.
        e = e.rename(
            # On décrit les colonnes à présenter, distinctes des lignes de données.
            columns={"excel_pipeline_status": "extractor_excel_pipeline_status"}
        )
    # On rapproche les tableaux avec les clés précisées ; le type de jointure ci-dessous décide
    # quelles lignes sont conservées.
    result = e.merge(
        context,
        # On donne les clés communes utilisées pour rapprocher les deux tableaux.
        on=ACQUISITION_KEYS,
        # On fixe le type de jointure ; ce choix détermine quelles lignes sans correspondance restent
        # présentes.
        how="left",
        # On demandu contrôle de cardinalité indiqué pour ne pas accepter un rapprochement
        # inattendu.
        validate="one_to_one",
        indicator="excel_match_status",
    )
    # On garde dans d la valeur renvoyée par prepare_decisions.
    d = prepare_decisions(decisions)
    # On vérifie ce cas avant la suite : d est renseigné (différent de None).
    if d is not None:
        # On rapproche les tableaux avec les clés précisées ; le type de jointure ci-dessous décide
        # quelles lignes sont conservées.
        unknown = d.merge(
            # On donne les clés communes utilisées pour rapprocher les deux tableaux.
            e[ACQUISITION_KEYS], on=ACQUISITION_KEYS, how="left", indicator=True
        )
        # Cette branche traite le cas où la condition unknown['_merge'].eq('both').all() n’est pas
        # remplie.
        if not unknown["_merge"].eq("both").all():
            # On interrompt cette branche avec ValueError : 'Décision hors du périmètre contrôlé :
            # sélectionner le bon fichier de décisions.'.
            raise ValueError(
                "Décision hors du périmètre contrôlé : sélectionner le bon fichier de décisions."
            )
        # On rapproche les tableaux avec les clés précisées ; le type de jointure ci-dessous décide
        # quelles lignes sont conservées.
        result = result.merge(d, on=ACQUISITION_KEYS, how="left", validate="one_to_one")
    else:
        # On parcourt ['decision_full_processing_expected', 'decision_reason', 'decision_source… ;
        # column désigne l’élément courant à chaque passage dans la boucle.
        for column in [
            "decision_full_processing_expected",
            "decision_reason",
            "decision_source",
            "decision_at",
        ]:
            # On commence result[column] avec un texte vide, à compléter uniquement si la suite apporte
            # une information.
            result[column] = ""
    # Seules les associations individuellement incohérentes sont rapprochées
    # de la documentation. Une synthèse False sans détail reste à vérifier.
    mismatch_parcels = {}
    # On parcourt a.groupby(ACQUISITION_KEYS, sort=False) ; (key, group) désigne l’élément courant à
    # chaque passage dans la boucle.
    for key, group in a.groupby(ACQUISITION_KEYS, sort=False):
        # On sélectionne dans group.loc les éléments désignés par
        # (group['parcel_mapping_consistent'].map(lambda value: text(value).casefold() in {'fal… ;
        # mismatches recevra cette sélection.
        mismatches = group.loc[
            group["parcel_mapping_consistent"].map(
                lambda value: text(value).casefold() in {"false", "0", "non"}
            ),
            "parcel_name",
        ]
        # On garde dans mismatch_parcels[key] une liste matérialisée à partir de
        # dict.fromkeys(mismatches.map(text)).
        mismatch_parcels[key] = list(dict.fromkeys(mismatches.map(text)))
    # On construit result['relationship_observed_gaps_json'] comme une liste à partir de
    # json.dumps(mismatch_parcels.get((row['vineyard_key'], row['acqui…, pour chaque (_, row) de
    # result.iterrows().
    result["relationship_observed_gaps_json"] = [
        json.dumps(
            mismatch_parcels.get(
                (row["vineyard_key"], row["acquisition_join_key"]), []
            ),
            # On choisit ici si les caractères accentués doivent être échappés dans le JSON.
            ensure_ascii=False,
        )
        for _, row in result.iterrows()
    ]
    # On garde dans qualifiers un tableau pandas construit avec les données indiquées.
    qualifiers = pd.DataFrame(
        [classify_processing(row) for _, row in result.iterrows()], index=result.index
    )
    # On garde dans result l’assemblage des tableaux suivant l’axe et les options indiqués.
    result = pd.concat([result, qualifiers], axis=1)
    # On utilise ce texte pour result['reconciliation_mode'] ; il ne dépend pas d’une valeur récupérée
    # ailleurs à cet endroit.
    result["reconciliation_mode"] = "excel_vs_live_nas"
    # On garde dans result['reconciled_at'] la représentation ISO de datetime.now(timezone.utc).
    result["reconciled_at"] = datetime.now(timezone.utc).isoformat()
    # On construit business_fields comme une liste à partir de c, pour chaque c de result.columns en ne
    # gardant que les éléments qui passent le filtre.
    business_fields = [
        c
        for c in result.columns
        if c.startswith("excel_")
        # Ce cas est aussi retenu si c commence par le texte 'processing_business'.
        or c.startswith("processing_business")
        # Ce cas est aussi retenu si c commence par le texte 'processing_expectation'.
        or c.startswith("processing_expectation")
        # Ce cas est aussi retenu si c commence par le texte 'processing_new_alert'.
        or c.startswith("processing_new_alert")
        # Ce cas est aussi retenu si c commence par le texte 'processing_decision'.
        or c.startswith("processing_decision")
        # Ce cas est aussi retenu si c commence par le texte 'decision_'.
        or c.startswith("decision_")
        # Ce cas est aussi retenu si c commence par le texte 'excluded_'.
        or c.startswith("excluded_")
        # Ce cas est aussi retenu si c commence par le texte 'eligible_'.
        or c.startswith("eligible_")
        # Ce cas est aussi retenu si c commence par le texte 'excel_exclusion'.
        or c.startswith("excel_exclusion")
        # Ce cas est aussi retenu si c commence par le texte 'acquisition_new_'.
        or c.startswith("acquisition_new_")
        # Ce cas est aussi retenu si c commence par le texte 'relationship_'.
        or c.startswith("relationship_")
    ]
    # On rapproche les tableaux avec les clés précisées ; le type de jointure ci-dessous décide
    # quelles lignes sont conservées.
    enriched_associations = a.merge(
        result[ACQUISITION_KEYS + business_fields],
        # On donne les clés communes utilisées pour rapprocher les deux tableaux.
        on=ACQUISITION_KEYS,
        # On fixe le type de jointure ; ce choix détermine quelles lignes sans correspondance restent
        # présentes.
        how="left",
        # On demandu contrôle de cardinalité indiqué pour ne pas accepter un rapprochement
        # inattendu.
        validate="many_to_one",
    )
    # On garde dans enriched_associations['acquisition_passage_count'] la valeur renvoyée par
    # enriched_associations.groupby(ACQUISITION_KEYS)['passage_name'].transform pour 'size'.
    enriched_associations["acquisition_passage_count"] = enriched_associations.groupby(
        ACQUISITION_KEYS
    )["passage_name"].transform("size")
    # Aucun héritage d'exclusion acquisition au niveau passage partagé.
    enriched_passages = p.copy()
    # On construit enriched_passages['stocks_observation_interpretation'] comme une liste à partir de
    # passage_interpretation(row), pour chaque (_, row) de p.iterrows().
    enriched_passages["stocks_observation_interpretation"] = [
        passage_interpretation(row) for _, row in p.iterrows()
    ]
    # On utilise ce texte pour enriched_passages['vitiparcel_business_rule_status'] ; il ne dépend pas
    # d’une valeur récupérée ailleurs à cet endroit.
    enriched_passages["vitiparcel_business_rule_status"] = (
        "Règle confirmée — stocks présent ET au moins un statut non sain pour le livrable prêt à livrer"
    )
    # On prépare counts comme liste vide ; on la remplira au fil des opérations suivantes.
    counts = []
    # On parcourt enriched_associations.groupby(PASSAGE_KEYS, dropna=False) ; (key, group) désigne
    # l’élément courant à chaque passage dans la boucle.
    for key, group in enriched_associations.groupby(PASSAGE_KEYS, dropna=False):
        # On retire les répétitions selon les colonnes choisies, pas selon une ressemblance visuelle.
        distinct = group.drop_duplicates(ACQUISITION_KEYS)
        # On garde dans eligible_count la conversion numérique de
        # distinct['eligible_for_new_anomaly_checks'].astype(bool).sum() en entier.
        eligible_count = int(
            distinct["eligible_for_new_anomaly_checks"].astype(bool).sum()
        )
        # On ajoute dict(zip(PASSAGE_KEYS, key), eligible_acquisitions_count=eligible_count,
        # excluded_acquisi… à la fin de counts ; les éléments précédents restent conservés.
        counts.append(
            dict(
                zip(PASSAGE_KEYS, key),
                eligible_acquisitions_count=eligible_count,
                excluded_acquisitions_count=len(distinct) - eligible_count,
                **passage_excel_context(group),
            )
        )
    # Cette branche traite le cas où les compteurs est évalué comme vrai.
    if counts:
        # On rapproche les tableaux avec les clés précisées ; le type de jointure ci-dessous décide
        # quelles lignes sont conservées.
        enriched_passages = enriched_passages.merge(
            # On donne les clés communes utilisées pour rapprocher les deux tableaux.
            pd.DataFrame(counts), on=PASSAGE_KEYS, how="left", validate="one_to_one"
        )
    else:
        # On fixe enriched_passages['eligible_acquisitions_count'] à 0 pour cette étape.
        enriched_passages["eligible_acquisitions_count"] = 0
        # On fixe enriched_passages['excluded_acquisitions_count'] à 0 pour cette étape.
        enriched_passages["excluded_acquisitions_count"] = 0
        # On parcourt les couples (field, default) de passage_excel_context(enriched_associations) :
        # on garde ensemble la clé et sa valeur au lieu des traiter dans deux listes séparées.
        for field, default in passage_excel_context(enriched_associations).items():
            # On garde default sous le nom enriched_passages[field] ; cette affectation ne copie pas à
            # elle seule un objet mutable.
            enriched_passages[field] = default
    # On garde dans enriched_passages['passage_control_scope'] les valeurs de
    # enriched_passages['eligible_acquisitions_count'] transformées par la fonction ou la
    # correspondance indiquée.
    enriched_passages["passage_control_scope"] = enriched_passages[
        "eligible_acquisitions_count"
    ].map(
        lambda count: "Dans le périmètre des contrôles"
        if count
        else "Hors contrôles — toutes les acquisitions associées sont exclues"
    )
    # On garde dans passage_qualifiers un tableau pandas construit avec les données indiquées.
    passage_qualifiers = pd.DataFrame(
        [classify_passage(row) for _, row in enriched_passages.iterrows()],
        index=enriched_passages.index,
    )
    # On traite à part le tableau enriched_passages lorsqu’il est vide.
    if enriched_passages.empty:
        # On parcourt ('vitiparcel_ready_verifiable', 'vitiparcel_ready_for_delivery', 'vitipar… ;
        # field désigne l’élément courant à chaque passage dans la boucle.
        for field in (
            "vitiparcel_ready_verifiable",
            "vitiparcel_ready_for_delivery",
            "vitiparcel_delivery_observation",
            "passage_business_category",
            "passage_next_action",
            "passage_vitiparcel_divergence",
            "passage_technical_review_required",
            "passage_structure_review_required",
            "passage_review_candidate",
        ):
            # On garde dans passage_qualifiers[field] une série pandas avec les valeurs et l’index
            # fournis.
            passage_qualifiers[field] = pd.Series(dtype="object")
    # On garde dans enriched_passages l’assemblage des tableaux suivant l’axe et les options indiqués.
    enriched_passages = pd.concat([enriched_passages, passage_qualifiers], axis=1)
    # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return result, enriched_associations, enriched_passages


def acquisition_display_reasons(row: pd.Series) -> list[str]:
    """Explique les indicateurs existants ; ne recalcule aucune décision métier."""
    # On prépare reasons comme liste vide ; on la remplira au fil des opérations suivantes.
    reasons = []
    # Cette branche traite le cas où le contrôle flag(row.get('relationship_review_required', pd.NA))
    # est positif.
    if flag(row.get("relationship_review_required", pd.NA)):
        # Cette branche traite le cas où la condition flag(row.get('found_in_parcel_mapping', pd.NA))
        # n’est pas remplie.
        if not flag(row.get("found_in_parcel_mapping", pd.NA)):
            # On ajoute 'Rattachement à une parcelle non démontré dans le mapping lu.' à la fin de
            # reasons ; les éléments précédents restent conservés.
            reasons.append(
                "Rattachement à une parcelle non démontré dans le mapping lu."
            )
        # Cette branche traite le cas où la condition flag(row.get('found_in_passage_mapping', pd.NA))
        # n’est pas remplie.
        if not flag(row.get("found_in_passage_mapping", pd.NA)):
            # On ajoute 'Aucun rattachement à un passage démontré dans le mapping lu ; livrables non
            # vérifiables.' à la fin de reasons ; les éléments précédents restent conservés.
            reasons.append(
                "Aucun rattachement à un passage démontré dans le mapping lu ; livrables non vérifiables."
            )
        # On vérifie ce cas avant la suite : text(row.get('parcel_mapping_consistent')).casefold()
        # appartient à {'false', '0', 'non'}.
        if text(row.get("parcel_mapping_consistent")).casefold() in {
            "false",
            "0",
            "non",
        }:
            # On ajoute 'Incohérence entre les mappings parcelle et passage, non neutralisée par la
            # documentation… à la fin de reasons ; les éléments précédents restent conservés.
            reasons.append(
                "Incohérence entre les mappings parcelle et passage, non neutralisée par la documentation Excel."
            )
    # Cette branche traite le cas où le contrôle flag(row.get('raw_evidence_review_required', pd.NA))
    # est positif et la condition text(row.get('raw_error')) n’est pas remplie.
    if flag(row.get("raw_evidence_review_required", pd.NA)) and not text(
        row.get("raw_error")
    ):
        # Cette branche traite le cas où la condition flag(row.get('found_in_raw_live', pd.NA)) n’est
        # pas remplie.
        if not flag(row.get("found_in_raw_live", pd.NA)):
            # On ajoute 'Présence du dossier Brut non démontrée.' à la fin de reasons ; les éléments
            # précédents restent conservés.
            reasons.append("Présence du dossier Brut non démontrée.")
        else:
            # On ajoute 'Sauvegarde PNG native LEFT et RIGHT non démontrée pour les deux côtés.' à la
            # fin de reasons ; les éléments précédents restent conservés.
            reasons.append(
                "Sauvegarde PNG native LEFT et RIGHT non démontrée pour les deux côtés."
            )
    # Cette branche traite le cas où le contrôle flag(row.get('processing_new_alert_candidate', pd.NA))
    # est positif.
    if flag(row.get("processing_new_alert_candidate", pd.NA)):
        # On ajoute 'Traitement WEBP LEFT et RIGHT non démontré : ' +
        # text(row.get('processing_business_categ… à la fin de reasons ; les éléments précédents
        # restent conservés.
        reasons.append(
            "Traitement WEBP LEFT et RIGHT non démontré : "
            + text(row.get("processing_business_category"))
            + "."
        )
    # Cette branche traite le cas où le contrôle flag(row.get('technical_review_required', pd.NA)) est
    # positif.
    if flag(row.get("technical_review_required", pd.NA)):
        # On ajoute 'Erreur technique / preuve non vérifiable : ' + (text(row.get('technical_errors'))
        # or 'co… à la fin de reasons ; les éléments précédents restent conservés.
        reasons.append(
            "Erreur technique / preuve non vérifiable : "
            + (text(row.get("technical_errors")) or "consulter les colonnes d’erreur")
            + "."
        )
    # On remet reasons or ['Consulter les indicateurs détaillés du CSV acquisitions.'] à l’appelant ;
    # les étapes suivantes de cette fonction ne sont plus parcourues.
    return reasons or ["Consulter les indicateurs détaillés du CSV acquisitions."]


# On rassemble dans ACQUISITION_DISPLAY_CONTEXT les 4 éléments explicitement indiqués, en conservant
# leur structure.
ACQUISITION_DISPLAY_CONTEXT = (
    ("Périmètre", "excel_perimeter"),
    ("WEBP", "excel_visual_processing"),
    ("Vitimap", "excel_vitimap"),
    ("Vitiparcel", "excel_vitiparcel"),
)


def acquisition_display_groups(candidates: pd.DataFrame) -> list[dict]:
    """Regroupe seulement l'affichage ; garde les lignes et leur ordre intactes.

    Les motifs et les quatre valeurs Excel affichées doivent être identiques.
    Les commentaires/problèmes particuliers sont conservés par acquisition.
    Aucune cause commune n'est inférée de ce regroupement d'observations.
    """
    # On crée le dictionnaire vide groups pour y ranger ensuite les éléments par clé.
    groups = {}
    # On parcourt candidates.iterrows() ; (_, row) désigne l’élément courant à chaque passage dans la
    # boucle.
    for _, row in candidates.iterrows():
        # On garde dans reasons une séquence non modifiable construite à partir de
        # acquisition_display_reasons(row).
        reasons = tuple(acquisition_display_reasons(row))
        # On garde dans context une séquence non modifiable construite à partir de
        # (text(row.get(field)) for _, field in ACQUISITION_DISPLAY_CONTEXT).
        context = tuple(
            text(row.get(field)) for _, field in ACQUISITION_DISPLAY_CONTEXT
        )
        # On rassemble dans key les 2 éléments explicitement indiqués, en conservant leur structure.
        key = (reasons, context)
        # On vérifie ce cas avant la suite : la clé de l’élément ne figure pas dans groups.
        if key not in groups:
            # On regroupe dans groups[key] ces champs nommés ; on pourra les retrouver par leur clé
            # plutôt que par leur position.
            groups[key] = {"reasons": reasons, "context": context, "rows": []}
        # On ajoute row à la fin de groups[key]['rows'] ; les éléments précédents restent conservés.
        groups[key]["rows"].append(row)
    # On fournit à l’appelant une liste matérialisée à partir de groups.values().
    return list(groups.values())


def extraction_id_from_path(path: Path) -> str | None:
    """Récupère le run-id du fichier explicitement sélectionné, pour l'affichage seul."""
    # On garde dans match la première correspondance du motif trouvée dans le texte.
    match = re.search(
        r"_live_nas_evidence_(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)\.csv$", path.name
    )
    # On prévoit le cas où match est évalué comme faux, par exemple une valeur vide selon son type.
    if not match:
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None
    # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
    try:
        # On appelle datetime.strptime avec match.group(1).
        datetime.strptime(match.group(1), "%Y-%m-%dT%H-%M-%SZ")
    except ValueError:
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None
    # On fournit à l’appelant la valeur renvoyée par match.group pour 1.
    return match.group(1)


def print_summary(results, paths, vineyard, run_id=None):
    """Présentation console uniquement : aucune modification des résultats."""
    # On répartit les éléments de results entre (acquisitions, _, passages), dans l’ordre indiqué.
    acquisitions, _, passages = results
    # On fixe width à 86 pour cette étape.
    width = 86
    # On multiplie ces valeurs pour construire line.
    line = "=" * width

    def heading(label, emoji=""):
        # On retient pour encoding la première valeur évaluée comme vraie dans cette chaîne de replis ;
        # une valeur vide fera donc passer à la suivante.
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        # On tente ce bloc et on traite séparément les erreurs prévues : (UnicodeEncodeError,
        # LookupError).
        try:
            # On appelle emoji.encode avec encoding.
            emoji.encode(encoding)
        except (UnicodeEncodeError, LookupError):
            # On commence emoji avec un texte vide, à compléter uniquement si la suite apporte une
            # information.
            emoji = ""
        # On affiche f"{(emoji + ' ' if emoji else '')}{label}" dans la sortie du programme.
        print(f"{emoji + ' ' if emoji else ''}{label}")

    def counter(label, count):
        # Conserver la valeur sur une ligne distincte des éventuelles continuations.
        pieces = textwrap.wrap(label, width=width - 10, break_long_words=False)
        # On affiche f'  {pieces[0]:<{width - 10}} {int(count):>5}' dans la sortie du programme.
        print(f"  {pieces[0]:<{width - 10}} {int(count):>5}")
        # On parcourt pieces[1:] ; piece désigne l’élément courant à chaque passage dans la boucle.
        for piece in pieces[1:]:
            # On affiche f'  {piece}' dans la sortie du programme.
            print(f"  {piece}")

    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On affiche line dans la sortie du programme.
    print(line)
    # On appelle heading avec 'RAPPROCHEMENT EXCEL / PREUVES NAS'.
    heading("RAPPROCHEMENT EXCEL / PREUVES NAS", "📊")
    # On affiche line dans la sortie du programme.
    print(line)
    # On affiche f'  Vignoble       : {vineyard}' dans la sortie du programme.
    print(f"  Vignoble       : {vineyard}")
    # On garde dans observed la forme textuelle préparée par text pour
    # acquisitions.iloc[0].get('checked_at').
    observed = text(acquisitions.iloc[0].get("checked_at"))
    # On affiche cette information de suivi dans la sortie du programme.
    print(f"  Run-id NAS     : {run_id or 'non renseigné — voir fichiers d’entrée'}")
    # On affiche f'  Observation NAS: {observed}' dans la sortie du programme.
    print(f"  Observation NAS: {observed}")
    # On affiche cette information de suivi dans la sortie du programme.
    print("  Sources        : suivi Excel ingéré + CSV de preuves extraites du NAS")
    # On affiche cette information de suivi dans la sortie du programme.
    print("  Mode           : rapprochement local — aucune nouvelle lecture du NAS")
    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        f"  {len(acquisitions)} acquisitions  |  {len(results[1])} associations  |  {len(passages)} passages distincts"
    )

    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On affiche le texte '1. ACQUISITIONS' dans la sortie du programme.
    print("1. ACQUISITIONS")
    # On affiche '-' * width dans la sortie du programme.
    print("-" * width)
    # On parcourt acquisitions['processing_business_category'].value_counts().items() ; (category,
    # count) désigne l’élément courant à chaque passage dans la boucle.
    for category, count in (
        acquisitions["processing_business_category"].value_counts().items()
    ):
        # On appelle counter avec category.
        counter(category, count)
    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On sélectionne dans acquisitions.loc les éléments désignés par
    # acquisitions['acquisition_new_anomaly_candidate'].map(flag) ; acquisition_candidates recevra
    # cette sélection.
    acquisition_candidates = acquisitions.loc[
        acquisitions["acquisition_new_anomaly_candidate"].map(flag)
    ]
    # On appelle counter avec 'Acquisitions candidates à une nouvelle vérification'.
    counter(
        "Acquisitions candidates à une nouvelle vérification",
        len(acquisition_candidates),
    )
    # Cette branche traite le cas où le contrôle len(acquisition_candidates) est positif.
    if len(acquisition_candidates):
        # On garde dans groups la valeur renvoyée par acquisition_display_groups.
        groups = acquisition_display_groups(acquisition_candidates)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"  Acquisitions regroupées par motifs et contexte Excel : {len(groups)} groupe(s)"
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print("  Même profil de vérification ne signifie pas même cause démontrée.")

        def detail(label, value):
            # On parcourt textwrap.wrap(f'{label} : {value}', width=width - 6, break_long_words=Fal… ;
            # piece désigne l’élément courant à chaque passage dans la boucle.
            for piece in textwrap.wrap(
                f"{label} : {value}", width=width - 6, break_long_words=False
            ):
                # On affiche f'      {piece}' dans la sortie du programme.
                print(f"      {piece}")

        # On parcourt groups en gardant aussi sa position dans (number, group) ; le comptage commence à
        # zéro.
        for number, group in enumerate(groups, start=1):
            # On récupère les lignes dans group et on le garde dans rows pour la suite.
            rows = group["rows"]
            # On affiche cette information de suivi dans la sortie du programme.
            print()
            # On affiche f'  Groupe {number} — {len(rows)} acquisition(s)' dans la sortie du programme.
            print(f"  Groupe {number} — {len(rows)} acquisition(s)")
            # On parcourt les explications regroupées dans group ; reason désigne l’élément courant à
            # chaque passage dans la boucle.
            for reason in group["reasons"]:
                # On appelle detail avec 'Motif'.
                detail("Motif", reason)
            # On garde dans context le texte formé en réunissant les éléments avec ' | ' comme
            # séparateur.
            context = " | ".join(
                f"{label}={value or 'non renseigné'}"
                for (label, _), value in zip(
                    ACQUISITION_DISPLAY_CONTEXT, group["context"]
                )
            )
            # On appelle detail avec 'Excel'.
            detail("Excel", context)
            # On affiche le texte '    Acquisitions concernées :' dans la sortie du programme.
            print("    Acquisitions concernées :")
            # On parcourt les lignes ; row désigne l’élément courant à chaque passage dans la boucle.
            for row in rows:
                # On affiche f"    - {row['acquisition_id_normalise']}" dans la sortie du programme.
                print(f"    - {row['acquisition_id_normalise']}")
            # On parcourt (('Problème Excel', 'excel_problems'), ('Commentaire Excel', 'excel_comme… ;
            # (label, field) désigne l’élément courant à chaque passage dans la boucle.
            for label, field in (
                ("Problème Excel", "excel_problems"),
                ("Commentaire Excel", "excel_comments"),
                ("Résolution déclarée dans Excel", "excel_resolution_statuses"),
            ):
                # On construit values comme une liste à partir de text(row.get(field)), pour chaque row
                # de rows.
                values = [text(row.get(field)) for row in rows]
                # Cette branche traite le cas où le test values[0] est satisfait et tous les éléments
                # satisfont le test indiqué.
                if values[0] and all(value == values[0] for value in values):
                    # On appelle detail avec label + (' commun' if len(rows) > 1 else '').
                    detail(label + (" commun" if len(rows) > 1 else ""), values[0])
                else:
                    # On parcourt zip(rows, values) ; (row, value) désigne l’élément courant à chaque
                    # passage dans la boucle.
                    for row, value in zip(rows, values):
                        # Cette branche traite le cas où la valeur reçue est évalué comme vrai.
                        if value:
                            # On appelle detail avec f"{label} [{row['acquisition_id_normalise']}]".
                            detail(
                                f"{label} [{row['acquisition_id_normalise']}]", value
                            )
            # On affiche cette information de suivi dans la sortie du programme.
            print()

    else:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "  Aucun nouveau cas signalé au niveau acquisition selon les règles actuelles."
        )
    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On appelle counter avec 'Acquisitions avec un écart de mapping déjà documenté dans Excel'.
    counter(
        "Acquisitions avec un écart de mapping déjà documenté dans Excel",
        acquisitions["relationship_known_documented"].sum(),
    )
    # On sélectionne dans acquisitions.loc les éléments désignés par
    # acquisitions['relationship_known_documented'].map(flag) ; known_mapping_rows recevra cette
    # sélection.
    known_mapping_rows = acquisitions.loc[
        acquisitions["relationship_known_documented"].map(flag)
    ]
    # On parcourt known_mapping_rows.iterrows() ; (_, row) désigne l’élément courant à chaque passage
    # dans la boucle.
    for _, row in known_mapping_rows.iterrows():
        # On affiche f"    - {row['acquisition_id_normalise']}" dans la sortie du programme.
        print(f"    - {row['acquisition_id_normalise']}")
        # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite,
        # car un JSON lisible n’est pas forcément un lot valide.
        covered = json.loads(
            text(row.get("relationship_documented_parcels_json")) or "[]"
        )
        # Cette branche traite le cas où covered est évalué comme vrai.
        if covered:
            # On affiche f"      Parcelle(s) concernée(s) : {', '.join(covered)}" dans la sortie du
            # programme.
            print(f"      Parcelle(s) concernée(s) : {', '.join(covered)}")
    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On affiche cette information de suivi dans la sortie du programme.
    print("  Les cas exclus restent visibles ; exclusion ne signifie pas résolution.")
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "  Le compteur de vérification inclut relations, PNG, WEBP et erreurs techniques."
    )

    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On affiche le texte '2. PASSAGES — bilan distinct des acquisitions' dans la sortie du programme.
    print("2. PASSAGES — bilan distinct des acquisitions")
    # On affiche '-' * width dans la sortie du programme.
    print("-" * width)
    # On traite à part le tableau passages lorsqu’il est vide.
    if passages.empty:
        # On inverse le masque ou les bits de acquisitions['found_in_passage_mapping'].map(flag) pour
        # obtenir missing_links ; avec pandas, cela inverse la sélection.
        missing_links = ~acquisitions["found_in_passage_mapping"].map(flag)
        # On combine ces masques avec & pour construire active_missing_links ; les parenthèses gardent
        # les comparaisons regroupées.
        active_missing_links = missing_links & acquisitions[
            "eligible_for_new_anomaly_checks"
        ].map(flag)
        # On affiche ce texte explicite dans la sortie du programme.
        print("  AUCUN PASSAGE IDENTIFIÉ DANS LE MAPPING LU POUR CE PÉRIMÈTRE.")
        # On appelle counter avec 'Acquisitions sans rattachement à un passage démontré'.
        counter(
            "Acquisitions sans rattachement à un passage démontré", missing_links.sum()
        )
        # On appelle counter avec 'Dont acquisitions dans le périmètre actif des contrôles'.
        counter(
            "Dont acquisitions dans le périmètre actif des contrôles",
            active_missing_links.sum(),
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print("  Aucun passage ne peut être contrôlé à partir de ces associations.")
        # On affiche ce texte explicite dans la sortie du programme.
        print("  Vitimap et Vitiparcel : sorties non vérifiables pour ce périmètre.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "  Cela ne prouve ni leur absence physique sur le NAS ni leur conformité."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print()
    # On regroupe dans short_labels ces champs nommés ; on pourra les retrouver par leur clé plutôt que
    # par leur position.
    short_labels = {
        "Attente Vitiparcel non renseignée — aucune nouvelle alerte automatique": "Statut Vitiparcel non renseigné dans le suivi Excel",
        "Déclaration Vitiparcel ambiguë — attente du passage non confirmée": "« Terminé » Excel ambigu",
        "Hors contrôles — toutes les acquisitions associées sont exclues": "Hors contrôles — toutes les acquisitions exclues",
    }
    # On parcourt les couples (category, count) de
    # passages['passage_business_category'].value_counts() : on garde ensemble la clé et sa valeur
    # au lieu des traiter dans deux listes séparées.
    for category, count in passages["passage_business_category"].value_counts().items():
        # On garde dans label le champ category de short_labels avec le repli indiqué si la clé est
        # absente.
        label = short_labels.get(category, category)
        # On sélectionne dans passages.loc les éléments désignés par
        # passages['passage_business_category'].eq(category) ; concerned recevra cette sélection.
        concerned = passages.loc[passages["passage_business_category"].eq(category)]
        # On garde dans ambiguity_reasons un ensemble vide, qui servira à repérer les valeurs déjà
        # rencontrées.
        ambiguity_reasons = set()
        # On vérifie ce cas avant la suite : category correspond à ce texte explicite.
        if (
            category
            == "Déclaration Vitiparcel ambiguë — attente du passage non confirmée"
        ):
            # On parcourt concerned['passage_excel_ambiguous_sources_json'] ; value désigne l’élément
            # courant à chaque passage dans la boucle.
            for value in concerned["passage_excel_ambiguous_sources_json"]:
                # On parcourt json.loads(text(value) or '[]') ; source désigne l’élément courant à
                # chaque passage dans la boucle.
                for source in json.loads(text(value) or "[]"):
                    # On complète cet ensemble avec les éléments fournis ; les doublons restent
                    # éliminés, sans notion de clé à remplacer.
                    ambiguity_reasons.update(
                        text(source.get("ambiguity_reason")).split(" | ")
                    )
            # On vérifie ce cas avant la suite : ambiguity_reasons correspond à {'Acquisition associée
            # à plusieurs passages'}.
            if ambiguity_reasons == {"Acquisition associée à plusieurs passages"}:
                # On utilise ce texte pour label ; il ne dépend pas d’une valeur récupérée ailleurs à
                # cet endroit.
                label = (
                    "« Terminé » Excel ambigu — acquisition liée à plusieurs passages"
                )
        # On appelle counter avec label.
        counter(label, count)
        # Détailler les cas ciblés, sans dérouler les statuts non renseignés.
        show_details = (
            category
            in {
                "Déclaration Vitiparcel ambiguë — attente du passage non confirmée",
                "Hors contrôles — toutes les acquisitions associées sont exclues",
                "Critère Vitiparcel prêt à livrer satisfait",
            }
            # Ce cas est aussi retenu si le contrôle
            # concerned['passage_review_candidate'].map(flag).any() est positif.
            or concerned["passage_review_candidate"].map(flag).any()
        )
        # Cette branche traite le cas où show_details est évalué comme vrai.
        if show_details:
            # On parcourt concerned.iterrows() ; (_, row) désigne l’élément courant à chaque passage
            # dans la boucle.
            for _, row in concerned.iterrows():
                # On affiche f"    - {text(row.get('Vineyard'))} / {row['passage_name']}" dans la
                # sortie du programme.
                print(f"    - {text(row.get('Vineyard'))} / {row['passage_name']}")
        # On vérifie ce cas avant la suite : category correspond à ce texte explicite.
        if (
            category
            == "Hors contrôles — toutes les acquisitions associées sont exclues"
        ):
            # On affiche ce texte explicite dans la sortie du programme.
            print(
                "    Motifs : tests déclarés ou statuts En attente / Autre dans Excel."
            )
        # Cette branche traite le cas où ambiguity_reasons est évalué comme vrai.
        if ambiguity_reasons:
            # On vérifie ce cas avant la suite : le texte 'Acquisition associée à plusieurs passages'
            # appartient à ambiguity_reasons.
            if "Acquisition associée à plusieurs passages" in ambiguity_reasons:
                # On affiche cette information de suivi dans la sortie du programme.
                print(
                    "    Le suivi Excel ne précise pas à quel passage le « Terminé » s’applique."
                )
            # On parcourt sorted(ambiguity_reasons - {'Acquisition associée à plusieurs passages',… ;
            # reason désigne l’élément courant à chaque passage dans la boucle.
            for reason in sorted(
                ambiguity_reasons - {"Acquisition associée à plusieurs passages", ""}
            ):
                # On affiche f'    Autre motif : {reason}.' dans la sortie du programme.
                print(f"    Autre motif : {reason}.")
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "    Le compteur porte sur les passages concernés, pas sur les acquisitions."
            )
        # Cette branche traite le cas où show_details est évalué comme vrai.
        if show_details:
            # On affiche cette information de suivi dans la sortie du programme.
            print()
    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On sélectionne dans passages.loc les éléments désignés par
    # passages['passage_review_candidate'].map(flag) ; candidates recevra cette sélection.
    candidates = passages.loc[passages["passage_review_candidate"].map(flag)]

    # On appelle counter avec 'Passages candidats à une nouvelle vérification'.
    counter("Passages candidats à une nouvelle vérification", len(candidates))
    # On traite à part le tableau passages lorsqu’il est vide.
    if passages.empty:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "  Compteur à 0 faute de passages identifiés — pas une validation des livrables."
        )

    # On parcourt candidates.iterrows() ; (_, row) désigne l’élément courant à chaque passage dans la
    # boucle.
    for _, row in candidates.iterrows():
        # On affiche f"    - {text(row.get('Vineyard'))} / {row['passage_name']}" dans la sortie du
        # programme.
        print(f"    - {text(row.get('Vineyard'))} / {row['passage_name']}")
        # On affiche f"      Motif : {text(row['passage_business_category'])}" dans la sortie du
        # programme.
        print(f"      Motif : {text(row['passage_business_category'])}")
    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On appelle heading avec 'À RETENIR'.
    heading("À RETENIR", "ℹ️")
    # On affiche ce texte explicite dans la sortie du programme.
    print("  Vitiparcel prêt : stocks présent ET au moins un statut non sain.")
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "  Statut Excel vide ou déclaration ambiguë : aucune alerte automatique sur les stocks,"
    )
    # On affiche cette information de suivi dans la sortie du programme.
    print("  mais pas une validation du livrable. Aucun retraitement automatique.")

    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On appelle heading avec 'FICHIERS LOCAUX'.
    heading("FICHIERS LOCAUX", "📁")
    # On affiche '-' * width dans la sortie du programme.
    print("-" * width)
    # Cette branche traite le cas où paths est évalué comme vrai.
    if paths:
        # On affiche f'  Dossier : {paths[0].parent}' dans la sortie du programme.
        print(f"  Dossier : {paths[0].parent}")
    # On parcourt ces collections en parallèle ; les éléments de même position seront comparés ou
    # associés dans le corps de la boucle.
    for label, path in zip(("Acquisitions", "Associations", "Passages"), paths):
        # On affiche f'  {label} :' dans la sortie du programme.
        print(f"  {label} :")
        # On affiche f'    {path.name}' dans la sortie du programme.
        print(f"    {path.name}")
    # On affiche line dans la sortie du programme.
    print(line)
    # On affiche cette information de suivi dans la sortie du programme.
    print()


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On appelle parser.add_argument avec '--reference'.
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    # On appelle parser.add_argument avec '--evidence'.
    parser.add_argument("--evidence", type=Path)
    # On appelle parser.add_argument avec '--associations'.
    parser.add_argument("--associations", type=Path)
    # On appelle parser.add_argument avec '--passages'.
    parser.add_argument("--passages", type=Path)
    # On appelle parser.add_argument avec '--vineyard'.
    parser.add_argument("--vineyard", required=True)
    # Option --run-id : Horodatage exact des trois CSV (aucun choix automatique du dernier fichier).
    # Sa déclaration ne déclenche pas l’action.
    parser.add_argument(
        "--run-id",
        help="Horodatage exact des trois CSV (aucun choix automatique du dernier fichier).",
    )
    # On appelle parser.add_argument avec '--input-dir'.
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=PROJECT_ROOT / "data/03_normalized/nas_live_evidence",
    )
    # Option --decisions : CSV facultatif de décisions métier explicites. Sa déclaration ne
    # déclenche pas l’action.
    parser.add_argument(
        "--decisions", type=Path, help="CSV facultatif de décisions métier explicites."
    )
    # On appelle parser.add_argument avec '--output-dir'.
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    # On garde dans args les options passées à la commande, après leur analyse par argparse.
    args = parser.parse_args(argv)
    # Cette branche traite le cas où le test args.run_id est satisfait.
    if args.run_id:
        # Cette branche traite le cas où au moins un élément satisfait le test indiqué.
        if any(
            path is not None
            for path in (args.evidence, args.associations, args.passages)
        ):
            # On appelle parser.error avec 'Choisir --run-id OU les trois chemins explicites, pas les
            # deux.'.
            parser.error(
                "Choisir --run-id OU les trois chemins explicites, pas les deux."
            )
        # Cette branche traite le cas où la condition
        # re.fullmatch('\\d{4}-\\d{2}-\\d{2}T\\d{2}-\\d{2}-\\d{2}Z', args.run_id) n’est pas remplie.
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z", args.run_id):
            # On appelle parser.error avec '--run-id doit correspondre à YYYY-MM-DDTHH-MM-SSZ.'.
            parser.error("--run-id doit correspondre à YYYY-MM-DDTHH-MM-SSZ.")
        # On garde dans filename_stem la version en minuscules de re.sub('[^A-Za-z0-9_-]+', '_',
        # args.vineyard).strip('_').
        filename_stem = (
            re.sub(r"[^A-Za-z0-9_-]+", "_", args.vineyard).strip("_").lower()
        )
        # On construit args.evidence en assemblant les morceaux du chemin. L’opérateur / de pathlib
        # ne crée ni dossier ni fichier.
        args.evidence = (
            args.input_dir / f"{filename_stem}_live_nas_evidence_{args.run_id}.csv"
        )
        # On construit args.associations en assemblant les morceaux du chemin. L’opérateur / de
        # pathlib ne crée ni dossier ni fichier.
        args.associations = (
            args.input_dir / f"{filename_stem}_live_nas_associations_{args.run_id}.csv"
        )
        # On construit args.passages en assemblant les morceaux du chemin. L’opérateur / de pathlib
        # ne crée ni dossier ni fichier.
        args.passages = (
            args.input_dir / f"{filename_stem}_live_nas_passages_{args.run_id}.csv"
        )
    # Cette branche traite le cas où au moins un élément satisfait le test indiqué.
    elif any(
        path is None for path in (args.evidence, args.associations, args.passages)
    ):
        # On appelle parser.error avec 'Fournir --run-id OU --evidence, --associations et --passages.'.
        parser.error("Fournir --run-id OU --evidence, --associations et --passages.")
    # On construit (reference, evidence, associations, passages) comme une liste à partir de
    # read_csv(path), pour chaque path de (args.reference, args.evidence, args.associations,
    # args.passages).
    reference, evidence, associations, passages = [
        read_csv(path)
        for path in (args.reference, args.evidence, args.associations, args.passages)
    ]
    # On garde dans vineyard_key la valeur renvoyée par normalize_join_key.
    vineyard_key = normalize_join_key(args.vineyard)
    # On prépare frames comme liste vide ; on la remplira au fil des opérations suivantes.
    frames = []
    # On parcourt (reference, evidence, associations, passages) ; frame désigne l’élément courant à
    # chaque passage dans la boucle.
    for frame in (reference, evidence, associations, passages):
        # On appelle validate_required_columns avec frame.
        validate_required_columns(frame, ["Vineyard"], "entrée CSV")
        # On ajoute frame.loc[frame['Vineyard'].apply(normalize_join_key).eq(vineyard_key)].copy() à la
        # fin de frames ; les éléments précédents restent conservés.
        frames.append(
            frame.loc[
                frame["Vineyard"].apply(normalize_join_key).eq(vineyard_key)
            ].copy()
        )
    # On choisit la valeur de decisions selon ce test : le test args.decisions est satisfait. Les deux
    # résultats possibles restent définis explicitement ici.
    decisions = read_csv(args.decisions) if args.decisions else None
    # On vérifie ce cas avant la suite : decisions est renseigné (différent de None).
    if decisions is not None:
        # On garde dans decisions une copie de
        # decisions.loc[decisions['Vineyard'].apply(normalize_join_key).eq… pour travailler sur cet
        # objet séparément.
        decisions = decisions.loc[
            decisions["Vineyard"].apply(normalize_join_key).eq(vineyard_key)
        ].copy()
    # On garde dans results la valeur renvoyée par reconcile.
    results = reconcile(*frames, decisions=decisions)
    # Sorties exclusivement dans le projet local ; ne pas écrire dans une source réseau.
    output = args.output_dir.resolve()
    # On garde dans project_data le chemin absolu résolu de PROJECT_ROOT / 'data', en tenant compte des
    # liens symboliques.
    project_data = (PROJECT_ROOT / "data").resolve()
    # Les résultats du rapprochement seront écrits dans les données locales du projet, pas sur un
    # chemin arbitraire.
    if not output.is_relative_to(project_data):
        # On interrompt cette branche avec ValueError : '--output-dir doit rester dans le dossier data
        # du projet local.'.
        raise ValueError(
            "--output-dir doit rester dans le dossier data du projet local."
        )
    # On prépare le dossier output avec les règles de création indiquées ; aucun résultat métier n’est
    # encore produit par cette création.
    output.mkdir(parents=True, exist_ok=True)
    # On garde dans timestamp la date datetime.now(timezone.utc) mise en forme selon le modèle indiqué.
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
    # On garde dans stem la version en minuscules de re.sub('[^A-Za-z0-9_-]+', '_', args.vineyard).
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", args.vineyard).lower()
    # On prépare paths comme liste vide ; on la remplira au fil des opérations suivantes.
    paths = []
    # On parcourt zip(('acquisitions', 'associations', 'passages'), results) ; (label, frame) désigne
    # l’élément courant à chaque passage dans la boucle.
    for label, frame in zip(("acquisitions", "associations", "passages"), results):
        # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est
        # créé par cette construction.
        path = output / f"{stem}_excel_nas_live_{label}_{timestamp}.csv"
        # Clés internes inutiles pour les lecteurs ; preuves originales conservées.
        frame.drop(
            # On décrit les colonnes à présenter, distinctes des lignes de données.
            columns=["vineyard_key", "acquisition_join_key", "excel_vineyard_key"],
            # On définit ce que la conversion fera des valeurs invalides, au lieu de laisser ce cas
            # implicite.
            errors="ignore",
        # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
        # décodé selon un réglage implicite du poste.
        ).to_csv(path, index=False, encoding="utf-8-sig")
        # On ajoute path à la fin de paths ; les éléments précédents restent conservés.
        paths.append(path)
    # On retient pour display_run_id la première valeur évaluée comme vraie dans cette chaîne de replis
    # ; une valeur vide fera donc passer à la suivante.
    display_run_id = args.run_id or extraction_id_from_path(args.evidence)
    # On appelle print_summary avec results.
    print_summary(results, paths, args.vineyard, display_run_id)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On appelle main sans argument positionnel.
    main()
