-- Tester les permissions de chargement sans importer de lot.
-- On vérifie les droits du groupe, on lit les 20 tables prévues et on tente de prendre les verrous
-- utilisés pour l’activation.
-- ROLLBACK libère les verrous de cette transaction ; aucune insertion d’essai n’est effectuée.

-- On garde les contrôles et les changements temporaires dans une seule transaction, annulée à la fin.
BEGIN;
SELECT rolname, rolcanlogin AS connexion_autorisee, rolsuper AS superutilisateur,
       rolcreatedb AS creation_base, rolcreaterole AS creation_role,
       rolreplication AS replication, rolbypassrls AS contourne_rls
FROM pg_roles WHERE rolname='projet12_import_writer';
DO $rights$
DECLARE t text; obj record; col record;
BEGIN
    -- On contrôle que projet12_import_writer ne peut pas créer librement des objets via le droit
    -- CREATE sur la base.
    IF has_database_privilege('projet12_import_writer', current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'CREATE sur la base interdit pour le groupe de chargement';
    END IF;
    FOR t IN SELECT nspname FROM pg_namespace WHERE nspname IN ('core','staging','mart','public') LOOP
        -- On refuse aussi CREATE au niveau de chaque schéma contrôlé : un groupe limité ne doit pas
        -- pouvoir y ajouter ses propres objets.
        IF has_schema_privilege('projet12_import_writer', t, 'CREATE') THEN
            RAISE EXCEPTION 'CREATE interdit sur le schema %', t;
        END IF;
    END LOOP;
    -- On passe sur les 20 tables prévues pour le chargement, avec la même liste explicite que celle
    -- des permissions accordées.
    FOREACH t IN ARRAY ARRAY['core.vineyards', 'core.excel_ingestion_runs', 'core.excel_versions', 'core.excel_ingestion_run_vineyards', 'core.excel_publications', 'core.excel_publication_versions', 'staging.excel_version_rows', 'staging.excel_publication_rows', 'core.excel_current_publication', 'core.pipeline_runs', 'core.nas_observation_runs', 'core.reconciliation_runs', 'core.pipeline_artifacts', 'staging.nas_acquisition_observations', 'staging.nas_passage_observations', 'staging.nas_association_observations', 'staging.reconciliation_acquisition_rows', 'staging.reconciliation_passage_rows', 'staging.reconciliation_association_rows', 'core.current_vineyard_reconciliations'] LOOP
        -- Le chargement a besoin des deux droits sur projet12_import_writer : relire l’historique pour
        -- le comparer et ajouter les nouveaux enregistrements.
        IF NOT has_table_privilege('projet12_import_writer',t,'SELECT')
           OR NOT has_table_privilege('projet12_import_writer',t,'INSERT') THEN
            RAISE EXCEPTION 'Lecture ou insertion manquante sur %', t;
        END IF;
    END LOOP;
    FOR obj IN SELECT c.oid,n.nspname,c.relname,c.relowner FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('core','staging','mart') AND c.relkind IN ('r','p','v','m','f') LOOP
        -- Posséder une table donnerait des pouvoirs au-delà des GRANT prévus ; projet12_import_writer
        -- ne doit donc pas être son propriétaire.
        IF obj.relowner=(SELECT oid FROM pg_roles WHERE rolname='projet12_import_writer') THEN
            RAISE EXCEPTION 'Le groupe ne doit pas posseder %.%',obj.nspname,obj.relname;
        END IF;
        -- On recherche les permissions qui permettraient de supprimer, réécrire ou gérer les objets
        -- au-delà du rôle prévu pour projet12_import_writer.
        IF has_table_privilege('projet12_import_writer',obj.oid,'DELETE')
           OR has_table_privilege('projet12_import_writer',obj.oid,'TRUNCATE')
           OR has_table_privilege('projet12_import_writer',obj.oid,'TRIGGER')
           OR has_table_privilege('projet12_import_writer',obj.oid,'REFERENCES') THEN
            RAISE EXCEPTION 'Permission excessive sur %.%',obj.nspname,obj.relname;
        END IF;
        -- On interdit UPDATE sur une table entière ; seules les autorisations de colonne des liens
        -- courants sont prévues.
        IF has_table_privilege('projet12_import_writer',obj.oid,'UPDATE') THEN
            RAISE EXCEPTION 'UPDATE global interdit sur %.%',obj.nspname,obj.relname;
        END IF;
        -- Les permissions de colonne sont examinées en plus de celles de table, en ignorant les
        -- attributs système et les colonnes supprimées.
        FOR col IN SELECT attnum,attname FROM pg_attribute
                   WHERE attrelid=obj.oid AND attnum>0 AND NOT attisdropped LOOP
            -- On inspecte les droits colonne par colonne : seules celles des deux liens courants
            -- figurent dans l’exception autorisée.
            IF has_column_privilege('projet12_import_writer',obj.oid,col.attnum,'UPDATE')
               AND NOT ((obj.nspname='core' AND obj.relname='excel_current_publication'
                         AND col.attname IN ('publication_id','activated_in_database_at'))
                     OR (obj.nspname='core' AND obj.relname='current_vineyard_reconciliations'
                         AND col.attname IN ('pipeline_execution_id','reconciliation_run_id','activated_in_database_at'))) THEN
                RAISE EXCEPTION 'UPDATE de colonne interdit sur %.%.%',obj.nspname,obj.relname,col.attname;
            END IF;
        END LOOP;
        -- Le groupe d’import n’a pas à insérer dans les objets de présentation mart ; son périmètre
        -- d’écriture reste core et staging.
        IF obj.nspname='mart' AND
            (has_table_privilege('projet12_import_writer',obj.oid,'INSERT')
             OR has_any_column_privilege('projet12_import_writer',obj.oid,'INSERT')) THEN
            RAISE EXCEPTION 'INSERT interdit sur mart.%',obj.relname;
        END IF;
    END LOOP;
    -- On vérifie l’autre côté de la règle : tous les champs nécessaires à l’activation doivent être
    -- modifiables, pas seulement une partie d’entre eux.
    IF NOT has_column_privilege('projet12_import_writer','core.excel_current_publication','publication_id','UPDATE')
       OR NOT has_column_privilege('projet12_import_writer','core.excel_current_publication','activated_in_database_at','UPDATE')
       OR NOT has_column_privilege('projet12_import_writer','core.current_vineyard_reconciliations','pipeline_execution_id','UPDATE')
       OR NOT has_column_privilege('projet12_import_writer','core.current_vineyard_reconciliations','reconciliation_run_id','UPDATE')
       OR NOT has_column_privilege('projet12_import_writer','core.current_vineyard_reconciliations','activated_in_database_at','UPDATE') THEN
        RAISE EXCEPTION 'Mise a jour des pointeurs incomplete';
    END IF;
END $rights$;
-- On exécute les lectures suivantes avec les droits effectifs de projet12_import_writer, et non ceux
-- du compte administrateur.
SET LOCAL ROLE projet12_import_writer;
-- On limite l’attente des verrous ; un dépassement demande un diagnostic, pas une suppression aveugle
-- des verrous.
SET LOCAL lock_timeout='10s';
SELECT current_database() AS base, current_user AS role_effectif;
-- On prend le verrou transactionnel commun aux chargements pour vérifier son accès. Il sera libéré au
-- ROLLBACK, sans supprimer de verrou local du workflow.
SELECT pg_advisory_xact_lock(120026,1);
DO $read$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['core.vineyards', 'core.excel_ingestion_runs', 'core.excel_versions', 'core.excel_ingestion_run_vineyards', 'core.excel_publications', 'core.excel_publication_versions', 'staging.excel_version_rows', 'staging.excel_publication_rows', 'core.excel_current_publication', 'core.pipeline_runs', 'core.nas_observation_runs', 'core.reconciliation_runs', 'core.pipeline_artifacts', 'staging.nas_acquisition_observations', 'staging.nas_passage_observations', 'staging.nas_association_observations', 'staging.reconciliation_acquisition_rows', 'staging.reconciliation_passage_rows', 'staging.reconciliation_association_rows', 'core.current_vineyard_reconciliations'] LOOP
        -- On tente une lecture effective de chaque table ; LIMIT 1 suffit à vérifier l’accès sans
        -- charger son contenu complet.
        EXECUTE format('SELECT * FROM %s LIMIT 1', t);
    END LOOP;
    RAISE NOTICE 'OK : lecture des 20 tables et acquisition du verrou commun.';
END $read$;
-- On vérifie que le compte peut verrouiller les lignes des liens courants, sans en modifier la valeur.
SELECT singleton, publication_id FROM core.excel_current_publication FOR UPDATE;
SELECT vineyard_key, pipeline_execution_id, reconciliation_run_id
FROM core.current_vineyard_reconciliations ORDER BY vineyard_key FOR UPDATE;
SELECT COUNT(*) AS bilans_actifs FROM core.current_vineyard_reconciliations;
SELECT COUNT(*) AS lignes_excel_publication FROM staging.excel_publication_rows;
SELECT COUNT(*) AS lignes_acquisitions_rapprochement_historique FROM staging.reconciliation_acquisition_rows;
-- On annule la transaction de diagnostic et on libère ses verrous ; aucune ligne métier n’est chargée
-- par ce contrôle.
ROLLBACK;
