"""Sensors for the Pantry integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PantryConfigEntry
from .const import (
    DOMAIN,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
    STATUS_FROZEN,
    STATUS_UNKNOWN,
)
from .store import PantryData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PantryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pantry sensors."""
    data: PantryData = entry.runtime_data
    async_add_entities(
        [
            PantryItemsSensor(entry, data),
            PantryCountSensor(entry, data, "expiring_soon", STATUS_EXPIRING_SOON),
            PantryCountSensor(entry, data, "expired", STATUS_EXPIRED),
            PantryCountSensor(entry, data, "needs_date", STATUS_UNKNOWN),
            PantryCountSensor(entry, data, "frozen", STATUS_FROZEN),
            PantryLastSyncSensor(entry, data),
        ]
    )


class PantrySensor(SensorEntity):
    """Base class for Pantry sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, entry: PantryConfigEntry, data: PantryData, key: str
    ) -> None:
        self._data = data
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Pantry",
            manufacturer="Pantry",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to data updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._data.signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        """Write the new state."""
        self.async_write_ha_state()


class PantryItemsSensor(PantrySensor):
    """Total number of pantry items."""

    _attr_native_unit_of_measurement = "items"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"items"})

    def __init__(self, entry: PantryConfigEntry, data: PantryData) -> None:
        super().__init__(entry, data, "items")

    @property
    def native_value(self) -> int:
        """Return the number of list entries."""
        return len(self._data.raw_items)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the item list and status counts."""
        counts = self._data.counts
        return {
            "items": self._data.items,
            "expiring_soon": counts[STATUS_EXPIRING_SOON],
            "expired": counts[STATUS_EXPIRED],
            "needs_date": counts[STATUS_UNKNOWN],
            "frozen": counts[STATUS_FROZEN],
        }


class PantryCountSensor(PantrySensor):
    """Count of items in one status."""

    _attr_native_unit_of_measurement = "items"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"items"})

    def __init__(
        self,
        entry: PantryConfigEntry,
        data: PantryData,
        key: str,
        status: str,
    ) -> None:
        super().__init__(entry, data, key)
        self._status = status

    @property
    def native_value(self) -> int:
        """Return the count for this status."""
        return self._data.counts[self._status]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the names of matching items."""
        return {
            "items": [
                item["name"]
                for item in self._data.items
                if item["status"] == self._status
            ]
        }


class PantryLastSyncSensor(PantrySensor):
    """Time of the last applied push."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: PantryConfigEntry, data: PantryData) -> None:
        super().__init__(entry, data, "last_sync")

    @property
    def native_value(self) -> datetime | None:
        """Return the last sync time."""
        return self._data.last_sync
