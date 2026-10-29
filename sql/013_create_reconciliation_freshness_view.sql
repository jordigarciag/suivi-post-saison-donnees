-- Expliquer l’ancienneté et la provenance des bilans actifs.
-- On conserve côte à côte le lot Excel du bilan et le lot Excel actuellement publié, sans réécrire les
-- anciens résultats.
-- L’âge du contrôle NAS n’est ni l’âge des fichiers, ni une durée de traitement, ni un retard de
-- livraison.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;

-- On rapproche les domaines du lot Excel courant et ceux des bilans actifs pour rendre visibles les
-- écarts de couverture et de version.
CREATE OR REPLACE VIEW mart.reconciliation_freshness_current AS
SELECT COALESCE(e.vineyard_key, r.vineyard_key) AS vineyard_key,
       COALESCE(e.vineyard_name, r.vineyard_name) AS vineyard_name,
       -- On indique si le domaine figure dans le lot Excel courant, indépendamment de l’existence d’un
       -- bilan actif.
       (e.vineyard_key IS NOT NULL) AS has_current_excel_reference,
       -- On signale séparément la présence d’un bilan actif ; il peut exister même si le domaine n’est
       -- plus dans le lot Excel courant.
       (r.vineyard_key IS NOT NULL) AS has_active_reconciliation,
       -- Ces champs décrivent la situation Excel actuelle ; les champs recorded qui suivent décrivent
       -- celle du bilan conservé.
       e.publication_id AS current_excel_publication_id,
       e.excel_version_id AS current_excel_version_id,
       e.excel_ingested_at AS current_excel_ingested_at,
       r.pipeline_execution_id, r.reconciliation_run_id,
       r.excel_publication_id AS recorded_excel_publication_id,
       r.excel_version_id AS recorded_excel_version_id,
       r.excel_ingested_at AS recorded_excel_ingested_at,
       r.nas_checked_at, r.reconciled_at,
       r.activated_in_database_at,
       (e.excel_version_id = r.excel_version_id) AS excel_version_matches_current,
       -- CURRENT_TIMESTAMP correspond au début de cette transaction SQL. Ce n’est pas l’heure de
       -- création de la vue.
       CURRENT_TIMESTAMP AS freshness_evaluated_at,
       -- On mesure le temps écoulé depuis le contrôle NAS, pas le temps de blocage d’une acquisition.
       CURRENT_TIMESTAMP - r.nas_checked_at AS nas_observation_age,
       -- L’ancienneté du calcul est mesurée à part de celle de l’observation qui lui a servi de
       -- source.
       CURRENT_TIMESTAMP - r.reconciled_at AS reconciliation_age,
       -- Ce délai sépare l’observation du calcul ; il ne mesure pas la durée de traitement des images.
       r.reconciled_at - r.nas_checked_at AS observation_to_reconciliation_delay,
       -- On distingue aussi le délai entre le calcul et son activation comme bilan courant.
       r.activated_in_database_at - r.reconciled_at AS reconciliation_to_activation_delay,
       -- On vérifie l’ordre observation → calcul → activation, sans supposer que ces trois instants
       -- sont identiques.
       (r.nas_checked_at <= r.reconciled_at
        AND r.reconciled_at <= r.activated_in_database_at) AS recorded_chronology_consistent,
       -- Une observation datée après la consultation demande un examen de l’horloge ou des
       -- métadonnées.
       (r.nas_checked_at > CURRENT_TIMESTAMP) AS nas_observation_in_future,
       CASE
           WHEN r.vineyard_key IS NULL THEN 'Référence Excel présente — aucun rapprochement actif'
           WHEN e.vineyard_key IS NULL THEN 'Rapprochement actif — vignoble absent de la référence Excel courante'
           WHEN e.excel_version_id = r.excel_version_id
               THEN 'Version Excel identique à la référence courante. Faits NAS issus du contrôle direct identifié ci-dessous, pas du rapport historique de septembre. Consulter séparément les dates Excel, NAS et rapprochement.'
           ELSE 'Version Excel différente — rapprochement non recalculé sur la version courante'
       END AS provenance_explanation,
       r.nas_pipeline_execution_id AS nas_pipeline_execution_id,
       r.extraction_run_id AS nas_extraction_run_id,
       src.source_filename AS recorded_excel_source_filename,
       src.source_modified_at AS recorded_excel_source_modified_at,
       src.source_sha256 AS recorded_excel_source_sha256,
       src.version_loaded_at AS recorded_excel_version_loaded_at,
       r.reconciliation_loaded_at AS reconciliation_loaded_at,
       CASE WHEN r.vineyard_key IS NOT NULL THEN
           'Contrôle ciblé du NAS opérationnel en lecture seule ; périmètre sélectionné depuis la référence Excel du bilan'
       END AS nas_observation_origin,
       CASE WHEN r.vineyard_key IS NOT NULL THEN
           'Rapport historique de septembre : branche distincte ; aucune utilisation directe comme entrée de ce rapprochement Excel/NAS live. Une influence sur des déclarations Excel ne peut pas être attribuée cellule par cellule avec les données conservées.'
       END AS historical_scan_role,
       CASE WHEN r.vineyard_key IS NOT NULL THEN
           'Date enregistrée pour l exécution du contrôle NAS ; pas un horodatage individuel de lecture de chaque fichier, ni sa date de création ou de traitement'
       END AS nas_observation_date_meaning,
       CASE WHEN r.vineyard_key IS NOT NULL THEN
           'Date de normalisation de la version Excel utilisée ; pas la date de dernière vérification métier de chaque cellule'
       END AS excel_ingestion_date_meaning,
       'Ancienneté depuis le contrôle NAS enregistré, calculée au début de cette transaction SQL ; ni âge des fichiers ni temps de blocage ni temps de traitement'::text AS observation_age_meaning,
       'Modification du fichier Excel : métadonnée de la source archivée, si renseignée ; pas une certification de dernière vérification des déclarations'::text AS excel_source_modified_date_meaning,
       'Dates de dernière vérification de chaque déclaration Excel, de mise à jour métier des mappings, de fin de traitement et de livraison : non établies par cette vue'::text AS dates_not_established
FROM mart.excel_vineyard_current e
-- On garde l’union des deux populations : domaine Excel sans bilan et bilan actif sans domaine Excel
-- courant restent visibles.
FULL OUTER JOIN mart.reconciliation_vineyard_current r
  ON r.vineyard_key = e.vineyard_key
-- On retrouve la source Excel du bilan avec son lot et sa version, pas le fichier de la publication
-- actuelle.
LEFT JOIN mart.excel_vineyard_history src
  ON src.publication_id = r.excel_publication_id
 AND src.vineyard_key = r.vineyard_key
 AND src.excel_version_id = r.excel_version_id;

COMMENT ON VIEW mart.reconciliation_freshness_current IS
'Anciennete de l observation NAS et provenance des bilans actifs, evaluees a la date de la transaction SQL. Les versions enregistrees restent distinctes de la reference Excel courante. NULL reste inconnu ou non applicable. Aucune qualification arbitraire recent/perime. Anciennete d observation distincte de duree a une etape, date de traitement ou livraison. Les vignobles Excel sans bilan actif et les bilans hors reference restent visibles. Des observations a des heures differentes ne constituent pas un scan global simultane.';
-- On ouvre la consultation des objets listés au groupe lecteur ; les tables internes ne sont pas
-- ajoutées implicitement à ce périmètre.
GRANT SELECT ON mart.reconciliation_freshness_current TO projet12_mart_reader;

-- On associe à chaque champ son origine et la date qui a réellement du sens pour lui : ingestion
-- Excel, contrôle NAS, calcul ou consultation.
CREATE OR REPLACE VIEW mart.reconciliation_field_provenance_current AS
SELECT f.vineyard_key, f.vineyard_name,
       f.pipeline_execution_id, f.reconciliation_run_id,
       d.field_name, d.source_kind, d.field_meaning,
       -- On choisit l’explication ou l’horodatage selon l’origine du champ, au lieu d’utiliser la date
       -- du bilan pour toutes les données.
       CASE d.source_kind
           WHEN 'excel' THEN 'Version Excel normalisée utilisée par le bilan'
           WHEN 'nas' THEN 'Contrôle direct du NAS : observations et indicateurs techniques de l extracteur'
           WHEN 'reconciliation' THEN 'Calcul du rapprochement : contexte Excel + observations NAS'
           ELSE 'Présentation calculée par une vue SQL'
       END AS source_description,
       CASE d.source_kind
           -- Pour une donnée Excel, la date pertinente ici est celle de la version normalisée utilisée
           -- par le bilan.
           WHEN 'excel' THEN f.recorded_excel_ingested_at
           -- Pour un constat NAS, on reprend la date du contrôle direct conservé.
           WHEN 'nas' THEN f.nas_checked_at
           -- Pour une conclusion croisée, on date le calcul, en gardant à côté les dates de ses
           -- sources.
           WHEN 'reconciliation' THEN f.reconciled_at
           ELSE f.freshness_evaluated_at
       END AS source_event_at,
       CASE d.source_kind
           WHEN 'excel' THEN f.excel_ingestion_date_meaning
           WHEN 'nas' THEN f.nas_observation_date_meaning
           WHEN 'reconciliation' THEN 'Date du calcul utilisant les sources identifiées ; ni date de contrôle NAS ni livraison'
           ELSE 'Date de consultation SQL au début de la transaction ; pas la date de création de la définition de vue'
       END AS source_event_date_meaning,
       f.recorded_excel_publication_id, f.recorded_excel_version_id,
       f.recorded_excel_source_filename,
       f.recorded_excel_source_modified_at,
       f.recorded_excel_ingested_at,
       f.nas_pipeline_execution_id, f.nas_extraction_run_id,
       f.nas_checked_at, f.reconciled_at,
       f.reconciliation_loaded_at, f.activated_in_database_at,
       f.freshness_evaluated_at,
       f.historical_scan_role, f.dates_not_established
FROM mart.reconciliation_freshness_current f
-- On décrit 29 champs pour chaque bilan actif. Chaque ligne documente une origine et une logique, pas
-- la présence réelle d’une valeur dans chaque acquisition.
CROSS JOIN LATERAL (VALUES
    ('acquisition_id_normalise', 'excel', 'Identifiant du référentiel normalisé ; le suffixe temporel ne date pas notre contrôle'),
    ('excel_perimeter', 'excel', 'Périmètre interprété à partir de la version Excel du bilan'),
    ('excel_pipeline_status', 'excel', 'Statut de contexte issu de la version Excel du bilan'),
    ('excel_comments', 'excel', 'Commentaires déclarés dans Excel ; pas une preuve technique NAS'),
    ('excel_problems', 'excel', 'Problèmes déclarés dans Excel'),
    ('excel_resolution_statuses', 'excel', 'Résolutions déclarées dans Excel ; pas une confirmation indépendante'),
    ('excel_visual_processing', 'excel', 'Déclaration Excel de traitement des images'),
    ('excel_vitimap', 'excel', 'Déclaration Excel de l étape Vitimap'),
    ('excel_vitiparcel', 'excel', 'Déclaration Excel de l étape Vitiparcel'),
    ('found_in_raw_live', 'nas', 'Présence du dossier Brut recherchée lors du contrôle ciblé'),
    ('raw_has_full_size_both_sides', 'nas', 'Présence de PNG natifs sur les deux côtés selon les critères de l extracteur'),
    ('found_in_processing_live', 'nas', 'Présence du dossier Processing ; ne prouve pas seule le traitement'),
    ('processing_has_webp_both_sides', 'nas', 'Présence de WEBP LEFT et RIGHT selon les critères de l extracteur'),
    ('found_in_parcel_mapping', 'nas', 'Rattachement lu dans le mapping de parcelles ; sa lecture ne garantit pas sa mise à jour métier'),
    ('found_in_passage_mapping', 'nas', 'Rattachement lu dans le mapping de passages'),
    ('parcel_mapping_consistent', 'nas', 'Comparaison des mappings lus ; calcul technique du contrôle'),
    ('passage_outputs_verifiable', 'nas', 'Possibilité de vérifier et attribuer les sorties selon les liens et informations disponibles'),
    ('passage_created', 'nas', 'Présence du dossier de passage identifié'),
    ('vitimap_created', 'nas', 'Présence du GeoJSON attendu ; pas une validation de qualité'),
    ('stocks_json_exists', 'nas', 'Présence du fichier de stocks dans le passage identifié'),
    ('non_healthy_status_count', 'nas', 'Comptage des entrées de statut non sain dans les stocks lus'),
    ('vitiparcel_created', 'nas', 'Critère technique calculé à partir des stocks ; lire avec la vérifiabilité, sans conclure à une livraison'),
    ('processing_business_category', 'reconciliation', 'Conclusion calculée à partir des preuves NAS et du contexte Excel'),
    ('relationship_business_category', 'reconciliation', 'Conclusion de rattachement calculée ; peut intégrer les explications Excel'),
    ('acquisition_review_candidate', 'reconciliation', 'Candidat à examiner selon les règles ; pas une anomalie certaine'),
    ('passage_review_candidate', 'reconciliation', 'Candidat passage calculé ; ne couvre que les passages identifiés'),
    ('vitiparcel_ready_for_delivery', 'reconciliation', 'Critère technique de rapprochement ; nom du champ distinct de livraison effective'),
    ('processing_explanation', 'presentation', 'Reformulation SQL ; aucun nouveau fait technique ni reclassement'),
    ('relationship_explanation', 'presentation', 'Reformulation SQL de la catégorie enregistrée')
) d(field_name, source_kind, field_meaning)
-- Le catalogue de champs ne concerne que les bilans réellement actifs ; un domaine présent seulement
-- dans Excel n’en crée pas un artificiellement.
WHERE f.has_active_reconciliation;
COMMENT ON VIEW mart.reconciliation_field_provenance_current IS
'Catalogue explicatif champ par champ du contrat Excel/NAS live actuel, pour chaque bilan actif. Les horodatages proviennent des sources conservees ; aucune date de mise a jour de cellule ou fichier NAS n est creee. Une ligne documente la logique du champ, pas sa presence ou sa valeur dans chaque acquisition. Les valeurs detaillees restent dans les vues acquisition, passage, association et leurs payloads. Pour les conclusions croisees, toutes les dates Excel et NAS sont conservees a cote de la date de calcul. Les explications de presentation sont evaluees a la consultation, sans recrire l historique.';
GRANT SELECT ON mart.reconciliation_field_provenance_current TO projet12_mart_reader;

-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
