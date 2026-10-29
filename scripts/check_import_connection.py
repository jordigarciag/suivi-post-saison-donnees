# Lecture du fichier — Diagnostic de l’identité et des droits du compte importeur.
# On contrôle la connexion prévue pour les chargements. Certaines vérifications utilisent une
# transaction et des verrous ; on ne les assimile pas à une simple ouverture de socket.
#

"""Connexion et droits du compte importeur : SELECT et verrous, aucune ecriture metier."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles database_config, verify_import_identity depuis import_connection_config, pour les
# appels de ce fichier.
from import_connection_config import database_config, verify_import_identity

# On rassemble dans TABLES les 21 éléments explicitement indiqués, en conservant leur structure.
TABLES = (
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
    "core.workflow_execution_events",
)
# On regroupe dans ALLOWED_UPDATE ces champs nommés ; on pourra les retrouver par leur clé plutôt que
# par leur position.
ALLOWED_UPDATE = {
    # On associe la clé 'core.excel_current_publication' à cette valeur dans cet objet.
    "core.excel_current_publication": {"publication_id", "activated_in_database_at"},
    # On associe la clé 'core.current_vineyard_reconciliations' à cette valeur dans cet objet.
    "core.current_vineyard_reconciliations": {
        "pipeline_execution_id",
        "reconciliation_run_id",
        "activated_in_database_at",
    },
}


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(ok, message):
    # On prévoit le cas où ok est évalué comme faux, par exemple une valeur vide selon son type.
    if not ok:
        # On interrompt cette branche avec ValueError.
        raise ValueError(message)


def check(connection):
    # On rend disponibles sql depuis psycopg, pour les appels de ce fichier.
    from psycopg import sql

    # On appelle verify_import_identity avec connection.execute('SELECT current_database(),
    # current_user, session_user').fetchone().
    verify_import_identity(
        connection.execute(
            "SELECT current_database(), current_user, session_user"
        ).fetchone()
    )
    # On récupère une seule ligne du résultat SQL ; les contrôles suivants vérifient les valeurs
    # attendues.
    attrs = connection.execute("""SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,
        rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user""").fetchone()
    # Le compte importeur doit garder les attributs limités attendus ; une connexion réussie avec
    # trop de privilèges ne serait pas un résultat satisfaisant.
    require(
        attrs == (True, True, False, False, False, False, False),
        "Attributs du compte inattendus.",
    )
    # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
    # présenter.
    groups = connection.execute("""SELECT r.rolname,m.admin_option FROM pg_auth_members m
        JOIN pg_roles r ON r.oid=m.roleid
        WHERE m.member=(SELECT oid FROM pg_roles WHERE rolname=current_user)""").fetchall()
    # On vérifie les appartenances de rôle, car des droits supplémentaires peuvent être hérités sans
    # apparaître dans les permissions directes du compte.
    require(
        groups == [("projet12_import_writer", False)],
        "Appartenance au groupe inattendue.",
    )
    # On garde dans group une ligne du résultat de la requête, ou None si elle n’en renvoie aucune.
    group = connection.execute("""SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,
        rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='projet12_import_writer' """).fetchone()
    # Le groupe de droits doit lui aussi rester limité : contrôler seulement le compte de connexion
    # ne couvrirait pas les droits hérités.
    require(
        group == (False, True, False, False, False, False, False),
        "Attributs du groupe inattendus.",
    )
    # Le groupe importeur ne doit pas récupérer indirectement les droits d’un autre rôle non prévu.
    require(
        not connection.execute("""SELECT EXISTS (SELECT 1 FROM pg_auth_members
        WHERE member=(SELECT oid FROM pg_roles WHERE rolname='projet12_import_writer'))""").fetchone()[
            0
        ],
        "Le groupe herite d autres roles.",
    )
    # On exige ici que connection.execute('SHOW transaction_read_only').fetchone()[0] correspond à le
    # texte 'off'. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        connection.execute("SHOW transaction_read_only").fetchone()[0] == "off",
        "Session en lecture seule : incompatible avec les futurs chargements et les verrous de lignes.",
    )
    # Le compte doit charger les tables prévues, pas créer librement des objets dans la base.
    require(
        not connection.execute(
            "SELECT has_database_privilege(current_user,current_database(),'CREATE')"
        ).fetchone()[0],
        "CREATE sur la base interdit.",
    )
    # On parcourt ('core', 'staging', 'mart', 'public') ; schema désigne l’élément courant à chaque
    # passage dans la boucle.
    for schema in ("core", "staging", "mart", "public"):
        # On exige ici que la condition connection.execute("SELECT
        # has_schema_privilege(current_user,%s,'CREATE')", (schema,)).fetchon… n’est pas remplie. Si ce
        # n’est pas le cas, le message associé bloque la suite.
        require(
            not connection.execute(
                "SELECT has_schema_privilege(current_user,%s,'CREATE')", (schema,)
            ).fetchone()[0],
            "CREATE interdit sur le schema " + schema,
        )
    # On garde dans objects toutes les lignes encore disponibles dans le résultat SQL.
    objects = connection.execute("""SELECT c.oid,n.nspname||'.'||c.relname,
        c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user),
        c.relowner=(SELECT oid FROM pg_roles WHERE rolname='projet12_import_writer')
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('core','staging','mart') AND c.relkind IN ('r','p','v','m','f')""").fetchall()
    # On parcourt objects ; (oid, name, owned_account, owned_group) désigne l’élément courant à chaque
    # passage dans la boucle.
    for oid, name, owned_account, owned_group in objects:
        # On exige ici que la condition owned_account n’est pas remplie et la condition owned_group
        # n’est pas remplie. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            not owned_account and not owned_group,
            "Compte ou groupe proprietaire de " + name,
        )
        # On parcourt ('UPDATE', 'DELETE', 'TRUNCATE', 'TRIGGER', 'REFERENCES') ; privilege désigne
        # l’élément courant à chaque passage dans la boucle.
        for privilege in ("UPDATE", "DELETE", "TRUNCATE", "TRIGGER", "REFERENCES"):
            # On exige ici que la condition connection.execute('SELECT
            # has_table_privilege(current_user,%s,%s)', (oid, privilege)).fetchon… n’est pas remplie.
            # Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                not connection.execute(
                    "SELECT has_table_privilege(current_user,%s,%s)", (oid, privilege)
                ).fetchone()[0],
                privilege + " global inattendu sur " + name,
            )
        # On garde dans columns toutes les lignes encore disponibles dans le résultat SQL.
        columns = connection.execute(
            """SELECT attname,has_column_privilege(current_user,attrelid,attnum,'UPDATE')
            FROM pg_attribute WHERE attrelid=%s AND attnum>0 AND NOT attisdropped""",
            (oid,),
        ).fetchall()
        # On construit observed_update comme un ensemble sans doublons à partir de col, pour chaque
        # (col, allowed) de columns en ne gardant que les éléments qui passent le filtre.
        observed_update = {col for col, allowed in columns if allowed}
        # On exige ici que observed_update correspond à ALLOWED_UPDATE.get(name, set()). Si ce n’est
        # pas le cas, le message associé bloque la suite.
        require(
            observed_update == ALLOWED_UPDATE.get(name, set()),
            "Permissions UPDATE de colonnes inattendues sur " + name,
        )
        # On vérifie ce cas avant la suite : le nom en cours ne figure pas dans TABLES.
        if name not in TABLES:
            # On exige ici que la condition connection.execute("SELECT
            # has_any_column_privilege(current_user,%s,'INSERT')", (oid,)).fetcho… n’est pas remplie.
            # Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                not connection.execute(
                    "SELECT has_any_column_privilege(current_user,%s,'INSERT')", (oid,)
                ).fetchone()[0],
                "Insertion inattendue sur " + name,
            )
    # On parcourt TABLES ; table désigne l’élément courant à chaque passage dans la boucle.
    for table in TABLES:
        # On parcourt ('SELECT', 'INSERT') ; privilege désigne l’élément courant à chaque passage dans
        # la boucle.
        for privilege in ("SELECT", "INSERT"):
            # On exige ici que le test connection.execute('SELECT
            # has_table_privilege(current_user,%s,%s)', (table, privilege)).fetchone()[0] est
            # satisfait. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                connection.execute(
                    "SELECT has_table_privilege(current_user,%s,%s)", (table, privilege)
                ).fetchone()[0],
                privilege + " absent sur " + table,
            )
        # On appelle connection.execute(sql.SQL('SELECT 1 FROM {} LIMIT
        # 1').format(sql.Identifier(*table.split('.')))).fetchall sans argument positionnel.
        connection.execute(
            sql.SQL("SELECT 1 FROM {} LIMIT 1").format(
                sql.Identifier(*table.split("."))
            )
        ).fetchall()
    # On applique ce réglage à la transaction courante ; il ne s’agit pas de modifier durablement la
    # configuration du serveur PostgreSQL.
    connection.execute("SET LOCAL lock_timeout='10s'")
    # Le verrou commun est déjà pris par un chargement. On ne force pas son passage et on ne
    # supprime pas le verrou pour contourner cette concurrence.
    require(
        connection.execute("SELECT pg_try_advisory_xact_lock(120026,1)").fetchone()[0],
        "Un chargement detient le verrou commun : reessayer apres sa fin.",
    )
    # On appelle connection.execute('SELECT singleton,publication_id FROM
    # core.excel_current_publication FOR UPDATE').fetchall sans argument positionnel.
    connection.execute(
        "SELECT singleton,publication_id FROM core.excel_current_publication FOR UPDATE"
    ).fetchall()
    # On appelle connection.execute('SELECT vineyard_key FROM core.current_vineyard_reconciliations FOR
    # UPDATE').fetchall sans argument positionnel.
    connection.execute(
        "SELECT vineyard_key FROM core.current_vineyard_reconciliations FOR UPDATE"
    ).fetchall()
    # On garde dans counts une ligne du résultat de la requête, ou None si elle n’en renvoie aucune.
    counts = connection.execute("""SELECT
        (SELECT COUNT(*) FROM core.current_vineyard_reconciliations),
        (SELECT COUNT(*) FROM staging.excel_publication_rows),
        (SELECT COUNT(*) FROM staging.reconciliation_acquisition_rows)""").fetchone()
    # On remet les compteurs à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return counts


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
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On lit les paramètres du diagnostic importeur, sans demander d’ingestion ni de chargement
    # métier.
    args = parser.parse_args(argv)
    # On initialise password à None : aucune valeur n’a encore été retenue ici.
    password = None
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On garde dans config les paramètres du compte PostgreSQL prévus par ce module.
        config = database_config(args.project_root)
        # On récupère config['password'] et on le garde dans password pour la suite.
        password = config["password"]
        # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas
        # de connexion.
        import psycopg

        # On utilise psycopg.connect(**config) dans son contexte de gestion ; les opérations de sortie
        # sont exécutées en quittant le bloc.
        with psycopg.connect(**config) as connection:
            # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
            try:
                # On garde dans counts la valeur renvoyée par check.
                counts = check(connection)
            finally:
                # Aucun commit de controle : libere aussi les verrous transactionnels.
                connection.rollback()
        # On affiche ce texte explicite dans la sortie du programme.
        print("Connexion OK : base=suivi_acquisitions | compte=projet12_importer")
        # On affiche ce texte explicite dans la sortie du programme.
        print("Connexion authentifiee : role effectif et compte de session verifies.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Compte sans attribut d administration ; membre du seul groupe projet12_import_writer."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"Lecture des {len(TABLES)} tables, journal inclus : OK. Permissions INSERT presentes ; aucune insertion executee."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "UPDATE limite aux colonnes des deux pointeurs ; historiques sans droit UPDATE/DELETE/TRUNCATE."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Verrou commun et verrouillage reel des pointeurs : OK ; verrous liberes par ROLLBACK."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"Bilans actifs : {counts[0]} | lignes Excel publications conservees : {counts[1]} | acquisitions rapprochements historiques : {counts[2]}"
        )
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT : OK — connexion et permissions du compte de chargement verifiees."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Aucune insertion, modification ou suppression executee. NAS : aucun acces. Mot de passe : non affiche."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Ce controle ne valide pas le chargement complet ni le raccordement du journal au pipeline."
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
        # On affiche 'CONTROLE BLOQUE : ' + message dans la sortie du programme.
        print("CONTROLE BLOQUE : " + message, file=sys.stderr)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Aucune ecriture metier executee. NAS : aucun acces. Ne pas elargir les droits pour contourner le blocage.",
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
