#!/usr/bin/env python3
"""Generates synthetic sample documents (rate confirmation, BOL, POD, invoice,
an unrelated memo, and one scanned-style image) into ./samples so the intake
pipeline has something realistic to run against. These are fabricated
documents for prototype testing only — not real shipments or invoices.
"""

from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SAMPLES_DIR = Path(__file__).parent / "samples"

DOCS = {
    "rate_confirmation_1001.pdf": [
        "ACME FREIGHT BROKERAGE",
        "RATE CONFIRMATION",
        "Confirmation Number: RC-88213",
        "Load #: LD-55210",
        "Shipper: Sunrise Produce Co, Fresno CA",
        "Consignee: Metro Grocers Distribution, Dallas TX",
        "Pickup Location: Fresno, CA",
        "Pickup Date: 10/02/2026",
        "Delivery Location: Dallas, TX",
        "Delivery Date: 10/04/2026",
        "Equipment Type: 53' Dry Van",
        "Linehaul Rate: $2,450.00",
        "Fuel Surcharge: $180.00",
        "Detention: $75.00",
        "Dispatcher: J. Alvarez",
    ],
    # No fuel surcharge/accessorial lines, and no separate "Load #" — the
    # confirmation number stands in as the reference. Exercises both the
    # "accessorials are optional" path and the confirmation-number alias.
    "rate_confirmation_no_accessorials_1002.pdf": [
        "BLUE OX BROKERAGE",
        "RATE CONFIRMATION",
        "Confirmation Number: RC-90042",
        "Shipper: Golden Valley Produce, Bakersfield CA",
        "Consignee: Pacific Fresh Foods, Seattle WA",
        "Pickup Location: Bakersfield, CA",
        "Pickup Date: 10/10/2026",
        "Delivery Location: Seattle, WA",
        "Delivery Date: 10/13/2026",
        "Equipment Type: Reefer",
        "Linehaul Rate: $3,900.00",
        "Dispatcher: M. Chen",
    ],
    "bol_2002.pdf": [
        "STRAIGHT BILL OF LADING",
        "BOL #: BOL-77410",
        "Shipper: Coastal Steel Supply, Long Beach CA",
        "Consignee: Highline Construction, Phoenix AZ",
        "Pickup Date: 09/28/2026",
        "Delivery Date: 09/30/2026",
        "PO Number: PO-44210",
        "Piece Count: 24",
        "Weight: 42,500 lbs",
        "Freight Charges: Prepaid",
        "Carrier Signature: on file",
    ],
    # Deliberately missing PO number to exercise the "PO is optional" path —
    # a BOL with no customer PO reference should still come back "ok".
    "bol_no_po_2003.pdf": [
        "STRAIGHT BILL OF LADING",
        "BOL #: BOL-77500",
        "Shipper: Riverside Lumber Co, Sacramento CA",
        "Consignee: Delta Builders Supply, Stockton CA",
        "Pickup Date: 10/01/2026",
        "Delivery Date: 10/02/2026",
        "Piece Count: 8",
        "Weight: 6,100 lbs",
        "Freight Charges: Collect",
    ],
    "pod_3003.pdf": [
        "PROOF OF DELIVERY",
        "POD #: POD-91827",
        "Load #: LD-55210",
        "Consignee: Metro Grocers Distribution, Dallas TX",
        "Delivered Date: 10/04/2026",
        "Delivered Time: 2:32 PM",
        "Piece Count: 18",
        "Received in good condition.",
        "Signature on file.",
    ],
    # Exercises the exception-notes path: shortage/damage noted at delivery.
    "pod_exception_3004.pdf": [
        "PROOF OF DELIVERY",
        "POD #: POD-91850",
        "BOL #: BOL-77410",
        "Consignee: Highline Construction, Phoenix AZ",
        "Delivered Date: 10/02/2026",
        "Delivered Time: 9:15 AM",
        "Piece Count: 22",
        "Exception: 2 pieces damaged in transit, consignee noted shortage of 1 piece.",
        "Signature on file.",
    ],
    "invoice_4004.pdf": [
        "EAZY EXPRESS LOGISTICS LLC",
        "INVOICE",
        "Invoice Number: INV-10045",
        "Invoice Date: 10/05/2026",
        "Bill To: Metro Grocers Distribution",
        "Load #: LD-55210",
        "Amount Due: $2,450.00",
        "Payment Terms: Net 30",
        "Remit To: Eazy Express Logistics LLC, PO Box 100, Miami FL",
    ],
    # Deliberately sparse/ambiguous invoice to exercise the low-confidence /
    # missing-fields review path.
    "invoice_partial_4005.pdf": [
        "INVOICE",
        "Invoice Number: INV-10099",
    ],
    "misc_memo_5005.pdf": [
        "INTERNAL MEMO",
        "To: All Dispatch Staff",
        "Re: Office closed for holiday on 11/27/2026",
        "Please plan load coverage accordingly.",
    ],
}


def make_pdf(path: Path, lines):
    c = canvas.Canvas(str(path), pagesize=letter)
    _, height = letter
    y = height - 72
    for line in lines:
        c.drawString(72, y, line)
        y -= 18
    c.save()


def make_scanned_pod_image(path: Path):
    """A rendered (not photographed) image to exercise the image-input path.
    OCR requires the tesseract binary; see README for the review-flagging
    behavior when it isn't installed."""
    img = Image.new("RGB", (900, 400), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "PROOF OF DELIVERY (SCANNED)",
        "POD #: POD-91900",
        "Load #: LD-66330",
        "Consignee: Gulfstream Retail Center, Tampa FL",
        "Delivery Date: 10/06/2026",
        "Received in good condition. Driver signature on file.",
    ]
    y = 30
    for line in lines:
        draw.text((30, y), line, fill="black")
        y += 40
    img.save(path)


def main():
    SAMPLES_DIR.mkdir(exist_ok=True)
    for filename, lines in DOCS.items():
        make_pdf(SAMPLES_DIR / filename, lines)
    make_scanned_pod_image(SAMPLES_DIR / "scanned_pod_6006.png")
    print(f"Generated {len(DOCS) + 1} synthetic sample documents in {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
