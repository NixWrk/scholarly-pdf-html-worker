import base64
from pathlib import Path
import struct
from typing import Any

from pdf_html_polish.quality_loop.p62_duplicates import repair_duplicate_figure_images


def _duplicate_figure_html() -> str:
    duplicated_payload = base64.b64encode(b"same-visual").decode("ascii")
    duplicated_data_url = f"data:image/png;base64,{duplicated_payload}"
    return (
        '<div class="z2m-figure-unit" id="fig-1">'
        f'<p class="z2m-figure-target"><img alt="Figure 1" src="{duplicated_data_url}"/></p>'
        '<p class="z2m-figure-caption">Figure 1. First caption.</p>'
        "</div>"
        '<div class="z2m-figure-unit" id="fig-2">'
        f'<p class="z2m-figure-target"><img alt="Figure 2" src="{duplicated_data_url}"/></p>'
        '<p class="z2m-figure-caption">Figure 2. Second caption.</p>'
        "</div>"
    )


def _recovered_duplicate_figure_html(source: str = "pdf_page_render") -> str:
    duplicated_payload = base64.b64encode(b"same-recovered-visual").decode("ascii")
    duplicated_data_url = f"data:image/png;base64,{duplicated_payload}"
    return (
        '<div class="z2m-figure-unit" id="fig-1">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        f'<img data-z2m-recovery-source="{source}" '
        f'alt="Recovered Figure 1 visual from source PDF" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 1. First caption.</p>'
        "</div>"
        '<div class="z2m-figure-unit" id="fig-2">'
        '<p class="z2m-figure-target z2m-p62-recovered-target">'
        f'<img data-z2m-recovery-source="{source}" '
        f'alt="Recovered Figure 2 visual from source PDF" src="{duplicated_data_url}"/>'
        "</p>"
        '<p class="z2m-figure-caption">Figure 2. Second caption.</p>'
        "</div>"
    )


def _png_header_bytes(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x06\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )


def test_duplicate_repair_skips_plain_duplicates_without_flag(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF")

    patched, repairs = repair_duplicate_figure_images(
        _duplicate_figure_html(),
        pdf_path=pdf_path,
        artifact_dir=tmp_path / "artifacts",
        zoom=1.0,
        pdf_text_pages=lambda *_args, **_kwargs: ("ok", ["Figure 1", "Figure 2"], None),
        resolve_pdf_page_for_figure=lambda *_args, **_kwargs: {"page_number": 1},
        recover_detached_pdf_figure_plate_asset=lambda *_args, **_kwargs: {},
        recover_pdf_figure_asset=lambda *_args, **_kwargs: {},
        data_url_from_image_file=lambda _path: None,
        slug=lambda value, **_kwargs: str(value),
    )

    assert patched == _duplicate_figure_html()
    assert repairs == []


def test_duplicate_repair_patches_plain_duplicate_group_when_enabled(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF")

    def recover_asset(
        _pdf_path: Path,
        _page_number: int,
        label: str,
        out_dir: Path,
        **_kwargs: Any,
    ) -> dict[str, str]:
        return {
            "path": str(out_dir / f"fig-{label}.png"),
            "source": "pdf_figure_region_render",
            "status": "rendered",
        }

    def data_url_from_image_file(path: Path) -> str:
        payload = base64.b64encode(path.stem.encode("ascii")).decode("ascii")
        return f"data:image/png;base64,{payload}"

    patched, repairs = repair_duplicate_figure_images(
        _duplicate_figure_html(),
        pdf_path=pdf_path,
        artifact_dir=tmp_path / "artifacts",
        zoom=1.0,
        pdf_text_pages=lambda *_args, **_kwargs: ("ok", ["Figure 1", "Figure 2"], None),
        resolve_pdf_page_for_figure=lambda *_args, **_kwargs: {"page_number": 1},
        recover_detached_pdf_figure_plate_asset=lambda *_args, **_kwargs: {},
        recover_pdf_figure_asset=recover_asset,
        data_url_from_image_file=data_url_from_image_file,
        slug=lambda value, **_kwargs: str(value),
        repair_plain_duplicates=True,
    )

    assert [repair["status"] for repair in repairs] == ["patched", "patched"]
    assert {repair["figure_label"] for repair in repairs} == {"1", "2"}
    assert 'alt="Recovered Figure 1 visual from source PDF"' in patched
    assert 'alt="Recovered Figure 2 visual from source PDF"' in patched
    assert patched.count("z2m-p62-recovered-target") == 2


def test_duplicate_repair_rejects_asset_with_same_duplicate_hash(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF")
    html = _recovered_duplicate_figure_html()

    def recover_asset(
        _pdf_path: Path,
        _page_number: int,
        label: str,
        out_dir: Path,
        **_kwargs: Any,
    ) -> dict[str, str]:
        return {
            "path": str(out_dir / f"fig-{label}.png"),
            "source": "pdf_native_image",
            "status": "native_image_extracted",
        }

    duplicated_payload = base64.b64encode(b"same-recovered-visual").decode("ascii")

    patched, repairs = repair_duplicate_figure_images(
        html,
        pdf_path=pdf_path,
        artifact_dir=tmp_path / "artifacts",
        zoom=1.0,
        pdf_text_pages=lambda *_args, **_kwargs: ("ok", ["Figure 1", "Figure 2"], None),
        resolve_pdf_page_for_figure=lambda *_args, **_kwargs: {"page_number": 1},
        recover_detached_pdf_figure_plate_asset=lambda *_args, **_kwargs: {},
        recover_pdf_figure_asset=recover_asset,
        data_url_from_image_file=lambda _path: f"data:image/png;base64,{duplicated_payload}",
        slug=lambda value, **_kwargs: str(value),
    )

    assert patched == html
    assert {repair["figure_label"] for repair in repairs} == {"1", "2"}
    assert {repair["reason"] for repair in repairs} == {"recovered_asset_matches_duplicate_hash"}


def test_duplicate_repair_patches_region_render_duplicate_targets(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF")
    html = _recovered_duplicate_figure_html(source="pdf_figure_region_render")

    def recover_asset(
        _pdf_path: Path,
        _page_number: int,
        label: str,
        out_dir: Path,
        **_kwargs: Any,
    ) -> dict[str, str]:
        return {
            "path": str(out_dir / f"fig-{label}.png"),
            "source": "pdf_figure_region_render",
            "status": "region_rendered",
        }

    def data_url_from_image_file(path: Path) -> str:
        payload = base64.b64encode(f"fresh-{path.stem}".encode("ascii")).decode("ascii")
        return f"data:image/png;base64,{payload}"

    patched, repairs = repair_duplicate_figure_images(
        html,
        pdf_path=pdf_path,
        artifact_dir=tmp_path / "artifacts",
        zoom=1.0,
        pdf_text_pages=lambda *_args, **_kwargs: ("ok", ["Figure 1", "Figure 2"], None),
        resolve_pdf_page_for_figure=lambda *_args, **_kwargs: {"page_number": 1},
        recover_detached_pdf_figure_plate_asset=lambda *_args, **_kwargs: {},
        recover_pdf_figure_asset=recover_asset,
        data_url_from_image_file=data_url_from_image_file,
        slug=lambda value, **_kwargs: str(value),
    )

    assert [repair["status"] for repair in repairs] == ["patched", "patched"]
    assert {repair["repair_mode"] for repair in repairs} == {"recovered_duplicate_target"}
    assert patched != html


def test_duplicate_repair_replaces_strip_like_recovered_targets_with_terminal_warning(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF")
    html = _recovered_duplicate_figure_html(source="pdf_figure_region_render")
    strip_asset = tmp_path / "page-header-strip.png"
    strip_asset.write_bytes(_png_header_bytes(769, 40))

    def recover_asset(
        _pdf_path: Path,
        _page_number: int,
        _label: str,
        _out_dir: Path,
        **_kwargs: Any,
    ) -> dict[str, str]:
        return {
            "path": str(strip_asset),
            "source": "pdf_figure_region_render",
            "status": "region_rendered",
        }

    patched, repairs = repair_duplicate_figure_images(
        html,
        pdf_path=pdf_path,
        artifact_dir=tmp_path / "artifacts",
        zoom=1.0,
        pdf_text_pages=lambda *_args, **_kwargs: ("ok", ["Figure 1", "Figure 2"], None),
        resolve_pdf_page_for_figure=lambda *_args, **_kwargs: {"page_number": 1},
        recover_detached_pdf_figure_plate_asset=lambda *_args, **_kwargs: {},
        recover_pdf_figure_asset=recover_asset,
        data_url_from_image_file=lambda _path: "",
        slug=lambda value, **_kwargs: str(value),
    )

    assert [repair["status"] for repair in repairs] == ["patched", "patched"]
    assert {repair["action"] for repair in repairs} == {
        "replaced_duplicate_recovery_with_missing_warning"
    }
    assert patched.count('data-z2m-recovery-status="source_visual_unavailable"') == 2
    assert "z2m-p62-recovered-target" not in patched
