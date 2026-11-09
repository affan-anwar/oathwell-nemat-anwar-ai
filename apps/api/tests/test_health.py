import pytest

pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}
