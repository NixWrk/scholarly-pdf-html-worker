"""Repair ambiguous same-document fragment targets after PDF HTML polish."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as html_escape
from html import unescape
import re
import urllib.parse

from .html_links import attr_value


@dataclass(frozen=True)
class DuplicateFragmentTargetRepair:
    html: str
    duplicate_target_count: int
    renamed_target_count: int
    rewritten_reference_count: int


@dataclass(frozen=True)
class BrokenLocalFragmentLinkRepair:
    html: str
    unwrapped_link_count: int


@dataclass(frozen=True)
class _HtmlTagToken:
    start: int
    name: str
    text: str
    chunk_key: str | None


@dataclass(frozen=True)
class _FragmentTargetOccurrence:
    index: int
    target: str
    position: int
    chunk_key: str | None
    value_spans: tuple[tuple[int, int], ...]


_HTML_TAG_TOKEN_RE = re.compile(
    r"<(?P<closing>/)?(?P<tag>[A-Za-z][\w:.-]*)"
    r"(?P<body>(?:[^'\">]|\"[^\"]*\"|'[^']*')*)>",
    re.DOTALL,
)
_ID_VALUE_RE = re.compile(
    r"(?<![\w:-])id\s*=\s*(['\"])(?P<value>.*?)\1",
    re.IGNORECASE | re.DOTALL,
)
_NAME_VALUE_RE = re.compile(
    r"(?<![\w:-])name\s*=\s*(['\"])(?P<value>.*?)\1",
    re.IGNORECASE | re.DOTALL,
)
_LOCAL_FRAGMENT_REFERENCE_RE = re.compile(
    r"(?P<prefix>(?<![\w:-])(?:href|xlink:href|usemap)\s*=\s*)"
    r"(?P<quote>['\"])(?P<value>#.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_INTERNAL_ANCHOR_RE = re.compile(
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>['\"])#(?P<target>[^'\"]+)(?P=quote)[^>]*)>"
    r"(?P<body>[\s\S]*?)</a\s*>",
    re.IGNORECASE,
)
_IDREF_VALUE_RE = re.compile(
    r"(?P<prefix>(?<![\w:-])(?:for|headers|list|form|itemref|"
    r"aria-activedescendant|aria-controls|aria-describedby|aria-details|"
    r"aria-errormessage|aria-flowto|aria-labelledby|aria-owns)\s*=\s*)"
    r"(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_CSS_FRAGMENT_URL_RE = re.compile(
    r"url\(\s*(?P<quote>['\"]?)#(?P<value>[^)'\"\s]+)(?P=quote)\s*\)",
    re.IGNORECASE,
)
_URL_FRAGMENT_SAFE = "!$&'()*+,;=:@/?-._~"


def repair_duplicate_fragment_targets(html: str) -> DuplicateFragmentTargetRepair:
    """Make repeated fragment targets unique and retarget local references.

    Chunked Marker documents preserve their source ranges on outer ``section``
    elements. References therefore prefer a target in the same range; when a
    range still contains repeated targets, the nearest occurrence wins.
    """

    tags = _html_tag_tokens(html)
    occurrences: list[_FragmentTargetOccurrence] = []
    occurrences_by_target: dict[str, list[_FragmentTargetOccurrence]] = {}
    for tag in tags:
        grouped_spans: dict[str, list[tuple[int, int]]] = {}
        for match in _ID_VALUE_RE.finditer(tag.text):
            target = unescape(match.group("value"))
            if target:
                grouped_spans.setdefault(target, []).append(
                    (tag.start + match.start("value"), tag.start + match.end("value"))
                )
        if tag.name in {"a", "map"}:
            for match in _NAME_VALUE_RE.finditer(tag.text):
                target = unescape(match.group("value"))
                if target:
                    grouped_spans.setdefault(target, []).append(
                        (tag.start + match.start("value"), tag.start + match.end("value"))
                    )
        for target, spans in grouped_spans.items():
            occurrence = _FragmentTargetOccurrence(
                index=len(occurrences),
                target=target,
                position=tag.start,
                chunk_key=tag.chunk_key,
                value_spans=tuple(spans),
            )
            occurrences.append(occurrence)
            occurrences_by_target.setdefault(target, []).append(occurrence)

    duplicated = {
        target: target_occurrences
        for target, target_occurrences in occurrences_by_target.items()
        if len(target_occurrences) > 1
    }
    if not duplicated:
        return DuplicateFragmentTargetRepair(
            html=html,
            duplicate_target_count=0,
            renamed_target_count=0,
            rewritten_reference_count=0,
        )

    used_targets = set(occurrences_by_target)
    assigned_targets: dict[int, str] = {}
    renamed_target_count = 0
    replacements: dict[tuple[int, int], str] = {}
    for target, target_occurrences in duplicated.items():
        for ordinal, occurrence in enumerate(target_occurrences, start=1):
            if ordinal == 1:
                assigned = target
            else:
                suffix = occurrence.chunk_key or f"d{ordinal}"
                assigned = _unique_fragment_target(
                    f"{target}--z2m-{suffix}",
                    used=used_targets,
                )
                renamed_target_count += 1
                escaped = html_escape(assigned, quote=True)
                for span in occurrence.value_spans:
                    replacements[span] = escaped
            assigned_targets[occurrence.index] = assigned

    rewritten_reference_count = 0
    for tag in tags:
        for match in _LOCAL_FRAGMENT_REFERENCE_RE.finditer(tag.text):
            raw_value = unescape(match.group("value"))
            target = urllib.parse.unquote(raw_value[1:])
            candidates = duplicated.get(target)
            if not candidates:
                continue
            selected = _nearest_fragment_target(
                candidates,
                position=tag.start,
                chunk_key=tag.chunk_key,
            )
            assigned = assigned_targets[selected.index]
            if assigned == target:
                continue
            span = (
                tag.start + match.start("value"),
                tag.start + match.end("value"),
            )
            encoded = urllib.parse.quote(assigned, safe=_URL_FRAGMENT_SAFE)
            replacements[span] = html_escape(f"#{encoded}", quote=True)
            rewritten_reference_count += 1

        for match in _IDREF_VALUE_RE.finditer(tag.text):
            tokens = unescape(match.group("value")).split()
            rewritten_tokens: list[str] = []
            changed = False
            for target in tokens:
                candidates = duplicated.get(target)
                if not candidates:
                    rewritten_tokens.append(target)
                    continue
                selected = _nearest_fragment_target(
                    candidates,
                    position=tag.start,
                    chunk_key=tag.chunk_key,
                )
                assigned = assigned_targets[selected.index]
                rewritten_tokens.append(assigned)
                changed = changed or assigned != target
            if not changed:
                continue
            span = (
                tag.start + match.start("value"),
                tag.start + match.end("value"),
            )
            replacements[span] = html_escape(" ".join(rewritten_tokens), quote=True)
            rewritten_reference_count += 1

        for match in _CSS_FRAGMENT_URL_RE.finditer(tag.text):
            target = urllib.parse.unquote(unescape(match.group("value")))
            candidates = duplicated.get(target)
            if not candidates:
                continue
            selected = _nearest_fragment_target(
                candidates,
                position=tag.start,
                chunk_key=tag.chunk_key,
            )
            assigned = assigned_targets[selected.index]
            if assigned == target:
                continue
            span = (
                tag.start + match.start("value"),
                tag.start + match.end("value"),
            )
            encoded = urllib.parse.quote(assigned, safe=_URL_FRAGMENT_SAFE)
            replacements[span] = html_escape(encoded, quote=True)
            rewritten_reference_count += 1

    return DuplicateFragmentTargetRepair(
        html=_replace_html_spans(html, replacements),
        duplicate_target_count=len(duplicated),
        renamed_target_count=renamed_target_count,
        rewritten_reference_count=rewritten_reference_count,
    )


def unwrap_broken_local_fragment_links(html: str) -> BrokenLocalFragmentLinkRepair:
    """Unwrap local anchors whose destination is absent from the final document."""

    if 'href="#' not in html and "href='#" not in html:
        return BrokenLocalFragmentLinkRepair(html=html, unwrapped_link_count=0)

    targets: set[str] = set()
    for tag in _html_tag_tokens(html):
        for match in _ID_VALUE_RE.finditer(tag.text):
            target = unescape(match.group("value"))
            if target:
                targets.add(target)
        if tag.name in {"a", "map"}:
            for match in _NAME_VALUE_RE.finditer(tag.text):
                target = unescape(match.group("value"))
                if target:
                    targets.add(target)

    unwrapped = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal unwrapped
        target = urllib.parse.unquote(unescape(match.group("target")))
        if target in targets:
            return match.group(0)
        unwrapped += 1
        return match.group("body")

    repaired = _INTERNAL_ANCHOR_RE.sub(replace, html)
    return BrokenLocalFragmentLinkRepair(
        html=repaired,
        unwrapped_link_count=unwrapped,
    )


def _html_tag_tokens(html: str) -> list[_HtmlTagToken]:
    tokens: list[_HtmlTagToken] = []
    section_stack: list[str | None] = []
    raw_text_tag: str | None = None
    for match in _HTML_TAG_TOKEN_RE.finditer(html):
        name = match.group("tag").lower()
        closing = bool(match.group("closing"))
        if raw_text_tag is not None:
            if closing and name == raw_text_tag:
                raw_text_tag = None
            continue
        if closing:
            if name == "section" and section_stack:
                section_stack.pop()
            continue

        text = match.group(0)
        self_closing = match.group("body").rstrip().endswith("/")
        chunk_key = section_stack[-1] if section_stack else None
        if name == "section":
            declared_chunk = _declared_chunk_key(text)
            if declared_chunk is not None:
                chunk_key = declared_chunk
            section_stack.append(chunk_key)
        tokens.append(
            _HtmlTagToken(
                start=match.start(),
                name=name,
                text=text,
                chunk_key=chunk_key,
            )
        )
        if name in {"script", "style"} and not self_closing:
            raw_text_tag = name
        if name == "section" and self_closing:
            section_stack.pop()
    return tokens


def _declared_chunk_key(tag: str) -> str | None:
    chunk = attr_value(tag, "data-zotero-worker-chunk")
    if not chunk:
        return None
    pages = attr_value(tag, "data-pages")
    raw = f"p{pages}" if pages else f"c{chunk}"
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-.")
    return (normalized or "chunk")[:64]


def _unique_fragment_target(base: str, *, used: set[str]) -> str:
    candidate = base
    ordinal = 2
    while candidate in used:
        candidate = f"{base}-{ordinal}"
        ordinal += 1
    used.add(candidate)
    return candidate


def _nearest_fragment_target(
    candidates: list[_FragmentTargetOccurrence],
    *,
    position: int,
    chunk_key: str | None,
) -> _FragmentTargetOccurrence:
    same_chunk = (
        [candidate for candidate in candidates if candidate.chunk_key == chunk_key]
        if chunk_key is not None
        else []
    )
    scoped = same_chunk or candidates
    return min(
        scoped,
        key=lambda candidate: (
            abs(candidate.position - position),
            0 if candidate.position >= position else 1,
            candidate.position,
        ),
    )


def _replace_html_spans(
    html: str,
    replacements: dict[tuple[int, int], str],
) -> str:
    result = html
    next_start = len(html) + 1
    for (start, end), value in sorted(
        replacements.items(),
        key=lambda item: item[0][0],
        reverse=True,
    ):
        if start < 0 or end < start or end > len(html) or end > next_start:
            raise ValueError("Overlapping or invalid HTML fragment replacement span.")
        result = result[:start] + value + result[end:]
        next_start = start
    return result
