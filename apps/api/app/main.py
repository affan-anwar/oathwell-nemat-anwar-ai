from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api
from app.core.config import get_settings
from app.db.session import engine

app = FastAPI(title="NematAnwar AI API", version="0.3.0")
if get_settings().cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["*"],
                       allow_headers=["Authorization", "Content-Type"])
app.include_router(api)


@app.middleware("http")
async def hardening(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > get_settings().max_body_bytes:
        return JSONResponse({"detail": "Request body too large"}, status_code=413)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return resp


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict:
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ready"}
