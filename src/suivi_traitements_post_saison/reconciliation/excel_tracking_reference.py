# Lecture du fichier — Préparation du tableau regroupant les suivis Excel pour les jointures métier.
# On rassemble les valeurs et leur provenance sans choisir arbitrairement entre deux valeurs
# contradictoires.
#

"""Préparation Excel commune au rapprochement historique et actuel.

Fonctions extraites sans modification du rapprochement historique existant.
Aucune lecture de configuration ni accès au NAS lors de l'import.
"""

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd

# On fixe MULTI_VALUE_SEPARATOR à cette valeur explicite ; les contrôles qui l’utilisent partent tous
# du même réglage.
MULTI_VALUE_SEPARATOR = " | "


# On rassemble dans EXCEL_REQUIRED_COLUMNS les 17 éléments explicitement indiqués, en conservant leur
# structure.
EXCEL_REQUIRED_COLUMNS = [
    "Vineyard",
    "Acquisition_ID",
    "Acquisition_ID_normalise",
    "Acquisition_side",
    "Acquisition_date",
    "Acquisition_datetime",
    "Acquisition_timestamp_valid",
    "Acquisition_timestamp_issue",
    "Périmètre",
    "Statut_pipeline",
    "is_test_candidate",
    "has_waiting_step",
    "needs_review",
    "is_blocked_candidate",
    "source_file",
    "source_sheet",
    "source_row_number",
]


# On rassemble dans EXCEL_INVARIANT_COLUMNS les 11 éléments explicitement indiqués, en conservant leur
# structure.
EXCEL_INVARIANT_COLUMNS = [
    "Vineyard",
    "Acquisition_date",
    "Acquisition_datetime",
    "Acquisition_timestamp_valid",
    "Acquisition_timestamp_issue",
    "Périmètre",
    "Statut_pipeline",
    "is_test_candidate",
    "has_waiting_step",
    "needs_review",
    "is_blocked_candidate",
]


# On rassemble dans EXCEL_BOOLEAN_COLUMNS les 5 éléments explicitement indiqués, en conservant leur
# structure.
EXCEL_BOOLEAN_COLUMNS = [
    "Acquisition_timestamp_valid",
    "is_test_candidate",
    "has_waiting_step",
    "needs_review",
    "is_blocked_candidate",
]


# On regroupe dans EXCEL_AGGREGATED_TEXT_COLUMNS ces champs nommés ; on pourra les retrouver par leur
# clé plutôt que par leur position.
EXCEL_AGGREGATED_TEXT_COLUMNS = {
    # On associe la clé 'Date' à cette valeur dans cet objet.
    "Date": "excel_dates",
    # On renseigne l’identifiant de parcelle sous la clé 'Parcel_ID'.
    "Parcel_ID": "excel_parcel_ids",
    # On associe la clé 'Commentaires' à cette valeur dans cet objet.
    "Commentaires": "excel_comments",
    "Problématique": "excel_problems",
    # On associe la clé 'Statut_Resolution' à cette valeur dans cet objet.
    "Statut_Resolution": "excel_resolution_statuses",
    # On associe la clé 'Annotation_rangs' à cette valeur dans cet objet.
    "Annotation_rangs": "excel_annotation_rangs",
    # On associe la clé 'Construction_JSON_Correction' à cette valeur dans cet objet.
    "Construction_JSON_Correction": "excel_json_correction",
    # On associe la clé 'Traitement_visuel_images' à cette valeur dans cet objet.
    "Traitement_visuel_images": "excel_visual_processing",
    # On associe la clé 'Segmentation_images' à cette valeur dans cet objet.
    "Segmentation_images": "excel_segmentation",
    # On associe la clé 'VitiMap' à cette valeur dans cet objet.
    "VitiMap": "excel_vitimap",
    # On associe la clé 'VitiParcel' à cette valeur dans cet objet.
    "VitiParcel": "excel_vitiparcel",
}


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    source_name: str,
) -> None:
    """Vérifie que les colonnes indispensables sont présentes."""

    # On construit missing_columns comme une liste à partir de column, pour chaque column de
    # required_columns en ne gardant que les éléments qui passent le filtre.
    missing_columns = [
        column for column in required_columns if column not in df.columns
    ]

    # Cette branche traite le cas où missing_columns est évalué comme vrai.
    if missing_columns:
        # On interrompt cette branche avec ValueError.
        raise ValueError(f"Colonnes absentes de {source_name} : {missing_columns}")


# On prépare une clé comparable pour les jointures, sans modifier les fichiers de source.
def normalize_join_key(value: object) -> str | None:
    """
    Normalise une clé uniquement pour effectuer la jointure.

    La valeur affichée dans le résultat conserve sa casse d'origine.
    La clé interne utilise casefold() afin d'éviter un faux écart dû
    uniquement aux majuscules et minuscules.
    """

    # On reconnaît aussi les valeurs manquantes propres à pandas, comme NaN ; elles ne doivent pas
    # s’afficher comme le texte "nan".
    if pd.isna(value):
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None

    # On garde dans normalized_value le texte str(value) sans les caractères de bord indiqués, ou sans
    # les espaces de bord par défaut.
    normalized_value = str(value).strip()

    # On prévoit le cas où normalized_value est évalué comme faux, par exemple une valeur vide selon
    # son type.
    if not normalized_value:
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None

    # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
    # enregistré dans les données sources.
    return normalized_value.casefold()


def value_to_boolean(value: object) -> bool:
    """Convertit de façon prudente une valeur CSV en booléen."""

    # On reconnaît aussi les valeurs manquantes propres à pandas, comme NaN ; elles ne doivent pas
    # s’afficher comme le texte "nan".
    if pd.isna(value):
        # On renvoie False comme résultat explicite de cette branche.
        return False

    # On réserve cette branche à value lorsqu’il est de type bool.
    if isinstance(value, bool):
        # On remet la valeur reçue à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return value

    # On réserve cette branche à value lorsqu’il est de type (int, float).
    if isinstance(value, (int, float)):
        # On fournit à l’appelant la valeur de vérité Python de la valeur reçue ; ce test ne distingue
        # pas à lui seul tous les états métier.
        return bool(value)

    # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
    # enregistré dans les données sources.
    normalized_value = str(value).strip().casefold()

    # On vérifie ce cas avant la suite : normalized_value appartient à {'true', '1', 'yes', 'oui'}.
    if normalized_value in {"true", "1", "yes", "oui"}:
        # On renvoie True comme résultat explicite de cette branche.
        return True

    # On vérifie ce cas avant la suite : normalized_value appartient à {'false', '0', 'no', 'non', ''}.
    if normalized_value in {"false", "0", "no", "non", ""}:
        # On renvoie False comme résultat explicite de cette branche.
        return False

    # On interrompt cette branche avec ValueError.
    raise ValueError(f"Valeur booléenne non reconnue : {value!r}")


def unique_non_empty_values(series: pd.Series) -> list[str]:
    """Retourne les valeurs textuelles uniques, non vides et triées."""

    # On prépare values comme liste vide ; on la remplira au fil des opérations suivantes.
    values = []
    # On garde dans seen un ensemble vide, qui servira à repérer les valeurs déjà rencontrées.
    seen = set()

    # On parcourt series ; value désigne l’élément courant à chaque passage dans la boucle.
    for value in series:
        # On reconnaît aussi les valeurs manquantes propres à pandas, comme NaN ; elles ne doivent pas
        # s’afficher comme le texte "nan".
        if pd.isna(value):
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue

        # On garde dans text le texte str(value) sans les caractères de bord indiqués, ou sans les
        # espaces de bord par défaut.
        text = str(value).strip()

        # On prévoit le cas où text est évalué comme faux, par exemple une valeur vide selon son type.
        if not text:
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue

        # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
        # enregistré dans les données sources.
        comparison_key = text.casefold()

        # On vérifie ce cas avant la suite : comparison_key appartient à seen.
        if comparison_key in seen:
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue

        # On ajoute comparison_key à seen ; comme il s’agit d’un ensemble, une valeur déjà présente
        # n’est pas comptée deux fois.
        seen.add(comparison_key)
        # On ajoute text à la fin de values ; les éléments précédents restent conservés.
        values.append(text)

    # On fournit à l’appelant les éléments triés des valeurs dans une nouvelle liste.
    return sorted(values, key=str.casefold)


def join_unique_values(series: pd.Series) -> str:
    """Réunit les valeurs uniques d'une série dans une seule cellule."""

    # On fournit à l’appelant le texte formé en réunissant les éléments avec MULTI_VALUE_SEPARATOR
    # comme séparateur.
    return MULTI_VALUE_SEPARATOR.join(unique_non_empty_values(series))


def get_single_text_value(
    group: pd.DataFrame,
    column: str,
    acquisition_key: str,
) -> str | None:
    """
    Retourne la valeur unique d'une colonne supposée invariante.

    Une erreur est levée si LEFT et RIGHT possèdent des valeurs
    différentes pour cette colonne.
    """

    # On garde dans values la valeur renvoyée par unique_non_empty_values.
    values = unique_non_empty_values(group[column])

    # On vérifie ce cas avant la suite : len(values) est supérieur à 1.
    if len(values) > 1:
        # On interrompt cette branche avec ValueError.
        raise ValueError(
            "Valeurs Excel contradictoires pour "
            f"{acquisition_key}, colonne {column} : {values}"
        )

    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return values[0] if values else None


def get_single_boolean_value(
    group: pd.DataFrame,
    column: str,
    acquisition_key: str,
) -> bool:
    """Retourne le booléen unique attendu dans un groupe Excel."""

    # On construit values comme un ensemble sans doublons à partir de value_to_boolean(value), pour
    # chaque value de group[column] en ne gardant que les éléments qui passent le filtre.
    values = {value_to_boolean(value) for value in group[column] if not pd.isna(value)}

    # On vérifie ce cas avant la suite : len(values) est supérieur à 1.
    if len(values) > 1:
        # On interrompt cette branche avec ValueError.
        raise ValueError(
            "Valeurs booléennes Excel contradictoires pour "
            f"{acquisition_key}, colonne {column} : {values}"
        )

    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return next(iter(values)) if values else False


def join_source_row_numbers(series: pd.Series) -> str:
    """Réunit les numéros de lignes Excel dans un ordre lisible."""

    # On prépare values comme liste vide ; on la remplira au fil des opérations suivantes.
    values = []

    # On parcourt series.dropna() ; value désigne l’élément courant à chaque passage dans la boucle.
    for value in series.dropna():
        # On tente ce bloc et on traite séparément les erreurs prévues : (TypeError, ValueError).
        try:
            # On ajoute int(float(value)) à la fin de values ; les éléments précédents restent
            # conservés.
            values.append(int(float(value)))
        except (TypeError, ValueError):
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue

    # On fournit à l’appelant le texte formé en réunissant les éléments avec MULTI_VALUE_SEPARATOR
    # comme séparateur.
    return MULTI_VALUE_SEPARATOR.join(str(value) for value in sorted(set(values)))


# On regroupe les suivis Excel et leur provenance pour les rapprochements suivants.
def prepare_excel_reference(
    excel_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Consolide les lignes Excel en une ligne par acquisition logique.

    Dans le fichier actuel, 44 acquisitions possèdent deux lignes :
    une ligne LEFT et une ligne RIGHT. Le rapprochement ne doit pas
    dupliquer l'observation NAS pour ces acquisitions.
    """

    # On appelle validate_required_columns avec excel_df.
    validate_required_columns(
        excel_df,
        EXCEL_REQUIRED_COLUMNS,
        "référentiel Excel",
    )

    # On garde dans prepared_df une copie de excel_df pour travailler sur cet objet séparément.
    prepared_df = excel_df.copy()

    # On garde dans prepared_df['acquisition_join_key'] le résultat de la fonction appliquée aux
    # éléments ou à l’axe indiqué de prepared_df['Acquisition_ID_normalise'].
    prepared_df["acquisition_join_key"] = prepared_df["Acquisition_ID_normalise"].apply(
        normalize_join_key
    )

    # Cette branche traite le cas où le contrôle prepared_df['acquisition_join_key'].isna().any() est
    # positif.
    if prepared_df["acquisition_join_key"].isna().any():
        # On interrompt cette branche avec ValueError : 'Le référentiel Excel contient une clé
        # normalisée vide.'.
        raise ValueError("Le référentiel Excel contient une clé normalisée vide.")

    # On prépare output_rows comme liste vide ; on la remplira au fil des opérations suivantes.
    output_rows = []

    # On parcourt prepared_df.groupby('acquisition_join_key', sort=False) ; (acquisition_key, group)
    # désigne l’élément courant à chaque passage dans la boucle.
    for acquisition_key, group in prepared_df.groupby(
        "acquisition_join_key",
        sort=False,
    ):
        # Vérification explicite des informations qui doivent être
        # identiques entre les lignes LEFT et RIGHT.
        invariant_values = {}

        # On parcourt EXCEL_INVARIANT_COLUMNS ; column désigne l’élément courant à chaque passage dans
        # la boucle.
        for column in EXCEL_INVARIANT_COLUMNS:
            # On vérifie ce cas avant la suite : column appartient à EXCEL_BOOLEAN_COLUMNS.
            if column in EXCEL_BOOLEAN_COLUMNS:
                # On garde dans invariant_values[column] la valeur renvoyée par
                # get_single_boolean_value.
                invariant_values[column] = get_single_boolean_value(
                    group,
                    column,
                    acquisition_key,
                )
            else:
                # On garde dans invariant_values[column] la valeur renvoyée par get_single_text_value.
                invariant_values[column] = get_single_text_value(
                    group,
                    column,
                    acquisition_key,
                )

        # On garde dans normalized_ids la valeur renvoyée par unique_non_empty_values.
        normalized_ids = unique_non_empty_values(group["Acquisition_ID_normalise"])

        # On vérifie ce cas avant la suite : len(normalized_ids) diffère de 1.
        if len(normalized_ids) != 1:
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                "Plusieurs écritures normalisées incompatibles pour "
                f"{acquisition_key} : {normalized_ids}"
            )

        # On garde dans sides la valeur renvoyée par unique_non_empty_values.
        sides = unique_non_empty_values(group["Acquisition_side"])

        # On regroupe dans row ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
        # leur position.
        row = {
            # On associe la clé 'acquisition_join_key' à cette valeur dans cet objet.
            "acquisition_join_key": acquisition_key,
            # On associe la clé 'excel_acquisition_id_normalise' à cette valeur dans cet objet.
            "excel_acquisition_id_normalise": normalized_ids[0],
            # On associe la clé 'excel_vineyard' à cette valeur dans cet objet.
            "excel_vineyard": invariant_values["Vineyard"],
            # On associe la clé 'excel_acquisition_date' à cette valeur dans cet objet.
            "excel_acquisition_date": invariant_values["Acquisition_date"],
            # On associe la clé 'excel_acquisition_datetime' à cette valeur dans cet objet.
            "excel_acquisition_datetime": invariant_values["Acquisition_datetime"],
            # On associe la clé 'excel_acquisition_timestamp_valid' à cette valeur dans cet objet.
            "excel_acquisition_timestamp_valid": invariant_values[
                "Acquisition_timestamp_valid"
            ],
            # On associe la clé 'excel_acquisition_timestamp_issue' à cette valeur dans cet objet.
            "excel_acquisition_timestamp_issue": invariant_values[
                "Acquisition_timestamp_issue"
            ],
            # On renseigne le périmètre du suivi Excel sous la clé 'excel_perimeter'.
            "excel_perimeter": invariant_values["Périmètre"],
            # On renseigne le statut du suivi Excel sous la clé 'excel_pipeline_status'.
            "excel_pipeline_status": invariant_values["Statut_pipeline"],
            # On associe la clé 'excel_is_test_candidate' à cette valeur dans cet objet.
            "excel_is_test_candidate": invariant_values["is_test_candidate"],
            # On associe la clé 'excel_has_waiting_step' à cette valeur dans cet objet.
            "excel_has_waiting_step": invariant_values["has_waiting_step"],
            # On associe la clé 'excel_needs_review' à cette valeur dans cet objet.
            "excel_needs_review": invariant_values["needs_review"],
            # On associe la clé 'excel_is_blocked_candidate' à cette valeur dans cet objet.
            "excel_is_blocked_candidate": invariant_values["is_blocked_candidate"],
            # On associe la clé 'excel_row_count' à cette valeur dans cet objet.
            "excel_row_count": len(group),
            # On associe la clé 'excel_has_multiple_rows' à cette valeur dans cet objet.
            "excel_has_multiple_rows": len(group) > 1,
            # On associe la clé 'excel_sides' à cette valeur dans cet objet.
            "excel_sides": MULTI_VALUE_SEPARATOR.join(sides),
            # On associe la clé 'excel_has_left' à cette valeur dans cet objet.
            "excel_has_left": "LEFT" in {side.upper() for side in sides},
            # On associe la clé 'excel_has_right' à cette valeur dans cet objet.
            "excel_has_right": "RIGHT" in {side.upper() for side in sides},
            # On associe la clé 'excel_has_unspecified_side' à cette valeur dans cet objet.
            "excel_has_unspecified_side": "NON_PRÉCISÉ"
            in {side.upper() for side in sides},
            # On associe la clé 'excel_source_acquisition_ids' à cette valeur dans cet objet.
            "excel_source_acquisition_ids": join_unique_values(group["Acquisition_ID"]),
            # On associe la clé 'excel_source_files' à cette valeur dans cet objet.
            "excel_source_files": join_unique_values(group["source_file"]),
            # On associe la clé 'excel_source_sheets' à cette valeur dans cet objet.
            "excel_source_sheets": join_unique_values(group["source_sheet"]),
            # On associe la clé 'excel_source_row_numbers' à cette valeur dans cet objet.
            "excel_source_row_numbers": join_source_row_numbers(
                group["source_row_number"]
            ),
        }

        # On parcourt les couples (source_column, output_column) de EXCEL_AGGREGATED_TEXT_COLUMNS :
        # on garde ensemble la clé et sa valeur au lieu des traiter dans deux listes séparées.
        for source_column, output_column in EXCEL_AGGREGATED_TEXT_COLUMNS.items():
            # On vérifie ce cas avant la suite : source_column appartient à group.columns.
            if source_column in group.columns:
                # On garde dans row[output_column] la valeur renvoyée par join_unique_values.
                row[output_column] = join_unique_values(group[source_column])
            else:
                # On commence row[output_column] avec un texte vide, à compléter uniquement si la suite
                # apporte une information.
                row[output_column] = ""

        # On ajoute row à la fin de output_rows ; les éléments précédents restent conservés.
        output_rows.append(row)

    # On garde dans consolidated_df un tableau pandas construit avec les données indiquées.
    consolidated_df = pd.DataFrame(output_rows)

    # On doit résoudre ces doublons avant de compter ou de rapprocher les lignes.
    if consolidated_df["acquisition_join_key"].duplicated().any():
        # On interrompt cette branche avec ValueError : 'La consolidation Excel contient encore des
        # doublons.'.
        raise ValueError("La consolidation Excel contient encore des doublons.")

    # On remet consolidated_df à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return consolidated_df
