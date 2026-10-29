# Lecture du fichier — Lecture des suivis Excel et préparation des identifiants et indicateurs de qualité.
# On harmonise les données avant le rapprochement. Nettoyer un identifiant ne doit pas masquer une
# ambiguïté de source : les anomalies disposent de leurs propres indicateurs.
#

"""
Lecture et normalisation des fichiers Excel de suivi des acquisitions.

Ce script réalise uniquement l'ingestion des fichiers Excel :

1. il charge la configuration YAML ;
2. il cherche les fichiers Excel dans le dossier incoming ;
3. il vérifie leurs colonnes ;
4. il nettoie les valeurs textuelles ;
5. il ignore les lignes qui ne contiennent aucune donnée métier ;
6. il sépare les lignes valides des lignes réellement rejetées ;
7. il normalise les différentes formes d'Acquisition_ID ;
8. il distingue les côtés LEFT, RIGHT et NON_PRÉCISÉ ;
9. il contrôle strictement l'horodatage présent dans l'identifiant ;
10. il attribue un périmètre et un statut provisoires ;
11. il conserve les acquisitions de production, de test et bloquées ;
12. il conserve des versions distinctes avec leur provenance ;
13. il publie des copies courantes compatibles avec les scripts suivants.

Le lancement exige --all-vineyards ou --vineyard NomDuVignoble.
La premiere initialisation exige --all-vineyards. Le pilotage des fichiers
est confie au module tracking_versioning.py, sans consultation du NAS.

À ce stade du projet, ce script ne consulte pas le NAS.
Les statuts calculés ici reposent uniquement sur les informations
présentes dans les fichiers Excel.

Important concernant les horodatages :
    - une valeur invalide n'est jamais corrigée automatiquement ;
    - l'identifiant original est toujours conservé ;
    - la ligne reste dans les données normalisées ;
    - l'anomalie est exposée dans des colonnes de qualité dédiées.
"""

# datetime permet de valider strictement les dates et d'enregistrer
# la date de l'ingestion.
from datetime import datetime, timezone

# Path facilite la manipulation des chemins.
from pathlib import Path

# re permet d'utiliser des expressions régulières.
import re

# pandas est utilisé pour lire et transformer les tableaux.
import pandas as pd

# PyYAML permet de charger le fichier tracking_files.yml.
import yaml


# ============================================================
# 1. CHEMINS PRINCIPAUX DU PROJET
# ============================================================

# Le script se trouve dans :
#
# src/
# └── suivi_traitements_post_saison/
#     └── ingestion/
#         └── excel_reader.py
#
# parents[3] permet de remonter à la racine du projet.
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Fichier YAML contenant la configuration de l'ingestion.
CONFIG_PATH = PROJECT_ROOT / "config" / "tracking_files.yml"

# Dossier contenant les copies locales des Excel.
INPUT_DIR = PROJECT_ROOT / "data" / "01_incoming" / "suivi_acquisitions"

# Dossier contenant les CSV normalisés.
OUTPUT_DIR = PROJECT_ROOT / "data" / "03_normalized" / "suivi_acquisitions_normalises"

# Dossier contenant les éventuelles lignes rejetées.
REJECTED_DIR = PROJECT_ROOT / "data" / "04_rejected"

# Fichier regroupant les données normalisées de tous les vignobles.
CONSOLIDATED_OUTPUT_PATH = OUTPUT_DIR / "toutes_acquisitions_normalisees.csv"


# ============================================================
# 2. CHARGEMENT DE LA CONFIGURATION YAML
# ============================================================


def load_settings(config_path: Path) -> dict:
    """
    Charge les paramètres présents dans tracking_files.yml.

    La fonction vérifie également que les sections nécessaires
    au script sont bien présentes.
    """

    # Cette branche traite le cas où la condition config_path.exists() n’est pas remplie.
    if not config_path.exists():
        # On interrompt cette branche avec FileNotFoundError.
        raise FileNotFoundError(f"Fichier de configuration introuvable : {config_path}")

    # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la sortie, y
    # compris après une erreur.
    with config_path.open(
        mode="r",
        # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
        # décodé selon un réglage implicite du poste.
        encoding="utf-8",
    ) as config_file:
        # On garde dans config la valeur renvoyée par yaml.safe_load.
        config = yaml.safe_load(config_file)

    # On prévoit le cas où config est évalué comme faux, par exemple une valeur vide selon son type.
    if not config:
        # On interrompt cette branche avec ValueError : 'Le fichier de configuration YAML est vide.'.
        raise ValueError("Le fichier de configuration YAML est vide.")

    # On vérifie ce cas avant la suite : le texte 'tracking_settings' ne figure pas dans les réglages.
    if "tracking_settings" not in config:
        # On interrompt cette branche avec ValueError : "La section 'tracking_settings' est absente du
        # YAML.".
        raise ValueError("La section 'tracking_settings' est absente du YAML.")

    # On récupère config['tracking_settings'] et on le garde dans settings pour la suite.
    settings = config["tracking_settings"]

    # On rassemble dans required_settings les 7 éléments explicitement indiqués, en conservant leur
    # structure.
    required_settings = [
        "target_sheet",
        "required_columns",
        "optional_columns",
        "test_search_columns",
        "technical_step_columns",
        "waiting_values",
        "review_values",
    ]

    # On construit missing_settings comme une liste à partir de setting, pour chaque setting de
    # required_settings en ne gardant que les éléments qui passent le filtre.
    missing_settings = [
        setting for setting in required_settings if setting not in settings
    ]

    # Cette branche traite le cas où missing_settings est évalué comme vrai.
    if missing_settings:
        # On interrompt cette branche avec ValueError.
        raise ValueError(f"Paramètres absents du fichier YAML : {missing_settings}")

    # On remet settings à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return settings


# ============================================================
# 3. OUTILS DE NETTOYAGE
# ============================================================


def clean_column_headers(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Nettoie les noms de colonnes.

    Exemple :
        " Acquisition_ID " devient "Acquisition_ID"
    """

    # On construit df.columns comme une liste à partir de str(column).strip(), pour chaque column de
    # df.columns.
    df.columns = [str(column).strip() for column in df.columns]

    # Deux en-têtes différents pourraient devenir identiques
    # après la suppression des espaces.
    duplicated_headers = df.columns[df.columns.duplicated()].tolist()

    # On doit résoudre ces doublons avant de compter ou de rapprocher les lignes.
    if duplicated_headers:
        # On interrompt cette branche avec ValueError.
        raise ValueError(f"En-têtes dupliqués après nettoyage : {duplicated_headers}")

    # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return df


def clean_text_columns(
    df: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """
    Nettoie les valeurs textuelles.

    Le nettoyage :
    1. convertit les valeurs en texte pandas ;
    2. retire les espaces au début et à la fin ;
    3. transforme les chaînes vides en pd.NA.
    """

    # On parcourt les colonnes ; column désigne l’élément courant à chaque passage dans la boucle.
    for column in columns:
        # On garde dans df[column] le résultat du remplacement demandé sur
        # df[column].astype('string').str.strip().
        df[column] = df[column].astype("string").str.strip().replace("", pd.NA)

    # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return df


def build_search_expression(
    values: list[str],
) -> str:
    """
    Construit une expression régulière à partir d'une liste.

    Exemple :
        ["en attente", "à revoir"]
    """

    # On construit escaped_values comme une liste à partir de re.escape(str(value).strip()), pour
    # chaque value de values en ne gardant que les éléments qui passent le filtre.
    escaped_values = [
        re.escape(str(value).strip()) for value in values if str(value).strip()
    ]

    # Expression qui ne correspondra à rien
    # si aucune valeur n'est configurée.
    if not escaped_values:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return r"(?!x)x"

    # On garde dans joined_values le texte formé en réunissant les éléments avec '|' comme séparateur.
    joined_values = "|".join(escaped_values)

    # Les limites de mots évitent que "autre"
    # corresponde accidentellement à "autrement".
    return rf"\b(?:{joined_values})\b"


def contains_expression_in_columns(
    df: pd.DataFrame,
    columns: list[str],
    expression: str,
) -> pd.Series:
    """
    Recherche une expression dans plusieurs colonnes.

    La fonction retourne une série de True et False.
    """

    # On garde dans result une série pandas avec les valeurs et l’index fournis.
    result = pd.Series(
        False,
        index=df.index,
    )

    # On parcourt les colonnes ; column désigne l’élément courant à chaque passage dans la boucle.
    for column in columns:
        # On garde dans column_matches la valeur renvoyée par df[column].fillna('').str.contains.
        column_matches = (
            df[column]
            .fillna("")
            .str.contains(
                expression,
                case=False,
                regex=True,
                na=False,
            )
        )

        # On réunit ces masques avec | pour construire result ; les parenthèses gardent les
        # comparaisons regroupées.
        result = result | column_matches

    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# ============================================================
# 4. CONTRÔLE DU VIGNOBLE
# ============================================================


def extract_vineyard_from_filename(
    file_path: Path,
) -> str | None:
    """
    Tente d'extraire le vignoble depuis le nom du fichier.

    Exemples reconnus :
        Suivi_acquisition_DomaineDemoA_2026.xlsx
        Suivi_acquisitions_DomaineDemoB_2026.xlsx

    La colonne Vineyard de l'Excel reste prioritaire.
    """

    # On utilise ce texte pour pattern ; il ne dépend pas d’une valeur récupérée ailleurs à cet
    # endroit.
    pattern = r"^Suivi_acquisitions?_(.+)_2026$"

    # On garde dans match la valeur renvoyée par re.match.
    match = re.match(
        pattern,
        file_path.stem,
        flags=re.IGNORECASE,
    )

    # On prévoit le cas où match est évalué comme faux, par exemple une valeur vide selon son type.
    if not match:
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None

    # On fournit à l’appelant la valeur renvoyée par match.group pour 1.
    return match.group(1)


def validate_vineyard(
    df: pd.DataFrame,
    file_path: Path,
) -> tuple[pd.DataFrame, str]:
    """
    Vérifie les valeurs de la colonne Vineyard.

    La colonne Excel reste la source principale.
    Le nom du fichier sert seulement de contrôle ou de secours.
    """

    # On garde dans filename_vineyard la valeur renvoyée par extract_vineyard_from_filename.
    filename_vineyard = extract_vineyard_from_filename(file_path)

    # On garde dans vineyard_values les valeurs de
    # df['Vineyard'].dropna().astype('string').str.strip().unique() dans une liste Python.
    vineyard_values = (
        df["Vineyard"].dropna().astype("string").str.strip().unique().tolist()
    )

    # On construit vineyard_values comme une liste à partir de value, pour chaque value de
    # vineyard_values en ne gardant que les éléments qui passent le filtre.
    vineyard_values = [value for value in vineyard_values if value]

    # Plusieurs vignobles dans le même fichier
    # constituent une anomalie structurelle.
    if len(vineyard_values) > 1:
        # On interrompt cette branche avec ValueError.
        raise ValueError(
            "Plusieurs vignobles différents sont présents "
            "dans la colonne Vineyard : "
            f"{vineyard_values}"
        )

    # Si toute la colonne est vide, le nom du fichier
    # peut servir de valeur de secours.
    if not vineyard_values:
        # On prévoit le cas où filename_vineyard est évalué comme faux, par exemple une valeur vide
        # selon son type.
        if not filename_vineyard:
            # On interrompt cette branche avec ValueError.
            raise ValueError(
                "La colonne Vineyard est vide et le vignoble "
                "ne peut pas être extrait du nom du fichier."
            )

        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "⚠️ La colonne Vineyard est entièrement vide. "
            "Le vignoble sera récupéré depuis le nom du fichier : "
            f"{filename_vineyard}"
        )

        # On garde filename_vineyard sous le nom df['Vineyard'] ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        df["Vineyard"] = filename_vineyard

        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return df, filename_vineyard

    # On récupère vineyard_values[0] et on le garde dans excel_vineyard pour la suite.
    excel_vineyard = vineyard_values[0]

    # Les cellules Vineyard ponctuellement vides sont complétées
    # avec la valeur trouvée dans les autres lignes du fichier.
    df["Vineyard"] = df["Vineyard"].fillna(excel_vineyard)

    # Comparaison entre l'Excel et le nom du fichier.
    if filename_vineyard and excel_vineyard.casefold() != filename_vineyard.casefold():
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "⚠️ Le vignoble de l'Excel ne correspond pas "
            "exactement au vignoble du nom du fichier."
        )
        # On affiche f'   Excel : {excel_vineyard}' dans la sortie du programme.
        print(f"   Excel : {excel_vineyard}")
        # On affiche f'   Fichier : {filename_vineyard}' dans la sortie du programme.
        print(f"   Fichier : {filename_vineyard}")

    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return df, excel_vineyard


# ============================================================
# 5. NORMALISATION DES IDENTIFIANTS D'ACQUISITION
# ============================================================


# On harmonise l’identifiant pour rapprocher les lignes qui désignent la même acquisition.
def normalize_acquisition_id(
    acquisition_id: str,
    vineyard: str,
) -> dict:
    """
    Normalise un identifiant d'acquisition.

    Une même acquisition peut être écrite de plusieurs façons :
        C04_V1_2026-06-05T13-30-04
        DomaineDemoH_C04_V1_2026-06-05T13-30-04
        DomaineDemoH_C04_V1_2026-06-05T13-30-04_LEFT
        DomaineDemoH_C04_V1_2026-06-05T13-30-04_RIGHT

    La fonction produit quatre informations :

    - Acquisition_ID_base :
      identifiant court utilisé pour rechercher le dossier Brut ;

    - Acquisition_ID_normalise :
      identifiant contenant le vignoble, sans LEFT ou RIGHT ;

    - Acquisition_side :
      LEFT, RIGHT ou NON_PRÉCISÉ ;

    - Acquisition_row_key :
      clé correspondant à la granularité de la ligne Excel.

    La valeur originale présente dans Acquisition_ID
    n'est jamais écrasée.
    """

    # Nettoyage simple des deux valeurs.
    source_id = str(acquisition_id).strip()
    # On garde dans vineyard_name le texte str(vineyard) sans les caractères de bord indiqués, ou sans
    # les espaces de bord par défaut.
    vineyard_name = str(vineyard).strip()

    # Par défaut, l'Excel ne précise pas le côté.
    acquisition_side = "NON_PRÉCISÉ"

    # Recherche d'un suffixe terminal _LEFT ou _RIGHT.
    side_match = re.search(
        r"_(LEFT|RIGHT)$",
        source_id,
        flags=re.IGNORECASE,
    )

    # Cette branche traite le cas où side_match est évalué comme vrai.
    if side_match:
        # Le côté est enregistré en majuscules.
        acquisition_side = side_match.group(1).upper()

        # Le suffixe LEFT ou RIGHT est retiré
        # de l'identifiant logique.
        id_without_side = source_id[: side_match.start()]
    else:
        # On garde source_id sous le nom id_without_side ; cette affectation ne copie pas à elle seule
        # un objet mutable.
        id_without_side = source_id

    # Préfixe attendu dans Processing.
    vineyard_prefix = f"{vineyard_name}_"

    # Si l'identifiant commence déjà par le vignoble,
    # nous retirons ce préfixe pour obtenir la forme courte.
    if id_without_side.casefold().startswith(vineyard_prefix.casefold()):
        # On garde dans acquisition_id_base la portion de id_without_side sélectionnée par
        # len(vineyard_prefix): ; les bornes de fin sont exclues.
        acquisition_id_base = id_without_side[len(vineyard_prefix) :]
    else:
        # Si le vignoble n'est pas présent,
        # l'identifiant est déjà considéré comme court.
        acquisition_id_base = id_without_side

    # L'identifiant normalisé contient toujours le vignoble,
    # mais jamais le suffixe LEFT ou RIGHT.
    acquisition_id_normalise = f"{vineyard_name}_{acquisition_id_base}"

    # La clé de ligne distingue les deux côtés.
    #
    # LEFT et RIGHT possèdent le même identifiant normalisé,
    # mais deux clés de ligne différentes.
    acquisition_row_key = f"{acquisition_id_normalise}|{acquisition_side}"

    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'Acquisition_ID_base' à cette valeur dans cet objet.
        "Acquisition_ID_base": acquisition_id_base,
        # On renseigne l’identifiant normalisé de l’acquisition sous la clé 'Acquisition_ID_normalise'.
        "Acquisition_ID_normalise": acquisition_id_normalise,
        # On associe la clé 'Acquisition_side' à cette valeur dans cet objet.
        "Acquisition_side": acquisition_side,
        # On associe la clé 'Acquisition_row_key' à cette valeur dans cet objet.
        "Acquisition_row_key": acquisition_row_key,
    }


def add_normalized_acquisition_ids(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ajoute les colonnes normalisées liées à Acquisition_ID.

    La fonction travaille ligne par ligne, car le vignoble
    peut être nécessaire pour compléter l'identifiant.
    """

    # On construit normalized_records comme une liste à partir de
    # normalize_acquisition_id(acquisition_id=acquisition_id, vineyard…, pour chaque (acquisition_id,
    # vineyard) de zip(df['Acquisition_ID'], df['Vineyard']).
    normalized_records = [
        normalize_acquisition_id(
            # On fournit l’identifiant de l’acquisition via le paramètre acquisition_id de cet appel.
            acquisition_id=acquisition_id,
            # On fournit le domaine concerné via le paramètre vineyard de cet appel.
            vineyard=vineyard,
        )
        for acquisition_id, vineyard in zip(
            df["Acquisition_ID"],
            df["Vineyard"],
        )
    ]

    # On garde dans normalized_ids_df un tableau pandas construit avec les données indiquées.
    normalized_ids_df = pd.DataFrame(
        normalized_records,
        index=df.index,
    )

    # Les nouvelles colonnes sont ajoutées sans modifier
    # la colonne Acquisition_ID originale.
    return pd.concat(
        [
            df,
            normalized_ids_df,
        ],
        # On indique l’axe de l’opération : sa valeur distingue le travail sur les lignes ou sur les
        # colonnes.
        axis=1,
    )


# ============================================================
# 6. CONTRÔLE STRICT DE L'HORODATAGE DE L'IDENTIFIANT
# ============================================================

# L'expression recherche l'horodatage terminal de l'identifiant
# normalisé. Le contrôle des plages numériques est volontairement
# effectué ensuite par Python afin d'éviter toute normalisation
# silencieuse de valeurs comme 08-01-60.
ACQUISITION_TIMESTAMP_PATTERN = re.compile(
    r"(?P<year>\d{4})-"
    r"(?P<month>\d{2})-"
    r"(?P<day>\d{2})T"
    r"(?P<hour>\d{2})-"
    r"(?P<minute>\d{2})-"
    r"(?P<second>\d{2})$"
)


# On tente de retrouver la date portée par l’identifiant selon le format attendu.
def parse_acquisition_timestamp(
    acquisition_id: object,
) -> dict:
    """
    Extrait et valide strictement l'horodatage d'un identifiant.

    La fonction ne demande jamais à pandas de corriger ou de
    normaliser une heure invalide. Les différentes composantes sont
    converties en entiers puis contrôlées explicitement.

    Exemples :

        ...T08-01-52
        → horodatage valide

        ...T08-01-60
        → horodatage invalide, secondes hors plage

    Même lorsqu'une heure est invalide, Acquisition_date est
    conservée si la partie calendaire YYYY-MM-DD est valide.
    """

    # On regroupe dans empty_result ces champs nommés ; on pourra les retrouver par leur clé plutôt que
    # par leur position.
    empty_result = {
        # On associe la clé 'Acquisition_date' à cette valeur dans cet objet.
        "Acquisition_date": pd.NA,
        # On associe la clé 'Acquisition_datetime' à cette valeur dans cet objet.
        "Acquisition_datetime": pd.NA,
        # On associe la clé 'Acquisition_timestamp_valid' à cette valeur dans cet objet.
        "Acquisition_timestamp_valid": False,
        # On associe la clé 'Acquisition_timestamp_issue' à cette valeur dans cet objet.
        "Acquisition_timestamp_issue": ("Horodatage absent ou format non reconnu"),
    }

    # On reconnaît aussi les valeurs manquantes propres à pandas, comme NaN ; elles ne doivent pas
    # s’afficher comme le texte "nan".
    if pd.isna(acquisition_id):
        # On remet empty_result à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return empty_result

    # On garde dans acquisition_text le texte str(acquisition_id) sans les caractères de bord indiqués,
    # ou sans les espaces de bord par défaut.
    acquisition_text = str(acquisition_id).strip()
    # On garde dans match la valeur renvoyée par ACQUISITION_TIMESTAMP_PATTERN.search.
    match = ACQUISITION_TIMESTAMP_PATTERN.search(acquisition_text)

    # On prévoit le cas où match est évalué comme faux, par exemple une valeur vide selon son type.
    if not match:
        # On remet empty_result à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return empty_result

    # On garde dans year la conversion numérique de match.group('year') en entier.
    year = int(match.group("year"))
    # On garde dans month la conversion numérique de match.group('month') en entier.
    month = int(match.group("month"))
    # On garde dans day la conversion numérique de match.group('day') en entier.
    day = int(match.group("day"))
    # On garde dans hour la conversion numérique de match.group('hour') en entier.
    hour = int(match.group("hour"))
    # On garde dans minute la conversion numérique de match.group('minute') en entier.
    minute = int(match.group("minute"))
    # On garde dans second la conversion numérique de match.group('second') en entier.
    second = int(match.group("second"))

    # La date calendaire est contrôlée séparément afin de pouvoir
    # la conserver quand seule l'heure est invalide.
    try:
        # On garde dans calendar_date la valeur renvoyée par datetime(year, month, day).date.
        calendar_date = datetime(
            year,
            month,
            day,
        ).date()
    except ValueError:
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On associe la clé 'Acquisition_date' à cette valeur dans cet objet.
            "Acquisition_date": pd.NA,
            # On associe la clé 'Acquisition_datetime' à cette valeur dans cet objet.
            "Acquisition_datetime": pd.NA,
            # On associe la clé 'Acquisition_timestamp_valid' à cette valeur dans cet objet.
            "Acquisition_timestamp_valid": False,
            # On associe la clé 'Acquisition_timestamp_issue' à cette valeur dans cet objet.
            "Acquisition_timestamp_issue": "Date invalide",
        }

    # On garde dans acquisition_date la représentation ISO de calendar_date.
    acquisition_date = calendar_date.isoformat()

    # Contrôles explicites des plages temporelles.
    # Cette approche empêche par exemple 60 secondes d'être
    # transformées silencieusement en une minute supplémentaire.
    if not 0 <= hour <= 23:
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On associe la clé 'Acquisition_date' à cette valeur dans cet objet.
            "Acquisition_date": acquisition_date,
            # On associe la clé 'Acquisition_datetime' à cette valeur dans cet objet.
            "Acquisition_datetime": pd.NA,
            # On associe la clé 'Acquisition_timestamp_valid' à cette valeur dans cet objet.
            "Acquisition_timestamp_valid": False,
            # On associe la clé 'Acquisition_timestamp_issue' à cette valeur dans cet objet.
            "Acquisition_timestamp_issue": "Heures hors plage",
        }

    # Cette branche traite le cas où la condition 0 <= minute <= 59 n’est pas remplie.
    if not 0 <= minute <= 59:
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On associe la clé 'Acquisition_date' à cette valeur dans cet objet.
            "Acquisition_date": acquisition_date,
            # On associe la clé 'Acquisition_datetime' à cette valeur dans cet objet.
            "Acquisition_datetime": pd.NA,
            # On associe la clé 'Acquisition_timestamp_valid' à cette valeur dans cet objet.
            "Acquisition_timestamp_valid": False,
            # On associe la clé 'Acquisition_timestamp_issue' à cette valeur dans cet objet.
            "Acquisition_timestamp_issue": "Minutes hors plage",
        }

    # Cette branche traite le cas où la condition 0 <= second <= 59 n’est pas remplie.
    if not 0 <= second <= 59:
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On associe la clé 'Acquisition_date' à cette valeur dans cet objet.
            "Acquisition_date": acquisition_date,
            # On associe la clé 'Acquisition_datetime' à cette valeur dans cet objet.
            "Acquisition_datetime": pd.NA,
            # On associe la clé 'Acquisition_timestamp_valid' à cette valeur dans cet objet.
            "Acquisition_timestamp_valid": False,
            # On associe la clé 'Acquisition_timestamp_issue' à cette valeur dans cet objet.
            "Acquisition_timestamp_issue": "Secondes hors plage",
        }

    # On garde dans strict_datetime la valeur renvoyée par datetime.
    strict_datetime = datetime(
        year,
        month,
        day,
        hour,
        minute,
        second,
    )

    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'Acquisition_date' à cette valeur dans cet objet.
        "Acquisition_date": acquisition_date,
        # On associe la clé 'Acquisition_datetime' à cette valeur dans cet objet.
        "Acquisition_datetime": strict_datetime.isoformat(sep=" "),
        # On associe la clé 'Acquisition_timestamp_valid' à cette valeur dans cet objet.
        "Acquisition_timestamp_valid": True,
        # On associe la clé 'Acquisition_timestamp_issue' à cette valeur dans cet objet.
        "Acquisition_timestamp_issue": pd.NA,
    }


def add_acquisition_timestamp_quality(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ajoute les colonnes de qualité temporelle des identifiants.

    Les contrôles sont réalisés sur Acquisition_ID_normalise,
    c'est-à-dire après retrait de LEFT/RIGHT et ajout éventuel du
    préfixe Vineyard.
    """

    # On construit timestamp_records comme une liste à partir de
    # parse_acquisition_timestamp(acquisition_id), pour chaque acquisition_id de
    # df['Acquisition_ID_normalise'].
    timestamp_records = [
        parse_acquisition_timestamp(acquisition_id)
        for acquisition_id in df["Acquisition_ID_normalise"]
    ]

    # On garde dans timestamp_df un tableau pandas construit avec les données indiquées.
    timestamp_df = pd.DataFrame(
        timestamp_records,
        index=df.index,
    )

    # On fournit à l’appelant l’assemblage des tableaux suivant l’axe et les options indiqués.
    return pd.concat(
        [
            df,
            timestamp_df,
        ],
        # On indique l’axe de l’opération : sa valeur distingue le travail sur les lignes ou sur les
        # colonnes.
        axis=1,
    )


# On repère le mélange d’identifiants globaux et d’identifiants par côté.
def detect_mixed_side_granularity(
    side_values: pd.Series,
) -> bool:
    """
    Détecte une acquisition présente à deux granularités :
    - une ligne sans côté explicite ;
    - et une ou plusieurs lignes LEFT/RIGHT.

    Exemple :
        acquisition sans suffixe
        acquisition_LEFT
        acquisition_RIGHT

    Ce cas n'est pas supprimé automatiquement.
    Il doit seulement être signalé.
    """

    # On garde dans sides les valeurs distinctes de side_values.dropna().astype(str).tolist().
    sides = set(side_values.dropna().astype(str).tolist())

    # On garde dans has_unspecified le résultat de cette comparaison : le texte 'NON_PRÉCISÉ'
    # appartient à sides.
    has_unspecified = "NON_PRÉCISÉ" in sides

    # On garde dans has_explicit_side la valeur de vérité Python de sides.intersection({'LEFT',
    # 'RIGHT'}) ; ce test ne distingue pas à lui seul tous les états métier.
    has_explicit_side = bool(
        sides.intersection(
            {
                "LEFT",
                "RIGHT",
            }
        )
    )

    # On remet has_unspecified and has_explicit_side à l’appelant ; les étapes suivantes de cette
    # fonction ne sont plus parcourues.
    return has_unspecified and has_explicit_side


def add_identifier_quality_flags(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ajoute les indicateurs de qualité liés aux identifiants.

    Une paire LEFT/RIGHT n'est pas un doublon anormal.

    Un doublon probable existe lorsque la même clé de ligne
    apparaît plusieurs fois, par exemple :
        même acquisition + LEFT
        même acquisition + LEFT
    """

    # Doublon réel probable à la granularité de la ligne.
    df["duplicate_row_key_in_file"] = df["Acquisition_row_key"].duplicated(keep=False)

    # Indique que plusieurs lignes appartiennent à la même
    # acquisition logique.
    #
    # Cela peut être parfaitement normal pour une paire
    # LEFT/RIGHT.
    df["has_multiple_rows_same_acquisition"] = df[
        "Acquisition_ID_normalise"
    ].duplicated(keep=False)

    # Détection d'un mélange entre une ligne globale
    # et des lignes LEFT/RIGHT.
    df["has_mixed_side_granularity"] = df.groupby("Acquisition_ID_normalise")[
        "Acquisition_side"
    ].transform(detect_mixed_side_granularity)

    # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return df


# ============================================================
# 7. LECTURE ET NORMALISATION D'UN FICHIER
# ============================================================


# On lit un classeur puis on applique les contrôles de colonnes, de valeurs et d’identifiants.
def process_excel_file(
    file_path: Path,
    settings: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Lit et normalise un fichier Excel.

    La fonction retourne :
    1. les lignes valides ;
    2. les lignes rejetées ;
    3. le nom du vignoble.
    """

    # On récupère settings['target_sheet'] et on le garde dans target_sheet pour la suite.
    target_sheet = settings["target_sheet"]
    # On récupère settings['required_columns'] et on le garde dans required_columns pour la suite.
    required_columns = settings["required_columns"]
    # On récupère settings['optional_columns'] et on le garde dans optional_columns pour la suite.
    optional_columns = settings["optional_columns"]

    # On assemble ces deux éléments pour construire source_columns.
    source_columns = required_columns + optional_columns

    # dtype="string" limite les conversions automatiques.
    df = pd.read_excel(
        file_path,
        sheet_name=target_sheet,
        # On impose les types lus ou construits pour éviter une interprétation automatique non
        # souhaitée.
        dtype="string",
    )

    # Conservation du numéro de ligne dans le fichier Excel.
    df["source_row_number"] = df.index + 2

    # On garde dans df la valeur renvoyée par clean_column_headers.
    df = clean_column_headers(df)

    # --------------------------------------------------------
    # Vérification des colonnes obligatoires
    # --------------------------------------------------------
    missing_required_columns = [
        column for column in required_columns if column not in df.columns
    ]

    # Cette branche traite le cas où missing_required_columns est évalué comme vrai.
    if missing_required_columns:
        # On interrompt cette branche avec ValueError.
        raise ValueError(f"Colonnes obligatoires absentes : {missing_required_columns}")

    # --------------------------------------------------------
    # Gestion des colonnes facultatives
    # --------------------------------------------------------
    missing_optional_columns = [
        column for column in optional_columns if column not in df.columns
    ]

    # On parcourt missing_optional_columns ; column désigne l’élément courant à chaque passage dans la
    # boucle.
    for column in missing_optional_columns:
        # On garde pd.NA sous le nom df[column] ; cette affectation ne copie pas à elle seule un objet
        # mutable.
        df[column] = pd.NA

    # Cette branche traite le cas où missing_optional_columns est évalué comme vrai.
    if missing_optional_columns:
        # On affiche f'⚠️ Colonnes facultatives absentes : {missing_optional_columns}' dans la sortie
        # du programme.
        print(f"⚠️ Colonnes facultatives absentes : {missing_optional_columns}")

    # Nettoyage des valeurs textuelles.
    df = clean_text_columns(
        df,
        source_columns,
    )

    # --------------------------------------------------------
    # Suppression des lignes sans véritable donnée métier
    # --------------------------------------------------------
    # Une ligne contenant uniquement Vineyard
    # ne représente pas une acquisition.
    business_columns = [column for column in source_columns if column != "Vineyard"]

    # On garde dans df une copie de df.loc[df[business_columns].notna().any(axis=1)] pour travailler
    # sur cet objet séparément.
    df = df.loc[df[business_columns].notna().any(axis=1)].copy()

    # Vérification du vignoble.
    df, vineyard_name = validate_vineyard(
        df,
        file_path,
    )

    # --------------------------------------------------------
    # Métadonnées de traçabilité
    # --------------------------------------------------------
    df["source_file"] = file_path.name
    # On garde target_sheet sous le nom df['source_sheet'] ; cette affectation ne copie pas à elle
    # seule un objet mutable.
    df["source_sheet"] = target_sheet
    # On garde dans df['ingested_at'] la représentation ISO de datetime.now(timezone.utc).
    df["ingested_at"] = datetime.now(timezone.utc).isoformat()

    # --------------------------------------------------------
    # Séparation des lignes sans Acquisition_ID
    # --------------------------------------------------------
    missing_id_mask = df["Acquisition_ID"].isna()

    # On garde dans rejected_df une copie de df.loc[missing_id_mask] pour travailler sur cet objet
    # séparément.
    rejected_df = df.loc[missing_id_mask].copy()

    # On utilise ce texte pour rejected_df['rejection_reason'] ; il ne dépend pas d’une valeur
    # récupérée ailleurs à cet endroit.
    rejected_df["rejection_reason"] = "Acquisition_ID manquant"

    # On garde dans normalized_df une copie de df.loc[~missing_id_mask] pour travailler sur cet objet
    # séparément.
    normalized_df = df.loc[~missing_id_mask].copy()

    # --------------------------------------------------------
    # Normalisation d'Acquisition_ID
    # --------------------------------------------------------
    normalized_df = add_normalized_acquisition_ids(normalized_df)

    # Contrôle strict de l'horodatage.
    # Les lignes invalides restent dans le flux normalisé.
    normalized_df = add_acquisition_timestamp_quality(normalized_df)

    # Ajout des autres indicateurs de qualité liés
    # aux identifiants et à leur granularité.
    normalized_df = add_identifier_quality_flags(normalized_df)

    # --------------------------------------------------------
    # Préparation des règles métier du YAML
    # --------------------------------------------------------
    test_columns = settings["test_search_columns"]
    # On récupère settings['technical_step_columns'] et on le garde dans technical_columns pour la
    # suite.
    technical_columns = settings["technical_step_columns"]

    # On garde dans waiting_expression la valeur renvoyée par build_search_expression.
    waiting_expression = build_search_expression(settings["waiting_values"])

    # On garde dans review_expression la valeur renvoyée par build_search_expression.
    review_expression = build_search_expression(settings["review_values"])

    # --------------------------------------------------------
    # Détection des tests
    # --------------------------------------------------------
    test_mask = contains_expression_in_columns(
        normalized_df,
        test_columns,
        r"\btest\b",
    )

    # --------------------------------------------------------
    # Détection de "en attente"
    # --------------------------------------------------------
    waiting_mask = contains_expression_in_columns(
        normalized_df,
        technical_columns,
        waiting_expression,
    )

    # --------------------------------------------------------
    # Détection de "autre"
    # --------------------------------------------------------
    review_mask = contains_expression_in_columns(
        normalized_df,
        technical_columns,
        review_expression,
    )

    # --------------------------------------------------------
    # Attribution du périmètre
    # --------------------------------------------------------
    # Une cellule vide ne provoque pas de blocage automatique.
    normalized_df["Périmètre"] = "Production"

    # En attente et autre indiquent un arrêt du flux normal.
    normalized_df.loc[
        waiting_mask | review_mask,
        "Périmètre",
    ] = "Bloqué"

    # Le test est prioritaire.
    normalized_df.loc[
        test_mask,
        "Périmètre",
    ] = "Test"

    # --------------------------------------------------------
    # Attribution du statut provisoire
    # --------------------------------------------------------
    normalized_df["Statut_pipeline"] = "À déterminer"

    # On utilise ce texte pour normalized_df.loc[waiting_mask, 'Statut_pipeline'] ; il ne dépend pas
    # d’une valeur récupérée ailleurs à cet endroit.
    normalized_df.loc[
        waiting_mask,
        "Statut_pipeline",
    ] = "En attente"

    # On utilise ce texte pour normalized_df.loc[review_mask, 'Statut_pipeline'] ; il ne dépend pas
    # d’une valeur récupérée ailleurs à cet endroit.
    normalized_df.loc[
        review_mask,
        "Statut_pipeline",
    ] = "Autre"

    # Le test est appliqué en dernier.
    normalized_df.loc[
        test_mask,
        "Statut_pipeline",
    ] = "Hors périmètre"

    # --------------------------------------------------------
    # Indicateurs métier
    # --------------------------------------------------------
    normalized_df["is_test_candidate"] = test_mask
    # On garde waiting_mask sous le nom normalized_df['has_waiting_step'] ; cette affectation ne copie
    # pas à elle seule un objet mutable.
    normalized_df["has_waiting_step"] = waiting_mask
    # On garde review_mask sous le nom normalized_df['needs_review'] ; cette affectation ne copie pas à
    # elle seule un objet mutable.
    normalized_df["needs_review"] = review_mask

    # On combine ces masques avec & pour construire normalized_df['is_blocked_candidate'] ; les
    # parenthèses gardent les comparaisons regroupées.
    normalized_df["is_blocked_candidate"] = (waiting_mask | review_mask) & ~test_mask

    # --------------------------------------------------------
    # Ordre des colonnes du fichier final
    # --------------------------------------------------------
    output_columns = source_columns + [
        # Représentations normalisées de l'identifiant.
        "Acquisition_ID_base",
        "Acquisition_ID_normalise",
        "Acquisition_side",
        "Acquisition_row_key",
        # Contrôle strict de l'horodatage.
        "Acquisition_date",
        "Acquisition_datetime",
        "Acquisition_timestamp_valid",
        "Acquisition_timestamp_issue",
        # Classification métier.
        "Périmètre",
        "Statut_pipeline",
        # Indicateurs métier.
        "is_test_candidate",
        "has_waiting_step",
        "needs_review",
        "is_blocked_candidate",
        # Contrôles sur les identifiants.
        "duplicate_row_key_in_file",
        "has_multiple_rows_same_acquisition",
        "has_mixed_side_granularity",
        # Traçabilité.
        "source_file",
        "source_sheet",
        "source_row_number",
        "ingested_at",
    ]

    # On sélectionne dans normalized_df les éléments désignés par output_columns ; normalized_df
    # recevra cette sélection.
    normalized_df = normalized_df[output_columns]

    # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return (
        normalized_df,
        rejected_df,
        vineyard_name,
    )


# ============================================================
# 8. CONTRÔLES GLOBAUX ET CONSOLIDATION
# ============================================================


def add_global_identifier_flags(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Ajoute les contrôles calculés sur l'ensemble des vignobles.

    Ces contrôles sont effectués après la concaténation
    de tous les fichiers normalisés.
    """

    # Même acquisition normalisée et même côté
    # présents plusieurs fois dans l'ensemble des fichiers.
    df["duplicate_row_key_global"] = df["Acquisition_row_key"].duplicated(keep=False)

    # Plusieurs lignes appartiennent à la même acquisition logique.
    # Cela peut être normal pour LEFT et RIGHT.
    df["has_multiple_rows_same_acquisition_global"] = df[
        "Acquisition_ID_normalise"
    ].duplicated(keep=False)

    # Détection globale du mélange :
    # ligne sans côté + lignes LEFT/RIGHT.
    df["has_mixed_side_granularity_global"] = df.groupby("Acquisition_ID_normalise")[
        "Acquisition_side"
    ].transform(detect_mixed_side_granularity)

    # On remet le tableau de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return df


# ============================================================
# 9. LANCEMENT DE L'INGESTION VERSIONNEE
# ============================================================


def main(argv=None) -> int:
    """Le pilotage des versions est separe des regles de normalisation.

    Les fonctions ci-dessus gardent leurs comportements precedents.
    Le module tracking_versioning assure la selection, l'archivage,
    la publication des references et les manifestes.
    """
    # On vérifie ce cas avant la suite : __package__ appartient à {None, ''}.
    if __package__ in {None, ""}:
        # On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
        import sys

        # On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux
        # importables dans ce contexte.
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    # On rend disponibles versioned_main depuis
    # suivi_traitements_post_saison.ingestion.tracking_versioning, pour les appels de ce fichier.
    from suivi_traitements_post_saison.ingestion.tracking_versioning import (
        main as versioned_main,
    )

    # On fournit à l’appelant la valeur renvoyée par versioned_main.
    return versioned_main(argv)


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
