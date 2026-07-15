"""Small runtime helpers shared by quality-loop orchestration code."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pdf_html_polish.html_stages import article_dir_from_html_stage


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]


def slug(value: str, *, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._")
    cleaned = re.sub(r"_+", "_", cleaned)
    return (cleaned or "article")[:max_len]


def _stable_truncated_slug(value: str, *, max_len: int) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._")
    cleaned = re.sub(r"_+", "_", cleaned) or "article"
    if len(cleaned) <= max_len:
        return cleaned

    digest = hashlib.sha1(cleaned.encode("utf-8", errors="ignore")).hexdigest()[:8]
    head_len = max_len - len(digest) - 1
    if head_len < 1:
        return digest[:max_len]
    return f"{cleaned[:head_len].rstrip('._')}_{digest}"


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def json_object(value: Any) -> dict[str, Any]:
    """Return a JSON object or an empty object for null/malformed values."""
    return value if isinstance(value, dict) else {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def console_text(value: Any) -> str:
    text = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def git_short_head(repo_root: Path = DEFAULT_REPO_ROOT) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, text=True).strip()
    except Exception:
        return ""


def git_dirty(repo_root: Path = DEFAULT_REPO_ROOT) -> bool:
    try:
        return bool(subprocess.check_output(["git", "status", "--short"], cwd=repo_root, text=True).strip())
    except Exception:
        return True


def profile_value(profile: dict[str, Any], key: str, default: str = "") -> str:
    return str(profile.get(key) or default)


def article_dir_from_stage(stage_path: Path) -> Path:
    return article_dir_from_html_stage(stage_path)


def article_name_from_stage(stage_path: Path) -> str:
    return article_dir_from_stage(stage_path).name


def artifact_hint(stage_path: Path, *, depth: int = 5) -> str:
    return str(Path(*stage_path.parts[-depth:])) if len(stage_path.parts) >= depth else str(stage_path)


def norm_path(value: Any) -> str:
    return str(Path(str(value)).resolve(strict=False)) if value else ""


def converted_article_id(raw_path: Path, index: int | None = None) -> str:
    del index
    article_dir = article_dir_from_stage(raw_path)
    version = article_dir.parent.name if article_dir.parent != article_dir else ""
    attachment = article_dir.parent.parent.name if article_dir.parent.parent != article_dir.parent else ""
    library = (
        article_dir.parent.parent.parent.name
        if article_dir.parent.parent.parent != article_dir.parent.parent
        else ""
    )
    prefix = "_".join(
        part
        for part in (
            slug(library, max_len=14),
            slug(attachment, max_len=10),
            slug(version, max_len=22),
        )
        if part
    )
    suffix = _stable_truncated_slug(article_dir.name, max_len=72)
    return f"{prefix}_{suffix}" if prefix else suffix
