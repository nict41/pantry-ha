"""Tests for pushes through the webhook and the midnight refresh."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import ClientResponse
from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
)

from custom_components.pantry.const import (
    EVENT_ITEM_ADDED,
    EVENT_ITEM_REMOVED,
    EVENT_ITEM_STATUS_CHANGED,
)

from .conftest import item, payload

URL = "/api/webhook/test-hook"

type Post = Callable[[dict[str, Any]], Awaitable[ClientResponse]]


@pytest.fixture(autouse=True)
async def utc_noon(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Fix the date and time zone."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2026-11-01 12:00:00+00:00")


@pytest.fixture
async def client(
    hass: HomeAssistant, setup_entry: MockConfigEntry, hass_client_no_auth: Any
) -> TestClient:
    """Return an unauthenticated client, as the phone is."""
    return await hass_client_no_auth()


@pytest.fixture
def post(hass: HomeAssistant, client: TestClient) -> Post:
    """Post a payload and let Home Assistant settle."""

    async def _post(body: dict[str, Any]) -> ClientResponse:
        response = await client.post(URL, json=body)
        await hass.async_block_till_done()
        return response

    return _post


async def test_push_is_applied(post: Post) -> None:
    response = await post(payload(items=[item()]))
    assert response.status == 200
    assert await response.json() == {"ok": True, "applied": True, "items": 1}


async def test_push_updates_sensors(hass: HomeAssistant, post: Post) -> None:
    await post(payload(items=[item()]))
    state = hass.states.get("sensor.pantry_items")
    assert state.state == "1"
    pushed = state.attributes["items"][0]
    assert pushed["status"] == "expiring_soon"
    assert pushed["days_left"] == 1
    assert pushed["expiry_date"] == "2026-11-02"
    assert hass.states.get("sensor.pantry_expiring_soon").state == "1"


async def test_repeat_sequence_is_ignored(hass: HomeAssistant, post: Post) -> None:
    await post(payload(items=[item()]))
    response = await post(payload(items=[]))
    assert await response.json() == {"ok": True, "applied": False, "items": 1}
    assert hass.states.get("sensor.pantry_items").state == "1"


async def test_older_sequence_is_ignored(hass: HomeAssistant, post: Post) -> None:
    await post(payload(items=[item()]))
    response = await post(payload(sequence=99, items=[]))
    assert (await response.json())["applied"] is False
    assert hass.states.get("sensor.pantry_items").state == "1"


async def test_manual_applies_with_older_sequence(
    hass: HomeAssistant, post: Post
) -> None:
    await post(payload(items=[item()]))
    response = await post(payload(sequence=99, reason="manual", items=[]))
    assert (await response.json())["applied"] is True
    assert hass.states.get("sensor.pantry_items").state == "0"


async def test_bad_json_is_rejected(client: TestClient) -> None:
    response = await client.post(URL, data="not json")
    assert response.status == 400
    assert await response.json() == {"ok": False, "error": "invalid_payload"}


async def test_other_schema_is_rejected(post: Post) -> None:
    response = await post(payload(schema=2))
    assert response.status == 400
    assert await response.json() == {"ok": False, "error": "unsupported_schema"}


async def test_get_changes_nothing(
    hass: HomeAssistant, post: Post, client: TestClient
) -> None:
    await post(payload(items=[item()]))
    await client.get(URL)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.pantry_items").state == "1"


async def test_first_sync_fires_no_events(hass: HomeAssistant, post: Post) -> None:
    added = async_capture_events(hass, EVENT_ITEM_ADDED)
    await post(payload(items=[item()]))
    assert added == []


async def test_second_sync_fires_events(hass: HomeAssistant, post: Post) -> None:
    await post(
        payload(
            items=[
                item(id="kept", expiry_date="2026-12-01"),
                item(id="gone"),
            ]
        )
    )
    added = async_capture_events(hass, EVENT_ITEM_ADDED)
    removed = async_capture_events(hass, EVENT_ITEM_REMOVED)
    changed = async_capture_events(hass, EVENT_ITEM_STATUS_CHANGED)

    await post(
        payload(
            sequence=101,
            items=[
                item(id="kept", expiry_date="2026-11-02"),
                item(id="new"),
            ],
        )
    )

    assert [event.data["id"] for event in added] == ["new"]
    assert [event.data["id"] for event in removed] == ["gone"]
    assert [event.data["id"] for event in changed] == ["kept"]
    assert changed[0].data["old_status"] == "ok"
    assert changed[0].data["new_status"] == "expiring_soon"


async def test_data_survives_reload(
    hass: HomeAssistant, post: Post, setup_entry: MockConfigEntry
) -> None:
    await post(payload(items=[item()]))
    await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.pantry_items").state == "1"


async def test_sequence_survives_reload(
    hass: HomeAssistant, post: Post, setup_entry: MockConfigEntry
) -> None:
    await post(payload(items=[item()]))
    await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    response = await post(payload(items=[]))
    assert (await response.json())["applied"] is False


async def test_midnight_updates_status_without_a_push(
    hass: HomeAssistant, post: Post, freezer: FrozenDateTimeFactory
) -> None:
    await post(payload(items=[item(expiry_date="2026-11-05")]))
    changed = async_capture_events(hass, EVENT_ITEM_STATUS_CHANGED)
    assert hass.states.get("sensor.pantry_expiring_soon").state == "0"

    freezer.move_to("2026-11-02 00:00:02+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pantry_expiring_soon").state == "1"
    assert changed[0].data["new_status"] == "expiring_soon"
