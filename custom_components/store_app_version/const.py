"""Constants for the Store App Version integration."""

DOMAIN = "store_app_version"

PLATFORM_APP_STORE = "app_store"
PLATFORM_PLAY_STORE = "play_store"

PLATFORM_LABELS = {
    PLATFORM_APP_STORE: "Apple App Store",
    PLATFORM_PLAY_STORE: "Google Play",
}

CONF_PLATFORM = "platform"
CONF_APP_ID = "app_id"
CONF_COUNTRY = "country"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_COUNTRY = "us"
DEFAULT_SCAN_INTERVAL = 60

MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 10080
