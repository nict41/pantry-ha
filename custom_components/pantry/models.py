"""Payload validation and status rules for Pantry."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any, cast

import voluptuous as vol

from .const import (
    SCHEMA_VERSION,
    STATUS_EXPIRED,
    STATUS_EXPIRING_SOON,
    STATUS_FROZEN,
    STATUS_OK,
    STATUS_UNKNOWN,
)


class InvalidPayload(ValueError):
    """The pushed payload is not valid."""


class UnsupportedSchema(InvalidPayload):
    """The pushed payload uses an unsupported schema version."""


def _integer(value: Any, *, minimum: int | None = None, maximum: int | None = None) -> int:
    """Return an integer, rejecting booleans and out-of-range values."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise vol.Invalid("expected an integer")
    if minimum is not None and value < minimum:
        raise vol.Invalid(f"expected at least {minimum}")
    if maximum is not None and value > maximum:
        raise vol.Invalid(f"expected at most {maximum}")
    return value


def _non_empty_string(value: Any) -> str:
    """Return a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise vol.Invalid("expected a non-empty string")
    return value


def _optional_date(value: Any) -> str | None:
    """Return a YYYY-MM-DD string, or None. Dates stay strings so templates can compare them."""
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 10:
        raise vol.Invalid("expected a YYYY-MM-DD string or null")
    try:
        date.fromisoformat(value)
    except ValueError as err:
        raise vol.Invalid("invalid date") from err
    return value


def _utc_string(value: Any) -> str:
    """Return an ISO 8601 UTC string, rejecting other offsets."""
    if not isinstance(value, str):
        raise vol.Invalid("expected an ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise vol.Invalid("invalid ISO 8601 timestamp") from err
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise vol.Invalid("expected a UTC timestamp")
    return value


_ITEM_SCHEMA = vol.Schema(
    {
        vol.Required("id"): _non_empty_string,
        vol.Required("name"): _non_empty_string,
        vol.Optional("brand", default=None): vol.Any(None, str),
        vol.Optional("quantity", default=None): vol.Any(None, str),
        vol.Optional("category", default=None): vol.Any(None, str),
        vol.Optional("food_group", default=None): vol.Any(None, str),
        vol.Optional("location", default=None): vol.Any(None, str),
        vol.Required("count"): lambda value: _integer(value, minimum=1),
        vol.Optional("barcode", default=None): vol.Any(None, str),
        vol.Optional("expiry_date", default=None): _optional_date,
        vol.Optional("printed_date", default=None): _optional_date,
        vol.Optional("opened_on", default=None): _optional_date,
        vol.Optional("added_at", default=None): vol.Any(None, str),
    },
    extra=vol.REMOVE_EXTRA,
)

_PAYLOAD_SCHEMA = vol.Schema(
    {
        vol.Required("schema"): lambda value: _integer(
            value, minimum=SCHEMA_VERSION, maximum=SCHEMA_VERSION
        ),
        vol.Required("sequence"): lambda value: _integer(value, minimum=1),
        vol.Required("sent_at"): _utc_string,
        vol.Required("reason"): vol.In(("change", "daily", "manual")),
        vol.Required("notify_days_before"): lambda value: _integer(
            value, minimum=0, maximum=30
        ),
        vol.Required("items"): [_ITEM_SCHEMA],
    },
    extra=vol.REMOVE_EXTRA,
)


def validate_payload(body: Any) -> dict[str, Any]:
    """Validate a pushed payload, keeping only known fields."""
    if not isinstance(body, dict):
        raise InvalidPayload("payload must be an object")

    schema = body.get("schema")
    if (
        isinstance(schema, int)
        and not isinstance(schema, bool)
        and schema != SCHEMA_VERSION
    ):
        raise UnsupportedSchema(f"unsupported schema {schema}")

    try:
        return cast(dict[str, Any], _PAYLOAD_SCHEMA(body))
    except vol.Invalid as err:
        raise InvalidPayload(str(err)) from err


def status_for(
    item: dict[str, Any], today: date, notify_days_before: int
) -> tuple[str, int | None]:
    """Return the status and days left for an item."""
    if item.get("location") == "freezer":
        return STATUS_FROZEN, None

    expiry_date = item.get("expiry_date")
    if expiry_date is None:
        return STATUS_UNKNOWN, None

    days_left = (date.fromisoformat(expiry_date) - today).days
    if days_left < 0:
        return STATUS_EXPIRED, days_left
    if days_left <= notify_days_before:
        return STATUS_EXPIRING_SOON, days_left
    return STATUS_OK, days_left


def enrich(
    items: Iterable[dict[str, Any]], today: date, notify_days_before: int
) -> list[dict[str, Any]]:
    """Return copies of items with status and days left, in display order."""
    enriched: list[dict[str, Any]] = []
    for item in items:
        copy = dict(item)
        status, days_left = status_for(copy, today, notify_days_before)
        copy["status"] = status
        copy["days_left"] = days_left
        enriched.append(copy)

    return sorted(
        enriched,
        key=lambda item: (
            item["expiry_date"] is None,
            item["expiry_date"] or "",
            item["name"],
        ),
    )
