"""Deterministic provider responses for offline pipeline and CLI tests."""
import json


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
