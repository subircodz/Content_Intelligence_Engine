import pytest

from intelligence_content_engine.research.tools.url_safety import UnsafeURLError, validate_outbound_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1",
        "http://192.168.1.1",
        "http://[::1]:8080",
        "http://user:pass@example.com",
    ],
)
def test_unsafe_urls_are_rejected(url):
    with pytest.raises(UnsafeURLError):
        validate_outbound_url(url)


def test_public_https_url_is_allowed(monkeypatch):
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    assert validate_outbound_url("https://example.com/path") == "https://example.com/path"


def test_hostname_resolving_to_private_address_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    with pytest.raises(UnsafeURLError):
        validate_outbound_url("https://example.com")
