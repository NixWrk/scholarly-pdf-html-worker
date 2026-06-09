#!/usr/bin/env python
"""Audit `01.en.raw.html` stage artifacts without running the pipeline."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.html_stages import RAW_STAGE_NAME, article_name_from_html_stage  # noqa: E402


STAGE_NAME = RAW_STAGE_NAME
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
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
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

TAG_RE = re.compile(r"<[^>]+>")
HTML_TAG_RE = re.compile(r"<html(?:\s|>)", re.IGNORECASE)
BODY_TAG_RE = re.compile(r"<body(?:\s|>)", re.IGNORECASE)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
IMG_SRC_RE = re.compile(
    r"<img\b[^>]*\bsrc\s*=\s*(?:(?P<quote>['\"])(?P<quoted>.*?)(?P=quote)|(?P<bare>[^\s>]+))",
    re.IGNORECASE | re.DOTALL,
)
FIGURE_LABEL_RE = re.compile(r"\b(?:FIGURE|Figure|Fig\.)\s+\d+[A-Za-z]?\b")
FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:FIGURE\s+\d+\s*\||Figure\s+\d+\s*[.:]|Fig\.\s+\d+\s*\.)",
    re.IGNORECASE,
)
TABLE_LABEL_RE = re.compile(r"\b(?:TABLE|Table)\s+(?:[IVXLCDM]+|\d+)\b")
PAGE_HEADER_RE = re.compile(r"\bPage\s+\d+\s+of\s+\d+\b", re.IGNORECASE)
RAW_SENTINEL_RE = re.compile(r"@@Z2M|<z2m\b|Z2M(?:_[ATF])?", re.IGNORECASE)
ESCAPED_ANCHOR_RE = re.compile(r"&lt;\s*/?\s*a(?:\s|&gt;|>)", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s<>'\"]+", re.IGNORECASE)
DUPLICATED_DOI_FRAGMENT_RE = re.compile(
    r"\b(10\.\d{4,9}/[^\s<>'\"]+)\s+\1\b",
    re.IGNORECASE,
)
BROKEN_HYPHEN_RE = re.compile(r"\b[A-Za-z]{2,}-\s+[a-z]{2,}\b")
GLUED_ROMAN_SUFFIX_RE = re.compile(
    r"\b[A-Za-z]{4,}(?:ii|iii|iv|vi|vii|viii|xii|xiii|xiv|xv|ingv)\b",
    re.IGNORECASE,
)
REFERENCES_RE = re.compile(
    r"\b(?:references|bibliography|works cited|literature cited)\b",
    re.IGNORECASE,
)

MICRO_CHARS = "\u00b5\u03bc"
MOJIBAKE_MICRO = "\u0412\u00b5"
MICRO_TOKEN_RE = re.compile(rf"(?:[{MICRO_CHARS}]|{MOJIBAKE_MICRO})")
FORMULA_UNIT_FRAGMENT_RE = re.compile(
    rf"(?:\d+\s*(?:[{MICRO_CHARS}]|{MOJIBAKE_MICRO})\s*m\b|"
    rf"(?:[{MICRO_CHARS}]|{MOJIBAKE_MICRO})\s+m\b|"
    rf"\bm\s+(?:[{MICRO_CHARS}]|{MOJIBAKE_MICRO})\b)",
    re.IGNORECASE,
)


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
    first_broken_stage: str = STAGE_NAME
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
        text = _normalize_ws(" ".join(current["parts"]))
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


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_tags(fragment: str) -> str:
    return _normalize_ws(unescape(TAG_RE.sub(" ", fragment)))


def _line_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _snippet_at(text: str, start: int, end: int | None = None, *, width: int = 260) -> str:
    end = start if end is None else end
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    if line_end - line_start > width * 2:
        context_start = max(line_start, start - width // 2)
        context_end = min(line_end, end + width // 2)
        snippet = _strip_tags(text[context_start:context_end])
        if context_start > line_start:
            snippet = "..." + snippet
        if context_end < line_end:
            snippet += "..."
    else:
        snippet = _strip_tags(text[line_start:line_end])
    if len(snippet) <= width:
        return snippet
    return snippet[: width - 3].rstrip() + "..."


def _first_match_defect(
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
        snippet=_snippet_at(text, first.start(), first.end()),
        line=_line_at(text, first.start()),
        hypothesis=hypothesis,
        proposed_fix_layer=proposed_fix_layer,
        regression_test=regression_test,
        extra={
            "count": len(matches),
            "examples": [
                _snippet_at(text, match.start(), match.end(), width=180)
                for match in matches[:max_examples]
            ],
        },
    )


def _read_utf8(path: Path) -> tuple[bytes, str, Defect | None]:
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


def _parse_blocks(text: str) -> list[Block]:
    parser = BlockParser()
    parser.feed(text)
    parser.close()
    return parser.blocks


def _image_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in IMG_SRC_RE.finditer(text):
        refs.append(match.group("quoted") or match.group("bare") or "")
    return refs


def _sidecar_images(article_dir: Path, stage_dir: Path) -> set[Path]:
    images: set[Path] = set()
    for base in {article_dir, stage_dir}:
        if not base.exists():
            continue
        for child in base.iterdir():
            if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                images.add(child.resolve(strict=False))
    return images


def _resolve_image_ref(src: str, article_dir: Path, stage_dir: Path) -> tuple[str, Path | None]:
    parsed = urlsplit(src)
    if parsed.scheme in {"http", "https", "data"}:
        return parsed.scheme, None
    clean = unquote(parsed.path).replace("\\", "/")
    candidates = [stage_dir / clean, article_dir / clean]
    for candidate in candidates:
        if candidate.exists():
            return "local", candidate.resolve(strict=False)
    return "missing", (article_dir / clean).resolve(strict=False)


def _image_summary(path: Path, text: str) -> tuple[dict[str, Any], Defect | None]:
    stage_dir = path.parent
    article_dir = stage_dir.parent
    refs = _image_refs(text)
    local_resolved: set[Path] = set()
    remote_refs = 0
    data_refs = 0
    missing: list[str] = []

    for src in refs:
        kind, resolved = _resolve_image_ref(src, article_dir, stage_dir)
        if kind == "local" and resolved is not None:
            local_resolved.add(resolved)
        elif kind == "data":
            data_refs += 1
        elif kind in {"http", "https"}:
            remote_refs += 1
        else:
            missing.append(src)

    sidecars = _sidecar_images(article_dir, stage_dir)
    unused = sorted(str(path) for path in sidecars.difference(local_resolved))
    summary = {
        "img_tags": len(IMG_TAG_RE.findall(text)),
        "image_srcs": len(refs),
        "local_sidecar_files": len(sidecars),
        "local_refs_resolved": len(local_resolved),
        "remote_refs": remote_refs,
        "data_uri_refs": data_refs,
        "missing_refs": missing[:20],
        "unused_sidecars": unused[:20],
    }
    if missing:
        return summary, Defect(
            id="R03",
            check="Count <img> tags and sidecar image files",
            severity="error",
            snippet=missing[0],
            line=None,
            hypothesis="Marker referenced an image that is not present beside the article or stage artifact.",
            proposed_fix_layer="Marker image extraction or staging",
            regression_test="Audit image refs and sidecars for the full EN raw control corpus.",
            extra={"missing_refs": missing[:20], "missing_count": len(missing)},
        )
    return summary, None


def _major_tag_defects(text: str) -> list[Defect]:
    defects: list[Defect] = []
    checks = [
        ("html", HTML_TAG_RE, re.compile(r"</html\s*>", re.IGNORECASE)),
        ("body", BODY_TAG_RE, re.compile(r"</body\s*>", re.IGNORECASE)),
    ]
    for tag, open_re, close_re in checks:
        opens = len(open_re.findall(text))
        closes = len(close_re.findall(text))
        if opens == 0 or closes == 0 or opens != closes:
            defects.append(
                Defect(
                    id="R02",
                    check="HTML has <html>, <body>, balanced major closing tags",
                    severity="error",
                    snippet=f"{tag}: open={opens}, close={closes}",
                    hypothesis="Marker emitted malformed HTML or the stage artifact was truncated.",
                    proposed_fix_layer="Marker output capture or raw-stage validation",
                    regression_test="Audit R02 over all canonical EN raw artifacts.",
                    extra={"tag": tag, "open": opens, "close": closes},
                )
            )
    return defects


def _caption_without_image_defects(blocks: list[Block], *, window: int = 3) -> list[Defect]:
    defects: list[Defect] = []
    for block in blocks:
        if not FIGURE_CAPTION_RE.search(block.text):
            continue
        start = max(0, block.index - window)
        stop = min(len(blocks), block.index + window + 1)
        if any(neighbor.has_img for neighbor in blocks[start:stop]):
            continue
        defects.append(
            Defect(
                id="R05",
                check="Figure label has nearby image before/after within a small block window",
                severity="warning",
                snippet=block.text[:260],
                line=block.line,
                hypothesis="A figure caption exists, but Marker did not keep a nearby figure image in the raw HTML.",
                proposed_fix_layer="classify as Marker/PDF extraction defect unless a documented fallback is added",
                regression_test="Audit caption-to-image proximity for all canonical EN raw artifacts.",
                extra={"block_index": block.index, "window": window},
            )
        )
    return defects


def _heading_ocr_defects(blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    for index, block in enumerate(blocks):
        if block.tag not in HEADING_TAGS:
            continue
        next_block = blocks[index + 1] if index + 1 < len(blocks) else None
        if next_block is None or not FIGURE_CAPTION_RE.search(next_block.text):
            continue
        letters = re.findall(r"[A-Za-z]", block.text)
        uppercase = [char for char in letters if char.isupper()]
        uppercase_ratio = (len(uppercase) / len(letters)) if letters else 0.0
        has_panel_terms = bool(
            re.search(
                r"\b(?:electrode|array|substrate|mask|etching|thickness|stimulating|recording)\b",
                block.text,
                re.IGNORECASE,
            )
        )
        suspicious = (
            len(block.text) > 120 and has_panel_terms
        ) or (
            len(block.text) > 80 and uppercase_ratio > 0.45 and has_panel_terms
        )
        if suspicious:
            defects.append(
                Defect(
                    id="R06",
                    check="Detect OCR-only figure panels in headings",
                    severity="warning",
                    snippet=block.text[:260],
                    line=block.line,
                    hypothesis="Marker converted figure panel text into a document heading.",
                    proposed_fix_layer="classify as Marker/PDF extraction defect; optionally add downstream fallback policy",
                    regression_test="Audit suspicious heading OCR leakage across the canonical EN raw corpus.",
                    extra={
                        "tag": block.tag,
                        "block_index": block.index,
                        "uppercase_ratio": round(uppercase_ratio, 3),
                    },
                )
            )
    return defects


def _all_caps_heading_defects(blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    for block in blocks:
        if block.tag not in HEADING_TAGS or len(block.text) < 40:
            continue
        letters = re.findall(r"[A-Za-z]", block.text)
        if not letters:
            continue
        uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
        if uppercase_ratio < 0.75:
            continue
        if not re.search(r"\b(?:Figure|FIGURE|Table|TABLE|[A-Z]{4,})\b", block.text):
            continue
        defects.append(
            Defect(
                id="R13",
                check="Detect suspicious all-caps figure/table text inside headings",
                severity="warning",
                snippet=block.text[:260],
                line=block.line,
                hypothesis="A figure or table panel was promoted to a heading in EN raw.",
                proposed_fix_layer="Marker/PDF extraction classification or EN polish fallback after corpus review",
                regression_test="Audit all-caps heading leakage across all canonical EN raw artifacts.",
                extra={
                    "tag": block.tag,
                    "block_index": block.index,
                    "uppercase_ratio": round(uppercase_ratio, 3),
                },
            )
        )
    return defects


def _references_summary(text: str) -> dict[str, Any]:
    matches = list(REFERENCES_RE.finditer(text))
    if not matches:
        return {"found": False, "line": None, "snippet": None, "post_reference_bytes": 0}
    first = matches[0]
    return {
        "found": True,
        "line": _line_at(text, first.start()),
        "snippet": _snippet_at(text, first.start(), first.end()),
        "post_reference_bytes": len(text) - first.start(),
    }


def _anchor_summary(text: str) -> dict[str, Any]:
    return {
        "anchors": len(re.findall(r"<a\b", text, re.IGNORECASE)),
        "escaped_anchors": len(ESCAPED_ANCHOR_RE.findall(text)),
        "ids": len(re.findall(r"\bid\s*=", text, re.IGNORECASE)),
        "hrefs": len(re.findall(r"\bhref\s*=", text, re.IGNORECASE)),
    }


def _mojibake_micro_count(text: str) -> int:
    return len(re.findall(re.escape(MOJIBAKE_MICRO), text))


def analyze_file(path: Path) -> dict[str, Any]:
    data, text, read_defect = _read_utf8(path)
    blocks = _parse_blocks(text) if text else []
    plain_text = _strip_tags(text) if text else ""
    image_summary, image_defect = _image_summary(path, text) if text else ({}, None)

    defects: list[Defect] = []
    if read_defect is not None:
        defects.append(read_defect)
    defects.extend(_major_tag_defects(text))
    if image_defect is not None:
        defects.append(image_defect)

    defects.extend(_caption_without_image_defects(blocks))
    defects.extend(_heading_ocr_defects(blocks))

    for defect in [
        _first_match_defect(
            defect_id="R07",
            check="Detect page headers/footers like Page X of Y",
            severity="info",
            pattern=PAGE_HEADER_RE,
            text=plain_text,
            hypothesis="EN raw contains page headers that should be removed in EN polish.",
            proposed_fix_layer="EN polish",
            regression_test="Unit-test page header removal and re-run EN raw audit to keep the baseline visible.",
        ),
        _first_match_defect(
            defect_id="R08",
            check="Detect glued roman/table footnote suffixes",
            severity="info",
            pattern=GLUED_ROMAN_SUFFIX_RE,
            text=plain_text,
            hypothesis="OCR or table extraction glued a roman footnote suffix to a word.",
            proposed_fix_layer="EN polish, only after checking same-pattern corpus hits",
            regression_test="Add focused normalization cases for the systemic suffix pattern.",
        ),
        _first_match_defect(
            defect_id="R09",
            check="Detect DOI corruption and duplicated DOI fragments",
            severity="info",
            pattern=DUPLICATED_DOI_FRAGMENT_RE,
            text=plain_text,
            hypothesis="Raw extraction duplicated a DOI token.",
            proposed_fix_layer="Marker/source classification if raw-only; EN polish if introduced later",
            regression_test="Compare DOI counts before and after polish for affected articles.",
        ),
        _first_match_defect(
            defect_id="R11",
            check="Detect broken hyphenated line joins in prose/table cells",
            severity="info",
            pattern=BROKEN_HYPHEN_RE,
            text=plain_text,
            hypothesis="Layout extraction preserved a hyphenated line break or table split.",
            proposed_fix_layer="EN polish after corpus review",
            regression_test="Add text-normalization test for the shared hyphenation shape.",
        ),
        _first_match_defect(
            defect_id="R12",
            check="Detect formula/unit splits around micro units",
            severity="info",
            pattern=FORMULA_UNIT_FRAGMENT_RE,
            text=plain_text,
            hypothesis="Formula or OCR extraction split micro-unit text before translation.",
            proposed_fix_layer="EN polish or formula protection",
            regression_test="Add formula/unit protection test and re-run audit over all EN raw files.",
        ),
        _first_match_defect(
            defect_id="R14",
            check="Detect raw pipeline sentinels",
            severity="error",
            pattern=RAW_SENTINEL_RE,
            text=text,
            hypothesis="Pipeline sentinels leaked into EN raw, which should never happen.",
            proposed_fix_layer="pipeline staging or sanitizer",
            regression_test="Run EN raw audit and fail on R14.",
        ),
    ]:
        if defect is not None:
            defects.append(defect)

    defects.extend(_all_caps_heading_defects(blocks))

    figure_mentions = list(FIGURE_LABEL_RE.finditer(plain_text))
    figure_captions = [block for block in blocks if FIGURE_CAPTION_RE.search(block.text)]
    table_labels = list(TABLE_LABEL_RE.finditer(plain_text))
    doi_tokens = list(DOI_RE.finditer(plain_text))

    summary = {
        "bytes": len(data),
        "blocks": len(blocks),
        "images": image_summary,
        "figure_labels": len(figure_mentions),
        "figure_caption_blocks": len(figure_captions),
        "table_labels": len(table_labels),
        "page_headers": len(PAGE_HEADER_RE.findall(plain_text)),
        "raw_sentinels": len(RAW_SENTINEL_RE.findall(text)),
        "anchors": _anchor_summary(text),
        "references": _references_summary(plain_text),
        "doi_tokens": len(doi_tokens),
        "duplicated_doi_fragments": len(DUPLICATED_DOI_FRAGMENT_RE.findall(plain_text)),
        "glued_roman_suffixes": len(GLUED_ROMAN_SUFFIX_RE.findall(plain_text)),
        "broken_hyphen_joins": len(BROKEN_HYPHEN_RE.findall(plain_text)),
        "formula_unit_fragments": len(FORMULA_UNIT_FRAGMENT_RE.findall(plain_text)),
        "micro_tokens": len(MICRO_TOKEN_RE.findall(plain_text)),
        "mojibake_micro_tokens": _mojibake_micro_count(plain_text),
    }

    return {
        "article": article_name_from_html_stage(path),
        "stage_path": str(path),
        "run_log": str(path.with_suffix(".log")) if path.with_suffix(".log").exists() else None,
        "en_raw_summary": summary,
        "defects_found": [asdict(defect) for defect in defects],
    }


def find_stage_files(roots: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        if root.is_file() and root.name == STAGE_NAME:
            found.append(root)
        elif root.exists():
            found.extend(root.rglob(STAGE_NAME))
    return sorted({path.resolve(strict=False) for path in found})


def _add_corpus_hit_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for article in articles:
        seen = {defect["id"] for defect in article["defects_found"]}
        for defect_id in seen:
            counts[defect_id] = counts.get(defect_id, 0) + 1
    for article in articles:
        for defect in article["defects_found"]:
            defect["same_pattern_hits_across_corpus"] = counts.get(defect["id"], 0)
    return counts


def build_report(roots: list[Path]) -> dict[str, Any]:
    files = find_stage_files(roots)
    articles = [analyze_file(path) for path in files]
    defect_counts = _add_corpus_hit_counts(articles)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": STAGE_NAME,
        "roots": [str(root) for root in roots],
        "article_count": len(articles),
        "corpus_summary": {
            "defect_counts": defect_counts,
            "totals": {
                "bytes": sum(article["en_raw_summary"]["bytes"] for article in articles),
                "img_tags": sum(article["en_raw_summary"]["images"].get("img_tags", 0) for article in articles),
                "figure_labels": sum(article["en_raw_summary"]["figure_labels"] for article in articles),
                "table_labels": sum(article["en_raw_summary"]["table_labels"] for article in articles),
                "page_headers": sum(article["en_raw_summary"]["page_headers"] for article in articles),
                "raw_sentinels": sum(article["en_raw_summary"]["raw_sentinels"] for article in articles),
            },
        },
        "articles": articles,
    }


def _print_summary(report: dict[str, Any]) -> None:
    print(f"EN raw audit: {report['article_count']} artifact(s)")
    totals = report["corpus_summary"]["totals"]
    print(
        "Totals: "
        f"bytes={totals['bytes']} "
        f"img={totals['img_tags']} "
        f"figure_labels={totals['figure_labels']} "
        f"table_labels={totals['table_labels']} "
        f"page_headers={totals['page_headers']} "
        f"raw_sentinels={totals['raw_sentinels']}"
    )
    defect_counts = report["corpus_summary"]["defect_counts"]
    if defect_counts:
        print("Defects by check: " + ", ".join(f"{key}={value}" for key, value in sorted(defect_counts.items())))
    else:
        print("Defects by check: none")
    for article in report["articles"]:
        summary = article["en_raw_summary"]
        print(
            f"- {article['article']}: "
            f"bytes={summary['bytes']} "
            f"img={summary['images'].get('img_tags', 0)} "
            f"fig={summary['figure_labels']} "
            f"tables={summary['table_labels']} "
            f"headers={summary['page_headers']} "
            f"defects={len(article['defects_found'])}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        required=True,
        help="Root directories or direct 01.en.raw.html files to audit.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit with status 1 when an error-severity defect is found.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.roots)
    _print_summary(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    if args.fail_on_error:
        for article in report["articles"]:
            if any(defect["severity"] == "error" for defect in article["defects_found"]):
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
