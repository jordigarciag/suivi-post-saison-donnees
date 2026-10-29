"""On vérifie le scénario public, séparément des petits cas unitaires de mock_fixture."""

import unittest
import pandas as pd
from mock_data import build_mock_state, DEMO_VINEYARDS
from history_engine import batch_options, compare_history, IDENTITY
from data_access import load_dashboard_state


class DemoDataTests(unittest.TestCase):
    def setUp(self):
        # Chaque test reçoit ses propres tableaux : une modification ne déborde pas sur le suivant.
        self.frames = build_mock_state()

    def test_five_vineyards_and_fifty_acquisitions(self):
        acquisitions = self.frames['reconciliation_acquisition_current']
        self.assertEqual(set(acquisitions.vineyard_name), set(DEMO_VINEYARDS))
        self.assertEqual(len(acquisitions), 50)
        self.assertTrue(acquisitions.groupby('vineyard_name').size().eq(10).all())

    def test_four_complete_scans(self):
        # Tous les vignobles sont couverts à chaque date ; aucun état courant ne comble un trou.
        metadata = self.frames['reconciliation_vineyard_history']
        self.assertEqual(len(batch_options(self.frames)), 4)
        self.assertTrue(metadata.groupby('pipeline_execution_id').size().eq(5).all())
        volumes = self.frames['reconciliation_acquisition_history'].groupby('pipeline_execution_id').size()
        self.assertEqual(list(volumes.sort_index()), [25, 40, 45, 50])

    def test_declared_volumes_match_details(self):
        # Les compteurs de synthèse doivent annoncer les vrais détails, y compris les associations.
        for kind in ('acquisition', 'passage', 'association'):
            actual = self.frames[f'reconciliation_{kind}_history'].groupby(IDENTITY).size()
            for row in self.frames['reconciliation_vineyard_history'].to_dict('records'):
                key = tuple(row[field] for field in IDENTITY)
                self.assertEqual(actual.loc[key], row[f'{kind}_count'])

    def test_current_is_exactly_last_snapshot(self):
        for kind in ('acquisition', 'passage', 'association'):
            history = self.frames[f'reconciliation_{kind}_history']
            expected = history[history.pipeline_execution_id.eq('demo_20261022')].reset_index(drop=True)
            pd.testing.assert_frame_equal(expected, self.frames[f'reconciliation_{kind}_current'])

    def test_every_transition_contains_business_changes(self):
        runs = [option['value'] for option in reversed(batch_options(self.frames))]
        for before, after in zip(runs, runs[1:]):
            with self.subTest(before=before, after=after):
                result = compare_history(self.frames, selected=[before, after], latest=False)
                self.assertEqual(result.comparable, result.expected)
                self.assertGreater(result.counts()['changed'], 0)
                self.assertFalse(result.messages)

    def test_links_reference_same_snapshot_entities(self):
        # Une association ne doit pas pointer vers une acquisition ou un passage d’un autre scan.
        for kind, extra in [('acquisition', ['acquisition_id_normalise']), ('passage', ['parcel_name', 'passage_name'])]:
            keys = IDENTITY + extra
            detail = self.frames[f'reconciliation_{kind}_history']
            allowed = set(map(tuple, detail[keys].itertuples(index=False, name=None)))
            links = self.frames['reconciliation_association_history']
            self.assertTrue(set(map(tuple, links[keys].itertuples(index=False, name=None))) <= allowed)

    def test_error_resolved_but_another_remains_unknown(self):
        history = self.frames['reconciliation_acquisition_history']
        recovered = history[history.acquisition_id_normalise.eq('DEMO_C_005')].set_index('pipeline_execution_id')
        self.assertTrue(recovered.loc['demo_20261021', 'has_technical_error'])
        self.assertIsNone(recovered.loc['demo_20261021', 'processing_has_webp_images'])
        self.assertFalse(recovered.loc['demo_20261022', 'has_technical_error'])
        persistent = history[history.acquisition_id_normalise.eq('DEMO_E_006')]
        self.assertTrue(persistent.processing_has_webp_images.isna().all())

    def test_final_scan_keeps_incomplete_production(self):
        acquisitions = self.frames['reconciliation_acquisition_current']
        pending = acquisitions[acquisitions.excel_perimeter.eq('Production') & acquisitions.processing_has_webp_images.eq(False)]
        self.assertEqual(pending.vineyard_name.nunique(), 5)

    def test_each_load_is_deterministic_and_independent(self):
        other = build_mock_state()
        for key in self.frames:
            pd.testing.assert_frame_equal(self.frames[key], other[key])
        # On modifie aussi une liste imbriquée, pour contrôler davantage qu’une copie de DataFrame.
        self.frames['reconciliation_passage_current'].iloc[0]['acquisition_ids_json'].append('FAUX')
        self.assertNotIn('FAUX', other['reconciliation_passage_current'].iloc[0]['acquisition_ids_json'])

    def test_explicit_mock_loader_uses_enriched_data(self):
        state = load_dashboard_state(force_mock=True)
        self.assertEqual(state.mode, 'mock')
        self.assertEqual(len(state.frames['reconciliation_acquisition_current']), 50)
