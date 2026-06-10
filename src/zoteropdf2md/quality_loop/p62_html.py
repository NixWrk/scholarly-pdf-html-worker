"""HTML patch helpers for P62 figure-image recovery."""

from __future__ import annotations

import base64
import hashlib
from html import escape, unescape
import re
from typing import Any

from zoteropdf2md.html_links import escape_html_attr_literal as _escape_html_attr
from zoteropdf2md.quality_loop.p62_matching import figure_label_present_in_text


ID_RE = re.compile(r"\bid\s*=\s*([\"'])(?P<id>.*?)\1", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
P62_MISSING_WARNING_ELEMENT_RE = re.compile(
    r"<(?P<tag>p|div|span)\b(?P<attrs>[^>]*\bz2m-missing-figure-warning\b[^>]*)>"
    r"[\s\S]*?</(?P=tag)>",
    re.IGNORECASE,
)
P62_MISSING_FIGURE_UNIT_RE = re.compile(
    r"<div\b(?=[^>]*\bz2m-missing-figure-unit\b)[^>]*>[\s\S]*?</div>",
    re.IGNORECASE,
)
P62_RECOVERED_TARGET_ELEMENT_RE = re.compile(
    r"<(?P<tag>p|div|span)\b(?P<attrs>[^>]*\bz2m-p62-recovered-target\b[^>]*)>"
    r"[\s\S]*?</(?P=tag)>",
    re.IGNORECASE,
)
P62_RECOVERY_SOURCE_RE = re.compile(
    r"\bdata-z2m-recovery-source\s*=\s*([\"'])(?P<source>.*?)\1",
    re.IGNORECASE | re.DOTALL,
)
P62_LOW_FIDELITY_RECOVERY_SOURCES = {"pdf_page_render"}
P62_PDF_DERIVED_RECOVERY_SOURCES = {
    "pdf_page_render",
    "pdf_figure_region_render",
    "pdf_native_image",
    "pdf_detached_plate_region_render",
}


def _visible_html_text(fragment: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", " ", fragment)
    text = TAG_RE.sub(" ", text)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def _remove_class_from_open_tag(open_tag: str, class_name: str) -> str:
    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        classes = [
            item
            for item in re.split(r"\s+", match.group(2).strip())
            if item and item != class_name
        ]
        if not classes:
            return ""
        return f"class={quote}{' '.join(classes)}{quote}"

    return re.sub(
        r"\bclass\s*=\s*(['\"])(.*?)\1",
        replace,
        open_tag,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )


def clean_resolved_missing_unit_classes(html: str) -> str:
    def replace_unit(match: re.Match[str]) -> str:
        raw = match.group(0)
        if "z2m-missing-figure-warning" in raw:
            return raw
        open_end = raw.find(">")
        if open_end < 0:
            return raw
        open_tag = _remove_class_from_open_tag(raw[: open_end + 1], "z2m-missing-figure-unit")
        return open_tag + raw[open_end + 1 :]

    return P62_MISSING_FIGURE_UNIT_RE.sub(replace_unit, html)


def recovery_target_html(
    data_url: str,
    *,
    figure_label: str,
    source: str,
    source_detail: str,
) -> str:
    label = str(figure_label or "").strip()
    alt = f"Recovered Figure {label} visual from source PDF" if label else "Recovered figure visual from source PDF"
    return (
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        '<img '
        f'data-z2m-src="{_escape_html_attr(source_detail)}" '
        f'data-z2m-recovery-source="{_escape_html_attr(source)}" '
        f'alt="{_escape_html_attr(alt)}" '
        f'src="{_escape_html_attr(data_url)}"/>'
        "</p>"
    )


def replace_missing_warning_with_image(
    html: str,
    *,
    figure_label: str,
    warning_index: int | None,
    data_url: str,
    source: str,
    source_detail: str,
) -> tuple[str, int]:
    matches = list(P62_MISSING_WARNING_ELEMENT_RE.finditer(html))
    if not matches:
        return html, 0

    label_matches = [
        match
        for match in matches
        if not figure_label or figure_label_present_in_text(_visible_html_text(match.group(0)), figure_label)
    ]
    usable_matches = label_matches or matches
    if warning_index and warning_index > 0 and warning_index <= len(usable_matches):
        target = usable_matches[warning_index - 1]
    else:
        target = usable_matches[0]

    replacement = recovery_target_html(
        data_url,
        figure_label=figure_label,
        source=source,
        source_detail=source_detail,
    )
    patched = html[: target.start()] + replacement + html[target.end() :]
    return clean_resolved_missing_unit_classes(patched), 1


def recovered_target_source(raw: str) -> str:
    match = P62_RECOVERY_SOURCE_RE.search(raw)
    if not match:
        return ""
    return unescape(str(match.group("source") or "")).strip()


def id_matches_figure_label(raw_id: str, figure_label: str) -> bool:
    normalized_id = re.sub(r"[^a-z0-9]+", "-", str(raw_id or "").casefold()).strip("-")
    normalized_label = re.sub(r"[^a-z0-9]+", "-", str(figure_label or "").casefold()).strip("-")
    return bool(normalized_label) and normalized_id in {
        f"fig-{normalized_label}",
        f"figure-{normalized_label}",
    }


def recovered_target_matches_label(
    html: str,
    match: re.Match[str],
    figure_label: str,
) -> bool:
    label = str(figure_label or "").strip()
    if not label:
        return True
    before = html[max(0, match.start() - 800) : match.start()]
    div_tags = list(re.finditer(r"<div\b[^>]*>", before, flags=re.IGNORECASE | re.DOTALL))
    if div_tags:
        nearest_div = div_tags[-1].group(0)
        id_match = ID_RE.search(nearest_div)
        if id_match:
            raw_id = unescape(str(id_match.group("id") or ""))
            return id_matches_figure_label(raw_id, label)

    after = html[match.end() : min(len(html), match.end() + 1800)]
    return figure_label_present_in_text(_visible_html_text(after), label)


def html_has_stale_page_render_for_label(html: str, figure_label: str) -> bool:
    return html_has_recovery_for_label(
        html,
        figure_label,
        sources=P62_LOW_FIDELITY_RECOVERY_SOURCES,
    )


def html_has_recovery_for_label(
    html: str,
    figure_label: str,
    *,
    sources: set[str] | None = None,
) -> bool:
    for match in P62_RECOVERED_TARGET_ELEMENT_RE.finditer(html):
        source = recovered_target_source(match.group(0))
        if sources is not None and source not in sources:
            continue
        if recovered_target_matches_label(html, match, figure_label):
            return True
    return False


def missing_warning_target_html(figure_label: str, *, reason: str = "") -> str:
    label = str(figure_label or "").strip()
    figure_text = f"Figure {label}" if label else "Figure"
    reason_attr = f' data-z2m-recovery-status="{_escape_html_attr(reason)}"' if reason else ""
    return (
        f'<p class="z2m-missing-figure-warning z2m-figure-target" role="note"{reason_attr}>'
        f"{escape(figure_text, quote=False)} image was not extracted into this HTML. "
        "Please check the original PDF for the missing visual content."
        "</p>"
    )


def replace_figure_unit_target_with_missing_warning(
    html: str,
    *,
    figure_label: str,
    reason: str,
) -> tuple[str, int]:
    label = str(figure_label or "").strip()
    if not label:
        return html, 0
    div_re = re.compile(r"<div\b[^>]*>", re.IGNORECASE | re.DOTALL)
    for div_match in div_re.finditer(html):
        id_match = ID_RE.search(div_match.group(0))
        if not id_match or not id_matches_figure_label(unescape(id_match.group("id")), label):
            continue
        close_index = html.find("</div>", div_match.end())
        if close_index < 0:
            continue
        body = html[div_match.end() : close_index]
        target = P62_MISSING_WARNING_ELEMENT_RE.search(body) or P62_RECOVERED_TARGET_ELEMENT_RE.search(body)
        if not target:
            continue
        replacement = missing_warning_target_html(label, reason=reason)
        if target.group(0) == replacement:
            return html, 0
        start = div_match.end() + target.start()
        end = div_match.end() + target.end()
        return html[:start] + replacement + html[end:], 1
    return html, 0


def html_has_missing_warning_for_figure_unit(html: str, figure_label: str) -> bool:
    label = str(figure_label or "").strip()
    if not label:
        return False
    div_re = re.compile(r"<div\b[^>]*>", re.IGNORECASE | re.DOTALL)
    for div_match in div_re.finditer(html):
        id_match = ID_RE.search(div_match.group(0))
        if not id_match or not id_matches_figure_label(unescape(id_match.group("id")), label):
            continue
        close_index = html.find("</div>", div_match.end())
        if close_index < 0:
            continue
        body = html[div_match.end() : close_index]
        return bool(P62_MISSING_WARNING_ELEMENT_RE.search(body))
    return False


def html_has_missing_warning_for_label(html: str, figure_label: str) -> bool:
    matches = list(P62_MISSING_WARNING_ELEMENT_RE.finditer(html))
    if not matches:
        return False
    if not figure_label:
        return True
    return any(
        figure_label_present_in_text(_visible_html_text(match.group(0)), figure_label)
        for match in matches
    )


def replace_recovery_with_missing_warning(
    html: str,
    *,
    figure_label: str,
    reason: str,
    replace_sources: set[str] | None = None,
) -> tuple[str, int]:
    sources = replace_sources or P62_PDF_DERIVED_RECOVERY_SOURCES
    for match in P62_RECOVERED_TARGET_ELEMENT_RE.finditer(html):
        existing_source = recovered_target_source(match.group(0))
        if existing_source not in sources:
            continue
        if not recovered_target_matches_label(html, match, figure_label):
            continue
        replacement = missing_warning_target_html(figure_label, reason=reason)
        return html[: match.start()] + replacement + html[match.end() :], 1
    return html, 0


def replace_stale_recovery_with_image(
    html: str,
    *,
    figure_label: str,
    data_url: str,
    source: str,
    source_detail: str,
    replace_sources: set[str] | None = None,
) -> tuple[str, int]:
    sources = replace_sources or P62_LOW_FIDELITY_RECOVERY_SOURCES
    for match in P62_RECOVERED_TARGET_ELEMENT_RE.finditer(html):
        existing_source = recovered_target_source(match.group(0))
        if existing_source not in sources:
            continue
        if not recovered_target_matches_label(html, match, figure_label):
            continue
        replacement = recovery_target_html(
            data_url,
            figure_label=figure_label,
            source=source,
            source_detail=source_detail,
        )
        return html[: match.start()] + replacement + html[match.end() :], 1
    return html, 0


def data_url_image_hash(raw: str) -> str:
    match = re.search(r"\bsrc\s*=\s*([\"'])data:image/[^;]+;base64,(?P<data>.*?)\1", raw, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    raw_data = str(match.group("data") or "")
    try:
        data = base64.b64decode(raw_data, validate=False)
    except Exception:
        return hashlib.sha256(raw_data.encode("utf-8", errors="replace")).hexdigest()
    return hashlib.sha256(data).hexdigest()


def figure_label_from_unit_id(raw_id: str) -> str:
    value = str(raw_id or "").strip()
    if not value.casefold().startswith("fig-"):
        return ""
    return re.sub(r"[^0-9A-Za-z]+", "-", value[4:]).strip("-")


def extract_html_figure_units(html: str) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    div_re = re.compile(r"<div\b[^>]*>", re.IGNORECASE | re.DOTALL)
    target_re = re.compile(r"<p\b[^>]*\bz2m-figure-target\b[^>]*>[\s\S]*?</p>", re.IGNORECASE)
    fallback_img_target_re = re.compile(r"<p\b[^>]*>\s*<img\b[\s\S]*?</p>", re.IGNORECASE)
    caption_re = re.compile(
        r"<p\b[^>]*\bz2m-figure-caption\b[^>]*>(?P<body>[\s\S]*?)</p>",
        re.IGNORECASE,
    )
    for div_match in div_re.finditer(html):
        div_tag = div_match.group(0)
        id_match = ID_RE.search(div_tag)
        if not id_match:
            continue
        raw_id = unescape(str(id_match.group("id") or ""))
        label = figure_label_from_unit_id(raw_id)
        if not label:
            continue
        if "z2m-figure-unit" not in div_tag and "z2m-float-unit" not in div_tag:
            continue
        close_index = html.find("</div>", div_match.end())
        if close_index < 0:
            continue
        body = html[div_match.end() : close_index]
        target_match = target_re.search(body) or fallback_img_target_re.search(body)
        caption_match = caption_re.search(body)
        img_hashes: list[str] = []
        recovery_sources: list[str] = []
        for img_match in re.finditer(r"<img\b[^>]*>", body, re.IGNORECASE | re.DOTALL):
            image_hash = data_url_image_hash(img_match.group(0))
            if image_hash:
                img_hashes.append(image_hash)
            source = recovered_target_source(img_match.group(0))
            if source:
                recovery_sources.append(source)
        units.append(
            {
                "id": raw_id,
                "label": label,
                "start": div_match.start(),
                "end": close_index + len("</div>"),
                "body_start": div_match.end(),
                "body_end": close_index,
                "target_start": div_match.end() + target_match.start() if target_match else 0,
                "target_end": div_match.end() + target_match.end() if target_match else 0,
                "caption": _visible_html_text(caption_match.group("body")) if caption_match else "",
                "image_hashes": img_hashes,
                "recovery_sources": recovery_sources,
            }
        )
    return units


def replace_figure_unit_target_with_image(
    html: str,
    *,
    figure_label: str,
    data_url: str,
    source: str,
    source_detail: str,
) -> tuple[str, int]:
    for unit in extract_html_figure_units(html):
        if str(unit.get("label") or "") != str(figure_label or ""):
            continue
        start = int(unit.get("target_start") or 0)
        end = int(unit.get("target_end") or 0)
        if not start or not end or end <= start:
            continue
        replacement = recovery_target_html(
            data_url,
            figure_label=figure_label,
            source=source,
            source_detail=source_detail,
        )
        return html[:start] + replacement + html[end:], 1
    return html, 0
