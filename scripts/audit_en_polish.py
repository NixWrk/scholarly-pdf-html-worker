#!/usr/bin/env python
"""Audit EN raw -> EN polish stage pairs without running Marker."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
from html import unescape
from pathlib import Path
import re
import sys
import urllib.parse
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.quality_loop.audit_blocks import (
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
    unit_diagnostic_texts as _unit_diagnostic_texts,
    visible_ref_number_from_match as _visible_ref_number_from_match,
    word_sequence_match as _word_sequence_match,
)
from zoteropdf2md.quality_loop.audit_diagnostics import make_defect
from zoteropdf2md.quality_loop.audit_report import (
    add_corpus_hit_counts as _add_corpus_hit_counts,
    assemble_report,
    corpus_totals as _corpus_totals,
    defect_quality_counted as _defect_quality_counted,
    find_stage_pairs,
    non_quality_corpus_hit_counts as _non_quality_corpus_hit_counts,
    observed_corpus_hit_counts as _observed_corpus_hit_counts,
    write_json_report as _write_json_report,
)
from zoteropdf2md.quality_loop.audit_pdf import (
    article_name_from_stage as _article_name_from_stage,
    extract_pdf_text as _extract_pdf_text,
    first_path_value as _first_path_value,
    load_pdf_diagnostic_text,
    load_pdf_map as _load_pdf_map,
    pdf_citation_link_summary,
    pdf_path_from_map_record as _pdf_path_from_map_record,
    source_pdf_path,
)
from zoteropdf2md.quality_loop.audit_p04 import (
    looks_like_math_or_measurement_range as _looks_like_math_or_measurement_range,
    unlinked_citation_candidate_numbers as _unlinked_citation_candidate_numbers_base,
    unlinked_citation_range_kind as _unlinked_citation_range_kind_base,
)
from zoteropdf2md.quality_loop.audit_p62 import (
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


RAW_STAGE = "01.en.raw.html"
POLISH_STAGE = "02.en.polish.html"
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
IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*(['\"])(?P<src>.*?)\1", re.IGNORECASE | re.DOTALL)
FIG_CAPTION_RE = re.compile(r"^\s*(?:Figure|Fig\.?|FIGURE)\s+\d+[A-Za-z]?\b", re.IGNORECASE)
TABLE_CAPTION_RE = re.compile(r"^\s*(?:TABLE|Table)\s+(?:[IVXLCM]+|\d+)\b", re.IGNORECASE)
REFERENCES_HEADING_RE = re.compile(r"^\s*(?:references|bibliography|works cited)\s*$", re.IGNORECASE)
LOCAL_ABSTRACT_SECTION_HEADING_RE = re.compile(r"^\s*\d{1,3}\s*\|\s+\S")
REF_ID_RE = re.compile(r"^ref-(\d+)$", re.IGNORECASE)
VISIBLE_REF_NUM_RE = re.compile(r"^\s*(?:\[\s*(\d{1,4})\s*\]|(\d{1,4})[.)])")
EMBEDDED_REF_BOUNDARY_RE = re.compile(r"\s(?P<num>\d{1,4})\.\s+(?=[A-Z\u00c0-\u00de])")
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
UNIT_FLATTEN_RE = re.compile(
    r"\b(?:mC\s*cm|cd\s*m|kg\s*h|mg\s*kg\s*h)\s*[-\u2212]\s*\d+\b|"
    r"\b(?-i:(?:u|\u00b5|\u03bc)m)\s*[23]\b|"
    r"\bmCcm[-\u2212]\d+\b|"
    r"\b\d+(?:\.\d+)?\s*(?-i:(?:u|\u00b5|\u03bc)?m)\s*[23]\b|"
    r"\b\d+(?:\.\d+)?Vand\b|"
    r"\b\d+(?:\.\d+)?\s*(?:u|µ|μ)Aand\b",
    re.IGNORECASE,
)
DEGREE_DEFECT_RE = re.compile(r"\b\d+(?:\.\d+)?\s+\u25e6(?=\W|$)")
LINKED_UNIT_EXP_DEFECT_RE = re.compile(
    r"\b(?:mm\s*s|cm\s*s|m\s*s|cd\s*m|mC\s*cm|(?:u|µ|μ)C\s*cm|cm|mm|m)\s*"
    r"(?:[-\u2212]|\s+\u2212)\s*1\b",
    re.IGNORECASE,
)
RESIDUAL_UNIT_TEX_RE = re.compile(
    r"\\\(\s*\\mu\s*\\\)\s*(?:C|A|m)\b|"
    r"\\muC\b|"
    r"\\mu\s*m\s*\^\{?2\}?|"
    r"\\mu\\text\{m\}|"
    r"mC\s*cm\s*<sup>\s*-?\s*<a\b",
    re.IGNORECASE,
)
JOINED_PROSE_TOKEN_RE = re.compile(
    r"\b(?:Vwater|0\.04for|forintracorticalstimulation|20nCfor|"
    r"chosenasthiswasregardedasthenominal|chosenasthiswasregardedasthe|"
    r"\d+(?:\.\d+)?(?:V|nC|(?:u|Вµ|Ој)A)(?:and|for|was))\b",
    re.IGNORECASE,
)
REF_DUP_BRACKET_PREFIX_RE = re.compile(
    r'<span\b[^>]*\bz2m-ref-num\b[^>]*>\s*(?P<num>\d{1,4})\.\s*</span>\s*'
    r'(?:<span\b[^>]*\bid\s*=\s*(["\'])page-[^"\']+\2[^>]*>\s*</span>\s*)*'
    r'\[(?P=num)\]',
    re.IGNORECASE,
)
MULTIPANEL_FIG_REF_RE = re.compile(
    r"\bfigures?\s+\d+\s*\([A-Za-z]\)\s*,\s*\([A-Za-z]\)",
    re.IGNORECASE,
)
PAGE_FURNITURE_CONTINUATION_RE = re.compile(
    r"(?:Copyright\s+\d{4}[\s\S]{0,120}?</p>\s*<p\b[^>]*>\s*(?:<a\b[^>]*>\s*)?\d{4}\s+[a-z]\s*,\s*[a-z]\)|"
    r"Correspondence:[\s\S]{0,120}?@\S+\s+[a-z]{1,4}\.\s+\d{4}\))",
    re.IGNORECASE,
)
CAPTION_INTRUSION_RE = re.compile(
    r"human input\s*\(required\)\s+image-modeling task",
    re.IGNORECASE,
)
PDF_DIAG_SECTION_SEQUENCE = ("funding", "supplementary material", "references")
INLINE_TEX_RE = re.compile(r"\\\(([\s\S]{0,800}?)\\\)")
MATH_TAG_WITH_CITATION_RE = re.compile(r"<math\b[\s\S]{0,800}?\[\d+\][\s\S]{0,800}?</math>", re.IGNORECASE)
EQUATION_ABSORB_RE = re.compile(
    r"\(\d{1,3}\)\s+(?:To make|As shown|where\b|Fig\.|Figure|Equation)",
    re.IGNORECASE,
)
CAPTION_TEX_RESIDUE_RE = re.compile(
    r"(?:\\\\|\\label\b|\\textbf\b|&lt;\s*/?\s*a\b|href=&quot;|href=\"<a\s+href=)",
    re.IGNORECASE,
)
TABLE_CAPTION_NODE_RE = re.compile(
    r"<(?P<tag>p|h[1-6]|figcaption)\b(?=[^>]*\bz2m-table-caption\b)[^>]*>"
    r"[\s\S]*?</(?P=tag)>",
    re.IGNORECASE,
)
BIORENDER_CAPTION_URL_RE = re.compile(r"BioRender\.com/", re.IGNORECASE)
BIORENDER_CAPTION_SPLIT_RE = re.compile(
    r"created\s+(?:in\s+)?BioRender[\s\S]{0,600}?</p>\s*"
    r"<h[1-6]\b[^>]*\bz2m-figure-caption\b[^>]*>[\s\S]{0,300}?BioRender\.com/"
    r"[\s\S]{0,300}?</h[1-6]>\s*"
    r"<p\b[^>]*\bz2m-figure-caption\b[^>]*>\s*comparison\s+shows\b",
    re.IGNORECASE,
)
OCR_CITATION_WORD_RE = re.compile(
    r"\btask\.\s+Sec\.|\bflagship models\s+6,000\b",
    re.IGNORECASE,
)
FRONTMATTER_OCR_RE = re.compile(
    r"(?:\u00a9\s*\d|(?:\b[A-Z][A-Za-z.-]+\s+){1,3}\d+\s+\d+\b|\b\d+\.\d+\.\d+\b)"
)
DISPLAY_MATH_OCR_RE = re.compile(r"(?:\\omega\s*}\s*\{\s*2m|omega\s*/\s*2m|\\frac\{\\omega\}\{2m\})")
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
KNOWN_OCR_TOKEN_RE = re.compile(
    r"\b(?:iournal\.pone|inital|neabling|Segmentaion|simpification|systometry|"
    r"urflowmetry|urtheral|validtation|seperable|pngpng|Uroflowmetery|"
    r"flowmetery|bootloding|Examing|Parametres|Rewiev|microconroller|"
    r"Mirocontroller|premicturtion|Nusssenblatt|temprature|childrean|"
    r"ulimate|three-dimensioanl|Tree-dimensional|Wherev\s*\d)\b|"
    r"\bDmax=Dminw1:5\b|\bpv0:\d+\b|\b0:5mLs\{?|\bhealth\s+male\s+volunteer\b|"
    r"\bwill\s+to\s+help\b|\beffici[^\w\s]{1,3}ency\b|\b0\.999\s+0995\b|"
    r"\b(?:effekt|retrospekt|qualitat)\s+iv\b|\bAPPEND\s+ix\b|"
    r"\bINTEL\s+i\s+LIGENT\b|\bQavg\s+and\s+Omax\b|\bVol\s+ofmoved\b|"
    r"\bcognitive\s+iter\b|\bsys-\s+tem\b|\bI\s+mplantable\b|"
    r"\bdocuments\s+that\s+that\s+intensity\b|\baesthesia\b|\bMagr\s+Reson\b|"
    r"\btelsa\b|\bMata-Analysis\b|\bcorrela\s+ition\b|\bcor\s+relation\b|"
    r"\braw\s+dat\s+a\b|\bRetinal\s+Nerve\s+Fiber\s+Laver\b|"
    r"\bAmercian\s+ophthalmological\s+society\b|\bbulbocarnosus\b|"
    r"\bqualify\s+factor\b|\blength\s+form\s+ADF4351\b|"
    r"\bdeceases\s+as\s+the\s+distance\b|\bUniverisity\b|\bMEME\s+sensors\b|"
    r"\bBolognia\b|\b63\s+DPhotoWorks\b|\bBulato\s+v\.\b|"
    r"\br=0\.9\s+(?:840|526)\b|\bfMR\s+i\b|"
    r"\b3\s+1\s+mm\s+female\s+human\s+brain\b|\bMu&es\b|\bHaiiy\b|"
    r"\bCruc\$xion\b|\bthev\b|\bP\s+to\s+bc\b|\bE\s+clarity\b|"
    r"\bparameter\s+a'\s+is\s+Eq\.\s*\(1\)\b|\bD_\{eve\}\b|"
    r"\bD'_\{\\rm\s+eve\}\b|\bb5223\b|\bDl5660620\b|\b2u560\b|"
    r"\bDl50\.4\b|\b9\s+m\s+m\b|\bF\s+1\s+8\b|"
    r"\bflow\s+flow\s+flow\s+flow\b|\bLiverposl\b|\bcomparision\b|"
    r"\bObject\s+Eden260V\b|\bWothlytype\b|\b20th-\s+and\s+21\s+st-century\b|"
    r"\belectromyograhic\b|\binvolunatary\b|\bclincal\b|\bsymphisis\b|"
    r"\bAmerican\s+Society\s+of\s+Clinical\s+Ncology\b|\bFlorescence\s+Technique\b|"
    r"\bTQma\s+x\b|\bVoiding\s+positing\b|\bsignificate\s+statistical\b|"
    r"\bpassive\s+senor\b|\bUrdynamic\b|\burinary\s+track\b|"
    r"\bInternational\s+continent\s+society\b|\bnon-invasivly\b|"
    r"\bhome\s+urofowmetry\b|\bRefrence\b|\bFERENCE\s+VALUES\b|"
    r"\b(?:Qrnax|TQrnax|TlOO|Q2sea)\b|\bclassifified\b|"
    r"\bNeurocsi\b|\bHip-pocampus\b|\bIPSS\s+0\s*=\s*10\s+symptoms\b|"
    r"\bDWT\s+values\s+-2\s+mm\b|\bgrade\s+1\u00bc0\b|"
    r"\bbeacause\b|\b\u03a4he\s+touch\s+map\b|\b\u0399mproving\b|"
    r"\bthrefore\b|\beBDetheque\b|\ban\s+notate\b|"
    r"\bform\s+eBDtheque\b|\bcompliment\s+of\s+the\s+text-area\s+mask\b|"
    r"\b0000-0003-4044-\s+0927\b|"
    r"\b(?:5\.22|4\.21|5\.13)\s+\\pm\s+2,\s+(?:38|36|40)\b|"
    r"\b(?:Schfer|Standarisation|subcomitee|standarization|aformentioned|Cvalli|"
    r"Routeledge)\b|\bPdetQma\s+x\b|\bBOO\s+i\b|\bIPP\s+Grade\s+(?-i:iii)\b|"
    r"\bsimulates\s+the\s+The\s+validation\b|\bto\s+be\s+The\s+topological\s+sort\b|"
    r"\bDirectX-\s+R\b|"
    r"\b(?:MDP\s+i|ISTOR|Appel's\s+Sir\s+i|Build-in\s+sensors|"
    r"Sem\s+i\s*-\s*structured|Gen-A\s+i|Numbe\s+er|parti\s+cipants|"
    r"nterview|Ggather|Vorkshop|ocus\s+group|ANACCESSIBLE|(?-i:TOOTEKO)|"
    r"Deptartment|fascade|basrelif|Mulitmodal|agumentation|"
    r"Archelological|Museum\s+of\s+Moden\s+Art|Deparment|Polywoks|"
    r"PRAVALENCE|pvalue\s*[<=>]|IPelvic|hispareunia|main:\s+\d|"
    r"characteriscs|obeserved|stuies|miduretrhal|incotinence|resultes|"
    r"intrauethral|oncontinence|Urologiy|OUALITY|QLO\s+C30|"
    r"istopaholohical|compilated|Continues\s+variables|San\s+Gerardoo|"
    r"catherization|preferrable|postvoding|Thirtyeight|electronical|"
    r"oraotten|PATRATS|STLAR|throughour|This\s+ing\s+with\s+Fig\.?\s*1|"
    r"elipse|couse-quence|Dipping\s+Robs|daguerrectype|negitive|"
    r"sclution|iedide|Cutring|proccss|Negavives|precipated|cunce|"
    r"14\s+C-beled|Shep(?:a|ha)dex|trimetylsilyl|dihydroxyated|"
    r"defensen|Rgiht|Verebrate|millenium|Foundayion|Naturwissenschaftem|"
    r"super\s+prescription\s+of\s+H3|secondsmm-2|sequence4|FA\s+330|"
    r"Ote\s+this:\s+DO|ARTI\s+CLE\s+TYPE|Accepted\s+Manuscrip|"
    r"room\s+temperation|Enzymelinked|attempeted|detecte|afrer|"
    r"tranformed|coditions|realtive|occurance|oberved|imlied|"
    r"speices|Furhtermore|responsed|treaditional|around287\.8|"
    r"Abstrac\s+t|F\s+igures|Acknow\s+rledgements|Chapte\s+r|"
    r"Append\s+i\s+ces|Apper\s+ndi\s+x|Bibliogra\s+phy|p,\s*pj\]of|"
    r"left\)999|fotograf\s+ii|London1843|co\s+verage|approximatley|"
    r"chronologicall\s+y|Archtecture|Woodsawer|Learning\s+R\s+ates|"
    r"Vacla\s+v|Date\s+o\s+of\s+mailing|Autho\s+Authorized|"
    r"patent\s+family\s+anne\s+x|hiah\s+camera|"
    r"In\s+some\s+\[880\]\s+embodiments|Marvland|OceanofPDF\.com|"
    r"Avoiraupois|appro\s+ximately|weigh\s+ght|(?-i:bH)|F\s+011\s+07|"
    r"Avo\s+i\s+irdupois|Chroming\s+and\s+Auditor\s+Spring\s+Inc\.|"
    r"ERTAINTY|acctone|pathologica|essenetial|USMLE:pPotential|"
    r"Constitutional\s+Al|GAL\s+such\s+as|"
    r"Al(?:\s+(?:techniques|Office|triad|systems|interventions|education|"
    r"feedback|driven|generated|based)|-driven|-generated|-based)|"
    r"euromodulation\s+devices|crania\s+l\s+implant|Bultimore|"
    r"Stoimeno\s+v\.|list\s+all\s+the\s+they\s+identified|"
    r"OPRATING\s+PRICIPLE|discription|milivolt|upto|coma\s+separated|"
    r"purposed\s+work|millitres|ghraph|Authers|"
    r"Electronic\(Cambridge|If\s+inal|best\s+suites|Stocks\s+shift|"
    r"nanomicells|plent|toxity|uroflometer|31\.6\s+8\s+C|35\.9\s+8\s+C|"
    r"3[67]8C|425\s+cmH2O|460\s+bpm)\b|"
    r"\bODs/MB\b|"
    r"\bet\s+nl\.|\bHands\s+of!|\bComputer\s+Based\s+Method\s+\?|"
    r"\.oog-inch\b",
    re.IGNORECASE,
)


def _known_ocr_token_is_false_positive(plain: str, match: re.Match[str]) -> bool:
    token = match.group(0)
    if token.upper() == "ELIPSE":
        context = plain[max(0, match.start() - 16) : min(len(plain), match.end() + 16)]
        return re.search(r"\bIRIT\s*-\s*ELIPSE\b", context, re.IGNORECASE) is not None
    if token == "Wothlytype":
        context = plain[max(0, match.start() - 120) : min(len(plain), match.end() + 120)]
        return re.search(r"\b(?:collodion|albumen|surface|coating|print)\b", context, re.IGNORECASE) is not None
    if token == "OceanofPDF.com":
        return True
    if token == "63 DPhotoWorks":
        context = plain[max(0, match.start() - 120) : min(len(plain), match.end() + 120)]
        return "DPhotoWorks website" in context or "3DPhotoWorks" in context
    if token == "3 1 mm female human brain":
        context = plain[max(0, match.start() - 160) : min(len(plain), match.end() + 160)]
        return "additional projects were published" in context.lower()
    if token.lower() == "cognitive iter":
        context = plain[max(0, match.start() - 160) : min(len(plain), match.end() + 160)]
        return re.search(r"\bhaptic\s+exploration\b", context, re.IGNORECASE) is not None
    return False


def _known_ocr_token_is_present_in_pdf_text_layer(token: str, pdf_text: str) -> bool:
    if not token or not pdf_text:
        return False
    token_norm = _diagnostic_text(token).lower()
    if len(token_norm) < 4:
        return False
    pdf_norm = _diagnostic_text(pdf_text).lower()
    if token_norm in pdf_norm:
        return True
    token_words = re.findall(r"[a-z0-9\u0370-\u03ff]+", token_norm, flags=re.IGNORECASE)
    if len(token_words) < 2:
        return False
    return re.search(r"\s+".join(re.escape(word) for word in token_words), pdf_norm, re.IGNORECASE) is not None
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
NUMERIC_VALUE_ROW_RE = re.compile(
    r"^\s*(?:[-+]?\d+(?:\.\d+)?\s+){3,}[-+]?\d+(?:\.\d+)?\s*$"
)
REFERENCE_BIBLIOGRAPHIC_SIGNAL_RE = re.compile(
    r"https?://|\bdoi\b|\b(?:pmid|arxiv|isbn)\b|"
    r"\b(?:19|20)\d{2}\b|"
    r"\b(?:journal|proceedings|conference|press|vol\.?|volume|pp\.?|pages?|"
    r"IEEE|ACM|Springer|Elsevier|Nature|Science|JAMA|Lancet|Urol|Ophthalmol|"
    r"Neurourol|Eur\s+J|Int\s+J)\b",
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
DOI_ONLY_METADATA_RE = re.compile(
    r"^\s*(?:doi:\s*)?(?:https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/\S+\s*(?:DOI:)?\s*$",
    re.IGNORECASE,
)
GERMAN_SOURCE_HINT_RE = re.compile(
    r"\b(?:AUSF|AUSFUEHRLICHES|AUSFUHRLICHES|PHOTOGRAPHIE|KOLLODIUM|"
    r"KOLLODIUMVERFAHREN|DRITTE|AUFLAGE|DRESDEN|WISS|PHOTOGR|INSTITUT|"
    r"TECHNICHE|SHULE|WISSEN|KALI|SALPETER|KUPFERVITRIOL|MASTIX|BORAX|"
    r"WASSER|VERLAG|KAPITEL|LEITTHEMA|DEUTSCHE|LEITLINIEN|DIAGNOSTIK|"
    r"PROSTATASYNDROMS|ZUSAMMENFASSUNG|UROLOGE|KLINIK|UND|DER|DIE|DAS|MIT)\b",
    re.IGNORECASE,
)
ROMAN_WORD_SPLIT_RE = re.compile(r"\b(?P<prefix>[A-Z][A-Za-z]{3,})\s+(?P<suffix>v|i|x|vi|ix)\b")
ROMAN_WORD_SPLIT_FALSE_PREFIXES = {
    "appendix",
    "assuming",
    "cardio",
    "chapter",
    "coordinates",
    "dcon",
    "definingx",
    "figure",
    "haystackd",
    "mean",
    "mimics",
    "node",
    "numbered",
    "reference",
    "section",
    "table",
    "type",
    "where",
}
AFFILIATION_LABEL_CONTEXT_RE = re.compile(r"\b(?:ARTICLE INFO|Keywords?|Received|Accepted)\b", re.IGNORECASE)
AFFILIATION_LABEL_RIGHT_RE = re.compile(
    r"\s+(?:Clinical|College|Department|Division|Faculty|Hospital|Institute|Laboratory|Lab|McGill|"
    r"Monash|National|Public|Research|School|Section|Unit|University)\b"
)
AFFILIATION_LABEL_LOCATION_PREFIXES = {
    "argentina",
    "australia",
    "austria",
    "belgium",
    "brazil",
    "canada",
    "china",
    "denmark",
    "england",
    "finland",
    "france",
    "germany",
    "hungary",
    "india",
    "ireland",
    "italy",
    "japan",
    "netherlands",
    "norway",
    "portugal",
    "spain",
    "sweden",
    "switzerland",
}
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
VISIBLE_FIGURE_REF_RE = re.compile(
    r"\b(?P<supp>(?:Supplementary|Supplemental|Suppl\.?)\s+)?"
    r"(?:Fig\.?|Figure)\s+"
    r"(?P<num>(?:S\s*)?\d{1,3}"
    r"(?:\s*(?:[\-\u2010-\u2014]\s*\d{1,3}|\.\s*(?:\d{1,2}(?!\d)|\d{3}(?!\s+[A-Za-z]))))*)"
    r"(?P<letter>[A-Z])?\b",
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


def _inline_tex_contains_citation_bracket(tex: str) -> bool:
    for match in re.finditer(r"\[\s*\d{1,4}\s*\]", tex):
        prefix = tex[: match.start()]
        if re.search(r"\\[A-Za-z]+\*?\s*$", prefix):
            continue
        return True
    return False


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


def _phrase_positions(text: str, phrases: Iterable[str]) -> dict[str, int]:
    return {phrase: text.find(phrase) for phrase in phrases}


def _is_inline_or_remote_src(src: str) -> bool:
    src = src.strip()
    if not src or src.startswith("#"):
        return True
    lower = src.lower()
    if lower.startswith(("data:", "http://", "https://", "blob:", "cid:")):
        return True
    parsed = urllib.parse.urlsplit(src)
    return bool(parsed.scheme and parsed.scheme.lower() not in {"file"})


def _local_image_candidates(html_path: Path, src: str) -> list[Path]:
    clean = src.strip().split("?", 1)[0].split("#", 1)[0]
    if not clean:
        return []
    parsed = urllib.parse.urlsplit(clean)
    path_value = parsed.path if parsed.scheme.lower() == "file" else clean
    decoded = urllib.parse.unquote(path_value)
    if re.match(r"^/[A-Za-z]:/", decoded):
        decoded = decoded[1:]
    candidate = Path(decoded)
    if candidate.is_absolute():
        return [candidate]

    search_dirs = [html_path.parent]
    if html_path.parent.name == "_z2m_stages":
        search_dirs.append(html_path.parent.parent)
    return [(base / decoded).resolve(strict=False) for base in search_dirs]


def _missing_local_images(html_path: Path, html: str) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    seen: set[str] = set()
    line_starts = _line_starts(html)
    for match in IMG_SRC_RE.finditer(html):
        src = unescape(match.group("src")).strip()
        if _is_inline_or_remote_src(src):
            continue
        candidates = _local_image_candidates(html_path, src)
        if any(candidate.is_file() for candidate in candidates):
            continue
        key = src
        if key in seen:
            continue
        seen.add(key)
        missing.append(
            {
                "src": src,
                "line": _line_at_from_starts(line_starts, match.start()),
                "searched": [str(candidate) for candidate in candidates],
            }
        )
    return missing


def _image_identity_key(html_path: Path, src: str) -> str | None:
    src = unescape(src).strip()
    if not src:
        return None
    if src.lower().startswith("data:image/"):
        return "data:" + hashlib.sha256(src.encode("utf-8", errors="replace")).hexdigest()
    if _is_inline_or_remote_src(src):
        return None
    for candidate in _local_image_candidates(html_path, src):
        if not candidate.is_file():
            continue
        try:
            return "file:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        except OSError:
            continue
    return f"src:{src}"


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


def _is_references_block(block: Block, references_started: bool) -> bool:
    return references_started or block.id.startswith("ref-") or REFERENCES_HEADING_RE.match(block.text) is not None


def _has_local_abstract_heading_nearby(
    blocks: list[Block],
    index: int,
    *,
    direction: int,
    window: int,
) -> bool:
    stop = min(len(blocks), index + window + 1) if direction > 0 else max(-1, index - window - 1)
    for scan_index in range(index + direction, stop, direction):
        candidate = blocks[scan_index]
        if LOCAL_ABSTRACT_SECTION_HEADING_RE.match(candidate.text):
            return True
        if candidate.tag.startswith("h") and REFERENCES_HEADING_RE.match(candidate.text):
            continue
    return False


def _looks_like_local_abstract_reference_block(blocks: list[Block], index: int) -> bool:
    block = blocks[index]
    visible_match = VISIBLE_REF_NUM_RE.match(block.text)
    visible_number = _visible_ref_number_from_match(visible_match)
    if visible_number is None or visible_number > 3:
        return False
    if not any(
        REFERENCES_HEADING_RE.match(blocks[scan_index].text)
        for scan_index in range(max(0, index - 3), index)
    ):
        return False
    if not (
        _has_local_abstract_heading_nearby(blocks, index, direction=-1, window=80)
        or _has_local_abstract_heading_nearby(blocks, index, direction=1, window=8)
    ):
        return False
    tail = VISIBLE_REF_NUM_RE.sub("", block.text, count=1).strip()
    author_head = r"[^\s,]{2,80}"
    initial_token = r"[^\W\d_](?:[^\W\d_]|\.){0,5}"
    return bool(
        re.match(
            rf"{author_head}(?:,\s+{initial_token}|(?:\s+{initial_token}){{1,4}}\s*,)",
            tail,
        )
        or re.search(r"\b(?:doi|pmid|pmcid)\s*:", tail, re.IGNORECASE)
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


def _block_looks_like_frontmatter_affiliation_table(block: Block) -> bool:
    if block.tag.lower() != "table" and "z2m-table-unit" not in block.classes:
        return False
    text = _normalize_ws(block.text)
    if not text or len(text) > 2600:
        return False
    affiliation_hits = len(
        re.findall(
            r"\b(?:department|division|faculty|institute|laboratory|school|university|"
            r"correspondence|authors?\s+contributed|netherlands|denmark)\b",
            text,
            re.IGNORECASE,
        )
    )
    marker_hits = len(re.findall(r"(?:^|[\s,])\d{1,2}(?:,\d{1,2})*(?=\s|,|$)", text))
    has_author_marker = bool(re.search(r"\b[A-Z][A-Za-z.-]+\s+[A-Z][A-Za-z.-]+\s+\d{1,2}(?:,\d{1,2})?", text))
    return affiliation_hits >= 2 and marker_hits >= 4 and has_author_marker


def _numbered_reference_block_is_likely_non_bibliographic(block: Block) -> bool:
    if block.id.startswith("ref-"):
        return False
    text = _normalize_ws(block.text)
    if re.match(r"^\s*\d+\.\d+(?:\.\d+)*\b", text):
        return True
    if REFERENCE_BIBLIOGRAPHIC_SIGNAL_RE.search(text):
        return False
    if re.match(r"^\s*\d+\.\s*\[?(?:optional|required)\]?\s", text, re.IGNORECASE):
        return True
    return True


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


def _figure_key_from_visible_number(value: str) -> str:
    value = re.sub(r"(?i)^s\s+(?=\d)", "s", value.strip())
    value = re.sub(r"\s*[.\-\u2010-\u2014]\s*", "-", value)
    return value.strip("-.").lower()


def _figure_key_from_visible_match(match: re.Match[str]) -> str:
    key = _figure_key_from_visible_number(match.group("num"))
    if match.group("supp"):
        return f"supplementary-{key}"
    return key


def _is_external_supplementary_figure_ref(match: re.Match[str]) -> bool:
    key = _figure_key_from_visible_number(match.group("num"))
    return bool(match.group("supp")) or key.startswith("s")


def _is_supplementary_figure_block(block: Block) -> bool:
    return block.id.lower().startswith("fig-supplementary-") or SUPPLEMENTARY_FIGURE_LABEL_RE.match(block.text) is not None


def _figure_target_keys(html: str) -> set[str]:
    return {
        key.lower()
        for key in re.findall(r"\bid\s*=\s*['\"]fig-([A-Za-z0-9-]+)['\"]", html, re.IGNORECASE)
    }


def _figure_target_numbers(html: str) -> set[int]:
    return {int(key) for key in _figure_target_keys(html) if key.isdigit()}


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


def _has_nearby_fig_link(block: Block, figure_key: str, text_pos: int) -> bool:
    raw_text = _strip_tags(block.raw)
    if text_pos >= len(raw_text):
        raw_window = block.raw
    else:
        raw_window = block.raw[max(0, text_pos - 180) : text_pos + 220]
    return re.search(rf"href\s*=\s*['\"]#fig-{re.escape(figure_key)}['\"]", raw_window, re.IGNORECASE) is not None


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


def _figure_unit_allows_shared_image_alias(body: str, wrapper_num: int, unrelated: list[int]) -> bool:
    if not unrelated:
        return False
    if len(re.findall(r"<img\b", body, re.IGNORECASE)) != 1:
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
        for number in [_figure_caption_number_from_caption_node(caption_match.group("body"))]
        if number is not None
    }
    expected = set(unrelated)
    if not expected.issubset(float_alias_nums) or not expected.issubset(caption_nums):
        return False
    all_caption_nums = sorted(caption_nums | {wrapper_num})
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


def _unit_match_is_repaired_in_raw(match_text: str, raw: str) -> bool:
    raw_unescaped = unescape(raw)
    if re.search(r"(?-i:(?:u|\u00b5|\u03bc)m)\s*[23]\b", match_text, re.IGNORECASE):
        return bool(
            re.search(
                r"(?-i:(?:u|\u00b5|\u03bc)m)\s*<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*[23]\s*</sup>",
                raw_unescaped,
                re.IGNORECASE,
            )
            or (
                "data-z2m-tex" in raw_unescaped
                and re.search(r"(?-i:(?:u|\u00b5|\u03bc)m)\s*\^\{?\s*[23]\s*\}?", raw_unescaped)
            )
        )
    if re.search(r"\b\d+(?:\.\d+)?\s*(?-i:(?:u|\u00b5|\u03bc)?m)\s*[23]\b", match_text, re.IGNORECASE):
        return bool(
            re.search(
                r"(?-i:(?:u|\u00b5|\u03bc)?m)\s*<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*[23]\s*</sup>",
                raw_unescaped,
                re.IGNORECASE,
            )
            or (
                "data-z2m-tex" in raw_unescaped
                and re.search(r"(?-i:(?:u|\u00b5|\u03bc)?m)\s*\^\{?\s*[23]\s*\}?", raw_unescaped)
            )
        )
    if re.search(r"\b(?:mC\s*cm|cd\s*m|kg\s*h|mg\s*kg\s*h)\s*[-\u2212]\s*\d+\b", match_text, re.IGNORECASE):
        return bool(re.search(r"<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*-\d+\s*</sup>", raw_unescaped, re.IGNORECASE))
    return False


def _frontmatter_name_candidates(text: str) -> list[str]:
    candidates = re.findall(
        r"\b[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){1,6}\b",
        text,
    )
    names: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_ws(candidate)
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(normalized)
    return names


def _frontmatter_ocr_repaired_by_polish(raw_text: str, polish_blocks: list[Block]) -> bool:
    names = _frontmatter_name_candidates(raw_text)
    if not names:
        return False
    name_keys = [name.lower() for name in names]
    relevant_blocks = [
        block
        for block in polish_blocks[:40]
        if any(name_key in block.text.lower() for name_key in name_keys)
    ]
    if not relevant_blocks:
        return False
    if not any(
        (block.classes & {"z2m-front-matter", "z2m-affiliations"}) and "<sup" in block.raw.lower()
        for block in relevant_blocks
    ):
        return False
    relevant_text = _normalize_ws(" ".join(block.text for block in relevant_blocks))
    if FRONTMATTER_OCR_RE.search(relevant_text):
        return False
    hit_count = sum(1 for name_key in name_keys if name_key in relevant_text.lower())
    return hit_count >= min(2, len(name_keys))


def _looks_like_copyright_notice(text: str) -> bool:
    lowered = text.lower()
    return (
        "copyright" in lowered
        or "all rights reserved" in lowered
        or "creative commons" in lowered
        or "open access article" in lowered
        or "licensee" in lowered
        or "©" in text
    )


def _looks_like_frontmatter_metadata_notice(text: str) -> bool:
    normalized = _normalize_ws(text)
    lowered = normalized.lower()
    doi_mention_re = r"(?:\bdoi\s*:?\s*(?:https?://(?:dx\.)?doi\.org/)?10\.\S+|https?://(?:dx\.)?doi\.org/10\.\S+)"
    if re.fullmatch(
        r"(?:to\s+(?:link|cite)\s+to\s+this\s+article|article\s+link)\s*:?\s*"
        r"(?:https?://(?:dx\.)?doi\.org/)?10\.\S+",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if re.fullmatch(
        r"(?:doi\s*:?\s*)?(?:https?://(?:dx\.)?doi\.org/)?10\.\S+",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if (
        re.search(doi_mention_re, lowered)
        and not re.search(r"\b(?:abstract|introduction|methods?|results?|discussion|conclusion)\b", lowered)
        and len(normalized) <= 180
    ):
        return True
    if (
        re.search(doi_mention_re, lowered)
        and (
            lowered.startswith(("citation:", "please cite this article as:"))
            or re.search(r"\b\d{4}\s*;\s*\d+\s*(?:\([^)]*\))?\s*:\s*\d+", normalized)
            or re.search(r"\b(?:journal|hearing\s+research|invest\s+ophthalmol|pak\s+j\s+med\s+sci)\b", lowered)
        )
        and len(normalized) <= 520
    ):
        return True
    if re.fullmatch(
        rf"(?:(?:received|accepted|published)\s*:?\s*\d{{1,4}}(?:[./]\d{{1,2}}){{2}}\s*){{2,4}}",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if re.fullmatch(
        r"(?:received|accepted|published)\s*:?\s*\d{1,2}\.\d{1,2}\.\d{4}\s+"
        r"(?:received|accepted|published)\s*:?\s*\d{1,2}\.\d{1,2}\.\d{4}",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if re.fullmatch(
        r"\d+(?:\.\d+){2,}\s+[A-Z][\s\S]{2,140}",
        normalized,
    ):
        return True
    if re.search(r"\b(?:clinicaltrials\.gov|trial\s+registration|project\s+no\.?)\b", lowered):
        return True
    if re.search(r"\bproject\s+no\.?\s+\d+(?:\.\d+){1,3}-[A-Z0-9-]+\b", normalized, re.IGNORECASE):
        return True
    if re.fullmatch(
        r"printed\s+in\s+the\s+united\s+states\s+of\s+america"
        r"(?:\s+\d+){3,}\s*",
        normalized,
        re.IGNORECASE,
    ):
        return True
    month = (
        r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    )
    if re.fullmatch(
        rf"(?:submitted|received|accepted|published|available\s+online(?:\s+date)?)?\s*:?\s*"
        rf"\d{{1,2}}\s+{month}\s+\d{{4}}(?:\s*\(\d{{1,2}}\.\d{{1,2}}\.\d{{4}}\))?",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if re.fullmatch(
        r"(?:submitted|received|accepted|published|available\s+online(?:\s+date)?)?\s*:?\s*"
        r"\d{1,2}\.\d{1,2}\.\d{4}",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if (
        re.search(r"\b(?:department|hospital|institute|university|medical\s+center|centre)\b", lowered)
        and re.search(r"\b(?:floor|room|street|road|laan|avenue|netherlands|usa|uk)\b", lowered)
    ):
        return True
    if (
        re.search(r"\b(?:tel\.?|fax|e-?mail|email|correspondence\s+to)\b|@", lowered)
        and re.search(
            r"\b(?:department|institute|university|school|college|hospital|center|centre|street|avenue|road|"
            r"box|poland|india|sweden|usa|uk)\b",
            lowered,
        )
    ):
        return True
    return False


def _looks_like_author_affiliation_index_line(text: str) -> bool:
    normalized = _normalize_ws(text)
    if not (40 <= len(normalized) <= 260):
        return False
    if any(marker in normalized for marker in ("\u00a9", "В©")):
        return False
    if not re.search(r"(?:\b\d{1,2}\s*,?\s*){3,}$", normalized):
        return False
    if normalized.count(",") < 2:
        return False
    name_hits = re.findall(
        r"\b[A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'-]+(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'-]+){0,3}\b",
        normalized,
    )
    if len(name_hits) < 3:
        return False
    return not re.search(r"\b(?:abstract|introduction|methods?|results?|discussion)\b", normalized, re.IGNORECASE)


def _looks_like_frontmatter_table_or_highlight_text(text: str) -> bool:
    normalized = _normalize_ws(text)
    lowered = normalized.lower()
    if lowered.startswith("patient ") and "cause of" in lowered and "blindness" in lowered and "braille" in lowered:
        return True
    if (
        re.search(r"\bprior\s+to\s+microelectrode\s+array\s+placement\b", lowered)
        and re.search(r"\b(?:mri|human\s+connectome\s+project|surgical\s+array)\b", lowered)
    ):
        return True
    if "for array targeting" in lowered and "connectome workbench" in lowered:
        return True
    if (
        re.match(r"^\d+(?:\.\d+){1,4}\.?\s+[A-Z][\s\S]{80,}", normalized)
        and re.search(r"\b(?:purpose|experiment|accuracy|array|targeting|participant|figure|workbench)\b", lowered)
    ):
        return True
    if re.match(r"^1\.\s+we\s+present\b", lowered) and re.search(r"\b2\.\s+we\s+characterize\b", lowered):
        return True
    return False


def _looks_like_table_of_contents_block(text: str) -> bool:
    normalized = _normalize_ws(text)
    lowered = normalized.lower()
    if "list of figures" in lowered or "list of tables" in lowered:
        return True
    section_hits = len(re.findall(r"\b\d+(?:\.\d+){1,3}\s+[A-Z][A-Za-z]", normalized))
    numbered_heading_hits = len(re.findall(r"\b\d{1,2}\.\s+[A-Z][A-Za-z]", normalized))
    roman_page_hits = len(re.findall(r"\b(?:i{1,3}|iv|v|vi{0,3}|ix|x|xi{0,3})\b", lowered))
    chapter_hits = len(re.findall(r"\bchapte?\s*r\s+\d+\s*:", lowered))
    if (
        numbered_heading_hits >= 5
        and len(re.findall(r"\b\d{1,4}\b", normalized)) >= 10
        and re.search(r"\b(?:page|introduction|keywords|appendices|application|reviewer|research)\b", lowered)
    ):
        return True
    if (
        section_hits >= 4
        and len(re.findall(r"\b\d{1,4}\b", normalized)) >= 8
        and re.search(r"\b(?:pre-review|post-review|reviewer\s+matching|application\s+of\s+ai|research)\b", lowered)
    ):
        return True
    if chapter_hits >= 2 and section_hits >= 4:
        return True
    if (
        section_hits >= 5
        and len(re.findall(r"\b\d{1,4}\b", normalized)) >= 10
        and re.search(r"\b(?:abstract|chapter|introduction|overview|literature\s+review|theoretical\s+background)\b", lowered)
    ):
        return True
    return section_hits >= 4 and roman_page_hits >= 1


def _frontmatter_defects(raw_blocks: list[Block], polish_blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    raw_early = raw_blocks[:20]
    for block in raw_early:
        if block.text.lower().startswith("to cite this article:"):
            continue
        if FRONTMATTER_OCR_RE.search(block.text):
            if _looks_like_copyright_notice(block.text):
                continue
            if _looks_like_frontmatter_metadata_notice(block.text):
                continue
            if _looks_like_author_affiliation_index_line(block.text):
                continue
            if _looks_like_frontmatter_table_or_highlight_text(block.text):
                continue
            if _looks_like_table_of_contents_block(block.text):
                continue
            if _frontmatter_ocr_repaired_by_polish(block.text, polish_blocks):
                continue
            defects.append(
                _defect(
                    defect_id="P01",
                    cc_class="CC-01/CC-13",
                    check="Suspicious raw front-matter marker OCR",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=RAW_STAGE,
                    hypothesis="Author affiliation, corresponding-author, or footnote markers were damaged before polish.",
                    proposed_fix_layer="Marker raw audit or EN polish front-matter repair",
                    regression_test="Audit Nature/front-matter author lines with multi-affiliations and contribution markers.",
                )
            )
            break

    for block in polish_blocks[:25]:
        if "z2m-affiliations" in block.classes and REF_LINK_RE.search(block.raw):
            defects.append(
                _defect(
                    defect_id="P02",
                    cc_class="CC-01/CC-02",
                    check="Affiliation block contains bibliography links",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Citation linkification ran inside a front-matter affiliation block.",
                    proposed_fix_layer="EN polish citation-linkification exclusion zones",
                    regression_test="Affiliation labels in z2m-affiliations must never link to #ref-*.",
                )
            )
            break

    for block in polish_blocks[:18]:
        ref_count = len(REF_LINK_RE.findall(block.raw))
        name_like_count = len(re.findall(r"\b[A-Z][A-Za-z.-]+\s+[A-Z][A-Za-z.-]+\b", block.text))
        body_like = re.search(
            r"\b(?:abstract|introduction|generative artificial intelligence|clinical|methodology|"
            r"papers?|studies|review|museum|gallery|visitors?|participants?|technolog(?:y|ies|ical)|"
            r"experimental|setup|tools?|toolkit|introduced|reported|developed|implementation|"
            r"behavior|behaviour|records?|measure|measured|larval|zebrafish|swim|swimming|"
            r"posture|locomotion)\b",
            block.text,
            re.IGNORECASE,
        )
        bracket_citation_like = re.search(r"\[\s*\d{1,3}", block.text) is not None
        sentence_count = len(re.findall(r"\w\.", block.text))
        if (
            ref_count >= 2
            and name_like_count >= 2
            and not body_like
            and not bracket_citation_like
            and sentence_count <= 2
        ):
            defects.append(
                _defect(
                    defect_id="P03",
                    cc_class="CC-01/CC-02",
                    check="Author-line markers link to bibliography refs",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Author affiliation markers were treated as bibliography citations.",
                    proposed_fix_layer="EN polish front-matter detection before reference linkification",
                    regression_test="Author names with superscript affiliation lists must stay unlinked.",
                    extra={"ref_link_count": ref_count, "name_like_count": name_like_count},
                )
            )
            break

    for block in polish_blocks[40:]:
        if "z2m-front-matter" not in block.classes:
            continue
        if REFERENCES_HEADING_RE.match(block.text):
            continue
        if len(block.text) < 80:
            continue
        if re.search(r"\b(?:clinical|validation|metrics|model|models|performance|evaluation|patients|studies)\b", block.text, re.IGNORECASE):
            defects.append(
                _defect(
                    defect_id="P25",
                    cc_class="CC-01/CC-02",
                    check="Late body paragraph is marked as front matter",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Front-matter protection is too broad and suppresses valid body citation linking.",
                    proposed_fix_layer="EN polish bounded block-role/front-matter classifier",
                    regression_test="Body paragraphs after the article-start region must not carry z2m-front-matter.",
                )
            )
            break
    return defects


def _citation_defects(polish_blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    references_started = False
    unlinked_range_candidates: dict[str, Block] = {}
    ref_numbers = {
        int(match.group(1))
        for block in polish_blocks
        for match in (re.match(r"^ref-(\d+)$", block.id, re.IGNORECASE),)
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


def _reference_identity_defects(polish_blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    references_started = False
    seen_visible: dict[int, Block] = {}
    seen_ids: dict[int, Block] = {}
    nested_seen_ids: dict[int, Block] = {}
    saw_mismatch = False
    saw_duplicate = False
    saw_gap = False
    saw_duplicate_prefix = False
    saw_embedded_numbered_reference = False
    missing_visible_number: list[tuple[int, Block]] = []

    def _looks_like_embedded_numbered_reference_tail(tail: str) -> bool:
        text = tail.strip()
        if len(text) < 18:
            return False
        if re.match(
            r"^(?:The\s+)?[A-Z][A-Za-z0-9&'\u2019().,\- ]{3,90}\.\s+Available\s+online\b",
            text,
        ):
            return True
        return bool(
            re.match(
                r"^[A-Z][A-Za-z\u00c0-\u00ff'\u2019.-]+,\s+(?:[A-Z]|et\s+al\.?\b)",
                text,
            )
            or re.match(
                r"^[A-Z][A-Za-z\u00c0-\u00ff'\u2019.-]+\s+"
                r"[A-Z][A-Za-z\u00c0-\u00ff'\u2019.-]+,\s+(?:[A-Z]|et\s+al\.?\b)",
                text,
            )
        )

    def _can_have_embedded_numbered_reference(
        block: Block, visible_number: int | None, id_number: int | None
    ) -> bool:
        if visible_number is not None or id_number is not None:
            return True
        return block.attrs.get("data-z2m-audit-nested-ref-item") == "1"

    for index, block in enumerate(polish_blocks):
        if REFERENCES_HEADING_RE.match(block.text):
            references_started = True
            continue
        if not _is_references_block(block, references_started):
            continue
        if not block.id and DOI_ONLY_METADATA_RE.match(block.text):
            continue
        if block.id.startswith("section-"):
            continue

        visible_match = VISIBLE_REF_NUM_RE.match(block.text)
        visible_number = _visible_ref_number_from_match(visible_match)
        id_match = REF_ID_RE.match(block.id)
        id_number = int(id_match.group(1)) if id_match is not None else None
        if (
            visible_number is not None
            and _looks_like_local_abstract_reference_block(polish_blocks, index)
        ):
            continue
        if id_number is None and NUMERIC_VALUE_ROW_RE.match(block.text):
            continue
        if (
            visible_number is not None
            and id_number is None
            and _numbered_reference_block_is_likely_non_bibliographic(block)
        ):
            continue
        is_nested_audit_ref = block.attrs.get("data-z2m-audit-nested-ref-item") == "1"
        if id_number is not None:
            if is_nested_audit_ref:
                nested_seen_ids[id_number] = block
            else:
                seen_ids[id_number] = block
                if visible_number is None and not DOI_ONLY_METADATA_RE.match(block.text):
                    missing_visible_number.append((id_number, block))
        if is_nested_audit_ref:
            if visible_number is not None and visible_number not in seen_visible:
                seen_visible[visible_number] = block
            continue

        if not saw_duplicate_prefix and REF_DUP_BRACKET_PREFIX_RE.search(block.raw):
            defects.append(
                _defect(
                    defect_id="P27",
                    cc_class="CC-02/CC-13",
                    check="Bibliography entry keeps duplicate bracketed reference prefix",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Reference normalization added z2m numbering without stripping the source bracket number.",
                    proposed_fix_layer="EN polish bibliography prefix deduplication",
                    regression_test="References like '1. [1] Author...' normalize to one visible number.",
                )
            )
            saw_duplicate_prefix = True

        if not saw_embedded_numbered_reference and _can_have_embedded_numbered_reference(
            block, visible_number, id_number
        ):
            text_without_prefix = VISIBLE_REF_NUM_RE.sub("", block.text, count=1)
            for embedded_match in EMBEDDED_REF_BOUNDARY_RE.finditer(text_without_prefix):
                embedded_number = int(embedded_match.group("num"))
                if embedded_number > 500 or embedded_number in {visible_number, id_number}:
                    continue
                if not _looks_like_embedded_numbered_reference_tail(
                    text_without_prefix[embedded_match.end() :]
                ):
                    continue
                defects.append(
                    _defect(
                        defect_id="P26",
                        cc_class="CC-02/CC-13",
                        check="Bibliography item contains embedded numbered references",
                        severity="warning",
                        block=block,
                        snippet=block.text,
                        stage=POLISH_STAGE,
                        hypothesis="Reference continuation merging swallowed one or more later bibliography entries into an earlier item.",
                        proposed_fix_layer="EN polish bibliography continuation merge and line-number stripping",
                        regression_test="Line-number-prefixed bibliography items such as '1161 106. Smith...' remain independent ref-106 entries.",
                        extra={
                            "embedded_number": embedded_number,
                            "id_number": id_number,
                            "visible_number": visible_number,
                        },
                    )
                )
                saw_embedded_numbered_reference = True
                break

        if not saw_mismatch and id_number is not None and visible_number is not None and id_number != visible_number:
            defects.append(
                _defect(
                    defect_id="P21",
                    cc_class="CC-02/CC-13",
                    check="Reference target ID does not match visible bibliography number",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Reference IDs were assigned by raw list ordinal after Marker split or duplicated bibliography items.",
                    proposed_fix_layer="EN polish bibliography normalization before citation linkification",
                    regression_test="id=ref-N must contain visible reference number N when the bibliography prints numbers.",
                    extra={"id_number": id_number, "visible_number": visible_number},
                )
            )
            saw_mismatch = True

        if visible_number is None:
            continue
        if visible_number in seen_visible and not saw_duplicate:
            defects.append(
                _defect(
                    defect_id="P22",
                    cc_class="CC-02/CC-13",
                    check="Duplicate visible bibliography number",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="A continuation fragment or duplicate raw list item may still be treated as a separate reference.",
                    proposed_fix_layer="EN polish bibliography continuation merge and reference audit",
                    regression_test="Duplicate visible reference numbers are merged or explicitly reported before manual review.",
                    extra={"visible_number": visible_number, "first_line": seen_visible[visible_number].line},
                )
            )
            saw_duplicate = True
        else:
            seen_visible[visible_number] = block

    if not saw_gap and len(seen_ids) >= 2:
        sorted_ids = sorted(seen_ids)
        for left, right in zip(sorted_ids, sorted_ids[1:]):
            if right - left > 1:
                missing = list(range(left + 1, right))
                missing = [ref_id for ref_id in missing if ref_id not in nested_seen_ids]
                if not missing:
                    continue
                defects.append(
                    _defect(
                        defect_id="P26",
                        cc_class="CC-02/CC-13",
                        check="Bibliography target IDs contain a gap",
                        severity="warning",
                        block=seen_ids[right],
                        snippet=seen_ids[right].text,
                        stage=POLISH_STAGE,
                        hypothesis="An unnumbered item or continuation may have been swallowed, skipped, or assigned the wrong identity.",
                        proposed_fix_layer="EN polish bibliography identity/gap audit",
                        regression_test="A missing visible number such as 58 is warned or assigned to the unnumbered bibliography item.",
                        extra={"missing_ids": missing[:10], "left_id": left, "right_id": right},
                    )
                )
                saw_gap = True
                break

    if missing_visible_number and (seen_visible or len(seen_ids) >= 2):
        ref_id, block = missing_visible_number[0]
        defects.append(
            _defect(
                defect_id="P97",
                cc_class="CC-02/CC-13",
                check="Bibliography target is missing its visible reference number",
                severity="error",
                block=block,
                snippet=block.text,
                stage=POLISH_STAGE,
                hypothesis="Reference IDs were created, but one or more bibliography entries were left unnumbered for the reader.",
                proposed_fix_layer="EN polish bibliography numbering and reference identity audit",
                regression_test="Every id=ref-N bibliography entry gets visible number N or is explicitly reported.",
                extra={
                    "ref_id": ref_id,
                    "missing_visible_ref_ids": [number for number, _block in missing_visible_number[:12]],
                },
            )
        )

    return defects


def _unit_math_defects(raw_html: str, polish_blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    for block in polish_blocks:
        for diagnostic_text in _unit_diagnostic_texts(block):
            unit_match = UNIT_FLATTEN_RE.search(diagnostic_text)
            if unit_match is not None and _unit_match_is_repaired_in_raw(unit_match.group(0), block.raw):
                unit_match = None
            linked_unit_match = LINKED_UNIT_EXP_DEFECT_RE.search(diagnostic_text)
            if linked_unit_match is not None and "z2m-unit-exp" in block.raw:
                linked_unit_match = None
            joined_match = JOINED_PROSE_TOKEN_RE.search(diagnostic_text)
            match = unit_match or DEGREE_DEFECT_RE.search(diagnostic_text) or linked_unit_match or joined_match
            if match:
                defects.append(
                    _defect(
                        defect_id="P06",
                        cc_class="CC-04",
                        check="Flattened or malformed unit/exponent/spacing pattern",
                        severity="warning",
                        block=block,
                        snippet=diagnostic_text or block.text,
                        stage=POLISH_STAGE,
                        hypothesis="Unit/math normalization did not preserve exponent, micro/degree symbol, or spacing.",
                        proposed_fix_layer="EN polish unit normalization before citation linkification",
                        regression_test="Normalize micro units, cm^-2, um^2, degree symbols, and value-unit-word spacing.",
                    )
                )
                break
        if defects and defects[-1].id == "P06":
            break

    for block in polish_blocks:
        if RESIDUAL_UNIT_TEX_RE.search(block.raw):
            defects.append(
                _defect(
                    defect_id="P23",
                    cc_class="CC-04/CC-05",
                    check="Residual unit-only TeX fragment remains in polish",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="A simple scientific unit was left as inline TeX or kept a linked unit exponent.",
                    proposed_fix_layer="EN polish unit normalization after MathML/TeX conversion",
                    regression_test="Unit-only TeX fragments like \\(\\mu\\) C, \\muC cm^-2, and \\mu m^2 normalize to readable unit text.",
                )
            )
            break

    for block in polish_blocks:
        if MATH_TAG_WITH_CITATION_RE.search(block.raw) or any(
            _inline_tex_contains_citation_bracket(match.group(1))
            for match in INLINE_TEX_RE.finditer(block.raw)
        ):
            defects.append(
                _defect(
                    defect_id="P07",
                    cc_class="CC-05",
                    check="Citation appears inside math span",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Math conversion swallowed an adjacent citation into the formula.",
                    proposed_fix_layer="Marker raw math extraction or EN polish math/citation boundary cleanup",
                    regression_test="Citations like [17] after equations must stay outside math spans and link normally.",
                )
            )
            break

    raw_match = DISPLAY_MATH_OCR_RE.search(raw_html)
    polish_math_text = "\n".join(block.raw for block in polish_blocks)
    if raw_match and DISPLAY_MATH_OCR_RE.search(polish_math_text):
        defects.append(
            _defect(
                defect_id="P08",
                cc_class="CC-05/CC-13",
                check="Suspicious raw display-math OCR substitution",
                severity="warning",
                block=None,
                snippet=_snippet(raw_html, raw_match.start(), raw_match.end()),
                stage=RAW_STAGE,
                hypothesis="A displayed equation likely contains an OCR/math-recognition substitution.",
                proposed_fix_layer="raw audit surfacing or math-quality audit",
                regression_test="Catch omega_0 becoming 2m and similar impossible denominator tokens.",
            )
        )
    return defects


def _equation_table_defects(polish_blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    for block in polish_blocks:
        if block.block_type.lower() == "equation" and EQUATION_ABSORB_RE.search(block.text):
            defects.append(
                _defect(
                    defect_id="P09",
                    cc_class="CC-06",
                    check="Equation block absorbed following prose",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Equation/prose merge logic crossed a numbered display equation boundary.",
                    proposed_fix_layer="EN polish equation block assembly",
                    regression_test="Equation (1) and following explanatory paragraph must remain separate blocks.",
                )
            )
            break

    for block in polish_blocks:
        if block.block_type.lower() == "equation" and re.match(r"^\s*(?:Fig\.?|Figure)\s+\d+\s+shows\b", block.text, re.IGNORECASE):
            defects.append(
                _defect(
                    defect_id="P10",
                    cc_class="CC-06",
                    check="Mixed prose/math paragraph classified as equation",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="A prose paragraph containing math was treated as a pure equation block.",
                    proposed_fix_layer="Marker raw block typing or EN polish mixed block handling",
                    regression_test="Paragraphs like 'Fig. 4 shows ... f(...) = ...' stay text-with-math.",
                )
            )
            break

    for index, block in enumerate(polish_blocks):
        if not re.fullmatch(r"\(\d{1,3}\)", block.text):
            continue
        previous = polish_blocks[max(0, index - 4):index]
        if any(prev.tag == "table" or prev.id.startswith("table-") for prev in previous):
            defects.append(
                _defect(
                    defect_id="P11",
                    cc_class="CC-06/CC-07",
                    check="Orphan equation number appears after table/float",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="A table or float was inserted between an equation body and its number.",
                    proposed_fix_layer="EN polish equation-number atomicity and float-safe relocation",
                    regression_test="No table/title/paragraph may appear between equation body and equation number.",
                )
            )
            break
    return defects


def _figure_caption_ux_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
) -> list[Defect]:
    defects: list[Defect] = []
    split_match = BIORENDER_CAPTION_SPLIT_RE.search(polish_html)
    if split_match is not None:
        defects.append(
            _defect(
                defect_id="P31",
                cc_class="CC-12/CC-13",
                check="BioRender caption URL split into standalone heading",
                severity="warning",
                block=None,
                snippet=_snippet(_plain_text(polish_html), split_match.start(), split_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Marker split a figure caption credit/URL into a heading-like fragment.",
                proposed_fix_layer="EN polish caption-fragment merger",
                regression_test="BioRender URL heading between caption fragments is merged back into one figure caption paragraph.",
            )
        )

    def _caption_raw_for_tex_residue(block: Block) -> str:
        if block.tag == "table":
            return ""
        if "z2m-table-unit" in block.classes:
            caption_match = TABLE_CAPTION_NODE_RE.search(block.raw)
            if caption_match is not None:
                return caption_match.group(0)
            return re.split(r"<table\b", block.raw, maxsplit=1, flags=re.IGNORECASE)[0]
        return block.raw

    for block in polish_blocks:
        is_caption = bool(_looks_like_figure_caption(block) or TABLE_CAPTION_RE.match(block.text))
        caption_raw = _caption_raw_for_tex_residue(block) if is_caption else ""
        if caption_raw and CAPTION_TEX_RESIDUE_RE.search(caption_raw):
            defects.append(
                _defect(
                    defect_id="P12",
                    cc_class="CC-12",
                    check="Caption contains TeX/escaped-link residue",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Caption cleanup left TeX linebreaks, labels, formatting commands, or escaped anchor text visible.",
                    proposed_fix_layer="EN polish caption cleanup",
                    regression_test="Captions with BioRender links, \\label, \\textbf, and \\\\ linebreaks render as readable caption text.",
                )
            )
            break

    for index, block in enumerate(polish_blocks[:-1]):
        if "z2m-figure-caption" not in block.classes or "biorender" not in block.text.lower():
            continue
        next_block = polish_blocks[index + 1]
        if (
            "z2m-figure-caption" in next_block.classes
            and next_block.tag.startswith("h")
            and BIORENDER_CAPTION_URL_RE.search(next_block.text)
        ):
            defects.append(
                _defect(
                    defect_id="P31",
                    cc_class="CC-12/CC-13",
                    check="BioRender caption URL split into standalone heading",
                    severity="warning",
                    block=next_block,
                    snippet=f"{block.text[-160:]} {next_block.text}",
                    stage=POLISH_STAGE,
                    hypothesis="Marker split a figure caption credit/URL into a heading-like fragment.",
                    proposed_fix_layer="EN polish caption-fragment merger",
                    regression_test="BioRender URL heading between caption fragments is merged back into one figure caption paragraph.",
                )
            )
            break

    figure_id_counts = Counter(
        match.group("id")
        for match in re.finditer(r'\bid\s*=\s*(["\'])(?P<id>fig-[^"\']+)\1', polish_html, re.IGNORECASE)
    )

    for block in polish_blocks:
        if block.tag == "table":
            continue
        is_figure_caption = _looks_like_figure_caption(block)
        if (
            is_figure_caption
            and not _is_supplementary_figure_block(block)
            and not _is_handled_missing_figure_block(block)
            and figure_id_counts.get(block.id, 0) <= 1
            and not _has_nearby_image(polish_blocks, block.index)
            and not _has_nearby_missing_figure_warning(polish_blocks, block.index)
        ):
            defects.append(
                _defect(
                    defect_id="P13",
                    cc_class="CC-08/CC-13",
                    check="Figure caption has no nearby image",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="The final HTML may silently present a caption-only figure.",
                    proposed_fix_layer="raw audit surfacing and EN polish missing-figure warning block",
                    regression_test="Caption-without-image produces a visible user-facing warning.",
                )
            )
            break

    for index, block in enumerate(polish_blocks):
        if "z2m-missing-figure-warning" not in block.classes:
            continue
        window = polish_blocks[index + 1 : min(len(polish_blocks), index + 8)]
        if any(candidate.has_figure_visual for candidate in window):
            defects.append(
                _defect(
                    defect_id="P16",
                    cc_class="CC-08/CC-13",
                    check="Missing-figure warning appears before a delayed nearby image",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Figure/caption assembly used too narrow a search window and warned even though the image was present later.",
                    proposed_fix_layer="EN polish figure target assignment and missing-warning scan",
                    regression_test="Delayed image within a caption continuation run is targeted instead of warning.",
                )
            )
            break

    for block in polish_blocks:
        if not block.id.startswith("fig-") or block.has_figure_visual:
            continue
        if figure_id_counts.get(block.id, 0) > 1:
            continue
        if _is_supplementary_figure_block(block):
            continue
        if _is_handled_missing_figure_block(block):
            continue
        if _has_nearby_missing_figure_warning(polish_blocks, block.index):
            continue
        if re.search(rf"href\s*=\s*['\"]#{re.escape(block.id)}['\"]", polish_html, re.IGNORECASE):
            defects.append(
                _defect(
                    defect_id="P14",
                    cc_class="CC-10",
                    check="Figure link target is caption paragraph, not whole figure block",
                    severity="info",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Figure navigation targets the caption ID, so the image may be above the viewport.",
                    proposed_fix_layer="EN polish HTML/CSS target wrapper and scroll behavior",
                    regression_test="Clicking #fig-* reveals the image and caption together.",
                )
            )
            break

    has_internal_links = bool(REF_LINK_RE.search(polish_html) or FIG_LINK_RE.search(polish_html) or TABLE_LINK_RE.search(polish_html))
    if has_internal_links and (":target" not in polish_html or "scroll-margin" not in polish_html):
        defects.append(
            _defect(
                defect_id="P15",
                cc_class="CC-03/CC-10",
                check="Internal-link target UX styling is missing or incomplete",
                severity="info",
                block=None,
                snippet="internal links found, but no shared :target/scroll-margin behavior",
                stage=POLISH_STAGE,
                hypothesis="Internal links may scroll/focus/highlight inconsistently across articles.",
                proposed_fix_layer="EN polish readability CSS/optional JS",
                regression_test="Reference, figure, table, equation, and section targets share scroll offset and target highlight.",
            )
        )

    for block in polish_blocks:
        if MULTIPANEL_FIG_REF_RE.search(block.text) and "z2m-fig-link" not in block.raw:
            defects.append(
                _defect(
                    defect_id="P17",
                    cc_class="CC-10",
                    check="Plural multipanel figure reference is not linked",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Figure-reference grammar misses plural forms like 'figures 4(A), (B)'.",
                    proposed_fix_layer="EN polish figure-reference parser",
                    regression_test="Link plural multipanel references to the base figure target.",
                )
            )
            break

    for index, block in enumerate(polish_blocks[:-2]):
        if block.tag != "p" or _looks_like_figure_caption(block) or REFERENCES_HEADING_RE.match(block.text):
            continue
        left = block.text.strip()
        if not re.search(r"\b(?:and|or|but|with|of|the|sensor's)\s*$", left, re.IGNORECASE):
            continue
        saw_float = False
        for candidate in polish_blocks[index + 1 : min(len(polish_blocks), index + 12)]:
            if (
                candidate.has_figure_visual
                or "z2m-float-unit" in candidate.classes
                or candidate.tag in {"table", "figure"}
                or _looks_like_figure_caption(candidate)
                or TABLE_CAPTION_RE.match(candidate.text)
            ):
                saw_float = True
                continue
            if not saw_float:
                break
            if candidate.tag == "p" and candidate.text and candidate.text[0].islower():
                if _source_pdf_text_confirms_float_gap(left, candidate.text, pdf_text):
                    break
                defects.append(
                    _defect(
                        defect_id="P30",
                        cc_class="CC-07/CC-13",
                        check="Likely float interruption inside body sentence",
                        severity="warning",
                        block=block,
                        snippet=f"{left} ... {candidate.text[:160]}",
                        stage=POLISH_STAGE,
                        hypothesis="A figure/table unit may still split a sentence continuation.",
                        proposed_fix_layer="EN polish float-aware reading-order repair",
                        regression_test="A paragraph ending in a conjunction before a float rejoins a lowercase continuation after the float.",
                    )
                )
                return defects
            break

    page_match = PAGE_FURNITURE_CONTINUATION_RE.search(polish_html)
    if page_match is not None:
        defects.append(
            _defect(
                defect_id="P18",
                cc_class="CC-01/CC-13",
                check="Page furniture interrupts a sentence continuation",
                severity="warning",
                block=None,
                snippet=_snippet(polish_html, page_match.start(), page_match.end()),
                stage=POLISH_STAGE,
                hypothesis="A page footer/front-matter block was treated as prose or blocked joining across a page/float gap.",
                proposed_fix_layer="EN polish page-furniture cleanup and continuation repair",
                regression_test="Copyright/correspondence/footer blocks stay separate and sentence tails rejoin surrounding prose.",
            )
        )

    caption_intrusion = CAPTION_INTRUSION_RE.search(_plain_text(polish_html))
    if caption_intrusion is not None:
        defects.append(
            _defect(
                defect_id="P19",
                cc_class="CC-12/CC-13",
                check="Figure-caption prose intrusion remains after backslash cleanup",
                severity="warning",
                block=None,
                snippet=_snippet(_plain_text(polish_html), caption_intrusion.start(), caption_intrusion.end()),
                stage=POLISH_STAGE,
                hypothesis="A caption/body split was cleaned syntactically but not reassembled semantically.",
                proposed_fix_layer="EN polish caption-intrusion recovery",
                regression_test="Caption ending at '(required)' must not swallow body prose or drop the intended continuation.",
            )
        )
    return defects


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
    if numeric_citation_dominant and not pdf_author_year_evidence:
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


def _replacement_chars_are_pdf_source_noise(polish_html: str, pdf_text: str) -> bool:
    if "\ufffd" not in polish_html or not pdf_text:
        return False
    if "dynes\ufffdsec\ufffdcm-5" in polish_html and "dynes\x01sec\x01cm-5" in pdf_text:
        return True
    if "FRIMODT-M\ufffdLLER" in polish_html and "FRIMODT-MɘLLER" in pdf_text:
        return True
    if polish_html.count("\ufffd") >= 50 and (
        "\u00ad" in pdf_text
        or "FRIMODT-MɘLLER" in pdf_text
        or len(re.findall(r"\b\d\s+\d\s+\d\s+\d\b", pdf_text)) >= 8
    ):
        return True
    return False


def _manual_blind_spot_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
) -> list[Defect]:
    defects: list[Defect] = []
    slim_html = _structure_html(polish_html)

    for match in PAGE_LINK_RE.finditer(slim_html):
        kind = _page_link_semantic_kind(slim_html, match)
        if kind is None:
            continue
        defects.append(
            _defect(
                defect_id="P33",
                cc_class="CC-02/CC-03/CC-10",
                check="Semantic reference still points to PDF page anchor",
                severity="warning" if kind.startswith("semantic") else "error",
                block=None,
                snippet=_snippet(slim_html, match.start(), match.end()),
                stage=POLISH_STAGE,
                hypothesis="A citation, table/figure/box/section reference, or OCR-glued citation was left as a #page-* link.",
                proposed_fix_layer="EN polish semantic cross-reference retargeting",
                regression_test="Box/Table/Section/Appendix and bibliography refs must target #box/#table/#section/#ref rather than #page.",
                extra={"page_target": match.group("target"), "label": _strip_tags(match.group("body")), "kind": kind},
            )
        )
        break

    nested_anchor_match = next(
        (match for match in ANCHOR_BODY_RE.finditer(slim_html) if "<a" in match.group("body").lower()),
        None,
    )
    double_close_match = DOUBLE_CLOSE_ANCHOR_RE.search(slim_html)
    malformed_anchor_match = nested_anchor_match or double_close_match
    if malformed_anchor_match is not None:
        defects.append(
            _defect(
                defect_id="P34",
                cc_class="CC-02/CC-03",
                check="Malformed nested or double-closed anchor",
                severity="error",
                block=None,
                snippet=_snippet(slim_html, malformed_anchor_match.start(), malformed_anchor_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Citation/link reconstruction wrapped an already-linked fragment or left an extra closing anchor.",
                proposed_fix_layer="EN polish anchor normalization after citation retargeting",
                regression_test="Citation lists such as [24, 25] and [30] never contain nested <a> tags or stray </a>.",
            )
        )

    replacement_pos = polish_html.find("\ufffd")
    if replacement_pos != -1:
        replacement_extra: dict[str, Any] = {"count": polish_html.count("\ufffd")}
        if _replacement_chars_are_pdf_source_noise(polish_html, pdf_text):
            replacement_extra.update(
                {
                    "quality_counted": False,
                    "source_pdf_text_layer_evidence": "replacement characters align with source PDF text-layer symbol/OCR loss",
                }
            )
        defects.append(
            _defect(
                defect_id="P35",
                cc_class="CC-04/CC-13",
                check="Unicode replacement character remains visible",
                severity="warning",
                block=None,
                snippet=_snippet(polish_html, replacement_pos, replacement_pos + 1),
                stage=POLISH_STAGE,
                hypothesis="A symbol was lost during PDF/OCR/html decoding, often a comparison sign or table significance mark.",
                proposed_fix_layer="raw symbol diagnostics and EN polish table-symbol repair",
                regression_test="Audit reports U+FFFD in table headers, footnotes, and scientific symbols.",
                extra=replacement_extra,
            )
        )

    plain = _plain_text(slim_html)
    url_check_plain = _plain_text(URL_ANCHOR_RE.sub(" URL ", slim_html))
    broken_url_match = BROKEN_URL_TEXT_RE.search(url_check_plain)
    malformed_url_anchor_match = MALFORMED_URL_ANCHOR_BODY_RE.search(slim_html)
    if broken_url_match is not None or malformed_url_anchor_match is not None:
        if broken_url_match is not None:
            snippet = _snippet(url_check_plain, broken_url_match.start(), broken_url_match.end())
        else:
            assert malformed_url_anchor_match is not None
            snippet = _strip_tags(
                _snippet(slim_html, malformed_url_anchor_match.start(), malformed_url_anchor_match.end())
            )
        defects.append(
            _defect(
                defect_id="P36",
                cc_class="CC-03/CC-13",
                check="Visible URL or DOI is split or malformed",
                severity="warning",
                block=None,
                snippet=snippet,
                stage=POLISH_STAGE,
                hypothesis="Line/page splitting, OCR, or autolinking left a visibly broken URL/DOI label.",
                proposed_fix_layer="EN polish URL/DOI label normalization",
                regression_test="URLs like 'https:// creativecommons.org', 'hps://dl.acm.org', and 'doi.org/ 10...' are joined or reported.",
            )
        )

    references_started = False
    for block in polish_blocks:
        if REFERENCES_HEADING_RE.match(block.text):
            references_started = True
        if _is_references_block(block, references_started) or block.classes & {
            "z2m-front-matter",
            "z2m-affiliations",
            "z2m-footnote",
        }:
            continue
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw):
            label = _strip_tags(match.group("body"))
            if not LOWERCASE_REF_GLUE_RE.fullmatch(label):
                continue
            defects.append(
                _defect(
                    defect_id="P37",
                    cc_class="CC-02/CC-13",
                    check="Citation link absorbed the final letter of a word",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Superscript OCR split the last letter from the preceding word and citation linking preserved that split.",
                    proposed_fix_layer="EN polish citation OCR glue repair",
                    regression_test="Patterns like 'functio n13,14' and 'consideration s20,23' rejoin the letter to the word.",
                    extra={"label": label, "ref_target": match.group("num")},
                )
            )
            break
        if defects and defects[-1].id == "P37":
            break

    for match in BOX_UNIT_RE.finditer(slim_html):
        box_text = _strip_tags(match.group("body"))
        tail = slim_html[match.end() : match.end() + 600]
        if len(box_text) <= 40 and re.fullmatch(r"(?:BOX|Box)\s+\d+[A-Za-z]?", box_text) and re.match(
            r"\s*<h[1-6]\b", tail, re.IGNORECASE
        ):
            defects.append(
                _defect(
                    defect_id="P38",
                    cc_class="CC-09/CC-12",
                    check="Box wrapper contains only the box label",
                    severity="warning",
                    block=None,
                    snippet=_snippet(slim_html, match.start(), min(len(slim_html), match.end() + 220)),
                    stage=POLISH_STAGE,
                    hypothesis="Box framing stopped at the label and left the box title/content outside the wrapper.",
                    proposed_fix_layer="EN polish box-unit assembly",
                    regression_test="Box 1 label, title, and body paragraphs are wrapped as one z2m-box-unit with top/bottom rules.",
                )
            )
            break

    for match in FIGURE_UNIT_RE.finditer(slim_html):
        figure_id = match.group("id")
        tail = slim_html[match.end() : match.end() + 5000]
        caption_match = IMMEDIATE_EXTERNAL_FIGURE_CAPTION_RE.search(tail)
        if caption_match is None:
            continue
        caption_raw = caption_match.group(0)
        caption_text = _strip_tags(caption_raw)
        figure_num_match = re.search(r"\d+", figure_id)
        figure_num = figure_num_match.group(0) if figure_num_match else ""
        points_to_same_figure = (
            re.search(rf"href\s*=\s*['\"]#{re.escape(figure_id)}['\"]", caption_raw, re.IGNORECASE) is not None
            or bool(figure_num and re.match(rf"\s*(?:Fig\.?|Figure)\s*{re.escape(figure_num)}\b", caption_text, re.IGNORECASE))
        )
        if not points_to_same_figure:
            continue
        defects.append(
            _defect(
                defect_id="P39",
                cc_class="CC-08/CC-12",
                check="Figure wrapper closes before its remaining image or caption",
                severity="warning",
                block=None,
                snippet=_snippet(slim_html, match.start(), min(len(slim_html), match.end() + caption_match.end())),
                stage=POLISH_STAGE,
                hypothesis="Multi-image or caption assembly left part of the same figure outside the z2m-figure-unit.",
                proposed_fix_layer="EN polish figure-unit expansion after target assignment",
                regression_test="Multi-panel figures keep all adjacent images and the matching caption inside the same figure wrapper.",
                extra={"figure_id": figure_id},
            )
        )
        break

    saw_float_split = False
    for index, block in enumerate(polish_blocks[:-2]):
        if block.tag != "p" or block.classes & {"z2m-front-matter", "z2m-affiliations"}:
            continue
        if _looks_like_figure_caption(block) or TABLE_CAPTION_RE.match(block.text):
            continue
        if not _ends_like_sentence_fragment(block.text):
            continue
        saw_float = False
        for candidate in polish_blocks[index + 1 : min(len(polish_blocks), index + 14)]:
            if _looks_like_float_or_caption(candidate):
                saw_float = True
                continue
            if not saw_float:
                break
            if _looks_like_float_note(candidate):
                continue
            if _looks_like_equation_continuation(candidate):
                break
            if candidate.tag == "p" and _starts_like_sentence_continuation(candidate.text):
                if _source_pdf_text_confirms_float_gap(block.text, candidate.text, pdf_text):
                    break
                defects.append(
                    _defect(
                        defect_id="P40",
                        cc_class="CC-07/CC-13",
                        check="Float likely interrupts a sentence continuation",
                        severity="warning",
                        block=block,
                        snippet=f"{block.text[-140:]} ... {candidate.text[:140]}",
                        stage=POLISH_STAGE,
                        hypothesis="A figure/table was left between two fragments of the same sentence.",
                        proposed_fix_layer="EN polish float-aware reading-order repair",
                        regression_test="Paragraph fragments around a float rejoin when the before-text has no sentence terminator and after-text starts as a continuation.",
                    )
                )
                saw_float_split = True
                break
            break
        if saw_float_split:
            break

    for block in polish_blocks:
        if TABLE_DOI_APPEND_RE.search(block.text):
            defects.append(
                _defect(
                    defect_id="P41",
                    cc_class="CC-07/CC-13",
                    check="Body prose is appended to a table DOI/note paragraph",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="A table note/DOI block swallowed the continuation of body prose after a misplaced table.",
                    proposed_fix_layer="EN polish table-note boundary and reading-order repair",
                    regression_test="Text following a table DOI, such as 'three parameters). These tendencies...', is restored to the surrounding body paragraph.",
                )
            )
            break

    return defects


def _looks_like_affiliation_label_roman_boundary(block: Block, split_match: re.Match[str]) -> bool:
    if split_match.group("suffix").lower() != "i":
        return False
    text = block.text
    if AFFILIATION_LABEL_CONTEXT_RE.search(text) is None:
        classes = set(block.attrs.get("class", "").split())
        if "z2m-front-matter" not in classes:
            return False
    right_text = text[split_match.end() : split_match.end() + 90]
    if AFFILIATION_LABEL_RIGHT_RE.match(right_text) is None:
        return False
    if split_match.group("prefix").lower() in AFFILIATION_LABEL_LOCATION_PREFIXES:
        return True
    nearby_text = text[max(0, split_match.start() - 1200) : split_match.end() + 200]
    affiliation_label_count = len(re.findall(r"\b[a-z]\s+(?=[A-Z][A-Za-z])", nearby_text))
    return affiliation_label_count >= 4


def _meine_recent_manual_defects(
    polish_html: str,
    polish_blocks: list[Block],
    *,
    pdf_text: str = "",
) -> list[Defect]:
    defects: list[Defect] = []
    slim_html = _structure_html(polish_html)
    plain = _plain_text(slim_html)
    ref_targets = _reference_target_numbers(slim_html)
    fig_targets = _figure_target_keys(slim_html)
    body_blocks = list(_non_reference_body_blocks(polish_blocks))

    for block in body_blocks:
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw):
            label = _strip_tags(match.group("body"))
            if AUTHOR_YEAR_TEXT_RE.search(label) is not None:
                continue
            visible_number = _ref_anchor_visible_number(label)
            target_number = int(match.group("num"))
            if visible_number is None or visible_number == target_number:
                continue
            if 1800 <= visible_number <= 2099:
                continue
            defects.append(
                _defect(
                    defect_id="P42",
                    cc_class="CC-02/CC-13",
                    check="Visible citation label points to a different bibliography target",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Bibliography continuation drift or ordinal reassignment changed #ref targets without preserving visible citation identity.",
                    proposed_fix_layer="EN polish bibliography identity audit before citation linkification",
                    regression_test="Visible citation labels such as ',9' must link to #ref-9, not shifted continuation targets.",
                    extra={"visible_number": visible_number, "ref_target": target_number, "label": label},
                )
            )
            break
        if defects and defects[-1].id == "P42":
            break

    for match in PAGE_LINK_RE.finditer(slim_html):
        label = _strip_tags(match.group("body"))
        left = _strip_tags(slim_html[max(0, match.start() - 100) : match.start()])
        if not (
            re.fullmatch(r"\d+\.\d+\)?\.?", label)
            and re.search(r"\b(?:Eqn?\.?|Equation)\s*$", left, re.IGNORECASE)
        ):
            continue
        defects.append(
            _defect(
                defect_id="P43",
                cc_class="CC-03/CC-06/CC-10",
                check="Decimal equation reference remains a PDF page link",
                severity="warning",
                block=None,
                snippet=_snippet(slim_html, match.start(), match.end()),
                stage=POLISH_STAGE,
                hypothesis="Equation-reference retargeting handles simple integers but misses decimal equation labels such as Eqn. 2.1.",
                proposed_fix_layer="EN polish equation-reference parser",
                regression_test="Eqn. 2.1 and Eqn. 2.4 page anchors retarget to equation IDs or unwrap if no reliable target exists.",
                extra={"page_target": match.group("target"), "label": label},
            )
        )
        break

    for block in polish_blocks[:25]:
        for match in PAGE_LINK_RE.finditer(block.raw):
            label = _strip_tags(match.group("body"))
            if re.fullmatch(r"i\s*\d+\s*,?", label, re.IGNORECASE) is None:
                continue
            defects.append(
                _defect(
                    defect_id="P44",
                    cc_class="CC-01/CC-03",
                    check="Front-matter affiliation marker remains as page-anchor glue",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Superscript affiliation labels in the front matter were OCR-glued into page-anchor links.",
                    proposed_fix_layer="EN polish front-matter marker repair before page-link preservation",
                    regression_test="Author/affiliation fragments like 'i1,' and 'i3,' do not remain linked to #page anchors.",
                    extra={"page_target": match.group("target"), "label": label},
                )
            )
            break
        if defects and defects[-1].id == "P44":
            break

    references_started = False
    roman_split_telemetry: tuple[str, str, str, str, str, Block, re.Match[str]] | None = None
    for block in polish_blocks:
        if REFERENCES_HEADING_RE.match(block.text):
            references_started = True
        if (
            _is_references_block(block, references_started)
            or block.tag in {"table", "td", "th"}
            or re.search(r"<table\b|<t[dh]\b", block.raw, re.IGNORECASE) is not None
        ):
            continue
        split_match = ROMAN_WORD_SPLIT_RE.search(block.text)
        if split_match is None:
            continue
        prefix = split_match.group("prefix").lower()
        if prefix in ROMAN_WORD_SPLIT_FALSE_PREFIXES:
            continue
        suffix = split_match.group("suffix").lower()
        right_text = block.text[split_match.end() : split_match.end() + 12]
        if suffix == "x" and right_text.startswith("-"):
            continue
        if suffix == "v" and re.match(r"\.\s*\d", right_text):
            continue
        raw_prefix = re.escape(split_match.group("prefix"))
        raw_suffix = re.escape(split_match.group("suffix"))
        if re.search(
            rf"\b{raw_prefix}\s*<sub\b[^>]*>\s*{raw_suffix}\s*</sub>",
            block.raw,
            re.IGNORECASE,
        ):
            continue
        if re.search(
            rf"\b{raw_prefix}\s*<sup\b[^>]*>\s*{raw_suffix}\s*</sup>",
            block.raw,
            re.IGNORECASE,
        ):
            if roman_split_telemetry is None:
                roman_split_telemetry = (
                    "P45S",
                    "Roman-like suffix is already a superscript marker",
                    "A rendered superscript affiliation/footnote marker resembles a split word in visible text.",
                    "EN audit P45 superscript-marker classifier",
                    "Superscript affiliation markers such as Teixeira<sup>i</sup> must not inflate P45.",
                    block,
                    split_match,
                )
            continue
        if re.search(
            rf"\b{raw_prefix}\s*<a\b[^>]*\bz2m-ref-link\b[^>]*>\s*{raw_suffix}\s*</a>",
            block.raw,
            re.IGNORECASE,
        ):
            if roman_split_telemetry is None:
                roman_split_telemetry = (
                    "P45L",
                    "Roman-like suffix is wrapped by a reference link",
                    "A reference-link boundary makes visible text resemble a split surname; repair belongs to citation/link cleanup.",
                    "EN audit P45 linked-suffix classifier",
                    "Author-year link fragments such as Pisan<a>i</a> must not inflate P45.",
                    block,
                    split_match,
                )
            continue
        if re.search(
            rf"\b{raw_prefix}\s*<span\b[^>]*\bz2m-math\b[^>]*>",
            block.raw,
            re.IGNORECASE,
        ):
            if roman_split_telemetry is None:
                roman_split_telemetry = (
                    "P45M",
                    "Roman-like suffix is a rendered math variable",
                    "A rendered math variable resembles a split word in visible text.",
                    "EN audit P45 math-variable classifier",
                    "Math spans such as Function <span class='z2m-math'>v</span> must not inflate P45.",
                    block,
                    split_match,
                )
            continue
        if _looks_like_affiliation_label_roman_boundary(block, split_match):
            if roman_split_telemetry is None:
                roman_split_telemetry = (
                    "P45A",
                    "Roman-like suffix is an affiliation label boundary",
                    "Front-matter affiliation labels after countries can resemble a split surname in visible text.",
                    "EN audit P45 affiliation-label classifier",
                    "Affiliation lists such as 'Denmark i National Institute' must not inflate P45.",
                    block,
                    split_match,
                )
            continue
        defects.append(
            _defect(
                defect_id="P45",
                cc_class="CC-04/CC-13",
                check="Word or surname is split before a roman-like suffix",
                severity="warning",
                block=block,
                snippet=block.text,
                stage=POLISH_STAGE,
                hypothesis="Roman-suffix/table-footnote heuristics split ordinary words or surnames ending in i/v/x.",
                proposed_fix_layer="EN polish roman/table-footnote disambiguation",
                regression_test="Surnames such as Belyaev, Yakovlev, and Nedelev remain intact.",
                extra={"match": split_match.group(0)},
            )
        )
        break

    if roman_split_telemetry is not None and not any(defect.id == "P45" for defect in defects):
        defect_id, check, hypothesis, proposed_fix_layer, regression_test, block, split_match = roman_split_telemetry
        defects.append(
            _defect(
                defect_id=defect_id,
                cc_class="CC-04/CC-13",
                check=check,
                severity="warning",
                block=block,
                snippet=block.text,
                stage=POLISH_STAGE,
                hypothesis=hypothesis,
                proposed_fix_layer=proposed_fix_layer,
                regression_test=regression_test,
                extra={"match": split_match.group(0), "quality_counted": False},
            )
        )

    mixed_var_match = MIXEDCASE_VAR_FOOTNOTE_RE.search(slim_html)
    if mixed_var_match is not None:
        defects.append(
            _defect(
                defect_id="P46",
                cc_class="CC-04/CC-11",
                check="Mixed-case scientific variable was split as a table footnote",
                severity="error",
                block=None,
                snippet=_snippet(slim_html, mixed_var_match.start(), mixed_var_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Table footnote detection treats terminal x/i/v as a footnote marker even when it is part of a variable such as Qmax.",
                proposed_fix_layer="EN polish table-footnote parser with variable/name guards",
                regression_test="Qmax/Qave/Qmn-style variables stay plain text in table cells and captions.",
            )
        )

    for caption_match in TABLE_CAPTION_ID_RE.finditer(slim_html):
        tail = slim_html[caption_match.end() : caption_match.end() + 4000]
        wrapper_match = TABLE_WRAPPER_ID_RE.search(tail)
        if wrapper_match is None:
            continue
        caption_num = caption_match.group("num")
        wrapper_num = wrapper_match.group("num")
        if caption_num == wrapper_num:
            continue
        defects.append(
            _defect(
                defect_id="P47",
                cc_class="CC-07/CC-11/CC-13",
                check="Table caption target drifts to a different table wrapper",
                severity="error",
                block=None,
                snippet=_snippet(slim_html, caption_match.start(), caption_match.end() + wrapper_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Caption/table assembly assigned a caption ID by visible label but wrapped the following table under a different ordinal.",
                proposed_fix_layer="EN polish table-unit assembly and caption-table adjacency validation",
                regression_test="A caption with id=table-4 is followed by or wrapped with table-4, never table-5.",
                extra={"caption_table": caption_num, "wrapper_table": wrapper_num},
            )
        )
        break

    for caption_match in TABLE_CAPTION_ID_RE.finditer(slim_html):
        tail = slim_html[caption_match.end() : caption_match.end() + 1600]
        first_table = re.search(r"<table\b", tail, re.IGNORECASE)
        first_wrapper = TABLE_WRAPPER_ID_RE.search(tail)
        if first_table is None or (first_wrapper is not None and first_wrapper.start() < first_table.start()):
            continue
        defects.append(
            _defect(
                defect_id="P48",
                cc_class="CC-07/CC-11",
                check="Table caption is followed by an unwrapped table",
                severity="warning",
                block=None,
                snippet=_snippet(slim_html, caption_match.start(), caption_match.end() + first_table.end()),
                stage=POLISH_STAGE,
                hypothesis="A visible table caption was given a target ID, but the adjacent table body was not included in the semantic wrapper.",
                proposed_fix_layer="EN polish table-unit wrapping",
                regression_test="Captions above tables wrap the following table body into the same z2m-table-unit.",
                extra={"caption_table": caption_match.group("num")},
            )
        )
        break

    for block in body_blocks:
        partial_table_match = TABLE_REF_PARTIAL_LINK_RE.search(block.raw)
        if partial_table_match is None:
            continue
        defects.append(
            _defect(
                defect_id="P49",
                cc_class="CC-03/CC-10",
                check="Only the digit of a table reference is linked",
                severity="warning",
                block=block,
                snippet=block.text,
                stage=POLISH_STAGE,
                hypothesis="Cross-reference linkification wrapped only the number and left the semantic label outside the anchor.",
                proposed_fix_layer="EN polish table-reference parser",
                regression_test="'Table 4', 'Tables 4 and 5', and similar labels are linked as whole semantic references.",
                extra=partial_table_match.groupdict(),
            )
        )
        break

    for block in body_blocks:
        if _block_is_float_or_table_context(block):
            continue
        linkless_raw = re.sub(r"<a\b[^>]*>.*?</a>", " ", block.raw, flags=re.IGNORECASE | re.DOTALL)
        linkless_text = _strip_tags(linkless_raw)
        flattened_match = FLATTENED_SUP_CITATION_RE.search(linkless_text)
        if flattened_match is None:
            continue
        if _flattened_sup_match_is_joined_figure_label(flattened_match):
            continue
        if _flattened_sup_match_is_doi_or_url_fragment(linkless_text, flattened_match):
            continue
        if (
            re.search(r"https?://(?:dx\.)?doi\.org/10\.\d{4,9}/", block.raw, re.IGNORECASE)
            and re.search(r"[A-Za-z]{3,}\.\d", flattened_match.group(0))
        ):
            continue
        number = int(flattened_match.group("num"))
        if number not in ref_targets:
            continue
        window = linkless_text[max(0, flattened_match.start() - 120) : flattened_match.end() + 160]
        if not re.search(r"\bet\s+al\.?\s*\d", flattened_match.group(0), re.IGNORECASE):
            if (
                MATH_OR_MEASUREMENT_RANGE_CONTEXT_RE.search(window)
                or _block_looks_like_math_or_measurement_range_context(block)
            ):
                continue
        if _looks_like_table_flattened_citation_context(linkless_text):
            continue
        defects.append(
            _defect(
                defect_id="P50",
                cc_class="CC-02/CC-13",
                check="Flattened superscript citation remains unlinked",
                severity="warning",
                block=block,
                snippet=block.text,
                stage=POLISH_STAGE,
                hypothesis="Superscript citation OCR was flattened into prose, so the citation parser did not see a bracket/sup marker.",
                proposed_fix_layer="EN polish citation OCR recovery",
                regression_test="Patterns like 'Agarwal et al3' and 'voiders.3' recover to reference links when ref-3 exists.",
                extra={"visible_number": number, "match": flattened_match.group(0)},
            )
        )
        break

    for match in PAGE_LINK_RE.finditer(slim_html):
        if _page_link_semantic_kind(slim_html, match) is not None:
            continue
        label = _strip_tags(match.group("body"))
        if len(re.findall(r"[A-Za-z]{2,}", label)) < 3:
            continue
        if AUTHOR_YEAR_TEXT_RE.search(label) is not None:
            continue
        if re.search(r"\b(?:copyright|creative commons|doi|https?)\b", label, re.IGNORECASE):
            continue
        defects.append(
            _defect(
                defect_id="P51",
                cc_class="CC-03/CC-07/CC-13",
                check="Prose fragment remains wrapped as a PDF page link",
                severity="warning",
                block=None,
                snippet=_snippet(slim_html, match.start(), match.end()),
                stage=POLISH_STAGE,
                hypothesis="Page-anchor preservation kept an OCR/page-break prose fragment linked instead of unwrapping it into body text.",
                proposed_fix_layer="EN polish page-link cleanup",
                regression_test="Plain prose fragments such as 'that formulas that use the total' are unwrapped from #page anchors.",
                extra={"page_target": match.group("target"), "label": label},
            )
        )
        break

    doi_split_match = DOI_SPLIT_PLAIN_RE.search(plain)
    if doi_split_match is not None:
        defects.append(
            _defect(
                defect_id="P52",
                cc_class="CC-03/CC-13",
                check="Plain DOI label is split after slash",
                severity="warning",
                block=None,
                snippet=_snippet(plain, doi_split_match.start(), doi_split_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Line wrapping split a DOI suffix and the URL/DOI repair pass did not join the visible label.",
                proposed_fix_layer="EN polish DOI normalization",
                regression_test="Labels like 'doi: 10.1002/ nau.22813' become one clickable DOI without changing the DOI text.",
            )
        )

    german_probe = plain[:20000]
    german_hits = GERMAN_SOURCE_HINT_RE.findall(german_probe)
    german_keys = {hit.upper() for hit in german_hits}
    german_anchor_hints = {
        "DEUTSCHE",
        "DRESDEN",
        "KLINIK",
        "KOLLODIUM",
        "KOLLODIUMVERFAHREN",
        "LEITTHEMA",
        "LEITLINIEN",
        "PHOTOGRAPHIE",
        "PROSTATASYNDROMS",
        "UROLOGE",
        "ZUSAMMENFASSUNG",
    }
    if len(german_hits) >= 8 and german_keys & german_anchor_hints:
        defects.append(
            _defect(
                defect_id="P53",
                cc_class="CC-00/CC-14",
                check="Likely non-English source reached the English polish audit",
                severity="error",
                block=None,
                snippet=_snippet(plain, 0, min(len(plain), 600)),
                stage=RAW_STAGE,
                hypothesis="Source-language gating did not exclude a German document before the English marker/polish profile.",
                proposed_fix_layer="Pre-marker source-language detection and run routing",
                regression_test="German sources are tagged as source_language=de before marker and are not sent through the EN polish profile.",
                extra={"german_hint_count": len(german_hits), "german_hints": sorted(german_keys)[:12]},
            )
        )

    for word_match in WORD_FOOTNOTE_SPLIT_RE.finditer(slim_html):
        prefix = word_match.group("prefix")
        combined = f"{prefix}{word_match.group('suffix')}".lower()
        if combined not in SUSPICIOUS_FOOTNOTE_WORD_MERGES:
            continue
        if prefix.lower() in {"qma", "qa", "qav", "qmn"}:
            continue
        if prefix.isupper() and len(prefix) >= 2:
            continue
        if prefix.lower() in {"pdms", "polyimide", "parylene"}:
            continue
        defects.append(
            _defect(
                defect_id="P54",
                cc_class="CC-04/CC-11/CC-13",
                check="Ordinary word was split as a table footnote",
                severity="warning",
                block=None,
                snippet=_snippet(slim_html, word_match.start(), word_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Table-footnote roman suffix repair is too broad and can split ordinary words, especially in non-English sources.",
                proposed_fix_layer="EN polish table-footnote parser with lexical and language-aware guards",
                regression_test="Words such as Mastix/Borax/Kupfervitriol and author surnames are not split into z2m-table-fn spans.",
                extra={"prefix": prefix, "suffix": word_match.group("suffix")},
            )
        )
        break

    for block in body_blocks:
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw):
            label = _strip_tags(match.group("body"))
            right_text = _strip_tags(block.raw[match.end() : match.end() + 100])
            surname_author_year_fragment = (
                re.fullmatch(r"[A-Z][A-Za-z'’.-]{3,}", label) is not None
                and re.match(r"^\s*et\s+al\.?\s*\(?\d{4}[a-z]?\)?", right_text, re.IGNORECASE) is not None
            )
            if AUTHOR_YEAR_TEXT_RE.search(label) is None and not surname_author_year_fragment:
                continue
            defects.append(
                _defect(
                    defect_id="P55",
                    cc_class="CC-02/CC-13",
                    check="Author-year citation is linked to a numeric bibliography target",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Article-level citation strategy confused author-year citations with numeric reference targets.",
                    proposed_fix_layer="EN polish article-level citation-style detection",
                    regression_test="Author-year citations match bibliography by surname/year or remain plain when confidence is low; they never map to arbitrary #ref-N.",
                    extra={"ref_target": match.group("num"), "label": label},
                )
            )
            break
        if defects and defects[-1].id == "P55":
            break

    for match in PAGE_LINK_RE.finditer(slim_html):
        label = _strip_tags(match.group("body"))
        if AUTHOR_YEAR_TEXT_RE.search(label) is None:
            continue
        defects.append(
            _defect(
                defect_id="P56",
                cc_class="CC-02/CC-03/CC-13",
                check="Author-year citation remains a PDF page link",
                severity="warning",
                block=None,
                snippet=_snippet(slim_html, match.start(), match.end()),
                stage=POLISH_STAGE,
                hypothesis="Author-year citation retargeting is missing or low-confidence, leaving stale #page anchors in body prose.",
                proposed_fix_layer="EN polish author-year citation parser",
                regression_test="Author-year page anchors either link by surname/year or unwrap to plain text without #page targets.",
                extra={"page_target": match.group("target"), "label": label},
            )
        )
        break

    for match in FIGURE_UNIT_RE.finditer(slim_html):
        wrapper_num_match = re.search(r"\d+", match.group("id"))
        if wrapper_num_match is None:
            continue
        wrapper_num = int(wrapper_num_match.group(0))
        body = match.group("body")
        alias_nums = {
            int(number)
            for number in re.findall(r"\bid\s*=\s*['\"]fig-(\d+)['\"]", body, re.IGNORECASE)
        }
        caption_nums = {
            number
            for caption_match in FIGURE_CAPTION_NODE_RE.finditer(body)
            for number in [_figure_caption_number_from_caption_node(caption_match.group("body"))]
            if number is not None
        }
        unrelated = sorted((alias_nums | caption_nums) - {wrapper_num})
        if not unrelated:
            continue
        if _figure_unit_allows_shared_image_alias(body, wrapper_num, unrelated):
            continue
        defects.append(
            _defect(
                defect_id="P57",
                cc_class="CC-08/CC-10/CC-13",
                check="Figure wrapper contains an unrelated figure alias or caption number",
                severity="error",
                block=None,
                snippet=_snippet(slim_html, match.start(), match.end()),
                stage=POLISH_STAGE,
                hypothesis="Figure assembly merged captions/aliases for distinct figures into one wrapper.",
                proposed_fix_layer="EN polish figure-unit assembly and alias validation",
                regression_test="fig-1 wrappers do not contain fig-4 aliases or visible Fig. 4 captions unless the PDF proves a shared compound figure.",
                extra={"wrapper_figure": wrapper_num, "unrelated_figures": unrelated[:10]},
            )
        )
        break

    for block in body_blocks:
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw):
            label_number = _ref_anchor_visible_number(_strip_tags(match.group("body")))
            if label_number is None:
                continue
            left_tail = _strip_tags(block.raw[max(0, match.start() - 100) : match.start()])
            if FIGS_REF_FALSE_REF_RE.search(left_tail) is None:
                continue
            defects.append(
                _defect(
                    defect_id="P58",
                    cc_class="CC-02/CC-03/CC-10",
                    check="Figure list/range number links to bibliography reference",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Figure-reference grammar failed, and the remaining number was picked up by bibliography citation linkification.",
                    proposed_fix_layer="EN polish figure-reference parser before citation linkification",
                    regression_test="Patterns like '(Figs. 3 and 5)' link to figure targets, not #ref-5.",
                    extra={"visible_number": label_number, "ref_target": match.group("num")},
                )
            )
            break
        if defects and defects[-1].id == "P58":
            break

    body_text = " ".join(block.text for block in body_blocks)
    bracket_citation_count = len(re.findall(r"\[\s*\d", body_text))
    author_year_count = len(AUTHOR_YEAR_TEXT_RE.findall(body_text))
    numeric_ref_link_count = sum(
        1
        for block in body_blocks
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw)
        if _ref_anchor_visible_number(_strip_tags(match.group("body"))) is not None
    )
    numeric_sup_ref_link_count = sum(
        1
        for block in body_blocks
        for match in REF_ANCHOR_BODY_RE.finditer(block.raw)
        if _ref_anchor_visible_number(_strip_tags(match.group("body"))) is not None
        and "<sup" in block.raw[max(0, match.start() - 40) : match.start()].lower()
    )
    numeric_citation_dominant = (
        numeric_ref_link_count >= 5
        and numeric_sup_ref_link_count >= 5
    ) or (
        numeric_ref_link_count >= 10
        and numeric_sup_ref_link_count >= 3
    )
    if author_year_count >= 4 and bracket_citation_count < 4 and not numeric_citation_dominant:
        for block in body_blocks:
            for match in REF_ANCHOR_BODY_RE.finditer(block.raw):
                label = _strip_tags(match.group("body"))
                if re.fullmatch(r"\d{1,3}", label) is None or int(label) > 3:
                    continue
                raw_window = block.raw[max(0, match.start() - 80) : match.end() + 80].lower()
                text_window = _strip_tags(block.raw[max(0, match.start() - 160) : match.end() + 160])
                if re.search(r"\b(?:Fig\.?|Figs\.?|Figure|Table|Eqn?\.?|Equation)\b", text_window, re.IGNORECASE):
                    continue
                if "<sup" not in raw_window and re.search(r"\b(?:source|web|github|facebook|living|data)\b", text_window, re.IGNORECASE) is None:
                    continue
                defects.append(
                    _defect(
                        defect_id="P59",
                        cc_class="CC-02/CC-13",
                        check="Numeric footnote marker links to bibliography in author-year article",
                        severity="error",
                        block=block,
                        snippet=block.text,
                        stage=POLISH_STAGE,
                        hypothesis="Mixed footnote/bibliography strategy treated source/web footnotes as numbered bibliography citations.",
                        proposed_fix_layer="EN polish citation-style and footnote-style separation",
                        regression_test="Frontiers-style source footnotes 1/2/3 link to footnotes or remain footnotes, not #ref-1/#ref-2/#ref-3.",
                        extra={"ref_target": match.group("num"), "label": label},
                    )
                )
                break
            if defects and defects[-1].id == "P59":
                break

    for block in body_blocks:
        comma_match = COMMA_DECIMAL_REF_RE.search(block.raw)
        single_stat_match = SINGLE_STAT_REF_RE.search(block.raw)
        if comma_match is not None and _ref_match_inside_bracketed_numeric_citation(
            block.raw,
            comma_match.start(),
            comma_match.end(),
        ):
            comma_match = None
        if single_stat_match is not None and _ref_match_inside_bracketed_numeric_citation(
            block.raw,
            single_stat_match.start(),
            single_stat_match.end(),
        ):
            single_stat_match = None
        if comma_match is not None:
            if not _looks_like_comma_decimal_stat_ref(block.raw, comma_match):
                comma_match = None
        if single_stat_match is not None and not _looks_like_sample_size_value_ref(block.raw, single_stat_match):
            single_stat_match = None
        if comma_match is None and single_stat_match is None:
            continue
        defects.append(
            _defect(
                defect_id="P60",
                cc_class="CC-02/CC-04/CC-13",
                check="Statistical or comma-decimal value was linked as bibliography references",
                severity="error",
                block=block,
                snippet=block.text,
                stage=POLISH_STAGE,
                hypothesis="Comma-decimal/statistical notation was mistaken for a reference list.",
                proposed_fix_layer="EN polish citation false-positive guards for statistical contexts",
                regression_test="Values like effect size 1,5, allocation ratio 3,1, and sample-size values remain numeric text.",
                extra=(comma_match or single_stat_match).groupdict(),
            )
        )
        break

    for block in body_blocks:
        if _looks_like_float_or_caption(block):
            continue
        for match in VISIBLE_FIGURE_REF_RE.finditer(block.text):
            figure_key = _figure_key_from_visible_match(match)
            if _is_external_supplementary_figure_ref(match):
                continue
            if figure_key in fig_targets:
                continue
            if _has_nearby_fig_link(block, figure_key, match.start()):
                continue
            defects.append(
                _defect(
                    defect_id="P61",
                    cc_class="CC-03/CC-08/CC-10",
                    check="Visible figure reference has no matching semantic figure target",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=POLISH_STAGE,
                    hypothesis="Figure extraction/wrapping did not create targets for all visible figure references.",
                    proposed_fix_layer="EN polish figure target completeness audit",
                    regression_test="References such as Figure 3D, Figure 4A, and Figure 4 report missing targets when no fig-3/fig-4 wrapper exists.",
                    extra={
                        "figure": figure_key,
                        "figure_key": figure_key,
                        "visible_label": match.group(0),
                        "quality_counted": False,
                    },
                )
            )
            break
        if defects and defects[-1].id == "P61":
            break

    warning_context_blocks = _parse_overlapping_blocks(polish_html)
    for warning_index, block in enumerate(_missing_figure_warning_blocks(polish_html)):
        classification = _classify_missing_figure_warning(block, warning_context_blocks)
        extra = {"warning_index": warning_index + 1, **classification["extra"]}
        defects.append(
            _defect(
                defect_id=classification["defect_id"],
                cc_class="CC-08/CC-13",
                check=classification["check"],
                severity="warning",
                block=block,
                snippet=block.text,
                stage=RAW_STAGE,
                hypothesis=classification["hypothesis"],
                proposed_fix_layer=classification["proposed_fix_layer"],
                regression_test=(
                    "Visible z2m-missing-figure-warning blocks are counted and split into "
                    "same-label, ambiguous-nearby-image, and no-nearby-image subtypes."
                ),
                extra=extra,
            )
        )

    for match in PAGE_LINK_RE.finditer(slim_html):
        label = _strip_tags(match.group("body"))
        if re.match(r"^\[\s*\d", label) is None:
            continue
        defects.append(
            _defect(
                defect_id="P63",
                cc_class="CC-02/CC-03/CC-10",
                check="Bracket citation remains a PDF page link",
                severity="error",
                block=None,
                snippet=_snippet(slim_html, match.start(), match.end()),
                stage=POLISH_STAGE,
                hypothesis="Bracket citation grammar missed page-anchor citation forms, including no-space lists and ranges.",
                proposed_fix_layer="EN polish bracket citation retargeting",
                regression_test="Citations like [1], [17,18], [20-23], [30], and [33] link to #ref targets instead of #page anchors.",
                extra={"page_target": match.group("target"), "label": label},
            )
        )
        break

    split_email_match = SPLIT_EMAIL_TEXT_RE.search(plain)
    if split_email_match is not None:
        defects.append(
            _defect(
                defect_id="P64",
                cc_class="CC-04/CC-13",
                check="Email local-part is split before a roman-like suffix",
                severity="warning",
                block=None,
                snippet=_snippet(plain, split_email_match.start(), split_email_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Roman-suffix repair split an email local-part such as simonov into 'simono v@...'.",
                proposed_fix_layer="EN polish roman-suffix email guard",
                regression_test="Email addresses like simonov@neuro.nnov.ru remain contiguous after roman-suffix cleanup.",
            )
        )

    runaway_match = RUNAWAY_REPEATED_TEXT_RE.search(plain)
    if runaway_match is not None:
        defects.append(
            _defect(
                defect_id="P65",
                cc_class="CC-04/CC-13",
                check="Runaway repeated word or phrase remains in polish text",
                severity="error",
                block=None,
                snippet=_snippet(plain, runaway_match.start(), runaway_match.end()),
                stage=POLISH_STAGE,
                hypothesis="OCR or sentence-repair cleanup repeated the same token/fragment enough times to corrupt a body paragraph.",
                proposed_fix_layer="EN polish repeated-fragment collapse audit",
                regression_test="Runs such as 'slow, slow, slow...' and repeated optogenetic kinetics fragments are reported.",
            )
        )

    lost_ff_match = LOST_FF_WORD_RE.search(plain)
    if lost_ff_match is not None:
        defects.append(
            _defect(
                defect_id="P66",
                cc_class="CC-04/CC-13",
                check="Common lost ligature word remains in polish text",
                severity="warning",
                block=None,
                snippet=_snippet(plain, lost_ff_match.start(), lost_ff_match.end()),
                stage=POLISH_STAGE,
                hypothesis="OCR or ligature normalization dropped an 'ff', 'fi', or 'fl' pair in common scientific prose.",
                proposed_fix_layer="EN polish OCR spelling/ligature cleanup",
                regression_test="Words such as effect, efficacy, officer, coefficient, flexible, fibers, and diffusion are not left as lost-ligature variants.",
                extra={"match": lost_ff_match.group(0)},
            )
        )

    joined_word_match = next(
        (
            match
            for match in KNOWN_JOINED_WORD_RE.finditer(plain)
            if not _joined_word_match_is_url_slug(plain, match)
        ),
        None,
    )
    if joined_word_match is not None:
        defects.append(
            _defect(
                defect_id="P67",
                cc_class="CC-04/CC-13",
                check="Known joined word or missing separator remains in polish text",
                severity="warning",
                block=None,
                snippet=_snippet(plain, joined_word_match.start(), joined_word_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Line-break, marker, or footnote cleanup failed to restore an ordinary word boundary or separator.",
                proposed_fix_layer="EN polish joined-word and separator cleanup",
                regression_test="Patterns such as 'considerationsincluding', 'timeconsuming', 'theCreative', 'd)2.5D', and 'prostatectomyDeltaVV' are reported.",
                extra={"match": joined_word_match.group(0)},
            )
        )

    float_interrupt_match = FLOAT_SENTENCE_INTERRUPT_RE.search(plain)
    if float_interrupt_match is not None:
        defects.append(
            _defect(
                defect_id="P68",
                cc_class="CC-07/CC-08/CC-13",
                check="Float material interrupts a body sentence",
                severity="error",
                block=None,
                snippet=_snippet(plain, float_interrupt_match.start(), float_interrupt_match.end()),
                stage=POLISH_STAGE,
                hypothesis="A box or figure was inserted between two halves of the same body sentence, preserving a bad PDF reading order.",
                proposed_fix_layer="EN polish float/body reading-order repair",
                regression_test="Sentences split by Box/Figure blocks, such as 'For these ... reasons' or 'also ... require evaluation', are reported.",
            )
        )

    corrupt_email_label_match = CORRUPT_EMAIL_LABEL_RE.search(plain)
    if corrupt_email_label_match is not None:
        defects.append(
            _defect(
                defect_id="P69",
                cc_class="CC-04/CC-13",
                check="E-mail label is corrupted by marker glyphs",
                severity="warning",
                block=None,
                snippet=_snippet(plain, corrupt_email_label_match.start(), corrupt_email_label_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Front-matter symbol cleanup attached an affiliation/correspondence marker to the e-mail label.",
                proposed_fix_layer="EN polish front-matter e-mail label cleanup",
                regression_test="Labels such as 'Me-mail:' and boxed-glyph 'Se-mail:' do not survive in final polish HTML.",
                extra={"match": corrupt_email_label_match.group(0)},
            )
        )

    reference_roman_split_match = REFERENCE_ROMAN_SPLIT_RE.search(plain)
    if reference_roman_split_match is not None:
        defects.append(
            _defect(
                defect_id="P70",
                cc_class="CC-04/CC-13",
                check="Reference journal abbreviation is split before roman-like v",
                severity="warning",
                block=None,
                snippet=_snippet(plain, reference_roman_split_match.start(), reference_roman_split_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Roman-suffix repair or reference cleanup split a journal abbreviation inside the bibliography.",
                proposed_fix_layer="EN polish reference roman-suffix guard",
                regression_test="'Neurosci. Biobehav. Rev.' does not become 'Neurosci. Biobeha v. Rev.' in references.",
            )
        )

    known_ocr_match = KNOWN_OCR_TOKEN_RE.search(plain)
    if known_ocr_match is not None and not _known_ocr_token_is_false_positive(plain, known_ocr_match):
        known_ocr_extra: dict[str, Any] = {"match": known_ocr_match.group(0)}
        if _known_ocr_token_is_present_in_pdf_text_layer(known_ocr_match.group(0), pdf_text):
            known_ocr_extra.update(
                {
                    "quality_counted": False,
                    "source_pdf_text_layer_evidence": "known OCR token is already present in the source PDF text layer",
                }
            )
        defects.append(
            _defect(
                defect_id="P71",
                cc_class="CC-04/CC-13",
                check="Known OCR token or phrase remains in polish text",
                severity="warning",
                block=None,
                snippet=_snippet(plain, known_ocr_match.start(), known_ocr_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Manual full-text review found recurring OCR token shapes that the broader audit did not classify.",
                proposed_fix_layer="EN polish OCR residue scanner",
                regression_test="Tokens such as 'urflowmetry', 'urtheral', 'premicturtion', 'Qavg and Omax', and malformed p-values are reported.",
                extra=known_ocr_extra,
            )
        )

    table_note_body_merge_match = TABLE_NOTE_BODY_MERGE_RE.search(plain)
    if table_note_body_merge_match is not None:
        defects.append(
            _defect(
                defect_id="P72",
                cc_class="CC-07/CC-11/CC-13",
                check="Table note is merged into following body prose",
                severity="error",
                block=None,
                snippet=_snippet(plain, table_note_body_merge_match.start(), table_note_body_merge_match.end()),
                stage=POLISH_STAGE,
                hypothesis="A table footnote/legend lost its boundary and swallowed the next body paragraph.",
                proposed_fix_layer="EN polish table-note/body boundary repair",
                regression_test="Table notes ending with symptom direction do not merge into 'studies to evaluate...' body prose.",
            )
        )

    author_marker_glue_match = AUTHOR_MARKER_GLUE_RE.search(plain)
    if author_marker_glue_match is not None:
        author_marker_context = plain[
            max(0, author_marker_glue_match.start() - 220) : author_marker_glue_match.end() + 220
        ]
        if re.match(r"Between\s+100\s+and\b", author_marker_glue_match.group(0), re.IGNORECASE) and re.search(
            r"\bBetween\s+0\s+and\s+100\b[\s\S]{0,240}\bBetween\s+100\s+and\s+200\b[\s\S]{0,240}"
            r"\bBetween\s+200\s+and\s+255\b[\s\S]{0,240}\bperceptual\s+threshold\b",
            author_marker_context,
            re.IGNORECASE,
        ):
            author_marker_glue_match = None

    if author_marker_glue_match is not None:
        defects.append(
            _defect(
                defect_id="P73",
                cc_class="CC-01/CC-04/CC-13",
                check="Author affiliation marker is glued into author line as 100",
                severity="warning",
                block=None,
                snippet=_snippet(plain, author_marker_glue_match.start(), author_marker_glue_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Front-matter superscript or ORCID marker was converted into a plain numeric token in the author list.",
                proposed_fix_layer="EN polish front-matter author-marker cleanup",
                regression_test="Author lines such as 'Mukhiddinov 100 and Soon-Young Kim' are reported as marker glue.",
                extra={"match": author_marker_glue_match.group(0)},
            )
        )

    latex_macro_runaway_match = LATEX_MACRO_RUNAWAY_RE.search(plain)
    if latex_macro_runaway_match is not None:
        defects.append(
            _defect(
                defect_id="P74",
                cc_class="CC-04/CC-13",
                check="Runaway LaTeX macro expansion remains in polish text",
                severity="error",
                block=None,
                snippet=_snippet(plain, latex_macro_runaway_match.start(), latex_macro_runaway_match.end()),
                stage=POLISH_STAGE,
                hypothesis="PDF/HTML import exposed a repeated TeX macro expansion instead of rendered article text.",
                proposed_fix_layer="EN polish TeX macro residue and web-import cleanup",
                regression_test="Repeated ACM-style '\\@ifnextchar' macro runs are reported as corrupt body text.",
            )
        )

    doi_body_merge = next(
        (
            (block, match)
            for block in body_blocks
            for match in [DOI_BODY_PROSE_MERGE_RE.search(block.text)]
            if match is not None
        ),
        None,
    )
    if doi_body_merge is not None:
        doi_body_merge_block, doi_body_merge_match = doi_body_merge
        defects.append(
            _defect(
                defect_id="P75",
                cc_class="CC-07/CC-13",
                check="DOI metadata is merged into following body prose",
                severity="warning",
                block=doi_body_merge_block,
                snippet=_snippet(
                    doi_body_merge_block.text,
                    doi_body_merge_match.start(),
                    doi_body_merge_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="A DOI/front-matter metadata line lost its boundary and swallowed the next paragraph.",
                proposed_fix_layer="EN polish DOI/front-matter boundary repair",
                regression_test="A DOI line followed by body prose such as 'the plasticity...' is reported.",
            )
        )

    detached_accent_match = DETACHED_ACCENT_RE.search(plain)
    if detached_accent_match is not None:
        defects.append(
            _defect(
                defect_id="P76",
                cc_class="CC-04/CC-13",
                check="Detached accent mark remains inside a word or name",
                severity="warning",
                block=None,
                snippet=_snippet(plain, detached_accent_match.start(), detached_accent_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Unicode accent composition was not normalized, leaving names such as Neumuller/Bezier with standalone accent glyphs.",
                proposed_fix_layer="EN polish Unicode accent normalization",
                regression_test="Names like 'Neumuller' and 'Bezier' do not retain detached diaeresis/acute marks.",
                extra={"match": detached_accent_match.group(0)},
            )
        )

    table_section_absorb_block: Block | None = None
    table_section_absorb_match: re.Match[str] | None = None
    for block in polish_blocks:
        table_section_absorb_match = TABLE_SECTION_ABSORB_RE.search(block.text)
        if table_section_absorb_match is not None:
            table_section_absorb_block = block
            break
    if table_section_absorb_block is not None and table_section_absorb_match is not None:
        defects.append(
            _defect(
                defect_id="P77",
                cc_class="CC-07/CC-11/CC-13",
                check="Table block absorbs following sections or figure captions",
                severity="error",
                block=table_section_absorb_block,
                snippet=_snippet(
                    table_section_absorb_block.text,
                    table_section_absorb_match.start(),
                    table_section_absorb_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="A table/list extraction block kept reading through subsequent section headings and body paragraphs.",
                proposed_fix_layer="EN polish table/list boundary and reading-order repair",
                regression_test="Table 3.1 blocks do not swallow '3.8 Data Acquisition' and '3.9 Criteria for Use of Data'.",
            )
        )

    specific_intra_word_matches: set[str] = set()

    inline_intra_word_space_match = INLINE_INTRA_WORD_SPACE_HTML_RE.search(slim_html)
    if inline_intra_word_space_match is not None:
        plain_match = INTRA_WORD_SPACE_RE.search(_strip_tags(inline_intra_word_space_match.group(0)))
        if plain_match is not None:
            specific_intra_word_matches.add(plain_match.group(0))
        defects.append(
            _defect(
                defect_id="P94",
                cc_class="CC-04/CC-13",
                check="Known intra-word spacing residue crosses inline markup",
                severity="warning",
                block=None,
                snippet=_strip_tags(
                    slim_html[
                        max(0, inline_intra_word_space_match.start() - 180) : inline_intra_word_space_match.end()
                        + 180
                    ]
                ),
                stage=POLISH_STAGE,
                hypothesis="OCR kept a word split across anchors or inline formatting, so text-only cleanup could not see the full word.",
                proposed_fix_layer="EN polish inline-aware OCR spacing cleanup",
                regression_test="Inline splits such as '<b>B</b> rain-computer' and anchor-split 'ob je ct s w ould' are classified separately from plain P78 text.",
                extra={"match": plain_match.group(0) if plain_match is not None else _strip_tags(inline_intra_word_space_match.group(0))},
            )
        )

    table_footnote_word_letter_match = TABLE_FOOTNOTE_WORD_LETTER_HTML_RE.search(slim_html)
    if table_footnote_word_letter_match is not None:
        plain_match = INTRA_WORD_SPACE_RE.search(_strip_tags(table_footnote_word_letter_match.group(0)))
        if plain_match is not None:
            specific_intra_word_matches.add(plain_match.group(0))
        defects.append(
            _defect(
                defect_id="P95",
                cc_class="CC-04/CC-13",
                check="Known word letter is misclassified as a table footnote marker",
                severity="warning",
                block=None,
                snippet=_strip_tags(
                    slim_html[
                        max(0, table_footnote_word_letter_match.start() - 180) : table_footnote_word_letter_match.end()
                        + 180
                    ]
                ),
                stage=POLISH_STAGE,
                hypothesis="A terminal letter of a known word or author name was preserved as z2m-table-fn instead of normal inline text.",
                proposed_fix_layer="EN polish table footnote/word-boundary cleanup",
                regression_test="Known names such as Leporini in tables are reported as table-footnote letter splits, not generic P78 spacing.",
                extra={"match": plain_match.group(0) if plain_match is not None else _strip_tags(table_footnote_word_letter_match.group(0))},
            )
        )

    intra_word_space_match = next(
        (
            match
            for match in INTRA_WORD_SPACE_RE.finditer(plain)
            if match.group(0) not in specific_intra_word_matches
        ),
        None,
    )
    if (
        intra_word_space_match is not None
        and intra_word_space_match.group(0) not in specific_intra_word_matches
    ):
        defects.append(
            _defect(
                defect_id="P78",
                cc_class="CC-04/CC-13",
                check="Known intra-word spacing residue remains in polish text",
                severity="warning",
                block=None,
                snippet=_snippet(plain, intra_word_space_match.start(), intra_word_space_match.end()),
                stage=POLISH_STAGE,
                hypothesis="OCR kept spurious character gaps inside ordinary words after final polish cleanup.",
                proposed_fix_layer="EN polish intra-word spacing cleanup",
                regression_test="Fragments such as 'ob je ct s w ould' and 'safe ty c oncerns' are reported.",
                extra={"match": intra_word_space_match.group(0)},
            )
        )

    affiliation_department_glue_match = AFFILIATION_DEPARTMENT_GLUE_RE.search(plain)
    if affiliation_department_glue_match is not None:
        defects.append(
            _defect(
                defect_id="P79",
                cc_class="CC-01/CC-04/CC-13",
                check="Front-matter affiliation number is glued to Department",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    affiliation_department_glue_match.start(),
                    affiliation_department_glue_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Superscript affiliation markers were flattened and attached to the following affiliation label.",
                proposed_fix_layer="EN polish front-matter affiliation spacing cleanup",
                regression_test="Affiliation labels such as '1Department' and '5Department' are reported.",
                extra={"match": affiliation_department_glue_match.group(0)},
            )
        )

    suspicious_email_domain_match = SUSPICIOUS_EMAIL_DOMAIN_RE.search(plain)
    if suspicious_email_domain_match is not None:
        defects.append(
            _defect(
                defect_id="P80",
                cc_class="CC-04/CC-13",
                check="Institutional email domain looks OCR-truncated",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    suspicious_email_domain_match.start(),
                    suspicious_email_domain_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Manual review found an institution-specific e-mail typo alongside otherwise consistent domain spellings.",
                proposed_fix_layer="EN polish front-matter e-mail/domain OCR cleanup",
                regression_test="Suspicious Florence-domain typo '@unfi.it' is reported.",
                extra={"match": suspicious_email_domain_match.group(0)},
            )
        )

    body_page_header_match = BODY_PAGE_HEADER_RE.search(plain)
    if body_page_header_match is not None:
        defects.append(
            _defect(
                defect_id="P81",
                cc_class="CC-07/CC-13",
                check="Page header or footer remains in body prose",
                severity="warning",
                block=None,
                snippet=_snippet(plain, body_page_header_match.start(), body_page_header_match.end()),
                stage=POLISH_STAGE,
                hypothesis="PDF page furniture was preserved as ordinary paragraph text after polish cleanup.",
                proposed_fix_layer="EN polish page furniture cleanup",
                regression_test="Headers such as 'FRANCO ET AL. | 1915' are reported.",
                extra={"match": body_page_header_match.group(0)},
            )
        )

    table_gibberish_flow_match = TABLE_GIBBERISH_FLOW_RE.search(plain)
    if table_gibberish_flow_match is not None:
        defects.append(
            _defect(
                defect_id="P82",
                cc_class="CC-04/CC-07/CC-11/CC-13",
                check="Table data has OCR-scrambled column headers",
                severity="error",
                block=None,
                snippet=_snippet(
                    plain,
                    table_gibberish_flow_match.start(),
                    table_gibberish_flow_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="A table extraction block lost column structure and preserved heavily scrambled OCR tokens.",
                proposed_fix_layer="EN polish table OCR/column structure audit",
                regression_test="Uroflow table fragments such as 'nales 5 ted Q a rates' and malformed P-value runs are reported.",
            )
        )

    float_or_metadata_interruption_match = next(
        (
            match
            for match in FLOAT_OR_METADATA_INTERRUPTION_RE.finditer(plain)
            if FLOAT_OR_METADATA_INTRUSION_MARKER_RE.search(match.group(0)) is not None
        ),
        None,
    )
    if float_or_metadata_interruption_match is not None:
        defects.append(
            _defect(
                defect_id="P83",
                cc_class="CC-07/CC-08/CC-13",
                check="Body phrase is interrupted by float or metadata material",
                severity="error",
                block=None,
                snippet=_snippet(
                    plain,
                    float_or_metadata_interruption_match.start(),
                    float_or_metadata_interruption_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="PDF reading order inserted figure, footnote, or journal metadata between two halves of one body phrase.",
                proposed_fix_layer="EN polish float/body reading-order repair",
                regression_test="Known splits such as 'printed on swell paper to ... form a tactile rendering' and 'mul- ... timodal sensing' are reported.",
            )
        )

    escaped_sup_footnote_match = ESCAPED_SUP_FOOTNOTE_RE.search(plain)
    if escaped_sup_footnote_match is not None:
        defects.append(
            _defect(
                defect_id="P84",
                cc_class="CC-01/CC-04/CC-13",
                check="Escaped footnote superscript markup remains as visible text",
                severity="warning",
                block=None,
                snippet=_snippet(plain, escaped_sup_footnote_match.start(), escaped_sup_footnote_match.end()),
                stage=POLISH_STAGE,
                hypothesis="A raw escaped footnote marker was not decoded or converted into a proper footnote marker.",
                proposed_fix_layer="EN polish escaped-footnote/front-matter cleanup",
                regression_test="Visible residues such as '& lt;sup>2' and '& lt;sup>3' are reported.",
                extra={"match": escaped_sup_footnote_match.group(0)},
            )
        )

    references_backmatter_interleave_match = REFERENCES_BACKMATTER_INTERLEAVE_RE.search(plain)
    if references_backmatter_interleave_match is not None:
        defects.append(
            _defect(
                defect_id="P85",
                cc_class="CC-07/CC-13",
                check="References are interleaved with back-matter sections",
                severity="error",
                block=None,
                snippet=_snippet(
                    plain,
                    references_backmatter_interleave_match.start(),
                    references_backmatter_interleave_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Back-matter continuation text was placed after an early References heading, mixing article metadata with bibliography entries.",
                proposed_fix_layer="EN polish back-matter/reference ordering repair",
                regression_test="Frontiers-style back matter split as 'ETHICS STATEMENT ... REFERENCES ... University of Bath ... AUTHOR CONTRIBUTIONS' is reported.",
            )
        )

    split_dot_email_match = _find_split_dot_email_match(plain)
    if split_dot_email_match is not None:
        defects.append(
            _defect(
                defect_id="P86",
                cc_class="CC-01/CC-04/CC-13",
                check="Email address is split after a dot",
                severity="warning",
                block=None,
                snippet=_snippet(plain, split_dot_email_match.start(), split_dot_email_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Line wrapping or sentence cleanup inserted whitespace inside an e-mail local-part.",
                proposed_fix_layer="EN polish e-mail normalization",
                regression_test="Visible e-mails such as 'jan. krhut@fno.cz' are reported as split local-parts.",
                extra={"match": split_dot_email_match.group(0)},
            )
        )

    old_scan_ocr_gibberish_match = OLD_SCAN_OCR_GIBBERISH_RE.search(plain)
    if old_scan_ocr_gibberish_match is not None:
        defects.append(
            _defect(
                defect_id="P87",
                cc_class="CC-04/CC-13",
                check="Old-scan OCR gibberish remains in polish text",
                severity="error",
                block=None,
                snippet=_snippet(
                    plain,
                    old_scan_ocr_gibberish_match.start(),
                    old_scan_ocr_gibberish_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Manual full-text review found old scanned PDFs with residual OCR tokens and table/caption gibberish that normal article cleanup cannot safely repair.",
                proposed_fix_layer="EN polish OCR-quality gate / old-scan routing",
                regression_test="Old-scan residues such as 'LUMBAH I - i', 'The (!I G :. nosis', 'v&me', 'foriTi', and 'kcounl/mg prolan' are reported.",
                extra={"match": old_scan_ocr_gibberish_match.group(0)},
            )
        )

    split_url_domain_match = SPLIT_URL_DOMAIN_RE.search(plain)
    if split_url_domain_match is not None:
        defects.append(
            _defect(
                defect_id="P88",
                cc_class="CC-04/CC-13",
                check="URL domain is split by OCR whitespace",
                severity="warning",
                block=None,
                snippet=_snippet(plain, split_url_domain_match.start(), split_url_domain_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Reference URL normalization missed whitespace inserted inside a domain name.",
                proposed_fix_layer="EN polish URL/domain whitespace cleanup",
                regression_test="Split domains such as 'www. osh a.europa.eu' are reported.",
                extra={"match": split_url_domain_match.group(0)},
            )
        )

    split_at_email_match = SPLIT_AT_EMAIL_RE.search(plain)
    if split_at_email_match is not None:
        defects.append(
            _defect(
                defect_id="P89",
                cc_class="CC-01/CC-04/CC-13",
                check="Email address is split after at-sign",
                severity="warning",
                block=None,
                snippet=_snippet(plain, split_at_email_match.start(), split_at_email_match.end()),
                stage=POLISH_STAGE,
                hypothesis="Line wrapping or front-matter cleanup inserted whitespace between the at-sign and the email domain.",
                proposed_fix_layer="EN polish e-mail normalization",
                regression_test="Visible e-mails such as 'iskandar@ neurosurgery.wisc.edu' are reported as split domains.",
                extra={"match": split_at_email_match.group(0)},
            )
        )

    bibliography_numbering_residue_match = BIBLIOGRAPHY_NUMBERING_RESIDUE_RE.search(plain)
    if (
        bibliography_numbering_residue_match is not None
        and not _bibliography_numbering_residue_is_clean_reference_boundary(
            polish_html,
            bibliography_numbering_residue_match.group(0),
        )
    ):
        defects.append(
            _defect(
                defect_id="P90",
                cc_class="CC-02/CC-04/CC-13",
                check="Bibliography numbering is duplicated or shifted",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    bibliography_numbering_residue_match.start(),
                    bibliography_numbering_residue_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Reference-list line wrapping preserved a previous bibliography number as visible text before the next entry.",
                proposed_fix_layer="EN polish reference numbering cleanup",
                regression_test="Reference runs such as '20. 20 van Tulder' and '33. 32 De Nunzio' are reported.",
                extra={"match": bibliography_numbering_residue_match.group(0)},
            )
        )

    publisher_recommendation_match = PUBLISHER_RECOMMENDATION_BLOCK_RE.search(plain)
    if publisher_recommendation_match is not None:
        defects.append(
            _defect(
                defect_id="P91",
                cc_class="CC-07/CC-13",
                check="Publisher recommendation sidebar remains in article body",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    publisher_recommendation_match.start(),
                    publisher_recommendation_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Publisher landing-page recommendations were preserved before the real article body.",
                proposed_fix_layer="EN polish publisher chrome/sidebar cleanup",
                regression_test="IOP front matter such as 'You may also like ... ChArUco-based 3D scanner' is reported.",
                extra={"match": publisher_recommendation_match.group(0)},
            )
        )

    affiliation_marker_residue_match = AFFILIATION_MARKER_RESIDUE_RE.search(plain)
    if affiliation_marker_residue_match is not None:
        defects.append(
            _defect(
                defect_id="P92",
                cc_class="CC-01/CC-04/CC-13",
                check="Author affiliation markers are glued or left as a numeric run",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    affiliation_marker_residue_match.start(),
                    affiliation_marker_residue_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="Front-matter cleanup did not separate author names from affiliation markers or compact a leftover affiliation-number run.",
                proposed_fix_layer="EN polish author/affiliation normalization",
                regression_test="Author residues such as 'Yary Volpe1' and 'İlbey 1 1 2 3 1 1' are reported.",
                extra={"match": affiliation_marker_residue_match.group(0)},
            )
        )

    pdf_line_number_residue_match = PDF_LINE_NUMBER_RESIDUE_RE.search(plain)
    if pdf_line_number_residue_match is not None:
        defects.append(
            _defect(
                defect_id="P93",
                cc_class="CC-04/CC-07/CC-13",
                check="Publisher line numbers remain in body prose",
                severity="warning",
                block=None,
                snippet=_snippet(
                    plain,
                    pdf_line_number_residue_match.start(),
                    pdf_line_number_residue_match.end(),
                ),
                stage=POLISH_STAGE,
                hypothesis="PDF line numbers from an accepted manuscript were preserved as ordinary article text.",
                proposed_fix_layer="EN polish page/line-number cleanup",
                regression_test="RSC accepted-manuscript line numbers such as 'with 20 the sizes' and '_{75} incubated' are reported.",
                extra={"match": pdf_line_number_residue_match.group(0)},
            )
        )

    return defects


def _section_order_pdf_defects(
    pdf_text: str,
    polish_html: str,
    polish_blocks: list[Block],
) -> list[Defect]:
    pdf_norm = _diagnostic_text(pdf_text)
    polish_norm = _diagnostic_text(polish_html)
    pdf_pos = _phrase_positions(pdf_norm, PDF_DIAG_SECTION_SEQUENCE)
    polish_pos = _phrase_positions(polish_norm, PDF_DIAG_SECTION_SEQUENCE)

    pdf_has_expected_order = (
        pdf_pos["funding"] != -1
        and pdf_pos["supplementary material"] != -1
        and pdf_pos["references"] != -1
        and pdf_pos["funding"] < pdf_pos["supplementary material"] < pdf_pos["references"]
    )
    polish_has_interleaved_refs = (
        polish_pos["funding"] != -1
        and polish_pos["supplementary material"] != -1
        and polish_pos["references"] != -1
        and polish_pos["funding"] < polish_pos["references"] < polish_pos["supplementary material"]
    )
    if not (pdf_has_expected_order and polish_has_interleaved_refs):
        return []

    ref_block = next((block for block in polish_blocks if REFERENCES_HEADING_RE.match(block.text)), None)
    return [
        _defect(
            defect_id="P24",
            cc_class="CC-13/CC-14",
            check="PDF text layer suggests end-section order differs from polish",
            severity="warning",
            block=ref_block,
            snippet="PDF order: FUNDING -> SUPPLEMENTARY MATERIAL -> REFERENCES; polish order: FUNDING -> REFERENCES -> SUPPLEMENTARY MATERIAL",
            stage=POLISH_STAGE,
            hypothesis="Marker or post-processing interleaved a two-column terminal section with the bibliography.",
            proposed_fix_layer="PDF-aware EN polish diagnostics and end-section ordering repair",
            regression_test="When PDF text has funding/supplementary material before references, audit warns if polish places references between them.",
            extra={"pdf_positions": pdf_pos, "polish_positions": polish_pos},
        )
    ]


def _pdf_text_layer_defects(
    pdf_text: str,
    polish_html: str,
    polish_blocks: list[Block],
) -> list[Defect]:
    if not pdf_text.strip():
        return []
    return _section_order_pdf_defects(pdf_text, polish_html, polish_blocks)


def analyze_pair(
    raw_path: Path,
    polish_path: Path,
    *,
    enable_pdf_diagnostics: bool = False,
    pdf_text_override: str | None = None,
    pdf_path_override: Path | None = None,
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
    }
    if enable_pdf_diagnostics or pdf_text_override is not None:
        pdf_text, pdf_summary = _load_pdf_diagnostic_text(raw_path, pdf_text_override, pdf_path_override)
    pdf_link_summary = {
        "pdf_link_text_status": "disabled",
        "pdf_link_count": 0,
        "pdf_citation_dest_links": 0,
        "pdf_author_year_link_labels": 0,
        "pdf_citation_link_samples": [],
        "pdf_link_text_error": None,
    }
    if enable_pdf_diagnostics:
        pdf_link_summary = _pdf_citation_link_summary(Path(pdf_summary["source_pdf_path"]))

    defects: list[Defect] = []
    defects.extend(_frontmatter_defects(raw_blocks, polish_blocks))
    defects.extend(_citation_defects(polish_blocks))
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
) -> dict[str, Any]:
    pairs = find_pairs(roots)
    articles: list[dict[str, Any]] = []
    progress_every = max(1, progress_write_every)
    for index, (raw_path, polish_path) in enumerate(pairs, 1):
        articles.append(
            analyze_pair(
                raw_path,
                polish_path,
                enable_pdf_diagnostics=enable_pdf_diagnostics,
                pdf_path_override=(pdf_map or {}).get(_article_name_from_stage(raw_path)),
            )
        )
        if progress_out is not None and (index % progress_every == 0 or index == len(pairs)):
            defect_counts = _add_corpus_hit_counts(articles)
            partial_report = _assemble_report(
                roots,
                articles,
                defect_counts,
                audit_status=("complete" if index == len(pairs) else "running"),
                total_pair_count=len(pairs),
            )
            _write_json_report(progress_out, partial_report)
            print(
                f"Audit progress: {index}/{len(pairs)} articles={len(articles)} "
                f"defects={sum(len(article['defects_found']) for article in articles)}",
                flush=True,
            )
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pdf_map = _load_pdf_map(args.pdf_map) if args.pdf_map is not None else None
    report = build_report(
        args.roots,
        enable_pdf_diagnostics=args.pdf_diagnostics,
        pdf_map=pdf_map,
        progress_out=args.out,
        progress_write_every=args.progress_write_every,
    )
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
