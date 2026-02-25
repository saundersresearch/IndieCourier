from functools import lru_cache
from typing import List, Tuple, Type

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
    media_endpoint: HttpUrl = Field(..., alias="media-endpoint")
    syndicate_to: List[SyndicationEndpoint] = Field(default_factory=list, alias="syndicate-to")

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


@lru_cache
def load_config():
    return Config()
