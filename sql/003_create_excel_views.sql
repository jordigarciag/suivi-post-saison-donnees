-- Rendre les versions Excel consultables depuis mart.
-- On rapproche les comptages des lignes réellement chargées de ceux annoncés par les manifestes.
-- La vue historique garde toutes les publications ; la vue courante ne retient que celle qui a été
-- activée.


-- On regroupe les créations et les droits dans une même transaction.
BEGIN;

-- On relit toutes les publications Excel par domaine, avec les dates et les volumes qui leur
-- appartiennent.
CREATE OR REPLACE VIEW mart.excel_vineyard_history AS
-- On compte les lignes réellement présentes pour chaque publication et domaine avant de les comparer
-- aux volumes annoncés.
WITH observed_counts AS (
    SELECT
        publication_id,
        vineyard_key,
        COUNT(*) AS row_count,
        -- ->> lit une valeur du JSON sous forme de texte ; AS donne un nom à la colonne obtenue.
        COUNT(DISTINCT (payload->>'Acquisition_ID_normalise')) AS logical_acquisition_count
    FROM staging.excel_publication_rows
    GROUP BY publication_id, vineyard_key
)
SELECT
    p.publication_id,
    p.published_at AS excel_published_at,
    p.loaded_at AS publication_loaded_at,
    p.ingestion_execution_id AS publication_execution_id,
    v.vineyard_key,
    v.vineyard_name,
    e.version_id AS excel_version_id,
    e.source_filename,
    e.source_modified_at,
    e.ingested_at AS excel_ingested_at,
    e.loaded_at AS version_loaded_at,
    counts.row_count,
    counts.logical_acquisition_count,
    -- On expose à côté les volumes du manifeste pour pouvoir comparer déclaration du producteur et
    -- lignes réellement chargées.
    e.normalized_rows AS declared_row_count,
    e.logical_acquisitions AS declared_logical_acquisition_count,
    e.rejected_rows AS declared_rejected_row_count,
    COALESCE(
        counts.row_count = e.normalized_rows
        AND counts.logical_acquisition_count = e.logical_acquisitions,
        false
    -- On vérifie à la fois les lignes et les acquisitions distinctes ; une donnée de comptage
    -- manquante ne doit pas valider la comparaison.
    ) AS row_counts_match_manifest,
    e.source_sha256,
    e.archive_path,
    e.version_manifest_path,
    e.normalized_path,
    p.reference_path AS publication_reference_path
FROM core.excel_publications p
-- On retrouve les versions membres de la publication, plutôt que prendre la dernière version connue de
-- chaque domaine.
JOIN core.excel_publication_versions members
    ON members.publication_id = p.publication_id
JOIN core.vineyards v
    ON v.vineyard_key = members.vineyard_key
-- On récupère les métadonnées de la version avec sa clé de domaine et son identifiant de version.
JOIN core.excel_versions e
    ON e.vineyard_key = members.vineyard_key
    AND e.version_id = members.version_id
-- On laisse visible une publication dont les lignes ne sont pas retrouvées ; le contrôle de volumes
-- pourra alors signaler le problème.
LEFT JOIN observed_counts counts
    ON counts.publication_id = p.publication_id
    AND counts.vineyard_key = members.vineyard_key;

COMMENT ON VIEW mart.excel_vineyard_history IS
    'Synthese par vignoble et publication Excel chargee : provenance, dates et comptages historiques, sans reclassement metier.';

-- On limite la lecture Excel au lot actuellement activé ; cette vue ne réalise pas encore le
-- croisement avec le NAS.
CREATE OR REPLACE VIEW mart.excel_vineyard_current AS
SELECT
    history.*,
    current_publication.activated_in_database_at
FROM mart.excel_vineyard_history history
-- Le lien courant sélectionne une publication de l’historique ; il ne duplique pas ses données.
JOIN core.excel_current_publication current_publication
    ON current_publication.publication_id = history.publication_id;

COMMENT ON VIEW mart.excel_vineyard_current IS
    'Synthese Excel de la publication courante ; ne constitue pas encore un bilan Excel-NAS ni un statut de livraison.';

-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
