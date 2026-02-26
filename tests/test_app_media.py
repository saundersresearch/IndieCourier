from urllib.parse import urljoin
from unittest.mock import MagicMock, patch

from app import github_login, app
from tests.conftest import FAKE_CONFIG

FAKE_PATH = "assets/images/notes/1234567890_abcd1234.jpg"

FAKE_GITHUB_RESPONSE = {
    "content": MagicMock(path=FAKE_PATH),
    "commit": MagicMock(sha="fake-sha"),
}

def test_media_endpoint(client):
    mock_repo = MagicMock()
    mock_repo.create_file.return_value = FAKE_GITHUB_RESPONSE

    mock_github = MagicMock()
    mock_github.get_user.return_value.get_repo.return_value = mock_repo

    app.dependency_overrides[github_login] = lambda: mock_github

    with patch("app.github_login", return_value=mock_github):
        response = client.post(
            "/media",
            files={"file": ("test.jpg", b"fake image data", "image/jpeg")},
            headers={"Authorization": "Bearer fake_token"},
        )
    assert response.status_code == 201
    assert response.headers["Location"] == urljoin(str(FAKE_CONFIG.site_url), FAKE_PATH)