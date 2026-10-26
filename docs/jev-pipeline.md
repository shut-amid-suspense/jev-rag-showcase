# Where Jev is used

Jev is a decision model used for passage selection and ranking. It does not generate the prose answer and it is not the embedding model.

| Jev RAG application mode | Retrieval and decision path | Final answer model in the recorded runs |
|---|---|---|
| Fast | User question -> hybrid keyword/embedding retrieval -> top five passages; no Jev call | Gemini |
| Standard | Gemini generates search terms -> hybrid searches build up to 40 candidates -> Jev ranks candidates -> best five passages | Gemini |
| Thorough | Gemini agent requests a search -> hybrid search shortlists 20 candidates -> Jev ranks them -> best three returned to the agent; the agent can repeat searches or read pages | Gemini |

## Decision API and source locations

- [poc.py](../poc.py) defines `JEV_MODEL` and the `/api/alpha/decisions` endpoint.
- [keywords.py](../keywords.py) builds the Standard candidate pool and calls Jev before `answer_from`.
- [agent.py](../agent.py) calls Jev inside `search`, then returns ranked passages to the agent.
- [classic.py](../classic.py) implements the Fast baseline without Jev.

The Jev request contains candidate passage IDs and text plus the question. Its selected choice and probabilities determine the ranking. The confidence/probability is a model output, not a measured correctness guarantee.

## What the original POC asks

Can Jev select the correct evidence more accurately, faster or more cheaply than conventional retrieval or a general chat-model reranker? The original retrieval experiments and saved results address passage selection. A whole-answer comparison between application modes also changes query expansion, search steps and context, so it cannot by itself isolate Jev's effect on answer quality.

## Observed calls in the ten-question operational smoke test

The actual recorded requests in [the three-mode smoke test](comparisons/2026-10-26-jev-rag-modes.json) contain:

| Mode | Jev calls |
|---|---:|
| Fast | 0 |
| Standard | 10 |
| Thorough | 19 |

This run established operation, time and cost. Its simple lookups, unrelated absence controls and page-hit counts do not establish realistic answer accuracy. The [troubleshooting criteria](../benchmarks/cases/troubleshooting-live11.json) and [review protocol](../benchmarks/accuracy-protocol.md) define a separate source-grounded diagnostic.

## Source-grounded troubleshooting diagnostic

The subsequent six-task run recorded 0 Jev calls in Fast, 6 in Standard, and 17 in Thorough. [The accuracy review](comparisons/2026-10-26-accuracy-review.md) separates final-answer completeness from the ranking contribution: in Standard's identical candidate pools, canonical evidence in the chosen five passages increased from 11/23 before Jev to 18/23 after Jev. This is a passage-ranking result on a small diagnostic, not a general answer-accuracy claim.
