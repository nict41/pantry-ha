"""Tests for the status rules and payload validation."""

from datetime import date
from typing import Any

import pytest

from custom_components.pantry.models import (
    InvalidPayload,
    UnsupportedSchema,
    enrich,
    status_for,
    validate_payload,
)

from .conftest import item, payload

TODAY = date(2026, 11, 1)


def _status(**overrides: Any) -> tuple[str, int | None]:
    return status_for(item(**overrides), TODAY, 3)


def test_today_is_expiring_soon() -> None:
    assert _status(expiry_date="2026-11-01") == ("expiring_soon", 0)


def test_last_warning_day_is_expiring_soon() -> None:
    assert _status(expiry_date="2026-11-04") == ("expiring_soon", 3)


def test_day_after_warning_is_ok() -> None:
    assert _status(expiry_date="2026-11-05") == ("ok", 4)


def test_yesterday_is_expired() -> None:
    assert _status(expiry_date="2026-10-31") == ("expired", -1)


def test_freezer_beats_a_date() -> None:
    assert _status(location="freezer") == ("frozen", None)


def test_no_date_is_unknown() -> None:
    assert _status(expiry_date=None) == ("unknown", None)


def test_enrich_sorts_by_date_then_undated_then_name() -> None:
    items = [
        item(id="1", name="Undated", expiry_date=None),
        item(id="2", name="Later", expiry_date="2026-12-01"),
        item(id="3", name="Pie", expiry_date="2026-11-02"),
        item(id="4", name="Apple", expiry_date="2026-11-02"),
    ]
    assert [i["name"] for i in enrich(items, TODAY, 3)] == [
        "Apple",
        "Pie",
        "Later",
        "Undated",
    ]


@pytest.mark.parametrize(
    "body",
    [
        [],
        {k: v for k, v in payload().items() if k != "items"},
        payload(reason="other"),
        payload(notify_days_before=31),
        payload(sequence=True),
        payload(items=[item(count=0)]),
        payload(items=[item(name="")]),
        payload(items=[item(expiry_date="2026-02-30")]),
        payload(items=[item(expiry_date="20261102")]),
    ],
)
def test_bad_payloads_are_rejected(body: Any) -> None:
    with pytest.raises(InvalidPayload):
        validate_payload(body)


def test_other_schema_is_unsupported() -> None:
    with pytest.raises(UnsupportedSchema):
        validate_payload(payload(schema=2))


def test_unknown_fields_are_dropped() -> None:
    result = validate_payload(payload(extra=1, items=[item(extra=1)]))
    assert "extra" not in result
    assert "extra" not in result["items"][0]


def test_dates_stay_strings() -> None:
    result = validate_payload(payload(items=[item()]))
    assert result["items"][0]["expiry_date"] == "2026-11-02"
