-- Créer le journal métier des tentatives du workflow.
-- Il est stocké dans suivi_acquisitions ; les runs et états techniques d’Airflow sont dans
-- airflow_meta.
-- On ajoute des événements au carnet au lieu de corriger ceux déjà écrits. Un événement d’étape réussi
-- ne suffit pas à déclarer la réussite de tout le workflow.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;
-- On limite l’attente des verrous ; un dépassement demande un diagnostic, pas une suppression aveugle
-- des verrous.
SET LOCAL lock_timeout = '5s';
DO $$ BEGIN
    -- On refuse d’appliquer ce script dans une autre base que suivi_acquisitions ; airflow_meta ne
    -- contient pas ces objets métier.
    IF current_database()<>'suivi_acquisitions' OR current_user<>'projet12_admin' THEN
        RAISE EXCEPTION 'Utiliser projet12_admin dans suivi_acquisitions';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='projet12_import_writer')
      OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='projet12_mart_reader') THEN
        RAISE EXCEPTION 'Groupes import/lecture absents';
    END IF;
    IF to_regclass('core.workflow_execution_events') IS NOT NULL THEN
        RAISE EXCEPTION 'Journal deja present : ne pas rejouer la creation comme une migration';
    END IF;
END $$;

-- On garde une ligne par événement : début du workflow, progression d’une étape ou incident. Les
-- tentatives en échec doivent aussi rester visibles. Les liens de lots sont facultatifs pour pouvoir
-- enregistrer un échec survenu avant leur chargement.
CREATE TABLE core.workflow_execution_events (
    -- Cet UUID reste stable si le même événement est retransmis ; il permet de le reconnaître sans
    -- créer une nouvelle tentative.
    event_id uuid PRIMARY KEY,
    -- On rattache les événements à la tentative du workflow, distincte des identifiants des lots Excel
    -- et NAS.
    workflow_execution_id uuid NOT NULL,
    -- Le producteur attribue un rang positif. L’unicité évite deux rangs identiques dans un run, mais
    -- n’impose pas à elle seule une séquence sans trou.
    event_sequence integer NOT NULL CHECK (event_sequence>0),
    -- On garde l’instant annoncé par le producteur, même si l’événement arrive plus tard en base.
    occurred_at timestamptz NOT NULL,
    -- On date séparément l’arrivée en base, notamment lors de la retransmission d’un journal local.
    recorded_in_database_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- On conserve l’origine du lancement pour distinguer script manuel, tâche Airflow et essai
    -- d’intégration.
    trigger_mode text NOT NULL CHECK (trigger_mode IN ('manual_script','airflow_manual','airflow_scheduled','integration_test')),
    -- Le type distingue un événement global, une étape et un contrôle de qualité.
    event_type text NOT NULL CHECK (event_type IN ('workflow','step','quality')),
    -- On indique l’étape du carnet concernée par cet événement, sans imposer ici une liste de huit
    -- noms.
    stage text NOT NULL CHECK (btrim(stage)<>''),
    -- On garde l’état de cet événement. Un success d’étape ne signifie pas que le workflow entier a
    -- réussi.
    status text NOT NULL CHECK (status IN ('started','running','success','failed','interrupted','skipped')),
    -- On prévoit un numéro de tentative positif ; sa valeur par défaut ne déclenche aucune relance.
    attempt_number integer NOT NULL DEFAULT 1 CHECK (attempt_number>0),
    -- On garde le périmètre déclaré de cette tentative sous forme d’objet JSON.
    scope_payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(scope_payload)='object'),
    -- On conserve les indicateurs de l’événement ; un objet vide reste possible si aucun indicateur
    -- n’est fourni.
    metrics_payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metrics_payload)='object'),
    excel_publication_id text,
    pipeline_execution_id text,
    -- Le message reste facultatif et borné à 2 000 caractères. Cette limite de taille ne retire pas
    -- automatiquement d’éventuels secrets.
    message text CHECK (message IS NULL OR length(message)<=2000),
    -- Le code d’erreur permet d’identifier le problème sans dépendre uniquement d’un texte de journal.
    error_code text,
    -- On n’accepte que des chemins locaux sous data/ ou logs/, sans remontée .. ni séparateur Windows.
    log_relative_path text CHECK (log_relative_path IS NULL OR (
        log_relative_path ~ '^(data|logs)/' AND
        log_relative_path !~ '(^|/)\.\.(/|$)' AND position(chr(92) in log_relative_path)=0)),
    -- Une durée renseignée doit être positive ou nulle ; ce n’est pas un horodatage.
    duration_seconds numeric CHECK (duration_seconds IS NULL OR duration_seconds>=0),
    -- Un run ne peut pas avoir deux événements au même rang, même avec deux UUID différents.
    UNIQUE (workflow_execution_id,event_sequence)
);
CREATE INDEX workflow_execution_events_execution_time_idx
    ON core.workflow_execution_events(workflow_execution_id,occurred_at);
COMMENT ON TABLE core.workflow_execution_events IS
'Journal append-only des tentatives completes, etapes et controles. Vide a la creation. Pas une source de preuves metier. Sequence attribuee par le producteur local. Identifiants Excel/pilote optionnels sans FK pour pouvoir enregistrer un echec avant chargement ; leur presence ne prouve pas l existence en base. Messages sans secrets. Pas de droit applicatif UPDATE/DELETE/TRUNCATE.';
COMMENT ON COLUMN core.workflow_execution_events.occurred_at IS
'Instant de l evenement fourni par le producteur ; distinct de son insertion en base, notamment apres reprise d un journal local.';
COMMENT ON COLUMN core.workflow_execution_events.status IS
'Etat de cet evenement : success ne signifie pas conformite metier ou livraison. Seul un evenement workflow terminal exprime le resultat global declare par le pilote complet.';
COMMENT ON COLUMN core.workflow_execution_events.event_id IS
'Identifiant stable pour une retransmission. Une reprise doit comparer le contenu d un evenement existant ; ON CONFLICT DO NOTHING seul ne constitue pas un controle d idempotence.';

GRANT USAGE ON SCHEMA core TO projet12_import_writer;
-- On autorise la lecture et l’ajout dans ces tables. Aucun UPDATE de leur contenu historique n’est
-- accordé par cette instruction.
GRANT SELECT,INSERT ON core.workflow_execution_events TO projet12_import_writer;

CREATE VIEW mart.workflow_event_history AS
SELECT * FROM core.workflow_execution_events;
COMMENT ON VIEW mart.workflow_event_history IS
'Evenements de supervision, y compris controles de qualite lorsque event_type=quality. Aucun journal complet historique reconstitue automatiquement.';
CREATE VIEW mart.workflow_execution_current AS
-- On cherche le dernier événement par numéro de séquence ; une date seule ne suffit pas à départager
-- l’ordre du carnet.
WITH latest_event AS (
    -- On retient une ligne par workflow ; le tri par séquence décroissante détermine ici la dernière
    -- ligne.
    SELECT DISTINCT ON (workflow_execution_id) *
    FROM core.workflow_execution_events
    ORDER BY workflow_execution_id,event_sequence DESC
-- On cherche séparément le dernier événement global ; une étape réussie ne doit pas devenir une
-- réussite globale par défaut.
), latest_workflow AS (
    SELECT DISTINCT ON (workflow_execution_id) workflow_execution_id,status,occurred_at
    -- Seuls les événements explicitement globaux fournissent l’état déclaré du workflow.
    FROM core.workflow_execution_events WHERE event_type='workflow'
    ORDER BY workflow_execution_id,event_sequence DESC
-- La première date observée donne le début visible du carnet, sans prouver que le journal reçu est
-- complet.
), first_event AS (
    SELECT workflow_execution_id,MIN(occurred_at) AS first_event_at
    FROM core.workflow_execution_events GROUP BY workflow_execution_id
)
SELECT e.workflow_execution_id,e.trigger_mode,f.first_event_at,
       e.occurred_at AS last_event_at,e.recorded_in_database_at,
       e.event_sequence AS last_event_sequence,e.event_type AS last_event_type,
       e.stage AS last_event_stage,e.status AS last_event_status,
       w.status AS last_declared_workflow_status,w.occurred_at AS workflow_status_declared_at,
       e.attempt_number,e.scope_payload,e.metrics_payload,
       e.excel_publication_id,e.pipeline_execution_id,e.message,e.error_code,e.log_relative_path
FROM latest_event e LEFT JOIN latest_workflow w USING (workflow_execution_id)
JOIN first_event f USING (workflow_execution_id);
COMMENT ON VIEW mart.workflow_execution_current IS
'Dernier evenement par sequence et dernier etat global explicitement declare. Une etape success ne devient pas un succes global. Un demarrage sans fin reste sans resultat terminal ; aucune interruption deduite automatiquement. Premiere date observee, pas garantie d un journal complet. Pas de donnees implique aucune execution visible.';
-- On ouvre la consultation des objets listés au groupe lecteur ; les tables internes ne sont pas
-- ajoutées implicitement à ce périmètre.
GRANT SELECT ON mart.workflow_event_history,mart.workflow_execution_current TO projet12_mart_reader;
-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
