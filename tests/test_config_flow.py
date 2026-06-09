"""Test the Moen Smart Water Network config flow."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.moen_smart_water_network.const import CONF_REFRESH_TOKEN, DOMAIN
from custom_components.moen_smart_water_network.moen_api.const import OAUTH_URL

TOKEN_RESPONSE = {
    "token": {
        "access_token": "AT",
        "refresh_token": "RT",
        "id_token": "IT",
        "expires_in": 3600,
    }
}


async def _start_menu(hass: HomeAssistant) -> dict:
    """Start the flow and return the menu result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    return result


async def test_credentials_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A valid username/password logs in and stores the resulting tokens."""
    aioclient_mock.post(OAUTH_URL, json=TOKEN_RESPONSE)

    result = await _start_menu(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "credentials"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"

    with patch(
        "custom_components.moen_smart_water_network.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "secret",
        CONF_ACCESS_TOKEN: "AT",
        CONF_REFRESH_TOKEN: "RT",
    }
    assert len(mock_setup.mock_calls) == 1


async def test_credentials_invalid_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Bad credentials surface an invalid_auth error on the form."""
    aioclient_mock.post(OAUTH_URL, status=401)

    result = await _start_menu(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "credentials"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "wrong"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_token_flow(hass: HomeAssistant) -> None:
    """The advanced token path stores the pasted tokens directly."""
    result = await _start_menu(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token"

    with patch(
        "custom_components.moen_smart_water_network.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_ACCESS_TOKEN: "a", CONF_REFRESH_TOKEN: "b"},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ACCESS_TOKEN: "a", CONF_REFRESH_TOKEN: "b"}
