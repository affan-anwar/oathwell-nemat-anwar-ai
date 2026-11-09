"""Role and permission model. Every API route checks a permission, never a role name.
Deny by default: a role has only the permissions listed here."""

# Permissions the Owner may switch off for Admins (delegated management).
DELEGABLE = ["approval.decide", "integration.manage", "member.manage", "automation.pause", "audit.read", "events.manage"]
OWNER_ONLY = ["theme.write", "admin.delegate", "role.manage_privileged", "credentials.revoke", "emergency.shutdown", "ai.manage"]

_EDITOR = {"read", "content.write", "campaign.write", "approval.request", "publish.execute", "brand.write", "events.plan"}
ROLE_PERMS = {
    "viewer": {"read"},
    # Specialised agents: least privilege, each controlled separately.
    "research_agent": {"read", "research.write"},
    "analytics_agent": {"read", "analytics.sync"},
    "content_agent": {"read", "content.write"},
    "publishing_agent": {"read", "publish.execute"},
    # Orchestrator: plans and drafts and may request approval. It can never approve, publish, connect accounts or manage people.
    "super_agent": {"read", "content.write", "campaign.write", "approval.request", "events.plan", "research.write", "analytics.sync"},
    "editor": set(_EDITOR),
    "admin": _EDITOR | set(DELEGABLE) | {"research.write", "analytics.sync"},
}
# The Owner holds every permission that exists, including the ones only the Owner may have.
ROLE_PERMS["owner"] = set().union(*ROLE_PERMS.values()) | set(OWNER_ONLY)
ROLES = list(ROLE_PERMS)
ASSIGNABLE = [r for r in ROLES if r != "owner"]  # nobody can be made an owner through the API
ADMIN_MANAGEABLE = {"viewer", "editor", "research_agent", "analytics_agent", "content_agent", "publishing_agent"}
LABELS = {"owner": "Owner", "admin": "Admin", "super_agent": "Super Agent", "editor": "Editor", "viewer": "Viewer",
          "research_agent": "Research Agent", "content_agent": "Content Agent", "analytics_agent": "Analytics Agent", "publishing_agent": "Publishing Agent"}


def has_perm(role: str, perm: str, admin_revoked=None) -> bool:
    if role == "admin" and perm in (admin_revoked or []):
        return False
    return perm in ROLE_PERMS.get(role, set())


def effective_perms(role: str, admin_revoked=None) -> list[str]:
    return sorted(p for p in ROLE_PERMS.get(role, set()) if has_perm(role, p, admin_revoked))


def can_assign(actor_role: str, target_current: str | None, new_role: str | None, admin_revoked=None) -> bool:
    """May `actor_role` create or change a member from `target_current` to `new_role`? (owner is never assignable)"""
    if target_current == "owner" or new_role == "owner":
        return False
    if actor_role == "owner":
        return True
    if actor_role == "admin" and has_perm("admin", "member.manage", admin_revoked):
        return (target_current is None or target_current in ADMIN_MANAGEABLE) and (new_role is None or new_role in ADMIN_MANAGEABLE)
    return False
