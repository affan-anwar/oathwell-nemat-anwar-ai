import os

os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-test-secret-key-0123456789")
os.environ.pop("LLM_PROVIDER", None)
os.environ.pop("ANTHROPIC_API_KEY", None)

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import get_db, make_engine  # noqa: E402
from app.main import app  # noqa: E402

TEST_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test.db")


@pytest.fixture()
def engine():
    eng = make_engine(TEST_URL)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    s = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield s
    s.close()


@pytest.fixture()
def client(engine):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def signup(client, email, name="Test User"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "correct-horse-1", "full_name": name})
    assert r.status_code == 201, r.text
    t = client.post("/api/v1/auth/login", json={"email": email, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture()
def owner(client):
    h = signup(client, "owner@example.com")
    ws = client.post("/api/v1/workspaces", json={"name": "Acme"}, headers=h).json()["id"]
    return h, ws


def mock_client(handler):
    """MOCK transport. Tests using this prove our logic only, not any real provider."""
    return httpx.Client(transport=httpx.MockTransport(handler))
