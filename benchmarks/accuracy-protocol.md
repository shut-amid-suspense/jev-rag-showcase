# Source-grounded accuracy diagnostic protocol

This protocol is fixed before the live troubleshooting run. It evaluates six practical, multi-constraint manual-support tasks with four required facts each: 24 criteria for each Jev RAG mode.

## Answer review

Each criterion receives one of three explicit labels:

- **Covered (1):** the answer correctly supplies every material part of the required fact.
- **Partial (0.5):** it supplies a correct useful part but omits a material condition, distinction or action.
- **Missing (0):** the required fact is absent or materially contradicted.

The report presents required-fact coverage as points out of 24 and fully covered criteria out of 24. This is a diagnostic rubric score, not a population-wide accuracy estimate. Material unsupported or incorrect additional claims are listed separately. A strict task pass requires all four criteria covered, no material factual error, and supporting citations. An incorrect extra claim prevents a strict pass even when the requested facts were otherwise included.

The reviewing assistant checks the recorded final answers against the frozen criteria and the document evidence. This is an assistant review, not an independent or blinded human assessment. All labels and explanations are saved so a reader can challenge them. Alternative passages containing equivalent support are accepted; a different page is not automatically wrong.

## Jev attribution

Fast is the same application's baseline and makes no Jev call. Standard uses Jev to rank its candidate pool. Thorough uses Jev for each agent search. The request log records actual decision API calls, candidate IDs, selected choices and ranking order.

For each Standard answer, compare the first five candidates supplied to Jev with the five candidates selected after its ranking on the same request. Report canonical evidence-chunk coverage for these fixed lists. This isolates a ranking change within a fixed candidate pool; it does not isolate Jev's effect on generated-answer quality, and canonical chunks are not the only valid evidence in a repetitive manual.

The earlier ten-question run is an operational timing/cost smoke test. Its page-hit counts do not establish answer accuracy, and it must not be presented as a meaningful hard-task accuracy benchmark.
