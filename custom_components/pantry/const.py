"""Constants for the Pantry integration."""

from __future__ import annotations

DOMAIN = "pantry"

SCHEMA_VERSION = 1
STORAGE_VERSION = 1

EVENT_ITEM_ADDED = "pantry_item_added"
EVENT_ITEM_REMOVED = "pantry_item_removed"
EVENT_ITEM_STATUS_CHANGED = "pantry_item_status_changed"

STATUS_OK = "ok"
STATUS_EXPIRING_SOON = "expiring_soon"
STATUS_EXPIRED = "expired"
STATUS_UNKNOWN = "unknown"
STATUS_FROZEN = "frozen"
