from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture
def client():
    return TestClient(app)


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


def test_missing_token(client):
    with patch("app.verify_authorization_token", new=AsyncMock(return_value=FAKE_TOKEN_RESPONSE)):
        response = client.get(
            "/micropub?q=config",
        )
    assert response.status_code == 401


def test_invalid_token(client):
    with patch("app.verify_authorization_token", new=AsyncMock(return_value=False)):
        response = client.get("/micropub?q=config", headers={"Authorization": "Bearer fake_token"})
    assert response.status_code == 403
