from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf_html_polish.pipeline import run_pipeline, run_raw_html_pipeline
from pdf_html_polish.pipeline_options import PipelineOptions

from pdf_html_polish.runtime_temp import (
    RUNTIME_OWNER_SUFFIX,
    RUNTIME_TEMP_DIRNAME,
    cleanup_runtime_temp_root,
    runtime_temp_root,
)


def _owner_path(run_dir: Path) -> Path:
    return run_dir.parent / f"{run_dir.name}{RUNTIME_OWNER_SUFFIX}"


def test_runtime_temp_roots_are_run_scoped_and_cleanup_preserves_live_sibling(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    first = runtime_temp_root(output_dir)
    (first / "first.txt").write_text("first", encoding="utf-8")
    second = runtime_temp_root(output_dir)
    (second / "second.txt").write_text("second", encoding="utf-8")

    assert first != second
    assert first.parent == second.parent == output_dir / RUNTIME_TEMP_DIRNAME
    assert first.is_dir()
    assert second.is_dir()

    assert cleanup_runtime_temp_root(first) is True
    assert not first.exists()
    assert (second / "second.txt").read_text(encoding="utf-8") == "second"
    assert cleanup_runtime_temp_root(second) is True
    assert not (output_dir / RUNTIME_TEMP_DIRNAME).exists()


def test_runtime_temp_root_prunes_owner_from_dead_process_generation(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    stale = runtime_temp_root(output_dir)
    stale_owner = _owner_path(stale)
    payload = json.loads(stale_owner.read_text(encoding="utf-8"))
    payload["process_create_time"] = float(payload["process_create_time"]) - 3600.0
    stale_owner.write_text(json.dumps(payload), encoding="utf-8")
    (stale / "partial.pdf").write_bytes(b"partial")

    current = runtime_temp_root(output_dir)

    assert not stale.exists()
    assert not stale_owner.exists()
    assert current.is_dir()
    assert cleanup_runtime_temp_root(current) is True


def test_runtime_temp_root_keeps_live_owned_sibling_during_prune(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    first = runtime_temp_root(output_dir)
    second = runtime_temp_root(output_dir)

    assert first.is_dir()
    assert _owner_path(first).is_file()
    assert second.is_dir()

    assert cleanup_runtime_temp_root(first) is True
    assert cleanup_runtime_temp_root(second) is True


def test_cleanup_runtime_temp_root_refuses_unmanaged_path(tmp_path: Path) -> None:
    unmanaged = tmp_path / "unmanaged"
    unmanaged.mkdir()

    with pytest.raises(ValueError, match="unmanaged runtime path"):
        cleanup_runtime_temp_root(unmanaged)

    assert unmanaged.is_dir()


def test_raw_pipeline_failure_cleans_only_its_owned_runtime_dir(tmp_path: Path) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF")
    output_dir = tmp_path / "output"
    live_sibling = runtime_temp_root(output_dir)
    sibling_payload = live_sibling / "sibling.bin"
    sibling_payload.write_bytes(b"live")

    class FailingRunner:
        def run_batch(self, **_kwargs: object) -> object:
            raise RuntimeError("marker failed")

        def run_single(self, **_kwargs: object) -> object:  # pragma: no cover
            raise AssertionError("single fallback must not run")

    with pytest.raises(RuntimeError, match="marker failed"):
        run_raw_html_pipeline(
            PipelineOptions(
                source_pdf_paths=[str(source_pdf)],
                output_dir=str(output_dir),
                export_mode="html",
            ),
            FailingRunner(),  # type: ignore[arg-type]
            lambda _message: None,
            lambda: False,
        )

    container = output_dir / RUNTIME_TEMP_DIRNAME
    remaining_run_dirs = sorted(
        path
        for path in container.iterdir()
        if path.is_dir() and path.name.startswith("run_")
    )
    assert remaining_run_dirs == [live_sibling]
    assert sibling_payload.read_bytes() == b"live"
    assert cleanup_runtime_temp_root(live_sibling) is True


def test_raw_pipeline_validates_before_creating_runtime_temp(tmp_path: Path) -> None:
    output_dir = tmp_path / "raw-output"

    with pytest.raises(ValueError, match="requires direct --pdf inputs"):
        run_raw_html_pipeline(
            PipelineOptions(
                source_pdf_paths=None,
                output_dir=str(output_dir),
                export_mode="html",
            ),
            object(),  # type: ignore[arg-type]
            lambda _message: None,
            lambda: False,
        )

    assert not (output_dir / RUNTIME_TEMP_DIRNAME).exists()


def test_full_pipeline_validates_before_creating_runtime_temp(tmp_path: Path) -> None:
    source_pdf = tmp_path / "paper.pdf"
    source_pdf.write_bytes(b"%PDF")
    output_dir = tmp_path / "full-output"

    with pytest.raises(ValueError, match="cannot use Zotero export mode"):
        run_pipeline(
            PipelineOptions(
                source_pdf_paths=[str(source_pdf)],
                output_dir=str(output_dir),
                export_mode="zotero_single_html",
            ),
            object(),  # type: ignore[arg-type]
            lambda _message: None,
            lambda: False,
        )

    assert not (output_dir / RUNTIME_TEMP_DIRNAME).exists()
