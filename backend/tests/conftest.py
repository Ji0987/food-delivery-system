"""API 整合測試共用 fixtures。"""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient


os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "automated-test-placeholder-not-a-production-secret"

from backend.database import engine  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
