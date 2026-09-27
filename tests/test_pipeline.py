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


def test_bol_with_all_fields_is_ok(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "out"
    samples.mkdir()
    _make_pdf(samples / "bol_full.pdf", [
        "STRAIGHT BILL OF LADING",
        "BOL #: BOL-77410",
        "Shipper: Coastal Steel Supply",
        "Consignee: Highline Construction",
        "PO Number: PO-44210",
        "Piece Count: 24",
        "Weight: 42,500 lbs",
    ])

    new_rows, _ = run(samples, out)
    row = new_rows[0]
    assert row["document_type"] == "bol"
    assert row["load_reference_number"] == "BOL-77410"
    assert row["piece_count"] == "24"
    assert row["weight"] == "42,500 lbs"
    assert row["po_number"] == "PO-44210"
    assert row["review_status"] == "ok"


def test_bol_missing_po_number_is_still_ok(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "out"
    samples.mkdir()
    _make_pdf(samples / "bol_no_po.pdf", [
        "STRAIGHT BILL OF LADING",
        "BOL #: BOL-77500",
        "Shipper: Riverside Lumber Co",
        "Consignee: Delta Builders Supply",
        "Piece Count: 8",
        "Weight: 6,100 lbs",
    ])

    new_rows, _ = run(samples, out)
    row = new_rows[0]
    assert row["document_type"] == "bol"
    assert row["po_number"] in (None, "")
    assert "po_number" not in row["missing_fields"].split(";")
    assert row["review_status"] == "ok"


def test_bol_missing_required_field_needs_review(tmp_path):
    samples = tmp_path / "samples"
    out = tmp_path / "out"
    samples.mkdir()
    _make_pdf(samples / "bol_sparse.pdf", [
        "STRAIGHT BILL OF LADING",
        "BOL #: BOL-77600",
    ])

    new_rows, _ = run(samples, out)
    row = new_rows[0]
    assert row["document_type"] == "bol"
    assert row["review_status"] == "needs_review"
    assert "piece_count" in row["missing_fields"].split(";")
    assert "weight" in row["missing_fields"].split(";")


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
