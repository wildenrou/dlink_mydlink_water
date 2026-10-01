# D-Link mydlink Water Leak Sensors for Home Assistant

Custom integration for polling D-Link mydlink DCH-S162 / DCH-S163 water leak status through the private mydlink cloud API.

## Latest release: v0.1.3

This release fixes duplicate child devices left behind by the device identifier change in v0.1.1 and adds local D-Link branding for Home Assistant 2026.3 and newer.

Legacy child devices are migrated automatically before entities load. If a current-format device already exists, the integration keeps it, moves any remaining entities to it, and removes the obsolete device. Entity IDs and unique IDs remain unchanged. New installations keep the current identifier format.

## How it works

This integration was built from the reverse-engineered flow validated during testing:

1. Authenticate through `GET /oauth/authorize2`.
2. Use the returned `api_site` and `access_token`.
3. Poll `GET /me/device/list?access_token=...`.
4. Poll `POST /me/device/info?access_token=...`.
5. Parse `change_cache.status_change`.

## Device/unit model

The paired DCH-S163 remote leak detector is **not** returned as a separate mydlink device. It is returned as a child `unit` inside the parent DCH-S162 payload.

Example:

```json
"units": [
  {"uid": 0, "model": "DCH-S162", "status": [15, 17, 23]},
  {"uid": 1, "model": "DCH-S163", "status": [15, 16, 22]}
]
```

The integration therefore creates entities per unit, not only per top-level device.

## Known / inferred status mapping

Validated by live testing:

- `uid: 0`, `model: DCH-S162`, `type: 23`, `value: 1` = water leak triggered on the DCH-S162 base unit.
- `uid: 0`, `model: DCH-S162`, `type: 15`, `value: 1` = alarm/problem status triggered on the DCH-S162 base unit.
- `value: 0` = normal/dry.

Inferred for the paired remote unit based on its advertised status capabilities:

- `uid: 1`, `model: DCH-S163`, `type: 22`, `value: 1` = likely water leak triggered on the paired DCH-S163 unit.
- `uid: 1`, `model: DCH-S163`, `type: 15`, `value: 1` = likely alarm/problem status triggered on the paired DCH-S163 unit.

The DCH-S163 leak mapping should still be confirmed by triggering the remote detector once after installation.

## Entities created

For each parent DCH-S162 device:

- parent online entity
- parent firmware sensor
- parent last update sensor

For each unit inside the parent device:

- DCH-S162 base unit water leak binary sensor
- DCH-S162 base unit alarm/problem binary sensor
- DCH-S163 paired unit water leak binary sensor
- DCH-S163 paired unit alarm/problem binary sensor

The paired unit should appear as a separate Home Assistant device linked via `via_device` to the parent DCH-S162.

## Installation

### Manual installation

1. Copy `custom_components/dlink_mydlink_water` to Home Assistant:

   `/config/custom_components/dlink_mydlink_water`

2. Restart Home Assistant.

3. Go to **Settings → Devices & services → Add integration**.

4. Search for **D-Link mydlink Water Leak Sensors**.

5. Enter your mydlink email/password.

Recommended polling interval: `30` seconds.

### HACS custom repository

Add this repository as a HACS custom repository:

```text
https://github.com/wildenrou/dlink_mydlink_water
```

Category:

```text
Integration
```

Then install/update through HACS and restart Home Assistant.

## Updating from an earlier version

After updating to v0.1.3:

1. Restart Home Assistant fully to load the updated integration and D-Link brand images.
2. Legacy child devices are migrated automatically after the first successful cloud refresh; no removal or reinstallation of the integration is needed.
3. Existing entity IDs are preserved. If an obsolete duplicate was referenced directly by a device-based automation, select the remaining active device in that automation.
4. Refresh the browser if it still displays a cached placeholder logo. Local branding requires Home Assistant 2026.3 or newer.

The migration leaves shared or ambiguous legacy devices untouched and logs a warning for shared devices, so these may require manual review.

## Changelog

### v0.1.3

- Migrate legacy three-part child identifiers to the current two-part format.
- Remove obsolete duplicate child devices while preserving entity IDs and recovering missing user settings.
- Leave parent devices, new installations, and unrelated registry entries unchanged.
- Move D-Link icons and logos into the supported `brand/` directory for Home Assistant 2026.3 and newer.
- Add 14 registry regression tests, verified with Home Assistant 2026.5.0.

### v0.1.2

- Fixed DCH-S163 paired child-device support.
- The integration now creates binary sensors for each `units[]` entry returned by `/me/device/info`.
- Fixed invalid Home Assistant child-device identifier format for paired units.
- Added `via_device` linkage from DCH-S163 child devices to the parent DCH-S162.
- Kept DCH-S162 base leak mapping as `uid: 0`, `type: 23`.
- Added inferred DCH-S163 leak mapping as `uid: 1`, `type: 22`.

### v0.1.1

- Added preliminary paired DCH-S163 unit sensor creation.
- Added debug logging for detected mydlink units.

### v0.1.0

- Initial cloud-polling integration.
- Added login flow.
- Added DCH-S162 device discovery.
- Added DCH-S162 water leak, alarm status, online, last update, and firmware entities.

## Security warning

If you pasted your mydlink password or tokens during reverse-engineering/testing, change your mydlink password before using this integration.

## Limitations

- Cloud polling only.
- Tested against one DCH-S162 with one paired DCH-S163.
- The DCH-S163 mapping is inferred from the paired unit's `status` list and should be confirmed by triggering the remote detector.
- No siren/strobe control yet.
