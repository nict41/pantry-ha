"""Set up the Pantry integration."""

from __future__ import annotations

from aiohttp import hdrs, web
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN
from .models import InvalidPayload, UnsupportedSchema, validate_payload
from .store import PantryData

PLATFORMS: list[Platform] = [Platform.SENSOR]

type PantryConfigEntry = ConfigEntry[PantryData]


async def async_setup_entry(hass: HomeAssistant, entry: PantryConfigEntry) -> bool:
    """Set up Pantry from a config entry."""
    data = PantryData(hass, entry.entry_id)
    await data.async_load()
    entry.runtime_data = data

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Handle a push from the Pantry app."""
        try:
            body = await request.json()
        except ValueError:
            return web.json_response(
                {"ok": False, "error": "invalid_payload"}, status=400
            )

        try:
            payload = validate_payload(body)
        except UnsupportedSchema:
            return web.json_response(
                {"ok": False, "error": "unsupported_schema"}, status=400
            )
        except InvalidPayload:
            return web.json_response(
                {"ok": False, "error": "invalid_payload"}, status=400
            )

        applied = await data.async_apply(payload)
        return web.json_response(
            {"ok": True, "applied": applied, "items": len(data.raw_items)}
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    webhook.async_register(
        hass,
        DOMAIN,
        entry.title,
        entry.data[CONF_WEBHOOK_ID],
        handle_webhook,
        local_only=False,
        allowed_methods=[hdrs.METH_POST],
    )

    async def refresh_at_midnight(now: object) -> None:
        """Refresh statuses after the local date changes."""
        await data.async_refresh_day()

    entry.async_on_unload(
        async_track_time_change(
            hass, refresh_at_midnight, hour=0, minute=0, second=1
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PantryConfigEntry) -> bool:
    """Unload a Pantry config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PantryConfigEntry) -> None:
    """Delete stored data when an entry is removed."""
    data = PantryData(hass, entry.entry_id)
    await data.async_remove()
