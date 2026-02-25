from urllib.parse import urlsplit

def is_url_equal(url1: str, url2: str) -> bool:
    components1 = urlsplit(url1)
    components2 = urlsplit(url2)
    return (
        components1.scheme == components2.scheme
        and components1.netloc == components2.netloc
        and components1.path.rstrip("/") == components2.path.rstrip("/")
    )
