-- Conserver les observations du NAS et les résultats de leur croisement avec Excel.
-- Chaque bilan garde les identifiants de ses deux sources. On doit pouvoir comprendre un ancien
-- résultat même si les suivis Excel changent ensuite.
-- Les observations restent ciblées sur le périmètre sélectionné : ce n’est pas un inventaire exhaustif
-- du NAS.


-- On regroupe les créations et les droits dans une même transaction.
BEGIN;

-- On décrit le lancement du parcours NAS et son lot Excel de départ. Le statut du programme ne dit
-- pas, à lui seul, si les livrables sont conformes.
CREATE TABLE IF NOT EXISTS core.pipeline_runs (
    -- On identifie l’exécution du parcours à laquelle cette ligne appartient ; la clé évite de
    -- mélanger deux lancements.
    pipeline_execution_id text PRIMARY KEY CHECK (btrim(pipeline_execution_id) <> ''),
    -- On enregistre la saison du traitement, avec une plage de valeurs autorisée pour écarter une
    -- année manifestement invalide.
    project_year integer NOT NULL CHECK (project_year BETWEEN 1900 AND 2200),
    -- On conserve l’état déclaré par le producteur. La contrainte impose ici un texte non vide, pas
    -- une liste fermée de statuts.
    status text NOT NULL CHECK (btrim(status) <> ''),
    -- On garde le début déclaré de l’exécution pour le comparer ensuite à sa fin.
    started_at timestamptz NOT NULL,
    -- Une fin non renseignée reste NULL ; on ne lui invente pas la date du chargement SQL.
    finished_at timestamptz,
    -- Le bilan reste attaché au lot Excel qui a servi à son calcul, même si une autre publication
    -- devient courante.
    excel_publication_id text NOT NULL REFERENCES core.excel_publications(publication_id),
    -- L’empreinte du tableau regroupé permet de vérifier qu’on utilise les mêmes données pendant les
    -- étapes du parcours.
    reference_sha256 text NOT NULL CHECK (reference_sha256 ~ '^[0-9a-f]{64}$'),
    -- Ce chemin retrouve la copie locale du tableau Excel retenu pour ce lancement, plutôt que sa
    -- version courante potentiellement modifiée.
    reference_snapshot_path text NOT NULL CHECK (btrim(reference_snapshot_path) <> ''),
    -- Le manifeste décrit le lot ; son chemin permet de retrouver le fichier contrôlé par le chargeur.
    manifest_path text NOT NULL CHECK (btrim(manifest_path) <> ''),
    -- Cette empreinte identifie les octets du manifeste. La contrainte vérifie sa forme, pas sa
    -- correspondance avec le fichier : celle-ci relève du chargeur.
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    -- On conserve l’identité des scripts annoncée pour cette exécution afin de contextualiser ses
    -- résultats.
    script_identity jsonb NOT NULL CHECK (jsonb_typeof(script_identity) = 'object'),
    -- On conserve aussi le contenu du manifeste pour comprendre ce qui a été annoncé lors du
    -- chargement.
    manifest_payload jsonb NOT NULL CHECK (jsonb_typeof(manifest_payload) = 'object'),
    -- Cette date vient de PostgreSQL au chargement ; elle ne remplace pas les dates d’ingestion, de
    -- contrôle ou de calcul fournies par le pipeline.
    loaded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (pipeline_execution_id, excel_publication_id),
    -- Une fin peut rester inconnue ; lorsqu’elle est fournie, elle ne doit pas précéder le début
    -- déclaré.
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);
COMMENT ON TABLE core.pipeline_runs IS
    'Executions locales du pilote, avec reference Excel, dates et manifeste ; succes technique distinct de la conformite metier.';

-- On rattache un contrôle NAS à un domaine et au périmètre Excel qui a guidé sa lecture.
CREATE TABLE IF NOT EXISTS core.nas_observation_runs (
    pipeline_execution_id text NOT NULL,
    -- La clé technique relie les lignes d’un même domaine entre les différentes tables.
    vineyard_key text NOT NULL,
    -- Cet identifiant désigne le contrôle des constats NAS, distinct du rapprochement qui les
    -- interprète ensuite.
    extraction_run_id text NOT NULL CHECK (btrim(extraction_run_id) <> ''),
    -- On garde le lot Excel qui a servi à choisir le périmètre de ce contrôle NAS.
    scope_excel_publication_id text NOT NULL,
    -- On précise la version du domaine dans ce lot, pour savoir quel suivi a guidé le contrôle.
    scope_excel_version_id text NOT NULL,
    -- On conserve la date du contrôle déclaré. Elle ne date pas individuellement la lecture ou la
    -- création de chaque fichier NAS.
    checked_at timestamptz NOT NULL,
    -- On conserve le nombre d’acquisitions annoncé pour ce lot ; les vues le compareront aux lignes
    -- stockées.
    acquisition_rows integer NOT NULL CHECK (acquisition_rows >= 0),
    -- Ce volume compte des liens acquisition–parcelle–passage, pas des acquisitions supplémentaires.
    association_rows integer NOT NULL CHECK (association_rows >= 0),
    -- Ce volume compte les passages distincts annoncés dans le lot.
    passage_rows integer NOT NULL CHECK (passage_rows >= 0),
    -- Le détail des métadonnées complète les champs structurés et permet de retrouver les informations
    -- du producteur.
    metadata_payload jsonb NOT NULL CHECK (jsonb_typeof(metadata_payload) = 'object'),
    loaded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pipeline_execution_id, vineyard_key),
    -- On exige que le périmètre Excel appartienne bien au lot déclaré ; une version connue dans un
    -- autre lot ne suffit pas.
    FOREIGN KEY (pipeline_execution_id, scope_excel_publication_id)
        REFERENCES core.pipeline_runs(pipeline_execution_id, excel_publication_id),
    FOREIGN KEY (scope_excel_publication_id, vineyard_key, scope_excel_version_id)
        REFERENCES core.excel_publication_versions(publication_id, vineyard_key, version_id)
);
COMMENT ON TABLE core.nas_observation_runs IS
    'Observations NAS live datees, avec perimetre Excel d origine ; pas un inventaire exhaustif du NAS.';
CREATE INDEX IF NOT EXISTS nas_observation_runs_vineyard_date_idx
    ON core.nas_observation_runs (vineyard_key, checked_at DESC);

-- On garde le lien entre un bilan calculé, l’observation NAS utilisée et la version Excel croisée. Ces
-- identifiants ne sont pas interchangeables.
CREATE TABLE IF NOT EXISTS core.reconciliation_runs (
    pipeline_execution_id text NOT NULL,
    vineyard_key text NOT NULL,
    -- On distingue chaque calcul de rapprochement pour un domaine et un lancement donnés.
    reconciliation_run_id text NOT NULL CHECK (btrim(reconciliation_run_id) <> ''),
    -- On garde l’exécution des observations NAS réellement utilisées ; elle ne doit pas être déduite
    -- du seul identifiant du bilan.
    nas_pipeline_execution_id text NOT NULL,
    excel_publication_id text NOT NULL,
    -- On précise la version Excel du domaine utilisée, pas seulement le lot global auquel elle
    -- appartient.
    excel_version_id text NOT NULL,
    -- On date le calcul du croisement Excel/NAS, séparément de la lecture des sources et du chargement
    -- SQL.
    reconciled_at timestamptz NOT NULL,
    acquisition_rows integer NOT NULL CHECK (acquisition_rows >= 0),
    association_rows integer NOT NULL CHECK (association_rows >= 0),
    passage_rows integer NOT NULL CHECK (passage_rows >= 0),
    -- On garde l’identité des règles appliquées lors du calcul ; un ancien classement ne sera pas
    -- silencieusement recalculé par une nouvelle vue.
    rules_identity jsonb NOT NULL CHECK (jsonb_typeof(rules_identity) = 'object'),
    metadata_payload jsonb NOT NULL CHECK (jsonb_typeof(metadata_payload) = 'object'),
    loaded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id),
    UNIQUE (pipeline_execution_id, vineyard_key, reconciliation_run_id, nas_pipeline_execution_id),
    FOREIGN KEY (pipeline_execution_id, excel_publication_id)
        REFERENCES core.pipeline_runs(pipeline_execution_id, excel_publication_id),
    -- Cette relation oblige le détail à utiliser le contrôle NAS déclaré par son bilan, pas une
    -- observation d’un autre lancement.
    FOREIGN KEY (nas_pipeline_execution_id, vineyard_key)
        REFERENCES core.nas_observation_runs(pipeline_execution_id, vineyard_key),
    FOREIGN KEY (excel_publication_id, vineyard_key, excel_version_id)
        REFERENCES core.excel_publication_versions(publication_id, vineyard_key, version_id)
);
COMMENT ON TABLE core.reconciliation_runs IS
    'Calculs historiques : quelle observation NAS et quelle version Excel ont servi a produire ce bilan.';
CREATE INDEX IF NOT EXISTS reconciliation_runs_vineyard_date_idx
    ON core.reconciliation_runs (vineyard_key, reconciled_at DESC);
CREATE INDEX IF NOT EXISTS reconciliation_runs_observation_idx
    ON core.reconciliation_runs (nas_pipeline_execution_id, vineyard_key);

-- On recense les CSV produits par le parcours : leur chemin, leur empreinte et leur volume. La table
-- ne contient pas leurs images ni leurs fichiers binaires.
CREATE TABLE IF NOT EXISTS core.pipeline_artifacts (
    pipeline_execution_id text NOT NULL REFERENCES core.pipeline_runs(pipeline_execution_id),
    vineyard_key text NOT NULL REFERENCES core.vineyards(vineyard_key),
    -- On distingue les fichiers d’observation NAS de ceux du rapprochement : leurs lignes n’expriment
    -- pas la même chose.
    stage text NOT NULL CHECK (stage IN ('nas_observation', 'reconciliation')),
    -- On précise si ce CSV contient des acquisitions, des associations ou des passages.
    artifact_kind text NOT NULL CHECK (artifact_kind IN ('acquisitions', 'associations', 'passages')),
    -- Ce chemin permet de retrouver le CSV produit pour cette étape et ce domaine.
    artifact_path text NOT NULL CHECK (btrim(artifact_path) <> ''),
    -- L’empreinte porte sur le contenu du CSV, pour détecter un changement après sa production.
    artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[0-9a-f]{64}$'),
    -- On garde la taille déclarée en octets ; elle ne peut pas être négative.
    artifact_size bigint NOT NULL CHECK (artifact_size >= 0),
    -- Ce compteur décrit les lignes du CSV, indépendamment de sa taille en octets.
    row_count integer NOT NULL CHECK (row_count >= 0),
    -- On date l’enregistrement de cette sortie en base, pas l’observation du NAS.
    registered_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (pipeline_execution_id, vineyard_key, stage, artifact_kind)
);
COMMENT ON TABLE core.pipeline_artifacts IS
    'Chemins, empreintes et comptages des CSV observes et rapproches, enregistres au chargement.';

-- On conserve les constats de lecture NAS par acquisition, avant leur interprétation avec le suivi
-- Excel.
CREATE TABLE IF NOT EXISTS staging.nas_acquisition_observations (
    pipeline_execution_id text NOT NULL,
    vineyard_key text NOT NULL,
    -- L’identifiant normalisé permet de relier la même acquisition entre le suivi Excel, les constats
    -- NAS et le bilan.
    acquisition_id_normalise text NOT NULL CHECK (btrim(acquisition_id_normalise) <> ''),
    -- On indique si les sorties de passage peuvent être vérifiées et attribuées. Il faut lire ce
    -- drapeau avant d’interpréter les résultats de présence.
    passage_outputs_verifiable boolean NOT NULL,
    -- On conserve le critère technique observé ; son nom ne prouve ni commande client ni livraison.
    -- Sans vérifiabilité, false ne suffit pas à conclure à une absence.
    vitiparcel_created boolean NOT NULL,
    -- On conserve le détail original dans un objet JSON ; les vues en extraient ensuite les champs
    -- utiles sans réécrire ce contenu.
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (pipeline_execution_id, vineyard_key, acquisition_id_normalise),
    FOREIGN KEY (pipeline_execution_id, vineyard_key)
        REFERENCES core.nas_observation_runs(pipeline_execution_id, vineyard_key)
);
COMMENT ON TABLE staging.nas_acquisition_observations IS
    'Preuves par acquisition et contexte d extraction ; un False non verifiable n est pas une absence prouvee.';

-- On garde une ligne par passage observé. Compter ces lignes évite de recompter les mêmes stocks pour
-- chaque acquisition qui s’y rattache.
CREATE TABLE IF NOT EXISTS staging.nas_passage_observations (
    pipeline_execution_id text NOT NULL,
    vineyard_key text NOT NULL,
    -- On identifie la parcelle du passage ; le nom du passage seul ne suffirait pas à former sa clé.
    parcel_name text NOT NULL CHECK (btrim(parcel_name) <> ''),
    -- On garde le passage avec sa parcelle, pour distinguer deux noms identiques utilisés dans des
    -- parcelles différentes.
    passage_name text NOT NULL CHECK (btrim(passage_name) <> ''),
    -- On conserve le constat de présence du fichier de stocks, sans en déduire sa qualité ni une
    -- livraison.
    stocks_json_exists boolean NOT NULL,
    -- On compte les entrées de statut non sain relevées dans les stocks, pas le nombre d’acquisitions.
    non_healthy_status_count integer NOT NULL CHECK (non_healthy_status_count >= 0),
    vitiparcel_created boolean NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    -- On distingue le même nom de passage dans deux parcelles ou deux bilans différents.
    PRIMARY KEY (pipeline_execution_id, vineyard_key, parcel_name, passage_name),
    FOREIGN KEY (pipeline_execution_id, vineyard_key)
        REFERENCES core.nas_observation_runs(pipeline_execution_id, vineyard_key)
);
COMMENT ON TABLE staging.nas_passage_observations IS
    'Passages distincts observes ; ne pas sommer les memes stocks repetes dans les associations.';

-- On décrit les liens acquisition–parcelle–passage observés. Plusieurs liens peuvent appartenir à une
-- même acquisition.
CREATE TABLE IF NOT EXISTS staging.nas_association_observations (
    pipeline_execution_id text NOT NULL,
    vineyard_key text NOT NULL,
    acquisition_id_normalise text NOT NULL,
    parcel_name text NOT NULL,
    passage_name text NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    -- La clé identifie un lien complet ; ni l’acquisition seule ni le passage seul ne suffisent à
    -- distinguer les associations.
    PRIMARY KEY (pipeline_execution_id, vineyard_key, acquisition_id_normalise, parcel_name, passage_name),
    FOREIGN KEY (pipeline_execution_id, vineyard_key, acquisition_id_normalise)
        REFERENCES staging.nas_acquisition_observations(pipeline_execution_id, vineyard_key, acquisition_id_normalise),
    FOREIGN KEY (pipeline_execution_id, vineyard_key, parcel_name, passage_name)
        REFERENCES staging.nas_passage_observations(pipeline_execution_id, vineyard_key, parcel_name, passage_name)
);
COMMENT ON TABLE staging.nas_association_observations IS
    'Liens acquisition-parcelle-passage : une relation n est ni une nouvelle acquisition ni un nouveau passage.';
CREATE INDEX IF NOT EXISTS nas_association_observations_passage_idx
    ON staging.nas_association_observations (pipeline_execution_id, vineyard_key, parcel_name, passage_name);

-- On conserve la conclusion du rapprochement pour chaque acquisition, y compris celles sans
-- observation NAS rattachée.
CREATE TABLE IF NOT EXISTS staging.reconciliation_acquisition_rows (
    pipeline_execution_id text NOT NULL,
    vineyard_key text NOT NULL,
    reconciliation_run_id text NOT NULL,
    nas_pipeline_execution_id text NOT NULL,
    acquisition_id_normalise text NOT NULL CHECK (btrim(acquisition_id_normalise) <> ''),
    -- NULL autorise une acquisition du suivi sans observation NAS rattachée. Si une observation est
    -- liée, son identifiant doit correspondre à celui du résultat.
    observed_acquisition_id text,
    passage_outputs_verifiable boolean,
    vitiparcel_created boolean,
    -- On marque les acquisitions à examiner selon les règles ; ce drapeau n’est ni une anomalie
    -- certaine ni une autorisation de retraitement.
    acquisition_review_candidate boolean NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id, acquisition_id_normalise),
    -- On interdit de rattacher le résultat d’une acquisition à l’observation d’une autre acquisition.
    CHECK (observed_acquisition_id IS NULL OR observed_acquisition_id = acquisition_id_normalise),
    FOREIGN KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id, nas_pipeline_execution_id)
        REFERENCES core.reconciliation_runs(pipeline_execution_id, vineyard_key, reconciliation_run_id, nas_pipeline_execution_id),
    -- Le lien vers une observation est contrôlé lorsqu’il est renseigné ; son absence reste possible
    -- pour une acquisition connue seulement du suivi Excel.
    FOREIGN KEY (nas_pipeline_execution_id, vineyard_key, observed_acquisition_id)
        REFERENCES staging.nas_acquisition_observations(pipeline_execution_id, vineyard_key, acquisition_id_normalise)
);
COMMENT ON TABLE staging.reconciliation_acquisition_rows IS
    'Resultats historiques par acquisition ; candidat a verifier ne signifie pas anomalie certaine ou retraitement autorise.';

-- On garde le bilan de chaque passage identifié. Le critère technique reste distinct d’une commande,
-- d’une validation qualité ou d’une livraison.
CREATE TABLE IF NOT EXISTS staging.reconciliation_passage_rows (
    pipeline_execution_id text NOT NULL,
    vineyard_key text NOT NULL,
    reconciliation_run_id text NOT NULL,
    nas_pipeline_execution_id text NOT NULL,
    parcel_name text NOT NULL,
    passage_name text NOT NULL,
    -- On précise si le critère du passage peut être évalué avant de lire sa valeur positive ou
    -- négative.
    vitiparcel_ready_verifiable boolean NOT NULL,
    -- Ce champ conserve son nom historique, mais ne représente qu’un critère technique. La commande et
    -- la livraison ne sont pas établies ici.
    vitiparcel_ready_for_delivery boolean NOT NULL,
    -- On garde la demande de revue du passage, distincte de celle des acquisitions qui lui sont
    -- associées.
    passage_review_candidate boolean NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id, parcel_name, passage_name),
    FOREIGN KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id, nas_pipeline_execution_id)
        REFERENCES core.reconciliation_runs(pipeline_execution_id, vineyard_key, reconciliation_run_id, nas_pipeline_execution_id),
    FOREIGN KEY (nas_pipeline_execution_id, vineyard_key, parcel_name, passage_name)
        REFERENCES staging.nas_passage_observations(pipeline_execution_id, vineyard_key, parcel_name, passage_name)
);
COMMENT ON TABLE staging.reconciliation_passage_rows IS
    'Bilan par passage distinct ; critere technique positif distinct de la livraison et de la qualite.';

-- On rattache chaque lien enrichi aux résultats acquisition et passage du même bilan, ainsi qu’à
-- l’association NAS d’origine.
CREATE TABLE IF NOT EXISTS staging.reconciliation_association_rows (
    pipeline_execution_id text NOT NULL,
    vineyard_key text NOT NULL,
    reconciliation_run_id text NOT NULL,
    nas_pipeline_execution_id text NOT NULL,
    acquisition_id_normalise text NOT NULL,
    parcel_name text NOT NULL,
    passage_name text NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id, acquisition_id_normalise, parcel_name, passage_name),
    FOREIGN KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id, nas_pipeline_execution_id)
        REFERENCES core.reconciliation_runs(pipeline_execution_id, vineyard_key, reconciliation_run_id, nas_pipeline_execution_id),
    -- On rattache ce lien aux résultats du même bilan ; cela évite d’assembler une acquisition et un
    -- passage issus de calculs différents.
    FOREIGN KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id, acquisition_id_normalise)
        REFERENCES staging.reconciliation_acquisition_rows(pipeline_execution_id, vineyard_key, reconciliation_run_id, acquisition_id_normalise),
    FOREIGN KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id, parcel_name, passage_name)
        REFERENCES staging.reconciliation_passage_rows(pipeline_execution_id, vineyard_key, reconciliation_run_id, parcel_name, passage_name),
    FOREIGN KEY (nas_pipeline_execution_id, vineyard_key, acquisition_id_normalise, parcel_name, passage_name)
        REFERENCES staging.nas_association_observations(pipeline_execution_id, vineyard_key, acquisition_id_normalise, parcel_name, passage_name)
);
COMMENT ON TABLE staging.reconciliation_association_rows IS
    'Relations enrichies, rattachees aux observations et aux conclusions du meme rapprochement.';
CREATE INDEX IF NOT EXISTS reconciliation_association_rows_passage_idx
    ON staging.reconciliation_association_rows (pipeline_execution_id, vineyard_key, reconciliation_run_id, parcel_name, passage_name);

-- On choisit un bilan actif par domaine, sans supprimer les bilans antérieurs. Deux domaines peuvent
-- avoir été contrôlés à des instants différents.
CREATE TABLE IF NOT EXISTS core.current_vineyard_reconciliations (
    vineyard_key text PRIMARY KEY REFERENCES core.vineyards(vineyard_key),
    pipeline_execution_id text NOT NULL,
    reconciliation_run_id text NOT NULL,
    -- On date le changement du lien courant. Cette activation peut être postérieure au calcul du
    -- bilan.
    activated_in_database_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pipeline_execution_id, vineyard_key, reconciliation_run_id)
        REFERENCES core.reconciliation_runs(pipeline_execution_id, vineyard_key, reconciliation_run_id)
);
COMMENT ON TABLE core.current_vineyard_reconciliations IS
    'Bilan courant valide par vignoble ; conserve les references propres au bilan sans melanger les versions.';


-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
