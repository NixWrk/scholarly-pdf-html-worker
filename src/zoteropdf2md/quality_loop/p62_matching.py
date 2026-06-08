"""P62 PDF figure-label matching helpers."""

from __future__ import annotations

from html import unescape
import re
from pathlib import Path
from typing import Any, Iterable


def tokenize_evidence_text(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[A-Za-zА-Яа-яЁё0-9]{3,}", unescape(str(value)).casefold())
        if not token.isdigit()
    ]


def evidence_snippet_tokens(snippets: list[str]) -> set[str]:
    snippet_tokens: set[str] = set()
    for snippet in snippets:
        snippet_tokens.update(tokenize_evidence_text(snippet)[:80])
    return snippet_tokens


def pdf_page_match_score(snippet_tokens: set[str], page_text: str) -> float:
    if not snippet_tokens:
        return 0.0
    page_tokens = set(tokenize_evidence_text(page_text))
    if not page_tokens:
        return 0.0
    return len(snippet_tokens & page_tokens) / max(1, len(snippet_tokens))


def best_pdf_text_page(snippets: list[str], pages: list[str]) -> tuple[int, float]:
    if not pages:
        return 0, 0.0
    snippet_tokens = evidence_snippet_tokens(snippets)
    if not snippet_tokens:
        return 1, 0.0

    best_page = 1
    best_score = -1.0
    for index, page_text in enumerate(pages, start=1):
        score = pdf_page_match_score(snippet_tokens, page_text)
        if score > best_score:
            best_page = index
            best_score = score
    return best_page, max(0.0, best_score)


def figure_label_present_in_text(text: str, figure_label: str) -> bool:
    label = str(figure_label or "").strip()
    if not label:
        return False
    return bool(
        re.search(
            rf"\b(?:fig(?:ure)?\.?)\s*{re.escape(label)}(?=\b|[^\w])",
            str(text or ""),
            re.IGNORECASE,
        )
    )


def figure_label_present_in_text_strict(text: str, figure_label: str) -> bool:
    label = str(figure_label or "").strip()
    if not label:
        return False
    return bool(
        re.search(
            rf"\b(?:fig(?:ure)?\.?)\s*{re.escape(label)}(?![\w-]|\.[A-Za-z0-9])",
            str(text or ""),
            re.IGNORECASE,
        )
    )


def full_figure_label_from_context(context: str, fallback_label: str) -> str:
    fallback = str(fallback_label or "").strip()
    candidates: list[str] = []
    for match in re.finditer(
        r"\b(?:fig(?:ure)?\.?)\s*([A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*[A-Za-z]?)\b",
        str(context or ""),
        re.IGNORECASE,
    ):
        label = match.group(1).strip().rstrip(".")
        if not label:
            continue
        if fallback:
            lower = label.casefold()
            base = fallback.casefold()
            if lower == base or lower.startswith(base + "-") or lower.startswith(base + "."):
                candidates.append(label)
        else:
            candidates.append(label)
    if candidates:
        return max(candidates, key=lambda item: (len(item), item))
    return fallback


def false_page_match_hint(page_text: str, figure_label: str) -> str:
    text = str(page_text or "")
    compact = re.sub(r"\s+", " ", text).strip()
    lower = compact.casefold()
    label = re.escape(str(figure_label or "").strip())
    if not label:
        return ""
    label_ref = rf"(?:fig(?:ure)?\.?)\s*{label}(?![\w-]|\.[A-Za-z0-9])"
    label_pos = re.search(label_ref, compact, re.IGNORECASE)
    window = lower
    if label_pos:
        start = max(0, label_pos.start() - 500)
        end = min(len(compact), label_pos.end() + 500)
        window = compact[start:end].casefold()
    if "table of contents" in window or re.search(r"\bcontents\b", window) and "....." in window:
        return "toc_or_contents"
    if "figure captions" in window or "list of figures" in window:
        return "figure_caption_list"
    if re.search(rf"\binsert\s+(?:fig(?:ure)?\.?)\s*{label}\b", window, re.IGNORECASE):
        return "manuscript_placeholder"
    if re.search(rf"\({label_ref}\)", window, re.IGNORECASE):
        return "prose_parenthetical_reference"
    if re.search(r"\breferences\b", window[:160], re.IGNORECASE):
        return "backmatter_or_reference_text"
    return ""


def label_looks_caption_like(page_text: str, figure_label: str) -> bool:
    label = str(figure_label or "").strip()
    if not label:
        return False
    pattern = re.compile(
        rf"^\s*(?:fig(?:ure)?\.?)\s*{re.escape(label)}(?![\w-]|\.[A-Za-z0-9])"
        r"[\s:.\-\u2013|]+.{8,}",
        re.IGNORECASE,
    )
    return any(pattern.search(line) for line in str(page_text or "").splitlines())


def caption_head_tokens(snippets: list[str], figure_label: str) -> list[str]:
    label = str(figure_label or "").strip()
    if not label:
        return []
    label_pattern = re.compile(
        rf"\b(?:fig(?:ure)?\.?)\s*{re.escape(label)}(?![\w-]|\.[A-Za-z0-9])",
        re.IGNORECASE,
    )
    for snippet in snippets:
        text = str(snippet or "")
        match = label_pattern.search(text)
        if not match:
            continue
        tokens = tokenize_evidence_text(text[match.end() : match.end() + 360])
        if tokens:
            return tokens[:16]
    return []


def caption_head_present_near_label(
    page_text: str,
    figure_label: str,
    snippets: list[str],
) -> bool:
    expected_tokens = caption_head_tokens(snippets, figure_label)
    if not expected_tokens:
        return False
    label = str(figure_label or "").strip()
    label_pattern = re.compile(
        rf"\b(?:fig(?:ure)?\.?)\s*{re.escape(label)}(?![\w-]|\.[A-Za-z0-9])",
        re.IGNORECASE,
    )
    threshold = min(6, max(3, len(expected_tokens) // 2))
    required_head = expected_tokens[: min(3, len(expected_tokens))]
    for match in label_pattern.finditer(str(page_text or "")):
        window_tokens = tokenize_evidence_text(page_text[match.end() : match.end() + 700])
        window_set = set(window_tokens)
        if not window_set:
            continue
        head_hits = sum(1 for token in required_head if token in window_set)
        total_hits = sum(1 for token in expected_tokens if token in window_set)
        if head_hits >= max(1, len(required_head) - 1) and total_hits >= threshold:
            return True
    return False


def pdf_page_visual_summaries(
    pdf_path: Path,
    page_numbers: Iterable[int],
) -> dict[int, dict[str, Any]]:
    wanted = {int(page_number) for page_number in page_numbers if int(page_number) > 0}
    if not wanted or not pdf_path.is_file():
        return {}
    summaries: dict[int, dict[str, Any]] = {}
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            for page_number in sorted(wanted):
                if page_number < 1 or page_number > len(doc):
                    continue
                page = doc.load_page(page_number - 1)
                text_dict = page.get_text("dict") or {}
                blocks = text_dict.get("blocks") or []
                image_blocks = [block for block in blocks if block.get("type") == 1]
                text_blocks = [block for block in blocks if block.get("type") == 0]
                try:
                    drawings = page.get_drawings()
                except Exception:
                    drawings = []
                summaries[page_number] = {
                    "page_number": page_number,
                    "image_xrefs": len(page.get_images(full=True)),
                    "image_blocks": len(image_blocks),
                    "drawings": len(drawings),
                    "text_blocks": len(text_blocks),
                    "width": float(page.rect.width),
                    "height": float(page.rect.height),
                }
        finally:
            doc.close()
    except Exception:
        return summaries
    return summaries
