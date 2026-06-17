"""Shared HTML block parsing helpers for EN polish audit scripts."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any, Iterable


TAG_RE = re.compile(r"<[^>]+>")
BLOCK_RE = re.compile(
    r"<(?P<tag>p|h[1-6]|div|table|figure|figcaption|li|td|th)\b(?P<attrs>[^>]*)>"
    r"(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
OPEN_BLOCK_TAG_RE = re.compile(
    r"<(?P<tag>p|h[1-6]|div|table|figure|figcaption|li|td|th)\b(?P<attrs>[^>]*)>",
    re.IGNORECASE | re.DOTALL,
)
TABLE_CELL_RE = re.compile(
    r"<t[dh]\b[^>]*>(?P<body>.*?)</t[dh]>",
    re.IGNORECASE | re.DOTALL,
)
ATTR_RE = re.compile(
    r"(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*"
    r"(?:(?P<q>['\"])(?P<quoted>.*?)(?P=q)|(?P<bare>[^\s>]+))",
    re.DOTALL,
)
NESTED_REF_LIST_ITEM_RE = re.compile(r"<li\b[^>]*\bid\s*=\s*['\"]ref-\d+['\"]", re.IGNORECASE)
DATA_IMAGE_RE = re.compile(r"data:image/[^'\"]+", re.IGNORECASE)
REF_ID_RE = re.compile(r"^ref-(\d+)$", re.IGNORECASE)
MISSING_FIGURE_WARNING_BLOCK_RE = re.compile(
    r"<(?P<tag>p|div|figure|figcaption|li)\b"
    r"(?=[^>]*\bz2m-missing-figure-warning\b)(?P<attrs>[^>]*)>"
    r"(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class Block:
    index: int
    tag: str
    attrs: dict[str, str]
    raw: str
    text: str
    line: int

    @property
    def id(self) -> str:
        return self.attrs.get("id", "")

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    @property
    def block_type(self) -> str:
        return self.attrs.get("block-type", "")

    @property
    def has_img(self) -> bool:
        return bool(re.search(r"<img\b", self.raw, re.IGNORECASE))

    @property
    def has_figure_visual(self) -> bool:
        return self.has_img or bool(
            re.search(r"<table\b(?=[^>]*\bz2m-figure-target\b)", self.raw, re.IGNORECASE)
        )


@dataclass
class Defect:
    id: str
    cc_class: str
    check: str
    severity: str
    snippet: str
    line: int | None
    first_broken_stage: str
    hypothesis: str
    proposed_fix_layer: str
    regression_test: str
    status: str = "open"
    extra: dict[str, Any] = field(default_factory=dict)


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_tags(fragment: str) -> str:
    return normalize_ws(unescape(TAG_RE.sub(" ", fragment)))


def visible_ref_number_from_match(match: re.Match[str] | None) -> int | None:
    if match is None:
        return None
    value = match.group(1) or match.group(2)
    return int(value) if value is not None else None


class _UnitDiagnosticTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.skip_depth:
            self.skip_depth += 1
            return

        attr_map = {name.lower(): value or "" for name, value in attrs}
        classes = set(attr_map.get("class", "").split())
        if tag in {"script", "style"} or classes.intersection({"z2m-math", "katex", "katex-html"}):
            self.skip_depth = 1
            return
        self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if not self.skip_depth:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.skip_depth:
            self.skip_depth -= 1
            return
        self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        return normalize_ws(unescape(" ".join(self.parts)))


def unit_diagnostic_text_from_html(fragment: str) -> str:
    parser = _UnitDiagnosticTextParser()
    try:
        parser.feed(fragment)
        parser.close()
    except Exception:
        return strip_tags(fragment)
    return parser.text()


def line_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def line_starts(text: str) -> list[int]:
    return [0] + [match.end() for match in re.finditer(r"\n", text)]


def line_at_from_starts(starts: list[int], offset: int) -> int:
    return bisect_right(starts, offset)


def snippet(text: str, start: int = 0, end: int | None = None, *, width: int = 260) -> str:
    end = start if end is None else end
    left = max(0, start - width // 2)
    right = min(len(text), end + width // 2)
    result = strip_tags(text[left:right])
    if left > 0:
        result = "..." + result
    if right < len(text):
        result += "..."
    if len(result) <= width:
        return result
    return result[: width - 3].rstrip() + "..."


def attrs(attr_text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in ATTR_RE.finditer(attr_text):
        value = match.group("quoted") if match.group("quoted") is not None else match.group("bare")
        result[match.group("name").lower()] = unescape(value or "")
    return result


def parse_blocks(html: str) -> list[Block]:
    blocks: list[Block] = []
    starts = line_starts(html)
    for match in BLOCK_RE.finditer(html):
        raw = match.group(0)
        blocks.append(
            Block(
                index=len(blocks),
                tag=match.group("tag").lower(),
                attrs=attrs(match.group("attrs")),
                raw=raw,
                text=strip_tags(raw),
                line=line_at_from_starts(starts, match.start()),
            )
        )
    return blocks


def parse_overlapping_blocks(html: str) -> list[Block]:
    blocks: list[Block] = []
    lower_html = html.lower()
    starts = line_starts(html)
    for match in OPEN_BLOCK_TAG_RE.finditer(html):
        tag = match.group("tag").lower()
        close_token = f"</{tag}>"
        close_start = lower_html.find(close_token, match.end())
        if close_start == -1:
            continue
        close_end = close_start + len(close_token)
        raw = html[match.start() : close_end]
        blocks.append(
            Block(
                index=len(blocks),
                tag=tag,
                attrs=attrs(match.group("attrs")),
                raw=raw,
                text=strip_tags(raw),
                line=line_at_from_starts(starts, match.start()),
            )
        )
    return blocks


def reference_identity_blocks(html: str) -> list[Block]:
    blocks: list[Block] = []
    seen_raw: set[str] = set()
    for block in parse_blocks(html):
        if block.tag in {"p", "div"} and not REF_ID_RE.match(block.id) and NESTED_REF_LIST_ITEM_RE.search(block.raw):
            continue
        blocks.append(block)
        seen_raw.add(block.raw)

    for block in parse_overlapping_blocks(html):
        if block.tag != "li" or not REF_ID_RE.match(block.id) or block.raw in seen_raw:
            continue
        block.attrs["data-z2m-audit-nested-ref-item"] = "1"
        blocks.append(block)
        seen_raw.add(block.raw)
    return blocks


def missing_figure_warning_blocks(html: str) -> list[Block]:
    blocks: list[Block] = []
    starts = line_starts(html)
    for match in MISSING_FIGURE_WARNING_BLOCK_RE.finditer(html):
        block_attrs = attrs(match.group("attrs"))
        if "z2m-missing-figure-warning" not in set(block_attrs.get("class", "").split()):
            continue
        raw = match.group(0)
        blocks.append(
            Block(
                index=len(blocks),
                tag=match.group("tag").lower(),
                attrs=block_attrs,
                raw=raw,
                text=strip_tags(raw),
                line=line_at_from_starts(starts, match.start()),
            )
        )
    return blocks


def plain_text(html: str) -> str:
    return strip_tags(html)


def structure_html(html: str) -> str:
    return DATA_IMAGE_RE.sub("data:image/...", html)


def unit_diagnostic_texts(block: Block) -> list[str]:
    cells = [unit_diagnostic_text_from_html(match.group("body")) for match in TABLE_CELL_RE.finditer(block.raw)]
    if cells:
        return cells
    return [unit_diagnostic_text_from_html(block.raw)]


def diagnostic_text(text: str) -> str:
    text = unescape(TAG_RE.sub(" ", text))
    text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def diagnostic_word_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", diagnostic_text(text)).strip()


def diagnostic_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", diagnostic_word_text(text))


def word_sequence_match(text: str, words: Iterable[str], *, start: int = 0) -> re.Match[str] | None:
    words = list(words)
    if not words:
        return None
    pattern = re.compile(r"\b" + r"\s+".join(re.escape(word) for word in words) + r"\b")
    return pattern.search(text, pos=start)
