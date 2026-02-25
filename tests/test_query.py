from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic_settings import SettingsConfigDict

from app import MicropubConfigResponse, app
from config import Config, load_config

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
    media_endpoint="https://example.com/micropub/media",
    syndicate_to=[{"uid": "twitter", "name": "Twitter", "service": None, "user": None}],
)

FAKE_CONFIG_RESPONSE = MicropubConfigResponse(
    me=FAKE_CONFIG.me,
    token_endpoint=FAKE_CONFIG.token_endpoint,
    media_endpoint=FAKE_CONFIG.media_endpoint,
    syndicate_to=FAKE_CONFIG.syndicate_to,
)

FAKE_SYNDICATION_RESPONSE = MicropubConfigResponse(syndicate_to=FAKE_CONFIG.syndicate_to)

FAKE_MEDIA_RESPONSE = MicropubConfigResponse(media_endpoint=FAKE_CONFIG.media_endpoint)


@pytest.fixture(autouse=True)
def override_config():
    app.dependency_overrides[load_config] = lambda: FAKE_CONFIG
    yield  # tests run here
    app.dependency_overrides.clear()  # teardown after each test


@pytest.fixture
def client():
    return TestClient(app)


def test_config(client):
    with patch("app.verify_authorization_token", new=AsyncMock(return_value=FAKE_TOKEN_RESPONSE)):
        response = client.get("/micropub?q=config", headers={"Authorization": "Bearer fake_token"})
        actual = MicropubConfigResponse.model_validate(response.json())
        assert actual == FAKE_CONFIG_RESPONSE


def test_syndicate_to(client):
    with patch("app.verify_authorization_token", new=AsyncMock(return_value=FAKE_TOKEN_RESPONSE)):
        response = client.get("/micropub?q=syndicate-to", headers={"Authorization": "Bearer fake_token"})
        actual = MicropubConfigResponse.model_validate(response.json())
        assert actual == FAKE_SYNDICATION_RESPONSE


def test_media_endpoint(client):
    with patch("app.verify_authorization_token", new=AsyncMock(return_value=FAKE_TOKEN_RESPONSE)):
        response = client.get("/micropub?q=media-endpoint", headers={"Authorization": "Bearer fake_token"})
        actual = MicropubConfigResponse.model_validate(response.json())
        assert actual == FAKE_MEDIA_RESPONSE
