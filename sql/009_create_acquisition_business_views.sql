-- Présenter les acquisitions selon leur contexte Excel et leur catégorie enregistrée.
-- On conserve les classements du rapprochement ; les libellés ajoutés les expliquent sans les
-- recalculer.
-- Les compteurs de revue et de non-vérifiabilité peuvent concerner les mêmes acquisitions : on ne les
-- additionne pas pour obtenir un total distinct.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;

-- On regroupe les acquisitions par périmètre et statut Excel enregistrés. Les cas de test ou d’attente
-- restent visibles au lieu d’être reclassés en production.
CREATE OR REPLACE VIEW mart.reconciliation_perimeter_current AS
SELECT vineyard_key, vineyard_name, pipeline_execution_id, reconciliation_run_id,
       excel_publication_id, excel_version_id, excel_ingested_at,
       nas_checked_at, reconciled_at, activated_in_database_at,
       excel_version_matches_current,
       recorded_excel_perimeter, recorded_excel_pipeline_status,
       -- On compte les acquisitions de ce groupe, pas les lignes de preuve détaillées.
       COUNT(*) AS acquisition_count,
       -- On compte uniquement les drapeaux de revue à true ; cela ne transforme pas ces acquisitions
       -- en anomalies certaines.
       COUNT(*) FILTER (WHERE acquisition_review_candidate IS TRUE) AS acquisitions_to_review,
       -- On isole les acquisitions dont les sorties ont été déclarées non vérifiables.
       COUNT(*) FILTER (WHERE passage_outputs_verifiable IS FALSE) AS acquisitions_outputs_not_verifiable,
       -- On compte séparément les vérifiabilités NULL, pour ne pas les assimiler à false.
       COUNT(*) FILTER (WHERE passage_outputs_verifiable IS NULL) AS acquisitions_verifiability_unknown
FROM mart.reconciliation_acquisition_current
-- On garde le bilan et son contexte Excel dans la clé du groupe ; des résultats de versions
-- différentes ne doivent pas être additionnés comme un même état.
GROUP BY vineyard_key, vineyard_name, pipeline_execution_id, reconciliation_run_id,
         excel_publication_id, excel_version_id, excel_ingested_at,
         nas_checked_at, reconciled_at, activated_in_database_at,
         excel_version_matches_current,
         recorded_excel_perimeter, recorded_excel_pipeline_status;

COMMENT ON VIEW mart.reconciliation_perimeter_current IS
'Synthese par vignoble, perimetre et statut Excel enregistres. Aucune inference de production ou exclusion. Non verifiable ne signifie pas absent ; les compteurs de verification et de non-verifiabilite peuvent se recouvrir. Provenance du rapprochement conservee, sans reclassement selon un nouvel Excel.';

-- On affine la répartition par catégorie de traitement et de rattachement. Les explications rendent
-- les classements lisibles sans les remplacer.
CREATE OR REPLACE VIEW mart.reconciliation_processing_category_current AS
SELECT vineyard_key, vineyard_name, pipeline_execution_id, reconciliation_run_id,
       excel_publication_id, excel_version_id, excel_ingested_at,
       nas_checked_at, reconciled_at, activated_in_database_at,
       excel_version_matches_current,
       recorded_excel_perimeter, recorded_excel_pipeline_status,
       recorded_processing_category,
       COUNT(*) AS acquisition_count,
       COUNT(*) FILTER (WHERE acquisition_review_candidate IS TRUE) AS acquisitions_to_review,
       COUNT(*) FILTER (WHERE passage_outputs_verifiable IS FALSE) AS acquisitions_outputs_not_verifiable,
       COUNT(*) FILTER (WHERE passage_outputs_verifiable IS NULL) AS acquisitions_verifiability_unknown,
       -- Ce classement porte sur les rattachements acquisition–parcelle–passage, séparément du
       -- traitement des images.
       -- ->> lit une valeur du JSON sous forme de texte ; AS donne un nom à la colonne obtenue.
       a.payload->>'relationship_business_category' AS recorded_relationship_category,
       CASE recorded_processing_category
           WHEN 'Écart non expliqué — à vérifier'
               THEN 'Preuve WEBP complète non démontrée — situation non expliquée par le suivi Excel'
           WHEN 'Divergence — terminé déclaré, preuve WEBP incomplète'
               THEN 'Traitement déclaré terminé dans Excel — preuve WEBP complète non retrouvée dans le NAS contrôlé'
           WHEN 'Preuve WEBP complète'
               THEN 'Présence de WEBP LEFT et RIGHT démontrée dans le NAS contrôlé'
           WHEN 'Hors périmètre production — test déclaré'
               THEN 'Test déclaré dans Excel — hors périmètre des contrôles de production'
           WHEN 'Hors contrôles — En attente / Autre dans Excel'
               THEN 'Statut Excel En attente ou Autre — hors contrôles de nouvelles anomalies selon les règles enregistrées'
           ELSE COALESCE(recorded_processing_category, 'Catégorie de traitement non renseignée')
       END AS processing_explanation,
       CASE a.payload->>'relationship_business_category'
           WHEN 'Écart de relation à vérifier'
               THEN 'Rattachement acquisition → parcelle et/ou passage à vérifier : consulter les motifs enregistrés ; lien manquant ou incohérent possible'
           ELSE COALESCE(a.payload->>'relationship_business_category', 'Conclusion sur le rattachement non renseignée')
       END AS relationship_explanation,
       'Non vérifiable : les informations disponibles ne permettent pas de vérifier ou attribuer les sorties de passage ; cela ne prouve pas leur absence.'::text AS passage_verifiability_explanation
FROM mart.reconciliation_acquisition_current a
GROUP BY vineyard_key, vineyard_name, pipeline_execution_id, reconciliation_run_id,
         excel_publication_id, excel_version_id, excel_ingested_at,
         nas_checked_at, reconciled_at, activated_in_database_at,
         excel_version_matches_current,
         recorded_excel_perimeter, recorded_excel_pipeline_status,
         recorded_processing_category,
         a.payload->>'relationship_business_category';

COMMENT ON VIEW mart.reconciliation_processing_category_current IS
'Repartition par contexte Excel et categorie de traitement enregistree. Preuve WEBP complete ne garantit ni rattachement parcelle/passage ni livraison. Les categories hors controles ne prouvent pas une absence de WEBP. Ne pas sommer les compteurs qui se recouvrent. Les categories originales sont conservees ; les explications de presentation ne recalculent aucune classification. Le rattachement est expose separement et peut affiner les groupes.';

-- On ouvre la consultation des objets listés au groupe lecteur ; les tables internes ne sont pas
-- ajoutées implicitement à ce périmètre.
GRANT SELECT ON mart.reconciliation_perimeter_current,
                mart.reconciliation_processing_category_current
TO projet12_mart_reader;
-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
