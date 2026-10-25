"""Domain-specific exceptions."""


class DomainException(Exception):
    """Base domain exception."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EntityNotFoundException(DomainException):
    """Raised when an entity is not found in the domain."""


class BusinessRuleViolationException(DomainException):
    """Raised when a business rule constraint is violated."""
