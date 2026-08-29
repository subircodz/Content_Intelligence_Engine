#!/usr/bin/env python3
"""
Manual test script for browser fetcher.
Tests Power.win and other URLs with the hybrid fetcher.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from intelligence_content_engine.research.tools import HybridFetcher, BrowserFetcher, WebFetcher


def test_url(fetcher, url: str, name: str):
    """Test a single URL with a fetcher."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    try:
        content = fetcher.fetch(url)
        if content:
            print(f"Status: SUCCESS")
            print(f"Content length: {len(content)} chars")
            print(f"First 500 chars:")
            print("-" * 40)
            print(content[:500])
            print("-" * 40)
        else:
            print(f"Status: FAILED - No content returned")
    except Exception as e:
        print(f"Status: ERROR - {type(e).__name__}: {e}")


def main():
    # Default test URLs
    test_urls = [
        ("https://power.win/", "Power.win Main Site"),
        ("https://docs.power.win/documentation/games/casino", "Power.win Docs - Casino"),
        ("https://blog.power.win/blog/how-online-casinos-work-complete-guide", "Power.win Blog - Casino Guide"),
        ("https://en.wikipedia.org/wiki/Online_gambling", "Wikipedia - Online Gambling (control)"),
    ]

    # Allow URL override from command line
    if len(sys.argv) > 1:
        test_urls = [(sys.argv[1], "Custom URL")]

    print("=" * 60)
    print("BROWSER FETCHER MANUAL TEST")
    print("=" * 60)

    # Test with HybridFetcher (HTTP first, browser fallback)
    print("\n\n>>> TESTING HybridFetcher (HTTP + Browser Fallback)")
    with HybridFetcher() as fetcher:
        for url, name in test_urls:
            test_url(fetcher, url, name)

    # Also test BrowserFetcher directly
    print("\n\n>>> TESTING BrowserFetcher (Direct)")
    with BrowserFetcher(timeout=60.0) as fetcher:
        for url, name in test_urls[:3]:  # Just Power.win URLs for browser
            test_url(fetcher, url, name)

    print("\n\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()