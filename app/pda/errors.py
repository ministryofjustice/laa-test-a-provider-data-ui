class ProviderDataApiError(Exception):
    """Base exception for Provider Data API errors."""

    pass


class PDAError(ProviderDataApiError):
    """Base exception for Provider Data API errors."""

    pass


class PDAConnectionError(PDAError):
    """Raised when unable to connect to the Provider Data API."""

    pass


class PDACapabilityError(PDAError):
    """Raised when an operation is not currently supported by the configured Provider Data API."""

    pass


class ProviderDataApiHttpError(ProviderDataApiError):
    """HTTP-level error returned by the Provider Data API."""

    def __init__(self, status_code: int, detail: str | None = None, response_data=None):
        self.status_code = status_code
        self.detail = detail
        self.response_data = response_data
        message = detail or f"HTTP error {status_code}"
        super().__init__(message)
