from __future__ import annotations

import html as html_lib
import re
from difflib import SequenceMatcher


_TABLE_PATTERN = re.compile(
    r"(?P<open><table\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></table>)",
    re.IGNORECASE,
)
_ROW_PATTERN = re.compile(
    r"(?P<open><tr\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></tr>)",
    re.IGNORECASE,
)
_CELL_PATTERN = re.compile(
    r"(?P<open><t[dh]\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></t[dh]>)",
    re.IGNORECASE,
)
_COLSPAN_PATTERN = re.compile(
    r"\s+colspan\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)
_TAG_PATTERN = re.compile(r"<[^>]+>")


def _visible_text(raw: str) -> str:
    text = _TAG_PATTERN.sub(" ", raw)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def _compact_text(text: str) -> str:
    return "".join(char.casefold() for char in text if char.isalnum())


def _alpha_count(text: str) -> int:
    return sum(char.isalpha() for char in text)


def _cells(row_html: str) -> list[re.Match[str]]:
    return list(_CELL_PATTERN.finditer(row_html))


def _cell_text(cell: re.Match[str]) -> str:
    return _visible_text(cell.group("body"))


def _cell_span(cell: re.Match[str]) -> int:
    match = re.search(
        r"\bcolspan\s*=\s*(?:\"(?P<double>\d+)\"|'(?P<single>\d+)'|(?P<bare>\d+))",
        cell.group("open"),
        re.IGNORECASE,
    )
    if match is None:
        return 1
    value = match.group("double") or match.group("single") or match.group("bare")
    return max(1, int(value))


def _phrase_candidates(rows: list[str]) -> dict[str, str]:
    candidates: dict[str, str] = {}
    for row_html in rows:
        for cell in _cells(row_html):
            if not cell.group("open").lower().startswith("<th"):
                continue
            text = _cell_text(cell)
            words = [word for word in text.split() if any(char.isalpha() for char in word)]
            compact = _compact_text(text)
            if not 2 <= len(words) <= 8 or _alpha_count(text) < 8 or len(compact) > 80:
                continue
            candidates.setdefault(compact, text)
    return candidates


def _open_with_colspan(open_tag: str, colspan: int) -> str:
    normalized = _COLSPAN_PATTERN.sub("", open_tag)
    if colspan <= 1:
        return normalized
    return f'{normalized[:-1].rstrip()} colspan="{colspan}">'


def _best_fragment_phrase(
    cells: list[re.Match[str]],
    *,
    start: int,
    candidates: dict[str, str],
) -> tuple[int, str] | None:
    best: tuple[float, int, str] | None = None
    for end in range(start + 2, min(len(cells), start + 4) + 1):
        sequence = cells[start:end]
        if any(not cell.group("open").lower().startswith("<th") for cell in sequence):
            break
        texts = [_cell_text(cell) for cell in sequence]
        if any(not text for text in texts):
            break
        components = {_compact_text(text) for text in texts}
        joined = "".join(_compact_text(text) for text in texts)
        if len(joined) < 8:
            continue
        for candidate_compact, candidate_text in candidates.items():
            if candidate_compact in components:
                continue
            length_ratio = len(joined) / max(1, len(candidate_compact))
            if not 0.7 <= length_ratio <= 1.3:
                continue
            similarity = SequenceMatcher(None, joined, candidate_compact).ratio()
            if similarity < 0.84:
                continue
            score = (similarity, end - start, candidate_text)
            if best is None or score > best:
                best = score
    if best is None:
        return None
    return start + best[1], best[2]


def _repair_fragmented_phrases(row_html: str, candidates: dict[str, str]) -> str:
    cells = _cells(row_html)
    if len(cells) < 2:
        return row_html
    output: list[str] = []
    cursor = 0
    index = 0
    while index < len(cells):
        cell = cells[index]
        output.append(row_html[cursor : cell.start()])
        match = _best_fragment_phrase(cells, start=index, candidates=candidates)
        if match is None:
            output.append(cell.group(0))
            cursor = cell.end()
            index += 1
            continue
        end, phrase = match
        merged_cells = cells[index:end]
        colspan = sum(_cell_span(item) for item in merged_cells)
        output.append(
            f"{_open_with_colspan(cell.group('open'), colspan)} "
            f"{html_lib.escape(phrase, quote=False)} {cell.group('close')}"
        )
        cursor = merged_cells[-1].end()
        index = end
    output.append(row_html[cursor:])
    return "".join(output)


def _row_is_data(row_html: str) -> bool:
    cells = _cells(row_html)
    if len(cells) < 4:
        return False
    first_text = _cell_text(cells[0])
    tail = [_cell_text(cell) for cell in cells[1:]]
    nonempty = [text for text in tail if text]
    if not first_text or len(nonempty) < 3:
        return False
    nonalpha = sum(_alpha_count(text) == 0 for text in nonempty)
    return len(first_text) <= 32 and nonalpha / len(nonempty) >= 0.7


def _header_block(rows: list[str], start: int) -> list[int]:
    indices = [start]
    for index in range(start + 1, min(len(rows), start + 5)):
        if _row_is_data(rows[index]):
            break
        indices.append(index)
    return indices


def _first_cell_text(row_html: str) -> str:
    cells = _cells(row_html)
    return _cell_text(cells[0]) if cells else ""


def _replace_first_cell(template_row: str, target_row: str) -> str:
    template_cells = _cells(template_row)
    target_cells = _cells(target_row)
    if not template_cells or not target_cells:
        return template_row
    template_cell = template_cells[0]
    return (
        template_row[: template_cell.start()]
        + target_cells[0].group(0)
        + template_row[template_cell.end() :]
    )


def _repair_table(table_html: str) -> str:
    table_match = _TABLE_PATTERN.fullmatch(table_html)
    if table_match is None:
        return table_html
    body = table_match.group("body")
    row_matches = list(_ROW_PATTERN.finditer(body))
    rows = [match.group(0) for match in row_matches]
    if len(rows) < 4:
        return table_html

    positions_by_anchor: dict[str, list[int]] = {}
    for index, row_html in enumerate(rows):
        if _row_is_data(row_html):
            continue
        first = _first_cell_text(row_html)
        anchor = _compact_text(first)
        if _alpha_count(first) >= 4 and len(anchor) <= 80:
            positions_by_anchor.setdefault(anchor, []).append(index)

    candidates = _phrase_candidates(rows)
    replacements: dict[int, str] = {}
    for positions in positions_by_anchor.values():
        if len(positions) < 2:
            continue
        template_indices = _header_block(rows, positions[0])
        if len(template_indices) < 2:
            continue
        template_rows = [
            _repair_fragmented_phrases(rows[index], candidates)
            for index in template_indices
        ]
        template_updates = {
            index: normalized
            for index, normalized in zip(template_indices, template_rows)
            if normalized != rows[index]
        }

        template_cell_count = sum(len(_cells(row_html)) for row_html in template_rows)
        template_last = _compact_text(_first_cell_text(template_rows[-1]))
        template_text = _compact_text(" ".join(_visible_text(row) for row in template_rows))
        for target_start in positions[1:]:
            target_indices = _header_block(rows, target_start)
            if len(target_indices) != len(template_indices):
                continue
            target_rows = [rows[index] for index in target_indices]
            target_last = _compact_text(_first_cell_text(target_rows[-1]))
            target_cell_count = sum(len(_cells(row_html)) for row_html in target_rows)
            target_text = _compact_text(" ".join(_visible_text(row) for row in target_rows))
            if template_last != target_last:
                continue
            if target_cell_count < template_cell_count + 4:
                continue
            if SequenceMatcher(None, template_text, target_text).ratio() < 0.45:
                continue
            replacements.update(template_updates)
            for target_index, template_row, target_row in zip(
                target_indices, template_rows, target_rows
            ):
                source_first = _first_cell_text(template_row)
                target_first = _first_cell_text(target_row)
                replacement = template_row
                if (
                    _compact_text(source_first) != _compact_text(target_first)
                    and _alpha_count(target_first) >= 4
                ):
                    replacement = _replace_first_cell(template_row, target_row)
                replacements[target_index] = replacement

    if not replacements:
        return table_html
    output: list[str] = []
    cursor = 0
    for index, row_match in enumerate(row_matches):
        output.append(body[cursor : row_match.start()])
        output.append(replacements.get(index, row_match.group(0)))
        cursor = row_match.end()
    output.append(body[cursor:])
    repaired_body = "".join(output)
    return f"{table_match.group('open')}{repaired_body}{table_match.group('close')}"


def repair_repeated_fragmented_table_headers(html: str) -> str:
    """Restore page-split table headers from a cleaner header in the same table."""
    return _TABLE_PATTERN.sub(lambda match: _repair_table(match.group(0)), html)
