# Lecture du fichier — Contrat du parcours principal : périmètre autorisé, déclenchement et reçu attendu.
# On décrit les conditions de lancement avant de lire les sources. Le reçu ressemble à un bordereau :
# on vérifie ses identifiants et les étapes annoncées, pas seulement sa présence.
#

"""Perimetre approuve, sans acces fichier, reseau ou configuration a l'import."""

# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On utilise les règles du fuseau demandé, notamment lors des changements d’heure.
from zoneinfo import ZoneInfo
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles UUID depuis uuid, pour les appels de ce fichier.
from uuid import UUID

# On garde dans ROOT un objet chemin local ; sa construction seule ne prouve pas que le fichier existe.
ROOT = Path("/opt/project")
# On garde dans BUSINESS_PYTHON un objet chemin local ; sa construction seule ne prouve pas que le
# fichier existe.
BUSINESS_PYTHON = Path("/home/airflow/.local/bin/python")
# On fixe SCOPE_ID à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
SCOPE_ID = "eight_vineyards_2026_v1"
# On fixe YEAR à 2026 pour cette étape.
YEAR = 2026
# On rassemble dans VINEYARDS les 8 éléments explicitement indiqués, en conservant leur structure.
VINEYARDS = (
    "DomaineDemoA",
    "DomaineDemoB",
    "DomaineDemoC",
    "DomaineDemoD",
    "DomaineDemoE",
    "DomaineDemoF",
    "DomaineDemoG",
    "DomaineDemoH",
)
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
# On fixe CHILD_TIMEOUT à 1200 pour cette étape.
CHILD_TIMEOUT = 1200
# On fixe RUN_TIMEOUT à 10800 pour cette étape.
RUN_TIMEOUT = 10800


class EightControlError(ValueError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(ok, code):
    # On prévoit le cas où ok est évalué comme faux, par exemple une valeur vide selon son type.
    if not ok:
        # On interrompt cette branche avec EightControlError.
        raise EightControlError(code)


# On décrit explicitement le périmètre qui doit accompagner le lancement et son reçu.
def scope():
    # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
    return dict(
        # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
        year=YEAR,
        # On transmet la sélection explicite des domaines concernés par cet appel.
        vineyards=list(VINEYARDS),
        # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
        all_vineyards=False,
        execution_kind="business",
    )


# On vérifie le type de déclenchement et les confirmations attendues avant d’autoriser la suite.
def validate_trigger(run_type, conf, scheduled_for=None, now=None):
    # On vérifie ce cas avant la suite : getattr(run_type, 'value', run_type) correspond au texte
    # 'scheduled'.
    if getattr(run_type, "value", run_type) == "scheduled":
        # Un run planifié ne doit pas profiter d’une configuration injectée pour élargir son
        # périmètre. Seule l’absence de surcharge, ou la forme neutre attendue, est acceptée.
        require(
            conf in (None, {})
            or (
                isinstance(conf, dict)
                # On exige aussi que set(conf) correspond à {'scope_id', 'allow_business_writes',
                # 'confirm_nas_read_only'}.
                and set(conf)
                == {"scope_id", "allow_business_writes", "confirm_nas_read_only"}
                # On exige aussi que conf.get('scope_id') correspond à SCOPE_ID.
                and conf.get("scope_id") == SCOPE_ID
                # On exige aussi que conf.get('allow_business_writes') est exactement la valeur fausse
                # (False).
                and conf.get("allow_business_writes") is False
                # On exige aussi que conf.get('confirm_nas_read_only') est exactement la valeur fausse
                # (False).
                and conf.get("confirm_nas_read_only") is False
            ),
            "SCHEDULED_CONFIGURATION_OVERRIDE_REFUSED",
        )
        # On appelle validate_scheduled_time avec scheduled_for.
        validate_scheduled_time(scheduled_for, now=now)
        # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont pas
        # exécutées.
        return

    # Ce parcours attend un lancement manuel : on ne le laisse pas accepter un autre type de run par
    # défaut.
    require(getattr(run_type, "value", run_type) == "manual", "MANUAL_TRIGGER_REQUIRED")
    # Le lancement manuel doit désigner le périmètre prévu et confirmer séparément les écritures
    # métier et la lecture seule du NAS. Une valeur simplement non vide ne remplace pas le booléen
    # True.
    require(
        isinstance(conf, dict)
        # On exige aussi que conf.get('scope_id') correspond à SCOPE_ID.
        and conf.get("scope_id") == SCOPE_ID
        # On exige aussi que conf.get('allow_business_writes') est exactement la valeur vraie (True).
        and conf.get("allow_business_writes") is True
        # On exige aussi que conf.get('confirm_nas_read_only') est exactement la valeur vraie (True).
        and conf.get("confirm_nas_read_only") is True
        # On exige aussi que set(conf) correspond à {'scope_id', 'allow_business_writes',
        # 'confirm_nas_read_only'}.
        and set(conf) == {"scope_id", "allow_business_writes", "confirm_nas_read_only"},
        "EXPLICIT_EIGHT_CONFIRMATIONS_REQUIRED",
    )


# On compare le périmètre reçu au périmètre explicitement autorisé.
def validate_names(names):
    # On attend exactement les huit domaines prévus, dans cet ordre ; accepter une sous-liste ou un
    # nom supplémentaire changerait le périmètre approuvé.
    require(
        isinstance(names, (list, tuple)) and tuple(names) == VINEYARDS,
        "EIGHT_SCOPE_MISMATCH",
    )


# On vérifie le reçu avant d’en extraire les identifiants transmis à Airflow.
def result_from_receipt(data, share_id):
    # Le reçu doit confirmer à la fois la réussite, les huit étapes, le mode, le périmètre et le
    # partage d’état. Un fichier JSON présent ne suffit pas.
    require(
        isinstance(data, dict)
        # On exige aussi que data.get('kind') correspond au texte 'execution'.
        and data.get("kind") == "execution"
        # On exige aussi que data.get('status') correspond au texte 'success'.
        and data.get("status") == "success"
        # On exige aussi que data.get('completed_steps') correspond à 8.
        and data.get("completed_steps") == 8
        # On exige aussi que data.get('trigger_mode') appartient à ('airflow_manual',
        # 'airflow_scheduled').
        and data.get("trigger_mode") in ("airflow_manual", "airflow_scheduled")
        # On exige aussi que data.get('scope_id') correspond à SCOPE_ID.
        and data.get("scope_id") == SCOPE_ID
        # On exige aussi que data.get('share_id') correspond à share_id.
        and data.get("share_id") == share_id,
        "EIGHT_RECEIPT_NOT_SUCCESS",
    )
    # On appelle validate_names avec data.get('vineyards').
    validate_names(data.get("vineyards"))
    # On valide et normalise l’UUID du run avant de s’en servir pour reconstruire le chemin attendu
    # de son journal.
    wid = str(UUID(data["workflow_execution_id"]))
    # L’identifiant du workflow détermine le dossier du journal ; ce contrôle évite de rattacher le
    # reçu au journal d’un autre run.
    require(
        data.get("journal_relative_path")
        == "data/03_normalized/workflow_runs/" + UUID(wid).hex + "/events.jsonl",
        "EIGHT_JOURNAL_PATH_MISMATCH",
    )
    # Il faut les identifiants des deux lots, Excel et NAS, pour rattacher le résultat aux données
    # qui ont réellement été croisées.
    require(
        all(
            isinstance(data.get(k), str) and data[k]
            for k in ("excel_publication_id", "pipeline_execution_id")
        ),
        "RESULT_IDENTIFIERS_MISSING",
    )
    # On ne renvoie que les champs utiles à la tâche Airflow ; le reçu contrôlé reste la source du
    # détail complet.
    return {
        k: data[k]
        for k in (
            "workflow_execution_id",
            "status",
            "completed_steps",
            "journal_relative_path",
            "excel_publication_id",
            "pipeline_execution_id",
            "trigger_mode",
            "scope_id",
            "vineyards",
        )
    }


# On fixe SCHEDULE_GRACE_SECONDS à 120 pour cette étape.
SCHEDULE_GRACE_SECONDS = 120


# On contrôle la fenêtre temporelle prévue pour un lancement planifié.
def validate_scheduled_time(scheduled_for, now=None):
    # Sans fuseau, une heure locale serait ambiguë lors d’un changement d’heure ou d’un
    # rapprochement avec des événements en UTC.
    require(
        isinstance(scheduled_for, datetime) and scheduled_for.tzinfo is not None,
        "SCHEDULED_DEADLINE_REQUIRED",
    )
    # On convertit l’échéance en heure de Paris en utilisant les règles du fuseau ; le passage heure
    # d’été/heure d’hiver est ainsi pris en compte.
    local = scheduled_for.astimezone(ZoneInfo("Europe/Paris"))
    # On raisonne en heure de Paris et on exige 10 h exactement ; un décalage UTC fixe serait faux
    # une partie de l’année.
    require(
        (local.hour, local.minute, local.second, local.microsecond) == (10, 0, 0, 0),
        "SCHEDULED_HOUR_INVALID",
    )
    # On retient pour now la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    now = now or datetime.now(timezone.utc)
    # L’heure de comparaison doit porter son fuseau, elle aussi, pour calculer un retard sans
    # ambiguïté.
    require(
        isinstance(now, datetime) and now.tzinfo is not None, "AWARE_CLOCK_REQUIRED"
    )
    # On compare les deux instants en UTC et on convertit l’écart en secondes ; un âge positif
    # mesure le retard depuis l’échéance.
    age = (
        now.astimezone(timezone.utc) - scheduled_for.astimezone(timezone.utc)
    ).total_seconds()
    # Un âge négatif signifie que l’échéance n’est pas encore atteinte ; on n’autorise pas une
    # exécution en avance.
    require(age >= 0, "SCHEDULED_RUN_TOO_EARLY")
    # Au-delà de la petite fenêtre prévue, on ignore ce départ plutôt que rattraper tardivement un
    # traitement censé commencer à l’heure.
    require(age <= SCHEDULE_GRACE_SECONDS, "SCHEDULED_RUN_EXPIRED_NO_CATCHUP")
