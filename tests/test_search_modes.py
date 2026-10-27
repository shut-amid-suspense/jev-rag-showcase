"""Exercise real PDF indexing and all three pipelines with a fake provider.

These are offline wiring regressions, not a model-accuracy evaluation.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev_rag import ui as app
from jev_rag import agent
from jev_rag import classic
from jev_rag import index_store
from jev_rag import keywords
from tests.fakes import FakeProvider
from jev_rag import api


class SearchModeTests(unittest.TestCase):
    def run_mode(self, mode):
        fake = FakeProvider()
        with tempfile.TemporaryDirectory() as folder, patch.object(index_store, 'DIR', folder):
            patches = [patch.object(module, 'post', fake.post) for module in [api, agent, classic, keywords]]
            for item in patches:
                item.start()
            try:
                app.INDEXES.clear()
                pdf = Path(__file__).resolve().parents[1] / 'examples/support-handbook.pdf'
                list(app.index_pdf(str(pdf), 'test-key-not-real'))
                fp = index_store.fingerprint(pdf)
                self.assertTrue(Path(index_store._path(fp)).exists())
                app.INDEXES.clear()  # simulate a new in-memory session; reload the JSON index
                index = app.find_index(fp)
                self.assertEqual(index['pages'], 8)
                fake.calls.clear()
                runner = app.METHODS[mode][2]
                events = list(runner('Who owns the Atlas support handover?', index,
                                     'test-key-not-real', provider='gemini'))
                result = next(value for kind, value in reversed(events) if kind == 'done')
                self.assertIn('Nora Chen', result['answer'])
                self.assertEqual(result['sources'][0]['page'], 1)
                decision_calls = sum(url.endswith('/decisions') for url in fake.calls)
                self.assertEqual(decision_calls, 0 if mode == 'classic' else 1)
            finally:
                for item in reversed(patches):
                    item.stop()
                app.INDEXES.clear()

    def test_fast_indexes_reloads_and_answers_without_jev(self):
        self.run_mode('classic')

    def test_standard_indexes_reloads_and_ranks_with_jev(self):
        self.run_mode('keywords')

    def test_thorough_indexes_reloads_and_uses_jev_in_agent_search(self):
        self.run_mode('agent')
