# Lecture du fichier — Moteur du workflow : verrou local, contexte partagé, étapes et journal.
# On pose un panneau « traitement en cours » pour éviter les lancements concurrents dans ce périmètre
# local. Le journal permet ensuite de suivre les étapes, sans effacer les incidents précédents.
#

"""Socle commun testable, sans connexion ni traitement automatique a l'import.
Les adaptateurs Excel, NAS et PostgreSQL sont assemblés dans workflow_assembly.py.
Ce module gère le verrou, les étapes et leur journal ; il ne choisit pas les sources.
"""

# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On rend disponibles Decimal depuis decimal, pour les appels de ce fichier.
from decimal import Decimal
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe socket. Ce module sera utilisé par les opérations de ce fichier.
import socket
# On importe time. On mesure des durées ou on gère les attentes prévues par ce fichier.
import time
# On rend disponibles UUID, uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import UUID, uuid4

# On rend disponibles normalize_event depuis workflow_journal_repository, pour les appels de ce
# fichier.
from workflow_journal_repository import normalize_event

# On fixe LOCK_RELATIVE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
LOCK_RELATIVE = "state/workflow_execution/workflow.lock"
# On fixe RUNS_RELATIVE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
RUNS_RELATIVE = "data/03_normalized/workflow_runs"


class WorkflowBusy(RuntimeError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


class JournalDeliveryError(RuntimeError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


# On produit l’instant courant en UTC avec son fuseau pour éviter les heures locales ambiguës.
def utc_now():
    # On fournit à l’appelant la représentation ISO de datetime.now(timezone.utc).
    return datetime.now(timezone.utc).isoformat()


# On construit un chemin et on vérifie qu’il reste dans le périmètre local autorisé par ce module.
def local_path(root, relative):
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où la condition root.is_dir() n’est pas remplie.
    if not root.is_dir():
        # On interrompt cette branche avec ValueError : 'Racine locale du projet absente.'.
        raise ValueError("Racine locale du projet absente.")
    # On calcule ce quotient pour construire path.
    path = root / relative
    # Le verrou et les traces doivent rester sous la racine locale du workflow.
    if not path.resolve().is_relative_to(root):
        # On interrompt cette branche avec ValueError : 'Destination du socle hors du projet local.'.
        raise ValueError("Destination du socle hors du projet local.")
    # On remet le chemin de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return path


# On crée le verrou exclusivement, puis seul son propriétaire peut le libérer.
@contextmanager
def workflow_lock(root, workflow_id):
    """Creation exclusive ; aucun vol de verrou ancien, liberation du seul proprietaire."""
    # On vérifie le format UUID, puis on garde sa représentation normalisée comme identité du
    # propriétaire du verrou.
    owner = str(UUID(str(workflow_id)))
    # Le verrou appartient au dossier state de cette copie du projet, pas à un emplacement choisi
    # librement par l’appelant.
    path = local_path(root, LOCK_RELATIVE)
    # On prépare le dossier local nécessaire à cette sortie ; créer le dossier ne produit pas encore
    # le fichier qu’il contiendra.
    path.parent.mkdir(parents=True, exist_ok=True)
    # On garde dans payload les octets de json.dumps({'workflow_execution_id': owner, 'pid':
    # os.getpid(),… obtenus avec l’encodage indiqué.
    payload = json.dumps(
        {
            # On renseigne l’identifiant de l’exécution du workflow sous la clé
            # 'workflow_execution_id'.
            "workflow_execution_id": owner,
            # On associe la clé 'pid' à cette valeur dans cet objet.
            "pid": os.getpid(),
            # On associe la clé 'hostname' à cette valeur dans cet objet.
            "hostname": socket.gethostname(),
            # On associe la clé 'created_at' à cette valeur dans cet objet.
            "created_at": utc_now(),
        },
        # On fixe ici l’ordre des clés sérialisées, utile pour obtenir une représentation stable.
        sort_keys=True,
    ).encode("utf-8")
    # On tente ce bloc et on traite séparément les erreurs prévues : FileExistsError.
    try:
        # O_EXCL refuse de créer un verrou déjà présent : deux candidats ne doivent pas pouvoir le
        # prendre ensemble.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        # On interrompt cette branche avec WorkflowBusy.
        raise WorkflowBusy(
            "Une execution ou un verrou restant bloque le lancement ; aucun nettoyage automatique."
        ) from None
    # Une erreur d'ecriture laisse volontairement le verrou pour diagnostic.
    with os.fdopen(fd, "wb") as handle:
        # On écrit payload dans handle ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout
        # ou d’un remplacement.
        handle.write(payload)
        # On vidu tampon d’écriture de handle vers sa destination ; cela ne remplace pas, à lui
        # seul, une synchronisation durable du fichier.
        handle.flush()
        # On demande la synchronisation des octets du verrou ; ce n’est pas une garantie de reprise
        # complète du traitement.
        os.fsync(handle.fileno())
    # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
    try:
        # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après ce
        # point si son itération continue.
        yield path
    finally:
        # Cette branche traite le cas où la condition path.is_file() n’est pas remplie ou
        # path.read_bytes() diffère du contenu détaillé.
        if not path.is_file() or path.read_bytes() != payload:
            # On interrompt cette branche avec RuntimeError : 'Proprietaire du verrou change : aucune
            # suppression effectuee.'.
            raise RuntimeError(
                "Proprietaire du verrou change : aucune suppression effectuee."
            )
        # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
        # d’autres fichiers.
        path.unlink()


def serializable(event):
    """Normalisation commune avec le repository, puis format JSON rejouable."""
    # On contrôle et normalise les champs du journal avant des conserver, pour garder le même
    # format entre fichier local et base métier.
    normalized = normalize_event(event)

    # On convertit les types explicitement prévus en valeurs sérialisables et on refuse les autres.
    def convert(value):
        # On réserve cette branche à value lorsqu’il est de type UUID.
        if isinstance(value, UUID):
            # On fournit à l’appelant la représentation textuelle de la valeur reçue.
            return str(value)
        # On réserve cette branche à value lorsqu’il est de type datetime.
        if isinstance(value, datetime):
            # On fournit à l’appelant la représentation ISO de value.
            return value.isoformat()
        # On réserve cette branche à value lorsqu’il est de type Decimal.
        if isinstance(value, Decimal):
            # On fournit à l’appelant la représentation textuelle de la valeur reçue.
            return str(value)
        # On interrompt cette branche avec TypeError : 'Type du journal non serialisable.'.
        raise TypeError("Type du journal non serialisable.")

    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    return json.loads(
        json.dumps(normalized, default=convert, ensure_ascii=False, allow_nan=False)
    )


class WorkflowContext:
    # Ce contexte gardes résultats des étapes et les identifiants des lots utilisés par une même
    # exécution.
    def __init__(self, root, workflow_id):
        # On garde dans self.root le chemin absolu résolu de Path(root), en tenant compte des liens
        # symboliques.
        self.root = Path(root).resolve()
        # On garde l’identifiant de cette exécution sous le nom self.workflow_execution_id ; cette
        # affectation ne copie pas à elle seule un objet mutable.
        self.workflow_execution_id = workflow_id
        # Le contexte commence sans résultat ; les étapes le rempliront au fur et à mesure, sous
        # leur propre nom.
        self.results = {}
        # On gardera ici les identifiants des deux lots suivis par le workflow, séparément de son
        # propre identifiant.
        self._links = {"excel_publication_id": None, "pipeline_execution_id": None}

    # On rattache les identifiants au contexte sans autoriser leur remplacement par un autre lot.
    def pin_ids(self, *, excel_publication_id=None, pipeline_execution_id=None):
        # On parcourt (('excel_publication_id', excel_publication_id), ('pipeline_execution_id'… ;
        # (key, value) désigne l’élément courant à chaque passage dans la boucle.
        for key, value in (
            ("excel_publication_id", excel_publication_id),
            ("pipeline_execution_id", pipeline_execution_id),
        ):
            # On vérifie ce cas avant la suite : la valeur reçue vaut None.
            if value is None:
                # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
                continue
            # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition value
            # n’est pas remplie.
            if not isinstance(value, str) or not value:
                # On interrompt cette branche avec ValueError : 'Identifiant de resultat invalide.'.
                raise ValueError("Identifiant de resultat invalide.")
            # Cette branche traite le cas où self._links[key] est renseigné (différent de None) et
            # self._links[key] diffère de la valeur reçue.
            if self._links[key] is not None and self._links[key] != value:
                # On interrompt cette branche avec ValueError : 'Identifiant deja fige pour cette
                # execution.'.
                raise ValueError("Identifiant deja fige pour cette execution.")
        # On parcourt (('excel_publication_id', excel_publication_id), ('pipeline_execution_id'… ;
        # (key, value) désigne l’élément courant à chaque passage dans la boucle.
        for key, value in (
            ("excel_publication_id", excel_publication_id),
            ("pipeline_execution_id", pipeline_execution_id),
        ):
            # On vérifie ce cas avant la suite : la valeur reçue est renseigné (différent de None).
            if value is not None:
                # On enregistre l’identifiant après les vérifications de la première boucle ; un lot
                # déjà lié ne peut pas être remplacé par un autre en cours de run.
                self._links[key] = value

    # On renvoie une copie des liens pour éviter de modifier le rangement interne par cet accès.
    def linked_ids(self):
        # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées (la
        # copie reste superficielle).
        return dict(self._links)


class LocalJournal:
    # Chaque exécution reçoit son dossier de journal et sa séquence d’événements.
    def __init__(self, root, workflow_id, trigger_mode, scope, sink=None):
        # On garde dans self.workflow_id la représentation textuelle de UUID(str(workflow_id)).
        self.workflow_id = str(UUID(str(workflow_id)))
        # On garde l’origine du déclenchement sous le nom self.trigger_mode ; cette affectation ne
        # copie pas à elle seule un objet mutable.
        self.trigger_mode = trigger_mode
        # On fixe self.sequence à 0 pour cette étape.
        self.sequence = 0
        # On garde sink sous le nom self.sink ; cette affectation ne copie pas à elle seule un objet
        # mutable.
        self.sink = sink
        # On garde dans seed la valeur renvoyée par serializable.
        seed = serializable(
            {
                # On renseigne l’identifiant stable de l’événement sous la clé 'event_id'.
                "event_id": str(uuid4()),
                # On renseigne l’identifiant de l’exécution du workflow sous la clé
                # 'workflow_execution_id'.
                "workflow_execution_id": self.workflow_id,
                # On renseigne le numéro d’ordre de l’événement sous la clé 'event_sequence'.
                "event_sequence": 1,
                # On renseigne la date de l’événement sous la clé 'occurred_at'.
                "occurred_at": utc_now(),
                # On renseigne l’origine du déclenchement sous la clé 'trigger_mode'.
                "trigger_mode": trigger_mode,
                # On associe la clé 'event_type' à cette valeur dans cet objet.
                "event_type": "workflow",
                # On renseigne l’étape concernée sous la clé 'stage'.
                "stage": "workflow",
                # On renseigne l’état du traitement sous la clé 'status'.
                "status": "started",
                # On renseigne le périmètre détaillé enregistré sous la clé 'scope_payload'.
                "scope_payload": scope,
            }
        )
        # On récupère le périmètre détaillé enregistré dans seed et on le garde dans self.scope pour la
        # suite.
        self.scope = seed["scope_payload"]
        # Cette branche traite le cas où sink est renseigné (différent de None) et la condition
        # callable(sink) n’est pas remplie.
        if sink is not None and not callable(sink):
            # On interrompt cette branche avec ValueError : 'Destinataire du journal non callable.'.
            raise ValueError("Destinataire du journal non callable.")
        # On assemble ces deux éléments pour construire relative.
        relative = RUNS_RELATIVE + "/" + UUID(self.workflow_id).hex + "/events.jsonl"
        # On garde dans self.path le chemin local après les contrôles de périmètre du module.
        self.path = local_path(root, relative)
        # On crée ce dossier en refusant un emplacement déjà existant ; cela évite de réutiliser
        # silencieusement les sorties d’un ancien essai.
        self.path.parent.mkdir(parents=True, exist_ok=False)
        # On ouvre le fichier en création exclusive : s’il existe déjà, on s’arrête au lieu de
        # l’écraser. Le bloc ferme le fichier à la sortie.
        with self.path.open("x", encoding="utf-8"):
            # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
            pass
        # On gardu chemin relatif sous le nom self.relative_path ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        self.relative_path = relative

    # On prépare puis émet l’information prévue par ce journal ou ce rapport.
    def emit(
        self,
        event_type,
        stage,
        status,
        *,
        links=None,
        error_code=None,
        completed_steps=None,
        duration=None,
        deliver=True,
    ):
        # On garde dans event la valeur renvoyée par serializable.
        event = serializable(
            {
                # On renseigne l’identifiant stable de l’événement sous la clé 'event_id'.
                "event_id": str(uuid4()),
                # On renseigne l’identifiant de l’exécution du workflow sous la clé
                # 'workflow_execution_id'.
                "workflow_execution_id": self.workflow_id,
                # On renseigne le numéro d’ordre de l’événement sous la clé 'event_sequence'.
                "event_sequence": self.sequence + 1,
                # On renseigne la date de l’événement sous la clé 'occurred_at'.
                "occurred_at": utc_now(),
                # On renseigne l’origine du déclenchement sous la clé 'trigger_mode'.
                "trigger_mode": self.trigger_mode,
                # On associe la clé 'event_type' à cette valeur dans cet objet.
                "event_type": event_type,
                # On renseigne l’étape concernée sous la clé 'stage'.
                "stage": stage,
                # On renseigne l’état du traitement sous la clé 'status'.
                "status": status,
                # On renseigne le périmètre détaillé enregistré sous la clé 'scope_payload'.
                "scope_payload": self.scope,
                # On renseigne les indicateurs détaillés enregistrés sous la clé 'metrics_payload'.
                "metrics_payload": {}
                if completed_steps is None
                else {"completed_steps": completed_steps},
                # On renseigne le code du problème rencontré sous la clé 'error_code'.
                "error_code": error_code,
                # On renseigne la durée en secondes sous la clé 'duration_seconds'.
                "duration_seconds": duration,
                # On renseigne le chemin relatif de la trace sous la clé 'log_relative_path'.
                "log_relative_path": self.relative_path,
                **(links or {}),
            }
        )
        # On assemble ces deux éléments pour construire line.
        line = (
            json.dumps(
                # On choisit ici si les caractères accentués doivent être échappés dans le JSON.
                event, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
            + "\n"
        )
        # On ouvre en ajout pour conserver les lignes précédentes du journal ; ce bloc ne remet pas
        # le fichier à zéro.
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            # On écrit line dans handle ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout
            # ou d’un remplacement.
            handle.write(line)
            # On vidu tampon d’écriture de handle vers sa destination ; cela ne remplace pas, à lui
            # seul, une synchronisation durable du fichier.
            handle.flush()
            # On demande la synchronisation de cette ligne du journal après le flush. Cela ne
            # remplace pas une stratégie complète de reprise du workflow.
            os.fsync(handle.fileno())
        # On avance le numéro seulement après l’écriture locale de l’événement ; cet ordre servira à
        # vérifier le journal à la relecture.
        self.sequence += 1
        # Cette branche traite le cas où deliver est évalué comme vrai et self.sink est renseigné
        # (différent de None).
        if deliver and self.sink is not None:
            # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
            try:
                # La mutation d'un destinataire ne doit pas affecter le journal local.
                self.sink(json.loads(line))
            except Exception:
                # On interrompt cette branche avec JournalDeliveryError : 'Transmission du journal non
                # confirmee ; evenement local conserve.'.
                raise JournalDeliveryError(
                    "Transmission du journal non confirmee ; evenement local conserve."
                ) from None
        # On remet l’événement en cours à l’appelant ; les étapes suivantes de cette fonction ne sont
        # plus parcourues.
        return event


# On relit les événements conservés dans le journal local.
def read_events(path):
    """Validation integrale avant retransmission ; fichier incomplet refuse, jamais repare."""
    # On lit le fichier comme du texte avec l’encodage indiqué ; ce n’est pas encore une validation
    # de son contenu métier.
    raw = Path(path).read_text(encoding="utf-8")
    # Cette branche traite le cas où la condition raw n’est pas remplie ou la condition
    # raw.endswith('\n') n’est pas remplie.
    if not raw or not raw.endswith("\n"):
        # On interrompt cette branche avec ValueError : 'Journal vide ou incomplet : diagnostic
        # requis.'.
        raise ValueError("Journal vide ou incomplet : diagnostic requis.")
    # Le format JSONL contient un objet par ligne. On relit et normalise toutes les lignes avant
    # d’en retransmettre une seule.
    events = [serializable(json.loads(line)) for line in raw.splitlines()]
    # Le premier événement sert de point de comparaison pour le run, le mode de déclenchement et le
    # périmètre des lignes suivantes.
    first = events[0]
    # On garde dans ids un ensemble vide, qui servira à repérer les valeurs déjà rencontrées.
    ids = set()
    # On recompte les événements à partir de 1 pour vérifier que le numéro enregistré suit bien
    # l’ordre des lignes.
    for sequence, event in enumerate(events, 1):
        # Cette branche traite le cas où le numéro d’ordre de l’événement dans event diffère de
        # sequence ou l’identifiant stable de l’événement dans event appartient à ids.
        if event["event_sequence"] != sequence or event["event_id"] in ids:
            # On interrompt cette branche avec ValueError : 'Sequence ou identifiant du journal
            # incoherent.'.
            raise ValueError("Sequence ou identifiant du journal incoherent.")
        # Cette branche traite le cas où au moins un élément satisfait le test indiqué.
        if any(
            event[key] != first[key]
            for key in ("workflow_execution_id", "trigger_mode", "scope_payload")
        ):
            # On interrompt cette branche avec ValueError : 'Execution, mode ou perimetre du journal
            # contradictoire.'.
            raise ValueError("Execution, mode ou perimetre du journal contradictoire.")
        # On mémorise cet identifiant pour détecter sa réapparition dans la suite du même journal.
        ids.add(event["event_id"])
    # On remet les événements du journal à l’appelant ; les étapes suivantes de cette fonction ne sont
    # plus parcourues.
    return events


# On retransmet les événements selon le contrat du journal ; on ne relance pas les étapes métier.
def replay_events(path, sink):
    """Rejoue les memes UUID et dates ; le repository decide inserted/reused."""
    # Cette branche traite le cas où la condition callable(sink) n’est pas remplie.
    if not callable(sink):
        # On interrompt cette branche avec ValueError : 'Destinataire du journal non callable.'.
        raise ValueError("Destinataire du journal non callable.")
    # On garde dans events les événements du journal local après validation de leur ordre et de leur
    # identité.
    events = read_events(path)
    # On parcourt les événements du journal ; event désigne l’élément courant à chaque passage dans la
    # boucle.
    for event in events:
        # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
        try:
            # On appelle sink avec event.
            sink(event)
        except Exception:
            # On interrompt cette branche avec JournalDeliveryError : 'Retransmission non confirmee ;
            # journal local conserve sans modification.'.
            raise JournalDeliveryError(
                "Retransmission non confirmee ; journal local conserve sans modification."
            ) from None
    # On fournit à l’appelant le nombre d’éléments des événements du journal.
    return len(events)


# On exécute les étapes dans l’ordre avec le même contexte et on journalise leur progression.
def run_workflow(
    root, steps, *, trigger_mode, scope, journal_sink=None, preflight=None
):
    """Enchaine des callbacks ; ce module ne fournit encore aucun adaptateur metier.
    Le verrou concerne les appels de ce socle partageant le meme repertoire state.
    Les echecs ne declenchent aucun rollback global ni reprise automatique.
    preflight optionnel : sous verrou, avant journal/etapes ; refus propage au lanceur.
    """
    # Cette branche traite le cas où preflight est renseigné (différent de None) et la condition
    # callable(preflight) n’est pas remplie.
    if preflight is not None and not callable(preflight):
        # On interrompt cette branche avec ValueError : 'Controle avant demarrage non callable.'.
        raise ValueError("Controle avant demarrage non callable.")
    # On garde dans steps une liste matérialisée à partir des étapes du workflow.
    steps = list(steps)
    # On extrait les noms des étapes ; le second élément de chaque paire est la fonction qui sera
    # appelée plus tard.
    names = [name for name, _ in steps]
    # On compare le nombre d’éléments au nombre de valeurs distinctes pour repérer les doublons
    # avant de poursuivre.
    if (
        not steps
        # Ce cas est aussi retenu si len(set(names)) diffère de len(names).
        or len(set(names)) != len(names)
        # Ce cas est aussi retenu si au moins un élément satisfait le test indiqué.
        or any(
            not isinstance(name, str)
            # Ce cas est aussi retenu si la condition re.fullmatch('[a-z][a-z0-9_]{0,79}', name) n’est
            # pas remplie.
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", name)
            # Ce cas est aussi retenu si la condition callable(action) n’est pas remplie.
            or not callable(action)
            for name, action in steps
        )
    ):
        # On interrompt cette branche avec ValueError : 'Etapes vides, dupliquees ou invalides.'.
        raise ValueError("Etapes vides, dupliquees ou invalides.")
    # On donne un identifiant propre à ce lancement. Il ne remplace pas les identifiants des lots
    # Excel et NAS, qui restent distincts.
    workflow_id = str(uuid4())
    # On démarre un chronomètre monotone pour mesurer une durée : une correction de l’horloge
    # système ne doit pas fausser ce calcul.
    started = time.monotonic()
    # On prépare completed comme liste vide ; on la remplira au fil des opérations suivantes.
    completed = []
    # On prépare le carnet commun de l’exécution : chaque étape y déposera son résultat pour les
    # étapes suivantes.
    context = WorkflowContext(root, workflow_id)
    # On prend le verrou avant les contrôles et les étapes ; sa libération est gérée en sortant du
    # bloc, sans permettre à deux runs locaux du partager.
    with workflow_lock(root, workflow_id):
        # Sous verrou, avant toute creation du journal et transmission SQL.
        # Un refus est propage ; aucune etape ni journal de workflow ne demarre.
        if preflight is not None:
            # On appelle preflight avec context.
            preflight(context)
        # Le journal local est créé une fois le contrôle préalable réussi. Il gardera les étapes
        # commencées, terminées et interrompues.
        journal = LocalJournal(root, workflow_id, trigger_mode, scope, journal_sink)
        # On initialise current à None : aucune valeur n’a encore été retenue ici.
        current = None
        # Aucune fonction métier n’est en train de s’exécuter à cet endroit ; les erreurs de
        # contrôle seront identifiées séparément.
        action_running = False
        # On utilise ce texte pour status ; il ne dépend pas d’une valeur récupérée ailleurs à cet
        # endroit.
        status = "success"
        # On initialise error_code à None : aucune valeur n’a encore été retenue ici.
        error_code = None
        # On tente ce bloc et on traite séparément les erreurs prévues : JournalDeliveryError,
        # KeyboardInterrupt, Exception.
        try:
            # On appelle journal.emit avec 'workflow'.
            journal.emit("workflow", "workflow", "started")
            # On suit l’ordre de la liste : chaque paire donne le nom de l’étape et la fonction à
            # appeler, avec le même contexte tout au long du run.
            for name, action in steps:
                # On retient le nom de l’étape avant de l’appeler ; si elle échoue, le journal
                # pourra désigner l’endroit où le parcours s’est arrêté.
                current = name
                # On enregistre le début avant d’appeler l’action. Une absence de fin indiquera
                # ainsi une étape commencée mais non confirmée.
                journal.emit("step", name, "started", links=context.linked_ids())
                # On marque l’entrée dans le traitement métier pour distinguer son échec d’un
                # problème de contrôle ou de journalisation.
                action_running = True
                # On appelle réellement l’étape avec le contexte partagé, puis on range son résultat
                # sous son nom. Le code ne passe à la suivante qu’après ce retour.
                context.results[name] = action(context)
                # On initialise action_running à False ; les branches suivantes pourront modifier cet
                # état.
                action_running = False
                # Cette étape a rendu la main sans lever d’exception ; on l’ajoute au bilan des
                # étapes terminées.
                completed.append(name)
                # On ne journalise la fin de l’étape qu’après son retour et le rangement de son
                # résultat dans le contexte.
                journal.emit("step", name, "success", links=context.linked_ids())
            # On appelle journal.emit avec 'workflow'.
            journal.emit(
                "workflow",
                "workflow",
                "success",
                links=context.linked_ids(),
                # On fournit les étapes terminées via le paramètre completed_steps de cet appel.
                completed_steps=len(completed),
                duration=time.monotonic() - started,
            )
        except JournalDeliveryError:
            # On distribue ces valeurs entre status, error_code, dans l’ordre de l’affectation. Chaque
            # nom reçoit son propre élément.
            status, error_code = "failed", "JOURNAL_DELIVERY_UNCONFIRMED"
        except KeyboardInterrupt:
            # On distribue ces valeurs entre status, error_code, dans l’ordre de l’affectation. Chaque
            # nom reçoit son propre élément.
            status, error_code = "interrupted", "WORKFLOW_INTERRUPTED"
        except Exception:
            # On distribue ces valeurs entre status, error_code, dans l’ordre de l’affectation. Chaque
            # nom reçoit son propre élément.
            status, error_code = (
                "failed",
                "WORKFLOW_STEP_FAILED" if action_running else "WORKFLOW_CONTROL_FAILED",
            )
        # On vérifie ce cas avant la suite : l’état du traitement diffère du texte 'success'.
        if status != "success":
            # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
            try:
                # Cette branche traite le cas où action_running est évalué comme vrai.
                if action_running:
                    # On appelle journal.emit avec 'step'.
                    journal.emit(
                        "step",
                        current,
                        status,
                        links=context.linked_ids(),
                        # On fournit le code du problème rencontré via le paramètre error_code de cet
                        # appel.
                        error_code=error_code,
                        deliver=False,
                    )
                # On appelle journal.emit avec 'workflow'.
                journal.emit(
                    "workflow",
                    "workflow",
                    status,
                    links=context.linked_ids(),
                    # On fournit le code du problème rencontré via le paramètre error_code de cet
                    # appel.
                    error_code=error_code,
                    # On fournit les étapes terminées via le paramètre completed_steps de cet appel.
                    completed_steps=len(completed),
                    duration=time.monotonic() - started,
                    deliver=False,
                )
            except Exception:
                # On interrompt cette branche avec RuntimeError.
                raise RuntimeError(
                    "Echec de conservation du journal local ; arreter et examiner les fichiers, aucune reprise automatique."
                ) from None
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On renseigne l’identifiant de l’exécution du workflow sous la clé
            # 'workflow_execution_id'.
            "workflow_execution_id": workflow_id,
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": status,
            # On renseigne le code du problème rencontré sous la clé 'error_code'.
            "error_code": error_code,
            # On renseigne les étapes terminées sous la clé 'completed_steps'.
            "completed_steps": list(completed),
            # On associe la clé 'journal_relative_path' à cette valeur dans cet objet.
            "journal_relative_path": journal.relative_path,
            **context.linked_ids(),
        }
