# Lecture du fichier — Tests de portfolio regressions.
#

"""Petits contrôles ajoutés lors de la préparation de la version partageable.

Les exceptions et les chemins sont fictifs. Aucun service externe n'est utilisé.
"""
# On importe os. On utilise les informations et opérations du système nécessaires à ce fichier.
import os
# On importe sys. On utilise les réglages et points d’entrée du processus Python courant.
import sys
# On rend disponibles Path depuis pathlib, pour les appels de ce fichier.
from pathlib import Path
# On rend disponibles patch depuis unittest.mock, pour les appels de ce fichier.
from unittest.mock import patch
# On importe unittest. On décrit les scénarios et les vérifications de la suite de tests.
import unittest

# On récupère Path(__file__).resolve().parents[1] et on le garde dans ROOT pour la suite.
ROOT = Path(__file__).resolve().parents[1]
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(ROOT / 'app'))
# On ajoute ce dossier aux chemins de recherche Python pour rendre les modules locaux importables dans
# ce contexte.
sys.path.insert(0, str(ROOT / 'scripts'))
# On importe data_access. Ce module sera utilisé par les opérations de ce fichier.
import data_access
# On importe dash_app. Ce module sera utilisé par les opérations de ce fichier.
import dash_app
# On importe prepare_airflow_workflow sous le nom preparation. Ce module sera utilisé par les
# opérations de ce fichier.
import prepare_airflow_workflow as preparation
# On importe prepare_airflow_workflow_wsl sous le nom wsl_preparation. Ce module sera utilisé par les
# opérations de ce fichier.
import prepare_airflow_workflow_wsl as wsl_preparation


class PortfolioRegressions(unittest.TestCase):
    # L’erreur simulée contient un détail privé. On vérifie qu’il ne remonte pas dans le message du
    # dashboard.
    def test_database_error_does_not_expose_connection_details(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {'DASHBOARD_USE_MOCK': '0'}), patch.object(data_access, 'DatabaseClient', side_effect=RuntimeError('private-connection-sentinel')):
            # On garde dans state la valeur renvoyée par data_access.load_dashboard_state.
            state = data_access.load_dashboard_state()
        # On vérifie que state.mode correspond à 'unavailable'.
        self.assertEqual(state.mode, 'unavailable')
        # On vérifie que 'private-connection-sentinel' ne figure pas dans state.status_message.
        self.assertNotIn('private-connection-sentinel', state.status_message)
        # On vérifie que 'DATABASE_UNAVAILABLE' figure dans state.status_message.
        self.assertIn('DATABASE_UNAVAILABLE', state.status_message)

    # Même si le calcul échoue, le callback doit fournir ses deux sorties attendues.
    def test_evolution_failure_preserves_two_outputs(self):
        # On remplace temporairement os.environ dans ce bloc de test ; le réglage initial sera rétabli
        # à sa sortie.
        with patch.dict(os.environ, {'DASHBOARD_USE_MOCK': '1'}):
            # On garde dans app la valeur renvoyée par dash_app.make_app.
            app = dash_app.make_app()
        # On garde dans callback le prochain élément de (value['callback'].__wrapped__ for key, value
        # in app.callback_map.items()….
        callback = next(value['callback'].__wrapped__ for key, value in app.callback_map.items() if 'evolution-chart-results' in key)
        # On remplace temporairement dash_app dans ce bloc de test ; le réglage initial sera rétabli à
        # sa sortie.
        with patch.object(dash_app, 'evolution_results', side_effect=ValueError('synthetic failure')), patch.object(dash_app.logging, 'exception'):
            # On garde dans result la valeur renvoyée par callback.
            result = callback({'mode': 'last_two', 'dates': []}, 'acquisition', 'all', 'count', {}, '__ALL__')
        # On vérifie que len(result) correspond à 2.
        self.assertEqual(len(result), 2)

    # Un chemin relatif dépend du dossier depuis lequel on lance le script. Ici, on exige une source
    # absolue avant de lire le projet.
    def test_wsl_rejects_relative_source_before_reading_project(self):
        # On attend wsl_preparation.WslPreparationError dans ce bloc ; si aucune erreur n’est levée, le
        # test doit échouer.
        with self.assertRaises(wsl_preparation.WslPreparationError):
            # On appelle wsl_preparation.prepare_wsl avec ROOT / 'nonexistent'.
            wsl_preparation.prepare_wsl(ROOT / 'nonexistent', 'relative/path')

    def test_single_mount_has_matching_compose_variable(self):
        # On garde dans compose le texte lu depuis ROOT / 'docker/docker-compose.airflow-workflow.yml'
        # avec l’encodage indiqué.
        compose = (ROOT / 'docker/docker-compose.airflow-workflow.yml').read_text(encoding='utf-8')
        # On parcourt ('prepare_airflow_workflow.py', 'prepare_airflow_workflow_wsl.py') ; script
        # désigne l’élément courant de ce scénario.
        for script in ('prepare_airflow_workflow.py', 'prepare_airflow_workflow_wsl.py'):
            # On garde dans source le texte lu depuis ROOT / 'scripts' / script avec l’encodage
            # indiqué.
            source = (ROOT / 'scripts' / script).read_text(encoding='utf-8')
            # On vérifie que 'PROJECT12_WORKFLOW_NAS_SOURCE' figure dans source.
            self.assertIn('PROJECT12_WORKFLOW_NAS_SOURCE', source)
        # On vérifie que '${PROJECT12_WORKFLOW_NAS_SOURCE:' figure dans compose.
        self.assertIn('${PROJECT12_WORKFLOW_NAS_SOURCE:', compose)
