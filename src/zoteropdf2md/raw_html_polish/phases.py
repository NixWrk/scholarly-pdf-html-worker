"""Documented pass order for raw/Marker HTML polishing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolishPhase:
    name: str
    purpose: str


DEFAULT_POLISH_PHASES: tuple[PolishPhase, ...] = (
    PolishPhase("pre_cleanup", "Remove repeated page furniture, publisher chrome, and malformed wrapper noise."),
    PolishPhase("math_and_units", "Repair math, units, formulas, and table transforms before structural grouping."),
    PolishPhase("frontmatter_and_footnotes", "Normalize title/frontmatter blocks and footnote/endnote material."),
    PolishPhase("semantic_targets", "Recover headings, anchors, sections, and internal link targets."),
    PolishPhase("references_and_links", "Recover reference sections, link citations, and sanitize outgoing URLs."),
    PolishPhase("float_units", "Group figures, tables, captions, and related cross-reference targets."),
    PolishPhase("presentation", "Inject readable document styles and wrap the body in the stable article container."),
    PolishPhase("katex_and_final_repairs", "Render KaTeX and run final text/layout repair passes."),
)


def default_polish_phase_names() -> tuple[str, ...]:
    """Return the stable raw HTML polish phase order."""

    return tuple(phase.name for phase in DEFAULT_POLISH_PHASES)
