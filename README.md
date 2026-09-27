# EazyOS Document Intake — local prototype

[![Tests](https://github.com/donaldc11/eazyosdoc-intake/actions/workflows/tests.yml/badge.svg)](https://github.com/donaldc11/eazyosdoc-intake/actions/workflows/tests.yml)

Reads rate confirmations, BOLs, PODs, and invoices from a folder of PDFs/images,
classifies each one, extracts what fields it can find, and writes:

- one JSON record per document in `out/records/`
- one row per document appended to `out/ledger.csv`
- the raw extracted text saved alongside, in `out/raw_text/`, so every field
  in a record can be traced back to the exact text it came from

**This is entirely local.** It does not connect to email, a live EazyOS
account, or any external service. It only reads files from the `samples/`
folder you point it at and writes to `out/`.

## Setup

```bash
cd ~/eazyos-doc-intake
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Generate sample documents

There's no real EazyOS data here — `generate_samples.py` fabricates a small,
clearly-synthetic set of documents (rate confirmation, BOL, POD, invoice, a
deliberately sparse invoice, an unrelated memo, and one rendered "scanned"
image) so the pipeline has something to run against:

```bash
python generate_samples.py
```

This creates `samples/*.pdf` and `samples/*.png`. To use your own documents
instead, just put PDFs/images in `samples/` (redact anything sensitive first)
and skip this step.

## Process the samples

```bash
python run.py --samples ./samples --out ./out
```

Re-running this command is safe: each document is fingerprinted with a
sha256 hash of its bytes, and any hash already present in `out/ledger.csv`
is skipped rather than reprocessed. Editing a document's content changes its
hash and is treated as a new document; renaming a file without changing its
content does **not** — same hash, still recognized as already processed.

## Output layout

```
out/
  ledger.csv           one row per document, for a quick spreadsheet review
  records/<hash>.json  full structured record per document
  raw_text/<hash>.txt  the exact text the record was extracted from
```

Each JSON record contains:

| field | meaning |
|---|---|
| `document_id` | sha256 of the source file's bytes |
| `source_path` | absolute path to the original file |
| `document_type` | `rate_confirmation` / `bol` / `pod` / `invoice` / `solicitation` / `unknown` |
| `classification_confidence` | 0–1, how dominant the winning type's keyword score was |
| `classification_scores` | raw keyword score per candidate type, for auditing |
| `load_reference_number`, `shipper`, `consignee`, `pickup_date`, `delivery_date`, `amount`, `currency` | freight/invoice fields — **`null` when not found, never guessed** |
| `issuing_agency`, `solicitation_number`, `due_date`, `naics_code`, `buyer_contact` | solicitation fields (rate confirmations, RFQs/SBQs/bidder instructions) — `null` when not found; `naics_code` only fills in when the source document states one explicitly |
| `naics_lookup_code`, `naics_lookup_confidence` | best-matching NAICS code from a static local table of codes Eazy Express bids (484xxx trucking, 492xxx couriers, 488xxx freight support, 541xxx as a stretch bucket), and its confidence (0–1); `null`/`0.0` when nothing in the table matches the document text. Distinct from `naics_code`, which only captures a code the document states outright — this is Eazy Express's own best guess, not the buyer's |
| `missing_fields` | fields expected for this document type but not found |
| `review_status` | `ok` or `needs_review` |
| `extraction_note` | set when extraction hit a caveat (e.g. scanned PDF, OCR unavailable) |
| `raw_text_path` | path to the exact extracted text this record was built from |

`review_status` is `needs_review` whenever any of: the document type is
`unknown`, classification confidence is below 0.6, a required field is
missing, or extraction produced a caveat. Nothing is silently auto-approved
when the data is thin.

## Checking a record against its source

For any row in `ledger.csv` (or file in `out/records/`):

1. Open `source_path` — the original PDF/image.
2. Open `raw_text_path` — the exact text the pipeline extracted from it.
3. Compare the record's fields against that raw text. If a field is `null`,
   confirm the raw text really doesn't contain it (rather than the regex
   missing it) — that's the case to loosen the extraction pattern for.
4. If `review_status` is `needs_review`, `missing_fields` tells you exactly
   what to fill in or verify by hand.

## Image / OCR support

Image files (`.png`, `.jpg`, etc.) go through OCR via `pytesseract`, which
needs the `tesseract` binary installed on the machine — it is **not**
installed in this environment, so the sample scanned image will come back
with `extraction_note: "OCR error..."`, empty text, and `review_status:
needs_review`. To enable OCR:

```bash
brew install tesseract
pip install pytesseract
```

Then re-run `python run.py` — the previously-skipped image will be
reprocessed only if you delete its old ledger row/record first (its hash
hasn't changed, so by default it'll still be treated as already handled;
this is a case where you'd intentionally want to reprocess).

## Tests

```bash
pytest
```

Covers: classification on each document type and on unrelated text,
field extraction never inventing values that aren't present, and that
re-running the pipeline against the same files does not create duplicate
records or ledger rows.
