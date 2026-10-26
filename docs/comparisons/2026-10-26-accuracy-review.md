# Jev RAG: source-grounded troubleshooting review

The earlier ten-question run was a time/cost smoke test. This separate diagnostic uses six multi-constraint technical-support scenarios, with four required facts each, frozen before the live run. All three application modes used the same manual, questions and Gemini answer model.

## Where Jev is used

Jev selects and ranks evidence passages. Gemini writes the final answer.

| Jev RAG mode | Jev function in the pipeline | Actual Jev calls in this six-task run |
|---|---|---:|
| Fast | No Jev; hybrid retrieval directly supplies five passages | 0 |
| Standard | Ranks the expanded search pool and supplies five passages | 6 |
| Thorough | Ranks candidates for each agent search and supplies three passages | 17 |

See [the pipeline and source locations](../jev-pipeline.md).

## Required-fact completeness

| Jev RAG mode | Rubric points / 24 | Fully covered criteria | Partially covered | Missing | Strictly complete tasks / 6 |
|---|---:|---:|---:|---:|---:|
| Fast | 4/24 | 4 | 0 | 20 | 1/6 |
| Standard | 23/24 | 22 | 2 | 0 | 4/6 |
| Thorough | 23.5/24 | 23 | 1 | 0 | 5/6 |

**These are rubric completeness scores, not validated population-wide accuracy percentages.** Covered = 1 point, partial = 0.5, missing = 0. A strict pass requires every criterion covered and no material factual error. No material factual error was confirmed in this review; Fast primarily failed through abstention and missing answers.

**Rubric limitation:** C3 requires a Freeze/Flatten contrast that the question did not explicitly ask for. Standard and Thorough correctly recommended Freeze/Unfreeze but received partial credit for that criterion. This is conservative grading of completeness, not a demonstrated incorrect answer; it also makes the strict task counts conservative.

The review was performed by the assistant against the source evidence, without independent or blinded judging. Every criterion label and explanation is available in the scorecard.

## Practical findings

- **Fast:** declined the first five multi-part tasks because its retrieved passages did not cover the full question. It answered the hardware-latency task correctly, where the required facts were concentrated in one passage. These are retrieval/task-completion failures, not five hallucinated answers.
- **Standard:** supplied the main multi-section procedures. Its project-sharing answer opened the file-collection controls but omitted the final Collect and Save confirmation (or the Collect All and Save shortcut). That omission prevents the described procedure from reliably completing the task.
- **Thorough:** supplied the collection confirmation and the other requested procedures. Its additional searches recovered useful evidence, but it took longer and made more paid requests.

## Jev ranking on identical candidate pools

For each Standard request, compare the first five candidates supplied to Jev with the five candidates selected by Jev. The pool and query expansion are held fixed for this comparison.

| Task | Canonical evidence chunks before Jev | After Jev | Canonical chunks for task |
|---|---:|---:|---:|
| automation-overdub-recovery | 3 | 3 | 3 |
| external-hardware-export | 2 | 4 | 4 |
| warp-quality-cpu-and-tails | 1 | 4 | 6 |
| low-latency-monitor-and-resample | 2 | 3 | 3 |
| portable-editable-project | 2 | 3 | 6 |
| hardware-latency-unknown-value | 1 | 1 | 1 |
| **Total** | **11** | **18** | **23** |

Jev increased canonical evidence-chunk coverage from 11/23 to 18/23 in these fixed pools. Four tasks improved, two were unchanged, and none decreased on this metric. This measures a ranking contribution; it is not answer accuracy and canonical chunks are not the only valid evidence. In particular, it does not prove that all of Standard's answer-quality improvement over Fast came from Jev; query expansion also changes retrieval.

## Time and cost on these harder tasks

| Jev RAG mode | Median whole-answer time | Mean API cost per task | Extrapolated per 1,000 tasks |
|---|---:|---:|---:|
| Fast | 16.20 s | $0.007569 | $7.57 |
| Standard | 18.18 s | $0.007001 | $7.00 |
| Thorough | 27.76 s | $0.011760 | $11.76 |

These are a single small live batch, not guarantees or results on the earlier simple questions. Charges cover all successful query, ranking and answer-generation requests; the saved manual index was reused. More requests do not necessarily mean higher total cost because tokens and model pricing differ.

## Inspect or reproduce

- [Frozen scenarios and source-grounded criteria](../../benchmarks/cases/troubleshooting-live11.json)
- [Scoring protocol committed before the run](../../benchmarks/accuracy-protocol.md)
- [All 18 recorded answers, calls, rankings, timings and costs](2026-10-26-jev-troubleshooting.json)
- [Per-criterion review and ranking scorecard](2026-10-26-accuracy-review.json)
- [All generated answers in readable form](2026-10-26-jev-troubleshooting.md)

From the repository root, with the manual at the case's repository-local path:

```bash
sesame run OPENROUTER_API_KEY -- .venv/bin/python benchmarks/compare_search_modes.py --case benchmarks/cases/troubleshooting-live11.json --output-prefix docs/comparisons/troubleshooting-repeat
```

The manual is copyrighted and excluded from Git. The repository also includes a complete synthetic handbook for portable operational checks; it is a demo fixture and is not evidence of hard-task accuracy. This diagnostic does not cover screenshots, broad enterprise workloads, repeated runs or production deployment.
