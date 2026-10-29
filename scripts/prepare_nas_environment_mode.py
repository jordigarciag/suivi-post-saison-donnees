# Lecture du fichier — Adaptation encadrée du mode de configuration de l’extracteur NAS.
# On vérifie la transformation prévue avant de l’appliquer. Ce script peut modifier un fichier local
# ; on ne le présente pas comme une simple lecture.
#

"""Adaptation ciblee de l'extracteur ; aucun NAS, PostgreSQL ou lancement Docker."""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On importe ast. On analyse la structure du code Python sans exécuter le texte analysé.
import ast
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On fixe RELATIVE à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
RELATIVE = "src/suivi_traitements_post_saison/extraction/nas_live_evidence_extractor.py"
# On fixe HELPER à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
HELPER = "src/suivi_traitements_post_saison/extraction/workflow_nas_environment.py"
# On fixe OLD à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
OLD = '    load_dotenv(PROJECT_ROOT / ".env")'
# On fixe NEW à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
NEW = "    configure_nas_environment(PROJECT_ROOT, local_loader=load_dotenv)"
# On fixe ANCHOR à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
ANCHOR = "from dotenv import load_dotenv"
# On fixe IMPORT à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même réglage.
IMPORT = """\n\n# Choix explicite local/environnement, sans casser l'execution directe.
if __package__ in {None, ""}:
    from workflow_nas_environment import configure_nas_environment
else:
    from .workflow_nas_environment import configure_nas_environment"""


def transform(source):
    # On analyse la structure du code source sans l’exécuter ; cela permet de contrôler ses appels
    # ou imports sans lancer le traitement décrit.
    ast.parse(source)
    # On vérifie ce cas avant la suite : NEW appartient à la source.
    if NEW in source:
        # Cette branche traite le cas où source.count(NEW) correspond à 1 et IMPORT appartient à la
        # source et OLD ne figure pas dans la source.
        if source.count(NEW) == 1 and IMPORT in source and OLD not in source:
            # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return source, False
        # On interrompt cette branche avec ValueError : 'Adaptation partielle ou contradictoire :
        # aucune modification.'.
        raise ValueError(
            "Adaptation partielle ou contradictoire : aucune modification."
        )
    # Cette branche traite le cas où source.count(OLD) diffère de 1 ou source.count(ANCHOR) diffère de
    # 1.
    if source.count(OLD) != 1 or source.count(ANCHOR) != 1:
        # On interrompt cette branche avec ValueError : 'Version de l extracteur non reconnue : aucune
        # modification.'.
        raise ValueError("Version de l extracteur non reconnue : aucune modification.")
    # On garde dans updated le résultat du remplacement demandé sur source.replace(ANCHOR, ANCHOR +
    # IMPORT, 1).
    updated = source.replace(ANCHOR, ANCHOR + IMPORT, 1).replace(OLD, NEW, 1)
    # On appelle ast.parse avec updated.
    ast.parse(updated)
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return updated, True


def apply(root):
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où la condition root.is_dir() n’est pas remplie ou str(root) commence
    # par ('\\\\', '//').
    if not root.is_dir() or str(root).startswith(("\\\\", "//")):
        # On interrompt cette branche avec ValueError : 'Racine locale requise.'.
        raise ValueError("Racine locale requise.")
    # On distribue ces valeurs entre source_path, helper, dans l’ordre de l’affectation. Chaque nom
    # reçoit son propre élément.
    source_path, helper = root / RELATIVE, root / HELPER
    # On parcourt (source_path, helper) ; path désigne l’élément courant à chaque passage dans la
    # boucle.
    for path in (source_path, helper):
        # La sauvegarde et le fichier à adapter doivent rester dans le projet avant toute
        # modification.
        if not path.is_file() or not path.resolve().is_relative_to(root):
            # On interrompt cette branche avec ValueError : 'Source ou helper absent ou redirige hors
            # du projet.'.
            raise ValueError("Source ou helper absent ou redirige hors du projet.")
    # On garde dans raw les octets lus depuis source_path, avant toute conversion en texte. Les
    # contrôles de contenu pourront ainsi repartir de cette lecture.
    raw = source_path.read_bytes()
    # Conserver BOM et fins de ligne, sans reformater les regles metier.
    bom = raw.startswith(b"\xef\xbb\xbf")
    # On garde dans source le texte décodé depuis les octets de raw.
    source = raw.decode("utf-8-sig")
    # On choisit la valeur de newline selon ce test : le texte '\r\n' appartient à la source. Les deux
    # résultats possibles restent définis explicitement ici.
    newline = "\r\n" if "\r\n" in source else "\n"
    # On répartit les valeurs renvoyées par transform entre (updated, changed) ; leur ordre doit
    # correspondre à celui prévu par cet appel.
    updated, changed = transform(source.replace("\r\n", "\n"))
    # On prévoit le cas où changed est évalué comme faux, par exemple une valeur vide selon son type.
    if not changed:
        # On renvoie None pour ce cas ; il n’y a pas de valeur exploitable à fournir à l’appelant.
        return None
    # On construit backup_dir en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    backup_dir = root / "logs/nas_environment_patch" / uuid4().hex
    # La sauvegarde et le fichier à adapter doivent rester dans le projet avant toute modification.
    if not backup_dir.resolve().is_relative_to(root):
        # On interrompt cette branche avec ValueError : 'Sauvegarde hors du projet local.'.
        raise ValueError("Sauvegarde hors du projet local.")
    # On crée ce dossier en refusant un emplacement déjà existant ; cela évite de réutiliser
    # silencieusement les sorties d’un ancien essai.
    backup_dir.mkdir(parents=True, exist_ok=False)
    # On écrit les octets préparés dans le fichier ciblé ; ce mode remplace son contenu s’il existe
    # déjà.
    (backup_dir / "nas_live_evidence_extractor.before.py").write_bytes(raw)
    # On écrit le texte préparé avec l’encodage indiqué ; cette opération remplace le contenu de ce
    # fichier.
    (backup_dir / "before.sha256").write_text(
        # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
        # décodé selon un réglage implicite du poste.
        hashlib.sha256(raw).hexdigest(), encoding="ascii"
    )
    # On garde dans payload les octets de updated.replace('\n', newline) obtenus avec l’encodage
    # indiqué.
    payload = updated.replace("\n", newline).encode("utf-8")
    # Cette branche traite le cas où bom est évalué comme vrai.
    if bom:
        # On assemble ces deux éléments pour construire payload.
        payload = b"\xef\xbb\xbf" + payload
    # Pas de remplacement si le fichier a change pendant la preparation.
    if source_path.read_bytes() != raw:
        # On interrompt cette branche avec ValueError : 'Source modifiee pendant la preparation :
        # adaptation abandonnee.'.
        raise ValueError(
            "Source modifiee pendant la preparation : adaptation abandonnee."
        )
    # On garde dans temporary la valeur renvoyée par source_path.with_name.
    temporary = source_path.with_name(
        "." + source_path.name + "." + uuid4().hex + ".tmp"
    )
    # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
    try:
        # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la sortie,
        # y compris après une erreur.
        with temporary.open("xb") as handle:
            # On écrit payload dans handle ; le mode d’ouverture du flux détermine s’il s’agit d’un
            # ajout ou d’un remplacement.
            handle.write(payload)
            # On vidu tampon d’écriture de handle vers sa destination ; cela ne remplace pas, à lui
            # seul, une synchronisation durable du fichier.
            handle.flush()
            # On demande la synchronisation du fichier après son écriture ; cela ne garantit pas à
            # lui seul la reprise de tout le workflow.
            os.fsync(handle.fileno())
        # On appelle os.chmod avec temporary.
        os.chmod(temporary, source_path.stat().st_mode & 0o777)
        # On vérifie ce cas avant la suite : source_path.read_bytes() diffère de raw.
        if source_path.read_bytes() != raw:
            # On interrompt cette branche avec ValueError : 'Source modifiee pendant la preparation :
            # adaptation abandonnee.'.
            raise ValueError(
                "Source modifiee pendant la preparation : adaptation abandonnee."
            )
        # On remplace la destination avec le fichier temporaire préparé, pour éviter de publier
        # directement un contenu en cours d’écriture.
        temporary.replace(source_path)
    finally:
        # Cette branche traite le cas où temporary existe.
        if temporary.exists():
            # On supprime ce fichier local selon le chemin préparé ; on ne nettoie pas arbitrairement
            # d’autres fichiers.
            temporary.unlink()
    # On fournit à l’appelant l’écriture de backup_dir.relative_to(root) avec des / comme séparateurs.
    return backup_dir.relative_to(root).as_posix()


def main(argv=None):
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On récupère les options de transformation du mode NAS ; la suite contrôle si une modification
    # du code est autorisée.
    args = parser.parse_args(argv)
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On garde dans backup la valeur renvoyée par apply.
        backup = apply(args.project_root)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Extracteur adapte ; sauvegarde locale : " + backup
            if backup
            else "Extracteur deja adapte : aucune reecriture."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Mode local conserve. Mode environment : aucun chargement du .env par cet appel."
        )
        # On affiche ce texte explicite dans la sortie du programme.
        print("Aucun acces NAS, PostgreSQL ou Docker. Aucun secret affiche.")
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "ADAPTATION NON CONFIRMEE : arreter ; aucune execution du pipeline autorisee."
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
