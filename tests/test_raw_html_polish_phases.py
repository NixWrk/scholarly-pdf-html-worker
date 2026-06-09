from zoteropdf2md.raw_html_polish import DEFAULT_POLISH_PHASES, default_polish_phase_names
from zoteropdf2md.single_file_html import polish_html_phase_names


def test_raw_html_polish_phase_order_is_stable() -> None:
    phase_names = default_polish_phase_names()

    assert phase_names == polish_html_phase_names()
    assert phase_names[0] == "pre_cleanup"
    assert phase_names[-1] == "katex_and_final_repairs"
    assert len(phase_names) == len(set(phase_names))
    assert len(DEFAULT_POLISH_PHASES) == len(phase_names)


def test_raw_html_polish_phase_metadata_has_purpose_text() -> None:
    assert all(phase.purpose for phase in DEFAULT_POLISH_PHASES)
