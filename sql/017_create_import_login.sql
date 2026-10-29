-- Créer le compte technique des importeurs Excel et NAS.
-- Il hérite de projet12_import_writer, sans appartenir à un autre groupe ni pouvoir déléguer ce rôle.
-- On vérifie aussi ses permissions effectives : une appartenance correcte ne suffirait pas si des
-- droits excessifs existaient déjà ailleurs.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;
DO $account$
DECLARE group_oid oid; account_oid oid;
BEGIN
    -- On refuse d’appliquer ce script dans une autre base que suivi_acquisitions ; airflow_meta ne
    -- contient pas ces objets métier.
    IF current_database() <> 'suivi_acquisitions' THEN
        RAISE EXCEPTION 'Base incorrecte : utiliser suivi_acquisitions';
    END IF;
    SELECT oid INTO group_oid FROM pg_roles WHERE rolname='projet12_import_writer';
    -- Le compte ne peut pas être créé sans son groupe de droits contrôlé ; il faut préparer 015 et
    -- vérifier 016 auparavant.
    IF group_oid IS NULL THEN
        RAISE EXCEPTION 'Groupe de chargement absent : executer 015 et verifier 016';
    END IF;
    -- Un rôle déjà présent doit correspondre au profil attendu ; on refuse de réutiliser
    -- silencieusement un compte plus puissant ou configuré autrement.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE oid=group_oid
        AND (rolcanlogin OR NOT rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
       OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member=group_oid) THEN
        RAISE EXCEPTION 'Attributs ou appartenances inattendus du groupe de chargement';
    END IF;
    SELECT oid INTO account_oid FROM pg_roles WHERE rolname='projet12_importer';
    -- On crée le rôle seulement s’il manque ; s’il existe déjà, la branche suivante doit en vérifier
    -- les attributs plutôt que les corriger silencieusement.
    IF account_oid IS NULL THEN
        -- On crée le compte qui pourra se connecter, en héritant du groupe prévu sans privilège
        -- d’administration.
        CREATE ROLE projet12_importer LOGIN INHERIT
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    ELSE
        IF EXISTS (SELECT 1 FROM pg_roles WHERE oid=account_oid
            AND (NOT rolcanlogin OR NOT rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) THEN
            RAISE EXCEPTION 'Compte existant avec attributs inattendus';
        END IF;
        -- On vérifie les appartenances héritées, qui pourraient donner des droits supplémentaires même
        -- si les permissions directes semblent correctes.
        IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member=account_oid
            AND (roleid<>group_oid OR admin_option)) THEN
            RAISE EXCEPTION 'Compte membre d autres roles ou avec delegation administrative : examen requis';
        END IF;
    END IF;
END $account$;
-- Le compte importeur hérite du groupe de chargement ; on évite de recopier séparément ses
-- permissions.
GRANT projet12_import_writer TO projet12_importer;
-- L’importeur doit pouvoir ouvrir une transaction de chargement ; ce réglage n’ajoute aucun droit sur
-- les tables.
ALTER ROLE projet12_importer SET default_transaction_read_only=off;
COMMENT ON ROLE projet12_importer IS
'Connexion technique pour importeurs Excel et NAS, membre de projet12_import_writer. Mot de passe defini separement. Pas de modification des historiques ni de suppression metier ; activation par mise a jour limitee des pointeurs.';
DO $rights$
DECLARE t text; obj record; col record;
BEGIN
    -- On contrôle que projet12_importer ne peut pas créer librement des objets via le droit CREATE sur
    -- la base.
    IF has_database_privilege('projet12_importer', current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'CREATE sur la base interdit pour le groupe de chargement';
    END IF;
    FOR t IN SELECT nspname FROM pg_namespace WHERE nspname IN ('core','staging','mart','public') LOOP
        -- On refuse aussi CREATE au niveau de chaque schéma contrôlé : un groupe limité ne doit pas
        -- pouvoir y ajouter ses propres objets.
        IF has_schema_privilege('projet12_importer', t, 'CREATE') THEN
            RAISE EXCEPTION 'CREATE interdit sur le schema %', t;
        END IF;
    END LOOP;
    -- On passe sur les 20 tables prévues pour le chargement, avec la même liste explicite que celle
    -- des permissions accordées.
    FOREACH t IN ARRAY ARRAY['core.vineyards', 'core.excel_ingestion_runs', 'core.excel_versions', 'core.excel_ingestion_run_vineyards', 'core.excel_publications', 'core.excel_publication_versions', 'staging.excel_version_rows', 'staging.excel_publication_rows', 'core.excel_current_publication', 'core.pipeline_runs', 'core.nas_observation_runs', 'core.reconciliation_runs', 'core.pipeline_artifacts', 'staging.nas_acquisition_observations', 'staging.nas_passage_observations', 'staging.nas_association_observations', 'staging.reconciliation_acquisition_rows', 'staging.reconciliation_passage_rows', 'staging.reconciliation_association_rows', 'core.current_vineyard_reconciliations'] LOOP
        -- Le chargement a besoin des deux droits sur projet12_importer : relire l’historique pour le
        -- comparer et ajouter les nouveaux enregistrements.
        IF NOT has_table_privilege('projet12_importer',t,'SELECT')
           OR NOT has_table_privilege('projet12_importer',t,'INSERT') THEN
            RAISE EXCEPTION 'Lecture ou insertion manquante sur %', t;
        END IF;
    END LOOP;
    FOR obj IN SELECT c.oid,n.nspname,c.relname,c.relowner FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('core','staging','mart') AND c.relkind IN ('r','p','v','m','f') LOOP
        -- Posséder une table donnerait des pouvoirs au-delà des GRANT prévus ; projet12_importer ne
        -- doit donc pas être son propriétaire.
        IF obj.relowner=(SELECT oid FROM pg_roles WHERE rolname='projet12_importer') THEN
            RAISE EXCEPTION 'Le groupe ne doit pas posseder %.%',obj.nspname,obj.relname;
        END IF;
        -- On recherche les permissions qui permettraient de supprimer, réécrire ou gérer les objets
        -- au-delà du rôle prévu pour projet12_importer.
        IF has_table_privilege('projet12_importer',obj.oid,'DELETE')
           OR has_table_privilege('projet12_importer',obj.oid,'TRUNCATE')
           OR has_table_privilege('projet12_importer',obj.oid,'TRIGGER')
           OR has_table_privilege('projet12_importer',obj.oid,'REFERENCES') THEN
            RAISE EXCEPTION 'Permission excessive sur %.%',obj.nspname,obj.relname;
        END IF;
        -- On interdit UPDATE sur une table entière ; seules les autorisations de colonne des liens
        -- courants sont prévues.
        IF has_table_privilege('projet12_importer',obj.oid,'UPDATE') THEN
            RAISE EXCEPTION 'UPDATE global interdit sur %.%',obj.nspname,obj.relname;
        END IF;
        -- Les permissions de colonne sont examinées en plus de celles de table, en ignorant les
        -- attributs système et les colonnes supprimées.
        FOR col IN SELECT attnum,attname FROM pg_attribute
                   WHERE attrelid=obj.oid AND attnum>0 AND NOT attisdropped LOOP
            -- On inspecte les droits colonne par colonne : seules celles des deux liens courants
            -- figurent dans l’exception autorisée.
            IF has_column_privilege('projet12_importer',obj.oid,col.attnum,'UPDATE')
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
            (has_table_privilege('projet12_importer',obj.oid,'INSERT')
             OR has_any_column_privilege('projet12_importer',obj.oid,'INSERT')) THEN
            RAISE EXCEPTION 'INSERT interdit sur mart.%',obj.relname;
        END IF;
    END LOOP;
    -- On vérifie l’autre côté de la règle : tous les champs nécessaires à l’activation doivent être
    -- modifiables, pas seulement une partie d’entre eux.
    IF NOT has_column_privilege('projet12_importer','core.excel_current_publication','publication_id','UPDATE')
       OR NOT has_column_privilege('projet12_importer','core.excel_current_publication','activated_in_database_at','UPDATE')
       OR NOT has_column_privilege('projet12_importer','core.current_vineyard_reconciliations','pipeline_execution_id','UPDATE')
       OR NOT has_column_privilege('projet12_importer','core.current_vineyard_reconciliations','reconciliation_run_id','UPDATE')
       OR NOT has_column_privilege('projet12_importer','core.current_vineyard_reconciliations','activated_in_database_at','UPDATE') THEN
        RAISE EXCEPTION 'Mise a jour des pointeurs incomplete';
    END IF;
END $rights$;

SELECT rolname, rolcanlogin AS connexion_autorisee, rolsuper AS superutilisateur,
       rolcreatedb AS creation_base, rolcreaterole AS creation_role,
       rolreplication AS replication, rolbypassrls AS contourne_rls
FROM pg_roles WHERE rolname='projet12_importer';
SELECT member_role.rolname AS compte, parent_role.rolname AS groupe,
       m.admin_option AS peut_deleguer_le_groupe
FROM pg_auth_members m
JOIN pg_roles member_role ON member_role.oid=m.member
JOIN pg_roles parent_role ON parent_role.oid=m.roleid
WHERE member_role.rolname='projet12_importer';
-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
