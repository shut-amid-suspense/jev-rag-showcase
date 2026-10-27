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

## Measurement scope

Each mode uses the same indexed PDF and answer model. The order rotates between questions. The JSON records successful model requests, provider-reported costs, citations, model turns, source hashes and elapsed times. The Markdown report contains every answer and explains the limitations of expected-page matching. Generated PDFs and indexes stay under the Git-ignored `data/benchmark-cache/` directory. Generated PDFs are refreshed when their source text changes.

Recorded request costs cover successful responses; failed or retried requests can incur additional unreported charges. They are not a billing ledger. Indexing costs are reported separately from per-answer costs.

## Coverage inventory

The main benchmark covers every mode in the application's `jev_rag.ui.METHODS` search control and fails its coverage check if that control changes.

| Application mode | Implementation in this repository |
|---|---|
| Jev RAG — Fast | `jev_rag.classic.run_classic` in [classic.py](../jev_rag/classic.py) |
| Jev RAG — Standard | `jev_rag.keywords.run_keywords` in [keywords.py](../jev_rag/keywords.py) |
| Jev RAG — Thorough | `jev_rag.agent.run_agent` in [agent.py](../jev_rag/agent.py) |

There are also separate retrieval research scripts in this repository. They are not additional choices in the application's search control, and the three-mode report does not claim to have rerun every historical research matrix.

| Research script | Alternatives it compares |
|---|---|
| [poc.py](../experiments/poc.py) | BM25, embeddings, Jev over the whole small corpus, embeddings plus Jev |
| [squad_eval.py](../experiments/squad_eval.py) | BM25, embeddings, embeddings plus Jev, embeddings plus a chat-model reranker |
| [ableton_eval.py](../experiments/ableton_eval.py) | BM25, embeddings, hybrid, hybrid plus Jev, hybrid plus a chat-model reranker, table-of-contents navigation with Jev |
| [section_eval.py](../experiments/section_eval.py) | Page-based, section-and-page, and section-based passage boundaries |
| [clef_eval.py](../experiments/clef_eval.py) | Jev, Clef and Clef-flash decision models for intent and passage selection |

## Historical research limitations

The older research scripts and saved JSON files measure passage selection, not complete answers. They were not rerun during the current application checks. Their cost fields are not directly comparable with the complete three-mode pipeline: some omit query embeddings or initial indexing, and some latency fields exclude local similarity search. See each script for its exact accounting.

The SQuAD experiment treats `is_impossible` as an abstention label. That label belongs to a question's associated paragraph; the script does not establish that every other paragraph in its shared corpus lacks an answer. Its unanswerable-item scores therefore have an additional limitation.

`experiments/ableton_eval.py` and `experiments/section_eval.py` require the matching manual and Poppler's `pdftotext` and `pdftohtml` commands. `python -m experiments.ableton_eval ingest` creates `data/chunks.json`; the committed `experiments/fixtures/ableton-questions.json` belongs to that historical chunking scheme. The SQuAD experiment requires `data/squad-dev-v2.0.json`. These external corpora and tools are unnecessary for the application or portable benchmark. Older research commands write into `experiments/results/` and overwrite fixed result filenames; preserve saved results before rerunning them. [Experiment commands and saved outputs](../experiments/README.md) are documented separately.

## Source-grounded troubleshooting accuracy diagnostic

The portable handbook is an operational example. It does not simulate hard document-support work or establish answer accuracy.

The six cases in [troubleshooting-live11.json](cases/troubleshooting-live11.json) instead require multi-section procedures, constraint handling, recovery steps and calibrated handling of an unknown hardware value. Their criteria and source locations were committed before the live run. [accuracy-protocol.md](accuracy-protocol.md) defines the review labels and Jev attribution method. The assistant's review is transparent but is not independent or blinded.

```bash
sesame run OPENROUTER_API_KEY -- .venv/bin/python benchmarks/compare_search_modes.py --case benchmarks/cases/troubleshooting-live11.json --output-prefix docs/comparisons/troubleshooting-repeat
```

The runner records Jev input candidate IDs, its ranking and choice, final citation IDs, time and request costs. A source-grounded review of the final answers is still required; matching the expected page does not automatically grade an answer. The recorded [accuracy review](../docs/comparisons/2026-10-26-accuracy-review.md) includes all criterion labels, methodological caveats, actual Jev-call counts and a before/after comparison on fixed Standard candidate pools.
