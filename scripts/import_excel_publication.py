# Lecture du fichier — Chargement d’un lot Excel vérifié dans les structures PostgreSQL prévues.
# On relie exécution, versions et publication. Réimporter le même lot ne doit pas justifier de
# réécrire son historique ; une divergence doit être examinée.
#

"""Chargement du socle Excel dans PostgreSQL, avec historique et transaction.

La preparation reutilise les octets verifies par load_excel_publication.py.
--check-only : aucun acces PostgreSQL. --load : controle puis import et activation.
Aucun acces NAS ; aucune modification des fichiers d'ingestion ou d'archives.
Compte dedie projet12_importer ; aucun repli vers le compte administrateur.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles Counter depuis collections, pour les appels de ce fichier.
from collections import Counter
# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On rend disponibles datetime depuis datetime, pour les appels de ce fichier.
from datetime import datetime
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys

# Import possible quand ce fichier est execute directement depuis scripts/.
from load_excel_publication import (
    LocalFiles,
    ValidationError,
    check_publication,
    read_csv,
    sha256,
    require,
)
# On rend disponibles database_config, verify_import_identity depuis import_connection_config, pour les
# appels de ce fichier.
from import_connection_config import database_config, verify_import_identity

# On regroupe dans TABLE_KEYS ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
# leur position.
TABLE_KEYS = {
    # On associe la clé 'core.vineyards' à cette valeur dans cet objet.
    "core.vineyards": ("vineyard_key",),
    # On associe la clé 'core.excel_ingestion_runs' à cette valeur dans cet objet.
    "core.excel_ingestion_runs": ("execution_id",),
    # On associe la clé 'core.excel_versions' à cette valeur dans cet objet.
    "core.excel_versions": ("vineyard_key", "version_id"),
    # On associe la clé 'core.excel_ingestion_run_vineyards' à cette valeur dans cet objet.
    "core.excel_ingestion_run_vineyards": ("execution_id", "vineyard_key"),
    # On associe la clé 'core.excel_publications' à cette valeur dans cet objet.
    "core.excel_publications": ("publication_id",),
    # On associe la clé 'core.excel_publication_versions' à cette valeur dans cet objet.
    "core.excel_publication_versions": ("publication_id", "vineyard_key"),
}
# On rassemble dans JSON_COLUMNS les 5 éléments explicitement indiqués, en conservant leur structure.
JSON_COLUMNS = {
    "identity",
    "manifest_payload",
    "metadata_payload",
    "result_payload",
    "payload",
}


# On prépare la valeur temporelle utilisée par le chargement SQL.
def timestamp(value):
    # On interprète la date ISO reçue ; les vérifications de fuseau et de cohérence restent
    # nécessaires après cette conversion.
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# On prépare la représentation structurée conservée avec les métadonnées du lot.
def payload(row):
    # Conserver les valeurs CSV textuelles. Seules les cellules vides deviennent NULL.
    # Aucune conversion de statut, aucune reinterpretation de date, aucun recalcul.
    return {key: (None if value == "" else value) for key, value in row.items()}


# On rassemble le lot à partir des fichiers et métadonnées contrôlés par cette fonction.
def prepare_bundle(root):
    # On garde dans files la valeur renvoyée par LocalFiles.
    files = LocalFiles(root)
    # On contrôle le lot publié et ses fichiers avant de construire les lignes destinées à la base.
    report = check_publication(root, files=files)
    # On garde dans registry le contenu du fichier JSON après passage par le lecteur contrôlé.
    registry = files.json("state/excel_ingestion/current.json")
    # On garde dans publication le contenu du fichier JSON après passage par le lecteur contrôlé.
    publication = files.json(registry["publication_manifest"])
    # On récupère publication['ingestion_execution_id'] et on le garde dans execution_id pour la suite.
    execution_id = publication["ingestion_execution_id"]
    # On assemble ces deux éléments pour construire run_path.
    run_path = (
        "data/03_normalized/excel_ingestion_runs/" + execution_id + "/manifest.json"
    )
    # On garde dans run le contenu du fichier JSON après passage par le lecteur contrôlé.
    run = files.json(run_path)
    # On prépare versions comme liste vide ; on la remplira au fil des opérations suivantes.
    versions = []
    # On parcourt sorted(publication['versions'].items()) ; (key, entry) désigne l’élément courant à
    # chaque passage dans la boucle.
    for key, entry in sorted(publication["versions"].items()):
        # On garde dans manifest le contenu du fichier JSON après passage par le lecteur contrôlé.
        manifest = files.json(entry["manifest"], entry["manifest_sha256"])
        # On récupère le chemin de travail dans manifest['artifacts']['normalized'] et on le garde dans
        # normalized_path pour la suite.
        normalized_path = manifest["artifacts"]["normalized"]["path"]
        # On récupère le chemin de travail dans manifest['artifacts']['rejected'] et on le garde dans
        # rejected_path pour la suite.
        rejected_path = manifest["artifacts"]["rejected"]["path"]
        # On garde dans normalized les lignes décodées par le lecteur CSV de ce module.
        normalized = read_csv(files.read(normalized_path), normalized_path, set())
        # On garde dans rejected les lignes décodées par le lecteur CSV de ce module.
        rejected = read_csv(files.read(rejected_path), rejected_path, set())
        # On ajoute {'key': key, 'entry': entry, 'manifest': manifest, 'normalized': normalized,
        # 'rejected':… à la fin de versions ; les éléments précédents restent conservés.
        versions.append(
            {
                # On renseigne la clé de l’élément sous la clé 'key'.
                "key": key,
                # On associe la clé 'entry' à cette valeur dans cet objet.
                "entry": entry,
                # On renseigne le manifeste du lot sous la clé 'manifest'.
                "manifest": manifest,
                # On associe la clé 'normalized' à cette valeur dans cet objet.
                "normalized": normalized,
                # On associe la clé 'rejected' à cette valeur dans cet objet.
                "rejected": rejected,
            }
        )
    # On récupère le repère utilisé pour les données Excel dans publication et on le garde dans
    # reference pour la suite.
    reference = publication["reference"]
    # On garde dans reference_rows les lignes décodées par le lecteur CSV de ce module.
    reference_rows = read_csv(files.read(reference["path"]), reference["path"], set())
    # On appelle files.unchanged sans argument positionnel.
    files.unchanged()
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'files' à cette valeur dans cet objet.
        "files": files,
        # On renseigne le bilan sous la clé 'report'.
        "report": report,
        # On associe la clé 'registry' à cette valeur dans cet objet.
        "registry": registry,
        # On renseigne la publication Excel sous la clé 'publication'.
        "publication": publication,
        # On associe la clé 'publication_path' à cette valeur dans cet objet.
        "publication_path": registry["publication_manifest"],
        # On associe la clé 'run' à cette valeur dans cet objet.
        "run": run,
        # On associe la clé 'run_path' à cette valeur dans cet objet.
        "run_path": run_path,
        # On associe la clé 'versions' à cette valeur dans cet objet.
        "versions": versions,
        # On renseigne le nombre de lignes du tableau regroupé sous la clé 'reference_rows'.
        "reference_rows": reference_rows,
    }


# On vérifie que le lot préparé est toujours cohérent avec la publication courante.
def check_still_current(bundle):
    # On reprend la liste des fichiers déclarés par le lot dans bundle ; cet accès suppose que la
    # clé a été produite ou vérifiée auparavant.
    files = bundle["files"]
    # Apres la preparation, ne jamais relire des CSV differents pour les inserer.
    # On utilise le cache valide, puis on refuse une modification locale detectee.
    files.unchanged()
    # On garde dans state le chemin après vérification de son périmètre autorisé.
    state = files.path("state/excel_ingestion")
    # On exige ici que la condition (state / 'ingestion.lock').exists() n’est pas remplie et la
    # condition (state / 'pending_publication.json').exists() n’est pas remplie. Si ce n’est pas le
    # cas, le message associé bloque la suite.
    require(
        not (state / "ingestion.lock").exists()
        # On exige aussi que la condition (state / 'pending_publication.json').exists() n’est pas
        # remplie.
        and not (state / "pending_publication.json").exists(),
        "Ingestion ou publication locale en cours : import annule.",
    )
    # On garde dans current_bytes les octets lus depuis
    # files.path('state/excel_ingestion/current.json'), avant toute conversion en texte. Les
    # contrôles de contenu pourront ainsi repartir de cette lecture.
    current_bytes = files.path("state/excel_ingestion/current.json").read_bytes()
    # On exige ici que current_bytes correspond à files.cache['state/excel_ingestion/current.json']. Si
    # ce n’est pas le cas, le message associé bloque la suite.
    require(
        current_bytes == files.cache["state/excel_ingestion/current.json"],
        "Le registre courant a change : import annule.",
    )


class PostgresRepository:
    """Toute ecriture est dans une transaction ; les snapshots existants sont verifies.

    Les requetes utilisent des parametres pour les valeurs et des identifiants SQL
    composes par psycopg. Aucune chaine issue d'un CSV n'est injectee dans le SQL.
    """

    def __init__(self, connection):
        # On rend disponibles sql depuis psycopg, pour les appels de ce fichier.
        from psycopg import sql
        # On rend disponibles Jsonb depuis psycopg.types.json, pour les appels de ce fichier.
        from psycopg.types.json import Jsonb

        # On garde la connexion PostgreSQL sous le nom self.connection ; cette affectation ne copie pas
        # à elle seule un objet mutable.
        self.connection = connection
        # On garde sql sous le nom self.sql ; cette affectation ne copie pas à elle seule un objet
        # mutable.
        self.sql = sql
        # On garde Jsonb sous le nom self.Jsonb ; cette affectation ne copie pas à elle seule un objet
        # mutable.
        self.Jsonb = Jsonb
        # On garde dans self.inserted les effectifs de chaque valeur rencontrée.
        self.inserted = Counter()
        # On garde dans self.reused les effectifs de chaque valeur rencontrée.
        self.reused = Counter()

    @contextmanager
    def transaction(self):
        # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre pas
        # tout le workflow.
        with self.connection.transaction():
            # Serialise les imports faits par ce chargeur, pour cette base.
            self.connection.execute("SET LOCAL lock_timeout = '10s'")
            # On interroge les valeurs enregistrées en base pour ce contrôle ; les paramètres
            # séparés de la requête fournissent les valeurs recherchées.
            self.connection.execute("SELECT pg_advisory_xact_lock(%s, %s)", (120026, 1))
            # On parcourt [*TABLE_KEYS, 'staging.excel_version_rows', 'staging.excel_publication_ro… ;
            # table désigne l’élément courant à chaque passage dans la boucle.
            for table in [
                *TABLE_KEYS,
                "staging.excel_version_rows",
                "staging.excel_publication_rows",
                "core.excel_current_publication",
            ]:
                # On récupère self.connection.execute('SELECT to_regclass(%s)', (table,)).fetchone()[0]
                # et on le garde dans found pour la suite.
                found = self.connection.execute(
                    "SELECT to_regclass(%s)", (table,)
                ).fetchone()[0]
                # On exige ici que found est renseigné (différent de None). Si ce n’est pas le cas, le
                # message associé bloque la suite.
                require(
                    found is not None,
                    "Table absente : " + table + ". Executer le script 002.",
                )
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield self

    def table_name(self, table):
        # On exige ici que table appartient à TABLE_KEYS ou table appartient à
        # {'staging.excel_version_rows', 'staging.excel_publication_rows'}. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            table in TABLE_KEYS
            # Ce cas est aussi retenu si table appartient à {'staging.excel_version_rows',
            # 'staging.excel_publication_rows'}.
            or table
            in {"staging.excel_version_rows", "staging.excel_publication_rows"},
            "Table non autorisee.",
        )
        # On protège les noms de schéma, table ou colonne avec Identifier ; les valeurs des lignes
        # sont, elles, transmises séparément aux paramètres SQL.
        return self.sql.Identifier(*table.split("."))

    def values(self, columns, values):
        # On fournit à l’appelant une séquence non modifiable construite à partir de (self.Jsonb(value)
        # if column in JSON_COLUMNS else value for column, value….
        return tuple(
            self.Jsonb(value) if column in JSON_COLUMNS else value
            for column, value in zip(columns, values)
        )

    # On conserve la donnée historique ou on vérifie qu’une donnée déjà présente est identique.
    def put_immutable(self, table, record):
        # On sélectionne dans TABLE_KEYS les éléments désignés par table ; keys recevra cette
        # sélection.
        keys = TABLE_KEYS[table]
        # On garde dans columns une séquence non modifiable construite à partir de record.
        columns = tuple(record)
        # On garde dans selected_columns le texte formé en réunissant les éléments avec self.sql.SQL(',
        # ') comme séparateur.
        selected_columns = self.sql.SQL(", ").join(
            self.sql.Identifier(column) for column in columns
        )
        # On garde dans where le texte formé en réunissant les éléments avec self.sql.SQL(' AND ')
        # comme séparateur.
        where = self.sql.SQL(" AND ").join(
            self.sql.SQL("{} = %s").format(self.sql.Identifier(key)) for key in keys
        )
        # Le verrou consultatif commun serialise les importeurs cooperants.
        # Ne pas exiger UPDATE sur une table historique pour une simple comparaison.
        query = self.sql.SQL("SELECT {} FROM {} WHERE {}").format(
            selected_columns, self.table_name(table), where
        )
        # On récupère une seule ligne du résultat SQL ; les contrôles suivants vérifient les valeurs
        # attendues.
        existing = self.connection.execute(
            query, tuple(record[key] for key in keys)
        ).fetchone()
        # On garde dans values une séquence non modifiable construite à partir de (record[column] for
        # column in columns).
        values = tuple(record[column] for column in columns)
        # On vérifie ce cas avant la suite : existing est renseigné (différent de None).
        if existing is not None:
            # On exige ici que tuple(existing) correspond aux valeurs. Si ce n’est pas le cas, le
            # message associé bloque la suite.
            require(
                tuple(existing) == values,
                "Contenu different pour un identifiant deja charge : "
                + table
                + " / "
                + ", ".join(str(record[k]) for k in keys),
            )
            # On ajoute 1 à self.reused[table] et on conserve ce nouvel état pour la suite.
            self.reused[table] += 1
            # On renvoie False comme résultat explicite de cette branche.
            return False
        # On garde dans query la valeur renvoyée par self.sql.SQL('INSERT INTO {} ({}) VALUES
        # ({})').format.
        query = self.sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            self.table_name(table),
            selected_columns,
            self.sql.SQL(", ").join(self.sql.Placeholder() for _ in columns),
        )
        # On envoie cette requête à self.connection avec ses paramètres ; son résultat sera contrôlé
        # séparément.
        self.connection.execute(query, self.values(columns, values))
        # On ajoute 1 à self.inserted[table] et on conserve ce nouvel état pour la suite.
        self.inserted[table] += 1
        # On renvoie True comme résultat explicite de cette branche.
        return True

    def put_rows(self, table, filters, identity_columns, records, *, new_parent):
        # Un snapshot deja charge ne doit pas etre repare/recrit en silence.
        # On verifie toutes ses lignes et leur contenu, meme en cas de relance.
        require(
            table in {"staging.excel_version_rows", "staging.excel_publication_rows"},
            "Table de lignes non autorisee.",
        )
        # On assemble ces deux éléments pour construire columns.
        columns = tuple(identity_columns) + ("payload",)
        # On garde dans selected le texte formé en réunissant les éléments avec self.sql.SQL(', ')
        # comme séparateur.
        selected = self.sql.SQL(", ").join(
            self.sql.Identifier(column) for column in columns
        )
        # On garde dans where le texte formé en réunissant les éléments avec self.sql.SQL(' AND ')
        # comme séparateur.
        where = self.sql.SQL(" AND ").join(
            self.sql.SQL("{} = %s").format(self.sql.Identifier(key)) for key in filters
        )
        # On garde dans query la valeur renvoyée par self.sql.SQL('SELECT {} FROM {} WHERE {}').format.
        query = self.sql.SQL("SELECT {} FROM {} WHERE {}").format(
            selected, self.table_name(table), where
        )
        # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
        # présenter.
        existing = self.connection.execute(query, tuple(filters.values())).fetchall()
        # On indexe le résultat par tuple((record[k] for k in identity_columns)), avec
        # record['payload'] comme valeur ; les contrôles d’unicité sont importants car une même clé
        # ne garde qu’une valeur dans un dictionnaire.
        expected_map = {
            tuple(record[k] for k in identity_columns): record["payload"]
            for record in records
        }
        # On exige ici que len(expected_map) correspond à len(records). Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            len(expected_map) == len(records),
            "Identites de lignes dupliquees dans le lot : " + table,
        )
        # On indexe le résultat par tuple(row[:-1]), avec row[-1] comme valeur ; les contrôles
        # d’unicité sont importants car une même clé ne garde qu’une valeur dans un dictionnaire.
        existing_map = {tuple(row[:-1]): row[-1] for row in existing}
        # On prévoit le cas où new_parent est évalué comme faux, par exemple une valeur vide selon son
        # type.
        if not new_parent:
            # On exige ici que len(existing) correspond à len(records) et existing_map correspond à
            # expected_map. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                len(existing) == len(records) and existing_map == expected_map,
                "Lignes historiques modifiees ou incompletes : " + table,
            )
            # On ajoute len(records) à self.reused[table] et on conserve ce nouvel état pour la suite.
            self.reused[table] += len(records)
            # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont
            # pas exécutées.
            return
        # On exige ici que la condition existing n’est pas remplie. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(not existing, "Lignes inattendues pour un nouveau snapshot : " + table)
        # On prévoit le cas où records est évalué comme faux, par exemple une valeur vide selon son
        # type.
        if not records:
            # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont
            # pas exécutées.
            return
        # On garde dans query la valeur renvoyée par self.sql.SQL('INSERT INTO {} ({}) VALUES
        # ({})').format.
        query = self.sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            self.table_name(table),
            selected,
            self.sql.SQL(", ").join(self.sql.Placeholder() for _ in columns),
        )
        # On construit values comme une liste à partir de self.values(columns, tuple((record[column]
        # for column in columns…, pour chaque record de records.
        values = [
            self.values(columns, tuple(record[column] for column in columns))
            for record in records
        ]
        # On utilise self.connection.cursor() dans son contexte de gestion ; les opérations de sortie
        # sont exécutées en quittant le bloc.
        with self.connection.cursor() as cursor:
            # On appelle cursor.executemany avec query.
            cursor.executemany(query, values)
        # On ajoute len(records) à self.inserted[table] et on conserve ce nouvel état pour la suite.
        self.inserted[table] += len(records)

    def verify_members(self, table, filters, expected_records):
        # On sélectionne dans TABLE_KEYS les éléments désignés par table ; keys recevra cette
        # sélection.
        keys = TABLE_KEYS[table]
        # On garde dans selected le texte formé en réunissant les éléments avec self.sql.SQL(', ')
        # comme séparateur.
        selected = self.sql.SQL(", ").join(self.sql.Identifier(key) for key in keys)
        # On garde dans where le texte formé en réunissant les éléments avec self.sql.SQL(' AND ')
        # comme séparateur.
        where = self.sql.SQL(" AND ").join(
            self.sql.SQL("{} = %s").format(self.sql.Identifier(key)) for key in filters
        )
        # On garde dans query la valeur renvoyée par self.sql.SQL('SELECT {} FROM {} WHERE {}').format.
        query = self.sql.SQL("SELECT {} FROM {} WHERE {}").format(
            selected, self.table_name(table), where
        )
        # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
        # présenter.
        rows = self.connection.execute(query, tuple(filters.values())).fetchall()
        # On construit expected comme un ensemble sans doublons à partir de tuple((record[key] for key
        # in keys)), pour chaque record de expected_records.
        expected = {tuple(record[key] for key in keys) for record in expected_records}
        # On exige ici que len(rows) correspond à len(expected) et {tuple(row) for row in rows}
        # correspond au résultat attendu. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            len(rows) == len(expected) and {tuple(row) for row in rows} == expected,
            "Composition historique differente : " + table,
        )

    # On gère le lien vers le résultat à consulter actuellement, sans assimiler ce lien à tout
    # l’historique.
    def activate(self, publication_id, published_at):
        # On récupère une seule ligne du résultat SQL ; les contrôles suivants vérifient les valeurs
        # attendues.
        existing = self.connection.execute("""
            SELECT c.publication_id, p.published_at
            FROM core.excel_current_publication c
            JOIN core.excel_publications p ON p.publication_id = c.publication_id
            WHERE c.singleton = true FOR UPDATE OF c
        """).fetchone()
        # Aucun lot n’est encore déclaré courant : on crée le premier lien, sans devoir remplacer
        # une publication précédente.
        if existing is None:
            # On insère les données avec des paramètres SQL séparés du texte de la requête ; les
            # contrôles de doublons restent définis par le repository et les contraintes.
            self.connection.execute(
                "INSERT INTO core.excel_current_publication (singleton, publication_id) VALUES (true, %s)",
                (publication_id,),
            )
            # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
            return "activated"
        # On vérifie ce cas avant la suite : existing[0] correspond à l’identifiant de la publication
        # Excel.
        if existing[0] == publication_id:
            # Ne pas modifier la date d'activation lors d'une relance identique.
            return "unchanged"
        # On exige ici que la date de publication est supérieur à existing[1]. Si ce n’est pas le cas,
        # le message associé bloque la suite.
        require(
            published_at > existing[1],
            "Refus de remplacer la publication courante par une publication plus ancienne ou de date ambigue.",
        )
        # On envoie cette requête à self.connection avec ses paramètres ; son résultat sera contrôlé
        # séparément.
        self.connection.execute(
            """UPDATE core.excel_current_publication
            SET publication_id = %s, activated_in_database_at = CURRENT_TIMESTAMP
            WHERE singleton = true""",
            (publication_id,),
        )
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "activated"


# On charge le lot préparé au moyen du dépôt fourni ; ce n’est pas une nouvelle lecture des sources.
def import_bundle(bundle, repository):
    """Un seul commit apres tous les controles ; toute exception entraine un rollback."""
    # On reprend les métadonnées de la publication dans bundle ; cet accès suppose que la clé a été
    # produite ou vérifiée auparavant.
    publication = bundle["publication"]
    # On récupère bundle['run'] et on le garde dans run pour la suite.
    run = bundle["run"]
    # On reprend la liste des fichiers déclarés par le lot dans bundle ; cet accès suppose que la
    # clé a été produite ou vérifiée auparavant.
    files = bundle["files"]
    # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre pas tout
    # le workflow.
    with repository.transaction():
        # On recontrôle que le lot préparé est encore celui attendu ; on ne relance pas l’ingestion
        # pour le remplacer en silence.
        check_still_current(bundle)
        # On traite séparément chaque version de domaine contenue dans cette publication, pour
        # garder son identifiant et ses lignes rattachés au bon lot.
        for version in bundle["versions"]:
            # On récupère version['entry'] et on le garde dans entry pour la suite.
            entry = version["entry"]
            # On conserve cet enregistrement dans core.vineyards. Si sa clé existe déjà, le
            # repository doit retrouver le même contenu : on n’écrit pas par-dessus une version
            # historique différente.
            repository.put_immutable(
                "core.vineyards",
                {
                    # On renseigne la clé du domaine sous la clé 'vineyard_key'.
                    "vineyard_key": version["key"],
                    # On renseigne le nom du domaine sous la clé 'vineyard_name'.
                    "vineyard_name": entry["vineyard"],
                    # On renseigne le nom technique de rangement sous la clé 'storage_key'.
                    "storage_key": "v_"
                    + sha256(entry["vineyard"].casefold().encode("utf-8"))[:10],
                },
            )
        # On conserve cet enregistrement dans core.excel_ingestion_runs. Si sa clé existe déjà, le
        # repository doit retrouver le même contenu : on n’écrit pas par-dessus une version
        # historique différente.
        new_run = repository.put_immutable(
            "core.excel_ingestion_runs",
            {
                # On renseigne l’identifiant d’exécution sous la clé 'execution_id'.
                "execution_id": run["execution_id"],
                # On renseigne la date de début sous la clé 'started_at'.
                "started_at": timestamp(run["started_at"]),
                # On renseigne la date de fin sous la clé 'finished_at'.
                "finished_at": timestamp(run["finished_at"]),
                # On renseigne l’état du traitement sous la clé 'status'.
                "status": run["status"],
                # On renseigne le marqueur d’initialisation sous la clé 'initialization'.
                "initialization": run["initialization"],
                # On renseigne les éléments d’identité du lot sous la clé 'identity'.
                "identity": run["identity"],
                # On renseigne le chemin du manifeste sous la clé 'manifest_path'.
                "manifest_path": bundle["run_path"],
                # On renseigne l’empreinte du manifeste sous la clé 'manifest_sha256'.
                "manifest_sha256": sha256(files.read(bundle["run_path"])),
                # On renseigne le contenu du manifeste sous la clé 'manifest_payload'.
                "manifest_payload": run,
            },
        )
        # On parcourt bundle['versions'] ; version désigne l’élément courant à chaque passage dans la
        # boucle.
        for version in bundle["versions"]:
            # On distribue ces valeurs entre key, entry, manifest, dans l’ordre de l’affectation.
            # Chaque nom reçoit son propre élément.
            key, entry, manifest = version["key"], version["entry"], version["manifest"]
            # On conserve cet enregistrement dans core.excel_versions. Si sa clé existe déjà, le
            # repository doit retrouver le même contenu : on n’écrit pas par-dessus une version
            # historique différente.
            new_version = repository.put_immutable(
                "core.excel_versions",
                {
                    # On renseigne la clé du domaine sous la clé 'vineyard_key'.
                    "vineyard_key": key,
                    # On renseigne l’identifiant de version sous la clé 'version_id'.
                    "version_id": entry["version_id"],
                    # On renseigne la date d’ingestion sous la clé 'ingested_at'.
                    "ingested_at": timestamp(entry["ingested_at"]),
                    # On renseigne le nom du fichier source sous la clé 'source_filename'.
                    "source_filename": entry["source_filename"],
                    # On renseigne l’empreinte du fichier source sous la clé 'source_sha256'.
                    "source_sha256": entry["source_sha256"],
                    # On renseigne la date de modification de la source sous la clé
                    # 'source_modified_at'.
                    "source_modified_at": timestamp(manifest["source_modified_at"]),
                    # On renseigne le chemin de la copie archivée sous la clé 'archive_path'.
                    "archive_path": manifest["artifacts"]["source"]["path"],
                    # On renseigne les éléments d’identité du lot sous la clé 'identity'.
                    "identity": entry["identity"],
                    # On associe la clé 'version_manifest_path' à cette valeur dans cet objet.
                    "version_manifest_path": entry["manifest"],
                    # On associe la clé 'version_manifest_sha256' à cette valeur dans cet objet.
                    "version_manifest_sha256": entry["manifest_sha256"],
                    # On renseigne le chemin du tableau normalisé sous la clé 'normalized_path'.
                    "normalized_path": entry["normalized_path"],
                    # On renseigne l’empreinte du tableau normalisé sous la clé 'normalized_sha256'.
                    "normalized_sha256": manifest["artifacts"]["normalized"]["sha256"],
                    # On renseigne le nombre de lignes normalisées sous la clé 'normalized_rows'.
                    "normalized_rows": entry["normalized_rows"],
                    # On renseigne le nombre d’acquisitions distinctes sous la clé
                    # 'logical_acquisitions'.
                    "logical_acquisitions": entry["logical_acquisitions"],
                    # On renseigne le nombre de lignes rejetées sous la clé 'rejected_rows'.
                    "rejected_rows": entry["rejected_rows"],
                    # On renseigne les métadonnées détaillées sous la clé 'metadata_payload'.
                    "metadata_payload": manifest,
                },
            )
            # On prépare records comme liste vide ; on la remplira au fil des opérations suivantes.
            records = []
            # On parcourt ['normalized', 'rejected'] ; kind désigne l’élément courant à chaque passage
            # dans la boucle.
            for kind in ["normalized", "rejected"]:
                # On ajoute les éléments de ({'vineyard_key': key, 'version_id': entry['version_id'],
                # 'row_kind': kind, 'row_ord… à records ; on n’ajoute pas la collection comme un seul
                # élément imbriqué.
                records.extend(
                    {
                        # On renseigne la clé du domaine sous la clé 'vineyard_key'.
                        "vineyard_key": key,
                        # On renseigne l’identifiant de version sous la clé 'version_id'.
                        "version_id": entry["version_id"],
                        # On renseigne la nature de la ligne, normalisée ou rejetée sous la clé
                        # 'row_kind'.
                        "row_kind": kind,
                        # On renseigne la position de la ligne dans le lot sous la clé 'row_ordinal'.
                        "row_ordinal": ordinal,
                        # On renseigne le contenu détaillé sous la clé 'payload'.
                        "payload": payload(row),
                    }
                    for ordinal, row in enumerate(version[kind], 1)
                )
            # On conserve les lignes de staging.excel_version_rows avec leur clé de lot et leur
            # position ; lors d’un nouvel import du même lot, leur composition doit rester
            # identique.
            repository.put_rows(
                "staging.excel_version_rows",
                {"vineyard_key": key, "version_id": entry["version_id"]},
                ("vineyard_key", "version_id", "row_kind", "row_ordinal"),
                records,
                # On indique si le lot parent vient d’être créé, pour adapter les vérifications de ses
                # lignes historiques.
                new_parent=new_version,
            )
        # On prépare run_members comme liste vide ; on la remplira au fil des opérations suivantes.
        run_members = []
        # On parcourt les domaines sélectionnés dans run ; item désigne l’élément courant à chaque
        # passage dans la boucle.
        for item in run["vineyards"]:
            # On regroupe dans record ces champs nommés ; on pourra les retrouver par leur clé plutôt
            # que par leur position.
            record = {
                # On renseigne l’identifiant d’exécution sous la clé 'execution_id'.
                "execution_id": run["execution_id"],
                # On renseigne la clé du domaine sous la clé 'vineyard_key'.
                "vineyard_key": item["vineyard"].casefold(),
                # On renseigne la date du contrôle sous la clé 'checked_at'.
                "checked_at": timestamp(item["checked_at"]),
                # On renseigne l’état du traitement sous la clé 'status'.
                "status": item["status"],
                # On renseigne l’identifiant de version sous la clé 'version_id'.
                "version_id": item["version_id"],
                # On associe la clé 'result_payload' à cette valeur dans cet objet.
                "result_payload": item,
            }
            # On conserve cet enregistrement dans core.excel_ingestion_run_vineyards. Si sa clé
            # existe déjà, le repository doit retrouver le même contenu : on n’écrit pas par-dessus
            # une version historique différente.
            new_member = repository.put_immutable(
                "core.excel_ingestion_run_vineyards", record
            )
            # On exige ici que new_run est évalué comme vrai ou la condition new_member n’est pas
            # remplie. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                new_run or not new_member,
                "Execution historique incomplete : import annule.",
            )
            # On ajoute record à la fin de run_members ; les éléments précédents restent conservés.
            run_members.append(record)
        # On vérifie les membres de core.excel_ingestion_run_vineyards pour ce lot, y compris leur
        # nombre. Des lignes déjà présentes mais incomplètes ne doivent pas être acceptées comme un
        # import réussi.
        repository.verify_members(
            "core.excel_ingestion_run_vineyards",
            {"execution_id": run["execution_id"]},
            run_members,
        )
        # On conserve cet enregistrement dans core.excel_publications. Si sa clé existe déjà, le
        # repository doit retrouver le même contenu : on n’écrit pas par-dessus une version
        # historique différente.
        new_publication = repository.put_immutable(
            "core.excel_publications",
            {
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": publication["publication_id"],
                # On associe la clé 'ingestion_execution_id' à cette valeur dans cet objet.
                "ingestion_execution_id": run["execution_id"],
                # On renseigne la date de publication sous la clé 'published_at'.
                "published_at": timestamp(publication["published_at"]),
                # On renseigne le chemin du tableau Excel regroupé sous la clé 'reference_path'.
                "reference_path": publication["reference"]["path"],
                # On renseigne l’empreinte du tableau Excel regroupé sous la clé 'reference_sha256'.
                "reference_sha256": publication["reference"]["sha256"],
                # On renseigne le nombre de lignes du tableau regroupé sous la clé 'reference_rows'.
                "reference_rows": publication["reference"]["rows"],
                # On renseigne le chemin du manifeste sous la clé 'manifest_path'.
                "manifest_path": bundle["publication_path"],
                # On renseigne l’empreinte du manifeste sous la clé 'manifest_sha256'.
                "manifest_sha256": sha256(files.read(bundle["publication_path"])),
                # On renseigne le contenu du manifeste sous la clé 'manifest_payload'.
                "manifest_payload": publication,
            },
        )
        # On prépare publication_members comme liste vide ; on la remplira au fil des opérations
        # suivantes.
        publication_members = []
        # On parcourt bundle['versions'] ; version désigne l’élément courant à chaque passage dans la
        # boucle.
        for version in bundle["versions"]:
            # On regroupe dans record ces champs nommés ; on pourra les retrouver par leur clé plutôt
            # que par leur position.
            record = {
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": publication["publication_id"],
                # On renseigne la clé du domaine sous la clé 'vineyard_key'.
                "vineyard_key": version["key"],
                # On renseigne l’identifiant de version sous la clé 'version_id'.
                "version_id": version["entry"]["version_id"],
            }
            # On conserve cet enregistrement dans core.excel_publication_versions. Si sa clé existe
            # déjà, le repository doit retrouver le même contenu : on n’écrit pas par-dessus une
            # version historique différente.
            new_member = repository.put_immutable(
                "core.excel_publication_versions", record
            )
            # On exige ici que new_publication est évalué comme vrai ou la condition new_member n’est
            # pas remplie. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                new_publication or not new_member,
                "Composition historique incomplete : import annule.",
            )
            # On ajoute record à la fin de publication_members ; les éléments précédents restent
            # conservés.
            publication_members.append(record)
        # On vérifie les membres de core.excel_publication_versions pour ce lot, y compris leur
        # nombre. Des lignes déjà présentes mais incomplètes ne doivent pas être acceptées comme un
        # import réussi.
        repository.verify_members(
            "core.excel_publication_versions",
            {"publication_id": publication["publication_id"]},
            publication_members,
        )
        # On construit records comme une liste à partir de {'publication_id':
        # publication['publication_id'], 'row_ordinal':…, pour chaque (ordinal, row) de
        # enumerate(bundle['reference_rows'], 1).
        records = [
            {
                # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
                "publication_id": publication["publication_id"],
                # On renseigne la position de la ligne dans le lot sous la clé 'row_ordinal'.
                "row_ordinal": ordinal,
                # On renseigne la clé du domaine sous la clé 'vineyard_key'.
                "vineyard_key": row["Vineyard"].casefold(),
                # On renseigne l’identifiant de version sous la clé 'version_id'.
                "version_id": row["excel_reference_version_id"],
                # On renseigne le contenu détaillé sous la clé 'payload'.
                "payload": payload(row),
            }
            for ordinal, row in enumerate(bundle["reference_rows"], 1)
        ]
        # On conserve les lignes de staging.excel_publication_rows avec leur clé de lot et leur
        # position ; lors d’un nouvel import du même lot, leur composition doit rester identique.
        repository.put_rows(
            "staging.excel_publication_rows",
            {"publication_id": publication["publication_id"]},
            ("publication_id", "row_ordinal", "vineyard_key", "version_id"),
            records,
            # On indique si le lot parent vient d’être créé, pour adapter les vérifications de ses
            # lignes historiques.
            new_parent=new_publication,
        )
        # Activer seulement apres tous les imports/controles. Le pointeur et les lignes
        # sont valides ensemble par le meme commit ; aucun etat partiel n'est publie.
        activation = repository.activate(
            publication["publication_id"], timestamp(publication["published_at"])
        )
        # On appelle check_still_current avec bundle.
        check_still_current(bundle)
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
        "publication_id": publication["publication_id"],
        # On associe la clé 'activation' à cette valeur dans cet objet.
        "activation": activation,
        # On associe la clé 'inserted' à cette valeur dans cet objet.
        "inserted": dict(repository.inserted),
        # On associe la clé 'reused' à cette valeur dans cet objet.
        "reused": dict(repository.reused),
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
        description="Import Excel versionne local, sans acces NAS."
    )
    # On déclare des options incompatibles entre elles : le parseur rejettera leur emploi simultané
    # avant le traitement.
    modes = parser.add_mutually_exclusive_group(required=True)
    # Option --check-only : Controle uniquement ; aucune connexion PostgreSQL. Sa déclaration ne
    # déclenche pas l’action.
    modes.add_argument(
        "--check-only",
        action="store_true",
        help="Controle uniquement ; aucune connexion PostgreSQL.",
    )
    # Option --load : Controle puis ecriture transactionnelle et activation de la publication
    # courante. Sa déclaration ne déclenche pas l’action.
    modes.add_argument(
        "--load",
        action="store_true",
        help="Controle puis ecriture transactionnelle et activation de la publication courante.",
    )
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On récupère les options de chargement Excel ; la branche choisie déterminera si la connexion
    # est seulement contrôlée ou si le lot est importé.
    args = parser.parse_args(argv)
    # On initialise password à None : aucune valeur n’a encore été retenue ici.
    password = None
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On prépare en mémoire le lot et ses contrôles à partir des sorties locales ; le chargement
        # PostgreSQL n’est pas effectué par cette seule préparation.
        bundle = prepare_bundle(args.project_root)
        # On récupère le bilan dans bundle et on le garde dans report pour la suite.
        report = bundle["report"]
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"Controle OK : {report['publication_id']} | {len(report['vineyards'])} vignobles | {report['rows']} lignes | {report['logical_acquisitions']} acquisitions logiques | {report['rejected_rows']} rejets"
        )
        # Cette branche traite le cas où le test args.check_only est satisfait.
        if args.check_only:
            # On affiche ce texte explicite dans la sortie du programme.
            print("PostgreSQL : aucune connexion, aucune ecriture. NAS : aucun acces.")
            # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
            # retour.
            return 0
        # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas
        # de connexion.
        import psycopg

        # On garde dans config les paramètres du compte PostgreSQL prévus par ce module.
        config = database_config(args.project_root)
        # On récupère config['password'] et on le garde dans password pour la suite.
        password = config["password"]
        # On utilise psycopg.connect(**config) dans son contexte de gestion ; les opérations de sortie
        # sont exécutées en quittant le bloc.
        with psycopg.connect(**config) as connection:
            # On garde dans actual une ligne du résultat de la requête, ou None si elle n’en renvoie
            # aucune.
            actual = connection.execute(
                "SELECT current_database(), current_user, session_user"
            ).fetchone()
            # On annule les écritures non validées dans cette transaction, sans prétendre annuler les
            # opérations déjà commises ailleurs.
            connection.rollback()  # Fermer la transaction de lecture avant la transaction d'import.
            # On appelle verify_import_identity avec actual.
            verify_import_identity(actual)
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Connexion de chargement : compte=projet12_importer | base=suivi_acquisitions"
            )
            # On garde dans result la valeur renvoyée par import_bundle.
            result = import_bundle(bundle, PostgresRepository(connection))
        # On affiche 'CHARGEMENT VALIDE : ' + result['publication_id'] dans la sortie du programme.
        print("CHARGEMENT VALIDE : " + result["publication_id"])
        # On parcourt sorted(set(result['inserted']) | set(result['reused'])) ; table désigne l’élément
        # courant à chaque passage dans la boucle.
        for table in sorted(set(result["inserted"]) | set(result["reused"])):
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"{table} : {result['inserted'].get(table, 0)} nouveaux enregistrements | {result['reused'].get(table, 0)} deja presents et verifies"
            )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Publication courante : "
            + ("activee" if result["activation"] == "activated" else "inchangee")
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print("Archives et registre local : aucune modification. NAS : aucun acces.")
        # On affiche le texte 'Les classifications Excel sont conservees.' dans la sortie du programme.
        print("Les classifications Excel sont conservees.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Cette commande traite uniquement la publication Excel : aucun chargement NAS ni recalcul des rapprochements."
        )
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as exc:
        # On garde dans message la représentation textuelle de exc.
        message = str(exc)
        # Cette branche traite le cas où password est évalué comme vrai.
        if password:
            # On garde dans message le résultat du remplacement demandé sur message.
            message = message.replace(password, "[secret masque]")
        # On affiche 'IMPORT BLOQUE : ' + message dans la sortie du programme.
        print("IMPORT BLOQUE : " + message, file=sys.stderr)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Le programme ne confirme pas de chargement valide. Une erreur avant COMMIT annule la transaction.",
            file=sys.stderr,
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Si la connexion a ete perdue pendant COMMIT, verifier la base avant de conclure ; une relance controle les identifiants existants.",
            file=sys.stderr,
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print(
            "Aucun historique n est supprime ou repare automatiquement.",
            file=sys.stderr,
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
