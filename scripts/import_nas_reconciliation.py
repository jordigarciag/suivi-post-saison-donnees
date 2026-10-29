# Lecture du fichier — Contrôle des résultats NAS et de rapprochement avant leur chargement.
# On vérifie les fichiers, leur structure et leurs relations. Comme à la réception d’un colis, on ne
# se contente pas de constater qu’un emballage est arrivé.
#

"""Premier palier de l'import NAS/rapprochement : controle local sans ecriture.

--check-only est le seul mode disponible. Aucun acces NAS/PostgreSQL/.env.
Les chemins NAS contenus dans les CSV restent des valeurs : ils ne sont pas ouverts.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On importe csv. On transforme les tableaux entre lignes Python et fichiers CSV.
import csv
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On rend disponibles Counter depuis collections, pour les appels de ce fichier.
from collections import Counter
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path, PurePosixPath, PureWindowsPath depuis pathlib, pour les appels de ce
# fichier.
from pathlib import Path, PurePosixPath, PureWindowsPath
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys

# On rend disponibles LocalFiles, ValidationError, date_value, hash_value, read_csv, require, sha256
# depuis load_excel_publication, pour les appels de ce fichier.
from load_excel_publication import (
    LocalFiles,
    ValidationError,
    date_value,
    hash_value,
    read_csv,
    require,
    sha256,
)

# On fixe PUB_ROOT à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
PUB_ROOT = "data/03_normalized/suivi_acquisitions_normalises/publications"
# On rassemble dans KINDS les 3 éléments explicitement indiqués, en conservant leur structure.
KINDS = ("acquisitions", "associations", "passages")
# On regroupe dans KEYS ces champs nommés ; on pourra les retrouver par leur clé plutôt que par leur
# position.
KEYS = {
    # On renseigne les acquisitions sous la clé 'acquisitions'.
    "acquisitions": ("Vineyard", "acquisition_id_normalise"),
    # On renseigne les associations entre acquisitions et passages sous la clé 'associations'.
    "associations": (
        "Vineyard",
        "acquisition_id_normalise",
        "parcel_name",
        "passage_name",
    ),
    # On renseigne les passages sous la clé 'passages'.
    "passages": ("Vineyard", "parcel_name", "passage_name"),
}
# On regroupe dans BASE_COLUMNS ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
# leur position.
BASE_COLUMNS = {
    # On renseigne les acquisitions sous la clé 'acquisitions'.
    "acquisitions": {
        "Vineyard",
        "project_year",
        "acquisition_id_normalise",
        "checked_at",
        "parcel_names_json",
        "parcel_count",
        "passage_links_json",
        "passage_link_count",
        "passage_outputs_verifiable",
        "vitiparcel_created",
    },
    # On renseigne les associations entre acquisitions et passages sous la clé 'associations'.
    "associations": {
        "Vineyard",
        "project_year",
        "acquisition_id_normalise",
        "parcel_name",
        "passage_name",
        "checked_at",
        "passage_outputs_verifiable",
        "vitiparcel_created",
    },
    # On renseigne les passages sous la clé 'passages'.
    "passages": {
        "Vineyard",
        "project_year",
        "parcel_name",
        "passage_name",
        "checked_at",
        "acquisitions_controlled_count",
        "acquisition_ids_json",
        "stocks_json_exists",
        "non_healthy_status_count",
        "vitiparcel_created",
    },
}
# On rassemble dans EXCEL_CONTEXT les 6 éléments explicitement indiqués, en conservant leur structure.
EXCEL_CONTEXT = {
    "excel_acquisition_id_normalise",
    "excel_vineyard",
    "excel_ingested_at",
    "excel_source_files",
    "excel_perimeter",
    "excel_pipeline_status",
}
# On regroupe dans RESULT_COLUMNS ces champs nommés ; on pourra les retrouver par leur clé plutôt que
# par leur position.
RESULT_COLUMNS = {
    # On renseigne les acquisitions sous la clé 'acquisitions'.
    "acquisitions": EXCEL_CONTEXT
    | {
        "reconciled_at",
        "processing_business_category",
        "acquisition_new_anomaly_candidate",
    },
    # On renseigne les associations entre acquisitions et passages sous la clé 'associations'.
    "associations": EXCEL_CONTEXT,
    # On renseigne les passages sous la clé 'passages'.
    "passages": {
        "vitiparcel_ready_verifiable",
        "vitiparcel_ready_for_delivery",
        "passage_review_candidate",
        "passage_business_category",
    },
}


# On prépare des valeurs compatibles avec le JSON attendu par ce contrôle.
def plain_json(data, label):
    # On vérifie l’unicité des clés pour ne pas choisir arbitrairement entre des lignes concurrentes.
    def unique_keys(pairs):
        # On crée le dictionnaire vide result pour y ranger ensuite les éléments par clé.
        result = {}
        # On parcourt pairs ; (key, value) désigne l’élément courant à chaque passage dans la boucle.
        for key, value in pairs:
            # On exige ici que la clé de l’élément ne figure pas dans le résultat de cette opération.
            # Si ce n’est pas le cas, le message associé bloque la suite.
            require(key not in result, "Cle JSON dupliquee : " + label + " / " + key)
            # On garde la valeur reçue sous le nom result[key] ; cette affectation ne copie pas à elle
            # seule un objet mutable.
            result[key] = value
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    # On tente ce bloc et on traite séparément les erreurs prévues : (UnicodeError,
    # json.JSONDecodeError).
    try:
        # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite,
        # car un JSON lisible n’est pas forcément un lot valide.
        result = json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        # On interrompt cette branche avec ValidationError. La cause initiale reste attachée grâce à
        # from.
        raise ValidationError("JSON illisible : " + label) from exc
    # On exige ici que le résultat de cette opération est du type dict. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(isinstance(result, dict), "Objet JSON attendu : " + label)
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On applique la conversion sur une colonne complète ; si elle manque, on prépare des valeurs
# inconnues.
def boolean(value, label, *, nullable=False):
    # On exige ici que la valeur reçue est du type str. Si ce n’est pas le cas, le message associé
    # bloque la suite.
    require(isinstance(value, str), "Booleen CSV invalide : " + label)
    # Cette branche traite le cas où nullable est évalué comme vrai et la valeur reçue correspond à le
    # texte ''.
    if nullable and value == "":
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None
    # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
    # enregistré dans les données sources.
    normalized = value.strip().casefold()
    # On exige ici que normalized appartient à {'true', 'false'}. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(normalized in {"true", "false"}, "Booleen absent ou inconnu : " + label)
    # On renvoie le booléen obtenu par cette comparaison : normalized correspond au texte 'true'.
    return normalized == "true"


# On contrôle la conversion en entier selon les valeurs acceptées ici.
def integer(value, label):
    # On exige ici que la valeur reçue est du type str et le contrôle re.fullmatch('0|[1-9][0-9]*',
    # value) est positif. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value),
        "Entier CSV invalide : " + label,
    )
    # On fournit à l’appelant la conversion numérique de la valeur reçue en entier.
    return int(value)


# On lit la liste structurée attendue plutôt que traiter un texte JSON comme une liste Python.
def json_list(value, label):
    # On tente ce bloc et on traite séparément les erreurs prévues : (TypeError, json.JSONDecodeError).
    try:
        # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite,
        # car un JSON lisible n’est pas forcément un lot valide.
        result = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        # On interrompt cette branche avec ValidationError. La cause initiale reste attachée grâce à
        # from.
        raise ValidationError("Liste JSON illisible : " + label) from exc
    # On exige ici que le résultat de cette opération est du type list. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(isinstance(result, list), "Liste JSON attendue : " + label)
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


class ManifestPaths:
    """Ramene les chemins du manifeste dans le projet local, sans ouvrir le NAS.

    Sur Windows, les chemins absolus doivent designer ce projet. Sur Linux,
    la racine Windows d'origine sert a reconstruire un exemple/test local.
    Les chemins absolus POSIX doivent rester dans la racine locale courante.
    Les chemins relatifs sont aussi acceptes, dans data/ seulement.
    """

    def __init__(self, root, reference_source):
        # On ramène la racine locale à un chemin absolu ; les contrôles suivants partiront du même
        # emplacement.
        self.root = Path(root).resolve()
        # On décompose le chemin Windows indiqué dans le manifeste, même si ce script tourne sous
        # Linux. PureWindowsPath manipule ici du texte : il ne contacte pas le NAS.
        source = PureWindowsPath(reference_source)
        # Au départ, on ne connaît pas la racine du projet Windows d’origine. On ne pourra donc pas
        # accepter n’importe quel chemin absolu.
        self.windows_root = None
        # On ne déduit la racine Windows d’origine que d’un chemin absolu ; une entrée relative ne
        # suffit pas à l’identifier.
        if source.is_absolute():
            # On sépare le lecteur et les dossiers : C:/demo/data/lot.csv devient, en simplifiant,
            # C:, demo, data, lot.csv.
            parts = source.parts
            # On repère le dossier data sans tenir compte de la casse. Deux dossiers portant ce nom
            # rendraient le choix de la racine ambigu.
            indices = [i for i, part in enumerate(parts) if part.casefold() == "data"]
            # Il faut un seul dossier data dans ce chemin pour séparer sans ambiguïté la racine et
            # la partie relative.
            require(len(indices) == 1, "Racine data ambiguë dans reference_source.")
            # On garde uniquement ce qui précède data. Avec C:/demo/data/lot.csv, la racine
            # d’origine est C:/demo ; l’étoile redonne chaque morceau au constructeur du chemin.
            self.windows_root = PureWindowsPath(*parts[: indices[0]])
            # Sur Windows, la racine indiquée doit être celle de cette copie. On refuse de rattacher
            # les fichiers d’un autre projet par simple ressemblance.
            if os.name == "nt":
                # On exige ici que self.windows_root correspond à PureWindowsPath(str(self.root)). Si
                # ce n’est pas le cas, le message associé bloque la suite.
                require(
                    self.windows_root == PureWindowsPath(str(self.root)),
                    "Les chemins absolus du manifeste designent un autre projet. Ne pas deplacer les fichiers sans procedure.",
                )

    def relative(self, value):
        # On exige d’abord une chaîne non vide : sans cela, aucun des cas de chemin ci-dessous ne
        # serait interprétable correctement.
        require(isinstance(value, str) and value, "Chemin de manifeste absent.")
        # On commence par interpréter la syntaxe Windows : cela permet aussi de reconnaître un
        # lecteur ou un partage réseau depuis Linux.
        windows = PureWindowsPath(value)
        # Ce premier cas concerne un chemin Windows absolu. Il faut en connaître la racine pour le
        # rattacher au projet local.
        if windows.is_absolute():
            # Un chemin absolu ne peut être ramené au projet que si la racine Windows d’origine a
            # été identifiée auparavant.
            require(
                self.windows_root is not None,
                "Chemin absolu sans racine de projet identifiee.",
            )
            # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
            try:
                # On retire la racine Windows connue, puis on écrit le reste avec des /. Exemple :
                # C:/demo/data/lot.csv devient data/lot.csv ; relative_to refuse un chemin situé
                # ailleurs.
                result = windows.relative_to(self.windows_root).as_posix()
            except ValueError as exc:
                # On interrompt cette branche avec ValidationError. La cause initiale reste attachée
                # grâce à from.
                raise ValidationError(
                    "Chemin hors du projet d origine : " + value
                ) from exc
        # Ce cas traite un chemin absolu Linux ; le préfixe // n’entre pas dans cette branche, car
        # il peut désigner un partage réseau.
        elif value.startswith("/") and not value.startswith("//"):
            # Chemin natif Linux : jamais de reconstruction depuis une autre racine.
            require(os.name != "nt", "Chemin POSIX absolu non natif : " + value)
            # Cette branche traite un chemin absolu de type Linux. On en découpe les composants sans
            # ouvrir le fichier.
            posix = PurePosixPath(value)
            # On écarte les séparateurs Windows et les remontées .. de cette branche : il ne faut ni
            # syntaxe mélangée ni sortie par un dossier parent.
            require(
                "\\" not in value and ".." not in posix.parts,
                "Chemin POSIX ambigu ou traversant : " + value,
            )
            # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
            try:
                # On retire cette fois la racine locale courante, pas celle du poste Windows. Un
                # chemin extérieur provoque une erreur plutôt qu’un déplacement implicite.
                result = posix.relative_to(
                    PurePosixPath(self.root.as_posix())
                ).as_posix()
            except ValueError as exc:
                # On interrompt cette branche avec ValidationError. La cause initiale reste attachée
                # grâce à from.
                raise ValidationError(
                    "Chemin POSIX hors du projet courant : " + value
                ) from exc
            # Gardes verifications de confinement, dont les liens symboliques,
            # du lecteur existant. Aucun fichier n'est lu ou modifie ici.
            require(
                PurePosixPath(result).parts
                # On exige aussi que PurePosixPath(result).parts[0] correspond au texte 'data'.
                and PurePosixPath(result).parts[0] == "data",
                "Seuls les fichiers data/ locaux sont autorises : " + value,
            )
            # On réutilise aussi le contrôle du lecteur local, notamment pour une redirection par
            # lien symbolique. Cette vérification de chemin ne lit pas le contenu du fichier.
            LocalFiles(self.root).path(result)
        else:
            # Dans le cas relatif, on interdit aussi les formes comme C:lot.csv : elles dépendent du
            # lecteur courant et ne désignent pas un chemin relatif simple.
            require(
                not windows.drive and not windows.root, "Chemin non relatif : " + value
            )
            # On uniformise les séparateurs du chemin relatif : data\lot.csv et data/lot.csv seront
            # représentés de la même manière.
            result = value.replace("\\", "/")
        # On découpe le résultat normalisé pour vérifier son premier dossier et repérer un éventuel
        # .. avant du rendre au chargeur.
        parts = PurePosixPath(result).parts
        # Le résultat doit rester sous data et ne contenir aucune remontée .. ; normaliser les
        # séparateurs ne suffit pas à garantir ce périmètre.
        require(
            parts and parts[0] == "data" and ".." not in parts,
            "Seuls les fichiers data/ locaux sont autorises : " + value,
        )
        # On renvoie un chemin relatif avec des / ; ce n’est toujours pas une lecture du fichier ni
        # un scan du NAS.
        return PurePosixPath(result).as_posix()


# On construit un accès par clé en respectant les contrôles d’unicité du module.
def keyed(rows, kind, label):
    # On crée le dictionnaire vide result pour y ranger ensuite les éléments par clé.
    result = {}
    # On parcourt les lignes ; row désigne l’élément courant à chaque passage dans la boucle.
    for row in rows:
        # On garde dans key une séquence non modifiable construite à partir de (row[column] for column
        # in KEYS[kind]).
        key = tuple(row[column] for column in KEYS[kind])
        # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(all(part.strip() for part in key), "Cle incomplete : " + label)
        # On exige ici que la clé de l’élément ne figure pas dans le résultat de cette opération. Si ce
        # n’est pas le cas, le message associé bloque la suite.
        require(key not in result, "Cle dupliquee : " + label)
        # On garde la ligne en cours sous le nom result[key] ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        result[key] = row
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On vérifie que les cellules structurées contiennent le type de document attendu.
def validate_json_cells(rows, label):
    # On parcourt les lignes en gardant aussi sa position dans (ordinal, row) ; le comptage commence à
    # 1.
    for ordinal, row in enumerate(rows, 1):
        # On parcourt les couples (column, value) de row : on garde ensemble la clé et sa valeur au
        # lieu des traiter dans deux listes séparées.
        for column, value in row.items():
            # Cette branche traite le cas où column se termine par le texte '_json' et la valeur reçue
            # est évalué comme vrai.
            if column.endswith("_json") and value:
                # On tente ce bloc et on traite séparément les erreurs prévues : json.JSONDecodeError.
                try:
                    # On décodu texte JSON en objets Python ; les contrôles de structure viennent
                    # ensuite, car un JSON lisible n’est pas forcément un lot valide.
                    json.loads(value)
                except json.JSONDecodeError as exc:
                    # On interrompt cette branche avec ValidationError. La cause initiale reste
                    # attachée grâce à from.
                    raise ValidationError(
                        "JSON de cellule invalide : "
                        + label
                        + " / "
                        + column
                        + " / "
                        + str(ordinal)
                    ) from exc


# On vérifie que les identifiants et associations se rattachent aux éléments attendus.
def validate_relations(nas):
    # On indexe le résultat par row['acquisition_id_normalise'], avec row comme valeur ; les
    # contrôles d’unicité sont importants car une même clé ne garde qu’une valeur dans un
    # dictionnaire.
    acquisitions = {row["acquisition_id_normalise"]: row for row in nas["acquisitions"]}
    # On indexe le résultat par (row['parcel_name'], row['passage_name']), avec row comme valeur ;
    # les contrôles d’unicité sont importants car une même clé ne garde qu’une valeur dans un
    # dictionnaire.
    passages = {
        (row["parcel_name"], row["passage_name"]): row for row in nas["passages"]
    }
    # On indexe le résultat par key, avec set() comme valeur ; les contrôles d’unicité sont
    # importants car une même clé ne garde qu’une valeur dans un dictionnaire.
    links = {key: set() for key in acquisitions}
    # On indexe reverse par key ; chaque clé sera associée à set(). Une même clé ne peut garder qu’une
    # valeur.
    reverse = {key: set() for key in passages}
    # On parcourt les associations entre acquisitions et passages dans nas ; row désigne l’élément
    # courant à chaque passage dans la boucle.
    for row in nas["associations"]:
        # On récupère l’identifiant normalisé de l’acquisition dans row et on le garde dans acquisition
        # pour la suite.
        acquisition = row["acquisition_id_normalise"]
        # On rassemble dans passage les 2 éléments explicitement indiqués, en conservant leur
        # structure.
        passage = row["parcel_name"], row["passage_name"]
        # On exige ici que acquisition appartient aux acquisitions. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            acquisition in acquisitions,
            "Association vers une acquisition inconnue : " + acquisition,
        )
        # On exige ici que passage appartient aux passages. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(
            passage in passages,
            "Association vers un passage inconnu : " + row["passage_name"],
        )
        # On ajoute passage à links[acquisition] ; comme il s’agit d’un ensemble, une valeur déjà
        # présente n’est pas comptée deux fois.
        links[acquisition].add(passage)
        # On ajoute acquisition à reverse[passage] ; comme il s’agit d’un ensemble, une valeur déjà
        # présente n’est pas comptée deux fois.
        reverse[passage].add(acquisition)
    # On parcourt les couples (acquisition, row) de acquisitions : on garde ensemble la clé et sa
    # valeur au lieu des traiter dans deux listes séparées.
    for acquisition, row in acquisitions.items():
        # On garde dans listed la valeur renvoyée par json_list.
        listed = json_list(
            row["passage_links_json"], acquisition + ".passage_links_json"
        )
        # Toutes les colonnes ou clés indispensables doivent être présentes ; des champs
        # supplémentaires ne compensent pas l’absence de l’un d’eux.
        require(
            all(
                isinstance(link, dict)
                # On exige aussi que le contrôle {'parcel_name', 'passage_name'}.issubset(link) est
                # positif.
                and {"parcel_name", "passage_name"}.issubset(link)
                for link in listed
            ),
            "Lien JSON incomplet : " + acquisition,
        )
        # On construit expected comme un ensemble sans doublons à partir de (link['parcel_name'],
        # link['passage_name']), pour chaque link de listed.
        expected = {(link["parcel_name"], link["passage_name"]) for link in listed}
        # On exige ici que len(expected) correspond à len(listed) et le résultat attendu correspond à
        # links[acquisition]. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            len(expected) == len(listed) and expected == links[acquisition],
            "Liens NAS incoherents : " + acquisition,
        )
        # On exige ici que integer(row['passage_link_count'], acquisition) correspond à len(expected).
        # Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            integer(row["passage_link_count"], acquisition) == len(expected),
            "Comptage de liens incoherent : " + acquisition,
        )
        # On garde dans parcels la valeur renvoyée par json_list.
        parcels = json_list(
            row["parcel_names_json"], acquisition + ".parcel_names_json"
        )
        # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            all(isinstance(parcel, str) and parcel for parcel in parcels),
            "Liste de parcelles invalide : " + acquisition,
        )
        # On vérifie l’unicité avant de constituer le résultat ; écraser une entrée dupliquée ferait
        # disparaître une incohérence de la source.
        require(
            len(parcels) == len(set(parcels))
            # On exige aussi que integer(row['parcel_count'], acquisition) correspond à len(parcels).
            and integer(row["parcel_count"], acquisition) == len(parcels),
            "Liste/comptage de parcelles incoherents : " + acquisition,
        )
        # On calcule la différence entre ces deux valeurs pour construire outside.
        outside = {pair[0] for pair in expected} - set(parcels)
        # Cette branche traite le cas où outside est évalué comme vrai.
        if outside:
            # Deux mappings sources peuvent se contredire. Conserver un ecart
            # EXPLICITEMENT observe n'est pas accepter une relation comme saine.
            require(
                boolean(
                    row.get("parcel_mapping_consistent", ""),
                    acquisition + ".parcel_mapping_consistent",
                )
                is False,
                "Ecart entre mappings non signale dans l observation : " + acquisition,
            )
            # On construit outside_rows comme une liste à partir de link, pour chaque link de
            # nas['associations'] en ne gardant que les éléments qui passent le filtre.
            outside_rows = [
                link
                for link in nas["associations"]
                if link["acquisition_id_normalise"] == acquisition
                # On exige aussi que link['parcel_name'] appartient à outside.
                and link["parcel_name"] in outside
            ]
            # On exige ici que outside_rows est évalué comme vrai et tous les éléments satisfont le
            # test indiqué. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                outside_rows
                # On exige aussi que tous les éléments satisfont le test indiqué.
                and all(
                    boolean(
                        link.get("parcel_mapping_consistent", ""),
                        acquisition + ".association.parcel_mapping_consistent",
                    )
                    is False
                    for link in outside_rows
                ),
                "Association hors mapping non signalee incoherente : " + acquisition,
            )
    # On parcourt les couples (passage, row) de passages : on garde ensemble la clé et sa valeur au
    # lieu des traiter dans deux listes séparées.
    for passage, row in passages.items():
        # On garde dans ids la valeur renvoyée par json_list.
        ids = json_list(row["acquisition_ids_json"], row["passage_name"])
        # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            all(isinstance(value, str) and value for value in ids),
            "Liste d acquisitions invalide : " + row["passage_name"],
        )
        # On exige ici que len(ids) correspond à len(set(ids)) et set(ids) correspond à
        # reverse[passage] et integer(row['acquisitions_controlled_count'], row['passage_name'])
        # correspond à len(ids). Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            len(ids) == len(set(ids))
            # On exige aussi que set(ids) correspond à reverse[passage].
            and set(ids) == reverse[passage]
            # On exige aussi que integer(row['acquisitions_controlled_count'], row['passage_name'])
            # correspond à len(ids).
            and integer(row["acquisitions_controlled_count"], row["passage_name"])
            == len(ids),
            "Acquisitions du passage incoherentes : " + row["passage_name"],
        )


def read_result_csv(
    data, label, required_columns, *, kind, declared_associations, compatibility
):
    """Compatibilite d'un ancien export d'associations VIDE uniquement.

    Seule l'omission de passage_outputs_verifiable est tolerable, sans ligne,
    avec volume nul declare. Les controles des liens d'acquisition et des cles
    NAS/rapprochement sont ensuite appliques normalement. Aucun octet modifie.
    """
    # On choisit la valeur de missing_allowed selon ce test : kind correspond au texte
    # 'associations'. Les deux résultats possibles restent définis explicitement ici.
    missing_allowed = (
        {"passage_outputs_verifiable"} if kind == "associations" else set()
    )
    # On garde dans rows les lignes décodées par le lecteur CSV de ce module.
    rows = read_csv(data, label, required_columns - missing_allowed)
    # On garde csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline='')).fieldnames sous le nom
    # columns ; cette affectation ne copie pas à elle seule un objet mutable.
    columns = csv.DictReader(
        io.StringIO(data.decode("utf-8-sig"), newline="")
    ).fieldnames
    # On calcule la différence entre ces deux valeurs pour construire missing.
    missing = required_columns - set(columns)
    # Cette branche traite le cas où missing est évalué comme vrai.
    if missing:
        # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas,
        # le message associé bloque la suite.
        require(
            kind == "associations"
            # On exige aussi que missing correspond à {'passage_outputs_verifiable'}.
            and missing == {"passage_outputs_verifiable"}
            # On exige aussi que la condition rows n’est pas remplie.
            and not rows
            # On exige aussi que type(declared_associations) est exactement int.
            and type(declared_associations) is int
            # On exige aussi que declared_associations correspond à 0.
            and declared_associations == 0,
            "Colonnes indispensables absentes hors du cas historique vide autorise : "
            + label,
        )
        # On ajoute label à la fin de compatibility ; les éléments précédents restent conservés.
        compatibility.append(label)
    # On remet les lignes à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return rows


# On vérifie les fichiers et liens annoncés pour cette exécution du pipeline.
def check_pipeline(root, manifest_relative, *, files=None):
    # On choisit la valeur de files selon ce test : files est renseigné (différent de None). Les deux
    # résultats possibles restent définis explicitement ici.
    files = files if files is not None else LocalFiles(root)
    # On recontrôle les métadonnées du fichier ; un changement pendant la lecture rendrait le lot
    # difficile à rattacher à une version précise.
    require(
        manifest_relative.startswith("data/"),
        "Le manifeste doit etre dans data/ du projet.",
    )
    # On garde dans state le chemin après vérification de son périmètre autorisé.
    state = files.path("state/excel_ingestion")

    # On refuse un état qui indique qu’une ingestion concurrente pourrait modifier les fichiers
    # contrôlés.
    def no_ingestion():
        # On exige ici que la condition (state / 'ingestion.lock').exists() n’est pas remplie et la
        # condition (state / 'pending_publication.json').exists() n’est pas remplie. Si ce n’est pas le
        # cas, le message associé bloque la suite.
        require(
            not (state / "ingestion.lock").exists()
            # On exige aussi que la condition (state / 'pending_publication.json').exists() n’est pas
            # remplie.
            and not (state / "pending_publication.json").exists(),
            "Ingestion/publication Excel en cours ou interrompue : controle bloque, ne pas supprimer les verrous aveuglement.",
        )

    # On appelle no_ingestion sans argument positionnel.
    no_ingestion()
    # On garde dans manifest la valeur renvoyée par plain_json.
    manifest = plain_json(files.read(manifest_relative), manifest_relative)
    # On exige ici que l’état du traitement dans manifest correspond au texte 'success'. Si ce n’est
    # pas le cas, le message associé bloque la suite.
    require(
        manifest["status"] == "success",
        "Le pilote ne declare pas une execution entierement reussie.",
    )
    # On récupère l’identifiant du traitement NAS dans manifest et on le garde dans execution_id pour
    # la suite.
    execution_id = manifest["pipeline_execution_id"]
    # On exige ici que l’identifiant d’exécution est du type str et le contrôle
    # re.fullmatch('[A-Za-z0-9_-]+', execution_id) est positif. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        isinstance(execution_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", execution_id),
        "Identifiant du pilote invalide.",
    )
    # On exige ici que manifest_relative correspond à 'data/03_normalized/pipeline_runs/' +
    # execution_id + '/manifest.json'. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        manifest_relative
        == "data/03_normalized/pipeline_runs/" + execution_id + "/manifest.json",
        "Chemin du manifeste incompatible avec son execution.",
    )
    # On exige ici que type(manifest['project_year']) est exactement int. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(type(manifest["project_year"]) is int, "Annee de projet invalide.")
    # On récupère manifest['project_year'] et on le garde dans year pour la suite.
    year = manifest["project_year"]
    # On garde dans start la date validée et convertie selon le format du chargeur.
    start = date_value(manifest["started_at"], "pipeline.started_at")
    # On garde dans finish la date validée et convertie selon le format du chargeur.
    finish = date_value(manifest["finished_at"], "pipeline.finished_at")
    # On exige ici que start ne dépasse pas finish. Si ce n’est pas le cas, le message associé bloque
    # la suite.
    require(start <= finish, "Chronologie du pilote incoherente.")
    # On vérifie l’empreinte du contenu par rapport au lot annoncé ; avoir le bon nom de fichier ne
    # suffit pas à identifier sa version.
    require(
        isinstance(manifest["script_sha256"], dict) and manifest["script_sha256"],
        "Identite des scripts absente.",
    )
    # On parcourt les couples (label, value) de manifest['script_sha256'] : on garde ensemble la clé
    # et sa valeur au lieu des traiter dans deux listes séparées.
    for label, value in manifest["script_sha256"].items():
        # On appelle hash_value avec value.
        hash_value(value, label)
    # On garde dans paths la valeur renvoyée par ManifestPaths.
    paths = ManifestPaths(root, manifest["reference_source"])
    # On garde dans reference_path la valeur renvoyée par paths.relative.
    reference_path = paths.relative(manifest["reference_source"])
    # On garde PurePosixPath(reference_path).parent sous le nom publication_dir ; cette affectation ne
    # copie pas à elle seule un objet mutable.
    publication_dir = PurePosixPath(reference_path).parent
    # On exige ici que publication_dir.parent.as_posix() correspond à PUB_ROOT et
    # PurePosixPath(reference_path).name correspond au texte 'reference.csv'. Si ce n’est pas le cas,
    # le message associé bloque la suite.
    require(
        publication_dir.parent.as_posix() == PUB_ROOT
        # On exige aussi que PurePosixPath(reference_path).name correspond au texte 'reference.csv'.
        and PurePosixPath(reference_path).name == "reference.csv",
        "La reference doit etre un snapshot de publication Excel, pas un export courant.",
    )
    # On garde publication_dir.name sous le nom publication_id ; cette affectation ne copie pas à elle
    # seule un objet mutable.
    publication_id = publication_dir.name
    # On garde dans publication_path l’écriture de publication_dir / 'manifest.json' avec des / comme
    # séparateurs.
    publication_path = (publication_dir / "manifest.json").as_posix()
    # On garde dans publication le contenu du fichier JSON après passage par le lecteur contrôlé.
    publication = files.json(publication_path)
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        publication["publication_id"] == publication_id
        # On exige aussi que le chemin de travail dans publication['reference'] correspond au chemin
        # du tableau Excel regroupé.
        and publication["reference"]["path"] == reference_path,
        "Publication Excel incompatible avec le manifeste du pilote.",
    )
    # On garde dans expected_hash la valeur renvoyée par hash_value.
    expected_hash = hash_value(manifest["reference_sha256"], "reference_sha256")
    # On exige ici que expected_hash correspond à publication['reference']['sha256']. Si ce n’est pas
    # le cas, le message associé bloque la suite.
    require(
        expected_hash == publication["reference"]["sha256"],
        "Empreintes de reference incompatibles.",
    )
    # On garde dans reference_bytes le contenu lu depuis files selon les paramètres fournis.
    reference_bytes = files.read(reference_path, expected_hash)
    # On garde dans snapshot_path la valeur renvoyée par paths.relative.
    snapshot_path = paths.relative(manifest["reference_snapshot"])
    # On exige ici que snapshot_path correspond à 'data/03_normalized/pipeline_runs/' + execution_id +
    # '/tracking_reference…. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        snapshot_path
        == "data/03_normalized/pipeline_runs/"
        + execution_id
        + "/tracking_reference_snapshot.csv",
        "Chemin du snapshot incompatible avec le pilote.",
    )
    # On appelle files.read avec snapshot_path.
    files.read(snapshot_path, expected_hash)
    # On garde dans reference les lignes décodées par le lecteur CSV de ce module.
    reference = read_csv(
        reference_bytes,
        reference_path,
        {
            "Vineyard",
            "Acquisition_ID_normalise",
            "excel_reference_version_id",
            "source_sha256",
            "source_file",
            "ingested_at",
            "Périmètre",
            "Statut_pipeline",
        },
    )
    # On exige ici que len(reference) correspond aux lignes dans publication['reference']. Si ce
    # n’est pas le cas, le message associé bloque la suite.
    require(
        len(reference) == publication["reference"]["rows"],
        "Comptage de reference Excel incoherent.",
    )
    # On exige ici que date_value(publication['published_at'], 'excel.published_at') ne dépasse pas
    # start. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        date_value(publication["published_at"], "excel.published_at") <= start,
        "Publication Excel posterieure au controle.",
    )
    # On prépare reports comme liste vide ; on la remplira au fil des opérations suivantes.
    reports = []
    # On prépare artifacts comme liste vide ; on la remplira au fil des opérations suivantes.
    artifacts = []
    # On prépare compatibility comme liste vide ; on la remplira au fil des opérations suivantes.
    compatibility = []
    # On gardera ici les associations déjà rencontrées afin de distinguer un doublon d’une nouvelle
    # association.
    seen = set()
    # On exige ici que les domaines sélectionnés dans manifest est du type list et le test
    # manifest['vineyards'] est satisfait. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        isinstance(manifest["vineyards"], list) and manifest["vineyards"],
        "Aucun vignoble dans le pilote.",
    )
    # On parcourt les domaines sélectionnés dans manifest ; item désigne l’élément courant à chaque
    # passage dans la boucle.
    for item in manifest["vineyards"]:
        # On distribue ces valeurs entre name, key, dans l’ordre de l’affectation. Chaque nom reçoit
        # son propre élément.
        name, key = item["vineyard"], item["vineyard"].casefold()
        # On exige ici que la clé de l’élément ne figure pas dans seen et la clé de l’élément
        # appartient à publication['versions']. Si ce n’est pas le cas, le message associé bloque la
        # suite.
        require(
            key not in seen and key in publication["versions"],
            "Vignoble duplique ou absent de la publication : " + name,
        )
        # On ajoute key à seen ; comme il s’agit d’un ensemble, une valeur déjà présente n’est pas
        # comptée deux fois.
        seen.add(key)
        # On exige ici que l’état du traitement dans item correspond au texte 'success' et
        # item['extraction_returncode'] correspond à 0 et item['reconciliation_returncode'] correspond
        # à 0. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            item["status"] == "success"
            # On exige aussi que item['extraction_returncode'] correspond à 0.
            and item["extraction_returncode"] == 0
            # On exige aussi que item['reconciliation_returncode'] correspond à 0.
            and item["reconciliation_returncode"] == 0,
            "Etape non reussie : " + name,
        )
        # On sélectionne dans publication['versions'] les éléments désignés par key ; entry recevra
        # cette sélection.
        entry = publication["versions"][key]
        # On exige ici que entry['vineyard'].casefold() correspond à la clé de l’élément. Si ce n’est
        # pas le cas, le message associé bloque la suite.
        require(
            entry["vineyard"].casefold() == key, "Version Excel incoherente : " + name
        )
        # On garde dans vineyard_start la date validée et convertie selon le format du chargeur.
        vineyard_start = date_value(item["started_at"], name + ".started_at")
        # On garde dans vineyard_finish la date validée et convertie selon le format du chargeur.
        vineyard_finish = date_value(item["finished_at"], name + ".finished_at")
        # On garde dans checked la date validée et convertie selon le format du chargeur.
        checked = date_value(item["observations"]["checked_at"], name + ".checked_at")
        # On exige ici que le test start <= vineyard_start <= checked <= vineyard_finish <= finish est
        # satisfait. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            start <= vineyard_start <= checked <= vineyard_finish <= finish,
            "Dates d observation incoherentes : " + name,
        )
        # On construit scoped_reference comme une liste à partir de row, pour chaque row de reference
        # en ne gardant que les éléments qui passent le filtre.
        scoped_reference = [
            row
            for row in reference
            if row["Vineyard"].casefold() == key
            # On exige aussi que '_' + str(year) + '-' appartient à l’identifiant normalisé de
            # l’acquisition dans row.
            and ("_" + str(year) + "-") in row["Acquisition_ID_normalise"]
        ]
        # On exige ici que scoped_reference est évalué comme vrai. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(scoped_reference, "Perimetre Excel vide : " + name)
        # On crée le dictionnaire vide by_acquisition pour y ranger ensuite les éléments par clé.
        by_acquisition = {}
        # On parcourt scoped_reference ; row désigne l’élément courant à chaque passage dans la boucle.
        for row in scoped_reference:
            # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le
            # cas, le message associé bloque la suite.
            require(
                row["excel_reference_version_id"] == entry["version_id"]
                # On exige aussi que l’empreinte du fichier source dans row correspond à l’empreinte du
                # fichier source dans entry.
                and row["source_sha256"] == entry["source_sha256"]
                # On exige aussi que row['source_file'] correspond au nom du fichier source dans
                # entry.
                and row["source_file"] == entry["source_filename"]
                # On exige aussi que la date d’ingestion dans row correspond à la date d’ingestion dans
                # entry.
                and row["ingested_at"] == entry["ingested_at"],
                "Provenance Excel incoherente : " + name,
            )
            # On ajoute row à la fin de by_acquisition.setdefault(row['Acquisition_ID_normalise'], [])
            # ; les éléments précédents restent conservés.
            by_acquisition.setdefault(row["Acquisition_ID_normalise"], []).append(row)
        # On récupère item['directory_name'] et on le garde dans directory pour la suite.
        directory = item["directory_name"]
        # On exige ici que directory est du type str et le contrôle re.fullmatch('v[0-9]+', directory)
        # est positif. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            isinstance(directory, str) and re.fullmatch(r"v[0-9]+", directory),
            "Sous-dossier de vignoble invalide.",
        )
        # On distribue ces valeurs entre nas, results, dans l’ordre de l’affectation. Chaque nom
        # reçoit son propre élément.
        nas, results = {}, {}
        # On parcourt [('nas_observation', nas, item['evidence_outputs'], item['extraction_run_… ;
        # (stage, target, outputs, run_id, folder) désigne l’élément courant à chaque passage dans la
        # boucle.
        for stage, target, outputs, run_id, folder in [
            (
                "nas_observation",
                nas,
                item["evidence_outputs"],
                item["extraction_run_id"],
                "nas_live_evidence",
            ),
            (
                "reconciliation",
                results,
                item["reconciliation_outputs"],
                item["reconciliation_run_id"],
                "reconciliations/nas_live",
            ),
        ]:
            # On exige ici que run_id est du type str et le contrôle re.fullmatch('[A-Za-z0-9_-]+',
            # run_id) est positif. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", run_id),
                "Identifiant de sortie invalide.",
            )
            # On assemble ces deux éléments pour construire parent.
            parent = (
                "data/03_normalized/"
                + folder
                + "/runs/"
                + execution_id
                + "/"
                + directory
            )
            # On parcourt KINDS ; kind désigne l’élément courant à chaque passage dans la boucle.
            for kind in KINDS:
                # On choisit la valeur de output_key selon ce test : l’étape concernée correspond à le
                # texte 'nas_observation' et kind correspond au texte 'acquisitions'. Les deux
                # résultats possibles restent définis explicitement ici.
                output_key = (
                    "evidence"
                    if stage == "nas_observation" and kind == "acquisitions"
                    else kind
                )
                # On garde dans path la valeur renvoyée par paths.relative.
                path = paths.relative(outputs[output_key])
                # On exige ici que PurePosixPath(path).parent.as_posix() correspond à parent et le
                # chemin de travail se termine par '_' + run_id + '.csv'. Si ce n’est pas le cas, le
                # message associé bloque la suite.
                require(
                    PurePosixPath(path).parent.as_posix() == parent
                    # On exige aussi que le chemin de travail se termine par '_' + run_id + '.csv'.
                    and path.endswith("_" + run_id + ".csv"),
                    "Fichier hors du run attendu : " + path,
                )
                # On réunit ces masques avec | pour construire needed ; les parenthèses gardent les
                # comparaisons regroupées.
                needed = BASE_COLUMNS[kind] | (
                    RESULT_COLUMNS[kind] if stage == "reconciliation" else set()
                )
                # On garde dans data le contenu lu depuis files selon les paramètres fournis.
                data = files.read(path)
                # On garde dans rows la valeur renvoyée par read_result_csv.
                rows = read_result_csv(
                    data,
                    path,
                    needed,
                    kind=kind,
                    declared_associations=item["observations"]["volumes"][
                        "associations"
                    ],
                    compatibility=compatibility,
                )
                # On gardes lignes sous le nom target[kind] ; cette affectation ne copie pas à elle
                # seule un objet mutable.
                target[kind] = rows
                # On appelle keyed avec rows.
                keyed(rows, kind, path)
                # On appelle validate_json_cells avec rows.
                validate_json_cells(rows, path)
                # On parcourt les lignes ; row désigne l’élément courant à chaque passage dans la
                # boucle.
                for row in rows:
                    # On exige ici que row['Vineyard'].casefold() correspond à la clé de l’élément et
                    # integer(row['project_year'], path) correspond à la saison. Si ce n’est pas le
                    # cas, le message associé bloque la suite.
                    require(
                        row["Vineyard"].casefold() == key
                        # On exige aussi que integer(row['project_year'], path) correspond à la saison.
                        and integer(row["project_year"], path) == year,
                        "Vignoble ou annee incompatible : " + path,
                    )
                    # On exige ici que date_value(row['checked_at'], path) correspond à checked. Si ce
                    # n’est pas le cas, le message associé bloque la suite.
                    require(
                        date_value(row["checked_at"], path) == checked,
                        "Date NAS incompatible : " + path,
                    )
                    # On appelle boolean avec row['vitiparcel_created'].
                    boolean(row["vitiparcel_created"], path + ".vitiparcel_created")
                    # On vérifie ce cas avant la suite : le texte 'passage_outputs_verifiable'
                    # appartient à la ligne en cours.
                    if "passage_outputs_verifiable" in row:
                        # On appelle boolean avec row['passage_outputs_verifiable'].
                        boolean(
                            row["passage_outputs_verifiable"],
                            path + ".passage_outputs_verifiable",
                        )
                # On ajoute {'vineyard': name, 'stage': stage, 'kind': kind, 'path': path, 'sha256':
                # sha256(data), 's… à la fin de artifacts ; les éléments précédents restent conservés.
                artifacts.append(
                    {
                        # On renseigne le domaine concerné sous la clé 'vineyard'.
                        "vineyard": name,
                        # On renseigne l’étape concernée sous la clé 'stage'.
                        "stage": stage,
                        # On associe la clé 'kind' à cette valeur dans cet objet.
                        "kind": kind,
                        # On renseigne le chemin de travail sous la clé 'path'.
                        "path": path,
                        # On conserve l’empreinte attendue pour retrouver la même version du contenu.
                        "sha256": sha256(data),
                        # On associe la clé 'size' à cette valeur dans cet objet.
                        "size": len(data),
                        # On renseigne les lignes sous la clé 'rows'.
                        "rows": len(rows),
                    }
                )
        # On exige ici que le test nas['acquisitions'] est satisfait. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(nas["acquisitions"], "Aucune acquisition observee : " + name)
        # On exige ici que set((row['acquisition_id_normalise'] for row in nas['acquisitions']))
        # correspond à set(by_acquisition). Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            set(row["acquisition_id_normalise"] for row in nas["acquisitions"])
            == set(by_acquisition),
            "Perimetre NAS different de la reference Excel : " + name,
        )
        # On appelle validate_relations avec nas.
        validate_relations(nas)
        # On récupère les constats à présenter dans item et on le garde dans observed pour la suite.
        observed = item["observations"]
        # On parcourt KINDS ; kind désigne l’élément courant à chaque passage dans la boucle.
        for kind in KINDS:
            # On choisit la valeur de output_key selon ce test : kind correspond au texte
            # 'acquisitions'. Les deux résultats possibles restent définis explicitement ici.
            output_key = "evidence" if kind == "acquisitions" else kind
            # On exige ici que type(observed['volumes'][output_key]) est exactement int et
            # observed['volumes'][output_key] correspond à len(nas[kind]). Si ce n’est pas le cas, le
            # message associé bloque la suite.
            require(
                type(observed["volumes"][output_key]) is int
                # On exige aussi que observed['volumes'][output_key] correspond à len(nas[kind]).
                and observed["volumes"][output_key] == len(nas[kind]),
                "Comptage NAS incompatible avec le manifeste : " + name + " / " + kind,
            )
            # On garde dans error_count la somme des valeurs de (any((value.strip() for column, value
            # in row.items() if column.endswith('….
            error_count = sum(
                any(
                    value.strip()
                    for column, value in row.items()
                    if column.endswith("_error")
                )
                for row in nas[kind]
            )
            # On exige ici que observed['rows_with_observation_errors'][output_key] correspond à
            # error_count. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                observed["rows_with_observation_errors"][output_key] == error_count,
                "Comptage d erreurs incompatible : " + name + " / " + kind,
            )
            # On garde dans source_map les lignes indexées par leur clé après vérification de
            # l’unicité.
            source_map = keyed(nas[kind], kind, "NAS " + kind)
            # On garde dans result_map les lignes indexées par leur clé après vérification de
            # l’unicité.
            result_map = keyed(results[kind], kind, "rapprochement " + kind)
            # On exige ici que source_map.keys() correspond à result_map.keys(). Si ce n’est pas le
            # cas, le message associé bloque la suite.
            require(
                source_map.keys() == result_map.keys(),
                "Cles NAS/rapprochement differentes : " + name + " / " + kind,
            )
            # On parcourt les couples (identity, source_row) de source_map : on garde ensemble la
            # clé et sa valeur au lieu des traiter dans deux listes séparées.
            for identity, source_row in source_map.items():
                # On sélectionne dans result_map les éléments désignés par identity ; result_row
                # recevra cette sélection.
                result_row = result_map[identity]
                # On parcourt les couples (column, value) de source_row : on garde ensemble la clé
                # et sa valeur au lieu des traiter dans deux listes séparées.
                for column, value in source_row.items():
                    # On choisit la valeur de result_column selon ce test : kind correspond au texte
                    # 'acquisitions' et column correspond au texte 'excel_pipeline_status' et le
                    # texte 'extractor_excel_pipeline_status' appartient à result_row. Les deux
                    # résultats possibles restent définis explicitement ici.
                    result_column = (
                        "extractor_excel_pipeline_status"
                        if kind == "acquisitions"
                        # On exige aussi que column correspond au texte 'excel_pipeline_status'.
                        and column == "excel_pipeline_status"
                        # On exige aussi que le texte 'extractor_excel_pipeline_status' appartient à
                        # result_row.
                        and "extractor_excel_pipeline_status" in result_row
                        else column
                    )
                    # On exige ici que result_column appartient à result_row et
                    # result_row[result_column] correspond à la valeur reçue. Si ce n’est pas le cas,
                    # le message associé bloque la suite.
                    require(
                        result_column in result_row
                        # On exige aussi que result_row[result_column] correspond à la valeur reçue.
                        and result_row[result_column] == value,
                        "Information source modifiee : "
                        + name
                        + " / "
                        + kind
                        + " / "
                        + column,
                    )
        # On construit reconciled_dates comme un ensemble sans doublons à partir de
        # date_value(row['reconciled_at'], name + '.reconciled_at'), pour chaque row de
        # results['acquisitions'].
        reconciled_dates = {
            date_value(row["reconciled_at"], name + ".reconciled_at")
            for row in results["acquisitions"]
        }
        # On exige ici que len(reconciled_dates) correspond à 1. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(
            len(reconciled_dates) == 1,
            "Dates de calcul multiples dans un meme bilan : " + name,
        )
        # On garde dans reconciled le prochain élément de iter(reconciled_dates).
        reconciled = next(iter(reconciled_dates))
        # On exige ici que le test checked <= reconciled <= vineyard_finish est satisfait. Si ce n’est
        # pas le cas, le message associé bloque la suite.
        require(
            checked <= reconciled <= vineyard_finish,
            "Date de rapprochement incoherente : " + name,
        )
        # On parcourt ('acquisitions', 'associations') ; kind désigne l’élément courant à chaque
        # passage dans la boucle.
        for kind in ("acquisitions", "associations"):
            # On parcourt results[kind] ; row désigne l’élément courant à chaque passage dans la
            # boucle.
            for row in results[kind]:
                # On récupère l’identifiant normalisé de l’acquisition dans row et on le garde dans
                # acquisition pour la suite.
                acquisition = row["acquisition_id_normalise"]
                # On exige ici que row['excel_acquisition_id_normalise'] correspond à acquisition et
                # row['excel_vineyard'].casefold() correspond à la clé de l’élément. Si ce n’est pas le
                # cas, le message associé bloque la suite.
                require(
                    row["excel_acquisition_id_normalise"] == acquisition
                    # On exige aussi que row['excel_vineyard'].casefold() correspond à la clé de
                    # l’élément.
                    and row["excel_vineyard"].casefold() == key,
                    "Acquisition Excel incompatible : " + acquisition,
                )
                # On exige ici que row['excel_ingested_at'] correspond à la date d’ingestion dans entry
                # et row['excel_source_files'] correspond au nom du fichier source dans entry. Si ce
                # n’est pas le cas, le message associé bloque la suite.
                require(
                    row["excel_ingested_at"] == entry["ingested_at"]
                    # On exige aussi que row['excel_source_files'] correspond au nom du fichier
                    # source dans entry.
                    and row["excel_source_files"] == entry["source_filename"],
                    "Source/date Excel incompatible : " + acquisition,
                )
                # On sélectionne dans by_acquisition les éléments désignés par acquisition ; excel_rows
                # recevra cette sélection.
                excel_rows = by_acquisition[acquisition]
                # Ne PAS recalculer la classification multi-lignes. Si le contexte
                # est uniforme, sa valeur doit correspondre. S'il differe entre
                # lignes, conserver le contexte agrege existant et le signaler.
                for column, excel_column in [
                    ("excel_perimeter", "Périmètre"),
                    ("excel_pipeline_status", "Statut_pipeline"),
                ]:
                    # On construit values comme un ensemble sans doublons à partir de
                    # excel[excel_column], pour chaque excel de excel_rows.
                    values = {excel[excel_column] for excel in excel_rows}
                    # On vérifie ce cas avant la suite : len(values) correspond à 1.
                    if len(values) == 1:
                        # On exige ici que row[column] correspond à next(iter(values)). Si ce n’est pas
                        # le cas, le message associé bloque la suite.
                        require(
                            row[column] == next(iter(values)),
                            "Contexte Excel incompatible : "
                            + acquisition
                            + " / "
                            + column,
                        )
        # On garde dans candidates la somme des valeurs de
        # (boolean(row['acquisition_new_anomaly_candidate'], name) for row in resul….
        candidates = sum(
            boolean(row["acquisition_new_anomaly_candidate"], name)
            for row in results["acquisitions"]
        )
        # On garde dans not_verifiable la somme des valeurs de (not
        # boolean(row['passage_outputs_verifiable'], name) for row in nas['acq….
        not_verifiable = sum(
            not boolean(row["passage_outputs_verifiable"], name)
            for row in nas["acquisitions"]
        )
        # On garde dans passage_candidates la somme des valeurs de
        # (boolean(row['passage_review_candidate'], name) for row in results['passa….
        passage_candidates = sum(
            boolean(row["passage_review_candidate"], name)
            for row in results["passages"]
        )
        # On garde dans positive_passages la somme des valeurs de
        # (boolean(row['vitiparcel_ready_for_delivery'], name) and boolean(row['vit….
        positive_passages = sum(
            boolean(row["vitiparcel_ready_for_delivery"], name)
            # On exige aussi que le contrôle boolean(row['vitiparcel_ready_verifiable'], name) est
            # positif.
            and boolean(row["vitiparcel_ready_verifiable"], name)
            for row in results["passages"]
        )
        # On garde dans mixed_contexts la somme des valeurs de (len({row['Périmètre'] for row in rows})
        # > 1 or len({row['Statut_pipeline….
        mixed_contexts = sum(
            len({row["Périmètre"] for row in rows}) > 1
            # Ce cas est aussi retenu si len({row['Statut_pipeline'] for row in rows}) est supérieur à
            # 1.
            or len({row["Statut_pipeline"] for row in rows}) > 1
            for rows in by_acquisition.values()
        )
        # On prépare acquisition_details comme liste vide ; on la remplira au fil des opérations
        # suivantes.
        acquisition_details = []
        # On parcourt les acquisitions dans results ; row désigne l’élément courant à chaque passage
        # dans la boucle.
        for row in results["acquisitions"]:
            # On ajoute {'id': row['acquisition_id_normalise'], 'review':
            # boolean(row['acquisition_new_anomaly_ca… à la fin de acquisition_details ; les éléments
            # précédents restent conservés.
            acquisition_details.append(
                {
                    # On renseigne l’identifiant du composant sous la clé 'id'.
                    "id": row["acquisition_id_normalise"],
                    # On renseigne la demande de vérification sous la clé 'review'.
                    "review": boolean(row["acquisition_new_anomaly_candidate"], name),
                    # On renseigne l’état de vérifiabilité sous la clé 'verifiable'.
                    "verifiable": boolean(row["passage_outputs_verifiable"], name),
                    # On associe la clé 'passage_link_count' à cette valeur dans cet objet.
                    "passage_link_count": integer(row["passage_link_count"], name),
                    # On associe la clé 'processing_category' à cette valeur dans cet objet.
                    "processing_category": row["processing_business_category"],
                    # On associe la clé 'relationship_category' à cette valeur dans cet objet.
                    "relationship_category": row.get(
                        "relationship_business_category", ""
                    ),
                    # On renseigne le périmètre du suivi Excel sous la clé 'excel_perimeter'.
                    "excel_perimeter": row["excel_perimeter"],
                    # On renseigne le statut du suivi Excel sous la clé 'excel_pipeline_status'.
                    "excel_pipeline_status": row["excel_pipeline_status"],
                    # On renseigne le détail des erreurs techniques sous la clé 'technical_errors'.
                    "technical_errors": row.get("technical_errors", ""),
                    # On associe la clé 'native_review' à cette valeur dans cet objet.
                    "native_review": row.get("raw_evidence_review_required", ""),
                }
            )
        # On prépare passage_details comme liste vide ; on la remplira au fil des opérations suivantes.
        passage_details = []
        # On parcourt les passages dans results ; row désigne l’élément courant à chaque passage dans
        # la boucle.
        for row in results["passages"]:
            # On ajoute {'name': row['passage_name'], 'parcel': row['parcel_name'], 'acquisitions':
            # row['acquisit… à la fin de passage_details ; les éléments précédents restent conservés.
            passage_details.append(
                {
                    # On renseigne le nom en cours sous la clé 'name'.
                    "name": row["passage_name"],
                    # On associe la clé 'parcel' à cette valeur dans cet objet.
                    "parcel": row["parcel_name"],
                    # On renseigne les acquisitions sous la clé 'acquisitions'.
                    "acquisitions": row["acquisitions_controlled_count"],
                    # On renseigne l’état de vérifiabilité sous la clé 'verifiable'.
                    "verifiable": boolean(row["vitiparcel_ready_verifiable"], name),
                    # On associe la clé 'ready' à cette valeur dans cet objet.
                    "ready": boolean(row["vitiparcel_ready_for_delivery"], name),
                    # On renseigne la demande de vérification sous la clé 'review'.
                    "review": boolean(row["passage_review_candidate"], name),
                    # On associe la clé 'category' à cette valeur dans cet objet.
                    "category": row["passage_business_category"],
                    # On associe la clé 'stocks_present' à cette valeur dans cet objet.
                    "stocks_present": boolean(row["stocks_json_exists"], name),
                    # On associe la clé 'nonhealthy' à cette valeur dans cet objet.
                    "nonhealthy": row["non_healthy_status_count"],
                }
            )
        # On ajoute {'vineyard': name, 'excel_version_id': entry['version_id'], 'checked_at':
        # item['observati… à la fin de reports ; les éléments précédents restent conservés.
        reports.append(
            {
                # On renseigne le domaine concerné sous la clé 'vineyard'.
                "vineyard": name,
                # On associe la clé 'excel_version_id' à cette valeur dans cet objet.
                "excel_version_id": entry["version_id"],
                # On renseigne la date du contrôle sous la clé 'checked_at'.
                "checked_at": item["observations"]["checked_at"],
                # On renseigne la date du rapprochement sous la clé 'reconciled_at'.
                "reconciled_at": reconciled.isoformat(),
                # On renseigne les acquisitions sous la clé 'acquisitions'.
                "acquisitions": len(nas["acquisitions"]),
                # On renseigne les associations entre acquisitions et passages sous la clé
                # 'associations'.
                "associations": len(nas["associations"]),
                # On renseigne les passages sous la clé 'passages'.
                "passages": len(nas["passages"]),
                # On associe la clé 'acquisition_candidates' à cette valeur dans cet objet.
                "acquisition_candidates": candidates,
                # On associe la clé 'not_verifiable' à cette valeur dans cet objet.
                "not_verifiable": not_verifiable,
                # On associe la clé 'non_verifiable_without_passage' à cette valeur dans cet objet.
                "non_verifiable_without_passage": sum(
                    not boolean(row["passage_outputs_verifiable"], name)
                    # On exige aussi que integer(row['passage_link_count'], name) correspond à 0.
                    and integer(row["passage_link_count"], name) == 0
                    for row in nas["acquisitions"]
                ),
                # On associe la clé 'non_verifiable_with_passage' à cette valeur dans cet objet.
                "non_verifiable_with_passage": sum(
                    not boolean(row["passage_outputs_verifiable"], name)
                    # On exige aussi que integer(row['passage_link_count'], name) est supérieur à 0.
                    and integer(row["passage_link_count"], name) > 0
                    for row in nas["acquisitions"]
                ),
                # On associe la clé 'excel_ingested_at' à cette valeur dans cet objet.
                "excel_ingested_at": entry["ingested_at"],
                # On associe la clé 'passage_candidates' à cette valeur dans cet objet.
                "passage_candidates": passage_candidates,
                # On associe la clé 'positive_passages' à cette valeur dans cet objet.
                "positive_passages": positive_passages,
                # On associe la clé 'mixed_excel_contexts' à cette valeur dans cet objet.
                "mixed_excel_contexts": mixed_contexts,
                # On associe la clé 'recorded_mapping_gaps' à cette valeur dans cet objet.
                "recorded_mapping_gaps": [
                    {
                        # On renseigne l’identifiant du composant sous la clé 'id'.
                        "id": row["acquisition_id_normalise"],
                        # On associe la clé 'parcel_mapping' à cette valeur dans cet objet.
                        "parcel_mapping": json_list(row["parcel_names_json"], name),
                        # On associe la clé 'outside_parcels' à cette valeur dans cet objet.
                        "outside_parcels": sorted(
                            {
                                link["parcel_name"]
                                for link in json_list(row["passage_links_json"], name)
                            }
                            - set(json_list(row["parcel_names_json"], name))
                        ),
                    }
                    for row in nas["acquisitions"]
                    if {
                        link["parcel_name"]
                        for link in json_list(row["passage_links_json"], name)
                    }
                    - set(json_list(row["parcel_names_json"], name))
                ],
                # On associe la clé 'acquisition_details' à cette valeur dans cet objet.
                "acquisition_details": sorted(
                    # On fournit la clé de l’élément via le paramètre key de cet appel.
                    acquisition_details, key=lambda row: row["id"]
                ),
                # On associe la clé 'passage_details' à cette valeur dans cet objet.
                "passage_details": sorted(
                    # On fournit la clé de l’élément via le paramètre key de cet appel.
                    passage_details, key=lambda row: (row["parcel"], row["name"])
                ),
                # On associe la clé 'association_details' à cette valeur dans cet objet.
                "association_details": [
                    {
                        # On associe la clé 'acquisition' à cette valeur dans cet objet.
                        "acquisition": row["acquisition_id_normalise"],
                        # On associe la clé 'parcel' à cette valeur dans cet objet.
                        "parcel": row["parcel_name"],
                        # On associe la clé 'passage' à cette valeur dans cet objet.
                        "passage": row["passage_name"],
                    }
                    for row in sorted(
                        nas["associations"],
                        # On fournit la clé de l’élément via le paramètre key de cet appel.
                        key=lambda row: (
                            row["acquisition_id_normalise"],
                            row["parcel_name"],
                            row["passage_name"],
                        ),
                    )
                ],
            }
        )
    # On appelle files.unchanged sans argument positionnel.
    files.unchanged()
    # On appelle no_ingestion sans argument positionnel.
    no_ingestion()
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On renseigne l’identifiant du traitement NAS sous la clé 'pipeline_execution_id'.
        "pipeline_execution_id": execution_id,
        # On renseigne l’identifiant du lot Excel sous la clé 'excel_publication_id'.
        "excel_publication_id": publication_id,
        # On renseigne l’empreinte du tableau Excel regroupé sous la clé 'reference_sha256'.
        "reference_sha256": expected_hash,
        # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
        "vineyards": reports,
        # On associe la clé 'artifacts' à cette valeur dans cet objet.
        "artifacts": artifacts,
        # On associe la clé 'files_verified' à cette valeur dans cet objet.
        "files_verified": len(files.cache),
        # On associe la clé 'empty_association_compatibility' à cette valeur dans cet objet.
        "empty_association_compatibility": compatibility,
        # On renseigne le nombre de lignes du tableau regroupé sous la clé 'reference_rows'.
        "reference_rows": len(reference),
        # On associe la clé 'common_files' à cette valeur dans cet objet.
        "common_files": [
            {
                # On associe la clé 'role' à cette valeur dans cet objet.
                "role": "Manifeste du pilote : journal de cette execution",
                # On renseigne le chemin de travail sous la clé 'path'.
                "path": manifest_relative,
                # On associe la clé 'type' à cette valeur dans cet objet.
                "type": "JSON",
            },
            {
                # On associe la clé 'role' à cette valeur dans cet objet.
                "role": "Manifeste de publication Excel : versions retenues",
                # On renseigne le chemin de travail sous la clé 'path'.
                "path": publication_path,
                # On associe la clé 'type' à cette valeur dans cet objet.
                "type": "JSON",
            },
            {
                # On associe la clé 'role' à cette valeur dans cet objet.
                "role": "Reference Excel publiee, avant selection du vignoble",
                # On renseigne le chemin de travail sous la clé 'path'.
                "path": reference_path,
                # On associe la clé 'type' à cette valeur dans cet objet.
                "type": "CSV",
            },
            {
                # On associe la clé 'role' à cette valeur dans cet objet.
                "role": "Copie figee de cette reference utilisee par le pilote",
                # On renseigne le chemin de travail sous la clé 'path'.
                "path": snapshot_path,
                # On associe la clé 'type' à cette valeur dans cet objet.
                "type": "CSV",
            },
        ],
    }


def render_report(report):
    """Noms, motifs enregistres et fichiers : affichage, sans reclassement metier."""
    # On multiplie ces valeurs pour construire separator.
    separator = "─" * 72
    # On affiche le texte '📋 CONTRÔLE LOCAL — PREUVES NAS ET RAPPROCHEMENT EXCEL' dans la sortie du
    # programme.
    print("📋 CONTRÔLE LOCAL — PREUVES NAS ET RAPPROCHEMENT EXCEL")
    # On affiche ce texte explicite dans la sortie du programme.
    print("Lecture des fichiers existants : aucun nouveau scan du NAS.")
    # On affiche 'Exécution du pilote : ' + report['pipeline_execution_id'] dans la sortie du
    # programme.
    print("Exécution du pilote : " + report["pipeline_execution_id"])
    # On affiche 'Publication Excel utilisée : ' + report['excel_publication_id'] dans la sortie du
    # programme.
    print("Publication Excel utilisée : " + report["excel_publication_id"])
    # On parcourt les domaines sélectionnés dans report ; item désigne l’élément courant à chaque
    # passage dans la boucle.
    for item in report["vineyards"]:
        # On affiche separator dans la sortie du programme.
        print(separator)
        # On affiche le domaine concerné dans item dans la sortie du programme.
        print(item["vineyard"])
        # On affiche 'Version Excel : ' + item['excel_version_id'] dans la sortie du programme.
        print("Version Excel : " + item["excel_version_id"])
        # On affiche 'Ingestion Excel : ' + item['excel_ingested_at'] dans la sortie du programme.
        print("Ingestion Excel : " + item["excel_ingested_at"])
        # On affiche 'Observation NAS : ' + item['checked_at'] dans la sortie du programme.
        print("Observation NAS : " + item["checked_at"])
        # On affiche 'Calcul du rapprochement : ' + item['reconciled_at'] dans la sortie du programme.
        print("Calcul du rapprochement : " + item["reconciled_at"])
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Les dates décrivent trois opérations différentes ; pas la date de livraison."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print()
        # On affiche le texte '1. PÉRIMÈTRE ET ASSOCIATIONS OBSERVÉES' dans la sortie du programme.
        print("1. PÉRIMÈTRE ET ASSOCIATIONS OBSERVÉES")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"   {item['acquisitions']} acquisitions contrôlées | {item['associations']} associations acquisition-parcelle-passage | {item['passages']} passages distincts"
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "   Une association indique à quelle parcelle et à quel passage une acquisition est rattachée."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "   Une acquisition peut avoir plusieurs associations ; un passage peut être partagé."
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print("   Associations observées (acquisition -> parcelle -> passage) :")
        # Cette branche traite le cas où la condition item['association_details'] n’est pas remplie.
        if not item["association_details"]:
            # On affiche le texte '     Aucune association identifiée.' dans la sortie du programme.
            print("     Aucune association identifiée.")
        # On parcourt item['association_details'] ; association désigne l’élément courant à chaque
        # passage dans la boucle.
        for association in item["association_details"]:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"     - {association['acquisition']} -> {association['parcel']} -> {association['passage']}"
            )
        # On affiche cette information de suivi dans la sortie du programme.
        print()
        # On affiche le texte '2. ACQUISITIONS À VÉRIFIER — LISTE ET MOTIFS ENREGISTRÉS' dans la sortie
        # du programme.
        print("2. ACQUISITIONS À VÉRIFIER — LISTE ET MOTIFS ENREGISTRÉS")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"   Acquisitions à vérifier : {item['acquisition_candidates']} / {item['acquisitions']}"
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "   Ces écarts sont à examiner ; leur cause n’est pas démontrée par ce compteur."
        )
        # On construit candidates comme une liste à partir de row, pour chaque row de
        # item['acquisition_details'] en ne gardant que les éléments qui passent le filtre.
        candidates = [row for row in item["acquisition_details"] if row["review"]]
        # Grouper les libelles existants evite de repeter 27 fois le meme contexte.
        # Deux motifs identiques ne prouvent pas une cause commune.
        groups = {}
        # On parcourt candidates ; row désigne l’élément courant à chaque passage dans la boucle.
        for row in candidates:
            # On rassemble dans key les 6 éléments explicitement indiqués, en conservant leur
            # structure.
            key = (
                row["processing_category"],
                row["relationship_category"],
                row["excel_perimeter"],
                row["excel_pipeline_status"],
                row["technical_errors"],
                row["native_review"],
            )
            # On ajoute row['id'] à la fin de groups.setdefault(key, []) ; les éléments précédents
            # restent conservés.
            groups.setdefault(key, []).append(row["id"])
        # On prévoit le cas où groups est évalué comme faux, par exemple une valeur vide selon son
        # type.
        if not groups:
            # On affiche ce texte explicite dans la sortie du programme.
            print("   Aucune acquisition signalée à vérifier dans le bilan enregistré.")
        # On parcourt groups.items() en gardant aussi sa position dans (index, (context, ids)) ; le
        # comptage commence à 1.
        for index, (context, ids) in enumerate(groups.items(), 1):
            # On répartit les éléments de context entre (processing, relationship, perimeter, status,
            # errors, native_rev…, dans l’ordre indiqué.
            processing, relationship, perimeter, status, errors, native_review = context
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"   Groupe {index} : {len(ids)} acquisition(s), mêmes libellés enregistrés"
            )
            # On affiche '     Traitement d’images : ' + processing dans la sortie du programme.
            print("     Traitement d’images : " + processing)
            # Cette branche traite le cas où relationship est évalué comme vrai.
            if relationship:
                # On affiche '     Rattachement parcelle/passage : ' + relationship dans la sortie du
                # programme.
                print("     Rattachement parcelle/passage : " + relationship)
            # On affiche f'     Contexte Excel : périmètre={perimeter} | statut={status}' dans la
            # sortie du programme.
            print(f"     Contexte Excel : périmètre={perimeter} | statut={status}")
            # On vérifie ce cas avant la suite : native_review correspond au texte 'True'.
            if native_review == "True":
                # On affiche ce texte explicite dans la sortie du programme.
                print("     Le bilan signale également une preuve native à vérifier.")
            # Cette branche traite le cas où les erreurs relevées est évalué comme vrai.
            if errors:
                # On affiche '     Erreurs techniques enregistrées : ' + errors dans la sortie du
                # programme.
                print("     Erreurs techniques enregistrées : " + errors)
            # On parcourt ids ; acquisition désigne l’élément courant à chaque passage dans la boucle.
            for acquisition in ids:
                # On affiche '       - ' + acquisition dans la sortie du programme.
                print("       - " + acquisition)
        # On affiche cette information de suivi dans la sortie du programme.
        print()
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"   Acquisitions dont les sorties de passage ne sont pas vérifiables : {item['not_verifiable']} / {item['acquisitions']}"
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"     - Sans passage associé identifié : {item['non_verifiable_without_passage']}"
        )
        # Cette branche traite le cas où le test item['non_verifiable_with_passage'] est satisfait.
        if item["non_verifiable_with_passage"]:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"     - Passage associé, mais sorties non vérifiables : {item['non_verifiable_with_passage']}"
            )
        # On construit nonverifiable comme une liste à partir de row, pour chaque row de
        # item['acquisition_details'] en ne gardant que les éléments qui passent le filtre.
        nonverifiable = [
            row for row in item["acquisition_details"] if not row["verifiable"]
        ]
        # Cette branche traite le cas où nonverifiable est évalué comme vrai.
        if nonverifiable:
            # On vérifie ce cas avant la suite : {row['id'] for row in nonverifiable} correspond à
            # {row['id'] for row in candidates}.
            if {row["id"] for row in nonverifiable} == {
                row["id"] for row in candidates
            }:
                # On affiche cette information de suivi dans la sortie du programme.
                print(
                    "   Identifiants concernés : exactement les mêmes que la liste à vérifier ci-dessus."
                )
            else:
                # On affiche le texte '   Identifiants concernés par la non-vérifiabilité :' dans la
                # sortie du programme.
                print("   Identifiants concernés par la non-vérifiabilité :")
                # On parcourt nonverifiable ; row désigne l’élément courant à chaque passage dans la
                # boucle.
                for row in nonverifiable:
                    # On choisit la valeur de reason selon ce test : row['passage_link_count']
                    # correspond à 0. Les deux résultats possibles restent définis explicitement ici.
                    reason = (
                        "aucun passage associé identifié"
                        if row["passage_link_count"] == 0
                        else "passage associé, mais sorties non vérifiables"
                    )
                    # On affiche f"     - {row['id']} | {reason}" dans la sortie du programme.
                    print(f"     - {row['id']} | {reason}")
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "   Non vérifiable = preuve impossible à attribuer/vérifier avec les informations disponibles."
            )
            # On affiche le texte '   Cela ne prouve PAS que VitiParcel est absent.' dans la sortie du
            # programme.
            print("   Cela ne prouve PAS que VitiParcel est absent.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "   Ces compteurs peuvent concerner les mêmes acquisitions : ne pas les additionner."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print()
        # On affiche ce texte explicite dans la sortie du programme.
        print("3. PASSAGES IDENTIFIÉS — NOMS ET ÉTAT DU CRITÈRE VITIPARCEL")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "   Critère technique : fichier de stocks présent ET au moins un statut non sain."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "   Critère satisfait ne signifie ni livré au client ni qualité définitivement validée."
        )
        # On rassemble dans buckets les 3 éléments explicitement indiqués, en conservant leur
        # structure.
        buckets = [
            (
                "Critère technique satisfait",
                [
                    row
                    for row in item["passage_details"]
                    if row["verifiable"] and row["ready"]
                ],
            ),
            (
                "Critère technique non démontré (évaluation possible)",
                [
                    row
                    for row in item["passage_details"]
                    if row["verifiable"] and not row["ready"]
                ],
            ),
            (
                "Critère non évaluable selon le bilan enregistré",
                [row for row in item["passage_details"] if not row["verifiable"]],
            ),
        ]
        # On parcourt buckets ; (title, rows) désigne l’élément courant à chaque passage dans la
        # boucle.
        for title, rows in buckets:
            # On affiche f"   {title} : {len(rows)} / {item['passages']}" dans la sortie du programme.
            print(f"   {title} : {len(rows)} / {item['passages']}")
            # On prévoit le cas où rows est évalué comme faux, par exemple une valeur vide selon son
            # type.
            if not rows:
                # On affiche le texte '     Aucun passage identifié dans cette catégorie.' dans la
                # sortie du programme.
                print("     Aucun passage identifié dans cette catégorie.")
            # On parcourt les lignes ; row désigne l’élément courant à chaque passage dans la boucle.
            for row in rows:
                # On affiche cette information de suivi dans la sortie du programme.
                print(
                    f"     - {row['name']} | parcelle={row['parcel']} | acquisitions associées={row['acquisitions']}"
                )
                # On affiche cette information de suivi dans la sortie du programme.
                print(
                    f"       Stocks présents : {'oui' if row['stocks_present'] else 'non'} | entrées de statut non sain : {row['nonhealthy']}"
                )
                # On affiche '       Catégorie enregistrée : ' + row['category'] dans la sortie du
                # programme.
                print("       Catégorie enregistrée : " + row["category"])
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"   Passages à vérifier selon le bilan enregistré : {item['passage_candidates']} / {item['passages']}"
        )
        # On construit passage_candidates comme une liste à partir de row, pour chaque row de
        # item['passage_details'] en ne gardant que les éléments qui passent le filtre.
        passage_candidates = [row for row in item["passage_details"] if row["review"]]
        # On prévoit le cas où passage_candidates est évalué comme faux, par exemple une valeur vide
        # selon son type.
        if not passage_candidates:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"   Ici, aucun des {item['passages']} passages identifiés n’est signalé à vérifier."
            )
        # On parcourt passage_candidates ; row désigne l’élément courant à chaque passage dans la
        # boucle.
        for row in passage_candidates:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"     - {row['name']} | parcelle={row['parcel']} | motif={row['category']}"
            )
        # On affiche le texte '   Ce compteur ne porte QUE sur les passages identifiés.' dans la sortie
        # du programme.
        print("   Ce compteur ne porte QUE sur les passages identifiés.")
        # Cette branche traite le cas où le test item['not_verifiable'] est satisfait.
        if item["not_verifiable"]:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "   Il ne résout pas les acquisitions dont les sorties restent non vérifiables."
            )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "   Les stocks se comptent par passage distinct, pas en sommant leurs associations."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print()
        # Cette branche traite le cas où le test item['mixed_excel_contexts'] est satisfait.
        if item["mixed_excel_contexts"]:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"   Contexte Excel : {item['mixed_excel_contexts']} acquisitions ont plusieurs périmètres/statuts déclarés."
            )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "   Leur contexte agrégé est conservé ; aucun nouveau classement n’est appliqué."
            )
        else:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "   Contexte Excel : aucun mélange de périmètre/statut entre lignes d’une même acquisition."
            )
        # Cette branche traite le cas où le champ 'recorded_mapping_gaps' de item est évalué comme
        # vrai.
        if item.get("recorded_mapping_gaps"):
            # On affiche le texte '   Écarts entre mappings explicitement enregistrés :' dans la sortie
            # du programme.
            print("   Écarts entre mappings explicitement enregistrés :")
            # On parcourt item['recorded_mapping_gaps'] ; gap désigne l’élément courant à chaque
            # passage dans la boucle.
            for gap in item["recorded_mapping_gaps"]:
                # On affiche '     - ' + gap['id'] dans la sortie du programme.
                print("     - " + gap["id"])
                # On affiche '       Mapping parcelle : ' + ', '.join(gap['parcel_mapping']) dans la
                # sortie du programme.
                print("       Mapping parcelle : " + ", ".join(gap["parcel_mapping"]))
                # On affiche cette information de suivi dans la sortie du programme.
                print(
                    "       Parcelle(s) des liens de passage absente(s) de ce mapping : "
                    + ", ".join(gap["outside_parcels"])
                )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "   Ces écarts sont conservés, pas corrigés ni déclarés résolus ; les flags False sources sont contrôlés."
            )
    # On affiche separator dans la sortie du programme.
    print(separator)
    # On affiche le texte '4. FICHIERS LUS — RÔLES, NOMS ET EMPLACEMENTS' dans la sortie du programme.
    print("4. FICHIERS LUS — RÔLES, NOMS ET EMPLACEMENTS")
    # On affiche ce texte explicite dans la sortie du programme.
    print("   Chemins ci-dessous : relatifs à la racine de ton projet.")
    # On regroupe dans role_labels ces champs nommés ; on pourra les retrouver par leur clé plutôt que
    # par leur position.
    role_labels = {
        # On renseigne les acquisitions sous la clé 'acquisitions'.
        "acquisitions": "Par acquisition",
        # On renseigne les associations entre acquisitions et passages sous la clé 'associations'.
        "associations": "Liens acquisition-parcelle-passage",
        # On renseigne les passages sous la clé 'passages'.
        "passages": "Par passage distinct",
    }
    # On parcourt [('nas_observation', 'PREUVES NAS : ce qui a été observé'), ('reconciliat… ; (stage,
    # title) désigne l’élément courant à chaque passage dans la boucle.
    for stage, title in [
        ("nas_observation", "PREUVES NAS : ce qui a été observé"),
        (
            "reconciliation",
            "RAPPROCHEMENT : contexte Excel et conclusions enregistrées",
        ),
    ]:
        # On construit stage_files comme une liste à partir de file, pour chaque file de
        # report['artifacts'] en ne gardant que les éléments qui passent le filtre.
        stage_files = [file for file in report["artifacts"] if file["stage"] == stage]
        # On affiche f'   {title} — {len(stage_files)} CSV' dans la sortie du programme.
        print(f"   {title} — {len(stage_files)} CSV")
        # On parcourt stage_files ; file désigne l’élément courant à chaque passage dans la boucle.
        for file in stage_files:
            # On garde dans path une représentation de chemin avec des /, sans accès au disque.
            path = PurePosixPath(file["path"])
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"     {file['vineyard']} | {role_labels[file['kind']]} | {file['rows']} lignes"
            )
            # On affiche '       Fichier : ' + path.name dans la sortie du programme.
            print("       Fichier : " + path.name)
            # On affiche '       Dossier : ' + path.parent.as_posix() dans la sortie du programme.
            print("       Dossier : " + path.parent.as_posix())
    # On affiche ce texte explicite dans la sortie du programme.
    print("   PROVENANCE COMMUNE : 2 manifestes JSON et 2 références Excel CSV")
    # On parcourt report['common_files'] ; file désigne l’élément courant à chaque passage dans la
    # boucle.
    for file in report["common_files"]:
        # On manipule les composants d’un chemin écrit avec des /, sans consulter le système de
        # fichiers à ce stade.
        path = PurePosixPath(file["path"])
        # On affiche '     ' + file['role'] dans la sortie du programme.
        print("     " + file["role"])
        # On affiche '       Fichier : ' + path.name dans la sortie du programme.
        print("       Fichier : " + path.name)
        # On affiche '       Dossier : ' + path.parent.as_posix() dans la sortie du programme.
        print("       Dossier : " + path.parent.as_posix())
        # On vérifie ce cas avant la suite : file['type'] correspond au texte 'CSV'.
        if file["type"] == "CSV":
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"       {report['reference_rows']} lignes dans la référence globale ; le contrôle sélectionne les vignobles du run."
            )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        f"   TOTAL : {report['files_verified']} fichiers locaux lus = {len(report['artifacts'])} CSV de preuves/rapprochement + 2 CSV de référence Excel + 2 manifestes JSON."
    )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "   Identifiants, relations, dates et informations sources : contrôles réussis."
    )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "   Empreintes des CSV calculées lors de ce contrôle ; intégrité depuis leur création non certifiée."
    )
    # Cette branche traite le cas où le champ 'empty_association_compatibility' du bilan est évalué
    # comme vrai.
    if report.get("empty_association_compatibility"):
        # On affiche le texte '   Compatibilité d’anciens CSV d’associations vides :' dans la sortie du
        # programme.
        print("   Compatibilité d’anciens CSV d’associations vides :")
        # On parcourt report['empty_association_compatibility'] ; path désigne l’élément courant à
        # chaque passage dans la boucle.
        for path in report["empty_association_compatibility"]:
            # On affiche '     - ' + path dans la sortie du programme.
            print("     - " + path)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "   Colonne passage_outputs_verifiable omise : tolérée UNIQUEMENT sans ligne et avec volume nul déclaré."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "   Liens des acquisitions et résultats rapprochés contrôlés ; aucun False, aucune relation ni colonne ajoutés."
        )
    # On affiche cette information de suivi dans la sortie du programme.
    print()
    # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un appel
    # depuis un autre outil.
    print("✅ RESULTAT : OK — fichiers cohérents pour préparer le chargement.")
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "Ce succès est technique : ce n’est pas une validation globale des livrables."
    )
    # On affiche ce texte explicite dans la sortie du programme.
    print("🔒 PostgreSQL : aucune connexion, aucune ecriture. NAS : aucun acces.")
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "Archives et registre local : aucune modification. Classifications : aucun recalcul."
    )


def main(argv=None):
    # On parcourt (sys.stdout, sys.stderr) ; stream désigne l’élément courant à chaque passage dans la
    # boucle.
    for stream in (sys.stdout, sys.stderr):
        # Cette branche traite le cas où le contrôle hasattr(stream, 'reconfigure') est positif.
        if hasattr(stream, "reconfigure"):
            # On appelle stream.reconfigure sans argument positionnel.
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(
        description="Controle local NAS/rapprochement ; aucun acces NAS/PostgreSQL."
    )
    # Option --manifest : Chemin relatif du manifeste dans data/. Sa déclaration ne déclenche pas
    # l’action.
    parser.add_argument(
        "--manifest", required=True, help="Chemin relatif du manifeste dans data/."
    )
    # Option --check-only : Seul mode disponible a ce premier palier ; aucun chargement. Sa
    # déclaration ne déclenche pas l’action.
    parser.add_argument(
        "--check-only",
        action="store_true",
        required=True,
        help="Seul mode disponible a ce premier palier ; aucun chargement.",
    )
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On récupère les options du contrôle des sorties NAS locales ; le contenu doit encore être
    # validé avant toute utilisation.
    args = parser.parse_args(argv)
    # On tente ce bloc et on traite séparément les erreurs prévues : (ValidationError, OSError,
    # KeyError, TypeError, AttributeError, ValueError).
    try:
        # On vérifie les sorties du parcours NAS et leur cohérence avant de considérer le résultat
        # comme chargeable.
        report = check_pipeline(args.project_root, args.manifest.replace("\\", "/"))
    except (
        ValidationError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        ValueError,
    ) as exc:
        # On affiche 'CONTROLE BLOQUE : ' + str(exc) dans la sortie du programme.
        print("CONTROLE BLOQUE : " + str(exc), file=sys.stderr)
        # On affiche ce texte explicite dans la sortie du programme.
        print(
            "Aucune ecriture, aucune connexion PostgreSQL, aucun acces NAS.",
            file=sys.stderr,
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    # On appelle render_report avec report.
    render_report(report)
    # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de retour.
    return 0


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
