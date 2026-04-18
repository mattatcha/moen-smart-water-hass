"""Config flow for Moen Smart Water Network."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, DOMAIN
from .moen_api import (
    MoenApiAuthenticationError,
    MoenApiClient,
    MoenApiCommunicationError,
    MoenApiError,
    MoenAuth,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
        ),
        vol.Required(CONF_REFRESH_TOKEN): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Moen Smart Water Network."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def _async_validate(self, user_input: dict[str, Any]) -> dict:
        """Validate credentials by fetching the user profile."""
        session = async_get_clientsession(self.hass)
        auth = MoenAuth(
            access_token=user_input[CONF_ACCESS_TOKEN],
            refresh_token=user_input[CONF_REFRESH_TOKEN],
            session=session,
        )
        client = MoenApiClient(auth=auth, session=session)
        # Refresh up front so that an obviously bad refresh token fails fast.
        await auth.async_refresh_token()
        return await client.async_get_user()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                user = await self._async_validate(user_input)
            except MoenApiAuthenticationError:
                errors["base"] = "invalid_auth"
            except MoenApiCommunicationError:
                errors["base"] = "cannot_connect"
            except MoenApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                unique_id = str(user.get("legacyId") or user.get("id"))
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Moen Smart Water Network",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, _entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Handle reauthentication when stored tokens become invalid."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Prompt the user for new credentials and update the existing entry."""
        errors: dict[str, str] = {}

        if user_input is not None and self._reauth_entry is not None:
            try:
                await self._async_validate(user_input)
            except MoenApiAuthenticationError:
                errors["base"] = "invalid_auth"
            except MoenApiCommunicationError:
                errors["base"] = "cannot_connect"
            except MoenApiError:
                errors["base"] = "unknown"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={**self._reauth_entry.data, **user_input},
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
