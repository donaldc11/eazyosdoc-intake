"""Rule-based document classifier. Transparent keyword scoring rather than a
black-box model, so a reviewer can see exactly why a document got its label."""

from typing import Dict, Tuple

STRONG_WEIGHT = 3
WEAK_WEIGHT = 1

DOC_TYPE_SIGNALS = {
    "rate_confirmation": {
        "strong": ["rate confirmation", "carrier rate confirmation"],
        "weak": ["agreed rate", "confirmation #", "confirmation number", "dispatcher"],
    },
    "bol": {
        "strong": ["bill of lading", "straight bill of lading"],
        "weak": ["bol #", "bol number", "freight charges", "carrier signature"],
    },
    "pod": {
        "strong": ["proof of delivery"],
        "weak": ["received in good condition", "delivered by", "signature on file", "pod #"],
    },
    "invoice": {
        "strong": ["invoice number", "remit to"],
        "weak": ["amount due", "bill to", "payment terms", "invoice date"],
    },
    "solicitation": {
        "strong": ["request for quote", "invitation for bid", "small business quote"],
        "weak": [
            "solicitation", "bidder", "contracting opportunity", "submit a quote",
            "submit quotes", "rfq", "sbq", "ifb", "invites you to submit",
        ],
    },
}


def classify(text: str) -> Tuple[str, float, Dict[str, int]]:
    """Returns (document_type, confidence, raw_scores). document_type is
    "unknown" when no signal phrases are found — never guessed."""
    lowered = text.lower()
    scores: Dict[str, int] = {}
    for doc_type, signals in DOC_TYPE_SIGNALS.items():
        score = 0
        for phrase in signals["strong"]:
            if phrase in lowered:
                score += STRONG_WEIGHT
        for phrase in signals["weak"]:
            if phrase in lowered:
                score += WEAK_WEIGHT
        scores[doc_type] = score

    total = sum(scores.values())
    if total == 0:
        return "unknown", 0.0, scores

    best_type = max(scores, key=scores.get)
    confidence = round(scores[best_type] / total, 3)
    return best_type, confidence, scores
