-- Créer le compte de connexion du dashboard et lui transmettre les droits du groupe lecteur.
-- Le mot de passe se définit séparément, jamais dans ce fichier.
-- Le mode lecture seule est un réglage par défaut ; les vérifications de permissions restent
-- nécessaires pour limiter réellement les accès.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;
DO $checks$
DECLARE
    login_oid oid;
BEGIN
    -- On refuse d’appliquer ce script dans une autre base que suivi_acquisitions ; airflow_meta ne
    -- contient pas ces objets métier.
    IF current_database() <> 'suivi_acquisitions' THEN
        RAISE EXCEPTION 'Base incorrecte : utiliser suivi_acquisitions.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'projet12_mart_reader') THEN
        RAISE EXCEPTION 'Role lecteur absent : executer 006 et verifier 007 avant de continuer.';
    END IF;
    SELECT oid INTO login_oid FROM pg_roles WHERE rolname = 'projet12_dashboard';
    -- On crée le rôle seulement s’il manque ; s’il existe déjà, la branche suivante doit en vérifier
    -- les attributs plutôt que les corriger silencieusement.
    IF login_oid IS NULL THEN
        -- On crée le compte qui pourra se connecter, en héritant du groupe prévu sans privilège
        -- d’administration.
        CREATE ROLE projet12_dashboard LOGIN INHERIT
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    ELSE
        -- Un rôle déjà présent doit correspondre au profil attendu ; on refuse de réutiliser
        -- silencieusement un compte plus puissant ou configuré autrement.
        IF EXISTS (SELECT 1 FROM pg_roles WHERE oid = login_oid AND
            (NOT rolcanlogin OR NOT rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) THEN
            RAISE EXCEPTION 'Compte existant avec attributs inattendus : examiner avant de continuer.';
        END IF;
        -- On vérifie les appartenances héritées, qui pourraient donner des droits supplémentaires même
        -- si les permissions directes semblent correctes.
        IF EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles parent ON parent.oid = m.roleid
            WHERE m.member = login_oid AND parent.rolname <> 'projet12_mart_reader') THEN
            RAISE EXCEPTION 'Compte deja membre d autres roles : examiner les permissions.';
        END IF;
    END IF;
END
$checks$;

-- On transmet au compte dashboard les permissions du groupe lecteur, sans lui attribuer de droits
-- d’écriture.
GRANT projet12_mart_reader TO projet12_dashboard;
-- Les nouvelles transactions du dashboard seront en lecture seule par défaut ; les droits SQL restent
-- la véritable limite d’accès.
ALTER ROLE projet12_dashboard SET default_transaction_read_only = on;
COMMENT ON ROLE projet12_dashboard IS
    'Projet 12 : connexion de consultation inheritee de projet12_mart_reader ; mot de passe defini separement, jamais dans ce fichier.';

DO $rights$
DECLARE obj record;
BEGIN
    -- On contrôle que projet12_dashboard ne peut pas créer librement des objets via le droit CREATE
    -- sur la base.
    IF has_database_privilege('projet12_dashboard', current_database(), 'CREATE') THEN
        RAISE EXCEPTION 'CREATE sur la base interdit pour ce compte.';
    END IF;
    FOR obj IN SELECT nspname FROM pg_namespace WHERE nspname IN ('core','staging','mart') LOOP
        -- On refuse aussi CREATE au niveau de chaque schéma contrôlé : un groupe limité ne doit pas
        -- pouvoir y ajouter ses propres objets.
        IF has_schema_privilege('projet12_dashboard', obj.nspname, 'CREATE') THEN
            RAISE EXCEPTION 'CREATE sur le schema % interdit pour ce compte.', obj.nspname;
        END IF;
    END LOOP;
    FOR obj IN SELECT c.oid,n.nspname,c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('core','staging','mart') AND c.relkind IN ('r','p','v','m','f')
    LOOP
        IF has_table_privilege('projet12_dashboard',obj.oid,'INSERT')
            OR has_table_privilege('projet12_dashboard',obj.oid,'UPDATE')
            OR has_table_privilege('projet12_dashboard',obj.oid,'DELETE')
            OR has_table_privilege('projet12_dashboard',obj.oid,'TRUNCATE')
            OR has_any_column_privilege('projet12_dashboard',obj.oid,'INSERT')
            OR has_any_column_privilege('projet12_dashboard',obj.oid,'UPDATE') THEN
            RAISE EXCEPTION 'Permission d ecriture inattendue sur %.%',obj.nspname,obj.relname;
        END IF;
        -- On recherche même les droits SELECT accordés sur une colonne : le dashboard doit consulter
        -- les vues, pas contourner leur présentation en lisant core ou staging.
        IF obj.nspname IN ('core','staging') AND
            (has_table_privilege('projet12_dashboard',obj.oid,'SELECT')
             OR has_any_column_privilege('projet12_dashboard',obj.oid,'SELECT')) THEN
            RAISE EXCEPTION 'Lecture directe inattendue sur %.%',obj.nspname,obj.relname;
        END IF;
    END LOOP;
END
$rights$;
-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
