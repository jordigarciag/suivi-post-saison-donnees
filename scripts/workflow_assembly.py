# Lecture du fichier — Assemblage des huit étapes avec des dépendances explicitement fournies.
# On décrit le parcours commun sans ouvrir les sources à l’import de ce module. Le lanceur choisit
# ensuite les véritables adaptateurs ou ceux des tests.
#

"""Assemblage partage des adaptateurs : aucun Airflow, .env ou connexion implicite.
Le lanceur livre avec ce lot autorise uniquement une repetition synthetique.
"""

# On décrit les champs d’un objet de données sans écrire toute sa construction à la main.
from dataclasses import dataclass, fields
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path

# On rend disponibles build_excel_steps, assert_excel_snapshot depuis workflow_excel_adapter, pour les
# appels de ce fichier.
from workflow_excel_adapter import build_excel_steps, assert_excel_snapshot
# On rend disponibles build_nas_steps, assert_nas_snapshot depuis workflow_nas_adapter, pour les appels
# de ce fichier.
from workflow_nas_adapter import build_nas_steps, assert_nas_snapshot
# On rend disponibles build_import_steps depuis workflow_postgres_adapter, pour les appels de ce
# fichier.
from workflow_postgres_adapter import build_import_steps
# On rend disponibles run_workflow depuis workflow_runtime, pour les appels de ce fichier.
from workflow_runtime import run_workflow


@dataclass(frozen=True)
class WorkflowDependencies:
    # On déclare le champ ingest_excel avec le type attendu object ; sa valeur sera fournie lors de la
    # construction de l’objet.
    ingest_excel: object
    # On déclare le champ prepare_excel avec le type attendu object ; sa valeur sera fournie lors de la
    # construction de l’objet.
    prepare_excel: object
    # On déclare le champ check_excel avec le type attendu object ; sa valeur sera fournie lors de la
    # construction de l’objet.
    check_excel: object
    # On déclare le champ select_vineyards avec le type attendu object ; sa valeur sera fournie lors de
    # la construction de l’objet.
    select_vineyards: object
    # On déclare le champ execute_nas avec le type attendu object ; sa valeur sera fournie lors de la
    # construction de l’objet.
    execute_nas: object
    # On déclare le champ prepare_nas avec le type attendu object ; sa valeur sera fournie lors de la
    # construction de l’objet.
    prepare_nas: object
    # On déclare le champ check_nas avec le type attendu object ; sa valeur sera fournie lors de la
    # construction de l’objet.
    check_nas: object
    # On déclare le champ excel_repository avec le type attendu object ; sa valeur sera fournie lors de
    # la construction de l’objet.
    excel_repository: object
    # On déclare le champ nas_repository avec le type attendu object ; sa valeur sera fournie lors de
    # la construction de l’objet.
    nas_repository: object
    # On déclare le champ import_excel avec le type attendu object ; sa valeur sera fournie lors de la
    # construction de l’objet.
    import_excel: object
    # On déclare le champ import_nas avec le type attendu object ; sa valeur sera fournie lors de la
    # construction de l’objet.
    import_nas: object

    def validate(self):
        # Cette branche traite le cas où la condition all((callable(getattr(self, field.name)) for
        # field in fields(self))) n’est pas remplie.
        if not all(callable(getattr(self, field.name)) for field in fields(self)):
            # On interrompt cette branche avec ValueError : 'Toutes les dependances doivent etre
            # explicites et callable.'.
            raise ValueError(
                "Toutes les dependances doivent etre explicites et callable."
            )


# On exige une sélection explicite de domaines ou le choix de tous, mais pas les deux à la fois.
def validate_selection(vineyards, all_vineyards):
    # Cette branche traite le cas où type(all_vineyards) n’est pas exactement bool ou les domaines
    # sélectionnés est renseigné (différent de None) et le type reçu ne correspond pas à (list, tuple).
    if type(all_vineyards) is not bool or (
        vineyards is not None and not isinstance(vineyards, (list, tuple))
    ):
        # On interrompt cette branche avec ValueError : 'Selection de vignobles invalide.'.
        raise ValueError("Selection de vignobles invalide.")
    # On vérifie ce cas avant la suite : bool(vineyards) correspond au choix de tous les domaines.
    if bool(vineyards) == all_vineyards:
        # On interrompt cette branche avec ValueError : 'Choisir des vignobles OU tous les vignobles.'.
        raise ValueError("Choisir des vignobles OU tous les vignobles.")
    # On prépare une sélection propre en gardant l’ordre demandé et en retirant les doublons de
    # casse ci-dessous.
    selected = []
    # On parcourt vineyards or [] ; value désigne l’élément courant à chaque passage dans la boucle.
    for value in vineyards or []:
        # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition
        # value.strip() n’est pas remplie.
        if not isinstance(value, str) or not value.strip():
            # On interrompt cette branche avec ValueError : 'Vignoble vide ou invalide.'.
            raise ValueError("Vignoble vide ou invalide.")
        # On enlève les espaces ajoutés autour du nom, sans modifier ses caractères internes.
        name = value.strip()
        # On compare les noms sans tenir compte des majuscules pour ne pas sélectionner deux fois le
        # même domaine sous deux écritures.
        if name.casefold() not in {n.casefold() for n in selected}:
            # On ajoute le nom après le contrôle des doublons ; l’ordre de la sélection initiale
            # reste conservé.
            selected.append(name)
    # On remet la sélection retenue à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return selected


# On assemble les huit étapes avec des dépendances validées avant le lancement.
def build_workflow_steps(
    root, *, dependencies, vineyards=None, all_vineyards=False, year=2026
):
    """Les huit etapes, utilisees sans duplication par les futurs points d'entree.
    Aucune dependance reelle fournie automatiquement : executor et repositories
    doivent etre definis explicitement AVANT de commencer l'ingestion.
    """
    # Cette branche traite le cas où le type reçu ne correspond pas à WorkflowDependencies.
    if not isinstance(dependencies, WorkflowDependencies):
        # On interrompt cette branche avec ValueError : 'Dependances du workflow absentes.'.
        raise ValueError("Dependances du workflow absentes.")
    # On appelle dependencies.validate sans argument positionnel.
    dependencies.validate()
    # On validu choix des domaines avant de construire les étapes ; choisir tous les domaines et
    # une liste explicite serait contradictoire.
    selected = validate_selection(vineyards, all_vineyards)
    # Cette branche traite le cas où type(year) n’est pas exactement int ou la condition 1900 <= year
    # <= 2200 n’est pas remplie.
    if type(year) is not int or not 1900 <= year <= 2200:
        # On interrompt cette branche avec ValueError : 'Annee invalide.'.
        raise ValueError("Annee invalide.")
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où la condition root.is_dir() n’est pas remplie.
    if not root.is_dir():
        # On interrompt cette branche avec ValueError : 'Racine locale absente.'.
        raise ValueError("Racine locale absente.")
    # On utilise un nom court pour l’ensemble des fonctions fournies au workflow ; les tests
    # pourront en donner des doubles sans appeler les installations réelles.
    d = dependencies
    # On prépare le contrôle de stabilité Excel à rappeler avant les consommateurs du lot. La lambda
    # crée ce rappel ; elle ne l’exécute pas encore.
    eg = lambda ctx: assert_excel_snapshot(ctx, ensure_current=d.check_excel)
    # Le contrôle NAS réutilise celui d’Excel : les deux lots doivent encore correspondre avant leur
    # utilisation ensemble.
    ng = lambda ctx: assert_nas_snapshot(ctx, ensure_excel=eg, ensure_nas=d.check_nas)
    # On remet build_excel_steps(root, vineyards=selected or None, all_vineyards=all_vin… à l’appelant
    # ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return (
        build_excel_steps(
            root,
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=selected or None,
            # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
            all_vineyards=all_vineyards,
            ingest=d.ingest_excel,
            prepare=d.prepare_excel,
            # On fournit la vérification de stabilité du lot, réutilisable avant ses consommateurs.
            ensure_current=d.check_excel,
        )
        + build_nas_steps(
            root,
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=selected or None,
            # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
            all_vineyards=all_vineyards,
            # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
            year=year,
            select=d.select_vineyards,
            execute=d.execute_nas,
            prepare=d.prepare_nas,
            # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
            ensure_excel=eg,
            # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
            ensure_nas=d.check_nas,
        )
        + build_import_steps(
            root,
            excel_repository=d.excel_repository,
            nas_repository=d.nas_repository,
            import_excel=d.import_excel,
            import_nas=d.import_nas,
            # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
            ensure_excel=eg,
            # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
            ensure_nas=ng,
        )
    )


def run_shared_rehearsal(
    root,
    *,
    dependencies,
    journal_sink,
    trigger_mode,
    vineyards=None,
    all_vineyards=False,
    year=2026,
):
    """Point d'appel sans dependance Airflow ; les services reels ne sont pas configures ici.
    Le journal signale explicitement la repetition, pas une actualisation metier.
    """
    # On vérifie ce cas avant la suite : l’origine du déclenchement ne figure pas dans
    # {'manual_script', 'airflow_manual', 'airflow_scheduled', 'integration_tes….
    if trigger_mode not in {
        "manual_script",
        "airflow_manual",
        "airflow_scheduled",
        "integration_test",
    }:
        # On interrompt cette branche avec ValueError : 'Mode de declenchement inconnu.'.
        raise ValueError("Mode de declenchement inconnu.")
    # Cette branche traite le cas où la condition callable(journal_sink) n’est pas remplie.
    if not callable(journal_sink):
        # On interrompt cette branche avec ValueError : 'Destinataire du journal explicite requis.'.
        raise ValueError("Destinataire du journal explicite requis.")
    # On validu choix des domaines avant de construire les étapes ; choisir tous les domaines et
    # une liste explicite serait contradictoire.
    selected = validate_selection(vineyards, all_vineyards)
    # On assemble le parcours et ses dépendances ; on distingue cette préparation du lancement
    # effectif du workflow.
    steps = build_workflow_steps(
        root,
        dependencies=dependencies,
        # On transmet la sélection explicite des domaines concernés par cet appel.
        vineyards=selected or None,
        # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
        all_vineyards=all_vineyards,
        # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
        year=year,
    )
    # On regroupe dans scope ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    scope = {
        # On renseigne la saison sous la clé 'year'.
        "year": year,
        # On renseigne les domaines sélectionnés sous la clé 'vineyards'.
        "vineyards": selected,
        # On renseigne le choix de tous les domaines sous la clé 'all_vineyards'.
        "all_vineyards": all_vineyards,
        # On associe la clé 'execution_kind' à cette valeur dans cet objet.
        "execution_kind": "synthetic_rehearsal",
        # On associe la clé 'postgresql_writes' à cette valeur dans cet objet.
        "postgresql_writes": False,
        # On associe la clé 'nas_access' à cette valeur dans cet objet.
        "nas_access": False,
    }
    # On lance les étapes assemblées avec le même contexte et leur journal ; le moteur ne fournit
    # pas de transaction globale couvrant tout le parcours.
    return run_workflow(
        # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
        root, steps, trigger_mode=trigger_mode, scope=scope, journal_sink=journal_sink
    )
