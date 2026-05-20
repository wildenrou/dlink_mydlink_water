# D-Link mydlink Water Leak Sensors for Home Assistant

Custom integration for polling D-Link mydlink DCH-S162 / DCH-S163 water leak status through the private mydlink cloud API.

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

The DCH-S163 mapping still needs one live trigger test to fully confirm.

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

1. Copy `custom_components/dlink_mydlink_water` to Home Assistant:

   `/config/custom_components/dlink_mydlink_water`

2. Restart Home Assistant.

3. Go to **Settings → Devices & services → Add integration**.

4. Search for **D-Link mydlink Water Leak Sensors**.

5. Enter your mydlink email/password.

Recommended polling interval: `30` seconds.

## Security warning

If you pasted your mydlink password or tokens during reverse-engineering/testing, change your mydlink password before using this integration.

## Limitations

- Cloud polling only.
- Tested against one DCH-S162 with one paired DCH-S163.
- The DCH-S163 mapping is inferred from the paired unit's `status` list and should be confirmed by triggering the remote detector.
- No siren/strobe control yet.
