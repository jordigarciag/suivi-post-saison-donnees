-- Contrôler les 14 indicateurs et leur synthèse sur un état cohérent des données.
-- On copie chaque vue une fois dans une table temporaire pour éviter de refaire les mêmes lectures à
-- chaque assertion.
-- Les contrôles portent sur les volumes, l’interprétation des inconnues et erreurs, puis les
-- permissions du dashboard.

-- On garde les contrôles et les changements temporaires dans une seule transaction, annulée à la fin.
BEGIN;
-- On évite ici le coût de compilation JIT pour ces requêtes de création ou de contrôle.
SET LOCAL jit = off;
-- On borne le temps d’exécution d’une instruction de ce diagnostic pour ne pas laisser une lecture
-- bloquée indéfiniment.
SET LOCAL statement_timeout = '120s';
-- On limite l’attente des verrous ; un dépassement demande un diagnostic, pas une suppression aveugle
-- des verrous.
SET LOCAL lock_timeout = '5s';
-- REPEATABLE READ garde le même état visible pendant ces contrôles ; des changements concurrents ne
-- doivent pas fausser les comparaisons entre vues.
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
DO $$ BEGIN RAISE NOTICE 'Etape 1/5 : lecture unique des acquisitions sources'; END $$;
-- On fige la population d’acquisitions de départ dans check_source pour la durée du diagnostic. La
-- table est temporaire, pas une nouvelle source métier.
CREATE TEMP TABLE check_source ON COMMIT DROP AS SELECT * FROM mart.reconciliation_acquisition_current;
DO $$ BEGIN RAISE NOTICE 'Etape 2/5 : lecture unique du detail des preuves'; END $$;
-- On fige le détail enrichi des constats dans check_evidence pour la durée du diagnostic. La table est
-- temporaire, pas une nouvelle source métier.
CREATE TEMP TABLE check_evidence ON COMMIT DROP AS SELECT * FROM mart.reconciliation_acquisition_evidence_current;
DO $$ BEGIN RAISE NOTICE 'Etape 3/5 : lecture unique des 14 indicateurs par acquisition'; END $$;
-- On fige les 14 indicateurs par acquisition dans check_proofs pour la durée du diagnostic. La table
-- est temporaire, pas une nouvelle source métier.
CREATE TEMP TABLE check_proofs ON COMMIT DROP AS SELECT * FROM mart.reconciliation_acquisition_proof_current;
DO $$ BEGIN RAISE NOTICE 'Etape 4/5 : lecture unique de la synthese des preuves'; END $$;
-- On fige la synthèse des interprétations dans check_summary pour la durée du diagnostic. La table est
-- temporaire, pas une nouvelle source métier.
CREATE TEMP TABLE check_summary ON COMMIT DROP AS SELECT * FROM mart.reconciliation_proof_summary_current;
-- On fournit au planificateur les statistiques de pg_temp.check_source pour éviter des choix coûteux
-- sur cette copie de contrôle.
ANALYZE pg_temp.check_source;
-- On fournit au planificateur les statistiques de pg_temp.check_evidence pour éviter des choix coûteux
-- sur cette copie de contrôle.
ANALYZE pg_temp.check_evidence;
-- On fournit au planificateur les statistiques de pg_temp.check_proofs pour éviter des choix coûteux
-- sur cette copie de contrôle.
ANALYZE pg_temp.check_proofs;
-- On fournit au planificateur les statistiques de pg_temp.check_summary pour éviter des choix coûteux
-- sur cette copie de contrôle.
ANALYZE pg_temp.check_summary;
DO $$ BEGIN RAISE NOTICE 'Etape 5/5 : assertions et affichage sur copies temporaires'; END $$;
DO $$
BEGIN
    -- L’enrichissement des acquisitions ne doit changer ni leur nombre ni leur granularité.
    IF (SELECT COUNT(*) FROM pg_temp.check_evidence)
       <> (SELECT COUNT(*) FROM pg_temp.check_source) THEN
        RAISE EXCEPTION 'Detail des preuves : nombre d acquisitions different de la source';
    END IF;
    -- Chaque acquisition doit retrouver 14 indicateurs et 14 clés différentes ; deux indicateurs
    -- identiques ne doivent pas masquer un indicateur absent.
    IF EXISTS (
        SELECT 1 FROM pg_temp.check_source a
        LEFT JOIN (
            SELECT vineyard_key,pipeline_execution_id,reconciliation_run_id,acquisition_id_normalise,
                   COUNT(*) AS n,COUNT(DISTINCT proof_key) AS keys
            FROM pg_temp.check_proofs
            GROUP BY vineyard_key,pipeline_execution_id,reconciliation_run_id,acquisition_id_normalise
        ) p USING (vineyard_key,pipeline_execution_id,reconciliation_run_id,acquisition_id_normalise)
        WHERE COALESCE(p.n,0)<>14 OR COALESCE(p.keys,0)<>14
    ) THEN
        RAISE EXCEPTION 'Catalogue de preuves incomplet pour une acquisition';
    END IF;
    -- On vérifie que la synthèse couvre toutes les lignes d’indicateurs du détail, sans en ajouter.
    IF (SELECT COALESCE(SUM(acquisition_count),0) FROM pg_temp.check_summary)
       <> (SELECT COUNT(*) FROM pg_temp.check_proofs) THEN
        RAISE EXCEPTION 'Somme des groupes de preuves differente du detail';
    END IF;
    -- Les catégories doivent se répartir tout le total de chaque indicateur, sans manque ni
    -- chevauchement.
    IF EXISTS (
        SELECT 1 FROM pg_temp.check_summary
        WHERE positive_proof_count+not_demonstrated_count+not_verifiable_count+
              verifiability_unknown_count+indicator_unknown_count+read_error_count+invalid_boolean_count<>acquisition_count
    ) THEN
        RAISE EXCEPTION 'Categories d interpretation non exhaustives';
    END IF;
    -- Une sortie impossible à vérifier doit rester dans cette catégorie, et non être présentée comme
    -- preuve positive ou absence.
    IF EXISTS (
        SELECT 1 FROM pg_temp.check_proofs
        WHERE requires_identified_passage AND passage_outputs_verifiable IS FALSE
          AND proof_interpretation<>'Non vérifiable : sorties de passage non attribuables ou non évaluables'
    ) THEN
        RAISE EXCEPTION 'Sortie non verifiable presentee comme preuve positive ou absence';
    END IF;
    -- Un texte renseigné mais non reconnu ne doit pas être converti silencieusement en false : on
    -- demande un diagnostic du détail.
    IF EXISTS (SELECT 1 FROM pg_temp.check_proofs
               WHERE recorded_boolean_value IS NULL AND NULLIF(btrim(recorded_text_value),'') IS NOT NULL) THEN
        RAISE EXCEPTION 'Valeur booléenne non reconnue dans les indicateurs : examiner le detail sans la transformer en false';
    END IF;
    -- On vérifie les accès utiles au dashboard sur les vues concernées, sans lui ouvrir les tables
    -- sources.
    IF NOT has_table_privilege('projet12_dashboard','mart.reconciliation_acquisition_evidence_current','SELECT')
       OR NOT has_table_privilege('projet12_dashboard','mart.reconciliation_acquisition_proof_current','SELECT')
       OR NOT has_table_privilege('projet12_dashboard','mart.reconciliation_proof_summary_current','SELECT') THEN
        RAISE EXCEPTION 'Lecture dashboard manquante pour les nouvelles vues';
    END IF;
    RAISE NOTICE 'OK : volumes, interpretations des preuves et droits dashboard conformes.';
END $$;
-- On rend les copies temporaires lisibles pour le contrôle final sous le compte dashboard, sans ouvrir
-- de nouvelles tables permanentes.
GRANT SELECT ON pg_temp.check_source, pg_temp.check_evidence, pg_temp.check_proofs, pg_temp.check_summary TO projet12_dashboard;
-- On exécute les lectures suivantes avec les droits effectifs de projet12_dashboard, et non ceux du
-- compte administrateur.
SET LOCAL ROLE projet12_dashboard;
SELECT current_database() AS base,current_user AS role_effectif;
SELECT recorded_excel_perimeter AS perimetre,COUNT(*) AS acquisitions,
       COUNT(*) FILTER (WHERE acquisition_review_candidate IS TRUE) AS a_verifier
FROM pg_temp.check_evidence
GROUP BY recorded_excel_perimeter ORDER BY recorded_excel_perimeter;
SELECT proof_label AS indicateur,SUM(acquisition_count) AS acquisitions_production,
       SUM(positive_proof_count) AS preuve_positive,
       SUM(not_demonstrated_count) AS preuve_non_demontree,
       SUM(not_verifiable_count) AS sorties_non_verifiables,
       SUM(verifiability_unknown_count+indicator_unknown_count) AS information_non_renseignee,
       SUM(read_error_count) AS erreur_lecture
FROM pg_temp.check_summary
WHERE recorded_excel_perimeter='Production'
GROUP BY proof_key,proof_label ORDER BY proof_key;
SELECT vineyard_name AS vignoble,
       COUNT(*) FILTER (WHERE raw_folder_present IS TRUE AND processing_folder_present IS FALSE) AS brut_present_processing_non_demontre,
       COUNT(*) FILTER (WHERE processing_folder_present IS TRUE AND webp_both_sides IS FALSE) AS processing_present_webp_complets_non_demontres
FROM pg_temp.check_evidence
WHERE recorded_excel_perimeter='Production' GROUP BY vineyard_name ORDER BY vineyard_name;
SELECT vineyard_name AS vignoble,recorded_processing_category AS traitement,
       recorded_relationship_category AS rattachement,
       recorded_processing_next_action AS action_traitement_enregistree,
       recorded_relationship_next_action AS action_rattachement_enregistree,
       COUNT(*) AS acquisitions_a_examiner,
       ARRAY_AGG(acquisition_id_normalise ORDER BY acquisition_id_normalise) AS identifiants_concernes
FROM pg_temp.check_evidence
WHERE acquisition_review_candidate IS TRUE
GROUP BY vineyard_name,recorded_processing_category,recorded_relationship_category,
         recorded_processing_next_action,recorded_relationship_next_action
ORDER BY vineyard_name,recorded_processing_category;
SELECT DISTINCT vineyard_name AS vignoble,distinct_nas_observations_retained AS observations_nas_du_vignoble,
       evolution_comparison_explanation AS comparaison_evolution
FROM pg_temp.check_evidence ORDER BY vineyard_name;
-- On annule la transaction de diagnostic et on libère ses verrous ; aucune ligne métier n’est chargée
-- par ce contrôle.
ROLLBACK;
