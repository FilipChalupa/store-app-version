"""Tests for the App Store iTunes Lookup mapping."""
from __future__ import annotations

import json
from pathlib import Path

from app_store import parse_itunes_lookup_item

FIXTURES = Path(__file__).parent / "fixtures"


def test_youtube_fixture_has_expected_fields() -> None:
    payload = json.loads((FIXTURES / "itunes_youtube_us.json").read_text())
    item = payload["results"][0]
    parsed = parse_itunes_lookup_item(item)

    assert "YouTube" in parsed["name"]
    assert "Google" in parsed["developer"]
    assert isinstance(parsed["version"], str)
    assert parsed["version"]
    assert parsed["url"].startswith("https://apps.apple.com/us/app/youtube")
    assert parsed["icon"].startswith("https://")
    assert isinstance(parsed["size_bytes"], int)
    assert parsed["size_bytes"] > 0


def test_size_bytes_string_is_coerced() -> None:
    parsed = parse_itunes_lookup_item({"fileSizeBytes": "12345"})
    assert parsed["size_bytes"] == 12345


def test_size_bytes_invalid_yields_none() -> None:
    parsed = parse_itunes_lookup_item({"fileSizeBytes": "not-a-number"})
    assert parsed["size_bytes"] is None


def test_missing_fields_become_none() -> None:
    parsed = parse_itunes_lookup_item({})
    assert parsed["version"] is None
    assert parsed["name"] is None
    assert parsed["icon"] is None


def test_icon_prefers_512_over_100() -> None:
    parsed = parse_itunes_lookup_item({
        "artworkUrl100": "https://example/100.png",
        "artworkUrl512": "https://example/512.png",
    })
    assert parsed["icon"] == "https://example/512.png"


def test_icon_falls_back_to_100() -> None:
    parsed = parse_itunes_lookup_item({"artworkUrl100": "https://example/100.png"})
    assert parsed["icon"] == "https://example/100.png"
