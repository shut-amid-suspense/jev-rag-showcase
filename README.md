# Jev RAG POC

A PDF question-answering proof of concept with three search modes: **Fast**, **Standard** and **Thorough**. These are choices in this application's Search control. Answers show the passages and pages they use.

- [How the application works and how to use it](HOW_IT_WORKS.md)
- [Benchmark runner, included test data and coverage inventory](benchmarks/README.md)
- [Live comparison of all three Jev RAG modes — 26 October 2026](docs/comparisons/2026-10-26-jev-rag-modes.md)
- [All measured requests, answers, timings and costs](docs/comparisons/2026-10-26-jev-rag-modes.json)

## Accuracy diagnostic: multi-section troubleshooting

The six troubleshooting cases have 24 source-grounded required facts, frozen before the run. The reviewing assistant checked each answer against those criteria and source evidence. This is a diagnostic completeness review, not an independent or population-wide accuracy estimate.

| Jev RAG mode | Actual Jev calls | Required-fact completeness points |
|---|---:|---:|
| Fast | 0 | 4/24 |
| Standard | 6 | 23/24 |
| Thorough | 17 | 23.5/24 |

Fast declined five multi-part tasks. Standard and Thorough recovered the required procedures more fully. Standard's project-sharing answer omitted the final Collect and Save confirmation. Both enhanced modes received partial credit on one conservative rubric item that demanded an extra Freeze/Flatten contrast not explicitly requested in its question; the scorecard flags that limitation.

On identical Standard candidate pools, Jev increased canonical evidence chunks in the selected five passages from 11/23 to 18/23. This isolates a ranking contribution, not the effect on generated-answer quality: query expansion and other workflow differences also affect answers, and equivalent evidence can exist outside the canonical chunks.

- [Accuracy review, limitations and Jev attribution](docs/comparisons/2026-10-26-accuracy-review.md)
- [All 18 troubleshooting answers and decision traces](docs/comparisons/2026-10-26-jev-troubleshooting.json)
- [Per-criterion scorecard](docs/comparisons/2026-10-26-accuracy-review.json)
- [Where Jev appears in each pipeline](docs/jev-pipeline.md)

## Operational smoke test: time and cost


**Accuracy scope:** the ten-question run below is an operational smoke test. Its simple lookups, unrelated absence controls and expected-page counts do not establish realistic answer accuracy. The separate [troubleshooting criteria](benchmarks/cases/troubleshooting-live11.json) and [review protocol](benchmarks/accuracy-protocol.md) define the separate source-grounded accuracy diagnostic reported above.

[Where Jev is used, with verified API-call counts](docs/jev-pipeline.md)

All three modes answered the same ten questions using the same 867-page manual and Gemini answer model. Mode order rotated between questions. These whole-answer measurements include retrieval and answer generation; initial indexing is separate.

| Jev RAG mode | Median response time | Mean API cost per question | Extrapolated API cost per 1,000 questions |
|---|---:|---:|---:|
| Jev RAG — Fast | 5.79 s | $0.002700 | $2.70 |
| Jev RAG — Standard | 14.55 s | $0.004156 | $4.16 |
| Jev RAG — Thorough | 20.75 s | $0.005658 | $5.66 |

Fast made one hybrid search. Standard generated search terms and used Jev to rank the combined candidates. Thorough let an agent search repeatedly with Jev and read pages before answering. The report includes every answer, its citations and model-request costs.

This small run does not establish a general answer-quality winner. Expected-page matching is not answer accuracy because the manual repeats instructions. Standard and Thorough change the workflow as well as using Jev, so their additional cost and time cannot be attributed entirely to the ranking step.

## Run a complete example from this repository

The benchmark includes a synthetic handbook and its questions. It generates the PDF locally and imports this repository's application functions. It does not require another checkout or the copyrighted manual. See [benchmark instructions](benchmarks/README.md) for environment setup.

Validate the portable example without calling a model:

```bash
.venv/bin/python benchmarks/compare_search_modes.py --check
```

With `OPENROUTER_API_KEY` supplied in the environment, compare all three modes:

```bash
.venv/bin/python benchmarks/compare_search_modes.py
```

Sesame can optionally supply the key:

```bash
sesame run OPENROUTER_API_KEY -- .venv/bin/python benchmarks/compare_search_modes.py
```

The recorded manual case and its frozen questions are also included, but its copyrighted PDF is excluded from Git. The default synthetic example is the portable case. Other retrieval research scripts are listed separately in the [coverage inventory](benchmarks/README.md#coverage-inventory); the three-mode report does not claim to rerun every historical research matrix.
