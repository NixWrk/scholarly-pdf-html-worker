from __future__ import annotations

import json
from pathlib import Path

from pdf_html_polish.zotero_pending import PENDING_ATTACHMENTS_FILE, load_pending_attachments


def test_load_pending_attachments_rejects_invalid_parent_ids(tmp_path: Path) -> None:
    required = {
        "source_pdf_path": "article.pdf",
        "html_path": "article.html",
        "queued_at_utc": "2026-07-15T00:00:00Z",
    }
    rows = [
        {**required, "parent_item_id": value}
        for value in (None, True, False, 0, -1, "not-an-id", "7")
    ]
    (tmp_path / PENDING_ATTACHMENTS_FILE).write_text(json.dumps(rows), encoding="utf-8")

    pending = load_pending_attachments(tmp_path)

    assert [row.parent_item_id for row in pending] == [7]
