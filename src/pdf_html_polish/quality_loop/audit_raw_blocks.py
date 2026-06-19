from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any

from pdf_html_polish.html_stages import RAW_STAGE_NAME


BLOCK_TAGS = {
    "address",
    "blockquote",
    "caption",
    "dd",
    "div",
    "dt",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "p",
    "td",
    "th",
}
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class Block:
    index: int
    tag: str
    text: str
    has_img: bool
    line: int


@dataclass
class Defect:
    id: str
    check: str
    severity: str
    snippet: str
    line: int | None = None
    first_broken_stage: str = RAW_STAGE_NAME
    hypothesis: str = ""
    same_pattern_hits_across_corpus: int | None = None
    proposed_fix_layer: str = ""
    regression_test: str = ""
    status: str = "open"
    extra: dict[str, Any] = field(default_factory=dict)


class BlockParser(HTMLParser):
    """Tiny block extractor for Marker HTML that keeps image proximity."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self._current: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.lower()
        if tag in BLOCK_TAGS and self._current is None:
            self._current = {
                "tag": tag,
                "parts": [],
                "has_img": False,
                "line": self.getpos()[0],
            }
        if self._current is not None:
            if tag == "img":
                self._current["has_img"] = True
                self._current["parts"].append(" [IMG] ")
            elif tag in {"br", "hr"}:
                self._current["parts"].append(" ")

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._current is not None and tag == self._current["tag"]:
            self._finish_current()

    def close(self) -> None:
        super().close()
        if self._current is not None:
            self._finish_current()

    def _finish_current(self) -> None:
        current = self._current
        if current is None:
            return
        text = normalize_ws(" ".join(current["parts"]))
        self.blocks.append(
            Block(
                index=len(self.blocks),
                tag=current["tag"],
                text=text,
                has_img=bool(current["has_img"]),
                line=int(current["line"]),
            )
        )
        self._current = None


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_tags(fragment: str) -> str:
    return normalize_ws(unescape(TAG_RE.sub(" ", fragment)))


def line_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def snippet_at(text: str, start: int, end: int | None = None, *, width: int = 260) -> str:
    end = start if end is None else end
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    if line_end - line_start > width * 2:
        context_start = max(line_start, start - width // 2)
        context_end = min(line_end, end + width // 2)
        snippet = strip_tags(text[context_start:context_end])
        if context_start > line_start:
            snippet = "..." + snippet
        if context_end < line_end:
            snippet += "..."
    else:
        snippet = strip_tags(text[line_start:line_end])
    if len(snippet) <= width:
        return snippet
    return snippet[: width - 3].rstrip() + "..."


def first_match_defect(
    *,
    defect_id: str,
    check: str,
    severity: str,
    pattern: re.Pattern[str],
    text: str,
    hypothesis: str,
    proposed_fix_layer: str,
    regression_test: str,
    max_examples: int = 5,
) -> Defect | None:
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    first = matches[0]
    return Defect(
        id=defect_id,
        check=check,
        severity=severity,
        snippet=snippet_at(text, first.start(), first.end()),
        line=line_at(text, first.start()),
        hypothesis=hypothesis,
        proposed_fix_layer=proposed_fix_layer,
        regression_test=regression_test,
        extra={
            "count": len(matches),
            "examples": [
                snippet_at(text, match.start(), match.end(), width=180)
                for match in matches[:max_examples]
            ],
        },
    )


def read_utf8(path: Path) -> tuple[bytes, str, Defect | None]:
    data = path.read_bytes()
    if not data:
        return data, "", Defect(
            id="R01",
            check="File exists, is non-empty, UTF-8 readable",
            severity="error",
            snippet="empty file",
            line=None,
            hypothesis="The EN raw stage artifact was not written correctly.",
            proposed_fix_layer="pipeline stage artifact creation",
            regression_test="Run the EN raw audit over the same article after re-export.",
        )
    try:
        return data, data.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        text = data.decode("utf-8", errors="replace")
        return data, text, Defect(
            id="R01",
            check="File exists, is non-empty, UTF-8 readable",
            severity="error",
            snippet=str(exc),
            line=None,
            hypothesis="The EN raw artifact is not valid UTF-8.",
            proposed_fix_layer="Marker output capture or stage writer",
            regression_test="Run the EN raw audit and require UTF-8 decoding to pass.",
            extra={"decode_error": str(exc)},
        )


def parse_blocks(text: str) -> list[Block]:
    parser = BlockParser()
    parser.feed(text)
    parser.close()
    return parser.blocks
