# Lecture du fichier — Lecture et validation des fichiers d’une publication Excel.
# On contrôle provenance, empreintes, lignes et liens avant que le chargeur ne publie ce lot en base.
# Vérifier le format ne suffit pas à valider la situation métier.
#

"""Premier palier du chargeur Excel : controle local, sans aucune ecriture.

Ce fichier ne se connecte PAS a PostgreSQL et ne consulte PAS le NAS.
Il ne normalise pas a nouveau les Excel et ne recalcule pas les classifications.
Le chargement transactionnel sera ajoute apres validation de ce controle.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles Counter depuis collections, pour les appels de ce fichier.
from collections import Counter
# On importe csv. On transforme les tableaux entre lignes Python et fichiers CSV.
import csv
# On rend disponibles datetime depuis datetime, pour les appels de ce fichier.
from datetime import datetime
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe io. On peut fournir des flux en mémoire aux lecteurs et aux captures de sortie.
import io
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path, PurePosixPath depuis pathlib, pour les appels de ce fichier.
from pathlib import Path, PurePosixPath
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys


class ValidationError(ValueError):
    """Une incoherence doit bloquer le futur chargement, pas etre corrigee en silence."""


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(condition, message):
    # On prévoit le cas où condition est évalué comme faux, par exemple une valeur vide selon son type.
    if not condition:
        # On interrompt cette branche avec ValidationError.
        raise ValidationError(message)


# On calcule l’empreinte SHA-256 utilisée pour comparer le contenu aux métadonnées attendues.
def sha256(data):
    # On fournit à l’appelant l’empreinte de hashlib.sha256(data) écrite en caractères hexadécimaux.
    return hashlib.sha256(data).hexdigest()


# On vérifie la forme attendue d’une empreinte avant de s’en servir comme référence de comparaison.
def hash_value(value, label):
    # On exige ici que la valeur reçue est du type str et le contrôle re.fullmatch('[0-9a-f]{64}',
    # value) est positif. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
        "Empreinte SHA-256 invalide : " + label,
    )
    # On remet la valeur reçue à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return value


# On contrôle un compteur avant de l’utiliser dans les vérifications du lot.
def count_value(value, label):
    # On exige ici que type(value) est exactement int et la valeur reçue est au moins égal à 0. Si ce
    # n’est pas le cas, le message associé bloque la suite.
    require(type(value) is int and value >= 0, "Comptage invalide : " + label)
    # On remet la valeur reçue à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return value


# On contrôle et prépare une date selon le format attendu par le chargeur.
def date_value(value, label):
    # On exige ici que la valeur reçue est du type str. Si ce n’est pas le cas, le message associé
    # bloque la suite.
    require(isinstance(value, str), "Date absente : " + label)
    # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
    try:
        # On interprète la date ISO reçue ; les vérifications de fuseau et de cohérence restent
        # nécessaires après cette conversion.
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        # On interrompt cette branche avec ValidationError. La cause initiale reste attachée grâce à
        # from.
        raise ValidationError("Date invalide : " + label) from exc
    # Sans fuseau, une heure locale serait ambiguë lors d’un changement d’heure ou d’un
    # rapprochement avec des événements en UTC.
    require(
        result.tzinfo is not None and result.utcoffset() is not None,
        "Fuseau horaire absent : " + label,
    )
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On exige un objet JSON du type prévu pour les métadonnées.
def json_object(data, label):
    # On refuse les clés répétées plutôt qu’écraser silencieusement leur première valeur.
    def no_duplicate_keys(pairs):
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
        result = json.loads(
            # On transmet les couples JSON à ce contrôle avant leur conversion finale, notamment pour
            # détecter les clés répétées.
            data.decode("utf-8-sig"), object_pairs_hook=no_duplicate_keys
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        # On interrompt cette branche avec ValidationError. La cause initiale reste attachée grâce à
        # from.
        raise ValidationError("JSON illisible : " + label) from exc
    # On exige ici que le résultat de cette opération est du type dict. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(isinstance(result, dict), "Objet JSON attendu : " + label)
    # On exige ici que type(result.get('format_version')) est exactement int et
    # result['format_version'] correspond à 1. Si ce n’est pas le cas, le message associé bloque la
    # suite.
    require(
        type(result.get("format_version")) is int and result["format_version"] == 1,
        "Format de manifeste non pris en charge : " + label,
    )
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


class LocalFiles:
    """Ne lit que des fichiers contenus dans data/ ou state/ du projet.

    Les empreintes portent sur les octets originaux. Le cache permet de controler
    et parser les memes octets ; une modification pendant le controle le bloque.
    """

    def __init__(self, root):
        # On garde dans self.root le chemin absolu résolu de Path(root), en tenant compte des liens
        # symboliques.
        self.root = Path(root).resolve()
        # On crée le dictionnaire vide self.cache pour y ranger ensuite les éléments par clé.
        self.cache = {}
        # On crée le dictionnaire vide self.signatures pour y ranger ensuite les éléments par clé.
        self.signatures = {}

    def path(self, relative):
        # On exige ici que le chemin relatif est du type str et le chemin relatif est évalué comme vrai
        # et le texte '\\' ne figure pas dans le chemin relatif. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(
            isinstance(relative, str) and relative and "\\" not in relative,
            "Chemin relatif non valide dans un manifeste.",
        )
        # On garde PurePosixPath(relative).parts sous le nom parts ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        parts = PurePosixPath(relative).parts
        # On exige ici que la condition PurePosixPath(relative).is_absolute() n’est pas remplie et le
        # texte '..' ne figure pas dans parts et parts est évalué comme vrai et parts[0] appartient à
        # {'data', 'state'}. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            not PurePosixPath(relative).is_absolute()
            # On exige aussi que le texte '..' ne figure pas dans parts.
            and ".." not in parts
            and parts
            # On exige aussi que parts[0] appartient à {'data', 'state'}.
            and parts[0] in {"data", "state"},
            "Chemin hors des dossiers locaux autorises : " + relative,
        )
        # On calcule la destination locale réelle, en suivant aussi les liens symboliques ; un
        # chemin qui paraît interne peut sinon sortir du projet.
        resolved = (self.root / relative).resolve()
        # On calcule séparément la racine du dossier autorisé (data ou state) pour vérifier que ce
        # dossier lui-même n’est pas redirigé ailleurs.
        anchor = (self.root / parts[0]).resolve()
        # Ce contrôle porte sur la destination résolue ; un chemin textuellement situé sous le
        # projet pourrait encore pointer ailleurs par un lien symbolique.
        require(
            anchor.is_relative_to(self.root) and resolved.is_relative_to(anchor),
            "Chemin redirige hors du projet : " + relative,
        )
        # On remet le chemin résolu à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return resolved

    # On prépare l’information utilisée pour comparer l’état de ce fichier.
    @staticmethod
    def signature(path):
        # On relève les métadonnées du fichier sans encore lire son contenu ; elles serviront à
        # repérer un changement pendant les contrôles.
        stat = path.stat()
        # La signature associe taille, date de modification précise et identifiant du fichier. C’est
        # un contrôle de stabilité, pas une empreinte de contenu.
        return stat.st_size, stat.st_mtime_ns, stat.st_ino

    def read(self, relative, expected_sha=None):
        # On garde dans path le chemin après vérification de son périmètre autorisé.
        path = self.path(relative)
        # On exige ici que le chemin de travail désigne un fichier. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(path.is_file(), "Fichier absent : " + relative)
        # On lit ce fichier seulement à son premier accès ; les contrôles suivants reprendront les
        # mêmes octets gardés en mémoire.
        if relative not in self.cache:
            # On relève l’état juste avant la lecture ; une seconde mesure permettra de repérer une
            # modification survenue pendant celle-ci.
            before = self.signature(path)
            # On garde dans data les octets lus depuis path, avant toute conversion en texte. Les
            # contrôles de contenu pourront ainsi repartir de cette lecture.
            data = path.read_bytes()
            # On recontrôle les métadonnées du fichier ; un changement pendant la lecture rendrait
            # le lot difficile à rattacher à une version précise.
            require(
                before == self.signature(path),
                "Fichier modifie pendant la lecture : " + relative,
            )
            # On gardes octets effectivement lus pour que l’analyse et le calcul d’empreinte
            # portent sur la même copie en mémoire.
            self.cache[relative] = data
            # On conserve aussi les métadonnées relevées avant cette lecture pour les recontrôler à
            # la fin.
            self.signatures[relative] = before
        # Les contrôles suivants repartent des octets déjà lus, pas d’une nouvelle lecture qui
        # pourrait donner une autre version.
        data = self.cache[relative]
        # Si le manifeste annonce une empreinte, on doit la comparer au contenu lu. L’absence
        # d’empreinte ne doit pas devenir une comparaison avec une chaîne vide.
        if expected_sha is not None:
            # On vérifie l’empreinte du contenu par rapport au lot annoncé ; avoir le bon nom de
            # fichier ne suffit pas à identifier sa version.
            require(
                sha256(data) == hash_value(expected_sha, relative),
                "Empreinte differente : " + relative,
            )
        # On remet les données en mémoire à l’appelant ; les étapes suivantes de cette fonction ne sont
        # plus parcourues.
        return data

    def json(self, relative, expected_sha=None):
        # On passe d’abord par la lecture contrôlée et son éventuelle empreinte, puis on décode le
        # JSON : on ne contourne pas le cache.
        return json_object(self.read(relative, expected_sha), relative)

    # On contrôle que les fichiers suivis n’ont pas changé depuis leur lecture.
    def unchanged(self):
        # On parcourt les couples (relative, signature) de self.signatures : on garde ensemble la
        # clé et sa valeur au lieu des traiter dans deux listes séparées.
        for relative, signature in self.signatures.items():
            # On recontrôle les métadonnées du fichier ; un changement pendant la lecture rendrait
            # le lot difficile à rattacher à une version précise.
            require(
                self.signature(self.path(relative)) == signature,
                "Fichier modifie pendant le controle : " + relative,
            )


def read_csv(data, label, required_columns):
    # On tente ce bloc et on traite séparément les erreurs prévues : (UnicodeError, csv.Error).
    try:
        # On décodes octets puis on lit le CSV en associant chaque valeur à son en-tête.
        # utf-8-sig accepte aussi la marque BOM que certains outils ajoutent au début.
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
        # On récupère les en-têtes avant de parcourir les lignes : des colonnes absentes ou
        # dupliquées rendraient l’association des valeurs peu fiable.
        columns = reader.fieldnames
        # On vérifie l’unicité avant de constituer le résultat ; écraser une entrée dupliquée ferait
        # disparaître une incohérence de la source.
        require(
            columns and len(columns) == len(set(columns)) and all(columns),
            "Entete CSV absent ou duplique : " + label,
        )
        # Toutes les colonnes ou clés indispensables doivent être présentes ; des champs
        # supplémentaires ne compensent pas l’absence de l’un d’eux.
        require(
            set(required_columns).issubset(columns),
            "Colonnes indispensables absentes : " + label,
        )
        # On matérialise les lignes en mémoire pour pouvoir les contrôler plusieurs fois ; le
        # lecteur CSV seul se parcourt progressivement.
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        # On interrompt cette branche avec ValidationError. La cause initiale reste attachée grâce à
        # from.
        raise ValidationError("CSV illisible : " + label) from exc
    # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        all(
            None not in row and all(value is not None for value in row.values())
            for row in rows
        ),
        "Nombre de cellules incoherent dans le CSV : " + label,
    )
    # On remet les lignes à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return rows


# On rassemble dans PROVENANCE les 10 éléments explicitement indiqués, en conservant leur structure.
PROVENANCE = {
    "Vineyard",
    "Acquisition_ID_normalise",
    "Acquisition_side",
    "Acquisition_row_key",
    "source_file",
    "source_sheet",
    "source_row_number",
    "ingested_at",
    "excel_reference_version_id",
    "source_sha256",
}


# On vérifie les lignes à partir des colonnes et règles attendues.
def check_rows(rows, key, entry, label):
    # On parcourt les lignes en gardant aussi sa position dans (ordinal, row) ; le comptage commence à
    # 1.
    for ordinal, row in enumerate(rows, 1):
        # On assemble ces deux éléments pour construire context.
        context = label + " / ligne de donnees " + str(ordinal)
        # On exige ici que row['Vineyard'].casefold() correspond à la clé de l’élément. Si ce n’est pas
        # le cas, le message associé bloque la suite.
        require(row["Vineyard"].casefold() == key, "Vignoble incoherent : " + context)
        # On parcourt [('excel_reference_version_id', 'version_id'), ('source_sha256', 'source_… ;
        # (column, field) désigne l’élément courant à chaque passage dans la boucle.
        for column, field in [
            ("excel_reference_version_id", "version_id"),
            ("source_sha256", "source_sha256"),
            ("source_file", "source_filename"),
            ("ingested_at", "ingested_at"),
        ]:
            # On exige ici que row[column] correspond à entry[field]. Si ce n’est pas le cas, le
            # message associé bloque la suite.
            require(
                row[column] == entry[field],
                "Provenance incoherente (" + column + ") : " + context,
            )
        # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas,
        # le message associé bloque la suite.
        require(
            row["Acquisition_ID_normalise"]
            and row["Acquisition_row_key"]
            and row["source_sheet"]
            and row["Acquisition_side"],
            "Identifiant ou provenance incomplet : " + context,
        )
        # On exige ici que le contrôle row['source_row_number'].isdigit() est positif et
        # int(row['source_row_number']) est supérieur à 0. Si ce n’est pas le cas, le message associé
        # bloque la suite.
        require(
            row["source_row_number"].isdigit() and int(row["source_row_number"]) > 0,
            "Numero de ligne source invalide : " + context,
        )


# On construit la représentation utilisée pour comparer les lignes du lot.
def row_identity(row):
    # On compare les identites et leur multiplicite, sans recalculer les regles metier.
    return tuple(
        row[column]
        for column in (
            "Acquisition_ID_normalise",
            "Acquisition_side",
            "Acquisition_row_key",
            "source_sheet",
            "source_row_number",
        )
    )


# On vérifie la publication, les fichiers annoncés et leur cohérence avant chargement.
def check_publication(root, *, files=None):
    # Le futur importeur peut reutiliser exactement les octets controles.
    files = files if files is not None else LocalFiles(root)
    # On garde dans state le chemin après vérification de son périmètre autorisé.
    state = files.path("state/excel_ingestion")

    # On refuse de préparer le lot alors qu’une ingestion en attente est signalée.
    def no_pending_ingestion():
        # On exige ici que la condition (state / 'ingestion.lock').exists() n’est pas remplie. Si ce
        # n’est pas le cas, le message associé bloque la suite.
        require(
            not (state / "ingestion.lock").exists(),
            "Une ingestion est en cours ou un verrou subsiste. Ne pas supprimer le verrou sans diagnostic.",
        )
        # On exige ici que la condition (state / 'pending_publication.json').exists() n’est pas
        # remplie. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            not (state / "pending_publication.json").exists(),
            "Une publication interrompue doit etre diagnostiquee avant de continuer.",
        )

    # On appelle no_pending_ingestion sans argument positionnel.
    no_pending_ingestion()
    # On garde dans registry le contenu du fichier JSON après passage par le lecteur contrôlé.
    registry = files.json("state/excel_ingestion/current.json")
    # On récupère registry['publication_manifest'] et on le garde dans publication_path pour la suite.
    publication_path = registry["publication_manifest"]
    # On garde dans publication le contenu du fichier JSON après passage par le lecteur contrôlé.
    publication = files.json(publication_path)
    # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        all(registry.get(key) == value for key, value in publication.items()),
        "Le registre courant et le manifeste de publication ne correspondent pas.",
    )
    # On exige ici que le champ 'publication_id' de la publication Excel est évalué comme vrai. Si ce
    # n’est pas le cas, le message associé bloque la suite.
    require(publication.get("publication_id"), "Identifiant de publication absent.")
    # On garde dans published_at la date validée et convertie selon le format du chargeur.
    published_at = date_value(publication["published_at"], "published_at")
    # On récupère publication['versions'] et on le garde dans entries pour la suite.
    entries = publication["versions"]
    # On exige ici que entries est du type dict et entries est évalué comme vrai. Si ce n’est pas le
    # cas, le message associé bloque la suite.
    require(isinstance(entries, dict) and entries, "Publication sans versions.")
    # On récupère le repère utilisé pour les données Excel dans publication et on le garde dans
    # reference pour la suite.
    reference = publication["reference"]
    # On appelle count_value avec reference['rows'].
    count_value(reference["rows"], "reference.rows")
    # On vérifie l’empreinte du contenu par rapport au lot annoncé ; avoir le bon nom de fichier ne
    # suffit pas à identifier sa version.
    require(
        registry["compatibility_export_sha256"] == reference["sha256"],
        "Empreinte de compatibilite incoherente dans le registre.",
    )
    # On garde dans ref_rows les lignes décodées par le lecteur CSV de ce module.
    ref_rows = read_csv(
        files.read(reference["path"], reference["sha256"]),
        reference["path"],
        PROVENANCE,
    )
    # On exige ici que len(ref_rows) correspond aux lignes dans reference. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        len(ref_rows) == reference["rows"],
        "Nombre de lignes de reference.csv incoherent.",
    )

    # On récupère publication['ingestion_execution_id'] et on le garde dans execution_id pour la suite.
    execution_id = publication["ingestion_execution_id"]
    # On exige ici que l’identifiant d’exécution est du type str et le contrôle
    # re.fullmatch('[A-Za-z0-9_-]+', execution_id) est positif. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        isinstance(execution_id, str) and re.fullmatch(r"[A-Za-z0-9_-]+", execution_id),
        "Identifiant d execution invalide.",
    )
    # On garde dans run le contenu du fichier JSON après passage par le lecteur contrôlé.
    run = files.json(
        "data/03_normalized/excel_ingestion_runs/" + execution_id + "/manifest.json"
    )
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        run["execution_id"] == execution_id
        # On exige aussi que l’identifiant de la publication Excel dans run correspond à l’identifiant
        # de la publication Excel dans publication.
        and run["publication_id"] == publication["publication_id"]
        # On exige aussi que le chemin du tableau Excel regroupé dans run correspond au chemin de
        # travail dans reference.
        and run["reference_path"] == reference["path"],
        "Execution et publication incompatibles.",
    )
    # On exige ici que l’état du traitement dans run appartient à {'success',
    # 'reporting_error_after_publication'}. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        run["status"] in {"success", "reporting_error_after_publication"},
        "Execution non publiable : " + str(run["status"]),
    )
    # On garde dans started la date validée et convertie selon le format du chargeur.
    started = date_value(run["started_at"], "execution.started_at")
    # On garde dans finished la date validée et convertie selon le format du chargeur.
    finished = date_value(run["finished_at"], "execution.finished_at")
    # On exige ici que le test started <= published_at <= finished est satisfait. Si ce n’est pas le
    # cas, le message associé bloque la suite.
    require(
        started <= published_at <= finished, "Chronologie de publication incoherente."
    )
    # On exige ici que type(run['initialization']) est exactement bool et les éléments d’identité du
    # lot dans run est du type dict. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        type(run["initialization"]) is bool and isinstance(run["identity"], dict),
        "Metadonnees d execution invalides.",
    )

    # On prépare report comme liste vide ; on la remplira au fil des opérations suivantes.
    report = []
    # On crée le dictionnaire vide normalized_identities pour y ranger ensuite les éléments par clé.
    normalized_identities = {}
    # On parcourt sorted(entries.items()) ; (key, entry) désigne l’élément courant à chaque passage
    # dans la boucle.
    for key, entry in sorted(entries.items()):
        # On exige ici que la clé de l’élément correspond à entry['vineyard'].casefold(). Si ce n’est
        # pas le cas, le message associé bloque la suite.
        require(
            key == entry["vineyard"].casefold(), "Cle de vignoble incoherente : " + key
        )
        # On exige ici que l’identifiant de version dans entry est du type str et le test
        # entry['version_id'] est satisfait. Si ce n’est pas le cas, le message associé bloque la
        # suite.
        require(
            isinstance(entry["version_id"], str) and entry["version_id"],
            "Version sans identifiant : " + key,
        )
        # On appelle date_value avec entry['ingested_at'].
        date_value(entry["ingested_at"], key + ".ingested_at")
        # On exige ici que date_value(entry['ingested_at'], key) ne dépasse pas la date de publication.
        # Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            date_value(entry["ingested_at"], key) <= published_at,
            "Version ingeree apres publication : " + key,
        )
        # On assemble ces deux éléments pour construire storage_key.
        storage_key = "v_" + sha256(entry["vineyard"].casefold().encode("utf-8"))[:10]
        # On garde dans version le contenu du fichier JSON après passage par le lecteur contrôlé.
        version = files.json(entry["manifest"], entry["manifest_sha256"])
        # On parcourt ('version_id', 'ingested_at', 'source_sha256', 'identity', 'normalized_ro… ;
        # field désigne l’élément courant à chaque passage dans la boucle.
        for field in (
            "version_id",
            "ingested_at",
            "source_sha256",
            "identity",
            "normalized_rows",
            "logical_acquisitions",
            "rejected_rows",
            "vineyard",
        ):
            # On exige ici que version[field] correspond à entry[field]. Si ce n’est pas le cas, le
            # message associé bloque la suite.
            require(
                version[field] == entry[field],
                "Version et publication incompatibles : " + key + " / " + field,
            )
        # On exige ici que version['source_file'] correspond au nom du fichier source dans entry. Si
        # ce n’est pas le cas, le message associé bloque la suite.
        require(
            version["source_file"] == entry["source_filename"],
            "Nom de source incoherent : " + key,
        )
        # On exige ici que Path(version['source_file']).name correspond à version['source_file']. Si ce
        # n’est pas le cas, le message associé bloque la suite.
        require(
            Path(version["source_file"]).name == version["source_file"],
            "Nom de source non valide : " + key,
        )
        # On appelle date_value avec version['source_modified_at'].
        date_value(version["source_modified_at"], key + ".source_modified_at")
        # On parcourt ('normalized_rows', 'logical_acquisitions', 'rejected_rows', 'source_size… ;
        # field désigne l’élément courant à chaque passage dans la boucle.
        for field in (
            "normalized_rows",
            "logical_acquisitions",
            "rejected_rows",
            "source_size",
        ):
            # On appelle count_value avec version[field].
            count_value(version[field], key + "." + field)
        # On récupère version['artifacts'] et on le garde dans artifacts pour la suite.
        artifacts = version["artifacts"]
        # Toutes les colonnes ou clés indispensables doivent être présentes ; des champs
        # supplémentaires ne compensent pas l’absence de l’un d’eux.
        require(
            isinstance(artifacts, dict)
            # On exige aussi que le contrôle {'source', 'normalized', 'rejected', 'config', 'reader',
            # 'versioning'}.is… est positif.
            and {
                "source",
                "normalized",
                "rejected",
                "config",
                "reader",
                "versioning",
            }.issubset(artifacts),
            "Artefacts de version incomplets : " + key,
        )
        # On parcourt les couples (label, artifact) de artifacts : on garde ensemble la clé et sa
        # valeur au lieu des traiter dans deux listes séparées.
        for label, artifact in artifacts.items():
            # On appelle files.read avec artifact['path'].
            files.read(artifact["path"], artifact["sha256"])
        # On exige ici que artifacts['source']['sha256'] correspond à l’empreinte du fichier source
        # dans version et len(files.read(artifacts['source']['path'])) correspond à
        # version['source_size']. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            artifacts["source"]["sha256"] == version["source_sha256"]
            # On exige aussi que len(files.read(artifacts['source']['path'])) correspond à
            # version['source_size'].
            and len(files.read(artifacts["source"]["path"])) == version["source_size"],
            "Source archivee incoherente : " + key,
        )
        # On exige ici que PurePosixPath(artifacts['source']['path']).name correspond à
        # version['source_file']. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            PurePosixPath(artifacts["source"]["path"]).name == version["source_file"],
            "Nom du fichier archive incoherent : " + key,
        )
        # On parcourt [('config', 'config_sha256'), ('reader', 'reader_sha256'), ('versioning',… ;
        # (label, identity_field) désigne l’élément courant à chaque passage dans la boucle.
        for label, identity_field in [
            ("config", "config_sha256"),
            ("reader", "reader_sha256"),
            ("versioning", "versioning_sha256"),
        ]:
            # On exige ici que artifacts[label]['sha256'] correspond à
            # version['identity'][identity_field]. Si ce n’est pas le cas, le message associé bloque la
            # suite.
            require(
                artifacts[label]["sha256"] == version["identity"][identity_field],
                "Identite du traitement incoherente : " + key + " / " + label,
            )
        # On exige ici que le chemin du tableau normalisé dans entry correspond au chemin de travail
        # dans artifacts['normalized']. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            entry["normalized_path"] == artifacts["normalized"]["path"],
            "Chemin normalise incoherent : " + key,
        )
        # On garde dans normalized les lignes décodées par le lecteur CSV de ce module.
        normalized = read_csv(
            files.read(entry["normalized_path"]), entry["normalized_path"], PROVENANCE
        )
        # On garde dans rejected les lignes décodées par le lecteur CSV de ce module.
        rejected = read_csv(
            files.read(artifacts["rejected"]["path"]),
            artifacts["rejected"]["path"],
            {"excel_reference_version_id", "source_sha256"},
        )
        # On exige ici que len(normalized) correspond au nombre de lignes normalisées dans version et
        # normalized est évalué comme vrai. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            len(normalized) == version["normalized_rows"] and normalized,
            "Nombre de lignes normalisees incoherent ou nul : " + key,
        )
        # On exige ici que len(rejected) correspond au nombre de lignes rejetées dans version. Si ce
        # n’est pas le cas, le message associé bloque la suite.
        require(
            len(rejected) == version["rejected_rows"],
            "Nombre de rejets incoherent : " + key,
        )
        # On parcourt rejected ; row désigne l’élément courant à chaque passage dans la boucle.
        for row in rejected:
            # On exige ici que row['excel_reference_version_id'] correspond à l’identifiant de version
            # dans entry et l’empreinte du fichier source dans row correspond à l’empreinte du fichier
            # source dans entry. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                row["excel_reference_version_id"] == entry["version_id"]
                # On exige aussi que l’empreinte du fichier source dans row correspond à l’empreinte du
                # fichier source dans entry.
                and row["source_sha256"] == entry["source_sha256"],
                "Provenance des rejets incoherente : " + key,
            )
        # On appelle check_rows avec normalized.
        check_rows(normalized, key, entry, entry["normalized_path"])
        # On garde dans logical le nombre d’éléments de {row['Acquisition_ID_normalise'] for row in
        # normalized}.
        logical = len({row["Acquisition_ID_normalise"] for row in normalized})
        # On exige ici que logical correspond au nombre d’acquisitions distinctes dans version. Si ce
        # n’est pas le cas, le message associé bloque la suite.
        require(
            logical == version["logical_acquisitions"],
            "Nombre d acquisitions logiques incoherent : " + key,
        )
        # Les CSV individuels copies dans la publication doivent rester identiques.
        snapshot = (
            PurePosixPath(publication_path).parent / (storage_key + ".csv")
        ).as_posix()
        # On appelle files.read avec snapshot.
        files.read(snapshot, artifacts["normalized"]["sha256"])
        # On garde dans normalized_identities[key] les effectifs de chaque valeur rencontrée.
        normalized_identities[key] = Counter(row_identity(row) for row in normalized)
        # On ajoute {'vineyard': entry['vineyard'], 'version_id': entry['version_id'], 'rows':
        # len(normalized… à la fin de report ; les éléments précédents restent conservés.
        report.append(
            {
                # On renseigne le domaine concerné sous la clé 'vineyard'.
                "vineyard": entry["vineyard"],
                # On renseigne l’identifiant de version sous la clé 'version_id'.
                "version_id": entry["version_id"],
                # On renseigne les lignes sous la clé 'rows'.
                "rows": len(normalized),
                # On renseigne le nombre d’acquisitions distinctes sous la clé 'logical_acquisitions'.
                "logical_acquisitions": logical,
                # On renseigne le nombre de lignes rejetées sous la clé 'rejected_rows'.
                "rejected_rows": len(rejected),
            }
        )

    # On indexe le résultat par key, avec [] comme valeur ; les contrôles d’unicité sont importants
    # car une même clé ne garde qu’une valeur dans un dictionnaire.
    ref_by_vineyard = {key: [] for key in entries}
    # On parcourt ref_rows ; row désigne l’élément courant à chaque passage dans la boucle.
    for row in ref_rows:
        # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
        # enregistré dans les données sources.
        key = row["Vineyard"].casefold()
        # On exige ici que la clé de l’élément appartient à entries. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(
            key in entries, "Vignoble inconnu dans la reference : " + row["Vineyard"]
        )
        # On ajoute row à la fin de ref_by_vineyard[key] ; les éléments précédents restent conservés.
        ref_by_vineyard[key].append(row)
    # On parcourt les couples (key, rows) de ref_by_vineyard : on garde ensemble la clé et sa valeur
    # au lieu des traiter dans deux listes séparées.
    for key, rows in ref_by_vineyard.items():
        # On appelle check_rows avec rows.
        check_rows(rows, key, entries[key], reference["path"])
        # On exige ici que Counter((row_identity(row) for row in rows)) correspond à
        # normalized_identities[key]. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            Counter(row_identity(row) for row in rows) == normalized_identities[key],
            "Lignes de publication incompatibles avec la version : " + key,
        )
    # On exige ici que sum((item['rows'] for item in report)) correspond à len(ref_rows). Si ce n’est
    # pas le cas, le message associé bloque la suite.
    require(
        sum(item["rows"] for item in report) == len(ref_rows),
        "Comptage global incoherent.",
    )

    # On garde dans selected un ensemble vide, qui servira à repérer les valeurs déjà rencontrées.
    selected = set()
    # On parcourt les domaines sélectionnés dans run ; item désigne l’élément courant à chaque passage
    # dans la boucle.
    for item in run["vineyards"]:
        # On garde dans key la forme de item['vineyard'] adaptée aux comparaisons sans distinction de
        # casse.
        key = item["vineyard"].casefold()
        # On exige ici que la clé de l’élément appartient à entries et la clé de l’élément ne figure
        # pas dans la sélection retenue. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            key in entries and key not in selected,
            "Selection d execution incoherente : " + key,
        )
        # On ajoute key à selected ; comme il s’agit d’un ensemble, une valeur déjà présente n’est pas
        # comptée deux fois.
        selected.add(key)
        # On exige ici que l’état du traitement dans item appartient à {'version_created',
        # 'unchanged'}. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            item["status"] in {"version_created", "unchanged"},
            "Resultat vignoble non publiable : " + key,
        )
        # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas,
        # le message associé bloque la suite.
        require(
            item["version_id"] == entries[key]["version_id"]
            # On exige aussi que la date d’ingestion dans item correspond à la date d’ingestion dans
            # entries[key].
            and item["ingested_at"] == entries[key]["ingested_at"]
            # On exige aussi que item['source_file'] correspond au nom du fichier source dans
            # entries[key].
            and item["source_file"] == entries[key]["source_filename"],
            "Resultat vignoble incompatible : " + key,
        )
        # On garde dans checked la date validée et convertie selon le format du chargeur.
        checked = date_value(item["checked_at"], key + ".checked_at")
        # On exige ici que le test started <= checked <= finished est satisfait. Si ce n’est pas le
        # cas, le message associé bloque la suite.
        require(
            started <= checked <= finished, "Date de verification incoherente : " + key
        )
        # On exige ici que les éléments d’identité du lot dans entries[key] correspond aux éléments
        # d’identité du lot dans run. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            entries[key]["identity"] == run["identity"],
            "Identite d execution incoherente : " + key,
        )
        # On vérifie ce cas avant la suite : l’état du traitement dans item correspond au texte
        # 'version_created'.
        if item["status"] == "version_created":
            # On parcourt [('rows', 'normalized_rows'), ('logical_acquisitions', 'logical_acquisiti… ;
            # (field, entry_field) désigne l’élément courant à chaque passage dans la boucle.
            for field, entry_field in [
                ("rows", "normalized_rows"),
                ("logical_acquisitions", "logical_acquisitions"),
                ("rejected_rows", "rejected_rows"),
            ]:
                # On exige ici que item[field] correspond à entries[key][entry_field]. Si ce n’est pas
                # le cas, le message associé bloque la suite.
                require(
                    item[field] == entries[key][entry_field],
                    "Comptage d execution incoherent : " + key,
                )
    # On exige ici que la sélection retenue est évalué comme vrai. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(selected, "Execution sans vignoble selectionne.")
    # Cette branche traite le cas où le test run['initialization'] est satisfait.
    if run["initialization"]:
        # On exige ici que la sélection retenue correspond à set(entries). Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(selected == set(entries), "Initialisation incomplete.")
    # On appelle files.unchanged sans argument positionnel.
    files.unchanged()
    # On appelle no_pending_ingestion sans argument positionnel.
    no_pending_ingestion()
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
        "publication_id": publication["publication_id"],
        # On renseigne l’identifiant d’exécution sous la clé 'execution_id'.
        "execution_id": execution_id,
        # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
        "vineyards": report,
        # On associe la clé 'files_verified' à cette valeur dans cet objet.
        "files_verified": len(files.cache),
        # On renseigne les lignes sous la clé 'rows'.
        "rows": len(ref_rows),
        # On renseigne le nombre d’acquisitions distinctes sous la clé 'logical_acquisitions'.
        "logical_acquisitions": sum(item["logical_acquisitions"] for item in report),
        # On renseigne le nombre de lignes rejetées sous la clé 'rejected_rows'.
        "rejected_rows": sum(item["rejected_rows"] for item in report),
    }


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
        description="Controle de la publication Excel courante, sans ecriture ni acces NAS/PostgreSQL."
    )
    # Option --check-only : Obligatoire : cette premiere version ne charge aucune donnee. Sa
    # déclaration ne déclenche pas l’action.
    parser.add_argument(
        "--check-only",
        action="store_true",
        required=True,
        help="Obligatoire : cette premiere version ne charge aucune donnee.",
    )
    # Option --project-root : Racine du projet ; detectee automatiquement si le fichier est dans
    # scripts/. Sa déclaration ne déclenche pas l’action.
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Racine du projet ; detectee automatiquement si le fichier est dans scripts/.",
    )
    # On lit les options du contrôle de publication Excel ; cette vérification locale ne signifie
    # pas que des lignes ont été chargées en base.
    args = parser.parse_args(argv)
    # On tente ce bloc et on traite séparément les erreurs prévues : (ValidationError, OSError,
    # KeyError, TypeError, AttributeError).
    try:
        # On contrôle le lot publié et ses fichiers avant de construire les lignes destinées à la
        # base.
        result = check_publication(args.project_root)
    except (ValidationError, OSError, KeyError, TypeError, AttributeError) as exc:
        # On affiche 'CONTROLE BLOQUE : ' + str(exc) dans la sortie du programme.
        print("CONTROLE BLOQUE : " + str(exc), file=sys.stderr)
        # On affiche le texte 'Aucune ecriture et aucun chargement PostgreSQL.' dans la sortie du
        # programme.
        print("Aucune ecriture et aucun chargement PostgreSQL.", file=sys.stderr)
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    # On affiche le texte 'CONTROLE EXCEL - LECTURE SEULE' dans la sortie du programme.
    print("CONTROLE EXCEL - LECTURE SEULE")
    # On affiche 'Publication : ' + result['publication_id'] dans la sortie du programme.
    print("Publication : " + result["publication_id"])
    # On affiche 'Execution creatrice : ' + result['execution_id'] dans la sortie du programme.
    print("Execution creatrice : " + result["execution_id"])
    # On parcourt les domaines sélectionnés dans result ; item désigne l’élément courant à chaque
    # passage dans la boucle.
    for item in result["vineyards"]:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"{item['vineyard']} : OK | {item['version_id']} | {item['rows']} lignes | {item['logical_acquisitions']} acquisitions logiques | {item['rejected_rows']} rejets"
        )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        f"Total : {result['rows']} lignes | {result['logical_acquisitions']} acquisitions logiques | {result['rejected_rows']} rejets"
    )
    # On affiche 'Fichiers controles : ' + str(result['files_verified']) dans la sortie du programme.
    print("Fichiers controles : " + str(result["files_verified"]))
    # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un appel
    # depuis un autre outil.
    print("RESULTAT : OK - publication coherente pour preparer le chargement.")
    # On affiche le texte 'PostgreSQL : aucune connexion, aucune ecriture.' dans la sortie du
    # programme.
    print("PostgreSQL : aucune connexion, aucune ecriture.")
    # On affiche ce texte explicite dans la sortie du programme.
    print("NAS : aucun acces. Archives et registre : aucune modification.")
    # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de retour.
    return 0


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
