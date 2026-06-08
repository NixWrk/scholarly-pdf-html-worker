from __future__ import annotations

from zoteropdf2md.quality_loop.audit_blocks import Defect, snippet
from zoteropdf2md.quality_loop.audit_diagnostics import make_defect
from zoteropdf2md.quality_loop.audit_manual_patterns import replacement_chars_are_pdf_source_noise


def replacement_char_defects(polish_html: str, pdf_text: str, *, stage: str) -> list[Defect]:
    replacement_pos = polish_html.find("\ufffd")
    if replacement_pos == -1:
        return []

    replacement_extra: dict[str, object] = {"count": polish_html.count("\ufffd")}
    if replacement_chars_are_pdf_source_noise(polish_html, pdf_text):
        replacement_extra.update(
            {
                "quality_counted": False,
                "source_pdf_text_layer_evidence": (
                    "replacement characters align with source PDF text-layer symbol/OCR loss"
                ),
            }
        )

    return [
        make_defect(
            defect_id="P35",
            cc_class="CC-04/CC-13",
            check="Unicode replacement character remains visible",
            severity="warning",
            block=None,
            snippet=snippet(polish_html, replacement_pos, replacement_pos + 1),
            stage=stage,
            hypothesis="A symbol was lost during PDF/OCR/html decoding, often a comparison sign or table significance mark.",
            proposed_fix_layer="raw symbol diagnostics and EN polish table-symbol repair",
            regression_test="Audit reports U+FFFD in table headers, footnotes, and scientific symbols.",
            extra=replacement_extra,
        )
    ]
