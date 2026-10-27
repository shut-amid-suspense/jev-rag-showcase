"""Offline regressions for local state and credential handling. No provider calls or real keys."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'

import app
import index_store
import poc


def sample_index():
    chunks = [{'id': 'c0', 'page': 1, 'section': 'Support', 'label': '[Support, p. 1] ',
               'text': '[Support, p. 1] Atlas handover owner is Nora Chen.'}]
    return {'name': 'sample.pdf', 'pages': 1, 'chunks': chunks,
            'uvecs': [[1.0, 0.0, 0.0]], 'bm25': poc.BM25([c['text'] for c in chunks])}


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(index_store, 'DIR', self.temp.name)
        self.patch.start()
        self.fp = 'a' * 64

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_round_trip_preserves_passages_vectors_and_search(self):
        original = sample_index()
        index_store.save(self.fp, original)
        loaded = index_store.load(self.fp)
        self.assertEqual(loaded['chunks'], original['chunks'])
        self.assertEqual(loaded['uvecs'], original['uvecs'])
        self.assertGreater(loaded['bm25'].scores('Nora')[0], 0)
        self.assertEqual(json.loads(Path(index_store._path(self.fp)).read_text())['version'], 2)

    def test_invalid_fingerprint_cannot_escape_cache(self):
        self.assertIsNone(index_store.load('../outside'))
        with self.assertRaises(ValueError):
            index_store.save('../outside', sample_index())
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_corrupt_json_is_a_cache_miss(self):
        Path(index_store._path(self.fp)).write_text('{broken')
        self.assertIsNone(index_store.load(self.fp))

    def test_old_pickle_is_not_loaded(self):
        (Path(self.temp.name) / (self.fp + '.pkl')).write_bytes(b'not a trusted index')
        self.assertIsNone(index_store.load(self.fp))

    def test_wrong_embedding_model_is_a_cache_miss(self):
        index_store.save(self.fp, sample_index())
        path = Path(index_store._path(self.fp))
        data = json.loads(path.read_text())
        data['embedding_model'] = 'different-model'
        path.write_text(json.dumps(data))
        self.assertIsNone(index_store.load(self.fp))

    def test_invalid_vector_dimensions_are_rejected(self):
        data = sample_index()
        data['uvecs'].append([1.0, 0.0])
        with self.assertRaises(ValueError):
            index_store.save(self.fp, data)

    def test_non_finite_vectors_are_rejected(self):
        data = sample_index()
        data['uvecs'][0][0] = float('nan')
        with self.assertRaises(ValueError):
            index_store.save(self.fp, data)

    def test_oversized_numeric_cache_values_are_a_cache_miss(self):
        index_store.save(self.fp, sample_index())
        path = Path(index_store._path(self.fp))
        data = json.loads(path.read_text())
        data['uvecs'][0][0] = 10 ** 400
        path.write_text(json.dumps(data))
        self.assertIsNone(index_store.load(self.fp))

    @unittest.skipIf(os.name == 'nt', 'POSIX file permissions')
    def test_cache_files_are_owner_only(self):
        index_store.save(self.fp, sample_index())
        self.assertEqual(stat.S_IMODE(Path(index_store._path(self.fp)).stat().st_mode), 0o600)

    def test_retention_does_not_remove_unrelated_json(self):
        unrelated = Path(self.temp.name) / 'notes.json'
        unrelated.write_text('{}')
        with patch.object(index_store, 'MAX_SAVED', 2):
            for letter in 'abc':
                index_store.save(letter * 64, sample_index())
        self.assertTrue(unrelated.exists())
        self.assertEqual(len([p for p in Path(self.temp.name).glob('*.json') if len(p.stem) == 64]), 2)


class CredentialTests(unittest.TestCase):
    def test_api_keys_use_session_state_not_browser_storage(self):
        import gradio as gr
        self.assertIsInstance(app.saved_key, gr.State)
        self.assertIsInstance(app.saved_cb, gr.State)
        self.assertNotIsInstance(app.saved_key, gr.BrowserState)

    def test_key_status_never_displays_key_values(self):
        output = repr(app.key_view('test-private-openrouter', 'test-private-cerebras', 'gemini'))
        self.assertNotIn('test-private-openrouter', output)
        self.assertNotIn('test-private-cerebras', output)
        self.assertIn('this session only', output)

    def test_key_validation_holds_value_in_state_and_clears_fields(self):
        with patch.object(app, 'embed', return_value=([[1.0]], 0, {})) as embed:
            result = app.save_keys('test-session-key', '', '', '', 'gemini')
        self.assertEqual(result[0], 'test-session-key')
        self.assertEqual(result[3:5], ('', ''))
        embed.assert_called_once_with(['key check'], 'test-session-key')

    def test_cli_key_only_comes_from_environment(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-env-key'}):
            self.assertEqual(poc.api_key(), 'test-env-key')
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                poc.api_key()


class WiringTests(unittest.TestCase):
    def test_all_three_modes_keep_their_application_runners(self):
        self.assertEqual([item[0] for item in app.METHODS.values()], ['Fast', 'Standard', 'Thorough'])
        self.assertEqual([item[2].__name__ for item in app.METHODS.values()],
                         ['run_classic', 'run_keywords', 'run_agent'])

    def test_synthetic_pdf_is_included_and_text_is_readable(self):
        import pymupdf
        with pymupdf.open(ROOT / 'examples/support-handbook.pdf') as document:
            self.assertEqual(len(document), 8)
            self.assertIn('Nora Chen', document[0].get_text())


if __name__ == '__main__':
    unittest.main()
