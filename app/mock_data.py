"""Cinq vignobles inventés, cinquante acquisitions et quatre scans reproductibles.

On change les observations d’un scan au suivant, jamais au hasard au rechargement.
Ce générateur ne lit ni fichier professionnel, ni NAS, ni base de données.
"""

from datetime import date, timedelta
import pandas as pd

# Les noms restent explicites : ce ne sont pas des clients anonymisés à deviner.
DEMO_VINEYARDS = tuple(f"Domaine démo {letter}" for letter in "ABCDE")
DEMO_DATES = ("2026-10-15", "2026-10-19", "2026-10-21", "2026-10-22")
# On découvre davantage d’acquisitions au fil des scans. La dixième apparaît au dernier état.
FIRST_SEEN = {1: 0, 2: 0, 3: 0, 4: 1, 5: 0, 6: 0, 7: 1, 8: 1, 9: 2, 10: 3}


def _provenance(stage, domain_index):
    """On date le contrôle de chaque vignoble au sein d’une même exécution fictive."""
    day = DEMO_DATES[stage]
    key = f"demo_{'ABCDE'[domain_index].lower()}"
    run = "demo_" + day.replace("-", "")
    # Les contrôles se succèdent : une exécution globale n’est pas un instant unique.
    minute = 1 + domain_index * 2
    return dict(
        vineyard_name=DEMO_VINEYARDS[domain_index], vineyard_key=key,
        pipeline_execution_id=run, nas_pipeline_execution_id=run,
        reconciliation_run_id=f"reconcile_{run}_{key}",
        extraction_run_id=f"extract_{run}_{key}",
        excel_publication_id=f"excel_pub_{stage}", excel_version_id=f"excel_{key}_{stage}",
        excel_ingested_at=day + "T07:58:00+00:00",
        nas_checked_at=f"{day}T08:{minute:02d}:00+00:00",
        reconciled_at=f"{day}T08:{minute:02d}:30+00:00",
        reconciliation_loaded_at=f"{day}T08:{minute:02d}:45+00:00",
    )


def _acquisition(stage, domain_index, number, provenance):
    """On décrit quelques trajectoires : progrès, attente et contrôle impossible."""
    letter = "ABCDE"[domain_index]
    identifier = f"DEMO_{letter}_{number:03d}"
    # Deux acquisitions partagent un passage : deux acquisitions ne sont pas deux livrables.
    passage_number = (number + 1) // 2
    parcel, passage = f"Parcelle {passage_number}", f"Passage {passage_number}"
    category = "Test" if number in (8, 9) else "Bloqué" if number == 10 else "Production"
    if number == 4 and stage < 2:
        category = "Bloqué"  # Une décision Excel l’intégrera ensuite à la production.

    # On étale les traitements et on décale certains vignobles d’un scan.
    ready_at = {1: 1, 2: 2, 3: 3, 4: 3, 5: 2, 6: 0, 7: 2, 8: 1, 9: 9, 10: 9}[number]
    ready_at += int(domain_index % 2 == 1 and number in (1, 5, 7))
    # On laisse un traitement incomplet par vignoble au dernier scan : tout ne finit pas en vert.
    if (domain_index, number) in {(0, 4), (1, 3), (2, 7), (3, 7), (4, 2)}:
        ready_at = 4
    processed = stage >= ready_at
    folder = stage >= max(0, ready_at - 1)
    # Pour la deuxième acquisition, le dossier précède les WEBP d’un scan supplémentaire.
    if number == 2:
        processed = stage >= max(3, ready_at)
    unreadable = (domain_index == 2 and number == 5 and stage == 2) or (
        domain_index == 4 and number == 6
    )
    if unreadable:
        folder = processed = None  # Inconnu, pas absent : on n’a pas pu observer le contenu.

    # Excel peut annoncer « Terminé » avant les preuves ; on garde cet écart dans la démonstration.
    declared_done = processed is True or (number == 2 and stage == 2)
    status = "Hors périmètre" if category == "Test" else "En attente" if category == "Bloqué" else (
        "Terminé" if declared_done else "En cours"
    )
    comment = "Échantillon de test, hors production." if category == "Test" else (
        "En attente de décision sur la suite du traitement." if category == "Bloqué" else (
            "Terminé déclaré dans Excel ; WEBP à contrôler." if declared_done and processed is not True else
            "Traitement confirmé par les observations." if processed is True else "Traitement en cours."
        )
    )
    # Le commentaire suit l’état et ne contient aucun renseignement professionnel.
    comment += " Exemple fictif."
    mapped = not (number == 7 and stage < 2)
    return dict(
        **provenance, acquisition_id_normalise=identifier,
        excel_perimeter=category, excel_pipeline_status=status, excel_comments=comment,
        excel_acquisition_date=str(date(2026, 6, 10) + timedelta(days=domain_index * 4 + number)),
        excel_source_files=[f"suivi_demo_{letter}.xlsx"], excel_source_sheets=["Suivi"],
        excel_source_row_numbers=[number + 1],
        excel_needs_review=unreadable or (declared_done and processed is not True),
        decision_reason="En attente de décision dans le suivi Excel." if category == "Bloqué" else "",
        found_in_raw_live=True, raw_has_full_size_image=True, raw_has_full_size_both_sides=True,
        found_in_processing_live=folder, processing_has_webp_images=processed,
        processing_has_webp_both_sides=processed,
        found_in_parcel_mapping=mapped, found_in_passage_mapping=mapped,
        parcel_mapping_consistent=mapped,
        parcel_name=parcel if mapped else None, passage_name=passage if mapped else None,
        has_technical_error=unreadable,
        technical_errors="Lecture du traitement impossible — exemple fictif." if unreadable else "",
        processing_error="Accès en lecture refusé — exemple fictif." if unreadable else None,
        processing_decision_required=declared_done and processed is not True,
        processing_next_action="Reprendre le contrôle en lecture." if unreadable else "Consulter les preuves du traitement.",
    )


def _passages(stage, acquisitions, provenance):
    """On construit les passages à partir des liens du scan, pas d’une liste indépendante."""
    rows = []
    for number in range(1, 6):
        parcel, passage = f"Parcelle {number}", f"Passage {number}"
        linked = [a for a in acquisitions if a["parcel_name"] == parcel and a["passage_name"] == passage]
        if not linked:
            continue  # Aucun passage inventé pour une acquisition inconnue ou sans lien.
        eligible = [a for a in linked if a["excel_perimeter"] == "Production"]
        verifiable = not any(a["has_technical_error"] for a in linked)
        # On attend toutes les acquisitions de production liées pour ce scénario fictif.
        # Cette convention construit les exemples ; elle ne remplace pas les règles métier réelles.
        complete = bool(eligible) and all(a["processing_has_webp_images"] is True for a in eligible)
        folder = any(a["found_in_processing_live"] is True for a in linked)
        # La carte et les stocks n’arrivent pas systématiquement au même scan.
        map_present = complete and stage >= 1
        stocks = complete and (number == 3 or stage >= 2)
        unhealthy = stocks and number in (1, 3)
        if not verifiable:
            folder = map_present = stocks = unhealthy = None
        criterion = (stocks and unhealthy) if verifiable else None
        rows.append(dict(
            **provenance, parcel_name=parcel, passage_name=passage,
            acquisition_ids_json=[a["acquisition_id_normalise"] for a in linked],
            eligible_acquisitions_count=len(eligible), passage_created=folder,
            vitimap_created=map_present, stocks_json_exists=stocks,
            has_non_healthy_status=unhealthy,
            stock_status_values=["non_healthy"] if unhealthy is True else ["healthy"] if stocks is True else [],
            passage_outputs_verifiable=verifiable, vitiparcel_ready_verifiable=verifiable,
            vitiparcel_technical_criterion_satisfied=criterion,
            # On sépare erreur et booléen : un contrôle interrompu n’est pas une absence.
            passage_error=None if verifiable else "Lecture du passage impossible — exemple fictif.",
            vitimap_error=None if verifiable else "Contrôle non terminé — exemple fictif.",
            vitiparcel_error=None if verifiable else "Contrôle non terminé — exemple fictif.",
            passage_next_action="Confirmer l’attente métier et consulter les preuves.",
            customer_expectation_explanation="Commande non documentée dans ces données fictives ; absence ne signifie pas retard.",
        ))
    return rows


def build_mock_state():
    """On renvoie des tableaux neufs pour ne pas modifier les prochains chargements."""
    histories = {kind: [] for kind in ("acquisition", "passage", "association")}
    metadata = []
    for stage, _day in enumerate(DEMO_DATES):
        scan = {kind: [] for kind in histories}
        scan_meta = []
        for domain_index, _domain in enumerate(DEMO_VINEYARDS):
            provenance = _provenance(stage, domain_index)
            acquisitions = [
                _acquisition(stage, domain_index, number, provenance)
                for number in range(1, 11) if FIRST_SEEN[number] <= stage
            ]
            passages = _passages(stage, acquisitions, provenance)
            # Les associations portent le même bilan que les acquisitions et passages liés.
            links = [dict(
                **provenance, acquisition_id_normalise=a["acquisition_id_normalise"],
                parcel_name=a["parcel_name"], passage_name=a["passage_name"],
            ) for a in acquisitions if a["parcel_name"] and a["passage_name"]]
            lookup = {(p["parcel_name"], p["passage_name"]): p for p in passages}
            for acquisition in acquisitions:
                linked = lookup.get((acquisition["parcel_name"], acquisition["passage_name"]))
                # Sans lien, on ne peut pas vérifier les sorties du passage de cette acquisition.
                acquisition["passage_outputs_verifiable"] = bool(linked and linked["passage_outputs_verifiable"])
            for kind, rows in (("acquisition", acquisitions), ("passage", passages), ("association", links)):
                scan[kind].extend(rows)
            scan_meta.append(dict(
                **provenance, acquisition_count=len(acquisitions), passage_count=len(passages),
                association_count=len(links), declared_acquisition_count=len(acquisitions),
                declared_passage_count=len(passages), declared_association_count=len(links),
                row_counts_match_declared=True,
            ))
        # On conserve chaque scan complet ; l’état courant sera uniquement le dernier.
        for kind in histories:
            histories[kind].extend(scan[kind])
        metadata.extend(scan_meta)
        current, current_meta = scan, scan_meta
    frames = {f"reconciliation_{kind}_history": pd.DataFrame(rows) for kind, rows in histories.items()}
    frames.update({f"reconciliation_{kind}_current": pd.DataFrame(rows) for kind, rows in current.items()})
    frames["reconciliation_vineyard_history"] = pd.DataFrame(metadata)
    frames["reconciliation_vineyard_current"] = pd.DataFrame(current_meta)
    frames["reconciliation_freshness_current"] = pd.DataFrame(current_meta)
    return frames
