-- Vérifier le groupe lecteur avec ses droits effectifs.
-- On affiche d’abord ses attributs et permissions, puis on essaie une lecture sous ce rôle.
-- La transaction finit par ROLLBACK : ce diagnostic ne charge aucune donnée métier.

-- On garde les contrôles et les changements temporaires dans une seule transaction, annulée à la fin.
BEGIN;

SELECT rolname, rolcanlogin AS connexion_autorisee,
       rolsuper AS superutilisateur, rolcreatedb AS creation_base,
       rolcreaterole AS creation_role, rolbypassrls AS contourne_rls
FROM pg_roles WHERE rolname = 'projet12_mart_reader';

SELECT n.nspname AS schema, c.relname AS objet,
    has_table_privilege('projet12_mart_reader', c.oid, 'SELECT') AS lecture,
    has_table_privilege('projet12_mart_reader', c.oid, 'INSERT') AS insertion,
    has_table_privilege('projet12_mart_reader', c.oid, 'UPDATE') AS modification,
    has_table_privilege('projet12_mart_reader', c.oid, 'DELETE') AS suppression
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE (n.nspname = 'mart' AND c.relkind = 'v')
   OR (n.nspname = 'core' AND c.relname = 'current_vineyard_reconciliations')
   OR (n.nspname = 'staging' AND c.relname = 'reconciliation_acquisition_rows')
ORDER BY n.nspname, c.relname;

-- On exécute les lectures suivantes avec les droits effectifs de projet12_mart_reader, et non ceux du
-- compte administrateur.
SET LOCAL ROLE projet12_mart_reader;
SELECT current_database() AS base, current_user AS role_effectif;
SELECT COUNT(*) AS bilans_courants,
       SUM(acquisition_count) AS acquisitions,
       SUM(association_count) AS associations,
       SUM(passage_count) AS passages
FROM mart.reconciliation_vineyard_current;

-- On annule la transaction de diagnostic et on libère ses verrous ; aucune ligne métier n’est chargée
-- par ce contrôle.
ROLLBACK;
