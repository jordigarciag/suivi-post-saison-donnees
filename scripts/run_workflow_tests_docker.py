# Lecture du fichier — Essais du workflow, des chargeurs et du journal dans l’environnement SQL de test.
# On vérifie les écritures et certains incidents dans une installation isolée. Les fichiers Compose
# de test dédiés ne sont pas tous fournis dans cette copie.
#

"""Workflow+chargeurs+journal SQL reels, dans le serveur Docker de TEST seulement.
Aucune ingestion Excel reelle, aucune extraction NAS, aucune connexion Airflow.
"""

# On importe argparse. On décrit les options de la commande et on contrôle leur forme.
import argparse
# On rend disponibles contextmanager depuis contextlib, pour les appels de ce fichier.
from contextlib import contextmanager
# On rend disponibles datetime, timezone depuis datetime, pour les appels de ce fichier.
from datetime import datetime, timezone
# On calcule des empreintes de contenu pour détecter les différences ; ce ne sont pas des mots de
# passe chiffrés.
import hashlib
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On importe re. On reconnaît ou transforme des motifs de texte avec les expressions régulières.
import re
# On importe shutil. On réalise les copies et nettoyages de fichiers explicitement prévus.
import shutil
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles uuid4 depuis uuid, pour les appels de ce fichier.
from uuid import uuid4

# On rend disponibles make_test_configs, load_schema_sources, verify_management_identity, ADMIN depuis
# run_importer_tests_docker, pour les appels de ce fichier.
from run_importer_tests_docker import (
    make_test_configs,
    load_schema_sources,
    verify_management_identity,
    ADMIN,
)
# On rend disponibles build_bundles depuis synthetic_import_fixtures, pour les appels de ce fichier.
from synthetic_import_fixtures import build_bundles
# On rend disponibles IMPORT_TABLES, PREFIX, guard_test_database, snapshot, histories_preserved,
# require depuis test_importer_postgres_integration, pour les appels de ce fichier.
from test_importer_postgres_integration import (
    IMPORT_TABLES,
    PREFIX,
    guard_test_database,
    snapshot,
    histories_preserved,
    require,
)
# On rend disponibles run_workflow, read_events, replay_events depuis workflow_runtime, pour les appels
# de ce fichier.
from workflow_runtime import run_workflow, read_events, replay_events
# On rend disponibles build_excel_steps, assert_excel_snapshot depuis workflow_excel_adapter, pour les
# appels de ce fichier.
from workflow_excel_adapter import build_excel_steps, assert_excel_snapshot
# On rend disponibles PipelineAttempt, assert_nas_snapshot depuis workflow_nas_adapter, pour les appels
# de ce fichier.
from workflow_nas_adapter import PipelineAttempt, assert_nas_snapshot
# On rend disponibles connection_scope, repository_scope, build_import_steps, build_journal_sink depuis
# workflow_postgres_adapter, pour les appels de ce fichier.
from workflow_postgres_adapter import (
    connection_scope,
    repository_scope,
    build_import_steps,
    build_journal_sink,
)
# On rend disponibles COLUMNS, normalize_event, append_event depuis workflow_journal_repository, pour
# les appels de ce fichier.
from workflow_journal_repository import COLUMNS, normalize_event, append_event

# On garde dans RESULTS_DIR un objet chemin local ; sa construction seule ne prouve pas que le fichier
# existe.
RESULTS_DIR = Path("/opt/test-results")


def journal_table_source(source):
    """Extrait seulement table/index de SQL 023 ; ni garde metier ni vues/grants globaux."""
    # On garde dans start la valeur renvoyée par source.find pour 'CREATE TABLE
    # core.workflow_execution_events ('.
    start = source.find("CREATE TABLE core.workflow_execution_events (")
    # On garde dans end la valeur renvoyée par source.find pour 'COMMENT ON TABLE
    # core.workflow_execution_event….
    end = source.find("COMMENT ON TABLE core.workflow_execution_events", start)
    # On exige ici que start est au moins égal à 0 et end est supérieur à start. Si ce n’est pas le
    # cas, le message associé bloque la suite.
    require(start >= 0 and end > start, "Structure attendue du journal absente.")
    # On garde dans ddl la portion de la source sélectionnée par start:end ; les bornes de fin sont
    # exclues.
    ddl = source[start:end]
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        re.findall(r"CREATE\s+TABLE\s+([a-z_.]+)", ddl, re.I)
        == ["core.workflow_execution_events"]
        # On exige aussi que le texte 'UNIQUE (workflow_execution_id,event_sequence)' appartient à ddl.
        and "UNIQUE (workflow_execution_id,event_sequence)" in ddl
        # On exige aussi que le texte 'duration_seconds numeric' appartient à ddl.
        and "duration_seconds numeric" in ddl
        # On exige aussi que la condition
        # re.search('\\b(GRANT|REVOKE|DROP|ALTER|DO|BEGIN|COMMIT|CREATE\\s+ROLE)\\b', ddl, re.I) n’est
        # pas remplie.
        and not re.search(
            r"\b(GRANT|REVOKE|DROP|ALTER|DO|BEGIN|COMMIT|CREATE\s+ROLE)\b", ddl, re.I
        ),
        "Structure du journal non reconnue : aucune preparation autorisee.",
    )
    # On remet ddl à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return ddl


def load_sources(root):
    # On garde dans sources la valeur renvoyée par load_schema_sources.
    sources = load_schema_sources(root)
    # On garde dans ddl la valeur renvoyée par journal_table_source.
    ddl = journal_table_source(
        (Path(root) / "sql/023_create_workflow_execution_journal.sql").read_text(
            # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
            # décodé selon un réglage implicite du poste.
            encoding="utf-8-sig"
        )
    )
    # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return sources, ddl


def prepare_fixture_roots(fixtures, bundles):
    """Copier uniquement les artefacts NAS ; jamais remplacer un manifeste Excel."""
    # On prépare roots comme liste vide ; on la remplira au fil des opérations suivantes.
    roots = []
    # On parcourt ((0, 2), (1, 3)) ; (index, nas_index) désigne l’élément courant à chaque passage dans
    # la boucle.
    for index, nas_index in ((0, 2), (1, 3)):
        # On garde dans root le chemin absolu résolu de fixtures[index].root, en tenant compte des
        # liens symboliques.
        root = fixtures[index].root.resolve()
        # On sélectionne dans fixtures les éléments désignés par nas_index ; nf recevra cette
        # sélection.
        nf = fixtures[nas_index]
        # On sélectionne dans bundles les éléments désignés par 1 if index == 0 else 3 ; bundle recevra
        # cette sélection.
        bundle = bundles[1 if index == 0 else 3]
        # On rassemble dans paths les 2 éléments explicitement indiqués, en conservant leur structure.
        paths = [nf.manifest_path, bundle["manifest"]["reference_snapshot"]]
        # On ajoute [item['path'] for item in bundle['report']['artifacts']] à paths et on conserve ce
        # nouvel état pour la suite.
        paths += [item["path"] for item in bundle["report"]["artifacts"]]
        # On parcourt paths ; relative désigne l’élément courant à chaque passage dans la boucle.
        for relative in paths:
            # On garde dans source le chemin absolu résolu de nf.root / relative, en tenant compte des
            # liens symboliques.
            source = (nf.root / relative).resolve()
            # On garde dans target le chemin absolu résolu de root / relative, en tenant compte des
            # liens symboliques.
            target = (root / relative).resolve()
            # Ce contrôle porte sur la destination résolue ; un chemin textuellement situé sous le
            # projet pourrait encore pointer ailleurs par un lien symbolique.
            require(
                source.is_relative_to(nf.root.resolve())
                # On exige aussi que la destination reste sous root / 'data'.
                and target.is_relative_to(root / "data"),
                "Artefact synthetique hors du repertoire autorise.",
            )
            # On exige ici que la condition target.exists() n’est pas remplie. Si ce n’est pas le cas,
            # le message associé bloque la suite.
            require(
                not target.exists(), "Ne pas remplacer un fichier de fixture existant."
            )
            # On prépare le dossier local nécessaire à cette sortie ; créer le dossier ne produit
            # pas encore le fichier qu’il contiendra.
            target.parent.mkdir(parents=True, exist_ok=True)
            # On appelle shutil.copyfile avec source.
            shutil.copyfile(source, target)
        # On ajoute (root, nf.manifest_path) à la fin de roots ; les éléments précédents restent
        # conservés.
        roots.append((root, nf.manifest_path))
    # On remet roots à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return roots


def prepared_steps(root, manifest_relative):
    """Entree de TEST : lots fictifs deja produits. Ne simule pas une observation nouvelle."""
    # On importe import_excel_publication sous le nom excel. Ce module sera utilisé par les opérations
    # de ce fichier.
    import import_excel_publication as excel
    # On importe load_nas_reconciliation sous le nom nas. Ce module sera utilisé par les opérations de
    # ce fichier.
    import load_nas_reconciliation as nas

    # On garde dans initial le lot préparé et contrôlé par le module appelé.
    initial = excel.prepare_bundle(root)
    # On reprend les métadonnées de la publication dans initial ; cet accès suppose que la clé a été
    # produite ou vérifiée auparavant.
    publication = initial["publication"]
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
    # On prépare pour eg une fonction courte ; elle ne sera exécutée que lorsqu’elle sera appelée, pas
    # lors de cette affectation.
    eg = lambda ctx: assert_excel_snapshot(
        # On fournit la vérification de stabilité du lot, réutilisable avant ses consommateurs.
        ctx, ensure_current=excel.check_still_current
    )
    # On prépare pour ng une fonction courte ; elle ne sera exécutée que lorsqu’elle sera appelée, pas
    # lors de cette affectation.
    ng = lambda ctx: assert_nas_snapshot(
        # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
        ctx, ensure_excel=eg, ensure_nas=nas.check_files
    )
    # On construit les fonctions des étapes Excel avec leurs dépendances ; la construction ne
    # déclenche pas encore ces étapes.
    steps = build_excel_steps(
        root,
        # On transmet la sélection explicite des domaines concernés par cet appel.
        vineyards=["DomaineDemoB"],
        ingest=lambda *a, **k: outcome,
        prepare=excel.prepare_bundle,
        # On fournit la vérification de stabilité du lot, réutilisable avant ses consommateurs.
        ensure_current=excel.check_still_current,
    )

    def bind(ctx):
        # On appelle eg avec ctx.
        eg(ctx)
        # On garde dans bundle le lot préparé et contrôlé par le module appelé.
        bundle = nas.prepare_bundle(root, manifest_relative)
        # On calcule ce quotient pour construire manifest_path.
        manifest_path = root / manifest_relative
        # On exige ici que la publication Excel dans bundle correspond à la publication Excel dans
        # ctx.results['excel_publication_check']. Si ce n’est pas le cas, le message associé bloque la
        # suite.
        require(
            bundle["publication"]
            == ctx.results["excel_publication_check"]["publication"],
            "Publication du lot NAS differente de la reference Excel.",
        )
        # On récupère l’identifiant du traitement NAS dans bundle['report'] et on le garde dans
        # execution pour la suite.
        execution = bundle["report"]["pipeline_execution_id"]
        # On rattache le contexte à ce lot pour empêcher un changement silencieux d’identifiant en
        # cours de traitement.
        ctx.pin_ids(pipeline_execution_id=execution)
        # On fournit à l’appelant la valeur renvoyée par PipelineAttempt.
        return PipelineAttempt(
            execution,
            manifest_path,
            manifest_relative,
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            ("DomaineDemoB",),
            2026,
        )

    def check(ctx):
        # On appelle eg avec ctx.
        eg(ctx)
        # On fournit à l’appelant le lot préparé et contrôlé par le module appelé.
        return nas.prepare_bundle(root, manifest_relative)

    # On ajoute [('nas_pipeline_execute', bind), ('nas_bundle_check', check)] à steps et on conserve ce
    # nouvel état pour la suite.
    steps += [("nas_pipeline_execute", bind), ("nas_bundle_check", check)]
    # On renvoie ces 3 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
    return steps, eg, ng


def archive_result(root, result, destination):
    # On garde dans source le chemin absolu résolu de root / result['journal_relative_path'], en tenant
    # compte des liens symboliques.
    source = (root / result["journal_relative_path"]).resolve()
    # Ce contrôle porte sur la destination résolue ; un chemin textuellement situé sous le projet
    # pourrait encore pointer ailleurs par un lien symbolique.
    require(
        source.is_relative_to(root.resolve() / "data/03_normalized/workflow_runs"),
        "Journal hors fixture.",
    )
    # On construit folder en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    folder = Path(destination) / result["workflow_execution_id"]
    # On crée ce dossier en refusant un emplacement déjà existant ; cela évite de réutiliser
    # silencieusement les sorties d’un ancien essai.
    folder.mkdir(parents=True, exist_ok=False)
    # On construit target en assemblant les morceaux du chemin. L’opérateur / de pathlib ne crée ni
    # dossier ni fichier.
    target = folder / "events.jsonl"
    # On appelle shutil.copyfile avec source.
    shutil.copyfile(source, target)
    # On écrit le texte préparé avec l’encodage indiqué ; cette opération remplace le contenu de ce
    # fichier.
    (folder / "result.json").write_text(
        # On utilise cet encodage pour lire ou écrire le texte ; le même contenu ne doit pas être
        # décodé selon un réglage implicite du poste.
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # On remet la destination à l’appelant ; les étapes suivantes de cette fonction ne sont plus
    # parcourues.
    return target


def verify_journal(connection, result, path):
    # On garde dans events les événements du journal local après validation de leur ordre et de leur
    # identité.
    events = read_events(path)
    # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
    # présenter.
    rows = connection.execute(
        "SELECT "
        + ",".join(COLUMNS)
        + " FROM core.workflow_execution_events WHERE workflow_execution_id=%s ORDER BY event_sequence",
        (result["workflow_execution_id"],),
    ).fetchall()
    # On exige ici que [dict(zip(COLUMNS, row)) for row in rows] correspond à [normalize_event(e) for e
    # in events]. Si ce n’est pas le cas, le message associé bloque la suite.
    require(
        [dict(zip(COLUMNS, row)) for row in rows]
        == [normalize_event(e) for e in events],
        "Evenements SQL differents du journal local (UUID, dates, contenu ou sequence).",
    )


def journal_state(c):
    # On récupère toutes les lignes du résultat SQL en mémoire avant des comparer ou de les
    # présenter.
    return c.execute(
        "SELECT event_id,recorded_in_database_at FROM core.workflow_execution_events ORDER BY workflow_execution_id,event_sequence"
    ).fetchall()


def run_checks(root, roots, opened, destination):
    # On importe import_excel_publication sous le nom excel. Ce module sera utilisé par les opérations
    # de ce fichier.
    import import_excel_publication as excel
    # On importe load_nas_reconciliation sous le nom nas. Ce module sera utilisé par les opérations de
    # ce fichier.
    import load_nas_reconciliation as nas
    # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas de
    # connexion.
    import psycopg

    # On garde dans destination un objet chemin local ; sa construction seule ne prouve pas que le
    # fichier existe.
    destination = Path(destination)
    # On crée ce dossier en refusant un emplacement déjà existant ; cela évite de réutiliser
    # silencieusement les sorties d’un ancien essai.
    destination.mkdir(parents=True, exist_ok=False)
    # On prépare la fonction qui écrira les événements du workflow dans le journal de la base
    # métier, distinct de la base technique Airflow.
    sink = build_journal_sink(root, opened=opened)
    # On prépare results comme liste vide ; on la remplira au fil des opérations suivantes.
    results = []

    def run(index, *, failing_nas=False, failing_journal=False):
        # On sélectionne dans roots les éléments désignés par index ; (workspace, relative) recevra
        # cette sélection.
        workspace, relative = roots[index]
        # On répartit les valeurs renvoyées par prepared_steps entre (steps, eg, ng) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        steps, eg, ng = prepared_steps(workspace, relative)
        # On prépare l’accès au repository demandé avec sa connexion encadrée ; ce n’est pas encore
        # un chargement de lignes.
        er = repository_scope(root, opened, "excel")
        # On garde dans nr le cadre d’accès au repository demandé pour le chargement.
        nr = repository_scope(root, opened, "nas")
        # Cette branche traite le cas où failing_nas est évalué comme vrai.
        if failing_nas:

            class FailingRepository(nas.PostgresRepository):
                # On change le lien courant selon le contrat de ce dépôt ; les anciennes observations
                # restent distinctes.
                def replace_pointer(self, record):
                    # On remplace le lien vers le résultat courant à l’intérieur de la transaction ;
                    # l’historique de ce qui a été chargé reste séparé de ce pointeur.
                    super().replace_pointer(record)
                    # On interrompt cette branche avec RuntimeError : 'Echec synthetique apres UPDATE
                    # avant COMMIT'.
                    raise RuntimeError("Echec synthetique apres UPDATE avant COMMIT")

            @contextmanager
            def nr():
                # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont
                # exécutées en quittant le bloc.
                with opened() as c:
                    # On fournit cette valeur à l’appelant et on suspend la fonction ici ; elle
                    # reprendra après ce point si son itération continue.
                    yield FailingRepository(c)

        # On ajoute build_import_steps(workspace, excel_repository=er, nas_repository=nr,
        # import_excel=e… à steps et on conserve ce nouvel état pour la suite.
        steps += build_import_steps(
            workspace,
            excel_repository=er,
            nas_repository=nr,
            import_excel=excel.import_bundle,
            import_nas=nas.import_bundle,
            # On fournit le garde-fou qui recontrôle le lot Excel retenu pour ce run.
            ensure_excel=eg,
            # On fournit le garde-fou qui recontrôle le lot NAS et son rattachement.
            ensure_nas=ng,
        )

        def interrupted_sink(event):
            # Cette branche traite le cas où l’étape concernée dans event correspond au texte
            # 'excel_import' et l’état du traitement dans event correspond au texte 'success'.
            if event["stage"] == "excel_import" and event["status"] == "success":
                # On interrompt cette branche avec RuntimeError : 'Panne synthetique du transport du
                # journal'.
                raise RuntimeError("Panne synthetique du transport du journal")
            # On fournit à l’appelant la valeur renvoyée par sink.
            return sink(event)

        # On lance les étapes assemblées avec le même contexte et leur journal ; le moteur ne
        # fournit pas de transaction globale couvrant tout le parcours.
        result = run_workflow(
            workspace,
            steps,
            # On fournit l’origine du déclenchement via le paramètre trigger_mode de cet appel.
            trigger_mode="integration_test",
            # On fournit le périmètre du traitement via le paramètre scope de cet appel.
            scope={"year": 2026, "vineyards": ["DomaineDemoB"], "synthetic": True},
            # On fournit le destinataire des événements du workflow ; ce n’est pas la base technique
            # des runs Airflow.
            journal_sink=interrupted_sink if failing_journal else sink,
        )
        # On garde dans archived la valeur renvoyée par archive_result.
        archived = archive_result(workspace, result, destination)
        # On ajoute (result, archived) à la fin de results ; les éléments précédents restent conservés.
        results.append((result, archived))
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return result, archived

    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On exige ici que tous les éléments satisfont le test indiqué et la condition journal_state(c)
        # n’est pas remplie. Si ce n’est pas le cas, le message associé bloque la suite.
        require(
            all(not rows for rows in snapshot(c, IMPORT_TABLES).values())
            # On exige aussi que la condition journal_state(c) n’est pas remplie.
            and not journal_state(c),
            "Base neuve non vide.",
        )
    # On répartit les valeurs renvoyées par run entre (first, path) ; leur ordre doit correspondre à
    # celui prévu par cet appel.
    first, path = run(0)
    # On exige ici que l’état du traitement dans first correspond au texte 'success'. Si ce n’est pas
    # le cas, le message associé bloque la suite.
    require(first["status"] == "success", "Premier workflow non confirme.")
    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On photographie l’état de test avant l’opération afin de pouvoir vérifier ensuite ce qui a
        # changé et ce qui doit rester identique.
        baseline = snapshot(c, IMPORT_TABLES)
        # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            all(baseline[t] for t in ("core.excel_publications", "core.pipeline_runs")),
            "Imports absents.",
        )
        # On contrôle les événements du journal enregistré, pas seulement la présence d’un message
        # de réussite dans la console.
        verify_journal(c, first, path)
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 1/8 : workflow synthetique ; imports Excel/NAS et journal SQL concordent."
    )

    # On répartit les valeurs renvoyées par run entre (repeated, path) ; leur ordre doit correspondre à
    # celui prévu par cet appel.
    repeated, path = run(0)
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        repeated["status"] == "success"
        # On exige aussi que l’identifiant de l’exécution du workflow dans repeated diffère de
        # l’identifiant de l’exécution du workflow dans first.
        and repeated["workflow_execution_id"] != first["workflow_execution_id"],
        "Nouvelle tentative non distinguee.",
    )
    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On exige ici que snapshot(c, IMPORT_TABLES) correspond à baseline. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            snapshot(c, IMPORT_TABLES) == baseline,
            "Relance metier avec doublon ou redatation.",
        )
        # On appelle verify_journal avec c.
        verify_journal(c, repeated, path)
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 2/8 : nouvelle tentative tracee ; memes lots sans doublon ni redatation metier."
    )

    # On répartit les valeurs renvoyées par run entre (failed, path) ; leur ordre doit correspondre à
    # celui prévu par cet appel.
    failed, path = run(1, failing_nas=True)
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        failed["status"] == "failed"
        # On exige aussi que le texte 'excel_import' appartient aux étapes terminées dans failed.
        and "excel_import" in failed["completed_steps"]
        # On exige aussi que le texte 'nas_import' ne figure pas dans les étapes terminées dans failed.
        and "nas_import" not in failed["completed_steps"],
        "Succes partiel non reconnu.",
    )
    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On garde dans after l’état photographié pour les comparaisons de cet essai.
        after = snapshot(c, IMPORT_TABLES)
        # On appelle histories_preserved avec baseline.
        histories_preserved(baseline, after)
        # On exige ici que c.execute('SELECT publication_id FROM core.excel_current_publication').fe…
        # correspond à l’identifiant du lot Excel dans failed. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(
            c.execute(
                "SELECT publication_id FROM core.excel_current_publication"
            ).fetchone()[0]
            == failed["excel_publication_id"],
            "Excel deja commis non conserve.",
        )
        # On assemble ces deux éléments pour construire nas_tables.
        nas_tables = tuple(nas.COLUMNS) + (nas.POINTER,)
        # On exige ici que tous les éléments satisfont le test indiqué. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            all(after[t] == baseline[t] for t in nas_tables),
            "Rollback du chargement NAS incomplet.",
        )
    # Les clotures d'echec du socle sont locales : retransmission explicite avant comparaison.
    replay_events(path, sink)
    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On appelle verify_journal avec c.
        verify_journal(c, failed, path)
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 3/8 : echec NAS APRES UPDATE ; transaction NAS annulee, Excel conserve, echec journalise apres rejeu."
    )

    # On répartit les valeurs renvoyées par run entre (second, path) ; leur ordre doit correspondre à
    # celui prévu par cet appel.
    second, path = run(1)
    # On exige ici que l’état du traitement dans second correspond au texte 'success'. Si ce n’est
    # pas le cas, le message associé bloque la suite.
    require(second["status"] == "success", "Deuxieme generation non chargee.")
    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On garde dans current l’état photographié pour les comparaisons de cet essai.
        current = snapshot(c, IMPORT_TABLES)
        # On appelle histories_preserved avec baseline.
        histories_preserved(baseline, current)
        # On exige ici que c.execute('SELECT pipeline_execution_id FROM core.current_vineyard_reconc…
        # correspond à l’identifiant du traitement NAS dans second. Si ce n’est pas le cas, le message
        # associé bloque la suite.
        require(
            c.execute(
                "SELECT pipeline_execution_id FROM core.current_vineyard_reconciliations"
            ).fetchone()[0]
            == second["pipeline_execution_id"],
            "Pointeur NAS non active.",
        )
        # On appelle verify_journal avec c.
        verify_journal(c, second, path)
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 4/8 : nouvelle tentative reussie ; seconde generation activee et historiques conserves."
    )

    # On répartit les valeurs renvoyées par run entre (lost, path) ; leur ordre doit correspondre à
    # celui prévu par cet appel.
    lost, path = run(1, failing_journal=True)
    # On exige ici que toutes les conditions regroupées ici sont remplies. Si ce n’est pas le cas, le
    # message associé bloque la suite.
    require(
        lost["error_code"] == "JOURNAL_DELIVERY_UNCONFIRMED"
        # On exige aussi que le texte 'excel_import' appartient aux étapes terminées dans lost.
        and "excel_import" in lost["completed_steps"]
        # On exige aussi que le texte 'nas_import' ne figure pas dans les étapes terminées dans lost.
        and "nas_import" not in lost["completed_steps"],
        "Panne de journal mal representee.",
    )
    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On exige ici que snapshot(c, IMPORT_TABLES) correspond à current. Si ce n’est pas le cas, le
        # message associé bloque la suite.
        require(
            snapshot(c, IMPORT_TABLES) == current,
            "Panne de journal a modifie un historique metier.",
        )
        # On récupère c.execute('SELECT COUNT(*) FROM core.workflow_execution_events WHERE work… et on
        # le garde dans prefix pour la suite.
        prefix = c.execute(
            "SELECT COUNT(*) FROM core.workflow_execution_events WHERE workflow_execution_id=%s",
            (lost["workflow_execution_id"],),
        ).fetchone()[0]
        # On exige ici que le test 0 < prefix < len(read_events(path)) est satisfait. Si ce n’est pas
        # le cas, le message associé bloque la suite.
        require(
            0 < prefix < len(read_events(path)),
            "Interruption du transport non provoquee.",
        )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 5/8 : panne de journal apres Excel ; suite arretee et evenements locaux conserves."
    )

    # On garde dans original les octets lus depuis path, avant toute conversion en texte. Les
    # contrôles de contenu pourront ainsi repartir de cette lecture.
    original = path.read_bytes()
    # On appelle replay_events avec path.
    replay_events(path, sink)
    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On appelle verify_journal avec c.
        verify_journal(c, lost, path)
        # On garde dans before la valeur renvoyée par journal_state.
        before = journal_state(c)
    # On appelle replay_events avec path.
    replay_events(path, sink)
    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On exige ici que journal_state(c) correspond à l’état relevé avant l’opération et
        # path.read_bytes() correspond à original. Si ce n’est pas le cas, le message associé bloque la
        # suite.
        require(
            journal_state(c) == before and path.read_bytes() == original,
            "Rejeu avec doublon, redatation ou modification du fichier.",
        )
        # On appelle verify_journal avec c.
        verify_journal(c, lost, path)
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 6/8 : rejeu deux fois ; memes UUID/dates, pas de doublon ni redatation SQL."
    )

    # On garde dans bad un nouveau dictionnaire construit avec les valeurs indiquées (la copie reste
    # superficielle).
    bad = dict(read_events(path)[0], message="Contradiction synthetique")
    # On tente ce bloc et on traite séparément les erreurs prévues : ValueError.
    try:
        # On appelle sink avec bad.
        sink(bad)
    except ValueError:
        # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
        pass
    else:
        # On interrompt cette branche avec ValueError : 'Contradiction du journal acceptee.'.
        raise ValueError("Contradiction du journal acceptee.")
    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On exige ici que journal_state(c) correspond à l’état relevé avant l’opération. Si ce n’est
        # pas le cas, le message associé bloque la suite.
        require(journal_state(c) == before, "Contradiction a modifie le journal.")
    # On affiche cette information de suivi dans la sortie du programme.
    print("OK 7/8 : evenement contradictoire refuse sans modification du journal.")

    # On utilise opened() dans son contexte de gestion ; les opérations de sortie sont exécutées en
    # quittant le bloc.
    with opened() as c:
        # On parcourt ('UPDATE core.workflow_execution_events SET message=message WHERE false',… ;
        # query désigne l’élément courant à chaque passage dans la boucle.
        for query in (
            "UPDATE core.workflow_execution_events SET message=message WHERE false",
            "DELETE FROM core.workflow_execution_events WHERE false",
        ):
            # On tente ce bloc et on traite séparément les erreurs prévues :
            # psycopg.errors.InsufficientPrivilege.
            try:
                # On regroupe ces opérations dans la transaction fournie par le dépôt ; cela ne
                # couvre pas tout le workflow.
                with c.transaction():
                    # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé
                    # séparément.
                    c.execute(query)
            except psycopg.errors.InsufficientPrivilege:
                # On n’ajoute pas d’action dans cette branche ; le parcours continue après ce bloc.
                pass
            else:
                # On interrompt cette branche avec ValueError : 'Permission de modification excessive
                # sur le journal.'.
                raise ValueError("Permission de modification excessive sur le journal.")
        # On exige ici que c.execute("SELECT has_table_privilege(current_user,'core.workflow_executi…
        # est exactement la valeur fausse (False). Si ce n’est pas le cas, le message associé bloque la
        # suite.
        require(
            c.execute(
                "SELECT has_table_privilege(current_user,'core.workflow_execution_events','TRUNCATE')"
            ).fetchone()[0]
            is False,
            "Droit TRUNCATE excessif.",
        )
        # On exige ici que journal_state(c) correspond à l’état relevé avant l’opération et snapshot(c,
        # IMPORT_TABLES) correspond à current. Si ce n’est pas le cas, le message associé bloque la
        # suite.
        require(
            journal_state(c) == before and snapshot(c, IMPORT_TABLES) == current,
            "Donnees modifiees pendant les essais de refus.",
        )
    # On affiche cette information de suivi dans la sortie du programme.
    print(
        "OK 8/8 : PostgreSQL refuse UPDATE/DELETE du journal ; droit TRUNCATE absent."
    )
    # On remet les résultats regroupés à l’appelant ; les étapes suivantes de cette fonction ne sont
    # plus parcourues.
    return results


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
    # On appelle parser.add_argument avec '--run'.
    parser.add_argument("--run", action="store_true", required=True)
    # On appelle parser.add_argument avec '--project-root'.
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    # On récupère les options des essais isolés du workflow ; ce lanceur doit rester rattaché aux
    # ressources de test.
    args = parser.parse_args(argv)
    # On distribue ces valeurs entre fixtures, created, name, dans l’ordre de l’affectation. Chaque
    # nom reçoit son propre élément.
    fixtures, created, name = [], False, None
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On répartit les valeurs renvoyées par make_test_configs entre (admin, importer) ; leur ordre
        # doit correspondre à celui prévu par cet appel.
        admin, importer = (
            make_test_configs()
        )  # Flag exact, host fixe, mots de passe FICTIFS.
        # On garde dans root le chemin absolu résolu de args.project_root, en tenant compte des liens
        # symboliques.
        root = args.project_root.resolve()
        # On répartit les valeurs renvoyées par load_sources entre (sources, journal) ; leur ordre doit
        # correspondre à celui prévu par cet appel.
        sources, journal = load_sources(root)  # Refus avant connexion si SQL inattendu.
        # On exige ici que RESULTS_DIR désigne un dossier. Si ce n’est pas le cas, le message associé
        # bloque la suite.
        require(
            RESULTS_DIR.is_dir(),
            "Dossier de resultats monte absent : ne pas lancer en dehors du service prevu.",
        )
        # On construit des lots synthétiques pour les essais ; ils ne proviennent pas des données de
        # l’entreprise.
        fixtures, bundles = build_bundles(root)
        # On garde dans roots la valeur renvoyée par prepare_fixture_roots.
        roots = prepare_fixture_roots(fixtures, bundles)
        # On parcourt roots ; (workspace, relative) désigne l’élément courant à chaque passage dans la
        # boucle.
        for workspace, relative in roots:
            # On appelle prepared_steps avec workspace.
            prepared_steps(workspace, relative)
        # Avant toute écriture d’essai, on vérifie qu’on vise la base et le compte de test attendus,
        # pas la base métier.
        name = guard_test_database(
            PREFIX
            + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            + "_"
            + uuid4().hex[:6]
        )
        # On importe psycopg. On utilise le pilote de connexion PostgreSQL ; l’import seul n’ouvre pas
        # de connexion.
        import psycopg
        # On rend disponibles sql depuis psycopg, pour les appels de ce fichier.
        from psycopg import sql

        # On utilise psycopg.connect(**admin, autocommit=True) dans son contexte de gestion ; les
        # opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(**admin, autocommit=True) as c:
            # On appelle verify_management_identity avec c.
            verify_management_identity(
                c
            )  # Compte admin de TEST et marqueur exact AVANT CREATE.
            # On exige ici que len(c.execute("SELECT rolname FROM pg_roles WHERE rolname IN
            # ('projet12_i… correspond à 2. Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                len(
                    c.execute(
                        "SELECT rolname FROM pg_roles WHERE rolname IN ('projet12_importer','projet12_import_writer')"
                    ).fetchall()
                )
                == 2,
                "Roles fictifs absents.",
            )
            # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé séparément.
            c.execute(
                sql.SQL("CREATE DATABASE {} WITH TEMPLATE template0 OWNER {}").format(
                    sql.Identifier(name), sql.Identifier(ADMIN)
                )
            )
            # On initialise created à True ; les branches suivantes pourront modifier cet état.
            created = True
            # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé séparément.
            c.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(name)
                )
            )
            # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé séparément.
            c.execute(
                sql.SQL(
                    "GRANT CONNECT ON DATABASE {} TO projet12_import_writer"
                ).format(sql.Identifier(name))
            )
        # On affiche 'Serveur Docker de TEST confirme ; nouvelle base : ' + name dans la sortie du
        # programme.
        print("Serveur Docker de TEST confirme ; nouvelle base : " + name)
        # On utilise psycopg.connect(**dict(admin, dbname=name), autocommit=True) dans son contexte de
        # gestion ; les opérations de sortie sont exécutées en quittant le bloc.
        with psycopg.connect(**dict(admin, dbname=name), autocommit=True) as c:
            # On exige ici que c.execute('SELECT
            # current_database(),current_user,session_user').fetchone… correspond à (name, ADMIN,
            # ADMIN). Si ce n’est pas le cas, le message associé bloque la suite.
            require(
                c.execute(
                    "SELECT current_database(),current_user,session_user"
                ).fetchone()
                == (name, ADMIN, ADMIN),
                "Destination de preparation incorrecte.",
            )
            # On parcourt ('core', 'staging') ; schema désigne l’élément courant à chaque passage dans
            # la boucle.
            for schema in ("core", "staging"):
                # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                c.execute(
                    sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(
                        sql.Identifier(schema), sql.Identifier(ADMIN)
                    )
                )
            # On parcourt (*sources, journal) ; source désigne l’élément courant à chaque passage dans
            # la boucle.
            for source in (*sources, journal):
                # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé
                # séparément.
                c.execute(source, prepare=False)
            # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé séparément.
            c.execute("GRANT USAGE ON SCHEMA core,staging TO projet12_import_writer")
            # On garde dans tables le texte formé en réunissant les éléments avec sql.SQL(',') comme
            # séparateur.
            tables = sql.SQL(",").join(
                sql.Identifier(*t.split("."))
                for t in (*IMPORT_TABLES, "core.workflow_execution_events")
            )
            # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé séparément.
            c.execute(
                sql.SQL("GRANT SELECT,INSERT ON {} TO projet12_import_writer").format(
                    tables
                )
            )
            # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé séparément.
            c.execute(
                "GRANT UPDATE(publication_id,activated_in_database_at) ON core.excel_current_publication TO projet12_import_writer"
            )
            # On envoie cette requête à c avec ses paramètres ; son résultat sera contrôlé séparément.
            c.execute(
                "GRANT UPDATE(pipeline_execution_id,reconciliation_run_id,activated_in_database_at) ON core.current_vineyard_reconciliations TO projet12_import_writer"
            )
        # On garde dans cfg un nouveau dictionnaire construit avec les valeurs indiquées (la copie
        # reste superficielle).
        cfg = dict(importer, dbname=guard_test_database(name))
        # On prépare le cadre d’ouverture et de vérification des connexions à la base indiquée.
        opened = connection_scope(lambda: psycopg.connect(**cfg, autocommit=True), name)
        # On appelle run_checks avec root.
        run_checks(root, roots, opened, RESULTS_DIR / name)
        # On affiche le bilan de ce contrôle ; le code de retour qui suit reste nécessaire pour un
        # appel depuis un autre outil.
        print(
            "RESULTAT : OK — 8 controles du workflow et du journal PostgreSQL isoles reussis."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Base metier, metadonnees Airflow et NAS : aucun acces. Extraction/ingestion reelles et DAG complet non testes."
        )
        # On affiche cette information de suivi dans la sortie du programme.
        print("Base de test conservee : " + name + " ; aucune suppression automatique.")
        # On affiche 'Journaux locaux conserves : logs/import_workflow_tests/' + name dans la sortie du
        # programme.
        print("Journaux locaux conserves : logs/import_workflow_tests/" + name)
        # On termine cette branche avec la valeur 0 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 0
    except Exception as exc:
        # Ne jamais imprimer les details de connexion ni une exception brute.
        print(
            "ESSAI NON CONFIRME : arreter et examiner les resultats de test ; aucun elargissement de droits.",
            file=sys.stderr,
        )
        # On garde dans code l’attribut 'sqlstate' de exc avec le repli indiqué s’il est absent.
        code = getattr(exc, "sqlstate", None)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Categorie : "
            + type(exc).__name__
            + (
                " ; SQLSTATE=" + code
                if isinstance(code, str) and re.fullmatch("[A-Z0-9]{5}", code)
                else ""
            ),
            file=sys.stderr,
        )
        # Cette branche traite le cas où created est évalué comme vrai.
        if created:
            # On affiche 'Base de test conservee pour diagnostic : ' + name dans la sortie du
            # programme.
            print("Base de test conservee pour diagnostic : " + name, file=sys.stderr)
        # On affiche cette information de suivi dans la sortie du programme.
        print(
            "Aucune suppression de base ou volume. Journaux deja produits conserves dans logs/import_workflow_tests.",
            file=sys.stderr,
        )
        # On termine cette branche avec la valeur 1 ; à la sortie d’un main, elle sert de code de
        # retour.
        return 1
    finally:
        # On parcourt reversed(fixtures) ; fixture désigne l’élément courant à chaque passage dans la
        # boucle.
        for fixture in reversed(fixtures):
            # On appelle fixture.doCleanups sans argument positionnel.
            fixture.doCleanups()


# On vérifie ce cas avant la suite : __name__ correspond au texte '__main__'.
if __name__ == "__main__":
    # On termine ce programme avec le résultat du point d’entrée ; un import du module ne doit pas
    # lancer ce bloc.
    raise SystemExit(main())
