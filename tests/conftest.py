"""Define fixtures available for all tests."""

import pytest
from homeassistant.const import CONF_ACCESS_TOKEN
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.moen_smart_water_network.const import CONF_REFRESH_TOKEN, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    return


@pytest.fixture
def config_entry(hass):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "TEST_USER_ID", CONF_REFRESH_TOKEN: ""},
        version=1,
    )


# This fixture, when used, will result in calls to async_get_data to return None. To have the call
# return a value, we would add the `return_value=<VALUE_TO_RETURN>` parameter to the patch call.
# @pytest.fixture(name="bypass_get_data")
# def bypass_get_data_fixture():
#     """Skip calls to get data from API."""
#     with patch("pyschlage.Schlage.locks"), patch("pyschlage.Schlage.users"):
#         yield


def mock_response(data: str) -> AiohttpClientMockResponse:
    """Create a fake AiohttpClientMockResponse."""
    return AiohttpClientMockResponse(
        "GET", "https://api.prod.iot.moen.com/v3/devices", response=(data)
    )


@pytest.fixture(name="api_responses")
def mock_api_responses() -> list[str]:
    """
    Fixture to set up a list of fake API responsees for tests to extend.

    These are returned in the order they are requested by the update coordinator.
    """
    return []


@pytest.fixture(name="responses")
def mock_responses(api_responses: list[str]) -> list[AiohttpClientMockResponse]:
    """Fixture to set up a list of fake API responsees for tests to extend."""
    return [mock_response(api_response) for api_response in api_responses]


# @pytest.fixture
# def aioclient_mock_fixture(aioclient_mock):
#     """Fixture to provide a aioclient mocker."""
#     now = round(time.time())
#     # Mocks the login response for flo.
#     aioclient_mock.post(
#         "https://api.meetflo.com/api/v1/users/auth",
#         text=json.dumps(
#             {
#                 "token": TEST_TOKEN,
#                 "tokenPayload": {
#                     "user": {"user_id": TEST_USER_ID, "email": TEST_EMAIL_ADDRESS},
#                     "timestamp": now,
#                 },
#                 "tokenExpiration": 86400,
#                 "timeNow": now,
#             }
#         ),
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#         status=HTTPStatus.OK,
#     )
#     # Mocks the presence ping response for flo.
#     aioclient_mock.post(
#         "https://api-gw.meetflo.com/api/v2/presence/me",
#         text=load_fixture("flo/ping_response.json"),
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#         status=HTTPStatus.OK,
#     )
#     # Mocks the devices for flo.
#     aioclient_mock.get(
#         "https://api-gw.meetflo.com/api/v2/devices/98765",
#         text=load_fixture("flo/device_info_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#     )
#     aioclient_mock.get(
#         "https://api-gw.meetflo.com/api/v2/devices/32839",
#         text=load_fixture("flo/device_info_response_detector.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#     )
#     # Mocks the water consumption for flo.
#     aioclient_mock.get(
#         "https://api-gw.meetflo.com/api/v2/water/consumption",
#         text=load_fixture("flo/water_consumption_info_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#     )
#     # Mocks the location info for flo.
#     aioclient_mock.get(
#         "https://api-gw.meetflo.com/api/v2/locations/mmnnoopp",
#         text=load_fixture("flo/location_info_expand_devices_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#     )
#     # Mocks the user info for flo.
#     aioclient_mock.get(
#         "https://api-gw.meetflo.com/api/v2/users/12345abcde",
#         text=load_fixture("flo/user_info_expand_locations_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#         params={"expand": "locations"},
#     )
#     # Mocks the user info for flo.
#     aioclient_mock.get(
#         "https://api-gw.meetflo.com/api/v2/users/12345abcde",
#         text=load_fixture("flo/user_info_expand_locations_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#     )
#     # Mocks the valve open call for flo.
#     aioclient_mock.post(
#         "https://api-gw.meetflo.com/api/v2/devices/98765",
#         text=load_fixture("flo/device_info_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#         json={"valve": {"target": "open"}},
#     )
#     # Mocks the valve close call for flo.
#     aioclient_mock.post(
#         "https://api-gw.meetflo.com/api/v2/devices/98765",
#         text=load_fixture("flo/device_info_response_closed.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#         json={"valve": {"target": "closed"}},
#     )
#     # Mocks the health test call for flo.
#     aioclient_mock.post(
#         "https://api-gw.meetflo.com/api/v2/devices/98765/healthTest/run",
#         text=load_fixture("flo/user_info_expand_locations_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#     )
#     # Mocks the health test call for flo.
#     aioclient_mock.post(
#         "https://api-gw.meetflo.com/api/v2/locations/mmnnoopp/systemMode",
#         text=load_fixture("flo/user_info_expand_locations_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#         json={"systemMode": {"target": "home"}},
#     )
#     # Mocks the health test call for flo.
#     aioclient_mock.post(
#         "https://api-gw.meetflo.com/api/v2/locations/mmnnoopp/systemMode",
#         text=load_fixture("flo/user_info_expand_locations_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#         json={"systemMode": {"target": "away"}},
#     )
#     # Mocks the health test call for flo.
#     aioclient_mock.post(
#         "https://api-gw.meetflo.com/api/v2/locations/mmnnoopp/systemMode",
#         text=load_fixture("flo/user_info_expand_locations_response.json"),
#         status=HTTPStatus.OK,
#         headers={"Content-Type": CONTENT_TYPE_JSON},
#         json={
#             "systemMode": {
#                 "target": "sleep",
#                 "revertMinutes": 120,
#                 "revertMode": "home",
#             }
#         },
#     )
