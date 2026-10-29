# Lecture du fichier — Essais des importeurs dans un serveur Docker explicitement réservé aux tests.
# Les identifiants présents ici sont fictifs. Les contrôles d’identité évitent de confondre ce
# serveur de test avec une base métier ; ne pas contourner ces vérifications.
#

"""Sept essais d'import dans un serveur Docker dedie ; aucun .env ou reseau metier."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe uuid. Ce module sera utilisé par les opérations de ce fichier.
import uuid

# On rend disponibles build_bundles depuis synthetic_import_fixtures, pour les appels de ce fichier.
from synthetic_import_fixtures import build_bundles
# On rend disponibles IMPORT_TABLES, PREFIX, guard_test_database, run_checks, require depuis
# test_importer_postgres_integration, pour les appels de ce fichier.
from test_importer_postgres_integration import (
    IMPORT_TABLES,
    PREFIX,
    guard_test_database,
    run_checks,
    require,
)

# On fixe HOST à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
HOST = "import-test-postgres"
# On fixe ADMIN à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
ADMIN = "projet12_import_test_admin"
# Identifiants FICTIFS, publics, reserves au serveur de test sans port publie.
ADMIN_PASSWORD = "synthetic-import-tests-admin-only"
# On fixe IMPORT_PASSWORD à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
IMPORT_PASSWORD = "synthetic-import-tests-writer-only"
# On fixe MARKER à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
MARKER = "project12-import-tests-only-v1"
# On rassemble dans SQL_FILES les 2 éléments explicitement indiqués, en conservant leur structure.
SQL_FILES = (
    "002_create_excel_history.sql",
    "004_create_nas_reconciliation_history.sql",
)


def make_test_configs():
    # On exige ici que os.environ.get('PROJECT12_IMPORT_TEST_ISOLATED') correspond au texte '1'. Si
    # ce n’est pas le cas, le message associé bloque la suite.
    require(
        os.environ.get("PROJECT12_IMPORT_TEST_ISOLATED") == "1",
        "Lancement reserve au service Docker de test isole ; aucune connexion tentee.",
    )
    # On regroupe dans common ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    common = {"host": HOST, "port": 5432, "connect_timeout": 5}
    # On garde dans admin un nouveau dictionnaire construit avec les valeurs indiquées (la copie reste
    # superficielle).
    admin = dict(common, dbname="postgres", user=ADMIN, password=ADMIN_PASSWORD)
    # On garde dans importer un nouveau dictionnaire construit avec les valeurs indiquées (la copie
    # reste superficielle).
    importer = dict(common, user="projet12_importer", password=IMPORT_PASSWORD)
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return admin, importer


def load_schema_sources(root):
    # On prépare sources comme liste vide ; on la remplira au fil des opérations suivantes.
    sources = []
    # On prépare tables comme liste vide ; on la remplira au fil des opérations suivantes.
    tables = []
    # On parcourt SQL_FILES ; filename désigne l’élément courant à chaque passage dans la boucle.
    for filename in SQL_FILES:
        # On construit path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
        # ni dossier ni fichier.
        path = Path(root) / "sql" / filename
        # On exige ici que le chemin de travail désigne un fichier. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(path.is_file(), "Migration de test absente : " + filename)
        # On lit le fichier comme du texte avec l’encodage indiqué ; ce n’est pas encore une
        # validation de son contenu métier.
        source = path.read_text(encoding="utf-8-sig")
        # On ajoute les éléments de
        # re.findall('CREATE\\s+TABLE\\s+IF\\s+NOT\\s+EXISTS\\s+((?:core|staging)\\.[a-z_]+)',… à
        # tables ; on n’ajoute pas la collection comme un seul élément imbriqué.
        tables.extend(
            re.findall(
                r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+((?:core|staging)\.[a-z_]+)",
                source,
                re.IGNORECASE,
            )
        )
        # On ajoute source à la fin de sources ; les éléments précédents restent conservés.
        sources.append(source)
    # On vérifie l’unicité avant de constituer le résultat ; écraser une entrée dupliquée ferait
    # disparaître une incohérence de la source.
    require(
        len(tables) == len(IMPORT_TABLES) and set(tables) == set(IMPORT_TABLES),
        "Les deux migrations ne correspondent pas exactement aux 20 tables d import ; arreter avant creation.",
    )
    # On remet les champs à l’origine du constat à l’appelant ; les étapes suivantes de cette fonction
    # ne sont plus parcourues.
    return sources


def verify_management_identity(connection):
    # On exige ici que connection.execute('SELECT current_database(),current_user,session_user')…
    # correspond à ('postgres', ADMIN, ADMIN). Si ce n’est pas le cas, le message associé bloque la
    # suite.
    require(
        connection.execute(
            "SELECT current_database(),current_user,session_user"
        ).fetchone()
        == ("postgres", ADMIN, ADMIN),
        "Identite administrative du serveur de test incorrecte.",
    )
    # On recontrôle les métadonnées du fichier ; un changement pendant la lecture rendrait le lot
    # difficile à rattacher à une version précise.
    require(
        connection.execute(
            "SELECT marker FROM public.project12_import_test_environment"
        ).fetchall()
        == [(MARKER,)],
        "Marqueur du serveur de test absent ou incorrect : creation refusee.",
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
    parser = argparse.ArgumentParser(description=__doc__)
    # Option --run : Autoriser les essais synthetiques sur le serveur Docker dedie. Sa déclaration
    # ne déclenche pas l’action.
    parser.add_argument(
        "--run",
        action="store_true",
        required=True,
        help="Autoriser les essais synthetiques sur le serveur Docker dedie.",
    )
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On lit les options des essais importeurs isolés ; les vérifications de base et de compte de
    # test restent obligatoires avant leurs écritures.
    args = parser.parse_args(argv)
    # On prépare fixtures comme liste vide ; on la remplira au fil des opérations suivantes.
    fixtures = []
    # On initialise created à False ; les branches suivantes pourront modifier cet état.
    created = False
    # On initialise name à None : aucune valeur n’a encore été retenue ici.
    name = None
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On répartit les valeurs renvoyées par make_test_configs entre (admin, importer) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        admin, importer = make_test_configs()
        # On garde dans root le chemin absolu résolu de args.project_root, en tenant compte des liens
        # symboliques.
        root = args.project_root.resolve()
        # On garde dans sources la valeur renvoyée par load_schema_sources.
        sources = load_schema_sources(root)
        # On construit des lots synthétiques pour les essais ; ils ne proviennent pas des données de
        # l’entreprise.
        fixtures, bundles = build_bundles(root)
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

        # On utilise psycopg.connect(**admin, autocommit=True) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(**admin, autocommit=True) as management:
            # On appelle verify_management_identity avec management.
            verify_management_identity(management)
            # On garde dans roles toutes les lignes encore disponibles dans le résultat SQL.
            roles = management.execute(
                "SELECT rolname FROM pg_roles WHERE rolname IN ('projet12_importer','projet12_import_writer')"
            ).fetchall()
            # On exige ici que len(roles) correspond à 2. Si ce n’est pas le cas, le message associé
            # bloque la suite.
            require(len(roles) == 2, "Roles du serveur de test absents.")
            # On envoie cette requête à management avec ses paramètres ; son résultat sera contrôlé
            # séparément.
            management.execute(
                sql.SQL("CREATE DATABASE {} WITH TEMPLATE template0 OWNER {}").format(
                    sql.Identifier(name), sql.Identifier(ADMIN)
                )
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
        # On affiche 'Serveur Docker de test confirme ; base neuve : ' + name dans la sortie du
        # programme.
        print("Serveur Docker de test confirme ; base neuve : " + name)
        # On utilise psycopg.connect(**dict(admin, dbname=name), autocommit=True) dans son contexte de
        # gestion ; les opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(**dict(admin, dbname=name), autocommit=True) as connection:
            # On exige ici que connection.execute('SELECT
            # current_database(),current_user,session_user')… correspond à (guard_test_database(name),
            # ADMIN, ADMIN). Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                connection.execute(
                    "SELECT current_database(),current_user,session_user"
                ).fetchone()
                == (guard_test_database(name), ADMIN, ADMIN),
                "Destination de preparation incorrecte.",
            )
            # On parcourt ('core', 'staging') ; schema désigne l’élément courant à chaque passage dans
            # la boucle.
            for schema in ("core", "staging"):
                # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                connection.execute(
                    sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                        sql.Identifier(schema), sql.Identifier(ADMIN)
                    )
                )
            # On parcourt les champs à l’origine du constat ; source désigne l’élément courant à chaque
            # passage dans la boucle.
            for source in sources:
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
            # On insère les données avec des paramètres SQL séparés du texte de la requête ; les
            # contrôles de doublons restent définis par le repository et les contraintes.
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
        # On utilise psycopg.connect(**dict(importer, dbname=guard_test_database(name)),
        # autocommit=True) dans son contexte de gestion ; les opérations de sortie sont exécutées en
        # quittant le bloc.
        with psycopg.connect(
            # On choisit ici si les instructions sont validées automatiquement hors d’un bloc
            # transactionnel explicite.
            **dict(importer, dbname=guard_test_database(name)), autocommit=True
        ) as connection:
            # On exige ici que connection.execute('SELECT
            # current_database(),current_user,session_user')… correspond à (name, 'projet12_importer',
            # 'projet12_importer'). Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                connection.execute(
                    "SELECT current_database(),current_user,session_user"
                ).fetchone()
                == (name, "projet12_importer", "projet12_importer"),
                "Identite importeur de test incorrecte.",
            )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Compte des essais : projet12_importer ; fichiers exclusivement synthetiques."
            )
            # On appelle run_checks avec connection.
            run_checks(connection, bundles)
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT : OK — 7 controles PostgreSQL reels reussis dans le serveur Docker isole."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Base metier et metadonnees Airflow : aucune connexion. NAS : aucun acces."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print("Base de test conservee : " + name + " ; aucune suppression automatique.")
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as exc:
        # On garde dans message le résultat du remplacement demandé sur
        # str(exc).replace(ADMIN_PASSWORD, '[identifiant de test masque]').
        message = (
            str(exc)
            .replace(ADMIN_PASSWORD, "[identifiant de test masque]")
            .replace(IMPORT_PASSWORD, "[identifiant de test masque]")
        )
        # On affiche 'ESSAI NON CONFIRME : ' + message dans la sortie du programme.
        print("ESSAI NON CONFIRME : " + message, file=sys.stderr)
        # Cette branche traite le cas où created est évalué comme vrai.
        if created:
            # On affiche 'Base de test conservee pour diagnostic : ' + name dans la sortie du
            # programme.
            print("Base de test conservee pour diagnostic : " + name, file=sys.stderr)
        # On affiche ce texte explicite dans la sortie du programme.
        print(
            "Arreter sans elargir les droits ; ne pas supprimer les volumes.",
            file=sys.stderr,
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    finally:
        # On parcourt reversed(fixtures) ; fixture désigne l’élément courant à chaque passage dans la
        # boucle.
        for fixture in reversed(fixtures):
            # On appelle fixture.doCleanups sans argument positionnel.
            fixture.doCleanups()


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
