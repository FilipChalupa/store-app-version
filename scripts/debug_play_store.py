#!/usr/bin/env python3
"""Standalone debugger for the Google Play parser.

Fetches the public Play Store details page for a single app and prints
exactly what the parser sees: how many AF_initDataCallback blocks were
found, which one contains the app_id, all version-shaped string
candidates, and the final extracted metadata.

Usage:
    python scripts/debug_play_store.py <package_name> [country]

Examples:
    python scripts/debug_play_store.py com.google.android.youtube us
    python scripts/debug_play_store.py com.kilomayo.tv.application cz
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "custom_components" / "store_app_version"))

import play_store  # noqa: E402

COUNTRY_TO_LANG = {
    "us": "en",
    "gb": "en",
    "ca": "en",
    "au": "en",
    "ie": "en",
    "nz": "en",
    "in": "en",
    "sg": "en",
    "za": "en",
    "cz": "cs",
    "sk": "sk",
    "de": "de",
    "at": "de",
    "ch": "de",
    "fr": "fr",
    "be": "fr",
    "lu": "fr",
    "es": "es",
    "mx": "es",
    "ar": "es",
    "co": "es",
    "cl": "es",
    "it": "it",
    "nl": "nl",
    "pl": "pl",
    "ru": "ru",
    "ua": "uk",
    "br": "pt",
    "pt": "pt",
    "jp": "ja",
    "kr": "ko",
    "cn": "zh",
    "tw": "zh",
    "tr": "tr",
    "se": "sv",
    "no": "no",
    "dk": "da",
    "fi": "fi",
    "hu": "hu",
    "ro": "ro",
    "bg": "bg",
    "gr": "el",
    "il": "he",
    "id": "id",
    "th": "th",
    "vn": "vi",
}


def fetch_html(app_id: str, country: str) -> str:
    lang = COUNTRY_TO_LANG.get(country.lower(), "en")
    url = "https://play.google.com/store/apps/details?" + urllib.parse.urlencode(
        {"id": app_id, "hl": lang, "gl": country}
    )
    print(f"GET {url}")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": f"{lang},en;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def truncate(value, limit=80):
    text = repr(value) if not isinstance(value, str) else value
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def collect_version_candidates(metadata):
    found = []

    def walk(node, sibling_strings):
        if isinstance(node, str):
            if play_store._VERSION_RE.match(node):
                found.append((node, sibling_strings))
        elif isinstance(node, list):
            siblings = [x for x in node if isinstance(x, str)]
            for item in node:
                walk(item, siblings)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value, sibling_strings)

    walk(metadata, [])
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1

    app_id = sys.argv[1]
    country = sys.argv[2] if len(sys.argv) > 2 else "us"

    html = fetch_html(app_id, country)
    print(f"HTML length: {len(html):,} bytes\n")

    blocks = play_store._extract_callback_blocks(html)
    print(f"AF_initDataCallback blocks: {len(blocks)} -> {sorted(blocks.keys())}\n")
    if not blocks:
        print("❌ No AF_initDataCallback blocks found at all.")
        print("   Maybe Google changed the page format, or returned a captcha/redirect.")
        print("   Saving raw HTML to /tmp/play_store_debug.html for inspection.")
        Path("/tmp/play_store_debug.html").write_text(html)
        return 2

    metadata = play_store._find_metadata_block(blocks, app_id)
    if metadata is None:
        print(f"❌ No block contains the string '{app_id}'.")
        print("   Showing first 300 chars of each block:")
        for key, block in blocks.items():
            print(f"   {key}: {truncate(json.dumps(block, ensure_ascii=False), 300)}")
        return 3

    metadata_key = next(k for k, v in blocks.items() if v is metadata)
    print(f"✅ Metadata block: {metadata_key}\n")

    in_metadata = collect_version_candidates(metadata)
    print(f"Version candidates inside metadata block ({len(in_metadata)}):")
    for ver, sibs in in_metadata[:30]:
        print(f"  {ver:18s}  siblings: {[truncate(s, 30) for s in sibs[:5]]}")
    if not in_metadata:
        print("  (none)")
    print()

    in_all = []
    for key, block in blocks.items():
        for ver, sibs in collect_version_candidates(block):
            in_all.append((key, ver, sibs))
    print(f"Version candidates across ALL blocks ({len(in_all)}):")
    for key, ver, sibs in in_all[:30]:
        print(f"  [{key}] {ver:18s} siblings: {[truncate(s, 30) for s in sibs[:5]]}")
    if not in_all:
        print("  (none)")
    print()

    parsed = play_store.parse_play_store_html(html, app_id)
    print("Parsed result:")
    if parsed is None:
        print("  ❌ parse_play_store_html returned None")
    else:
        for key, value in parsed.items():
            print(f"  {key:18s} = {truncate(value, 120)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
