-- Vérifier les accès au journal sans y écrire d’événement d’essai.
-- L’importeur doit pouvoir lire et ajouter ; le dashboard doit passer par les vues de supervision.
-- Ce contrôle repère aussi des modes de déclenchement contradictoires pour une même exécution.

-- On garde les contrôles et les changements temporaires dans une seule transaction, annulée à la fin.
BEGIN;
-- On évite ici le coût de compilation JIT pour ces requêtes de création ou de contrôle.
SET LOCAL jit = off;
-- On borne le temps d’exécution d’une instruction de ce diagnostic pour ne pas laisser une lecture
-- bloquée indéfiniment.
SET LOCAL statement_timeout = '120s';
DO $$
DECLARE t oid := to_regclass('core.workflow_execution_events');
BEGIN
    -- On vérifie d’abord que la table du journal existe ; des permissions ne peuvent pas valider un
    -- journal absent.
    IF t IS NULL THEN RAISE EXCEPTION 'Journal absent'; END IF;
    -- L’importeur doit pouvoir consulter et ajouter les événements, sans dépendre du compte
    -- administrateur.
    IF NOT has_table_privilege('projet12_importer',t,'SELECT')
      OR NOT has_table_privilege('projet12_importer',t,'INSERT') THEN
        RAISE EXCEPTION 'Lecture/insertion importeur manquante';
    END IF;
    -- On refuse aussi les droits de colonne : interdire seulement UPDATE sur la table laisserait
    -- potentiellement passer une modification partielle.
    IF has_table_privilege('projet12_importer',t,'UPDATE') OR has_any_column_privilege('projet12_importer',t,'UPDATE')
      OR has_table_privilege('projet12_importer',t,'DELETE') OR has_table_privilege('projet12_importer',t,'TRUNCATE')
      OR has_table_privilege('projet12_importer',t,'TRIGGER') OR has_table_privilege('projet12_importer',t,'REFERENCES')
      OR has_any_column_privilege('projet12_importer',t,'REFERENCES') THEN
        RAISE EXCEPTION 'Privilege de modification historique ou gestion inattendu pour l importeur';
    END IF;
    -- Le dashboard doit passer par les vues du journal, sans lecture directe ni droits de gestion sur
    -- sa table.
    IF has_table_privilege('projet12_dashboard',t,'SELECT') OR has_any_column_privilege('projet12_dashboard',t,'SELECT')
      OR has_table_privilege('projet12_dashboard',t,'INSERT') OR has_any_column_privilege('projet12_dashboard',t,'INSERT')
      OR has_table_privilege('projet12_dashboard',t,'UPDATE') OR has_any_column_privilege('projet12_dashboard',t,'UPDATE')
      OR has_table_privilege('projet12_dashboard',t,'DELETE') OR has_table_privilege('projet12_dashboard',t,'TRUNCATE')
      OR has_table_privilege('projet12_dashboard',t,'TRIGGER') OR has_table_privilege('projet12_dashboard',t,'REFERENCES')
      OR has_any_column_privilege('projet12_dashboard',t,'REFERENCES') THEN
        RAISE EXCEPTION 'Acces direct ou droit de gestion inattendu pour le dashboard';
    END IF;
    -- On teste les deux accès utiles à l’interface : historique des événements et résumé courant des
    -- exécutions.
    IF NOT has_table_privilege('projet12_dashboard','mart.workflow_event_history','SELECT')
       OR NOT has_table_privilege('projet12_dashboard','mart.workflow_execution_current','SELECT') THEN
        RAISE EXCEPTION 'Lecture des vues de supervision manquante';
    END IF;
    -- Les événements d’un même workflow doivent conserver la même origine de lancement ; on recherche
    -- les contradictions, pas seulement les doublons d’identifiant.
    IF EXISTS (SELECT 1 FROM core.workflow_execution_events
               GROUP BY workflow_execution_id HAVING COUNT(DISTINCT trigger_mode)>1) THEN
        RAISE EXCEPTION 'Modes de declenchement contradictoires pour une execution';
    END IF;
    RAISE NOTICE 'OK : journal append-only et droits de lecture/insertion conformes ; aucune insertion test executee';
END $$;
-- On exécute les lectures suivantes avec les droits effectifs de projet12_importer, et non ceux du
-- compte administrateur.
SET LOCAL ROLE projet12_importer;
SELECT current_database() AS base,current_user AS role_effectif;
SELECT COUNT(*) AS evenements_deja_enregistres FROM core.workflow_execution_events;
-- On revient au rôle de session avant de prendre un autre rôle pour la seconde partie du diagnostic.
RESET ROLE;
-- On exécute les lectures suivantes avec les droits effectifs de projet12_dashboard, et non ceux du
-- compte administrateur.
SET LOCAL ROLE projet12_dashboard;
SELECT current_user AS role_effectif;
SELECT COUNT(*) AS evenements_visibles FROM mart.workflow_event_history;
SELECT COUNT(*) AS executions_visibles FROM mart.workflow_execution_current;
SELECT COUNT(*) AS vues_mart FROM pg_views WHERE schemaname='mart';
SELECT COUNT(*) AS bilans,SUM(acquisition_count) AS acquisitions,SUM(association_count) AS associations,SUM(passage_count) AS passages
FROM mart.reconciliation_vineyard_current;
-- On annule la transaction de diagnostic et on libère ses verrous ; aucune ligne métier n’est chargée
-- par ce contrôle.
ROLLBACK;
