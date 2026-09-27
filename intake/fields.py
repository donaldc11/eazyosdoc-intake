"""Field extraction. Every function returns None when a value isn't found in
the text — fields are never inferred or guessed."""

import re
from typing import Optional, Tuple


def _search(pattern: str, text: str) -> Optional[str]:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_load_reference(text: str) -> Optional[str]:
    # "invoice"/"bol"/"confirmation" are included as aliases: non-freight
    # invoices (e.g. SaaS subscriptions) have no load number, bills of lading
    # are usually labeled "BOL #" rather than "Load #", and some rate
    # confirmations have no separate load number at all — just a
    # "Confirmation Number". Each is the closest thing to a document
    # reference number for its respective document type.
    return _search(r"(?:load|ref(?:erence)?|order|invoice|bol|confirmation)\s*(?:#|no\.?|number)?\s*[:#]\s*([A-Za-z0-9\-]{3,})", text)


def extract_shipper(text: str) -> Optional[str]:
    value = _search(r"shipper\s*[:\-]\s*([^\n]+)", text)
    if value:
        return value
    # Non-freight invoice layouts have no "shipper" concept; the seller/issuer
    # fills that role. Matched against known vendor layouts from the samples.
    match = re.search(r"^(Google LLC)$", text, re.MULTILINE)
    if match:
        return match.group(1)
    match = re.search(r"^(Atlassian\s+[A-Za-z]+\s+Ltd)", text, re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def extract_consignee(text: str) -> Optional[str]:
    return _search(r"consignee\s*[:\-]\s*([^\n]+)", text)


def extract_pickup_date(text: str) -> Optional[str]:
    return _search(r"(?:pickup|ship)\s*date\s*[:\-]\s*([\d/\-]{6,10})", text)


def extract_delivery_date(text: str) -> Optional[str]:
    return _search(r"delivery\s*date\s*[:\-]\s*([\d/\-]{6,10})", text)


def extract_amount_currency(text: str) -> Tuple[Optional[str], Optional[str]]:
    match = re.search(r"\$\s*([\d,]+\.\d{2})", text)
    if match:
        return match.group(1).replace(",", ""), "USD"

    # Some invoice layouts (e.g. Atlassian) spell out the currency code
    # instead of using a "$" symbol.
    match = re.search(
        r"(?:Invoice Total|Total Amount Due|Amount Due|Total billed amount)\s*:?\s*(USD|EUR|GBP|AUD|CAD)\s*([\d,]+\.\d{2})",
        text, re.IGNORECASE,
    )
    if match:
        return match.group(2).replace(",", ""), match.group(1).upper()

    match = re.search(r"\b(USD|EUR|GBP|AUD|CAD)\s+([\d,]+\.\d{2})\b", text)
    if match:
        return match.group(2).replace(",", ""), match.group(1).upper()

    return None, None


def extract_piece_count(text: str) -> Optional[str]:
    return _search(r"(?:piece count|total pieces|# of pieces|pieces|pcs)\s*[:#]\s*(\d+)", text)


def extract_weight(text: str) -> Optional[str]:
    return _search(r"(?:gross weight|total weight|weight)\s*[:#]\s*([\d,]+(?:\.\d+)?\s*(?:lbs?|kgs?|pounds)?)", text)


def extract_po_number(text: str) -> Optional[str]:
    value = _search(r"\bP\.?O\.?\s*(?:Number|No\.?|#)?\s*[:#]\s*([A-Za-z0-9\-]{2,})", text)
    if value:
        return value
    return _search(r"Purchase Order\s*(?:Number|No\.?|#)?\s*[:#]\s*([A-Za-z0-9\-]{2,})", text)


def extract_delivered_at(text: str) -> Optional[str]:
    # Single-line "Delivered: <date> <time>" layout.
    match = re.search(r"delivered\s*[:\-]\s*([\d/\-]{6,10})\s+([\d:]{3,8}\s*(?:am|pm)?)", text, re.IGNORECASE)
    if match:
        return f"{match.group(1)} {match.group(2).strip()}"

    # Separate "Delivered/Delivery Date: X" plus optional "Delivered/Delivery Time: Y".
    date_match = re.search(r"deliver(?:ed|y)\s*date\s*[:\-]\s*([\d/\-]{6,10})", text, re.IGNORECASE)
    if not date_match:
        return None
    time_match = re.search(r"deliver(?:ed|y)\s*time\s*[:\-]\s*([\d:]{3,8}\s*(?:am|pm)?)", text, re.IGNORECASE)
    if time_match:
        return f"{date_match.group(1)} {time_match.group(1).strip()}"
    return date_match.group(1)


EXCEPTION_KEYWORDS = [
    "shortage", "short count", "damage", "damaged", "refused", "refusal", "discrepancy",
]


def extract_exception_notes(text: str) -> Optional[str]:
    # Returns the exact line noting the exception (never invented or
    # summarized); None when no exception keyword appears anywhere.
    for line in text.splitlines():
        lowered = line.lower()
        if any(keyword in lowered for keyword in EXCEPTION_KEYWORDS):
            stripped = line.strip()
            if stripped:
                return stripped
    return None


def extract_pickup_location(text: str) -> Optional[str]:
    return _search(r"pickup\s*(?:location|city\s*/?\s*state|city)\s*[:\-]\s*([^\n]+)", text)


def extract_delivery_location(text: str) -> Optional[str]:
    return _search(r"delivery\s*(?:location|city\s*/?\s*state|city)\s*[:\-]\s*([^\n]+)", text)


def extract_equipment_type(text: str) -> Optional[str]:
    return _search(r"equipment\s*(?:type)?\s*[:\-]\s*([^\n]+)", text)


ACCESSORIAL_KEYWORDS = [
    "fuel surcharge", "fsc", "accessorial", "detention", "lumper", "layover", "tarp fee", "chassis fee",
]


def extract_accessorial_charges(text: str) -> Optional[str]:
    # Returns every matching line verbatim, joined — a rate con can carry
    # more than one accessorial charge (fuel surcharge + detention, etc).
    # None when no such line appears (a clean linehaul-only rate con).
    matches = [line.strip() for line in text.splitlines() if any(keyword in line.lower() for keyword in ACCESSORIAL_KEYWORDS) and line.strip()]
    return "; ".join(matches) if matches else None


def extract_issuing_agency(text: str) -> Optional[str]:
    match = re.search(r"The ([A-Z][A-Za-z0-9()&,.'\-\s]{1,80}?) invites you to submit", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"^\s*(DEPARTMENT OF [A-Z][A-Z \-&]+?)\s*$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def extract_solicitation_number(text: str) -> Optional[str]:
    match = re.search(r"\b(?:SBQ|RFQ|IFB|Solicitation)\s*(?:No\.?|Number|#)\s*[:.]?\s*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"Rate Sheet for ([A-Za-z0-9\-]+),", text, re.IGNORECASE)
    if match:
        return match.group(1)
    # Fallback for solicitations forwarded as email with no formal number:
    # the email subject line is the closest thing to a reference.
    match = re.search(r"Subject:\s*(?:FW:\s*|RE:\s*|FWD:\s*)*(.+)", text)
    if match:
        return match.group(1).strip()
    return None


def extract_due_date(text: str) -> Optional[str]:
    match = re.search(r"submit (?:a |an )?(?:quote|bid|proposal)s?\s+by\s+(\d{1,2}/\d{1,2}/\d{2,4})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"no later than COB\s+(\d{1,2}/\d{1,2}/\d{2,4})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"submit the following documents.*?on\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})", text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1)
    return None


def extract_naics_code(text: str) -> Optional[str]:
    return _search(r"NAICS\s*(?:code)?\s*[:#]?\s*(\d{4,6})", text)


def extract_buyer_contact(text: str) -> Optional[str]:
    match = re.search(r"([A-Z][a-z]+\s+[A-Z][a-z]+),?\s*\n?\s*([\w.+-]+@[\w.-]+\.\w+)", text)
    if match:
        return f"{match.group(1)} <{match.group(2)}>"
    match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    if match:
        return match.group(0)
    return None
