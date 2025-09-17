"""Library-specific exceptions for pybragerone."""


class PybrageroneError(Exception):
    """Base exception for pybragerone."""


class BadRequest(PybrageroneError):
    """HTTP 400 or invalid request to the backend."""


class Unauthorized(PybrageroneError):
    """Authentication required or invalid credentials."""


class Forbidden(PybrageroneError):
    """Forbidden by backend (HTTP 403)."""


class NotFound(PybrageroneError):
    """Requested resource was not found (HTTP 404)."""


class ServerError(PybrageroneError):
    """5xx errors from backend."""


class NetworkError(PybrageroneError):
    """Networking error (connection reset, DNS, etc.)."""


class Timeout(PybrageroneError):
    """Network timeout."""


class NotConnected(PybrageroneError):
    """Operation requires an active connection (REST or WS)."""


class ParseError(PybrageroneError):
    """Frontend asset parse error."""
