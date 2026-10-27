# Retrieval experiments

These studies compare passage selection and document chunking. The three application workflows and their complete-answer diagnostic are documented in [the benchmark guide](../benchmarks/README.md).

Run experiments as modules from the repository root, after installing `requirements.txt` and supplying `OPENROUTER_API_KEY` in the environment. Live runs incur provider charges. Importing the modules performs no provider requests.

| Experiment | Command | Saved result |
|---|---|---|
| Synthetic near-duplicate passages | `python -m experiments.poc` | [results.json](results/results.json) |
| SQuAD paragraph retrieval | `python -m experiments.squad_eval` | [squad-results.json](results/squad-results.json) |
| Ableton retrieval and table-of-contents navigation | `python -m experiments.ableton_eval run` | [ableton-results.json](results/ableton-results.json) |
| Section/page chunking alternatives | `python -m experiments.section_eval` | [section-results.json](results/section-results.json) |
| Jev, Clef and Clef-flash decisions | `python -m experiments.clef_eval` | [clef-results.json](results/clef-results.json) |

The commands overwrite their fixed result paths. The committed result files are historical observations, not new runs of the reorganized code. Corpus preparation and model calls are unnecessary for viewing those records.

## Inputs and preparation

The synthetic POC and Clef studies generate their own inputs. `python -m experiments.poc --probe` makes a small endpoint check; `python -m experiments.squad_eval --probe` also indexes its corpus if needed.

The SQuAD study expects `data/squad-dev-v2.0.json`. It labels unanswerable items using the original question/paragraph pair; it does not prove that an answer is absent from every other paragraph in its shared retrieval corpus.

The Ableton studies expect the matching 867-page manual at `data/live11-manual-en.pdf` and Poppler's `pdftotext` and `pdftohtml` commands. Run `python -m experiments.ableton_eval ingest` to create `data/chunks.json`. The historical [questions](fixtures/ableton-questions.json) belong to that extraction/chunking scheme. `python -m experiments.ableton_eval questions` regenerates and overwrites those questions using a paid model; preserve the committed fixture before doing that. Embedding caches stay in the ignored `data/` directory.

The application and the portable benchmark do not require these corpora or Poppler. The copyrighted manual and SQuAD dataset are not included.

## Interpreting the records

These scripts report passage IDs, page hits, decision latency and selected cost fields. Their metrics do not establish complete-answer accuracy. Some cost fields exclude embeddings or indexing; some latency fields exclude local similarity search. They should not be compared directly with the whole-answer costs in [the six-task diagnostic](../docs/comparisons/2026-10-26-accuracy-review.md).

Shared retrieval algorithms are implemented in [jev_rag/retrieval.py](../jev_rag/retrieval.py), and provider requests in [jev_rag/api.py](../jev_rag/api.py). The application does not import this experiment package. Original executed source files for the six-task diagnostic remain frozen in [benchmarks/recorded-source/](../benchmarks/recorded-source/manifest.json).
