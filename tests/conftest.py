"""Shared fixtures for the Pantry tests."""

from typing import Any

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pantry.const import DOMAIN


def item(**overrides: Any) -> dict[str, Any]:
    """Return a valid item."""
    return {
        "id": "a",
        "name": "Cream",
        "count": 1,
        "expiry_date": "2026-11-02",
    } | overrides


def payload(**overrides: Any) -> dict[str, Any]:
    """Return a valid payload."""
    return {
        "schema": 1,
        "sequence": 100,
        "sent_at": "2026-11-01T18:00:00Z",
        "reason": "change",
        "notify_days_before": 3,
        "items": [],
    } | overrides


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration."""


@pytest.fixture
async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up one Pantry entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_WEBHOOK_ID: "test-hook"}, title="Pantry"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
