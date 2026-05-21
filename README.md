# D-Link mydlink Water Leak Sensors for Home Assistant

Custom integration for polling D-Link mydlink DCH-S162 / DCH-S163 water leak status through the private mydlink cloud API.

## Latest release: v0.1.2

This release fixes support for paired DCH-S163 child leak detectors.

The DCH-S163 is not returned by mydlink as a separate top-level device. It is exposed as a child `unit` inside the parent DCH-S162 device payload. The integration now creates Home Assistant entities per child unit and uses valid Home Assistant child-device identifiers so the paired DCH-S163 can appear as its own linked device.

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

After updating to v0.1.2:

1. Restart Home Assistant fully.
2. Reloading the integration alone may not be enough for newly-created device/entity registry entries.
3. Check for a child device corresponding to the DCH-S163 paired unit.
4. Trigger the paired leak detector once to verify the inferred `uid: 1`, `type: 22` mapping.

## Changelog

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
