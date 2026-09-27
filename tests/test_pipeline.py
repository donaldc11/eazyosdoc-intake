import csv

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from intake.pipeline import run


def _make_pdf(path, lines):
    c = canvas.Canvas(str(path), pagesize=letter)
    y = 750
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
    c.save()


def test_dedup_on_rerun(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "out"
    samples.mkdir()
    _make_pdf(samples / "rc.pdf", [
        "RATE CONFIRMATION",
        "Load #: LD-1",
        "Shipper: Test Shipper",
        "Consignee: Test Consignee",
        "Pickup Date: 01/01/2026",
        "Delivery Date: 01/02/2026",
        "Agreed Rate: $500.00",
    ])

    new_rows_1, skipped_1 = run(samples, out)
    assert len(new_rows_1) == 1
    assert skipped_1 == 0

    # Re-running against the same file must not create duplicate records or rows.
    new_rows_2, skipped_2 = run(samples, out)
    assert len(new_rows_2) == 0
    assert skipped_2 == 1

    with (out / "ledger.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["document_type"] == "rate_confirmation"

    records = list((out / "records").glob("*.json"))
    assert len(records) == 1


def test_never_invents_missing_fields(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "out"
    samples.mkdir()
    _make_pdf(samples / "sparse_invoice.pdf", ["INVOICE", "Invoice Number: INV-1"])

    new_rows, _ = run(samples, out)
    row = new_rows[0]
    assert row["amount"] in (None, "")
    assert "amount" in row["missing_fields"].split(";")
    assert row["review_status"] == "needs_review"


def test_adding_a_new_file_only_processes_the_new_one(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "out"
    samples.mkdir()
    _make_pdf(samples / "rc.pdf", ["RATE CONFIRMATION", "Load #: LD-1", "Agreed Rate: $1.00"])

    run(samples, out)

    _make_pdf(samples / "bol.pdf", ["BILL OF LADING", "BOL #: BOL-1"])
    new_rows, skipped = run(samples, out)

    assert len(new_rows) == 1
    assert skipped == 1
    assert new_rows[0]["document_type"] == "bol"


def test_txt_files_are_processed(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "out"
    samples.mkdir()
    (samples / "notice.txt").write_text(
        "INVOICE\nInvoice Number: INV-9\nRemit To: Someone\nAmount Due: $75.00\n",
        encoding="utf-8",
    )

    new_rows, _ = run(samples, out)
    assert len(new_rows) == 1
    assert new_rows[0]["document_type"] == "invoice"
    assert new_rows[0]["amount"] == "75.00"


def test_naics_lookup_is_tagged_on_solicitation_docs(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "out"
    samples.mkdir()
    (samples / "rfq.txt").write_text(
        "REQUEST FOR QUOTE (RFQ)\n"
        "The Sample Agency invites you to submit a quote for daily mail courier service.\n",
        encoding="utf-8",
    )

    new_rows, _ = run(samples, out)
    row = new_rows[0]
    assert row["document_type"] == "solicitation"
    assert row["naics_lookup_code"] == "492110"
    assert float(row["naics_lookup_confidence"]) > 0


def test_naics_lookup_is_empty_when_nothing_matches(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "out"
    samples.mkdir()
    (samples / "rfq.txt").write_text(
        "REQUEST FOR QUOTE (RFQ)\n"
        "The Sample Agency invites you to submit a quote for office plant watering services.\n",
        encoding="utf-8",
    )

    new_rows, _ = run(samples, out)
    row = new_rows[0]
    assert row["document_type"] == "solicitation"
    assert row["naics_lookup_code"] in (None, "")
    assert float(row["naics_lookup_confidence"]) == 0.0
