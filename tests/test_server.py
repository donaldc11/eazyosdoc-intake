"""Server tests use FastAPI's TestClient against the default (regex) engine
only — no network calls, no GEMINI_API_KEY needed, so CI stays green."""

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from main import app

client = TestClient(app)


def _make_pdf_bytes(lines):
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


def test_root_returns_usage_info():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_process_rate_confirmation_pdf():
    pdf_bytes = _make_pdf_bytes([
        "RATE CONFIRMATION",
        "Load #: RC-1",
        "Shipper: Test Shipper",
        "Pickup Location: Fresno, CA",
        "Pickup Date: 10/02/2026",
        "Delivery Location: Dallas, TX",
        "Delivery Date: 10/04/2026",
        "Equipment Type: Reefer",
        "Linehaul Rate: $500.00",
    ])
    response = client.post(
        "/process",
        files={"file": ("rc.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["document_type"] == "rate_confirmation"
    assert body["load_reference_number"] == "RC-1"
    assert body["review_status"] == "ok"
    # Stateless: no server-local paths leak into the response.
    assert body["source_path"] == "rc.pdf"
    assert body["raw_text_path"] is None


def test_process_rejects_unsupported_file_type():
    response = client.post(
        "/process",
        files={"file": ("data.xyz", b"whatever", "application/octet-stream")},
    )
    assert response.status_code == 400


def test_process_rejects_bad_engine():
    response = client.post(
        "/process",
        params={"engine": "not-a-real-engine"},
        files={"file": ("rc.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 400
