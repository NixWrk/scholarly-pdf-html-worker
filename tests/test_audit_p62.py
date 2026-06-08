from zoteropdf2md.quality_loop.audit_blocks import parse_blocks, parse_overlapping_blocks
from zoteropdf2md.quality_loop.audit_p62 import (
    classify_missing_figure_warning,
    figure_label_from_text,
    nearby_image_offsets,
)


def test_figure_label_from_text_normalizes_panel_labels() -> None:
    assert figure_label_from_text("Figure 4A. Example panel.") == "4a"
    assert figure_label_from_text("Fig. 7. Example.") == "7"


def test_p62_classifier_reports_same_label_image_near_warning() -> None:
    html = "\n".join(
        [
            '<div id="fig-9" class="z2m-float-unit z2m-figure-unit">',
            '<p class="z2m-figure-target"><img src="data:image/png;base64,abc"/></p>',
            '<p class="z2m-missing-figure-warning">Figure 9 image was not extracted into this HTML.</p>',
            '<p class="z2m-figure-caption">Figure 9. Caption belongs to the image above.</p>',
            "</div>",
        ]
    )
    blocks = parse_overlapping_blocks(html)
    warning = next(block for block in blocks if "z2m-missing-figure-warning" in block.classes)

    classification = classify_missing_figure_warning(warning, blocks)

    assert classification["defect_id"] == "P62A"
    assert classification["extra"]["p62_subtype"] == "same_label_image_near_warning"


def test_nearby_image_offsets_stops_at_different_labeled_figure_unit() -> None:
    html = (
        '<div id="fig-8" class="z2m-float-unit z2m-figure-unit">'
        '<p class="z2m-figure-target"><img src="data:image/png;base64,abc"/></p>'
        '<p class="z2m-figure-caption">Figure 8. Previous extracted image.</p>'
        "</div>"
        '<p id="fig-10">Figure 10. Caption survived, but its image is absent.</p>'
    )
    blocks = parse_blocks(html)
    target = next(block for block in blocks if block.id == "fig-10")

    assert nearby_image_offsets(blocks, target.index, label="10") == []
    assert nearby_image_offsets(blocks, target.index, label=None) == [-1]
