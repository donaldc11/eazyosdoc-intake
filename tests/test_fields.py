from intake import fields as fx


def test_extracts_present_fields():
    text = (
        "Load #: LD-1\n"
        "Shipper: Test Shipper Co\n"
        "Consignee: Test Consignee Co\n"
        "Pickup Date: 01/01/2026\n"
        "Delivery Date: 01/02/2026\n"
        "Agreed Rate: $500.00\n"
    )
    assert fx.extract_load_reference(text) == "LD-1"
    assert fx.extract_shipper(text) == "Test Shipper Co"
    assert fx.extract_consignee(text) == "Test Consignee Co"
    assert fx.extract_pickup_date(text) == "01/01/2026"
    assert fx.extract_delivery_date(text) == "01/02/2026"
    amount, currency = fx.extract_amount_currency(text)
    assert amount == "500.00"
    assert currency == "USD"


def test_never_invents_absent_fields():
    text = "INVOICE\nInvoice Number: INV-1\n"
    assert fx.extract_shipper(text) is None
    assert fx.extract_consignee(text) is None
    assert fx.extract_pickup_date(text) is None
    assert fx.extract_delivery_date(text) is None
    amount, currency = fx.extract_amount_currency(text)
    assert amount is None
    assert currency is None


def test_google_invoice_layout():
    text = (
        "Invoice\n"
        "Invoice number: 5671505596\n"
        "$1.62\n"
        "Google Workspace\n"
        "Total in USD\n"
        "$1.62\n"
        "Google LLC\n"
        "1600 Amphitheatre Pkwy\n"
        "Bill to\n"
        "Christopher Donaldson\n"
    )
    assert fx.extract_load_reference(text) == "5671505596"
    assert fx.extract_shipper(text) == "Google LLC"
    amount, currency = fx.extract_amount_currency(text)
    assert amount == "1.62"
    assert currency == "USD"


def test_atlassian_invoice_layout():
    text = (
        "Atlassian Pty Ltd, \n"
        "Level 6, 341 George St,\n"
        "Invoice number:   IN-008-125-304\n"
        "RECEIPT\n"
        "Invoice Total: USD 0.00\n"
        "Payment due: USD 0.00\n"
    )
    assert fx.extract_load_reference(text) == "IN-008-125-304"
    assert fx.extract_shipper(text) == "Atlassian Pty Ltd"
    amount, currency = fx.extract_amount_currency(text)
    assert amount == "0.00"
    assert currency == "USD"


def test_solicitation_fields_rfq_style():
    text = (
        "Subject: FW: ALRB RFQ - HQ Decommission - Round 2\n"
        "Request for Quote (RFQ)\n"
        "The Agricultural Labor Relations Board (ALRB) invites you to submit a quote by 07/16/2026 for:\n"
        "no later than COB 07/16/2026.\n"
        "Office: (916) 894-6706\n"
    )
    assert fx.extract_issuing_agency(text) == "Agricultural Labor Relations Board (ALRB)"
    assert fx.extract_due_date(text) == "07/16/2026"
    assert fx.extract_naics_code(text) is None


def test_solicitation_fields_sbq_style():
    text = (
        "SBQ No. 132288\n"
        "SMALL BUSINESS QUOTE (SBQ) REQUEST\n"
        "The EDD invites you to submit a quote for the services specified.\n"
        "Jason.Bartz@edd.ca.gov\n"
    )
    assert fx.extract_issuing_agency(text) == "EDD"
    assert fx.extract_solicitation_number(text) == "132288"
    assert fx.extract_buyer_contact(text) == "Jason.Bartz@edd.ca.gov"


def test_solicitation_fields_letter_style_due_date_and_contact():
    text = (
        "DEPARTMENT OF FORESTRY AND FIRE PROTECTION \n"
        "Rate Sheet for 7CA07875, Hazardous Waste Removal Services\n"
        "please submit the following documents \n"
        "attached by email to my attention, Irina Lopatin, irina.lopatin@fire.ca.gov; "
        "by 5:00 p.m. on June 29, 2026.\n"
    )
    assert fx.extract_issuing_agency(text) == "DEPARTMENT OF FORESTRY AND FIRE PROTECTION"
    assert fx.extract_solicitation_number(text) == "7CA07875"
    assert fx.extract_due_date(text) == "June 29, 2026"
    assert fx.extract_buyer_contact(text) == "Irina Lopatin <irina.lopatin@fire.ca.gov>"
