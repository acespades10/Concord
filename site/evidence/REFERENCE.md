# Reference labels and independent metric checks

The small SMS reference set has 30 items: the first 15 `ham` records and first
15 `spam` records in the UCI SMS Spam Collection's original source order.
`data/reference-labels.json` preserves the collection's established labels,
keyed by the imported external IDs. The benchmark does not treat the labels as
new human judgments. Dataset acquisition, citation, and integrity information
are in `data/`.

The balanced, deterministic subset supports a reproducible workflow exercise.
It is too small and selectively sampled to estimate performance on the full
collection or production messages. Source labels can contain annotation error.
Do not present a comparison against them as an independent contemporary review.

## Independent calculation

`reference.py` uses only the Python standard library and never imports the app.
It computes unweighted categorical Cohen kappa from a contingency table and
Fleiss kappa by explicitly enumerating rater pairs. `fractions.Fraction` keeps
observed agreement, chance agreement, and kappa exact until JSON float output;
each defined kappa also includes its rational `exact` value.

For Fleiss kappa, retain only items with exactly the target number of votes.
Observed agreement is the number of equal-label unordered rater pairs divided
by all possible unordered pairs over those items. Chance agreement is the sum
of squared pooled category proportions. For pairwise Cohen kappa, retain only
items submitted by both raters. Observed agreement is the contingency diagonal
divided by shared items; chance agreement is the sum of the products of the two
raters' category marginal proportions. Both use `(observed - chance)/(1 - chance)`.

Missing data are excluded from the relevant calculation rather than imputed.
No complete items (or fewer than two target raters) makes Fleiss kappa undefined.
No shared items makes pairwise Cohen kappa undefined. Chance agreement of one
makes either kappa undefined, including perfect agreement using only one label.
Undefined values are JSON `null` with an explicit reason; they are not zero.

Coverage is submissions divided by items times target raters. An item needs at
least three votes, a strict majority, and vote share at least 0.8 to resolve at
the benchmark settings. Thus three raters must agree unanimously: a 2:1 split
has share 2/3 and enters review. Awaiting items are excluded from the `unresolved`
review count. Label distribution counts submitted labels, including dissent.
Adjudication does not rewrite the original vote-based kappas or distribution.

## Established worked examples

`reference-cases.json` records the inputs and expected results used by
`apps/api/tests/test_benchmark_reference.py`:

1. The published [Fleiss worked example](https://en.wikipedia.org/wiki/Fleiss%27_kappa#Worked_example)
   has 10 subjects, 14 raters, and five categories. Its count matrix yields
   `4211/20059 = 0.20993070442195524`; the checked-in rounded expectation is
   `0.2099307`. Definition: Fleiss (1971), _Measuring nominal scale agreement
   among many raters_, [doi:10.1037/h0031619](https://doi.org/10.1037/h0031619).
2. The published [Cohen simple example](https://en.wikipedia.org/wiki/Cohen%27s_kappa#Simple_example)
   has contingency counts `[[20,5],[10,15]]` for 50 grant proposals. Observed
   agreement is `35/50`, chance agreement is `1/2`, and kappa is `2/5 = 0.4`.
   Definition: Cohen (1960), _A coefficient of agreement for nominal scales_,
   [doi:10.1177/001316446002000104](https://doi.org/10.1177/001316446002000104).
3. Hand-checkable cases cover balanced unanimity (`1`), equal opposite pairs
   (`-1`), and two opposite 2:1 three-rater splits (`-1/3`). In the last case
   observed agreement is `1/3`, chance agreement is `1/2`.

The two online worked examples were checked on 2026-11-14; copies of their
numeric inputs are checked in so tests do not depend on network availability.
The exact Fleiss fraction is derived from that published matrix, not a claim
that the article prints the fraction.

Tests compare the application with these independent results, exhaust all 64
binary two-item/three-rater matrices, cover undefined cases, and compare full
summary counts, missing-vote handling, consensus, and pairwise statistics.
Run from the repository root after installing the API development dependencies:

```powershell
uv run --project apps/api --extra dev pytest apps/api/tests/test_benchmark_reference.py
```

## Simulation limits and wrong-consensus controls

The deterministic benchmark uses three simulated raters. For item indices
after sorting external IDs, residue 0 modulo 6 flips rater 3, residue 1 flips
rater 2, residue 2 flips all three, and residues 3, 4, and 5 preserve source
labels. Across 30 items this creates ten disagreements and five unanimously
wrong controls. This policy measures a workflow under scripted errors. It is
not evidence of human annotator agreement, usability, or annotation speed.

Reviewing only disagreement rows would leave all five wrong-consensus controls
undetected. The review run must inspect every row or explicitly correct those
five controls against source labels. Compare submitted votes, automatic
consensus, and reviewed output separately against the reference labels.
