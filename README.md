# Jev RAG — an evaluated document assistant

Ask practical questions about a long PDF and inspect the passages behind each answer. This proof of concept explores whether a decision model, **Jev**, can improve the selection of evidence for a generative answer model.

The application compares three complete retrieval workflows. It also records Jev's ranking on fixed candidate pools, so its contribution can be inspected separately from query expansion.

| Search mode | What happens | Jev's role |
|---|---|---|
| **Fast** | One hybrid keyword/embedding search, then an answer from five passages | Baseline without Jev |
| **Standard** | Generate focused queries, combine their results, then answer from five selected passages | Ranks up to 40 candidates |
| **Thorough** | An agent can search again or read a page before answering | Ranks the candidates for each search |

Gemini writes the final answers in the recorded comparisons. Jev selects evidence; it does not generate the answer prose. An optional Cerebras/Qwen route is also implemented but was not part of those comparisons.

## Start the app

Requires Python 3.11+ and an OpenRouter API key. From this repository's root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Open the local URL printed by Gradio. Enter your own OpenRouter key, upload [the included demo PDF](examples/support-handbook.pdf), wait until it is ready, and try the same question with each search mode. On Windows, use `.venv\Scripts\python` in place of `.venv/bin/python`.

API keys are held in memory for the active app session. Re-enter them after a page reload; **Remove keys** clears the active state. They are not persisted in browser storage or written into the index. Uploaded PDFs are processed by OpenRouter and the configured model providers. Use the synthetic demo or documents you are comfortable sending to those providers.

The demo handbook is fictional and intended to demonstrate operation. It is not the accuracy test corpus.

## Where to review the work

1. [Pipeline and exact source locations](docs/jev-pipeline.md) — where Jev enters each workflow.
2. [Source-grounded troubleshooting review](docs/comparisons/2026-10-26-accuracy-review.md) — six multi-part tasks, frozen criteria, omissions, limitations and ranking evidence.
3. [Recorded answers and Jev decision traces](docs/comparisons/2026-10-26-jev-troubleshooting.json) — request-level models, costs, candidate IDs and rankings.
4. [Benchmark instructions and coverage inventory](benchmarks/README.md) — reproduce all three modes using only this repository.

## What was measured

The six-task technical-support diagnostic uses an 867-page manual and 24 required facts committed before the run. The reviewer checked completeness against source evidence.

| Mode | Required-fact points / 24 | Median whole-answer time | Mean API cost per task |
|---|---:|---:|---:|
| Fast | 4 | 16.20 s | $0.007569 |
| Standard | 23 | 18.18 s | $0.007001 |
| Thorough | 23.5 | 27.76 s | $0.011760 |

Fast declined five multi-part tasks when its retrieved context was incomplete. Standard omitted a final file-collection confirmation in one procedure. Thorough included it. One conservative rubric item demanded an additional distinction not explicit in its question; the scorecard flags that limitation.

These are **assistant-reviewed completeness points on six diagnostic cases**, not a general accuracy percentage or independent evaluation. The full-mode comparison changes query expansion, search steps and context, so improvements cannot all be attributed to Jev.

On identical Standard candidate pools, Jev increased canonical evidence chunks in the selected five passages from **11/23 to 18/23**. This is a passage-ranking contribution; equivalent evidence may exist outside the canonical chunks. The [review](docs/comparisons/2026-10-26-accuracy-review.md) includes the per-task comparisons and every grading explanation.

A separate [ten-question operational smoke test](docs/comparisons/2026-10-26-jev-rag-modes.md) records time and cost on simpler questions. It is not an accuracy claim. Historical retrieval experiments remain in the repository and are listed separately in the coverage inventory.

## Reproduce and check

Offline checks need no API key:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_evidence.py
.venv/bin/python benchmarks/compare_search_modes.py --check
```

With `OPENROUTER_API_KEY` supplied in your environment, run the portable three-mode comparison:

```bash
.venv/bin/python benchmarks/compare_search_modes.py
```

The benchmark builds a PDF from its committed synthetic handbook and stores reports inside this repository. Live requests incur API charges. Sesame is an optional way to supply the environment variable; it is not required.

The recorded manual cases and frozen questions are included, but the copyrighted Ableton PDF is not. Place the matching manual under the case's repository-local path to rerun those cases. Its fingerprint and original executed source hashes are recorded. Small [frozen source snapshots](benchmarks/recorded-source/manifest.json) keep historical evidence verifiable even from the ZIP, without another repository or the original Git history.

## Scope of this sharing version

This is a local, single-user research application. It supports text-based PDFs and optional question screenshots; it does not OCR scanned PDFs. The recorded diagnostic did not evaluate screenshots, production workloads, access control or concurrent users.

This sharing version improves setup, removes browser-persisted API keys, uses validated data-only JSON caches, and avoids stopping other running processes. Retrieval and answering algorithms are unchanged. Historical measurements refer to their original source versions, which remain included for inspection; packaging checks are described in [VERIFICATION.md](VERIFICATION.md).

See [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for usage and [PRIVACY.md](PRIVACY.md) for the data flow.
