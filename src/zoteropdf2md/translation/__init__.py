"""HTML translation runner package."""

from __future__ import annotations

__all__ = [
    "LMStudioConfig",
    "LMStudioInstructTranslator",
    "build_parser",
    "main",
    "run",
]


def __getattr__(name: str):
    if name in {"build_parser", "main", "run"}:
        from . import html_probe

        return getattr(html_probe, name)
    if name in {"LMStudioConfig", "LMStudioInstructTranslator"}:
        from . import lmstudio_client

        return getattr(lmstudio_client, name)
    raise AttributeError(name)
