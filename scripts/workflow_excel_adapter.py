# Lecture du fichier — Trois étapes Excel : ingestion, contrôle de publication et conservation de la version utilisée.
# On travaille à partir d’une photographie des données : toutes les étapes doivent se rattacher au
# même lot. Un changement détecté peut interrompre la suite, plutôt que mélanger deux versions.
#

"""Adaptateur Excel du socle commun ; aucun traitement declenche a l'import.
Trois callbacks : ingestion, controle de publication, reference figee.
Aucun PostgreSQL, aucun NAS. Pas encore de commande de pipeline complet.
"""

# On décrit les champs d’un objet de données sans écrire toute sa construction à la main.
from dataclasses import dataclass
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe importlib. Ce module sera utilisé par les opérations de ce fichier.
import importlib
# On rend disponibles Path, PurePosixPath depuis pathlib, pour les appels de ce fichier.
from pathlib import Path, PurePosixPath
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys


@dataclass(frozen=True)
class PinnedExcel:
    # On déclare le champ publication_id avec le type attendu str ; sa valeur sera fournie lors de la
    # construction de l’objet.
    publication_id: str
    # On déclare le champ reference_path avec le type attendu Path ; sa valeur sera fournie lors de la
    # construction de l’objet.
    reference_path: Path
    # On déclare le champ reference_sha256 avec le type attendu str ; sa valeur sera fournie lors de la
    # construction de l’objet.
    reference_sha256: str


def _project_module(root, name, relative):
    # On construit directory en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    directory = root / (
        "src" if name.startswith("suivi_traitements_post_saison.") else "scripts"
    )
    # On vérifie ce cas avant la suite : str(directory) ne figure pas dans sys.path.
    if str(directory) not in sys.path:
        # On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux
        # importables dans ce contexte.
        sys.path.insert(0, str(directory))
    # On charge le module par son nom ; le contrôle qui suit peut vérifier qu’il provient bien de
    # cette copie du projet.
    module = importlib.import_module(name)
    # Un autre exemplaire du projet a été importé. On refuse de mélanger son code avec les fichiers
    # de cette copie.
    if Path(module.__file__).resolve() != (root / relative).resolve():
        # On interrompt cette branche avec RuntimeError : 'Module charge depuis un autre projet :
        # arreter sans rechargement automatique.'.
        raise RuntimeError(
            "Module charge depuis un autre projet : arreter sans rechargement automatique."
        )
    # On remet module à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return module


def _ingest(root, vineyards, all_vineyards):
    # On charge le module suivi_traitements_post_saison.ingestion.tracking_versioning de cette copie
    # ; le helper contrôle son emplacement pour ne pas mélanger deux projets présents sur le poste.
    module = _project_module(
        root,
        "suivi_traitements_post_saison.ingestion.tracking_versioning",
        "src/suivi_traitements_post_saison/ingestion/tracking_versioning.py",
    )
    # On fournit à l’appelant la valeur renvoyée par module.run_ingestion.
    return module.run_ingestion(root, vineyards=vineyards, all_vineyards=all_vineyards)


def _prepare(root):
    # On fournit à l’appelant le lot préparé et contrôlé par le module appelé.
    return _project_module(
        root, "import_excel_publication", "scripts/import_excel_publication.py"
    ).prepare_bundle(root)


def _current(root, bundle):
    # On appelle _project_module(root, 'import_excel_publication',
    # 'scripts/import_excel_publication.py').check_still_current avec bundle.
    _project_module(
        root, "import_excel_publication", "scripts/import_excel_publication.py"
    ).check_still_current(bundle)


def _reference_info(root, publication):
    # Cette branche traite le cas où le type reçu ne correspond pas à dict.
    if not isinstance(publication, dict):
        # On interrompt cette branche avec ValueError : 'Publication Excel invalide.'.
        raise ValueError("Publication Excel invalide.")
    # On récupère l’identifiant du lot Excel. Une clé absente donne None ici ; les contrôles
    # suivants doivent décider si c’est acceptable.
    publication_id = publication.get("publication_id")
    # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition
    # re.fullmatch('[A-Za-z0-9_-]+', publication_id) n’est pas remplie.
    if not isinstance(publication_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]+", publication_id
    ):
        # On interrompt cette branche avec ValueError : 'Identifiant de publication Excel invalide.'.
        raise ValueError("Identifiant de publication Excel invalide.")
    # On récupère les métadonnées du tableau Excel regroupé. Une clé absente donne None ici ; les
    # contrôles suivants doivent décider si c’est acceptable.
    reference = publication.get("reference")
    # Cette branche traite le cas où le type reçu ne correspond pas à dict.
    if not isinstance(reference, dict):
        # On interrompt cette branche avec ValueError : 'Reference de publication absente.'.
        raise ValueError("Reference de publication absente.")
    # On garde dans relative le champ 'path' de reference, ou None si la clé est absente.
    relative = reference.get("path")
    # On récupère l’empreinte de contenu attendue. Une clé absente donne None ici ; les contrôles
    # suivants doivent décider si c’est acceptable.
    sha = reference.get("sha256")
    # On assemble ces deux éléments pour construire expected.
    expected = (
        "data/03_normalized/suivi_acquisitions_normalises/publications/"
        + publication_id
        + "/reference.csv"
    )
    # Cette branche traite le cas où au moins un des cas regroupés ici est rencontré.
    if (
        not isinstance(relative, str)
        # Ce cas est aussi retenu si le texte '\\' appartient au chemin relatif.
        or "\\" in relative
        # Ce cas est aussi retenu si PurePosixPath(relative).as_posix() diffère du résultat attendu.
        or PurePosixPath(relative).as_posix() != expected
        # Ce cas est aussi retenu si le chemin relatif diffère du résultat attendu.
        or relative != expected
    ):
        # On interrompt cette branche avec ValueError : 'Reference hors de la publication immutable
        # attendue.'.
        raise ValueError("Reference hors de la publication immutable attendue.")
    # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition
    # re.fullmatch('[0-9a-f]{64}', sha) n’est pas remplie.
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        # On interrompt cette branche avec ValueError : 'Empreinte de reference invalide.'.
        raise ValueError("Empreinte de reference invalide.")
    # On calcule ce quotient pour construire path.
    path = root / relative
    # Le tableau Excel utilisé doit rester dans les données de cette publication, pas pointer vers
    # une autre copie.
    if not path.resolve().is_relative_to(
        (root / "data").resolve()
    # Ce cas est aussi retenu si la condition path.resolve().is_relative_to(root) n’est pas remplie.
    ) or not path.resolve().is_relative_to(root):
        # On interrompt cette branche avec ValueError : 'Reference redirigee hors du projet local.'.
        raise ValueError("Reference redirigee hors du projet local.")
    # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return publication_id, path, sha


def _context_root(context, root):
    # On vérifie ce cas avant la suite : context.root diffère de la racine locale du projet.
    if context.root != root:
        # On interrompt cette branche avec ValueError : 'Racines du socle et de l adaptateur
        # differentes.'.
        raise ValueError("Racines du socle et de l adaptateur differentes.")


# On prépare les trois opérations Excel avec des dépendances remplaçables pour les tests.
def build_excel_steps(
    root,
    *,
    vineyards=None,
    all_vineyards=False,
    ingest=None,
    prepare=None,
    ensure_current=None,
):
    """Fonctions injectables pour essais ; fonctions existantes par defaut.
    Les statuts success et unchanged continuent tous deux vers les controles.
    """
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où type(all_vineyards) n’est pas exactement bool ou bool(vineyards)
    # correspond au choix de tous les domaines.
    if type(all_vineyards) is not bool or bool(vineyards) == all_vineyards:
        # On interrompt cette branche avec ValueError : 'Choisir des vignobles explicites OU tous les
        # vignobles.'.
        raise ValueError("Choisir des vignobles explicites OU tous les vignobles.")
    # Cette branche traite le cas où les domaines sélectionnés est renseigné (différent de None) et le
    # type reçu ne correspond pas à (list, tuple).
    if vineyards is not None and not isinstance(vineyards, (list, tuple)):
        # On interrompt cette branche avec ValueError : 'Liste de vignobles invalide.'.
        raise ValueError("Liste de vignobles invalide.")
    # On prépare selected comme liste vide ; on la remplira au fil des opérations suivantes.
    selected = []
    # On parcourt vineyards or [] ; name désigne l’élément courant à chaque passage dans la boucle.
    for name in vineyards or []:
        # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition
        # name.strip() n’est pas remplie.
        if not isinstance(name, str) or not name.strip():
            # On interrompt cette branche avec ValueError : 'Vignoble vide ou invalide.'.
            raise ValueError("Vignoble vide ou invalide.")
        # On retire les espaces de bord du nom avant du comparer aux noms déjà retenus.
        name = name.strip()
        # On compare les noms sans tenir compte des majuscules pour ne pas sélectionner deux fois le
        # même domaine sous deux écritures.
        if name.casefold() not in {n.casefold() for n in selected}:
            # On ajoute le nom après le contrôle des doublons ; l’ordre de la sélection initiale
            # reste conservé.
            selected.append(name)
    # L’appelant peut fournir une ingestion de test ; sinon on garde l’ingestion du projet. On
    # choisit la fonction ici, sans encore la lancer.
    ingest = ingest or _ingest
    # Même principe pour la préparation du lot : une dépendance explicite permet de tester cette
    # étape sans relire les sources réelles.
    prepare = prepare or _prepare
    # On utilise le contrôle fourni par l’appelant ; à défaut, le rappel vérifiera la publication
    # locale. Il sera appelé au moment voulu, pas pendant sa définition.
    check = ensure_current or (lambda bundle: _current(root, bundle))
    # Cette branche traite le cas où la condition all((callable(fn) for fn in (ingest, prepare,
    # check))) n’est pas remplie.
    if not all(callable(fn) for fn in (ingest, prepare, check)):
        # On interrompt cette branche avec ValueError : 'Fonctions de l adaptateur invalides.'.
        raise ValueError("Fonctions de l adaptateur invalides.")

    def ingestion(context):
        # On appelle _context_root avec context.
        _context_root(context, root)
        # On garde dans result la valeur renvoyée par ingest.
        result = ingest(
            root,
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=None if all_vineyards else list(selected),
            # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
            all_vineyards=all_vineyards,
        )
        # Cette branche traite le cas où le type reçu ne correspond pas à dict ou result.get('status')
        # ne figure pas dans {'success', 'unchanged'}.
        if not isinstance(result, dict) or result.get("status") not in {
            "success",
            "unchanged",
        }:
            # On interrompt cette branche avec ValueError : 'Ingestion Excel non confirmee ; arreter
            # les etapes suivantes.'.
            raise ValueError(
                "Ingestion Excel non confirmee ; arreter les etapes suivantes."
            )
        # Cette branche traite le cas où le type reçu ne correspond pas à str ou la condition
        # result['publication_id'] n’est pas remplie ou le type reçu ne correspond pas à str.
        if (
            not isinstance(result.get("publication_id"), str)
            # Ce cas est aussi retenu si la condition result['publication_id'] n’est pas remplie.
            or not result["publication_id"]
            # Ce cas est aussi retenu si le type reçu ne correspond pas à str.
            or not isinstance(result.get("reference_path"), str)
        ):
            # On interrompt cette branche avec ValueError : 'Identifiants de sortie Excel incomplets.'.
            raise ValueError("Identifiants de sortie Excel incomplets.")
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    # On vérifie que la publication préparée correspond bien à la sortie de l’ingestion.
    def publication_check(context):
        # On appelle _context_root avec context.
        _context_root(context, root)
        # On garde dans bundle la valeur renvoyée par prepare.
        bundle = prepare(root)
        # On appelle check avec bundle.
        check(bundle)
        # On répartit les valeurs renvoyées par _reference_info entre (publication_id, _, _) ; leur
        # ordre doit correspondre à celui prévu par cet appel.
        publication_id, _, _ = _reference_info(root, bundle["publication"])
        # On reprend la sortie de l’ingestion de ce run pour la comparer au lot préparé, et non à
        # une autre publication trouvée sur le disque.
        source = context.results["excel_ingestion"]
        # Cette branche traite le cas où au moins un des cas regroupés ici est rencontré.
        if (
            source["publication_id"] != publication_id
            # Ce cas est aussi retenu si le chemin du tableau Excel regroupé dans source diffère de le
            # chemin de travail dans bundle['publication']['reference'].
            or source["reference_path"] != bundle["publication"]["reference"]["path"]
        ):
            # On interrompt cette branche avec ValueError : 'Publication preparee differente du
            # resultat d ingestion.'.
            raise ValueError("Publication preparee differente du resultat d ingestion.")
        # On remet le lot préparé à l’appelant ; les étapes suivantes de cette fonction ne sont plus
        # parcourues.
        return bundle

    # On conserve l’identifiant et l’empreinte du tableau Excel utilisé par la suite.
    def reference_pin(context):
        # On appelle _context_root avec context.
        _context_root(context, root)
        # On reprend le lot Excel déjà contrôlé dans context.results ; cet accès suppose que la clé
        # a été produite ou vérifiée auparavant.
        bundle = context.results["excel_publication_check"]
        # On appelle check avec bundle.
        check(bundle)
        # On récupère les trois repères du même lot : son identifiant, le chemin du tableau regroupé
        # et l’empreinte attendue de ses octets.
        publication_id, path, sha = _reference_info(root, bundle["publication"])
        # On compare l’empreinte des octets actuels à celle du lot attendu ; une différence doit
        # bloquer le mélange de versions.
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            # On interrompt cette branche avec ValueError : 'Reference modifiee avant fixation.'.
            raise ValueError("Reference modifiee avant fixation.")
        # On rattache le contexte à ce lot pour empêcher un changement silencieux d’identifiant en
        # cours de traitement.
        context.pin_ids(excel_publication_id=publication_id)
        # On regroupe ces repères dans un objet non modifiable ; cela ne bloque pas le fichier sur
        # disque, d’où les vérifications d’empreinte ultérieures.
        return PinnedExcel(publication_id, path, sha)

    # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return [
        ("excel_ingestion", ingestion),
        ("excel_publication_check", publication_check),
        ("excel_reference_pin", reference_pin),
    ]


# On vérifie que les étapes utilisent toujours le lot Excel retenu pour cette exécution.
def assert_excel_snapshot(context, *, ensure_current=None):
    """Garde a appeler avant les futurs consommateurs ; aucun recalcul d ingestion."""
    # On garde dans pinned le champ 'excel_reference_pin' de context.results, ou None si la clé est
    # absente.
    pinned = context.results.get("excel_reference_pin")
    # On garde dans bundle le champ 'excel_publication_check' de context.results, ou None si la clé est
    # absente.
    bundle = context.results.get("excel_publication_check")
    # Cette branche traite le cas où le type reçu ne correspond pas à PinnedExcel ou le lot préparé
    # vaut None.
    if not isinstance(pinned, PinnedExcel) or bundle is None:
        # On interrompt cette branche avec ValueError : 'Publication Excel non figee dans cette
        # execution.'.
        raise ValueError("Publication Excel non figee dans cette execution.")
    # On retient pour check la première valeur évaluée comme vraie dans cette chaîne de replis ; une
    # valeur vide fera donc passer à la suivante.
    check = ensure_current or (lambda b: _current(context.root, b))
    # On appelle check avec bundle.
    check(bundle)
    # On répartit les valeurs renvoyées par _reference_info entre (publication_id, path, sha) ; leur
    # ordre doit correspondre à celui prévu par cet appel.
    publication_id, path, sha = _reference_info(context.root, bundle["publication"])
    # On vérifie ce cas avant la suite : (publication_id, path, sha) diffère de (pinned.publication_id,
    # pinned.reference_path, pinned.reference_sha256).
    if (publication_id, path, sha) != (
        pinned.publication_id,
        pinned.reference_path,
        pinned.reference_sha256,
    ):
        # On interrompt cette branche avec ValueError : 'Metadonnees de publication differentes de la
        # reference figee.'.
        raise ValueError(
            "Metadonnees de publication differentes de la reference figee."
        )
    # On vérifie ce cas avant la suite : l’identifiant du lot Excel dans context.linked_ids() diffère
    # de pinned.publication_id.
    if context.linked_ids()["excel_publication_id"] != pinned.publication_id:
        # On interrompt cette branche avec ValueError : 'Identifiant global incompatible avec la
        # publication figee.'.
        raise ValueError("Identifiant global incompatible avec la publication figee.")
    # On compare l’empreinte des octets actuels à celle du lot attendu ; une différence doit bloquer
    # le mélange de versions.
    if hashlib.sha256(path.read_bytes()).hexdigest() != pinned.reference_sha256:
        # On interrompt cette branche avec ValueError : 'Reference modifiee apres fixation ;
        # consommateur bloque.'.
        raise ValueError("Reference modifiee apres fixation ; consommateur bloque.")
    # On remet pinned à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return pinned
