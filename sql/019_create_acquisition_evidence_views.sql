-- Rendre les constats enregistrés lisibles, indicateur par indicateur.
-- On distingue les données brutes, les traitements, les correspondances et les sorties de passage.
-- Le détail produit 14 lignes d’indicateurs par acquisition : ce ne sont pas 14 acquisitions ni 14
-- livrables supplémentaires.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;
-- On évite ici le coût de compilation JIT pour ces requêtes de création ou de contrôle.
SET LOCAL jit = off;
-- On limite l’attente des verrous ; un dépassement demande un diagnostic, pas une suppression aveugle
-- des verrous.
SET LOCAL lock_timeout = '5s';

-- On extrait les indicateurs conservés dans le JSON pour les consulter comme des colonnes, sans
-- refaire les contrôles de fichiers.
CREATE OR REPLACE VIEW mart.reconciliation_acquisition_evidence_current AS
-- On matérialise cette source pour cette requête afin de réutiliser ses lignes sans réévaluer
-- plusieurs fois la même vue.
WITH acquisition_source AS MATERIALIZED (
    SELECT * FROM mart.reconciliation_acquisition_current
), history_counts AS MATERIALIZED (
    -- On compte les contrôles NAS distincts au niveau du domaine ; cela ne prouve pas que chaque
    -- acquisition figure dans chacun.
    SELECT vineyard_key, COUNT(DISTINCT nas_pipeline_execution_id) AS distinct_nas_observations
    FROM mart.reconciliation_vineyard_history GROUP BY vineyard_key
)
SELECT a.*,
       -- On lit le constat de présence du dossier Brut.
       -- ->> lit une valeur du JSON sous forme de texte ; AS donne un nom à la colonne obtenue.
       -- On retire les espaces et on ignore la casse avant de lire true ou false.
       -- Toute autre valeur reste inconnue (NULL), plutôt que d’être interprétée comme une absence.
       CASE lower(btrim(a.payload->>'found_in_raw_live')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS raw_folder_present,
       -- Ce constat demande au moins une image PNG dans l’arborescence native attendue.
       CASE lower(btrim(a.payload->>'raw_has_full_size_image')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS native_png_present,
       -- Ici, on distingue la présence de PNG sur les deux côtés LEFT et RIGHT de la présence d’un
       -- seul côté.
       CASE lower(btrim(a.payload->>'raw_has_full_size_both_sides')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS native_png_both_sides,
       -- On lit la présence du dossier Processing ; son existence seule ne démontre pas que les images
       -- ont été traitées.
       CASE lower(btrim(a.payload->>'found_in_processing_live')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS processing_folder_present,
       -- On reprend le constat d’au moins une image WEBP.
       CASE lower(btrim(a.payload->>'processing_has_webp_images')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS webp_present,
       -- On conserve séparément le constat de WEBP sur les deux côtés, plus exigeant qu’un WEBP isolé.
       CASE lower(btrim(a.payload->>'processing_has_webp_both_sides')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS webp_both_sides,
       -- On expose la présence de l’acquisition dans les correspondances de parcelles.
       CASE lower(btrim(a.payload->>'found_in_parcel_mapping')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS parcel_mapping_present,
       -- On expose sa présence dans les correspondances de passages.
       CASE lower(btrim(a.payload->>'found_in_passage_mapping')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS passage_mapping_present,
       -- On garde le résultat du contrôle de cohérence des correspondances lorsqu’il a été évalué.
       CASE lower(btrim(a.payload->>'parcel_mapping_consistent')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS mapping_consistent,
       -- On reprend le constat des dossiers de passage identifiés, à lire avec la vérifiabilité des
       -- rattachements.
       CASE lower(btrim(a.payload->>'passage_created')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS passage_folder_present,
       -- On lit la présence des GeoJSON attendus, sans conclure à leur qualité ou à une livraison.
       CASE lower(btrim(a.payload->>'vitimap_created')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS vitimap_present,
       -- On convertit le constat enregistré de présence des stocks ; ce n’est pas une nouvelle lecture
       -- du JSON sur le NAS.
       CASE lower(btrim(a.payload->>'stocks_json_exists')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS stocks_present,
       -- On expose la détection d’au moins un statut non sain dans les stocks contrôlés.
       CASE lower(btrim(a.payload->>'has_non_healthy_status')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS non_healthy_status_present,
       -- On distingue une erreur technique enregistrée d’une conclusion négative sur un livrable.
       CASE lower(btrim(a.payload->>'has_technical_error')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS technical_error_recorded,
       -- On retrouve le niveau maximal de preuve enregistré, sans en déduire le temps passé à cette
       -- étape.
       a.payload->>'maximum_evidence_stage' AS recorded_maximum_evidence_stage,
       -- On expose l’action de traitement enregistrée ; une valeur absente reste inconnue, pas une
       -- décision automatique.
       a.payload->>'processing_next_action' AS recorded_processing_next_action,
       -- On garde l’action concernant les rattachements, distincte de celle du traitement.
       a.payload->>'relationship_next_action' AS recorded_relationship_next_action,
       -- Ce classement porte sur les rattachements acquisition–parcelle–passage, séparément du
       -- traitement des images.
       a.payload->>'relationship_business_category' AS recorded_relationship_category,
       -- Le motif d’exclusion vient du suivi Excel conservé ; la vue n’en invente pas un à partir de
       -- l’absence d’un fichier.
       a.payload->>'excel_exclusion_reason' AS recorded_excel_exclusion_reason,
       -- On expose les erreurs conservées pour pouvoir distinguer lecture impossible et preuve non
       -- retrouvée.
       a.payload->>'technical_errors' AS recorded_technical_errors,
       COALESCE(h.distinct_nas_observations,0) AS distinct_nas_observations_retained,
       CASE WHEN COALESCE(h.distinct_nas_observations,0)<2
            THEN 'Une seule observation NAS ou aucune : évolution entre contrôles non évaluable'
            ELSE 'Plusieurs observations NAS conservées : comparaison des preuves non calculée par cette vue'
       END AS evolution_comparison_explanation
FROM acquisition_source a
LEFT JOIN history_counts h ON h.vineyard_key=a.vineyard_key;
COMMENT ON VIEW mart.reconciliation_acquisition_evidence_current IS
'Detail du bilan actif avec indicateurs deja enregistres, contexte Excel et actions du rapprochement. PNG au moins un et PNG deux cotes, WEBP au moins un et WEBP deux cotes restent distincts. Aucune decision de retraitement automatique ni duree de blocage. Les actions non renseignees restent NULL. Le nombre d observations concerne le vignoble, pas une preuve que chaque acquisition a ete controlee dans chacune. Les comparaisons d evolution ne sont pas calculees.';

-- On transforme les colonnes de constats en lignes d’indicateurs. Chaque ligne garde sa valeur
-- originale, son erreur éventuelle et une interprétation prudente.
CREATE OR REPLACE VIEW mart.reconciliation_acquisition_proof_current AS
-- On prépare une seule lecture du détail des constats avant de le déplier en indicateurs.
WITH evidence_source AS MATERIALIZED (
    SELECT * FROM mart.reconciliation_acquisition_evidence_current
)
SELECT e.vineyard_key,e.vineyard_name,e.pipeline_execution_id,e.reconciliation_run_id,
       e.excel_publication_id,e.excel_version_id,e.excel_ingested_at,
       e.nas_checked_at,e.reconciled_at,e.excel_version_matches_current,
       e.acquisition_id_normalise,e.recorded_excel_perimeter,e.recorded_excel_pipeline_status,
       e.acquisition_review_candidate,e.passage_outputs_verifiable,
       p.proof_key,p.proof_label,p.source_field,p.recorded_text_value,p.recorded_boolean_value,
       p.requires_identified_passage,p.recorded_read_error,
       CASE
           -- La vérifiabilité passe en premier : une sortie non attribuable ne doit pas être lue comme
           -- absente ou positive.
           WHEN p.requires_identified_passage AND e.passage_outputs_verifiable IS FALSE
               THEN 'Non vérifiable : sorties de passage non attribuables ou non évaluables'
           -- On distingue l’impossibilité connue de vérifier d’une vérifiabilité simplement non
           -- renseignée.
           WHEN p.requires_identified_passage AND e.passage_outputs_verifiable IS NULL
               THEN 'Vérifiabilité des sorties de passage non renseignée'
           -- On expose la preuve positive enregistrée tout en conservant l’éventuelle erreur dans sa
           -- colonne dédiée ; une erreur complémentaire peut donc coexister.
           WHEN p.recorded_boolean_value IS TRUE
               THEN 'Preuve positive enregistrée'
           -- Pour les autres cas, une erreur de lecture empêche d’interpréter un indicateur négatif
           -- comme une absence.
           WHEN p.recorded_read_error IS NOT NULL
               THEN 'Erreur de lecture enregistrée : ne pas conclure à une absence'
           -- Un champ vide ou composé d’espaces reste non renseigné ; on ne le transforme pas en
           -- false.
           WHEN NULLIF(btrim(p.recorded_text_value),'') IS NULL
               THEN 'Indicateur non renseigné'
           -- Si le texte existe mais n’est pas un booléen reconnu, on le signale plutôt que choisir
           -- une valeur par défaut.
           WHEN p.recorded_boolean_value IS NULL
               THEN 'Valeur booléenne non reconnue : à examiner'
           ELSE 'Preuve non démontrée selon l indicateur enregistré'
       END AS proof_interpretation
FROM evidence_source e
-- On déplie chaque acquisition en 14 indicateurs. Le booléen requires_identified_passage précise
-- lesquels exigent un rattachement de passage vérifiable.
CROSS JOIN LATERAL (VALUES
    ('raw_folder', 'Dossier Brut', 'found_in_raw_live', e.payload->>'found_in_raw_live', e.raw_folder_present, false, NULLIF(btrim(e.payload->>'raw_error'),'')),
    ('native_png', 'Au moins un PNG natif', 'raw_has_full_size_image', e.payload->>'raw_has_full_size_image', e.native_png_present, false, NULLIF(btrim(e.payload->>'raw_error'),'')),
    ('native_png_both', 'PNG natifs LEFT et RIGHT', 'raw_has_full_size_both_sides', e.payload->>'raw_has_full_size_both_sides', e.native_png_both_sides, false, NULLIF(btrim(e.payload->>'raw_error'),'')),
    ('processing_folder', 'Dossier Processing', 'found_in_processing_live', e.payload->>'found_in_processing_live', e.processing_folder_present, false, NULLIF(btrim(e.payload->>'processing_error'),'')),
    ('webp', 'Au moins un WEBP', 'processing_has_webp_images', e.payload->>'processing_has_webp_images', e.webp_present, false, NULLIF(btrim(e.payload->>'processing_error'),'')),
    ('webp_both', 'WEBP LEFT et RIGHT', 'processing_has_webp_both_sides', e.payload->>'processing_has_webp_both_sides', e.webp_both_sides, false, NULLIF(btrim(e.payload->>'processing_error'),'')),
    ('parcel_mapping', 'Rattachement lu dans le mapping parcelles', 'found_in_parcel_mapping', e.payload->>'found_in_parcel_mapping', e.parcel_mapping_present, false, NULL::text),
    ('passage_mapping', 'Rattachement lu dans le mapping passages', 'found_in_passage_mapping', e.payload->>'found_in_passage_mapping', e.passage_mapping_present, false, NULL::text),
    ('mapping_consistency', 'Cohérence des mappings lorsqu évaluée', 'parcel_mapping_consistent', e.payload->>'parcel_mapping_consistent', e.mapping_consistent, false, NULL::text),
    ('passage_folder', 'Dossier de passage identifié', 'passage_created', e.payload->>'passage_created', e.passage_folder_present, true, NULLIF(btrim(e.payload->>'passage_error'),'')),
    ('vitimap', 'GeoJSON Vitimap', 'vitimap_created', e.payload->>'vitimap_created', e.vitimap_present, true, NULLIF(btrim(e.payload->>'vitimap_error'),'')),
    ('stocks', 'Fichier de stocks', 'stocks_json_exists', e.payload->>'stocks_json_exists', e.stocks_present, true, NULLIF(btrim(e.payload->>'vitiparcel_error'),'')),
    ('non_healthy_status', 'Au moins un statut non sain dans les stocks', 'has_non_healthy_status', e.payload->>'has_non_healthy_status', e.non_healthy_status_present, true, NULLIF(btrim(e.payload->>'vitiparcel_error'),'')),
    ('vitiparcel_criterion', 'Critère technique VitiParcel selon l extracteur', 'vitiparcel_created', e.vitiparcel_created::text, e.vitiparcel_created, true, NULLIF(btrim(e.payload->>'vitiparcel_error'),''))
) p(proof_key,proof_label,source_field,recorded_text_value,recorded_boolean_value,requires_identified_passage,recorded_read_error);
COMMENT ON VIEW mart.reconciliation_acquisition_proof_current IS
'14 indicateurs par acquisition : valeurs originales et lecture prudente. Ce sont des lignes de preuves, pas des acquisitions supplementaires. FALSE sans verification possible de passage ne prouve pas une absence. Une preuve negative ou une erreur ne donne aucune autorisation de retraitement. Une valeur TRUE peut coexister avec une erreur supplementaire conservee dans recorded_read_error. Le critere VitiParcel ne certifie pas la qualite ou la livraison.';

-- On compte les interprétations pour chaque indicateur séparément. Additionner plusieurs indicateurs
-- ne donnerait pas un nombre d’acquisitions distinctes.
CREATE OR REPLACE VIEW mart.reconciliation_proof_summary_current AS
-- On réutilise le même détail d’indicateurs pour calculer leur répartition.
WITH proof_source AS MATERIALIZED (
    SELECT * FROM mart.reconciliation_acquisition_proof_current
)
SELECT vineyard_key,vineyard_name,pipeline_execution_id,reconciliation_run_id,
       excel_publication_id,excel_version_id,nas_checked_at,
       recorded_excel_perimeter,recorded_excel_pipeline_status,
       -- On compte les acquisitions de ce groupe, pas les lignes de preuve détaillées.
       proof_key,proof_label,COUNT(*) AS acquisition_count,
       -- On compte les lignes interprétées comme preuve positive pour cet indicateur précis.
       COUNT(*) FILTER (WHERE proof_interpretation='Preuve positive enregistrée') AS positive_proof_count,
       -- On compte les preuves non démontrées, sans transformer ce constat en obligation de produire
       -- le livrable.
       COUNT(*) FILTER (WHERE proof_interpretation='Preuve non démontrée selon l indicateur enregistré') AS not_demonstrated_count,
       -- On isole les sorties qui ne peuvent pas être attribuées ou évaluées pour le passage.
       COUNT(*) FILTER (WHERE proof_interpretation='Non vérifiable : sorties de passage non attribuables ou non évaluables') AS not_verifiable_count,
       -- Ce compteur garde les cas où la possibilité de vérifier les sorties n’est pas renseignée.
       COUNT(*) FILTER (WHERE proof_interpretation='Vérifiabilité des sorties de passage non renseignée') AS verifiability_unknown_count,
       -- On distingue l’indicateur lui-même non renseigné d’un indicateur évalué à false.
       COUNT(*) FILTER (WHERE proof_interpretation='Indicateur non renseigné') AS indicator_unknown_count,
       -- Les erreurs de lecture restent visibles dans leur propre catégorie, au lieu de gonfler les
       -- absences supposées.
       COUNT(*) FILTER (WHERE proof_interpretation='Erreur de lecture enregistrée : ne pas conclure à une absence') AS read_error_count,
       -- On signale les textes qui ne sont ni un booléen reconnu ni une valeur vide : ils demandent un
       -- examen.
       COUNT(*) FILTER (WHERE proof_interpretation='Valeur booléenne non reconnue : à examiner') AS invalid_boolean_count
FROM proof_source
-- On garde le bilan et son contexte Excel dans la clé du groupe ; des résultats de versions
-- différentes ne doivent pas être additionnés comme un même état.
GROUP BY vineyard_key,vineyard_name,pipeline_execution_id,reconciliation_run_id,
         excel_publication_id,excel_version_id,nas_checked_at,
         recorded_excel_perimeter,recorded_excel_pipeline_status,proof_key,proof_label;
COMMENT ON VIEW mart.reconciliation_proof_summary_current IS
'Repartition exclusive des interpretations pour chaque indicateur, vignoble et contexte Excel. Ne pas sommer les lignes de plusieurs indicateurs pour obtenir un nombre d acquisitions. Conserver tests et cas bloques visibles ; filtrer explicitement Production pour la synthese de production. Pas de KPI automatique reste a retraiter, pas de duree de blocage.';
-- On ouvre la consultation des objets listés au groupe lecteur ; les tables internes ne sont pas
-- ajoutées implicitement à ce périmètre.
GRANT SELECT ON mart.reconciliation_acquisition_evidence_current,
                mart.reconciliation_acquisition_proof_current,
                mart.reconciliation_proof_summary_current TO projet12_mart_reader;
-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
