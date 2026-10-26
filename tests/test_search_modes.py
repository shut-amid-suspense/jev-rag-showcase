"""Exercise real PDF indexing and all three pipelines with a fake provider.

These are offline wiring regressions, not a model-accuracy evaluation.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
import agent
import classic
import index_store
import keywords
import poc


class FakeProvider:
    def __init__(self):
        self.calls = []

    def post(self, url, body, key, attempts=3):
        self.calls.append(url)
        usage = {'cost': 0.000001, 'prompt_tokens': 10, 'completion_tokens': 5}
        if url.endswith('/embeddings'):
            vectors = []
            for number, text in enumerate(body['input']):
                vector = [1.0, 0.0, 0.0] if 'atlas' in text.lower() else [0.0, 1.0, 0.0]
                vectors.append({'index': number, 'embedding': vector})
            return {'data': vectors, 'usage': usage}, 1.0
        if url.endswith('/decisions'):
            answers = {}
            for name, question in body['questions'].items():
                criteria = question['criteria']
                selected = next((item for item, text in criteria.items() if 'Nora Chen' in text), next(iter(criteria)))
                answers[name] = {'choice': selected, 'confidence': 1,
                                 'probabilities': {item: int(item == selected) for item in criteria}}
            return {'answers': answers, 'usage': usage}, 1.0
        names = [tool['function']['name'] for tool in body['tools']]
        if 'search_terms' in names:
            name, arguments = 'search_terms', {'terms': ['Atlas support handover owner']}
        elif 'search' in names and not any(message['role'] == 'tool' for message in body['messages']):
            name, arguments = 'search', {'query': 'Atlas support handover owner'}
        else:
            name, arguments = 'final_answer', {'answer': 'The Atlas handover owner is Nora Chen.', 'passage_ids': ['c0']}
        message = {'content': '', 'tool_calls': [{'id': 'test-call', 'type': 'function',
                    'function': {'name': name, 'arguments': json.dumps(arguments)}}]}
        return {'choices': [{'message': message}], 'usage': usage}, 1.0


class SearchModeTests(unittest.TestCase):
    def run_mode(self, mode):
        fake = FakeProvider()
        with tempfile.TemporaryDirectory() as folder, patch.object(index_store, 'DIR', folder):
            patches = [patch.object(module, 'post', fake.post) for module in [poc, agent, classic, keywords]]
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
