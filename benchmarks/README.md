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

Supply `OPENROUTER_API_KEY` in the environment using your preferred key manager, then run:

```bash
.venv/bin/python benchmarks/compare_search_modes.py
```

Sesame is optional. On a machine already using it, the equivalent command is:

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

## Coverage inventory

The main benchmark covers every mode in the application's `app.METHODS` search control and fails its coverage check if that control changes.

| Application mode | Implementation in this repository |
|---|---|
| Jev RAG — Fast | `classic.run_classic` in [classic.py](../classic.py) |
| Jev RAG — Standard | `keywords.run_keywords` in [keywords.py](../keywords.py) |
| Jev RAG — Thorough | `agent.run_agent` in [agent.py](../agent.py) |

There are also separate retrieval research scripts in this repository. They are not additional choices in the application's search control, and the three-mode report does not claim to have rerun every historical research matrix.

| Research script | Alternatives it compares |
|---|---|
| [poc.py](../poc.py) | BM25, embeddings, Jev over the whole small corpus, embeddings plus Jev |
| [squad_eval.py](../squad_eval.py) | BM25, embeddings, embeddings plus Jev, embeddings plus a chat-model reranker |
| [ableton_eval.py](../ableton_eval.py) | BM25, embeddings, hybrid, hybrid plus Jev, hybrid plus a chat-model reranker, table-of-contents navigation with Jev |
| [section_eval.py](../section_eval.py) | Page-based, section-and-page, and section-based passage boundaries |
| [clef_eval.py](../clef_eval.py) | Jev, Clef and Clef-flash decision models for intent and passage selection |
