import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.permissions import ROLES


def uid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC everywhere


class Base(DeclarativeBase):
    pass


def pk():
    return mapped_column(String(36), primary_key=True, default=uid)


def fk(table: str, nullable=False):
    return mapped_column(String(36), ForeignKey(f"{table}.id"), index=True, nullable=nullable)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    full_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = pk()
    name: Mapped[str] = mapped_column(String(200))
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    admin_revoked: Mapped[list | None] = mapped_column(JSON, default=list)  # permissions the Owner withdrew from Admins
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),
                      CheckConstraint("role in (" + ",".join(f"'{r}'" for r in ROLES) + ")", name="ck_membership_role"))
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = fk("workspaces")
    user_id: Mapped[str] = fk("users")
    role: Mapped[str] = mapped_column(String(20))  # see app/core/permissions.py
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    theme_mode: Mapped[str | None] = mapped_column(String(10))  # this user's own dark/light/system choice in this workspace
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), primary_key=True)
    business_name: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(500))
    industry: Mapped[str | None] = mapped_column(String(120))
    products: Mapped[str | None] = mapped_column(Text)
    target_audience: Mapped[str | None] = mapped_column(Text)
    market: Mapped[str | None] = mapped_column(String(200))
    languages: Mapped[list] = mapped_column(JSON, default=list)
    brand_voice: Mapped[str | None] = mapped_column(Text)
    guidelines: Mapped[str | None] = mapped_column(Text)
    approved_claims: Mapped[str | None] = mapped_column(Text)
    prohibited_claims: Mapped[str | None] = mapped_column(Text)
    competitors: Mapped[list] = mapped_column(JSON, default=list)
    objectives: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str | None] = mapped_column(String(3))
    budget_limit: Mapped[float | None] = mapped_column(Numeric(12, 2))
    channels: Mapped[list] = mapped_column(JSON, default=list)
    timezone: Mapped[str | None] = mapped_column(String(64))
    occasions: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = fk("workspaces")
    name: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str | None] = mapped_column(Text)
    channels: Mapped[list] = mapped_column(JSON, default=list)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    created_by: Mapped[str] = fk("users")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ContentDocument(Base):
    __tablename__ = "content_documents"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = fk("workspaces")
    campaign_id: Mapped[str | None] = fk("campaigns", nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, review, approved, published, failed
    created_by: Mapped[str] = fk("users")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ContentVersion(Base):
    """Immutable. A change always creates a new row."""
    __tablename__ = "content_versions"
    __table_args__ = (UniqueConstraint("document_id", "number"),)
    id: Mapped[str] = pk()
    document_id: Mapped[str] = fk("content_documents")
    workspace_id: Mapped[str] = fk("workspaces")
    number: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    content_hash: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(10))  # human or ai
    author_id: Mapped[str] = fk("users")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = fk("workspaces")
    provider: Mapped[str] = mapped_column(String(30))
    label: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    secret_encrypted: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="unverified")  # unverified, connected, failed, disconnected
    status_detail: Mapped[str | None] = mapped_column(Text)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = fk("workspaces")
    document_id: Mapped[str] = fk("content_documents")
    version_id: Mapped[str] = fk("content_versions")
    content_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(30))
    integration_id: Mapped[str] = fk("integrations")
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    requested_by: Mapped[str] = fk("users")
    decided_by: Mapped[str | None] = fk("users", nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    comment: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)  # naive UTC
    block_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ExecutionRecord(Base):
    __tablename__ = "execution_records"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = fk("workspaces")
    approval_id: Mapped[str] = fk("approval_requests")
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(20))  # EXECUTING, PUBLISHED, FAILED, UNCLEAR
    detail: Mapped[str | None] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(String(12), default="manual", server_default="manual")
    external_id: Mapped[str | None] = mapped_column(String(200))
    external_url: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str | None] = fk("workspaces", nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(36))
    outcome: Mapped[str] = mapped_column(String(20))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[str] = pk()
    email_key: Mapped[str] = mapped_column(String(255), index=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = fk("workspaces")
    user_id: Mapped[str] = fk("users")
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AiUsage(Base):
    __tablename__ = "ai_usage"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = fk("workspaces")
    user_id: Mapped[str] = fk("users")
    model: Mapped[str] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12))  # success, rejected, failed
    action: Mapped[str] = mapped_column(String(30), default="generate", server_default="generate")
    provider: Mapped[str] = mapped_column(String(20), default="anthropic", server_default="anthropic")
    campaign_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class WorkerHeartbeat(Base):
    """The scheduler worker writes this every pass. The dashboard calls the agent Running only if it is fresh."""
    __tablename__ = "worker_heartbeats"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    beat_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ThemeSetting(Base):
    """Owner-controlled colours. scope=workspace applies to one workspace; scope=global applies to every workspace the owner owns."""
    __tablename__ = "theme_settings"
    __table_args__ = (UniqueConstraint("workspace_id"), UniqueConstraint("owner_user_id"))
    id: Mapped[str] = pk()
    scope: Mapped[str] = mapped_column(String(10))
    workspace_id: Mapped[str | None] = fk("workspaces", nullable=True)
    owner_user_id: Mapped[str | None] = fk("users", nullable=True)
    tokens: Mapped[dict] = mapped_column(JSON, default=dict)  # {"dark": {...}, "light": {...}}
    default_mode: Mapped[str] = mapped_column(String(10), default="dark")
    allow_user_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str] = fk("users")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AiProviderConfig(Base):
    """Which AI provider and models a workspace uses. Selected by the Owner; models must have been verified against the provider."""
    __tablename__ = "ai_provider_configs"
    id: Mapped[str] = pk()
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(120))
    fast_model: Mapped[str | None] = mapped_column(String(120))
    fallback_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_provider: Mapped[str | None] = mapped_column(String(20))
    fallback_model: Mapped[str | None] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[str] = fk("users")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AiProviderHealth(Base):
    """Result of the last real connection test per provider. A provider is only shown as connected after a test succeeded."""
    __tablename__ = "ai_provider_health"
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    models: Mapped[list | None] = mapped_column(JSON)
