from typing import Dict, List, Tuple, Type
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, JsonConfigSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict

class UserOrService(BaseModel):
    name: str
    url: HttpUrl | None = None
    photo: str | None = None


class SyndicationEndpoint(BaseModel):
    uid: str
    name: str
    service: UserOrService | None = None
    user: UserOrService | None = None


class Config(BaseSettings):
    me: HttpUrl
    token_endpoint: HttpUrl = Field(..., alias="token-endpoint")
    site_url: HttpUrl = Field(..., alias="site-url")
    syndicate_to: List[SyndicationEndpoint] = Field(default_factory=list, alias="syndicate-to")
    github_repo: str 
    github_token: str
    github_user: str
    media_dir: str
    article_dir: str = "_posts"
    note_dir: str = "_notes"
    tz: ZoneInfo = ZoneInfo("UTC")

    # Load env vars from .env and syndication endpoints from syndicate-to.json
    model_config = SettingsConfigDict(
        env_file=".env",
        json_file="syndicate-to.json",
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            JsonConfigSettingsSource(settings_cls),
        )
    
class MicropubConfigResponse(BaseModel):
    me: HttpUrl | None = None
    token_endpoint: HttpUrl | None = Field(None, alias="token-endpoint")
    media_endpoint: HttpUrl | None = Field(None, alias="media-endpoint")
    syndicate_to: List[SyndicationEndpoint] | None = Field(None, alias="syndicate-to")

    model_config = {
        "populate_by_name": True,
    }


class GithubFileResponse(BaseModel):
    class ContentFile(BaseModel):
        path: str
    class Commit(BaseModel):
        sha: str

    content: ContentFile
    commit: Commit


class MicropubRequest(BaseModel):
    type: List[str]
    properties: Dict[str, List[str | Dict]]