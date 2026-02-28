from datetime import datetime
from zoneinfo import ZoneInfo

import mf2py

def test_is_url_equal():
    from utils import is_url_equal

    assert is_url_equal("https://example.com/path", "https://example.com/path/")
    assert is_url_equal("https://example.com/path#fragment", "https://example.com/path")
    assert not is_url_equal("https://example.com/path1", "https://example.com/path2")
    assert not is_url_equal("http://example.com/path", "https://example.com/path")

def test_get_datetime():
    from utils import get_datetime


    with open("tests/test_article.html") as f:
        mf2_parser = mf2py.parse(doc=f)

    # Loop over nested dictionary items and look for dt-published
    dt = get_datetime(mf2_parser)
    assert dt == datetime(2026, 2, 26, 20, 53, 35, tzinfo=ZoneInfo("America/Chicago"))


def test_is_note():
    from utils import is_note

    with open("tests/test_article.html") as f:
        mf2_parser = mf2py.parse(doc=f)
    assert not is_note(mf2_parser)

    with open("tests/test_note.html") as f:
        mf2_parser = mf2py.parse(doc=f)
    assert is_note(mf2_parser)