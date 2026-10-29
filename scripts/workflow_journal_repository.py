# Lecture du fichier — Validation et enregistrement des événements du journal métier.
# On conserve ce qui s’est passé, avec une séquence et des identifiants. Ce carnet se trouve dans la
# base métier, pas dans la base technique d’Airflow.
#

"""Ecriture append-only du journal ; aucune connexion ou operation a l'import.
Le pilote complet devra verifier sa connexion et conserver un journal local.
Ce module seul ne lance ni pipeline, ni NAS, ni synchronisation automatique.
"""

# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Decimal depuis decimal, pour les appels de ce fichier.
from decimal import Decimal
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles PurePosixPath depuis pathlib, pour les appels de ce fichier.
from pathlib import PurePosixPath
# On rend disponibles UUID depuis uuid, pour les appels de ce fichier.
from uuid import UUID

# On rassemble dans COLUMNS les 17 éléments explicitement indiqués, en conservant leur structure.
COLUMNS = (
    "event_id",
    "workflow_execution_id",
    "event_sequence",
    "occurred_at",
    "trigger_mode",
    "event_type",
    "stage",
    "status",
    "attempt_number",
    "scope_payload",
    "metrics_payload",
    "excel_publication_id",
    "pipeline_execution_id",
    "message",
    "error_code",
    "log_relative_path",
    "duration_seconds",
)
# On rassemble dans MODES les 4 éléments explicitement indiqués, en conservant leur structure.
MODES = {"manual_script", "airflow_manual", "airflow_scheduled", "integration_test"}
# On rassemble dans STATUSES les 6 éléments explicitement indiqués, en conservant leur structure.
STATUSES = {"started", "running", "success", "failed", "interrupted", "skipped"}


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(condition, message):
    # On prévoit le cas où condition est évalué comme faux, par exemple une valeur vide selon son type.
    if not condition:
        # On interrompt cette branche avec ValueError.
        raise ValueError(message)


# On contrôle et normalise la structure d’un événement avant son enregistrement.
def normalize_event(event):
    # On exige ici que l’événement en cours est du type dict. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(isinstance(event, dict), "Evenement non objet.")
    # On exige ici que la condition set(event) - set(COLUMNS) n’est pas remplie. Si ce n’est pas le
    # cas, le message associé bloque la suite.
    require(not set(event) - set(COLUMNS), "Champ d evenement non reconnu.")
    # On indexe le résultat par key, avec event.get(key) comme valeur ; les contrôles d’unicité sont
    # importants car une même clé ne garde qu’une valeur dans un dictionnaire.
    e = {key: event.get(key) for key in COLUMNS}
    # On parcourt ('event_id', 'workflow_execution_id') ; key désigne l’élément courant à chaque
    # passage dans la boucle.
    for key in ("event_id", "workflow_execution_id"):
        # On tente ce bloc et on traite séparément les erreurs prévues : (ValueError, TypeError,
        # AttributeError).
        try:
            # On garde dans e[key] un UUID interprété et validé à partir de la valeur fournie.
            e[key] = UUID(str(e[key]))
        except (ValueError, TypeError, AttributeError):
            # On interrompt cette branche avec ValueError : 'Identifiant UUID invalide.'.
            raise ValueError("Identifiant UUID invalide.") from None
    # On parcourt (('event_sequence', None), ('attempt_number', 1)) ; (key, default) désigne l’élément
    # courant à chaque passage dans la boucle.
    for key, default in (("event_sequence", None), ("attempt_number", 1)):
        # On garde dans e[key] le champ key de event avec le repli indiqué si la clé est absente.
        e[key] = event.get(key, default)
        # On exige ici que type(e[key]) est exactement int et e[key] est supérieur à 0. Si ce n’est pas
        # le cas, le message associé bloque la suite.
        require(type(e[key]) is int and e[key] > 0, "Sequence ou tentative invalide.")
    # On récupère la date de l’événement dans e et on le garde dans when pour la suite.
    when = e["occurred_at"]
    # On réserve cette branche à when lorsqu’il est de type str.
    if isinstance(when, str):
        # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
        try:
            # On interprète la date ISO reçue ; les vérifications de fuseau et de cohérence restent
            # nécessaires après cette conversion.
            when = datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            # On interrompt cette branche avec ValueError : 'Date d evenement invalide.'.
            raise ValueError("Date d evenement invalide.") from None
    # Sans fuseau, une heure locale serait ambiguë lors d’un changement d’heure ou d’un
    # rapprochement avec des événements en UTC.
    require(
        isinstance(when, datetime)
        # On exige aussi que when.tzinfo est renseigné (différent de None).
        and when.tzinfo is not None
        # On exige aussi que when.utcoffset() est renseigné (différent de None).
        and when.utcoffset() is not None,
        "Date sans fuseau horaire.",
    )
    # On garde dans e['occurred_at'] le même instant que when, exprimé dans le fuseau demandé.
    e["occurred_at"] = when.astimezone(timezone.utc)
    # On exige ici que l’origine du déclenchement dans e appartient à MODES. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(e["trigger_mode"] in MODES, "Mode de declenchement invalide.")
    # On exige ici que e['event_type'] appartient à {'workflow', 'step', 'quality'}. Si ce n’est pas le
    # cas, le message associé bloque la suite.
    require(
        e["event_type"] in {"workflow", "step", "quality"}, "Type d evenement invalide."
    )
    # On exige ici que l’état du traitement dans e appartient à STATUSES. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(e["status"] in STATUSES, "Statut invalide.")
    # On exige ici que l’étape concernée dans e est du type str et le contrôle bool(e['stage'].strip())
    # est positif. Si ce n’est pas le cas, le message associé bloque la suite.
    require(isinstance(e["stage"], str) and bool(e["stage"].strip()), "Etape vide.")
    # On parcourt ('scope_payload', 'metrics_payload') ; key désigne l’élément courant à chaque passage
    # dans la boucle.
    for key in ("scope_payload", "metrics_payload"):
        # On garde dans e[key] le champ key de event avec le repli indiqué si la clé est absente.
        e[key] = event.get(key, {})
        # On exige ici que e[key] est du type dict. Si ce n’est pas le cas, le message associé bloque
        # la suite.
        require(isinstance(e[key], dict), "Payload du journal non objet.")
        # Defensive copy and strict JSON: no nonfinite numbers or custom values.
        e[key] = json.loads(json.dumps(e[key], allow_nan=False, ensure_ascii=False))
    # On parcourt ('excel_publication_id', 'pipeline_execution_id', 'message', 'error_code'… ; key
    # désigne l’élément courant à chaque passage dans la boucle.
    for key in (
        "excel_publication_id",
        "pipeline_execution_id",
        "message",
        "error_code",
        "log_relative_path",
    ):
        # On exige ici que e[key] vaut None ou e[key] est du type str. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(e[key] is None or isinstance(e[key], str), "Champ texte invalide.")
    # On exige ici que e['message'] vaut None ou len(e['message']) ne dépasse pas 2000. Si ce n’est pas
    # le cas, le message associé bloque la suite.
    require(e["message"] is None or len(e["message"]) <= 2000, "Message trop long.")
    # On récupère le chemin relatif de la trace dans e et on le garde dans path pour la suite.
    path = e["log_relative_path"]
    # On vérifie ce cas avant la suite : le chemin de travail est renseigné (différent de None).
    if path is not None:
        # On garde PurePosixPath(path).parts sous le nom parts ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        parts = PurePosixPath(path).parts
        # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas,
        # le message associé bloque la suite.
        require(
            parts
            # On exige aussi que parts[0] appartient à {'data', 'logs'}.
            and parts[0] in {"data", "logs"}
            # On exige aussi que la condition path.startswith('/') n’est pas remplie.
            and not path.startswith("/")
            # On exige aussi que le texte '\\' ne figure pas dans le chemin de travail.
            and "\\" not in path
            # On exige aussi que le texte '..' ne figure pas dans parts.
            and ".." not in parts,
            "Chemin du log non local relatif.",
        )
    # On vérifie ce cas avant la suite : la durée en secondes dans e est renseigné (différent de None).
    if e["duration_seconds"] is not None:
        # On exige ici que le type reçu ne correspond pas à bool. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(not isinstance(e["duration_seconds"], bool), "Duree invalide.")
        # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
        try:
            # On garde dans duration la valeur renvoyée par Decimal.
            duration = Decimal(str(e["duration_seconds"]))
        except Exception:
            # On interrompt cette branche avec ValueError : 'Duree invalide.'.
            raise ValueError("Duree invalide.") from None
        # On exige ici que le contrôle duration.is_finite() est positif et duration est au moins égal à
        # 0. Si ce n’est pas le cas, le message associé bloque la suite.
        require(duration.is_finite() and duration >= 0, "Duree invalide.")
        # On garde duration sous le nom e['duration_seconds'] ; cette affectation ne copie pas à elle
        # seule un objet mutable.
        e["duration_seconds"] = duration
    # On remet e à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return e


# On ajoute l’événement selon les règles du dépôt, sans réécrire les événements précédents.
def append_event(connection, event):
    """Transaction courte ; doublon identique reutilise, contradiction refusee.
    Le compte appeleur doit etre authentifie/autorise par le pilote.
    Le verrou commun serialize la verification puis l'insertion sans FOR UPDATE
    sur les evenements historiques. Compatible avec une transaction externe.
    """
    # On contrôle et normalise les champs du journal avant des conserver, pour garder le même
    # format entre fichier local et base métier.
    e = normalize_event(event)
    # On rend disponibles Jsonb depuis psycopg.types.json, pour les appels de ce fichier.
    from psycopg.types.json import Jsonb

    # On garde dans names le texte formé en réunissant les éléments avec ',' comme séparateur.
    names = ",".join(COLUMNS)
    # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre pas tout
    # le workflow.
    with connection.transaction():
        # On interroge les valeurs enregistrées en base pour ce contrôle ; les paramètres séparés de
        # la requête fournissent les valeurs recherchées.
        connection.execute("SELECT pg_advisory_xact_lock(%s,%s)", (120026, 1))
        # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
        # présenter.
        rows = connection.execute(
            "SELECT "
            + names
            + " FROM core.workflow_execution_events WHERE event_id=%s OR (workflow_execution_id=%s AND event_sequence=%s)",
            (e["event_id"], e["workflow_execution_id"], e["event_sequence"]),
        ).fetchall()
        # Cette branche traite le cas où les lignes est évalué comme vrai.
        if rows:
            # On exige ici que len(rows) correspond à 1 et dict(zip(COLUMNS, rows[0])) correspond à e.
            # Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                len(rows) == 1 and dict(zip(COLUMNS, rows[0])) == e,
                "Evenement existant contradictoire : aucune modification autorisee.",
            )
            # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
            return "reused"
        # On récupère une seule ligne du résultat SQL ; les contrôles suivants vérifient les valeurs
        # attendues.
        previous = connection.execute(
            "SELECT event_sequence,trigger_mode,scope_payload FROM core.workflow_execution_events WHERE workflow_execution_id=%s ORDER BY event_sequence DESC LIMIT 1",
            (e["workflow_execution_id"],),
        ).fetchone()
        # On exige ici que le numéro d’ordre de l’événement dans e correspond à previous[0] + 1 if
        # previous else 1. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            e["event_sequence"] == (previous[0] + 1 if previous else 1),
            "Sequence non consecutive.",
        )
        # Cette branche traite le cas où previous est évalué comme vrai.
        if previous:
            # On exige ici que previous[1] correspond à l’origine du déclenchement dans e et
            # previous[2] correspond au périmètre détaillé enregistré dans e. Si ce n’est pas le cas,
            # le message associé bloque la suite.
            require(
                previous[1] == e["trigger_mode"] and previous[2] == e["scope_payload"],
                "Mode ou perimetre contradictoire pour la tentative.",
            )
        # On construit values comme une liste à partir de Jsonb(e[key]) if key.endswith('_payload')
        # else e[key], pour chaque key de COLUMNS.
        values = [
            Jsonb(e[key]) if key.endswith("_payload") else e[key] for key in COLUMNS
        ]
        # On insère les données avec des paramètres SQL séparés du texte de la requête ; les
        # contrôles de doublons restent définis par le repository et les contraintes.
        connection.execute(
            "INSERT INTO core.workflow_execution_events ("
            + names
            + ") VALUES ("
            + ",".join(["%s"] * len(COLUMNS))
            + ")",
            values,
        )
    # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
    return "inserted"
