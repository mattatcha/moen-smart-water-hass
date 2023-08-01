"""Adds config flow for Blueprint."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import selector

from .const import DOMAIN, CONF_REFRESH_TOKEN

# from homeassistant.helpers import config_entry_oauth2_flow


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Moen Smart Water Network."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}

        if user_input is not None:
            # try:
            #     res = await self._test_credentials(
            #         access_token=user_input[CONF_ACCESS_TOKEN],
            #         refresh_token=user_input[CONF_REFRESH_TOKEN],
            #     )
            # except ApiClientAuthenticationError as exception:
            #     LOGGER.warning(exception)
            #     _errors["base"] = "auth"
            # except ApiClientCommunicationError as exception:
            #     LOGGER.error(exception)
            #     _errors["base"] = "connection"
            # except ApiClientError as exception:
            #     LOGGER.exception(exception)
            #     _errors["base"] = "unknown"
            # else:
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

    # async def _test_credentials(self, access_token: str, refresh_token: str) -> dict:
    #     """Validate credentials."""
    #     client = ApiClient(
    #         access_token=access_token,
    #         refresh_token=refresh_token,
    #         session=async_create_clientsession(self.hass),
    #     )
    #     await client.async_auth()
