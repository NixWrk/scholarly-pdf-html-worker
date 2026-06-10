from zoteropdf2md.raw_html_polish.html_fragments import (
    add_body_class,
    add_class_attr,
    add_id_attr,
    matching_div_close_span,
    node_close_end,
    node_has_class,
    node_id_value,
    node_open_id_value,
    strip_node_id_and_add_class,
    transform_node_open,
    visible_text,
)


def test_visible_text_strips_tags_and_normalizes_nonbreaking_spaces() -> None:
    assert visible_text("<p>A&nbsp;<b>B</b>&#160;C\u00a0D</p>") == "A B C D"


def test_class_and_id_helpers_preserve_existing_attrs() -> None:
    assert add_id_attr('<p class="x">', "intro") == '<p class="x" id="intro">'
    assert add_id_attr('<p id="old">', "new") == '<p id="old">'
    assert add_class_attr('<p id="x" class="a">', "b") == '<p id="x" class="a b">'
    assert add_class_attr('<p class="a b">', "b") == '<p class="a b">'
    assert add_body_class('<html><body class="z">x</body></html>', "wide") == (
        '<html><body class="z wide">x</body></html>'
    )


def test_node_helpers_read_and_transform_only_node_open_tag() -> None:
    raw = '<p id="caption-1" class="z2m-figure-caption"><span id="inner">Figure 1</span></p>'
    assert node_id_value(raw) == "caption-1"
    assert node_open_id_value(raw) == "caption-1"
    assert node_has_class(raw, "z2m-figure-caption") is True
    transformed = strip_node_id_and_add_class(raw, "z2m-figure-target")
    assert transformed == '<p class="z2m-figure-caption z2m-figure-target"><span id="inner">Figure 1</span></p>'


def test_transform_node_open_ignores_non_float_nodes() -> None:
    assert transform_node_open("<div>x</div>", lambda tag: tag.replace("<div", "<section")) == "<div>x</div>"
    assert transform_node_open("<table><tr></tr></table>", lambda tag: tag.replace("<table", "<table data-x=\"1\"")) == (
        '<table data-x="1"><tr></tr></table>'
    )


def test_close_span_helpers_find_balanced_div_and_simple_node_end() -> None:
    html = '<div id="outer"><p>x</p><div id="inner">y</div></div><p>tail</p>'
    open_end = html.find(">") + 1
    assert matching_div_close_span(html, open_end) == (47, 53)
    assert node_close_end("<p>one</p><p>two</p>", "p", 3) == 10
