from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

import pdf_html_polish.quality_loop.audit_command_provenance as audit_provenance
import pdf_html_polish.quality_loop.commands as audit_commands
from pdf_html_polish.quality_loop.audit_command_provenance import (
    AuditCommandProvenanceError,
    file_record,
    validate_audit_command_report,
)
from pdf_html_polish.quality_loop.commands import run_audit


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _stage_pair(root: Path, article: str) -> tuple[Path, Path, Path]:
    article_root = root / article
    stage_dir = article_root / "_z2m_stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    raw_path = stage_dir / "01.en.raw.html"
    polish_path = stage_dir / "02.en.polish.html"
    raw_path.write_text(f"<html><body><p>{article} raw.</p></body></html>", encoding="utf-8")
    polish_path.write_text(f"<html><body><p>{article} polish.</p></body></html>", encoding="utf-8")
    return article_root, raw_path.resolve(strict=False), polish_path.resolve(strict=False)


def _reports(run_dir: Path) -> tuple[dict, dict]:
    audit = json.loads((run_dir / "audit_full_checks.json").read_text(encoding="utf-8"))
    command = json.loads((run_dir / "audit_command_report.json").read_text(encoding="utf-8"))
    return audit, command


def test_real_audit_command_report_validates_exact_subprocess_output(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"

    run_audit(run_dir, roots=[root])
    audit, command = _reports(run_dir)

    validate_audit_command_report(run_dir, audit, command)
    assert command["schema_version"] == 3
    assert command["command_output"] == command["audit_output"]
    assert command["code_manifest"]["files"]
    assert command["environment_overrides"] == {
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
    }


def test_run_audit_forces_and_attests_subprocess_environment_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    captured_environment: dict[str, str] = {}
    real_popen = audit_commands.subprocess.Popen

    def capturing_popen(*args, **kwargs):
        captured_environment.update(kwargs["env"])
        return real_popen(*args, **kwargs)

    monkeypatch.setenv("PYTHONHASHSEED", "random")
    monkeypatch.setenv("PYTHONIOENCODING", "cp1251")
    monkeypatch.setattr(audit_commands.subprocess, "Popen", capturing_popen)

    run_audit(run_dir, roots=[root])
    audit, command = _reports(run_dir)
    expected = {
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
    }

    assert command["environment_overrides"] == expected
    assert {name: captured_environment[name] for name in expected} == expected
    validate_audit_command_report(run_dir, audit, command)


@pytest.mark.parametrize("filename", ["audit_stdout.log", "audit_stderr.log"])
def test_run_audit_unlinks_existing_hardlinked_logs_before_writing(
    tmp_path: Path,
    filename: str,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sentinel = tmp_path / f"outside_{filename}"
    sentinel.write_text("keep", encoding="utf-8")
    os.link(sentinel, run_dir / filename)

    run_audit(run_dir, roots=[root])

    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert (run_dir / filename).is_file()


def test_run_audit_rejects_link_like_run_directory_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run-link"
    monkeypatch.setattr(
        audit_commands,
        "path_is_link_like",
        lambda path: Path(path) == run_dir,
    )

    with pytest.raises(ValueError, match="Audit run directory is link-like"):
        run_audit(run_dir, roots=[root])

    assert not (run_dir / "audit_stdout.log").exists()
    assert not (run_dir / "audit_stderr.log").exists()


def test_run_audit_rejects_lexically_aliased_run_directory(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    alias_parent = tmp_path / "unused"
    alias_parent.mkdir()
    run_alias = alias_parent / ".." / "run"

    with pytest.raises(ValueError, match="Audit run directory must be canonical"):
        run_audit(run_alias, roots=[root])

    assert not (tmp_path / "run" / "audit_stdout.log").exists()
    assert not (tmp_path / "run" / "audit_stderr.log").exists()


def test_run_audit_rejects_link_like_log_before_opening(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    stdout_path = run_dir / "audit_stdout.log"
    stdout_path.write_text("keep", encoding="utf-8")
    real_path_is_link_like = audit_commands.path_is_link_like

    def simulated_link_like(path: Path) -> bool:
        candidate = Path(path).resolve(strict=False)
        return (
            candidate == stdout_path.resolve(strict=False)
            or real_path_is_link_like(path)
        )

    monkeypatch.setattr(
        audit_commands,
        "path_is_link_like",
        simulated_link_like,
    )

    with pytest.raises(ValueError, match="Existing audit stdout is link-like"):
        run_audit(run_dir, roots=[root])

    assert stdout_path.read_text(encoding="utf-8") == "keep"
    assert not (run_dir / "audit_full_checks.json").exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("started_at", None),
        ("started_at", "2026-01-01"),
        ("started_at", "2026-01-01T00:00:00"),
        ("started_at", "2026-01-01T00:00:00Z"),
        ("started_at", "2026-01-01 00:00:00+00:00"),
        ("started_at", "2026-01-01T03:00:00+03:00"),
        ("finished_at", False),
    ],
)
def test_audit_command_rejects_noncanonical_utc_timestamps(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    audit, command = _reports(run_dir)
    command[field] = value

    with pytest.raises(
        AuditCommandProvenanceError,
        match=rf"audit_command_{field}_invalid",
    ):
        validate_audit_command_report(run_dir, audit, command)


def test_audit_command_rejects_reversed_timestamp_interval(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    audit, command = _reports(run_dir)
    command["started_at"] = "2026-01-01T00:00:01+00:00"
    command["finished_at"] = "2026-01-01T00:00:00+00:00"

    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_command_timestamp_order_invalid",
    ):
        validate_audit_command_report(run_dir, audit, command)


@pytest.mark.parametrize(
    ("generated_at", "reason"),
    [
        ("2026-01-01T00:00:00Z", "audit_report_generated_at_invalid"),
        ("1970-01-01T00:00:00+00:00", "audit_report_generated_at_outside_command"),
        ("9999-01-01T00:00:00+00:00", "audit_report_generated_at_outside_command"),
    ],
)
def test_audit_report_generated_at_is_canonical_and_within_command_interval(
    tmp_path: Path,
    generated_at: str,
    reason: str,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    audit, command = _reports(run_dir)
    audit["generated_at"] = generated_at
    _write_json(run_dir / "audit_full_checks.json", audit)
    output_record = file_record(run_dir / "audit_full_checks.json", label="audit_output")
    command["command_output"] = dict(output_record)
    command["audit_output"] = dict(output_record)

    with pytest.raises(AuditCommandProvenanceError, match=reason):
        validate_audit_command_report(run_dir, audit, command)


@pytest.mark.parametrize("mutation", ["missing", "not-object", "extra", "wrong"])
def test_audit_command_rejects_environment_override_mutations(
    tmp_path: Path,
    mutation: str,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    audit, command = _reports(run_dir)

    if mutation == "missing":
        command.pop("environment_overrides")
        reason = "audit_command_report_schema_invalid"
    elif mutation == "not-object":
        command["environment_overrides"] = []
        reason = "audit_command_environment_overrides_invalid"
    elif mutation == "extra":
        command["environment_overrides"]["SECRET"] = "must-not-be-recorded"
        reason = "audit_command_environment_overrides_invalid"
    else:
        command["environment_overrides"]["PYTHONIOENCODING"] = "cp1251"
        reason = "audit_command_environment_overrides_invalid"

    with pytest.raises(AuditCommandProvenanceError, match=reason):
        validate_audit_command_report(run_dir, audit, command)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("repo-alias", "audit_command_repo_root_invalid"),
        ("relative-root", "audit_command_root_invalid"),
        ("root-alias", "audit_command_root_not_canonical"),
        ("output-type", "audit_command_output_path_invalid"),
        ("record-relative", "audit_output_path_invalid"),
        ("record-alias", "audit_output_path_not_canonical"),
        ("stdout-alias", "audit_stdout_path_mismatch"),
        ("stderr-outside", "audit_stderr_path_mismatch"),
        ("cache-relative", "audit_command_cache_dir_invalid"),
    ],
)
def test_audit_command_rejects_path_edge_mutations(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    audit, command = _reports(run_dir)

    if mutation == "repo-alias":
        command["repo_root"] = str(Path(command["repo_root"]) / "src" / "..")
    elif mutation == "relative-root":
        command["roots"] = ["source"]
    elif mutation == "root-alias":
        command["roots"] = [str(root / "unused" / "..")]
    elif mutation == "output-type":
        command["output_path"] = False
    elif mutation == "record-relative":
        command["audit_output"]["path"] = "audit_full_checks.json"
    elif mutation == "record-alias":
        output = Path(command["audit_output"]["path"])
        command["audit_output"]["path"] = str(
            output.parent / "unused" / ".." / output.name
        )
    elif mutation == "stdout-alias":
        command["stdout_path"] = str(run_dir / "unused" / ".." / "audit_stdout.log")
    elif mutation == "stderr-outside":
        command["stderr_path"] = str(tmp_path / "audit_stderr.log")
    else:
        command["pdf_diagnostics_cache_dir"] = "relative-cache"

    with pytest.raises(AuditCommandProvenanceError, match=reason):
        validate_audit_command_report(run_dir, audit, command)


def test_audit_command_rejects_run_snapshot_outside_run_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    source_pdf = tmp_path / "doc.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    source_map = tmp_path / "source_pdf_map.json"
    _write_json(source_map, {"Doc": str(source_pdf)})
    run_dir = tmp_path / "run"
    run_audit(
        run_dir,
        roots=[root],
        enable_pdf_diagnostics=True,
        pdf_map_path=source_map,
    )
    audit, command = _reports(run_dir)
    source_snapshot = Path(command["pdf_map_input"]["source_snapshot"]["path"])
    outside_snapshot = tmp_path / "outside_source_map.json"
    outside_snapshot.write_bytes(source_snapshot.read_bytes())
    command["pdf_map_input"]["source_snapshot"] = file_record(
        outside_snapshot,
        label="outside_source_map",
    )

    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_pdf_map_source_snapshot_outside_run",
    ):
        validate_audit_command_report(run_dir, audit, command)


def test_audit_command_rejects_link_like_artifact_record_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    audit, command = _reports(run_dir)
    synthetic_link = run_dir / "audit_output_link.json"
    monkeypatch.setattr(
        audit_provenance,
        "path_is_link_like",
        lambda path: Path(path) == synthetic_link,
    )
    command["audit_output"]["path"] = str(synthetic_link)

    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_output_path_link_like",
    ):
        validate_audit_command_report(run_dir, audit, command)


def test_stage_pdf_diagnostics_bind_current_source_content(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _article_root, raw_path, _polish_path = _stage_pair(root, "Doc")
    source_pdf = raw_path.parent / "00.source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 stage\n")
    run_dir = tmp_path / "run"

    run_audit(run_dir, roots=[root], enable_pdf_diagnostics=True)
    audit, command = _reports(run_dir)
    summary = audit["articles"][0]["summary"]

    assert summary["source_pdf_origin"] == "stage"
    assert summary["source_pdf_path"] == str(source_pdf)
    assert summary["source_pdf_present"] is True
    assert summary["source_pdf_bytes"] == source_pdf.stat().st_size
    validate_audit_command_report(run_dir, audit, command)

    source_pdf.write_bytes(b"%PDF-1.4 changed after audit\n")
    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_report_pdf_stage_fingerprint_mismatch:Doc",
    ):
        validate_audit_command_report(run_dir, audit, command)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("missing-field", "audit_command_report_schema_invalid"),
        ("argv", "audit_command_argv_mismatch"),
        ("code", "audit_code_manifest_mismatch"),
        ("stdout-tail", "audit_stdout_tail_mismatch"),
        ("output", "audit_output_fingerprint_mismatch"),
        ("duplicate-root", "audit_command_roots_duplicate"),
        ("returncode", "audit_command_returncode_invalid"),
        ("output-path", "audit_command_output_path_invalid"),
    ],
)
def test_audit_command_report_rejects_provenance_mutations(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    audit, command = _reports(run_dir)

    if mutation == "missing-field":
        command.pop("python_version")
    elif mutation == "argv":
        command["command"] = ["forged-audit"]
    elif mutation == "code":
        command["code_manifest"]["sha256"] = "0" * 64
    elif mutation == "stdout-tail":
        command["stdout_tail"] = "forged"
    elif mutation == "output":
        command["audit_output"]["sha256"] = "0" * 64
    elif mutation == "duplicate-root":
        command["roots"].append(command["roots"][0])
    elif mutation == "returncode":
        command["returncode"] = 1
    elif mutation == "output-path":
        command["output_path"] = str(run_dir / "other.json")
    else:  # pragma: no cover - parameter list is exhaustive
        raise AssertionError(mutation)

    with pytest.raises(AuditCommandProvenanceError, match=reason):
        validate_audit_command_report(run_dir, audit, command)


def test_pdf_map_uses_immutable_snapshot_and_rejects_snapshot_mutation(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    source_pdf = tmp_path / "doc.pdf"
    source_pdf_bytes = b"%PDF-1.4\n"
    source_pdf.write_bytes(source_pdf_bytes)
    source_map = tmp_path / "source_pdf_map.json"
    _write_json(source_map, {"Doc": str(source_pdf)})
    run_dir = tmp_path / "run"

    run_audit(
        run_dir,
        roots=[root],
        enable_pdf_diagnostics=True,
        pdf_map_path=source_map,
    )
    audit, command = _reports(run_dir)
    map_input = command["pdf_map_input"]
    source_map_snapshot = Path(map_input["source_snapshot"]["path"])
    materialized_map_snapshot = Path(map_input["materialized_snapshot"]["path"])
    materialized_map_bytes = materialized_map_snapshot.read_bytes()
    pdf_source = map_input["pdf_sources"][0]
    source_pdf_snapshot = Path(pdf_source["snapshot"]["path"])
    article = audit["articles"][0]
    summary = article["summary"]

    assert pdf_source["article"] == "Doc"
    assert pdf_source["source"]["path"] == str(source_pdf.resolve(strict=False))
    assert source_pdf_snapshot.read_bytes() == source_pdf_bytes
    assert summary["source_pdf_path"] == str(source_pdf_snapshot)
    assert summary["source_pdf_bytes"] == len(source_pdf_bytes)
    assert summary["source_pdf_sha256"] == pdf_source["snapshot"]["sha256"]
    assert json.loads(materialized_map_snapshot.read_text(encoding="utf-8")) == {
        "Doc": str(source_pdf_snapshot)
    }

    _write_json(source_map, {"forged": str(tmp_path / "other.pdf")})
    source_pdf.write_bytes(b"changed outside immutable run")
    validate_audit_command_report(run_dir, audit, command)
    assert source_pdf_snapshot.read_bytes() == source_pdf_bytes

    materialized_map_snapshot.write_text('{"Doc":"forged.pdf"}\n', encoding="utf-8")
    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_pdf_map_materialized_snapshot_fingerprint_mismatch",
    ):
        validate_audit_command_report(run_dir, audit, command)
    materialized_map_snapshot.write_bytes(materialized_map_bytes)

    source_pdf_snapshot.write_bytes(b"tampered run-local PDF")
    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_pdf_source_snapshot_fingerprint_mismatch",
    ):
        validate_audit_command_report(run_dir, audit, command)

    source_pdf_snapshot.write_bytes(source_pdf_bytes)
    source_map_snapshot.write_text('{"forged":"map"}\n', encoding="utf-8")
    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_pdf_map_source_snapshot_fingerprint_mismatch",
    ):
        validate_audit_command_report(run_dir, audit, command)


def test_run_audit_rejects_relative_pdf_map_source_path(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    source_map = tmp_path / "source_pdf_map.json"
    _write_json(source_map, {"Doc": "relative.pdf"})

    with pytest.raises(ValueError, match="Audit PDF map path must be absolute"):
        run_audit(
            tmp_path / "run",
            roots=[root],
            enable_pdf_diagnostics=True,
            pdf_map_path=source_map,
        )


@pytest.mark.parametrize("alias_kind", ["map-source", "pdf-entry"])
def test_run_audit_rejects_lexical_alias_pdf_map_paths(
    tmp_path: Path,
    alias_kind: str,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    source_pdf = tmp_path / "doc.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    alias_parent = tmp_path / "unused"
    alias_parent.mkdir()
    source_map = tmp_path / "source_pdf_map.json"
    source_map_value = str(source_pdf)
    supplied_map_path = source_map
    if alias_kind == "pdf-entry":
        source_map_value = str(alias_parent / ".." / source_pdf.name)
    _write_json(source_map, {"Doc": source_map_value})
    if alias_kind == "map-source":
        supplied_map_path = alias_parent / ".." / source_map.name

    with pytest.raises(ValueError, match="Audit PDF map path must be canonical"):
        run_audit(
            tmp_path / "run",
            roots=[root],
            enable_pdf_diagnostics=True,
            pdf_map_path=supplied_map_path,
        )

@pytest.mark.parametrize("link_kind", ["map-source", "pdf-entry"])
def test_run_audit_rejects_link_like_pdf_map_paths(
    tmp_path: Path,
    link_kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    source_pdf = tmp_path / "doc.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    source_map = tmp_path / "source_pdf_map.json"
    _write_json(source_map, {"Doc": str(source_pdf)})
    synthetic_link = source_map if link_kind == "map-source" else source_pdf
    monkeypatch.setattr(
        audit_commands,
        "path_is_link_like",
        lambda path: Path(path) == synthetic_link,
    )

    with pytest.raises(ValueError, match="Audit PDF map path is link-like"):
        run_audit(
            tmp_path / "run",
            roots=[root],
            enable_pdf_diagnostics=True,
            pdf_map_path=source_map,
        )


@pytest.mark.parametrize(
    ("path_kind", "reason"),
    [
        ("relative", "Audit diagnostics cache path must be absolute"),
        ("lexical-alias", "Audit diagnostics cache path must be canonical"),
    ],
)
def test_run_audit_rejects_noncanonical_pdf_diagnostics_cache_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path_kind: str,
    reason: str,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    if path_kind == "relative":
        monkeypatch.chdir(tmp_path)
        cache_path = Path("cache")
    else:
        alias_parent = tmp_path / "unused"
        alias_parent.mkdir()
        cache_path = alias_parent / ".." / "cache"

    with pytest.raises(ValueError, match=reason):
        run_audit(
            tmp_path / "run",
            roots=[root],
            enable_pdf_diagnostics=True,
            pdf_diagnostics_cache_dir=cache_path,
        )


def test_run_audit_checks_pdf_diagnostics_cache_for_links_before_resolving(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    alias_parent = tmp_path / "unused"
    alias_parent.mkdir()
    synthetic_link = alias_parent / ".." / "cache"
    monkeypatch.setattr(
        audit_commands,
        "path_is_link_like",
        lambda path: Path(path) == synthetic_link,
    )

    with pytest.raises(ValueError, match="Audit diagnostics cache path is link-like"):
        run_audit(
            tmp_path / "run",
            roots=[root],
            enable_pdf_diagnostics=True,
            pdf_diagnostics_cache_dir=synthetic_link,
        )


@pytest.mark.parametrize(
    ("snapshot_kind", "reason"),
    [
        ("source", "audit_pdf_map_source_path_not_canonical:Doc"),
        ("materialized", "audit_pdf_map_materialized_path_not_canonical:Doc"),
    ],
)
def test_audit_command_rejects_aliased_paths_inside_attested_pdf_maps(
    tmp_path: Path,
    snapshot_kind: str,
    reason: str,
) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    source_pdf = tmp_path / "doc.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    source_map = tmp_path / "source_pdf_map.json"
    _write_json(source_map, {"Doc": str(source_pdf)})
    run_dir = tmp_path / "run"
    run_audit(
        run_dir,
        roots=[root],
        enable_pdf_diagnostics=True,
        pdf_map_path=source_map,
    )
    audit, command = _reports(run_dir)
    map_input = command["pdf_map_input"]

    if snapshot_kind == "source":
        snapshot_record = map_input["source_snapshot"]
        target_path = source_pdf
        label = "audit_pdf_map_source_snapshot"
    else:
        snapshot_record = map_input["materialized_snapshot"]
        target_path = Path(map_input["pdf_sources"][0]["snapshot"]["path"])
        label = "audit_pdf_map_materialized_snapshot"
    snapshot_path = Path(snapshot_record["path"])
    alias_parent = target_path.parent / "unused"
    alias_parent.mkdir(exist_ok=True)
    _write_json(snapshot_path, {"Doc": str(alias_parent / ".." / target_path.name)})
    replacement = file_record(snapshot_path, label=label)
    snapshot_record.clear()
    snapshot_record.update(replacement)

    with pytest.raises(AuditCommandProvenanceError, match=reason):
        validate_audit_command_report(run_dir, audit, command)


def test_audit_command_rejects_missing_pdf_source_record(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    source_pdf = tmp_path / "doc.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    source_map = tmp_path / "source_pdf_map.json"
    _write_json(source_map, {"Doc": str(source_pdf)})
    run_dir = tmp_path / "run"
    run_audit(
        run_dir,
        roots=[root],
        enable_pdf_diagnostics=True,
        pdf_map_path=source_map,
    )
    audit, command = _reports(run_dir)
    command["pdf_map_input"]["pdf_sources"] = []

    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_pdf_map_materialization_mismatch",
    ):
        validate_audit_command_report(run_dir, audit, command)


def test_audit_command_rejects_mutated_pdf_summary_identity(tmp_path: Path) -> None:
    root = tmp_path / "source"
    _stage_pair(root, "Doc")
    source_pdf = tmp_path / "doc.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n")
    source_map = tmp_path / "source_pdf_map.json"
    _write_json(source_map, {"Doc": str(source_pdf)})
    run_dir = tmp_path / "run"
    run_audit(
        run_dir,
        roots=[root],
        enable_pdf_diagnostics=True,
        pdf_map_path=source_map,
    )
    audit, command = _reports(run_dir)
    audit["articles"][0]["summary"]["source_pdf_sha256"] = "f" * 64

    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_report_pdf_source_mismatch:Doc",
    ):
        validate_audit_command_report(run_dir, audit, command)


def test_targeted_audit_snapshots_baseline_before_replacing_output(tmp_path: Path) -> None:
    root = tmp_path / "source"
    first_root, _first_raw, first_polish = _stage_pair(root, "First")
    _stage_pair(root, "Second")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    baseline_path = run_dir / "audit_full_checks.json"
    baseline_bytes = baseline_path.read_bytes()

    first_polish.write_text(
        "<html><body><p>First polish changed.</p></body></html>",
        encoding="utf-8",
    )
    run_audit(
        run_dir,
        roots=[first_root],
        merge_previous_report_path=baseline_path,
    )
    audit, command = _reports(run_dir)
    snapshot_path = Path(command["merge_previous_report_input"]["snapshot"]["path"])

    validate_audit_command_report(run_dir, audit, command)
    assert snapshot_path.read_bytes() == baseline_bytes
    assert baseline_path.read_bytes() != baseline_bytes
    assert command["merge_previous_report_path"] == str(snapshot_path)
    assert audit["targeted_audit"]["previous_report_path"] == str(snapshot_path)

    snapshot_path.write_text('{"forged":"baseline"}\n', encoding="utf-8")
    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_merge_previous_input_snapshot_fingerprint_mismatch",
    ):
        validate_audit_command_report(run_dir, audit, command)


def test_targeted_pdf_audit_carries_only_attested_baseline_sources(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    first_root, _first_raw, first_polish = _stage_pair(root, "First")
    _stage_pair(root, "Second")
    first_pdf = tmp_path / "first.pdf"
    second_pdf = tmp_path / "second.pdf"
    first_pdf.write_bytes(b"%PDF-1.4 first\n")
    second_pdf.write_bytes(b"%PDF-1.4 second\n")
    source_map = tmp_path / "source_pdf_map.json"
    _write_json(
        source_map,
        {"First": str(first_pdf), "Second": str(second_pdf)},
    )
    run_dir = tmp_path / "run"
    run_audit(
        run_dir,
        roots=[root],
        enable_pdf_diagnostics=True,
        pdf_map_path=source_map,
    )
    baseline_audit, baseline_command = _reports(run_dir)
    baseline_second = next(
        item for item in baseline_audit["articles"] if item["article"] == "Second"
    )
    baseline_second_source = next(
        item
        for item in baseline_command["pdf_map_input"]["pdf_sources"]
        if item["article"] == "Second"
    )

    first_polish.write_text(
        "<html><body><p>First polish changed.</p></body></html>",
        encoding="utf-8",
    )
    run_audit(
        run_dir,
        roots=[first_root],
        enable_pdf_diagnostics=True,
        pdf_map_path=source_map,
        merge_previous_report_path=run_dir / "audit_full_checks.json",
    )
    audit, command = _reports(run_dir)

    validate_audit_command_report(run_dir, audit, command)
    merge_input = command["merge_previous_report_input"]
    assert merge_input["allowed_changed_articles"] == ["First"]
    assert Path(merge_input["command_snapshot"]["path"]).is_file()
    carried_second = next(
        item for item in audit["articles"] if item["article"] == "Second"
    )
    assert carried_second == baseline_second
    assert (
        carried_second["summary"]["source_pdf_path"]
        == baseline_second_source["snapshot"]["path"]
    )


def _targeted_audit_fixture(
    tmp_path: Path,
    *,
    enable_pdf_diagnostics: bool = False,
) -> tuple[Path, Path, Path | None, dict, dict]:
    root = tmp_path / "source"
    first_root, _first_raw, first_polish = _stage_pair(root, "First")
    _stage_pair(root, "Second")
    run_dir = tmp_path / "run"
    source_map: Path | None = None
    if enable_pdf_diagnostics:
        first_pdf = tmp_path / "first.pdf"
        second_pdf = tmp_path / "second.pdf"
        first_pdf.write_bytes(b"%PDF-1.4 first\n")
        second_pdf.write_bytes(b"%PDF-1.4 second\n")
        source_map = tmp_path / "source_pdf_map.json"
        _write_json(
            source_map,
            {"First": str(first_pdf), "Second": str(second_pdf)},
        )
    run_audit(
        run_dir,
        roots=[root],
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map_path=source_map,
    )
    first_polish.write_text(
        "<html><body><p>First polish changed.</p></body></html>",
        encoding="utf-8",
    )
    run_audit(
        run_dir,
        roots=[first_root],
        enable_pdf_diagnostics=enable_pdf_diagnostics,
        pdf_map_path=source_map,
        merge_previous_report_path=run_dir / "audit_full_checks.json",
    )
    audit, command = _reports(run_dir)
    return run_dir, first_root, source_map, audit, command


def _replace_current_audit(
    run_dir: Path,
    audit: dict,
    command: dict,
) -> dict:
    output_path = run_dir / "audit_full_checks.json"
    _write_json(output_path, audit)
    output_record = file_record(output_path, label="audit_output")
    candidate = copy.deepcopy(command)
    candidate["command_output"] = dict(output_record)
    candidate["audit_output"] = dict(output_record)
    return candidate


def test_targeted_merge_rejects_baseline_command_snapshot_mutations(
    tmp_path: Path,
) -> None:
    run_dir, _first_root, _source_map, audit, command = _targeted_audit_fixture(
        tmp_path
    )
    merge_input = command["merge_previous_report_input"]
    command_snapshot_path = Path(merge_input["command_snapshot"]["path"])
    original_bytes = command_snapshot_path.read_bytes()

    command_snapshot_path.write_bytes(original_bytes + b" ")
    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_merge_previous_command_snapshot_fingerprint_mismatch",
    ):
        validate_audit_command_report(run_dir, audit, command)

    command_snapshot_path.write_bytes(original_bytes)
    baseline_command = json.loads(original_bytes.decode("utf-8"))
    baseline_command["targeted_merge_enabled"] = True
    _write_json(command_snapshot_path, baseline_command)
    merge_input["command_snapshot"] = file_record(
        command_snapshot_path,
        label="audit_merge_previous_command_snapshot",
    )
    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_merge_baseline_not_full",
    ):
        validate_audit_command_report(run_dir, audit, command)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("started-at-alias", "audit_command_started_at_invalid"),
        ("timestamp-order", "audit_command_timestamp_order_invalid"),
        ("generated-at-alias", "audit_report_generated_at_invalid"),
        ("generated-at-outside", "audit_report_generated_at_outside_command"),
        (
            "environment",
            "audit_merge_baseline_command_environment_overrides_mismatch",
        ),
        ("repo-root-alias", "audit_merge_baseline_command_repo_root_mismatch"),
    ],
)
def test_targeted_merge_rejects_coherently_forged_baseline_edge_contracts(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    run_dir, _first_root, _source_map, audit, command = _targeted_audit_fixture(
        tmp_path
    )
    merge_input = command["merge_previous_report_input"]
    report_snapshot_path = Path(merge_input["snapshot"]["path"])
    command_snapshot_path = Path(merge_input["command_snapshot"]["path"])
    baseline_report = json.loads(report_snapshot_path.read_text(encoding="utf-8"))
    baseline_command = json.loads(command_snapshot_path.read_text(encoding="utf-8"))

    if mutation == "started-at-alias":
        baseline_command["started_at"] = "2026-01-01T00:00:00Z"
    elif mutation == "timestamp-order":
        baseline_command["started_at"] = "2026-01-01T00:00:01+00:00"
        baseline_command["finished_at"] = "2026-01-01T00:00:00+00:00"
    elif mutation == "generated-at-alias":
        baseline_report["generated_at"] = "2026-01-01T00:00:00Z"
    elif mutation == "generated-at-outside":
        baseline_report["generated_at"] = "1970-01-01T00:00:00+00:00"
    elif mutation == "environment":
        baseline_command["environment_overrides"]["PYTHONIOENCODING"] = "cp1251"
    else:
        baseline_command["repo_root"] = str(
            Path(baseline_command["repo_root"]) / "src" / ".."
        )

    if mutation.startswith("generated-at"):
        _write_json(report_snapshot_path, baseline_report)
        report_snapshot = file_record(
            report_snapshot_path,
            label="audit_input_snapshot",
        )
        merge_input["snapshot"] = report_snapshot
        baseline_output = dict(report_snapshot)
        baseline_output["path"] = merge_input["source_path"]
        baseline_command["command_output"] = dict(baseline_output)
        baseline_command["audit_output"] = dict(baseline_output)

    _write_json(command_snapshot_path, baseline_command)
    merge_input["command_snapshot"] = file_record(
        command_snapshot_path,
        label="audit_merge_previous_command_snapshot",
    )

    with pytest.raises(AuditCommandProvenanceError, match=reason):
        validate_audit_command_report(run_dir, audit, command)


def test_targeted_merge_rejects_invalid_allowed_changed_article_sets(
    tmp_path: Path,
) -> None:
    run_dir, _first_root, _source_map, audit, command = _targeted_audit_fixture(
        tmp_path
    )
    cases = [
        ([], "audit_merge_allowed_changed_articles_invalid"),
        (["First", "First"], "audit_merge_allowed_changed_articles_invalid"),
        (["Second", "First"], "audit_merge_allowed_changed_articles_invalid"),
        (["First", "Second"], "audit_merge_target_article_set_mismatch"),
    ]
    for changed_articles, reason in cases:
        candidate = copy.deepcopy(command)
        candidate["merge_previous_report_input"][
            "allowed_changed_articles"
        ] = changed_articles
        with pytest.raises(AuditCommandProvenanceError, match=reason):
            validate_audit_command_report(run_dir, audit, candidate)


def test_targeted_merge_still_validates_target_baseline_summary(
    tmp_path: Path,
) -> None:
    run_dir, _first_root, _source_map, audit, command = _targeted_audit_fixture(
        tmp_path
    )
    merge_input = command["merge_previous_report_input"]
    report_snapshot_path = Path(merge_input["snapshot"]["path"])
    command_snapshot_path = Path(merge_input["command_snapshot"]["path"])
    baseline_report = json.loads(report_snapshot_path.read_text(encoding="utf-8"))
    baseline_first = next(
        item for item in baseline_report["articles"] if item["article"] == "First"
    )
    baseline_first["summary"] = "forged"
    _write_json(report_snapshot_path, baseline_report)
    report_snapshot_record = file_record(
        report_snapshot_path,
        label="audit_input_snapshot",
    )
    merge_input["snapshot"] = report_snapshot_record

    baseline_command = json.loads(command_snapshot_path.read_text(encoding="utf-8"))
    baseline_output_record = dict(report_snapshot_record)
    baseline_output_record["path"] = merge_input["source_path"]
    baseline_command["command_output"] = dict(baseline_output_record)
    baseline_command["audit_output"] = dict(baseline_output_record)
    _write_json(command_snapshot_path, baseline_command)
    merge_input["command_snapshot"] = file_record(
        command_snapshot_path,
        label="audit_merge_previous_command_snapshot",
    )

    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_report_summary_invalid:First",
    ):
        validate_audit_command_report(run_dir, audit, command)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("carried-article", "audit_merge_carried_article_mismatch:Second"),
        ("targeted-metadata", "audit_report_targeted_metadata_invalid"),
        ("target-roots", "audit_report_targeted_metadata_invalid"),
    ],
)
def test_targeted_merge_rejects_merged_report_mutations(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    run_dir, _first_root, _source_map, audit, command = _targeted_audit_fixture(
        tmp_path
    )
    candidate_audit = copy.deepcopy(audit)
    if mutation == "carried-article":
        carried = next(
            item
            for item in candidate_audit["articles"]
            if item["article"] == "Second"
        )
        carried["summary"]["polish_blocks"] += 1
    elif mutation == "targeted-metadata":
        candidate_audit["targeted_audit"]["reused_article_count"] += 1
    else:
        candidate_audit["targeted_audit"]["target_roots"] = []
    candidate_command = _replace_current_audit(
        run_dir,
        candidate_audit,
        command,
    )

    with pytest.raises(AuditCommandProvenanceError, match=reason):
        validate_audit_command_report(run_dir, candidate_audit, candidate_command)


def test_targeted_merge_revalidates_baseline_pdf_snapshots(
    tmp_path: Path,
) -> None:
    run_dir, _first_root, _source_map, audit, command = _targeted_audit_fixture(
        tmp_path,
        enable_pdf_diagnostics=True,
    )
    merge_input = command["merge_previous_report_input"]
    baseline_command = json.loads(
        Path(merge_input["command_snapshot"]["path"]).read_text(encoding="utf-8")
    )
    baseline_map = baseline_command["pdf_map_input"]
    second_source = next(
        item
        for item in baseline_map["pdf_sources"]
        if item["article"] == "Second"
    )
    source_snapshot_path = Path(second_source["snapshot"]["path"])
    source_snapshot_bytes = source_snapshot_path.read_bytes()
    source_snapshot_path.write_bytes(source_snapshot_bytes + b"tampered")
    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_pdf_source_snapshot_fingerprint_mismatch",
    ):
        validate_audit_command_report(run_dir, audit, command)

    source_snapshot_path.write_bytes(source_snapshot_bytes)
    map_snapshot_path = Path(baseline_map["source_snapshot"]["path"])
    map_snapshot_bytes = map_snapshot_path.read_bytes()
    map_snapshot_path.write_bytes(map_snapshot_bytes + b" ")
    with pytest.raises(
        AuditCommandProvenanceError,
        match="audit_pdf_map_source_snapshot_fingerprint_mismatch",
    ):
        validate_audit_command_report(run_dir, audit, command)


def test_targeted_run_rejects_targeted_baseline_explicitly(tmp_path: Path) -> None:
    run_dir, first_root, _source_map, _audit, _command = _targeted_audit_fixture(
        tmp_path
    )

    with pytest.raises(ValueError, match="Targeted audit baseline must be a full audit"):
        run_audit(
            run_dir,
            roots=[first_root],
            merge_previous_report_path=run_dir / "audit_full_checks.json",
        )


def test_targeted_preflight_has_no_pdf_snapshot_side_effects_on_mode_mismatch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    first_root, _first_raw, first_polish = _stage_pair(root, "First")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    output_path = run_dir / "audit_full_checks.json"
    command_path = run_dir / "audit_command_report.json"
    baseline_output = output_path.read_bytes()
    baseline_command = command_path.read_bytes()
    source_pdf = tmp_path / "first.pdf"
    source_pdf.write_bytes(b"%PDF-1.4 first\n")
    source_map = tmp_path / "source_pdf_map.json"
    _write_json(source_map, {"First": str(source_pdf)})
    first_polish.write_text(
        "<html><body><p>First polish changed.</p></body></html>",
        encoding="utf-8",
    )
    snapshot_dir = run_dir / "_enrichment_snapshot"
    assert not snapshot_dir.exists()

    with pytest.raises(
        ValueError,
        match="Targeted audit baseline PDF diagnostics mode does not match",
    ):
        run_audit(
            run_dir,
            roots=[first_root],
            enable_pdf_diagnostics=True,
            pdf_map_path=source_map,
            merge_previous_report_path=output_path,
        )

    assert not snapshot_dir.exists()
    assert output_path.read_bytes() == baseline_output
    assert command_path.read_bytes() == baseline_command


@pytest.mark.parametrize("document", ["report", "command"])
def test_targeted_preflight_rejects_duplicate_baseline_json_keys(
    tmp_path: Path,
    document: str,
) -> None:
    root = tmp_path / "source"
    first_root, _first_raw, first_polish = _stage_pair(root, "First")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    path = run_dir / (
        "audit_full_checks.json"
        if document == "report"
        else "audit_command_report.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    first_key = next(iter(payload))
    duplicate = (
        json.dumps(first_key)
        + ": "
        + json.dumps(payload[first_key])
        + ",\n"
    )
    original = path.read_text(encoding="utf-8")
    path.write_text("{\n" + duplicate + original[2:], encoding="utf-8")
    first_polish.write_text(
        "<html><body><p>First polish changed.</p></body></html>",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=rf"audit_baseline_{document}_json_unreadable",
    ):
        run_audit(
            run_dir,
            roots=[first_root],
            merge_previous_report_path=run_dir / "audit_full_checks.json",
        )
    assert not (run_dir / "_enrichment_snapshot").exists()


def test_targeted_preflight_rejects_nonfinite_baseline_json(tmp_path: Path) -> None:
    root = tmp_path / "source"
    first_root, _first_raw, first_polish = _stage_pair(root, "First")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    command_path = run_dir / "audit_command_report.json"
    original = command_path.read_text(encoding="utf-8")
    mutated = original.replace('"jobs": 1', '"jobs": NaN', 1)
    assert mutated != original
    command_path.write_text(mutated, encoding="utf-8")
    first_polish.write_text(
        "<html><body><p>First polish changed.</p></body></html>",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="audit_baseline_command_json_unreadable",
    ):
        run_audit(
            run_dir,
            roots=[first_root],
            merge_previous_report_path=run_dir / "audit_full_checks.json",
        )
    assert not (run_dir / "_enrichment_snapshot").exists()


def test_targeted_preflight_rejects_oversized_baseline_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "source"
    first_root, _first_raw, first_polish = _stage_pair(root, "First")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root])
    report_path = run_dir / "audit_full_checks.json"
    monkeypatch.setattr(
        audit_provenance,
        "_MAX_AUDIT_JSON_BYTES",
        report_path.stat().st_size - 1,
    )
    first_polish.write_text(
        "<html><body><p>First polish changed.</p></body></html>",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="audit_baseline_report_too_large",
    ):
        run_audit(
            run_dir,
            roots=[first_root],
            merge_previous_report_path=report_path,
        )
    assert not (run_dir / "_enrichment_snapshot").exists()


@pytest.mark.parametrize(
    ("snapshot_field", "document", "record_label"),
    [
        ("snapshot", "report", "audit_input_snapshot"),
        (
            "command_snapshot",
            "command",
            "audit_merge_previous_command_snapshot",
        ),
    ],
)
def test_targeted_validator_rejects_duplicate_keys_in_baseline_snapshots(
    tmp_path: Path,
    snapshot_field: str,
    document: str,
    record_label: str,
) -> None:
    run_dir, _first_root, _source_map, audit, command = _targeted_audit_fixture(
        tmp_path
    )
    merge_input = command["merge_previous_report_input"]
    snapshot_path = Path(merge_input[snapshot_field]["path"])
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    first_key = next(iter(payload))
    duplicate = (
        json.dumps(first_key)
        + ": "
        + json.dumps(payload[first_key])
        + ",\n"
    )
    original = snapshot_path.read_text(encoding="utf-8")
    snapshot_path.write_text("{\n" + duplicate + original[2:], encoding="utf-8")
    merge_input[snapshot_field] = file_record(
        snapshot_path,
        label=record_label,
    )

    with pytest.raises(
        AuditCommandProvenanceError,
        match=rf"audit_merge_baseline_{document}_json_unreadable",
    ):
        validate_audit_command_report(run_dir, audit, command)


def test_targeted_preflight_allows_changed_target_stage_pdf(tmp_path: Path) -> None:
    root = tmp_path / "source"
    first_root, first_raw, first_polish = _stage_pair(root, "First")
    _second_root, second_raw, _second_polish = _stage_pair(root, "Second")
    first_pdf = first_raw.parent / "00.source.pdf"
    second_pdf = second_raw.parent / "00.source.pdf"
    first_pdf.write_bytes(b"%PDF-1.4 first baseline\n")
    second_pdf.write_bytes(b"%PDF-1.4 second baseline\n")
    run_dir = tmp_path / "run"
    run_audit(run_dir, roots=[root], enable_pdf_diagnostics=True)

    changed_pdf = b"%PDF-1.4 first changed\n"
    first_pdf.write_bytes(changed_pdf)
    first_polish.write_text(
        "<html><body><p>First polish changed.</p></body></html>",
        encoding="utf-8",
    )
    run_audit(
        run_dir,
        roots=[first_root],
        enable_pdf_diagnostics=True,
        merge_previous_report_path=run_dir / "audit_full_checks.json",
    )
    audit, command = _reports(run_dir)

    validate_audit_command_report(run_dir, audit, command)
    first = next(item for item in audit["articles"] if item["article"] == "First")
    assert first["summary"]["source_pdf_bytes"] == len(changed_pdf)
    assert first["summary"]["source_pdf_sha256"] == file_record(
        first_pdf,
        label="expected_changed_stage_pdf",
    )["sha256"]
