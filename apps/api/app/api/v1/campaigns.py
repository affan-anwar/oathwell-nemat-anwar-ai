from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select

from app.api.deps import current_user, require_perm, scoped
from app.db.models import Campaign
from app.db.session import get_db
from app.services.audit import record

router = APIRouter(prefix="/workspaces/{ws}/campaigns", tags=["campaigns"])
TRANSITIONS = {"DRAFT": {"ACTIVE", "CANCELLED", "ARCHIVED"}, "ACTIVE": {"PAUSED", "COMPLETED", "CANCELLED"},
               "PAUSED": {"ACTIVE", "CANCELLED"}, "COMPLETED": {"ARCHIVED"}, "CANCELLED": {"ARCHIVED"},
               "ARCHIVED": set()}


def _tz(v: str) -> str:
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("unknown time zone")
    return v


class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    objective: str | None = Field(default=None, max_length=4000)
    audience: str | None = Field(default=None, max_length=4000)
    channels: list[str] = Field(default_factory=list, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def _v(cls, v):
        return _tz(v)

    @model_validator(mode="after")
    def _dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date is before start_date")
        return self


class CampaignPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    objective: str | None = Field(default=None, max_length=4000)
    audience: str | None = Field(default=None, max_length=4000)
    channels: list[str] | None = Field(default=None, max_length=20)
    start_date: date | None = None
    end_date: date | None = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def _v(cls, v):
        return _tz(v) if v else v


class TransitionIn(BaseModel):
    to: str


def out(c: Campaign) -> dict:
    return {k: getattr(c, k) for k in ["id", "name", "objective", "audience", "channels", "start_date", "end_date",
                                       "timezone", "status", "created_at", "updated_at"]}


@router.post("", status_code=201)
def create(ws: str, body: CampaignIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "campaign.write")
    c = Campaign(workspace_id=ws, created_by=user.id, **body.model_dump())
    db.add(c)
    db.flush()
    record(db, ws, user.id, "campaign.create", "campaign", c.id)
    db.commit()
    return out(c)


@router.get("")
def list_(ws: str, status: str | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
          db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    q = select(Campaign).where(Campaign.workspace_id == ws)
    q = q.where(Campaign.status == status) if status else q.where(Campaign.status != "ARCHIVED")
    return [out(c) for c in db.scalars(q.order_by(Campaign.created_at.desc()).limit(limit).offset(offset))]


@router.get("/{cid}")
def get(ws: str, cid: str, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "read")
    return out(scoped(db, Campaign, cid, ws))


@router.patch("/{cid}")
def patch(ws: str, cid: str, body: CampaignPatch, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "campaign.write")
    c = scoped(db, Campaign, cid, ws)
    if c.status in ("ARCHIVED", "CANCELLED", "COMPLETED"):
        raise HTTPException(409, f"A {c.status.lower()} campaign cannot be edited")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    if c.start_date and c.end_date and c.end_date < c.start_date:
        raise HTTPException(422, "end_date is before start_date")
    record(db, ws, user.id, "campaign.update", "campaign", c.id)
    db.commit()
    return out(c)


@router.post("/{cid}/transition")
def transition(ws: str, cid: str, body: TransitionIn, db=Depends(get_db), user=Depends(current_user)):
    require_perm(db, user, ws, "campaign.write")
    c = scoped(db, Campaign, cid, ws)
    if body.to not in TRANSITIONS.get(c.status, set()):
        raise HTTPException(409, f"Cannot move from {c.status} to {body.to}")
    old, c.status = c.status, body.to
    record(db, ws, user.id, "campaign.transition", "campaign", c.id, detail={"from": old, "to": body.to})
    db.commit()
    return out(c)
