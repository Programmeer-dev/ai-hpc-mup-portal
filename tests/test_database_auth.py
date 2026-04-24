from datetime import datetime, timedelta
import uuid

from database.database import (
    authenticate_user,
    create_user,
    create_user_session,
    revoke_all_user_sessions,
    revoke_user_session,
    set_user_city,
    validate_user_session,
)


def _user_name() -> str:
    return f"pytest_{uuid.uuid4().hex[:8]}"


def test_create_and_authenticate_user():
    username = _user_name()
    password = "Pytest123!"

    created = create_user(username, password, f"{username}@example.com")
    assert created is True

    assert authenticate_user(username, password) is True
    assert authenticate_user(username, "bad-pass") is False



def test_set_user_city_roundtrip():
    username = _user_name()
    password = "Pytest123!"

    assert create_user(username, password, f"{username}@example.com") is True
    assert set_user_city(username, "Podgorica") is True



def test_user_session_lifecycle():
    username = _user_name()
    password = "Pytest123!"
    token = uuid.uuid4().hex

    assert create_user(username, password, f"{username}@example.com") is True

    expires = (datetime.now() + timedelta(hours=2)).isoformat()
    assert create_user_session(username, token, expires) is True
    assert validate_user_session(username, token) is True

    revoke_user_session(username, token)
    assert validate_user_session(username, token) is False



def test_revoke_all_user_sessions():
    username = _user_name()
    password = "Pytest123!"
    token_a = uuid.uuid4().hex
    token_b = uuid.uuid4().hex

    assert create_user(username, password, f"{username}@example.com") is True

    expires = (datetime.now() + timedelta(hours=2)).isoformat()
    assert create_user_session(username, token_a, expires) is True
    assert create_user_session(username, token_b, expires) is True

    revoke_all_user_sessions(username, except_token=token_a)
    assert validate_user_session(username, token_a) is True
    assert validate_user_session(username, token_b) is False
