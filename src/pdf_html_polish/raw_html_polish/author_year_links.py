"""Author-year citation link cleanup helpers."""

from __future__ import annotations

import html as html_lib
import re
from collections.abc import Callable
from typing import Any

from ..author_year_patterns import (
    AUTHOR_NAME_TOKEN,
    AUTHOR_YEAR_CITATION_PATTERN,
    AUTHOR_YEAR_SUFFIX_TOKEN,
)
from .html_fragments import visible_text
from .references_links import (
    AUTHOR_YEAR_CITATION_TEXT_PATTERN,
    LI_BLOCK_PATTERN,
    LI_ID_PATTERN,
    PAGE_ANCHOR_PATTERN,
    P_BLOCK_PATTERN,
    REF_ANCHOR_PATTERN,
    references_heading_search,
    replace_href_and_link_class,
)


PdfAnnotationLabelKeys = Callable[[Any | None], set[str]]
NormalizePdfAnnotationLabel = Callable[[str], str]


PROTECTED_AUTHOR_YEAR_LINKIFY_PATTERN = re.compile(
    r"<a\b[\s\S]*?</a>|<script\b[\s\S]*?</script>|<style\b[\s\S]*?</style>|"
    r"<math\b[\s\S]*?</math>|<[^>]+>",
    re.IGNORECASE,
)
PLAIN_AUTHOR_YEAR_CITATION_PATTERN = AUTHOR_YEAR_CITATION_PATTERN


def _default_pdf_annotation_reference_label_keys(
    citation_profile: Any | None,
) -> set[str]:
    return set()


def _default_normalize_pdf_annotation_label(value: str) -> str:
    return re.sub(r"\s+", " ", visible_text(value)).strip(" \t\r\n.,;:")


def author_year_label_tokens_and_year(label: str) -> tuple[list[str], str]:
    text = html_lib.unescape(visible_text(label))
    year_match = re.search(rf"\b{AUTHOR_YEAR_SUFFIX_TOKEN}\b", text, re.IGNORECASE)
    year = year_match.group(0).casefold() if year_match is not None else ""
    text = re.sub(rf"\b{AUTHOR_YEAR_SUFFIX_TOKEN}\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(?:et\s+al\.?|\u0438\s+\u0434\u0440\.?)", " ", text, flags=re.IGNORECASE
    )
    text = re.sub(r"[\(\)\[\],.;:]+|&", " ", text)
    tokens = [
        token.casefold().strip(".")
        for token in re.findall(AUTHOR_NAME_TOKEN, text)
        if token.casefold().strip(".")
        not in {"and", "et", "al", "\u0438", "\u0434\u0440"}
        and len(token.strip(". ")) > 1
    ]
    return list(dict.fromkeys(tokens)), year


def reference_text_matches_author_year(
    ref_text: str, name_tokens: list[str], year: str
) -> bool:
    if not name_tokens or not year:
        return False
    ref_lower = html_lib.unescape(ref_text).casefold()
    ref_years = {
        found.casefold()
        for found in re.findall(
            rf"\b{AUTHOR_YEAR_SUFFIX_TOKEN}\b", ref_text, re.IGNORECASE
        )
    }
    if year.casefold() not in ref_years:
        return False
    for token in name_tokens:
        if (
            re.search(
                rf"(?<![a-z\u00c0-\u00ff\u0430-\u044f\u0451]){re.escape(token)}(?![a-z\u00c0-\u00ff\u0430-\u044f\u0451])",
                ref_lower,
                re.IGNORECASE,
            )
            is None
        ):
            return False
    return True


def reference_text_by_number(html: str) -> dict[int, str]:
    references: dict[int, str] = {}
    for li_match in LI_BLOCK_PATTERN.finditer(html):
        attrs = li_match.group(1) or ""
        id_match = LI_ID_PATTERN.search(attrs)
        if id_match is None:
            continue
        references[int(id_match.group(2))] = visible_text(li_match.group(2))
    for paragraph_match in P_BLOCK_PATTERN.finditer(html):
        open_tag = paragraph_match.group("open") or ""
        id_match = LI_ID_PATTERN.search(open_tag)
        if id_match is None:
            continue
        references[int(id_match.group(2))] = visible_text(paragraph_match.group("body"))
    return references


def link_plain_author_year_citations(html: str) -> str:
    """Link plain author-year citation labels to matching bibliography targets."""
    if "ref-" not in html:
        return html
    reference_texts = reference_text_by_number(html)
    if not reference_texts:
        return html
    references_heading = references_heading_search(html, allow_notes_heading=True)
    if references_heading is None:
        return html

    body_html = html[: references_heading.start()]
    references_html = html[references_heading.start() :]

    def matching_target(label: str) -> int | None:
        tokens, year = author_year_label_tokens_and_year(label)
        matches = [
            target
            for target, ref_text in reference_texts.items()
            if reference_text_matches_author_year(ref_text, tokens, year)
        ]
        return matches[0] if len(matches) == 1 else None

    def replace_text_segment(segment: str) -> str:
        def replace(match: re.Match[str]) -> str:
            label = match.group(0)
            target = matching_target(label)
            if target is None:
                return label
            return f'<a href="#ref-{target}" class="z2m-ref-link">{label}</a>'

        return PLAIN_AUTHOR_YEAR_CITATION_PATTERN.sub(replace, segment)

    parts = PROTECTED_AUTHOR_YEAR_LINKIFY_PATTERN.split(body_html)
    separators = PROTECTED_AUTHOR_YEAR_LINKIFY_PATTERN.findall(body_html)
    rebuilt: list[str] = []
    for index, part in enumerate(parts):
        rebuilt.append(replace_text_segment(part))
        if index < len(separators):
            rebuilt.append(separators[index])
    return "".join(rebuilt) + references_html


def unwrap_author_year_ref_links(
    html: str,
    citation_profile: Any | None = None,
    *,
    pdf_annotation_reference_label_keys: PdfAnnotationLabelKeys | None = None,
    normalize_pdf_annotation_label: NormalizePdfAnnotationLabel | None = None,
) -> str:
    """Remove low-confidence numeric ref links from author-year citation text."""
    if "#ref-" not in html:
        return html

    pdf_annotation_reference_label_keys = (
        pdf_annotation_reference_label_keys
        or _default_pdf_annotation_reference_label_keys
    )
    normalize_pdf_annotation_label = (
        normalize_pdf_annotation_label or _default_normalize_pdf_annotation_label
    )
    pdf_annotation_labels = pdf_annotation_reference_label_keys(citation_profile)

    year_continuation_pattern = re.compile(
        r"^\s*\(?\d{4}[a-z]?\)?[\),.;:]*\s*$",
        re.IGNORECASE,
    )
    author_tail_pattern = re.compile(
        r"(?:\(|;|,|\bby\s+)?\s*"
        r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
        r"(?:\s+(?:et\s+al\.?|and|&)\s+"
        r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
        r"|\s+et\s+al\.?)?"
        r"(?:,|\.)?\s*$",
        re.IGNORECASE,
    )

    def is_author_year_continuation(label: str, left_text: str) -> bool:
        if year_continuation_pattern.fullmatch(label) is None:
            return False
        label_for_pattern = re.sub(
            r"(\d{4}[a-z]?)[\),.;:]+$",
            r"\1",
            label.strip(),
            flags=re.IGNORECASE,
        )
        if AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(
            f"{left_text[-180:]} {label_for_pattern}"
        ):
            return True
        return author_tail_pattern.search(left_text[-140:]) is not None

    def normalized_year_label(label: str) -> str:
        match = re.search(r"\d{4}[a-z]?", label, re.IGNORECASE)
        return match.group(0).casefold() if match else ""

    def right_hand_year_label(right_text: str) -> str:
        right_text = html_lib.unescape(right_text)
        name_token = (
            r"(?:[A-Z]\.\s*)?"
            r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
        )
        match = re.match(
            rf"^\s*(?:(?:\(|,|;|\band\b|\bet\s+al\.?)\s*)?"
            rf"(?:(?:&|\band\b)\s*{name_token}\s*)?"
            r"\(?\s*(\d{4}[a-z]?)\)?",
            right_text,
            re.IGNORECASE,
        )
        return match.group(1).casefold() if match else ""

    def looks_like_author_year_author_fragment(
        label: str, left_text: str, right_text: str
    ) -> bool:
        if not right_hand_year_label(right_text):
            return False
        cleaned = label.strip()
        if re.search(r"\d{4}", cleaned):
            return False
        name_token = (
            r"(?:[A-Z]\.\s*)?"
            r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
        )
        name_fragment = re.sub(
            r"\s+", " ", html_lib.unescape(cleaned.strip("([;, "))
        ).strip()
        if re.fullmatch(
            rf"{name_token}(?:\s+(?:et\s+al\.?|&\s*{name_token}|and\s+{name_token}))?",
            name_fragment,
            re.IGNORECASE,
        ):
            return True
        if re.fullmatch(rf"(?:&|and)\s*{name_token}", name_fragment, re.IGNORECASE):
            return (
                author_tail_pattern.search(html_lib.unescape(left_text)[-140:])
                is not None
            )
        if re.fullmatch(r"et\s+al\.?", name_fragment, re.IGNORECASE):
            return author_tail_pattern.search(left_text[-140:]) is not None
        return False

    reference_text_by_num = reference_text_by_number(html)

    year_labels_by_target: dict[int, set[str]] = {}
    for anchor_match in REF_ANCHOR_PATTERN.finditer(html):
        label = visible_text(anchor_match.group("body"))
        left_text = visible_text(
            html[max(0, anchor_match.start() - 180) : anchor_match.start()]
        )
        if not is_author_year_continuation(label, left_text):
            continue
        year = normalized_year_label(label)
        if not year:
            continue
        year_labels_by_target.setdefault(int(anchor_match.group("num")), set()).add(
            year
        )
    repeated_year_targets = {
        target for target, years in year_labels_by_target.items() if len(years) > 1
    }

    def target_ref_matches_author_year(
        target: int,
        label: str,
        left_text: str,
        right_text: str = "",
        *,
        require_reference_year: bool = False,
    ) -> bool:
        ref_text = reference_text_by_num.get(target, "")
        if not ref_text:
            if require_reference_year:
                return False
            return target not in repeated_year_targets
        ref_lower = ref_text.casefold()
        ref_years = {
            year.casefold()
            for year in re.findall(r"\b\d{4}[a-z]?\b", ref_text, re.IGNORECASE)
        }
        label_year = normalized_year_label(label) or right_hand_year_label(right_text)
        if not ref_years:
            if require_reference_year:
                return False
            return target not in repeated_year_targets
        if label_year and label_year not in ref_years:
            return False
        author_source = html_lib.unescape(f"{left_text[-160:]} {label}")
        author_match = author_tail_pattern.search(author_source[-220:])
        if author_match is None:
            if require_reference_year:
                return False
            return target not in repeated_year_targets
        author_tail = author_match.group(0)
        surnames = [
            surname.casefold()
            for surname in re.findall(
                r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+",
                author_tail,
            )
            if surname.casefold() not in {"et", "al", "and"}
            and len(surname.strip(". ")) > 1
        ]
        if not surnames:
            return target not in repeated_year_targets
        return any(surname in ref_lower for surname in surnames)

    def author_year_matching_ref_target(label: str, right_text: str) -> int | None:
        year = normalized_year_label(label) or right_hand_year_label(right_text)
        tokens, _ = author_year_label_tokens_and_year(label)
        if not year or not tokens:
            return None
        matches = [
            target
            for target, ref_text in reference_text_by_num.items()
            if reference_text_matches_author_year(ref_text, tokens, year)
        ]
        return matches[0] if len(matches) == 1 else None

    def replace(match: re.Match[str]) -> str:
        label = visible_text(match.group("body"))
        if normalize_pdf_annotation_label(label).casefold() in pdf_annotation_labels:
            return match.group(0)
        left_text = visible_text(html[max(0, match.start() - 180) : match.start()])
        right_text = visible_text(html[match.end() : match.end() + 140])
        is_year_continuation = is_author_year_continuation(label, left_text)
        if is_year_continuation and target_ref_matches_author_year(
            int(match.group("num")),
            label,
            left_text,
            right_text,
        ):
            return match.group(0)
        surname_fragment = (
            re.fullmatch(r"[A-Z][A-Za-z'вЂ™.-]{3,}", label) is not None
            and re.match(
                r"^\s*et\s+al\.?\s*\(?\d{4}[a-z]?\)?", right_text, re.IGNORECASE
            )
            is not None
        ) or looks_like_author_year_author_fragment(label, left_text, right_text)
        single_surname_et_al_fragment = (
            re.fullmatch(r"[A-Z][A-Za-z'\u2019.-]{3,}", label) is not None
            and re.match(
                r"^\s*et\s+al\.?\s*\(?\d{4}[a-z]?\)?", right_text, re.IGNORECASE
            )
            is not None
        )
        if single_surname_et_al_fragment:
            return match.group("body")
        if surname_fragment:
            matching_target = author_year_matching_ref_target(label, right_text)
            if matching_target is not None and matching_target != int(
                match.group("num")
            ):
                attrs = replace_href_and_link_class(
                    match.group("attrs"),
                    f"#ref-{matching_target}",
                    "z2m-ref-link",
                )
                return f"<a{attrs}>{match.group('body')}</a>"
        if surname_fragment and target_ref_matches_author_year(
            int(match.group("num")),
            label,
            left_text,
            right_text,
            require_reference_year=True,
        ):
            return match.group(0)
        if (
            AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(label) is None
            and not surname_fragment
            and not is_year_continuation
        ):
            return match.group(0)
        return match.group("body")

    return REF_ANCHOR_PATTERN.sub(replace, html)


def repair_roman_suffix_author_year_ref_link_splits(html: str) -> str:
    """Undo ref links that captured a surname-final roman-like suffix."""
    if "z2m-ref-link" not in html:
        return html

    pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+"
        r"<a\b(?=[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"])(?=[^>]*\bz2m-ref-link\b)[^>]*>"
        r"\s*(?P<suffix>vi|i|v)\s*</a>"
        r"(?=\s*<a\b(?=[^>]*\bhref\s*=\s*['\"]#ref-(?P=target)['\"])(?=[^>]*\bz2m-ref-link\b)[^>]*>"
        r"\s*\(?\d{4})",
        re.IGNORECASE,
    )
    blocked_roots = {
        "appendix",
        "figure",
        "section",
        "table",
    }

    def replace(match: re.Match[str]) -> str:
        root = match.group("root")
        if root.lower() in blocked_roots:
            return match.group(0)
        return f"{root}{match.group('suffix').lower()}"

    return pattern.sub(replace, html)


def unwrap_author_year_page_links(html: str) -> str:
    """Page anchors around author-year citations are stale PDF navigation, not citations."""
    if "#page-" not in html:
        return html

    name_token = (
        r"(?:[A-Z]\.\s*)?"
        r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
    )
    blocked_fragments = {
        "appendix",
        "chapter",
        "eq",
        "eqn",
        "equation",
        "fig",
        "figure",
        "method",
        "methods",
        "page",
        "pages",
        "pp",
        "results",
        "section",
        "table",
    }

    def looks_like_author_year_page_fragment(
        label: str, left_text: str, right_text: str
    ) -> bool:
        cleaned = re.sub(r"\s+", " ", html_lib.unescape(label).strip("([;, ")).strip()
        if not cleaned or re.search(r"\d{4}", cleaned):
            return False
        if cleaned.casefold().rstrip(".") in blocked_fragments:
            return False
        right_context = re.sub(r"\s+", " ", html_lib.unescape(right_text)).strip()
        if not right_context or re.match(
            r"^(?:of|for|in|to)\b", right_context, re.IGNORECASE
        ):
            return False
        split_et_al_continuation = (
            re.fullmatch(rf"{name_token}\s+et", cleaned, re.IGNORECASE) is not None
            and re.match(
                r"^al\.?\s*\(?\d{4}[a-z]?\)?",
                right_context,
                re.IGNORECASE,
            )
            is not None
        )
        split_surname_continuation = (
            re.fullmatch(r"\(?[A-Z][A-Za-z]{2,6}", cleaned) is not None
            and re.match(
                r"^[a-z]{1,10}\s+et\s+al\.?\s*\(?\d{4}[a-z]?\)?",
                right_context,
                re.IGNORECASE,
            )
            is not None
        )
        citation_context = (
            re.search(r"[\(;]\s*$", html_lib.unescape(left_text)) is not None
            or re.search(r"\bby\s*$", html_lib.unescape(left_text), re.IGNORECASE)
            is not None
            or label.lstrip().startswith("(")
            or right_context.startswith((",", ";", ")", "&"))
            or re.match(
                r"^(?:&|and|al\.?|et\s+al\.?|\(?\d{4})\b", right_context, re.IGNORECASE
            )
            is not None
            or split_et_al_continuation
            or split_surname_continuation
        )
        if not citation_context:
            return False
        candidate = re.sub(r"\s+", " ", f"{cleaned} {right_context[:120]}").strip()
        if AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(candidate):
            return True
        if split_et_al_continuation:
            return True
        if split_surname_continuation:
            return True
        return False

    def replace(match: re.Match[str]) -> str:
        label = visible_text(match.group("body"))
        label_for_pattern = re.sub(
            r"(\d{4}[a-z]?)[\),.;:]+$", r"\1", label.strip(), flags=re.IGNORECASE
        )
        if AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(label) is None:
            left_text = visible_text(html[max(0, match.start() - 180) : match.start()])
            right_text = visible_text(html[match.end() : match.end() + 80])
            if re.search(r"\d{4}", label) and AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(
                f"{left_text[-180:]} {label_for_pattern}"
            ):
                return match.group("body")
            flexible_year_continuation = re.search(
                r"\b[A-Z][A-Za-z'.-]+(?:\s+et\s+al\.?|\s*&\s*[A-Z][A-Za-z'.-]+)?"
                r"(?:,)?\s*(?:\d{4}[a-z]?\s*[,;]?\s*)?$",
                left_text,
            ) is not None and not re.match(
                r"^\s*(?:of|for|in|to)\b", right_text, re.IGNORECASE
            )
            year_continuation = (
                re.fullmatch(
                    r"\(?\d{4}[a-z]?\)?[\),.;:]*", label.strip(), re.IGNORECASE
                )
                is not None
                and re.search(
                    r"\b[A-Z][A-Za-z'РІР‚в„ў.-]+(?:\s+et\s+al\.?)?,\s*(?:\d{4}[a-z]?\s*,?\s*)?$",
                    left_text,
                )
                is not None
            )
            author_fragment_continuation = looks_like_author_year_page_fragment(
                label, left_text, right_text
            )
            if not (
                year_continuation
                or flexible_year_continuation
                or author_fragment_continuation
            ):
                return match.group(0)
        return match.group("body")

    return PAGE_ANCHOR_PATTERN.sub(replace, html)


def recover_trailing_citation_after_author_year_ref(html: str) -> str:
    """Recover flattened citation numbers after linked author-year fragments."""
    ref_numbers = {int(match.group(2)) for match in LI_ID_PATTERN.finditer(html)}
    if not ref_numbers or "#ref-" not in html:
        return html

    pattern = re.compile(
        r"(?P<anchor><a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>[\s\S]{0,120}?</a>)"
        r"(?P<gap>\s*)(?P<num>\d{1,3})(?P<trail>\s*\.)",
        re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        number = int(match.group("num"))
        if number not in ref_numbers:
            return match.group(0)
        anchor_text = visible_text(match.group("anchor"))
        if re.search(r"\b\d{4}[a-z]?\)?\s*$", anchor_text) is None:
            return match.group(0)
        return (
            f"{match.group('anchor')}<sup>"
            f'<a href="#ref-{number}" class="z2m-ref-link">{number}</a>'
            f"</sup>{match.group('trail').lstrip()}"
        )

    return pattern.sub(replace, html)
