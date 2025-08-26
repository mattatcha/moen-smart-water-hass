"""Adds config flow for Blueprint."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import selector

from .const import CONF_REFRESH_TOKEN, DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Moen Smart Water Network."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title="Moen Smart Water Network",
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
                    vol.Required(CONF_REFRESH_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        ),
                    ),
                }
            ),
            errors=_errors,
        )
