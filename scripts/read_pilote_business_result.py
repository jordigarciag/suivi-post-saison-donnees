# Lecture du fichier — Lecture et présentation du bilan déjà enregistré pour un domaine fictif.
# On prépare des libellés à partir des résultats SQL. Aucun nouveau résultat ne doit être déduit d’un
# fichier que ce lecteur n’a pas observé.
#

"""Lecture du bilan DomaineDemoD conserve en SQL ; aucun recalcul ni acces NAS."""

# On rend disponibles Counter, defaultdict depuis collections, pour les appels de ce fichier.
from collections import Counter, defaultdict
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

# On rend disponibles WORKFLOW, PIPELINE, PUBLICATION, CheckError, require, validate_local, verify_sql
# depuis check_pilote_workflow_result, pour les appels de ce fichier.
from check_pilote_workflow_result import (
    WORKFLOW,
    PIPELINE,
    PUBLICATION,
    CheckError,
    require,
    validate_local,
    verify_sql,
)


# On ramène une valeur scalaire aux trois états utiles : vrai, faux ou non renseigné.
def boolean(value):
    # Un champ vide reste inconnu : le présenter comme False ferait croire qu’un contrôle négatif a
    # réellement eu lieu.
    if value is None or value == "":
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None
    # Si la source fournit déjà un vrai booléen, on le conserve sans passer par la vérité générale
    # de Python.
    if type(value) is bool:
        # On remet la valeur reçue à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return value
    # Pour une chaîne, on ne reconnaît que les écritures prévues ci-dessous ; le texte "false" est
    # non vide mais ne doit pas devenir True.
    if isinstance(value, str):
        # On vérifie ce cas avant la suite : value.casefold() appartient à ('true', '1').
        if value.casefold() in ("true", "1"):
            # On renvoie True comme résultat explicite de cette branche.
            return True
        # On vérifie ce cas avant la suite : value.casefold() appartient à ('false', '0').
        if value.casefold() in ("false", "0"):
            # On renvoie False comme résultat explicite de cette branche.
            return False
    # On interrompt cette branche avec CheckError : 'BOOLEAN_VALUE_UNEXPECTED'.
    raise CheckError("BOOLEAN_VALUE_UNEXPECTED")


# On prépare un libellé lisible à partir des valeurs prévues dans ce module.
def label(value):
    # On ramène d’abord les formes admises à True, False ou None ; on ne transforme pas une valeur
    # inconnue en Non.
    value = boolean(value)
    # On garde trois libellés distincts : une absence de renseignement n’est pas un constat négatif.
    return "Oui" if value is True else "Non" if value is False else "Non renseigne"


def text(value):
    # Echappement des retours a la ligne et caracteres de controle de la sortie.
    return json.dumps(
        "Non renseigne" if value is None or value == "" else str(value),
        # On choisit ici si les caractères accentués doivent être échappés dans le JSON.
        ensure_ascii=False,
    )


def evidence(payload, field, error_field):
    # Un seul nom d’erreur est transformé en tuple ; une liste de noms reste parcourable de la même
    # façon juste après.
    error_fields = (error_field,) if isinstance(error_field, str) else error_field
    # Une erreur de lecture prime sur le constat : comme devant une porte fermée, on ne sait pas
    # conclure que le fichier derrière manque.
    if any(payload.get(key) for key in error_fields):
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "Non verifiable (erreur de lecture)"
    # Sans erreur de lecture annoncée, on peut présenter la valeur enregistrée du constat, y compris
    # son éventuel état inconnu.
    return label(payload.get(field))


def summary_lines(acquisitions, passages, associations):
    # On garde dans acquisitions les éléments triés des acquisitions dans une nouvelle liste.
    acquisitions = sorted(acquisitions, key=lambda r: r[0])
    # On garde dans passages les éléments triés des passages dans une nouvelle liste.
    passages = sorted(passages, key=lambda r: (r[0], r[1]))
    # On indexe le résultat par r[0], avec 'A%02d' % (i + 1) comme valeur ; les contrôles d’unicité
    # sont importants car une même clé ne garde qu’une valeur dans un dictionnaire.
    amap = {r[0]: "A%02d" % (i + 1) for i, r in enumerate(acquisitions)}
    # On indexe le résultat par (r[0], r[1]), avec 'P%02d' % (i + 1) comme valeur ; les contrôles
    # d’unicité sont importants car une même clé ne garde qu’une valeur dans un dictionnaire.
    pmap = {(r[0], r[1]): "P%02d" % (i + 1) for i, r in enumerate(passages)}
    # Plusieurs résultats pour la même clé rendraient le bilan ambigu ; on ne garde pas
    # arbitrairement la dernière ligne.
    require(
        len(amap) == len(acquisitions) and len(pmap) == len(passages),
        "DUPLICATE_RESULT_KEYS",
    )
    # On prépare, pour chaque acquisition, un ensemble de passages : un même passage n’a pas à être
    # compté plusieurs fois.
    links = defaultdict(set)
    # On prépare aussi la lecture inverse, du passage vers les acquisitions, pour présenter les deux
    # côtés du rapprochement.
    inverse = defaultdict(set)
    # On gardera ici les associations déjà rencontrées afin de distinguer un doublon d’une nouvelle
    # association.
    seen = set()
    # On parcourt les associations entre acquisitions et passages ; (acquisition, parcel, passage)
    # désigne l’élément courant à chaque passage dans la boucle.
    for acquisition, parcel, passage in associations:
        # Une association doit correspondre à un résultat connu ; sinon on présenterait un
        # rattachement sans acquisition contrôlée.
        require(
            acquisition in amap and (parcel, passage) in pmap,
            "ASSOCIATION_WITHOUT_RESULT",
        )
        # On refuse de compter deux fois le même rattachement : le nombre de lignes ne doit pas
        # gonfler le nombre d’associations réelles.
        require((acquisition, parcel, passage) not in seen, "DUPLICATE_ASSOCIATION")
        # On ajoute (acquisition, parcel, passage) à seen ; comme il s’agit d’un ensemble, une valeur
        # déjà présente n’est pas comptée deux fois.
        seen.add((acquisition, parcel, passage))
        # On rattache le repère du passage à cette acquisition ; l’ensemble évite les répétitions
        # dans la présentation.
        links[acquisition].add(pmap[(parcel, passage)])
        # On conserve le lien inverse pour pouvoir afficher quelles acquisitions alimentent chaque
        # passage.
        inverse[(parcel, passage)].add(amap[acquisition])
    # On rassemble dans lines les 6 éléments explicitement indiqués, en conservant leur structure.
    lines = [
        "BILAN PILOTE ENREGISTRE - aucun nouveau controle du NAS.",
        "Reperes Axx/Pxx : correspondances internes a cette sortie, pas de nouveaux identifiants metier.",
        "Les identifiants reels, parcelles, chemins NAS et commentaires libres ne sont pas affiches.",
        "Volumes : %d acquisitions ; %d associations ; %d passages distincts."
        % (len(acquisitions), len(associations), len(passages)),
        "",
        "SYNTHESE DES ACQUISITIONS",
    ]
    # On parcourt [('excel_perimeter', 'Perimetres Excel'), ('processing_business_category'… ; (key,
    # title) désigne l’élément courant à chaque passage dans la boucle.
    for key, title in [
        ("excel_perimeter", "Perimetres Excel"),
        ("processing_business_category", "Categories traitement"),
        ("relationship_business_category", "Categories relations"),
    ]:
        # On ajoute title + ' :' à la fin de lines ; les éléments précédents restent conservés.
        lines.append(title + " :")
        # On garde dans counter les effectifs de chaque valeur rencontrée.
        counter = Counter(r[3].get(key) or "Non renseigne" for r in acquisitions)
        # On parcourt sorted(counter.items()) ; (name, count) désigne l’élément courant à chaque
        # passage dans la boucle.
        for name, count in sorted(counter.items()):
            # On ajoute '  %d : %s' % (count, text(name)) à la fin de lines ; les éléments précédents
            # restent conservés.
            lines.append("  %d : %s" % (count, text(name)))
    # On ajoute 'Acquisitions candidates a verification : %d (pas des anomalies prouvees).' % sum((r[1]
    # i… à la fin de lines ; les éléments précédents restent conservés.
    lines.append(
        "Acquisitions candidates a verification : %d (pas des anomalies prouvees)."
        % sum(r[1] is True for r in acquisitions)
    )
    # On ajoute les éléments de ['', 'DETAIL DES ACQUISITIONS'] à lines ; on n’ajoute pas la collection
    # comme un seul élément imbriqué.
    lines.extend(["", "DETAIL DES ACQUISITIONS"])
    # On parcourt les acquisitions ; (aid, review, verifiable, payload) désigne l’élément courant à
    # chaque passage dans la boucle.
    for aid, review, verifiable, payload in acquisitions:
        # Le détail d’une acquisition doit avoir la structure attendue avant d’en extraire les
        # constats.
        require(isinstance(payload, dict), "ACQUISITION_PAYLOAD_INVALID")
        # On ajoute amap[aid] + ' -> ' + (', '.join(sorted(links[aid])) or 'Aucun passage associe dans
        # ce lot… à la fin de lines ; les éléments précédents restent conservés.
        lines.append(
            amap[aid]
            + " -> "
            + (", ".join(sorted(links[aid])) or "Aucun passage associe dans ce lot")
        )
        # On ajoute '  Excel : perimetre=%s ; statut=%s ; candidat a verification=%s.' %
        # (text(payload.get('e… à la fin de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Excel : perimetre=%s ; statut=%s ; candidat a verification=%s."
            % (
                text(payload.get("excel_perimeter")),
                text(payload.get("excel_pipeline_status")),
                label(review),
            )
        )
        # On ajoute '  Brut=%s ; image full size=%s ; full size deux cotes=%s ; mapping parcelle=%s.' %
        # (evid… à la fin de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Brut=%s ; image full size=%s ; full size deux cotes=%s ; mapping parcelle=%s."
            % (
                evidence(payload, "found_in_raw_live", "raw_error"),
                evidence(payload, "raw_has_full_size_image", "raw_error"),
                evidence(payload, "raw_has_full_size_both_sides", "raw_error"),
                evidence(payload, "found_in_parcel_mapping", "parcel_mapping_error"),
            )
        )
        # On ajoute '  Processing=%s ; WEBP au moins un cote=%s ; WEBP deux cotes=%s.' %
        # (evidence(payload, '… à la fin de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Processing=%s ; WEBP au moins un cote=%s ; WEBP deux cotes=%s."
            % (
                evidence(payload, "found_in_processing_live", "processing_error"),
                evidence(payload, "processing_has_webp_images", "processing_error"),
                evidence(payload, "processing_has_webp_both_sides", "processing_error"),
            )
        )
        # On ajoute '  Sorties de passage verifiables (synthese acquisition)=%s.' % label(verifiable) à
        # la fin de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Sorties de passage verifiables (synthese acquisition)=%s."
            % label(verifiable)
        )
        # On ajoute '  Traitement : %s' % text(payload.get('processing_business_category')) à la fin de
        # lines ; les éléments précédents restent conservés.
        lines.append(
            "  Traitement : %s" % text(payload.get("processing_business_category"))
        )
        # On ajoute '  Action traitement : %s' % text(payload.get('processing_next_action')) à la fin
        # de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Action traitement : %s" % text(payload.get("processing_next_action"))
        )
        # On ajoute '  Relations : %s' % text(payload.get('relationship_business_category')) à la fin
        # de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Relations : %s" % text(payload.get("relationship_business_category"))
        )
        # On ajoute '  Action relations : %s' % text(payload.get('relationship_next_action')) à la fin
        # de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Action relations : %s" % text(payload.get("relationship_next_action"))
        )
    # On ajoute les éléments de ['', 'SYNTHESE ET DETAIL DES PASSAGES'] à lines ; on n’ajoute pas la
    # collection comme un seul élément imbriqué.
    lines.extend(["", "SYNTHESE ET DETAIL DES PASSAGES"])
    # On garde dans categories les effectifs de chaque valeur rencontrée.
    categories = Counter(
        r[5].get("passage_business_category") or "Non renseigne" for r in passages
    )
    # On parcourt sorted(categories.items()) ; (category, count) désigne l’élément courant à chaque
    # passage dans la boucle.
    for category, count in sorted(categories.items()):
        # On ajoute '  %d : %s' % (count, text(category)) à la fin de lines ; les éléments précédents
        # restent conservés.
        lines.append("  %d : %s" % (count, text(category)))
    # On ajoute 'Passages candidats a verification : %d.' % sum((r[2] is True for r in passages)) à la
    # fin de lines ; les éléments précédents restent conservés.
    lines.append(
        "Passages candidats a verification : %d." % sum(r[2] is True for r in passages)
    )
    # On parcourt les passages ; (parcel, passage, review, verifiable, ready, payload) désigne
    # l’élément courant à chaque passage dans la boucle.
    for parcel, passage, review, verifiable, ready, payload in passages:
        # Même contrôle pour un passage : un champ présent mais d’un mauvais type ne peut pas être
        # interprété comme une preuve.
        require(isinstance(payload, dict), "PASSAGE_PAYLOAD_INVALID")
        # On ajoute pmap[parcel, passage] + ' <- ' + (', '.join(sorted(inverse[parcel, passage])) or
        # 'Aucune… à la fin de lines ; les éléments précédents restent conservés.
        lines.append(
            pmap[(parcel, passage)]
            + " <- "
            + (
                ", ".join(sorted(inverse[(parcel, passage)]))
                or "Aucune acquisition associee dans ce lot"
            )
        )
        # On ajoute '  Dossier=%s ; Vitimap=%s ; JSON stocks=%s.' % (evidence(payload,
        # 'passage_created', 'pa… à la fin de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Dossier=%s ; Vitimap=%s ; JSON stocks=%s."
            % (
                evidence(payload, "passage_created", "passage_error"),
                evidence(
                    payload, "vitimap_created", ("passage_error", "vitimap_error")
                ),
                evidence(
                    payload, "stocks_json_exists", ("passage_error", "vitiparcel_error")
                )
                if verifiable is True
                else "Non verifiable",
            )
        )
        # On choisit la valeur de ready_label selon ce test : l’état de vérifiabilité est exactement la
        # valeur vraie (True). Les deux résultats possibles restent définis explicitement ici.
        ready_label = label(ready) if verifiable is True else "Non verifiable"
        # On ajoute '  Critere Vitiparcel verifiable=%s ; satisfait=%s ; candidat a verification=%s.' %
        # (labe… à la fin de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Critere Vitiparcel verifiable=%s ; satisfait=%s ; candidat a verification=%s."
            % (label(verifiable), ready_label, label(review))
        )
        # On ajoute '  Observation : %s' % text(payload.get('vitiparcel_delivery_observation')) à la
        # fin de lines ; les éléments précédents restent conservés.
        lines.append(
            "  Observation : %s" % text(payload.get("vitiparcel_delivery_observation"))
        )
        # On ajoute '  Categorie : %s' % text(payload.get('passage_business_category')) à la fin de
        # lines ; les éléments précédents restent conservés.
        lines.append(
            "  Categorie : %s" % text(payload.get("passage_business_category"))
        )
        # On ajoute '  Action : %s' % text(payload.get('passage_next_action')) à la fin de lines ; les
        # éléments précédents restent conservés.
        lines.append("  Action : %s" % text(payload.get("passage_next_action")))
    # On ajoute les éléments de ['', 'LIMITES : presence technique != qualite validee ou livraison au
    # client.', 'Un… à lines ; on n’ajoute pas la collection comme un seul élément imbriqué.
    lines.extend(
        [
            "",
            "LIMITES : presence technique != qualite validee ou livraison au client.",
            "Un critere non satisfait ou une commande inconnue ne prouvent pas un travail oublie.",
            "Non renseigne / non verifiable ne sont pas convertis en absence prouvee.",
            "Aucune regle metier recalculee, aucune ecriture, aucun acces NAS, aucun nouveau workflow.",
        ]
    )
    # On remet lines à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return lines


def main():
    # On récupère Path(__file__).resolve().parents[1] et on le garde dans root pour la suite.
    root = Path(__file__).resolve().parents[1]
    # On assemble les morceaux du chemin path avec l’opérateur / de pathlib ; aucun fichier n’est créé
    # par cette construction.
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
        # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas
        # de connexion.
        import psycopg

        # On garde dans digest l’empreinte de hashlib.sha256(path.read_bytes()) sous forme d’octets.
        digest = hashlib.sha256(path.read_bytes()).digest()
        # On garde dans expected la valeur renvoyée par validate_local.
        expected = validate_local(read_events(path), normalize_event)
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
                # On répartit les valeurs renvoyées par verify_sql entre (_, counts) ; leur ordre doit
                # correspondre à celui prévu par cet appel.
                _, counts = verify_sql(conn, expected, COLUMNS)
                # On garde dans keys toutes les lignes encore disponibles dans le résultat SQL.
                keys = conn.execute(
                    """SELECT c.vineyard_key,c.reconciliation_run_id
                    FROM core.current_vineyard_reconciliations c JOIN core.vineyards v
                    ON v.vineyard_key=c.vineyard_key WHERE lower(v.vineyard_name)=lower(%s)""",
                    ("DomaineDemoD",),
                ).fetchall()
                # On exige une correspondance unique pour le domaine pilote afin de ne pas afficher
                # le résultat d’un autre périmètre.
                require(len(keys) == 1, "PILOTE_KEY_AMBIGUOUS")
                # On récupère keys[0] et on le garde dans (key, rec) pour la suite.
                key, rec = keys[0]
                # On rassemble dans params les 3 éléments explicitement indiqués, en conservant leur
                # structure.
                params = (PIPELINE, key, rec)
                # On utilise ce texte pour clause ; il ne dépend pas d’une valeur récupérée ailleurs à
                # cet endroit.
                clause = " WHERE pipeline_execution_id=%s AND vineyard_key=%s AND reconciliation_run_id=%s"
                # On garde dans acquisitions toutes les lignes encore disponibles dans le résultat SQL.
                acquisitions = conn.execute(
                    "SELECT acquisition_id_normalise,acquisition_review_candidate,"
                    "passage_outputs_verifiable,payload FROM staging.reconciliation_acquisition_rows"
                    + clause,
                    params,
                ).fetchall()
                # On garde dans passages toutes les lignes encore disponibles dans le résultat SQL.
                passages = conn.execute(
                    "SELECT parcel_name,passage_name,passage_review_candidate,"
                    "vitiparcel_ready_verifiable,vitiparcel_ready_for_delivery,payload "
                    "FROM staging.reconciliation_passage_rows" + clause,
                    params,
                ).fetchall()
                # On garde dans associations toutes les lignes encore disponibles dans le résultat SQL.
                associations = conn.execute(
                    "SELECT acquisition_id_normalise,parcel_name,passage_name "
                    "FROM staging.reconciliation_association_rows" + clause,
                    params,
                ).fetchall()
                # Le nombre d’éléments relus doit correspondre au bilan annoncé ; une sortie
                # partielle ne valide pas le résultat complet.
                require(
                    [len(acquisitions), len(associations), len(passages)] == counts,
                    "RESULT_COUNTS_MISMATCH",
                )
                # Le journal local doit rester identique pendant ce contrôle ; on ne confirme pas un
                # résultat à partir de deux états successifs du fichier.
                require(
                    hashlib.sha256(path.read_bytes()).digest() == digest,
                    "LOCAL_JOURNAL_CHANGED",
                )
                # On garde dans lines la valeur renvoyée par summary_lines.
                lines = summary_lines(acquisitions, passages, associations)
            finally:
                # On annule les écritures non validées dans cette transaction, sans prétendre annuler
                # les opérations déjà commises ailleurs.
                conn.rollback()
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Connexion importeur ; transaction READ ONLY ; journal et bilan actif reverifies."
        )
        # On affiche 'Reference Excel : ' + PUBLICATION + ' ; traitement NAS : ' + PIPELINE dans la
        # sortie du programme.
        print("Reference Excel : " + PUBLICATION + " ; traitement NAS : " + PIPELINE)
        # On affiche '\n'.join(lines) dans la sortie du programme.
        print("\n".join(lines))
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print("RESULTAT : OK - lecture du bilan DomaineDemoD conserve terminee.")
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as exc:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "LECTURE NON CONFIRMEE : "
            + (str(exc) if isinstance(exc, CheckError) else type(exc).__name__)
        )
        # On affiche le texte 'Ne pas relancer le workflow ; aucun rejeu automatique.' dans la sortie
        # du programme.
        print("Ne pas relancer le workflow ; aucun rejeu automatique.")
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine le programme avec ce code de sortie pour que l’appelant puisse distinguer réussite et
    # échec.
    sys.exit(main())
