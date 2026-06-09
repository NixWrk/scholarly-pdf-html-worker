"""Compatibility wrapper for the packaged LM Studio client."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.translation.lmstudio_client import *  # noqa: F401,F403,E402
