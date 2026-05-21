from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import status_value
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class UnitStatusDescription:
    key: str
    name: str
    status_type: int
    device_class: BinarySensorDeviceClass


UNIT_MODEL_STATUS: dict[str, list[UnitStatusDescription]] = {
    # Validated by testing: uid 0 / type 23 / value 1 means base DCH-S162 leak triggered.
    "DCH-S162": [
        UnitStatusDescription(
            key="water_leak",
            name="Water Leak",
            status_type=23,
            device_class=BinarySensorDeviceClass.MOISTURE,
        ),
        UnitStatusDescription(
            key="alarm_status",
            name="Alarm Status",
            status_type=15,
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ],
    # Inferred from the DCH-S163 unit capabilities: status list is [15, 16, 22], matching
    # the DCH-S162 pattern where the highest status code is the water/leak state.
    "DCH-S163": [
        UnitStatusDescription(
            key="water_leak",
            name="Water Leak",
            status_type=22,
            device_class=BinarySensorDeviceClass.MOISTURE,
        ),
        UnitStatusDescription(
            key="alarm_status",
            name="Alarm Status",
            status_type=15,
            device_class=BinarySensorDeviceClass.PROBLEM,
        ),
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[BinarySensorEntity] = []

    for info in coordinator.data.get("devices", []):
        mydlink_id = str(info["mydlink_id"])
        entities.append(MydlinkParentOnlineSensor(coordinator, mydlink_id))

        units = info.get("units") or []
        _LOGGER.debug("Creating mydlink unit sensors for %s: %s", mydlink_id, units)
        for unit in units:
            model = str(unit.get("model", ""))
            try:
                uid = int(unit.get("uid", 0))
            except (TypeError, ValueError):
                _LOGGER.warning("Skipping mydlink unit with invalid uid: %s", unit)
                continue

            descriptions = UNIT_MODEL_STATUS.get(model, [])
            if not descriptions:
                _LOGGER.debug("No known status mapping for mydlink unit model %s: %s", model, unit)
                continue

            for description in descriptions:
                entities.append(MydlinkUnitStatusSensor(coordinator, mydlink_id, uid, description))

    async_add_entities(entities)


def _find_info(coordinator: DataUpdateCoordinator, mydlink_id: str) -> dict[str, Any] | None:
    for info in coordinator.data.get("devices", []):
        if str(info.get("mydlink_id")) == mydlink_id:
            return info
    return None


def _find_unit(info: dict[str, Any], uid: int) -> dict[str, Any] | None:
    for unit in info.get("units") or []:
        try:
            if int(unit.get("uid")) == uid:
                return unit
        except (TypeError, ValueError):
            continue
    return None


def _unit_name(info: dict[str, Any], uid: int) -> str:
    meta_info = info.get("meta_info")
    if isinstance(meta_info, str) and meta_info:
        try:
            parsed = json.loads(meta_info)
            for module in parsed.get("Modules") or []:
                try:
                    if int(module.get("uid")) == uid and module.get("name"):
                        return str(module["name"])
                except (TypeError, ValueError):
                    continue
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    unit = _find_unit(info, uid) or {}
    if unit.get("model"):
        return f"{info.get('device_name', 'mydlink')} {unit['model']} {uid}"
    return f"{info.get('device_name', 'mydlink')} Unit {uid}"


class MydlinkParentOnlineSensor(CoordinatorEntity[DataUpdateCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: DataUpdateCoordinator, mydlink_id: str) -> None:
        super().__init__(coordinator)
        self._mydlink_id = mydlink_id
        self._attr_unique_id = f"{DOMAIN}_{mydlink_id}_online"

    @property
    def _info(self) -> dict[str, Any] | None:
        return _find_info(self.coordinator, self._mydlink_id)

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
        if info is None or info.get("online") is None:
            return None
        return bool(info.get("online"))


class MydlinkUnitStatusSensor(CoordinatorEntity[DataUpdateCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        mydlink_id: str,
        uid: int,
        description: UnitStatusDescription,
    ) -> None:
        super().__init__(coordinator)
        self._mydlink_id = mydlink_id
        self._uid = uid
        self._description = description
        self._attr_unique_id = f"{DOMAIN}_{mydlink_id}_uid{uid}_{description.key}_type{description.status_type}"
        self._attr_name = description.name
        self._attr_device_class = description.device_class

    @property
    def _info(self) -> dict[str, Any] | None:
        return _find_info(self.coordinator, self._mydlink_id)

    @property
    def _unit(self) -> dict[str, Any] | None:
        info = self._info
        if info is None:
            return None
        return _find_unit(info, self._uid)

    @property
    def device_info(self):
        info = self._info or {}
        unit = self._unit or {}
        unit_identifier = f"{self._mydlink_id}_uid{self._uid}"
        return {
            "identifiers": {(DOMAIN, unit_identifier)},
            "name": _unit_name(info, self._uid) if info else f"mydlink Unit {self._uid}",
            "manufacturer": "D-Link",
            "model": unit.get("model") or info.get("device_model"),
            "sw_version": unit.get("version") or info.get("fw_ver"),
            "via_device": (DOMAIN, self._mydlink_id),
        }

    @property
    def available(self) -> bool:
        return super().available and self._info is not None and self._unit is not None

    @property
    def is_on(self) -> bool | None:
        info = self._info
        if info is None:
            return None
        value = status_value(info, self._uid, self._description.status_type)
        if value is None:
            # mydlink only includes the latest changed statuses in change_cache. If a
            # known leak/alarm status is missing but the unit is present, treat it as
            # normal/off rather than unknown.
            return False
        return value == 1

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self._info or {}
        unit = self._unit or {}
        value = status_value(info, self._uid, self._description.status_type)
        return {
            "mydlink_id": self._mydlink_id,
            "uid": self._uid,
            "unit_model": unit.get("model"),
            "sub_id": unit.get("sub_id"),
            "status_type": self._description.status_type,
            "raw_value": value,
            "assumed_off": value is None,
            "private_ip": info.get("private_ip"),
            "firmware": unit.get("version") or info.get("fw_ver"),
            "raw_change_cache": info.get("change_cache"),
        }
