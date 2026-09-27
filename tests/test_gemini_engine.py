"""Tests for the Gemini engine use a stub client — no network calls, no
GEMINI_API_KEY needed, so CI stays green without the real credential."""

import json

import pytest

from intake import gemini_engine


class FakeResponse:
    """Mimics google.genai's GenerateContentResponse just enough for
    classify_and_extract: no .parsed (forcing the json.loads(response.text)
    fallback path), plus a .text with the raw JSON string."""

    def __init__(self, payload: dict):
        self.parsed = None
        self.text = json.dumps(payload)


class FakeModels:
    def __init__(self, payload: dict):
        self._payload = payload
        self.last_call = None

    def generate_content(self, model, contents, config):
        self.last_call = {"model": model, "contents": contents, "config": config}
        return FakeResponse(self._payload)


class FakeClient:
    def __init__(self, payload: dict):
        self.models = FakeModels(payload)


RATE_CON_PAYLOAD = {
    "document_type": "rate_confirmation",
    "confidence": 0.95,
    "load_reference_number": "RC-1001",
    "shipper": "Sunrise Produce Co",
    "consignee": "Metro Grocers Distribution",
    "pickup_date": "10/02/2026",
    "delivery_date": "10/04/2026",
    "pickup_location": "Fresno, CA",
    "delivery_location": "Dallas, TX",
    "equipment_type": "53' Dry Van",
    "amount": "2450.00",
    "currency": "USD",
    "accessorial_charges": "Fuel Surcharge: $180.00",
    "piece_count": None,
    "weight": None,
    "po_number": None,
    "delivered_at": None,
    "exception_notes": None,
    "issuing_agency": None,
    "solicitation_number": None,
    "due_date": None,
    "naics_code": None,
    "buyer_contact": None,
}


def test_classify_and_extract_parses_stub_response(tmp_path):
    doc = tmp_path / "rc.txt"
    doc.write_text("RATE CONFIRMATION\nLoad #: RC-1001\n", encoding="utf-8")

    client = FakeClient(RATE_CON_PAYLOAD)
    result = gemini_engine.classify_and_extract(doc, client=client)

    assert result["document_type"] == "rate_confirmation"
    assert result["confidence"] == 0.95
    assert result["load_reference_number"] == "RC-1001"
    assert result["pickup_location"] == "Fresno, CA"
    assert result["accessorial_charges"] == "Fuel Surcharge: $180.00"
    # Fields the model didn't return anything for stay None, never invented.
    assert result["piece_count"] is None
    assert result["po_number"] is None


def test_classify_and_extract_sends_document_bytes(tmp_path):
    doc = tmp_path / "rc.txt"
    doc.write_text("RATE CONFIRMATION\n", encoding="utf-8")

    client = FakeClient(RATE_CON_PAYLOAD)
    gemini_engine.classify_and_extract(doc, client=client)

    call = client.models.last_call
    assert call["model"]
    # contents = [prompt, Part.from_bytes(...)] — the document itself is sent,
    # not just a description of it.
    assert len(call["contents"]) == 2
    assert gemini_engine.PROMPT in call["contents"]


def test_unrecognized_document_type_falls_back_to_unknown(tmp_path):
    doc = tmp_path / "weird.txt"
    doc.write_text("something", encoding="utf-8")

    payload = {**RATE_CON_PAYLOAD, "document_type": "not_a_real_type"}
    client = FakeClient(payload)
    result = gemini_engine.classify_and_extract(doc, client=client)

    assert result["document_type"] == "unknown"


def test_missing_keys_default_to_none(tmp_path):
    doc = tmp_path / "sparse.txt"
    doc.write_text("INVOICE", encoding="utf-8")

    client = FakeClient({"document_type": "invoice", "confidence": 0.8})
    result = gemini_engine.classify_and_extract(doc, client=client)

    assert result["document_type"] == "invoice"
    assert result["shipper"] is None
    assert result["amount"] is None


def test_malformed_json_response_raises_value_error(tmp_path):
    doc = tmp_path / "doc.txt"
    doc.write_text("something", encoding="utf-8")

    class BrokenResponse:
        parsed = None
        text = "not json at all {{{"

    class BrokenModels:
        def generate_content(self, model, contents, config):
            return BrokenResponse()

    class BrokenClient:
        models = BrokenModels()

    with pytest.raises(ValueError):
        gemini_engine.classify_and_extract(doc, client=BrokenClient())


def test_get_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gemini_engine.get_client()


def test_mime_type_guessing(tmp_path):
    assert gemini_engine.guess_mime_type(tmp_path / "a.pdf") == "application/pdf"
    assert gemini_engine.guess_mime_type(tmp_path / "a.png") == "image/png"
    assert gemini_engine.guess_mime_type(tmp_path / "a.txt") == "text/plain"
    assert gemini_engine.guess_mime_type(tmp_path / "a.xyz") == "application/octet-stream"
