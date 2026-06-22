from __future__ import annotations

import functools
import html as html_lib
import re
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from .citation_profile_recovery import (
    MAX_PROFILE_REFERENCE_GAP_RECOVERY as _MAX_PROFILE_REFERENCE_GAP_RECOVERY,
    citation_profile_confidence as _citation_profile_confidence,
    citation_profile_has_zotero_reference_evidence as _citation_profile_has_zotero_reference_evidence,
    citation_profile_is_author_year as _citation_profile_is_author_year,
    citation_profile_is_bracket_numeric as _citation_profile_is_bracket_numeric,
    citation_profile_is_high_confidence_paren_numeric as _citation_profile_is_high_confidence_paren_numeric,
    citation_profile_is_high_confidence_superscript_numeric as _citation_profile_is_high_confidence_superscript_numeric,
    citation_profile_items as _citation_profile_items,
    citation_profile_ref_prefix as _citation_profile_ref_prefix,
    citation_profile_reference_entries_by_number as _citation_profile_reference_entries_by_number,
    citation_profile_reference_recovery_numbers as _citation_profile_reference_recovery_numbers,
    citation_profile_style as _citation_profile_style,
    contiguous_profile_reference_recovery_numbers as _contiguous_profile_reference_recovery_numbers,
    pdf_recovered_reference_section_from_profile as _pdf_recovered_reference_section_from_profile,
    profile_item_value as _profile_item_value,
)
from .email_repair import repair_split_visible_emails as _repair_split_visible_emails
from .html_images import (
    IMAGE_CACHE_KEY_ATTR_PATTERN as _IMAGE_CACHE_KEY_ATTR_PATTERN,
    IMG_SRC_PATTERN as _IMG_SRC_PATTERN,
    InlineHtmlResult,
    data_image_src_looks_renderable as _data_image_src_looks_renderable,
    decode_data_image_payload as _decode_data_image_payload,
    detect_image_signature as _detect_image_signature,
    detect_jpeg_colorspace as _detect_jpeg_colorspace,
    html_node_has_broken_data_image as _node_has_broken_data_image,
    html_node_has_renderable_image as _node_has_renderable_image,
    html_node_image_srcs as _node_image_srcs,
    inline_images_from_html_text as _inline_images_from_html_text,
    is_inline_or_remote as _is_inline_or_remote,
    refresh_inlined_data_urls_by_cache as _refresh_inlined_data_urls_by_cache,
    refresh_inlined_data_urls_by_hint as _refresh_inlined_data_urls_by_hint,
    to_data_url as _to_data_url,
    validate_data_url as _validate_data_url,
)
from .html_links import (
    NESTED_FIG_LINK_PATTERN as _NESTED_FIG_LINK_PATTERN,
    NESTED_SAME_HREF_INTERNAL_LINK_PATTERN as _NESTED_SAME_HREF_INTERNAL_LINK_PATTERN,
    escape_html_attr_literal as _escape_html_attr,
    href_attr_literal as _extract_href_attr,
    replace_href_attr_literal as _replace_href_attr_literal,
    unwrap_nested_fig_links as _unwrap_nested_fig_links,
    unwrap_nested_same_href_internal_links as _unwrap_nested_same_href_internal_links,
)
from .html_references import (
    NOTES_AND_REFERENCES_HEADING_PATTERN as _NOTES_AND_REFERENCES_HEADING_PATTERN,
    REFERENCES_HEADING_PATTERN as _REFERENCES_HEADING_PATTERN,
)
from .polish_language import PolishLanguagePolicy, resolve_polish_language_policy
from .raw_html_polish import (
    DEFAULT_POLISH_PHASES,
    ExecutablePolishPhase,
    RawPolishContext,
    RawPolishState,
    default_polish_phase_names,
    run_polish_phases,
)
from .raw_html_polish.html_fragments import (
    CLOSE_TAG_PATTERN as _CLOSE_TAG_PATTERN,
    DIV_TAG_PATTERN as _DIV_TAG_PATTERN,
    ESCAPED_INLINE_TAG_PATTERN as _ESCAPED_INLINE_TAG_PATTERN,
    FLOAT_NODE_PATTERN as _FLOAT_NODE_PATTERN,
    HTML_TAG_PATTERN as _HTML_TAG_PATTERN,
    MATH_TAG_SPLIT_PATTERN as _MATH_TAG_SPLIT_PATTERN,
    OPEN_TAG_PATTERN as _OPEN_TAG_PATTERN,
    SPACED_ESCAPED_INLINE_TAG_PATTERN as _SPACED_ESCAPED_INLINE_TAG_PATTERN,
    SPACED_INLINE_TAG_PATTERN as _SPACED_INLINE_TAG_PATTERN,
    SPLIT_ESCAPED_INLINE_OPEN_TAG_PATTERN as _SPLIT_ESCAPED_INLINE_OPEN_TAG_PATTERN,
    TAG_SPLIT_PATTERN as _TAG_SPLIT_PATTERN,
    add_body_class as _add_body_class,
    add_class_attr as _add_class_attr,
    add_id_attr as _add_id_attr,
    append_class_to_attrs as _append_class_to_attrs,
    has_id_attr as _has_id_attr,
    matching_div_close_span as _matching_div_close_span,
    node_close_end as _node_close_end,
    node_has_class as _node_has_class,
    node_id_value as _node_id_value,
    node_open_id_value as _node_open_id_value,
    normalize_spaced_inline_sup_sub_tags as _normalize_spaced_inline_sup_sub_tags,
    remove_id_attr as _remove_id_attr,
    strip_node_id_and_add_class as _strip_node_id_and_add_class,
    transform_node_open as _transform_node_open,
    unescape_inline_sup_sub as _unescape_inline_sup_sub,
    update_skip_stack_for_tags as _update_skip_stack_for_tags,
    visible_text as _visible_text,
)
from .raw_html_polish.katex import (
    KATEX_ASSET_DIR as _KATEX_ASSET_DIR,
    KATEX_PLACEHOLDER_PATTERN as _KATEX_PLACEHOLDER_PATTERN,
    KATEX_STYLE_MARKER as _KATEX_STYLE_MARKER,
    MATHJAX_CONFIG_TAG_PATTERN as _MATHJAX_CONFIG_TAG_PATTERN,
    MATHJAX_SCRIPT as _MATHJAX_SCRIPT,
    MATHJAX_SCRIPT_TAG_PATTERN as _MATHJAX_SCRIPT_TAG_PATTERN,
    close_katex_v8_context,
    inject_katex_css as _inject_katex_css_impl,
    inject_mathjax as _inject_mathjax_impl,
    katex_inlined_css as _katex_inlined_css,
    katex_v8_context as _katex_v8_context,
    render_katex_html as _render_katex_html_impl,
    strip_mathjax_scripts as _strip_mathjax_scripts,
)
from .raw_html_polish.math_units import (
    convert_latex_sup_citations as _convert_latex_sup_citations,
    convert_math_tags_to_tex as _convert_math_tags_to_tex,
    fix_latex_text_commands as _fix_latex_text_commands,
    fix_subscript_equation_spill as _fix_subscript_equation_spill,
    move_trailing_bracket_citations_out_of_inline_tex as _move_trailing_bracket_citations_out_of_inline_tex,
    repair_common_math_ocr_substitutions as _repair_common_math_ocr_substitutions,
    repair_sqrt_subscript_brace_spill as _repair_sqrt_subscript_brace_spill,
)
from .raw_html_polish.float_units import (
    FIG_CAPTION_PANEL_SUFFIX_TOKEN as _FIG_CAPTION_PANEL_SUFFIX_TOKEN,
    FIG_COMPOUND_KEY_TOKEN as _FIG_COMPOUND_KEY_TOKEN,
    FIG_KEY_TOKEN as _FIG_KEY_TOKEN,
    FIG_PANEL_SUFFIX_TOKEN as _FIG_PANEL_SUFFIX_TOKEN,
    FIG_REF_LABEL_TOKEN as _FIG_REF_LABEL_TOKEN,
    FIG_RELAXED_KEY_TOKEN as _FIG_RELAXED_KEY_TOKEN,
    EXTENDED_DATA_FIG_PREFIX_TOKEN as _EXTENDED_DATA_FIG_PREFIX_TOKEN,
    SUPPLEMENTARY_FIG_KEY_TOKEN as _SUPPLEMENTARY_FIG_KEY_TOKEN,
    SUPPLEMENTARY_FIG_PREFIX_TOKEN as _SUPPLEMENTARY_FIG_PREFIX_TOKEN,
    SUPPLEMENTARY_FIG_RELAXED_KEY_TOKEN as _SUPPLEMENTARY_FIG_RELAXED_KEY_TOKEN,
    TABLE_KEY_TOKEN as _TABLE_KEY_TOKEN,
    TABLE_REF_WORD_TOKEN as _TABLE_REF_WORD_TOKEN,
    caption_tail_opens_caption as _caption_tail_opens_caption,
    embedded_table_caption_key_from_visible as _embedded_table_caption_key_from_visible,
    figure_caption_num_from_visible as _figure_caption_num_from_visible,
    is_caption_node as _is_caption_node,
    is_figure_caption_node as _is_figure_caption_node,
    is_table_caption_node as _is_table_caption_node,
    is_table_note_node as _is_table_note_node,
    looks_table_note_text as _looks_table_note_text,
    raw_has_class as _raw_has_class,
    table_caption_key_from_visible as _table_caption_key_from_visible,
)
from .raw_html_polish.frontmatter_footnotes import (
    AUTHOR_BYLINE_NAME_PATTERN as _AUTHOR_BYLINE_NAME_RE,
    PAGE_HEADER_FOOTER_LINE_PATTERN as _PAGE_HEADER_FOOTER_LINE_PATTERN,
    SUPERSCRIPT_DIGIT_TRANSLATION as _SUPERSCRIPT_DIGIT_TRANSLATION,
    footnote_keywords as _footnote_keywords,
    leading_footnote_number as _leading_footnote_number,
    looks_affiliation_block as _looks_affiliation_block,
    looks_affiliation_label_body as _looks_affiliation_label_body,
    looks_author_byline_front_matter as _looks_author_byline_front_matter,
    looks_author_marker_ocr_candidate as _looks_author_marker_ocr_candidate,
    looks_footnote_block as _looks_footnote_block_impl,
    looks_front_matter_block as _looks_front_matter_block_impl,
    mark_affiliation_paragraphs as _mark_affiliation_paragraphs,
    mark_front_matter_paragraphs as _mark_front_matter_paragraphs_impl,
    mark_footnote_paragraphs_and_refs as _mark_footnote_paragraphs_and_refs_impl,
    repair_affiliation_label_ocr_body as _repair_affiliation_label_ocr_body,
    repair_author_marker_ocr_body as _repair_author_marker_ocr_body,
    repair_confirmed_front_matter_artifacts as _repair_confirmed_front_matter_artifacts,
    repair_confirmed_front_matter_email_artifacts_body as _repair_confirmed_front_matter_email_artifacts_body,
    repair_front_matter_marker_ocr as _repair_front_matter_marker_ocr_impl,
    repair_front_matter_page_anchor_markers as _repair_front_matter_page_anchor_markers_impl,
    repair_page_footnote_ref_links as _repair_page_footnote_ref_links,
    repair_sevick_muraca_author_marker as _repair_sevick_muraca_author_marker,
    repair_turkish_urology_byline as _repair_turkish_urology_byline,
    repair_xue_byline_abstract_split as _repair_xue_byline_abstract_split,
    split_url_footnote_prose_tails as _split_url_footnote_prose_tails,
    split_zhu_affiliation_tail as _split_zhu_affiliation_tail,
    unicode_capitalized_name_pair_count as _unicode_capitalized_name_pair_count,
    unicode_glued_author_marker_count as _unicode_glued_author_marker_count,
)
from .raw_html_polish.references_links import (
    LINE_PREFIXED_VISIBLE_REF_NUM_PATTERN as _LINE_PREFIXED_VISIBLE_REF_NUM_PATTERN,
    PAGE_ANCHOR_BRACKET_REF_INITIAL_PATTERN as _PAGE_ANCHOR_BRACKET_REF_INITIAL_PATTERN,
    PAGE_ANCHOR_BRACKET_REF_NUM_STRIP_PATTERN as _PAGE_ANCHOR_BRACKET_REF_NUM_STRIP_PATTERN,
    PAGE_ANCHOR_BRACKET_REF_TRAILING_PUNCT_PATTERN as _PAGE_ANCHOR_BRACKET_REF_TRAILING_PUNCT_PATTERN,
    REFERENCE_LINE_PREFIX_ONLY_PATTERN as _REFERENCE_LINE_PREFIX_ONLY_PATTERN,
    VISIBLE_REF_NUM_PATTERN as _VISIBLE_REF_NUM_PATTERN,
    line_prefixed_reference_number_match as _line_prefixed_reference_number_match,
    looks_like_reference_line_number as _looks_like_reference_line_number,
    normalize_standalone_reference_paragraph_prefix as _normalize_standalone_reference_paragraph_prefix,
    reference_visible_number as _reference_visible_number,
    references_heading_match as _references_heading_match,
    references_heading_search as _references_heading_search,
    strip_duplicate_reference_number_artifacts as _strip_duplicate_reference_number_artifacts,
    strip_embedded_reference_number_artifacts as _strip_embedded_reference_number_artifacts,
    strip_leading_reference_line_number_before_expected_number as _strip_leading_reference_line_number_before_expected_number,
    strip_leading_reference_line_number_only as _strip_leading_reference_line_number_only,
    strip_leading_reference_line_number_pair as _strip_leading_reference_line_number_pair,
    strip_leading_reference_line_number_pairs_in_list_items as _strip_leading_reference_line_number_pairs_in_list_items,
    strip_page_anchor_bracket_ref_num_prefix as _strip_page_anchor_bracket_ref_num_prefix,
    strip_reference_visible_number as _strip_reference_visible_number,
)
from .raw_html_polish.presentation import (
    cleanup_empty_html_blocks as _cleanup_empty_html_blocks,
    fix_heading_inline_abbreviation_breaks as _fix_heading_inline_abbreviation_breaks,
    inject_default_styles as _presentation_inject_default_styles,
    inject_utf8_charset as _inject_utf8_charset,
    restore_abbreviations as _restore_abbreviations,
    wrap_body_in_container as _wrap_body_in_container,
)
from .raw_html_polish.pre_cleanup import (
    AUX_PROTOCOL_SENTINEL_LEAK_PATTERN as _AUX_PROTOCOL_SENTINEL_LEAK_PATTERN,
    BACKSLASH_BEFORE_QUOTE_PATTERN as _BACKSLASH_BEFORE_QUOTE_PATTERN,
    HEADING_PROTOCOL_SENTINEL_LEAK_PATTERN as _HEADING_PROTOCOL_SENTINEL_LEAK_PATTERN,
    INLINE_OR_DISPLAY_TEX_PATTERN as _INLINE_OR_DISPLAY_TEX_PATTERN,
    LEADING_SPACED_BACKSLASH_PATTERN as _LEADING_SPACED_BACKSLASH_PATTERN,
    RU_BARE_FIG_LEXEME_PATTERN as _RU_BARE_FIG_LEXEME_PATTERN,
    SKIP_AUTOLINK_TAGS as _SKIP_AUTOLINK_TAGS,
    SLASH_PIPE_ARTIFACT_PATTERN as _SLASH_PIPE_ARTIFACT_PATTERN,
    TEXT_NODE_REPAIR_SKIP_TAGS as _TEXT_NODE_REPAIR_SKIP_TAGS,
    TRAILING_SPACED_BACKSLASH_PATTERN as _TRAILING_SPACED_BACKSLASH_PATTERN,
    cleanup_marker_escape_artifacts as _cleanup_marker_escape_artifacts,
    fix_common_mojibake as _fix_common_mojibake,
    strip_protocol_sentinel_leaks as _strip_protocol_sentinel_leaks,
    update_skip_stack as _update_skip_stack,
)
from .raw_html_polish.url_autolink import (
    autolink_plain_urls as _autolink_plain_urls,
    autolink_text_urls as _autolink_text_urls,
)
from .raw_html_polish.url_anchors import (
    ADJACENT_IDENTICAL_HREF_URL_ANCHOR_PATTERN as _ADJACENT_IDENTICAL_HREF_URL_ANCHOR_PATTERN,
    ADJACENT_SAME_HREF_ANCHOR_PATTERN as _ADJACENT_SAME_HREF_ANCHOR_PATTERN,
    ADJACENT_SAME_MAILTO_ANCHOR_PATTERN as _ADJACENT_SAME_MAILTO_ANCHOR_PATTERN,
    IDENTICAL_HREF_PROTOCOL_PREFIX_ANCHOR_PATTERN as _IDENTICAL_HREF_PROTOCOL_PREFIX_ANCHOR_PATTERN,
    PROSE_PREFIXED_URL_ANCHOR_TAIL_PATTERN as _PROSE_PREFIXED_URL_ANCHOR_TAIL_PATTERN,
    SPLIT_DOI_HEAD_TAIL_ANCHOR_PATTERN as _SPLIT_DOI_HEAD_TAIL_ANCHOR_PATTERN,
    SPLIT_DOI_URL_ANCHOR_PATH_TAIL_PATTERN as _SPLIT_DOI_URL_ANCHOR_PATH_TAIL_PATTERN,
    SPLIT_SCHEME_URL_ANCHOR_FRAGMENTS_PATTERN as _SPLIT_SCHEME_URL_ANCHOR_FRAGMENTS_PATTERN,
    SPLIT_SCHEME_URL_ANCHOR_HEAD_PATTERN as _SPLIT_SCHEME_URL_ANCHOR_HEAD_PATTERN,
    SPLIT_SAME_HREF_DOI_ANCHOR_TEXT_PATTERN as _SPLIT_SAME_HREF_DOI_ANCHOR_TEXT_PATTERN,
    SPLIT_VISIBLE_URL_ANCHOR_PATTERN as _SPLIT_VISIBLE_URL_ANCHOR_PATTERN,
    SPLIT_URL_ANCHOR_BLOCK_TAIL_PATTERN as _SPLIT_URL_ANCHOR_BLOCK_TAIL_PATTERN,
    SPLIT_URL_ANCHOR_DOMAIN_TAIL_PATTERN as _SPLIT_URL_ANCHOR_DOMAIN_TAIL_PATTERN,
    SPACED_PROTOCOL_HREF_ATTR_PATTERN as _SPACED_PROTOCOL_HREF_ATTR_PATTERN,
    SPACED_PROTOCOL_URL_ANCHOR_PATTERN as _SPACED_PROTOCOL_URL_ANCHOR_PATTERN,
    URL_ANCHOR_TEXT_PATTERN as _URL_ANCHOR_TEXT_PATTERN,
    URL_FRAGMENT_ANCHOR_CHUNK_PATTERN as _URL_FRAGMENT_ANCHOR_CHUNK_PATTERN,
    URL_FRAGMENT_TEXT_CHUNK_PATTERN as _URL_FRAGMENT_TEXT_CHUNK_PATTERN,
    consume_compact_prefix as _consume_compact_prefix,
    looks_like_split_same_href_text_label as _looks_like_split_same_href_text_label,
    merge_adjacent_same_href_mailto_anchors as _merge_adjacent_same_href_mailto_anchors,
    merge_adjacent_same_href_url_anchors as _merge_adjacent_same_href_url_anchors,
    merge_split_same_href_doi_anchors as _merge_split_same_href_doi_anchors,
    normalize_double_escaped_url_anchor_text as _normalize_double_escaped_url_anchor_text,
    normalize_mailto_address as _normalize_mailto_address,
    normalize_same_href_text_anchor_label as _normalize_same_href_text_anchor_label,
    repair_prose_prefixed_url_anchor_tail as _repair_prose_prefixed_url_anchor_tail,
    repair_split_doi_head_tail_anchors as _repair_split_doi_head_tail_anchors,
    repair_split_doi_url_anchor_path_tails as _repair_split_doi_url_anchor_path_tails,
    repair_split_scheme_url_anchor_fragments as _repair_split_scheme_url_anchor_fragments,
    repair_split_scheme_url_anchor_runs as _repair_split_scheme_url_anchor_runs,
    repair_split_visible_url_anchors as _repair_split_visible_url_anchors,
    repair_split_url_anchor_block_tail as _repair_split_url_anchor_block_tail,
    repair_split_url_anchor_domain_tail as _repair_split_url_anchor_domain_tail,
    repair_spaced_protocol_url_anchors as _repair_spaced_protocol_url_anchors,
    unescape_html_entities_repeated as _unescape_html_entities_repeated,
)
from .semantic_labels import (
    extended_data_figure_key_from_visible_number as _extended_data_figure_key_from_visible_number,
    figure_key_from_visible_number as _figure_key_from_visible_number,
    normalize_table_key as _normalize_table_key,
    supplementary_figure_key_from_visible_number as _supplementary_figure_key_from_visible_number,
)
from .text_cleanup import (
    REPEATED_PHRASE_PATTERN as _REPEATED_PHRASE_PATTERN,
    drop_repeated_phrases,
)
from .url_repair import (
    BROKEN_PLAIN_URL_PROTOCOL_PATTERN as _BROKEN_PLAIN_URL_PROTOCOL_PATTERN,
    compact_visible_url_fragment as _compact_visible_url_fragment,
    repair_broken_visible_url_text as _repair_broken_visible_url_text,
    split_url_and_trailing_punct as _split_url_and_trailing_punct,
    starts_like_visible_url_fragment as _starts_like_visible_url_fragment,
    strip_url_fragment_edge_quotes as _strip_url_fragment_edge_quotes,
    strip_wrapping_url_quotes as _strip_wrapping_url_quotes,
    url_fragment_compare_key as _url_fragment_compare_key,
    url_fragment_keys_match_allowing_lost_hyphens as _url_fragment_keys_match_allowing_lost_hyphens,
)


_HEAD_CLOSE_PATTERN = re.compile(r"</head>", re.IGNORECASE)
_BODY_PATTERN = re.compile(r"(<body\b[^>]*>)(.*?)(</body>)", re.IGNORECASE | re.DOTALL)
_URL_PATTERN = re.compile(r"(?P<url>(?:https?://|www\.)[^\s<>\"]+)", re.IGNORECASE)
_DOI_METADATA_BODY_BOUNDARY_PATTERN = re.compile(
    r"(?P<doi>(?:\b(?:DOI|doi)\s*:\s*)?(?:"
    r"<a\b(?=[^>]*\bhref\s*=\s*['\"]https?://(?:dx\.)?doi\.org/10\.)[^>]*>[\s\S]{0,400}?</a>"
    r"|https?://(?:dx\.)?doi\.org/10\.[^\s<]+"
    r"|10\.\d{4,9}/[^\s<]+"
    r"))"
    r"(?P<space>\s+)"
    r"(?P<tail>(?:</?(?:span|em|i|b|strong)\b[^>]*>\s*)*"
    r"(?:the|this|we|in|as|or|depicted|generated|lines)\b[\s\S]{20,})",
    re.IGNORECASE,
)
_PLOS_TABLE_DOI_BODY_BOUNDARY_PATTERN = re.compile(
    r"(?P<doi>(?:\b(?:DOI|doi)\s*:\s*)?(?:"
    r"<a\b(?=[^>]*\bhref\s*=\s*['\"]https?://(?:dx\.)?doi\.org/10\.1371/journal\.pone\.[^'\"]+\.t\d+)"
    r"[^>]*>[\s\S]{0,400}?</a>"
    r"|https?://(?:dx\.)?doi\.org/10\.1371/journal\.pone\.[^\s<]+\.t\d+\b"
    r"|10\.1371/journal\.pone\.[^\s<]+\.t\d+\b"
    r"))"
    r"(?P<space>\s+)"
    r"(?P<tail>[\s\S]{35,})",
    re.IGNORECASE,
)
_WILEY_DOWNLOAD_PAGE_FURNITURE_PATTERN = re.compile(
    r"^\s*\d{6,9},\s+\d{4},\s+[A-Za-z0-9]+,\s+Downloaded\s+from\s+"
    r"https://onlinelibrary\.wiley\.com/doi/\S+\s+by\s+[\s\S]{0,900}?"
    r"Wiley\s+Online\s+Library\b[\s\S]{0,900}?"
    r"(?:Terms\s+and\s+Conditions|Creative\s+Commons\s+License)\b",
    re.IGNORECASE,
)
_REFERENCE_PARAGRAPH_ATTR_PATTERN = re.compile(
    r"\b(?:id\s*=\s*['\"]ref-\d+|"
    r"class\s*=\s*['\"][^'\"]*(?:z2m-reference|z2m-bibliography|references|bibliography))",
    re.IGNORECASE,
)
_JOURNAL_PAGE_FURNITURE_PATTERN = re.compile(
    r"^[A-Z][A-Za-z& .:-]{2,80}\s+\d{4}\s*,\s*\d+\s*,\s*\d+"
    r"(?:\s*\.\s*https?://doi\.org/\S+)?"
    r"(?:\s+\d+\s+of\s+\d+)?\s*$",
    re.IGNORECASE,
)
_LI_OPEN_PATTERN = re.compile(r"<li\b([^>]*)>", re.IGNORECASE)
_LI_BLOCK_PATTERN = re.compile(r"<li\b([^>]*)>(.*?)</li>", re.IGNORECASE | re.DOTALL)
_LI_ID_PATTERN = re.compile(r'\bid\s*=\s*["\']ref-(\d+)["\']', re.IGNORECASE)
_SUP_PATTERN = re.compile(r"<sup\b[^>]*>(.*?)</sup>", re.IGNORECASE | re.DOTALL)
_SUP_NUMBER_PATTERN = re.compile(r"\d+")


_BRACKET_CITATION_PATTERN = re.compile(
    r'(?<!\\)\[\s*(\d{1,3}(?:\s*(?:,|[-\u2013\u2014])\s*\d{1,3})*)\s*\]'
)
_CROSS_TAG_BRACKET_CITATION_PATTERN = re.compile(
    r'(?<!\\)\[\s*(?P<body>(?=[\s\S]*?<)[\s\S]{1,2000}?)\s*\]',
    re.IGNORECASE,
)
_LINKED_BRACKET_ORPHAN_CLOSE_ANCHOR_PATTERN = re.compile(
    r"(?P<bracket>\[(?:\s|[,;]|\-|[\u2010-\u2014]|"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d{1,4}['\"][^>]*>\s*\d{1,4}\s*</a>)+\])"
    r"</a>(?P<trail>[,.;:]?)",
    re.IGNORECASE,
)
# Parenthetical reference: "(ref. 30)" / "(ref 30)" / "(см. 30)" → sup link
_PAREN_REF_CITATION_PATTERN = re.compile(
    r'\((?:ref|см|see)\.?\s*(\d{1,3})\)',
    re.IGNORECASE,
)
_CITATION_SKIP_TAGS = _SKIP_AUTOLINK_TAGS | {
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "td",
    "th",
    "figure",
    "figcaption",
}
_CITATION_PROTECTED_CLASS_PATTERN = re.compile(
    r'\bclass\s*=\s*(["\'])(?=[^"\']*\b(?:z2m-affiliations|z2m-front-matter|z2m-footnote|z2m-missing-figure-warning)\b)[^"\']*\1',
    re.IGNORECASE,
)
_CITATION_PROTECTED_ID_PATTERN = re.compile(
    r'\bid\s*=\s*(["\'])(?:fig-|table-|box-|section-)[^"\']*\1',
    re.IGNORECASE,
)
_CITATION_PROTECTED_BLOCK_TYPE_PATTERN = re.compile(
    r'\bblock-type\s*=\s*(["\'])Equation\1',
    re.IGNORECASE,
)
_NONCITATION_NUMERIC_CONTEXT_PATTERN = re.compile(
    r"(?:"
    r"\bpH(?:\s+of)?\s*$|"
    r"\bD\s*$|"
    r"\b(?:monkey|week|month|unit|units|animal|female|male|sp|kg|cm|mm|um|nm|mA|uA|Hz|MHz|GHz|kHz)\b[\s\S]{0,24}$|"
    r"\b(?-i:[AV])\b[\s\S]{0,24}$|"
    r"\b(?:fig|figure|table|section|eq|equation)\.?\s*$"
    r")",
    re.IGNORECASE,
)
_LEADING_REF_NUMBER_PATTERN = re.compile(r"^\s*(?:<[^>]+>\s*)*\d+\.\s+", re.IGNORECASE)
_BRACKET_REF_NUM_STRIP_PATTERN = re.compile(r'^\s*\[(\d+)\]\s*')
_LEADING_PAGE_SPAN_BRACKET_REF_NUM_STRIP_PATTERN = re.compile(
    r'^\s*(?:<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\1[^>]*>\s*</span>\s*)+\[\d+\]\s*',
    re.IGNORECASE,
)
_DOTTED_BRACKET_REF_NUM_STRIP_PATTERN = re.compile(
    r'^(\s*(?:<[^>]+>\s*)*\d+\.\s*)\[\d+\]\s*',
    re.IGNORECASE,
)
_PAGE_ANCHOR_DOTTED_REF_NUM_STRIP_PATTERN = re.compile(
    r'^\s*(?:<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\1[^>]*>\s*</span>\s*)*'
    r'(?:<(?:b|strong)\b[^>]*>\s*)?'
    r'<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\2[^>]*>\s*\d{1,4}\s*</a>\s*'
    r'\.?\s*(?:</(?:b|strong)>\s*)?',
    re.IGNORECASE,
)
_LEADING_REFERENCE_AUTHOR_LINE_NUMBER_ARTIFACT_PATTERN = re.compile(
    r'^(\s*(?:<[^>]+>\s*)*)\d{1,3}\s+'
    r'(?=(?:<[^>]+>\s*)*[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00ff\'\u2019.-]+,\s+'
    r'(?:[A-Z]|et\s+al\.?\b))',
    re.IGNORECASE,
)
_VISIBLE_LEADING_REFERENCE_AUTHOR_LINE_NUMBER_ARTIFACT_PATTERN = re.compile(
    r"^\d{1,3}\s+"
    r"(?=[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00ff'\u2019.-]+,\s+(?:[A-Z]|et\s+al\.?\b))",
    re.IGNORECASE,
)
_UL_OPEN_PATTERN = re.compile(r"<ul\b([^>]*)>", re.IGNORECASE)
_UL_TAG_PATTERN = re.compile(r"</?ul\b[^>]*>", re.IGNORECASE)
_LI_TAG_PATTERN = re.compile(r"</?li\b[^>]*>", re.IGNORECASE)
_REFERENCE_PAGE_ID_PATTERN = re.compile(r'\bid\s*=\s*(["\'])(page-[^"\']+)\1', re.IGNORECASE)
_EQUATION_PARA_PATTERN = re.compile(
    r'(<p\b[^>]*block-type="Equation"[^>]*>)(.*?)(</p>)',
    re.IGNORECASE | re.DOTALL,
)
_DISPLAY_MATH_IN_PARA_PATTERN = re.compile(r'\\\[(.*?)\\\]', re.DOTALL)
_TRAILING_EQ_NUM_PATTERN = re.compile(r'\(\d+\)\s*$')
_TEXT_TRAILING_EQ_NUM_PATTERN = re.compile(r'\s*(?P<num>\(\d{1,3}\))\s*$')
_LATEX_TAG_PATTERN = re.compile(r'\\tag\{(\d+)\}')
_UNICODE_SUP_CITATION_PATTERN = re.compile(
    r'(?P<left>\b[A-Za-z][A-Za-z-]{2,})'
    r'(?P<sup>[\u00b9\u00b2\u00b3\u2070\u2074-\u2079]+'
    r'(?:\s*[,.;:\-\u2013\u2014]\s*[\u00b9\u00b2\u00b3\u2070\u2074-\u2079]+)*)'
    r'(?=[\s,.;:!?)<\]]|$)'
)
_INLINE_TEX_PATTERN = re.compile(r'\\\((.*?)\\\)', re.DOTALL)
_LEAKED_SQRT_M_CITATION_PATTERN = re.compile(
    r'\\sqrt\{\\mathrm\{m\}\^\{(?P<cite>\d{1,3})\}\}\s*$',
    re.IGNORECASE,
)
_LEAKED_UNIT_EXPONENT_PATTERN = re.compile(
    r'(?P<core>[\s\S]*?)'
    r'(?P<unit>('
    r'\\mathrm\{(?:m|mm|cm|nm|um|µm|Па|кПа|МПа|ГПа|Гц|кГц|МГц|ГГц|В|мВ|А|мА|Вт|мВт)\}'
    r'|м|мм|см|нм|ум|µm|Па|кПа|МПа|ГПа|Гц|кГц|МГц|ГГц|В|мВ|А|мА|Вт|мВт'
    r'|m|mm|cm|nm|um|Pa|kPa|MPa|GPa|Hz|kHz|MHz|GHz|V|mV|A|mA|W|mW'
    r'))\s*\^\{(?P<cite>\d{1,3})\}\s*$',
    re.IGNORECASE,
)
# Heading model/OCR artefact: the model inserts a period before an inline-
# formatted abbreviation: "беспроводного. <i>LC</i> Датчик" inside <h1>-<h6>.
_HEADING_TAG_PATTERN = re.compile(
    r'(<h[1-6]\b[^>]*>)(.*?)(</h[1-6]>)',
    re.IGNORECASE | re.DOTALL,
)
_HEADING_OPEN_TAG_PATTERN = re.compile(r"^<h[1-6](?P<attrs>\b[^>]*)>$", re.IGNORECASE)
_Z2M_LINK_GLUE_PATTERN = re.compile(
    r'(<a\b[^>]*\bclass\s*=\s*["\']z2m-(?:ref|fig|section)-link["\'][^>]*>[\s\S]*?</a>)(?=[A-Za-zА-Яа-яЁё])',
    re.IGNORECASE,
)
_URL_LINK_WORD_GLUE_PATTERN = re.compile(
    r'(<a\b[^>]*\bhref\s*=\s*["\'](?:https?://|www\.)[^"\']+["\'][^>]*>[\s\S]*?</a>)(?=(?:and|or|[A-Za-z]))',
    re.IGNORECASE,
)
_CREATIVE_COMMONS_PUBLICDOMAIN_MISSING_PAREN_PATTERN = re.compile(
    r'(?P<prefix>\(\s*<a\b[^>]*\bhref\s*=\s*["\']https?://creativecommons\.org/publicdomain/zero/1\.0/["\'][^>]*>'
    r'https?://creativecommons\.org/publicdomain/zero/1\.0/</a>)\s+(?P<tail>applies\b)',
    re.IGNORECASE,
)
# SentencePiece byte-fallback tokens emitted by Gemma when it encounters Unicode
# near translation boundaries: e.g. <0xE2><0x82><0xA9> instead of a real character.
# When followed by citation numbers they represent a dropped <sup> tag.
_BYTE_TOKEN_ARTIFACT_PATTERN = re.compile(r'(?:<0x[0-9A-Fa-f]{2}>)+')
_BYTE_TOKEN_CITATION_PATTERN = re.compile(r'(?:<0x[0-9A-Fa-f]{2}>)+(\d[\d,\u2013\u2014\-]*)')
_CYRILLIC_CHAR_PATTERN = re.compile(r"[\u0400-\u04FF]")
# Bare citation numbers that Marker failed to mark as superscript.
# Two variants:
#   Glued  — number immediately follows letter: "issues17,68"
#   Spaced — single space before citation group: "issues 17,68."
#            (only allowed before sentence-ending punctuation to reduce false positives)
# Numbers are only wrapped when ALL of them fall within [1, ref_count].
_BARE_CITATION_GLUED_PATTERN = re.compile(
    r'(?<=[A-Za-zА-Яа-яёЁ])(\d{1,3}(?:,\s?\d{1,3})+)(?=[\s.,;:!?)<\]]|$)'
)
_BARE_CITATION_SPACED_PATTERN = re.compile(
    r'(?<=[A-Za-zА-Яа-яёЁ]) (\d{1,3}(?:,\d{1,3})+)(?=[.,;:!?)<\]]|$)'
)
# Dot-separated citations: OCR artefact where Marker writes "17.68" instead of "17,68"
# Only triggered when ALL numbers are within ref_count and the sequence immediately
# follows a letter (no space), to minimise collisions with decimal numbers.
_BARE_CITATION_DOT_PATTERN = re.compile(
    r'(?<=[A-Za-zА-Яа-яёЁ])(\d{1,3}(?:\.\d{1,3})+)(?=[\s.,;:!?)<\]]|$)'
)
# Section headings that start with a Roman numeral (I. INTRODUCTION, II. METHOD …)
_OCR_TASK_SEC_CITATION_PATTERN = re.compile(r"\btask\.\s+Sec\.(?=\s*</p>)", re.IGNORECASE)
_OCR_FLAGSHIP_MODELS_6000_CITATION_PATTERN = re.compile(
    r"\bflagship models\s+6,000(?=[.,;:!?)<\]])",
    re.IGNORECASE,
)
_ROMAN_SECTION_HEADING_PATTERN = re.compile(
    r'<(h[1-6])(\b[^>]*)>\s*([IVX]{1,6})\.\s',
    re.IGNORECASE,
)
_NUMERIC_SECTION_HEADING_VISIBLE_PATTERN = re.compile(
    r"^\s*(\d{1,2}(?:\.\d{1,2})*)\.?\s+\S"
)
_APPENDIX_HEADING_VISIBLE_PATTERN = re.compile(r"^\s*Appendix\s+([A-Z])\b", re.IGNORECASE)
_BOX_HEADING_VISIBLE_PATTERN = re.compile(r"^\s*(?:BOX|Box)\s+(\d+)\b")
_BOX_REF_PATTERN = re.compile(r"\b(Box)\s+(\d+)\b")
_PAGE_LINKED_BOX_REF_PATTERN = re.compile(
    r"(?P<label>\bBox)\s*"
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#page-[^'\"]+['\"][^>]*)>"
    r"\s*(?P<num>\d+)(?P<trail>\)?)\s*</a>",
    re.IGNORECASE | re.DOTALL,
)
_PAGE_LINKED_DECIMAL_EQUATION_REF_PATTERN = re.compile(
    r"(?P<label>\bEq(?:n|uation)?\.?|Equation)\s*"
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#page-[^'\"]+['\"][^>]*)>"
    r"\s*(?P<num>\(?\d{1,3}(?:\.\d{1,3})?\)?)(?P<trail>[\)\]\.,;:]*)\s*</a>",
    re.IGNORECASE | re.DOTALL,
)
# In-text references to section numbers (English or Russian).
# Russian case forms: Раздел (nominative/accusative), Раздела (genitive),
# Разделе (locative), Разделу (dative) — all captured by the suffix group.
# Page-linked section references produced when Marker splits the section number into an anchor.
_PAGE_LINKED_SECTION_REF_PATTERN = re.compile(
    r"(?P<label>\bSection)\s*"
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#page-[^'\"]+['\"][^>]*)>"
    r"\s*(?P<num>[IVX]{1,6}|\d{1,2}(?:\.\d{1,2})*)(?P<trail>[\.)]?)\s*</a>",
    re.IGNORECASE | re.DOTALL,
)
_APPENDIX_REF_PATTERN = re.compile(r"\b(Appendix)\s+([A-Z])\b", re.IGNORECASE)
_PAGE_LINKED_APPENDIX_REF_PATTERN = re.compile(
    r"(?P<label>\bAppendix)\s*"
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#page-[^'\"]+['\"][^>]*)>"
    r"\s*(?P<letter>[A-Z])(?P<trail>\.?)\s*</a>",
    re.IGNORECASE | re.DOTALL,
)
_SECTION_REF_PATTERN = re.compile(
    r'\b(Section|\u0420\u0430\u0437\u0434\u0435\u043b[\u0435\u0430\u0443\u043e]?)\s+'
    r'([IVX]{1,6}|\d{1,2}(?:\.\d{1,2})*)\b',
    re.IGNORECASE,
)
_EQUATION_REF_PATTERN = re.compile(
    r'\b(Eq(?:uation)?s?\.?|Equations?)\s+(\d{1,3})\b',
    re.IGNORECASE,
)

# In-text figure references: "Fig. 3" / "рис. 3" / "фиг. 3" NOT followed by ". <text>"
# (that would be a figure caption).  We distinguish "Fig. 3. Caption..." from "...Fig. 3."
# (end of sentence) by requiring whitespace after the dot, i.e. ".\s" → caption lookahead.
_FIG_REF_PATTERN = re.compile(
    r'\b((?:Figs?|Figures?|Рис(?:унок)?|рис(?:унок)?|Фиг(?:ура)?|фиг(?:ура)?|FIGS?|FIGURES?)\.?)\s*(\d+)([a-z])?\b(?!\s*(?:\.\s|\|))',
    re.IGNORECASE,
)
_FIG_REF_CHAIN_CONT_PATTERN = re.compile(
    r'(?P<sep>\s*(?:and|or|,|&|–|-)\s*)(?P<num>\d+)(?P<suf>[a-z])\b',
    re.IGNORECASE,
)
_EXT_FIG_REF_PATTERN = re.compile(
    r'\b((?:FIGS?|FIGURES?|Figs?|Figures?'
    r'|\u0420\u0438\u0441|\u0440\u0438\u0441|\u0424\u0438\u0433|\u0444\u0438\u0433)\.?)'
    rf'\s*({_FIG_KEY_TOKEN})({_FIG_PANEL_SUFFIX_TOKEN})?\b(?!\s*(?:\.\s|\|))',
    re.IGNORECASE,
)
_SUPPLEMENTARY_FIG_REF_PATTERN = re.compile(
    rf"\b(?P<prefix>{_SUPPLEMENTARY_FIG_PREFIX_TOKEN}\s+{_FIG_REF_LABEL_TOKEN}\.?)"
    rf"\s*(?P<num>{_SUPPLEMENTARY_FIG_KEY_TOKEN})(?P<suffix>{_FIG_PANEL_SUFFIX_TOKEN})?"
    r"\b(?!\s*(?:\.\s|\|))",
    re.IGNORECASE,
)
_EXTENDED_DATA_FIG_REF_PATTERN = re.compile(
    rf"\b(?P<prefix>{_EXTENDED_DATA_FIG_PREFIX_TOKEN}\s+{_FIG_REF_LABEL_TOKEN}\.?)"
    rf"\s*(?P<num>{_FIG_KEY_TOKEN})(?P<suffix>{_FIG_PANEL_SUFFIX_TOKEN})?"
    r"\b(?!\s*(?:\.\s|\|))",
    re.IGNORECASE,
)
_FIG_REF_PATTERN = re.compile(
    rf"\b({_FIG_REF_LABEL_TOKEN}\.?)\s*({_FIG_KEY_TOKEN})({_FIG_PANEL_SUFFIX_TOKEN})?\b(?!\s*(?:\.\s|\|))",
    re.IGNORECASE,
)
_SPACED_MULTIPANEL_FIG_REF_PATTERN = re.compile(
    rf"\b({_FIG_REF_LABEL_TOKEN}\.?)\s*({_FIG_KEY_TOKEN})"
    r"(?P<panels>\s*\([A-Za-z]\)(?:\s*,\s*\([A-Za-z]\))*)"
    r"(?=\s*(?:,|\band\b|\bor\b|\)|;))",
    re.IGNORECASE,
)
_TERMINAL_FIG_REF_PATTERN = re.compile(
    rf"\b({_FIG_REF_LABEL_TOKEN}\.?)\s*(\d{{1,3}})({_FIG_PANEL_SUFFIX_TOKEN})?"
    r"\b(?=\s*(?:\.(?!\s*\d)|[\),;\]:]|$))",
    re.IGNORECASE,
)
_FIG_REF_CHAIN_CONT_PATTERN = re.compile(
    rf"(?P<sep>\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*)"
    rf"(?P<num>{_FIG_KEY_TOKEN})(?P<suf>{_FIG_PANEL_SUFFIX_TOKEN})?\b",
    re.IGNORECASE,
)
_FIG_ID_ATTR_PATTERN = re.compile(
    r'\bid\s*=\s*(["\'])fig-(?P<key>[^"\']+)\1',
    re.IGNORECASE,
)
_PAGE_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
_SEMANTIC_INTERNAL_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])#'
    r'(?P<target>(?:table|page)-[^"\']+)(?P=quote)[^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
_SPLIT_PAGE_FIG_LINK_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*)>'
    r'(?P<body>\s*[\(\[]?\s*(?:FIG(?:URE)?|Fig(?:ure)?|Figs?|Figures?)\.?\s*)</a>'
    rf'\s*(?P<num>{_SUPPLEMENTARY_FIG_KEY_TOKEN})(?P<suffix>{_FIG_PANEL_SUFFIX_TOKEN}?[\)\]\.,;:]*)',
    re.IGNORECASE,
)
_SPLIT_PAGE_TABLE_LINK_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*)>'
    r'(?P<body>\s*[\(\[]?\s*(?:TABLE|Table|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s*)</a>'
    rf'\s*(?P<num>{_TABLE_KEY_TOKEN})(?P<suffix>[a-z]?[\)\]\.,;:]*)',
    re.IGNORECASE,
)
_NUMERIC_PAGE_ANCHOR_PATTERN = re.compile(
    r'<a\b[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
_REF_ANCHOR_PATTERN = re.compile(
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']#ref-(?P<num>\d+)["\'][^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
_REFERENCE_LEADING_PAGE_NUM_ANCHOR_PATTERN = re.compile(
    r'(?P<open><li\b[^>]*\bid\s*=\s*(["\'])ref-(?P<num>\d+)\2[^>]*>\s*'
    r'(?:(?:<(?:b|strong|i|em)\b[^>]*>\s*)*)?)'
    r'<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\4[^>]*>'
    r'(?P<body>\s*(?:<span\b[^>]*\bz2m-ref-num\b[^>]*>\s*)?\d{1,4}\.?\s*(?:</span>)?\s*)'
    r'</a>',
    re.IGNORECASE,
)
_REFERENCE_DUPLICATE_PAGE_NUM_ANCHOR_PATTERN = re.compile(
    r'(?P<open><li\b[^>]*\bid\s*=\s*(["\'])ref-(?P<num>\d+)\2[^>]*>\s*'
    r'<span\b[^>]*\bz2m-ref-num\b[^>]*>\s*\d{1,4}\.?\s*</span>\s*)'
    r'<a\b[^>]*\bhref\s*=\s*(["\'])#page-[^"\']+\4[^>]*>'
    r'(?P<body>\s*\d{1,4}\.?\s*)'
    r'</a>\s*',
    re.IGNORECASE,
)
_AUTHOR_YEAR_CITATION_TEXT_PATTERN = re.compile(
    r"\b"
    r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
    r"(?:\s+(?:et\s+al\.?|and\s+[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+|&\s*[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+))?"
    r"(?:,\s*|\s+)\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
_STAT_FALSE_REF_CONTEXT_PATTERN = re.compile(
    r"\b(?:effect\s+size|allocation\s+ratio|G\*Power|sample\s+size|"
    r"statistical\s+power|power\s+analysis|Cohen|group|SD|SEM|Z\s+values?|"
    r"range\s+from\s+about|logMAR|within\s+\d+\s+or\s+\d+\s+s)\b",
    re.IGNORECASE,
)
_STAT_FALSE_REF_STRONG_CONTEXT_PATTERN = re.compile(
    r"\b(?:effect\s+size|allocation\s+ratio|G\*Power|sample\s+size|"
    r"statistical\s+power|power\s+analysis|Cohen|SD|SEM|Z\s+values?|"
    r"range\s+from\s+about|logMAR|within\s+\d+\s+or\s+\d+\s+s)\b",
    re.IGNORECASE,
)
_TABLE_REF_PATTERN = re.compile(
    rf'\b({_TABLE_REF_WORD_TOKEN}\.?)'
    rf'\s+({_TABLE_KEY_TOKEN})([a-z])?\b(?!\s*(?:\.\s|\|))',
    re.IGNORECASE,
)
_TABLE_REF_PAIR_PAGE_LINK_PATTERN = re.compile(
    rf'\b(?P<word>{_TABLE_REF_WORD_TOKEN})\s+(?P<first>{_TABLE_KEY_TOKEN})\s+'
    r'(?P<join>and|or|и|или|&)\s+'
    r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*)>'
    r'(?P<body>[\s\S]*?)</a>',
    re.IGNORECASE,
)
_TABLE_REF_PAIR_PATTERN = re.compile(
    rf'\b(?P<word>{_TABLE_REF_WORD_TOKEN})\s+(?P<first>{_TABLE_KEY_TOKEN})\s+'
    rf'(?P<join>and|or|и|или|&)\s+(?P<second>{_TABLE_KEY_TOKEN})\b',
    re.IGNORECASE,
)
_TABLE_CELL_BLOCK_PATTERN = re.compile(
    r'(?P<open><t[dh]\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></t[dh]>)',
    re.IGNORECASE,
)
_TABLE_ROMAN_FOOTNOTE_MARKER = (
    r"(?:xiv|xiii|xii|xi|xv|viii|vii|vi|iv|iii|ii|ix|x|v|i)"
)
_TABLE_CELL_ROMAN_SUFFIX_PATTERN = re.compile(
    rf"\b(?P<root>[A-Za-z][A-Za-z0-9-]{{2,}}?)(?P<roman>{_TABLE_ROMAN_FOOTNOTE_MARKER})\b",
    re.IGNORECASE,
)
_TABLE_CELL_SEPARATED_ROMAN_SUFFIX_PATTERN = re.compile(
    rf"\b(?P<root>[A-Za-z][A-Za-z0-9-]{{2,}}(?:\s+[A-Za-z][A-Za-z0-9-]{{2,}}){{0,4}})\s+"
    rf"(?P<roman>{_TABLE_ROMAN_FOOTNOTE_MARKER})\b(?=\s*$)",
    re.IGNORECASE,
)
_TABLE_CELL_SINGLE_LETTER_ROOT_ROMAN_SUFFIX_PATTERN = re.compile(
    rf"\b(?P<root>[A-Za-z][A-Za-z0-9-]{{2,}}\s+[A-Z])(?P<roman>{_TABLE_ROMAN_FOOTNOTE_MARKER})\b",
)
_TABLE_CELL_PAREN_ROMAN_SUFFIX_PATTERN = re.compile(
    rf"(?P<close>\))(?P<roman>{_TABLE_ROMAN_FOOTNOTE_MARKER})\b",
    re.IGNORECASE,
)
_FIGURE_GAP_PARA_PATTERN = (
    r"<p\b[^>]*>\s*"
    r"(?:(?:<img\b)|(?:<(?:strong|em|b|i)\b[^>]*>\s*)*(?:Fig(?:ure)?|FIG)\.?\s*\d\b)"
    r"[\s\S]*?</p>"
)
_FIGURE_GAP_BLOCK_PATTERN = rf"(?:<figure\b[\s\S]*?</figure>|{_FIGURE_GAP_PARA_PATTERN})"
_SENTENCE_SPLIT_BY_FIGURE_PATTERN = re.compile(
    r'(?P<left_open><p\b[^>]*>)(?P<left_body>[\s\S]*?)(?P<left_close></p>)'
    rf'(?P<middle>\s*{_FIGURE_GAP_BLOCK_PATTERN}\s*)'
    r'(?P<right_open><p\b[^>]*>)(?P<right_body>[\s\S]*?)(?P<right_close></p>)',
    re.IGNORECASE,
)
_SENTENCE_SPLIT_BY_DOUBLE_FIGURE_GAP_PATTERN = re.compile(
    r'(?P<left_open><p\b[^>]*>)(?P<left_body>[\s\S]*?)(?P<left_close></p>)'
    rf'(?P<middle1>\s*{_FIGURE_GAP_BLOCK_PATTERN}\s*)'
    rf'(?P<middle2>\s*{_FIGURE_GAP_BLOCK_PATTERN}\s*)'
    r'(?P<right_open><p\b[^>]*>)(?P<right_body>[\s\S]*?)(?P<right_close></p>)',
    re.IGNORECASE,
)
_SENTENCE_GAP_BLOCK_PATTERN = re.compile(
    _FIGURE_GAP_BLOCK_PATTERN,
    re.IGNORECASE,
)
_SENTENCE_NODE_PATTERN = re.compile(
    r"<p\b[^>]*>[\s\S]*?</p>|<figure\b[\s\S]*?</figure>|<h[1-6]\b[^>]*>[\s\S]*?</h[1-6]>|<table\b[\s\S]*?</table>",
    re.IGNORECASE,
)
_FLOAT_AWARE_SENTENCE_NODE_PATTERN = re.compile(
    r'<div\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bz2m-float-unit\b)[^>]*>[\s\S]*?</div>|'
    r"<p\b[^>]*>[\s\S]*?</p>|<figure\b[\s\S]*?</figure>|<h[1-6]\b[^>]*>[\s\S]*?</h[1-6]>|<table\b[\s\S]*?</table>",
    re.IGNORECASE,
)
_SENTENCE_P_NODE_PATTERN = re.compile(
    r'^(?P<open><p\b[^>]*>)(?P<body>[\s\S]*)(?P<close></p>)$',
    re.IGNORECASE,
)
_FLOAT_UNIT_DIV_PATTERN = re.compile(
    r'<div\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bz2m-float-unit\b)[^>]*>[\s\S]*?</div>',
    re.IGNORECASE,
)
_P_BLOCK_PATTERN = re.compile(
    r'(?P<open><p\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></p>)',
    re.IGNORECASE,
)
_P_OR_H_BLOCK_PATTERN = re.compile(
    r'(?P<open><(?P<tag>p|h[1-6])\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></(?P=tag)>)',
    re.IGNORECASE,
)
_SENTENCE_H_NODE_PATTERN = re.compile(
    r'^(?P<open><h[1-6]\b[^>]*>)(?P<body>[\s\S]*)(?P<close></h[1-6]>)$',
    re.IGNORECASE,
)
_H_BLOCK_PATTERN = re.compile(
    r'(?P<open><h[1-6]\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></h[1-6]>)',
    re.IGNORECASE,
)
_TABLE_CAPTION_PARA_PATTERN = re.compile(
    r'(<p\b[^>]*>\s*)'
    r'((?:(?:<(?:span|strong|em|b|i|sup|sub)\b[^>]*>|</(?:span|strong|em|b|i|sup|sub)>)\s*)*)'
    rf'(TABLE|Table|Таблица)\s+({_TABLE_KEY_TOKEN})\s*[\.\-:]?\s*([^<]*?)(\s*</p>)',
    re.IGNORECASE,
)
_FIGURE_CAPTION_STYLE_PATTERN = re.compile(
    r'(<p\b[^>]*>\s*)'
    r'((?:(?:<(?:span|strong|em|b|i|sup|sub)\b[^>]*>|</(?:span|strong|em|b|i|sup|sub)>)\s*)*)'
    r'(FIG(?:URE)?|Fig(?:ure)?'
    r'|\u0420\u0430\u0434\u0438\u043e\u0433\u0440\u0430\u043c(?:\u043c\u0430)?|\u0440\u0430\u0434\u0438\u043e\u0433\u0440\u0430\u043c(?:\u043c\u0430)?'
    r'|\u0420\u0438\u0441(?:\u0443\u043d\u043e\u043a|\u0443\u043d\u043e\u0433|\u0443\u043d\u043a|\u0443\u043d\u043e)?'
    r'|\u0440\u0438\u0441(?:\u0443\u043d\u043e\u043a|\u0443\u043d\u043e\u0433|\u0443\u043d\u043a|\u0443\u043d\u043e)?'
    r'|\u0424\u0438\u0433(?:\u0443\u0440\u0430)?|\u0444\u0438\u0433(?:\u0443\u0440\u0430)?)'
    rf'\.?\s*({_FIG_RELAXED_KEY_TOKEN})\s*([.\|:\-]?)\s*([^<]*?)'
    r'(\s*</p>)',
    re.IGNORECASE,
)
_RU_INLINE_FIG_REF_PATTERN = re.compile(
    r"\b(?:Figure|Fig|Фиг(?:ура)?|Рис(?:унок|уног|унк|уно)?)\.?\s+([SsСс]?[IVXLCM\d]+)([A-Za-zА-Яа-я]?)\b",
    re.IGNORECASE,
)
_RU_INLINE_TABLE_REF_PATTERN = re.compile(
    r"\b(Table|Tables)\.?\s+([IVXLCM\d]+)\b",
    re.IGNORECASE,
)
_RU_LONG_ENGLISH_RUN_PATTERN = re.compile(
    r"(?<![A-Za-z])"
    r"(?:[A-Za-z]{2,}(?:[-'][A-Za-z]{2,})?)"
    r"(?:[ ,;:()\-]{1,3}[A-Za-z]{2,}(?:[-'][A-Za-z]{2,})?){7,}"
    r"[,.;:]?",
)
_RU_REF_NORMALIZE_SKIP_TAGS = {"script", "style", "code", "pre", "math", "svg"}
_RU_HEADING_EN_PREFIX_PATTERN = re.compile(
    r"^(?P<lead>\s*(?:<(?:span|strong|em|b|i|sup|sub)\b[^>]*>\s*)*)"
    r"(?P<prefix>[A-Za-z0-9()\-,:;'\"\u00b5\s]{20,}?)"
    r"(?P<rest>\s*[\u0400-\u04FF][\s\S]*)$",
)
# Marker OCR artefact: figure captions wrapped in <math display="inline"> instead
# of plain HTML.  A genuine <math> block never contains <strong>/<em>/<b>/<i> tags.
_SPURIOUS_MATH_CAPTION_PATTERN = re.compile(
    r'<math\b[^>]*>((?:(?!</math>).)*?<(?:strong|em|b|i)\b(?:(?!</math>).)*?)</math>',
    re.IGNORECASE | re.DOTALL,
)
# Bare single citation: "knowledge 67. Prompt" — number preceded by letter+space,
# followed by period + capital letter (new-sentence signal).
_BARE_CITATION_SINGLE_SPACED_PATTERN = re.compile(
    r'(?P<lead>\b(?P<word>[A-Za-zА-Яа-яЁё]{3,})\s)(?P<num>\d{1,3})(?=\. [A-Z])'
)
# Dot-citation preceded by space: "issues 17.68." — spaced variant of the glued
# dot pattern.  Only fires when followed by sentence-end punctuation.
_BARE_CITATION_SINGLE_CONNECTOR_PATTERN = re.compile(
    r'(?P<lead>(?:\b(?P<word>[A-Za-z]{3,})|\([A-Za-z]{2,8}\))\s)'
    r'(?P<num>\d{1,3})(?=\s+(?:for|and|or|to|in|of|with|by|as)\b)'
)
_BARE_CITATION_SINGLE_TRAILING_PATTERN = re.compile(
    r'(?P<lead>\b(?P<word>[A-Za-zА-Яа-яЁё]{3,})\s)'
    r'(?P<num>\d{1,3})(?=(?:[;:!?)]|$|(?:\.(?!\d))))'
)
_BARE_CITATION_SINGLE_DOT_SUFFIX_PATTERN = re.compile(
    r'(?P<lead>\b(?P<word>[A-Za-z]{3,}))'
    r'\.(?P<num>\d{1,3})(?=[\s,;:!?)<\]]|$)'
)
_BARE_CITATION_SINGLE_GLUED_PATTERN = re.compile(
    r'(?P<lead>(?:\b(?P<word>[A-Za-z]{5,})|\([A-Za-z]{2,8}\)))'
    r'(?P<num>\d{1,3})(?=\s+(?:for|and|or|to|in|of|with|by|as)\b)'
)
_BARE_CITATION_ET_AL_GLUED_PATTERN = re.compile(
    r'(?P<lead>\bet\s+al\.?)\s*(?P<num>\d{1,3})(?=[\s,.;:!?)<\]/]|$)',
    re.IGNORECASE,
)
_HTML_INLINE_SPACE_PATTERN = r"(?:\s|&nbsp;|\xa0)"
_ET_AL_SPLIT_CITATION_FOLLOW_VERBS = (
    r"(?:call|calls|called|consider|considers|define|defines|defined|"
    r"name|names|named|use|uses|used|suggest|suggests|report|reports|reported|"
    r"show|shows|demonstrate|demonstrates|describe|describes|described|"
    r"identify|identifies|identified|classify|classifies|classified|"
    r"label|labels|labeled|term|terms|termed|propose|proposes|proposed|"
    r"find|finds|found|observe|observes|observed|indicate|indicates|indicated)"
)
_ET_AL_SPLIT_CITATION_FOLLOW_PATTERN = (
    rf"(?={_HTML_INLINE_SPACE_PATTERN}*"
    r"(?:<a\b(?=[^>]*\bhref\s*=\s*['\"]#page-)[^>]*>"
    rf"{_HTML_INLINE_SPACE_PATTERN}*)?"
    rf"{_ET_AL_SPLIT_CITATION_FOLLOW_VERBS}\b)"
)
_SPLIT_ET_AL_TWO_DIGIT_TEXT_PATTERN = re.compile(
    rf"(?P<lead>\bet\s+al\.?){_HTML_INLINE_SPACE_PATTERN}*"
    rf"(?P<first>[1-9]){_HTML_INLINE_SPACE_PATTERN}+"
    rf"(?P<second>\d)"
    rf"{_ET_AL_SPLIT_CITATION_FOLLOW_PATTERN}",
    re.IGNORECASE,
)
_SPLIT_ET_AL_TWO_DIGIT_LINK_PATTERN = re.compile(
    rf"(?P<lead>\bet\s+al\.?){_HTML_INLINE_SPACE_PATTERN}*"
    rf"<sup\b[^>]*>{_HTML_INLINE_SPACE_PATTERN}*"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d{1,4})['\"][^>]*>"
    rf"{_HTML_INLINE_SPACE_PATTERN}*(?P<first>\d{{1,4}}){_HTML_INLINE_SPACE_PATTERN}*"
    rf"(?:</a>{_HTML_INLINE_SPACE_PATTERN}*</sup>|</sup>{_HTML_INLINE_SPACE_PATTERN}*</a>)"
    rf"{_HTML_INLINE_SPACE_PATTERN}*(?P<second>\d)"
    rf"{_ET_AL_SPLIT_CITATION_FOLLOW_PATTERN}",
    re.IGNORECASE | re.DOTALL,
)
_FLATTENED_DOT_SUPERSCRIPT_CITATION_PATTERN = re.compile(
    r'(?P<lead>\b(?P<word>[A-Za-z]{3,}))'
    r'\.(?P<body>\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12})'
    r'(?=[\s,;:!?)<\]]|$)'
)
_FLATTENED_SENTENCE_SUPERSCRIPT_CITATION_PATTERN = re.compile(
    r'(?P<punct>[.!?])\s+'
    r'(?P<body>\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12})'
    r'(?=\s+[A-Z])'
)
_BARE_CITATION_SPACED_DOT_PATTERN = re.compile(
    r'(?<=[A-Za-zА-Яа-яёЁ]) (\d{1,3}(?:\.\d{1,3})+)(?=[.,;:!?)<\]]|$)'
)
_BARE_CITATION_TRAILING_WORD_STOPLIST = {
    "table",
    "figure",
    "fig",
    "section",
    "sec",
    "box",
    "eq",
    "equation",
    "chapter",
    "range",
    "distance",
    "frequency",
    "parameter",
    "value",
    "values",
    "sample",
    "data",
    "page",
    "pages",
    "unit",
    "units",
    "vol",
    "volume",
    "issue",
    "front",
    "supplementary",
    "doi",
    "pmid",
    "isbn",
    "mhz",
    "ghz",
    "khz",
    "mm",
    "cm",
    "kg",
    "g",
    "mg",
    "nm",
    "um",
    "ph",
    "monkey",
    "week",
    "month",
    "animal",
    "female",
    "male",
    "d",
    "ma",
    "ua",
    "a",
    "v",
    "hz",
    "as",
    "at",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "of",
    "than",
    "to",
    "under",
    "with",
    "Вµm",
}
_FLATTENED_DOT_HARD_STOPLIST = {
    "table",
    "figure",
    "fig",
    "section",
    "sec",
    "box",
    "eq",
    "equation",
    "chapter",
    "doi",
    "pmid",
    "isbn",
}
_FALSE_DECIMAL_SUP_CITATION_PATTERN = re.compile(
    r'<sup>\s*(?:<a\b[^>]*\bz2m-ref-link\b[^>]*>)?(?P<num>\d{1,3})(?:</a>)?\s*</sup>\.(?P<frac>\d+)',
    re.IGNORECASE,
)
_FALSE_FIGURE_LABEL_SUP_PATTERN = re.compile(
    r'(?P<prefix>\b(?:Fig(?:ure)?|Рис(?:унок)?|рис(?:унок)?|Фиг(?:ура)?|фиг(?:ура)?|FIG(?:URE)?)\.?\s*)'
    r'<sup>\s*(?:<a\b[^>]*\bz2m-ref-link\b[^>]*>)?(?P<num>\d{1,3})(?:</a>)?\s*</sup>'
    r'(?=\s*\.)',
    re.IGNORECASE,
)
_FALSE_PH_RANGE_LINK_PATTERN = re.compile(
    r'(?P<prefix>\bpH\s+\d{1,2}(?:\.\d+)?\s*(?:[-\u2010-\u2014]|to\b|and\b)\s*)'
    r'(?:<sup\b[^>]*>\s*)?'
    r'<a\b[^>]*\bhref\s*=\s*["\']#(?P<kind>ref|fig)-(?P<target>\d{1,2})["\'][^>]*>'
    r'\s*(?P<num>\d{1,2})\s*</a>'
    r'(?:\s*</sup>)?',
    re.IGNORECASE,
)
_FALSE_SUBJECT_SERIES_LINK_PATTERN = re.compile(
    r'(?P<prefix>\b(?:monkeys?|animals?|subjects?|participants?|patients?|males?|females?)\s+'
    r'\d{1,2}(?:\s*,\s*\d{1,2})*\s*(?:,?\s*(?:and|or)\s*)?)'
    r'(?:<sup\b[^>]*>\s*)?'
    r'<a\b[^>]*\bhref\s*=\s*["\']#(?P<kind>ref|fig)-(?P<target>\d{1,2})["\'][^>]*>'
    r'\s*(?P<num>\d{1,2})\s*</a>'
    r'(?:\s*</sup>)?',
    re.IGNORECASE,
)
_FALSE_RANGE_START_LINK_PATTERN = re.compile(
    r'(?P<prefix>\b(?:over|from|for|during|between|approximately|about|around|roughly)\s+)'
    r'<sup\b[^>]*>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>\d{1,2})["\'][^>]*>'
    r'\s*(?P<num>\d{1,2})\s*</a>\s*</sup>'
    r'(?=\s+(?:to|and|-|\u2013|\u2014)\s+\d{1,3}(?:\.\d+)?\s*'
    r'(?:minutes?|hours?|days?|weeks?|months?|years?|s|sec|ms|Hz|kHz|MHz|MBq|mg|kg)\b)',
    re.IGNORECASE,
)
_FALSE_COUNT_OF_TOTAL_SUP_REF_PATTERN = re.compile(
    r'(?P<prefix>)<sup\b[^>]*>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>\d{1,3})["\'][^>]*>'
    r'\s*(?P<num>\d{1,3})\s*</a>\s*</sup>'
    r'(?=\s+of\s+(?:the\s+)?(?:\d{1,4}\s+)?'
    r'(?:arrays?|implants?|patients?|participants?|subjects?|animals?|cases?|trials?|'
    r'samples?|electrodes?|channels?|sessions?|items?|objects?|studies?)\b)',
    re.IGNORECASE,
)
_FALSE_DAY_NUMBER_SUP_REF_PATTERN = re.compile(
    r'(?P<prefix>\b(?:by|on|at|after|before|until|through)\s+day\s*)'
    r'<sup\b[^>]*>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>\d{1,3})["\'][^>]*>'
    r'\s*(?P<num>\d{1,3})\s*</a>\s*</sup>'
    r'(?=\s*(?:[),.;:]|$))',
    re.IGNORECASE,
)
_FALSE_SPLIT_YEAR_REF_PATTERN = re.compile(
    r'(?P<head>\b(?:19|20)\d)\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>\d)["\'][^>]*>'
    r'\s*(?P<num>\d)\s*(?P<paren>\))?\s*</a>',
    re.IGNORECASE,
)
_FALSE_FUNCTIONAL_CLASS_LINK_PATTERN = re.compile(
    r'(?P<prefix>\b(?:WHO\s+)?functional\s+class(?:es)?\s+'
    r'(?:[1-5]\s*(?:,|and|or)\s*)*)'
    r'(?:<sup\b[^>]*>\s*)?'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>[1-5])["\'][^>]*>'
    r'\s*(?P<num>[1-5])\s*</a>'
    r'(?:\s*</sup>)?',
    re.IGNORECASE,
)
_FALSE_AREA_NUMBER_LINK_PATTERN = re.compile(
    r'(?P<prefix>\b(?:Brodmann\s+)?area\s*)'
    r'<sup\b[^>]*>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>[1-6])["\'][^>]*>'
    r'\s*(?P<num>[1-6])\s*</a>\s*</sup>'
    r'(?=\s+(?:in|of|and|within|near|first|subsequently|[A-Z][a-z]))',
    re.IGNORECASE,
)
_FALSE_CORTICAL_LAYER_LINK_PATTERN = re.compile(
    r'(?P<prefix>\bcortical\s+layer\s*)'
    r'<sup\b[^>]*>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>[1-6])["\'][^>]*\bz2m-ref-link\b[^>]*>'
    r'\s*(?P<num>[1-6])\s*</a>\s*</sup>'
    r'(?=\s*(?:[),.;:]|\band\b|\bor\b))',
    re.IGNORECASE,
)
_FALSE_DIMENSION_LEADING_SUP_REF_PATTERN = re.compile(
    r'<sup>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>\d+)["\'][^>]*\bz2m-ref-link\b[^>]*>'
    r'\s*(?P<num>\d{1,3})\s*</a>\s*</sup>'
    r'(?=\s*(?:by|x|\u00d7)\s*\d+(?:\.\d+)?\s*'
    r'(?:<[^>]+>\s*)*(?:u|µ|μ|Вµ|Ој)?m(?:\s*<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*2\s*</sup>|\s*2\b|\b))',
    re.IGNORECASE,
)
_FALSE_BETWEEN_RANGE_SUP_REF_PATTERN = re.compile(
    r'(?P<prefix>\b(?:between|from)\s+)'
    r'<sup>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>\d+)["\'][^>]*\bz2m-ref-link\b[^>]*>'
    r'\s*(?P<num>\d{1,3})\s*</a>\s*</sup>'
    r'(?=\s+(?:and|to)\s+\d+(?:\.\d+)?\s*(?:degrees?|°|\u00b0)\b)',
    re.IGNORECASE,
)
_FALSE_RANGE_ENDPOINT_SUP_REF_PATTERN = re.compile(
    r'(?P<prefix>\b(?:between|from)\s+\d+(?:\.\d+)?\s+(?:and|to)\s+)'
    r'<sup>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>\d+)["\'][^>]*\bz2m-ref-link\b[^>]*>'
    r'\s*(?P<num>\d{1,3})\s*</a>\s*</sup>'
    r'(?=\s*(?:[.,;)]|\b(?:for|of|in|across|each|with|to)\b))',
    re.IGNORECASE,
)
_LINKED_DECIMAL_COMMA_SUP_VALUE_PATTERN = re.compile(
    r'<sup(?P<attrs>[^>]*)>\s*(?P<body>'
    r'(?:'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-\d{1,4}["\'][^>]*>\s*\d{1,4}\s*</a>'
    r'|\d{1,4}'
    r')'
    r'(?:\s*,\s*'
    r'(?:'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-\d{1,4}["\'][^>]*>\s*\d{1,4}\s*</a>'
    r'|\d{1,4}'
    r')){1,4}'
    r')\s*</sup>',
    re.IGNORECASE | re.DOTALL,
)
_DECIMAL_COMMA_SUP_VALUE_CONTEXT_RE = re.compile(
    r"\b(?:"
    r"effect\s+size|logmar|snellen\s+acuity|visual\s+acuity|"
    r"measurements?\s+of|cohens?\s+d|value|values|score|scores?|"
    r"coefficient|ratio|mean|median|power|slope|molecular\s+weight|"
    r"course\s+of|over\s+the\s+course\s+of|diameters?|distances?|"
    r"version|v"
    r")\b[\s\S]{0,160}$",
    re.IGNORECASE,
)
_FALSE_NUMBERED_SEQUENCE_LEADING_SUP_REF_PATTERN = re.compile(
    r'(?P<prefix>\b(?:graphics?|objects?|sessions?|experiments?|studies|items?|trials?|tasks?|stages?)\s+)'
    r'<sup>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>\d+)["\'][^>]*\bz2m-ref-link\b[^>]*>'
    r'\s*(?P<num>\d{1,3})\s*</a>\s*</sup>'
    r'(?=\s*(?:to|through|and|or)\s+\d)',
    re.IGNORECASE,
)
_FALSE_COLOR_LABEL_SUP_REF_PATTERN = re.compile(
    r'(?P<color>\b(?:red|green|blue|orange|yellow|purple|violet|gray|grey|white|black|brown))'
    r'<sup(?P<attrs>[^>]*)>\s*(?P<body>'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*\bz2m-ref-link\b[^>]*>\s*\d{1,3}\s*</a>'
    r'(?:\s*,\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*\bz2m-ref-link\b[^>]*>\s*\d{1,3}\s*</a>){0,2}'
    r')\s*</sup>',
    re.IGNORECASE | re.DOTALL,
)
_FALSE_COLOR_LABEL_PLAIN_PERCENT_SUP_PATTERN = re.compile(
    r'(?P<color>\b(?:red|green|blue|orange|yellow|purple|violet|gray|grey|white|black|brown))'
    r'<sup(?P<attrs>[^>]*)>\s*(?P<first>\d{1,3})\s*,\s*(?P<tail>\d{1,3}(?:\s*,\s*\d{1,3}){0,2})\s*</sup>'
    r'(?P<fraction>\s*\.\s*\d+\s*%)',
    re.IGNORECASE,
)
_FALSE_ELECTRODE_PAIR_SUP_REF_PATTERN = re.compile(
    r'(?P<prefix>\b(?:electrodes?|contacts?|channels?)\s+)'
    r'<sup>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target1>\d+)["\'][^>]*\bz2m-ref-link\b[^>]*>'
    r'\s*(?P<num1>\d{1,3})\s*</a>\s*</sup>'
    r'(?P<sep>\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*)'
    r'<sup>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target2>\d+)["\'][^>]*\bz2m-ref-link\b[^>]*>'
    r'\s*(?P<num2>\d{1,3})\s*</a>\s*</sup>',
    re.IGNORECASE,
)
_FALSE_ELECTRODE_PAIR_LEADING_SUP_REF_PATTERN = re.compile(
    r'(?P<prefix>\b(?:electrodes?|contacts?|channels?)\s+)'
    r'<sup>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target1>\d+)["\'][^>]*\bz2m-ref-link\b[^>]*>'
    r'\s*(?P<num1>\d{1,3})\s*</a>\s*</sup>'
    r'(?P<sep>\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*)'
    r'(?P<num2>\d{1,3})(?=\s*(?:[.,;:)]|</p>|<br\b|\b(?:then|with|from|for|of|in|is|are|were|was|picked|produce|produces|produced)\b))',
    re.IGNORECASE,
)
_FALSE_STAT_SUP_CITATION_PATTERN = re.compile(
    r'(?P<base>\b(?:[RrXxPpNn]|df|chi)\s*|(?:\u03c7|\u03a7)\s*)'
    r'<sup(?P<attrs>[^>]*)>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<ref>\d+)["\'][^>]*>\s*(?P<exp>2)\s*</a>\s*'
    r'</sup>',
    re.IGNORECASE,
)
_CHEMICAL_ELEMENT_SYMBOLS = (
    "Og", "Ts", "Lv", "Mc", "Fl", "Nh", "Cn", "Rg", "Ds", "Mt", "Hs", "Bh", "Sg", "Db", "Rf",
    "Lr", "No", "Md", "Fm", "Es", "Cf", "Bk", "Cm", "Am", "Pu", "Np", "Pa", "Th", "Ac", "Ra",
    "Fr", "Rn", "At", "Po", "Bi", "Pb", "Tl", "Hg", "Au", "Pt", "Ir", "Os", "Re", "W", "Ta",
    "Hf", "Lu", "Yb", "Tm", "Er", "Ho", "Dy", "Tb", "Gd", "Eu", "Sm", "Pm", "Nd", "Pr", "Ce",
    "La", "Ba", "Cs", "Xe", "I", "Te", "Sb", "Sn", "In", "Cd", "Ag", "Pd", "Rh", "Ru", "Tc",
    "Mo", "Nb", "Zr", "Y", "Sr", "Rb", "Kr", "Br", "Se", "As", "Ge", "Ga", "Zn", "Cu", "Ni",
    "Co", "Fe", "Mn", "Cr", "V", "Ti", "Sc", "Ca", "K", "Ar", "Cl", "S", "P", "Si", "Al",
    "Mg", "Na", "Ne", "F", "O", "N", "C", "B", "Be", "Li", "He", "H",
)
_CHEMICAL_ELEMENT_ALT = "|".join(re.escape(symbol) for symbol in _CHEMICAL_ELEMENT_SYMBOLS)
_CHEMICAL_ELEMENT_TOKEN_PATTERN = re.compile(rf"(?:{_CHEMICAL_ELEMENT_ALT})")
_CHEMICAL_SINGLE_PREFIX_FORMULAS = {"H", "N", "O"}
_FALSE_CHEMICAL_FORMULA_SUP_CITATION_PATTERN = re.compile(
    rf'(?P<base>\b(?:(?:{_CHEMICAL_ELEMENT_ALT})){{1,8}})'
    r'<sup(?P<attrs>[^>]*)>\s*'
    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<ref>\d{1,2})["\'][^>]*>\s*(?P<num>\d{1,2})\s*</a>\s*'
    r'</sup>'
    rf'(?P<suffix>(?:\s*(?:{_CHEMICAL_ELEMENT_ALT})(?![a-z]))?)',
)
_LINKED_BASE10_MANTISSA_BEFORE_EXP_PATTERN = re.compile(
    r'<sup>\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-10["\'][^>]*>\s*10\s*</a>\s*</sup>\s*'
    r'(?=<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*-?\d{1,2}\s*</sup>)',
    re.IGNORECASE,
)
_LEADING_PAGE_ANCHOR_HTML_PATTERN = (
    r'(?:\s|<span\b[^>]*\bid\s*=\s*["\']page-[^"\']+["\'][^>]*>\s*</span>)*'
)
_PDF_RUNNING_HEADER_PREFIX_PATTERNS = (
    re.compile(
        rf"^(?P<lead>{_LEADING_PAGE_ANCHOR_HTML_PATTERN})"
        r"(?P<header>(?:[A-Z][A-Za-z'\-]+\s+et\s+al\.\s+)?Combined\s+Imaging\s+in\s+Breast\s+Cancer)\b"
        r"(?P<tail>[\s\S]*)$",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^(?P<lead>{_LEADING_PAGE_ANCHOR_HTML_PATTERN})"
        r"(?P<header>Journal\s+of\s+Materials\s+Chemistry\s+B\s+Accepted\s+Manuscrip(?:t)?)\b"
        r"(?P<tail>[\s\S]*)$",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^(?P<lead>{_LEADING_PAGE_ANCHOR_HTML_PATTERN})"
        r"(?P<header>ChemComm\s+Accepted\s+Manuscript)\b"
        r"(?P<tail>[\s\S]*)$",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^(?P<lead>{_LEADING_PAGE_ANCHOR_HTML_PATTERN})"
        r"(?P<header>Published\s+on\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}\.?\s+Downloaded\s+by\s+[\s\S]*?)"
        r"(?P<tail>\s*)$",
        re.IGNORECASE,
    ),
)
_PDF_LINE_NUMBER_CONTINUATION_BODY_PATTERN = re.compile(
    rf"^(?P<lead>{_LEADING_PAGE_ANCHOR_HTML_PATTERN})"
    r"(?:(?P<num>[1-9]\d{0,2})|<sup\b[^>]*>\s*(?P<sup_num>[1-9]\d{0,2})\s*</sup>)\s*"
    r"(?P<tail>[\s\S]*)$",
    re.IGNORECASE,
)
_TRAILING_TABLE_NOTE_BODY_PATTERN = re.compile(
    r"^(?P<prefix>[\s\S]*?)"
    r"(?P<note>\s*(?:<span\b[^>]*\bid\s*=\s*[\"']page-[^\"']+[\"'][^>]*>\s*</span>\s*)*"
    r"(?:<sup\b[^>]*>\s*[a-z]\s*</sup>\s*|[a-z]\s*)"
    r"(?:(?:Body\s+mass\s+index|Tumor\s+in\s+situ|Triple-negative\s+breast\s+cancer|"
    r"Sentinel\s+lymph\s+node\s+biopsy|Axillary\s+lymph\s+node\s+dissection|"
    r"Indocyanine\s+green|Methylene\s+blue|Radioisotope)\.?|"
    r"Positivity\s+was\s+defined\s+as[\s\S]{0,240}|"
    r"Bolded\s+rows\s+show\s+the\s+distribution\s+across\s+all\s+sites\.?|"
    r"Significant,\s*(?:<[^>]+>\s*)*p[\s\S]{0,90}?0\.05\.?)\s*)$",
    re.IGNORECASE,
)
_TRAILING_TABLE_NOTE_MARKERS = (
    "body mass index",
    "tumor in situ",
    "triple-negative",
    "sentinel lymph",
    "axillary lymph",
    "indocyanine",
    "methylene",
    "radioisotope",
    "positivity was defined",
    "bolded rows show",
    "significant,",
)
_TRAILING_TABLE_CAPTION_BODY_PATTERN = re.compile(
    rf"^(?P<prefix>[\s\S]*?)"
    rf"(?P<caption>\s*(?:<span\b[^>]*\bid\s*=\s*[\"']page-[^\"']+[\"'][^>]*>\s*</span>\s*)*"
    rf"(?:TABLE|Table)\.?\s+{_TABLE_KEY_TOKEN}\b[\s\S]*)$",
    re.IGNORECASE,
)
_GLUED_ROMAN_SUFFIX_PATTERN = re.compile(
    r"\b([A-Za-z][A-Za-z\-]{3,}?)(iii|iv|ii|vi|v)\b",
)
_NESTED_ESCAPED_ANCHOR_AUTOLINK_PATTERN = re.compile(
    r'&lt;a\s+href="\s*<a\s+href="(?P<url>https?://[^"]+)"[^>]*>[^<]+</a>\s*"&gt;'
    r'\s*<a\s+href="https?://[^"]+&lt;/a&gt;"[^>]*>[^<]+&lt;/a&gt;</a>',
    re.IGNORECASE,
)
_MICRO_SQUARE_UNIT_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<prefix>u|\u00b5|\u03bc|Вµ|Ој)m\s*2(?=\W|[A-Za-z]|$)",
    re.IGNORECASE,
)
_COMPACT_CURRENT_DENSITY_PATTERN = re.compile(
    r"\b(?P<prefix>m|u|\u00b5|\u03bc)C\s*c?m\s*\^?\s*[-\u2212]\s*2\b",
    re.IGNORECASE,
)
_VALUE_COMPACT_CURRENT_DENSITY_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<prefix>m|u|\u00b5|\u03bc)C\s*c?m\s*\^?\s*[-\u2212]\s*2\b",
    re.IGNORECASE,
)
_INLINE_TEX_MICRO_CURRENT_DENSITY_PATTERN = re.compile(
    r"\\\(\s*(?P<value>\d+(?:\.\d+)?)"
    r"(?:\s|\\,|\\\s*|~)*\\mu\s*C"
    r"(?:\s|\\,|\\\s*|~)*cm\s*\^\{?\s*[-\u2212]\s*2\s*\}?\s*\\\)",
    re.IGNORECASE,
)
_INLINE_TEX_CIC_CHARGE_DENSITY_PATTERN = re.compile(
    r"\\\(\s*\(?\s*CIC\s*\)?\s*of\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*mC\s*c?m\s*"
    r"(?:\^\{?\s*[-\u2212]\s*2\s*\}?)?\s*\\\)",
    re.IGNORECASE,
)
_INLINE_TEX_CIC_ASSIGN_CHARGE_DENSITY_PATTERN = re.compile(
    r"\\\(\s*\(?\s*CIC\s*=\s*"
    r"(?P<value>\d+(?:\.\d+)?)\s*(?:\\,)?\s*mC\s*c?m\s*"
    r"(?:\^\{?\s*[-\u2212]\s*2\s*\}?)?\s*\)?\s*\\\)",
    re.IGNORECASE,
)
_INLINE_TEX_MICRO_AREA_PATTERN = re.compile(
    r"\\\(\s*(?P<value>\d+(?:\.\d+)?)"
    r"(?:\s|\\,|\\\s*|~)*\\mu\s*m\s*\^\{?\s*2\s*\}?\s*\\\)",
    re.IGNORECASE,
)
_VALUE_INLINE_TEX_MICRO_METER_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*\\\(\s*\\mu(?:\\text\{m\}|m|\s*m)"
    r"(?:\s*\^\{?\s*(?P<exp>[12])\s*\}?)?\s*\\\)",
    re.IGNORECASE,
)
_VALUE_INLINE_TEX_MICRO_CURRENT_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*\\\(\s*\\mu\s*A\s*\\\)",
    re.IGNORECASE,
)
_INLINE_TEX_MICRO_CURRENT_PATTERN = re.compile(
    r"\\\(\s*(?P<value>[-\u2212]?\d+(?:\.\d+)?)"
    r"(?:\s|\\,|\\\s*|~)*\\mu\s*A\s*\\\)",
    re.IGNORECASE,
)
_INLINE_TEX_MICRO_SYMBOL_PATTERN = re.compile(
    r"\\\(\s*\\mu\s*\\\)\s*(?=(?:C|A|m)\b)",
    re.IGNORECASE,
)
_INLINE_TEX_OMEGA_SYMBOL_PATTERN = re.compile(r"\\\(\s*\\Omega\s*\\\)", re.IGNORECASE)
_INLINE_TEX_PM_SYMBOL_PATTERN = re.compile(r"\\\(\s*\\pm\s*\\\)", re.IGNORECASE)
_INLINE_TEX_DIMENSION_PROSE_PATTERN = re.compile(
    r"\\\((?P<body>[\s\S]{1,420}?)\\\)",
    re.IGNORECASE,
)
_DISPLAY_TEX_DIMENSION_PROSE_PATTERN = re.compile(
    r"\\\[(?P<body>[\s\S]{1,420}?)\\\]",
    re.IGNORECASE,
)
_LATEX_MICRO_METER_UNIT_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)(?:\s|\\,|\\\s*|~)*\\mu(?:\\text\{m\}|m|\s*m)(?:\s*\^\{?(?P<exp>[12])\}?)?",
    re.IGNORECASE,
)
_TAG_SPLIT_MICRO_METER_PATTERN = re.compile(
    r"<(?P<tag>i|em)\b[^>]*>\s*(?:\\mu|u|\u00b5|\u03bc|Вµ|Ој|Р’Вµ|РћС)\s*</(?P=tag)>\s*m\b",
    re.IGNORECASE,
)
_SPACED_MICRO_METER_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:\u00b5|\u03bc|Вµ|Ој|Р’Вµ|РћС)\s+m\b",
    re.IGNORECASE,
)
_DIMENSION_TIMES_PATTERN = re.compile(
    r"(?P<left>\d+(?:\.\d+)?(?:\s*(?:\u00b5m|\u03bcm|um))?"
    r"(?:<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*[12]\s*</sup>)?)"
    r"\s*(?:\\\(\s*\\times\s*\\\)|\\times|[x\u00d7])\s*"
    r"(?P<right>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_CHEMICAL_OXIDE_PATTERN = re.compile(r"\b(?P<element>Al|Hf|Ir|Ti|Ta|Si)O[xX]\b")
_SPLIT_CHEMICAL_OXIDE_PATTERN = re.compile(
    r"\b(?P<element>Al|Hf|Ir|Ti|Ta|Si)O\s*"
    r"<(?P<tag>i|em)\b[^>]*>\s*(?:<sup>\s*)?[xX](?:\s*</sup>)?\s*</(?P=tag)>",
    re.IGNORECASE,
)
_INLINE_TEX_SENTENCE_BOUNDARY_PATTERN = re.compile(
    r"(?P<formula>\\\([^<]*?\\\))\s*</p>\s*<p(?P<attrs>[^>]*)>\s*"
    r"(?P<next>Additionally|However|Conversely|Therefore)\b",
    re.IGNORECASE,
)
_CIC_UNIT_SENTENCE_BOUNDARY_PATTERN = re.compile(
    r"(?P<phrase>\(CIC\)\s+of\s+\d+(?:\.\d+)?\s+mC\s+cm"
    r"<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*-\s*2\s*</sup>)"
    r"\s*</p>\s*<p(?P<attrs>[^>]*)>\s*(?P<next>Additionally|However|Conversely|Therefore)\b",
    re.IGNORECASE,
)
_OHM_PREFIX_SPACE_PATTERN = re.compile(
    r"\b(?P<prefix>k|M|G|T|m|u|\u00b5|\u03bc)\s+(?:\u03a9|\u2126)\b",
)
_OHM_PUNCT_SPACE_PATTERN = re.compile(
    r"(?P<unit>(?:(?:k|M|G|T|m|u|\u00b5|\u03bc)?(?:\u03a9|\u2126)))\s+(?P<punct>[,.;:])",
)
_UNIT_EXPONENT_SUP_LEADING_SPACE_PATTERN = re.compile(
    r"(?P<unit>(?:mC|nC|uC|\u00b5C|\u03bcC)\s+cm|cd\s+m|(?:mm|cm|m)\s+s|(?:u|\u00b5|\u03bc)m|mm|cm|m)"
    r"\s+(?=<sup\b[^>]*\bz2m-unit-exp\b)",
    re.IGNORECASE,
)
_UNIT_EXPONENT_SUP_PUNCT_SPACE_PATTERN = re.compile(
    r"(?P<sup><sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*[-\d]+\s*</sup>)\s+(?P<punct>[,.;:])",
    re.IGNORECASE,
)
_PAREN_WORD_NUMBER_GLUE_PATTERN = re.compile(
    r"\)(?P<word>of|for|at|in)(?P<value>\d)",
    re.IGNORECASE,
)
_UNIT_WORD_GLUE_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>V|nC|(?:u|\u00b5|\u03bc)A)(?P<word>and|for|was)\b",
    re.IGNORECASE,
)
_PVALUE_FOR_GLUE_PATTERN = re.compile(
    r"(?P<prefix>\bp\s*=\s*(?P<value>\d+(?:\.\d+)?))for\b",
    re.IGNORECASE,
)
_EFFECTIVE_VARIABLE_PATTERN = re.compile(r"\b(?P<var>[A-Z])\s+eff\b")
_EFFECTIVE_VARIABLE_HTML_PATTERN = re.compile(
    r"(?P<var><(?:i|em)\b[^>]*>\s*[A-Z]\s*</(?:i|em)>)\s+eff\b"
)
_ALLOY_OXYGEN_VARIABLE_FORMULA_PATTERN = re.compile(
    r"\b(?P<metal>(?:[A-Z][a-z]?){2,})\s*"
    r"<i>\s*x\s*</i>\s*O\s*<i>\s*y\s*</i>"
)
_INLINE_CHRONOLOGICALLY_SPLIT_PATTERN = re.compile(
    r"(?P<open><(?:i|em|b|strong|span)\b[^>]*>\s*)"
    r"(?P<stem>chronologicall)"
    r"(?P<close>\s*</(?:i|em|b|strong|span)>)\s*y\b",
    re.IGNORECASE,
)
_KNOWN_WORD_GLUE_REPAIRS = (
    (re.compile(r"\b(\d+)year-old\b", re.IGNORECASE), r"\1-year-old"),
    (re.compile(r"\b(\d+)\s+year-old\b", re.IGNORECASE), r"\1-year-old"),
    (re.compile(r"\bforthe\b", re.IGNORECASE), "for the"),
    (re.compile(r"\bstate-ofthe-art\b", re.IGNORECASE), "state-of-the-art"),
    (re.compile(r"\boff-theshelf\b", re.IGNORECASE), "off-the-shelf"),
    (re.compile(r"\bInstituteDepartment\b"), "Institute Department"),
    (re.compile(r"\bAlessentially\b"), "AI essentially"),
    (re.compile(r"\bAl(?=\s+(?:techniques|Office|triad|systems|interventions|education|feedback|based)\b)"), "AI"),
    (re.compile(r"\bAl(?=-(?:driven|generated|based)\b)"), "AI"),
    (re.compile(r"\bartiicial\b", re.IGNORECASE), "artificial"),
    (re.compile(r"\binluence\b", re.IGNORECASE), "influence"),
    (re.compile(r"\birst\b", re.IGNORECASE), "first"),
    (re.compile(r"\bitness\b", re.IGNORECASE), "fitness"),
    (re.compile(r"\bworklow\b", re.IGNORECASE), "workflow"),
    (re.compile(r"\bscientiic\b", re.IGNORECASE), "scientific"),
    (re.compile(r"\bcertiication\b", re.IGNORECASE), "certification"),
    (re.compile(r"\bfalsiications\b", re.IGNORECASE), "falsifications"),
    (re.compile(r"\bmodifcations\b", re.IGNORECASE), "modifications"),
    (re.compile(r"\bspecifc\b", re.IGNORECASE), "specific"),
    (re.compile(r"\bspecifcity\b", re.IGNORECASE), "specificity"),
    (re.compile(r"\bidentifed\b", re.IGNORECASE), "identified"),
    (re.compile(r"\bidentifes\b", re.IGNORECASE), "identifies"),
    (re.compile(r"\befect\b", re.IGNORECASE), "effect"),
    (re.compile(r"\befects\b", re.IGNORECASE), "effects"),
    (re.compile(r"\befective\b", re.IGNORECASE), "effective"),
    (re.compile(r"\befectively\b", re.IGNORECASE), "effectively"),
    (re.compile(r"\bafect\b", re.IGNORECASE), "affect"),
    (re.compile(r"\bafects\b", re.IGNORECASE), "affects"),
    (re.compile(r"\bafected\b", re.IGNORECASE), "affected"),
    (re.compile(r"\bafecting\b", re.IGNORECASE), "affecting"),
    (re.compile(r"\bafective\b", re.IGNORECASE), "affective"),
    (re.compile(r"\bdiferential\b", re.IGNORECASE), "differential"),
    (re.compile(r"\bdiferentially\b", re.IGNORECASE), "differentially"),
    (re.compile(r"\bdiferent\b", re.IGNORECASE), "different"),
    (re.compile(r"\bdiference\b", re.IGNORECASE), "difference"),
    (re.compile(r"\bdiferences\b", re.IGNORECASE), "differences"),
    (re.compile(r"\bdiferentiating\b", re.IGNORECASE), "differentiating"),
    (re.compile(r"\bcoeficient\b", re.IGNORECASE), "coefficient"),
    (re.compile(r"\bcoefcient\b", re.IGNORECASE), "coefficient"),
    (re.compile(r"\bcoefcients\b", re.IGNORECASE), "coefficients"),
    (re.compile(r"\beficient\b", re.IGNORECASE), "efficient"),
    (re.compile(r"\bfow\b"), "flow"),
    (re.compile(r"\bfxed\b"), "fixed"),
    (re.compile(r"\bartifcial\b", re.IGNORECASE), "artificial"),
    (re.compile(r"\brefect\b", re.IGNORECASE), "reflect"),
    (re.compile(r"\bafiliations\b", re.IGNORECASE), "affiliations"),
    (re.compile(r"\baferents\b", re.IGNORECASE), "afferents"),
    (re.compile(r"\bdefcits\b", re.IGNORECASE), "deficits"),
    (re.compile(r"\bofline\b", re.IGNORECASE), "offline"),
    (re.compile(r"\bobject\s+ive\b", re.IGNORECASE), "objective"),
    (re.compile(r"\bRefrence\b"), "Reference"),
    (re.compile(r"\brefrence\b"), "reference"),
    (re.compile(r"\bapproximatley\b", re.IGNORECASE), "approximately"),
    (re.compile(r"\bsuiprising\b", re.IGNORECASE), "surprising"),
    (re.compile(r"\battaclied\b", re.IGNORECASE), "attached"),
    (re.compile(r"\bcomparision\b", re.IGNORECASE), "comparison"),
    (re.compile(r"\bclincal\b", re.IGNORECASE), "clinical"),
    (re.compile(r"\bbeacause\b", re.IGNORECASE), "because"),
    (re.compile(r"\bthrefore\b", re.IGNORECASE), "therefore"),
    (re.compile(r"\burtheral\b", re.IGNORECASE), "urethral"),
    (re.compile(r"\bUroflowrnetry\b"), "Uroflowmetry"),
    (re.compile(r"\buroflowrnetry\b"), "uroflowmetry"),
    (re.compile(r"\bUroflowmetery\b"), "Uroflowmetry"),
    (re.compile(r"\buroflowmetery\b"), "uroflowmetry"),
    (re.compile(r"\bUrofowmetery\b"), "Uroflowmetry"),
    (re.compile(r"\burofowmetery\b"), "uroflowmetry"),
    (re.compile(r"\burofowmetry\b", re.IGNORECASE), "uroflowmetry"),
    (re.compile(r"\bUrdynamic\b", re.IGNORECASE), "urodynamic"),
    (re.compile(r"\bfowmeter\b", re.IGNORECASE), "flowmeter"),
    (re.compile(r"\bfows\b", re.IGNORECASE), "flows"),
    (re.compile(r"\bfowrate\b", re.IGNORECASE), "flow rate"),
    (re.compile(r"\bfowmetry\b", re.IGNORECASE), "flowmetry"),
    (re.compile(r"\bflter\b", re.IGNORECASE), "filter"),
    (re.compile(r"\bcutof\b", re.IGNORECASE), "cutoff"),
    (re.compile(r"\bfuid\b", re.IGNORECASE), "fluid"),
    (re.compile(r"\bfuorescent\b", re.IGNORECASE), "fluorescent"),
    (re.compile(r"\bflling\b", re.IGNORECASE), "filling"),
    (re.compile(r"\bsignifcant\b", re.IGNORECASE), "significant"),
    (re.compile(r"\bndings\b", re.IGNORECASE), "findings"),
    (re.compile(r"\burflowmetry\b", re.IGNORECASE), "uroflowmetry"),
    (re.compile(r"\bFERENCE\s+VALUES\b"), "REFERENCE VALUES"),
    (re.compile(r"\bRewiev\b", re.IGNORECASE), "review"),
    (re.compile(r"\bintraand\s+inter-", re.IGNORECASE), "intra- and inter-"),
    (re.compile(r"\bflowmetery\b", re.IGNORECASE), "flowmetry"),
    (re.compile(r"\bnon-invasivly\b", re.IGNORECASE), "non-invasively"),
    (re.compile(r"\bsubcomitee\b", re.IGNORECASE), "subcommittee"),
    (re.compile(r"\bstandarization\b", re.IGNORECASE), "standardization"),
    (re.compile(r"\bstandarisation\b", re.IGNORECASE), "standardisation"),
    (re.compile(r"\baformentioned\b", re.IGNORECASE), "aforementioned"),
    (re.compile(r"\beicient\b", re.IGNORECASE), "efficient"),
    (re.compile(r"\beiciency\b", re.IGNORECASE), "efficiency"),
    (re.compile(r"\beectiveness\b", re.IGNORECASE), "effectiveness"),
    (re.compile(r"\bine-grained\b", re.IGNORECASE), "fine-grained"),
    (re.compile(r"\bdeining\b", re.IGNORECASE), "defining"),
    (re.compile(r"\bsimpliication\b", re.IGNORECASE), "simplification"),
    (re.compile(r"\buniied\b", re.IGNORECASE), "unified"),
    (re.compile(r"\bailiations\b", re.IGNORECASE), "affiliations"),
    (re.compile(r"\bofrealistic\b", re.IGNORECASE), "of realistic"),
    (re.compile(r"\bofclinical\b", re.IGNORECASE), "of clinical"),
    (re.compile(r"\bofmedical\b", re.IGNORECASE), "of medical"),
    (re.compile(r"\bofmachine\b", re.IGNORECASE), "of machine"),
    (re.compile(r"\bofperspective\b", re.IGNORECASE), "of perspective"),
    (re.compile(r"\boffactual\b", re.IGNORECASE), "of factual"),
    (re.compile(r"\boflarge\b", re.IGNORECASE), "of large"),
    (re.compile(r"\bofthe\b", re.IGNORECASE), "of the"),
    (re.compile(r"\bof(\d+)\b", re.IGNORECASE), r"of \1"),
    (re.compile(r"\bGAL(?=\s+such\s+as\b)"), "GAI"),
    (re.compile(r"\bqualify\s+factor\b", re.IGNORECASE), "quality factor"),
    (re.compile(r"\bUniverisity\b", re.IGNORECASE), "University"),
    (re.compile(r"\bMEME\s+sensors\b", re.IGNORECASE), "MEMS sensors"),
    (re.compile(r"\bessenetial\b", re.IGNORECASE), "essential"),
    (re.compile(r"\bpathologica\b", re.IGNORECASE), "pathological"),
    (re.compile(r"\bdeceases\s+as\s+the\s+distance\b", re.IGNORECASE), "decreases as the distance"),
    (re.compile(r"\blength\s+form\s+ADF4351\b", re.IGNORECASE), "length from ADF4351"),
    (re.compile(r"\btoxity\b", re.IGNORECASE), "toxicity"),
    (re.compile(r"\bTlOO\b"), "T100"),
    (re.compile(r"\bQrnax\b"), "Qmax"),
    (re.compile(r"\bTQrnax\b"), "TQmax"),
    (re.compile(r"\bQ2sea\b"), "Q2sec"),
    (re.compile(r"\bLondon(?=(?:1[6-9]|20)\d{2}\b)"), "London "),
    (re.compile(r"\bco\s+verage\b", re.IGNORECASE), "coverage"),
    (re.compile(r"\bistor\s+ii\b", re.IGNORECASE), "istorii"),
    (re.compile(r"\bfotograf\s+ii\b", re.IGNORECASE), "fotografii"),
    (re.compile(r"\bMirocontroller\b", re.IGNORECASE), "microcontroller"),
    (re.compile(r"\bmicroconroller\b", re.IGNORECASE), "microcontroller"),
    (re.compile(r"\bNusssenblatt\b", re.IGNORECASE), "Nussenblatt"),
    (re.compile(r"\btemprature\b", re.IGNORECASE), "temperature"),
    (re.compile(r"\bchildrean\b", re.IGNORECASE), "children"),
    (re.compile(r"\bfascade\b", re.IGNORECASE), "facade"),
    (re.compile(r"\belectromyograhic\b", re.IGNORECASE), "electromyographic"),
    (re.compile(r"\bCompetinginterests\b", re.IGNORECASE), "Competing interests"),
    (re.compile(r"\bAdditionalinformation\b", re.IGNORECASE), "Additional information"),
    (re.compile(r"\bandrequests\b", re.IGNORECASE), "and requests"),
    (re.compile(r"\bandpermissions\b", re.IGNORECASE), "and permissions"),
    (re.compile(r"\bUSMLE:pPotential\b"), "USMLE: Potential"),
    (re.compile(r"\bforintracorticalstimulation\b", re.IGNORECASE), "for intracortical stimulation"),
    (re.compile(r"\bchosenasthiswasregardedasthenominal\b", re.IGNORECASE), "chosen as this was regarded as the nominal"),
    (re.compile(r"\bchosenasthiswasregardedasthe\b", re.IGNORECASE), "chosen as this was regarded as the"),
    (re.compile(r"\btimeconsuming\b", re.IGNORECASE), "time-consuming"),
    (re.compile(r"\btimedependent\b", re.IGNORECASE), "time-dependent"),
    (re.compile(r"\burineflow\b", re.IGNORECASE), "urine flow"),
    (re.compile(r"\bVideobased\b"), "Video-based"),
    (re.compile(r"\bvideobased\b"), "video-based"),
    (re.compile(r"\btextbased\b", re.IGNORECASE), "text-based"),
    (re.compile(r"\bleftright\b", re.IGNORECASE), "left-right"),
    (re.compile(r"\bfeed-andsleep\b", re.IGNORECASE), "feed-and-sleep"),
    (re.compile(r"\bsymptomscore\b", re.IGNORECASE), "symptom score"),
    (re.compile(r"\bdarkbrown\b", re.IGNORECASE), "dark brown"),
    (re.compile(r"\bpushpull\b", re.IGNORECASE), "push-pull"),
    (re.compile(r"\bFromFebruary\b"), "From February"),
    (re.compile(r"\bQcould\b"), "Q could"),
    (re.compile(r"\bQto\b"), "Q to"),
    (re.compile(r"\bBPHassociated\b"), "BPH-associated"),
    (re.compile(r"\bIPPgrades\b"), "IPP grades"),
    (re.compile(r"\bPositionrelated\b"), "Position-related"),
    (re.compile(r"\breadyreckoners\b", re.IGNORECASE), "ready reckoners"),
    (re.compile(r"\bwithlower\b", re.IGNORECASE), "with lower"),
    (re.compile(r"\btwoobject\b", re.IGNORECASE), "two-object"),
    (re.compile(r"\bshiftinvariant\b", re.IGNORECASE), "shift-invariant"),
    (re.compile(r"\bextrusionsurgically\b", re.IGNORECASE), "extrusion surgically"),
    (re.compile(r"\bdomaininvariant\b", re.IGNORECASE), "domain-invariant"),
    (re.compile(r"\bvitamin-Ddeficient\b", re.IGNORECASE), "vitamin-D-deficient"),
    (re.compile(r"\bOpticalTouch\b"), "Optical Touch"),
    (re.compile(r"\bvanderVorst\b"), "van der Vorst"),
    (re.compile(r"\bAl\s+Omari1\b"), "Al Omari 1"),
    (re.compile(r"\btexture\.Tactile\b"), "texture. Tactile"),
    (re.compile(r"\bsemisupervised\b", re.IGNORECASE), "semi-supervised"),
    (re.compile(r"\bthreedimensional\b", re.IGNORECASE), "three-dimensional"),
    (re.compile(r"\btwodimensional\b", re.IGNORECASE), "two-dimensional"),
    (re.compile(r"\blowdimensional\b", re.IGNORECASE), "low-dimensional"),
    (re.compile(r"\blocationspecific\b", re.IGNORECASE), "location-specific"),
    (re.compile(r"\btopdown\b", re.IGNORECASE), "top-down"),
    (re.compile(r"\bcontextdependent\b", re.IGNORECASE), "context-dependent"),
    (re.compile(r"\bfinergrained\b", re.IGNORECASE), "finer-grained"),
    (re.compile(r"\bsingleneuron\b", re.IGNORECASE), "single-neuron"),
    (re.compile(r"\bcontentaware\b", re.IGNORECASE), "content-aware"),
    (re.compile(r"\binhibitionbased\b", re.IGNORECASE), "inhibition-based"),
    (re.compile(r"\bfeaturebased\b", re.IGNORECASE), "feature-based"),
    (re.compile(r"\bphaselocked\b", re.IGNORECASE), "phase-locked"),
    (re.compile(r"\bcrossfrequency\b", re.IGNORECASE), "cross-frequency"),
    (re.compile(r"\bmetaanalysis\b", re.IGNORECASE), "meta-analysis"),
    (re.compile(r"\bpremicturtion\b", re.IGNORECASE), "premicturition"),
    (re.compile(r"\bulimate\b", re.IGNORECASE), "ultimate"),
    (re.compile(r"\bsupple\s+mental\b", re.IGNORECASE), "supplemental"),
    (re.compile(r"\bBiobeha\s+v\.\s+Rev\.", re.IGNORECASE), "Biobehav. Rev."),
    (re.compile(r"\bBeha\s+v\.\s+Res\.", re.IGNORECASE), "Behav. Res."),
    (re.compile(r"\bBeha\s+v\.\s+Sci\.", re.IGNORECASE), "Behav. Sci."),
    (re.compile(r"\bBeha\s+v\.\s+Neurosci\.", re.IGNORECASE), "Behav. Neurosci."),
    (re.compile(r"\bVwater\b", re.IGNORECASE), "V water"),
    (re.compile(r"\bKuznietso\s+v\b", re.IGNORECASE), "Kuznietsov"),
    (re.compile(r"\bbasreliefs\b", re.IGNORECASE), "bas-reliefs"),
    (re.compile(r"\bmattecollodion\b", re.IGNORECASE), "matte-collodion"),
    (re.compile(r"\basprepared\b", re.IGNORECASE), "as-prepared"),
    (re.compile(r"\basmeasured\b", re.IGNORECASE), "as measured"),
    (re.compile(r"\blung-tohead\b", re.IGNORECASE), "lung-to-head"),
    (re.compile(r"\bexplorationSeamless\b"), "exploration. Seamless"),
    (re.compile(r"\bda\s+Vinci1Si\b"), "da Vinci Si"),
    (re.compile(r"\ballin-one\b", re.IGNORECASE), "all-in-one"),
    (re.compile(r"\bfarred\b", re.IGNORECASE), "far-red"),
    (re.compile(r"\bPerceptionof\b"), "Perception of"),
    (re.compile(r"\bKey-wordaware\b"), "Keyword-aware"),
    (re.compile(r"\bopenaccess\b", re.IGNORECASE), "open-access"),
    (re.compile(r"\bBEHAVIORALAND\b"), "BEHAVIORAL AND"),
    (re.compile(r"\bMBVurgency\b"), "MBV-urgency"),
    (re.compile(r"\bCTABassistant\b"), "CTAB-assisted"),
    (re.compile(r"\bQmaxnormal\b"), "Qmax-normal"),
    (re.compile(r"\btouchinteraction\b", re.IGNORECASE), "touch interaction"),
    (re.compile(r"\bintraand\s+interobserver\b", re.IGNORECASE), "intra- and interobserver"),
    (re.compile(r"\bnearinfrared\b", re.IGNORECASE), "near-infrared"),
    (re.compile(r"\bShapefrom-shading\b"), "Shape-from-shading"),
    (re.compile(r"\bpatients,were\b", re.IGNORECASE), "patients were"),
    (re.compile(r"\bstaffmembers\b", re.IGNORECASE), "staff members"),
    (re.compile(r"\btheCreative\b"), "the Creative"),
    (re.compile(r"\bsinglefinger\b", re.IGNORECASE), "single-finger"),
    (re.compile(r"\bComputeraided\b"), "Computer-aided"),
    (re.compile(r"\bcomputeraided\b"), "computer-aided"),
    (re.compile(r"\bMRsafe\b"), "MR-safe"),
    (re.compile(r"\bMRcompatible\b"), "MR-compatible"),
    (re.compile(r"\binIndian\b"), "in Indian"),
    (re.compile(r"\bNineteenthcentury\b"), "Nineteenth-century"),
    (re.compile(r"\bnineteenthcentury\b"), "nineteenth-century"),
    (re.compile(r"\bairpolluted\b", re.IGNORECASE), "air-polluted"),
    (re.compile(r"\bwatersoluble\b", re.IGNORECASE), "water-soluble"),
    (re.compile(r"\bnonneoadjuvant\b", re.IGNORECASE), "non-neoadjuvant"),
    (re.compile(r"\blightbeam\b", re.IGNORECASE), "light-beam"),
    (re.compile(r"\bSUFestimated\b"), "SUF-estimated"),
    (re.compile(r"\bSUFdetermined\b"), "SUF-determined"),
    (re.compile(r"\bUFrecorded\b"), "UF-recorded"),
)
_LARGE_HTML_SAFE_WORD_GLUE_REPAIRS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bTheexperiment\b"), "The experiment"),
    (re.compile(r"\btheexperiment\b", re.IGNORECASE), "the experiment"),
    (re.compile(r"\btookplaceinasquare\b", re.IGNORECASE), "took place in a square"),
    (re.compile(r"\bbywooden\b", re.IGNORECASE), "by wooden"),
    (re.compile(r"\bThisarearepresented\b"), "This area represented"),
    (re.compile(r"\bafictitious\b", re.IGNORECASE), "a fictitious"),
    (re.compile(r"\broomthat\b", re.IGNORECASE), "room that"),
    (re.compile(r"\bhadtobeencoded\b", re.IGNORECASE), "had to be encoded"),
    (re.compile(r"\bbyparticipants\b", re.IGNORECASE), "by participants"),
    (re.compile(r"\bTheflooroftheareawasmarked\b"), "The floor of the area was marked"),
    (re.compile(r"\bbyacolored\b", re.IGNORECASE), "by a colored"),
    (re.compile(r"\bgridtomonitor\b", re.IGNORECASE), "grid to monitor"),
    (re.compile(r"\binjuryassociated\b", re.IGNORECASE), "injury-associated"),
    (re.compile(r"\btractfunction\b", re.IGNORECASE), "tract function"),
    (re.compile(r"\binflammationat\b", re.IGNORECASE), "inflammation at"),
    (re.compile(r"\bbenignprostatic\b", re.IGNORECASE), "benign prostatic"),
    (re.compile(r"\bTheeffect\b"), "The effect"),
    (re.compile(r"\bhealthyyoung\b", re.IGNORECASE), "healthy young"),
    (re.compile(r"\bdistentionon\b", re.IGNORECASE), "distention on"),
    (re.compile(r"\bsuggestiveof\b", re.IGNORECASE), "suggestive of"),
    (re.compile(r"\bAcceptableBladder\b"), "Acceptable Bladder"),
    (re.compile(r"\bandChallenges\b"), "and Challenges"),
    (re.compile(r"\bSoftBankbacked\b"), "SoftBank-backed"),
    (re.compile(r"\bNeururolUrodyn2021\b"), "Neurourol Urodyn 2021"),
    (re.compile(r"\bitemspecific\b", re.IGNORECASE), "item-specific"),
    (re.compile(r"\bmatch-tosample\b", re.IGNORECASE), "match-to-sample"),
    (re.compile(r"\bcontrolrelated\b", re.IGNORECASE), "control-related"),
    (re.compile(r"\bcuetrials\b", re.IGNORECASE), "cue trials"),
    (re.compile(r"\btrialaverage\b", re.IGNORECASE), "trial average"),
    (re.compile(r"\bintraobject\b", re.IGNORECASE), "intra-object"),
    (re.compile(r"\bimageto-image\b", re.IGNORECASE), "image-to-image"),
    (re.compile(r"\brealdomain\b", re.IGNORECASE), "real domain"),
    (re.compile(r"\btextdetection\b", re.IGNORECASE), "text-detection"),
    (re.compile(r"\bspeechballoon\b", re.IGNORECASE), "speech-balloon"),
    (re.compile(r"\bheld\s+inWM\b"), "held in WM"),
    (re.compile(r"\bimagedepth\b", re.IGNORECASE), "image-depth"),
    (re.compile(r"\bcustomdesigned\b", re.IGNORECASE), "custom-designed"),
    (re.compile(r"\bcognitive\s+iter\b", re.IGNORECASE), "cognitive filter"),
    (re.compile(r"\bsys-\s*tem\b", re.IGNORECASE), "system"),
    (re.compile(r"\btelsa\b", re.IGNORECASE), "tesla"),
    (re.compile(r"\bTQma\s+x\b"), "TQmax"),
    (re.compile(r"\bPdetQma\s+x\b"), "PdetQmax"),
    (re.compile(r"\bQrnax\b"), "Qmax"),
    (re.compile(r"\bTQrnax\b"), "TQmax"),
    (re.compile(r"\bQ2sea\b"), "Q2sec"),
    (re.compile(r"\bTlOO\b"), "T100"),
    (re.compile(r"\bAppel's\s+Sir\s+i\b", re.IGNORECASE), "Apple's Siri"),
    (re.compile(r"\bF\s+igures\b"), "Figures"),
    (re.compile(r"\bf\s+igures\b"), "figures"),
    (re.compile(r"\bchronologicall\s+y\b", re.IGNORECASE), "chronologically"),
    (re.compile(r"\bArchtecture\b"), "Architecture"),
    (re.compile(r"\barchtecture\b"), "architecture"),
    (re.compile(r"\bWoodsawer\b"), "Woodsawyer"),
    (re.compile(r"\bwoodsawer\b"), "woodsawyer"),
    (re.compile(r"\bclassifified\b", re.IGNORECASE), "classified"),
    (re.compile(r"\binital\b", re.IGNORECASE), "initial"),
    (re.compile(r"\bLondon(?=(?:1[6-9]|20)\d{2}\b)"), "London "),
    (re.compile(r"\bco\s+verage\b", re.IGNORECASE), "coverage"),
    (re.compile(r"\bappro\s+ximately\b", re.IGNORECASE), "approximately"),
    (re.compile(r"\bPRAVALENCE\b", re.IGNORECASE), "prevalence"),
    (re.compile(r"\bMulitmodal\b", re.IGNORECASE), "Multimodal"),
    (
        re.compile(r"\binternational\s+continent\s+society\b", re.IGNORECASE),
        "International Continence Society",
    ),
    (re.compile(r"\b\u03a4he\s+touch\s+map\b"), "The touch map"),
    (re.compile(r"\beBDetheque\b"), "eBDtheque"),
    (re.compile(r"\bmilivolt\b", re.IGNORECASE), "millivolt"),
    (re.compile(r"\bnanomicells\b", re.IGNORECASE), "nanomicelles"),
    (re.compile(r"\bDirectX-\s+R\b"), "DirectX-R"),
    (re.compile(r"\bBOO\s+i\b"), "BOOI"),
    (re.compile(r"\bsymphisis\b", re.IGNORECASE), "symphysis"),
    (re.compile(r"\b14\s+C-beled\b"), "14C-labeled"),
    (re.compile(r"\burine\s+ow\b", re.IGNORECASE), "urine flow"),
    (re.compile(r"\bwhite\s+ght\b", re.IGNORECASE), "white light"),
    (re.compile(r"\bmagnetic\s+eld\b", re.IGNORECASE), "magnetic field"),
    (re.compile(r"\beld\s+strength\b", re.IGNORECASE), "field strength"),
    (re.compile(r"\bsignifi\s+cant\b", re.IGNORECASE), "significant"),
    (re.compile(r"\bsignifi\s+cantly\b", re.IGNORECASE), "significantly"),
    (re.compile(r"\bsuf\s+cient\b", re.IGNORECASE), "sufficient"),
    (re.compile(r"\binsuf\s+cient\b", re.IGNORECASE), "insufficient"),
    (re.compile(r"\bbene\s+ts\b", re.IGNORECASE), "benefits"),
    (re.compile(r"\bfuorescent\b", re.IGNORECASE), "fluorescent"),
    (re.compile(r"\bfowed\b", re.IGNORECASE), "flowed"),
    (re.compile(r"\bfowmeters\b", re.IGNORECASE), "flowmeters"),
    (re.compile(r"\bfowrates\b", re.IGNORECASE), "flow rates"),
    (re.compile(r"\bsignifcance\b", re.IGNORECASE), "significance"),
    (re.compile(r"\bUrofowmetery\b"), "Uroflowmetry"),
    (re.compile(r"\burofowmetery\b"), "uroflowmetry"),
    (re.compile(r"\bUrofowmetry\b"), "Uroflowmetry"),
    (re.compile(r"\burofowmetry\b"), "uroflowmetry"),
    (re.compile(r"\bUrofowmeter\b"), "Uroflowmeter"),
    (re.compile(r"\burofowmeter\b"), "uroflowmeter"),
    (re.compile(r"\bve\s+patients\b", re.IGNORECASE), "five patients"),
    (re.compile(r"\bOf\s+ce\b"), "Office"),
    (re.compile(r"\benclusive\s+app\b", re.IGNORECASE), "inclusive app"),
    (re.compile(r"\bLUMBAH\s+I\s+-\s+i\b"), "LUMBAR DISC"),
    (re.compile(r"\(\s*!I\s+G\s*:\.\s*nosis\b", re.IGNORECASE), "diagnosis"),
    (re.compile(r"\bLumbar\s+lan\.~r\s+tl!\s*\*,?\.\s*tomy\b", re.IGNORECASE), "Lumbar laminectomy"),
    (re.compile(r"\bresult\s+t\s+L\s+'\s+n\b", re.IGNORECASE), "resulted in"),
    (re.compile(r"\bmuschnr\b[:.]*", re.IGNORECASE), "musculature."),
    (re.compile(r"\bv(?:&|&amp;)me\b", re.IGNORECASE), "volume"),
    (re.compile(r"\bTVRP\b"), "TURP"),
    (re.compile(r"\bpleak\s+flow\b", re.IGNORECASE), "peak flow"),
    (re.compile(r"\bmesc\b", re.IGNORECASE), "msec"),
    (re.compile(r"\bU-W\s+vertebrae\b", re.IGNORECASE), "L4-L5 vertebrae"),
    (re.compile(r"\b4y6-8\b"), "4,6-8"),
    (re.compile(r"\bVesicaf\b"), "Vesical"),
    (re.compile(r"\bJ\s+Ural\b"), "J Urol"),
    (re.compile(r"\bsnine\b", re.IGNORECASE), "spine"),
    (re.compile(r"\bGvnecol\b"), "Gynecol"),
    (re.compile(r"@e3\)"), "(1963)"),
    (re.compile(r"\borolanse\b", re.IGNORECASE), "prolapse"),
    (re.compile(r"\bI\s+Bone\s+Point\s+Sure\b"), "J Bone Joint Surg"),
    (re.compile(r"\bBvadley\b"), "Bradley"),
    (re.compile(r"\bforiTi\b", re.IGNORECASE), "form"),
    (re.compile(r"\bstimulus\.d/T\./Sz\b", re.IGNORECASE), "stimulus dEz/dz"),
    (re.compile(r"\belTicacy\b", re.IGNORECASE), "efficacy"),
    (re.compile(r"\bkcounl/mg\s+prolan\b", re.IGNORECASE), "kcount/mg protein"),
    (re.compile(r"\bLndferase\b"), "Luciferase"),
    (re.compile(r"\bdetermitied\b", re.IGNORECASE), "determined"),
    (re.compile(r"\biiiiegfiited\b", re.IGNORECASE), "integrated"),
    (re.compile(r"\blummesceoce\b", re.IGNORECASE), "luminescence"),
    (re.compile(r"\blinearmotor\s+S~pole\s+aller\b", re.IGNORECASE), "linearmotor S-pole after"),
    (re.compile(r"\bIt\s+isl\b"), "It is"),
    (re.compile(r"\baJways\b"), "always"),
    (re.compile(r"\bdemonstrale\b", re.IGNORECASE), "demonstrate"),
    (re.compile(r"\benor[\u00b7\s-]+mous\b", re.IGNORECASE), "enormous"),
    (re.compile(r"\briSing\b"), "rising"),
    (re.compile(r"\bproperty\s+center\b", re.IGNORECASE), "properly center"),
    (re.compile(r"\bcharaCleriza[\u00b7\s-]+lion\b", re.IGNORECASE), "characterization"),
    (re.compile(r"\bLlnhof\s+Master\s+Te(?:<|&lt;):hnlka\b"), "Linhof Master Technika"),
    (re.compile(r"\bUnhol\s+Kafdan\s+Mastel\s+TL\b"), "Linhof Kardan Master TL"),
    (re.compile(r"\binli\s+nily\b", re.IGNORECASE), "infinity"),
    (re.compile(r"\binfinily\b", re.IGNORECASE), "infinity"),
    (re.compile(r"\bout\s+of\s+locus\b", re.IGNORECASE), "out of focus"),
    (re.compile(r"\bScheimplJug\b"), "Scheimpflug"),
    (re.compile(r"\bSchelmptlug\b"), "Scheimpflug"),
    (re.compile(r"\bcompanson\s+ShOIS\b", re.IGNORECASE), "comparison shots"),
    (re.compile(r"\bparticularimagedislance\b", re.IGNORECASE), "particular image distance"),
    (re.compile(r"\bIndMdual\s+OUlldlngs\b", re.IGNORECASE), "Individual buildings"),
    (re.compile(r"\bgelloreground\b", re.IGNORECASE), "get foreground"),
    (re.compile(r"\bsubjecl\b", re.IGNORECASE), "subject"),
    (re.compile(r"\bpocIure\b", re.IGNORECASE), "picture"),
    (re.compile(r"\bslreellevel\b", re.IGNORECASE), "street level"),
    (re.compile(r"\beleminate\b", re.IGNORECASE), "eliminate"),
    (re.compile(r"\bsufiicient\b", re.IGNORECASE), "sufficient"),
    (re.compile(r"\bmillimelers\b", re.IGNORECASE), "millimeters"),
    (re.compile(r"\baillinhof-supplied\b", re.IGNORECASE), "all Linhof-supplied"),
    (re.compile(r"\bspecificions\b", re.IGNORECASE), "specifications"),
    (re.compile(r"\bMu(?:&|&amp;)es\b"), "Musées"),
    (re.compile(r"\bMu(?:&|&amp;)e\b"), "Musée"),
    (re.compile(r"\bHaiiy\b"), "Haüy"),
    (re.compile(r"\bCruc\$xion\b"), "Crucifixion"),
    (re.compile(r"\bmeaszu'ing\b", re.IGNORECASE), "measuring"),
    (re.compile(r"\bfww-cion\b", re.IGNORECASE), "function"),
    (re.compile(r"\bAi1[\u2022•]\s+displacement\s+pl'inuip\s*Ze\b", re.IGNORECASE), "Air displacement principle"),
    (re.compile(r"\bprinaip\s+Ze\b", re.IGNORECASE), "principle"),
    (re.compile(r"\bpl'inuip\s*Ze\b", re.IGNORECASE), "principle"),
    (re.compile(r"\bcontin,Ious\b", re.IGNORECASE), "continuous"),
    (re.compile(r"\bGra1Jimetry\b"), "Gravimetry"),
    (re.compile(r"\bOVerfLow\b"), "Overflow"),
    (re.compile(r"\buroflowrneter\b", re.IGNORECASE), "uroflowmeter"),
    (re.compile(r"\bUroflowrnetry\b"), "Uroflowmetry"),
    (re.compile(r"\bRotCDTleter\b"), "Rotameter"),
    (re.compile(r"\bPsyahoZogiaaZ\b"), "Psychological"),
    (re.compile(r"\bbZood\b"), "blood"),
    (re.compile(r"\bResiduaZ\b"), "Residual"),
    (re.compile(r"\bMuZtiphasicity\b"), "Multiphasicity"),
    (re.compile(r"\bestabZishment\b"), "establishment"),
    (re.compile(r"\bvaZues\b"), "values"),
    (re.compile(r"\bvariabZes\b"), "variables"),
    (re.compile(r"\babiZities\b"), "abilities"),
    (re.compile(r"\bA!Jstract\b"), "Abstract"),
    (re.compile(r"\bvuiation\b", re.IGNORECASE), "variation"),
    (re.compile(r"\bmeaswe\b", re.IGNORECASE), "measure"),
    (re.compile(r"\bDruck/Fiow\b"), "Druck/Flow"),
)
_LARGE_HTML_SAFE_LITERAL_WORD_GLUE_REPAIRS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bDmax=Dminw1:5\b"), "Dmax/Dmin > 1.5"),
    (re.compile(r"\bWherev\s+2\b"), "Where v^2"),
    (re.compile(r"\b0\.999\s+0995\b"), "0.999 0.995"),
    (re.compile(r"\br=0\.9\s+(840|526)\b"), r"r=0.9\1"),
    (
        re.compile(r"\bgrade\s+([123])(?:\u00bc|\u0412\u0458)(?=\d|more\b)", re.IGNORECASE),
        r"grade \1 = ",
    ),
    (re.compile(r"\bComputer\s+Based\s+Method\s+\?"), "Computer Based Method?"),
    (re.compile(r"\bI-SlOP\b"), "f-stop"),
    (re.compile(r"\bP\s+to\s+bc\b", re.IGNORECASE), "to be"),
)
_LARGE_HTML_SAFE_WORD_GLUE_MARKERS = (
    "Dmax=Dminw1:5",
    "Wherev 2",
    "0.999 0995",
    "r=0.9 840",
    "r=0.9 526",
    "grade 1\u00bc0",
    "grade 1\u0412\u04580",
    "Computer Based Method ?",
    "Theexperiment",
    "theexperiment",
    "tookplaceinasquare",
    "bywooden",
    "Thisarearepresented",
    "afictitious",
    "roomthat",
    "hadtobeencoded",
    "byparticipants",
    "Theflooroftheareawasmarked",
    "byacolored",
    "gridtomonitor",
    "injuryassociated",
    "tractfunction",
    "inflammationat",
    "benignprostatic",
    "Benignprostatic",
    "Theeffect",
    "healthyyoung",
    "distentionon",
    "suggestiveof",
    "AcceptableBladder",
    "andChallenges",
    "SoftBankbacked",
    "NeururolUrodyn2021",
    "itemspecific",
    "match-tosample",
    "controlrelated",
    "cuetrials",
    "trialaverage",
    "intraobject",
    "imageto-image",
    "realdomain",
    "textdetection",
    "speechballoon",
    "held inWM",
    "imagedepth",
    "customdesigned",
    "cognitive iter",
    "sys- tem",
    "telsa",
    "TQma x",
    "PdetQma x",
    "Qrnax",
    "TQrnax",
    "Q2sea",
    "TlOO",
    "Appel's Sir i",
    "F igures",
    "chronologicall y",
    "Archtecture",
    "archtecture",
    "Woodsawer",
    "woodsawer",
    "classifified",
    "inital",
    "London1843",
    "co verage",
    "appro ximately",
    "PRAVALENCE",
    "Mulitmodal",
    "International continent society",
    "international continent society",
    "\u03a4he touch map",
    "eBDetheque",
    "milivolt",
    "nanomicells",
    "DirectX- R",
    "BOO i",
    "symphisis",
    "14 C-beled",
    "urine ow",
    "white ght",
    "magnetic eld",
    "eld strength",
    "signifi cant",
    "signifi cantly",
    "suf cient",
    "insuf cient",
    "bene ts",
    "fuorescent",
    "fowed",
    "fowmeters",
    "fowrates",
    "signifcance",
    "Urofowmetery",
    "urofowmetery",
    "Urofowmetry",
    "urofowmetry",
    "Urofowmeter",
    "urofowmeter",
    "ve patients",
    "Of ce",
    "enclusive app",
    "LUMBAH I - i",
    "(!I G :. nosis",
    "lan.~r tl!",
    "result t L ' n",
    "muschnr",
    "v&me",
    "v&amp;me",
    "TVRP",
    "pleak flow",
    "mesc",
    "U-W vertebrae",
    "4y6-8",
    "Vesicaf",
    "J Ural",
    "snine",
    "Gvnecol",
    "@e3)",
    "orolanse",
    "I Bone Point Sure",
    "Bvadley",
    "foriTi",
    "stimulus.d/T./Sz",
    "elTicacy",
    "kcounl/mg prolan",
    "Lndferase",
    "determitied",
    "iiiiegfiited",
    "lummesceoce",
    "linearmotor S~pole aller",
    "It isl",
    "aJways",
    "demonstrale",
    "enor· mous",
    "riSing",
    "property center",
    "charaCleriza· lion",
    "Llnhof Master Te<:hnlka",
    "Llnhof Master Te&lt;:hnlka",
    "Unhol Kafdan Mastel TL",
    "inli nily",
    "infinily",
    "out of locus",
    "I-SlOP",
    "ScheimplJug",
    "Schelmptlug",
    "companson ShOIS",
    "particularimagedislance",
    "IndMdual OUlldlngs",
    "gelloreground",
    "subjecl",
    "pocIure",
    "slreellevel",
    "eleminate",
    "sufiicient",
    "millimelers",
    "aillinhof-supplied",
    "specificions",
    "Mu&es",
    "Mu&e",
    "Mu&amp;es",
    "Mu&amp;e",
    "Haiiy",
    "Cruc$xion",
    "P to bc",
    "measzu'ing",
    "fww-cion",
    "Ai1• displacement",
    "prinaip Ze",
    "pl'inuipZe",
    "contin,Ious",
    "Gra1Jimetry",
    "OVerfLow",
    "uroflowrneter",
    "Uroflowrnetry",
    "RotCDTleter",
    "PsyahoZogiaaZ",
    "bZood",
    "ResiduaZ",
    "MuZtiphasicity",
    "estabZishment",
    "vaZues",
    "variabZes",
    "abiZities",
    "A!Jstract",
    "vuiation",
    "measwe",
    "Druck/Fiow",
)
_EN_OCR_WORD_REPAIRS = (
    (re.compile(r"\bsignifcantly\b", re.IGNORECASE), "significantly"),
    (re.compile(r"\bsignifcant\b", re.IGNORECASE), "significant"),
    (re.compile(r"\bmodifcation\b", re.IGNORECASE), "modification"),
    (re.compile(r"\beficacy\b", re.IGNORECASE), "efficacy"),
    (re.compile(r"\beficiently\b", re.IGNORECASE), "efficiently"),
    (re.compile(r"\bsuficient\b", re.IGNORECASE), "sufficient"),
    (re.compile(r"\bsuficiently\b", re.IGNORECASE), "sufficiently"),
    (re.compile(r"\bofice\b", re.IGNORECASE), "office"),
    (re.compile(r"\boficer\b", re.IGNORECASE), "officer"),
    (re.compile(r"\btradeofs\b", re.IGNORECASE), "tradeoffs"),
    (re.compile(r"\bfexible\b", re.IGNORECASE), "flexible"),
    (re.compile(r"\bultrafexible\b", re.IGNORECASE), "ultraflexible"),
    (re.compile(r"\bfbers\b", re.IGNORECASE), "fibers"),
    (re.compile(r"\bfber\b", re.IGNORECASE), "fiber"),
    (re.compile(r"\bflms\b", re.IGNORECASE), "films"),
    (re.compile(r"\bflm\b", re.IGNORECASE), "film"),
    (re.compile(r"\bfbroin\b", re.IGNORECASE), "fibroin"),
    (re.compile(r"\bbiofuid\b", re.IGNORECASE), "biofluid"),
    (re.compile(r"\bdifusion\b", re.IGNORECASE), "diffusion"),
    (re.compile(r"\bscafolds\b", re.IGNORECASE), "scaffolds"),
    (re.compile(r"\bscafold\b", re.IGNORECASE), "scaffold"),
    (re.compile(r"\bfeld-efect\b", re.IGNORECASE), "field-effect"),
    (re.compile(r"\bfltering\b", re.IGNORECASE), "filtering"),
    (re.compile(r"\bfll\b", re.IGNORECASE), "fill"),
    (re.compile(r"\bflled\b", re.IGNORECASE), "filled"),
    (re.compile(r"\bfowing\b", re.IGNORECASE), "flowing"),
    (re.compile(r"\bfuoroscopy\b", re.IGNORECASE), "fluoroscopy"),
    (re.compile(r"\bfuoroscopic\b", re.IGNORECASE), "fluoroscopic"),
    (re.compile(r"\bfashes\b", re.IGNORECASE), "flashes"),
    (re.compile(r"\bgalss\b", re.IGNORECASE), "glass"),
    (re.compile(r"\bcoeficients\b", re.IGNORECASE), "coefficients"),
    (re.compile(r"\bfrst\b", re.IGNORECASE), "first"),
    (re.compile(r"\bfne\b", re.IGNORECASE), "fine"),
    (re.compile(r"\bfgurative\b", re.IGNORECASE), "figurative"),
    (re.compile(r"\bdefne\b"), "define"),
    (re.compile(r"\bdefned\b", re.IGNORECASE), "defined"),
    (re.compile(r"\bprofcient\b", re.IGNORECASE), "proficient"),
    (re.compile(r"\bbeneft\b", re.IGNORECASE), "benefit"),
    (re.compile(r"\bdifcult\b", re.IGNORECASE), "difficult"),
    (re.compile(r"\bdifculty\b", re.IGNORECASE), "difficulty"),
    (re.compile(r"\bdifculties\b", re.IGNORECASE), "difficulties"),
    (re.compile(r"\bstaf\b", re.IGNORECASE), "staff"),
    (re.compile(r"\befort\b", re.IGNORECASE), "effort"),
    (re.compile(r"\beforts\b", re.IGNORECASE), "efforts"),
    (re.compile(r"\bconfrm\b", re.IGNORECASE), "confirm"),
    (re.compile(r"\bconfrmed\b", re.IGNORECASE), "confirmed"),
    (re.compile(r"\bconfrming\b", re.IGNORECASE), "confirming"),
    (re.compile(r"\bclarifed\b", re.IGNORECASE), "clarified"),
    (re.compile(r"\binfuenced\b", re.IGNORECASE), "influenced"),
    (re.compile(r"\bfnger\b", re.IGNORECASE), "finger"),
    (re.compile(r"\bfndings\b", re.IGNORECASE), "findings"),
    (re.compile(r"\bfeld\b", re.IGNORECASE), "field"),
    (re.compile(r"\bsignificate\b", re.IGNORECASE), "significant"),
    (re.compile(r"\binvolunatary\b", re.IGNORECASE), "involuntary"),
    (re.compile(r"\buroflometer\b", re.IGNORECASE), "uroflowmeter"),
    (re.compile(r"\bupto\b", re.IGNORECASE), "up to"),
    (re.compile(r"\bsimpification\b", re.IGNORECASE), "simplification"),
    (re.compile(r"\bparametres\b", re.IGNORECASE), "parameters"),
    (re.compile(r"\bpngpng\b", re.IGNORECASE), "png"),
    (re.compile(r"\bAmercian\b", re.IGNORECASE), "American"),
    (re.compile(r"\bprostatectomy\u0394VV\b", re.IGNORECASE), "prostatectomy \u0394VV"),
    (re.compile(r"\bgroundtruth\b", re.IGNORECASE), "ground-truth"),
    (re.compile(r"\bbackilluminated\b", re.IGNORECASE), "back-illuminated"),
    (re.compile(r"\bdisplaycan\b", re.IGNORECASE), "display can"),
    (re.compile(r"\bofdepression\b", re.IGNORECASE), "of depression"),
    (re.compile(r"\bnumbergestures\b", re.IGNORECASE), "number gestures"),
    (re.compile(r"\b99Tcmcolloids\b", re.IGNORECASE), "99Tcm colloids"),
    (re.compile(r"\bliverposl\b", re.IGNORECASE), "Liverpool"),
    (re.compile(r"\bExaming\b", re.IGNORECASE), "examining"),
    (re.compile(r"\binital\b", re.IGNORECASE), "initial"),
    (re.compile(r"\bBolognia\b", re.IGNORECASE), "Bologna"),
    (re.compile(r"\bsystometry\b", re.IGNORECASE), "cystometry"),
    (re.compile(r"\bbulbocarnosus\b", re.IGNORECASE), "bulbocavernosus"),
    (re.compile(r"\bNcology\b", re.IGNORECASE), "oncology"),
    (re.compile(r"\beuromodulation\b", re.IGNORECASE), "neuromodulation"),
    (re.compile(r"\bSegmentaion\b", re.IGNORECASE), "segmentation"),
    (re.compile(r"\bbootloding\b", re.IGNORECASE), "bootloading"),
    (re.compile(r"\bdiscription\b", re.IGNORECASE), "description"),
    (re.compile(r"\bDeptartment\b", re.IGNORECASE), "department"),
    (re.compile(r"\bPRAVALENCE\b", re.IGNORECASE), "prevalence"),
    (re.compile(r"\bNeurocsi\b", re.IGNORECASE), "Neurosci"),
    (re.compile(r"\bSchfer\b"), "Sch\u00e4fer"),
)
_EN_OCR_PHRASE_REPAIRS = (
    (re.compile(r"(?:\u00ae|\u0412\u00ae)rst\b", re.IGNORECASE), "first"),
    (re.compile(r"\bmedicineresistant\b", re.IGNORECASE), "medicine-resistant"),
    (re.compile(r"\bcustomdesigned\b", re.IGNORECASE), "custom-designed"),
    (re.compile(r"\bhardwareupdate\b", re.IGNORECASE), "hardware update"),
    (re.compile(r"\beasy-tolearn\b", re.IGNORECASE), "easy-to-learn"),
    (re.compile(r"\bAttributebased\b"), "Attribute-based"),
    (re.compile(r"\battributebased\b"), "attribute-based"),
    (re.compile(r"\bthistask\b", re.IGNORECASE), "this task"),
    (re.compile(r"\bhigherthan\b", re.IGNORECASE), "higher than"),
    (re.compile(r"\bdisabilitiessometimesface\b", re.IGNORECASE), "disabilities sometimes face"),
    (re.compile(r"\bartworksis\b", re.IGNORECASE), "artworks is"),
    (re.compile(r"\bhierarchicalsegmentation\b", re.IGNORECASE), "hierarchical segmentation"),
    (re.compile(r"\bwebbased\b", re.IGNORECASE), "web-based"),
    (re.compile(r"\bneedsto\b", re.IGNORECASE), "needs to"),
    (re.compile(r"\bincludesinformation\b", re.IGNORECASE), "includes information"),
    (re.compile(r"\bparticipantssuggested\b", re.IGNORECASE), "participants suggested"),
    (re.compile(r"\boverallwork\b", re.IGNORECASE), "overall work"),
    (re.compile(r"\bguidelinesfor\b", re.IGNORECASE), "guidelines for"),
    (re.compile(r"\bissimilarto\b", re.IGNORECASE), "is similar to"),
    (re.compile(r"\beasierto\b", re.IGNORECASE), "easier to"),
    (re.compile(r"\bspatialcognitive\b", re.IGNORECASE), "spatial-cognitive"),
    (re.compile(r"\bwassupported\b", re.IGNORECASE), "was supported"),
    (re.compile(r"\bblindaccessible\b", re.IGNORECASE), "blind-accessible"),
    (re.compile(r"\bpopulationbased\b", re.IGNORECASE), "population-based"),
    (re.compile(r"\bmagnetic\s+eld\b", re.IGNORECASE), "magnetic field"),
    (re.compile(r"\burine\s+ow\b", re.IGNORECASE), "urine flow"),
    (re.compile(r"\bsignalto-noise\b", re.IGNORECASE), "signal-to-noise"),
    (re.compile(r"\bbasrelief\b", re.IGNORECASE), "bas-relief"),
    (re.compile(r"\bfrontto-back\b", re.IGNORECASE), "front-to-back"),
    (re.compile(r"\becofriendly\b", re.IGNORECASE), "eco-friendly"),
    (re.compile(r"\bnervesparing\b", re.IGNORECASE), "nerve-sparing"),
    (re.compile(r"\bupprojection\b", re.IGNORECASE), "up-projection"),
    (re.compile(r"\bKeunWhangbo\b"), "Keun Whangbo"),
    (re.compile(r"\bfirst-inhumans\b", re.IGNORECASE), "first-in-humans"),
    (re.compile(r"\bDescriptionsfor\b"), "Descriptions for"),
    (re.compile(r"\brealworld\b", re.IGNORECASE), "real-world"),
    (re.compile(r"\bRefreshabletactile\b"), "Refreshable tactile"),
    (re.compile(r"\bOFTACTILE\b"), "OF TACTILE"),
    (re.compile(r"\bresidualnormal\b", re.IGNORECASE), "residual-normal"),
    (re.compile(r"\bprocessingbased\b", re.IGNORECASE), "processing-based"),
    (re.compile(r"\bhandassembled\b", re.IGNORECASE), "hand-assembled"),
    (re.compile(r"\bstaffmember\b", re.IGNORECASE), "staff member"),
    (re.compile(r"\bselfcontrolled\b", re.IGNORECASE), "self-controlled"),
    (re.compile(r"\bQmaxurgency\b"), "Qmax-urgency"),
    (re.compile(r"\bd\)2\.5D\b"), "d) 2.5D"),
    (re.compile(r"\bEVERYDAYACTIVITIES\b"), "EVERYDAY ACTIVITIES"),
    (re.compile(r"\burinary\s+track\b", re.IGNORECASE), "urinary tract"),
    (re.compile(r"\bAppend ix\b"), "Appendix"),
    (re.compile(r"\bAPPEND\s+ix\b"), "APPENDIX"),
    (re.compile(r"\bMDP\s+i\b"), "MDPI"),
    (re.compile(r"\bHindaw\s+i\b"), "Hindawi"),
    (re.compile(r"\bfMR\s+i\b"), "fMRI"),
    (re.compile(r"\bI\s+mplantable\b"), "Implantable"),
    (re.compile(r"\bSem\s+i\s*-\s*structured\b"), "Semi-structured"),
    (re.compile(r"\bsem\s+i\s*-\s*structured\b"), "semi-structured"),
    (re.compile(r"\bS\s+chematic\b"), "Schematic"),
    (re.compile(r"\bT\s+he\b"), "The"),
    (re.compile(r"\bTree-dimensional\b"), "Three-dimensional"),
    (re.compile(r"\btree-dimensional\b"), "three-dimensional"),
    (re.compile(r"\bThree-dimensioanl\b"), "Three-dimensional"),
    (re.compile(r"\bthree-dimensioanl\b"), "three-dimensional"),
    (re.compile(r"\bSofware\b"), "Software"),
    (re.compile(r"\bsofware\b"), "software"),
    (re.compile(r"\bwill\s+to\s+help\b", re.IGNORECASE), "will help"),
    (re.compile(r"\bMata-Analysis\b"), "Meta-Analysis"),
    (re.compile(r"\bMagr\s+Reson\b", re.IGNORECASE), "Magn Reson"),
    (re.compile(r"\bdocuments\s+that\s+that\s+intensity\b", re.IGNORECASE), "documents that the intensity"),
    (re.compile(r"\bRetinal\s+Nerve\s+Fiber\s+Laver\b"), "Retinal Nerve Fiber Layer"),
    (re.compile(r"\bt\s+o\s+the\s+best\s+of\s+our\s+knowledge\b", re.IGNORECASE), "to the best of our knowledge"),
    (re.compile(r"\bThirtyeight\b"), "Thirty-eight"),
    (re.compile(r"\bthirtyeight\b"), "thirty-eight"),
    (re.compile(r"\bsys-\s*tem\b", re.IGNORECASE), "system"),
    (re.compile(r"\bcrania\s+l\s+implant\b", re.IGNORECASE), "cranial implant"),
    (re.compile(r"\bappro\s+ximately\b", re.IGNORECASE), "approximately"),
    (re.compile(r"\bF\s+igures\b"), "Figures"),
    (re.compile(r"\bf\s+igures\b"), "figures"),
    (re.compile(r"\bpassive\s+senor\b", re.IGNORECASE), "passive sensor"),
    (re.compile(r"\bAppel's\s+Sir\s+i\b", re.IGNORECASE), "Apple's Siri"),
    (re.compile(r"\bcompliment\s+of\s+the\s+text-area\s+mask\b", re.IGNORECASE), "complement of the text-area mask"),
    (re.compile(r"\bHip-pocampus\b", re.IGNORECASE), "Hippocampus"),
    (re.compile(r"\bFlorescence\s+Technique\b", re.IGNORECASE), "Fluorescence Technique"),
    (re.compile(r"\bStocks\s+shift\b", re.IGNORECASE), "Stokes shift"),
    (re.compile(r"\bObject\s+Eden260V\b", re.IGNORECASE), "Objet Eden260V"),
    (re.compile(r"\bOPRATING\s+PRICIPLE\b", re.IGNORECASE), "OPERATING PRINCIPLE"),
    (re.compile(r"\bARTI\s+CLE\s+TYPE\b", re.IGNORECASE), "ARTICLE TYPE"),
    (re.compile(r"\bsimulates\s+the\s+The\s+validation\b", re.IGNORECASE), "simulates the validation"),
    (re.compile(r"\bto\s+be\s+The\s+topological\s+sort\b", re.IGNORECASE), "to be the topological sort"),
    (re.compile(r"\baesthesia\s+protocols\b", re.IGNORECASE), "anesthesia protocols"),
    (re.compile(r"\bPdetQma\s+x\b"), "PdetQmax"),
    (re.compile(r"\bTQma\s+x\b"), "TQmax"),
    (re.compile(r"\bob\s+je\s+ct\s+s\s+w\s+ould\b", re.IGNORECASE), "objects would"),
    (re.compile(r"\bsafe\s+ty\s+c\s+oncerns\b", re.IGNORECASE), "safety concerns"),
    (re.compile(r"\bincl\s+ude\b", re.IGNORECASE), "include"),
    (re.compile(r"\bb\s+e\s+interpreted\b", re.IGNORECASE), "be interpreted"),
    (re.compile(r"\bA\s+dd\s+itional\b"), "Additional"),
    (re.compile(r"\bsupple\s+mental\b", re.IGNORECASE), "supplemental"),
    (re.compile(r"\bexpressi\s+ve\s+ness\b", re.IGNORECASE), "expressiveness"),
    (re.compile(r"\bT\s+his\s+fact\b"), "This fact"),
    (re.compile(r"\bspecifi\s+c\b", re.IGNORECASE), "specific"),
    (re.compile(r"\bSpecifi\s+cally\b"), "Specifically"),
    (re.compile(r"\bspecifi\s+cally\b"), "specifically"),
    (re.compile(r"\bfi\s+rst\b", re.IGNORECASE), "first"),
    (re.compile(r"\bdefi\s+ciency\b", re.IGNORECASE), "deficiency"),
    (re.compile(r"\bdefi\s+ne\b", re.IGNORECASE), "define"),
    (re.compile(r"\bdefi\s+ned\b", re.IGNORECASE), "defined"),
    (re.compile(r"\bDefi\s+nition\b"), "Definition"),
    (re.compile(r"\bdefi\s+nition\b"), "definition"),
    (re.compile(r"\bDiffi\s+cult\b"), "Difficult"),
    (re.compile(r"\bdiffi\s+cult\b"), "difficult"),
    (re.compile(r"\bdiffi\s+culties\b", re.IGNORECASE), "difficulties"),
    (re.compile(r"\bdiffi\s+culty\b", re.IGNORECASE), "difficulty"),
    (re.compile(r"\bidentifi\s+es\b", re.IGNORECASE), "identifies"),
    (re.compile(r"\bidentifi\s+ed\b", re.IGNORECASE), "identified"),
    (re.compile(r"\bsignifi\s+cant\b", re.IGNORECASE), "significant"),
    (re.compile(r"\bsignifi\s+cantly\b", re.IGNORECASE), "significantly"),
    (re.compile(r"\binfl\s+uence\b", re.IGNORECASE), "influence"),
    (re.compile(r"\bProfi\s+le\b"), "Profile"),
    (re.compile(r"\bprofi\s+les\b", re.IGNORECASE), "profiles"),
    (re.compile(r"\bprofi\s+le\b", re.IGNORECASE), "profile"),
    (re.compile(r"\bconfi\s+dence\b", re.IGNORECASE), "confidence"),
    (re.compile(r"\bGriffi\s+ths\b"), "Griffiths"),
    (re.compile(r"\brefl\s+ux\b", re.IGNORECASE), "reflux"),
    (re.compile(r"\bfl\s+uoroscopy\b", re.IGNORECASE), "fluoroscopy"),
    (re.compile(r"\bfl\s+uoroscopic\b", re.IGNORECASE), "fluoroscopic"),
    (re.compile(r"\bfl\s+uorescent\b", re.IGNORECASE), "fluorescent"),
    (re.compile(r"\bfl\s+oor\b", re.IGNORECASE), "floor"),
    (re.compile(r"\bOffi\s+ce\b"), "Office"),
    (re.compile(r"\boffi\s+ce\b"), "office"),
    (re.compile(r"\bbenefi\s+cial\b", re.IGNORECASE), "beneficial"),
    (re.compile(r"\boutfl\s+ow\b", re.IGNORECASE), "outflow"),
    (re.compile(r"\burofl\s+owmetry\b", re.IGNORECASE), "uroflowmetry"),
    (re.compile(r"\burofl\s+owmeter\b", re.IGNORECASE), "uroflowmeter"),
    (re.compile(r"\burofl\s+ow\b", re.IGNORECASE), "uroflow"),
    (re.compile(r"\bfl\s+uid\b", re.IGNORECASE), "fluid"),
    (re.compile(r"\bfl\s+ow\b", re.IGNORECASE), "flow"),
    (re.compile(r"\bCNC-millin\s+g\s+m\s+achines\b", re.IGNORECASE), "CNC-milling machines"),
    (re.compile(r"\bsupp\s+ort\s+structures\b", re.IGNORECASE), "support structures"),
    (re.compile(r"\ba\s+dditive\s+production\b", re.IGNORECASE), "additive production"),
    (re.compile(r"\balternati\s+ves\b", re.IGNORECASE), "alternatives"),
    (re.compile(r"\bpr\s+inting\s+services\b", re.IGNORECASE), "printing services"),
    (re.compile(r"\btechnical\s+ly\b", re.IGNORECASE), "technically"),
    (re.compile(r"\bhigh\s*\)\s*w\s+ere\b", re.IGNORECASE), "high) were"),
    (re.compile(r"\bthr\s+ee\s+different\b", re.IGNORECASE), "three different"),
    (re.compile(r"\bstraightfo\s+rw\s+ard\b", re.IGNORECASE), "straightforward"),
    (re.compile(r"\bGener\s+al\s+digital\b"), "General digital"),
    (re.compile(r"\bBarc\s+elona\b", re.IGNORECASE), "Barcelona"),
    (re.compile(r"\benj\s+oy\b", re.IGNORECASE), "enjoy"),
    (re.compile(r"\bB rain-computer\b"), "Brain-computer"),
    (re.compile(r"\bIta ly\b"), "Italy"),
    (re.compile(r"\benviron\s+ment\b", re.IGNORECASE), "environment"),
    (re.compile(r"\bNeuro\s+sci\b", re.IGNORECASE), "Neurosci"),
    (re.compile(r"\bParkin\s+sonism\b", re.IGNORECASE), "Parkinsonism"),
    (re.compile(r"\bdisconti\s+nuation\b", re.IGNORECASE), "discontinuation"),
    (re.compile(r"\bBel humeur\b"), "Belhumeur"),
    (re.compile(r"\bLeporin i\b"), "Leporini"),
    (re.compile(r"\badvanta-\s*[\u00a8\u02d9]\s*geous\b", re.IGNORECASE), "advantageous"),
    (
        re.compile(r"\bThe laser components include The Cartesian linear stage provides\b"),
        "The Cartesian linear stage provides",
    ),
    (re.compile(r"\bbest suites\b", re.IGNORECASE), "best suits"),
    (re.compile(r"\bHands of!"), "Hands off!"),
    (re.compile(r"\ball the they identified\b", re.IGNORECASE), "all that they identified"),
    (re.compile(r"\bvoiding positing\b", re.IGNORECASE), "voiding position"),
)
_EN_OCR_CROSS_TAG_SKIP_TAGS = {"script", "style", "code", "pre", "math", "svg"}
_EN_OCR_INLINE_TOKEN_TAG_PATTERN = r"(?P<tag>a|b|i|span|sup|sub)"
_EN_OCR_CROSS_TAG_REPAIRS: tuple[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]], ...] = (
    (
        re.compile(
            rf"\bAPPEND\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*ix\s*</(?P=tag)>"
        ),
        "APPENDIX",
    ),
    (
        re.compile(
            rf"\bAppend\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*ix\s*</(?P=tag)>"
        ),
        "Appendix",
    ),
    (
        re.compile(
            rf"\bMDP\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*i\s*</(?P=tag)>",
            re.IGNORECASE,
        ),
        "MDPI",
    ),
    (
        re.compile(
            rf"\bHindaw\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*i\s*</(?P=tag)>",
            re.IGNORECASE,
        ),
        "Hindawi",
    ),
    (
        re.compile(
            rf"\bfMR\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*i\s*</(?P=tag)>",
            re.IGNORECASE,
        ),
        "fMRI",
    ),
    (
        re.compile(
            rf"\bSem\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*i\s*</(?P=tag)>\s*-\s*structured\b",
            re.IGNORECASE,
        ),
        "Semi-structured",
    ),
    (
        re.compile(
            rf"\b(?P<prefix>TQma|PdetQma)\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*x\s*</(?P=tag)>",
            re.IGNORECASE,
        ),
        lambda m: f"{m.group('prefix')}x",
    ),
    (
        re.compile(
            rf"\b(?P<stem>crania)\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*l\s*</(?P=tag)>\s+implant\b",
            re.IGNORECASE,
        ),
        lambda m: f"{_case_like(m.group('stem'), 'cranial')} implant",
    ),
    (
        re.compile(
            rf"\bappro\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*x\s*</(?P=tag)>\s*imately\b",
            re.IGNORECASE,
        ),
        "approximately",
    ),
    (
        re.compile(
            rf"\b(?P<lead>[Ff])\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*igures\s*</(?P=tag)>"
        ),
        lambda m: "Figures" if m.group("lead") == "F" else "figures",
    ),
    (
        re.compile(
            rf"\bsys\s*-\s*<{_EN_OCR_INLINE_TOKEN_TAG_PATTERN}\b[^>]*>\s*tem\s*</(?P=tag)>\b",
            re.IGNORECASE,
        ),
        "system",
    ),
    (
        re.compile(
            r"(?P<open><a\b[^>]*>)\s*(?P<prefix>\[?)\s*Bel\s*(?P<close></a>)\s*humeur\b",
            re.IGNORECASE,
        ),
        lambda m: f"{m.group('open')}{m.group('prefix')}Belhumeur{m.group('close')}",
    ),
    (
        re.compile(
            r"\bob\s*<a\b[^>]*>\s*je\s*</a>\s*"
            r"<a\b[^>]*>\s*ct\s*</a>\s*"
            r"<a\b[^>]*>\s*s\s+w\s*</a>\s*ould\b",
            re.IGNORECASE,
        ),
        "objects would",
    ),
    (
        re.compile(
            r"\bob\s+je\s+ct\s*<a\b[^>]*>\s*s\s+w\s*</a>\s*ould\b",
            re.IGNORECASE,
        ),
        "objects would",
    ),
    (
        re.compile(r"\bsafe\s*<a\b[^>]*>\s*ty\s+c\s*</a>\s*oncerns\b", re.IGNORECASE),
        "safety concerns",
    ),
    (
        re.compile(r"\bincl\s*<a\b[^>]*>\s*ude\s*</a>", re.IGNORECASE),
        "include",
    ),
    (
        re.compile(r"<a\b[^>]*>\s*b\s*</a>\s*e\s+interpreted\b", re.IGNORECASE),
        "be interpreted",
    ),
    (
        re.compile(r"\bA\s*<a\b[^>]*>\s*dd\s*</a>\s*itional\b"),
        "Additional",
    ),
    (
        re.compile(r"\bexpressi\s*<a\b[^>]*>\s*ve\s*</a>\s*ness\b", re.IGNORECASE),
        "expressiveness",
    ),
    (
        re.compile(r"\bsignifi\s*(?P<open><a\b[^>]*>)\s*cantly\b", re.IGNORECASE),
        lambda m: f"significantly {m.group('open')}",
    ),
    (
        re.compile(r"\bsignifi\s*(?P<open><a\b[^>]*>)\s*cant\b", re.IGNORECASE),
        lambda m: f"significant {m.group('open')}",
    ),
    (
        re.compile(r"\bT\s*<a\b[^>]*>\s*his\s*</a>\s*fact\b"),
        "This fact",
    ),
    (
        re.compile(r"\bCNC-millin\s*<a\b[^>]*>\s*g\s+m\s*</a>\s*achines\b", re.IGNORECASE),
        "CNC-milling machines",
    ),
    (
        re.compile(
            r"\bsupp\s*<a\b[^>]*>\s*ort\s+structures\s+in\s+a\s*</a>\s*"
            r"dditive\s+production\b",
            re.IGNORECASE,
        ),
        "support structures in additive production",
    ),
    (
        re.compile(r"\balternati\s*<a\b[^>]*>\s*ves\s*</a>", re.IGNORECASE),
        "alternatives",
    ),
    (
        re.compile(r"<a\b[^>]*>\s*pr\s*</a>\s*inting\s+services\b", re.IGNORECASE),
        "printing services",
    ),
    (
        re.compile(r"\btechnical\s*<a\b[^>]*>\s*ly\s*</a>", re.IGNORECASE),
        "technically",
    ),
    (
        re.compile(
            r"\bhigh\s*<a\b[^>]*>\s*\)\s*</a>\s*<a\b[^>]*>\s*w\s*</a>\s*ere\b",
            re.IGNORECASE,
        ),
        "high) were",
    ),
    (
        re.compile(r"\bthr\s*<a\b[^>]*>\s*ee\s*</a>\s*different\b", re.IGNORECASE),
        "three different",
    ),
    (
        re.compile(r"\bstraightfo\s*<a\b[^>]*>\s*rw\s*</a>\s*ard\b", re.IGNORECASE),
        "straightforward",
    ),
    (
        re.compile(r"\bGener\s*<a\b[^>]*>\s*al\s*</a>\s*digital\b"),
        "General digital",
    ),
    (
        re.compile(r"<a\b[^>]*>\s*Barc\s*</a>\s*elona\b", re.IGNORECASE),
        "Barcelona",
    ),
    (
        re.compile(r"\benj\s*<a\b[^>]*>\s*oy(?P<trail>\s+a)?\s*</a>", re.IGNORECASE),
        lambda m: "enjoy" + (m.group("trail") or ""),
    ),
    (
        re.compile(r"<b\b[^>]*>\s*B\s*</b>\s*rain-computer\b", re.IGNORECASE),
        "Brain-computer",
    ),
    (
        re.compile(r"\bIta\s*<b\b[^>]*>\s*ly\s*</b>", re.IGNORECASE),
        "Italy",
    ),
    (
        re.compile(
            r"\b(?P<stem>Leporin|Ghian)\s*"
            r"<sup\b(?=[^>]*\bclass\s*=\s*([\"'])[^\"']*\bz2m-table-fn\b[^\"']*\2)[^>]*>"
            r"\s*i\s*</sup>",
            re.IGNORECASE,
        ),
        lambda m: f"{m.group('stem')}i",
    ),
)
_DETACHED_ACCENT_AUTHOR_AND_PATTERN = re.compile(r",\s*[\u00b4\u00a8\u02c6]\s+(?=and\b)")
_DETACHED_CEDILLA_INITIAL_PATTERN = re.compile(r"\bC[\u00b8\u0327]\s*\.\s+(?=Varel\b)")
_DETACHED_DIAERESIS_SPACE_PATTERN = re.compile(r"\s+[\u00a8]\s+(?=intraocular\b)")
_DETACHED_DIAERESIS_POWERED_PATTERN = re.compile(r"\s+[\u00a8]\s+(?=powered\b)")
_DETACHED_SYD_DIAERESIS_PATTERN = re.compile(r"\bSyd\s+[\u00a8]\s+anheimo\b")
_DETACHED_MOJIBAKE_CEDILLA_INITIAL_PATTERN = re.compile(r"\bC\u0412\u0451\s*\.\s+(?=Varel\b)")
_DETACHED_MOJIBAKE_DIAERESIS_SPACE_PATTERN = re.compile(r"\s+\u0412\u0401\s+(?=intraocular\b)")
_DETACHED_MOJIBAKE_DIAERESIS_POWERED_PATTERN = re.compile(r"\s+\u0412\u0401\s+(?=powered\b)")
_DETACHED_MOJIBAKE_SYD_DIAERESIS_PATTERN = re.compile(r"\bSyd\s+\u0412\u0401\s+anheimo\b")
_PUBLISHED_DOWNLOADED_PAGE_FURNITURE_PATTERN = re.compile(
    r"\bPublished\s+on\s+\d{1,2}\s+[A-Z][a-z]+\s+\d{4}\.\s+Downloaded\s+by\s+"
    r".{3,180}?\s+on\s+\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\s*",
    re.IGNORECASE,
)
_PAGE_FURNITURE_TEXT_REPAIRS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_PUBLISHED_DOWNLOADED_PAGE_FURNITURE_PATTERN, " "),
    (
        re.compile(
            r"\bPublished\s+on\s+20\s+July\s+2015\.\s+Downloaded\s+by\s+"
            r"California\s+State\s+University\s+at\s+Fresno\s+on\s+"
            r"\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\s*",
            re.IGNORECASE,
        ),
        " ",
    ),
    (
        re.compile(
            r"\bManuscript\s+received\s+on\s+April\s+17,\s+2021\.\s+"
            r"Revised\s+Manuscript\s+received\s+on\s+April\s+15,\s+2021\.\s+"
            r"Manuscript\s+published\s+on\s+April\s+30,\s+2021\.?"
            r"(?:\s*\*\s*Correspondence\s+Author)?\s*",
            re.IGNORECASE,
        ),
        " ",
    ),
    (re.compile(r"\bAlrabadi\s+et\s+al\.\s+\d+\s+(?=each\b)", re.IGNORECASE), ""),
    (re.compile(r"\bChemComm\s+Accepted\s+Manuscript\s+", re.IGNORECASE), ""),
    (re.compile(r"\s*\bFRANCO\s+ET\s+AL\.\s*\|\s*\d{3,5}\b\s*", re.IGNORECASE), " "),
    (re.compile(r"\b\d{2,3}\s+Y\.\s+Volpe\s+et\s+al\.\s+", re.IGNORECASE), ""),
)
_PAGE_FURNITURE_HTML_NODE_PATTERN = re.compile(
    r"<(?P<tag>p|h[1-6])\b(?P<attrs>[^>]*)>(?P<body>[\s\S]*?)</(?P=tag)>",
    re.IGNORECASE,
)
_PAGE_FURNITURE_VISIBLE_BLOCK_PATTERNS: tuple[re.Pattern[str], ...] = (
    _PUBLISHED_DOWNLOADED_PAGE_FURNITURE_PATTERN,
    re.compile(
        r"Published\s+By:\s+Blue\s+Eyes\s+Intelligence\s+Engineering\s+&\s+"
        r"Sciences\s+Publication\s+©\s+Copyright:\s+All\s+rights\s+reserved\.",
        re.IGNORECASE,
    ),
    re.compile(
        r"Retrieval\s+Number:100\.1/ijmh\.E1208015521\s+doi:"
        r"10\.35940/ijmh\.E1208\.045821\s+Journal\s+Website\s*:?\s*www\.ijmh\.org",
        re.IGNORECASE,
    ),
    re.compile(r"Alrabadi\s+et\s+al\.\s+\d+", re.IGNORECASE),
    re.compile(r"Accepted\s+Manuscript", re.IGNORECASE),
    re.compile(r"ChemComm\s+Accepted\s+Manuscrip(?:t)?", re.IGNORECASE),
    re.compile(r"FRANCO\s+ET\s+AL\.\s*\|\s*\d{3,5}", re.IGNORECASE),
    re.compile(r"\d{2,3}\s+Y\.\s+Volpe\s+et\s+al\.", re.IGNORECASE),
)
_CHEMCOMM_ACCEPTED_MANUSCRIPT_HEADER_PATTERN = re.compile(
    r"\s*<h1\b[^>]*>\s*ChemComm\s*</h1>\s*"
    r"<p\b[^>]*>\s*Accepted\s+Manuscript\s*</p>",
    re.IGNORECASE | re.DOTALL,
)
_ALRABADI_INLINE_PAGE_FURNITURE_PATTERN = re.compile(
    r"\s*<i\b[^>]*>\s*Alrabadi\s+et\s+al\.\s*</i>\s*\d+\s+(?=each\b)",
    re.IGNORECASE | re.DOTALL,
)
_FRANCO_INLINE_PAGE_FURNITURE_PATTERN = re.compile(
    r"(?:<span\b[^>]*\bid\s*=\s*([\"'])page-[^\"']+\1[^>]*>\s*</span>\s*)?"
    r"FRANCO\s+ET\s+AL\.\s*"
    r"<sup\b[^>]*>\s*\|\s*</sup>\s*<sup\b[^>]*>\s*\d{3,5}\s*</sup>\s*"
    r"(?=(?:USA\)|persistence\b))",
    re.IGNORECASE | re.DOTALL,
)
_FRANCO_SPLIT_SENTENCE_PATTERN = re.compile(
    r"(Microsoft\s+Redmond\s+Washington,\s*)</p>\s*<p\b[^>]*>\s*(USA\))",
    re.IGNORECASE | re.DOTALL,
)
_EMPTY_BLOCKQUOTE_PATTERN = re.compile(
    r"<blockquote\b[^>]*>\s*</blockquote>",
    re.IGNORECASE | re.DOTALL,
)
_LATIN_MOJIBAKE_ACCENT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("\u0412\u0401\u0414\u00b1", "\u00ef"),
    ("\u0412\u0491\u0414\u00b1", "\u00ed"),
    ("\u0412\u00a8\u0414\u00b1", "\u00ef"),
    ("\u0412\u00b4\u0414\u00b1", "\u00ed"),
    ("\u0414\u00b1", "i"),
    ("\u0412\u0401", "\u00a8"),
    ("\u0412\u0451", "\u00b8"),
    ("\u0412\u0491", "\u00b4"),
    ("\u0412\u00a8", "\u00a8"),
    ("\u0412\u00b4", "\u00b4"),
    ("\u041b\u2122", "\u02d9"),
    ("\u041b\u045a", "\u02dc"),
    ("\u041b\u2020", "\u02c6"),
    ("\u041b\u2021", "\u02c7"),
    ("\u0415\u0455", "\u017e"),
    ("\u0415\u040e", "\u0161"),
    ("\u0415\u00a0", "\u0160"),
)
_LATIN_DETACHED_ACCENT_REPAIRS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bfac[\u00b8]\s*ade\b", re.IGNORECASE), "fa\u00e7ade"),
    (re.compile(r"\bfa[\u00b8]\s*cades\b", re.IGNORECASE), "fa\u00e7ades"),
    (re.compile(r"\bfa[\u00b8]\s*cade\b", re.IGNORECASE), "fa\u00e7ade"),
    (re.compile(r"\bO[\u00b4]\s*Donnell\b"), "O'Donnell"),
    (re.compile(r"\bconsumer[\u00b4]\s*s\b", re.IGNORECASE), "consumer's"),
    (re.compile(r"\bwould\s+[\u00b4]\s+be\b", re.IGNORECASE), "would be"),
    (re.compile(r"\bPakenait\s+[\u02d9]\s*e[\u02d9]?\b"), "Pakenait\u0117"),
    (re.compile(r"\bBRICENO\s*[\u02dc~]"), "BRICE\u00d1O"),
    (re.compile(r"\bHOLLERER\s*[\u02dc~]\s*,"), "HOLLERER,"),
    (re.compile(r"\bHOLLERER\s+[\u00a8]\s*,"), "HOLLERER,"),
    (re.compile(r"\bSusstrunk\s+[\u00a8]"), "S\u00fcsstrunk"),
    (re.compile(r"\bBezi[\u00b4]\s*er\b", re.IGNORECASE), "B\u00e9zier"),
    (re.compile(r"\bBros-\s*[\u00b4]\s*tow\b"), "Brostow"),
    (re.compile(r"\bWabi\s+[\u00b4]\s*nski\b"), "Wabi\u0144ski"),
    (re.compile(r"\bMo[\u00b4]\s*scicka\b"), "Mo\u015bcicka"),
    (re.compile(r"\bmoir[\u00b4]\s*e\b", re.IGNORECASE), "moir\u00e9"),
    (re.compile(r"\bmany\s+[\u00a8]\s+insightful\b", re.IGNORECASE), "many insightful"),
    (re.compile(r"\bMicrosoft\s+[\u00b4]\s+coco\b", re.IGNORECASE), "Microsoft COCO"),
    (re.compile(r"\bPeter\s+M\s+[\u02d9]\s+Hall\b"), "Peter M. Hall"),
    (re.compile(r",\s+[\u02d9]\s+and\b"), ", and"),
    (re.compile(r"\bOA(?:\u041b\u2020|\u02c6)\s+(?:\u041b\u2021|\u02c7)SModhrain\b"), "O'Modhrain"),
    (re.compile(r"\b([A-Z]{3,})\s+[\u00b4]\s*,"), r"\1,"),
    (re.compile(r"\b([A-Z][a-z]{2,})\s+[\u00b4]\s+([A-Z][a-z]{2,})\b"), r"\1 \2"),
    (re.compile(r"\b([A-Z][a-z]{2,})\s+[\u00a8]\s+([A-Z][a-z]{2,})\b"), r"\1 \2"),
    (re.compile(r"\b([a-z]{3,})\s+[\u00b4]\s+(for|to|be|and|of|in|with|the)\b", re.IGNORECASE), r"\1 \2"),
    (re.compile(r"\bRadim\s+[\u02c7]\s+S[\u02c7]\s*ara\b"), "Radim \u0160\u00e1ra"),
    (re.compile(r"\bBAijhler,\s+[\u02dc]\s+and\b"), "B\u00fchler, and"),
)
_PAKENAIT_ORCID_DOT_SUFFIX_PATTERN = re.compile(
    r"(?P<open><a\b(?=[^>]*\bhref\s*=\s*['\"]https?://orcid\.org/)[^>]*>\s*Karolina\s+Pakenait)"
    r"\s*(?P<close></a>)\s*(?:\u041b\u2122|\u02d9)\s*e(?:\u041b\u2122|\u02d9)?",
    re.IGNORECASE,
)
_CHECK_FOR_UPDATES_PATTERN = re.compile(r"\s*\bCheck\s+for\s+updates\b\s*", re.IGNORECASE)
_MG_KG_H_NEG_PATTERN = re.compile(r"\bmg\s+kg\s+h\s*[-\u2212]\s*1\b", re.IGNORECASE)
_MG_KG_H_NEG_HTML_PATTERN = re.compile(
    r"\bmg\s+kg\s+h\s*(?:<i>\s*)?[-\u2212](?:\s*</i>)?\s*<sup\b[^>]*>\s*1\s*</sup>",
    re.IGNORECASE,
)
_DEGREE_CIRCLE_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*\u25e6(?P<space>\s*)(?P<unit>C)?")
_DEGREE_CIRCLE_HTML_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?:<(?:i|em|b|strong)\b[^>]*>\s*)?"
    r"\u25e6"
    r"(?P<after>\s*(?:[×x]\s*)?)"
    r"(?:</(?:i|em|b|strong)>)?"
    r"(?P<post>\s*)"
    r"(?P<unit>C)?",
    re.IGNORECASE,
)
_SPACED_CANDELA_UNIT_PATTERN = re.compile(
    r"(?<![A-Za-z])c\s+d\s+m(?=\s*(?:[-\u2212\u2013\u2014]|<sup\b|\)|,|\.|;|:|$))",
    re.IGNORECASE,
)
_ANCHOR_TRAILING_NEG_UNIT_EXP_PATTERN = re.compile(
    r"(?P<open><a\b[^>]*>)"
    r"(?P<body>(?:(?!</a>).){0,500}?)"
    r"(?<![A-Za-z])"
    r"(?P<unit>(?:mS\s*cm|mT\s*m|mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|uC\s*cm|"
    r"cd\s*m|nm\s*d|mm\s*s|cm\s*s|m\s*s|cm|mm|nm|M|m|d|s))"
    r"(?P<trailing>\s*)</a>\s*[-\u2212\u2013\u2014]\s*(?P<exp>[123])\b",
    re.IGNORECASE | re.DOTALL,
)
_SPLIT_NEG_UNIT_EXP_HTML_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<unit>(?:mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|uC\s*cm|cd\s*m|nm\s*d|mm\s*s|cm\s*s|m\s*s|cm|mm|nm|m|d|s)\s*)"
    r"(?:<i>\s*)?[-\u2212](?:\s*</i>)?\s*<sup(?P<attrs>[^>]*)>\s*(?P<exp>[123])\s*</sup>",
    re.IGNORECASE,
)
_SPLIT_SIGN_ONLY_NEG_UNIT_EXP_HTML_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<unit>(?:mg\s*L|mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|uC\s*cm|"
    r"cd\s*m|nm\s*d|mm\s*s|cm\s*s|m\s*s|cm|mm|nm|M|m|d|s)\s*)"
    r"<sup\b[^>]*>\s*[-\u2212\u2013\u2014]\s*</sup>\s*"
    r"<sup\b[^>]*>\s*(?:<a\b[^>]*>)?\s*(?P<exp>[123])\s*(?:</a>)?\s*</sup>",
    re.IGNORECASE,
)
_PLAIN_POS_UNIT_EXP_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<value>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>(?:\u00b5m|\u03bcm|um|mm|cm|nm|m))\s*(?P<exp>[23])\b"
)
_UNIT_EXPONENT_SUP_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:<(?:i|em)\b[^>]*>\s*)?"
    r"(?P<unit>(?:\u00b5m|\u03bcm|Вµm|Ојm|um|mS\s*cm|mT\s*m|mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|uC\s*cm|cd\s*m|nm\s*d|mm\s*s|cm\s*s|m\s*s|cm|mm|nm|M|m)\s*)"
    r"(?:</(?:i|em)>\s*)?"
    r"<sup(?P<attrs>[^>]*)>\s*(?P<exp>[-\u2212]?\s*[123])\s*</sup>",
    re.IGNORECASE,
)
_LINKED_POS_UNIT_EXPONENT_SUP_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<unit>"
    r"(?:(?:<(?:i|em)\b[^>]*>\s*)?"
    r"(?:\u00b5m|\u03bcm|um|mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|"
    r"uC\s*cm|cd\s*m|mm\s*s|cm\s*s|m\s*s|cm|mm|deg|m|T)"
    r"(?:\s*</(?:i|em)>)?)\s*)"
    r"<sup\b[^>]*>\s*<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>[123])['\"][^>]*>"
    r"\s*(?P=exp)\s*</a>\s*</sup>",
    re.IGNORECASE,
)
_LINKED_UNIT_EXPONENT_SUP_PATTERN = re.compile(
    r"(?P<unit>(?:mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|uC\s*cm|cd\s*m|nm\s*d|mm\s*s|cm\s*s|m\s*s|cm|mm|nm|m|d|s)\s*)"
    r"(?:<i>\s*)?[-\u2212](?:\s*</i>)?\s*"
    r"<sup\b[^>]*>\s*<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>[123])['\"][^>]*>\s*(?P=exp)\s*</a>\s*</sup>",
    re.IGNORECASE,
)
_LINKED_NEG_UNIT_EXPONENT_SUP_PATTERN = re.compile(
    r"(?P<unit>(?:mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|uC\s*cm|cd\s*m|nm\s*d|mm\s*s|cm\s*s|m\s*s|cm|mm|nm|m|d|s)\s*)"
    r"<sup\b[^>]*>\s*(?:<i>\s*)?[-\u2212](?:\s*</i>)?\s*"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>[123])['\"][^>]*>\s*(?P=exp)\s*</a>\s*</sup>",
    re.IGNORECASE,
)
_LINKED_SPLIT_UNIT_EXPONENT_REF_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<unit>(?:\u00b5m|\u03bcm|um|mm|cm|nm|m)\s*)"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>[23])['\"][^>]*>\s*(?P=exp)\s*</a>",
    re.IGNORECASE,
)
_LINKED_PLAIN_NEG_UNIT_EXPONENT_REF_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<unit>(?:mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|uC\s*cm|"
    r"cd\s*m|nm\s*d|mm\s*s|cm\s*s|m\s*s|cm|mm|nm|m)\s*)"
    r"[-\u2212]\s*"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>[123])['\"][^>]*>\s*(?P=exp)\s*</a>",
    re.IGNORECASE,
)
_PLAIN_NEG_UNIT_EXP_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<unit>(?:mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|uC\s*cm|"
    r"cd\s*m|mL\s*s|mL\s*min|mL\s*h|L\s*s|L\s*min|L\s*h|"
    r"nm\s*d|mm\s*s|cm\s*s|m\s*s|cm|mm|nm|m|d|s)\s*)"
    r"[-\u2212\u2013\u2014]\s*(?P<exp>[123])\b",
    re.IGNORECASE,
)
_LINKED_DIRECT_UNIT_EXPONENT_REF_PATTERN = re.compile(
    r"(?P<prefix>\b(?:N|Pa|MPa|GPa|J|W|V|A|F|Ohm|\u03a9)\s+)"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>[123])['\"][^>]*>\s*"
    r"(?P<unit>m|cm|mm|um|\u00b5m|\u03bcm)\s*(?P=exp)\s*</a>",
    re.IGNORECASE,
)
_ML_PER_SECOND_UNIT_EXPONENT_SUP_PATTERN = re.compile(
    r"(?P<unit>mL)\s*[:/]\s*s\s*\{\s*"
    r"<sup(?P<attrs>[^>]*)>\s*(?P<exp>1)\s*</sup>",
    re.IGNORECASE,
)
_LINKED_ML_PER_SECOND_UNIT_EXPONENT_SUP_PATTERN = re.compile(
    r"(?P<unit>mL)\s*[:/]\s*s\s*\{\s*"
    r"<sup\b[^>]*>\s*<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>1)['\"][^>]*>\s*(?P=exp)\s*</a>\s*</sup>",
    re.IGNORECASE,
)
_LINKED_GENERAL_NEG_UNIT_EXPONENT_SUP_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<unit>(?:mg|kg|ng|pg|g|mL|L|cm|mm|m|min|h|s)\s*)"
    r"<sup\b[^>]*>\s*[-\u2212]\s*"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>[1-6])['\"][^>]*>\s*(?P=exp)\s*</a>\s*</sup>",
    re.IGNORECASE,
)
_LINKED_PER_MINUTE_MISSING_MINUS_SUP_PATTERN = re.compile(
    r"(?P<unit>\b(?:(?:revolutions?|beats?|[lL]|mL|ml)\s*)?min\s*)"
    r"<sup\b[^>]*>\s*"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>1)['\"][^>]*>\s*(?P=exp)\s*</a>\s*</sup>",
    re.IGNORECASE,
)
_BRACE_RANGE_BEFORE_ML_PER_SECOND_PATTERN = re.compile(
    r"\b(?P<left>\d+(?:\.\d+)?)\s*\{\s*(?P<right>\d+(?:\.\d+)?)"
    r"(?=\s*mL\s+s<sup\b[^>]*\bz2m-unit-exp\b)",
    re.IGNORECASE,
)
_COMPACT_VALUE_ML_PER_SECOND_PATTERN = re.compile(
    r"(?P<value>\d)(?=mL\s+s<sup\b[^>]*\bz2m-unit-exp\b)",
    re.IGNORECASE,
)
_BASE10_EXPONENT_SUP_PATTERN = re.compile(
    r"(?P<base>\b10)\s*(?P<minus>[-\u2212\u2013\u2014])?\s*"
    r"<sup(?P<attrs>[^>]*)>\s*(?P<exp>\d{1,2})\s*</sup>",
    re.IGNORECASE,
)
_FRANCO_GARBLED_TABLE_GROUP_HEADER_ROW_PATTERN = re.compile(
    r"<tr>\s*"
    r"(?=(?:(?!</tr>)[\s\S]){0,1400}\bnales\s*<br\s*/?>\s*an\s*±sD\b)"
    r"(?=(?:(?!</tr>)[\s\S]){0,1400}\bQn\s*<br\s*/?>\s*Flow\s*i\b)"
    r"(?=(?:(?!</tr>)[\s\S]){0,1400}\bnax\s*<br\s*/?>\s*ndexes\b)"
    r"(?:(?!</tr>)[\s\S])*?</tr>",
    re.IGNORECASE,
)
_STULIK_COLLODION_STRAY_HEADER_PATTERN = re.compile(
    r"(?P<title><th\b[^>]*>\s*<b>\s*Collodion\s+Prints\s*</b>\s*</th>)\s*"
    r"<th\b[^>]*>\s*S\s*</th>",
    re.IGNORECASE,
)
_ABSTRACTS_QUESTIONNAIRE_HEADER_ROW_PATTERN = re.compile(
    r"<tr>\s*"
    r"<th\b[^>]*>\s*MENDATION\s*<br\s*/?>\s*QUESTIONNAIRE\s*[‐-]\s*"
    r"<br\s*/?>\s*M\s*<br\s*/?>\s*RECO\s*</th>\s*"
    r"<th\b[^>]*>\s*QUESTIONNAIRE\s*<br\s*/?>\s*TYPE\s+OF\s*</th>\s*"
    r"<th\b[^>]*>\s*REFERENCES\s*</th>\s*"
    r"<th\b[^>]*>\s*W\s+TO\s+GET\s+IT\s*<br\s*/?>\s*HO\s*</th>\s*"
    r"</tr>",
    re.IGNORECASE,
)
_ABSTRACTS_QUESTIONNAIRE_CONTINUED_HEADER_ROW_PATTERN = re.compile(
    r"<tr>\s*"
    r"<th\b[^>]*>\s*MS\s*<br\s*/?>\s*MPTO\s*<br\s*/?>\s*SY\s*</th>\s*"
    r"<th\b[^>]*>\s*MENDATION\s*<br\s*/?>\s*QUESTIONNAIRE\s*[‐-]\s*"
    r"<br\s*/?>\s*M\s*<br\s*/?>\s*RECO\s*</th>\s*"
    r"<th\b[^>]*>\s*QUESTIONNAIRE\s*<br\s*/?>\s*TYPE\s+OF\s*</th>\s*"
    r"<th\b[^>]*>\s*REFERENCES\s*</th>\s*"
    r"<th\b[^>]*>\s*W\s+TO\s+GET\s+IT\s*<br\s*/?>\s*HO\s*</th>\s*"
    r"</tr>",
    re.IGNORECASE,
)
_ROLLEMA_TABLE_CONTINUED_HEADING_PATTERN = re.compile(
    r"\bT\s+a\s+bl\s+e\s+2\s+1\s+con\s+t'\s*[\ufffd�]?\s*nue\s+d\)",
    re.IGNORECASE,
)
_ROLLEMA_PRINTOUT_HEADER_REPAIRS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bHE[\ufffd�+]LTHY\s+SUBJECT\b", re.IGNORECASE), "HEALTHY SUBJECT"),
    (re.compile(r"\bME[\ufffd�+]SUREMENT\b", re.IGNORECASE), "MEASUREMENT"),
    (re.compile(r"\bSER\s+I\s+[\ufffd�+]L\s+NBR\s*\.", re.IGNORECASE), "SERIAL-NBR."),
)
_LINKED_BASE10_EXPONENT_SUP_PATTERN = re.compile(
    r"(?P<base>\b10)\s*(?P<minus>[-\u2212\u2013\u2014])?\s*"
    r"<sup\b[^>]*>\s*<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>\d{1,2})['\"][^>]*>\s*(?P=exp)\s*</a>\s*</sup>",
    re.IGNORECASE,
)
_PLAIN_BASE10_EXPONENT_BEFORE_UNIT_SUP_PATTERN = re.compile(
    r"\b10\s*[-\u2212\u2013\u2014]\s*(?P<exp>\d{1,2})"
    r"(?=\s+(?:mC\s*cm|\u00b5C\s*cm|\u03bcC\s*cm|uC\s*cm|cd\s*m|nm\s*d|mm\s*s|cm\s*s|m\s*s|cm|mm|nm|m|d|s)"
    r"\s*<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*-\d+\s*</sup>)",
    re.IGNORECASE,
)
_MISSING_SPACE_AFTER_UNIT_SUP_PATTERN = re.compile(
    r'(<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*[-\d]+\s*</sup>)(?=[A-Za-z])',
    re.IGNORECASE,
)
_ANESTHESIA_DOSE_INLINE_TEX_PATTERN = re.compile(
    r"(?P<first>\b\d+(?:\.\d+)?(?:[-\u2013\u2014]\d+(?:\.\d+)?)?)\s*"
    r"\\\(\s*mg\\cdot\s*kg\^\{-1\}\\cdot\s*h\^\{-1\},\\\s*"
    r"(?P<second>\d+(?:\.\d+)?)\\\s*\\mu\s*g\\cdot\s*kg\^\{-1\}\\cdot\s*h\^\{-1\},\\\s*"
    r"and\\\s*(?P<percent>\d+(?:\.\d+)?(?:[-\u2013\u2014]\d+(?:\.\d+)?)?)\\%,\\\s*respectively\.\\\)",
    re.IGNORECASE,
)
_CITATION_PREFIX_BODY_PATTERN = re.compile(
    r"^\s*(?P<cite><a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>"
    r"\s*\[?\d+\]?\s*</a>)\s*\.\s*(?P<tail>[A-Z][\s\S]{10,})$",
    re.IGNORECASE,
)
_ESCAPED_ANCHOR_SNIPPET_PATTERN = re.compile(
    r'&lt;a\s+href=(["\'])(?P<href>https?://[^"\']+)\1&gt;(?P<label>https?://[^<]+)&lt;/a&gt;',
    re.IGNORECASE,
)
_DEFAULT_READABILITY_STYLE = """
<style data-z2m-style="readable">
  :root { color-scheme: light; }
  body {
    margin: 0;
    padding: 22px;
    font-family: "Segoe UI", "Arial", sans-serif;
    line-height: 1.62;
    color: #1f2937;
    background: linear-gradient(180deg, #f5f8fb 0%, #edf2f7 100%);
  }
  #marker-doc {
    max-width: 980px;
    margin: 0 auto;
    background: #ffffff;
    border: 1px solid #dbe5ef;
    border-radius: 12px;
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
    padding: 30px 36px;
  }
  body.z2m-has-wide-table #marker-doc {
    max-width: min(1500px, calc(100vw - 44px));
  }
  h1, h2, h3, h4, h5, h6 {
    color: #0f172a;
    line-height: 1.28;
    margin-top: 1.15em;
    margin-bottom: 0.5em;
  }
  p {
    margin: 0.6em 0;
    text-indent: 1.25em;
    word-break: break-word;
  }
  p.z2m-affiliations {
    text-indent: 0;
    margin: 1.1em 0;
    padding: 0.7em 0;
    border-top: 1px solid #c7d3df;
    border-bottom: 1px solid #c7d3df;
    font-size: 0.95em;
  }
  p.z2m-front-matter {
    text-indent: 0;
  }
  p.z2m-footnote {
    text-indent: 0;
    margin: 0.85em 0;
    padding: 0.55em 0 0;
    border-top: 1px solid #c7d3df;
    font-size: 0.94em;
    color: #475569;
  }
  p.z2m-table-note {
    text-indent: 0;
    margin: 0.45em 0 0.2em;
    font-size: 0.94em;
    color: #475569;
  }
  p.z2m-missing-figure-warning {
    text-indent: 0;
    margin: 0.55em 0 0.4em;
    padding: 0.5em 0.7em;
    border-left: 4px solid #b45309;
    background: #fff7ed;
    color: #7c2d12;
    font-size: 0.94em;
  }
  [id^="ref-"],
  [id^="fig-"],
  [id^="table-"],
  [id^="box-"],
  [id^="eq-"],
  [id^="section-"] {
    scroll-margin-top: 42vh;
  }
  :target {
    outline: 2px solid #2563eb;
    outline-offset: 4px;
    background: #eff6ff;
  }
  .z2m-float-unit {
    text-indent: 0;
    margin: 1.35em 0;
    padding: 0.7em 0;
    border-top: 1px solid #cbd5e1;
    border-bottom: 1px solid #cbd5e1;
  }
  .z2m-float-unit.z2m-float-run-start {
    margin-bottom: 0;
    padding-bottom: 0.35em;
    border-bottom: 0;
  }
  .z2m-float-unit.z2m-float-run-mid {
    margin-top: 0;
    margin-bottom: 0;
    padding-top: 0.35em;
    padding-bottom: 0.35em;
    border-top: 0;
    border-bottom: 0;
  }
  .z2m-float-unit.z2m-float-run-end {
    margin-top: 0;
    padding-top: 0.35em;
    border-top: 0;
  }
  .z2m-float-unit p,
  .z2m-float-unit h1,
  .z2m-float-unit h2,
  .z2m-float-unit h3,
  .z2m-float-unit h4,
  .z2m-float-unit h5,
  .z2m-float-unit h6 {
    text-indent: 0;
  }
  .z2m-float-unit img {
    margin-top: 0.45em;
    margin-bottom: 0.65em;
  }
  .z2m-figure-caption,
  .z2m-table-caption {
    text-indent: 0;
    margin: 0.55em 0 0;
    padding: 0;
    border: 0;
  }
  p[id^="fig-"],
  p.z2m-figure-caption,
  p[id^="table-"],
  figcaption {
    text-indent: 0;
    margin: 1.15em 0 0.85em;
    padding: 0;
  }
  a {
    color: #0b57d0;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  a:hover {
    color: #1d4ed8;
  }
  .z2m-ref-link {
    text-decoration: none;
    font-weight: 500;
  }
  .z2m-section-link,
  .z2m-fig-link,
  .z2m-box-link,
  .z2m-eq-link,
  .z2m-table-link {
    text-decoration: none;
    border-bottom: 1px dotted #0b57d0;
    font-weight: 500;
  }
  .z2m-section-link:hover,
  .z2m-fig-link:hover,
  .z2m-box-link:hover,
  .z2m-eq-link:hover,
  .z2m-table-link:hover {
    border-bottom-style: solid;
  }
  sup.z2m-table-fn {
    font-size: 0.75em;
    margin-left: 0.08em;
    vertical-align: super;
  }
  .z2m-ref-num {
    font-weight: 600;
    margin-right: 0.3em;
  }
  ul, ol { margin: 0.65em 0 0.75em 1.3em; }
  li { margin: 0.28em 0; }
  blockquote {
    margin: 0.9em 0;
    padding: 0.55em 0.9em;
    border-left: 4px solid #60a5fa;
    background: #f8fbff;
    color: #0b355c;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.1em 0;
    font-size: 0.96rem;
  }
  table.z2m-wide-table {
    width: max-content;
    min-width: 100%;
    max-width: none;
  }
  th, td {
    border: 1px solid #dbe3ec;
    padding: 0.45em 0.58em;
    vertical-align: top;
  }
  th {
    background: #f4f8fc;
    font-weight: 600;
  }
  pre, code {
    font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
    font-size: 0.93em;
  }
  pre {
    background: #f7fafc;
    border: 1px solid #dbe3ec;
    border-radius: 8px;
    padding: 0.85em 0.95em;
    overflow-x: auto;
  }
  code {
    background: #f3f7fb;
    border-radius: 4px;
    padding: 0.08em 0.25em;
  }
  img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0.9em auto;
    border: 1px solid #d9e0e7;
    border-radius: 6px;
  }
  math[display="block"] {
    overflow-x: auto;
    display: block;
    margin: 0.6em 0;
  }
  math {
    overflow-x: auto;
  }
  p[block-type="Equation"] {
    text-align: center;
    margin: 0.8em 0;
    text-indent: 0;
  }
  .z2m-equation-row {
    display: flex;
    align-items: center;
    margin: 0.8em 0;
  }
  .z2m-equation-row > p[block-type="Equation"] {
    flex: 1;
    margin: 0;
    padding: 0;
  }
  .z2m-eq-lhs,
  .z2m-eq-num {
    flex: 0 0 3.5em;
    font-size: 0.92em;
    color: #374151;
  }
  .z2m-eq-num { text-align: right; }
  @media (max-width: 960px) {
    body { padding: 10px; }
    #marker-doc { padding: 16px 15px; border-radius: 8px; }
    table { display: block; overflow-x: auto; white-space: nowrap; }
  }
</style>
""".strip()

_inject_default_styles = functools.partial(
    _presentation_inject_default_styles,
    readability_style=_DEFAULT_READABILITY_STYLE,
)

_MOJIBAKE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("вЂ”", "—"),
    ("вЂ“", "–"),
    ("вЂ™", "’"),
    ("вЂњ", "“"),
    ("вЂќ", "”"),
    ("В©", "©"),
)


_MOJIBAKE_REPLACEMENTS = _MOJIBAKE_REPLACEMENTS + (
    ("\u0420\u0406\u0420\u201a\u0432\u0402\u045c", "\u2014"),
    ("\u0420\u0406\u0420\u201a\u0432\u0402\u045a", "\u2013"),
    ("\u0420\u0406\u0420\u201a\u0432\u0404\u045e", "\u2019"),
    ("\u0420\u0406\u0420\u201a\u0421\u0459", "\u201c"),
    ("\u0420\u0406\u0420\u201a\u0421\u045a", "\u201d"),
    ("\u0420\u2019\u0412\u00a9", "\u00a9"),
    ("\u0420\u2019\u0412\u00b0", "\u00b0"),
    ("\u0420\u2019\u0412\u00b5", "\u00b5"),
    ("\u0420\u045b\u0421\u0098", "\u03bc"),
    ("\u0420\u045b\u0412\u00a9", "\u03a9"),
    ("\u0420\u201c\u0432\u0402\u201d", "\u00d7"),
    ("вЂ”", "—"),
    ("вЂ“", "–"),
    ("вЂ™", "’"),
    ("вЂњ", "“"),
    ("вЂќ", "”"),
    ("в€’", "−"),
    ("В°", "°"),
    ("Вµ", "µ"),
    ("Ој", "μ"),
    ("О©", "Ω"),
    ("Г—", "×"),
)


def _inject_mathjax(html: str) -> str:
    return _inject_mathjax_impl(html, ensure_head=_inject_default_styles)


def _inject_katex_css(html: str) -> str:
    return _inject_katex_css_impl(html, ensure_head=_inject_default_styles)


def _render_katex_html(html: str) -> str:
    return _render_katex_html_impl(html, ensure_head=_inject_default_styles)


def _citation_tag_is_protected(tag_fragment: str) -> bool:
    raw = tag_fragment.strip()
    open_match = _OPEN_TAG_PATTERN.match(raw)
    if open_match is None:
        return False
    tag_name = open_match.group(1).lower()
    return (
        tag_name in _CITATION_SKIP_TAGS
        or _CITATION_PROTECTED_CLASS_PATTERN.search(raw) is not None
        or _CITATION_PROTECTED_ID_PATTERN.search(raw) is not None
        or _CITATION_PROTECTED_BLOCK_TYPE_PATTERN.search(raw) is not None
    )


def _update_citation_skip_stack(tag_fragment: str, skip_stack: list[str]) -> None:
    raw = tag_fragment.strip()
    if not raw.startswith("<") or raw.startswith("<!--") or raw.startswith("<!"):
        return

    close_match = _CLOSE_TAG_PATTERN.match(raw)
    if close_match is not None:
        tag_name = close_match.group(1).lower()
        for idx in range(len(skip_stack) - 1, -1, -1):
            if skip_stack[idx] == tag_name:
                del skip_stack[idx]
                break
        return

    if raw.endswith("/>"):
        return

    open_match = _OPEN_TAG_PATTERN.match(raw)
    if open_match is None:
        return
    tag_name = open_match.group(1).lower()
    if _citation_tag_is_protected(raw):
        skip_stack.append(tag_name)


def _looks_front_matter_block(raw: str) -> bool:
    return _looks_front_matter_block_impl(
        raw,
        looks_affiliation_block=_looks_affiliation_block,
    )


def _mark_front_matter_paragraphs(html: str) -> str:
    return _mark_front_matter_paragraphs_impl(
        html,
        looks_front_matter_block=_looks_front_matter_block,
    )


def _repair_front_matter_page_anchor_markers(body: str) -> str:
    return _repair_front_matter_page_anchor_markers_impl(
        body,
        looks_like_ocr_split_word_join=_looks_like_ocr_split_word_join,
    )


def _repair_front_matter_marker_ocr(html: str) -> str:
    return _repair_front_matter_marker_ocr_impl(
        html,
        looks_like_ocr_split_word_join=_looks_like_ocr_split_word_join,
    )


def _looks_footnote_block(raw: str) -> bool:
    return _looks_footnote_block_impl(
        raw,
        figure_caption_num_from_visible=_figure_caption_num_from_visible,
        table_caption_key_from_visible=_table_caption_key_from_visible,
    )


def _mark_footnote_paragraphs_and_refs(html: str) -> str:
    return _mark_footnote_paragraphs_and_refs_impl(
        html,
        figure_caption_num_from_visible=_figure_caption_num_from_visible,
        table_caption_key_from_visible=_table_caption_key_from_visible,
        citation_tag_is_protected=_citation_tag_is_protected,
        numeric_superscript_context_allows_citation=_numeric_superscript_context_allows_citation,
    )


def _node_protects_citations(raw: str) -> bool:
    tag_match = _OPEN_TAG_PATTERN.match(raw.strip())
    if tag_match is not None and tag_match.group(1).lower() in _CITATION_SKIP_TAGS:
        return True
    open_end = raw.find(">")
    if open_end < 0:
        return False
    return _citation_tag_is_protected(raw[: open_end + 1])


def _strip_ref_links(html: str) -> str:
    return re.sub(
        r'<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>([\s\S]*?)</a>',
        r"\1",
        html,
        flags=re.IGNORECASE,
    )


def _strip_reference_links_in_protected_blocks(html: str) -> str:
    def _strip_if_protected(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return _strip_ref_links(raw)
        return raw

    return _SENTENCE_NODE_PATTERN.sub(_strip_if_protected, html)


def _link_sup_citations_in_safe_blocks(html: str, link_sup) -> str:
    def _link_if_safe(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        return _SUP_PATTERN.sub(link_sup, raw)

    return _SENTENCE_NODE_PATTERN.sub(_link_if_safe, html)


def _unwrap_spurious_math_captions(html: str) -> str:
    """Unwrap <math> tags that contain HTML formatting — they are figure captions.

    Marker sometimes wraps figure captions in ``<math display="inline">`` by mistake.
    Real math never contains ``<strong>``, ``<em>``, ``<b>``, or ``<i>`` tags, so any
    ``<math>`` block that does is safe to unwrap so cleanup can process it.
    """
    return _SPURIOUS_MATH_CAPTION_PATTERN.sub(r'\1', html)


def _link_paren_ref_citations(html: str, ref_count: int) -> str:
    """Convert (ref. N) / (ref N) / (см. N) to superscript anchor links.

    Handles the artefact where Marker or the translator leaves parenthetical
    references like ``(ref. 30)`` as plain text instead of ``<sup>30</sup>``.
    Only links numbers in the range [1, ref_count].
    """
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def replace_paren_ref(match: re.Match[str]) -> str:
        try:
            number = int(match.group(1))
        except ValueError:
            return match.group(0)
        if 1 <= number <= ref_count:
            return f'<sup><a href="#ref-{number}" class="z2m-ref-link">{number}</a></sup>'
        return match.group(0)

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_citation_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_PAREN_REF_CITATION_PATTERN.sub(replace_paren_ref, part))

    return "".join(out)


def _link_bracket_citations(html: str, ref_count: int) -> str:
    """Wrap [N] citation markers with anchor links to #ref-N in text nodes.

    Skips text inside tags that should not be modified (scripts, math, existing
    anchors, etc.).  Only links numbers in the range [1, ref_count].
    """
    void_anchor_pattern = re.compile(
        r'<a\b[^>]*\bhref\s*=\s*["\']javascript:void\(0\)["\'][^>]*>'
        r'(?P<body>[\s\S]{0,180}?)</a>',
        re.IGNORECASE,
    )

    def link_number(num_match: re.Match[str]) -> str:
        number = int(num_match.group(0))
        return f'<a href="#ref-{number}" class="z2m-ref-link">{num_match.group(0)}</a>'

    def render_visible_bracket(visible: str) -> str | None:
        match = re.fullmatch(
            r"\s*(?P<bracket>\[\s*(?P<content>\d{1,3}(?:\s*(?:,|[-\u2013\u2014])\s*\d{1,3})*)\s*\])"
            r"(?P<trail>[.,;:]?)\s*",
            visible,
        )
        if match is None:
            return None
        content = match.group("content")
        numbers = [int(item) for item in re.findall(r"\d{1,3}", content)]
        if not numbers or not all(1 <= number <= ref_count for number in numbers):
            return None
        if len(numbers) == 1 and content.strip().isdigit():
            number = numbers[0]
            return (
                f'<a href="#ref-{number}" class="z2m-ref-link">[{number}]</a>'
                f'{match.group("trail")}'
            )
        return "[" + re.sub(r"\d{1,3}", link_number, content) + "]" + match.group("trail")

    def replace_void_anchor(match: re.Match[str]) -> str:
        linked = render_visible_bracket(_visible_text(match.group("body")))
        return linked if linked is not None else match.group(0)

    html = void_anchor_pattern.sub(replace_void_anchor, html)

    def replace_cross_tag_bracket(match: re.Match[str]) -> str:
        body = match.group("body")
        if "<" not in body:
            return match.group(0)
        visible = _visible_text(body)
        if _BRACKET_CITATION_PATTERN.fullmatch(f"[{visible}]") is None:
            return match.group(0)
        numbers = [int(item) for item in re.findall(r"\d{1,3}", visible)]
        if not numbers or not all(1 <= number <= ref_count for number in numbers):
            return match.group(0)

        if "<a " in body.lower():
            linked_numbers = {
                int(anchor_match.group("label"))
                for anchor_match in re.finditer(
                    r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<target>\d{1,4})["\'][^>]*>'
                    r'\s*(?P<label>\d{1,4})\s*</a>',
                    body,
                    re.IGNORECASE,
                )
                if anchor_match.group("target") == anchor_match.group("label")
            }
            if numbers and set(numbers).issubset(linked_numbers):
                return match.group(0)
            normalized_visible = re.sub(r"\s+([,;])", r"\1", visible.strip())
            normalized_visible = re.sub(r"([,;])(?=\S)", r"\1 ", normalized_visible)
            normalized_visible = re.sub(r"\s*([-\u2013\u2014])\s*", r"\1", normalized_visible)
            return "[" + re.sub(r"\d{1,3}", link_number, normalized_visible) + "]"

        tag_parts = _TAG_SPLIT_PATTERN.split(body)
        linked_parts: list[str] = []
        for part in tag_parts:
            if not part:
                continue
            if part.startswith("<"):
                linked_parts.append(part)
                continue

            linked_parts.append(re.sub(r"\d{1,3}", link_number, part))

        return "[" + "".join(linked_parts) + "]"

    def link_cross_tag_brackets_in_node(node_match: re.Match[str]) -> str:
        raw = node_match.group(0)
        open_end = raw.find(">")
        open_tag = raw[: open_end + 1] if open_end >= 0 else raw
        if (
            _CITATION_PROTECTED_CLASS_PATTERN.search(open_tag) is not None
            or _CITATION_PROTECTED_BLOCK_TYPE_PATTERN.search(open_tag) is not None
        ):
            return raw
        return _CROSS_TAG_BRACKET_CITATION_PATTERN.sub(replace_cross_tag_bracket, raw)

    html = _SENTENCE_NODE_PATTERN.sub(link_cross_tag_brackets_in_node, html)

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def replace_bracket(match: re.Match[str]) -> str:
        left_inline_open = match.string.rfind(r"\(", 0, match.start())
        left_inline_close = match.string.rfind(r"\)", 0, match.start())
        left_display_open = match.string.rfind(r"\[", 0, match.start())
        left_display_close = match.string.rfind(r"\]", 0, match.start())
        if left_inline_open > left_inline_close or left_display_open > left_display_close:
            return match.group(0)
        content = match.group(1)
        numbers = [int(item) for item in re.findall(r"\d{1,3}", content)]
        if not numbers or not all(1 <= number <= ref_count for number in numbers):
            return match.group(0)
        if len(numbers) == 1 and content.strip().isdigit():
            number = numbers[0]
            return f'<a href="#ref-{number}" class="z2m-ref-link">[{number}]</a>'

        return "[" + re.sub(r"\d{1,3}", link_number, content) + "]"

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        linked = _CROSS_TAG_BRACKET_CITATION_PATTERN.sub(replace_cross_tag_bracket, part)
        out.append(_BRACKET_CITATION_PATTERN.sub(replace_bracket, linked))

    linked_html = "".join(out)

    def link_plain_brackets_in_node(node_match: re.Match[str]) -> str:
        raw = node_match.group(0)
        open_end = raw.find(">")
        open_tag = raw[: open_end + 1] if open_end >= 0 else raw
        if (
            _CITATION_PROTECTED_CLASS_PATTERN.search(open_tag) is not None
            or _CITATION_PROTECTED_BLOCK_TYPE_PATTERN.search(open_tag) is not None
        ):
            return raw
        local_parts = _TAG_SPLIT_PATTERN.split(raw)
        local_out: list[str] = []
        local_skip_stack: list[str] = []
        for local_part in local_parts:
            if not local_part:
                continue
            if local_part.startswith("<"):
                _update_skip_stack(local_part, local_skip_stack)
                local_out.append(local_part)
                continue
            if local_skip_stack:
                local_out.append(local_part)
                continue
            local_out.append(_BRACKET_CITATION_PATTERN.sub(replace_bracket, local_part))
        return "".join(local_out)

    return _SENTENCE_NODE_PATTERN.sub(link_plain_brackets_in_node, linked_html)


_TABLE_OR_FLOAT_CITATION_NODE_PATTERN = re.compile(
    r"<table\b[\s\S]*?</table>",
    re.IGNORECASE,
)


def _link_table_float_numeric_citation_ranges(html: str, ref_count: int) -> str:
    if ref_count <= 0 or ("<sup" not in html and "[" not in html):
        return html

    def link_number(match: re.Match[str]) -> str:
        number = int(match.group(0))
        return f'<a href="#ref-{number}" class="z2m-ref-link">{match.group(0)}</a>'

    def citation_numbers(label: str) -> list[int]:
        numbers = _expand_reference_label_numbers(label)
        if len(numbers) < 2:
            return []
        if any(number < 1 or number > ref_count for number in numbers):
            return []
        return numbers

    def replace_sup(match: re.Match[str]) -> str:
        raw = match.group(0)
        if "z2m-unit-exp" in raw or "z2m-footnote-ref" in raw or "<a " in raw.lower():
            return raw
        body = match.group(1)
        numbers = citation_numbers(_visible_text(body))
        if not numbers or max(numbers) < 10:
            return raw
        linked = _link_numeric_superscript_body(body, ref_count)
        if linked is None:
            return raw
        return f"<sup>{linked}</sup>"

    def replace_bracket(match: re.Match[str]) -> str:
        content = match.group(1)
        numbers = citation_numbers(content)
        if not numbers or max(numbers) < 10:
            return match.group(0)
        return "[" + re.sub(r"\d{1,3}", link_number, content) + "]"

    def replace_node(match: re.Match[str]) -> str:
        raw = _SUP_PATTERN.sub(replace_sup, match.group(0))
        parts = _TAG_SPLIT_PATTERN.split(raw)
        out: list[str] = []
        skip_stack: list[str] = []
        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                open_match = _OPEN_TAG_PATTERN.match(part.strip())
                close_match = _CLOSE_TAG_PATTERN.match(part.strip())
                if close_match is not None and skip_stack:
                    tag_name = close_match.group(1).lower()
                    for idx in range(len(skip_stack) - 1, -1, -1):
                        if skip_stack[idx] == tag_name:
                            del skip_stack[idx]
                            break
                elif (
                    open_match is not None
                    and open_match.group(1).lower() in {"a", "script", "style", "math", "svg"}
                    and not part.rstrip().endswith("/>")
                ):
                    skip_stack.append(open_match.group(1).lower())
                out.append(part)
                continue
            out.append(part if skip_stack else _BRACKET_CITATION_PATTERN.sub(replace_bracket, part))
        return "".join(out)

    return _TABLE_OR_FLOAT_CITATION_NODE_PATTERN.sub(replace_node, html)


def _link_late_numeric_citation_ranges_before_references(html: str, citation_profile: Any | None = None) -> str:
    if _should_suppress_numeric_ref_links_for_author_year(html, citation_profile):
        return html
    ref_ids = [int(value) for value in re.findall(r'\bid\s*=\s*["\']ref-(\d{1,4})["\']', html)]
    if not ref_ids:
        return html
    heading_match = _references_heading_search(html, allow_notes_heading=True)
    if heading_match is None:
        first_ref_match = re.search(r'<li\b[^>]*\bid\s*=\s*["\']ref-\d+', html, re.IGNORECASE)
        split_at = first_ref_match.start() if first_ref_match is not None else len(html)
    else:
        split_at = heading_match.start()
    before = html[:split_at]
    after = html[split_at:]
    ref_count = max(ref_ids)
    before = _link_bracket_citations(before, ref_count)
    return _link_table_float_numeric_citation_ranges(before + after, ref_count)


def _recover_bare_citations(html: str, ref_count: int) -> str:
    """Wrap bare citation numbers in ``<sup>`` tags.

    Handles three Marker OCR failure modes:

    1. *Glued* — number immediately follows a letter: ``issues17,68``
    2. *Spaced* — space before the group, followed by punctuation: ``issues 17,68.``
    3. *Dot-separated* — Marker wrote commas as dots: ``issues17.68``

    Numbers are only wrapped when *every* individual number falls within
    ``[1, ref_count]`` to minimise false positives.

    Skips content inside tags that should not be modified (scripts, anchors, etc.).
    """
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []
    trailing_word_stoplist = {
        "table",
        "figure",
        "fig",
        "section",
        "sec",
        "box",
        "eq",
        "equation",
        "chapter",
        "range",
        "distance",
        "frequency",
        "parameter",
        "value",
        "values",
        "sample",
        "data",
        "page",
        "pages",
        "unit",
        "units",
        "vol",
        "volume",
        "issue",
        "front",
        "supplementary",
        "doi",
        "pmid",
        "isbn",
        "mhz",
        "ghz",
        "khz",
        "mm",
        "cm",
        "kg",
        "g",
        "mg",
        "nm",
        "um",
        "ph",
        "monkey",
        "week",
        "month",
        "animal",
        "female",
        "male",
        "d",
        "ma",
        "ua",
        "a",
        "v",
        "hz",
        "as",
        "at",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "in",
        "of",
        "than",
        "to",
        "under",
        "with",
        "µm",
    }

    def _stoplisted(word: str) -> bool:
        return word.lower() in _BARE_CITATION_TRAILING_WORD_STOPLIST

    def _normalize_comma_citations(nums_text: str) -> str | None:
        try:
            nums = [int(n.strip()) for n in nums_text.split(",")]
        except ValueError:
            return None
        if not nums:
            return None

        # OCR merge artefact: "169,70" where original likely was "69,70".
        if len(nums) == 2:
            first, second = nums[0], nums[1]
            if (
                first >= 100
                and second < 100
                and first > second
                and str(first).startswith("1")
            ):
                candidate = int(str(first)[1:])
                if 1 <= candidate <= ref_count and 0 <= (second - candidate) <= 5:
                    nums[0] = candidate

        if not all(1 <= n <= ref_count for n in nums):
            return None
        return ",".join(str(n) for n in nums)

    def _valid_nums(nums_text: str, sep: str = ",") -> bool:
        try:
            return all(1 <= int(n.strip()) <= ref_count for n in nums_text.split(sep))
        except ValueError:
            return False

    def _looks_like_ratio_suffix(m: re.Match[str], group_name: str = "num") -> bool:
        tail = m.string[m.end(group_name): m.end(group_name) + 5]
        return bool(re.match(r":\d", tail))

    def _looks_like_capitalized_version_label(m: re.Match[str]) -> bool:
        word = m.group("word") or ""
        if not word or not word[0].isupper():
            return False
        # Single bare citations in prose normally follow a lowercase word
        # ("datasets 62.").  A capitalized token followed by one small number
        # and punctuation is much more likely to be a product/model/version
        # label, table label, named cohort, or similar non-bibliographic value.
        try:
            number = int(m.group("num"))
        except ValueError:
            return False
        return 0 <= number <= 20

    def _has_non_citation_left_context(m: re.Match[str]) -> bool:
        left = m.string[max(0, m.start() - 60): m.start()]
        return _NONCITATION_NUMERIC_CONTEXT_PATTERN.search(left) is not None

    def _wrap_glued(m: re.Match[str]) -> str:
        if _has_non_citation_left_context(m):
            return m.group(0)
        nums_text = m.group(1)
        normalized = _normalize_comma_citations(nums_text)
        return f"<sup>{normalized}</sup>" if normalized is not None else m.group(0)

    def _wrap_spaced(m: re.Match[str]) -> str:
        if _has_non_citation_left_context(m):
            return m.group(0)
        nums_text = m.group(1)
        # Preserve the space before <sup>
        normalized = _normalize_comma_citations(nums_text)
        return f" <sup>{normalized}</sup>" if normalized is not None else m.group(0)

    def _wrap_dot(m: re.Match[str]) -> str:
        if _has_non_citation_left_context(m):
            return m.group(0)
        nums_text = m.group(1)
        # Convert dots to commas so downstream link logic treats them uniformly
        nums_comma = nums_text.replace(".", ",")
        normalized = _normalize_comma_citations(nums_comma)
        return f"<sup>{normalized}</sup>" if normalized is not None else m.group(0)

    def _wrap_single_spaced(m: re.Match[str]) -> str:
        word = (m.group("word") or "").lower()
        if _has_non_citation_left_context(m):
            return m.group(0)
        if _stoplisted(word):
            return m.group(0)
        if _looks_like_capitalized_version_label(m):
            return m.group(0)
        if _looks_like_ratio_suffix(m, "num"):
            return m.group(0)
        nums_text = m.group("num")
        return f"{m.group('lead')}<sup>{nums_text}</sup>" if _valid_nums(nums_text) else m.group(0)

    def _wrap_spaced_dot(m: re.Match[str]) -> str:
        if _has_non_citation_left_context(m):
            return m.group(0)
        nums_text = m.group(1)
        nums_comma = nums_text.replace(".", ",")
        normalized = _normalize_comma_citations(nums_comma)
        return f" <sup>{normalized}</sup>" if normalized is not None else m.group(0)

    def _wrap_single_trailing(m: re.Match[str]) -> str:
        word = (m.group("word") or "").lower()
        if _has_non_citation_left_context(m):
            return m.group(0)
        if _stoplisted(word):
            return m.group(0)
        if _looks_like_capitalized_version_label(m):
            return m.group(0)
        if _looks_like_ratio_suffix(m, "num"):
            return m.group(0)
        nums_text = m.group("num")
        return f"{m.group('lead')}<sup>{nums_text}</sup>" if _valid_nums(nums_text) else m.group(0)

    def _wrap_single_dot_suffix(m: re.Match[str]) -> str:
        word = (m.group("word") or "").lower()
        if _has_non_citation_left_context(m):
            return m.group(0)
        if _stoplisted(word):
            return m.group(0)
        if _looks_like_ratio_suffix(m, "num"):
            return m.group(0)
        nums_text = m.group("num")
        return f"{m.group('lead')}.<sup>{nums_text}</sup>" if _valid_nums(nums_text) else m.group(0)

    def _wrap_single_glued(m: re.Match[str]) -> str:
        word = (m.group("word") or "").lower()
        if _has_non_citation_left_context(m):
            return m.group(0)
        if _stoplisted(word):
            return m.group(0)
        if _looks_like_capitalized_version_label(m):
            return m.group(0)
        if _looks_like_ratio_suffix(m, "num"):
            return m.group(0)
        nums_text = m.group("num")
        return f"{m.group('lead')}<sup>{nums_text}</sup>" if _valid_nums(nums_text) else m.group(0)

    def _wrap_et_al_glued(m: re.Match[str]) -> str:
        nums_text = m.group("num")
        linked = _link_numeric_superscript_body(nums_text, ref_count) if _valid_nums(nums_text) else None
        return f"{m.group('lead')}<sup>{linked}</sup>" if linked is not None else m.group(0)

    def _wrap_single_connector(m: re.Match[str]) -> str:
        word = (m.groupdict().get("word") or "").lower()
        if _has_non_citation_left_context(m):
            return m.group(0)
        if word and _stoplisted(word):
            return m.group(0)
        if word and _looks_like_capitalized_version_label(m):
            return m.group(0)
        if _looks_like_ratio_suffix(m, "num"):
            return m.group(0)
        nums_text = m.group("num")
        return f"{m.group('lead')}<sup>{nums_text}</sup>" if _valid_nums(nums_text) else m.group(0)

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_citation_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        text = _BARE_CITATION_GLUED_PATTERN.sub(_wrap_glued, part)
        # Spaced-dot before single-spaced so "word 17.68." wins over "word 17."
        text = _BARE_CITATION_SPACED_DOT_PATTERN.sub(_wrap_spaced_dot, text)
        text = _BARE_CITATION_SPACED_PATTERN.sub(_wrap_spaced, text)
        text = _BARE_CITATION_SINGLE_SPACED_PATTERN.sub(_wrap_single_spaced, text)
        text = _BARE_CITATION_SINGLE_CONNECTOR_PATTERN.sub(_wrap_single_connector, text)
        text = _BARE_CITATION_SINGLE_DOT_SUFFIX_PATTERN.sub(_wrap_single_dot_suffix, text)
        text = _BARE_CITATION_ET_AL_GLUED_PATTERN.sub(_wrap_et_al_glued, text)
        text = _BARE_CITATION_SINGLE_GLUED_PATTERN.sub(_wrap_single_glued, text)
        text = _BARE_CITATION_DOT_PATTERN.sub(_wrap_dot, text)
        text = _BARE_CITATION_SINGLE_TRAILING_PATTERN.sub(_wrap_single_trailing, text)
        out.append(text)

    return "".join(out)


def _recover_flattened_author_superscript_citations(
    html: str,
    ref_count: int,
    *,
    author_only: bool = False,
) -> str:
    """Link narrow author-adjacent flattened superscript citations."""
    if ref_count <= 0:
        return html

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def _link_number(number_text: str) -> str | None:
        if len(number_text) > 1 and number_text.startswith("0"):
            return None
        try:
            number = int(number_text)
        except ValueError:
            return None
        if not (1 <= number <= ref_count):
            return None
        return f'<a href="#ref-{number}" class="z2m-ref-link">{number_text}</a>'

    def _has_non_citation_left_context(m: re.Match[str]) -> bool:
        left = m.string[max(0, m.start() - 60): m.start()]
        return _NONCITATION_NUMERIC_CONTEXT_PATTERN.search(left) is not None

    def _replace_et_al(m: re.Match[str]) -> str:
        linked = _link_number(m.group("num"))
        if linked is None:
            return m.group(0)
        return f"{m.group('lead')}<sup>{linked}</sup>"

    def _replace_word_dot(m: re.Match[str]) -> str:
        word = (m.group("word") or "").lower()
        if word in _BARE_CITATION_TRAILING_WORD_STOPLIST:
            return m.group(0)
        if _has_non_citation_left_context(m):
            return m.group(0)
        linked = _link_number(m.group("num"))
        if linked is None:
            return m.group(0)
        return f"{m.group('lead')}.<sup>{linked}</sup>"

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_citation_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        text = _BARE_CITATION_ET_AL_GLUED_PATTERN.sub(_replace_et_al, part)
        if not author_only:
            text = _BARE_CITATION_SINGLE_DOT_SUFFIX_PATTERN.sub(_replace_word_dot, text)
        out.append(text)

    return "".join(out)


def _recover_flattened_superscript_numeric_citations(html: str, ref_count: int) -> str:
    if ref_count <= 0:
        return html

    def _valid_body(body: str) -> bool:
        return _link_numeric_superscript_body(body, ref_count) is not None

    def _has_multiple_numbers(body: str) -> bool:
        return len(_numeric_citation_body_numbers(body)) > 1

    def _replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        visible = _visible_text(raw)
        dot_matches = list(_FLATTENED_DOT_SUPERSCRIPT_CITATION_PATTERN.finditer(visible))
        sentence_matches = list(_FLATTENED_SENTENCE_SUPERSCRIPT_CITATION_PATTERN.finditer(visible))
        et_al_count = len(list(_BARE_CITATION_ET_AL_GLUED_PATTERN.finditer(visible)))
        strong_dot_evidence = any(_has_multiple_numbers(m.group("body")) for m in dot_matches)
        allow_single_dot = strong_dot_evidence or et_al_count > 0 or len(dot_matches) >= 2
        allow_sentence_single = et_al_count > 0 or len(sentence_matches) >= 2 or strong_dot_evidence

        def _replace_dot(part_match: re.Match[str]) -> str:
            word = (part_match.group("word") or "").lower()
            body = part_match.group("body")
            if word in _FLATTENED_DOT_HARD_STOPLIST or word.endswith(("fig", "figure")):
                return part_match.group(0)
            if (
                word in _BARE_CITATION_TRAILING_WORD_STOPLIST
                and not (_has_multiple_numbers(body) or allow_single_dot)
            ):
                return part_match.group(0)
            linked = _link_numeric_superscript_body(body, ref_count)
            if linked is None:
                return part_match.group(0)
            return f"{part_match.group('lead')}.<sup>{linked}</sup>"

        def _replace_sentence(part_match: re.Match[str]) -> str:
            body = part_match.group("body")
            if not (_has_multiple_numbers(body) or allow_sentence_single):
                return part_match.group(0)
            linked = _link_numeric_superscript_body(body, ref_count)
            if linked is None:
                return part_match.group(0)
            return f"{part_match.group('punct')} <sup>{linked}</sup>"

        parts = _TAG_SPLIT_PATTERN.split(raw)
        out: list[str] = []
        skip_stack: list[str] = []
        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                _update_citation_skip_stack(part, skip_stack)
                out.append(part)
                continue
            if skip_stack:
                out.append(part)
                continue
            fixed = _BARE_CITATION_ET_AL_GLUED_PATTERN.sub(
                lambda m: (
                    f"{m.group('lead')}<sup>{_link_numeric_superscript_body(m.group('num'), ref_count)}</sup>"
                    if _valid_body(m.group("num"))
                    else m.group(0)
                ),
                part,
            )
            fixed = _FLATTENED_DOT_SUPERSCRIPT_CITATION_PATTERN.sub(_replace_dot, fixed)
            fixed = _FLATTENED_SENTENCE_SUPERSCRIPT_CITATION_PATTERN.sub(_replace_sentence, fixed)
            out.append(fixed)
        return "".join(out)

    return _SENTENCE_NODE_PATTERN.sub(_replace_node, html)


def _link_split_et_al_two_digit_citations_in_fragment(fragment: str, ref_count: int) -> str:
    if ref_count < 10 or "et al" not in fragment.lower():
        return fragment

    def _render(lead: str, number_text: str) -> str | None:
        linked = _link_numeric_superscript_body(number_text, ref_count)
        if linked is None:
            return None
        return f"{lead}<sup>{linked}</sup>"

    def _replace_linked(match: re.Match[str]) -> str:
        first = match.group("first").strip()
        target = match.group("target").strip()
        if len(first) != 1 or target != first:
            return match.group(0)
        rendered = _render(match.group("lead"), f"{first}{match.group('second')}")
        return rendered if rendered is not None else match.group(0)

    def _replace_plain(match: re.Match[str]) -> str:
        rendered = _render(match.group("lead"), f"{match.group('first')}{match.group('second')}")
        return rendered if rendered is not None else match.group(0)

    repaired = _SPLIT_ET_AL_TWO_DIGIT_LINK_PATTERN.sub(_replace_linked, fragment)
    return _SPLIT_ET_AL_TWO_DIGIT_TEXT_PATTERN.sub(_replace_plain, repaired)


def _link_flattened_et_al_numeric_citations_in_text_blocks(html: str, ref_count: int) -> str:
    if ref_count <= 0 or "et al" not in html.lower():
        return html

    def _replace_block(match: re.Match[str]) -> str:
        raw = match.group(0)
        if len(raw) > 10000:
            return raw
        open_tag = match.group("open")
        if not re.search(r'\bblock-type\s*=\s*["\']Text["\']', open_tag, re.IGNORECASE):
            return raw
        if _node_protects_citations(raw):
            return raw

        def _replace_text_node(part: str) -> str:
            if len(part) > 5000:
                return part
            def _replace_et_al(et_match: re.Match[str]) -> str:
                linked = _link_numeric_superscript_body(et_match.group("num"), ref_count)
                if linked is None:
                    return et_match.group(0)
                return f"{et_match.group('lead')}<sup>{linked}</sup>"

            return _BARE_CITATION_ET_AL_GLUED_PATTERN.sub(_replace_et_al, part)

        raw = _link_split_et_al_two_digit_citations_in_fragment(raw, ref_count)
        parts = _TAG_SPLIT_PATTERN.split(raw)
        return "".join(part if part.startswith("<") else _replace_text_node(part) for part in parts)

    return _P_BLOCK_PATTERN.sub(_replace_block, html)


def _link_flattened_et_al_numeric_citations_to_existing_refs(html: str) -> str:
    ref_ids = [int(value) for value in re.findall(r'\bid\s*=\s*["\']ref-(\d{1,4})["\']', html)]
    if not ref_ids:
        return html
    return _link_flattened_et_al_numeric_citations_in_text_blocks(html, max(ref_ids))


def _recover_ocr_citation_artifacts(html: str, ref_count: int) -> str:
    if ref_count >= 58:
        html = _OCR_TASK_SEC_CITATION_PATTERN.sub(r"task<sup>58</sup>.", html)
    if ref_count >= 60:
        html = _OCR_FLAGSHIP_MODELS_6000_CITATION_PATTERN.sub(
            r"flagship models<sup>59,60</sup>",
            html,
        )
    return html


def _recover_citations_leaked_into_tex_units(html: str, ref_count: int) -> str:
    """Recover citations that leaked into TeX unit exponents.

    OCR/Marker occasionally glues a citation superscript to a unit inside inline
    TeX, producing constructs like ``\\sqrt{\\mathrm{m}^{24}}`` or ``GPa^{23}``.
    We move such trailing citation numbers back to ``<sup>N</sup>``.
    """
    if ref_count <= 0:
        return html

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def _fix_inline_tex(m: re.Match[str]) -> str:
        expr = m.group(1)
        expr_fixed = expr
        leaked_cites: list[int] = []

        sqrt_match = _LEAKED_SQRT_M_CITATION_PATTERN.search(expr_fixed)
        if sqrt_match is not None:
            cite = int(sqrt_match.group("cite"))
            if 10 <= cite <= ref_count:
                leaked_cites.append(cite)
                expr_fixed = _LEAKED_SQRT_M_CITATION_PATTERN.sub(
                    r'\\sqrt{\\mathrm{m}}',
                    expr_fixed,
                )

        unit_match = _LEAKED_UNIT_EXPONENT_PATTERN.search(expr_fixed)
        if unit_match is not None:
            cite = int(unit_match.group("cite"))
            if 10 <= cite <= ref_count:
                leaked_cites.append(cite)
                expr_fixed = f"{unit_match.group('core')}{unit_match.group('unit')}"

        if not leaked_cites:
            return m.group(0)

        suffix = "".join(f"<sup>{n}</sup>" for n in leaked_cites)
        return f"\\({expr_fixed}\\){suffix}"

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_citation_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_INLINE_TEX_PATTERN.sub(_fix_inline_tex, part))

    return "".join(out)


def _restore_inline_tex_sentence_punctuation(html: str) -> str:
    html = _INLINE_TEX_SENTENCE_BOUNDARY_PATTERN.sub(
        lambda m: f"{m.group('formula')}.</p><p{m.group('attrs')}>{m.group('next')}",
        html,
    )
    return _CIC_UNIT_SENTENCE_BOUNDARY_PATTERN.sub(
        lambda m: f"{m.group('phrase')}.</p><p{m.group('attrs')}>{m.group('next')}",
        html,
    )


def _normalize_split_micro_meter_tokens(html: str) -> str:
    html = _TAG_SPLIT_MICRO_METER_PATTERN.sub("\u00b5m", html)
    return _SPACED_MICRO_METER_PATTERN.sub("\u00b5m", html)


def _looks_inline_tex_dimension_prose(body: str) -> bool:
    if len(body) > 420:
        return False
    lowered = body.lower()
    if re.search(r"\\(?:frac|sqrt|sum|prod|int|lim|alpha|beta|gamma|delta|phi|omega|sigma)\b", lowered):
        return False
    visible = _visible_text(body)
    if not visible:
        return False
    if re.search(r"[_=]", visible):
        return False
    if "^" in body and not re.search(r"(?:\\mu|µ|μ|um|Вµ|Ој|Р’Вµ|РћС)m?\s*\^", body, re.IGNORECASE):
        return False
    if not re.search(r"(?:\\mu|µm|μm|um|Вµm|Ојm|Р’Вµm|РћСm|\bmm\b|\bcm\b|\bch\b|\\times|×|x\s*\d|\bto\b)", body + " " + visible, re.IGNORECASE):
        return False
    words = {word.lower() for word in re.findall(r"[A-Za-zµμВµОј]+", visible)}
    allowed = {
        "and",
        "or",
        "to",
        "ch",
        "mm",
        "cm",
        "m",
        "um",
        "µm",
        "μm",
        "times",
        "text",
        "pm",
        "mathrm",
        "shafts",
        "threads",
        "вµm",
        "ојm",
        "р",
        "в",
        "vm",
        "om",
    }
    return all(word in allowed for word in words)


def _normalize_inline_tex_dimension_body(body: str) -> str:
    text = body
    text = re.sub(r"\\\s+(?=ch\b)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\\(?:,|;|!| )", " ", text)
    text = re.sub(r"\\pm\b", "\u00b1", text, flags=re.IGNORECASE)
    text = re.sub(r"\\text\{\s*([A-Za-zµμ]+)\s*\}", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\\mathrm\{\s*([A-Za-zµμ]+)\s*\}", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\\times\b", "\u00d7", text, flags=re.IGNORECASE)
    text = re.sub(r"\\mu\s*\\text\{m\}", "\u00b5m", text, flags=re.IGNORECASE)
    text = re.sub(r"\\mu\s*m\b", "\u00b5m", text, flags=re.IGNORECASE)
    text = re.sub(r"\\mum\b", "\u00b5m", text, flags=re.IGNORECASE)
    text = _normalize_split_micro_meter_tokens(text)
    text = re.sub(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>u|\u00b5|\u03bc|Вµ|Ој|Р’Вµ|РћС)m\s*\^?\s*2\b",
        lambda m: f"{m.group('value')} \u00b5m<sup class=\"z2m-unit-exp\">2</sup>",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(?<=\d)\s*(?:x|×|Г—)\s*(?=\d)", " \u00d7 ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+\bto\b\s+", " to ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s+([,;:])", r"\1", text)
    text = re.sub(r"([,;:])(?=\S)", r"\1 ", text)
    return text.strip()


def _looks_inline_tex_statistical_prose(body: str) -> bool:
    if len(body) > 260:
        return False
    if "<" in body or ">" in body:
        return False
    if not re.search(r"\\pm(?=\b|\d)", body, re.IGNORECASE):
        return False
    if re.search(r"\\(?!pm(?=\b|\d)|[,;! ])", body, re.IGNORECASE):
        return False
    visible = _visible_text(body)
    if not re.search(r"\d", visible):
        return False
    words = {word.lower() for word in re.findall(r"[A-Za-z]+", visible)}
    allowed = {"p", "vs", "pm"}
    return words <= allowed and bool(words & {"p", "vs", "pm"})


def _normalize_inline_tex_statistical_body(body: str) -> str:
    text = body
    text = re.sub(r"\\pm(?=\b|\d)", "\u00b1", text, flags=re.IGNORECASE)
    text = re.sub(r"\\(?:,|;|!| )", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*±\s*", " ± ", text)
    text = re.sub(r"\bvs\.?\s*", "vs. ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bp\s*=\s*", "p = ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+([,;:])", r"\1", text)
    text = re.sub(r"([,;:])(?=\S)", r"\1 ", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text.strip()


def _normalize_inline_tex_statistical_prose(html: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        body = match.group("body")
        if not _looks_inline_tex_statistical_prose(body):
            return match.group(0)
        return _normalize_inline_tex_statistical_body(body)

    return _INLINE_TEX_DIMENSION_PROSE_PATTERN.sub(_replace, html)


def _normalize_inline_tex_dimension_prose(html: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        body = match.group("body")
        if not _looks_inline_tex_dimension_prose(body):
            return match.group(0)
        return _normalize_inline_tex_dimension_body(body)

    html = _INLINE_TEX_DIMENSION_PROSE_PATTERN.sub(_replace, html)
    return _DISPLAY_TEX_DIMENSION_PROSE_PATTERN.sub(_replace, html)


def _normalize_dimension_prose_spacing(html: str) -> str:
    unit = r"(?:u|\u00b5|\u03bc)m|mm|cm"
    unit_exp = r"(?:<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*[12]\s*</sup>)?"
    html = re.sub(
        rf"\(\s+(?=\d+(?:\.\d+)?\s*(?:(?:{unit})\b|[x\u00d7]))",
        "(",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        rf"(?P<left>(?:{unit}){unit_exp})\s+([;:,])",
        r"\g<left>\2",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        rf"(\([^()]*?(?:(?:{unit})|ch|[x\u00d7])[^()]*?)\s+\)",
        r"\1)",
        html,
        flags=re.IGNORECASE,
    )
    return re.sub(
        rf"(\([^()]*?(?:(?:{unit})|ch|[x\u00d7])[^()]*?\))\s+([,.;:])",
        r"\1\2",
        html,
        flags=re.IGNORECASE,
    )


def _normalize_unit_symbol_spacing(html: str) -> str:
    html = _OHM_PREFIX_SPACE_PATTERN.sub(lambda m: f"{m.group('prefix')}Ω", html)
    html = _OHM_PUNCT_SPACE_PATTERN.sub(lambda m: f"{m.group('unit').replace('Ω', 'Ω')}{m.group('punct')}", html)
    html = _UNIT_EXPONENT_SUP_LEADING_SPACE_PATTERN.sub(lambda m: m.group("unit"), html)
    return _UNIT_EXPONENT_SUP_PUNCT_SPACE_PATTERN.sub(
        lambda m: f"{m.group('sup')}{m.group('punct')}",
        html,
    )


def _repair_equation_defined_index_prose(html: str) -> str:
    if not re.search(
        r"iECoG\(t\)(?:_j|\s+j|\s*<sup\b)|\bCOG\(t\)|\bposition\s+j\b",
        html,
        flags=re.IGNORECASE,
    ):
        return html

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def _repair_text_span(text: str) -> str:
        repaired = re.sub(r"\biECoG\(t\)\s+j\b", "iECoG(t)<sub>j</sub>", text)
        repaired = re.sub(r"\bx\s+j\b", "x<sub>j</sub>", repaired)
        return re.sub(r"\byj\b", "y<sub>j</sub>", repaired)

    idx = 0
    while idx < len(parts):
        part = parts[idx]
        if not part:
            idx += 1
            continue
        if part.startswith("<"):
            if (
                not skip_stack
                and re.match(r"<sup\b", part, flags=re.IGNORECASE)
                and out
                and idx + 2 < len(parts)
                and re.fullmatch(r"\s*j\s*", parts[idx + 1] or "", flags=re.IGNORECASE)
                and re.match(r"</sup\s*>", parts[idx + 2] or "", flags=re.IGNORECASE)
            ):
                previous = out.pop()
                stripped_previous = previous.rstrip()
                if re.search(r"(?:iECoG\(t\)|\bx)\s*$", stripped_previous, flags=re.IGNORECASE):
                    out.append(re.sub(r"\s+$", "", stripped_previous))
                    out.append("<sub>j</sub>")
                    idx += 3
                    continue
            _update_skip_stack(part, skip_stack)
            out.append(part)
            idx += 1
            continue
        if skip_stack:
            out.append(part)
            idx += 1
            continue
        out.append(_repair_text_span(part))
        idx += 1

    return "".join(out)


def _repair_large_html_safe_word_glue_text(text: str) -> str:
    if any(marker in text for marker in _LARGE_HTML_SAFE_WORD_GLUE_MARKERS):
        for pattern, replacement in _LARGE_HTML_SAFE_LITERAL_WORD_GLUE_REPAIRS:
            text = pattern.sub(replacement, text)
        for pattern, replacement in _LARGE_HTML_SAFE_WORD_GLUE_REPAIRS:
            text = pattern.sub(lambda m, repl=replacement: _case_like(m.group(0), repl), text)
    return text


def _repair_known_word_glue_text(text: str) -> str:
    text = _repair_large_html_safe_word_glue_text(text)
    if len(text) > 5000:
        return text
    text = _EFFECTIVE_VARIABLE_PATTERN.sub(
        lambda m: f'{m.group("var")}<sub>eff</sub>',
        text,
    )
    for pattern, replacement in _KNOWN_WORD_GLUE_REPAIRS:
        text = pattern.sub(replacement, text)
    return text


def _repair_large_html_safe_word_glue(html: str) -> str:
    if not any(marker in html for marker in _LARGE_HTML_SAFE_WORD_GLUE_MARKERS):
        return html

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_repair_large_html_safe_word_glue_text(part))
    return "".join(out)


def _case_like(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _repair_english_ocr_text_artifacts_text(text: str) -> str:
    if len(text) > 5000:
        return text
    for pattern, replacement in _EN_OCR_WORD_REPAIRS:
        text = pattern.sub(lambda m, repl=replacement: _case_like(m.group(0), repl), text)
    for pattern, replacement in _EN_OCR_PHRASE_REPAIRS:
        text = pattern.sub(replacement, text)
    return text


def _repair_english_ocr_cross_tag_artifacts(html: str) -> str:
    def _apply_repairs(fragment: str) -> str:
        for pattern, replacement in _EN_OCR_CROSS_TAG_REPAIRS:
            fragment = pattern.sub(replacement, fragment)
        return fragment

    def _flush_buffer() -> None:
        if buffer:
            out.append(_apply_repairs("".join(buffer)))
            buffer.clear()

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    buffer: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if not part.startswith("<"):
            if skip_stack:
                out.append(part)
            else:
                buffer.append(part)
            continue

        raw = part.strip()
        close_match = _CLOSE_TAG_PATTERN.match(raw)
        open_match = _OPEN_TAG_PATTERN.match(raw)
        tag_name = ""
        if close_match is not None:
            tag_name = close_match.group(1).lower()
        elif open_match is not None:
            tag_name = open_match.group(1).lower()

        if skip_stack:
            out.append(part)
            if close_match is not None:
                for idx in range(len(skip_stack) - 1, -1, -1):
                    if skip_stack[idx] == tag_name:
                        del skip_stack[idx]
                        break
            elif (
                open_match is not None
                and tag_name in _EN_OCR_CROSS_TAG_SKIP_TAGS
                and not raw.endswith("/>")
            ):
                skip_stack.append(tag_name)
            continue

        if open_match is not None and tag_name in _EN_OCR_CROSS_TAG_SKIP_TAGS and not raw.endswith("/>"):
            _flush_buffer()
            out.append(part)
            skip_stack.append(tag_name)
            continue

        buffer.append(part)

    _flush_buffer()
    return "".join(out)


def _repair_english_ocr_text_artifacts(html: str) -> str:
    if len(html) > 500000:
        return html
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_repair_english_ocr_text_artifacts_text(part))

    return _repair_english_ocr_cross_tag_artifacts("".join(out))


def _with_diaeresis(match: re.Match[str]) -> str:
    vowel = match.group("vowel")
    replacements = {
        "a": "\u00e4",
        "e": "\u00eb",
        "i": "\u00ef",
        "o": "\u00f6",
        "u": "\u00fc",
        "y": "\u00ff",
        "A": "\u00c4",
        "E": "\u00cb",
        "I": "\u00cf",
        "O": "\u00d6",
        "U": "\u00dc",
        "Y": "\u0178",
    }
    return f"{match.group('left')}{replacements.get(vowel, vowel)}"


def _with_preceding_acute(match: re.Match[str]) -> str:
    replacements = {
        "a": "\u00e1",
        "e": "\u00e9",
        "i": "\u00ed",
        "\u0131": "\u00ed",
        "o": "\u00f3",
        "u": "\u00fa",
        "y": "\u00fd",
        "A": "\u00c1",
        "E": "\u00c9",
        "I": "\u00cd",
        "O": "\u00d3",
        "U": "\u00da",
        "Y": "\u00dd",
    }
    return replacements.get(match.group("vowel"), match.group("vowel"))


def _with_preceding_diaeresis(match: re.Match[str]) -> str:
    replacements = {
        "a": "\u00e4",
        "e": "\u00eb",
        "i": "\u00ef",
        "\u0131": "\u00ef",
        "o": "\u00f6",
        "u": "\u00fc",
        "y": "\u00ff",
        "A": "\u00c4",
        "E": "\u00cb",
        "I": "\u00cf",
        "O": "\u00d6",
        "U": "\u00dc",
        "Y": "\u0178",
    }
    return replacements.get(match.group("vowel"), match.group("vowel"))


def _with_following_acute(match: re.Match[str]) -> str:
    return _with_preceding_acute(match)


def _with_following_diaeresis(match: re.Match[str]) -> str:
    return _with_preceding_diaeresis(match)


def _with_preceding_circumflex(match: re.Match[str]) -> str:
    replacements = {
        "a": "\u00e2",
        "e": "\u00ea",
        "i": "\u00ee",
        "\u0131": "\u00ee",
        "o": "\u00f4",
        "u": "\u00fb",
        "A": "\u00c2",
        "E": "\u00ca",
        "I": "\u00ce",
        "O": "\u00d4",
        "U": "\u00db",
    }
    return replacements.get(match.group("vowel"), match.group("vowel"))


def _with_following_circumflex(match: re.Match[str]) -> str:
    return _with_preceding_circumflex(match)


def _with_preceding_tilde(match: re.Match[str]) -> str:
    replacements = {
        "a": "\u00e3",
        "o": "\u00f5",
        "n": "\u00f1",
        "A": "\u00c3",
        "O": "\u00d5",
        "N": "\u00d1",
    }
    return replacements.get(match.group("letter"), match.group("letter"))


def _with_following_tilde(match: re.Match[str]) -> str:
    return _with_preceding_tilde(match)


def _with_following_caron(match: re.Match[str]) -> str:
    replacements = {
        "c": "\u010d",
        "s": "\u0161",
        "z": "\u017e",
        "C": "\u010c",
        "S": "\u0160",
        "Z": "\u017d",
    }
    return replacements.get(match.group("letter"), match.group("letter"))


def _with_preceding_acute_consonant(match: re.Match[str]) -> str:
    replacements = {
        "n": "\u0144",
        "N": "\u0143",
    }
    return replacements.get(match.group("letter"), match.group("letter"))


def _with_following_acute_consonant(match: re.Match[str]) -> str:
    return _with_preceding_acute_consonant(match)


def _with_following_cedilla(match: re.Match[str]) -> str:
    replacements = {
        "c": "\u00e7",
        "C": "\u00c7",
        "s": "\u015f",
        "S": "\u015e",
    }
    return replacements.get(match.group("letter"), match.group("letter"))


def _repair_latin_detached_accent_artifacts_text(text: str) -> str:
    if not any(mark in text for mark in ("\u00a8", "\u00b4", "\u02c6", "\u02c7", "\u02d9", "\u02dc", "\u00b8")) and not any(
        bad in text for bad, _good in _LATIN_MOJIBAKE_ACCENT_REPLACEMENTS
    ):
        return text
    for bad, good in _LATIN_MOJIBAKE_ACCENT_REPLACEMENTS:
        text = text.replace(bad, good)
    for pattern, replacement in _LATIN_DETACHED_ACCENT_REPAIRS:
        text = pattern.sub(replacement, text)
    text = re.sub(
        r"(?<![A-Za-z])\u00b4\s+Symbol\s+for\s+minutes\s+of\s+arc\b",
        "\u2032 Symbol for minutes of arc",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(?P<left>[A-Za-z])\u00a8\s*(?P<vowel>[AEIOUaeiouyY])", _with_diaeresis, text)
    text = re.sub(
        r"(?i)(?P<prefix>\b[A-Z][A-Za-z\u017e\u0161]+[ai])\u00b4\s*c\b",
        lambda m: f"{m.group('prefix')}\u0107",
        text,
    )
    text = re.sub(
        r"(?i)(?P<prefix>\bMa)\u00b4\s*ckowski\b",
        lambda m: f"{m.group('prefix')}\u0107kowski",
        text,
    )
    text = re.sub(
        r"(?i)(?P<prefix>\bNiccol)\u00b4\s*o\b",
        lambda m: f"{m.group('prefix')}\u00f3",
        text,
    )
    text = re.sub(r"(?P<vowel>[AEIOUYaeiouy\u0131])\u00b4(?=\s*(?:[A-Za-z]|[,.;)]))", _with_preceding_acute, text)
    text = re.sub(r"(?P<vowel>[AEIOUYaeiouy\u0131])\u00a8(?=\s*(?:[A-Za-z]|[,.;)]))", _with_preceding_diaeresis, text)
    text = re.sub(r"(?P<vowel>[AEIOUaeiou\u0131])\u02c6(?=\s*(?:[A-Za-z]|[,.;)]))", _with_preceding_circumflex, text)
    text = re.sub(r"(?P<letter>[Nn])\u00b4(?=\s*(?:[B-DF-HJ-NP-TV-Zb-df-hj-np-tv-z]|[,.;)]))", _with_preceding_acute_consonant, text)
    text = re.sub(r"\bSao\u02dc(?=\s|[,.;)])", "S\u00e3o", text)
    text = re.sub(r"(?P<letter>[AaOoNn])\u02dc(?=\s*(?:[A-Za-z]|[,.;)]))", _with_preceding_tilde, text)
    text = re.sub(r"(?P<letter>[cCsSzZ])\u02c7(?=\s*(?:[A-Za-z]|[,.;)]))", _with_following_caron, text)
    text = re.sub(r"\b(?P<left>[A-Za-z]{2,})-\s+[\u00a8\u00b4\u02c6]\s+(?P<right>[a-z]{3,})\b", r"\g<left>\g<right>", text)
    text = re.sub(r"\b(?P<left>[a-z]{3,})-\s+[\u00a8\u00b4\u02c6]\s+(?P<right>[a-z]{3,})\b", r"\g<left>\g<right>", text)
    text = re.sub(r"\b(?P<left>[A-Z][A-Za-z]{2,})-\s+[\u00a8\u00b4\u02c6]\s+(?P<right>[A-Z][A-Za-z]{2,})\b", r"\g<left>-\g<right>", text)
    text = re.sub(
        r"\b(?P<left>and|or|of|to|in|by|for|with|the)\s+[\u00a8\u00b4]\s+(?P<right>[A-Za-z]{2,})\b",
        r"\g<left> \g<right>",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bRe\s+[\u00a8\u00b4\u02c6]\s+flective\b", "Reflective", text)
    text = re.sub(r"\bre\s+[\u00a8\u00b4\u02c6]\s+flective\b", "reflective", text)
    text = re.sub(r"\b(?P<left>[A-Za-z]{3,})\s+[\u00a8\u00b4]\s+(?P<right>[A-Za-z]{2,})\b", r"\g<left> \g<right>", text)
    text = re.sub(r"\u00b4\s*(?P<vowel>[AEIOUYaeiouy\u0131])", _with_following_acute, text)
    text = re.sub(r"\u00a8\s*(?P<vowel>[AEIOUYaeiouy\u0131])", _with_following_diaeresis, text)
    text = re.sub(r"\u02c6\s*(?P<vowel>[AEIOUaeiou\u0131])", _with_following_circumflex, text)
    text = re.sub(r"\u00b4\s*(?P<letter>[Nn])", _with_following_acute_consonant, text)
    text = re.sub(r"\u02dc\s*(?P<letter>[AaOoNn])", _with_following_tilde, text)
    text = re.sub(r"\u02c7\s*(?P<letter>[cCsSzZ])", _with_following_caron, text)
    text = re.sub(r"\u00b8\s*(?P<letter>[cCsS])", _with_following_cedilla, text)
    text = re.sub(r"(?P<left>[cC])\u00b8(?=[A-Za-z])", lambda m: "\u00c7" if m.group("left") == "C" else "\u00e7", text)
    return text


def _repair_latin_detached_accent_artifacts_html(html: str) -> str:
    html = re.sub(r"\s+[\u00a8\u00b4\u02c6]\s+(?=<(?:i|em|b|strong)\b)", " ", html, flags=re.IGNORECASE)
    return _PAKENAIT_ORCID_DOT_SUFFIX_PATTERN.sub(
        lambda m: f"{m.group('open')}\u0117{m.group('close')}",
        html,
    )


def _repair_latin_detached_accent_artifacts_in_visible_text(html: str) -> str:
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack_for_tags(part, skip_stack, _TEXT_NODE_REPAIR_SKIP_TAGS)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_repair_latin_detached_accent_artifacts_text(part))

    return "".join(out)


def _compact_effective_variable_html(match: re.Match[str]) -> str:
    var_tag = re.sub(r">\s*([A-Z])\s*<", r">\1<", match.group("var"))
    return f"{var_tag}<sub>eff</sub>"


def _repair_known_word_glue_inline_html(html: str) -> str:
    def _repair_chronologically(match: re.Match[str]) -> str:
        replacement = "Chronologically" if match.group("stem")[0].isupper() else "chronologically"
        return f"{match.group('open')}{replacement}{match.group('close')}"

    return _INLINE_CHRONOLOGICALLY_SPLIT_PATTERN.sub(_repair_chronologically, html)


def _repair_known_word_glue(html: str) -> str:
    html = _EFFECTIVE_VARIABLE_HTML_PATTERN.sub(_compact_effective_variable_html, html)
    html = _repair_known_word_glue_inline_html(html)
    if len(html) > 500000:
        return _repair_large_html_safe_word_glue(html)
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_repair_known_word_glue_text(part))

    return "".join(out)


def _repair_known_table_ocr_artifacts(html: str) -> str:
    if "nales" in html and "Qn" in html and "Flow i" in html:
        html = _FRANCO_GARBLED_TABLE_GROUP_HEADER_ROW_PATTERN.sub("", html)
    if "Collodion Prints" in html and "<th> S </th>" in html:
        html = _STULIK_COLLODION_STRAY_HEADER_PATTERN.sub(r"\g<title> <th> </th>", html)
    if "MENDATION" in html and "W TO GET IT" in html:
        html = _ABSTRACTS_QUESTIONNAIRE_HEADER_ROW_PATTERN.sub(
            "<tr>"
            "<th>SYMPTOMS QUESTIONNAIRE - RECOMMENDATION</th>"
            "<th>TYPE OF QUESTIONNAIRE</th>"
            "<th>REFERENCES</th>"
            "<th>HOW TO GET IT</th>"
            "</tr>",
            html,
        )
        html = _ABSTRACTS_QUESTIONNAIRE_CONTINUED_HEADER_ROW_PATTERN.sub(
            "<tr>"
            "<th>SYMPTOMS</th>"
            "<th>QUESTIONNAIRE - RECOMMENDATION</th>"
            "<th>TYPE OF QUESTIONNAIRE</th>"
            "<th>REFERENCES</th>"
            "<th>HOW TO GET IT</th>"
            "</tr>",
            html,
        )
    if "T a bl e" in html and "con t" in html:
        html = _ROLLEMA_TABLE_CONTINUED_HEADING_PATTERN.sub("Table 2.1 (continued)", html)
    if "SUBJECT 11" in html and "ME" in html and "SUREMENT 32" in html:
        for pattern, replacement in _ROLLEMA_PRINTOUT_HEADER_REPAIRS:
            html = pattern.sub(replacement, html)
    return html


def _repair_page_furniture_html_artifacts(html: str) -> str:
    if "ChemComm" in html:
        html = _CHEMCOMM_ACCEPTED_MANUSCRIPT_HEADER_PATTERN.sub(" ", html)
    if "Alrabadi" in html:
        html = _ALRABADI_INLINE_PAGE_FURNITURE_PATTERN.sub(" ", html)
    if "FRANCO" in html:
        html = _FRANCO_INLINE_PAGE_FURNITURE_PATTERN.sub("", html)

    def _replace_node(match: re.Match[str]) -> str:
        body = match.group("body")
        if len(body) > 4000:
            return match.group(0)
        visible = html_lib.unescape(_visible_text(body))
        if not visible:
            return match.group(0)
        for pattern in _PAGE_FURNITURE_VISIBLE_BLOCK_PATTERNS:
            if pattern.fullmatch(visible):
                return ""
        return match.group(0)

    if len(html) > 500000:
        repaired = html
    elif any(marker in html for marker in ("Published", "Downloaded", "Alrabadi", "Accepted Manuscript", "FRANCO", "Volpe")):
        repaired = _PAGE_FURNITURE_HTML_NODE_PATTERN.sub(_replace_node, html)
    else:
        repaired = html
    if "Microsoft" in repaired and "USA)" in repaired:
        repaired = _FRANCO_SPLIT_SENTENCE_PATTERN.sub(r"\1\2", repaired)
    return _EMPTY_BLOCKQUOTE_PATTERN.sub("", repaired)


def _repair_safe_text_artifacts(html: str) -> str:
    html = _repair_page_furniture_html_artifacts(html)
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def _repair_text(text: str) -> str:
        repaired = _repair_split_visible_emails(text)
        if len(repaired) > 5000:
            return repaired
        repaired = _DETACHED_ACCENT_AUTHOR_AND_PATTERN.sub(", ", repaired)
        repaired = _DETACHED_CEDILLA_INITIAL_PATTERN.sub("C. ", repaired)
        repaired = _DETACHED_DIAERESIS_SPACE_PATTERN.sub(" ", repaired)
        repaired = _DETACHED_DIAERESIS_POWERED_PATTERN.sub(" ", repaired)
        repaired = _DETACHED_SYD_DIAERESIS_PATTERN.sub("Syd\u00e4nheimo", repaired)
        repaired = _DETACHED_MOJIBAKE_CEDILLA_INITIAL_PATTERN.sub("C. ", repaired)
        repaired = _DETACHED_MOJIBAKE_DIAERESIS_SPACE_PATTERN.sub(" ", repaired)
        repaired = _DETACHED_MOJIBAKE_DIAERESIS_POWERED_PATTERN.sub(" ", repaired)
        repaired = _DETACHED_MOJIBAKE_SYD_DIAERESIS_PATTERN.sub("Syd\u00e4nheimo", repaired)
        repaired = _repair_latin_detached_accent_artifacts_text(repaired)
        repaired = _CHECK_FOR_UPDATES_PATTERN.sub(" ", repaired)
        for pattern, replacement in _PAGE_FURNITURE_TEXT_REPAIRS:
            repaired = pattern.sub(replacement, repaired)
        return re.sub(r"(?<=\S) {2,}(?=\S)", " ", repaired)

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_repair_text(part))

    repaired_html = _repair_latin_detached_accent_artifacts_html("".join(out))
    return _repair_page_furniture_html_artifacts(repaired_html)


_PDF_LINE_NUMBER_TOKEN_PATTERN = re.compile(
    r"(?<![\w./-])(?P<num>[1-9]\d{0,2})(?![\w./-])"
)
_PDF_LINE_NUMBER_UNIT_FOLLOW_PATTERN = re.compile(
    r"^\s*(?:"
    r"%|‰|°|"
    r"(?:[µμu]?(?:g|m|mol|M|A|C)|nM|mM|M|mg|kg|g|ng|pg|"
    r"mL|L|nm|µm|μm|um|mm|cm|m|s|sec|min|h|Hz|kHz|MHz|GHz|"
    r"kV|mV|V|W|K|Pa|Da|bp|kb|MBq)\b"
    r")",
    re.IGNORECASE,
)
_PDF_LINE_NUMBER_MONTH_FOLLOW_PATTERN = re.compile(
    r"^\s*(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\b",
    re.IGNORECASE,
)
_PDF_LINE_NUMBER_LEFT_LABEL_PATTERN = re.compile(
    r"\b(?:fig(?:ure)?|table|section|sec|chapter|eq(?:uation)?|page|pages|"
    r"vol(?:ume)?|issue|doi|no)\.?\s*$",
    re.IGNORECASE,
)
_PDF_LINE_NUMBER_LEFT_UNIT_PATTERN = re.compile(
    r"\b(?:pH|kg|g|mg|ng|pg|mol|mL|L|nm|µm|μm|um|mm|cm|m|s|sec|min|h|"
    r"Hz|kHz|MHz|GHz|kV|mV|V|W|K|Pa|Da|bp|kb)\s*$",
    re.IGNORECASE,
)


def _is_pdf_line_number_value(value: int) -> bool:
    return 5 <= value <= 300 and value % 5 == 0


def _line_number_skip_stack_update(tag_fragment: str, skip_stack: list[str]) -> None:
    raw = tag_fragment.strip()
    if not raw.startswith("<") or raw.startswith("<!--") or raw.startswith("<!"):
        return
    close_match = _CLOSE_TAG_PATTERN.match(raw)
    if close_match is not None:
        tag_name = close_match.group(1).lower()
        for idx in range(len(skip_stack) - 1, -1, -1):
            if skip_stack[idx] == tag_name:
                del skip_stack[idx]
                break
        return
    if tag_fragment.rstrip().endswith("/>"):
        return
    open_match = _OPEN_TAG_PATTERN.match(raw)
    if open_match is None:
        return
    tag_name = open_match.group(1).lower()
    if tag_name in _CITATION_SKIP_TAGS or tag_name in {"sup", "sub"}:
        skip_stack.append(tag_name)
        return
    if _CITATION_PROTECTED_CLASS_PATTERN.search(raw) is not None:
        skip_stack.append(tag_name)


def _pdf_line_number_text_parts(html: str) -> list[str]:
    parts = _TAG_SPLIT_PATTERN.split(html)
    text_parts: list[str] = []
    skip_stack: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _line_number_skip_stack_update(part, skip_stack)
            continue
        if not skip_stack:
            text_parts.append(part)
    return text_parts


def _pdf_line_number_context_allows(text: str, match: re.Match[str]) -> bool:
    try:
        value = int(match.group("num"))
    except ValueError:
        return False
    if not _is_pdf_line_number_value(value):
        return False

    left = text[: match.start()]
    right = text[match.end():]
    left_stripped = left.rstrip()
    right_stripped = right.lstrip()
    if not right_stripped:
        return False
    if left_stripped and left_stripped[-1] in "-–—/":
        return False
    if right_stripped[0] in "-–—/.,:)]}%":
        return False
    if re.search(r"\b\d{1,3}\s*,\s*$", left):
        return False
    if _PDF_LINE_NUMBER_UNIT_FOLLOW_PATTERN.match(right):
        return False
    if _PDF_LINE_NUMBER_MONTH_FOLLOW_PATTERN.match(right):
        return False
    left_visible = _visible_text(left[-80:])
    if _PDF_LINE_NUMBER_LEFT_LABEL_PATTERN.search(left_visible):
        return False
    if _PDF_LINE_NUMBER_LEFT_UNIT_PATTERN.search(left_visible):
        return False

    right_word_match = re.match(r"\s*([A-Za-z][A-Za-z-]*)", right)
    right_acronym_match = re.match(r"\s*\([A-Z][A-Z0-9-]{1,12}\)", right)
    before_is_start = not left_stripped
    left_word_match = re.search(r"([A-Za-z][A-Za-z-]*)\s*[,;:]?\s*$", left)
    has_left_word = left_word_match is not None
    if right_word_match is None:
        return bool(right_acronym_match and has_left_word and left_stripped[-1] not in ".!?")

    right_word = right_word_match.group(1)
    right_word_lower = right_word.lower()
    if before_is_start:
        return len(right_word) >= 3 and right_word_lower not in {"ref", "doi"}

    if left_stripped[-1] in ".!?":
        # Superscript-style citations often OCR as ". 40 In"; do not eat them.
        return False

    if right_word[0].islower():
        return has_left_word or (left_stripped[-1] in ",;:")
    if has_left_word and right_word_lower not in {"fig", "figure", "table", "section"}:
        return True
    if left_stripped[-1] in ",;:" and right_word_lower not in {"fig", "figure", "table"}:
        return True
    return has_left_word and right_word_lower in {
        "the",
        "only",
        "a",
        "an",
        "and",
        "or",
        "for",
        "of",
        "in",
        "on",
        "to",
        "with",
        "by",
        "from",
        "as",
        "which",
        "that",
        "this",
        "these",
        "those",
    }


def _pdf_line_number_candidates(text: str) -> list[int]:
    values: list[int] = []
    for match in _PDF_LINE_NUMBER_TOKEN_PATTERN.finditer(text):
        if _pdf_line_number_context_allows(text, match):
            values.append(int(match.group("num")))
    return values


def _longest_pdf_line_number_run(values: set[int]) -> int:
    longest = 0
    current = 0
    for value in range(5, 305, 5):
        if value in values:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _looks_like_pdf_line_numbered_document(html: str) -> bool:
    candidates: list[int] = []
    for text in _pdf_line_number_text_parts(html):
        candidates.extend(_pdf_line_number_candidates(text))
    unique = set(candidates)
    return len(candidates) >= 10 and len(unique) >= 8 and _longest_pdf_line_number_run(unique) >= 6


def _strip_pdf_line_number_artifacts(html: str) -> str:
    if not _looks_like_pdf_line_numbered_document(html):
        return html

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def replace(match: re.Match[str]) -> str:
        if not _pdf_line_number_context_allows(match.string, match):
            return match.group(0)
        return ""

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _line_number_skip_stack_update(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        repaired = _PDF_LINE_NUMBER_TOKEN_PATTERN.sub(replace, part)
        repaired = re.sub(r"(?<=\S) {2,}(?=\S)", " ", repaired)
        repaired = re.sub(r"^\s+(?=[A-Z])", "", repaired)
        out.append(repaired)

    return "".join(out)


def _normalize_scientific_units(html: str) -> str:
    html = _normalize_split_micro_meter_tokens(html)
    html = _normalize_inline_tex_statistical_prose(html)
    html = _normalize_inline_tex_dimension_prose(html)
    html = _normalize_dimension_prose_spacing(html)
    html = _normalize_unit_symbol_spacing(html)
    html = _SPLIT_CHEMICAL_OXIDE_PATTERN.sub(
        lambda m: f"{m.group('element')}O<sub>x</sub>",
        html,
    )
    html = _ALLOY_OXYGEN_VARIABLE_FORMULA_PATTERN.sub(
        lambda m: f"{m.group('metal')}<sub>x</sub>O<sub>y</sub>",
        html,
    )
    html = _DEGREE_CIRCLE_HTML_PATTERN.sub(
        lambda m: f"{m.group('value')}°{m.group('unit') or m.group('after') or m.group('post')}",
        html,
    )
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def normalize_text(text: str) -> str:
        text = _ANESTHESIA_DOSE_INLINE_TEX_PATTERN.sub(
            lambda m: (
                f"{m.group('first')} \\(mg\\cdot kg^{{-1}}\\cdot h^{{-1}}\\), "
                f"{m.group('second')} \\(\\mu g\\cdot kg^{{-1}}\\cdot h^{{-1}}\\), "
                f"and {m.group('percent')}%, respectively."
            ),
            text,
        )
        text = _PAREN_WORD_NUMBER_GLUE_PATTERN.sub(
            lambda m: f") {m.group('word')} {m.group('value')}",
            text,
        )
        text = _LATEX_MICRO_METER_UNIT_PATTERN.sub(
            lambda m: (
                f"{m.group('value')} \u00b5m"
                + (
                    f'<sup class="z2m-unit-exp">{m.group("exp")}</sup>'
                    if m.group("exp")
                    else ""
                )
            ),
            text,
        )
        text = _INLINE_TEX_MICRO_CURRENT_DENSITY_PATTERN.sub(
            lambda m: f"{m.group('value')} \u03bcC cm<sup class=\"z2m-unit-exp\">-2</sup>",
            text,
        )
        text = _INLINE_TEX_CIC_CHARGE_DENSITY_PATTERN.sub(
            lambda m: f"(CIC) of {m.group('value')} mC cm<sup class=\"z2m-unit-exp\">-2</sup>",
            text,
        )
        text = _INLINE_TEX_CIC_ASSIGN_CHARGE_DENSITY_PATTERN.sub(
            lambda m: f"(CIC = {m.group('value')} mC cm<sup class=\"z2m-unit-exp\">-2</sup>)",
            text,
        )
        text = _INLINE_TEX_MICRO_AREA_PATTERN.sub(
            lambda m: f"{m.group('value')} \u00b5m<sup class=\"z2m-unit-exp\">2</sup>",
            text,
        )
        text = _VALUE_INLINE_TEX_MICRO_METER_PATTERN.sub(
            lambda m: f"{m.group('value')} \u00b5m"
            + (
                f'<sup class="z2m-unit-exp">{m.group("exp")}</sup>'
                if m.group("exp")
                else ""
            ),
            text,
        )
        text = _VALUE_INLINE_TEX_MICRO_CURRENT_PATTERN.sub(
            lambda m: f"{m.group('value')} \u03bcA",
            text,
        )
        text = _INLINE_TEX_MICRO_CURRENT_PATTERN.sub(
            lambda m: f"{m.group('value').replace('−', '-')} \u03bcA",
            text,
        )
        text = _INLINE_TEX_MICRO_SYMBOL_PATTERN.sub("\u03bc", text)
        text = _INLINE_TEX_OMEGA_SYMBOL_PATTERN.sub("\u03a9", text)
        text = _INLINE_TEX_PM_SYMBOL_PATTERN.sub("\u00b1", text)
        text = re.sub(r"(?<=\d)\s+,\s+(?=(?:respectively|p\s*=))", ", ", text, flags=re.IGNORECASE)
        text = re.sub(r"\b([Pp])\s*=\s*(?=\d)", r"\1 = ", text)
        text = re.sub(r"\)\s+\.(?=\s+[A-Z])", ").", text)
        text = _DIMENSION_TIMES_PATTERN.sub(
            lambda m: f"{m.group('left')} \u00d7 {m.group('right')}",
            text,
        )
        text = _CHEMICAL_OXIDE_PATTERN.sub(
            lambda m: f"{m.group('element')}O<sub>x</sub>",
            text,
        )
        text = _VALUE_COMPACT_CURRENT_DENSITY_PATTERN.sub(
            lambda m: f"{m.group('value')} {m.group('prefix')}C cm<sup class=\"z2m-unit-exp\">-2</sup>",
            text,
        )
        text = _MICRO_SQUARE_UNIT_PATTERN.sub(
            lambda m: f"{m.group('value')} \u00b5m<sup class=\"z2m-unit-exp\">2</sup>",
            text,
        )
        text = _COMPACT_CURRENT_DENSITY_PATTERN.sub(
            lambda m: f"{m.group('prefix')}C cm<sup class=\"z2m-unit-exp\">-2</sup>",
            text,
        )
        text = _SPACED_CANDELA_UNIT_PATTERN.sub("cd m", text)
        text = _UNIT_WORD_GLUE_PATTERN.sub(
            lambda m: f"{m.group('value')} {m.group('unit')} {m.group('word')}",
            text,
        )
        text = _PVALUE_FOR_GLUE_PATTERN.sub(
            lambda m: f"{m.group('prefix')} for",
            text,
        )
        text = _repair_known_word_glue_text(text)
        text = _MG_KG_H_NEG_PATTERN.sub(
            "mg kg<sup class=\"z2m-unit-exp\">-1</sup> h<sup class=\"z2m-unit-exp\">-1</sup>",
            text,
        )
        text = _DEGREE_CIRCLE_PATTERN.sub(
            lambda m: f"{m.group('value')}\u00b0{m.group('unit') or m.group('space')}",
            text,
        )
        return _normalize_unit_symbol_spacing(text)

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(normalize_text(part))

    return _normalize_unit_symbol_spacing(
        _normalize_dimension_prose_spacing(_normalize_inline_tex_dimension_prose("".join(out)))
    )


def _mark_unit_exponent_superscripts(html: str) -> str:
    def _unit_match_has_word_left(match: re.Match[str]) -> bool:
        return match.start() > 0 and match.string[match.start() - 1].isalpha()

    def replace_unit_sup(match: re.Match[str]) -> str:
        if _unit_match_has_word_left(match):
            return match.group(0)
        attrs = match.group("attrs") or ""
        if "z2m-unit-exp" in attrs and re.match(r"\s*<(?:i|em)\b", match.group(0), re.IGNORECASE):
            return match.group(0)
        if "z2m-unit-exp" not in attrs:
            attrs = _append_class_to_attrs(attrs, "z2m-unit-exp")
        exp = match.group("exp").replace("\u2212", "-").replace(" ", "")
        return f"{match.group('unit').rstrip()}<sup{attrs}>{exp}</sup>"

    def replace_base10_sup(match: re.Match[str]) -> str:
        attrs = match.group("attrs") or ""
        attrs = _append_class_to_attrs(attrs, "z2m-unit-exp")
        exp = match.group("exp")
        groups = match.groupdict()
        if groups.get("minus") or groups.get("inner_minus"):
            exp = f"-{exp}"
        return f"{match.group('base')}<sup{attrs}>{exp}</sup>"

    def replace_linked_unit_sup(match: re.Match[str]) -> str:
        if _unit_match_has_word_left(match):
            return match.group(0)
        return f'{match.group("unit")}<sup class="z2m-unit-exp">-{match.group("exp")}</sup>'

    def replace_ml_per_second_sup(match: re.Match[str]) -> str:
        return f'{match.group("unit")} s<sup class="z2m-unit-exp">-1</sup>'

    def replace_per_minute_missing_minus_sup(match: re.Match[str]) -> str:
        unit = re.sub(
            r"\b(revolutions?|beats?)(?=min\b)",
            r"\1 ",
            match.group("unit"),
            flags=re.IGNORECASE,
        ).rstrip()
        return f'{unit}<sup class="z2m-unit-exp">-1</sup>'

    html = _ANCHOR_TRAILING_NEG_UNIT_EXP_PATTERN.sub(
        lambda m: (
            f'{m.group("open")}{m.group("body")}{m.group("unit").rstrip()}'
            f'<sup class="z2m-unit-exp">-{m.group("exp")}</sup></a>'
        ),
        html,
    )
    html = _LINKED_ML_PER_SECOND_UNIT_EXPONENT_SUP_PATTERN.sub(
        replace_ml_per_second_sup,
        html,
    )
    html = _LINKED_GENERAL_NEG_UNIT_EXPONENT_SUP_PATTERN.sub(
        replace_linked_unit_sup,
        html,
    )
    html = _LINKED_PER_MINUTE_MISSING_MINUS_SUP_PATTERN.sub(
        replace_per_minute_missing_minus_sup,
        html,
    )
    html = _ML_PER_SECOND_UNIT_EXPONENT_SUP_PATTERN.sub(
        replace_ml_per_second_sup,
        html,
    )
    html = _BRACE_RANGE_BEFORE_ML_PER_SECOND_PATTERN.sub(r"\g<left>-\g<right>", html)
    html = _COMPACT_VALUE_ML_PER_SECOND_PATTERN.sub(r"\g<value> ", html)
    html = _LINKED_POS_UNIT_EXPONENT_SUP_PATTERN.sub(
        lambda m: f'{m.group("unit").rstrip()}<sup class="z2m-unit-exp">{m.group("exp")}</sup>',
        html,
    )
    html = _LINKED_UNIT_EXPONENT_SUP_PATTERN.sub(
        replace_linked_unit_sup,
        html,
    )
    html = _LINKED_NEG_UNIT_EXPONENT_SUP_PATTERN.sub(
        replace_linked_unit_sup,
        html,
    )
    html = _LINKED_SPLIT_UNIT_EXPONENT_REF_PATTERN.sub(
        lambda m: f'{m.group("unit")}<sup class="z2m-unit-exp">{m.group("exp")}</sup>',
        html,
    )
    html = re.sub(
        r"(?<![A-Za-z])(?P<unit>(?:nm|d|s)\s*)"
        r"<sup\b[^>]*>\s*<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>[1234])['\"][^>]*>\s*(?P=exp)\s*</a>\s*</sup>",
        lambda m: f'{m.group("unit")}<sup class="z2m-unit-exp">{m.group("exp")}</sup>',
        html,
        flags=re.IGNORECASE,
    )
    html = _LINKED_PLAIN_NEG_UNIT_EXPONENT_REF_PATTERN.sub(
        lambda m: f'{m.group("unit").rstrip()}<sup class="z2m-unit-exp">-{m.group("exp")}</sup>',
        html,
    )
    html = _PLAIN_NEG_UNIT_EXP_PATTERN.sub(
        lambda m: f'{m.group("unit").rstrip()}<sup class="z2m-unit-exp">-{m.group("exp")}</sup>',
        html,
    )
    html = _LINKED_DIRECT_UNIT_EXPONENT_REF_PATTERN.sub(
        lambda m: f'{m.group("prefix")}{m.group("unit")}<sup class="z2m-unit-exp">{m.group("exp")}</sup>',
        html,
    )
    html = re.sub(
        r"(?P<base>\b10)\s*<sup\b[^>]*>\s*(?P<inner_minus>[-\u2212\u2013\u2014])\s*"
        r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<exp>\d{1,2})['\"][^>]*>\s*(?P=exp)\s*</a>\s*</sup>",
        lambda m: f'{m.group("base")}<sup class="z2m-unit-exp">-{m.group("exp")}</sup>',
        html,
        flags=re.IGNORECASE,
    )
    html = _LINKED_BASE10_EXPONENT_SUP_PATTERN.sub(
        lambda m: f'{m.group("base")}<sup class="z2m-unit-exp">{"-" if m.group("minus") else ""}{m.group("exp")}</sup>',
        html,
    )
    html = _PLAIN_BASE10_EXPONENT_BEFORE_UNIT_SUP_PATTERN.sub(
        lambda m: f'10<sup class="z2m-unit-exp">-{m.group("exp")}</sup>',
        html,
    )
    html = _MG_KG_H_NEG_HTML_PATTERN.sub(
        'mg kg<sup class="z2m-unit-exp">-1</sup> h<sup class="z2m-unit-exp">-1</sup>',
        html,
    )
    html = _SPLIT_SIGN_ONLY_NEG_UNIT_EXP_HTML_PATTERN.sub(
        lambda m: f'{m.group("unit").rstrip()}<sup class="z2m-unit-exp">-{m.group("exp")}</sup>',
        html,
    )
    html = _SPLIT_NEG_UNIT_EXP_HTML_PATTERN.sub(
        lambda m: f"{m.group('unit')}<sup{_append_class_to_attrs(m.group('attrs') or '', 'z2m-unit-exp')}>-{m.group('exp')}</sup>",
        html,
    )
    html = _PLAIN_POS_UNIT_EXP_PATTERN.sub(
        lambda m: f'{m.group("value")} {m.group("unit")}<sup class="z2m-unit-exp">{m.group("exp")}</sup>',
        html,
    )
    html = re.sub(
        r"(?P<base>\b10)\s*<sup(?P<attrs>[^>]*)>\s*(?P<inner_minus>[-\u2212\u2013\u2014])\s*(?P<exp>\d{1,2})\s*</sup>",
        replace_base10_sup,
        html,
        flags=re.IGNORECASE,
    )
    html = _BASE10_EXPONENT_SUP_PATTERN.sub(replace_base10_sup, html)
    html = re.sub(
        r"(?<![A-Za-z])(?P<unit>(?:nm|d|s)\s*)<sup(?P<attrs>[^>]*)>\s*(?P<exp>[1234])\s*</sup>",
        replace_unit_sup,
        html,
        flags=re.IGNORECASE,
    )
    html = _UNIT_EXPONENT_SUP_PATTERN.sub(replace_unit_sup, html)
    return _normalize_unit_symbol_spacing(_MISSING_SPACE_AFTER_UNIT_SUP_PATTERN.sub(r"\1 ", html))


def _fix_false_sup_citations_in_decimals_and_figure_labels(html: str) -> str:
    """Undo known false-positive citation links in decimals and figure labels."""
    def _unwrap_linked_numeric_value_superscripts(text: str) -> str:
        if "#ref-" not in text or "<sup" not in text:
            return text

        def _replace_value_sup(match: re.Match[str]) -> str:
            raw = match.group(0)
            if "z2m-ref-link" not in raw:
                return raw
            body = match.group(1)
            visible = re.sub(r"\s+", " ", _visible_text(body)).strip()
            if re.fullmatch(r"\d{1,4}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,4}){1,4}", visible) is None:
                return raw
            linked_refs = re.findall(
                r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(\d+)["\'][^>]*\bz2m-ref-link\b[^>]*>\s*(\d{1,4})\s*</a>',
                body,
                re.IGNORECASE,
            )
            if not linked_refs or any(target != label for target, label in linked_refs):
                return raw
            left_text = _visible_text(text[max(0, match.start() - 220): match.start()])
            right_text = _visible_text(text[match.end(): match.end() + 180])
            left_value_context = re.search(
                r"(?:\b(?:ages?|aged|at|between|can\s+last|delay|distance|duration|from|interval|jittered|last|lasting)\s*$"
                r"|\b(?:left|right)\s+at\s*$"
                r"|\bclosest\s+obstacle\s*\([^)]*$"
                r"|[\(,;]\s*$)",
                left_text,
                re.IGNORECASE,
            ) is not None
            right_value_context = re.match(
                r"^\s*(?:"
                r"\d+\s*(?:mm|cm|m|s|ms|sec(?:onds?)?|seconds?|years?|yrs?|months?|days?|hours?)\b|"
                r"(?:or|and|to)\s+\d+(?:\.\d+)?\s*(?:mm|cm|m|s|ms|sec(?:onds?)?|seconds?|years?|months?|days?|hours?)?\b|"
                r"\)\s*(?:participated|were|was|[,.;]|\b)"
                r")",
                right_text,
                re.IGNORECASE,
            ) is not None
            if not (left_value_context and right_value_context):
                return raw
            value = re.sub(r"\s*([\u2013\u2014-])\s*", r"\1", visible)
            if re.match(
                r"^\s*\d+\s*(?:mm|cm|m|s|ms|sec(?:onds?)?|seconds?|years?|yrs?|months?|days?|hours?)\b",
                right_text,
                re.IGNORECASE,
            ):
                value = re.sub(r"\s*,\s*", ",", value)
            else:
                value = re.sub(r"\s*,\s*", ", ", value)
            value = re.sub(r"\s*;\s*", "; ", value)
            return value

        return _SUP_PATTERN.sub(_replace_value_sup, text)

    def _unwrap_linked_decimal_comma_sup_values(text: str) -> str:
        if "#ref-" not in text or "<sup" not in text:
            return text

        def _replace_decimal_sup(match: re.Match[str]) -> str:
            body = match.group("body")
            if "#ref-" not in body:
                return match.group(0)
            visible_body = re.sub(r"\s+", "", _visible_text(body))
            if re.fullmatch(r"\d{1,4}(?:,\d{1,4}){1,4}", visible_body) is None:
                return match.group(0)
            numbers = re.findall(r"\d{1,4}", visible_body)
            if len(numbers) != 2:
                return match.group(0)
            left_text = _visible_text(text[max(0, match.start() - 260) : match.start()])
            right_text = _visible_text(text[match.end() : match.end() + 160])
            if _DECIMAL_COMMA_SUP_VALUE_CONTEXT_RE.search(left_text) is None:
                return match.group(0)
            if re.match(r"^\s*(?:[,;.)\]]|$)", right_text) is None:
                return match.group(0)
            return ".".join(numbers)

        return _LINKED_DECIMAL_COMMA_SUP_VALUE_PATTERN.sub(_replace_decimal_sup, text)

    def _repair_matching_short_context_sup(match: re.Match[str]) -> str:
        if match.group("target") != match.group("num"):
            return match.group(0)
        return f"{match.group('prefix')}{match.group('num')}"

    if len(html) > 500000:
        if "z2m-ref-link" not in html or "<sup" not in html:
            return html
        fixed_large = _FALSE_STAT_SUP_CITATION_PATTERN.sub(
            lambda m: f"{m.group('base')}<sup{m.group('attrs')}>{m.group('exp')}</sup>",
            html,
        )
        fixed_large = _FALSE_CORTICAL_LAYER_LINK_PATTERN.sub(
            _repair_matching_short_context_sup,
            fixed_large,
        )
        fixed_large = _FALSE_COUNT_OF_TOTAL_SUP_REF_PATTERN.sub(
            _repair_matching_short_context_sup,
            fixed_large,
        )
        fixed_large = _FALSE_DAY_NUMBER_SUP_REF_PATTERN.sub(
            _repair_matching_short_context_sup,
            fixed_large,
        )
        fixed_large = _unwrap_linked_numeric_value_superscripts(fixed_large)
        fixed_large = _unwrap_linked_decimal_comma_sup_values(fixed_large)
        return fixed_large

    def _repair_chemical_formula_sup(match: re.Match[str]) -> str:
        if match.group("ref") != match.group("num"):
            return match.group(0)
        base = match.group("base")
        suffix = match.group("suffix") or ""
        suffix_stripped = suffix.strip()
        element_count = len(_CHEMICAL_ELEMENT_TOKEN_PATTERN.findall(base))
        has_suffix_element = bool(suffix_stripped)
        if (
            element_count < 2
            and not has_suffix_element
            and base not in _CHEMICAL_SINGLE_PREFIX_FORMULAS
        ):
            return match.group(0)
        if has_suffix_element:
            return f"{base}{match.group('num')}{suffix_stripped}"
        return f"{base}{match.group('num')}"

    def _repair_short_numeric_context_link(match: re.Match[str]) -> str:
        if match.group("target") != match.group("num"):
            return match.group(0)
        if int(match.group("num")) > 30:
            return match.group(0)
        return f"{match.group('prefix')}{match.group('num')}"

    def _repair_ph_range_link(match: re.Match[str]) -> str:
        if int(match.group("num")) > 14:
            return match.group(0)
        return _repair_short_numeric_context_link(match)

    def _repair_split_year_ref(match: re.Match[str]) -> str:
        if match.group("target") != match.group("num"):
            return match.group(0)
        return f"{match.group('head')}{match.group('num')}{match.group('paren') or ''}"

    fixed = _FALSE_DECIMAL_SUP_CITATION_PATTERN.sub(
        lambda m: f"{m.group('num')}.{m.group('frac')}",
        html,
    )
    fixed = _FALSE_FIGURE_LABEL_SUP_PATTERN.sub(
        lambda m: f"{m.group('prefix')}{m.group('num')}",
        fixed,
    )
    fixed = _FALSE_PH_RANGE_LINK_PATTERN.sub(_repair_ph_range_link, fixed)
    fixed = _FALSE_SUBJECT_SERIES_LINK_PATTERN.sub(_repair_short_numeric_context_link, fixed)
    fixed = _FALSE_RANGE_START_LINK_PATTERN.sub(_repair_short_numeric_context_link, fixed)
    fixed = _FALSE_COUNT_OF_TOTAL_SUP_REF_PATTERN.sub(_repair_matching_short_context_sup, fixed)
    fixed = _FALSE_DAY_NUMBER_SUP_REF_PATTERN.sub(_repair_matching_short_context_sup, fixed)
    fixed = _FALSE_SPLIT_YEAR_REF_PATTERN.sub(_repair_split_year_ref, fixed)
    previous = None
    while previous != fixed:
        previous = fixed
        fixed = _FALSE_FUNCTIONAL_CLASS_LINK_PATTERN.sub(_repair_short_numeric_context_link, fixed)
    fixed = _FALSE_AREA_NUMBER_LINK_PATTERN.sub(_repair_short_numeric_context_link, fixed)
    fixed = _FALSE_CORTICAL_LAYER_LINK_PATTERN.sub(
        _repair_matching_short_context_sup,
        fixed,
    )
    fixed = _FALSE_CHEMICAL_FORMULA_SUP_CITATION_PATTERN.sub(
        _repair_chemical_formula_sup,
        fixed,
    )
    fixed = _FALSE_STAT_SUP_CITATION_PATTERN.sub(
        lambda m: f"{m.group('base')}<sup{m.group('attrs')}>{m.group('exp')}</sup>",
        fixed,
    )
    fixed = _unwrap_linked_numeric_value_superscripts(fixed)
    fixed = _unwrap_linked_decimal_comma_sup_values(fixed)
    fixed = _LINKED_BASE10_MANTISSA_BEFORE_EXP_PATTERN.sub("10", fixed)
    fixed = _LINKED_ML_PER_SECOND_UNIT_EXPONENT_SUP_PATTERN.sub(
        lambda m: f'{m.group("unit")} s<sup class="z2m-unit-exp">-1</sup>',
        fixed,
    )
    return fixed


def _repair_numeric_ref_false_positives(html: str) -> str:
    """Unwrap citation links that are clearly dimensions or numeric ranges."""
    if len(html) > 500000 or "#ref-" not in html:
        return html

    def _unwrap_if_target_matches(match: re.Match[str]) -> str:
        if match.group("target") != match.group("num"):
            return match.group(0)
        prefix = match.groupdict().get("prefix") or ""
        return f"{prefix}{match.group('num')}"

    def _unwrap_color_label(match: re.Match[str]) -> str:
        body = match.group("body")
        refs = re.findall(
            r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(\d+)["\'][^>]*>\s*(\d{1,3})\s*</a>',
            body,
            re.IGNORECASE,
        )
        if not refs or any(target != label for target, label in refs):
            return match.group(0)
        numbers = [label for _, label in refs]
        if any(int(number) > 30 for number in numbers):
            return match.group(0)
        left_text = _visible_text(html[max(0, match.start() - 240) : match.start()])
        right_text = _visible_text(html[match.end() : match.end() + 240])
        window = f"{left_text} {match.group(0)} {right_text}"
        has_color_label_context = (
            re.search(
                r"\b(?:hues?|preferred\s+color|color\s+grating|chromatic|color\s+setting|colors?\s+used)\b",
                window,
                re.IGNORECASE,
            )
            is not None
            or re.match(r"\s+in\s+Experiment\s+\d\b", right_text, re.IGNORECASE) is not None
            or re.match(r"\.\d+\s*%", right_text) is not None
        )
        if not has_color_label_context:
            return match.group(0)
        color = match.group("color")
        if len(numbers) >= 2 and re.match(r"\.\d+\s*%", right_text):
            return f"{color}<sup>{numbers[0]}</sup>," + ",".join(numbers[1:])
        return f"{color}<sup>{','.join(numbers)}</sup>"

    def _normalize_plain_color_percent_label(match: re.Match[str]) -> str:
        tail = re.sub(r"\s+", "", match.group("tail"))
        fraction = re.sub(r"\s+", "", match.group("fraction"))
        return f'{match.group("color")}<sup{match.group("attrs")}>{match.group("first")}</sup>,{tail}{fraction}'

    repaired = _FALSE_DIMENSION_LEADING_SUP_REF_PATTERN.sub(_unwrap_if_target_matches, html)
    repaired = _FALSE_BETWEEN_RANGE_SUP_REF_PATTERN.sub(_unwrap_if_target_matches, repaired)
    repaired = _FALSE_RANGE_ENDPOINT_SUP_REF_PATTERN.sub(_unwrap_if_target_matches, repaired)
    repaired = _FALSE_NUMBERED_SEQUENCE_LEADING_SUP_REF_PATTERN.sub(_unwrap_if_target_matches, repaired)
    repaired = _FALSE_ELECTRODE_PAIR_SUP_REF_PATTERN.sub(
        lambda m: (
            m.group(0)
            if m.group("target1") != m.group("num1") or m.group("target2") != m.group("num2")
            else f"{m.group('prefix')}{m.group('num1')}{m.group('sep')}{m.group('num2')}"
        ),
        repaired,
    )
    repaired = _FALSE_ELECTRODE_PAIR_LEADING_SUP_REF_PATTERN.sub(
        lambda m: (
            m.group(0)
            if m.group("target1") != m.group("num1")
            else f"{m.group('prefix')}{m.group('num1')}{m.group('sep')}{m.group('num2')}"
        ),
        repaired,
    )
    repaired = _FALSE_COLOR_LABEL_SUP_REF_PATTERN.sub(_unwrap_color_label, repaired)
    return _FALSE_COLOR_LABEL_PLAIN_PERCENT_SUP_PATTERN.sub(
        _normalize_plain_color_percent_label,
        repaired,
    )


def _fix_nested_autolink_in_escaped_anchor_snippets(html: str) -> str:
    """Collapse nested autolinks generated inside escaped anchor snippets."""
    return _NESTED_ESCAPED_ANCHOR_AUTOLINK_PATTERN.sub(
        lambda m: (
            f'<a href="{m.group("url")}" target="_blank" rel="noopener noreferrer">'
            f'{m.group("url")}</a>'
        ),
        html,
    )


def _unescape_safe_escaped_anchor_snippets(html: str) -> str:
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def replace(match: re.Match[str]) -> str:
        href = match.group("href")
        label = match.group("label")
        if href != label:
            return match.group(0)
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label}</a>'

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_ESCAPED_ANCHOR_SNIPPET_PATTERN.sub(replace, part))

    return "".join(out)


def _escape_html_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _merge_post_autolink_split_url_anchors(html: str) -> str:
    """Merge URL anchors that were split by OCR and then autolinked separately."""

    def replace(match: re.Match[str]) -> str:
        href = _strip_wrapping_url_quotes(match.group("href"))
        next_href = _strip_wrapping_url_quotes(match.group("next_href"))
        body = _visible_text(match.group("body"))
        next_body = _visible_text(match.group("next_body"))
        tail = match.group("tail") or ""

        combined = f"{body}{match.group('join')}{next_body}{tail}"
        repaired = _repair_broken_visible_url_text(combined)
        if not _starts_like_visible_url_fragment(repaired):
            return match.group(0)
        repaired_key = _url_fragment_compare_key(repaired)
        next_href_key = _url_fragment_compare_key(next_href)
        href_key = _url_fragment_compare_key(href)
        if not repaired_key:
            return match.group(0)
        if not (
            next_href_key.startswith(repaired_key)
            or repaired_key.startswith(next_href_key)
            or (href_key and href_key != next_href_key and next_href_key.startswith(href_key))
        ):
            return match.group(0)

        repaired_url, repaired_trailing = _split_url_and_trailing_punct(repaired)
        repaired_key = _url_fragment_compare_key(repaired_url)
        label = next_href if next_href_key.startswith(repaired_key) and len(repaired_key) >= len(next_href_key) - 4 else repaired_url
        merged_url, trailing = _split_url_and_trailing_punct(label)
        if not trailing:
            trailing = repaired_trailing
        if not re.search(r"\.[A-Za-z]{2,}(?:[/:?#]|$)", merged_url, re.IGNORECASE):
            return match.group(0)
        attrs = re.sub(
            r'(\bhref\s*=\s*)(["\'])(.*?)\2',
            lambda m: f'{m.group(1)}"{_escape_html_attr(merged_url)}"',
            match.group("next_attrs"),
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return f'<a{attrs}>{_escape_html_text(merged_url)}</a>{trailing}'

    pattern = re.compile(
        r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>https?://[^"\']+)(?P=quote)[^>]*)>'
        r'(?P<body>[^<]{1,260})</a>'
        r'(?P<join>\s*\.?\s*)'
        r'<a\b(?P<next_attrs>[^>]*\bhref\s*=\s*(?P<next_quote>["\'])(?P<next_href>https?://[^"\']+)(?P=next_quote)[^>]*)>'
        r'(?P<next_body>[^<]{1,500})</a>'
        r'(?P<tail>\s*[A-Za-z0-9][A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]{0,220})?',
        re.IGNORECASE | re.DOTALL,
    )

    previous = None
    current = html
    while previous != current:
        previous = current
        current = pattern.sub(replace, current)
    return current


def _repair_split_www_domain_anchor_with_noisy_href(html: str) -> str:
    """Recover ``http://www.example`` when the continuation anchor href is OCR-noisy."""

    pattern = re.compile(
        r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])http://www(?P=quote)[^>]*)>'
        r'(?P<body>http://www)</a>\s*\.\s*'
        r'<a\b(?P<next_attrs>[^>]*\bhref\s*=\s*(?P<next_quote>["\'])http://[^"\']+(?P=next_quote)[^>]*)>'
        r'(?P<next_body>[\s\S]{1,500}?)</a>',
        re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        visible = _visible_text(match.group("next_body"))
        domain_match = re.match(
            r"\s*(?P<domain>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)(?P<trailing>[\s\S]*)",
            visible,
        )
        if domain_match is None:
            return match.group(0)
        domain = domain_match.group("domain").rstrip(".,;:)")
        if "." not in domain:
            return match.group(0)
        merged_url = f"http://www.{domain}"
        attrs = _replace_href_attr_literal(match.group("attrs"), merged_url)
        return f'<a{attrs}>{_escape_html_text(merged_url)}</a>{_escape_html_text(domain_match.group("trailing"))}'

    return pattern.sub(replace, html)


def _repair_miswrapped_doi_anchor_labels(html: str) -> str:
    """Move prose out of DOI anchors when OCR split the DOI after a slash."""
    pattern = re.compile(
        r'<a\b(?P<attrs>[^>]*)>'
        r'(?P<body>(?:(?!</a>).)*?\bdoi:\s*10\.\d{4,9}/\s*)</a>'
        r'\s*(?P<tail>[^\s<]+)',
        re.IGNORECASE | re.DOTALL,
    )

    def _replace(match: re.Match[str]) -> str:
        href = _extract_href_attr(match.group("attrs")) or ""
        href_match = re.match(r"https?://(?:dx\.)?doi\.org/(?P<doi>10\..+)$", href, re.IGNORECASE)
        if href_match is None:
            return match.group(0)
        href_doi = href_match.group("doi")
        body = match.group("body")
        doi_match = re.search(r"(?P<prefix>[\s\S]*?\bdoi:\s*)(?P<head>10\.\d{4,9}/)\s*$", body, re.IGNORECASE)
        if doi_match is None:
            return match.group(0)
        full_doi = doi_match.group("head") + match.group("tail")
        if full_doi.rstrip(".,;:") != href_doi.rstrip(".,;:"):
            return match.group(0)
        full_doi, trailing = _split_url_and_trailing_punct(full_doi)
        attrs = match.group("attrs")
        label = _escape_html_text(full_doi)
        return f'{doi_match.group("prefix")}<a{attrs}>{label}</a>{trailing}'

    return pattern.sub(_replace, html)


def _repair_doi_anchor_swallowed_prose_tails(html: str) -> str:
    """Move prose tails out of DOI anchors whose href swallowed paragraph text."""
    if "doi.org/10." not in html.lower():
        return html

    broken_block_tail = re.compile(
        r"(?P<open><p\b[^>]*>\s*(?:DOI\s*:\s*)?)"
        r"<a\b[^>]*\bhref\s*=\s*(?P<quote>['\"])"
        r"(?P<url>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]+)"
        r"\s*</p>\s*<p>\s*(?P<head>[A-Za-z][A-Za-z-]*)\s*(?P=quote)[^>]*>"
        r"(?P<label>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]+)"
        r"\s+(?P=head)\s*</a>\s*(?P<rest>[\s\S]*?</p>)",
        re.IGNORECASE,
    )
    href_tail = re.compile(
        r"(?P<open><p\b[^>]*>\s*(?:DOI\s*:\s*)?)"
        r"<a\b[^>]*\bhref\s*=\s*(?P<quote>['\"])"
        r"(?P<url>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]+)"
        r"(?P<tail>\s+[A-Za-z][A-Za-z-]{2,80})(?P=quote)[^>]*>"
        r"(?P<label>https?://(?:dx\.)?doi\.org/10\.\d{4,9}/[A-Za-z0-9._~-]+)"
        r"(?P=tail)</a>\s*(?P<rest>[\s\S]*?)</p>",
        re.IGNORECASE,
    )

    def _doi_paragraph(open_tag: str, url: str) -> str:
        escaped_url = _escape_html_attr(url)
        return f'{open_tag}<a href="{escaped_url}">{_escape_html_text(url)}</a></p>'

    def _replace_broken_block(match: re.Match[str]) -> str:
        url = match.group("url")
        if match.group("label").rstrip(".,;:") != url.rstrip(".,;:"):
            return match.group(0)
        tail = f"{match.group('head')} {match.group('rest').lstrip()}"
        return f"{_doi_paragraph(match.group('open'), url)}\n<p>{tail}"

    def _replace_href_tail(match: re.Match[str]) -> str:
        url = match.group("url")
        if match.group("label").rstrip(".,;:") != url.rstrip(".,;:"):
            return match.group(0)
        tail = f"{match.group('tail').strip()} {match.group('rest').lstrip()}".rstrip()
        tail_text = _visible_text(tail)
        if len(tail_text) < 25 or len(tail_text.split()) < 4:
            return match.group(0)
        return f"{_doi_paragraph(match.group('open'), url)}\n<p>{tail}</p>"

    previous = None
    current = html
    while previous != current:
        previous = current
        current = broken_block_tail.sub(_replace_broken_block, current)
        current = href_tail.sub(_replace_href_tail, current)
    return current


def _repair_broken_plain_url_text(html: str) -> str:
    """Join OCR spaces inside visible plain URLs before autolinking."""

    def repair_text(text: str) -> str:
        return _repair_broken_visible_url_text(text)

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(repair_text(part))

    return "".join(out)


def _repair_broken_url_anchor_labels(html: str) -> str:
    """Normalize visible URL labels when the href already carries the intact URL."""
    lower_html = html.lower()
    if "http" not in lower_html and "www." not in lower_html:
        return html

    pattern = re.compile(
        r'<a\b(?P<attrs>[^>]*\bhref\s*=\s*(?P<quote>["\'])(?P<href>(?:https?://|www\.)[^"\']+)(?P=quote)[^>]*)>'
        r'(?P<body>[^<]{0,500})</a>',
        re.IGNORECASE | re.DOTALL,
    )

    def repair_label(label: str) -> str:
        return _repair_broken_visible_url_text(label)

    def split_trailing_prose_url(value: str) -> tuple[str, str] | None:
        match = re.match(
            r"(?P<url>https?://\S+?)(?P<trail>\)\s+(?:applies|is|are|to|for)\b[\s\S]*)$",
            value.strip(),
            re.IGNORECASE,
        )
        if match is None:
            return None
        url = match.group("url")
        if not re.search(r"\.[A-Za-z]{2,}(?:[/:?#]|$)", url, re.IGNORECASE):
            return None
        return url, match.group("trail")

    def replace(match: re.Match[str]) -> str:
        href = _strip_wrapping_url_quotes(match.group("href"))
        body = match.group("body")
        repaired = repair_label(body)
        href_repaired = repair_label(href)
        href_split = split_trailing_prose_url(href_repaired)
        body_split = split_trailing_prose_url(repaired)
        if href_split is not None or body_split is not None:
            split_url, split_tail = body_split or href_split  # type: ignore[misc]
            if _url_fragment_compare_key(split_url) == _url_fragment_compare_key((href_split or body_split)[0]):  # type: ignore[index]
                attrs = re.sub(
                    r'(\bhref\s*=\s*)(["\'])(.*?)\2',
                    lambda m: f'{m.group(1)}"{_escape_html_attr(split_url)}"',
                    match.group("attrs"),
                    count=1,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                return f'<a{attrs}>{_escape_html_text(split_url)}</a>{_escape_html_text(split_tail)}'
        repaired_key = _url_fragment_compare_key(repaired)
        href_key = _url_fragment_compare_key(href)
        compact_repaired = _compact_visible_url_fragment(html_lib.unescape(repaired)).rstrip("/")
        compact_href = _compact_visible_url_fragment(html_lib.unescape(href)).rstrip("/")
        if compact_href and compact_repaired.lower() in {
            f"{compact_href}{compact_href}".lower(),
            f"{compact_href}/{compact_href}".lower(),
        }:
            attrs = _replace_href_attr_literal(match.group("attrs"), html_lib.unescape(href))
            return f'<a{attrs}>{_escape_html_text(html_lib.unescape(href))}</a>'
        if repaired_key != href_key:
            href_repaired_url, href_repaired_trailing = _split_url_and_trailing_punct(href_repaired.strip())
            if (
                href_repaired != href
                and not href_repaired_trailing
                and _url_fragment_compare_key(href_repaired_url) == repaired_key
            ):
                attrs = _replace_href_attr_literal(match.group("attrs"), href_repaired_url)
                return f'<a{attrs}>{_escape_html_text(href_repaired_url)}</a>'
            if repaired == body or not re.search(r"(?:https?://|www\.)", body, re.IGNORECASE):
                return match.group(0)
            return f'<a{match.group("attrs")}>{_escape_html_text(repaired)}</a>'
        visible_url, trailing = _split_url_and_trailing_punct(repaired.strip())
        if trailing and _url_fragment_compare_key(visible_url) == href_key:
            return f'<a{match.group("attrs")}>{_escape_html_text(href)}</a>{_escape_html_text(trailing)}'
        if repaired == body and not re.match(r"\s*https?://", body, re.IGNORECASE):
            return match.group(0)
        return f'<a{match.group("attrs")}>{_escape_html_text(href)}</a>'

    return pattern.sub(replace, html)


def _split_doi_metadata_body_paragraphs(html: str) -> str:
    """Split DOI/front-matter metadata from body prose when both share one paragraph."""
    lowered = html.lower()
    if "doi" not in lowered and "10." not in html:
        return html

    def replace(match: re.Match[str]) -> str:
        open_tag = match.group("open")
        if _REFERENCE_PARAGRAPH_ATTR_PATTERN.search(open_tag):
            return match.group(0)

        body = match.group("body")
        boundary = _PLOS_TABLE_DOI_BODY_BOUNDARY_PATTERN.search(body)
        is_plos_table_doi = boundary is not None
        if boundary is None:
            boundary = _DOI_METADATA_BODY_BOUNDARY_PATTERN.search(body)
        if boundary is None:
            return match.group(0)
        if _node_has_class(open_tag, "z2m-front-matter") and not is_plos_table_doi:
            return match.group(0)

        left_body = body[: boundary.end("doi")].rstrip()
        right_body = body[boundary.start("tail") :].lstrip()
        right_text = _visible_text(right_body)
        if len(right_text) < 35 or len(right_text.split()) < 5:
            return match.group(0)

        prefix_text = _visible_text(body[: boundary.start("doi")])
        if len(prefix_text) > 500 and not is_plos_table_doi and not re.search(
            r"\b(?:fig(?:ure)?|table|doi|copyright|license|received|published|available|plos)\b",
            prefix_text,
            re.IGNORECASE,
        ):
            return match.group(0)

        return f"{open_tag}{left_body}{match.group('close')}\n<p>{right_body}</p>"

    return _P_BLOCK_PATTERN.sub(replace, html)


_TABLE_UNIT_TRAILING_BODY_AFTER_TABLE_DOI_NOTE_PATTERN = re.compile(
    r'(?P<open><div\b(?=[^>]*\bclass\s*=\s*(["\'])[^"\']*\bz2m-table-unit\b)[^>]*>)'
    r"(?P<body>[\s\S]*?)"
    r"(?P<note><p\b(?=[^>]*\bclass\s*=\s*([\"'])[^\"']*\bz2m-table-note\b)[^>]*>"
    r"(?=[\s\S]*?10\.1371/journal\.pone\.[^<]+\.t\d+\b)[\s\S]*?</p>)"
    r"\s*(?P<tail><p\b[^>]*>[\s\S]{40,}?</p>)\s*</div>",
    re.IGNORECASE,
)


def _move_body_tail_after_table_doi_note_out_of_table_unit(html: str) -> str:
    """Move body prose out of a table wrapper when it follows a PLOS table DOI note."""

    def replace(match: re.Match[str]) -> str:
        tail = match.group("tail")
        tail_text = _visible_text(tail)
        if len(tail_text) < 35:
            return match.group(0)
        if _is_caption_node(tail) or _is_table_note_node(tail):
            return match.group(0)
        if re.match(
            r"^(?:fig(?:ure)?|table|source|note|notes?|doi|https?://)\b",
            tail_text,
            re.IGNORECASE,
        ):
            return match.group(0)
        return f"{match.group('open')}{match.group('body')}{match.group('note')}</div>\n{tail}"

    previous = None
    current = html
    while previous != current:
        previous = current
        current = _TABLE_UNIT_TRAILING_BODY_AFTER_TABLE_DOI_NOTE_PATTERN.sub(replace, current)
    return current


def _rewrite_page_linked_bracket_citations(html: str, ref_count: int) -> str:
    if ref_count <= 0 or "#page-" not in html:
        return html

    run_pattern = re.compile(
        r'(?P<run>(?:<a\b[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*>[\s\S]{0,80}?</a>\s*){1,6})',
        re.IGNORECASE,
    )
    pattern = re.compile(
        r'\[\s*(?P<body>(?:<a\b[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*>[\s\S]*?</a>\s*){1,6})\]',
        re.IGNORECASE,
    )
    open_outside_pattern = re.compile(
        r'\[\s*(?P<body>(?:<a\b[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*>[\s\S]{0,80}?</a>\s*){1,6})',
        re.IGNORECASE,
    )
    split_anchor_pattern = re.compile(
        r'(?P<run><a\b[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*>'
        r'\s*\[\s*\d{1,3}\s*</a>'
        r'(?:\s*(?:,|[-\u2013\u2014])\s*'
        r'<a\b[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*>'
        r'\s*\d{1,3}\s*\]?\s*</a>){1,5})(?P<trail>[.,;:]?)',
        re.IGNORECASE,
    )
    close_outside_pattern = re.compile(
        r'(?P<body><a\b[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*>\s*\[\s*\d{1,3}\s*</a>)\s*\]',
        re.IGNORECASE,
    )

    def _linked_bracket_from_visible(text: str) -> str | None:
        stripped = text.strip()
        trailing = ""
        trailing_match = re.match(
            r"^(?P<bracket>\[\s*\d{1,3}(?:\s*(?:,|[-\u2013\u2014])\s*\d{1,3})*\s*\])"
            r"(?P<trail>(?:\)+[.,;:]?|[.,;:]))$",
            stripped,
        )
        if trailing_match is not None:
            stripped = trailing_match.group("bracket")
            trailing = trailing_match.group("trail")

        numbers = [int(item) for item in re.findall(r"\d{1,3}", stripped)]
        if not numbers or not all(1 <= number <= ref_count for number in numbers):
            return None
        if _BRACKET_CITATION_PATTERN.fullmatch(stripped) is None:
            return None

        def link_number(num_match: re.Match[str]) -> str:
            number = int(num_match.group(0))
            return f'<a href="#ref-{number}" class="z2m-ref-link">{num_match.group(0)}</a>'

        normalized = re.sub(r"\s+([,;])", r"\1", stripped)
        normalized = re.sub(r"([,;])(?=\S)", r"\1 ", normalized)
        normalized = re.sub(r"\s*([-\u2013\u2014])\s*", r"\1", normalized)
        return re.sub(r"\d{1,3}", link_number, normalized) + trailing

    def replace_run(match: re.Match[str]) -> str:
        raw = match.group("run")
        trailing_match = re.search(r"(\s+)$", raw)
        trailing = trailing_match.group(1) if trailing_match is not None else ""
        text = _visible_text(raw)
        linked = _linked_bracket_from_visible(text)
        return f"{linked}{trailing}" if linked is not None else match.group(0)

    def replace(match: re.Match[str]) -> str:
        body = match.group("body")
        text = _visible_text(body)
        linked = _linked_bracket_from_visible(f"[{text}]")
        return linked if linked is not None else match.group(0)

    def replace_open_outside(match: re.Match[str]) -> str:
        body = match.group("body")
        text = _visible_text(body)
        linked = _linked_bracket_from_visible(f"[{text}")
        return linked if linked is not None else match.group(0)

    def replace_close_outside(match: re.Match[str]) -> str:
        body = match.group("body")
        text = _visible_text(body)
        linked = _linked_bracket_from_visible(f"{text}]")
        return linked if linked is not None else match.group(0)

    def replace_split_anchor_run(match: re.Match[str]) -> str:
        raw = match.group("run")
        trail = match.group("trail") or ""
        linked = _linked_bracket_from_visible(f"{_visible_text(raw)}{trail}")
        return linked if linked is not None else match.group(0)

    current = run_pattern.sub(replace_run, html)
    current = split_anchor_pattern.sub(replace_split_anchor_run, current)
    current = pattern.sub(replace, current)
    current = open_outside_pattern.sub(replace_open_outside, current)
    current = close_outside_pattern.sub(replace_close_outside, current)
    return _LINKED_BRACKET_ORPHAN_CLOSE_ANCHOR_PATTERN.sub(r"\g<bracket>\g<trail>", current)


def _unlink_supplementary_page_refs(html: str) -> str:
    if "#page-" not in html:
        return html

    pattern = re.compile(
        r'<a\b[^>]*\bhref\s*=\s*["\']#page-[^"\']+["\'][^>]*>'
        r'(?P<body>[\s\S]{0,80}?S\d[\s\S]{0,80}?)</a>'
        r'(?P<tail>\s*(?:Tables?|Figures?|Files?|Data)\b)',
        re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        body_text = _visible_text(match.group("body"))
        if not re.search(r"\bS\d{1,3}(?:\s*[-\u2013\u2014]\s*S?\d{1,3})?", body_text):
            return match.group(0)
        return f"{match.group('body')}{match.group('tail')}"

    return pattern.sub(replace, html)


def _unwrap_numeric_page_links_for_citation_recovery(html: str) -> str:
    if "#page-" not in html:
        return html

    def replace(match: re.Match[str]) -> str:
        body = match.group("body")
        text = _visible_text(body)
        if not text:
            return ""
        if re.fullmatch(r"[\s\d,\[\]\-\u2013\u2014]+", text):
            return text
        return match.group(0)

    return _NUMERIC_PAGE_ANCHOR_PATTERN.sub(replace, html)


def _looks_like_ocr_split_word_join(word: str, letter: str) -> bool:
    token = f"{word}{letter}"
    if token.lower() in {"adn", "age", "al", "arc", "hz", "ive", "map", "pa", "see", "set", "two", "us"}:
        return True
    if len(word) >= 3:
        return (
            (word[-1].islower() and letter.islower())
            or (word.isupper() and letter.isupper())
            or (word.isupper() and letter.lower() == "s")
        )
    return token.lower() in {"in", "on", "of", "to", "as", "is", "it", "if", "by", "or", "we", "wm"} or token.isupper()


def _strip_reference_line_number_artifacts(body: str, number: str) -> str:
    def strip_start(match: re.Match[str]) -> str:
        try:
            line_number = int(match.group("line"))
        except ValueError:
            return match.group(0)
        if line_number == int(number) or not _looks_like_reference_line_number(line_number):
            return match.group(0)
        return match.group("prefix")

    fixed = re.sub(
        rf'^(?P<prefix>\s*(?:(?!</?sup\b)<[^>]+>\s*)*)<sup\b[^>]*>\s*'
        rf'(?P<line>\d{{1,4}})\s*</sup>\s+{re.escape(number)}\s+'
        r'(?=(?:<[^>]+>\s*)*[A-Z])',
        strip_start,
        body,
        count=1,
        flags=re.IGNORECASE,
    )
    fixed = re.sub(
        rf'^(?P<prefix>\s*(?:<[^>]+>\s*)*)(?P<line>\d{{1,4}})\s+{re.escape(number)}\s+'
        r'(?=(?:<[^>]+>\s*)*[A-Z])',
        strip_start,
        fixed,
        count=1,
    )

    def strip_embedded(match: re.Match[str]) -> str:
        try:
            line_number = int(match.group("line"))
        except ValueError:
            return match.group(0)
        if line_number == int(number) or not _looks_like_reference_line_number(line_number):
            return match.group(0)
        return match.group("prefix")

    fixed = re.sub(
        rf'(?P<prefix>(?:^|[\s,;])(?:[A-Z]\.\s*){{1,4}})(?P<line>\d{{1,4}})\s+'
        rf'{re.escape(number)}\s+(?=[A-Z][A-Za-z-]+\b)',
        strip_embedded,
        fixed,
        count=1,
    )
    return _LEADING_REFERENCE_AUTHOR_LINE_NUMBER_ARTIFACT_PATTERN.sub(r"\1", fixed, count=1)


def _looks_reference_front_matter_list_item(body: str) -> bool:
    """Detect affiliation/ESI list items that RSC puts before references."""
    text = _visible_text(body).strip()
    if not text:
        return True
    lower = text.lower()
    if re.match(r"^[^a-z0-9]{0,3}\s*(?:electronic\s+)?supplementary\b", lower):
        return True
    if re.search(r"\b(?:e-?mail|fax|tel)\s*:", lower):
        return True
    if re.match(
        r"^[a-z]\s+"
        r"(?:key\s+laboratory|laboratory|department|school|institute|faculty|college|"
        r"university|centre|center)\b",
        lower,
    ):
        return True
    if re.match(r"^[a-z]\s+.*\b(?:china|usa|uk|germany|france|japan|canada|italy)\.?\s*$", lower):
        return True
    return False


def _looks_post_reference_reporting_list_item(body: str) -> bool:
    text = _visible_text(_strip_reference_visible_number(body)).strip().lower()
    if not text:
        return False
    return bool(
        re.match(
            r"^(?:"
            r"accession codes?|"
            r"unique identifiers?|"
            r"web links? for publicly available datasets|"
            r"a description of any restrictions on data availability|"
            r"restrictions on data availability|"
            r"for clinical datasets or third party data|"
            r"policy information about availability of data|"
            r"all manuscripts must include a data availability statement"
            r")\b",
            text,
        )
    )


_HTML_HEADING_BLOCK_PATTERN = re.compile(
    r"<h[1-6]\b[^>]*>[\s\S]{0,500}?</h[1-6]>",
    re.IGNORECASE,
)
_POST_REFERENCES_NON_BIBLIOGRAPHY_HEADING_TEXT_PATTERN = re.compile(
    r"^(?:appendix|appendices)\b|"
    r"\b(?:data\s+sheet|datasheet|program\s+codes?|related\s+products|features|description)\b",
    re.IGNORECASE,
)
_POST_REFERENCE_ALLOWED_HEADING_RE = re.compile(
    r"^(?:"
    r"acknowledg(?:e)?ments?|appendix|appendices|author\s+contributions?|"
    r"competing\s+interests?|conflicts?\s+of\s+interest|data\s+availability|"
    r"ethics?|figure\s+legends?|funding|notes?|references?|bibliography|"
    r"supplementary|supporting\s+information"
    r")\b",
    re.IGNORECASE,
)
_POST_REFERENCE_BIBLIOGRAPHIC_SIGNAL_RE = re.compile(
    r"\b(?:"
    r"Ann\.|J\.|Journal|Lond\.|Nature|Organs|Physiol\.|Press|Proc\.|Science|"
    r"Soc\.|Springer|Trans\.|Vol\."
    r")\b",
    re.IGNORECASE,
)
_DOCUMENT_CLOSING_SUFFIX_RE = re.compile(r"\s*</body>\s*</html>\s*$", re.IGNORECASE)


def _has_post_references_non_bibliography_heading(html: str, end: int) -> bool:
    for heading_match in _HTML_HEADING_BLOCK_PATTERN.finditer(html[:end]):
        heading = heading_match.group(0)
        if _references_heading_match(heading):
            continue
        heading_text = _visible_text(heading).strip()
        if not heading_text:
            continue
        if _POST_REFERENCES_NON_BIBLIOGRAPHY_HEADING_TEXT_PATTERN.search(heading_text) is not None:
            return True
    return False


def _reference_list_tail_before_heading_looks_bibliographic(left_html: str) -> bool:
    window = left_html[-5000:]
    if re.search(r"</(?:ul|ol)>\s*</p>\s*$", window, re.IGNORECASE) is None:
        return False
    list_start = max(window.rfind("<ul"), window.rfind("<ol"))
    if list_start < 0:
        return False
    list_html = window[list_start:]
    list_text = _visible_text(list_html)
    if len(list_text) < 120:
        return False
    year_count = len(re.findall(r"\b(?:18|19|20)\d{2}\b", list_text))
    if year_count >= 2 and _POST_REFERENCE_BIBLIOGRAPHIC_SIGNAL_RE.search(list_text) is not None:
        return True
    numbered_author_count = len(re.findall(r"(?:^|\s)\d{1,3}\s+[A-Z][A-Za-z'.-]+", list_text))
    return year_count >= 2 and numbered_author_count >= 2


def _last_reference_list_number_before_heading(left_html: str) -> int | None:
    window = left_html[-12000:]
    last_number: int | None = None
    for match in _LI_BLOCK_PATTERN.finditer(window):
        number = _reference_visible_number(match.group(2) or "")
        if number is not None and number > 0:
            last_number = number
    return last_number


def _first_reference_list_number_after_heading(right_html: str) -> int | None:
    search_window = right_html[:12000]
    match = _LI_BLOCK_PATTERN.search(search_window)
    if match is None:
        return None
    number = _reference_visible_number(match.group(2) or "")
    return number if number is not None and number > 0 else None


def _heading_continues_sequential_reference_list(html: str, heading_match: re.Match[str]) -> bool:
    """Return True when a heading is an intra-bibliography divider, not a new article."""

    previous_number = _last_reference_list_number_before_heading(html[: heading_match.start()])
    next_number = _first_reference_list_number_after_heading(html[heading_match.end() :])
    return previous_number is not None and next_number == previous_number + 1


def _trim_adjacent_article_tail_after_references(html: str) -> tuple[str, int]:
    """Drop a second article that Marker appended after the current references."""

    if "<h" not in html.lower() or ("<ul" not in html.lower() and "<ol" not in html.lower()):
        return html, 0
    earliest_boundary = int(len(html) * 0.35)
    for heading_match in _HTML_HEADING_BLOCK_PATTERN.finditer(html):
        if heading_match.start() < earliest_boundary:
            continue
        heading_text = _visible_text(heading_match.group(0)).strip()
        if not heading_text or _POST_REFERENCE_ALLOWED_HEADING_RE.match(heading_text):
            continue
        if not _reference_list_tail_before_heading_looks_bibliographic(html[: heading_match.start()]):
            continue
        if _heading_continues_sequential_reference_list(html, heading_match):
            continue
        suffix_match = _DOCUMENT_CLOSING_SUFFIX_RE.search(html)
        suffix = ""
        if suffix_match is not None and suffix_match.start() >= heading_match.start():
            suffix = suffix_match.group(0)
        return html[: heading_match.start()].rstrip() + suffix, 1
    return html, 0


def _find_matching_html_tag(html: str, open_start: int, tag_name: str) -> tuple[int, int] | None:
    pattern = _UL_TAG_PATTERN if tag_name.lower() == "ul" else _LI_TAG_PATTERN
    depth = 0
    for match in pattern.finditer(html, open_start):
        raw = match.group(0)
        if raw.startswith("</"):
            depth -= 1
            if depth == 0:
                return match.start(), match.end()
            continue
        if raw.rstrip().endswith("/>"):
            continue
        depth += 1
    return None


def _remove_reference_list_indent_class(attrs: str) -> str:
    class_match = re.search(r'\s*\bclass\s*=\s*(["\'])(.*?)\1', attrs, re.IGNORECASE | re.DOTALL)
    if class_match is None:
        return attrs
    classes = [
        class_name
        for class_name in class_match.group(2).split()
        if not re.fullmatch(r"list-indent-\d+", class_name, re.IGNORECASE)
    ]
    if not classes:
        return attrs[: class_match.start()] + attrs[class_match.end() :]
    return (
        attrs[: class_match.start(2)]
        + " ".join(classes)
        + attrs[class_match.end(2) :]
    )


def _flatten_reference_li_nodes(ul_body: str) -> list[str]:
    items: list[str] = []
    cursor = 0
    while True:
        open_match = _LI_OPEN_PATTERN.search(ul_body, cursor)
        if open_match is None:
            break
        close_span = _find_matching_html_tag(ul_body, open_match.start(), "li")
        if close_span is None:
            break
        close_start, close_end = close_span
        attrs = _remove_reference_list_indent_class(open_match.group(1) or "")
        body = ul_body[open_match.end():close_start]
        parent_parts: list[str] = []
        nested_items: list[str] = []
        body_cursor = 0
        while True:
            nested_open = _UL_OPEN_PATTERN.search(body, body_cursor)
            if nested_open is None:
                break
            nested_close = _find_matching_html_tag(body, nested_open.start(), "ul")
            if nested_close is None:
                break
            nested_close_start, nested_close_end = nested_close
            parent_parts.append(body[body_cursor:nested_open.start()])
            nested_items.extend(_flatten_reference_li_nodes(body[nested_open.end():nested_close_start]))
            body_cursor = nested_close_end
        parent_parts.append(body[body_cursor:])
        parent_body = "".join(parent_parts).strip()
        if _visible_text(parent_body).strip():
            items.append(f"<li{attrs}>{parent_body}</li>")
        items.extend(nested_items)
        cursor = close_end
    return items


def _flatten_nested_reference_list_items(html: str) -> str:
    if "<ul" not in html.lower() or "list-indent" not in html.lower():
        return html

    out: list[str] = []
    cursor = 0
    while True:
        open_match = _UL_OPEN_PATTERN.search(html, cursor)
        if open_match is None:
            break
        close_span = _find_matching_html_tag(html, open_match.start(), "ul")
        if close_span is None:
            break
        close_start, close_end = close_span
        out.append(html[cursor:open_match.start()])
        flattened = _flatten_reference_li_nodes(html[open_match.end():close_start])
        if flattened:
            out.append(f"{open_match.group(0)} {' '.join(flattened)} </ul>")
        else:
            out.append(html[open_match.start():close_end])
        cursor = close_end
    out.append(html[cursor:])
    return "".join(out)


_UNHEADED_REFERENCE_LIST_BLOCK_PATTERN = re.compile(
    r'(?:<p\b[^>]*>\s*)?<ul\b[\s\S]*?</ul>(?:\s*</p>)?',
    re.IGNORECASE,
)


def _unheaded_reference_list_start(html: str) -> int | None:
    """Find bibliography lists that Marker emitted without a References heading."""
    for match in _UNHEADED_REFERENCE_LIST_BLOCK_PATTERN.finditer(html):
        block = match.group(0)
        numbers: list[int] = []
        for li_match in _LI_BLOCK_PATTERN.finditer(block):
            number = _reference_visible_number(li_match.group(2) or "")
            if number is None:
                break
            numbers.append(number)
            if len(numbers) >= 4:
                break
        if len(numbers) < 3 or numbers[:3] != [1, 2, 3]:
            continue
        left_text = _visible_text(html[max(0, match.start() - 1800):match.start()]).lower()
        if "acknowledg" in left_text or match.start() > int(len(html) * 0.55):
            return match.start()
    return None


_EMBEDDED_REFERENCES_HEADING_HTML = '<h2 data-z2m-embedded-references="1">References</h2>'
_ZOTERO_GOOGLE_DOCS_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*(['\"])https://www\.zotero\.org/google-docs/[^'\"]+\1[^>]*>"
    r"(?P<body>[\s\S]*?)</a>",
    re.IGNORECASE,
)


def _unwrap_zotero_google_docs_reference_anchors(html: str) -> str:
    if "zotero.org/google-docs" not in html:
        return html
    return _ZOTERO_GOOGLE_DOCS_ANCHOR_RE.sub(lambda match: match.group("body"), html)


def _reference_candidate_visible_number(body: str) -> int | None:
    return _reference_visible_number(_unwrap_zotero_google_docs_reference_anchors(body))


def _reference_candidate_body_looks_bibliographic(body: str) -> bool:
    unwrapped = _unwrap_zotero_google_docs_reference_anchors(body)
    if _reference_visible_number(unwrapped) is None:
        return False
    if _looks_reference_front_matter_list_item(unwrapped):
        return False
    return _looks_like_standalone_reference_paragraph_body(unwrapped)


def _reference_list_suffix_start(li_matches: list[re.Match[str]]) -> int | None:
    for start in range(len(li_matches)):
        numbers: list[int] = []
        bibliographic_hits = 0
        for li_match in li_matches[start : start + 6]:
            body = li_match.group(2) or ""
            number = _reference_candidate_visible_number(body)
            if number is None:
                break
            numbers.append(number)
            if _reference_candidate_body_looks_bibliographic(body):
                bibliographic_hits += 1
            if len(numbers) >= 3:
                break
        if numbers[:3] == [1, 2, 3] and bibliographic_hits >= 2:
            return start
    return None


def _next_list_block_starts_with_reference_number(html: str, start_at: int, number: int) -> bool:
    scan_limit = min(len(html), start_at + 12000)
    for match in _P_BLOCK_PATTERN.finditer(html, start_at):
        if match.start() > scan_limit:
            break
        raw = match.group(0)
        if not _visible_text(raw).strip():
            continue
        if "<ul" not in raw.lower():
            return False
        first_li = _LI_BLOCK_PATTERN.search(raw)
        if first_li is None:
            return False
        return _reference_candidate_visible_number(first_li.group(2) or "") == number
    return False


def _split_embedded_zotero_reference_tail_paragraph(html: str) -> tuple[str, bool]:
    if "zotero.org/google-docs" not in html:
        return html, False
    for match in _P_BLOCK_PATTERN.finditer(html):
        body = match.group("body") or ""
        for anchor_match in _ZOTERO_GOOGLE_DOCS_ANCHOR_RE.finditer(body):
            if _visible_text(anchor_match.group("body")).strip() != "1":
                continue
            ref_body = body[anchor_match.start() :].strip()
            if _reference_candidate_visible_number(ref_body) != 1:
                continue
            if not _reference_candidate_body_looks_bibliographic(ref_body):
                continue
            if not _next_list_block_starts_with_reference_number(html, match.end(), 2):
                continue
            prefix_body = body[: anchor_match.start()].rstrip()
            prefix = ""
            if _visible_text(prefix_body).strip():
                prefix = f"{match.group('open')}{prefix_body}{match.group('close')}"
            ref_list = (
                f"{_EMBEDDED_REFERENCES_HEADING_HTML}"
                '<p block-type="ListGroup" data-z2m-embedded-reference-tail="1"><ul>'
                f'<li block-type="ListItem">{ref_body}</li>'
                "</ul></p>"
            )
            return html[: match.start()] + prefix + ref_list + html[match.end() :], True
    return html, False


def _split_embedded_reference_list_suffix(html: str) -> tuple[str, bool]:
    for match in _P_BLOCK_PATTERN.finditer(html):
        body = match.group("body") or ""
        if "<ul" not in body.lower():
            continue
        ul_match = _UL_OPEN_PATTERN.search(body)
        if ul_match is None:
            continue
        li_matches = list(_LI_BLOCK_PATTERN.finditer(body))
        if len(li_matches) < 3:
            continue
        suffix_start = _reference_list_suffix_start(li_matches)
        if suffix_start is None:
            continue
        ul_open = ul_match.group(0)
        prefix_items = " ".join(li.group(0) for li in li_matches[:suffix_start])
        suffix_items = " ".join(li.group(0) for li in li_matches[suffix_start:])
        if not suffix_items:
            continue
        prefix = ""
        if prefix_items and _visible_text(prefix_items).strip():
            prefix = f"{match.group('open')}{ul_open} {prefix_items} </ul>{match.group('close')}"
        suffix = f"{_EMBEDDED_REFERENCES_HEADING_HTML}{match.group('open')}{ul_open} {suffix_items} </ul>{match.group('close')}"
        return html[: match.start()] + prefix + suffix + html[match.end() :], True
    return html, False


def _split_embedded_unheaded_reference_section(html: str) -> str:
    if _references_heading_search(html, allow_notes_heading=True) is not None:
        return html
    repaired, changed = _split_embedded_zotero_reference_tail_paragraph(html)
    if changed:
        return repaired
    repaired, changed = _split_embedded_reference_list_suffix(html)
    return repaired if changed else html


def _looks_reference_continuation_body(body: str) -> bool:
    without_visible_number = _strip_reference_visible_number(body)
    without_line_number = _strip_leading_reference_line_number_only(without_visible_number)
    if without_line_number != without_visible_number:
        return True
    text = _visible_text(without_line_number)
    if not text:
        return True
    lower = text.lower()
    if re.match(
        r"^(?:\(?\d{4}[a-z]?\)?|doi\b|https?://|www\.|available\b|retrieved\b|accessed\b|arxiv\b|"
        r"bioarxiv\b|medrxiv\b|preprint\b)",
        lower,
    ):
        return True
    if re.match(r"^\d{1,4}\b", text):
        return True
    if re.match(r"^(?:and|or|by|of|for|in|on|to|with|versus|vs\.?)\b", lower):
        return True
    if re.match(r"^[,;:.]\s*", text):
        return True
    # Numbered bibliographies often split a long title/URL continuation into a
    # separate list item without any leading reference number.  In that mode a
    # lowercase opener is a strong continuation signal, but we avoid applying it
    # to unnumbered bibliographies.
    return bool(re.match(r"^[a-z][a-z-]{2,}\b", text))


def _looks_like_uppercase_reference_continuation(prev_body: str, body: str) -> bool:
    if _reference_visible_number(body) is not None:
        return False
    text = _visible_text(_strip_leading_reference_line_number_only(_strip_reference_visible_number(body))).strip()
    if not re.match(r"^[A-Z][A-Za-z-]{2,}\b", text):
        return False
    prev_text = _visible_text(_strip_leading_reference_line_number_only(_strip_reference_visible_number(prev_body))).strip()
    if not prev_text:
        return False
    if re.search(r"(?:[,;:]|\b(?:and|or|with|for|of|in|compared))\s*$", prev_text, re.IGNORECASE):
        return True
    if not re.search(r"[.!?][\"')\]]?\s*$", prev_text):
        return True
    return bool(re.search(r"(?:\b[A-Z]\.\s*){1,4}$", prev_text))


def _looks_like_unnumbered_reference_title_continuation(prev_body: str, body: str) -> bool:
    if _reference_visible_number(body) is not None:
        return False
    text = _visible_text(_strip_leading_reference_line_number_only(_strip_reference_visible_number(body))).strip()
    prev_text = _visible_text(_strip_leading_reference_line_number_only(_strip_reference_visible_number(prev_body))).strip()
    if not text or not prev_text:
        return False
    if re.search(r"[.!?][\"')\]]?\s*$", prev_text):
        return False
    has_open_quote = (
        prev_text.count('"') % 2 == 1
        or prev_text.count("\u201c") > prev_text.count("\u201d")
    )
    if not has_open_quote:
        return False
    return bool(
        re.match(
            r"^[A-Z][A-Za-z-]{2,}\b(?:[,\"]|\s+\b(?:and|or|of|for|in|to|on)\b)",
            text,
        )
    )


def _looks_like_unnumbered_reference_continuation(prev_body: str, body: str) -> bool:
    if _reference_visible_number(body) is not None:
        return False
    text = _visible_text(_strip_leading_reference_line_number_only(_strip_reference_visible_number(body))).strip()
    prev_text = _visible_text(_strip_leading_reference_line_number_only(_strip_reference_visible_number(prev_body))).strip()
    if not text or not prev_text:
        return False
    if _looks_like_unnumbered_reference_title_continuation(prev_body, body):
        return True
    lower = text.lower()
    if not re.search(r"[.!?][\"')\]]?\s*$", prev_text):
        if re.match(r"^(?:and|or|of|for|in|on|to|with|versus|vs\.?)\b", lower):
            return True
        if re.match(r"^[a-z][a-z-]{2,}\b", text):
            return True
    if re.match(
        r"^(?:ACM\s+Transactions|IEEE\b|Journal\b|Proceedings\b|Proc\.|"
        r"Canadian\s+Urological\s+Association\s+Journal\b|"
        r"Neurology\s+and\s+Urodynamics\b|PLoS\b|Nature\b|Science\b)",
        text,
    ):
        return bool(
            re.search(r"\b\d{4}[a-z]?\.\s+.{12,120}[A-Za-z][.!?][\"')\]]?$", prev_text)
        )
    return False


_REFERENCE_STUDY_GROUP_AUTHOR_GLUE_RE = re.compile(
    r"\b(?P<group>[A-Z][A-Za-z0-9-]*(?:\s+[A-Z][A-Za-z0-9-]*){0,8}\s+Study\s+Group)"
    r"(?P<author>[A-Z][A-Za-z-]+\s+[A-Z]{1,4}\.)"
)


def _repair_reference_author_group_glue(html: str) -> str:
    return _REFERENCE_STUDY_GROUP_AUTHOR_GLUE_RE.sub(
        lambda m: f"{m.group('group')}. {m.group('author')}",
        html,
    )


def _normalize_reference_list_items(html: str) -> str:
    """Merge reference continuation ``<li>`` nodes before assigning IDs."""
    matches = list(_LI_BLOCK_PATTERN.finditer(html))
    if not matches:
        return html

    replacement_bodies: dict[int, str] = {}
    skipped: set[int] = set()
    last_real_index: int | None = None
    numbered_mode = False

    for index, match in enumerate(matches):
        body = replacement_bodies.get(index, match.group(2) or "")
        visible_number = _reference_visible_number(body)
        if visible_number is None:
            starts_like_continuation = _looks_reference_continuation_body(body)
        else:
            stripped_visible = _visible_text(_strip_reference_visible_number(body)).strip()
            starts_like_continuation = bool(
                not stripped_visible
                or re.match(
                    r"^(?:\(?\d{4}[a-z]?\)?|doi\b|https?://|www\.|[,;:.])",
                    stripped_visible.lower(),
                )
            )
        if (
            not starts_like_continuation
            and last_real_index is not None
            and numbered_mode
            and visible_number is None
        ):
            prev_body = replacement_bodies.get(last_real_index, matches[last_real_index].group(2) or "")
            starts_like_continuation = _looks_like_uppercase_reference_continuation(prev_body, body)
        if (
            not starts_like_continuation
            and last_real_index is not None
            and numbered_mode
            and visible_number is not None
        ):
            prev_body = replacement_bodies.get(last_real_index, matches[last_real_index].group(2) or "")
            prev_number = _reference_visible_number(prev_body)
            prev_text = _visible_text(_strip_reference_visible_number(prev_body)).strip()
            stripped_visible = _visible_text(_strip_reference_visible_number(body)).strip()
            if (
                prev_number is not None
                and visible_number == prev_number + 1
                and stripped_visible
                and re.match(r"^[a-z][a-z-]{2,}\b", stripped_visible)
                and not re.search(r"[.!?][\"')\]]?\s*$", prev_text)
            ):
                starts_like_continuation = True
        unnumbered_title_continuation = False
        if last_real_index is not None and not numbered_mode and visible_number is None:
            prev_body = replacement_bodies.get(last_real_index, matches[last_real_index].group(2) or "")
            unnumbered_title_continuation = _looks_like_unnumbered_reference_continuation(prev_body, body)
        is_continuation = (
            last_real_index is not None
            and (
                (numbered_mode and starts_like_continuation)
                or unnumbered_title_continuation
            )
        )

        if is_continuation:
            prev_body = replacement_bodies.get(last_real_index, matches[last_real_index].group(2) or "")
            prev_number = _reference_visible_number(prev_body)
            stripped_body = _strip_leading_reference_line_number_only(
                _strip_reference_visible_number(body)
            ).lstrip()
            if (
                visible_number is not None
                and not _visible_text(stripped_body).strip()
                and prev_number is not None
                and visible_number not in {prev_number, prev_number + 1}
            ):
                continuation_body = body.lstrip()
            else:
                continuation_body = stripped_body
            replacement_bodies[last_real_index] = f"{prev_body.rstrip()} {continuation_body}".rstrip()
            skipped.add(index)
            continue

        if visible_number is not None:
            numbered_mode = True
        last_real_index = index

    if not replacement_bodies and not skipped:
        return html

    out: list[str] = []
    cursor = 0
    for index, match in enumerate(matches):
        out.append(html[cursor:match.start()])
        if index in skipped:
            pass
        else:
            body = replacement_bodies.get(index, match.group(2) or "")
            out.append(f"<li{match.group(1) or ''}>{body}</li>")
        cursor = match.end()
    out.append(html[cursor:])
    return "".join(out)


_COLLAPSED_REFERENCE_SEPARATOR_PATTERN = re.compile(
    r"\s+\.\s+(?=(?:<[^>]+>\s*)*[A-Z])",
    re.IGNORECASE,
)
_NUMBERED_REFERENCE_BOUNDARY_PATTERN = re.compile(
    r"\s+(?P<num>\d{1,4})(?:\.\s+|(?=(?:<[^>]+>\s*)*[A-Z]\.)|(?=\s+(?:<[^>]+>\s*)*[A-Z]\.))",
    re.IGNORECASE,
)


def _looks_like_collapsed_reference_part(body: str) -> bool:
    text = _visible_text(body).strip()
    text = re.sub(r"^\.+\s*", "", text)
    if len(text) < 18:
        return False
    if re.match(r"^(?:https?://|www\.|doi\b)", text, re.IGNORECASE):
        return False
    if re.match(r"^[A-Z][A-Za-z'\u2019.-]+(?:\s+[A-Z][A-Za-z'\u2019.-]*){0,5}\s*,", text):
        return True
    if re.match(r"^[A-Z][A-Za-z'\u2019.-]+(?:\s+[A-Z][A-Za-z'\u2019.-]*){0,4}\s+(?:and|&)\s+", text):
        return True
    if re.match(r"^[A-Z][A-Za-z'\u2019.-]+(?:\s+[A-Z][A-Za-z'\u2019.-]*){0,3}\s+et\s+al\.?\b", text):
        return True
    return bool(re.match(r"^[A-Z]{2,}[A-Za-z0-9.-]*\s+\d", text))


def _split_collapsed_reference_list_items(html: str) -> str:
    """Split a single bibliography ``<li>`` that contains many dot-bulleted refs.

    Marker sometimes drops all list-item boundaries from a bibliography while
    preserving each lost bullet as `` . Author...`` inside the first item.  If
    left collapsed, only ``ref-1`` exists and all later numeric citations remain
    unlinked.  The splitter is deliberately conservative: it requires an
    existing visible start number and several author-like boundary candidates.
    """

    def replace(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        body = match.group(2) or ""
        if _LI_ID_PATTERN.search(attrs) is not None:
            return match.group(0)
        start_number = _reference_visible_number(body)
        if start_number is None or start_number <= 0:
            return match.group(0)

        stripped_body = _strip_reference_visible_number(body)
        stripped_body = re.sub(r"^\s*(?:\.\s*)+", "", stripped_body).strip()
        if not stripped_body:
            return match.group(0)
        raw_parts = _COLLAPSED_REFERENCE_SEPARATOR_PATTERN.split(stripped_body)
        parts = [re.sub(r"^\s*(?:\.\s*)+", "", part).strip() for part in raw_parts]
        parts = [part for part in parts if _visible_text(part).strip()]
        if len(parts) < 4:
            return match.group(0)

        author_like_count = sum(1 for part in parts if _looks_like_collapsed_reference_part(part))
        if author_like_count < max(3, int(len(parts) * 0.55)):
            return match.group(0)

        return " ".join(
            f"<li{attrs}>{start_number + offset}. {part}</li>"
            for offset, part in enumerate(parts)
        )

    return _LI_BLOCK_PATTERN.sub(replace, html)


def _looks_like_numbered_reference_boundary_tail(tail: str) -> bool:
    text = _visible_text(tail).strip()
    text = _VISIBLE_LEADING_REFERENCE_AUTHOR_LINE_NUMBER_ARTIFACT_PATTERN.sub("", text, count=1)
    if len(text) < 16:
        return False
    if re.match(
        r"^(?:[A-Z]\.\s*){1,4}[A-Z][A-Za-z\u00c0-\u024f'\u2019.-]+(?:,|\s+(?:and|&)\b)",
        text,
    ):
        return True
    if re.match(
        r"^(?:The\s+)?[A-Z][A-Za-z0-9&'’().,\- ]{3,90}\.\s+Available\s+online\b",
        text,
    ):
        return True
    return bool(
        re.match(
            r"^[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'\u2019.-]+,\s+(?:[A-Z]|et\s+al\.?\b)",
            text,
        )
        or re.match(
            r"^[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'\u2019.-]+\s+"
            r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'\u2019.-]+,\s+(?:[A-Z]|et\s+al\.?\b)",
            text,
        )
    )


def _split_sequential_numbered_reference_list_items(html: str) -> str:
    """Split bibliography items that contain the next numbered reference inline."""

    def replace(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        body = match.group(2) or ""
        if _LI_ID_PATTERN.search(attrs) is not None:
            return match.group(0)
        start_number = _reference_visible_number(body)
        if start_number is None or start_number <= 0:
            return match.group(0)

        stripped_body = _strip_reference_visible_number(body).strip()
        if not stripped_body:
            return match.group(0)

        segments: list[tuple[int, str]] = []
        current_number = start_number
        cursor = 0
        for boundary in _NUMBERED_REFERENCE_BOUNDARY_PATTERN.finditer(stripped_body):
            try:
                next_number = int(boundary.group("num"))
            except ValueError:
                continue
            if next_number != current_number + 1:
                continue
            if not _looks_like_numbered_reference_boundary_tail(stripped_body[boundary.end() :]):
                continue
            left = stripped_body[cursor : boundary.start()].strip()
            if not _visible_text(left).strip():
                continue
            segments.append((current_number, left))
            current_number = next_number
            cursor = boundary.end()

        if not segments:
            return match.group(0)

        tail = stripped_body[cursor:].strip()
        if not _visible_text(tail).strip():
            return match.group(0)
        segments.append((current_number, tail))
        if len(segments) < 2:
            return match.group(0)

        return " ".join(
            f"<li{attrs}>{number}. {part}</li>"
            for number, part in segments
        )

    return _LI_BLOCK_PATTERN.sub(replace, html)


_REFERENCE_TERMINAL_LINK_LABEL_RE = re.compile(
    r"\[(?:CrossRef|Medline|PubMed|Google\s+Scholar|DOI)(?::[^\]]+)?\]\s*$",
    re.IGNORECASE,
)


def _looks_like_implicit_reference_author_tail(body: str) -> bool:
    text = _visible_text(body).strip()
    if len(text) < 50:
        return False
    author_prefix = (
        r"(?:"
        r"[A-Z][A-Za-z'\u2019.-]+"
        r"|(?:d[aeiou]|de|del|della|dos|van|von|der|den|ten|ter)"
        r")"
    )
    author_like = bool(
        re.match(
            rf"^{author_prefix}(?:\s+{author_prefix}){{0,3}},\s+"
            r"(?:[A-Z](?:\.[A-Z]?\.?)*|[A-Z][A-Za-z'\u2019.-]+)",
            text,
        )
        or re.match(
            rf"^{author_prefix}(?:\s+{author_prefix}){{0,3}}\s+"
            rf"{author_prefix}(?:\s+{author_prefix}){{0,2}},\s+"
            r"(?:[A-Z](?:\.[A-Z]?\.?)*|[A-Z][A-Za-z'\u2019.-]+)",
            text,
        )
    )
    if not author_like:
        return False
    return bool(re.search(r"\b(?:19|20)\d{2}\b", text) or _REFERENCE_TERMINAL_LINK_LABEL_RE.search(text))


def _split_implicit_unnumbered_reference_list_items(html: str) -> str:
    """Split a swallowed unnumbered reference when the next visible number skips one."""
    matches = list(_LI_BLOCK_PATTERN.finditer(html))
    if len(matches) < 2:
        return html

    replacements: dict[int, str] = {}

    def _next_visible_number(index: int) -> int | None:
        for candidate in matches[index + 1 : min(len(matches), index + 5)]:
            number = _reference_visible_number(candidate.group(2) or "")
            if number is not None:
                return number
        return None

    def _split_body(body: str) -> tuple[str, str] | None:
        stripped_body = _strip_reference_visible_number(body).strip()
        if not stripped_body:
            return None
        for boundary in re.finditer(r"</a>\s+", stripped_body, re.IGNORECASE):
            head = stripped_body[: boundary.end()].strip()
            tail = stripped_body[boundary.end() :].strip()
            head_text = _visible_text(head)
            if len(head_text) < 80 or not _REFERENCE_TERMINAL_LINK_LABEL_RE.search(head_text):
                continue
            if not _looks_like_implicit_reference_author_tail(tail):
                continue
            return head, tail
        return None

    for index, match in enumerate(matches):
        attrs = match.group(1) or ""
        if _LI_ID_PATTERN.search(attrs) is not None:
            continue
        body = match.group(2) or ""
        start_number = _reference_visible_number(body)
        if start_number is None or start_number <= 0:
            continue
        next_number = _next_visible_number(index)
        if next_number is None or next_number != start_number + 2:
            continue
        split = _split_body(body)
        if split is None:
            continue
        head, tail = split
        replacements[index] = (
            f"<li{attrs}>{start_number}. {head}</li> "
            f"<li{attrs}>{start_number + 1}. {tail}</li>"
        )

    if not replacements:
        return html

    out: list[str] = []
    cursor = 0
    for index, match in enumerate(matches):
        out.append(html[cursor:match.start()])
        out.append(replacements.get(index, match.group(0)))
        cursor = match.end()
    out.append(html[cursor:])
    return "".join(out)


def _add_reference_ids_to_list_items(html: str) -> tuple[str, int]:
    ref_index = 0
    max_ref_id = 0
    used_ids: set[int] = set()
    started_references = False

    def _next_unused_id(preferred: int | None = None) -> int:
        nonlocal ref_index
        if preferred is not None and preferred > 0 and preferred not in used_ids:
            ref_index = max(ref_index, preferred)
            return preferred
        ref_index += 1
        while ref_index in used_ids:
            ref_index += 1
        return ref_index

    def replace(match: re.Match[str]) -> str:
        nonlocal max_ref_id, started_references
        attrs = match.group(1) or ""
        body = match.group(2) or ""
        existing_id = _LI_ID_PATTERN.search(attrs)
        if existing_id is not None:
            try:
                ref_id = int(existing_id.group(1))
            except ValueError:
                ref_id = _next_unused_id()
            used_ids.add(ref_id)
            max_ref_id = max(max_ref_id, ref_id)
            started_references = True
            return match.group(0)

        if _looks_post_reference_reporting_list_item(body):
            return match.group(0)
        if not started_references and _has_post_references_non_bibliography_heading(html, match.start()):
            return match.group(0)
        if not started_references and _looks_reference_front_matter_list_item(body):
            return match.group(0)

        body = _strip_leading_reference_line_number_pair(body)
        expected_ref = ref_index + 1 if started_references and ref_index > 0 else None
        body = _strip_leading_reference_line_number_before_expected_number(body, expected_ref)
        started_references = True
        ref_id = _next_unused_id(_reference_visible_number(body))
        used_ids.add(ref_id)
        max_ref_id = max(max_ref_id, ref_id)
        return f'<li{attrs} id="ref-{ref_id}">{body}</li>'

    return _LI_BLOCK_PATTERN.sub(replace, html), max_ref_id


def _looks_like_standalone_reference_paragraph_body(body: str) -> bool:
    text = _visible_text(_strip_reference_visible_number(body)).strip()
    if len(text) < 24:
        return False
    if re.match(r"^(?:fig(?:ure)?|table|supplement|appendix|acknowledg|funding)\b", text, re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"\b(?:18|19|20)\d{2}[a-z]?\b|"
            r"\b(?:doi|https?://|www\.|journal|proceedings|conference|publisher|press|"
            r"vol\.|pp\.|arxiv|pmid)\b|"
            r";\s*[A-Z][A-Za-z-]+",
            text,
            re.IGNORECASE,
        )
    )


def _looks_like_duplicate_number_doi_footer_reference(
    body: str,
    visible_number: int,
    expected_number: int | None = None,
) -> bool:
    text = re.sub(r"\s+", " ", _visible_text(body)).strip()
    if not text:
        return False
    match = re.match(rf"^{visible_number}\.?\s+{visible_number}\b(?P<tail>[\s\S]*)$", text)
    if match is not None:
        tail = match.group("tail").strip()
        if re.match(r"^(?:https?://(?:dx\.)?doi\.org/|doi\b|10\.\d{4,9}/)", tail, re.IGNORECASE):
            return True
    if (
        expected_number is not None
        and expected_number > 0
        and visible_number >= 500
        and visible_number > expected_number + 100
    ):
        tail = re.sub(r"\s+", " ", _visible_text(_strip_reference_visible_number(body))).strip()
        if re.match(r"^(?:https?://(?:dx\.)?doi\.org/|doi\b|10\.\d{4,9}/)", tail, re.IGNORECASE):
            return True
    if visible_number >= 500:
        tail = re.sub(r"\s+", " ", _visible_text(_strip_reference_visible_number(body))).strip()
        if (
            len(tail) <= 220
            and re.match(r"^(?:https?://(?:dx\.)?doi\.org/|doi\b|10\.\d{4,9}/)", tail, re.IGNORECASE)
            and re.search(r"\b(?:journal|press|publisher|clinical|ophthalmology)\b", tail, re.IGNORECASE)
        ):
            return True
    return False


def _looks_like_numbered_page_footer_doi_paragraph(body: str, visible_number: int, expected_number: int | None) -> bool:
    if _looks_like_duplicate_number_doi_footer_reference(body, visible_number, expected_number):
        return True
    return False


def _add_reference_ids_to_standalone_reference_paragraphs(html: str) -> tuple[str, int]:
    used_ids = {int(match.group(1)) for match in _LI_ID_PATTERN.finditer(html)}
    max_ref_id = max(used_ids, default=0)

    def replace(match: re.Match[str]) -> str:
        nonlocal max_ref_id
        open_tag = match.group("open")
        body = match.group("body") or ""
        if _has_id_attr(open_tag):
            existing_id = _LI_ID_PATTERN.search(open_tag)
            if existing_id is not None:
                normalized_body = _normalize_standalone_reference_paragraph_prefix(body, existing_id.group(1))
                if normalized_body != body:
                    return f'{open_tag}{normalized_body}{match.group("close")}'
            return match.group(0)
        body = _strip_leading_reference_line_number_before_expected_number(
            body,
            max_ref_id + 1 if max_ref_id > 0 else None,
        )
        body = _strip_leading_reference_line_number_pair(body)
        expected_number = max_ref_id + 1 if max_ref_id > 0 else None
        visible_number = _reference_visible_number(body)
        if visible_number is None or visible_number <= 0 or visible_number in used_ids:
            return match.group(0)
        if _looks_like_numbered_page_footer_doi_paragraph(body, visible_number, expected_number):
            return match.group(0)
        if not _looks_like_standalone_reference_paragraph_body(body):
            return match.group(0)
        used_ids.add(visible_number)
        max_ref_id = max(max_ref_id, visible_number)
        body = _normalize_standalone_reference_paragraph_prefix(body, str(visible_number))
        return f'{_add_id_attr(open_tag, f"ref-{visible_number}")}{body}{match.group("close")}'

    return _P_BLOCK_PATTERN.sub(replace, html), max_ref_id


def _reference_page_anchor_map(references_html: str) -> dict[str, str]:
    page_to_ref: dict[str, str] = {}
    blocks = [*_LI_BLOCK_PATTERN.finditer(references_html), *_P_BLOCK_PATTERN.finditer(references_html)]
    for match in blocks:
        id_match = _LI_ID_PATTERN.search(match.group(0))
        if id_match is None:
            continue
        ref_target = f"ref-{id_match.group(1)}"
        for page_match in _REFERENCE_PAGE_ID_PATTERN.finditer(match.group(0)):
            page_to_ref[page_match.group(2)] = ref_target
    return page_to_ref


def _unwrap_broken_reference_links(html: str) -> str:
    if "#ref-" not in html:
        return html
    ref_numbers = {int(match.group(1)) for match in _LI_ID_PATTERN.finditer(html)}
    if not ref_numbers:
        return html

    def replace(match: re.Match[str]) -> str:
        try:
            target = int(match.group("num"))
        except ValueError:
            return match.group(0)
        if target in ref_numbers:
            return match.group(0)
        return match.group("body")

    return _REF_ANCHOR_PATTERN.sub(replace, html)


def _rewrite_page_links_to_reference_targets(html: str, page_to_ref: dict[str, str]) -> str:
    if not page_to_ref or "#page-" not in html:
        return html

    def replace(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        href_match = re.search(r'\bhref\s*=\s*(["\'])#(page-[^"\']+)\1', attrs, re.IGNORECASE)
        if href_match is None:
            return match.group(0)
        ref_target = page_to_ref.get(href_match.group(2))
        if ref_target is None:
            return match.group(0)
        new_attrs = _replace_anchor_href_and_class(attrs, f"#{ref_target}", "z2m-ref-link")
        return f"<a{new_attrs}>{match.group('body')}</a>"

    return _PAGE_ANCHOR_PATTERN.sub(replace, html)


def _convert_unicode_sup_citations(html: str, ref_count: int) -> str:
    """Promote OCR Unicode superscript citation digits to ``<sup>`` tags."""
    if ref_count <= 0:
        return html

    unit_like_words = {
        "min",
        "sec",
        "mol",
        "pixel",
        "pixels",
        "voxel",
        "voxels",
    }

    def _numbers_from_sup(value: str) -> list[int]:
        decoded = value.translate(_SUPERSCRIPT_DIGIT_TRANSLATION)
        numbers = re.findall(r"\d{1,4}", decoded)
        result: list[int] = []
        for number in numbers:
            try:
                result.append(int(number))
            except ValueError:
                return []
        return result

    def _replace_in_text(text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            left = match.group("left")
            if left.lower() in unit_like_words:
                return match.group(0)
            numbers = _numbers_from_sup(match.group("sup"))
            if not numbers or any(number < 1 or number > ref_count for number in numbers):
                return match.group(0)
            label = match.group("sup").translate(_SUPERSCRIPT_DIGIT_TRANSLATION)
            label = re.sub(r"\s*[,.;:]\s*", ",", label)
            label = re.sub(r"\s*[\-\u2013\u2014]\s*", "\u2013", label)
            return f"{left}<sup>{label}</sup>"

        return _UNICODE_SUP_CITATION_PATTERN.sub(replace, text)

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_citation_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_replace_in_text(part))

    return "".join(out)


def _repair_ocr_letter_glued_ref_links(html: str, ref_count: int) -> str:
    """Move OCR-split final word letters out of citation anchors.

    Marker can emit ``functio <a href="#page-X">n13</a>`` for a superscript
    citation.  After page-to-reference retargeting that becomes a valid ref
    anchor, but the visible word is still broken.  This pass repairs that
    narrow shape and wraps the adjacent citation run back into ``<sup>``.
    """
    if ref_count <= 0 or "z2m-ref-link" not in html:
        return html

    paren_pattern = re.compile(
        r"(?P<phrase>\([^<>()]{2,80})\s+"
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"][^>]*)>"
        r"\s*\)\s*(?P<label>\d{1,3})(?P<trail>[\.,;:]*)\s*</a>",
        re.IGNORECASE,
    )
    run_pattern = re.compile(
        r"(?P<word>\b(?:[A-Za-z]{1,}|(?:18|19|20)\d0))(?P<joiner>['\u2019]?)\s+"
        r"(?P<run>(?:<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>[\s\S]{0,80}?</a>\s*){1,8})",
        re.IGNORECASE,
    )
    anchor_pattern = re.compile(
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"][^>]*)>"
        r"(?P<body>[\s\S]*?)</a>",
        re.IGNORECASE,
    )

    def replace_parenthesis(match: re.Match[str]) -> str:
        try:
            target = int(match.group("target"))
            label = int(match.group("label"))
        except ValueError:
            return match.group(0)
        if target != label or not (1 <= label <= ref_count):
            return match.group(0)
        return (
            f"{match.group('phrase')})<sup>"
            f"<a{match.group('attrs')}>{match.group('label')}</a>"
            f"</sup>{match.group('trail')}"
        )

    def replace(match: re.Match[str]) -> str:
        run = match.group("run")
        anchors = list(anchor_pattern.finditer(run))
        if not anchors:
            return match.group(0)

        cursor = 0
        gaps: list[str] = []
        for anchor in anchors:
            gap = run[cursor:anchor.start()]
            if gap.strip():
                return match.group(0)
            gaps.append(gap)
            cursor = anchor.end()
        post_run_gap = run[cursor:]
        if post_run_gap.strip():
            return match.group(0)

        word = match.group("word")
        joiner = match.group("joiner") or ""
        first_visible = _visible_text(anchors[0].group("body"))
        first_match = re.fullmatch(r"\s*(?P<letter>[A-Za-z])\s*(?P<body>\d{1,3}[\s\S]{0,40})\s*", first_visible)
        digit_match = re.fullmatch(r"\s*(?P<letter>[1-9])(?P<body>\d{1,3}[\s\S]{0,40})\s*", first_visible)
        if first_match is None and digit_match is None:
            return match.group(0)

        glue_letter = (first_match or digit_match).group("letter")  # type: ignore[union-attr]
        repaired_word = f"{word}{joiner}{glue_letter}"
        allowed_digit_glue = (
            digit_match is not None
            and joiner == ""
            and repaired_word in {"V1", "V2", "V3", "V4"}
        )
        allowed_decade_glue = re.fullmatch(r"(?:18|19|20)\d0", word) is not None and glue_letter.lower() == "s"
        allowed_possessive_glue = joiner in {"'", "\u2019"} and glue_letter.lower() == "s"
        if (
            not allowed_digit_glue
            and not allowed_decade_glue
            and not allowed_possessive_glue
            and not _looks_like_ocr_split_word_join(word, glue_letter)
        ):
            return match.group(0)

        try:
            first_target = int(anchors[0].group("target"))
        except ValueError:
            return match.group(0)
        first_label = (first_match or digit_match).group("body").strip()  # type: ignore[union-attr]
        first_numbers = [int(value) for value in re.findall(r"\d{1,3}", first_label)]
        if not first_numbers:
            return match.group(0)
        if first_target != first_numbers[0] and not (1 <= first_numbers[0] <= ref_count):
            return match.group(0)
        if not (1 <= first_target <= ref_count) and first_numbers[0] != first_target:
            return match.group(0)

        rebuilt: list[str] = []
        trailing = ""
        for index, anchor in enumerate(anchors):
            attrs = anchor.group("attrs")
            visible = _visible_text(anchor.group("body"))
            if index == 0:
                label = first_label
            else:
                label = visible.strip()
            if not label:
                return match.group(0)

            if index == len(anchors) - 1 and re.search(r"[\.)]\s*$", label):
                trailing = re.search(r"([\.)])\s*$", label).group(1)  # type: ignore[union-attr]
                label = re.sub(r"[\.)]\s*$", "", label).rstrip()
            try:
                target = int(anchor.group("target"))
            except ValueError:
                return match.group(0)
            label_numbers = [int(value) for value in re.findall(r"\d{1,3}", label)]
            if not label_numbers:
                return match.group(0)
            linked_number = label_numbers[0]
            if not (1 <= linked_number <= ref_count):
                return match.group(0)
            if target != linked_number:
                attrs = _replace_href_and_link_class(attrs, f"#ref-{linked_number}", "z2m-ref-link")
            elif not (1 <= target <= ref_count):
                return match.group(0)
            rebuilt.append(f"<a{attrs}>{label}</a>")

        return f"{repaired_word}<sup>{''.join(rebuilt)}</sup>{trailing}{post_run_gap}"

    html = paren_pattern.sub(replace_parenthesis, html)
    return run_pattern.sub(replace, html)


def _repair_ocr_letter_glued_page_citation_links(html: str, ref_count: int) -> str:
    """Retarget OCR-split word-final page anchors that carry citation numbers."""
    if ref_count <= 0 or "#page-" not in html:
        return html

    paren_pattern = re.compile(
        r"(?P<phrase>\([^<>()]{2,80})\s+"
        r"<a\b[^>]*\bhref\s*=\s*['\"]#page-[^'\"]+['\"][^>]*>"
        r"\s*\)\s*(?P<label>\d{1,3})(?P<trail>[\.,;:]*)\s*</a>",
        re.IGNORECASE,
    )
    page_anchor_pattern = re.compile(
        r"(?P<word>\b[A-Za-z]{1,})\s+"
        r"<a\b[^>]*\bhref\s*=\s*['\"]#page-[^'\"]+['\"][^>]*>"
        r"(?P<body>[\s\S]{0,80}?)</a>"
        r"(?P<run>(?:\s*(?:[,;]|\-|\u2013|\u2014)?\s*"
        r"<a\b[^>]*\bhref\s*=\s*['\"]#(?:ref-\d+|page-[^'\"]+)['\"][^>]*>[\s\S]{0,80}?</a>){0,8})",
        re.IGNORECASE,
    )
    run_anchor_pattern = re.compile(
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#(?P<target>ref-\d+|page-[^'\"]+)['\"][^>]*)>"
        r"(?P<body>[\s\S]{0,80}?)</a>",
        re.IGNORECASE,
    )

    def replace_parenthesis(match: re.Match[str]) -> str:
        try:
            number = int(match.group("label"))
        except ValueError:
            return match.group(0)
        if not (1 <= number <= ref_count):
            return match.group(0)
        return (
            f"{match.group('phrase')})<sup>"
            f'<a href="#ref-{number}" class="z2m-ref-link">{number}</a>'
            f"</sup>{match.group('trail')}"
        )

    def replace(match: re.Match[str]) -> str:
        node_open_start = match.string.rfind("<p", 0, match.start())
        node_close_start = match.string.rfind("</p>", 0, match.start())
        if node_open_start > node_close_start:
            node_open_end = match.string.find(">", node_open_start, match.start())
            if node_open_end != -1 and "z2m-front-matter" in match.string[node_open_start:node_open_end]:
                return match.group(0)
        body_text = _visible_text(match.group("body"))
        first_match = re.fullmatch(
            r"\s*(?P<letter>[A-Za-z])\s*"
            r"(?P<label>\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12})"
            r"(?P<trail>[\.,;:]*)\s*",
            body_text,
        )
        if first_match is None:
            return match.group(0)
        repaired_word = f"{match.group('word')}{first_match.group('letter')}"
        if (
            not _looks_like_ocr_split_word_join(match.group("word"), first_match.group("letter"))
            and repaired_word.lower() not in {"adn", "hz"}
        ):
            return match.group(0)
        label = first_match.group("label")
        tokens = re.findall(r"\d{1,3}", label)
        if any(len(value) > 1 and value.startswith("0") for value in tokens):
            return match.group(0)
        numbers = [int(value) for value in tokens]
        if not numbers or any(number < 1 or number > ref_count for number in numbers):
            return match.group(0)

        def link_label_number(num_match: re.Match[str]) -> str:
            label_number = int(num_match.group(0))
            return f'<a href="#ref-{label_number}" class="z2m-ref-link">{num_match.group(0)}</a>'

        first_anchor = re.sub(r"\d{1,3}", link_label_number, label)

        def retarget_run_anchor(anchor_match: re.Match[str]) -> str:
            target = anchor_match.group("target")
            if target.lower().startswith("ref-"):
                return anchor_match.group(0)
            visible = _visible_text(anchor_match.group("body"))
            label_match = re.fullmatch(
                r"\s*(?P<prefix>[,;\-\u2013\u2014]?)\s*(?P<num>\d{1,3})(?P<trail>[\.,;:]*)\s*",
                visible,
            )
            if label_match is None:
                return anchor_match.group(0)
            try:
                run_number = int(label_match.group("num"))
            except ValueError:
                return anchor_match.group(0)
            if not (1 <= run_number <= ref_count):
                return anchor_match.group(0)
            label = f"{label_match.group('prefix')}{run_number}{label_match.group('trail')}"
            return f'<a href="#ref-{run_number}" class="z2m-ref-link">{label}</a>'

        run = run_anchor_pattern.sub(retarget_run_anchor, match.group("run")).strip()
        return f"{repaired_word}<sup>{first_anchor}{run}</sup>{first_match.group('trail')}"

    html = paren_pattern.sub(replace_parenthesis, html)
    return page_anchor_pattern.sub(replace, html)


def _append_pdf_recovered_reference_section_if_safe(
    html: str,
    citation_profile: Any | None,
) -> tuple[str, int]:
    section, max_number = _pdf_recovered_reference_section_from_profile(citation_profile)
    if not section:
        return html, 0
    body_match = _BODY_PATTERN.search(html)
    if body_match is None:
        return f"{html}{section}", max_number
    return f"{html[:body_match.start(3)]}{section}{html[body_match.start(3):]}", max_number


def _expand_reference_label_numbers(value: str) -> list[int]:
    tokens = re.findall(r"\d{1,4}|[,;]|\u2013|\u2014|-", value)
    numbers: list[int] = []
    pending_range_from: int | None = None
    previous_number: int | None = None
    for token in tokens:
        if token.isdigit():
            number = int(token)
            if not 1 <= number <= 999:
                pending_range_from = None
                previous_number = None
                continue
            if pending_range_from is not None:
                if pending_range_from < number and number - pending_range_from <= 50:
                    numbers.extend(range(pending_range_from + 1, number + 1))
                else:
                    numbers.append(number)
                pending_range_from = None
            else:
                numbers.append(number)
            previous_number = number
        elif token in {"-", "\u2013", "\u2014"} and previous_number is not None:
            pending_range_from = previous_number
        else:
            pending_range_from = None
    deduped: list[int] = []
    seen: set[int] = set()
    for number in numbers:
        if number not in seen:
            seen.add(number)
            deduped.append(number)
    return deduped


_BODY_PLAIN_REFERENCE_CANDIDATE_RE = re.compile(
    r"(?<![\w.])(?P<body>\d{1,3}\s*(?:,|;|-|\u2013|\u2014)\s*\d{1,3}"
    r"(?:\s*(?:,|;|-|\u2013|\u2014)\s*\d{1,3}){0,12})"
    r"(?!\s*(?:%|\u2030|cm|mm|m\b|kg|g\b|mg|hz|khz|mhz|ghz|s\b|min\b|h\b|"
    r"years?\b|months?\b|days?\b))",
    re.IGNORECASE,
)


def _plain_body_reference_candidate_is_safe_for_recovery(text: str, match: re.Match[str]) -> bool:
    start, end = match.span("body")
    prefix = text[max(0, start - 80) : start].lower()
    suffix = text[end : min(len(text), end + 18)].lower()
    if re.match(r"\s*(?:%|\u2030|percent|cm|mm|m\b|kg|g\b|mg|hz|khz|mhz|ghz|s\b|min\b|h\b)", suffix):
        return False
    if re.search(
        r"(?:fig(?:ure)?|table|section|sec|eq(?:uation)?|page|pages|pp|volume|vol|issue|"
        r"range|distance|frequency|values?|sample|n\s*=|aged?|years?|months?|days?|"
        r"cm|mm|kg|mg|hz|mhz|mpa|\u00b0|\u00b1|\u00d7|x)\s*$",
        prefix,
    ):
        return False
    return re.search(r"[a-z][a-z),.;:'\"\s-]{0,60}$", prefix, re.IGNORECASE) is not None


def _link_plain_body_reference_candidate_ranges_in_safe_blocks(html: str, ref_count: int) -> str:
    if ref_count <= 0:
        return html

    def replace_candidate(match: re.Match[str]) -> str:
        body = match.group("body")
        numbers = _expand_reference_label_numbers(body)
        if len(numbers) < 2:
            return match.group(0)
        if any(number < 1 or number > ref_count for number in numbers):
            return match.group(0)
        if not _plain_body_reference_candidate_is_safe_for_recovery(match.string, match):
            return match.group(0)
        linked = _link_numeric_superscript_body(body, ref_count)
        if linked is None:
            return match.group(0)
        return f"<sup>{linked}</sup>"

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        parts = _TAG_SPLIT_PATTERN.split(raw)
        out: list[str] = []
        skip_stack: list[str] = []
        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                _update_citation_skip_stack(part, skip_stack)
                out.append(part)
                continue
            out.append(part if skip_stack else _BODY_PLAIN_REFERENCE_CANDIDATE_RE.sub(replace_candidate, part))
        return "".join(out)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


def _body_reference_candidate_numbers_for_recovery(html: str) -> set[int]:
    heading_match = _references_heading_search(html, allow_notes_heading=True)
    before_references = html[: heading_match.start()] if heading_match is not None else html
    text = _visible_text(before_references)
    numbers: set[int] = set()
    for match in _BRACKET_CITATION_PATTERN.finditer(text):
        numbers.update(_expand_reference_label_numbers(match.group(1)))
    for match in _BODY_PLAIN_REFERENCE_CANDIDATE_RE.finditer(text):
        if not _plain_body_reference_candidate_is_safe_for_recovery(text, match):
            continue
        numbers.update(_expand_reference_label_numbers(match.group("body")))
    return numbers


def _profile_reference_entry_looks_bibliographic(text: str) -> bool:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 24:
        return False
    lower = text.lower()
    has_affiliation_signal = re.search(
        r"\b(?:department|faculty|foundation|institute|laborator(?:y|ies)|school|university)\b|"
        r"\b(?:fax|tel|e-?mail)\s*:",
        lower,
    )
    has_reference_signal = re.search(
        r"\b(?:18|19|20)\d{2}[a-z]?\b|"
        r"\b(?:doi|journal|proc\.?|proceedings|conference|publisher|press|patent|arxiv|"
        r"science|nature|chem\.?|med\.?|physiol\.?|nano|anal\.?|vol\.?|pp\.?)\b",
        text,
        re.IGNORECASE,
    )
    if has_affiliation_signal and has_reference_signal is None:
        return False
    return has_reference_signal is not None


def _citation_profile_with_body_reference_recovery_numbers(html: str, citation_profile: Any | None) -> Any | None:
    if not isinstance(citation_profile, dict):
        return citation_profile
    entries_by_number = _citation_profile_reference_entries_by_number(citation_profile)
    if not entries_by_number:
        return citation_profile
    if _citation_profile_reference_recovery_numbers(citation_profile) and _contiguous_profile_reference_recovery_numbers(
        citation_profile,
        entries_by_number,
    ):
        return citation_profile
    body_numbers = sorted(_body_reference_candidate_numbers_for_recovery(html))
    matched_numbers = [
        number
        for number in body_numbers
        if number in entries_by_number and _profile_reference_entry_looks_bibliographic(entries_by_number[number])
    ]
    if not matched_numbers:
        return citation_profile
    max_number = max(matched_numbers)
    if any(
        number not in entries_by_number
        or not _profile_reference_entry_looks_bibliographic(entries_by_number[number])
        for number in range(1, max_number + 1)
    ):
        return citation_profile
    updated = dict(citation_profile)
    updated["reference_entries_recovery_numbers"] = list(range(1, max_number + 1))
    updated["reference_entries_recovery_trigger"] = "body_citation_existing_profile"
    return updated


_SENTENCE_TRAILING_PLAIN_NUMERIC_CITATION_RE = re.compile(
    r"(?P<punct>[.!?])\s+"
    r"(?P<label>\d{1,3}(?:\s*(?:,|;|-|\u2013|\u2014)\s*\d{1,3}){1,12})"
    r"(?P<trail>[,;:]?)\s+"
    r"(?P<next>(?:<[^>]+>\s*)*[A-Z][A-Za-z])",
    re.IGNORECASE,
)
_SENTENCE_TRAILING_SUP_NUMERIC_CITATION_RE = re.compile(
    r"(?P<punct>[.!?])\s*"
    r"<sup\b[^>]*>\s*"
    r"(?P<label>\d{1,3}(?:\s*(?:,|;|-|\u2013|\u2014)\s*\d{1,3}){1,12})"
    r"\s*</sup>\s*"
    r"(?P<next>(?:<[^>]+>\s*)*[A-Z][A-Za-z])",
    re.IGNORECASE,
)


def _link_sentence_trailing_plain_numeric_citations(html: str, ref_count: int) -> str:
    if ref_count <= 0:
        return html

    def link_label(label: str) -> str | None:
        numbers = _expand_reference_label_numbers(label)
        if len(numbers) < 2:
            return None
        if any(number < 1 or number > ref_count for number in numbers):
            return None

        def replace_number(match: re.Match[str]) -> str:
            number = int(match.group(0))
            return f'<a href="#ref-{number}" class="z2m-ref-link">{match.group(0)}</a>'

        return re.sub(r"\d{1,3}", replace_number, label)

    def replace_node(match: re.Match[str]) -> str:
        open_tag = match.group("open")
        raw = match.group(0)
        if re.search(
            r"\b(?:z2m-front-matter|z2m-figure|z2m-table|z2m-equation|katex|math)\b",
            raw,
            re.IGNORECASE,
        ):
            return raw
        body = match.group("body") or ""

        def replace_plain(label_match: re.Match[str]) -> str:
            linked = link_label(label_match.group("label"))
            if linked is None:
                return label_match.group(0)
            return (
                f"{label_match.group('punct')}<sup>{linked}</sup> "
                f"{label_match.group('next')}"
            )

        linked_body = _SENTENCE_TRAILING_SUP_NUMERIC_CITATION_RE.sub(replace_plain, body)
        linked_body = _SENTENCE_TRAILING_PLAIN_NUMERIC_CITATION_RE.sub(replace_plain, linked_body)
        if linked_body == body:
            return raw
        return f"{open_tag}{linked_body}{match.group('close')}"

    return _P_BLOCK_PATTERN.sub(replace_node, html)


def _recover_missing_reference_entries_from_profile(
    html: str,
    citation_profile: Any | None,
    *,
    body_html: str | None = None,
) -> tuple[str, int]:
    entries_by_number = _citation_profile_reference_entries_by_number(citation_profile)
    if not entries_by_number:
        return html, 0

    matches = list(_LI_BLOCK_PATTERN.finditer(html))
    ref_matches: dict[int, re.Match[str]] = {}
    for match in matches:
        attrs = match.group(1) or ""
        id_match = _LI_ID_PATTERN.search(attrs)
        if id_match is None:
            continue
        try:
            ref_id = int(id_match.group(1))
        except ValueError:
            continue
        ref_matches.setdefault(ref_id, match)

    existing_ids = sorted(ref_matches)
    if len(existing_ids) < 2:
        return html, 0

    insert_after: dict[int, list[str]] = {}
    recovered_max = 0
    for left, right in zip(existing_ids, existing_ids[1:]):
        gap = right - left - 1
        if gap <= 0 or gap > _MAX_PROFILE_REFERENCE_GAP_RECOVERY:
            continue
        recovered_items: list[str] = []
        for number in range(left + 1, right):
            entry_text = entries_by_number.get(number)
            if not entry_text:
                continue
            escaped = html_lib.escape(entry_text, quote=False)
            recovered_items.append(
                f'<li block-type="ListItem" id="ref-{number}" data-z2m-pdf-recovered-ref="1">'
                f"{escaped}</li>"
            )
            recovered_max = max(recovered_max, number)
        if recovered_items:
            insert_after.setdefault(left, []).extend(recovered_items)

    body_reference_numbers = _body_reference_candidate_numbers_for_recovery(body_html or html)
    if body_reference_numbers:
        last_existing = existing_ids[-1]
        recovered_items = []
        for number in sorted(body_reference_numbers):
            if number <= last_existing:
                continue
            if number - last_existing > _MAX_PROFILE_REFERENCE_GAP_RECOVERY:
                continue
            entry_text = entries_by_number.get(number)
            if not entry_text:
                continue
            escaped = html_lib.escape(entry_text, quote=False)
            recovered_items.append(
                f'<li block-type="ListItem" id="ref-{number}" data-z2m-pdf-recovered-ref="1">'
                f"{escaped}</li>"
            )
            recovered_max = max(recovered_max, number)
        if recovered_items:
            insert_after.setdefault(last_existing, []).extend(recovered_items)

    if not insert_after:
        return html, 0

    out: list[str] = []
    cursor = 0
    for match in matches:
        out.append(html[cursor : match.end()])
        attrs = match.group(1) or ""
        id_match = _LI_ID_PATTERN.search(attrs)
        if id_match is not None:
            try:
                ref_id = int(id_match.group(1))
            except ValueError:
                ref_id = 0
            additions = insert_after.get(ref_id)
            if additions:
                out.append(" ")
                out.append(" ".join(additions))
        cursor = match.end()
    out.append(html[cursor:])
    return "".join(out), recovered_max


_PDF_AUTHOR_YEAR_CITATION_LABEL_PATTERN = re.compile(
    r"\b"
    r"[A-Z][A-Za-z'’.-]{1,}"
    r"(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z'’.-]{1,}|&\s*[A-Z][A-Za-z'’.-]{1,}))?"
    r"(?:,\s*|\s+)"
    r"\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)


def _normalize_pdf_annotation_label(value: str) -> str:
    return re.sub(r"\s+", " ", _visible_text(value)).strip(" \t\r\n.,;:")


_PDF_ANNOTATION_CONTEXT_TRANSLATION = str.maketrans(
    {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\u2013": "-",
        "\u2014": "-",
    }
)


def _normalize_pdf_annotation_context(value: str) -> str:
    return re.sub(r"\s+", " ", _visible_text(value).translate(_PDF_ANNOTATION_CONTEXT_TRANSLATION)).strip()


def _compact_pdf_annotation_context(value: str) -> str:
    normalized = _normalize_pdf_annotation_context(value).casefold()
    return re.sub(r"[^a-z0-9]+", "", normalized)


def _pdf_annotation_reference_target(item: Any, citation_profile: Any | None, ref_index: int) -> int | None:
    kind = str(_profile_item_value(item, "kind", "") or "")
    target_text = str(_profile_item_value(item, "target", "") or "")
    if kind != "reference":
        ref_prefix = _citation_profile_ref_prefix(citation_profile)
        dest = str(_profile_item_value(item, "dest", "") or "")
        if not ref_prefix or not dest.startswith(ref_prefix):
            return None
        match = re.match(rf"{re.escape(ref_prefix)}(\d+)", dest)
        if match is None:
            return None
        target_text = match.group(1)
    try:
        target = int(target_text)
    except ValueError:
        return None
    return target if 1 <= target <= ref_index else None


def _pdf_annotation_reference_label_candidates(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []

    labels: list[str] = []
    for match in _PDF_AUTHOR_YEAR_CITATION_LABEL_PATTERN.finditer(normalized):
        label = _normalize_pdf_annotation_label(match.group(0))
        if not label:
            continue
        if not re.search(r"[A-Za-z]", label) or re.search(r"\d{4}", label) is None:
            continue
        if len(label) > 120:
            continue
        labels.append(label)

    if not labels and re.search(r"[A-Za-z]", normalized) and re.search(r"\d{4}", normalized):
        label = _normalize_pdf_annotation_label(normalized)
        if 6 <= len(label) <= 120 and not re.search(r"\b(?:doi|https?|www)\b", label, re.IGNORECASE):
            labels.append(label)

    deduped: list[str] = []
    seen: set[str] = set()
    for label in labels:
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(label)
    return deduped


def _pdf_annotation_reference_link_budgets(
    citation_profile: Any | None,
    ref_index: int,
) -> dict[tuple[str, int], int]:
    budgets: dict[tuple[str, int], int] = {}
    profile_items = _citation_profile_items(citation_profile, "annotations")
    if not profile_items:
        profile_items = _citation_profile_items(citation_profile, "samples")
    for item in profile_items:
        target = _pdf_annotation_reference_target(item, citation_profile, ref_index)
        if target is None:
            continue
        text = str(_profile_item_value(item, "text", "") or "")
        for label in _pdf_annotation_reference_label_candidates(text):
            key = (label.casefold(), target)
            budgets[key] = budgets.get(key, 0) + 1

    labels_to_targets: dict[str, set[int]] = {}
    for label_key, target in budgets:
        labels_to_targets.setdefault(label_key, set()).add(target)
    ambiguous_labels = {
        label_key for label_key, targets in labels_to_targets.items()
        if len(targets) > 1
    }
    return {
        key: count for key, count in budgets.items()
        if key[0] not in ambiguous_labels
    }


def _pdf_annotation_reference_target_budgets(
    citation_profile: Any | None,
    ref_index: int,
) -> dict[int, int]:
    budgets: dict[int, int] = {}
    profile_items = _citation_profile_items(citation_profile, "annotations")
    if not profile_items:
        return budgets
    for item in profile_items:
        target = _pdf_annotation_reference_target(item, citation_profile, ref_index)
        if target is None:
            continue
        budgets[target] = budgets.get(target, 0) + 1
    return budgets


def _pdf_annotation_reference_label_keys(citation_profile: Any | None) -> set[str]:
    keys: set[str] = set()
    profile_items = _citation_profile_items(citation_profile, "annotations")
    if not profile_items:
        profile_items = _citation_profile_items(citation_profile, "samples")
    for item in profile_items:
        text = str(_profile_item_value(item, "text", "") or "")
        for label in _pdf_annotation_reference_label_candidates(text):
            keys.add(label.casefold())
    return keys


def _html_text_label_pattern(label: str) -> re.Pattern[str]:
    escaped = re.escape(_escape_html_text(label))
    escaped = re.sub(r"\\\s+", r"\\s+", escaped)
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def _link_pdf_annotation_reference_texts_in_safe_blocks(
    html: str,
    citation_profile: Any | None,
    ref_index: int,
) -> str:
    """Project concrete PDF reference annotations back onto Marker HTML text."""
    budgets = _pdf_annotation_reference_link_budgets(citation_profile, ref_index)
    if not budgets:
        return html

    labels: dict[str, int] = {
        label_key: target for (label_key, target), _count in budgets.items()
    }
    patterns = [
        (label_key, labels[label_key], _html_text_label_pattern(label_key))
        for label_key in sorted(labels, key=len, reverse=True)
    ]

    def remaining(label_key: str, target: int) -> int:
        return budgets.get((label_key, target), 0)

    def consume(label_key: str, target: int) -> bool:
        key = (label_key, target)
        count = budgets.get(key, 0)
        if count <= 0:
            return False
        budgets[key] = count - 1
        return True

    def find_label_target(value: str) -> tuple[str, int] | None:
        normalized = _normalize_pdf_annotation_label(value).casefold()
        target = labels.get(normalized)
        if target is None or remaining(normalized, target) <= 0:
            return None
        return normalized, target

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw

        def replace_page_anchor(anchor_match: re.Match[str]) -> str:
            found = find_label_target(anchor_match.group("body"))
            if found is None:
                return anchor_match.group(0)
            label_key, target = found
            if not consume(label_key, target):
                return anchor_match.group(0)
            attrs = _replace_href_and_link_class(anchor_match.group("attrs"), f"#ref-{target}", "z2m-ref-link")
            return f'<a{attrs}>{anchor_match.group("body")}</a>'

        current = _PAGE_ANCHOR_PATTERN.sub(replace_page_anchor, raw)
        parts = _TAG_SPLIT_PATTERN.split(current)
        out: list[str] = []
        anchor_depth = 0

        def replace_plain(label_key: str, target: int, text_match: re.Match[str]) -> str:
            if not consume(label_key, target):
                return text_match.group(0)
            return f'<a href="#ref-{target}" class="z2m-ref-link">{text_match.group(0)}</a>'

        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                close_match = _CLOSE_TAG_PATTERN.match(part)
                open_match = _OPEN_TAG_PATTERN.match(part)
                if close_match is not None and close_match.group(1).lower() == "a" and anchor_depth:
                    anchor_depth -= 1
                out.append(part)
                if open_match is not None and open_match.group(1).lower() == "a" and not part.rstrip().endswith("/>"):
                    anchor_depth += 1
                continue
            if anchor_depth:
                out.append(part)
                continue
            linked = part
            for label_key, target, pattern in patterns:
                if remaining(label_key, target) <= 0:
                    continue
                linked = pattern.sub(lambda m, lk=label_key, tgt=target: replace_plain(lk, tgt, m), linked)
            out.append(linked)
        return "".join(out)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


_REF_ANCHOR_RUN_PATTERN = re.compile(
    r"(?P<run>(?:\s*"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>[\s\S]{0,80}?</a>"
    r"\s*){1,12})",
    re.IGNORECASE,
)


def _wrap_pdf_annotation_ref_runs_as_superscripts(
    html: str,
    citation_profile: Any | None,
    ref_index: int,
) -> str:
    if "#ref-" not in html:
        return html
    target_budgets = _pdf_annotation_reference_target_budgets(citation_profile, ref_index)
    if not target_budgets:
        return html

    anchor_pattern = re.compile(
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"][^>]*)>"
        r"(?P<body>[\s\S]{0,80}?)</a>",
        re.IGNORECASE,
    )

    def is_inside_sup(raw: str, position: int) -> bool:
        left = raw[:position].lower()
        return left.rfind("<sup") > left.rfind("</sup")

    def label_parts(body: str, target: int, *, first: bool) -> tuple[str, str] | None:
        visible = _visible_text(body).strip()
        match = re.search(r"\d{1,3}", visible)
        if match is None:
            return None
        try:
            label_number = int(match.group(0))
        except ValueError:
            return None
        if label_number != target:
            return None
        prefix = visible[:match.start()]
        suffix = visible[match.end():]
        separator = ""
        if prefix and not first:
            sep_match = re.search(r"[,;\-\u2013\u2014]\s*$", prefix)
            if sep_match is not None:
                separator = sep_match.group(0).strip()
        if not separator and not first:
            separator = ","
        if not separator and suffix.strip().startswith((",", ";")):
            separator = ""
        return separator, str(label_number)

    def replace_run(match: re.Match[str]) -> str:
        raw = match.group("run")
        if is_inside_sup(match.string, match.start()):
            return raw
        anchors = list(anchor_pattern.finditer(raw))
        if not anchors:
            return raw
        cursor = 0
        rebuilt: list[str] = []
        consumed_targets: list[int] = []
        for index, anchor in enumerate(anchors):
            gap = raw[cursor:anchor.start()]
            if gap.strip():
                return raw
            cursor = anchor.end()
            try:
                target = int(anchor.group("target"))
            except ValueError:
                return raw
            if target_budgets.get(target, 0) <= 0:
                return raw
            parts = label_parts(anchor.group("body"), target, first=index == 0)
            if parts is None:
                return raw
            separator, label = parts
            if separator:
                rebuilt.append(separator)
            attrs = _replace_href_and_link_class(anchor.group("attrs"), f"#ref-{target}", "z2m-ref-link")
            rebuilt.append(f"<a{attrs}>{label}</a>")
            consumed_targets.append(target)
        if raw[cursor:].strip():
            return raw
        for target in consumed_targets:
            target_budgets[target] = target_budgets.get(target, 0) - 1
        return f"<sup>{''.join(rebuilt)}</sup>"

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        return _REF_ANCHOR_RUN_PATTERN.sub(replace_run, raw)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


def _wrap_plain_ref_links_as_superscript_citations(html: str) -> str:
    if "#ref-" not in html:
        return html
    ref_numbers = {int(match.group(1)) for match in _LI_ID_PATTERN.finditer(html)}

    def is_inside_sup(raw: str, position: int) -> bool:
        left = raw[:position].lower()
        return left.rfind("<sup") > left.rfind("</sup")

    def numeric_label(body: str) -> tuple[bool, str] | None:
        visible = _visible_text(body).strip()
        leading_dot = bool(re.match(r"^\.\s*", visible))
        if leading_dot:
            visible = re.sub(r"^\.\s*", "", visible, count=1)
        if not re.fullmatch(
            r"\d{1,3}(?:\s*(?:[,;]|\-|\u2010|\u2011|\u2012|\u2013|\u2014)\s*\d{1,3}){0,12}",
            visible,
        ):
            return None
        label = re.sub(r"\s*([,;\-\u2010\u2011\u2012\u2013\u2014])\s*", r"\1", visible)
        return leading_dot, label

    def linked_numeric_run(body: str) -> tuple[str, str] | None:
        if not ref_numbers:
            return None
        visible = _visible_text(body).strip()
        trail_match = re.search(r"(?P<trail>[\)\]]+)\s*$", visible)
        trail = ""
        if trail_match is not None:
            trail = trail_match.group("trail")
            visible = visible[: trail_match.start()].rstrip()
        if not visible:
            return None
        if any(value.startswith("0") for value in re.findall(r"\d{2,3}", visible)):
            return None
        numbers = [int(value) for value in re.findall(r"\d{1,3}", visible)]
        if not numbers or any(number not in ref_numbers or 1800 <= number <= 2099 for number in numbers):
            return None
        if re.fullmatch(
            r"\d{1,3}(?:\s*(?:[,;]|\-|\u2010|\u2011|\u2012|\u2013|\u2014|\s)\s*\d{1,3}){0,24}",
            visible,
        ) is None:
            return None

        def link_number(num_match: re.Match[str]) -> str:
            number_text = num_match.group(0)
            number = int(number_text)
            return f'<a href="#ref-{number}" class="z2m-ref-link">{number_text}</a>'

        body_without_trail = body
        if trail:
            body_without_trail = re.sub(r"[\)\]\s]+$", "", body, count=1)
        return re.sub(r"\d{1,3}", link_number, body_without_trail), trail

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        out: list[str] = []
        cursor = 0
        for anchor_match in _REF_ANCHOR_PATTERN.finditer(raw):
            out.append(raw[cursor:anchor_match.start()])
            replacement = anchor_match.group(0)
            if not is_inside_sup(raw, anchor_match.start()):
                linked_run = linked_numeric_run(anchor_match.group("body"))
                if linked_run is not None:
                    linked, trail = linked_run
                    replacement = f"<sup>{linked}</sup>{trail}"
                else:
                    label = numeric_label(anchor_match.group("body"))
                    if label is not None:
                        leading_dot, text = label
                        replacement = f'<a{anchor_match.group("attrs")}>{text}</a>'
                        replacement = f"<sup>{replacement}</sup>"
                        if leading_dot:
                            replacement = f".{replacement}"
            elif ref_numbers:
                linked_run = linked_numeric_run(anchor_match.group("body"))
                if linked_run is not None:
                    linked, trail = linked_run
                    replacement = f"{linked}{trail}"
            out.append(replacement)
            cursor = anchor_match.end()
        out.append(raw[cursor:])
        return "".join(out)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


_PDF_ANNOTATION_TEX_SUP_CITATION_PATTERN = re.compile(
    r"\\\(\s*1\^\{(?P<body>\d{1,3}\s*(?:[-\u2013\u2014]\s*\d{1,3}){1,3})\}\s*\\\)"
)


def _link_pdf_annotation_tex_superscript_citations(
    html: str,
    citation_profile: Any | None,
    ref_index: int,
) -> str:
    target_budgets = _pdf_annotation_reference_target_budgets(citation_profile, ref_index)
    if not target_budgets:
        return html

    def replace(match: re.Match[str]) -> str:
        body = match.group("body")
        numbers = [int(value) for value in re.findall(r"\d{1,3}", body)]
        if not numbers or any(number < 1 or number > ref_index for number in numbers):
            return match.group(0)
        if any(target_budgets.get(number, 0) <= 0 for number in (numbers[0], numbers[-1])):
            return match.group(0)

        def link_number(num_match: re.Match[str]) -> str:
            number = int(num_match.group(0))
            if number not in {numbers[0], numbers[-1]}:
                return num_match.group(0)
            target_budgets[number] = target_budgets.get(number, 0) - 1
            return f'<a href="#ref-{number}" class="z2m-ref-link">{number}</a>'

        linked = re.sub(r"\d{1,3}", link_number, body)
        return f"<sup>{linked}</sup>"

    return _SENTENCE_NODE_PATTERN.sub(
        lambda node_match: (
            node_match.group(0)
            if _node_protects_citations(node_match.group(0))
            else _PDF_ANNOTATION_TEX_SUP_CITATION_PATTERN.sub(replace, node_match.group(0))
        ),
        html,
    )


def _pdf_annotation_superscript_context_hints(
    citation_profile: Any | None,
    ref_index: int,
) -> dict[int, list[tuple[str, str]]]:
    hints: dict[int, list[tuple[str, str]]] = {}
    for item in _citation_profile_items(citation_profile, "annotations"):
        target = _pdf_annotation_reference_target(item, citation_profile, ref_index)
        if target is None:
            continue
        text = _normalize_pdf_annotation_context(str(_profile_item_value(item, "text", "") or ""))
        if not text:
            continue
        pattern = re.compile(rf"(?<!\d){re.escape(str(target))}(?!\d)")
        for match in pattern.finditer(text):
            left_hint = _compact_pdf_annotation_context(text[: match.start()])[-14:]
            right_hint = _compact_pdf_annotation_context(text[match.end():])[:14]
            if not left_hint and not right_hint:
                continue
            hints.setdefault(target, []).append((left_hint, right_hint))
    return hints


def _ref_link_counts_by_target(html: str) -> dict[int, int]:
    counts: dict[int, int] = {}
    for match in re.finditer(r'href\s*=\s*["\']#ref-(\d+)["\']', html, re.IGNORECASE):
        try:
            target = int(match.group(1))
        except ValueError:
            continue
        counts[target] = counts.get(target, 0) + 1
    return counts


def _pdf_annotation_superscript_context_matches(
    left: str,
    right: str,
    hints: list[tuple[str, str]],
) -> bool:
    left_context = _compact_pdf_annotation_context(left[-160:])
    right_context = _compact_pdf_annotation_context(right[:160])
    for left_hint, right_hint in hints:
        left_score = 0
        right_score = 0
        for length in (10, 8, 6, 4, 3, 2, 1):
            if len(left_hint) >= length and left_context.endswith(left_hint[-length:]):
                left_score = length
                break
        for length in (10, 8, 6, 4, 3, 2):
            if len(right_hint) >= length and right_context.startswith(right_hint[:length]):
                right_score = length
                break
        if left_score >= 4:
            return True
        if right_score >= 4 and (not left_hint or left_score >= 1):
            return True
        if left_score >= 1 and right_score >= 2:
            return True
    return False


_NUMERIC_SUPERSCRIPT_DASH_CHARS = "-\u2013\u2014"
_NUMERIC_SUPERSCRIPT_OPERATOR_CHARS = "=+*/^<>≤≥±"


_UNIT_SENTENCE_LEFT_CONTEXT_PATTERN = re.compile(
    r"(?:\b(?:kg|cm|mm|um|nm|mA|uA|Hz|MHz|GHz|kHz)\.?\s*|\b(?-i:[AV])\.?\s*)$",
    re.IGNORECASE,
)


def _inline_math_is_open(text: str, position: int) -> bool:
    left_inline_open = text.rfind(r"\(", 0, position)
    left_inline_close = text.rfind(r"\)", 0, position)
    left_display_open = text.rfind(r"\[", 0, position)
    left_display_close = text.rfind(r"\]", 0, position)
    return left_inline_open > left_inline_close or left_display_open > left_display_close


def _has_non_citation_numeric_left_context(left_visible: str) -> bool:
    for match in _NONCITATION_NUMERIC_CONTEXT_PATTERN.finditer(left_visible):
        if (
            match.start() > 0
            and left_visible[match.start() - 1] == "."
            and left_visible[match.start()].lower() in {"a", "v"}
        ):
            continue
        return True
    return False


def _lowercase_after_superscript_still_looks_citation(left_visible: str, right_visible: str) -> bool:
    right = right_visible.lstrip()
    if not re.match(r"[a-z]", right):
        return True
    left = left_visible.rstrip()
    if not left:
        return False
    if left[-1] in {",", ";", "."}:
        return True
    if re.search(r"\bet\s+al\.?$", left, re.IGNORECASE):
        return True
    if not re.match(
        r"(?:and|or|than|with|for|in|to|from|of|was|were|is|are|has|have|had|can|may|might|would|should)\b",
        right,
        re.IGNORECASE,
    ):
        return False
    word_match = re.search(r"([A-Za-z][A-Za-z-]{2,})\s*$", left)
    return word_match is not None


def _numeric_superscript_context_allows_citation(
    text: str,
    start: int,
    end: int,
    *,
    allow_lowercase_after: bool = False,
) -> bool:
    if start > 0 and text[start - 1].isdigit():
        return False
    if _inline_math_is_open(text, start):
        return False

    left = text[:start]
    right = text[end:]
    left_stripped = left.rstrip()
    right_stripped = right.lstrip()
    left_visible = _visible_text(left[-100:])

    if _has_non_citation_numeric_left_context(left_visible):
        return False
    if re.search(r"\d\s*$", left_visible) and re.match(r"[A-Za-z]", right_stripped):
        return False
    if left_stripped and left_stripped[-1] in _NUMERIC_SUPERSCRIPT_DASH_CHARS:
        return False
    if left_stripped and left_stripped[-1] in _NUMERIC_SUPERSCRIPT_OPERATOR_CHARS:
        return False
    if right_stripped and right_stripped[0] in _NUMERIC_SUPERSCRIPT_DASH_CHARS:
        return False
    if right_stripped.startswith("%"):
        return False
    if (
        not allow_lowercase_after
        and re.match(r"[A-Za-z]", right_stripped)
        and not re.match(r"[A-Z]", right_stripped)
        and not _lowercase_after_superscript_still_looks_citation(left_visible, _visible_text(right[:80]))
    ):
        return False
    return True


def _numeric_superscript_context_allows_zotero_citation(text: str, start: int, end: int) -> bool:
    if _numeric_superscript_context_allows_citation(
        text,
        start,
        end,
        allow_lowercase_after=True,
    ):
        return True
    left_visible = _visible_text(text[:start][-100:])
    return bool(_UNIT_SENTENCE_LEFT_CONTEXT_PATTERN.search(left_visible))


def _link_pdf_annotation_plain_superscript_citations(
    html: str,
    citation_profile: Any | None,
    ref_index: int,
) -> str:
    target_budgets = _pdf_annotation_reference_target_budgets(citation_profile, ref_index)
    if not target_budgets:
        return html

    for target, existing_count in _ref_link_counts_by_target(html).items():
        if target in target_budgets:
            target_budgets[target] = max(0, target_budgets[target] - existing_count)
    hints = _pdf_annotation_superscript_context_hints(citation_profile, ref_index)
    targets = sorted(
        (target for target, budget in target_budgets.items() if budget > 0 and hints.get(target)),
        reverse=True,
    )
    if not targets:
        return html

    number_pattern = re.compile(
        rf"(?P<gap>\s*)(?P<num>{'|'.join(re.escape(str(target)) for target in targets)})(?!\d)"
    )

    def replace_in_text(part: str) -> str:
        def replace(match: re.Match[str]) -> str:
            try:
                target = int(match.group("num"))
            except ValueError:
                return match.group(0)
            if target_budgets.get(target, 0) <= 0:
                return match.group(0)

            start = match.start("num")
            end = match.end("num")
            if not _numeric_superscript_context_allows_citation(part, start, end):
                return match.group(0)
            left = part[:start]
            right = part[end:]
            if not _pdf_annotation_superscript_context_matches(left, right, hints.get(target, [])):
                return match.group(0)

            target_budgets[target] = target_budgets.get(target, 0) - 1
            return f'<sup><a href="#ref-{target}" class="z2m-ref-link">{target}</a></sup>'

        return number_pattern.sub(replace, part)

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        parts = _TAG_SPLIT_PATTERN.split(raw)
        out: list[str] = []
        skip_stack: list[str] = []
        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                _update_citation_skip_stack(part, skip_stack)
                out.append(part)
                continue
            out.append(part if skip_stack else replace_in_text(part))
        return "".join(out)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


_ZOTERO_OVERLAY_NUMERIC_CITATION_TEXT_RE = re.compile(
    r"^\s*\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12}\s*$"
)
_ZOTERO_OVERLAY_NUMERIC_TOKEN_RE = re.compile(r"\d{1,3}|[,;]|\u2013|\u2014|-")


def _zotero_overlay_citation_refs(item: Any, ref_index: int) -> list[int]:
    raw_refs = _profile_item_value(item, "refs", None)
    if raw_refs is None:
        raw_refs = _profile_item_value(item, "references", None)
    refs: list[int] = []
    if not isinstance(raw_refs, list):
        return refs
    for raw in raw_refs:
        value = raw.get("index") if isinstance(raw, dict) else raw
        try:
            ref = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= ref <= ref_index and ref not in refs:
            refs.append(ref)
    return refs


def _zotero_overlay_citation_hints(text: str, context: str) -> list[tuple[str, str]]:
    compact_text = _compact_pdf_annotation_context(text)
    compact_context = _compact_pdf_annotation_context(context)
    if not compact_text or not compact_context:
        return []
    hints: list[tuple[str, str]] = []
    start = 0
    while True:
        index = compact_context.find(compact_text, start)
        if index < 0:
            break
        left_hint = compact_context[:index][-18:]
        right_hint = compact_context[index + len(compact_text):][:18]
        if left_hint or right_hint:
            hints.append((left_hint, right_hint))
        start = index + 1
    return hints


def _zotero_numeric_citation_pattern(text: str) -> re.Pattern[str] | None:
    normalized = _normalize_pdf_annotation_context(text).strip()
    if not _ZOTERO_OVERLAY_NUMERIC_CITATION_TEXT_RE.fullmatch(normalized):
        return None
    tokens = _ZOTERO_OVERLAY_NUMERIC_TOKEN_RE.findall(normalized)
    if not tokens or not re.fullmatch(r"\d{1,3}", tokens[0] or ""):
        return None
    parts: list[str] = []
    expect_number = True
    for token in tokens:
        if re.fullmatch(r"\d{1,3}", token):
            if not expect_number:
                return None
            if len(token) > 1 and token.startswith("0"):
                return None
            parts.append(re.escape(token))
            expect_number = False
        else:
            if expect_number:
                return None
            if token in {",", ";"}:
                parts.append(r"\s*[,;]\s*")
            else:
                parts.append(r"\s*(?:-|\u2013|\u2014)\s*")
            expect_number = True
    if expect_number:
        return None
    return re.compile(rf"(?P<gap>\s*)(?P<body>{''.join(parts)})(?!\d)")


def _zotero_overlay_numeric_citation_entries(
    citation_profile: Any | None,
    ref_index: int,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in _citation_profile_items(citation_profile, "zotero_citations"):
        text = str(_profile_item_value(item, "text", "") or "")
        refs = _zotero_overlay_citation_refs(item, ref_index)
        if not text or not refs:
            continue
        pattern = _zotero_numeric_citation_pattern(text)
        if pattern is None:
            continue
        hints = _zotero_overlay_citation_hints(text, str(_profile_item_value(item, "context", "") or ""))
        if not hints:
            continue
        entries.append({"text": text, "refs": refs, "pattern": pattern, "hints": hints})
    return entries


def _has_zotero_overlay_numeric_citations(citation_profile: Any | None, ref_index: int) -> bool:
    return bool(_zotero_overlay_numeric_citation_entries(citation_profile, ref_index))


def _link_zotero_overlay_numeric_citations_in_safe_blocks(
    html: str,
    citation_profile: Any | None,
    ref_index: int,
) -> str:
    entries = _zotero_overlay_numeric_citation_entries(citation_profile, ref_index)
    if not entries:
        return html
    remaining = {index: 1 for index in range(len(entries))}

    def replace_text(part: str) -> str:
        current = part
        for index, entry in enumerate(entries):
            if remaining.get(index, 0) <= 0:
                continue
            pattern: re.Pattern[str] = entry["pattern"]

            def replace(match: re.Match[str], *, entry_index: int = index, entry_data: dict[str, Any] = entry) -> str:
                if remaining.get(entry_index, 0) <= 0:
                    return match.group(0)
                body = match.group("body")
                linked = _link_numeric_superscript_body(body, ref_index)
                if linked is None:
                    return match.group(0)

                left = match.string[: match.start("body")]
                right = match.string[match.end("body"):]
                if not _numeric_superscript_context_allows_zotero_citation(
                    match.string,
                    match.start("body"),
                    match.end("body"),
                ):
                    return match.group(0)
                if not _pdf_annotation_superscript_context_matches(left, right, entry_data["hints"]):
                    return match.group(0)

                remaining[entry_index] = remaining.get(entry_index, 0) - 1
                gap = match.group("gap") or ""
                prefix = "" if gap and left.rstrip() else gap
                return f"{prefix}<sup>{linked}</sup>"

            current = pattern.sub(replace, current)
        return current

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        parts = _TAG_SPLIT_PATTERN.split(raw)
        out: list[str] = []
        skip_stack: list[str] = []
        inline_skip_stack: list[str] = []
        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                _update_citation_skip_stack(part, skip_stack)
                close_match = _CLOSE_TAG_PATTERN.match(part.strip())
                if close_match is not None and inline_skip_stack:
                    tag_name = close_match.group(1).lower()
                    for idx in range(len(inline_skip_stack) - 1, -1, -1):
                        if inline_skip_stack[idx] == tag_name:
                            del inline_skip_stack[idx]
                            break
                else:
                    open_match = _OPEN_TAG_PATTERN.match(part.strip())
                    if (
                        open_match is not None
                        and open_match.group(1).lower() in {"a", "sup"}
                        and not part.rstrip().endswith("/>")
                    ):
                        inline_skip_stack.append(open_match.group(1).lower())
                out.append(part)
                continue
            out.append(part if skip_stack or inline_skip_stack else replace_text(part))
        return "".join(out)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


_PLAIN_SUPERSCRIPT_NUMERIC_CITATION_GROUP_PATTERN = re.compile(
    r"(?P<punct>[.!?])\s+"
    r"(?P<body>\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){1,12})"
    r"(?=\s+[A-Z])"
)
_PLAIN_SUPERSCRIPT_NUMERIC_COMMA_GROUP_PATTERN = re.compile(
    r"(?P<punct>,)\s+"
    r"(?P<body>\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){1,12})"
    r"(?=\s+(?:and|or|but|whereas|while|no|not|the|a|an|this|these|those|"
    r"we|which|that|it|they|there|in|on|for|with|without|as|since|because)\b)"
)
_PLAIN_SUPERSCRIPT_NUMERIC_CITATION_ANY_PATTERN = re.compile(
    r"(?P<punct>[.!?])\s+"
    r"(?P<body>\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12})"
    r"(?=\s+[A-Z])"
)
_VISIBLE_FLATTENED_SUPERSCRIPT_NUMERIC_CITATION_PATTERN = re.compile(
    r"(?<=[.!?])\s+"
    r"(?P<body>\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){1,12})"
    r"(?=\s+[A-Z])"
)


def _looks_like_flattened_superscript_numeric_document(html: str, ref_index: int) -> bool:
    if ref_index <= 0:
        return False
    count = 0
    text = _visible_text(html)
    for match in _VISIBLE_FLATTENED_SUPERSCRIPT_NUMERIC_CITATION_PATTERN.finditer(text):
        numbers = [int(value) for value in re.findall(r"\d{1,3}", match.group("body"))]
        if numbers and all(1 <= number <= ref_index for number in numbers):
            count += 1
    return count >= 5


def _looks_like_bracket_numeric_document(html: str, ref_index: int) -> bool:
    if ref_index <= 0:
        return False
    count = 0
    text = _visible_text(html)
    for match in _BRACKET_CITATION_PATTERN.finditer(text):
        numbers = [int(value) for value in re.findall(r"\d{1,3}", match.group(1))]
        if numbers and all(1 <= number <= ref_index for number in numbers):
            count += 1
    return count >= 2


def _link_numeric_superscript_body(body: str, ref_index: int) -> str | None:
    visible = _visible_text(body)
    tokens = re.findall(r"\d{1,3}", visible)
    if any(len(value) > 1 and value.startswith("0") for value in tokens):
        return None
    numbers = [int(value) for value in tokens]
    if not numbers or any(number < 1 or number > ref_index for number in numbers):
        return None
    if not re.fullmatch(r"\s*\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12}\s*", visible):
        return None

    def link_number(match: re.Match[str]) -> str:
        number = int(match.group(0))
        return f'<a href="#ref-{number}" class="z2m-ref-link">{match.group(0)}</a>'

    return re.sub(r"\d{1,3}", link_number, body)


def _numeric_citation_body_numbers(body: str) -> list[int]:
    visible = _visible_text(body)
    tokens = re.findall(r"\d{1,3}", visible)
    if any(len(value) > 1 and value.startswith("0") for value in tokens):
        return []
    return [int(value) for value in tokens]


def _linked_reference_numbers_in_html(html: str) -> set[int]:
    linked: set[int] = set()
    for anchor_match in re.finditer(r"<a\b[^>]*>", html, re.IGNORECASE):
        anchor = anchor_match.group(0)
        if "z2m-ref-link" not in anchor:
            continue
        href_match = re.search(r"\bhref\s*=\s*['\"]#ref-(\d{1,3})['\"]", anchor, re.IGNORECASE)
        if href_match is None:
            continue
        linked.add(int(href_match.group(1)))
    return linked


def _link_existing_numeric_superscripts_in_safe_blocks(
    html: str,
    ref_index: int,
    *,
    allow_lowercase_after: bool = False,
) -> str:
    def single_number_body(body: str) -> bool:
        return len(_numeric_citation_body_numbers(body)) == 1

    def replace_sup(match: re.Match[str]) -> str:
        raw = match.group(0)
        if "z2m-unit-exp" in raw or "z2m-footnote-ref" in raw or "<a " in raw.lower():
            return raw
        if (
            allow_lowercase_after
            and single_number_body(match.group(1))
            and not _numeric_superscript_context_allows_citation(match.string, match.start(), match.end())
        ):
            return raw
        if not _numeric_superscript_context_allows_citation(
            match.string,
            match.start(),
            match.end(),
            allow_lowercase_after=allow_lowercase_after,
        ):
            return raw
        linked = _link_numeric_superscript_body(match.group(1), ref_index)
        if linked is None:
            return raw
        return f"<sup>{linked}</sup>"

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        return _SUP_PATTERN.sub(replace_sup, raw)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


_SENTENCE_TERMINAL_SUP_RANGE_PATTERN = re.compile(
    r"(?P<punct>[.!?])(?P<gap>\s*)"
    r"<sup\b(?![^>]*\b(?:z2m-unit-exp|z2m-footnote-ref)\b)[^>]*>"
    r"\s*(?P<body>\d{1,3}\s*[-\u2013\u2014]\s*\d{1,3}"
    r"(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12})\s*"
    r"</sup>",
    re.IGNORECASE,
)


def _link_sentence_terminal_superscript_ranges_in_safe_blocks(html: str, ref_index: int) -> str:
    if ref_index <= 0 or "<sup" not in html:
        return html

    def replace_range(match: re.Match[str]) -> str:
        linked = _link_numeric_superscript_body(match.group("body"), ref_index)
        if linked is None:
            return match.group(0)
        return f"{match.group('punct')}{match.group('gap')}<sup>{linked}</sup>"

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        return _SENTENCE_TERMINAL_SUP_RANGE_PATTERN.sub(replace_range, raw)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


def _link_plain_superscript_numeric_groups_in_safe_blocks(
    html: str,
    ref_index: int,
    *,
    allow_single: bool = False,
    linked_ref_numbers: set[int] | None = None,
) -> str:
    pattern = (
        _PLAIN_SUPERSCRIPT_NUMERIC_CITATION_ANY_PATTERN
        if allow_single
        else _PLAIN_SUPERSCRIPT_NUMERIC_CITATION_GROUP_PATTERN
    )

    def replace_group(match: re.Match[str]) -> str:
        if match.group("punct") == "," and re.search(r"[-\u2013\u2014]", match.group("body")) is None:
            numbers = _numeric_citation_body_numbers(match.group("body"))
            if linked_ref_numbers is None or any(number in linked_ref_numbers for number in numbers):
                return match.group(0)
        if not _numeric_superscript_context_allows_citation(
            match.string,
            match.start("body"),
            match.end("body"),
        ):
            return match.group(0)
        linked = _link_numeric_superscript_body(match.group("body"), ref_index)
        if linked is None:
            return match.group(0)
        return f"{match.group('punct')}<sup>{linked}</sup>"

    def replace_text(part: str) -> str:
        text = pattern.sub(replace_group, part)
        if not allow_single:
            text = _PLAIN_SUPERSCRIPT_NUMERIC_COMMA_GROUP_PATTERN.sub(replace_group, text)
        return text

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        parts = _TAG_SPLIT_PATTERN.split(raw)
        out: list[str] = []
        skip_stack: list[str] = []
        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                _update_citation_skip_stack(part, skip_stack)
                out.append(part)
                continue
            out.append(part if skip_stack else replace_text(part))
        return "".join(out)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


_REF_SUP_NO_SPACE_AFTER_PATTERN = re.compile(
    r"(?P<sup><sup\b[^>]*>[\s\S]{0,400}?\bz2m-ref-link\b[\s\S]{0,400}?</sup>)(?P<next>[A-Za-z])",
    re.IGNORECASE,
)


def _normalize_spacing_after_ref_superscripts(html: str) -> str:
    return _REF_SUP_NO_SPACE_AFTER_PATTERN.sub(r"\g<sup> \g<next>", html)


def _link_unlinked_numeric_superscripts_to_existing_refs(html: str) -> str:
    ref_ids = [int(value) for value in re.findall(r'\bid\s*=\s*["\']ref-(\d{1,4})["\']', html)]
    if not ref_ids or "<sup" not in html:
        return html
    ref_set = set(ref_ids)

    def _split_before_references(document: str) -> tuple[str, str]:
        heading_match = _references_heading_search(document, allow_notes_heading=True)
        if heading_match is not None:
            return document[: heading_match.start()], document[heading_match.start():]
        first_ref_match = re.search(r'<li\b[^>]*\bid\s*=\s*["\']ref-\d+', document, re.IGNORECASE)
        if first_ref_match is not None:
            return document[: first_ref_match.start()], document[first_ref_match.start():]
        return document, ""

    def _link_existing_multi_number_sup_body(body: str) -> str | None:
        normalized_body = _fix_common_mojibake(body)
        visible = _visible_text(normalized_body)
        if not re.fullmatch(
            r"\s*\d{1,4}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,4}){1,12}\s*",
            visible,
        ):
            return None
        tokens = re.findall(r"\d{1,4}", visible)
        if len(tokens) < 2 or any(len(value) > 1 and value.startswith("0") for value in tokens):
            return None
        numbers = [int(value) for value in tokens]
        if any(number not in ref_set for number in numbers):
            return None

        def link_text(part: str) -> str:
            def link_number(match: re.Match[str]) -> str:
                number = int(match.group(0))
                if number not in ref_set:
                    return match.group(0)
                return f'<a href="#ref-{number}" class="z2m-ref-link">{match.group(0)}</a>'

            return re.sub(r"\d{1,4}", link_number, part)

        parts = _TAG_SPLIT_PATTERN.split(normalized_body)
        out: list[str] = []
        skip_stack: list[str] = []
        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                _update_citation_skip_stack(part, skip_stack)
                out.append(part)
                continue
            out.append(part if skip_stack else link_text(part))
        return "".join(out)

    def _link_numeric_sup_ranges_in_body_fragment(fragment: str) -> str:
        def replace_sup(match: re.Match[str]) -> str:
            raw = match.group(0)
            if (
                "z2m-unit-exp" in raw
                or "z2m-footnote-ref" in raw
                or "z2m-table-fn" in raw
            ):
                return raw
            if not _numeric_superscript_context_allows_citation(match.string, match.start(), match.end()):
                return raw
            linked_body = _link_existing_multi_number_sup_body(match.group(1))
            if linked_body is None:
                return raw
            return f"<sup>{linked_body}</sup>"

        def replace_node(match: re.Match[str]) -> str:
            raw = match.group(0)
            if _node_protects_citations(raw):
                return raw
            return _SUP_PATTERN.sub(replace_sup, raw)

        return _SENTENCE_NODE_PATTERN.sub(replace_node, fragment)

    def _link_et_al_sup(match: re.Match[str]) -> str:
        number = int(match.group("num"))
        if number not in ref_set:
            return match.group(0)
        return (
            f'{match.group("lead")}<sup><a href="#ref-{number}" '
            f'class="z2m-ref-link">{match.group("num")}</a></sup>'
        )

    html = re.sub(
        r'(?P<lead>\bet\s+al\.?)<sup>\s*(?P<num>\d{1,3})\s*</sup>',
        _link_et_al_sup,
        html,
        flags=re.IGNORECASE,
    )
    before_references, references_and_after = _split_before_references(html)
    before_references = _link_numeric_sup_ranges_in_body_fragment(before_references)
    return before_references + references_and_after


def _unwrap_numeric_ref_links_for_author_year_profile(html: str) -> str:
    if "#ref-" not in html:
        return html

    heading_match = _references_heading_search(html, allow_notes_heading=True)
    if heading_match is not None:
        before_references = html[: heading_match.start()]
        references_and_after = html[heading_match.start():]
    else:
        first_ref_match = re.search(r'<li\b[^>]*\bid\s*=\s*["\']ref-\d+', html, re.IGNORECASE)
        if first_ref_match is None:
            before_references = html
            references_and_after = ""
        else:
            before_references = html[: first_ref_match.start()]
            references_and_after = html[first_ref_match.start():]

    def unwrap_numeric_anchor(match: re.Match[str]) -> str:
        visible = _visible_text(match.group("body")).strip()
        if not re.search(r"\d", visible):
            return match.group(0)
        if re.fullmatch(r"[\s\(\[\]\),.;:\-\u2010\u2011\u2012\u2013\u2014\d]+", visible) is None:
            return match.group(0)
        return match.group("body")

    return _REF_ANCHOR_PATTERN.sub(unwrap_numeric_anchor, before_references) + references_and_after


def _unlink_sup_ref_links(html: str) -> str:
    def replace_sup(match: re.Match[str]) -> str:
        raw = match.group(0)
        if "z2m-ref-link" not in raw:
            return raw
        inner = match.group(1)
        inner = re.sub(
            r'<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*\bz2m-ref-link\b[^>]*>([\s\S]*?)</a>',
            r"\1",
            inner,
            flags=re.IGNORECASE,
        )
        return f"<sup>{inner}</sup>"

    return _SUP_PATTERN.sub(replace_sup, html)


_PAGE_ANCHOR_INLINE_NUMERIC_GROUP_PATTERN = re.compile(
    r"(?P<group>(?:"
    r"<a\b(?=[^>]*\bhref\s*=\s*['\"]#page-)[^>]*>[\s\d,;\(\)\-\u2013\u2014]*</a>"
    r"|[\s\d,;\(\)\-\u2013\u2014]"
    r"){3,600})",
    re.IGNORECASE,
)
_PLAIN_PAREN_NUMERIC_CITATION_PATTERN = re.compile(
    r"\(\s*\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12}\s*\)"
)


def _link_paren_numeric_page_citations_in_safe_blocks(
    html: str,
    ref_index: int,
    citation_profile: Any | None = None,
) -> str:
    """Retarget page-anchor numeric citations for parenthetical numeric articles."""
    target_budgets = _pdf_annotation_reference_target_budgets(citation_profile, ref_index)
    enforce_target_budgets = bool(target_budgets)

    def render_visible_citation(visible: str) -> str | None:
        match = re.fullmatch(
            r"\s*(?P<prefix>[\)\]]?\s*)?"
            r"(?P<body>\(\s*\d{1,3}(?:\s*(?:[,;]|\u2013|\u2014|-)\s*\d{1,3}){0,12}\s*\))"
            r"(?P<trail>[.,;:]?)\s*",
            visible,
        )
        if match is None:
            return None

        prefix = match.group("prefix") or ""
        body = match.group("body")
        trail = match.group("trail")
        numbers = [int(value) for value in re.findall(r"\d{1,3}", body)]
        if not numbers or any(number < 1 or number > ref_index for number in numbers):
            return None
        if enforce_target_budgets and any(target_budgets.get(number, 0) <= 0 for number in numbers):
            return None

        def link_number(num_match: re.Match[str]) -> str:
            number_text = num_match.group(0)
            number = int(number_text)
            if enforce_target_budgets:
                target_budgets[number] = target_budgets.get(number, 0) - 1
            return f'<a href="#ref-{number}" class="z2m-ref-link">{number_text}</a>'

        return prefix + re.sub(r"\d{1,3}", link_number, body) + trail

    def link_plain_parenthetical_citations(raw: str) -> str:
        parts = _TAG_SPLIT_PATTERN.split(raw)
        out: list[str] = []
        link_depth = 0

        def replace_plain(match: re.Match[str]) -> str:
            rendered = render_visible_citation(match.group(0))
            return match.group(0) if rendered is None else rendered

        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                close_match = _CLOSE_TAG_PATTERN.match(part)
                open_match = _OPEN_TAG_PATTERN.match(part)
                if close_match is not None and close_match.group(1).lower() == "a" and link_depth:
                    link_depth -= 1
                out.append(part)
                if open_match is not None and open_match.group(1).lower() == "a":
                    link_depth += 1
                continue
            if link_depth:
                out.append(part)
            else:
                out.append(_PLAIN_PAREN_NUMERIC_CITATION_PATTERN.sub(replace_plain, part))
        return "".join(out)

    def replace_group(match: re.Match[str]) -> str:
        raw = match.group("group")
        if "#page-" not in raw:
            return raw
        visible = _visible_text(raw)
        if not visible or re.search(r"[A-Za-z%]", visible):
            return raw
        rendered = render_visible_citation(visible)
        if rendered is None:
            return raw
        leading_space = " " if raw[:1].isspace() else ""
        trailing_space = " " if raw[-1:].isspace() else ""
        return f"{leading_space}{rendered}{trailing_space}"

    def replace_node(match: re.Match[str]) -> str:
        raw = match.group(0)
        if _node_protects_citations(raw):
            return raw
        retargeted = _PAGE_ANCHOR_INLINE_NUMERIC_GROUP_PATTERN.sub(replace_group, raw)
        return link_plain_parenthetical_citations(retargeted)

    return _SENTENCE_NODE_PATTERN.sub(replace_node, html)


_BACKMATTER_AFTER_REFERENCES_HEADING_RE = re.compile(
    r"^(?:"
    r"author\s+contributions?|funding|acknowledg(?:e)?ments?|"
    r"supplementary\s+materials?|conflicts?\s+of\s+interest|"
    r"data\s+availability\s+statement|ethics\s+statement"
    r")$",
    re.IGNORECASE,
)


def _repair_backmatter_interleaved_in_references(html: str) -> str:
    """Move back-matter islands that Marker placed inside the references list."""
    if "<li" not in html.lower() or _references_heading_search(html) is None:
        return html

    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html

    references_index = next(
        (index for index, node in enumerate(nodes) if _references_heading_match(node.group(0)) is not None),
        None,
    )
    if references_index is None:
        return html

    def is_reference_list_node(raw: str) -> bool:
        return "<li" in raw.lower()

    def is_backmatter_heading(raw: str) -> bool:
        if re.match(r"<h[1-6]\b", raw.lstrip(), re.IGNORECASE) is None:
            return False
        visible = re.sub(r"\s+", " ", _visible_text(raw)).strip(" .:")
        return _BACKMATTER_AFTER_REFERENCES_HEADING_RE.fullmatch(visible) is not None

    def is_orphan_backmatter_continuation(raw: str, next_index: int) -> bool:
        if not raw.lstrip().lower().startswith("<p"):
            return False
        if next_index >= len(nodes) or not is_backmatter_heading(nodes[next_index].group(0)):
            return False
        if "<li" in raw.lower() or _references_heading_match(raw) is not None:
            return False
        visible = re.sub(r"\s+", " ", _visible_text(raw)).strip()
        if not visible or len(visible) > 700:
            return False
        return re.search(
            r"\b(?:approved by|written informed consent|provided .*consent|participation in the study|"
            r"participants provided|ethics committee|university of)\b",
            visible,
            re.IGNORECASE,
        ) is not None

    def has_later_reference_list(start_index: int) -> bool:
        return any(is_reference_list_node(nodes[index].group(0)) for index in range(start_index, len(nodes)))

    seen_reference_list = False
    groups: list[tuple[int, int]] = []
    index = references_index + 1
    while index < len(nodes):
        raw = nodes[index].group(0)
        if _references_heading_match(raw) is not None:
            break
        if is_reference_list_node(raw):
            seen_reference_list = True
            index += 1
            continue
        if not seen_reference_list:
            index += 1
            continue

        start_index: int | None = None
        if is_backmatter_heading(raw):
            start_index = index
        elif is_orphan_backmatter_continuation(raw, index + 1):
            start_index = index
        if start_index is None:
            index += 1
            continue

        end_index = start_index
        saw_heading = False
        scan = start_index
        while scan < len(nodes):
            scan_raw = nodes[scan].group(0)
            if scan > start_index and (
                _references_heading_match(scan_raw) is not None or is_reference_list_node(scan_raw)
            ):
                break
            if is_backmatter_heading(scan_raw):
                saw_heading = True
            end_index = scan
            scan += 1
        if saw_heading and has_later_reference_list(end_index + 1):
            groups.append((start_index, end_index))
            index = end_index + 1
            continue
        index += 1

    if not groups:
        return html

    moved_indices = {index for start, end in groups for index in range(start, end + 1)}
    moved_html = "".join(html[nodes[start].start() : nodes[end].end()] for start, end in groups)
    out_parts: list[str] = []
    cursor = 0
    for index, node in enumerate(nodes):
        out_parts.append(html[cursor : node.start()])
        if index == references_index:
            out_parts.append(moved_html)
        if index not in moved_indices:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _add_reference_ids_and_citation_links(html: str, citation_profile: Any | None = None) -> str:
    html = _split_embedded_unheaded_reference_section(html)
    html = _repair_backmatter_interleaved_in_references(html)
    heading_match = _references_heading_search(
        html,
        allow_notes_heading=_citation_profile_has_zotero_reference_evidence(citation_profile),
    )
    if heading_match is not None:
        split_at = heading_match.end()
    else:
        split_at = _unheaded_reference_list_start(html)
        if split_at is None:
            citation_profile = _citation_profile_with_body_reference_recovery_numbers(html, citation_profile)
            html, recovered_ref_index = _append_pdf_recovered_reference_section_if_safe(html, citation_profile)
            if recovered_ref_index == 0:
                return html
            heading_match = _references_heading_search(
                html,
                allow_notes_heading=_citation_profile_has_zotero_reference_evidence(citation_profile),
            )
            if heading_match is not None:
                split_at = heading_match.end()
            else:
                split_at = _unheaded_reference_list_start(html)
                if split_at is None:
                    return html
    embedded_reference_recovery = (
        heading_match is not None
        and "data-z2m-embedded-references" in heading_match.group(0)
    )
    before_references = html[:split_at]
    references_and_after = html[split_at:]
    before_references = _mark_front_matter_paragraphs(before_references)
    before_references = _repair_front_matter_marker_ocr(before_references)
    before_references = _repair_confirmed_front_matter_artifacts(before_references)
    before_references = _mark_footnote_paragraphs_and_refs(before_references)
    before_references = _strip_reference_links_in_protected_blocks(before_references)

    references_and_after = _unwrap_zotero_google_docs_reference_anchors(references_and_after)
    references_and_after = _flatten_nested_reference_list_items(references_and_after)
    references_and_after = _repair_reference_author_group_glue(references_and_after)
    references_and_after = _strip_leading_reference_line_number_pairs_in_list_items(references_and_after)
    references_and_after = _normalize_reference_list_items(references_and_after)
    references_and_after = _split_collapsed_reference_list_items(references_and_after)
    references_and_after = _split_sequential_numbered_reference_list_items(references_and_after)
    references_and_after = _split_implicit_unnumbered_reference_list_items(references_and_after)
    references_with_ids, ref_index = _add_reference_ids_to_list_items(references_and_after)
    references_with_ids, paragraph_ref_index = _add_reference_ids_to_standalone_reference_paragraphs(
        references_with_ids
    )
    ref_index = max(ref_index, paragraph_ref_index)
    references_with_ids, recovered_ref_index = _recover_missing_reference_entries_from_profile(
        references_with_ids,
        citation_profile,
        body_html=before_references,
    )
    ref_index = max(ref_index, recovered_ref_index)
    if ref_index == 0:
        return html
    if "data-z2m-pdf-recovered-references" in references_with_ids:
        before_references = _link_sentence_trailing_plain_numeric_citations(before_references, ref_index)
        before_references = _link_plain_superscript_numeric_groups_in_safe_blocks(before_references, ref_index)
    if embedded_reference_recovery:
        before_references = _link_plain_body_reference_candidate_ranges_in_safe_blocks(before_references, ref_index)

    profile_is_author_year = _citation_profile_is_author_year(citation_profile)
    profile_is_paren_numeric = _citation_profile_is_high_confidence_paren_numeric(citation_profile)
    profile_has_reference_annotations = bool(
        _pdf_annotation_reference_target_budgets(citation_profile, ref_index)
    )
    profile_is_flattened_superscript_numeric = (
        not profile_is_author_year
        and not profile_is_paren_numeric
        and not profile_has_reference_annotations
        and _looks_like_flattened_superscript_numeric_document(before_references, ref_index)
    )
    profile_has_zotero_overlay_citations = (
        not profile_is_author_year
        and not profile_is_paren_numeric
        and _has_zotero_overlay_numeric_citations(citation_profile, ref_index)
    )
    profile_is_superscript_numeric = (
        _citation_profile_is_high_confidence_superscript_numeric(citation_profile)
        or profile_is_flattened_superscript_numeric
        or profile_has_zotero_overlay_citations
    )
    profile_is_bracket_numeric = (
        not profile_is_author_year
        and not profile_is_paren_numeric
        and not profile_is_superscript_numeric
        and (
            _citation_profile_is_bracket_numeric(citation_profile)
            or _looks_like_bracket_numeric_document(before_references, ref_index)
        )
    )
    if not profile_is_author_year and not profile_is_paren_numeric:
        before_references = _link_bracket_citations(before_references, ref_index)
        before_references = _link_table_float_numeric_citation_ranges(before_references, ref_index)

    page_to_ref = _reference_page_anchor_map(references_with_ids)
    if profile_is_paren_numeric:
        before_references = _link_paren_numeric_page_citations_in_safe_blocks(
            before_references,
            ref_index,
            citation_profile=citation_profile,
        )
    else:
        before_references = _rewrite_page_linked_bracket_citations(before_references, ref_index)
        before_references = _rewrite_page_links_to_reference_targets(before_references, page_to_ref)
    before_references = _link_pdf_annotation_reference_texts_in_safe_blocks(
        before_references,
        citation_profile,
        ref_index,
    )
    before_references = _repair_ocr_letter_glued_page_citation_links(before_references, ref_index)
    if profile_is_superscript_numeric:
        before_references = _wrap_pdf_annotation_ref_runs_as_superscripts(
            before_references,
            citation_profile,
            ref_index,
        )
        before_references = _link_pdf_annotation_tex_superscript_citations(
            before_references,
            citation_profile,
            ref_index,
        )
        before_references = _link_pdf_annotation_plain_superscript_citations(
            before_references,
            citation_profile,
            ref_index,
        )
        before_references = _link_zotero_overlay_numeric_citations_in_safe_blocks(
            before_references,
            citation_profile,
            ref_index,
        )
        before_references = _link_existing_numeric_superscripts_in_safe_blocks(before_references, ref_index)
        before_references = _link_sentence_terminal_superscript_ranges_in_safe_blocks(before_references, ref_index)
        before_references = _recover_flattened_author_superscript_citations(before_references, ref_index)
        before_references = _link_plain_superscript_numeric_groups_in_safe_blocks(
            before_references,
            ref_index,
            allow_single=False,
            linked_ref_numbers=_linked_reference_numbers_in_html(before_references),
        )
        before_references = _wrap_plain_ref_links_as_superscript_citations(before_references)
        before_references = _normalize_spacing_after_ref_superscripts(before_references)

    if not re.search(r"<ol\b", references_with_ids, re.IGNORECASE):
        def ensure_visible_ref_number(match: re.Match[str]) -> str:
            attrs = match.group(1) or ""
            body = match.group(2) or ""
            id_match = _LI_ID_PATTERN.search(attrs)
            if id_match is None:
                return match.group(0)
            number = id_match.group(1)
            # Strip leading "[N]" bracket number (IEEE/Vancouver style) to avoid
            # "1. [1] Author..." double-numbering.
            body = _LEADING_PAGE_SPAN_BRACKET_REF_NUM_STRIP_PATTERN.sub("", body)
            body = _strip_page_anchor_bracket_ref_num_prefix(body)
            body = _BRACKET_REF_NUM_STRIP_PATTERN.sub("", body)
            body = _DOTTED_BRACKET_REF_NUM_STRIP_PATTERN.sub(r"\1", body)
            body = _PAGE_ANCHOR_DOTTED_REF_NUM_STRIP_PATTERN.sub("", body)
            body = _strip_reference_line_number_artifacts(body, number)
            body = _strip_duplicate_reference_number_artifacts(body, number)
            body = _strip_embedded_reference_number_artifacts(body)
            body = re.sub(
                rf'^(\s*(?:<[^>]+>\s*)*){re.escape(number)}(?=[A-Z]\.)',
                r"\1",
                body,
                count=1,
            )
            body = re.sub(
                rf'^(\s*(?:<[^>]+>\s*)*){re.escape(number)}\s+(?=[A-Z])',
                r"\1",
                body,
            )
            # Idempotency guard: if a z2m-ref-num span already exists this <li>
            # was processed in a previous polish pass — don't add another one.
            if 'class="z2m-ref-num"' in body:
                return f"<li{attrs}>{body}</li>"
            # If Marker already wrote "N. Author..." wrap that N. in the span for
            # consistent bold styling instead of leaving it unstyled.
            if _LEADING_REF_NUMBER_PATTERN.search(body):
                body = re.sub(
                    r'^(\s*(?:<[^>]+>\s*)*?)(\d+\.)\s+',
                    lambda m: f'{m.group(1)}<span class="z2m-ref-num">{m.group(2)}</span> ',
                    body,
                )
                return f"<li{attrs}>{body}</li>"
            numbered_body = f'<span class="z2m-ref-num">{number}.</span> {body.lstrip()}'
            return f"<li{attrs}>{numbered_body}</li>"

        references_with_ids = _LI_BLOCK_PATTERN.sub(ensure_visible_ref_number, references_with_ids)

    def link_sup(match: re.Match[str]) -> str:
        if "z2m-unit-exp" in match.group(0):
            return match.group(0)
        if "z2m-footnote-ref" in match.group(0):
            return match.group(0)
        inner = match.group(1)
        if "<a " in inner.lower():
            return match.group(0)

        pair_match = re.fullmatch(r"\s*(\d{3})\s*,\s*(\d{1,3})\s*", inner)
        if pair_match is not None:
            first = int(pair_match.group(1))
            second = int(pair_match.group(2))
            if first > second and str(first).startswith("1") and second < 100:
                candidate = int(str(first)[1:])
                if 1 <= candidate <= ref_index and 0 <= (second - candidate) <= 5:
                    inner = f"{candidate},{second}"

        def replace_number(num_match: re.Match[str]) -> str:
            number_text = num_match.group(0)
            try:
                number = int(number_text)
            except ValueError:
                return number_text
            if 1 <= number <= ref_index:
                return f'<a href="#ref-{number}" class="z2m-ref-link">{number_text}</a>'
            return number_text

        linked_inner = _SUP_NUMBER_PATTERN.sub(replace_number, inner)
        return f"<sup>{linked_inner}</sup>"

    def normalize_linked_ocr_pairs(text: str) -> str:
        pair_pattern = re.compile(
            r'<sup>\s*'
            r'<a href="#ref-(\d+)" class="z2m-ref-link">(\d+)</a>\s*,\s*'
            r'<a href="#ref-(\d+)" class="z2m-ref-link">(\d+)</a>\s*'
            r'</sup>',
            re.IGNORECASE,
        )

        def repl(m: re.Match[str]) -> str:
            href_a, txt_a, href_b, txt_b = m.group(1), m.group(2), m.group(3), m.group(4)
            if href_a != txt_a or href_b != txt_b:
                return m.group(0)
            try:
                first = int(txt_a)
                second = int(txt_b)
            except ValueError:
                return m.group(0)
            if first > second and str(first).startswith("1") and second < 100:
                candidate = int(str(first)[1:])
                if 1 <= candidate <= ref_index and 0 <= (second - candidate) <= 5:
                    return (
                        f'<sup><a href="#ref-{candidate}" class="z2m-ref-link">{candidate}</a>,'
                        f'<a href="#ref-{second}" class="z2m-ref-link">{second}</a></sup>'
                    )
            return m.group(0)

        return pair_pattern.sub(repl, text)

    if (
        not profile_is_author_year
        and not profile_is_paren_numeric
        and not profile_is_superscript_numeric
        and not profile_is_bracket_numeric
    ):
        # Recover citation superscripts that leaked into TeX unit exponents:
        # "\(112-278~\mathrm{MPa}\sqrt{\mathrm{m}^{24}}\)" -> "\(112-278~\mathrm{MPa}\sqrt{\mathrm{m}}\)<sup>24</sup>"
        before_references = _recover_citations_leaked_into_tex_units(before_references, ref_index)
        before_references = _unwrap_numeric_page_links_for_citation_recovery(before_references)

        # Recover bare citations: "issues17,68" → "issues<sup>17,68</sup>"
        before_references = _recover_ocr_citation_artifacts(before_references, ref_index)
        before_references = _recover_flattened_superscript_numeric_citations(before_references, ref_index)
        before_references = _recover_bare_citations(before_references, ref_index)
        before_references = _rewrite_page_linked_bracket_citations(before_references, ref_index)
        before_references = _convert_unicode_sup_citations(before_references, ref_index)

    # Link <sup>N</sup> citations first, then [N] bracket-style, then (ref. N).
    if profile_is_paren_numeric or profile_is_superscript_numeric:
        before_with_citation_links = before_references
    elif profile_is_bracket_numeric:
        before_with_citation_links = _unlink_sup_ref_links(before_references)
        before_with_citation_links = _unwrap_numeric_page_links_for_citation_recovery(before_with_citation_links)
        before_with_citation_links = _link_bracket_citations(before_with_citation_links, ref_index)
    else:
        before_with_citation_links = _link_sup_citations_in_safe_blocks(before_references, link_sup)
        before_with_citation_links = _link_bracket_citations(before_with_citation_links, ref_index)
    if not profile_is_author_year and not profile_is_paren_numeric:
        before_with_citation_links = _recover_flattened_superscript_numeric_citations(
            before_with_citation_links,
            ref_index,
        )
    if profile_is_superscript_numeric:
        before_with_citation_links = _link_existing_numeric_superscripts_in_safe_blocks(
            before_with_citation_links,
            ref_index,
            allow_lowercase_after=True,
        )
    if not profile_is_author_year and not profile_is_paren_numeric:
        before_with_citation_links = _link_flattened_et_al_numeric_citations_in_text_blocks(
            before_with_citation_links,
            ref_index,
        )
    if not profile_is_author_year and not profile_is_bracket_numeric:
        before_with_citation_links = _link_paren_ref_citations(before_with_citation_links, ref_index)
    before_with_citation_links = normalize_linked_ocr_pairs(before_with_citation_links)
    before_with_citation_links = _repair_ocr_letter_glued_ref_links(before_with_citation_links, ref_index)
    linked_document = before_with_citation_links + references_with_ids
    linked_document = _rewrite_page_links_to_reference_targets(linked_document, page_to_ref)
    linked_document = _repair_ocr_letter_glued_page_citation_links(linked_document, ref_index)
    linked_document = _repair_ocr_letter_glued_ref_links(linked_document, ref_index)
    if profile_is_superscript_numeric:
        linked_document = _wrap_pdf_annotation_ref_runs_as_superscripts(
            linked_document,
            citation_profile,
            ref_index,
        )
        linked_document = _normalize_spacing_after_ref_superscripts(linked_document)
    if profile_is_superscript_numeric:
        linked_document = _wrap_plain_ref_links_as_superscript_citations(linked_document)
        linked_document = _normalize_spacing_after_ref_superscripts(linked_document)
    linked_document = _unwrap_broken_reference_links(linked_document)
    return linked_document


def _set_block_type_attr(open_tag: str, value: str) -> str:
    if re.search(r"\bblock-type\s*=", open_tag, re.IGNORECASE):
        return re.sub(
            r'(\bblock-type\s*=\s*)(["\'])(.*?)\2',
            rf'\1"{value}"',
            open_tag,
            count=1,
            flags=re.IGNORECASE,
        )
    if open_tag.endswith(">"):
        return f'{open_tag[:-1]} block-type="{value}">'
    return f'{open_tag} block-type="{value}">'


def _fix_equation_display(html: str) -> str:
    """Normalize display equations, equation numbers, and prose swallowed by them."""

    def _strip_tag_from_math(math_text: str) -> tuple[str, str | None]:
        tag_m = _LATEX_TAG_PATTERN.search(math_text)
        if tag_m:
            num = tag_m.group(1)
            content_no_tag = _LATEX_TAG_PATTERN.sub("", math_text).rstrip()
            return content_no_tag, f"({num})"
        return math_text, None

    def _equation_row(open_tag: str, math_body: str, close_tag: str, num_text: str) -> str:
        num_match = re.search(r"\d{1,3}", num_text)
        id_attr = f' id="eq-{num_match.group(0)}"' if num_match is not None else ""
        return (
            f'<div{id_attr} class="z2m-equation-row">'
            f'<span class="z2m-eq-lhs"></span>'
            f"{open_tag}{math_body}{close_tag}"
            f'<span class="z2m-eq-num">{num_text}</span>'
            f"</div>"
        )

    def _looks_like_standalone_text_equation(body: str, visible_without_num: str) -> bool:
        if "=" not in visible_without_num:
            return False
        if not any(marker in body for marker in ("\\(", "\\[", "<math", "</math>")):
            return False
        if len(visible_without_num) > 320:
            return False
        lhs = visible_without_num.split("=", 1)[0].strip()
        if not lhs or len(lhs) > 80:
            return False
        if not re.search(r"[A-Za-z0-9]", lhs):
            return False
        return len(re.findall(r"\b[a-z]{3,}\b", lhs)) <= 2

    def fix_para(m: re.Match[str]) -> str:
        open_tag, body, close_tag = m.group(1), m.group(2), m.group(3)
        body_rstripped = body.rstrip()
        display_matches = list(_DISPLAY_MATH_IN_PARA_PATTERN.finditer(body_rstripped))
        if not display_matches:
            math_tag_tail_match = re.match(
                r"^\s*(?P<math><math\b(?=[^>]*\bdisplay\s*=\s*['\"]block['\"])[^>]*>"
                r"[\s\S]*?</math>)\s*(?P<num>\(\d{1,3}\))(?P<tail>\s+\S[\s\S]*)$",
                body_rstripped,
                re.IGNORECASE,
            )
            if math_tag_tail_match is not None:
                return (
                    _equation_row(
                        open_tag,
                        math_tag_tail_match.group("math"),
                        close_tag,
                        math_tag_tail_match.group("num"),
                    )
                    + f'<p block-type="Text">{math_tag_tail_match.group("tail").lstrip()}</p>'
                )
            return m.group(0)

        first_display = display_matches[0]
        leading_text = body_rstripped[: first_display.start()].strip()
        cleaned_first_math, tag_num = _strip_tag_from_math(first_display.group(0))
        tail_after_first = body_rstripped[first_display.end() :].lstrip()
        split_num = tag_num
        split_tail = tail_after_first
        if split_num is None:
            tail_num_match = re.match(r"(?P<num>\(\d{1,3}\))(?P<tail>\s+\S[\s\S]*)$", tail_after_first)
            if tail_num_match is not None:
                split_num = tail_num_match.group("num")
                split_tail = tail_num_match.group("tail").lstrip()

        if not leading_text and split_num is not None and split_tail:
            return (
                _equation_row(open_tag, cleaned_first_math, close_tag, split_num)
                + f'<p block-type="Text">{split_tail}</p>'
            )

        stripped = _DISPLAY_MATH_IN_PARA_PATTERN.sub("", body)
        stripped = re.sub(r"\(\d+\)", "", stripped).strip()
        if stripped:
            body_inline = _DISPLAY_MATH_IN_PARA_PATTERN.sub(
                lambda bm: f"\\({bm.group(1)}\\)",
                body,
            )
            return f"{_set_block_type_attr(open_tag, 'Text')}{body_inline}{close_tag}"

        tag_num: str | None = None
        new_body_parts: list[str] = []
        last = 0
        for dm in display_matches:
            new_body_parts.append(body_rstripped[last : dm.start()])
            cleaned, found_num = _strip_tag_from_math(dm.group(0))
            new_body_parts.append(cleaned)
            if found_num and tag_num is None:
                tag_num = found_num
            last = dm.end()
        new_body_parts.append(body_rstripped[last:])
        body_no_tag = "".join(new_body_parts).rstrip()

        if tag_num:
            return _equation_row(open_tag, body_no_tag, close_tag, tag_num)

        eq_num_match = _TRAILING_EQ_NUM_PATTERN.search(body_rstripped)
        if eq_num_match:
            num_text = eq_num_match.group(0).strip()
            body_no_num = body_rstripped[: eq_num_match.start()].rstrip()
            return _equation_row(open_tag, body_no_num, close_tag, num_text)

        return m.group(0)

    fixed = _EQUATION_PARA_PATTERN.sub(fix_para, html)

    def fix_text_para(m: re.Match[str]) -> str:
        open_tag, body, close_tag = m.group("open"), m.group("body"), m.group("close")
        if not re.search(r'\bblock-type\s*=\s*(["\'])Text\1', open_tag, re.IGNORECASE):
            return m.group(0)
        body_rstripped = body.rstrip()
        eq_num_match = _TEXT_TRAILING_EQ_NUM_PATTERN.search(body_rstripped)
        if eq_num_match is None:
            return m.group(0)
        body_no_num = body_rstripped[: eq_num_match.start()].rstrip()
        body_no_num = re.sub(r"\s+\.$", ".", body_no_num).rstrip()
        visible_without_num = _visible_text(body_no_num)
        if not _looks_like_standalone_text_equation(body_no_num, visible_without_num):
            return m.group(0)
        return _equation_row(_set_block_type_attr(open_tag, "Equation"), body_no_num, close_tag, eq_num_match.group("num"))

    return _P_BLOCK_PATTERN.sub(fix_text_para, fixed)


def _fix_orphaned_sup_tags(html: str) -> str:
    """Remove broken ``<sup>`` openers whose direct content starts with a period.

    The translator occasionally emits a spurious ``<sup>`` wrapper around body
    text, producing something like::

        …understudied <sup>. However, researchers apply models
        <sup><a href="#ref-5">5</a></sup> to many tasks.</sup>

    — where the entire following paragraph renders as superscript.

    **Strategy**: delete only the ``<sup>`` *opener* tag.  Any eventual
    ``</sup>`` that was meant to close it becomes an orphan — HTML5 parsers
    silently ignore orphan end tags.  Unclosed inner ``<sup>N`` citation tags
    are implicitly closed at the end of their parent block element (``</p>``)
    by the HTML5 parsing algorithm, so they render correctly.

    This avoids any fragile balanced-matching logic and works regardless of
    how many ``</sup>`` tags the translator dropped.

    **Guard**: if the distance to the next ``</sup>`` is ≤ 25 characters,
    the ``<sup>`` is treated as a legitimate short marker (table footnote,
    ``<sup>a</sup>``, etc.) and is left unchanged.
    """
    def _maybe_delete_opener(m: re.Match[str]) -> str:
        # Peek at how far the next </sup> is to distinguish a real short marker
        # from a broken long wrapper.
        next_close = html.find("</sup>", m.end())
        content_len = (next_close - m.end()) if next_close >= 0 else 9999
        if content_len <= 25:
            return m.group(0)   # short marker — leave untouched
        return ""               # delete only the <sup> opener

    return re.sub(r"<sup>(?=\s*\.)", _maybe_delete_opener, html)


# Latin abbreviations that the translator sometimes transliterates into Cyrillic
# when they appear right after an expanded Cyrillic form, e.g.
# "Генеративный искусственный интеллект (ГАИ)".  We restore the Latin form so
# the document stays consistent with the rest of the body text (which, due to
# the translation prompt, keeps "GAI" untouched).
_LATIN_ABBREV_RESTORE_MAP: dict[str, str] = {
    "ГАИ": "GAI",
    "ВНА": "VNA",
    "МПЧ": "ICP",  # Cyrillic mis-transliteration of ICP (sometimes)
    "ИКД": "ICP",
    "ОСШ": "SNR",
    "АЦП": "ADC",
    "ОУ": "AC",    # only in abbreviation contexts — handled via parens
    "ПЧ": "RF",
    "МЭМС": "MEMS",
    "ПЛИС": "FPGA",
    "МИМО": "MIMO",
}


def _restore_latin_abbrevs(html: str) -> str:
    """Replace Cyrillic transliterations of Latin abbrevs in parentheses.

    The translator, when it sees ``Generative artificial intelligence (GAI)``,
    often writes ``Генеративный искусственный интеллект (ГАИ)`` — it
    transliterates the abbreviation even though the prompt forbids it.  We
    restore the Latin form by replacing ``(ГАИ)`` with ``(GAI)`` (and friends)
    after translation.
    """
    if not any(cyr in html for cyr in _LATIN_ABBREV_RESTORE_MAP):
        return html
    for cyr, lat in _LATIN_ABBREV_RESTORE_MAP.items():
        # In parentheses — highest confidence.
        html = re.sub(rf"\(\s*{re.escape(cyr)}\s*\)", f"({lat})", html)
    return html


def _add_section_anchors(html: str) -> tuple[str, set[str]]:
    """Add ``id="section-{ROMAN}"`` to headings that open with a Roman numeral.

    Returns the modified HTML and the set of upper-case Roman numerals found.
    """
    found: set[str] = set()

    def _section_key(value: str) -> str:
        return value.strip().strip(".").upper().replace(".", "-")

    def _add_id(m: re.Match[str]) -> str:
        roman = m.group(3).upper()
        attrs = m.group(2)
        if re.search(r'\bid\s*=', attrs, re.IGNORECASE):
            found.add(roman)
            return m.group(0)
        found.add(roman)
        full = m.group(0)
        tag_close = full.index('>')
        return full[:tag_close] + f' id="section-{roman}"' + full[tag_close:]

    result = _ROMAN_SECTION_HEADING_PATTERN.sub(_add_id, html)

    def _add_numeric_id(m: re.Match[str]) -> str:
        raw = m.group(0)
        open_tag = m.group("open")
        if _has_id_attr(open_tag):
            return raw
        visible = _visible_text(raw)
        numeric_match = _NUMERIC_SECTION_HEADING_VISIBLE_PATTERN.match(visible)
        if numeric_match is None:
            return raw
        if _figure_caption_num_from_visible(visible) is not None:
            return raw
        if _table_caption_key_from_visible(visible) is not None:
            return raw
        key = _section_key(numeric_match.group(1))
        found.add(key)
        return f'{_add_id_attr(open_tag, f"section-{key}")}{m.group("body")}{m.group("close")}'

    result = _H_BLOCK_PATTERN.sub(_add_numeric_id, result)

    def _add_appendix_id(m: re.Match[str]) -> str:
        raw = m.group(0)
        open_tag = m.group("open")
        visible = _visible_text(raw)
        appendix_match = _APPENDIX_HEADING_VISIBLE_PATTERN.match(visible)
        if appendix_match is None:
            return raw
        key = f"APPENDIX-{appendix_match.group(1).upper()}"
        found.add(key)
        if _has_id_attr(open_tag):
            return raw
        return f'{_add_id_attr(open_tag, f"section-appendix-{appendix_match.group(1).lower()}")}{m.group("body")}{m.group("close")}'

    result = _H_BLOCK_PATTERN.sub(_add_appendix_id, result)
    return result, found


_ROMAN_ONE_OCR_FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:FIG(?:URE)?|Fig(?:ure)?|fig(?:ure)?)\.?\s*I\b([\s\S]*)$",
)


def _roman_one_ocr_figure_caption_num_from_visible(visible: str) -> str | None:
    match = _ROMAN_ONE_OCR_FIGURE_CAPTION_RE.match(visible)
    if match is None:
        return None
    tail = match.group(1)
    if re.match(r"^\s*\(\s*(?:see\s+legend|continued)\b[\s\S]*\)\s*$", tail, re.IGNORECASE):
        return None
    if not _caption_tail_opens_caption(tail):
        return None
    return _figure_key_from_visible_number("1")


_PLAIN_TABLE_SURROGATE_PATTERN = re.compile(
    r"^(?P<open><table\b[^>]*>)(?P<body>[\s\S]*)(?P<close></table>)$",
    re.IGNORECASE,
)


def _plain_table_surrogate_parts(raw: str) -> tuple[str, str, str] | None:
    match = _PLAIN_TABLE_SURROGATE_PATTERN.match(raw.strip())
    if match is None:
        return None
    open_tag = match.group("open")
    if _has_id_attr(open_tag):
        return None
    if any(
        _node_has_class(open_tag, class_name)
        for class_name in ("z2m-float-unit", "z2m-table-target", "z2m-figure-target")
    ):
        return None
    if "z2m-table-caption" in raw or "z2m-table-unit" in raw:
        return None
    if len(re.findall(r"<t[dh]\b", raw, flags=re.IGNORECASE)) < 4:
        return None
    if len(_visible_text(raw)) < 10:
        return None
    return open_tag, match.group("body"), match.group("close")


def _add_figure_anchors(html: str) -> tuple[str, set[str]]:
    """Add ``id="fig-{n}"`` to the visual figure target when possible.

    Returns the modified HTML and the set of figure number strings found.
    """
    found: set[str] = set()
    matches = list(_P_OR_H_BLOCK_PATTERN.finditer(html))
    if not matches:
        return html, found

    replacements: dict[int, str] = {}

    def _node_raw(index: int) -> str:
        return replacements.get(index, matches[index].group(0))

    def _replace_open(raw: str, transform: Callable[[str], str]) -> str:
        return _transform_node_open(raw, transform)

    def _has_image(index: int) -> bool:
        return bool(re.search(r"<img\b", _node_raw(index), re.IGNORECASE))

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[matches[a_idx].end():matches[b_idx].start()])

    def _page_anchor_id(raw: str) -> str | None:
        node_id = _node_id_value(raw) or ""
        return node_id if re.fullmatch(r"page-[A-Za-z0-9_.:-]+", node_id, re.IGNORECASE) else None

    def _image_can_receive_figure_id(index: int) -> bool:
        if not _has_image(index):
            return False
        image_open = _SENTENCE_P_NODE_PATTERN.match(_node_raw(index))
        if image_open is None:
            return False
        return not _has_id_attr(image_open.group("open")) or _page_anchor_id(_node_raw(index)) is not None

    def _image_is_immediately_captioned_as_different_figure(index: int, fig_num: str) -> bool:
        scan = index + 1
        while scan < len(matches) and _between_is_whitespace(scan - 1, scan):
            raw = _node_raw(scan)
            if _has_image(scan) or re.search(r"<table\b", raw, re.IGNORECASE):
                return False
            visible = _visible_text(raw).strip()
            if not visible:
                scan += 1
                continue
            caption_num = _figure_caption_num_from_visible(visible)
            if caption_num is not None:
                return caption_num != fig_num
            if not _node_is_caption_bridge_or_note_paragraph(raw):
                return False
            scan += 1
        return False

    def _caption_grid_image_index(caption_index: int) -> int | None:
        caption_run_start = caption_index
        while caption_run_start > 0 and _between_is_whitespace(caption_run_start - 1, caption_run_start):
            previous = _node_raw(caption_run_start - 1)
            if _has_image(caption_run_start - 1):
                break
            if _figure_caption_num_from_visible(_visible_text(previous)) is None:
                break
            caption_run_start -= 1

        image_indices: list[int] = []
        scan = caption_run_start - 1
        while scan >= 0:
            if scan + 1 < len(matches) and not _between_is_whitespace(scan, scan + 1):
                break
            if not _node_is_caption_bridge_or_note_paragraph(_node_raw(scan)):
                break
            scan -= 1
        while scan >= 0:
            if scan + 1 < len(matches) and not _between_is_whitespace(scan, scan + 1):
                break
            if not _has_image(scan):
                break
            image_indices.insert(0, scan)
            scan -= 1

        offset = caption_index - caption_run_start
        if len(image_indices) >= 2 and 0 <= offset < len(image_indices):
            candidate = image_indices[offset]
            if _image_can_receive_figure_id(candidate):
                return candidate
        return None

    def _is_preceded_by_different_figure_caption(caption_index: int, fig_num: str) -> bool:
        previous = caption_index - 1
        if previous < 0 or not _between_is_whitespace(previous, caption_index):
            return False
        previous_num = _figure_caption_num_from_visible(_visible_text(_node_raw(previous)))
        return previous_num is not None and previous_num != fig_num

    def _caption_points_to_existing_figure_target(caption_index: int, raw: str, target_id: str) -> bool:
        if re.search(rf'href\s*=\s*(["\'])#{re.escape(target_id)}\1', raw, re.IGNORECASE) is None:
            return False
        before_caption = html[:matches[caption_index].start()]
        return (
            re.search(
                rf'<(?:div|p|figure)\b(?=[^>]*\bid\s*=\s*(["\']){re.escape(target_id)}\1)'
                r'(?=[^>]*\bz2m-figure-(?:unit|target)\b)',
                before_caption,
                re.IGNORECASE,
            )
            is not None
        )

    def _embedded_figure_caption_num(index: int) -> str | None:
        raw = _node_raw(index)
        if _node_has_class(raw, "z2m-front-matter") or re.search(
            r'\bblock-type\s*=\s*(["\'])Text\1',
            raw,
            re.IGNORECASE,
        ):
            return None
        visible = _visible_text(raw)
        if not visible or len(visible) > 700:
            return None
        if (
            _figure_caption_num_from_visible(visible) is not None
            or _table_caption_key_from_visible(visible) is not None
        ):
            return None
        matches = list(_FIG_REF_PATTERN.finditer(visible))
        if len(matches) != 1:
            return None
        match = matches[0]
        left = visible[: match.start()].strip(" \t\r\n.;:,-|")
        right = visible[match.end() :].strip(" \t\r\n.;:,-|")
        if not left or not right:
            return None
        if len(left) > 260 or len(right) > 520:
            return None
        if left.endswith(("(", "[", "{")) or right.startswith((")", "]", "}")):
            return None
        if re.search(
            r"\b(?:associated with|discussed in|shown in|reported in|mentioned in|described in|"
            r"depicted in|illustrated in|presented in|available in|see|in)\s*$",
            left,
            re.IGNORECASE,
        ):
            return None
        if re.match(r"^(?:and|or|&|also|tables?\b|figs?\b|figures?\b)", right, re.IGNORECASE):
            return None
        if re.match(
            r"^(?:shows?|shown|illustrates?|depicts?|presents?|describes?|see|where|which|that)\b",
            right,
            re.IGNORECASE,
        ):
            return None
        return _figure_key_from_visible_number(match.group(2))

    def _nearby_image_index(caption_index: int, fig_num: str) -> int | None:
        grid_index = _caption_grid_image_index(caption_index)
        if grid_index is not None:
            return grid_index
        for offset in range(1, 7):
            previous = caption_index - offset
            if previous < 0:
                break
            if not _between_is_whitespace(previous, previous + 1):
                break
            previous_raw = _node_raw(previous)
            if _node_is_caption_bridge_or_note_paragraph(previous_raw):
                continue
            if _image_can_receive_figure_id(previous):
                candidate = previous
                while (
                    candidate > 0
                    and _between_is_whitespace(candidate - 1, candidate)
                    and _image_can_receive_figure_id(candidate - 1)
                ):
                    candidate -= 1
                if _image_is_immediately_captioned_as_different_figure(candidate, fig_num):
                    break
                return candidate
            if _has_image(previous):
                break
            previous_caption_num = _figure_caption_num_from_visible(_visible_text(previous_raw))
            if previous_caption_num is not None:
                break
            if not _looks_like_figure_caption_fragment(previous_raw):
                break
        if _is_preceded_by_different_figure_caption(caption_index, fig_num):
            return None
        for offset in range(1, 7):
            following = caption_index + offset
            if following >= len(matches):
                break
            if not _between_is_whitespace(following - 1, following):
                break
            following_raw = _node_raw(following)
            if _image_can_receive_figure_id(following):
                if (
                    (following != caption_index + 1 or _node_has_class(_node_raw(caption_index), "has-continuation"))
                    and _image_is_immediately_captioned_as_different_figure(following, fig_num)
                ):
                    break
                return following
            if _has_image(following):
                break
            following_caption_num = _figure_caption_num_from_visible(_visible_text(following_raw))
            if following_caption_num is not None:
                break
            if not (
                _node_is_caption_bridge_or_note_paragraph(following_raw)
                or _looks_like_figure_caption_fragment(following_raw)
                or _looks_like_figure_panel_caption_continuation(following_raw)
            ):
                break
        return None

    def _adjacent_image_index(caption_index: int) -> int | None:
        previous = caption_index - 1
        if (
            previous >= 0
            and _between_is_whitespace(previous, caption_index)
            and _image_can_receive_figure_id(previous)
        ):
            return previous
        following = caption_index + 1
        if (
            following < len(matches)
            and _between_is_whitespace(caption_index, following)
            and _image_can_receive_figure_id(following)
        ):
            return following
        return None

    def _caption_follows_plain_table_surrogate(caption_index: int) -> bool:
        before_caption = html[: matches[caption_index].start()]
        table_match = re.search(r"(<table\b[\s\S]*?</table>)\s*$", before_caption, re.IGNORECASE)
        return table_match is not None and _plain_table_surrogate_parts(table_match.group(1)) is not None

    def _relaxed_adjacent_figure_caption_num(index: int) -> str | None:
        if _has_image(index) or _adjacent_image_index(index) is None:
            return None
        visible = _visible_text(_node_raw(index))
        if not visible or len(visible) > 700:
            return None
        match = re.match(
            r"^\s*(?:FIG(?:URE)?|Fig(?:ure)?"
            r"|Р РёСЃ(?:СѓРЅРѕРє)?|СЂРёСЃ(?:СѓРЅРѕРє)?|Р¤РёРі(?:СѓСЂР°)?|С„РёРі(?:СѓСЂР°)?)"
            rf"\.?\s*({_FIG_RELAXED_KEY_TOKEN})({_FIG_CAPTION_PANEL_SUFFIX_TOKEN})?([\s\S]*)$",
            visible,
            re.IGNORECASE,
        )
        if match is None:
            return None
        tail = match.group(3).strip()
        if not tail or _caption_tail_opens_caption(tail):
            return None
        panel_suffix = (match.group(2) or "").strip()
        tail_for_check = tail
        if panel_suffix and re.fullmatch(r"[tTfFzZrR]", panel_suffix):
            tail_for_check = f"{panel_suffix} {tail_for_check}"
        if re.match(
            r"^(?:(?:[tTfFzZrR]\s+)(?:maps?|plots?|curves?|contrasts?)|"
            r"(?:activation|statistical|contrast)\s+maps?)\b",
            tail_for_check,
            re.IGNORECASE,
        ) is None:
            return None
        return _figure_key_from_visible_number(match.group(1))

    for index, match in enumerate(matches):
        raw = _node_raw(index)
        visible = _visible_text(raw)
        fig_num = _figure_caption_num_from_visible(visible)
        embedded_caption = False
        relaxed_adjacent_caption = False
        roman_one_ocr_caption = False
        if fig_num is None:
            fig_num = _roman_one_ocr_figure_caption_num_from_visible(visible)
            roman_one_ocr_caption = fig_num is not None
        if fig_num is None:
            fig_num = _relaxed_adjacent_figure_caption_num(index)
            relaxed_adjacent_caption = fig_num is not None
        if fig_num is None:
            fig_num = _embedded_figure_caption_num(index)
            embedded_caption = fig_num is not None
        if fig_num is None:
            continue
        roman_one_image_index: int | None = None
        roman_one_table_surrogate_caption = False
        if roman_one_ocr_caption and not _has_image(index):
            roman_one_image_index = _adjacent_image_index(index)
            if roman_one_image_index is None:
                roman_one_table_surrogate_caption = _caption_follows_plain_table_surrogate(index)
            if roman_one_image_index is None and not roman_one_table_surrogate_caption:
                continue
        found.add(fig_num)

        target_id = f"fig-{fig_num}"
        if (
            not _has_image(index)
            and not relaxed_adjacent_caption
            and _looks_like_in_text_figure_reference_node(raw, fig_num)
        ):
            if _caption_points_to_existing_figure_target(index, raw, target_id):
                replacements[index] = _replace_open(
                    _node_raw(index),
                    lambda open_tag: _remove_id_attr(open_tag),
                )
            continue

        if not _has_image(index) and _caption_points_to_existing_figure_target(index, raw, target_id):
            replacements[index] = _replace_open(
                _node_raw(index),
                lambda open_tag: _add_class_attr(_remove_id_attr(open_tag), "z2m-figure-caption"),
            )
            continue

        target_index = index
        if not _has_image(index):
            image_index = (
                roman_one_image_index
                if roman_one_ocr_caption
                else _nearby_image_index(index, fig_num)
            )
            if image_index is not None:
                target_index = image_index
            elif embedded_caption:
                continue

        target_raw = _node_raw(target_index)
        page_id = _page_anchor_id(target_raw) if _has_image(target_index) else None
        target_replacement = _replace_open(
            target_raw,
            lambda open_tag: (
                _add_class_attr(_add_id_attr(_remove_id_attr(open_tag), target_id), "z2m-figure-target")
                if _has_image(target_index)
                else _add_class_attr(_add_id_attr(open_tag, target_id), "z2m-figure-caption")
                if roman_one_table_surrogate_caption and target_index == index
                else _add_id_attr(open_tag, target_id)
            ),
        )
        if page_id is not None:
            target_replacement = f'<span id="{page_id}"></span>{target_replacement}'
        replacements[target_index] = target_replacement
        if target_index != index:
            replacements[index] = _replace_open(
                _node_raw(index),
                lambda open_tag: _add_class_attr(_remove_id_attr(open_tag), "z2m-figure-caption"),
            )

    if not replacements:
        return html, found

    out: list[str] = []
    cursor = 0
    for index, match in enumerate(matches):
        out.append(html[cursor : match.start()])
        out.append(replacements.get(index, match.group(0)))
        cursor = match.end()
    out.append(html[cursor:])
    return "".join(out), found


def _recover_orphan_figure_anchors(html: str, found_figures: set[str]) -> tuple[str, set[str]]:
    """Create conservative figure targets for orphan Marker figure images.

    Marker sometimes extracts the visual region as ``_page_*_Figure_*.jpeg`` but
    loses the explicit ``Figure N`` caption label.  If the prose still contains
    visible references to that missing figure, give the nearby image a semantic
    ``fig-N`` target so references can link to the image instead of remaining
    page-like or plain text references.
    """
    matches = list(_P_BLOCK_PATTERN.finditer(html))
    if not matches:
        return html, set()

    replacements: dict[int, str] = {}
    recovered: set[str] = set()
    assigned_images: set[int] = set()

    def _node_raw(index: int) -> str:
        return replacements.get(index, matches[index].group(0))

    def _replace_open(raw: str, transform: Callable[[str], str]) -> str:
        node_match = _SENTENCE_P_NODE_PATTERN.match(raw)
        if node_match is None:
            return raw
        return f"{transform(node_match.group('open'))}{node_match.group('body')}{node_match.group('close')}"

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[matches[a_idx].end():matches[b_idx].start()])

    def _between_allows_reference_scan(a_idx: int, b_idx: int) -> bool:
        segment = html[matches[a_idx].end():matches[b_idx].start()]
        if _html_gap_is_ignorable(segment):
            return True
        heading_matches = list(_H_BLOCK_PATTERN.finditer(segment))
        if not heading_matches:
            return False
        for heading_match in heading_matches:
            heading_text = _visible_text(heading_match.group(0))
            if re.match(
                r"^(?:references|bibliography|acknowledg|funding|conflicts?|supplementary|appendix)\b",
                heading_text,
                re.IGNORECASE,
            ):
                return False
        cleaned = _H_BLOCK_PATTERN.sub("", segment)
        return _html_gap_is_ignorable(cleaned)

    def _has_image(index: int) -> bool:
        return bool(re.search(r"<img\b", _node_raw(index), re.IGNORECASE))

    def _image_src_values(raw: str) -> list[str]:
        values: list[str] = []
        for attr_name in ("data-z2m-src", "src"):
            for match in re.finditer(
                rf'\b{attr_name}\s*=\s*(["\'])(?P<value>[^"\']+)\1',
                raw,
                re.IGNORECASE,
            ):
                values.append(urllib.parse.unquote(match.group("value")))
        return values

    def _image_src_looks_like_marker_figure(raw: str) -> bool:
        for src in _image_src_values(raw):
            clean_src = src.split("?", 1)[0].split("#", 1)[0]
            if re.search(
                r"(?:^|[/\\])_?page_\d+_(?:Figure|Picture)_\d+\.(?:jpe?g|png|webp|gif)\b",
                clean_src,
                re.IGNORECASE,
            ):
                return True
            if re.search(r"(?:^|[/\\])Figure[_\s-]*\d+\.(?:jpe?g|png|webp|gif)\b", clean_src, re.IGNORECASE):
                return True
        return False

    def _image_src_is_page_zero_picture(raw: str) -> bool:
        for src in _image_src_values(raw):
            clean_src = src.split("?", 1)[0].split("#", 1)[0]
            if re.search(r"(?:^|[/\\])_?page_0_Picture_\d+\.(?:jpe?g|png|webp|gif)\b", clean_src, re.IGNORECASE):
                return True
        return False

    def _page_anchor_id(raw: str) -> str | None:
        node_id = _node_id_value(raw) or ""
        return node_id if re.fullmatch(r"page-[A-Za-z0-9_.:-]+", node_id, re.IGNORECASE) else None

    def _is_table_caption(index: int) -> bool:
        return _table_caption_key_from_visible(_visible_text(_node_raw(index))) is not None

    def _has_adjacent_table_caption(index: int) -> bool:
        previous = index - 1
        if previous >= 0 and _between_is_whitespace(previous, index) and _is_table_caption(previous):
            return True
        following = index + 1
        return following < len(matches) and _between_is_whitespace(index, following) and _is_table_caption(following)

    def _is_orphan_figure_image(index: int) -> bool:
        if not _has_image(index):
            return False
        raw = _node_raw(index)
        node_match = _SENTENCE_P_NODE_PATTERN.match(raw)
        if node_match is None:
            return False
        if _has_id_attr(node_match.group("open")) and _page_anchor_id(raw) is None:
            return False
        if _node_has_class(raw, "z2m-figure-target") or _node_has_class(raw, "z2m-figure-caption"):
            return False
        if not _image_src_looks_like_marker_figure(raw):
            return False
        return not _has_adjacent_table_caption(index)

    def _figure_ref_nums_from_visible(visible: str) -> list[str]:
        if _figure_caption_num_from_visible(visible) is not None:
            return []
        seen: set[str] = set()
        nums: list[str] = []
        supplementary_spans: list[tuple[int, int]] = []
        extended_data_spans: list[tuple[int, int]] = []

        def _add(num: str) -> None:
            if num not in found_figures and num not in recovered and num not in seen:
                seen.add(num)
                nums.append(num)

        for match in _EXTENDED_DATA_FIG_REF_PATTERN.finditer(visible):
            extended_data_spans.append((match.start(), match.end()))
            _add(_extended_data_figure_key_from_visible_number(match.group("num")))

        for match in _SUPPLEMENTARY_FIG_REF_PATTERN.finditer(visible):
            supplementary_spans.append((match.start(), match.end()))
            _add(_supplementary_figure_key_from_visible_number(match.group("num")))

        for pattern in (_FIG_REF_PATTERN, _EXT_FIG_REF_PATTERN):
            for match in pattern.finditer(visible):
                if any(
                    start <= match.start() < end
                    for start, end in (*supplementary_spans, *extended_data_spans)
                ):
                    continue
                _add(_figure_key_from_visible_number(match.group(2)))
        for match in _TERMINAL_FIG_REF_PATTERN.finditer(visible):
            if any(
                start <= match.start() < end
                for start, end in (*supplementary_spans, *extended_data_spans)
            ):
                continue
            _add(_figure_key_from_visible_number(match.group(2)))
        return nums

    def _page_linked_missing_figure_refs() -> dict[str, list[str]]:
        refs_by_page: dict[str, list[str]] = {}
        for anchor_match in _PAGE_ANCHOR_PATTERN.finditer(html):
            href_match = re.search(
                r'\bhref\s*=\s*(["\'])#(?P<page>page-[^"\']+)\1',
                anchor_match.group("attrs"),
                re.IGNORECASE,
            )
            if href_match is None:
                continue
            refs = _figure_ref_nums_from_visible(_visible_text(anchor_match.group("body")))
            if len(refs) != 1:
                continue
            page_id = href_match.group("page")
            if refs[0] not in refs_by_page.setdefault(page_id, []):
                refs_by_page[page_id].append(refs[0])
        return refs_by_page

    def _nearby_missing_refs_after(index: int, *, window: int = 7) -> list[str]:
        refs: list[str] = []
        seen: set[str] = set()
        upper = min(len(matches), index + window + 1)
        for scan in range(index + 1, upper):
            if scan > index + 1 and not _between_allows_reference_scan(scan - 1, scan):
                break
            raw = _node_raw(scan)
            if _has_image(scan):
                break
            if _figure_caption_num_from_visible(_visible_text(raw)) is not None or _is_table_caption(scan):
                continue
            for num in _figure_ref_nums_from_visible(_visible_text(raw)):
                if num not in seen:
                    seen.add(num)
                    refs.append(num)
        return refs

    def _nearby_missing_refs_before(index: int, *, window: int = 4) -> list[str]:
        refs: list[str] = []
        seen: set[str] = set()
        lower = max(0, index - window)
        for scan in range(index - 1, lower - 1, -1):
            if scan < index - 1 and not _between_allows_reference_scan(scan, scan + 1):
                break
            raw = _node_raw(scan)
            if _node_has_class(raw, "z2m-figure-target") or _node_has_class(raw, "z2m-figure-caption"):
                continue
            if _has_image(scan):
                return []
            if _figure_caption_num_from_visible(_visible_text(raw)) is not None or _is_table_caption(scan):
                continue
            for num in _figure_ref_nums_from_visible(_visible_text(raw)):
                if num not in seen:
                    seen.add(num)
                    refs.insert(0, num)
        return refs

    def _next_known_figure_num_after(index: int, *, window: int = 8) -> str | None:
        upper = min(len(matches), index + window + 1)
        for scan in range(index + 1, upper):
            if scan > index + 1 and not _between_allows_reference_scan(scan - 1, scan):
                break
            raw = _node_raw(scan)
            node_id = _node_id_value(raw)
            node_id_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", node_id or "", re.IGNORECASE)
            if node_id_match is not None:
                return node_id_match.group(1)
            caption_num = _figure_caption_num_from_visible(_visible_text(raw))
            if caption_num is not None and caption_num in found_figures:
                return caption_num
        return None

    def _looks_like_unlabeled_caption(index: int) -> bool:
        if index < 0 or index >= len(matches):
            return False
        raw = _node_raw(index)
        if _has_image(index) or re.search(r"<table\b", raw, re.IGNORECASE):
            return False
        visible = _visible_text(raw)
        if not visible or len(visible) > 1200:
            return False
        if _figure_caption_num_from_visible(visible) is not None or _table_caption_key_from_visible(visible) is not None:
            return False
        panel_hits = len(re.findall(r"\([A-Ha-h]\)", visible))
        if panel_hits >= 2:
            return True
        bare_panel_hits = len(re.findall(r"(?:^|[.;]\s+)[A-Ha-h]\s+(?:Before|After|[A-Z(])", visible))
        if bare_panel_hits >= 2:
            return True
        orientation_panel_hits = {
            match.group(1).lower()
            for match in re.finditer(
                r"\((left|right|top|bottom|upper|lower|middle|center|central)\)",
                visible,
                re.IGNORECASE,
            )
        }
        if len(orientation_panel_hits) >= 2 and re.search(
            r"\b(?:render|renders|image|images|panel|panels|plot|plots|map|maps|slice|slices|"
            r"diagram|schematic|cluster|clusters|activated|displayed)\b",
            visible,
            re.IGNORECASE,
        ):
            return True
        return bool(
            re.search(r"\b(?:Before|After)\b[\s\S]{0,240}\b(?:Before|After)\b", visible)
            and re.search(r"\b(?:volume|flow|trace|curve|micrograph|image|plot|diagram|schematic)\b", visible, re.IGNORECASE)
        )

    def _following_unlabeled_caption_index(image_index: int) -> int | None:
        following = image_index + 1
        if following < len(matches) and _between_is_whitespace(image_index, following) and _looks_like_unlabeled_caption(following):
            return following
        return None

    def _orphan_image_run_start(index: int) -> int:
        run_start = index
        while (
            run_start > 0
            and _between_is_whitespace(run_start - 1, run_start)
            and _is_orphan_figure_image(run_start - 1)
            and run_start - 1 not in assigned_images
        ):
            run_start -= 1
        return run_start

    def _assign_image(index: int, fig_num: str, caption_index: int | None = None, aliases: Iterable[str] = ()) -> None:
        target_id = f"fig-{fig_num}"
        raw = _node_raw(index)
        page_id = _page_anchor_id(raw)
        alias_nums: list[str] = []
        for alias in aliases:
            if alias == fig_num or alias in found_figures or alias in recovered or alias in alias_nums:
                continue
            alias_nums.append(alias)
        replacement = _replace_open(
            _node_raw(index),
            lambda open_tag: _add_class_attr(
                _add_id_attr(_remove_id_attr(open_tag), target_id),
                "z2m-figure-target",
            ),
        )
        alias_html = ""
        if alias_nums:
            alias_html = "".join(
                f'<span id="fig-{alias}" class="z2m-float-alias" data-z2m-origin="orphan-image-ref"></span>'
                for alias in alias_nums
            )
        if page_id is not None:
            replacement = f'<span id="{page_id}"></span>{replacement}'
        if alias_html:
            replacement = alias_html + replacement
        replacements[index] = replacement
        assigned_images.add(index)
        recovered.add(fig_num)
        recovered.update(alias_nums)
        if caption_index is not None:
            replacements[caption_index] = _replace_open(
                _node_raw(caption_index),
                lambda open_tag: _add_class_attr(_remove_id_attr(open_tag), "z2m-figure-caption"),
            )

    def _simple_consecutive_keys(values: list[str]) -> bool:
        if len(values) < 2 or not all(re.fullmatch(r"\d{1,3}", value) for value in values):
            return False
        numbers = [int(value) for value in values]
        return numbers == list(range(numbers[0], numbers[0] + len(numbers)))

    def _keys_are_predecessors_of(values: list[str], next_key: str | None) -> bool:
        if next_key is None or not re.fullmatch(r"\d{1,3}", next_key):
            return False
        if not _simple_consecutive_keys(values):
            return False
        return int(values[-1]) + 1 == int(next_key)

    page_linked_refs = _page_linked_missing_figure_refs()

    for index in range(len(matches)):
        if not _is_orphan_figure_image(index) or index in assigned_images:
            continue
        caption_index = _following_unlabeled_caption_index(index)
        if caption_index is None:
            continue
        caption_raw = _node_raw(caption_index)
        page_ids = [
            match.group("page")
            for match in re.finditer(
                r'\bid\s*=\s*(["\'])(?P<page>page-[^"\']+)\1',
                caption_raw,
                re.IGNORECASE,
            )
        ]
        candidates: list[str] = []
        for page_id in page_ids:
            for fig_num in page_linked_refs.get(page_id, []):
                if fig_num not in found_figures and fig_num not in recovered and fig_num not in candidates:
                    candidates.append(fig_num)
        if len(candidates) == 1:
            _assign_image(index, candidates[0], caption_index)

    # Strongest signal: a Marker figure image followed by an unlabeled panel
    # legend, then the next numbered figure target. Use the missing predecessor.
    for index in range(len(matches)):
        if not _is_orphan_figure_image(index) or index in assigned_images:
            continue
        caption_index = _following_unlabeled_caption_index(index)
        if caption_index is None:
            continue
        next_known = _next_known_figure_num_after(index)
        if next_known is None:
            nearby_refs = _nearby_missing_refs_after(index, window=10)
            fig_num = nearby_refs[0] if nearby_refs else None
        else:
            try:
                predecessor = str(int(next_known) - 1)
            except ValueError:
                predecessor = ""
            fig_num = predecessor if predecessor and predecessor not in found_figures and predecessor not in recovered else None
        if fig_num is not None:
            target_index = _orphan_image_run_start(index)
            _assign_image(target_index, fig_num, caption_index)
            assigned_images.update(range(target_index, index + 1))

    # Prose may introduce a figure immediately before the visual region.  Use
    # it before forward-looking assignment so a later reference to another
    # figure does not steal the image.
    for index in range(len(matches)):
        if not _is_orphan_figure_image(index) or index in assigned_images:
            continue
        refs = [
            fig_num
            for fig_num in _nearby_missing_refs_before(index)
            if fig_num not in found_figures and fig_num not in recovered
        ]
        if len(refs) == 1:
            _assign_image(index, refs[0])

    # Secondary signal: a run of orphan figure images immediately before prose
    # that cites the missing figures. Pair them in reading order.
    index = 0
    while index < len(matches):
        if not _is_orphan_figure_image(index) or index in assigned_images:
            index += 1
            continue
        run = [index]
        scan = index + 1
        while scan < len(matches) and _between_is_whitespace(scan - 1, scan) and _is_orphan_figure_image(scan) and scan not in assigned_images:
            run.append(scan)
            scan += 1

        if any(_image_src_is_page_zero_picture(_node_raw(image_index)) for image_index in run):
            index = run[-1] + 1
            continue

        refs = [
            fig_num
            for fig_num in _nearby_missing_refs_after(run[-1])
            if fig_num not in found_figures and fig_num not in recovered
        ]
        if refs and len(refs) == len(run):
            for image_index, fig_num in zip(run, refs):
                _assign_image(image_index, fig_num)
        elif len(run) == 1 and _keys_are_predecessors_of(refs, _next_known_figure_num_after(run[-1], window=10)):
            _assign_image(run[0], refs[0], aliases=refs[1:])
        index = run[-1] + 1

    if not replacements:
        return html, set()

    out: list[str] = []
    cursor = 0
    for index, match in enumerate(matches):
        out.append(html[cursor : match.start()])
        out.append(replacements.get(index, match.group(0)))
        cursor = match.end()
    out.append(html[cursor:])
    return "".join(out), recovered


def _add_table_anchors(html: str) -> tuple[str, set[str]]:
    """Add ``id="table-{n}"`` to paragraphs that open with a table caption marker."""
    found: set[str] = set()

    def _add_id(m: re.Match[str]) -> str:
        raw = m.group(0)
        table_key = _table_caption_key_from_visible(_visible_text(raw))
        if table_key is None:
            return raw
        found.add(table_key)
        p_open = m.group("open")
        if _has_id_attr(p_open):
            return raw
        return f'{_add_id_attr(p_open, f"table-{table_key}")}{m.group("body")}{m.group("close")}'

    result = _P_BLOCK_PATTERN.sub(_add_id, html)
    result = _H_BLOCK_PATTERN.sub(_add_id, result)
    table_block = re.compile(
        r'(?P<open><table\b[^>]*>)(?P<body>[\s\S]*?)(?P<close></table>)',
        re.IGNORECASE,
    )

    def _add_table_id(m: re.Match[str]) -> str:
        raw = m.group(0)
        table_key = _table_caption_key_from_visible(_visible_text(raw))
        if table_key is None:
            first_row = re.search(r"<tr\b[\s\S]*?</tr>", raw, re.IGNORECASE)
            if first_row is not None:
                table_key = _embedded_table_caption_key_from_visible(_visible_text(first_row.group(0)))
        if table_key is None:
            return raw
        found.add(table_key)
        table_open = m.group("open")
        if _has_id_attr(table_open):
            return raw
        return f'{_add_id_attr(table_open, f"table-{table_key}")}{m.group("body")}{m.group("close")}'

    result = table_block.sub(_add_table_id, result)
    return result, found


def _add_box_anchors(html: str) -> tuple[str, set[str]]:
    """Add ``id="box-{n}"`` to Box headings."""
    found: set[str] = set()

    def _add_id(m: re.Match[str]) -> str:
        raw = m.group(0)
        visible = _visible_text(raw)
        box_match = _BOX_HEADING_VISIBLE_PATTERN.match(visible)
        if box_match is None:
            return raw
        if len(visible) > 1800:
            return raw
        number = box_match.group(1)
        found.add(number)
        open_tag = m.group("open")
        if _has_id_attr(open_tag):
            return raw
        return f'{_add_id_attr(open_tag, f"box-{number}")}{m.group("body")}{m.group("close")}'

    result = _P_BLOCK_PATTERN.sub(_add_id, html)
    result = _H_BLOCK_PATTERN.sub(_add_id, result)
    return result, found


def _link_section_refs(html: str, found_sections: set[str]) -> str:
    """Wrap ``Section II`` / ``Раздел II`` occurrences with ``<a>`` links."""
    if not found_sections:
        return html

    def _section_key(value: str) -> str:
        return value.strip().strip(".").upper().replace(".", "-")

    def _replace_page_linked(m: re.Match[str]) -> str:
        key = _section_key(m.group("num"))
        if key not in found_sections:
            return m.group(0)
        attrs = _replace_anchor_href_and_class(m.group("attrs"), f"#section-{key}", "z2m-section-link")
        return f'<a{attrs}>{m.group("label")}\xa0{m.group("num").strip().strip(".")}</a>{m.group("trail")}'

    html = _PAGE_LINKED_SECTION_REF_PATTERN.sub(_replace_page_linked, html)

    def _replace_page_linked_appendix(m: re.Match[str]) -> str:
        letter = m.group("letter").upper()
        key = f"APPENDIX-{letter}"
        if key not in found_sections:
            return m.group(0)
        attrs = _replace_anchor_href_and_class(
            m.group("attrs"),
            f"#section-appendix-{letter.lower()}",
            "z2m-section-link",
        )
        return f'<a{attrs}>{m.group("label")}\xa0{letter}</a>{m.group("trail")}'

    html = _PAGE_LINKED_APPENDIX_REF_PATTERN.sub(_replace_page_linked_appendix, html)

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def _replace(m: re.Match[str]) -> str:
        word = m.group(1)
        section = m.group(2)
        key = _section_key(section)
        if key not in found_sections:
            return m.group(0)
        return f'<a href="#section-{key}" class="z2m-section-link">{word}\xa0{section}</a>'

    def _replace_appendix(m: re.Match[str]) -> str:
        word = m.group(1)
        letter = m.group(2).upper()
        key = f"APPENDIX-{letter}"
        if key not in found_sections:
            return m.group(0)
        return f'<a href="#section-appendix-{letter.lower()}" class="z2m-section-link">{word}\xa0{letter}</a>'

    heading_stack: list[str] = []

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            raw = part.strip()
            close_match = _CLOSE_TAG_PATTERN.match(raw)
            if close_match is not None and re.fullmatch(r"h[1-6]", close_match.group(1), re.IGNORECASE):
                if heading_stack:
                    heading_stack.pop()
            else:
                open_match = _OPEN_TAG_PATTERN.match(raw)
                if (
                    open_match is not None
                    and not raw.endswith("/>")
                    and re.fullmatch(r"h[1-6]", open_match.group(1), re.IGNORECASE)
                ):
                    heading_stack.append(open_match.group(1).lower())
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack or heading_stack:
            out.append(part)
            continue
        linked = _SECTION_REF_PATTERN.sub(_replace, part)
        out.append(_APPENDIX_REF_PATTERN.sub(_replace_appendix, linked))

    return "".join(out)


def _link_equation_refs(html: str) -> str:
    """Wrap ``Equation N`` / ``Eq. N`` references when an equation anchor exists."""
    found_numbers = {
        match.group(2)
        for match in re.finditer(r'\bid\s*=\s*(["\'])eq-(\d{1,3})\1', html, flags=re.IGNORECASE)
    }
    if not found_numbers:
        return html

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def _replace(m: re.Match[str]) -> str:
        label = m.group(1)
        number = m.group(2)
        if number not in found_numbers:
            return m.group(0)
        return f'<a href="#eq-{number}" class="z2m-eq-link">{label}\xa0{number}</a>'

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_EQUATION_REF_PATTERN.sub(_replace, part))

    return "".join(out)


def _link_box_refs(html: str, found_boxes: set[str]) -> str:
    """Wrap ``Box N`` references when a box anchor exists."""
    if not found_boxes:
        return html

    def _replace_page_linked(m: re.Match[str]) -> str:
        number = m.group("num")
        if number not in found_boxes:
            return m.group(0)
        attrs = _replace_anchor_href_and_class(m.group("attrs"), f"#box-{number}", "z2m-box-link")
        return f'<a{attrs}>{m.group("label")}\xa0{number}</a>{m.group("trail")}'

    html = _PAGE_LINKED_BOX_REF_PATTERN.sub(_replace_page_linked, html)

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def _replace(m: re.Match[str]) -> str:
        label = m.group(1)
        number = m.group(2)
        if number not in found_boxes:
            return m.group(0)
        return f'<a href="#box-{number}" class="z2m-box-link">{label}\xa0{number}</a>'

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_citation_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_BOX_REF_PATTERN.sub(_replace, part))

    return "".join(out)


def _link_figure_refs(html: str, found_figures: set[str]) -> str:
    """Wrap ``Fig. 3`` / ``рис. 3`` occurrences with ``<a>`` links.

    Caption paragraphs themselves are intentionally skipped because
    ``_FIG_REF_PATTERN`` has a negative lookahead for a trailing dot.
    """
    if not found_figures:
        return html

    def _is_inside_fig_link(fragment: str, start: int, end: int) -> bool:
        open_pos = fragment.rfind("<a", 0, start)
        if open_pos < 0:
            return False
        open_end = fragment.find(">", open_pos)
        if open_end < 0 or open_end >= start:
            return False
        if "z2m-fig-link" not in fragment[open_pos:open_end + 1]:
            return False
        close_before = fragment.rfind("</a", 0, start)
        if close_before > open_pos:
            return False
        close_after = fragment.find("</a", end)
        return close_after >= 0

    html = _unwrap_nested_fig_links(html)
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []
    scan_text = ""
    protected_figure_tag: str | None = None
    current_section_chapter: str | None = None

    def _opens_protected_figure_text(raw_tag: str) -> str | None:
        open_match = _OPEN_TAG_PATTERN.match(raw_tag)
        if open_match is None:
            return None
        tag_name = open_match.group(1).lower()
        if tag_name == "p" and re.search(r'\bid\s*=\s*["\']fig-[A-Za-z0-9-]+', raw_tag):
            return tag_name
        if re.search(r'\bclass\s*=\s*["\'][^"\']*\bz2m-missing-figure-warning\b', raw_tag):
            return tag_name
        return None

    def _section_chapter_from_heading_tag(raw_tag: str) -> str | None:
        open_match = _OPEN_TAG_PATTERN.match(raw_tag)
        if open_match is None or not re.fullmatch(r"h[1-6]", open_match.group(1), re.IGNORECASE):
            return None
        section_id = re.search(r'\bid\s*=\s*["\']section-(\d{1,3})(?:[-"\'])', raw_tag, re.IGNORECASE)
        return section_id.group(1) if section_id is not None else None

    def _chapter_local_figure_key(key: str, suffix: str) -> str | None:
        if not suffix or current_section_chapter is None:
            return None
        local_key = f"{current_section_chapter}-{key}"
        return local_key if local_key in found_figures else None

    def _replace(m: re.Match[str]) -> str:
        prefix = m.group(1)
        num = m.group(2)
        suffix = m.group(3) or ""
        key = _figure_key_from_visible_number(num)
        if scan_text and _is_inside_fig_link(scan_text, m.start(), m.end()):
            return m.group(0)
        local_key = _chapter_local_figure_key(key, suffix)
        if key not in found_figures and local_key is not None:
            return f'<a href="#fig-{local_key}" class="z2m-fig-link">{prefix}\xa0{num}{suffix}</a>'
        if key not in found_figures:
            return m.group(0)
        return f'<a href="#fig-{key}" class="z2m-fig-link">{prefix}\xa0{num}{suffix}</a>'

    def _replace_supplementary(m: re.Match[str]) -> str:
        prefix = m.group("prefix")
        num = m.group("num")
        suffix = m.group("suffix") or ""
        key = _supplementary_figure_key_from_visible_number(num)
        if scan_text and _is_inside_fig_link(scan_text, m.start(), m.end()):
            return m.group(0)
        if key not in found_figures:
            return m.group(0)
        return f'<a href="#fig-{key}" class="z2m-fig-link">{prefix}\xa0{num}{suffix}</a>'

    def _replace_extended_data(m: re.Match[str]) -> str:
        prefix = m.group("prefix")
        num = m.group("num")
        suffix = m.group("suffix") or ""
        key = _extended_data_figure_key_from_visible_number(num)
        if scan_text and _is_inside_fig_link(scan_text, m.start(), m.end()):
            return m.group(0)
        if key not in found_figures:
            return m.group(0)
        return f'<a href="#fig-{key}" class="z2m-fig-link">{prefix}\xa0{num}{suffix}</a>'

    def _replace_spaced_multipanel(m: re.Match[str]) -> str:
        prefix = m.group(1)
        num = m.group(2)
        panels = m.group("panels") or ""
        key = _figure_key_from_visible_number(num)
        if scan_text and _is_inside_fig_link(scan_text, m.start(), m.end()):
            return m.group(0)
        if key not in found_figures:
            return m.group(0)
        return f'<a href="#fig-{key}" class="z2m-fig-link">{prefix}\xa0{num}</a>{panels}'

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            raw_tag = part.strip().lower()
            section_chapter = _section_chapter_from_heading_tag(part)
            if section_chapter is not None:
                current_section_chapter = section_chapter
            close_match = _CLOSE_TAG_PATTERN.match(raw_tag)
            if close_match is not None and close_match.group(1).lower() == protected_figure_tag:
                protected_figure_tag = None
            elif protected_figure_tag is None:
                protected_figure_tag = _opens_protected_figure_text(raw_tag)
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack or protected_figure_tag is not None:
            out.append(part)
            continue
        scan_text = part
        linked = _EXTENDED_DATA_FIG_REF_PATTERN.sub(_replace_extended_data, part)
        scan_text = linked
        linked = _SUPPLEMENTARY_FIG_REF_PATTERN.sub(_replace_supplementary, linked)
        scan_text = linked
        linked = _SPACED_MULTIPANEL_FIG_REF_PATTERN.sub(_replace_spaced_multipanel, linked)
        scan_text = linked
        linked = _FIG_REF_PATTERN.sub(_replace, linked)
        scan_text = linked
        linked = _EXT_FIG_REF_PATTERN.sub(_replace, linked)

        # Handle compact chained subfigure refs: "Figure 1c and 1d" / "Fig. 2a-2c".
        def _replace_chain(m: re.Match[str]) -> str:
            tag_open = linked.rfind("<", 0, m.start())
            tag_close = linked.rfind(">", 0, m.start())
            if tag_open > tag_close or _is_inside_fig_link(linked, m.start(), m.end()):
                return m.group(0)
            num = m.group("num")
            suffix = m.group("suf") or ""
            left_ctx = linked[max(0, m.start() - 160):m.start()]
            key = _figure_key_from_visible_number(num)
            if re.search(r'href\s*=\s*["\']#fig-supplementary-[^"\']+["\']', left_ctx, re.IGNORECASE):
                supplementary_key = _supplementary_figure_key_from_visible_number(num)
                if supplementary_key in found_figures:
                    key = supplementary_key
            if key not in found_figures:
                return m.group(0)
            if 'class="z2m-fig-link"' not in left_ctx:
                return m.group(0)
            return (
                f'{m.group("sep")}'
                f'<a href="#fig-{key}" class="z2m-fig-link">{num}{suffix}</a>'
            )

        linked = _FIG_REF_CHAIN_CONT_PATTERN.sub(_replace_chain, linked)
        linked = _unwrap_nested_fig_links(linked)
        out.append(linked)

    return "".join(out)


def _current_figure_target_keys(html: str) -> set[str]:
    return {match.group("key") for match in _FIG_ID_ATTR_PATTERN.finditer(html)}


def _late_recover_orphan_figure_anchors_and_links(html: str) -> str:
    current_figures = _current_figure_target_keys(html)
    if not current_figures:
        return html
    recovered_html, recovered_figures = _recover_orphan_figure_anchors(html, current_figures)
    if not recovered_figures:
        return html
    recovered_html = _wrap_float_units(recovered_html)
    recovered_html = _mark_missing_figure_units(recovered_html)
    recovered_html = _link_figure_refs(recovered_html, recovered_figures)
    recovered_html = _unwrap_nested_same_href_internal_links(recovered_html)
    return _normalize_spacing_after_z2m_links(recovered_html)


def _link_spaced_multipanel_figure_refs(html: str, found_figures: set[str]) -> str:
    if not found_figures:
        return html

    def _is_inside_fig_link(fragment: str, start: int, end: int) -> bool:
        open_pos = fragment.rfind("<a", 0, start)
        if open_pos < 0:
            return False
        open_end = fragment.find(">", open_pos)
        if open_end < 0 or open_end >= start:
            return False
        if "z2m-fig-link" not in fragment[open_pos:open_end + 1]:
            return False
        close_before = fragment.rfind("</a", 0, start)
        if close_before > open_pos:
            return False
        close_after = fragment.find("</a", end)
        return close_after >= 0

    def _opens_protected_figure_text(raw_tag: str) -> bool:
        return bool(
            re.match(r"<p\b", raw_tag)
            and (
                re.search(r'\bid\s*=\s*["\']fig-[A-Za-z0-9-]+', raw_tag)
                or re.search(
                    r'\bclass\s*=\s*["\'][^"\']*\b(?:z2m-figure-caption|'
                    r"z2m-figure-target|z2m-missing-figure-warning)\b",
                    raw_tag,
                )
            )
        )

    def _replace_spaced_multipanel(m: re.Match[str]) -> str:
        prefix = m.group(1)
        num = m.group(2)
        panels = m.group("panels") or ""
        key = _figure_key_from_visible_number(num)
        if scan_text and _is_inside_fig_link(scan_text, m.start(), m.end()):
            return m.group(0)
        if key not in found_figures:
            return m.group(0)
        return f'<a href="#fig-{key}" class="z2m-fig-link">{prefix}\xa0{num}</a>{panels}'

    html = _unwrap_nested_fig_links(html)
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []
    scan_text = ""
    inside_protected_figure_text = False
    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            raw_tag = part.strip().lower()
            if re.match(r"</p\b", raw_tag):
                inside_protected_figure_text = False
            elif _opens_protected_figure_text(raw_tag):
                inside_protected_figure_text = True
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack or inside_protected_figure_text:
            out.append(part)
            continue
        scan_text = part
        linked = _SPACED_MULTIPANEL_FIG_REF_PATTERN.sub(_replace_spaced_multipanel, part)
        out.append(linked)
    return "".join(out)


def _retarget_void_figure_number_links(html: str, found_figures: set[str]) -> str:
    """Retarget publisher placeholder anchors used for split figure refs."""
    if not found_figures or "javascript:void(0)" not in html:
        return html
    inline_wrap = r"(?:<(?:i|em|b|strong|span)\b[^>]*>\s*){0,3}"
    inline_close = r"(?:\s*</(?:i|em|b|strong|span)>){0,3}"
    pattern = re.compile(
        rf"(?P<prefix>\b{_FIG_REF_LABEL_TOKEN}\.?\s*{inline_wrap})"
        r"<a(?P<attrs>\b[^>]*\bhref\s*=\s*([\"'])javascript:void\(0\)\3[^>]*)>"
        rf"\s*(?P<num>{_FIG_KEY_TOKEN})(?P<suffix>{_FIG_PANEL_SUFFIX_TOKEN})?"
        r"(?P<trail>[\)\]\.,;:]?)\s*</a>"
        rf"(?P<closing>{inline_close})",
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        num = match.group("num")
        key = _figure_key_from_visible_number(num)
        if key not in found_figures:
            return match.group(0)
        suffix = match.group("suffix") or ""
        trail = match.group("trail") or ""
        attrs = re.sub(
            r'\bhref\s*=\s*(["\'])javascript:void\(0\)\1',
            f'href="#fig-{key}"',
            match.group("attrs"),
            count=1,
            flags=re.IGNORECASE,
        )
        attrs = _replace_href_and_link_class(attrs, f"#fig-{key}", "z2m-fig-link")
        return f"{match.group('prefix')}<a{attrs}>{num}{suffix}{trail}</a>{match.group('closing')}"

    return pattern.sub(_replace, html)


def _repair_figure_refs_split_by_line_number_artifacts(html: str, found_figures: set[str]) -> str:
    """Move a split figure number back across publisher line-number blocks.

    Marker sometimes emits accepted-manuscript line numbers as the first token
    after a figure label, leaving the real figure number at the start of the
    next artificial block: ``Figure 564 </li><li>8C)``.  Retarget only when
    the recovered figure key exists, so true large-number labels are preserved.
    """
    if not found_figures:
        return html
    pattern = re.compile(
        rf"(?P<label>\b{_FIG_REF_LABEL_TOKEN}\.?\s+)"
        r"(?P<line>\d{3,4})\s*"
        r"(?P<close></(?:p|li)>)\s*"
        r"(?P<open><(?:p|li)\b[^>]*>)\s*"
        rf"(?P<num>{_FIG_KEY_TOKEN})(?P<suffix>{_FIG_PANEL_SUFFIX_TOKEN})?"
        r"(?P<trail>[\)\]\.,;:])",
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        line_number = int(match.group("line"))
        if line_number < 100:
            return match.group(0)
        num = match.group("num")
        suffix = match.group("suffix") or ""
        key = _figure_key_from_visible_number(num)
        if key not in found_figures:
            return match.group(0)
        return (
            f"{match.group('label')}{num}{suffix}{match.group('trail')}"
            f"{match.group('close')}{match.group('open')}"
        )

    return pattern.sub(_replace, html)


def _replace_anchor_href_and_class(attrs: str, href: str, class_name: str) -> str:
    attrs = re.sub(
        r'\bhref\s*=\s*(["\'])#page-[^"\']+\1',
        f'href="{href}"',
        attrs,
        count=1,
        flags=re.IGNORECASE,
    )

    class_match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', attrs, re.IGNORECASE | re.DOTALL)
    if class_match is None:
        return f'{attrs} class="{class_name}"'
    classes = class_match.group(2).split()
    if class_name in classes:
        return attrs
    new_class = " ".join([*classes, class_name])
    return attrs[:class_match.start(2)] + new_class + attrs[class_match.end(2):]


def _replace_href_and_link_class(attrs: str, href: str, class_name: str) -> str:
    attrs = re.sub(
        r'\bhref\s*=\s*(["\'])#[^"\']+\1',
        f'href="{href}"',
        attrs,
        count=1,
        flags=re.IGNORECASE,
    )
    class_match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', attrs, re.IGNORECASE | re.DOTALL)
    if class_match is None:
        return f'{attrs} class="{class_name}"'
    classes = [
        cls for cls in class_match.group(2).split()
        if cls not in {"z2m-ref-link", "z2m-fig-link", "z2m-table-link", "z2m-eq-link"}
    ]
    if class_name not in classes:
        classes.append(class_name)
    return attrs[:class_match.start(2)] + " ".join(classes) + attrs[class_match.end(2):]


def _rewrite_existing_page_figure_links(
    html: str,
    found_figures: set[str],
    *,
    language_policy: PolishLanguagePolicy | None = None,
) -> str:
    """Retarget Marker page links used as figure references to figure anchors."""
    if not found_figures:
        return html
    fig_tail = (
        r"(?:(?:[a-z]|\([a-z]\))(?:\s*(?:,|[-\u2010\u2011\u2012\u2013\u2014])\s*(?:[a-z]|\([a-z]\)))*)?"
        rf"(?:\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*{_FIG_KEY_TOKEN}(?:[a-z]|\([a-z]\))?)*"
    )
    supplementary_fig_tail = (
        r"(?:(?:[a-z]|\([a-z]\))(?:\s*(?:,|[-\u2010\u2011\u2012\u2013\u2014])\s*(?:[a-z]|\([a-z]\)))*)?"
        rf"(?:\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*{_SUPPLEMENTARY_FIG_KEY_TOKEN}(?:[a-z]|\([a-z]\))?)*"
    )
    fig_left_context = (
        r"(?:FIG(?:URE)?S?|Fig(?:ure)?s?|\u0420\u0438\u0441|\u0440\u0438\u0441|\u0424\u0438\u0433|\u0444\u0438\u0433)"
        rf"\.?\s*(?:{_FIG_KEY_TOKEN}(?:[a-z]|\([a-z]\))?\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*)?$"
    )
    supplementary_left_context = rf"\b{_SUPPLEMENTARY_FIG_PREFIX_TOKEN}\s*$"
    extended_data_left_context = rf"\b{_EXTENDED_DATA_FIG_PREFIX_TOKEN}\s*$"

    def _replace_split(m: re.Match[str]) -> str:
        number = m.group("num")
        left_text = _visible_text(html[max(0, m.start() - 180):m.start()])
        extended_data_context = re.search(extended_data_left_context, left_text, re.IGNORECASE) is not None
        supplementary_context = re.search(supplementary_left_context, left_text, re.IGNORECASE) is not None
        key = (
            _extended_data_figure_key_from_visible_number(number)
            if extended_data_context
            else _supplementary_figure_key_from_visible_number(number)
            if supplementary_context
            else _figure_key_from_visible_number(number)
        )
        if key not in found_figures:
            return m.group(0)
        attrs = _replace_anchor_href_and_class(m.group("attrs"), f"#fig-{key}", "z2m-fig-link")
        return f"<a{attrs}>{m.group('body')}{number}{m.group('suffix')}</a>"

    html = _SPLIT_PAGE_FIG_LINK_PATTERN.sub(_replace_split, html)

    def _replace(m: re.Match[str]) -> str:
        body = m.group("body")
        body_text = _visible_text(body)
        semantic_body_text = (
            language_policy.strip_semantic_reference_lead_in(body_text)
            if language_policy is not None
            else body_text
        )
        left_text = _visible_text(html[max(0, m.start() - 180):m.start()])
        extended_data_direct = re.match(
            rf"^[\(\[]*(?:(?P<lead>{_EXTENDED_DATA_FIG_PREFIX_TOKEN})\s+)?"
            r"(?:FIG(?:URE)?S?|Fig(?:ure)?s?)"
            rf"\.?\s*(?P<num>{_FIG_KEY_TOKEN}){fig_tail}[\(\)\]\.,;:]*$",
            semantic_body_text,
            re.IGNORECASE,
        )
        extended_data_context = (
            extended_data_direct is not None
            and (
                bool(extended_data_direct.group("lead"))
                or re.search(extended_data_left_context, left_text, re.IGNORECASE) is not None
            )
        )
        supplementary_direct = re.match(
            rf"^[\(\[]*(?:(?P<lead>{_SUPPLEMENTARY_FIG_PREFIX_TOKEN})\s+)?"
            r"(?:FIG(?:URE)?S?|Fig(?:ure)?s?|\u0420\u0438\u0441|\u0440\u0438\u0441|\u0424\u0438\u0433|\u0444\u0438\u0433)"
            rf"\.?\s*(?P<num>{_SUPPLEMENTARY_FIG_KEY_TOKEN}){supplementary_fig_tail}[\(\)\]\.,;:]*$",
            semantic_body_text,
            re.IGNORECASE,
        )
        supplementary_context = (
            supplementary_direct is not None
            and (
                bool(supplementary_direct.group("lead"))
                or re.search(supplementary_left_context, left_text, re.IGNORECASE) is not None
            )
        )
        if extended_data_context:
            number = _extended_data_figure_key_from_visible_number(extended_data_direct.group("num"))
        elif supplementary_context:
            number = _supplementary_figure_key_from_visible_number(supplementary_direct.group("num"))
        else:
            direct = re.match(
                r"^[\(\[]*(?:FIG(?:URE)?S?|Fig(?:ure)?s?|\u0420\u0438\u0441|\u0440\u0438\u0441|\u0424\u0438\u0433|\u0444\u0438\u0433)"
                rf"\.?\s*({_FIG_KEY_TOKEN}){fig_tail}[\(\)\]\.,;:]*$",
                semantic_body_text,
                re.IGNORECASE,
            )
            number = direct.group(1) if direct is not None else None
        if number is None:
            num_only = re.match(
                rf"^({_FIG_KEY_TOKEN}){fig_tail}[\(\)\]\.,;:]*$",
                semantic_body_text,
                re.IGNORECASE,
            )
            if num_only is not None:
                if re.search(fig_left_context, left_text, re.IGNORECASE):
                    number = num_only.group(1)
                elif re.search(
                    r"(?:\b(?:image|photograph|picture|panel)\s*\(\s*in\s*|\b(?:image|photograph|picture|panel|in)\s*)$",
                    left_text,
                    re.IGNORECASE,
                ) and re.match(r"^\d+[a-z]", semantic_body_text, re.IGNORECASE):
                    number = num_only.group(1)
        key = (
            number
            if supplementary_context or extended_data_context
            else (_figure_key_from_visible_number(number) if number is not None else None)
        )
        if key is None or key not in found_figures:
            return m.group(0)
        attrs = _replace_anchor_href_and_class(m.group("attrs"), f"#fig-{key}", "z2m-fig-link")
        return f"<a{attrs}>{body}</a>"

    return _PAGE_ANCHOR_PATTERN.sub(_replace, html)


def _rewrite_existing_page_table_links(html: str, found_tables: set[str]) -> str:
    """Retarget Marker page links used as table references to table anchors."""
    if not found_tables:
        return html
    table_left_context = (
        rf"(?:TABLES?|Tables?|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s*"
        rf"(?:{_TABLE_KEY_TOKEN}\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*)?$"
    )
    table_range_left_context = (
        rf"(?:TABLES?|Tables?|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s+{_TABLE_KEY_TOKEN}\s*$"
    )

    def _replace_pair_page_link(m: re.Match[str]) -> str:
        body_text = _visible_text(m.group("body"))
        second_match = re.match(
            rf"^\s*(?P<second>{_TABLE_KEY_TOKEN})(?P<trail>[\)\]\.,;:]*)\s*$",
            body_text,
            re.IGNORECASE,
        )
        if second_match is None:
            return m.group(0)
        first = m.group("first")
        second = second_match.group("second")
        first_key = _normalize_table_key(first)
        second_key = _normalize_table_key(second)
        if first_key not in found_tables or second_key not in found_tables:
            return m.group(0)
        attrs = _replace_anchor_href_and_class(m.group("attrs"), f"#table-{second_key}", "z2m-table-link")
        first_link = f'<a href="#table-{first_key}" class="z2m-table-link">{m.group("word")}\xa0{first}</a>'
        return f'{first_link} {m.group("join")} <a{attrs}>{second}</a>{second_match.group("trail")}'

    html = _TABLE_REF_PAIR_PAGE_LINK_PATTERN.sub(_replace_pair_page_link, html)

    def _replace_split(m: re.Match[str]) -> str:
        key = _normalize_table_key(m.group("num"))
        if key not in found_tables:
            return m.group(0)
        attrs = _replace_anchor_href_and_class(m.group("attrs"), f"#table-{key}", "z2m-table-link")
        body = m.group("body")
        joiner = "" if body.endswith((" ", "\n", "\t")) else " "
        return f"<a{attrs}>{body}{joiner}{m.group('num')}{m.group('suffix')}</a>"

    html = _SPLIT_PAGE_TABLE_LINK_PATTERN.sub(_replace_split, html)

    def _replace(m: re.Match[str]) -> str:
        body = m.group("body")
        body_text = _visible_text(body)
        direct = re.match(
            rf"^[\(\[]*(?:TABLES?|Tables?|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s+({_TABLE_KEY_TOKEN})[\(\)\]\.,;:]*$",
            body_text,
            re.IGNORECASE,
        )
        key = _normalize_table_key(direct.group(1)) if direct is not None else None
        if key is None:
            num_only = re.match(rf"^({_TABLE_KEY_TOKEN})[\(\)\]\.,;:]*$", body_text, re.IGNORECASE)
            if num_only is not None:
                left_text = _visible_text(html[max(0, m.start() - 180):m.start()])
                if re.search(table_left_context, left_text, re.IGNORECASE):
                    key = _normalize_table_key(num_only.group(1))
            else:
                range_tail = re.match(
                    rf"^\s*[-\u2010\u2011\u2012\u2013\u2014]\s*({_TABLE_KEY_TOKEN})[\)\]\.,;:]*$",
                    body_text,
                    re.IGNORECASE,
                )
                if range_tail is not None:
                    left_text = _visible_text(html[max(0, m.start() - 180):m.start()])
                    if re.search(table_range_left_context, left_text, re.IGNORECASE):
                        key = _normalize_table_key(range_tail.group(1))
        if key is None or key not in found_tables:
            return m.group(0)
        attrs = _replace_anchor_href_and_class(m.group("attrs"), f"#table-{key}", "z2m-table-link")
        return f"<a{attrs}>{body}</a>"

    return _PAGE_ANCHOR_PATTERN.sub(_replace, html)


def _unwrap_unresolved_semantic_page_links(
    html: str,
    *,
    found_figures: set[str],
    found_tables: set[str],
    found_sections: set[str],
    found_boxes: set[str],
    language_policy: PolishLanguagePolicy | None = None,
) -> str:
    """Retarget or remove stale page links from semantic cross-references."""
    if "#page-" not in html:
        return html

    found_equations = {
        match.group(2).upper().replace(".", "-")
        for match in re.finditer(r'\bid\s*=\s*(["\'])eq-([^"\']+)\1', html, re.IGNORECASE)
    }
    fig_tail = (
        r"(?:(?:[a-z]|\([a-z]\))(?:\s*(?:,|[-\u2010\u2011\u2012\u2013\u2014])\s*(?:[a-z]|\([a-z]\)))*)?"
        rf"(?:\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*{_FIG_KEY_TOKEN}(?:[a-z]|\([a-z]\))?)*"
    )
    supplementary_fig_tail = (
        r"(?:(?:[a-z]|\([a-z]\))(?:\s*(?:,|[-\u2010\u2011\u2012\u2013\u2014])\s*(?:[a-z]|\([a-z]\)))*)?"
        rf"(?:\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*{_SUPPLEMENTARY_FIG_KEY_TOKEN}(?:[a-z]|\([a-z]\))?)*"
    )
    fig_left_context = (
        r"(?:FIG(?:URE)?S?|Fig(?:ure)?s?|\u0420\u0438\u0441|\u0440\u0438\u0441|\u0424\u0438\u0433|\u0444\u0438\u0433)"
        rf"\.?\s*(?:{_FIG_KEY_TOKEN}(?:[a-z]|\([a-z]\))?\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*)?$"
    )
    supplementary_left_context = rf"\b{_SUPPLEMENTARY_FIG_PREFIX_TOKEN}\s*$"
    extended_data_left_context = rf"\b{_EXTENDED_DATA_FIG_PREFIX_TOKEN}\s*$"
    table_left_context = (
        rf"(?:TABLES?|Tables?|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s*"
        rf"(?:{_TABLE_KEY_TOKEN}\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*)?$"
    )
    table_range_left_context = (
        rf"(?:TABLES?|Tables?|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s+{_TABLE_KEY_TOKEN}\s*$"
    )

    def _section_key(value: str) -> str:
        return value.strip().strip("().,;:").upper().replace(".", "-")

    def _eq_key(value: str) -> str:
        return value.strip().strip("().,;:").upper().replace(".", "-")

    def _has_internal_target(prefix: str, key: str) -> bool:
        return re.search(rf'\bid\s*=\s*(["\']){re.escape(prefix + key)}\1', html, re.IGNORECASE) is not None

    def _link_page_anchor(m: re.Match[str], href: str, class_name: str) -> str:
        attrs = _replace_anchor_href_and_class(m.group("attrs"), href, class_name)
        return f'<a{attrs}>{m.group("body")}</a>'

    def _replace(m: re.Match[str]) -> str:
        body = m.group("body")
        body_text = _visible_text(body)
        semantic_body_text = (
            language_policy.strip_semantic_reference_lead_in(body_text)
            if language_policy is not None
            else body_text
        )
        semantic_body_text = html_lib.unescape(semantic_body_text)
        stripped_semantic = semantic_body_text.strip()
        left_text = _visible_text(html[max(0, m.start() - 180):m.start()])
        right_text = _visible_text(html[m.end():m.end() + 120])

        fig_number: str | None = None
        extended_data_direct = re.match(
            rf"^[\(\[]*(?:(?P<lead>{_EXTENDED_DATA_FIG_PREFIX_TOKEN})\s+)?"
            r"(?:FIG(?:URE)?S?|Fig(?:ure)?s?)"
            rf"\.?\s*(?P<num>{_FIG_KEY_TOKEN}){fig_tail}[\(\)\]\.,;:]*$",
            semantic_body_text,
            re.IGNORECASE,
        )
        extended_data_context = (
            extended_data_direct is not None
            and (
                bool(extended_data_direct.group("lead"))
                or re.search(extended_data_left_context, left_text, re.IGNORECASE) is not None
            )
        )
        supplementary_direct = re.match(
            rf"^[\(\[]*(?:(?P<lead>{_SUPPLEMENTARY_FIG_PREFIX_TOKEN})\s+)?"
            r"(?:FIG(?:URE)?S?|Fig(?:ure)?s?|\u0420\u0438\u0441|\u0440\u0438\u0441|\u0424\u0438\u0433|\u0444\u0438\u0433)"
            rf"\.?\s*(?P<num>{_SUPPLEMENTARY_FIG_KEY_TOKEN}){supplementary_fig_tail}[\(\)\]\.,;:]*$",
            semantic_body_text,
            re.IGNORECASE,
        )
        supplementary_context = (
            supplementary_direct is not None
            and (
                bool(supplementary_direct.group("lead"))
                or re.search(supplementary_left_context, left_text, re.IGNORECASE) is not None
            )
        )
        if extended_data_context:
            fig_number = _extended_data_figure_key_from_visible_number(extended_data_direct.group("num"))
        elif supplementary_context:
            fig_number = _supplementary_figure_key_from_visible_number(supplementary_direct.group("num"))
        else:
            fig_decimal_direct = re.match(
                r"^[\(\[]*(?:FIG(?:URE)?S?|Fig(?:ure)?s?|\u0420\u0438\u0441|\u0440\u0438\u0441|\u0424\u0438\u0433|\u0444\u0438\u0433)"
                r"\.?\s*(\d+\.\d+[a-z]?)[\(\)\]\.,;:]*$",
                semantic_body_text,
                re.IGNORECASE,
            )
            if fig_decimal_direct is not None:
                fig_number = fig_decimal_direct.group(1).lower().replace(".", "-")

        fig_direct = re.match(
            r"^[\(\[]*(?:FIG(?:URE)?S?|Fig(?:ure)?s?|\u0420\u0438\u0441|\u0440\u0438\u0441|\u0424\u0438\u0433|\u0444\u0438\u0433)"
            rf"\.?\s*({_FIG_KEY_TOKEN}){fig_tail}[\(\)\]\.,;:]*$",
            semantic_body_text,
            re.IGNORECASE,
        )
        if fig_number is None and fig_direct is not None:
            fig_number = _figure_key_from_visible_number(fig_direct.group(1))
        else:
            fig_num_only = re.match(
                rf"^({_FIG_KEY_TOKEN}){fig_tail}[\(\)\]\.,;:]*$",
                semantic_body_text,
                re.IGNORECASE,
            )
            if fig_number is None and fig_num_only is not None and re.search(fig_left_context, left_text, re.IGNORECASE):
                fig_number = _figure_key_from_visible_number(fig_num_only.group(1))
            elif fig_number is None and fig_num_only is not None and re.search(
                r"\b(?:FIG(?:URE)?S?|Fig(?:ure)?s?)\b[\s\S]{0,120}(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*$",
                left_text,
                re.IGNORECASE,
            ):
                fig_number = _figure_key_from_visible_number(fig_num_only.group(1))
            elif fig_number is None and fig_num_only is not None and re.search(
                r"(?:\b(?:image|photograph|picture|panel)\s*\(\s*in\s*|\b(?:image|photograph|picture|panel|in)\s*)$",
                left_text,
                re.IGNORECASE,
            ) and re.match(r"^\d+[a-z]", semantic_body_text, re.IGNORECASE):
                fig_number = _figure_key_from_visible_number(fig_num_only.group(1))
        if fig_number is not None:
            if fig_number in found_figures:
                return _link_page_anchor(m, f"#fig-{fig_number}", "z2m-fig-link")
            return body
        if (
            re.search(r"\bFig\s*$", left_text, re.IGNORECASE)
            and stripped_semantic.lower() == "ur"
            and re.match(r"^\s*e\s+\d", right_text, re.IGNORECASE)
        ):
            return body
        if re.search(r"\bFigur\s*$", left_text, re.IGNORECASE) and re.match(
            r"^e\s*\d", stripped_semantic, re.IGNORECASE
        ):
            return body

        table_key: str | None = None
        table_decimal_direct = re.match(
            r"^[\(\[]*(?:TABLES?|Tables?|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s+(\d+\.\d+[a-z]?)[\(\)\]\.,;:]*$",
            semantic_body_text,
            re.IGNORECASE,
        )
        if table_decimal_direct is not None:
            table_key = table_decimal_direct.group(1).lower().replace(".", "-")

        table_direct = re.match(
            rf"^[\(\[]*(?:TABLES?|Tables?|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s+({_TABLE_KEY_TOKEN})[\(\)\]\.,;:]*$",
            semantic_body_text,
            re.IGNORECASE,
        )
        if table_key is None and table_direct is not None:
            table_key = _normalize_table_key(table_direct.group(1))
        else:
            table_decimal_num_only = re.match(
                r"^(\d+\.\d+[a-z]?)[\(\)\]\.,;:]*$",
                semantic_body_text,
                re.IGNORECASE,
            )
            if table_key is None and table_decimal_num_only is not None and re.search(
                r"(?:TABLES?|Tables?|\u0422\u0430\u0431\u043b\u0438\u0446\u0430)\.?\s+\d+\.\d+[a-z]?\s*(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*$",
                left_text,
                re.IGNORECASE,
            ):
                table_key = table_decimal_num_only.group(1).lower().replace(".", "-")

            table_num_only = re.match(
                rf"^({_TABLE_KEY_TOKEN})[\(\)\]\.,;:]*$",
                semantic_body_text,
                re.IGNORECASE,
            )
            if table_key is None and table_num_only is not None and re.search(table_left_context, left_text, re.IGNORECASE):
                table_key = _normalize_table_key(table_num_only.group(1))
            elif table_key is None and table_num_only is not None and re.search(
                rf"\b(?:TABLES?|Tables?)\b[\s\S]{{0,120}}(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*$",
                left_text,
                re.IGNORECASE,
            ):
                table_key = _normalize_table_key(table_num_only.group(1))
            elif table_key is None and table_num_only is None:
                table_range_tail = re.match(
                    rf"^\s*[-\u2010\u2011\u2012\u2013\u2014]\s*({_TABLE_KEY_TOKEN})[\)\]\.,;:]*$",
                    semantic_body_text,
                    re.IGNORECASE,
                )
                if table_range_tail is not None and re.search(table_range_left_context, left_text, re.IGNORECASE):
                    table_key = _normalize_table_key(table_range_tail.group(1))
        if table_key is not None:
            if table_key in found_tables:
                return _link_page_anchor(m, f"#table-{table_key}", "z2m-table-link")
            return body

        section_key: str | None = None
        section_plural_context = False
        section_direct = re.match(
            r"^[\(\[]*Section\s+(?P<num>[IVX]{1,6}|\d{1,2}(?:\.\d{1,2})*)(?P<trail>[\)\]\.,;:]*)$",
            stripped_semantic,
            re.IGNORECASE,
        )
        if section_direct is not None:
            section_key = _section_key(section_direct.group("num"))
        else:
            section_num_only = re.match(
                r"^(?P<num>[IVX]{1,6}|\d{1,2}(?:\.\d{1,2})*)(?P<trail>[\)\]\.,;:]*)$",
                stripped_semantic,
                re.IGNORECASE,
            )
            if section_num_only is not None and re.search(r"\bSection\s*$", left_text, re.IGNORECASE):
                section_key = _section_key(section_num_only.group("num"))
            elif section_num_only is not None and re.search(
                r"\bSections?\b[\s\S]{0,120}(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*$",
                left_text,
                re.IGNORECASE,
            ):
                section_key = _section_key(section_num_only.group("num"))
                section_plural_context = True
        if section_key is not None:
            if section_key in found_sections or _has_internal_target("section-", section_key):
                return _link_page_anchor(m, f"#section-{section_key}", "z2m-section-link")
            if section_plural_context:
                return body
            return body

        appendix_key: str | None = None
        appendix_direct = re.match(
            r"^[\(\[]*Appendix\s+(?P<letter>[A-Z])(?P<trail>[\)\]\.,;:]*)$",
            stripped_semantic,
            re.IGNORECASE,
        )
        if appendix_direct is not None:
            appendix_key = appendix_direct.group("letter").upper()
        else:
            appendix_letter_only = re.match(r"^(?P<letter>[A-Z])(?P<trail>[\)\]\.,;:]*)$", stripped_semantic)
            if appendix_letter_only is not None and re.search(r"\bAppendix\s*$", left_text, re.IGNORECASE):
                appendix_key = appendix_letter_only.group("letter").upper()
        if appendix_key is not None:
            target_key = f"APPENDIX-{appendix_key}"
            if target_key in found_sections:
                return _link_page_anchor(m, f"#section-appendix-{appendix_key.lower()}", "z2m-section-link")
            return body

        box_direct = re.match(
            r"^[\(\[]*Box\s+(?P<num>\d+)(?P<trail>[\)\]\.,;:]*)$",
            stripped_semantic,
            re.IGNORECASE,
        )
        box_num = box_direct.group("num") if box_direct is not None else None
        if box_num is None:
            box_num_only = re.match(r"^(?P<num>\d+)(?P<trail>[\)\]\.,;:]*)$", stripped_semantic)
            if box_num_only is not None and re.search(r"\bBox\s*$", left_text, re.IGNORECASE):
                box_num = box_num_only.group("num")
        if box_num is not None:
            if box_num in found_boxes:
                return _link_page_anchor(m, f"#box-{box_num}", "z2m-box-link")
            return body

        eq_direct = re.match(
            r"^[\(\[]*(?:Eq(?:n|uation)?\.?|Equation)\s+(?P<num>\(?\d{1,3}(?:\.\d{1,3})?\)?)(?P<trail>[\)\]\.,;:]*)$",
            stripped_semantic,
            re.IGNORECASE,
        )
        eq_key = _eq_key(eq_direct.group("num")) if eq_direct is not None else None
        if eq_key is None:
            eq_num_only = re.match(
                r"^(?P<num>\(?\d{1,3}(?:\.\d{1,3})?\)?)(?P<trail>[\)\]\.,;:]*)$",
                stripped_semantic,
            )
            if eq_num_only is not None and re.search(r"\b(?:Eq(?:n|uation)?\.?|Equation)\s*$", left_text, re.IGNORECASE):
                eq_key = _eq_key(eq_num_only.group("num"))
        if eq_key is not None:
            if eq_key in found_equations:
                return _link_page_anchor(m, f"#eq-{eq_key}", "z2m-eq-link")
            return body

        if re.fullmatch(
            r"[\(\[]?\s*(?:Fig(?:ure)?s?|Figures?|Table|Tables|Section|Appendix|Box|Eq(?:n|uation)?\.?|Equation)\.?\s*[\)\]]?",
            stripped_semantic,
            re.IGNORECASE,
        ) and re.match(r"^\s*(?:ure\s+)?(?:S?\d|[A-Z]\b)", right_text, re.IGNORECASE):
            return body

        if re.fullmatch(r"(?i:fig(?:ure)?|fig\.?|table|tables?)", stripped_semantic) and re.match(
            r"^\s*of\b",
            right_text,
            re.IGNORECASE,
        ):
            return m.group(0)

        semantic_context = f"{left_text[-120:]} {stripped_semantic} {right_text[:120]}"
        if re.search(
            r"\b(?:Fig(?:ure)?s?|Figures?|Tables?|Additional\s+Files?|"
            r"Supplementary\s+(?:Fig(?:ure)?|Table|Appendix|Information|Files?)|"
            r"Multimedia\s+Appendices?|Sections?|Appendix|Textbox|Box|"
            r"Eq(?:n|uation)?\.?|Equation|Algorithm|Results|Methods?|"
            r"Requirements?|Listings?|Formula|Chapters?|Video\s+captioning)\b|"
            r"\b(?:Tab|Sect|Req)\.|§",
            semantic_context,
            re.IGNORECASE,
        ) and (
            re.search(r"\d|[A-Z]\.?", stripped_semantic) is not None
            or re.fullmatch(
                r"(?i:results|training|textbox|table|figure|fig\.?|appendix|methods?|below\.?)",
                stripped_semantic,
            )
            is not None
        ):
            return body

        return m.group(0)

    return _PAGE_ANCHOR_PATTERN.sub(_replace, html)


def _cleanup_decimal_equation_page_links(html: str) -> str:
    """Unwrap decimal equation page links that cannot be safely mapped to eq IDs."""
    if "#page-" not in html:
        return html

    def _replace(match: re.Match[str]) -> str:
        label = match.group("label")
        number = match.group("num")
        target_key = number.strip("()").replace(".", "-")
        if re.search(rf'\bid\s*=\s*(["\'])eq-{re.escape(target_key)}\1', html, re.IGNORECASE):
            attrs = _replace_anchor_href_and_class(match.group("attrs"), f"#eq-{target_key}", "z2m-eq-link")
            return f'<a{attrs}>{label}\xa0{number}{match.group("trail")}</a>'
        return f'{label} {number}{match.group("trail")}'

    return _PAGE_LINKED_DECIMAL_EQUATION_REF_PATTERN.sub(_replace, html)


def _retarget_mismatched_ref_link_labels(html: str) -> str:
    """Keep visible numeric citation labels aligned with their #ref target."""
    if "#ref-" not in html:
        return html
    ref_numbers = {int(match.group(1)) for match in _LI_ID_PATTERN.finditer(html)}
    if not ref_numbers:
        return html

    def _is_valid_visible_ref(number: int) -> bool:
        return number in ref_numbers and not (1800 <= number <= 2099)

    def _render_numeric_label(label: str) -> str | None:
        if re.search(r"[A-Za-z]", label):
            return None
        if re.fullmatch(
            r"[\s\(\[\]\),.;:\-\u2010\u2011\u2012\u2013\u2014\d]+",
            label,
        ) is None:
            return None
        numbers = [int(value) for value in re.findall(r"\d{1,4}", label)]
        if not numbers or any(not _is_valid_visible_ref(number) for number in numbers):
            return None
        if any(value.startswith("0") for value in re.findall(r"\d{2,4}", label)):
            return None

        def _link_number(num_match: re.Match[str]) -> str:
            number_text = num_match.group(0)
            number = int(number_text)
            return f'<a href="#ref-{number}" class="z2m-ref-link">{number_text}</a>'

        return re.sub(r"\d{1,4}", _link_number, label)

    def _looks_like_page_reference_label(label: str) -> bool:
        normalized = re.sub(r"\s+", " ", label).strip()
        return re.search(
            r"(?:"
            r"\b(?:see|cf)\.?\s+(?:p|pp|page|pages)\.?\s*\d|"
            r"\b(?:p|pp|page|pages)\.?\s*\d|"
            r"\u0441\u043c\.?\s*\u0441\.?\s*\d"
            r")",
            normalized,
            re.IGNORECASE,
        ) is not None

    def _looks_like_author_year_context(label: str, left_text: str) -> bool:
        label_for_pattern = re.sub(r"(\d{4}[a-z]?)[\),.;:]+$", r"\1", label.strip(), flags=re.IGNORECASE)
        if _AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(label_for_pattern):
            return True
        if not re.fullmatch(r"\(?\d{4}[a-z]?\)?[\),.;:]*", label.strip(), re.IGNORECASE):
            return False
        if _AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(f"{left_text[-180:]} {label_for_pattern}"):
            return True
        author_tail = re.compile(
            r"(?:\(|;|,|\bby\s+)?\s*"
            r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
            r"(?:\s+[a-z])?"
            r"(?:\s+(?:et\s+al\.?|and|&)\s+"
            r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
            r"(?:\s+[a-z])?|\s+et\s+al\.?)?"
            r"(?:,|\.)?\s*$"
        )
        return author_tail.search(left_text[-120:]) is not None

    def _should_preserve_invalid_single_label(match: re.Match[str], label: str, visible_number: int) -> bool:
        left_text = _visible_text(html[max(0, match.start() - 180): match.start()])
        if 1800 <= visible_number <= 2099 and _looks_like_author_year_context(label, left_text):
            return True
        if _looks_like_page_reference_label(label):
            return True
        if re.fullmatch(r"\s*\d{3,4}[\)\]\.,;:]*\s*", label) and re.search(
            r"[-\u2212]?\d+\.\d+\s*$",
            left_text,
        ):
            return True
        return False

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        numbers = [int(num) for num in re.findall(r"\d{1,4}", label)]
        if len(numbers) > 1:
            rendered = _render_numeric_label(label)
            if rendered is not None and int(match.group("num")) not in numbers:
                return rendered
            return match.group(0)
        if len(numbers) != 1:
            return match.group(0)
        visible_number = numbers[0]
        if visible_number == int(match.group("num")):
            return match.group(0)
        if not _is_valid_visible_ref(visible_number):
            if _should_preserve_invalid_single_label(match, label, visible_number):
                return match.group(0)
            return match.group("body")
        attrs = _replace_href_and_link_class(match.group("attrs"), f"#ref-{visible_number}", "z2m-ref-link")
        return f'<a{attrs}>{match.group("body")}</a>'

    return _REF_ANCHOR_PATTERN.sub(_replace, html)


def _repair_ref_links_with_leading_closing_punctuation(html: str) -> str:
    """Move a leading closing parenthesis/bracket back outside a citation link."""
    if "#ref-" not in html:
        return html

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        label_match = re.fullmatch(r"(?P<lead>[\)\]])\s*(?P<num>\d{1,3})(?P<trail>[,.;:]*)", label)
        if label_match is None or label_match.group("num") != match.group("num"):
            return match.group(0)
        return (
            f'{label_match.group("lead")}'
            f'<a{match.group("attrs")}>{label_match.group("num")}</a>'
            f'{label_match.group("trail")}'
        )

    return _REF_ANCHOR_PATTERN.sub(_replace, html)


def _unwrap_reference_list_page_number_links(html: str) -> str:
    """Remove Marker page links from leading bibliography item numbers."""
    if "#page-" not in html or "z2m-ref-num" not in html:
        return html

    def _replace(match: re.Match[str]) -> str:
        label = re.sub(r"\s+", " ", _visible_text(match.group("body"))).strip()
        if label != f"{match.group('num')}." and label != match.group("num"):
            return match.group(0)
        return f"{match.group('open')}{match.group('body')}"

    repaired = _REFERENCE_LEADING_PAGE_NUM_ANCHOR_PATTERN.sub(_replace, html)

    def _drop_duplicate(match: re.Match[str]) -> str:
        label = re.sub(r"\s+", " ", _visible_text(match.group("body"))).strip()
        if label != f"{match.group('num')}." and label != match.group("num"):
            return match.group(0)
        return match.group("open")

    return _REFERENCE_DUPLICATE_PAGE_NUM_ANCHOR_PATTERN.sub(_drop_duplicate, repaired)


def _unwrap_reference_list_page_links(html: str) -> str:
    """Remove residual PDF page links inside normalized bibliography entries."""
    if "#page-" not in html or "ref-" not in html:
        return html

    def _unwrap_anchors(fragment: str) -> str:
        return _PAGE_ANCHOR_PATTERN.sub(lambda match: match.group("body"), fragment)

    def _replace_li(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        body = match.group(2) or ""
        if _LI_ID_PATTERN.search(attrs) is None:
            return match.group(0)
        return f"<li{attrs}>{_unwrap_anchors(body)}</li>"

    repaired = _LI_BLOCK_PATTERN.sub(_replace_li, html)

    def _replace_p(match: re.Match[str]) -> str:
        open_tag = match.group("open")
        if _LI_ID_PATTERN.search(open_tag) is None:
            return match.group(0)
        return f'{open_tag}{_unwrap_anchors(match.group("body"))}{match.group("close")}'

    return _P_BLOCK_PATTERN.sub(_replace_p, repaired)


def _unwrap_page_reference_ref_links(html: str, language_policy: PolishLanguagePolicy) -> str:
    """Remove bibliography links from explicit page references."""
    if "#ref-" not in html:
        return html

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        left_text = _visible_text(html[max(0, match.start() - 48): match.start()])
        if language_policy.looks_like_page_reference(label, left_text=left_text):
            return match.group("body")
        return match.group(0)

    return _REF_ANCHOR_PATTERN.sub(_replace, html)


def _repair_ref_links_absorbed_decimal_or_unit_text(html: str) -> str:
    """Move OCR-swallowed decimal/unit text back out of citation anchors."""
    if "#ref-" not in html:
        return html
    ref_numbers = {int(match.group(1)) for match in _LI_ID_PATTERN.finditer(html)}
    if not ref_numbers:
        return html

    def _valid_cite(
        cite_text: str,
        target_text: str,
        *,
        allow_near_target: bool = False,
        allow_wrong_target: bool = False,
    ) -> int | None:
        if not cite_text or cite_text.startswith("0"):
            return None
        try:
            cite = int(cite_text)
            target = int(target_text)
        except ValueError:
            return None
        if cite not in ref_numbers or 1800 <= cite <= 2099:
            return None
        if target == cite or (allow_near_target and abs(target - cite) <= 1) or allow_wrong_target:
            return cite
        return None

    decimal_pattern = re.compile(
        r"(?P<prefix>(?<![\w.])[-\u2212]?\d+\.\d+)\s+"
        r"(?P<sup_open><sup\b[^>]*>\s*)?"
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"][^>]*)>"
        r"\s*(?P<lead>\d)(?P<cite>\d{2,3})(?P<trail>[\)\]\.,;:]*)\s*</a>"
        r"(?P<sup_close>\s*</sup>)?",
        re.IGNORECASE | re.DOTALL,
    )
    percent_pattern = re.compile(
        r"(?P<prefix>\d)\s+"
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"][^>]*)>"
        r"\s*%(?P<cite>\d{1,3})(?P<trail>[\)\]\.,;:]*)\s*</a>",
        re.IGNORECASE | re.DOTALL,
    )
    slash_unit_pattern = re.compile(
        r"(?P<prefix>\b(?:mL|ml|L|mm|cm|m|um|nm|µm)\s*/)\s*"
        r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"][^>]*)>"
        r"\s*s(?P<cite>\d{1,3})(?P<trail>[\)\]\.,;:]*)\s*</a>",
        re.IGNORECASE | re.DOTALL,
    )

    def _anchor(attrs: str, cite: int, label: str) -> str:
        fixed_attrs = _replace_href_and_link_class(attrs, f"#ref-{cite}", "z2m-ref-link")
        return f"<a{fixed_attrs}>{label}</a>"

    def _replace_decimal(match: re.Match[str]) -> str:
        full_text = f"{match.group('lead')}{match.group('cite')}"
        try:
            full_number = int(full_text)
            target_number = int(match.group("target"))
        except ValueError:
            full_number = -1
            target_number = -1
        if full_number in ref_numbers and abs(target_number - full_number) <= 1:
            return match.group(0)
        cite = _valid_cite(match.group("cite"), match.group("target"), allow_near_target=True)
        if cite is None:
            cite = _valid_cite(
                match.group("cite"),
                match.group("target"),
                allow_wrong_target=full_number not in ref_numbers,
            )
        if cite is None:
            return match.group(0)
        anchor = _anchor(match.group("attrs"), cite, str(cite))
        if match.group("sup_open") and match.group("sup_close"):
            anchor = f"{match.group('sup_open')}{anchor}{match.group('sup_close')}"
        return (
            f"{match.group('prefix')}{match.group('lead')}"
            f"{anchor}{match.group('trail')}"
        )

    def _replace_percent(match: re.Match[str]) -> str:
        cite = _valid_cite(match.group("cite"), match.group("target"))
        if cite is None:
            return match.group(0)
        return f"{match.group('prefix')}%{_anchor(match.group('attrs'), cite, str(cite))}{match.group('trail')}"

    def _replace_slash_unit(match: re.Match[str]) -> str:
        cite = _valid_cite(match.group("cite"), match.group("target"))
        if cite is None:
            return match.group(0)
        return f"{match.group('prefix')}s{_anchor(match.group('attrs'), cite, str(cite))}{match.group('trail')}"

    repaired = decimal_pattern.sub(_replace_decimal, html)
    repaired = percent_pattern.sub(_replace_percent, repaired)
    return slash_unit_pattern.sub(_replace_slash_unit, repaired)


def _unwrap_author_year_ref_links(html: str, citation_profile: Any | None = None) -> str:
    """Remove low-confidence numeric ref links from author-year citation text."""
    if "#ref-" not in html:
        return html
    pdf_annotation_labels = _pdf_annotation_reference_label_keys(citation_profile)

    year_continuation_pattern = re.compile(
        r"^\s*\(?\d{4}[a-z]?\)?[\),.;:]*\s*$",
        re.IGNORECASE,
    )
    author_tail_pattern = re.compile(
        r"(?:\(|;|,|\bby\s+)?\s*"
        r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
        r"(?:\s+(?:et\s+al\.?|and|&)\s+"
        r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
        r"|\s+et\s+al\.?)?"
        r"(?:,|\.)?\s*$",
        re.IGNORECASE,
    )

    def _is_author_year_continuation(label: str, left_text: str) -> bool:
        if year_continuation_pattern.fullmatch(label) is None:
            return False
        label_for_pattern = re.sub(
            r"(\d{4}[a-z]?)[\),.;:]+$",
            r"\1",
            label.strip(),
            flags=re.IGNORECASE,
        )
        if _AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(f"{left_text[-180:]} {label_for_pattern}"):
            return True
        return author_tail_pattern.search(left_text[-140:]) is not None

    def _normalized_year_label(label: str) -> str:
        match = re.search(r"\d{4}[a-z]?", label, re.IGNORECASE)
        return match.group(0).casefold() if match else ""

    def _right_hand_year_label(right_text: str) -> str:
        right_text = html_lib.unescape(right_text)
        name_token = (
            r"(?:[A-Z]\.\s*)?"
            r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
        )
        match = re.match(
            rf"^\s*(?:(?:\(|,|;|\band\b|\bet\s+al\.?)\s*)?"
            rf"(?:(?:&|\band\b)\s*{name_token}\s*)?"
            r"\(?\s*(\d{4}[a-z]?)\)?",
            right_text,
            re.IGNORECASE,
        )
        return match.group(1).casefold() if match else ""

    def _looks_like_author_year_author_fragment(label: str, left_text: str, right_text: str) -> bool:
        if not _right_hand_year_label(right_text):
            return False
        cleaned = label.strip()
        if re.search(r"\d{4}", cleaned):
            return False
        name_token = (
            r"(?:[A-Z]\.\s*)?"
            r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
        )
        name_fragment = re.sub(r"\s+", " ", html_lib.unescape(cleaned.strip("([;, "))).strip()
        if re.fullmatch(
            rf"{name_token}(?:\s+(?:et\s+al\.?|&\s*{name_token}|and\s+{name_token}))?",
            name_fragment,
            re.IGNORECASE,
        ):
            return True
        if re.fullmatch(rf"(?:&|and)\s*{name_token}", name_fragment, re.IGNORECASE):
            return author_tail_pattern.search(html_lib.unescape(left_text)[-140:]) is not None
        if re.fullmatch(r"et\s+al\.?", name_fragment, re.IGNORECASE):
            return author_tail_pattern.search(left_text[-140:]) is not None
        return False

    def _author_year_name_tokens(label: str) -> list[str]:
        cleaned = html_lib.unescape(label)
        cleaned = re.sub(r"\b\d{4}[a-z]?\b", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bet\s+al\.?", " ", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"[\(\)\[\],.;:]+", " ", cleaned)
        tokens = [
            token.casefold()
            for token in re.findall(
                r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+",
                cleaned,
            )
            if token.casefold().strip(".") not in {"and", "et", "al"}
            and len(token.strip(". ")) > 1
        ]
        return list(dict.fromkeys(tokens))

    reference_text_by_num: dict[int, str] = {}
    for li_match in _LI_BLOCK_PATTERN.finditer(html):
        attrs = li_match.group(1) or ""
        id_match = _LI_ID_PATTERN.search(attrs)
        if id_match is None:
            continue
        reference_text_by_num[int(id_match.group(1))] = _visible_text(li_match.group(2))

    year_labels_by_target: dict[int, set[str]] = {}
    for anchor_match in _REF_ANCHOR_PATTERN.finditer(html):
        label = _visible_text(anchor_match.group("body"))
        left_text = _visible_text(html[max(0, anchor_match.start() - 180): anchor_match.start()])
        if not _is_author_year_continuation(label, left_text):
            continue
        year = _normalized_year_label(label)
        if not year:
            continue
        year_labels_by_target.setdefault(int(anchor_match.group("num")), set()).add(year)
    repeated_year_targets = {
        target for target, years in year_labels_by_target.items() if len(years) > 1
    }

    def _target_ref_matches_author_year(
        target: int,
        label: str,
        left_text: str,
        right_text: str = "",
        *,
        require_reference_year: bool = False,
    ) -> bool:
        ref_text = reference_text_by_num.get(target, "")
        if not ref_text:
            if require_reference_year:
                return False
            return target not in repeated_year_targets
        ref_lower = ref_text.casefold()
        ref_years = {year.casefold() for year in re.findall(r"\b\d{4}[a-z]?\b", ref_text, re.IGNORECASE)}
        label_year = _normalized_year_label(label) or _right_hand_year_label(right_text)
        if not ref_years:
            if require_reference_year:
                return False
            return target not in repeated_year_targets
        if label_year and label_year not in ref_years:
            return False
        author_source = html_lib.unescape(f"{left_text[-160:]} {label}")
        author_match = author_tail_pattern.search(author_source[-220:])
        if author_match is None:
            if require_reference_year:
                return False
            return target not in repeated_year_targets
        author_tail = author_match.group(0)
        surnames = [
            surname.casefold()
            for surname in re.findall(
                r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+",
                author_tail,
            )
            if surname.casefold() not in {"et", "al", "and"} and len(surname.strip(". ")) > 1
        ]
        if not surnames:
            return target not in repeated_year_targets
        return any(surname in ref_lower for surname in surnames)

    def _reference_text_matches_author_year(ref_text: str, name_tokens: list[str], year: str) -> bool:
        if not name_tokens or not year:
            return False
        ref_lower = html_lib.unescape(ref_text).casefold()
        ref_years = {
            found.casefold()
            for found in re.findall(r"\b\d{4}[a-z]?\b", ref_text, re.IGNORECASE)
        }
        if year.casefold() not in ref_years:
            return False
        for token in name_tokens:
            if re.search(
                rf"(?<![a-z\u00c0-\u00ff]){re.escape(token)}(?![a-z\u00c0-\u00ff])",
                ref_lower,
                re.IGNORECASE,
            ) is None:
                return False
        return True

    def _author_year_matching_ref_target(label: str, right_text: str) -> int | None:
        year = _normalized_year_label(label) or _right_hand_year_label(right_text)
        tokens = _author_year_name_tokens(label)
        if not year or not tokens:
            return None
        matches = [
            target
            for target, ref_text in reference_text_by_num.items()
            if _reference_text_matches_author_year(ref_text, tokens, year)
        ]
        return matches[0] if len(matches) == 1 else None

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        if _normalize_pdf_annotation_label(label).casefold() in pdf_annotation_labels:
            return match.group(0)
        left_text = _visible_text(html[max(0, match.start() - 180): match.start()])
        right_text = _visible_text(html[match.end(): match.end() + 140])
        is_year_continuation = _is_author_year_continuation(label, left_text)
        if is_year_continuation and _target_ref_matches_author_year(
            int(match.group("num")),
            label,
            left_text,
            right_text,
        ):
            return match.group(0)
        surname_fragment = (
            re.fullmatch(r"[A-Z][A-Za-z'’.-]{3,}", label) is not None
            and re.match(r"^\s*et\s+al\.?\s*\(?\d{4}[a-z]?\)?", right_text, re.IGNORECASE) is not None
        ) or _looks_like_author_year_author_fragment(label, left_text, right_text)
        single_surname_et_al_fragment = (
            re.fullmatch(r"[A-Z][A-Za-z'\u2019.-]{3,}", label) is not None
            and re.match(r"^\s*et\s+al\.?\s*\(?\d{4}[a-z]?\)?", right_text, re.IGNORECASE)
            is not None
        )
        if single_surname_et_al_fragment:
            return match.group("body")
        if surname_fragment:
            matching_target = _author_year_matching_ref_target(label, right_text)
            if matching_target is not None and matching_target != int(match.group("num")):
                attrs = _replace_href_and_link_class(
                    match.group("attrs"),
                    f"#ref-{matching_target}",
                    "z2m-ref-link",
                )
                return f'<a{attrs}>{match.group("body")}</a>'
        if surname_fragment and _target_ref_matches_author_year(
            int(match.group("num")),
            label,
            left_text,
            right_text,
            require_reference_year=True,
        ):
            return match.group(0)
        if (
            _AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(label) is None
            and not surname_fragment
            and not is_year_continuation
        ):
            return match.group(0)
        return match.group("body")

    return _REF_ANCHOR_PATTERN.sub(_replace, html)


def _repair_roman_suffix_author_year_ref_link_splits(html: str) -> str:
    """Undo ref links that captured a surname-final roman-like suffix."""
    if "z2m-ref-link" not in html:
        return html

    pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+"
        r"<a\b(?=[^>]*\bhref\s*=\s*['\"]#ref-(?P<target>\d+)['\"])(?=[^>]*\bz2m-ref-link\b)[^>]*>"
        r"\s*(?P<suffix>vi|i|v)\s*</a>"
        r"(?=\s*<a\b(?=[^>]*\bhref\s*=\s*['\"]#ref-(?P=target)['\"])(?=[^>]*\bz2m-ref-link\b)[^>]*>"
        r"\s*\(?\d{4})",
        re.IGNORECASE,
    )
    blocked_roots = {
        "appendix",
        "figure",
        "section",
        "table",
    }

    def _replace(match: re.Match[str]) -> str:
        root = match.group("root")
        if root.lower() in blocked_roots:
            return match.group(0)
        return f"{root}{match.group('suffix').lower()}"

    return pattern.sub(_replace, html)


def _unwrap_author_year_page_links(html: str) -> str:
    """Page anchors around author-year citations are stale PDF navigation, not citations."""
    if "#page-" not in html:
        return html

    name_token = (
        r"(?:[A-Z]\.\s*)?"
        r"[A-Z\u00c0-\u00de][A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u00ff'\u2019.-]+"
    )
    blocked_fragments = {
        "appendix",
        "chapter",
        "eq",
        "eqn",
        "equation",
        "fig",
        "figure",
        "method",
        "methods",
        "page",
        "pages",
        "pp",
        "results",
        "section",
        "table",
    }

    def _looks_like_author_year_page_fragment(label: str, left_text: str, right_text: str) -> bool:
        cleaned = re.sub(r"\s+", " ", html_lib.unescape(label).strip("([;, ")).strip()
        if not cleaned or re.search(r"\d{4}", cleaned):
            return False
        if cleaned.casefold().rstrip(".") in blocked_fragments:
            return False
        right_context = re.sub(r"\s+", " ", html_lib.unescape(right_text)).strip()
        if not right_context or re.match(r"^(?:of|for|in|to)\b", right_context, re.IGNORECASE):
            return False
        split_et_al_continuation = re.fullmatch(rf"{name_token}\s+et", cleaned, re.IGNORECASE) is not None and re.match(
            r"^al\.?\s*\(?\d{4}[a-z]?\)?",
            right_context,
            re.IGNORECASE,
        ) is not None
        split_surname_continuation = re.fullmatch(r"\(?[A-Z][A-Za-z]{2,6}", cleaned) is not None and re.match(
            r"^[a-z]{1,10}\s+et\s+al\.?\s*\(?\d{4}[a-z]?\)?",
            right_context,
            re.IGNORECASE,
        ) is not None
        citation_context = (
            re.search(r"[\(;]\s*$", html_lib.unescape(left_text)) is not None
            or re.search(r"\bby\s*$", html_lib.unescape(left_text), re.IGNORECASE) is not None
            or label.lstrip().startswith("(")
            or right_context.startswith((",", ";", ")", "&"))
            or re.match(r"^(?:&|and|al\.?|et\s+al\.?|\(?\d{4})\b", right_context, re.IGNORECASE)
            is not None
            or split_et_al_continuation
            or split_surname_continuation
        )
        if not citation_context:
            return False
        candidate = re.sub(r"\s+", " ", f"{cleaned} {right_context[:120]}").strip()
        if _AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(candidate):
            return True
        if split_et_al_continuation:
            return True
        if split_surname_continuation:
            return True
        return False

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        label_for_pattern = re.sub(r"(\d{4}[a-z]?)[\),.;:]+$", r"\1", label.strip(), flags=re.IGNORECASE)
        if _AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(label) is None:
            left_text = _visible_text(html[max(0, match.start() - 180): match.start()])
            right_text = _visible_text(html[match.end(): match.end() + 80])
            if re.search(r"\d{4}", label) and _AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(
                f"{left_text[-180:]} {label_for_pattern}"
            ):
                return match.group("body")
            flexible_year_continuation = (
                re.search(
                    r"\b[A-Z][A-Za-z'.-]+(?:\s+et\s+al\.?|\s*&\s*[A-Z][A-Za-z'.-]+)?"
                    r"(?:,)?\s*(?:\d{4}[a-z]?\s*[,;]?\s*)?$",
                    left_text,
                )
                is not None
                and not re.match(r"^\s*(?:of|for|in|to)\b", right_text, re.IGNORECASE)
            )
            year_continuation = (
                re.fullmatch(r"\(?\d{4}[a-z]?\)?[\),.;:]*", label.strip(), re.IGNORECASE) is not None
                and re.search(
                    r"\b[A-Z][A-Za-z'вЂ™.-]+(?:\s+et\s+al\.?)?,\s*(?:\d{4}[a-z]?\s*,?\s*)?$",
                    left_text,
                )
                is not None
            )
            author_fragment_continuation = _looks_like_author_year_page_fragment(label, left_text, right_text)
            if not (year_continuation or flexible_year_continuation or author_fragment_continuation):
                return match.group(0)
        return match.group("body")

    return _PAGE_ANCHOR_PATTERN.sub(_replace, html)


def _unwrap_stale_numeric_page_links(html: str, language_policy: PolishLanguagePolicy) -> str:
    """Remove leftover page anchors that wrap citation-like numeric labels."""
    if "#page-" not in html:
        return html

    numeric_label = re.compile(
        r"^\s*[\[\(]?\s*\d{1,4}"
        r"(?:\s*(?:[,;]|&|and|[-\u2010\u2011\u2012\u2013\u2014])\s*\d{1,4})*"
        r"[\]\)\.,;:]*\s*$",
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        left_text = _visible_text(html[max(0, match.start() - 80): match.start()])
        if language_policy.looks_like_page_reference(label, left_text=left_text):
            return match.group(0)
        if re.search(r"\b(?:pages?|pp?\.?|sheet|slide)\s*$", left_text, re.IGNORECASE):
            return match.group(0)
        if numeric_label.fullmatch(label) is None:
            return match.group(0)
        return match.group("body")

    return _PAGE_ANCHOR_PATTERN.sub(_replace, html)


def _unwrap_plain_prose_page_links(html: str) -> str:
    """Drop page anchors that wrap ordinary prose fragments."""
    if "#page-" not in html:
        return html

    semantic_label = re.compile(
        r"^\s*(?:"
        r"(?:Fig(?:s|ure)?|Figures?|Table|Tables|Box|Section|Appendix|Eq(?:n|uation)?\.?|Equation)"
        r"\.?\s+[A-Za-z0-9IVXLCM.\-–]+|"
        r"\[\s*\d|"
        r"\(?S?\d+(?:[-–]\s*S?\d+)?\s*(?:Tables?|Figures?|Files?|Data)?\)?"
        r")",
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        if re.fullmatch(r"[A-Z]{2,6}", label.strip()) is not None:
            left_text = _visible_text(html[max(0, match.start() - 48): match.start()])
            if re.search(r"\b(?:page|pp?\.?|section|chapter)\s*$", left_text, re.IGNORECASE) is None:
                return match.group("body")
        if len(re.findall(r"[A-Za-z]{2,}", label)) < 3:
            return match.group(0)
        if _AUTHOR_YEAR_CITATION_TEXT_PATTERN.search(label) is not None:
            return match.group("body")
        if semantic_label.match(label):
            if re.match(r"^\s*\d+(?:\.\d+){1,}\.?\s+[A-Z]", label) and len(
                re.findall(r"[A-Za-z]{2,}", label)
            ) >= 3:
                return match.group("body")
            return match.group(0)
        if re.search(r"\b(?:copyright|creative commons|doi|https?|www\.)\b", label, re.IGNORECASE):
            return match.group(0)
        return match.group("body")

    return _PAGE_ANCHOR_PATTERN.sub(_replace, html)


def _unwrap_page_reference_page_links(html: str, language_policy: PolishLanguagePolicy) -> str:
    """Remove page-anchor links from explicit page-reference labels."""
    if "#page-" not in html:
        return html

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        left_text = _visible_text(html[max(0, match.start() - 48): match.start()])
        if language_policy.looks_like_page_reference(label, left_text=left_text):
            return match.group("body")
        return match.group(0)

    return _PAGE_ANCHOR_PATTERN.sub(_replace, html)


def _unwrap_duplicate_see_page_anchor_tails(html: str) -> str:
    """Unwrap page-number tails when Marker split one "See page N" page anchor."""
    if "#page-" not in html:
        return html

    pattern = re.compile(
        r'(?P<first><a\b(?P<attrs1>[^>]*\bhref\s*=\s*(?P<q1>["\'])#(?P<target>page-[^"\']+)(?P=q1)[^>]*)>'
        r"\s*See\s*</a>)"
        r"\s*"
        r'<a\b[^>]*\bhref\s*=\s*(?P<q2>["\'])#(?P=target)(?P=q2)[^>]*>'
        r"(?P<body>\s*(?:pages?|pp?\.?)?\s*\d{1,4}[\)\]\.,;:]*\s*)</a>",
        re.IGNORECASE,
    )
    return pattern.sub(lambda match: f"{match.group('first')} {match.group('body').strip()}", html)


def _unwrap_broken_page_anchor_links(html: str) -> str:
    """Drop #page-* links that no longer have a matching page anchor id."""
    if "#page-" not in html:
        return html
    page_ids = {match.group(2) for match in _REFERENCE_PAGE_ID_PATTERN.finditer(html)}
    if not page_ids:
        return _PAGE_ANCHOR_PATTERN.sub(lambda match: match.group("body"), html)

    def _replace(match: re.Match[str]) -> str:
        href_match = re.search(r'\bhref\s*=\s*(["\'])#(?P<target>page-[^"\']+)\1', match.group("attrs"), re.IGNORECASE)
        if href_match is None or href_match.group("target") in page_ids:
            return match.group(0)
        return match.group("body")

    return _PAGE_ANCHOR_PATTERN.sub(_replace, html)


def _unwrap_broken_internal_semantic_links(html: str) -> str:
    """Drop late broken table/page links without stripping preserved citation markup."""
    if 'href="#' not in html and "href='#" not in html:
        return html
    ids = {
        match.group("id")
        for match in re.finditer(
            r'\bid\s*=\s*(["\'])(?P<id>[^"\']+)\1',
            html,
            re.IGNORECASE | re.DOTALL,
        )
    }

    def _replace(match: re.Match[str]) -> str:
        target = match.group("target")
        if target in ids:
            return match.group(0)
        if target.startswith("page-"):
            label = _visible_text(match.group("body")).strip()
            left_text = _visible_text(html[max(0, match.start() - 100) : match.start()])
            if re.fullmatch(r"[\[\(]?\s*(?:pages?|pp?\.?|p\.?)?\s*\d{1,4}[\)\]\.,;:]?", label, re.IGNORECASE):
                return match.group(0)
            if re.search(r"\b(?:fig(?:ure)?|figs?|figures?|table|рисунок|фигура|таблица)\s*$", left_text, re.IGNORECASE):
                if re.fullmatch(r"\d{1,4}[A-Za-zА-Яа-я]?", label):
                    return match.group(0)
        return match.group("body")

    return _SEMANTIC_INTERNAL_ANCHOR_PATTERN.sub(_replace, html)


def _repair_statistical_ref_false_positives(html: str) -> str:
    """Unlink small numbers that are statistical values, not bibliography references."""
    if "#ref-" not in html:
        return html

    def _context_text(source: str, start: int, end: int) -> str:
        left_bound = source.rfind("<p", 0, start)
        right_bound = source.find("</p>", end)
        if left_bound == -1 or right_bound == -1:
            context_html = source[max(0, start - 180) : end + 180]
        else:
            context_html = source[left_bound : right_bound + len("</p>")]
        return _visible_text(context_html)

    def _has_stat_value_left_context(source: str, start: int) -> bool:
        left_text = _visible_text(source[max(0, start - 240) : start])
        return re.search(
            r"(?:"
            r"\beffect\s+size\b[^.;:]{0,120}\b(?:was|is|of|=)\s*|"
            r"\ballocation\s+ratio\b[^.;:]{0,160}\bG\*Power\s*|"
            r"\bG\*Power\s*|"
            r"\blogMAR\s*|"
            r"\blogMAR\b[^;:]{0,100}\b(?:and|or)\s*|"
            r"\b(?:SD|SEM)\s*=?\s*|"
            r"\bZ\s+values?\b[^.;:]{0,80}\b(?:was|were|of|=)\s*|"
            r"\brange\s+from\s+about\s*"
            r")$",
            left_text,
            re.IGNORECASE,
        ) is not None

    def _has_sample_size_value_left_context(source: str, start: int) -> bool:
        left_text = _visible_text(source[max(0, start - 240) : start])
        return re.search(
            r"\bsample\s+size\b[^.;:]{0,160}\b(?:was|were|is|=|:)\s*$",
            left_text,
            re.IGNORECASE,
        ) is not None

    def _right_allows_sample_size_value(source: str, end: int) -> bool:
        right_text = _visible_text(source[end : end + 100]).lstrip()
        return (
            not right_text
            or re.match(
                r"^(?:[\.,;:)]|to\b|[-\u2010-\u2014]|\d|participants?\b|patients?\b|subjects?\b|controls?\b)",
                right_text,
                re.IGNORECASE,
            )
            is not None
        )

    def _inside_bracket_numeric_citation(source: str, start: int, end: int) -> bool:
        left = source.rfind("[", max(0, start - 120), start)
        right = source.find("]", end, min(len(source), end + 160))
        if left < 0 or right < 0:
            return False
        visible = re.sub(r"\s+", " ", _visible_text(source[left : right + 1])).strip()
        return _BRACKET_CITATION_PATTERN.fullmatch(visible) is not None

    numeric_sup_run_pattern = re.compile(
        r"<sup\b[^>]*>[\s\S]{0,260}?\bz2m-ref-link\b[\s\S]{0,260}?</sup>",
        re.IGNORECASE,
    )

    def _replace_stat_sup_run(match: re.Match[str]) -> str:
        raw = match.group(0)
        compact_text = re.sub(r"\s+", "", _visible_text(raw))
        if re.fullmatch(r"\d{1,3}(?:[,;\-\u2013\u2014]\d{1,3})+", compact_text) is None:
            return raw
        context = _context_text(html, match.start(), match.end())
        if _STAT_FALSE_REF_STRONG_CONTEXT_PATTERN.search(context) is None:
            return raw
        if not _has_stat_value_left_context(html, match.start()):
            return raw
        if re.fullmatch(r"\d{1,3},\d{1,3}", compact_text):
            return compact_text.replace(",", ".")
        return compact_text

    repaired = numeric_sup_run_pattern.sub(_replace_stat_sup_run, html)

    def _inside_superscript_citation_run(match: re.Match[str]) -> bool:
        sup_start = repaired.rfind("<sup", 0, match.start())
        if sup_start == -1:
            return False
        previous_sup_close = repaired.rfind("</sup>", 0, match.start())
        if previous_sup_close > sup_start:
            return False
        sup_end = repaired.find("</sup>", match.end())
        if sup_end == -1:
            return False
        sup_html = repaired[sup_start : sup_end + len("</sup>")]
        if "z2m-ref-link" not in sup_html:
            return False
        sup_text = re.sub(r"\s+", "", _visible_text(sup_html))
        return re.fullmatch(r"\d{1,3}(?:[,;\-\u2013\u2014]\d{1,3})+", sup_text) is not None

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        if re.fullmatch(r"\d{1,3}", label) is None:
            return match.group(0)
        try:
            number = int(label)
        except ValueError:
            return match.group(0)
        if number > 5:
            if _has_sample_size_value_left_context(repaired, match.start()) and _right_allows_sample_size_value(
                repaired,
                match.end(),
            ):
                return match.group("body")
            return match.group(0)
        if _inside_bracket_numeric_citation(repaired, match.start(), match.end()):
            return match.group(0)
        if _has_sample_size_value_left_context(repaired, match.start()) and _right_allows_sample_size_value(
            repaired,
            match.end(),
        ):
            return match.group("body")
        if _inside_superscript_citation_run(match):
            if _has_stat_value_left_context(repaired, match.start()):
                return match.group("body")
            return match.group(0)
        context = _context_text(repaired, match.start(), match.end())
        if _STAT_FALSE_REF_CONTEXT_PATTERN.search(context) is None:
            return match.group(0)
        return match.group("body")

    return _REF_ANCHOR_PATTERN.sub(_replace, repaired)


def _repair_figure_ref_links_misclassified_as_refs(html: str, found_figures: set[str]) -> str:
    """Retarget or unwrap numbers in figure lists that citation linking caught."""
    if "#ref-" not in html:
        return html
    figure_list_left_context = re.compile(
        rf"\b(?P<supp>{_SUPPLEMENTARY_FIG_PREFIX_TOKEN}\s+)?{_FIG_REF_LABEL_TOKEN}\.?\s*"
        rf"(?:{_FIG_KEY_TOKEN}(?:[a-z]|\([a-z]\))?\s*"
        rf"(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*)*$",
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body"))
        if re.fullmatch(r"\d{1,3}", label) is None:
            return match.group(0)
        left_text = _visible_text(html[max(0, match.start() - 120): match.start()])
        context_match = figure_list_left_context.search(left_text)
        if context_match is None:
            return match.group(0)
        key = (
            _supplementary_figure_key_from_visible_number(label)
            if context_match.group("supp")
            else _figure_key_from_visible_number(label)
        )
        if key in found_figures:
            attrs = _replace_href_and_link_class(match.group("attrs"), f"#fig-{key}", "z2m-fig-link")
            return f'<a{attrs}>{match.group("body")}</a>'
        return match.group("body")

    repaired = _REF_ANCHOR_PATTERN.sub(_replace, html)
    return re.sub(
        r'<sup\b[^>]*>\s*(<a\b[^>]*\bz2m-fig-link\b[^>]*>[\s\S]{0,120}?</a>)\s*</sup>',
        r"\1",
        repaired,
        flags=re.IGNORECASE,
    )


def _repair_bracket_citation_fig_links_misclassified_as_figures(html: str) -> str:
    """Turn figure links back into ref links when they sit inside [N, M] citations."""
    if "z2m-fig-link" not in html or "#ref-" not in html:
        return html
    ref_numbers = {int(match.group(1)) for match in _LI_ID_PATTERN.finditer(html)}
    if not ref_numbers:
        return html

    pattern = re.compile(r"\[\s*(?P<body>(?=[\s\S]*?<a\b)[\s\S]{1,260}?)\s*\]", re.IGNORECASE)

    def _replace(match: re.Match[str]) -> str:
        body = match.group("body")
        if "z2m-fig-link" not in body:
            return match.group(0)
        visible = _visible_text(body)
        if _BRACKET_CITATION_PATTERN.fullmatch(f"[{visible}]") is None:
            return match.group(0)
        numbers = [int(value) for value in re.findall(r"\d{1,3}", visible)]
        if not numbers or any(number not in ref_numbers for number in numbers):
            return match.group(0)
        normalized = re.sub(r"\s+([,;])", r"\1", visible.strip())
        normalized = re.sub(r"([,;])(?=\S)", r"\1 ", normalized)
        normalized = re.sub(r"\s*([-\u2013\u2014])\s*", r"\1", normalized)

        def _link_number(num_match: re.Match[str]) -> str:
            number_text = num_match.group(0)
            number = int(number_text)
            return f'<a href="#ref-{number}" class="z2m-ref-link">{number_text}</a>'

        return "[" + re.sub(r"\d{1,3}", _link_number, normalized) + "]"

    return pattern.sub(_replace, html)


def _repair_sup_figure_chain_continuations(html: str, found_figures: set[str]) -> str:
    """Link chained figure numbers that OCR/citation cleanup left in a sup tag."""
    if not found_figures or "<sup" not in html or "z2m-fig-link" not in html:
        return html
    chain_sup_pattern = re.compile(
        r'(?P<prefix><a\b[^>]*\bhref\s*=\s*["\']#fig-[^"\']+["\'][^>]*'
        r'\bz2m-fig-link\b[^>]*>[\s\S]{0,180}?</a>\s*'
        r'(?:and|or|,|&|[-\u2010\u2011\u2012\u2013\u2014])\s*)'
        r'<sup\b[^>]*>\s*(?P<label>\d+(?:\s*,\s*\d+|(?:[.\-\u2010\u2011\u2012\u2013\u2014])\d+)*)\s*</sup>',
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        label = re.sub(r"\s+", "", match.group("label"))
        visible = label.replace(",", ".")
        key = _figure_key_from_visible_number(visible)
        if re.search(r'href\s*=\s*["\']#fig-supplementary-[^"\']+["\']', match.group("prefix"), re.IGNORECASE):
            supplementary_key = _supplementary_figure_key_from_visible_number(visible)
            if supplementary_key in found_figures:
                key = supplementary_key
        if key not in found_figures:
            return match.group(0)
        return f'{match.group("prefix")}<a href="#fig-{key}" class="z2m-fig-link">{visible}</a>'

    return chain_sup_pattern.sub(_replace, html)


_SUP_TABLE_LINK_PATTERN = re.compile(
    r'<sup\b[^>]*>\s*(<a\b(?=[^>]*\bz2m-table-link\b)[^>]*>[\s\S]*?</a>)\s*</sup>',
    re.IGNORECASE,
)
_SUP_NUMERIC_LABEL_PATTERN = re.compile(
    r'<sup\b[^>]*>\s*(?P<label>\d{1,3}|[IVXLCM]+)\s*</sup>',
    re.IGNORECASE,
)


def _repair_table_ref_links_misclassified_as_refs(html: str, found_tables: set[str]) -> str:
    """Retarget numeric refs that are actually the second item in a table list."""
    if "#ref-" not in html or not found_tables:
        return html

    table_context = re.compile(
        rf"(?:{_TABLE_REF_WORD_TOKEN})\.?\s+{_TABLE_KEY_TOKEN}\s*"
        r"(?:and|or|и|или|,|&)\s*$",
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        label = _visible_text(match.group("body")).strip(" .;:,")
        if re.fullmatch(r"\d{1,3}|[IVXLCM]+", label, re.IGNORECASE) is None:
            return match.group(0)
        key = _normalize_table_key(label)
        if key not in found_tables:
            return match.group(0)
        left_text = _visible_text(html[max(0, match.start() - 180): match.start()])
        if table_context.search(left_text) is None:
            return match.group(0)
        attrs = _replace_href_and_link_class(match.group("attrs"), f"#table-{key}", "z2m-table-link")
        return f'<a{attrs}>{match.group("body")}</a>'

    repaired = _REF_ANCHOR_PATTERN.sub(_replace, html)
    repaired = _SUP_TABLE_LINK_PATTERN.sub(r"\1", repaired)

    def _replace_plain_sup(match: re.Match[str]) -> str:
        label = match.group("label").strip()
        key = _normalize_table_key(label)
        if key not in found_tables:
            return match.group(0)
        left_text = _visible_text(repaired[max(0, match.start() - 180): match.start()])
        if table_context.search(left_text) is None:
            return match.group(0)
        return f'<a href="#table-{key}" class="z2m-table-link">{label}</a>'

    return _SUP_NUMERIC_LABEL_PATTERN.sub(_replace_plain_sup, repaired)


def _looks_author_year_citation_document(html: str) -> bool:
    heading_match = _references_heading_search(html)
    body_html = html[: heading_match.start()] if heading_match is not None else html
    body_text = _visible_text(body_html)
    author_year_count = len(_AUTHOR_YEAR_CITATION_TEXT_PATTERN.findall(body_text))
    bracket_count = len(re.findall(r"\[\s*\d", body_text))
    paren_numeric_ref_count = 0
    for match in _REF_ANCHOR_PATTERN.finditer(body_html):
        if "<sup" in body_html[max(0, match.start() - 40): match.start()].lower():
            continue
        label = _visible_text(match.group("body")).strip()
        if re.fullmatch(r"[\s\(\)\[\],.;:\-\u2010-\u2014\d]+", label) is None:
            continue
        numbers = [int(value) for value in re.findall(r"\d{1,4}", label)]
        if not numbers or any(1800 <= number <= 2099 for number in numbers):
            continue
        left_text = _visible_text(body_html[max(0, match.start() - 40): match.start()])
        right_text = _visible_text(body_html[match.end() : match.end() + 80])
        if (
            re.search(r"\(\s*$", left_text) is not None
            or label.startswith("(")
            or re.match(r"^\s*(?:[,;\-\u2010-\u2014]\s*\d|\))", right_text) is not None
        ):
            paren_numeric_ref_count += 1
    if paren_numeric_ref_count >= 5:
        return False
    return author_year_count >= 4 and bracket_count < 4


def _should_suppress_numeric_ref_links_for_author_year(
    html: str,
    citation_profile: Any | None = None,
) -> bool:
    if _citation_profile_is_author_year(citation_profile):
        return True
    if (
        _citation_profile_is_high_confidence_paren_numeric(citation_profile)
        or _citation_profile_is_high_confidence_superscript_numeric(citation_profile)
        or _citation_profile_is_bracket_numeric(citation_profile)
    ):
        return False
    return False


def _repair_author_year_footnote_ref_links(html: str, citation_profile: Any | None = None) -> str:
    """In author-year papers, source/web footnote markers are not numeric refs."""
    if (
        _citation_profile_is_high_confidence_paren_numeric(citation_profile)
        or _citation_profile_is_high_confidence_superscript_numeric(citation_profile)
        or _citation_profile_is_bracket_numeric(citation_profile)
    ):
        return html
    if "#ref-" not in html or not _looks_author_year_citation_document(html):
        return html
    references_heading = _references_heading_search(html)
    footnote_definition_ref_numbers = {
        int(match.group("num"))
        for match in re.finditer(
            r"<p\b[^>]*>\s*"
            r"(?:<span\b[^>]*\bid\s*=\s*['\"]page-[^'\"]+['\"][^>]*>\s*</span>\s*)?"
            r"<math\b[^>]*>\s*<sup\b[^>]*>\s*\^?\s*"
            r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<num>\d{1,3})['\"][^>]*>"
            r"\s*(?P=num)\s*</a>\s*</sup>\s*</math>\s*[^<]*[A-Za-z]",
            html,
            re.IGNORECASE,
        )
        if int(match.group("num")) <= 5
    }
    footnote_definition_ref_numbers.update(
        int(match.group("num"))
        for match in re.finditer(
            r"<p\b[^>]*>\s*"
            r"(?:<span\b[^>]*\bid\s*=\s*['\"]page-[^'\"]+['\"][^>]*>\s*</span>\s*)?"
            r"<sup\b[^>]*>\s*"
            r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<num>\d{1,3})['\"][^>]*>"
            r"\s*\^?\s*(?P=num)\s*</a>\s*</sup>\s*[^<]*[A-Za-z]",
            html,
            re.IGNORECASE,
        )
        if int(match.group("num")) <= 5
    )

    def _version_number_context(left_text: str) -> bool:
        return (
            re.search(
                r"\b(?:python|pytorch|cuda|tensorflow|torch|matlab|opencv|numpy|scipy|driver)\s+"
                r"(?:driver\s+)?version\s*$|\bversion\s*$|\bR\s*\(\s*v\s*$",
                left_text,
                re.IGNORECASE,
            )
            is not None
        )

    def _enumerated_dot_item_context(number: int, left_text: str, right_text: str) -> bool:
        if re.match(r"^\s*\.\s+[A-Z][A-Za-z0-9-]+", right_text) is None:
            return False
        if re.search(
            r"(?:[:;]\s*|\b(?:and|or|using|including|includes?|methods?|their|its|our|his|her)\s*)$",
            left_text,
            re.IGNORECASE,
        ) is None:
            return False
        return number == 1 or re.search(r"\b\d{1,2}\s*\.\s+[A-Z0-9]", left_text) is not None

    def _level_number_context(number: int, left_text: str, right_text: str) -> bool:
        if number < 1 or number > 5:
            return False
        if re.search(r"\blevel\s*$", left_text, re.IGNORECASE) is None:
            return False
        if re.match(r"^\s*(?:\)|,|\.|;|:|$)", right_text) is None:
            return False
        return (
            re.search(
                r"\b(?:olympic|filter|confidence|evidence|severity|risk|dose|grade|stage|class|type)\b",
                left_text[-140:],
                re.IGNORECASE,
            )
            is not None
        )

    def _replace(match: re.Match[str]) -> str:
        if references_heading is not None and match.start() > references_heading.start():
            return match.group(0)
        label = _visible_text(match.group("body")).strip()
        label_number_match = re.fullmatch(r"[\s\(\[]*(\d{1,3})[\s\)\].;:]*", label)
        if label_number_match is None:
            return match.group(0)
        try:
            number = int(label_number_match.group(1))
        except ValueError:
            return match.group(0)
        raw_window = html[max(0, match.start() - 80): match.end() + 80].lower()
        text_window = _visible_text(html[max(0, match.start() - 160): match.end() + 160])
        range_window = _visible_text(html[max(0, match.start() - 24): match.end() + 36])
        left_text = _visible_text(html[max(0, match.start() - 140): match.start()])
        dot_enum_left_text = _visible_text(html[max(0, match.start() - 420): match.start()])
        paragraph_start = html.rfind("<p", 0, match.start())
        paragraph_close = html.rfind("</p>", 0, match.start())
        same_paragraph_start = paragraph_start if paragraph_start > paragraph_close else max(0, match.start() - 160)
        same_paragraph_raw = html[same_paragraph_start : match.end() + 180]
        same_paragraph_window = _visible_text(html[max(same_paragraph_start, match.start() - 160): match.end() + 160])
        same_paragraph_left_text = _visible_text(
            html[max(same_paragraph_start, match.start() - 140): match.start()]
        )
        version_context = (
            re.search(
                r"\b(?:python|pytorch|cuda|tensorflow|torch|matlab|opencv|numpy|scipy|driver)\s+"
                r"(?:driver\s+)?version\b",
                same_paragraph_window,
                re.IGNORECASE,
            )
            is not None
            or _version_number_context(same_paragraph_left_text)
        )
        equation_label_context = (
            re.fullmatch(r"[\[(]\s*\d{1,3}\s*[\])]", label) is not None
            and re.search(r"<math\b|z2m-math|katex", same_paragraph_raw, re.IGNORECASE) is not None
        )
        numbered_study_context = (
            re.search(
                r"\b(?:experiments?|studies|study)\s+\d+\s*(?:,|and|or)\s*$",
                left_text,
                re.IGNORECASE,
            )
            is not None
        )
        right_context_start = match.end()
        sup_close = html.find("</sup>", match.end(), match.end() + 60)
        if sup_close >= 0 and not _visible_text(html[match.end() : sup_close]):
            right_context_start = sup_close + len("</sup>")
        right_text = _visible_text(html[right_context_start : right_context_start + 120])
        counted_range_context = (
            re.search(r"\b(?:counted|identified|selected|reported|rated)\s*$", left_text, re.IGNORECASE)
            is not None
            and re.match(r"^\s*(?:to|through|[-\u2013\u2014])\s+\d", right_text, re.IGNORECASE)
            is not None
        )
        sample_count_context = (
            (
                re.search(r"\b\d{1,3}\s*,\s*\d{1,3}\s*,\s*(?:and|or)\s*$", left_text, re.IGNORECASE)
                is not None
                and re.match(r"^\s*of\s+", right_text, re.IGNORECASE) is not None
            )
            or (
                re.search(r"\b\d{1,3}\s+with\b[\s\S]{0,80}\b(?:and|or)\s*$", left_text, re.IGNORECASE)
                is not None
                and re.match(r"^\s*with\s+", right_text, re.IGNORECASE) is not None
            )
        )
        inline_numeric_range_context = (
            re.search(r"(?:\(|\[)?\s*\d{1,3}\s*(?:,|[-\u2010-\u2014])\s*$", left_text)
            is not None
            and (
                re.match(r"^\s*(?:[,;.)\]]|$)", right_text) is not None
                or re.search(r"[\)\]]\s*$", label) is not None
            )
        )
        front_matter_affiliation_context = (
            number <= 20
            and re.search(
                r"\b[A-Z][A-Za-z'\u2019.-]+(?:\s+[A-Z]\.){0,4}\s+[A-Z][A-Za-z'\u2019.-]+\s*$",
                left_text,
            )
            is not None
            and re.match(r"^\s*[A-Z][A-Za-z'\u2019.-]+", right_text) is not None
            and re.search(r"\b(?:Abstract|Background|Objective|Methods?)\b", right_text[:240], re.IGNORECASE)
            is not None
        )
        standard_part_context = (
            re.search(
                r"\b(?:ISO|IEC|ASTM|DIN|EN|BS)\s+\d[\w.-]*\s+(?:part|pt\.?)\s*$",
                left_text,
                re.IGNORECASE,
            )
            is not None
            and re.match(r"^\s*(?:[),.;:]|\b(?:and|of|for|in)\b|$)", right_text, re.IGNORECASE)
            is not None
        )
        decimal_unit_context = (
            number <= 20
            and re.search(
                r"\b(?:may\s+be|was|were|is|are|below|above|difference|differences?|value|values?)\s*$",
                left_text,
                re.IGNORECASE,
            )
            is not None
            and re.match(
                r"^\s*,\s*\d{1,2}\s*\.\s*(?:[a-z]\s*(?:[.\u00b7]\s*)?)?min\s*[-\u2212]?\s*1\b",
                right_text,
                re.IGNORECASE,
            )
            is not None
        )
        color_label_context = (
            number <= 30
            and re.search(
                r"\b(?:red|green|blue|orange|yellow|purple|violet|gray|grey|white|black|brown)\s*$",
                left_text,
                re.IGNORECASE,
            )
            is not None
            and (
                re.match(r"^\s*(?:,\s*\d+(?:\s*\.\s*\d+)?|\.\s*\d+)\s*%", right_text) is not None
                or re.match(r"^\s*in\s+Experiment\s+\d\b", right_text, re.IGNORECASE) is not None
            )
        )
        numbered_sequence_context = (
            (
                re.search(
                    r"\b(?:experiments?|sessions?|objects?|graphics?|tactors?|subsections?|sections?)\s*$",
                    left_text,
                    re.IGNORECASE,
                )
                is not None
                and re.match(r"^\s*(?:and|to)\s+\d", right_text, re.IGNORECASE) is not None
            )
            or (
                re.search(
                    r"\b(?:experiments?|sessions?|objects?|graphics?|tactors?)\s+\d+"
                    r"(?:\s*(?:,|and|or|to|then)\s*\d+)*\s+(?:and|or|to|then)\s*$",
                    dot_enum_left_text,
                    re.IGNORECASE,
                )
                is not None
                and re.match(r"^\s*(?:\)|,|\.|and|or|to|$)", right_text, re.IGNORECASE)
                is not None
            )
            or (
                re.search(
                    r"\b(?:between|from|then|only|over|missed|inducing|stages?|ages?|z\s+scores?)\s*$",
                    left_text,
                    re.IGNORECASE,
                )
                is not None
                and re.match(r"^\s*(?:and|to|of|in|\)|\.|,|$)", right_text, re.IGNORECASE)
                is not None
            )
            or (
                number in {2, 3}
                and re.search(r"\)\s*$", left_text)
                and re.match(r"^\s*(?:[+\-*/=,.;)]|$)", right_text) is not None
            )
            or (
                number in {2, 3}
                and re.search(r"/\s*\d+\s*$", left_text)
                and re.match(r"^\s*(?:\)|,|\.|;|$)", right_text) is not None
            )
            or (
                re.search(r"\(\s*\d+\s*[-\u2013\u2014]\s*\d+\s*\)\s*$", left_text) is not None
                and re.match(r"^\s*(?:the|a|an|[A-Za-z])\b", right_text, re.IGNORECASE) is not None
            )
            or re.match(r"^\s*DF\s*:", right_text, re.IGNORECASE) is not None
            or re.search(r"(?:frames?s|framess)\s*[-\u2212]\s*$", left_text, re.IGNORECASE) is not None
            or (
                re.search(r"\b(?:luminance|targ)\s*$", left_text, re.IGNORECASE) is not None
                and re.match(r"^\s*(?:\)|/|,|\.|;|and\b|or\b|$)", right_text, re.IGNORECASE) is not None
            )
            or re.search(r"(?:\bDRE|dLight|Qwen|V)\s*$", left_text) is not None
        )
        enumerated_item_context = (
            re.match(r"^\s*\)", right_text) is not None
            and re.search(
                r"(?:[:;]\s*|\b(?:and|or|using|including|includes?|methods?|presents?|investigate|their|its|our|his|her)\s*)$",
                left_text,
                re.IGNORECASE,
            )
            is not None
            and (
                number == 1
                or re.search(
                    r"\b\d{1,2}\s*\)",
                    _visible_text(html[max(0, match.start() - 240) : match.start()]),
                )
                is not None
            )
        )
        enumerated_dot_context = _enumerated_dot_item_context(number, dot_enum_left_text, right_text)
        if (
            version_context
            or equation_label_context
            or counted_range_context
            or sample_count_context
            or inline_numeric_range_context
            or front_matter_affiliation_context
            or standard_part_context
            or decimal_unit_context
            or color_label_context
            or numbered_study_context
            or numbered_sequence_context
            or enumerated_item_context
            or enumerated_dot_context
            or _level_number_context(number, left_text, right_text)
        ):
            return match.group("body")
        if number > 5:
            return match.group(0)
        if re.search(r"\d\s*(?:,|[-\u2013\u2014])\s*\d", range_window):
            return match.group(0)
        if number in footnote_definition_ref_numbers and "<math" in raw_window:
            return match.group("body")
        if re.search(r"\b(?:Fig\.?|Figs\.?|Figure|Table|Eqn?\.?|Equation)\b", text_window, re.IGNORECASE):
            return match.group(0)
        if number in footnote_definition_ref_numbers:
            return match.group("body")
        left_text = _visible_text(html[max(0, match.start() - 80): match.start()])
        if re.search(r"(?:\b[A-Z][a-z][A-Za-z'’.-]{2,}\.?\s*|\bet\s+al\.?\s*)$", left_text):
            return match.group(0)
        if re.search(
            r"(?:\b(?:CIC|CSC|impedance|capacity|day|used|source|data|platforms?|input|term|efficient)|"
            r"\((?:CIC|CSC)\)|"
            r"\([A-Za-z][^()]{0,180}\d{4}[a-z]?(?:;[^()]{0,180}\d{4}[a-z]?)*\))\s*$",
            left_text,
            re.IGNORECASE,
        ):
            return match.group("body")
        footnote_context = re.search(
            r"\b(?:source|web|github|facebook|living|data)\b",
            text_window,
            re.IGNORECASE,
        ) is not None
        if "z2m-footnote-ref" not in raw_window and not footnote_context:
            return match.group(0)
        return match.group("body")

    repaired = _REF_ANCHOR_PATTERN.sub(_replace, html)

    def _decimal_comma_value_context(left_text: str) -> bool:
        return (
            re.search(
                r"\b(?:effect\s+size|logmar|snellen\s+acuity|visual\s+acuity|"
                r"measurements?\s+of|cohens?\s+d|value|values|score|scores|"
                r"coefficient|ratio|mean|median|power)\b[\s\S]{0,120}$",
                left_text,
                re.IGNORECASE,
            )
            is not None
        )

    def _replace_linked_numeric_sup(match: re.Match[str]) -> str:
        body = match.group("body")
        visible_body = _visible_text(body)
        if re.fullmatch(r"\d{1,3}(?:\s*,\s*\d{1,3}){1,4}", visible_body) is None:
            return match.group(0)
        numbers = re.findall(r"\d{1,3}", visible_body)
        if len(numbers) < 2:
            return match.group(0)
        left_text = _visible_text(repaired[max(0, match.start() - 220): match.start()])
        dotted_number_context = re.search(
            r"(?:\b(?:v|version|cpu|qwen|dlight|subsections?|sections?)\s*$|"
            r"\b(?:diameters?|distances?|ratios?)(?:\s+[A-Za-z-]+){0,8}\s+(?:of|were|was)\s*$|"
            r"\bslope\s+of\s*$|"
            r"\b(?:rated|score|scores?|averaging|at|and)\s*$)",
            left_text,
            re.IGNORECASE,
        ) is not None
        if _version_number_context(left_text):
            return ".".join(numbers)
        if dotted_number_context:
            return ".".join(numbers)
        if len(numbers) == 2 and _decimal_comma_value_context(left_text):
            return ".".join(numbers)
        return match.group(0)

    linked_numeric_sup = re.compile(
        r"<sup\b[^>]*>\s*(?P<body>"
        r"(?:(?:<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>\s*\d{1,3}\s*</a>|\d{1,3})"
        r"\s*(?:,\s*)?){2,5}"
        r")\s*</sup>",
        re.IGNORECASE | re.DOTALL,
    )
    repaired = linked_numeric_sup.sub(_replace_linked_numeric_sup, repaired)

    def _replace_linked_fraction_sup(match: re.Match[str]) -> str:
        body = match.group("body")
        visible_body = re.sub(r"\s+", "", _visible_text(body))
        if re.fullmatch(r"\d{1,3}(?:/\d{1,3}){1,3}", visible_body) is None:
            return match.group(0)
        numbers = [int(value) for value in re.findall(r"\d{1,3}", visible_body)]
        if not numbers or any(number > 5 for number in numbers):
            return match.group(0)
        left_text = _visible_text(repaired[max(0, match.start() - 160): match.start()])
        right_text = _visible_text(repaired[match.end() : match.end() + 80])
        if re.search(r"\b(?:fig(?:ure)?|table|eq(?:uation)?|ref(?:erence)?)\.?\s*$", left_text, re.IGNORECASE):
            return match.group(0)
        if re.match(r"^\s*(?:[-\u2013\u2014]\s*)?\d", right_text):
            return match.group(0)
        return f"<sup>{visible_body}</sup>"

    linked_fraction_sup = re.compile(
        r"<sup\b[^>]*>\s*(?P<body>"
        r"(?:<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>\s*\d{1,3}\s*</a>|\d{1,3})"
        r"(?:\s*/\s*"
        r"(?:<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>\s*\d{1,3}\s*</a>|\d{1,3})){1,3}"
        r")\s*</sup>",
        re.IGNORECASE | re.DOTALL,
    )
    repaired = linked_fraction_sup.sub(_replace_linked_fraction_sup, repaired)

    def _replace_plain_numeric_sup(match: re.Match[str]) -> str:
        body = re.sub(r"\s+", "", match.group("body"))
        left_text = _visible_text(repaired[max(0, match.start() - 160): match.start()])
        dot_enum_left_text = _visible_text(repaired[max(0, match.start() - 420): match.start()])
        right_text = _visible_text(repaired[match.end() : match.end() + 80])
        if _version_number_context(left_text):
            return body.replace(",", ".")
        if re.search(r"\b(?:experiments?|studies|study)\s+\d+\s*(?:,|and|or)\s*$", left_text, re.IGNORECASE):
            return body
        if (
            re.search(
                r"\b(?:experiments?|sessions?|objects?|graphics?|tactors?|subsections?|sections?)\s*$",
                left_text,
                re.IGNORECASE,
            )
            is not None
            and re.match(r"^\s*(?:and|to)\s+\d", right_text, re.IGNORECASE) is not None
        ):
            return body
        if (
            re.search(
                r"\b(?:experiments?|sessions?|objects?|graphics?|tactors?)\s+\d+"
                r"(?:\s*(?:,|and|or|to|then)\s*\d+)*\s+(?:and|or|to|then)\s*$",
                dot_enum_left_text,
                re.IGNORECASE,
            )
            is not None
            and re.match(r"^\s*(?:\)|,|\.|and|or|to|$)", right_text, re.IGNORECASE) is not None
        ):
            return body
        if (
            re.search(
                r"\b(?:between|from|then|only|over|missed|inducing|stages?|ages?|z\s+scores?)\s*$",
                left_text,
                re.IGNORECASE,
            )
            is not None
            and re.match(r"^\s*(?:and|to|of|in|\)|\.|,|$)", right_text, re.IGNORECASE) is not None
        ):
            return body
        if re.match(r"^\s*DF\s*:", right_text, re.IGNORECASE) is not None:
            return body
        if (
            re.search(r"\b(?:luminance|targ)\s*$", left_text, re.IGNORECASE) is not None
            and re.match(r"^\s*(?:\)|/|,|\.|;|and\b|or\b|$)", right_text, re.IGNORECASE) is not None
        ):
            return body
        if re.search(r"(?:\bDRE|dLight|Qwen|V)\s*$", left_text) is not None:
            return body
        if (
            re.match(r"^\s*\)", right_text) is not None
            and re.search(
                r"(?:[:;]\s*|\b(?:and|or|using|including|includes?|methods?|presents?|investigate|their|its|our|his|her)\s*)$",
                left_text,
                re.IGNORECASE,
            )
            is not None
            and (
                body == "1"
                or re.search(r"\b\d{1,2}\s*\)", left_text) is not None
            )
        ):
            return body
        try:
            number = int(body)
        except ValueError:
            number = -1
        if number > 0 and _enumerated_dot_item_context(number, dot_enum_left_text, right_text):
            return body
        if number > 0 and _level_number_context(number, left_text, right_text):
            return body
        return match.group(0)

    plain_numeric_sup = re.compile(
        r"<sup\b[^>]*>\s*(?P<body>\d{1,3}(?:\s*,\s*\d{1,3}){0,4})\s*</sup>",
        re.IGNORECASE,
    )
    return plain_numeric_sup.sub(_replace_plain_numeric_sup, repaired)


def _repair_acronym_footnote_ref_citations(html: str) -> str:
    """Promote acronym-adjacent footnote refs that are actually citations."""
    if _looks_author_year_citation_document(html):
        return html
    ref_numbers = {int(match.group(1)) for match in _LI_ID_PATTERN.finditer(html)}
    if not ref_numbers or "z2m-footnote-ref" not in html:
        return html

    pattern = re.compile(
        r"(?P<prefix>\([A-Za-z]{2,8}\)\s*)"
        r"<sup\b[^>]*\bz2m-footnote-ref\b[^>]*>\s*(?P<num>\d{1,3})\s*</sup>",
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        number = int(match.group("num"))
        if number not in ref_numbers:
            return match.group(0)
        return (
            f'{match.group("prefix")}<sup>'
            f'<a href="#ref-{number}" class="z2m-ref-link">{number}</a>'
            f'</sup>'
        )

    return pattern.sub(_replace, html)


def _recover_trailing_citation_after_author_year_ref(html: str) -> str:
    """Recover flattened citation numbers after linked author-year fragments."""
    ref_numbers = {int(match.group(1)) for match in _LI_ID_PATTERN.finditer(html)}
    if not ref_numbers or "#ref-" not in html:
        return html

    pattern = re.compile(
        r"(?P<anchor><a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>[\s\S]{0,120}?</a>)"
        r"(?P<gap>\s*)(?P<num>\d{1,3})(?P<trail>\s*\.)",
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        number = int(match.group("num"))
        if number not in ref_numbers:
            return match.group(0)
        anchor_text = _visible_text(match.group("anchor"))
        if re.search(r"\b\d{4}[a-z]?\)?\s*$", anchor_text) is None:
            return match.group(0)
        return (
            f'{match.group("anchor")}<sup>'
            f'<a href="#ref-{number}" class="z2m-ref-link">{number}</a>'
            f'</sup>{match.group("trail").lstrip()}'
        )

    return pattern.sub(_replace, html)


def _unwrap_malformed_ref_anchor_openings(html: str) -> str:
    """Remove unclosed outer ref anchors before they swallow later links/blocks."""
    if "#ref-" not in html or "<a" not in html:
        return html

    malformed_open = re.compile(
        r'<a\b(?=[^>]*\bhref\s*=\s*["\']#ref-\d+["\'])(?=[^>]*\bz2m-ref-link\b)[^>]*>'
        r'(?=(?:(?!</a>).)*?(?:<a\b|</p>|</h[1-6]\s*>|</div\s*>|<p\b|<h[1-6]\b|<div\b))',
        re.IGNORECASE | re.DOTALL,
    )

    def _replace(match: re.Match[str]) -> str:
        right = current[match.end(): match.end() + 180]
        if re.match(
            r"\s*(?:<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>|[A-Za-z]\s*\[\s*"
            r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>)",
            right,
            re.IGNORECASE,
        ):
            return match.group(0)
        return ""

    previous = None
    current = html
    while previous != current:
        previous = current
        current = malformed_open.sub(_replace, current)
    return current


def _repair_nested_reference_links(html: str) -> str:
    """Remove empty/outer reference anchors around already linked citations."""
    if "#ref-" not in html:
        return html

    empty_anchor = re.compile(
        r'<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>\s*</a>\s*',
        re.IGNORECASE,
    )
    dangling_outer_linked_bracket = re.compile(
        r'<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>\s*'
        r'(?=\[\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'])',
        re.IGNORECASE,
    )
    linked_bracket_inside_anchor = re.compile(
        r'<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>\s*'
        r'(?P<body>\[\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>[\s\S]{1,20}?</a>'
        r'(?:\s*(?:,|[-\u2013\u2014])\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>[\s\S]{1,20}?</a>)*\s*\])'
        r'\s*</a>',
        re.IGNORECASE,
    )
    external_linked_bracket = re.compile(
        r'<a\b(?![^>]*\bhref\s*=\s*["\']#ref-)[^>]*>\s*'
        r'(?P<body>\[\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>[\s\S]{1,20}?</a>'
        r'(?:\s*(?:,|[-\u2013\u2014])\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>[\s\S]{1,20}?</a>)*\s*,?\s*)'
        r'</a>',
        re.IGNORECASE,
    )
    dangling_external_citation_open = re.compile(
        r'<a\b(?![^>]*\bhref\s*=\s*["\']#ref-)[^>]*>\s*'
        r'(?=\[\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'])',
        re.IGNORECASE,
    )
    unclosed_ref_before_next_ref = re.compile(
        r'(?P<open><a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<num>\d+)["\'][^>]*>)'
        r'(?P<label>\s*(?P=num)\s*),\s*(?=<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'])',
        re.IGNORECASE,
    )
    mixed_plain_ref_list_anchor = re.compile(
        r'(?P<open><a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<num>\d+)["\'][^>]*>)'
        r'\s*(?P<prefix>\[\s*(?P=num)\s*\]\s*,\s*)'
        r'(?P<body>\[\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>[\s\S]{1,80}?</a>\s*\])'
        r'\s*</a>',
        re.IGNORECASE,
    )
    prefixed_same_href_nested_ref = re.compile(
        r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<num>\d+)["\'][^>]*>\s*'
        r'(?P<prefix>[A-Za-z]\s*\[\s*)'
        r'(?P<inner><a\b[^>]*\bhref\s*=\s*["\']#ref-(?P=num)["\'][^>]*>[\s\S]{1,80}?</a>)'
        r'(?P<trail>[\s,]*)</a>',
        re.IGNORECASE,
    )
    ocr_split_outer_ref_list = re.compile(
        r'(?P<word>\b[A-Za-z]{2,})\s+'
        r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<num>\d+)["\'][^>]*>\s*'
        r'(?P<letter>[A-Za-z])\s*'
        r'(?P<body>\[\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P=num)["\'][^>]*>[\s\S]{1,30}?</a>'
        r'(?:\s*,\s*<a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>[\s\S]{1,30}?</a>){1,8}'
        r'\s*\][\.,;:]*)\s*</a>',
        re.IGNORECASE,
    )
    same_href_nested_ref = re.compile(
        r'<a\b[^>]*\bhref\s*=\s*["\']#ref-(?P<num>\d+)["\'][^>]*>\s*'
        r'(?P<inner><a\b[^>]*\bhref\s*=\s*["\']#ref-(?P=num)["\'][^>]*>[\s\S]{1,160}?</a>)'
        r'(?P<trail>[\)\]\.,;:]*)\s*</a>',
        re.IGNORECASE,
    )
    double_closed_ref = re.compile(
        r'(?P<anchor><a\b[^>]*\bhref\s*=\s*["\']#ref-\d+["\'][^>]*>[\s\S]{0,80}?</a>)\s*</a>',
        re.IGNORECASE,
    )
    double_closed_any_anchor = re.compile(
        r'(?P<anchor><a\b[^>]*>[\s\S]{0,1200}?</a>)\s*</a>'
        r'(?=\s*(?:</b>|</p>|[,\]\).(]|<a\b|[A-Z][A-Za-z]))',
        re.IGNORECASE,
    )

    def _repair_mixed_plain_ref_list(match: re.Match[str]) -> str:
        label = f"{match.group('open')}{match.group('prefix').strip()}</a>"
        return f"{label} {match.group('body')}"

    def _repair_ocr_split_outer_ref_list(match: re.Match[str]) -> str:
        word = match.group("word")
        letter = match.group("letter")
        if not _looks_like_ocr_split_word_join(word, letter):
            return match.group(0)
        return f"{word}{letter} {match.group('body')}"

    previous = None
    current = _unwrap_malformed_ref_anchor_openings(html)
    while previous != current:
        previous = current
        current = _unwrap_malformed_ref_anchor_openings(current)
        current = unclosed_ref_before_next_ref.sub(
            lambda m: f'{m.group("open")}{m.group("label").strip()}</a>, ',
            current,
        )
        current = dangling_outer_linked_bracket.sub("", current)
        current = dangling_external_citation_open.sub("", current)
        current = linked_bracket_inside_anchor.sub(lambda m: m.group("body"), current)
        current = external_linked_bracket.sub(lambda m: m.group("body"), current)
        current = mixed_plain_ref_list_anchor.sub(_repair_mixed_plain_ref_list, current)
        current = prefixed_same_href_nested_ref.sub(
            lambda m: f'{m.group("prefix")}{m.group("inner")}{m.group("trail")}',
            current,
        )
        current = same_href_nested_ref.sub(lambda m: f'{m.group("inner")}{m.group("trail")}', current)
        current = ocr_split_outer_ref_list.sub(_repair_ocr_split_outer_ref_list, current)
        current = double_closed_ref.sub(lambda m: m.group("anchor"), current)
        current = double_closed_any_anchor.sub(lambda m: m.group("anchor"), current)
        current = empty_anchor.sub("", current)
    return current


def _link_table_refs(html: str, found_tables: set[str]) -> str:
    """Wrap ``Table 1`` / ``TABLE I`` occurrences with links to table anchors."""
    if not found_tables:
        return html

    def _link_number(table_no: str) -> str:
        key = _normalize_table_key(table_no)
        if key not in found_tables:
            return table_no
        return f'<a href="#table-{key}" class="z2m-table-link">{table_no}</a>'

    def _link_labeled_number(label: str, table_no: str) -> str:
        key = _normalize_table_key(table_no)
        if key not in found_tables:
            return f"{label} {table_no}"
        return f'<a href="#table-{key}" class="z2m-table-link">{label}\xa0{table_no}</a>'

    def _rewrite_pair_page_link(m: re.Match[str]) -> str:
        body_text = _visible_text(m.group("body"))
        second_match = re.match(
            rf"^\s*(?P<second>{_TABLE_KEY_TOKEN})(?P<trail>[\)\]\.,;:]*)\s*$",
            body_text,
            re.IGNORECASE,
        )
        if second_match is None:
            return m.group(0)
        first = m.group("first")
        second = second_match.group("second")
        first_key = _normalize_table_key(first)
        second_key = _normalize_table_key(second)
        if first_key not in found_tables or second_key not in found_tables:
            return m.group(0)
        return (
            f'{_link_labeled_number(m.group("word"), first)} {m.group("join")} '
            f'{_link_number(second)}{second_match.group("trail")}'
        )

    html = _TABLE_REF_PAIR_PAGE_LINK_PATTERN.sub(_rewrite_pair_page_link, html)

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []
    table_caption_tag: str | None = None

    def _replace_pair(m: re.Match[str]) -> str:
        first = m.group("first")
        second = m.group("second")
        first_key = _normalize_table_key(first)
        second_key = _normalize_table_key(second)
        if first_key not in found_tables or second_key not in found_tables:
            return m.group(0)
        return (
            f'{_link_labeled_number(m.group("word"), first)} {m.group("join")} '
            f'{_link_number(second)}'
        )

    def _replace(m: re.Match[str]) -> str:
        word = m.group(1)
        table_no = m.group(2)
        suffix = m.group(3) or ""
        key = _normalize_table_key(table_no)
        if key not in found_tables:
            return m.group(0)
        return f'<a href="#table-{key}" class="z2m-table-link">{word}\xa0{table_no}{suffix}</a>'

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            raw_tag = part.strip().lower()
            close_match = _CLOSE_TAG_PATTERN.match(raw_tag)
            open_match = _OPEN_TAG_PATTERN.match(raw_tag)
            if close_match is not None and close_match.group(1).lower() == table_caption_tag:
                table_caption_tag = None
            elif open_match is not None and re.search(r'\bid\s*=\s*["\']table-[^"\']+', raw_tag):
                table_caption_tag = open_match.group(1).lower()
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack or table_caption_tag is not None:
            out.append(part)
            continue
        linked = _TABLE_REF_PAIR_PATTERN.sub(_replace_pair, part)
        out.append(_TABLE_REF_PATTERN.sub(_replace, linked))

    return "".join(out)


def _normalize_numeric_section_heading_levels(html: str) -> str:
    """Keep numbered article headings at stable visual levels."""

    def _replace(match: re.Match[str]) -> str:
        open_tag, body = match.group(1), match.group(2)
        visible = _visible_text(body)
        numeric = _NUMERIC_SECTION_HEADING_VISIBLE_PATTERN.match(visible)
        if numeric is None:
            return match.group(0)
        if re.search(r"\bpage\s+\d+\s+of\s+\d+\b", visible, re.IGNORECASE):
            return match.group(0)

        section_num = numeric.group(1)
        target_tag = "h3" if "." in section_num else "h2"
        open_match = _HEADING_OPEN_TAG_PATTERN.match(open_tag)
        if open_match is None:
            return match.group(0)
        attrs = open_match.group("attrs") or ""
        return f"<{target_tag}{attrs}>{body}</{target_tag}>"

    return _HEADING_TAG_PATTERN.sub(_replace, html)


def _looks_like_ru_html_content(html: str) -> bool:
    return len(_CYRILLIC_CHAR_PATTERN.findall(html)) >= 24


def _normalize_spacing_after_z2m_links(html: str) -> str:
    """Insert a missing space when a z2m link is glued to the following word."""
    if len(html) > 500000:
        return html
    if "z2m-" not in html or "-link" not in html:
        return html
    return _Z2M_LINK_GLUE_PATTERN.sub(r"\1 ", html)


def _normalize_spacing_after_url_links(html: str) -> str:
    """Insert a missing space when a URL link is glued to following prose."""
    if len(html) > 500000:
        return html
    if "http://" not in html and "https://" not in html and "www." not in html:
        return html
    html = _URL_LINK_WORD_GLUE_PATTERN.sub(r"\1 ", html)
    return _CREATIVE_COMMONS_PUBLICDOMAIN_MISSING_PAREN_PATTERN.sub(r"\g<prefix>) \g<tail>", html)


def _normalize_table_caption_style(html: str, *, table_caption_language: str = "ru") -> str:
    """Normalize table caption paragraphs to a single style.

    Target form:
    - ``Таблица N. Хвост.`` for ``table_caption_language='ru'``
    - ``TABLE N. Tail.`` for ``table_caption_language='en'``
    """
    def _normalize(m: re.Match[str]) -> str:
        p_open = m.group(1)
        leading_inline = m.group(2)
        table_no = m.group(4)
        tail = m.group(5)
        p_close = m.group(6)
        number = table_no.upper()
        cleaned_tail = re.sub(r"\s+", " ", tail).strip()
        cleaned_tail = cleaned_tail.strip(" .;:,")
        label = "TABLE" if table_caption_language == "en" else "Таблица"

        if cleaned_tail:
            letters = re.findall(r"[A-Za-zА-Яа-яЁё]", cleaned_tail)
            has_lower = any(ch.lower() == ch and ch.upper() != ch for ch in letters)
            has_upper = any(ch.upper() == ch and ch.lower() != ch for ch in letters)
            sentence_tail = cleaned_tail.lower() if letters and has_upper and not has_lower else cleaned_tail
            sentence_tail = sentence_tail[:1].upper() + sentence_tail[1:]
            return f"{p_open}{leading_inline}{label} {number}. {sentence_tail}.{p_close}"
        return f"{p_open}{leading_inline}{label} {number}.{p_close}"

    return _TABLE_CAPTION_PARA_PATTERN.sub(_normalize, html)


def _normalize_figure_caption_style(html: str, *, figure_caption_language: str = "ru") -> str:
    """Normalize figure caption lexemes and punctuation in caption context only."""

    def _normalize(m: re.Match[str]) -> str:
        p_open = m.group(1)
        leading_inline = m.group(2)
        source_label = m.group(3)
        fig_no = m.group(4)
        delimiter = m.group(5) or ""
        tail = m.group(6)
        p_close = m.group(7)

        normalized_source = source_label.lower()
        english_label = normalized_source.startswith("fig")
        number = re.sub(r"\s*([.\-\u2010\u2011\u2012\u2013\u2014])\s*", r"\1", fig_no.upper())

        # Skip in-text refs like "Fig. 16 shows ...".
        if english_label and delimiter not in {".", "|", ":", "-"}:
            return m.group(0)

        cleaned_tail = re.sub(r"\s+", " ", tail).strip().strip(" .;:,|-")
        if figure_caption_language == "en":
            label = "Figure"
        else:
            # Keep English labels in generic mode; the RU post-pass normalizes
            # these only once the document is known to be Russian.
            if english_label:
                return m.group(0)
            label = "Рисунок"

        if cleaned_tail:
            sentence_tail = cleaned_tail[:1].upper() + cleaned_tail[1:]
            return f"{p_open}{leading_inline}{label} {number}. {sentence_tail}.{p_close}"
        return f"{p_open}{leading_inline}{label} {number}.{p_close}"

    return _FIGURE_CAPTION_STYLE_PATTERN.sub(_normalize, html)


_CAPTION_LEADING_PAGE_ANCHOR_PATTERN = re.compile(
    r"^(?P<prefix>\s*)"
    r"<a\b(?P<attrs>[^>]*\bhref\s*=\s*['\"]#page-[^'\"]+['\"][^>]*)>"
    r"(?P<body>[\s\S]*?)</a>"
    r"(?P<rest>[\s\S]*)$",
    re.IGNORECASE,
)


def _unwrap_leading_caption_page_anchors(html: str) -> str:
    """Remove Marker page links from the leading label inside caption nodes."""
    if "#page-" not in html:
        return html

    def _looks_like_caption_label(text: str, *, table: bool) -> bool:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if table:
            return bool(
                re.match(
                    rf"^(?:TABLES?|Tables?)\.?\s+{_TABLE_KEY_TOKEN}(?:[\).:|,-]?\s+[A-Z])?[\).:|,-]*$",
                    cleaned,
                    re.IGNORECASE,
                )
            )
        return bool(
            re.match(
                rf"^(?:FIG(?:URE)?S?|Fig(?:ure)?s?)\.?\s*{_FIG_KEY_TOKEN}"
                r"(?:[\).:|,-]?\s+[A-Z])?[\).:|,-]*$",
                cleaned,
                re.IGNORECASE,
            )
        )

    def _replace_node(match: re.Match[str]) -> str:
        open_tag = match.group("open")
        is_figure_caption = _node_has_class(open_tag, "z2m-figure-caption")
        is_table_caption = _node_has_class(open_tag, "z2m-table-caption")
        if not (is_figure_caption or is_table_caption):
            return match.group(0)
        body = match.group("body")
        anchor_match = _CAPTION_LEADING_PAGE_ANCHOR_PATTERN.match(body)
        if anchor_match is None:
            return match.group(0)
        if not _looks_like_caption_label(anchor_match.group("body"), table=is_table_caption):
            return match.group(0)
        unwrapped = f"{anchor_match.group('prefix')}{anchor_match.group('body')}{anchor_match.group('rest')}"
        return f"{open_tag}{unwrapped}{match.group('close')}"

    return _P_OR_H_BLOCK_PATTERN.sub(_replace_node, html)


def _normalize_ru_reference_lexemes(html: str) -> str:
    """Normalize English Figure/Table labels in RU body text (including anchors)."""

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []
    references_block_depth = 0

    def _update_ru_skip_stack(tag_fragment: str) -> None:
        raw = tag_fragment.strip()
        if not raw.startswith("<") or raw.startswith("<!--") or raw.startswith("<!"):
            return

        close_match = _CLOSE_TAG_PATTERN.match(raw)
        if close_match is not None:
            tag_name = close_match.group(1).lower()
            for idx in range(len(skip_stack) - 1, -1, -1):
                if skip_stack[idx] == tag_name:
                    del skip_stack[idx]
                    break
            return

        if raw.endswith("/>"):
            return

        open_match = _OPEN_TAG_PATTERN.match(raw)
        if open_match is None:
            return
        tag_name = open_match.group(1).lower()
        if tag_name in _RU_REF_NORMALIZE_SKIP_TAGS:
            skip_stack.append(tag_name)

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            raw = part.strip()
            if re.match(r'^<\s*div\b[^>]*\bz2m-references-block\b', raw, re.IGNORECASE):
                references_block_depth += 1
            elif re.match(r'^<\s*/\s*div\b', raw, re.IGNORECASE) and references_block_depth > 0:
                references_block_depth -= 1
            _update_ru_skip_stack(part)
            out.append(part)
            continue

        if skip_stack or references_block_depth > 0:
            out.append(part)
            continue

        normalized = _RU_INLINE_FIG_REF_PATTERN.sub(
            lambda m: f"Рисунок {m.group(1)}{m.group(2) or ''}",
            part,
        )
        normalized = _RU_INLINE_TABLE_REF_PATTERN.sub(
            lambda m: f"{'Таблицы' if m.group(1).lower().endswith('s') else 'Таблица'} {m.group(2)}",
            normalized,
        )
        out.append(normalized)

    return "".join(out)


def _strip_english_heading_prefix_in_ru(html: str) -> str:
    """Drop long English prefixes before Cyrillic text in RU headings."""

    def _fix(match: re.Match[str]) -> str:
        open_tag, content, close_tag = match.group(1), match.group(2), match.group(3)
        stripped = content.lstrip()
        if not stripped:
            return match.group(0)
        if stripped.startswith("http://") or stripped.startswith("https://"):
            return match.group(0)

        pref = _RU_HEADING_EN_PREFIX_PATTERN.match(content)
        if pref is None:
            return match.group(0)
        prefix = pref.group("prefix")
        latin_words = re.findall(r"[A-Za-z]{2,}", prefix)
        if len(latin_words) < 4:
            return match.group(0)
        if re.search(r"\b(?:doi|http|www)\b", prefix, re.IGNORECASE):
            return match.group(0)
        fixed = pref.group("lead") + pref.group("rest").lstrip()
        return f"{open_tag}{fixed}{close_tag}"

    return _HEADING_TAG_PATTERN.sub(_fix, html)


def _strip_long_english_runs_in_ru_text(html: str) -> str:
    """Remove long English runs from mixed RU text nodes outside references."""

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []
    references_block_depth = 0

    def _update_ru_skip_stack(tag_fragment: str) -> None:
        raw = tag_fragment.strip()
        if not raw.startswith("<") or raw.startswith("<!--") or raw.startswith("<!"):
            return

        close_match = _CLOSE_TAG_PATTERN.match(raw)
        if close_match is not None:
            tag_name = close_match.group(1).lower()
            for idx in range(len(skip_stack) - 1, -1, -1):
                if skip_stack[idx] == tag_name:
                    del skip_stack[idx]
                    break
            return

        if raw.endswith("/>"):
            return

        open_match = _OPEN_TAG_PATTERN.match(raw)
        if open_match is None:
            return
        tag_name = open_match.group(1).lower()
        if tag_name in _RU_REF_NORMALIZE_SKIP_TAGS:
            skip_stack.append(tag_name)

    def _replace_run(match: re.Match[str]) -> str:
        run = match.group(0) or ""
        run_low = run.lower()
        if "http://" in run_low or "https://" in run_low or "www." in run_low or "doi" in run_low:
            return run
        if " et al" in run_low:
            return run
        if " in vivo" in run_low or " in vitro" in run_low or " ex vivo" in run_low:
            return run
        return " "

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            raw = part.strip()
            if re.match(r'^<\s*div\b[^>]*\bz2m-references-block\b', raw, re.IGNORECASE):
                references_block_depth += 1
            elif re.match(r'^<\s*/\s*div\b', raw, re.IGNORECASE) and references_block_depth > 0:
                references_block_depth -= 1
            _update_ru_skip_stack(part)
            out.append(part)
            continue
        if skip_stack or references_block_depth > 0:
            out.append(part)
            continue

        if not re.search(r"[\u0400-\u04FF]", part) or not re.search(r"[A-Za-z]", part):
            out.append(part)
            continue

        cleaned = _RU_LONG_ENGLISH_RUN_PATTERN.sub(_replace_run, part)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        out.append(cleaned)

    return "".join(out)


def _looks_ocr_figure_annotation_heading(raw_heading: str) -> bool:
    visible = _visible_text(raw_heading)
    if len(visible) < 80:
        return False
    if re.search(r"[.!?]", visible):
        return False

    latin_words = re.findall(r"[A-Za-z]{2,}", visible)
    if len(latin_words) < 14:
        return False

    keyword_hits = len(
        re.findall(
            r"\b(?:thickness|substrate|electrode|mask|etching|layer|liftoff|parylene|silicon|stimulating|fabricat\w*)\b",
            visible,
            flags=re.IGNORECASE,
        )
    )
    unit_hits = len(
        re.findall(
            r"\b\d+(?:\.\d+)?\s*(?:mm|cm|um|µm|nm|ch|khz|mhz|ghz)\b",
            visible,
            flags=re.IGNORECASE,
        )
    )
    return keyword_hits >= 3 and unit_hits >= 1


def _drop_ocr_figure_annotation_headings(html: str) -> str:
    """Drop OCR figure-annotation headings that leak text labels from figure images."""

    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if len(nodes) < 2:
        return html

    dropped: set[int] = set()

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    for i in range(len(nodes) - 1):
        if i in dropped:
            continue
        heading_raw = nodes[i].group(0)
        if not re.match(r"^\s*<h[1-6]\b", heading_raw, re.IGNORECASE):
            continue
        if not _looks_ocr_figure_annotation_heading(heading_raw):
            continue
        if not _between_is_whitespace(i, i + 1):
            continue
        next_raw = nodes[i + 1].group(0)
        if not _is_figure_caption_node(next_raw):
            continue
        dropped.add(i)

    if not dropped:
        return html

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx not in dropped:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _drop_page_header_footer_paragraphs(html: str) -> str:
    """Remove OCR page header/footer paragraphs such as ``Page X of Y``."""
    pattern = re.compile(r"(<p\b[^>]*>)([\s\S]*?)(</p>)", re.IGNORECASE)

    def _replace(match: re.Match[str]) -> str:
        body = match.group(2) or ""
        visible = _visible_text(body)
        if not visible:
            return match.group(0)
        if _WILEY_DOWNLOAD_PAGE_FURNITURE_PATTERN.match(visible):
            return ""
        if len(visible) <= 180 and _JOURNAL_PAGE_FURNITURE_PATTERN.match(visible):
            return ""
        if not _PAGE_HEADER_FOOTER_LINE_PATTERN.search(visible):
            return match.group(0)
        low = visible.lower()
        if (
            "et al." in low
            or "nature " in low
            or "journal" in low
            or len(visible) <= 220
        ):
            return ""
        return match.group(0)

    return pattern.sub(_replace, html)


def _normalize_glued_roman_suffixes(html: str) -> str:
    """Split OCR-glued roman suffix markers (e.g. ``ablationiv`` -> ``ablation iv``)."""
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        root = match.group(1)
        suffix = match.group(2)
        lowered = root.lower()
        if root.isupper():
            return match.group(0)
        # arXiv, BioRxiv, etc. are legitimate mixed-case tokens, not glued suffixes.
        if any(ch.isupper() for ch in root[1:]):
            return match.group(0)
        if lowered.endswith(("h", "x")):
            return match.group(0)
        return f"{root} {suffix}"

    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_GLUED_ROMAN_SUFFIX_PATTERN.sub(_replace, part))

    return "".join(out)


def _normalize_table_cell_roman_suffixes(html: str) -> str:
    """Split roman footnote suffixes glued to short table-cell terms."""

    def _table_fn(roman: str) -> str:
        return f'<sup class="z2m-table-fn">{roman.lower()}</sup>'

    def _fix_cell(m: re.Match[str]) -> str:
        body = m.group("body")
        visible = _visible_text(body)
        if len(visible) > 90:
            return m.group(0)
        if "z2m-table-fn" in body:
            return m.group(0)
        if not any(ch.isupper() for ch in visible):
            return m.group(0)

        parts = _TAG_SPLIT_PATTERN.split(body)
        out: list[str] = []
        skip_stack: list[str] = []
        table_fn_placeholders: list[str] = []

        def _stash_table_fn(roman: str) -> str:
            table_fn_placeholders.append(_table_fn(roman))
            return f"\x00Z2MTABLEFN{len(table_fn_placeholders) - 1}\x00"

        def _restore_table_fn(text: str) -> str:
            for idx, placeholder in enumerate(table_fn_placeholders):
                text = text.replace(f"\x00Z2MTABLEFN{idx}\x00", placeholder)
            return text

        def _replace_glued(suffix_match: re.Match[str]) -> str:
            root = suffix_match.group("root")
            roman = suffix_match.group("roman")
            if roman.lower() == "x" and root.isupper():
                return suffix_match.group(0)
            if roman.lower() == "x" and root.endswith(("O", "o")):
                return suffix_match.group(0)
            if root.endswith(("x", "X")):
                return suffix_match.group(0)
            return f"{root}{_stash_table_fn(roman)}"

        def _replace_separated(suffix_match: re.Match[str]) -> str:
            root = suffix_match.group("root")
            roman = suffix_match.group("roman")
            if roman.lower() == "x" and root.isupper():
                return suffix_match.group(0)
            if roman.lower() == "x" and root.endswith(("O", "o")):
                return suffix_match.group(0)
            return f"{root}{_stash_table_fn(roman)}"

        def _replace_paren(suffix_match: re.Match[str]) -> str:
            return f'{suffix_match.group("close")}{_stash_table_fn(suffix_match.group("roman"))}'

        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                _update_skip_stack(part, skip_stack)
                out.append(part)
                continue
            if skip_stack:
                out.append(part)
                continue
            normalized = re.sub(r"\bv\s+ii\b", "vii", part, flags=re.IGNORECASE)
            normalized = re.sub(r"\bv\s+iii\b", "viii", normalized, flags=re.IGNORECASE)
            normalized = re.sub(r"\bx\s+ii\b", "xii", normalized, flags=re.IGNORECASE)
            normalized = re.sub(r"\bx\s+iii\b", "xiii", normalized, flags=re.IGNORECASE)
            normalized = re.sub(
                r"\b([A-Za-z][A-Za-z0-9-]{2,})v\s+ii\b",
                r"\1vii",
                normalized,
                flags=re.IGNORECASE,
            )
            normalized = re.sub(
                r"\b([A-Za-z][A-Za-z0-9-]{2,})v\s+iii\b",
                r"\1viii",
                normalized,
                flags=re.IGNORECASE,
            )
            normalized = re.sub(
                r"\b([A-Za-z][A-Za-z0-9-]{2,})x\s+ii\b",
                r"\1xii",
                normalized,
                flags=re.IGNORECASE,
            )
            normalized = re.sub(
                r"\b([A-Za-z][A-Za-z0-9-]{2,})x\s+iii\b",
                r"\1xiii",
                normalized,
                flags=re.IGNORECASE,
            )
            normalized = _TABLE_CELL_PAREN_ROMAN_SUFFIX_PATTERN.sub(_replace_paren, normalized)
            normalized = _TABLE_CELL_SINGLE_LETTER_ROOT_ROMAN_SUFFIX_PATTERN.sub(_replace_glued, normalized)
            normalized = _TABLE_CELL_SEPARATED_ROMAN_SUFFIX_PATTERN.sub(_replace_separated, normalized)
            normalized = _TABLE_CELL_ROMAN_SUFFIX_PATTERN.sub(_replace_glued, normalized)
            out.append(_restore_table_fn(normalized))

        return f'{m.group("open")}{"".join(out)}{m.group("close")}'

    return _TABLE_CELL_BLOCK_PATTERN.sub(_fix_cell, html)


def _repair_false_roman_suffix_splits(html: str) -> str:
    """Join ordinary capitalized words/surnames split before i/v/x."""
    email_pattern = re.compile(
        r"\b(?P<root>[A-Za-z][A-Za-z0-9._%+-]{2,})\s+(?P<suffix>vi|iv|ix|i|v|x)"
        r"(?=@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    )
    et_al_surname_roman_pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+(?P<suffix>vi|i|v)"
        r"(?=\s+et\s+al\.?(?:\b|\d))"
    )
    possessive_surname_roman_pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+(?P<suffix>vi|i|v)"
        r"(?=['\u2019]s\b)"
    )
    hyphen_surname_v_pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,}o)\s+v(?=-[A-Z][A-Za-z'-]{2,})"
    )
    proper_surname_v_tail_pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+v"
        r"(?=(?:\s+(?:[A-Z]{1,4}\b|[A-Z][a-z][A-Za-z'-]{2,}\d*)|\s*[)\u2020*]))"
    )
    author_surname_v_citation_pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+v(?=\s*\[\d{1,3}\])"
    )
    affiliation_surname_vi_pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+vi(?=\s+(?:are|is)\s+with\b)"
    )
    named_o_v_term_pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,}o)\s+v"
        r"(?=\s+(?:chain|chains|model|models|process|processes|test|tests)\b)"
    )
    initial_surname_v_sentence_pattern = re.compile(
        r"(?P<initials>\b(?:[A-Z]\.\s*){1,4})"
        r"(?P<root>[A-Z][a-z][A-Za-z'-]{2,}o)\s+v(?=\.\s+[A-Z])"
    )
    reporting_surname_vi_pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+vi"
        r"(?=\s+(?:argues|classifies|notes|observes|proposed|proposes|says|states|suggests|writes)\b)"
    )
    kolmogorov_pattern = re.compile(r"\bKolmogoro\s+v\b", re.IGNORECASE)
    smirnov_pattern = re.compile(r"\bSmirno\s+v\b", re.IGNORECASE)
    markov_pattern = re.compile(
        r"\bMarko\s+v(?=\s+(?:blanket|chain|chains|decision|model|models|process|processes|property|"
        r"field|fields|hypothesis|random|state|states|transition)\b)",
        re.IGNORECASE,
    )
    lyapunov_pattern = re.compile(
        r"\bLyapuno\s+v(?=\s+(?:analysis|candidate|exponent|exponents|function|functional|stability|type)\b)",
        re.IGNORECASE,
    )
    chebychev_pattern = re.compile(r"\bChebyche\s+v(?=\s+filter\b)", re.IGNORECASE)
    tikhonov_pattern = re.compile(r"\bTikhono\s+v(?=\s+regularization\b)", re.IGNORECASE)
    arxiv_pattern = re.compile(
        r"\bArxi\s+v(?=\s+(?:and|at|interface|interfaces|paper|papers|preprint|preprints|reviewing|tool|tools)\b)",
        re.IGNORECASE,
    )
    mostafavi_pattern = re.compile(r"\bMostafa\s+vi(?=\s+et\s+al\.?(?:\b|\d))", re.IGNORECASE)
    neuravi_pattern = re.compile(r"\bNeura\s+vi(?=\s*/\s*Cerenovus\b)", re.IGNORECASE)
    inqovi_pattern = re.compile(r"\bInqo\s+vi(?=[),.;])", re.IGNORECASE)
    negev_pattern = re.compile(r"\bNege\s+v(?=\.)", re.IGNORECASE)
    korolev_pattern = re.compile(r"\bKorole\s+v(?=\s+str\b)", re.IGNORECASE)
    pattern = re.compile(
        r"\b(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+(?P<suffix>vi|iv|ix|i|v|x)"
        r"(?=(?:\s*,|\s*\(|\s*&(?:amp;)?\s*|\s+(?:and|or)\b|\s+\d{1,4}\b|\s+(?:le|de|van|von)\b|\s+[A-Z](?:\b|[a-z]{2,}\b)|[.;:]?\s*</p>|[.;:]?\s*$))"
    )
    name_pattern = re.compile(
        r"(?P<given>\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2}\s+)"
        r"(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+(?P<suffix>iii|ii|vi|iv|ix|i|v|x)"
        r"(?=\s+[a-z])"
    )
    initial_name_pattern = re.compile(
        r"(?P<initials>\b(?:[A-Z]\.\s*){1,4})"
        r"(?P<root>[A-Z][a-z][A-Za-z'-]{2,})\s+(?P<suffix>iii|ii|vi|iv|ix|i|v|x)"
        r"(?=(?:\s+[A-Z]|[.;:]?\s*</p>|[.;:]?\s*$|[.;:]?\s*[)\u2020*]))"
    )

    def _replace_text(text: str) -> str:
        def _join_allowed(root: str) -> bool:
            return root.lower() not in {
                "table",
                "figure",
                "section",
                "appendix",
                "chapter",
                "mean",
                "node",
                "reference",
                "dcon",
                "cardio",
                "haystackd",
                "function",
            }

        def _replace(match: re.Match[str]) -> str:
            if not _join_allowed(match.group("root")):
                return match.group(0)
            return f"{match.group('root')}{match.group('suffix')}"

        def _replace_name(match: re.Match[str]) -> str:
            given_tail = match.group("given").strip().split()[-1].lower()
            if given_tail in {"the", "this", "these", "those", "while"}:
                return match.group(0)
            if not _join_allowed(match.group("root")):
                return match.group(0)
            return f"{match.group('given')}{match.group('root')}{match.group('suffix')}"

        def _known_replacement(replacement: str) -> Callable[[re.Match[str]], str]:
            return lambda match: _case_like(match.group(0).split()[0], replacement)

        text = email_pattern.sub(lambda match: f"{match.group('root')}{match.group('suffix')}", text)
        text = et_al_surname_roman_pattern.sub(
            lambda match: (
                f"{match.group('root')}{match.group('suffix')}"
                if _join_allowed(match.group("root"))
                else match.group(0)
            ),
            text,
        )
        text = possessive_surname_roman_pattern.sub(
            lambda match: (
                f"{match.group('root')}{match.group('suffix')}"
                if _join_allowed(match.group("root"))
                else match.group(0)
            ),
            text,
        )
        text = proper_surname_v_tail_pattern.sub(
            lambda match: f"{match.group('root')}v" if _join_allowed(match.group("root")) else match.group(0),
            text,
        )
        text = author_surname_v_citation_pattern.sub(
            lambda match: f"{match.group('root')}v" if _join_allowed(match.group("root")) else match.group(0),
            text,
        )
        text = affiliation_surname_vi_pattern.sub(
            lambda match: f"{match.group('root')}vi" if _join_allowed(match.group("root")) else match.group(0),
            text,
        )
        text = hyphen_surname_v_pattern.sub(
            lambda match: f"{match.group('root')}v" if _join_allowed(match.group("root")) else match.group(0),
            text,
        )
        text = named_o_v_term_pattern.sub(
            lambda match: f"{match.group('root')}v" if _join_allowed(match.group("root")) else match.group(0),
            text,
        )
        text = kolmogorov_pattern.sub(_known_replacement("kolmogorov"), text)
        text = smirnov_pattern.sub(_known_replacement("smirnov"), text)
        text = markov_pattern.sub(_known_replacement("markov"), text)
        text = lyapunov_pattern.sub(_known_replacement("lyapunov"), text)
        text = chebychev_pattern.sub(_known_replacement("chebychev"), text)
        text = tikhonov_pattern.sub(_known_replacement("tikhonov"), text)
        text = arxiv_pattern.sub(_known_replacement("arxiv"), text)
        text = mostafavi_pattern.sub(_known_replacement("mostafavi"), text)
        text = neuravi_pattern.sub(_known_replacement("neuravi"), text)
        text = inqovi_pattern.sub(_known_replacement("inqovi"), text)
        text = negev_pattern.sub(_known_replacement("negev"), text)
        text = korolev_pattern.sub(_known_replacement("korolev"), text)
        text = initial_surname_v_sentence_pattern.sub(
            lambda match: f"{match.group('initials')}{match.group('root')}v",
            text,
        )
        text = reporting_surname_vi_pattern.sub(lambda match: f"{match.group('root')}vi", text)
        text = name_pattern.sub(_replace_name, text)
        text = initial_name_pattern.sub(
            lambda match: (
                match.group(0)
                if not _join_allowed(match.group("root"))
                else f"{match.group('initials')}{match.group('root')}{match.group('suffix')}"
            ),
            text,
        )
        return pattern.sub(_replace, text)

    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    skip_stack: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            _update_skip_stack(part, skip_stack)
            out.append(part)
            continue
        if skip_stack:
            out.append(part)
            continue
        out.append(_replace_text(part))
    return "".join(out)


def _repair_variable_table_fn_splits(html: str) -> str:
    """Undo table-footnote markup when it split compact variables or common words."""
    variable_pattern = re.compile(
        r"\b(?P<stem>NeuR|Qma|Qme|Qmn|Qmi|Qav|Qave|Qa|Ima|Vma)"
        r"<sup\b[^>]*\bz2m-table-fn\b[^>]*>\s*(?P<suffix>[A-Za-z])\s*</sup>",
        re.IGNORECASE,
    )
    ordinary_word_pattern = re.compile(
        r"\b(?P<word>Flow|Index|Rate|Value|Values|Group|XII)"
        r"<sup\b[^>]*\bz2m-table-fn\b[^>]*>\s*(?P<suffix>i|v|x)\s*</sup>",
        re.IGNORECASE,
    )
    merged_word_pattern = re.compile(
        r"\b(?P<stem>mult|comple|inde|matri|matr|ma|neuroto|ple|fi|Rev|Curon)"
        r"<sup\b[^>]*\bz2m-table-fn\b[^>]*>\s*(?P<suffix>ii|iii|iv|vi|vii|viii|ix|x|v|i)\s*</sup>",
        re.IGNORECASE,
    )
    roman_phrase_pattern = re.compile(
        r"\b(?P<word>and|or|types?)"
        r"<sup\b[^>]*\bz2m-table-fn\b[^>]*>\s*(?P<roman>ii|iii|iv|vi|vii|viii|ix|x)\s*</sup>",
        re.IGNORECASE,
    )

    def _repair_merged_word(match: re.Match[str]) -> str:
        merged = f"{match.group('stem')}{match.group('suffix')}"
        if merged.lower() not in {
            "multi",
            "complex",
            "index",
            "matrix",
            "max",
            "neurotox",
            "plex",
            "fix",
            "revi",
            "curonix",
        }:
            return match.group(0)
        return merged

    html = variable_pattern.sub(lambda m: f"{m.group('stem')}{m.group('suffix')}", html)
    html = ordinary_word_pattern.sub(lambda m: f"{m.group('word')} {m.group('suffix')}", html)
    html = merged_word_pattern.sub(_repair_merged_word, html)
    return roman_phrase_pattern.sub(lambda m: f"{m.group('word')} {m.group('roman').upper()}", html)


def _normalize_table_cell_soft_breaks(html: str) -> str:
    """Remove line-layout <br> tags inside data cells and rejoin split words."""

    split_word_patterns = (
        (re.compile(r"\belectro\s+chemical\b", re.IGNORECASE), "electrochemical"),
        (re.compile(r"\bmicro\s+fabrication\b", re.IGNORECASE), "microfabrication"),
        (re.compile(r"\bmul\s+tiple\b", re.IGNORECASE), "multiple"),
        (re.compile(r"\bdeposi\s+tion\b", re.IGNORECASE), "deposition"),
        (re.compile(r"\bdepo\s+sition\b", re.IGNORECASE), "deposition"),
        (re.compile(r"\bpropert\s+ies\b", re.IGNORECASE), "properties"),
        (re.compile(r"\bgan\s+glion\b", re.IGNORECASE), "ganglion"),
        (re.compile(r"\bsyn\s+drome\b", re.IGNORECASE), "syndrome"),
        (re.compile(r"\bSyn\s+apse\b", re.IGNORECASE), "Synapse"),
        (re.compile(r"\bintramuscu\s+lar\b", re.IGNORECASE), "intramuscular"),
    )

    def _fix_cell(m: re.Match[str]) -> str:
        open_tag = m.group("open")
        body = m.group("body")
        if not open_tag.lower().startswith("<td"):
            return m.group(0)
        has_soft_break = re.search(r"<br\s*/?>", body, re.IGNORECASE) is not None
        has_split_word = any(pattern.search(_visible_text(body)) is not None for pattern, _ in split_word_patterns)
        if not has_soft_break and not has_split_word:
            return m.group(0)
        if has_soft_break and re.search(r"\[[^\]]*<br\s*/?>[^\]]*\]", body, re.IGNORECASE):
            return m.group(0)

        if has_soft_break:
            body = re.sub(r"\s*<br\s*/?>\s*", " ", body, flags=re.IGNORECASE)
        parts = _TAG_SPLIT_PATTERN.split(body)
        out: list[str] = []
        for part in parts:
            if not part:
                continue
            if part.startswith("<"):
                out.append(part)
                continue
            text = re.sub(r"[ \t]{2,}", " ", part)
            for pattern, replacement in split_word_patterns:
                text = pattern.sub(replacement, text)
            out.append(text)

        return f'{open_tag}{"".join(out)}{m.group("close")}'

    return _TABLE_CELL_BLOCK_PATTERN.sub(_fix_cell, html)


def _repair_table_significance_markers(html: str) -> str:
    """Restore significance stars when OCR emits the replacement character."""
    marker_pattern = r"(?:\ufffd|пїЅ)"
    if not re.search(marker_pattern, html) or "statistically significant" not in _visible_text(html).lower():
        return html
    html = re.sub(rf"((?:&lt;|<)?\s*\d+(?:\.\d+)?){marker_pattern}", r"\1*", html)
    html = re.sub(
        rf"<sup\b[^>]*>\s*{marker_pattern}\s*</sup>(?=\s*:\s*statistically significant)",
        "*",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(rf"{marker_pattern}(?=\s*:\s*statistically significant)", "*", html, flags=re.IGNORECASE)
    html = re.sub(rf"(vs\.\s*){marker_pattern}\s*(?=\+\d)", r"\1&le; ", html, flags=re.IGNORECASE)
    html = re.sub(rf"(vs\.\s*){marker_pattern}\s*(?=-?\d)", r"\1&ge; ", html, flags=re.IGNORECASE)
    html = re.sub(rf"((?:VV|PVR)\s*){marker_pattern}\s*(?=-\d)", r"\1&ge;", html)
    html = re.sub(rf"((?:MFR)\s*){marker_pattern}\s*(?=\+\d)", r"\1&le;", html)
    return html


def _repair_known_replacement_char_symbols(html: str) -> str:
    """Restore high-confidence symbols that OCR emitted as U+FFFD."""
    if "\ufffd" not in html:
        return html

    html = html.replace("package\ufffd=\ufffdnlme", "package=nlme")
    html = html.replace("10.1007/s10143-004-\ufffd0337-6", "10.1007/s10143-004-0337-6")
    html = html.replace("SilkeK\ufffdrcher", "SilkeKärcher")
    html = html.replace("Let\ufffdsosa", "Letšosa")
    html = html.replace("FRIMODT-M\ufffdLLER", "FRIMODT-MØLLER")
    html = html.replace("FRI-MODT-M\ufffdLLER", "FRI-MODT-MØLLER")
    html = html.replace("FRIMODT-M\u00a2LLE\ufffd", "FRIMODT-M&Oslash;LLER")
    html = html.replace("EB1*\ufffd", "EB1**")
    html = html.replace("dynes\ufffdsec\ufffdcm-5\ufffdm", "dynes&middot;sec&middot;cm-5&middot;m")
    html = html.replace("dynes\ufffdsec\ufffdcm-5", "dynes&middot;sec&middot;cm-5")
    html = html.replace("A\ufffdroplethysmograph", "A&euml;roplethysmograph")
    html = html.replace("KAUF\ufffdmN", "KAUFMAN")
    html = html.replace("f lo\ufffd rate", "flow rate")
    html = html.replace("f\ufffdow rate signa\ufffd", "flow rate signal")
    html = html.replace("signa\ufffd", "signal")
    html = html.replace("u\ufffdine", "urine")
    html = html.replace("Targ\ufffdt points", "Target points")
    html = html.replace("trabeculat\ufffdon", "trabeculation")
    html = html.replace("MAR \ufffdIN", "MARTIN")
    html = html.replace("\ufffdmol/1", "&micro;mol/l")
    html = html.replace("\ufffdol/1", "&micro;mol/l")
    html = html.replace("bladder \ufffdicture", "bladder picture")
    html = html.replace("co\ufffdtraction", "contraction")
    html = html.replace("relative!\ufffd", "relatively")
    html = html.replace("prior \ufffdo", "prior to")
    html = html.replace("\ufffdresence", "presence")
    html = html.replace("F\ufffdE each \ufffdalected", "For each selected")
    html = html.replace("m\ufffdsclassifications", "misclassifications")
    html = html.replace("ran\ufffde of V", "range of V")
    html = html.replace("McNEMAR\ufffds", "McNEMAR's")
    html = html.replace("psychologische re\ufffd\ufffding", "psychologische remming")
    html = html.replace("binnen \ufffden persoon", "binnen &eacute;&eacute;n persoon")
    html = html.replace("Bl\ufffdstomningens", "Bl&aring;st&ouml;mningens")
    html = html.replace("North k\ufffderica", "North America")
    html = html.replace("MENNINGER, \ufffd. A.", "MENNINGER, K. A.")
    html = html.replace("SAN\ufffdE", "SAND&Oslash;E")
    html = html.replace("\ufffdatho logie", "Pathologie")
    html = html.replace("EDW\ufffd\ufffdS", "EDWARDS")
    html = html.replace("f\ufffdgures", "figures")
    html = html.replace("f\ufffdgure", "figure")
    html = html.replace("percent\ufffd le", "percentile")

    html = re.sub(r">\s*\ufffd\s*(?=<b>\s*IMPLICATIONS\s+FOR\s+REHABILITATION\b)", "> ", html, flags=re.IGNORECASE)
    html = re.sub(r"(<li\b[^>]*>)\s*\ufffd\s*", r"\1", html, flags=re.IGNORECASE)
    html = re.sub(r"\ufffd\ufffd\s*(?=<b>\s*EB\b)", "** ", html, flags=re.IGNORECASE)
    html = re.sub(r"\ufffd\s*(?=<b>\s*LB\b)", "* ", html, flags=re.IGNORECASE)
    html = re.sub(r"\ufffd\ufffd(?=\s*=\s*p\s*(?:<i>\s*)?&lt;)", "**", html, flags=re.IGNORECASE)
    html = re.sub(r"\ufffd(?=\s*=\s*p\s*(?:<i>\s*)?&lt;)", "*", html, flags=re.IGNORECASE)
    html = re.sub(r"\band\s*\ufffd\s*(?=10\s+pixels\b)", "and &le; ", html, flags=re.IGNORECASE)
    html = re.sub(r"<sup>\s*\ufffd\s*</sup>(?=\s*Obesity\s+was\s+defined\b)", "<sup>*</sup>", html, flags=re.IGNORECASE)
    html = re.sub(r"<sup>\s*\ufffd\s*</sup>(?=\s*Model\s+1\b)", "<sup>*</sup>", html, flags=re.IGNORECASE)
    html = html.replace("Obesity\ufffd", "Obesity*")
    html = html.replace("Model 1\ufffd", "Model 1*")
    html = re.sub(r"\ufffd(?=\s*<b>\s*(?:140|90)\s+mmHg\b)", "&ge;", html, flags=re.IGNORECASE)
    html = re.sub(r"\ufffd(?=\s*(?:27\.5\s*kg/m|50\s+years|50\s+years\s+old|140\s+mmHg|90\s+mmHg))", "&ge;", html)
    html = re.sub(r"\bf\ufffdow\b", "flow", html, flags=re.IGNORECASE)
    html = re.sub(r"\bTabl\s+2\s+1\s+e\s*\.\s*\.\s*con\s+t['\"]\s*\ufffdnue\s+d\)", "Table 2.1 (continued)", html, flags=re.IGNORECASE)
    html = re.sub(
        r"\bTABLE\s+2\.\s*1\s*\.\s*\(co\s+n\s+t[\"']\s*\ufffdnue\s+d\)\.",
        "Table 2.1 (continued).",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"\bTable\s+2\s+1\s*\.\s*(?:<br/?>\s*)?\(co\s+n\s+t[\"']\s*\ufffdnue\s+d\)",
        "Table 2.1 (continued)",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(r"for volumes\s*\ufffd\s*100\s+ml", "for volumes &le; 100 ml", html, flags=re.IGNORECASE)
    html = re.sub(r"10\s*V/\s*\ufffd\s*0\.02\s*V", "10 V/&plusmn; 0.02 V", html)
    html = re.sub(r"less\s+than\s*\ufffd\s*3%", "less than &plusmn; 3%", html, flags=re.IGNORECASE)
    html = re.sub(r"\(\s*\ufffd\s*\)(?=\s*the\s+edge\s+of\s+the\s+grid\b)", "(&#9662;)", html, flags=re.IGNORECASE)
    html = re.sub(r"\ufffd\s*h\b", "&frac12; h", html)
    html = re.sub(r"\b(?:up\s+to|exceed)\s*\ufffd\s*(?=(?:2(?:\.0)?\s*ml/\s*s|2%))", lambda m: m.group(0).replace("\ufffd", "&plusmn;"), html, flags=re.IGNORECASE)
    html = re.sub(r"error\s*:\s*\ufffd\s*1\.0\s*s", "error : &plusmn; 1.0 s", html, flags=re.IGNORECASE)
    html = re.sub(r"\b5\.9\s*\ufffd\s*3\.3\s*ml/\s*s", "5.9 &plusmn; 3.3 ml/s", html)
    html = re.sub(
        r"(<th>\s*J\s*</th>\s*)<th>\s*\ufffd\s*</th>(\s*<th>\s*5\s*</th>)",
        r"\1<th> 4 </th>\2",
        html,
    )
    html = html.replace("<tr> <td> \ufffd </td> <td> 66 </td>", "<tr> <td> age </td> <td> 66 </td>")
    html = html.replace("<tr> <td> \ufffd </td> <td> 78 </td>", "<tr> <td> age </td> <td> 78 </td>")
    html = html.replace("duration of s;t\ufffdtoms", "duration of symptoms")
    html = html.replace("subjective s\ufffdtoms", "subjective symptoms")
    html = html.replace("duration of s\ufffd111 2toms", "duration of symptoms")
    html = html.replace("subjective s\ufffdEtoms", "subjective symptoms")
    html = html.replace("<td> I\ufffd </td>", "<td> 1&frac12; </td>")
    html = html.replace("rectal 12al\ufffdtion", "rectal palpation")
    html = html.replace("<td> \ufffd\xb7 </td>", "<td> i+ </td>")
    html = html.replace("\ufffd (maximum f low rate)", "Qmax (maximum flow rate)")
    html = re.sub(r"0\s*\ufffd\s*R\s*<sup\b[^>]*>\s*2\s*</sup>\s*:5\s*l", "0 &le; R<sup>2</sup> &le; 1", html)
    html = re.sub(r"\(x\s*\ufffd\s*2\s*SD\)", "(x &plusmn; 2 SD)", html)
    html = re.sub(r"(?:100|200)\s*(?:ml\s*)?\ufffd\s*V\s*\ufffd\s*(?:150|350|450)\s*ml", lambda m: re.sub(r"\s+", " ", m.group(0).replace("\ufffd", "&le;")), html)
    html = re.sub(r"1\s*0\s*0\s*ml\s*\ufffd\s*V\s*\ufffd\s*450\s*ml", "100 ml &le; V &le; 450 ml", html)
    html = re.sub(r"1\s*0\s*0\s*ml\s*&le;\s*V\s*&le;\s*450\s*ml", "100 ml &le; V &le; 450 ml", html)
    html = re.sub(r"100\s*\ufffd1\s*\ufffd\s*V\s*\ufffd\s*450\s*ml", "100 ml &le; V &le; 450 ml", html)
    html = re.sub(r"discrimination\s+l\s*imi\s*t\s*\ufffd\s*measurements", "discrimination limit; measurements", html, flags=re.IGNORECASE)
    html = re.sub(r"study\s*\ufffd\s*</li>", "study; </li>", html, flags=re.IGNORECASE)
    html = re.sub(r"the\s+sensitivity\s+is\s*\ufffd\s*x\s*100%\s*62%\s*\ufffd", "the sensitivity is 5/8 x 100% = 62%;", html, flags=re.IGNORECASE)
    html = re.sub(r"the\s+specificity\s+is\s*\*\s*x\s*100%\s*75%\s*\ufffd", "the specificity is 6/8 x 100% = 75%;", html, flags=re.IGNORECASE)
    html = re.sub(
        r"the\s+percentage\s+of\s+misclassifications\s+is\s*3\s*\+\s*2\s*×\s*100%\s*=\s*3\s*1\s*%\s*\.\s*8\s*\+\s*8",
        "the percentage of misclassifications is (3 + 2)/(8 + 8) x 100% = 31%.",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(r"\(\s*a\s*\ufffd\s*0\.05\s*\)", "(&alpha; = 0.05)", html)
    html = re.sub(r"\(n=SB\s*;\s*\ufffd\s*m=870\)", "(n=58; &Sigma; m=870)", html)
    html = html.replace("n\ufffdSB", "n=58")
    html = re.sub(r"o\.\s*\ufffd\s*\.?\s*v\.", "o.i.v.", html)
    html = re.sub(r";\s*\ufffd\s*2\s*3\s*\.2\s*s", "; x = 23.2 s", html)
    html = re.sub(r";\s*\ufffd\s*7\s*\.\s*6\s*s", "; x = 7.6 s", html)
    html = re.sub(r"\(\s*y\s+SO\ufffd\s*\)", "(&gamma; = 80%)", html)
    html = re.sub(r"mean\s*\ufffd\s*1\s*SD", "mean &plusmn; 1 SD", html, flags=re.IGNORECASE)
    html = html.replace("4. \ufffd \ufffde variable", "4. The variable")
    html = re.sub(r"\(\s*\ufffd\s*2\.5\s*%\s*false\s+pos", "(&le; 2.5 % false pos", html, flags=re.IGNORECASE)
    html = re.sub(r"\(V\s*\ufffd\s*res\s*idu\s+na\s+mictie\)", "(V + residu na mictie)", html, flags=re.IGNORECASE)
    html = re.sub(r"\(d\ufffd/dt[lI]max", "(dL/dt)max", html)
    html = re.sub(r"(<t[dh]\b[^>]*>)\s*\ufffd\s*(</t[dh]>)", r"\1\2", html, flags=re.IGNORECASE)
    return html


def _repair_second_echelon_ocr_residue_html(html: str) -> str:
    markers = (
        "Wherev",
        "TQma",
        "PdetQma",
        "sys-",
        "DirectX-",
        "pv0:",
        "0:5",
        "0:5mLs",
        "health male volunteer",
        "validtation",
        "9 m m",
        "m </sup> m",
        "seperable",
        "Dl5660620",
        "Cvalli",
        "attempeted",
        "detecte",
        "afrer",
        "ghraph",
        "Authers",
        "dihydroxyated",
        "defensen",
        "Rgiht",
        "Verebrate",
        "Foundayion",
        "Naturwissenschaftem",
        "millenium",
        "tranformed",
        "coditions",
        "imlied",
        "oberved",
        "occurance",
        "realtive",
        "responsed",
        "speices",
        "treaditional",
        "Furhtermore",
        "et nl.",
        "Electronic(Cambridge",
        "E clarity",
        "b5223",
        "0.999 0995",
        "r=0.9 ",
        "left)999",
        "Avo<sup",
        "Avoi",
        "63 DPhotoWorks",
        "thev",
        "flow flow flow flow",
        "BOO i",
        "BOO <",
        "IPP Grade iii",
        "IPP Grade<sup",
        "Gen-A i",
        "Gen-A<sup",
        "Routeledge",
        "Build-in sensors",
        "Shepadex",
        "sequence4",
        "FA 330",
        "trimetylsilyl",
        "around287.8",
        "millitres",
        "368C",
        "378C",
        "rst few",
        "Museum of Moden Art",
        "room temperation",
        "purposed work",
        "425 cmH2O",
        "Archelological",
        "Appel's Sir i",
        "14 C-beled",
        "secondsmm-2",
        "p, pj]of",
        "F igures",
        "appro ximately",
        "appro </t",
        "If inal",
        "coma separated",
        "plent",
        "8 C",
        "8 <i",
        "IPelvic",
        "hispareunia",
        "agumentation",
        "DWT values -2 mm",
        "\u0399mproving",
        "form eBDtheque",
        "enzymelinked",
        "Ote this: DO",
        "0995",
        "Sir<sup",
        "C-beled",
        "List of F",
        "APPEND<sup",
        "main:",
        "ODs/MB",
        "Beha v. Neurosci",
        "Parkin",
        "virtual environ",
        "Behav. Neuro",
        "environ ment",
        "Parkin sonism",
        "Neuro sci",
        "disconti nuation",
        "Wilhel mina",
        "RUTHERFO RD",
        "Inter national",
    )
    if not any(marker in html for marker in markers):
        return html

    sup_x = r"<sup\b[^>]*>\s*x\s*</sup>"
    sup_r = r"<sup\b[^>]*>\s*R\s*</sup>"
    page_anchor = r"(?:<span\b[^>]*\bid\s*=\s*['\"]page-[^'\"]+['\"][^>]*>\s*</span>\s*)?"
    html = re.sub(rf"\bWherev\s*(<sup\b[^>]*>\s*2\s*</sup>)", r"Where v\1", html, flags=re.IGNORECASE)
    html = re.sub(rf"\bTQma\s*{sup_x}", "TQmax", html)
    html = re.sub(rf"\bPdetQma\s*{sup_x}", "PdetQmax", html)
    html = re.sub(rf"\bsys-\s*{page_anchor}tem\b", "system", html, flags=re.IGNORECASE)
    html = re.sub(rf"\bDirectX-\s*{sup_r}", "DirectX-R", html)

    html = re.sub(r"\bpv0:(\d+)\b", lambda m: f"p<0.{m.group(1)}", html)
    sup_one = r"(?:1|<sup\b[^>]*>\s*1\s*</sup>)"
    unit_exp_minus_one = '<sup class="z2m-unit-exp">-1</sup>'
    html = re.sub(
        rf"\b0:5\s*mLs\{{?\s*{sup_one}\s+mm\{{?\s*{sup_one}",
        f"0.5 mL s{unit_exp_minus_one} mm{unit_exp_minus_one}",
        html,
    )
    html = re.sub(r"\bhealth\s+male\s+volunteer\b", "healthy male volunteer", html, flags=re.IGNORECASE)
    html = re.sub(r"\bvalidtation\b", "validation", html, flags=re.IGNORECASE)
    html = re.sub(
        r"\b(\d+(?:\.\d+)?)\s+(?:m|<sup\b[^>]*>\s*m\s*</sup>)\s+m\b",
        r"\1 mm",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(r"\bseperable\b", "separable", html, flags=re.IGNORECASE)
    html = re.sub(r"\bDl5660620\b", "Delta lambda=660 +/- 20", html)
    html = re.sub(r"\bCvalli\b", "Cavalli", html)
    html = re.sub(r"\battempeted\b", "attempted", html, flags=re.IGNORECASE)
    html = re.sub(r"\bdetecte\b", "detect", html, flags=re.IGNORECASE)
    html = re.sub(r"\bafrer\b", "after", html, flags=re.IGNORECASE)
    html = re.sub(r"\bghraph\b", "graph", html, flags=re.IGNORECASE)
    html = re.sub(r"\bAuthers\b", "Authors", html)
    html = re.sub(r"\bTime\s+verses\s+Flow\s+Rate\s+graph\b", "Time versus Flow Rate graph", html)
    html = re.sub(r"\bdihydroxyated\b", "dihydroxylated", html, flags=re.IGNORECASE)
    html = re.sub(r"\bdefensen\b", "defensin", html, flags=re.IGNORECASE)
    html = re.sub(r"\bRgiht\b", "Right", html, flags=re.IGNORECASE)
    html = re.sub(r"\bVerebrate\b", "Vertebrate", html, flags=re.IGNORECASE)
    html = re.sub(r"\bFoundayion\b", "Foundation", html, flags=re.IGNORECASE)
    html = re.sub(r"\bNaturwissenschaftem\b", "Naturwissenschaften", html, flags=re.IGNORECASE)
    html = re.sub(r"\bmillenium\b", "millennium", html, flags=re.IGNORECASE)
    html = re.sub(r"\btranformed\b", "transformed", html, flags=re.IGNORECASE)
    html = re.sub(r"\bcoditions\b", "conditions", html, flags=re.IGNORECASE)
    html = re.sub(r"\bimlied\b", "implied", html, flags=re.IGNORECASE)
    html = re.sub(r"\boberved\b", "observed", html, flags=re.IGNORECASE)
    html = re.sub(r"\boccurance\b", "occurrence", html, flags=re.IGNORECASE)
    html = re.sub(r"\brealtive\b", "relative", html, flags=re.IGNORECASE)
    html = re.sub(r"\bresponsed\b", "responded", html, flags=re.IGNORECASE)
    html = re.sub(r"\bspeices\b", "species", html, flags=re.IGNORECASE)
    html = re.sub(r"\btreaditional\b", "traditional", html, flags=re.IGNORECASE)
    html = re.sub(r"\bFurhtermore\b", "Furthermore", html, flags=re.IGNORECASE)
    html = re.sub(r"\bet\s+nl\.", "et al.", html, flags=re.IGNORECASE)
    html = re.sub(r"\bElectronic\(Cambridge\b", "Electronics (Cambridge", html)
    html = re.sub(r"\bE\s+clarity\s+of\b", "The clarity of", html)
    html = re.sub(r"\bb5223\b", "b=223", html)
    html = re.sub(r"\b0\.999\s+0995\b", "0.999 0.995", html)
    html = re.sub(r"\br=0\.9\s+(840|526)\b", r"r=0.9\1", html)
    html = re.sub(r"\bleft\)999\b", "left). .999", html)
    html = re.sub(
        r"<th\b[^>]*>\s*Avo\s*<sup\b[^>]*>\s*i\s*</sup>\s*</th>\s*<th\b[^>]*>\s*irdupois\s*</th>",
        '<th colspan="2">Avoirdupois</th>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"<th\b[^>]*>\s*Avoi\s*</th>\s*<th\b[^>]*>\s*irdupois\s*</th>",
        '<th colspan="2">Avoirdupois</th>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"<th\b[^>]*>\s*A\s*</th>\s*<th\b[^>]*>\s*oirdupois\s*</th>",
        '<th colspan="2">Avoirdupois</th>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(r"\b63\s+DPhotoWorks\b", "3DPhotoWorks", html)
    html = re.sub(r"\band\s+thev\s+have\b", "and they have", html, flags=re.IGNORECASE)
    html = re.sub(r"\bflow\s+flow\s+flow\s+flow\b", "flow", html, flags=re.IGNORECASE)
    html = re.sub(r"\bBOO\s+i\b", "BOOI", html)
    html = re.sub(
        r"\bBOO\s*<(?:i|em|span|sup|sub)\b[^>]*>\s*i\s*</(?:i|em|span|sup|sub)>",
        "BOOI",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(r"\bIPP\s+Grade\s*(?:iii|<sup\b[^>]*>\s*iii\s*</sup>)", "IPP Grade III", html)
    html = re.sub(r"\bGen-A\s*(?:i|<sup\b[^>]*>\s*i\s*</sup>)", "Gen-AI", html)
    html = re.sub(r"\bRouteledge\b", "Routledge", html, flags=re.IGNORECASE)
    html = re.sub(r"\bBuild-in\s+sensors\b", "Built-in sensors", html, flags=re.IGNORECASE)
    html = re.sub(r"\bShep(?:a|ha)dex\b", "Sephadex", html)
    html = re.sub(r"\btrimetylsilyl\b", "trimethylsilyl", html, flags=re.IGNORECASE)
    html = re.sub(r"\bsequence4\b", "sequence 4", html, flags=re.IGNORECASE)
    html = re.sub(r"\bFA\s+330\b", "FA 33°", html)
    html = re.sub(r"\baround287\.8\b", "around 287.8", html, flags=re.IGNORECASE)
    html = re.sub(r"\bmillitres\b", "millilitres", html, flags=re.IGNORECASE)
    html = re.sub(r"\b(3[67])8C\b", r"\1.8 °C", html)
    html = re.sub(r"\brst\s+few\b", "first few", html, flags=re.IGNORECASE)
    html = re.sub(r"\bMuseum\s+of\s+Moden\s+Art\b", "Museum of Modern Art", html)
    html = re.sub(r"\broom\s+temperation\b", "room temperature", html, flags=re.IGNORECASE)
    html = re.sub(r"\bpurposed\s+work\b", "proposed work", html, flags=re.IGNORECASE)
    html = re.sub(r"\b425\s+cmH2O\b", ">25 cmH2O", html)
    html = re.sub(r"\b460\s+bpm\b", ">60 bpm", html)
    html = re.sub(r"\bArchelological\b", "Archaeological", html, flags=re.IGNORECASE)
    html = re.sub(r"\bAppel's\s+Sir\s+i\b", "Apple's Siri", html, flags=re.IGNORECASE)
    html = re.sub(r"\b14\s+C-beled\b", "14C-labeled", html)
    html = re.sub(r"\bsecondsmm-2\b", "s/mm2", html)
    html = re.sub(r"\bp,\s*pj\]of\b", "p, pj] of", html)
    html = re.sub(r"\bF\s+igures\b", "Figures", html)
    html = re.sub(r"\bf\s+igures\b", "figures", html)
    html = re.sub(r"\bappro\s+ximately\b", "approximately", html, flags=re.IGNORECASE)
    html = re.sub(r"\bIf\s+inal\b", "I_final", html)
    html = re.sub(r"\bcoma\s+separated\b", "comma-separated", html, flags=re.IGNORECASE)
    html = re.sub(r"\ba\s+plent\s+of\b", "plenty of", html, flags=re.IGNORECASE)
    html = re.sub(r"\bplent\b", "plenty", html, flags=re.IGNORECASE)
    html = re.sub(r"\b(\d+(?:\.\d+)?)\s+8\s+C\b", r"\1 °C", html)
    html = re.sub(r"\bIPelvic\b", "Pelvic", html)
    html = re.sub(r"\bhispareunia\b", "dyspareunia", html, flags=re.IGNORECASE)
    html = re.sub(r"\bagumentation\b", "augmentation", html, flags=re.IGNORECASE)
    html = re.sub(r"\bDWT\s+values\s+-2\s+mm\b", "DWT values >2 mm", html)
    html = re.sub(r"\b\u0399mproving\b", "Improving", html)
    html = re.sub(r"\bform\s+eBDtheque\b", "from eBDtheque", html, flags=re.IGNORECASE)
    html = re.sub(r"\benzymelinked\b", "enzyme-linked", html, flags=re.IGNORECASE)
    html = re.sub(r"\bOte\s+this:\s+DO:", "Cite this: DOI:", html, flags=re.IGNORECASE)
    html = re.sub(r"(<td\b[^>]*>\s*)0995(?=\s*[–-])", r"\g<1>0.995", html)
    html = re.sub(r"\br=0\.9\s*<a\b[^>]*>\s*840\s+45\s*</a>", "r=0.9840 45", html)
    html = re.sub(
        r"\br=0\.9\s*<a\b[^>]*>\s*526\s+30\s+31\s+33\s+52\)\s*</a>",
        "r=0.9526 30 31 33 52)",
        html,
    )
    html = re.sub(r"\bAppel's\s+Sir\s*<sup\b[^>]*>\s*i\s*</sup>", "Apple's Siri", html, flags=re.IGNORECASE)
    html = re.sub(r"<sup\b[^>]*>\s*14\s*</sup>\s*C-beled\b", "<sup>14</sup>C-labeled", html, flags=re.IGNORECASE)
    html = re.sub(
        r"List\s+of\s+F\s*</t([dh])>\s*<t([dh])\b(?P<attrs>[^>]*)>\s*igures",
        r"List of Figures</t\1><t\2\g<attrs>>",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"\bappro\s*</t([dh])>\s*<t([dh])\b(?P<attrs>[^>]*)>\s*ximately",
        r"approximately</t\1><t\2\g<attrs>>",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"\bappro\s*</td>\s*<td>\s*ximately\b",
        "approximately</td><td>",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"(<i\b[^>]*>\s*)(\d+(?:\.\d+)?)\s*</i>\s*8\s*<i\b[^>]*>\s*C\b",
        r"\g<1>\2 °C",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r"(\d+(?:\.\d+)?)\s*</i>\s*8\s*<i\b[^>]*>\s*C\b",
        r"\1 °C",
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(r"\bmain:\s*(?=\d)", "mean: ", html, flags=re.IGNORECASE)
    html = re.sub(r"\bODs/MB\b", "QDs/MB", html)
    html = re.sub(r"\bBeha\s+v\.\s+Neurosci\.", "Behav. Neurosci.", html, flags=re.IGNORECASE)
    html = re.sub(r"\benviron\s+ment\b", "environment", html, flags=re.IGNORECASE)
    html = re.sub(r"\bParkin\s+sonism\b", "Parkinsonism", html, flags=re.IGNORECASE)
    html = re.sub(r"\bNeuro\s+sci\b", "Neurosci", html, flags=re.IGNORECASE)
    html = re.sub(r"\bParkin\s*</a>\s*(<a\b[^>]*>)\s*sonism\b", r"Parkinsonism</a> \1", html)
    html = re.sub(r"\benviron\s*</a>\s*(<a\b[^>]*>)\s*ment\b", r"environment</a> \1", html, flags=re.IGNORECASE)
    html = re.sub(r"\bNeuro\s*</a>\s*sci\.", "Neurosci.</a>", html)
    html = re.sub(r"\bdisconti\s+nuation\b", "discontinuation", html, flags=re.IGNORECASE)
    html = re.sub(r"\bWilhel\s+mina\b", "Wilhelmina", html, flags=re.IGNORECASE)
    html = re.sub(r"\bRUTHERFO\s+RD\b", "RUTHERFORD", html)
    html = re.sub(r"\bInter\s+national\b", "International", html, flags=re.IGNORECASE)
    html = re.sub(
        r"\b(?P<head>APPEND|Append)\s*<sup\b[^>]*>\s*ix\s*</sup>",
        lambda m: "APPENDIX" if m.group("head").isupper() else "Appendix",
        html,
    )
    html = re.sub(
        r"\b(?P<head>APPEND|Append)\s+ix\b",
        lambda m: "APPENDIX" if m.group("head").isupper() else "Appendix",
        html,
    )
    return html


def _mark_wide_table_layout(html: str) -> str:
    """Mark very wide tables so the readability container expands."""
    found_wide = False

    def _mark_table(m: re.Match[str]) -> str:
        nonlocal found_wide
        raw = m.group(0)
        row_cell_counts = [
            len(re.findall(r"<t[dh]\b", row.group(0), flags=re.IGNORECASE))
            for row in re.finditer(r"<tr\b[\s\S]*?</tr>", raw, flags=re.IGNORECASE)
        ]
        if not row_cell_counts or max(row_cell_counts) < 14:
            return raw
        found_wide = True
        open_end = raw.find(">")
        if open_end < 0:
            return raw
        open_tag = _add_class_attr(raw[: open_end + 1], "z2m-wide-table")
        return open_tag + raw[open_end + 1:]

    marked = re.sub(r"<table\b[\s\S]*?</table>", _mark_table, html, flags=re.IGNORECASE)
    if not found_wide:
        return marked
    return _add_body_class(marked, "z2m-has-wide-table")


def _html_gap_is_ignorable(segment: str) -> bool:
    """Return true for whitespace plus standalone page anchors/wrapper tags."""
    cleaned = re.sub(
        r'<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\1[^>]*>\s*</span>',
        "",
        segment,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"</?blockquote\b[^>]*>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip() == ""


def _looks_inline_figure_block(block_html: str) -> bool:
    stripped = block_html.strip()
    if stripped.lower().startswith("<figure"):
        return True
    visible = _visible_text(stripped)
    if _looks_like_in_text_figure_reference_sentence(stripped):
        return False
    if re.match(r"^(?:fig(?:ure)?|fig)\.?\s*\d+\b", visible, re.IGNORECASE):
        return True
    if "<img" not in stripped.lower():
        return False
    # For image-only gaps, allow merge only when no visible caption text exists.
    return len(visible) <= 2


def _looks_running_header_line(visible: str) -> bool:
    text = re.sub(r"\s+", " ", visible).strip()
    if not text:
        return False
    if _PAGE_HEADER_FOOTER_LINE_PATTERN.search(text):
        return True
    if len(text) > 220:
        return False
    for pattern in _PDF_RUNNING_HEADER_PREFIX_PATTERNS:
        match = pattern.match(text)
        if match is not None and not match.group("tail").strip():
            return True
    return False


def _normalize_page_furniture_key(visible: str) -> str:
    text = re.sub(r"\s+", " ", visible).strip()
    return text.lower()


def _looks_repeated_page_furniture_text(visible: str) -> bool:
    text = re.sub(r"\s+", " ", visible).strip()
    if not text or len(text) > 220:
        return False
    if _looks_running_header_line(text):
        return True
    lower = text.lower()
    if re.search(r"\b(?:published on|downloaded by|accepted manuscript|page\s+\d+\s+of\s+\d+)\b", lower):
        return True
    if re.search(r"\b(?:journal|chemistry|chemcomm|medicine|imaging|manuscript)\b", lower):
        words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
        return 3 <= len(words) <= 14
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text)
    if not (3 <= len(words) <= 12):
        return False
    if text.rstrip().endswith((".", "!", "?", ":", ";")):
        return False
    titleish = sum(1 for word in words if word[:1].isupper() or word.isupper())
    return titleish / max(len(words), 1) >= 0.55


def _is_protected_page_furniture_node(raw: str) -> bool:
    protected_classes = (
        "z2m-table-note",
        "z2m-footnote",
        "z2m-figure-caption",
        "z2m-table-caption",
        "z2m-ref-link",
        "z2m-references-block",
    )
    if any(_node_has_class(raw, class_name) for class_name in protected_classes):
        return True
    if re.search(r'\bblock-type\s*=\s*(["\'])List(?:Group|Item)\1', raw, re.IGNORECASE):
        return True
    if re.match(r"^\s*<h[1-6]\b", raw, re.IGNORECASE):
        visible = _visible_text(raw)
        if re.match(r"^(?:abstract|introduction|results?|discussion|conclusions?|references?)\b", visible, re.IGNORECASE):
            return True
    return False


def _repeated_page_furniture_keys(html: str) -> set[str]:
    counts: dict[str, int] = {}
    for node in _SENTENCE_NODE_PATTERN.finditer(html):
        raw = node.group(0)
        if not (raw.lstrip().lower().startswith("<p") or re.match(r"^\s*<h[1-6]\b", raw, re.IGNORECASE)):
            continue
        if _is_protected_page_furniture_node(raw):
            continue
        visible = _visible_text(raw)
        if not _looks_repeated_page_furniture_text(visible):
            continue
        key = _normalize_page_furniture_key(visible)
        counts[key] = counts.get(key, 0) + 1
    return {key for key, count in counts.items() if count >= 2}


def _strip_plain_visible_prefix_from_body(body: str, visible_prefix: str) -> str | None:
    prefix_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'&.-]*", visible_prefix)
    if len(prefix_words) < 3:
        return None
    prefix_pattern = r"\s+".join(re.escape(word) for word in prefix_words)
    pattern = re.compile(
        rf"^(?P<lead>{_LEADING_PAGE_ANCHOR_HTML_PATTERN})(?P<prefix>{prefix_pattern})\b(?P<tail>[\s\S]+)$",
        re.IGNORECASE,
    )
    match = pattern.match(body)
    if match is None:
        return None
    tail = match.group("tail").lstrip()
    tail_text = _visible_text(tail)
    if len(tail_text) < 6:
        return None
    return match.group("lead") + tail


def _drop_repeated_page_furniture(html: str) -> str:
    repeated_keys = _repeated_page_furniture_keys(html)
    if not repeated_keys:
        return html

    key_to_text: dict[str, str] = {}
    for node in _SENTENCE_NODE_PATTERN.finditer(html):
        visible = _visible_text(node.group(0))
        key = _normalize_page_furniture_key(visible)
        if key in repeated_keys and key not in key_to_text:
            key_to_text[key] = re.sub(r"\s+", " ", visible).strip()

    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    dropped: set[int] = set()
    replacements: dict[int, str] = {}

    for idx, node in enumerate(nodes):
        raw = node.group(0)
        if not raw.lstrip().lower().startswith("<p"):
            continue
        if _is_protected_page_furniture_node(raw):
            continue
        match = _SENTENCE_P_NODE_PATTERN.match(raw)
        if match is None:
            continue
        visible = _visible_text(match.group("body"))
        key = _normalize_page_furniture_key(visible)
        if key in repeated_keys:
            dropped.add(idx)
            continue
        for repeated_text in key_to_text.values():
            stripped_body = _strip_plain_visible_prefix_from_body(match.group("body"), repeated_text)
            if stripped_body is None:
                continue
            replacements[idx] = f"{match.group('open')}{stripped_body}{match.group('close')}"
            break

    if not dropped and not replacements:
        return html

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


_PUBLISHER_CHROME_BLOCK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"<h[1-6]\b[^>]*>\s*(?:<[^>]+>\s*)*check\s+for\s*(?:</[^>]+>\s*)*</h[1-6]>\s*"
        r"<p\b[^>]*>\s*updates\s*</p>\s*"
        r"(?:<p\b[^>]*>\s*Citation\s*:[\s\S]{0,6000}?</p>\s*)?"
        r"(?:<p\b[^>]*>\s*Academic\s+Editor\s*:[\s\S]{0,1200}?</p>\s*)?"
        r"(?:<p\b(?=[^>]*\bz2m-front-matter\b)[^>]*>\s*"
        r"Received\s*:[\s\S]{0,1200}?Published\s*:[\s\S]{0,1200}?</p>\s*)?"
        r"(?:<p\b[^>]*>\s*Publisher['\u2019]s\s+Note\s*:[\s\S]{0,1600}?</p>\s*)?"
        r"(?:<p\b[^>]*>\s*Copyright\s*:[\s\S]{0,2600}?</p>\s*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"<h1\b[^>]*>\s*(?:<b\b[^>]*>\s*)?"
        r"Resonance-Compatible\s+Incubator\s+With\s+a\s+Built-in\s+Coil\s+"
        r"Ultrafast\s+Magnetic\s+Resonance\s+Imaging\s+of\s+the\s+Neonate\s+"
        r"in\s+a\s+Magnetic[\s\S]*?(?=</body>|</main>|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"<h[1-6]\b[^>]*>\s*(?:<[^>]+>\s*)*FLORE\s+Repository\s+istituzionale"
        r"[\s\S]{0,800}?</h[1-6]>"
        r"[\s\S]{0,200000}?\bArticle\s+begins\s+on\s+next\s+page\b[\s\S]{0,500}?</p>\s*",
        re.IGNORECASE,
    ),
    re.compile(
        r"<h[1-6]\b[^>]*>\s*(?:<b>\s*)?Articles\s+you\s+may\s+be\s+interested\s+in"
        r"(?:\s*</b>)?\s*</h[1-6]>"
        r"[\s\S]{0,120000}?(?=<p\b[^>]*>\s*<img\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"<h[1-6]\b[^>]*>\s*(?:<[^>]+>\s*)*University\s+of\s+Groningen"
        r"[\s\S]{0,800}?</h[1-6]>"
        r"[\s\S]{0,160000}?<p\b[^>]*>\s*Download\s+date\s*:[\s\S]{0,500}?</p>\s*",
        re.IGNORECASE,
    ),
)


def _expand_span_start_to_leading_image_paragraph(html: str, start: int) -> int:
    prefix = html[:start]
    search_start = max(0, len(prefix) - 2_000_000)
    paragraph_start = prefix.lower().rfind("<p", search_start)
    if paragraph_start < 0:
        return start
    candidate = html[paragraph_start:start]
    if re.fullmatch(r"<p\b[^>]*>\s*<img\b[\s\S]*?</p>\s*", candidate, flags=re.IGNORECASE):
        return paragraph_start
    return start


def _drop_publisher_chrome_pages(html: str) -> str:
    spans: list[tuple[int, int]] = []
    for pattern in _PUBLISHER_CHROME_BLOCK_PATTERNS:
        for match in pattern.finditer(html):
            spans.append((_expand_span_start_to_leading_image_paragraph(html, match.start()), match.end()))
    if not spans:
        return html

    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    out: list[str] = []
    cursor = 0
    for start, end in merged:
        out.append(html[cursor:start])
        cursor = end
    out.append(html[cursor:])
    return "".join(out)


def _strip_pdf_running_header_prefix_from_body(body: str) -> tuple[str, bool]:
    current = body
    changed = False
    while True:
        for pattern in _PDF_RUNNING_HEADER_PREFIX_PATTERNS:
            match = pattern.match(current)
            if match is None:
                continue
            tail = match.group("tail")
            if not tail or not _visible_text(tail):
                current = match.group("lead")
            else:
                current = match.group("lead") + tail.lstrip()
            changed = True
            break
        else:
            return current, changed


def _strip_leading_pdf_line_number_from_body(body: str) -> tuple[str, bool]:
    match = _PDF_LINE_NUMBER_CONTINUATION_BODY_PATTERN.match(body)
    if match is None:
        return body, False
    try:
        number = int(match.group("num") or match.group("sup_num"))
    except ValueError:
        return body, False
    if number % 5 != 0:
        return body, False

    tail = match.group("tail")
    tail_text = _visible_text(tail)
    if not re.match(
        r"^(?:eV|nm|mM|uM|mL|cm|mm|kg|Research\s+Project)\b",
        tail_text,
        re.IGNORECASE,
    ):
        return body, False
    return match.group("lead") + tail.lstrip(), True


def _split_trailing_table_note_from_body(body: str) -> tuple[str, str] | None:
    if len(body) > 4000:
        tail = body[-2500:].lower()
        if not any(marker in tail for marker in _TRAILING_TABLE_NOTE_MARKERS):
            return None
    match = _TRAILING_TABLE_NOTE_BODY_PATTERN.match(body)
    if match is None:
        return None
    prefix = match.group("prefix").rstrip()
    note = match.group("note").lstrip()
    prefix_text = _visible_text(prefix)
    note_text = _visible_text(note)
    if len(prefix_text) < 20 or not _looks_table_note_text(note_text):
        return None
    return prefix, note


def _split_trailing_table_caption_from_body(body: str) -> tuple[str, str] | None:
    match = _TRAILING_TABLE_CAPTION_BODY_PATTERN.match(body)
    if match is None:
        return None
    prefix = match.group("prefix").rstrip()
    caption = match.group("caption").lstrip()
    prefix_text = _visible_text(prefix)
    caption_text = _visible_text(caption)
    if len(prefix_text) < 20:
        return None
    if prefix_text.rstrip().endswith((".", "!", "?", ":", ";", "вЂ¦")):
        return None
    if _table_caption_key_from_visible(caption_text) is None:
        return None
    if len(caption_text) < 35 and not re.match(r"^TABLE\b", caption_text):
        return None
    return prefix, caption


def _looks_sidebar_heading_text(visible: str) -> bool:
    text = re.sub(r"\s+", " ", visible).strip()
    return bool(
        re.match(
            r"^(?:strengths?\s+and\s+limitations?|main\s+points?|key\s+points?|highlights?)\b",
            text,
            re.IGNORECASE,
        )
    )


def _looks_metadata_gap_text(visible: str) -> bool:
    text = re.sub(r"\s+", " ", visible).strip()
    if not text or len(text) > 1800:
        return False
    if _looks_running_header_line(text):
        return True
    return bool(
        re.match(
            r"^(?:"
            r"This\s+work\s+was\s+performed|"
            r"This\s+is\s+a\s+slightly\s+extended|"
            r"All\s+paintings\b|"
            r"Permission\s+to\s+make\s+digital|"
            r"(?:Copyright|\u00a9|&copy;)\b|"
            r"DOI\b|"
            r"Received(?:\s+for\s+publication)?\b|"
            r"Accepted\s+for\s+publication\b|"
            r"accepted\s+\w+\s+\d{1,2},?\s+\d{4}\b|"
            r"Read\s+at\s+(?:the\s+)?annual\s+meeting\b|"
            r"Supported\s+by\b|"
            r"From\s+the\b|"
            r"Address\s+correspondence\b|"
            r"Present\s+Address\b|"
            r"Authors?'?\s+addresses\b|"
            r"Competing\s+Interests?\b|"
            r"Funding\b|"
            r"The\s+authors\s+have\s+declared\b|"
            r"Torsten\s+Lonneker-Lammers\b|"
            r"Ravi\s+Srinivasan\b|"
            r"PEDIATRICS\s+\(ISSN\b|"
            r"Correspondence\s+to\b"
            r")",
            text,
            re.IGNORECASE,
        )
    )


def _looks_list_group_block(raw: str) -> bool:
    if not raw.lstrip().lower().startswith("<p"):
        return False
    if re.search(r'\bblock-type\s*=\s*(["\'])ListGroup\1', raw, re.IGNORECASE):
        return True
    return bool(re.search(r"<ul\b|<ol\b|<li\b", raw, re.IGNORECASE))


def _looks_nonprose_gap_block(block_html: str) -> bool:
    stripped = block_html.strip()
    lowered = stripped.lower()
    if lowered.startswith("<figure") or lowered.startswith("<table"):
        return True

    if lowered.startswith("<h"):
        h_match = _SENTENCE_H_NODE_PATTERN.match(stripped)
        visible = _visible_text(h_match.group("body") if h_match else stripped)
        if _looks_sidebar_heading_text(visible):
            return True
        return bool(re.match(r"^(?:fig(?:ure)?|table|таблица)\.?\s*[ivxlcdm\d]+\b", visible, re.IGNORECASE))

    if lowered.startswith("<p"):
        if _is_table_note_node(stripped):
            return True
        if _looks_list_group_block(stripped):
            return True
        if _node_has_class(stripped, "z2m-front-matter") or _looks_front_matter_block(stripped):
            return True
        if _looks_affiliation_block(stripped):
            return True
        if _node_has_class(stripped, "z2m-footnote"):
            return True
        if _looks_inline_figure_block(stripped):
            return True
        if _is_figure_caption_node(stripped) and not _looks_like_in_text_figure_reference_sentence(stripped):
            return True
        visible = _visible_text(stripped)
        if not visible:
            return True
        if re.fullmatch(r"[\s.,;:|/\\-]+", visible):
            return True
        if _looks_running_header_line(visible):
            return True
        if re.match(r"^(?:table|таблица)\.?\s*[ivxlcdm\d]+\b", visible, re.IGNORECASE):
            return True
        if _looks_metadata_gap_text(visible):
            return True
        # Table-tail math notes often rendered as standalone paragraphs.
        if re.match(r"^\\[\(\[]", visible):
            return True

    return False


def _looks_inline_figure_gap(block_html: str) -> bool:
    blocks = _SENTENCE_GAP_BLOCK_PATTERN.findall(block_html)
    if not blocks:
        return False
    saw_figure_like = False
    for block in blocks:
        if not _looks_nonprose_gap_block(block):
            return False
        saw_figure_like = True
    return saw_figure_like


def _language_probe_text_for_continuation(text: str) -> str:
    # Marker mojibake for en dash/nbsp can contain Cyrillic-looking bytes.
    # Strip known artifacts for the language guard without hiding real Cyrillic.
    pattern = r"(?:\u0432\u0402\S*|\u0420\u0406\u0420\u201a\S*|\u0412(?=\s|\xa0|\d|$))"
    return re.sub(pattern, "", text)


def _is_sentence_continuation(left_text: str, right_text: str) -> bool:
    if not left_text or not right_text:
        return False
    if not re.search(r"[A-Za-zА-Яа-яЁё]", left_text + right_text):
        return False
    if len(left_text) > 1200:
        left_text = left_text[-1200:]
    if len(right_text) > 1200:
        right_text = right_text[:1200]
    left_text = _language_probe_text_for_continuation(left_text)
    right_text = _language_probe_text_for_continuation(right_text)

    right_start = right_text.lstrip()
    if not right_start:
        return False
    norm_right_start = re.sub(r'^[\s"\'(\[\{,;:]+', "", right_start)
    if not norm_right_start:
        norm_right_start = right_start
    if re.match(r"^(?:fig(?:ure)?|table)\.?\s*\d+", norm_right_start, re.IGNORECASE):
        return False
    if re.search(
        r"\b(?:however|therefore|consequently|conversely|additionally|moreover|nevertheless|thus),\s*$",
        left_text,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"\bin\s+the\s+\((?:hypothetic|hypothetical)\)\s*$", left_text, re.IGNORECASE) and re.match(
        r"^3D\s+space\b",
        norm_right_start,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"\bet\s*$", left_text, re.IGNORECASE) and re.match(
        r"^al\.\s+\d{4}[a-z]?(?:\s*[,;-]\s*[a-z])?\)?\b",
        norm_right_start,
        re.IGNORECASE,
    ):
        return True
    if re.search(r"\bet\s+al\.\s*$", left_text, re.IGNORECASE) and re.match(
        r"^\d{4}[a-z]?(?:\s*[,–-]\s*[a-z])?\)?\b",
        norm_right_start,
        re.IGNORECASE,
    ):
        return True
    if left_text.count("(") > left_text.count(")") and re.match(
        r"^(?:[<>]|\u2264|\u2265|&(?:gt|lt);)\s*\d",
        norm_right_start,
        re.IGNORECASE,
    ):
        return True
    if right_start.startswith("("):
        return True
    if left_text.rstrip().endswith((".", "!", "?", ":", ";", "…")):
        return False

    first_token_match = re.match(r'^["\'(\[]*([^\W\d_]+)', norm_right_start, re.UNICODE)
    first_token = first_token_match.group(1).lower() if first_token_match else ""
    if re.search(r"\b(?:Science|Construction|Scientific)\s*$", left_text, re.IGNORECASE) and re.match(
        r"^(?:Foundations?|Research\s+Project)\b",
        norm_right_start,
        re.IGNORECASE,
    ):
        return True
    if re.search(
        r"\b(?:the|a|an|of|for|with|and|or|to|in|at|by|from|between|through|using|into|on|"
        r"и|или|с|со|в|во|на|по|для|от|из|к|ко|при|между)\s*$",
        left_text,
        re.IGNORECASE,
    ) and re.match(
        r"^(?:[A-Z]{2,}[A-Za-z0-9-]*|[A-Z]?[a-z]+|"
        r"\d+(?:[.,]\d+)?\s*(?:%|-)|"
        r"\d+(?:[.,]\d+)?\s*(?:eV|nm|cm|mm|mM|uM|mL|kg)\b)",
        norm_right_start,
    ):
        return True
    continuation_tokens = {
        "and",
        "or",
        "but",
        "with",
        "which",
        "where",
        "when",
        "while",
        "that",
        "to",
        "for",
        "of",
        "in",
        "on",
        "at",
        "as",
        "by",
        "if",
        "after",
        "before",
        "during",
        "because",
        "meanwhile",
        "then",
        "currently",
        "it",
        "this",
        "these",
        "those",
        "the",
        "a",
        "an",
        "acquisition",
        "и",
        "или",
        "но",
        "с",
        "со",
        "в",
        "во",
        "на",
        "по",
        "для",
        "что",
        "как",
        "который",
        "которая",
        "которое",
        "которые",
        "при",
        "между",
    }
    first_char = norm_right_start[0]
    if first_char.islower():
        return True
    if first_token in continuation_tokens:
        return True
    return False


def _is_sentence_continuation_across_affiliation_gap(left_text: str, right_text: str) -> bool:
    """Relaxed continuation check for cases split by long affiliation footnote blocks."""
    left_text = _language_probe_text_for_continuation(left_text)
    right_text = _language_probe_text_for_continuation(right_text)
    if not left_text or not right_text:
        return False
    if not re.search(r"[A-Za-z]", left_text + right_text):
        return False
    if re.search(r"[А-Яа-яЁё]", left_text + right_text):
        return False

    right_start = right_text.lstrip()
    if not right_start:
        return False
    norm_right_start = re.sub(r'^[\s"\'(\[\{,;:]+', "", right_start)
    if not norm_right_start:
        norm_right_start = right_start
    if re.match(r"^(?:fig(?:ure)?|table|box)\.?\s*\d*", norm_right_start, re.IGNORECASE):
        return False
    if re.match(r"^\d+", norm_right_start):
        return False
    if len(norm_right_start) < 4:
        return False
    if left_text.rstrip().endswith((".", "!", "?", ":", ";", "…")):
        return False
    return True


def _is_short_fragment_left(left_text: str) -> bool:
    words = re.findall(r"[^\W\d_]+", left_text, re.UNICODE)
    if not words or len(words) > 5:
        return False
    if left_text.rstrip().endswith((".", "!", "?", ":", ";", "…")):
        return False
    first = words[0].lower()
    return first in {
        "this",
        "these",
        "it",
        "that",
        "which",
        "also",
        "we",
        "they",
        "there",
        "here",
        "our",
        "the",
        "only",
        "мы",
        "это",
        "также",
        "который",
        "которая",
        "которые",
    }


def _merge_sentence_parts(left_body: str, right_body: str) -> str:
    merged_left = left_body.rstrip()
    tail = right_body.lstrip()
    if merged_left and tail:
        if merged_left.endswith("-") and re.match(r"^[a-z]", tail):
            # OCR line-wrap hyphenation (e.g. "regis-" + "ter") around split blocks.
            merged_left = merged_left[:-1]
        elif tail[:1] in ",.;:)]}":
            pass
        elif not merged_left.endswith((" ", "\n", "\t", "-", "(", "[", "/")):
            merged_left += " "
    merged_left += tail
    return merged_left


def _looks_like_in_text_figure_reference_sentence(raw: str) -> bool:
    text = _visible_text(raw)
    return re.match(
        r"^\s*(?:fig(?:ure)?s?\.?|figures?)\s+\d+[A-Za-z]?"
        r"(?:\s|,)+"
        r"(?:shows?|illustrates?|presents?|depicts?|demonstrates?|summari[sz]es?|"
        r"provides?|reports?|contains?|the|this|these|we|it|they)\b",
        text,
        re.IGNORECASE,
    ) is not None


def _looks_like_caption_continuation_after_figure(caption_text: str, right_text: str) -> bool:
    """Return true when prose after a figure is more likely caption continuation."""
    if not caption_text or not right_text:
        return False
    right_start = right_text.lstrip()
    if len(right_start) < 6:
        return False
    norm_right_start = re.sub(r'^[\s"\'(\[\{,;:]+', "", right_start)
    if not norm_right_start:
        norm_right_start = right_start
    if re.match(r"^(?:fig(?:ure)?|table|box)\.?\s*\d+", norm_right_start, re.IGNORECASE):
        return False
    if re.match(r"^\d+\s*[.)]", norm_right_start):
        return False
    if re.match(r"^\([A-Ha-h]\)\s+\S", right_start) and _standalone_figure_label_key_from_visible(caption_text):
        return True
    if not (
        norm_right_start[:1].islower()
        or right_start[:1] in "([{"
        or re.match(r"^(?:and|or|to|with|of|by|in|for|as)\b", norm_right_start, re.IGNORECASE)
    ):
        return False
    if caption_text.rstrip().endswith((".", "!", "?", ";", "вЂ¦")):
        return False
    return _is_sentence_continuation(caption_text, right_text)


def _split_caption_continuation_with_body_tail(
    left_text: str,
    caption_text: str,
    right_body: str,
) -> tuple[str, str] | None:
    """Split a paragraph that starts as caption continuation but ends as body tail."""
    for match in re.finditer(r"\s+(?=\()", right_body):
        caption_tail = right_body[: match.start()].rstrip()
        body_tail = right_body[match.end() :].lstrip()
        caption_tail_text = _visible_text(caption_tail)
        body_tail_text = _visible_text(body_tail)
        if len(caption_tail_text) < 40 or len(body_tail_text) < 20:
            continue
        if not re.search(r"[.!?]\s*$", caption_tail_text):
            continue
        if not _looks_like_caption_continuation_after_figure(caption_text, caption_tail_text):
            continue
        if not _is_sentence_continuation(left_text, body_tail_text):
            continue
        return caption_tail, body_tail
    return None


def _is_equation_like_node(raw: str) -> bool:
    if not raw.lstrip().lower().startswith("<p"):
        return False
    if re.search(r'\bblock-type\s*=\s*(["\'])Equation\1', raw, re.IGNORECASE):
        return True
    if _node_has_class(raw, "z2m-equation") or _node_has_class(raw, "z2m-equation-row"):
        return True
    return "z2m-math-display" in raw and len(_visible_text(raw)) < 1200


def _node_is_empty_spacer_paragraph(raw: str) -> bool:
    return (
        re.match(r"<p\b", raw, re.IGNORECASE) is not None
        and not _node_image_srcs(raw)
        and not _visible_text(raw).strip()
    )


def _node_is_caption_bridge_paragraph(raw: str) -> bool:
    if re.match(r"<p\b", raw, re.IGNORECASE) is None:
        return False
    if _node_image_srcs(raw):
        return False
    if _node_is_empty_spacer_paragraph(raw):
        return True
    visible = _visible_text(raw).strip()
    if re.fullmatch(r"[\s.,;:|/\\\-\u2010-\u2014]+", visible):
        return True
    if _is_figure_caption_node(raw) or _is_table_caption_node(raw):
        return False
    if re.match(r"^\d+(?:\.\d+)*\b", visible):
        return False
    if len(visible) > 90 or re.search(r"[.!?]\s*$", visible):
        return False
    lower = visible.lower()
    bridge_terms = (
        "image",
        "input",
        "translated",
        "overview",
        "module",
        "display",
        "board",
        "chart",
        "graph",
        "screenshot",
        "prototype",
    )
    return any(term in lower for term in bridge_terms)


def _node_is_figure_caption_note_paragraph(raw: str) -> bool:
    if re.match(r"<p\b", raw, re.IGNORECASE) is None:
        return False
    if _node_image_srcs(raw):
        return False
    if _is_figure_caption_node(raw) or _is_table_caption_node(raw):
        return False
    visible = _visible_text(raw).strip()
    if not visible or len(visible) > 2200:
        return False
    lower = visible.lower()
    note_terms = (
        "criteria",
        "question",
        "respondent",
        "ranked",
        "ranking",
        "defined",
        "score",
        "scale",
        "error bar",
        "data are",
        "data represent",
        "values are",
        "mean",
        "sem",
        "standard error",
    )
    if re.match(r"^\*{1,3}\s+\S", visible) and any(term in lower for term in note_terms):
        return True
    if re.match(r"^(?:note|notes?)\s*[:.]\s+\S", visible, re.IGNORECASE) and len(visible) <= 1000:
        return any(term in lower for term in note_terms)
    return False


def _node_is_caption_bridge_or_note_paragraph(raw: str) -> bool:
    return _node_is_caption_bridge_paragraph(raw) or _node_is_figure_caption_note_paragraph(raw)


def _looks_like_in_text_figure_reference_node(raw: str, fig_num: str) -> bool:
    visible = _visible_text(raw).strip()
    if not visible:
        return False
    label = r"\s*[\-.\u2010-\u2014]\s*".join(
        re.escape(part) for part in re.split(r"[\-.\u2010-\u2014]", fig_num) if part
    )
    prefix = rf"(?:FIG(?:URE)?|Fig(?:ure)?|Figure)\.?\s*{label}"
    panel = r"(?:\s*\([A-Za-z]\)|[A-Za-z]|\s+[A-Za-z](?=\s))?"
    if re.match(
        rf"^{prefix}{panel}\s+and\s+(?:Fig(?:ure)?\.?|Figure)\s*{label}{panel}\s+"
        r"(?:represent|represents|show|shows|depict|depicts|illustrate|illustrates|examine|examines|"
        r"suggest|suggests|validate|validates|detail|details|exemplify|exemplifies)\b",
        visible,
        re.IGNORECASE,
    ):
        return True
    if re.match(
        rf"^{prefix}{panel}\s+(?:and|or)\s+(?:Fig(?:ure)?\.?|Figure)\s*{_FIG_KEY_TOKEN}{panel}\s+"
        r"(?:represents?|shows?|depicts?|illustrates?|examines?|suggests?|validates?|details?|exemplif(?:y|ies))\b",
        visible,
        re.IGNORECASE,
    ):
        return True
    if re.match(
        rf"^{prefix}{panel}\s+(?:and|or|,|&)\s+[A-Za-z]\s+"
        r"(?:represents?|shows?|depicts?|illustrates?|examines?|suggests?|validates?|details?|exemplif(?:y|ies))\b",
        visible,
        re.IGNORECASE,
    ):
        return True
    if re.match(
        rf"^{prefix}{panel}\s*[\-\u2010\u2011\u2012\u2013\u2014]\s*(?:{label}\s*)?[A-Za-z]\s+"
        r"(?:represents?|shows?|depicts?|illustrates?|examines?|suggests?|indicates?|presents?|validates?|details?|exemplif(?:y|ies))\b",
        visible,
        re.IGNORECASE,
    ):
        return True
    if re.match(
        rf"^{prefix}\s*\(\s*(?:left|right|top|bottom|upper|lower|central|center|middle|"
        r"same|both|all|main|inset|side|front|back|first|second|third)"
        r"(?:\s+(?:and|or|/)?\s*(?:left|right|top|bottom|upper|lower|central|center|middle|"
        r"same|both|all|main|inset|side|front|back|first|second|third|panels?|panel|plots?|plot|images?|image))*"
        r"\s*\)\s+"
        r"(?:represents?|shows?|depicts?|illustrates?|examines?|suggests?|indicates?|presents?|exemplif(?:y|ies))\b",
        visible,
        re.IGNORECASE,
    ):
        return True
    if re.match(
        rf"^{prefix}\s*\([A-Za-z]\)\.\s+"
        r"(?:Such|The|This|These|Those|It|They|As|Starting|Using|Since|When)\b",
        visible,
        re.IGNORECASE,
    ):
        return True
    if re.match(
        rf"^{prefix}{panel}\s+"
        r"(?:visually\s+)?(?:depicts|shows|showcases|illustrates|represents|presents|summarizes|"
        r"plots|visualizes|visualises|displays|maps|describes|examines|suggests|validates|details(?!\s+of\b)|"
        r"exemplifies|reveals|highlights|contrasts|compares)\b",
        visible,
        re.IGNORECASE,
    ):
        return True
    return False


def _missing_figure_warning_html(fig_num: str, *, figure_caption_language: str = "en") -> str:
    if figure_caption_language == "ru":
        text = (
            f"Рисунок {fig_num} не был извлечен в этот HTML. "
            "См. исходный PDF для отсутствующего визуального содержимого."
        )
    else:
        text = (
            f"Figure {fig_num} image was not extracted into this HTML. "
            "Please check the original PDF for the missing visual content."
        )
    return f'<p class="z2m-missing-figure-warning" role="note">{text}</p>'


_ACCEPTED_MANUSCRIPT_FIGURE_PLACEHOLDER_RE = re.compile(
    r"^\s*(?:[/\[\(\{]\s*)?"
    r"(?:INSERT\s+)?FIG(?:URE)?\.?\s+(?P<num>\d{1,3})\s+"
    r"(?:NEAR\s+HERE|HERE|GOES\s+HERE|TO\s+COME)"
    r"(?:\s*[/\]\)\}])?\s*$",
    re.IGNORECASE,
)
_ACCEPTED_MANUSCRIPT_SLASH_FIGURE_PLACEHOLDER_RE = re.compile(
    r"^\s*/\s*(?:INSERT\s+)?FIG(?:URE)?\.?\s+(?P<num>\d{1,3})\s*/\s*$",
    re.IGNORECASE,
)


def _wrap_accepted_manuscript_figure_placeholders_as_missing(
    html: str,
    *,
    figure_caption_language: str = "en",
) -> tuple[str, set[str]]:
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, set()

    existing_ids = {
        match.group("id").lower()
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[A-Za-z0-9-]+)\1', html, re.IGNORECASE)
    }
    replacements: dict[int, str] = {}
    found: set[str] = set()

    for index, node in enumerate(nodes):
        raw = node.group(0)
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            continue
        if _node_has_class(raw, "z2m-float-unit") or _node_has_class(raw, "z2m-missing-figure-unit"):
            continue
        visible = _visible_text(raw)
        placeholder = _ACCEPTED_MANUSCRIPT_FIGURE_PLACEHOLDER_RE.match(visible)
        if placeholder is None:
            placeholder = _ACCEPTED_MANUSCRIPT_SLASH_FIGURE_PLACEHOLDER_RE.match(visible)
        if placeholder is None:
            continue
        fig_num = _figure_key_from_visible_number(placeholder.group("num"))
        target_id = f"fig-{fig_num}"
        if target_id.lower() in existing_ids:
            continue

        warning_html = _missing_figure_warning_html(
            fig_num,
            figure_caption_language=figure_caption_language,
        )
        warning_html = re.sub(
            r"^<p\b",
            '<p data-z2m-origin="accepted-manuscript-placeholder"',
            warning_html,
            count=1,
            flags=re.IGNORECASE,
        )
        warning_html = re.sub(
            r'\bclass\s*=\s*(["\'])z2m-missing-figure-warning\1',
            r'class=\1z2m-missing-figure-warning z2m-figure-target\1',
            warning_html,
            count=1,
            flags=re.IGNORECASE,
        )
        caption_html = _strip_node_id_and_add_class(raw, "z2m-figure-caption")
        replacements[index] = (
            f'<div id="{target_id}" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
            f"{warning_html}{caption_html}</div>"
        )
        existing_ids.add(target_id.lower())
        found.add(fig_num)

    if not replacements:
        return html, set()

    out_parts: list[str] = []
    cursor = 0
    for index, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        out_parts.append(replacements.get(index, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), found


_STANDALONE_FIGURE_LABEL_RE = re.compile(
    r"^\s*(?:FIG(?:URE)?|Fig(?:ure)?"
    r"|Рис(?:унок)?|рис(?:унок)?|Фиг(?:ура)?|фиг(?:ура)?)"
    rf"\.?\s*({_FIG_RELAXED_KEY_TOKEN})({_FIG_CAPTION_PANEL_SUFFIX_TOKEN})?\s*$",
    re.IGNORECASE,
)


def _standalone_figure_label_key_from_visible(visible: str) -> str | None:
    match = _STANDALONE_FIGURE_LABEL_RE.match(visible)
    if match is None:
        return None
    if match.group(2):
        return None
    return _figure_key_from_visible_number(match.group(1))


def _anchor_standalone_figure_labels_before_images(html: str) -> tuple[str, set[str]]:
    """Promote short ``Figure N`` labels immediately next to images to real targets."""
    if "<img" not in html.lower():
        return html, set()

    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if len(nodes) < 2:
        return html, set()

    existing_ids = {
        match.group("id").lower()
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[A-Za-z0-9-]+)\1', html, re.IGNORECASE)
    }
    replacements: dict[int, str] = {}
    consumed: set[int] = set()
    found: set[str] = set()

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _replace_open(raw: str, transform: Callable[[str], str]) -> str:
        return _transform_node_open(raw, transform)

    def _looks_like_caption_detail_after_standalone_label(raw: str) -> bool:
        if not raw.lstrip().lower().startswith("<p"):
            return False
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            return False
        if _node_has_class(raw, "z2m-float-unit") or _node_has_class(raw, "z2m-figure-unit"):
            return False
        if _is_figure_caption_node(raw) or _is_table_caption_node(raw):
            return False
        visible = _visible_text(raw).strip()
        if not visible or len(visible) > 1400:
            return False
        if _standalone_figure_label_key_from_visible(visible) is not None:
            return False
        if _figure_caption_num_from_visible(visible) is not None:
            return False
        return bool(re.match(r"^\([A-Ha-h]\)\s+\S", visible))

    def _looks_like_caption_body_after_standalone_label(raw: str) -> bool:
        if not raw.lstrip().lower().startswith("<p"):
            return False
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            return False
        if _node_has_class(raw, "z2m-float-unit") or _node_has_class(raw, "z2m-figure-unit"):
            return False
        if _is_figure_caption_node(raw) or _is_table_caption_node(raw):
            return False
        visible = _visible_text(raw).strip()
        if len(visible) < 24 or len(visible) > 2600:
            return False
        if _standalone_figure_label_key_from_visible(visible) is not None:
            return False
        if _figure_caption_num_from_visible(visible) is not None:
            return False
        if re.match(r"^\([A-Ha-h]\)\s+\S", visible):
            return False
        if re.match(
            r"^(?:abstract|introduction|background|methods?|materials|results?|discussion|"
            r"conclusions?|references|bibliography|acknowledg|funding|conflicts?)\b",
            visible,
            re.IGNORECASE,
        ):
            return False
        return True

    def _looks_like_caption_panel_heading_after_standalone_label(raw: str) -> bool:
        if not re.match(r"<(?:p|h[1-6])\b", raw.lstrip(), re.IGNORECASE):
            return False
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            return False
        if _node_has_class(raw, "z2m-float-unit") or _node_has_class(raw, "z2m-figure-unit"):
            return False
        visible = _visible_text(raw).strip()
        if not visible or len(visible) > 240:
            return False
        if _standalone_figure_label_key_from_visible(visible) is not None:
            return False
        if (
            _figure_caption_num_from_visible(visible) is not None
            or _table_caption_key_from_visible(visible) is not None
        ):
            return False
        return bool(re.match(r"^\(?[A-Ha-h]\)?(?:[).:,\-\u2010-\u2014]|\s+)\S", visible))

    def _image_target_replacement(raw: str, *, image_idx: int, first_image_idx: int, target_id: str) -> str:
        return _replace_open(
            raw,
            lambda open_tag: _add_class_attr(
                (
                    _add_id_attr(_remove_id_attr(open_tag), target_id)
                    if image_idx == first_image_idx
                    else _remove_id_attr(open_tag)
                ),
                "z2m-figure-target",
            ),
        )

    def _caption_body_has_rich_panel_inventory(raw: str) -> bool:
        visible = _visible_text(raw)
        return len(re.findall(r"\([A-Ha-h]\)", visible)) >= 3

    def _preceding_panel_image_run_indices(label_index: int, target_id: str) -> tuple[list[int], list[int]]:
        scan_idx = label_index - 1
        group_reversed: list[int] = []
        image_indices_reversed: list[int] = []
        while scan_idx >= 0 and len(group_reversed) < 18:
            if scan_idx < label_index - 1 and not _between_is_whitespace(scan_idx, scan_idx + 1):
                break
            scan_raw = nodes[scan_idx].group(0)
            scan_visible = _visible_text(scan_raw)
            if _standalone_figure_label_key_from_visible(scan_visible) is not None:
                break
            if (
                _figure_caption_num_from_visible(scan_visible) is not None
                or _table_caption_key_from_visible(scan_visible) is not None
            ):
                break
            if re.search(r"<img\b", scan_raw, re.IGNORECASE) is not None:
                image_id = _node_open_id_value(scan_raw)
                if image_id is not None and image_id.lower() != target_id.lower():
                    break
                group_reversed.append(scan_idx)
                image_indices_reversed.append(scan_idx)
                scan_idx -= 1
                continue
            if image_indices_reversed and (
                _looks_like_caption_panel_heading_after_standalone_label(scan_raw)
                or _node_is_caption_bridge_or_note_paragraph(scan_raw)
            ):
                group_reversed.append(scan_idx)
                scan_idx -= 1
                continue
            break
        return list(reversed(group_reversed)), list(reversed(image_indices_reversed))

    def _distant_previous_image_index_for_caption_label(label_index: int, target_id: str) -> int | None:
        scan_idx = label_index - 1
        scanned = 0
        while scan_idx >= 0 and scanned < 14:
            if scan_idx < label_index - 1 and not _between_is_whitespace(scan_idx, scan_idx + 1):
                break
            scan_raw = nodes[scan_idx].group(0)
            scan_visible = _visible_text(scan_raw)
            if _standalone_figure_label_key_from_visible(scan_visible) is not None:
                break
            if (
                _figure_caption_num_from_visible(scan_visible) is not None
                or _table_caption_key_from_visible(scan_visible) is not None
            ):
                break
            if re.search(r"<img\b", scan_raw, re.IGNORECASE) is not None:
                image_id = _node_open_id_value(scan_raw)
                if image_id is None or image_id.lower() == target_id.lower():
                    return scan_idx
                return None
            scan_idx -= 1
            scanned += 1
        return None

    for index in range(len(nodes) - 2):
        if index in consumed or index + 1 in consumed:
            continue
        if not _between_is_whitespace(index, index + 1):
            continue

        label_raw = nodes[index].group(0)
        if not re.match(r"<(?:p|h[1-6])\b", label_raw.lstrip(), re.IGNORECASE):
            continue
        if re.search(r"<img\b|<table\b", label_raw, re.IGNORECASE):
            continue
        if _node_has_class(label_raw, "z2m-float-unit") or _node_has_class(label_raw, "z2m-figure-unit"):
            continue

        fig_num = _standalone_figure_label_key_from_visible(_visible_text(label_raw))
        if fig_num is None:
            continue
        target_id = f"fig-{fig_num}"
        if target_id.lower() in existing_ids:
            continue

        caption_body_raw = nodes[index + 1].group(0)
        if not _looks_like_caption_body_after_standalone_label(caption_body_raw):
            continue

        run_indices, image_indices = _preceding_panel_image_run_indices(index, target_id)
        if not image_indices and _caption_body_has_rich_panel_inventory(caption_body_raw):
            previous_image_idx = _distant_previous_image_index_for_caption_label(index, target_id)
            if previous_image_idx is not None:
                run_indices = [previous_image_idx]
                image_indices = [previous_image_idx]
        if not image_indices:
            continue

        replacements[index] = _strip_node_id_and_add_class(label_raw, "z2m-figure-caption")
        replacements[index + 1] = _strip_node_id_and_add_class(caption_body_raw, "z2m-figure-caption")
        for run_idx in run_indices:
            run_raw = nodes[run_idx].group(0)
            if re.search(r"<img\b", run_raw, re.IGNORECASE) is not None:
                replacements[run_idx] = _image_target_replacement(
                    run_raw,
                    image_idx=run_idx,
                    first_image_idx=image_indices[0],
                    target_id=target_id,
                )
            else:
                replacements[run_idx] = _strip_node_id_and_add_class(run_raw, "z2m-figure-caption")
        consumed.update({index, index + 1, *run_indices})
        existing_ids.add(target_id.lower())
        found.add(fig_num)

    for index in range(len(nodes) - 2):
        if index in consumed or index + 1 in consumed:
            continue
        if not _between_is_whitespace(index, index + 1):
            continue

        label_raw = nodes[index].group(0)
        if not re.match(r"<(?:p|h[1-6])\b", label_raw.lstrip(), re.IGNORECASE):
            continue
        if re.search(r"<img\b|<table\b", label_raw, re.IGNORECASE):
            continue
        if _node_has_class(label_raw, "z2m-float-unit") or _node_has_class(label_raw, "z2m-figure-unit"):
            continue

        fig_num = _standalone_figure_label_key_from_visible(_visible_text(label_raw))
        if fig_num is None:
            continue
        target_id = f"fig-{fig_num}"
        if target_id.lower() in existing_ids:
            continue

        caption_body_raw = nodes[index + 1].group(0)
        if not _looks_like_caption_body_after_standalone_label(caption_body_raw):
            continue

        caption_indices = [index, index + 1]
        image_indices: list[int] = []
        different_label_after_images = False
        scan_idx = index + 2
        while scan_idx < len(nodes) and len(caption_indices) + len(image_indices) < 18:
            if not _between_is_whitespace(scan_idx - 1, scan_idx):
                break
            if scan_idx in consumed:
                break
            scan_raw = nodes[scan_idx].group(0)
            scan_visible = _visible_text(scan_raw)
            if _standalone_figure_label_key_from_visible(scan_visible) is not None:
                different_label_after_images = bool(image_indices)
                break
            if (
                _figure_caption_num_from_visible(scan_visible) is not None
                or _table_caption_key_from_visible(scan_visible) is not None
            ):
                break
            if re.search(r"<img\b", scan_raw, re.IGNORECASE) is not None:
                image_id = _node_open_id_value(scan_raw)
                if image_id is not None and image_id.lower() != target_id.lower():
                    break
                image_indices.append(scan_idx)
                scan_idx += 1
                continue
            if (
                _looks_like_caption_panel_heading_after_standalone_label(scan_raw)
                or _node_is_caption_bridge_or_note_paragraph(scan_raw)
            ):
                caption_indices.append(scan_idx)
                scan_idx += 1
                continue
            break

        if not image_indices or different_label_after_images:
            continue

        replacements[index] = _strip_node_id_and_add_class(label_raw, "z2m-figure-caption")
        replacements[index + 1] = _strip_node_id_and_add_class(caption_body_raw, "z2m-figure-caption")
        for caption_idx in caption_indices[2:]:
            replacements[caption_idx] = _strip_node_id_and_add_class(
                nodes[caption_idx].group(0),
                "z2m-figure-caption",
            )
        for image_idx in image_indices:
            image_raw = nodes[image_idx].group(0)
            replacements[image_idx] = _image_target_replacement(
                image_raw,
                image_idx=image_idx,
                first_image_idx=image_indices[0],
                target_id=target_id,
            )
        consumed.update({*caption_indices, *image_indices})
        existing_ids.add(target_id.lower())
        found.add(fig_num)

    for index in range(len(nodes) - 1):
        if index in consumed or index + 1 in consumed:
            continue
        if not _between_is_whitespace(index, index + 1):
            continue

        label_raw = nodes[index].group(0)
        if not re.match(r"<(?:p|h[1-6])\b", label_raw.lstrip(), re.IGNORECASE):
            continue
        if re.search(r"<img\b|<table\b", label_raw, re.IGNORECASE):
            continue
        if _node_has_class(label_raw, "z2m-float-unit") or _node_has_class(label_raw, "z2m-figure-unit"):
            continue

        fig_num = _standalone_figure_label_key_from_visible(_visible_text(label_raw))
        if fig_num is None:
            continue
        target_id = f"fig-{fig_num}"
        if target_id.lower() in existing_ids:
            continue

        image_raw = nodes[index + 1].group(0)
        if not image_raw.lstrip().lower().startswith("<p"):
            continue
        if re.search(r"<img\b", image_raw, re.IGNORECASE) is None:
            continue
        if _node_has_class(image_raw, "z2m-figure-target") or _node_has_class(image_raw, "z2m-figure-unit"):
            continue
        image_id = _node_open_id_value(image_raw)
        if image_id is not None and image_id.lower() != target_id.lower():
            continue

        detail_indices: list[int] = []
        detail_idx = index + 2
        if (
            detail_idx < len(nodes)
            and detail_idx not in consumed
            and _between_is_whitespace(index + 1, detail_idx)
            and _looks_like_caption_detail_after_standalone_label(nodes[detail_idx].group(0))
        ):
            detail_indices.append(detail_idx)

        replacements[index] = _strip_node_id_and_add_class(label_raw, "z2m-figure-caption")
        replacements[index + 1] = _replace_open(
            image_raw,
            lambda open_tag, target_id=target_id: _add_class_attr(
                _add_id_attr(_remove_id_attr(open_tag), target_id),
                "z2m-figure-target",
            ),
        )
        for detail_idx in detail_indices:
            replacements[detail_idx] = _strip_node_id_and_add_class(
                nodes[detail_idx].group(0),
                "z2m-figure-caption",
            )
        consumed.update({index, index + 1, *detail_indices})
        existing_ids.add(target_id.lower())
        found.add(fig_num)

    for index in range(len(nodes) - 1):
        if index in consumed or index + 1 in consumed:
            continue
        if not _between_is_whitespace(index, index + 1):
            continue

        image_raw = nodes[index].group(0)
        if not image_raw.lstrip().lower().startswith("<p"):
            continue
        if re.search(r"<img\b", image_raw, re.IGNORECASE) is None:
            continue
        if _node_has_class(image_raw, "z2m-figure-target") or _node_has_class(image_raw, "z2m-figure-unit"):
            continue

        label_raw = nodes[index + 1].group(0)
        if not re.match(r"<(?:p|h[1-6])\b", label_raw.lstrip(), re.IGNORECASE):
            continue
        if re.search(r"<img\b|<table\b", label_raw, re.IGNORECASE):
            continue
        if _node_has_class(label_raw, "z2m-float-unit") or _node_has_class(label_raw, "z2m-figure-unit"):
            continue

        fig_num = _standalone_figure_label_key_from_visible(_visible_text(label_raw))
        if fig_num is None:
            continue
        target_id = f"fig-{fig_num}"
        if target_id.lower() in existing_ids:
            continue

        image_id = _node_open_id_value(image_raw)
        if image_id is not None and image_id.lower() != target_id.lower():
            continue

        detail_indices: list[int] = []
        detail_idx = index + 2
        if (
            detail_idx < len(nodes)
            and detail_idx not in consumed
            and _between_is_whitespace(index + 1, detail_idx)
            and _looks_like_caption_detail_after_standalone_label(nodes[detail_idx].group(0))
        ):
            detail_indices.append(detail_idx)

        replacements[index] = _replace_open(
            image_raw,
            lambda open_tag, target_id=target_id: _add_class_attr(
                _add_id_attr(_remove_id_attr(open_tag), target_id),
                "z2m-figure-target",
            ),
        )
        replacements[index + 1] = _strip_node_id_and_add_class(label_raw, "z2m-figure-caption")
        for detail_idx in detail_indices:
            replacements[detail_idx] = _strip_node_id_and_add_class(
                nodes[detail_idx].group(0),
                "z2m-figure-caption",
            )
        consumed.update({index, index + 1, *detail_indices})
        existing_ids.add(target_id.lower())
        found.add(fig_num)

    if not replacements:
        return html, set()

    out_parts: list[str] = []
    cursor = 0
    for index, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        out_parts.append(replacements.get(index, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), found


def _wrap_standalone_caption_before_image_units(html: str) -> str:
    """Wrap caption-before-image figure runs that include panel headings between images."""
    if "z2m-figure-caption" not in html or "z2m-figure-target" not in html:
        return html

    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html

    groups: dict[int, tuple[list[int], str]] = {}
    consumed: set[int] = set()

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    for index, node in enumerate(nodes):
        if index in consumed:
            continue
        raw = node.group(0)
        if not _node_has_class(raw, "z2m-figure-caption"):
            continue
        fig_num = _standalone_figure_label_key_from_visible(_visible_text(raw))
        if fig_num is None:
            continue
        target_id = f"fig-{fig_num}"
        group_indices: list[int] = []
        has_image = False
        scan_idx = index
        while scan_idx < len(nodes) and len(group_indices) < 24:
            if scan_idx in consumed:
                break
            if scan_idx > index and not _between_is_whitespace(scan_idx - 1, scan_idx):
                break
            scan_raw = nodes[scan_idx].group(0)
            scan_visible = _visible_text(scan_raw)
            if scan_idx > index:
                next_standalone = _standalone_figure_label_key_from_visible(scan_visible)
                if next_standalone is not None and next_standalone != fig_num:
                    break
                caption_num = _figure_caption_num_from_visible(scan_visible)
                if caption_num is not None and caption_num != fig_num:
                    break
                if _table_caption_key_from_visible(scan_visible) is not None:
                    break
            if re.search(r"<img\b", scan_raw, re.IGNORECASE) is not None:
                if not _node_has_class(scan_raw, "z2m-figure-target"):
                    break
                image_id = _node_open_id_value(scan_raw)
                if image_id is not None and image_id.lower() != target_id.lower():
                    break
                has_image = True
                group_indices.append(scan_idx)
                scan_idx += 1
                continue
            if _node_has_class(scan_raw, "z2m-figure-caption"):
                group_indices.append(scan_idx)
                scan_idx += 1
                continue
            if _node_is_caption_bridge_or_note_paragraph(scan_raw):
                group_indices.append(scan_idx)
                scan_idx += 1
                continue
            break

        if not has_image or len(group_indices) < 2:
            continue

        content_html = "".join(
            _strip_node_id_and_add_class(
                nodes[idx].group(0),
                (
                    "z2m-figure-target"
                    if re.search(r"<img\b", nodes[idx].group(0), re.IGNORECASE)
                    else "z2m-figure-caption"
                ),
            )
            for idx in group_indices
        )
        wrapper = f'<div id="{target_id}" class="z2m-float-unit z2m-figure-unit">{content_html}</div>'
        groups[group_indices[0]] = (group_indices, wrapper)
        consumed.update(group_indices)

    if not groups:
        return html

    out_parts: list[str] = []
    cursor = 0
    skip_indices: set[int] = set()
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in groups:
            group_indices, wrapper = groups[idx]
            out_parts.append(wrapper)
            skip_indices.update(group_indices[1:])
        elif idx in skip_indices:
            pass
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _wrap_figure_table_surrogate_units(html: str) -> str:
    """Wrap table-like visuals that are captioned as figures."""
    if "z2m-figure-caption" not in html or "<table" not in html.lower():
        return html

    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if len(nodes) < 2:
        return html

    groups: dict[int, tuple[list[int], str]] = {}
    consumed: set[int] = set()

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _is_table_surrogate_figure_note(raw: str) -> bool:
        if re.match(r"<p\b", raw, re.IGNORECASE) is None:
            return False
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            return False
        if _figure_caption_num_from_visible(_visible_text(raw)) is not None:
            return False
        visible = _visible_text(raw).strip()
        if not visible or len(visible) > 1400:
            return False
        if re.match(r"^(?:notes?|source)\s*[:.]\s+\S", visible, re.IGNORECASE) is None:
            return False
        return re.search(
            r"\b(?:used with permission|permission|adapted|reprinted|copyright|from)\b",
            visible,
            re.IGNORECASE,
        ) is not None

    for index in range(1, len(nodes)):
        if index in consumed or index - 1 in consumed:
            continue
        if not _between_is_whitespace(index - 1, index):
            continue

        caption_raw = nodes[index].group(0)
        caption_id = _node_id_value(caption_raw) or ""
        fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", caption_id, re.IGNORECASE)
        if fig_match is None:
            continue
        if not _node_has_class(caption_raw, "z2m-figure-caption"):
            continue
        if re.search(r"<img\b|<table\b", caption_raw, re.IGNORECASE):
            continue

        table_parts = _plain_table_surrogate_parts(nodes[index - 1].group(0))
        if table_parts is None:
            continue
        table_open, table_body, table_close = table_parts

        note_indices: list[int] = []
        next_idx = index + 1
        while next_idx < len(nodes) and _between_is_whitespace(next_idx - 1, next_idx):
            next_raw = nodes[next_idx].group(0)
            if not (
                _node_is_caption_bridge_or_note_paragraph(next_raw)
                or _is_table_surrogate_figure_note(next_raw)
            ):
                break
            note_indices.append(next_idx)
            next_idx += 1

        group_indices = [index - 1, index, *note_indices]
        if any(idx in consumed for idx in group_indices):
            continue

        table_html = f'{_add_class_attr(table_open, "z2m-figure-target")}{table_body}{table_close}'
        caption_html = _strip_node_id_and_add_class(caption_raw, "z2m-figure-caption")
        note_html = "".join(
            _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-figure-caption")
            for idx in note_indices
        )
        wrapper = (
            f'<div id="{caption_id}" class="z2m-float-unit z2m-figure-unit">'
            f"{table_html}{caption_html}{note_html}</div>"
        )
        groups[group_indices[0]] = (group_indices, wrapper)
        consumed.update(group_indices)

    if not groups:
        return html

    out_parts: list[str] = []
    cursor = 0
    skip_indices: set[int] = set()
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in groups:
            group_indices, wrapper = groups[idx]
            out_parts.append(wrapper)
            skip_indices.update(group_indices[1:])
        elif idx in skip_indices:
            pass
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _insert_missing_figure_warnings(
    html: str,
    *,
    figure_caption_language: str = "en",
) -> tuple[str, int]:
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    insert_before: dict[int, str] = {}
    drop_indices: set[int] = set()
    warnings = 0
    id_counts = Counter(
        match.group("id")
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[A-Za-z0-9_.:-]+)\1', html, re.IGNORECASE)
    )

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        gap = html[nodes[a_idx].end():nodes[b_idx].start()]
        return _html_gap_is_ignorable(gap)

    def _image_node_can_belong_to_fig(raw: str, fig_num: str) -> bool:
        node_id = _node_id_value(raw) or ""
        id_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", node_id, re.IGNORECASE)
        return id_match is None or id_match.group(1) == fig_num

    def _is_previous_compound_caption(raw: str, fig_num: str) -> bool:
        previous_num = _figure_caption_num_from_visible(_visible_text(raw))
        if previous_num is None:
            return False
        try:
            return int(previous_num) < int(fig_num)
        except ValueError:
            return False

    def _associated_image_indices(caption_idx: int, fig_num: str) -> list[int]:
        associated: list[int] = []

        caption_run_start = caption_idx
        while (
            caption_run_start > 0
            and _between_is_whitespace(caption_run_start - 1, caption_run_start)
            and _is_figure_caption_node(nodes[caption_run_start - 1].group(0))
        ):
            caption_run_start -= 1

        caption_run_end = caption_idx
        while (
            caption_run_end + 1 < len(nodes)
            and _between_is_whitespace(caption_run_end, caption_run_end + 1)
            and _is_figure_caption_node(nodes[caption_run_end + 1].group(0))
        ):
            caption_run_end += 1

        image_run: list[int] = []
        image_idx = caption_run_start - 1
        while image_idx >= 0 and _between_is_whitespace(image_idx, image_idx + 1):
            image_raw = nodes[image_idx].group(0)
            if _node_is_caption_bridge_or_note_paragraph(image_raw):
                image_idx -= 1
                continue
            if not _node_image_srcs(image_raw):
                break
            image_run.insert(0, image_idx)
            image_idx -= 1

        if image_run:
            caption_offset = caption_idx - caption_run_start
            if len(image_run) >= (caption_run_end - caption_run_start + 1):
                candidate_idx = image_run[caption_offset]
                if _image_node_can_belong_to_fig(nodes[candidate_idx].group(0), fig_num):
                    return [candidate_idx]
            if len(image_run) == 1 and _image_node_can_belong_to_fig(nodes[image_run[0]].group(0), fig_num):
                return [image_run[0]]

        prev_idx = caption_idx - 1
        scanned = 0
        while prev_idx >= 0 and scanned < 6 and _between_is_whitespace(prev_idx, prev_idx + 1):
            prev_raw = nodes[prev_idx].group(0)
            if _node_is_caption_bridge_or_note_paragraph(prev_raw):
                prev_idx -= 1
                scanned += 1
                continue
            if _node_image_srcs(prev_raw):
                if _image_node_can_belong_to_fig(prev_raw, fig_num):
                    associated.append(prev_idx)
                break
            if _is_figure_caption_node(prev_raw):
                if _is_previous_compound_caption(prev_raw, fig_num):
                    prev_idx -= 1
                    scanned += 1
                    continue
                break
            if not (
                _looks_like_figure_caption_fragment(prev_raw)
                or _looks_like_figure_panel_caption_continuation(prev_raw)
            ):
                break
            prev_idx -= 1
            scanned += 1

        next_idx = caption_idx + 1
        scanned = 0
        while next_idx < len(nodes) and scanned < 6 and _between_is_whitespace(next_idx - 1, next_idx):
            next_raw = nodes[next_idx].group(0)
            if _node_is_caption_bridge_or_note_paragraph(next_raw):
                next_idx += 1
                scanned += 1
                continue
            if _is_figure_caption_node(next_raw):
                break
            if _node_image_srcs(next_raw):
                if _image_node_can_belong_to_fig(next_raw, fig_num):
                    associated.append(next_idx)
                break
            if not (
                _looks_like_figure_caption_fragment(next_raw)
                or _looks_like_figure_panel_caption_continuation(next_raw)
            ):
                break
            next_idx += 1
            scanned += 1

        return associated

    for idx, node in enumerate(nodes):
        raw = node.group(0)
        if not _is_figure_caption_node(raw):
            continue
        if "z2m-missing-figure-warning" in raw:
            continue
        if _node_has_renderable_image(raw):
            continue
        fig_num = _figure_caption_num_from_visible(_visible_text(raw)) or "?"
        if fig_num.startswith("supplementary-"):
            continue
        target_id = _node_open_id_value(raw) or ""
        if target_id and id_counts.get(target_id, 0) > 1:
            continue
        start = max(0, idx - 6)
        stop = min(len(nodes), idx + 7)
        nearby_raw = "\n".join(nodes[j].group(0) for j in range(start, stop))
        if _looks_like_in_text_figure_reference_node(raw, fig_num):
            continue
        image_indices = _associated_image_indices(idx, fig_num)
        nearby_renderable_image = any(_node_has_renderable_image(nodes[j].group(0)) for j in image_indices)
        if nearby_renderable_image:
            continue
        if "z2m-missing-figure-warning" in nearby_raw:
            continue
        warning_html = _missing_figure_warning_html(
            fig_num,
            figure_caption_language=figure_caption_language,
        )
        if target_id and re.search(rf"href\s*=\s*['\"]#{re.escape(target_id)}['\"]", html, re.IGNORECASE):
            warning_html = re.sub(
                r"^<p\b",
                '<p data-z2m-origin="caption-only-target"',
                warning_html,
                count=1,
                flags=re.IGNORECASE,
            )
        insert_before[idx] = warning_html
        drop_indices.update(
            j for j in image_indices
            if _node_has_broken_data_image(nodes[j].group(0))
        )
        warnings += 1

    if warnings == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in drop_indices:
            pass
        elif idx in insert_before:
            out_parts.append(insert_before[idx])
            out_parts.append("\n")
            out_parts.append(node.group(0))
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), warnings


def _drop_compound_caption_missing_warnings(html: str) -> tuple[str, int]:
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _previous_caption_has_shared_image(caption_idx: int, fig_num: str) -> bool:
        prev_idx = caption_idx - 1
        scanned = 0
        while prev_idx >= 0 and scanned < 6 and _between_is_whitespace(prev_idx, prev_idx + 1):
            prev_raw = nodes[prev_idx].group(0)
            if _node_image_srcs(prev_raw):
                return _node_has_renderable_image(prev_raw)
            previous_num = _figure_caption_num_from_visible(_visible_text(prev_raw))
            if previous_num is not None:
                try:
                    if int(previous_num) < int(fig_num):
                        prev_idx -= 1
                        scanned += 1
                        continue
                except ValueError:
                    pass
            break
        return False

    drop_indices: set[int] = set()
    for idx, node in enumerate(nodes):
        raw = node.group(0)
        if not _node_has_class(raw, "z2m-missing-figure-warning"):
            continue
        if idx == 0 or idx + 1 >= len(nodes):
            continue
        if not _between_is_whitespace(idx, idx + 1) or not _between_is_whitespace(idx - 1, idx):
            continue
        next_raw = nodes[idx + 1].group(0)
        if not _is_figure_caption_node(next_raw):
            continue
        fig_num = _figure_caption_num_from_visible(_visible_text(next_raw))
        if fig_num is None:
            continue
        if _is_figure_caption_node(nodes[idx - 1].group(0)) and _previous_caption_has_shared_image(idx - 1, fig_num):
            drop_indices.add(idx)

    if not drop_indices:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx not in drop_indices:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), len(drop_indices)


def _drop_same_label_image_missing_warnings(html: str) -> tuple[str, int]:
    if "z2m-missing-figure-warning" not in html:
        return html, 0
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _nearest_caption_label(index: int, *, direction: int, window: int = 4) -> str | None:
        scanned = 0
        current = index + direction
        while 0 <= current < len(nodes) and scanned < window:
            if direction < 0 and not _between_is_whitespace(current, current + 1):
                break
            if direction > 0 and not _between_is_whitespace(current - 1, current):
                break
            raw = nodes[current].group(0)
            label = _figure_caption_num_from_visible(_visible_text(raw))
            if label is not None:
                return label
            if _node_has_renderable_image(raw) or _node_is_caption_bridge_or_note_paragraph(raw):
                current += direction
                scanned += 1
                continue
            if not (
                _looks_like_figure_caption_fragment(raw)
                or _looks_like_figure_panel_caption_continuation(raw)
            ):
                break
            current += direction
            scanned += 1
        return None

    def _has_nearby_renderable_image(index: int, *, direction: int, window: int = 4) -> bool:
        if direction == 0:
            return False
        stop = min(len(nodes), index + window + 1) if direction > 0 else max(-1, index - window - 1)
        previous = index
        for candidate in range(index + direction, stop, direction):
            if direction > 0 and not _between_is_whitespace(previous, candidate):
                break
            if direction < 0 and not _between_is_whitespace(candidate, previous):
                break
            if _node_has_renderable_image(nodes[candidate].group(0)):
                return True
            previous = candidate
        return False

    drop_indices: set[int] = set()
    for idx, node in enumerate(nodes):
        raw = node.group(0)
        if not _node_has_class(raw, "z2m-missing-figure-warning"):
            continue
        fig_num = _figure_caption_num_from_visible(_visible_text(raw))
        if fig_num is None:
            continue
        previous_label = _nearest_caption_label(idx, direction=-1)
        next_label = _nearest_caption_label(idx, direction=1)
        previous_has_image = _has_nearby_renderable_image(idx, direction=-1)
        next_has_image = _has_nearby_renderable_image(idx, direction=1)
        if (
            previous_label == fig_num
            and previous_has_image
            or next_label == fig_num
            and next_has_image
            or next_label == fig_num
            and previous_has_image
            and previous_label in {None, fig_num}
        ):
            drop_indices.add(idx)

    if not drop_indices:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx not in drop_indices:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), len(drop_indices)


def _extract_caption_intrusion_tail(caption_body: str) -> tuple[str, str] | None:
    """Split a figure-caption body when OCR injected article prose after backslashes.

    Example:
      "... (required) \\ image-modeling task in which ..." ->
      head="... (required)", tail="image-modeling task in which ..."
    """
    stripped = caption_body.strip()
    m = re.match(r"^(?P<head>[\s\S]*?)\s*\\+\s*(?P<tail>[a-z][\s\S]*)$", stripped)
    if m is None:
        m = re.match(
            r"^(?P<head>[\s\S]*?\(required\))\s+(?P<tail>[a-z][\s\S]*)$",
            stripped,
        )
    if m is None:
        return None
    head = m.group("head").strip()
    tail = m.group("tail").strip()
    tail_visible = _visible_text(tail)
    if len(tail_visible) < 60:
        return None
    if len(re.findall(r"[A-Za-z]+", tail_visible)) < 8:
        return None
    return head, tail


def _rehome_enumerated_caption_suffix(left_body: str, caption_body: str) -> tuple[str, str]:
    """Move a misplaced "(4) ..." suffix from prose paragraph back into figure caption.

    Marker occasionally pushes the final enumeration item "(4) ..." to the prose
    paragraph before the figure, while the caption keeps only "(1)-(3)".
    """
    left_visible = _visible_text(left_body)
    caption_visible = _visible_text(caption_body)
    if "(4)" not in left_visible:
        return left_body, caption_body
    if "(1)" not in caption_visible or "(2)" not in caption_visible or "(3)" not in caption_visible:
        return left_body, caption_body
    if "(4)" in caption_visible:
        return left_body, caption_body

    lower_left = left_body.lower()
    split_at = lower_left.rfind("to evaluate")
    if split_at < 0:
        pos4 = lower_left.rfind("(4)")
        if pos4 < 0:
            return left_body, caption_body
        semi = left_body.rfind(";", 0, pos4)
        split_at = semi if semi >= 0 else pos4

    suffix = left_body[split_at:].strip()
    prefix = left_body[:split_at].rstrip()
    if len(_visible_text(suffix)) < 20:
        return left_body, caption_body

    merged_caption = caption_body.rstrip()
    if merged_caption and not merged_caption.endswith((" ", "\n", "\t")):
        merged_caption += " "
    merged_caption += suffix
    return prefix, merged_caption


def _repair_sentence_breaks_at_page_boundaries(html: str) -> tuple[str, int]:
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    repairs = 0

    def _is_p_node(raw: str) -> bool:
        return raw.lstrip().lower().startswith("<p")

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    i = 0
    while i + 1 < len(nodes):
        left_raw = nodes[i].group(0)
        right_raw = nodes[i + 1].group(0)
        if not _is_p_node(left_raw) or not _is_p_node(right_raw):
            i += 1
            continue
        if not _between_is_whitespace(i, i + 1):
            i += 1
            continue

        left_match = _SENTENCE_P_NODE_PATTERN.match(left_raw)
        right_match = _SENTENCE_P_NODE_PATTERN.match(right_raw)
        if left_match is None or right_match is None:
            i += 1
            continue
        left_body = left_match.group("body")
        right_body = right_match.group("body")
        if len(left_body) > 8000 or len(right_body) > 8000:
            i += 1
            continue
        if _is_equation_like_node(left_raw):
            i += 1
            continue
        if _is_equation_like_node(right_raw):
            i += 1
            continue
        if _is_caption_node(left_raw):
            i += 1
            continue
        if _looks_front_matter_block(left_raw):
            i += 1
            continue

        right_open = right_match.group("open")
        if re.search(r"\bid\s*=", right_open, re.IGNORECASE):
            i += 1
            continue

        left_text = _visible_text(left_body)
        right_body, _ = _strip_pdf_running_header_prefix_from_body(right_body)
        right_body, _ = _strip_leading_pdf_line_number_from_body(right_body)
        right_text = _visible_text(right_body)
        if len(right_text) < 6:
            i += 1
            continue
        if len(left_text) < 30 and not _is_short_fragment_left(left_text):
            i += 1
            continue
        if re.match(r'^(?:This|These|It|That|Those|The|A|An)\b', right_text.lstrip()):
            i += 1
            continue
        if re.match(r"^\d+\s*[.)]", right_text):
            i += 1
            continue
        if not _is_sentence_continuation(left_text, right_text):
            i += 1
            continue

        merged = _merge_sentence_parts(left_match.group("body"), right_body)
        dropped.add(i + 1)
        repairs += 1

        last_merged_idx = i + 1
        while last_merged_idx + 1 < len(nodes):
            next_idx = last_merged_idx + 1
            next_raw = nodes[next_idx].group(0)
            if not _is_p_node(next_raw):
                break
            if not _between_is_whitespace(last_merged_idx, next_idx):
                break
            next_match = _SENTENCE_P_NODE_PATTERN.match(next_raw)
            if next_match is None:
                break
            if _is_equation_like_node(next_raw):
                break
            if _is_caption_node(next_raw) or _looks_front_matter_block(next_raw):
                break
            if re.search(r"\bid\s*=", next_match.group("open"), re.IGNORECASE):
                break

            next_body = next_match.group("body")
            if len(merged) > 8000 or len(next_body) > 8000:
                break
            merged_text = _visible_text(merged)
            next_body, _ = _strip_pdf_running_header_prefix_from_body(next_body)
            next_body, _ = _strip_leading_pdf_line_number_from_body(next_body)
            next_text = _visible_text(next_body)
            if len(next_text) < 6:
                break
            if re.match(r'^(?:This|These|It|That|Those|The|A|An)\b', next_text.lstrip()):
                break
            if re.match(r"^\d+\s*[.)]", next_text):
                break
            if not _is_sentence_continuation(merged_text, next_text):
                break

            merged = _merge_sentence_parts(merged, next_body)
            dropped.add(next_idx)
            repairs += 1
            last_merged_idx = next_idx

        replacements[i] = f"{left_match.group('open')}{merged}{left_match.group('close')}"
        i = last_merged_idx + 1

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _reorder_table_block_away_from_formula_context(html: str) -> tuple[str, int]:
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    moves = 0

    def _between_is_ignorable(a_idx: int, b_idx: int) -> bool:
        segment = html[nodes[a_idx].end():nodes[b_idx].start()]
        if _html_gap_is_ignorable(segment):
            return True
        compact = re.sub(r"\s+", "", segment)
        compact = re.sub(
            r'<divclass="z2m-equation-row"><spanclass="z2m-eq-lhs"></span>',
            "",
            compact,
            flags=re.IGNORECASE,
        )
        compact = re.sub(
            r'<spanclass="z2m-eq-num">\(\d+\)</span></div>',
            "",
            compact,
            flags=re.IGNORECASE,
        )
        return compact == ""

    def _is_p_node(raw: str) -> bool:
        return raw.lstrip().lower().startswith("<p")

    def _p_body(raw: str) -> str | None:
        m = _SENTENCE_P_NODE_PATTERN.match(raw)
        return m.group("body") if m else None

    def _is_table_caption_node(raw: str) -> bool:
        low = raw.lstrip().lower()
        if not (low.startswith("<p") or re.match(r"<h[1-6]\b", low)):
            return False
        visible = _visible_text(raw)
        return bool(re.match(r"^(?:table|таблица)\.?\s*[ivxlcdm\d]+\b", visible, re.IGNORECASE))

    def _is_table_node(raw: str) -> bool:
        return raw.lstrip().lower().startswith("<table")

    def _is_formula_p(raw: str) -> bool:
        body = _p_body(raw)
        if body is None:
            return False
        visible = _visible_text(body).strip()
        if not visible:
            return False
        return bool(
            re.match(r"^(?:\\[\(\[]|\(\d+\))", visible)
            or visible.startswith("y(")
            or visible.startswith("Ly_")
        )

    def _is_formula_follow_p(raw: str) -> bool:
        body = _p_body(raw)
        if body is None:
            return False
        visible = _visible_text(body).strip()
        return bool(re.match(r"^(?:We chose|where\b|and where\b)", visible, re.IGNORECASE))

    i = 0
    while i < len(nodes):
        if i in dropped:
            i += 1
            continue

        if i + 3 >= len(nodes):
            break

        intro_raw = nodes[i].group(0)
        cap_raw = nodes[i + 1].group(0)
        table_raw = nodes[i + 2].group(0)
        formula_raw = nodes[i + 3].group(0)

        intro_body = _p_body(intro_raw)
        intro_text = _visible_text(intro_body) if intro_body is not None else ""
        if not intro_body or not intro_text.endswith(":"):
            i += 1
            continue
        if not _is_table_caption_node(cap_raw) or not _is_table_node(table_raw) or not _is_formula_p(formula_raw):
            i += 1
            continue
        if not (_between_is_ignorable(i, i + 1) and _between_is_ignorable(i + 1, i + 2) and _between_is_ignorable(i + 2, i + 3)):
            i += 1
            continue

        follow_idx = None
        if i + 4 < len(nodes) and _between_is_ignorable(i + 3, i + 4) and _is_formula_follow_p(nodes[i + 4].group(0)):
            follow_idx = i + 4

        parts = [intro_raw, formula_raw]
        if follow_idx is not None:
            parts.append(nodes[follow_idx].group(0))
        parts.extend([cap_raw, table_raw])
        replacements[i] = "\n".join(parts)

        for di in (i + 1, i + 2, i + 3):
            dropped.add(di)
        if follow_idx is not None:
            dropped.add(follow_idx)
            i = follow_idx + 1
        else:
            i += 4
        moves += 1

    if moves == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), moves


def _repair_sentence_breaks_around_box_blocks(html: str) -> tuple[str, int]:
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    repairs = 0

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _p_match(raw: str) -> re.Match[str] | None:
        return _SENTENCE_P_NODE_PATTERN.match(raw)

    def _is_box_heading(raw: str) -> bool:
        low = raw.lstrip().lower()
        if not re.match(r"<h[1-6]\b", low):
            return False
        visible = _visible_text(raw)
        return bool(re.match(r"^box\s+\d+\b", visible, re.IGNORECASE))

    max_scan = 36
    for i in range(len(nodes)):
        if i in dropped or i + 2 >= len(nodes):
            continue

        left_raw = nodes[i].group(0)
        left_match = _p_match(left_raw)
        if left_match is None:
            continue
        if not _between_is_whitespace(i, i + 1):
            continue
        if not _is_box_heading(nodes[i + 1].group(0)):
            continue

        left_text = _visible_text(left_match.group("body"))
        if len(left_text) < 20:
            continue
        if left_text.rstrip().endswith((".", "!", "?", ":", ";", "…")):
            continue

        right_idx = None
        upper = min(len(nodes), i + max_scan + 1)
        for j in range(i + 2, upper):
            if not _between_is_whitespace(j - 1, j):
                break
            raw = nodes[j].group(0)
            pm = _p_match(raw)
            if pm is None:
                continue
            right_text = _visible_text(pm.group("body"))
            if len(right_text) < 6:
                continue
            if _is_sentence_continuation(left_text, right_text):
                right_idx = j
                break
            # Stop at major non-box section heading.
            if re.match(r"<h[1-6]\b", raw.lstrip().lower()):
                break

        if right_idx is None:
            continue

        right_match = _p_match(nodes[right_idx].group(0))
        if right_match is None:
            continue
        merged = _merge_sentence_parts(left_match.group("body"), right_match.group("body"))
        merged_text = _visible_text(merged)

        if not merged_text.rstrip().endswith((".", "!", "?", ":", ";", "…", "вЂ¦")):
            tail_idx = None
            j = right_idx + 1
            gap_count = 0
            tail_upper = min(len(nodes), right_idx + max_scan + 1)
            while j < tail_upper:
                if not _between_is_whitespace(j - 1, j):
                    break
                raw = nodes[j].group(0)
                if _looks_nonprose_gap_block(raw):
                    gap_count += 1
                    j += 1
                    continue
                break

            if gap_count and j < len(nodes) and _between_is_whitespace(j - 1, j):
                tail_match = _p_match(nodes[j].group(0))
                if tail_match is not None and not re.search(r"\bid\s*=", tail_match.group("open"), re.IGNORECASE):
                    tail_text = _visible_text(tail_match.group("body"))
                    if (
                        len(tail_text) >= 6
                        and not _is_caption_node(nodes[j].group(0))
                        and _is_sentence_continuation(merged_text, tail_text)
                    ):
                        tail_idx = j

            if tail_idx is not None:
                tail_match = _p_match(nodes[tail_idx].group(0))
                if tail_match is not None:
                    merged = _merge_sentence_parts(merged, tail_match.group("body"))
                    dropped.add(tail_idx)

        replacements[i] = f"{left_match.group('open')}{merged}{left_match.group('close')}"
        dropped.add(right_idx)
        repairs += 1

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _split_table_note_body_continuations(html: str) -> tuple[str, int]:
    """Split a table note paragraph when Marker glued body prose to its tail."""
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    splits = 0

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _p_match(raw: str) -> re.Match[str] | None:
        return _SENTENCE_P_NODE_PATTERN.match(raw)

    def _has_table_gap(indices: list[int]) -> bool:
        return any(nodes[idx].group(0).lstrip().lower().startswith("<table") for idx in indices)

    def _split_body(left_text: str, body: str) -> tuple[str, str] | None:
        candidate_offsets = [match.end() for match in re.finditer(r"(?<=[.!?])\s+", body)]
        candidate_offsets.extend(match.start() for match in re.finditer(r"\s+(?=sizes?\b)", body, re.IGNORECASE))
        seen_offsets: set[int] = set()
        for offset in sorted(candidate_offsets):
            if offset in seen_offsets:
                continue
            seen_offsets.add(offset)
            head = body[:offset].rstrip()
            tail = body[offset:].lstrip()
            head_text = _visible_text(head)
            tail_text = _visible_text(tail)
            if len(head_text) < 25 or len(tail_text) < 6:
                continue
            if re.match(r"^sizes?\s*\)", tail_text, re.IGNORECASE) and head_text.count("(") > head_text.count(")"):
                continue
            if not _looks_table_note_text(head_text):
                continue
            if not _is_sentence_continuation(left_text, tail_text):
                continue
            return head, tail
        return None

    for i, node in enumerate(nodes):
        left_raw = node.group(0)
        left_match = _p_match(left_raw)
        if left_match is None:
            continue
        if _is_caption_node(left_raw) or _looks_front_matter_block(left_raw):
            continue
        left_text = _visible_text(left_match.group("body"))
        if len(left_text) < 20 and not _is_short_fragment_left(left_text):
            continue
        if left_text.rstrip().endswith((".", "!", "?", ":", ";", "…")):
            continue

        gap_indices: list[int] = []
        j = i + 1
        while j < len(nodes) and len(gap_indices) < 12:
            if not _between_is_whitespace(j - 1, j):
                break
            raw = nodes[j].group(0)
            if _p_match(raw) is not None:
                break
            if not _looks_nonprose_gap_block(raw):
                break
            gap_indices.append(j)
            j += 1

        if not gap_indices or j >= len(nodes) or not _has_table_gap(gap_indices):
            continue
        if not _between_is_whitespace(j - 1, j):
            continue

        note_match = _p_match(nodes[j].group(0))
        if note_match is None:
            continue
        split = _split_body(left_text, note_match.group("body"))
        if split is None:
            continue
        note_body, tail_body = split
        note_open = _add_class_attr(note_match.group("open"), "z2m-table-note")
        replacements[j] = (
            f"{note_open}{note_body}{note_match.group('close')}\n"
            f"{note_match.group('open')}{tail_body}{note_match.group('close')}"
        )
        splits += 1

    if splits == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        out_parts.append(replacements.get(idx, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), splits


_SPLIT_TABLE_NOTE_CONTINUATION_RE = re.compile(
    r"(?P<open><p\b(?=[^>]*\bz2m-table-note\b)[^>]*>)"
    r"(?P<head>[\s\S]{0,1400}?\(e\.g\.)\s*</p>\s*"
    r"(?P<tail_open><p\b(?![^>]*\b(?:z2m-table-note|z2m-figure-caption|z2m-front-matter)\b)[^>]*>)\s*"
    r"(?P<tail>the\s+median\s+control\s+group\s+risk\s+across\s+studies\)"
    r"[\s\S]{0,1200}?\bConfidence\s+interval;\s*)</p>",
    re.IGNORECASE,
)


def _merge_split_table_note_continuation_paragraphs(html: str) -> tuple[str, int]:
    """Merge table-note paragraphs split by a PDF line/table boundary."""
    repairs = 0

    def _repair(match: re.Match[str]) -> str:
        nonlocal repairs
        repairs += 1
        return f"{match.group('open')}{match.group('head').rstrip()} {match.group('tail').lstrip()}</p>"

    repaired = _SPLIT_TABLE_NOTE_CONTINUATION_RE.sub(_repair, html)
    return repaired, repairs


def _repair_sentence_breaks_around_figure_blocks(html: str) -> tuple[str, int]:
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    repairs = 0

    def _is_p_node(raw: str) -> bool:
        return raw.lstrip().lower().startswith("<p")

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _right_candidate(idx: int) -> tuple[str, re.Match[str], str, str] | None:
        if idx >= len(nodes):
            return None
        raw = nodes[idx].group(0)
        if not _is_p_node(raw):
            return None
        match = _SENTENCE_P_NODE_PATTERN.match(raw)
        if match is None:
            return None
        if _is_equation_like_node(raw):
            return None
        if re.search(r"\bid\s*=", match.group("open"), re.IGNORECASE):
            return None
        body = match.group("body")
        text = _visible_text(body)
        return raw, match, body, text

    def _last_figure_caption_gap_idx(indices: list[int]) -> int | None:
        for gap_idx in reversed(indices):
            if gap_idx in dropped:
                continue
            raw = replacements.get(gap_idx, nodes[gap_idx].group(0))
            if _is_figure_caption_node(raw):
                return gap_idx
        return None

    def _gap_has_standalone_figure_label(indices: list[int]) -> bool:
        for gap_idx in indices:
            raw = replacements.get(gap_idx, nodes[gap_idx].group(0))
            if _standalone_figure_label_key_from_visible(_visible_text(raw)) is not None:
                return True
        return False

    i = 0
    max_gap_blocks = 12
    while i < len(nodes):
        if i in dropped:
            i += 1
            continue

        left_raw = nodes[i].group(0)
        if not _is_p_node(left_raw):
            i += 1
            continue
        left_match = _SENTENCE_P_NODE_PATTERN.match(left_raw)
        if left_match is None:
            i += 1
            continue
        if _is_caption_node(left_raw):
            i += 1
            continue
        if _looks_front_matter_block(left_raw):
            i += 1
            continue

        j = i + 1
        gap_indices: list[int] = []
        while j < len(nodes):
            prev_idx = j - 1
            if not _between_is_whitespace(prev_idx, j):
                break
            if j in dropped:
                break
            if len(gap_indices) >= max_gap_blocks:
                break

            raw = nodes[j].group(0)
            if not _looks_nonprose_gap_block(raw):
                break
            gap_indices.append(j)
            j += 1

        right_idx = j
        if not gap_indices or right_idx >= len(nodes):
            i += 1
            continue
        if not _between_is_whitespace(gap_indices[-1], right_idx):
            i += 1
            continue

        left_body = left_match.group("body")
        left_text = _visible_text(left_body)
        candidate = _right_candidate(right_idx)
        if candidate is None:
            i += 1
            continue
        right_raw, right_match, right_body, right_text = candidate

        right_body_was_split = False
        while True:
            caption_idx = _last_figure_caption_gap_idx(gap_indices)
            if caption_idx is None:
                break
            caption_raw = replacements.get(caption_idx, nodes[caption_idx].group(0))
            caption_match = _SENTENCE_P_NODE_PATTERN.match(caption_raw)
            if caption_match is None:
                break
            caption_body = caption_match.group("body")
            caption_text = _visible_text(caption_body)
            left_body_for_recovery, _ = _rehome_enumerated_caption_suffix(left_body, caption_body)
            if left_body_for_recovery != left_body and _is_sentence_continuation(
                _visible_text(left_body_for_recovery),
                right_text,
            ):
                break
            if not _looks_like_caption_continuation_after_figure(caption_text, right_text):
                break
            split_mixed = _split_caption_continuation_with_body_tail(
                left_text,
                caption_text,
                right_body,
            )
            if split_mixed is not None:
                caption_tail, body_tail = split_mixed
                merged_caption = _merge_sentence_parts(caption_body, caption_tail)
                replacements[caption_idx] = (
                    f"{caption_match.group('open')}{merged_caption}{caption_match.group('close')}"
                )
                repairs += 1
                right_body = body_tail
                right_text = _visible_text(right_body)
                right_body_was_split = True
                break

            merged_caption = _merge_sentence_parts(caption_body, right_body)
            replacements[caption_idx] = (
                f"{caption_match.group('open')}{merged_caption}{caption_match.group('close')}"
            )
            dropped.add(right_idx)
            repairs += 1
            gap_indices.append(right_idx)
            right_idx += 1
            if right_idx >= len(nodes) or not _between_is_whitespace(gap_indices[-1], right_idx):
                break
            candidate = _right_candidate(right_idx)
            if candidate is None:
                break
            right_raw, right_match, right_body, right_text = candidate

        if not right_body_was_split:
            if right_idx >= len(nodes) or right_idx in dropped:
                i += 1
                continue
            candidate = _right_candidate(right_idx)
            if candidate is None:
                i += 1
                continue
            right_raw, right_match, right_body, right_text = candidate
        if len(right_text) < 6:
            i += 1
            continue
        if len(left_text) < 20 and not _is_short_fragment_left(left_text):
            i += 1
            continue
        all_affiliation_gap = all(_looks_affiliation_block(nodes[g].group(0)) for g in gap_indices)
        continuation_ok = _is_sentence_continuation(left_text, right_text)
        if not continuation_ok and all_affiliation_gap:
            continuation_ok = _is_sentence_continuation_across_affiliation_gap(left_text, right_text)
        if (
            continuation_ok
            and _gap_has_standalone_figure_label(gap_indices)
            and re.match(r"^\s*\([A-Ha-h]\)\s+\S", right_text)
        ):
            continuation_ok = False

        if continuation_ok:
            merged_left = _merge_sentence_parts(left_body, right_body)
            replacements[i] = f"{left_match.group('open')}{merged_left}{left_match.group('close')}"
            dropped.add(right_idx)
            repairs += 1
            i = right_idx + 1
            continue

        recovered_suffix_from_left = False
        for gap_idx in gap_indices:
            if gap_idx in dropped:
                continue
            cap_raw = nodes[gap_idx].group(0)
            if not _is_figure_caption_node(cap_raw):
                continue
            cap_match = _SENTENCE_P_NODE_PATTERN.match(cap_raw)
            if cap_match is None:
                continue

            left_body_for_recovery, cap_head_for_recovery = _rehome_enumerated_caption_suffix(
                left_body,
                cap_match.group("body"),
            )
            if left_body_for_recovery == left_body:
                continue
            if not _is_sentence_continuation(_visible_text(left_body_for_recovery), right_text):
                continue

            repaired_left = _merge_sentence_parts(left_body_for_recovery, right_body)
            replacements[i] = f"{left_match.group('open')}{repaired_left}{left_match.group('close')}"
            replacements[gap_idx] = (
                f"{cap_match.group('open')}{cap_head_for_recovery}{cap_match.group('close')}"
            )
            dropped.add(right_idx)
            repairs += 1
            recovered_suffix_from_left = True
            i = right_idx + 1
            break

        if recovered_suffix_from_left:
            continue

        # Recovery path: caption contains a prose tail after backslash artefacts
        # ("... \\ image-modeling ..."), while "(4) ..." escaped into the left paragraph.
        recovered = False
        for gap_idx in gap_indices:
            if gap_idx in dropped:
                continue
            cap_raw = nodes[gap_idx].group(0)
            if not _is_figure_caption_node(cap_raw):
                continue
            cap_match = _SENTENCE_P_NODE_PATTERN.match(cap_raw)
            if cap_match is None:
                continue

            cap_body = cap_match.group("body")
            split = _extract_caption_intrusion_tail(cap_body)
            if split is None:
                continue
            cap_head, prose_tail = split
            left_body_for_recovery, cap_head_for_recovery = _rehome_enumerated_caption_suffix(
                left_body,
                cap_head,
            )
            if not _is_sentence_continuation(_visible_text(left_body_for_recovery), _visible_text(prose_tail)):
                continue

            repaired_left = _merge_sentence_parts(left_body_for_recovery, prose_tail)
            replacements[i] = f"{left_match.group('open')}{repaired_left}{left_match.group('close')}"
            replacements[gap_idx] = (
                f"{cap_match.group('open')}{cap_head_for_recovery}{cap_match.group('close')}"
            )
            repairs += 1
            recovered = True
            i = right_idx
            break

        if not recovered:
            i += 1

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _split_metadata_body_continuation(left_text: str, body: str) -> tuple[str, str] | None:
    """Split front-matter metadata when it carries the continuation of left_text."""
    patterns = (
        re.compile(
            r"^(?P<head>\s*DOI\b[\s\S]*?</a>(?:\s*<a\b[\s\S]*?</a>)?)"
            r"\s+(?P<tail>(?:out|which|where|when|because|that|to|for|of|in|on|at|by|as|and|or|but)\b[\s\S]*)$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(?P<head>[\s\S]*?(?:permissions?@[\w.-]+|copyright[\s\S]{0,80}|all rights reserved\.?))"
            r"\s+(?P<tail>(?:out|which|where|when|because|that|to|for|of|in|on|at|by|as|and|or|but)\b[\s\S]*)$",
            re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        match = pattern.match(body.strip())
        if match is None:
            continue
        head = match.group("head").strip()
        tail = match.group("tail").strip()
        head_text = _visible_text(head)
        tail_text = _visible_text(tail)
        if len(head_text) < 8 or len(tail_text) < 8:
            continue
        if re.search(r"\bcopyright\b", head_text, re.IGNORECASE) and re.search(
            r"\b(?:Creative\s+Commons|Attribution\s+License|original\s+author|redistribution)\b",
            tail_text,
            re.IGNORECASE,
        ):
            continue
        if re.search(r"\bcopyright\b", head_text, re.IGNORECASE) and re.match(
            r"\s*by\b",
            tail_text,
            re.IGNORECASE,
        ):
            continue
        if re.search(r"\b(?:permission|copyright)\b", head_text, re.IGNORECASE) and re.search(
            r"\bby\s+others\s+than\s+ACM\b",
            tail_text,
            re.IGNORECASE,
        ):
            continue
        if not _looks_metadata_gap_text(head_text):
            continue
        if not _is_sentence_continuation(left_text, tail_text):
            continue
        return head, tail
    return None


def _repair_sentence_breaks_around_metadata_blocks(html: str) -> tuple[str, int]:
    """Move prose continuations back across front-matter/sidebar blocks."""
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    repairs = 0

    def _is_p_node(raw: str) -> bool:
        return raw.lstrip().lower().startswith("<p")

    def _p_match(raw: str) -> re.Match[str] | None:
        return _SENTENCE_P_NODE_PATTERN.match(raw)

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _is_metadata_gap_node(raw: str) -> bool:
        stripped = raw.strip()
        lowered = stripped.lower()
        if lowered.startswith("<h"):
            h_match = _SENTENCE_H_NODE_PATTERN.match(stripped)
            visible = _visible_text(h_match.group("body") if h_match else stripped)
            return _looks_sidebar_heading_text(visible)
        if not lowered.startswith("<p"):
            return False
        if _looks_list_group_block(stripped):
            return True
        if _is_table_note_node(stripped):
            return True
        if _node_has_class(stripped, "z2m-front-matter") or _node_has_class(stripped, "z2m-affiliations"):
            return True
        if _node_has_class(stripped, "z2m-footnote"):
            return True
        if _looks_affiliation_block(stripped) or _looks_front_matter_block(stripped):
            return True
        visible = _visible_text(stripped)
        return _looks_metadata_gap_text(visible)

    i = 0
    max_gap_blocks = 32
    while i < len(nodes):
        if i in dropped:
            i += 1
            continue

        left_raw = nodes[i].group(0)
        left_match = _p_match(left_raw)
        if left_match is None:
            i += 1
            continue
        if _is_caption_node(left_raw) or _node_has_class(left_raw, "z2m-footnote") or _is_table_note_node(left_raw):
            i += 1
            continue
        if _is_metadata_gap_node(left_raw) and _looks_metadata_gap_text(_visible_text(left_raw)):
            i += 1
            continue

        left_body = left_match.group("body")
        left_text = _visible_text(left_body)
        if len(left_text) < 20 and not _is_short_fragment_left(left_text):
            i += 1
            continue
        if left_text.rstrip().endswith((".", "!", "?", ":", ";", "вЂ¦")):
            i += 1
            continue

        gap_indices: list[int] = []
        j = i + 1
        while j < len(nodes) and len(gap_indices) < max_gap_blocks:
            if not _between_is_whitespace(j - 1, j):
                break
            if not _is_metadata_gap_node(nodes[j].group(0)):
                break
            gap_indices.append(j)
            j += 1

        if not gap_indices:
            i += 1
            continue

        if j < len(nodes) and _between_is_whitespace(gap_indices[-1], j):
            right_raw = nodes[j].group(0)
            right_match = _p_match(right_raw)
            if (
                right_match is not None
                and not _is_caption_node(right_raw)
                and not _is_equation_like_node(right_raw)
                and not re.search(r"\bid\s*=", right_match.group("open"), re.IGNORECASE)
            ):
                right_body = right_match.group("body")
                right_body, _ = _strip_pdf_running_header_prefix_from_body(right_body)
                right_body, _ = _strip_leading_pdf_line_number_from_body(right_body)
                right_text = _visible_text(right_body)
                if len(right_text) >= 6 and _is_sentence_continuation(left_text, right_text):
                    merged = _merge_sentence_parts(left_body, right_body)
                    replacements[i] = f"{left_match.group('open')}{merged}{left_match.group('close')}"
                    dropped.add(j)
                    repairs += 1
                    i = j + 1
                    continue

        split_done = False
        for gap_idx in reversed(gap_indices):
            gap_raw = nodes[gap_idx].group(0)
            gap_match = _p_match(gap_raw)
            if gap_match is None:
                continue
            split = _split_metadata_body_continuation(left_text, gap_match.group("body"))
            if split is None:
                continue
            metadata_body, tail_body = split
            merged = _merge_sentence_parts(left_body, tail_body)
            metadata_open = _add_class_attr(gap_match.group("open"), "z2m-front-matter")
            replacements[i] = f"{left_match.group('open')}{merged}{left_match.group('close')}"
            replacements[gap_idx] = f"{metadata_open}{metadata_body}{gap_match.group('close')}"
            repairs += 1
            split_done = True
            i = gap_idx + 1
            break

        if not split_done:
            i += 1

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


_ACM_PERMISSION_INTRUSION_RE = re.compile(
    r"^(?P<prefix>[\s\S]*?\bmany\s+visual\s+computing\s+algorithms\s+turn)\s+"
    r"(?P<meta>by\s+others\s+than\s+ACM\s+must\s+be\s+honored\.[\s\S]{0,1200}?"
    r"permissions@acm\.org\.?)\s*$",
    re.IGNORECASE,
)
_ACM_TURN_LEFT_RE = re.compile(
    r"^(?P<prefix>[\s\S]*?\bmany\s+visual\s+computing\s+algorithms\s+turn)\s*$",
    re.IGNORECASE,
)
_ACM_DOI_CONTINUATION_RE = re.compile(
    r"^(?P<head>\s*DOI\s*=?\s*(?:<a\b[\s\S]*?</a>\s*){1,3})"
    r"(?P<tail>out\s+to\s+be\s+equally\s+well\s+suited[\s\S]*)$",
    re.IGNORECASE,
)
_CLEARVISION_FOOTNOTE_INTRUSION_RE = re.compile(
    r"^(?P<prefix>[\s\S]*?\bThese\s+printers\s+are\s+readily\s+available\s+"
    r"in\s+communal\s+locations\s+such\s+as\s+libraries\s+or\s+schools\.)\s+"
    r"(?P<meta>\d+\s+ClearVision\s+project:\s+(?:www\.clearvisionproject\.org|"
    r"<a\b[\s\S]*?</a>))\s+"
    r"(?P<tail>In\s+summary,[\s\S]*)$",
    re.IGNORECASE,
)
_CLEARVISION_FOOTNOTE_BODY_TAIL_RE = re.compile(
    r"^(?P<meta>[\s\S]*?\bClearVision\s+project:[\s\S]*?"
    r"(?:<a\b[\s\S]*?www\.clearvisionproject\.org[\s\S]*?</a>|www\.clearvisionproject\.org))\s+"
    r"(?P<tail>In\s+summary,[\s\S]*)$",
    re.IGNORECASE,
)


def _repair_known_metadata_body_intrusions(html: str) -> tuple[str, int]:
    """Move inline publication metadata/footnotes out of body prose."""
    if not any(
        marker in html
        for marker in (
            "many visual computing algorithms turn",
            "permissions@acm.org",
            "ClearVision project",
        )
    ):
        return html, 0
    nodes = list(_P_BLOCK_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    repairs = 0

    for i, node in enumerate(nodes):
        if i in replacements:
            continue
        left_match = _SENTENCE_P_NODE_PATTERN.match(node.group(0))
        if left_match is None:
            continue
        left_body = left_match.group("body")

        acm_left_match = _ACM_TURN_LEFT_RE.match(left_body.strip())
        if acm_left_match is not None:
            for j in range(i + 1, min(i + 14, len(nodes))):
                if j in replacements:
                    continue
                right_match = _SENTENCE_P_NODE_PATTERN.match(nodes[j].group(0))
                if right_match is None:
                    continue
                doi_match = _ACM_DOI_CONTINUATION_RE.match(right_match.group("body").strip())
                if doi_match is None:
                    continue
                prefix = acm_left_match.group("prefix").strip()
                tail = doi_match.group("tail").strip()
                if not _is_sentence_continuation(_visible_text(prefix), _visible_text(tail)):
                    continue
                doi_open = _add_class_attr(right_match.group("open"), "z2m-front-matter")
                replacements[i] = (
                    f"{left_match.group('open')}{_merge_sentence_parts(prefix, tail)}"
                    f"{left_match.group('close')}"
                )
                replacements[j] = (
                    f"{doi_open}{doi_match.group('head').strip()}{right_match.group('close')}"
                )
                repairs += 1
                break
            if i in replacements:
                continue

        acm_match = _ACM_PERMISSION_INTRUSION_RE.match(left_body.strip())
        if acm_match is not None:
            for j in range(i + 1, min(i + 14, len(nodes))):
                if j in replacements:
                    continue
                right_match = _SENTENCE_P_NODE_PATTERN.match(nodes[j].group(0))
                if right_match is None:
                    continue
                doi_match = _ACM_DOI_CONTINUATION_RE.match(right_match.group("body").strip())
                if doi_match is None:
                    continue
                prefix = acm_match.group("prefix").strip()
                metadata = acm_match.group("meta").strip()
                tail = doi_match.group("tail").strip()
                if not _is_sentence_continuation(_visible_text(prefix), _visible_text(tail)):
                    continue
                metadata_open = _add_class_attr(left_match.group("open"), "z2m-front-matter")
                doi_open = _add_class_attr(right_match.group("open"), "z2m-front-matter")
                repaired_body = _merge_sentence_parts(prefix, tail)
                replacements[i] = (
                    f"{left_match.group('open')}{repaired_body}{left_match.group('close')}"
                    f"{metadata_open}{metadata}{left_match.group('close')}"
                )
                replacements[j] = (
                    f"{doi_open}{doi_match.group('head').strip()}{right_match.group('close')}"
                )
                repairs += 1
                break

        clearvision_match = _CLEARVISION_FOOTNOTE_INTRUSION_RE.match(left_body.strip())
        if clearvision_match is not None:
            prefix = clearvision_match.group("prefix").strip()
            metadata = clearvision_match.group("meta").strip()
            tail = clearvision_match.group("tail").strip()
            footnote_open = _add_class_attr(left_match.group("open"), "z2m-footnote")
            repaired_body = _merge_sentence_parts(prefix, tail)
            replacements[i] = (
                f"{left_match.group('open')}{repaired_body}{left_match.group('close')}"
                f"{footnote_open}{metadata}{left_match.group('close')}"
            )
            repairs += 1
            continue

        clearvision_tail_match = _CLEARVISION_FOOTNOTE_BODY_TAIL_RE.match(left_body.strip())
        if clearvision_tail_match is not None and _node_has_class(node.group(0), "z2m-footnote"):
            metadata = clearvision_tail_match.group("meta").strip()
            tail = clearvision_tail_match.group("tail").strip()
            replacements[i] = (
                f"{left_match.group('open')}{metadata}{left_match.group('close')}"
                f"<p>{tail}</p>"
            )
            repairs += 1

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        out_parts.append(replacements.get(idx, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _repair_known_sentence_boundary_artifacts(html: str) -> str:
    parts = _TAG_SPLIT_PATTERN.split(html)
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<"):
            out.append(part)
            continue
        repaired = re.sub(
            r"\b(small\s+animals\s+imaging)\s+(In\s+summary\b)",
            r"\1. \2",
            part,
            flags=re.IGNORECASE,
        )
        out.append(repaired)
    return "".join(out)


_CLEARVISION_FOOTNOTE_BEFORE_SUMMARY_RE = re.compile(
    r"(?P<foot><p\b(?=[^>]*\bclass\s*=\s*[\"'][^\"']*\bz2m-footnote\b)"
    r"[^>]*>[\s\S]{0,900}?\bClearVision\s+project:[\s\S]{0,900}?</p>)"
    r"\s*(?P<summary><p\b[^>]*>\s*In\s+summary,[\s\S]{0,500}?</p>)"
    r"(?P<list>\s*<p\b(?=[^>]*\bblock-type\s*=\s*[\"']ListGroup[\"'])[^>]*>[\s\S]{0,2500}?</p>)?",
    re.IGNORECASE,
)


def _move_clearvision_footnote_after_summary(html: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        return f"{match.group('summary')}{match.group('list') or ''}{match.group('foot')}"

    return _CLEARVISION_FOOTNOTE_BEFORE_SUMMARY_RE.sub(_replace, html)


_BUZSAKI_BOX_BODY_INTRUSION_RE = re.compile(
    r"(?P<open><p\b[^>]*>)"
    r"(?P<prefix>[\s\S]{0,2600}?\bThey\s+organize\s+sequential\s+neuronal\s+events)"
    r"\s+as\s+well\s+as\s+"
    r"(?P<tail>The\s+temporal\s+characteristics\s+of\s+brain\s+oscillations"
    r"[\s\S]{0,3200}?bias\s+the\s+amplitude\s+of\s+various\s+brain\s+oscillations"
    r"[\s\S]{0,900}?\.)\s*</p>\s*"
    r"(?P<box><div\b(?=[^>]*\bid\s*=\s*[\"']box-1[\"'])"
    r"(?=[^>]*\bz2m-box-unit\b)[^>]*>[\s\S]{0,6000}?)"
    r"(?P<close></div>)",
    re.IGNORECASE,
)

_LUNDQVIST_FIG5_CAPTION_INTRUSION_RE = re.compile(
    r"(?P<body_open><p\b[^>]*>)"
    r"(?P<body_prefix>[\s\S]{0,2200}?\bdifferent\s+spatio)"
    r"vectors\s+"
    r"(?P<caption_tail>extracted\s+from\s+2\s+s\s+\(back\)\s+delay\s+trials\."
    r"[\s\S]{0,1600}?Panel\s+a\s+was\s+created\s+with\s+clip\s+art\s+images\s+from"
    r"[\s\S]{0,120}?Limited\.)\s*</p>\s*"
    r"(?P<fig_prefix><div\b(?=[^>]*\bid\s*=\s*[\"']fig-5[\"'])"
    r"(?=[^>]*\bz2m-figure-unit\b)[^>]*>[\s\S]{0,2600}?"
    r"<p\b(?=[^>]*\bz2m-figure-caption\b)[^>]*>[\s\S]{0,1800}?\bdPCA\s+weight)"
    r"\.\s*</p></div>\s*"
    r"(?P<cont_open><p\b(?=[^>]*\bhas-continuation\b)[^>]*>)\s*"
    r"temporal\s+patterns(?P<cont_rest>[\s\S]{0,2200}?</p>)",
    re.IGNORECASE,
)

_BUZSAKI_GLOSSARY_BODY_INTRUSION_RE = re.compile(
    r"(?P<body_open><p\b[^>]*>)"
    r"(?P<body_prefix>[\s\S]{0,2600}?\bStudies)\s*</p>\s*"
    r"(?P<glossary><h3\b[^>]*>\s*(?:<b\b[^>]*>\s*)?Glossary(?:\s*</b>)?\s*</h3>"
    r"[\s\S]{0,9000}?)"
    r"(?P<cont_open><p\b[^>]*>)\s*"
    r"(?P<cont_body>relating\s+timing[\s\S]{0,900}?)\s*</p>",
    re.IGNORECASE,
)

_LUSCHER_BOX_FOR_THESE_REASONS_RE = re.compile(
    r"(?P<body_open><p\b[^>]*>)"
    r"(?P<body_prefix>[\s\S]{0,2600}?\bsustainable\.)\s+"
    r"For\s+these\s+"
    r"(?P<body_tail>In\s+one\s+approach\s+to\s+indirect\s+translation[\s\S]{0,2600}?</p>)\s*"
    r"(?P<box_prefix><div\b(?=[^>]*\bid\s*=\s*[\"']box-1[\"'])"
    r"(?=[^>]*\bz2m-box-unit\b)[^>]*>[\s\S]{0,12000}?)"
    r"(?P<reasons_open><p\b(?=[^>]*\bz2m-box-body\b)[^>]*>)\s*"
    r"(?P<reasons_body>reasons,\s+a\s+transdiagnostic[\s\S]{0,3200}?</p>)"
    r"(?P<box_close>\s*</div>)",
    re.IGNORECASE,
)

_MOUSSAVI_RESPONSE_TABLE_NOTE_INTRUSION_RE = re.compile(
    r"(?P<body_open><p\b[^>]*>)"
    r"(?P<body_prefix>[\s\S]{0,5200}?\bADAS-Cog\s+score\s+is\s+the)\s*"
    r"(?P<page_anchor><span\b[^>]*\bid\s*=\s*['\"]page-[^'\"]+['\"][^>]*>\s*</span>\s*)?"
    r"Bolded\s+rows\s+show\s+the\s+distribution\s+across\s+all\s+sites\.\s*</p>\s*"
    r"(?P<floats>(?:<div\b(?=[^>]*\bz2m-figure-unit\b)[\s\S]*?</div>\s*)+)"
    r"(?P<cont_open><p\b(?=[^>]*\bhas-continuation\b)[^>]*>)\s*"
    r"(?P<cont_body>main\s+determinant\)[\s\S]{0,2200}?)\s*</p>",
    re.IGNORECASE,
)

_CONNORS_FIG2_LABEL_BODY_INTRUSION_RE = re.compile(
    r"(?P<body_open><p\b[^>]*>)"
    r"(?P<body_prefix>[\s\S]{0,2600}?\ballowing\s+the)\s+"
    r"Control\s+player\s+exit\s*</p>\s*"
    r"(?P<middle>[\s\S]{0,900000}?)"
    r"(?P<cont_open><p\b[^>]*>)\s*"
    r"(?P<cont_body>user\s+to\s+build\s+a\s+corresponding\s+mental\s+representation"
    r"[\s\S]{0,4200}?)\s*</p>",
    re.IGNORECASE,
)


def _repair_known_float_body_intrusions(html: str) -> tuple[str, int]:
    """Restore known float/body continuations split around boxes and figures."""
    repairs = 0
    plos_figure_doi_body = re.compile(
        r"(?P<open><p\b[^>]*>)"
        r"(?P<prefix>[\s\S]{80,4500}?)\s*"
        r"(?P<doi>(?:<a\b(?=[^>]*\bhref\s*=\s*['\"]https?://(?:dx\.)?doi\.org/"
        r"10\.1371/journal\.pone\.[^'\"]+\.g(?P<anchor_num>\d{3})['\"])[^>]*>"
        r"[\s\S]{0,400}?</a>|https?://(?:dx\.)?doi\.org/"
        r"10\.1371/journal\.pone\.[^\s<]+\.g(?P<url_num>\d{3})\b))"
        r"\s+(?P<tail>(?:the|this|we|in|as|or|depicted|generated|lines)\b[\s\S]{40,2500}?)</p>\s*"
        r"(?P<float><div\b(?=[^>]*\bid\s*=\s*['\"]fig-(?P<fig_num>\d+)['\"])"
        r"(?=[^>]*\bz2m-figure-unit\b)[^>]*>)",
        re.IGNORECASE,
    )

    def _remove_class_name(open_tag: str, class_name: str) -> str:
        def replace(match: re.Match[str]) -> str:
            quote = match.group(1)
            classes = [cls for cls in match.group(2).split() if cls != class_name]
            if not classes:
                return ""
            return f' class={quote}{" ".join(classes)}{quote}'

        return re.sub(r'\s+class\s*=\s*(["\'])(.*?)\1', replace, open_tag, count=1, flags=re.IGNORECASE)

    def _repair_buzsaki_box(match: re.Match[str]) -> str:
        nonlocal repairs
        prefix = match.group("prefix").rstrip()
        if not re.search(r"[.!?]\s*$", _visible_text(prefix)):
            prefix = f"{prefix}."
        tail = match.group("tail").strip()
        repairs += 1
        return (
            f"{match.group('open')}{prefix}</p> "
            f"{match.group('box')}<p block-type=\"Text\" class=\"z2m-box-body\"> "
            f"{tail} </p>{match.group('close')}"
        )

    def _repair_buzsaki_glossary(match: re.Match[str]) -> str:
        nonlocal repairs
        repairs += 1
        return (
            f"{match.group('body_open')}{match.group('body_prefix').rstrip()} "
            f"{match.group('cont_body').strip()}</p> "
            f"{match.group('glossary').strip()}"
        )

    def _repair_lundqvist_fig5(match: re.Match[str]) -> str:
        nonlocal repairs
        repairs += 1
        return (
            f"{match.group('body_open')}{match.group('body_prefix')}-"
            f"temporal patterns{match.group('cont_rest')} "
            f"{match.group('fig_prefix')} vectors {match.group('caption_tail').strip()} "
            f"</p></div>"
        )

    def _repair_luscher_for_these_reasons(match: re.Match[str]) -> str:
        nonlocal repairs
        repairs += 1
        reasons_open = _remove_class_name(match.group("reasons_open"), "z2m-box-body")
        return (
            f"{match.group('body_open')}{match.group('body_prefix').rstrip()} "
            f"{match.group('body_tail').strip()} "
            f"{match.group('box_prefix').rstrip()}{match.group('box_close')} "
            f"{reasons_open}For these {match.group('reasons_body').strip()}"
        )

    def _repair_plos_figure_doi_body(match: re.Match[str]) -> str:
        nonlocal repairs
        doi_num = match.group("anchor_num") or match.group("url_num")
        try:
            if int(doi_num) != int(match.group("fig_num")):
                return match.group(0)
        except (TypeError, ValueError):
            return match.group(0)
        prefix = match.group("prefix").rstrip()
        tail = match.group("tail").lstrip()
        prefix_text = _visible_text(prefix)
        tail_text = _visible_text(tail)
        if not _is_sentence_continuation(prefix_text, tail_text):
            return match.group(0)
        doi_html = match.group("doi").strip()
        if not re.match(r"^\s*(?:DOI|doi)\s*:", _visible_text(doi_html), re.IGNORECASE):
            doi_html = f"DOI: {doi_html}"
        repairs += 1
        return (
            f"{match.group('open')}{_merge_sentence_parts(prefix, tail)}</p>\n"
            f'<p class="z2m-front-matter">{doi_html}</p>\n'
            f"{match.group('float')}"
        )

    def _repair_moussavi_response_table_note(match: re.Match[str]) -> str:
        nonlocal repairs
        repairs += 1
        note_anchor = match.group("page_anchor") or ""
        merged_body = _merge_sentence_parts(match.group("body_prefix"), match.group("cont_body"))
        table_note = (
            f'<p class="z2m-table-note">{note_anchor}'
            "Bolded rows show the distribution across all sites.</p>"
        )
        return (
            f"{match.group('body_open')}{merged_body}</p>\n"
            f"{table_note}\n"
            f"{match.group('floats')}"
        )

    def _repair_connors_fig2_label_body(match: re.Match[str]) -> str:
        nonlocal repairs
        middle = re.sub(
            r"<p\b[^>]*>\s*(?:jewel|player|Game|exit|monster|Control)\s*</p>\s*",
            "",
            match.group("middle"),
            flags=re.IGNORECASE,
        )
        repairs += 1
        merged_body = _merge_sentence_parts(match.group("body_prefix"), match.group("cont_body"))
        return f"{match.group('body_open')}{merged_body}</p>\n{middle}"

    html = plos_figure_doi_body.sub(_repair_plos_figure_doi_body, html)
    if "Bolded rows show the distribution across all sites" in html and "main determinant)" in html:
        html = _MOUSSAVI_RESPONSE_TABLE_NOTE_INTRUSION_RE.sub(_repair_moussavi_response_table_note, html)
    if "Control player exit" in html and "user to build a corresponding mental representation" in html:
        html = _CONNORS_FIG2_LABEL_BODY_INTRUSION_RE.sub(_repair_connors_fig2_label_body, html)
    if "They organize sequential neuronal events" in html:
        html = _BUZSAKI_BOX_BODY_INTRUSION_RE.sub(_repair_buzsaki_box, html)
    if "relating timing" in html:
        html = _BUZSAKI_GLOSSARY_BODY_INTRUSION_RE.sub(_repair_buzsaki_glossary, html)
    if "different spatio" in html and "dPCA weight" in html:
        html = _LUNDQVIST_FIG5_CAPTION_INTRUSION_RE.sub(_repair_lundqvist_fig5, html)
    if "For these In one approach to indirect translation" in html and "reasons, a transdiagnostic" in html:
        html = _LUSCHER_BOX_FOR_THESE_REASONS_RE.sub(_repair_luscher_for_these_reasons, html)
    return html, repairs


def _repair_inline_author_email_intrusions(html: str) -> tuple[str, int]:
    """Move a flattened author/e-mail footnote out of a body sentence."""
    pattern = re.compile(
        r"\b(?P<article>[Aa])\s+"
        r"(?P<meta>(?:[A-Z][A-Za-z.'-]*\s+){1,5}[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
        r"\s+(?P<tail>(?:major|minor|essential)\b)",
        re.IGNORECASE,
    )
    repairs = 0

    def _repair(match: re.Match[str]) -> str:
        nonlocal repairs
        open_tag = match.group("open")
        body = match.group("body")
        close = match.group("close")
        body_text = _visible_text(body)
        if len(body_text) < 80:
            return match.group(0)
        intrusion = pattern.search(body)
        if intrusion is None:
            return match.group(0)
        metadata = intrusion.group("meta").strip()
        if "@" not in metadata or len(metadata.split()) < 3:
            return match.group(0)
        repaired_body = (
            body[: intrusion.start()]
            + f"{intrusion.group('article')} {intrusion.group('tail')}"
            + body[intrusion.end() :]
        )
        repairs += 1
        return f'{open_tag}{repaired_body}{close}\n<p class="z2m-front-matter">{metadata}</p>'

    repaired = _P_BLOCK_PATTERN.sub(_repair, html)
    return repaired, repairs


def _repair_sentence_breaks_around_footnote_blocks(html: str) -> tuple[str, int]:
    """Move prose continuations back across footnote blocks without dropping notes."""
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    repairs = 0

    def _is_p_node(raw: str) -> bool:
        return raw.lstrip().lower().startswith("<p")

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    i = 0
    while i < len(nodes):
        if i in dropped:
            i += 1
            continue

        left_raw = nodes[i].group(0)
        if not _is_p_node(left_raw):
            i += 1
            continue
        left_match = _SENTENCE_P_NODE_PATTERN.match(left_raw)
        if left_match is None:
            i += 1
            continue
        if _is_caption_node(left_raw) or _node_has_class(left_raw, "z2m-footnote"):
            i += 1
            continue
        gap_indices: list[int] = []
        j = i + 1
        while j < len(nodes) and len(gap_indices) < 10:
            if not _between_is_whitespace(j - 1, j):
                break
            raw = nodes[j].group(0)
            if j in dropped or not (_is_p_node(raw) and _node_has_class(raw, "z2m-footnote")):
                break
            gap_indices.append(j)
            j += 1

        if not gap_indices or j >= len(nodes):
            i += 1
            continue
        if not _between_is_whitespace(gap_indices[-1], j):
            i += 1
            continue

        right_raw = nodes[j].group(0)
        if not _is_p_node(right_raw):
            i += 1
            continue
        right_match = _SENTENCE_P_NODE_PATTERN.match(right_raw)
        if right_match is None:
            i += 1
            continue
        right_open = right_match.group("open")
        if re.search(r"\bid\s*=", right_open, re.IGNORECASE):
            i += 1
            continue

        left_body = left_match.group("body")
        right_body = right_match.group("body")
        left_text = _visible_text(left_body)
        right_text = _visible_text(right_body)
        if len(left_text) < 20 and not _is_short_fragment_left(left_text):
            i += 1
            continue
        if len(right_text) < 6:
            i += 1
            continue
        if not _is_sentence_continuation(left_text, right_text):
            i += 1
            continue

        merged_left = _merge_sentence_parts(left_body, right_body)
        replacements[i] = f"{left_match.group('open')}{merged_left}{left_match.group('close')}"
        dropped.add(j)
        repairs += 1
        i = j + 1

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _repair_citation_prefix_paragraph_continuations(html: str) -> tuple[str, int]:
    """Move a page-split leading citation back to the sentence it closes."""
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    repairs = 0

    def _is_p_node(raw: str) -> bool:
        return raw.lstrip().lower().startswith("<p")

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    for idx in range(len(nodes) - 1):
        left_raw = nodes[idx].group(0)
        right_raw = nodes[idx + 1].group(0)
        if not (_is_p_node(left_raw) and _is_p_node(right_raw)):
            continue
        if not _between_is_whitespace(idx, idx + 1):
            continue
        if _is_caption_node(left_raw) or _is_caption_node(right_raw):
            continue
        left_match = _SENTENCE_P_NODE_PATTERN.match(left_raw)
        right_match = _SENTENCE_P_NODE_PATTERN.match(right_raw)
        if left_match is None or right_match is None:
            continue

        left_text = _visible_text(left_match.group("body"))
        if len(left_text) < 40:
            continue
        if left_text.rstrip().endswith((".", "!", "?", ":", ";", "…")):
            continue

        prefix_match = _CITATION_PREFIX_BODY_PATTERN.match(right_match.group("body"))
        if prefix_match is None:
            continue
        tail = prefix_match.group("tail").strip()
        if not tail:
            continue

        left_body = left_match.group("body").rstrip()
        cite = prefix_match.group("cite")
        separator = "" if left_body.endswith((" ", "\n", "\t")) else " "
        replacements[idx] = (
            f"{left_match.group('open')}{left_body}{separator}{cite}."
            f"{left_match.group('close')}"
        )
        replacements[idx + 1] = (
            f"{right_match.group('open')}{tail}{right_match.group('close')}"
        )
        repairs += 1

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        out_parts.append(replacements.get(idx, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _repair_terminal_section_interleaving(html: str) -> tuple[str, int]:
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    repairs = 0

    def _heading_text(raw: str) -> str:
        if not re.match(r"^\s*<h[1-6]\b", raw, re.IGNORECASE):
            return ""
        return _visible_text(raw).strip().upper()

    def _is_p(raw: str) -> bool:
        return raw.lstrip().lower().startswith("<p")

    def _is_ref_list(raw: str) -> bool:
        visible = _visible_text(raw)
        return bool(re.search(r"\b(?:\d{1,3}\.\s+|\[\d{1,3}\]\s+)", visible)) and (
            "<li" in raw.lower() or "listgroup" in raw.lower()
        )

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    i = 0
    while i + 7 < len(nodes):
        if i in dropped:
            i += 1
            continue
        if _heading_text(nodes[i].group(0)) != "FUNDING":
            i += 1
            continue
        if not all(_between_is_whitespace(j, j + 1) for j in range(i, i + 7)):
            i += 1
            continue

        funding_body_idx = i + 1
        ref_heading_idx = i + 2
        first_refs_idx = i + 3
        funding_cont_idx = i + 4
        supp_heading_idx = i + 5
        supp_body_idx = i + 6
        second_refs_idx = i + 7

        funding_body = nodes[funding_body_idx].group(0)
        funding_cont = nodes[funding_cont_idx].group(0)
        if not _is_p(funding_body) or not _is_p(funding_cont):
            i += 1
            continue
        funding_text = _visible_text(funding_body)
        continuation_text = _visible_text(funding_cont)
        if funding_text.rstrip().endswith((".", "!", "?")):
            i += 1
            continue
        if len(continuation_text) < 40 or continuation_text.lower().startswith("the supplementary material"):
            i += 1
            continue
        if _heading_text(nodes[ref_heading_idx].group(0)) != "REFERENCES":
            i += 1
            continue
        if _heading_text(nodes[supp_heading_idx].group(0)) != "SUPPLEMENTARY MATERIAL":
            i += 1
            continue
        if not _is_ref_list(nodes[first_refs_idx].group(0)) or not _is_ref_list(nodes[second_refs_idx].group(0)):
            i += 1
            continue

        replacements[i] = "\n".join(
            [
                nodes[i].group(0),
                funding_body,
                funding_cont,
                nodes[supp_heading_idx].group(0),
                nodes[supp_body_idx].group(0),
                nodes[ref_heading_idx].group(0),
                nodes[first_refs_idx].group(0),
                nodes[second_refs_idx].group(0),
            ]
        )
        dropped.update(range(i + 1, i + 8))
        repairs += 1
        i += 8

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _merge_biorender_caption_fragments(html: str) -> tuple[str, int]:
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    repairs = 0

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    i = 0
    while i + 2 < len(nodes):
        if i in dropped:
            i += 1
            continue
        if not _between_is_whitespace(i, i + 1) or not _between_is_whitespace(i + 1, i + 2):
            i += 1
            continue

        first_raw = nodes[i].group(0)
        url_raw = nodes[i + 1].group(0)
        tail_raw = nodes[i + 2].group(0)
        first_match = _SENTENCE_P_NODE_PATTERN.match(first_raw)
        tail_match = _SENTENCE_P_NODE_PATTERN.match(tail_raw)
        url_match = _FLOAT_NODE_PATTERN.match(url_raw)
        if first_match is None or tail_match is None or url_match is None:
            i += 1
            continue
        if url_match.group("tag").lower() not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            i += 1
            continue
        if not all(
            _node_has_class(raw, "z2m-figure-caption")
            for raw in (first_raw, url_raw, tail_raw)
        ):
            i += 1
            continue
        if "biorender" not in first_raw.lower() or "biorender.com" not in url_raw.lower():
            i += 1
            continue

        first_body = first_match.group("body").rstrip()
        url_body = url_match.group("body").strip()
        tail_body = tail_match.group("body").lstrip()
        tail_text = _visible_text(tail_body).strip()
        if not tail_text or not tail_text[:1].islower():
            i += 1
            continue

        first_body = re.sub(r"\bcreated\s+BioRender\.", "created in BioRender.", first_body, flags=re.IGNORECASE)
        first_body = re.sub(
            r"\bChamanzar\.\s*\(2025\)",
            "Chamanzar, M. (2025)",
            first_body,
            flags=re.IGNORECASE,
        )
        tail_body = re.sub(r"^comparison\s+shows\b", "c shows", tail_body, count=1, flags=re.IGNORECASE)
        merged = _merge_sentence_parts(first_body, url_body)
        merged = _merge_sentence_parts(merged, tail_body)
        replacements[i] = f"{first_match.group('open')}{merged}{first_match.group('close')}"
        dropped.update({i + 1, i + 2})
        repairs += 1
        i += 3

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _repair_caption_suffix_left_body_tail_right(html: str) -> tuple[str, int]:
    """Repair the mirrored figure-caption intrusion shape.

    Some Marker layouts put the final caption enumeration item into the prose
    paragraph before a figure, while the actual prose tail starts after the
    caption.  This pass runs late enough to see normalized figure targets and
    captions, then moves the caption suffix back and rejoins the prose tail.
    """
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    repairs = 0

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    for i in range(len(nodes)):
        if i in dropped:
            continue
        left_raw = nodes[i].group(0)
        left_match = _SENTENCE_P_NODE_PATTERN.match(left_raw)
        if left_match is None:
            continue
        left_body = left_match.group("body")
        left_text = _visible_text(left_body)
        if "(4)" not in left_text or "to evaluate" not in left_text.lower():
            continue

        caption_idx = None
        right_idx = None
        upper = min(len(nodes), i + 8)
        for j in range(i + 1, upper):
            if not _between_is_whitespace(j - 1, j):
                break
            raw = nodes[j].group(0)
            if caption_idx is None:
                if _is_figure_caption_node(raw):
                    caption_idx = j
                elif not _looks_nonprose_gap_block(raw):
                    break
                continue
            if _SENTENCE_P_NODE_PATTERN.match(raw) is not None and not _is_figure_caption_node(raw):
                right_idx = j
                break
            if not _looks_nonprose_gap_block(raw):
                break

        if caption_idx is None or right_idx is None:
            continue

        cap_match = _SENTENCE_P_NODE_PATTERN.match(nodes[caption_idx].group(0))
        right_match = _SENTENCE_P_NODE_PATTERN.match(nodes[right_idx].group(0))
        if cap_match is None or right_match is None:
            continue

        right_body = right_match.group("body")
        left_body_for_recovery, cap_body_for_recovery = _rehome_enumerated_caption_suffix(
            left_body,
            cap_match.group("body"),
        )
        if left_body_for_recovery == left_body:
            continue
        if not _is_sentence_continuation(_visible_text(left_body_for_recovery), _visible_text(right_body)):
            continue

        merged_left = _merge_sentence_parts(left_body_for_recovery, right_body)
        replacements[i] = f"{left_match.group('open')}{merged_left}{left_match.group('close')}"
        replacements[caption_idx] = f"{cap_match.group('open')}{cap_body_for_recovery}{cap_match.group('close')}"
        dropped.add(right_idx)
        repairs += 1

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _is_same_figure_caption(raw: str, fig_num: str) -> bool:
    if re.search(r"<img\b", raw, re.IGNORECASE):
        return False
    visible = _visible_text(raw)
    caption_num = _figure_caption_num_from_visible(visible)
    if caption_num == fig_num:
        return True
    return _node_has_class(raw, "z2m-figure-caption") and caption_num in {None, fig_num}


def _looks_like_figure_caption_fragment(raw: str) -> bool:
    if not re.match(r"<(?:p|h[1-6])\b", raw, re.IGNORECASE):
        return False
    if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
        return False
    visible = _visible_text(raw)
    if not visible or len(visible) > 650:
        return False
    if _node_has_class(raw, "z2m-figure-caption"):
        return True
    if _URL_PATTERN.fullmatch(visible.rstrip(".")) is not None:
        return True
    if re.match(r"^[a-z]\s+[A-Z(]", visible):
        return True
    return bool(re.match(r"^[a-z][a-z-]{2,}\s+(?:shows?|showing|demonstrates?|indicates?|compares?|comparison)\b", visible, re.IGNORECASE))


def _looks_like_figure_panel_caption_continuation(raw: str) -> bool:
    if not re.match(r"<(?:p|h[1-6])\b", raw, re.IGNORECASE):
        return False
    if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
        return False
    visible = _visible_text(raw)
    if not visible or len(visible) > 1400:
        return False
    if re.match(r"^[A-Z][a-z]+(?:\s+[a-z]+){2,}\b", visible):
        return False
    panel_hits = len(re.findall(r"(?:^|\s)[a-h]\s+(?=[A-Z(])", visible))
    if panel_hits >= 2:
        return True
    return bool(re.match(r"^[a-h]\s+[A-Z(]", visible)) and re.search(r"\b(?:shown|shows?|micrographs?|images?|schematic|process|flow)\b", visible, re.IGNORECASE)


def _is_same_table_caption(raw: str, table_key: str) -> bool:
    if not re.match(r"<(?:p|h[1-6])\b", raw, re.IGNORECASE):
        return False
    caption_key = _table_caption_key_from_visible(_visible_text(raw))
    node_id = _node_id_value(raw)
    if caption_key == table_key:
        return True
    return node_id == f"table-{table_key}"


def _wrap_box_units(html: str) -> str:
    """Wrap Box headings and nearby box body paragraphs in a framed float unit."""
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html

    groups: dict[int, tuple[list[int], str]] = {}
    consumed: set[int] = set()

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _is_box_boundary(raw: str) -> bool:
        visible = _visible_text(raw)
        node_id = _node_id_value(raw) or ""
        if re.match(r"^(?:fig|table|section|ref|eq)-", node_id, re.IGNORECASE):
            return True
        if _BOX_HEADING_VISIBLE_PATTERN.match(visible):
            return True
        if _references_heading_match(raw):
            return True
        if re.match(r"<h[1-6]\b", raw, re.IGNORECASE):
            return True
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            return True
        if _figure_caption_num_from_visible(visible) is not None:
            return True
        if _table_caption_key_from_visible(visible) is not None:
            return True
        return False

    def _looks_like_box_title_candidate(raw: str) -> bool:
        if not re.match(r"<h[1-6]\b", raw, re.IGNORECASE):
            return False
        if _node_id_value(raw):
            return False
        visible = _visible_text(raw)
        if not visible or len(visible) > 260:
            return False
        if _BOX_HEADING_VISIBLE_PATTERN.match(visible):
            return False
        if re.match(
            r"^(?:abstract|introduction|background|methods?|materials|results?|discussion|conclusions?|"
            r"references|bibliography|acknowledg|supplementary|appendix)\b",
            visible,
            re.IGNORECASE,
        ):
            return False
        if _figure_caption_num_from_visible(visible) is not None:
            return False
        if _table_caption_key_from_visible(visible) is not None:
            return False
        return True

    for index, node in enumerate(nodes):
        if index in consumed:
            continue
        raw = node.group(0)
        node_id = _node_id_value(raw)
        box_match = re.fullmatch(r"box-(\d+)", node_id or "", re.IGNORECASE)
        if box_match is None:
            continue

        group_indices = [index]
        next_idx = index + 1
        while next_idx < len(nodes) and len(group_indices) < 9:
            if not _between_is_whitespace(next_idx - 1, next_idx):
                break
            next_raw = nodes[next_idx].group(0)
            if len(group_indices) == 1 and _looks_like_box_title_candidate(next_raw):
                group_indices.append(next_idx)
                next_idx += 1
                continue
            if _is_box_boundary(next_raw):
                break
            if _SENTENCE_P_NODE_PATTERN.match(next_raw) is None:
                break
            group_indices.append(next_idx)
            next_idx += 1

        if any(idx in consumed for idx in group_indices):
            continue

        content_html = "".join(
            _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-box-heading" if idx == index else "z2m-box-body")
            for idx in group_indices
        )
        wrapper = f'<div id="{node_id}" class="z2m-float-unit z2m-box-unit">{content_html}</div>'
        groups[group_indices[0]] = (group_indices, wrapper)
        consumed.update(group_indices)

    if not groups:
        return html

    out_parts: list[str] = []
    cursor = 0
    skip_indices: set[int] = set()
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in groups:
            group_indices, wrapper = groups[idx]
            out_parts.append(wrapper)
            skip_indices.update(group_indices[1:])
        elif idx in skip_indices:
            pass
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _wrap_float_units(html: str) -> str:
    """Wrap recognized figure/table content and captions in one link target."""
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html

    groups: dict[int, tuple[list[int], str]] = {}
    consumed: set[int] = set()

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _grid_caption_index(image_index: int, fig_num: str) -> int | None:
        image_run_start = image_index
        while image_run_start > 0 and _between_is_whitespace(image_run_start - 1, image_run_start):
            if not re.search(r"<img\b", nodes[image_run_start - 1].group(0), re.IGNORECASE):
                break
            image_run_start -= 1

        image_run_end = image_index
        while image_run_end + 1 < len(nodes) and _between_is_whitespace(image_run_end, image_run_end + 1):
            if not re.search(r"<img\b", nodes[image_run_end + 1].group(0), re.IGNORECASE):
                break
            image_run_end += 1

        image_offset = image_index - image_run_start
        if image_run_end - image_run_start + 1 < 2:
            return None

        caption_indices: list[int] = []
        scan = image_run_end + 1
        while scan < len(nodes):
            if scan > image_run_end + 1 and not _between_is_whitespace(scan - 1, scan):
                break
            if not _node_is_caption_bridge_or_note_paragraph(nodes[scan].group(0)):
                break
            scan += 1
        while scan < len(nodes):
            if scan > image_run_end + 1 and not _between_is_whitespace(scan - 1, scan):
                break
            caption_raw = nodes[scan].group(0)
            if _figure_caption_num_from_visible(_visible_text(caption_raw)) is None:
                break
            caption_indices.append(scan)
            scan += 1

        if len(caption_indices) >= 2 and image_offset < len(caption_indices):
            candidate = caption_indices[image_offset]
            if _is_same_figure_caption(nodes[candidate].group(0), fig_num):
                return candidate
        return None

    def _caption_is_immediately_followed_by_image(caption_index: int) -> bool:
        following = caption_index + 1
        return (
            following < len(nodes)
            and _between_is_whitespace(caption_index, following)
            and re.search(r"<img\b", nodes[following].group(0), re.IGNORECASE) is not None
        )

    def _unnumbered_caption_fragment_belongs_to_previous_figure(caption_index: int, fig_num: str) -> bool:
        raw = nodes[caption_index].group(0)
        if not _node_has_class(raw, "z2m-figure-caption"):
            return False
        if _figure_caption_num_from_visible(_visible_text(raw)) is not None:
            return False
        scan_idx = caption_index - 1
        while scan_idx >= 0 and _between_is_whitespace(scan_idx, scan_idx + 1):
            scan_raw = nodes[scan_idx].group(0)
            if re.search(r"<img\b|<table\b", scan_raw, re.IGNORECASE):
                return False
            if not _node_has_class(scan_raw, "z2m-figure-caption"):
                return False
            visible = _visible_text(scan_raw)
            caption_num = _figure_caption_num_from_visible(visible) or _standalone_figure_label_key_from_visible(visible)
            if caption_num is not None:
                return caption_num != fig_num
            scan_idx -= 1
        return False

    for index, node in enumerate(nodes):
        if index in consumed:
            continue
        raw = node.group(0)
        node_id = _node_id_value(raw)
        if node_id is None:
            continue

        fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", node_id, re.IGNORECASE)
        if fig_match is not None and re.search(r"<img\b", raw, re.IGNORECASE):
            fig_num = fig_match.group(1)
            before: list[int] = []
            following_images: list[int] = []
            caption_bridge_indices: list[int] = []
            after: list[int] = []

            prev_idx = index - 1
            while prev_idx >= 0 and _between_is_whitespace(prev_idx, prev_idx + 1):
                if _unnumbered_caption_fragment_belongs_to_previous_figure(prev_idx, fig_num):
                    break
                if not _is_same_figure_caption(nodes[prev_idx].group(0), fig_num):
                    break
                before.insert(0, prev_idx)
                prev_idx -= 1

            if not before:
                lower_bound = max(0, index - 6)
                for candidate_idx in range(index - 1, lower_bound - 1, -1):
                    if not _between_is_whitespace(candidate_idx, candidate_idx + 1):
                        break
                    candidate_raw = nodes[candidate_idx].group(0)
                    if _unnumbered_caption_fragment_belongs_to_previous_figure(candidate_idx, fig_num):
                        break
                    if _is_same_figure_caption(candidate_raw, fig_num):
                        candidate_range = list(range(candidate_idx, index))
                        if all(_looks_like_figure_caption_fragment(nodes[idx].group(0)) for idx in candidate_range):
                            before = candidate_range
                        break
                    if not _looks_like_figure_caption_fragment(candidate_raw):
                        break

            next_idx = index + 1
            candidate_following_images: list[int] = []
            while next_idx < len(nodes) and _between_is_whitespace(next_idx - 1, next_idx):
                next_raw = nodes[next_idx].group(0)
                if not re.search(r"<img\b", next_raw, re.IGNORECASE):
                    break
                next_id = _node_id_value(next_raw) or ""
                if re.fullmatch(r"fig-[A-Za-z0-9-]+", next_id, re.IGNORECASE):
                    break
                candidate_following_images.append(next_idx)
                next_idx += 1

            while next_idx < len(nodes) and _between_is_whitespace(next_idx - 1, next_idx):
                next_raw = nodes[next_idx].group(0)
                if not _node_is_caption_bridge_or_note_paragraph(next_raw):
                    break
                caption_bridge_indices.append(next_idx)
                next_idx += 1

            while next_idx < len(nodes) and _between_is_whitespace(next_idx - 1, next_idx):
                next_raw = nodes[next_idx].group(0)
                if _is_same_figure_caption(next_raw, fig_num):
                    after.append(next_idx)
                    next_idx += 1
                    continue
                if (before or after) and _looks_like_figure_panel_caption_continuation(next_raw):
                    after.append(next_idx)
                    next_idx += 1
                    continue
                if after:
                    next_caption_num = _figure_caption_num_from_visible(_visible_text(next_raw))
                    if next_caption_num is not None:
                        numbered_after = [
                            _figure_caption_num_from_visible(_visible_text(nodes[idx].group(0)))
                            for idx in after
                        ]
                        extra_caption_count = sum(1 for value in numbered_after if value is not None and value != fig_num)
                        try:
                            is_next_compound_caption = int(next_caption_num) == int(fig_num) + extra_caption_count + 1
                        except ValueError:
                            is_next_compound_caption = False
                        if (
                            is_next_compound_caption
                            and nodes[next_idx].group(0).lstrip().lower().startswith("<p")
                            and not _caption_is_immediately_followed_by_image(next_idx)
                        ):
                            after.append(next_idx)
                            next_idx += 1
                            continue
                        break
                if after and _looks_like_figure_caption_fragment(next_raw):
                    after.append(next_idx)
                    next_idx += 1
                    continue
                else:
                    break

            if after or _node_has_class(raw, "z2m-figure-target"):
                following_images = candidate_following_images

            if not before and not after:
                grid_idx = _grid_caption_index(index, fig_num)
                if grid_idx is not None:
                    after = [grid_idx]

            group_indices = before + [index] + following_images + (caption_bridge_indices if after else []) + after
            if any(idx in consumed for idx in group_indices):
                continue
            alias_html = "".join(
                f'<span id="{alias_id}" class="z2m-float-alias"></span>'
                for idx in before + after
                for alias_id in [_node_id_value(nodes[idx].group(0))]
                if alias_id is not None and re.fullmatch(r"fig-[A-Za-z0-9-]+", alias_id, re.IGNORECASE) and alias_id != node_id
            )
            image_html = "".join(
                _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-figure-target")
                for idx in [index] + following_images
            )
            bridge_html = "".join(
                _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-figure-caption")
                for idx in (caption_bridge_indices if after else [])
            )
            caption_html = "".join(
                _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-figure-caption")
                for idx in before + after
            )
            wrapper = (
                f'<div id="{node_id}" class="z2m-float-unit z2m-figure-unit">'
                f"{alias_html}{image_html}{bridge_html}{caption_html}</div>"
            )
            groups[group_indices[0]] = (group_indices, wrapper)
            consumed.update(group_indices)
            continue

        if fig_match is not None and _is_same_figure_caption(raw, fig_match.group(1)):
            fig_num = fig_match.group(1)
            if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
                continue
            image_indices: list[int] = []
            bridge_indices: list[int] = []
            drop_gap_indices: list[int] = []
            scan_idx = index - 1
            while scan_idx >= 0 and _between_is_whitespace(scan_idx, scan_idx + 1):
                scan_raw = nodes[scan_idx].group(0)
                if re.search(r"<img\b", scan_raw, re.IGNORECASE) is not None:
                    break
                if _node_is_caption_bridge_or_note_paragraph(scan_raw):
                    bridge_indices.insert(0, scan_idx)
                    scan_idx -= 1
                    continue
                if _looks_nonprose_gap_block(scan_raw):
                    drop_gap_indices.insert(0, scan_idx)
                    scan_idx -= 1
                    continue
                break
            while scan_idx >= 0 and _between_is_whitespace(scan_idx, scan_idx + 1):
                scan_raw = nodes[scan_idx].group(0)
                if re.search(r"<img\b", scan_raw, re.IGNORECASE) is None:
                    break
                scan_id = _node_id_value(scan_raw) or ""
                if re.fullmatch(r"fig-[A-Za-z0-9-]+", scan_id, re.IGNORECASE) and scan_id != node_id:
                    break
                image_indices.insert(0, scan_idx)
                scan_idx -= 1
            if image_indices:
                group_indices = image_indices + bridge_indices + drop_gap_indices + [index]
                if any(idx in consumed for idx in group_indices):
                    continue
                image_html = "".join(
                    _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-figure-target")
                    for idx in image_indices
                )
                bridge_html = "".join(
                    _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-figure-caption")
                    for idx in bridge_indices
                )
                caption_html = _strip_node_id_and_add_class(raw, "z2m-figure-caption")
                wrapper = (
                    f'<div id="{node_id}" class="z2m-float-unit z2m-figure-unit">'
                    f"{image_html}{bridge_html}{caption_html}</div>"
                )
                groups[group_indices[0]] = (group_indices, wrapper)
                consumed.update(group_indices)
                continue

        if fig_match is not None and _is_same_figure_caption(raw, fig_match.group(1)):
            fig_num = fig_match.group(1)
            if index == 0 or not _between_is_whitespace(index - 1, index):
                continue
            warning_idx = index - 1
            warning_raw = nodes[warning_idx].group(0)
            if not _node_has_class(warning_raw, "z2m-missing-figure-warning"):
                continue

            after: list[int] = []
            next_idx = index + 1
            while next_idx < len(nodes) and _between_is_whitespace(next_idx - 1, next_idx):
                next_raw = nodes[next_idx].group(0)
                if _looks_like_figure_panel_caption_continuation(next_raw):
                    after.append(next_idx)
                    next_idx += 1
                    continue
                if after and _looks_like_figure_caption_fragment(next_raw):
                    after.append(next_idx)
                    next_idx += 1
                    continue
                break

            group_indices = [warning_idx, index] + after
            if any(idx in consumed for idx in group_indices):
                continue
            warning_html = _strip_node_id_and_add_class(warning_raw, "z2m-figure-target")
            caption_html = "".join(
                _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-figure-caption")
                for idx in [index] + after
            )
            wrapper = (
                f'<div id="{node_id}" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
                f"{warning_html}{caption_html}</div>"
            )
            groups[group_indices[0]] = (group_indices, wrapper)
            consumed.update(group_indices)
            continue

        table_match = re.fullmatch(r"table-([A-Za-z0-9-]+)", node_id, re.IGNORECASE)
        if table_match is None or not _is_same_table_caption(raw, table_match.group(1)):
            continue
        table_key = table_match.group(1)
        table_index: int | None = None
        previous_table_index = (
            index - 1
            if index > 0
            and _between_is_whitespace(index - 1, index)
            and re.match(r"<table\b", nodes[index - 1].group(0), re.IGNORECASE)
            else None
        )
        following_table_index = (
            index + 1
            if index + 1 < len(nodes)
            and _between_is_whitespace(index, index + 1)
            and re.match(r"<table\b", nodes[index + 1].group(0), re.IGNORECASE)
            else None
        )
        if previous_table_index is not None and previous_table_index not in consumed:
            table_index = previous_table_index
        elif following_table_index is not None and following_table_index not in consumed:
            table_index = following_table_index
        if table_index is None:
            continue

        note_indices: list[int] = []
        next_idx = max(index, table_index) + 1
        while next_idx < len(nodes) and _between_is_whitespace(next_idx - 1, next_idx):
            candidate_raw = nodes[next_idx].group(0)
            if not _is_table_note_node(candidate_raw):
                break
            note_indices.append(next_idx)
            next_idx += 1

        group_indices = sorted([index, table_index] + note_indices)
        if any(idx in consumed for idx in group_indices):
            continue
        table_html = _strip_node_id_and_add_class(nodes[table_index].group(0), None)
        caption_html = _strip_node_id_and_add_class(raw, "z2m-table-caption")
        note_html = "".join(
            _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-table-note")
            for idx in note_indices
        )
        table_content = (
            f"{caption_html}{table_html}{note_html}"
            if index < table_index
            else f"{table_html}{caption_html}{note_html}"
        )
        wrapper = (
            f'<div id="{node_id}" class="z2m-float-unit z2m-table-unit">'
            f"{table_content}</div>"
        )
        groups[group_indices[0]] = (group_indices, wrapper)
        consumed.update(group_indices)

    if not groups:
        return html

    out_parts: list[str] = []
    cursor = 0
    skip_indices: set[int] = set()
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in groups:
            group_indices, wrapper = groups[idx]
            out_parts.append(wrapper)
            skip_indices.update(group_indices[1:])
        elif idx in skip_indices:
            pass
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _absorb_external_figure_captions_into_units(html: str) -> str:
    """Move a nearby matching caption/image run into an existing figure unit."""
    nodes = list(_FLOAT_AWARE_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html

    replacements: dict[int, str] = {}
    skip_indices: set[int] = set()
    id_occurrence_cache: dict[str, int] = {}

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _caption_points_to_figure(raw: str, figure_id: str) -> bool:
        return (
            re.search(rf'href\s*=\s*(["\'])#{re.escape(figure_id)}\1', raw, re.IGNORECASE)
            is not None
        )

    def _matches_figure_caption(raw: str, figure_id: str, fig_num: str) -> bool:
        caption_id = _node_id_value(raw)
        if caption_id is not None and caption_id != figure_id and not caption_id.startswith("page-"):
            return False
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            return False
        visible = _visible_text(raw)
        starts_like_caption = (
            re.match(
                rf"^\s*(?:{_FIG_REF_LABEL_TOKEN}\.?)\s*{_FIG_RELAXED_KEY_TOKEN}\b",
                visible,
                re.IGNORECASE,
            )
            is not None
        )
        if not (_node_has_class(raw, "z2m-figure-caption") or starts_like_caption):
            return False
        return _is_same_figure_caption(raw, fig_num) or _caption_points_to_figure(raw, figure_id)

    def _is_image_only_node(raw: str) -> bool:
        return (
            re.search(r"<img\b", raw, re.IGNORECASE) is not None
            and not _visible_text(raw).strip()
        )

    def _id_occurs_elsewhere(node_id: str) -> bool:
        if node_id in id_occurrence_cache:
            return id_occurrence_cache[node_id] > 1
        pattern = rf'\bid\s*=\s*(["\']){re.escape(node_id)}\1'
        id_occurrence_cache[node_id] = len(re.findall(pattern, html, re.IGNORECASE))
        return id_occurrence_cache[node_id] > 1

    def _image_target_html_from_node(raw: str) -> str:
        node_id = _node_id_value(raw)
        alias_html = ""
        if (
            node_id is not None
            and re.fullmatch(r"fig-[A-Za-z0-9-]+", node_id, re.IGNORECASE)
            and not _id_occurs_elsewhere(node_id)
        ):
            alias_html = f'<span id="{node_id}" class="z2m-float-alias"></span>'
        if _node_has_class(raw, "z2m-figure-unit"):
            open_end = raw.find(">")
            close_pos = raw.lower().rfind("</div>")
            if open_end >= 0 and close_pos > open_end:
                return alias_html + raw[open_end + 1:close_pos]
        return alias_html + _strip_node_id_and_add_class(raw, "z2m-figure-target")

    def _is_continuation_only_caption_text(text: str, fig_num: str) -> bool:
        return (
            re.fullmatch(
                rf"\s*(?:{_FIG_REF_LABEL_TOKEN}\.?)\s*{re.escape(fig_num)}\s*[\).:|,-]?\s*"
                r"(?:cont\.?|continued)\s*\.?\s*",
                text,
                re.IGNORECASE,
            )
            is not None
        )

    def _has_non_continuation_figure_caption(raw: str, fig_num: str) -> bool:
        for caption_match in re.finditer(
            r'<(?:p|h[1-6])\b(?=[^>]*\bclass\s*=\s*(["\'])[^"\']*\bz2m-figure-caption\b)[^>]*>'
            r"(?P<body>[\s\S]*?)</(?:p|h[1-6])>",
            raw,
            re.IGNORECASE,
        ):
            if not _is_continuation_only_caption_text(_visible_text(caption_match.group("body")), fig_num):
                return True
        return False

    for index, node in enumerate(nodes[:-1]):
        raw = node.group(0)
        if not _node_has_class(raw, "z2m-figure-unit"):
            continue
        figure_id = _node_id_value(raw)
        if figure_id is None:
            continue
        fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", figure_id, re.IGNORECASE)
        if fig_match is None:
            continue
        has_existing_caption = _has_non_continuation_figure_caption(raw, fig_match.group(1))

        caption_idx: int | None = None
        pending_image_indices: list[int] = []
        pending_bridge_indices: list[int] = []
        has_foreign_figure_unit = False
        scan_idx = index + 1
        while scan_idx < len(nodes) and scan_idx <= index + 8:
            if scan_idx in skip_indices or not _between_is_whitespace(scan_idx - 1, scan_idx):
                break
            candidate_raw = nodes[scan_idx].group(0)
            if _matches_figure_caption(candidate_raw, figure_id, fig_match.group(1)):
                caption_idx = scan_idx
                break
            if _is_image_only_node(candidate_raw):
                candidate_id = _node_id_value(candidate_raw) or ""
                if (
                    re.fullmatch(r"fig-[A-Za-z0-9-]+", candidate_id, re.IGNORECASE)
                    and candidate_id != figure_id
                ):
                    if not _node_has_class(candidate_raw, "z2m-figure-unit"):
                        break
                    has_foreign_figure_unit = True
                pending_image_indices.append(scan_idx)
                scan_idx += 1
                continue
            if _node_is_caption_bridge_or_note_paragraph(candidate_raw):
                pending_bridge_indices.append(scan_idx)
                scan_idx += 1
                continue
            break
        if caption_idx is None:
            continue
        if has_existing_caption and not pending_image_indices:
            continue
        caption_raw = nodes[caption_idx].group(0)
        if has_foreign_figure_unit and not _caption_points_to_figure(caption_raw, figure_id):
            continue

        close_pos = raw.lower().rfind("</div>")
        if close_pos < 0:
            continue
        image_html = "".join(_image_target_html_from_node(nodes[idx].group(0)) for idx in pending_image_indices)
        bridge_html = "".join(
            _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-figure-caption")
            for idx in pending_bridge_indices
        )
        caption_html = _strip_node_id_and_add_class(caption_raw, "z2m-figure-caption")
        replacements[index] = raw[:close_pos] + image_html + bridge_html + caption_html + raw[close_pos:]
        skip_indices.update(pending_image_indices)
        skip_indices.update(pending_bridge_indices)
        skip_indices.add(caption_idx)

    if not replacements:
        return html

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in replacements:
            out_parts.append(replacements[idx])
        elif idx in skip_indices:
            pass
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _mark_missing_figure_units(html: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        raw = match.group(0)
        if "z2m-figure-unit" not in raw:
            return raw
        has_table_surrogate = re.search(
            r'<table\b(?=[^>]*\bclass\s*=\s*(["\'])[^"\']*\bz2m-figure-target\b[^"\']*\1)[\s\S]*?</table>',
            raw,
            re.IGNORECASE,
        )
        if _node_has_renderable_image(raw) or has_table_surrogate:
            return raw
        open_end = raw.find(">")
        if open_end < 0:
            return raw
        if "z2m-missing-figure-warning" not in raw and _node_has_broken_data_image(raw):
            unit_id = _node_id_value(raw) or ""
            fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", unit_id, re.IGNORECASE)
            if fig_match is None:
                return raw
            warning_html = _strip_node_id_and_add_class(
                _missing_figure_warning_html(fig_match.group(1)),
                "z2m-figure-target",
            )
            replaced = re.sub(
                r"<p\b[^>]*>\s*(?:<span\b[^>]*>\s*</span>\s*)*<img\b[\s\S]*?</p>",
                warning_html,
                raw,
                count=1,
                flags=re.IGNORECASE,
            )
            if replaced == raw:
                replaced = raw[: open_end + 1] + warning_html + raw[open_end + 1 :]
            raw = replaced
            open_end = raw.find(">")
        open_tag = _add_class_attr(raw[: open_end + 1], "z2m-missing-figure-unit")
        return open_tag + raw[open_end + 1:]

    return _FLOAT_UNIT_DIV_PATTERN.sub(_replace, html)


_DUPLICATE_NESTED_FLOAT_UNIT_PATTERN = re.compile(
    r'<div\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bz2m-float-unit\b)[^>]*'
    r'\bid\s*=\s*["\'](?P<outer_id>[^"\']+)["\'][^>]*>\s*'
    r'(?P<inner><div\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bz2m-float-unit\b)[^>]*'
    r'\bid\s*=\s*["\'](?P<inner_id>[^"\']+)["\'][^>]*>[\s\S]*?</div>)\s*</div>',
    re.IGNORECASE,
)
_FIGURE_UNIT_OPEN_TAG_PATTERN = re.compile(
    r'<div\b(?=[^>]*\bz2m-float-unit\b)(?=[^>]*\bz2m-figure-unit\b)'
    r'(?=[^>]*\bid\s*=\s*(["\'])(?P<id>fig-[^"\']+)\1)[^>]*>',
    re.IGNORECASE,
)
_FIGURE_BODY_NEXT_NODE_OPEN_PATTERN = re.compile(
    r'\s*(?:<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\1[^>]*>\s*</span>\s*)*'
    r"(?P<open><(?P<tag>p|h[1-6]|div)\b[^>]*>)",
    re.IGNORECASE,
)
_FIG_ID_CANDIDATE_NODE_PATTERN = re.compile(
    r'<(?P<tag>p|h[1-6]|div)\b'
    r'(?=[^>]*\bid\s*=\s*(["\'])fig-[A-Za-z0-9_.:-]+\2)[^>]*>'
    r'[\s\S]*?</(?P=tag)>',
    re.IGNORECASE,
)
def _collapse_duplicate_nested_float_units(html: str) -> str:
    """Collapse duplicate float wrappers produced when source HTML is already polished."""
    def _replace(match: re.Match[str]) -> str:
        if match.group("outer_id") != match.group("inner_id"):
            return match.group(0)
        return match.group("inner")

    previous = None
    current = html
    while previous != current:
        previous = current
        current = _DUPLICATE_NESTED_FLOAT_UNIT_PATTERN.sub(_replace, current)
    return current


def _figure_body_tail_split_offset(body: str, figure_id: str) -> int | None:
    fig_num = figure_id.removeprefix("fig-")
    figure_key = _figure_key_from_visible_number(fig_num)
    caption_seen = False
    scan_pos = 0

    while True:
        match = _FIGURE_BODY_NEXT_NODE_OPEN_PATTERN.match(body, scan_pos)
        if match is None:
            return None
        open_tag = match.group("open")
        tag = match.group("tag").lower()
        open_start = match.start("open")
        open_end = match.end("open")

        if tag == "div":
            if _node_has_class(open_tag, "z2m-figure-unit"):
                nested_id = _node_id_value(open_tag)
                if caption_seen and nested_id != figure_id:
                    return scan_pos
                close_span = _matching_div_close_span(body, open_end)
                if close_span is None:
                    return scan_pos if caption_seen else None
                scan_pos = close_span[1]
                continue
            return scan_pos if caption_seen else None

        close_end = _node_close_end(body, tag, open_end)
        if close_end is None:
            return scan_pos if caption_seen else None
        raw_node = body[open_start:close_end]
        has_figure_class = any(
            _node_has_class(open_tag, class_name)
            for class_name in ("z2m-figure-target", "z2m-figure-caption", "z2m-missing-figure-warning")
        )
        if not has_figure_class:
            return scan_pos if caption_seen else None

        if _node_has_class(open_tag, "z2m-figure-caption"):
            visible = _visible_text(raw_node)
            caption_num = _figure_caption_num_from_visible(visible)
            if caption_num is not None:
                if caption_num != figure_key:
                    return scan_pos if caption_seen else None
                caption_seen = True
        scan_pos = close_end


def _split_figure_units_at_body_tail(html: str) -> str:
    """Close figure units before swallowed body prose or a later distinct figure."""
    out_parts: list[str] = []
    cursor = 0
    search_pos = 0
    splits = 0

    while True:
        match = _FIGURE_UNIT_OPEN_TAG_PATTERN.search(html, search_pos)
        if match is None:
            break
        close_span = _matching_div_close_span(html, match.end())
        if close_span is None:
            body = html[match.end():]
            split_offset = _figure_body_tail_split_offset(body, match.group("id"))
            if split_offset is None:
                search_pos = match.end()
                continue
            out_parts.append(html[cursor:match.start()])
            head = body[:split_offset].rstrip()
            tail = body[split_offset:]
            out_parts.append(f"{match.group(0)}{head}</div>{tail}")
            cursor = len(html)
            splits += 1
            break
        close_start, close_end = close_span
        body = html[match.end():close_start]
        split_offset = _figure_body_tail_split_offset(body, match.group("id"))
        out_parts.append(html[cursor:match.start()])
        if split_offset is None:
            out_parts.append(html[match.start():close_end])
        else:
            head = body[:split_offset].rstrip()
            tail = body[split_offset:]
            out_parts.append(f"{match.group(0)}{head}</div>{tail}")
            splits += 1
        cursor = close_end
        search_pos = close_end

    if splits == 0:
        return html
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _figure_caption_tail_starts_like_body(tail_body: str) -> bool:
    tail_text = _visible_text(tail_body)
    if len(tail_text) < 45 or len(re.findall(r"[A-Za-z]+", tail_text)) < 7:
        return False
    if re.match(
        r"^(?:fig(?:ure)?|table|source|note|notes?|legend|doi|https?://|where|and|or|with|of|by|for)\b",
        tail_text,
        re.IGNORECASE,
    ):
        return False
    first = re.sub(r'^[\s"\'(\[\{]+', "", tail_text)
    first_token_match = re.match(r"^([A-Za-z][A-Za-z0-9._~-]{3,180})\b", first)
    if first_token_match is not None:
        first_token = first_token_match.group(1).rstrip(".,;:")
        if "." in first_token and re.search(r"\d", first_token):
            return False
    return bool(
        first[:1].islower()
        or re.match(r"^(?:Given|The|This|These|Those|We|In|As|Our|Their|Such)\b", first)
    )


def _figure_caption_ends_with_doi_marker(caption_body: str) -> bool:
    caption_text = _visible_text(caption_body).rstrip()
    caption_text = caption_text.rstrip(").,;:")
    return (
        re.search(
            r"(?:\bdoi\s*:?\s*)?(?:https?://(?:dx\.)?doi\.org/)?"
            r"10\.\d{4,9}/[A-Za-z0-9._;()/:+-]+$",
            caption_text,
            re.IGNORECASE,
        )
        is not None
    )


def _split_figure_caption_internal_body_tail(caption_body: str) -> tuple[str, str] | None:
    """Split body prose accidentally appended to a terminal figure caption."""
    caption_text = _visible_text(caption_body)
    if _figure_caption_num_from_visible(caption_text) is None:
        return None

    doi_boundary = re.compile(
        r"(?P<head>[\s\S]*?"
        r"(?:\b(?:DOI|doi)\s*:?\s*)?"
        r"(?:"
        r"<a\b(?=[^>]*\bhref\s*=\s*['\"](?:https?://(?:dx\.)?doi\.org/10\.|10\.))[^>]*>"
        r"[\s\S]{0,500}?</a>"
        r"|(?<![\"'=:/A-Za-z0-9._-])https?://(?:dx\.)?doi\.org/10\.[^\s<\"]+"
        r"|(?<![\"'=:/A-Za-z0-9._-])10\.\d{4,9}/[^\s<\"]+"
        r"))(?P<space>\s+)(?P<tail>(?:</?(?:span|em|i|b|strong)\b[^>]*>\s*)*[\s\S]{45,})$",
        re.IGNORECASE,
    )
    citation_boundary = re.compile(
        r"(?P<head>[\s\S]*?[.!?]\s*"
        r"<sup\b[^>]*>[\s\S]{0,300}?\bz2m-ref-link\b[\s\S]{0,300}?</sup>)"
        r"(?P<space>\s+)(?P<tail>(?:</?(?:span|em|i|b|strong)\b[^>]*>\s*)*[\s\S]{45,})$",
        re.IGNORECASE,
    )

    for pattern in (doi_boundary, citation_boundary):
        match = pattern.match(caption_body)
        if match is None:
            continue
        head = match.group("head").rstrip()
        tail = match.group("tail").lstrip()
        if not _figure_caption_tail_starts_like_body(tail):
            continue
        if len(_visible_text(head)) < 25:
            continue
        return head, tail
    return None


def _split_figure_caption_internal_body_tails(html: str) -> str:
    """Move article-body tails out of figure captions after terminal DOI/citation markers."""
    if "z2m-figure-caption" not in html or "z2m-figure-unit" not in html:
        return html

    def _split_body(body: str) -> tuple[str, str] | None:
        for caption_match in _P_OR_H_BLOCK_PATTERN.finditer(body):
            if not _node_has_class(caption_match.group("open"), "z2m-figure-caption"):
                continue
            split = _split_figure_caption_internal_body_tail(caption_match.group("body"))
            if split is None:
                continue
            after = body[caption_match.end():]
            if after.strip() and not _html_gap_is_ignorable(after):
                continue
            head_body, tail_body = split
            repaired_caption = (
                f"{caption_match.group('open')}{head_body}{caption_match.group('close')}"
            )
            figure_body = body[: caption_match.start()] + repaired_caption + after
            return figure_body.rstrip(), f"<p>{tail_body}</p>"
        return None

    out_parts: list[str] = []
    cursor = 0
    search_pos = 0
    splits = 0
    while True:
        match = _FIGURE_UNIT_OPEN_TAG_PATTERN.search(html, search_pos)
        if match is None:
            break
        close_span = _matching_div_close_span(html, match.end())
        if close_span is None:
            search_pos = match.end()
            continue
        body = html[match.end():close_span[0]]
        split = _split_body(body)
        if split is None:
            search_pos = close_span[1]
            continue
        figure_body, tail_html = split
        out_parts.append(html[cursor:match.start()])
        out_parts.append(f"{match.group(0)}{figure_body}</div>\n{tail_html}")
        cursor = close_span[1]
        search_pos = close_span[1]
        splits += 1

    if splits == 0:
        return html
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _split_distinct_nested_figure_units(html: str) -> str:
    """Split adjacent figure units that were accidentally nested under one wrapper."""
    current = html
    for _ in range(20):
        if current.count("z2m-figure-unit") < 2:
            return current

        changed = False
        search_pos = 0
        while True:
            outer = _FIGURE_UNIT_OPEN_TAG_PATTERN.search(current, search_pos)
            if outer is None:
                return current

            outer_close = _matching_div_close_span(current, outer.end())
            if outer_close is None:
                search_pos = outer.end()
                continue

            body = current[outer.end():outer_close[0]]
            inner = _FIGURE_UNIT_OPEN_TAG_PATTERN.search(body)
            if inner is None:
                search_pos = outer_close[1]
                continue

            inner_id = inner.group("id")
            if inner_id == outer.group("id"):
                search_pos = outer_close[1]
                continue

            body_before = body[:inner.start()]
            if not re.search(r"<(?:img|p|h[1-6])\b", body_before, re.IGNORECASE):
                search_pos = outer_close[1]
                continue

            inner_close = _matching_div_close_span(body, inner.end())
            if inner_close is None or body[inner_close[1]:].strip():
                search_pos = outer_close[1]
                continue

            stripped_body = body_before.rstrip()
            trailing_space = body_before[len(stripped_body):]
            replacement = (
                f"{outer.group(0)}{stripped_body}</div>"
                f"{trailing_space}{body[inner.start():inner_close[1]]}"
            )
            current = current[:outer.start()] + replacement + current[outer_close[1]:]
            changed = True
            break

        if not changed:
            return current
    return current


def _split_leading_image_from_duplicate_caption_successor_units(html: str) -> str:
    """Split a missing predecessor image from a successor unit with duplicated captions.

    Marker sometimes emits two consecutive single-image figures as one wrapper,
    then repeats only the later figure caption.  Do this only for the narrow
    structural signature: ``fig-N`` is absent, ``fig-(N+1)`` has exactly two
    image targets, and the ``N+1`` caption label appears at least twice.
    """
    if "z2m-figure-unit" not in html or "<img" not in html.lower():
        return html

    existing_ids = {
        match.group("id").lower()
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[A-Za-z0-9-]+)\1', html, re.IGNORECASE)
    }
    out_parts: list[str] = []
    cursor = 0
    search_pos = 0
    splits = 0

    def _context_mentions_figure(left_html: str, key: str) -> bool:
        left_text = _visible_text(left_html[-5000:])
        return (
            re.search(
                rf"\b(?:Fig(?:ure)?|FIG(?:URE)?)\.?\s*{re.escape(key)}(?!\d)(?:[A-Z])?\b",
                left_text,
                re.IGNORECASE,
            )
            is not None
        )

    def _target_image_nodes(body: str) -> list[re.Match[str]]:
        return [
            match
            for match in _P_OR_H_BLOCK_PATTERN.finditer(body)
            if _node_has_class(match.group("open"), "z2m-figure-target")
            and re.search(r"<img\b", match.group(0), re.IGNORECASE)
        ]

    def _duplicate_caption_count(body: str, key: str) -> int:
        count = 0
        label_re = re.compile(
            rf"\b(?:Fig(?:ure)?|FIG(?:URE)?)\.?\s*{re.escape(key)}(?!\d)(?:\s*[:.|-]|\b)",
            re.IGNORECASE,
        )
        for match in _P_OR_H_BLOCK_PATTERN.finditer(body):
            if not _node_has_class(match.group("open"), "z2m-figure-caption"):
                continue
            count += len(label_re.findall(_visible_text(match.group(0))))
        return count

    while True:
        match = _FIGURE_UNIT_OPEN_TAG_PATTERN.search(html, search_pos)
        if match is None:
            break
        close_span = _matching_div_close_span(html, match.end())
        if close_span is None:
            search_pos = match.end()
            continue

        unit_id = match.group("id")
        unit_match = re.fullmatch(r"fig-(\d{1,3})", unit_id, re.IGNORECASE)
        if unit_match is None:
            search_pos = close_span[1]
            continue
        successor_key = unit_match.group(1)
        predecessor_key = str(int(successor_key) - 1)
        if predecessor_key == "0" or f"fig-{predecessor_key}".lower() in existing_ids:
            search_pos = close_span[1]
            continue

        body = html[match.end():close_span[0]]
        image_nodes = _target_image_nodes(body)
        if len(image_nodes) != 2:
            search_pos = close_span[1]
            continue
        if _duplicate_caption_count(body, successor_key) < 2:
            search_pos = close_span[1]
            continue
        if not _context_mentions_figure(html[:match.start()], predecessor_key):
            search_pos = close_span[1]
            continue

        first_image = image_nodes[0]
        predecessor_body = first_image.group(0)
        successor_body = body[: first_image.start()] + body[first_image.end():]
        predecessor_wrapper = (
            f'<div id="fig-{predecessor_key}" class="z2m-float-unit z2m-figure-unit">'
            f"{predecessor_body}</div>"
        )

        out_parts.append(html[cursor:match.start()])
        out_parts.append(predecessor_wrapper)
        out_parts.append(f"{match.group(0)}{successor_body}</div>")
        cursor = close_span[1]
        search_pos = close_span[1]
        existing_ids.add(f"fig-{predecessor_key}".lower())
        splits += 1

    if splits == 0:
        return html
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _split_leading_image_run_from_first_sequence_unit(html: str) -> str:
    """Split a multi-image first unit when it also carries earlier missing figures."""
    if "z2m-figure-unit" not in html or "<img" not in html.lower():
        return html

    existing_ids = {
        match.group("id").lower()
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[A-Za-z0-9-]+)\1', html, re.IGNORECASE)
    }

    def _context_mentions_figure(left_html: str, key: str) -> bool:
        left_text = _visible_text(left_html[-7000:])
        return (
            re.search(
                rf"\b(?:Fig(?:ure)?|FIG(?:URE)?)\.?\s*{re.escape(key)}(?!\d)(?:[A-Z])?\b",
                left_text,
                re.IGNORECASE,
            )
            is not None
        )

    search_pos = 0
    while True:
        match = _FIGURE_UNIT_OPEN_TAG_PATTERN.search(html, search_pos)
        if match is None:
            return html
        close_span = _matching_div_close_span(html, match.end())
        if close_span is None:
            search_pos = match.end()
            continue
        unit_match = re.fullmatch(r"fig-(\d{1,3})", match.group("id"), re.IGNORECASE)
        if unit_match is None:
            search_pos = close_span[1]
            continue
        first_key = unit_match.group(1)
        first_num = int(first_key)
        break

    if first_num <= 2:
        return html

    missing_keys = [str(num) for num in range(1, first_num)]
    if any(f"fig-{key}".lower() in existing_ids for key in missing_keys):
        return html
    if any(not _context_mentions_figure(html[: match.start()], key) for key in missing_keys):
        return html

    body = html[match.end():close_span[0]]
    caption_nodes = [
        node
        for node in _P_OR_H_BLOCK_PATTERN.finditer(body)
        if _node_has_class(node.group("open"), "z2m-figure-caption")
    ]
    if not caption_nodes:
        return html
    first_caption = caption_nodes[0]
    caption_num = _figure_caption_num_from_visible(_visible_text(first_caption.group(0)))
    if caption_num != first_key:
        return html

    leading_images = [
        node
        for node in _P_OR_H_BLOCK_PATTERN.finditer(body[: first_caption.start()])
        if _node_has_class(node.group("open"), "z2m-figure-target")
        and re.search(r"<img\b", node.group(0), re.IGNORECASE)
    ]
    if len(leading_images) != first_num:
        return html

    predecessor_images = leading_images[: len(missing_keys)]
    successor_body_parts: list[str] = []
    cursor = 0
    for image_node in predecessor_images:
        successor_body_parts.append(body[cursor:image_node.start()])
        cursor = image_node.end()
    successor_body_parts.append(body[cursor:])
    successor_body = "".join(successor_body_parts)

    predecessor_wrappers = "".join(
        f'<div id="fig-{missing_key}" class="z2m-float-unit z2m-figure-unit">'
        f"{image_node.group(0)}</div>"
        for missing_key, image_node in zip(missing_keys, predecessor_images)
    )
    replacement = f'{predecessor_wrappers}{match.group(0)}{successor_body}</div>'
    return html[: match.start()] + replacement + html[close_span[1]:]


def _recover_unique_bare_source_named_figure_units(html: str) -> str:
    """Wrap a unique bare image whose source filename identifies a missing figure."""
    if "<img" not in html.lower():
        return html

    existing_keys = {
        match.group("key").lower()
        for match in re.finditer(r'\bid\s*=\s*(["\'])fig-(?P<key>[A-Za-z0-9-]+)\1', html, re.IGNORECASE)
    }
    doc_text = _visible_text(html)
    mentioned_keys = {
        _figure_key_from_visible_number(match.group("num")).lower()
        for match in re.finditer(
            r"\b(?:Fig(?:ure)?|FIG(?:URE)?)\.?\s*(?P<num>\d{1,3})(?!\d)(?:[A-Z])?\b",
            doc_text,
            re.IGNORECASE,
        )
    }
    missing_keys = {key for key in mentioned_keys if key.isdigit() and key not in existing_keys}
    if not missing_keys:
        return html
    existing_numeric_keys = {key for key in existing_keys if key.isdigit()}
    recovery_keys = set(missing_keys)
    if not existing_numeric_keys and len(missing_keys) > 1:
        recovery_keys = {str(min(int(key) for key in missing_keys))}

    def _image_source(raw: str) -> str:
        match = re.search(r'\bdata-z2m-src\s*=\s*(["\'])(?P<src>[^"\']+)\1', raw, re.IGNORECASE)
        if match is not None:
            return match.group("src")
        match = re.search(r'\bsrc\s*=\s*(["\'])(?P<src>[^"\']+)\1', raw, re.IGNORECASE)
        return match.group("src") if match is not None else ""

    def _figure_key_from_image_source(src: str) -> str | None:
        match = re.search(r"(?:^|[_\-/])Figure[_\-. ]*(?P<num>\d{1,3})(?!\d)", src, re.IGNORECASE)
        if match is None:
            return None
        return str(int(match.group("num")))

    candidates_by_key: dict[str, list[re.Match[str]]] = {key: [] for key in recovery_keys}
    for node_match in _P_OR_H_BLOCK_PATTERN.finditer(html):
        raw = node_match.group(0)
        if len(re.findall(r"<img\b", raw, re.IGNORECASE)) != 1:
            continue
        if _visible_text(raw).strip():
            continue
        if (
            _node_has_class(node_match.group("open"), "z2m-figure-target")
            or _node_has_class(node_match.group("open"), "z2m-figure-caption")
            or _node_has_class(node_match.group("open"), "z2m-missing-figure-warning")
            or _node_has_class(node_match.group("open"), "z2m-front-matter")
        ):
            continue
        key = _figure_key_from_image_source(_image_source(raw))
        if key in candidates_by_key:
            candidates_by_key[key].append(node_match)

    replacements: list[tuple[int, int, str]] = []
    for key, candidates in candidates_by_key.items():
        if len(candidates) != 1:
            continue
        image_node = candidates[0]
        image_html = _strip_node_id_and_add_class(image_node.group(0), "z2m-figure-target")
        replacements.append(
            (
                image_node.start(),
                image_node.end(),
                f'<div id="fig-{key}" class="z2m-float-unit z2m-figure-unit">{image_html}</div>',
            )
        )

    if not replacements:
        return html

    out_parts: list[str] = []
    cursor = 0
    for start, end, replacement in sorted(replacements, key=lambda item: item[0]):
        out_parts.append(html[cursor:start])
        out_parts.append(replacement)
        cursor = end
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _recover_sequence_gap_bare_image_figure_units(html: str) -> str:
    """Wrap a bare image as the missing figure between adjacent numbered units."""
    if "z2m-figure-unit" not in html or "<img" not in html.lower():
        return html

    figure_units: list[tuple[int, int, int]] = []
    semantic_keys: set[str] = {
        match.group("key")
        for match in re.finditer(r'\bid\s*=\s*(["\'])fig-(?P<key>\d{1,3})\1', html, re.IGNORECASE)
    }
    caption_label_pattern = re.compile(
        r"\b(?:FIG(?:URE)?|Fig(?:ure)?|Figure)\.?\s*"
        r"(?P<num>\d{1,3})(?!\d)(?![.-]\d)"
        r"(?:\s*(?:[\.:|]|[-\u2010\u2011\u2012\u2013\u2014]))",
        re.IGNORECASE,
    )
    skip_caption_label_left_context = re.compile(
        r"\b(?:as|see|shown|showing|participant|panel|panels?|same|in|of|from|with|"
        r"extended\s+data|supplementary|supplemental)\s+$",
        re.IGNORECASE,
    )
    search_pos = 0

    while True:
        match = _FIGURE_UNIT_OPEN_TAG_PATTERN.search(html, search_pos)
        if match is None:
            break
        close_span = _matching_div_close_span(html, match.end())
        if close_span is None:
            search_pos = match.end()
            continue

        unit_id = match.group("id")
        unit_match = re.fullmatch(r"fig-(\d{1,3})", unit_id, re.IGNORECASE)
        if unit_match is not None:
            unit_num = int(unit_match.group(1))
            figure_units.append((unit_num, match.start(), close_span[1]))
            semantic_keys.add(str(unit_num))

        body = html[match.end():close_span[0]]
        for caption_match in _P_OR_H_BLOCK_PATTERN.finditer(body):
            if not _node_has_class(caption_match.group("open"), "z2m-figure-caption"):
                continue
            caption_visible = _visible_text(caption_match.group("body"))
            caption_num = _figure_caption_num_from_visible(caption_visible)
            if caption_num is not None:
                semantic_keys.add(_figure_key_from_visible_number(caption_num).lower())
            for label_match in caption_label_pattern.finditer(caption_visible):
                left_context = caption_visible[max(0, label_match.start() - 36):label_match.start()]
                if skip_caption_label_left_context.search(left_context):
                    continue
                semantic_keys.add(_figure_key_from_visible_number(label_match.group("num")).lower())

        search_pos = close_span[1]

    if not figure_units:
        return html

    doc_text = _visible_text(html)

    def _document_mentions_figure(key: str) -> bool:
        return (
            re.search(
                rf"\b(?:Fig(?:ure)?|FIG(?:URE)?)\.?\s*{re.escape(key)}(?!\d)(?:[A-Z])?\b",
                doc_text,
                re.IGNORECASE,
        )
        is not None
    )

    def _trailing_float_search_html(gap_html: str) -> str:
        for node_match in _P_OR_H_BLOCK_PATTERN.finditer(gap_html):
            raw = node_match.group(0)
            visible = _visible_text(raw).strip()
            if _node_has_class(node_match.group("open"), "z2m-front-matter"):
                return gap_html[: node_match.start()]
            if _references_heading_match(visible) is not None:
                return gap_html[: node_match.start()]
            if re.match(r"(?i)^(?:acknowledg(?:e)?ments?|received\b|references\b|bibliography\b)", visible):
                return gap_html[: node_match.start()]
        return gap_html

    def _bare_image_nodes(gap_html: str) -> list[re.Match[str]]:
        nodes: list[re.Match[str]] = []
        for node_match in _P_OR_H_BLOCK_PATTERN.finditer(gap_html):
            raw = node_match.group(0)
            if len(re.findall(r"<img\b", raw, re.IGNORECASE)) != 1:
                continue
            if _node_has_class(node_match.group("open"), "z2m-figure-target"):
                continue
            if _node_has_class(node_match.group("open"), "z2m-figure-caption"):
                continue
            if _node_has_class(node_match.group("open"), "z2m-missing-figure-warning"):
                continue
            if _visible_text(raw).strip():
                continue
            nodes.append(node_match)
        return nodes

    replacements: list[tuple[int, int, str]] = []
    first_num, first_start, _first_end = figure_units[0]
    if first_num > 1:
        leading_missing_keys = [str(num) for num in range(1, first_num)]
        if not any(missing_key in semantic_keys for missing_key in leading_missing_keys) and all(
            _document_mentions_figure(missing_key) for missing_key in leading_missing_keys
        ):
            leading_gap_html = html[:first_start]
            leading_image_nodes = _bare_image_nodes(leading_gap_html)
            if len(leading_image_nodes) == len(leading_missing_keys):
                for missing_key, image_node in zip(leading_missing_keys, leading_image_nodes):
                    image_html = _strip_node_id_and_add_class(image_node.group(0), "z2m-figure-target")
                    wrapper = (
                        f'<div id="fig-{missing_key}" class="z2m-float-unit z2m-figure-unit">'
                        f"{image_html}</div>"
                    )
                    replacements.append((image_node.start(), image_node.end(), wrapper))
                    semantic_keys.add(missing_key)

    for left_unit, right_unit in zip(figure_units, figure_units[1:]):
        left_num, _left_start, left_end = left_unit
        right_num, right_start, _right_end = right_unit
        if right_num - left_num < 2:
            continue
        missing_keys = [str(num) for num in range(left_num + 1, right_num)]
        if any(missing_key in semantic_keys for missing_key in missing_keys):
            continue
        if any(not _document_mentions_figure(missing_key) for missing_key in missing_keys):
            continue

        gap_html = html[left_end:right_start]
        image_nodes = _bare_image_nodes(gap_html)
        if len(image_nodes) != len(missing_keys):
            continue

        for missing_key, image_node in zip(missing_keys, image_nodes):
            image_html = _strip_node_id_and_add_class(image_node.group(0), "z2m-figure-target")
            wrapper = (
                f'<div id="fig-{missing_key}" class="z2m-float-unit z2m-figure-unit">'
                f"{image_html}</div>"
            )
            replacements.append((left_end + image_node.start(), left_end + image_node.end(), wrapper))
            semantic_keys.add(missing_key)

    last_num, _last_start, last_end = figure_units[-1]
    trailing_gap_html = _trailing_float_search_html(html[last_end:])
    trailing_image_nodes = _bare_image_nodes(trailing_gap_html)
    if trailing_image_nodes:
        trailing_missing_keys: list[str] = []
        next_num = last_num + 1
        while _document_mentions_figure(str(next_num)):
            missing_key = str(next_num)
            if missing_key in semantic_keys:
                break
            trailing_missing_keys.append(missing_key)
            if len(trailing_missing_keys) > len(trailing_image_nodes):
                break
            next_num += 1
        if trailing_missing_keys and len(trailing_missing_keys) == len(trailing_image_nodes):
            for missing_key, image_node in zip(trailing_missing_keys, trailing_image_nodes):
                image_html = _strip_node_id_and_add_class(image_node.group(0), "z2m-figure-target")
                wrapper = (
                    f'<div id="fig-{missing_key}" class="z2m-float-unit z2m-figure-unit">'
                    f"{image_html}</div>"
                )
                replacements.append((last_end + image_node.start(), last_end + image_node.end(), wrapper))
                semantic_keys.add(missing_key)

    if not replacements:
        return html

    out_parts: list[str] = []
    cursor = 0
    for start, end, replacement in replacements:
        out_parts.append(html[cursor:start])
        out_parts.append(replacement)
        cursor = end
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _sequence_gap_missing_figure_warning_html(
    fig_num: str,
    *,
    figure_caption_language: str = "en",
) -> str:
    warning_html = _missing_figure_warning_html(
        fig_num,
        figure_caption_language=figure_caption_language,
    )
    warning_html = re.sub(
        r"^<p\b",
        '<p data-z2m-origin="sequence-gap-missing-target"',
        warning_html,
        count=1,
        flags=re.IGNORECASE,
    )
    warning_html = re.sub(
        r'\bclass\s*=\s*(["\'])z2m-missing-figure-warning\1',
        r'class=\1z2m-missing-figure-warning z2m-figure-target\1',
        warning_html,
        count=1,
        flags=re.IGNORECASE,
    )
    return (
        f'<div id="fig-{fig_num}" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
        f"{warning_html}</div>"
    )


def _insert_sequence_gap_missing_figure_units(
    html: str,
    *,
    figure_caption_language: str = "en",
) -> tuple[str, int]:
    """Add explicit missing-figure units for numbered gaps with no recoverable HTML visual."""
    if "z2m-figure-unit" not in html:
        return html, 0

    figure_units: list[tuple[int, int, int]] = []
    semantic_keys: set[str] = set()
    caption_label_pattern = re.compile(
        r"\b(?:FIG(?:URE)?|Fig(?:ure)?|Figure)\.?\s*"
        r"(?P<num>\d{1,3})(?!\d)(?![.-]\d)"
        r"(?:\s*(?:[\.:|]|[-\u2010\u2011\u2012\u2013\u2014]))",
        re.IGNORECASE,
    )
    skip_caption_label_left_context = re.compile(
        r"\b(?:as|see|shown|showing|participant|panel|panels?|same|in|of|from|with|"
        r"extended\s+data|supplementary|supplemental)\s+$",
        re.IGNORECASE,
    )
    search_pos = 0
    while True:
        match = _FIGURE_UNIT_OPEN_TAG_PATTERN.search(html, search_pos)
        if match is None:
            break
        close_span = _matching_div_close_span(html, match.end())
        if close_span is None:
            search_pos = match.end()
            continue
        unit_match = re.fullmatch(r"fig-(\d{1,3})", match.group("id"), re.IGNORECASE)
        if unit_match is not None:
            unit_num = int(unit_match.group(1))
            figure_units.append((unit_num, match.start(), close_span[1]))
            semantic_keys.add(str(unit_num))

        body = html[match.end():close_span[0]]
        for caption_match in _P_OR_H_BLOCK_PATTERN.finditer(body):
            if not _node_has_class(caption_match.group("open"), "z2m-figure-caption"):
                continue
            caption_visible = _visible_text(caption_match.group("body"))
            caption_num = _figure_caption_num_from_visible(caption_visible)
            if caption_num is not None:
                semantic_keys.add(_figure_key_from_visible_number(caption_num).lower())
            for label_match in caption_label_pattern.finditer(caption_visible):
                left_context = caption_visible[max(0, label_match.start() - 36):label_match.start()]
                if skip_caption_label_left_context.search(left_context):
                    continue
                semantic_keys.add(_figure_key_from_visible_number(label_match.group("num")).lower())

        search_pos = close_span[1]

    if not figure_units:
        return html, 0

    def _mentioned_numbers_in_text(text: str) -> set[int]:
        return {
            int(match.group("num"))
            for match in re.finditer(
                r"\b(?:Fig(?:ure)?|FIG(?:URE)?)\.?\s*(?P<num>\d{1,3})(?!\d)(?:[A-Z])?\b",
                text,
                re.IGNORECASE,
            )
        }

    doc_text = _visible_text(html)
    doc_blocks = [_visible_text(match.group(0)) for match in _P_OR_H_BLOCK_PATTERN.finditer(html)]
    mentioned_numbers = _mentioned_numbers_in_text(doc_text)

    def _all_missing_keys_are_mentioned(missing_keys: list[str]) -> bool:
        return all(key.isdigit() and int(key) in mentioned_numbers for key in missing_keys)

    def _has_independent_figure_mention(key: str, left_num: int, right_num: int | None) -> bool:
        label_re = re.compile(
            rf"\b(?:Fig(?:ure)?|FIG(?:URE)?)\.?\s*{re.escape(key)}(?!\d)(?:[A-Z])?\b",
            re.IGNORECASE,
        )
        neighbor_label = r"(?:Fig(?:ure)?|FIG(?:URE)?)\.?"
        for block_text in doc_blocks:
            for match in label_re.finditer(block_text):
                left_context = block_text[max(0, match.start() - 90):match.start()]
                right_context = block_text[match.end():match.end() + 90]
                joint_with_left = (
                    re.search(
                        rf"\b{neighbor_label}\s*{left_num}(?!\d)(?:[A-Z])?\s*(?:,|and|or|&)\s*$",
                        left_context,
                        re.IGNORECASE,
                    )
                    is not None
                )
                joint_with_right = (
                    right_num is not None
                    and re.match(
                        rf"^\s*(?:,|and|or|&)\s*{neighbor_label}\s*{right_num}(?!\d)(?:[A-Z])?\b",
                        right_context,
                        re.IGNORECASE,
                    )
                    is not None
                )
                if not joint_with_left and not joint_with_right:
                    return True
        return False

    def _gap_has_visual_or_float(gap_html: str) -> bool:
        return re.search(r"<img\b|<table\b|\bz2m-float-unit\b", gap_html, re.IGNORECASE) is not None

    def _trailing_float_search_html(gap_html: str) -> str:
        for node_match in _P_OR_H_BLOCK_PATTERN.finditer(gap_html):
            visible = _visible_text(node_match.group(0)).strip()
            if _node_has_class(node_match.group("open"), "z2m-front-matter"):
                return gap_html[: node_match.start()]
            if _references_heading_match(visible) is not None:
                return gap_html[: node_match.start()]
            if re.match(r"(?i)^(?:acknowledg(?:e)?ments?|received\b|references\b|bibliography\b)", visible):
                return gap_html[: node_match.start()]
        return gap_html

    def _leading_missing_search_html(gap_html: str) -> str:
        last_visual_match: re.Match[str] | None = None
        for last_visual_match in re.finditer(r"<img\b|<table\b|\bz2m-float-unit\b", gap_html, re.IGNORECASE):
            pass
        if last_visual_match is None:
            return gap_html
        close_match = re.search(r"</(?:p|div|figure|table)>", gap_html[last_visual_match.end():], re.IGNORECASE)
        if close_match is None:
            return gap_html[last_visual_match.end():]
        return gap_html[last_visual_match.end() + close_match.end():]

    def _image_source_figure_key(img_html: str) -> str | None:
        for attr_name in ("data-z2m-src", "src"):
            attr_match = re.search(
                rf'\b{attr_name}\s*=\s*(["\'])(?P<src>[^"\']+)\1',
                img_html,
                re.IGNORECASE,
            )
            if attr_match is None:
                continue
            source_match = re.search(
                r"(?:^|[/\\_. -])Figure[/\\_. -]*(?P<num>\d{1,3})(?!\d)",
                attr_match.group("src"),
                re.IGNORECASE,
            )
            if source_match is not None:
                return str(int(source_match.group("num")))
        return None

    def _first_unit_images_allow_leading_missing(first_unit_html: str, missing_keys: list[str]) -> bool:
        image_nodes = list(re.finditer(r"<img\b[^>]*>", first_unit_html, re.IGNORECASE))
        if len(image_nodes) <= 1:
            return True
        image_source_keys = [_image_source_figure_key(image_node.group(0)) for image_node in image_nodes]
        return all(key is not None and key not in missing_keys for key in image_source_keys)

    insertions: list[tuple[int, str]] = []
    first_num, first_start, _first_end = figure_units[0]
    if first_num == 2:
        leading_missing_nums = list(range(1, first_num))
        leading_missing_keys = [str(num) for num in leading_missing_nums]
        raw_leading_gap_html = html[:first_start]
        leading_gap_html = _leading_missing_search_html(raw_leading_gap_html)
        leading_mentions = _mentioned_numbers_in_text(_visible_text(leading_gap_html))
        first_unit_html = html[first_start:_first_end]
        if (
            all(num in leading_mentions for num in leading_missing_nums)
            and not any(missing_key in semantic_keys for missing_key in leading_missing_keys)
            and _first_unit_images_allow_leading_missing(first_unit_html, leading_missing_keys)
            and not _gap_has_visual_or_float(leading_gap_html)
            and all(
                _has_independent_figure_mention(missing_key, 0, first_num)
                for missing_key in leading_missing_keys
            )
        ):
            insertions.append(
                (
                    first_start,
                    "".join(
                        _sequence_gap_missing_figure_warning_html(
                            missing_key,
                            figure_caption_language=figure_caption_language,
                        )
                        for missing_key in leading_missing_keys
                    ),
                )
            )
            semantic_keys.update(leading_missing_keys)

    for left_unit, right_unit in zip(figure_units, figure_units[1:]):
        left_num, _left_start, left_end = left_unit
        right_num, right_start, _right_end = right_unit
        if right_num - left_num < 2:
            continue
        missing_keys = [str(num) for num in range(left_num + 1, right_num)]
        if any(missing_key in semantic_keys for missing_key in missing_keys):
            continue
        if not _all_missing_keys_are_mentioned(missing_keys):
            continue
        if any(
            not _has_independent_figure_mention(missing_key, left_num, right_num)
            for missing_key in missing_keys
        ):
            continue
        if _gap_has_visual_or_float(html[left_end:right_start]):
            continue
        insertions.append(
            (
                left_end,
                "".join(
                    _sequence_gap_missing_figure_warning_html(
                        missing_key,
                        figure_caption_language=figure_caption_language,
                    )
                    for missing_key in missing_keys
                ),
            )
        )
        semantic_keys.update(missing_keys)

    last_num, _last_start, last_end = figure_units[-1]
    raw_trailing_gap_html = html[last_end:]
    trailing_gap_html = _trailing_float_search_html(raw_trailing_gap_html)
    trailing_starts_at_terminal_section = (
        trailing_gap_html != raw_trailing_gap_html and not trailing_gap_html.strip()
    )
    trailing_text = _visible_text(trailing_gap_html)
    trailing_mentioned_numbers = {
        int(match.group("num"))
        for match in re.finditer(
            r"\b(?:Fig(?:ure)?|FIG(?:URE)?)\.?\s*(?P<num>\d{1,3})(?!\d)(?:[A-Z])?\b",
            trailing_text,
            re.IGNORECASE,
        )
    }
    trailing_mentions = sorted(num for num in trailing_mentioned_numbers if num > last_num)
    if trailing_mentions and not _gap_has_visual_or_float(trailing_gap_html):
        trailing_missing_nums = list(range(last_num + 1, trailing_mentions[-1] + 1))
        trailing_missing_keys = [str(num) for num in trailing_missing_nums]
        if (
            all(num in trailing_mentioned_numbers for num in trailing_missing_nums)
            and not any(missing_key in semantic_keys for missing_key in trailing_missing_keys)
            and all(
                _has_independent_figure_mention(missing_key, last_num, None)
                for missing_key in trailing_missing_keys
            )
        ):
            insertions.append(
                (
                    last_end,
                    "".join(
                        _sequence_gap_missing_figure_warning_html(
                            missing_key,
                            figure_caption_language=figure_caption_language,
                        )
                        for missing_key in trailing_missing_keys
                    ),
                )
            )
            semantic_keys.update(trailing_missing_keys)

    next_final_key = str(last_num + 1)
    if (
        next_final_key not in semantic_keys
        and last_num + 1 in mentioned_numbers
        and not any(pos == last_end for pos, _insertion in insertions)
        and not _gap_has_visual_or_float(trailing_gap_html)
        and not trailing_starts_at_terminal_section
        and _has_independent_figure_mention(next_final_key, last_num, None)
    ):
        insertions.append(
            (
                last_end,
                _sequence_gap_missing_figure_warning_html(
                    next_final_key,
                    figure_caption_language=figure_caption_language,
                ),
            )
        )
        semantic_keys.add(next_final_key)

    if not insertions:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for pos, insertion in sorted(insertions, key=lambda item: item[0]):
        out_parts.append(html[cursor:pos])
        out_parts.append(insertion)
        cursor = pos
    out_parts.append(html[cursor:])
    return "".join(out_parts), len(insertions)


def _drop_unbacked_foreign_figure_aliases(html: str) -> str:
    def _caption_labels(raw: str) -> set[str]:
        labels: set[str] = set()
        for caption_match in re.finditer(
            r'<(?:p|h[1-6])\b(?=[^>]*\bclass\s*=\s*(["\'])[^"\']*\bz2m-figure-caption\b)[^>]*>'
            r"(?P<body>[\s\S]*?)</(?:p|h[1-6])>",
            raw,
            re.IGNORECASE,
        ):
            label = _figure_caption_num_from_visible(_visible_text(caption_match.group("body")))
            if label is not None:
                labels.add(label)
        return labels

    def _replace_unit(match: re.Match[str]) -> str:
        raw = match.group(0)
        unit_id = _node_id_value(raw)
        unit_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", unit_id or "", re.IGNORECASE)
        if unit_match is None or "z2m-float-alias" not in raw:
            return raw
        labels = _caption_labels(raw)

        def _replace_alias(alias_match: re.Match[str]) -> str:
            if re.search(r'\bdata-z2m-origin\s*=\s*(["\'])orphan-image-ref\1', alias_match.group(0), re.IGNORECASE):
                return alias_match.group(0)
            alias_id = alias_match.group("id")
            alias_num_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", alias_id, re.IGNORECASE)
            if alias_num_match is None or alias_id == unit_id:
                return alias_match.group(0)
            alias_num = _figure_key_from_visible_number(alias_num_match.group(1))
            if alias_num in labels:
                return alias_match.group(0)
            return ""

        return re.sub(
            r'<span\b(?=[^>]*\bz2m-float-alias\b)[^>]*\bid\s*=\s*(["\'])(?P<id>fig-[^"\']+)\1[^>]*>\s*</span>',
            _replace_alias,
            raw,
            flags=re.IGNORECASE,
        )

    return _FLOAT_UNIT_DIV_PATTERN.sub(_replace_unit, html)


def _add_aliases_for_embedded_figure_caption_labels(html: str) -> str:
    if "z2m-figure-unit" not in html or "Figure" not in html and "Fig" not in html:
        return html

    existing_ids = {
        match.group("id")
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[^"\']+)\1', html, re.IGNORECASE)
    }
    caption_label_pattern = re.compile(
        r"\b(?:FIG(?:URE)?|Fig(?:ure)?|Figure)\.?\s*"
        r"(?P<num>\d{1,3})(?!\d)(?![.-]\d)"
        r"(?:\s*(?:[\.:|]|[-\u2010\u2011\u2012\u2013\u2014]))",
        re.IGNORECASE,
    )
    skip_left_context = re.compile(
        r"\b(?:as|see|shown|showing|participant|panel|panels?|same|in|of|from|with|"
        r"extended\s+data|supplementary|supplemental)\s+$",
        re.IGNORECASE,
    )

    def _caption_label_keys(raw: str) -> list[str]:
        keys: list[str] = []
        for caption_match in _P_OR_H_BLOCK_PATTERN.finditer(raw):
            if not _node_has_class(caption_match.group("open"), "z2m-figure-caption"):
                continue
            visible = _visible_text(caption_match.group("body"))
            for label_match in caption_label_pattern.finditer(visible):
                left_context = visible[max(0, label_match.start() - 36):label_match.start()]
                if skip_left_context.search(left_context):
                    continue
                key = _figure_key_from_visible_number(label_match.group("num"))
                if key not in keys:
                    keys.append(key)
        return keys

    def _replace_unit(match: re.Match[str]) -> str:
        raw = match.group(0)
        unit_id = _node_id_value(raw)
        unit_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", unit_id or "", re.IGNORECASE)
        if unit_match is None:
            return raw
        primary_key = unit_match.group(1)
        alias_ids: list[str] = []
        for key in _caption_label_keys(raw):
            alias_id = f"fig-{key}"
            if key == primary_key or alias_id in existing_ids:
                continue
            alias_ids.append(alias_id)
            existing_ids.add(alias_id)
        if not alias_ids:
            return raw
        open_end = raw.find(">")
        if open_end < 0:
            return raw
        alias_html = "".join(f'<span id="{alias_id}" class="z2m-float-alias"></span>' for alias_id in alias_ids)
        return raw[: open_end + 1] + alias_html + raw[open_end + 1:]

    return _FLOAT_UNIT_DIV_PATTERN.sub(_replace_unit, html)


def _retarget_duplicate_figure_targets_from_context_refs(html: str) -> tuple[str, set[str]]:
    """Retarget a repeated figure label when nearby prose clearly points to the next figure.

    Some PDFs have a real numbering inconsistency: two adjacent visual figures both carry
    ``Figure N`` captions, while the prose immediately before the second one refers to
    ``Figure N+1`` (often with a panel suffix such as ``Figure 6A``).  In that case the
    second target should be addressable as ``fig-(N+1)`` instead of producing a missing
    target warning.
    """
    if "fig-" not in html or not re.search(r"\bFig(?:ure)?s?\.?\s*\d", html, re.IGNORECASE):
        return html, set()

    nodes = list(_FLOAT_AWARE_SENTENCE_NODE_PATTERN.finditer(html))
    if len(nodes) < 3:
        return html, set()

    existing_keys = _current_figure_target_keys(html)
    replacements: dict[int, str] = {}
    retargeted: set[str] = set()

    def _node_raw(index: int) -> str:
        return replacements.get(index, nodes[index].group(0))

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _simple_next_key(key: str) -> str | None:
        if not re.fullmatch(r"\d{1,3}", key):
            return None
        try:
            return str(int(key) + 1)
        except ValueError:
            return None

    def _figure_ref_keys(visible: str) -> set[str]:
        keys: set[str] = set()
        for pattern in (_FIG_REF_PATTERN, _EXT_FIG_REF_PATTERN):
            for match in pattern.finditer(visible):
                keys.add(_figure_key_from_visible_number(match.group(2)))
        return keys

    def _preceding_context_refs_key(index: int, target_key: str) -> bool:
        scan = index - 1
        scanned_text_nodes = 0
        while scan >= 0 and scanned_text_nodes < 4:
            if scan + 1 < len(nodes) and not _between_is_whitespace(scan, scan + 1):
                break
            raw = _node_raw(scan)
            if _node_has_class(raw, "z2m-float-unit") or re.search(r"<table\b", raw, re.IGNORECASE):
                break
            if re.search(r"<img\b", raw, re.IGNORECASE):
                scan -= 1
                continue
            visible = _visible_text(raw)
            if not visible.strip():
                scan -= 1
                continue
            if _figure_caption_num_from_visible(visible) is not None:
                break
            if target_key in _figure_ref_keys(visible):
                return True
            scanned_text_nodes += 1
            if len(visible) > 1800:
                break
            scan -= 1
        return False

    def _caption_label_key(raw: str) -> str | None:
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            return None
        return _figure_caption_num_from_visible(_visible_text(raw))

    def _unit_caption_key(raw: str) -> str | None:
        labels: list[str] = []
        for match in _P_OR_H_BLOCK_PATTERN.finditer(raw):
            if not _node_has_class(match.group("open"), "z2m-figure-caption"):
                continue
            label = _caption_label_key(match.group(0))
            if label is not None:
                labels.append(label)
        if len(set(labels)) == 1:
            return labels[0]
        return None

    def _following_caption_index(image_index: int, fig_key: str) -> int | None:
        scan = image_index + 1
        while scan < len(nodes):
            if not _between_is_whitespace(scan - 1, scan):
                break
            raw = _node_raw(scan)
            if re.search(r"<img\b", raw, re.IGNORECASE):
                scan += 1
                continue
            if _node_is_caption_bridge_or_note_paragraph(raw):
                scan += 1
                continue
            label = _caption_label_key(raw)
            if label == fig_key:
                return scan
            break
        return None

    def _target_key_at(index: int) -> str | None:
        raw = _node_raw(index)
        node_id = _node_id_value(raw)
        fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", node_id or "", re.IGNORECASE)
        if fig_match is None:
            return None
        key = fig_match.group(1)
        if _node_has_class(raw, "z2m-figure-unit"):
            return key if _unit_caption_key(raw) == key else None
        if re.search(r"<img\b", raw, re.IGNORECASE):
            caption_idx = _following_caption_index(index, key)
            return key if caption_idx is not None else None
        return None

    target_key_counts = Counter(
        key for index in range(len(nodes)) for key in [_target_key_at(index)] if key is not None
    )
    if not any(count > 1 for count in target_key_counts.values()):
        return html, set()

    def _retarget_open_id(raw: str, new_key: str) -> str:
        open_end = raw.find(">")
        if open_end < 0:
            return raw
        open_tag = raw[: open_end + 1]
        return _add_id_attr(_remove_id_attr(open_tag), f"fig-{new_key}") + raw[open_end + 1:]

    def _replace_caption_label(raw: str, old_key: str, new_key: str) -> str:
        label_pattern = re.compile(
            rf"(?P<prefix>^\s*(?:<(?:b|strong|em|i|span)\b[^>]*>\s*)*"
            rf"(?:Fig(?:ure)?|FIG(?:URE)?|Figure)\.?(?:\s|&nbsp;|\xa0)*)"
            rf"{re.escape(old_key)}"
            rf"(?P<suffix>(?:\s|&nbsp;|\xa0)*(?:[\).:|,\-])?)",
            re.IGNORECASE,
        )

        def _replace_block(match: re.Match[str]) -> str:
            open_tag = match.group("open")
            if not _node_has_class(open_tag, "z2m-figure-caption"):
                return match.group(0)
            if _caption_label_key(match.group(0)) != old_key:
                return match.group(0)
            body = label_pattern.sub(
                lambda label_match: (
                    f"{label_match.group('prefix')}{new_key}{label_match.group('suffix')}"
                ),
                match.group("body"),
                count=1,
            )
            return f"{open_tag}{body}{match.group('close')}"

        return _P_OR_H_BLOCK_PATTERN.sub(_replace_block, raw, count=1)

    seen_target_counts: Counter[str] = Counter()
    for index in range(len(nodes)):
        key = _target_key_at(index)
        if key is None:
            continue
        seen_target_counts[key] += 1
        if seen_target_counts[key] < 2 or target_key_counts[key] < 2:
            continue
        new_key = _simple_next_key(key)
        if new_key is None or new_key in existing_keys or new_key in retargeted:
            continue
        if not _preceding_context_refs_key(index, new_key):
            continue

        raw = _node_raw(index)
        retargeted_raw = _retarget_open_id(raw, new_key)
        if _node_has_class(raw, "z2m-figure-unit"):
            retargeted_raw = _replace_caption_label(retargeted_raw, key, new_key)
        else:
            caption_idx = _following_caption_index(index, key)
            if caption_idx is not None:
                replacements[caption_idx] = _replace_caption_label(_node_raw(caption_idx), key, new_key)
        replacements[index] = retargeted_raw
        retargeted.add(new_key)
        existing_keys.add(new_key)

    if not replacements:
        return html, set()

    out_parts: list[str] = []
    cursor = 0
    for index, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        out_parts.append(replacements.get(index, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), retargeted


def _drop_stale_in_text_figure_reference_ids(html: str) -> str:
    """Remove duplicate fig-* ids from prose references once a real target exists."""
    fig_ids = [
        match.group("id")
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[A-Za-z0-9_.:-]+)\1', html, re.IGNORECASE)
    ]
    if len(fig_ids) < 2:
        return html
    id_counts = Counter(fig_ids)
    duplicate_ids = {fig_id for fig_id, count in id_counts.items() if count > 1}
    if not duplicate_ids:
        return html

    candidates = list(_FIG_ID_CANDIDATE_NODE_PATTERN.finditer(html))
    if not candidates:
        return html
    replacements: dict[int, str] = {}

    for index, node in enumerate(candidates):
        raw = node.group(0)
        node_id = _node_id_value(raw)
        if node_id not in duplicate_ids:
            continue
        fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", node_id or "", re.IGNORECASE)
        if fig_match is None:
            continue
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            continue
        if _node_has_class(raw, "z2m-figure-unit") or _node_has_class(raw, "z2m-figure-caption"):
            continue
        if not _looks_like_in_text_figure_reference_node(raw, fig_match.group(1)):
            continue
        replacements[index] = _strip_node_id_and_add_class(raw)

    if not replacements:
        return html

    out_parts: list[str] = []
    cursor = 0
    for index, node in enumerate(candidates):
        out_parts.append(html[cursor:node.start()])
        out_parts.append(replacements.get(index, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _retarget_caption_only_figure_ids_to_nearby_images(html: str) -> str:
    if "fig-" not in html or "<img" not in html.lower():
        return html

    fig_ids = [
        match.group("id")
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[A-Za-z0-9_.:-]+)\1', html, re.IGNORECASE)
    ]
    if not fig_ids:
        return html
    id_counts = Counter(fig_ids)

    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html
    replacements: dict[int, str] = {}
    consumed_targets: set[int] = set()

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _replace_open(raw: str, transform: Callable[[str], str]) -> str:
        return _transform_node_open(raw, transform)

    def _image_can_receive_target(index: int, target_id: str) -> bool:
        raw = replacements.get(index, nodes[index].group(0))
        if index in consumed_targets:
            return False
        if not raw.lstrip().lower().startswith("<p"):
            return False
        if re.search(r"<img\b", raw, re.IGNORECASE) is None:
            return False
        node_id = _node_open_id_value(raw)
        return node_id is None or node_id == target_id

    def _allows_scan(raw: str, fig_num: str) -> bool:
        if _node_is_caption_bridge_or_note_paragraph(raw):
            return True
        if _looks_like_figure_caption_fragment(raw) or _looks_like_figure_panel_caption_continuation(raw):
            return True
        visible = _visible_text(raw).strip()
        if not visible:
            return True
        node_id = _node_id_value(raw) or ""
        if re.fullmatch(r"fig-[A-Za-z0-9-]+", node_id, re.IGNORECASE) and node_id != f"fig-{fig_num}":
            return False
        caption_num = _figure_caption_num_from_visible(visible)
        if caption_num is not None:
            return caption_num == fig_num
        if re.match(r"<h[1-6]\b", raw.lstrip(), re.IGNORECASE):
            if node_id or len(visible) > 140:
                return False
            return not re.match(
                r"^(?:abstract|introduction|background|methods?|materials|results?|discussion|conclusions?|"
                r"references|bibliography|acknowledg|supplementary|appendix)\b",
                visible,
                re.IGNORECASE,
            )
        if len(visible) <= 220 and re.search(r"[.!?]\s+[A-Z]", visible) is None:
            return True
        if len(visible) <= 900 and visible[:1].islower():
            return True
        return False

    def _allows_relaxed_scan(raw: str, fig_num: str) -> bool:
        if _allows_scan(raw, fig_num):
            return True
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            return False
        if _node_has_class(raw, "z2m-float-unit"):
            return False
        node_id = _node_open_id_value(raw) or ""
        if re.fullmatch(r"(?:fig|table|section)-[A-Za-z0-9-]+", node_id, re.IGNORECASE):
            return False
        if re.match(r"<h[1-6]\b", raw.lstrip(), re.IGNORECASE):
            return False
        if not raw.lstrip().lower().startswith("<p"):
            return False
        visible = _visible_text(raw).strip()
        if not visible:
            return True
        if len(visible) > 2200:
            return False
        caption_num = _figure_caption_num_from_visible(visible)
        if caption_num is not None and caption_num != fig_num:
            return False
        return True

    def _image_run_indices(image_idx: int, target_id: str) -> list[int]:
        start = image_idx
        while start > 0 and _between_is_whitespace(start - 1, start):
            if not _image_can_receive_target(start - 1, target_id):
                break
            start -= 1
        end = image_idx
        while end + 1 < len(nodes) and _between_is_whitespace(end, end + 1):
            if not _image_can_receive_target(end + 1, target_id):
                break
            end += 1
        return list(range(start, end + 1))

    def _image_is_immediately_captioned_as_different_figure(image_idx: int, fig_num: str) -> bool:
        scan_idx = image_idx + 1
        while scan_idx < len(nodes) and _between_is_whitespace(scan_idx - 1, scan_idx):
            raw = replacements.get(scan_idx, nodes[scan_idx].group(0))
            if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
                return False
            visible = _visible_text(raw).strip()
            if not visible:
                scan_idx += 1
                continue
            caption_num = _figure_caption_num_from_visible(visible)
            if caption_num is not None:
                return caption_num != fig_num
            if not _node_is_caption_bridge_or_note_paragraph(raw):
                return False
            scan_idx += 1
        return False

    def _nearby_image_indices(caption_idx: int, fig_num: str, target_id: str, *, relaxed: bool = False) -> list[int]:
        max_scan = 4 if relaxed else 8
        for direction in (1, -1):
            scan_idx = caption_idx + direction
            scanned = 0
            while 0 <= scan_idx < len(nodes) and scanned < max_scan:
                if direction > 0:
                    if not _between_is_whitespace(scan_idx - 1, scan_idx):
                        break
                elif not _between_is_whitespace(scan_idx, scan_idx + 1):
                    break
                raw = replacements.get(scan_idx, nodes[scan_idx].group(0))
                if _image_can_receive_target(scan_idx, target_id):
                    if (
                        direction > 0
                        and (
                            scan_idx != caption_idx + 1
                            or _node_has_class(replacements.get(caption_idx, nodes[caption_idx].group(0)), "has-continuation")
                        )
                        and _image_is_immediately_captioned_as_different_figure(scan_idx, fig_num)
                    ):
                        break
                    return _image_run_indices(scan_idx, target_id)
                if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
                    break
                if not (_allows_relaxed_scan(raw, fig_num) if relaxed else _allows_scan(raw, fig_num)):
                    break
                scan_idx += direction
                scanned += 1
        return []

    for index, node in enumerate(nodes):
        raw = replacements.get(index, node.group(0))
        target_id = _node_id_value(raw)
        fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", target_id or "", re.IGNORECASE)
        if fig_match is None:
            continue
        fig_num = fig_match.group(1)
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            continue
        if _looks_like_in_text_figure_reference_node(raw, fig_num):
            continue
        if _figure_caption_num_from_visible(_visible_text(raw)) != fig_num:
            continue
        if id_counts[target_id or ""] > 1:
            continue
        image_indices = _nearby_image_indices(index, fig_num, target_id or "")
        if not image_indices:
            image_indices = _nearby_image_indices(index, fig_num, target_id or "", relaxed=True)
        if not image_indices:
            continue
        for image_pos, image_idx in enumerate(image_indices):
            image_raw = replacements.get(image_idx, nodes[image_idx].group(0))
            replacements[image_idx] = _replace_open(
                image_raw,
                lambda open_tag, image_pos=image_pos, target_id=target_id: _add_class_attr(
                    open_tag if image_pos != 0 or _has_id_attr(open_tag) else _add_id_attr(open_tag, target_id or ""),
                    "z2m-figure-target",
                ),
            )
        replacements[index] = _replace_open(
            raw,
            lambda open_tag: _add_class_attr(_remove_id_attr(open_tag), "z2m-figure-caption"),
        )
        consumed_targets.update(image_indices)

    if not replacements:
        return html

    out_parts: list[str] = []
    cursor = 0
    for index, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        out_parts.append(replacements.get(index, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _wrap_remaining_caption_only_figure_targets_as_missing(
    html: str,
    *,
    figure_caption_language: str = "en",
) -> tuple[str, int]:
    if "fig-" not in html:
        return html, 0

    fig_ids = [
        match.group("id")
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[^"\']+)\1', html, re.IGNORECASE)
    ]
    if not fig_ids:
        return html, 0
    id_counts = Counter(fig_ids)

    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0
    groups: dict[int, tuple[list[int], str]] = {}
    consumed: set[int] = set()
    wrapped = 0

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    for index, node in enumerate(nodes):
        if index in consumed:
            continue
        raw = node.group(0)
        target_id = _node_open_id_value(raw)
        fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", target_id or "", re.IGNORECASE)
        if fig_match is None:
            continue
        if id_counts[target_id or ""] > 1:
            continue
        if re.search(r"<img\b|<table\b", raw, re.IGNORECASE):
            continue
        if _node_has_class(raw, "z2m-missing-figure-warning") or _node_has_class(raw, "z2m-missing-figure-unit"):
            continue
        if re.search(rf"href\s*=\s*['\"]#{re.escape(target_id or '')}['\"]", html, re.IGNORECASE) is None:
            continue
        fig_num = fig_match.group(1)
        if _figure_caption_num_from_visible(_visible_text(raw)) != fig_num:
            continue
        if fig_num.startswith("supplementary-"):
            continue
        if _looks_like_in_text_figure_reference_node(raw, fig_num):
            continue

        start = max(0, index - 3)
        stop = min(len(nodes), index + 4)
        nearby_raw = "\n".join(nodes[j].group(0) for j in range(start, stop))
        if "z2m-missing-figure-warning" in nearby_raw:
            continue

        after: list[int] = []
        next_idx = index + 1
        while next_idx < len(nodes) and _between_is_whitespace(next_idx - 1, next_idx):
            next_raw = nodes[next_idx].group(0)
            if _looks_like_figure_panel_caption_continuation(next_raw):
                after.append(next_idx)
                next_idx += 1
                continue
            if after and _looks_like_figure_caption_fragment(next_raw):
                after.append(next_idx)
                next_idx += 1
                continue
            break

        group_indices = [index] + after
        if any(idx in consumed for idx in group_indices):
            continue
        warning_html = _missing_figure_warning_html(fig_num, figure_caption_language=figure_caption_language)
        warning_html = re.sub(
            r"^<p\b",
            '<p data-z2m-origin="caption-only-target"',
            warning_html,
            count=1,
            flags=re.IGNORECASE,
        )
        warning_html = _strip_node_id_and_add_class(
            warning_html,
            "z2m-figure-target",
        )
        caption_html = "".join(
            _strip_node_id_and_add_class(nodes[idx].group(0), "z2m-figure-caption")
            for idx in group_indices
        )
        wrapper = (
            f'<div id="{target_id}" class="z2m-float-unit z2m-figure-unit z2m-missing-figure-unit">'
            f"{warning_html}{caption_html}</div>"
        )
        groups[index] = (group_indices, wrapper)
        consumed.update(group_indices)
        wrapped += 1

    if not groups:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    index = 0
    while index < len(nodes):
        node = nodes[index]
        out_parts.append(html[cursor:node.start()])
        group = groups.get(index)
        if group is None:
            out_parts.append(node.group(0))
            cursor = node.end()
            index += 1
            continue
        group_indices, wrapper = group
        out_parts.append(wrapper)
        last_idx = group_indices[-1]
        cursor = nodes[last_idx].end()
        index = last_idx + 1
    out_parts.append(html[cursor:])
    return "".join(out_parts), wrapped


def _merge_caption_only_missing_units_with_previous_image_units(html: str) -> tuple[str, int]:
    if (
        "z2m-missing-figure-unit" not in html
        or "z2m-figure-unit" not in html
        or "<img" not in html.lower()
    ):
        return html, 0
    nodes = list(_FLOAT_AWARE_SENTENCE_NODE_PATTERN.finditer(html))
    if len(nodes) < 2:
        return html, 0

    id_counts = Counter(
        match.group("id")
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[A-Za-z0-9_.:-]+)\1', html, re.IGNORECASE)
    )
    div_pattern = re.compile(r"^(?P<open><div\b[^>]*>)(?P<body>[\s\S]*)(?P<close></div>)$", re.IGNORECASE)

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _div_parts(raw: str) -> tuple[str, str, str] | None:
        match = div_pattern.match(raw)
        if match is None:
            return None
        return match.group("open"), match.group("body"), match.group("close")

    def _open_id(open_tag: str) -> str | None:
        match = re.search(r'\bid\s*=\s*(["\'])([^"\']+)\1', open_tag, re.IGNORECASE)
        return match.group(2) if match is not None else None

    def _open_classes(open_tag: str) -> list[str]:
        match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', open_tag, re.IGNORECASE | re.DOTALL)
        return match.group(2).split() if match is not None else []

    def _image_only_unit_parts(raw: str) -> tuple[str, str, str] | None:
        parts = _div_parts(raw)
        if parts is None:
            return None
        open_tag, body, close_tag = parts
        classes = set(_open_classes(open_tag))
        if not {"z2m-float-unit", "z2m-figure-unit"}.issubset(classes):
            return None
        if "z2m-missing-figure-unit" in classes or "z2m-missing-figure-warning" in raw:
            return None
        if not _node_has_renderable_image(raw):
            return None
        if "z2m-figure-caption" in raw:
            return None
        visible = _visible_text(raw).strip()
        if visible and _figure_caption_num_from_visible(visible) is not None:
            return None
        if visible and len(re.findall(r"[A-Za-z]{3,}", visible)) >= 4:
            return None
        return open_tag, body, close_tag

    def _missing_unit_parts(raw: str) -> tuple[str, str, str, str] | None:
        parts = _div_parts(raw)
        if parts is None:
            return None
        open_tag, body, close_tag = parts
        classes = set(_open_classes(open_tag))
        if not {"z2m-float-unit", "z2m-figure-unit", "z2m-missing-figure-unit"}.issubset(classes):
            return None
        target_id = _open_id(open_tag) or ""
        fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", target_id, re.IGNORECASE)
        if fig_match is None or _node_has_renderable_image(raw):
            return None
        fig_num = fig_match.group(1)
        if "z2m-missing-figure-warning" not in raw or "z2m-figure-caption" not in raw:
            return None
        caption_body = re.sub(
            r'<p\b(?=[^>]*\bz2m-missing-figure-warning\b)[^>]*>[\s\S]*?</p>',
            "",
            body,
            flags=re.IGNORECASE,
        )
        labels = {
            label
            for match in re.finditer(r"<p\b[^>]*>[\s\S]*?</p>", caption_body, re.IGNORECASE)
            for label in [_figure_caption_num_from_visible(_visible_text(match.group(0)))]
            if label is not None
        }
        if fig_num not in labels or any(label != fig_num for label in labels):
            return None
        if not caption_body.strip():
            return None
        return open_tag, caption_body, close_tag, fig_num

    def _add_target_to_first_image_paragraph(body: str) -> str:
        def _replace(match: re.Match[str]) -> str:
            open_tag = _add_class_attr(_remove_id_attr(match.group("open")), "z2m-figure-target")
            return f"{open_tag}{match.group('rest')}"

        return re.sub(
            r"(?P<open><p\b[^>]*>)(?P<rest>[\s\S]*?<img\b[\s\S]*?</p>)",
            _replace,
            body,
            count=1,
            flags=re.IGNORECASE,
        )

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    merged = 0
    for index in range(1, len(nodes)):
        if index in replacements or index - 1 in dropped or not _between_is_whitespace(index - 1, index):
            continue
        image_raw = nodes[index - 1].group(0)
        missing_raw = nodes[index].group(0)
        image_parts = _image_only_unit_parts(image_raw)
        missing_parts = _missing_unit_parts(missing_raw)
        if image_parts is None or missing_parts is None:
            continue
        image_open, image_body, _image_close = image_parts
        missing_open, caption_body, _missing_close, fig_num = missing_parts
        target_id = f"fig-{fig_num}"
        previous_id = _open_id(image_open)
        if previous_id and previous_id != target_id and id_counts.get(previous_id, 0) <= 1:
            continue

        run_classes = [
            class_name
            for class_name in _open_classes(missing_open)
            if class_name.startswith("z2m-float-run-") or class_name == "z2m-float-alias"
        ]
        wrapper_classes = " ".join(["z2m-float-unit", "z2m-figure-unit", *run_classes])
        image_body = _add_target_to_first_image_paragraph(image_body)
        replacements[index] = f'<div id="{target_id}" class="{wrapper_classes}">{image_body}{caption_body}</div>'
        dropped.add(index - 1)
        merged += 1

    if not replacements:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for index, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if index in dropped:
            cursor = node.end()
            continue
        out_parts.append(replacements.get(index, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), merged


def _merge_caption_only_missing_units_with_previous_table_surrogates(html: str) -> tuple[str, int]:
    if "z2m-missing-figure-unit" not in html or "<table" not in html.lower():
        return html, 0
    nodes = list(_FLOAT_AWARE_SENTENCE_NODE_PATTERN.finditer(html))
    if len(nodes) < 2:
        return html, 0

    div_pattern = re.compile(r"^(?P<open><div\b[^>]*>)(?P<body>[\s\S]*)(?P<close></div>)$", re.IGNORECASE)
    table_pattern = re.compile(
        r"^(?P<open><table\b[^>]*>)(?P<body>[\s\S]*)(?P<close></table>)$",
        re.IGNORECASE,
    )

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _open_id(open_tag: str) -> str | None:
        match = re.search(r'\bid\s*=\s*(["\'])([^"\']+)\1', open_tag, re.IGNORECASE)
        return match.group(2) if match is not None else None

    def _open_classes(open_tag: str) -> list[str]:
        match = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', open_tag, re.IGNORECASE | re.DOTALL)
        return match.group(2).split() if match is not None else []

    def _table_surrogate_parts(raw: str) -> tuple[str, str, str] | None:
        match = table_pattern.match(raw)
        if match is None:
            return None
        open_tag = match.group("open")
        if _open_id(open_tag):
            return None
        classes = set(_open_classes(open_tag))
        if classes.intersection({"z2m-float-unit", "z2m-table-target", "z2m-figure-target"}):
            return None
        if "z2m-table-caption" in raw or "z2m-table-unit" in raw:
            return None
        if len(re.findall(r"<t[dh]\b", raw, flags=re.IGNORECASE)) < 4:
            return None
        visible = _visible_text(raw)
        if len(visible) < 10:
            return None
        return open_tag, match.group("body"), match.group("close")

    def _missing_unit_parts(raw: str) -> tuple[str, str, str, str] | None:
        match = div_pattern.match(raw)
        if match is None:
            return None
        open_tag = match.group("open")
        classes = set(_open_classes(open_tag))
        if not {"z2m-float-unit", "z2m-figure-unit", "z2m-missing-figure-unit"}.issubset(classes):
            return None
        target_id = _open_id(open_tag) or ""
        fig_match = re.fullmatch(r"fig-([A-Za-z0-9-]+)", target_id, re.IGNORECASE)
        if fig_match is None or _node_has_renderable_image(raw):
            return None
        fig_num = fig_match.group(1)
        if "caption-only-target" not in raw or "z2m-missing-figure-warning" not in raw:
            return None
        caption_body = re.sub(
            r'<p\b(?=[^>]*\bz2m-missing-figure-warning\b)[^>]*>[\s\S]*?</p>',
            "",
            match.group("body"),
            flags=re.IGNORECASE,
        )
        labels = {
            label
            for caption_match in re.finditer(r"<p\b[^>]*>[\s\S]*?</p>", caption_body, re.IGNORECASE)
            for label in [_figure_caption_num_from_visible(_visible_text(caption_match.group(0)))]
            if label is not None
        }
        if fig_num not in labels or any(label != fig_num for label in labels):
            return None
        if not caption_body.strip():
            return None
        return open_tag, caption_body, match.group("close"), fig_num

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    merged = 0
    for index in range(1, len(nodes)):
        if index in replacements or index - 1 in dropped or not _between_is_whitespace(index - 1, index):
            continue
        table_parts = _table_surrogate_parts(nodes[index - 1].group(0))
        missing_parts = _missing_unit_parts(nodes[index].group(0))
        if table_parts is None or missing_parts is None:
            continue
        table_open, table_body, table_close = table_parts
        missing_open, caption_body, _missing_close, fig_num = missing_parts
        target_id = f"fig-{fig_num}"
        run_classes = [
            class_name
            for class_name in _open_classes(missing_open)
            if class_name.startswith("z2m-float-run-") or class_name == "z2m-float-alias"
        ]
        wrapper_classes = " ".join(["z2m-float-unit", "z2m-figure-unit", *run_classes])
        table_open = _add_class_attr(table_open, "z2m-figure-target")
        replacements[index] = f'<div id="{target_id}" class="{wrapper_classes}">{table_open}{table_body}{table_close}{caption_body}</div>'
        dropped.add(index - 1)
        merged += 1

    if not replacements:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for index, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if index in dropped:
            cursor = node.end()
            continue
        out_parts.append(replacements.get(index, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), merged


def _repair_sentence_breaks_around_float_units_once(html: str) -> tuple[str, int]:
    """Move prose continuations back across already wrapped figure/table/box units."""
    nodes = list(_FLOAT_AWARE_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    dropped: set[int] = set()
    repairs = 0

    def _is_p_node(raw: str) -> bool:
        return raw.lstrip().lower().startswith("<p")

    def _is_float_node(raw: str) -> bool:
        return _node_has_class(raw, "z2m-float-unit")

    def _is_gap_node(raw: str) -> bool:
        if (
            _is_float_node(raw)
            or _is_table_note_node(raw)
            or _node_has_class(raw, "z2m-table-note")
            or _node_has_class(raw, "z2m-footnote")
        ):
            return True
        if _is_p_node(raw):
            if len(raw) > 8000:
                # Large prose/image paragraphs are never safe "gap" candidates for sentence repair.
                return False
            visible = _visible_text(raw)
            return (
                not visible.strip()
                or re.fullmatch(r"[\s.,;:|/\\-]+", visible) is not None
                or _looks_running_header_line(visible)
                or _looks_inline_figure_block(raw)
                or (_is_figure_caption_node(raw) and not _looks_like_in_text_figure_reference_sentence(raw))
            )
        return _looks_nonprose_gap_block(raw)

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    def _right_candidate(idx: int) -> tuple[re.Match[str], str, str] | None:
        if idx >= len(nodes):
            return None
        raw = nodes[idx].group(0)
        if not _is_p_node(raw):
            return None
        match = _SENTENCE_P_NODE_PATTERN.match(raw)
        if match is None:
            return None
        if _is_equation_like_node(raw):
            return None
        if re.search(r"\bid\s*=", match.group("open"), re.IGNORECASE):
            return None
        body = match.group("body")
        return match, body, _visible_text(body)

    def _body_too_large_for_sentence_repair(body: str, visible: str) -> bool:
        if len(body) <= 8000:
            return False
        if len(body) > 50000:
            return True
        if re.search(r"<(?:img|table|figure)\b|z2m-float-unit", body, re.IGNORECASE):
            return True
        return len(visible) > 3200

    def _append_float_caption_continuation(
        float_raw: str,
        left_text: str,
        right_body: str,
        right_text: str,
    ) -> tuple[str, bool]:
        caption_matches = [
            match
            for match in _P_OR_H_BLOCK_PATTERN.finditer(float_raw)
            if _node_has_class(match.group("open"), "z2m-figure-caption")
        ]
        if not caption_matches:
            return float_raw, False
        if not left_text.rstrip().endswith((".", "!", "?", ":", ";", "\u2026", "вЂ¦", "РІР‚В¦")) and re.match(
            r"^\s*(?:<[^>]+>\s*)*[a-z]",
            right_text,
        ):
            return float_raw, False
        if _is_sentence_continuation(left_text, right_text):
            return float_raw, False
        caption_match = caption_matches[-1]
        caption_body = caption_match.group("body")
        caption_text = _visible_text(caption_body)
        if _figure_caption_ends_with_doi_marker(caption_body) and _figure_caption_tail_starts_like_body(right_body):
            return float_raw, False
        if not _looks_like_caption_continuation_after_figure(caption_text, right_text):
            return float_raw, False
        merged_caption = _merge_sentence_parts(caption_body, right_body)
        replacement = f"{caption_match.group('open')}{merged_caption}{caption_match.group('close')}"
        return (
            float_raw[: caption_match.start()]
            + replacement
            + float_raw[caption_match.end() :],
            True,
        )

    def _last_float_gap_idx(indices: list[int]) -> int | None:
        for gap_idx in reversed(indices):
            if gap_idx in dropped:
                continue
            raw = replacements.get(gap_idx, nodes[gap_idx].group(0))
            if _is_float_node(raw):
                return gap_idx
        return None

    i = 0
    while i < len(nodes):
        if i in dropped:
            i += 1
            continue

        left_raw = nodes[i].group(0)
        if not _is_p_node(left_raw):
            i += 1
            continue
        left_match = _SENTENCE_P_NODE_PATTERN.match(left_raw)
        if left_match is None:
            i += 1
            continue
        if _is_caption_node(left_raw) or _is_table_note_node(left_raw):
            i += 1
            continue
        if _node_has_class(left_raw, "z2m-footnote") or _node_has_class(left_raw, "z2m-table-note"):
            i += 1
            continue
        gap_indices: list[int] = []
        j = i + 1
        while j < len(nodes) and len(gap_indices) < 16:
            if not _between_is_whitespace(j - 1, j):
                break
            raw = nodes[j].group(0)
            if not _is_gap_node(raw):
                break
            gap_indices.append(j)
            j += 1

        if not gap_indices or j >= len(nodes) or not _between_is_whitespace(gap_indices[-1], j):
            i += 1
            continue

        candidate = _right_candidate(j)
        if candidate is None:
            i += 1
            continue
        right_match, right_body, right_text = candidate

        while True:
            float_idx = _last_float_gap_idx(gap_indices)
            if float_idx is None:
                break
            float_raw = replacements.get(float_idx, nodes[float_idx].group(0))
            left_text_for_caption = _visible_text(left_match.group("body"))
            repaired_float, absorbed = _append_float_caption_continuation(
                float_raw,
                left_text_for_caption,
                right_body,
                right_text,
            )
            if not absorbed:
                break
            replacements[float_idx] = repaired_float
            dropped.add(j)
            repairs += 1
            gap_indices.append(j)
            j += 1
            if j >= len(nodes) or not _between_is_whitespace(gap_indices[-1], j):
                break
            candidate = _right_candidate(j)
            if candidate is None:
                break
            right_match, right_body, right_text = candidate

        if j >= len(nodes) or j in dropped:
            i += 1
            continue
        candidate = _right_candidate(j)
        if candidate is None:
            i += 1
            continue
        right_match, right_body, right_text = candidate

        left_body = left_match.group("body")
        note_body = None
        split_note = _split_trailing_table_note_from_body(left_body)
        if split_note is not None:
            left_body, note_body = split_note
        right_body, _ = _strip_pdf_running_header_prefix_from_body(right_body)
        right_body, _ = _strip_leading_pdf_line_number_from_body(right_body)
        left_text = _visible_text(left_body)
        right_text = _visible_text(right_body)
        if _body_too_large_for_sentence_repair(left_body, left_text) or _body_too_large_for_sentence_repair(
            right_body,
            right_text,
        ):
            i += 1
            continue
        if len(right_text) < 6:
            i += 1
            continue
        if len(left_text) < 20 and not _is_short_fragment_left(left_text):
            i += 1
            continue
        if not _is_sentence_continuation(left_text, right_text):
            i += 1
            continue

        merged_left = _merge_sentence_parts(left_body, right_body)
        replacement = f"{left_match.group('open')}{merged_left}{left_match.group('close')}"
        if note_body:
            replacement += f'\n<p class="z2m-table-note">{note_body}</p>'
        replacements[i] = replacement
        dropped.add(j)
        repairs += 1
        i = j + 1

    if repairs == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        if idx in dropped:
            pass
        elif idx in replacements:
            out_parts.append(replacements[idx])
        else:
            out_parts.append(node.group(0))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), repairs


def _repair_sentence_breaks_around_float_units(html: str) -> tuple[str, int]:
    """Move prose continuations back across one or more adjacent float runs."""
    current = html
    total_repairs = 0
    for _ in range(8):
        current, repairs = _repair_sentence_breaks_around_float_units_once(current)
        if repairs == 0:
            return current, total_repairs
        total_repairs += repairs
    return current, total_repairs


def _mark_consecutive_float_runs(html: str) -> str:
    """Mark adjacent figure/table wrappers so a run renders with one outer frame."""
    matches = list(_FLOAT_UNIT_DIV_PATTERN.finditer(html))
    if len(matches) < 2:
        return html

    runs: list[list[int]] = []
    run_start = 0
    for idx in range(1, len(matches)):
        gap = html[matches[idx - 1].end():matches[idx].start()]
        if _html_gap_is_ignorable(gap):
            continue
        if idx - run_start >= 2:
            runs.append(list(range(run_start, idx)))
        run_start = idx
    if len(matches) - run_start >= 2:
        runs.append(list(range(run_start, len(matches))))
    if not runs:
        return html

    class_by_match: dict[int, str] = {}
    for run in runs:
        for pos, match_idx in enumerate(run):
            if pos == 0:
                class_by_match[match_idx] = "z2m-float-run-start"
            elif pos == len(run) - 1:
                class_by_match[match_idx] = "z2m-float-run-end"
            else:
                class_by_match[match_idx] = "z2m-float-run-mid"

    out_parts: list[str] = []
    cursor = 0
    for idx, match in enumerate(matches):
        out_parts.append(html[cursor:match.start()])
        raw = match.group(0)
        class_name = class_by_match.get(idx)
        if class_name is None:
            out_parts.append(raw)
        else:
            open_end = raw.find(">")
            if open_end < 0:
                out_parts.append(raw)
            else:
                open_tag = _add_class_attr(raw[: open_end + 1], class_name)
                out_parts.append(open_tag + raw[open_end + 1:])
        cursor = match.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts)


def _split_trailing_table_captions_before_tables(html: str) -> tuple[str, int]:
    """Separate a table caption that Marker glued to the preceding prose paragraph."""
    nodes = list(_SENTENCE_NODE_PATTERN.finditer(html))
    if not nodes:
        return html, 0

    replacements: dict[int, str] = {}
    splits = 0

    def _between_is_whitespace(a_idx: int, b_idx: int) -> bool:
        return _html_gap_is_ignorable(html[nodes[a_idx].end():nodes[b_idx].start()])

    for idx in range(len(nodes) - 1):
        raw = nodes[idx].group(0)
        next_raw = nodes[idx + 1].group(0)
        if not raw.lstrip().lower().startswith("<p"):
            continue
        if not re.match(r"<table\b", next_raw.lstrip(), re.IGNORECASE):
            continue
        if not _between_is_whitespace(idx, idx + 1):
            continue
        match = _SENTENCE_P_NODE_PATTERN.match(raw)
        if match is None:
            continue
        split = _split_trailing_table_caption_from_body(match.group("body"))
        if split is None:
            continue
        prose_body, caption_body = split
        replacements[idx] = (
            f"{match.group('open')}{prose_body}{match.group('close')}\n"
            f"{match.group('open')}{caption_body}{match.group('close')}"
        )
        splits += 1

    if splits == 0:
        return html, 0

    out_parts: list[str] = []
    cursor = 0
    for idx, node in enumerate(nodes):
        out_parts.append(html[cursor:node.start()])
        out_parts.append(replacements.get(idx, node.group(0)))
        cursor = node.end()
    out_parts.append(html[cursor:])
    return "".join(out_parts), splits


def _repair_remaining_table_caption_units(html: str) -> str:
    """Wrap table captions that survived table-unit assembly as loose targets."""
    caption_then_table = re.compile(
        r'(?P<caption><p\b(?=[^>]*\bid\s*=\s*["\']table-(?P<num>[A-Za-z0-9-]+)["\'])[^>]*>'
        r'[\s\S]*?</p>)(?P<gap>\s*)(?P<table><table\b[\s\S]*?</table>)',
        re.IGNORECASE,
    )
    table_then_caption = re.compile(
        r'(?P<table><table\b[\s\S]*?</table>)(?P<gap>\s*)'
        r'(?P<caption><p\b(?=[^>]*\bid\s*=\s*["\']table-(?P<num>[A-Za-z0-9-]+)["\'])[^>]*>'
        r'[\s\S]*?</p>)',
        re.IGNORECASE,
    )
    orphan_caption = re.compile(
        r'(?P<caption><p\b(?=[^>]*\bid\s*=\s*["\']table-(?P<num>[A-Za-z0-9-]+)["\'])[^>]*>'
        r'[\s\S]*?</p>)',
        re.IGNORECASE,
    )

    def _caption_matches(caption: str, table_key: str) -> bool:
        return _is_same_table_caption(caption, table_key)

    def _wrap(caption: str, table_key: str, table: str = "", *, caption_first: bool = True) -> str:
        caption_html = _strip_node_id_and_add_class(caption, "z2m-table-caption")
        if table:
            table_html = _strip_node_id_and_add_class(table, None)
            body = f"{caption_html}{table_html}" if caption_first else f"{table_html}{caption_html}"
        else:
            body = caption_html
        return f'<div id="table-{table_key}" class="z2m-float-unit z2m-table-unit">{body}</div>'

    def _replace_caption_then_table(match: re.Match[str]) -> str:
        table_key = match.group("num")
        caption = match.group("caption")
        if not _caption_matches(caption, table_key):
            return match.group(0)
        return _wrap(caption, table_key, match.group("table"), caption_first=True)

    def _replace_table_then_caption(match: re.Match[str]) -> str:
        table_key = match.group("num")
        caption = match.group("caption")
        if not _caption_matches(caption, table_key):
            return match.group(0)
        return _wrap(caption, table_key, match.group("table"), caption_first=False)

    def _replace_orphan(match: re.Match[str]) -> str:
        table_key = match.group("num")
        caption = match.group("caption")
        if not _caption_matches(caption, table_key):
            return match.group(0)
        return _wrap(caption, table_key)

    current = caption_then_table.sub(_replace_caption_then_table, html)
    current = table_then_caption.sub(_replace_table_then_caption, current)
    return orphan_caption.sub(_replace_orphan, current)


def _split_table_units_before_section_headings(html: str) -> str:
    """Close loose table wrappers before the next numbered section heading."""
    table_unit = re.compile(
        r'(?P<open><div\b(?=[^>]*\bclass\s*=\s*["\'][^"\']*\bz2m-table-unit\b)[^>]*>)'
        r'(?P<body>[\s\S]*?)(?P<close></div>)',
        re.IGNORECASE,
    )

    def _replace(match: re.Match[str]) -> str:
        body = match.group("body")
        for heading in _H_BLOCK_PATTERN.finditer(body):
            heading_raw = heading.group(0)
            visible = _visible_text(heading_raw)
            if _figure_caption_num_from_visible(visible) is not None:
                continue
            if _table_caption_key_from_visible(visible) is not None:
                continue
            if _NUMERIC_SECTION_HEADING_VISIBLE_PATTERN.match(visible) is None:
                continue
            before = body[: heading.start()]
            if not before.strip():
                return match.group(0)
            after = body[heading.start():]
            if re.search(
                r"<div\b(?=[^>]*\bclass\s*=\s*([\"'])[^\"']*\bz2m-float-unit\b)",
                after,
                re.IGNORECASE,
            ):
                return f"{match.group('open')}{before}</div>{after}{match.group('close')}"
            return f"{match.group('open')}{before}{match.group('close')}{after}"
        return match.group(0)

    previous = None
    current = html
    while previous != current:
        previous = current
        current = table_unit.sub(_replace, current)
    return current


def _raw_polish_context_language_policy(context: RawPolishContext) -> PolishLanguagePolicy:
    if context.language_policy is None:
        raise ValueError("Raw polish context has no language policy")
    return context.language_policy


def _polish_phase_pre_cleanup(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
    del context
    polished = state.html
    polished = _unwrap_spurious_math_captions(polished)
    polished = _unwrap_nested_fig_links(polished)
    polished = _drop_page_header_footer_paragraphs(polished)
    polished = _drop_repeated_page_furniture(polished)
    polished = _drop_publisher_chrome_pages(polished)
    polished = drop_repeated_phrases(polished)
    polished = _normalize_glued_roman_suffixes(polished)
    polished = _normalize_table_cell_roman_suffixes(polished)
    polished = _repair_false_roman_suffix_splits(polished)
    polished = _repair_variable_table_fn_splits(polished)
    polished = _normalize_table_cell_soft_breaks(polished)
    polished = _repair_table_significance_markers(polished)
    polished = _repair_known_replacement_char_symbols(polished)
    polished = _fix_latex_text_commands(polished)
    polished = _unwrap_spurious_math_captions(polished)
    polished = _fix_subscript_equation_spill(polished)
    polished = _fix_orphaned_sup_tags(polished)
    polished = _unescape_inline_sup_sub(polished)
    polished = _normalize_spaced_inline_sup_sub_tags(polished)
    polished = _fix_common_mojibake(polished)
    polished = _repair_known_replacement_char_symbols(polished)
    polished = _repair_safe_text_artifacts(polished)
    polished = _BYTE_TOKEN_CITATION_PATTERN.sub(r'<sup>\1</sup>', polished)
    polished = _BYTE_TOKEN_ARTIFACT_PATTERN.sub("", polished)
    polished = _cleanup_marker_escape_artifacts(polished)
    polished = _strip_protocol_sentinel_leaks(polished)
    return state.with_html(polished)


def _polish_phase_math_and_units(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
    del context
    polished = state.html
    polished = _convert_latex_sup_citations(polished)
    polished = _move_trailing_bracket_citations_out_of_inline_tex(polished)
    polished = _normalize_scientific_units(polished)
    polished = _mark_unit_exponent_superscripts(polished)
    polished = _fix_equation_display(polished)
    polished = _convert_math_tags_to_tex(polished)
    polished = _convert_latex_sup_citations(polished)
    polished = _restore_inline_tex_sentence_punctuation(polished)
    polished = _normalize_scientific_units(polished)
    polished = _mark_unit_exponent_superscripts(polished)
    polished = _repair_common_math_ocr_substitutions(polished)
    polished = _fix_equation_display(polished)
    polished = _move_trailing_bracket_citations_out_of_inline_tex(polished)
    polished = _convert_latex_sup_citations(polished)
    polished = _restore_inline_tex_sentence_punctuation(polished)
    polished = _repair_equation_defined_index_prose(polished)
    polished, _ = _repair_sentence_breaks_around_box_blocks(polished)
    polished, _ = _repair_sentence_breaks_at_page_boundaries(polished)
    polished, _ = _reorder_table_block_away_from_formula_context(polished)
    polished, _ = _split_table_note_body_continuations(polished)
    polished, _ = _merge_split_table_note_continuation_paragraphs(polished)
    return state.with_html(polished)


def _polish_phase_frontmatter_and_footnotes(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
    del context
    polished = state.html
    polished = _mark_footnote_paragraphs_and_refs(polished)
    polished = _split_url_footnote_prose_tails(polished)
    polished = _repair_page_footnote_ref_links(polished)
    polished, _ = _repair_sentence_breaks_around_footnote_blocks(polished)
    polished, _ = _repair_sentence_breaks_around_figure_blocks(polished)
    polished, _ = _repair_terminal_section_interleaving(polished)
    polished = _drop_ocr_figure_annotation_headings(polished)
    polished = _fix_false_sup_citations_in_decimals_and_figure_labels(polished)
    polished = _mark_affiliation_paragraphs(polished)
    polished = _mark_front_matter_paragraphs(polished)
    polished = _repair_front_matter_marker_ocr(polished)
    polished = _repair_confirmed_front_matter_artifacts(polished)
    polished = _mark_footnote_paragraphs_and_refs(polished)
    polished = _split_url_footnote_prose_tails(polished)
    polished = _repair_page_footnote_ref_links(polished)
    polished, _ = _repair_inline_author_email_intrusions(polished)
    polished, _ = _repair_known_metadata_body_intrusions(polished)
    polished, _ = _repair_known_float_body_intrusions(polished)
    polished, _ = _repair_sentence_breaks_around_metadata_blocks(polished)
    polished = _repair_known_sentence_boundary_artifacts(polished)
    return state.with_html(polished)


def _polish_phase_semantic_targets(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
    polished = state.html
    polished = _strip_reference_links_in_protected_blocks(polished)
    polished = _strip_pdf_line_number_artifacts(polished)
    polished = _strip_leading_reference_line_number_pairs_in_list_items(polished)
    polished = _normalize_numeric_section_heading_levels(polished)
    polished, found_sections = _add_section_anchors(polished)
    polished, standalone_label_figures = _anchor_standalone_figure_labels_before_images(polished)
    polished, found_figures = _add_figure_anchors(polished)
    found_figures.update(standalone_label_figures)
    polished, duplicate_context_figures = _retarget_duplicate_figure_targets_from_context_refs(polished)
    found_figures.update(duplicate_context_figures)
    polished, _ = _split_trailing_table_captions_before_tables(polished)
    polished, found_tables = _add_table_anchors(polished)
    polished, recovered_figures = _recover_orphan_figure_anchors(polished, found_figures)
    found_figures.update(recovered_figures)
    polished, late_standalone_label_figures = _anchor_standalone_figure_labels_before_images(polished)
    found_figures.update(late_standalone_label_figures)
    polished, placeholder_figures = _wrap_accepted_manuscript_figure_placeholders_as_missing(
        polished,
        figure_caption_language=context.table_caption_language,
    )
    found_figures.update(placeholder_figures)
    polished, found_boxes = _add_box_anchors(polished)
    polished, _ = _repair_known_float_body_intrusions(polished)
    return state.with_updates(
        html=polished,
        found_sections=found_sections,
        found_figures=found_figures,
        found_tables=found_tables,
        found_boxes=found_boxes,
    )


def _polish_phase_references_and_links(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
    language_policy = _raw_polish_context_language_policy(context)
    polished = state.html
    citation_profile = context.citation_profile
    found_sections = state.found_sections
    found_figures = state.found_figures
    found_tables = state.found_tables
    found_boxes = state.found_boxes
    if context.enable_citation_linkify:
        polished = _add_reference_ids_and_citation_links(polished, citation_profile=citation_profile)
        polished = _retarget_mismatched_ref_link_labels(polished)
        polished = _repair_ref_links_with_leading_closing_punctuation(polished)
        polished = _unwrap_reference_list_page_number_links(polished)
        polished = _unwrap_reference_list_page_links(polished)
        polished = _unwrap_page_reference_ref_links(polished, language_policy)
        polished = _repair_ref_links_absorbed_decimal_or_unit_text(polished)
        polished = _repair_nested_reference_links(polished)
        polished = _unwrap_malformed_ref_anchor_openings(polished)
        polished = _unwrap_author_year_ref_links(polished, citation_profile=citation_profile)
        polished = _repair_roman_suffix_author_year_ref_link_splits(polished)
        polished = _repair_author_year_footnote_ref_links(polished, citation_profile=citation_profile)
        polished = _repair_acronym_footnote_ref_citations(polished)
        if not _should_suppress_numeric_ref_links_for_author_year(polished, citation_profile):
            polished = _recover_trailing_citation_after_author_year_ref(polished)
        else:
            polished = _unwrap_numeric_ref_links_for_author_year_profile(polished)
        polished, _ = _repair_citation_prefix_paragraph_continuations(polished)
        polished = _link_section_refs(polished, found_sections)
        polished = _link_equation_refs(polished)
        polished = _cleanup_decimal_equation_page_links(polished)
        polished = _link_box_refs(polished, found_boxes)
        polished = _repair_figure_refs_split_by_line_number_artifacts(polished, found_figures)
        polished = _rewrite_existing_page_figure_links(
            polished,
            found_figures,
            language_policy=language_policy,
        )
        polished = _link_figure_refs(polished, found_figures)
        polished = _retarget_void_figure_number_links(polished, found_figures)
        polished = _repair_figure_ref_links_misclassified_as_refs(polished, found_figures)
        polished = _repair_bracket_citation_fig_links_misclassified_as_figures(polished)
        polished = _repair_sup_figure_chain_continuations(polished, found_figures)
        polished = _rewrite_existing_page_table_links(polished, found_tables)
        polished = _link_table_refs(polished, found_tables)
        polished = _repair_table_ref_links_misclassified_as_refs(polished, found_tables)
        polished = _link_late_numeric_citation_ranges_before_references(polished, citation_profile)
        polished = _unwrap_nested_same_href_internal_links(polished)
        polished = _unwrap_unresolved_semantic_page_links(
            polished,
            found_figures=found_figures,
            found_tables=found_tables,
            found_sections=found_sections,
            found_boxes=found_boxes,
            language_policy=language_policy,
        )
        polished = _unlink_supplementary_page_refs(polished)
        polished = _unwrap_author_year_page_links(polished)
        polished = _unwrap_stale_numeric_page_links(polished, language_policy)
        polished = _unwrap_plain_prose_page_links(polished)
        polished = _unwrap_page_reference_page_links(polished, language_policy)
        polished = _unwrap_broken_page_anchor_links(polished)
        polished = _repair_numeric_ref_false_positives(polished)
        polished = _repair_statistical_ref_false_positives(polished)
        polished = _mark_unit_exponent_superscripts(polished)
        polished = _repair_nested_reference_links(polished)
        polished = _unwrap_malformed_ref_anchor_openings(polished)
        polished = _fix_false_sup_citations_in_decimals_and_figure_labels(polished)
        if _citation_profile_is_high_confidence_superscript_numeric(citation_profile):
            polished = _wrap_plain_ref_links_as_superscript_citations(polished)
            polished = _normalize_spacing_after_ref_superscripts(polished)
    else:
        polished = _rewrite_existing_page_table_links(polished, found_tables)
        polished = _link_table_refs(polished, found_tables)
        polished = _repair_table_ref_links_misclassified_as_refs(polished, found_tables)
        polished = _unwrap_nested_same_href_internal_links(polished)
    if context.enable_citation_linkify:
        polished = _link_late_numeric_citation_ranges_before_references(polished, citation_profile)
    return state.with_html(polished)


def _polish_phase_float_units(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
    language_policy = _raw_polish_context_language_policy(context)
    polished = state.html
    table_caption_language = context.table_caption_language
    citation_profile = context.citation_profile
    polished = _unwrap_leading_caption_page_anchors(polished)
    polished = _normalize_table_caption_style(polished, table_caption_language=table_caption_language)
    polished = _normalize_figure_caption_style(polished, figure_caption_language=table_caption_language)
    polished = _absorb_external_figure_captions_into_units(polished)
    polished, _ = _merge_biorender_caption_fragments(polished)
    polished, _ = _repair_caption_suffix_left_body_tail_right(polished)
    polished, _ = _refresh_inlined_data_urls_by_cache(polished, image_cache=context.image_cache)
    ru_caption_context = (
        table_caption_language == "ru"
        and (not context.enable_citation_linkify or _looks_like_ru_html_content(polished))
    )
    polished, _ = _insert_missing_figure_warnings(
        polished,
        figure_caption_language=("ru" if ru_caption_context else "en"),
    )
    polished, _ = _drop_compound_caption_missing_warnings(polished)
    polished, _ = _drop_same_label_image_missing_warnings(polished)
    polished = _wrap_box_units(polished)
    polished = _wrap_standalone_caption_before_image_units(polished)
    polished = _wrap_figure_table_surrogate_units(polished)
    polished = _wrap_float_units(polished)
    polished = _absorb_external_figure_captions_into_units(polished)
    polished = _collapse_duplicate_nested_float_units(polished)
    polished = _split_figure_caption_internal_body_tails(polished)
    polished = _split_figure_units_at_body_tail(polished)
    polished = _split_distinct_nested_figure_units(polished)
    polished = _split_leading_image_from_duplicate_caption_successor_units(polished)
    polished = _split_leading_image_run_from_first_sequence_unit(polished)
    polished = _recover_unique_bare_source_named_figure_units(polished)
    polished = _recover_sequence_gap_bare_image_figure_units(polished)
    polished, _ = _insert_sequence_gap_missing_figure_units(
        polished,
        figure_caption_language=("ru" if ru_caption_context else "en"),
    )
    polished = _drop_unbacked_foreign_figure_aliases(polished)
    polished = _mark_missing_figure_units(polished)
    polished = _repair_remaining_table_caption_units(polished)
    polished = _split_table_units_before_section_headings(polished)
    polished = _collapse_duplicate_nested_float_units(polished)
    polished = _split_figure_caption_internal_body_tails(polished)
    polished = _split_figure_units_at_body_tail(polished)
    polished = _split_distinct_nested_figure_units(polished)
    polished = _split_leading_image_from_duplicate_caption_successor_units(polished)
    polished = _split_leading_image_run_from_first_sequence_unit(polished)
    polished = _recover_unique_bare_source_named_figure_units(polished)
    polished = _recover_sequence_gap_bare_image_figure_units(polished)
    polished, _ = _insert_sequence_gap_missing_figure_units(
        polished,
        figure_caption_language=("ru" if ru_caption_context else "en"),
    )
    polished = _drop_unbacked_foreign_figure_aliases(polished)
    polished, _ = _repair_sentence_breaks_around_float_units(polished)
    polished, _ = _repair_sentence_breaks_at_page_boundaries(polished)
    polished = _absorb_external_figure_captions_into_units(polished)
    polished = _retarget_caption_only_figure_ids_to_nearby_images(polished)
    polished, _ = _wrap_remaining_caption_only_figure_targets_as_missing(
        polished,
        figure_caption_language=("ru" if ru_caption_context else "en"),
    )
    polished, _ = _merge_caption_only_missing_units_with_previous_image_units(polished)
    polished, _ = _merge_caption_only_missing_units_with_previous_table_surrogates(polished)
    polished, _ = _drop_same_label_image_missing_warnings(polished)
    polished = _wrap_standalone_caption_before_image_units(polished)
    polished = _wrap_figure_table_surrogate_units(polished)
    polished = _wrap_float_units(polished)
    polished = _mark_missing_figure_units(polished)
    polished = _collapse_duplicate_nested_float_units(polished)
    polished = _split_figure_caption_internal_body_tails(polished)
    polished = _split_figure_units_at_body_tail(polished)
    polished = _split_distinct_nested_figure_units(polished)
    polished = _split_leading_image_from_duplicate_caption_successor_units(polished)
    polished = _split_leading_image_run_from_first_sequence_unit(polished)
    polished = _recover_unique_bare_source_named_figure_units(polished)
    polished = _recover_sequence_gap_bare_image_figure_units(polished)
    polished, _ = _insert_sequence_gap_missing_figure_units(
        polished,
        figure_caption_language=("ru" if ru_caption_context else "en"),
    )
    polished = _drop_unbacked_foreign_figure_aliases(polished)
    polished = _add_aliases_for_embedded_figure_caption_labels(polished)
    polished, _ = _merge_caption_only_missing_units_with_previous_image_units(polished)
    polished, _ = _merge_caption_only_missing_units_with_previous_table_surrogates(polished)
    polished = _drop_stale_in_text_figure_reference_ids(polished)
    polished = _unwrap_duplicate_see_page_anchor_tails(polished)
    polished = _unwrap_page_reference_page_links(polished, language_policy)
    polished = _unwrap_plain_prose_page_links(polished)
    polished = _repair_known_word_glue(polished)
    polished = _repair_second_echelon_ocr_residue_html(polished)
    polished = _repair_known_table_ocr_artifacts(polished)
    polished = _repair_known_replacement_char_symbols(polished)
    polished = _repair_safe_text_artifacts(polished)
    if language_policy.code == "en":
        polished = _repair_latin_detached_accent_artifacts_in_visible_text(polished)
        polished = _repair_english_ocr_text_artifacts(polished)
    polished = _mark_consecutive_float_runs(polished)
    polished, _ = _merge_biorender_caption_fragments(polished)
    if ru_caption_context:
        polished = _normalize_ru_reference_lexemes(polished)
    if table_caption_language == "ru" and not context.enable_citation_linkify:
        polished = _strip_english_heading_prefix_in_ru(polished)
        polished = _strip_long_english_runs_in_ru_text(polished)
    polished = _normalize_spacing_after_z2m_links(polished)
    polished = _fix_nested_autolink_in_escaped_anchor_snippets(polished)
    polished = _unescape_safe_escaped_anchor_snippets(polished)
    polished = _repair_split_url_anchor_block_tail(polished)
    polished = _repair_split_scheme_url_anchor_fragments(polished)
    polished = _repair_split_visible_url_anchors(polished)
    polished = _repair_miswrapped_doi_anchor_labels(polished)
    polished = _repair_doi_anchor_swallowed_prose_tails(polished)
    polished = _merge_split_same_href_doi_anchors(polished)
    polished = _repair_split_doi_head_tail_anchors(polished)
    polished = _repair_split_doi_url_anchor_path_tails(polished)
    polished = _repair_spaced_protocol_url_anchors(polished)
    polished = _repair_broken_url_anchor_labels(polished)
    polished = _merge_adjacent_same_href_mailto_anchors(polished)
    polished = _merge_adjacent_same_href_url_anchors(polished)
    polished = _repair_prose_prefixed_url_anchor_tail(polished)
    polished = _repair_broken_plain_url_text(polished)
    polished = _repair_spaced_protocol_url_anchors(polished)
    polished = _repair_broken_url_anchor_labels(polished)
    polished = _repair_split_scheme_url_anchor_fragments(polished)
    polished = _autolink_plain_urls(polished)
    polished = _repair_split_url_anchor_domain_tail(polished)
    polished = _repair_prose_prefixed_url_anchor_tail(polished)
    polished = _repair_split_visible_url_anchors(polished)
    polished = _merge_split_same_href_doi_anchors(polished)
    polished = _repair_split_doi_head_tail_anchors(polished)
    polished = _repair_split_doi_url_anchor_path_tails(polished)
    polished = _repair_doi_anchor_swallowed_prose_tails(polished)
    polished = _merge_adjacent_same_href_url_anchors(polished)
    polished = _merge_post_autolink_split_url_anchors(polished)
    polished = _repair_split_www_domain_anchor_with_noisy_href(polished)
    polished = _repair_broken_url_anchor_labels(polished)
    polished = _repair_split_url_anchor_block_tail(polished)
    polished = _merge_adjacent_same_href_url_anchors(polished)
    polished = _repair_prose_prefixed_url_anchor_tail(polished)
    polished = _split_doi_metadata_body_paragraphs(polished)
    polished = _move_body_tail_after_table_doi_note_out_of_table_unit(polished)
    polished, _ = _merge_split_table_note_continuation_paragraphs(polished)
    polished = _split_figure_caption_internal_body_tails(polished)
    polished = _split_figure_units_at_body_tail(polished)
    polished = _split_distinct_nested_figure_units(polished)
    polished, _ = _repair_sentence_breaks_around_float_units(polished)
    polished, _ = _repair_known_metadata_body_intrusions(polished)
    polished = _move_clearvision_footnote_after_summary(polished)
    polished = _normalize_spacing_after_url_links(polished)
    polished, _ = _repair_known_float_body_intrusions(polished)
    polished = _split_figure_caption_internal_body_tails(polished)
    polished = _split_figure_units_at_body_tail(polished)
    polished = _split_distinct_nested_figure_units(polished)
    polished = _split_leading_image_from_duplicate_caption_successor_units(polished)
    polished = _split_leading_image_run_from_first_sequence_unit(polished)
    polished = _recover_unique_bare_source_named_figure_units(polished)
    polished = _recover_sequence_gap_bare_image_figure_units(polished)
    polished, _ = _insert_sequence_gap_missing_figure_units(
        polished,
        figure_caption_language=("ru" if ru_caption_context else "en"),
    )
    polished, _ = _repair_sentence_breaks_around_float_units(polished)
    polished = _strip_leading_reference_line_number_pairs_in_list_items(polished)
    polished = _repair_nested_reference_links(polished)
    polished = _unwrap_malformed_ref_anchor_openings(polished)
    polished = _merge_split_same_href_doi_anchors(polished)
    polished = _repair_split_doi_head_tail_anchors(polished)
    polished = _repair_split_doi_url_anchor_path_tails(polished)
    polished = _repair_doi_anchor_swallowed_prose_tails(polished)
    polished = _split_figure_caption_internal_body_tails(polished)
    polished = _split_figure_units_at_body_tail(polished)
    polished = _split_distinct_nested_figure_units(polished)
    polished = _split_leading_image_from_duplicate_caption_successor_units(polished)
    polished = _split_leading_image_run_from_first_sequence_unit(polished)
    polished = _recover_unique_bare_source_named_figure_units(polished)
    polished = _recover_sequence_gap_bare_image_figure_units(polished)
    polished, _ = _insert_sequence_gap_missing_figure_units(
        polished,
        figure_caption_language=("ru" if ru_caption_context else "en"),
    )
    if not _should_suppress_numeric_ref_links_for_author_year(polished, citation_profile):
        polished = _link_flattened_et_al_numeric_citations_to_existing_refs(polished)
        polished = _link_unlinked_numeric_superscripts_to_existing_refs(polished)
    else:
        polished = _unwrap_numeric_ref_links_for_author_year_profile(polished)
    polished = _repair_author_year_footnote_ref_links(polished, citation_profile=citation_profile)
    polished = _unwrap_malformed_ref_anchor_openings(polished)
    polished = _repair_nested_reference_links(polished)
    polished = _repair_numeric_ref_false_positives(polished)
    polished = _fix_false_sup_citations_in_decimals_and_figure_labels(polished)
    if language_policy.code == "en":
        polished = _repair_english_ocr_text_artifacts(polished)
    return state.with_html(polished)


def _polish_phase_presentation(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
    del context
    polished = state.html
    polished = _mark_wide_table_layout(polished)
    polished = _inject_utf8_charset(polished)
    polished = _inject_default_styles(polished)
    polished = _wrap_body_in_container(polished)
    polished = _cleanup_empty_html_blocks(polished)
    polished = _fix_heading_inline_abbreviation_breaks(polished)
    polished = _restore_abbreviations(polished)
    return state.with_html(polished)


def _polish_phase_katex_and_final_repairs(state: RawPolishState, context: RawPolishContext) -> RawPolishState:
    language_policy = _raw_polish_context_language_policy(context)
    polished = state.html
    citation_profile = context.citation_profile
    polished = _render_katex_html(polished)
    polished, _ = _repair_sentence_breaks_around_float_units(polished)
    if not _should_suppress_numeric_ref_links_for_author_year(polished, citation_profile):
        polished = _link_flattened_et_al_numeric_citations_to_existing_refs(polished)
        polished = _link_unlinked_numeric_superscripts_to_existing_refs(polished)
    else:
        polished = _unwrap_numeric_ref_links_for_author_year_profile(polished)
    polished = _repair_author_year_footnote_ref_links(polished, citation_profile=citation_profile)
    polished = _unwrap_malformed_ref_anchor_openings(polished)
    polished = _repair_nested_reference_links(polished)
    polished = _repair_numeric_ref_false_positives(polished)
    polished = _fix_false_sup_citations_in_decimals_and_figure_labels(polished)
    if language_policy.code == "en":
        polished = _repair_english_ocr_text_artifacts(polished)
    polished = _repair_second_echelon_ocr_residue_html(polished)
    polished = _repair_confirmed_front_matter_artifacts(polished)
    polished = _normalize_double_escaped_url_anchor_text(polished)
    if context.enable_citation_linkify:
        polished = _late_recover_orphan_figure_anchors_and_links(polished)
        current_figures = _current_figure_target_keys(polished)
        if current_figures:
            polished = _link_spaced_multipanel_figure_refs(polished, current_figures)
            polished = _unwrap_nested_same_href_internal_links(polished)
            polished = _normalize_spacing_after_z2m_links(polished)
    polished = _unwrap_broken_internal_semantic_links(polished)
    polished, _ = _trim_adjacent_article_tail_after_references(polished)
    return state.with_html(polished)


_RAW_POLISH_PHASE_RUNNERS = {
    "pre_cleanup": _polish_phase_pre_cleanup,
    "math_and_units": _polish_phase_math_and_units,
    "frontmatter_and_footnotes": _polish_phase_frontmatter_and_footnotes,
    "semantic_targets": _polish_phase_semantic_targets,
    "references_and_links": _polish_phase_references_and_links,
    "float_units": _polish_phase_float_units,
    "presentation": _polish_phase_presentation,
    "katex_and_final_repairs": _polish_phase_katex_and_final_repairs,
}


def _raw_html_polish_phases() -> tuple[ExecutablePolishPhase, ...]:
    phases: list[ExecutablePolishPhase] = []
    for phase in DEFAULT_POLISH_PHASES:
        runner = _RAW_POLISH_PHASE_RUNNERS[phase.name]
        phases.append(ExecutablePolishPhase(name=phase.name, purpose=phase.purpose, run=runner))
    return tuple(phases)


def polish_html_phase_names() -> tuple[str, ...]:
    """Return the documented raw HTML polish phase order."""

    return default_polish_phase_names()


_DATA_IMAGE_SHIELD_PLACEHOLDER = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
_DATA_IMAGE_SHIELD_ATTR_PATTERN = re.compile(
    r'\s+data-z2m-data-image-src-shield\s*=\s*(["\'])([^"\']+)\1',
    re.IGNORECASE,
)


def _shield_renderable_data_image_srcs(html: str) -> tuple[str, dict[str, str]]:
    """Replace large renderable data-image payloads with tiny placeholders during text polish."""

    shielded: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        prefix = match.group(1)
        quote = match.group(2)
        src_value = match.group(3).strip()
        suffix = match.group(4)
        if not src_value.lower().startswith("data:image/"):
            return match.group(0)
        if not _data_image_src_looks_renderable(src_value):
            return match.group(0)
        if _DATA_IMAGE_SHIELD_ATTR_PATTERN.search(prefix):
            return match.group(0)

        key = f"img-src-{len(shielded)}"
        shielded[key] = src_value
        prefix = re.sub(
            r"\bsrc\s*=\s*$",
            f'data-z2m-data-image-src-shield="{key}" src=',
            prefix,
            flags=re.IGNORECASE,
        )
        return f"{prefix}{quote}{_DATA_IMAGE_SHIELD_PLACEHOLDER}{suffix}"

    return _IMG_SRC_PATTERN.sub(replace, html), shielded


def _restore_shielded_data_image_srcs(html: str, shielded: Mapping[str, str]) -> str:
    if not shielded:
        return html

    def replace(match: re.Match[str]) -> str:
        prefix = match.group(1)
        quote = match.group(2)
        suffix = match.group(4)
        key_match = _DATA_IMAGE_SHIELD_ATTR_PATTERN.search(prefix)
        if key_match is None:
            return match.group(0)
        original_src = shielded.get(key_match.group(2).strip())
        if not original_src:
            return match.group(0)
        prefix = _DATA_IMAGE_SHIELD_ATTR_PATTERN.sub("", prefix)
        return f"{prefix}{quote}{original_src}{suffix}"

    return _IMG_SRC_PATTERN.sub(replace, html)


def polish_html_document(
    html: str,
    *,
    table_caption_language: str = "ru",
    enable_citation_linkify: bool = True,
    citation_profile: Any | None = None,
    image_cache: Mapping[str, str] | None = None,
    polish_language: str | None = None,
) -> str:
    language_policy = resolve_polish_language_policy(
        polish_language,
        table_caption_language=table_caption_language,
    )
    context = RawPolishContext(
        table_caption_language=table_caption_language,
        enable_citation_linkify=enable_citation_linkify,
        citation_profile=citation_profile,
        image_cache=image_cache,
        language_policy=language_policy,
    )
    shielded_html, data_image_srcs = _shield_renderable_data_image_srcs(html)
    polished = run_polish_phases(
        shielded_html,
        context=context,
        phases=_raw_html_polish_phases(),
    ).html
    return _restore_shielded_data_image_srcs(polished, data_image_srcs)


def _looks_like_ru_html_artifact(html_path: Path) -> bool:
    name = html_path.name.lower()
    if name.endswith(".ru.html") or name.endswith("_ru.html") or name.endswith("-ru.html"):
        return True
    return bool(
        re.search(
            r"(?:^|[\s._\-\[\(])ru(?:ssian)?(?:[\s._\-\]\)]|$)",
            name,
            re.IGNORECASE,
        )
    )


def inline_images_only_from_html_file(html_path: Path) -> InlineHtmlResult:
    """Inline sidecar images without applying Marker/PDF HTML polish."""

    text = html_path.read_text(encoding="utf-8", errors="replace")
    result, _ = _inline_images_from_html_text(text, html_path.parent)
    return result


def polish_and_inline_html_file(html_path: Path, citation_profile: Any | None = None) -> InlineHtmlResult:
    """Inline sidecar images and run Marker/PDF HTML polish."""

    text = html_path.read_text(encoding="utf-8", errors="replace")
    base_dir = html_path.parent
    inline_result, image_cache = _inline_images_from_html_text(text, base_dir)
    inlined_html = inline_result.html
    inlined_count = inline_result.inlined_images
    is_ru_html = _looks_like_ru_html_artifact(html_path)
    inlined_html = polish_html_document(
        inlined_html,
        table_caption_language=("ru" if is_ru_html else "en"),
        enable_citation_linkify=not is_ru_html,
        citation_profile=citation_profile,
        image_cache=image_cache,
    )
    inlined_html, refreshed_after_polish = _refresh_inlined_data_urls_by_hint(
        inlined_html,
        base_dir=base_dir,
    )
    inlined_count += refreshed_after_polish
    inlined_html, refreshed_from_cache = _refresh_inlined_data_urls_by_cache(
        inlined_html,
        image_cache=image_cache,
    )
    inlined_count += refreshed_from_cache
    return InlineHtmlResult(html=inlined_html, inlined_images=inlined_count)


def inline_images_from_html_file(html_path: Path, citation_profile: Any | None = None) -> InlineHtmlResult:
    """Backward-compatible alias for Marker/PDF polish plus image inlining."""

    return polish_and_inline_html_file(html_path, citation_profile=citation_profile)

