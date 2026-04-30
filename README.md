# Store App Version

A [Home Assistant](https://www.home-assistant.io/) custom integration that creates sensors tracking the published version of apps in the **Apple App Store** and **Google Play**. Distributed via [HACS](https://hacs.xyz/).

Each sensor exposes the current store version as its state and rich metadata (release notes, release date, rating, icon URL, etc.) as attributes. Useful for dashboards, "new version available" notifications, or comparing the store version against a version reported by your own infrastructure.

## Features

- One sensor per app per platform — add as many as you like
- Apple App Store via the official iTunes Lookup API (no API key)
- Google Play via a built-in HTML parser — no third-party libraries
- UI config flow — no YAML required
- Configurable country/region (default `us`)
- Configurable update interval (default 60 minutes, range 5 min – 1 week)
- App icon shown inline in Home Assistant UI (`entity_picture`)
- Last known version restored across Home Assistant restarts
- Built-in diagnostics download for support
- Translations: English, Czech, German, Spanish, French, Ukrainian

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → menu (⋮) → **Custom repositories**.
2. Add this repository URL, category **Integration**, and confirm.
3. Search for **Store App Version** and install.
4. Restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration** and pick *Store App Version*.

### Manual

1. Copy the [`custom_components/store_app_version`](custom_components/store_app_version) folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & Services**.

## Configuration

Each config entry tracks **one app on one platform in one country**. To track the same app on iOS and Android, add it twice — once per platform.

| Field | Description |
| --- | --- |
| **Store** | Apple App Store or Google Play |
| **App identifier** | See below |
| **Country code** | Two-letter ISO code (e.g. `us`, `cz`, `gb`). Default `us`. |
| **Update interval** | Minutes between refreshes. Default 60. |

Country and update interval can be changed later via the integration's **Configure** button (options flow).

### App identifier

| Store | Format | Example | Where to find it |
| --- | --- | --- | --- |
| Apple App Store | numeric track ID **or** bundle ID | `544007664` or `com.google.ios.youtube` | URL of the App Store listing — `apps.apple.com/us/app/youtube/id544007664` → `544007664` |
| Google Play | package name | `com.google.android.youtube` | URL of the Play Store listing — `play.google.com/store/apps/details?id=com.google.android.youtube` → `com.google.android.youtube` |

## Sensor

A device named e.g. *YouTube (App Store)* with a single sensor `sensor.<app>_version`.

- **State**: current version string (e.g. `19.42.1`). Persists across Home Assistant restarts (last known value is restored before the first refresh completes).
- **Entity picture**: the app icon, shown inline next to the sensor in the Home Assistant UI.
- **Attributes**:
  - `app_id`, `platform`, `country`
  - `name`, `developer`
  - `released` — release date (ISO 8601 for App Store, locale-formatted string for Google Play)
  - `release_notes` — what's new in this version
  - `min_os_version`
  - `size_bytes` (App Store only)
  - `rating`, `rating_count`
  - `url` — link to the store listing
  - `icon` — URL of the app icon
  - `installs` (Google Play only — e.g. `"1,000,000+"`)

Some Google Play attributes are extracted by content heuristics from the rendered store page; if Google changes the page layout some attributes may temporarily be `null` while the version is still detected reliably.

## Examples

### Notify when the version changes

```yaml
automation:
  - alias: "App version bump notification"
    trigger:
      - platform: state
        entity_id: sensor.youtube_version
    action:
      - service: notify.mobile_app_phone
        data:
          title: "{{ state_attr('sensor.youtube_version', 'name') }} updated"
          message: >
            New version {{ states('sensor.youtube_version') }}.
            {{ state_attr('sensor.youtube_version', 'release_notes') }}
```

### Compare store version against your own backend

```yaml
template:
  - binary_sensor:
      - name: "MyApp iOS update available"
        state: >
          {{ states('sensor.myapp_ios_version')
             != states('sensor.myapp_backend_reported_ios_version') }}
```

### Markdown card with icon and notes

```yaml
type: markdown
content: |
  ![]({{ state_attr('sensor.youtube_version', 'icon') }})

  **{{ state_attr('sensor.youtube_version', 'name') }}** —
  v{{ states('sensor.youtube_version') }}

  {{ state_attr('sensor.youtube_version', 'release_notes') }}
```

## Limitations and notes

- **Google Play has no official public API.** The integration scrapes the public store details page directly. If Google changes the page structure, fetches may temporarily return wrong data or fail until the parser is updated.
- **Google Play app icon is sometimes broken.** The icon URL extracted from the store page sometimes returns HTTP 400 when fetched directly; for those apps the entity picture / `icon` attribute will fail to load. App Store icons are unaffected.
- **"Varies with device" version.** Some apps publish multiple variants per device (Android App Bundle / dynamic delivery). For those apps Google Play does not expose a single version string and the sensor will reflect what the store shows.
- **iTunes Lookup is rate-limited.** With the default 60-minute interval and a handful of apps you will not run into limits, but avoid setting an aggressive scan interval across many apps.
- The integration polls in the cloud — it cannot detect a new version any faster than the configured update interval.
- Country code matters: an app may have different versions in different App Store/Play Store regions. The Play Store query language is auto-derived from the country (e.g. `cz` → `cs`, `de` → `de`, `us` → `en`); apps published only in a local language may need the matching country to expose full metadata.

## Troubleshooting

- **"App not found"** — verify the identifier and country. Some apps are not published in all regions.
- **Stale version** — Home Assistant logs (Settings → System → Logs) will show fetch errors for `store_app_version`. Increase log level with:
  ```yaml
  logger:
    default: warning
    logs:
      custom_components.store_app_version: debug
  ```
- **Diagnostics dump** — for any wrong / missing attribute, open *Settings → Devices & Services*, find the integration entry, click ⋮ → *Download diagnostics*. The JSON contains the config entry and what the coordinator last fetched (including the last exception, if any) — attach it to a bug report.

## Development

The integration is a standard Home Assistant custom component. Layout:

```
custom_components/store_app_version/
├── __init__.py        # entry setup + reload listener
├── manifest.json      # HA manifest
├── const.py           # domain & defaults
├── coordinator.py     # DataUpdateCoordinator (drives both fetchers)
├── app_store.py       # iTunes Lookup mapping (pure, testable)
├── play_store.py      # Google Play HTML parser (pure, testable)
├── config_flow.py     # UI config + options flow
├── sensor.py          # sensor entity (RestoreSensor + entity_picture)
├── diagnostics.py     # "Download diagnostics" payload
├── strings.json       # source strings (English)
└── translations/      # en, cs, de, es, fr, uk
```

### Tests

```bash
pip install -r requirements_test.txt
pytest
```

Tests run offline against fixtures in `tests/fixtures/`. CI runs them on every push (`.github/workflows/test.yml`).

### Helper scripts

- `scripts/debug_play_store.py <package> [country]` — fetch a Play Store page and print exactly what the parser sees (callback blocks, version candidates, final extracted dict). Use this when an attribute is wrong for a specific app.
- `scripts/capture_fixture.py <package> [country]` — fetch a Play Store page, strip everything except `<meta og:*>` and `AF_initDataCallback` blocks, and save it to `tests/fixtures/`. Use this to add a new test fixture.

## License

MIT.
