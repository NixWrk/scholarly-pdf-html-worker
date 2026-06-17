"""Plain URL/DOI autolinking for raw/Marker polished HTML."""

from __future__ import annotations

import re

from ..url_repair import split_url_and_trailing_punct


_TAG_SPLIT_PATTERN = re.compile(r"(<[^>]+>)")
_OPEN_TAG_PATTERN = re.compile(r"^<\s*([a-zA-Z0-9:_-]+)")
_CLOSE_TAG_PATTERN = re.compile(r"^<\s*/\s*([a-zA-Z0-9:_-]+)")
_SKIP_AUTOLINK_TAGS = {"script", "style", "code", "pre", "math", "svg", "a"}
_URL_PATTERN = re.compile(r"(?P<url>(?:https?://|www\.)[^\s<>\"]+)", re.IGNORECASE)
_DOI_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./-])\bdoi:\s*(?P<doi>10\.\d{4,9}/[^\s<>\"]+)",
    re.IGNORECASE,
)
_BARE_DOI_CONTEXT_PATTERN = re.compile(
    r"(?P<prefix>\b(?:Digital\s+Object\s+Identifier|DOI)\s+)"
    r"(?P<doi>10\.\d{4,9}/[^\s<>\"]+)",
    re.IGNORECASE,
)
_BARE_DOI_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._~:/?#@!$&'()*+,;=%-])"
    r"(?P<doi>10\.\d{4,9}/[^\s<>\"\[\]]+)",
    re.IGNORECASE,
)
_URL_TRAILING_CONNECTOR_RE = re.compile(
    r"^(.*/)(?:and|or|the|to|in|of|for|with|from|at|by|a|an)$",
    re.IGNORECASE,
)
_BROKEN_URL_SPLIT_PATTERN = re.compile(
    r"((?:https?://|www\.)[^\s<>\"]+?/)\s+([A-Za-z0-9][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)",
    re.IGNORECASE,
)
_BROKEN_URL_HOST_SPLIT_PATTERN = re.compile(
    r"\b(?P<host>arxi)\s+(?P<tail>v\.org)\b",
    re.IGNORECASE,
)
_BROKEN_DOI_SPLIT_PATTERN = re.compile(
    r"(?P<prefix>\b(?:doi:\s*|(?:Digital\s+Object\s+Identifier|DOI)\s+)?)"
    r"(?P<head>10\.\d{4,9}/)\s+"
    r"(?P<tail>[A-Za-z0-9][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)",
    re.IGNORECASE,
)


def _update_skip_stack(tag_fragment: str, skip_stack: list[str]) -> None:
    raw = tag_fragment[:256].lstrip()
    if not raw.startswith("<") or raw.startswith("<!--") or raw.startswith("<!"):
        return

    close_match = _CLOSE_TAG_PATTERN.match(raw)
    if close_match is not None:
        tag_name = close_match.group(1).lower()
        for idx in range(len(skip_stack) - 1, -1, -1):
            if skip_stack[idx] == tag_name:
                del skip_stack[idx]
                break
        return

    if raw.endswith("/>"):
        return

    open_match = _OPEN_TAG_PATTERN.match(raw)
    if open_match is None:
        return
    tag_name = open_match.group(1).lower()
    if tag_name in _SKIP_AUTOLINK_TAGS:
        skip_stack.append(tag_name)


def autolink_text_urls(text: str) -> str:
    lower_text = text.lower()
    if "http" not in lower_text and "www." not in lower_text and "doi" not in lower_text and "10." not in text:
        return text
    if len(text) > 50000:
        return text

    repaired_text = _BROKEN_URL_SPLIT_PATTERN.sub(r"\1\2", text)
    repaired_text = _BROKEN_URL_HOST_SPLIT_PATTERN.sub(r"\g<host>\g<tail>", repaired_text)
    repaired_text = _BROKEN_DOI_SPLIT_PATTERN.sub(r"\g<prefix>\g<head>\g<tail>", repaired_text)

    doi_placeholders: list[str] = []

    def _stash_doi_anchor(anchor: str) -> str:
        doi_placeholders.append(anchor)
        return f"\x00Z2MDOI{len(doi_placeholders) - 1}\x00"

    def _restore_doi_anchors(value: str) -> str:
        for index, anchor in enumerate(doi_placeholders):
            value = value.replace(f"\x00Z2MDOI{index}\x00", anchor)
        return value

    def _doi_anchor(core_doi: str) -> str:
        return (
            f'<a href="https://doi.org/{core_doi}" target="_blank" '
            f'rel="noopener noreferrer">{core_doi}</a>'
        )

    def replace_doi(match: re.Match[str]) -> str:
        raw_doi = match.group("doi")
        core_doi, trailing = split_url_and_trailing_punct(raw_doi)
        if not core_doi:
            return match.group(0)
        return f"doi:{_stash_doi_anchor(_doi_anchor(core_doi))}{trailing}"

    def replace_bare_doi(match: re.Match[str]) -> str:
        raw_doi = match.group("doi")
        core_doi, trailing = split_url_and_trailing_punct(raw_doi)
        if not core_doi:
            return match.group(0)
        return f"{_stash_doi_anchor(_doi_anchor(core_doi))}{trailing}"

    protected_text = _DOI_PATTERN.sub(replace_doi, repaired_text)
    protected_text = _BARE_DOI_CONTEXT_PATTERN.sub(
        lambda m: f"{m.group('prefix')}{replace_bare_doi(m)}",
        protected_text,
    )
    protected_text = _BARE_DOI_PATTERN.sub(replace_bare_doi, protected_text)

    def replace_url(match: re.Match[str]) -> str:
        raw_url = match.group("url")
        core_url, trailing = split_url_and_trailing_punct(raw_url)
        if not core_url:
            return raw_url

        connector_match = _URL_TRAILING_CONNECTOR_RE.match(core_url)
        if connector_match:
            stripped = connector_match.group(1)
            connector_word = core_url[len(stripped) :]
            core_url = stripped
            trailing = connector_word + trailing

        href = core_url
        if core_url.lower().startswith("www."):
            href = f"https://{core_url}"

        return (
            f'<a href="{href}" target="_blank" rel="noopener noreferrer">{core_url}</a>'
            f"{trailing}"
        )

    linked = _URL_PATTERN.sub(replace_url, protected_text)
    return _restore_doi_anchors(linked)


def autolink_plain_urls(html: str) -> str:
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        low = part.lower()
        if "&lt;a " in low or "&lt;/a&gt;" in low:
            out.append(part)
            continue
        out.append(autolink_text_urls(part))

    return "".join(out)
