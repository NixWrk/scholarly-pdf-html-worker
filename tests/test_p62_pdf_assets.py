from pdf_html_polish.quality_loop.p62_pdf_assets import (
    false_match_hint_blocks_asset_recovery,
    fitz_rect_area,
    fitz_rect_tuple,
    fitz_rects_intersect,
    fitz_union_rect,
    fitz_x_overlap_ratio,
    select_graphic_rects_for_caption,
    simple_numeric_figure_index,
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


def test_trim_region_away_from_caption_keeps_larger_side_for_top_caption() -> None:
    page = FakeRect(0, 0, 600, 800)
    region = FakeRect(40, 30, 550, 220)
    caption = FakeRect(52, 58, 180, 68)

    trimmed = trim_region_away_from_caption(region, page, caption)

    assert trimmed.y0 > caption.y1
    assert trimmed.y1 == 220
