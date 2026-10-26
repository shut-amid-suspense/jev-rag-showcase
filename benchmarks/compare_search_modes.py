"""Benchmark all three Jev RAG application modes using repository-local inputs.

Run with the project's Python environment and an OPENROUTER_API_KEY supplied by
Sesame. No source code or credentials are read from another repository.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def local_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('Benchmark inputs and outputs must be inside this repository')
    return path


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_fixture(source: Path, target: Path) -> None:
    import pymupdf
    target.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as document:
        for text in source.read_text().split('\n---\n'):
            page = document.new_page(width=595, height=842)
            remaining = page.insert_textbox(pymupdf.Rect(42, 42, 553, 800), text.strip(),
                                            fontsize=11, fontname='helv')
            if remaining < 0:
                raise ValueError('Fixture page overflows; shorten the source text')
        document.save(target)


def summary(rows: list[dict]) -> dict:
    out = {}
    for mode in ['Fast', 'Standard', 'Thorough']:
        group = [row for row in rows if row['mode'] == mode]
        if not group:
            continue
        out[mode] = {
            'queries': len(group),
            'completed_answers': sum(bool(row.get('answer')) for row in group),
            'median_seconds': statistics.median(row['seconds'] for row in group),
            'slowest_seconds': max(row['seconds'] for row in group),
            'mean_known_cost_usd': statistics.mean(row['known_cost_usd'] for row in group),
            'total_known_cost_usd': sum(row['known_cost_usd'] for row in group),
            'mean_requests': statistics.mean(len(row['requests']) for row in group),
            'unknown_cost_requests': sum(row['unknown_cost_requests'] for row in group),
            'jev_calls': sum('/decisions' in call['endpoint'] for row in group for call in row['requests']),
            'expected_page_cited': sum(row.get('expected_page_cited', False) for row in group),
            'answerable_questions': sum(row['expected_page'] is not None for row in group),
            'empty_answers': sum(not row.get('answer') for row in group),
        }
    return out


def write_report(data: dict, target: Path, result_path: Path) -> None:
    lines = ['# Jev RAG POC: Fast, Standard and Thorough', '',
        'This benchmark compares the three search modes exposed by this application. All application code, test questions, the benchmark runner and the recorded results belong to this repository.', '',
        '## Scope and method', '',
        '- **Jev RAG — Fast:** one hybrid keyword/embedding search; answer from the top five passages.',
        '- **Jev RAG — Standard:** generate search terms, combine their search results, rank up to 40 candidates with Jev, and answer from five passages.',
        '- **Jev RAG — Thorough:** an agent can search repeatedly with Jev, read whole pages and then answer; the application limits it to six model turns.', '',
        f"Run started: {data['started_at']}. Document: `{data['document']}`. Questions: `{data['case_file']}`.", '',
        f"The same {len(data['questions'])} questions, document index, and answer model were used for each mode. Mode order rotated for successive questions. Requests within each answer ran sequentially; indexing used the application's normal batching.", '',
        f"Answer model: `{data['models']['answer']}`. Embeddings: `{data['models']['embedding']}`. Jev: `{data['models']['reranker']}`.", '',
        'The runner calls the application functions directly. It does not automate browser interactions or test screenshots. Application source hashes and request-level usage are recorded in the JSON.', '',
        '## Whole-answer measurements', '',
        '| Jev RAG mode | Median time | Slowest | Mean cost per question | Estimated cost per 1,000 | Mean API requests |',
        '|---|---:|---:|---:|---:|---:|']
    for mode, values in data['summary'].items():
        price = f"${values['mean_known_cost_usd']:.6f}"
        per_1000 = f"${values['mean_known_cost_usd']*1000:.2f}"
        if values['unknown_cost_requests']:
            price += ' + unknown charges'
            per_1000 = 'incomplete cost data'
        lines.append(f"| Jev RAG — {mode} | {values['median_seconds']:.2f} s | {values['slowest_seconds']:.2f} s | {price} | {per_1000} | {values['mean_requests']:.1f} |")
    lines += ['',
        'Costs are provider-reported `usage.cost` for the complete answer pipeline: query embeddings, query expansion where used, reranking where used and answer generation. Initial indexing is separate. Per-1,000 figures extrapolate this small sample; they are not a bulk run or guaranteed prices.', '',
        f"Index preparation: {data['indexing']['seconds']:.2f} s, ${data['indexing']['known_cost_usd']:.6f}, {data['indexing']['passages']} passages. Saved index reused: {data['indexing']['reused']}.", '',
        f"Total known API cost for this run, including any indexing calls: ${data['total_known_cost_usd']:.6f}.", '',
        '## Where Jev was used', '',
        'Jev is the passage decision/ranking model. Gemini generates the final answer. The recorded requests show the following actual Jev API calls:', '',
        '| Jev RAG mode | Jev decision API calls in this run |', '|---|---:|',
        *[f"| Jev RAG — {mode} | {values['jev_calls']} |" for mode, values in data['summary'].items()], '',
        '## Answer-quality limits', '',
        'Expected-page matching is a retrieval/citation check, not an answer-correctness score. A document may contain the same instruction on several pages. No blinded answer-quality judging was performed. The sample and one timing run per question do not establish a general accuracy winner. Standard and Thorough change the retrieval workflow as well as using Jev, so their differences cannot be attributed entirely to the ranking model.', '',
        '| Jev RAG mode | Answers returned | Expected page cited on answerable questions | Empty answers |',
        '|---|---:|---:|---:|']
    for mode, values in data['summary'].items():
        lines.append(f"| Jev RAG — {mode} | {values['completed_answers']}/{values['queries']} | {values['expected_page_cited']}/{values['answerable_questions']} | {values['empty_answers']} |")
    lines += ['',
        'Questions marked with no expected page are absence controls when present. Their full answers and source lists are preserved below; empty citations by themselves do not prove a correct refusal. If the case includes required-fact criteria, these need a separate source-grounded review; the timing runner does not automatically establish answer accuracy.', '',
        '## Reproduce from this repository', '',
        '[Benchmark instructions](../../benchmarks/README.md) include a synthetic handbook and questions that are committed in this repository. The default run builds its own PDF from that fixture, so it does not require a downloaded manual or another checkout.', '',
        'Run this exact case from the repository root after making its PDF available at the recorded repository-local path:', '',
        '```bash',
        f"sesame run OPENROUTER_API_KEY -- .venv/bin/python benchmarks/compare_search_modes.py --case {data['case_file']} --output-prefix docs/comparisons/repeated-jev-rag-modes",
        '```', '',
        'The Ableton manual case uses a copyrighted local PDF and is therefore not the default portable case. The PDF and generated indexes are ignored by Git. Its SHA-256 is recorded for comparison; the questions and all measured results are committed here.', '',
        f"[Machine-readable measured results]({result_path.name})", '',
        '## All answers', '']
    for number, question in enumerate(data['questions'], 1):
        lines += [f"### {number}. {question['q']}", '']
        for mode in ['Fast', 'Standard', 'Thorough']:
            row = next(row for row in data['application'] if row['question_number'] == number and row['mode'] == mode)
            pages = ', '.join(map(str, row['source_pages'])) or 'none'
            lines += [f"**Jev RAG — {mode}: {row['seconds']:.2f} s; ${row['known_cost_usd']:.6f}; source pages: {pages}; model turns: {row.get('turns', 'unknown')}**", '',
                      row.get('answer') or 'No answer was returned.', '']
    target.write_text('\n'.join(line.rstrip() for line in '\n'.join(lines).splitlines()).rstrip()+'\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', default='benchmarks/cases/support-handbook.json')
    parser.add_argument('--output-prefix', default='docs/comparisons/jev-rag-modes')
    parser.add_argument('--check', action='store_true', help='Validate local inputs and all three modes without API calls')
    args = parser.parse_args()
    case_path = local_path(args.case)
    case = json.loads(case_path.read_text())
    pdf_path = local_path(case['document'])
    if case.get('generate_from') and not pdf_path.exists():
        make_fixture(local_path(case['generate_from']), pdf_path)
    if not pdf_path.exists():
        parser.error(f"Document missing: {case['document']}. Use the default synthetic case for a complete in-repository example.")
    questions = case['questions']
    if not questions or any(not item['q'].strip() for item in questions):
        parser.error('The case must contain nonempty questions')
    os.environ['ASK_PDF_INDEX_DIR'] = str(ROOT / 'data/benchmark-cache/indexes')
    os.environ['GRADIO_ANALYTICS_ENABLED'] = 'False'
    sys.path.insert(0, str(ROOT))
    import app
    import agent
    import classic
    import keywords
    import poc

    modes = [(label, runner) for label, _, runner in app.METHODS.values()]
    if {label for label, _ in modes} != {'Fast', 'Standard', 'Thorough'}:
        raise RuntimeError('Application modes changed; review benchmark coverage')
    if args.check:
        import pymupdf
        with pymupdf.open(pdf_path) as document:
            for item in questions:
                if item['page'] is not None:
                    assert 1 <= item['page'] <= len(document)
                    assert len(document[item['page']-1].get_text().split()) >= app.MIN_WORDS
            if case.get('generate_from'):
                for item in questions:
                    for fact in item.get('expected_facts', []):
                        assert fact.lower() in document[item['page']-1].get_text().lower(), fact
        print(f"Checked {relative(case_path)}: {len(questions)} questions, local document, all three Jev RAG modes; no API calls.")
        return
    key = os.environ.get('OPENROUTER_API_KEY', '').strip()
    if not key:
        parser.error('Supply OPENROUTER_API_KEY through sesame run')
    output_prefix = local_path(args.output_prefix)
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    result_path = output_prefix.with_suffix('.json')
    report_path = output_prefix.with_suffix('.md')
    if result_path.exists() or report_path.exists():
        parser.error('Choose a new output prefix to preserve an existing recorded run')
    requests = []
    original_post = poc.post

    def measured_post(url, body, supplied_key, attempts=3):
        start = time.perf_counter()
        response, elapsed_ms = original_post(url, body, supplied_key, attempts)
        usage = response.get('usage', {})
        record = {'endpoint': url, 'requested_model': body.get('model'),
            'returned_model': response.get('model'), 'seconds': time.perf_counter()-start,
            'cost_usd': usage.get('cost'),
            'input_tokens': usage.get('prompt_tokens', usage.get('input_tokens')),
            'output_tokens': usage.get('completion_tokens', usage.get('output_tokens'))}
        if '/decisions' in url:
            decisions = {}
            for name, question in body.get('questions', {}).items():
                candidates = list(question.get('criteria', {}))
                answer = response.get('answers', {}).get(name, {})
                probabilities = answer.get('probabilities') or {answer.get('choice'): 1}
                decisions[name] = {'candidate_ids': candidates,
                    'ranked_ids': sorted(candidates, key=lambda item: -probabilities.get(item, 0)),
                    'choice': answer.get('choice'), 'confidence': answer.get('confidence')}
            record['decisions'] = decisions
        requests.append(record)
        return response, elapsed_ms

    for module in [poc, agent, classic, keywords]:
        module.post = measured_post
    data = {'project': 'Jev RAG POC', 'status': 'running',
        'started_at': datetime.now(ZoneInfo('Europe/Berlin')).isoformat(),
        'case_file': relative(case_path), 'case_sha256': sha256(case_path), 'evaluation_scope': case.get('evaluation_scope'), 'document': relative(pdf_path), 'document_sha256': sha256(pdf_path),
        'questions': questions, 'models': {'answer': agent.PROVIDERS['gemini']['model'],
        'embedding': poc.EMBED_MODEL, 'reranker': poc.JEV_MODEL},
        'source_revision': ((subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or None) if (ROOT / '.git').exists() else None),
        'application_source_sha256': {path.name: sha256(path) for path in ROOT.glob('*.py')},
        'benchmark_sha256': sha256(Path(__file__)), 'application': []}

    def save() -> None:
        data['summary'] = summary(data['application'])
        data['total_known_cost_usd'] = sum(item['cost_usd'] for item in requests if item['cost_usd'] is not None)
        result_path.write_text(json.dumps(data, indent=2)+'\n')

    try:
        print('Preparing the repository-local document index...', flush=True)
        start = time.perf_counter()
        fp = app.index_store.fingerprint(pdf_path)
        reused = app.index_store._path(fp)
        existed = Path(reused).exists()
        list(app.index_pdf(str(pdf_path), key))
        index = app.find_index(fp)
        if not index:
            raise RuntimeError('Application did not produce a usable index')
        data['indexing'] = {'seconds': time.perf_counter()-start, 'reused': existed,
            'pages': index['pages'], 'passages': len(index['chunks']),
            'known_cost_usd': sum(item['cost_usd'] for item in requests if item['cost_usd'] is not None),
            'requests': list(requests)}
        save()
        for number, question in enumerate(questions, 1):
            offset = (number-1) % len(modes)
            for mode, runner in modes[offset:]+modes[:offset]:
                first_request = len(requests)
                start = time.perf_counter()
                events = list(runner(question['q'], index, key, provider='gemini'))
                done = next(value for kind, value in reversed(events) if kind == 'done')
                calls = requests[first_request:]
                trace = []
                for kind, event in events:
                    if kind != 'step':
                        continue
                    clean = json.loads(json.dumps(event))
                    for result in clean.get('results', []):
                        result.pop('text', None)
                    trace.append(clean)
                row = {'question_number': number, 'question': question['q'],
                    'expected_page': question['page'], 'mode': mode, 'answer': done['answer'],
                    'source_pages': sorted({source['page'] for source in done['sources']}),
                    'source_ids': list(dict.fromkeys(source['id'] for source in done['sources'])),
                    'seconds': time.perf_counter()-start,
                    'known_cost_usd': sum(call['cost_usd'] for call in calls if call['cost_usd'] is not None),
                    'unknown_cost_requests': sum(call['cost_usd'] is None for call in calls),
                    'application_reported_cost_usd': done['cost'], 'turns': done.get('turns'),
                    'retries': done.get('retries'), 'trace': trace, 'requests': calls}
                if question['page'] is not None:
                    row['expected_page_cited'] = question['page'] in row['source_pages']
                data['application'].append(row)
                save()
                print(json.dumps({'question': number, 'mode': 'Jev RAG — '+mode,
                    'seconds': round(row['seconds'], 2), 'cost_usd': row['known_cost_usd'],
                    'source_pages': row['source_pages'], 'answer': row['answer']}), flush=True)
        data['status'] = 'complete'
        data['finished_at'] = datetime.now(ZoneInfo('Europe/Berlin')).isoformat()
        save()
        write_report(data, report_path, result_path)
        print(json.dumps({'summary': data['summary'], 'total_known_cost_usd': data['total_known_cost_usd']}), flush=True)
        print('Saved '+relative(report_path)+' and '+relative(result_path), flush=True)
    except Exception as error:
        data['status'] = 'failed'
        data['failure'] = str(error).replace(key, '[REDACTED]')[:1000]
        save()
        raise SystemExit(data['failure']) from None


if __name__ == '__main__':
    main()
