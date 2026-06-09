from __future__ import annotations

from collections.abc import Sequence

from zoteropdf2md.translation.html_probe import main as run_html_probe_main


def main(argv: Sequence[str] | None = None) -> int:
    return run_html_probe_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
