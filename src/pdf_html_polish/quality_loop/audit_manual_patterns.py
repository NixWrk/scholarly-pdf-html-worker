from __future__ import annotations

import re

from pdf_html_polish.quality_loop.audit_blocks import Block, strip_tags


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
SPLIT_DOT_EMAIL_RE = re.compile(
    r"\b(?-i:[a-z]{2,})\.\s+[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|"
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\s*\.\s+|\s+\.\s*)[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
SPLIT_DOT_EMAIL_SENTENCE_WORDS = {
    "addressed",
    "author",
    "authors",
    "contact",
    "correspondence",
    "email",
}
REFERENCE_BOUNDARY_START_RE = re.compile(
    r"\b(?P<num>\d{1,4})\.\s+"
    r"(?P<name>[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]{1,40})"
)


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
    if polish_html.count("\ufffd") <= 3 and re.search(
        r"<t[dh]\b[^>]*>\s*[\d\s.,'\"*+\-:;()/\u2022]*\ufffd[\d\s.,'\"*+\-:;()/\u2022]*</t[dh]>",
        polish_html,
        re.IGNORECASE,
    ):
        numeric_cells = re.findall(
            r"<t[dh]\b[^>]*>\s*[\d\s.,'\"*+\-:;()/\u2022]{1,32}</t[dh]>",
            polish_html,
            re.IGNORECASE,
        )
        if len(numeric_cells) >= 12 or len(re.findall(r"\b\d\s+\d\s+\d\s+\d\b", pdf_text)) >= 4:
            return True
    return False


def joined_word_match_is_url_slug(text: str, match: re.Match[str]) -> bool:
    left = text[max(0, match.start() - 96) : match.start()]
    return bool(re.search(r"(?:https?://|www\.)[^\s<>()\[\]]*$", left, re.IGNORECASE))


def split_dot_email_is_sentence_boundary(match: re.Match[str]) -> bool:
    matched = match.group(0)
    dot_pos = matched.find(".")
    at_pos = matched.find("@")
    if dot_pos < 0 or (at_pos >= 0 and at_pos < dot_pos):
        return False
    leading_word = re.match(r"\b([A-Za-z]{2,})\.\s+", matched)
    return bool(leading_word and leading_word.group(1).lower() in SPLIT_DOT_EMAIL_SENTENCE_WORDS)


def find_split_dot_email_match(text: str) -> re.Match[str] | None:
    for match in SPLIT_DOT_EMAIL_RE.finditer(text):
        if not split_dot_email_is_sentence_boundary(match):
            return match
    return None


def bibliography_numbering_residue_is_clean_reference_boundary(polish_html: str, residue: str) -> bool:
    starts = [
        (int(match.group("num")), match.group("name"))
        for match in REFERENCE_BOUNDARY_START_RE.finditer(residue)
    ]
    if not starts:
        return False
    for number, name in starts:
        li_match = re.search(
            rf"<li\b(?=[^>]*\bid\s*=\s*['\"]ref-{number}['\"])[^>]*>"
            rf"(?P<body>[\s\S]{{0,1200}}?)</li>",
            polish_html,
            re.IGNORECASE,
        )
        if li_match is None:
            return False
        li_text = strip_tags(li_match.group("body"))
        if re.search(rf"\b{number}\.\s+{re.escape(name)}", li_text) is None:
            return False
    return True


def ends_like_sentence_fragment(text: str) -> bool:
    text = text.strip()
    if len(text) < 24 or re.search(r"[.!?:;\]\)]\s*$", text):
        return False
    match = re.search(r"([A-Za-z][A-Za-z-]*)\s*$", text)
    if match is None:
        return False
    word = match.group(1)
    return word.islower() or word.lower() in {
        "and",
        "or",
        "with",
        "of",
        "the",
        "to",
        "for",
        "than",
        "daytime",
        "post-operative",
        "pre-operative",
    }


def starts_like_sentence_continuation(text: str) -> bool:
    text = text.strip()
    return bool(re.match(r"^(?:[a-z]|\(?[a-z])", text))


def page_link_semantic_kind(html: str, match: re.Match[str]) -> str | None:
    label = strip_tags(match.group("body"))
    left = strip_tags(html[max(0, match.start() - 140) : match.start()])
    right = strip_tags(html[match.end() : match.end() + 140])
    left_tail = left[-80:]
    right_head = right[:80]
    context = f"{left_tail} {label} {right_head}"
    supplemental_media_re = re.compile(r"\b(?:Video|Movie|Audio|Dataset|Data|File|Text|Protocol|Supplement)\b", re.IGNORECASE)

    if re.fullmatch(r"\(?S\d+[A-Z]?\)?", label.strip(), re.IGNORECASE) and supplemental_media_re.match(
        right_head.strip()
    ):
        return None
    if supplemental_media_re.fullmatch(label.strip()) and re.search(r"\bS\d+[A-Z]?\s*$", left_tail, re.IGNORECASE):
        return None

    if re.search(r"\b(?:Box|Table|Tables|Fig\.?|Figure|Section|Appendix|Equation|Eq\.?)\s*$", left_tail, re.IGNORECASE):
        return "semantic-cross-reference"
    if re.match(r"^(?:Box|Table|Tables|Fig\.?|Figure|Section|Appendix|Equation|Eq\.?)\b", label, re.IGNORECASE):
        return "semantic-cross-reference"
    if re.match(r"^\(?S\d+", label, re.IGNORECASE) and re.match(r"^\s*Tables?\b", right_head, re.IGNORECASE):
        return "semantic-cross-reference"
    if re.search(r"\b(?:Table|Tables|Box|Section|Appendix|Figure|Fig\.?)\b", context, re.IGNORECASE) and re.search(
        r"\d|[A-Z]\.?", label
    ):
        return "semantic-cross-reference"
    if re.fullmatch(r"\[?\d{1,4}\]?[\].,;)]*", label):
        return "citation"
    if re.fullmatch(r"[a-z]\s*\d{1,4}(?:[\s,\-–\u2013\u2014\d.);]*)?", label):
        return "citation-ocr-glue"
    return None


def looks_like_affiliation_label_roman_boundary(block: Block, split_match: re.Match[str]) -> bool:
    if split_match.group("suffix").lower() != "i":
        return False
    text = block.text
    right_text = text[split_match.end() : split_match.end() + 90]
    if AFFILIATION_LABEL_RIGHT_RE.match(right_text) is None:
        return False
    classes = set(block.attrs.get("class", "").split())
    has_affiliation_context = (
        AFFILIATION_LABEL_CONTEXT_RE.search(text) is not None
        or "z2m-front-matter" in classes
    )
    left_text = text[: split_match.start()]
    location_boundary = (
        split_match.group("prefix").lower() in AFFILIATION_LABEL_LOCATION_PREFIXES
        and (has_affiliation_context or re.search(r"[,;]\s*$", left_text) is not None)
    )
    if location_boundary:
        return True
    if not has_affiliation_context:
        return False
    nearby_text = text[max(0, split_match.start() - 1200) : split_match.end() + 200]
    affiliation_label_count = len(re.findall(r"\b[a-z]\s+(?=[A-Z][A-Za-z])", nearby_text))
    return affiliation_label_count >= 4
