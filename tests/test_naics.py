from intake.naics import lookup_naics


def test_matches_484xxx_trucking_bucket():
    text = "This solicitation is for specialized hazardous waste transport and flatbed trucking services."
    code, confidence = lookup_naics(text)
    assert code == "484230"
    assert confidence > 0


def test_matches_492xxx_courier_bucket():
    text = "The vendor shall provide daily mail courier service between two office locations."
    code, confidence = lookup_naics(text)
    assert code == "492110"
    assert confidence > 0


def test_matches_488xxx_freight_support_bucket():
    text = "Vendor to perform non-hazardous waste pickup, with access to the loading dock and freight elevator."
    code, confidence = lookup_naics(text)
    assert code == "488999"
    assert confidence > 0


def test_matches_541xxx_stretch_bucket():
    text = "The agency seeks a firm to provide logistics consulting and supply chain consulting services."
    code, confidence = lookup_naics(text)
    assert code == "541614"
    assert confidence > 0


def test_no_match_returns_none_and_zero_confidence():
    code, confidence = lookup_naics("Please find attached the quarterly budget report for review.")
    assert code is None
    assert confidence == 0.0
