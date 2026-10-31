"""Application error types shared across modules."""


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""

    def __init__(self, message: str, *, code: str = "config_error") -> None:
        super().__init__(message)
        self.code = code
