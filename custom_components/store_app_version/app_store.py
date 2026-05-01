"""Apple App Store metadata mapping.

Pure helpers for converting an iTunes Lookup API response into our
internal metadata dict. Kept separate from the coordinator so it can be
unit-tested without HTTP.
"""

from __future__ import annotations

from typing import Any

ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"


def parse_itunes_lookup_item(item: dict[str, Any]) -> dict[str, Any]:
    """Map a single iTunes Lookup ``results`` entry to our schema."""
    return {
        "version": item.get("version"),
        "name": item.get("trackName"),
        "developer": item.get("artistName"),
        "released": item.get("currentVersionReleaseDate"),
        "release_notes": item.get("releaseNotes"),
        "min_os_version": item.get("minimumOsVersion"),
        "size_bytes": _to_int(item.get("fileSizeBytes")),
        "rating": item.get("averageUserRating"),
        "rating_count": item.get("userRatingCount"),
        "url": item.get("trackViewUrl"),
        "icon": item.get("artworkUrl512") or item.get("artworkUrl100"),
    }


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
