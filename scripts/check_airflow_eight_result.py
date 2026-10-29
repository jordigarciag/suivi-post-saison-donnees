# Lecture du fichier — Lecture des preuves de fin du parcours Airflow principal.
# On rapproche les identifiants du reçu, du journal et des résultats. Un état de tâche favorable ne
# remplace pas cette vérification métier.
#

"""Controle Windows apres Airflow : huit vignobles, recu/journal/manifestes/SQL ; SELECT seulement."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles UUID depuis uuid, pour les appels de ce fichier.
from uuid import UUID
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On rend disponibles VINEYARDS, scope, result_from_receipt depuis airflow_eight_contract, pour les
# appels de ce fichier.
from airflow_eight_contract import VINEYARDS, scope, result_from_receipt

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


class ResultCheckError(ValueError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(ok, code):
    # On prévoit le cas où ok est évalué comme faux, par exemple une valeur vide selon son type.
    if not ok:
        # On interrompt cette branche avec ResultCheckError.
        raise ResultCheckError(code)


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # Option --receipt : Chemin local du recu execution annonce dans Airflow. Sa déclaration ne
    # déclenche pas l’action.
    parser.add_argument(
        "--receipt",
        type=Path,
        required=True,
        help="Chemin local du recu execution annonce dans Airflow.",
    )
    # On récupère les options de ce lancement dans args ; les vérifications ci-dessous restent
    # nécessaires avant des utiliser.
    args = parser.parse_args(argv)
    # On récupère Path(__file__).resolve().parents[1] et on le garde dans root pour la suite.
    root = Path(__file__).resolve().parents[1]
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On exige ici que os.environ.get('PROJECT12_IMPORT_CONNECTION_MODE', 'local') correspond à le
        # texte 'local'. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            os.environ.get("PROJECT12_IMPORT_CONNECTION_MODE", "local") == "local",
            "LOCAL_IMPORT_CONFIGURATION_REQUIRED",
        )
        # On choisit la valeur de receipt_path selon ce test : args.receipt est absolu. Les deux
        # résultats possibles restent définis explicitement ici.
        receipt_path = (
            args.receipt if args.receipt.is_absolute() else root / args.receipt
        )
        # On exige ici que receipt_path.resolve().parent correspond à (root /
        # 'logs/airflow_workflow').resolve(). Si ce n’est pas le cas, le message associé bloque la
        # suite.
        require(
            receipt_path.resolve().parent == (root / "logs/airflow_workflow").resolve(),
            "RECEIPT_PATH_NOT_LOCAL",
        )
        # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite,
        # car un JSON lisible n’est pas forcément un lot valide.
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas,
        # le message associé bloque la suite.
        require(
            receipt.get("kind") == "execution"
            # On exige aussi que receipt.get('status') correspond au texte 'success'.
            and receipt.get("status") == "success"
            # On exige aussi que receipt.get('trigger_mode') appartient à ('airflow_manual',
            # 'airflow_scheduled').
            and receipt.get("trigger_mode") in ("airflow_manual", "airflow_scheduled")
            # On exige aussi que receipt.get('completed_steps') correspond à 8.
            and receipt.get("completed_steps") == 8,
            "EXECUTION_RECEIPT_NOT_SUCCESS",
        )
        # On garde dans marker les objets Python décodés depuis le JSON fourni.
        marker = json.loads(
            (root / "state/workflow_execution/airflow_share_identity.json").read_text(
                # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas
                # être décodé selon un réglage implicite du poste.
                encoding="utf-8"
            )
        )
        # On vérifie le contenu du reçu métier : le seul code de sortie du processus ne suffit pas à
        # confirmer toutes les étapes.
        result_from_receipt(receipt, marker["share_id"])
        # On garde dans wid la représentation textuelle de UUID(receipt['workflow_execution_id']).
        wid = str(UUID(receipt["workflow_execution_id"]))
        # On assemble ces deux éléments pour construire relative.
        relative = "data/03_normalized/workflow_runs/" + UUID(wid).hex + "/events.jsonl"
        # On exige ici que receipt.get('journal_relative_path') correspond au chemin relatif. Si ce
        # n’est pas le cas, le message associé bloque la suite.
        require(
            receipt.get("journal_relative_path") == relative,
            "LOCAL_JOURNAL_PATH_MISMATCH",
        )
        # On rend disponibles read_events depuis workflow_runtime, pour les appels de ce fichier.
        from workflow_runtime import read_events
        # On rend disponibles COLUMNS, normalize_event depuis workflow_journal_repository, pour les
        # appels de ce fichier.
        from workflow_journal_repository import COLUMNS, normalize_event
        # On rend disponibles database_config, verify_import_identity depuis import_connection_config,
        # pour les appels de ce fichier.
        from import_connection_config import database_config, verify_import_identity

        # On calcule ce quotient pour construire journal.
        journal = root / relative
        # On photographie les octets du journal avant sa validation ; une seconde empreinte
        # permettra de détecter un changement pendant le contrôle.
        digest = hashlib.sha256(journal.read_bytes()).digest()
        # On relit le journal avec ses contrôles de séquence et d’identité avant du comparer aux
        # événements attendus.
        events = read_events(journal)
        # Le journal attendu commence par le début du workflow, avant les événements de ses étapes.
        expected_sequence = [("workflow", "workflow", "started")]
        # On parcourt STEPS ; step désigne l’élément courant à chaque passage dans la boucle.
        for step in STEPS:
            # Chaque étape doit avoir un début puis une fin réussie ; on ne valide pas seulement le
            # nombre total d’événements.
            expected_sequence += [("step", step, "started"), ("step", step, "success")]
        # La réussite globale doit venir après les huit étapes, pas avant ou au milieu du journal.
        expected_sequence.append(("workflow", "workflow", "success"))
        # On exige ici que [(e['event_type'], e['stage'], e['status']) for e in events] correspond à
        # expected_sequence. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            [(e["event_type"], e["stage"], e["status"]) for e in events]
            == expected_sequence,
            "LOCAL_SEQUENCE_MISMATCH",
        )
        # On garde dans expected_scope la valeur renvoyée par scope.
        expected_scope = scope()
        # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            all(
                e["workflow_execution_id"] == wid
                # On exige aussi que l’origine du déclenchement dans e correspond à l’origine du
                # déclenchement dans receipt.
                and e["trigger_mode"] == receipt["trigger_mode"]
                # On exige aussi que le périmètre détaillé enregistré dans e correspond à
                # expected_scope.
                and e["scope_payload"] == expected_scope
                # On exige aussi que le code du problème rencontré dans e vaut None.
                and e["error_code"] is None
                for e in events
            ),
            "WORKFLOW_SCOPE_OR_MODE_MISMATCH",
        )
        # On distribue ces valeurs entre pub, pipeline, dans l’ordre de l’affectation. Chaque nom
        # reçoit son propre élément.
        pub, pipeline = (
            receipt["excel_publication_id"],
            receipt["pipeline_execution_id"],
        )
        # On exige ici que pub est du type str et le contrôle bool(pub) est positif et pipeline est du
        # type str et le contrôle bool(pipeline) est positif. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(
            isinstance(pub, str)
            # On exige aussi que le contrôle bool(pub) est positif.
            and bool(pub)
            # On exige aussi que pipeline est du type str.
            and isinstance(pipeline, str)
            # On exige aussi que le contrôle bool(pipeline) est positif.
            and bool(pipeline),
            "RESULT_LINKS_MISSING",
        )
        # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas,
        # le message associé bloque la suite.
        require(
            events[-1]["excel_publication_id"] == pub
            # On exige aussi que l’identifiant du traitement NAS dans events[-1] correspond à pipeline.
            and events[-1]["pipeline_execution_id"] == pipeline
            # On exige aussi que events[-1]['metrics_payload'].get('completed_steps') correspond à 8.
            and events[-1]["metrics_payload"].get("completed_steps") == 8,
            "LOCAL_FINAL_LINKS_MISMATCH",
        )
        # On garde dans marker les objets Python décodés depuis le JSON fourni.
        marker = json.loads(
            (root / "state/workflow_execution/airflow_share_identity.json").read_text(
                # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas
                # être décodé selon un réglage implicite du poste.
                encoding="utf-8"
            )
        )
        # On exige ici que receipt.get('share_id') correspond à marker['share_id']. Si ce n’est pas le
        # cas, le message associé bloque la suite.
        require(
            receipt.get("share_id") == marker["share_id"],
            "SHARED_STATE_RECEIPT_MISMATCH",
        )
        # On exige ici que re.fullmatch('[0-9]{8}_[0-9a-f]{8}', pipeline) est renseigné (différent de
        # None). Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            re.fullmatch(r"[0-9]{8}_[0-9a-f]{8}", pipeline) is not None,
            "PIPELINE_ID_INVALID",
        )
        # On assemble ces deux éléments pour construire manifest_relative.
        manifest_relative = (
            "data/03_normalized/pipeline_runs/" + pipeline + "/manifest.json"
        )
        # On calcule ce quotient pour construire manifest_path.
        manifest_path = root / manifest_relative
        # Ce contrôle porte sur la destination résolue ; un chemin textuellement situé sous le
        # projet pourrait encore pointer ailleurs par un lien symbolique.
        require(
            manifest_path.resolve().is_relative_to((root / "data").resolve())
            # On exige aussi que (root / 'data').resolve() reste sous root.resolve().
            and (root / "data").resolve().is_relative_to(root.resolve()),
            "MANIFEST_PATH_REDIRECTED",
        )
        # On garde dans manifest_bytes les octets lus depuis manifest_path, avant toute conversion
        # en texte. Les contrôles de contenu pourront ainsi repartir de cette lecture.
        manifest_bytes = manifest_path.read_bytes()
        # On garde dans manifest les objets Python décodés depuis le JSON fourni.
        manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
        # On exige ici que manifest.get('pipeline_execution_id') correspond à pipeline et
        # manifest.get('status') correspond au texte 'success' et manifest.get('project_year')
        # correspond à 2026. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            manifest.get("pipeline_execution_id") == pipeline
            # On exige aussi que manifest.get('status') correspond au texte 'success'.
            and manifest.get("status") == "success"
            # On exige aussi que manifest.get('project_year') correspond à 2026.
            and manifest.get("project_year") == 2026,
            "MANIFEST_NOT_SUCCESS",
        )
        # On garde dans items le champ 'vineyards' de manifest, ou None si la clé est absente.
        items = manifest.get("vineyards")
        # On exige ici que items est du type list et [item.get('vineyard') for item in items]
        # correspond à list(VINEYARDS) et tous les éléments satisfont le test indiqué. Si ce n’est pas
        # le cas, le message associé bloque la suite.
        require(
            isinstance(items, list)
            # On exige aussi que [item.get('vineyard') for item in items] correspond à list(VINEYARDS).
            and [item.get("vineyard") for item in items] == list(VINEYARDS)
            # On exige aussi que tous les éléments satisfont le test indiqué.
            and all(item.get("status") == "success" for item in items),
            "MANIFEST_EIGHT_SCOPE_MISMATCH",
        )
        # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas
        # de connexion.
        import psycopg

        # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre pas
        # tout le workflow.
        with psycopg.connect(
            **database_config(root),
            # On choisit ici si les instructions sont validées automatiquement hors d’un bloc
            # transactionnel explicite.
            autocommit=False,
            # On fournit les choix que ce contrôle doit proposer à l’utilisateur.
            options="-c default_transaction_read_only=on",
        ) as conn:
            # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
            try:
                # On envoie cette requête à conn avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                conn.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                # On appelle verify_import_identity avec conn.execute('SELECT
                # current_database(),current_user,session_user').fetchone().
                verify_import_identity(
                    conn.execute(
                        "SELECT current_database(),current_user,session_user"
                    ).fetchone()
                )
                # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou
                # des présenter.
                rows = conn.execute(
                    "SELECT "
                    + ",".join(COLUMNS)
                    + " FROM core.workflow_execution_events "
                    "WHERE workflow_execution_id=%s ORDER BY event_sequence",
                    (wid,),
                ).fetchall()
                # On exige ici que [dict(zip(COLUMNS, r)) for r in rows] correspond à
                # [normalize_event(e) for e in events]. Si ce n’est pas le cas, le message associé
                # bloque la suite.
                require(
                    [dict(zip(COLUMNS, r)) for r in rows]
                    == [normalize_event(e) for e in events],
                    "LOCAL_SQL_JOURNAL_MISMATCH",
                )
                # On exige ici que conn.execute('SELECT publication_id FROM
                # core.excel_current_publication W… correspond à [(pub,)]. Si ce n’est pas le cas, le
                # message associé bloque la suite.
                require(
                    conn.execute(
                        "SELECT publication_id FROM core.excel_current_publication WHERE singleton=true"
                    ).fetchall()
                    == [(pub,)],
                    "EXCEL_CURRENT_POINTER_MISMATCH",
                )
                # On recontrôle les métadonnées du fichier ; un changement pendant la lecture
                # rendrait le lot difficile à rattacher à une version précise.
                require(
                    conn.execute(
                        "SELECT project_year,status,excel_publication_id,manifest_path,manifest_sha256,manifest_payload FROM core.pipeline_runs WHERE pipeline_execution_id=%s",
                        (pipeline,),
                    ).fetchall()
                    == [
                        (
                            2026,
                            "success",
                            pub,
                            manifest_relative,
                            hashlib.sha256(manifest_bytes).hexdigest(),
                            manifest,
                        )
                    ],
                    "PIPELINE_REFERENCE_MISMATCH",
                )
                # On prépare summaries comme liste vide ; on la remplira au fil des opérations
                # suivantes.
                summaries = []
                # On parcourt VINEYARDS ; vineyard désigne l’élément courant à chaque passage dans la
                # boucle.
                for vineyard in VINEYARDS:
                    # On garde dans active toutes les lignes encore disponibles dans le résultat SQL.
                    active = conn.execute(
                        """SELECT c.vineyard_key,c.reconciliation_run_id,c.pipeline_execution_id,
                        r.nas_pipeline_execution_id,r.excel_publication_id,r.acquisition_rows,r.association_rows,r.passage_rows
                        FROM core.current_vineyard_reconciliations c JOIN core.vineyards v ON v.vineyard_key=c.vineyard_key
                        JOIN core.reconciliation_runs r ON r.pipeline_execution_id=c.pipeline_execution_id
                        AND r.vineyard_key=c.vineyard_key AND r.reconciliation_run_id=c.reconciliation_run_id
                        WHERE lower(v.vineyard_name)=lower(%s)""",
                        (vineyard,),
                    ).fetchall()
                    # On exige ici que len(active) correspond à 1. Si ce n’est pas le cas, le message
                    # associé bloque la suite.
                    require(
                        len(active) == 1, "ACTIVE_VINEYARD_RESULT_MISSING:" + vineyard
                    )
                    # On récupère active[0] et on le garde dans (key, rec, pid, nas, rpub, *counts)
                    # pour la suite.
                    key, rec, pid, nas, rpub, *counts = active[0]
                    # On exige ici que (pid, nas, rpub) correspond à (pipeline, pipeline, pub). Si ce
                    # n’est pas le cas, le message associé bloque la suite.
                    require(
                        (pid, nas, rpub) == (pipeline, pipeline, pub),
                        "ACTIVE_VINEYARD_LINKS_MISMATCH:" + vineyard,
                    )
                    # On parcourt ces collections en parallèle ; les éléments de même position
                    # seront comparés ou associés dans le corps de la boucle.
                    for table, count in zip(
                        (
                            "reconciliation_acquisition_rows",
                            "reconciliation_association_rows",
                            "reconciliation_passage_rows",
                        ),
                        counts,
                    ):
                        # On exige ici que conn.execute('SELECT COUNT(*) FROM staging.' + table + '
                        # WHERE pipeline_e… correspond à count. Si ce n’est pas le cas, le message
                        # associé bloque la suite.
                        require(
                            conn.execute(
                                "SELECT COUNT(*) FROM staging."
                                + table
                                + " WHERE pipeline_execution_id=%s "
                                "AND vineyard_key=%s AND reconciliation_run_id=%s",
                                (pipeline, key, rec),
                            ).fetchone()[0]
                            == count,
                            "SQL_VOLUME_MISMATCH",
                        )
                    # On ajoute (vineyard, counts) à la fin de summaries ; les éléments précédents
                    # restent conservés.
                    summaries.append((vineyard, counts))
                # On exige ici que manifest_path.read_bytes() correspond à manifest_bytes. Si ce n’est
                # pas le cas, le message associé bloque la suite.
                require(
                    manifest_path.read_bytes() == manifest_bytes,
                    "LOCAL_MANIFEST_CHANGED",
                )
                # On vérifie l’empreinte du contenu par rapport au lot annoncé ; avoir le bon nom de
                # fichier ne suffit pas à identifier sa version.
                require(
                    hashlib.sha256(journal.read_bytes()).digest() == digest,
                    "LOCAL_JOURNAL_CHANGED",
                )
            finally:
                # On annule les écritures non validées dans cette transaction, sans prétendre annuler
                # les opérations déjà commises ailleurs.
                conn.rollback()
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT AIRFLOW CONFIRME : recu partage Windows/Docker ; journal local/SQL 18/18 ; huit etapes."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Mode du journal : "
            + receipt["trigger_mode"]
            + " ; huit vignobles approuves, annee 2026."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Workflow : "
            + wid
            + " ; publication Excel : "
            + pub
            + " ; traitement NAS : "
            + pipeline
        )
        # On parcourt summaries ; (vineyard, counts) désigne l’élément courant à chaque passage dans la
        # boucle.
        for vineyard, counts in summaries:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                vineyard
                + " : %d acquisitions ; %d associations ; %d passages." % tuple(counts)
            )
        # On affiche ce texte explicite dans la sortie du programme.
        print("Aucune ecriture SQL, aucune consultation NAS, aucun nouveau workflow.")
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as e:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "CONTROLE NON CONFIRME : "
            + (str(e) if isinstance(e, ResultCheckError) else type(e).__name__)
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print("Pas de relance automatique ; examiner les traces conservees.")
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine le programme avec ce code de sortie pour que l’appelant puisse distinguer réussite et
    # échec.
    sys.exit(main())
