from datetime import datetime, timedelta
import uuid

from database.database import create_user, set_user_city
from dms_core.manager import DmsManager
from dms_core.models import DmsRequest, RequestPriority, RequestStatus, RequestType, SessionLocal


def _user_name() -> str:
    return f"pytestsla_{uuid.uuid4().hex[:8]}"


def test_sla_escalation_raises_priority_for_overdue_active_request():
    username = _user_name()
    email = f"{username}@example.com"
    assert create_user(username, "Pytest123!", email) is True
    assert set_user_city(username, "Podgorica") is True

    session = SessionLocal()
    try:
        manager = DmsManager(session)
        req = manager.create_request(
            request_type=RequestType.PASOS,
            user_id=username,
            user_email=email,
            user_city="Podgorica",
            details={"service_group": "semi_digital"},
            description="sla test",
            reason="sla",
        )
        manager.submit_request(req.id, changed_by=username)

        db_req = session.get(DmsRequest, req.id)
        db_req.estimated_completion = datetime.now() - timedelta(days=10)
        db_req.priority = RequestPriority.MEDIUM
        session.commit()

        result = manager.apply_sla_escalation()
        assert result["checked_overdue"] >= 1
        assert result["escalated"] >= 1

        refreshed = session.get(DmsRequest, req.id)
        assert refreshed.priority in {RequestPriority.HIGH, RequestPriority.URGENT}
        assert refreshed.status == RequestStatus.SUBMITTED
    finally:
        session.close()


def test_build_audit_pack_contains_request_history_and_comments():
    username = _user_name()
    email = f"{username}@example.com"
    assert create_user(username, "Pytest123!", email) is True
    assert set_user_city(username, "Podgorica") is True

    session = SessionLocal()
    try:
        manager = DmsManager(session)
        req = manager.create_request(
            request_type=RequestType.VOZACKA_DOZVOLA,
            user_id=username,
            user_email=email,
            user_city="Podgorica",
            details={"service_group": "semi_digital"},
            description="audit test",
            reason="audit",
        )
        manager.submit_request(req.id, changed_by=username)
        manager.add_comment(req.id, author=username, content="audit comment", author_type="user")

        pack = manager.build_audit_pack(req.id)
        assert pack["request"]["id"] == req.id
        assert isinstance(pack["status_history"], list)
        assert isinstance(pack["comments"], list)
        assert len(pack["status_history"]) >= 1
    finally:
        session.close()
