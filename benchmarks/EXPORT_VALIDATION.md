# Independent export validation

`validate_export.py` uses only the Python standard library. It imports neither
Concord nor the benchmark runner, simulation, review, or reference-metric code.
It reads the five supplied artifacts and writes a JSON report. Exit code 0
requires every check to pass; missing, malformed, inconsistent, or unsupported
input produces a failed report and a nonzero exit code.

From the repository root, run:

```powershell
python -m benchmarks.validate_export `
  --dataset benchmarks/data/dataset.jsonl `
  --reference benchmarks/data/reference-labels.json `
  --consensus .local/benchmark/consensus.jsonl `
  --annotations .local/benchmark/annotations.jsonl `
  --submissions .local/benchmark/simulated-submissions.json `
  --output .local/benchmark/validation.json
```

The normal runner invokes this command automatically. The validator also works
with `python -S`, with third-party site packages disabled. It never reconstructs
an export from source data or repairs an artifact before checking it.

The report contains `passed`, item and submission counts, named checks, and the
SHA-256 digest and byte length of each input. Digests identify the exact files
examined; they are evidence for reproducing the check, not signatures proving
the files' origin. The dataset and reference file are the trusted comparison
inputs. Independently authenticating the public dataset is a separate step.

The checks require:

- Unique source IDs and an exact reference-label ID set; labels must be `ham`
  or `spam`.
- One leading manifest per export, schema `1.0.0`, completed rating mode, the
  documented project configuration, selected dataset names, and correct counts.
  Both manifests must describe the same project and metric revision.
- An exact source-text roundtrip, including whitespace and Unicode code points,
  the documented response prompt, empty rating tokens, and lossless metadata.
  The import wraps source metadata, so `metadata_json` must decode to
  `{"metadata": <source row metadata>}`.
- Exactly three distinct pseudonymous raters for every source item. Raw payloads
  must match the submission ledger and an independently implemented six-item
  simulation cycle. Duplicate item/rater pairs and assignment IDs fail.
- Every consensus item explicitly adjudicated by the benchmark reviewer, with
  its source reference label, the API's default empty payload note, and
  automatic-review rationale. The exported vote
  share must retain the original scripted majority's support, even when the
  reviewer corrects a unanimously wrong scripted label.
- Strict permitted fields, canonical UUID identities, valid submission times,
  and no email addresses, authentication secrets, or reference-label fields in
  metadata. Unknown fields, JSON duplicate keys, non-finite numbers, missing
  records, and unknown IDs fail closed.

Raw payload notes must say `SIMULATED ANNOTATION: scripted benchmark vote; not a
human judgment.` The submission artifact must disclose the same simulation
policy. Consensus labels are automatic source-reference adjudications, so a
successful result demonstrates export integrity for this controlled fixture.
It does not measure human annotation agreement or independent label quality.

`apps/api/tests/test_benchmark_exports.py` builds fixtures without importing any
application code and tests corruption of text, Unicode, labels, coverage,
identities, review status, metadata, manifests, and JSON syntax. Its CLI test
disables site packages and checks both success and nonzero failure behavior.
An additional integration test runs the real API benchmark with validation
enabled to check the export serialization contract against the CLI.
