from dms_core.dms_ai import get_dms_aware_response, get_dms_aware_response_with_source
from dms_core.init_dms import init_dms_database, init_dms_templates
from dms_core.models import DocumentTemplate, SessionLocal


def _ensure_templates(db):
    init_dms_database(db)
    if db.query(DocumentTemplate).count() == 0:
        init_dms_templates(
            db,
            mup_rules_path="database/mup_rules.json",
            turizam_path="requirements_data/turizam_requirements.json",
        )


def test_ai_handles_passport_docs_query():
    db = SessionLocal()
    try:
        _ensure_templates(db)
        answer = get_dms_aware_response("Sta mi treba za pasos", db)
        text = answer.lower()
        assert "pasos" in text or "paso" in text
        assert "dokument" in text or "obavezni" in text
    finally:
        db.close()


def test_ai_handles_identity_card_query():
    db = SessionLocal()
    try:
        _ensure_templates(db)
        answer = get_dms_aware_response("Sta mi treba za licnu kartu", db)
        text = answer.lower()
        assert "licna karta" in text or "lična karta" in text
        assert "dokument" in text or "obavezni" in text
    finally:
        db.close()


def test_ai_handles_drivers_license_fee_query():
    db = SessionLocal()
    try:
        _ensure_templates(db)
        answer = get_dms_aware_response("Kolika je taksa za vozacku", db)
        text = answer.lower()
        assert "vozack" in text or "vozačk" in text or "dozvol" in text
        assert "taksa" in text or "eur" in text
    finally:
        db.close()


def test_ai_handles_status_tracking_query():
    db = SessionLocal()
    try:
        _ensure_templates(db)
        answer = get_dms_aware_response("Kako pratim status zahtjeva", db)
        text = answer.lower()
        assert "moji zahtjevi" in text or "status" in text
    finally:
        db.close()


def test_ai_handles_tourism_registration_query():
    db = SessionLocal()
    try:
        _ensure_templates(db)
        answer = get_dms_aware_response("Kako da registrujem stan za turizam", db)
        text = answer.lower()
        assert "turizam" in text or "registracija" in text
    finally:
        db.close()


def test_ai_returns_source_metadata():
    db = SessionLocal()
    try:
        _ensure_templates(db)
        answer, source = get_dms_aware_response_with_source("Sta mi treba za pasos", db)
        assert isinstance(answer, str)
        assert source in {"llm", "fallback"}
    finally:
        db.close()


def test_ai_follow_up_payment_question_uses_chat_context():
    db = SessionLocal()
    try:
        _ensure_templates(db)
        first_answer = get_dms_aware_response("Trebam pasos", db)
        follow_up, source = get_dms_aware_response_with_source(
            "na koji ziro racun treba da uplatim",
            db,
            chat_history=[
                {"role": "user", "content": "Trebam pasos"},
                {"role": "assistant", "content": first_answer},
            ],
        )
        text = follow_up.lower()
        assert source in {"llm", "fallback"}
        assert "uplata" in text or "ziro" in text or "832-12345-00" in text
        assert "pasos" in text or "paso" in text
    finally:
        db.close()
