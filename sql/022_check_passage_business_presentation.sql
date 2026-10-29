-- Vérifier la présentation des passages sans changer leurs résultats.
-- On contrôle les volumes, l’unicité des clés, l’équivalence du nouvel alias technique et la présence
-- des explications.
-- Les affichages finaux sont réalisés avec les droits du dashboard ; la transaction est ensuite
-- annulée.

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
DO $$ BEGIN RAISE NOTICE 'Etape 1/3 : lecture des passages et des bilans'; END $$;
-- On fige les passages distincts du bilan actif dans check_business_passages pour la durée du
-- diagnostic. La table est temporaire, pas une nouvelle source métier.
CREATE TEMP TABLE check_business_passages ON COMMIT DROP AS SELECT * FROM mart.reconciliation_passage_current;
-- On fige les compteurs des bilans actifs dans check_business_vineyards pour la durée du diagnostic.
-- La table est temporaire, pas une nouvelle source métier.
CREATE TEMP TABLE check_business_vineyards ON COMMIT DROP AS SELECT * FROM mart.reconciliation_vineyard_current;
DO $$ BEGIN RAISE NOTICE 'Etape 2/3 : coherence des volumes, alias et permissions'; END $$;
DO $$
BEGIN
    -- Le détail des passages doit retrouver la somme des compteurs des bilans actifs.
    IF (SELECT COUNT(*) FROM pg_temp.check_business_passages) <> (SELECT COALESCE(SUM(passage_count),0) FROM pg_temp.check_business_vineyards) THEN
        RAISE EXCEPTION 'Nombre de passages different des bilans';
    END IF;
    -- La clé comprend domaine, exécution, rapprochement, parcelle et passage ; un nom de passage seul
    -- n’est pas unique.
    IF EXISTS (SELECT 1 FROM pg_temp.check_business_passages
       GROUP BY vineyard_key,pipeline_execution_id,reconciliation_run_id,parcel_name,passage_name HAVING COUNT(*)<>1) THEN
        RAISE EXCEPTION 'Cle passage dupliquee';
    END IF;
    -- Le nouvel alias doit reprendre strictement l’ancien critère lorsqu’il est vérifiable, et rester
    -- NULL sinon.
    IF EXISTS (SELECT 1 FROM pg_temp.check_business_passages
       WHERE vitiparcel_technical_criterion_satisfied IS DISTINCT FROM
         CASE WHEN vitiparcel_ready_verifiable IS TRUE THEN vitiparcel_ready_for_delivery ELSE NULL END) THEN
        RAISE EXCEPTION 'Alias technique different du critere original';
    END IF;
    -- Les trois explications doivent être présentes pour chaque passage : stocks, attente client et
    -- portée du passage.
    IF EXISTS (SELECT 1 FROM pg_temp.check_business_passages
        WHERE stocks_annotation_explanation IS NULL OR client_expectation_explanation IS NULL OR passage_scope_explanation IS NULL) THEN
        RAISE EXCEPTION 'Explication manquante';
    END IF;
    -- On vérifie les accès utiles au dashboard sur les vues concernées, sans lui ouvrir les tables
    -- sources.
    IF NOT has_table_privilege('projet12_dashboard','mart.reconciliation_passage_current','SELECT')
      OR NOT has_table_privilege('projet12_dashboard','mart.reconciliation_acquisition_proof_current','SELECT') THEN
        RAISE EXCEPTION 'Droit de lecture dashboard manquant';
    END IF;
    RAISE NOTICE 'OK : volumes, cle passage, alias technique et droits conformes';
END $$;
DO $$ BEGIN RAISE NOTICE 'Etape 3/3 : lecture directe des nouveaux champs sous le role dashboard'; END $$;
-- On exécute les lectures suivantes avec les droits effectifs de projet12_dashboard, et non ceux du
-- compte administrateur.
SET LOCAL ROLE projet12_dashboard;
SELECT current_database() AS base,current_user AS role_effectif;
SELECT stocks_annotation_explanation, COUNT(*) AS lignes_passages
FROM mart.reconciliation_passage_current GROUP BY 1 ORDER BY 1;
SELECT vitiparcel_technical_criterion_satisfied, COUNT(*) AS lignes_passages
FROM mart.reconciliation_passage_current GROUP BY 1 ORDER BY 1 NULLS LAST;
SELECT DISTINCT client_expectation_explanation,passage_scope_explanation FROM mart.reconciliation_passage_current;
SELECT proof_key,proof_label,COUNT(*) AS lignes_indicateur
FROM mart.reconciliation_acquisition_proof_current GROUP BY 1,2 ORDER BY 1;
-- On annule la transaction de diagnostic et on libère ses verrous ; aucune ligne métier n’est chargée
-- par ce contrôle.
ROLLBACK;
