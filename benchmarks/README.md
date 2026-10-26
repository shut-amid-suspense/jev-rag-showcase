# Benchmark the three Jev RAG search modes

This runner measures **Jev RAG — Fast**, **Jev RAG — Standard** and **Jev RAG — Thorough**, using the exact functions selected by the application's search control. It reads only code and inputs inside this repository. It receives its API key from the environment and does not read another project's configuration.

## Portable example included in this repository

The synthetic support handbook and its ten questions are committed under `fixtures/` and `cases/`. The runner builds a text-based PDF locally using the application's existing PyMuPDF dependency. This example requires no private document, external checkout or downloaded manual.

From the repository root, prepare the existing application environment if necessary:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Validate the local fixture, question pages and coverage of all three application modes without making model requests:

```bash
.venv/bin/python benchmarks/compare_search_modes.py --check
```

Run the live comparison with the OpenRouter key provided by Sesame:

```bash
sesame run OPENROUTER_API_KEY -- .venv/bin/python benchmarks/compare_search_modes.py
```

The default result files are `docs/comparisons/jev-rag-modes.md` and `.json`. Live runs incur API charges. The runner refuses to overwrite an existing recorded run; choose a new `--output-prefix` to run again.

## Existing manual case

`cases/live11.json` freezes the exact ten questions used in the recorded manual comparison. It expects the PDF at `data/live11-manual-en.pdf` within this repository. That copyrighted PDF is not committed. Use the complete synthetic example above when the manual is unavailable.

```bash
sesame run OPENROUTER_API_KEY -- .venv/bin/python benchmarks/compare_search_modes.py --case benchmarks/cases/live11.json --output-prefix docs/comparisons/manual-repeat
```

Each mode uses the same indexed PDF and answer model. The order rotates between questions. The JSON records the actual model requests, provider-reported costs, citations, model turns, source hashes and elapsed times. The Markdown report contains every answer and explains the limitations of expected-page matching. Generated PDFs and indexes stay under the Git-ignored `data/benchmark-cache/` directory.
