"""Custom Google Play Store metadata parser.

Google Play has no public API. The store details page embeds metadata
inside ``AF_initDataCallback({key: 'ds:N', ..., data: <JSON>});`` blocks.
The shape of those blocks changes between redesigns, so this parser
locates fields by content-based heuristics rather than fixed JSON paths.
"""
from __future__ import annotations

import html as _html
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
_OG_TITLE_RE = re.compile(
    r'<meta\s+property="og:title"\s+content="([^"]*)"', re.IGNORECASE
)
_OG_IMAGE_RE = re.compile(
    r'<meta\s+property="og:image"\s+content="([^"]*)"', re.IGNORECASE
)
_DEV_LINK_RE = re.compile(
    r'href="(?:/store/apps/dev(?:eloper)?\?id=)[^"]+"[^>]*>([^<]+)</a>',
    re.IGNORECASE,
)
_TITLE_SUFFIX_SEPARATORS = (" – ", " - ", " — ")
_MIN_OS_LABELS = (
    "Vyžaduje Android",
    "Requires Android",
    "Erfordert Android",
    "Requiert Android",
    "Requiere Android",
    "Richiede Android",
    "Vereist Android",
    "Wymaga Androida",
    "Requer o Android",
    "Требуется Android",
    "Потребує Android",
)
_RELEASED_LABELS = (
    "Vydáno dne", "Released on",
    "Veröffentlicht am",
    "Date de publication",
    "Fecha de lanzamiento",
    "Data di rilascio",
    "Data wydania",
    "Дата выпуска",
    "Дата випуску",
)
_UPDATED_LABELS = (
    "Aktualizováno dne", "Updated on",
    "Aktualisiert am",
    "Date de mise à jour",
    "Fecha de actualización",
    "Data aggiornamento",
    "Data aktualizacji",
    "Дата обновления",
    "Оновлено",
)


def parse_play_store_html(html: str, app_id: str) -> dict[str, Any] | None:
    """Parse the rendered Play Store details page.

    Returns a dict of metadata, or None if the page didn't contain a
    recognisable data block for the app.
    """
    blocks = _extract_callback_blocks(html)
    if not blocks:
        return None

    # The metadata for one app is split across multiple AF_initDataCallback
    # blocks (e.g. version in ds:5, title in another ds:N, app_id maybe just
    # in a tracking block). Treat the union of all blocks as a single search
    # space and rely on content-based heuristics.
    all_data: list[Any] = list(blocks.values())

    if not _walk_match(all_data, lambda s: s == app_id):
        return None

    return {
        "version": _find_version(all_data),
        "name": _extract_og_title(html) or _find_title(all_data, app_id),
        "developer": _find_developer(all_data) or _extract_developer_html(html),
        "release_notes": _find_release_notes(all_data),
        "min_os_version": (
            _find_min_android(all_data) or _extract_label_value(html, _MIN_OS_LABELS)
        ),
        "size_bytes": None,
        "rating": _find_rating(all_data),
        "rating_count": _find_rating_count(all_data),
        "url": f"https://play.google.com/store/apps/details?id={app_id}",
        "icon": _extract_og_image(html) or _find_icon(all_data),
        "released": (
            _extract_label_value(html, _RELEASED_LABELS)
            or _extract_label_value(html, _UPDATED_LABELS)
            or _find_release_date(all_data)
        ),
        "installs": _find_installs(all_data),
    }


def _extract_og_title(html: str) -> str | None:
    match = _OG_TITLE_RE.search(html)
    if not match:
        return None
    title = _html.unescape(match.group(1)).strip()
    if not title:
        return None
    for separator in _TITLE_SUFFIX_SEPARATORS:
        if separator in title:
            title = title.split(separator)[0].strip()
            break
    return title or None


def _extract_og_image(html: str) -> str | None:
    match = _OG_IMAGE_RE.search(html)
    if not match:
        return None
    url = _html.unescape(match.group(1)).strip()
    return _normalize_googleusercontent_url(url) if url else None


def _normalize_googleusercontent_url(url: str) -> str:
    """Force a known-good size suffix on play-lh.googleusercontent.com URLs.

    KNOWN BROKEN: the URLs returned here (with or without size suffix)
    sometimes still 400 when fetched directly. Investigation showed that
    neither ``<meta og:image>`` nor the first googleusercontent URL inside
    the AF_initDataCallback data is reliably the app icon — Google appears
    to gate some of these URLs by referrer or session cookie. Leaving the
    extractor in place because for some apps it does work; needs a deeper
    rewrite (probably parsing the rendered <img> tag from the visible
    HTML) to be fully reliable. See README "Limitations".
    """
    if "googleusercontent.com" not in url:
        return url
    if "=" in url and "?" not in url:
        url = url.split("=", 1)[0]
    return f"{url}=s512"


def _extract_developer_html(html: str) -> str | None:
    match = _DEV_LINK_RE.search(html)
    if not match:
        return None
    return _html.unescape(match.group(1)).strip() or None


def _extract_label_value(html: str, labels: tuple[str, ...]) -> str | None:
    """Find the value rendered next to a label in the "About this app" panel.

    Play Store renders rows like::

        <div ...>Verze</div><div ...>1.0.1</div>

    The class names are obfuscated and change, but the structural pair
    (label closing tag, then one or more wrapper tags, then a value) is
    consistent.
    """
    for label in labels:
        pattern = re.compile(
            r">"
            + re.escape(label)
            + r"</[^>]+>(?:\s*<[^>]+>)+([^<]{1,200})<",
            re.IGNORECASE,
        )
        match = pattern.search(html)
        if match:
            value = _html.unescape(match.group(1)).strip()
            if value:
                return value
    return None


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

    def walk(node: Any, ancestor_strings: list[str]) -> None:
        if isinstance(node, str):
            if _VERSION_RE.match(node):
                candidates.append((node, ancestor_strings))
        elif isinstance(node, list):
            new_ancestors = (
                ancestor_strings + [x for x in node if isinstance(x, str)]
            )[-30:]
            for item in node:
                walk(item, new_ancestors)
        elif isinstance(node, dict):
            new_ancestors = (
                ancestor_strings
                + [v for v in node.values() if isinstance(v, str)]
            )[-30:]
            for value in node.values():
                walk(value, new_ancestors)

    walk(metadata, [])

    if not candidates:
        return None

    # Prefer candidates whose ancestor array(s) also contain a date —
    # the "About this app" row pairs Version with Updated/Released.
    for version, ancestors in candidates:
        if any(_DATE_RE.search(s) for s in ancestors):
            return version

    # Otherwise prefer the version with the most segments (app versions are
    # typically X.Y.Z while min OS / API level have fewer segments).
    unique = list({c[0] for c in candidates})
    unique.sort(key=lambda v: (-v.count("."), -len(v)))
    return unique[0]


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
            return _normalize_googleusercontent_url(value)
    return None


def _find_release_notes(metadata: Any) -> str | None:
    """Release notes are an HTML string with <br> tags, shorter than the description.

    We only return something when at least two such strings exist (so we
    can distinguish the description from release notes); otherwise the
    single match is almost always the description and would be misleading.
    """
    htmlish = [
        s for s in _walk_strings(metadata)
        if "<br" in s or "<p>" in s or "</p>" in s
    ]
    if len(htmlish) < 2:
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
        match = _DATE_RE.search(value)
        if match:
            return match.group(0)
    return None


def _find_installs(metadata: Any) -> str | None:
    for value in _walk_strings(metadata):
        if _INSTALLS_RE.fullmatch(value):
            return value.strip()
    return None
