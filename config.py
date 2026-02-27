from functools import lru_cache
from typing import List, Tuple, Type

from pydantic import BaseModel, Field, HttpUrl
from pydantic_settings import BaseSettings, JsonConfigSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict


@lru_cache
def load_config():
    return Config()
