# Lecture du fichier — Diagnostic de la connexion et des permissions réellement utilisées par le dashboard.
# On vérifie l’identité du compte et l’accès aux vues prévues. Un serveur qui répond ne prouve pas
# que ce compte dispose des bons droits.
#

"""Controle TCP reel du compte dashboard et des 19 vues : aucune ecriture ni acces NAS."""

# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys

# On rassemble dans VIEWS les 19 éléments explicitement indiqués, en conservant leur structure.
VIEWS = (
    "excel_vineyard_history",
    "excel_vineyard_current",
    "reconciliation_vineyard_history",
    "reconciliation_vineyard_current",
    "reconciliation_acquisition_current",
    "reconciliation_passage_current",
    "reconciliation_perimeter_current",
    "reconciliation_processing_category_current",
    "reconciliation_acquisition_history",
    "reconciliation_passage_history",
    "reconciliation_association_history",
    "reconciliation_association_current",
    "reconciliation_freshness_current",
    "reconciliation_field_provenance_current",
    "reconciliation_acquisition_evidence_current",
    "reconciliation_acquisition_proof_current",
    "reconciliation_proof_summary_current",
    "workflow_event_history",
    "workflow_execution_current",
)
# On fixe USER à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
USER = "projet12_dashboard"


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(condition, message):
    # On prévoit le cas où condition est évalué comme faux, par exemple une valeur vide selon son type.
    if not condition:
        # On interrompt cette branche avec ValueError.
        raise ValueError(message)


# On prépare les paramètres PostgreSQL nécessaires au contrôle défini par ce module.
def database_config(root):
    # On rend disponibles dotenv_values depuis dotenv, pour les appels de ce fichier.
    from dotenv import dotenv_values

    # On lit les réglages du fichier sans les injecter automatiquement dans l’environnement global ;
    # les secrets ne doivent pas être affichés.
    config = dotenv_values(Path(root) / ".env", encoding="utf-8-sig", interpolate=False)
    # On exige ici que config.get('PROJECT12_DASHBOARD_USER') correspond à USER. Si ce n’est pas le
    # cas, le message associé bloque la suite.
    require(
        config.get("PROJECT12_DASHBOARD_USER") == USER,
        "PROJECT12_DASHBOARD_USER absent ou incorrect.",
    )
    # On garde dans password le champ 'PROJECT12_DASHBOARD_PASSWORD' de config, ou None si la clé est
    # absente.
    password = config.get("PROJECT12_DASHBOARD_PASSWORD")
    # On exige ici que password est du type str et le contrôle bool(password) est positif. Si ce n’est
    # pas le cas, le message associé bloque la suite.
    require(
        isinstance(password, str) and bool(password),
        "PROJECT12_DASHBOARD_PASSWORD absent.",
    )
    # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
    return dict(
        host="127.0.0.1",
        port=5433,
        dbname="suivi_acquisitions",
        user=USER,
        password=password,
        # On limite l’attente de connexion PostgreSQL, sans garantir la durée des requêtes ultérieures.
        connect_timeout=5,
    )


# On compare l’identité réelle du compte aux conditions attendues.
def validate_identity(identity):
    # On exige ici que tuple(identity) correspond à ('suivi_acquisitions', USER, USER). Si ce n’est pas
    # le cas, le message associé bloque la suite.
    require(
        tuple(identity) == ("suivi_acquisitions", USER, USER),
        "Base, role effectif ou compte de session inattendu.",
    )


# On vérifie les permissions requises et celles qui ne doivent pas être accordées.
def validate_rights(rows, source_column_access):
    # rows : schema, objet, SELECT, INSERT, UPDATE, DELETE, TRUNCATE, TRIGGER, REFERENCES.
    require(
        not any(any(row[3:]) for row in rows),
        "Droits d ecriture ou de gestion metier detectes.",
    )
    # On exige ici que la condition any((row[0] in ('core', 'staging') and row[2] for row in rows))
    # n’est pas remplie. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        not any(row[0] in ("core", "staging") and row[2] for row in rows),
        "Lecture directe de tables sources detectee.",
    )
    # On exige ici que la condition source_column_access n’est pas remplie. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(not source_column_access, "Lecture directe de colonnes sources detectee.")


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
    # On récupère les options du contrôle du compte dashboard ; ce parcours vérifie la lecture SQL,
    # pas les chargements.
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
        # On rend disponibles sql depuis psycopg, pour les appels de ce fichier.
        from psycopg import sql

        # On utilise psycopg.connect(**config) dans son contexte de gestion ; les opérations de sortie
        # sont exécutées en quittant le bloc.
        with psycopg.connect(**config) as connection:
            # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
            try:
                # On compare l’identité renvoyée par PostgreSQL à celle attendue ; les paramètres de
                # connexion seuls ne prouvent pas quel rôle est effectivement utilisé.
                validate_identity(
                    connection.execute(
                        "SELECT current_database(),current_user,session_user"
                    ).fetchone()
                )
                # On affiche ce texte explicite dans la sortie du programme.
                print(
                    "Connexion OK : base=suivi_acquisitions | compte=projet12_dashboard"
                )
                # On applique ce réglage à la transaction courante ; il ne s’agit pas de modifier
                # durablement la configuration du serveur PostgreSQL.
                connection.execute("SET LOCAL jit = off")
                # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                connection.execute("SET LOCAL statement_timeout = '120s'")
                # On envoie cette requête à connection avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                connection.execute("SET LOCAL lock_timeout = '5s'")
                # On exige ici que connection.execute('SHOW transaction_read_only').fetchone()[0]
                # correspond au texte 'on'. Si ce n’est pas le cas, le message associé bloque la
                # suite.
                require(
                    connection.execute("SHOW transaction_read_only").fetchone()[0]
                    == "on",
                    "Transaction de consultation non configuree en lecture seule.",
                )
                # On récupère une seule ligne du résultat SQL ; les contrôles suivants vérifient les
                # valeurs attendues.
                attrs = connection.execute("""SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,
                    rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user""").fetchone()
                # Le compte importeur doit garder les attributs limités attendus ; une connexion
                # réussie avec trop de privilèges ne serait pas un résultat satisfaisant.
                require(
                    attrs == (True, True, False, False, False, False, False),
                    "Attributs du compte inattendus.",
                )
                # On garde dans groups toutes les lignes encore disponibles dans le résultat SQL.
                groups = connection.execute("""SELECT r.rolname,m.admin_option FROM pg_auth_members m
                    JOIN pg_roles r ON r.oid=m.roleid
                    WHERE m.member=(SELECT oid FROM pg_roles WHERE rolname=current_user)""").fetchall()
                # On exige ici que groups correspond à [('projet12_mart_reader', False)]. Si ce n’est
                # pas le cas, le message associé bloque la suite.
                require(
                    groups == [("projet12_mart_reader", False)],
                    "Appartenance du compte a un groupe inattendu.",
                )
                # On exige ici que la condition connection.execute("SELECT
                # has_database_privilege(current_user,current_database(),'CREATE')").… n’est pas
                # remplie. Si ce n’est pas le cas, le message associé bloque la suite.
                require(
                    not connection.execute(
                        "SELECT has_database_privilege(current_user,current_database(),'CREATE')"
                    ).fetchone()[0],
                    "CREATE sur la base interdit pour le dashboard.",
                )
                # On parcourt ('core', 'staging', 'mart', 'public') ; schema désigne l’élément courant
                # à chaque passage dans la boucle.
                for schema in ("core", "staging", "mart", "public"):
                    # On exige ici que la condition connection.execute("SELECT
                    # has_schema_privilege(current_user,%s,'CREATE')", (schema,)).fetchon… n’est pas
                    # remplie. Si ce n’est pas le cas, le message associé bloque la suite.
                    require(
                        not connection.execute(
                            "SELECT has_schema_privilege(current_user,%s,'CREATE')",
                            (schema,),
                        ).fetchone()[0],
                        "CREATE inattendu sur le schema " + schema,
                    )
                # On garde dans rights toutes les lignes encore disponibles dans le résultat SQL.
                rights = connection.execute("""SELECT n.nspname,c.relname,
                    has_table_privilege(current_user,c.oid,'SELECT'),
                    has_table_privilege(current_user,c.oid,'INSERT') OR has_any_column_privilege(current_user,c.oid,'INSERT'),
                    has_table_privilege(current_user,c.oid,'UPDATE') OR has_any_column_privilege(current_user,c.oid,'UPDATE'),
                    has_table_privilege(current_user,c.oid,'DELETE'),
                    has_table_privilege(current_user,c.oid,'TRUNCATE'),
                    has_table_privilege(current_user,c.oid,'TRIGGER'),
                    has_table_privilege(current_user,c.oid,'REFERENCES')
                    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname IN ('core','staging','mart') AND c.relkind IN ('r','p','v','m','f')""").fetchall()
                # On garde dans columns toutes les lignes encore disponibles dans le résultat SQL.
                columns = connection.execute("""SELECT n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                    WHERE n.nspname IN ('core','staging') AND c.relkind IN ('r','p','v','m','f')
                    AND has_any_column_privilege(current_user,c.oid,'SELECT')""").fetchall()
                # On vérifie les droits accordés au compte ; pouvoir se connecter ne prouve pas
                # qu’ils sont correctement limités.
                validate_rights(rights, columns)
                # On affiche cette information de suivi dans la sortie du programme.
                print(
                    "Transaction en lecture seule : on. Aucun attribut d administration ; groupe lecteur uniquement."
                )
                # On affiche cette information de suivi dans la sortie du programme.
                print(
                    "Schemas : aucune creation. Tables core/staging : aucune lecture directe, y compris de colonnes."
                )
                # On affiche cette information de suivi dans la sortie du programme.
                print(
                    "Objets metier : aucun droit INSERT/UPDATE/DELETE/TRUNCATE/TRIGGER/REFERENCES."
                )
                # On parcourt VIEWS ; view désigne l’élément courant à chaque passage dans la boucle.
                for view in VIEWS:
                    # On interroge les valeurs enregistrées en base pour ce contrôle ; les
                    # paramètres séparés de la requête fournissent les valeurs recherchées.
                    connection.execute(
                        sql.SQL("SELECT * FROM {} LIMIT 0").format(
                            sql.Identifier("mart", view)
                        )
                    )
                    # On affiche '  - mart.' + view + ' : lecture OK' dans la sortie du programme.
                    print("  - mart." + view + " : lecture OK")
                # On affiche f'Lecture des {len(VIEWS)} vues mart attendues : OK' dans la sortie du
                # programme.
                print(f"Lecture des {len(VIEWS)} vues mart attendues : OK")
                # On garde dans counts une ligne du résultat de la requête, ou None si elle n’en
                # renvoie aucune.
                counts = connection.execute("""SELECT COUNT(*),COALESCE(SUM(acquisition_count),0),
                    COALESCE(SUM(association_count),0),COALESCE(SUM(passage_count),0)
                    FROM mart.reconciliation_vineyard_current""").fetchone()
                # On garde dans history une ligne du résultat de la requête, ou None si elle n’en
                # renvoie aucune.
                history = connection.execute("""SELECT
                    (SELECT COUNT(*) FROM mart.reconciliation_acquisition_history),
                    (SELECT COUNT(*) FROM mart.reconciliation_association_history),
                    (SELECT COUNT(*) FROM mart.reconciliation_passage_history)""").fetchone()
                # On garde dans coverage une ligne du résultat de la requête, ou None si elle n’en
                # renvoie aucune.
                coverage = connection.execute("""SELECT COUNT(*),
                    COUNT(*) FILTER (WHERE has_current_excel_reference AND NOT has_active_reconciliation),
                    COUNT(*) FILTER (WHERE has_active_reconciliation AND NOT has_current_excel_reference),
                    COUNT(*) FILTER (WHERE excel_version_matches_current IS FALSE)
                    FROM mart.reconciliation_freshness_current""").fetchone()
                # On garde dans provenance une ligne du résultat de la requête, ou None si elle n’en
                # renvoie aucune.
                provenance = connection.execute("""SELECT COUNT(DISTINCT field_name),COUNT(*)
                    FROM mart.reconciliation_field_provenance_current""").fetchone()
                # On affiche ce texte explicite dans la sortie du programme.
                print(
                    "Comptage reel des trois nouvelles vues sous le compte dashboard..."
                )
                # On récupère connection.execute('SELECT COUNT(*) FROM
                # mart.reconciliation_acquisition_… et on le garde dans evidence pour la suite.
                evidence = connection.execute(
                    "SELECT COUNT(*) FROM mart.reconciliation_acquisition_evidence_current"
                ).fetchone()[0]
                # On récupère connection.execute('SELECT COUNT(*) FROM
                # mart.reconciliation_acquisition_… et on le garde dans proofs pour la suite.
                proofs = connection.execute(
                    "SELECT COUNT(*) FROM mart.reconciliation_acquisition_proof_current"
                ).fetchone()[0]
                # On garde dans groups une ligne du résultat de la requête, ou None si elle n’en
                # renvoie aucune.
                groups = connection.execute(
                    "SELECT COUNT(*),COALESCE(SUM(acquisition_count),0) FROM mart.reconciliation_proof_summary_current"
                ).fetchone()
                # On exige ici que evidence correspond à counts[1]. Si ce n’est pas le cas, le message
                # associé bloque la suite.
                require(
                    evidence == counts[1],
                    "Volume du detail des preuves different du bilan.",
                )
                # On exige ici que proofs correspond à 14 * evidence. Si ce n’est pas le cas, le
                # message associé bloque la suite.
                require(
                    proofs == 14 * evidence,
                    "Volume des 14 indicateurs different du detail.",
                )
                # On exige ici que groups[1] correspond à proofs. Si ce n’est pas le cas, le message
                # associé bloque la suite.
                require(
                    groups[1] == proofs,
                    "Somme de la synthese differente des indicateurs.",
                )
                # On garde dans journal une ligne du résultat de la requête, ou None si elle n’en
                # renvoie aucune.
                journal = connection.execute(
                    "SELECT COUNT(*),COUNT(DISTINCT workflow_execution_id) FROM mart.workflow_event_history"
                ).fetchone()
                # On récupère connection.execute('SELECT COUNT(*) FROM
                # mart.workflow_execution_current'… et on le garde dans journal_current pour la suite.
                journal_current = connection.execute(
                    "SELECT COUNT(*) FROM mart.workflow_execution_current"
                ).fetchone()[0]
                # On exige ici que journal_current correspond à journal[1]. Si ce n’est pas le cas, le
                # message associé bloque la suite.
                require(
                    journal_current == journal[1],
                    "Nombre d executions du journal different des identifiants distincts.",
                )
            finally:
                # On annule les écritures non validées dans cette transaction, sans prétendre annuler
                # les opérations déjà commises ailleurs.
                connection.rollback()
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"Bilans courants : {counts[0]} | acquisitions : {counts[1]} | associations : {counts[2]} | passages : {counts[3]}"
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"Lignes historiques : acquisitions={history[0]} | associations={history[1]} | passages={history[2]} ; pas des totaux uniques toutes observations confondues."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"Provenance : {coverage[0]} vignobles visibles | Excel sans bilan={coverage[1]} | bilans hors reference={coverage[2]} | versions differentes={coverage[3]}"
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"Catalogue de provenance : {provenance[0]} champs documentes | {provenance[1]} lignes vignoble/champ ; pas des acquisitions supplementaires."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"Preuves : {evidence} acquisitions | {proofs} indicateurs | {groups[0]} groupes de synthese ; lecture reelle sous le compte dashboard."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            f"Journal : {journal[0]} evenements | {journal_current} executions ; zero est normal tant que la chaine ne le renseigne pas."
        )
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT : OK — connexion, permissions de consultation et lecture des 19 vues verifiees."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Aucune ecriture executee. NAS : aucun acces. Mot de passe : non affiche. Transaction terminee par ROLLBACK."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Ce controle ne certifie pas la conformite metier ou l actualite de toutes les sources."
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
            "Aucune ecriture executee. Ne pas transmettre .env ni elargir les permissions pour contourner le blocage.",
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
