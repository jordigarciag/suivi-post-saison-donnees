# Lecture du fichier — Construction de lots fictifs utilisés par les essais d’import.
# On fabrique volontairement de petits exemples contrôlables. Une fixture décrit un cas de test, pas
# un export anonymisé de la production.
#

"""Fichiers de test uniquement ; aucun Excel reel, aucun acces NAS."""

# On sépare les copies d’objets, notamment pour comparer un état avant et après une opération.
import copy
# On importe json. On lit ou écrit les objets et manifestes au format JSON.
import json
# On rend disponibles Path, PurePosixPath depuis pathlib, pour les appels de ce fichier.
from pathlib import Path, PurePosixPath
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On importe shutil. On réalise les copies et nettoyages de fichiers explicitement prévus.
import shutil


def manifest_sibling(manifest_path, filename):
    """Chemin serialise POSIX ; Path reste reserve aux acces au disque local."""
    # On fournit à l’appelant l’écriture de PurePosixPath(manifest_path).parent / filename avec des /
    # comme séparateurs.
    return (PurePosixPath(manifest_path).parent / filename).as_posix()


def build_bundles(project_root):
    # On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables
    # dans ce contexte.
    sys.path.insert(0, str(Path(project_root) / "tests/unit"))
    # On importe test_excel_publication_check sous le nom ef. Ce module sera utilisé par les opérations
    # de ce fichier.
    import test_excel_publication_check as ef
    # On importe test_nas_reconciliation_check sous le nom nf. Ce module sera utilisé par les
    # opérations de ce fichier.
    import test_nas_reconciliation_check as nf
    # On importe import_excel_publication sous le nom excel. Ce module sera utilisé par les opérations
    # de ce fichier.
    import import_excel_publication as excel
    # On importe load_nas_reconciliation sous le nom nas. Ce module sera utilisé par les opérations de
    # ce fichier.
    import load_nas_reconciliation as nas

    # On prépare fixtures comme liste vide ; on la remplira au fil des opérations suivantes.
    fixtures = []
    # On tente ce bloc et on traite séparément les erreurs prévues : Exception.
    try:
        # On garde dans e1 la valeur renvoyée par ef.TestExcelPublicationCheck.
        e1 = ef.TestExcelPublicationCheck()
        # On initialise un petit projet temporaire à l’aide de la fixture du test Excel, sans
        # utiliser un classeur de l’entreprise.
        e1.setUp()
        # On garde cet objet de test pour pouvoir libérer son dossier temporaire dans le nettoyage
        # final.
        fixtures.append(e1)
        # Ajouter le contexte commun attendu par le rapprochement synthetique.
        for row in e1.rows:
            # On complète row avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
            # valeur fournie.
            row.update({"Périmètre": "Production", "Statut_pipeline": "À déterminer"})
        # On transforme les lignes de test en octets CSV avec les colonnes de la première ligne ;
        # ces mêmes octets alimenteront le lot synthétique.
        data = ef.csv_bytes(e1.rows, list(e1.rows[0]))
        # On récupère les métadonnées du fichier normalisé pour mettre à jour ensemble son contenu
        # et son empreinte.
        normal = e1.vm["artifacts"]["normalized"]
        # On écrit normal['path'] dans e1 ; le mode d’ouverture du flux détermine s’il s’agit d’un
        # ajout ou d’un remplacement.
        e1.write(normal["path"], data)
        # On renseigne ici l’empreinte attendue du fichier dans normal ; ce champ restera associé au
        # lot ou à l’élément en cours.
        normal["sha256"] = ef.check.sha256(data)
        # On écrit e1.vm_path dans e1 ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout ou
        # d’un remplacement.
        e1.write(e1.vm_path, ef.json_bytes(e1.vm))
        # On renseigne ici l’empreinte du manifeste dans e1.entry ; ce champ restera associé au lot
        # ou à l’élément en cours.
        e1.entry["manifest_sha256"] = ef.check.sha256(ef.json_bytes(e1.vm))
        # On écrit e1.ref_path dans e1 ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout
        # ou d’un remplacement.
        e1.write(e1.ref_path, data)
        # On écrit manifest_sibling(e1.pub_path, e1.storage + '.csv') dans e1 ; le mode d’ouverture du
        # flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        e1.write(manifest_sibling(e1.pub_path, e1.storage + ".csv"), data)
        # On renseigne ici l’empreinte attendue du fichier dans e1.publication['reference'] ; ce
        # champ restera associé au lot ou à l’élément en cours.
        e1.publication["reference"]["sha256"] = ef.check.sha256(data)
        # On remet le manifeste de publication de test en cohérence avec les fichiers qui viennent
        # d’être modifiés.
        e1.sync_publication()
        # On garde dans first_excel le lot préparé et contrôlé par le module appelé.
        first_excel = excel.prepare_bundle(e1.root)

        # On garde dans e2 la valeur renvoyée par ef.TestExcelPublicationCheck.
        e2 = ef.TestExcelPublicationCheck()
        # On crée un second projet de test indépendant pour simuler une publication suivante.
        e2.setUp()
        # On ajoute aussi ce second projet au nettoyage ; il ne doit pas rester sur le disque après
        # l’essai.
        fixtures.append(e2)
        # Meme version Excel, nouvelle publication : verifier UPDATE du pointeur.
        shutil.copytree(e1.root, e2.root, dirs_exist_ok=True)
        # On rend e2.publication indépendant de e1.publication, y compris pour les listes et
        # dictionnaires imbriqués ; les modifications du scénario ne doivent pas contaminer l’état
        # de départ.
        e2.publication = copy.deepcopy(e1.publication)
        # On garde dans e2.run une copie indépendante, y compris pour les objets imbriqués.
        e2.run = copy.deepcopy(e1.run)
        # On donne à la seconde publication un identifiant différent pour tester l’avancement du
        # résultat courant sans effacer la première.
        e2.publication_id = "20261008_33333334"
        # On distingue aussi l’ingestion ayant produit ce nouveau lot ; publication et exécution ne
        # représentent pas la même chose.
        e2.execution_id = "20261008_22222223"
        # On assemble ces deux éléments pour construire e2.pub_path.
        e2.pub_path = (
            "data/03_normalized/suivi_acquisitions_normalises/publications/"
            + e2.publication_id
            + "/manifest.json"
        )
        # On garde dans e2.ref_path la valeur renvoyée par manifest_sibling.
        e2.ref_path = manifest_sibling(e2.pub_path, "reference.csv")
        # On assemble ces deux éléments pour construire e2.run_path.
        e2.run_path = (
            "data/03_normalized/excel_ingestion_runs/"
            + e2.execution_id
            + "/manifest.json"
        )
        # On complète e2.publication avec les valeurs indiquées ; une clé déjà présente prendra la
        # nouvelle valeur fournie.
        e2.publication.update(
            # On fournit l’identifiant de la publication Excel via le paramètre publication_id de cet
            # appel.
            publication_id=e2.publication_id,
            ingestion_execution_id=e2.execution_id,
            # On fournit la date de publication via le paramètre published_at de cet appel.
            published_at="2026-10-08T14:21:17+00:00",
        )
        # On renseigne ici le chemin déclaré dans les métadonnées dans e2.publication['reference'] ;
        # ce champ restera associé au lot ou à l’élément en cours.
        e2.publication["reference"]["path"] = e2.ref_path
        # On complète e2.run avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
        # valeur fournie.
        e2.run.update(
            # On fournit l’identifiant d’exécution via le paramètre execution_id de cet appel.
            execution_id=e2.execution_id,
            # On fournit l’identifiant de la publication Excel via le paramètre publication_id de cet
            # appel.
            publication_id=e2.publication_id,
            # On fournit le chemin du tableau Excel regroupé via le paramètre reference_path de cet
            # appel.
            reference_path=e2.ref_path,
            # On fournit la date de début via le paramètre started_at de cet appel.
            started_at="2026-10-08T14:21:15+00:00",
            # On fournit la date de fin via le paramètre finished_at de cet appel.
            finished_at="2026-10-08T14:21:18+00:00",
            # On fournit le marqueur d’initialisation via le paramètre initialization de cet appel.
            initialization=False,
        )
        # On renseigne ici l’instant du contrôle dans e2.run['vineyards'][0] ; ce champ restera
        # associé au lot ou à l’élément en cours.
        e2.run["vineyards"][0]["checked_at"] = "2026-10-08T14:21:15.5+00:00"
        # On écrit e2.run_path dans e2 ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout
        # ou d’un remplacement.
        e2.write(e2.run_path, ef.json_bytes(e2.run))
        # On écrit e2.ref_path dans e2 ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout
        # ou d’un remplacement.
        e2.write(e2.ref_path, data)
        # On écrit manifest_sibling(e2.pub_path, e2.storage + '.csv') dans e2 ; le mode d’ouverture du
        # flux détermine s’il s’agit d’un ajout ou d’un remplacement.
        e2.write(manifest_sibling(e2.pub_path, e2.storage + ".csv"), data)
        # On recalcule les métadonnées de cette nouvelle publication fictive avant de la soumettre
        # au chargeur.
        e2.sync_publication()
        # On garde dans second_excel le lot préparé et contrôlé par le module appelé.
        second_excel = excel.prepare_bundle(e2.root)

        def make_nas(e, number):
            # On garde dans f la valeur renvoyée par nf.TestNasReconciliationCheck.
            f = nf.TestNasReconciliationCheck()
            # On prépare un lot NAS entièrement fictif avec la fixture de rapprochement ; aucun scan
            # réel n’est nécessaire.
            f.setUp()
            # On ajoute f à la fin de fixtures ; les éléments précédents restent conservés.
            fixtures.append(f)
            # On choisit deux dates fictives successives pour vérifier que le résultat courant
            # avance dans le bon ordre chronologique.
            day = "07" if number == 1 else "08"
            # On assemble ces deux éléments pour construire f.execution.
            f.execution = "202610" + day + "_1234567" + str(number)
            # On assemble ces deux éléments pour construire f.manifest_path.
            f.manifest_path = (
                "data/03_normalized/pipeline_runs/" + f.execution + "/manifest.json"
            )
            # On garde e.ref_path sous le nom f.reference_path ; cette affectation ne copie pas à elle
            # seule un objet mutable.
            f.reference_path = e.ref_path
            # On garde e.pub_path sous le nom f.pub_path ; cette affectation ne copie pas à elle seule
            # un objet mutable.
            f.pub_path = e.pub_path
            # On assemble ces deux éléments pour construire f.snapshot_path.
            f.snapshot_path = (
                "data/03_normalized/pipeline_runs/"
                + f.execution
                + "/tracking_reference_snapshot.csv"
            )
            # On assemble ces deux éléments pour construire checked.
            checked = "2026-10-" + day + "T15:01:00+00:00"
            # On assemble ces deux éléments pour construire reconciled.
            reconciled = "2026-10-" + day + "T15:02:00+00:00"
            # On reprend une acquisition fictive déjà connue du lot Excel pour construire un
            # rapprochement cohérent côté NAS.
            acquisition = e1.rows[0]["Acquisition_ID_normalise"]
            # On garde dans f.nas['acquisitions'] la portion des acquisitions dans f.nas
            # sélectionnée par :1 ; les bornes de fin sont exclues.
            f.nas["acquisitions"] = f.nas["acquisitions"][:1]
            # On garde dans f.results['acquisitions'] la portion des acquisitions dans f.results
            # sélectionnée par :1 ; les bornes de fin sont exclues.
            f.results["acquisitions"] = f.results["acquisitions"][:1]
            # On garde dans f.nas['associations'] la portion des associations entre acquisitions et
            # passages dans f.nas sélectionnée par :1 ; les bornes de fin sont exclues.
            f.nas["associations"] = f.nas["associations"][:1]
            # On garde dans f.results['associations'] la portion des associations entre acquisitions
            # et passages dans f.results sélectionnée par :1 ; les bornes de fin sont exclues.
            f.results["associations"] = f.results["associations"][:1]
            # On parcourt (f.nas, f.results) ; datasets désigne l’élément courant à chaque passage dans
            # la boucle.
            for datasets in (f.nas, f.results):
                # On parcourt les couples (kind, rows) de datasets : on garde ensemble la clé et sa
                # valeur au lieu des traiter dans deux listes séparées.
                for kind, rows in datasets.items():
                    # On parcourt les lignes ; row désigne l’élément courant à chaque passage dans la
                    # boucle.
                    for row in rows:
                        # On renseigne ici le nom fictif du domaine dans row ; ce champ restera
                        # associé au lot ou à l’élément en cours.
                        row["Vineyard"] = "DomaineDemoB"
                        # On renseigne ici l’instant du contrôle dans row ; ce champ restera associé
                        # au lot ou à l’élément en cours.
                        row["checked_at"] = checked
                        # On vérifie ce cas avant la suite : le texte 'acquisition_id_normalise'
                        # appartient à la ligne en cours.
                        if "acquisition_id_normalise" in row:
                            # On renseigne ici la clé normalisée de l’acquisition dans row ; ce
                            # champ restera associé au lot ou à l’élément en cours.
                            row["acquisition_id_normalise"] = acquisition
                        # On vérifie ce cas avant la suite : le texte 'excel_acquisition_id_normalise'
                        # appartient à la ligne en cours.
                        if "excel_acquisition_id_normalise" in row:
                            # On renseigne ici la clé d’acquisition du côté Excel dans row ; ce
                            # champ restera associé au lot ou à l’élément en cours.
                            row["excel_acquisition_id_normalise"] = acquisition
                            # On renseigne ici le domaine enregistré dans le suivi Excel dans row ;
                            # ce champ restera associé au lot ou à l’élément en cours.
                            row["excel_vineyard"] = "DomaineDemoB"
                            # On renseigne ici le nom du classeur fictif source dans row ; ce champ
                            # restera associé au lot ou à l’élément en cours.
                            row["excel_source_files"] = "DomaineDemoB.xlsx"
                        # On vérifie ce cas avant la suite : le texte 'reconciled_at' appartient à la
                        # ligne en cours.
                        if "reconciled_at" in row:
                            # On renseigne ici l’instant du rapprochement Excel/NAS dans row ; ce
                            # champ restera associé au lot ou à l’élément en cours.
                            row["reconciled_at"] = reconciled
                        # On vérifie ce cas avant la suite : kind correspond au texte 'passages'.
                        if kind == "passages":
                            # On renseigne ici le nombre d’acquisitions contrôlées dans row ; ce
                            # champ restera associé au lot ou à l’élément en cours.
                            row["acquisitions_controlled_count"] = "1"
                            # On prépare une représentation JSON ; les options ci-dessous fixent les
                            # détails de sérialisation.
                            row["acquisition_ids_json"] = json.dumps([acquisition])
            # On écrit f.pub_path dans f ; le mode d’ouverture du flux détermine s’il s’agit d’un ajout
            # ou d’un remplacement.
            f.write(f.pub_path, (e.root / e.pub_path).read_bytes())
            # On écrit f.reference_path dans f ; le mode d’ouverture du flux détermine s’il s’agit d’un
            # ajout ou d’un remplacement.
            f.write(f.reference_path, data)
            # On écrit f.snapshot_path dans f ; le mode d’ouverture du flux détermine s’il s’agit d’un
            # ajout ou d’un remplacement.
            f.write(f.snapshot_path, data)
            # On récupère f.manifest['vineyards'][0] et on le garde dans item pour la suite.
            item = f.manifest["vineyards"][0]
            # On complète item avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle
            # valeur fournie.
            item.update(
                # On fournit le domaine concerné via le paramètre vineyard de cet appel.
                vineyard="DomaineDemoB",
                # On fournit la date de début via le paramètre started_at de cet appel.
                started_at="2026-10-" + day + "T15:00:01+00:00",
                # On fournit la date de fin via le paramètre finished_at de cet appel.
                finished_at="2026-10-" + day + "T15:03:00+00:00",
                extraction_run_id="2026-10-" + day + "T15-01-00Z",
                reconciliation_run_id="2026-10-" + day + "T15-02-00-123456Z",
            )
            # On renseigne ici l’instant du contrôle dans item['observations'] ; ce champ restera
            # associé au lot ou à l’élément en cours.
            item["observations"]["checked_at"] = checked
            # On regroupe dans item['observations']['volumes'] ces champs nommés ; on pourra les
            # retrouver par leur clé plutôt que par leur position.
            item["observations"]["volumes"] = {
                # On associe la clé 'evidence' à cette valeur dans cet objet.
                "evidence": 1,
                # On renseigne les associations entre acquisitions et passages sous la clé
                # 'associations'.
                "associations": 1,
                # On renseigne les passages sous la clé 'passages'.
                "passages": 1,
            }
            # On parcourt [('nas', f.nas), ('result', f.results)] ; (stage, datasets) désigne l’élément
            # courant à chaque passage dans la boucle.
            for stage, datasets in [("nas", f.nas), ("result", f.results)]:
                # On choisit la valeur de outputs selon ce test : l’étape concernée correspond à le
                # texte 'nas'. Les deux résultats possibles restent définis explicitement ici.
                outputs = (
                    item["evidence_outputs"]
                    if stage == "nas"
                    else item["reconciliation_outputs"]
                )
                # On choisit la valeur de folder selon ce test : l’étape concernée correspond à le
                # texte 'nas'. Les deux résultats possibles restent définis explicitement ici.
                folder = (
                    "nas_live_evidence"
                    if stage == "nas"
                    else "reconciliations/nas_live"
                )
                # On parcourt datasets ; kind désigne l’élément courant à chaque passage dans la
                # boucle.
                for kind in datasets:
                    # On choisit la valeur de run_id selon ce test : l’étape concernée correspond à le
                    # texte 'nas'. Les deux résultats possibles restent définis explicitement ici.
                    run_id = (
                        item["extraction_run_id"]
                        if stage == "nas"
                        else item["reconciliation_run_id"]
                    )
                    # On assemble ces deux éléments pour construire path.
                    path = (
                        "data/03_normalized/"
                        + folder
                        + "/runs/"
                        + f.execution
                        + "/v01/domainedemob_"
                        + kind
                        + "_"
                        + run_id
                        + ".csv"
                    )
                    # On gardu chemin de travail sous le nom outputs['evidence' if stage == 'nas'
                    # and kind == 'acquisitions'… ; cette affectation ne copie pas à elle seule un
                    # objet mutable.
                    outputs[
                        "evidence"
                        if stage == "nas" and kind == "acquisitions"
                        else kind
                    ] = path
                    # On écrit path dans f ; le mode d’ouverture du flux détermine s’il s’agit d’un
                    # ajout ou d’un remplacement.
                    f.write(path, nf.csv_bytes(datasets[kind]))
            # On complète f.manifest avec les valeurs indiquées ; une clé déjà présente prendra la
            # nouvelle valeur fournie.
            f.manifest.update(
                # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de
                # cet appel.
                pipeline_execution_id=f.execution,
                # On fournit la date de début via le paramètre started_at de cet appel.
                started_at="2026-10-" + day + "T15:00:00+00:00",
                # On fournit la date de fin via le paramètre finished_at de cet appel.
                finished_at="2026-10-" + day + "T15:03:01+00:00",
                reference_source=f.reference_path,
                reference_snapshot=f.snapshot_path,
                # On fournit l’empreinte du tableau Excel regroupé via le paramètre reference_sha256 de
                # cet appel.
                reference_sha256=nf.checker.sha256(data),
            )
            # On recalcule le manifeste de test après les modifications du scénario.
            f.sync_manifest()
            # On fournit à l’appelant le lot préparé et contrôlé par le module appelé.
            return nas.prepare_bundle(f.root, f.manifest_path)

        # On garde dans first_nas la valeur renvoyée par make_nas.
        first_nas = make_nas(e1, 1)
        # On garde dans second_nas la valeur renvoyée par make_nas.
        second_nas = make_nas(e2, 2)
        # On renvoie ces 2 éléments ensemble ; l’appelant doit respecter leur ordre s’il les décompose.
        return fixtures, (first_excel, first_nas, second_excel, second_nas)
    except Exception:
        # On parcourt reversed(fixtures) ; f désigne l’élément courant à chaque passage dans la boucle.
        for f in reversed(fixtures):
            # On appelle f.doCleanups sans argument positionnel.
            f.doCleanups()
        # On laisse remonter l’erreur déjà interceptée, sans la remplacer par une réussite ni en
        # fabriquer une autre.
        raise
