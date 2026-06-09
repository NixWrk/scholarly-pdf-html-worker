from __future__ import annotations

from pdf_html_translator.cli import translate_html
from zoteropdf2md.translation import lmstudio_client as packaged_lmstudio_client
from experiments.lmstudio_instruct_translation import lmstudio_client as experiment_lmstudio_client


def test_translate_cli_delegates_to_packaged_runner(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_main(argv):
        calls.append(tuple(argv or ()))
        return 7

    monkeypatch.setattr(translate_html, "run_html_probe_main", fake_main)

    assert translate_html.main(["--root", "articles"]) == 7
    assert calls == [("--root", "articles")]


def test_experiment_lmstudio_client_is_packaged_client_wrapper() -> None:
    assert experiment_lmstudio_client.LMStudioConfig is packaged_lmstudio_client.LMStudioConfig
    assert experiment_lmstudio_client.LMStudioInstructTranslator is packaged_lmstudio_client.LMStudioInstructTranslator
