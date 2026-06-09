from pathlib import Path

from zoteropdf2md.html_stages import (
    HTML_STAGE_DIR_NAME,
    POLISH_STAGE_NAME,
    RAW_STAGE_NAME,
    TRANSLATE_STAGE_NAME,
    article_dir_from_html_stage,
    article_name_from_html_stage,
    is_html_stage_path,
)


def test_html_stage_constants_and_article_helpers() -> None:
    stage_path = Path("root") / "Article Name" / HTML_STAGE_DIR_NAME / RAW_STAGE_NAME
    flat_path = Path("root") / "Article Name" / POLISH_STAGE_NAME

    assert RAW_STAGE_NAME == "01.en.raw.html"
    assert POLISH_STAGE_NAME == "02.en.polish.html"
    assert TRANSLATE_STAGE_NAME == "03.ru.translate.html"
    assert is_html_stage_path(stage_path)
    assert not is_html_stage_path(flat_path)
    assert article_dir_from_html_stage(stage_path) == Path("root") / "Article Name"
    assert article_name_from_html_stage(stage_path) == "Article Name"
    assert article_dir_from_html_stage(flat_path) == Path("root") / "Article Name"
