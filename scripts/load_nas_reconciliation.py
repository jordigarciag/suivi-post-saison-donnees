# Lecture du fichier — Préparation et import des observations NAS et des rapprochements historisés.
# On conserve les observations puis on gère le pointeur vers le bilan actif. Le pointeur indique quoi
# consulter actuellement ; il ne remplace pas les anciennes observations.
#

"""Charge les snapshots NAS/rapprochement controles, sans consulter le NAS.

Prerequis : SQL 002/004 et publication Excel deja importee. Les dix tables
historiques sont comparees exactement sur une relance : aucune reparation.
Le pointeur courant est active dans la meme transaction, par vignoble.
Compte dedie projet12_importer ; aucun repli vers un compte administrateur.
"""

# On diffère l’évaluation des annotations de type ; cette directive doit rester avant les autres
# imports.
from __future__ import annotations
# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles Counter depuis collections, pour les appels de ce fichier.
from collections import Counter
# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys

# On rend disponibles check_pipeline, plain_json, ManifestPaths, boolean, integer depuis
# import_nas_reconciliation, pour les appels de ce fichier.
from import_nas_reconciliation import (
    check_pipeline,
    plain_json,
    ManifestPaths,
    boolean,
    integer,
)
# On rend disponibles LocalFiles, require, read_csv, sha256 depuis load_excel_publication, pour les
# appels de ce fichier.
from load_excel_publication import LocalFiles, require, read_csv, sha256
# On rend disponibles payload, timestamp depuis import_excel_publication, pour les appels de ce
# fichier.
from import_excel_publication import payload, timestamp
# On rend disponibles database_config, verify_import_identity depuis import_connection_config, pour les
# appels de ce fichier.
from import_connection_config import database_config, verify_import_identity

# Ordre : les parents et passages sont inseres avant leurs associations.
COLUMNS = {
    # On associe la clé 'core.pipeline_runs' à cette valeur dans cet objet.
    "core.pipeline_runs": (
        "pipeline_execution_id",
        "project_year",
        "status",
        "started_at",
        "finished_at",
        "excel_publication_id",
        "reference_sha256",
        "reference_snapshot_path",
        "manifest_path",
        "manifest_sha256",
        "script_identity",
        "manifest_payload",
    ),
    # On associe la clé 'core.nas_observation_runs' à cette valeur dans cet objet.
    "core.nas_observation_runs": (
        "pipeline_execution_id",
        "vineyard_key",
        "extraction_run_id",
        "scope_excel_publication_id",
        "scope_excel_version_id",
        "checked_at",
        "acquisition_rows",
        "association_rows",
        "passage_rows",
        "metadata_payload",
    ),
    # On associe la clé 'core.reconciliation_runs' à cette valeur dans cet objet.
    "core.reconciliation_runs": (
        "pipeline_execution_id",
        "vineyard_key",
        "reconciliation_run_id",
        "nas_pipeline_execution_id",
        "excel_publication_id",
        "excel_version_id",
        "reconciled_at",
        "acquisition_rows",
        "association_rows",
        "passage_rows",
        "rules_identity",
        "metadata_payload",
    ),
    # On associe la clé 'core.pipeline_artifacts' à cette valeur dans cet objet.
    "core.pipeline_artifacts": (
        "pipeline_execution_id",
        "vineyard_key",
        "stage",
        "artifact_kind",
        "artifact_path",
        "artifact_sha256",
        "artifact_size",
        "row_count",
    ),
    # On associe la clé 'staging.nas_acquisition_observations' à cette valeur dans cet objet.
    "staging.nas_acquisition_observations": (
        "pipeline_execution_id",
        "vineyard_key",
        "acquisition_id_normalise",
        "passage_outputs_verifiable",
        "vitiparcel_created",
        "payload",
    ),
    # On associe la clé 'staging.nas_passage_observations' à cette valeur dans cet objet.
    "staging.nas_passage_observations": (
        "pipeline_execution_id",
        "vineyard_key",
        "parcel_name",
        "passage_name",
        "stocks_json_exists",
        "non_healthy_status_count",
        "vitiparcel_created",
        "payload",
    ),
    # On associe la clé 'staging.nas_association_observations' à cette valeur dans cet objet.
    "staging.nas_association_observations": (
        "pipeline_execution_id",
        "vineyard_key",
        "acquisition_id_normalise",
        "parcel_name",
        "passage_name",
        "payload",
    ),
    # On associe la clé 'staging.reconciliation_acquisition_rows' à cette valeur dans cet objet.
    "staging.reconciliation_acquisition_rows": (
        "pipeline_execution_id",
        "vineyard_key",
        "reconciliation_run_id",
        "nas_pipeline_execution_id",
        "acquisition_id_normalise",
        "observed_acquisition_id",
        "passage_outputs_verifiable",
        "vitiparcel_created",
        "acquisition_review_candidate",
        "payload",
    ),
    # On associe la clé 'staging.reconciliation_passage_rows' à cette valeur dans cet objet.
    "staging.reconciliation_passage_rows": (
        "pipeline_execution_id",
        "vineyard_key",
        "reconciliation_run_id",
        "nas_pipeline_execution_id",
        "parcel_name",
        "passage_name",
        "vitiparcel_ready_verifiable",
        "vitiparcel_ready_for_delivery",
        "passage_review_candidate",
        "payload",
    ),
    # On associe la clé 'staging.reconciliation_association_rows' à cette valeur dans cet objet.
    "staging.reconciliation_association_rows": (
        "pipeline_execution_id",
        "vineyard_key",
        "reconciliation_run_id",
        "nas_pipeline_execution_id",
        "acquisition_id_normalise",
        "parcel_name",
        "passage_name",
        "payload",
    ),
}
# On regroupe dans KEYS ces champs nommés ; on pourra les retrouver par leur clé plutôt que par leur
# position.
KEYS = {
    # On associe la clé 'core.pipeline_runs' à cette valeur dans cet objet.
    "core.pipeline_runs": ("pipeline_execution_id",),
    # On associe la clé 'core.nas_observation_runs' à cette valeur dans cet objet.
    "core.nas_observation_runs": ("pipeline_execution_id", "vineyard_key"),
    # On associe la clé 'core.reconciliation_runs' à cette valeur dans cet objet.
    "core.reconciliation_runs": (
        "pipeline_execution_id",
        "vineyard_key",
        "reconciliation_run_id",
    ),
    # On associe la clé 'core.pipeline_artifacts' à cette valeur dans cet objet.
    "core.pipeline_artifacts": (
        "pipeline_execution_id",
        "vineyard_key",
        "stage",
        "artifact_kind",
    ),
    # On associe la clé 'staging.nas_acquisition_observations' à cette valeur dans cet objet.
    "staging.nas_acquisition_observations": (
        "pipeline_execution_id",
        "vineyard_key",
        "acquisition_id_normalise",
    ),
    # On associe la clé 'staging.nas_passage_observations' à cette valeur dans cet objet.
    "staging.nas_passage_observations": (
        "pipeline_execution_id",
        "vineyard_key",
        "parcel_name",
        "passage_name",
    ),
    # On associe la clé 'staging.nas_association_observations' à cette valeur dans cet objet.
    "staging.nas_association_observations": (
        "pipeline_execution_id",
        "vineyard_key",
        "acquisition_id_normalise",
        "parcel_name",
        "passage_name",
    ),
    # On associe la clé 'staging.reconciliation_acquisition_rows' à cette valeur dans cet objet.
    "staging.reconciliation_acquisition_rows": (
        "pipeline_execution_id",
        "vineyard_key",
        "reconciliation_run_id",
        "acquisition_id_normalise",
    ),
    # On associe la clé 'staging.reconciliation_passage_rows' à cette valeur dans cet objet.
    "staging.reconciliation_passage_rows": (
        "pipeline_execution_id",
        "vineyard_key",
        "reconciliation_run_id",
        "parcel_name",
        "passage_name",
    ),
    # On associe la clé 'staging.reconciliation_association_rows' à cette valeur dans cet objet.
    "staging.reconciliation_association_rows": (
        "pipeline_execution_id",
        "vineyard_key",
        "reconciliation_run_id",
        "acquisition_id_normalise",
        "parcel_name",
        "passage_name",
    ),
}
# On rassemble dans JSON_COLUMNS les 6 éléments explicitement indiqués, en conservant leur structure.
JSON_COLUMNS = {
    "script_identity",
    "manifest_payload",
    "metadata_payload",
    "rules_identity",
    "payload",
    "identity",
}
# On fixe POINTER à cette valeur explicite ; les contrôles qui l’utilisent partent tous du même
# réglage.
POINTER = "core.current_vineyard_reconciliations"
# On rassemble dans EXCEL_TABLES les 5 éléments explicitement indiqués, en conservant leur structure.
EXCEL_TABLES = {
    "core.excel_publications",
    "core.excel_publication_versions",
    "core.excel_versions",
    "staging.excel_publication_rows",
    "core.vineyards",
}


# On rassemble le lot à partir des fichiers et métadonnées contrôlés par cette fonction.
def prepare_bundle(root, manifest_path):
    # On garde dans files la valeur renvoyée par LocalFiles.
    files = LocalFiles(root)
    # On vérifie les sorties du parcours NAS et leur cohérence avant de considérer le résultat comme
    # chargeable.
    report = check_pipeline(root, manifest_path, files=files)
    # On garde dans manifest la valeur renvoyée par plain_json.
    manifest = plain_json(files.read(manifest_path), manifest_path)
    # On garde dans paths la valeur renvoyée par ManifestPaths.
    paths = ManifestPaths(root, manifest["reference_source"])
    # On garde dans reference_path la valeur renvoyée par paths.relative.
    reference_path = paths.relative(manifest["reference_source"])
    # On garde dans pub_path l’écriture de Path(reference_path).parent / 'manifest.json' avec des /
    # comme séparateurs.
    pub_path = (Path(reference_path).parent / "manifest.json").as_posix()
    # On garde dans publication le contenu du fichier JSON après passage par le lecteur contrôlé.
    publication = files.json(pub_path)
    # On garde dans reference les lignes décodées par le lecteur CSV de ce module.
    reference = read_csv(files.read(reference_path), reference_path, set())
    # On distribue ces valeurs entre execution, pub_id, dans l’ordre de l’affectation. Chaque nom
    # reçoit son propre élément.
    execution, pub_id = report["pipeline_execution_id"], report["excel_publication_id"]
    # On indexe le résultat par table, avec [] comme valeur ; les contrôles d’unicité sont
    # importants car une même clé ne garde qu’une valeur dans un dictionnaire.
    records = {table: [] for table in COLUMNS}
    # On ajoute dict(pipeline_execution_id=execution, project_year=manifest['project_year'],
    # status=manif… à la fin de records['core.pipeline_runs'] ; les éléments précédents restent
    # conservés.
    records["core.pipeline_runs"].append(
        dict(
            # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de cet
            # appel.
            pipeline_execution_id=execution,
            project_year=manifest["project_year"],
            # On fournit l’état du traitement via le paramètre status de cet appel.
            status=manifest["status"],
            # On fournit la date de début via le paramètre started_at de cet appel.
            started_at=timestamp(manifest["started_at"]),
            # On fournit la date de fin via le paramètre finished_at de cet appel.
            finished_at=timestamp(manifest["finished_at"]),
            # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de cet appel.
            excel_publication_id=pub_id,
            # On fournit l’empreinte du tableau Excel regroupé via le paramètre reference_sha256 de cet
            # appel.
            reference_sha256=manifest["reference_sha256"],
            reference_snapshot_path=paths.relative(manifest["reference_snapshot"]),
            # On fournit le chemin du manifeste via le paramètre manifest_path de cet appel.
            manifest_path=manifest_path,
            # On fournit l’empreinte du manifeste via le paramètre manifest_sha256 de cet appel.
            manifest_sha256=sha256(files.read(manifest_path)),
            script_identity=manifest["script_sha256"],
            # On fournit le contenu du manifeste via le paramètre manifest_payload de cet appel.
            manifest_payload=manifest,
        )
    )
    # On prépare pointers comme liste vide ; on la remplira au fil des opérations suivantes.
    pointers = []
    # On parcourt ces collections en parallèle ; les éléments de même position seront comparés ou
    # associés dans le corps de la boucle.
    for item, summary in zip(manifest["vineyards"], report["vineyards"]):
        # On prépare une comparaison sans tenir compte de la casse ; on ne modifie pas ici le nom
        # enregistré dans les données sources.
        key = item["vineyard"].casefold()
        # On sélectionne dans publication['versions'] les éléments désignés par key ; entry recevra
        # cette sélection.
        entry = publication["versions"][key]
        # On garde dans base un nouveau dictionnaire construit avec les valeurs indiquées.
        base = dict(pipeline_execution_id=execution, vineyard_key=key)
        # On récupère item['reconciliation_run_id'] et on le garde dans rec_id pour la suite.
        rec_id = item["reconciliation_run_id"]
        # On garde dans rec_base un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        rec_base = dict(
            base, reconciliation_run_id=rec_id, nas_pipeline_execution_id=execution
        )
        # On crée le dictionnaire vide datasets pour y ranger ensuite les éléments par clé.
        datasets = {}
        # On parcourt ('nas_observation', 'reconciliation') ; stage désigne l’élément courant à chaque
        # passage dans la boucle.
        for stage in ("nas_observation", "reconciliation"):
            # On crée le dictionnaire vide datasets[stage] pour y ranger ensuite les éléments par clé.
            datasets[stage] = {}
            # On parcourt report['artifacts'] ; artifact désigne l’élément courant à chaque passage
            # dans la boucle.
            for artifact in report["artifacts"]:
                # Cette branche traite le cas où le domaine concerné dans artifact correspond à le
                # domaine concerné dans item et l’étape concernée dans artifact correspond à l’étape
                # concernée.
                if (
                    artifact["vineyard"] == item["vineyard"]
                    # On exige aussi que l’étape concernée dans artifact correspond à l’étape
                    # concernée.
                    and artifact["stage"] == stage
                ):
                    # On récupère artifact['kind'] et on le garde dans kind pour la suite.
                    kind = artifact["kind"]
                    # On garde dans datasets[stage][kind] les lignes décodées par le lecteur CSV de ce
                    # module.
                    datasets[stage][kind] = read_csv(
                        files.read(artifact["path"]), artifact["path"], set()
                    )
                    # On ajoute dict(base, stage=stage, artifact_kind=kind,
                    # artifact_path=artifact['path'], artifact_sha2… à la fin de
                    # records['core.pipeline_artifacts'] ; les éléments précédents restent conservés.
                    records["core.pipeline_artifacts"].append(
                        dict(
                            base,
                            # On fournit l’étape concernée via le paramètre stage de cet appel.
                            stage=stage,
                            artifact_kind=kind,
                            artifact_path=artifact["path"],
                            artifact_sha256=artifact["sha256"],
                            artifact_size=artifact["size"],
                            row_count=artifact["rows"],
                        )
                    )
        # On distribue ces valeurs entre nas, rec, dans l’ordre de l’affectation. Chaque nom reçoit
        # son propre élément.
        nas, rec = datasets["nas_observation"], datasets["reconciliation"]
        # On garde dans volumes un nouveau dictionnaire construit avec les valeurs indiquées.
        volumes = dict(
            acquisition_rows=len(nas["acquisitions"]),
            association_rows=len(nas["associations"]),
            passage_rows=len(nas["passages"]),
        )
        # On ajoute dict(base, extraction_run_id=item['extraction_run_id'],
        # scope_excel_publication_id=pub_id… à la fin de records['core.nas_observation_runs'] ; les
        # éléments précédents restent conservés.
        records["core.nas_observation_runs"].append(
            dict(
                base,
                extraction_run_id=item["extraction_run_id"],
                scope_excel_publication_id=pub_id,
                scope_excel_version_id=entry["version_id"],
                # On fournit la date du contrôle via le paramètre checked_at de cet appel.
                checked_at=timestamp(summary["checked_at"]),
                # On fournit les métadonnées détaillées via le paramètre metadata_payload de cet appel.
                metadata_payload=item["observations"],
                **volumes,
            )
        )
        # On ajoute dict(rec_base, excel_publication_id=pub_id, excel_version_id=entry['version_id'],
        # reconci… à la fin de records['core.reconciliation_runs'] ; les éléments précédents restent
        # conservés.
        records["core.reconciliation_runs"].append(
            dict(
                rec_base,
                # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de cet
                # appel.
                excel_publication_id=pub_id,
                excel_version_id=entry["version_id"],
                # On fournit la date du rapprochement via le paramètre reconciled_at de cet appel.
                reconciled_at=timestamp(summary["reconciled_at"]),
                rules_identity={
                    # On associe la clé 'script_sha256' à cette valeur dans cet objet.
                    "script_sha256": manifest["script_sha256"],
                    # On associe la clé 'capture_complete' à cette valeur dans cet objet.
                    "capture_complete": False,
                    # On associe la clé 'note' à cette valeur dans cet objet.
                    "note": "Empreintes disponibles ; dependances et configurations non capturees integralement.",
                },
                # On fournit les métadonnées détaillées via le paramètre metadata_payload de cet appel.
                metadata_payload=item,
                **volumes,
            )
        )

        def b(row, column):
            # On fournit à l’appelant la conversion booléenne définie par ce module, avec sa gestion
            # des valeurs inconnues.
            return boolean(row[column], item["vineyard"] + "." + column)

        # On parcourt les acquisitions dans nas ; row désigne l’élément courant à chaque passage dans
        # la boucle.
        for row in nas["acquisitions"]:
            # On ajoute dict(base, acquisition_id_normalise=row['acquisition_id_normalise'],
            # passage_outputs_veri… à la fin de records['staging.nas_acquisition_observations'] ; les
            # éléments précédents restent conservés.
            records["staging.nas_acquisition_observations"].append(
                dict(
                    base,
                    # On fournit l’identifiant normalisé de l’acquisition via le paramètre
                    # acquisition_id_normalise de cet appel.
                    acquisition_id_normalise=row["acquisition_id_normalise"],
                    passage_outputs_verifiable=b(row, "passage_outputs_verifiable"),
                    vitiparcel_created=b(row, "vitiparcel_created"),
                    # On fournit le contenu détaillé via le paramètre payload de cet appel.
                    payload=payload(row),
                )
            )
        # On parcourt les passages dans nas ; row désigne l’élément courant à chaque passage dans la
        # boucle.
        for row in nas["passages"]:
            # On ajoute dict(base, parcel_name=row['parcel_name'], passage_name=row['passage_name'],
            # stocks_json_… à la fin de records['staging.nas_passage_observations'] ; les éléments
            # précédents restent conservés.
            records["staging.nas_passage_observations"].append(
                dict(
                    base,
                    parcel_name=row["parcel_name"],
                    passage_name=row["passage_name"],
                    stocks_json_exists=b(row, "stocks_json_exists"),
                    non_healthy_status_count=integer(
                        row["non_healthy_status_count"], "non_healthy_status_count"
                    ),
                    vitiparcel_created=b(row, "vitiparcel_created"),
                    # On fournit le contenu détaillé via le paramètre payload de cet appel.
                    payload=payload(row),
                )
            )
        # On parcourt les associations entre acquisitions et passages dans nas ; row désigne l’élément
        # courant à chaque passage dans la boucle.
        for row in nas["associations"]:
            # On ajoute dict(base, acquisition_id_normalise=row['acquisition_id_normalise'],
            # parcel_name=row['par… à la fin de records['staging.nas_association_observations'] ; les
            # éléments précédents restent conservés.
            records["staging.nas_association_observations"].append(
                dict(
                    base,
                    # On fournit l’identifiant normalisé de l’acquisition via le paramètre
                    # acquisition_id_normalise de cet appel.
                    acquisition_id_normalise=row["acquisition_id_normalise"],
                    parcel_name=row["parcel_name"],
                    passage_name=row["passage_name"],
                    # On fournit le contenu détaillé via le paramètre payload de cet appel.
                    payload=payload(row),
                )
            )
        # On parcourt les acquisitions dans rec ; row désigne l’élément courant à chaque passage dans
        # la boucle.
        for row in rec["acquisitions"]:
            # On ajoute dict(rec_base, acquisition_id_normalise=row['acquisition_id_normalise'],
            # observed_acquisi… à la fin de records['staging.reconciliation_acquisition_rows'] ; les
            # éléments précédents restent conservés.
            records["staging.reconciliation_acquisition_rows"].append(
                dict(
                    rec_base,
                    # On fournit l’identifiant normalisé de l’acquisition via le paramètre
                    # acquisition_id_normalise de cet appel.
                    acquisition_id_normalise=row["acquisition_id_normalise"],
                    observed_acquisition_id=row["acquisition_id_normalise"],
                    passage_outputs_verifiable=b(row, "passage_outputs_verifiable"),
                    vitiparcel_created=b(row, "vitiparcel_created"),
                    acquisition_review_candidate=b(
                        row, "acquisition_new_anomaly_candidate"
                    ),
                    # On fournit le contenu détaillé via le paramètre payload de cet appel.
                    payload=payload(row),
                )
            )
        # On parcourt les passages dans rec ; row désigne l’élément courant à chaque passage dans la
        # boucle.
        for row in rec["passages"]:
            # On ajoute dict(rec_base, parcel_name=row['parcel_name'],
            # passage_name=row['passage_name'], vitiparc… à la fin de
            # records['staging.reconciliation_passage_rows'] ; les éléments précédents restent
            # conservés.
            records["staging.reconciliation_passage_rows"].append(
                dict(
                    rec_base,
                    parcel_name=row["parcel_name"],
                    passage_name=row["passage_name"],
                    vitiparcel_ready_verifiable=b(row, "vitiparcel_ready_verifiable"),
                    vitiparcel_ready_for_delivery=b(
                        row, "vitiparcel_ready_for_delivery"
                    ),
                    passage_review_candidate=b(row, "passage_review_candidate"),
                    # On fournit le contenu détaillé via le paramètre payload de cet appel.
                    payload=payload(row),
                )
            )
        # On parcourt les associations entre acquisitions et passages dans rec ; row désigne l’élément
        # courant à chaque passage dans la boucle.
        for row in rec["associations"]:
            # On ajoute dict(rec_base, acquisition_id_normalise=row['acquisition_id_normalise'],
            # parcel_name=row[… à la fin de records['staging.reconciliation_association_rows'] ; les
            # éléments précédents restent conservés.
            records["staging.reconciliation_association_rows"].append(
                dict(
                    rec_base,
                    # On fournit l’identifiant normalisé de l’acquisition via le paramètre
                    # acquisition_id_normalise de cet appel.
                    acquisition_id_normalise=row["acquisition_id_normalise"],
                    parcel_name=row["parcel_name"],
                    passage_name=row["passage_name"],
                    # On fournit le contenu détaillé via le paramètre payload de cet appel.
                    payload=payload(row),
                )
            )
        # On ajoute dict(vineyard_key=key, pipeline_execution_id=execution,
        # reconciliation_run_id=rec_id) à la fin de pointers ; les éléments précédents restent
        # conservés.
        pointers.append(
            dict(
                # On fournit la clé du domaine via le paramètre vineyard_key de cet appel.
                vineyard_key=key,
                # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de
                # cet appel.
                pipeline_execution_id=execution,
                reconciliation_run_id=rec_id,
            )
        )
    # On parcourt les couples (table, rows) de records : on garde ensemble la clé et sa valeur au
    # lieu des traiter dans deux listes séparées.
    for table, rows in records.items():
        # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            all(set(row) == set(COLUMNS[table]) for row in rows),
            "Colonnes incoherentes : " + table,
        )
    # On garde dans bundle un nouveau dictionnaire construit avec les valeurs indiquées.
    bundle = dict(
        files=files,
        # On fournit le bilan via le paramètre report de cet appel.
        report=report,
        # On fournit le manifeste du lot via le paramètre manifest de cet appel.
        manifest=manifest,
        # On fournit la publication Excel via le paramètre publication de cet appel.
        publication=publication,
        pub_path=pub_path,
        records=records,
        pointers=pointers,
        # On fournit le repère utilisé pour les données Excel via le paramètre reference de cet appel.
        reference=reference,
    )
    # On recontrôle les fichiers utilisés par le lot pour repérer un changement survenu depuis sa
    # préparation.
    check_files(bundle)
    # On remet le lot préparé à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return bundle


# On contrôle les fichiers du lot et leurs métadonnées avant des utiliser.
def check_files(bundle):
    # On appelle bundle['files'].unchanged sans argument positionnel.
    bundle["files"].unchanged()
    # On garde dans state le chemin après vérification de son périmètre autorisé.
    state = bundle["files"].path("state/excel_ingestion")
    # On exige ici que la condition (state / 'ingestion.lock').exists() n’est pas remplie et la
    # condition (state / 'pending_publication.json').exists() n’est pas remplie. Si ce n’est pas le
    # cas, le message associé bloque la suite.
    require(
        not (state / "ingestion.lock").exists()
        # On exige aussi que la condition (state / 'pending_publication.json').exists() n’est pas
        # remplie.
        and not (state / "pending_publication.json").exists(),
        "Ingestion locale en cours ou interrompue : chargement bloque.",
    )


# On compare les enregistrements pour distinguer une réutilisation d’une divergence.
def equal_records(existing, expected, keys, label):
    def mapping(rows):
        # On indexe le résultat par tuple((row[key] for key in keys)), avec row comme valeur ; les
        # contrôles d’unicité sont importants car une même clé ne garde qu’une valeur dans un
        # dictionnaire.
        result = {tuple(row[key] for key in keys): row for row in rows}
        # On exige ici que len(result) correspond à len(rows). Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(len(result) == len(rows), "Identifiants dupliques : " + label)
        # On remet le résultat de cette opération à l’appelant ; les étapes suivantes de cette fonction
        # ne sont plus parcourues.
        return result

    # On exige ici que mapping(existing) correspond à mapping(expected). Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        mapping(existing) == mapping(expected),
        "Historique different ou incomplet : "
        + label
        + ". Aucune reparation automatique.",
    )


class PostgresRepository:
    def __init__(self, connection):
        # On rend disponibles sql depuis psycopg, pour les appels de ce fichier.
        from psycopg import sql
        # On rend disponibles Jsonb depuis psycopg.types.json, pour les appels de ce fichier.
        from psycopg.types.json import Jsonb

        # On distribue ces valeurs entre self.connection, self.sql, self.Jsonb, dans l’ordre de
        # l’affectation. Chaque nom reçoit son propre élément.
        self.connection, self.sql, self.Jsonb = connection, sql, Jsonb

    @contextmanager
    def transaction(self):
        # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre pas
        # tout le workflow.
        with self.connection.transaction():
            # On applique ce réglage à la transaction courante ; il ne s’agit pas de modifier
            # durablement la configuration du serveur PostgreSQL.
            self.connection.execute("SET LOCAL lock_timeout = '10s'")
            # On envoie cette requête à self.connection avec ses paramètres ; son résultat sera
            # contrôlé séparément.
            self.connection.execute("SELECT pg_advisory_xact_lock(%s,%s)", (120026, 1))
            # On parcourt set(COLUMNS) | {POINTER} | EXCEL_TABLES ; table désigne l’élément courant à
            # chaque passage dans la boucle.
            for table in set(COLUMNS) | {POINTER} | EXCEL_TABLES:
                # On exige ici que self.connection.execute('SELECT to_regclass(%s)',
                # (table,)).fetchone()[0] est renseigné (différent de None). Si ce n’est pas le cas, le
                # message associé bloque la suite.
                require(
                    self.connection.execute(
                        "SELECT to_regclass(%s)", (table,)
                    ).fetchone()[0]
                    is not None,
                    "Table absente : " + table + ". Verifier SQL 002/004.",
                )
            # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle reprendra après
            # ce point si son itération continue.
            yield

    def name(self, table):
        # On exige ici que table appartient à set(COLUMNS) | {POINTER} | EXCEL_TABLES. Si ce n’est pas
        # le cas, le message associé bloque la suite.
        require(
            table in set(COLUMNS) | {POINTER} | EXCEL_TABLES, "Table non autorisee."
        )
        # On protège les noms de schéma, table ou colonne avec Identifier ; les valeurs des lignes
        # sont, elles, transmises séparément aux paramètres SQL.
        return self.sql.Identifier(*table.split("."))

    def read(self, table, columns, filters):
        # Pas de droit UPDATE demande sur les historiques : comparaison seule.
        # Le verrou consultatif commun reste acquis pendant toute la transaction.
        # Seul le pointeur mutable conserve un verrou de ligne FOR UPDATE.
        template = "SELECT {} FROM {} WHERE {}" + (
            " FOR UPDATE" if table == POINTER else ""
        )
        # On garde dans query la valeur renvoyée par self.sql.SQL(template).format.
        query = self.sql.SQL(template).format(
            self.sql.SQL(",").join(map(self.sql.Identifier, columns)),
            self.name(table),
            self.sql.SQL(" AND ").join(
                self.sql.SQL("{} = %s").format(self.sql.Identifier(k)) for k in filters
            ),
        )
        # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
        # présenter.
        rows = self.connection.execute(query, tuple(filters.values())).fetchall()
        # On remet [dict(zip(columns, row)) for row in rows] à l’appelant ; les étapes suivantes de
        # cette fonction ne sont plus parcourues.
        return [dict(zip(columns, row)) for row in rows]

    def insert(self, table, columns, rows):
        # On prévoit le cas où rows est évalué comme faux, par exemple une valeur vide selon son type.
        if not rows:
            # On quitte cette fonction à cet endroit ; les instructions situées après ce retour ne sont
            # pas exécutées.
            return
        # On garde dans query la valeur renvoyée par self.sql.SQL('INSERT INTO {} ({}) VALUES
        # ({})').format.
        query = self.sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            self.name(table),
            self.sql.SQL(",").join(map(self.sql.Identifier, columns)),
            self.sql.SQL(",").join(self.sql.Placeholder() for _ in columns),
        )
        # On construit values comme une liste à partir de tuple((self.Jsonb(row[c]) if c in
        # JSON_COLUMNS else row[c] for c…, pour chaque row de rows.
        values = [
            tuple(self.Jsonb(row[c]) if c in JSON_COLUMNS else row[c] for c in columns)
            for row in rows
        ]
        # On utilise self.connection.cursor() dans son contexte de gestion ; les opérations de sortie
        # sont exécutées en quittant le bloc.
        with self.connection.cursor() as cursor:
            # On appelle cursor.executemany avec query.
            cursor.executemany(query, values)

    # On change le lien courant selon le contrat de ce dépôt ; les anciennes observations restent
    # distinctes.
    def replace_pointer(self, record):
        # On envoie cette requête à self.connection avec ses paramètres ; son résultat sera contrôlé
        # séparément.
        self.connection.execute(
            self.sql.SQL("""UPDATE {} SET pipeline_execution_id=%s,
            reconciliation_run_id=%s, activated_in_database_at=CURRENT_TIMESTAMP WHERE vineyard_key=%s""").format(
                self.name(POINTER)
            ),
            (
                record["pipeline_execution_id"],
                record["reconciliation_run_id"],
                record["vineyard_key"],
            ),
        )


# On vérifie la cohérence du lot NAS avec les informations Excel déjà conservées.
def verify_excel(bundle, repo):
    # On reprend les métadonnées de la publication dans bundle ; cet accès suppose que la clé a été
    # produite ou vérifiée auparavant.
    pub = bundle["publication"]
    # On garde dans wanted un nouveau dictionnaire construit avec les valeurs indiquées.
    wanted = dict(
        # On fournit l’identifiant de la publication Excel via le paramètre publication_id de cet
        # appel.
        publication_id=pub["publication_id"],
        # On fournit l’empreinte du tableau Excel regroupé via le paramètre reference_sha256 de cet
        # appel.
        reference_sha256=pub["reference"]["sha256"],
        # On fournit le nombre de lignes du tableau regroupé via le paramètre reference_rows de cet
        # appel.
        reference_rows=pub["reference"]["rows"],
        # On fournit le chemin du tableau Excel regroupé via le paramètre reference_path de cet appel.
        reference_path=pub["reference"]["path"],
        # On fournit le chemin du manifeste via le paramètre manifest_path de cet appel.
        manifest_path=bundle["pub_path"],
        # On fournit l’empreinte du manifeste via le paramètre manifest_sha256 de cet appel.
        manifest_sha256=sha256(bundle["files"].read(bundle["pub_path"])),
        # On fournit le contenu du manifeste via le paramètre manifest_payload de cet appel.
        manifest_payload=pub,
    )
    # On appelle equal_records avec repo.read('core.excel_publications', tuple(wanted),
    # {'publication_id': pub['publication_i….
    equal_records(
        repo.read(
            "core.excel_publications",
            tuple(wanted),
            {"publication_id": pub["publication_id"]},
        ),
        [wanted],
        ("publication_id",),
        "publication Excel deja importee",
    )
    # Comparer toute la reference publiee en base, pas seulement ses compteurs.
    wanted_rows = [
        dict(publication_id=pub["publication_id"], row_ordinal=i, payload=payload(row))
        for i, row in enumerate(bundle["reference"], 1)
    ]
    # On appelle equal_records avec repo.read('staging.excel_publication_rows', ('publication_id',
    # 'row_ordinal', 'payload'),….
    equal_records(
        repo.read(
            "staging.excel_publication_rows",
            ("publication_id", "row_ordinal", "payload"),
            {"publication_id": pub["publication_id"]},
        ),
        wanted_rows,
        ("publication_id", "row_ordinal"),
        "lignes de reference Excel",
    )
    # Les membres de la publication doivent etre exactement ceux du manifeste.
    members = [
        dict(
            # On fournit l’identifiant de la publication Excel via le paramètre publication_id de cet
            # appel.
            publication_id=pub["publication_id"],
            # On fournit la clé du domaine via le paramètre vineyard_key de cet appel.
            vineyard_key=key,
            # On fournit l’identifiant de version via le paramètre version_id de cet appel.
            version_id=entry["version_id"],
        )
        for key, entry in pub["versions"].items()
    ]
    # On appelle equal_records avec repo.read('core.excel_publication_versions', ('publication_id',
    # 'vineyard_key', 'version_….
    equal_records(
        repo.read(
            "core.excel_publication_versions",
            ("publication_id", "vineyard_key", "version_id"),
            {"publication_id": pub["publication_id"]},
        ),
        members,
        ("publication_id", "vineyard_key"),
        "versions de publication Excel",
    )
    # On parcourt bundle['pointers'] ; pointer désigne l’élément courant à chaque passage dans la
    # boucle.
    for pointer in bundle["pointers"]:
        # On récupère la clé du domaine dans pointer et on le garde dans key pour la suite.
        key = pointer["vineyard_key"]
        # On sélectionne dans pub['versions'] les éléments désignés par key ; entry recevra cette
        # sélection.
        entry = pub["versions"][key]
        # On garde dans wanted un nouveau dictionnaire construit avec les valeurs indiquées.
        wanted = dict(
            # On fournit la clé du domaine via le paramètre vineyard_key de cet appel.
            vineyard_key=key,
            # On fournit l’identifiant de version via le paramètre version_id de cet appel.
            version_id=entry["version_id"],
            # On fournit la date d’ingestion via le paramètre ingested_at de cet appel.
            ingested_at=timestamp(entry["ingested_at"]),
            # On fournit le nom du fichier source via le paramètre source_filename de cet appel.
            source_filename=entry["source_filename"],
            # On fournit l’empreinte du fichier source via le paramètre source_sha256 de cet appel.
            source_sha256=entry["source_sha256"],
        )
        # On parcourt [('identity', 'identity'), ('manifest_sha256', 'version_manifest_sha256')] ;
        # (source, dest) désigne l’élément courant à chaque passage dans la boucle.
        for source, dest in [
            ("identity", "identity"),
            ("manifest_sha256", "version_manifest_sha256"),
        ]:
            # On vérifie ce cas avant la suite : la source appartient à entry.
            if source in entry:
                # On sélectionne dans entry les éléments désignés par source ; wanted[dest] recevra
                # cette sélection.
                wanted[dest] = entry[source]
        # On appelle equal_records avec repo.read('core.excel_versions', tuple(wanted),
        # {'vineyard_key': key, 'version_id': entry….
        equal_records(
            repo.read(
                "core.excel_versions",
                tuple(wanted),
                {"vineyard_key": key, "version_id": entry["version_id"]},
            ),
            [wanted],
            ("vineyard_key", "version_id"),
            "version Excel " + key,
        )


# On gère le lien vers le résultat à consulter actuellement, sans assimiler ce lien à tout
# l’historique.
def activate(bundle, repo, pointer):
    # On récupère la clé du domaine dans pointer et on le garde dans key pour la suite.
    key = pointer["vineyard_key"]
    # On garde dans old le contenu lu depuis repo selon les paramètres fournis.
    old = repo.read(POINTER, tuple(pointer), {"vineyard_key": key})
    # Cette branche traite le cas où old est évalué comme vrai et old[0] correspond à pointer.
    if old and old[0] == pointer:
        # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
        return "inchange"
    # Cette branche traite le cas où old est évalué comme vrai.
    if old:

        # On compare les instants concernés pour refuser une chronologie incohérente.
        def chronology(p):
            # On indexe le résultat par k, avec p[k] comme valeur ; les contrôles d’unicité sont
            # importants car une même clé ne garde qu’une valeur dans un dictionnaire.
            filters = {
                k: p[k]
                for k in (
                    "pipeline_execution_id",
                    "vineyard_key",
                    "reconciliation_run_id",
                )
            }
            # On garde dans rows le contenu lu depuis repo selon les paramètres fournis.
            rows = repo.read(
                "core.reconciliation_runs",
                ("nas_pipeline_execution_id", "excel_version_id", "reconciled_at"),
                filters,
            )
            # On exige ici que len(rows) correspond à 1. Si ce n’est pas le cas, le message associé
            # bloque la suite.
            require(len(rows) == 1, "Pointeur courant sans rapprochement : " + key)
            # On récupère rows[0] et on le garde dans rec pour la suite.
            rec = rows[0]
            # On garde dans obs le contenu lu depuis repo selon les paramètres fournis.
            obs = repo.read(
                "core.nas_observation_runs",
                ("checked_at",),
                {
                    # On renseigne l’identifiant du traitement NAS sous la clé 'pipeline_execution_id'.
                    "pipeline_execution_id": rec["nas_pipeline_execution_id"],
                    # On renseigne la clé du domaine sous la clé 'vineyard_key'.
                    "vineyard_key": key,
                },
            )
            # On garde dans version le contenu lu depuis repo selon les paramètres fournis.
            version = repo.read(
                "core.excel_versions",
                ("ingested_at",),
                {"vineyard_key": key, "version_id": rec["excel_version_id"]},
            )
            # On exige ici que le test len(obs) == len(version) == 1 est satisfait. Si ce n’est pas le
            # cas, le message associé bloque la suite.
            require(
                len(obs) == len(version) == 1,
                "Provenance du rapprochement courant incomplete : " + key,
            )
            # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les
            # décompose.
            return rec["reconciled_at"], obs[0]["checked_at"], version[0]["ingested_at"]

        # On distribue ces valeurs entre before, after, dans l’ordre de l’affectation. Chaque nom
        # reçoit son propre élément.
        before, after = chronology(old[0]), chronology(pointer)
        # On exige ici que after[0] est supérieur à before[0] et after[1] est au moins égal à before[1]
        # et after[2] est au moins égal à before[2]. Si ce n’est pas le cas, le message associé bloque
        # la suite.
        require(
            after[0] > before[0] and after[1] >= before[1] and after[2] >= before[2],
            "Activation refusee : dates anciennes ou ambiguës pour "
            + key
            + ". Aucun retour arriere automatique.",
        )
        # On remplace le lien vers le résultat courant à l’intérieur de la transaction ;
        # l’historique de ce qui a été chargé reste séparé de ce pointeur.
        repo.replace_pointer(pointer)
    else:
        # On appelle repo.insert avec POINTER.
        repo.insert(POINTER, tuple(pointer), [pointer])
    # On renvoie ce libellé explicite pour le cas qui vient d’être identifié.
    return "active"


# On charge le lot préparé au moyen du dépôt fourni ; ce n’est pas une nouvelle lecture des sources.
def import_bundle(bundle, repo):
    # On distribue ces valeurs entre inserted, reused, dans l’ordre de l’affectation. Chaque nom
    # reçoit son propre élément.
    inserted, reused = Counter(), Counter()
    # On récupère l’identifiant du traitement NAS dans bundle['report'] et on le garde dans execution
    # pour la suite.
    execution = bundle["report"]["pipeline_execution_id"]
    # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne couvre pas tout
    # le workflow.
    with repo.transaction():
        # On recontrôle les fichiers utilisés par le lot pour repérer un changement survenu depuis
        # sa préparation.
        check_files(bundle)
        # On vérifie le rattachement du lot NAS au lot Excel enregistré avant d’activer le
        # rapprochement.
        verify_excel(bundle, repo)
        # On garde dans existing le contenu lu depuis repo selon les paramètres fournis.
        existing = repo.read(
            "core.pipeline_runs",
            COLUMNS["core.pipeline_runs"],
            {"pipeline_execution_id": execution},
        )
        # On inverse la valeur de vérité de existing pour obtenir new.
        new = not existing
        # On parcourt les couples (table, columns) de COLUMNS : on garde ensemble la clé et sa
        # valeur au lieu des traiter dans deux listes séparées.
        for table, columns in COLUMNS.items():
            # On sélectionne dans bundle['records'] les éléments désignés par table ; rows recevra
            # cette sélection.
            rows = bundle["records"][table]
            # On garde dans existing le contenu lu depuis repo selon les paramètres fournis.
            existing = repo.read(table, columns, {"pipeline_execution_id": execution})
            # Cette branche traite le cas où new est évalué comme vrai.
            if new:
                # On exige ici que la condition existing n’est pas remplie. Si ce n’est pas le cas, le
                # message associé bloque la suite.
                require(
                    not existing,
                    "Donnees deja presentes sans execution parente : " + table,
                )
                # On appelle repo.insert avec table.
                repo.insert(table, columns, rows)
                # On garde dans inserted[table] le nombre d’éléments des lignes.
                inserted[table] = len(rows)
            else:
                # On appelle equal_records avec existing.
                equal_records(existing, rows, KEYS[table], table)
                # On garde dans reused[table] le nombre d’éléments des lignes.
                reused[table] = len(rows)
        # On indexe le résultat par p['vineyard_key'], avec activate(bundle, repo, p) comme valeur ;
        # les contrôles d’unicité sont importants car une même clé ne garde qu’une valeur dans un
        # dictionnaire.
        activations = {
            p["vineyard_key"]: activate(bundle, repo, p) for p in bundle["pointers"]
        }
        # On appelle check_files avec bundle.
        check_files(bundle)
    # On fournit à l’appelant un nouveau dictionnaire construit avec les valeurs indiquées.
    return dict(inserted=dict(inserted), reused=dict(reused), activations=activations)


def main(argv=None):
    # On parcourt (sys.stdout, sys.stderr) ; stream désigne l’élément courant à chaque passage dans la
    # boucle.
    for stream in (sys.stdout, sys.stderr):
        # Cette branche traite le cas où le contrôle hasattr(stream, 'reconfigure') est positif.
        if hasattr(stream, "reconfigure"):
            # On appelle stream.reconfigure sans argument positionnel.
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    # On garde dans parser le lecteur des options de cette commande.
    parser = argparse.ArgumentParser(
        description="Controle puis chargement transactionnel NAS/rapprochement, depuis des fichiers locaux."
    )
    # On déclare des options incompatibles entre elles : le parseur rejettera leur emploi simultané
    # avant le traitement.
    modes = parser.add_mutually_exclusive_group(required=True)
    # Option --check-only : Controle local ; aucune connexion PostgreSQL. Sa déclaration ne
    # déclenche pas l’action.
    modes.add_argument(
        "--check-only",
        action="store_true",
        help="Controle local ; aucune connexion PostgreSQL.",
    )
    # Option --load : Controle, import et activation par vignoble dans PostgreSQL. Sa déclaration ne
    # déclenche pas l’action.
    modes.add_argument(
        "--load",
        action="store_true",
        help="Controle, import et activation par vignoble dans PostgreSQL.",
    )
    # On appelle parser.add_argument avec '--manifest'.
    parser.add_argument("--manifest", required=True)
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On récupère les options du chargeur NAS ; seules les branches explicitement prévues pourront
    # importer le lot validé.
    args = parser.parse_args(argv)
    # On initialise password à None : aucune valeur n’a encore été retenue ici.
    password = None
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On prépare en mémoire le lot et ses contrôles à partir des sorties locales ; le chargement
        # PostgreSQL n’est pas effectué par cette seule préparation.
        bundle = prepare_bundle(args.project_root, args.manifest.replace("\\", "/"))
        # On récupère le bilan dans bundle et on le garde dans report pour la suite.
        report = bundle["report"]
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "📋 Controle local OK : "
            + report["pipeline_execution_id"]
            + " | publication Excel "
            + report["excel_publication_id"]
        )
        # On parcourt les domaines sélectionnés dans report ; v désigne l’élément courant à chaque
        # passage dans la boucle.
        for v in report["vineyards"]:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"{v['vineyard']} : {v['acquisitions']} acquisitions | {v['associations']} associations | {v['passages']} passages distincts"
            )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"  A verifier : {v['acquisition_candidates']} acquisitions | sorties non verifiables : {v['not_verifiable']} acquisitions"
            )
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "  Non verifiable ne signifie pas absent. Aucun nouveau calcul de classification."
            )
        # Cette branche traite le cas où le test args.check_only est satisfait.
        if args.check_only:
            # On affiche ce texte explicite dans la sortie du programme.
            print(
                "🔒 PostgreSQL : aucune connexion, aucune ecriture. NAS : aucun acces."
            )
            # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
            # retour.
            return 0
        # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas
        # de connexion.
        import psycopg

        # On garde dans config les paramètres du compte PostgreSQL prévus par ce module.
        config = database_config(args.project_root)
        # On récupère config['password'] et on le garde dans password pour la suite.
        password = config["password"]
        # On utilise psycopg.connect(**config) dans son contexte de gestion ; les opérations de sortie
        # sont exécutées en quittant le bloc.
        with psycopg.connect(**config) as connection:
            # On garde dans actual une ligne du résultat de la requête, ou None si elle n’en renvoie
            # aucune.
            actual = connection.execute(
                "SELECT current_database(),current_user,session_user"
            ).fetchone()
            # On annule les écritures non validées dans cette transaction, sans prétendre annuler les
            # opérations déjà commises ailleurs.
            connection.rollback()
            # On appelle verify_import_identity avec actual.
            verify_import_identity(actual)
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                "Connexion de chargement : compte=projet12_importer | base=suivi_acquisitions"
            )
            # On garde dans result la valeur renvoyée par import_bundle.
            result = import_bundle(bundle, PostgresRepository(connection))
        # On affiche '✅ CHARGEMENT VALIDE : ' + report['pipeline_execution_id'] dans la sortie du
        # programme.
        print("✅ CHARGEMENT VALIDE : " + report["pipeline_execution_id"])
        # On parcourt COLUMNS ; table désigne l’élément courant à chaque passage dans la boucle.
        for table in COLUMNS:
            # On affiche cette information de suivi dans la sortie du programme.
            print(
                f"{table} : {result['inserted'].get(table, 0)} nouveaux | {result['reused'].get(table, 0)} deja presents et verifies"
            )
        # On parcourt les couples (key, status) de result['activations'] : on garde ensemble la clé
        # et sa valeur au lieu des traiter dans deux listes séparées.
        for key, status in result["activations"].items():
            # On affiche 'Rapprochement courant de ' + key + ' : ' + status dans la sortie du
            # programme.
            print("Rapprochement courant de " + key + " : " + status)
        # On affiche ce texte explicite dans la sortie du programme.
        print("Archives et registre local : aucune modification. NAS : aucun acces.")
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Historique conserve ; critere technique positif distinct de livraison client."
        )
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as exc:
        # On garde dans message la représentation textuelle de exc.
        message = str(exc)
        # Cette branche traite le cas où password est évalué comme vrai.
        if password:
            # On garde dans message le résultat du remplacement demandé sur message.
            message = message.replace(password, "[secret masque]")
        # On affiche 'CHARGEMENT NON CONFIRME : ' + message dans la sortie du programme.
        print("CHARGEMENT NON CONFIRME : " + message, file=sys.stderr)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Une erreur avant COMMIT annule la transaction. Si la connexion est perdue pendant COMMIT, verifier la base avant de conclure.",
            file=sys.stderr,
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Aucun historique supprime ou repare automatiquement ; une relance verifie les donnees existantes.",
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
