# Verification

Application checks were completed on 26 October 2026. Documentation and diagram checks were completed on 27 October 2026.

## Setup and functional checks

- Installed the two pinned direct dependencies into a fresh environment with Python 3.15.1 on macOS. The resolved 52-package set is recorded in `requirements-tested.txt`. The historical live benchmark used the original environment; it was not rerun during these checks.
- All **19 offline regression tests passed**. They cover session-only key state, status redaction, environment-only CLI credentials, JSON cache round trips and corruption handling, invalid fingerprint rejection, embedding compatibility, non-finite/oversized numeric vectors, owner-only cache-file permissions, retention boundaries, and actual PDF indexing/reloading through all three application pipelines with a fake provider.
- The fake-provider tests validate wiring and storage behavior; they are not model-accuracy measurements.
- The portable benchmark's `--check` passed with the committed handbook and its ten questions, without provider requests.
- The Gradio app started successfully from the fresh environment on loopback. Its initial browser screen displayed the updated session-only key instructions and Use keys control. No real key was entered during that browser check.
- The launcher syntax check passed. It no longer stops other processes.

## Recorded evidence

`scripts/verify_evidence.py` verifies the recorded source hashes, complete request-cost records, accuracy-review hash and frozen review protocol using only files included in this repository. The two original executed source snapshots are under `benchmarks/recorded-source/`.

The recorded measurements refer to those historical source versions. The current application differs in credential lifetime, cache serialization, setup and documentation. The retrieval and answering modules `agent.py`, `classic.py` and `keywords.py` match the recorded implementation. The offline checks above validate application behavior; they do not refresh the historical model measurements.

## Contents and scope

The source archive contains source, tests, a synthetic demo PDF, frozen benchmark cases, recorded measurements and source snapshots. It excludes API keys, environment files, virtual environments, uploads, generated indexes, logs and the copyrighted Ableton manual. The source ZIP excludes Git metadata.

The repository and the source ZIP are checked separately. The ZIP can be extracted, its evidence verified, and its portable fixture checked without the original checkout or Git history.

This remains a local research proof of concept. The six-task completeness review is assistant-scored and has explicit rubric limitations; it is not a representative independent accuracy evaluation or a production-service claim.

## Architecture documentation

The architecture overview is generated from `scripts/render_architecture.py`; the PNG and SVG are committed together. Diagram labels and limits were checked against the retrieval, agent and indexing code. The SVG was parsed as XML, repeated rendering produced identical files, and the three Mermaid diagrams in `ARCHITECTURE.md` passed syntax parsing. The PNG was visually inspected for label clipping and arrow placement.
