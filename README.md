# D-Link mydlink Water Leak Sensors for Home Assistant

Custom integration for polling D-Link mydlink DCH-S162 / DCH-S163 water leak status through the private mydlink cloud API.

This integration was built from the reverse-engineered flow validated during testing:

1. Authenticate through `GET /oauth/authorize2`.
2. Use the returned `api_site` and `access_token`.
3. Poll `GET /me/device/list?access_token=...`.
4. Poll `POST /me/device/info?access_token=...`.
5. Parse `change_cache.status_change`.

Known mapping from testing:

- `uid: 0`, `type: 23`, `value: 1` = water leak triggered on the DCH-S162 base unit.
- `uid: 0`, `type: 15`, `value: 1` = alarm/problem status triggered on the DCH-S162 base unit.
- `value: 0` = normal/dry.

## Entities created

For each discovered DCH-S16x device:

- `binary_sensor.<device>_water_leak`
- `binary_sensor.<device>_alarm_status`
- `binary_sensor.<device>_online`
- `sensor.<device>_last_update`
- `sensor.<device>_firmware`

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
- The paired DCH-S163 remote unit status mapping is not yet implemented because only the base unit was triggered during validation.
- No siren/strobe control yet.
