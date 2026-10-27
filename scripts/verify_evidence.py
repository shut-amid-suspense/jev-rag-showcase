"""Check historical source hashes and recalculate the published diagnostic metrics.

This checks artifact consistency, not semantic answer correctness or provider bills.
It does not require the copyrighted manual, provider access or Git history.
"""
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
MODES = ('Fast', 'Standard', 'Thorough')
LABEL_POINTS = {'covered': 1, 'partial': 0.5, 'missing': 0}
RESULT = '2026-10-26-jev-troubleshooting.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def equal(actual, expected, message):
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        require(type(actual) in (int, float) and math.isfinite(actual)
                and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12), message)
    else:
        require(actual == expected, message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def known_cost(requests):
    for request in requests:
        cost = request.get('cost_usd')
        require(cost is None or (type(cost) in (int, float) and math.isfinite(cost) and cost >= 0),
                'Invalid request cost')
    return sum(item['cost_usd'] for item in requests if item.get('cost_usd') is not None)


def verify_run(result):
    require(result['status'] == 'complete', 'Recorded run is incomplete')
    questions, rows = result['questions'], result['application']
    expected_pairs = {(number, mode) for number in range(1, len(questions) + 1) for mode in MODES}
    pairs = [(row['question_number'], row['mode']) for row in rows]
    require(len(pairs) == len(expected_pairs) and set(pairs) == expected_pairs,
            'Missing or duplicate question/mode result')
    require(set(result['summary']) == set(MODES), 'Summary mode coverage differs')
    for row in rows:
        question = questions[row['question_number'] - 1]
        equal(row['question'], question['q'], 'Recorded question differs')
        equal(row['expected_page'], question['page'], 'Recorded expected page differs')
        require(type(row['seconds']) in (int, float) and math.isfinite(row['seconds'])
                and row['seconds'] >= 0, 'Invalid elapsed time')
        equal(row['known_cost_usd'], known_cost(row['requests']), 'Row request costs do not add up')
        equal(row['unknown_cost_requests'], sum(r.get('cost_usd') is None for r in row['requests']),
              'Unknown-cost count differs')
        require(row['unknown_cost_requests'] == 0, 'Historical run has unknown recorded costs')
        equal(row['application_reported_cost_usd'], row['known_cost_usd'], 'Application/request cost differs')
        if question['page'] is not None:
            equal(row['expected_page_cited'], question['page'] in row['source_pages'], 'Page-hit flag differs')
    for mode in MODES:
        group = [row for row in rows if row['mode'] == mode]
        expected = {
            'queries': len(group),
            'completed_answers': sum(bool(row['answer']) for row in group),
            'median_seconds': statistics.median(row['seconds'] for row in group),
            'slowest_seconds': max(row['seconds'] for row in group),
            'mean_known_cost_usd': statistics.mean(row['known_cost_usd'] for row in group),
            'total_known_cost_usd': sum(row['known_cost_usd'] for row in group),
            'mean_requests': statistics.mean(len(row['requests']) for row in group),
            'unknown_cost_requests': sum(row['unknown_cost_requests'] for row in group),
            'jev_calls': sum('/decisions' in r['endpoint'] for row in group for r in row['requests']),
            'expected_page_cited': sum(row.get('expected_page_cited', False) for row in group),
            'answerable_questions': sum(row['expected_page'] is not None for row in group),
            'empty_answers': sum(not row['answer'] for row in group),
        }
        for key, value in expected.items():
            equal(result['summary'][mode][key], value, f'{mode}: summary {key} differs')
    indexing = result['indexing']
    equal(indexing['known_cost_usd'], known_cost(indexing['requests']), 'Indexing cost differs')
    total = indexing['known_cost_usd'] + sum(row['known_cost_usd'] for row in rows)
    equal(result['total_known_cost_usd'], total, 'Whole-run cost differs')


def verify_review(review, result, case):
    equal(case['questions'], result['questions'], 'Frozen case differs from run')
    questions = case['questions']
    rows = review['reviews']
    pairs = [(row['question_number'], row['mode']) for row in rows]
    expected = {(number, mode) for number in range(1, len(questions) + 1) for mode in MODES}
    require(len(pairs) == len(expected) and set(pairs) == expected, 'Review coverage differs')
    for row in rows:
        question = questions[row['question_number'] - 1]
        equal(row['question_id'], question['id'], 'Review task ID differs')
        criteria = {item['id']: item for item in question['criteria']}
        require(len(row['grades']) == len(criteria) and
                {g['criterion_id'] for g in row['grades']} == set(criteria), 'Criterion coverage differs')
        for grade in row['grades']:
            criterion = criteria[grade['criterion_id']]
            require(grade['status'] in LABEL_POINTS, 'Unknown criterion label')
            equal(grade['points'], LABEL_POINTS[grade['status']], 'Criterion label/points differ')
            equal(grade['required_fact'], criterion['required_fact'], 'Required fact differs')
            equal(grade['canonical_support_chunk_ids'], criterion['support_chunk_ids'], 'Support IDs differ')
        equal(row['points'], sum(g['points'] for g in row['grades']), 'Task points differ')
        equal(row['maximum_points'], len(criteria), 'Task maximum differs')
        complete = all(g['status'] == 'covered' for g in row['grades']) and not row['material_factual_errors_confirmed']
        equal(row['strict_pass'], complete, 'Strict-pass flag differs')
        answer = next(r for r in result['application']
                      if r['question_number'] == row['question_number'] and r['mode'] == row['mode'])
        require(not row['strict_pass'] or bool(answer['source_ids']), 'Strict pass has no citations')
    for mode in MODES:
        group = [row for row in rows if row['mode'] == mode]
        grades = [grade for row in group for grade in row['grades']]
        values = {
            'criteria_points': sum(g['points'] for g in grades),
            'maximum_points': len(grades),
            'fully_covered_criteria': sum(g['status'] == 'covered' for g in grades),
            'partial_criteria': sum(g['status'] == 'partial' for g in grades),
            'missing_criteria': sum(g['status'] == 'missing' for g in grades),
            'strict_complete_tasks': sum(row['strict_pass'] for row in group),
            'tasks': len(group),
            'confirmed_material_factual_errors': sum(len(row['material_factual_errors_confirmed']) for row in group),
        }
        for key, value in values.items():
            equal(review['summary'][mode][key], value, f'{mode}: review {key} differs')
    rankings = review['fixed_pool_jev_ranking']
    require(len(rankings) == len(questions) and {r['question_id'] for r in rankings} ==
            {q['id'] for q in questions}, 'Ranking task coverage differs')
    for ranking in rankings:
        number, question = next((n, q) for n, q in enumerate(questions, 1) if q['id'] == ranking['question_id'])
        row = next(r for r in result['application'] if r['question_number'] == number and r['mode'] == 'Standard')
        calls = [r for r in row['requests'] if '/decisions' in r['endpoint']]
        require(len(calls) == 1, 'Expected one Standard decision request')
        decision = calls[0]['decisions']['pick']
        equal(ranking['before_first_five_ids'], decision['candidate_ids'][:5], 'Before-Jev IDs differ')
        equal(ranking['jev_selected_five_ids'], decision['ranked_ids'][:5], 'After-Jev IDs differ')
        canonical = {i for criterion in question['criteria'] for i in criterion['support_chunk_ids']}
        require(len(ranking['canonical_evidence_ids']) == len(canonical) and
                set(ranking['canonical_evidence_ids']) == canonical, 'Canonical evidence differs')
        equal(ranking['canonical_chunks_before'], len(canonical & set(ranking['before_first_five_ids'])), 'Before coverage differs')
        equal(ranking['canonical_chunks_after'], len(canonical & set(ranking['jev_selected_five_ids'])), 'After coverage differs')
        equal(ranking['canonical_chunks_total'], len(canonical), 'Canonical total differs')


def main():
    manifest = json.loads((ROOT / 'benchmarks/recorded-source/manifest.json').read_text())
    for entry in manifest['snapshots']:
        for name, expected in entry['files'].items():
            equal(digest(ROOT / entry['directory'] / name), expected, f'Snapshot hash differs: {name}')
    result = json.loads((ROOT / 'docs/comparisons' / RESULT).read_text())
    snapshot = next(item for item in manifest['snapshots'] if item['original_revision'] == result['source_revision'])
    folder = ROOT / snapshot['directory']
    equal(digest(folder / 'benchmarks/compare_search_modes.py'), result['benchmark_sha256'], 'Executed runner hash differs')
    for filename, expected in result['application_source_sha256'].items():
        equal(digest(folder / filename), expected, f'Executed source hash differs: {filename}')
    equal(digest(folder / result['case_file']), result['case_sha256'], 'Executed case hash differs')
    verify_run(result)
    review = json.loads((ROOT / 'docs/comparisons/2026-10-26-accuracy-review.json').read_text())
    equal(review['results_file'], RESULT, 'Scorecard references a different run')
    equal(digest(ROOT / 'docs/comparisons' / RESULT), review['results_sha256'], 'Results hash differs')
    equal(digest(ROOT / 'benchmarks/accuracy-protocol.md'), review['protocol_sha256'], 'Protocol hash differs')
    case = json.loads((folder / result['case_file']).read_text())
    verify_review(review, result, case)
    print('Verified source hashes, recorded request costs, timing summaries, rubric arithmetic and fixed-pool Jev coverage.')
    print('Artifact consistency checks do not independently validate answer correctness or unreported provider charges.')


if __name__ == '__main__':
    main()
