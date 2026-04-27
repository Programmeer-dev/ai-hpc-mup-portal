from datetime import datetime, timedelta
import uuid

from database.database import (
    authenticate_user,
    clear_login_failures,
    create_user,
    create_user_session,
    get_login_block_status,
    get_id_card_number,
    get_user_city,
    get_user_email,
    record_login_failure,
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


def test_signup_persists_profile_fields():
    username = _user_name()
    password = "Pytest123!"
    email = f"{username}@example.com"
    city = "Podgorica"
    id_card_number = "A123456"

    assert create_user(
        username=username,
        password=password,
        email=email,
        city=city,
        id_card_number=id_card_number,
    ) is True

    assert get_user_email(username) == email
    assert get_user_city(username) == city
    assert get_id_card_number(username) == id_card_number


def test_login_block_status_after_repeated_failures():
    username = _user_name()
    password = "Pytest123!"

    assert create_user(username, password, f"{username}@example.com") is True

    clear_login_failures(username)
    for _ in range(5):
        record_login_failure(username)

    status = get_login_block_status(username, max_attempts=5, window_minutes=15)
    assert status["blocked"] is True
    assert status["attempts_left"] == 0

    clear_login_failures(username)
    unblocked = get_login_block_status(username, max_attempts=5, window_minutes=15)
    assert unblocked["blocked"] is False
