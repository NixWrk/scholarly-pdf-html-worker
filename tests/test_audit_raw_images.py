from pdf_html_polish.quality_loop.audit_raw_images import image_refs, image_summary, resolve_image_ref, sidecar_images


def test_image_refs_reads_quoted_and_bare_sources() -> None:
    html = '<img src="one.png"><img src=two.jpg><img alt="ignored">'

    assert image_refs(html) == ["one.png", "two.jpg"]


def test_resolve_image_ref_classifies_local_remote_data_and_missing(tmp_path) -> None:
    article_dir = tmp_path / "article"
    stage_dir = article_dir / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    (stage_dir / "fig one.png").write_bytes(b"image")

    kind, resolved = resolve_image_ref("fig%20one.png", article_dir, stage_dir)
    assert kind == "local"
    assert resolved == (stage_dir / "fig one.png").resolve(strict=False)

    assert resolve_image_ref("https://example.test/fig.png", article_dir, stage_dir) == ("https", None)
    assert resolve_image_ref("data:image/png;base64,abc", article_dir, stage_dir) == ("data", None)

    missing_kind, missing_path = resolve_image_ref("missing.png", article_dir, stage_dir)
    assert missing_kind == "missing"
    assert missing_path == (article_dir / "missing.png").resolve(strict=False)


def test_image_summary_counts_sidecars_and_reports_missing_refs(tmp_path) -> None:
    article_dir = tmp_path / "article"
    stage_dir = article_dir / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    html_path = stage_dir / "01.en.raw.html"
    (stage_dir / "used.png").write_bytes(b"image")
    (article_dir / "unused.jpg").write_bytes(b"image")
    html_path.write_text(
        '<img src="used.png"><img src="missing.png"><img src="data:image/png;base64,abc">',
        encoding="utf-8",
    )

    summary, defect = image_summary(html_path, html_path.read_text(encoding="utf-8"))

    assert summary["img_tags"] == 3
    assert summary["local_sidecar_files"] == 2
    assert summary["local_refs_resolved"] == 1
    assert summary["data_uri_refs"] == 1
    assert summary["missing_refs"] == ["missing.png"]
    assert summary["unused_sidecars"] == [str((article_dir / "unused.jpg").resolve(strict=False))]
    assert defect is not None
    assert defect.id == "R03"


def test_sidecar_images_collects_article_and_stage_images(tmp_path) -> None:
    article_dir = tmp_path / "article"
    stage_dir = article_dir / "_z2m_stages"
    stage_dir.mkdir(parents=True)
    article_image = article_dir / "article.webp"
    stage_image = stage_dir / "stage.tif"
    article_image.write_bytes(b"image")
    stage_image.write_bytes(b"image")
    (article_dir / "notes.txt").write_text("not image", encoding="utf-8")

    assert sidecar_images(article_dir, stage_dir) == {
        article_image.resolve(strict=False),
        stage_image.resolve(strict=False),
    }
