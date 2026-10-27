"""Dependency-boundary and entry-point checks for the repository layout."""
import ast
import importlib
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from jev_rag import api
from jev_rag.paths import ROOT
from jev_rag.retrieval import BM25, rrf, top_k


class RepositoryLayoutTests(unittest.TestCase):
    def test_runtime_import_does_not_load_experiments(self):
        code = "import sys; import jev_rag.ui; assert not any(n == 'experiments' or n.startswith('experiments.') for n in sys.modules)"
        process = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT,
                                 env={**os.environ, 'GRADIO_ANALYTICS_ENABLED': 'False'},
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        forbidden = {'experiments', 'poc', 'squad_eval', 'ableton_eval', 'section_eval', 'clef_eval'}
        for path in (ROOT / 'jev_rag').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    names = [name.name.split('.')[0] for name in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [(node.module or '').split('.')[0]]
                else:
                    continue
                self.assertFalse(forbidden.intersection(names), str(path))

    def test_every_experiment_imports_without_provider_requests(self):
        with patch.object(api, 'post', side_effect=AssertionError('Request during import')):
            for name in ['poc', 'squad_eval', 'ableton_eval', 'section_eval', 'clef_eval']:
                module = importlib.import_module('experiments.' + name)
                self.assertTrue(Path(module.__file__).is_file())
        from experiments import ableton_eval, squad_eval
        self.assertEqual(Path(ableton_eval.QUESTIONS), ROOT / 'experiments/fixtures/ableton-questions.json')
        self.assertTrue(Path(ableton_eval.QUESTIONS).is_file())
        self.assertEqual(Path(squad_eval.DATA).parent, ROOT / 'data')
        for name in ['poc.json', 'squad.json', 'ableton.json', 'section.json', 'clef.json']:
            self.assertTrue((ROOT / 'experiments/results' / name).is_file())

    def test_shared_retrieval_preserves_keyword_vector_and_fusion_behavior(self):
        keyword = BM25(['daily backup and restore', 'invoice payment adjustment'])
        self.assertGreater(keyword.scores('restore')[0], keyword.scores('restore')[1])
        self.assertEqual(top_k([0, 2], [[1, 0], [0, 1]], 2), [1, 0])
        self.assertEqual(rrf([0, 1], [1, 2])[0], 1)


if __name__ == '__main__':
    unittest.main()
