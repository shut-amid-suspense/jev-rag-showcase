# Verification

Initial application checks were completed on 26 October 2026. The application, benchmark tooling, documentation and archive were checked again on 27 October 2026.

## Setup and functional checks

- Installed the two pinned direct dependencies into a fresh environment with Python 3.15.1 on macOS. The resolved 52-package set is recorded in `requirements-tested.txt`. The historical live benchmark used the original environment; it was not rerun during these checks.
- All **29 offline regression tests passed** on 27 October. They cover session-only key state, status redaction, environment-only CLI credentials, JSON cache round trips and corruption handling, invalid fingerprint rejection, embedding compatibility, non-finite/oversized numeric vectors, owner-only cache-file permissions, retention boundaries, and actual PDF indexing/reloading through all three application pipelines with a fake provider.
- The fake-provider tests validate wiring and storage behavior; they are not model-accuracy measurements. Additional tests run the benchmark CLI across all three modes, protect existing reports, detect manipulated request costs, timing summaries, criterion scores and ranking lists, verify fixture regeneration, and check that provider error bodies do not reach exceptions or server logs.
- The portable benchmark's `--check` passed with the committed handbook and its ten questions, without provider requests.
- The Gradio app started successfully from the fresh environment on loopback. Its initial browser screen displayed the updated session-only key instructions and Use keys control. No real key was entered during that browser check. A fresh local startup on 27 October also served the page and configuration successfully, with the expected key controls and six-turn agent description; the check then stopped its server.
- The launcher syntax check passed. It starts the app without terminating other processes.

## Recorded evidence

`scripts/verify_evidence.py` checks recorded source hashes, the accuracy-review hash and frozen review protocol using only files included in this repository. It recalculates request-cost totals, timing summaries, mode coverage, rubric arithmetic, strict-task counts and fixed-pool Jev coverage. This verifies artifact consistency, not semantic answer correctness or charges from unreported failed attempts. The original executed source snapshot is under `benchmarks/recorded-source/`.

The recorded measurements refer to those historical source versions. The current application differs in credential lifetime, cache serialization, setup and documentation. The retrieval and answering modules `agent.py`, `classic.py` and `keywords.py` match the recorded implementation. The offline checks above validate application behavior; they do not refresh the historical model measurements.

## Contents and scope

The source archive contains source, tests, a synthetic demo PDF, frozen benchmark cases, recorded measurements and source snapshots. It excludes API keys, environment files, virtual environments, uploads, generated indexes, logs and the copyrighted Ableton manual. The source ZIP excludes Git metadata.

The repository and the source ZIP are checked separately. The ZIP can be extracted, its evidence verified, and its portable fixture checked without the original checkout or Git history.

This remains a local research proof of concept. The six-task completeness review is assistant-scored and has explicit rubric limitations; it is not a representative independent accuracy evaluation or a production-service claim.

## Architecture documentation

The architecture overview is generated from `scripts/render_architecture.py`; the PNG and SVG are committed together. Diagram labels and limits were checked against the retrieval, agent and indexing code. The SVG was parsed as XML, repeated rendering produced identical files, and the three Mermaid diagrams in `ARCHITECTURE.md` passed syntax parsing. The PNG was visually inspected for label clipping and arrow placement.

## Changes after the recorded diagnostic

The superseded operational smoke test and its unused source snapshot were removed from the source archive. The six-task diagnostic's raw results, criterion scorecard, preregistered protocol, executed source files and frozen diagnostic case remain byte-for-byte unchanged. The current synthetic example uses service-support absence questions and is explicitly separate from the historical accuracy diagnostic.

The current UI describes the actual six-turn agent limit. PDF handles close after extraction, provider error bodies are excluded from logged exceptions, generated fixture PDFs are invalidated when their text changes, and benchmark timestamps use the system's timezone without requiring a separate timezone database. These checks did not make paid model requests or refresh the historical measurements.
