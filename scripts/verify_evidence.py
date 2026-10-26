"""Verify recorded measurements against source snapshots included in this repo."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'benchmarks/recorded-source/manifest.json').read_text())
    for entry in manifest['snapshots']:
        folder = ROOT / entry['directory']
        for name, expected in entry['files'].items():
            assert digest(folder / name) == expected, name
    for name in ['2026-10-26-jev-rag-modes.json', '2026-10-26-jev-troubleshooting.json']:
        result = json.loads((ROOT / 'docs/comparisons' / name).read_text())
        snapshot = next(item for item in manifest['snapshots']
                        if item['original_revision'] == result['source_revision'])
        folder = ROOT / snapshot['directory']
        assert digest(folder / 'benchmarks/compare_search_modes.py') == result['benchmark_sha256']
        for filename, expected in result['application_source_sha256'].items():
            assert digest(folder / filename) == expected, filename
        if result.get('case_sha256'):
            assert digest(folder / result['case_file']) == result['case_sha256']
        for mode in ['Fast', 'Standard', 'Thorough']:
            rows = [row for row in result['application'] if row['mode'] == mode]
            assert len(rows) == len(result['questions'])
            assert all(row['unknown_cost_requests'] == 0 for row in rows)
        print('Verified recorded source and complete request costs:', name)
    review = json.loads((ROOT / 'docs/comparisons/2026-10-26-accuracy-review.json').read_text())
    assert digest(ROOT / 'docs/comparisons' / review['results_file']) == review['results_sha256']
    assert digest(ROOT / 'benchmarks/accuracy-protocol.md') == review['protocol_sha256']
    for mode, expected in review['summary'].items():
        rows = [row for row in review['reviews'] if row['mode'] == mode]
        assert sum(row['points'] for row in rows) == expected['criteria_points']
    print('Verified the review scorecard and preregistered protocol.')


if __name__ == '__main__':
    main()
