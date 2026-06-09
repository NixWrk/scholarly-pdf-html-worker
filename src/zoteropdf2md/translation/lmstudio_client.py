from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from time import perf_counter
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "local-model"
DEFAULT_CONTEXT_LENGTH = 32768

SYSTEM_PROMPT = """You are a professional scientific translator.
Translate English text to Russian.
Follow the user's marker protocol exactly.
Return only the translated text, with no explanations, no markdown fences, and no preface."""

USER_PROMPT_TEMPLATE = """Translate the following text from English to Russian.

Rules:
1. Preserve every marker exactly as written, including markers like <z2m-i1/>, @@Z2M_A0@@, and @@Z2M_T0@@.
2. Preserve DOI, URL, email addresses, formulas, citation numbers, and HTML-like placeholders.
3. Preserve uppercase technical acronyms such as IEEE, CMOS, RFID, ADC, RF, NFC, SAR, SNR.
4. Do not add comments. Output only the translation.
5. If a protected token is listed below, copy it byte-for-byte exactly. Do not translate it, transliterate it, localize it, change decimal separators, or change its case.

Protected tokens:
{protected_tokens}

Text:
{text}"""

PROMPT_LEAK_PATTERN = re.compile(
    r"translation\s*:|translated text\s*:|here is|rules\s*:|"
    r"translate the following|output only the translation|"
    r"вот перевод|правила\s*:|сохраняйте кажд",
    re.IGNORECASE,
)
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)

PROTECTED_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<z2m-i\d+/>", re.IGNORECASE),
    re.compile(r"@@Z2M_[A-Z]\d+@@", re.IGNORECASE),
    re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE),
    re.compile(r"\bdoi:\s*10\.\d{4,9}/[^\s<>()\"']+", re.IGNORECASE),
    re.compile(r"\b10\.\d{4,9}/[^\s<>()\"']+", re.IGNORECASE),
    re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\[[0-9,\s\-–—]+\]"),
    re.compile(r"\b(?:Fig|Figure|Table|Eq)\.?\s+[A-Za-z0-9().-]+", re.IGNORECASE),
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:Hz|kHz|MHz|GHz|V|mV|A|mA|W|mW|dB|cm|mm|um|µm|nm|ns|ms|s)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b[A-Z]{2,8}\d*\b"),
    re.compile(r"\b[A-Z]\s*=\s*[A-Za-z0-9^_{}+\-*/() ]{1,80}"),
)


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def lms_identifier_for_model(model_key: str, *, context_length: int | None = None) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_.-]+", "_", model_key).strip("._-")
    if context_length:
        identifier = f"{identifier}_ctx{int(context_length)}"
    if not identifier:
        identifier = "lmstudio_model"
    return identifier[:120]


def run_lms(args: list[str], *, timeout_s: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["lms", *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )


def lms_server_base_url(*, start_if_needed: bool = False, timeout_s: int = 120) -> str:
    status = run_lms(["server", "status"], timeout_s=timeout_s)
    text = f"{status.stdout}\n{status.stderr}"
    match = re.search(r"port\s+(\d+)", text, flags=re.IGNORECASE)
    if match:
        return f"http://127.0.0.1:{match.group(1)}/v1"

    if start_if_needed:
        started = run_lms(["server", "start"], timeout_s=timeout_s)
        if started.returncode != 0:
            raise RuntimeError(
                "Failed to start LM Studio server with lms: "
                f"{started.stdout.strip()} {started.stderr.strip()}".strip()
            )
        status = run_lms(["server", "status"], timeout_s=timeout_s)
        text = f"{status.stdout}\n{status.stderr}"
        match = re.search(r"port\s+(\d+)", text, flags=re.IGNORECASE)
        if match:
            return f"http://127.0.0.1:{match.group(1)}/v1"

    raise RuntimeError(
        "Cannot discover LM Studio server port from `lms server status`. "
        "Start the server or pass --base-url explicitly."
    )


def resolve_base_url(base_url: str, *, start_server: bool = False, timeout_s: int = 120) -> str:
    if base_url.strip().lower() == "auto":
        return lms_server_base_url(start_if_needed=start_server, timeout_s=timeout_s)
    return normalize_base_url(base_url)


def loaded_lms_identifiers(*, timeout_s: int = 120) -> set[str]:
    result = run_lms(["ps", "--json"], timeout_s=timeout_s)
    if result.returncode != 0:
        return set()
    try:
        rows = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return set()
    identifiers: set[str] = set()
    if not isinstance(rows, list):
        return identifiers
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("identifier", "modelKey", "model_key", "path", "displayName"):
            value = row.get(key)
            if value:
                identifiers.add(str(value))
    return identifiers


def load_lms_model(
    model_key: str,
    *,
    context_length: int = DEFAULT_CONTEXT_LENGTH,
    gpu: str = "max",
    parallel: int = 1,
    ttl: int = 3600,
    identifier: str | None = None,
    timeout_s: int = 1800,
) -> str:
    context_length = max(1024, int(context_length))
    identifier = identifier or lms_identifier_for_model(model_key, context_length=context_length)
    loaded = loaded_lms_identifiers(timeout_s=120)
    if identifier in loaded or model_key in loaded:
        return identifier

    args = [
        "load",
        model_key,
        "--context-length",
        str(context_length),
        "--gpu",
        gpu,
        "--parallel",
        str(max(1, int(parallel))),
        "--identifier",
        identifier,
        "-y",
    ]
    if ttl > 0:
        args.extend(["--ttl", str(int(ttl))])
    result = run_lms(args, timeout_s=timeout_s)
    if result.returncode != 0:
        raise RuntimeError(
            "Failed to load LM Studio model: "
            f"command=lms {' '.join(args)} "
            f"stdout={result.stdout.strip()} stderr={result.stderr.strip()}"
        )
    return identifier


def unload_lms_model(identifier: str, *, timeout_s: int = 120, missing_ok: bool = True) -> bool:
    identifier = (identifier or "").strip()
    if not identifier:
        return False
    loaded = loaded_lms_identifiers(timeout_s=min(timeout_s, 120))
    if identifier not in loaded:
        if missing_ok:
            return False
        raise RuntimeError(f"LM Studio model is not loaded: {identifier}")

    result = run_lms(["unload", identifier], timeout_s=timeout_s)
    if result.returncode != 0:
        if missing_ok and "not" in f"{result.stdout} {result.stderr}".lower():
            return False
        raise RuntimeError(
            "Failed to unload LM Studio model: "
            f"command=lms unload {identifier} "
            f"stdout={result.stdout.strip()} stderr={result.stderr.strip()}"
        )
    return True


def text_hash(text: str | None) -> str | None:
    if text is None:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def text_snippet(text: str | None, *, max_len: int = 240) -> str | None:
    if text is None:
        return None
    cleaned = html_lib.unescape(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max(0, max_len - 3)].rstrip() + "..."


def strip_model_chatter(text: str) -> str:
    cleaned = THINK_BLOCK_PATTERN.sub("", text).strip()
    cleaned = re.sub(r"^\s*(?:translation|translated text|перевод)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def protected_tokens_for_text(text: str, *, max_tokens: int = 80) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for pattern in PROTECTED_TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            token = match.group(0).strip()
            if not token or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
            if len(tokens) >= max_tokens:
                return tokens
    return tokens


def protected_token_prompt(text: str) -> str:
    tokens = protected_tokens_for_text(text)
    if not tokens:
        return "- none"
    return "\n".join(f"- {token}" for token in tokens)


def post_json(base_url: str, path: str, payload: dict[str, Any], *, timeout_s: int) -> dict[str, Any]:
    url = f"{normalize_base_url(base_url)}/{path.lstrip('/')}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LM Studio HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot connect to LM Studio at {url}: {exc}") from exc


def get_json(base_url: str, path: str, *, timeout_s: int) -> dict[str, Any]:
    url = f"{normalize_base_url(base_url)}/{path.lstrip('/')}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LM Studio HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot connect to LM Studio at {url}: {exc}") from exc


def list_models(base_url: str, *, timeout_s: int = 30) -> list[str]:
    data = get_json(base_url, "models", timeout_s=timeout_s)
    models = data.get("data") or []
    ids: list[str] = []
    for item in models:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
    return ids


@dataclass(frozen=True)
class LMStudioConfig:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 4096
    timeout_s: int = 600


class LMStudioInstructTranslator:
    def __init__(self, config: LMStudioConfig) -> None:
        self.config = config
        self.calls: list[dict[str, Any]] = []
        self._call_id = 0

    def reset_calls(self) -> None:
        self.calls.clear()
        self._call_id = 0

    def translate(self, text: str, *, call_type: str = "translate") -> str:
        if not text.strip():
            return text

        self._call_id += 1
        call_id = self._call_id
        started = perf_counter()
        target: str | None = None
        error_type: str | None = None
        error_message: str | None = None
        response_data: dict[str, Any] = {}
        try:
            payload = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": USER_PROMPT_TEMPLATE.format(
                            text=text,
                            protected_tokens=protected_token_prompt(text),
                        ),
                    },
                ],
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "max_tokens": self.config.max_tokens,
                "stream": False,
            }
            response_data = post_json(
                self.config.base_url,
                "chat/completions",
                payload,
                timeout_s=self.config.timeout_s,
            )
            choices = response_data.get("choices") or []
            if not choices:
                raise RuntimeError(f"LM Studio returned no choices: {response_data!r}")
            message = choices[0].get("message") or {}
            target = strip_model_chatter(str(message.get("content") or ""))
            return target or text
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc).replace("\n", " ").strip()
            if len(error_message) > 500:
                error_message = error_message[:500] + "..."
            raise
        finally:
            elapsed = perf_counter() - started
            choice0 = (response_data.get("choices") or [{}])[0] if response_data else {}
            usage = response_data.get("usage") or {}
            self.calls.append(
                {
                    "call_id": call_id,
                    "call_type": call_type,
                    "model": self.config.model,
                    "source_chars": len(text),
                    "target_chars": len(target) if target is not None else None,
                    "source_snippet": text_snippet(text),
                    "target_snippet": text_snippet(target),
                    "source_text_hash": text_hash(text),
                    "target_text_hash": text_hash(target),
                    "elapsed_s": round(elapsed, 4),
                    "finish_reason": choice0.get("finish_reason"),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                    "prompt_leak_like": bool(PROMPT_LEAK_PATTERN.search(target or "")),
                    "error_type": error_type,
                    "error": error_message,
                }
            )
