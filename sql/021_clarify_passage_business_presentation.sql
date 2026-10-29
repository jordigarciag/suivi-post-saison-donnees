-- Clarifier ce que les constats de passage permettent réellement d’affirmer.
-- Le nom historique vitiparcel_ready_for_delivery est conservé pour compatibilité, mais il ne prouve
-- pas une livraison.
-- Un livrable peut ne pas être attendu pour ce passage. Les sources exploitées ne documentent pas les
-- commandes client : la vue ne doit pas en inventer.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;
-- On évite ici le coût de compilation JIT pour ces requêtes de création ou de contrôle.
SET LOCAL jit = off;
-- On limite l’attente des verrous ; un dépassement demande un diagnostic, pas une suppression aveugle
-- des verrous.
SET LOCAL lock_timeout = '5s';

-- On expose les passages distincts du bilan actif. Un passage sans preuve vérifiable ne devient pas
-- pour autant un livrable manquant.
CREATE OR REPLACE VIEW mart.reconciliation_passage_current AS
-- On conserve le domaine et les identifiants du bilan pour retrouver l’origine de chaque ligne de
-- détail.
SELECT h.vineyard_key, h.vineyard_name, h.pipeline_execution_id, h.reconciliation_run_id,
    -- On garde le lot et la version Excel utilisés par ce bilan, pas ceux d’une publication apparue
    -- plus tard.
    h.excel_publication_id, h.excel_version_id, h.excel_ingested_at,
    -- On distingue la date du contrôle NAS, celle du croisement et celle de l’activation du bilan.
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
    -- ->> lit une valeur du JSON sous forme de texte ; AS donne un nom à la colonne obtenue.
    p.payload->>'passage_business_category' AS recorded_passage_category,
    -- Le JSON complet reste disponible pour consulter les détails qui ne sont pas exposés dans des
    -- colonnes dédiées.
    p.payload,
    -- On convertit le constat enregistré de présence des stocks ; ce n’est pas une nouvelle lecture du
    -- JSON sur le NAS.
    -- On retire les espaces et on ignore la casse avant de lire true ou false.
    -- Toute autre valeur reste inconnue (NULL), plutôt que d’être interprétée comme une absence.
    CASE lower(btrim(p.payload->>'stocks_json_exists')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS stocks_present,
    -- On expose la détection d’au moins un statut non sain dans les stocks contrôlés.
    CASE lower(btrim(p.payload->>'has_non_healthy_status')) WHEN 'true' THEN true WHEN 'false' THEN false ELSE NULL END AS non_healthy_status_present,
    -- On montre les statuts réellement conservés dans les stocks pour contextualiser le critère
    -- technique.
    p.payload->>'stock_status_values' AS recorded_stock_status_values,
    -- L’alias reprend le critère seulement s’il est vérifiable ; sinon, NULL empêche de présenter un
    -- faux résultat négatif.
    CASE WHEN p.vitiparcel_ready_verifiable IS TRUE THEN p.vitiparcel_ready_for_delivery ELSE NULL END AS vitiparcel_technical_criterion_satisfied,
    CASE
        -- On traite d’abord les erreurs de lecture du passage ou des stocks, avant de commenter l’état
        -- technique.
        WHEN NULLIF(btrim(p.payload->>'passage_error'),'') IS NOT NULL
          OR NULLIF(btrim(p.payload->>'vitiparcel_error'),'') IS NOT NULL
            THEN 'Erreur de lecture passage ou stocks : ne pas conclure a une absence ni a un etat d annotation'
        -- Un fichier non détecté ne permet pas d’affirmer qu’il avait été commandé : on garde cette
        -- limite dans le libellé.
        WHEN lower(btrim(p.payload->>'stocks_json_exists'))='false'
            THEN 'Fichier stocks non detecte lors du controle enregistre ; attente client non documentee'
        -- IS DISTINCT FROM inclut aussi NULL : on regroupe ici les valeurs inconnues ou non reconnues,
        -- sans les appeler absentes.
        WHEN lower(btrim(p.payload->>'stocks_json_exists')) IS DISTINCT FROM 'true'
            THEN 'Presence du fichier stocks non renseignee ou valeur non reconnue'
        -- Un statut non sain est une composante technique observée, pas une validation qualité ni une
        -- preuve de livraison.
        WHEN lower(btrim(p.payload->>'has_non_healthy_status'))='true'
            THEN 'Stocks presents et statut non sain detecte : composante technique observee, sans validation qualite ni preuve de livraison'
        WHEN lower(btrim(p.payload->>'has_non_healthy_status'))='false'
          -- Des statuts uniquement sains peuvent correspondre à un support avant annotation, mais ne
          -- prouvent ni un oubli ni une obligation de produire.
          AND lower(btrim(p.payload->>'stock_status_values')) IN ('healthy','sain','healthy | sain','sain | healthy')
            THEN 'Stocks presents, statuts sains uniquement : support potentiellement pret pour annotation ; annotation non realisee possible, non prouvee ; aucune obligation deduite'
        WHEN lower(btrim(p.payload->>'has_non_healthy_status'))='false'
            THEN 'Stocks presents, aucun statut non sain detecte : verifier les valeurs conservees ; ne pas deduire une annotation oubliee'
        ELSE 'Stocks presents ; detection des statuts non sains non renseignee ou valeur non reconnue'
    END AS stocks_annotation_explanation,
    'Attente de commande non documentee dans les sources actuellement exploitees : Vitimap et/ou Vitiparcel peuvent etre demandes selon le passage ; aucune obligation de production deduite'::text AS client_expectation_explanation,
    'Passage lie a une parcelle et une temporalite ; periode metier approximative de deux semaines, pas une echeance de production ni un seuil de retard'::text AS passage_scope_explanation
FROM mart.reconciliation_vineyard_current h
-- La jointure utilise exécution, domaine et rapprochement : elle ne doit pas ramener le détail d’un
-- autre bilan du même domaine.
JOIN staging.reconciliation_passage_rows p
    ON p.pipeline_execution_id=h.pipeline_execution_id AND p.vineyard_key=h.vineyard_key
   AND p.reconciliation_run_id=h.reconciliation_run_id;
COMMENT ON VIEW mart.reconciliation_passage_current IS
'Une ligne par passage du bilan actif, rattache a une parcelle et une temporalite. Champs originaux conserves ; alias technique et explications ajoutes sans reclassement. Attente client non documentee, pas d obligation de Vitiparcel pour chaque passage ni de preuve de livraison. HEALTHY seul peut correspondre a un support avant annotation sans le prouver. Les explications documentent le contrat actuel du projet ; elles ne proviennent pas d une commande client chargee.';
COMMENT ON COLUMN mart.reconciliation_passage_current.vitiparcel_ready_for_delivery IS
'Ancien nom technique conserve pour compatibilite : ne prouve ni livraison, ni validation qualite, ni commande. Lire avec vitiparcel_ready_verifiable ; preferer l alias vitiparcel_technical_criterion_satisfied.';
COMMENT ON COLUMN mart.reconciliation_passage_current.vitiparcel_technical_criterion_satisfied IS
'Alias du critere enregistre stocks + statut non sain. NULL si non verifiable ; aucune reinterpretation de la commande ni modification du calcul conserve.';

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
    ('native_png', 'Au moins un PNG dans l arborescence native attendue', 'raw_has_full_size_image', e.payload->>'raw_has_full_size_image', e.native_png_present, false, NULLIF(btrim(e.payload->>'raw_error'),'')),
    ('native_png_both', 'PNG natifs LEFT et RIGHT', 'raw_has_full_size_both_sides', e.payload->>'raw_has_full_size_both_sides', e.native_png_both_sides, false, NULLIF(btrim(e.payload->>'raw_error'),'')),
    ('processing_folder', 'Dossier Processing', 'found_in_processing_live', e.payload->>'found_in_processing_live', e.processing_folder_present, false, NULLIF(btrim(e.payload->>'processing_error'),'')),
    ('webp', 'Au moins un WEBP', 'processing_has_webp_images', e.payload->>'processing_has_webp_images', e.webp_present, false, NULLIF(btrim(e.payload->>'processing_error'),'')),
    ('webp_both', 'WEBP LEFT et RIGHT', 'processing_has_webp_both_sides', e.payload->>'processing_has_webp_both_sides', e.webp_both_sides, false, NULLIF(btrim(e.payload->>'processing_error'),'')),
    ('parcel_mapping', 'Rattachement lu dans le mapping parcelles', 'found_in_parcel_mapping', e.payload->>'found_in_parcel_mapping', e.parcel_mapping_present, false, NULL::text),
    ('passage_mapping', 'Rattachement lu dans le mapping passages', 'found_in_passage_mapping', e.payload->>'found_in_passage_mapping', e.passage_mapping_present, false, NULL::text),
    ('mapping_consistency', 'Cohérence des mappings lorsqu évaluée', 'parcel_mapping_consistent', e.payload->>'parcel_mapping_consistent', e.mapping_consistent, false, NULL::text),
    ('passage_folder', 'Dossiers presents pour tous les passages associes', 'passage_created', e.payload->>'passage_created', e.passage_folder_present, true, NULLIF(btrim(e.payload->>'passage_error'),'')),
    ('vitimap', 'GeoJSON Vitimap presents pour tous les passages associes', 'vitimap_created', e.payload->>'vitimap_created', e.vitimap_present, true, NULLIF(btrim(e.payload->>'vitimap_error'),'')),
    ('stocks', 'Stocks presents pour tous les passages associes', 'stocks_json_exists', e.payload->>'stocks_json_exists', e.stocks_present, true, NULLIF(btrim(e.payload->>'vitiparcel_error'),'')),
    ('non_healthy_status', 'Statut non sain detecte dans chacun des passages associes', 'has_non_healthy_status', e.payload->>'has_non_healthy_status', e.non_healthy_status_present, true, NULLIF(btrim(e.payload->>'vitiparcel_error'),'')),
    ('vitiparcel_criterion', 'Critere technique Vitiparcel satisfait pour tous les passages associes', 'vitiparcel_created', e.vitiparcel_created::text, e.vitiparcel_created, true, NULLIF(btrim(e.payload->>'vitiparcel_error'),''))
) p(proof_key,proof_label,source_field,recorded_text_value,recorded_boolean_value,requires_identified_passage,recorded_read_error);
COMMENT ON VIEW mart.reconciliation_acquisition_proof_current IS
'14 indicateurs par acquisition : valeurs originales et lecture prudente. Ce sont des lignes de preuves, pas des acquisitions supplementaires. FALSE sans verification possible de passage ne prouve pas une absence. Une preuve negative ou une erreur ne donne aucune autorisation de retraitement. Une valeur TRUE peut coexister avec une erreur supplementaire conservee dans recorded_read_error. Le critere VitiParcel ne certifie pas la qualite ou la livraison.';

COMMENT ON VIEW mart.reconciliation_proof_summary_current IS
'Synthese des 14 indicateurs avec libelles clarifies ; comptages par acquisition, pas nombre de livrables uniques. Les controles LEFT/RIGHT sont conserves. Etat technique distinct de commande client et de livraison.';
-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
