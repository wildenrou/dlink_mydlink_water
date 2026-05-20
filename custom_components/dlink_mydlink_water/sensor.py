from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SensorEntity] = []

    for info in coordinator.data.get("devices", []):
        entities.append(MydlinkLastUpdateSensor(coordinator, info["mydlink_id"]))
        entities.append(MydlinkFirmwareSensor(coordinator, info["mydlink_id"]))

    async_add_entities(entities)


class _BaseMydlinkSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DataUpdateCoordinator, mydlink_id: str) -> None:
        super().__init__(coordinator)
        self._mydlink_id = mydlink_id

    @property
    def _info(self) -> dict[str, Any] | None:
        for info in self.coordinator.data.get("devices", []):
            if str(info.get("mydlink_id")) == self._mydlink_id:
                return info
        return None

    @property
    def device_info(self):
        info = self._info or {}
        return {
            "identifiers": {(DOMAIN, self._mydlink_id)},
            "name": info.get("device_name", f"mydlink {self._mydlink_id}"),
            "manufacturer": "D-Link",
            "model": info.get("device_model", "DCH-S162"),
            "sw_version": info.get("fw_ver"),
        }

    @property
    def available(self) -> bool:
        return super().available and self._info is not None


class MydlinkLastUpdateSensor(_BaseMydlinkSensor):
    _attr_name = "Last Update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: DataUpdateCoordinator, mydlink_id: str) -> None:
        super().__init__(coordinator, mydlink_id)
        self._attr_unique_id = f"{DOMAIN}_{mydlink_id}_last_update"

    @property
    def native_value(self) -> datetime | None:
        info = self._info
        if not info:
            return None
        try:
            return datetime.fromtimestamp(int(info.get("lat")), tz=UTC)
        except (TypeError, ValueError, OSError):
            return None


class MydlinkFirmwareSensor(_BaseMydlinkSensor):
    _attr_name = "Firmware"

    def __init__(self, coordinator: DataUpdateCoordinator, mydlink_id: str) -> None:
        super().__init__(coordinator, mydlink_id)
        self._attr_unique_id = f"{DOMAIN}_{mydlink_id}_firmware"

    @property
    def native_value(self) -> str | None:
        info = self._info
        if not info:
            return None
        return info.get("fw_ver")
