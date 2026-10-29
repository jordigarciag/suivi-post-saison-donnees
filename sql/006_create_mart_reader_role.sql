-- Créer le groupe de droits de consultation, sans compte de connexion.
-- projet12_mart_reader est NOLOGIN : le dashboard héritera ensuite de ses permissions.
-- On autorise les six vues listées et on refuse les droits d’écriture ou de lecture directe des
-- couches internes.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;

DO $checks$
DECLARE
    expected_view text;
    reader_oid oid;
BEGIN
    -- On refuse d’appliquer ce script dans une autre base que suivi_acquisitions ; airflow_meta ne
    -- contient pas ces objets métier.
    IF current_database() <> 'suivi_acquisitions' THEN
        RAISE EXCEPTION 'Base incorrecte : executer dans suivi_acquisitions, pas dans une base de restauration.';
    END IF;
    FOREACH expected_view IN ARRAY ARRAY[
        'excel_vineyard_history', 'excel_vineyard_current',
        'reconciliation_vineyard_history', 'reconciliation_vineyard_current',
        'reconciliation_acquisition_current', 'reconciliation_passage_current'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'mart' AND c.relname = expected_view AND c.relkind = 'v'
        ) THEN
            RAISE EXCEPTION 'Vue attendue absente : mart.%', expected_view;
        END IF;
    END LOOP;

    SELECT oid INTO reader_oid FROM pg_roles WHERE rolname = 'projet12_mart_reader';
    -- On crée le rôle seulement s’il manque ; s’il existe déjà, la branche suivante doit en vérifier
    -- les attributs plutôt que les corriger silencieusement.
    IF reader_oid IS NULL THEN
        -- On crée un groupe de droits sans connexion directe ni capacité d’administrer les bases ou
        -- les rôles.
        CREATE ROLE projet12_mart_reader
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    ELSE
        -- Un rôle déjà présent doit correspondre au profil attendu ; on refuse de réutiliser
        -- silencieusement un compte plus puissant ou configuré autrement.
        IF EXISTS (
            SELECT 1 FROM pg_roles WHERE oid = reader_oid
            AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
        ) THEN
            RAISE EXCEPTION 'Role projet12_mart_reader existant avec des attributs inattendus : examiner avant de continuer.';
        END IF;
        -- On vérifie les appartenances héritées, qui pourraient donner des droits supplémentaires même
        -- si les permissions directes semblent correctes.
        IF EXISTS (SELECT 1 FROM pg_auth_members WHERE member = reader_oid) THEN
            RAISE EXCEPTION 'Role lecteur membre d un autre role : examiner les droits herites.';
        END IF;
    END IF;
END
$checks$;

GRANT CONNECT ON DATABASE suivi_acquisitions TO projet12_mart_reader;
GRANT USAGE ON SCHEMA mart TO projet12_mart_reader;
-- On ouvre la consultation des objets listés au groupe lecteur ; les tables internes ne sont pas
-- ajoutées implicitement à ce périmètre.
GRANT SELECT ON
    mart.excel_vineyard_history,
    mart.excel_vineyard_current,
    mart.reconciliation_vineyard_history,
    mart.reconciliation_vineyard_current,
    mart.reconciliation_acquisition_current,
    mart.reconciliation_passage_current
TO projet12_mart_reader;

COMMENT ON ROLE projet12_mart_reader IS
    'Projet 12 : groupe NOLOGIN pour lire les six vues mart autorisees. Pas un compte de connexion. Acces aux donnees internes, ne pas exposer publiquement.';

DO $rights$
DECLARE
    obj record;
BEGIN
    -- On contrôle que projet12_mart_reader ne peut pas créer librement des objets via le droit CREATE
    -- sur la base.
    IF has_database_privilege('projet12_mart_reader', current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'Le lecteur possede CREATE sur la base : verifier les permissions existantes.';
    END IF;
    FOR obj IN SELECT nspname FROM pg_namespace WHERE nspname IN ('core','staging','mart') LOOP
        -- On refuse aussi CREATE au niveau de chaque schéma contrôlé : un groupe limité ne doit pas
        -- pouvoir y ajouter ses propres objets.
        IF has_schema_privilege('projet12_mart_reader', obj.nspname, 'CREATE') THEN
            RAISE EXCEPTION 'Le lecteur peut creer des objets dans le schema %', obj.nspname;
        END IF;
    END LOOP;
    FOR obj IN
        SELECT c.oid, n.nspname, c.relname
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('core','staging','mart') AND c.relkind IN ('r','p','v','m','f')
    LOOP
        -- On recherche les permissions qui permettraient de supprimer, réécrire ou gérer les objets
        -- au-delà du rôle prévu pour projet12_mart_reader.
        IF has_table_privilege('projet12_mart_reader', obj.oid, 'INSERT')
           OR has_table_privilege('projet12_mart_reader', obj.oid, 'UPDATE')
           OR has_table_privilege('projet12_mart_reader', obj.oid, 'DELETE')
           OR has_table_privilege('projet12_mart_reader', obj.oid, 'TRUNCATE')
           OR has_any_column_privilege('projet12_mart_reader', obj.oid, 'INSERT')
           OR has_any_column_privilege('projet12_mart_reader', obj.oid, 'UPDATE') THEN
            RAISE EXCEPTION 'Droits d ecriture inattendus sur %.%', obj.nspname, obj.relname;
        END IF;
        -- On recherche même les droits SELECT accordés sur une colonne : le dashboard doit consulter
        -- les vues, pas contourner leur présentation en lisant core ou staging.
        IF obj.nspname IN ('core','staging') AND
            (has_table_privilege('projet12_mart_reader', obj.oid, 'SELECT')
             OR has_any_column_privilege('projet12_mart_reader', obj.oid, 'SELECT')) THEN
            RAISE EXCEPTION 'Lecture directe inattendue sur %.% : acces limite aux vues mart.', obj.nspname, obj.relname;
        END IF;
    END LOOP;
END
$rights$;

-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
