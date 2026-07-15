from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re

from .language_detect import visible_text_from_html


REOCR_QUEUE_NAME = "_reocr_pending.json"
REOCR_MARKER_DIR_NAME = "_reocr_pending"
REOCR_SUFFIX = "_needs_reocr"

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]*|[\u0400-\u04FF][\u0400-\u04FF0-9'-]*")
LATIN_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9'-]*$")
VOWEL_RE = re.compile(r"[AEIOUYaeiouy]")
IMG_TAG_RE = re.compile(r"<img\b", re.IGNORECASE)
TABLE_TAG_RE = re.compile(r"<table\b", re.IGNORECASE)

KNOWN_OCR_TOKEN_RE = re.compile(
    r"\b(?:"
    r"Abstrac\s+t|Chapte\s+r|Append\s+i\s+ces|Bibliogra\s+phy|"
    r"Uroflowrnetry|uroflowrneter|Gra1Jimetry|RotCDTleter|PsyahoZogiaaZ|"
    r"A!Jstract|PRAVALENCE|OUALITY|miduretrhal|postvoding|"
    r"specifc|identifed|artifcial|ofline|afiliations|"
    r"fowrate|fuorescent|Urdynamic|non-invasivly|"
    r"oraotten|PATRATS|STLAR|daguerrectype|proccss|Negavives|"
    r"OPRATING\s+PRICIPLE|discription|milivolt|ghraph|Authers|"
    r"The\s+second\s+second|C\s+TANGET\s+STATE|Service\s+Surveyor|"
    r"GAT\s+CLEARING\s+LINE|PARTS\s+S|PROPERTY"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OcrQualityDecision:
    needs_reocr: bool
    score: float
    reasons: list[str]
    text_chars: int
    word_count: int
    image_count: int
    table_count: int
    replacement_chars: int
    damaged_token_count: int
    damaged_token_ratio: float
    known_ocr_hits: int
    sample_bad_tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ReocrQueueResult:
    queue_path: Path
    marker_path: Path | None
    added: bool
    pending_total: int
    reocr_alias_base_name: str


def _normalize_path(path: Path) -> str:
    return os.path.normcase(str(path.expanduser().resolve(strict=False)))


def reocr_alias_base_name(alias_base_name: str) -> str:
    return alias_base_name if alias_base_name.endswith(REOCR_SUFFIX) else f"{alias_base_name}{REOCR_SUFFIX}"


def _is_damaged_token(token: str) -> bool:
    if len(token) < 5 or not LATIN_WORD_RE.match(token):
        return False
    lower = token.lower().strip("-'")
    if not lower or lower.isdigit():
        return False
    if VOWEL_RE.search(lower) is None and not re.fullmatch(r"[ivxlcdm]+", lower):
        return True
    if re.search(r"[A-Za-z]\d[A-Za-z]|\d[A-Za-z]{2,}\d", token):
        return True
    if re.search(r"[A-Z]{2,}[a-z][A-Z]|[a-z][A-Z]{2,}[a-z]", token):
        return True
    if re.search(r"(?:rn|vv|ii|ll){3,}", lower):
        return True
    return False


def assess_ocr_quality_from_html(html: str) -> OcrQualityDecision:
    text = visible_text_from_html(html, strip_references=False)
    words = WORD_RE.findall(text)
    damaged_tokens = [token for token in words if _is_damaged_token(token)]
    damaged_ratio = len(damaged_tokens) / max(len(words), 1)
    known_hits = len(KNOWN_OCR_TOKEN_RE.findall(text))
    replacement_chars = text.count("\ufffd")
    image_count = len(IMG_TAG_RE.findall(html))
    table_count = len(TABLE_TAG_RE.findall(html))

    reasons: list[str] = []
    if len(text) < 400 and image_count >= 2:
        reasons.append("too_little_extractable_text_with_images")
    if len(words) < 60 and image_count >= 2:
        reasons.append("too_few_words_with_images")
    if len(text) >= 1000 and replacement_chars >= 5:
        reasons.append("visible_replacement_characters")
    if len(damaged_tokens) >= 25 and damaged_ratio >= 0.18:
        reasons.append("high_damaged_token_ratio")
    if known_hits >= 4:
        reasons.append("known_ocr_residue_hits")
    if known_hits >= 2 and (damaged_ratio >= 0.08 or table_count >= 2):
        reasons.append("ocr_residue_cluster")

    score = 1.0
    if len(text) < 400 and image_count >= 2:
        score -= 0.35
    if len(words) < 60 and image_count >= 2:
        score -= 0.25
    score -= min(0.35, damaged_ratio * 1.4)
    score -= min(0.25, known_hits * 0.04)
    if len(text) >= 1000:
        score -= min(0.20, replacement_chars / max(len(text), 1) * 60)
    score = max(0.0, min(1.0, round(score, 3)))

    needs_reocr = bool(reasons) or score < 0.55
    return OcrQualityDecision(
        needs_reocr=needs_reocr,
        score=score,
        reasons=reasons,
        text_chars=len(text),
        word_count=len(words),
        image_count=image_count,
        table_count=table_count,
        replacement_chars=replacement_chars,
        damaged_token_count=len(damaged_tokens),
        damaged_token_ratio=round(damaged_ratio, 4),
        known_ocr_hits=known_hits,
        sample_bad_tokens=sorted(set(damaged_tokens), key=str.lower)[:20],
    )


def load_reocr_queue(output_dir: Path) -> list[dict[str, object]]:
    queue_path = output_dir / REOCR_QUEUE_NAME
    if not queue_path.is_file():
        return []
    try:
        data = json.loads(queue_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    entries = data.get("entries") if isinstance(data, dict) else data
    return entries if isinstance(entries, list) else []


def _write_reocr_queue(output_dir: Path, entries: list[dict[str, object]]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    queue_path = output_dir / REOCR_QUEUE_NAME
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue": "reocr",
        "suffix": REOCR_SUFFIX,
        "pending_total": len(entries),
        "entries": entries,
    }
    queue_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return queue_path


def enqueue_reocr_candidate(
    *,
    output_dir: Path,
    source_pdf_path: Path,
    alias_base_name: str,
    artifact_path: Path,
    stage_raw_path: Path | None,
    decision: OcrQualityDecision,
) -> ReocrQueueResult:
    reocr_alias = reocr_alias_base_name(alias_base_name)
    entries = load_reocr_queue(output_dir)
    source_norm = _normalize_path(source_pdf_path)
    alias_norm = alias_base_name.lower()
    now = datetime.now(timezone.utc).isoformat()

    entry: dict[str, object] = {
        "queued_at": now,
        "source_pdf_path": str(source_pdf_path),
        "source_pdf_norm": source_norm,
        "alias_base_name": alias_base_name,
        "reocr_alias_base_name": reocr_alias,
        "suffix": REOCR_SUFFIX,
        "artifact_path": str(artifact_path),
        "stage_raw_path": "" if stage_raw_path is None else str(stage_raw_path),
        "ocr_quality": decision.to_dict(),
    }

    added = True
    merged: list[dict[str, object]] = []
    for existing in entries:
        if (
            str(existing.get("source_pdf_norm", "")) == source_norm
            and str(existing.get("alias_base_name", "")).lower() == alias_norm
        ):
            merged.append(entry)
            added = False
        else:
            merged.append(existing)
    if added:
        merged.append(entry)

    queue_path = _write_reocr_queue(output_dir, merged)

    marker_dir = output_dir / REOCR_MARKER_DIR_NAME
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker_path = marker_dir / f"{reocr_alias}.json"
    marker_path.write_text(
        json.dumps(entry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return ReocrQueueResult(
        queue_path=queue_path,
        marker_path=marker_path,
        added=added,
        pending_total=len(merged),
        reocr_alias_base_name=reocr_alias,
    )
