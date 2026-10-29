-- Préparer les bilans par domaine, acquisition et passage.
-- Les compteurs partent des lignes enregistrées ; ces vues ne relisent ni les fichiers Excel ni le
-- NAS.
-- On sépare ce qui est à vérifier, ce qui n’est pas vérifiable et ce qui n’est pas renseigné. Aucun de
-- ces états ne suffit, seul, à prouver une absence de livrable.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;

-- On calcule les synthèses à partir des acquisitions, associations et passages conservés pour chaque
-- rapprochement.
CREATE OR REPLACE VIEW mart.reconciliation_vineyard_history AS
-- On agrège d’abord les acquisitions à leur propre niveau ; joindre directement tous les détails
-- multiplierait les lignes.
WITH acquisitions AS (
    SELECT pipeline_execution_id, vineyard_key, reconciliation_run_id,
        -- On compte les acquisitions de ce groupe, pas les lignes de preuve détaillées.
        COUNT(*) AS acquisition_count,
        -- On compte uniquement les drapeaux de revue à true ; cela ne transforme pas ces acquisitions
        -- en anomalies certaines.
        COUNT(*) FILTER (WHERE acquisition_review_candidate IS TRUE) AS acquisitions_to_review,
        -- On isole les acquisitions dont les sorties ont été déclarées non vérifiables.
        COUNT(*) FILTER (WHERE passage_outputs_verifiable IS FALSE) AS acquisitions_outputs_not_verifiable,
        -- On compte séparément les vérifiabilités NULL, pour ne pas les assimiler à false.
        COUNT(*) FILTER (WHERE passage_outputs_verifiable IS NULL) AS acquisitions_verifiability_unknown
    FROM staging.reconciliation_acquisition_rows
    GROUP BY pipeline_execution_id, vineyard_key, reconciliation_run_id
-- On compte les associations séparément, car plusieurs liens peuvent concerner une même acquisition.
), associations AS (
    SELECT pipeline_execution_id, vineyard_key, reconciliation_run_id,
        -- On compte les relations : une acquisition liée à deux passages peut contribuer deux fois à
        -- ce volume.
        COUNT(*) AS association_count
    FROM staging.reconciliation_association_rows
    GROUP BY pipeline_execution_id, vineyard_key, reconciliation_run_id
-- On agrège les passages distincts sans les multiplier par leurs associations aux acquisitions.
), passages AS (
    SELECT pipeline_execution_id, vineyard_key, reconciliation_run_id,
        -- On compte les passages distincts conservés dans cette table de résultats.
        COUNT(*) AS passage_count,
        COUNT(*) FILTER (WHERE vitiparcel_ready_verifiable IS TRUE
                         AND vitiparcel_ready_for_delivery IS TRUE) AS passages_criterion_satisfied,
        COUNT(*) FILTER (WHERE vitiparcel_ready_verifiable IS TRUE
                         AND vitiparcel_ready_for_delivery IS FALSE) AS passages_criterion_not_demonstrated,
        -- On garde à part les passages dont le critère technique n’a pas pu être vérifié.
        COUNT(*) FILTER (WHERE vitiparcel_ready_verifiable IS FALSE) AS passages_criterion_not_verifiable,
        -- On compte les passages signalés pour revue, sans les confondre avec les acquisitions à
        -- examiner.
        COUNT(*) FILTER (WHERE passage_review_candidate IS TRUE) AS passages_to_review
    FROM staging.reconciliation_passage_rows
    GROUP BY pipeline_execution_id, vineyard_key, reconciliation_run_id
)
SELECT
    r.vineyard_key, v.vineyard_name,
    r.pipeline_execution_id, r.reconciliation_run_id,
    r.nas_pipeline_execution_id, n.extraction_run_id,
    -- On garde le lot et la version Excel utilisés par ce bilan, pas ceux d’une publication apparue
    -- plus tard.
    r.excel_publication_id, r.excel_version_id,
    e.ingested_at AS excel_ingested_at,
    n.checked_at AS nas_checked_at,
    r.reconciled_at, r.loaded_at AS reconciliation_loaded_at,
    COALESCE(a.acquisition_count, 0) AS acquisition_count,
    COALESCE(a.acquisitions_to_review, 0) AS acquisitions_to_review,
    COALESCE(a.acquisitions_outputs_not_verifiable, 0) AS acquisitions_outputs_not_verifiable,
    COALESCE(a.acquisitions_verifiability_unknown, 0) AS acquisitions_verifiability_unknown,
    COALESCE(links.association_count, 0) AS association_count,
    COALESCE(p.passage_count, 0) AS passage_count,
    -- Ce compteur exige un critère vérifiable et positif ; il ne mesure pas les livraisons client.
    COALESCE(p.passages_criterion_satisfied, 0) AS passages_criterion_satisfied,
    -- On ne classe ici les critères négatifs que lorsque leur vérification était possible.
    COALESCE(p.passages_criterion_not_demonstrated, 0) AS passages_criterion_not_demonstrated,
    COALESCE(p.passages_criterion_not_verifiable, 0) AS passages_criterion_not_verifiable,
    COALESCE(p.passages_to_review, 0) AS passages_to_review,
    -- On garde les trois volumes annoncés lors du chargement pour contrôler la complétude du bilan.
    r.acquisition_rows AS declared_acquisition_count,
    r.association_rows AS declared_association_count,
    r.passage_rows AS declared_passage_count,
    (COALESCE(a.acquisition_count, 0) = r.acquisition_rows
     AND COALESCE(links.association_count, 0) = r.association_rows
     -- Les trois comptages doivent correspondre : acquisitions, liens et passages. Un seul écart
     -- suffit à rendre ce contrôle faux.
     AND COALESCE(p.passage_count, 0) = r.passage_rows) AS row_counts_match_declared
FROM core.reconciliation_runs r
JOIN core.vineyards v ON v.vineyard_key = r.vineyard_key
-- On rattache le bilan à son observation NAS pour ce domaine, avec l’identifiant de source conservé
-- dans le rapprochement.
JOIN core.nas_observation_runs n
    ON n.pipeline_execution_id = r.nas_pipeline_execution_id
   AND n.vineyard_key = r.vineyard_key
-- On récupère les métadonnées de la version avec sa clé de domaine et son identifiant de version.
JOIN core.excel_versions e
    ON e.vineyard_key = r.vineyard_key AND e.version_id = r.excel_version_id
-- On conserve le bilan même si ce type de détail n’a aucune ligne. Les COALESCE ci-dessus donnent
-- alors un compteur à zéro, pas un constat d’absence de fichier.
LEFT JOIN acquisitions a
    ON a.pipeline_execution_id = r.pipeline_execution_id AND a.vineyard_key = r.vineyard_key
   AND a.reconciliation_run_id = r.reconciliation_run_id
LEFT JOIN associations links
    ON links.pipeline_execution_id = r.pipeline_execution_id AND links.vineyard_key = r.vineyard_key
   AND links.reconciliation_run_id = r.reconciliation_run_id
LEFT JOIN passages p
    ON p.pipeline_execution_id = r.pipeline_execution_id AND p.vineyard_key = r.vineyard_key
   AND p.reconciliation_run_id = r.reconciliation_run_id;

COMMENT ON VIEW mart.reconciliation_vineyard_history IS
    'Syntheses historiques par vignoble et rapprochement charge. Comptages des resultats conserves, sans reclassement ; zero signifie aucune ligne de cette categorie, pas absence certaine de livrable.';

-- On retrouve les bilans activés et on compare leur version Excel à la version courante, sans
-- recalculer leurs conclusions.
CREATE OR REPLACE VIEW mart.reconciliation_vineyard_current AS
SELECT h.*, c.activated_in_database_at,
    -- La version aujourd’hui publiée reste distincte de la version du bilan ; l’égalité sert
    -- d’avertissement de provenance, pas de recalcul.
    members.version_id AS current_excel_version_id,
    (members.version_id = h.excel_version_id) AS excel_version_matches_current
FROM mart.reconciliation_vineyard_history h
-- On ne retient que le rapprochement activé pour ce domaine, en comparant toute sa clé.
JOIN core.current_vineyard_reconciliations c
    ON c.pipeline_execution_id = h.pipeline_execution_id AND c.vineyard_key = h.vineyard_key
   AND c.reconciliation_run_id = h.reconciliation_run_id
-- On garde le bilan même si aucune publication Excel courante n’est disponible pour la comparaison.
LEFT JOIN core.excel_current_publication current_excel ON current_excel.singleton IS TRUE
-- La version courante peut manquer pour ce domaine ; on garde alors NULL au lieu d’affirmer une
-- différence de version.
LEFT JOIN core.excel_publication_versions members
    ON members.publication_id = current_excel.publication_id AND members.vineyard_key = h.vineyard_key;

COMMENT ON VIEW mart.reconciliation_vineyard_current IS
    'Bilan courant des seuls vignobles actives. La comparaison de version Excel est un avertissement de provenance, pas un recalcul : false signifie version differente, NULL reference courante indisponible. Les dates et classifications du bilan ne sont jamais remplacees par celles de la nouvelle reference.';

-- On expose le détail des acquisitions du bilan actif, avec le contexte Excel qui a réellement servi
-- au calcul.
CREATE OR REPLACE VIEW mart.reconciliation_acquisition_current AS
-- On conserve le domaine et les identifiants du bilan pour retrouver l’origine de chaque ligne de
-- détail.
SELECT h.vineyard_key, h.vineyard_name, h.pipeline_execution_id, h.reconciliation_run_id,
    h.excel_publication_id, h.excel_version_id, h.excel_ingested_at,
    -- On distingue la date du contrôle NAS, celle du croisement et celle de l’activation du bilan.
    h.nas_checked_at, h.reconciled_at, h.activated_in_database_at,
    h.excel_version_matches_current,
    -- On identifie l’acquisition et on garde ensemble la vérifiabilité des sorties et le critère
    -- technique observé.
    a.acquisition_id_normalise, a.passage_outputs_verifiable, a.vitiparcel_created,
    -- Ce drapeau demande un examen ; il ne suffit pas à affirmer qu’une anomalie existe.
    a.acquisition_review_candidate,
    -- On reprend la catégorie de traitement calculée et enregistrée lors du rapprochement.
    -- ->> lit une valeur du JSON sous forme de texte ; AS donne un nom à la colonne obtenue.
    a.payload->>'processing_business_category' AS recorded_processing_category,
    -- On retrouve le périmètre issu du suivi Excel utilisé par ce bilan.
    a.payload->>'excel_perimeter' AS recorded_excel_perimeter,
    -- On conserve le statut déclaré dans le suivi Excel, sans le remplacer par un constat NAS.
    a.payload->>'excel_pipeline_status' AS recorded_excel_pipeline_status,
    -- Le JSON complet reste disponible pour consulter les détails qui ne sont pas exposés dans des
    -- colonnes dédiées.
    a.payload
FROM mart.reconciliation_vineyard_current h
-- La jointure utilise exécution, domaine et rapprochement : elle ne doit pas ramener le détail d’un
-- autre bilan du même domaine.
JOIN staging.reconciliation_acquisition_rows a
    ON a.pipeline_execution_id = h.pipeline_execution_id AND a.vineyard_key = h.vineyard_key
   AND a.reconciliation_run_id = h.reconciliation_run_id;

COMMENT ON VIEW mart.reconciliation_acquisition_current IS
    'Acquisitions du bilan courant, avec contexte enregistre. Lire vitiparcel_created avec passage_outputs_verifiable : false non verifiable ne prouve pas une absence. NULL reste inconnu ; candidat a verifier ne signifie pas anomalie certaine.';

-- On expose les passages distincts du bilan actif. Un passage sans preuve vérifiable ne devient pas
-- pour autant un livrable manquant.
CREATE OR REPLACE VIEW mart.reconciliation_passage_current AS
SELECT h.vineyard_key, h.vineyard_name, h.pipeline_execution_id, h.reconciliation_run_id,
    h.excel_publication_id, h.excel_version_id, h.excel_ingested_at,
    h.nas_checked_at, h.reconciled_at, h.activated_in_database_at,
    h.excel_version_matches_current,
    -- La parcelle et le passage identifient la sortie ; le drapeau de vérifiabilité précise si son
    -- critère est interprétable.
    p.parcel_name, p.passage_name, p.vitiparcel_ready_verifiable,
    -- On conserve le critère technique enregistré et la demande éventuelle de revue, sans conclure à
    -- une livraison.
    p.vitiparcel_ready_for_delivery, p.passage_review_candidate,
    -- On reprend la conclusion enregistrée pour ce passage, plutôt que la recalculer à la
    -- consultation.
    p.payload->>'passage_business_category' AS recorded_passage_category,
    p.payload
FROM mart.reconciliation_vineyard_current h
JOIN staging.reconciliation_passage_rows p
    ON p.pipeline_execution_id = h.pipeline_execution_id AND p.vineyard_key = h.vineyard_key
   AND p.reconciliation_run_id = h.reconciliation_run_id;

COMMENT ON VIEW mart.reconciliation_passage_current IS
    'Une ligne par passage distinct du bilan courant. Critere technique positif distinct de livraison client ou de validation de qualite. Les acquisitions sans passage identifie ne sont pas representees par des passages fictifs.';

-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
