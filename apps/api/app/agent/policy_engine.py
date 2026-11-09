"""Deterministic rules. The AI model never calls these to grant itself permission; the backend does."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

HIGH_IMPACT = frozenset({"email", "whatsapp", "sms", "ads"})


class Mode(str, Enum):
    AUTO = "AUTO"
    REVIEW = "REVIEW"  # "Ask me first"
    OFF = "OFF"


@dataclass(frozen=True)
class Policy:
    tenant_id: str
    modes: dict = field(default_factory=dict)  # channel -> Mode; missing channel means REVIEW
    paused: bool = False
    global_kill_switch: bool = False
    high_impact_auto_enabled: bool = False  # extra admin opt-in for email, whatsapp, sms, ads
    max_actions_per_day: int = 5
    daily_spend_cap: Decimal = Decimal("0")
    quiet_hours: tuple | None = None  # (start_hour, end_hour) in tenant local time

    def mode(self, channel: str) -> Mode:
        return self.modes.get(channel, Mode.REVIEW)


@dataclass(frozen=True)
class Action:
    tenant_id: str
    channel: str
    kind: str  # publish, send, spend
    content_hash: str
    version: int
    scheduled_at: datetime  # tenant local time
    spend: Decimal = Decimal("0")


@dataclass(frozen=True)
class Approval:
    tenant_id: str
    channel: str
    kind: str
    content_hash: str
    version: int
    source: str  # "human" or "policy"
    approver_id: str | None
    expires_at: datetime
    revoked: bool = False


@dataclass(frozen=True)
class Context:
    now: datetime
    actions_today: int = 0
    spend_today: Decimal = Decimal("0")
    channel_connected: bool = False
    consent_ok: bool = True


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def _in_quiet_hours(hours: tuple | None, when: datetime) -> bool:
    if not hours:
        return False
    start, end = hours
    h = when.hour
    return start <= h < end if start < end else (h >= start or h < end)


def submission_route(policy: Policy, action: Action) -> str:
    """Return 'blocked', 'needs_review' or 'auto_approve' for a validated draft."""
    if policy.global_kill_switch or policy.paused or action.tenant_id != policy.tenant_id:
        return "blocked"
    mode = policy.mode(action.channel)
    if mode is Mode.OFF:
        return "blocked"
    if mode is Mode.AUTO and (action.channel not in HIGH_IMPACT or policy.high_impact_auto_enabled):
        return "auto_approve"
    return "needs_review"


def execution_guard(policy: Policy, action: Action, approval: Approval | None, ctx: Context) -> Decision:
    """Run immediately before every external action. First failed check blocks it."""
    no = lambda r: Decision(False, r)
    if policy.global_kill_switch:
        return no("global kill switch is on")
    if policy.paused:
        return no("tenant is paused")
    if action.tenant_id != policy.tenant_id:
        return no("tenant mismatch")
    mode = policy.mode(action.channel)
    if mode is Mode.OFF:
        return no("channel is off")
    if not ctx.channel_connected:
        return no("channel is not connected")
    if approval is None:
        return no("no approval")
    if approval.tenant_id != action.tenant_id:
        return no("approval belongs to another tenant")
    if (approval.channel, approval.kind) != (action.channel, action.kind):
        return no("approval is for a different action")
    if approval.content_hash != action.content_hash or approval.version != action.version:
        return no("content changed after approval")
    if approval.revoked:
        return no("approval revoked")
    if ctx.now >= approval.expires_at:
        return no("approval expired")
    if approval.source == "policy":
        if submission_route(policy, action) != "auto_approve":
            return no("policy no longer allows automatic action")
    elif approval.source != "human" or not approval.approver_id:
        return no("approval has no valid approver")
    if action.channel == "email" and not ctx.consent_ok:
        return no("subscriber consent missing")
    if ctx.actions_today >= policy.max_actions_per_day:
        return no("daily action limit reached")
    if ctx.spend_today + action.spend > policy.daily_spend_cap and action.spend > 0:
        return no("daily spend cap would be exceeded")
    if _in_quiet_hours(policy.quiet_hours, action.scheduled_at):
        return no("inside quiet hours")
    return Decision(True, "ok")
