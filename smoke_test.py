import json
import random
import sqlite3
import string
from datetime import datetime
from pathlib import Path

from database.database import (
    authenticate_user,
    create_user,
    get_user_city,
    get_user_request_submissions,
    init_db,
    save_request_submission,
    set_user_city,
)
from dms_core.init_dms import init_dms_database, init_dms_templates
from dms_core.manager import DmsManager
from dms_core.models import (
    DmsRequest,
    DocumentTemplate,
    RequestComment,
    RequestStatus,
    RequestStatusHistory,
    RequestType,
    SessionLocal,
)
from municipality_utils import get_all_municipalities, validate_municipality

BASE_DIR = Path(__file__).resolve().parent
AUTH_DB_PATH = BASE_DIR / "data" / "mup_data.db"


class SmokeRunner:
    def __init__(self) -> None:
        self.results: list[dict] = []
        self.username: str | None = None
        self.request_ids: list[int] = []

    def check(self, name: str, fn) -> None:
        try:
            detail = fn()
            self.results.append({"name": name, "status": "PASS", "detail": detail})
        except Exception as exc:
            self.results.append({"name": name, "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    def cleanup(self) -> None:
        if not self.username:
            return

        conn = sqlite3.connect(str(AUTH_DB_PATH))
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM request_submissions WHERE username = ?", (self.username,))
        except sqlite3.OperationalError:
            pass
        cur.execute("DELETE FROM users WHERE username = ?", (self.username,))
        conn.commit()
        conn.close()

        session = SessionLocal()
        try:
            ids = list(self.request_ids)
            if not ids:
                ids = [r.id for r in session.query(DmsRequest).filter(DmsRequest.user_id == self.username).all()]

            if ids:
                session.query(RequestComment).filter(RequestComment.request_id.in_(ids)).delete(synchronize_session=False)
                session.query(RequestStatusHistory).filter(RequestStatusHistory.request_id.in_(ids)).delete(synchronize_session=False)
                session.query(DmsRequest).filter(DmsRequest.id.in_(ids)).delete(synchronize_session=False)
                session.commit()
        finally:
            session.close()

    def run(self) -> int:
        municipalities = get_all_municipalities()
        city = municipalities[0] if municipalities else "Podgorica"

        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.username = f"smoke_{suffix}"
        password = "Smoke123!"
        email = f"{self.username}@example.com"

        self.check("init_db", lambda: (init_db(), "ok")[1])
        self.check("db_files_exist", lambda: {"auth_db": AUTH_DB_PATH.exists(), "dms_db": (BASE_DIR / "instance" / "dms.db").exists()})

        self.check("municipality_list_nonempty", lambda: len(municipalities))
        self.check(
            "municipality_validation",
            lambda: {
                "valid_example": validate_municipality(city),
                "invalid_example": validate_municipality("NOT_A_REAL_MUNICIPALITY_123"),
            },
        )

        def ensure_templates():
            db = SessionLocal()
            try:
                init_dms_database(db)
                count = db.query(DocumentTemplate).count()
                if count == 0:
                    init_dms_templates(
                        db,
                        mup_rules_path=str(BASE_DIR / "database" / "mup_rules.json"),
                        turizam_path=str(BASE_DIR / "requirements_data" / "turizam_requirements.json"),
                    )
                    count = db.query(DocumentTemplate).count()
                return {"template_count": count}
            finally:
                db.close()

        self.check("templates_bootstrap", ensure_templates)

        self.check("create_user", lambda: create_user(self.username, password, email))
        self.check("set_user_city", lambda: set_user_city(self.username, city))
        self.check("get_user_city", lambda: get_user_city(self.username))
        self.check("authenticate_user_ok", lambda: authenticate_user(self.username, password))
        self.check("authenticate_user_bad_password", lambda: authenticate_user(self.username, "wrongpass"))

        def dms_flow():
            db = SessionLocal()
            try:
                manager = DmsManager(db)
                req = manager.create_request(
                    request_type=RequestType.LICNA_KARTA,
                    user_id=self.username,
                    user_email=email,
                    user_city=city,
                    details={"service_group": "semi_digital", "requested_at": datetime.now().isoformat()},
                    description="Smoke test zahtjev",
                    reason="provjera",
                )
                self.request_ids.append(req.id)

                manager.submit_request(req.id, changed_by=self.username)
                manager.add_comment(req.id, author=self.username, content="Smoke komentar", author_type="user")

                refreshed = db.get(DmsRequest, req.id)
                comments = manager.get_visible_comments(req.id, for_user=True)
                return {
                    "request_id": req.id,
                    "status": refreshed.status.value if refreshed else "missing",
                    "expected_status": RequestStatus.SUBMITTED.value,
                    "comments": len(comments),
                }
            finally:
                db.close()

        self.check("dms_create_submit_comment", dms_flow)
        self.check(
            "save_request_submission",
            lambda: save_request_submission(self.username, self.request_ids[0], RequestType.LICNA_KARTA.value, RequestStatus.SUBMITTED.value),
        )
        self.check("get_user_request_submissions", lambda: len(get_user_request_submissions(self.username, limit=5)))

        passed = sum(1 for item in self.results if item["status"] == "PASS")
        failed = sum(1 for item in self.results if item["status"] == "FAIL")

        print(
            json.dumps(
                {
                    "summary": {"passed": passed, "failed": failed, "total": len(self.results)},
                    "results": self.results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return 0 if failed == 0 else 1


def main() -> int:
    runner = SmokeRunner()
    try:
        return runner.run()
    finally:
        runner.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
