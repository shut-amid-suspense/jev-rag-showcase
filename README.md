# Jev RAG POC

A PDF question-answering proof of concept comparing hybrid retrieval, Jev reranking, and agentic search. Answers show the passages and pages they use.

- [How the application works and how to use it](HOW_IT_WORKS.md)
- [Live Fast versus Standard comparison — 26 October 2026](docs/comparisons/2026-10-26-fast-vs-standard.md)
- [Measured requests, answers, timings, and costs](docs/comparisons/2026-10-26-fast-vs-standard.json)

## Latest live comparison

Both modes answered the same ten questions using the same 867-page manual and answer model. These are whole-answer measurements, including retrieval and answer generation, with indexing measured separately.

| Mode | Median response time | Mean API cost per question | Extrapolated API cost per 1,000 questions |
|---|---:|---:|---:|
| Fast: hybrid retrieval | 5.66 s | $0.002512 | $2.51 |
| Standard: query expansion and Jev reranking | 11.45 s | $0.003996 | $4.00 |

Standard sometimes found broader evidence; this small run does not establish a general answer-quality winner. Standard also changes query generation and candidate selection, so its additional cost and time cannot be attributed entirely to Jev. The report separately measures adding Jev to a fixed shortlist.

Initial indexing took 45.05 seconds and cost $0.005609. Costs above are recorded provider charges from this run, not guaranteed current prices. See the full report for sampling, limitations, individual answers, and the distinction between expected-page matching and answer accuracy.
