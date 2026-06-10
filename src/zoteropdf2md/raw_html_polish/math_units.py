"""Math and scientific-unit cleanup helpers for raw HTML polish."""

from __future__ import annotations

import re

from .katex import STATIC_DISPLAY_TEX_PATTERN, STATIC_INLINE_TEX_PATTERN


MATH_TAG_PATTERN = re.compile(r"<math(\b[^>]*)>(.*?)</math>", re.IGNORECASE | re.DOTALL)

# Marker sometimes emits citation superscripts as MathJax inline math:
# \(^{157}\) or \(^{153-156}\) instead of <sup>157</sup>.
LATEX_SUP_CITATION_PATTERN = re.compile(
    r'\\\(\^\{([\d,\s\-\u2013\u2014]+)\}\\\)',
)
LATEX_SUP_CITATION_BARE_PATTERN = re.compile(
    r'\\\(\^([\d,\s\-\u2013\u2014]+)\\\)',
)
INLINE_TEX_PATTERN = re.compile(r'\\\((.*?)\\\)', re.DOTALL)
INLINE_TEX_TRAILING_BRACKET_CITATION_PATTERN = re.compile(
    r"(?P<core>[\s\S]*?)\s*(?P<cite>\[\s*\d{1,3}(?:\s*(?:,|[-\u2013\u2014])\s*\d{1,3})*\s*\])\s*$"
)
OMEGA_ZERO_RATIO_OCR_PATTERN = re.compile(r"\\frac\{\\omega\}\{2m\}(?=\s*=\s*1)")

# Quick-scan trigger: only run the subscript-spill fix when this substring exists.
SUBSCRIPT_OPEN = re.compile(r'[_^]\{')
# Detect an = followed immediately by a "large" LaTeX command inside a subscript/
# superscript brace. This is the Marker OCR artefact where the equation
# continuation was accidentally included in the sub/superscript.
SUBSCRIPT_SPILL_RE = re.compile(
    r'=\s*\\(?:frac|sqrt|sum|int|oint|prod|lim|sup|inf|max|min|sin|cos|tan|'
    r'exp|log|ln|left|right|bigl|bigr|Big|Bigl|Bigr|begin|end)\b'
)

LATEX_LABEL_PATTERN = re.compile(r"\\label\{[^{}]*\}")
LATEX_TEXTBF_PATTERN = re.compile(r"\\textbf\{([^{}]*)\}")
LATEX_ITALIC_PATTERN = re.compile(r"\\(?:textit|emph)\{([^{}]*)\}")
LATEX_TEXTRM_PATTERN = re.compile(r"\\textrm\{([^{}]*)\}")
LATEX_TEXT_PATTERN = re.compile(r"\\text\{([^{}]*)\}")


def fix_subscript_equation_spill(html: str) -> str:
    """Fix Marker OCR artefact where equation continuations enter sub/superscripts."""
    if not SUBSCRIPT_OPEN.search(html):
        return html

    out: list[str] = []
    i = 0
    n = len(html)

    while i < n:
        ch = html[i]
        if ch not in ("_", "^") or i + 1 >= n or html[i + 1] != "{":
            out.append(ch)
            i += 1
            continue

        brace_open = i + 1
        content_start = i + 2
        depth = 0
        close_pos = -1
        for k in range(brace_open, n):
            if html[k] == "{":
                depth += 1
            elif html[k] == "}":
                depth -= 1
                if depth == 0:
                    close_pos = k
                    break

        if close_pos == -1:
            out.append(html[i])
            i += 1
            continue

        content = html[content_start:close_pos]

        spill = SUBSCRIPT_SPILL_RE.search(content)
        if spill is None:
            out.append(html[i : close_pos + 1])
            i = close_pos + 1
            continue

        eq_pos = spill.start()
        before_eq = content[:eq_pos]
        after_eq = content[eq_pos + 1 :]
        out.append(f"{ch}{{{before_eq}}}={after_eq}")
        i = close_pos + 1

    return "".join(out)


def fix_latex_text_commands(html: str) -> str:
    html = LATEX_LABEL_PATTERN.sub("", html)
    html = LATEX_TEXTBF_PATTERN.sub(r"<strong>\1</strong>", html)
    html = LATEX_ITALIC_PATTERN.sub(r"<em>\1</em>", html)
    html = LATEX_TEXTRM_PATTERN.sub(r"\1", html)
    html = LATEX_TEXT_PATTERN.sub(r"\1", html)
    html = re.sub(r"(\b\d+(?:\.\d+)?)\s*<i>\s*\\\\m\s*\.\s*</i>", r"\1 µm.", html, flags=re.IGNORECASE)
    html = re.sub(r"(\b\d+(?:\.\d+)?)\s*<i>\s*\\\\m\s*</i>", r"\1 µm", html, flags=re.IGNORECASE)
    return html


def move_trailing_bracket_citations_out_of_inline_tex(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        expr = match.group(1)
        cite_match = INLINE_TEX_TRAILING_BRACKET_CITATION_PATTERN.match(expr)
        if cite_match is None:
            return match.group(0)
        core = cite_match.group("core").rstrip()
        cite = cite_match.group("cite")
        if not core:
            return match.group(0)
        return f"\\({core}\\) {cite}"

    return INLINE_TEX_PATTERN.sub(replace, html)


def latex_group_end(text: str, open_pos: int) -> int:
    if open_pos < 0 or open_pos >= len(text) or text[open_pos] != "{":
        return -1
    depth = 0
    escaped = False
    for pos in range(open_pos, len(text)):
        ch = text[pos]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return pos
    return -1


def latex_brace_balance(text: str) -> int:
    balance = 0
    escaped = False
    for ch in text:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "{":
            balance += 1
        elif ch == "}":
            balance -= 1
    return balance


def skip_latex_spaces(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def repair_sqrt_subscript_brace_spill(tex: str) -> str:
    r"""Repair OCR that closes a ``\frac`` denominator before a sqrt subscript."""
    if "\\frac" not in tex or "\\sqrt" not in tex or "_{" not in tex:
        return tex
    if latex_brace_balance(tex) >= 0:
        return tex

    replacements: list[tuple[int, int, str]] = []
    search_from = 0
    while True:
        frac_pos = tex.find(r"\frac", search_from)
        if frac_pos < 0:
            break
        pos = skip_latex_spaces(tex, frac_pos + len(r"\frac"))
        if pos >= len(tex) or tex[pos] != "{":
            search_from = frac_pos + len(r"\frac")
            continue

        numerator_end = latex_group_end(tex, pos)
        if numerator_end < 0:
            break
        denom_open = skip_latex_spaces(tex, numerator_end + 1)
        if denom_open >= len(tex) or tex[denom_open] != "{":
            search_from = numerator_end + 1
            continue

        denom_body = skip_latex_spaces(tex, denom_open + 1)
        if not tex.startswith(r"\sqrt", denom_body):
            search_from = denom_open + 1
            continue
        sqrt_group_open = skip_latex_spaces(tex, denom_body + len(r"\sqrt"))
        if sqrt_group_open >= len(tex) or tex[sqrt_group_open] != "{":
            search_from = denom_body + len(r"\sqrt")
            continue

        sqrt_group_end = latex_group_end(tex, sqrt_group_open)
        if sqrt_group_end < 0:
            break
        premature_denom_close = skip_latex_spaces(tex, sqrt_group_end + 1)
        if premature_denom_close >= len(tex) or tex[premature_denom_close] != "}":
            search_from = sqrt_group_end + 1
            continue
        if latex_group_end(tex, denom_open) != premature_denom_close:
            search_from = premature_denom_close + 1
            continue

        subscript_marker = skip_latex_spaces(tex, premature_denom_close + 1)
        if subscript_marker >= len(tex) or tex[subscript_marker] != "_":
            search_from = premature_denom_close + 1
            continue
        subscript_open = skip_latex_spaces(tex, subscript_marker + 1)
        if subscript_open >= len(tex) or tex[subscript_open] != "{":
            search_from = subscript_marker + 1
            continue
        subscript_end = latex_group_end(tex, subscript_open)
        if subscript_end < 0:
            break
        subscript_body = tex[subscript_open + 1 : subscript_end]
        if not re.fullmatch(r"[A-Za-z0-9,\s]+", subscript_body) or len(subscript_body) > 24:
            search_from = subscript_end + 1
            continue

        delayed_denom_close = skip_latex_spaces(tex, subscript_end + 1)
        if delayed_denom_close >= len(tex) or tex[delayed_denom_close] != "}":
            search_from = subscript_end + 1
            continue

        sqrt_body = tex[sqrt_group_open + 1 : sqrt_group_end]
        replacement = r"{\sqrt{\frac{" + sqrt_body + "}{" + subscript_body.strip() + r"}}}"
        replacements.append((denom_open, delayed_denom_close + 1, replacement))
        search_from = delayed_denom_close + 1

    if not replacements:
        return tex
    repaired = tex
    for start, end, replacement in sorted(replacements, reverse=True):
        repaired = repaired[:start] + replacement + repaired[end:]
    return repaired


def repair_latex_parse_artifacts(tex: str) -> str:
    return repair_sqrt_subscript_brace_spill(tex)


def repair_common_math_ocr_substitutions(html: str) -> str:
    html = OMEGA_ZERO_RATIO_OCR_PATTERN.sub(r"\\frac{\\omega}{\\omega_0}", html)
    html = STATIC_DISPLAY_TEX_PATTERN.sub(
        lambda m: f"\\[{repair_latex_parse_artifacts(m.group('body'))}\\]",
        html,
    )
    return STATIC_INLINE_TEX_PATTERN.sub(
        lambda m: f"\\({repair_latex_parse_artifacts(m.group('body'))}\\)",
        html,
    )


def convert_math_tags_to_tex(html: str) -> str:
    """Convert raw-LaTeX <math> elements into MathJax-renderable delimiters."""

    def replace_math(match: re.Match[str]) -> str:
        attrs = match.group(1)
        content = match.group(2).strip()
        if not content:
            return ""
        if re.search(r"<[a-zA-Z]", content):
            return match.group(0)
        is_block = bool(
            re.search(r'\bdisplay\s*=\s*["\']block["\']', attrs, re.IGNORECASE)
        )
        if is_block:
            return f"\\[{content}\\]"
        return f"\\({content}\\)"

    return MATH_TAG_PATTERN.sub(replace_math, html)


def convert_latex_sup_citations(html: str) -> str:
    r"""Convert Marker's LaTeX superscript citations to ``<sup>`` tags."""
    html = LATEX_SUP_CITATION_PATTERN.sub(r"<sup>\1</sup>", html)
    return LATEX_SUP_CITATION_BARE_PATTERN.sub(r"<sup>\1</sup>", html)
