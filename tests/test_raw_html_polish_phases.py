import pytest

from pdf_html_polish.raw_html_polish import (
    DEFAULT_POLISH_PHASES,
    ExecutablePolishPhase,
    RawPolishContext,
    RawPolishState,
    default_polish_phase_names,
    run_polish_phases,
)
from pdf_html_polish.single_file_html import _raw_html_polish_phases, polish_html_phase_names


def test_raw_html_polish_phase_order_is_stable() -> None:
    phase_names = default_polish_phase_names()

    assert phase_names == polish_html_phase_names()
    assert phase_names[0] == "pre_cleanup"
    assert phase_names[-1] == "katex_and_final_repairs"
    assert len(phase_names) == len(set(phase_names))
    assert len(DEFAULT_POLISH_PHASES) == len(phase_names)


def test_raw_html_polish_phase_metadata_has_purpose_text() -> None:
    assert all(phase.purpose for phase in DEFAULT_POLISH_PHASES)


def test_raw_html_polish_executable_phases_match_documented_order() -> None:
    executable_phases = _raw_html_polish_phases()

    assert executable_phases is _raw_html_polish_phases()
    assert tuple(phase.name for phase in executable_phases) == default_polish_phase_names()
    assert all(isinstance(phase, ExecutablePolishPhase) for phase in executable_phases)
    assert all(callable(phase.run) for phase in executable_phases)


def test_run_polish_phases_carries_state_in_order() -> None:
    calls: list[str] = []

    def first(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
        calls.append(context.table_caption_language)
        return state.with_updates(html=state.html + "a", found_sections={"s1": "S1"})

    def second(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
        calls.append(context.table_caption_language)
        return state.with_html(state.html + state.found_sections["s1"])

    result = run_polish_phases(
        "",
        context=RawPolishContext(table_caption_language="en", enable_citation_linkify=True),
        phases=(
            ExecutablePolishPhase("first", "first test phase", first),
            ExecutablePolishPhase("second", "second test phase", second),
        ),
    )

    assert result.html == "aS1"
    assert calls == ["en", "en"]
    assert [timing["phase"] for timing in result.phase_timings] == ["first", "second"]
    assert result.phase_timings[0]["input_chars"] == 0
    assert result.phase_timings[0]["output_chars"] == 1
    assert result.phase_timings[1]["input_chars"] == 1
    assert result.phase_timings[1]["output_chars"] == 3
    assert all(timing["seconds"] >= 0 for timing in result.phase_timings)


def test_run_polish_phases_rejects_invalid_phase_return() -> None:
    def broken(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
        del context
        return state.html  # type: ignore[return-value]

    with pytest.raises(TypeError, match="Raw polish phase 'broken' returned"):
        run_polish_phases(
            "html",
            context=RawPolishContext(table_caption_language="en", enable_citation_linkify=True),
            phases=(ExecutablePolishPhase("broken", "broken test phase", broken),),
        )
