#!/usr/bin/env python
"""Audit EN raw -> EN polish stage pairs without running Marker."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from dataclasses import asdict
from html import unescape
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pdf_html_polish.html_stages import HTML_STAGE_DIR_NAME, POLISH_STAGE_NAME, RAW_STAGE_NAME
from pdf_html_polish.quality_loop.audit_blocks import (
    Block,
    Defect,
    attrs as _attrs,
    diagnostic_text as _diagnostic_text,
    diagnostic_word_text as _diagnostic_word_text,
    diagnostic_words as _diagnostic_words,
    line_at as _line_at,
    line_at_from_starts as _line_at_from_starts,
    line_starts as _line_starts,
    missing_figure_warning_blocks as _missing_figure_warning_blocks,
    normalize_ws as _normalize_ws,
    parse_blocks as _parse_blocks,
    parse_overlapping_blocks as _parse_overlapping_blocks,
    plain_text as _plain_text,
    reference_identity_blocks as _reference_identity_blocks,
    snippet as _snippet,
    strip_tags as _strip_tags,
    structure_html as _structure_html,
    unit_diagnostic_text_from_html as _unit_diagnostic_text_from_html,
    visible_ref_number_from_match as _visible_ref_number_from_match,
    word_sequence_match as _word_sequence_match,
)
from pdf_html_polish.quality_loop.audit_images import (
    IMG_SRC_RE,
    image_identity_key as _image_identity_key,
    is_inline_or_remote_src as _is_inline_or_remote_src,
    local_image_candidates as _local_image_candidates,
    missing_local_images as _missing_local_images,
)
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect
from pdf_html_polish.quality_loop.audit_frontmatter import (
    FRONTMATTER_OCR_RE,
    block_looks_like_frontmatter_affiliation_table as _block_looks_like_frontmatter_affiliation_table,
    frontmatter_defects as _frontmatter_defects,
)
from pdf_html_polish.quality_loop.audit_figure_caption_ux import (
    BIORENDER_CAPTION_SPLIT_RE,
    BIORENDER_CAPTION_URL_RE,
    CAPTION_INTRUSION_RE,
    CAPTION_TEX_RESIDUE_RE,
    MULTIPANEL_FIG_REF_RE,
    PAGE_FURNITURE_CONTINUATION_RE,
    TABLE_CAPTION_NODE_RE,
    figure_caption_ux_defects as _figure_caption_ux_defects_base,
)
from pdf_html_polish.quality_loop.audit_reference_identity import (
    DOI_ONLY_METADATA_RE,
    EMBEDDED_REF_BOUNDARY_RE,
    LOCAL_ABSTRACT_SECTION_HEADING_RE,
    NUMERIC_VALUE_ROW_RE,
    REFERENCES_HEADING_RE,
    REFERENCE_BIBLIOGRAPHIC_SIGNAL_RE,
    REF_DUP_BRACKET_PREFIX_RE,
    REF_ID_RE,
    VISIBLE_REF_NUM_RE,
    is_references_block as _is_references_block,
    looks_like_local_abstract_reference_block as _looks_like_local_abstract_reference_block,
    numbered_reference_block_is_likely_non_bibliographic as _numbered_reference_block_is_likely_non_bibliographic,
    reference_identity_defects as _reference_identity_defects,
)
from pdf_html_polish.quality_loop.audit_manual_patterns import (
    looks_like_affiliation_label_roman_boundary as _looks_like_affiliation_label_roman_boundary,
)
from pdf_html_polish.quality_loop.audit_manual_recent import (
    ManualBlindSpotDeps,
    MeineRecentLinkDeps,
    MeineRecentTextDeps,
    manual_blind_spot_defects as _manual_blind_spot_defects_base,
    meine_recent_link_structure_defects as _meine_recent_link_structure_defects_base,
    meine_recent_text_ocr_defects as _meine_recent_text_ocr_defects_base,
)
from pdf_html_polish.quality_loop.audit_math_units import (
    DEGREE_DEFECT_RE,
    DISPLAY_MATH_OCR_RE,
    EQUATION_ABSORB_RE,
    INLINE_TEX_RE,
    JOINED_PROSE_TOKEN_RE,
    LINKED_UNIT_EXP_DEFECT_RE,
    MATH_TAG_WITH_CITATION_RE,
    RESIDUAL_UNIT_TEX_RE,
    UNIT_FLATTEN_RE,
    equation_table_defects as _equation_table_defects,
    inline_tex_contains_citation_bracket as _inline_tex_contains_citation_bracket,
    unit_math_defects as _unit_math_defects,
    unit_match_is_repaired_in_raw as _unit_match_is_repaired_in_raw,
)
from pdf_html_polish.quality_loop.audit_report import (
    add_corpus_hit_counts as _add_corpus_hit_counts,
    assemble_report,
    corpus_totals as _corpus_totals,
    defect_quality_counted as _defect_quality_counted,
    find_stage_pairs,
    non_quality_corpus_hit_counts as _non_quality_corpus_hit_counts,
    observed_corpus_hit_counts as _observed_corpus_hit_counts,
    write_json_report as _write_json_report,
)
from pdf_html_polish.quality_loop.audit_pdf import (
    article_name_from_stage as _article_name_from_stage,
    extract_pdf_text as _extract_pdf_text,
    first_path_value as _first_path_value,
    load_pdf_diagnostic_text,
    load_pdf_map as _load_pdf_map,
    PdfDiagnosticsCache as _PackagePdfDiagnosticsCache,
    pdf_citation_link_summary,
    pdf_text_layer_defects as _pdf_text_layer_defects_impl,
    pdf_path_from_map_record as _pdf_path_from_map_record,
    section_order_pdf_defects as _section_order_pdf_defects_impl,
    source_pdf_path,
)
from pdf_html_polish.quality_loop.audit_p04 import (
    looks_like_math_or_measurement_range as _looks_like_math_or_measurement_range,
    unlinked_citation_candidate_numbers as _unlinked_citation_candidate_numbers_base,
    unlinked_citation_range_kind as _unlinked_citation_range_kind_base,
    unlinked_sup_numeric_range_matches_footnote_targets as _unlinked_sup_numeric_range_matches_footnote_targets,
)
from pdf_html_polish.quality_loop.audit_p35 import replacement_char_defects as _replacement_char_defects
from pdf_html_polish.quality_loop.audit_p45 import roman_word_split_defects as _roman_word_split_defects
from pdf_html_polish.quality_loop.audit_p61 import (
    figure_target_keys as _figure_target_keys,
    figure_target_numbers as _figure_target_numbers,
    visible_figure_target_defects as _visible_figure_target_defects,
)
from pdf_html_polish.quality_loop.audit_p71 import known_ocr_token_defects as _known_ocr_token_defects
from pdf_html_polish.quality_loop.audit_p62 import (
    classify_missing_figure_warning as _classify_missing_figure_warning_base,
    figure_label_from_id as _figure_label_from_id,
    figure_label_from_text as _figure_label_from_text,
    figure_unit_label as _figure_unit_label,
    find_warning_block_index as _find_warning_block_index,
    has_nearby_image as _has_nearby_image,
    has_nearby_missing_figure_warning as _has_nearby_missing_figure_warning,
    is_handled_missing_figure_block as _is_handled_missing_figure_block,
    nearest_figure_label as _nearest_figure_label,
    nearby_image_offsets as _nearby_image_offsets_base,
    normalize_figure_label_key as _normalize_figure_label_key,
)


RAW_STAGE = RAW_STAGE_NAME
POLISH_STAGE = POLISH_STAGE_NAME
PDF_SOURCE_STAGE = "00.source.pdf"

REF_LINK_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(\d+)['\"][^>]*>", re.IGNORECASE)
FIG_LINK_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*['\"]#fig-([^'\"]+)['\"][^>]*>", re.IGNORECASE)
TABLE_LINK_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*['\"]#table-([^'\"]+)['\"][^>]*>", re.IGNORECASE)
PAGE_LINK_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"]#page-(?P<target>[^'\"]+)['\"][^>]*>"
    r"(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
ANCHOR_BODY_RE = re.compile(r"<a\b[^>]*>(?P<body>.*?)</a>", re.IGNORECASE | re.DOTALL)
DOUBLE_CLOSE_ANCHOR_RE = re.compile(r"</a>\s*</a>", re.IGNORECASE)
URL_ANCHOR_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"](?:https?://|www\.)[^'\"]+['\"][^>]*>.*?</a>",
    re.IGNORECASE | re.DOTALL,
)
MALFORMED_URL_ANCHOR_BODY_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"](?:https?://|www\.)[^'\"]+['\"][^>]*>"
    r"\s*(?:(?:hps|htps|ttps)://|https?://\s+|\d+www\.|"
    r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+/\s+"
    r"[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+)[\s\S]{0,300}?</a>|"
    r"<a\b[^>]*\bhref\s*=\s*(?P<split_quote>['\"])(?P<split_href>https?://[^'\"]+)(?P=split_quote)[^>]*>"
    r"\s*\(?https?://[^<]{1,120}/\s*</a>\s*"
    r"<a\b[^>]*\bhref\s*=\s*(?P=split_quote)(?P=split_href)(?P=split_quote)[^>]*>"
    r"\s*[A-Za-z0-9][^<]{0,120}</a>",
    re.IGNORECASE | re.DOTALL,
)
REF_ANCHOR_BODY_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<num>\d+)['\"][^>]*>"
    r"(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
FIG_CAPTION_RE = re.compile(r"^\s*(?:Figure|Fig\.?|FIGURE)\s+\d+[A-Za-z]?\b", re.IGNORECASE)
TABLE_CAPTION_RE = re.compile(r"^\s*(?:TABLE|Table)\s+(?:[IVXLCM]+|\d+)\b", re.IGNORECASE)
CITATION_RANGE_LIST_RE = re.compile(
    r"\[\s*\d+\s*(?:[-\u2013]\s*\d+|,\s*\d+)"
    r"(?:\s*,\s*\d+(?:\s*[-\u2013]\s*\d+)?)*\s*\]"
)
TAGGED_CITATION_RANGE_LIST_RE = re.compile(
    r"\[\s*(?P<body>(?=[\s\S]*?<)[\s\S]{1,260}?)\s*\]",
    re.IGNORECASE,
)
SUP_NUMERIC_RANGE_RE = re.compile(
    r"<sup\b(?![^>]*\bz2m-unit-exp\b)[^>]*>"
    r"(?P<body>\s*\d{1,3}\s*(?:[-\u2013\u2014]\s*\d{1,3}|,\s*\d{1,3})"
    r"(?:\s*,\s*\d{1,3}(?:\s*[-\u2013\u2014]\s*\d{1,3})?)*\s*)"
    r"</sup>",
    re.IGNORECASE,
)
LATEX_SUP_CITATION_RE = re.compile(r"\\\(\^\{[\d,\s\-\u2013\u2014]+}\\\)")
OCR_CITATION_WORD_RE = re.compile(
    r"\btask\.\s+Sec\.|\bflagship models\s+6,000\b",
    re.IGNORECASE,
)
NONCITATION_CONTEXT_RE = re.compile(
    r"\b(?:pH|D\d|Vand|Aand|mAand|uAand|µAand|μAand)\b|"
    r"\b(?:week|month)\s+\d+\b|"
    r"\b(?:monkey|animal|female|male)\s+\d+\b|"
    r"\b(?:mm\s*s|cm\s*s|m\s*s|cm|mC|kg|mA|uA|µA|μA|MHz|GHz|kHz)\s*[-\u2212]\s*\d+\b|"
    r"\b(?:u|µ|μ)m\s*(?:1|2)\b",
    re.IGNORECASE,
)
ML_PER_SECOND_CONTEXT_RE = re.compile(r"\bmL\s*[:/]\s*s\s*\{?\s*[-\u2212]?\s*\d+\b", re.IGNORECASE)
BROKEN_URL_TEXT_RE = re.compile(
    r"\b(?:hps|htps|ttps)://\S+|"
    r"\bhttps?://\s+|"
    r"\bhttps?://\S+\s+\d+www\.|"
    r"\b\d+www\.[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|"
    r"\bhttps?://(?:dx\.)?doi\.org/\d+\.\d+/\s+[A-Za-z0-9]|"
    r"\bhttps?://doi\.org/10\s+\.\s+\d+|"
    r"\bhttps?://\S+/(?:wp|news-room/north|contents/part1/ports-and|ports-and-container)\s+[A-Za-z0-9]|"
    r"\bhttps?://\S+/cgi/pt\?\s+[A-Za-z0-9]|"
    r"\bhttps?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+/\s+"
    r"(?!https?://|www\.)"
    r"(?=[A-Za-z0-9._~:/?#\[\]@!$&'*+,;=%-]*[A-Za-z._~:/?#\[\]@!$&'*+,;=%-])"
    r"[A-Za-z0-9._~:/?#\[\]@!$&'*+,;=%-]+|"
    r"\bhttps?://\S+\.(?:h\s+tml|xht\s+ml)\b|"
    r"\btouching-\s+the-prado\b|"
    r"\bdoi\.org/\s+10\.",
    re.IGNORECASE,
)
LOWERCASE_REF_GLUE_RE = re.compile(r"^[a-z][\s\u00a0]*\d{1,4}(?:[\s,\-–\u2013\u2014\d.);]*)?$")
SPLIT_EMAIL_TEXT_RE = re.compile(
    r"\b[A-Za-z][A-Za-z0-9._%+-]{2,}\s+(?:vi|iv|ix|i|v|x)@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
RUNAWAY_REPEATED_TEXT_RE = re.compile(
    r"\b(?P<word>[A-Za-z]{3,})\b(?:\s*(?:,|\\,)\s*(?P=word)\b){5,}|"
    r"(?:moderately\s+slow\s+deactivation\s+kinetics[\s\S]{0,120}?){3,}",
    re.IGNORECASE,
)
LOST_FF_WORD_RE = re.compile(
    r"\b(?:afective|coeficient|diference|diferential|efect(?:s|ive|ively)?|"
    r"eficacy|eficient(?:ly)?|afect(?:s|ed|ing|ive|ively)?|eectiveness|"
    r"diferent(?:ial(?:ly)?)?|specifc|identifed|fow|fxed|artifcial|"
    r"refect|ofline|aferents|afiliations|ailiations|ofice|oficer|"
    r"suficient(?:ly)?|tradeofs|"
    r"fexible|ultrafexible|fbers|flms?|fbroin|biofuid|difusion|coefcient|"
    r"defcits|scafolds|feld-efect|fnger|galss|artiicial|scientiic|"
    r"certiication|deining|simpliication|irst|inluence|itness|worklow|"
    r"frst|fne|fgurative|defned|profcient|beneft|"
    r"difcult(?:y|ies)?|staf|efort(?:s)?|confrm(?:ed|ing)?|clarifed|"
    r"infuenced|fndings|feld|ndings)\b|"
    r"(?:\u00ae|\u0412\u00ae)rst\b|"
    r"\b(?:suf|insuf)\s+cient\b|\bbene\s+ts\b|\bmagnetic\s+eld\b|"
    r"\beld\s+strength\b|\bve\s+patients\b|\bOf\s+ce\b|\burine\s+ow\b|"
    r"\bwhite\s+ght\b|"
    r"\b(?:specifi|Specifi|signifi|Signifi|defi|Defi|diffi|Diffi|profi|Profi|"
    r"confi|Confi|benefi|Benefi|identi?fi|Identi?fi|Offi|offi|Griffi|"
    r"fl|Fl|urofl|Urofl|outfl|Outfl|refl|Refl|infl|Infl)\s+"
    r"(?:c|cally|cant(?:ly)?|ned|ne|nition|ciency|cult(?:y|ies)?|le(?:s|ometry)?|"
    r"dence|cial|es|ce|ths|oor|ow(?:s|metry|meter|rate)?|uid|ll(?:ing)?|"
    r"uoroscopy|uoroscopic|uorescent|ux|uence)\b|"
    r"\b(?:Urofowmet(?:ry|ery)|urofowmet(?:ry|er)|"
    r"fow(?:s|ing|ed|meter|meters|metry|rate|rates)?|"
    r"fll(?:ing|ed)?|fuid|fuoroscop(?:y|ic)|fuorescent|"
    r"modifcations?|modifcation|signifcant(?:ly)?|specifcity|"
    r"identifes|diferentiating|flter(?:ing)?|cutof)\b",
    re.IGNORECASE,
)
KNOWN_JOINED_WORD_RE = re.compile(
    r"\b(?:considerationsincluding|displaycan|refreshabletactile|staffmembers?|"
    r"timeconsuming|nervesparing|da\s+Vinci1Si|touchinteraction|realworld|"
    r"Theexperiment|tookplace|Thisarearepresented|hadtobeencoded|"
    r"off-theshelf|state-ofthe-art|numbergestures|twodimensional|"
    r"Perceptionof|Descriptionsfor|openaccess|basrelief|threedimensional|"
    r"UFrecorded|SUFestimated|SUFdetermined|MRsafe|MRcompatible|"
    r"lung-tohead|feed-andsleep|readyreckoners|injuryassociated|"
    r"allin-one|singlefinger|locationspecific|Computeraided|Volpe1|"
    r"MBVurgency|Qmaxnormal|residualnormal|ofdepression|inIndian|"
    r"asmeasured|symptomscore|withlower|tractfunction|benignprostatic|"
    r"urineflow|AcceptableBladder|suggestiveof|distentionon|healthyyoung|"
    r"Theeffect|mattecollodion|Nineteenthcentury|darkbrown|nearinfrared|"
    r"selfcontrolled|99Tcmcolloids|nonneoadjuvant|vanderVorst|populationbased|"
    r"Positionrelated|intraand|lightbeam|Videobased|handassembled|OpticalTouch|"
    r"airpolluted|vitamin-Ddeficient|watersoluble|asprepared|ecofriendly|"
    r"explorationSeamless|basreliefs|frontto-back|signalto-noise|farred|"
    r"FromFebruary|Qmaxurgency|image\s+processingbased|"
    r"extrusionsurgically|inflammationat|of\s+theonly|NeururolUrodyn2021|"
    r"such\s+asportraits|iodineattacks|"
    r"timedependent|first-inhumans|backilluminated|anatomicallycompatible|"
    r"convectionenhanced|neurologicallyrelated|valvegated|mindenhancing|"
    r"andChallenges|SoftBankbacked|singleneuron|crossfrequency|"
    r"inhibitionbased|phaselocked|ofrealistic|ofmedical|ofclinical|"
    r"ofperspective|offactual|oflarge|of13|ofthe\s+accepted|andrequests|"
    r"andpermissions|Competinginterests|Additionalinformation|"
    r"Alessentially|medicineresistant|customdesigned|hardwareupdate|"
    r"KeunWhangbo|easy-tolearn|Shapefrom-shading|Attributebased|"
    r"thistask|higherthan|disabilitiessometimesface|artworksis|"
    r"hierarchicalsegmentation|webbased|needsto|includesinformation|"
    r"participantssuggested|overallwork|guidelinesfor|issimilarto|"
    r"easierto|spatialcognitive|wassupported|blindaccessible|"
    r"Key-wordaware|CTABassistant|pushpull|twoobject|itemspecific|"
    r"controlrelated|lowdimensional|topdown|contextdependent|"
    r"finergrained|cuetrials|trialaverage|match-tosample|"
    r"spatiovectors|Qcould|Qto|IPPgrades|metaanalysis|"
    r"BPHassociated|BEHAVIORALAND|OFTACTILE|EVERYDAYACTIVITIES|"
    r"featurebased|upprojection|groundtruth|shiftinvariant|imagedepth|"
    r"intraobject|state-oftheart|domaininvariant|textdetection|"
    r"speechballoon|textbased|contentaware|leftright|Semisupervised|"
    r"imageto-image|realdomain)\b|"
    r"\btexture\.Tactile\b|"
    r"\bheld\s+inWM\b|"
    r"patients,were|prostatectomy\u0394VV|\btheCreative\b|\bd\)2\.5D\b|"
    r"\bAl\s+Omari1\b",
    re.IGNORECASE,
)


def _joined_word_match_is_url_slug(text: str, match: re.Match[str]) -> bool:
    left = text[max(0, match.start() - 96): match.start()]
    return bool(re.search(r"(?:https?://|www\.)[^\s<>()\[\]]*$", left, re.IGNORECASE))


FLOAT_SENTENCE_INTERRUPT_RE = re.compile(
    r"For\s+these[\s\S]{200,6000}?reasons,\s+a\s+transdiagnostic|"
    r"also\s+and\s+the\s+Committee[\s\S]{0,2000}?require\s+evaluation|"
    r"trigger\s+global\s+projection\s+targets[\s\S]{0,2000}?"
    r"innate\s+or\s+adaptive\s+immune\s+responses|"
    r"systemic\s+circulation[\s\S]{0,1800}?"
    r"(?:transduced\s+target\s+cells|Human\s+immune\s+responses\s+to\s+AAV)"
    r"[\s\S]{0,1800}?\(with\s+some\s+serotypes\s+more\s+likely\s+to\s+leak",
    re.IGNORECASE,
)
CORRUPT_EMAIL_LABEL_RE = re.compile(r"(?:\b[MmSs]e-mail:|[\u25a1\ufffd]\s*S?e-mail:)")
REFERENCE_ROMAN_SPLIT_RE = re.compile(
    r"\bBiobeha\s+v\.\s+Rev\.|\bBeha\s+v\.\s+Res\.\s+Methods\b|"
    r"\bBeha\s+v\.\s+Sci\.(?=\W|$)",
    re.IGNORECASE,
)
TABLE_NOTE_BODY_MERGE_RE = re.compile(
    r"Positive\s+value\s*=\s*increased\s+symptoms,\s*negative\s+value\s*=\s*"
    r"decreased\s+symptoms\s+studies\s+to\s+evaluate\b|"
    r"\bin\s+the\s+absence\s+of\s+aSignificant,\s*p\s*(?:<|&lt;)\s*0\.05\.\s+"
    r"standards,\s+it\s+remains\b",
    re.IGNORECASE,
)
AUTHOR_MARKER_GLUE_RE = re.compile(r"\b[A-Z][A-Za-z-]{3,}\s+100\s+and\b")
LATEX_MACRO_RUNAWAY_RE = re.compile(r"(?:\\@ifnextchar[\s\S]{0,80}){6,}", re.IGNORECASE)
DOI_BODY_PROSE_MERGE_RE = re.compile(
    r"\b(?:DOI:\s*(?:https?://(?:dx\.)?doi\.org/)?10\.[^\s<]+|"
    r"https?://(?:dx\.)?doi\.org/10\.[^\s<]+)"
    r"\s+(?:the|this|we|in|as|or|depicted|generated|lines)\b",
    re.IGNORECASE,
)
DETACHED_ACCENT_RE = re.compile(
    r"\b[A-Za-z]{2,}[\u00a8\u00b4\u00b8\u02c6\u02c7\u02d9\u02dc][A-Za-z]{1,}\b|"
    r"\bOA\u02c6\s+\u02c7SModhrain\b|"
    r"\bB[A-Za-z]+hler,\s*\u02dc\s+and\b|"
    r"\bHeppner,\s*[\u00b4\u02c6]\s+and\b|"
    r"\bC\u00b8\s*\.\s+Varel\b|"
    r"\bSyd\s+\u00a8\s+anheimo\b|"
    r"\bwireless\s+\u00a8\s+intraocular\b|"
    r"\bPakenait\s+\u02d9\s*e\u02d9?\b|\bPeter\s+M\s+\u02d9\s+Hall\b|"
    r"\bSpath\s+\u00a8\b|\bSequin\s+\u00b4\s+,|\bwould\s+\u00b4\s+be\b|"
    r"\b[A-Za-z]{2,}\s+\u00a8\b|\b[A-Za-z]{2,}-?\s+[\u00a8\u00b4]\s+[A-Za-z]{2,}\b|"
    r"\bBRICENO\S\s*,\s*H\.\s*M\.|\bHOLLERER\s+[^A-Za-z0-9\s,]\s*,\s*T\.|"
    r"\b(?:PogoreliВґc|HuskiВґc|CohadЕѕiВґc|JukiВґc|Л‡\s+Using)\b",
    re.IGNORECASE,
)
TABLE_SECTION_ABSORB_RE = re.compile(
    r"\bTable\s+3\.1:[\s\S]{0,3000}\b3\.8\.\s+Data\s+Acquisition"
    r"[\s\S]{0,3000}\b3\.9\.\s+Criteria\s+for\s+Use\s+of\s+Data\b",
    re.IGNORECASE,
)
INTRA_WORD_SPACE_RE = re.compile(
    r"\bob\s+je\s+ct\s+s\s+w\s+ould\b|"
    r"\bsafe\s+ty\s+c\s+oncerns\b|"
    r"\bincl\s+ude\b|"
    r"\bb\s+e\s+interpreted\b|"
    r"\bA\s+dd\s+itional\b|"
    r"\bsupple\s+mental\b|"
    r"\bexpressi\s+ve\s+ness\b|"
    r"\bT\s+his\s+fact\b|"
    r"\bCNC-millin\s+g\s+m\s+achines\b|"
    r"\bsupp\s+ort\s+structures\b|"
    r"\ba\s+dditive\s+production\b|"
    r"\balternati\s+ves\b|"
    r"\bpr\s+inting\s+services\b|"
    r"\btechnical\s+ly\b|"
    r"\bstraightfo\s+rw\s+ard\b|"
    r"\bGener\s+al\s+digital\b|"
    r"\bBarc\s+elona\b|"
    r"\bthr\s+ee\s+different\b|"
    r"\bt\s+o\s+the\s+best\s+of\s+our\s+knowledge\b|"
    r"\bhigh\s*\)\s*w\s+ere\b|"
    r"\bB\s+rain-computer\b|"
    r"\bBel\s+humeur\b|"
    r"\bGroenenda\s+al@|\bWilhel\s+mina\b|\bRUTHERFO\s+RD\b|"
    r"\benviron\s+ment\b|\bInter\s+national\b|\bdisconti\s+nuation\b|"
    r"\bIta\s+ly\b|\bLeporin\s+i\b|\benj\s+oy\b|\bsepa\s+ration\b|"
    r"\bat\s+tached\b|\bfr\s+om\s+ye\s+elk\b|\beve\s+ly\b",
    re.IGNORECASE,
)
INLINE_INTRA_WORD_SPACE_HTML_RE = re.compile(
    r"<a\b[^>]*>\s*\[?\s*Bel\s*</a>\s*humeur\b|"
    r"\bob\s*<a\b[^>]*>\s*je\s*</a>\s*"
    r"<a\b[^>]*>\s*ct\s*</a>\s*"
    r"<a\b[^>]*>\s*s\s+w\s*</a>\s*ould\b|"
    r"\bob\s+je\s+ct\s*<a\b[^>]*>\s*s\s+w\s*</a>\s*ould\b|"
    r"\bsafe\s*<a\b[^>]*>\s*ty\s+c\s*</a>\s*oncerns\b|"
    r"\bincl\s*<a\b[^>]*>\s*ude\s*</a>|"
    r"<a\b[^>]*>\s*b\s*</a>\s*e\s+interpreted\b|"
    r"\bA\s*<a\b[^>]*>\s*dd\s*</a>\s*itional\b|"
    r"\bexpressi\s*<a\b[^>]*>\s*ve\s*</a>\s*ness\b|"
    r"\bT\s*<a\b[^>]*>\s*his\s*</a>\s*fact\b|"
    r"\bCNC-millin\s*<a\b[^>]*>\s*g\s+m\s*</a>\s*achines\b|"
    r"\bsupp\s*<a\b[^>]*>\s*ort\s+structures\s+in\s+a\s*</a>\s*dditive\s+production\b|"
    r"\balternati\s*<a\b[^>]*>\s*ves\s*</a>|"
    r"<a\b[^>]*>\s*pr\s*</a>\s*inting\s+services\b|"
    r"\btechnical\s*<a\b[^>]*>\s*ly\s*</a>|"
    r"\bhigh\s*<a\b[^>]*>\s*\)\s*</a>\s*<a\b[^>]*>\s*w\s*</a>\s*ere\b|"
    r"\bthr\s*<a\b[^>]*>\s*ee\s*</a>\s*different\b|"
    r"\bstraightfo\s*<a\b[^>]*>\s*rw\s*</a>\s*ard\b|"
    r"\bGener\s*<a\b[^>]*>\s*al\s*</a>\s*digital\b|"
    r"<a\b[^>]*>\s*Barc\s*</a>\s*elona\b|"
    r"\benj\s*<a\b[^>]*>\s*oy(?:\s+a)?\s*</a>|"
    r"<b\b[^>]*>\s*B\s*</b>\s*rain-computer\b|"
    r"\bIta\s*<b\b[^>]*>\s*ly\s*</b>",
    re.IGNORECASE,
)
TABLE_FOOTNOTE_WORD_LETTER_HTML_RE = re.compile(
    r"\b(?:Leporin|Ghian)\s*"
    r"<sup\b(?=[^>]*\bclass\s*=\s*([\"'])[^\"']*\bz2m-table-fn\b[^\"']*\1)[^>]*>"
    r"\s*i\s*</sup>",
    re.IGNORECASE,
)
AFFILIATION_DEPARTMENT_GLUE_RE = re.compile(r"\b(?:[1-9]|Institute)Department\b")
SUSPICIOUS_EMAIL_DOMAIN_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@unfi\.it\b",
    re.IGNORECASE,
)
BODY_PAGE_HEADER_RE = re.compile(
    r"\b[A-Z][A-Z]+(?:\s+ET\s+AL\.)?\s*\|\s*\d{3,5}\b|"
    r"\bJin\s+et\s+al\.\s+Combined\s+Imaging\s+in\s+Breast\s+Cancer\b|"
    r"\bAlrabadi\s+et\s+al\.\s+\d+\b|"
    r"\b\d+:\d+\s+.{0,4}\s+A\.\s+Reichinger\s+et\s+al\.(?=\W|$)|"
    r"\bThe\s+Getty\s+Conservation\s+Institute,\s+©\s+2013\s+J\.\s+Paul\s+Getty\s+Trust\b|"
    r"\bResonance-Compatible\s+Incubator\s+With\s+a\s+Built-in\s+Coil\s+"
    r"Ultrafast\s+Magnetic\s+Resonance\s+Imaging\s+of\s+the\s+Neonate\s+in\s+a\s+Magnetic\b|"
    r"\bPEDIATRICS\s+is\s+owned[\s\S]{0,360}\bAmerican\s+Academy\s+of\s+Pediatrics\b|"
    r"\bJournal\s+of\s+Materials\s+Chemistry\s+B\s+Accepted\s+Manuscrip\b|"
    r"\bPublished\s+on\s+20\s+July\s+2015\.\s+Downloaded\s+by\s+California\s+State\s+University\s+at\s+Fresno\b|"
    r"\bPublished\s+on\s+03\s+August\s+2015\.\s+Downloaded\s+by\s+Emory\s+University\b|"
    r"\bChemComm\s+Accepted\s+Manuscript\b|"
    r"\b15206777,\s+2021,\s+S3,\s+Downloaded\s+from\s+https://onlinelibrary\.wiley\.com/doi/10\.1002/nau\.24751\b|"
    r"\bEgyptian\s+National\s+Sti\.\s+Network\s+\(Enstinet\)\b|"
    r"\bRETURN\s+CIRCULATION\s+DEPARTMENT\b|"
    r"\b\d{2,3}\s+Y\.\s+Volpe\s+et\s+al\.(?=\s|$)|"
    r"\bManuscript\s+received\s+on\s+April\s+17,\s+2021\b[\s\S]{0,260}"
    r"\bManuscript\s+published\s+on\s+April\s+30,\s+2021\b|"
    r"\bBlue\s+Eyes\s+Intelligence\s+Engineering\s+&\s+Sciences\s+Publication\b|"
    r"\bRetrieval\s+Number:100\.1/ijmh\.E1208015521\b|"
    r"\bCheck\s+for\s+updates\b",
    re.IGNORECASE,
)
TABLE_GIBBERISH_FLOW_RE = re.compile(
    r"\bTABLE\s+\d[\s\S]{0,1400}\bnales\s+5\s+ted\s+Q\s+a\s+rates\b|"
    r"\bQn\s+Flow\s+i\s+[^\s]{1,4}ax\s+ndexes\b|"
    r"\bP\s+Values\s+0\.06\s+0\.00\s+4\s+\.565\b|"
    r"\bDid\s+tl\s+ne\s+IAG\s+he\s+elp\b|"
    r"\bYour\s+general\s+ii\s+mpressio\s+n\b|"
    r"\bHow\s+did\s+you\s+f\s+ind\s+using\s+g\s+the\s+IAC\b|"
    r"\bWhat\s+tee\s+chnology\s+u\s+may\s+tic\s+k\b|"
    r"\bOrigina\s+al\s+Color\s+Simpl\s+i\s+fication\b|"
    r"\bCollodion\s+Prints\s+S\s+Process[\s\S]{0,900}\bWothlytype\b|"
    r"\bAn\s+Over\s+5\s+Ho\s+6[\s\S]{0,600}\bPac\s+kard\s+Ideal\s+Shutter\b|"
    r"\bCleaning\s+the\s+Autographic\s+Kodak\s+Camera\s+1915-192640[\s\S]{0,600}\bHIMPY\b|"
    r"\bGrafle\s+x\s+Speed\s+Graphic[\s\S]{0,1400}\btopper\s+diago\s+silotoro\b|"
    r"\bThornton-Pickard\s+Duple\s+x\s+Ruby\s+Refle\s+x[\s\S]{0,1400}\btiems\s+strate\b|"
    r"\bMS\s+MPTO\s+SY[\s\S]{0,900}\bW\s+TO\s+GET\s+IT\s+HO\b|"
    r"\bHyposulp\s+Water\s+phite\s+of\s+of\s+soc\s+la\b|"
    r"\bRain\s+or\s+distille\s+d\s+w\s+rater\b|"
    r"\bРўСѓ\s+of\s+ar\s+t\s+bei\s+ng\s+M\s+oda\s+litie\s+s[\s\S]{0,1400}"
    r"\bEv\s+alu\s+atio\s+n\b|"
    r"\benclusive\s+app\b[\s\S]{0,1200}\bCavalier\s+i\s+et\s+al\.|"
    r"\bTrichopoulos\s+et\s+al\.[\s\S]{0,1200}\bV\s+\.\s+v\s+V\b|"
    r"\bHydrometer\s+g\s+4[\s\S]{0,180}\bHydrometer\s+only\b|"
    r"\bT\s+a\s+bl\s+e\s+2\s+1\s+con\s+t'[\s\S]{0,40}nue\s+d\b|"
    r"\bHE\S?LTHY\s+SUBJECT\s+11\s+ME\S?SUREMENT\s+32\s+SER\b",
    re.IGNORECASE,
)
FLOAT_OR_METADATA_INTERRUPTION_RE = re.compile(
    r"\bDespite\s+the\s+intensive\s+investigation\s+of[\s\S]{0,1800}\badults\s+and\s+older\s+children\b|"
    r"\bprinted\s+on\s+swell\s+paper\s+to[\s\S]{0,1600}\bform\s+a\s+tactile\s+rendering\b|"
    r"\bin\s+the\s+\(hypothetic\)[\s\S]{0,1600}\b3D\s+space\b|"
    r"\bprogrammed\s+pharmacological\s+delivery\s+and\s+mul-[\s\S]{0,2000}\btimodal\s+sensing\b|"
    r"\bMRI\s+is\s+now\s+recommended\s+as\s+the\s+standard\s+of\s+care\s+for\s+term\s+infants"
    r"[\s\S]{0,1400}\bwith\s+hypoxic\s+ischaemic\s+encephalopathy\b|"
    r"\breliability\s+remains\s+insufficiently[\s\S]{0,2200}\bresearched\b|"
    r"\bTransperineal\s+ultrasound\s+uroflowmetry[\s\S]{0,2600}\bwas\b"
    r"[\s\S]{0,2600}\bcompared\s+with\s+pressure\s+flow\s+studies\b|"
    r"\bselected\s+for\s+the\s+\(B\)\s+1\.\s+Flocked[\s\S]{0,1600}"
    r"\bfamous\s+enough\s+P\s+to\s+bc[\s\S]{0,600}\bE\s+clarity\b|"
    r"\bThere\s+is\s+obvious\s+urinary\s+leakage\s+with[\s\S]{0,900}"
    r"\bminimal\s+increases\s+in\s+intravesical\s+pressure\b|"
    r"\bmalignancy\s+or\s+traumatic\s+lesions\.\s+A[\s\S]{0,1000}"
    r"\bjohn\.webster@wisc\.edu\s+major\s+and\s+essential\s+step\b|"
    r"\bmany\s+visual\s+computing\s+algorithms\s+turn[\s\S]{0,1800}"
    r"\bout\s+to\s+be\s+equally\s+well\s+suited\b|"
    r"\bsurrounding\s+environment\s+needs\s+to\s+be\s+controlled\s+care-"
    r"[\s\S]{0,1400}\bfully,\s+because\b|"
    r"\bapplication\s+discloses\s+magnetic\s+resonance(?:\s+imaging)?"
    r"(?:\s+\(MRI\))?\s+(?:\[071\]\s+)?This\s+(?:imaging\s+)?compatible\b|"
    r"\bThey\s+organize\s+sequential\s+neuronal\s+events\s+as\s+well\s+as\s+The\s+temporal\s+characteristics\b|"
    r"\bStudies\s+Glossary[\s\S]{0,2500}\brelating\s+timing\b|"
    r"\bThe\s+laser\s+components\s+include\s+The\s+Cartesian[\s\S]{0,1600}\b16\s+a\s+60W\s+CO2\b|"
    r"\busing-artificial-intelligence-to-help-blind-people-see-facebook\s+A\s+novel\s+system\b|"
    r"\bClearVision\s+project:\s+www\.clearvisionproject\.org\s+In\s+summary\b|"
    r"\bsmall\s+animals\s+imaging\s+In\s+summary\b|"
    r"\bUrinary\s+flow\s+can\s+also\s+be\s+recorded\s+by\s+voiding\s+on\s+a\s+disk"
    r"[\s\S]{0,1800}\bwhich\s+rotates\s+at\s+a\s+constant\s+speed\b|"
    r"\bwho\s+measured\s+the\s+maximum\s+flow\s+by[\s\S]{0,1800}"
    r"\brecording\s+the\s+volume\s+of\s+air\s+displaced\b|"
    r"\bFour\s+of\s+these\s+principles\s+were\s+tested[\s\S]{0,1200}"
    r"\bUF2[\s\S]{0,1200}\bconstant\s+flow\b|"
    r"\bPatients\s+with\s+a\s+history\s+of\s+lower\s+urinary\s+system\s+surgery"
    r"[\s\S]{0,700}\bwere\s+ex-[\s\S]{0,1200}\bMain\s+Points\b"
    r"[\s\S]{0,1200}\bcluded,\s+and\s+a\s+total\s+of\s+83\s+patients\b|"
    r"\bSpatial\s+computing\s+predicts\s+that\s+control-related[\s\S]{0,1200}"
    r"\bThe\s+green\s+\(sample\s+1\)[\s\S]{0,800}\brectangles\s+mark\b|"
    r"\bA\s+significantly\s+larger\s+portion\s+of\s+the\s+dPCA\s+gamma\s+components"
    r"[\s\S]{0,1600}\bThe\s+4-array\s+spatial\s+distribution\b|"
    r"\bdifferent\s+spatiovectors\s+extracted\s+from\s+2\s+s[\s\S]{0,1200}"
    r"\bSource\s+data\s+are\s+provided[\s\S]{0,300}\bPanel\s+a\b|"
    r"\bCorrespondence\s+Author\s+participants\s+were\s+asked\s+to\s+complete\b|"
    r"\bCompeting\s+interest:\s+See\s+page\s+\d+\s+of\s+the\s+Creative\s+Commons\s+Attribution\s+License\b",
    re.IGNORECASE,
)
FLOAT_OR_METADATA_INTRUSION_MARKER_RE = re.compile(
    r"\b(?:"
    r"Fig(?:ure)?\.?|Figure|Table|Box|Panel\s+[a-z]|"
    r"Strengths?\s+and\s+limitations?|Main\s+Points?|"
    r"Review\s+Article|Source\s+data|"
    r"From\s+the|Accepted\s+for\s+publication|Read\s+at\s+(?:the\s+)?annual\s+meeting|"
    r"Supported\s+by|Department|University|Author(?:s?'?\s+addresses)?|"
    r"Correspondence|Competing\s+Interests?|Creative\s+Commons|Permission|Copyright|DOI|"
    r"john\.[A-Za-z0-9._%+-]+@|https?://|www\."
    r")\b|"
    r"\bas\s+well\s+as\s+The\s+temporal\s+characteristics\b|"
    r"\bsmall\s+animals\s+imaging\s+In\s+summary\b|"
    r"\b\[071\]\s+This\b",
    re.IGNORECASE,
)
ESCAPED_SUP_FOOTNOTE_RE = re.compile(r"&\s*lt;sup>\s*[A-Za-z0-9]\b", re.IGNORECASE)
REFERENCES_BACKMATTER_INTERLEAVE_RE = re.compile(
    r"\bETHICS\s+STATEMENT\b[\s\S]{0,1200}\bREFERENCES\b[\s\S]{0,3500}"
    r"\bUniversity\s+of\s+Bath\b[\s\S]{0,1000}\bAUTHOR\s+CONTRIBUTIONS\b",
    re.IGNORECASE,
)
SPLIT_DOT_EMAIL_RE = re.compile(
    r"\b(?-i:[a-z]{2,})\.\s+[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|"
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\s*\.\s+|\s+\.\s*)[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
SPLIT_AT_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@\s+[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
SPLIT_DOT_EMAIL_SENTENCE_WORDS = {
    "addressed",
    "author",
    "authors",
    "contact",
    "correspondence",
    "email",
}


def _split_dot_email_is_sentence_boundary(match: re.Match[str]) -> bool:
    matched = match.group(0)
    dot_pos = matched.find(".")
    at_pos = matched.find("@")
    if dot_pos < 0 or (at_pos >= 0 and at_pos < dot_pos):
        return False
    leading_word = re.match(r"\b([A-Za-z]{2,})\.\s+", matched)
    return bool(leading_word and leading_word.group(1).lower() in SPLIT_DOT_EMAIL_SENTENCE_WORDS)


def _find_split_dot_email_match(text: str) -> re.Match[str] | None:
    for match in SPLIT_DOT_EMAIL_RE.finditer(text):
        if not _split_dot_email_is_sentence_boundary(match):
            return match
    return None


OLD_SCAN_OCR_GIBBERISH_RE = re.compile(
    r"\bLUMBAH\s+I\s+-\s+i\b|"
    r"\(\s*!I\s+G\s*:\.\s*nosis\b|"
    r"\blan\.~r\s+tl!\b|\bresult\s+t\s+L\s+'\s+n\b|\bmuschnr\b|"
    r"\bv&me\b|\bTVRP\b|\bpleak\s+flow\b|\bS\s+-'\b|"
    r"\btimulus\b|\bmesc\b|\bU-W\s+vertebrae\b|\b4y6-8\b|"
    r"\bVesicaf\b|\bJ\s+Ural\b|\bsnine\b|\bGvnecol\b|"
    r"@e3\)|\borolanse\b|\bI\s+Bone\s+Point\s+Sure\b|\bBvadley\b|"
    r"\bsuiprising\b|\bforiTi\b|\bstimulus\.d/T\./Sz\b|\belTicacy\b|"
    r"\bkcounl/mg\s+prolan\b|\bLndferase\b|\bdetermitied\b|"
    r"\biiiiegfiited\b|\blummesceoce\b|\blinearmotor\s+S~pole\s+aller\b|"
    r"\bMu&es\b|\bHaiiy\b|\bCruc\$xion\b|\bP\s+to\s+bc\b|"
    r"\bIt\s+isl\b|\b(?-i:aJways)\b|\bdemonstrale\b|\benor[\u00b7\s-]+mous\b|"
    r"\b(?-i:riSing)\b|\bproperty\s+center\b|\bcharaCleriza[\u00b7\s-]+lion\b|"
    r"\bLlnhof\s+Master\s+Te<:hnlka\b|\bUnhol\s+Kafdan\s+Mastel\s+TL\b|"
    r"\bI-SlOP\b|\binli\s+nily\b|\bout\s+of\s+locus\b|\bScheimplJug\b|"
    r"\bcompanson\s+ShOIS\b|\bparticularimagedislance\b|"
    r"\bIndMdual\s+OUlldlngs\b|\bgelloreground\b|\bsubjecl\b|"
    r"\bslreellevel\b|\beleminate\b|\bpocIure\b|\bsufiicient\b|"
    r"\bmillimelers\b|\bspecificions\b|\baillinhof-supplied\b|"
    r"\b(?:Uroflowrnetry|uroflowrneter|RotCDTleter|PsyahoZogiaaZ|"
    r"Gra1Jimetry|(?-i:OVerfLow)|ResiduaZ|bZood|MuZtiphasicity|"
    r"estabZishment|variabZes|abiZities|A!Jstract|vuiation|"
    r"measwe)\b|"
    r"\bprinaip\s+Ze\b|\bmeaszu'ing\b|\bfww-cion\b|\bcontin,Ious\b|"
    r"\bDruck/Fiow\b",
    re.IGNORECASE,
)
SPLIT_URL_DOMAIN_RE = re.compile(
    r"\bwww\.\s+[A-Za-z]{2,}\s+[A-Za-z](?:\.[A-Za-z]{2,})+\b|"
    r"\bwww\.[A-Za-z0-9-]+\s+\.\s+[A-Za-z]{2,}\b|"
    r"\bwww\.[A-Za-z0-9-]+(?:\s+[A-Za-z0-9-]+)+\.[A-Za-z]{2,}\b|"
    r"\bhttps?://[A-Za-z0-9-]+\s+\.\s+[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
BIBLIOGRAPHY_NUMBERING_RESIDUE_RE = re.compile(
    r"\b20\.\s+20\s+van\s+Tulder\b|"
    r"\b3[34]\.\s+3[23]\s+(?:De\s+Nunzio|G(?:u|Гј)zelsoy)\b|"
    r"\bmagnetic\s+resonance\s+82\.\s+imaging\s+volume\s+estimation\b|"
    r"\b39\.\s+Sub-committee[\s\S]{0,260}\b39\.\s+Haylen\b|"
    r"\bMedical\s+management\s+3\.\s+of\s+benign\s+prostatic\s+hyperplasia\b|"
    r"\bfindings\s+and\s+17\.\s+postvoiding\s+residual\s+urine\b|"
    r"\bpost-void\s+residual\s+20\.\s+urine\s+volume\b|"
    r"\bA\s+Comprehensive\s+Review\s+4\.\s+Emphasizing\s+Anatomy\b|"
    r"\bUrethral\s+Stricture\s+Recurrence\s+21\.\s+After\s+Anterior\s+Urethroplasty\b|"
    r"\bChallenges\s+and\s+Opportunities,\s+Jeddah\s+28\.\s+Khorsheed\b|"
    r"\bProceedings\s+of\s+the\s+2023\s+ACM\s+31\.\s+International\s+Conference\b|"
    r"\b16\.\s+16Novadaq\b|"
    r"\b25\s+5\s+H\.\s+Li\b|\b100\s+39\s+Khokhlov\b|\b105\s+41\s+Y\.\s+Yan\b|"
    r"\bneuroimaging\s+76\.\s+Mondok\b|\b\(2020\)\.\s+van\s+Rijn\b|"
    r"\b281\.\s+Zhang[\s\S]{0,500}\b282\.\s+Buzs|\bGroupMorrell\s+MJ\b|"
    r"\bSuggestive\s+contours\s+for\s+conveying\s+shape\.\s+5\.\s+ACM\s+Transactions\b|"
    r"\bTouchPen[\s\S]{0,320}\b13\.\s+Cham\b|"
    r"\bTinne\s+Tuytelaars[\s\S]{0,320}\b36\.\s+Cham\b|"
    r"\b7\.\s+50\s+7\s+P\.\s+Greenspan\b|"
    r"\b11\.\s+55\s+10\s+X\.\s+He\b|"
    r"\b1468\.\s+1469\.\s+20\s+L\.\s+Wang\b|"
    r"\b1470\.\s+75\s+21\s+X\.\s+Chen\b|"
    r"\b1476\.\s+We\.\s+Liu\b",
    re.IGNORECASE,
)
PUBLISHER_RECOMMENDATION_BLOCK_RE = re.compile(
    r"\bYou\s+may\s+also\s+like\b[\s\S]{0,700}"
    r"(?:\bBecome\s+a\s+Multilingual\b|\bChArUco-based\s+3D\s+scanner\b|"
    r"\btolerable\s+impurity\s+concentrations\b)|"
    r"\bArticles\s+you\s+may\s+be\s+interested\s+in\b[\s\S]{0,700}"
    r"\bMagnetic\s+resonance-guided\s+near-infrared\s+tomography\s+of\s+the\s+breast\b|"
    r"\bFLORE\s+Repository\s+istituzionale[\s\S]{0,1500}\bArticle\s+begins\s+on\s+next\s+page\b|"
    r"\bUniversity\s+of\s+Groningen[\s\S]{0,1200}\bIMPORTANT\s+NOTE\b|"
    r"\bDownloaded\s+from\s+the\s+University\s+of\s+Groningen/UMCG\s+research\s+database\b|"
    r"\bwww\.forgottenbooks\.com\b|"
    r"\bTHIS\s+PAGE\s+IS\s+LOCKED\s+TO\s+FREE\s+MEMBERS\b|"
    r"\bPurchase\s+full\s+membership\s+to\s+immediately\s+unlock\s+this\s+page\b|"
    r"\bOver\s+2,000\s+years\s+of\s+human\s+knowledge\b",
    re.IGNORECASE,
)
AFFILIATION_MARKER_RESIDUE_RE = re.compile(
    r"\bYary\s+Volpe1\b|\b(?:Ilbey|İlbey)\s+1\s+1\s+2\s+3\s+1\s+1\b|"
    r"\bLujain\s+Al\s+Omari1\b|"
    r"\bEva\s+M\.\s+Sevick-Murac\s+aa\)|"
    r"\bS\.V\.\s+Krishna\s+Reddy\s+pa\s+and\s+Ahammad\s+Basha\s+Shaik\s+pb\s+a\s+Department\b|"
    r"\bMingyue\s+Xue,\s+ab\s+Mengbing\s+Zou[\s\S]{0,120}"
    r"\bZhihua\s+Zhan\s+Ab\s+and\s+Shulin\s+Zhao\s+Zhao\b|"
    r"\b(?:Zhen\s+Ling\s+Teo|Robert\s+J\.\s+T\.\s+Morris)\s+\u00a9\s+\d",
    re.IGNORECASE,
)
PDF_LINE_NUMBER_RESIDUE_RE = re.compile(
    r"\bJournal\s+of\s+Materials\s+Chemistry\s+B\s+Accepted\s+Manuscrip\b"
    r"[\s\S]{0,5000}?"
    r"\b(?:with\s+20\s+the\s+sizes|been\s+25\s+reported|"
    r"Fresh\s+lychee\s+was\s+purchased|All\s+measurements\s+were\s+performed|"
    r"_\{75\}\s+incubated|95\s+The\s+morphology|20\s+analytical\s+chemistry|"
    r"100\s+39\s+Khokhlov|105\s+41\s+Y\.\s+Yan)\b|"
    r"\bAccepted\s+Manuscript\b[\s\S]{0,5000}?"
    r"\b(?:excellent\s+10\s+contrast|minimal\s+15\s+autofluorescence|"
    r"20\s+photobleaching|25\s+development|30\s+dyes|35\s+resulting|"
    r"45\s+developed|60\s+illustrated|75\s+fabricated|85\s+nanomicelles|"
    r"100\s+As\s+shown|Key\s+25\s+Technologies)\b",
    re.IGNORECASE,
)
BOX_UNIT_RE = re.compile(
    r"<div\b(?=[^>]*\bz2m-box-unit\b)[^>]*>(?P<body>.*?)</div>",
    re.IGNORECASE | re.DOTALL,
)
FIGURE_UNIT_RE = re.compile(
    r"<div\b(?=[^>]*\bz2m-figure-unit\b)(?=[^>]*\bid\s*=\s*['\"](?P<id>fig-[^'\"]+)['\"])[^>]*>"
    r"(?P<body>.*?)</div>",
    re.IGNORECASE | re.DOTALL,
)
IMMEDIATE_EXTERNAL_FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:<p\b[^>]*>(?:(?!</p>)[\s\S])*<img\b(?:(?!</p>)[\s\S])*</p>\s*)?"
    r"<p\b[^>]*\bz2m-figure-caption\b[^>]*>(?P<body>.*?)</p>",
    re.IGNORECASE | re.DOTALL,
)
FIGURE_CAPTION_NODE_RE = re.compile(
    r"<(?:p|h[1-6])\b(?=[^>]*\bz2m-figure-caption\b)[^>]*>(?P<body>.*?)</(?:p|h[1-6])>",
    re.IGNORECASE | re.DOTALL,
)
TABLE_DOI_APPEND_RE = re.compile(
    r"https?://doi\.org/10\.[^\s<]+\.t\d+\s+"
    r"(?P<tail>(?:[a-z]|\(?[a-z])[\s\S]{20,220})",
    re.IGNORECASE,
)
DOI_SPLIT_PLAIN_RE = re.compile(r"\bdoi:\s*10\.\d{4,9}/\s+[A-Za-z0-9]", re.IGNORECASE)
GERMAN_SOURCE_HINT_RE = re.compile(
    r"\b(?:AUSF|AUSFUEHRLICHES|AUSFUHRLICHES|PHOTOGRAPHIE|KOLLODIUM|"
    r"KOLLODIUMVERFAHREN|DRITTE|AUFLAGE|DRESDEN|WISS|PHOTOGR|INSTITUT|"
    r"TECHNICHE|SHULE|WISSEN|KALI|SALPETER|KUPFERVITRIOL|MASTIX|BORAX|"
    r"WASSER|VERLAG|KAPITEL|LEITTHEMA|DEUTSCHE|LEITLINIEN|DIAGNOSTIK|"
    r"PROSTATASYNDROMS|ZUSAMMENFASSUNG|UROLOGE|KLINIK|UND|DER|DIE|DAS|MIT)\b",
    re.IGNORECASE,
)
MIXEDCASE_VAR_FOOTNOTE_RE = re.compile(
    r"\b(?:Qma|Qa|Qav|Qmn)<sup\b[^>]*\bz2m-table-fn\b[^>]*>\s*[A-Za-z]+\s*</sup>",
    re.IGNORECASE,
)
WORD_FOOTNOTE_SPLIT_RE = re.compile(
    r"\b(?P<prefix>[^\W\d_]{3,})<sup\b[^>]*\bz2m-table-fn\b[^>]*>"
    r"\s*(?P<suffix>i|v|x|vi|ix)\s*</sup>",
    re.IGNORECASE,
)
SUSPICIOUS_FOOTNOTE_WORD_MERGES = {
    "multi",
    "complex",
    "index",
    "matrix",
    "max",
    "neurotox",
    "plex",
    "fix",
    "neurx",
    "revi",
    "curonix",
    "mastix",
    "borax",
}
AUTHOR_YEAR_TEXT_RE = re.compile(
    r"\b[A-Z][A-Za-z'’.-]+(?:\s+et\s+al\.)?(?:,\s*|\s+)\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
AUTHOR_YEAR_STYLE_TEXT_RE = re.compile(
    r"\b"
    r"[A-Z][A-Za-z'\u2019.-]+"
    r"(?:\s+(?:et\s+al\.?|and\s+[A-Z][A-Za-z'\u2019.-]+|&\s*[A-Z][A-Za-z'\u2019.-]+))?"
    r"(?:,\s*|\s+)\(?\d{4}[a-z]?\)?",
    re.IGNORECASE,
)
FLATTENED_SUP_CITATION_RE = re.compile(
    r"\b(?:et\s+al\.?\s*|[A-Za-z]{5,}\.)(?P<num>\d{1,3})(?!\s*\d)(?=[\s,.;)])",
    re.IGNORECASE,
)
COMMA_DECIMAL_REF_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<left>\d{1,3})['\"][^>]*>\s*(?P=left)\s*</a>"
    r"\s*,\s*"
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<right>\d{1,3})['\"][^>]*>\s*(?P=right)\s*</a>",
    re.IGNORECASE,
)
SUPPLEMENTARY_FIGURE_LABEL_RE = re.compile(
    r"^\s*(?:Supplementary|Supplemental|Suppl\.?)\s+"
    r"(?:Fig(?:ure)?\.?|Figure)\s+(?:S\s*)?\d{1,3}[A-Za-z]?\b",
    re.IGNORECASE,
)
TABLE_REF_PARTIAL_LINK_RE = re.compile(
    r"\bTables?\s+<a\b[^>]*\bhref\s*=\s*['\"]#table-(?P<target>\d+)['\"][^>]*>"
    r"\s*(?P<label>\d+)\s*</a>",
    re.IGNORECASE | re.DOTALL,
)
FIGS_REF_FALSE_REF_RE = re.compile(r"\bFigs?\.?\s+\d+(?:\s+and|\s*,)?\s*$", re.IGNORECASE)
SINGLE_STAT_REF_RE = re.compile(
    r"\b(?:sample\s+size|G\*Power|allocation\s+ratio|effect\s+size)\b"
    r"[\s\S]{0,180}?<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<num>\d{1,3})['\"][^>]*>"
    r"\s*(?P=num)\s*</a>",
    re.IGNORECASE,
)
STAT_NUMERIC_CONTEXT_RE = re.compile(
    r"\b(?:sample\s+size|G\*Power|allocation\s+ratio|effect\s+size|"
    r"statistical\s+power|power\s+analysis)\b",
    re.IGNORECASE,
)
MATH_OR_MEASUREMENT_RANGE_CONTEXT_RE = re.compile(
    r"(?:\\\[|\\\(|"
    r"\b(?:anova|array|arrays|class|classes|coordinate|coordinates|equation|eq\.?|"
    r"formula|glm|heatmap|interval|intervals|likelihood|matrix|median|parameter|"
    r"parameters|probability|range|scale|score|scores|threshold|vector|"
    r"values?)\b|"
    r"[=<>]|[\u00b0\u03bc\u03c0\u03c3\u03c4\u03a6\u2208\u2211\u2212\u2217"
    r"\u2219\u2223\u223c\u2248\u25e6])",
    re.IGNORECASE,
)
NON_CITATION_BRACKET_RANGE_CONTEXT_RE = re.compile(
    r"\b(?:amplitude|array|arrays|bounds?|class\s+scores?|coordinate|coordinates|"
    r"current|dimension|dimensions|electrode\s+values?|feature|heatmap|input|"
    r"interval|intervals|layer|layers|likelihood|map\s+size|matrix|median|"
    r"normalization|normalized|output|parameters?|pixel|points?|probability|range|"
    r"random\s+number|scale|score|scores|sigmoid|starting|STAI|threshold|values?|"
    r"vector|vectors|VAS)\b|"
    r"[=<>∈∑]",
    re.IGNORECASE,
)
TABLE_CAPTION_ID_RE = re.compile(
    r"<p\b(?=[^>]*\bid\s*=\s*['\"]table-(?P<num>\d+)['\"])[^>]*>"
    r"(?P<body>.*?)</p>",
    re.IGNORECASE | re.DOTALL,
)
TABLE_WRAPPER_ID_RE = re.compile(
    r"<div\b(?=[^>]*\bid\s*=\s*['\"]table-(?P<num>\d+)['\"])(?=[^>]*\bz2m-table-unit\b)[^>]*>",
    re.IGNORECASE | re.DOTALL,
)


_REFERENCE_BOUNDARY_START_RE = re.compile(
    r"\b(?P<num>\d{1,4})\.\s+"
    r"(?P<name>[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]{1,40})"
)


def _bibliography_numbering_residue_is_clean_reference_boundary(
    polish_html: str,
    residue: str,
) -> bool:
    starts = [
        (int(match.group("num")), match.group("name"))
        for match in _REFERENCE_BOUNDARY_START_RE.finditer(residue)
    ]
    if not starts:
        return False
    for number, name in starts:
        li_match = re.search(
            rf"<li\b(?=[^>]*\bid\s*=\s*['\"]ref-{number}['\"])[^>]*>"
            rf"(?P<body>[\s\S]{{0,1200}}?)</li>",
            polish_html,
            re.IGNORECASE,
        )
        if li_match is None:
            return False
        li_text = _strip_tags(li_match.group("body"))
        if re.search(rf"\b{number}\.\s+{re.escape(name)}", li_text) is None:
            return False
    return True


def _source_pdf_text_confirms_float_gap(left_text: str, right_text: str, pdf_text: str) -> bool:
    """Return true when the source PDF text layer has float material between fragments."""
    if not pdf_text.strip():
        return False
    left_diag = _diagnostic_text(left_text)
    right_word_diag = _diagnostic_word_text(right_text)
    pdf_diag = _diagnostic_text(pdf_text)
    pdf_word_diag = _diagnostic_word_text(pdf_text)
    if (
        "this feature makes these coils" in left_diag
        and "positive depending" in right_word_diag
        and "table 1" in pdf_diag
        and "negative or" in pdf_diag
    ):
        return True
    if (
        "no tumors developed in either" in left_diag
        and "sham or field exposed animals" in right_word_diag
        and "figure 7" in pdf_word_diag
    ):
        return True
    left_words = _diagnostic_words(left_text)[-9:]
    right_words = _diagnostic_words(right_text)[:9]
    if len(left_words) < 3 or len(right_words) < 3:
        return False

    pdf_words_text = pdf_word_diag
    left_match = _word_sequence_match(pdf_words_text, left_words)
    if left_match is None and len(left_words) > 5:
        left_words = left_words[-5:]
        left_match = _word_sequence_match(pdf_words_text, left_words)
    if left_match is None:
        return False

    right_match = _word_sequence_match(pdf_words_text, right_words, start=left_match.end())
    if right_match is None and len(right_words) > 5:
        right_words = right_words[:5]
        right_match = _word_sequence_match(pdf_words_text, right_words, start=left_match.end())
    if right_match is None:
        return False
    if right_match.start() - left_match.end() > 12000:
        return False

    between = pdf_words_text[left_match.end() : right_match.start()]
    if len(_diagnostic_words(between)) < 3:
        return False
    return bool(
        re.search(
            r"\b(?:fig(?:ure)?|table)\s+\d+[a-z]?\b|"
            r"\b(?:path\s+taken|directed\s+navigation|game|jewel|player|monster|exit|control)\b",
            between,
            re.IGNORECASE,
        )
    )


def _source_pdf_path(raw_path: Path) -> Path:
    return source_pdf_path(raw_path, pdf_source_stage=PDF_SOURCE_STAGE)


def _pdf_citation_link_summary(pdf_path: Path, *, sample_limit: int = 12) -> dict[str, Any]:
    return pdf_citation_link_summary(
        pdf_path,
        author_year_text_re=AUTHOR_YEAR_TEXT_RE,
        sample_limit=sample_limit,
    )


def _load_pdf_diagnostic_text(
    raw_path: Path,
    pdf_text_override: str | None,
    pdf_path_override: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    return load_pdf_diagnostic_text(
        raw_path,
        pdf_text_override,
        pdf_source_stage=PDF_SOURCE_STAGE,
        pdf_path_override=pdf_path_override,
        extract_pdf_text_func=_extract_pdf_text,
    )


class PdfDiagnosticsCache(_PackagePdfDiagnosticsCache):
    def __init__(self, cache_dir: Path) -> None:
        def link_summary_adapter(
            pdf_path: Path,
            *,
            author_year_text_re: re.Pattern[str],
            sample_limit: int,
        ) -> dict[str, Any]:
            del author_year_text_re
            return _pdf_citation_link_summary(pdf_path, sample_limit=sample_limit)

        super().__init__(
            cache_dir,
            pdf_source_stage=PDF_SOURCE_STAGE,
            extract_pdf_text_func=_extract_pdf_text,
            pdf_citation_link_summary_func=link_summary_adapter,
            author_year_text_re=AUTHOR_YEAR_TEXT_RE,
            author_year_cache_key="AUTHOR_YEAR_TEXT_RE:v1",
        )


def _defect(
    *,
    defect_id: str,
    cc_class: str,
    check: str,
    severity: str,
    block: Block | None,
    snippet: str,
    stage: str,
    hypothesis: str,
    proposed_fix_layer: str,
    regression_test: str,
    extra: dict[str, Any] | None = None,
) -> Defect:
    return make_defect(
        defect_id=defect_id,
        cc_class=cc_class,
        check=check,
        severity=severity,
        block=block,
        snippet=snippet,
        stage=stage,
        hypothesis=hypothesis,
        proposed_fix_layer=proposed_fix_layer,
        regression_test=regression_test,
        extra=extra,
    )


def _nearby_image_offsets(blocks: list[Block], index: int, *, label: str | None = None, window: int = 8) -> list[int]:
    return _nearby_image_offsets_base(
        blocks,
        index,
        label=label,
        window=window,
        looks_like_figure_caption=_looks_like_figure_caption,
    )


def _classify_missing_figure_warning(
    warning: Block,
    polish_blocks: list[Block],
) -> dict[str, Any]:
    return _classify_missing_figure_warning_base(
        warning,
        polish_blocks,
        looks_like_figure_caption=_looks_like_figure_caption,
    )


def _ref_match_inside_sentence_final_superscript(raw: str, start: int, end: int) -> bool:
    sup_open = raw.rfind("<sup", 0, start)
    if sup_open < 0:
        return False
    prior_sup_close = raw.rfind("</sup", 0, start)
    if prior_sup_close > sup_open:
        return False
    sup_close = raw.find("</sup>", end)
    if sup_close < 0:
        return False
    before_text = _strip_tags(raw[max(0, sup_open - 96) : sup_open]).rstrip()
    if not before_text or before_text[-1] not in ".!?)]":
        return False
    sup_body = raw[sup_open : sup_close + len("</sup>")]
    if not re.search(r'\bhref\s*=\s*["\']#ref-\d+["\']', sup_body, re.IGNORECASE):
        return False
    after_text = _strip_tags(raw[sup_close + len("</sup>") : sup_close + len("</sup>") + 96]).lstrip()
    return not after_text or bool(re.match(r"(?:[A-Z]|\(|\[|,|;|:)", after_text))


def _ref_match_inside_author_et_al_citation(raw: str, start: int, end: int) -> bool:
    left_text = _strip_tags(raw[max(0, start - 96) : start]).rstrip()
    return re.search(r"\bet\s+al\.?\s*$", left_text, re.IGNORECASE) is not None


def _ref_match_is_parenthetical_tail_citation(raw: str, start: int, end: int) -> bool:
    anchor_end = raw.find("</a>", end, min(len(raw), end + 160))
    if anchor_end < 0:
        return False
    anchor_visible = _normalize_ws(_strip_tags(raw[start : anchor_end + len("</a>")]))
    if re.fullmatch(r"\)\s*\d{1,4}\s*\.?", anchor_visible) is None:
        return False
    right_text = _strip_tags(raw[anchor_end + len("</a>") : anchor_end + len("</a>") + 32]).lstrip()
    return not right_text or right_text[0] in ".,;)]"


def _block_looks_like_author_affiliation_byline(block: Block) -> bool:
    text = _normalize_ws(block.text)
    if len(text) > 1200:
        return False
    degree_hits = len(re.findall(r"\b(?:M\.D|Ph\.?D|F\.R\.C\.S|B\.Sc|M\.Sc)\.?", text, re.IGNORECASE))
    short_ref_hits = len(re.findall(r"(?:^|[\s,])\d{1,2}(?=\s|,|$)", text))
    return degree_hits >= 4 and short_ref_hits >= 4


def _ref_visible_number_from_anchor(raw: str, start: int, end: int) -> tuple[int | None, int]:
    anchor_end = raw.find("</a>", end, min(len(raw), end + 200))
    if anchor_end < 0:
        return None, end
    label = _normalize_ws(_strip_tags(raw[start : anchor_end + len("</a>")]))
    number = _ref_anchor_visible_number(label)
    return number, anchor_end + len("</a>")


def _ref_match_is_month_word_citation(raw: str, start: int, end: int) -> bool:
    number, anchor_end = _ref_visible_number_from_anchor(raw, start, end)
    if number is None or number <= 12:
        return False
    left_text = _strip_tags(raw[max(0, start - 64) : start]).rstrip()
    right_text = _strip_tags(raw[anchor_end : anchor_end + 32]).lstrip()
    return re.search(r"\bmonth\s*$", left_text, re.IGNORECASE) is not None and (
        not right_text or right_text[0] in ".,;:)]"
    )


def _ref_match_is_measurement_parenthetical_citation(raw: str, start: int, end: int) -> bool:
    number, anchor_end = _ref_visible_number_from_anchor(raw, start, end)
    if number is None:
        return False
    left_text = _strip_tags(raw[max(0, start - 140) : start])
    right_text = _strip_tags(raw[anchor_end : anchor_end + 48]).lstrip()
    if not right_text.startswith(")"):
        return False
    left_paren = left_text.rfind("(")
    right_paren = left_text.rfind(")")
    if left_paren < 0 or right_paren > left_paren:
        return False
    parenthetical = left_text[left_paren:]
    return bool(re.search(r"(?:%|mL\s*/\s*s|mL\s+s|mmHg|cmH2O|L\s*/\s*s)", parenthetical, re.IGNORECASE))


def _ref_match_follows_figure_or_unit_parenthetical_citation(raw: str, start: int, end: int) -> bool:
    number, anchor_end = _ref_visible_number_from_anchor(raw, start, end)
    if number is None:
        return False
    left_text = _strip_tags(raw[max(0, start - 260) : start]).rstrip()
    right_text = _strip_tags(raw[anchor_end : anchor_end + 48]).lstrip()
    if not left_text.endswith(")"):
        return False
    if right_text and right_text[0] not in ".,;:)]":
        return False
    right_paren = left_text.rfind(")")
    left_paren = left_text.rfind("(", 0, right_paren)
    if left_paren < 0:
        return False
    parenthetical = left_text[left_paren : right_paren + 1]
    return bool(
        re.search(r"\b(?:Fig|Figure)\.?\s*\d", parenthetical, re.IGNORECASE)
        or re.search(
            r"(?:%|mL\s*/\s*s|mL\s+s|mmHg|cmH2O|L\s*/\s*s|N\s*m\s*2|"
            r"(?:u|Вµ|Ој|μ)m\s*2|mm\s*2|cm\s*2)",
            parenthetical,
            re.IGNORECASE,
        )
    )


def _ref_match_inside_animal_human_study_citation(raw: str, start: int, end: int) -> bool:
    window = _normalize_ws(_strip_tags(raw[max(0, start - 320) : min(len(raw), end + 320)]))
    return bool(
        re.search(
            r"\banimal\s*\d{1,3}\s+and\s+human\s+studies\s+of\s+retinal\s*\d{1,3}"
            r"(?:\s*,\s*\d{1,3})?\s+and\s+cortical\s*\d{1,3}\s+stimulat\w*",
            window,
            re.IGNORECASE,
        )
        or re.search(r"\breport\s+\d{1,3}\s+by\s+that\s+group\b", window, re.IGNORECASE)
    )


def _linked_ref_near_non_citation_context(block: Block) -> bool:
    if _block_looks_like_author_affiliation_byline(block):
        return False
    for match in REF_LINK_RE.finditer(block.raw):
        if _ref_match_inside_bracketed_numeric_citation(block.raw, match.start(), match.end()):
            continue
        if _ref_match_inside_sentence_final_superscript(block.raw, match.start(), match.end()):
            continue
        if _ref_match_inside_author_et_al_citation(block.raw, match.start(), match.end()):
            continue
        if _ref_match_is_parenthetical_tail_citation(block.raw, match.start(), match.end()):
            continue
        if _ref_match_is_month_word_citation(block.raw, match.start(), match.end()):
            continue
        if _ref_match_is_measurement_parenthetical_citation(block.raw, match.start(), match.end()):
            continue
        if _ref_match_follows_figure_or_unit_parenthetical_citation(block.raw, match.start(), match.end()):
            continue
        if _ref_match_inside_animal_human_study_citation(block.raw, match.start(), match.end()):
            continue
        window_raw = block.raw[max(0, match.start() - 48): match.end() + 80]
        window_text = _strip_tags(window_raw)
        context_text = re.sub(r"\bD\d-type\b", "D-type", window_text, flags=re.IGNORECASE)
        if re.search(r"\b[A-Za-z0-9]+-D\d+\s+\d{1,3}\b", context_text):
            continue
        if NONCITATION_CONTEXT_RE.search(context_text) or ML_PER_SECOND_CONTEXT_RE.search(context_text):
            return True
    return False


def _block_is_float_or_table_context(block: Block) -> bool:
    if block.id.lower().startswith(("fig-", "table-", "box-")):
        return True
    if block.classes & {
        "z2m-figure-caption",
        "z2m-figure-unit",
        "z2m-table-caption",
        "z2m-table-unit",
        "z2m-box-caption",
        "z2m-box-unit",
        "z2m-missing-figure-warning",
    }:
        return True
    return bool(re.match(r"^\s*(?:TABLE|Table|FIG(?:URE)?|Fig(?:ure)?\.?)\s+\d", block.text))


def _reference_target_numbers(html: str) -> set[int]:
    return {int(number) for number in re.findall(r"\bid\s*=\s*['\"]ref-(\d+)['\"]", html, re.IGNORECASE)}


def _is_supplementary_figure_block(block: Block) -> bool:
    return block.id.lower().startswith("fig-supplementary-") or SUPPLEMENTARY_FIGURE_LABEL_RE.match(block.text) is not None


def _non_reference_body_blocks(blocks: list[Block]) -> Iterable[Block]:
    references_started = False
    for block in blocks:
        if REFERENCES_HEADING_RE.match(block.text):
            references_started = True
        if _is_references_block(block, references_started):
            continue
        if block.classes & {"z2m-front-matter", "z2m-affiliations", "z2m-footnote"}:
            continue
        yield block


def _ref_anchor_visible_number(label: str) -> int | None:
    numbers = re.findall(r"\d+", label)
    if len(numbers) != 1:
        return None
    return int(numbers[0])


def _ref_match_inside_bracketed_reference_list(raw: str, start: int, end: int) -> bool:
    ref_anchor = re.search(r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+", raw[start:end], re.IGNORECASE)
    anchor_start = start + ref_anchor.start() if ref_anchor is not None else start
    left = raw.rfind("[", max(0, anchor_start - 240), anchor_start)
    if left < 0:
        return False
    right = raw.find("]", end, min(len(raw), end + 160))
    if right < 0:
        return False
    visible = _normalize_ws(_strip_tags(raw[left : right + 1]))
    return (
        re.fullmatch(
            r"\[\s*\d{1,4}(?:\s*(?:[,;]|[-\u2013\u2014]|\band\b)\s*\d{1,4})+\s*\]\.?",
            visible,
            re.IGNORECASE,
        )
        is not None
    )


def _ref_match_inside_bracketed_numeric_citation(raw: str, start: int, end: int) -> bool:
    ref_anchor = re.search(r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+", raw[start:end], re.IGNORECASE)
    anchor_start = start + ref_anchor.start() if ref_anchor is not None else start
    anchor_end = raw.find("</a>", end, min(len(raw), end + 160))
    if anchor_end >= 0:
        anchor_visible = _normalize_ws(_strip_tags(raw[start : anchor_end + len("</a>")]))
        if re.fullmatch(r"\[\s*\d{1,4}\s*\]\s*\.?", anchor_visible, re.IGNORECASE):
            return True
    left = raw.rfind("[", max(0, anchor_start - 240), anchor_start)
    if left < 0:
        return False
    right = raw.find("]", end, min(len(raw), end + 160))
    if right < 0:
        return False
    visible = _normalize_ws(_strip_tags(raw[left : right + 1]))
    return (
        re.fullmatch(
            r"\[\s*\d{1,4}(?:\s*(?:[,;]|[-\u2013\u2014]|\band\b)\s*\d{1,4})*\s*\]\s*\.?",
            visible,
            re.IGNORECASE,
        )
        is not None
    )


def _anchor_span_inside_match(raw: str, match: re.Match[str]) -> tuple[int, int]:
    anchor = REF_ANCHOR_BODY_RE.search(raw[match.start() : match.end()])
    if anchor is None:
        return match.start(), match.end()
    start = match.start() + anchor.start()
    return start, match.start() + anchor.end()


def _looks_like_sample_size_value_ref(raw: str, match: re.Match[str]) -> bool:
    anchor_start, anchor_end = _anchor_span_inside_match(raw, match)
    left_text = _strip_tags(raw[max(0, anchor_start - 240) : anchor_start])
    right_text = _strip_tags(raw[anchor_end : anchor_end + 100]).lstrip()
    if re.search(
        r"\bsample\s+size\b[^.;:]{0,160}\b(?:was|were|is|=|:)\s*$",
        left_text,
        re.IGNORECASE,
    ) is None:
        return False
    return (
        not right_text
        or re.match(
            r"^(?:[\.,;:)]|to\b|[-\u2010-\u2014]|\d|participants?\b|patients?\b|subjects?\b|controls?\b)",
            right_text,
            re.IGNORECASE,
        )
        is not None
    )


def _looks_like_comma_decimal_stat_ref(raw: str, match: re.Match[str]) -> bool:
    left_text = _strip_tags(raw[max(0, match.start() - 240) : match.start()])
    return re.search(
        r"(?:"
        r"\beffect\s+size\b[^.;:]{0,140}\b(?:was|were|is|of|=|:)\s*|"
        r"\ballocation\s+ratio\b[^.;:]{0,180}\b(?:was|were|is|of|=|:|G\*Power)\s*|"
        r"\bG\*Power\s*|"
        r"\bCohen(?:'s)?\s*d\s*=?\s*|"
        r"\blogMAR\s*|"
        r"\b(?:SD|SEM)\s*=?\s*"
        r")$",
        left_text,
        re.IGNORECASE,
    ) is not None


def _plain_bracket_range_is_likely_non_citation_math_or_measurement(text: str, match: re.Match[str]) -> bool:
    body = match.group(0)
    numbers = [int(value) for value in re.findall(r"\d+", body)]
    if not numbers:
        return False
    left = text[max(0, match.start() - 80) : match.start()]
    if re.search(
        r"\b(?:prior|previous|related|reported|study|studies|work|works|literature|"
        r"references?|refs?)\s*$",
        left,
        re.IGNORECASE,
    ):
        return False
    right = text[match.end() : match.end() + 80]
    window = text[max(0, match.start() - 180) : min(len(text), match.end() + 180)]
    if any(number == 0 for number in numbers):
        return True
    if re.match(r"\s*(?:%|[munpµμ]?A|[munpµμ]?m|V|Hz|s|ms|kg|N)\b", right):
        return True
    if re.search(r"\b(?:map\s+size|starting|ending|points?)\b", window, re.IGNORECASE):
        return True
    if len(numbers) >= 3 and NON_CITATION_BRACKET_RANGE_CONTEXT_RE.search(window):
        return True
    return (
        NON_CITATION_BRACKET_RANGE_CONTEXT_RE.search(window) is not None
        and _looks_like_math_or_measurement_range(text, match)
    )


def _plain_bracket_range_is_likely_non_citation_table_text(text: str, match: re.Match[str]) -> bool:
    body = match.group(0)
    if re.fullmatch(r"\[\s*(?:19|20)\d{2}\s*[-\u2013\u2014]\s*(?:19|20)\d{2}\s*\]", body):
        return True
    window = text[max(0, match.start() - 220) : min(len(text), match.end() + 220)]
    return bool(
        re.search(r"\b(?:search\s+statement|set\s+number|concept|ti,\s*ab|exp\s+OR)\b", window, re.IGNORECASE)
        and re.search(r"\[\s*(?:19|20)\d{2}\s*[-\u2013\u2014]\s*(?:19|20)\d{2}\s*\]", body)
    )


def _block_looks_like_math_or_measurement_range_context(block: Block) -> bool:
    text = block.text
    if STAT_NUMERIC_CONTEXT_RE.search(text):
        return True
    if re.search(r"\[\s*(?:0|[-\u2212])", text):
        return True
    return MATH_OR_MEASUREMENT_RANGE_CONTEXT_RE.search(text) is not None


def _looks_like_table_flattened_citation_context(text: str) -> bool:
    if len(re.findall(r"\bet\s+al\.?\s*\d{1,3}\b", text, re.IGNORECASE)) < 2:
        return False
    return re.search(
        r"\b(?:algorithm|category|curve|descriptors|efficiency|flow\s+rate|"
        r"indicator|normal|compressive|constrictive|precision|recall|"
        r"roc|score|smooth|tower-shaped)\b",
        text,
        re.IGNORECASE,
    ) is not None


def _flattened_sup_match_is_joined_figure_label(match: re.Match[str]) -> bool:
    return re.match(r"\b[A-Za-z]*(?:fig|figure)\.\d{1,3}\b", match.group(0), re.IGNORECASE) is not None


def _flattened_sup_match_is_doi_or_url_fragment(text: str, match: re.Match[str]) -> bool:
    window = text[max(0, match.start() - 180) : min(len(text), match.end() + 120)]
    return bool(
        re.search(r"https?://(?:dx\.)?doi\.org/10\.\d{4,9}/", window, re.IGNORECASE)
        or re.search(r"\bdoi\s*:?\s*10\.\d{4,9}/", window, re.IGNORECASE)
    )


def _looks_like_software_version_context(text: str, start: int) -> bool:
    left = text[max(0, start - 160):start]
    return (
        re.search(
            r"\b(?:python|pytorch|cuda|tensorflow|torch|matlab|opencv|numpy|scipy|driver)\s+"
            r"(?:driver\s+)?version\s*$|\bversion\s*$",
            left,
            re.IGNORECASE,
        )
        is not None
    )


def _sup_numeric_range_is_software_version(block: Block, match: re.Match[str]) -> bool:
    numbers = re.findall(r"\d{1,3}", match.group("body"))
    if len(numbers) < 2:
        return False
    visible_pattern = r"\s*,\s*".join(re.escape(number) for number in numbers)
    for text_match in re.finditer(visible_pattern, block.text):
        if _looks_like_software_version_context(block.text, text_match.start()):
            return True
    return False


def _has_unlinked_tagged_citation_range(block: Block) -> bool:
    for match in TAGGED_CITATION_RANGE_LIST_RE.finditer(block.raw):
        body = match.group("body")
        if "<" not in body or "z2m-ref-link" in body:
            continue
        visible = _strip_tags(body)
        if CITATION_RANGE_LIST_RE.fullmatch(f"[{visible}]") is not None:
            return True
    return False


def _has_unlinked_sup_numeric_range(block: Block) -> bool:
    for match in SUP_NUMERIC_RANGE_RE.finditer(block.raw):
        if "z2m-ref-link" not in match.group(0):
            if _sup_numeric_range_is_software_version(block, match):
                continue
            return True
    return False


def _unlinked_citation_range_kind(block: Block) -> str:
    return _unlinked_citation_range_kind_base(
        block,
        looks_like_float_or_caption=_looks_like_float_or_caption,
        block_looks_like_frontmatter_affiliation_table=_block_looks_like_frontmatter_affiliation_table,
    )


def _unlinked_citation_candidate_numbers(block: Block) -> list[int]:
    return _unlinked_citation_candidate_numbers_base(block)


def _looks_like_figure_prose_reference_text(text: str) -> bool:
    figure_label = (
        r"(?:\d+(?:[.\-\u2010-\u2014]\d+)*(?:[A-Za-z](?:\s*,\s*[A-Za-z])?)?|"
        r"\d+\s*\([A-Za-z]\))"
    )
    if re.match(
        rf"^\s*(?:Figure|Fig\.?|FIGURE)\s+{figure_label}\s*(?:[,.;:]\s*)?"
        r"(?:visually\s+)?(?:provides?|depicts?|is|are|was|were|demonstrates?|summari[sz]es?|"
        r"shows?|showcases?|illustrates?|represents?|presents?|plots?|visuali[sz]es?|displays?|"
        r"maps?|describes?|examines?|suggests?|validates?|details?|exemplif(?:y|ies)|reveals?|"
        r"highlights?|contrasts?|compares?)\b",
        text,
        re.IGNORECASE,
    ):
        return True
    if re.match(
        rf"^\s*(?:Figure|Fig\.?|FIGURE)\s+{figure_label}\s*"
        r"\(\s*(?:left|right|top|bottom|upper|lower|central|center|middle|"
        r"same|both|all|main|inset|side|front|back|first|second|third)"
        r"[\s\S]{0,80}\)\s+"
        r"(?:provides?|depicts?|is|are|shows?|illustrates?|represents?|presents?)\b",
        text,
        re.IGNORECASE,
    ):
        return True
    label_hits = re.findall(r"\b(?:Figure|Fig\.?|FIGURE)\s+\d", text, re.IGNORECASE)
    if len(label_hits) >= 2 and re.search(r"\b\d{1,4}\s+(?:Figure|Fig\.?|FIGURE)\s+\d", text, re.IGNORECASE):
        return True
    if re.fullmatch(r"\s*(?:Figure|Fig\.?|FIGURE)\s+\d+(?:[.\-\u2010-\u2014]\d+)*(?:[A-Za-z])?\s*\.?\s*", text, re.IGNORECASE):
        return True
    return False


def _looks_like_figure_caption(block: Block) -> bool:
    if block.id.startswith("fig-"):
        return True
    if FIG_CAPTION_RE.match(block.text) is None:
        return False
    if not (block.classes & {"z2m-figure-caption", "z2m-figure-target"}) and _looks_like_figure_prose_reference_text(block.text):
        return False
    if re.match(
        r"^\s*(?:Figure|Fig\.?|FIGURE)\s+\d+\s*"
        r"\(\s*(?:left|right|top|bottom|upper|lower|central|center|middle|"
        r"same|both|all|main|inset|side|front|back|first|second|third)"
        r"(?:\s+(?:and|or|/)?\s*(?:left|right|top|bottom|upper|lower|central|center|middle|"
        r"same|both|all|main|inset|side|front|back|first|second|third|panels?|panel|plots?|plot|images?|image))*"
        r"\s*\)\s+"
        r"(?:shows?|depicts?|illustrates?|examines?|suggests?|indicates?|presents?|represents?|validates?|details?|exemplif(?:y|ies))\b",
        block.text,
        re.IGNORECASE,
    ):
        return False
    if re.match(
        r"^\s*(?:Figure|Fig\.?|FIGURE)\s+\d+[A-Za-z]?\s*[\-\u2010-\u2014]\s*(?:\d+\s*)?[A-Za-z]\s+"
        r"(?:shows?|depicts?|illustrates?|examines?|suggests?|indicates?|presents?|represents?|validates?|details?|exemplif(?:y|ies))\b",
        block.text,
        re.IGNORECASE,
    ):
        return False
    return re.match(
        r"^\s*(?:Figure|Fig\.?|FIGURE)\s+\d+(?:[A-Za-z]|\s*\([A-Za-z]\)|\s+[A-Za-z](?=\s))?\s+"
        r"(?:shows|showed|showcases|illustrates|presents|contains|plots|visualizes|visualises|"
        r"displays|maps|describes|examines|suggests|validates|details|exemplifies|represents|reveals|highlights)\b",
        block.text,
        re.IGNORECASE,
    ) is None and re.match(
        r"^\s*(?:Figure|Fig\.?|FIGURE)\s+\d+(?:[A-Za-z]|\s*\([A-Za-z]\)|\s+[A-Za-z](?=\s))?"
        r"\s+(?:and|or|,|&)\s+[A-Za-z]\s+(?:shows?|depicts?|illustrates?|examines?|suggests?|validates?|details?|exemplif(?:y|ies))\b",
        block.text,
        re.IGNORECASE,
    ) is None


def _figure_caption_number_from_caption_node(raw_body: str) -> int | None:
    text = _strip_tags(raw_body)
    match = re.match(r"\s*(?:Fig\.?|Figure|FIGURE)\s+(\d+)\b(?P<tail>[\s\S]*)$", text, re.IGNORECASE)
    if match is None:
        return None
    tail = match.group("tail").lstrip()
    if not tail or tail[:1] not in ".:|-":
        return None
    return int(match.group(1))


def _figure_caption_numbers_from_caption_node(raw_body: str) -> set[int]:
    text = _strip_tags(raw_body)
    label_re = re.compile(
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
    numbers: set[int] = set()
    for match in label_re.finditer(text):
        left_context = text[max(0, match.start() - 36):match.start()]
        if skip_left_context.search(left_context):
            continue
        numbers.add(int(match.group("num")))
    return numbers


def _figure_unit_allows_shared_image_alias(body: str, wrapper_num: int, unrelated: list[int]) -> bool:
    if not unrelated:
        return False
    image_count = len(re.findall(r"<img\b", body, re.IGNORECASE))
    if image_count < 1:
        return False
    float_alias_nums = {
        int(number)
        for number in re.findall(
            r"<span\b(?=[^>]*\bz2m-float-alias\b)[^>]*\bid\s*=\s*['\"]fig-(\d+)['\"]",
            body,
            re.IGNORECASE,
        )
    }
    caption_nums = {
        number
        for caption_match in FIGURE_CAPTION_NODE_RE.finditer(body)
        for number in _figure_caption_numbers_from_caption_node(caption_match.group("body"))
    }
    expected = set(unrelated)
    if not expected.issubset(float_alias_nums) or not expected.issubset(caption_nums):
        return False
    all_caption_nums = sorted(caption_nums | {wrapper_num})
    if image_count > len(all_caption_nums):
        return False
    return all_caption_nums == list(range(min(all_caption_nums), max(all_caption_nums) + 1))


def _looks_like_float_or_caption(block: Block) -> bool:
    return (
        block.has_figure_visual
        or bool(block.classes & {"z2m-float-unit", "z2m-figure-unit", "z2m-table-unit", "z2m-box-unit"})
        or block.tag in {"table", "figure", "figcaption"}
        or _looks_like_figure_caption(block)
        or TABLE_CAPTION_RE.match(block.text) is not None
    )


def _looks_like_float_note(block: Block) -> bool:
    text = block.text.strip()
    if not text:
        return True
    if len(text) <= 180 and re.match(
        r"^(?:\*|\ufffd|Values?\b|Median\b|Abbreviations?\b|doi:|https?://doi\.org/10\.)",
        text,
        re.IGNORECASE,
    ):
        return True
    return bool(len(text) <= 140 and re.match(r"^[A-Z]{2,8}\s*:", text))


def _ends_like_sentence_fragment(text: str) -> bool:
    text = text.strip()
    if len(text) < 24 or re.search(r"[.!?:;\]\)]\s*$", text):
        return False
    match = re.search(r"([A-Za-z][A-Za-z-]*)\s*$", text)
    if match is None:
        return False
    word = match.group(1)
    return word.islower() or word.lower() in {
        "and",
        "or",
        "with",
        "of",
        "the",
        "to",
        "for",
        "than",
        "daytime",
        "post-operative",
        "pre-operative",
    }


def _starts_like_sentence_continuation(text: str) -> bool:
    text = text.strip()
    return bool(re.match(r"^(?:[a-z]|\(?[a-z])", text))


def _looks_like_equation_continuation(block: Block) -> bool:
    if block.block_type.lower() == "equation":
        return True
    if "z2m-math-display" in block.raw:
        return True
    text = block.text.strip()
    return bool(re.match(r"^(?:\\[\[(]|[dD]\s*[tTV]\b|[A-Za-z]\s*=)", text))


def _page_link_semantic_kind(html: str, match: re.Match[str]) -> str | None:
    label = _strip_tags(match.group("body"))
    left = _strip_tags(html[max(0, match.start() - 140) : match.start()])
    right = _strip_tags(html[match.end() : match.end() + 140])
    left_tail = left[-80:]
    right_head = right[:80]
    context = f"{left_tail} {label} {right_head}"

    if re.search(r"\b(?:Box|Table|Tables|Fig\.?|Figure|Section|Appendix|Equation|Eq\.?)\s*$", left_tail, re.IGNORECASE):
        return "semantic-cross-reference"
    if re.match(r"^(?:Box|Table|Tables|Fig\.?|Figure|Section|Appendix|Equation|Eq\.?)\b", label, re.IGNORECASE):
        return "semantic-cross-reference"
    if re.match(r"^\(?S\d+", label, re.IGNORECASE) and re.match(r"^\s*Tables?\b", right_head, re.IGNORECASE):
        return "semantic-cross-reference"
    if re.search(r"\b(?:Table|Tables|Box|Section|Appendix|Figure|Fig\.?)\b", context, re.IGNORECASE) and re.search(
        r"\d|[A-Z]\.?", label
    ):
        return "semantic-cross-reference"
    if re.fullmatch(r"\[?\d{1,4}\]?[\].,;)]*", label):
        return "citation"
    if re.fullmatch(r"[a-z]\s*\d{1,4}(?:[\s,\-–\u2013\u2014\d.);]*)?", label):
        return "citation-ocr-glue"
    return None


def _reference_numbers_from_blocks(blocks: list[Block]) -> set[int]:
    numbers: set[int] = set()
    for block in blocks:
        id_match = re.match(r"^ref-(\d+)$", block.id, re.IGNORECASE)
        if id_match is not None:
            numbers.add(int(id_match.group(1)))
        for raw_match in re.finditer(r"\bid\s*=\s*['\"]ref-(\d+)['\"]", block.raw, re.IGNORECASE):
            numbers.add(int(raw_match.group(1)))
    return numbers


def _citation_defects(polish_blocks: list[Block], *, reference_blocks: list[Block] | None = None) -> list[Defect]:
    defects: list[Defect] = []
    references_started = False
    unlinked_range_candidates: dict[str, Block] = {}
    ref_numbers = _reference_numbers_from_blocks(reference_blocks or polish_blocks)
    footnote_numbers = {
        int(match.group(1))
        for block in polish_blocks
        for match in (re.match(r"^footnote-(\d+)$", block.id, re.IGNORECASE),)
        if match is not None
    }
    saw_false_positive = False
    saw_ocr_citation = False
    saw_latex_sup = False
    for block in polish_blocks:
        if REFERENCES_HEADING_RE.match(block.text):
            references_started = True
        if _is_references_block(block, references_started):
            continue
        if block.classes & {"z2m-front-matter", "z2m-affiliations", "z2m-footnote"}:
            continue
        if not saw_ocr_citation and OCR_CITATION_WORD_RE.search(block.text):
            defects.append(
                _defect(
                    defect_id="P32",
                    cc_class="CC-02/CC-14",
                    check="Likely OCR-corrupted superscript citation remains",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Marker recognized superscript citation numbers as words or ordinary numeric text.",
                    proposed_fix_layer="EN polish citation OCR recovery with reference-count/PDF evidence guards",
                    regression_test="Patterns such as 'task. Sec.' and 'flagship models 6,000' recover to citation links when references 58-60 exist.",
                )
            )
            saw_ocr_citation = True
        range_kind = _unlinked_citation_range_kind(block)
        if range_kind and range_kind not in unlinked_range_candidates:
            unlinked_range_candidates[range_kind] = block
        if not saw_latex_sup and LATEX_SUP_CITATION_RE.search(block.raw):
            defects.append(
                _defect(
                    defect_id="P28",
                    cc_class="CC-02/CC-05",
                    check="Citation-like LaTeX superscript remains in polish",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Citation-like math superscripts were generated after the citation conversion pass or skipped as math.",
                    proposed_fix_layer="EN polish post-math citation recovery",
                    regression_test="Inline math forms like \\(^{71-73}\\) become linked citation superscripts.",
                )
            )
            saw_latex_sup = True
        if not saw_false_positive and _linked_ref_near_non_citation_context(block):
            defects.append(
                _defect(
                    defect_id="P05",
                    cc_class="CC-02/CC-04",
                    check="Reference links appear in likely non-citation numeric context",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Broad numeric linkification may have linked units, labels, or scientific values.",
                    proposed_fix_layer="EN polish citation false-positive guards",
                    regression_test="pH, units, week/month labels, animal labels, and stimulus labels must remain unlinked.",
                )
            )
            saw_false_positive = True
    if "body" in unlinked_range_candidates:
        block = unlinked_range_candidates["body"]
        candidate_numbers = _unlinked_citation_candidate_numbers(block)
        missing_targets = [number for number in candidate_numbers if number not in ref_numbers]
        if not ref_numbers:
            defects.append(
                _defect(
                    defect_id="P04N",
                    cc_class="CC-02/CC-13",
                    check="Citation-like range/list has no bibliography targets to link",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Reference heading/list recognition failed, so citation parser cannot create valid #ref links.",
                    proposed_fix_layer="EN polish bibliography heading and reference-list detection",
                    regression_test="Citation ranges in articles with no recognized ref targets are classified separately from parser misses.",
                    extra={"quality_counted": False, "candidate_numbers": candidate_numbers},
                )
            )
        elif candidate_numbers and missing_targets:
            defects.append(
                _defect(
                    defect_id="P04R",
                    cc_class="CC-02/CC-13",
                    check="Citation-like range/list refers to missing bibliography targets",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Bibliography normalization skipped or merged some target numbers, so citation parser cannot link safely.",
                    proposed_fix_layer="EN polish bibliography continuation split and reference ID gap repair",
                    regression_test="Ranges such as [6, 7] remain separate from P04 when ref-6/ref-7 are absent.",
                    extra={
                        "quality_counted": False,
                        "candidate_numbers": candidate_numbers,
                        "missing_targets": missing_targets,
                    },
                )
            )
        else:
            defects.append(
                _defect(
                    defect_id="P04",
                    cc_class="CC-02",
                    check="Unlinked body citation range/list remains in polish",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Citation grammar misses body ranges, en-dash/hyphen spans, or comma-separated lists.",
                    proposed_fix_layer="EN polish citation parser",
                    regression_test="Link [1-4], [8-10], [11, 12], and mixed body citation list/range forms.",
                )
            )
    elif "float" in unlinked_range_candidates:
        block = unlinked_range_candidates["float"]
        candidate_numbers = _unlinked_citation_candidate_numbers(block)
        if candidate_numbers and ref_numbers and not any(number in ref_numbers for number in candidate_numbers):
            return defects
        defects.append(
            _defect(
                defect_id="P04T",
                cc_class="CC-02/CC-06",
                check="Citation-like numeric range/list remains in table or float context",
                severity="warning",
                block=block,
                snippet=block.text,
                stage=POLISH_STAGE,
                hypothesis="Table, caption, or float content contains numeric ranges/lists that should be reviewed separately from body citation linking.",
                proposed_fix_layer="EN audit P04 table/float classifier or table-specific citation policy",
                regression_test="Author-affiliation and table numeric ranges must not inflate body P04 counts.",
                extra={"quality_counted": False},
            )
        )
    elif "math" in unlinked_range_candidates:
        block = unlinked_range_candidates["math"]
        candidate_numbers = _unlinked_citation_candidate_numbers(block)
        if candidate_numbers and ref_numbers and not any(number in ref_numbers for number in candidate_numbers):
            return defects
        if not _unlinked_sup_numeric_range_matches_footnote_targets(block, footnote_numbers):
            defects.append(
                _defect(
                    defect_id="P04M",
                    cc_class="CC-02/CC-05",
                    check="Citation-like numeric range/list remains in math or measurement context",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Math, statistical, vector, or measurement notation resembles citation ranges and needs separate classification.",
                    proposed_fix_layer="EN audit P04 math/measurement classifier",
                    regression_test="Numeric vectors, parameter intervals, and measurement ranges must not inflate body P04 counts.",
                    extra={"quality_counted": False},
                )
            )
    return defects


def _figure_caption_ux_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
) -> list[Defect]:
    has_internal_links = bool(REF_LINK_RE.search(polish_html) or FIG_LINK_RE.search(polish_html) or TABLE_LINK_RE.search(polish_html))
    return _figure_caption_ux_defects_base(
        polish_html,
        polish_blocks,
        pdf_text=pdf_text,
        has_internal_links=has_internal_links,
        looks_like_figure_caption=_looks_like_figure_caption,
        is_supplementary_figure_block=_is_supplementary_figure_block,
        is_handled_missing_figure_block=_is_handled_missing_figure_block,
        has_nearby_image=_has_nearby_image,
        has_nearby_missing_figure_warning=_has_nearby_missing_figure_warning,
        source_pdf_text_confirms_float_gap=_source_pdf_text_confirms_float_gap,
        table_caption_re=TABLE_CAPTION_RE,
        references_heading_re=REFERENCES_HEADING_RE,
        polish_stage=POLISH_STAGE,
    )


def _image_asset_defects(polish_path: Path, polish_html: str) -> list[Defect]:
    defects: list[Defect] = []
    missing = _missing_local_images(polish_path, polish_html)
    for image in missing[:5]:
        defects.append(
            _defect(
                defect_id="P20",
                cc_class="CC-08/CC-13",
                check="Local image asset referenced by polish HTML is missing",
                severity="error",
                block=None,
                snippet=f"missing image src={image['src']}",
                stage=POLISH_STAGE,
                hypothesis="The HTML references a local sidecar image that is absent relative to the stage/review copy.",
                proposed_fix_layer="review packaging or EN polish image asset export",
                regression_test="Review/export HTML with local img src must include the referenced image or inline it as data URI.",
                extra=image,
            )
        )
    return defects


def _figure_visual_identity_defects(polish_path: Path, polish_html: str) -> list[Defect]:
    line_starts = _line_starts(polish_html)
    records_by_key: dict[str, list[dict[str, Any]]] = {}
    for match in FIGURE_UNIT_RE.finditer(polish_html):
        figure_id = match.group("id")
        body = match.group("body")
        caption_numbers = [
            number
            for caption_match in FIGURE_CAPTION_NODE_RE.finditer(body)
            for number in [_figure_caption_number_from_caption_node(caption_match.group("body"))]
            if number is not None
        ]
        for img_match in IMG_SRC_RE.finditer(body):
            src = unescape(img_match.group("src")).strip()
            key = _image_identity_key(polish_path, src)
            if key is None:
                continue
            records_by_key.setdefault(key, []).append(
                {
                    "figure_id": figure_id,
                    "caption_numbers": caption_numbers,
                    "src": src[:160],
                    "line": _line_at_from_starts(line_starts, match.start()),
                    "snippet": _strip_tags(body)[:260],
                }
            )

    for records in records_by_key.values():
        figure_ids = sorted({str(record["figure_id"]) for record in records})
        if len(figure_ids) < 2:
            continue
        caption_sets = {
            tuple(record.get("caption_numbers") or [])
            for record in records
            if record.get("caption_numbers")
        }
        if len(caption_sets) == 1 and len(records) <= 2:
            continue
        first = records[0]
        defects = [
            _defect(
                defect_id="P96",
                cc_class="CC-08/CC-13",
                check="Same visual image is attached to multiple distinct figure targets",
                severity="error",
                block=None,
                snippet=first["snippet"] or f"duplicate visual across {', '.join(figure_ids)}",
                stage=POLISH_STAGE,
                hypothesis="A missing-figure recovery or pre-existing figure assignment reused the next/previous figure image for a different caption.",
                proposed_fix_layer="P62 image recovery duplicate-visual audit and figure-page relocalization",
                regression_test="Distinct fig-5 and fig-6 units with identical image payloads are reported before review packaging.",
                extra={
                    "figure_ids": figure_ids,
                    "records": records[:6],
                },
            )
        ]
        return defects
    return []


def _numeric_ref_label_numbers(label: str) -> list[int]:
    if re.fullmatch(r"[\s\(\)\[\],.;:\-\u2010-\u2014\d]+", label) is None:
        return []
    numbers = [int(value) for value in re.findall(r"\d{1,4}", label)]
    if any(value.startswith("0") for value in re.findall(r"\d{2,4}", label)):
        return []
    return [number for number in numbers if not (1800 <= number <= 2099)]


def _paren_numeric_ref_link_count(body_blocks: Iterable[Block]) -> int:
    count = 0
    for block in body_blocks:
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw):
            if "<sup" in block.raw[max(0, match.start() - 40) : match.start()].lower():
                continue
            label = _strip_tags(match.group("body")).strip()
            if not _numeric_ref_label_numbers(label):
                continue
            left_text = _strip_tags(block.raw[max(0, match.start() - 40) : match.start()])
            right_text = _strip_tags(block.raw[match.end() : match.end() + 80])
            if (
                re.search(r"\(\s*$", left_text) is not None
                or label.startswith("(")
                or re.match(r"^\s*(?:[,;\-\u2010-\u2014]\s*\d|\))", right_text) is not None
            ):
                count += 1
    return count


def _ref_anchor_is_bracketed_numeric_citation(block_raw: str, match: re.Match[str]) -> bool:
    label = _strip_tags(match.group("body")).strip()
    if not _numeric_ref_label_numbers(label):
        return False
    if label.lstrip().startswith("[") or label.rstrip().endswith("]"):
        return True
    left_text = _strip_tags(block_raw[max(0, match.start() - 24) : match.start()])
    right_text = _strip_tags(block_raw[match.end() : match.end() + 36])
    return (
        re.search(r"\[\s*$", left_text) is not None
        and re.match(r"^\s*(?:[,;]\s*\d|\])", right_text) is not None
    )


def _citation_style_consistency_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
    pdf_link_summary: dict[str, Any] | None = None,
) -> list[Defect]:
    body_blocks = list(_non_reference_body_blocks(polish_blocks))
    body_text = " ".join(block.text for block in body_blocks)
    html_author_year_count = len(AUTHOR_YEAR_STYLE_TEXT_RE.findall(body_text))
    pdf_author_year_count = len(AUTHOR_YEAR_STYLE_TEXT_RE.findall(pdf_text)) if pdf_text else 0
    pdf_link_summary = pdf_link_summary or {}
    pdf_citation_dest_links = int(pdf_link_summary.get("pdf_citation_dest_links") or 0)
    pdf_author_year_link_labels = int(pdf_link_summary.get("pdf_author_year_link_labels") or 0)
    pdf_author_year_evidence = pdf_citation_dest_links >= 5 and pdf_author_year_link_labels >= 2
    html_author_year_evidence = html_author_year_count >= 6
    if not (pdf_author_year_evidence or html_author_year_evidence):
        return []

    bracket_citation_count = len(re.findall(r"\[\s*\d", body_text))
    numeric_ref_link_count = sum(
        1
        for block in body_blocks
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw)
        if _numeric_ref_label_numbers(_strip_tags(match.group("body")))
    )
    numeric_sup_ref_link_count = sum(
        1
        for block in body_blocks
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw)
        if _numeric_ref_label_numbers(_strip_tags(match.group("body")))
        and "<sup" in block.raw[max(0, match.start() - 40) : match.start()].lower()
    )
    numeric_citation_dominant = (
        numeric_ref_link_count >= 5 and numeric_sup_ref_link_count >= 5
    ) or (
        numeric_ref_link_count >= 10 and numeric_sup_ref_link_count >= 3
    )
    paren_numeric_ref_link_count = _paren_numeric_ref_link_count(body_blocks)
    if (numeric_citation_dominant or paren_numeric_ref_link_count >= 5) and not pdf_author_year_evidence:
        return []
    if bracket_citation_count >= 4 and not pdf_author_year_evidence:
        return []

    for block in body_blocks:
        if _block_is_float_or_table_context(block):
            continue
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw):
            label = _strip_tags(match.group("body"))
            numbers = _numeric_ref_label_numbers(label)
            if not numbers:
                continue
            if _ref_anchor_is_bracketed_numeric_citation(block.raw, match):
                continue
            text_window = _strip_tags(block.raw[max(0, match.start() - 180) : match.end() + 180])
            if re.search(r"\b(?:Fig\.?|Figs\.?|Figure|Table|Eqn?\.?|Equation)\b", text_window, re.IGNORECASE):
                continue
            return [
                _defect(
                    defect_id="P98",
                    cc_class="CC-02/CC-13/CC-14",
                    check="Numeric-only bibliography link appears in author-year article",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Article-level citation style evidence was author-year, but numeric citation fallback still created a bibliography link.",
                    proposed_fix_layer="PDF citation-profile driven article-level citation-style lock",
                    regression_test="When PDF link labels or HTML body evidence prove author-year style, numeric-only body #ref links are unwrapped.",
                    extra={
                        "label": label,
                        "ref_target": match.group("num"),
                        "html_author_year_count": html_author_year_count,
                        "pdf_author_year_count": pdf_author_year_count,
                        "pdf_citation_dest_links": pdf_citation_dest_links,
                        "pdf_author_year_link_labels": pdf_author_year_link_labels,
                    },
                )
            ]
    return []


def _manual_blind_spot_deps() -> ManualBlindSpotDeps:
    return ManualBlindSpotDeps(
        page_link_re=PAGE_LINK_RE,
        anchor_body_re=ANCHOR_BODY_RE,
        double_close_anchor_re=DOUBLE_CLOSE_ANCHOR_RE,
        url_anchor_re=URL_ANCHOR_RE,
        malformed_url_anchor_body_re=MALFORMED_URL_ANCHOR_BODY_RE,
        broken_url_text_re=BROKEN_URL_TEXT_RE,
        references_heading_re=REFERENCES_HEADING_RE,
        ref_anchor_body_re=REF_ANCHOR_BODY_RE,
        lowercase_ref_glue_re=LOWERCASE_REF_GLUE_RE,
        box_unit_re=BOX_UNIT_RE,
        figure_unit_re=FIGURE_UNIT_RE,
        immediate_external_figure_caption_re=IMMEDIATE_EXTERNAL_FIGURE_CAPTION_RE,
        table_caption_re=TABLE_CAPTION_RE,
        table_doi_append_re=TABLE_DOI_APPEND_RE,
        page_link_semantic_kind=_page_link_semantic_kind,
        looks_like_figure_caption=_looks_like_figure_caption,
        ends_like_sentence_fragment=_ends_like_sentence_fragment,
        looks_like_float_or_caption=_looks_like_float_or_caption,
        looks_like_float_note=_looks_like_float_note,
        looks_like_equation_continuation=_looks_like_equation_continuation,
        starts_like_sentence_continuation=_starts_like_sentence_continuation,
        source_pdf_text_confirms_float_gap=_source_pdf_text_confirms_float_gap,
    )


def _manual_blind_spot_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
) -> list[Defect]:
    return _manual_blind_spot_defects_base(
        polish_html,
        polish_blocks,
        deps=_manual_blind_spot_deps(),
        pdf_text=pdf_text,
        polish_stage=POLISH_STAGE,
    )


def _meine_recent_link_structure_deps() -> MeineRecentLinkDeps:
    return MeineRecentLinkDeps(
        ref_anchor_body_re=REF_ANCHOR_BODY_RE,
        author_year_text_re=AUTHOR_YEAR_TEXT_RE,
        page_link_re=PAGE_LINK_RE,
        mixedcase_var_footnote_re=MIXEDCASE_VAR_FOOTNOTE_RE,
        table_caption_id_re=TABLE_CAPTION_ID_RE,
        table_wrapper_id_re=TABLE_WRAPPER_ID_RE,
        table_ref_partial_link_re=TABLE_REF_PARTIAL_LINK_RE,
        flattened_sup_citation_re=FLATTENED_SUP_CITATION_RE,
        math_or_measurement_range_context_re=MATH_OR_MEASUREMENT_RANGE_CONTEXT_RE,
        doi_split_plain_re=DOI_SPLIT_PLAIN_RE,
        german_source_hint_re=GERMAN_SOURCE_HINT_RE,
        word_footnote_split_re=WORD_FOOTNOTE_SPLIT_RE,
        suspicious_footnote_word_merges=SUSPICIOUS_FOOTNOTE_WORD_MERGES,
        figure_unit_re=FIGURE_UNIT_RE,
        figure_caption_node_re=FIGURE_CAPTION_NODE_RE,
        figs_ref_false_ref_re=FIGS_REF_FALSE_REF_RE,
        comma_decimal_ref_re=COMMA_DECIMAL_REF_RE,
        single_stat_ref_re=SINGLE_STAT_REF_RE,
        references_heading_re=REFERENCES_HEADING_RE,
        reference_target_numbers=_reference_target_numbers,
        figure_target_keys=_figure_target_keys,
        non_reference_body_blocks=_non_reference_body_blocks,
        ref_anchor_visible_number=_ref_anchor_visible_number,
        roman_word_split_defects=_roman_word_split_defects,
        is_references_block=_is_references_block,
        looks_like_affiliation_label_roman_boundary=_looks_like_affiliation_label_roman_boundary,
        block_is_float_or_table_context=_block_is_float_or_table_context,
        flattened_sup_match_is_joined_figure_label=_flattened_sup_match_is_joined_figure_label,
        flattened_sup_match_is_doi_or_url_fragment=_flattened_sup_match_is_doi_or_url_fragment,
        block_looks_like_math_or_measurement_range_context=_block_looks_like_math_or_measurement_range_context,
        looks_like_table_flattened_citation_context=_looks_like_table_flattened_citation_context,
        page_link_semantic_kind=_page_link_semantic_kind,
        figure_caption_number_from_caption_node=_figure_caption_number_from_caption_node,
        figure_unit_allows_shared_image_alias=_figure_unit_allows_shared_image_alias,
        ref_match_inside_bracketed_numeric_citation=_ref_match_inside_bracketed_numeric_citation,
        looks_like_comma_decimal_stat_ref=_looks_like_comma_decimal_stat_ref,
        looks_like_sample_size_value_ref=_looks_like_sample_size_value_ref,
        visible_figure_target_defects=_visible_figure_target_defects,
        looks_like_float_or_caption=_looks_like_float_or_caption,
        parse_overlapping_blocks=_parse_overlapping_blocks,
        missing_figure_warning_blocks=_missing_figure_warning_blocks,
        classify_missing_figure_warning=_classify_missing_figure_warning,
    )


def _meine_recent_text_ocr_deps() -> MeineRecentTextDeps:
    return MeineRecentTextDeps(
        split_email_text_re=SPLIT_EMAIL_TEXT_RE,
        runaway_repeated_text_re=RUNAWAY_REPEATED_TEXT_RE,
        lost_ff_word_re=LOST_FF_WORD_RE,
        known_joined_word_re=KNOWN_JOINED_WORD_RE,
        float_sentence_interrupt_re=FLOAT_SENTENCE_INTERRUPT_RE,
        corrupt_email_label_re=CORRUPT_EMAIL_LABEL_RE,
        reference_roman_split_re=REFERENCE_ROMAN_SPLIT_RE,
        table_note_body_merge_re=TABLE_NOTE_BODY_MERGE_RE,
        author_marker_glue_re=AUTHOR_MARKER_GLUE_RE,
        latex_macro_runaway_re=LATEX_MACRO_RUNAWAY_RE,
        doi_body_prose_merge_re=DOI_BODY_PROSE_MERGE_RE,
        detached_accent_re=DETACHED_ACCENT_RE,
        table_section_absorb_re=TABLE_SECTION_ABSORB_RE,
        inline_intra_word_space_html_re=INLINE_INTRA_WORD_SPACE_HTML_RE,
        intra_word_space_re=INTRA_WORD_SPACE_RE,
        table_footnote_word_letter_html_re=TABLE_FOOTNOTE_WORD_LETTER_HTML_RE,
        affiliation_department_glue_re=AFFILIATION_DEPARTMENT_GLUE_RE,
        suspicious_email_domain_re=SUSPICIOUS_EMAIL_DOMAIN_RE,
        body_page_header_re=BODY_PAGE_HEADER_RE,
        table_gibberish_flow_re=TABLE_GIBBERISH_FLOW_RE,
        float_or_metadata_interruption_re=FLOAT_OR_METADATA_INTERRUPTION_RE,
        float_or_metadata_intrusion_marker_re=FLOAT_OR_METADATA_INTRUSION_MARKER_RE,
        escaped_sup_footnote_re=ESCAPED_SUP_FOOTNOTE_RE,
        references_backmatter_interleave_re=REFERENCES_BACKMATTER_INTERLEAVE_RE,
        old_scan_ocr_gibberish_re=OLD_SCAN_OCR_GIBBERISH_RE,
        split_url_domain_re=SPLIT_URL_DOMAIN_RE,
        split_at_email_re=SPLIT_AT_EMAIL_RE,
        bibliography_numbering_residue_re=BIBLIOGRAPHY_NUMBERING_RESIDUE_RE,
        publisher_recommendation_block_re=PUBLISHER_RECOMMENDATION_BLOCK_RE,
        affiliation_marker_residue_re=AFFILIATION_MARKER_RESIDUE_RE,
        pdf_line_number_residue_re=PDF_LINE_NUMBER_RESIDUE_RE,
        non_reference_body_blocks=_non_reference_body_blocks,
        joined_word_match_is_url_slug=_joined_word_match_is_url_slug,
        known_ocr_token_defects=_known_ocr_token_defects,
        find_split_dot_email_match=_find_split_dot_email_match,
        bibliography_numbering_residue_is_clean_reference_boundary=_bibliography_numbering_residue_is_clean_reference_boundary,
    )


def _meine_recent_manual_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
) -> list[Defect]:
    defects: list[Defect] = []
    defects.extend(
        _meine_recent_link_structure_defects_base(
            polish_html,
            polish_blocks,
            deps=_meine_recent_link_structure_deps(),
            pdf_text=pdf_text,
            polish_stage=POLISH_STAGE,
            raw_stage=RAW_STAGE,
        )
    )
    defects.extend(
        _meine_recent_text_ocr_defects_base(
            polish_html,
            polish_blocks,
            deps=_meine_recent_text_ocr_deps(),
            pdf_text=pdf_text,
            polish_stage=POLISH_STAGE,
        )
    )
    return defects


def _section_order_pdf_defects(
    pdf_text: str,
    polish_html: str,
    polish_blocks: list[Block],
) -> list[Defect]:
    return _section_order_pdf_defects_impl(
        pdf_text,
        polish_html,
        polish_blocks,
        references_heading_re=REFERENCES_HEADING_RE,
        stage=POLISH_STAGE,
    )


def _pdf_text_layer_defects(
    pdf_text: str,
    polish_html: str,
    polish_blocks: list[Block],
) -> list[Defect]:
    return _pdf_text_layer_defects_impl(
        pdf_text,
        polish_html,
        polish_blocks,
        references_heading_re=REFERENCES_HEADING_RE,
        stage=POLISH_STAGE,
    )


def analyze_pair(
    raw_path: Path,
    polish_path: Path,
    *,
    enable_pdf_diagnostics: bool = False,
    pdf_text_override: str | None = None,
    pdf_path_override: Path | None = None,
    pdf_diagnostics_cache: PdfDiagnosticsCache | None = None,
) -> dict[str, Any]:
    raw_html = raw_path.read_text(encoding="utf-8", errors="replace")
    polish_html = polish_path.read_text(encoding="utf-8", errors="replace")
    raw_blocks = _parse_blocks(raw_html)
    polish_blocks = _parse_blocks(polish_html)
    polish_reference_blocks = _reference_identity_blocks(polish_html)
    pdf_text = ""
    pdf_summary: dict[str, Any] = {
        "pdf_diagnostics_enabled": enable_pdf_diagnostics,
        "source_pdf_path": str(pdf_path_override or _source_pdf_path(raw_path)),
        "source_pdf_present": (pdf_path_override or _source_pdf_path(raw_path)).is_file(),
        "source_pdf_origin": "map" if pdf_path_override is not None else "stage",
        "pdf_text_status": "disabled",
        "pdf_text_chars": 0,
        "pdf_text_error": None,
        "pdf_text_cache_status": "disabled",
    }
    if enable_pdf_diagnostics or pdf_text_override is not None:
        if pdf_diagnostics_cache is not None:
            pdf_text, pdf_summary = pdf_diagnostics_cache.load_text(raw_path, pdf_text_override, pdf_path_override)
        else:
            pdf_text, pdf_summary = _load_pdf_diagnostic_text(raw_path, pdf_text_override, pdf_path_override)
            pdf_summary["pdf_text_cache_status"] = "disabled"
    pdf_link_summary = {
        "pdf_link_text_status": "disabled",
        "pdf_link_count": 0,
        "pdf_citation_dest_links": 0,
        "pdf_author_year_link_labels": 0,
        "pdf_citation_link_samples": [],
        "pdf_link_text_error": None,
        "pdf_link_cache_status": "disabled",
    }
    if enable_pdf_diagnostics:
        if pdf_diagnostics_cache is not None:
            pdf_link_summary = pdf_diagnostics_cache.link_summary(Path(pdf_summary["source_pdf_path"]))
        else:
            pdf_link_summary = _pdf_citation_link_summary(Path(pdf_summary["source_pdf_path"]))
            pdf_link_summary["pdf_link_cache_status"] = "disabled"

    defects: list[Defect] = []
    defects.extend(_frontmatter_defects(raw_blocks, polish_blocks))
    defects.extend(_citation_defects(polish_blocks, reference_blocks=polish_reference_blocks))
    defects.extend(_reference_identity_defects(polish_reference_blocks))
    defects.extend(_unit_math_defects(raw_html, polish_blocks))
    defects.extend(_equation_table_defects(polish_blocks))
    defects.extend(_figure_caption_ux_defects(polish_html, polish_blocks, pdf_text=pdf_text))
    defects.extend(_figure_visual_identity_defects(polish_path, polish_html))
    defects.extend(_image_asset_defects(polish_path, polish_html))
    defects.extend(
        _citation_style_consistency_defects(
            polish_html,
            polish_blocks,
            pdf_text=pdf_text,
            pdf_link_summary=pdf_link_summary,
        )
    )
    defects.extend(_manual_blind_spot_defects(polish_html, polish_blocks, pdf_text=pdf_text))
    defects.extend(_meine_recent_manual_defects(polish_html, polish_blocks, pdf_text=pdf_text))
    if enable_pdf_diagnostics or pdf_text_override is not None:
        defects.extend(_pdf_text_layer_defects(pdf_text, polish_html, polish_blocks))

    missing_images = _missing_local_images(polish_path, polish_html)

    summary = {
        "raw_blocks": len(raw_blocks),
        "polish_blocks": len(polish_blocks),
        "raw_img_tags": len(re.findall(r"<img\b", raw_html, re.IGNORECASE)),
        "polish_img_tags": len(re.findall(r"<img\b", polish_html, re.IGNORECASE)),
        "polish_ref_links": len(REF_LINK_RE.findall(polish_html)),
        "polish_fig_links": len(FIG_LINK_RE.findall(polish_html)),
        "polish_table_links": len(TABLE_LINK_RE.findall(polish_html)),
        "polish_page_links": len(PAGE_LINK_RE.findall(polish_html)),
        "polish_fig_ids": len(re.findall(r"\bid\s*=\s*['\"]fig-", polish_html, re.IGNORECASE)),
        "polish_table_ids": len(re.findall(r"\bid\s*=\s*['\"]table-", polish_html, re.IGNORECASE)),
        "polish_has_target_style": ":target" in polish_html,
        "polish_has_scroll_margin": "scroll-margin" in polish_html,
        "polish_replacement_chars": polish_html.count("\ufffd"),
        "polish_missing_local_images": len(missing_images),
        **pdf_summary,
        **pdf_link_summary,
    }
    article = _article_name_from_stage(polish_path)
    return {
        "article": article,
        "raw_stage_path": str(raw_path),
        "polish_stage_path": str(polish_path),
        "summary": summary,
        "defects_found": [asdict(defect) for defect in defects],
    }


def find_pairs(roots: Iterable[Path]) -> list[tuple[Path, Path]]:
    return find_stage_pairs(roots, raw_stage=RAW_STAGE, polish_stage=POLISH_STAGE)


def _assemble_report(
    roots: list[Path],
    articles: list[dict[str, Any]],
    defect_counts: dict[str, int],
    *,
    audit_status: str,
    total_pair_count: int,
) -> dict[str, Any]:
    return assemble_report(
        roots,
        articles,
        defect_counts,
        raw_stage=RAW_STAGE,
        polish_stage=POLISH_STAGE,
        audit_status=audit_status,
        total_pair_count=total_pair_count,
    )


def build_report(
    roots: list[Path],
    *,
    enable_pdf_diagnostics: bool = False,
    pdf_map: dict[str, Path] | None = None,
    progress_out: Path | None = None,
    progress_write_every: int = 10,
    jobs: int = 1,
    pdf_diagnostics_cache_dir: Path | None = None,
) -> dict[str, Any]:
    pairs = find_pairs(roots)
    progress_every = max(1, progress_write_every)
    worker_count = max(1, int(jobs or 1))
    articles_by_index: list[dict[str, Any] | None] = [None] * len(pairs)
    pdf_diagnostics_cache = (
        PdfDiagnosticsCache(pdf_diagnostics_cache_dir)
        if enable_pdf_diagnostics and pdf_diagnostics_cache_dir is not None
        else None
    )

    def completed_articles() -> list[dict[str, Any]]:
        return [article for article in articles_by_index if article is not None]

    def write_progress(completed: int) -> None:
        if progress_out is None or not (completed % progress_every == 0 or completed == len(pairs)):
            return
        articles = completed_articles()
        defect_counts = _add_corpus_hit_counts(articles)
        partial_report = _assemble_report(
            roots,
            articles,
            defect_counts,
            audit_status=("complete" if completed == len(pairs) else "running"),
            total_pair_count=len(pairs),
        )
        _write_json_report(progress_out, partial_report)
        print(
            f"Audit progress: {completed}/{len(pairs)} articles={len(articles)} "
            f"defects={sum(len(article['defects_found']) for article in articles)}",
            flush=True,
        )

    if worker_count <= 1 or len(pairs) <= 1:
        for index, (raw_path, polish_path) in enumerate(pairs, 1):
            articles_by_index[index - 1] = analyze_pair(
                raw_path,
                polish_path,
                enable_pdf_diagnostics=enable_pdf_diagnostics,
                pdf_path_override=(pdf_map or {}).get(_article_name_from_stage(raw_path)),
                pdf_diagnostics_cache=pdf_diagnostics_cache,
            )
            write_progress(index)
    else:
        tasks = [
            (
                index,
                raw_path,
                polish_path,
                enable_pdf_diagnostics,
                str((pdf_map or {}).get(_article_name_from_stage(raw_path)) or ""),
                pdf_diagnostics_cache,
            )
            for index, (raw_path, polish_path) in enumerate(pairs, 1)
        ]
        completed = 0
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(_analyze_pair_task, task) for task in tasks]
            for future in as_completed(futures):
                index, article = future.result()
                articles_by_index[index - 1] = article
                completed += 1
                write_progress(completed)
    articles = completed_articles()
    defect_counts = _add_corpus_hit_counts(articles)
    report = _assemble_report(
        roots,
        articles,
        defect_counts,
        audit_status="complete",
        total_pair_count=len(pairs),
    )
    if progress_out is not None:
        _write_json_report(progress_out, report)
    return report


def _analyze_pair_task(task: tuple[int, Path, Path, bool, str, PdfDiagnosticsCache | None]) -> tuple[int, dict[str, Any]]:
    index, raw_path, polish_path, enable_pdf_diagnostics, pdf_path, pdf_diagnostics_cache = task
    return (
        index,
        analyze_pair(
            raw_path,
            polish_path,
            enable_pdf_diagnostics=enable_pdf_diagnostics,
            pdf_path_override=Path(pdf_path) if pdf_path else None,
            pdf_diagnostics_cache=pdf_diagnostics_cache,
        ),
    )


def merge_targeted_report(
    previous_report: dict[str, Any],
    targeted_report: dict[str, Any],
    *,
    previous_report_path: Path | None = None,
    allow_new_articles: bool = False,
) -> dict[str, Any]:
    previous_articles = previous_report.get("articles") or []
    targeted_articles = targeted_report.get("articles") or []
    by_article: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for article in previous_articles:
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        by_article[article_id] = article
        order.append(article_id)

    replaced: list[str] = []
    new_articles: list[str] = []
    for article in targeted_articles:
        article_id = str(article.get("article") or "")
        if not article_id:
            continue
        if article_id not in by_article:
            if not allow_new_articles:
                raise ValueError(f"Targeted audit article is not present in previous report: {article_id}")
            order.append(article_id)
            new_articles.append(article_id)
        else:
            replaced.append(article_id)
        by_article[article_id] = article

    merged_articles = [by_article[article_id] for article_id in order if article_id in by_article]
    defect_counts = _add_corpus_hit_counts(merged_articles)
    merged = _assemble_report(
        [Path(root) for root in previous_report.get("roots") or targeted_report.get("roots") or []],
        merged_articles,
        defect_counts,
        audit_status="complete",
        total_pair_count=int(previous_report.get("total_pair_count") or len(merged_articles)),
    )
    merged["targeted_audit"] = {
        "enabled": True,
        "previous_report_path": str(previous_report_path) if previous_report_path is not None else "",
        "target_roots": targeted_report.get("roots") or [],
        "target_article_count": len(targeted_articles),
        "reused_article_count": max(0, len(previous_articles) - len(replaced)),
        "replaced_article_count": len(replaced),
        "new_article_count": len(new_articles),
        "replaced_articles": sorted(replaced),
        "new_articles": sorted(new_articles),
    }
    return merged


def _safe_print(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write((text + "\n").encode(encoding, errors="replace"))
            sys.stdout.flush()
        else:  # pragma: no cover - unusual redirected stdout implementation
            print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def _print_summary(report: dict[str, Any]) -> None:
    _safe_print(f"EN raw/polish pair audit: {report['article_count']} pair(s)")
    totals = report["corpus_summary"]["totals"]
    _safe_print(
        "Totals: "
        f"raw_img={totals['raw_img_tags']} "
        f"polish_img={totals['polish_img_tags']} "
        f"ref_links={totals['polish_ref_links']} "
        f"fig_links={totals['polish_fig_links']} "
        f"table_links={totals['polish_table_links']} "
        f"page_links={totals['polish_page_links']} "
        f"bad_chars={totals['polish_replacement_chars']} "
        f"missing_img={totals['polish_missing_local_images']}"
    )
    defect_counts = report["corpus_summary"]["defect_counts"]
    if defect_counts:
        _safe_print("Defects by check: " + ", ".join(f"{key}={value}" for key, value in sorted(defect_counts.items())))
    else:
        _safe_print("Defects by check: none")
    for article in report["articles"]:
        summary = article["summary"]
        _safe_print(
            f"- {article['article']}: "
            f"blocks={summary['raw_blocks']}->{summary['polish_blocks']} "
            f"img={summary['raw_img_tags']}->{summary['polish_img_tags']} "
            f"missing_img={summary['polish_missing_local_images']} "
            f"refs={summary['polish_ref_links']} "
            f"fig_links={summary['polish_fig_links']} "
            f"page_links={summary['polish_page_links']} "
            f"bad_chars={summary['polish_replacement_chars']} "
            f"defects={len(article['defects_found'])}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--roots",
        nargs="+",
        type=Path,
        required=True,
        help="Root directories, 01.en.raw.html files, or 02.en.polish.html files to audit.",
    )
    parser.add_argument("--out", type=Path, help="Optional JSON report path.")
    parser.add_argument(
        "--progress-write-every",
        type=int,
        default=10,
        help="When --out is set, atomically refresh the JSON report after this many audited pairs.",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit with status 1 when an error-severity defect is found.",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit with status 1 when any warning/error defect is found.",
    )
    parser.add_argument(
        "--pdf-diagnostics",
        action="store_true",
        help=(
            f"Use {PDF_SOURCE_STAGE} beside raw stages, when available, as an optional text-layer signal "
            "for low-confidence ordering diagnostics."
        ),
    )
    parser.add_argument(
        "--pdf-map",
        type=Path,
        help=(
            "Optional JSON map from article id to external PDF path. Accepts a plain object, "
            "a list of {article,pdf_path} records, or Zotero candidate records with exact/fuzzy matches."
        ),
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel article workers for audit analysis. Defaults to 1.",
    )
    parser.add_argument(
        "--merge-previous-report",
        type=Path,
        help=(
            "Merge this targeted audit into an existing full audit report. The roots are treated as "
            "the changed subset, unchanged articles are reused, and corpus summaries are recomputed."
        ),
    )
    parser.add_argument(
        "--pdf-diagnostics-cache-dir",
        type=Path,
        help="Optional directory cache for PDF text/link diagnostics keyed by path, size, and mtime.",
    )
    parser.add_argument(
        "--allow-new-target-articles",
        action="store_true",
        help="Allow targeted merge to add articles that were not present in the previous report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pdf_map = _load_pdf_map(args.pdf_map) if args.pdf_map is not None else None
    previous_report: dict[str, Any] | None = None
    if args.merge_previous_report is not None:
        previous_report = json.loads(args.merge_previous_report.read_text(encoding="utf-8"))
    report = build_report(
        args.roots,
        enable_pdf_diagnostics=args.pdf_diagnostics,
        pdf_map=pdf_map,
        progress_out=None if previous_report is not None else args.out,
        progress_write_every=args.progress_write_every,
        jobs=args.jobs,
        pdf_diagnostics_cache_dir=args.pdf_diagnostics_cache_dir,
    )
    if previous_report is not None:
        report = merge_targeted_report(
            previous_report,
            report,
            previous_report_path=args.merge_previous_report,
            allow_new_articles=args.allow_new_target_articles,
        )
        if args.out is not None:
            _write_json_report(args.out, report)
    _print_summary(report)
    if args.out is not None:
        print(f"Wrote {args.out}")
    if args.fail_on_error or args.fail_on_warning:
        severities = {"error"}
        if args.fail_on_warning:
            severities.add("warning")
        for article in report["articles"]:
            if any(defect["severity"] in severities for defect in article["defects_found"]):
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
