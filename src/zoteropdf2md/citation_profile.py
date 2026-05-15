from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Any


PAREN_NUMERIC_CITATION_RE = re.compile(
    r"\(\s*\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12}\s*\)"
)
BRACKET_NUMERIC_CITATION_RE = re.compile(
    r"\[\s*\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12}\s*\]"
)
PLAIN_SUPERSCRIPT_NUMERIC_CITATION_RE = re.compile(
    r"(?<=[.!?])\s+"
    r"\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){1,12}"
    r"(?=\s+[A-Z])"
)
PDF_REF_START_RE = re.compile(r"^(?P<num>[1-9]\d{0,2})(?=[A-Z])")


@dataclass(frozen=True)
class PdfLinkSample:
    page: int
    dest: str
    text: str


@dataclass(frozen=True)
class PdfLinkAnnotation:
    page: int
    kind: str
    dest: str
    target: str
    text: str
    uri: str = ""
    target_page: int = 0
    target_x: float = 0.0
    target_y: float = 0.0
    rect: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class PdfReferenceStart:
    page: int
    number: int
    x: float
    y: float
    text: str


@dataclass(frozen=True)
class CitationProfile:
    source_pdf_path: str
    status: str
    style: str = "unknown"
    confidence: str = "low"
    page_count: int = 0
    link_count: int = 0
    named_dest_count: int = 0
    ref_dest_prefix: str = ""
    figure_dest_prefix: str = ""
    table_dest_prefix: str = ""
    ref_link_count: int = 0
    figure_link_count: int = 0
    table_link_count: int = 0
    paren_numeric_count: int = 0
    bracket_numeric_count: int = 0
    samples: list[PdfLinkSample] = field(default_factory=list)
    annotations: list[PdfLinkAnnotation] = field(default_factory=list)
    reference_starts: list[PdfReferenceStart] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_citation_style_from_text(
    text: str,
    *,
    ref_link_count: int = 0,
    superscript_hint_count: int = 0,
) -> tuple[str, str, int, int]:
    paren_count = len(PAREN_NUMERIC_CITATION_RE.findall(text))
    bracket_count = len(BRACKET_NUMERIC_CITATION_RE.findall(text))
    plain_superscript_count = len(PLAIN_SUPERSCRIPT_NUMERIC_CITATION_RE.findall(text))

    if ref_link_count >= 5 and superscript_hint_count >= max(5, bracket_count * 2, paren_count):
        return "superscript_numeric", "high", paren_count, bracket_count
    if plain_superscript_count >= max(5, paren_count * 2, bracket_count * 2):
        return "superscript_numeric", "high", paren_count, bracket_count
    if ref_link_count >= 5 and paren_count >= max(5, bracket_count * 2):
        return "paren_numeric", "high", paren_count, bracket_count
    if bracket_count >= 5 and bracket_count >= max(5, paren_count * 2):
        return "bracket_numeric", "medium", paren_count, bracket_count
    if superscript_hint_count >= 5 and superscript_hint_count > max(paren_count, bracket_count):
        return "superscript_numeric", "medium", paren_count, bracket_count
    if paren_count >= 5 and paren_count > bracket_count:
        return "paren_numeric", "medium", paren_count, bracket_count
    if bracket_count >= 5 and bracket_count > paren_count:
        return "bracket_numeric", "medium", paren_count, bracket_count
    return "unknown", "low", paren_count, bracket_count


def _dest_prefix_counts(dests: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for dest in dests:
        match = re.match(r"([A-Za-z]+)\d+", dest)
        if match is None:
            continue
        prefix = match.group(1)
        counts[prefix] = counts.get(prefix, 0) + 1
    return counts


def _dominant_prefix(counts: dict[str, int], candidates: tuple[str, ...]) -> str:
    best = ""
    best_count = 0
    lower_counts = {key.lower(): (key, value) for key, value in counts.items()}
    for candidate in candidates:
        found = lower_counts.get(candidate.lower())
        if found is None:
            continue
        key, value = found
        if value > best_count:
            best = key
            best_count = value
    return best


def _target_from_dest(dest: str, prefix: str) -> str:
    if not prefix or not dest.startswith(prefix):
        return ""
    suffix = dest[len(prefix):]
    match = re.match(r"(\d+)", suffix)
    return match.group(1) if match is not None else ""


def _link_text_from_rect(page: Any, rect: Any) -> str:
    textbox = ""
    words_text = ""
    try:
        textbox = page.get_textbox(rect + (-8, -4, 8, 4)).replace("\n", " ")
    except Exception:
        textbox = ""
    try:
        expanded = rect + (-2, -2, 2, 2)
        words = []
        for word in page.get_text("words") or []:
            word_rect = type(rect)(word[:4])
            if word_rect.intersects(expanded):
                words.append(word)
        words.sort(key=lambda item: (item[5], item[6], item[7]))
        words_text = " ".join(str(word[4]) for word in words)
    except Exception:
        words_text = ""

    candidates = [
        re.sub(r"\s+", " ", value).strip()
        for value in (words_text, textbox)
        if value and value.strip()
    ]
    if not candidates:
        return ""
    return min(candidates, key=lambda value: (len(value), value))


def _reference_starts_from_doc(doc: Any) -> list[PdfReferenceStart]:
    starts: list[PdfReferenceStart] = []
    for page_index, page in enumerate(doc):
        try:
            words = page.get_text("words") or []
        except Exception:
            continue
        candidates: list[PdfReferenceStart] = []
        for word in words:
            try:
                x0, y0, _x1, _y1, text = word[:5]
            except Exception:
                continue
            text = str(text)
            match = PDF_REF_START_RE.match(text)
            if match is None:
                continue
            try:
                number = int(match.group("num"))
            except ValueError:
                continue
            candidates.append(
                PdfReferenceStart(
                    page=page_index + 1,
                    number=number,
                    x=round(float(x0), 3),
                    y=round(float(y0), 3),
                    text=text,
                )
            )
        starts.extend(_filter_reference_start_sequences(candidates))
    return sorted(starts, key=lambda item: (item.page, item.x, item.y, item.number))


def _filter_reference_start_sequences(candidates: list[PdfReferenceStart]) -> list[PdfReferenceStart]:
    if len(candidates) < 4 and not any(candidate.number >= 20 for candidate in candidates):
        return []
    columns: list[list[PdfReferenceStart]] = []
    for candidate in sorted(candidates, key=lambda item: item.x):
        for column in columns:
            if abs(column[0].x - candidate.x) <= 24:
                column.append(candidate)
                break
        else:
            columns.append([candidate])

    kept: list[PdfReferenceStart] = []
    for column in columns:
        ordered = sorted(column, key=lambda item: (item.y, item.number))
        longest: list[PdfReferenceStart] = []
        current: list[PdfReferenceStart] = []
        previous_number = 0
        for candidate in ordered:
            if not current or candidate.number in {previous_number + 1, previous_number + 2}:
                current.append(candidate)
            else:
                if len(current) > len(longest):
                    longest = current
                current = [candidate]
            previous_number = candidate.number
        if len(current) > len(longest):
            longest = current
        if len(longest) >= 4:
            kept.extend(longest)
        elif any(candidate.number >= 20 for candidate in ordered):
            kept.extend(ordered)
    return kept


def _reference_target_from_page_location(
    starts_by_page: dict[int, list[PdfReferenceStart]],
    page_target: str,
    target_x: float,
    target_y: float,
) -> str:
    if not page_target.isdigit():
        return ""
    starts = starts_by_page.get(int(page_target), [])
    if not starts:
        return ""
    if target_x:
        starts = [start for start in starts if abs(start.x - target_x) <= 80]
    if not starts:
        return ""
    candidates = [start for start in starts if start.y >= target_y - 16]
    if not candidates:
        candidates = starts
    chosen = min(
        candidates,
        key=lambda start: (
            abs(start.y - target_y),
            max(0.0, start.y - target_y),
            abs(start.x - target_x) if target_x else 0.0,
        ),
    )
    if target_y and abs(chosen.y - target_y) > 40:
        return ""
    return str(chosen.number)


def _superscript_reference_hint_count(annotations: list[PdfLinkAnnotation]) -> int:
    count = 0
    for annotation in annotations:
        if annotation.kind != "reference":
            continue
        text = annotation.text
        if PAREN_NUMERIC_CITATION_RE.search(text) or BRACKET_NUMERIC_CITATION_RE.search(text):
            continue
        if re.search(r"(?:[A-Za-z]\d{1,3}|\d{1,3}\s*(?:[-\u2013\u2014]|,)\s*\d{1,3}|[.,:;]\s*\d{1,3})", text):
            count += 1
    return count


def build_citation_profile_from_pdf(pdf_path: str | Path, *, sample_limit: int = 32) -> CitationProfile:
    path = Path(pdf_path).expanduser().resolve(strict=False)
    if not path.is_file():
        return CitationProfile(
            source_pdf_path=str(path),
            status="missing_pdf",
            errors=[f"PDF not found: {path}"],
        )

    try:
        import fitz  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depends on local optional dependency
        return CitationProfile(
            source_pdf_path=str(path),
            status="pymupdf_unavailable",
            errors=[str(exc)],
        )

    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        return CitationProfile(
            source_pdf_path=str(path),
            status="pdf_open_failed",
            errors=[str(exc)],
        )

    errors: list[str] = []
    dests: list[str] = []
    raw_annotations: list[tuple[int, str, str, str, float, float, str, list[float]]] = []
    link_count = 0
    text_parts: list[str] = []
    reference_starts: list[PdfReferenceStart] = []
    try:
        reference_starts = _reference_starts_from_doc(doc)
        for page_index, page in enumerate(doc):
            try:
                text_parts.append(page.get_text("text") or "")
            except Exception as exc:
                errors.append(f"page {page_index + 1} text failed: {exc}")

            try:
                links = page.get_links()
            except Exception as exc:
                errors.append(f"page {page_index + 1} links failed: {exc}")
                continue
            link_count += len(links)
            for link in links:
                dest = str(link.get("nameddest") or "")
                uri = str(link.get("uri") or "")
                page_target = ""
                target_x = 0.0
                target_y = 0.0
                if link.get("page") is not None:
                    try:
                        page_target = str(int(link["page"]) + 1)
                    except Exception:
                        page_target = str(link.get("page") or "")
                if link.get("to") is not None:
                    try:
                        target_x = round(float(link["to"].x), 3)
                        target_y = round(float(link["to"].y), 3)
                    except Exception:
                        target_x = 0.0
                        target_y = 0.0
                if not dest and not uri and not page_target:
                    continue
                if dest:
                    dests.append(dest)
                try:
                    rect = fitz.Rect(link["from"])
                    sample_text = _link_text_from_rect(page, rect)
                    rect_values = [round(float(value), 3) for value in (rect.x0, rect.y0, rect.x1, rect.y1)]
                except Exception:
                    sample_text = ""
                    rect_values = []
                raw_annotations.append(
                    (page_index + 1, dest, uri, page_target, target_x, target_y, sample_text, rect_values)
                )
    finally:
        page_count = doc.page_count
        doc.close()

    prefix_counts = _dest_prefix_counts(dests)
    ref_prefix = _dominant_prefix(prefix_counts, ("B", "R", "ref"))
    figure_prefix = _dominant_prefix(prefix_counts, ("f", "F", "fig"))
    table_prefix = _dominant_prefix(prefix_counts, ("T", "tab", "table"))
    starts_by_page: dict[int, list[PdfReferenceStart]] = {}
    for start in reference_starts:
        starts_by_page.setdefault(start.page, []).append(start)
    annotations: list[PdfLinkAnnotation] = []
    for page_number, dest, uri, page_target, target_x, target_y, text, rect in raw_annotations:
        kind = "internal"
        target = ""
        ref_target = _target_from_dest(dest, ref_prefix)
        figure_target = _target_from_dest(dest, figure_prefix)
        table_target = _target_from_dest(dest, table_prefix)
        if ref_target:
            kind = "reference"
            target = ref_target
        elif figure_target:
            kind = "figure"
            target = figure_target
        elif table_target:
            kind = "table"
            target = table_target
        elif uri:
            kind = "external"
            target = uri
        elif dest:
            target = dest
        elif page_ref_target := _reference_target_from_page_location(
            starts_by_page,
            page_target,
            target_x,
            target_y,
        ):
            kind = "reference"
            target = page_ref_target
        else:
            kind = "page"
            target = page_target
        annotations.append(
            PdfLinkAnnotation(
                page=page_number,
                kind=kind,
                dest=dest,
                target=target,
                text=text,
                uri=uri,
                target_page=int(page_target) if page_target.isdigit() else 0,
                target_x=target_x,
                target_y=target_y,
                rect=rect,
            )
        )
    ref_link_count = sum(1 for annotation in annotations if annotation.kind == "reference")
    figure_link_count = sum(1 for annotation in annotations if annotation.kind == "figure")
    table_link_count = sum(1 for annotation in annotations if annotation.kind == "table")
    samples = [
        PdfLinkSample(page=annotation.page, dest=annotation.dest, text=annotation.text)
        for annotation in annotations[:sample_limit]
    ]
    style, confidence, paren_count, bracket_count = infer_citation_style_from_text(
        "\n".join(text_parts),
        ref_link_count=ref_link_count,
        superscript_hint_count=_superscript_reference_hint_count(annotations),
    )

    return CitationProfile(
        source_pdf_path=str(path),
        status="ok",
        style=style,
        confidence=confidence,
        page_count=page_count,
        link_count=link_count,
        named_dest_count=len(dests),
        ref_dest_prefix=ref_prefix,
        figure_dest_prefix=figure_prefix,
        table_dest_prefix=table_prefix,
        ref_link_count=ref_link_count,
        figure_link_count=figure_link_count,
        table_link_count=table_link_count,
        paren_numeric_count=paren_count,
        bracket_numeric_count=bracket_count,
        samples=samples,
        annotations=annotations,
        reference_starts=reference_starts,
        errors=errors,
    )
