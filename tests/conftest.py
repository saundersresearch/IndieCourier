from unittest.mock import AsyncMock, patch
from urllib.parse import urljoin

import pytest
from fastapi.testclient import TestClient
from pydantic_settings import SettingsConfigDict

from app import MicropubConfigResponse, app
from config import Config, load_config

class FakeConfig(Config):
    model_config = SettingsConfigDict(
        env_file=None,
        json_file=None,
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(cls, settings_cls, **kwargs):
        return (kwargs["init_settings"],)  # only init_settings, nothing else
    
FAKE_CONFIG = FakeConfig(
    me="https://example.com",
    token_endpoint="https://tokens.indieauth.com/token",
    site_url="http://localhost:8000",
    syndicate_to=[{"uid": "twitter", "name": "Twitter", "service": None, "user": None}],
    github_repo="example-repo",
    github_token="fake-github-token",
    github_user="fake-github-user",
    content_dir="_notes",
    media_dir="assets/images/notes",
)

FAKE_TOKEN_RESPONSE = """
{
    "me": "https://example.com",
    "issued_by":"https://tokens.indieauth.com/token",
    "client_id":"https://example.com/micropub/",
    "issued_at": 173679503,
    "scope":"create update delete",
    "nonce": 173679503
}
"""

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def mock_token():
    with patch("auth.introspect_token", new=AsyncMock(return_value=FAKE_TOKEN_RESPONSE)):
        app.dependency_overrides[load_config] = lambda: FAKE_CONFIG
        yield  # tests run here
        app.dependency_overrides.clear()  # teardown after each test