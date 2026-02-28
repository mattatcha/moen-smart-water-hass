"""OAuth2 authentication and AWS Cognito credential management for Moen API."""

from __future__ import annotations

import datetime
import logging
import socket
from typing import Any

import aiohttp
import async_timeout
import jwt
from aiohttp import ClientSession
from awscrt import auth, io

from .const import COGNITO_ENDPOINT, OAUTH_CLIENT_ID, OAUTH_URL, USER_AGENT
from .exceptions import (
    MoenApiAuthenticationError,
    MoenApiCommunicationError,
)

_LOGGER = logging.getLogger(__name__)


class MoenAuth:
    """Manages OAuth2 tokens and AWS Cognito credentials for Moen API access."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        session: ClientSession,
    ) -> None:
        """Initialize with OAuth2 tokens."""
        self._session = session
        self._token = access_token
        self._refresh_token = refresh_token
        self._token_expiration: datetime.datetime | None = None
        self._id_token: str | None = None

    @property
    def access_token(self) -> str:
        """Return the current access token."""
        return self._token

    @property
    def id_token(self) -> str | None:
        """Return the current ID token."""
        return self._id_token

    async def async_refresh_token(self) -> None:
        """Refresh tokens from the OAuth2 endpoint."""
        _LOGGER.debug("Requesting new access token")
        auth_response: dict = await self._api_wrapper(
            method="post",
            url=OAUTH_URL,
            data={
                "client_id": OAUTH_CLIENT_ID,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
        )

        self._token = auth_response["token"]["access_token"]
        self._token_expiration = datetime.datetime.now(
            tz=datetime.UTC
        ) + datetime.timedelta(seconds=auth_response["token"]["expires_in"])
        self._id_token = auth_response["token"]["id_token"]

        _LOGGER.debug(
            "Received new access token that expires in %s at %s",
            auth_response["token"]["expires_in"],
            self._token_expiration,
        )

    async def async_ensure_token(self) -> None:
        """Refresh the token if it is expired or about to expire."""
        if self._token_expiration is None or datetime.datetime.now(
            tz=datetime.UTC
        ) >= self._token_expiration - datetime.timedelta(minutes=5):
            await self.async_refresh_token()

    def get_auth_headers(self) -> dict[str, str]:
        """Return Authorization headers using the current access token."""
        return {"Authorization": f"Bearer {self._token}"}

    def create_cognito_credentials_provider(
        self, legacy_id: str
    ) -> auth.AwsCredentialsProvider:
        """Create an AWS Cognito credentials provider for MQTT connections."""
        vals = jwt.decode(self._token, options={"verify_signature": False})
        iss = vals["iss"].removeprefix("https://")

        def credentials_factory() -> auth.AwsCredentials:
            _LOGGER.debug("credentials_factory was called")
            cog = auth.AwsCredentialsProvider.new_cognito(
                endpoint=COGNITO_ENDPOINT,
                identity=legacy_id,
                logins=[(iss, self._id_token)],
                tls_ctx=io.ClientTlsContext(io.TlsContextOptions()),
            )
            f = cog.get_credentials()
            return f.result()

        return auth.AwsCredentialsProvider.new_delegate(credentials_factory)

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
    ) -> Any:
        """Make an API request (used for auth-specific endpoints)."""
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": USER_AGENT,
        }

        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
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
