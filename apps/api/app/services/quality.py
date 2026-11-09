"""Deterministic content checks. No AI involved, so results are repeatable."""
import re

from sqlalchemy import select

from app.db.models import ContentDocument, ContentVersion

LIMITS = {"social_post": 3000, "seo_metadata": 500, "ad_copy": 1500}  # workspace rules, not platform guarantees
SIMILAR = 0.8
ABSOLUTE = ["guaranteed", "100%", "risk-free", "risk free", "best in the world", "number one", "#1", "miracle", "cure"]  # heuristic list, not fact checking


def shingles(text: str, n: int = 5) -> set:
    words = re.findall(r"\w+", text.lower())
    if not words:
        return set()
    return {" ".join(words[i:i + n]) for i in range(max(len(words) - n + 1, 1))}


def _latest_other_versions(db, ws_id: str, doc_id: str, cap: int = 200) -> list:
    docs = db.execute(select(ContentDocument.id, ContentDocument.title).where(
        ContentDocument.workspace_id == ws_id, ContentDocument.id != doc_id).order_by(ContentDocument.created_at.desc()).limit(cap)).all()
    titles = {i: t for i, t in docs}
    best = {}
    for v in db.scalars(select(ContentVersion).where(ContentVersion.document_id.in_(list(titles)))):
        if v.document_id not in best or v.number > best[v.document_id].number:
            best[v.document_id] = v
    return [(titles[i], v) for i, v in best.items()]


def check(db, ws_id: str, doc, version, profile: dict) -> list[dict]:
    issues = []
    add = lambda level, code, msg: issues.append({"level": level, "code": code, "message": msg})
    text = version.body
    if not doc.title.strip():
        add("error", "missing_title", "The document has no title.")
    if not text.strip():
        add("error", "empty_body", "The body is empty.")
    low = (doc.title + " " + text).lower()
    for phrase in [l.strip() for l in (profile.get("prohibited_claims") or "").splitlines() if l.strip()]:
        if phrase.lower() in low:
            add("error", "prohibited_phrase", f"Contains the forbidden phrase “{phrase}”.")
    limit = LIMITS.get(doc.kind)
    if limit and len(text) > limit:
        add("error", "too_long", f"{len(text)} characters. The limit for {doc.kind.replace('_', ' ')} is {limit}.")
    if doc.kind == "blog" and len(re.findall(r"\w+", text)) < 300:
        add("warning", "short_blog", "Blog posts under 300 words rarely rank or engage well.")
    approved = (profile.get("approved_claims") or "").lower()
    for w in ABSOLUTE:
        if w in low and w not in approved:
            add("warning", "absolute_claim", f"“{w}” is an absolute claim. Make sure you can prove it.")
    seen = set()
    for m in re.findall(r"\b\d+(?:\.\d+)?\s?%|\b\d+x\b", text):
        if m.lower() not in approved and m not in seen:
            seen.add(m)
            add("warning", "unsupported_claim", f"“{m}” is a number claim that is not in your approved claims. Check it before publishing.")
    mine = shingles(text)
    for title, other in _latest_other_versions(db, ws_id, doc.id):
        if other.content_hash == version.content_hash:
            add("warning", "duplicate", f"Identical to “{title}”.")
            continue
        theirs = shingles(other.body)
        if mine and theirs:
            sim = len(mine & theirs) / len(mine | theirs)
            if sim >= SIMILAR:
                add("warning", "similar", f"{round(sim * 100)}% similar to “{title}”.")
    return issues
