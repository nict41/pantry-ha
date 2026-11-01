"""Config and options flows for Pantry."""

from __future__ import annotations

from homeassistant.components import webhook
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import NoURLAvailableError

from .const import DOMAIN


@callback
def pantry_link(hass: HomeAssistant, webhook_id: str) -> str:
    """Return the webhook link shown to the user."""
    try:
        return webhook.async_generate_url(hass, webhook_id)
    except NoURLAvailableError:
        return webhook.async_generate_path(webhook_id)


class PantryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Pantry config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Create the single Pantry entry."""
        self._async_abort_entries_match()

        if user_input is not None:
            webhook_id = webhook.async_generate_id()
            return self.async_create_entry(
                title="Pantry",
                data={CONF_WEBHOOK_ID: webhook_id},
                description_placeholders={
                    "webhook_url": pantry_link(self.hass, webhook_id)
                },
            )

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return PantryOptionsFlow()


class PantryOptionsFlow(OptionsFlow):
    """Show the Pantry link again."""

    async def async_step_init(
        self, user_input: dict[str, object] | None = None
    ) -> ConfigFlowResult:
        """Show the link or close the flow."""
        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "webhook_url": pantry_link(
                    self.hass, self.config_entry.data[CONF_WEBHOOK_ID]
                )
            },
        )
