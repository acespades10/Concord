"""Deterministic scripted votes, explicitly separate from human annotations."""

from collections.abc import Mapping

SIMULATION_NOTE = "SIMULATED ANNOTATION: scripted benchmark vote; not a human judgment."
POLICY = (
    "Sort external IDs, then use zero-based index modulo 6: 0 flips rater3; "
    "1 flips rater2; 2 flips all three; 3, 4 and 5 keep the reference label. "
    "The reference drives a controlled error simulation, not a blinded annotation study."
)
RATERS = ["rater1", "rater2", "rater3"]
IMPORT_RESPONSE = "Classify this message as ham or spam."


def build_votes(reference_labels: Mapping[str, str]) -> dict[str, list[str]]:
    """Return three ordered votes per ID with controlled disagreement and shared errors."""
    votes = {}
    for index, external_id in enumerate(sorted(reference_labels)):
        label = reference_labels[external_id]
        if label not in {"ham", "spam"}:
            raise ValueError(f"Unsupported reference label for {external_id}: {label!r}")
        row = [label] * 3
        flipped = "spam" if label == "ham" else "ham"
        for rater in {0: [2], 1: [1], 2: [0, 1, 2]}.get(index % 6, []):
            row[rater] = flipped
        votes[external_id] = row
    return votes
