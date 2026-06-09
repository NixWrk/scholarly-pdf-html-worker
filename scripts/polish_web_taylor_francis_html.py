"""Polish Taylor & Francis full-article HTML attachments."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zoteropdf2md.web_polish.cli import main_taylor_francis


if __name__ == "__main__":
    raise SystemExit(main_taylor_francis())
