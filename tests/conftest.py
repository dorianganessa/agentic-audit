import pytest
from agentaudit_api.main import create_app
from agentaudit_api.models.api_key import (
    ApiKey,
    generate_api_key,
    hash_api_key,
    key_prefix_from_key,
)
from agentaudit_api.models.organization import Organization
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlmodel import SQLModel
from starlette.testclient import TestClient
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture()
def db_url(postgres):
    raw_url = postgres.get_connection_url()
    if "psycopg2" not in raw_url:
        return raw_url.replace("postgresql://", "postgresql+psycopg2://")
    return raw_url


@pytest.fixture()
def app(db_url):
    application = create_app(database_url=db_url)

    engine = create_engine(db_url)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    yield application


@pytest.fixture()
def api_key_raw(app, db_url):
    """Create a test org + API key and return the raw key string."""
    engine = create_engine(db_url)
    raw_key = generate_api_key()

    with Session(engine) as session:
        org = Organization(name="Test Org")
        session.add(org)
        session.flush()

        api_key = ApiKey(
            key_hash=hash_api_key(raw_key),
            key_prefix=key_prefix_from_key(raw_key),
            name="Test",
            org_id=org.id,
        )
        session.add(api_key)
        session.commit()

    return raw_key


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c
