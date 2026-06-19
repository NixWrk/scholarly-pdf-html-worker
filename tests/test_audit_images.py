import hashlib
import re

from pdf_html_polish.quality_loop.audit_images import (
    figure_visual_identity_defects,
    image_asset_defects,
    image_identity_key,
    is_inline_or_remote_src,
    local_image_candidates,
    missing_local_images,
)


def test_image_src_classification_keeps_file_urls_local() -> None:
    assert is_inline_or_remote_src("data:image/png;base64,abc") is True
    assert is_inline_or_remote_src("https://example.test/a.png") is True
    assert is_inline_or_remote_src("#fig-1") is True
    assert is_inline_or_remote_src("file:///C:/tmp/a.png") is False
    assert is_inline_or_remote_src("images/a.png") is False


def test_local_image_candidates_include_article_dir_for_stage_paths(tmp_path) -> None:
    html_path = tmp_path / "article" / "_pdf_html_polish_stages" / "02.en.polish.html"
    html_path.parent.mkdir(parents=True)

    candidates = local_image_candidates(html_path, "images/fig%201.png?cache=1#frag")

    assert candidates == [
        (html_path.parent / "images" / "fig 1.png").resolve(strict=False),
        (html_path.parent.parent / "images" / "fig 1.png").resolve(strict=False),
    ]


def test_missing_local_images_reports_unique_local_sources(tmp_path) -> None:
    html_path = tmp_path / "article" / "_pdf_html_polish_stages" / "02.en.polish.html"
    html_path.parent.mkdir(parents=True)
    (html_path.parent / "present.png").write_bytes(b"png")
    html = "\n".join(
        [
            "<p>before</p>",
            '<img src="present.png">',
            '<img src="missing.png">',
            '<img src="missing.png">',
            '<img src="https://example.test/remote.png">',
        ]
    )

    missing = missing_local_images(html_path, html)

    assert len(missing) == 1
    assert missing[0]["src"] == "missing.png"
    assert missing[0]["line"] == 3


def test_image_identity_key_hashes_data_and_local_file_sources(tmp_path) -> None:
    html_path = tmp_path / "article" / "_pdf_html_polish_stages" / "02.en.polish.html"
    html_path.parent.mkdir(parents=True)
    image_path = html_path.parent / "fig.png"
    image_path.write_bytes(b"figure-bytes")
    data_src = "data:image/png;base64,AAAA"

    assert image_identity_key(html_path, data_src) == (
        "data:" + hashlib.sha256(data_src.encode("utf-8")).hexdigest()
    )
    assert image_identity_key(html_path, "fig.png") == (
        "file:" + hashlib.sha256(b"figure-bytes").hexdigest()
    )
    assert image_identity_key(html_path, "missing.png") == "src:missing.png"
    assert image_identity_key(html_path, "https://example.test/remote.png") is None


def test_image_asset_defects_reports_missing_local_images(tmp_path) -> None:
    html_path = tmp_path / "article" / "_pdf_html_polish_stages" / "02.en.polish.html"
    html_path.parent.mkdir(parents=True)

    defects = image_asset_defects(html_path, '<img src="missing.png">', stage="02.en.polish.html")

    assert [defect.id for defect in defects] == ["P20"]
    assert defects[0].snippet == "missing image src=missing.png"
    assert defects[0].first_broken_stage == "02.en.polish.html"


def test_figure_visual_identity_defects_reports_duplicate_distinct_figures(tmp_path) -> None:
    html_path = tmp_path / "article" / "_pdf_html_polish_stages" / "02.en.polish.html"
    html_path.parent.mkdir(parents=True)
    data_url = "data:image/png;base64,AAAA"
    html = (
        '<div id="fig-5" class="z2m-figure-unit">'
        f'<p><img src="{data_url}"></p>'
        '<p class="z2m-figure-caption">Figure 5. First.</p>'
        "</div>"
        '<div id="fig-6" class="z2m-figure-unit">'
        f'<p><img src="{data_url}"></p>'
        '<p class="z2m-figure-caption">Figure 6. Second.</p>'
        "</div>"
    )
    figure_unit_re = re.compile(
        r"<div\b(?=[^>]*\bz2m-figure-unit\b)(?=[^>]*\bid\s*=\s*['\"](?P<id>fig-[^'\"]+)['\"])[^>]*>"
        r"(?P<body>.*?)</div>",
        re.IGNORECASE | re.DOTALL,
    )
    caption_node_re = re.compile(
        r"<p\b(?=[^>]*\bz2m-figure-caption\b)[^>]*>(?P<body>.*?)</p>",
        re.IGNORECASE | re.DOTALL,
    )

    defects = figure_visual_identity_defects(
        html_path,
        html,
        stage="02.en.polish.html",
        figure_unit_re=figure_unit_re,
        figure_caption_node_re=caption_node_re,
        figure_caption_number_from_caption_node=lambda body: int(re.search(r"\d+", body).group(0)),
    )

    assert [defect.id for defect in defects] == ["P96"]
    assert defects[0].extra["figure_ids"] == ["fig-5", "fig-6"]
