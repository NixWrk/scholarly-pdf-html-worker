from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from html import unescape
from pathlib import Path
import re
import subprocess


TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_STYLE_RE = re.compile(r"<(script|style|svg|math)\b[\s\S]*?</\1>", re.IGNORECASE)
COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
CJK_RE = re.compile(r"[\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
HIRAGANA_KATAKANA_RE = re.compile(r"[\u3040-\u30FF]")
CJK_UNIFIED_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
BLOCK_TAG_RE = re.compile(
    r"</?(?:article|section|div|p|br|h[1-6]|li|ol|ul|table|thead|tbody|tfoot|tr|td|th)\b[^>]*>",
    re.IGNORECASE,
)
REFERENCE_HEADING_RE = re.compile(
    r"\b(?:references|bibliography|works cited|"
    r"\u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u0430|"
    r"\u0441\u043f\u0438\u0441\u043e\u043a\s+\u043b\u0438\u0442\u0435\u0440\u0430\u0442\u0443\u0440\u044b|"
    r"\u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0438)\b",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF\u0400-\u04FF]+")
LATIN_RE = re.compile(r"[A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u00FF]")
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")

WINDOW_CHARS = 4500
MAX_WINDOWS = 9

EN_STOPWORDS = {
    "a",
    "about",
    "after",
    "also",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "between",
    "by",
    "can",
    "for",
    "from",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "may",
    "not",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "these",
    "this",
    "to",
    "using",
    "was",
    "were",
    "which",
    "with",
}

RU_STOPWORDS = {
    "\u0431\u0435\u0437",
    "\u0431\u043e\u043b\u0435\u0435",
    "\u0431\u044b\u043b",
    "\u0431\u044b\u043b\u0430",
    "\u0431\u044b\u043b\u0438",
    "\u0431\u044b\u0442\u044c",
    "\u0432",
    "\u0432\u043e",
    "\u0434\u043b\u044f",
    "\u0434\u043e",
    "\u0435\u0433\u043e",
    "\u0435\u0435",
    "\u0435\u0441\u043b\u0438",
    "\u0438\u0437",
    "\u0438\u043b\u0438",
    "\u043a",
    "\u043a\u0430\u043a",
    "\u043c\u0435\u0436\u0434\u0443",
    "\u043d\u0430",
    "\u043d\u0435",
    "\u043d\u043e",
    "\u043e",
    "\u043e\u0431",
    "\u043e\u0442",
    "\u043f\u043e",
    "\u043f\u043e\u0441\u043b\u0435",
    "\u043f\u0440\u0438",
    "\u0441",
    "\u0441\u043e",
    "\u0442\u0430\u043a",
    "\u0442\u0430\u043a\u0436\u0435",
    "\u0442\u043e",
    "\u0443",
    "\u0447\u0442\u043e",
    "\u044d\u0442\u043e",
}

DE_STOPWORDS = {
    "aber",
    "als",
    "auch",
    "auf",
    "bei",
    "dem",
    "den",
    "der",
    "des",
    "deutschen",
    "diagnostik",
    "die",
    "diese",
    "dieser",
    "durch",
    "eine",
    "einem",
    "einen",
    "einer",
    "für",
    "haben",
    "ist",
    "mit",
    "nach",
    "nicht",
    "oder",
    "patienten",
    "sich",
    "sind",
    "sowie",
    "und",
    "untersuchung",
    "von",
    "werden",
    "wurde",
    "zur",
}

FR_STOPWORDS = {
    "avec",
    "cette",
    "dans",
    "des",
    "du",
    "elle",
    "est",
    "et",
    "les",
    "leur",
    "mais",
    "nous",
    "par",
    "pas",
    "pour",
    "que",
    "qui",
    "sont",
    "sur",
    "une",
    "aux",
    "ces",
    "comme",
    "dans",
    "entre",
    "être",
    "chez",
    "plus",
    "peut",
    "étude",
    "résultats",
    "méthode",
    "analyse",
}

ES_STOPWORDS = {
    "con",
    "como",
    "del",
    "desde",
    "dos",
    "el",
    "en",
    "entre",
    "es",
    "esta",
    "este",
    "estos",
    "las",
    "los",
    "más",
    "para",
    "pero",
    "por",
    "que",
    "se",
    "sin",
    "son",
    "sus",
    "también",
    "una",
    "uno",
    "estudio",
    "resultados",
    "método",
    "análisis",
}

IT_STOPWORDS = {
    "che",
    "con",
    "dei",
    "del",
    "della",
    "delle",
    "gli",
    "il",
    "in",
    "la",
    "le",
    "lo",
    "ma",
    "nel",
    "nella",
    "per",
    "più",
    "questo",
    "sono",
    "sulla",
    "tra",
    "uno",
    "studio",
    "risultati",
    "metodo",
    "analisi",
}

PT_STOPWORDS = {
    "com",
    "como",
    "das",
    "dos",
    "em",
    "entre",
    "esta",
    "este",
    "foi",
    "mais",
    "mas",
    "não",
    "os",
    "para",
    "por",
    "que",
    "são",
    "se",
    "sem",
    "uma",
    "estudo",
    "resultados",
    "método",
    "análise",
}

NL_STOPWORDS = {
    "als",
    "bij",
    "dat",
    "de",
    "der",
    "dit",
    "door",
    "een",
    "en",
    "het",
    "hun",
    "in",
    "is",
    "met",
    "niet",
    "om",
    "op",
    "te",
    "van",
    "voor",
    "werden",
    "zijn",
    "onderzoek",
    "resultaten",
    "methode",
    "analyse",
}

PL_STOPWORDS = {
    "ale",
    "analiza",
    "badania",
    "bez",
    "dla",
    "do",
    "jest",
    "jako",
    "które",
    "lub",
    "metoda",
    "na",
    "nie",
    "oraz",
    "po",
    "przez",
    "się",
    "są",
    "także",
    "tego",
    "to",
    "wyniki",
    "z",
    "ze",
}

EUROPEAN_STOPWORDS = {
    "de": DE_STOPWORDS,
    "fr": FR_STOPWORDS,
    "es": ES_STOPWORDS,
    "it": IT_STOPWORDS,
    "pt": PT_STOPWORDS,
    "nl": NL_STOPWORDS,
    "pl": PL_STOPWORDS,
}


@dataclass(frozen=True)
class LanguageDetection:
    detected_language: str
    confidence: float
    reason: str
    text_chars: int
    word_count: int
    latin_chars: int
    cyrillic_chars: int
    latin_ratio: float
    cyrillic_ratio: float
    english_stopword_hits: int
    russian_stopword_hits: int
    sampled_windows: int = 1
    window_language_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class LanguageGateDecision:
    should_skip: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PdfTextExtraction:
    status: str
    text: str
    error: str | None = None
    pages_total: int | None = None
    pages_sampled: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["text_chars"] = len(self.text)
        data.pop("text", None)
        return data


def normalize_language_code(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    aliases = {
        "english": "en",
        "eng": "en",
        "en-us": "en",
        "en-gb": "en",
        "russian": "ru",
        "rus": "ru",
        "ru-ru": "ru",
        "german": "de",
        "deu": "de",
        "ger": "de",
        "de-de": "de",
        "french": "fr",
        "fra": "fr",
        "fre": "fr",
        "fr-fr": "fr",
        "spanish": "es",
        "spa": "es",
        "es-es": "es",
        "italian": "it",
        "ita": "it",
        "it-it": "it",
        "portuguese": "pt",
        "por": "pt",
        "pt-br": "pt",
        "pt-pt": "pt",
        "dutch": "nl",
        "nld": "nl",
        "dut": "nl",
        "nl-nl": "nl",
        "polish": "pl",
        "pol": "pl",
        "pl-pl": "pl",
        "japanese": "ja",
        "jpn": "ja",
        "ja-jp": "ja",
        "chinese": "zh",
        "zho": "zh",
        "chi": "zh",
        "zh-cn": "zh",
        "zh-tw": "zh",
    }
    return aliases.get(normalized, normalized)


def visible_text_from_html(html: str, *, strip_references: bool = True) -> str:
    without_hidden = SCRIPT_STYLE_RE.sub(" ", html)
    without_comments = COMMENT_RE.sub(" ", without_hidden)
    with_block_breaks = BLOCK_TAG_RE.sub("\n", without_comments)
    text_with_lines = unescape(TAG_RE.sub(" ", with_block_breaks))
    text_with_lines = URL_RE.sub(" ", text_with_lines)
    if strip_references:
        lines = [re.sub(r"\s+", " ", line).strip() for line in text_with_lines.splitlines()]
        kept: list[str] = []
        consumed_chars = 0
        for line in lines:
            if REFERENCE_HEADING_RE.fullmatch(line) and consumed_chars > 180:
                break
            kept.append(line)
            consumed_chars += len(line) + 1
        text_with_lines = "\n".join(kept)
    text = re.sub(r"\s+", " ", text_with_lines).strip()
    if strip_references:
        match = REFERENCE_HEADING_RE.search(text)
        if match is not None and match.start() > 250:
            text = text[: match.start()].strip()
    return text


def detect_language_from_html(html: str) -> LanguageDetection:
    return detect_language_from_text(visible_text_from_html(html))


def detect_language_from_pdf(
    pdf_path: Path,
    *,
    max_pages: int = 15,
) -> tuple[LanguageDetection, PdfTextExtraction]:
    extraction = extract_text_from_pdf(pdf_path, max_pages=max_pages)
    detection = detect_language_from_text(extraction.text)
    return detection, extraction


def detect_language_from_text(text: str) -> LanguageDetection:
    normalized = re.sub(r"\s+", " ", text).strip()
    aggregate = _detect_language_once(normalized, min_alpha_chars=250, min_words=40)
    windows = [
        _detect_language_once(window, min_alpha_chars=160, min_words=24)
        for window in _sample_text_windows(normalized)
    ]
    return _combine_document_detection(aggregate, windows)


def _sample_text_windows(text: str) -> list[str]:
    if not text:
        return [""]
    if len(text) <= WINDOW_CHARS:
        return [text]
    span = max(1, len(text) - WINDOW_CHARS)
    count = min(MAX_WINDOWS, max(3, len(text) // WINDOW_CHARS + 1))
    starts = sorted({round(span * index / (count - 1)) for index in range(count)})
    return [text[start : start + WINDOW_CHARS] for start in starts]


def _sample_pdf_page_indexes(page_count: int, *, max_pages: int = 15) -> list[int]:
    if page_count <= 0 or max_pages <= 0:
        return []
    if page_count <= max_pages:
        return list(range(page_count))
    positions = {0, 1, 2, page_count - 3, page_count - 2, page_count - 1}
    remaining = max_pages - len([pos for pos in positions if 0 <= pos < page_count])
    if remaining > 0:
        span = page_count - 1
        for index in range(remaining):
            positions.add(round(span * (index + 1) / (remaining + 1)))
    return sorted(pos for pos in positions if 0 <= pos < page_count)[:max_pages]


def extract_text_from_pdf(pdf_path: Path, *, max_pages: int = 15) -> PdfTextExtraction:
    if not pdf_path.is_file():
        return PdfTextExtraction(status="missing", text="", error=None)

    errors: list[str] = []
    try:
        import fitz  # type: ignore[import-not-found]

        doc = fitz.open(str(pdf_path))
        try:
            pages = _sample_pdf_page_indexes(len(doc), max_pages=max_pages)
            text = "\n".join(doc[index].get_text("text") for index in pages)
            return PdfTextExtraction(
                status="pymupdf",
                text=text,
                pages_total=len(doc),
                pages_sampled=[index + 1 for index in pages],
            )
        finally:
            doc.close()
    except ImportError as exc:
        errors.append(f"pymupdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - extractor/environment specific
        errors.append(f"pymupdf failed: {exc}")

    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]

        reader = PdfReader(str(pdf_path))
        pages = _sample_pdf_page_indexes(len(reader.pages), max_pages=max_pages)
        text = "\n".join(reader.pages[index].extract_text() or "" for index in pages)
        return PdfTextExtraction(
            status="pypdf",
            text=text,
            pages_total=len(reader.pages),
            pages_sampled=[index + 1 for index in pages],
        )
    except ImportError as exc:
        errors.append(f"pypdf unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - extractor/environment specific
        errors.append(f"pypdf failed: {exc}")

    try:
        from PyPDF2 import PdfReader as PyPDF2Reader  # type: ignore[import-not-found]

        reader = PyPDF2Reader(str(pdf_path))
        pages = _sample_pdf_page_indexes(len(reader.pages), max_pages=max_pages)
        text = "\n".join(reader.pages[index].extract_text() or "" for index in pages)
        return PdfTextExtraction(
            status="pypdf2",
            text=text,
            pages_total=len(reader.pages),
            pages_sampled=[index + 1 for index in pages],
        )
    except ImportError as exc:
        errors.append(f"pypdf2 unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - extractor/environment specific
        errors.append(f"pypdf2 failed: {exc}")

    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode == 0:
            return PdfTextExtraction(status="pdftotext", text=result.stdout)
        errors.append(f"pdftotext failed: {result.stderr.strip() or result.returncode}")
    except FileNotFoundError as exc:
        errors.append(f"pdftotext unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - extractor/environment specific
        errors.append(f"pdftotext failed: {exc}")

    return PdfTextExtraction(status="unavailable", text="", error="; ".join(errors))


def _combine_document_detection(
    aggregate: LanguageDetection,
    windows: list[LanguageDetection],
) -> LanguageDetection:
    reliable = [
        window
        for window in windows
        if window.detected_language != "unknown" and window.confidence >= 0.65
    ]
    counts = Counter(window.detected_language for window in reliable)
    summary_counts = dict(sorted(counts.items()))
    if not reliable:
        return _with_window_summary(aggregate, windows, summary_counts)

    concrete_languages = {lang for lang in counts if lang not in {"unknown", "mixed"}}
    aggregate_lang = aggregate.detected_language
    top_lang, top_count = counts.most_common(1)[0]
    aggregate_count = counts.get(aggregate_lang, 0)

    if len(concrete_languages) >= 2 and aggregate_count < max(2, len(reliable) - 1):
        return _with_window_summary(
            LanguageDetection(
                detected_language="mixed",
                confidence=min(0.95, max(window.confidence for window in reliable)),
                reason="document_windows_disagree",
                text_chars=aggregate.text_chars,
                word_count=aggregate.word_count,
                latin_chars=aggregate.latin_chars,
                cyrillic_chars=aggregate.cyrillic_chars,
                latin_ratio=aggregate.latin_ratio,
                cyrillic_ratio=aggregate.cyrillic_ratio,
                english_stopword_hits=aggregate.english_stopword_hits,
                russian_stopword_hits=aggregate.russian_stopword_hits,
            ),
            windows,
            summary_counts,
        )

    if aggregate_lang == "unknown" and top_count >= 2:
        return _with_window_summary(
            _replace_detection(aggregate, top_lang, counts[top_lang], f"document_window_majority_{top_lang}"),
            windows,
            summary_counts,
        )

    if top_lang != aggregate_lang and top_count >= 2 and top_count > aggregate_count:
        return _with_window_summary(
            _replace_detection(aggregate, top_lang, top_count, f"document_window_majority_{top_lang}"),
            windows,
            summary_counts,
        )

    return _with_window_summary(aggregate, windows, summary_counts)


def _replace_detection(
    source: LanguageDetection,
    language: str,
    top_count: int,
    reason: str,
) -> LanguageDetection:
    confidence = max(source.confidence, min(0.94, 0.68 + top_count * 0.05))
    return LanguageDetection(
        detected_language=language,
        confidence=confidence,
        reason=reason,
        text_chars=source.text_chars,
        word_count=source.word_count,
        latin_chars=source.latin_chars,
        cyrillic_chars=source.cyrillic_chars,
        latin_ratio=source.latin_ratio,
        cyrillic_ratio=source.cyrillic_ratio,
        english_stopword_hits=source.english_stopword_hits,
        russian_stopword_hits=source.russian_stopword_hits,
    )


def _with_window_summary(
    detection: LanguageDetection,
    windows: list[LanguageDetection],
    counts: dict[str, int],
) -> LanguageDetection:
    return LanguageDetection(
        detected_language=detection.detected_language,
        confidence=detection.confidence,
        reason=detection.reason,
        text_chars=detection.text_chars,
        word_count=detection.word_count,
        latin_chars=detection.latin_chars,
        cyrillic_chars=detection.cyrillic_chars,
        latin_ratio=detection.latin_ratio,
        cyrillic_ratio=detection.cyrillic_ratio,
        english_stopword_hits=detection.english_stopword_hits,
        russian_stopword_hits=detection.russian_stopword_hits,
        sampled_windows=len(windows),
        window_language_counts=counts,
    )


def _detect_language_once(
    text: str,
    *,
    min_alpha_chars: int,
    min_words: int,
) -> LanguageDetection:
    text = re.sub(r"\s+", " ", text).strip()
    latin_chars = len(LATIN_RE.findall(text))
    cyrillic_chars = len(CYRILLIC_RE.findall(text))
    cjk_chars = len(CJK_RE.findall(text))
    kana_chars = len(HIRAGANA_KATAKANA_RE.findall(text))
    han_chars = len(CJK_UNIFIED_RE.findall(text))
    alpha_chars = latin_chars + cyrillic_chars
    script_chars = alpha_chars + cjk_chars
    words = [word.lower() for word in WORD_RE.findall(text)]
    english_hits = sum(1 for word in words if word in EN_STOPWORDS)
    russian_hits = sum(1 for word in words if word in RU_STOPWORDS)
    european_hits = {
        code: sum(1 for word in words if word in stopwords)
        for code, stopwords in EUROPEAN_STOPWORDS.items()
    }
    latin_ratio = latin_chars / alpha_chars if alpha_chars else 0.0
    cyrillic_ratio = cyrillic_chars / alpha_chars if alpha_chars else 0.0

    if cjk_chars >= min_alpha_chars and kana_chars >= 20:
        return LanguageDetection(
            detected_language="ja",
            confidence=0.96,
            reason="japanese_kana_cjk",
            text_chars=len(text),
            word_count=len(words),
            latin_chars=latin_chars,
            cyrillic_chars=cyrillic_chars,
            latin_ratio=latin_ratio,
            cyrillic_ratio=cyrillic_ratio,
            english_stopword_hits=english_hits,
            russian_stopword_hits=russian_hits,
        )
    if han_chars >= min_alpha_chars and kana_chars < 20:
        return LanguageDetection(
            detected_language="zh",
            confidence=0.94,
            reason="chinese_han_majority",
            text_chars=len(text),
            word_count=len(words),
            latin_chars=latin_chars,
            cyrillic_chars=cyrillic_chars,
            latin_ratio=latin_ratio,
            cyrillic_ratio=cyrillic_ratio,
            english_stopword_hits=english_hits,
            russian_stopword_hits=russian_hits,
        )

    if script_chars < min_alpha_chars or len(words) < min_words:
        return LanguageDetection(
            detected_language="unknown",
            confidence=0.0,
            reason="too_little_text",
            text_chars=len(text),
            word_count=len(words),
            latin_chars=latin_chars,
            cyrillic_chars=cyrillic_chars,
            latin_ratio=latin_ratio,
            cyrillic_ratio=cyrillic_ratio,
            english_stopword_hits=english_hits,
            russian_stopword_hits=russian_hits,
        )

    english_stop_score = min(english_hits / 35.0, 1.0)
    russian_stop_score = min(russian_hits / 25.0, 1.0)
    best_euro_code, best_euro_hits = max(european_hits.items(), key=lambda item: item[1])
    best_euro_stop_score = min(best_euro_hits / 35.0, 1.0)
    english_score = latin_ratio * 0.72 + english_stop_score * 0.28
    russian_score = cyrillic_ratio * 0.78 + russian_stop_score * 0.22
    european_score = latin_ratio * 0.70 + best_euro_stop_score * 0.30

    if cyrillic_chars >= 200 and cyrillic_ratio >= 0.35:
        confidence = max(0.86, min(0.99, russian_score))
        detected = "ru"
        reason = "cyrillic_majority"
    elif cyrillic_chars >= 120 and cyrillic_ratio >= 0.15 and russian_hits >= 8:
        confidence = max(0.8, min(0.98, russian_score))
        detected = "ru"
        reason = "russian_stopwords"
    elif (
        latin_ratio >= 0.72
        and best_euro_hits >= 12
        and best_euro_hits >= max(12, int(english_hits * 0.75))
    ):
        confidence = max(0.78, min(0.98, european_score))
        detected = best_euro_code
        reason = f"latin_majority_{best_euro_code}_stopwords"
    elif latin_ratio >= 0.72 and english_hits >= 12 and cyrillic_ratio < 0.12:
        confidence = max(0.78, min(0.99, english_score))
        detected = "en"
        reason = "latin_majority_english_stopwords"
    elif latin_ratio >= 0.35 and cyrillic_ratio >= 0.20:
        confidence = min(0.92, max(latin_ratio, cyrillic_ratio))
        detected = "mixed"
        reason = "substantial_latin_and_cyrillic"
    elif english_score > russian_score and english_score >= 0.65:
        detected = "en"
        confidence = min(0.9, english_score)
        reason = "english_score"
    elif russian_score > english_score and russian_score >= 0.65:
        detected = "ru"
        confidence = min(0.9, russian_score)
        reason = "russian_score"
    else:
        detected = "unknown"
        confidence = max(english_score, russian_score)
        reason = "low_confidence"

    return LanguageDetection(
        detected_language=detected,
        confidence=confidence,
        reason=reason,
        text_chars=len(text),
        word_count=len(words),
        latin_chars=latin_chars,
        cyrillic_chars=cyrillic_chars,
        latin_ratio=latin_ratio,
        cyrillic_ratio=cyrillic_ratio,
        english_stopword_hits=english_hits,
        russian_stopword_hits=russian_hits,
    )


def language_gate_decision(
    detection: LanguageDetection,
    *,
    target_language: str = "en",
    min_confidence: float = 0.75,
    skip_unknown: bool = False,
) -> LanguageGateDecision:
    target = normalize_language_code(target_language)
    detected = normalize_language_code(detection.detected_language)
    if not target or target in {"auto", "any", "all"}:
        return LanguageGateDecision(False, "no_target_language")
    if detected == target:
        return LanguageGateDecision(False, "target_language_detected")
    if detected == "unknown":
        if skip_unknown:
            return LanguageGateDecision(True, "unknown_language_requested_skip")
        return LanguageGateDecision(False, "unknown_language_allowed")
    if detection.confidence >= min_confidence:
        return LanguageGateDecision(True, f"detected_{detected}_not_{target}")
    return LanguageGateDecision(False, "non_target_below_threshold")
