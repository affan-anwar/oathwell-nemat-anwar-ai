import pytest
from app.agent.state_machine import InvalidTransition, Status as S, can_transition, transition


def test_valid_path():
    s = S.DRAFT
    for nxt in [S.VALIDATING, S.PENDING_APPROVAL, S.APPROVED, S.SCHEDULED, S.EXECUTING, S.PUBLISHED]:
        s = transition(s, nxt)
    assert s is S.PUBLISHED


def test_cannot_skip_approval():
    assert not can_transition(S.DRAFT, S.EXECUTING)
    assert not can_transition(S.PENDING_APPROVAL, S.EXECUTING)
    with pytest.raises(InvalidTransition):
        transition(S.DRAFT, S.PUBLISHED)


def test_terminal_states_are_final():
    for t in [S.REJECTED, S.PUBLISHED, S.SENT, S.CANCELLED, S.EXPIRED]:
        assert all(not can_transition(t, n) for n in S)


def test_failed_is_never_success():
    assert not can_transition(S.FAILED, S.PUBLISHED)
    assert can_transition(S.EXECUTING, S.RECONCILIATION_REQUIRED)


def test_approved_content_edit_goes_back_to_draft():
    assert can_transition(S.APPROVED, S.DRAFT)
    assert can_transition(S.SCHEDULED, S.DRAFT)
