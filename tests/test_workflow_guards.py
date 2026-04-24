import uuid
from datetime import datetime

import pytest

from database.database import create_user, set_user_city
from dms_core.manager import DmsManager
from dms_core.models import RequestStatus, RequestType, SessionLocal


def _user_name() -> str:
    return f"pytestwf_{uuid.uuid4().hex[:8]}"


def _new_request(user_id: str, user_email: str, city: str) -> int:
    session = SessionLocal()
    try:
        manager = DmsManager(session)
        req = manager.create_request(
            request_type=RequestType.LICNA_KARTA,
            user_id=user_id,
            user_email=user_email,
            user_city=city,
            details={"service_group": "semi_digital", "requested_at": datetime.now().isoformat()},
            description="pytest request",
            reason="testing",
        )
        manager.submit_request(req.id, changed_by=user_id)
        return req.id
    finally:
        session.close()


def test_admin_can_change_status():
    username = _user_name()
    email = f"{username}@example.com"
    assert create_user(username, "Pytest123!", email) is True
    assert set_user_city(username, "Podgorica") is True

    req_id = _new_request(username, email, "Podgorica")

    session = SessionLocal()
    try:
        manager = DmsManager(session)
        ok = manager.transition_request(
            req_id,
            RequestStatus.UNDER_REVIEW,
            changed_by="admin",
            actor_role="admin",
            reason="uzima u obradu",
        )
        assert ok is True
    finally:
        session.close()



def test_user_cannot_use_admin_transition():
    username = _user_name()
    email = f"{username}@example.com"
    assert create_user(username, "Pytest123!", email) is True
    assert set_user_city(username, "Podgorica") is True

    req_id = _new_request(username, email, "Podgorica")

    session = SessionLocal()
    try:
        manager = DmsManager(session)
        with pytest.raises(PermissionError):
            manager.transition_request(
                req_id,
                RequestStatus.UNDER_REVIEW,
                changed_by=username,
                actor_role="user",
                reason="ne bi trebalo biti dozvoljeno",
            )
    finally:
        session.close()
