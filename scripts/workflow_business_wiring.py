# Lecture du fichier — Raccordement du socle commun aux opérations Excel, NAS et PostgreSQL.
# On fournit les dépendances réelles à l’assemblage. Cela évite que le moteur du workflow ait à
# connaître directement chaque détail de connexion.
#

"""Raccordement explicite aux fonctions reelles. Construction sans execution.
Pas de commande --run dans cette livraison : controle local uniquement.
"""

# On décrit les champs d’un objet de données sans écrire toute sa construction à la main.
from dataclasses import dataclass, field
# On rend disponibles _project_module depuis workflow_excel_adapter, pour les appels de ce fichier.
from workflow_excel_adapter import _project_module
# On rend disponibles build_nas_executor depuis workflow_nas_executor, pour les appels de ce fichier.
from workflow_nas_executor import build_nas_executor
# On rend disponibles connection_scope, repository_scope, build_journal_sink depuis
# workflow_postgres_adapter, pour les appels de ce fichier.
from workflow_postgres_adapter import (
    connection_scope,
    repository_scope,
    build_journal_sink,
)
# On rend disponibles WorkflowDependencies, build_workflow_steps, validate_selection depuis
# workflow_assembly, pour les appels de ce fichier.
from workflow_assembly import (
    WorkflowDependencies,
    build_workflow_steps,
    validate_selection,
)
# On rend disponibles BusinessConfiguration depuis workflow_business_config, pour les appels de ce
# fichier.
from workflow_business_config import BusinessConfiguration


@dataclass(frozen=True)
class BusinessPlan:
    # On garde dans dependencies la valeur du champ lue avec les règles définies dans ce module.
    dependencies: WorkflowDependencies = field(repr=False)
    # On garde dans steps la valeur du champ lue avec les règles définies dans ce module.
    steps: object = field(repr=False)
    # On garde dans journal_sink la valeur du champ lue avec les règles définies dans ce module.
    journal_sink: object = field(repr=False)
    # On prépare vineyards comme séquence vide ; on la remplira au fil des opérations suivantes.
    vineyards: tuple = ()
    # On initialise all_vineyards à False ; les branches suivantes pourront modifier cet état.
    all_vineyards: bool = False
    # On fixe year à 2026 pour cette étape.
    year: int = 2026


def connect_importer(configuration):
    """Connexion uniquement lors de l'appel par une factory, jamais au controle local."""
    # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas de
    # connexion.
    import psycopg

    # Cette instruction ouvre réellement une connexion PostgreSQL avec les paramètres préparés ; ce
    # n’est plus une simple validation de configuration.
    return psycopg.connect(**dict(configuration.importer), autocommit=True)


# On relie la configuration métier aux opérations concrètes du workflow.
def build_business_plan(
    configuration,
    *,
    vineyards=None,
    all_vineyards=False,
    year=2026,
    timeout_seconds=3600,
):
    # Cette branche traite le cas où le type reçu ne correspond pas à BusinessConfiguration.
    if not isinstance(configuration, BusinessConfiguration):
        # On interrompt cette branche avec ValueError : 'Configuration capturee explicite requise.'.
        raise ValueError("Configuration capturee explicite requise.")
    # On validu choix des domaines avant de construire les étapes ; choisir tous les domaines et
    # une liste explicite serait contradictoire.
    selected = validate_selection(vineyards, all_vineyards)
    # On garde configuration.root sous le nom root ; cette affectation ne copie pas à elle seule un
    # objet mutable.
    root = configuration.root
    # On prépare un exécuteur avec les deux racines NAS et la durée maximale autorisée. Il ne lit
    # pas encore les acquisitions : il sera fourni aux étapes.
    executor = build_nas_executor(
        root,
        # On passe la racine des données brutes explicitement, sans la deviner depuis le poste.
        nas_brut_root=configuration.nas_brut_root,
        # On passe séparément la racine des résultats de traitement.
        nas_processing_root=configuration.nas_processing_root,
        # On fournit le délai maximal en secondes via le paramètre timeout_seconds de cet appel.
        timeout_seconds=timeout_seconds,
    )
    # On charge le module suivi_traitements_post_saison.ingestion.tracking_versioning de cette copie
    # ; le helper contrôle son emplacement pour ne pas mélanger deux projets présents sur le poste.
    tracking = _project_module(
        root,
        "suivi_traitements_post_saison.ingestion.tracking_versioning",
        "src/suivi_traitements_post_saison/ingestion/tracking_versioning.py",
    )
    # On charge le module import_excel_publication de cette copie ; le helper contrôle son
    # emplacement pour ne pas mélanger deux projets présents sur le poste.
    excel = _project_module(
        root, "import_excel_publication", "scripts/import_excel_publication.py"
    )
    # On charge le module load_nas_reconciliation de cette copie ; le helper contrôle son
    # emplacement pour ne pas mélanger deux projets présents sur le poste.
    nas = _project_module(
        root, "load_nas_reconciliation", "scripts/load_nas_reconciliation.py"
    )
    # On charge le module run_local_pipeline de cette copie ; le helper contrôle son emplacement
    # pour ne pas mélanger deux projets présents sur le poste.
    pilot = _project_module(root, "run_local_pipeline", "scripts/run_local_pipeline.py")
    # On prépare une fabrique de connexions vérifiées. La lambda reporte la connexion au moment où
    # une opération en a réellement besoin.
    opened = connection_scope(
        lambda: connect_importer(configuration), "suivi_acquisitions"
    )

    def execute(root, reference, selected, year, *, stop_on_error):
        # Au moment de l’appel, on fait passer le parcours NAS par l’exécuteur encadré au lieu de
        # lancer ses commandes sans ces contrôles.
        return pilot.execute_pipeline(
            root,
            reference,
            selected,
            year,
            # On décide si le parcours s’arrête dès la première erreur, au lieu de laisser ce choix
            # implicite.
            stop_on_error=stop_on_error,
            executor=executor,
        )

    # On rassemble les opérations concrètes : lecture Excel, préparation des lots, contrôles NAS et
    # repositories SQL. Le moteur ne dépend ainsi pas directement de leurs détails.
    dependencies = WorkflowDependencies(
        tracking.run_ingestion,
        excel.prepare_bundle,
        excel.check_still_current,
        pilot.select_vineyards,
        execute,
        nas.prepare_bundle,
        nas.check_files,
        repository_scope(root, opened, "excel"),
        repository_scope(root, opened, "nas"),
        excel.import_bundle,
        nas.import_bundle,
    )
    # On assemble le parcours et ses dépendances ; on distingue cette préparation du lancement
    # effectif du workflow.
    steps = build_workflow_steps(
        root,
        dependencies=dependencies,
        # On transmet la sélection explicite des domaines concernés par cet appel.
        vineyards=vineyards,
        # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
        all_vineyards=all_vineyards,
        # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
        year=year,
    )
    # On prépare le destinataire des événements dans la base métier. Ce journal complète les runs
    # techniques conservés séparément par Airflow.
    sink = build_journal_sink(root, opened=opened)
    # Le plan regroupe les étapes et leurs paramètres pour le lancement ultérieur ; retourner ce
    # plan ne lance pas l’ingestion.
    return BusinessPlan(
        dependencies, tuple(steps), sink, tuple(selected), all_vineyards, year
    )
