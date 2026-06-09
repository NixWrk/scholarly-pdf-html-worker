from __future__ import annotations

from pdf_html_translator.cli import translate_html


def test_translate_cli_delegates_to_packaged_runner(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_main(argv):
        calls.append(tuple(argv or ()))
        return 7

    monkeypatch.setattr(translate_html, "run_html_probe_main", fake_main)

    assert translate_html.main(["--root", "articles"]) == 7
    assert calls == [("--root", "articles")]
