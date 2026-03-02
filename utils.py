from copy import deepcopy
from urllib.parse import urlsplit

import httpx
from datetime import datetime
import mf2py 
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

def replace_keys(obj, key_map: Dict[str, str]):
    # Recursively replace keys in a nested dictionary or list
    if isinstance(obj, dict):
        new_dict = {}
        for key, value in obj.items():
            new_key = key_map.get(key, key)
            new_dict[new_key] = replace_keys(value, key_map)
        return new_dict

    elif isinstance(obj, list):
        return [replace_keys(item, key_map) for item in obj]

    else:
        return obj

def mf2_to_jekyll(mf2: Dict, mf2_to_replace: Dict):
    frontmatter = {}
    keep_as_list = ("tags", "syndicate_to")

    type = mf2.get("type", [])
    if type:
        type = type[0].replace("h-", "")
    frontmatter["type"] = type

    properties = mf2.get("properties", {})
    properties = replace_keys(properties, mf2_to_replace)

    for k, v in properties.items():
        if k.endswith("[]"):
            k = k[:-2]
        if k not in keep_as_list and isinstance(v, list) and len(v) == 1:
            frontmatter[k] = v[0]
        else:
            frontmatter[k] = v

    # Content can be a string or HTML 
    content = frontmatter.pop("content", "")
    if isinstance(content, dict) and "html" in content:
        content = content["html"]

    return frontmatter, content

def find_first_key(data, target_key):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key:
                return value
            result = find_first_key(value, target_key)
            if result is not None:
                return result

    elif isinstance(data, list):
        for item in data:
            result = find_first_key(item, target_key)
            if result is not None:
                return result

    return None

def get_datetime(mf2_parser) -> datetime | None:
    # Loop over nested dictionary items and look for dt-published
    dt_published = find_first_key(mf2_parser, "published")
    if isinstance(dt_published, list) and len(dt_published) == 1:
        dt_published = dt_published[0]
    if dt_published:
        return datetime.fromisoformat(dt_published)
    return None

def is_note(mf2_parser) -> bool:
    name = find_first_key(mf2_parser, "name")
    if name:
        return False
    return True


def apply_patch(data, replace=None, add=None, delete=None):
    result = deepcopy(data)
    replace = replace or {}
    add = add or {}

    # Delete can be either a list of keys or a dict with values to remove
    if isinstance(delete, list):
        for k in delete:
            result.pop(k, None)
        delete_dict = {}
    elif isinstance(delete, dict):
        delete_dict = delete
    else:
        delete_dict = {}

    for k, v in replace.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = apply_patch(result[k], replace=v, add=None, delete=None)
        else:
            result[k] = deepcopy(v)

    for k, v in add.items():
        if isinstance(result.get(k), list) and isinstance(v, list):
            for item in v:
                if item not in result[k]:
                    result[k].append(item)
        else:
            result[k] = deepcopy(v)

    for k, vals in delete_dict.items():
        if k not in result:
            continue

        target = result[k]
        if isinstance(target, list) and isinstance(vals, list):
            result[k] = [item for item in target if item not in vals]
            if not result[k]:
                result.pop(k, None)
        elif isinstance(target, dict) and isinstance(vals, list):
            for nested in vals:
                target.pop(nested, None)
            if not target:
                result.pop(k, None)
        else:
            result.pop(k, None)

    return result