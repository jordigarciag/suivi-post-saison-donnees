-- Définir les droits du groupe de chargement.
-- On autorise la lecture et l’insertion dans les tables prévues, mais pas la réécriture de leur
-- historique.
-- Seuls les champs des deux liens vers le résultat courant peuvent être modifiés. Le compte de
-- connexion sera créé dans le script 017.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;
DO $role$
BEGIN
    -- On refuse d’appliquer ce script dans une autre base que suivi_acquisitions ; airflow_meta ne
    -- contient pas ces objets métier.
    IF current_database() <> 'suivi_acquisitions' THEN
        RAISE EXCEPTION 'Base incorrecte : utiliser suivi_acquisitions';
    END IF;
    -- Un rôle déjà présent doit correspondre au profil attendu ; on refuse de réutiliser
    -- silencieusement un compte plus puissant ou configuré autrement.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='projet12_import_writer') THEN
        -- On crée un groupe de droits sans connexion directe ni capacité d’administrer les bases ou
        -- les rôles.
        CREATE ROLE projet12_import_writer NOLOGIN INHERIT
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='projet12_import_writer'
        AND (rolcanlogin OR NOT rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) THEN
        RAISE EXCEPTION 'Groupe existant avec attributs inattendus';
    END IF;
    -- On vérifie les appartenances héritées, qui pourraient donner des droits supplémentaires même si
    -- les permissions directes semblent correctes.
    IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member=
        (SELECT oid FROM pg_roles WHERE rolname='projet12_import_writer')) THEN
        RAISE EXCEPTION 'Le groupe importe des permissions d autres roles : examen requis';
    END IF;
END $role$;
GRANT CONNECT ON DATABASE suivi_acquisitions TO projet12_import_writer;
GRANT USAGE ON SCHEMA core, staging TO projet12_import_writer;
-- On autorise la lecture et l’ajout dans ces tables. Aucun UPDATE de leur contenu historique n’est
-- accordé par cette instruction.
GRANT SELECT, INSERT ON
    core.vineyards,
    core.excel_ingestion_runs,
    core.excel_versions,
    core.excel_ingestion_run_vineyards,
    core.excel_publications,
    core.excel_publication_versions,
    staging.excel_version_rows,
    staging.excel_publication_rows,
    core.excel_current_publication,
    core.pipeline_runs,
    core.nas_observation_runs,
    core.reconciliation_runs,
    core.pipeline_artifacts,
    staging.nas_acquisition_observations,
    staging.nas_passage_observations,
    staging.nas_association_observations,
    staging.reconciliation_acquisition_rows,
    staging.reconciliation_passage_rows,
    staging.reconciliation_association_rows,
    core.current_vineyard_reconciliations
TO projet12_import_writer;
-- On autorise seulement le déplacement du marque-page Excel et sa date, pas la modification des
-- anciennes publications.
GRANT UPDATE (publication_id, activated_in_database_at)
    ON core.excel_current_publication TO projet12_import_writer;
-- Même principe pour les bilans par domaine : seuls l’exécution ciblée, le rapprochement et la date
-- d’activation peuvent changer.
GRANT UPDATE (pipeline_execution_id, reconciliation_run_id, activated_in_database_at)
    ON core.current_vineyard_reconciliations TO projet12_import_writer;
COMMENT ON ROLE projet12_import_writer IS
'Groupe technique NOLOGIN pour chargements Excel et NAS : lecture/insertion, mise a jour limitee aux pointeurs. Aucun UPDATE des historiques, DELETE, TRUNCATE ou DDL. Un compte de chargement sera cree separement. Les importeurs doivent etre adaptes aux permissions avant utilisation.';
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
-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
