from __future__ import annotations

import re

from zoteropdf2md.quality_loop.audit_blocks import Block


AFFILIATION_LABEL_CONTEXT_RE = re.compile(r"\b(?:ARTICLE INFO|Keywords?|Received|Accepted)\b", re.IGNORECASE)
AFFILIATION_LABEL_RIGHT_RE = re.compile(
    r"\s+(?:Clinical|College|Department|Division|Faculty|Hospital|Institute|Laboratory|Lab|McGill|"
    r"Monash|National|Public|Research|School|Section|Unit|University)\b"
)
AFFILIATION_LABEL_LOCATION_PREFIXES = {
    "argentina",
    "australia",
    "austria",
    "belgium",
    "brazil",
    "canada",
    "china",
    "denmark",
    "england",
    "finland",
    "france",
    "germany",
    "hungary",
    "india",
    "ireland",
    "italy",
    "japan",
    "netherlands",
    "norway",
    "portugal",
    "spain",
    "sweden",
    "switzerland",
}


def replacement_chars_are_pdf_source_noise(polish_html: str, pdf_text: str) -> bool:
    if "\ufffd" not in polish_html or not pdf_text:
        return False
    if "dynes\ufffdsec\ufffdcm-5" in polish_html and "dynes\x01sec\x01cm-5" in pdf_text:
        return True
    if "FRIMODT-M\ufffdLLER" in polish_html and "FRIMODT-M\u0258LLER" in pdf_text:
        return True
    if polish_html.count("\ufffd") >= 50 and (
        "\u00ad" in pdf_text
        or "FRIMODT-M\u0258LLER" in pdf_text
        or len(re.findall(r"\b\d\s+\d\s+\d\s+\d\b", pdf_text)) >= 8
    ):
        return True
    return False


def looks_like_affiliation_label_roman_boundary(block: Block, split_match: re.Match[str]) -> bool:
    if split_match.group("suffix").lower() != "i":
        return False
    text = block.text
    if AFFILIATION_LABEL_CONTEXT_RE.search(text) is None:
        classes = set(block.attrs.get("class", "").split())
        if "z2m-front-matter" not in classes:
            return False
    right_text = text[split_match.end() : split_match.end() + 90]
    if AFFILIATION_LABEL_RIGHT_RE.match(right_text) is None:
        return False
    if split_match.group("prefix").lower() in AFFILIATION_LABEL_LOCATION_PREFIXES:
        return True
    nearby_text = text[max(0, split_match.start() - 1200) : split_match.end() + 200]
    affiliation_label_count = len(re.findall(r"\b[a-z]\s+(?=[A-Z][A-Za-z])", nearby_text))
    return affiliation_label_count >= 4
