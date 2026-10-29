-- Vérifier que les vues historiques ne perdent ni ne multiplient les lignes.
-- On compare les volumes stockés, les volumes annoncés par bilan et les associations courantes.
-- Le dernier affichage cumule plusieurs observations : il ne compte pas nécessairement des
-- acquisitions ou passages uniques dans le temps.

-- On garde les contrôles et les changements temporaires dans une seule transaction, annulée à la fin.
BEGIN;
DO $$
BEGIN
    -- Le détail acquisition doit retrouver exactement le volume stocké ; une jointure pourrait sinon
    -- en supprimer ou en multiplier.
    IF (SELECT COUNT(*) FROM mart.reconciliation_acquisition_history)
       <> (SELECT COUNT(*) FROM staging.reconciliation_acquisition_rows) THEN
        RAISE EXCEPTION 'Historique acquisition : volume different des lignes stockees';
    END IF;
    -- On contrôle aussi chaque bilan séparément : un total global correct pourrait masquer deux
    -- erreurs qui se compensent.
    IF EXISTS (
        SELECT 1 FROM core.reconciliation_runs r
        LEFT JOIN (
            SELECT pipeline_execution_id, vineyard_key, reconciliation_run_id, COUNT(*) AS n
            FROM mart.reconciliation_acquisition_history
            GROUP BY pipeline_execution_id, vineyard_key, reconciliation_run_id
        ) d USING (pipeline_execution_id, vineyard_key, reconciliation_run_id)
        WHERE COALESCE(d.n,0) <> r.acquisition_rows
    ) THEN
        RAISE EXCEPTION 'Historique acquisition : volume different du declare pour un rapprochement';
    END IF;
    -- On vérifie qu’un passage stocké donne une ligne dans l’historique, sans multiplication par ses
    -- acquisitions associées.
    IF (SELECT COUNT(*) FROM mart.reconciliation_passage_history)
       <> (SELECT COUNT(*) FROM staging.reconciliation_passage_rows) THEN
        RAISE EXCEPTION 'Historique passage : volume different des lignes stockees';
    END IF;
    -- Les volumes de passages doivent correspondre aux déclarations de chaque rapprochement, pas
    -- seulement à leur somme.
    IF EXISTS (
        SELECT 1 FROM core.reconciliation_runs r
        LEFT JOIN (
            SELECT pipeline_execution_id, vineyard_key, reconciliation_run_id, COUNT(*) AS n
            FROM mart.reconciliation_passage_history
            GROUP BY pipeline_execution_id, vineyard_key, reconciliation_run_id
        ) d USING (pipeline_execution_id, vineyard_key, reconciliation_run_id)
        WHERE COALESCE(d.n,0) <> r.passage_rows
    ) THEN
        RAISE EXCEPTION 'Historique passage : volume different du declare pour un rapprochement';
    END IF;
    -- Toutes les associations stockées doivent apparaître une fois dans leur historique.
    IF (SELECT COUNT(*) FROM mart.reconciliation_association_history)
       <> (SELECT COUNT(*) FROM staging.reconciliation_association_rows) THEN
        RAISE EXCEPTION 'Historique association : volume different des lignes stockees';
    END IF;
    -- On recoupe le nombre de liens pour chaque bilan avec le nombre annoncé lors du chargement.
    IF EXISTS (
        SELECT 1 FROM core.reconciliation_runs r
        LEFT JOIN (
            SELECT pipeline_execution_id, vineyard_key, reconciliation_run_id, COUNT(*) AS n
            FROM mart.reconciliation_association_history
            GROUP BY pipeline_execution_id, vineyard_key, reconciliation_run_id
        ) d USING (pipeline_execution_id, vineyard_key, reconciliation_run_id)
        WHERE COALESCE(d.n,0) <> r.association_rows
    ) THEN
        RAISE EXCEPTION 'Historique association : volume different du declare pour un rapprochement';
    END IF;
    -- Le détail des liens actifs doit retrouver le compteur des bilans actifs ; les bilans historiques
    -- ne doivent pas s’y ajouter.
    IF (SELECT COUNT(*) FROM mart.reconciliation_association_current)
       <> (SELECT COALESCE(SUM(association_count),0) FROM mart.reconciliation_vineyard_current) THEN
        RAISE EXCEPTION 'Associations courantes : volume different du bilan courant';
    END IF;
    -- On confirme le droit du dashboard sur cette vue de détail ; être membre du groupe ne garantit
    -- pas qu’une nouvelle vue a été ajoutée à ses permissions.
    IF NOT has_table_privilege('projet12_dashboard', 'mart.reconciliation_acquisition_history', 'SELECT') THEN
        RAISE EXCEPTION 'Lecture dashboard manquante : reconciliation_acquisition_history';
    END IF;
    IF NOT has_table_privilege('projet12_dashboard', 'mart.reconciliation_passage_history', 'SELECT') THEN
        RAISE EXCEPTION 'Lecture dashboard manquante : reconciliation_passage_history';
    END IF;
    IF NOT has_table_privilege('projet12_dashboard', 'mart.reconciliation_association_history', 'SELECT') THEN
        RAISE EXCEPTION 'Lecture dashboard manquante : reconciliation_association_history';
    END IF;
    IF NOT has_table_privilege('projet12_dashboard', 'mart.reconciliation_association_current', 'SELECT') THEN
        RAISE EXCEPTION 'Lecture dashboard manquante : reconciliation_association_current';
    END IF;
    RAISE NOTICE 'OK : volumes historiques et associations courantes conformes ; droits dashboard presents.';
END $$;
-- On exécute les lectures suivantes avec les droits effectifs de projet12_dashboard, et non ceux du
-- compte administrateur.
SET LOCAL ROLE projet12_dashboard;
SELECT current_database() AS base, current_user AS role_effectif;
SELECT 'Historique : acquisitions' AS perimetre, COUNT(*) AS lignes FROM mart.reconciliation_acquisition_history
UNION ALL SELECT 'Historique : passages', COUNT(*) FROM mart.reconciliation_passage_history
UNION ALL SELECT 'Historique : associations', COUNT(*) FROM mart.reconciliation_association_history
UNION ALL SELECT 'Courant : associations', COUNT(*) FROM mart.reconciliation_association_current;
SELECT vineyard_name AS vignoble, COUNT(*) AS rapprochements_conserves,
       SUM(acquisition_count) AS acquisitions_cumulees,
       SUM(association_count) AS associations_cumulees,
       SUM(passage_count) AS passages_cumules
FROM mart.reconciliation_vineyard_history
GROUP BY vineyard_name ORDER BY vineyard_name;
-- On annule la transaction de diagnostic et on libère ses verrous ; aucune ligne métier n’est chargée
-- par ce contrôle.
ROLLBACK;
