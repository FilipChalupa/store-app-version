#!/usr/bin/env python3
"""Capture a Google Play details page as a trimmed test fixture.

Fetches the public store page and writes only the parts our parser
actually reads: the ``<meta og:title>`` and ``<meta og:image>`` tags
and every ``AF_initDataCallback({...});`` block. Everything else
(Google internals, telemetry, JS bundles, frontend API keys) is
dropped, both to keep the fixture small (~100 kB instead of ~1 MB)
and to avoid baking opaque Google internals into the repository.

Usage:
    python scripts/capture_fixture.py <package_name> [country]

Examples:
    python scripts/capture_fixture.py com.kilomayo.tv.application cz
    python scripts/capture_fixture.py com.google.android.youtube us

Writes to ``tests/fixtures/play_<package>_<country>.html``.
"""
from __future__ import annotations

import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

COUNTRY_TO_LANG = {
    "us": "en", "gb": "en", "ca": "en", "au": "en", "ie": "en", "nz": "en",
    "in": "en", "sg": "en", "za": "en",
    "cz": "cs", "sk": "sk",
    "de": "de", "at": "de", "ch": "de",
    "fr": "fr", "be": "fr", "lu": "fr",
    "es": "es", "mx": "es", "ar": "es", "co": "es", "cl": "es",
    "it": "it", "nl": "nl", "pl": "pl", "ua": "uk", "ru": "ru",
    "br": "pt", "pt": "pt",
    "jp": "ja", "kr": "ko", "cn": "zh", "tw": "zh",
}

OG_TAG_RE = re.compile(
    r'<meta\s+property="og:(?:title|image)"\s+content="[^"]*"\s*/?>',
    re.IGNORECASE,
)
CALLBACK_RE = re.compile(
    r"AF_initDataCallback\(\{[^{}]*?key:\s*'ds:\d+'.*?,\s*sideChannel:\s*\{\}\}\);",
    re.DOTALL,
)


def fetch_page(app_id: str, country: str) -> str:
    lang = COUNTRY_TO_LANG.get(country.lower(), "en")
    url = "https://play.google.com/store/apps/details?" + urllib.parse.urlencode(
        {"id": app_id, "hl": lang, "gl": country}
    )
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


def trim(html: str) -> str:
    og_tags = OG_TAG_RE.findall(html)
    callbacks = CALLBACK_RE.findall(html)
    head = "\n".join(og_tags)
    body = "\n".join(f"<script>{cb}</script>" for cb in callbacks)
    return f"<!doctype html>\n<html><head>\n{head}\n</head><body>\n{body}\n</body></html>\n"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1

    app_id = sys.argv[1]
    country = sys.argv[2] if len(sys.argv) > 2 else "us"

    print(f"Fetching {app_id} from {country}...")
    html = fetch_page(app_id, country)
    print(f"  raw HTML: {len(html):,} bytes")

    trimmed = trim(html)
    print(f"  trimmed:  {len(trimmed):,} bytes")

    safe_app_id = app_id.replace(".", "_")
    out = FIXTURES_DIR / f"play_{safe_app_id}_{country}.html"
    out.write_text(trimmed)
    print(f"  wrote:    {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
