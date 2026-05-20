from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import status_value
from .const import DOMAIN


@dataclass(frozen=True)
class MydlinkBinaryDescription:
    key: str
    name: str
    device_class: BinarySensorDeviceClass | None
    value_fn: Callable[[dict[str, Any]], bool | None]


def _status_bool(uid: int, status_type: int) -> Callable[[dict[str, Any]], bool | None]:
    def _value(info: dict[str, Any]) -> bool | None:
        value = status_value(info, uid, status_type)
        if value is None:
            return None
        return value == 1

    return _value


DESCRIPTIONS = [
    MydlinkBinaryDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda info: bool(info.get("online")) if info.get("online") is not None else None,
    ),
    MydlinkBinaryDescription(
        key="water_leak_uid0_type23",
        name="Water Leak",
        device_class=BinarySensorDeviceClass.MOISTURE,
        value_fn=_status_bool(uid=0, status_type=23),
    ),
    MydlinkBinaryDescription(
        key="alarm_uid0_type15",
        name="Alarm Status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_status_bool(uid=0, status_type=15),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[MydlinkBinarySensor] = []

    for info in coordinator.data.get("devices", []):
        for description in DESCRIPTIONS:
            entities.append(MydlinkBinarySensor(coordinator, info["mydlink_id"], description))

    async_add_entities(entities)


class MydlinkBinarySensor(CoordinatorEntity[DataUpdateCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        mydlink_id: str,
        description: MydlinkBinaryDescription,
    ) -> None:
        super().__init__(coordinator)
        self._mydlink_id = mydlink_id
        self._description = description
        self._attr_unique_id = f"{DOMAIN}_{mydlink_id}_{description.key}"
        self._attr_name = description.name
        self._attr_device_class = description.device_class

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

    @property
    def is_on(self) -> bool | None:
        info = self._info
        if info is None:
            return None
        return self._description.value_fn(info)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info or {}
        return {
            "mydlink_id": self._mydlink_id,
            "private_ip": info.get("private_ip"),
            "firmware": info.get("fw_ver"),
            "raw_change_cache": info.get("change_cache"),
        }
