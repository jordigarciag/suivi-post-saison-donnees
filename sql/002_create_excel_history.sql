-- Historiser les suivis Excel sans écraser les versions précédentes.
-- On distingue une exécution d’ingestion, une version de classeur par domaine et une publication qui
-- les regroupe.
-- Le résultat courant sera un lien vers une publication conservée : comme un marque-page, il change la
-- page consultée sans supprimer les anciennes.


-- On regroupe les créations et les droits dans une même transaction.
BEGIN;

-- On enregistre les domaines une seule fois. Cette table donne leur identité, pas le détail de leurs
-- acquisitions.
CREATE TABLE IF NOT EXISTS core.vineyards (
    -- La clé technique relie les lignes d’un même domaine entre les différentes tables.
    vineyard_key text PRIMARY KEY CHECK (btrim(vineyard_key) <> ''),
    -- On garde le nom de présentation du domaine à côté de sa clé de jointure.
    vineyard_name text NOT NULL CHECK (btrim(vineyard_name) <> ''),
    -- Ce nom de rangement respecte la forme v_ suivie de dix caractères hexadécimaux ; son unicité
    -- évite une collision dans ce référentiel.
    storage_key text NOT NULL UNIQUE CHECK (storage_key ~ '^v_[0-9a-f]{10}$'),
    -- On date l’enregistrement du domaine en base, pas le début de son activité métier.
    registered_in_database_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE core.vineyards IS
    'Referentiel des vignobles ; ne contient pas leurs acquisitions.';

-- On garde la trace de chaque ingestion Excel, y compris un contrôle qui ne produit aucune nouvelle
-- version.
CREATE TABLE IF NOT EXISTS core.excel_ingestion_runs (
    -- Cet identifiant désigne une ingestion Excel, même lorsque les sources se révèlent inchangées.
    execution_id text PRIMARY KEY CHECK (btrim(execution_id) <> ''),
    -- On garde le début déclaré de l’exécution pour le comparer ensuite à sa fin.
    started_at timestamptz NOT NULL,
    -- Une fin non renseignée reste NULL ; on ne lui invente pas la date du chargement SQL.
    finished_at timestamptz,
    -- On conserve l’état déclaré par le producteur. La contrainte impose ici un texte non vide, pas
    -- une liste fermée de statuts.
    status text NOT NULL CHECK (btrim(status) <> ''),
    -- Ce drapeau distingue une initialisation du suivi d’une exécution ultérieure.
    initialization boolean NOT NULL,
    -- On garde les éléments d’identité du traitement dans un objet JSON pour retrouver son contexte.
    identity jsonb NOT NULL CHECK (jsonb_typeof(identity) = 'object'),
    -- Le manifeste décrit le lot ; son chemin permet de retrouver le fichier contrôlé par le chargeur.
    manifest_path text NOT NULL CHECK (btrim(manifest_path) <> ''),
    -- Cette empreinte identifie les octets du manifeste. La contrainte vérifie sa forme, pas sa
    -- correspondance avec le fichier : celle-ci relève du chargeur.
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    -- On conserve aussi le contenu du manifeste pour comprendre ce qui a été annoncé lors du
    -- chargement.
    manifest_payload jsonb NOT NULL CHECK (jsonb_typeof(manifest_payload) = 'object'),
    -- Cette date vient de PostgreSQL au chargement ; elle ne remplace pas les dates d’ingestion, de
    -- contrôle ou de calcul fournies par le pipeline.
    loaded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Une fin peut rester inconnue ; lorsqu’elle est fournie, elle ne doit pas précéder le début
    -- déclaré.
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);
COMMENT ON TABLE core.excel_ingestion_runs IS
    'Journal des executions Excel, y compris les verifications sans changement.';

-- On décrit une version de classeur pour un domaine : source, empreintes, dates et volumes. Une
-- nouvelle version ajoute une ligne au lieu de remplacer la précédente.
CREATE TABLE IF NOT EXISTS core.excel_versions (
    vineyard_key text NOT NULL REFERENCES core.vineyards(vineyard_key),
    -- On identifie la version retenue pour ce domaine ; deux domaines peuvent utiliser des
    -- identifiants qu’il faut lire avec leur clé de domaine.
    version_id text NOT NULL CHECK (btrim(version_id) <> ''),
    -- On date la normalisation de cette version Excel, pas la dernière vérification métier de chacune
    -- de ses cellules.
    ingested_at timestamptz NOT NULL,
    -- On garde le nom de la source Excel pour retrouver le classeur à l’origine de cette version.
    source_filename text NOT NULL CHECK (btrim(source_filename) <> ''),
    -- L’empreinte du classeur sert à distinguer les versions de contenu, même si le nom du fichier est
    -- identique.
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    -- On conserve la date de modification connue du fichier source. Ce n’est pas une certification de
    -- mise à jour des déclarations Excel.
    source_modified_at timestamptz,
    -- Ce chemin permet de retrouver la copie archivée du classeur lorsqu’elle est renseignée.
    archive_path text,
    identity jsonb NOT NULL CHECK (jsonb_typeof(identity) = 'object'),
    -- Le manifeste propre à cette version décrit ses sorties, séparément du manifeste de la
    -- publication globale.
    version_manifest_path text NOT NULL CHECK (btrim(version_manifest_path) <> ''),
    -- On garde l’empreinte du manifeste de version pour vérifier qu’il n’a pas été remplacé.
    version_manifest_sha256 text NOT NULL CHECK (version_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    -- Ce chemin désigne les lignes normalisées de la version, pas le classeur source.
    normalized_path text NOT NULL CHECK (btrim(normalized_path) <> ''),
    -- On garde l’empreinte du tableau normalisé utilisé pour constituer le lot.
    normalized_sha256 text NOT NULL CHECK (normalized_sha256 ~ '^[0-9a-f]{64}$'),
    -- Ce volume compte des lignes normalisées ; plusieurs lignes peuvent désigner une seule
    -- acquisition.
    normalized_rows integer NOT NULL CHECK (normalized_rows >= 0),
    -- On garde séparément le nombre d’acquisitions distinctes, pour ne pas le confondre avec le nombre
    -- de lignes.
    logical_acquisitions integer NOT NULL CHECK (logical_acquisitions >= 0),
    -- Les lignes rejetées restent comptées et traçables au lieu de disparaître du bilan d’ingestion.
    rejected_rows integer NOT NULL CHECK (rejected_rows >= 0),
    -- Le détail des métadonnées complète les champs structurés et permet de retrouver les informations
    -- du producteur.
    metadata_payload jsonb NOT NULL CHECK (jsonb_typeof(metadata_payload) = 'object'),
    loaded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- L’unicité porte sur cette combinaison : elle permet de conserver plusieurs versions ou
    -- exécutions sans écraser les précédentes.
    PRIMARY KEY (vineyard_key, version_id),
    -- Le nombre d’acquisitions distinctes ne peut pas dépasser le nombre de lignes qui les
    -- représentent.
    CHECK (logical_acquisitions <= normalized_rows)
);
COMMENT ON TABLE core.excel_versions IS
    'Versions Excel par vignoble, avec source, contexte de traitement et empreintes.';
CREATE INDEX IF NOT EXISTS excel_versions_vineyard_date_idx
    ON core.excel_versions (vineyard_key, ingested_at DESC);

-- On garde le résultat de chaque domaine dans chaque ingestion : modifié, inchangé ou en échec. Une
-- seule exécution peut donc avoir plusieurs résultats.
CREATE TABLE IF NOT EXISTS core.excel_ingestion_run_vineyards (
    execution_id text NOT NULL REFERENCES core.excel_ingestion_runs(execution_id),
    vineyard_key text NOT NULL REFERENCES core.vineyards(vineyard_key),
    -- On conserve la date du contrôle déclaré. Elle ne date pas individuellement la lecture ou la
    -- création de chaque fichier NAS.
    checked_at timestamptz NOT NULL,
    status text NOT NULL CHECK (btrim(status) <> ''),
    version_id text,
    -- Le résultat détaillé du domaine garde les informations qui ne sont pas reprises dans les
    -- colonnes principales.
    result_payload jsonb NOT NULL CHECK (jsonb_typeof(result_payload) = 'object'),
    PRIMARY KEY (execution_id, vineyard_key),
    FOREIGN KEY (vineyard_key, version_id)
        REFERENCES core.excel_versions(vineyard_key, version_id)
);
COMMENT ON TABLE core.excel_ingestion_run_vineyards IS
    'Resultat de chaque vignoble selectionne : nouvelle version, inchange ou echec.';

-- On décrit un lot Excel regroupé et publié, qui rassemble les versions retenues pour les domaines
-- concernés.
CREATE TABLE IF NOT EXISTS core.excel_publications (
    -- Cet identifiant désigne le lot publié qui rassemble les versions Excel retenues.
    publication_id text PRIMARY KEY CHECK (btrim(publication_id) <> ''),
    -- On relie la publication à l’ingestion qui l’a produite ; ce n’est pas l’identifiant de version
    -- d’un seul classeur.
    ingestion_execution_id text NOT NULL REFERENCES core.excel_ingestion_runs(execution_id),
    -- Cette date décrit la publication du lot, indépendamment de son arrivée ultérieure en base.
    published_at timestamptz NOT NULL,
    -- On garde le chemin du tableau regroupant les suivis Excel de cette publication.
    reference_path text NOT NULL CHECK (btrim(reference_path) <> ''),
    -- L’empreinte du tableau regroupé permet de vérifier qu’on utilise les mêmes données pendant les
    -- étapes du parcours.
    reference_sha256 text NOT NULL CHECK (reference_sha256 ~ '^[0-9a-f]{64}$'),
    -- On enregistre le volume annoncé du tableau regroupé afin de le comparer aux lignes effectivement
    -- chargées.
    reference_rows integer NOT NULL CHECK (reference_rows >= 0),
    manifest_path text NOT NULL CHECK (btrim(manifest_path) <> ''),
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    manifest_payload jsonb NOT NULL CHECK (jsonb_typeof(manifest_payload) = 'object'),
    loaded_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE core.excel_publications IS
    'Historique des references globales Excel effectivement chargees en base.';
CREATE INDEX IF NOT EXISTS excel_publications_date_idx
    ON core.excel_publications (published_at DESC, publication_id);

-- On mémorise la composition exacte d’une publication : une version par domaine. Sans ce lien, on ne
-- saurait pas quels classeurs ont produit un ancien lot.
CREATE TABLE IF NOT EXISTS core.excel_publication_versions (
    publication_id text NOT NULL REFERENCES core.excel_publications(publication_id),
    vineyard_key text NOT NULL,
    version_id text NOT NULL,
    PRIMARY KEY (publication_id, vineyard_key),
    UNIQUE (publication_id, vineyard_key, version_id),
    FOREIGN KEY (vineyard_key, version_id)
        REFERENCES core.excel_versions(vineyard_key, version_id)
);
COMMENT ON TABLE core.excel_publication_versions IS
    'Composition historique : quelle version de chaque vignoble pour chaque publication.';
CREATE INDEX IF NOT EXISTS excel_publication_versions_version_idx
    ON core.excel_publication_versions (vineyard_key, version_id);

-- On conserve les lignes normalisées et rejetées d’une version. Leur rang permet de distinguer deux
-- lignes même si elles parlent de la même acquisition.
CREATE TABLE IF NOT EXISTS staging.excel_version_rows (
    vineyard_key text NOT NULL,
    version_id text NOT NULL,
    -- On distingue une ligne normalisée d’une ligne rejetée : les deux sont conservées mais n’ont pas
    -- le même usage.
    row_kind text NOT NULL CHECK (row_kind IN ('normalized', 'rejected')),
    -- Le rang distingue les lignes au sein du lot ; ce n’est pas un nouvel identifiant d’acquisition.
    row_ordinal integer NOT NULL CHECK (row_ordinal > 0),
    -- On conserve le détail original dans un objet JSON ; les vues en extraient ensuite les champs
    -- utiles sans réécrire ce contenu.
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    -- Le rang est unique au sein d’une version et d’un type de ligne ; normalisé et rejeté restent
    -- deux ensembles distincts.
    PRIMARY KEY (vineyard_key, version_id, row_kind, row_ordinal),
    FOREIGN KEY (vineyard_key, version_id)
        REFERENCES core.excel_versions(vineyard_key, version_id)
);
COMMENT ON TABLE staging.excel_version_rows IS
    'Lignes normalisees ou rejetees d une version ; une ligne n est pas necessairement une acquisition.';

-- On garde les lignes du tableau Excel regroupé telles qu’elles ont été publiées, avec leur
-- rattachement au domaine et à sa version.
CREATE TABLE IF NOT EXISTS staging.excel_publication_rows (
    publication_id text NOT NULL,
    row_ordinal integer NOT NULL CHECK (row_ordinal > 0),
    vineyard_key text NOT NULL,
    version_id text NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (publication_id, row_ordinal),
    -- La ligne doit appartenir à une version réellement membre de cette publication, pas seulement à
    -- une version existante du domaine.
    FOREIGN KEY (publication_id, vineyard_key, version_id)
        REFERENCES core.excel_publication_versions(publication_id, vineyard_key, version_id)
);
COMMENT ON TABLE staging.excel_publication_rows IS
    'Copie historique du contenu de reference.csv, sans recalcul des anciennes classifications.';
CREATE INDEX IF NOT EXISTS excel_publication_rows_vineyard_idx
    ON staging.excel_publication_rows (publication_id, vineyard_key);

-- On garde un seul marque-page vers la publication Excel courante. Les données des publications
-- précédentes restent dans leurs tables historiques.
CREATE TABLE IF NOT EXISTS core.excel_current_publication (
    -- La clé booléenne et CHECK(singleton) n’autorisent que la ligne true : on peut donc avoir au plus
    -- une publication courante, pas obligatoirement une.
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    publication_id text NOT NULL REFERENCES core.excel_publications(publication_id),
    -- On date le changement du lien courant. Cette activation peut être postérieure au calcul du
    -- bilan.
    activated_in_database_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE core.excel_current_publication IS
    'Pointeur unique vers la publication Excel courante validee en base.';


-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
