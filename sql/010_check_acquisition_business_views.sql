-- Contrôler les deux synthèses d’acquisitions.
-- Leurs totaux doivent retrouver ceux de la vue source, y compris les états inconnus.
-- On vérifie ensuite la lecture avec le compte du dashboard, puis on annule la transaction de
-- contrôle.

-- On garde les contrôles et les changements temporaires dans une seule transaction, annulée à la fin.
BEGIN;
DO $$
DECLARE
    source_count bigint;
    source_review bigint;
    source_unverifiable bigint;
    source_unknown bigint;
    perimeter_totals record;
    category_totals record;
BEGIN
    SELECT COUNT(*), COUNT(*) FILTER (WHERE acquisition_review_candidate IS TRUE),
           COUNT(*) FILTER (WHERE passage_outputs_verifiable IS FALSE),
           COUNT(*) FILTER (WHERE passage_outputs_verifiable IS NULL)
    INTO source_count, source_review, source_unverifiable, source_unknown
    FROM mart.reconciliation_acquisition_current;
    SELECT COALESCE(SUM(acquisition_count),0) AS n,
           COALESCE(SUM(acquisitions_to_review),0) AS review,
           COALESCE(SUM(acquisitions_outputs_not_verifiable),0) AS unverifiable,
           COALESCE(SUM(acquisitions_verifiability_unknown),0) AS unknown_count
    INTO perimeter_totals FROM mart.reconciliation_perimeter_current;
    SELECT COALESCE(SUM(acquisition_count),0) AS n,
           COALESCE(SUM(acquisitions_to_review),0) AS review,
           COALESCE(SUM(acquisitions_outputs_not_verifiable),0) AS unverifiable,
           COALESCE(SUM(acquisitions_verifiability_unknown),0) AS unknown_count
    INTO category_totals FROM mart.reconciliation_processing_category_current;
    -- On recoupe chaque compteur des deux synthèses avec la vue source ; un regroupement ne doit ni
    -- perdre ni doubler des acquisitions.
    IF perimeter_totals.n <> source_count OR category_totals.n <> source_count
       OR perimeter_totals.review <> source_review OR category_totals.review <> source_review
       OR perimeter_totals.unverifiable <> source_unverifiable OR category_totals.unverifiable <> source_unverifiable
       OR perimeter_totals.unknown_count <> source_unknown OR category_totals.unknown_count <> source_unknown THEN
        RAISE EXCEPTION 'Totaux des syntheses differents de la vue source';
    END IF;
    -- Les deux nouvelles synthèses doivent être réellement lisibles par le compte du dashboard, pas
    -- seulement par le compte qui les crée.
    IF NOT has_table_privilege('projet12_dashboard', 'mart.reconciliation_perimeter_current', 'SELECT')
       OR NOT has_table_privilege('projet12_dashboard', 'mart.reconciliation_processing_category_current', 'SELECT') THEN
        RAISE EXCEPTION 'Droits de lecture manquants pour le dashboard';
    END IF;
    RAISE NOTICE 'OK : totaux des deux syntheses conformes a la source ; droits dashboard presents.';
END $$;

-- On exécute les lectures suivantes avec les droits effectifs de projet12_dashboard, et non ceux du
-- compte administrateur.
SET LOCAL ROLE projet12_dashboard;
SELECT current_database() AS base, current_user AS role_effectif;
SELECT recorded_excel_perimeter AS perimetre_excel,
       SUM(acquisition_count) AS acquisitions,
       SUM(acquisitions_to_review) AS acquisitions_a_verifier,
       SUM(acquisitions_outputs_not_verifiable) AS acquisitions_non_verifiables
FROM mart.reconciliation_perimeter_current
GROUP BY recorded_excel_perimeter ORDER BY recorded_excel_perimeter;
SELECT vineyard_name AS vignoble,
       recorded_excel_perimeter AS perimetre_excel,
       recorded_excel_pipeline_status AS statut_excel,
       recorded_processing_category AS categorie_originale,
       processing_explanation AS explication_traitement_webp,
       recorded_relationship_category AS categorie_rattachement_originale,
       relationship_explanation AS explication_rattachement_parcelle_passage,
       acquisition_count AS acquisitions,
       acquisitions_to_review AS acquisitions_a_verifier,
       acquisitions_outputs_not_verifiable AS acquisitions_sorties_non_verifiables,
       acquisitions_verifiability_unknown AS acquisitions_verifiabilite_inconnue
FROM mart.reconciliation_processing_category_current
ORDER BY vineyard_name, recorded_excel_perimeter, recorded_excel_pipeline_status,
         recorded_processing_category, recorded_relationship_category;
SELECT DISTINCT passage_verifiability_explanation AS attention_interpretation
FROM mart.reconciliation_processing_category_current;
-- On annule la transaction de diagnostic et on libère ses verrous ; aucune ligne métier n’est chargée
-- par ce contrôle.
ROLLBACK;
