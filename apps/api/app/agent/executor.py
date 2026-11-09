"""Runs an action once. Retries return the stored result and never call the provider again."""
from dataclasses import dataclass
from typing import Protocol

from app.agent.policy_engine import Action, Approval, Context, Policy, execution_guard


class Provider(Protocol):
    def execute(self, action: Action, idempotency_key: str) -> dict: ...


@dataclass
class Result:
    status: str  # BLOCKED, CONFIRMED, FAILED, UNCLEAR
    detail: str = ""
    provider_response: dict | None = None


class ExecutionStore:
    """In-memory for now. Phase 1 replaces it with a PostgreSQL table with a unique key."""

    def __init__(self) -> None:
        self._done: dict[str, Result] = {}

    def get(self, key: str) -> Result | None:
        return self._done.get(key)

    def put(self, key: str, result: Result) -> None:
        self._done[key] = result


def idempotency_key(a: Action) -> str:
    return f"{a.tenant_id}:{a.channel}:{a.kind}:{a.content_hash}:{a.version}:{a.scheduled_at.isoformat()}"


def run_action(policy: Policy, action: Action, approval: Approval | None, ctx: Context,
               provider: Provider, store: ExecutionStore) -> Result:
    decision = execution_guard(policy, action, approval, ctx)
    if not decision.allowed:
        return Result("BLOCKED", decision.reason)
    key = idempotency_key(action)
    previous = store.get(key)
    if previous is not None and previous.status in {"CONFIRMED", "UNCLEAR"}:
        return previous
    try:
        response = provider.execute(action, key)
    except Exception as exc:  # provider error: record it, never report success
        result = Result("FAILED", str(exc))
        store.put(key, result)
        return result
    # Only a response the provider marks as confirmed counts as success.
    if isinstance(response, dict) and response.get("confirmed") is True:
        result = Result("CONFIRMED", "provider confirmed", response)
    else:
        result = Result("UNCLEAR", "provider did not confirm; reconciliation required", response)
    store.put(key, result)
    return result
