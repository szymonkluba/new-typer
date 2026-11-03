from unittest.mock import MagicMock

from itsdangerous import URLSafeTimedSerializer

from app.auth.dependencies import create_session_token, get_current_user, serializer
from app.config import COOKIE_NAME, COOKIE_MAX_AGE


def test_create_session_token_returns_string():
    token = create_session_token(1)
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_session_token_contains_user_id():
    token = create_session_token(42)
    data = serializer.loads(token)
    assert data == {"user_id": 42}


def test_get_current_user_valid_token(db, make_user):
    user = make_user()
    token = create_session_token(user.id)
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    result = get_current_user(request, db)
    assert result is not None
    assert result.id == user.id


def test_get_current_user_no_cookie(db):
    request = MagicMock()
    request.cookies = {}
    assert get_current_user(request, db) is None


def test_get_current_user_invalid_token(db):
    request = MagicMock()
    request.cookies = {COOKIE_NAME: "garbage-token-value"}
    assert get_current_user(request, db) is None


def test_get_current_user_tampered_token(db, make_user):
    user = make_user()
    token = create_session_token(user.id)
    tampered = token[:-3] + "XXX"
    request = MagicMock()
    request.cookies = {COOKIE_NAME: tampered}
    assert get_current_user(request, db) is None


def test_get_current_user_expired_token(db, make_user):
    user = make_user()
    token = create_session_token(user.id)
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    import time
    import unittest.mock
    # Advance time far beyond COOKIE_MAX_AGE to simulate expiry
    future_time = time.time() + COOKIE_MAX_AGE + 3600
    with unittest.mock.patch("itsdangerous.timed.time.time", return_value=future_time):
        result = get_current_user(request, db)
    assert result is None


def test_get_current_user_deleted_user(db, make_user):
    user = make_user()
    token = create_session_token(user.id)
    db.delete(user)
    db.commit()
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    assert get_current_user(request, db) is None


def test_get_current_user_wrong_secret(db, make_user):
    user = make_user()
    wrong_serializer = URLSafeTimedSerializer("wrong-secret-key")
    token = wrong_serializer.dumps({"user_id": user.id})
    request = MagicMock()
    request.cookies = {COOKIE_NAME: token}
    assert get_current_user(request, db) is None
