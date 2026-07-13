"""Custom exceptions for the API."""


class EnvironmentVariableNotFoundError(Exception):
    """Exception raised when an environment variable is not found."""

    def __init__(self, varname: str) -> None:
        """Initialise the exception."""
        super().__init__(f"Environment variable {varname} not found.")


class BadEnvironmentError(Exception):
    """Exception raised when the environment is not set correctly."""

    def __init__(self, current_environment: str, allowed_environments: set[str]) -> None:
        """Initialise the exception."""
        super().__init__(
            f"Environment {current_environment} not allowed. "
            f"Allowed environments are {allowed_environments}."
        )


class BadDBTypeError(Exception):
    """Exception raised when the DB_TYPE is not set correctly."""

    def __init__(self, db_type: str, allowed_types: set[str]) -> None:
        """Initialise the exception."""
        super().__init__(f"DB_TYPE {db_type} not allowed. Allowed types are {allowed_types}.")


class ModelNotHavingAttributeError(Exception):
    """Exception raised when the model does not have the requested attribute."""

    def __init__(self, model_name: str, attribute: str) -> None:
        """Initialise the exception."""
        super().__init__(f"Model {model_name} does not have attribute {attribute}.")


class InvalidProductTypeError(ValueError):
    """Exception raised when an invalid product type is provided."""

    def __init__(self, product_type: str) -> None:
        """Initialise the exception."""
        super().__init__(
            f"Invalid product_type: '{product_type}'. Product type not found in database."
        )


class InvalidProductLocationError(ValueError):
    """Exception raised when an invalid product location is provided."""

    def __init__(self, product_location: str) -> None:
        """Initialise the exception."""
        super().__init__(
            f"Invalid product_location: '{product_location}'. Product location not found in database."
        )


class InvalidExpiryDateError(ValueError):
    """Exception raised when expiry date is invalid."""

    def __init__(self, message: str) -> None:
        """Initialise the exception."""
        super().__init__(message)
