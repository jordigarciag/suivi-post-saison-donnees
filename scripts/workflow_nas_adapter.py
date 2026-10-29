# Lecture du fichier — Raccordement de l’observation NAS au workflow et aux données Excel retenues.
# On prépare le périmètre, exécute l’observation et contrôle le lot obtenu. Les liens avec les mêmes
# données Excel sont vérifiés aux transitions prévues.
#

"""Raccord du pilote au socle ; traitements reels non actives dans ce lot.
Le vrai pilote exige un executor explicitement fourni dans un futur lot.
"""

# On décrit les champs d’un objet de données sans écrire toute sa construction à la main.
from dataclasses import dataclass
# On rend disponibles datetime depuis datetime, pour les appels de ce fichier.
from datetime import datetime
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re

# On rend disponibles _project_module, assert_excel_snapshot depuis workflow_excel_adapter, pour les
# appels de ce fichier.
from workflow_excel_adapter import _project_module, assert_excel_snapshot


@dataclass(frozen=True)
class PipelineAttempt:
    # On déclare le champ pipeline_execution_id avec le type attendu str ; sa valeur sera fournie lors
    # de la construction de l’objet.
    pipeline_execution_id: str
    # On déclare le champ manifest_path avec le type attendu Path ; sa valeur sera fournie lors de la
    # construction de l’objet.
    manifest_path: Path
    # On déclare le champ manifest_relative_path avec le type attendu str ; sa valeur sera fournie lors
    # de la construction de l’objet.
    manifest_relative_path: str
    # On déclare le champ manifest_sha256 avec le type attendu str ; sa valeur sera fournie lors de la
    # construction de l’objet.
    manifest_sha256: str
    # On déclare le champ vineyards avec le type attendu tuple ; sa valeur sera fournie lors de la
    # construction de l’objet.
    vineyards: tuple
    # On déclare le champ year avec le type attendu int ; sa valeur sera fournie lors de la
    # construction de l’objet.
    year: int


def _select(root, reference, requested, all_vineyards, year):
    # On fournit à l’appelant la valeur renvoyée par _project_module(root, 'run_local_pipeline',
    # 'scripts/run_local_pipeline.py').select_vineyards.
    return _project_module(
        root, "run_local_pipeline", "scripts/run_local_pipeline.py"
    ).select_vineyards(reference, requested, all_vineyards, year)


def _prepare(root, relative):
    # On fournit à l’appelant le lot préparé et contrôlé par le module appelé.
    return _project_module(
        root, "load_nas_reconciliation", "scripts/load_nas_reconciliation.py"
    ).prepare_bundle(root, relative)


def _files(root, bundle):
    # On appelle _project_module(root, 'load_nas_reconciliation',
    # 'scripts/load_nas_reconciliation.py').check_files avec bundle.
    _project_module(
        root, "load_nas_reconciliation", "scripts/load_nas_reconciliation.py"
    ).check_files(bundle)


def _local_manifest(root, returned):
    # Cette branche traite le cas où le type reçu ne correspond pas à (str, Path).
    if not isinstance(returned, (str, Path)):
        # On interrompt cette branche avec ValueError : 'Chemin du manifeste du pilote invalide.'.
        raise ValueError("Chemin du manifeste du pilote invalide.")
    # On garde dans path un objet chemin local ; sa construction seule ne prouve pas que le fichier
    # existe.
    path = Path(returned)
    # On choisit la valeur de path selon ce test : le chemin de travail est absolu. Les deux résultats
    # possibles restent définis explicitement ici.
    path = path if path.is_absolute() else root / path
    # On construit base en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    base = root / "data/03_normalized/pipeline_runs"
    # On attend le manifeste à sa place dans les résultats du pipeline ; un fichier du même nom
    # ailleurs ne suffit pas.
    if not base.resolve().is_relative_to(root):
        # On interrompt cette branche avec ValueError : 'Dossier du pilote hors du projet local.'.
        raise ValueError("Dossier du pilote hors du projet local.")
    # On calcule le chemin local résolu pour détecter les redirections avant de vérifier qu’il reste
    # dans le projet.
    resolved = path.resolve()
    # On attend le manifeste à sa place dans les résultats du pipeline ; un fichier du même nom
    # ailleurs ne suffit pas.
    if (
        not resolved.is_relative_to(base.resolve())
        # Ce cas est aussi retenu si path.name diffère du texte 'manifest.json'.
        or path.name != "manifest.json"
        # Ce cas est aussi retenu si path.parent.parent.resolve() diffère de base.resolve().
        or path.parent.parent.resolve() != base.resolve()
    ):
        # On interrompt cette branche avec ValueError : 'Manifeste hors du dossier d execution
        # attendu.'.
        raise ValueError("Manifeste hors du dossier d execution attendu.")
    # Cette branche traite le cas où la condition re.fullmatch('[0-9]{8}_[0-9a-f]{8}',
    # path.parent.name) n’est pas remplie.
    if not re.fullmatch(r"[0-9]{8}_[0-9a-f]{8}", path.parent.name):
        # On interrompt cette branche avec ValueError : 'Identifiant du dossier du pilote invalide.'.
        raise ValueError("Identifiant du dossier du pilote invalide.")
    # On remet le chemin de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return path


def _validate_manifest(root, path, pinned, vineyards, year):
    # On garde dans raw les octets lus depuis path, avant toute conversion en texte. Les contrôles
    # de contenu pourront ainsi repartir de cette lecture.
    raw = path.read_bytes()
    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    manifest = json.loads(raw.decode("utf-8-sig"))
    # Cette branche traite le cas où le type reçu ne correspond pas à dict ou
    # manifest.get('pipeline_execution_id') diffère de path.parent.name.
    if (
        not isinstance(manifest, dict)
        # Ce cas est aussi retenu si manifest.get('pipeline_execution_id') diffère de path.parent.name.
        or manifest.get("pipeline_execution_id") != path.parent.name
    ):
        # On interrompt cette branche avec ValueError : 'Identifiant du manifeste incompatible avec son
        # dossier.'.
        raise ValueError("Identifiant du manifeste incompatible avec son dossier.")
    # Cette branche traite le cas où type(manifest.get('project_year')) n’est pas exactement int ou
    # manifest['project_year'] diffère de la saison.
    if (
        type(manifest.get("project_year")) is not int
        # Ce cas est aussi retenu si manifest['project_year'] diffère de la saison.
        or manifest["project_year"] != year
    ):
        # On interrompt cette branche avec ValueError : 'Annee du manifeste incompatible avec le
        # perimetre.'.
        raise ValueError("Annee du manifeste incompatible avec le perimetre.")
    # On garde dans source le champ 'reference_source' de manifest, ou None si la clé est absente.
    source = manifest.get("reference_source")
    # On garde dans snapshot le champ 'reference_snapshot' de manifest, ou None si la clé est absente.
    snapshot = manifest.get("reference_snapshot")
    # Cette branche traite le cas où le type reçu ne correspond pas à str ou le type reçu ne correspond
    # pas à str.
    if not isinstance(source, str) or not isinstance(snapshot, str):
        # On interrompt cette branche avec ValueError : 'Liens de reference du pilote absents.'.
        raise ValueError("Liens de reference du pilote absents.")
    # On choisit la valeur de source_path selon ce test : Path(source) est absolu. Les deux résultats
    # possibles restent définis explicitement ici.
    source_path = Path(source) if Path(source).is_absolute() else root / source
    # On choisit la valeur de snapshot_path selon ce test : Path(snapshot) est absolu. Les deux
    # résultats possibles restent définis explicitement ici.
    snapshot_path = Path(snapshot) if Path(snapshot).is_absolute() else root / snapshot
    # On vérifie ce cas avant la suite : source_path.resolve() diffère de
    # pinned.reference_path.resolve().
    if source_path.resolve() != pinned.reference_path.resolve():
        # On interrompt cette branche avec ValueError : 'Le pilote a utilise une autre reference
        # Excel.'.
        raise ValueError("Le pilote a utilise une autre reference Excel.")
    # La copie des données Excel doit être celle conservée à côté de ce manifeste.
    if snapshot_path.resolve() != (
        path.parent / "tracking_reference_snapshot.csv"
    # Ce cas est aussi retenu si la condition snapshot_path.resolve().is_relative_to(root) n’est pas
    # remplie.
    ).resolve() or not snapshot_path.resolve().is_relative_to(root):
        # On interrompt cette branche avec ValueError : 'Snapshot de reference hors du dossier
        # attendu.'.
        raise ValueError("Snapshot de reference hors du dossier attendu.")
    # On compare l’empreinte des octets actuels à celle du lot attendu ; une différence doit bloquer
    # le mélange de versions.
    if (
        manifest.get("reference_sha256") != pinned.reference_sha256
        # Ce cas est aussi retenu si hashlib.sha256(snapshot_path.read_bytes()).hexdigest() diffère de
        # pinned.reference_sha256.
        or hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
        != pinned.reference_sha256
    ):
        # On interrompt cette branche avec ValueError : 'Empreinte du snapshot incompatible avec la
        # reference figee.'.
        raise ValueError("Empreinte du snapshot incompatible avec la reference figee.")
    # On garde dans items le champ 'vineyards' de manifest, ou None si la clé est absente.
    items = manifest.get("vineyards")
    # Cette branche traite le cas où le type reçu ne correspond pas à list ou au moins un élément
    # satisfait le test indiqué ou [item.get('vineyard') for item in items] diffère de list(vineyards).
    if (
        not isinstance(items, list)
        # Ce cas est aussi retenu si au moins un élément satisfait le test indiqué.
        or any(not isinstance(item, dict) for item in items)
        # Ce cas est aussi retenu si [item.get('vineyard') for item in items] diffère de
        # list(vineyards).
        or [item.get("vineyard") for item in items] != list(vineyards)
    ):
        # On interrompt cette branche avec ValueError : 'Vignobles du manifeste differents du perimetre
        # selectionne.'.
        raise ValueError("Vignobles du manifeste differents du perimetre selectionne.")
    # On tente ce bloc et on traite séparément les erreurs prévues : (KeyError, TypeError, ValueError).
    try:
        # On interprète la date ISO reçue ; les vérifications de fuseau et de cohérence restent
        # nécessaires après cette conversion.
        start = datetime.fromisoformat(manifest["started_at"].replace("Z", "+00:00"))
        # On garde dans end la date interprétée depuis son écriture ISO.
        end = datetime.fromisoformat(manifest["finished_at"].replace("Z", "+00:00"))
        # On calcule valid avec ces conditions liées par and ; Python s’arrête dès qu’une valeur est
        # évaluée comme fausse.
        valid = start.tzinfo is not None and end.tzinfo is not None and end >= start
    except (KeyError, TypeError, ValueError):
        # On initialise valid à False ; les branches suivantes pourront modifier cet état.
        valid = False
    # On prévoit le cas où valid est évalué comme faux, par exemple une valeur vide selon son type.
    if not valid:
        # On interrompt cette branche avec ValueError : 'Dates de cloture du pilote invalides.'.
        raise ValueError("Dates de cloture du pilote invalides.")
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return manifest, hashlib.sha256(raw).hexdigest()


def _context_root(context, root):
    # On vérifie ce cas avant la suite : context.root diffère de la racine locale du projet.
    if context.root != root:
        # On interrompt cette branche avec ValueError : 'Racines du pilote et du socle differentes.'.
        raise ValueError("Racines du pilote et du socle differentes.")


# On prépare les opérations de périmètre, d’observation et de contrôle du lot NAS.
def build_nas_steps(
    root,
    *,
    vineyards=None,
    all_vineyards=False,
    year=2026,
    select=None,
    execute=None,
    prepare=None,
    ensure_excel=None,
    ensure_nas=None,
    executor=None,
):
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où type(year) n’est pas exactement int ou la condition 1900 <= year
    # <= 2200 n’est pas remplie.
    if type(year) is not int or not 1900 <= year <= 2200:
        # On interrompt cette branche avec ValueError : 'Annee du perimetre invalide.'.
        raise ValueError("Annee du perimetre invalide.")
    # Cette branche traite le cas où type(all_vineyards) n’est pas exactement bool ou bool(vineyards)
    # correspond au choix de tous les domaines.
    if type(all_vineyards) is not bool or bool(vineyards) == all_vineyards:
        # On interrompt cette branche avec ValueError : 'Choisir des vignobles explicites OU tous les
        # vignobles.'.
        raise ValueError("Choisir des vignobles explicites OU tous les vignobles.")
    # Cette branche traite le cas où les domaines sélectionnés est renseigné (différent de None) et le
    # type reçu ne correspond pas à (list, tuple) ou au moins un élément satisfait le test indiqué.
    if vineyards is not None and (
        not isinstance(vineyards, (list, tuple))
        # Ce cas est aussi retenu si au moins un élément satisfait le test indiqué.
        or any(not isinstance(n, str) or not n.strip() for n in vineyards)
    ):
        # On interrompt cette branche avec ValueError : 'Liste de vignobles invalide.'.
        raise ValueError("Liste de vignobles invalide.")
    # On prépare requested comme liste vide ; on la remplira au fil des opérations suivantes.
    requested = []
    # On parcourt vineyards or [] ; name désigne l’élément courant à chaque passage dans la boucle.
    for name in vineyards or []:
        # On retire les espaces de bord du nom avant du comparer aux noms déjà retenus.
        name = name.strip()
        # On compare les noms sans tenir compte des majuscules pour ne pas sélectionner deux fois le
        # même domaine sous deux écritures.
        if name.casefold() not in {n.casefold() for n in requested}:
            # On ajoute name à la fin de requested ; les éléments précédents restent conservés.
            requested.append(name)
    # On retient pour selector la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    selector = select or (
        lambda reference, names, all_flag, y: _select(
            root, reference, names, all_flag, y
        )
    )
    # On retient pour preparer la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    preparer = prepare or _prepare
    # On retient pour excel_guard la première valeur évaluée comme vraie dans cette chaîne de replis ;
    # une valeur vide fera donc passer à la suivante.
    excel_guard = ensure_excel or assert_excel_snapshot
    # On retient pour nas_guard la première valeur évaluée comme vraie dans cette chaîne de replis ;
    # une valeur vide fera donc passer à la suivante.
    nas_guard = ensure_nas or (lambda bundle: _files(root, bundle))
    # Cette branche traite le cas où executor est renseigné (différent de None) et la condition
    # callable(executor) n’est pas remplie.
    if executor is not None and not callable(executor):
        # On interrompt cette branche avec ValueError : 'Executor invalide.'.
        raise ValueError("Executor invalide.")
    # On vérifie ce cas avant la suite : execute vaut None.
    if execute is None:

        def execute(local_root, reference, names, y, *, stop_on_error):
            # On vérifie ce cas avant la suite : executor vaut None.
            if executor is None:
                # On interrompt cette branche avec RuntimeError : 'Execution NAS reelle non activee :
                # executor securise a fournir dans un futur lot.'.
                raise RuntimeError(
                    "Execution NAS reelle non activee : executor securise a fournir dans un futur lot."
                )
            # On charge le module run_local_pipeline de cette copie ; le helper contrôle son
            # emplacement pour ne pas mélanger deux projets présents sur le poste.
            module = _project_module(
                root, "run_local_pipeline", "scripts/run_local_pipeline.py"
            )
            # On fournit à l’appelant la valeur renvoyée par module.execute_pipeline.
            return module.execute_pipeline(
                local_root,
                reference,
                names,
                y,
                # On décide si le parcours s’arrête dès la première erreur, au lieu de laisser ce choix
                # implicite.
                stop_on_error=stop_on_error,
                executor=executor,
            )

    # Cette branche traite le cas où la condition all((callable(fn) for fn in (selector, execute,
    # preparer, excel_guard, nas_guard))) n’est pas remplie.
    if not all(
        callable(fn) for fn in (selector, execute, preparer, excel_guard, nas_guard)
    ):
        # On interrompt cette branche avec ValueError : 'Fonctions de l adaptateur invalides.'.
        raise ValueError("Fonctions de l adaptateur invalides.")

    def scope_prepare(context):
        # On appelle _context_root avec context.
        _context_root(context, root)
        # On garde dans pinned la valeur renvoyée par excel_guard.
        pinned = excel_guard(context)
        # On garde dans selected la valeur renvoyée par selector.
        selected = selector(pinned.reference_path, list(requested), all_vineyards, year)
        # Cette branche traite le cas où au moins un des cas regroupés ici est rencontré.
        if (
            not isinstance(selected, list)
            # Ce cas est aussi retenu si la condition selected n’est pas remplie.
            or not selected
            # Ce cas est aussi retenu si au moins un élément satisfait le test indiqué.
            or any(not isinstance(n, str) or not n.strip() for n in selected)
            # Ce cas est aussi retenu si len({n.casefold() for n in selected}) diffère de
            # len(selected).
            or len({n.casefold() for n in selected}) != len(selected)
        ):
            # On interrompt cette branche avec ValueError : 'Selection du pilote vide ou
            # contradictoire.'.
            raise ValueError("Selection du pilote vide ou contradictoire.")
        # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
        # information par sa clé.
        return {"vineyards": tuple(selected), "year": year}

    def pipeline_execute(context):
        # On appelle _context_root avec context.
        _context_root(context, root)
        # On garde dans pinned la valeur renvoyée par excel_guard.
        pinned = excel_guard(context)
        # On récupère les domaines sélectionnés dans context.results['nas_scope_prepare'] et on le
        # garde dans selected pour la suite.
        selected = context.results["nas_scope_prepare"]["vineyards"]
        # On construit base en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
        # ni dossier ni fichier.
        base = root / "data/03_normalized/pipeline_runs"
        # Le dossier des résultats doit rester local au projet avant de lancer l’observation.
        if not base.resolve().is_relative_to(root):
            # On interrompt cette branche avec ValueError : 'Dossier du pilote hors du projet local.'.
            raise ValueError("Dossier du pilote hors du projet local.")
        # On choisit la valeur de previous selon ce test : base désigne un dossier. Les deux résultats
        # possibles restent définis explicitement ici.
        previous = {p.name for p in base.iterdir()} if base.is_dir() else set()
        # On garde dans outcome la valeur renvoyée par execute.
        outcome = execute(
            # On décide si le parcours s’arrête dès la première erreur, au lieu de laisser ce choix
            # implicite.
            root, pinned.reference_path, list(selected), year, stop_on_error=True
        )
        # Cette branche traite le cas où le type reçu ne correspond pas à tuple ou len(outcome) diffère
        # de 2 ou type(outcome[0]) n’est pas exactement int.
        if (
            not isinstance(outcome, tuple)
            # Ce cas est aussi retenu si len(outcome) diffère de 2.
            or len(outcome) != 2
            # Ce cas est aussi retenu si type(outcome[0]) n’est pas exactement int.
            or type(outcome[0]) is not int
        ):
            # On interrompt cette branche avec ValueError : 'Resultat du pilote incomplet.'.
            raise ValueError("Resultat du pilote incomplet.")
        # On répartit les éléments de outcome entre (code, returned), dans l’ordre indiqué.
        code, returned = outcome
        # On garde dans path la valeur renvoyée par _local_manifest.
        path = _local_manifest(root, returned)
        # On vérifie ce cas avant la suite : path.parent.name appartient à previous.
        if path.parent.name in previous:
            # On interrompt cette branche avec ValueError : 'Le pilote a retourne une execution deja
            # presente avant cet appel.'.
            raise ValueError(
                "Le pilote a retourne une execution deja presente avant cet appel."
            )
        # On répartit les valeurs renvoyées par _validate_manifest entre (manifest, sha) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        manifest, sha = _validate_manifest(root, path, pinned, selected, year)
        # On rattache le contexte à ce lot pour empêcher un changement silencieux d’identifiant en
        # cours de traitement.
        context.pin_ids(pipeline_execution_id=manifest["pipeline_execution_id"])
        # Cette branche traite le cas où le code de retour correspond à 130 et manifest.get('status')
        # correspond au texte 'interrupted'.
        if code == 130 and manifest.get("status") == "interrupted":
            # On interrompt cette branche avec KeyboardInterrupt.
            raise KeyboardInterrupt()
        # Cette branche traite le cas où le code de retour diffère de 0 ou manifest.get('status')
        # diffère du texte 'success' ou au moins un élément satisfait le test indiqué.
        if (
            code != 0
            # Ce cas est aussi retenu si manifest.get('status') diffère du texte 'success'.
            or manifest.get("status") != "success"
            # Ce cas est aussi retenu si au moins un élément satisfait le test indiqué.
            or any(item.get("status") != "success" for item in manifest["vineyards"])
        ):
            # On interrompt cette branche avec ValueError : 'Pilote non reussi ou partiel : controles
            # et chargements suivants bloques.'.
            raise ValueError(
                "Pilote non reussi ou partiel : controles et chargements suivants bloques."
            )
        # On fournit à l’appelant la valeur renvoyée par PipelineAttempt.
        return PipelineAttempt(
            manifest["pipeline_execution_id"],
            path,
            path.relative_to(root).as_posix(),
            sha,
            tuple(selected),
            year,
        )

    def bundle_check(context):
        # On appelle _context_root avec context.
        _context_root(context, root)
        # On garde dans pinned la valeur renvoyée par excel_guard.
        pinned = excel_guard(context)
        # On reprend le résultat de l’étape NAS dans context.results ; cet accès suppose que la clé
        # a été produite ou vérifiée auparavant.
        attempt = context.results["nas_pipeline_execute"]
        # On compare l’empreinte des octets actuels à celle du lot attendu ; une différence doit
        # bloquer le mélange de versions.
        if (
            hashlib.sha256(attempt.manifest_path.read_bytes()).hexdigest()
            != attempt.manifest_sha256
        ):
            # On interrompt cette branche avec ValueError : 'Manifeste modifie apres execution du
            # pilote.'.
            raise ValueError("Manifeste modifie apres execution du pilote.")
        # On garde dans bundle la valeur renvoyée par preparer.
        bundle = preparer(root, attempt.manifest_relative_path)
        # On appelle nas_guard avec bundle.
        nas_guard(bundle)
        # On appelle _check_bundle_links avec context.
        _check_bundle_links(context, bundle, attempt, pinned)
        # On vérifie ce cas avant la suite :
        # hashlib.sha256(attempt.manifest_path.read_bytes()).hexdigest() diffère de
        # attempt.manifest_sha256.
        if (
            hashlib.sha256(attempt.manifest_path.read_bytes()).hexdigest()
            != attempt.manifest_sha256
        ):
            # On interrompt cette branche avec ValueError : 'Manifeste modifie pendant les controles.'.
            raise ValueError("Manifeste modifie pendant les controles.")
        # On remet le lot préparé à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return bundle

    # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return [
        ("nas_scope_prepare", scope_prepare),
        ("nas_pipeline_execute", pipeline_execute),
        ("nas_bundle_check", bundle_check),
    ]


def _check_bundle_links(context, bundle, attempt, pinned):
    # On récupère le bilan dans bundle et on le garde dans report pour la suite.
    report = bundle["report"]
    # Cette branche traite le cas où report.get('pipeline_execution_id') diffère de
    # attempt.pipeline_execution_id ou report.get('excel_publication_id') diffère de
    # pinned.publication_id.
    if (
        report.get("pipeline_execution_id") != attempt.pipeline_execution_id
        # Ce cas est aussi retenu si report.get('excel_publication_id') diffère de
        # pinned.publication_id.
        or report.get("excel_publication_id") != pinned.publication_id
    ):
        # On interrompt cette branche avec ValueError : 'Le lot NAS ne correspond pas aux identifiants
        # de cette execution.'.
        raise ValueError(
            "Le lot NAS ne correspond pas aux identifiants de cette execution."
        )
    # On vérifie ce cas avant la suite : la publication Excel dans bundle diffère de la publication
    # Excel dans context.results['excel_publication_ch….
    if (
        bundle["publication"]
        != context.results["excel_publication_check"]["publication"]
    ):
        # On interrompt cette branche avec ValueError : 'Le lot NAS utilise une autre publication
        # Excel.'.
        raise ValueError("Le lot NAS utilise une autre publication Excel.")
    # On vérifie ce cas avant la suite : le manifeste du lot dans bundle diffère de
    # json.loads(attempt.manifest_path.read_text(encoding='utf-8-sig')).
    if bundle["manifest"] != json.loads(
        attempt.manifest_path.read_text(encoding="utf-8-sig")
    ):
        # On interrompt cette branche avec ValueError : 'Le lot NAS ne correspond pas au manifeste
        # controle.'.
        raise ValueError("Le lot NAS ne correspond pas au manifeste controle.")


# On vérifie les liens du lot NAS avec le contexte et les données Excel de l’exécution.
def assert_nas_snapshot(context, *, ensure_excel=None, ensure_nas=None):
    # On garde dans pinned la valeur renvoyée par ensure_excel or assert_excel_snapshot.
    pinned = (ensure_excel or assert_excel_snapshot)(context)
    # On garde dans attempt le champ 'nas_pipeline_execute' de context.results, ou None si la clé est
    # absente.
    attempt = context.results.get("nas_pipeline_execute")
    # On garde dans bundle le champ 'nas_bundle_check' de context.results, ou None si la clé est
    # absente.
    bundle = context.results.get("nas_bundle_check")
    # Cette branche traite le cas où le type reçu ne correspond pas à PipelineAttempt ou le lot préparé
    # vaut None.
    if not isinstance(attempt, PipelineAttempt) or bundle is None:
        # On interrompt cette branche avec ValueError : 'Lot NAS non controle dans cette execution.'.
        raise ValueError("Lot NAS non controle dans cette execution.")
    # On appelle ensure_nas or (lambda b: _files(context.root, b)) avec bundle.
    (ensure_nas or (lambda b: _files(context.root, b)))(bundle)
    # On compare l’empreinte des octets actuels à celle du lot attendu ; une différence doit bloquer
    # le mélange de versions.
    if (
        context.linked_ids()["pipeline_execution_id"] != attempt.pipeline_execution_id
        # Ce cas est aussi retenu si hashlib.sha256(attempt.manifest_path.read_bytes()).hexdigest()
        # diffère de attempt.manifest_sha256.
        or hashlib.sha256(attempt.manifest_path.read_bytes()).hexdigest()
        != attempt.manifest_sha256
    ):
        # On interrompt cette branche avec ValueError : 'Identifiant ou manifeste NAS different du
        # resultat controle.'.
        raise ValueError("Identifiant ou manifeste NAS different du resultat controle.")
    # On appelle _check_bundle_links avec context.
    _check_bundle_links(context, bundle, attempt, pinned)
    # On remet le lot préparé à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return bundle
