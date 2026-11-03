from datetime import date, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import create_session_token
from app.auth.utils import hash_password
from app.config import COOKIE_NAME
from app.database import Base, get_db
from app.models import Bet, Competition, Result, User


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture()
def tables(test_engine):
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db(test_engine, tables):
    TestSession = sessionmaker(bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    from app.main import app

    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    with patch("app.scraper.scheduler.start_scheduler"), patch("app.scraper.scheduler.stop_scheduler"):
        from starlette.testclient import TestClient

        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def auth_client(client, db):
    def _make_auth_client(user):
        token = create_session_token(user.id)
        client.cookies.set(COOKIE_NAME, token)
        return client

    return _make_auth_client


@pytest.fixture()
def make_user(db):
    _counter = [0]

    def _make_user(username=None, password="password123"):
        _counter[0] += 1
        if username is None:
            username = f"testuser{_counter[0]}"
        user = User(username=username, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make_user


@pytest.fixture()
def make_competition(db):
    _counter = [0]

    def _make_competition(
        name=None,
        venue="Wisla",
        comp_date=None,
        category="WC",
        comp_type="individual",
        gender="M",
        status="upcoming",
        fis_event_id=None,
        fis_race_id=None,
    ):
        _counter[0] += 1
        if name is None:
            name = f"Test Competition {_counter[0]}"
        if comp_date is None:
            comp_date = date.today() + timedelta(days=7)
        comp = Competition(
            name=name,
            venue=venue,
            date=comp_date,
            category=category,
            type=comp_type,
            gender=gender,
            status=status,
            fis_event_id=fis_event_id,
            fis_race_id=fis_race_id,
        )
        db.add(comp)
        db.commit()
        db.refresh(comp)
        return comp

    return _make_competition


@pytest.fixture()
def make_result(db):
    def _make_result(competition_id, rank, athlete_name, nation="POL", total_points=None):
        result = Result(
            competition_id=competition_id,
            rank=rank,
            athlete_name=athlete_name,
            nation=nation,
            total_points=total_points,
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result

    return _make_result


@pytest.fixture()
def make_bet(db):
    def _make_bet(user_id, competition_id, position, athlete_name):
        bet = Bet(
            user_id=user_id,
            competition_id=competition_id,
            position=position,
            athlete_name=athlete_name,
        )
        db.add(bet)
        db.commit()
        db.refresh(bet)
        return bet

    return _make_bet
