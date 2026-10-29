# Lecture du fichier — Répétition locale du workflow avec des dépendances de démonstration.
# On répète le scénario avec des accessoires de test, pas les installations réelles. Une répétition
# réussie ne valide donc pas la connexion au NAS ou à PostgreSQL.
#

"""Entree manuelle : REPETITION SYNTHETIQUE UNIQUEMENT. Aucun mode metier --run.
Les huit etapes utilisent des fixtures, les controles de fichiers reels et des
chargeurs/destinataires de journal simules. Aucune connexion SQL ou lecture NAS.
"""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe shutil. On réalise les copies et nettoyages de fichiers explicitement prévus.
import shutil
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On rend disponibles WorkflowDependencies, run_shared_rehearsal, validate_selection depuis
# workflow_assembly, pour les appels de ce fichier.
from workflow_assembly import (
    WorkflowDependencies,
    run_shared_rehearsal,
    validate_selection,
)
# On rend disponibles _project_module depuis workflow_excel_adapter, pour les appels de ce fichier.
from workflow_excel_adapter import _project_module
# On rend disponibles read_events depuis workflow_runtime, pour les appels de ce fichier.
from workflow_runtime import read_events


def local_project(root):
    # On fixe le point de départ local sous forme absolue avant de construire les chemins de ce
    # traitement.
    root = Path(root).resolve()
    # Cette branche traite le cas où la condition root.is_dir() n’est pas remplie ou str(root) commence
    # par ('\\\\', '//').
    if not root.is_dir() or str(root).startswith(("\\\\", "//")):
        # On interrompt cette branche avec ValueError : 'Projet local existant requis ; chemins reseau
        # refuses.'.
        raise ValueError("Projet local existant requis ; chemins reseau refuses.")
    # On parcourt ('scripts/workflow_assembly.py', 'scripts/synthetic_import_fixtures.py',… ; relative
    # désigne l’élément courant à chaque passage dans la boucle.
    for relative in (
        "scripts/workflow_assembly.py",
        "scripts/synthetic_import_fixtures.py",
        "tests/unit/test_excel_publication_check.py",
        "tests/unit/test_nas_reconciliation_check.py",
    ):
        # On calcule ce quotient pour construire path.
        path = root / relative
        # Les fichiers nécessaires à la répétition doivent provenir de cette copie locale.
        if not path.is_file() or not path.resolve().is_relative_to(root):
            # On interrompt cette branche avec ValueError : 'Source de repetition absente ou hors du
            # projet.'.
            raise ValueError("Source de repetition absente ou hors du projet.")
    # On remet la racine locale du projet à l’appelant ; les étapes suivantes de cette fonction ne sont
    # plus parcourues.
    return root


# On fournit des dépendances fictives pour répéter les étapes sans les installations métier.
def rehearsal_dependencies(project, workspace, excel_bundle, nas_bundle, nas_fixture):
    # On charge le module import_excel_publication de cette copie ; le helper contrôle son
    # emplacement pour ne pas mélanger deux projets présents sur le poste.
    excel = _project_module(
        project, "import_excel_publication", "scripts/import_excel_publication.py"
    )
    # On charge le module load_nas_reconciliation de cette copie ; le helper contrôle son
    # emplacement pour ne pas mélanger deux projets présents sur le poste.
    nas = _project_module(
        project, "load_nas_reconciliation", "scripts/load_nas_reconciliation.py"
    )
    # On charge le module run_local_pipeline de cette copie ; le helper contrôle son emplacement
    # pour ne pas mélanger deux projets présents sur le poste.
    pilot = _project_module(
        project, "run_local_pipeline", "scripts/run_local_pipeline.py"
    )
    # On reprend les métadonnées de la publication dans excel_bundle ; cet accès suppose que la clé
    # a été produite ou vérifiée auparavant.
    publication = excel_bundle["publication"]
    # On regroupe dans outcome ces champs nommés ; on pourra les retrouver par leur clé plutôt que par
    # leur position.
    outcome = {
        # On renseigne l’état du traitement sous la clé 'status'.
        "status": "unchanged",
        # On renseigne l’identifiant de la publication Excel sous la clé 'publication_id'.
        "publication_id": publication["publication_id"],
        # On renseigne le chemin du tableau Excel regroupé sous la clé 'reference_path'.
        "reference_path": publication["reference"]["path"],
    }
    # On prépare une liste distincte pour chacun de ces résultats : calls, received. Elles seront
    # alimentées au même rythme dans la boucle.
    calls, received = [], []

    def ingest(root, *, vineyards, all_vineyards):
        # On vérifie ce cas avant la suite : la racine locale du projet diffère de workspace.
        if root != workspace:
            # On interrompt cette branche avec ValueError : 'Ingestion synthetique hors fixture.'.
            raise ValueError("Ingestion synthetique hors fixture.")
        # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées (la
        # copie reste superficielle).
        return dict(outcome)

    def execute(root, reference, vineyards, year, *, stop_on_error):
        # Pas de subprocess/extracteur/NAS : copier uniquement des sorties fictives.
        if (
            root != workspace
            # Ce cas est aussi retenu si la saison diffère de 2026.
            or year != 2026
            # Ce cas est aussi retenu si les domaines sélectionnés diffère de ['DomaineDemoB'].
            or vineyards != ["DomaineDemoB"]
            # Ce cas est aussi retenu si stop_on_error n’est pas exactement la valeur vraie (True).
            or stop_on_error is not True
        ):
            # On interrompt cette branche avec ValueError : 'Perimetre incompatible avec les fixtures
            # de repetition.'.
            raise ValueError("Perimetre incompatible avec les fixtures de repetition.")
        # On vérifie ce cas avant la suite : reference.resolve() diffère de (workspace /
        # publication['reference']['path']).resolve().
        if (
            reference.resolve()
            != (workspace / publication["reference"]["path"]).resolve()
        ):
            # On interrompt cette branche avec ValueError : 'Reference differente de la publication
            # synthetique.'.
            raise ValueError("Reference differente de la publication synthetique.")
        # On garde nas_fixture.manifest_path sous le nom relative ; cette affectation ne copie pas à
        # elle seule un objet mutable.
        relative = nas_fixture.manifest_path
        # On rassemble dans paths les 2 éléments explicitement indiqués, en conservant leur structure.
        paths = [relative, nas_bundle["manifest"]["reference_snapshot"]]
        # On ajoute [item['path'] for item in nas_bundle['report']['artifacts']] à paths et on conserve
        # ce nouvel état pour la suite.
        paths += [item["path"] for item in nas_bundle["report"]["artifacts"]]
        # On parcourt paths ; path désigne l’élément courant à chaque passage dans la boucle.
        for path in paths:
            # On garde dans source le chemin absolu résolu de nas_fixture.root / path, en tenant compte
            # des liens symboliques.
            source = (nas_fixture.root / path).resolve()
            # On garde dans target le chemin absolu résolu de workspace / path, en tenant compte des
            # liens symboliques.
            target = (workspace / path).resolve()
            # Les exemples restent dans leur dossier temporaire et on ne remplace pas une
            # destination déjà présente.
            if (
                not source.is_relative_to(nas_fixture.root.resolve())
                # Ce cas est aussi retenu si la condition target.is_relative_to(workspace / 'data')
                # n’est pas remplie.
                or not target.is_relative_to(workspace / "data")
                # Ce cas est aussi retenu si la destination existe.
                or target.exists()
            ):
                # On interrompt cette branche avec ValueError : 'Copie de fixture hors perimetre ou
                # artefact deja present.'.
                raise ValueError(
                    "Copie de fixture hors perimetre ou artefact deja present."
                )
            # On prépare le dossier local nécessaire à cette sortie ; créer le dossier ne produit
            # pas encore le fichier qu’il contiendra.
            target.parent.mkdir(parents=True, exist_ok=True)
            # On appelle shutil.copyfile avec source.
            shutil.copyfile(source, target)
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return 0, workspace / relative

    # On construit un dépôt de test qui remplace le stockage réel pour ce scénario.
    @contextmanager
    def fake_repository():
        # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après ce
        # point si son itération continue.
        yield object()

    # On transmet le lot Excel contrôlé au chargeur prévu par ce parcours.
    def excel_load(bundle, repository):
        # On appelle excel.check_still_current avec bundle.
        excel.check_still_current(bundle)
        # On vérifie ce cas avant la suite : l’identifiant de la publication Excel dans
        # bundle['publication'] diffère de l’identifiant de la publication Excel dans publication.
        if bundle["publication"]["publication_id"] != publication["publication_id"]:
            # On interrompt cette branche avec ValueError : 'Lot Excel simule incoherent.'.
            raise ValueError("Lot Excel simule incoherent.")
        # On ajoute 'excel' à la fin de calls ; les éléments précédents restent conservés.
        calls.append("excel")

    # On transmet le lot d’observations contrôlé au chargeur prévu par ce parcours.
    def nas_load(bundle, repository):
        # On appelle nas.check_files avec bundle.
        nas.check_files(bundle)
        # Cette branche traite le cas où calls diffère de ['excel'] ou l’identifiant du lot Excel dans
        # bundle['report'] diffère de l’identifiant de la publication Excel dans publication.
        if (
            calls != ["excel"]
            # Ce cas est aussi retenu si l’identifiant du lot Excel dans bundle['report'] diffère de
            # l’identifiant de la publication Excel dans publication.
            or bundle["report"]["excel_publication_id"] != publication["publication_id"]
        ):
            # On interrompt cette branche avec ValueError : 'Chargement NAS simule hors sequence.'.
            raise ValueError("Chargement NAS simule hors sequence.")
        # On ajoute 'nas' à la fin de calls ; les éléments précédents restent conservés.
        calls.append("nas")

    # On transmet l’événement au destinataire fourni pour ce journal.
    def sink(event):
        # Copie en memoire seulement : aucune ecriture PostgreSQL.
        received.append(json.loads(json.dumps(event)))
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "inserted"

    # On garde dans dependencies la valeur renvoyée par WorkflowDependencies.
    dependencies = WorkflowDependencies(
        ingest,
        excel.prepare_bundle,
        excel.check_still_current,
        pilot.select_vineyards,
        execute,
        nas.prepare_bundle,
        nas.check_files,
        fake_repository,
        fake_repository,
        excel_load,
        nas_load,
    )
    # On renvoie ces 4 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return dependencies, sink, calls, received


def archive(project, workspace, result):
    # On construit base en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    base = project / "logs/workflow_rehearsals"
    # On archive seulement les traces de la répétition conservées dans le dossier prévu.
    if not base.resolve().is_relative_to(project):
        # On interrompt cette branche avec ValueError : 'Destination des journaux hors du projet
        # local.'.
        raise ValueError("Destination des journaux hors du projet local.")
    # On construit folder en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    folder = base / result["workflow_execution_id"]
    # On crée ce dossier en refusant un emplacement déjà existant ; cela évite de réutiliser
    # silencieusement les sorties d’un ancien essai.
    folder.mkdir(parents=True, exist_ok=False)
    # On garde dans source le chemin absolu résolu de workspace / result['journal_relative_path'], en
    # tenant compte des liens symboliques.
    source = (workspace / result["journal_relative_path"]).resolve()
    # On archive seulement les traces de la répétition conservées dans le dossier prévu.
    if not source.is_relative_to(workspace / "data/03_normalized/workflow_runs"):
        # On interrompt cette branche avec ValueError : 'Journal hors fixture.'.
        raise ValueError("Journal hors fixture.")
    # On appelle shutil.copyfile avec source.
    shutil.copyfile(source, folder / "events.jsonl")
    # On garde dans payload un nouveau dictionnaire construit avec les valeurs indiquées (la copie
    # reste superficielle).
    payload = dict(
        result,
        execution_kind="synthetic_rehearsal",
        postgresql_writes=False,
        nas_access=False,
    )
    # On écrit le texte préparé avec l’encodage indiqué ; cette opération remplace le contenu de ce
    # fichier.
    (folder / "result.json").write_text(
        # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
        # décodé selon un réglage implicite du poste.
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # On fournit à l’appelant l’écriture de folder.relative_to(project) avec des / comme séparateurs.
    return folder.relative_to(project).as_posix()


# On exécute la répétition synthétique et on conserve ses traces locales.
def run_rehearsal(project, *, vineyards=None, all_vineyards=False, year=2026):
    # On garde dans project la valeur renvoyée par local_project.
    project = local_project(project)
    # On validu choix des domaines avant de construire les étapes ; choisir tous les domaines et
    # une liste explicite serait contradictoire.
    selected = validate_selection(vineyards, all_vineyards)
    # Dataset fictif unique : aucun vignoble reel lu a partir de l'argument utilisateur.
    if year != 2026 or (
        not all_vineyards and any(name.casefold() != "domainedemob" for name in selected)
    ):
        # On interrompt cette branche avec ValueError : 'Repetition disponible uniquement pour le
        # vignoble fictif DomaineDemoB, annee 2026.'.
        raise ValueError(
            "Repetition disponible uniquement pour le vignoble fictif DomaineDemoB, annee 2026."
        )
    # On charge le module synthetic_import_fixtures de cette copie ; le helper contrôle son
    # emplacement pour ne pas mélanger deux projets présents sur le poste.
    module = _project_module(
        project, "synthetic_import_fixtures", "scripts/synthetic_import_fixtures.py"
    )
    # On répartit les valeurs renvoyées par module.build_bundles entre (fixtures, bundles) ; leur ordre
    # doit correspondre à celui prévu par cet appel.
    fixtures, bundles = module.build_bundles(project)
    # On encadre cette opération pour que le bloc finally soit exécuté même si elle échoue.
    try:
        # On garde dans workspace le chemin absolu résolu de fixtures[0].root, en tenant compte des
        # liens symboliques.
        workspace = fixtures[0].root.resolve()
        # On répartit les valeurs renvoyées par rehearsal_dependencies entre (dependencies, sink,
        # calls, received) ; leur ordre doit correspondre à celui prévu par cet appel.
        dependencies, sink, calls, received = rehearsal_dependencies(
            project, workspace, bundles[0], bundles[1], fixtures[2]
        )
        # On garde dans result le bilan de la répétition avec les dépendances explicitement fournies.
        result = run_shared_rehearsal(
            workspace,
            dependencies=dependencies,
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            journal_sink=sink,
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="manual_script",
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=selected or None,
            # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
            all_vineyards=all_vineyards,
            # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
            year=year,
        )
        # On garde dans relative la valeur renvoyée par archive.
        relative = archive(project, workspace, result)
        # On vérifie ce cas avant la suite : l’état du traitement dans result correspond au texte
        # 'success'.
        if result["status"] == "success":
            # On garde dans events les événements du journal local après validation de leur ordre et de
            # leur identité.
            events = read_events(project / relative / "events.jsonl")
            # Cette branche traite le cas où calls diffère de ['excel', 'nas'] ou received diffère de
            # les événements du journal.
            if calls != ["excel", "nas"] or received != events:
                # On interrompt cette branche avec ValueError : 'Repetition non concordante ; journaux
                # conserves.'.
                raise ValueError("Repetition non concordante ; journaux conserves.")
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return result, relative
    finally:
        # On parcourt reversed(fixtures) ; fixture désigne l’élément courant à chaque passage dans la
        # boucle.
        for fixture in reversed(fixtures):
            # On appelle fixture.doCleanups sans argument positionnel.
            fixture.doCleanups()


def main(argv=None):
    # On parcourt (sys.stdout, sys.stderr) ; stream désigne l’élément courant à chaque passage dans la
    # boucle.
    for stream in (sys.stdout, sys.stderr):
        # Cette branche traite le cas où le contrôle hasattr(stream, 'reconfigure') est positif.
        if hasattr(stream, "reconfigure"):
            # On appelle stream.reconfigure sans argument positionnel.
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(description=__doc__)
    # On appelle parser.add_argument avec '--rehearsal'.
    parser.add_argument("--rehearsal", action="store_true", required=True)
    # On déclare des options incompatibles entre elles : le parseur rejettera leur emploi simultané
    # avant le traitement.
    selection = parser.add_mutually_exclusive_group(required=True)
    # On appelle selection.add_argument avec '--vineyard'.
    selection.add_argument("--vineyard", action="append")
    # On appelle selection.add_argument avec '--all-vineyards'.
    selection.add_argument("--all-vineyards", action="store_true")
    # On appelle parser.add_argument avec '--year'.
    parser.add_argument("--year", type=int, choices=[2026], default=2026)
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On récupère les options de la répétition locale, fondée sur les dépendances et données
    # synthétiques du projet.
    args = parser.parse_args(argv)
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "MODE REPETITION : fichiers fictifs, chargements et transmission du journal SIMULES."
    )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "Aucun .env lu ; aucune connexion PostgreSQL ; aucun acces NAS ; aucun lancement Airflow."
    )
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On répartit les valeurs renvoyées par run_rehearsal entre (result, relative) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        result, relative = run_rehearsal(
            args.project_root,
            # On transmet la sélection explicite des domaines concernés par cet appel.
            vineyards=args.vineyard,
            # Ce paramètre distingue le choix de tous les domaines d’une liste de sélection explicite.
            all_vineyards=args.all_vineyards,
            # On transmet la saison à utiliser pour les contrôles et les chemins concernés.
            year=args.year,
        )
        # On affiche 'Etapes confirmees : ' + str(len(result['completed_steps'])) + '/8' dans la sortie
        # du programme.
        print("Etapes confirmees : " + str(len(result["completed_steps"])) + "/8")
        # On affiche 'Journal local conserve : ' + relative dans la sortie du programme.
        print("Journal local conserve : " + relative)
        # On garde l’échec explicite : certaines étapes peuvent déjà être validées et ne doivent pas
        # être relancées comme si rien ne s’était passé.
        if result["status"] != "success":
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "RESULTAT REPETITION : NON CONFIRME ; code="
                + str(result["error_code"]),
                file=sys.stderr,
            )
            # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
            # retour.
            return 1
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT REPETITION : OK — entree manuelle et huit etapes assemblees ; aucun chargement reel."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Le pipeline metier, les secrets des sous-processus et le raccordement Airflow restent a preparer."
        )
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as exc:
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "REPETITION NON CONFIRMEE : "
            + type(exc).__name__
            + " ; arreter sans lancer le pipeline reel.",
            file=sys.stderr,
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
