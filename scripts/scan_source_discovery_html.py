"""Scan full-text discovery HTML files for web-polish planning.

This is a read-only diagnostic helper for the Zotero/source-discovery corpus.
It intentionally avoids third-party parser dependencies because it is meant to
run inside the existing project environment.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import argparse
import os
import re
import sys


DEFAULT_ROOTS = (
    Path(r"D:\Elvis_projects\Zotero_automatization\data\html\source_discovery"),
    Path("/data/html/source_discovery"),
)

PROVIDER_RE = re.compile(
    r"(?P<rank>\d+)\.(?P<provider>[^.]+)\.(?P<host>.+?)\.[0-9a-f]{10}(?:\.z2m_embedded)?\.html$"
)

SCRIPT_RE = re.compile(r"<script\b[\s\S]*?</script>", re.IGNORECASE)
STYLE_RE = re.compile(r"<style\b[\s\S]*?</style>", re.IGNORECASE)
NOSCRIPT_RE = re.compile(r"<noscript\b[\s\S]*?</noscript>", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")

SIGNATURES: tuple[tuple[str, str], ...] = (
    ("arxiv_latexml", "ltx_page_main"),
    ("pmc_main", 'id="main-content"'),
    ("pmc_article", "pmc-article"),
    ("jats", "jats"),
    ("tandf_fulltext", "hlFld-Fulltext"),
    ("tandf_nlm", "NLM_article"),
    ("springer_nature_body", "c-article-body"),
    ("springer_article", "main-content"),
    ("article_tag", "<article"),
    ("researchgate", "ResearchGate"),
    ("next_payload", "self.__next_f.push"),
    ("react_payload", "__NEXT_DATA__"),
)


@dataclass(frozen=True)
class ScanItem:
    path: Path
    provider: str
    host: str
    size: int
    signatures: tuple[str, ...]
    cleaned_text_len: int
    script_bytes: int
    same_doc_abs_fragment_hrefs: int
    local_asset_refs: int
    remote_image_refs: int
    data_image_refs: int


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--limit-examples", type=int, default=5)
    parser.add_argument("--all-html", action="store_true")
    parser.add_argument("--polish-smoke", action="store_true")
    args = parser.parse_args()

    root = args.root or first_existing_root()
    if root is None:
        print("No source_discovery root found.")
        return 2

    pattern = "*.html" if args.all_html else "*.z2m_embedded.html"
    items = [scan_file(path) for path in root.rglob(pattern)]
    items = [item for item in items if item is not None]

    print(f"root: {root}")
    print(f"files: {len(items)} ({pattern})")
    print()

    print("providers:")
    for provider, count in Counter(item.provider for item in items).most_common():
        print(f"  {provider:26} {count:5}")
    print()

    print("hosts:")
    for host, count in Counter(item.host for item in items).most_common(20):
        print(f"  {host:34} {count:5}")
    print()

    print("signatures:")
    signature_counts = Counter(signature for item in items for signature in item.signatures)
    for signature, count in signature_counts.most_common():
        print(f"  {signature:26} {count:5}")
    print()

    print("by provider/signature:")
    provider_signature_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for item in items:
        key = "+".join(item.signatures) if item.signatures else "none"
        provider_signature_counts[item.provider][key] += 1
    for provider in sorted(provider_signature_counts):
        print(f"  {provider}")
        for key, count in provider_signature_counts[provider].most_common(10):
            print(f"    {count:4} {key}")
    print()

    print("link/image totals:")
    print(f"  same_doc_abs_fragment_hrefs: {sum(item.same_doc_abs_fragment_hrefs for item in items)}")
    print(f"  local_asset_refs:           {sum(item.local_asset_refs for item in items)}")
    print(f"  remote_image_refs:          {sum(item.remote_image_refs for item in items)}")
    print(f"  data_image_refs:            {sum(item.data_image_refs for item in items)}")
    print(f"  script_bytes:               {sum(item.script_bytes for item in items)}")
    print()

    print("lowest cleaned text examples:")
    for item in sorted(items, key=lambda item: item.cleaned_text_len)[: args.limit_examples]:
        print(f"  {item.cleaned_text_len:7} {item.provider:26} {item.host:30} {item.path}")
    print()

    print("provider examples:")
    seen: set[str] = set()
    for item in sorted(items, key=lambda item: (item.provider, -item.cleaned_text_len)):
        if item.provider in seen:
            continue
        seen.add(item.provider)
        print(f"  {item.provider:26} {item.host:30} text={item.cleaned_text_len} sig={','.join(item.signatures) or 'none'}")
        print(f"    {item.path}")

    if args.polish_smoke:
        print()
        run_polish_smoke(items, limit_examples=args.limit_examples)

    return 0


def first_existing_root() -> Path | None:
    for root in DEFAULT_ROOTS:
        if root.exists():
            return root
    return None


def scan_file(path: Path) -> ScanItem | None:
    match = PROVIDER_RE.search(path.name)
    if match is None:
        return None
    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    sample = html[:1_000_000]
    lowered = sample.lower()
    signatures = tuple(name for name, needle in SIGNATURES if needle.lower() in lowered)
    scripts = SCRIPT_RE.findall(html)
    cleaned = strip_non_article_payloads(html)
    text = TAG_RE.sub(" ", cleaned)
    text = " ".join(text.split())

    href_values = re.findall(r"\bhref\s*=\s*['\"]([^'\"]+)['\"]", html, flags=re.IGNORECASE)
    same_doc_abs_fragment_hrefs = sum(
        1
        for href in href_values
        if href.startswith(("http://", "https://")) and "#" in href and not href.rstrip().endswith("#")
    )

    src_values = re.findall(r"\bsrc\s*=\s*['\"]([^'\"]+)['\"]", html, flags=re.IGNORECASE)
    remote_image_refs = sum(1 for src in src_values if src.startswith(("http://", "https://")))
    data_image_refs = sum(1 for src in src_values if src.startswith("data:image/"))
    local_asset_refs = sum(
        1
        for src in src_values
        if src
        and not src.startswith(("http://", "https://", "data:", "mailto:", "#", "javascript:"))
    )

    return ScanItem(
        path=path,
        provider=match.group("provider"),
        host=match.group("host"),
        size=os.path.getsize(path),
        signatures=signatures,
        cleaned_text_len=len(text),
        script_bytes=sum(len(script) for script in scripts),
        same_doc_abs_fragment_hrefs=same_doc_abs_fragment_hrefs,
        local_asset_refs=local_asset_refs,
        remote_image_refs=remote_image_refs,
        data_image_refs=data_image_refs,
    )


def strip_non_article_payloads(html: str) -> str:
    html = SCRIPT_RE.sub(" ", html)
    html = STYLE_RE.sub(" ", html)
    html = NOSCRIPT_RE.sub(" ", html)
    return html


def run_polish_smoke(items: list[ScanItem], *, limit_examples: int) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))

    from zoteropdf2md.web_html_polish import (  # pylint: disable=import-outside-toplevel
        WebHtmlPolishError,
        extract_web_article_fragment,
        require_web_article_html,
    )

    kind_counts: Counter[str] = Counter()
    selector_counts: Counter[str] = Counter()
    provider_extracted: dict[str, Counter[str]] = defaultdict(Counter)
    failures: list[tuple[ScanItem, str]] = []

    for item in items:
        try:
            html = item.path.read_text(encoding="utf-8", errors="replace")
            kind = require_web_article_html(html)
            extraction = extract_web_article_fragment(html, kind=kind)
        except WebHtmlPolishError as exc:
            failures.append((item, str(exc)))
            provider_extracted[item.provider]["rejected"] += 1
            continue
        except OSError as exc:
            failures.append((item, str(exc)))
            provider_extracted[item.provider]["read_error"] += 1
            continue

        kind_counts[kind.value] += 1
        provider_extracted[item.provider]["extracted" if extraction.extracted else "fallback"] += 1
        selector_counts[extraction.selector or "none"] += 1

    print("polish smoke kinds:")
    for kind, count in kind_counts.most_common():
        print(f"  {kind:26} {count:5}")
    print()

    print("polish smoke extracted/fallback by provider:")
    for provider in sorted(provider_extracted):
        stats = provider_extracted[provider]
        print(
            f"  {provider:26} extracted={stats['extracted']:4} "
            f"fallback={stats['fallback']:4} rejected={stats['rejected']:4} "
            f"read_error={stats['read_error']:4}"
        )
    print()

    print("polish smoke selectors:")
    for selector, count in selector_counts.most_common(20):
        print(f"  {selector:34} {count:5}")

    if failures:
        print()
        print("polish smoke failures:")
        for item, message in failures[:limit_examples]:
            print(f"  {item.provider:26} {item.host:30} {message}")
            print(f"    {item.path}")


if __name__ == "__main__":
    raise SystemExit(main())
