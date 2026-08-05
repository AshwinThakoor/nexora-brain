class ServiceError(Exception):
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class ResourceNotFoundError(ServiceError):
    def __init__(self, resource: str, resource_id: object):
        super().__init__(f"{resource} {resource_id} was not found")


class ResourceConflictError(ServiceError):
    """Raised when a requested state conflicts with existing data."""


class ResourceValidationError(ServiceError):
    """Raised when a business rule rejects otherwise valid input."""


class AcademyInputError(ServiceError):
    """Raised for a syntactically valid Academy request with invalid input."""


class AuthenticationRequiredError(ServiceError):
    """Raised when an Academy route has no usable request principal."""


class AuthorizationDeniedError(ServiceError):
    """Raised when an authenticated principal lacks resource access."""
