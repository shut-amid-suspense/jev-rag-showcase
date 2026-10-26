# Sharing-copy verification

Checked on 26 October 2026. The working project was not changed; this is a separate sharing copy.

## Setup and functional checks

- Installed the two pinned direct dependencies into a fresh environment with Python 3.15.1 on macOS. The resolved 52-package set is recorded in `requirements-tested.txt`. The historical live benchmark used the original environment; it was not rerun as part of packaging.
- All **19 offline regression tests passed**. They cover session-only key state, status redaction, environment-only CLI credentials, JSON cache round trips and corruption handling, invalid fingerprint rejection, embedding compatibility, non-finite/oversized numeric vectors, owner-only cache-file permissions, retention boundaries, and actual PDF indexing/reloading through all three application pipelines with a fake provider.
- The fake-provider tests validate wiring and storage behavior; they are not model-accuracy measurements.
- The portable benchmark's `--check` passed with the committed handbook and its ten questions, without provider requests.
- The cleaned Gradio app started successfully from the fresh environment on loopback. Its initial browser screen displayed the updated session-only key instructions and Use keys control. No real key was entered during that browser check.
- The launcher syntax check passed. It no longer stops other processes.

## Recorded evidence

`scripts/verify_evidence.py` verifies the recorded source hashes, complete request-cost records, accuracy-review hash and frozen review protocol using only files included in this repository. The two original executed source snapshots are under `benchmarks/recorded-source/`.

The recorded measurements refer to those historical source versions. The sharing copy changes credential lifetime, cache serialization, setup and documentation. The retrieval and answering modules `agent.py`, `classic.py` and `keywords.py` are unchanged from the working project. It is therefore important to distinguish recorded live measurements from the packaging regressions above.

## Contents and scope

The sharing package contains source, tests, a synthetic demo PDF, frozen benchmark cases, recorded measurements and source snapshots. It excludes API keys, environment files, virtual environments, uploads, generated indexes, logs and the copyrighted Ableton manual. The ZIP excludes Git metadata; the local repository retains development history and has no remote configured.

The working tree and the source ZIP are checked separately. The ZIP can be extracted, its evidence verified, and its portable fixture checked without the original checkout or Git history.

This remains a local research proof of concept. The six-task completeness review is assistant-scored and has explicit rubric limitations; it is not a representative independent accuracy evaluation or a production-service claim.
