"""Migrate the pre-0.1.1 child device identifiers before loading entities."""

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def async_migrate_child_devices(hass: HomeAssistant, entry_id: str) -> None:
    """Reuse legacy devices, or clean up duplicates left by the identifier change."""
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    for device in dr.async_entries_for_config_entry(devices, entry_id):
        # The old integration created exactly one three-part identifier per child.
        if len(device.identifiers) != 1:
            continue
        identifier = next(iter(device.identifiers))
        if len(identifier) != 3 or identifier[0] != DOMAIN:
            continue
        new_identifier = (DOMAIN, f"{identifier[1]}_uid{identifier[2]}")
        registered_entities = er.async_entries_for_device(entities, device.id)
        if device.config_entries != {entry_id} or any(
            entity.config_entry_id != entry_id for entity in registered_entities
        ):
            _LOGGER.warning("Skipping shared legacy mydlink device %s", device.id)
            continue

        current = devices.async_get_device(identifiers={new_identifier})
        if current is None or current.id == device.id:
            devices.async_update_device(device.id, new_identifiers={new_identifier})
            continue

        # Keep the already-current device and its user settings. Recover legacy
        # settings only where the current device has none.
        settings = {
            key: getattr(device, key)
            for key in ("area_id", "name_by_user", "disabled_by")
            if getattr(current, key) is None and getattr(device, key) is not None
        }
        devices.async_update_device(
            current.id,
            add_config_entry_id=entry_id,
            labels=current.labels | device.labels,
            **settings,
        )
        for entity in registered_entities:
            entities.async_update_entity(entity.entity_id, device_id=current.id)
        # Detach only after moving entities: removal otherwise deletes their
        # registry entries. Parent devices and entity unique IDs are untouched.
        devices.async_update_device(device.id, remove_config_entry_id=entry_id)
