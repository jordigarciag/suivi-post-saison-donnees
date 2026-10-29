# Lecture du fichier — Préparation de la configuration de montage propre à WSL.
# On conserve l’identité de partage existante et on renseigne une racine NAS unique. Ce fichier ne
# monte pas le partage et ne répare pas Docker.
#

"""Prepare un env Compose WSL distinct : aucune lecture NAS, aucun secret copie."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path, PurePosixPath depuis pathlib, pour les appels de ce fichier.
from pathlib import Path, PurePosixPath
# On rend disponibles UUID depuis uuid, pour les appels de ce fichier.
from uuid import UUID

# On fixe TARGET à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
TARGET = ".env.airflow.workflow.wsl.local"


class WslPreparationError(ValueError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(ok, code):
    # On prévoit le cas où ok est évalué comme faux, par exemple une valeur vide selon son type.
    if not ok:
        # On interrompt cette branche avec WslPreparationError.
        raise WslPreparationError(code)


# On construit un chemin et on vérifie qu’il reste dans le périmètre local autorisé par ce module.
def local_path(root, relative):
    # On garde la racine locale du projet sous le nom path ; cette affectation ne copie pas à elle
    # seule un objet mutable.
    path = root
    # On parcourt Path(relative).parts ; part désigne l’élément courant à chaque passage dans la
    # boucle.
    for part in Path(relative).parts:
        # On calcule ce quotient pour construire path.
        path = path / part
        # On exige ici que la condition path.is_symlink() n’est pas remplie et la condition
        # hasattr(path, 'is_junction') and path.is_junction() n’est pas remplie. Si ce n’est pas le
        # cas, le message associé bloque la suite.
        require(
            not path.is_symlink()
            # On exige aussi que la condition hasattr(path, 'is_junction') and path.is_junction() n’est
            # pas remplie.
            and not (hasattr(path, "is_junction") and path.is_junction()),
            "LOCAL_PATH_REDIRECTED",
        )
    # Ce contrôle porte sur la destination résolue ; un chemin textuellement situé sous le projet
    # pourrait encore pointer ailleurs par un lien symbolique.
    require(path.resolve().is_relative_to(root), "LOCAL_PATH_OUTSIDE_PROJECT")
    # On remet le chemin de travail à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return path


# On écrit la configuration locale WSL après vérification des éléments locaux requis.
def prepare_wsl(root, nas_source="/mnt/demo-data"):
    # On exige ici que nas_source est du type str et PurePosixPath(nas_source) est absolu et la
    # condition any((c in nas_source for c in "\x00\r\n'")) n’est pas remplie. Si ce n’est pas le cas,
    # le message associé bloque la suite.
    require(isinstance(nas_source, str) and PurePosixPath(nas_source).is_absolute() and not any(c in nas_source for c in "\x00\r\n'"), "NAS_SOURCE_VALUE_INVALID")
    # On garde dans root un objet chemin local ; sa construction seule ne prouve pas que le fichier
    # existe.
    root = Path(root)
    # On exige ici que la condition str(root).startswith(('\\\\', '//')) n’est pas remplie. Si ce n’est
    # pas le cas, le message associé bloque la suite.
    require(not str(root).startswith(("\\\\", "//")), "PROJECT_MUST_BE_LOCAL")
    # On exige ici que la condition root.is_symlink() n’est pas remplie et la condition hasattr(root,
    # 'is_junction') and root.is_junction() n’est pas remplie. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(
        not root.is_symlink()
        # On exige aussi que la condition hasattr(root, 'is_junction') and root.is_junction() n’est pas
        # remplie.
        and not (hasattr(root, "is_junction") and root.is_junction()),
        "LOCAL_PATH_REDIRECTED",
    )
    # On garde dans root le chemin absolu résolu de root, en tenant compte des liens symboliques.
    root = root.resolve()
    # On exige ici que la racine locale du projet désigne un dossier. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(root.is_dir(), "PROJECT_MISSING")
    # Signature du lot deja installe : ne pas preparer dans un dossier arbitraire.
    for relative in (
        "scripts/prepare_airflow_workflow.py",
        "scripts/run_airflow_pilote_workflow.py",
        "config/tracking_files.yml",
        "docker/docker-compose.airflow-workflow.yml",
    ):
        # On exige ici que local_path(root, relative) désigne un fichier. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(local_path(root, relative).is_file(), "EXISTING_WORKFLOW_FILE_MISSING")
    # On garde dans lock le chemin local après les contrôles de périmètre du module.
    lock = local_path(root, "state/workflow_execution/workflow.lock")
    # On exige ici que la condition lock.exists() n’est pas remplie. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(not lock.exists(), "WORKFLOW_LOCK_PRESENT")
    # On garde dans marker le chemin local après les contrôles de périmètre du module.
    marker = local_path(root, "state/workflow_execution/airflow_share_identity.json")
    # On exige ici que marker désigne un fichier. Si ce n’est pas le cas, le message associé bloque la
    # suite.
    require(marker.is_file(), "EXISTING_SHARE_MARKER_REQUIRED")
    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    identity = json.loads(marker.read_text(encoding="utf-8"))
    # On exige ici que les éléments d’identité du lot est du type dict et set(identity) correspond à
    # {'share_id'}. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        isinstance(identity, dict) and set(identity) == {"share_id"},
        "SHARE_MARKER_INVALID",
    )
    # On tente ce bloc et on traite séparément les erreurs prévues : (TypeError, ValueError,
    # AttributeError).
    try:
        # On garde dans valid le résultat de cette comparaison : str(UUID(identity['share_id']))
        # correspond à identity['share_id'].
        valid = str(UUID(identity["share_id"])) == identity["share_id"]
    except (TypeError, ValueError, AttributeError):
        # On initialise valid à False ; les branches suivantes pourront modifier cet état.
        valid = False
    # On exige ici que valid est évalué comme vrai. Si ce n’est pas le cas, le message associé bloque
    # la suite.
    require(valid, "SHARE_MARKER_INVALID")

    # On parcourt ('src', 'scripts', 'data', 'state', 'logs', 'data/01_incoming/suivi_acqui… ; relative
    # désigne l’élément courant à chaque passage dans la boucle.
    for relative in (
        "src",
        "scripts",
        "data",
        "state",
        "logs",
        "data/01_incoming/suivi_acquisitions",
        "data/02_raw_archive",
        "data/03_normalized",
        "data/04_rejected",
        "logs/airflow_workflow",
    ):
        # On exige ici que local_path(root, relative) désigne un dossier. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(local_path(root, relative).is_dir(), "EXISTING_LOCAL_DIRECTORY_MISSING")

    # On utilise ce texte pour content ; il ne dépend pas d’une valeur récupérée ailleurs à cet
    # endroit.
    content = (
        "# Local WSL : sources de montage uniquement ; aucun secret. Ne pas publier.\n"
    )
    # Racine unique attendue par docker-compose.airflow-workflow.yml.
    content += "PROJECT12_WORKFLOW_NAS_SOURCE='" + nas_source + "'\n"
    # On ajoute "PROJECT12_WORKFLOW_SHARE_ID='" + identity['share_id'] + "'\n" à content et on conserve
    # ce nouvel état pour la suite.
    content += "PROJECT12_WORKFLOW_SHARE_ID='" + identity["share_id"] + "'\n"
    # On garde dans target le chemin local après les contrôles de périmètre du module.
    target = local_path(root, TARGET)
    # Cette branche traite le cas où la destination existe.
    if target.exists():
        # On exige ici que la destination désigne un fichier et target.read_text(encoding='utf-8')
        # correspond à content. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            target.is_file() and target.read_text(encoding="utf-8") == content,
            "EXISTING_WSL_ENV_DIFFERENT",
        )

    # Ajouter l'exclusion avant de creer le fichier de configuration local.
    ignore = local_path(root, ".gitignore")
    # On choisit la valeur de previous selon ce test : ignore existe. Les deux résultats possibles
    # restent définis explicitement ici.
    previous = ignore.read_text(encoding="utf-8-sig") if ignore.exists() else ""
    # On vérifie ce cas avant la suite : TARGET ne figure pas dans previous.splitlines().
    if TARGET not in previous.splitlines():
        # On ouvre en ajout pour conserver les lignes précédentes du journal ; ce bloc ne remet pas
        # le fichier à zéro.
        with ignore.open("a", encoding="utf-8", newline="\n") as stream:
            # On écrit ('\n' if previous and (not previous.endswith('\n')) else '') + TARGET + '\n'
            # dans stream ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout ou d’un
            # remplacement.
            stream.write(
                ("\n" if previous and not previous.endswith("\n") else "")
                + TARGET
                + "\n"
            )
    # Cette branche traite le cas où la condition target.exists() n’est pas remplie.
    if not target.exists():
        # On ouvre le fichier en création exclusive : s’il existe déjà, on s’arrête au lieu de
        # l’écraser. Le bloc ferme le fichier à la sortie.
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            # On écrit content dans stream ; le mode d’ouverture du flux détermine s’il s’agit d’un
            # ajout ou d’un remplacement.
            stream.write(content)
    # On remet identity['share_id'] à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return identity["share_id"]


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # Option --nas-source : Racine NAS montée sous WSL, non consultée par cette préparation. Sa
    # déclaration ne déclenche pas l’action.
    parser.add_argument("--nas-source", default="/mnt/demo-data", help="Racine NAS montée sous WSL, non consultée par cette préparation.")
    # On récupère les chemins WSL à préparer ; ils ne sont pas interchangeables avec les chemins
    # Windows du poste.
    args = parser.parse_args(argv)
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On appelle prepare_wsl avec args.project_root.
        prepare_wsl(args.project_root, args.nas_source)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Fichier .env.airflow.workflow.wsl.local prepare ; identite existante conservee."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Configuration Windows, .env metier et trois fichiers Airflow fournis : inchanges."
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print("Exclusion Git ajoutee si necessaire. Aucun secret lu ou copie.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Aucun acces NAS, PostgreSQL ou Docker. Montage DrvFS a verifier dans Ubuntu."
        )
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as exc:
        # On choisit la valeur de code selon ce test : exc est du type WslPreparationError. Les deux
        # résultats possibles restent définis explicitement ici.
        code = str(exc) if isinstance(exc, WslPreparationError) else type(exc).__name__
        # On affiche 'PREPARATION WSL NON CONFIRMEE : ' + code dans la sortie du programme.
        print("PREPARATION WSL NON CONFIRMEE : " + code)
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
