"""Regression tests using Home Assistant's real device and entity registries."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dlink_mydlink_water import async_setup_entry
from custom_components.dlink_mydlink_water.const import DOMAIN
from custom_components.dlink_mydlink_water.device_migration import async_migrate_child_devices


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"email": "test@example.com", "password": "test"})
    entry.add_to_hass(hass)
    return entry


def child(device_registry, entry, uid, legacy=False, **kwargs):
    identifier = (DOMAIN, "123", str(uid)) if legacy else (DOMAIN, f"123_uid{uid}")
    return device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={identifier}, **kwargs
    )


def entity(entity_registry, entry, device, key="water_leak"):
    return entity_registry.async_get_or_create(
        "binary_sensor", DOMAIN, f"{DOMAIN}_123_uid1_{key}_type22",
        config_entry=entry, device_id=device.id,
    )


@pytest.mark.parametrize("uid", [0, 1, 12])
async def test_reuse_legacy(hass, entry, device_registry, entity_registry, area_registry, uid):
    area = area_registry.async_create("Kitchen")
    parent = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "123")}
    )
    old = child(device_registry, entry, uid, legacy=True, via_device=(DOMAIN, "123"))
    device_registry.async_update_device(
        old.id, name_by_user="Kitchen leak", area_id=area.id,
        disabled_by=dr.DeviceEntryDisabler.USER, labels={"important"},
    )
    sensor = entity(entity_registry, entry, old)

    async_migrate_child_devices(hass, entry.entry_id)
    await hass.async_block_till_done()

    migrated = device_registry.async_get_device(identifiers={(DOMAIN, f"123_uid{uid}")})
    assert migrated.id == old.id
    assert migrated.name_by_user == "Kitchen leak"
    assert migrated.area_id == area.id
    assert migrated.disabled_by == dr.DeviceEntryDisabler.USER
    assert migrated.labels == {"important"}
    assert migrated.via_device_id == parent.id
    assert device_registry.async_get_device(identifiers={(DOMAIN, "123", str(uid))}) is None
    assert entity_registry.async_get(sensor.entity_id).device_id == old.id
    assert entity_registry.async_get(sensor.entity_id).unique_id == sensor.unique_id

    async_migrate_child_devices(hass, entry.entry_id)
    assert len(device_registry.devices) == 2


@pytest.mark.parametrize("has_legacy_entity", [False, True])
async def test_cleanup_duplicate(hass, entry, device_registry, entity_registry, area_registry, has_legacy_entity):
    area = area_registry.async_create("Kitchen")
    old = child(device_registry, entry, 1, legacy=True)
    device_registry.async_update_device(old.id, name_by_user="Old name", area_id=area.id, labels={"old"})
    current = child(device_registry, entry, 1)
    device_registry.async_update_device(current.id, name_by_user="Current name", labels={"new"})
    old_entity = entity(entity_registry, entry, old) if has_legacy_entity else None
    current_entity = entity(entity_registry, entry, current, "alarm_status")

    async_migrate_child_devices(hass, entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(old.id) is None
    assert len(device_registry.devices) == 1
    kept = device_registry.async_get(current.id)
    assert kept.identifiers == {(DOMAIN, "123_uid1")}
    assert kept.name_by_user == "Current name"
    assert kept.area_id == area.id
    assert kept.labels == {"old", "new"}
    for sensor in (old_entity, current_entity):
        if sensor:
            registered = entity_registry.async_get(sensor.entity_id)
            assert registered is not None
            assert registered.device_id == current.id
            assert registered.unique_id == sensor.unique_id
    async_migrate_child_devices(hass, entry.entry_id)
    assert len(device_registry.devices) == 1


async def test_new_install_and_parent_untouched(hass, entry, device_registry):
    parent = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "123")}
    )
    current = child(device_registry, entry, 0)
    async_migrate_child_devices(hass, entry.entry_id)
    assert device_registry.async_get(parent.id) == parent
    assert device_registry.async_get(current.id) == current
    assert len(device_registry.devices) == 2


async def test_empty_registry(hass, entry, device_registry):
    async_migrate_child_devices(hass, entry.entry_id)
    assert not device_registry.devices


async def test_other_entry_and_domain_untouched(hass, entry, device_registry):
    other = MockConfigEntry(domain=DOMAIN)
    other.add_to_hass(hass)
    foreign_entry = child(device_registry, other, 1, legacy=True)
    foreign_domain = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("other", "123", "2")}
    )
    async_migrate_child_devices(hass, entry.entry_id)
    assert device_registry.async_get(foreign_entry.id) == foreign_entry
    assert device_registry.async_get(foreign_domain.id) == foreign_domain


async def test_shared_device_untouched(hass, entry, device_registry):
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    old = child(device_registry, entry, 1, legacy=True)
    device_registry.async_update_device(old.id, add_config_entry_id=other.entry_id)
    current = child(device_registry, entry, 1)
    async_migrate_child_devices(hass, entry.entry_id)
    assert device_registry.async_get(old.id).identifiers == old.identifiers
    assert device_registry.async_get(current.id) == current


async def test_multiple_children_without_live_data(hass, entry, device_registry):
    old = [child(device_registry, entry, uid, legacy=True) for uid in range(3)]
    async_migrate_child_devices(hass, entry.entry_id)
    assert len(device_registry.devices) == 3
    for uid, device in enumerate(old):
        assert device_registry.async_get_device(identifiers={(DOMAIN, f"123_uid{uid}")}).id == device.id


async def test_setup_migrates_before_platforms(hass, entry, device_registry):
    old = child(device_registry, entry, 1, legacy=True)

    async def forward(config_entry, platforms):
        assert device_registry.async_get_device(identifiers={(DOMAIN, "123_uid1")}).id == old.id
        assert device_registry.async_get_device(identifiers={(DOMAIN, "123", "1")}) is None

    with (
        patch("custom_components.dlink_mydlink_water.MydlinkApiClient"),
        patch("custom_components.dlink_mydlink_water.DataUpdateCoordinator") as coordinator,
        patch.object(hass.config_entries, "async_forward_entry_setups", side_effect=forward),
    ):
        coordinator.return_value.async_config_entry_first_refresh = AsyncMock()
        assert await async_setup_entry(hass, entry)


async def test_entity_unique_ids_and_device_info(hass, entry):
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
    from custom_components.dlink_mydlink_water.binary_sensor import (
        MydlinkUnitStatusSensor, UNIT_MODEL_STATUS,
    )
    import logging

    coordinator = DataUpdateCoordinator(hass, logging.getLogger(__name__), name=DOMAIN, config_entry=entry)
    coordinator.async_set_updated_data({"devices": []})
    sensor = MydlinkUnitStatusSensor(coordinator, "123", 1, UNIT_MODEL_STATUS["DCH-S163"][0])
    assert sensor.unique_id == f"{DOMAIN}_123_uid1_water_leak_type22"
    assert sensor.device_info["identifiers"] == {(DOMAIN, "123_uid1")}
    assert sensor.device_info["via_device"] == (DOMAIN, "123")


async def test_multiple_identifiers_untouched(hass, entry, device_registry):
    old = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "123", "1"), ("other", "extra")},
    )
    async_migrate_child_devices(hass, entry.entry_id)
    assert device_registry.async_get(old.id) == old


async def test_foreign_entity_untouched(hass, entry, device_registry, entity_registry):
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    old = child(device_registry, entry, 1, legacy=True)
    sensor = entity(entity_registry, other, old)
    current = child(device_registry, entry, 1)
    async_migrate_child_devices(hass, entry.entry_id)
    await hass.async_block_till_done()
    assert device_registry.async_get(old.id) == old
    assert device_registry.async_get(current.id) == current
    assert entity_registry.async_get(sensor.entity_id).device_id == old.id
