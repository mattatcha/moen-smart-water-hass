"""REST API client for Moen Smart Water Network."""

from __future__ import annotations

import logging
import socket
from typing import TYPE_CHECKING, Any

import aiohttp
import async_timeout

from .const import API_BASE_URL_V1, API_BASE_URL_V3, API_USER_URL, LAMBDA_INVOKE_URL
from .exceptions import (
    MoenApiAuthenticationError,
    MoenApiCommunicationError,
)

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from .auth import MoenAuth
    from .models import DeviceData, DevicesResponse, SchedulesResponse, ZoneDuration

_LOGGER = logging.getLogger(__name__)


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

    async def async_app_shadow_get(self, client_id: str) -> dict:
        """Get app shadow data."""
        return await self._request_with_refresh(
            method="post",
            url=LAMBDA_INVOKE_URL,
            data={
                "escape": False,
                "parse": False,
                "fn": "smartwater-app-shadow-api-prod-get",
                "body": {"shadow": False, "locale": "en_US", "clientId": client_id},
            },
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

    async def async_get_schedules(self, device_id: str) -> SchedulesResponse:
        """Get irrigation schedules for a device."""
        return await self._request_with_refresh(
            method="get",
            url=f"{API_BASE_URL_V3}/irrigation/schedules",
            params={"duid": device_id, "type": "scheduled"},
        )

    async def async_get_schedule_summary(self, device_id: str) -> dict:
        """Get schedule summary for a device."""
        return await self._request_with_refresh(
            method="get",
            url=f"{API_BASE_URL_V3}/irrigation/schedules/summary",
            params={"duid": device_id},
        )

    async def async_create_manual_plan(
        self, device_id: str, zones: list[ZoneDuration], name: str = "Manual Run"
    ) -> dict:
        """Create a manual irrigation plan using the APK ZoneDuration format."""
        data = {"duid": device_id, "zones": zones, "name": name, "ttl": 0}
        return await self._request_with_refresh(
            method="post", url=f"{API_BASE_URL_V3}/irrigation/manual", data=data
        )

    async def async_enable_zone(self, device_id: str, zone_id: str) -> dict:
        """Enable a zone."""
        return await self._request_with_refresh(
            method="post",
            url=f"{API_BASE_URL_V3}/device/{device_id}/zone/{device_id}_{zone_id}",
            data={"enabled": True},
        )

    async def async_disable_zone(self, device_id: str, zone_id: str) -> dict:
        """Disable a zone."""
        return await self._request_with_refresh(
            method="post",
            url=f"{API_BASE_URL_V3}/device/{device_id}/zone/{device_id}_{zone_id}",
            data={"enabled": False},
        )

    async def async_update_zone(self, device_id: str, zone_id: str, data: dict) -> dict:
        """Update zone configuration."""
        return await self._request_with_refresh(
            method="post",
            url=f"{API_BASE_URL_V3}/device/{device_id}/zone/{device_id}_{zone_id}",
            data=data,
        )

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
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information from {url}: {exception}"
            raise MoenApiCommunicationError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information from {url}: {exception}"
            raise MoenApiCommunicationError(msg) from exception
