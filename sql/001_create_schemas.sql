-- Les trois couches de la base métier : staging, core et mart.
-- On crée ici des espaces de rangement, pas encore leurs tables ni leurs données.
-- Ces schémas appartiennent à suivi_acquisitions. La base airflow_meta reste séparée : elle sert à
-- Airflow.


-- On regroupe les créations et les droits dans une même transaction.
BEGIN;


-- On ouvre la zone de réception des lignes et de leur provenance, avant leur présentation métier. IF
-- NOT EXISTS tolère un schéma déjà présent, sans vérifier toute sa configuration.
CREATE SCHEMA IF NOT EXISTS staging
    AUTHORIZATION projet12_admin;

COMMENT ON SCHEMA staging IS
    'Donnees recues du pipeline, avec leur provenance, avant validation et publication.';


-- On sépare ici les identités, versions, liens de provenance et historiques structurés.
CREATE SCHEMA IF NOT EXISTS core
    AUTHORIZATION projet12_admin;

COMMENT ON SCHEMA core IS
    'Donnees structurees et controlees, observations historisees et tracabilite des executions.';


-- On réserve cet espace aux vues de consultation. Le dashboard pourra les lire sans reconstruire
-- lui-même toutes les jointures.
CREATE SCHEMA IF NOT EXISTS mart
    AUTHORIZATION projet12_admin;

COMMENT ON SCHEMA mart IS
    'Vues et indicateurs metier prepares pour la consultation et le dashboard.';


-- On valide les créations et permissions de ce script si la transaction a réussi.
COMMIT;
