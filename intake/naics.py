"""Static local NAICS code lookup for solicitation documents, scoped to the
codes Eazy Express actually bids: 484xxx trucking, 492xxx couriers, 488xxx
freight support, and 541xxx as a stretch bucket for logistics-adjacent
professional services. No external API calls — this is a fixed keyword
table matched against extracted document text."""

from typing import Dict, List, Optional, Tuple

NAICS_TABLE: Dict[str, List[str]] = {
    # 484xxx - General freight & specialized trucking
    "484110": ["local trucking", "local freight delivery", "intrastate trucking", "local hauling"],
    "484121": ["truckload", "full truckload", "ftl freight", "long-haul trucking", "over-the-road", "otr trucking"],
    "484122": ["less than truckload", "less-than-truckload", "ltl freight", "ltl shipping"],
    "484230": [
        "specialized freight", "flatbed trucking", "refrigerated trucking", "reefer trucking",
        "tanker trucking", "hazardous waste transport", "hazmat transport", "oversize load",
        "hazardous materials transportation",
    ],
    # 492xxx - Couriers & local delivery
    "492110": ["courier", "express delivery", "mail courier", "parcel delivery", "same-day delivery"],
    "492210": ["local messenger", "messenger service", "local delivery service"],
    # 488xxx - Support activities for transportation
    "488510": ["freight broker", "freight brokerage", "third-party logistics", "3pl services", "freight forwarding"],
    "488410": ["towing service", "tow truck"],
    "488999": ["non-hazardous waste pickup", "waste pickup", "loading dock", "freight elevator", "decommission"],
    # 541xxx - stretch bucket: logistics-adjacent professional services
    "541614": ["logistics consulting", "supply chain consulting", "distribution consulting", "process consulting"],
}


def lookup_naics(text: str) -> Tuple[Optional[str], float]:
    """Returns (naics_code, confidence): the table code whose keywords match
    most often in the text, and confidence as that code's share of all
    keyword hits found. Returns (None, 0.0) when nothing in the table
    matches — never guesses a code."""
    lowered = text.lower()
    scores = {code: sum(1 for phrase in phrases if phrase in lowered) for code, phrases in NAICS_TABLE.items()}
    total = sum(scores.values())
    if total == 0:
        return None, 0.0
    best_code = max(scores, key=scores.get)
    confidence = round(scores[best_code] / total, 3)
    return best_code, confidence
