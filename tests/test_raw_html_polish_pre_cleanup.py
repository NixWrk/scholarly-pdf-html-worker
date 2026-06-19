from pdf_html_polish.raw_html_polish.pre_cleanup import (
    cleanup_marker_escape_artifacts,
    fix_common_mojibake,
    strip_protocol_sentinel_leaks,
)


def test_fix_common_mojibake_repairs_known_marker_sequences() -> None:
    assert fix_common_mojibake("\u0432\u0402\u201d dash") == "\u2014 dash"
    assert fix_common_mojibake("\u0412\u00b5m") == "\u00b5m"


def test_cleanup_marker_escape_artifacts_repairs_prose_but_preserves_tex() -> None:
    html = r"<p>alpha \ | \ beta \(x \\ y\) word\" tail</p>"

    assert cleanup_marker_escape_artifacts(html) == r'<p>alpha | beta \(x \\ y\) word" tail</p>'


def test_strip_protocol_sentinel_leaks_removes_internal_tokens() -> None:
    html = "<p>Intro @@Z2M_HSEP@@, , -ABC tail @@Z2M_A12@@.</p>"

    assert strip_protocol_sentinel_leaks(html) == "<p>Intro , ABC tail .</p>"
