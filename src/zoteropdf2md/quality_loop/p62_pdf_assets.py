"""PDF asset recovery helpers for P62 missing-figure repairs."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import Any, Callable

from zoteropdf2md.quality_loop.p62_matching import false_page_match_hint


DataUrlFromImageFile = Callable[[Path], str | None]
SlugFunc = Callable[..., str]

P62_UNRECOVERABLE_FALSE_MATCH_HINTS = {
    "toc_or_contents",
    "figure_caption_list",
    "manuscript_placeholder",
    "backmatter_or_reference_text",
    "prose_parenthetical_reference",
}


def render_fallback_page_number(
    pdf_path: Path,
    source_page_number: int,
    figure_label: str,
) -> tuple[int, str]:
    page_number = max(1, int(source_page_number or 1))
    label = str(figure_label or "").strip()
    if not label or page_number <= 1:
        return page_number, "primary_matched_page"

    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if page_number > len(doc):
                return page_number, "primary_page_out_of_text_limit"
            page = doc.load_page(page_number - 1)
            rects = []
            for needle in (f"Figure {label}", f"Fig. {label}", f"Fig {label}"):
                rects.extend(page.search_for(needle))
            if not rects:
                return page_number, "primary_matched_page"
            top_ratio = min(float(rect.y0) for rect in rects) / max(1.0, float(page.rect.height))
            if top_ratio <= 0.22:
                return page_number - 1, "caption_near_page_top_previous_page"
            return page_number, "caption_on_primary_page"
        finally:
            doc.close()
    except Exception:
        return page_number, "primary_matched_page"


def false_match_hint_blocks_asset_recovery(
    hint: str,
    *,
    caption_found: bool = False,
) -> bool:
    value = str(hint or "")
    if value == "prose_parenthetical_reference" and caption_found:
        return False
    return value in P62_UNRECOVERABLE_FALSE_MATCH_HINTS


def pdf_page_false_match_hint(pdf_path: Path, page_number: int, figure_label: str) -> str:
    label = str(figure_label or "").strip()
    if not label or not pdf_path.is_file() or page_number <= 0:
        return ""
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if page_number > len(doc):
                return ""
            page_text = str(doc.load_page(page_number - 1).get_text("text") or "")
        finally:
            doc.close()
    except Exception:
        return ""
    return false_page_match_hint(page_text, label)


def pdf_page_caption_label_found(pdf_path: Path, page_number: int, figure_label: str) -> bool:
    label = str(figure_label or "").strip()
    if not label or not pdf_path.is_file() or page_number <= 0:
        return False
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if page_number > len(doc):
                return False
            page = doc.load_page(page_number - 1)
            return bool(page_caption_label_rects(page, label))
        finally:
            doc.close()
    except Exception:
        return False


def pdf_visual_inventory(pdf_path: Path) -> dict[str, Any]:
    if not pdf_path.is_file():
        return {
            "status": "missing_pdf",
            "page_count": 0,
            "native_image_count": 0,
            "large_image_count": 0,
            "pages_with_native_images": [],
            "pages_with_large_images": [],
            "error": "",
        }
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            native_pages: list[dict[str, Any]] = []
            large_pages: list[dict[str, Any]] = []
            native_count = 0
            large_count = 0
            for page_index in range(len(doc)):
                page = doc.load_page(page_index)
                images = page.get_images(full=True)
                large_images = large_image_rects(page)
                native_count += len(images)
                large_count += len(large_images)
                if images:
                    native_pages.append({"page_number": page_index + 1, "count": len(images)})
                if large_images:
                    large_pages.append({"page_number": page_index + 1, "count": len(large_images)})
            return {
                "status": "ready",
                "page_count": len(doc),
                "native_image_count": native_count,
                "large_image_count": large_count,
                "pages_with_native_images": native_pages[:40],
                "pages_with_large_images": large_pages[:40],
                "error": "",
            }
        finally:
            doc.close()
    except ImportError as exc:
        return {
            "status": "renderer_unavailable",
            "page_count": 0,
            "native_image_count": 0,
            "large_image_count": 0,
            "pages_with_native_images": [],
            "pages_with_large_images": [],
            "error": str(exc),
        }
    except Exception as exc:  # pragma: no cover - PDF-specific
        return {
            "status": "inventory_error",
            "page_count": 0,
            "native_image_count": 0,
            "large_image_count": 0,
            "pages_with_native_images": [],
            "pages_with_large_images": [],
            "error": str(exc),
        }


def pypdf_image_inventory(pdf_path: Path) -> dict[str, Any]:
    if not pdf_path.is_file():
        return {
            "status": "missing_pdf",
            "page_count": 0,
            "image_count": 0,
            "pages_with_images": [],
            "errors": [],
        }
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(pdf_path))
        pages_with_images: list[dict[str, Any]] = []
        errors: list[str] = []
        image_count = 0
        for index, page in enumerate(reader.pages, start=1):
            try:
                images = list(getattr(page, "images", []) or [])
            except Exception as exc:  # pragma: no cover - PDF-specific
                errors.append(f"page {index}: {exc}")
                images = []
            image_count += len(images)
            if images:
                pages_with_images.append({"page_number": index, "count": len(images)})
        return {
            "status": "ready" if not errors else "partial",
            "page_count": len(reader.pages),
            "image_count": image_count,
            "pages_with_images": pages_with_images[:40],
            "errors": errors[:8],
        }
    except ImportError as exc:
        return {
            "status": "parser_unavailable",
            "page_count": 0,
            "image_count": 0,
            "pages_with_images": [],
            "errors": [str(exc)],
        }
    except Exception as exc:  # pragma: no cover - PDF-specific
        return {
            "status": "inventory_error",
            "page_count": 0,
            "image_count": 0,
            "pages_with_images": [],
            "errors": [str(exc)],
        }


def external_pdf_tool_inventory() -> dict[str, Any]:
    tools = {}
    for tool_name in ("pdfimages", "mutool", "pdfinfo", "pdftoppm"):
        tools[tool_name] = {"available": bool(shutil.which(tool_name))}
    return {"status": "ready", "tools": tools}


def recover_pdf_figure_asset(
    pdf_path: Path,
    page_number: int,
    figure_label: str,
    artifact_dir: Path,
    *,
    zoom: float,
    data_url_from_image_file: DataUrlFromImageFile,
    slug: SlugFunc,
) -> dict[str, Any]:
    if not pdf_path.is_file():
        return {"status": "missing_pdf", "path": "", "source": "", "error": ""}
    label = str(figure_label or "").strip()
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if page_number < 1 or page_number > len(doc):
                return {
                    "status": "page_out_of_range",
                    "path": "",
                    "source": "",
                    "error": f"page {page_number} outside 1..{len(doc)}",
                }
            page = doc.load_page(page_number - 1)
            page_area = max(1.0, float(page.rect.width) * float(page.rect.height))
            caption_label_rects = page_caption_label_rects(page, label)
            caption_rects = caption_label_rects or page_label_rects(page, label)
            false_match = false_page_match_hint(str(page.get_text("text") or ""), label)
            if false_match_hint_blocks_asset_recovery(
                false_match,
                caption_found=bool(caption_label_rects),
            ):
                return {
                    "status": f"false_label_match_{false_match}",
                    "path": "",
                    "source": "",
                    "error": "Matched PDF page is a false figure-label location, not a recoverable visual.",
                    "page_number": page_number,
                    "caption_found": bool(caption_rects),
                    "false_match_hint": false_match,
                }
            caption_rect = fitz_union_rect(caption_rects) if caption_rects else None
            graphics = page_graphic_rects(page)
            selected = select_graphic_rects_for_caption(page.rect, graphics, caption_rect)
            if not selected:
                text_region = text_figure_region_for_caption(page, caption_rect)
                if text_region is not None:
                    text_region = expand_rect(
                        text_region,
                        page.rect,
                        margin=max(4.0, min(page.rect.width, page.rect.height) * 0.01),
                    )
                    if fitz_rect_area(text_region) > page_area * 0.001:
                        out_path = artifact_dir / f"fig_{slug(label or 'unknown', max_len=20)}_pdf_text_region_page_{page_number:04d}.png"
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        pixmap = page.get_pixmap(matrix=fitz.Matrix(float(zoom), float(zoom)), clip=text_region, alpha=False)
                        pixmap.save(str(out_path))
                        if data_url_from_image_file(out_path) is not None:
                            return {
                                "status": "text_region_rendered",
                                "path": str(out_path),
                                "source": "pdf_figure_region_render",
                                "error": "",
                                "page_number": page_number,
                                "caption_found": bool(caption_rect),
                                "selected_rect": fitz_rect_tuple(text_region),
                                "graphic_count": len(graphics),
                                "selected_graphic_count": 0,
                            }
                return {
                    "status": "no_figure_region",
                    "path": "",
                    "source": "",
                    "error": "No graphic/image region could be associated with the target caption.",
                    "page_number": page_number,
                    "caption_found": bool(caption_rect),
                    "graphic_count": len(graphics),
                }

            image_candidates = [item for item in selected if item.get("kind") == "image" and item.get("xref")]
            selected_area = sum(fitz_rect_area(item["rect"]) for item in selected)
            drawing_count = sum(1 for item in selected if item.get("kind") == "drawing")
            if (
                len(image_candidates) == 1
                and drawing_count == 0
                and selected_area >= page_area * 0.01
            ):
                extracted = doc.extract_image(int(image_candidates[0]["xref"]))
                data = extracted.get("image")
                ext = str(extracted.get("ext") or "png").lower().lstrip(".")
                if data:
                    out_path = artifact_dir / f"fig_{slug(label or 'unknown', max_len=20)}_pdf_native_page_{page_number:04d}.{ext}"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_bytes(data)
                    if data_url_from_image_file(out_path) is not None:
                        return {
                            "status": "native_image_extracted",
                            "path": str(out_path),
                            "source": "pdf_native_image",
                            "error": "",
                            "page_number": page_number,
                            "caption_found": bool(caption_rect),
                            "selected_rect": fitz_rect_tuple(image_candidates[0]["rect"]),
                            "graphic_count": len(graphics),
                        }

            region = fitz_union_rect([item["rect"] for item in selected])
            region = expand_rect(region, page.rect, margin=max(4.0, min(page.rect.width, page.rect.height) * 0.01))
            region = include_nearby_text_blocks(page, region, caption_rect)
            region = expand_rect(region, page.rect, margin=max(3.0, min(page.rect.width, page.rect.height) * 0.006))
            if fitz_rect_area(region) <= page_area * 0.001:
                return {
                    "status": "figure_region_too_small",
                    "path": "",
                    "source": "",
                    "error": "Associated figure region is too small.",
                    "page_number": page_number,
                    "caption_found": bool(caption_rect),
                    "selected_rect": fitz_rect_tuple(region),
                }
            out_path = artifact_dir / f"fig_{slug(label or 'unknown', max_len=20)}_pdf_region_page_{page_number:04d}.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(float(zoom), float(zoom)), clip=region, alpha=False)
            pixmap.save(str(out_path))
            if data_url_from_image_file(out_path) is None:
                return {
                    "status": "region_render_invalid",
                    "path": str(out_path),
                    "source": "",
                    "error": "Rendered region did not produce a valid image.",
                    "page_number": page_number,
                    "caption_found": bool(caption_rect),
                    "selected_rect": fitz_rect_tuple(region),
                }
            return {
                "status": "region_rendered",
                "path": str(out_path),
                "source": "pdf_figure_region_render",
                "error": "",
                "page_number": page_number,
                "caption_found": bool(caption_rect),
                "selected_rect": fitz_rect_tuple(region),
                "graphic_count": len(graphics),
                "selected_graphic_count": len(selected),
            }
        finally:
            doc.close()
    except ImportError as exc:
        return {"status": "renderer_unavailable", "path": "", "source": "", "error": str(exc)}
    except Exception as exc:  # pragma: no cover - PDF/render specific
        return {"status": "figure_asset_error", "path": "", "source": "", "error": str(exc)}


def recover_detached_pdf_figure_plate_asset(
    pdf_path: Path,
    anchor_page_number: int,
    figure_label: str,
    artifact_dir: Path,
    *,
    zoom: float,
    data_url_from_image_file: DataUrlFromImageFile,
    slug: SlugFunc,
) -> dict[str, Any]:
    label_index = simple_numeric_figure_index(figure_label)
    if label_index <= 0:
        return {"status": "not_numeric_figure_label", "path": "", "source": "", "error": ""}
    if not pdf_path.is_file():
        return {"status": "missing_pdf", "path": "", "source": "", "error": ""}
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            if anchor_page_number < 1 or anchor_page_number > len(doc):
                return {
                    "status": "page_out_of_range",
                    "path": "",
                    "source": "",
                    "error": f"page {anchor_page_number} outside 1..{len(doc)}",
                }
            anchor_page = doc.load_page(anchor_page_number - 1)
            anchor_text = str(anchor_page.get_text("text") or "").casefold()
            if "accepted article" not in anchor_text:
                return {"status": "not_detached_plate_pattern", "path": "", "source": "", "error": ""}
            if large_image_rects(anchor_page):
                return {"status": "anchor_page_has_large_image", "path": "", "source": "", "error": ""}

            plates: list[dict[str, Any]] = []
            for page_index in range(anchor_page_number - 1, len(doc)):
                page = doc.load_page(page_index)
                text = str(page.get_text("text") or "").strip()
                text_blocks = sum(
                    1
                    for block in (page.get_text("dict") or {}).get("blocks") or []
                    if block.get("type") == 0
                )
                if text_blocks > 8 and len(text) > 1600:
                    continue
                for image in large_image_rects(page):
                    plates.append(
                        {
                            "page_number": page_index + 1,
                            "rect": image["rect"],
                            "xref": image.get("xref") or 0,
                            "area_ratio": image.get("area_ratio") or 0.0,
                        }
                    )
            plates.sort(
                key=lambda item: (
                    int(item.get("page_number") or 0),
                    float(item["rect"].y0),
                    float(item["rect"].x0),
                )
            )
            if len(plates) < label_index:
                return {
                    "status": "detached_plate_not_found",
                    "path": "",
                    "source": "",
                    "error": f"found {len(plates)} plate images, need figure index {label_index}",
                    "plate_count": len(plates),
                }
            chosen = plates[label_index - 1]
            page_number = int(chosen["page_number"])
            page = doc.load_page(page_number - 1)
            rect = expand_rect(chosen["rect"], page.rect, margin=3.0)
            out_path = artifact_dir / f"fig_{slug(figure_label or 'unknown', max_len=20)}_pdf_plate_page_{page_number:04d}.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(float(zoom), float(zoom)), clip=rect, alpha=False)
            pixmap.save(str(out_path))
            if data_url_from_image_file(out_path) is None:
                return {
                    "status": "detached_plate_render_invalid",
                    "path": str(out_path),
                    "source": "",
                    "error": "Rendered detached plate did not produce a valid image.",
                    "page_number": page_number,
                    "selected_rect": fitz_rect_tuple(rect),
                }
            return {
                "status": "detached_plate_rendered",
                "path": str(out_path),
                "source": "pdf_detached_plate_region_render",
                "error": "",
                "page_number": page_number,
                "anchor_page_number": anchor_page_number,
                "selected_rect": fitz_rect_tuple(rect),
                "plate_count": len(plates),
                "plate_index": label_index,
            }
        finally:
            doc.close()
    except ImportError as exc:
        return {"status": "renderer_unavailable", "path": "", "source": "", "error": str(exc)}
    except Exception as exc:  # pragma: no cover - PDF/render specific
        return {"status": "detached_plate_error", "path": "", "source": "", "error": str(exc)}


def simple_numeric_figure_index(figure_label: str) -> int:
    label = str(figure_label or "").strip()
    if not re.fullmatch(r"\d{1,3}", label):
        return 0
    value = int(label)
    return value if value > 0 else 0


def large_image_rects(page: Any) -> list[dict[str, Any]]:
    page_area = max(1.0, float(page.rect.width) * float(page.rect.height))
    images: list[dict[str, Any]] = []
    seen: set[tuple[int, tuple[float, float, float, float]]] = set()
    try:
        for image_info in page.get_images(full=True):
            xref = int(image_info[0])
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            for rect in rects:
                area_ratio = fitz_rect_area(rect) / page_area
                key = (xref, fitz_rect_tuple(rect))
                if area_ratio < 0.04 or key in seen:
                    continue
                seen.add(key)
                images.append({"xref": xref, "rect": rect, "area_ratio": area_ratio})
    except Exception:
        return images
    return images


def page_caption_label_rects(page: Any, figure_label: str) -> list[Any]:
    label = str(figure_label or "").strip()
    if not label:
        return []
    caption_pattern = re.compile(
        rf"^\s*(?:fig(?:ure)?\.?)\s*{re.escape(label)}(?![\w-]|\.[A-Za-z0-9])(?:\s*[.:|]\s*|\s+)",
        re.IGNORECASE,
    )
    rects: list[Any] = []
    try:
        import fitz  # type: ignore[import-not-found]

        blocks = (page.get_text("dict") or {}).get("blocks") or []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines") or []:
                text = "".join(span.get("text", "") for span in line.get("spans") or [])
                if not caption_pattern.search(text):
                    continue
                bbox = line.get("bbox") or block.get("bbox")
                if bbox:
                    rects.append(fitz.Rect(bbox))
    except Exception:
        return rects
    return rects


def page_label_rects(page: Any, figure_label: str) -> list[Any]:
    label = str(figure_label or "").strip()
    if not label:
        return []
    rects: list[Any] = []
    for needle in (f"Figure {label}", f"FIGURE {label}", f"Fig. {label}", f"Fig {label}"):
        try:
            rects.extend(page.search_for(needle))
        except Exception:
            continue
    return rects


def graphic_rect_is_page_rule(page_rect: Any, rect: Any) -> bool:
    page_width = max(1.0, float(page_rect.width))
    page_height = max(1.0, float(page_rect.height))
    rect_width = max(0.0, float(rect.width))
    rect_height = max(0.0, float(rect.height))
    if rect_width < page_width * 0.72 or rect_height > max(2.0, page_height * 0.01):
        return False
    top_distance = max(0.0, float(rect.y0) - float(page_rect.y0))
    bottom_distance = max(0.0, float(page_rect.y1) - float(rect.y1))
    return top_distance <= page_height * 0.12 or bottom_distance <= page_height * 0.12


def page_graphic_rects(page: Any) -> list[dict[str, Any]]:
    graphics: list[dict[str, Any]] = []
    seen: set[tuple[str, int, tuple[float, float, float, float]]] = set()
    try:
        for image_info in page.get_images(full=True):
            xref = int(image_info[0])
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            for rect in rects:
                key = ("image", xref, fitz_rect_tuple(rect))
                if key not in seen and fitz_rect_area(rect) > 1.0:
                    seen.add(key)
                    graphics.append({"kind": "image", "xref": xref, "rect": rect})
    except Exception:
        pass
    try:
        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect is None or fitz_rect_area(rect) <= 4.0:
                continue
            if graphic_rect_is_page_rule(page.rect, rect):
                continue
            key = ("drawing", 0, fitz_rect_tuple(rect))
            if key in seen:
                continue
            seen.add(key)
            graphics.append({"kind": "drawing", "xref": 0, "rect": rect})
    except Exception:
        pass
    return graphics


def select_graphic_rects_for_caption(
    page_rect: Any,
    graphics: list[dict[str, Any]],
    caption_rect: Any | None,
) -> list[dict[str, Any]]:
    if not graphics:
        return []
    page_height = max(1.0, float(page_rect.height))
    page_width = max(1.0, float(page_rect.width))
    page_area = page_width * page_height
    if caption_rect is None:
        return sorted(graphics, key=lambda item: fitz_rect_area(item["rect"]), reverse=True)[:8]

    above: list[tuple[float, dict[str, Any]]] = []
    below: list[tuple[float, dict[str, Any]]] = []
    overlapping: list[tuple[float, dict[str, Any]]] = []
    side_aligned: list[tuple[float, dict[str, Any]]] = []
    for item in graphics:
        rect = item["rect"]
        area = fitz_rect_area(rect)
        if area < max(4.0, page_area * 0.00005):
            continue
        x_overlap = fitz_x_overlap_ratio(rect, caption_rect)
        y_overlap = fitz_y_overlap_ratio(rect, caption_rect)
        horizontal_gap = max(
            0.0,
            max(float(caption_rect.x0) - float(rect.x1), float(rect.x0) - float(caption_rect.x1)),
        )
        same_vertical_band = (
            y_overlap > 0.0
            or abs(float(rect.y0) - float(caption_rect.y0)) <= page_height * 0.08
            or abs(float(rect.y1) - float(caption_rect.y1)) <= page_height * 0.08
        )
        if same_vertical_band and horizontal_gap <= page_width * 0.72:
            side_aligned.append((horizontal_gap - min(0.5, y_overlap) * 40.0, item))
            continue
        if x_overlap <= 0 and area < page_area * 0.03:
            continue
        if rect.y1 <= caption_rect.y0 + 3:
            distance = max(0.0, float(caption_rect.y0 - rect.y1))
            if distance <= page_height * 0.62:
                above.append((distance - min(0.3, x_overlap) * 40.0, item))
        elif rect.y0 >= caption_rect.y1 - 3:
            distance = max(0.0, float(rect.y0 - caption_rect.y1))
            if distance <= page_height * 0.62:
                below.append((distance - min(0.3, x_overlap) * 40.0, item))
        else:
            overlapping.append((0.0, item))

    chosen_pool = side_aligned if side_aligned else above if above else below if below else overlapping
    if not chosen_pool:
        return sorted(graphics, key=lambda item: fitz_rect_area(item["rect"]), reverse=True)[:8]
    chosen_pool.sort(key=lambda item: item[0])
    nearest_distance = chosen_pool[0][0]
    distance_window = page_width * 0.62 if chosen_pool is side_aligned else page_height * 0.28
    selected = [
        item
        for distance, item in chosen_pool
        if distance <= nearest_distance + distance_window
    ]
    if not selected:
        selected = [chosen_pool[0][1]]
    return selected


def text_figure_region_for_caption(page: Any, caption_rect: Any | None) -> Any | None:
    if caption_rect is None:
        return None
    try:
        import fitz  # type: ignore[import-not-found]

        blocks = (page.get_text("dict") or {}).get("blocks") or []
    except Exception:
        return None
    page_height = max(1.0, float(page.rect.height))
    page_width = max(1.0, float(page.rect.width))
    min_y = max(0.0, float(caption_rect.y0) - page_height * 0.48)
    candidates: list[Any] = []
    for block in blocks:
        if block.get("type") != 0 or not block.get("bbox"):
            continue
        try:
            rect = fitz.Rect(block.get("bbox"))
        except Exception:
            continue
        if fitz_rects_intersect(rect, caption_rect):
            continue
        if rect.y1 > caption_rect.y0 + 3:
            continue
        if rect.y1 < min_y:
            continue
        if rect.width < page_width * 0.18 or rect.height < 5:
            continue
        if fitz_x_overlap_ratio(rect, caption_rect) <= 0 and rect.width < page_width * 0.55:
            continue
        candidates.append(rect)
    if not candidates:
        return None
    region = fitz_union_rect(candidates)
    if fitz_rect_area(region) < page_width * page_height * 0.01:
        return None
    return region


def include_nearby_text_blocks(page: Any, region: Any, caption_rect: Any | None) -> Any:
    try:
        blocks = (page.get_text("dict") or {}).get("blocks") or []
    except Exception:
        return region
    expanded = expand_rect(region, page.rect, margin=12.0)
    rects = [region]
    for block in blocks:
        if block.get("type") != 0 or not block.get("bbox"):
            continue
        try:
            import fitz  # type: ignore[import-not-found]

            rect = fitz.Rect(block.get("bbox"))
        except Exception:
            continue
        if caption_rect is not None and fitz_rects_intersect(rect, caption_rect):
            continue
        if fitz_rects_intersect(rect, expanded):
            rects.append(rect)
    return fitz_union_rect(rects)


def fitz_rect_area(rect: Any) -> float:
    return max(0.0, float(rect.width)) * max(0.0, float(rect.height))


def fitz_x_overlap_ratio(a: Any, b: Any) -> float:
    overlap = max(0.0, min(float(a.x1), float(b.x1)) - max(float(a.x0), float(b.x0)))
    return overlap / max(1.0, min(float(a.width), float(b.width)))


def fitz_y_overlap_ratio(a: Any, b: Any) -> float:
    overlap = max(0.0, min(float(a.y1), float(b.y1)) - max(float(a.y0), float(b.y0)))
    return overlap / max(1.0, min(float(a.height), float(b.height)))


def fitz_rects_intersect(a: Any, b: Any) -> bool:
    return min(float(a.x1), float(b.x1)) > max(float(a.x0), float(b.x0)) and min(float(a.y1), float(b.y1)) > max(float(a.y0), float(b.y0))


def fitz_union_rect(rects: list[Any]) -> Any:
    if not rects:
        raise ValueError("Cannot union empty rect list")
    rect = rects[0]
    for other in rects[1:]:
        rect = rect | other
    return rect


def expand_rect(rect: Any, page_rect: Any, *, margin: float) -> Any:
    try:
        import fitz  # type: ignore[import-not-found]

        return fitz.Rect(
            max(float(page_rect.x0), float(rect.x0) - margin),
            max(float(page_rect.y0), float(rect.y0) - margin),
            min(float(page_rect.x1), float(rect.x1) + margin),
            min(float(page_rect.y1), float(rect.y1) + margin),
        )
    except Exception:
        return rect


def fitz_rect_tuple(rect: Any) -> tuple[float, float, float, float]:
    return (
        round(float(rect.x0), 2),
        round(float(rect.y0), 2),
        round(float(rect.x1), 2),
        round(float(rect.y1), 2),
    )
