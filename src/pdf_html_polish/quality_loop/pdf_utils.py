"""PDF and image utility functions shared by quality-loop stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pdf_html_polish.atomic_io import write_generated_file_atomic
from pdf_html_polish.html_images import to_data_url as _to_data_url
from pdf_html_polish.html_images import validate_data_url as _validate_data_url


def pdf_text_pages(pdf_path: Path, *, max_pages: int | None = None) -> tuple[str, list[str], str | None]:
    if not pdf_path.is_file():
        return "missing", [], None

    errors: list[str] = []
    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        try:
            limit = len(doc) if not max_pages or max_pages <= 0 else min(len(doc), max_pages)
            return "pymupdf", [doc.load_page(index).get_text("text") or "" for index in range(limit)], None
        finally:
            doc.close()
    except ImportError as exc:
        errors.append(f"pymupdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - PDF/parser specific
        errors.append(f"pymupdf failed: {exc}")

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        pages = list(reader.pages)
        limit = len(pages) if not max_pages or max_pages <= 0 else min(len(pages), max_pages)
        return "pypdf", [pages[index].extract_text() or "" for index in range(limit)], None
    except ImportError as exc:
        errors.append(f"pypdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - PDF/parser specific
        errors.append(f"pypdf failed: {exc}")

    return "unavailable", [], "; ".join(errors)


def render_pdf_page(pdf_path: Path, page_number: int, out_path: Path, *, zoom: float) -> dict[str, Any]:
    if not pdf_path.is_file():
        return {"status": "missing_pdf", "path": "", "error": ""}
    try:
        import fitz

        doc = fitz.open(str(pdf_path))
        try:
            if page_number < 1 or page_number > len(doc):
                return {
                    "status": "page_out_of_range",
                    "path": "",
                    "error": f"page {page_number} outside 1..{len(doc)}",
                }
            page = doc.load_page(page_number - 1)
            matrix = fitz.Matrix(float(zoom), float(zoom))
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            write_generated_file_atomic(
                out_path,
                lambda temporary: pixmap.save(str(temporary), output="png"),
                validator=lambda temporary: data_url_from_image_file(temporary) is not None,
            )
            return {"status": "rendered", "path": str(out_path), "error": ""}
        finally:
            doc.close()
    except ImportError as exc:
        return {"status": "renderer_unavailable", "path": "", "error": str(exc)}
    except Exception as exc:  # pragma: no cover - PDF/render specific
        return {"status": "render_error", "path": "", "error": str(exc)}


def data_url_from_image_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    data_url = _to_data_url(path, detect_by_signature=True, log_func=None)
    if data_url is None or not _validate_data_url(data_url, path):
        return None
    return data_url


def first_valid_image_path(validation: dict[str, Any]) -> Path | None:
    for raw_path in validation.get("image_paths") or []:
        path = Path(str(raw_path))
        if data_url_from_image_file(path) is not None:
            return path
    return None
