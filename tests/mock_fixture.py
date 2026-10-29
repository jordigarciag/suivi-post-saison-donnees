# Cas minimaux de régression, indépendants de la démonstration enrichie.
# Lecture du fichier — Jeu de données fictives pour explorer le dashboard sans les installations professionnelles.
# On prépare notamment des cas présents, absents et inconnus. Ces exemples servent à montrer les
# différences de traitement, pas à reproduire des résultats d’exploitation.
#

"""Données synthétiques destinées uniquement au mode de démonstration explicite."""

# On importe pandas sous le nom pd. On prépare les tableaux de données et leurs calculs avec pandas.
import pandas as pd


# On construit le premier ensemble d’exemples fictifs, ensuite complété pour les scénarios
# d’historique.
def _build_base_mock_state():
    # On distribue ces valeurs entre a, b, dans l’ordre de l’affectation. Chaque nom reçoit son propre
    # élément.
    a, b = "Domaine démo A", "Domaine démo B"
    # On prépare aq comme liste vide ; on la remplira au fil des opérations suivantes.
    aq = []
    # On parcourt [(a, 'DEMO_A_001', 'Production', True, True, 'Parcelle 1', 'Passage 1', F… ;
    # (vineyard, identifier, category, proc, webp, parcel, passage, review, err… désigne l’élément
    # courant à chaque passage dans la boucle.
    for vineyard, identifier, category, proc, webp, parcel, passage, review, error in [
        (
            a,
            "DEMO_A_001",
            "Production",
            True,
            True,
            "Parcelle 1",
            "Passage 1",
            False,
            False,
        ),
        (
            a,
            "DEMO_A_002",
            "Production",
            True,
            False,
            "Parcelle 2",
            "Passage 2",
            True,
            False,
        ),
        (a, "DEMO_A_003", "Test", False, False, "Parcelle 3", "Passage 3", True, False),
        (a, "DEMO_A_004", "Bloqué", True, True, "Parcelle 4", "Passage 4", True, False),
        (
            b,
            "DEMO_B_001",
            "Production",
            None,
            None,
            "Parcelle 5",
            "Passage 5",
            False,
            False,
        ),
        (
            b,
            "DEMO_B_002",
            "Production",
            True,
            True,
            "Parcelle 6",
            "Passage 6",
            False,
            False,
        ),
        (b, "DEMO_B_003", "Test", False, False, None, None, True, True),
    ]:
        # On ajoute dict(vineyard_name=vineyard, acquisition_id_normalise=identifier,
        # excel_perimeter=categor… à la fin de aq ; les éléments précédents restent conservés.
        aq.append(
            dict(
                # On fournit le nom du domaine via le paramètre vineyard_name de cet appel.
                vineyard_name=vineyard,
                # On fournit l’identifiant normalisé de l’acquisition via le paramètre
                # acquisition_id_normalise de cet appel.
                acquisition_id_normalise=identifier,
                # On fournit le périmètre du suivi Excel via le paramètre excel_perimeter de cet appel.
                excel_perimeter=category,
                # On fournit la présence dans les traitements via le paramètre found_in_processing_live
                # de cet appel.
                found_in_processing_live=proc,
                # On fournit la présence d’images WEBP via le paramètre processing_has_webp_images de
                # cet appel.
                processing_has_webp_images=webp,
                parcel_name=parcel,
                passage_name=passage,
                excel_needs_review=review,
                has_technical_error=error,
                excel_acquisition_date="2026-06-19",
                # On fournit la prochaine action indiquée pour le traitement via le paramètre
                # processing_next_action de cet appel.
                processing_next_action="Consulter les preuves du traitement",
                nas_checked_at="2026-10-21T08:29:00+00:00",
                # On fournit la date du rapprochement via le paramètre reconciled_at de cet appel.
                reconciled_at="2026-10-21T08:30:00+00:00",
            )
        )
    # On parcourt les acquisitions ; row désigne l’élément courant à chaque passage dans la boucle.
    for row in aq:
        # On récupère l’identifiant normalisé de l’acquisition dans row et on le garde dans ident pour
        # la suite.
        ident = row["acquisition_id_normalise"]
        # On complète row avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle valeur
        # fournie.
        row.update(
            # On fournit le statut du suivi Excel via le paramètre excel_pipeline_status de cet appel.
            excel_pipeline_status="En attente"
            if row["excel_perimeter"] == "Bloqué"
            else "Hors périmètre"
            if row["excel_perimeter"] == "Test"
            else "À déterminer",
            excel_comments="Attente de décision sur la suite du traitement — exemple fictif."
            if row["excel_perimeter"] == "Bloqué"
            else "",
            decision_reason="Hors contrôles de production : statut En attente."
            if row["excel_perimeter"] == "Bloqué"
            else "",
            excel_source_files=["suivi_acquisitions_demo.xlsx"],
            excel_source_sheets=["Suivi"],
            excel_source_row_numbers=[12],
            # On fournit la présence constatée dans les données brutes via le paramètre
            # found_in_raw_live de cet appel.
            found_in_raw_live=None
            if ident == "DEMO_B_001"
            else False
            if ident == "DEMO_B_002"
            else True,
            # On fournit la présence d’une image pleine taille via le paramètre raw_has_full_size_image
            # de cet appel.
            raw_has_full_size_image=None
            if ident == "DEMO_B_001"
            else False
            if ident == "DEMO_A_002"
            else True,
            # On fournit la présence dans les correspondances de parcelles via le paramètre
            # found_in_parcel_mapping de cet appel.
            found_in_parcel_mapping=None
            if ident == "DEMO_B_001"
            else ident != "DEMO_A_002",
            # On fournit la présence dans les correspondances de passages via le paramètre
            # found_in_passage_mapping de cet appel.
            found_in_passage_mapping=None
            if ident == "DEMO_B_001"
            else ident != "DEMO_B_002",
            processing_decision_required=ident == "DEMO_A_002",
            # On fournit la catégorie métier du traitement via le paramètre
            # processing_business_category de cet appel.
            processing_business_category="Divergence — terminé déclaré, preuve WEBP incomplète"
            if ident == "DEMO_A_002"
            else "",
            # On fournit le détail des erreurs techniques via le paramètre technical_errors de cet
            # appel.
            technical_errors="Exemple fictif : contrôle interrompu."
            if row["has_technical_error"]
            else "",
        )
    # On prépare passages comme liste vide ; on la remplira au fil des opérations suivantes.
    passages = []
    # On parcourt [(a, 'Parcelle 1', 'Passage 1', ['DEMO_A_001'], True, True, True, 1, True… ;
    # (vineyard, parcel, passage, ids, map_, stocks, unhealthy, eligible, creat… désigne l’élément
    # courant à chaque passage dans la boucle.
    for vineyard, parcel, passage, ids, map_, stocks, unhealthy, eligible, created in [
        (a, "Parcelle 1", "Passage 1", ["DEMO_A_001"], True, True, True, 1, True),
        (a, "Parcelle 2", "Passage 2", ["DEMO_A_002"], False, False, False, 1, True),
        (a, "Parcelle 3", "Passage 3", ["DEMO_A_003"], False, False, False, 0, True),
        (a, "Parcelle 4", "Passage 4", ["DEMO_A_004"], False, True, False, 0, True),
        (b, "Parcelle 5", "Passage 5", ["DEMO_B_001"], None, None, None, 1, None),
        (b, "Parcelle 6", "Passage 6", ["DEMO_B_002"], False, True, False, 1, True),
    ]:
        # On ajoute dict(vineyard_name=vineyard, parcel_name=parcel, passage_name=passage,
        # acquisition_ids_js… à la fin de passages ; les éléments précédents restent conservés.
        passages.append(
            dict(
                # On fournit le nom du domaine via le paramètre vineyard_name de cet appel.
                vineyard_name=vineyard,
                parcel_name=parcel,
                passage_name=passage,
                acquisition_ids_json=ids,
                vitimap_created=map_,
                stocks_json_exists=stocks,
                has_non_healthy_status=unhealthy,
                eligible_acquisitions_count=eligible,
                passage_created=created,
                passage_error=None,
                vitimap_error=None,
                vitiparcel_error=None,
                passage_next_action="Confirmer l’attente métier et consulter les preuves",
            )
        )
    # On prépare history comme liste vide ; on la remplira au fil des opérations suivantes.
    history = []
    # On parcourt les acquisitions ; r désigne l’élément courant à chaque passage dans la boucle.
    for r in aq:
        # On vérifie ce cas avant la suite : le périmètre du suivi Excel dans r diffère du texte
        # 'Production'.
        if r["excel_perimeter"] != "Production":
            # On ignore la suite de ce tour de boucle et on passe à l’élément suivant.
            continue
        # On parcourt [('demo_20261015', '2026-10-15T08:00:00+00:00'), ('demo_20261021', '2026-… ;
        # (run, time) désigne l’élément courant à chaque passage dans la boucle.
        for run, time in [
            ("demo_20261015", "2026-10-15T08:00:00+00:00"),
            ("demo_20261021", "2026-10-21T08:29:00+00:00"),
        ]:
            # On garde dans item un nouveau dictionnaire construit avec les valeurs indiquées (la copie
            # reste superficielle).
            item = dict(r, pipeline_execution_id=run, nas_checked_at=time)
            # Cette branche traite le cas où l’identifiant normalisé de l’acquisition dans r correspond
            # au texte 'DEMO_A_001' et run correspond au texte 'demo_20261015'.
            if r["acquisition_id_normalise"] == "DEMO_A_001" and run == "demo_20261015":
                # On initialise item['processing_has_webp_images'] à False ; les branches suivantes
                # pourront modifier cet état.
                item["processing_has_webp_images"] = False
            # On ajoute item à la fin de history ; les éléments précédents restent conservés.
            history.append(item)
    # On garde dans freshness un tableau pandas construit avec les données indiquées.
    freshness = pd.DataFrame(
        [
            dict(
                # On fournit le nom du domaine via le paramètre vineyard_name de cet appel.
                vineyard_name=v,
                nas_checked_at="2026-10-21T08:29:00+00:00",
                # On fournit la date du rapprochement via le paramètre reconciled_at de cet appel.
                reconciled_at="2026-10-21T08:30:00+00:00",
            )
            for v in [a, b]
        ]
    )
    # On renvoie ce résultat avec des champs nommés, pour que l’appelant puisse retrouver chaque
    # information par sa clé.
    return {
        # On associe la clé 'reconciliation_acquisition_current' à cette valeur dans cet objet.
        "reconciliation_acquisition_current": pd.DataFrame(aq),
        # On associe la clé 'reconciliation_passage_current' à cette valeur dans cet objet.
        "reconciliation_passage_current": pd.DataFrame(passages),
        # On associe la clé 'reconciliation_freshness_current' à cette valeur dans cet objet.
        "reconciliation_freshness_current": freshness,
        # On associe la clé 'reconciliation_vineyard_current' à cette valeur dans cet objet.
        "reconciliation_vineyard_current": pd.DataFrame({"vineyard_name": [a, b]}),
        # On associe la clé 'reconciliation_acquisition_history' à cette valeur dans cet objet.
        "reconciliation_acquisition_history": pd.DataFrame(history),
        # On associe la clé 'reconciliation_vineyard_history' à cette valeur dans cet objet.
        "reconciliation_vineyard_history": pd.DataFrame(),
    }




def build_mock_state():
    """Four complete synthetic snapshots, last two unchanged.

    Older transitions exercise Excel status/comments, NAS proofs, scope and links.
    Not loaded unless DASHBOARD_USE_MOCK=1 (or explicit test argument).
    """
    # On sépare les copies d’objets, notamment pour comparer un état avant et après une opération.
    import copy

    # On garde dans base la valeur renvoyée par _build_base_mock_state.
    base = _build_base_mock_state()
    # On indexe histories par k ; chaque clé sera associée à []. Une même clé ne peut garder qu’une
    # valeur.
    histories = {k: [] for k in ["acquisition", "passage", "association"]}
    # On prépare metadata comme liste vide ; on la remplira au fil des opérations suivantes.
    metadata = []
    # On prépare une liste distincte pour chacun de ces résultats : current_aq, current_ps. Elles
    # seront alimentées au même rythme dans la boucle.
    current_aq, current_ps = [], []
    # On rassemble dans dates les 4 éléments explicitement indiqués, en conservant leur structure.
    dates = ["2026-10-15", "2026-10-19", "2026-10-21", "2026-10-22"]
    # On parcourt dates en gardant aussi sa position dans (stage, date) ; le comptage commence à zéro.
    for stage, date in enumerate(dates):
        # On assemble ces deux éléments pour construire run.
        run = "demo_" + date.replace("-", "")
        # On parcourt ['Domaine démo A', 'Domaine démo B'] ; vineyard désigne l’élément courant à
        # chaque passage dans la boucle.
        for vineyard in ["Domaine démo A", "Domaine démo B"]:
            # On choisit la valeur de key selon ce test : le domaine concerné se termine par le texte
            # 'A'. Les deux résultats possibles restent définis explicitement ici.
            key = "demo_a" if vineyard.endswith("A") else "demo_b"
            # On assemble ces deux éléments pour construire nas_date.
            nas_date = date + (
                "T08:01:00+00:00" if key == "demo_a" else "T08:03:00+00:00"
            )
            # On garde dans prov un nouveau dictionnaire construit avec les valeurs indiquées.
            prov = dict(
                # On fournit le nom du domaine via le paramètre vineyard_name de cet appel.
                vineyard_name=vineyard,
                # On fournit la clé du domaine via le paramètre vineyard_key de cet appel.
                vineyard_key=key,
                # On fournit l’identifiant du traitement NAS via le paramètre pipeline_execution_id de
                # cet appel.
                pipeline_execution_id=run,
                nas_pipeline_execution_id=run,
                reconciliation_run_id=f"reconcile_{run}_{key}",
                extraction_run_id=f"extract_{run}_{key}",
                # On fournit l’identifiant du lot Excel via le paramètre excel_publication_id de cet
                # appel.
                excel_publication_id="excel_pub_" + ("old" if stage == 0 else "new"),
                excel_version_id="excel_" + key + ("_old" if stage == 0 else "_new"),
                excel_ingested_at=date + "T07:58:00+00:00",
                nas_checked_at=nas_date,
                # On fournit la date du rapprochement via le paramètre reconciled_at de cet appel.
                reconciled_at=date + "T08:05:00+00:00",
                reconciliation_loaded_at=date + "T08:06:00+00:00",
            )
            # On construit aq comme une liste à partir de dict(copy.deepcopy(r), **prov), pour chaque r
            # de base['reconciliation_acquisition_current'].to_dict('records') en ne gardant que les
            # éléments qui passent le filtre.
            aq = [
                dict(copy.deepcopy(r), **prov)
                for r in base["reconciliation_acquisition_current"].to_dict("records")
                if r["vineyard_name"] == vineyard
            ]
            # On construit ps comme une liste à partir de dict(copy.deepcopy(r), **prov), pour chaque r
            # de base['reconciliation_passage_current'].to_dict('records') en ne gardant que les
            # éléments qui passent le filtre.
            ps = [
                dict(copy.deepcopy(r), **prov)
                for r in base["reconciliation_passage_current"].to_dict("records")
                if r["vineyard_name"] == vineyard
            ]
            # On vérifie ce cas avant la suite : l’étape concernée correspond à 0.
            if stage == 0:
                # On parcourt les acquisitions ; r désigne l’élément courant à chaque passage dans la
                # boucle.
                for r in aq:
                    # On vérifie ce cas avant la suite : l’identifiant normalisé de l’acquisition dans
                    # r correspond au texte 'DEMO_A_001'.
                    if r["acquisition_id_normalise"] == "DEMO_A_001":
                        # On initialise r['processing_has_webp_images'] à False ; les branches
                        # suivantes pourront modifier cet état.
                        r["processing_has_webp_images"] = False
                        # On utilise ce texte pour r['excel_pipeline_status'] ; il ne dépend pas d’une
                        # valeur récupérée ailleurs à cet endroit.
                        r["excel_pipeline_status"] = "En cours"
                        # On utilise ce texte pour r['excel_comments'] ; il ne dépend pas d’une valeur
                        # récupérée ailleurs à cet endroit.
                        r["excel_comments"] = "Traitement à vérifier — exemple fictif."
                # On parcourt les passages ; p désigne l’élément courant à chaque passage dans la
                # boucle.
                for p in ps:
                    # On vérifie ce cas avant la suite : p['passage_name'] correspond au texte
                    # 'Passage 1'.
                    if p["passage_name"] == "Passage 1":
                        # On initialise p['vitimap_created'] à False ; les branches suivantes pourront
                        # modifier cet état.
                        p["vitimap_created"] = False
                        # On initialise p['stocks_json_exists'] à False ; les branches suivantes
                        # pourront modifier cet état.
                        p["stocks_json_exists"] = False
                        # On initialise p['has_non_healthy_status'] à False ; les branches suivantes
                        # pourront modifier cet état.
                        p["has_non_healthy_status"] = False
            # On vérifie ce cas avant la suite : l’étape concernée est inférieur à 2.
            if stage < 2:
                # On construit aq comme une liste à partir de r, pour chaque r de aq en ne gardant que
                # les éléments qui passent le filtre.
                aq = [r for r in aq if r["acquisition_id_normalise"] != "DEMO_A_004"]
                # On construit ps comme une liste à partir de r, pour chaque r de ps en ne gardant que
                # les éléments qui passent le filtre.
                ps = [r for r in ps if r["passage_name"] != "Passage 4"]
            # On prépare links comme liste vide ; on la remplira au fil des opérations suivantes.
            links = []
            # On parcourt les acquisitions ; r désigne l’élément courant à chaque passage dans la
            # boucle.
            for r in aq:
                # Cette branche traite le cas où le champ 'parcel_name' de r est évalué comme vrai et
                # le champ 'passage_name' de r est évalué comme vrai.
                if r.get("parcel_name") and r.get("passage_name"):
                    # On ajoute dict(**prov, acquisition_id_normalise=r['acquisition_id_normalise'],
                    # parcel_name=r['parce… à la fin de links ; les éléments précédents restent
                    # conservés.
                    links.append(
                        dict(
                            **prov,
                            # On fournit l’identifiant normalisé de l’acquisition via le paramètre
                            # acquisition_id_normalise de cet appel.
                            acquisition_id_normalise=r["acquisition_id_normalise"],
                            parcel_name=r["parcel_name"],
                            passage_name=r["passage_name"],
                        )
                    )
            # On ajoute aq à histories['acquisition'] et on conserve ce nouvel état pour la suite.
            histories["acquisition"] += aq
            # On ajoute ps à histories['passage'] et on conserve ce nouvel état pour la suite.
            histories["passage"] += ps
            # On ajoute links à histories['association'] et on conserve ce nouvel état pour la suite.
            histories["association"] += links
            # On ajoute dict(**prov, acquisition_count=len(aq), passage_count=len(ps),
            # association_count=len(link… à la fin de metadata ; les éléments précédents restent
            # conservés.
            metadata.append(
                dict(
                    **prov,
                    acquisition_count=len(aq),
                    passage_count=len(ps),
                    association_count=len(links),
                    declared_acquisition_count=len(aq),
                    declared_passage_count=len(ps),
                    declared_association_count=len(links),
                    row_counts_match_declared=True,
                )
            )
            # On vérifie ce cas avant la suite : l’étape concernée correspond à len(dates) - 1.
            if stage == len(dates) - 1:
                # On ajoute aq à current_aq et on conserve ce nouvel état pour la suite.
                current_aq += aq
                # On ajoute ps à current_ps et on conserve ce nouvel état pour la suite.
                current_ps += ps
    # On complète base avec les valeurs indiquées ; une clé déjà présente prendra la nouvelle valeur
    # fournie.
    base.update(
        {f"reconciliation_{k}_history": pd.DataFrame(v) for k, v in histories.items()}
    )
    # On garde dans base['reconciliation_vineyard_history'] un tableau pandas construit avec les
    # données indiquées.
    base["reconciliation_vineyard_history"] = pd.DataFrame(metadata)
    # On garde dans base['reconciliation_acquisition_current'] un tableau pandas construit avec les
    # données indiquées.
    base["reconciliation_acquisition_current"] = pd.DataFrame(current_aq)
    # On garde dans base['reconciliation_passage_current'] un tableau pandas construit avec les données
    # indiquées.
    base["reconciliation_passage_current"] = pd.DataFrame(current_ps)
    # On garde dans base['reconciliation_vineyard_current'] un tableau pandas construit avec les
    # données indiquées.
    base["reconciliation_vineyard_current"] = pd.DataFrame(metadata[-2:])
    # On garde dans base['reconciliation_freshness_current'] un tableau pandas construit avec les
    # données indiquées.
    base["reconciliation_freshness_current"] = pd.DataFrame(metadata[-2:])
    # On remet base à l’appelant ; les étapes suivantes de cette fonction ne sont plus parcourues.
    return base
