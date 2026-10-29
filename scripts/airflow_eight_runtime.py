# Lecture du fichier — Contrôles du périmètre fictif complet avant les étapes métier.
# On relie les sources attendues au lot Excel préparé. L’accès à un dossier ne prouve pas encore la
# validité de tous les fichiers qu’il contient.
#

"""Precontrole des huit sources ; pas d'ingestion ni connexion SQL ici."""

# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles ROOT, YEAR, VINEYARDS, validate_names, require depuis airflow_eight_contract,
# pour les appels de ce fichier.
from airflow_eight_contract import ROOT, YEAR, VINEYARDS, validate_names, require


# On retrouve le périmètre demandé dans la publication Excel contrôlée.
def selected_from_publication(root=ROOT):
    # On rend disponibles prepare_bundle depuis import_excel_publication, pour les appels de ce
    # fichier.
    from import_excel_publication import prepare_bundle
    # On rend disponibles select_vineyards depuis run_local_pipeline, pour les appels de ce fichier.
    from run_local_pipeline import select_vineyards

    # On prépare en mémoire le lot et ses contrôles à partir des sorties locales ; le chargement
    # PostgreSQL n’est pas effectué par cette seule préparation.
    bundle = prepare_bundle(root)
    # On garde dans reference le chemin après vérification de son périmètre autorisé.
    reference = bundle["files"].path(bundle["publication"]["reference"]["path"])
    # On garde dans selected la valeur renvoyée par select_vineyards.
    selected = select_vineyards(reference, [], True, YEAR)
    # On appelle validate_names avec selected.
    validate_names(selected)
    # On appelle bundle['files'].unchanged sans argument positionnel.
    bundle["files"].unchanged()
    # On remet le lot préparé à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return bundle


# On contrôle les sources attendues pour chacun des huit domaines fictifs autorisés.
def check_eight_sources(root=ROOT):
    # On rend disponibles check_runtime depuis airflow_workflow_runtime_check, pour les appels de ce
    # fichier.
    from airflow_workflow_runtime_check import check_runtime

    # Reutilise tous les garde-fous du diagnostic DomaineDemoD valide (montages, partage,
    # destinations locales et sondes temporaires). Ne cree pas de journal metier.
    share = check_runtime(root)
    # On garde dans bundle la valeur renvoyée par selected_from_publication.
    bundle = selected_from_publication(root)
    # On rend disponibles discover depuis suivi_traitements_post_saison.ingestion.tracking_versioning,
    # pour les appels de ce fichier.
    from suivi_traitements_post_saison.ingestion.tracking_versioning import discover

    # On construit incoming en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée
    # ni dossier ni fichier.
    incoming = root / "data/01_incoming/suivi_acquisitions"
    # Ce contrôle porte sur la destination résolue ; un chemin textuellement situé sous le projet
    # pourrait encore pointer ailleurs par un lien symbolique.
    require(
        (root / "data").resolve().is_relative_to(root.resolve())
        # On exige aussi que incoming.resolve() reste sous (root / 'data').resolve().
        and incoming.resolve().is_relative_to((root / "data").resolve()),
        "EXCEL_INPUT_DIRECTORY_REDIRECTED",
    )
    # On garde dans available la valeur renvoyée par discover.
    available = discover(incoming, {name.casefold() for name in VINEYARDS})
    # On vérifie la présence des huit sources attendues avant de lancer le parcours complet ; un
    # périmètre incomplet ne doit pas être présenté comme complet.
    require(
        set(available) == {name.casefold() for name in VINEYARDS},
        "EIGHT_EXCEL_SOURCES_MISSING",
    )
    # On parcourt VINEYARDS ; name désigne l’élément courant à chaque passage dans la boucle.
    for name in VINEYARDS:
        # On sélectionne dans available les éléments désignés par name.casefold() ; (actual, source)
        # recevra cette sélection.
        actual, source = available[name.casefold()]
        # Les fichiers du lot doivent couvrir le périmètre autorisé ; on ne se contente pas du
        # nombre de fichiers.
        require(
            actual == name and source.resolve().is_relative_to(incoming.resolve()),
            "EXCEL_SOURCE_SCOPE_MISMATCH",
        )
        # On garde dans before les métadonnées de source, distinctes du contenu du fichier.
        before = source.stat()
        # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la sortie,
        # y compris après une erreur.
        with source.open("rb") as stream:
            # Un classeur .xlsx est une archive ZIP. Ce premier contrôle écarte un fichier renommé
            # ou illisible, sans garantir à lui seul que ses feuilles sont valides.
            require(stream.read(4) == b"PK\x03\x04", "EXCEL_SOURCE_NOT_ZIP_WORKBOOK")
        # On garde dans after les métadonnées de source, distinctes du contenu du fichier.
        after = source.stat()
        # On recontrôle les métadonnées du fichier ; un changement pendant la lecture rendrait le
        # lot difficile à rattacher à une version précise.
        require(
            (before.st_size, before.st_mtime_ns, before.st_ino)
            == (after.st_size, after.st_mtime_ns, after.st_ino),
            "EXCEL_SOURCE_CHANGED",
        )
        # On parcourt (Path('/opt/nas/brute_v2025') / name / str(YEAR), Path('/opt/nas/data_pro… ; path
        # désigne l’élément courant à chaque passage dans la boucle.
        for path in (
            Path("/opt/nas/brute_v2025") / name / str(YEAR),
            Path("/opt/nas/data_processing_2025") / name / "acquisitions" / str(YEAR),
        ):
            # On utilise os.scandir(path) dans son contexte de gestion ; les opérations de sortie sont
            # exécutées en quittant le bloc.
            with os.scandir(path) as entries:
                # On appelle next avec entries.
                next(entries, None)
        # On parcourt (('parcels', 'parcels_acquisitions_map.json'), ('passages', 'parcels_pass… ;
        # (folder, suffix) désigne l’élément courant à chaque passage dans la boucle.
        for folder, suffix in (
            ("parcels", "parcels_acquisitions_map.json"),
            ("passages", "parcels_passages_acquisitions_map.json"),
        ):
            # On construit path en assemblant les morceaux du chemin. L’opérateur / de pathlib ne
            # crée ni dossier ni fichier.
            path = (
                Path("/opt/nas/data_processing_2025")
                / name
                / folder
                / (name + "_" + suffix)
            )
            # On ouvre la ressource indiquée pour la durée du bloc ; sa fermeture est assurée à la
            # sortie, y compris après une erreur.
            with path.open("r", encoding="utf-8-sig") as stream:
                # Les correspondances NAS doivent être des objets JSON de la forme attendue avant de
                # servir à relier acquisitions, parcelles et passages.
                require(
                    isinstance(json.load(stream), (dict, list)),
                    "NAS_MAPPING_JSON_INVALID",
                )
    # On appelle bundle['files'].unchanged sans argument positionnel.
    bundle["files"].unchanged()
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return share, bundle["publication"]["publication_id"]


# On enveloppe les étapes avec les contrôles de contexte requis à leurs transitions.
def guarded_steps(plan):
    # On compare les noms des étapes au parcours approuvé pour éviter qu’un assemblage différent
    # soit exécuté sous le même nom.
    require(
        tuple(name for name, _ in plan.steps)
        == __import__("airflow_eight_contract").STEPS,
        "SHARED_STEPS_MISMATCH",
    )
    # On rend disponibles select_vineyards depuis run_local_pipeline, pour les appels de ce fichier.
    from run_local_pipeline import select_vineyards

    # On prépare wrapped comme liste vide ; on la remplira au fil des opérations suivantes.
    wrapped = []
    # On parcourt plan.steps ; (name, action) désigne l’élément courant à chaque passage dans la
    # boucle.
    for name, action in plan.steps:
        # On vérifie ce cas avant la suite : le nom en cours correspond au texte 'nas_scope_prepare'.
        if name == "nas_scope_prepare":

            # On exécute cette étape seulement après le contrôle prévu par son enveloppe.
            def guarded(context, original=action):
                # On garde dans outcome la valeur renvoyée par original.
                outcome = original(context)
                # On appelle validate_names avec outcome['vineyards'].
                validate_names(outcome["vineyards"])
                # On reprend les repères du tableau Excel retenu pour ce run dans context.results ;
                # cet accès suppose que la clé a été produite ou vérifiée auparavant.
                pinned = context.results["excel_reference_pin"]
                # On appelle validate_names avec select_vineyards(pinned.reference_path, [], True,
                # YEAR).
                validate_names(select_vineyards(pinned.reference_path, [], True, YEAR))
                # On remet outcome à l’appelant ; les étapes suivantes de cette fonction ne sont plus
                # parcourues.
                return outcome

            # On ajoute (name, guarded) à la fin de wrapped ; les éléments précédents restent
            # conservés.
            wrapped.append((name, guarded))
        else:
            # On ajoute (name, action) à la fin de wrapped ; les éléments précédents restent conservés.
            wrapped.append((name, action))
    # On remet wrapped à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return wrapped
