"""Adversarial artifact checks and an offline run through the benchmark CLI."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import compare_search_modes as benchmark
from scripts import verify_evidence as evidence
from tests.fakes import FakeProvider
from jev_rag import ui as app
from jev_rag import agent
from jev_rag import classic
from jev_rag import index_store
from jev_rag import keywords
from jev_rag import api


class EvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.result = json.loads((ROOT / 'docs/comparisons' / evidence.RESULT).read_text())
        self.review = json.loads((ROOT / 'docs/comparisons/2026-10-26-accuracy-review.json').read_text())
        self.case = json.loads((ROOT / 'benchmarks/cases/troubleshooting-live11.json').read_text())

    def test_recorded_metrics_are_consistent(self):
        evidence.verify_run(self.result)
        evidence.verify_review(self.review, self.result, self.case)

    def test_modified_request_cost_is_detected(self):
        self.result['application'][0]['requests'][0]['cost_usd'] += 0.01
        with self.assertRaises(ValueError):
            evidence.verify_run(self.result)

    def test_modified_latency_summary_is_detected(self):
        self.result['summary']['Standard']['median_seconds'] += 1
        with self.assertRaises(ValueError):
            evidence.verify_run(self.result)

    def test_duplicate_result_cannot_hide_missing_mode(self):
        self.result['application'][0] = copy.deepcopy(self.result['application'][1])
        with self.assertRaises(ValueError):
            evidence.verify_run(self.result)

    def test_inconsistent_grade_label_and_points_are_detected(self):
        self.review['reviews'][0]['grades'][0]['status'] = 'covered'
        with self.assertRaises(ValueError):
            evidence.verify_review(self.review, self.result, self.case)

    def test_modified_strict_task_summary_is_detected(self):
        self.review['summary']['Fast']['strict_complete_tasks'] += 1
        with self.assertRaises(ValueError):
            evidence.verify_review(self.review, self.result, self.case)

    def test_modified_jev_selected_evidence_is_detected(self):
        self.review['fixed_pool_jev_ranking'][0]['jev_selected_five_ids'][0] = 'invented'
        with self.assertRaises(ValueError):
            evidence.verify_review(self.review, self.result, self.case)


class BenchmarkTests(unittest.TestCase):
    def test_generated_fixture_refreshes_on_source_change_and_reuses_unchanged_pdf(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / 'source.txt', Path(folder) / 'fixture.pdf'
            source.write_text('Original operations handbook.')
            benchmark.ensure_fixture(source, target)
            original = target.read_bytes()
            benchmark.ensure_fixture(source, target)
            self.assertEqual(target.read_bytes(), original)
            source.write_text('Updated operations handbook.')
            benchmark.ensure_fixture(source, target)
            with pymupdf.open(target) as document:
                self.assertIn('Updated operations', document[0].get_text())

    def test_cli_records_all_modes_and_preserves_existing_reports(self):
        fake = FakeProvider()
        with tempfile.TemporaryDirectory(dir=ROOT / 'data') as folder, contextlib.ExitStack() as stack:
            directory = Path(folder)
            relative = directory.relative_to(ROOT)
            case = {'document': str(relative / 'input.pdf'),
                    'generate_from': 'benchmarks/fixtures/support-handbook.txt',
                    'questions': [{'q': 'Who owns the Atlas support handover?', 'page': 1}]}
            case_path = directory / 'case.json'
            case_path.write_text(json.dumps(case))
            argv = ['compare_search_modes.py', '--case', str(case_path.relative_to(ROOT)),
                    '--output-prefix', str(relative / 'measured')]
            for module in [api, agent, classic, keywords]:
                stack.enter_context(patch.object(module, 'post', fake.post))
            stack.enter_context(patch.object(index_store, 'DIR', str(directory / 'indexes')))
            stack.enter_context(patch.dict('os.environ', {'OPENROUTER_API_KEY': 'offline-test-key'}))
            stack.enter_context(patch.object(sys, 'argv', argv))
            app.INDEXES.clear()
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    benchmark.main()
                result_path = directory / 'measured.json'
                result = json.loads(result_path.read_text())
                self.assertIn('jev_rag/retrieval.py', result['application_source_sha256'])
                self.assertIn('jev_rag/ui.py', result['application_source_sha256'])
                self.assertFalse(any(name.startswith('experiments/') for name in result['application_source_sha256']))
                evidence.verify_run(result)
                self.assertEqual({row['mode'] for row in result['application']}, set(evidence.MODES))
                self.assertEqual([result['summary'][mode]['jev_calls'] for mode in evidence.MODES], [0, 1, 1])
                report = (directory / 'measured.md').read_text()
                self.assertIn('successful recorded requests', report)
                expected_link = Path(benchmark.os.path.relpath(ROOT / 'benchmarks/README.md', directory)).as_posix()
                self.assertIn(f']({expected_link})', report)
                original = result_path.read_bytes()
                calls = len(fake.calls)
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    benchmark.main()
                self.assertEqual(result_path.read_bytes(), original)
                self.assertEqual(len(fake.calls), calls)
            finally:
                app.INDEXES.clear()


class ErrorPrivacyTests(unittest.TestCase):
    def test_provider_error_body_is_not_exposed_in_exception_or_server_log(self):
        body = b'sensitive-document-fragment test-private-key'
        error = api.HTTPStatusError('https://provider.example/request', 400, body)
        self.assertNotIn('sensitive-document-fragment', str(error))
        self.assertNotIn('test-private-key', str(error))
        log = io.StringIO()
        with contextlib.redirect_stderr(log):
            message = app.friendly(error)
        self.assertNotIn('sensitive-document-fragment', log.getvalue())
        self.assertNotIn('test-private-key', log.getvalue())
        self.assertIn('400', message)


if __name__ == '__main__':
    unittest.main()
