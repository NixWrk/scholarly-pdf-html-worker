from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pdf_html_polish.webdav_config import WebDavServer
from pdf_html_polish.webdav_uploader import WebDavUploader, _build_remote_url


@pytest.mark.parametrize(
    "remote_path",
    ["../secret.html", "folder/../../secret.html", "%2e%2e/secret.html"],
)
def test_build_remote_url_rejects_traversal(remote_path: str) -> None:
    server = WebDavServer(url="https://dav.example.test", remote_root="articles")

    with pytest.raises(ValueError, match="must stay below"):
        _build_remote_url(server, remote_path)


def test_upload_file_rejects_invalid_remote_root_without_network(tmp_path: Path) -> None:
    source = tmp_path / "article.html"
    source.write_text("<p>ok</p>", encoding="utf-8")
    server = WebDavServer(url="https://dav.example.test", remote_root="../escape")

    with (
        patch("pdf_html_polish.webdav_uploader.requests.request") as request,
        patch("pdf_html_polish.webdav_uploader.requests.put") as put,
    ):
        ok, message = WebDavUploader().upload_file(server, source, "article.html")

    assert not ok
    assert "Invalid remote path" in message
    request.assert_not_called()
    put.assert_not_called()


def test_ensure_remote_dirs_rejects_embedded_separator_without_network() -> None:
    server = WebDavServer(url="https://dav.example.test")

    with patch("pdf_html_polish.webdav_uploader.requests.request") as request:
        ok, message = WebDavUploader().ensure_remote_dirs(server, ["safe/escape"])

    assert not ok
    assert "Invalid remote path" in message
    request.assert_not_called()
