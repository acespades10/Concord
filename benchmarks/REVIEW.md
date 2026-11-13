# Simulated source-reference review

`benchmarks/run.py` calls `await review_project(reviewer, project_id,
reference_labels)` with an authenticated reviewer API client and the labels in
`benchmarks/data/reference-labels.json`. This is automatic reference-based
adjudication. The script has the source answers; it performs no human judgment
and provides no evidence of improved annotator accuracy.

The helper reads the ordinary review queue, then `GET
/api/v1/projects/{project_id}/review?all_items=true`. It checks exact source-ID
coverage and three submitted ratings per item before writing any decisions.
It inspects all 30 items, including items already resolved by unanimous votes.
For each item it sends `PUT
/api/v1/projects/{project_id}/items/{item_id}/adjudication` with `mode: rating`,
the source label, and a rationale explicitly identifying a simulated review
against the source reference label.

The deterministic three-rater policy produces 10 disagreement items and five
unanimously wrong items. Reviewing only the initial queue would miss all five
unanimously wrong items. All 30 receive explicit adjudications, including the
15 unanimously correct items.

The JSON evidence includes each item's original votes, source label and
rationale; the initial and final queue counts; and SHA-256 hashes of the
submitted annotation representations before and after review. The helper
fails if these annotation payloads change, if any final decision or resolved
label differs from its reference, or if the final queue is nonempty. The runner
also checks that submission counts, raw label distribution, Fleiss' kappa and
pairwise metrics remain unchanged, and exports raw annotations for independent
validation.

This is a sequential workflow demonstration. The existing adjudication API
allows a later reviewer write to replace an earlier decision (last-write-wins).
This benchmark does not demonstrate reviewer conflict protection, independent
human review, source-label infallibility, or out-of-sample quality.
