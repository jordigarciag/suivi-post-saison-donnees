-- Contrôler la couverture et les dates de la vue de fraîcheur.
-- On doit retrouver tous les domaines des deux sources, même lorsqu’une seule source est présente.
-- Le catalogue décrit 29 champs par bilan actif ; ses dates doivent correspondre à leur origine, pas
-- toutes à la date du rapprochement.

-- On garde les contrôles et les changements temporaires dans une seule transaction, annulée à la fin.
BEGIN;
DO $$
BEGIN
    -- On attend une seule ligne de fraîcheur par domaine, même si plusieurs bilans historiques sont
    -- conservés.
    IF EXISTS (
        SELECT vineyard_key FROM mart.reconciliation_freshness_current
        GROUP BY vineyard_key HAVING COUNT(*) <> 1
    ) THEN
        RAISE EXCEPTION 'Plusieurs lignes de fraicheur pour un vignoble';
    END IF;
    -- On compare les ensembles dans les deux sens : aucun domaine ne doit disparaître ni être ajouté
    -- par la vue.
    IF EXISTS (
        (SELECT vineyard_key FROM mart.excel_vineyard_current
         UNION SELECT vineyard_key FROM mart.reconciliation_vineyard_current)
        EXCEPT SELECT vineyard_key FROM mart.reconciliation_freshness_current
    ) OR EXISTS (
        SELECT vineyard_key FROM mart.reconciliation_freshness_current
        EXCEPT (SELECT vineyard_key FROM mart.excel_vineyard_current
                UNION SELECT vineyard_key FROM mart.reconciliation_vineyard_current)
    ) THEN
        RAISE EXCEPTION 'Couverture de la vue de fraicheur differente des sources';
    END IF;
    -- On compare les identifiants et les dates avec le bilan actif. IS DISTINCT FROM détecte aussi les
    -- différences impliquant NULL.
    IF EXISTS (
        SELECT 1 FROM mart.reconciliation_freshness_current f
        -- On filtre le détail historique avec la clé complète du bilan actif afin de ne pas mélanger
        -- les dates d’observation.
        JOIN mart.reconciliation_vineyard_current r USING (vineyard_key)
        WHERE f.pipeline_execution_id IS DISTINCT FROM r.pipeline_execution_id
           OR f.reconciliation_run_id IS DISTINCT FROM r.reconciliation_run_id
           OR f.recorded_excel_publication_id IS DISTINCT FROM r.excel_publication_id
           OR f.recorded_excel_version_id IS DISTINCT FROM r.excel_version_id
           OR f.recorded_excel_ingested_at IS DISTINCT FROM r.excel_ingested_at
           OR f.nas_checked_at IS DISTINCT FROM r.nas_checked_at
           OR f.reconciled_at IS DISTINCT FROM r.reconciled_at
           OR f.activated_in_database_at IS DISTINCT FROM r.activated_in_database_at
           OR f.excel_version_matches_current IS DISTINCT FROM r.excel_version_matches_current
    ) THEN
        RAISE EXCEPTION 'Provenance differente du bilan actif';
    END IF;
    -- On vérifie les accès utiles au dashboard sur les vues concernées, sans lui ouvrir les tables
    -- sources.
    IF NOT has_table_privilege('projet12_dashboard', 'mart.reconciliation_freshness_current', 'SELECT') THEN
        RAISE EXCEPTION 'Droit de lecture dashboard manquant';
    END IF;
    IF NOT has_table_privilege('projet12_dashboard', 'mart.reconciliation_field_provenance_current', 'SELECT') THEN
        RAISE EXCEPTION 'Droit de lecture du catalogue de provenance manquant';
    END IF;
    -- On attend les 29 noms de champ distincts pour chaque bilan actif, pas simplement un total de
    -- lignes qui pourrait cacher des doublons.
    IF EXISTS (
        SELECT vineyard_key FROM mart.reconciliation_field_provenance_current
        GROUP BY vineyard_key HAVING COUNT(*) <> 29 OR COUNT(DISTINCT field_name) <> 29
    ) OR (SELECT COUNT(DISTINCT vineyard_key) FROM mart.reconciliation_field_provenance_current)
         <> (SELECT COUNT(*) FROM mart.reconciliation_vineyard_current) THEN
        RAISE EXCEPTION 'Catalogue de provenance : couverture des champs ou vignobles incomplete';
    END IF;
    -- Chaque champ doit prendre la date de sa propre origine : Excel, NAS, rapprochement ou
    -- consultation.
    IF EXISTS (
        SELECT 1 FROM mart.reconciliation_field_provenance_current p
        JOIN mart.reconciliation_freshness_current f USING (vineyard_key)
        WHERE p.source_event_at IS DISTINCT FROM
           CASE p.source_kind WHEN 'excel' THEN f.recorded_excel_ingested_at
                              -- Pour un constat NAS, on reprend la date du contrôle direct conservé.
                              WHEN 'nas' THEN f.nas_checked_at
                              -- Pour une conclusion croisée, on date le calcul, en gardant à côté les
                              -- dates de ses sources.
                              WHEN 'reconciliation' THEN f.reconciled_at
                              ELSE f.freshness_evaluated_at END
    ) THEN
        RAISE EXCEPTION 'Date de provenance differente de la source';
    END IF;
    RAISE NOTICE 'OK : couverture, provenance des bilans actifs et droit de lecture conformes.';
END $$;
-- On exécute les lectures suivantes avec les droits effectifs de projet12_dashboard, et non ceux du
-- compte administrateur.
SET LOCAL ROLE projet12_dashboard;
SELECT current_database() AS base, current_user AS role_effectif;
SELECT COUNT(*) AS vignobles_visibles,
       COUNT(*) FILTER (WHERE has_current_excel_reference) AS vignobles_excel_courant,
       COUNT(*) FILTER (WHERE has_active_reconciliation) AS bilans_actifs,
       COUNT(*) FILTER (WHERE has_current_excel_reference AND NOT has_active_reconciliation) AS vignobles_excel_sans_bilan,
       COUNT(*) FILTER (WHERE has_active_reconciliation AND NOT has_current_excel_reference) AS bilans_hors_reference_excel,
       COUNT(*) FILTER (WHERE excel_version_matches_current IS TRUE) AS versions_excel_identiques,
       COUNT(*) FILTER (WHERE excel_version_matches_current IS FALSE) AS versions_excel_differentes,
       COUNT(*) FILTER (WHERE has_active_reconciliation AND excel_version_matches_current IS NULL) AS comparaisons_version_indisponibles,
       COUNT(*) FILTER (WHERE recorded_chronology_consistent IS FALSE) AS chronologies_a_examiner,
       COUNT(*) FILTER (WHERE nas_observation_in_future IS TRUE) AS observations_datees_dans_le_futur
FROM mart.reconciliation_freshness_current;
SELECT vineyard_name AS vignoble,
       pipeline_execution_id AS execution_du_bilan,
       recorded_excel_source_filename AS fichier_excel_du_bilan,
       recorded_excel_source_modified_at AS modification_fichier_excel_si_connue,
       recorded_excel_version_id AS version_excel_du_bilan,
       current_excel_version_id AS version_excel_courante,
       recorded_excel_ingested_at AS normalisation_excel_du_bilan,
       recorded_excel_version_loaded_at AS chargement_version_excel_en_base,
       nas_observation_origin AS origine_des_faits_nas,
       nas_extraction_run_id AS identifiant_du_controle_nas,
       nas_checked_at AS date_du_controle_direct_nas,
       nas_observation_date_meaning AS sens_date_nas,
       reconciled_at AS calcul_du_rapprochement,
       reconciliation_loaded_at AS chargement_rapprochement_en_base,
       activated_in_database_at AS activation_du_bilan,
       freshness_evaluated_at AS consultation_sql,
       nas_observation_age AS temps_depuis_controle_direct_nas,
       historical_scan_role AS role_du_scan_historique,
       dates_not_established AS dates_non_etablies,
       provenance_explanation AS interpretation
FROM mart.reconciliation_freshness_current ORDER BY vineyard_name;
SELECT DISTINCT field_name AS champ,
       source_description AS origine,
       field_meaning AS logique,
       source_event_date_meaning AS signification_date
FROM mart.reconciliation_field_provenance_current ORDER BY field_name;
-- On annule la transaction de diagnostic et on libère ses verrous ; aucune ligne métier n’est chargée
-- par ce contrôle.
ROLLBACK;
