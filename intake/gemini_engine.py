"""Gemini-based classification/extraction engine. Sends a document's raw
bytes to Gemini multimodal and asks it to classify the document type and
extract the same field set the regex engine (intake.fields) already
produces, so its output can feed the same pipeline: same schema, same
missing-field/review-status logic, same tests.

The API key is read from the GEMINI_API_KEY environment variable — never
hardcoded. Every call site accepts an optional `client` for dependency
injection so tests can stub it out; get_client() is only invoked when no
client is supplied.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel

DEFAULT_MODEL = "gemini-3.8-flash"

DOCUMENT_TYPES = ["rate_confirmation", "bol", "pod", "invoice", "solicitation", "unknown"]

# The full field superset the regex engine computes for every document,
# regardless of type — kept identical here so Gemini's output slots into
# the exact same record shape.
FIELD_NAMES = [
    "load_reference_number", "shipper", "consignee", "pickup_date", "delivery_date",
    "pickup_location", "delivery_location", "equipment_type", "amount", "currency",
    "accessorial_charges", "piece_count", "weight", "po_number", "delivered_at",
    "exception_notes", "issuing_agency", "solicitation_number", "due_date",
    "naics_code", "buyer_contact",
]

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".txt": "text/plain",
}

PROMPT = """You are a document intake classifier for a trucking/logistics company (Eazy Express).

Classify this document as exactly one of: rate_confirmation, bol, pod, invoice, solicitation, unknown.
- rate_confirmation: a broker's rate confirmation / rate con for a truckload
- bol: a bill of lading
- pod: a proof of delivery
- invoice: an invoice/bill (freight or otherwise, e.g. a SaaS subscription invoice)
- solicitation: an RFQ, SBQ, IFB, or bidder-instructions package soliciting a quote/bid
- unknown: anything that doesn't clearly fit one of the above

Then extract these fields from the document text. Use null for any field not
present in the document — never guess, infer, or fabricate a value. Only
report what the document actually states.

- load_reference_number: the load #, BOL #, confirmation #, or invoice # — whichever this document uses as its reference number
- shipper: the shipper or broker/seller name
- consignee: the consignee or receiver name
- pickup_date: the pickup/ship date
- delivery_date: the delivery date
- pickup_location: pickup city/state (distinct from the date)
- delivery_location: delivery city/state (distinct from the date)
- equipment_type: trailer/equipment type (e.g. "53' Dry Van", "Reefer")
- amount: the total/linehaul dollar amount, digits only (e.g. "2450.00")
- currency: the currency code (e.g. "USD")
- accessorial_charges: any fuel surcharge, detention, lumper, or other accessorial line items, verbatim, joined with "; " if more than one
- piece_count: number of pieces/pallets
- weight: shipment weight, with whatever unit the document states (e.g. "42,500 lbs")
- po_number: customer purchase order number, if referenced
- delivered_at: delivery date and time combined if both are stated, date-only otherwise
- exception_notes: verbatim note of any shortage, damage, or refusal at delivery
- issuing_agency: the government agency or company issuing a solicitation
- solicitation_number: the RFQ/SBQ/IFB number or contract/solicitation reference
- due_date: the quote/bid due date for a solicitation
- naics_code: a NAICS code, only if the document states one explicitly
- buyer_contact: the buyer/contact name and/or email for a solicitation

Respond with confidence as your own self-assessed classification confidence, 0 to 1.
"""


class GeminiExtraction(BaseModel):
    document_type: str
    confidence: float
    load_reference_number: Optional[str] = None
    shipper: Optional[str] = None
    consignee: Optional[str] = None
    pickup_date: Optional[str] = None
    delivery_date: Optional[str] = None
    pickup_location: Optional[str] = None
    delivery_location: Optional[str] = None
    equipment_type: Optional[str] = None
    amount: Optional[str] = None
    currency: Optional[str] = None
    accessorial_charges: Optional[str] = None
    piece_count: Optional[str] = None
    weight: Optional[str] = None
    po_number: Optional[str] = None
    delivered_at: Optional[str] = None
    exception_notes: Optional[str] = None
    issuing_agency: Optional[str] = None
    solicitation_number: Optional[str] = None
    due_date: Optional[str] = None
    naics_code: Optional[str] = None
    buyer_contact: Optional[str] = None


def guess_mime_type(path: Path) -> str:
    return MIME_TYPES.get(path.suffix.lower(), "application/octet-stream")


def get_client():
    """Builds a real genai.Client from the GEMINI_API_KEY env var. Never
    call this in a test — inject a stub client instead."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Export it in your shell before running "
            "with --engine gemini; it is never read from a file this codebase commits."
        )
    from google import genai
    return genai.Client(api_key=api_key)


def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    """Fills in any keys Gemini omitted with None, and falls back to
    'unknown' for an unrecognized document_type — never invents a value,
    just guards the shape of what's returned."""
    normalized = {key: data.get(key) for key in FIELD_NAMES}
    doc_type = data.get("document_type")
    normalized["document_type"] = doc_type if doc_type in DOCUMENT_TYPES else "unknown"
    try:
        normalized["confidence"] = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        normalized["confidence"] = 0.0
    return normalized


def classify_and_extract(path: Path, client=None) -> Dict[str, Any]:
    """Sends the document's raw bytes to Gemini multimodal and returns a
    normalized dict: {document_type, confidence, <all FIELD_NAMES>}.
    Raises ValueError if Gemini's response can't be parsed as the expected
    JSON shape — callers should treat that as an extraction failure, not
    invent a fallback value."""
    from google.genai import types

    client = client or get_client()
    mime_type = guess_mime_type(path)
    file_bytes = path.read_bytes()

    response = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
        contents=[PROMPT, types.Part.from_bytes(data=file_bytes, mime_type=mime_type)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeminiExtraction,
        ),
    )

    parsed = getattr(response, "parsed", None)
    if parsed is not None:
        data = parsed.model_dump() if hasattr(parsed, "model_dump") else dict(parsed)
    else:
        try:
            data = json.loads(response.text)
        except (json.JSONDecodeError, TypeError, AttributeError) as exc:
            raise ValueError(f"Gemini response was not valid JSON: {exc}") from exc

    return _normalize(data)
