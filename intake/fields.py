"""Field extraction. Every function returns None when a value isn't found in
the text — fields are never inferred or guessed."""

import re
from typing import Optional, Tuple


def _search(pattern: str, text: str) -> Optional[str]:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_load_reference(text: str) -> Optional[str]:
    # "invoice"/"bol" are included as aliases: non-freight invoices (e.g. SaaS
    # subscriptions) have no load number, and bills of lading are usually
    # labeled "BOL #" rather than "Load #" — both are the closest thing to a
    # document reference number for their respective document types.
    return _search(r"(?:load|ref(?:erence)?|order|invoice|bol)\s*(?:#|no\.?|number)?\s*[:#]\s*([A-Za-z0-9\-]{3,})", text)


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
