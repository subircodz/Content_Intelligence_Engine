from power_win_content.client import ClientConfig


def test_domain_normalization():
    config = ClientConfig(name="Example", domain="https://www.Example.com/")
    assert config.domain == "example.com"
    assert config.base_url == "https://example.com"


def test_first_party_subdomains_are_supported():
    config = ClientConfig(
        name="Example",
        domain="example.com",
        first_party_domains=("docs.example.com",),
    )
    assert config.is_first_party_url("https://example.com/article")
    assert config.is_first_party_url("https://docs.example.com/guide")
    assert not config.is_first_party_url("https://notexample.com/article")
    assert not config.is_first_party_url("https://example.com.evil.test/article")


def test_sitemaps_are_client_configuration():
    config = ClientConfig(
        name="Acme",
        domain="acme.test",
        first_party_sitemaps=("https://acme.test/sitemap.xml",),
    )
    assert config.first_party_sitemaps == ("https://acme.test/sitemap.xml",)
