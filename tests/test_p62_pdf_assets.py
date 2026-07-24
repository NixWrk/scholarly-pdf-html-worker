import fitz

from pdf_html_polish.quality_loop.p62_pdf_assets import (
    false_match_hint_blocks_asset_recovery,
    fitz_rect_area,
    fitz_rect_tuple,
    fitz_rects_intersect,
    fitz_union_rect,
    fitz_x_overlap_ratio,
    select_graphic_rects_for_caption,
    selected_graphics_should_defer_to_text_region,
    simple_numeric_figure_index,
    text_figure_region_for_caption,
    trim_region_away_from_caption,
)


class FakeRect:
    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1
        self.width = x1 - x0
        self.height = y1 - y0

    def __or__(self, other: "FakeRect") -> "FakeRect":
        return FakeRect(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1),
        )


class FakeTextPage:
    def __init__(self, blocks: list[dict[str, object]]) -> None:
        self.rect = fitz.Rect(0, 0, 600, 840)
        self._blocks = blocks

    def get_text(self, kind: str) -> dict[str, object]:
        assert kind == "dict"
        return {"blocks": self._blocks}


def _text_block(bbox: tuple[float, float, float, float], text: str) -> dict[str, object]:
    return {
        "type": 0,
        "bbox": bbox,
        "lines": [{"bbox": bbox, "spans": [{"text": text}]}],
    }


def test_false_match_hint_blocks_unrecoverable_sources_but_allows_caption_context() -> None:
    assert false_match_hint_blocks_asset_recovery("manuscript_placeholder")
    assert false_match_hint_blocks_asset_recovery("prose_parenthetical_reference")
    assert not false_match_hint_blocks_asset_recovery(
        "prose_parenthetical_reference",
        caption_found=True,
    )


def test_p62_pdf_rect_helpers_are_geometry_only() -> None:
    left = FakeRect(10, 20, 50, 70)
    right = FakeRect(30, 50, 90, 110)

    assert fitz_rect_area(left) == 2000
    assert round(fitz_x_overlap_ratio(left, right), 3) == 0.5
    assert fitz_rects_intersect(left, right)
    assert fitz_rect_tuple(fitz_union_rect([left, right])) == (10.0, 20.0, 90.0, 110.0)


def test_simple_numeric_figure_index_accepts_only_plain_positive_numbers() -> None:
    assert simple_numeric_figure_index("3") == 3
    assert simple_numeric_figure_index("0") == 0
    assert simple_numeric_figure_index("3A") == 0


def test_select_graphic_rects_ignores_caption_rule_before_real_figure_region() -> None:
    page = FakeRect(0, 0, 600, 800)
    caption = FakeRect(72, 320, 220, 338)
    caption_rule = {"kind": "drawing", "rect": FakeRect(60, 312, 540, 314)}
    figure = {"kind": "image", "xref": 12, "rect": FakeRect(90, 120, 510, 300)}

    selected = select_graphic_rects_for_caption(page, [caption_rule, figure], caption)

    assert selected == [figure]


def test_text_figure_regions_are_bounded_by_previous_caption() -> None:
    page = FakeTextPage(
        [
            _text_block((220, 47, 541, 56), "Paper title 4"),
            _text_block((104, 68, 474, 78), "First prompt"),
            _text_block((178, 88, 394, 147), "First code listing"),
            _text_block((110, 169, 486, 179), "Figure 3: First example."),
            _text_block((104, 193, 495, 227), "Second prompt"),
            _text_block((178, 230, 399, 329), "Second code listing"),
            _text_block((55, 342, 541, 364), "Figure 4: Second example."),
        ]
    )

    figure_3 = text_figure_region_for_caption(page, fitz.Rect(110, 169, 486, 179))
    figure_4 = text_figure_region_for_caption(page, fitz.Rect(55, 342, 541, 364))

    assert fitz_rect_tuple(figure_3) == (104.0, 68.0, 474.0, 147.0)
    assert fitz_rect_tuple(figure_4) == (104.0, 193.0, 495.0, 329.0)


def test_remote_graphic_below_caption_defers_to_nearby_text_figure() -> None:
    page = FakeRect(0, 0, 600, 840)
    caption = FakeRect(55, 342, 541, 364)
    text_region = FakeRect(104, 193, 495, 329)
    unrelated = {"kind": "drawing", "rect": FakeRect(263, 436, 275, 445)}

    assert selected_graphics_should_defer_to_text_region(
        page,
        [unrelated],
        caption,
        text_region,
    )


def test_trim_region_away_from_caption_keeps_larger_side_for_top_caption() -> None:
    page = FakeRect(0, 0, 600, 800)
    region = FakeRect(40, 30, 550, 220)
    caption = FakeRect(52, 58, 180, 68)

    trimmed = trim_region_away_from_caption(region, page, caption)

    assert trimmed.y0 > caption.y1
    assert trimmed.y1 == 220
