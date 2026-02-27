from urllib.parse import urljoin

from schemas import MicropubConfigResponse
from tests.conftest import FAKE_CONFIG

FAKE_CONFIG_RESPONSE = MicropubConfigResponse(
    me=FAKE_CONFIG.me,
    token_endpoint=FAKE_CONFIG.token_endpoint,
    media_endpoint=urljoin(str(FAKE_CONFIG.site_url), "/media"),
    syndicate_to=FAKE_CONFIG.syndicate_to,
)

FAKE_SYNDICATION_RESPONSE = MicropubConfigResponse(syndicate_to=FAKE_CONFIG.syndicate_to)

FAKE_MEDIA_RESPONSE = MicropubConfigResponse(media_endpoint=urljoin(str(FAKE_CONFIG.site_url), "/media"))

def test_config(client):
    response = client.get("/micropub?q=config", headers={"Authorization": "Bearer fake_token"})
    actual = MicropubConfigResponse.model_validate(response.json())
    assert actual == FAKE_CONFIG_RESPONSE


def test_syndicate_to(client):
    response = client.get("/micropub?q=syndicate-to", headers={"Authorization": "Bearer fake_token"})
    actual = MicropubConfigResponse.model_validate(response.json())
    assert actual == FAKE_SYNDICATION_RESPONSE


def test_media_endpoint(client):
    response = client.get("/micropub?q=media-endpoint", headers={"Authorization": "Bearer fake_token"})
    actual = MicropubConfigResponse.model_validate(response.json())
    assert actual == FAKE_MEDIA_RESPONSE
