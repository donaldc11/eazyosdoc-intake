"""Orchestrates extraction, classification, and field extraction into a JSON
record per document plus a CSV ledger. Idempotent: documents are keyed by the
sha256 hash of their bytes, so re-running against the same files never
creates duplicate records or ledger rows."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from . import classify, extract, gemini_engine, naics
from . import fields as fx

EXPECTED_FIELDS = {
    # accessorial_charges is deliberately excluded: a clean linehaul-only
    # rate con has none, so its absence shouldn't force a review.
    "rate_confirmation": [
        "load_reference_number", "shipper", "pickup_location", "pickup_date",
        "delivery_location", "delivery_date", "equipment_type", "amount", "currency",
    ],
    # po_number is deliberately excluded: not every BOL references a
    # customer PO, so its absence shouldn't force a review.
    "bol": ["load_reference_number", "shipper", "consignee", "piece_count", "weight"],
    # exception_notes is deliberately excluded: it flags a problem when
    # present, but a clean POD has none, so its absence shouldn't force
    # a review.
    "pod": ["load_reference_number", "consignee", "delivered_at", "piece_count"],
    "invoice": ["load_reference_number", "amount", "currency", "shipper"],
    # naics_code is deliberately excluded: the spec calls it out as "if
    # present" rather than a required field, so its absence shouldn't force
    # a review.
    "solicitation": ["issuing_agency", "solicitation_number", "due_date", "buyer_contact"],
    "unknown": [],
}

CONFIDENCE_REVIEW_THRESHOLD = 0.6

CSV_FIELDNAMES = [
    "document_id",
    "source_path",
    "document_type",
    "classification_confidence",
    "load_reference_number",
    "shipper",
    "consignee",
    "pickup_location",
    "pickup_date",
    "delivery_location",
    "delivery_date",
    "equipment_type",
    "amount",
    "currency",
    "accessorial_charges",
    "piece_count",
    "weight",
    "po_number",
    "delivered_at",
    "exception_notes",
    "issuing_agency",
    "solicitation_number",
    "due_date",
    "naics_code",
    "naics_lookup_code",
    "naics_lookup_confidence",
    "buyer_contact",
    "missing_fields",
    "review_status",
    "extraction_note",
    "processed_at",
    "raw_text_path",
]


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_existing_hashes(ledger_path: Path) -> set:
    if not ledger_path.exists():
        return set()
    with ledger_path.open(newline="", encoding="utf-8") as f:
        return {row["document_id"] for row in csv.DictReader(f)}


def build_record(path: Path, doc_id: str) -> Tuple[dict, str]:
    raw_text, note = extract.extract_text(path)
    doc_type, confidence, scores = classify.classify(raw_text)

    record_fields = {
        "load_reference_number": fx.extract_load_reference(raw_text),
        "shipper": fx.extract_shipper(raw_text),
        "consignee": fx.extract_consignee(raw_text),
        "pickup_date": fx.extract_pickup_date(raw_text),
        "delivery_date": fx.extract_delivery_date(raw_text),
        "pickup_location": fx.extract_pickup_location(raw_text),
        "delivery_location": fx.extract_delivery_location(raw_text),
        "equipment_type": fx.extract_equipment_type(raw_text),
    }
    amount, currency = fx.extract_amount_currency(raw_text)
    record_fields["amount"] = amount
    record_fields["currency"] = currency
    record_fields["accessorial_charges"] = fx.extract_accessorial_charges(raw_text)
    record_fields["piece_count"] = fx.extract_piece_count(raw_text)
    record_fields["weight"] = fx.extract_weight(raw_text)
    record_fields["po_number"] = fx.extract_po_number(raw_text)
    record_fields["delivered_at"] = fx.extract_delivered_at(raw_text)
    record_fields["exception_notes"] = fx.extract_exception_notes(raw_text)
    record_fields["issuing_agency"] = fx.extract_issuing_agency(raw_text)
    record_fields["solicitation_number"] = fx.extract_solicitation_number(raw_text)
    record_fields["due_date"] = fx.extract_due_date(raw_text)
    record_fields["naics_code"] = fx.extract_naics_code(raw_text)
    record_fields["buyer_contact"] = fx.extract_buyer_contact(raw_text)

    record = _finalize_record(doc_id, path, doc_type, confidence, scores, record_fields, note, raw_text)
    return record, raw_text


def _finalize_record(doc_id: str, path: Path, doc_type: str, confidence: float, scores: dict,
                      record_fields: dict, note: str, raw_text: str) -> dict:
    """Shared by both engines: applies the same missing-field/review-status
    logic and assembles the same record shape regardless of which engine
    produced doc_type/confidence/record_fields."""
    naics_lookup_code, naics_lookup_confidence = naics.lookup_naics(raw_text)
    record_fields = {**record_fields, "naics_lookup_code": naics_lookup_code, "naics_lookup_confidence": naics_lookup_confidence}

    expected = EXPECTED_FIELDS.get(doc_type, [])
    missing = [key for key in expected if record_fields.get(key) is None]

    needs_review = (
        doc_type == "unknown"
        or confidence < CONFIDENCE_REVIEW_THRESHOLD
        or bool(missing)
        or bool(note)
    )

    return {
        "document_id": doc_id,
        "source_path": str(path.resolve()),
        "document_type": doc_type,
        "classification_confidence": confidence,
        "classification_scores": scores,
        **record_fields,
        "missing_fields": missing,
        "review_status": "needs_review" if needs_review else "ok",
        "extraction_note": note,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "raw_text_path": None,
    }


def build_record_with_gemini(path: Path, doc_id: str, client=None) -> Tuple[dict, str]:
    """Same output shape as build_record, sourced from Gemini multimodal
    instead of the regex engine. raw_text is still extracted locally (for
    the audit trail and as input to the local, API-free NAICS lookup) —
    Gemini reads the document's raw bytes directly for classification and
    field extraction."""
    raw_text, note = extract.extract_text(path)

    try:
        result = gemini_engine.classify_and_extract(path, client=client)
    except ValueError as exc:
        doc_type, confidence, scores = "unknown", 0.0, {"engine": "gemini"}
        record_fields = {key: None for key in gemini_engine.FIELD_NAMES}
        note = note or str(exc)
        record = _finalize_record(doc_id, path, doc_type, confidence, scores, record_fields, note, raw_text)
        return record, raw_text

    doc_type = result["document_type"]
    confidence = result["confidence"]
    scores = {"engine": "gemini"}
    record_fields = {key: result.get(key) for key in gemini_engine.FIELD_NAMES}

    record = _finalize_record(doc_id, path, doc_type, confidence, scores, record_fields, note, raw_text)
    return record, raw_text


def run(samples_dir: Path, out_dir: Path, engine: str = "regex", gemini_client=None) -> Tuple[List[dict], int]:
    records_dir = out_dir / "records"
    raw_dir = out_dir / "raw_text"
    records_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "ledger.csv"

    existing_hashes = load_existing_hashes(ledger_path)
    input_files = sorted(
        p for p in samples_dir.iterdir()
        if p.is_file() and p.suffix.lower() in extract.SUPPORTED_EXTENSIONS
    )

    new_rows = []
    skipped = 0

    for path in input_files:
        doc_id = hash_file(path)
        if doc_id in existing_hashes:
            skipped += 1
            print(f"skip (already processed, hash matches): {path.name}")
            continue

        if engine == "gemini":
            record, raw_text = build_record_with_gemini(path, doc_id, client=gemini_client)
        else:
            record, raw_text = build_record(path, doc_id)

        raw_text_file = raw_dir / f"{doc_id}.txt"
        raw_text_file.write_text(raw_text, encoding="utf-8")
        record["raw_text_path"] = str(raw_text_file.resolve())

        record_file = records_dir / f"{doc_id}.json"
        record_file.write_text(json.dumps(record, indent=2), encoding="utf-8")

        row = {key: record.get(key) for key in CSV_FIELDNAMES}
        row["missing_fields"] = ";".join(record["missing_fields"])
        new_rows.append(row)
        existing_hashes.add(doc_id)

        print(f"processed: {path.name} -> {record['document_type']} ({record['review_status']})")

    if new_rows:
        write_header = not ledger_path.exists()
        with ledger_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerows(new_rows)

    print(f"\n{len(new_rows)} new document(s) processed, {skipped} skipped as duplicates.")
    return new_rows, skipped
