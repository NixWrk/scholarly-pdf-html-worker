#!/usr/bin/env python
"""Audit EN raw -> EN polish stage pairs without running Marker."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
import json
from pathlib import Path
import re
import urllib.parse
from typing import Any, Iterable


RAW_STAGE = "01.en.raw.html"
POLISH_STAGE = "02.en.polish.html"
PDF_SOURCE_STAGE = "00.source.pdf"

TAG_RE = re.compile(r"<[^>]+>")
BLOCK_RE = re.compile(
    r"<(?P<tag>p|h[1-6]|div|table|figure|figcaption|li|td|th)\b(?P<attrs>[^>]*)>"
    r"(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
TABLE_CELL_RE = re.compile(
    r"<t[dh]\b[^>]*>(?P<body>.*?)</t[dh]>",
    re.IGNORECASE | re.DOTALL,
)
ATTR_RE = re.compile(
    r"(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*"
    r"(?:(?P<q>['\"])(?P<quoted>.*?)(?P=q)|(?P<bare>[^\s>]+))",
    re.DOTALL,
)
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
    r"\s*(?:hps|htps|ttps)://[\s\S]{0,300}?</a>",
    re.IGNORECASE | re.DOTALL,
)
REF_ANCHOR_BODY_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(?P<num>\d+)['\"][^>]*>"
    r"(?P<body>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*(['\"])(?P<src>.*?)\1", re.IGNORECASE | re.DOTALL)
DATA_IMAGE_RE = re.compile(r"data:image/[^'\"]+", re.IGNORECASE)
FIG_CAPTION_RE = re.compile(r"^\s*(?:Figure|Fig\.?|FIGURE)\s+\d+[A-Za-z]?\b", re.IGNORECASE)
TABLE_CAPTION_RE = re.compile(r"^\s*(?:TABLE|Table)\s+(?:[IVXLCM]+|\d+)\b", re.IGNORECASE)
REFERENCES_HEADING_RE = re.compile(r"^\s*(?:references|bibliography|works cited)\s*$", re.IGNORECASE)
REF_ID_RE = re.compile(r"^ref-(\d+)$", re.IGNORECASE)
VISIBLE_REF_NUM_RE = re.compile(r"^\s*(\d{1,4})\.")
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
    r"\b(?:u|µ|μ)m\s+\d+\b|"
    r"\bmCcm[-\u2212]\d+\b|"
    r"\b\d+(?:\.\d+)?\s*(?:u|µ|μ)?m\s*2\b|"
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
    r"\bhttps?://(?:dx\.)?doi\.org/\d+\.\d+/\s+[A-Za-z0-9]|"
    r"\bhttps?://doi\.org/10\s+\.\s+\d+|"
    r"\bhttps?://\S+/(?:wp|news-room/north|contents/part1/ports-and|ports-and-container)\s+[A-Za-z0-9]|"
    r"\bhttps?://\S+/cgi/pt\?\s+[A-Za-z0-9]|"
    r"\bhttps?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+/\s+"
    r"(?=[A-Za-z0-9._~:/?#\[\]@!$&'*+,;=%-]*[A-Za-z._~:/?#\[\]@!$&'*+,;=%-])"
    r"[A-Za-z0-9._~:/?#\[\]@!$&'*+,;=%-]+|"
    r"\bhttps?://\S+\.(?:h\s+tml|xht\s+ml)\b|"
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
    r"eficacy|eficient(?:ly)?|ofice|oficer|suficient(?:ly)?|tradeofs|"
    r"fexible|ultrafexible|fbers|flms?|fbroin|biofuid|difusion|coefcient|"
    r"defcits|scafolds|feld-efect|fnger|galss)\b|"
    r"\b(?:specifi|Specifi|signifi|Signifi|defi|Defi|diffi|Diffi|profi|Profi|"
    r"confi|Confi|benefi|Benefi|identi?fi|Identi?fi|Offi|offi|Griffi|"
    r"fl|Fl|urofl|Urofl|outfl|Outfl|refl|Refl|infl|Infl)\s+"
    r"(?:c|cally|cant(?:ly)?|ned|ne|nition|ciency|cult(?:y|ies)?|le(?:s|ometry)?|"
    r"dence|cial|es|ce|ths|oor|ow(?:s|metry|meter|rate)?|uid|ll(?:ing)?|"
    r"uoroscopy|uoroscopic|uorescent|ux|uence)\b",
    re.IGNORECASE,
)
KNOWN_JOINED_WORD_RE = re.compile(
    r"\b(?:considerationsincluding|displaycan|refreshabletactile|staffmembers?|"
    r"timeconsuming|nervesparing|da\s+Vinci1Si|touchinteraction|realworld|"
    r"off-theshelf|state-ofthe-art|numbergestures|voicecommands|twodimensional|"
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
    r"timedependent|first-inhumans|backilluminated|anatomicallycompatible|"
    r"convectionenhanced|neurologicallyrelated|valvegated|mindenhancing|"
    r"andChallenges|SoftBankbacked)\b|"
    r"patients,were|prostatectomy\u0394VV|\btheCreative\b|\bd\)2\.5D\b|"
    r"\bAl\s+Omari1\b",
    re.IGNORECASE,
)
FLOAT_SENTENCE_INTERRUPT_RE = re.compile(
    r"For\s+these[\s\S]{200,6000}?reasons,\s+a\s+transdiagnostic|"
    r"also\s+and\s+the\s+Committee[\s\S]{0,2000}?require\s+evaluation|"
    r"trigger\s+global\s+projection\s+targets[\s\S]{0,2000}?"
    r"innate\s+or\s+adaptive\s+immune\s+responses|"
    r"systemic\s+circulation[\s\S]{0,3000}?\(with\s+some\s+serotypes\s+more\s+likely\s+to\s+leak",
    re.IGNORECASE,
)
CORRUPT_EMAIL_LABEL_RE = re.compile(r"(?:\b[MmSs]e-mail:|[\u25a1\ufffd]\s*S?e-mail:)")
REFERENCE_ROMAN_SPLIT_RE = re.compile(
    r"\bBiobeha\s+v\.\s+Rev\.|\bBeha\s+v\.\s+Res\.\s+Methods\b",
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
    r"\b0000-0003-4044-\s+0927\b|"
    r"\b(?:5\.22|4\.21|5\.13)\s+\\pm\s+2,\s+(?:38|36|40)\b|"
    r"\b(?:Schfer|Standarisation|subcomitee|standarization|aformentioned|Cvalli|"
    r"Routeledge)\b|\bPdetQma\s+x\b|\bBOO\s+i\b|\bIPP\s+Grade\s+(?-i:iii)\b|"
    r"\bsimulates\s+the\s+The\s+validation\b|\bto\s+be\s+The\s+topological\s+sort\b|"
    r"\bDirectX-\s+R\b|"
    r"\b(?:MDP\s+i|ISTOR|Appel's\s+Sir\s+i|Build-in\s+sensors|"
    r"Sem\s+i\s*-\s*structured|Gen-A\s+i|Numbe\s+er|parti\s+cipants|"
    r"nterview|Ggather|Vorkshop|ocus\s+group|ANACCESSIBLE|TOOTEKO|"
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
    r"In\s+some\s+\[880\]\s+embodiments|Marvland|OceanofPDF\.com)\b",
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
    r"\s+(?:the|this|we|in|as|depicted|generated|lines)\b",
    re.IGNORECASE,
)
DETACHED_ACCENT_RE = re.compile(
    r"\b[A-Za-z]{2,}[\u00a8\u00b4\u02c6\u02c7\u02dc][A-Za-z]{1,}\b|"
    r"\bOA\u02c6\s+\u02c7SModhrain\b|"
    r"\bB[A-Za-z]+hler,\s*\u02dc\s+and\b|"
    r"\bHeppner,\s*[\u00b4\u02c6]\s+and\b|"
    r"\bC\u00b8\s*\.\s+Varel\b|"
    r"\bSyd\s+\u00a8\s+anheimo\b|"
    r"\bwireless\s+\u00a8\s+intraocular\b|"
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
    r"\bhigh\s*\)\s*w\s+ere\b",
    re.IGNORECASE,
)
AFFILIATION_DEPARTMENT_GLUE_RE = re.compile(r"\b[1-9]Department\b")
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
    r"\bPublished\s+on\s+20\s+July\s+2015\.\s+Downloaded\s+by\s+California\s+State\s+University\s+at\s+Fresno\b",
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
    r"\bРўСѓ\s+of\s+ar\s+t\s+bei\s+ng\s+M\s+oda\s+litie\s+s[\s\S]{0,1400}"
    r"\bEv\s+alu\s+atio\s+n\b|"
    r"\benclusive\s+app\b[\s\S]{0,1200}\bCavalier\s+i\s+et\s+al\.|"
    r"\bTrichopoulos\s+et\s+al\.[\s\S]{0,1200}\bV\s+\.\s+v\s+V\b",
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
    r"(?:\s+\(MRI\))?\s+(?:\[071\]\s+)?This\s+(?:imaging\s+)?compatible\b",
    re.IGNORECASE,
)
ESCAPED_SUP_FOOTNOTE_RE = re.compile(r"&\s*lt;sup>\s*[A-Za-z0-9]\b", re.IGNORECASE)
REFERENCES_BACKMATTER_INTERLEAVE_RE = re.compile(
    r"\bETHICS\s+STATEMENT\b[\s\S]{0,1200}\bREFERENCES\b[\s\S]{0,3500}"
    r"\bUniversity\s+of\s+Bath\b[\s\S]{0,1000}\bAUTHOR\s+CONTRIBUTIONS\b",
    re.IGNORECASE,
)
SPLIT_DOT_EMAIL_RE = re.compile(
    r"\b[A-Za-z]{2,}\.\s+[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b|"
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\s*\.\s+|\s+\.\s*)[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
SPLIT_AT_EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@\s+[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)
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
    r"\bmillimelers\b|\bspecificions\b|\baillinhof-supplied\b",
    re.IGNORECASE,
)
SPLIT_URL_DOMAIN_RE = re.compile(
    r"\bwww\.\s+[A-Za-z]{2,}\s+[A-Za-z](?:\.[A-Za-z]{2,})+\b|"
    r"\bwww\.[A-Za-z0-9-]+\s+\.\s+[A-Za-z]{2,}\b|"
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
    r"\b25\s+5\s+H\.\s+Li\b|\b100\s+39\s+Khokhlov\b|\b105\s+41\s+Y\.\s+Yan\b",
    re.IGNORECASE,
)
PUBLISHER_RECOMMENDATION_BLOCK_RE = re.compile(
    r"\bYou\s+may\s+also\s+like\b[\s\S]{0,700}"
    r"(?:\bBecome\s+a\s+Multilingual\b|\bChArUco-based\s+3D\s+scanner\b|"
    r"\btolerable\s+impurity\s+concentrations\b)|"
    r"\bArticles\s+you\s+may\s+be\s+interested\s+in\b[\s\S]{0,700}"
    r"\bMagnetic\s+resonance-guided\s+near-infrared\s+tomography\s+of\s+the\s+breast\b",
    re.IGNORECASE,
)
AFFILIATION_MARKER_RESIDUE_RE = re.compile(
    r"\bYary\s+Volpe1\b|\b(?:Ilbey|İlbey)\s+1\s+1\s+2\s+3\s+1\s+1\b|"
    r"\bLujain\s+Al\s+Omari1\b|"
    r"\bEva\s+M\.\s+Sevick-Murac\s+aa\)|"
    r"\bS\.V\.\s+Krishna\s+Reddy\s+pa\s+and\s+Ahammad\s+Basha\s+Shaik\s+pb\s+a\s+Department\b|"
    r"\bMingyue\s+Xue,\s+ab\s+Mengbing\s+Zou[\s\S]{0,120}"
    r"\bZhihua\s+Zhan\s+Ab\s+and\s+Shulin\s+Zhao\s+Zhao\b",
    re.IGNORECASE,
)
PDF_LINE_NUMBER_RESIDUE_RE = re.compile(
    r"\bJournal\s+of\s+Materials\s+Chemistry\s+B\s+Accepted\s+Manuscrip\b"
    r"[\s\S]{0,5000}?"
    r"\b(?:with\s+20\s+the\s+sizes|been\s+25\s+reported|"
    r"Fresh\s+lychee\s+was\s+purchased|All\s+measurements\s+were\s+performed|"
    r"_\{75\}\s+incubated|95\s+The\s+morphology|20\s+analytical\s+chemistry|"
    r"100\s+39\s+Khokhlov|105\s+41\s+Y\.\s+Yan)\b",
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
    r"^\s*(?:<p\b[^>]*>\s*<img\b.*?</p>\s*)?"
    r"<p\b[^>]*\bz2m-figure-caption\b[^>]*>(?P<body>.*?)</p>",
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
VISIBLE_FIGURE_REF_RE = re.compile(r"\b(?:Fig\.?|Figure)\s+(?P<num>\d{1,3})(?P<letter>[A-Z])?\b")
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
MISSING_FIGURE_WARNING_RE = re.compile(
    r"<[^>]+\bz2m-missing-figure-warning\b[^>]*>",
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


@dataclass
class Block:
    index: int
    tag: str
    attrs: dict[str, str]
    raw: str
    text: str
    line: int

    @property
    def id(self) -> str:
        return self.attrs.get("id", "")

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    @property
    def block_type(self) -> str:
        return self.attrs.get("block-type", "")

    @property
    def has_img(self) -> bool:
        return bool(re.search(r"<img\b", self.raw, re.IGNORECASE))


@dataclass
class Defect:
    id: str
    cc_class: str
    check: str
    severity: str
    snippet: str
    line: int | None
    first_broken_stage: str
    hypothesis: str
    proposed_fix_layer: str
    regression_test: str
    status: str = "open"
    extra: dict[str, Any] = field(default_factory=dict)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _strip_tags(fragment: str) -> str:
    return _normalize_ws(unescape(TAG_RE.sub(" ", fragment)))


def _line_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _snippet(text: str, start: int = 0, end: int | None = None, *, width: int = 260) -> str:
    end = start if end is None else end
    left = max(0, start - width // 2)
    right = min(len(text), end + width // 2)
    snippet = _strip_tags(text[left:right])
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet += "..."
    if len(snippet) <= width:
        return snippet
    return snippet[: width - 3].rstrip() + "..."


def _attrs(attr_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_RE.finditer(attr_text):
        value = match.group("quoted") if match.group("quoted") is not None else match.group("bare")
        attrs[match.group("name").lower()] = unescape(value or "")
    return attrs


def _parse_blocks(html: str) -> list[Block]:
    blocks: list[Block] = []
    for match in BLOCK_RE.finditer(html):
        raw = match.group(0)
        blocks.append(
            Block(
                index=len(blocks),
                tag=match.group("tag").lower(),
                attrs=_attrs(match.group("attrs")),
                raw=raw,
                text=_strip_tags(raw),
                line=_line_at(html, match.start()),
            )
        )
    return blocks


def _plain_text(html: str) -> str:
    return _strip_tags(html)


def _structure_html(html: str) -> str:
    return DATA_IMAGE_RE.sub("data:image/...", html)


def _unit_diagnostic_texts(block: Block) -> list[str]:
    cells = [_strip_tags(match.group("body")) for match in TABLE_CELL_RE.finditer(block.raw)]
    if cells:
        return cells
    return [block.text]


def _diagnostic_text(text: str) -> str:
    text = unescape(TAG_RE.sub(" ", text))
    text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


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
                "line": _line_at(html, match.start()),
                "searched": [str(candidate) for candidate in candidates],
            }
        )
    return missing


def _source_pdf_path(raw_path: Path) -> Path:
    return raw_path.parent / PDF_SOURCE_STAGE


def _article_name_from_stage(stage_path: Path) -> str:
    return stage_path.parent.parent.name if stage_path.parent.name == "_z2m_stages" else stage_path.parent.name


def _first_path_value(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, dict):
        for key in ("pdf_path", "source_pdf_path", "path"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate:
                return candidate
    if isinstance(value, list):
        for item in value:
            candidate = _first_path_value(item)
            if candidate:
                return candidate
    return None


def _pdf_path_from_map_record(record: Any) -> Path | None:
    if isinstance(record, str) and record:
        return Path(record).expanduser()
    if not isinstance(record, dict):
        return None
    for key in ("pdf_path", "source_pdf_path", "path"):
        candidate = record.get(key)
        if isinstance(candidate, str) and candidate:
            return Path(candidate).expanduser()
    for key in ("exact_matches", "fuzzy_matches", "matches"):
        candidate = _first_path_value(record.get(key))
        if candidate:
            return Path(candidate).expanduser()
    return None


def _load_pdf_map(pdf_map_path: Path) -> dict[str, Path]:
    data = json.loads(pdf_map_path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict) and not any(key in data for key in ("items", "articles", "records")):
        return {
            str(article): path
            for article, value in data.items()
            if (path := _pdf_path_from_map_record(value)) is not None
        }

    if isinstance(data, dict):
        records = data.get("items") or data.get("articles") or data.get("records") or []
    else:
        records = data

    pdf_map: dict[str, Path] = {}
    if not isinstance(records, list):
        return pdf_map
    for record in records:
        if not isinstance(record, dict):
            continue
        article = record.get("article")
        if not isinstance(article, str) or not article:
            continue
        pdf_path = _pdf_path_from_map_record(record)
        if pdf_path is not None:
            pdf_map[article] = pdf_path
    return pdf_map


def _extract_pdf_text(pdf_path: Path) -> tuple[str, str, str | None]:
    if not pdf_path.is_file():
        return "missing", "", None

    errors: list[str] = []
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            return "pymupdf", "\n".join(page.get_text("text") for page in doc), None
        finally:
            doc.close()
    except ImportError as exc:
        errors.append(f"pymupdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - extractor/environment specific
        errors.append(f"pymupdf failed: {exc}")

    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(pdf_path))
        return "pypdf", "\n".join(page.extract_text() or "" for page in reader.pages), None
    except ImportError as exc:
        errors.append(f"pypdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - extractor/environment specific
        errors.append(f"pypdf failed: {exc}")

    return "unavailable", "", "; ".join(errors)


def _load_pdf_diagnostic_text(
    raw_path: Path,
    pdf_text_override: str | None,
    pdf_path_override: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    pdf_path = pdf_path_override or _source_pdf_path(raw_path)
    pdf_origin = "map" if pdf_path_override is not None else "stage"
    if pdf_text_override is not None:
        return pdf_text_override, {
            "pdf_diagnostics_enabled": True,
            "source_pdf_path": str(pdf_path),
            "source_pdf_present": pdf_path.is_file(),
            "source_pdf_origin": pdf_origin,
            "pdf_text_status": "override",
            "pdf_text_chars": len(pdf_text_override),
            "pdf_text_error": None,
        }

    status, text, error = _extract_pdf_text(pdf_path)
    return text, {
        "pdf_diagnostics_enabled": True,
        "source_pdf_path": str(pdf_path),
        "source_pdf_present": pdf_path.is_file(),
        "source_pdf_origin": pdf_origin,
        "pdf_text_status": status,
        "pdf_text_chars": len(text),
        "pdf_text_error": error,
    }


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
    return Defect(
        id=defect_id,
        cc_class=cc_class,
        check=check,
        severity=severity,
        snippet=snippet[:260],
        line=block.line if block is not None else None,
        first_broken_stage=stage,
        hypothesis=hypothesis,
        proposed_fix_layer=proposed_fix_layer,
        regression_test=regression_test,
        extra=extra or {},
    )


def _is_references_block(block: Block, references_started: bool) -> bool:
    return references_started or block.id.startswith("ref-") or REFERENCES_HEADING_RE.match(block.text) is not None


def _has_nearby_image(blocks: list[Block], index: int, *, window: int = 6) -> bool:
    start = max(0, index - window)
    stop = min(len(blocks), index + window + 1)
    return any(block.has_img for block in blocks[start:stop])


def _has_nearby_missing_figure_warning(blocks: list[Block], index: int, *, window: int = 2) -> bool:
    start = max(0, index - window)
    stop = min(len(blocks), index + window + 1)
    return any("z2m-missing-figure-warning" in block.classes for block in blocks[start:stop])


def _is_handled_missing_figure_block(block: Block) -> bool:
    return (
        "z2m-missing-figure-unit" in block.classes
        and "z2m-missing-figure-warning" in block.raw
        and "z2m-figure-caption" in block.raw
    )


def _linked_ref_near_non_citation_context(block: Block) -> bool:
    for match in REF_LINK_RE.finditer(block.raw):
        window_raw = block.raw[max(0, match.start() - 48): match.end() + 80]
        window_text = _strip_tags(window_raw)
        if NONCITATION_CONTEXT_RE.search(window_text) or ML_PER_SECOND_CONTEXT_RE.search(window_text):
            return True
    return False


def _reference_target_numbers(html: str) -> set[int]:
    return {int(number) for number in re.findall(r"\bid\s*=\s*['\"]ref-(\d+)['\"]", html, re.IGNORECASE)}


def _figure_target_numbers(html: str) -> set[int]:
    return {int(number) for number in re.findall(r"\bid\s*=\s*['\"]fig-(\d+)['\"]", html, re.IGNORECASE)}


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


def _has_nearby_fig_link(block: Block, figure_num: str, text_pos: int) -> bool:
    raw_text = _strip_tags(block.raw)
    if text_pos >= len(raw_text):
        raw_window = block.raw
    else:
        raw_window = block.raw[max(0, text_pos - 180) : text_pos + 220]
    return re.search(rf"href\s*=\s*['\"]#fig-{re.escape(figure_num)}['\"]", raw_window, re.IGNORECASE) is not None


def _ref_match_inside_bracketed_reference_list(raw: str, start: int, end: int) -> bool:
    ref_anchor = re.search(r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+", raw[start:end], re.IGNORECASE)
    anchor_start = start + ref_anchor.start() if ref_anchor is not None else start
    left = raw.rfind("[", max(0, anchor_start - 100), anchor_start)
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


def _looks_like_numeric_vector(text: str, match: re.Match[str]) -> bool:
    body = match.group(0).strip()[1:-1]
    numbers = [int(item) for item in re.findall(r"\d+", body)]
    if not numbers:
        return False
    if any(number == 0 for number in numbers):
        return True
    left = text[max(0, match.start() - 100): match.start()].lower()
    return bool(
        re.search(
            r"\b(?:vector|vectors|assignment|assignments|likelihood|likelihoods|"
            r"score|scores|class|classes|elements|normalized|dividing)\b",
            left,
        )
    )


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
            return True
    return False


def _looks_like_figure_caption(block: Block) -> bool:
    if block.id.startswith("fig-"):
        return True
    if FIG_CAPTION_RE.match(block.text) is None:
        return False
    return re.match(
        r"^\s*(?:Figure|Fig\.?|FIGURE)\s+\d+[A-Za-z]?(?:\s*\([A-Za-z]\))?\s+"
        r"(?:shows|showed|illustrates|presents|contains)\b",
        block.text,
        re.IGNORECASE,
    ) is None


def _looks_like_float_or_caption(block: Block) -> bool:
    return (
        block.has_img
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
    if re.search(r"(?:u|µ|μ)m\s+\d+\b", match_text, re.IGNORECASE):
        return bool(re.search(r"(?:u|µ|μ)m\s*<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*\d+\s*</sup>", raw, re.IGNORECASE))
    if re.search(r"\b\d+(?:\.\d+)?\s*(?:u|µ|μ)?m\s*2\b", match_text, re.IGNORECASE):
        return bool(re.search(r"(?:u|µ|μ)m\s*<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*2\s*</sup>", raw, re.IGNORECASE))
    if re.search(r"\b(?:mC\s*cm|cd\s*m|kg\s*h|mg\s*kg\s*h)\s*[-\u2212]\s*\d+\b", match_text, re.IGNORECASE):
        return bool(re.search(r"<sup\b[^>]*\bz2m-unit-exp\b[^>]*>\s*-\d+\s*</sup>", raw, re.IGNORECASE))
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
        re.search(r"\b(?:department|hospital|university|medical\s+center|centre)\b", lowered)
        and re.search(r"\b(?:room|street|road|laan|avenue|netherlands|usa|uk)\b", lowered)
    ):
        return True
    return False


def _looks_like_table_of_contents_block(text: str) -> bool:
    normalized = _normalize_ws(text)
    lowered = normalized.lower()
    if "list of figures" in lowered or "list of tables" in lowered:
        return True
    section_hits = len(re.findall(r"\b\d+(?:\.\d+){1,3}\s+[A-Z][A-Za-z]", normalized))
    roman_page_hits = len(re.findall(r"\b(?:i{1,3}|iv|v|vi{0,3}|ix|x|xi{0,3})\b", lowered))
    chapter_hits = len(re.findall(r"\bchapte?\s*r\s+\d+\s*:", lowered))
    if chapter_hits >= 2 and section_hits >= 4:
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
            r"papers?|studies|review|museum|gallery|visitors?|participants?|technolog(?:y|ies|ical))\b",
            block.text,
            re.IGNORECASE,
        )
        sentence_count = len(re.findall(r"\w\.", block.text))
        if ref_count >= 2 and name_like_count >= 2 and not body_like and sentence_count <= 2:
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
    saw_unlinked_range = False
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
        if not saw_unlinked_range:
            match = CITATION_RANGE_LIST_RE.search(block.text)
            stat_numeric_context = STAT_NUMERIC_CONTEXT_RE.search(block.text) is not None
            if (
                not stat_numeric_context
                and (
                    (match and "z2m-ref-link" not in block.raw and not _looks_like_numeric_vector(block.text, match))
                    or _has_unlinked_tagged_citation_range(block)
                    or _has_unlinked_sup_numeric_range(block)
                )
            ):
                defects.append(
                    _defect(
                        defect_id="P04",
                        cc_class="CC-02",
                        check="Unlinked citation range/list remains in polish",
                        severity="error",
                        block=block,
                        snippet=block.text,
                        stage=POLISH_STAGE,
                        hypothesis="Citation grammar misses ranges, en-dash/hyphen spans, or comma-separated lists.",
                        proposed_fix_layer="EN polish citation parser",
                        regression_test="Link [1-4], [8-10], [11, 12], and mixed list/range citation forms.",
                    )
                )
                saw_unlinked_range = True
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
    return defects


def _reference_identity_defects(polish_blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    references_started = False
    seen_visible: dict[int, Block] = {}
    seen_ids: dict[int, Block] = {}
    saw_mismatch = False
    saw_duplicate = False
    saw_gap = False
    saw_duplicate_prefix = False

    for block in polish_blocks:
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
        visible_number = int(visible_match.group(1)) if visible_match is not None else None
        id_match = REF_ID_RE.match(block.id)
        id_number = int(id_match.group(1)) if id_match is not None else None
        if id_number is not None:
            seen_ids[id_number] = block

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
            re.search(r"\[\d+\]", match.group(1)) for match in INLINE_TEX_RE.finditer(block.raw)
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


def _figure_caption_ux_defects(polish_html: str, polish_blocks: list[Block]) -> list[Defect]:
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

    for block in polish_blocks:
        is_caption = bool(_looks_like_figure_caption(block) or TABLE_CAPTION_RE.match(block.text))
        if is_caption and CAPTION_TEX_RESIDUE_RE.search(block.raw):
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

    for block in polish_blocks:
        is_figure_caption = _looks_like_figure_caption(block)
        if (
            is_figure_caption
            and not _is_handled_missing_figure_block(block)
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
        if any(candidate.has_img for candidate in window):
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
        if not block.id.startswith("fig-") or block.has_img:
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
                candidate.has_img
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


def _manual_blind_spot_defects(polish_html: str, polish_blocks: list[Block]) -> list[Defect]:
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
                extra={"count": polish_html.count("\ufffd")},
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
            if candidate.tag == "p" and _starts_like_sentence_continuation(candidate.text):
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


def _meine_recent_manual_defects(polish_html: str, polish_blocks: list[Block]) -> list[Defect]:
    defects: list[Defect] = []
    slim_html = _structure_html(polish_html)
    plain = _plain_text(slim_html)
    ref_targets = _reference_target_numbers(slim_html)
    fig_targets = _figure_target_numbers(slim_html)
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
        if prefix in {"table", "figure", "section", "appendix", "chapter"}:
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
        linkless_raw = re.sub(r"<a\b[^>]*>.*?</a>", " ", block.raw, flags=re.IGNORECASE | re.DOTALL)
        linkless_text = _strip_tags(linkless_raw)
        flattened_match = FLATTENED_SUP_CITATION_RE.search(linkless_text)
        if flattened_match is None:
            continue
        number = int(flattened_match.group("num"))
        if number not in ref_targets:
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
            int(number)
            for number in re.findall(
                r"<p\b[^>]*\bz2m-figure-caption\b[^>]*>\s*(?:<a\b[^>]*>\s*)?"
                r"(?:Fig\.?|Figure)\s+(\d+)\b",
                body,
                re.IGNORECASE | re.DOTALL,
            )
        }
        unrelated = sorted((alias_nums | caption_nums) - {wrapper_num})
        if not unrelated:
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
    numeric_citation_dominant = numeric_ref_link_count >= 5 and numeric_sup_ref_link_count >= 5
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
        if comma_match is not None and _ref_match_inside_bracketed_reference_list(
            block.raw,
            comma_match.start(),
            comma_match.end(),
        ):
            comma_match = None
        if single_stat_match is not None and _ref_match_inside_bracketed_reference_list(
            block.raw,
            single_stat_match.start(),
            single_stat_match.end(),
        ):
            single_stat_match = None
        if comma_match is not None:
            context = _strip_tags(block.raw[max(0, comma_match.start() - 180) : comma_match.end() + 180])
            if re.search(
                r"\b(?:effect\s+size|allocation\s+ratio|G\*Power|sample\s+size|"
                r"statistical\s+power|power\s+analysis|Cohen)\b",
                context,
                re.IGNORECASE,
            ) is None:
                comma_match = None
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
            figure_num = int(match.group("num"))
            if figure_num in fig_targets:
                continue
            if _has_nearby_fig_link(block, match.group("num"), match.start()):
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
                    extra={"figure": figure_num, "visible_label": match.group(0)},
                )
            )
            break
        if defects and defects[-1].id == "P61":
            break

    missing_figure_match = MISSING_FIGURE_WARNING_RE.search(slim_html)
    if missing_figure_match is not None:
        defects.append(
            _defect(
                defect_id="P62",
                cc_class="CC-08/CC-13",
                check="Polish reports an extracted figure is missing",
                severity="warning",
                block=None,
                snippet=_snippet(slim_html, missing_figure_match.start(), missing_figure_match.end()),
                stage=RAW_STAGE,
                hypothesis="The final HTML is explicit about a missing source image, but the article is still visually incomplete.",
                proposed_fix_layer="Marker image extraction diagnostics or review packaging",
                regression_test="Visible z2m-missing-figure-warning blocks are counted in the audit JSON.",
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

    joined_word_match = KNOWN_JOINED_WORD_RE.search(plain)
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
    if known_ocr_match is not None:
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
                extra={"match": known_ocr_match.group(0)},
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

    doi_body_merge_match = DOI_BODY_PROSE_MERGE_RE.search(plain)
    if doi_body_merge_match is not None:
        defects.append(
            _defect(
                defect_id="P75",
                cc_class="CC-07/CC-13",
                check="DOI metadata is merged into following body prose",
                severity="warning",
                block=None,
                snippet=_snippet(plain, doi_body_merge_match.start(), doi_body_merge_match.end()),
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

    table_section_absorb_match = TABLE_SECTION_ABSORB_RE.search(plain)
    if table_section_absorb_match is not None:
        defects.append(
            _defect(
                defect_id="P77",
                cc_class="CC-07/CC-11/CC-13",
                check="Table block absorbs following sections or figure captions",
                severity="error",
                block=None,
                snippet=_snippet(plain, table_section_absorb_match.start(), table_section_absorb_match.end()),
                stage=POLISH_STAGE,
                hypothesis="A table/list extraction block kept reading through subsequent section headings and body paragraphs.",
                proposed_fix_layer="EN polish table/list boundary and reading-order repair",
                regression_test="Table 3.1 blocks do not swallow '3.8 Data Acquisition' and '3.9 Criteria for Use of Data'.",
            )
        )

    intra_word_space_match = INTRA_WORD_SPACE_RE.search(plain)
    if intra_word_space_match is not None:
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

    float_or_metadata_interruption_match = FLOAT_OR_METADATA_INTERRUPTION_RE.search(plain)
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

    split_dot_email_match = SPLIT_DOT_EMAIL_RE.search(plain)
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
    if bibliography_numbering_residue_match is not None:
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
    pdf_summary: dict[str, Any] = {
        "pdf_diagnostics_enabled": enable_pdf_diagnostics,
        "source_pdf_path": str(pdf_path_override or _source_pdf_path(raw_path)),
        "source_pdf_present": (pdf_path_override or _source_pdf_path(raw_path)).is_file(),
        "source_pdf_origin": "map" if pdf_path_override is not None else "stage",
        "pdf_text_status": "disabled",
        "pdf_text_chars": 0,
        "pdf_text_error": None,
    }

    defects: list[Defect] = []
    defects.extend(_frontmatter_defects(raw_blocks, polish_blocks))
    defects.extend(_citation_defects(polish_blocks))
    defects.extend(_reference_identity_defects(polish_blocks))
    defects.extend(_unit_math_defects(raw_html, polish_blocks))
    defects.extend(_equation_table_defects(polish_blocks))
    defects.extend(_figure_caption_ux_defects(polish_html, polish_blocks))
    defects.extend(_image_asset_defects(polish_path, polish_html))
    defects.extend(_manual_blind_spot_defects(polish_html, polish_blocks))
    defects.extend(_meine_recent_manual_defects(polish_html, polish_blocks))
    if enable_pdf_diagnostics or pdf_text_override is not None:
        pdf_text, pdf_summary = _load_pdf_diagnostic_text(raw_path, pdf_text_override, pdf_path_override)
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
    pairs: set[tuple[Path, Path]] = set()
    for root in roots:
        candidates: list[Path] = []
        if root.is_file():
            if root.name == POLISH_STAGE:
                candidates.append(root)
            elif root.name == RAW_STAGE and (root.parent / POLISH_STAGE).is_file():
                candidates.append(root.parent / POLISH_STAGE)
        elif root.exists():
            candidates.extend(root.rglob(POLISH_STAGE))
        for polish_path in candidates:
            raw_path = polish_path.parent / RAW_STAGE
            if raw_path.is_file():
                pairs.add((raw_path.resolve(strict=False), polish_path.resolve(strict=False)))
    return sorted(pairs, key=lambda pair: str(pair[1]))


def _add_corpus_hit_counts(articles: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for article in articles:
        seen = {defect["id"] for defect in article["defects_found"]}
        for defect_id in seen:
            counts[defect_id] = counts.get(defect_id, 0) + 1
    for article in articles:
        for defect in article["defects_found"]:
            defect["same_pattern_hits_across_corpus"] = counts.get(defect["id"], 0)
    return counts


def build_report(
    roots: list[Path],
    *,
    enable_pdf_diagnostics: bool = False,
    pdf_map: dict[str, Path] | None = None,
) -> dict[str, Any]:
    pairs = find_pairs(roots)
    articles = [
        analyze_pair(
            raw_path,
            polish_path,
            enable_pdf_diagnostics=enable_pdf_diagnostics,
            pdf_path_override=(pdf_map or {}).get(_article_name_from_stage(raw_path)),
        )
        for raw_path, polish_path in pairs
    ]
    defect_counts = _add_corpus_hit_counts(articles)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": f"{RAW_STAGE} -> {POLISH_STAGE}",
        "roots": [str(root) for root in roots],
        "article_count": len(articles),
        "corpus_summary": {
            "defect_counts": defect_counts,
            "totals": {
                "raw_img_tags": sum(article["summary"]["raw_img_tags"] for article in articles),
                "polish_img_tags": sum(article["summary"]["polish_img_tags"] for article in articles),
                "polish_ref_links": sum(article["summary"]["polish_ref_links"] for article in articles),
                "polish_fig_links": sum(article["summary"]["polish_fig_links"] for article in articles),
                "polish_table_links": sum(article["summary"]["polish_table_links"] for article in articles),
                "polish_page_links": sum(article["summary"]["polish_page_links"] for article in articles),
                "polish_replacement_chars": sum(article["summary"]["polish_replacement_chars"] for article in articles),
                "polish_missing_local_images": sum(
                    article["summary"]["polish_missing_local_images"] for article in articles
                ),
                "source_pdf_present": sum(1 for article in articles if article["summary"]["source_pdf_present"]),
                "pdf_text_chars": sum(article["summary"]["pdf_text_chars"] for article in articles),
            },
        },
        "articles": articles,
    }


def _print_summary(report: dict[str, Any]) -> None:
    print(f"EN raw/polish pair audit: {report['article_count']} pair(s)")
    totals = report["corpus_summary"]["totals"]
    print(
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
        print("Defects by check: " + ", ".join(f"{key}={value}" for key, value in sorted(defect_counts.items())))
    else:
        print("Defects by check: none")
    for article in report["articles"]:
        summary = article["summary"]
        print(
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
    report = build_report(args.roots, enable_pdf_diagnostics=args.pdf_diagnostics, pdf_map=pdf_map)
    _print_summary(report)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
