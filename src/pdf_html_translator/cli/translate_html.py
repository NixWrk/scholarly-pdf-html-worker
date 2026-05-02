from __future__ import annotations

import runpy
import sys
from collections.abc import Sequence
from pathlib import Path


def main(argv: Sequence[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "experiments" / "lmstudio_instruct_translation" / "run_html_probe.py"
    if not script.is_file():
        raise SystemExit(f"LM Studio runner not found: {script}")
    sys.argv = [str(script), *(list(argv) if argv is not None else sys.argv[1:])]
    try:
        runpy.run_path(str(script), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
