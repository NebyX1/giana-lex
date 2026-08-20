class LegalDomainError(Exception):
    """Base error for legal case operations."""


class CaseNotFoundError(LegalDomainError):
    """The case does not exist or is not visible to the actor."""


class ConcurrentCaseUpdateError(LegalDomainError):
    """An optimistic lock rejected a stale case write."""


class InvalidCaseTransitionError(LegalDomainError):
    """The requested state edge is not in the transition table."""


class DuplicateCommandError(LegalDomainError):
    """A command violates its idempotency boundary."""


class WorkflowConflictError(LegalDomainError):
    """The workflow lifecycle does not permit the operation."""


class DraftVersionMismatchError(WorkflowConflictError):
    """A review targets a stale draft or review task."""
