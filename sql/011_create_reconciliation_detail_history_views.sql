-- Ouvrir le détail historique des acquisitions, passages et associations.
-- Une acquisition peut apparaître dans plusieurs bilans : les clés du rapprochement permettent de
-- distinguer ces observations.
-- La vue d’associations courantes filtre ensuite cet historique sur le bilan actif de chaque domaine.

-- On regroupe les créations et les droits dans une même transaction.
BEGIN;

-- On expose les acquisitions de tous les rapprochements conservés. Les identifiants du bilan
-- distinguent deux observations de la même acquisition.
CREATE OR REPLACE VIEW mart.reconciliation_acquisition_history AS
-- On conserve le domaine et les identifiants du bilan pour retrouver l’origine de chaque ligne de
-- détail.
SELECT h.vineyard_key, h.vineyard_name, h.pipeline_execution_id, h.reconciliation_run_id,
       -- Ces deux identifiants retrouvent le parcours d’observation NAS et son extraction, avant le
       -- calcul du rapprochement.
       h.nas_pipeline_execution_id, h.extraction_run_id,
       -- On garde le lot et la version Excel utilisés par ce bilan, pas ceux d’une publication apparue
       -- plus tard.
       h.excel_publication_id, h.excel_version_id, h.excel_ingested_at,
       -- On distingue la date du contrôle NAS, celle du croisement et celle du chargement du bilan en
       -- base.
       h.nas_checked_at, h.reconciled_at, h.reconciliation_loaded_at,
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
       -- Ce classement porte sur les rattachements acquisition–parcelle–passage, séparément du
       -- traitement des images.
       a.payload->>'relationship_business_category' AS recorded_relationship_category,
       -- Le JSON complet reste disponible pour consulter les détails qui ne sont pas exposés dans des
       -- colonnes dédiées.
       a.payload
FROM mart.reconciliation_vineyard_history h
-- La jointure utilise exécution, domaine et rapprochement : elle ne doit pas ramener le détail d’un
-- autre bilan du même domaine.
JOIN staging.reconciliation_acquisition_rows a
  ON a.pipeline_execution_id = h.pipeline_execution_id
 AND a.vineyard_key = h.vineyard_key
 AND a.reconciliation_run_id = h.reconciliation_run_id;
COMMENT ON VIEW mart.reconciliation_acquisition_history IS 'Une ligne par acquisition ET rapprochement conserve. Les categories sont celles enregistrees a cette date, sans recalcul. Lire vitiparcel_created avec passage_outputs_verifiable : non verifiable ne signifie pas absent.';

-- On conserve l’accès aux passages de chaque ancien bilan, pas seulement à leur dernier état activé.
CREATE OR REPLACE VIEW mart.reconciliation_passage_history AS
SELECT h.vineyard_key, h.vineyard_name, h.pipeline_execution_id, h.reconciliation_run_id,
       h.nas_pipeline_execution_id, h.extraction_run_id,
       h.excel_publication_id, h.excel_version_id, h.excel_ingested_at,
       h.nas_checked_at, h.reconciled_at, h.reconciliation_loaded_at,
       -- La parcelle et le passage identifient la sortie ; le drapeau de vérifiabilité précise si son
       -- critère est interprétable.
       p.parcel_name, p.passage_name, p.vitiparcel_ready_verifiable,
       -- On conserve le critère technique enregistré et la demande éventuelle de revue, sans conclure
       -- à une livraison.
       p.vitiparcel_ready_for_delivery, p.passage_review_candidate,
       -- On reprend la conclusion enregistrée pour ce passage, plutôt que la recalculer à la
       -- consultation.
       p.payload->>'passage_business_category' AS recorded_passage_category, p.payload
FROM mart.reconciliation_vineyard_history h
JOIN staging.reconciliation_passage_rows p
  ON p.pipeline_execution_id = h.pipeline_execution_id
 AND p.vineyard_key = h.vineyard_key
 AND p.reconciliation_run_id = h.reconciliation_run_id;
COMMENT ON VIEW mart.reconciliation_passage_history IS 'Une ligne par passage ET rapprochement conserve. Critere technique satisfait ne signifie pas livraison client. Aucun passage fictif pour les acquisitions sans passage identifie.';

-- On rend consultables les liens acquisition–parcelle–passage de chaque rapprochement historique.
CREATE OR REPLACE VIEW mart.reconciliation_association_history AS
SELECT h.vineyard_key, h.vineyard_name, h.pipeline_execution_id, h.reconciliation_run_id,
       h.nas_pipeline_execution_id, h.extraction_run_id,
       h.excel_publication_id, h.excel_version_id, h.excel_ingested_at,
       h.nas_checked_at, h.reconciled_at, h.reconciliation_loaded_at,
       a.acquisition_id_normalise, a.parcel_name, a.passage_name, a.payload
FROM mart.reconciliation_vineyard_history h
JOIN staging.reconciliation_association_rows a
  ON a.pipeline_execution_id = h.pipeline_execution_id
 AND a.vineyard_key = h.vineyard_key
 AND a.reconciliation_run_id = h.reconciliation_run_id;
COMMENT ON VIEW mart.reconciliation_association_history IS 'Une ligne par lien acquisition-parcelle-passage ET rapprochement conserve. Plusieurs liens par acquisition et plusieurs acquisitions par passage possibles. Zero association reste zero : aucun lien invente.';

-- On filtre les associations historiques sur les seuls bilans actifs, en gardant leur contexte de
-- version Excel.
CREATE OR REPLACE VIEW mart.reconciliation_association_current AS
SELECT a.*, c.activated_in_database_at, c.excel_version_matches_current
FROM mart.reconciliation_association_history a
-- On filtre le détail historique avec la clé complète du bilan actif afin de ne pas mélanger les dates
-- d’observation.
JOIN mart.reconciliation_vineyard_current c
  ON c.pipeline_execution_id = a.pipeline_execution_id
 AND c.vineyard_key = a.vineyard_key
 AND c.reconciliation_run_id = a.reconciliation_run_id;
COMMENT ON VIEW mart.reconciliation_association_current IS
'Associations du rapprochement actuellement active pour chaque vignoble. La comparaison de version Excel est un indicateur de provenance, sans reclassement. Ne pas confondre nombre de liens, acquisitions et passages.';

-- On ouvre la consultation des objets listés au groupe lecteur ; les tables internes ne sont pas
-- ajoutées implicitement à ce périmètre.
GRANT SELECT ON mart.reconciliation_acquisition_history,
                mart.reconciliation_passage_history,
                mart.reconciliation_association_history,
                mart.reconciliation_association_current
TO projet12_mart_reader;
-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
