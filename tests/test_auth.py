from unittest.mock import AsyncMock, patch

from tests.conftest import FAKE_TOKEN_RESPONSE

def test_missing_token(client):
    with patch("auth.introspect_token", new=AsyncMock(return_value=FAKE_TOKEN_RESPONSE)):
        response = client.get(
            "/micropub?q=config",
        )
    assert response.status_code == 401


def test_invalid_token(client):
    with patch("auth.introspect_token", new=AsyncMock(return_value=None)):
        response = client.get("/micropub?q=config", headers={"Authorization": "Bearer fake_token"})
    assert response.status_code == 403
