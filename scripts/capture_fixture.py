#!/usr/bin/env python3
"""Capture a Google Play details page as a sanitised test fixture.

Fetches the public store page and saves it verbatim, except for one
sanitisation pass that redacts Google's public frontend API keys
(``AIzaSy*``). Those keys aren't secrets — they're embedded in every
google.com page and restricted by HTTP referrer — but pinning them
into the repository is gratuitous, so we replace them with a clearly
marked placeholder.

The rest of the HTML is kept intact because our parser uses both the
``AF_initDataCallback`` JSON blocks and the rendered "About this app"
HTML (label-value pairs like ``Verze 1.0.1``, ``Vyžaduje Android …``).
Stripping aggressively breaks fixture-driven tests for those fields.

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
    "ua": "uk",
    "ru": "ru",
    "br": "pt",
    "pt": "pt",
    "jp": "ja",
    "kr": "ko",
    "cn": "zh",
    "tw": "zh",
}

API_KEY_RE = re.compile(r"AIzaSy[A-Za-z0-9_-]{33}")


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


def sanitise(html: str) -> str:
    return API_KEY_RE.sub("<REDACTED-API-KEY>", html)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1

    app_id = sys.argv[1]
    country = sys.argv[2] if len(sys.argv) > 2 else "us"

    print(f"Fetching {app_id} from {country}...")
    html = fetch_page(app_id, country)
    print(f"  raw HTML:    {len(html):,} bytes")

    sanitised = sanitise(html)
    redacted = len(API_KEY_RE.findall(html))
    print(f"  sanitised:   {len(sanitised):,} bytes ({redacted} API keys redacted)")

    safe_app_id = app_id.replace(".", "_")
    out = FIXTURES_DIR / f"play_{safe_app_id}_{country}.html"
    out.write_text(sanitised)
    print(f"  wrote:       {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
