from pathlib import Path

import pytest

from pdf_html_polish.quality_loop.pdf_utils import (
    data_url_from_image_file,
    first_valid_image_path,
    pdf_text_pages,
    render_pdf_page,
)


def test_pdf_utils_report_missing_pdf(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pdf"

    assert pdf_text_pages(missing) == ("missing", [], None)
    assert render_pdf_page(missing, 1, tmp_path / "page.png", zoom=1.0) == {
        "status": "missing_pdf",
        "path": "",
        "error": "",
    }


def test_pdf_utils_data_url_validates_local_image(tmp_path: Path) -> None:
    image_path = tmp_path / "tiny.png"
    image_path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000d49444154789c6360000002000100ffff03000006000557bfabdd00000000"
            "49454e44ae426082"
        )
    )

    data_url = data_url_from_image_file(image_path)

    assert data_url is not None
    assert data_url.startswith("data:image/png;base64,")
    assert first_valid_image_path({"image_paths": [str(tmp_path / "none.png"), str(image_path)]}) == image_path


def test_render_pdf_page_atomically_publishes_real_png(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "source.pdf"
    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "Atomic evidence render")
        document.save(str(pdf_path))
    finally:
        document.close()
    out_path = tmp_path / "page.png"

    result = render_pdf_page(pdf_path, 1, out_path, zoom=1.0)

    assert result == {
        "status": "rendered",
        "path": str(out_path),
        "error": "",
    }
    assert out_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert not list(tmp_path.glob(".page.png.*.tmp"))
