# Lecture du fichier — Vérification locale et SQL du résultat du parcours limité à un domaine.
# On suit les liens entre exécution et résultats ; les volumes constatés sont lus dans le contexte
# contrôlé.
#

"""Controle apres execution DomaineDemoD : SELECT seulement, aucune retransmission."""

# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys

# On fixe WORKFLOW à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
WORKFLOW = "44d41939-fc16-4771-8457-d24c18d248cf"
# On fixe PIPELINE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
PIPELINE = "20261013_88eae821"
# On fixe PUBLICATION à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
PUBLICATION = "20261013_775f8588"
# On rassemble dans STEPS les 8 éléments explicitement indiqués, en conservant leur structure.
STEPS = (
    "excel_ingestion",
    "excel_publication_check",
    "excel_reference_pin",
    "nas_scope_prepare",
    "nas_pipeline_execute",
    "nas_bundle_check",
    "excel_import",
    "nas_import",
)


class CheckError(ValueError):
    """Code de controle constant, sans information sensible."""


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(condition, code):
    # On prévoit le cas où condition est évalué comme faux, par exemple une valeur vide selon son type.
    if not condition:
        # On interrompt cette branche avec CheckError.
        raise CheckError(code)


# On vérifie les éléments locaux nécessaires à ce diagnostic avant la consultation SQL.
def validate_local(events, normalize):
    # On rassemble dans expected les 1 éléments explicitement indiqués, en conservant leur structure.
    expected = [("workflow", "workflow", "started")]
    # On parcourt STEPS ; step désigne l’élément courant à chaque passage dans la boucle.
    for step in STEPS:
        # On ajoute les éléments de [('step', step, 'started'), ('step', step, 'success')] à expected ;
        # on n’ajoute pas la collection comme un seul élément imbriqué.
        expected.extend([("step", step, "started"), ("step", step, "success")])
    # On ajoute ('workflow', 'workflow', 'success') à la fin de expected ; les éléments précédents
    # restent conservés.
    expected.append(("workflow", "workflow", "success"))
    # On exige ici que [(e['event_type'], e['stage'], e['status']) for e in events] correspond à le
    # résultat attendu. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        [(e["event_type"], e["stage"], e["status"]) for e in events] == expected,
        "LOCAL_SEQUENCE_UNEXPECTED",
    )
    # On garde dans scope un nouveau dictionnaire construit avec les valeurs indiquées.
    scope = dict(
        # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
        year=2026, vineyards=["DomaineDemoD"], all_vineyards=False, execution_kind="business"
    )
    # On parcourt les événements du journal ; e désigne l’élément courant à chaque passage dans la
    # boucle.
    for e in events:
        # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas,
        # le message associé bloque la suite.
        require(
            e["workflow_execution_id"] == WORKFLOW
            # On exige aussi que le périmètre détaillé enregistré dans e correspond au périmètre du
            # traitement.
            and e["scope_payload"] == scope
            # On exige aussi que l’origine du déclenchement dans e correspond au texte
            # 'manual_script'.
            and e["trigger_mode"] == "manual_script"
            # On exige aussi que le code du problème rencontré dans e vaut None.
            and e["error_code"] is None,
            "LOCAL_EXECUTION_MISMATCH",
        )
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        events[-1]["excel_publication_id"] == PUBLICATION
        # On exige aussi que l’identifiant du traitement NAS dans events[-1] correspond à PIPELINE.
        and events[-1]["pipeline_execution_id"] == PIPELINE
        # On exige aussi que events[-1]['metrics_payload'].get('completed_steps') correspond à 8.
        and events[-1]["metrics_payload"].get("completed_steps") == 8,
        "LOCAL_FINAL_LINKS_MISMATCH",
    )
    # On remet [normalize(e) for e in events] à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return [normalize(e) for e in events]


# On rapproche les informations conservées en base pour contrôler la cohérence du résultat.
def verify_sql(conn, expected, columns):
    # Premiere instruction de la transaction ; aucune fonction de chargement appelee.
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
    # On exige ici que conn.execute('SHOW transaction_read_only').fetchone() correspond à ('on',). Si
    # ce n’est pas le cas, le message associé bloque la suite.
    require(
        conn.execute("SHOW transaction_read_only").fetchone() == ("on",),
        "READ_ONLY_NOT_CONFIRMED",
    )
    # On récupère une seule ligne du résultat SQL ; les contrôles suivants vérifient les valeurs
    # attendues.
    identity = conn.execute(
        "SELECT current_database(), current_user, session_user"
    ).fetchone()
    # On exige ici que les éléments d’identité du lot correspond à ('suivi_acquisitions',
    # 'projet12_importer', 'projet12_importer'). Si ce n’est pas le cas, le message associé bloque la
    # suite.
    require(
        identity == ("suivi_acquisitions", "projet12_importer", "projet12_importer"),
        "DATABASE_OR_IDENTITY_MISMATCH",
    )
    # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
    # présenter.
    rows = conn.execute(
        "SELECT "
        + ",".join(columns)
        + " FROM core.workflow_execution_events WHERE workflow_execution_id=%s ORDER BY event_sequence",
        (WORKFLOW,),
    ).fetchall()
    # On exige ici que [dict(zip(columns, row)) for row in rows] correspond au résultat attendu. Si
    # ce n’est pas le cas, le message associé bloque la suite.
    require(
        [dict(zip(columns, row)) for row in rows] == expected,
        "LOCAL_SQL_JOURNAL_MISMATCH",
    )
    # On exige ici que conn.execute('SELECT publication_id FROM core.excel_current_publication W…
    # correspond à [(PUBLICATION,)]. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        conn.execute(
            "SELECT publication_id FROM core.excel_current_publication WHERE singleton=true"
        ).fetchall()
        == [(PUBLICATION,)],
        "CURRENT_EXCEL_PUBLICATION_MISMATCH",
    )
    # On exige ici que conn.execute('SELECT project_year,status,excel_publication_id FROM core.p…
    # correspond à [(2026, 'success', PUBLICATION)]. Si ce n’est pas le cas, le message associé bloque
    # la suite.
    require(
        conn.execute(
            "SELECT project_year,status,excel_publication_id FROM core.pipeline_runs "
            "WHERE pipeline_execution_id=%s",
            (PIPELINE,),
        ).fetchall()
        == [(2026, "success", PUBLICATION)],
        "PIPELINE_LINKS_MISMATCH",
    )
    # On garde dans active toutes les lignes encore disponibles dans le résultat SQL.
    active = conn.execute(
        """SELECT c.vineyard_key,v.vineyard_name,c.pipeline_execution_id,
        c.reconciliation_run_id,r.nas_pipeline_execution_id,r.excel_publication_id,
        r.acquisition_rows,r.association_rows,r.passage_rows
        FROM core.current_vineyard_reconciliations c
        JOIN core.vineyards v ON v.vineyard_key=c.vineyard_key
        JOIN core.reconciliation_runs r ON r.pipeline_execution_id=c.pipeline_execution_id
          AND r.vineyard_key=c.vineyard_key AND r.reconciliation_run_id=c.reconciliation_run_id
        WHERE lower(v.vineyard_name)=lower(%s)""",
        ("DomaineDemoD",),
    ).fetchall()
    # On exige ici que len(active) correspond à 1. Si ce n’est pas le cas, le message associé bloque la
    # suite.
    require(len(active) == 1, "PILOTE_CURRENT_RESULT_MISSING_OR_AMBIGUOUS")
    # On récupère active[0] et on le garde dans (key, name, pipeline, rec, nas, pub, acq, assoc,
    # passages) pour la suite.
    key, name, pipeline, rec, nas, pub, acq, assoc, passages = active[0]
    # On exige ici que name.casefold() correspond au texte 'domainedemod' et pipeline correspond à
    # PIPELINE et nas correspond à PIPELINE et pub correspond à PUBLICATION. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        name.casefold() == "domainedemod"
        # On exige aussi que pipeline correspond à PIPELINE.
        and pipeline == PIPELINE
        # On exige aussi que nas correspond à PIPELINE.
        and nas == PIPELINE
        # On exige aussi que pub correspond à PUBLICATION.
        and pub == PUBLICATION,
        "PILOTE_CURRENT_LINKS_MISMATCH",
    )
    # On prépare counts comme liste vide ; on la remplira au fil des opérations suivantes.
    counts = []
    # On parcourt [('reconciliation_acquisition_rows', acq), ('reconciliation_association_r… ; (table,
    # total) désigne l’élément courant à chaque passage dans la boucle.
    for table, total in [
        ("reconciliation_acquisition_rows", acq),
        ("reconciliation_association_rows", assoc),
        ("reconciliation_passage_rows", passages),
    ]:
        # On récupère conn.execute('SELECT COUNT(*) FROM staging.' + table + ' WHERE pipeline_e… et on
        # le garde dans actual pour la suite.
        actual = conn.execute(
            "SELECT COUNT(*) FROM staging."
            + table
            + " WHERE pipeline_execution_id=%s AND vineyard_key=%s AND reconciliation_run_id=%s",
            (PIPELINE, key, rec),
        ).fetchone()[0]
        # On exige ici que le résultat obtenu correspond à total. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(actual == total, "RECONCILIATION_ROW_COUNT_MISMATCH")
        # On ajoute actual à la fin de counts ; les éléments précédents restent conservés.
        counts.append(actual)
    # On récupère conn.execute('SELECT COUNT(*) FROM staging.excel_publication_rows WHERE p… et on le
    # garde dans excel pour la suite.
    excel = conn.execute(
        "SELECT COUNT(*) FROM staging.excel_publication_rows "
        "WHERE publication_id=%s AND vineyard_key=%s",
        (PUBLICATION, key),
    ).fetchone()[0]
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return excel, counts


def main():
    # On récupère Path(__file__).resolve().parents[1] et on le garde dans root pour la suite.
    root = Path(__file__).resolve().parents[1]
    # On construit path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    path = (
        root
        / "data/03_normalized/workflow_runs"
        / WORKFLOW.replace("-", "")
        / "events.jsonl"
    )
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # Cette entrée de lecture attend la configuration locale prévue ; elle ne doit pas deviner
        # une autre connexion.
        require(
            os.environ.get("PROJECT12_IMPORT_CONNECTION_MODE", "local") == "local",
            "LOCAL_CONFIGURATION_REQUIRED",
        )
        # On rend disponibles read_events depuis workflow_runtime, pour les appels de ce fichier.
        from workflow_runtime import read_events
        # On rend disponibles COLUMNS, normalize_event depuis workflow_journal_repository, pour les
        # appels de ce fichier.
        from workflow_journal_repository import COLUMNS, normalize_event
        # On rend disponibles database_config depuis import_connection_config, pour les appels de ce
        # fichier.
        from import_connection_config import database_config

        # On garde dans before l’empreinte de hashlib.sha256(path.read_bytes()) sous forme d’octets.
        before = hashlib.sha256(path.read_bytes()).digest()
        # On garde dans expected la valeur renvoyée par validate_local.
        expected = validate_local(read_events(path), normalize_event)
        # Le journal local doit rester identique pendant ce contrôle ; on ne confirme pas un
        # résultat à partir de deux états successifs du fichier.
        require(
            hashlib.sha256(path.read_bytes()).digest() == before,
            "LOCAL_JOURNAL_CHANGED",
        )
        # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas
        # de connexion.
        import psycopg

        # On garde dans config les paramètres du compte PostgreSQL prévus par ce module.
        config = database_config(root)
        # Protection des la connexion, puis transaction coherente en lecture seule.
        with psycopg.connect(
            # On choisit ici si les instructions sont validées automatiquement hors d’un bloc
            # transactionnel explicite.
            **config, autocommit=False, options="-c default_transaction_read_only=on"
        ) as conn:
            # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
            try:
                # On répartit les valeurs renvoyées par verify_sql entre (excel, counts) ; leur ordre
                # doit correspondre à celui prévu par cet appel.
                excel, counts = verify_sql(conn, expected, COLUMNS)
                # On exige ici que hashlib.sha256(path.read_bytes()).digest() correspond à l’état
                # relevé avant l’opération. Si ce n’est pas le cas, le message associé bloque la suite.
                require(
                    hashlib.sha256(path.read_bytes()).digest() == before,
                    "LOCAL_JOURNAL_CHANGED",
                )
            finally:
                # On annule les écritures non validées dans cette transaction, sans prétendre annuler
                # les opérations déjà commises ailleurs.
                conn.rollback()
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Connexion : suivi_acquisitions ; compte projet12_importer ; transaction READ ONLY."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Journal : 18/18 evenements locaux identiques aux evenements SQL, tous les champs compares."
        )
        # On affiche 'Publication Excel courante : ' + PUBLICATION dans la sortie du programme.
        print("Publication Excel courante : " + PUBLICATION)
        # On affiche 'Bilan actif DomaineDemoD : traitement et observation NAS ' + PIPELINE dans la
        # sortie du programme.
        print("Bilan actif DomaineDemoD : traitement et observation NAS " + PIPELINE)
        # On affiche le texte 'Liens Excel/NAS/rapprochement : concordants.' dans la sortie du
        # programme.
        print("Liens Excel/NAS/rapprochement : concordants.")
        # On affiche 'Lignes Excel DomaineDemoD dans cette publication : %d' % excel dans la sortie du
        # programme.
        print("Lignes Excel DomaineDemoD dans cette publication : %d" % excel)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Rapprochement DomaineDemoD : %d acquisitions ; %d associations ; %d passages."
            % tuple(counts)
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Volumes des trois tables de rapprochement : conformes aux volumes declares."
        )
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print("RESULTAT : OK - journal SQL et bilan actif DomaineDemoD confirmes.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Aucune ecriture SQL, aucun acces NAS, aucun rejeu, aucun nouveau workflow."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Ce controle ne valide pas la conformite metier des livrables ni une relance sans doublon."
        )
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as exc:
        # Ne pas afficher de message externe pouvant contenir un secret ou une ligne metier.
        print(
            "CONTROLE NON CONFIRME : "
            + (str(exc) if isinstance(exc, CheckError) else type(exc).__name__)
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print("Ne pas relancer le workflow et ne pas modifier les pointeurs.")
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine le programme avec ce code de sortie pour que l’appelant puisse distinguer réussite et
    # échec.
    sys.exit(main())
