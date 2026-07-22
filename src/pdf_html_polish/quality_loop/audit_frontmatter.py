from __future__ import annotations

import re

from pdf_html_polish.html_stages import POLISH_STAGE_NAME, RAW_STAGE_NAME
from pdf_html_polish.quality_loop.audit_blocks import Block, Defect, normalize_ws
from pdf_html_polish.quality_loop.audit_diagnostics import make_defect


REF_LINK_RE = re.compile(r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-(\d+)['\"][^>]*>", re.IGNORECASE)
REF_LINK_BODY_RE = re.compile(
    r"<a\b[^>]*\bhref\s*=\s*['\"]#ref-\d+['\"][^>]*>(?P<body>[\s\S]{0,180}?)</a>",
    re.IGNORECASE,
)
REFERENCES_HEADING_RE = re.compile(r"^\s*(?:references|bibliography|works cited)\s*$", re.IGNORECASE)
FRONTMATTER_OCR_RE = re.compile(
    r"(?:\u00a9\s*\d|(?:\b[A-Z][A-Za-z.-]+\s+){1,3}"
    r"(?:\d+\s+\d+|\d+(?:\.\d+){2})\b)"
)


def _is_predominantly_cyrillic(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if len(letters) < 40:
        return False
    cyrillic_count = sum("\u0400" <= char <= "\u04ff" for char in letters)
    return cyrillic_count / len(letters) >= 0.7


def _numeric_marker_ref_link_count(raw: str) -> int:
    count = 0
    for match in REF_LINK_BODY_RE.finditer(raw):
        visible = normalize_ws(re.sub(r"<[^>]+>", " ", match.group("body"))).replace("&nbsp;", " ")
        if re.fullmatch(r"[\d\s,;\-\u2013\u2014]+", visible):
            count += 1
    return count


def block_looks_like_frontmatter_affiliation_table(block: Block) -> bool:
    if block.tag.lower() != "table" and "z2m-table-unit" not in block.classes:
        return False
    text = normalize_ws(block.text)
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


def frontmatter_name_candidates(text: str) -> list[str]:
    candidates = re.findall(
        r"\b[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){1,6}\b",
        text,
    )
    names: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = normalize_ws(candidate)
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(normalized)
    return names


def frontmatter_ocr_repaired_by_polish(raw_text: str, polish_blocks: list[Block]) -> bool:
    names = frontmatter_name_candidates(raw_text)
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
    relevant_text = normalize_ws(" ".join(block.text for block in relevant_blocks))
    if FRONTMATTER_OCR_RE.search(relevant_text):
        return False
    hit_count = sum(1 for name_key in name_keys if name_key in relevant_text.lower())
    return hit_count >= min(2, len(name_keys))


def looks_like_copyright_notice(text: str) -> bool:
    lowered = text.lower()
    return (
        "copyright" in lowered
        or "all rights reserved" in lowered
        or "creative commons" in lowered
        or "open access article" in lowered
        or "licensee" in lowered
        or "\u00a9" in text
    )


def looks_like_frontmatter_metadata_notice(text: str) -> bool:
    normalized = normalize_ws(text)
    lowered = normalized.lower()
    if "international publication date" in lowered and re.search(
        r"\b\d{1,2}(?:[./]\d{1,2}){2}\b|\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
        normalized,
    ):
        return True
    if re.fullmatch(
        r"IP\s+Address\s*:\s*(?:\d{1,3}\.){3}\d{1,3}",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if len(normalized) <= 100 and re.fullmatch(
        r"\d{1,3}/[\d,]+\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}(?:\s+\(\d{1,2}\.\d{1,2}\.\d{4}\))?\s+[A-Z]{2}",
        normalized,
    ):
        return True
    if (
        len(re.findall(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", normalized)) >= 2
        and re.search(
            r"\b(?:recebido|publica(?:\u00e7\u00e3o|cao)|vers(?:\u00e3o|ao)|aprova(?:\u00e7\u00e3o|cao))\b",
            lowered,
        )
    ):
        return True
    if (
        re.search(r"\bcorrespondence\b", lowered)
        and re.search(r"\b(?:e-?mail|email)\b|@", lowered)
        and re.search(r"\b(?:address|suite|street|avenue|road|doi)\b", lowered)
    ):
        return True
    if len(normalized) <= 90 and re.fullmatch(
        r"\d{4}\s+[A-Z][A-Za-z. ]{2,45}\s+\d{1,4}\s+\d{4,8}",
        normalized,
    ):
        return True
    if re.match(
        r"^(?:"
        r"Academic\s+Editors?\s*:|"
        r"(?:[*\u2217]\s*)?Equal\s+(?:advising|contribution)\b|"
        r"These\s+authors\s+contributed\s+equally\b|"
        r"See\s+(?:the\s+)?Comment\s+page\s+\d+\b|"
        r"(?:ASSETS|TEI|CHI|UIST|DIS)\s*['\u2019]?\s*\d{2}\b|"
        r"Open\s+Access\s+Support\s+provided\s+by\s*:|"
        r"Conference\s+Sponsors?\s*:|"
        r"Citation\s+in\s+BibTeX\s+format\b|"
        r"PDF\s+Download\b"
        r")",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if re.match(r"^publisher(?:'|\u2019)s\s+note\s*:", normalized, re.IGNORECASE):
        return True
    if lowered.startswith("citation:") and (
        "doi.org/" in lowered or re.search(r"\b\d{4}\b", normalized) is not None
    ):
        return True
    doi_mention_re = r"(?:\bdoi\s*:?\s*(?:https?://(?:dx\.)?doi\.org/)?10\.\S+|https?://(?:dx\.)?doi\.org/10\.\S+)"
    if lowered.startswith(("pre-print version.", "preprint version.")) and re.search(
        doi_mention_re, lowered
    ):
        return True
    if (
        (
            re.search(doi_mention_re, lowered)
            or re.search(r"\b10\.\d{4,9}/\S+", normalized)
        )
        and len(normalized) <= 600
        and re.search(r"\bet\s+al\.\.?|\bpp?\.\s*\d|\bhal-\d+", lowered)
    ):
        return True
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
        r"(?:(?:received|accepted|available\s+online|published|eingereicht|akzeptiert|angenommen|ver\u00f6ffentlicht)\s*:?\s*\d{1,4}(?:[./]\d{1,2}){2}\s*){2,5}",
        normalized,
        re.IGNORECASE,
    ):
        return True
    if re.fullmatch(
        r"(?:received|accepted|available\s+online|published|eingereicht|akzeptiert|angenommen|ver\u00f6ffentlicht)\s*:?\s*\d{1,2}\.\d{1,2}\.\d{4}\s+"
        r"(?:received|accepted|available\s+online|published|eingereicht|akzeptiert|angenommen|ver\u00f6ffentlicht)\s*:?\s*\d{1,2}\.\d{1,2}\.\d{4}",
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
    if re.search(
        r"\b(?:department|hospital|institute|university|medical\s+center|centre|"
        r"klinik(?:um)?|institut|universit(?:\u00e4t|aet|t)|fakult\u00e4t|abteilung)\b",
        lowered,
    ) and (
        re.search(
            r"\b(?:floor|room|street|road|laan|avenue|stra\u00dfe|strasse|weg|platz|kai)\b",
            lowered,
        )
        or re.search(r"\b\d{5}\s+[a-z\u00c0-\u00ff-]+", lowered)
    ):
        return True
    if (
        re.search(r"\b(?:tel\.?|fax|e-?mail|email|correspondence\s+to)\b|@", lowered)
        and re.search(
            r"\b(?:department|institute|university|school|college|hospital|center|centre|street|avenue|road|"
            r"universit\u00e4t|fakult\u00e4t|institut|abteilung|stra\u00dfe|"
            r"box|poland|india|sweden|usa|uk)\b",
            lowered,
        )
    ):
        return True
    return False


def looks_like_author_affiliation_index_line(text: str) -> bool:
    normalized = normalize_ws(text)
    if not (40 <= len(normalized) <= 700):
        return False
    if any(marker in normalized for marker in ("\u00a9", "В©")):
        return False
    name_hits = re.findall(
        r"\b[A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'-]+(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'-]+){0,3}\b",
        normalized,
    )
    if len(name_hits) < 3:
        return False
    if re.search(
        r"\b(?:abstract|introduction|methods?|results?|discussion)\b",
        normalized,
        re.IGNORECASE,
    ):
        return False
    if (
        re.search(r"(?:\b\d{1,2}\s*,?\s*){3,}$", normalized)
        and normalized.count(",") >= 2
    ):
        return True
    affiliation_hits = len(
        re.findall(
            r"\b(?:department|institute|university|school|faculty|centre|center)\b",
            normalized,
            re.IGNORECASE,
        )
    )
    line_number_hits = len(re.findall(r"(?<![\w.-])\d{1,2}(?![\w.-])", normalized))
    return affiliation_hits >= 2 and line_number_hits >= 6


def looks_like_frontmatter_table_or_highlight_text(text: str) -> bool:
    normalized = normalize_ws(text)
    lowered = normalized.lower()
    if (
        lowered.startswith("case no.")
        and re.search(r"\bage\b", lowered)
        and re.search(r"\bsex\b", lowered)
        and re.search(r"\b(?:lesion|deficit|procedure)\b", lowered)
    ):
        return True
    if all(
        marker in lowered for marker in ("subjects", "data points", "sessions", "total")
    ):
        return True
    if all(marker in lowered for marker in ("reading accuracy", "reading speed", "font size")):
        return True
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


def looks_like_table_of_contents_block(text: str) -> bool:
    normalized = normalize_ws(text)
    lowered = normalized.lower()
    supplementary_entries = len(
        re.findall(r"\bS\d{1,2}\s*:\s*[A-Z]", normalized)
    )
    page_tails = len(
        re.findall(
            r"(?:^|\s)(?:S\d{1,2}|[A-Z]|\d{1,2}\.)[^.!?]{8,120}\s+\d{1,3}(?=\s|$)",
            normalized,
        )
    )
    if supplementary_entries >= 2 and page_tails >= 4:
        return True
    if "list of figures" in lowered or "list of tables" in lowered:
        return True
    section_hits = len(re.findall(r"\b\d+(?:\.\d+){1,3}\s+[A-Z][A-Za-z]", normalized))
    numbered_heading_hits = len(re.findall(r"\b\d{1,2}\.\s+[A-Z][A-Za-z]", normalized))
    roman_page_hits = len(re.findall(r"\b(?:i{1,3}|iv|v|vi{0,3}|ix|x|xi{0,3})\b", lowered))
    chapter_hits = len(re.findall(r"\bchapte?\s*r\s+\d+\s*:", lowered))
    spelled_chapter_hits = len(
        re.findall(
            r"\bchapter\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\b",
            lowered,
        )
    )
    if (
        spelled_chapter_hits >= 3
        and len(re.findall(r"\b\d{1,4}\b", normalized)) >= 8
    ):
        return True
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


def frontmatter_defects(
    raw_blocks: list[Block],
    polish_blocks: list[Block],
    *,
    raw_stage: str = RAW_STAGE_NAME,
    polish_stage: str = POLISH_STAGE_NAME,
) -> list[Defect]:
    defects: list[Defect] = []
    raw_early = raw_blocks[:20]
    for block in raw_early:
        if block.text.lower().startswith("to cite this article:"):
            continue
        if _is_predominantly_cyrillic(block.text):
            continue
        if FRONTMATTER_OCR_RE.search(block.text):
            if looks_like_copyright_notice(block.text):
                continue
            if looks_like_frontmatter_metadata_notice(block.text):
                continue
            if looks_like_author_affiliation_index_line(block.text):
                continue
            if looks_like_frontmatter_table_or_highlight_text(block.text):
                continue
            if looks_like_table_of_contents_block(block.text):
                continue
            if frontmatter_ocr_repaired_by_polish(block.text, polish_blocks):
                continue
            defects.append(
                make_defect(
                    defect_id="P01",
                    cc_class="CC-01/CC-13",
                    check="Suspicious raw front-matter marker OCR",
                    severity="warning",
                    block=block,
                    snippet=block.text,
                    stage=raw_stage,
                    hypothesis="Author affiliation, corresponding-author, or footnote markers were damaged before polish.",
                    proposed_fix_layer="Marker raw audit or EN polish front-matter repair",
                    regression_test="Audit Nature/front-matter author lines with multi-affiliations and contribution markers.",
                )
            )
            break

    for block in polish_blocks[:25]:
        if "z2m-affiliations" in block.classes and REF_LINK_RE.search(block.raw):
            defects.append(
                make_defect(
                    defect_id="P02",
                    cc_class="CC-01/CC-02",
                    check="Affiliation block contains bibliography links",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Citation linkification ran inside a front-matter affiliation block.",
                    proposed_fix_layer="EN polish citation-linkification exclusion zones",
                    regression_test="Affiliation labels in z2m-affiliations must never link to #ref-*.",
                )
            )
            break

    for block in polish_blocks[:18]:
        ref_count = len(REF_LINK_RE.findall(block.raw))
        marker_ref_count = _numeric_marker_ref_link_count(block.raw)
        name_like_count = len(re.findall(r"\b[A-Z][A-Za-z.-]+\s+[A-Z][A-Za-z.-]+\b", block.text))
        body_like = re.search(
            r"\b(?:abstract|introduction|generative artificial intelligence|clinical|methodology|"
            r"papers?|studies|review|museum|gallery|visitors?|participants?|technolog(?:y|ies|ical)|"
            r"experimental|setup|tools?|toolkit|introduced|reported|developed|implementation|"
            r"behavior|behaviour|records?|measure|measured|larval|zebrafish|swim|swimming|"
            r"posture|locomotion|research|data|projects?|collections?|neuroimaging|"
            r"analys(?:is|es))\b",
            block.text,
            re.IGNORECASE,
        )
        bracket_citation_like = re.search(r"\[\s*\d{1,3}", block.text) is not None
        sentence_count = len(re.findall(r"\w\.", block.text))
        prose_before_trailing_markers = re.sub(
            r"\s+[\d\s,;\-\u2013\u2014]+$", "", block.text
        ).rstrip()
        prose_terminated = prose_before_trailing_markers.endswith((".", "!", "?"))
        if (
            marker_ref_count >= 2
            and name_like_count >= 2
            and not body_like
            and not bracket_citation_like
            and not prose_terminated
            and sentence_count <= 2
        ):
            defects.append(
                make_defect(
                    defect_id="P03",
                    cc_class="CC-01/CC-02",
                    check="Author-line markers link to bibliography refs",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Author affiliation markers were treated as bibliography citations.",
                    proposed_fix_layer="EN polish front-matter detection before reference linkification",
                    regression_test="Author names with superscript affiliation lists must stay unlinked.",
                    extra={
                        "ref_link_count": ref_count,
                        "marker_ref_link_count": marker_ref_count,
                        "name_like_count": name_like_count,
                    },
                )
            )
            break

    for left_index, left in enumerate(polish_blocks[:40]):
        left_text = normalize_ws(left.text)
        if (
            not left_text
            or left.tag != "p"
            or left_text.endswith((".", "!", "?", ":", ";"))
            or "z2m-front-matter" in left.classes
            or looks_like_frontmatter_metadata_notice(left_text)
            or looks_like_copyright_notice(left_text)
        ):
            continue
        metadata_count = 0
        first_metadata: Block | None = None
        cursor = left_index + 1
        while cursor < min(len(polish_blocks), 45):
            candidate = polish_blocks[cursor]
            candidate_text = normalize_ws(candidate.text)
            if not candidate_text:
                cursor += 1
                continue
            if (
                "z2m-front-matter" in candidate.classes
                or looks_like_frontmatter_metadata_notice(candidate_text)
                or looks_like_copyright_notice(candidate_text)
            ):
                if first_metadata is None:
                    first_metadata = candidate
                metadata_count += 1
                cursor += 1
                continue
            break
        if metadata_count < 2 or cursor >= len(polish_blocks):
            continue
        right = polish_blocks[cursor]
        right_text = normalize_ws(right.text)
        if right.tag != "p" or re.match(
            r"^(?:[a-z\u0430-\u044f\u0451]|and\b|or\b|among\b|\u0438\b|\u0430\b|\u043d\u043e\b|\u0441\u0440\u0435\u0434\u0438\b)",
            right_text,
        ) is None:
            continue
        if first_metadata is None:
            continue
        defects.append(
            make_defect(
                defect_id="P100",
                cc_class="CC-01/CC-02",
                check="Publication metadata interrupts a body sentence",
                severity="error",
                block=first_metadata,
                snippet=f"{left_text[-160:]} [metadata] {right_text[:160]}",
                stage=polish_stage,
                hypothesis="Front matter was emitted between two fragments of one body sentence.",
                proposed_fix_layer="EN polish metadata-gap sentence repair",
                regression_test="Publication metadata between sentence fragments must not split body prose.",
                extra={"metadata_block_count": metadata_count},
            )
        )
        break

    for block in polish_blocks[40:]:
        if "z2m-front-matter" not in block.classes:
            continue
        if REFERENCES_HEADING_RE.match(block.text):
            continue
        if (
            str(block.attrs.get("block-type") or "").lower() == "listgroup"
            or re.search(r"<(?:ul|ol|li)\b", block.raw, re.IGNORECASE)
        ):
            continue
        if len(block.text) < 80:
            continue
        if re.search(r"\b(?:clinical|validation|metrics|model|models|performance|evaluation|patients|studies)\b", block.text, re.IGNORECASE):
            defects.append(
                make_defect(
                    defect_id="P25",
                    cc_class="CC-01/CC-02",
                    check="Late body paragraph is marked as front matter",
                    severity="error",
                    block=block,
                    snippet=block.text,
                    stage=polish_stage,
                    hypothesis="Front-matter protection is too broad and suppresses valid body citation linking.",
                    proposed_fix_layer="EN polish bounded block-role/front-matter classifier",
                    regression_test="Body paragraphs after the article-start region must not carry z2m-front-matter.",
                )
            )
            break
    return defects
