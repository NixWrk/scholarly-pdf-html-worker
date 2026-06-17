from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import uuid
from unittest.mock import patch

from pdf_html_polish import zotero_overlay_probe


def _workspace_tmp() -> Path:
    path = Path(".tmp_local2") / f"z2m_overlay_probe_test_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve(strict=False)


def test_generate_zotero_overlay_json_invokes_probe_and_writes_output() -> None:
    tmp_path = _workspace_tmp()
    try:
        pdf_path = tmp_path / "article.pdf"
        pdf_path.write_bytes(b"%PDF-1.7\n")
        probe_path = tmp_path / "zotero_overlay_probe.mjs"
        probe_path.write_text("// fake probe\n", encoding="utf-8")
        output_path = tmp_path / "article.overlays.json"
        calls: list[list[str]] = []

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            output_path.write_text('{"summary":{"citations":[]}}\n', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "ok", "")

        old_probe = os.environ.get(zotero_overlay_probe.OVERLAY_PROBE_ENV)
        old_pdfjs = os.environ.pop(zotero_overlay_probe.PDFJS_DIR_ENV, None)
        os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = str(probe_path)
        try:
            with patch.object(zotero_overlay_probe, "run", fake_run):
                result = zotero_overlay_probe.generate_zotero_overlay_json(pdf_path, output_path)
        finally:
            if old_probe is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_PROBE_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = old_probe
            if old_pdfjs is not None:
                os.environ[zotero_overlay_probe.PDFJS_DIR_ENV] = old_pdfjs

        assert result.generated
        assert result.attempted
        assert output_path.is_file()
        assert calls
        assert calls[0][:3] == ["node", str(probe_path.resolve()), str(pdf_path.resolve())]
        assert "--out" in calls[0]
        assert str(output_path.resolve()) in calls[0]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_zotero_overlay_json_reports_missing_probe() -> None:
    tmp_path = _workspace_tmp()
    try:
        old_probe = os.environ.get(zotero_overlay_probe.OVERLAY_PROBE_ENV)
        os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = str(tmp_path / "missing.mjs")
        try:
            with patch.object(zotero_overlay_probe, "_repo_root", lambda: tmp_path):
                result = zotero_overlay_probe.generate_zotero_overlay_json(
                    tmp_path / "article.pdf",
                    tmp_path / "article.overlays.json",
                )
        finally:
            if old_probe is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_PROBE_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = old_probe

        assert not result.attempted
        assert not result.generated
        assert "not found" in result.error
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
