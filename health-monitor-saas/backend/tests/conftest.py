import os

os.environ["HM_DATABASE_URL"] = "sqlite://"  # in-memory
os.environ["HM_STRIPE_SECRET_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        c.session_factory = TestSession
        yield c


def signup(client, email="alice@example.com", password="s3cure-pass!"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Alice"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return signup(client)


@pytest.fixture
def subscribed(client, auth):
    r = client.post("/api/v1/billing/checkout", json={"plan": "basic"}, headers=auth)
    assert r.status_code == 200, r.text
    return auth


@pytest.fixture
def device_key(client, subscribed):
    r = client.post("/api/v1/devices", json={"name": "Left wrist"}, headers=subscribed)
    assert r.status_code == 201, r.text
    return r.json()["api_key"]
