# Lecture du fichier — Contrôles d’intégration du journal métier sur PostgreSQL de test.
# On vérifie les événements et les permissions. Ce journal métier ne remplace pas les métadonnées
# d’exécution conservées par Airflow dans son autre base.
#

"""Essais reels du journal, exclusivement dans une base neuve synthetique."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4
# On rend disponibles append_event, require depuis workflow_journal_repository, pour les appels de ce
# fichier.
from workflow_journal_repository import append_event, require

# On fixe PREFIX à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
PREFIX = "suivi_acquisitions_journal_test_"


# On refuse une cible qui ne présente pas l’identité attendue pour la base de test.
def guard_test_database(name):
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        isinstance(name, str)
        # On exige aussi que le nom en cours commence par PREFIX.
        and name.startswith(PREFIX)
        # On exige aussi que 0 est inférieur à len(name[len(PREFIX):]).
        and 0 < len(name[len(PREFIX) :])
        # On exige aussi que len(name) ne dépasse pas 63.
        and len(name) <= 63
        # On exige aussi que tous les éléments satisfont le test indiqué.
        and all(c in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in name),
        "Nom de base isolee non autorise.",
    )
    # On remet le nom en cours à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return name


def journal_schema(source):
    # On garde dans start la valeur renvoyée par source.find pour 'CREATE TABLE
    # core.workflow_execution_events ('.
    start = source.find("CREATE TABLE core.workflow_execution_events (")
    # On garde dans end la valeur renvoyée par source.rfind pour 'COMMIT;'.
    end = source.rfind("COMMIT;")
    # On exige ici que start est au moins égal à 0 et end est supérieur à start et le texte 'CREATE
    # VIEW mart.workflow_execution_current AS' appartient à la source. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        start >= 0
        # On exige aussi que end est supérieur à start.
        and end > start
        # On exige aussi que le texte 'CREATE VIEW mart.workflow_execution_current AS' appartient à la
        # source.
        and "CREATE VIEW mart.workflow_execution_current AS" in source,
        "SQL 023 attendu absent ou incomplet.",
    )
    # Exact schema/grants/views from reviewed 023, excluding its main-database guard.
    return source[start:end]


def event(run, seq, kind="step", status="started", stage="nas_pipeline"):
    # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
    return dict(
        # On fournit l’identifiant stable de l’événement via le paramètre event_id de cet appel.
        event_id=str(uuid4()),
        # On fournit l’identifiant de l’exécution du workflow via le paramètre workflow_execution_id de
        # cet appel.
        workflow_execution_id=str(run),
        # On fournit le numéro d’ordre de l’événement via le paramètre event_sequence de cet appel.
        event_sequence=seq,
        # On fournit la date de l’événement via le paramètre occurred_at de cet appel.
        occurred_at=datetime.now(timezone.utc).isoformat(),
        # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
        trigger_mode="integration_test",
        event_type=kind,
        # On fournit l’étape concernée via le paramètre stage de cet appel.
        stage=stage,
        # On fournit l’état du traitement via le paramètre status de cet appel.
        status=status,
        # On fournit le périmètre détaillé enregistré via le paramètre scope_payload de cet appel.
        scope_payload={"year": 2026, "vineyards": ["VignobleSynthetique"]},
        # On fournit les indicateurs détaillés enregistrés via le paramètre metrics_payload de cet
        # appel.
        metrics_payload={},
        message="Evenement synthetique sans donnees de production",
    )


def state(c):
    # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
    # présenter.
    return c.execute(
        "SELECT event_id,recorded_in_database_at FROM core.workflow_execution_events ORDER BY workflow_execution_id,event_sequence"
    ).fetchall()


def run_checks(c):
    # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas de
    # connexion.
    import psycopg

    # On crée un nouvel identifiant UUID ; il sert à distinguer cet élément des précédents, pas à
    # numéroter les éléments dans l’ordre.
    run = uuid4()
    # On garde dans first la valeur renvoyée par event.
    first = event(run, 1, "workflow", "started", "workflow")
    # On exige ici que append_event(c, first) correspond au texte 'inserted'. Si ce n’est pas le cas,
    # le message associé bloque la suite.
    require(append_event(c, first) == "inserted", "Insertion initiale non effectuee.")
    # On garde dans original la valeur renvoyée par state.
    original = state(c)
    # On affiche ce texte explicite dans la sortie du programme.
    print("OK 1/8 : premier evenement insere avec le compte importeur.")
    # On exige ici que append_event(c, first) correspond au texte 'reused' et state(c) correspond à
    # original. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        append_event(c, first) == "reused" and state(c) == original,
        "Relance non idempotente ou redatation.",
    )
    # On affiche le texte 'OK 2/8 : relance identique sans doublon ni redatation.' dans la sortie du
    # programme.
    print("OK 2/8 : relance identique sans doublon ni redatation.")
    # On parcourt (dict(first, message='Contenu modifie'), dict(first, event_id=str(uuid4()… ; bad
    # désigne l’élément courant de ce scénario.
    for bad in (
        dict(first, message="Contenu modifie"),
        dict(first, event_id=str(uuid4())),
    ):
        # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
        try:
            # On transmet cette information à append_event pour garder une trace de l’étape et de ses
            # valeurs associées.
            append_event(c, bad)
        except ValueError:
            # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
            pass
        else:
            # On interrompt cette branche avec ValueError : 'Contradiction non rejetee.'.
            raise ValueError("Contradiction non rejetee.")
        # On exige ici que state(c) correspond à original. Si ce n’est pas le cas, le message associé
        # bloque la suite.
        require(state(c) == original, "Une contradiction a modifie le journal.")
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 3/8 : meme identifiant ou meme sequence avec contenu contradictoire refuse."
    )
    # Outer transaction demonstrates complete rollback even after append_event returns.
    try:
        # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre pas
        # tout le workflow.
        with c.transaction():
            # On transmet cette information à append_event pour garder une trace de l’étape et de ses
            # valeurs associées.
            append_event(c, event(uuid4(), 1, "workflow", "started", "workflow"))
            # On interrompt cette branche avec RuntimeError : 'Echec synthetique apres insertion'.
            raise RuntimeError("Echec synthetique apres insertion")
    except RuntimeError:
        # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
        pass
    # On exige ici que state(c) correspond à original. Si ce n’est pas le cas, le message associé
    # bloque la suite.
    require(state(c) == original, "Insertion non annulee par rollback.")
    # On affiche ce texte explicite dans la sortie du programme.
    print("OK 4/8 : insertion annulee apres echec transactionnel provoque.")
    # On parcourt (event(run, 3), dict(event(run, 2), trigger_mode='manual_script'), dict(e… ; bad
    # désigne l’élément courant de ce scénario.
    for bad in (
        event(run, 3),
        dict(event(run, 2), trigger_mode="manual_script"),
        dict(event(run, 2), scope_payload={"year": 2025}),
    ):
        # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
        try:
            # On transmet cette information à append_event pour garder une trace de l’étape et de ses
            # valeurs associées.
            append_event(c, bad)
        except ValueError:
            # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
            pass
        else:
            # On interrompt cette branche avec ValueError : 'Sequence/mode/perimetre incoherent
            # accepte.'.
            raise ValueError("Sequence/mode/perimetre incoherent accepte.")
    # On exige ici que state(c) correspond à original. Si ce n’est pas le cas, le message associé
    # bloque la suite.
    require(state(c) == original, "Refus de coherence non atomique.")
    # On transmet cette information à append_event pour garder une trace de l’étape et de ses valeurs
    # associées.
    append_event(c, event(run, 2, "quality", "success", "nas_bundle_check"))
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 5/8 : coherence sequence/mode/perimetre et ajout d un controle de qualite."
    )
    # On parcourt ('UPDATE core.workflow_execution_events SET message=message WHERE false',… ; query
    # désigne l’élément courant de ce scénario.
    for query in (
        "UPDATE core.workflow_execution_events SET message=message WHERE false",
        "DELETE FROM core.workflow_execution_events WHERE false",
    ):
        # On tente ce bloc et on traite séparément les erreurs prévues :
        # psycopg.errors.InsufficientPrivilege.
        try:
            # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre
            # pas tout le workflow.
            with c.transaction():
                # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                c.execute(query)
        except psycopg.errors.InsufficientPrivilege:
            # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
            pass
        else:
            # On interrompt cette branche avec ValueError : 'Modification historique non refusee par
            # PostgreSQL.'.
            raise ValueError("Modification historique non refusee par PostgreSQL.")
    # On affiche ce texte explicite dans la sortie du programme.
    print("OK 6/8 : UPDATE et DELETE refuses par PostgreSQL au compte importeur.")
    # On remet run à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return run


def main(argv=None):
    # On parcourt (sys.stdout, sys.stderr) ; stream désigne l’élément courant de ce scénario.
    for stream in (sys.stdout, sys.stderr):
        # Cette branche traite le cas où le contrôle hasattr(stream, 'reconfigure') est positif.
        if hasattr(stream, "reconfigure"):
            # On appelle stream.reconfigure sans argument positionnel.
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On appelle parser.add_argument avec '--run'.
    parser.add_argument("--run", action="store_true", required=True)
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On lit les options de cette commande ; les branches qui suivent décident s’il faut seulement
    # diagnostiquer ou réellement exécuter le parcours.
    args = parser.parse_args(argv)
    # On initialise name à None : aucune valeur n’a encore été retenue ici.
    name = None
    # On initialise created à False ; les branches suivantes pourront modifier cet état.
    created = False
    # On prépare secrets comme liste vide ; on la remplira au fil des opérations suivantes.
    secrets = []
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On garde dans root le chemin absolu résolu de args.project_root, en tenant compte des liens
        # symboliques.
        root = args.project_root.resolve()
        # On garde dans ddl la valeur renvoyée par journal_schema.
        ddl = journal_schema(
            (root / "sql/023_create_workflow_execution_journal.sql").read_text(
                # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas
                # être décodé selon un réglage implicite du poste.
                encoding="utf-8-sig"
            )
        )
        # On rend disponibles database_config depuis import_connection_config, pour les appels de ce
        # fichier.
        from import_connection_config import database_config

        # On garde dans config les paramètres du compte PostgreSQL prévus par ce module.
        config = database_config(root)
        # On ajoute config['password'] à la fin de secrets ; les éléments précédents restent conservés.
        secrets.append(config["password"])
        # On rend disponibles dotenv_values depuis dotenv, pour les appels de ce fichier.
        from dotenv import dotenv_values

        # On garde dans env les réglages lus sans modifier automatiquement l’environnement global.
        env = dotenv_values(root / ".env", encoding="utf-8-sig", interpolate=False)
        # On garde dans password le champ 'PROJECT12_POSTGRES_PASSWORD' de env, ou None si la clé est
        # absente.
        password = env.get("PROJECT12_POSTGRES_PASSWORD")
        # On exige ici que password est du type str et le contrôle bool(password) est positif. Si ce
        # n’est pas le cas, le message associé bloque la suite.
        require(
            isinstance(password, str) and bool(password),
            "Mot de passe admin absent du fichier local.",
        )
        # On garde dans dashboard_password le champ 'PROJECT12_DASHBOARD_PASSWORD' de env, ou None si
        # la clé est absente.
        dashboard_password = env.get("PROJECT12_DASHBOARD_PASSWORD")
        # On exige ici que env.get('PROJECT12_DASHBOARD_USER') correspond au texte
        # 'projet12_dashboard' et dashboard_password est du type str et le contrôle
        # bool(dashboard_password) est positif. Si ce n’est pas le cas, le message associé bloque la
        # suite.
        require(
            env.get("PROJECT12_DASHBOARD_USER") == "projet12_dashboard"
            # On exige aussi que dashboard_password est du type str.
            and isinstance(dashboard_password, str)
            # On exige aussi que le contrôle bool(dashboard_password) est positif.
            and bool(dashboard_password),
            "Configuration dashboard dediee absente.",
        )
        # On ajoute les éléments de [password, dashboard_password] à secrets ; on n’ajoute pas la
        # collection comme un seul élément imbriqué.
        secrets.extend([password, dashboard_password])
        # Avant toute écriture d’essai, on vérifie qu’on vise la base et le compte de test attendus,
        # pas la base métier.
        name = guard_test_database(
            PREFIX
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            + "_"
            + uuid4().hex[:6]
        )
        # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas
        # de connexion.
        import psycopg
        # On rend disponibles sql depuis psycopg, pour les appels de ce fichier.
        from psycopg import sql

        # On garde dans admin un nouveau dictionnaire construit avec les valeurs indiquées.
        admin = dict(
            host="127.0.0.1",
            port=5433,
            dbname="postgres",
            user="projet12_admin",
            password=password,
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
                "Identite administrative inattendue.",
            )
            # On garde dans roles toutes les lignes encore disponibles dans le résultat SQL.
            roles = management.execute(
                "SELECT rolname FROM pg_roles WHERE rolname IN ('projet12_importer','projet12_import_writer','projet12_dashboard','projet12_mart_reader')"
            ).fetchall()
            # On exige ici que len(roles) correspond à 4. Si ce n’est pas le cas, le message associé
            # bloque la suite.
            require(len(roles) == 4, "Roles applicatifs absents.")
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
                    "GRANT CONNECT ON DATABASE {} TO projet12_import_writer,projet12_mart_reader"
                ).format(sql.Identifier(name))
            )
        # On affiche 'Base de test creee : ' + name dans la sortie du programme.
        print("Base de test creee : " + name)
        # On utilise psycopg.connect(**dict(admin, dbname=guard_test_database(name)), autocommit=True)
        # dans son contexte de gestion ; les opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(
            # On choisit ici si les instructions sont validées automatiquement hors d’un bloc
            # transactionnel explicite.
            **dict(admin, dbname=guard_test_database(name)), autocommit=True
        ) as setup:
            # On exige ici que setup.execute('SELECT current_database()').fetchone()[0] correspond à le
            # nom en cours. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                setup.execute("SELECT current_database()").fetchone()[0] == name,
                "Base de preparation incorrecte.",
            )
            # On lance l’opération prévue par setup.execute avec les paramètres de ce cas.
            setup.execute(
                "CREATE SCHEMA core AUTHORIZATION projet12_admin; CREATE SCHEMA mart AUTHORIZATION projet12_admin; GRANT USAGE ON SCHEMA mart TO projet12_mart_reader",
                prepare=False,
            )
            # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre
            # pas tout le workflow.
            with setup.transaction():
                # On lance l’opération prévue par setup.execute avec les paramètres de ce cas.
                setup.execute(ddl, prepare=False)
        # On utilise psycopg.connect(**dict(config, dbname=guard_test_database(name)), autocommit=True)
        # dans son contexte de gestion ; les opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(
            # On choisit ici si les instructions sont validées automatiquement hors d’un bloc
            # transactionnel explicite.
            **dict(config, dbname=guard_test_database(name)), autocommit=True
        ) as c:
            # On exige ici que c.execute('SELECT
            # current_database(),current_user,session_user').fetchone… correspond à (name,
            # 'projet12_importer', 'projet12_importer'). Si ce n’est pas le cas, le message associé
            # bloque la suite.
            require(
                c.execute(
                    "SELECT current_database(),current_user,session_user"
                ).fetchone()
                == (name, "projet12_importer", "projet12_importer"),
                "Identite importeur inattendue.",
            )
            # On garde dans run la valeur renvoyée par run_checks.
            run = run_checks(c)
        # On garde dans dash un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        dash = dict(
            config,
            dbname=guard_test_database(name),
            user="projet12_dashboard",
            password=dashboard_password,
        )
        # On utilise psycopg.connect(**dash, autocommit=True) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(**dash, autocommit=True) as c:
            # On exige ici que c.execute('SELECT
            # current_database(),current_user,session_user').fetchone… correspond à (name,
            # 'projet12_dashboard', 'projet12_dashboard'). Si ce n’est pas le cas, le message associé
            # bloque la suite.
            require(
                c.execute(
                    "SELECT current_database(),current_user,session_user"
                ).fetchone()
                == (name, "projet12_dashboard", "projet12_dashboard"),
                "Identite dashboard inattendue.",
            )
            # On exige ici que c.execute('SHOW transaction_read_only').fetchone()[0] correspond à le
            # texte 'on'. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                c.execute("SHOW transaction_read_only").fetchone()[0] == "on",
                "Lecture seule absente.",
            )
            # On garde dans row une ligne du résultat de la requête, ou None si elle n’en renvoie
            # aucune.
            row = c.execute(
                "SELECT last_event_status,last_declared_workflow_status FROM mart.workflow_execution_current WHERE workflow_execution_id=%s",
                (run,),
            ).fetchone()
            # On exige ici que la ligne en cours correspond à ('success', 'started'). Si ce n’est pas
            # le cas, le message associé bloque la suite.
            require(
                row == ("success", "started"),
                "Succes du controle assimile a succes global.",
            )
            # On exige ici que c.execute('SELECT COUNT(*) FROM
            # mart.workflow_event_history').fetchone()[… correspond à 2. Si ce n’est pas le cas, le
            # message associé bloque la suite.
            require(
                c.execute(
                    "SELECT COUNT(*) FROM mart.workflow_event_history"
                ).fetchone()[0]
                == 2,
                "Historique visible incoherent.",
            )
            # On tente ce bloc et on traite séparément les erreurs prévues :
            # psycopg.errors.InsufficientPrivilege.
            try:
                # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne
                # couvre pas tout le workflow.
                with c.transaction():
                    # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé
                    # séparément.
                    c.execute("SELECT * FROM core.workflow_execution_events LIMIT 0")
            except psycopg.errors.InsufficientPrivilege:
                # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
                pass
            else:
                # On interrompt cette branche avec ValueError : 'Lecture directe core autorisee au
                # dashboard.'.
                raise ValueError("Lecture directe core autorisee au dashboard.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "OK 7/8 : lecture authentifiee dashboard ; succes d etape distinct du resultat global ; core inaccessible."
        )
        # On utilise psycopg.connect(**dict(config, dbname=guard_test_database(name)), autocommit=True)
        # dans son contexte de gestion ; les opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(
            # On choisit ici si les instructions sont validées automatiquement hors d’un bloc
            # transactionnel explicite.
            **dict(config, dbname=guard_test_database(name)), autocommit=True
        ) as c:
            # On exige ici que c.execute('SELECT
            # current_database(),current_user,session_user').fetchone… correspond à (name,
            # 'projet12_importer', 'projet12_importer'). Si ce n’est pas le cas, le message associé
            # bloque la suite.
            require(
                c.execute(
                    "SELECT current_database(),current_user,session_user"
                ).fetchone()
                == (name, "projet12_importer", "projet12_importer"),
                "Identite importeur inattendue.",
            )
            # On garde dans terminal la valeur renvoyée par event.
            terminal = event(run, 3, "workflow", "failed", "workflow")
            # On transmet cette information à append_event pour garder une trace de l’étape et de ses
            # valeurs associées.
            append_event(c, terminal)
            # On garde dans before la valeur renvoyée par state.
            before = state(c)
            # On exige ici que append_event(c, terminal) correspond au texte 'reused' et state(c)
            # correspond à l’état relevé avant l’opération. Si ce n’est pas le cas, le message associé
            # bloque la suite.
            require(
                append_event(c, terminal) == "reused" and state(c) == before,
                "Relance terminale non idempotente.",
            )
        # On utilise psycopg.connect(**dash, autocommit=True) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(**dash, autocommit=True) as c:
            # On exige ici que c.execute('SELECT last_declared_workflow_status FROM
            # mart.workflow_execut… correspond au texte 'failed'. Si ce n’est pas le cas, le message
            # associé bloque la suite.
            require(
                c.execute(
                    "SELECT last_declared_workflow_status FROM mart.workflow_execution_current WHERE workflow_execution_id=%s",
                    (run,),
                ).fetchone()[0]
                == "failed",
                "Echec global non visible.",
            )
        # On affiche ce texte explicite dans la sortie du programme.
        print("OK 8/8 : echec global visible et retransmission sans changement.")
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT : OK — journal teste dans une base isolee, avec trois evenements synthetiques."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Base principale : aucune connexion ni ecriture. NAS : aucun acces. Roles globaux : aucune modification."
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
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
