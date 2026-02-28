"""Exceptions for the Moen Smart Water Network API."""


class MoenApiError(Exception):
    """Exception to indicate a general API error."""


class MoenApiCommunicationError(MoenApiError):
    """Exception to indicate a communication error."""


class MoenApiAuthenticationError(MoenApiError):
    """Exception to indicate an authentication error."""
