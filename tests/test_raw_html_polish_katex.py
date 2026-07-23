import pytest

from pdf_html_polish.raw_html_polish import katex


def _ensure_head(html: str) -> str:
    if "</head>" in html:
        return html
    return f"<head></head>{html}"


def test_render_katex_html_uses_static_renderer_and_injects_css(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeContext:
        def call(self, _name: str, items: list[dict[str, object]]) -> list[str]:
            assert items == [{"t": "x < y", "d": False}]
            return ["<span class='katex'>x &lt; y</span>"]

    monkeypatch.setattr(katex, "katex_v8_context", lambda: FakeContext())
    monkeypatch.setattr(katex, "katex_inlined_css", lambda: ".katex{}")

    rendered = katex.render_katex_html("<html><head></head><body>\\(x < y\\)</body></html>", ensure_head=_ensure_head)

    assert 'data-z2m-style="katex"' in rendered
    assert 'class="z2m-math z2m-math-inline"' in rendered
    assert 'data-z2m-tex="\\(x &lt; y\\)"' in rendered
    assert "<span class='katex'>x &lt; y</span>" in rendered


def test_render_katex_html_falls_back_to_mathjax_when_renderer_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_context() -> object:
        raise ImportError("mini-racer unavailable")

    monkeypatch.setattr(katex, "katex_v8_context", missing_context)

    rendered = katex.render_katex_html("<body>\\[x\\]</body>", ensure_head=_ensure_head)

    assert 'id="MathJax-script"' in rendered
    assert "\\[x\\]" in rendered


def test_render_katex_html_leaves_tex_inside_code_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_context() -> object:
        raise AssertionError("KaTeX context should not be requested")

    monkeypatch.setattr(katex, "katex_v8_context", fail_context)

    html = "<html><head></head><body><code>\\(x\\)</code></body></html>"

    assert katex.render_katex_html(html, ensure_head=_ensure_head) == html


def test_render_katex_html_unwraps_text_heavy_math_without_loading_renderer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_context() -> object:
        raise AssertionError("KaTeX context should not be requested")

    monkeypatch.setattr(katex, "katex_v8_context", fail_context)
    html = (
        r"<body>\(\mbox{Quality estimation of the measured signals of ICG: "
        r"$0,1$ - not acceptable; $2,3$-acceptable }\)</body>"
    )

    rendered = katex.render_katex_html(html, ensure_head=_ensure_head)

    assert "z2m-math" not in rendered
    assert "katex-error" not in rendered
    assert "$0,1$" not in rendered
    assert "Quality estimation of the measured signals of ICG" in rendered
    assert "0,1 - not acceptable; 2,3-acceptable" in rendered


def test_render_katex_html_keeps_short_text_command_as_math(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeContext:
        def call(self, _name: str, items: list[dict[str, object]]) -> list[str]:
            assert items == [{"t": r"\mbox{if}", "d": False}]
            return ["<span class='katex'>if</span>"]

    monkeypatch.setattr(katex, "katex_v8_context", lambda: FakeContext())
    monkeypatch.setattr(katex, "katex_inlined_css", lambda: ".katex{}")

    rendered = katex.render_katex_html(
        r"<html><head></head><body>\(\mbox{if}\)</body></html>",
        ensure_head=_ensure_head,
    )

    assert 'class="z2m-math z2m-math-inline"' in rendered
    assert r'data-z2m-tex="\(\mbox{if}\)"' in rendered


def test_strip_mathjax_scripts_removes_config_and_loader() -> None:
    html = (
        "<head><script>MathJax={tex:{}}</script>"
        '<script id="MathJax-script" src="mathjax.js"></script></head><body>x</body>'
    )

    assert katex.strip_mathjax_scripts(html) == "<head></head><body>x</body>"
