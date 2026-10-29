# Lecture du fichier — Conservation temporaire des données du dashboard dans le processus Python.
# Le navigateur garde une clé plutôt que tous les tableaux. Ce rangement reste local au processus :
# ce n’est ni une base persistante ni une autorisation d’accès.
#

"""Cache local borné : le navigateur reçoit une référence, pas tout l'historique.

Un seul processus Python, comme le lanceur livré. Redémarrage/expiration :
message explicite et rechargement, jamais remplacement par des données fictives.
"""

# On rend disponibles OrderedDict depuis collections, pour les appels de ce fichier.
from collections import OrderedDict
# On rend disponibles RLock depuis threading, pour les appels de ce fichier.
from threading import RLock
# On rend disponibles monotonic depuis time, pour les appels de ce fichier.
from time import monotonic
# On rend disponibles token_urlsafe depuis secrets, pour les appels de ce fichier.
from secrets import token_urlsafe

# On garde dans _LOCK la valeur renvoyée par RLock.
_LOCK = RLock()
# On garde dans _STATES la valeur renvoyée par OrderedDict.
_STATES = OrderedDict()
# On multiplie ces valeurs pour construire _TTL.
_TTL = 4 * 3600
# On fixe _MAX à 24 pour cette étape.
_MAX = 24


# On range les données côté serveur et on renvoie une clé de consultation.
def put_store(payload):
    # On garde dans token la valeur renvoyée par token_urlsafe pour 24.
    token = token_urlsafe(24)
    # On utilise _LOCK dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with _LOCK:
        # On rassemble dans _STATES[token] les 3 éléments explicitement indiqués, en conservant leur
        # structure.
        _STATES[token] = (monotonic(), payload, OrderedDict())
        # On répète ce bloc tant que len(_STATES) est supérieur à _MAX. La condition sera réévaluée à
        # chaque tour.
        while len(_STATES) > _MAX:
            # On appelle _STATES.popitem sans argument positionnel.
            _STATES.popitem(last=False)
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        **{
            k: payload.get(k)
            for k in [
                "mode",
                "status_message",
                "loaded_at",
                "snapshot_run",
                "snapshot_latest",
            ]
        },
        # On associe la clé '_store_id' à cette valeur dans cet objet.
        "_store_id": token,
    }


# On retrouve les données associées à une clé encore présente dans ce processus.
def resolve_store(value):
    # Cette branche traite le cas où la condition value n’est pas remplie ou le texte '_store_id' ne
    # figure pas dans la valeur reçue.
    if not value or "_store_id" not in value:
        # On remet value or {'mode': 'unavailable', 'frames': {}} à l’appelant ; les étapes suivantes
        # de cette fonction ne sont plus parcourues.
        return value or {"mode": "unavailable", "frames": {}}
    # On récupère value['_store_id'] et on le garde dans token pour la suite.
    token = value["_store_id"]
    # On utilise _LOCK dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with _LOCK:
        # On garde dans entry le champ token de _STATES, ou None si la clé est absente.
        entry = _STATES.get(token)
        # Cette branche traite le cas où entry est évalué comme vrai et monotonic() - entry[0] est
        # inférieur à _TTL.
        if entry and monotonic() - entry[0] < _TTL:
            # On appelle _STATES.move_to_end avec token.
            _STATES.move_to_end(token)
            # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées (la
            # copie reste superficielle).
            return dict(entry[1], _cache_key=token)
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'mode' à cette valeur dans cet objet.
        "mode": "unavailable",
        # On associe la clé 'frames' à cette valeur dans cet objet.
        "frames": {},
        # On associe la clé 'status_message' à cette valeur dans cet objet.
        "status_message": "Session expirée ou serveur redémarré. Cliquer sur « Actualiser les données ».",
        # On associe la clé 'cache_expired' à cette valeur dans cet objet.
        "cache_expired": True,
    }


# On réutilise un résultat en cache dans les limites prévues par ce stockage local.
def cached(store, key, compute):
    # On garde dans token le champ '_cache_key' de store, ou None si la clé est absente.
    token = store.get("_cache_key")
    # On prévoit le cas où token est évalué comme faux, par exemple une valeur vide selon son type.
    if not token:
        # On fournit à l’appelant la valeur renvoyée par compute.
        return compute()
    # Lock only cache access, not an expensive calculation.
    with _LOCK:
        # On garde dans entry le champ token de _STATES, ou None si la clé est absente.
        entry = _STATES.get(token)
        # Cette branche traite le cas où entry est évalué comme vrai et la clé de l’élément appartient
        # à entry[2].
        if entry and key in entry[2]:
            # On appelle entry[2].move_to_end avec key.
            entry[2].move_to_end(key)
            # On remet entry[2][key] à l’appelant ; les étapes suivantes de cette fonction ne sont plus
            # parcourues.
            return entry[2][key]
    # On garde dans result la valeur renvoyée par compute.
    result = compute()
    # On utilise _LOCK dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with _LOCK:
        # On garde dans entry le champ token de _STATES, ou None si la clé est absente.
        entry = _STATES.get(token)
        # Cette branche traite le cas où entry est évalué comme vrai.
        if entry:
            # On gardu résultat de cette opération sous le nom entry[2][key] ; cette affectation ne
            # copie pas à elle seule un objet mutable.
            entry[2][key] = result
            # On répète ce bloc tant que len(entry[2]) est supérieur à 20. La condition sera réévaluée
            # à chaque tour.
            while len(entry[2]) > 20:
                # On appelle entry[2].popitem sans argument positionnel.
                entry[2].popitem(last=False)
    # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return result
