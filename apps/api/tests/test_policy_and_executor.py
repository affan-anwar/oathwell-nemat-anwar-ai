from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

from app.agent.executor import ExecutionStore, run_action
from app.agent.policy_engine import (Action, Approval, Context, Mode, Policy,
                                     execution_guard, submission_route)

NOW = datetime(2026, 10, 16, 12, 0)


def policy(**kw):
    base = dict(tenant_id="t1", modes={"blog": Mode.AUTO, "email": Mode.REVIEW, "ads": Mode.AUTO},
                max_actions_per_day=3, daily_spend_cap=Decimal("1500"))
    base.update(kw)
    return Policy(**base)


def action(channel="blog", kind="publish", **kw):
    base = dict(tenant_id="t1", channel=channel, kind=kind, content_hash="h1", version=1,
                scheduled_at=NOW + timedelta(hours=1))
    base.update(kw)
    return Action(**base)


def human(a, **kw):
    base = dict(tenant_id=a.tenant_id, channel=a.channel, kind=a.kind, content_hash=a.content_hash,
                version=a.version, source="human", approver_id="u1", expires_at=NOW + timedelta(days=1))
    base.update(kw)
    return Approval(**base)


def ctx(**kw):
    base = dict(now=NOW, channel_connected=True)
    base.update(kw)
    return Context(**base)


def test_routes():
    assert submission_route(policy(), action("blog")) == "auto_approve"
    assert submission_route(policy(), action("email", "send")) == "needs_review"
    assert submission_route(policy(), action("linkedin")) == "needs_review"  # default is Ask me first
    assert submission_route(policy(), action("ads", "spend")) == "needs_review"  # needs extra opt-in
    assert submission_route(policy(high_impact_auto_enabled=True), action("ads", "spend")) == "auto_approve"
    assert submission_route(policy(modes={"blog": Mode.OFF}), action("blog")) == "blocked"
    assert submission_route(policy(paused=True), action("blog")) == "blocked"


def test_no_approval_no_execution():
    assert not execution_guard(policy(), action(), None, ctx()).allowed


def test_human_approval_allows():
    a = action("email", "send")
    assert execution_guard(policy(), a, human(a), ctx()).allowed


def test_review_channel_rejects_policy_approval():
    a = action("email", "send")
    ap = human(a, source="policy", approver_id=None)
    assert not execution_guard(policy(), a, ap, ctx()).allowed


def test_policy_approval_valid_for_auto_channel():
    a = action("blog")
    ap = human(a, source="policy", approver_id=None)
    assert execution_guard(policy(), a, ap, ctx()).allowed


def test_policy_approval_stops_when_policy_changes():
    a = action("blog")
    ap = human(a, source="policy", approver_id=None)
    assert not execution_guard(policy(modes={"blog": Mode.REVIEW}), a, ap, ctx()).allowed


def test_edit_after_approval_invalidates():
    a = action()
    ap = human(a)
    assert not execution_guard(policy(), replace(a, content_hash="h2"), ap, ctx()).allowed
    assert not execution_guard(policy(), replace(a, version=2), ap, ctx()).allowed


def test_other_tenant_blocked():
    a = action()
    assert not execution_guard(policy(), replace(a, tenant_id="t2"), human(replace(a, tenant_id="t2")), ctx()).allowed
    assert not execution_guard(policy(), a, human(a, tenant_id="t2"), ctx()).allowed


def test_wrong_role_less_approval_blocked():
    a = action()
    assert not execution_guard(policy(), a, human(a, approver_id=None), ctx()).allowed


def test_expired_and_revoked():
    a = action()
    assert not execution_guard(policy(), a, human(a, expires_at=NOW), ctx()).allowed
    assert not execution_guard(policy(), a, human(a, revoked=True), ctx()).allowed


def test_pause_kill_switch_disconnect():
    a = action()
    ap = human(a)
    assert not execution_guard(policy(paused=True), a, ap, ctx()).allowed
    assert not execution_guard(policy(global_kill_switch=True), a, ap, ctx()).allowed
    assert not execution_guard(policy(), a, ap, ctx(channel_connected=False)).allowed


def test_limits_quiet_hours_consent():
    a = action()
    ap = human(a)
    assert not execution_guard(policy(), a, ap, ctx(actions_today=3)).allowed
    quiet = policy(quiet_hours=(22, 7))
    late = action(scheduled_at=datetime(2026, 10, 16, 23, 0))
    assert not execution_guard(quiet, late, human(late), ctx()).allowed
    early = action(scheduled_at=datetime(2026, 10, 17, 6, 0))
    assert not execution_guard(quiet, early, human(early), ctx()).allowed
    assert execution_guard(quiet, a, ap, ctx()).allowed
    e = action("email", "send")
    assert not execution_guard(policy(), e, human(e), ctx(consent_ok=False)).allowed


def test_spend_cap():
    a = action("ads", "spend", spend=Decimal("1000"))
    ap = human(a)
    p = policy(modes={"ads": Mode.REVIEW})
    assert execution_guard(p, a, ap, ctx(spend_today=Decimal("500"))).allowed
    assert not execution_guard(p, a, ap, ctx(spend_today=Decimal("600"))).allowed


class CountingProvider:
    def __init__(self, response):
        self.calls, self.response = 0, response

    def execute(self, action, key):
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_retry_does_not_duplicate():
    a = action()
    p, store, prov = policy(), ExecutionStore(), CountingProvider({"confirmed": True, "id": 7})
    r1 = run_action(p, a, human(a), ctx(), prov, store)
    r2 = run_action(p, a, human(a), ctx(), prov, store)
    assert r1.status == r2.status == "CONFIRMED" and prov.calls == 1


def test_blocked_never_calls_provider():
    a = action()
    prov = CountingProvider({"confirmed": True})
    r = run_action(policy(paused=True), a, human(a), ctx(), prov, ExecutionStore())
    assert r.status == "BLOCKED" and prov.calls == 0


def test_failure_is_recorded_not_success():
    a = action()
    prov = CountingProvider(RuntimeError("401 from provider"))
    r = run_action(policy(), a, human(a), ctx(), prov, ExecutionStore())
    assert r.status == "FAILED" and "401" in r.detail


def test_unconfirmed_response_is_not_success_and_not_repeated():
    a = action()
    store, prov = ExecutionStore(), CountingProvider({"ok": True})
    r1 = run_action(policy(), a, human(a), ctx(), prov, store)
    r2 = run_action(policy(), a, human(a), ctx(), prov, store)
    assert r1.status == "UNCLEAR" and r2.status == "UNCLEAR" and prov.calls == 1
