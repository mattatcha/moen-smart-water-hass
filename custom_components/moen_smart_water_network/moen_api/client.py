"""REST API client for Moen Smart Water Network."""

from __future__ import annotations

import json
import logging
import socket
from typing import TYPE_CHECKING, Any

import aiohttp
import async_timeout

from .const import (
    API_BASE_URL_V1,
    API_BASE_URL_V3,
    API_USER_URL,
    FN_ALERTS_ACTIVE,
    FN_DEVICE_LIST,
    FN_LATEST_FIRMWARE,
    FN_SHADOW_GET,
    FN_SHADOW_UPDATE,
    FN_SUMP_PUMP_CAPACITY,
    FN_SUMP_PUMP_ENVIRONMENT,
    FN_SUMP_PUMP_LAST_USAGE,
    FN_SUMP_PUMP_SESSIONS,
    LAMBDA_INVOKE_URL,
    SUMP_PUMP_COMMANDS,
)
from .exceptions import (
    MoenApiAuthenticationError,
    MoenApiCommunicationError,
    MoenApiError,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from .auth import MoenAuth
    from .models import (
        ActiveAlert,
        DeviceData,
        DevicesResponse,
        IrrigationSchedulesResponse,
        IrrigationZoneDuration,
        ShadowDocument,
        SumpPumpCapacity,
        SumpPumpEnvironment,
        SumpPumpLastUsage,
        SumpPumpSession,
    )

_LOGGER = logging.getLogger(__name__)

HTTP_BAD_REQUEST = 400


def _maybe_json(value: Any) -> Any:
    """Decode a JSON string, returning the value unchanged if it isn't JSON."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def _raise_if_error(fn: str, value: Any) -> None:
    """Raise MoenApiError when an invoker payload reports a Lambda failure."""
    if not isinstance(value, dict):
        return
    if "errorType" in value:
        msg = f"{fn} failed: {value.get('errorType')}: {value.get('errorMessage')}"
        raise MoenApiError(msg)
    status = value.get("statusCode")
    if isinstance(status, int) and status >= HTTP_BAD_REQUEST:
        msg = f"{fn} failed with status {status}: {value.get('body')}"
        raise MoenApiError(msg)


def unwrap_invoker_response(fn: str, response: Any) -> Any:
    """
    Return the Lambda result from a Lambda-invoker response.

    The invoker wraps results as ``{"StatusCode", "Payload"}``. ``Payload`` may be
    a JSON string, and may itself wrap the result as ``{"statusCode", "body"}``
    with ``body`` as another JSON string. With ``parse=True`` the invoker
    returns the result directly as ``Payload``.
    """
    payload = (
        _maybe_json(response.get("Payload", response))
        if isinstance(response, dict)
        else response
    )
    _raise_if_error(fn, payload)
    if isinstance(payload, dict) and "body" in payload:
        body = _maybe_json(payload["body"])
        _raise_if_error(fn, body)
        return body
    return payload


class MoenApiClient:
    """REST API client for Moen Smart Water Network devices."""

    def __init__(self, auth: MoenAuth, session: ClientSession) -> None:
        """Initialize with auth manager and aiohttp session."""
        self._auth = auth
        self._session = session

    @property
    def auth(self) -> MoenAuth:
        """Return the auth manager."""
        return self._auth

    async def async_get_alerts(self) -> Any:
        """Get alerts from the API."""
        return await self._request_with_refresh(
            method="get", url=f"{API_BASE_URL_V3}/events/alerts"
        )

    async def async_app_shadow_get(self, client_id: str) -> ShadowDocument:
        """Get a device's AWS IoT shadow document via the Lambda invoker."""
        return await self._invoke(
            FN_SHADOW_GET,
            {"shadow": False, "locale": "en_US", "clientId": str(client_id)},
        )

    async def async_get_user(self) -> dict:
        """Get user data from the API."""
        return await self._request_with_refresh(method="get", url=API_USER_URL)

    async def async_user_presence(self, duration_seconds: int = 35) -> dict:
        """Send a presence update for the user."""
        return await self._request_with_refresh(
            method="post",
            url=f"{API_BASE_URL_V1}/user/me/presence",
            data={"durationSeconds": duration_seconds},
        )

    async def async_get_devices(self) -> DevicesResponse:
        """Get all devices from the API."""
        return await self._request_with_refresh(
            method="get", url=f"{API_BASE_URL_V3}/devices"
        )

    async def async_get_device(self, device_id: str) -> DeviceData:
        """Get a single device from the API."""
        return await self._request_with_refresh(
            method="get",
            url=f"{API_BASE_URL_V3}/device/{device_id}",
            params={"expand": "addons"},
        )

    async def async_get_irrigation_schedules(
        self, device_id: str
    ) -> IrrigationSchedulesResponse:
        """Get irrigation schedules for a device."""
        return await self._request_with_refresh(
            method="get",
            url=f"{API_BASE_URL_V3}/irrigation/schedules",
            params={"duid": device_id, "type": "scheduled"},
        )

    async def async_get_irrigation_schedule_summary(self, device_id: str) -> dict:
        """Get schedule summary for a device."""
        return await self._request_with_refresh(
            method="get",
            url=f"{API_BASE_URL_V3}/irrigation/schedules/summary",
            params={"duid": device_id},
        )

    async def async_create_irrigation_manual_plan(
        self,
        device_id: str,
        zones: list[IrrigationZoneDuration],
        name: str = "Manual Run",
    ) -> dict:
        """Create a manual irrigation plan (zones in the Moen app's format)."""
        data = {"duid": device_id, "zones": zones, "name": name, "ttl": 0}
        return await self._request_with_refresh(
            method="post", url=f"{API_BASE_URL_V3}/irrigation/manual", data=data
        )

    async def async_enable_irrigation_zone(self, device_id: str, zone_id: str) -> dict:
        """Enable a zone."""
        return await self._request_with_refresh(
            method="post",
            url=f"{API_BASE_URL_V3}/device/{device_id}/zone/{device_id}_{zone_id}",
            data={"enabled": True},
        )

    async def async_disable_irrigation_zone(self, device_id: str, zone_id: str) -> dict:
        """Disable a zone."""
        return await self._request_with_refresh(
            method="post",
            url=f"{API_BASE_URL_V3}/device/{device_id}/zone/{device_id}_{zone_id}",
            data={"enabled": False},
        )

    async def async_update_irrigation_zone(
        self, device_id: str, zone_id: str, data: dict
    ) -> dict:
        """Update zone configuration."""
        return await self._request_with_refresh(
            method="post",
            url=f"{API_BASE_URL_V3}/device/{device_id}/zone/{device_id}_{zone_id}",
            data=data,
        )

    # --- Lambda invoker (legacy app API, used for the sump pump monitor) ---

    async def async_get_legacy_devices(self) -> list[dict[str, Any]]:
        """List devices from the app API (includes federatedIdentity, pumpInfo)."""
        result = await self._invoke(FN_DEVICE_LIST, {"locale": "en_US"})
        return result if isinstance(result, list) else []

    async def async_get_sump_pump_environment(
        self, client_id: str, cognito_id: str | None
    ) -> SumpPumpEnvironment:
        """Get the latest temperature and humidity of a sump pump monitor."""
        return await self._invoke(
            FN_SUMP_PUMP_ENVIRONMENT,
            {
                "cognitoIdentityId": cognito_id or "",
                "pathParameters": {"duid": str(client_id), "deviceType": "NAB"},
            },
        )

    async def async_get_sump_pump_last_usage(self, client_id: str) -> SumpPumpLastUsage:
        """Get the last pump cycle summary and the estimated next cycle."""
        return await self._invoke(
            FN_SUMP_PUMP_LAST_USAGE,
            {"cognitoIdentityId": "", "duid": str(client_id), "locale": "en_US"},
        )

    async def async_get_sump_pump_sessions(
        self, client_id: str, cognito_id: str | None, limit: int = 1
    ) -> list[SumpPumpSession]:
        """Get per-cycle pump history, newest first."""
        result = await self._invoke(
            FN_SUMP_PUMP_SESSIONS,
            {
                "cognitoIdentityId": cognito_id or "",
                "duid": str(client_id),
                "type": "session",
                "limit": limit,
                "locale": "en_US",
            },
            parse=True,
            escape=True,
        )
        if isinstance(result, dict):
            return result.get("usage") or []
        return []

    async def async_get_sump_pump_capacity(
        self, client_id: str, cognito_id: str | None
    ) -> SumpPumpCapacity:
        """Get the primary pump capacity indicator and highest capacity days."""
        return await self._invoke(
            FN_SUMP_PUMP_CAPACITY,
            {"cognitoIdentityId": cognito_id or "", "duid": str(client_id)},
        )

    async def async_get_latest_firmware(self, client_id: str) -> dict[str, Any]:
        """Get the current and latest firmware versions for a device."""
        return await self._invoke(FN_LATEST_FIRMWARE, {"duid": str(client_id)})

    async def async_get_active_alerts_v2(self) -> list[ActiveAlert]:
        """Get all active alerts for the account (every device)."""
        result = await self._invoke(FN_ALERTS_ACTIVE, {})
        if isinstance(result, dict):
            return result.get("alerts") or []
        return []

    async def async_sump_pump_command(self, client_id: str, command: str) -> Any:
        """Send a streaming command (drop_on / updates_off) to a sump pump monitor."""
        if command not in SUMP_PUMP_COMMANDS:
            msg = f"Unsupported sump pump command: {command}"
            raise ValueError(msg)
        return await self._invoke(
            FN_SHADOW_UPDATE,
            {"clientId": str(client_id), "payload": {"crockCommand": command}},
            parse=True,
            escape=True,
        )

    async def _invoke(
        self,
        fn: str,
        body: dict[str, Any],
        *,
        parse: bool = False,
        escape: bool = False,
    ) -> Any:
        """Call a Lambda function through the invoker and unwrap its result."""
        response = await self._request_with_refresh(
            method="post",
            url=LAMBDA_INVOKE_URL,
            data={"fn": fn, "parse": parse, "escape": escape, "body": body},
        )
        return unwrap_invoker_response(fn, response)

    async def _request_with_refresh(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
    ) -> Any:
        """Make a request, refreshing auth tokens on 401/403."""
        refreshed = False
        for _ in range(2):
            try:
                return await self._api_wrapper(
                    method=method, url=url, data=data, params=params
                )
            except MoenApiAuthenticationError:
                if not refreshed:
                    await self._auth.async_refresh_token()
                    refreshed = True
                    continue
                raise
        return None  # unreachable, satisfies type checker

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
    ) -> Any:
        """Make a raw API request with current auth headers."""
        headers = self._auth.get_auth_headers()

        _LOGGER.debug("Making request to %s: params: %s \nbody: %s", url, params, data)

        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params,
                )
                if response.status in (401, 403):
                    msg = "Invalid credentials"
                    raise MoenApiAuthenticationError(msg)

                response.raise_for_status()
                return await response.json(content_type=None)

        except TimeoutError as exception:
            msg = f"Timeout error fetching information from {url}: {exception}"
            raise MoenApiCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information from {url}: {exception}"
            raise MoenApiCommunicationError(msg) from exception
