# Lecture du fichier — Contrôles d’intégration des importeurs sur une base réservée aux tests.
# On vérifie l’identité cible avant les opérations SQL. Ces essais peuvent écrire dans cette base de
# test ; ils ne doivent pas viser une base professionnelle.
#

"""Essai PostgreSQL reel sur base neuve isolee, avec fichiers synthetiques uniquement."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe uuid. Ce module sera utilisé par les opérations de ce fichier.
import uuid
# On rend disponibles database_config depuis import_connection_config, pour les appels de ce fichier.
from import_connection_config import database_config
# On rend disponibles build_bundles depuis synthetic_import_fixtures, pour les appels de ce fichier.
from synthetic_import_fixtures import build_bundles

# On fixe PREFIX à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
PREFIX = "suivi_acquisitions_import_test_"
# Tables propres aux imports Excel/NAS : ne pas utiliser la liste du controle general.
IMPORT_TABLES = (
    "core.vineyards",
    "core.excel_ingestion_runs",
    "core.excel_versions",
    "core.excel_ingestion_run_vineyards",
    "core.excel_publications",
    "core.excel_publication_versions",
    "staging.excel_version_rows",
    "staging.excel_publication_rows",
    "core.excel_current_publication",
    "core.pipeline_runs",
    "core.nas_observation_runs",
    "core.reconciliation_runs",
    "core.pipeline_artifacts",
    "staging.nas_acquisition_observations",
    "staging.nas_passage_observations",
    "staging.nas_association_observations",
    "staging.reconciliation_acquisition_rows",
    "staging.reconciliation_passage_rows",
    "staging.reconciliation_association_rows",
    "core.current_vineyard_reconciliations",
)
# On rassemble dans POINTERS les 2 éléments explicitement indiqués pour ce cas d’essai.
POINTERS = {"core.excel_current_publication", "core.current_vineyard_reconciliations"}


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(condition, message):
    # On prévoit le cas où condition est évalué comme faux, par exemple une valeur vide selon son type.
    if not condition:
        # On interrompt cette branche avec ValueError.
        raise ValueError(message)


# On refuse une cible qui ne présente pas l’identité attendue pour la base de test.
def guard_test_database(name):
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        isinstance(name, str)
        # On exige aussi que le nom en cours commence par PREFIX.
        and name.startswith(PREFIX)
        # On exige aussi que len(name) ne dépasse pas 63.
        and len(name) <= 63
        and name[len(PREFIX) :]
        # On exige aussi que tous les éléments satisfont le test indiqué.
        and all(c.isalnum() or c == "_" for c in name),
        "Nom de base de test non autorise : operation refusee.",
    )
    # On exige ici que le nom en cours diffère du texte 'suivi_acquisitions'. Si ce n’est pas le
    # cas, le message associé bloque la suite.
    require(name != "suivi_acquisitions", "Base principale interdite pour cet essai.")
    # On remet le nom en cours à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return name


# On prend une copie de l’état consulté pour pouvoir la comparer après l’essai.
def snapshot(connection, tables):
    # On rend disponibles sql depuis psycopg, pour les appels de ce fichier.
    from psycopg import sql

    # On crée le dictionnaire vide result pour y ranger ensuite les éléments par clé.
    result = {}
    # On parcourt tables ; table désigne l’élément courant de ce scénario.
    for table in tables:
        # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
        # présenter.
        rows = connection.execute(
            sql.SQL("SELECT row_to_json(t) FROM {} t").format(
                sql.Identifier(*table.split("."))
            )
        ).fetchall()
        # On garde dans result[table] la valeur renvoyée par frozenset.
        result[table] = frozenset(
            json.dumps(
                # On fixe ici l’ordre des clés sérialisées, utile pour obtenir une représentation
                # stable.
                row[0], sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
            for row in rows
        )
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result


# On compare les historiques avant et après l’opération pour détecter une modification inattendue.
def histories_preserved(before, after):
    # Toutes les colonnes ou clés indispensables doivent être présentes ; des champs supplémentaires
    # ne compensent pas l’absence de l’un d’eux.
    require(
        all(before[t].issubset(after[t]) for t in before if t not in POINTERS),
        "Une ligne historique deja chargee a disparu ou change.",
    )


class InjectedFailure(RuntimeError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


def run_checks(connection, bundles):
    # On importe import_excel_publication sous le nom excel. Ce module sera utilisé par les opérations
    # de ce fichier.
    import import_excel_publication as excel
    # On importe load_nas_reconciliation sous le nom nas. Ce module sera utilisé par les opérations de
    # ce fichier.
    import load_nas_reconciliation as nas

    # On répartit les éléments de bundles entre (e1, n1, e2, n2), dans l’ordre indiqué.
    e1, n1, e2, n2 = bundles
    # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        all(not rows for rows in snapshot(connection, IMPORT_TABLES).values()),
        "La base de test doit etre vide.",
    )
    # On garde dans result le bilan du chargement du lot via le repository fourni.
    result = excel.import_bundle(e1, excel.PostgresRepository(connection))
    # On exige ici que sum(result['inserted'].values()) est supérieur à 0 et result['activation']
    # correspond au texte 'activated'. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        sum(result["inserted"].values()) > 0 and result["activation"] == "activated",
        "Premier import Excel non effectue.",
    )
    # On photographie l’état de test avant l’opération afin de pouvoir vérifier ensuite ce qui a
    # changé et ce qui doit rester identique.
    before = snapshot(connection, IMPORT_TABLES)
    # On garde dans repeat le bilan du chargement du lot via le repository fourni.
    repeat = excel.import_bundle(e1, excel.PostgresRepository(connection))
    # On exige ici que sum(repeat['inserted'].values()) correspond à 0 et snapshot(connection,
    # IMPORT_TABLES) correspond à l’état relevé avant l’opération. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        sum(repeat["inserted"].values()) == 0
        # On exige aussi que snapshot(connection, IMPORT_TABLES) correspond à l’état relevé avant
        # l’opération.
        and snapshot(connection, IMPORT_TABLES) == before,
        "Relance Excel non idempotente ou date modifiee.",
    )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 1/7 : insertion Excel et premiere activation ; relance identique sans changement."
    )
    # On garde dans result le bilan du chargement du lot via le repository fourni.
    result = nas.import_bundle(n1, nas.PostgresRepository(connection))
    # On exige ici que sum(result['inserted'].values()) est supérieur à 0 et result['activations']
    # correspond à {'domainedemob': 'active'}. Si ce n’est pas le cas, le message associé bloque la
    # suite.
    require(
        sum(result["inserted"].values()) > 0
        # On exige aussi que result['activations'] correspond à {'domainedemob': 'active'}.
        and result["activations"] == {"domainedemob": "active"},
        "Premier import NAS non effectue.",
    )
    # On garde dans before l’état photographié pour les comparaisons de cet essai.
    before = snapshot(connection, IMPORT_TABLES)
    # On garde dans repeat le bilan du chargement du lot via le repository fourni.
    repeat = nas.import_bundle(n1, nas.PostgresRepository(connection))
    # On exige ici que sum(repeat['inserted'].values()) correspond à 0 et snapshot(connection,
    # IMPORT_TABLES) correspond à l’état relevé avant l’opération. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        sum(repeat["inserted"].values()) == 0
        # On exige aussi que snapshot(connection, IMPORT_TABLES) correspond à l’état relevé avant
        # l’opération.
        and snapshot(connection, IMPORT_TABLES) == before,
        "Relance NAS non idempotente.",
    )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 2/7 : insertion des dix tables NAS/rapprochement et pointeur ; relance inchangee."
    )
    # Meme version Excel, seconde publication synthetique : vrai UPDATE du pointeur.
    before = snapshot(connection, IMPORT_TABLES)
    # On garde dans result le bilan du chargement du lot via le repository fourni.
    result = excel.import_bundle(e2, excel.PostgresRepository(connection))
    # On exige ici que result['activation'] correspond au texte 'activated'. Si ce n’est pas le cas,
    # le message associé bloque la suite.
    require(result["activation"] == "activated", "Deuxieme publication non activee.")
    # On récupère connection.execute('SELECT publication_id FROM core.excel_current_publica… et on le
    # garde dans current pour la suite.
    current = connection.execute(
        "SELECT publication_id FROM core.excel_current_publication"
    ).fetchone()[0]
    # On exige ici que current correspond à l’identifiant de la publication Excel dans
    # e2['publication']. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        current == e2["publication"]["publication_id"], "Pointeur Excel non remplace."
    )
    # On appelle histories_preserved avec before.
    histories_preserved(before, snapshot(connection, IMPORT_TABLES))
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 3/7 : seconde publication Excel activee par UPDATE ; anciens enregistrements conserves."
    )

    # Echec APRES insertion et UPDATE du pointeur, dans la transaction du chargeur.
    class FailingRepository(nas.PostgresRepository):
        # On change le lien courant selon le contrat de ce dépôt ; les anciennes observations restent
        # distinctes.
        def replace_pointer(self, record):
            # On remplace le lien vers le résultat courant à l’intérieur de la transaction ;
            # l’historique de ce qui a été chargé reste séparé de ce pointeur.
            super().replace_pointer(record)
            # On interrompt cette branche avec InjectedFailure : 'Echec synthetique apres activation,
            # avant COMMIT'.
            raise InjectedFailure("Echec synthetique apres activation, avant COMMIT")

    # On garde dans before l’état photographié pour les comparaisons de cet essai.
    before = snapshot(connection, IMPORT_TABLES)
    # On tente ce bloc et on traite séparément les erreurs prévues : InjectedFailure.
    try:
        # On appelle nas.import_bundle avec n2.
        nas.import_bundle(n2, FailingRepository(connection))
    except InjectedFailure:
        # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
        pass
    else:
        # On interrompt cette branche avec ValueError : 'Echec synthetique non declenche.'.
        raise ValueError("Echec synthetique non declenche.")
    # On exige ici que snapshot(connection, IMPORT_TABLES) correspond à l’état relevé avant
    # l’opération. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        snapshot(connection, IMPORT_TABLES) == before,
        "Rollback incomplet apres echec synthetique.",
    )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 4/7 : echec provoque apres UPDATE ; toutes les insertions et le pointeur sont annules."
    )
    # On garde dans result le bilan du chargement du lot via le repository fourni.
    result = nas.import_bundle(n2, nas.PostgresRepository(connection))
    # On exige ici que result['activations'] correspond à {'domainedemob': 'active'}. Si ce n’est pas
    # le cas, le message associé bloque la suite.
    require(
        result["activations"] == {"domainedemob": "active"},
        "Nouveau rapprochement non active.",
    )
    # On récupère connection.execute('SELECT pipeline_execution_id FROM core.current_vineya… et on le
    # garde dans current pour la suite.
    current = connection.execute(
        "SELECT pipeline_execution_id FROM core.current_vineyard_reconciliations"
    ).fetchone()[0]
    # On exige ici que current correspond à l’identifiant du traitement NAS dans n2['report']. Si ce
    # n’est pas le cas, le message associé bloque la suite.
    require(
        current == n2["report"]["pipeline_execution_id"], "Pointeur NAS non remplace."
    )
    # On appelle histories_preserved avec before.
    histories_preserved(before, snapshot(connection, IMPORT_TABLES))
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 5/7 : second rapprochement active par UPDATE ; observations historiques conservees."
    )
    # On garde dans before l’état photographié pour les comparaisons de cet essai.
    before = snapshot(connection, IMPORT_TABLES)
    # On garde dans repeat le bilan du chargement du lot via le repository fourni.
    repeat = nas.import_bundle(n2, nas.PostgresRepository(connection))
    # On exige ici que sum(repeat['inserted'].values()) correspond à 0 et snapshot(connection,
    # IMPORT_TABLES) correspond à l’état relevé avant l’opération. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        sum(repeat["inserted"].values()) == 0
        # On exige aussi que snapshot(connection, IMPORT_TABLES) correspond à l’état relevé avant
        # l’opération.
        and snapshot(connection, IMPORT_TABLES) == before,
        "Derniere relance a modifie les donnees.",
    )
    # On affiche ce texte explicite dans la sortie du programme.
    print("OK 6/7 : relance du nouveau rapprochement sans doublon ni redatation.")
    # WHERE false garantit zero ligne affectee meme si une permission excessive existe.
    import psycopg

    # On parcourt ('UPDATE staging.reconciliation_acquisition_rows SET payload=payload WHER… ; query
    # désigne l’élément courant de ce scénario.
    for query in (
        "UPDATE staging.reconciliation_acquisition_rows SET payload=payload WHERE false",
        "DELETE FROM staging.reconciliation_acquisition_rows WHERE false",
    ):
        # On tente ce bloc et on traite séparément les erreurs prévues :
        # psycopg.errors.InsufficientPrivilege.
        try:
            # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre
            # pas tout le workflow.
            with connection.transaction():
                # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                connection.execute(query)
        except psycopg.errors.InsufficientPrivilege:
            # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
            pass
        else:
            # On interrompt cette branche avec ValueError.
            raise ValueError("Permission historique excessive : " + query.split()[0])
    # On exige ici que snapshot(connection, IMPORT_TABLES) correspond à l’état relevé avant
    # l’opération. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        snapshot(connection, IMPORT_TABLES) == before,
        "Donnees changees pendant les tests de refus.",
    )
    # On affiche cette information de suivi dans la sortie du programme.
    print("OK 7/7 : tentatives UPDATE et DELETE historiques refusees par PostgreSQL.")


def main(argv=None):
    # On parcourt (sys.stdout, sys.stderr) ; stream désigne l’élément courant de ce scénario.
    for stream in (sys.stdout, sys.stderr):
        # Cette branche traite le cas où le contrôle hasattr(stream, 'reconfigure') est positif.
        if hasattr(stream, "reconfigure"):
            # On appelle stream.reconfigure sans argument positionnel.
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # Option --run : Autoriser explicitement la creation de la base de test et les essais
    # synthetiques. Sa déclaration ne déclenche pas l’action.
    parser.add_argument(
        "--run",
        action="store_true",
        required=True,
        help="Autoriser explicitement la creation de la base de test et les essais synthetiques.",
    )
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On lit les options de cette commande ; les branches qui suivent décident s’il faut seulement
    # diagnostiquer ou réellement exécuter le parcours.
    args = parser.parse_args(argv)
    # On prépare fixtures comme liste vide ; on la remplira au fil des opérations suivantes.
    fixtures = []
    # On initialise created à False ; les branches suivantes pourront modifier cet état.
    created = False
    # On initialise name à None : aucune valeur n’a encore été retenue ici.
    name = None
    # On prépare secrets comme liste vide ; on la remplira au fil des opérations suivantes.
    secrets = []
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On garde dans root le chemin absolu résolu de args.project_root, en tenant compte des liens
        # symboliques.
        root = args.project_root.resolve()
        # Preparations locales avant toute creation. Aucun fichier de production lu.
        fixtures, bundles = build_bundles(root)
        # On prépare schema_sources comme liste vide ; on la remplira au fil des opérations suivantes.
        schema_sources = []
        # On parcourt ('002_create_excel_history.sql', '004_create_nas_reconciliation_history.s… ;
        # filename désigne l’élément courant de ce scénario.
        for filename in (
            "002_create_excel_history.sql",
            "004_create_nas_reconciliation_history.sql",
        ):
            # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier
            # n’est créé par cette construction.
            path = root / "sql" / filename
            # On exige ici que le chemin de travail désigne un fichier. Si ce n’est pas le cas, le
            # message associé bloque la suite.
            require(path.is_file(), "SQL prerequisite absent : " + filename)
            # On ajoute path.read_text(encoding='utf-8-sig') à la fin de schema_sources ; les éléments
            # précédents restent conservés.
            schema_sources.append(path.read_text(encoding="utf-8-sig"))
        # On garde dans config les paramètres du compte PostgreSQL prévus par ce module.
        config = database_config(root)
        # On ajoute config['password'] à la fin de secrets ; les éléments précédents restent conservés.
        secrets.append(config["password"])
        # On rend disponibles dotenv_values depuis dotenv, pour les appels de ce fichier.
        from dotenv import dotenv_values

        # On lit les réglages du fichier sans les injecter automatiquement dans l’environnement
        # global ; les secrets ne doivent pas être affichés.
        env = dotenv_values(root / ".env", encoding="utf-8-sig", interpolate=False)
        # On garde dans admin_password le champ 'PROJECT12_POSTGRES_PASSWORD' de env, ou None si la clé
        # est absente.
        admin_password = env.get("PROJECT12_POSTGRES_PASSWORD")
        # On exige ici que admin_password est du type str et le contrôle bool(admin_password) est
        # positif. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            isinstance(admin_password, str) and bool(admin_password),
            "Mot de passe administrateur absent pour creer la base de test.",
        )
        # On ajoute admin_password à la fin de secrets ; les éléments précédents restent conservés.
        secrets.append(admin_password)
        # Avant toute écriture d’essai, on vérifie qu’on vise la base et le compte de test attendus,
        # pas la base métier.
        name = guard_test_database(
            PREFIX
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            + "_"
            + uuid.uuid4().hex[:6]
        )
        # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas
        # de connexion.
        import psycopg
        # On rend disponibles sql depuis psycopg, pour les appels de ce fichier.
        from psycopg import sql

        # Administration via postgres, PAS via la base principale du projet.
        admin = dict(
            host="127.0.0.1",
            port=5433,
            dbname="postgres",
            user="projet12_admin",
            password=admin_password,
            # On limite l’attente de connexion PostgreSQL, sans garantir la durée des requêtes
            # ultérieures.
            connect_timeout=5,
        )
        # On utilise psycopg.connect(**admin, autocommit=True) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(**admin, autocommit=True) as management:
            # On exige ici que management.execute('SELECT
            # current_database(),current_user,session_user')… correspond à ('postgres',
            # 'projet12_admin', 'projet12_admin'). Si ce n’est pas le cas, le message associé bloque la
            # suite.
            require(
                management.execute(
                    "SELECT current_database(),current_user,session_user"
                ).fetchone()
                == ("postgres", "projet12_admin", "projet12_admin"),
                "Connexion administrative inattendue.",
            )
            # On garde dans roles toutes les lignes encore disponibles dans le résultat SQL.
            roles = management.execute(
                "SELECT rolname FROM pg_roles WHERE rolname IN ('projet12_importer','projet12_import_writer')"
            ).fetchall()
            # On exige ici que len(roles) correspond à 2. Si ce n’est pas le cas, le message associé
            # bloque la suite.
            require(len(roles) == 2, "Roles importeurs absents.")
            # On envoie cette requête à management avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            management.execute(
                sql.SQL(
                    "CREATE DATABASE {} WITH TEMPLATE template0 OWNER projet12_admin"
                ).format(sql.Identifier(name))
            )
            # On initialise created à True ; les branches suivantes pourront modifier cet état.
            created = True
            # On envoie cette requête à management avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            management.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(name)
                )
            )
            # On envoie cette requête à management avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            management.execute(
                sql.SQL(
                    "GRANT CONNECT ON DATABASE {} TO projet12_import_writer"
                ).format(sql.Identifier(name))
            )
        # On affiche 'Base de test creee : ' + name dans la sortie du programme.
        print("Base de test creee : " + name)
        # On garde dans setup un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        setup = dict(admin, dbname=name)
        # On utilise psycopg.connect(**setup, autocommit=True) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(**setup, autocommit=True) as connection:
            # On exige ici que connection.execute('SELECT current_database()').fetchone()[0] correspond
            # à guard_test_database(name). Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                connection.execute("SELECT current_database()").fetchone()[0]
                == guard_test_database(name),
                "Base de creation incorrecte.",
            )
            # On parcourt ('core', 'staging') ; schema désigne l’élément courant de ce scénario.
            for schema in ("core", "staging"):
                # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                connection.execute(
                    sql.SQL("CREATE SCHEMA {} AUTHORIZATION projet12_admin").format(
                        sql.Identifier(schema)
                    )
                )
            # On parcourt schema_sources ; source désigne l’élément courant de ce scénario.
            for source in schema_sources:
                # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                connection.execute(source, prepare=False)

            # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            connection.execute(
                "GRANT USAGE ON SCHEMA core,staging TO projet12_import_writer"
            )
            # On garde dans table_list le texte formé en réunissant les éléments avec sql.SQL(',')
            # comme séparateur.
            table_list = sql.SQL(",").join(
                sql.Identifier(*table.split(".")) for table in IMPORT_TABLES
            )
            # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            connection.execute(
                sql.SQL("GRANT SELECT,INSERT ON {} TO projet12_import_writer").format(
                    table_list
                )
            )
            # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            connection.execute(
                "GRANT UPDATE(publication_id,activated_in_database_at) ON core.excel_current_publication TO projet12_import_writer"
            )
            # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            connection.execute(
                "GRANT UPDATE(pipeline_execution_id,reconciliation_run_id,activated_in_database_at) ON core.current_vineyard_reconciliations TO projet12_import_writer"
            )
        # Exception de destination EXPLICITE pour ce test isole ; les CLI normaux
        # conservent leur refus de travailler hors suivi_acquisitions.
        test_config = dict(config, dbname=guard_test_database(name))
        # On utilise psycopg.connect(**test_config, autocommit=True) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(**test_config, autocommit=True) as connection:
            # On garde dans identity une ligne du résultat de la requête, ou None si elle n’en renvoie
            # aucune.
            identity = connection.execute(
                "SELECT current_database(),current_user,session_user"
            ).fetchone()
            # On exige ici que les éléments d’identité du lot correspond à (name, 'projet12_importer',
            # 'projet12_importer'). Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                identity == (name, "projet12_importer", "projet12_importer"),
                "Identite du compte de test incorrecte.",
            )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Compte des essais : projet12_importer ; donnees exclusivement synthetiques."
            )
            # On appelle run_checks avec connection.
            run_checks(connection, bundles)
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT : OK — insertions, activations, relances et rollback PostgreSQL reel verifies dans la base isolee."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Base principale : aucune connexion ni ecriture metier. NAS : aucun acces."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print("Base de test conservee : " + name + " ; aucune suppression automatique.")
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as exc:
        # On garde dans message la représentation textuelle de exc.
        message = str(exc)
        # On parcourt secrets ; secret désigne l’élément courant de ce scénario.
        for secret in secrets:
            # Cette branche traite le cas où secret est évalué comme vrai.
            if secret:
                # On garde dans message le résultat du remplacement demandé sur message.
                message = message.replace(secret, "[secret masque]")
        # On affiche 'TEST NON CONFIRME : ' + message dans la sortie du programme.
        print("TEST NON CONFIRME : " + message, file=sys.stderr)
        # Cette branche traite le cas où created est évalué comme vrai.
        if created:
            # On affiche 'Base de test conservee pour diagnostic : ' + name dans la sortie du
            # programme.
            print("Base de test conservee pour diagnostic : " + name, file=sys.stderr)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Ne pas elargir les permissions pour contourner le blocage. Ne pas supprimer le volume Docker.",
            file=sys.stderr,
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    finally:
        # On parcourt reversed(fixtures) ; fixture désigne l’élément courant de ce scénario.
        for fixture in reversed(fixtures):
            # On appelle fixture.doCleanups sans argument positionnel.
            fixture.doCleanups()


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
