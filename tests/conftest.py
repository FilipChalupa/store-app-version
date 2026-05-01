"""Pytest configuration. Adds the integration package to sys.path so tests
can import its pure-Python modules without a Home Assistant install.
"""

from __future__ import annotations

import sys
from pathlib import Path

_INTEGRATION_ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "store_app_version"
sys.path.insert(0, str(_INTEGRATION_ROOT))
