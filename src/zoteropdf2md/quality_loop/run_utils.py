"""Small runtime helpers shared by quality-loop orchestration code."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]


def slug(value: str, *, max_len: int = 80) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._")
    cleaned = re.sub(r"_+", "_", cleaned)
    return (cleaned or "article")[:max_len]


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.is_file():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    return stage_path.parent.parent if stage_path.parent.name == "_z2m_stages" else stage_path.parent


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
    suffix = slug(article_dir.name, max_len=72)
    return f"{prefix}_{suffix}" if prefix else suffix
