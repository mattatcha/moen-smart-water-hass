"""Define fixtures available for all tests."""

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_ACCESS_TOKEN
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.moen_smart_water_network.const import CONF_REFRESH_TOKEN, DOMAIN
from custom_components.moen_smart_water_network.moen_api.const import (
    API_BASE_URL_V1,
    API_BASE_URL_V3,
    API_USER_URL,
    LAMBDA_INVOKE_URL,
    OAUTH_URL,
)

FIXTURES = Path(__file__).parent / "fixtures"

SUMP_PUMP_DUID = "nab-duid-0001"
SUMP_PUMP_CLIENT_ID = "100000001"
IRRIGATION_DUID = "hyd-duid-0001"
IRRIGATION_CLIENT_ID = "100000002"
FLO_DUIDS = ("flo-duid-0001", "flo-duid-0002")


def load_json(name: str) -> Any:
    """Load a JSON fixture (scrubbed responses captured from the live API)."""
    return json.loads((FIXTURES / name).read_text())


IRRIGATION_DEVICE: dict[str, Any] = {
    "duid": IRRIGATION_DUID,
    "clientId": IRRIGATION_CLIENT_ID,
    "nickname": "Smart Sprinkler Controller",
    "type": "hyd",
    "location": {"id": "location-0001"},
    "connected": True,
    "lastConnect": "2026-11-23T07:06:55.526Z",
    "connectivity": {"type": "wifi", "net": "TestNetwork", "rssi": -40},
    "firmware": {"version": "v1.0.6d", "upgradeUri": "example"},
    "powerSource": "ac",
    "irrigation": {
        "numZones": 2,
        "wateringState": {"running": False},
        "masterValveConnected": True,
        "wateringMode": "off",
        "rainSensor": {"connected": True, "type": "closed"},
        "flowSensor": {"connected": False},
        "zones": [
            {
                "id": f"{IRRIGATION_DUID}_1",
                "clientId": "1",
                "wired": True,
                "name": "Front Yard East",
                "enabled": True,
            },
            {
                "id": f"{IRRIGATION_DUID}_8",
                "clientId": "8",
                "wired": False,
                "name": "Zone 8",
                "enabled": True,
            },
        ],
    },
}

FLO_DEVICES: list[dict[str, Any]] = [
    {
        "duid": duid,
        "clientId": duid,
        "nickname": name,
        "type": "flo",
        "location": {"id": "location-0001"},
        "meta": {"warnings": ["firmware_properties_missing"]},
        "boardType": "FLO_1_0",
        "alertsDigest": {"total": 0},
    }
    for duid, name in zip(
        FLO_DUIDS, ("Inside Flo Valve", "Outside Flo Valve"), strict=True
    )
]


class FakeMoenCloud:
    """In-memory stand-in for the Moen REST + Lambda invoker APIs."""

    def __init__(self) -> None:
        """Initialize with the captured sump pump responses."""
        self.shadow: dict[str, Any] = load_json("sump_pump_shadow.json")
        self.environment: Any = load_json("sump_pump_environment.json")
        self.last_usage: Any = load_json("sump_pump_last_usage.json")
        self.sessions: Any = load_json("sump_pump_sessions.json")
        self.capacity: Any = load_json("sump_pump_capacity.json")
        self.firmware: Any = load_json("sump_pump_firmware.json")
        self.legacy_sump_pump: Any = load_json("sump_pump_legacy_device.json")
        self.alerts: list[dict[str, Any]] = []
        self.invocations: list[tuple[str, dict[str, Any]]] = []
        self.failing: set[str] = set()

    def set_droplet(self, **droplet: Any) -> None:
        """Replace the shadow's water level block."""
        self.shadow["state"]["reported"]["droplet"] = droplet

    def commands(self) -> list[str]:
        """Return the crockCommands sent so far."""
        return [
            body["payload"]["crockCommand"]
            for fn, body in self.invocations
            if fn == "smartwater-app-shadow-api-prod-update"
        ]

    def _result(self, fn: str) -> tuple[Any, bool]:
        """Return (result, parsed) for a Lambda function."""
        routes: dict[str, tuple[Any, bool]] = {
            "smartwater-app-device-api-prod-list": ([self.legacy_sump_pump], False),
            "smartwater-app-shadow-api-prod-get": (copy.deepcopy(self.shadow), False),
            "smartwater-app-shadow-api-prod-update": ({"status": True}, True),
            "fbgpg_usage_v1_get_device_environment_latest_prod": (
                self.environment,
                False,
            ),
            "fbgpg_usage_v1_get_last_usage_prod": (self.last_usage, False),
            "fbgpg_usage_v1_get_my_usage_device_history_prod": (self.sessions, True),
            "fbgpg_usage_v1_get_my_usage_device_history_top10_prod": (
                self.capacity,
                False,
            ),
            "fbgpg_device_v1_device_get_latest_firmware_prod": (self.firmware, False),
            "fbgpg_alerts_v2_get_alerts_active_by_user_prod": (
                {"alerts": self.alerts},
                False,
            ),
        }
        return routes[fn]

    async def invoker(self, method, url, data) -> AiohttpClientMockResponse:
        """Answer a Lambda invoker POST, wrapped the way the real API does."""
        fn = data["fn"]
        self.invocations.append((fn, data["body"]))
        if fn in self.failing:
            payload: Any = {
                "errorType": "DatabaseException",
                "errorMessage": "Database error during get device ownership",
            }
        else:
            result, parsed = self._result(fn)
            payload = (
                result if parsed else {"statusCode": 200, "body": json.dumps(result)}
            )
        return AiohttpClientMockResponse(
            method, url, json={"StatusCode": 200, "Payload": payload}
        )


@pytest.fixture
def moen_cloud(aioclient_mock: AiohttpClientMocker) -> FakeMoenCloud:
    """Register the Moen API mocks for an account with 2 Flo valves, 1 sump pump and 1 sprinkler."""
    cloud = FakeMoenCloud()
    sump_pump_v3 = load_json("v3_device_sump_pump.json")
    aioclient_mock.get(
        f"{API_BASE_URL_V3}/devices",
        json={
            "count": 4,
            "devices": [*FLO_DEVICES, sump_pump_v3, IRRIGATION_DEVICE],
            "total": 4,
        },
    )
    aioclient_mock.get(API_USER_URL, json={"legacyId": "us-east-2:legacy"})
    aioclient_mock.post(f"{API_BASE_URL_V1}/user/me/presence", json={})
    aioclient_mock.get(
        f"{API_BASE_URL_V3}/device/{IRRIGATION_DUID}", json=IRRIGATION_DEVICE
    )
    aioclient_mock.get(
        f"{API_BASE_URL_V3}/irrigation/schedules", json={"items": [], "total": 0}
    )
    aioclient_mock.post(
        OAUTH_URL,
        json={
            "token": {"access_token": "access", "id_token": "id", "expires_in": 3600}
        },
    )
    aioclient_mock.post(LAMBDA_INVOKE_URL, side_effect=cloud.invoker)
    return cloud


@pytest.fixture(autouse=True)
def mock_mqtt():
    """Never open real AWS IoT connections in tests."""
    with patch("custom_components.moen_smart_water_network.MoenMqttClient") as mqtt_cls:
        instance = MagicMock()
        instance.async_run = AsyncMock()
        mqtt_cls.return_value = instance
        yield mqtt_cls


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
