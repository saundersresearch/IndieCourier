import re
from unittest.mock import MagicMock, patch
from urllib.parse import urljoin

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import parse_micropub_request, github_login, app
from schemas import Config, MicropubRequest
from schemas import MicropubRequest
from tests.conftest import FAKE_CONFIG

FAKE_FORM = {
    "h": "entry",
    "name": "Test Post",
    "content": "Hello world!",
    "category": ["test", "micropub"],
    "photo": "https://example.com/photo.jpg",   
}

FAKE_JSON = {
    "type": ["h-entry"],
    "properties": {
        "name": ["Test Post"],
        "content": ["Hello world!"],
        "category": ["test", "micropub"],
        "photo": ["https://example.com/photo.jpg"],
    }
}

def test_mf2_form_and_json_match():
    app = FastAPI()
    @app.post("/test")
    async def test_endpoint(parsed: MicropubRequest = Depends(parse_micropub_request)):
        return parsed
    
    client = TestClient(app)
    
    response_form = client.post(
        "/test",
        data=FAKE_FORM,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    response_json = client.post(
        "/test",
        json=FAKE_JSON,
        headers={"Content-Type": "application/json"},
    )

    assert response_form.json() == response_json.json()


FAKE_PATH = "assets/images/notes/1234567890_abcd1234.jpg"

FAKE_GITHUB_RESPONSE = {
    "content": MagicMock(path=FAKE_PATH),
    "commit": MagicMock(sha="fake-sha"),
}

def test_media_endpoint_form(client):
    mock_repo = MagicMock()
    mock_repo.create_file.return_value = FAKE_GITHUB_RESPONSE

    mock_github = MagicMock()
    mock_github.get_user.return_value.get_repo.return_value = mock_repo

    app.dependency_overrides[github_login] = lambda: mock_github

    with patch("app.github_login", return_value=mock_github):
        response = client.post(
            "/micropub",
            data=FAKE_FORM,
            headers={"Authorization": "Bearer fake_token"},
        )
    assert response.status_code == 202
    url = str(response.headers["Location"])
    expected_url_pattern = rf"{urljoin(str(FAKE_CONFIG.site_url), '/')}posts/\d{{4}}/\d{{2}}/\d{{2}}/test-post"
    assert re.fullmatch(expected_url_pattern, url)

def test_media_endpoint_json(client):
    mock_repo = MagicMock()
    mock_repo.create_file.return_value = FAKE_GITHUB_RESPONSE

    mock_github = MagicMock()
    mock_github.get_user.return_value.get_repo.return_value = mock_repo

    app.dependency_overrides[github_login] = lambda: mock_github

    with patch("app.github_login", return_value=mock_github):
        response = client.post(
            "/micropub",
            json=FAKE_JSON,
            headers={"Authorization": "Bearer fake_token"},
        )
    assert response.status_code == 202
    url = str(response.headers["Location"])
    expected_url_pattern = rf"{urljoin(str(FAKE_CONFIG.site_url), '/')}posts/\d{{4}}/\d{{2}}/\d{{2}}/test-post"
    assert re.fullmatch(expected_url_pattern, url)