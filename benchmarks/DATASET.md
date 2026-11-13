# SMS Spam Collection sample

This benchmark uses 30 messages from the public **SMS Spam Collection** dataset by
Tiago Almeida and Jos Hidalgo (2011), UCI Machine Learning Repository,
[DOI 10.24432/C5CC84](https://doi.org/10.24432/C5CC84).

The [official UCI dataset page](https://archive.ics.uci.edu/dataset/228/sms+spam+collection)
states that the dataset is licensed under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
This permits redistribution and adaptation with attribution. This document supplies
the dataset credit and source links; retain them when redistributing this sample.
The sample selection and JSON conversion are changes made for Concord. Message
text and source labels are unchanged. No endorsement by the dataset authors is implied.

## Committed source and evidence

- `data/source/sms-spam-collection.zip` is the complete archive downloaded from
  [UCI's official download](https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip).
  SHA-256: `1587ea43e58e82b14ff1f5425c88e17f8496bfcdb67a583dbff9eefaf9963ce3`.
- `data/source/uci-dataset-page.html` records the official page, including the
  attribution and CC BY 4.0 license statement, fetched on 2026-11-13 UTC
  (2026-11-14 in Singapore).
- `data/source/CC-BY-4.0.txt` is the license text fetched from
  [Creative Commons](https://creativecommons.org/licenses/by/4.0/legalcode.txt).
- `data/manifest.json` pins SHA-256 checksums for the archive, original source
  member, saved evidence, license text, and generated files. Retrieval dates
  describe the committed downloads, not a claim that future downloads are identical.

The original `SMSSpamCollection` member contains 5,574 records: 4,827 `ham` and
747 `spam`. Its SHA-256 is
`7d039a24a6083ed9ef0f806ebad56bbb976e3aeb8de05669173bfdc4996c239d`.
The archive includes its original `readme`, which describes collection sources.

## Deterministic selection and schemas

Select the first 15 records labeled `ham` and the first 15 labeled `spam`, then
retain their original source-row order. There is no random seed, AI selection,
or generated reference label. This balanced convenience sample is for a small
workflow demonstration; it is not a representative test split or a model-quality
estimate for the complete dataset.

`data/dataset.jsonl` contains UTF-8 JSON objects with this schema:

```json
{
  "id": "sms-00001",
  "text": "<original SMS text>",
  "metadata": { "source_row": 1, "dataset": "uci_sms_spam_collection" }
}
```

`id` encodes the original one-based source row. Text preserves original spelling,
Unicode, capitalization, and all SMS whitespace, including trailing spaces.
Only the source label, separating tab, and record-ending newline are removed.
The metadata contains no reference label. Import adapters should map `id` to
Concord's `external_id`; this source-neutral file is not a rating-mode upload
with the app's required `prompt` and `response` fields.

`data/reference-labels.json` is a separate object mapping those IDs to their
original source labels (`ham` or `spam`). Evaluation may read this file; annotators
should receive only the message records and labeling guidelines.

## Offline reproduction

From the repository root, using Python 3.12+ and only its standard library:

```sh
python benchmarks/prepare_dataset.py
python benchmarks/prepare_dataset.py --check
```

The default command verifies the source and evidence checksums, regenerates both
fixtures, and checks their expected hashes. `--check` verifies the committed
fixtures without rewriting them. Neither command accesses the network.

To deliberately re-download the exact pinned official archive:

```sh
python benchmarks/prepare_dataset.py --fetch-source
```

This command rejects changed archive bytes before replacing the local archive.
Updating to a different source version requires reviewing the dataset, license,
selection, and manifest together.
