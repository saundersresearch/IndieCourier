def test_is_url_equal():
    from utils import is_url_equal

    assert is_url_equal("https://example.com/path", "https://example.com/path/")
    assert is_url_equal("https://example.com/path#fragment", "https://example.com/path")
    assert not is_url_equal("https://example.com/path1", "https://example.com/path2")
    assert not is_url_equal("http://example.com/path", "https://example.com/path")
