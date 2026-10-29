# Lecture du fichier — Gestion des connexions, des dépôts SQL et des étapes de chargement.
# On encadre la durée de vie des ressources. Les transactions des chargeurs ne constituent pas une
# transaction unique couvrant tout le workflow et ses fichiers.
#

"""Adaptateurs explicites : aucune connexion, lecture .env ou ecriture a l'import.
Les factories recoivent des connexions neuves autocommit ; pas de transaction
externe, pour que chaque retour de chargeur corresponde a son propre commit.
"""

# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re

# On rend disponibles _project_module, assert_excel_snapshot depuis workflow_excel_adapter, pour les
# appels de ce fichier.
from workflow_excel_adapter import _project_module, assert_excel_snapshot
# On rend disponibles assert_nas_snapshot depuis workflow_nas_adapter, pour les appels de ce fichier.
from workflow_nas_adapter import assert_nas_snapshot

# On fixe USER à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
USER = "projet12_importer"
# On fixe TEST_DATABASE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
TEST_DATABASE = r"suivi_acquisitions_import_test_[A-Za-z0-9_]+"


def verify_connection(connection, expected_database):
    """Controle minimal d'identite ; ne remplace pas le diagnostic complet des droits."""
    # Cette branche traite le cas où expected_database diffère du texte 'suivi_acquisitions' et la
    # condition re.fullmatch(TEST_DATABASE, expected_database) n’est pas remplie.
    if expected_database != "suivi_acquisitions" and not re.fullmatch(
        TEST_DATABASE, expected_database
    ):
        # On interrompt cette branche avec ValueError : 'Destination non autorisee pour cet
        # adaptateur.'.
        raise ValueError("Destination non autorisee pour cet adaptateur.")
    # Cette branche traite le cas où connection.autocommit n’est pas exactement la valeur vraie (True)
    # ou int(connection.info.transaction_status) diffère de 0.
    if (
        connection.autocommit is not True
        # Ce cas est aussi retenu si int(connection.info.transaction_status) diffère de 0.
        or int(connection.info.transaction_status) != 0
    ):
        # On interrompt cette branche avec ValueError : 'Connexion neuve autocommit hors transaction
        # requise.'.
        raise ValueError("Connexion neuve autocommit hors transaction requise.")
    # On récupère une seule ligne du résultat SQL ; les contrôles suivants vérifient les valeurs
    # attendues.
    identity = connection.execute(
        "SELECT current_database(), current_user, session_user"
    ).fetchone()
    # On vérifie ce cas avant la suite : tuple(identity or ()) diffère de (expected_database, USER,
    # USER).
    if tuple(identity or ()) != (expected_database, USER, USER):
        # On interrompt cette branche avec ValueError : 'Identite du compte ou de la base
        # incompatible.'.
        raise ValueError("Identite du compte ou de la base incompatible.")
    # On garde dans attributes une ligne du résultat de la requête, ou None si elle n’en renvoie
    # aucune.
    attributes = connection.execute(
        "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=current_user"
    ).fetchone()
    # Cette branche traite le cas où attributes vaut None ou len(attributes) diffère de 5 ou au moins
    # un élément satisfait le test indiqué.
    if attributes is None or len(attributes) != 5 or any(attributes):
        # On interrompt cette branche avec ValueError : 'Compte privilegie interdit pour le chargement
        # et le journal.'.
        raise ValueError("Compte privilegie interdit pour le chargement et le journal.")


# On fournit une connexion pendant la durée prévue puis on gère sa fermeture.
def connection_scope(connect, expected_database):
    """Le callable connect fourni explicitement doit retourner une connexion dediee.
    Aucun parametre, secret ou repli administrateur n'est fabrique ici.
    """
    # Cette branche traite le cas où la condition callable(connect) n’est pas remplie.
    if not callable(connect):
        # On interrompt cette branche avec ValueError : 'Factory de connexion explicite requise.'.
        raise ValueError("Factory de connexion explicite requise.")
    # Cette branche traite le cas où au moins un des cas regroupés ici est rencontré.
    if not isinstance(expected_database, str) or (
        expected_database != "suivi_acquisitions"
        # On exige aussi que la condition re.fullmatch(TEST_DATABASE, expected_database) n’est pas
        # remplie.
        and not re.fullmatch(TEST_DATABASE, expected_database)
    ):
        # On interrompt cette branche avec ValueError : 'Destination non autorisee pour cet
        # adaptateur.'.
        raise ValueError("Destination non autorisee pour cet adaptateur.")

    # On fournit la ressource ouverte dans le contexte prévu et on en gère la sortie.
    @contextmanager
    def opened():
        # On garde dans connection la valeur renvoyée par connect.
        connection = connect()
        # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
        try:
            # On appelle verify_connection avec connection.
            verify_connection(connection, expected_database)
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield connection
        finally:
            # On ferme connection pour libérer la ressource associée après son utilisation.
            connection.close()

    # On remet opened à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return opened


# On fournit un dépôt SQL dans le périmètre de connexion prévu.
def repository_scope(root, opened, kind):
    """Choisit le repository existant ; il garde ses transactions et ses controles."""
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où kind ne figure pas dans {'excel', 'nas'} ou la condition
    # callable(opened) n’est pas remplie.
    if kind not in {"excel", "nas"} or not callable(opened):
        # On interrompt cette branche avec ValueError : 'Repository ou connexion explicite invalide.'.
        raise ValueError("Repository ou connexion explicite invalide.")
    # On choisit la valeur de module_name selon ce test : kind correspond au texte 'excel'. Les deux
    # résultats possibles restent définis explicitement ici.
    module_name = (
        "import_excel_publication" if kind == "excel" else "load_nas_reconciliation"
    )

    # On prépare le dépôt qui sera utilisé par l’étape de chargement.
    @contextmanager
    def repository():
        # On garde dans module le module du projet après vérification de son emplacement.
        module = _project_module(root, module_name, "scripts/" + module_name + ".py")
        # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
        # quittant le bloc.
        with opened() as connection:
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield module.PostgresRepository(connection)

    # On remet l’accès aux données SQL à l’appelant ; les étapes suivantes de cette fonction ne sont
    # plus parcourues.
    return repository


# On construit les opérations de chargement SQL avec les connexions et dépôts fournis.
def build_import_steps(
    root,
    *,
    excel_repository,
    nas_repository,
    import_excel=None,
    import_nas=None,
    ensure_excel=None,
    ensure_nas=None,
):
    """Charge uniquement les lots deja controles de ce contexte ; pas de recalcul.
    Une exception n'implique PAS un rollback des etapes precedentes ni une certitude
    sur un COMMIT dont la reponse aurait ete perdue. Aucun retry automatique.
    """
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où la condition callable(excel_repository) n’est pas remplie ou la
    # condition callable(nas_repository) n’est pas remplie.
    if not callable(excel_repository) or not callable(nas_repository):
        # On interrompt cette branche avec ValueError : 'Les deux factories de repositories sont
        # requises.'.
        raise ValueError("Les deux factories de repositories sont requises.")
    # On retient pour excel_guard la première valeur évaluée comme vraie dans cette chaîne de replis ;
    # une valeur vide fera donc passer à la suivante.
    excel_guard = ensure_excel or assert_excel_snapshot
    # On retient pour nas_guard la première valeur évaluée comme vraie dans cette chaîne de replis ;
    # une valeur vide fera donc passer à la suivante.
    nas_guard = ensure_nas or assert_nas_snapshot

    # On vérifie que le contexte et les opérations se rattachent à la même racine de projet.
    def check_root(context):
        # On vérifie ce cas avant la suite : context.root diffère de la racine locale du projet.
        if context.root != root:
            # On interrompt cette branche avec ValueError : 'Contexte appartenant a un autre projet.'.
            raise ValueError("Contexte appartenant a un autre projet.")

    # On transmet le lot Excel contrôlé au chargeur prévu par ce parcours.
    def excel_load(context):
        # On appelle check_root avec context.
        check_root(context)
        # On garde dans pinned la valeur renvoyée par excel_guard.
        pinned = excel_guard(context)
        # On reprend le lot Excel déjà contrôlé dans context.results ; cet accès suppose que la clé
        # a été produite ou vérifiée auparavant.
        bundle = context.results["excel_publication_check"]
        # Le lot NAS doit deja etre controle avant la premiere ecriture Excel.
        nas_guard(context)
        # On retient pour load la première valeur évaluée comme vraie dans cette chaîne de replis ; une
        # valeur vide fera donc passer à la suivante.
        load = (
            import_excel
            or _project_module(
                root, "import_excel_publication", "scripts/import_excel_publication.py"
            ).import_bundle
        )
        # On utilise excel_repository() dans son contexte de gestion ; les opérations de sortie sont
        # exécutées en quittant le bloc.
        with excel_repository() as repository:
            # On appelle excel_guard avec context.
            excel_guard(context)
            # On appelle nas_guard avec context.
            nas_guard(context)
            # On appelle load avec bundle.
            load(bundle, repository)
        # Pas de validation tardive susceptible d'effacer un succes deja commis.
        return {"status": "success", "excel_publication_id": pinned.publication_id}

    # On transmet le lot d’observations contrôlé au chargeur prévu par ce parcours.
    def nas_load(context):
        # On appelle check_root avec context.
        check_root(context)
        # On garde dans pinned la valeur renvoyée par excel_guard.
        pinned = excel_guard(context)
        # On garde dans bundle la valeur renvoyée par nas_guard.
        bundle = nas_guard(context)
        # On garde dans receipt le champ 'excel_import' de context.results, ou None si la clé est
        # absente.
        receipt = context.results.get("excel_import")
        # On vérifie ce cas avant la suite : le reçu du traitement diffère de {'status': 'success',
        # 'excel_publication_id': pinned.publication_id}.
        if receipt != {
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "success",
            # On renseigne l’identifiant du lot Excel sous la clé 'excel_publication_id'.
            "excel_publication_id": pinned.publication_id,
        }:
            # On interrompt cette branche avec ValueError : 'Chargement Excel non confirme pour cette
            # publication.'.
            raise ValueError("Chargement Excel non confirme pour cette publication.")
        # On retient pour load la première valeur évaluée comme vraie dans cette chaîne de replis ; une
        # valeur vide fera donc passer à la suivante.
        load = (
            import_nas
            or _project_module(
                root, "load_nas_reconciliation", "scripts/load_nas_reconciliation.py"
            ).import_bundle
        )
        # On utilise nas_repository() dans son contexte de gestion ; les opérations de sortie sont
        # exécutées en quittant le bloc.
        with nas_repository() as repository:
            # On appelle excel_guard avec context.
            excel_guard(context)
            # On appelle nas_guard avec context.
            nas_guard(context)
            # On appelle load avec bundle.
            load(bundle, repository)
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {
            # On renseigne l’état du traitement sous la clé 'status'.
            "status": "success",
            # On renseigne l’identifiant du traitement NAS sous la clé 'pipeline_execution_id'.
            "pipeline_execution_id": context.linked_ids()["pipeline_execution_id"],
            # On renseigne l’identifiant du lot Excel sous la clé 'excel_publication_id'.
            "excel_publication_id": pinned.publication_id,
        }

    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return [("excel_import", excel_load), ("nas_import", nas_load)]


# On prépare le destinataire des événements à enregistrer dans le journal SQL métier.
def build_journal_sink(root, *, opened, append=None):
    """Chaque evenement : nouvelle connexion, transaction courte du repository,
    fermeture. Un echec est traite par le journal local du socle, sans relance.
    Le rejeu explicite utilise les memes UUID/dates via replay_events.
    """
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où la condition callable(opened) n’est pas remplie.
    if not callable(opened):
        # On interrompt cette branche avec ValueError : 'Factory explicite requise pour le journal.'.
        raise ValueError("Factory explicite requise pour le journal.")

    # On transmet l’événement au destinataire fourni pour ce journal.
    def sink(event):
        # On charge le module workflow_journal_repository de cette copie ; le helper contrôle son
        # emplacement pour ne pas mélanger deux projets présents sur le poste.
        module = _project_module(
            root,
            "workflow_journal_repository",
            "scripts/workflow_journal_repository.py",
        )
        # Valider avant l'ouverture ; le repository normalise aussi avant insertion.
        module.normalize_event(event)
        # On retient pour write la première valeur évaluée comme vraie dans cette chaîne de replis ;
        # une valeur vide fera donc passer à la suivante.
        write = append or module.append_event
        # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
        # quittant le bloc.
        with opened() as connection:
            # On garde dans outcome la valeur renvoyée par write.
            outcome = write(connection, event)
        # On vérifie ce cas avant la suite : outcome ne figure pas dans {'inserted', 'reused'}.
        if outcome not in {"inserted", "reused"}:
            # On interrompt cette branche avec ValueError : 'Transmission du journal non confirmee.'.
            raise ValueError("Transmission du journal non confirmee.")
        # On remet outcome à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return outcome

    # On remet sink à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return sink
