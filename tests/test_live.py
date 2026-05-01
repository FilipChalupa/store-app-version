"""Live tests against the real App Store and Google Play.

These hit production endpoints and are skipped by default. Run them
manually with::

    pytest -m live

A scheduled GitHub Action (.github/workflows/scraper-health.yml) runs
them daily to detect when Apple or Google change their response shape
and our parsers start producing wrong results — long before users hit
it. A failure here is the early-warning bell.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

import play_store
import pytest
from app_store import parse_itunes_lookup_item

# Google's own apps are stable test targets — they're not going to be
# pulled, renamed, or republished under different identifiers.
PLAY_TEST_PACKAGE = "com.google.android.youtube"
APPLE_TEST_BUNDLE = "com.google.ios.youtube"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _fetch(url: str, accept_lang: str | None = None) -> str:
    headers: dict[str, str] = {"User-Agent": USER_AGENT}
    if accept_lang:
        headers["Accept-Language"] = accept_lang
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


@pytest.mark.live
def test_play_store_youtube_us() -> None:
    """The Play Store parser still extracts the basics from a real page."""
    url = "https://play.google.com/store/apps/details?" + urllib.parse.urlencode(
        {"id": PLAY_TEST_PACKAGE, "hl": "en", "gl": "us"}
    )
    html = _fetch(url, accept_lang="en,en;q=0.5")
    result = play_store.parse_play_store_html(html, PLAY_TEST_PACKAGE)

    assert result is not None, "Parser returned None — page format may have changed"
    assert result["version"], "No version extracted"
    assert play_store._VERSION_RE.match(result["version"]), (
        f"Extracted version {result['version']!r} does not match the version regex"
    )
    assert "." in result["version"], f"Suspicious version {result['version']!r} (only one segment)"
    assert result["name"], "No app name extracted"
    assert "YouTube" in result["name"], f"Unexpected app name {result['name']!r}"
    assert result["url"].endswith(f"id={PLAY_TEST_PACKAGE}")


@pytest.mark.live
def test_app_store_youtube_us() -> None:
    """The iTunes Lookup API still returns YouTube with the expected shape."""
    url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
        {"bundleId": APPLE_TEST_BUNDLE, "country": "us"}
    )
    payload = json.loads(_fetch(url))

    assert payload["resultCount"] >= 1, "iTunes Lookup returned no results for YouTube"
    item = parse_itunes_lookup_item(payload["results"][0])

    assert item["version"], "No version extracted"
    assert "." in item["version"]
    assert item["name"], "No app name extracted"
    assert "YouTube" in item["name"]
    assert item["icon"], "No icon URL"
    assert item["icon"].startswith("https://")
    assert isinstance(item["size_bytes"], int)
    assert item["size_bytes"] > 0
