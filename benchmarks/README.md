# Reproducible annotation sample

This sample exercises Concord's actual API from import through an independently
checked export. Every annotation and review decision is simulated. The reference
labels come from the public dataset, not an AI-generated answer key.

## Run from a fresh checkout

Requires `uv`, which installs the pinned Python 3.12 runtime. No browser, Node.js,
database server, API server, account setup, or model API key is required for the
automated workflow. Dependency installation needs network access; the fixture and
workflow run offline afterward.

```sh
uv sync --project apps/api --extra dev --frozen
uv run --project apps/api --extra dev --frozen python benchmarks/prepare_dataset.py --check
uv run --project apps/api --extra dev --frozen python benchmarks/run.py --output .local/benchmark
```

After normal repository setup, `pnpm benchmark` runs the same workflow. Each run
requires a fresh output directory. For example, use `--output .local/benchmark-2`
for the second run. The runner refuses to overwrite an existing benchmark database
and does not use the application's normal database. Generated runs are ignored by
Git. CI reproduces the workflow and uploads its artifacts.

The [recorded local run](RESULTS.md) includes verified counts, checks, timings,
and the machine and runtime conditions under which they were measured.

## The five parts

| Part                             | Implementation                                                            | Evidence                                                                                             |
| -------------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| 1. Licensed public dataset       | [Dataset provenance](DATASET.md), source archive and checksum manifest    | Offline regeneration preserves original text, source-row IDs and labels                              |
| 2. Established reference set     | Separate source labels and [independent metric definitions](REFERENCE.md) | Exact rational arithmetic, published worked examples and exhaustive small cases                      |
| 3. Controlled submissions        | `simulation.py` and `run.py`                                              | Three distinct authenticated annotators claim, save and submit all 30 records                        |
| 4. Review                        | [Review procedure](REVIEW.md)                                             | Reviewer inspects all records, including wrong unanimous results, and records source-based decisions |
| 5. Independent export validation | [Validator](EXPORT_VALIDATION.md)                                         | A separate standard-library Python process checks JSONL content and rejects corruption               |

Only account provisioning and database schema creation bypass the HTTP API.
Project creation, team membership, imports, allocation, draft saves, submissions,
metrics, review, completion, and exports all use the existing API routes with
cookie sessions, trusted Origin and CSRF headers. The runner uses HTTPX's in-process
ASGI transport; it does not measure browser or network behavior.

The source-neutral fixture maps `id` to `external_id` and original SMS `text` to
the rating editor's `prompt`. The `response` is the fixed instruction
`Classify this message as ham or spam.` Metadata holds dataset provenance only;
the reference label remains in a separate local file. This reuses Concord's
categorical rating mode without changing its annotation schema.

## Expected controls

There are 30 messages, balanced between 15 `ham` and 15 `spam`, and 90 simulated
annotations. Sort IDs and take each zero-based index modulo six:

| Remainder | Introduced mistake                     |
| --------- | -------------------------------------- |
| 0         | Rater 3 flips the source label         |
| 1         | Rater 2 flips the source label         |
| 2         | All three raters flip the source label |
| 3, 4, 5   | All three retain the source label      |

At Concord's 80% review threshold, the 10 two-to-one splits need review. The 20
unanimous items resolve automatically, but 5 of those have the wrong source label.
The scripted reviewer inspects all 30 and explicitly adjudicates them to the source
labels. This tests that review can override consensus while preserving raw votes.

The independent pre-review reference gives Fleiss' kappa `281/506`
(`0.5553359683794467`). Pairwise Cohen kappas are `2/3`, `2/3`, and `1/3`.
Review must leave these raw-vote agreement scores unchanged. The final export must
contain all 30 adjudicated records with the original IDs and text, and the raw
export must still contain the original 90 simulated submissions.

Source files, vote policy, labels, counts, and metric values reproduce exactly.
Generated project/item/assignment UUIDs, submission times, timings, and resulting
export byte hashes vary between runs. A validator hash identifies one artifact;
it is not an expectation that fresh runs produce byte-identical exports.

The balanced convenience sample is not a representative model evaluation set.
The simulation uses the source labels to construct deliberate mistakes and to
resolve them. It cannot establish human agreement, annotation usability, improved
model accuracy, or time savings.

## Inspect the output

| File                                         | Contents                                                                                      |
| -------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `report.json`                                | Overall result, API probes, review evidence, independent comparisons and measured stage times |
| `validation.json`                            | Standalone export validation results                                                          |
| `metrics-before.json` / `metrics-after.json` | API metrics around review                                                                     |
| `reference-metrics.json`                     | Independent metric calculations                                                               |
| `simulated-submissions.json`                 | Explicit simulation policy and intended submissions                                           |
| `consensus.jsonl`                            | Approved records, preceded by the export manifest                                             |
| `annotations.jsonl`                          | Original simulated submissions, preceded by the export manifest                               |
| `benchmark.sqlite3`                          | Completed project and its separate role accounts                                              |
| `failure.json`                               | Diagnostics if a run fails                                                                    |

JSONL exports begin with a `_manifest` record; consumers should read that record
separately before reading the data rows. Rerun the validator in a separate process:

```sh
python benchmarks/validate_export.py --dataset benchmarks/data/dataset.jsonl --reference benchmarks/data/reference-labels.json --consensus .local/benchmark/consensus.jsonl --annotations .local/benchmark/annotations.jsonl --submissions .local/benchmark/simulated-submissions.json --output .local/benchmark/revalidated.json
```

The validator uses only Python's standard library, so it can run outside Concord's
virtual environment. `--skip-validation` is a runner development option and never
produces a passing overall report.

### Open the completed project in Concord

With the normal web dependencies installed, point a separate API process at the
generated database. In PowerShell, from the repository root:

```powershell
$benchmarkDb = (Resolve-Path .local/benchmark/benchmark.sqlite3).Path.Replace('\', '/')
$env:DATABASE_URL = "sqlite+aiosqlite:///$benchmarkDb"
uv run --directory apps/api uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal run `pnpm dev:web`, then visit `http://localhost:3000`. Use the
email/password fields rather than the normal demo account selectors. These
benchmark-only accounts all use password `local-benchmark-only-2026`:

| Account                      | Role                                 |
| ---------------------------- | ------------------------------------ |
| `admin@benchmark.invalid`    | Administrator                        |
| `reviewer@benchmark.invalid` | Reviewer                             |
| `rater1@benchmark.invalid`   | Annotator 1                          |
| `rater2@benchmark.invalid`   | Annotator 2                          |
| `rater3@benchmark.invalid`   | Annotator 3                          |
| `outsider@benchmark.invalid` | Annotator without project membership |

Use separate browser profiles for simultaneous role inspection. The project is
completed, so reviewers can inspect decisions and export results; annotators have
no remaining work. Starting this database does not seed the normal demo accounts.

## Checks and limits

```sh
uv run --directory apps/api pytest
uv run --project apps/api ruff check --config apps/api/pyproject.toml apps/api benchmarks
```

The runner probes unauthorized access, CSRF and Origin rejection, completion
before coverage, recovery of saved drafts, stale versions, duplicate submissions,
and submitted-annotation immutability. Draft recovery is an API check, not a browser
refresh or network-interruption experiment. Blinded A/B behavior belongs to the
existing API tests; this sample uses categorical ratings.

Timing observations describe one local SQLite run at this sample size. They are
not throughput, large-dataset, production, or browser-performance claims. The
report records request and stage durations; repeat runs under controlled conditions
before drawing performance conclusions. Concurrent reviewer edits still use the
application's existing last-write-wins behavior and are not protected by this
benchmark. This work adds a reproducible demonstration, not every reliability or
performance improvement listed in the project roadmap.
