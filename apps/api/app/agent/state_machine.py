"""Status flow for every external marketing action. Only listed moves are allowed."""
from enum import Enum


class Status(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    EXECUTING = "EXECUTING"
    PUBLISHED = "PUBLISHED"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


S = Status
ALLOWED: dict[Status, frozenset[Status]] = {
    S.DRAFT: frozenset({S.VALIDATING, S.CANCELLED}),
    S.VALIDATING: frozenset({S.PENDING_APPROVAL, S.APPROVED, S.DRAFT, S.CANCELLED}),
    S.PENDING_APPROVAL: frozenset({S.APPROVED, S.REJECTED, S.CHANGES_REQUESTED, S.EXPIRED, S.CANCELLED}),
    S.CHANGES_REQUESTED: frozenset({S.DRAFT, S.CANCELLED}),
    S.APPROVED: frozenset({S.SCHEDULED, S.EXECUTING, S.DRAFT, S.CANCELLED, S.EXPIRED}),
    S.SCHEDULED: frozenset({S.EXECUTING, S.DRAFT, S.CANCELLED, S.EXPIRED}),
    S.EXECUTING: frozenset({S.PUBLISHED, S.SENT, S.FAILED, S.RECONCILIATION_REQUIRED}),
    S.FAILED: frozenset({S.SCHEDULED, S.CANCELLED}),
    S.RECONCILIATION_REQUIRED: frozenset({S.PUBLISHED, S.SENT, S.FAILED, S.CANCELLED}),
    S.REJECTED: frozenset(),
    S.PUBLISHED: frozenset(),
    S.SENT: frozenset(),
    S.CANCELLED: frozenset(),
    S.EXPIRED: frozenset(),
}


class InvalidTransition(Exception):
    pass


def can_transition(current: Status, new: Status) -> bool:
    return new in ALLOWED[current]


def transition(current: Status, new: Status) -> Status:
    if not can_transition(current, new):
        raise InvalidTransition(f"{current.value} -> {new.value} is not allowed")
    return new
