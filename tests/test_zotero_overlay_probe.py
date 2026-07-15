from __future__ import annotations

import json
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
        old_cache = os.environ.get(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV)
        os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = str(probe_path)
        os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = str(tmp_path / "cache")
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
            if old_cache is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = old_cache

        assert result.generated
        assert result.attempted
        assert output_path.is_file()
        assert calls
        assert calls[0][:3] == ["node", str(probe_path.resolve()), str(pdf_path.resolve())]
        assert "--out" in calls[0]
        assert str(output_path.resolve()) in calls[0]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_zotero_overlay_json_reuses_content_cache() -> None:
    tmp_path = _workspace_tmp()
    try:
        pdf_path = tmp_path / "article.pdf"
        pdf_path.write_bytes(b"%PDF same content\n")
        probe_path = tmp_path / "zotero_overlay_probe.mjs"
        probe_path.write_text("// fake probe\n", encoding="utf-8")
        first_output = tmp_path / "first.overlays.json"
        second_output = tmp_path / "second.overlays.json"
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            Path(command[command.index("--out") + 1]).write_text(
                '{"summary":{"citations":[{"text":"[1]"}]}}\n',
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "ok", "")

        old_probe = os.environ.get(zotero_overlay_probe.OVERLAY_PROBE_ENV)
        old_cache = os.environ.get(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV)
        os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = str(probe_path)
        os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = str(tmp_path / "cache")
        try:
            with patch.object(zotero_overlay_probe, "run", fake_run):
                first = zotero_overlay_probe.generate_zotero_overlay_json(pdf_path, first_output)
                second = zotero_overlay_probe.generate_zotero_overlay_json(pdf_path, second_output)
        finally:
            if old_probe is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_PROBE_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = old_probe
            if old_cache is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = old_cache

        assert first.generated
        assert first.attempted
        assert second.generated
        assert not second.attempted
        assert first_output.read_text(encoding="utf-8") == second_output.read_text(encoding="utf-8")
        assert len(calls) == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_zotero_overlay_json_cache_misses_when_pdf_content_changes() -> None:
    tmp_path = _workspace_tmp()
    try:
        pdf_path = tmp_path / "article.pdf"
        pdf_path.write_bytes(b"%PDF first\n")
        probe_path = tmp_path / "zotero_overlay_probe.mjs"
        probe_path.write_text("// fake probe\n", encoding="utf-8")
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            Path(command[command.index("--out") + 1]).write_text(
                f'{{"summary":{{"calls":{len(calls)}}}}}\n',
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "ok", "")

        old_probe = os.environ.get(zotero_overlay_probe.OVERLAY_PROBE_ENV)
        old_cache = os.environ.get(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV)
        os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = str(probe_path)
        os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = str(tmp_path / "cache")
        try:
            with patch.object(zotero_overlay_probe, "run", fake_run):
                first = zotero_overlay_probe.generate_zotero_overlay_json(pdf_path, tmp_path / "first.json")
                pdf_path.write_bytes(b"%PDF changed\n")
                second = zotero_overlay_probe.generate_zotero_overlay_json(pdf_path, tmp_path / "second.json")
        finally:
            if old_probe is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_PROBE_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = old_probe
            if old_cache is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = old_cache

        assert first.generated
        assert second.generated
        assert len(calls) == 2
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_find_zotero_pdfjs_dir_uses_local_vendor_checkout() -> None:
    tmp_path = _workspace_tmp()
    try:
        local_pdfjs = tmp_path / ".tmp_local2" / "vendor" / "zotero-pdfjs"
        local_pdfjs.mkdir(parents=True)
        old_pdfjs = os.environ.pop(zotero_overlay_probe.PDFJS_DIR_ENV, None)
        try:
            with patch.object(zotero_overlay_probe, "_repo_root", lambda: tmp_path):
                assert zotero_overlay_probe.find_zotero_pdfjs_dir() == local_pdfjs.resolve(strict=False)
        finally:
            if old_pdfjs is not None:
                os.environ[zotero_overlay_probe.PDFJS_DIR_ENV] = old_pdfjs
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_find_zotero_pdfjs_dir_accepts_compat_env() -> None:
    tmp_path = _workspace_tmp()
    try:
        pdfjs_dir = tmp_path / "zotero-pdfjs"
        pdfjs_dir.mkdir()
        old_pdfjs = os.environ.pop(zotero_overlay_probe.PDFJS_DIR_ENV, None)
        old_compat = os.environ.get(zotero_overlay_probe.PDFJS_COMPAT_DIR_ENV)
        os.environ[zotero_overlay_probe.PDFJS_COMPAT_DIR_ENV] = str(pdfjs_dir)
        try:
            assert zotero_overlay_probe.find_zotero_pdfjs_dir() == pdfjs_dir.resolve(strict=False)
        finally:
            if old_pdfjs is not None:
                os.environ[zotero_overlay_probe.PDFJS_DIR_ENV] = old_pdfjs
            if old_compat is None:
                os.environ.pop(zotero_overlay_probe.PDFJS_COMPAT_DIR_ENV, None)
            else:
                os.environ[zotero_overlay_probe.PDFJS_COMPAT_DIR_ENV] = old_compat
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


def test_generate_zotero_overlay_json_rejects_stale_output() -> None:
    tmp_path = _workspace_tmp()
    try:
        pdf_path = tmp_path / "article.pdf"
        pdf_path.write_bytes(b"%PDF-1.7\n")
        probe_path = tmp_path / "zotero_overlay_probe.mjs"
        probe_path.write_text("// fake probe\n", encoding="utf-8")
        output_path = tmp_path / "article.overlays.json"
        output_path.write_text('{"summary":{"stale":true}}', encoding="utf-8")

        old_probe = os.environ.get(zotero_overlay_probe.OVERLAY_PROBE_ENV)
        old_cache = os.environ.get(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV)
        os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = str(probe_path)
        os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = str(tmp_path / "cache")
        try:
            with patch.object(
                zotero_overlay_probe,
                "run",
                return_value=subprocess.CompletedProcess([], 0, "ok", ""),
            ):
                result = zotero_overlay_probe.generate_zotero_overlay_json(pdf_path, output_path)
        finally:
            if old_probe is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_PROBE_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = old_probe
            if old_cache is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = old_cache

        assert result.attempted
        assert not result.generated
        assert "invalid JSON" in result.error
        assert not output_path.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_zotero_overlay_json_removes_partial_output_on_timeout() -> None:
    tmp_path = _workspace_tmp()
    try:
        pdf_path = tmp_path / "article.pdf"
        pdf_path.write_bytes(b"%PDF-1.7\n")
        probe_path = tmp_path / "zotero_overlay_probe.mjs"
        probe_path.write_text("// fake probe\n", encoding="utf-8")
        output_path = tmp_path / "article.overlays.json"

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            output_path.write_text('{"summary":', encoding="utf-8")
            raise subprocess.TimeoutExpired(command, 3, output=b"bad:\xff", stderr=b"timed out")

        old_probe = os.environ.get(zotero_overlay_probe.OVERLAY_PROBE_ENV)
        old_cache = os.environ.get(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV)
        os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = str(probe_path)
        os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = str(tmp_path / "cache")
        try:
            with patch.object(zotero_overlay_probe, "run", fake_run):
                result = zotero_overlay_probe.generate_zotero_overlay_json(
                    pdf_path,
                    output_path,
                    timeout_seconds=3,
                )
        finally:
            if old_probe is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_PROBE_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = old_probe
            if old_cache is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = old_cache

        assert result.attempted
        assert not result.generated
        assert "timed out" in result.error
        assert isinstance(result.stdout, str)
        assert "bad:" in result.stdout
        assert result.stderr == "timed out"
        assert not output_path.exists()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_generate_zotero_overlay_json_ignores_corrupt_cache() -> None:
    tmp_path = _workspace_tmp()
    try:
        pdf_path = tmp_path / "article.pdf"
        pdf_path.write_bytes(b"%PDF cache key\n")
        probe_path = tmp_path / "zotero_overlay_probe.mjs"
        probe_path.write_text("// fake probe\n", encoding="utf-8")
        output_path = tmp_path / "article.overlays.json"

        old_probe = os.environ.get(zotero_overlay_probe.OVERLAY_PROBE_ENV)
        old_cache = os.environ.get(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV)
        os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = str(probe_path)
        os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = str(tmp_path / "cache")
        try:
            cached = zotero_overlay_probe._cached_overlay_path(pdf_path)
            cached.parent.mkdir(parents=True)
            cached.write_text("not json", encoding="utf-8")

            def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                output_path.write_text('{"summary":{"fresh":true}}', encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "ok", "")

            with patch.object(zotero_overlay_probe, "run", fake_run):
                result = zotero_overlay_probe.generate_zotero_overlay_json(pdf_path, output_path)
        finally:
            if old_probe is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_PROBE_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_PROBE_ENV] = old_probe
            if old_cache is None:
                os.environ.pop(zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV, None)
            else:
                os.environ[zotero_overlay_probe.OVERLAY_CACHE_DIR_ENV] = old_cache

        assert result.attempted
        assert result.generated
        assert json.loads(output_path.read_text(encoding="utf-8"))["summary"] == {"fresh": True}
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
