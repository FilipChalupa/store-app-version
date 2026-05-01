"""Tests for the Google Play Store HTML parser."""

from __future__ import annotations

from pathlib import Path

import play_store
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def kilomayo_html() -> str:
    return (FIXTURES / "play_com_kilomayo_tv_application_cz.html").read_text()


@pytest.fixture(scope="module")
def youtube_html() -> str:
    return (FIXTURES / "play_com_google_android_youtube_us.html").read_text()


def test_returns_none_when_no_callback_blocks() -> None:
    """No AF_initDataCallback => parser refuses to guess."""
    assert play_store.parse_play_store_html("<html></html>", "anything") is None


def test_returns_none_when_app_id_not_on_page() -> None:
    html = (
        "AF_initDataCallback({key: 'ds:0', isError: false, hash: '1', "
        'data:[null,"other.app.id"], sideChannel: {}});'
    )
    assert play_store.parse_play_store_html(html, "missing.app") is None


def test_extract_callback_blocks(kilomayo_html: str) -> None:
    """Sanity check: regex for AF_initDataCallback finds multiple blocks."""
    blocks = play_store._extract_callback_blocks(kilomayo_html)
    assert len(blocks) >= 5
    assert all(key.startswith("ds:") for key in blocks)


def test_kilomayo_version(kilomayo_html: str) -> None:
    """Real-world fixture: should pick the app version (1.0.1), not min Android (7.0)."""
    result = play_store.parse_play_store_html(kilomayo_html, "com.kilomayo.tv.application")
    assert result is not None
    assert result["version"] == "1.0.1"


def test_kilomayo_name(kilomayo_html: str) -> None:
    """og:title with the locale suffix stripped."""
    result = play_store.parse_play_store_html(kilomayo_html, "com.kilomayo.tv.application")
    assert result is not None
    assert result["name"] == "KiloMayo TV"


def test_kilomayo_url(kilomayo_html: str) -> None:
    result = play_store.parse_play_store_html(kilomayo_html, "com.kilomayo.tv.application")
    assert result is not None
    assert result["url"] == (
        "https://play.google.com/store/apps/details?id=com.kilomayo.tv.application"
    )


def test_kilomayo_developer_from_json_ld(kilomayo_html: str) -> None:
    """Developer falls back to JSON-LD ``author.name`` when not in raw HTML."""
    result = play_store.parse_play_store_html(kilomayo_html, "com.kilomayo.tv.application")
    assert result is not None
    assert result["developer"] == "KiloMayo"


def test_youtube_basics(youtube_html: str) -> None:
    """Popular app — basic identity fields all populate."""
    result = play_store.parse_play_store_html(youtube_html, "com.google.android.youtube")
    assert result is not None
    assert result["name"] == "YouTube"
    assert result["developer"] == "Google LLC"
    assert result["url"].endswith("=com.google.android.youtube")


def test_youtube_version_is_real(youtube_html: str) -> None:
    """Should be 3-segment app version, not a 2-segment Android requirement."""
    result = play_store.parse_play_store_html(youtube_html, "com.google.android.youtube")
    assert result is not None
    assert result["version"] is not None
    assert play_store._VERSION_RE.match(result["version"])
    assert result["version"].count(".") >= 2


def test_youtube_rating_from_json_ld(youtube_html: str) -> None:
    """Rating + count come from the JSON-LD aggregateRating block."""
    result = play_store.parse_play_store_html(youtube_html, "com.google.android.youtube")
    assert result is not None
    assert isinstance(result["rating"], float)
    assert 0 < result["rating"] <= 5
    assert isinstance(result["rating_count"], int)
    assert result["rating_count"] > 1_000_000  # YouTube has hundreds of millions


def test_youtube_installs(youtube_html: str) -> None:
    result = play_store.parse_play_store_html(youtube_html, "com.google.android.youtube")
    assert result is not None
    assert result["installs"] is not None
    assert "+" in result["installs"]


def test_youtube_released(youtube_html: str) -> None:
    """`released` comes from the rendered "Updated on" label."""
    result = play_store.parse_play_store_html(youtube_html, "com.google.android.youtube")
    assert result is not None
    assert result["released"] is not None
    # Format like "Apr 25, 2026" — let date regex confirm it's date-shaped.
    assert play_store._DATE_RE.search(result["released"])


def test_kilomayo_keys(kilomayo_html: str) -> None:
    """Result schema: every documented attribute key must be present (value
    may be None for fields the heuristics couldn't extract)."""
    result = play_store.parse_play_store_html(kilomayo_html, "com.kilomayo.tv.application")
    assert result is not None
    expected_keys = {
        "version",
        "name",
        "developer",
        "release_notes",
        "min_os_version",
        "size_bytes",
        "rating",
        "rating_count",
        "url",
        "icon",
        "released",
        "installs",
    }
    assert set(result) == expected_keys


@pytest.mark.parametrize(
    ("input_url", "expected"),
    [
        # Known-good size suffix preserved? No — we always force =s512.
        (
            "https://play-lh.googleusercontent.com/abc=w512-h512-rw",
            "https://play-lh.googleusercontent.com/abc=s512",
        ),
        # No size suffix at all → append =s512.
        (
            "https://play-lh.googleusercontent.com/abc",
            "https://play-lh.googleusercontent.com/abc=s512",
        ),
        # Non-googleusercontent URL → leave as is.
        (
            "https://example.com/icon.png",
            "https://example.com/icon.png",
        ),
        # Query string present → don't touch the suffix.
        (
            "https://example.com/icon?size=large",
            "https://example.com/icon?size=large",
        ),
    ],
)
def test_normalize_googleusercontent_url(input_url: str, expected: str) -> None:
    assert play_store._normalize_googleusercontent_url(input_url) == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("KiloMayo TV", "KiloMayo TV"),
        ("YouTube - Apps on Google Play", "YouTube"),
        ("KiloMayo TV – Aplikace na Google Play", "KiloMayo TV"),
        ("App — Apps on Google Play", "App"),
        ("", None),
    ],
)
def test_extract_og_title(title: str, expected: str | None) -> None:
    html = f'<meta property="og:title" content="{title}">'
    assert play_store._extract_og_title(html) == expected


def test_extract_og_title_missing() -> None:
    assert play_store._extract_og_title("<html></html>") is None


@pytest.mark.parametrize(
    ("input_string", "should_match"),
    [
        ("1.0.1", True),
        ("1.2.3.4", True),
        ("19.42.1", True),
        ("2025.11.28", True),
        ("1.0-beta", True),
        ("1.0+build.5", True),
        ("7.0", True),
        ("1", False),  # single int is not a version
        ("hello", False),
        ("v1.0.1", False),  # the leading 'v' isn't allowed
        ("", False),
    ],
)
def test_version_regex(input_string: str, should_match: bool) -> None:
    assert bool(play_store._VERSION_RE.match(input_string)) is should_match
