import base64
import re
from unittest.mock import MagicMock, patch
from urllib.parse import urljoin

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import mf2py

from app import parse_micropub_request, github_login, app
from schemas import Config, MicropubRequest
from schemas import MicropubRequest
from tests.conftest import FAKE_CONFIG

FAKE_CONTENT = """---
type: entry
tags:
- foo
- bar
photo:
  value: https://photos.example.com/globe.gif
  alt: Spinning globe animation
syndicate_to: bluesky
---
hello world
"""

FAKE_CONTENT_DELETED = """---
type: entry
tags:
- foo
- bar
photo:
  value: https://photos.example.com/globe.gif
  alt: Spinning globe animation
syndicate_to: bluesky
published: false
---
hello world
"""

FAKE_GITHUB_RESPONSE = {
    "content": MagicMock(decoded_content=base64.b64encode(FAKE_CONTENT.encode("utf-8"))),
    "commit": MagicMock(sha="fake-sha"),
}

FAKE_GITHUB_RESPONSE_DELETED = {
    "content": MagicMock(decoded_content=base64.b64encode(FAKE_CONTENT_DELETED.encode("utf-8"))),
    "commit": MagicMock(sha="fake-sha"),
}

def test_micropub_delete(client):
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_contents = MagicMock()
    mock_github.get_user.return_value.get_repo.return_value = mock_repo
    mock_repo.get_contents.return_value = mock_contents
    mock_contents.decoded_content = FAKE_CONTENT.encode("utf-8")
    mock_repo.get_user.return_value.get_repo.return_value.update_contents.return_value = None

    app.dependency_overrides[github_login] = lambda: mock_github

    with patch("app.github_login", return_value=mock_github):
        with open("tests/test_article.html") as f:
            mf2_parser = mf2py.parse(doc=f)
        with patch("mf2py.parse", return_value=mf2_parser):
            url = urljoin(str(FAKE_CONFIG.site_url), "/posts/2024/06/01/test-post")

            response = client.post(
                "/micropub",
                data={"action": "delete", "url": url},
                headers={"Authorization": "Bearer fake_token"},
            )
        assert response.status_code == 204

    with patch("app.github_login", return_value=mock_github):
        with open("tests/test_note.html") as f:
            mf2_parser = mf2py.parse(doc=f)
        with patch("mf2py.parse", return_value=mf2_parser):
            url = urljoin(str(FAKE_CONFIG.site_url), "/notes/2024/06/01/1772160815")

            response = client.post(
                "/micropub",
                data={"action": "delete", "url": url},
                headers={"Authorization": "Bearer fake_token"},
            )
        assert response.status_code == 204



def test_micropub_undelete(client):
    mock_github = MagicMock()
    mock_repo = MagicMock()
    mock_contents = MagicMock()
    mock_github.get_user.return_value.get_repo.return_value = mock_repo
    mock_repo.get_contents.return_value = mock_contents
    mock_contents.decoded_content = FAKE_CONTENT_DELETED.encode("utf-8")
    mock_repo.get_user.return_value.get_repo.return_value.update_contents.return_value = None

    app.dependency_overrides[github_login] = lambda: mock_github

    with patch("app.github_login", return_value=mock_github):
        with open("tests/test_article.html") as f:
            mf2_parser = mf2py.parse(doc=f)
        with patch("mf2py.parse", return_value=mf2_parser):
            url = urljoin(str(FAKE_CONFIG.site_url), "/posts/2024/06/01/test-post")

            response = client.post(
                "/micropub",
                data={"action": "undelete", "url": url},
                headers={"Authorization": "Bearer fake_token"},
            )
        assert response.status_code == 204

    with patch("app.github_login", return_value=mock_github):
        with open("tests/test_note.html") as f:
            mf2_parser = mf2py.parse(doc=f)
        with patch("mf2py.parse", return_value=mf2_parser):
            url = urljoin(str(FAKE_CONFIG.site_url), "/notes/2024/06/01/1772160815")

            response = client.post(
                "/micropub",
                data={"action": "undelete", "url": url},
                headers={"Authorization": "Bearer fake_token"},
            )
        assert response.status_code == 204

