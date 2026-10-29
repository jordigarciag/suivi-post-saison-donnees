# Lecture du fichier — Tests de acquisition id normalization.
#

"""
Tests unitaires de la normalisation et de la qualité des identifiants.

Ces tests utilisent uniquement des identifiants synthétiques. Ils ne lisent
ni les fichiers Excel réels ni le NAS.
"""

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd

# On rend disponibles normalize_acquisition_id, parse_acquisition_timestamp depuis
# suivi_traitements_post_saison.ingestion.excel_reader, pour les appels de ce fichier.
from suivi_traitements_post_saison.ingestion.excel_reader import (
    normalize_acquisition_id,
    parse_acquisition_timestamp,
)


# ============================================================
# 1. TESTS HISTORIQUES DE NORMALISATION
# ============================================================


def test_short_id_receives_vineyard_prefix():
    """Un identifiant Brut court doit recevoir le nom du vignoble."""

    # On garde dans result l’identifiant d’acquisition ramené à la forme commune prévue.
    result = normalize_acquisition_id(
        # On fournit l’identifiant de l’acquisition via le paramètre acquisition_id de cet appel.
        acquisition_id="C04_V1_2026-06-05T13-30-04",
        # On fournit le domaine concerné via le paramètre vineyard de cet appel.
        vineyard="DomaineDemoH",
    )

    # On compare result['Acquisition_ID_base'] à 'C04_V1_2026-06-05T13-30-04' : le test porte sur
    # cette sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_ID_base"] == ("C04_V1_2026-06-05T13-30-04")
    # On compare result['Acquisition_ID_normalise'] à 'DomaineDemoH_C04_V1_2026-06-05T13-30-04' : le
    # test porte sur cette sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_ID_normalise"] == (
        "DomaineDemoH_C04_V1_2026-06-05T13-30-04"
    )


def test_existing_vineyard_prefix_is_not_duplicated():
    """Un préfixe Vineyard déjà présent ne doit pas être ajouté deux fois."""

    # On garde dans result l’identifiant d’acquisition ramené à la forme commune prévue.
    result = normalize_acquisition_id(
        # On fournit l’identifiant de l’acquisition via le paramètre acquisition_id de cet appel.
        acquisition_id=("DomaineDemoH_C04_V1_2026-06-05T13-30-04"),
        # On fournit le domaine concerné via le paramètre vineyard de cet appel.
        vineyard="DomaineDemoH",
    )

    # On compare result['Acquisition_ID_base'] à 'C04_V1_2026-06-05T13-30-04' : le test porte sur
    # cette sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_ID_base"] == ("C04_V1_2026-06-05T13-30-04")
    # On compare result['Acquisition_ID_normalise'] à 'DomaineDemoH_C04_V1_2026-06-05T13-30-04' : le
    # test porte sur cette sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_ID_normalise"] == (
        "DomaineDemoH_C04_V1_2026-06-05T13-30-04"
    )


def test_left_suffix_is_detected():
    """Le suffixe LEFT doit être retiré de l'identifiant logique."""

    # On garde dans result l’identifiant d’acquisition ramené à la forme commune prévue.
    result = normalize_acquisition_id(
        # On fournit l’identifiant de l’acquisition via le paramètre acquisition_id de cet appel.
        acquisition_id=("DomaineDemoH_C04_V1_2026-06-05T13-30-04_LEFT"),
        # On fournit le domaine concerné via le paramètre vineyard de cet appel.
        vineyard="DomaineDemoH",
    )

    # On compare result['Acquisition_side'] à 'LEFT' : le test porte sur cette sortie précise, pas
    # seulement sur l’absence d’exception.
    assert result["Acquisition_side"] == "LEFT"
    # On compare result['Acquisition_ID_normalise'] à 'DomaineDemoH_C04_V1_2026-06-05T13-30-04' : le
    # test porte sur cette sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_ID_normalise"] == (
        "DomaineDemoH_C04_V1_2026-06-05T13-30-04"
    )
    # On attend que result['Acquisition_row_key'] se termine par le texte '|LEFT'. Si ce contrôle
    # échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_row_key"].endswith("|LEFT")


def test_right_suffix_is_detected():
    """Le suffixe RIGHT doit être retiré de l'identifiant logique."""

    # On garde dans result l’identifiant d’acquisition ramené à la forme commune prévue.
    result = normalize_acquisition_id(
        # On fournit l’identifiant de l’acquisition via le paramètre acquisition_id de cet appel.
        acquisition_id=("DomaineDemoH_C04_V1_2026-06-05T13-30-04_RIGHT"),
        # On fournit le domaine concerné via le paramètre vineyard de cet appel.
        vineyard="DomaineDemoH",
    )

    # On compare result['Acquisition_side'] à 'RIGHT' : le test porte sur cette sortie précise, pas
    # seulement sur l’absence d’exception.
    assert result["Acquisition_side"] == "RIGHT"
    # On compare result['Acquisition_ID_normalise'] à 'DomaineDemoH_C04_V1_2026-06-05T13-30-04' : le
    # test porte sur cette sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_ID_normalise"] == (
        "DomaineDemoH_C04_V1_2026-06-05T13-30-04"
    )
    # On attend que result['Acquisition_row_key'] se termine par le texte '|RIGHT'. Si ce contrôle
    # échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_row_key"].endswith("|RIGHT")


def test_id_without_side_is_marked_unspecified():
    """Une ligne sans suffixe doit conserver une granularité non précisée."""

    # On garde dans result l’identifiant d’acquisition ramené à la forme commune prévue.
    result = normalize_acquisition_id(
        # On fournit l’identifiant de l’acquisition via le paramètre acquisition_id de cet appel.
        acquisition_id=("DomaineDemoH_C04_V1_2026-06-05T13-30-04"),
        # On fournit le domaine concerné via le paramètre vineyard de cet appel.
        vineyard="DomaineDemoH",
    )

    # On compare result['Acquisition_side'] à 'NON_PRÉCISÉ' : le test porte sur cette sortie
    # précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_side"] == "NON_PRÉCISÉ"
    # On attend que result['Acquisition_row_key'] se termine par le texte '|NON_PRÉCISÉ'. Si ce
    # contrôle échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_row_key"].endswith("|NON_PRÉCISÉ")


def test_left_and_right_share_same_normalized_id():
    """LEFT et RIGHT doivent représenter une seule acquisition logique."""

    # On garde dans left_result l’identifiant d’acquisition ramené à la forme commune prévue.
    left_result = normalize_acquisition_id(
        # On fournit l’identifiant de l’acquisition via le paramètre acquisition_id de cet appel.
        acquisition_id=("DomaineDemoH_C04_V1_2026-06-05T13-30-04_LEFT"),
        # On fournit le domaine concerné via le paramètre vineyard de cet appel.
        vineyard="DomaineDemoH",
    )
    # On garde dans right_result l’identifiant d’acquisition ramené à la forme commune prévue.
    right_result = normalize_acquisition_id(
        # On fournit l’identifiant de l’acquisition via le paramètre acquisition_id de cet appel.
        acquisition_id=("DomaineDemoH_C04_V1_2026-06-05T13-30-04_RIGHT"),
        # On fournit le domaine concerné via le paramètre vineyard de cet appel.
        vineyard="DomaineDemoH",
    )

    # On compare left_result['Acquisition_ID_normalise'] à right_result['Acquisition_ID_normalise']
    # : le test porte sur cette sortie précise, pas seulement sur l’absence d’exception.
    assert (
        left_result["Acquisition_ID_normalise"]
        == right_result["Acquisition_ID_normalise"]
    )
    # On attend que left_result['Acquisition_row_key'] diffère de right_result['Acquisition_row_key'].
    # Si ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert left_result["Acquisition_row_key"] != right_result["Acquisition_row_key"]


# ============================================================
# 2. TESTS DU CONTRÔLE STRICT DE L'HORODATAGE
# ============================================================


def test_valid_timestamp_with_second_52_is_recognized():
    """Un horodatage normal doit être extrait sans modification."""

    # On garde dans result la date d’acquisition interprétée avec ses éventuels problèmes de lecture.
    result = parse_acquisition_timestamp(
        "DomaineDemoC_C06_V2_2026-07-20T08-01-52"
    )

    # On compare result['Acquisition_date'] à '2026-07-20' : le test porte sur cette sortie précise,
    # pas seulement sur l’absence d’exception.
    assert result["Acquisition_date"] == "2026-07-20"
    # On compare result['Acquisition_datetime'] à '2026-07-20 08:01:52' : le test porte sur cette
    # sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_datetime"] == ("2026-07-20 08:01:52")
    # On attend que result['Acquisition_timestamp_valid'] est exactement la valeur vraie (True). Si ce
    # contrôle échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_timestamp_valid"] is True
    # On attend que le contrôle pd.isna(result['Acquisition_timestamp_issue']) est positif. Si ce
    # contrôle échoue, le scénario s’arrête sur cette assertion.
    assert pd.isna(result["Acquisition_timestamp_issue"])


def test_second_59_is_valid():
    """La seconde 59 est la dernière valeur valide d'une minute."""

    # On garde dans result la date d’acquisition interprétée avec ses éventuels problèmes de lecture.
    result = parse_acquisition_timestamp(
        "DomaineDemoC_C06_V2_2026-07-20T08-01-59"
    )

    # On compare result['Acquisition_datetime'] à '2026-07-20 08:01:59' : le test porte sur cette
    # sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_datetime"] == ("2026-07-20 08:01:59")
    # On attend que result['Acquisition_timestamp_valid'] est exactement la valeur vraie (True). Si ce
    # contrôle échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_timestamp_valid"] is True
    # On attend que le contrôle pd.isna(result['Acquisition_timestamp_issue']) est positif. Si ce
    # contrôle échoue, le scénario s’arrête sur cette assertion.
    assert pd.isna(result["Acquisition_timestamp_issue"])


def test_second_60_is_rejected():
    """La seconde 60 doit être signalée au lieu d'être normalisée."""

    # On garde dans result la date d’acquisition interprétée avec ses éventuels problèmes de lecture.
    result = parse_acquisition_timestamp(
        "DomaineDemoC_C06_V2_2026-07-20T08-01-60"
    )

    # On compare result['Acquisition_date'] à '2026-07-20' : le test porte sur cette sortie précise,
    # pas seulement sur l’absence d’exception.
    assert result["Acquisition_date"] == "2026-07-20"
    # On attend que le contrôle pd.isna(result['Acquisition_datetime']) est positif. Si ce contrôle
    # échoue, le scénario s’arrête sur cette assertion.
    assert pd.isna(result["Acquisition_datetime"])
    # On attend que result['Acquisition_timestamp_valid'] est exactement la valeur fausse (False). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_timestamp_valid"] is False
    # On compare result['Acquisition_timestamp_issue'] à 'Secondes hors plage' : le test porte sur
    # cette sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_timestamp_issue"] == ("Secondes hors plage")


def test_second_66_is_rejected():
    """La valeur 66 doit être reconnue comme une seconde impossible."""

    # On garde dans result la date d’acquisition interprétée avec ses éventuels problèmes de lecture.
    result = parse_acquisition_timestamp(
        "DomaineDemoC_C06_V2_2026-07-20T08-01-66"
    )

    # On compare result['Acquisition_date'] à '2026-07-20' : le test porte sur cette sortie précise,
    # pas seulement sur l’absence d’exception.
    assert result["Acquisition_date"] == "2026-07-20"
    # On attend que le contrôle pd.isna(result['Acquisition_datetime']) est positif. Si ce contrôle
    # échoue, le scénario s’arrête sur cette assertion.
    assert pd.isna(result["Acquisition_datetime"])
    # On attend que result['Acquisition_timestamp_valid'] est exactement la valeur fausse (False). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_timestamp_valid"] is False
    # On compare result['Acquisition_timestamp_issue'] à 'Secondes hors plage' : le test porte sur
    # cette sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_timestamp_issue"] == ("Secondes hors plage")


def test_impossible_calendar_date_is_rejected():
    """Une date comme le 30 février ne doit pas être acceptée."""

    # On garde dans result la date d’acquisition interprétée avec ses éventuels problèmes de lecture.
    result = parse_acquisition_timestamp("DomaineDemoB_C01_V1_2026-02-30T10-00-00")

    # On attend que le contrôle pd.isna(result['Acquisition_date']) est positif. Si ce contrôle échoue,
    # le scénario s’arrête sur cette assertion.
    assert pd.isna(result["Acquisition_date"])
    # On attend que le contrôle pd.isna(result['Acquisition_datetime']) est positif. Si ce contrôle
    # échoue, le scénario s’arrête sur cette assertion.
    assert pd.isna(result["Acquisition_datetime"])
    # On attend que result['Acquisition_timestamp_valid'] est exactement la valeur fausse (False). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_timestamp_valid"] is False
    # On compare result['Acquisition_timestamp_issue'] à 'Date invalide' : le test porte sur cette
    # sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_timestamp_issue"] == "Date invalide"


def test_identifier_without_timestamp_is_flagged():
    """Un identifiant sans horodatage terminal doit rester contrôlable."""

    # On garde dans result la date d’acquisition interprétée avec ses éventuels problèmes de lecture.
    result = parse_acquisition_timestamp("DomaineDemoB_C01_V1_sans_horodatage")

    # On attend que le contrôle pd.isna(result['Acquisition_date']) est positif. Si ce contrôle échoue,
    # le scénario s’arrête sur cette assertion.
    assert pd.isna(result["Acquisition_date"])
    # On attend que le contrôle pd.isna(result['Acquisition_datetime']) est positif. Si ce contrôle
    # échoue, le scénario s’arrête sur cette assertion.
    assert pd.isna(result["Acquisition_datetime"])
    # On attend que result['Acquisition_timestamp_valid'] est exactement la valeur fausse (False). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_timestamp_valid"] is False
    # On compare result['Acquisition_timestamp_issue'] à 'Horodatage absent ou format non reconnu' :
    # le test porte sur cette sortie précise, pas seulement sur l’absence d’exception.
    assert result["Acquisition_timestamp_issue"] == (
        "Horodatage absent ou format non reconnu"
    )


def test_invalid_timestamp_is_not_silently_normalized():
    """08-01-60 ne doit surtout pas devenir automatiquement 08:02:00."""

    # On garde dans result la date d’acquisition interprétée avec ses éventuels problèmes de lecture.
    result = parse_acquisition_timestamp(
        "DomaineDemoC_C06_V2_2026-07-20T08-01-60"
    )

    # Une valeur manquante est attendue : aucune date corrigée
    # telle que 08:02:00 ne doit être fabriquée.
    assert pd.isna(result["Acquisition_datetime"])
    # On attend que result['Acquisition_timestamp_valid'] est exactement la valeur fausse (False). Si
    # ce contrôle échoue, le scénario s’arrête sur cette assertion.
    assert result["Acquisition_timestamp_valid"] is False
