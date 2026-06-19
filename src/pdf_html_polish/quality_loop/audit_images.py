"""Image-asset diagnostics shared by EN polish audit tooling."""

from __future__ import annotations

import hashlib
from html import unescape
from pathlib import Path
import re
from typing import Any, Callable
import urllib.parse

from pdf_html_polish.html_stages import is_html_stage_dir_name
from pdf_html_polish.quality_loop.audit_blocks import Defect, line_at_from_starts, line_starts, strip_tags
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect


IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*(['\"])(?P<src>.*?)\1", re.IGNORECASE | re.DOTALL)


def is_inline_or_remote_src(src: str) -> bool:
    src = src.strip()
    if not src or src.startswith("#"):
        return True
    lower = src.lower()
    if lower.startswith(("data:", "http://", "https://", "blob:", "cid:")):
        return True
    parsed = urllib.parse.urlsplit(src)
    return bool(parsed.scheme and parsed.scheme.lower() not in {"file"})


def local_image_candidates(html_path: Path, src: str) -> list[Path]:
    clean = src.strip().split("?", 1)[0].split("#", 1)[0]
    if not clean:
        return []
    parsed = urllib.parse.urlsplit(clean)
    path_value = parsed.path if parsed.scheme.lower() == "file" else clean
    decoded = urllib.parse.unquote(path_value)
    if re.match(r"^/[A-Za-z]:/", decoded):
        decoded = decoded[1:]
    candidate = Path(decoded)
    if candidate.is_absolute():
        return [candidate]

    search_dirs = [html_path.parent]
    if is_html_stage_dir_name(html_path.parent.name):
        search_dirs.append(html_path.parent.parent)
    return [(base / decoded).resolve(strict=False) for base in search_dirs]


def missing_local_images(html_path: Path, html: str) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    seen: set[str] = set()
    starts = line_starts(html)
    for match in IMG_SRC_RE.finditer(html):
        src = unescape(match.group("src")).strip()
        if is_inline_or_remote_src(src):
            continue
        candidates = local_image_candidates(html_path, src)
        if any(candidate.is_file() for candidate in candidates):
            continue
        key = src
        if key in seen:
            continue
        seen.add(key)
        missing.append(
            {
                "src": src,
                "line": line_at_from_starts(starts, match.start()),
                "searched": [str(candidate) for candidate in candidates],
            }
        )
    return missing


def image_identity_key(html_path: Path, src: str) -> str | None:
    src = unescape(src).strip()
    if not src:
        return None
    if src.lower().startswith("data:image/"):
        return "data:" + hashlib.sha256(src.encode("utf-8", errors="replace")).hexdigest()
    if is_inline_or_remote_src(src):
        return None
    for candidate in local_image_candidates(html_path, src):
        if not candidate.is_file():
            continue
        try:
            return "file:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        except OSError:
            continue
    return f"src:{src}"


def image_asset_defects(polish_path: Path, polish_html: str, *, stage: str) -> list[Defect]:
    defects: list[Defect] = []
    missing = missing_local_images(polish_path, polish_html)
    for image in missing[:5]:
        defects.append(
            make_defect(
                defect_id="P20",
                cc_class="CC-08/CC-13",
                check="Local image asset referenced by polish HTML is missing",
                severity="error",
                block=None,
                snippet=f"missing image src={image['src']}",
                stage=stage,
                hypothesis="The HTML references a local sidecar image that is absent relative to the stage/review copy.",
                proposed_fix_layer="review packaging or EN polish image asset export",
                regression_test="Review/export HTML with local img src must include the referenced image or inline it as data URI.",
                extra=image,
            )
        )
    return defects


def figure_visual_identity_defects(
    polish_path: Path,
    polish_html: str,
    *,
    stage: str,
    figure_unit_re: re.Pattern[str],
    figure_caption_node_re: re.Pattern[str],
    figure_caption_number_from_caption_node: Callable[[str], int | None],
) -> list[Defect]:
    starts = line_starts(polish_html)
    records_by_key: dict[str, list[dict[str, Any]]] = {}
    for match in figure_unit_re.finditer(polish_html):
        figure_id = match.group("id")
        body = match.group("body")
        caption_numbers = [
            number
            for caption_match in figure_caption_node_re.finditer(body)
            for number in [figure_caption_number_from_caption_node(caption_match.group("body"))]
            if number is not None
        ]
        for img_match in IMG_SRC_RE.finditer(body):
            src = unescape(img_match.group("src")).strip()
            key = image_identity_key(polish_path, src)
            if key is None:
                continue
            records_by_key.setdefault(key, []).append(
                {
                    "figure_id": figure_id,
                    "caption_numbers": caption_numbers,
                    "src": src[:160],
                    "line": line_at_from_starts(starts, match.start()),
                    "snippet": strip_tags(body)[:260],
                }
            )

    for records in records_by_key.values():
        figure_ids = sorted({str(record["figure_id"]) for record in records})
        if len(figure_ids) < 2:
            continue
        caption_sets = {
            tuple(record.get("caption_numbers") or [])
            for record in records
            if record.get("caption_numbers")
        }
        if len(caption_sets) == 1 and len(records) <= 2:
            continue
        first = records[0]
        return [
            make_defect(
                defect_id="P96",
                cc_class="CC-08/CC-13",
                check="Same visual image is attached to multiple distinct figure targets",
                severity="error",
                block=None,
                snippet=first["snippet"] or f"duplicate visual across {', '.join(figure_ids)}",
                stage=stage,
                hypothesis="A missing-figure recovery or pre-existing figure assignment reused the next/previous figure image for a different caption.",
                proposed_fix_layer="P62 image recovery duplicate-visual audit and figure-page relocalization",
                regression_test="Distinct fig-5 and fig-6 units with identical image payloads are reported before review packaging.",
                extra={
                    "figure_ids": figure_ids,
                    "records": records[:6],
                },
            )
        ]
    return []
