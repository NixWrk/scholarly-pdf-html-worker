"""Documented pass order for raw/Marker HTML polishing."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True)
class PolishPhase:
    name: str
    purpose: str


@dataclass(frozen=True)
class RawPolishContext:
    table_caption_language: str
    enable_citation_linkify: bool
    citation_profile: Any | None = None
    image_cache: Mapping[str, str] | None = None
    language_policy: Any | None = None


@dataclass(frozen=True)
class RawPolishState:
    html: str
    found_sections: Any = field(default_factory=dict)
    found_figures: Any = field(default_factory=dict)
    found_tables: Any = field(default_factory=dict)
    found_boxes: Any = field(default_factory=dict)

    def with_html(self, html: str) -> RawPolishState:
        return replace(self, html=html)

    def with_updates(self, **updates: Any) -> RawPolishState:
        return replace(self, **updates)


RawPolishStep = Callable[[RawPolishState, RawPolishContext], RawPolishState]


@dataclass(frozen=True)
class ExecutablePolishPhase(PolishPhase):
    run: RawPolishStep


DEFAULT_POLISH_PHASES: tuple[PolishPhase, ...] = (
    PolishPhase("pre_cleanup", "Remove repeated page furniture, publisher chrome, and malformed wrapper noise."),
    PolishPhase("math_and_units", "Repair math, units, formulas, and table transforms before structural grouping."),
    PolishPhase("frontmatter_and_footnotes", "Normalize title/frontmatter blocks and footnote/endnote material."),
    PolishPhase("semantic_targets", "Recover headings, anchors, sections, and internal link targets."),
    PolishPhase("references_and_links", "Recover reference sections, link citations, and sanitize outgoing URLs."),
    PolishPhase("float_units", "Group figures, tables, captions, and late link/text repairs."),
    PolishPhase("presentation", "Inject readable document styles and wrap the body in the stable article container."),
    PolishPhase("katex_and_final_repairs", "Render KaTeX and run final text/layout repair passes."),
)


def default_polish_phase_names() -> tuple[str, ...]:
    """Return the stable raw HTML polish phase order."""

    return tuple(phase.name for phase in DEFAULT_POLISH_PHASES)


def run_polish_phases(
    html: str,
    *,
    context: RawPolishContext,
    phases: Iterable[ExecutablePolishPhase],
) -> RawPolishState:
    """Run executable raw-polish phases in order and return the final state."""

    state = RawPolishState(html=html)
    for phase in phases:
        state = phase.run(state, context)
        if not isinstance(state, RawPolishState):
            raise TypeError(f"Raw polish phase {phase.name!r} returned {type(state)!r}")
    return state
