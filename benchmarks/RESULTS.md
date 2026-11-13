# Verified local run

Run on **14 November 2026, Asia/Singapore**, using the checked-in fixture and
`pnpm benchmark`. The overall report and standalone export validation both passed.
Generated artifacts are in `.local/benchmark/` on the implementation machine;
fresh checkouts recreate them with the commands in [README.md](README.md).

All submissions and review decisions in these results are **simulated**.

## Workflow results

| Check                         | Observed result                                                                      |
| ----------------------------- | ------------------------------------------------------------------------------------ |
| Source integrity              | Pinned archive, evidence files and fixtures verified offline                         |
| Imported messages             | 30, with 15 source `ham` and 15 source `spam` labels                                 |
| Simulated submissions         | 90, from three separately authenticated annotators                                   |
| Before review                 | 20 resolved and 10 disagreements queued                                              |
| Wrong unanimous controls      | 5 detected by checking all records against source labels                             |
| Review                        | 30 explicit source-based adjudications; queue reduced to 0                           |
| Raw submissions               | Unchanged by review                                                                  |
| Fleiss' kappa                 | `281/506`, approximately `0.5553359683794467`                                        |
| Pairwise Cohen kappas         | `2/3`, `2/3`, `1/3`                                                                  |
| After-review agreement        | Raw-vote kappas and distributions unchanged                                          |
| Permission and editing probes | 20 passed                                                                            |
| Approved export               | 30 adjudicated records; all original IDs, text, metadata and source labels preserved |
| Raw export                    | 90 original simulated submissions; complete unique item/rater coverage               |
| Independent validation        | Separate standard-library process returned success                                   |

The 20 probes include unauthorized project and export access, trusted Origin and
CSRF enforcement, stale saves/submissions, saved-draft recovery, duplicate
submission rejection, submitted-annotation immutability, and an annotator's
attempt to change an approved label. See the generated report for each probe.

## Measured conditions and timings

One local run with sequential requests, a new SQLite database, and HTTPX's
in-process ASGI transport. Windows 10 build 19045, AMD64 Family 21 Model 56
Stepping 1, four logical CPUs; Python 3.12.13, SQLite 3.53.1, FastAPI 0.142.2,
SQLAlchemy 2.1.3, HTTPX 0.28.1. SQLite uses foreign-key checks, WAL and a 15-second
busy timeout. Dependencies were installed before the timed run.

| Operation                                                | Observed duration |
| -------------------------------------------------------- | ----------------- |
| Import API request, 30 messages                          | 24.034 ms         |
| Claim, save and submit 90 annotations                    | 7.003 s           |
| Read metrics and compare independent calculations        | 0.034 s           |
| Review, unauthorized-edit probe and after-review metrics | 0.915 s           |
| Complete project and export both JSONL files             | 0.095 s           |
| Independent export validator process                     | 0.826 s           |
| Total workflow timer                                     | 12.537 s          |

The total uses `time.perf_counter` and includes fixture checking, schema/account
creation and login. It starts after Python module imports, so it is not the
shell command's total startup time. These observations cover one small fixture
on a general-purpose desktop with uncontrolled background load. They do not
measure large-corpus filtering, concurrent throughput, browser latency, network
latency, or production capacity.

## Validation commands

| Command                                        | Result                                                          |
| ---------------------------------------------- | --------------------------------------------------------------- |
| `uv run --directory apps/api pytest -q`        | 122 backend tests passed                                        |
| `pnpm lint`                                    | Web ESLint and API/benchmark Ruff passed                        |
| `pnpm format:check`                            | Repository Prettier and API/benchmark Ruff format checks passed |
| `uv lock --project apps/api --check`           | Existing dependency lock remained current                       |
| `python benchmarks/prepare_dataset.py --check` | 30 source-derived rows verified                                 |
| `pnpm benchmark`                               | Full workflow and independent export validation passed          |

The export validator has 53 focused tests, including intentionally corrupted
artifacts, a process with site packages disabled, and a complete real-API export
regression. The metric tests include published Fleiss/Cohen examples and all 64
binary two-item/three-rater vote matrices. The first full run exposed the API's
default empty `note` in adjudication payloads; the validator now checks that real
contract, and the integration regression covers it.

The final run's consensus JSONL SHA-256 is
`e23671049a8a194bb56929e0c0b4b598fc69e4b2f801b29aa823f35c5f39e130`.
Its raw annotation JSONL SHA-256 is
`1d1bc1ef7357eb9ec34790885365b3c7399682848310e27085d2321dde2a0d9e`.
These identify this run only; fresh run UUIDs and timestamps change export bytes.
The independently checked source fixture hash remains
`8d0bdc6744d5af7a4ed81936d4be4b19e74c6406ef6761bbaee8e12ab0747509`.

## Scope of the evidence

This run verifies a controlled annotation workflow and consumable JSONL exports.
It is not a human annotation study or an independent re-labeling of the source
dataset. Human agreement, usability, time savings, adoption, and model accuracy
were not measured. Browser/network interruption behavior, concurrent reviewer
conflict protection, large-data performance, PostgreSQL, and hosted CI execution
were not verified by this local run. The CI workflow includes the benchmark;
remote CI results are reported separately by GitHub Actions.
