from urllib.parse import urlsplit

from functools import lru_cache
from typing import Dict, Tuple

from schemas import Config

def is_url_equal(url1: str, url2: str) -> bool:
    components1 = urlsplit(url1)
    components2 = urlsplit(url2)
    return (
        components1.scheme == components2.scheme
        and components1.netloc == components2.netloc
        and components1.path.rstrip("/") == components2.path.rstrip("/")
    )

@lru_cache
def load_config():
    return Config()

def mf2_to_jekyll(mf2: Dict):
    frontmatter = {}

    mf2_to_replace = {
        "name": "title",
        "category": "tags",
        "mp-syndicate-to": "syndicate_to",
        "syndicate-to": "syndicate_to",
        "value": "url"
    }

    type = mf2.get("type", [])
    if type:
        type = type[0].replace("h-", "")
    frontmatter["type"] = type

    properties = mf2.get("properties", {})
    for key, value in properties.items():
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if key in mf2_to_replace:
            key = mf2_to_replace[key]
            frontmatter[key] = value
        else:
            frontmatter[key] = value

    # Content can be a string or HTML 
    content = frontmatter.pop("content", "")
    if isinstance(content, dict) and "html" in content:
        content = content["html"]

    return frontmatter, content