import os
from unittest.mock import patch, Mock

import sqlalchemy as sa
import stripe
from faker import Faker
import pytest

from supbackend.api import init_views
from supbackend.create_app import create_app
from flask_jwt_extended import create_access_token
from supbackend.db.fixtures import (
    NormalUserFactory,
    TransportationProviderFactory,
    TransportationOfferFactory,
    OfferTagFactory,
    ProviderReviewFactory,
)
from pytest_factoryboy import register
from pytest_postgresql.factories import DatabaseJanitor

register(NormalUserFactory)
register(TransportationProviderFactory)
register(TransportationOfferFactory)
register(OfferTagFactory)
register(ProviderReviewFactory)

# for faker
LOCALE = "en_US"

# Retrieve a database connection string from the environment
# should be a DB that doesn't exist
DB_CONN = os.getenv("TEST_DATABASE_URL", "postgresql:///supbackend_test".lower())
DB_OPTS = sa.engine.url.make_url(DB_CONN).translate_connect_args()
DB_VERSION = "10.10"


@pytest.fixture(scope="session")
def database(request):
    """Create a Postgres database for the tests, and drop it when the tests are done."""
    host = DB_OPTS.get("host")
    port = DB_OPTS.get("port")
    user = DB_OPTS.get("username")
    db_name = DB_OPTS["database"]

    with DatabaseJanitor(user, host, port, db_name, DB_VERSION):
        yield


@pytest.fixture(scope="session")
def app(database):
    """Create a Flask app context for tests."""
    # override config for test app here
    app = create_app(dict(SQLALCHEMY_DATABASE_URI=DB_CONN, TESTING=True))
    init_views()

    with app.app_context():
        yield app


@pytest.fixture(scope="session")
def _db(app):
    """Provide the transactional fixtures with access to the database via a Flask-SQLAlchemy database connection."""
    from supbackend.db import db

    # create all tables for test DB
    db.create_all()

    return db


@pytest.fixture
def client_unauthenticated(app):
    return app.test_client()


@pytest.fixture
def client(app, user, session):
    # get flask test client
    client = app.test_client()

    session.commit()  # need an id for user
    access_token = create_access_token(identity=user)

    # set environ http header to authenticate user
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {access_token}"

    return client


@pytest.fixture(scope="session")
def faker():
    return Faker(LOCALE)


@pytest.fixture
def user(normal_user_factory, db_session):
    user = normal_user_factory.create()
    db_session.commit()
    return user


@pytest.fixture(autouse=True)
def session(db_session):
    """Ensure every test is inside a subtransaction giving us a clean slate each test."""
    yield db_session


@pytest.fixture
def mock_stripe():
    with patch.object(stripe, "Customer"), patch.object(stripe, "Charge"):
        with patch.object(stripe, "Customer"), patch.object(
            stripe.Customer, "create"
        ) as customer_create_mock:
            customer_create_mock.return_value = Mock(id="cust_4321")
            yield
