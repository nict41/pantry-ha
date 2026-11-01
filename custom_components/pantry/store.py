"""Stored state for a Pantry config entry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_ITEM_ADDED,
    EVENT_ITEM_REMOVED,
    EVENT_ITEM_STATUS_CHANGED,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
    STATUS_FROZEN,
    STATUS_OK,
    STATUS_UNKNOWN,
    STORAGE_VERSION,
)
from .models import enrich, status_for

_STATUSES = (
    STATUS_OK,
    STATUS_EXPIRING_SOON,
    STATUS_EXPIRED,
    STATUS_UNKNOWN,
    STATUS_FROZEN,
)


class PantryData:
    """Runtime and persisted state for one Pantry entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}"
        )
        self.sequence: int = 0
        self.notify_days_before: int = 3
        self.raw_items: list[dict[str, Any]] = []
        self.last_sync: datetime | None = None
        self.has_data: bool = False
        self._statuses: dict[str, str] = {}

    @property
    def signal(self) -> str:
        """Return the dispatcher signal for entity updates."""
        return f"{DOMAIN}_{self.entry_id}_updated"

    @property
    def items(self) -> list[dict[str, Any]]:
        """Return the current items enriched with status."""
        return enrich(
            self.raw_items, dt_util.now().date(), self.notify_days_before
        )

    @property
    def counts(self) -> dict[str, int]:
        """Return a count for every status."""
        counts = dict.fromkeys(_STATUSES, 0)
        for item in self.items:
            counts[item["status"]] += 1
        return counts

    async def async_load(self) -> None:
        """Load persisted state and compute statuses without firing events."""
        stored = await self._store.async_load()
        if not stored:
            return

        self.sequence = int(stored.get("sequence", 0))
        self.notify_days_before = int(stored.get("notify_days_before", 3))
        self.raw_items = stored.get("items", [])
        last_sync = stored.get("last_sync")
        if isinstance(last_sync, str):
            try:
                self.last_sync = datetime.fromisoformat(last_sync)
            except ValueError:
                self.last_sync = None
        self.has_data = bool(stored.get("has_data", bool(self.raw_items)))

        today = dt_util.now().date()
        self._statuses = {
            item["id"]: status_for(item, today, self.notify_days_before)[0]
            for item in self.raw_items
        }

    async def async_apply(self, payload: dict[str, Any]) -> bool:
        """Apply a validated payload, firing events for real changes."""
        if payload["reason"] != "manual" and payload["sequence"] <= self.sequence:
            return False

        previous_items = {item["id"]: item for item in self.raw_items}
        previous_statuses = dict(self._statuses)
        today = dt_util.now().date()
        notify_days_before = payload["notify_days_before"]
        new_items: list[dict[str, Any]] = payload["items"]
        new_statuses = {
            item["id"]: status_for(item, today, notify_days_before)[0]
            for item in new_items
        }

        if self.has_data:
            for item in new_items:
                if item["id"] not in previous_items:
                    self.hass.bus.async_fire(
                        EVENT_ITEM_ADDED,
                        enrich([item], today, notify_days_before)[0],
                    )

            for item_id, item in previous_items.items():
                if item_id not in new_statuses:
                    removed = dict(item)
                    status, days_left = status_for(
                        removed, today, self.notify_days_before
                    )
                    removed["status"] = status
                    removed["days_left"] = days_left
                    self.hass.bus.async_fire(EVENT_ITEM_REMOVED, removed)

            for item in new_items:
                item_id = item["id"]
                if (
                    item_id in previous_statuses
                    and previous_statuses[item_id] != new_statuses[item_id]
                ):
                    changed = enrich([item], today, notify_days_before)[0]
                    changed["old_status"] = previous_statuses[item_id]
                    changed["new_status"] = new_statuses[item_id]
                    self.hass.bus.async_fire(EVENT_ITEM_STATUS_CHANGED, changed)

        self.sequence = payload["sequence"]
        self.notify_days_before = notify_days_before
        self.raw_items = new_items
        self.last_sync = dt_util.utcnow()
        self.has_data = True

        await self._store.async_save(
            {
                "sequence": self.sequence,
                "notify_days_before": self.notify_days_before,
                "items": self.raw_items,
                "last_sync": self.last_sync.isoformat(),
                "has_data": self.has_data,
            }
        )

        self._statuses = new_statuses
        async_dispatcher_send(self.hass, self.signal)
        return True

    async def async_refresh_day(self) -> None:
        """Recompute statuses at midnight and announce changes."""
        today = dt_util.now().date()
        new_statuses = {
            item["id"]: status_for(item, today, self.notify_days_before)[0]
            for item in self.raw_items
        }

        for item in self.raw_items:
            item_id = item["id"]
            old_status = self._statuses.get(item_id)
            new_status = new_statuses[item_id]
            if old_status is not None and old_status != new_status:
                changed = enrich(
                    [item], today, self.notify_days_before
                )[0]
                changed["old_status"] = old_status
                changed["new_status"] = new_status
                self.hass.bus.async_fire(EVENT_ITEM_STATUS_CHANGED, changed)

        self._statuses = new_statuses
        async_dispatcher_send(self.hass, self.signal)

    async def async_remove(self) -> None:
        """Remove the persisted data."""
        await self._store.async_remove()
