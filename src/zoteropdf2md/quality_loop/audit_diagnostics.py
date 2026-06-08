"""Diagnostic metadata and defect construction for EN polish audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zoteropdf2md.quality_loop.audit_blocks import Block, Defect


@dataclass(frozen=True)
class DiagnosticSpec:
    id: str
    detector: str
    summary: str
    audit_signal: str
    repair_hint: str
    quality_counted_by_default: bool = True


DIAGNOSTIC_SPECS: dict[str, DiagnosticSpec] = {
    "P04": DiagnosticSpec(
        id="P04",
        detector="_citation_defects",
        summary="Unlinked body citation range/list despite available bibliography targets.",
        audit_signal="Searches non-reference body blocks for bracket or superscript numeric ranges that were not linked to #ref-*.",
        repair_hint="Citation linkification and bibliography target recovery.",
    ),
    "P04M": DiagnosticSpec(
        id="P04M",
        detector="_citation_defects",
        summary="Citation-like numeric range appears in math or measurement context.",
        audit_signal="Splits math/measurement candidates away from body P04 so they can be reviewed as telemetry.",
        repair_hint="Citation false-positive guards for math, measurements, and numeric vectors.",
        quality_counted_by_default=False,
    ),
    "P04N": DiagnosticSpec(
        id="P04N",
        detector="_citation_defects",
        summary="Citation-like numeric range has no recognized reference targets.",
        audit_signal="Reports bracket/superscript citation candidates when the document lacks matching ref-N bibliography IDs.",
        repair_hint="Bibliography target recovery from HTML/PDF-backed reference evidence.",
        quality_counted_by_default=False,
    ),
    "P04R": DiagnosticSpec(
        id="P04R",
        detector="_citation_defects",
        summary="Citation range points at missing reference IDs in an otherwise recognized bibliography.",
        audit_signal="Expands candidate citation numbers and compares them against existing ref-N targets.",
        repair_hint="Bibliography continuation split, merge, and reference ID gap repair.",
        quality_counted_by_default=False,
    ),
    "P04T": DiagnosticSpec(
        id="P04T",
        detector="_citation_defects",
        summary="Citation-like numeric range appears in table/float context.",
        audit_signal="Separates table, affiliation-table, and float numeric ranges from body citation misses.",
        repair_hint="Table-specific citation policy and numeric-range false-positive guards.",
        quality_counted_by_default=False,
    ),
    "P35": DiagnosticSpec(
        id="P35",
        detector="_replacement_char_defects",
        summary="Unicode replacement character remains visible.",
        audit_signal="Searches polish HTML for U+FFFD and records PDF text-layer evidence when source noise explains it.",
        repair_hint="Raw symbol diagnostics, OCR/text-layer triage, or EN polish table-symbol repair.",
        quality_counted_by_default=False,
    ),
    "P45M": DiagnosticSpec(
        id="P45M",
        detector="_manual_blind_spot_defects",
        summary="Known manual-review pattern in metadata, front matter, or layout cleanup.",
        audit_signal="Pattern-based scanner for recently observed non-quality blind spots.",
        repair_hint="Manual review triage or narrow EN polish cleanup rule.",
        quality_counted_by_default=False,
    ),
    "P45S": DiagnosticSpec(
        id="P45S",
        detector="_manual_blind_spot_defects",
        summary="Known manual-review pattern in section/body split cleanup.",
        audit_signal="Pattern-based scanner for accepted telemetry around section/body boundaries.",
        repair_hint="Manual review triage or sentence-boundary repair rule.",
        quality_counted_by_default=False,
    ),
    "P61": DiagnosticSpec(
        id="P61",
        detector="_visible_figure_target_defects",
        summary="Visible figure reference has no matching semantic figure target.",
        audit_signal="Scans body prose for Figure/Fig references and compares them with fig-* targets and nearby links.",
        repair_hint="Figure target wrapping, figure extraction, or accepted telemetry for source-missing figures.",
        quality_counted_by_default=False,
    ),
    "P62": DiagnosticSpec(
        id="P62",
        detector="_figure_caption_ux_defects",
        summary="Visible missing-figure warning with no nearby recovered image.",
        audit_signal="Parses z2m-missing-figure-warning blocks and classifies nearby image/caption context.",
        repair_hint="Marker image extraction, PDF-backed image recovery, or review packaging.",
        quality_counted_by_default=False,
    ),
    "P62A": DiagnosticSpec(
        id="P62A",
        detector="_classify_missing_figure_warning",
        summary="Stale missing-figure warning is adjacent to a same-label image/caption.",
        audit_signal="Matches warning label against nearby image and caption labels.",
        repair_hint="Figure image/caption association cleanup.",
        quality_counted_by_default=False,
    ),
    "P62B": DiagnosticSpec(
        id="P62B",
        detector="_classify_missing_figure_warning",
        summary="Missing-figure warning has nearby image content but ambiguous label match.",
        audit_signal="Finds nearby image offsets, then records ambiguity when label evidence is not strong enough.",
        repair_hint="Figure image/caption association and manual review packaging.",
        quality_counted_by_default=False,
    ),
    "P71": DiagnosticSpec(
        id="P71",
        detector="_known_ocr_token_defects",
        summary="Known OCR token or phrase remains in polish text.",
        audit_signal="Searches final polish plain text for curated manual-review OCR residue tokens and PDF-layer evidence.",
        repair_hint="Targeted OCR cleanup rule or accepted telemetry classification when the source PDF layer already contains it.",
        quality_counted_by_default=False,
    ),
}


def diagnostic_spec(defect_id: str) -> DiagnosticSpec | None:
    return DIAGNOSTIC_SPECS.get(defect_id)


def make_defect(
    *,
    defect_id: str,
    cc_class: str,
    check: str,
    severity: str,
    block: Block | None,
    snippet: str,
    stage: str,
    hypothesis: str,
    proposed_fix_layer: str,
    regression_test: str,
    extra: dict[str, Any] | None = None,
) -> Defect:
    return Defect(
        id=defect_id,
        cc_class=cc_class,
        check=check,
        severity=severity,
        snippet=snippet[:260],
        line=block.line if block is not None else None,
        first_broken_stage=stage,
        hypothesis=hypothesis,
        proposed_fix_layer=proposed_fix_layer,
        regression_test=regression_test,
        extra=extra or {},
    )
