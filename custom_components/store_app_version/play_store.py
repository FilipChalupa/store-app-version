"""Custom Google Play Store metadata parser.

Google Play has no public API. The store details page embeds metadata
inside ``AF_initDataCallback({key: 'ds:N', ..., data: <JSON>});`` blocks.
The shape of those blocks changes between redesigns, so this parser
locates fields by content-based heuristics rather than fixed JSON paths.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterator

PLAY_STORE_URL = "https://play.google.com/store/apps/details"

_CALLBACK_RE = re.compile(
    r"AF_initDataCallback\(\{[^{}]*?key:\s*'(ds:\d+)'[^{}]*?data:\s*(.+?)\s*,\s*sideChannel:\s*\{\}\}\)",
    re.DOTALL,
)
_VERSION_RE = re.compile(r"^\d+(?:\.\d+){1,3}(?:[-+][A-Za-z0-9.]+)?$")
_DATE_RE = re.compile(
    r"(?:[A-Z][a-zěščřžýáíéúůôäöüА-Яа-я]+\s+\d{1,2},?\s+\d{4}"
    r"|\d{1,2}\.\s*[a-zěščřžýáíéúůôäöü]+\s+\d{4}"
    r"|\d{1,2}\s+[A-Za-z]+\s+\d{4})"
)
_INSTALLS_RE = re.compile(r"^[\d\s,. ]+\+\s*$")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def parse_play_store_html(html: str, app_id: str) -> dict[str, Any] | None:
    """Parse the rendered Play Store details page.

    Returns a dict of metadata, or None if the page didn't contain a
    recognisable data block for the app.
    """
    blocks = _extract_callback_blocks(html)
    metadata = _find_metadata_block(blocks, app_id)
    if metadata is None:
        return None

    return {
        "version": _find_version(metadata),
        "name": _find_title(metadata, app_id),
        "developer": _find_developer(metadata),
        "release_notes": _find_release_notes(metadata),
        "min_os_version": _find_min_android(metadata),
        "size_bytes": None,
        "rating": _find_rating(metadata),
        "rating_count": _find_rating_count(metadata),
        "url": f"https://play.google.com/store/apps/details?id={app_id}",
        "icon": _find_icon(metadata),
        "released": _find_release_date(metadata),
        "installs": _find_installs(metadata),
    }


def _extract_callback_blocks(html: str) -> dict[str, Any]:
    blocks: dict[str, Any] = {}
    for match in _CALLBACK_RE.finditer(html):
        key, raw = match.group(1), match.group(2)
        try:
            blocks[key] = json.loads(raw)
        except json.JSONDecodeError:
            continue
    return blocks


def _find_metadata_block(blocks: dict[str, Any], app_id: str) -> Any:
    """Find the data block containing the app metadata.

    The metadata block always contains the app's package name as a
    string somewhere in its tree. We pick the first block that does.
    """
    for block in blocks.values():
        if _walk_match(block, lambda s: s == app_id):
            return block
    return None


def _walk_match(obj: Any, pred: Callable[[str], bool]) -> bool:
    if isinstance(obj, str):
        return pred(obj)
    if isinstance(obj, list):
        return any(_walk_match(x, pred) for x in obj)
    if isinstance(obj, dict):
        return any(_walk_match(v, pred) for v in obj.values())
    return False


def _walk_strings(obj: Any) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_strings(item)
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_strings(value)


def _walk_arrays(obj: Any) -> Iterator[list]:
    if isinstance(obj, list):
        yield obj
        for item in obj:
            yield from _walk_arrays(item)
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_arrays(value)


def _find_version(metadata: Any) -> str | None:
    """Pick the most-likely version string out of all version-shaped strings."""
    candidates: list[tuple[str, list[str]]] = []

    def walk(node: Any, sibling_strings: list[str]) -> None:
        if isinstance(node, str):
            if _VERSION_RE.match(node):
                candidates.append((node, sibling_strings))
        elif isinstance(node, list):
            siblings = [x for x in node if isinstance(x, str)]
            for item in node:
                walk(item, siblings)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value, sibling_strings)

    walk(metadata, [])

    if not candidates:
        return None

    # Prefer candidates whose enclosing array also contains a date —
    # the "About this app" row pairs Version with Updated/Released.
    for version, siblings in candidates:
        if any(_DATE_RE.search(s) for s in siblings):
            return version

    # Otherwise return the most repeated one.
    versions = [c[0] for c in candidates]
    return max(set(versions), key=versions.count)


def _find_title(metadata: Any, app_id: str) -> str | None:
    """Title typically lives in the same small array as the package name."""
    for arr in _walk_arrays(metadata):
        if app_id not in arr:
            continue
        for value in arr:
            if (
                isinstance(value, str)
                and value != app_id
                and 0 < len(value) <= 100
                and not value.startswith(("http", "/", "data:"))
                and "googleusercontent.com" not in value
            ):
                return value
    return None


def _find_developer(metadata: Any) -> str | None:
    """Developer name lives in an array adjacent to a /store/apps/dev link."""
    for arr in _walk_arrays(metadata):
        has_dev_link = any(
            isinstance(x, str) and "store/apps/dev" in x for x in arr
        )
        if not has_dev_link:
            continue
        for value in arr:
            if (
                isinstance(value, str)
                and 0 < len(value) <= 80
                and not value.startswith(("http", "/", "data:"))
                and "store/apps/dev" not in value
            ):
                return value
    return None


def _find_icon(metadata: Any) -> str | None:
    """First googleusercontent image URL is almost always the icon."""
    for value in _walk_strings(metadata):
        if "googleusercontent.com" in value and value.startswith("https://"):
            return value
    return None


def _find_release_notes(metadata: Any) -> str | None:
    """Release notes are an HTML string with <br> tags, usually shorter than the description."""
    htmlish = [
        s for s in _walk_strings(metadata)
        if "<br" in s or "<p>" in s or "</p>" in s
    ]
    if not htmlish:
        return None
    htmlish.sort(key=len)
    return _strip_html(htmlish[0])


def _strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value)
    value = _HTML_TAG_RE.sub("", value)
    return value.strip()


def _find_min_android(metadata: Any) -> str | None:
    """e.g. '7.0 and up' (English), localized for other languages."""
    for value in _walk_strings(metadata):
        if (
            5 <= len(value) <= 60
            and any(c.isdigit() for c in value)
            and (
                "and up" in value.lower()
                or "und höher" in value.lower()
                or "ou ultérieure" in value.lower()
                or "y posteriores" in value.lower()
                or "a vyšší" in value.lower()
                or "та новіших" in value.lower()
            )
        ):
            return value
    return None


def _find_rating(metadata: Any) -> float | None:
    """Rating is a float in (0, 5]; pick the most common occurrence."""
    floats: list[float] = []

    def walk(node: Any) -> None:
        if isinstance(node, float) and 0 < node <= 5:
            floats.append(round(node, 2))
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(metadata)
    if not floats:
        return None
    return max(set(floats), key=floats.count)


def _find_rating_count(metadata: Any) -> int | None:
    """Rating count is a large integer alongside the rating float."""
    for arr in _walk_arrays(metadata):
        has_rating_float = any(
            isinstance(x, float) and 0 < x <= 5 for x in arr
        )
        if not has_rating_float:
            continue
        for value in arr:
            if isinstance(value, int) and value > 5:
                return value
    return None


def _find_release_date(metadata: Any) -> str | None:
    for value in _walk_strings(metadata):
        if _DATE_RE.fullmatch(value):
            return value
    return None


def _find_installs(metadata: Any) -> str | None:
    for value in _walk_strings(metadata):
        if _INSTALLS_RE.fullmatch(value):
            return value.strip()
    return None
