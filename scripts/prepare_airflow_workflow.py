# Lecture du fichier — Préparation des chemins de montage et de l’identité de partage du workflow.
#

"""Prepare les sources des montages Docker ; ne lit pas le NAS et ne copie aucun mot de passe."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path, PureWindowsPath, PurePosixPath depuis pathlib, pour les appels de ce
# fichier.
from pathlib import Path, PureWindowsPath, PurePosixPath
# On rend disponibles UUID, uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import UUID, uuid4


class PreparationError(ValueError):
    # Cette classe marque un type d’erreur distinct, sans ajouter de comportement à sa classe parente.
    pass


# On centralise un contrôle bloquant : si la condition est fausse, le code associé explique le refus.
def require(ok, code):
    # On prévoit le cas où ok est évalué comme faux, par exemple une valeur vide selon son type.
    if not ok:
        # On interrompt cette branche avec PreparationError.
        raise PreparationError(code)


# On vérifie lexicalement une source de montage absolue, sans tenter d’y accéder.
def source_value(value):
    # On exige ici que la valeur reçue est du type str et le contrôle bool(value.strip()) est positif
    # et la condition any((c in value for c in "\x00\r\n'")) n’est pas remplie. Si ce n’est pas le cas,
    # le message associé bloque la suite.
    require(
        isinstance(value, str)
        # On exige aussi que le contrôle bool(value.strip()) est positif.
        and bool(value.strip())
        # On exige aussi que la condition any((c in value for c in "\x00\r\n'")) n’est pas remplie.
        and not any(c in value for c in "\x00\r\n'"),
        "NAS_SOURCE_VALUE_INVALID",
    )
    # On exige ici que PurePosixPath(value) est absolu ou PureWindowsPath(value) est absolu. Si ce
    # n’est pas le cas, le message associé bloque la suite.
    require(
        PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute(),
        "NAS_SOURCE_NOT_ABSOLUTE",
    )
    # On renvoie l’une des deux valeurs selon le test indiqué ; ce choix termine la fonction pour ce
    # cas.
    return (
        PureWindowsPath(value).as_posix()
        if PureWindowsPath(value).is_absolute()
        else value
    )


# On prépare les éléments du lot ou de la configuration définis dans ce module ; cela ne constitue
# pas à soi seul une exécution métier réussie.
def prepare(root):
    # On rend disponibles dotenv_values depuis dotenv, pour les appels de ce fichier.
    from dotenv import dotenv_values

    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # On exige ici que la condition (root / 'state/workflow_execution/workflow.lock').exists() n’est
    # pas remplie. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        not (root / "state/workflow_execution/workflow.lock").exists(),
        "WORKFLOW_LOCK_PRESENT",
    )
    # On exige ici que root / '.env' désigne un fichier. Si ce n’est pas le cas, le message associé
    # bloque la suite.
    require((root / ".env").is_file(), "LOCAL_ENV_MISSING")
    # On garde dans values les réglages lus sans modifier automatiquement l’environnement global.
    values = dotenv_values(root / ".env", encoding="utf-8-sig", interpolate=False)
    # On construit sources comme une liste à partir de source_value(values.get(k)), pour chaque k de
    # ('NAS_BRUT_ROOT', 'NAS_PROCESSING_ROOT').
    sources = [
        source_value(values.get(k)) for k in ("NAS_BRUT_ROOT", "NAS_PROCESSING_ROOT")
    ]
    # On exige ici que sources[0] diffère de sources[1]. Si ce n’est pas le cas, le message associé
    # bloque la suite.
    require(sources[0] != sources[1], "NAS_SOURCES_MUST_BE_DISTINCT")
    # On parcourt les champs à l’origine du constat ; s désigne l’élément courant à chaque passage dans
    # la boucle.
    for s in sources:
        # Comparaison lexicale uniquement ; aucune resolution ou consultation du NAS.
        candidate = PureWindowsPath(s) if PureWindowsPath(s).is_absolute() else Path(s)
        # On choisit la valeur de base selon ce test : candidate est du type PureWindowsPath. Les deux
        # résultats possibles restent définis explicitement ici.
        base = (
            PureWindowsPath(str(root))
            if isinstance(candidate, PureWindowsPath)
            else root
        )
        # Ce contrôle porte sur la destination résolue ; un chemin textuellement situé sous le
        # projet pourrait encore pointer ailleurs par un lien symbolique.
        require(
            not candidate.is_relative_to(base) and not base.is_relative_to(candidate),
            "NAS_PROJECT_OVERLAP",
        )
    # On construit marker en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    marker = root / "state/workflow_execution/airflow_share_identity.json"
    # Cette branche traite le cas où marker existe.
    if marker.exists():
        # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite,
        # car un JSON lisible n’est pas forcément un lot valide.
        identity = json.loads(marker.read_text(encoding="utf-8"))
        # On exige ici que set(identity) correspond à {'share_id'} et str(UUID(identity['share_id']))
        # correspond à identity['share_id']. Si ce n’est pas le cas, le message associé bloque la
        # suite.
        require(
            set(identity) == {"share_id"}
            # On exige aussi que str(UUID(identity['share_id'])) correspond à identity['share_id'].
            and str(UUID(identity["share_id"])) == identity["share_id"],
            "SHARE_MARKER_INVALID",
        )
    else:
        # On regroupe dans identity ces champs nommés ; on pourra les retrouver par leur clé plutôt que
        # par leur position.
        identity = {"share_id": str(uuid4())}
    # Compose monte une racine unique en lecture seule sous /opt/nas.
    # Vérification lexicale : ne pas résoudre ni parcourir les chemins du NAS.
    paths = [PureWindowsPath(s) if PureWindowsPath(s).is_absolute() else PurePosixPath(s) for s in sources]
    # On exige ici que paths[0].name correspond au texte 'brute_v2025' et paths[1].name correspond à
    # le texte 'data_processing_2025'. Si ce n’est pas le cas, le message associé bloque la suite.
    require(paths[0].name == "brute_v2025" and paths[1].name == "data_processing_2025", "NAS_SUBDIRECTORY_NAMES_INVALID")
    # On exige ici que paths[0].parent correspond à paths[1].parent. Si ce n’est pas le cas, le message
    # associé bloque la suite.
    require(paths[0].parent == paths[1].parent, "NAS_COMMON_PARENT_REQUIRED")
    # On garde dans nas_source la valeur renvoyée par source_value.
    nas_source = source_value(paths[0].parent.as_posix())
    # On utilise ce texte pour content ; il ne dépend pas d’une valeur récupérée ailleurs à cet
    # endroit.
    content = "# Local : chemin du montage ; aucun mot de passe. Ne pas publier.\n"
    # On ajoute "PROJECT12_WORKFLOW_NAS_SOURCE='" + nas_source + "'\n" à content et on conserve ce
    # nouvel état pour la suite.
    content += "PROJECT12_WORKFLOW_NAS_SOURCE='" + nas_source + "'\n"
    # On ajoute "PROJECT12_WORKFLOW_SHARE_ID='" + identity['share_id'] + "'\n" à content et on conserve
    # ce nouvel état pour la suite.
    content += "PROJECT12_WORKFLOW_SHARE_ID='" + identity["share_id"] + "'\n"
    # On construit target en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    target = root / ".env.airflow.workflow.local"
    # Cette branche traite le cas où la destination existe.
    if target.exists():
        # On exige ici que target.read_text(encoding='utf-8') correspond à content. Si ce n’est pas le
        # cas, le message associé bloque la suite.
        require(
            target.read_text(encoding="utf-8") == content,
            "EXISTING_WORKFLOW_ENV_DIFFERENT",
        )
    # Exclure avant toute creation de ce fichier local.
    ignore = root / ".gitignore"
    # On choisit la valeur de previous selon ce test : ignore existe. Les deux résultats possibles
    # restent définis explicitement ici.
    previous = ignore.read_text(encoding="utf-8-sig") if ignore.exists() else ""
    # On vérifie ce cas avant la suite : le texte '.env.airflow.workflow.local' ne figure pas dans
    # previous.splitlines().
    if ".env.airflow.workflow.local" not in previous.splitlines():
        # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la sortie,
        # y compris après une erreur.
        with ignore.open("a", encoding="utf-8", newline="\n") as f:
            # On écrit ('\n' if previous and (not previous.endswith('\n')) else '') +
            # '.env.airflow.workflow.loc… dans f ; le mode d’ouverture du flux détermine s’il s’agit
            # d’un ajout ou d’un remplacement.
            f.write(
                ("\n" if previous and not previous.endswith("\n") else "")
                + ".env.airflow.workflow.local\n"
            )
    # On parcourt ('state/workflow_execution', 'logs/airflow_workflow', 'data/01_incoming/s… ; relative
    # désigne l’élément courant à chaque passage dans la boucle.
    for relative in (
        "state/workflow_execution",
        "logs/airflow_workflow",
        "data/01_incoming/suivi_acquisitions",
        "data/02_raw_archive",
        "data/03_normalized",
        "data/04_rejected",
    ):
        # On calcule ce quotient pour construire p.
        p = root / relative
        # On exige ici que la condition p.is_symlink() n’est pas remplie et la condition hasattr(p,
        # 'is_junction') and p.is_junction() n’est pas remplie. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(
            not p.is_symlink() and not (hasattr(p, "is_junction") and p.is_junction()),
            "LOCAL_PATH_REDIRECTED",
        )
        # On exige ici que p.resolve() reste sous la racine locale du projet. Si ce n’est pas le cas,
        # le message associé bloque la suite.
        require(p.resolve().is_relative_to(root), "LOCAL_PATH_OUTSIDE_PROJECT")
        # On prépare le dossier local nécessaire à cette sortie ; créer le dossier ne produit pas
        # encore le fichier qu’il contiendra.
        p.mkdir(parents=True, exist_ok=True)
    # Cette branche traite le cas où la condition marker.exists() n’est pas remplie.
    if not marker.exists():
        # On ouvre le fichier en création exclusive : s’il existe déjà, on s’arrête au lieu de
        # l’écraser. Le bloc ferme le fichier à la sortie.
        with marker.open("x", encoding="utf-8") as f:
            # On appelle json.dump avec identity.
            json.dump(identity, f)
    # Cette branche traite le cas où la condition target.exists() n’est pas remplie.
    if not target.exists():
        # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la sortie,
        # y compris après une erreur.
        with target.open("x", encoding="utf-8", newline="\n") as f:
            # On écrit content dans f ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout ou
            # d’un remplacement.
            f.write(content)
    # On remet les éléments d’identité du lot à l’appelant ; les étapes suivantes de cette fonction ne
    # sont plus parcourues.
    return identity


# On exige un reçu de diagnostic récent et lié à la même identité de partage.
def check_diagnostic(root):
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # On décodu texte JSON en objets Python ; les contrôles de structure viennent ensuite, car un
    # JSON lisible n’est pas forcément un lot valide.
    identity = json.loads(
        (root / "state/workflow_execution/airflow_share_identity.json").read_text(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8"
        )
    )
    # On garde dans paths une liste matérialisée à partir de (root /
    # 'logs/airflow_workflow').glob('diagnostic_*.json').
    paths = list((root / "logs/airflow_workflow").glob("diagnostic_*.json"))
    # On exige ici que le contrôle bool(paths) est positif. Si ce n’est pas le cas, le message associé
    # bloque la suite.
    require(bool(paths), "DIAGNOSTIC_RECEIPT_MISSING_ON_HOST")
    # On garde dans path la plus grande valeur parmi paths.
    path = max(paths, key=lambda p: p.stat().st_mtime_ns)
    # On garde dans receipt les objets Python décodés depuis le JSON fourni.
    receipt = json.loads(path.read_text(encoding="utf-8"))
    # On exige ici que receipt.get('kind') correspond au texte 'diagnostic' et receipt.get('status')
    # correspond au texte 'success' et receipt.get('share_id') correspond à identity['share_id']. Si
    # ce n’est pas le cas, le message associé bloque la suite.
    require(
        receipt.get("kind") == "diagnostic"
        # On exige aussi que receipt.get('status') correspond au texte 'success'.
        and receipt.get("status") == "success"
        # On exige aussi que receipt.get('share_id') correspond à identity['share_id'].
        and receipt.get("share_id") == identity["share_id"],
        "DIAGNOSTIC_RECEIPT_MISMATCH",
    )
    # On interprète la date ISO reçue ; les vérifications de fuseau et de cohérence restent
    # nécessaires après cette conversion.
    when = datetime.fromisoformat(receipt["occurred_at"])
    # On exige ici que when.utcoffset() est renseigné (différent de None) et le test 0 <=
    # (datetime.now(timezone.utc) - when).total_seconds() <= 900 est satisfait. Si ce n’est pas le cas,
    # le message associé bloque la suite.
    require(
        when.utcoffset() is not None
        # On exige aussi que le test 0 <= (datetime.now(timezone.utc) - when).total_seconds() <= 900
        # est satisfait.
        and 0 <= (datetime.now(timezone.utc) - when).total_seconds() <= 900,
        "DIAGNOSTIC_RECEIPT_TOO_OLD",
    )
    # On remet path.name à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return path.name


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On appelle parser.add_argument avec '--check-diagnostic'.
    parser.add_argument("--check-diagnostic", action="store_true")
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On lit les paramètres de raccordement du workflow : les chemins et le mode doivent être
    # contrôlés avant d’écrire la configuration.
    args = parser.parse_args(argv)
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # Cette branche traite le cas où le test args.check_diagnostic est satisfait.
        if args.check_diagnostic:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Diagnostic Docker retrouve depuis Windows : "
                + check_diagnostic(args.project_root)
            )
            # On affiche ce texte explicite dans la sortie du programme.
            print(
                "Identite partagee concordante ; recu recent ; aucun traitement lance."
            )
        else:
            # On appelle prepare avec args.project_root.
            prepare(args.project_root)
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Fichier .env.airflow.workflow.local prepare ; identite de partage conservee."
            )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Sources NAS lues dans la configuration, valeurs non affichees ; accessibilite Docker NON testee."
            )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Aucun secret copie, aucun acces NAS, aucune connexion PostgreSQL, aucun lancement Docker."
            )
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as e:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "PREPARATION NON CONFIRMEE : "
            + (str(e) if isinstance(e, PreparationError) else type(e).__name__)
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
