"""Moen API Client."""
from __future__ import annotations

import asyncio
import datetime
import logging
import socket
from typing import Optional
from uuid import uuid4

import aiohttp
import async_timeout
import jwt
from aiohttp import ClientSession
from awscrt import auth, io, mqtt
from awsiot import iotshadow, mqtt_connection_builder

API_BASE_URL = "https://api.prod.iot.moen.com/v3"
API_USER_URL = "https://4j1gkf0vji.execute-api.us-east-2.amazonaws.com/prod/v1/users/me"

LAMBDA_INVOKE_URL = (
    "https://exo9f857n8.execute-api.us-east-2.amazonaws.com/prod/v1/invoker"
)

OAUTH_URL = (
    "https://4j1gkf0vji.execute-api.us-east-2.amazonaws.com/prod/v1/oauth2/token"
)

OAUTH_CLIENT_ID = "6qn9pep31dglq6ed4fvlq6rp5t"

COGNITO_ENDPOINT = "cognito-identity.us-east-2.amazonaws.com"

MQTT_REGION = "us-east-2"
MQTT_ENDPOINT = "a1r2q5ic87novc-ats.iot.us-east-2.amazonaws.com"

_LOGGER = logging.getLogger(__name__)


class ApiClientError(Exception):
    """Exception to indicate a general API error."""


class ApiClientCommunicationError(ApiClientError):
    """Exception to indicate a communication error."""


class ApiClientAuthenticationError(ApiClientError):
    """Exception to indicate an authentication error."""


class ApiClient:
    """Moen API Client."""

    def __init__(
        self,
        # username: str,
        # password: str,
        access_token: str,
        refresh_token: str,
        session: Optional[ClientSession] = None,
    ) -> None:
        """Moen API Client."""
        # self._username = username
        # self._password = password
        self._session: ClientSession = session
        self._token: Optional[str] = access_token
        self._refresh_token: Optional[str] = refresh_token
        self._token_expiration: Optional[datetime] = None
        self._id_token: str = None

    async def async_subscribe(self, client_id, callback) -> any:
        """Subscribe to shadow data"""
        user = await self.async_get_user()

        legacy_id = user["legacyId"]
        vals = jwt.decode(self._token, options={"verify_signature": False})

        iss = vals["iss"].removeprefix("https://")

        # credentials_provider = auth.AwsCredentialsProvider.new_cognito(
        #     endpoint=COGNITO_ENDPOINT,
        #     identity=legacy_id,
        #     logins=[(iss, self._id_token)],
        #     tls_ctx=io.ClientTlsContext(io.TlsContextOptions()),
        # )
        def credentials_factory():
            # I expect this to be printed every time aws-crt needs to renew the credentials:
            _LOGGER.debug("credentials_factory was called!")
            cog = auth.AwsCredentialsProvider.new_cognito(
                endpoint=COGNITO_ENDPOINT,
                identity=legacy_id,
                logins=[(iss, self._id_token)],
                tls_ctx=io.ClientTlsContext(io.TlsContextOptions()),
            )

            f = cog.get_credentials()
            return f.result()

        credentials_provider = auth.AwsCredentialsProvider.new_delegate(
            credentials_factory
        )
        mqtt_connection = mqtt_connection_builder.websockets_with_default_aws_signing(
            region=MQTT_REGION,
            endpoint=MQTT_ENDPOINT,
            credentials_provider=credentials_provider,
            client_id=str(uuid4()),
            clean_session=False,
            keep_alive_secs=30,
            on_connection_interrupted=lambda connection, error, **kwargs: _LOGGER.debug(
                "connection interrupted: %s", error
            ),
            on_connection_failure=lambda connection, callback_data: _LOGGER.error(
                "connection failure: %s", callback_data
            ),
            on_connection_resumed=lambda connection, return_code, session_present: _LOGGER.debug(
                "connection resumed: %s", return_code
            ),
            on_connection_success=lambda connection, callback_data: _LOGGER.debug(
                "connection success: %s", callback_data
            ),
            on_connection_closed=lambda connection, callback_data: _LOGGER.debug(
                "connection closed: %s", callback_data
            ),
        )

        connected_future = mqtt_connection.connect()

        shadow_client = iotshadow.IotShadowClient(mqtt_connection)

        connected_future.result()
        _LOGGER.debug("connected to mqtt")

        def on_message_received(topic, payload, **kwargs):
            _LOGGER.debug("Received message on topic '%s': %s", topic, payload)

        subscribe_future, _ = mqtt_connection.subscribe(
            topic=f"iot/HYD/{client_id}/subscription",
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_message_received,
        )

        subscribe_future.result()

        _LOGGER.debug("Subscribing to Update responses...")
        (
            update_accepted_subscribed_future,
            _,
        ) = shadow_client.subscribe_to_update_shadow_accepted(
            request=iotshadow.UpdateShadowSubscriptionRequest(thing_name=client_id),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=callback,
        )

        # Wait for subscriptions to succeed
        update_accepted_subscribed_future.result()

        _LOGGER.debug("Subscribing to Get responses...")
        (
            get_accepted_subscribed_future,
            _,
        ) = shadow_client.subscribe_to_get_shadow_accepted(
            request=iotshadow.GetShadowSubscriptionRequest(thing_name=client_id),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=callback,
        )

        # Wait for subscriptions to succeed
        get_accepted_subscribed_future.result()

        publish_get_future = shadow_client.publish_get_shadow(
            request=iotshadow.GetShadowRequest(
                thing_name=client_id  # , client_token=token
            ),
            qos=mqtt.QoS.AT_LEAST_ONCE,
        )
        publish_get_future.result()

        while True:
            await asyncio.sleep(3)

    async def async_refresh_token(self) -> None:
        """Refresh tokens from the API."""
        _LOGGER.debug("Requesting new access token")
        auth_response: dict = await self._api_wrapper(
            method="post",
            url=OAUTH_URL,
            data={
                "client_id": OAUTH_CLIENT_ID,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
            auth_request=True,
        )

        _LOGGER.debug(
            "Received new access token",
        )
        self._token = auth_response["token"]["access_token"]
        self._token_expiration = datetime.datetime.now() + datetime.timedelta(
            seconds=auth_response["token"]["expires_in"]
        )
        self._id_token = auth_response["token"]["id_token"]

    async def async_get_alerts(self) -> any:
        """Get alerts from the API."""
        return await self._request_with_refresh(
            method="get", url=API_BASE_URL + "/events/alerts"
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
        """Get data from the API."""
        return await self._request_with_refresh(method="get", url=API_USER_URL)

    async def async_get_devices(self) -> dict:
        """Get devices from the API."""
        return await self._request_with_refresh(
            method="get", url=f"{API_BASE_URL}/devices"
        )

    async def async_get_device(self, device_id: str) -> dict:
        """Get devices from the API."""
        return await self._request_with_refresh(
            method="get",
            url=f"{API_BASE_URL}/device/{device_id}",
            params={"expand": "addons"},
        )

    async def async_get_schedules(self, device_id: str) -> dict:
        """Get data from the API."""
        return await self._request_with_refresh(
            method="get",
            url=f"{API_BASE_URL}/irrigation/schedules",
            params={"duid": device_id, "type": "scheduled"},
        )

    async def async_manual_run(self, device_id: str, name: str, zones: dict) -> dict:
        """Start a manual run"""
        data = {"duid": device_id, "ttl": 0, "zones": zones, "name": name}
        return await self._request_with_refresh(
            method="post", url=f"{API_BASE_URL}/irrigation/manual", data=data
        )

    async def _request_with_refresh(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
    ) -> Optional[any]:
        """
        Wrapper around _request, to refresh tokens if needed.
        If an ExpiredTokenError is seen call refresh_tokens and
        try one more time. Otherwise, send the results up
        """
        response = None
        refreshed = False
        for _ in range(0, 2):
            try:
                response = await self._api_wrapper(
                    method=method,
                    url=url,
                    data=data,
                    params=params,
                )
            except ApiClientAuthenticationError:
                if not refreshed:
                    # Refresh tokens and try again
                    await self.async_refresh_token()
                    refreshed = True
                    continue

                # Send the exception up the stack otherwise
                raise

            # Success, fall out of the loop
            break

        return response

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
        auth_request: bool = False,
    ) -> any:
        """Get information from the API."""
        # Add authorization header to headers dict
        # if self._token_expiration and datetime.now() >= self._token_expiration:
        #     _LOGGER.info("Requesting new access token to replace expired one")

        #     # Nullify the token so that the authentication request doesn't use it:
        #     self._token = None

        #     # Nullify the expiration so the authentication request doesn't get caught
        #     # here:
        #     self._token_expiration = None

        #     await self.async_refresh_token()
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Moen/3 CFNetwork/1408.0.4 Darwin/22.5.0",
        }
        if not auth_request:
            headers = {
                "Authorization": f"Bearer {self._token}",
            }

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
                    raise ApiClientAuthenticationError(
                        "Invalid credentials",
                    )

                response.raise_for_status()
                return await response.json()

        except asyncio.TimeoutError as exception:
            raise ApiClientCommunicationError(
                f"Timeout error fetching information from {url}: {exception}"
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise ApiClientCommunicationError(
                f"Error fetching information from {url}: {exception}",
            ) from exception
        # except Exception as exception:  # pylint: disable=broad-except
        #     raise ApiClientError("Something really wrong happened!") from exception
