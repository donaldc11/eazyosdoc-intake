from intake.classify import classify


def test_rate_confirmation_detected():
    text = "RATE CONFIRMATION\nConfirmation Number: RC-1\nAgreed Rate: $100.00\nDispatcher: A"
    doc_type, confidence, _ = classify(text)
    assert doc_type == "rate_confirmation"
    assert confidence > 0


def test_bol_detected():
    text = "STRAIGHT BILL OF LADING\nBOL #: BOL-1\nFreight Charges: Prepaid"
    doc_type, confidence, _ = classify(text)
    assert doc_type == "bol"
    assert confidence > 0


def test_pod_detected():
    text = "PROOF OF DELIVERY\nReceived in good condition.\nSignature on file."
    doc_type, _, _ = classify(text)
    assert doc_type == "pod"


def test_invoice_detected():
    text = "INVOICE\nInvoice Number: INV-1\nRemit To: Someone\nAmount Due: $10.00"
    doc_type, _, _ = classify(text)
    assert doc_type == "invoice"


def test_solicitation_detected_rfq_style():
    text = (
        "Request for Quote (RFQ)\n"
        "The Agricultural Labor Relations Board (ALRB) invites you to submit a quote by 07/16/2026.\n"
        "Bidder Declaration attached.\n"
    )
    doc_type, confidence, _ = classify(text)
    assert doc_type == "solicitation"
    assert confidence > 0


def test_solicitation_detected_sbq_style():
    text = (
        "SMALL BUSINESS QUOTE (SBQ) REQUEST\n"
        "This is a Small Business/DVBE only solicitation.\n"
        "Bidders shall complete, sign, and return all forms.\n"
    )
    doc_type, _, _ = classify(text)
    assert doc_type == "solicitation"


def test_unrelated_text_is_unknown():
    doc_type, confidence, scores = classify("Just a random paragraph about nothing relevant at all.")
    assert doc_type == "unknown"
    assert confidence == 0.0
    assert all(score == 0 for score in scores.values())


def test_empty_text_is_unknown():
    doc_type, confidence, _ = classify("")
    assert doc_type == "unknown"
    assert confidence == 0.0
