import json
import logging
import re
import secrets
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from database.database import (
    authenticate_user,
    clear_login_failures,
    cleanup_expired_sessions,
    create_user_session,
    create_user,
    get_user_city,
    get_user_email,
    get_login_block_status,
    init_db,
    record_login_failure,
    revoke_all_user_sessions,
    revoke_user_session,
    set_user_city,
    validate_user_session,
)
from dms_core import DmsManager, RequestStatus
from dms_core.init_dms import init_dms_database, init_dms_templates
from dms_core.models import DocumentTemplate, SessionLocal
from dms_core.notifications import list_notifications, mark_all_read, unread_count
from municipality_utils import get_all_municipalities, validate_municipality
from pages.admin_panel import admin_dashboard
from pages.dms_requests import dms_request_page, my_requests_page
from permissions import Role, get_effective_role, has_admin_access


BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "data" / "session.json"
LOG_DIR = BASE_DIR / "logs"
REMEMBER_SESSION_DAYS = 7
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_MINUTES = 15


load_dotenv()


st.set_page_config(
    page_title="DMS MUP Portal",
    page_icon="📋",
    layout="wide",
)


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        /* ---- globalni font i pozadina ---- */
        html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; }

        /* ---- auth header banner ---- */
        .mup-banner {
            background: linear-gradient(135deg, #003087 0%, #0057b8 100%);
            color: white;
            padding: 28px 32px 20px 32px;
            border-radius: 10px;
            margin-bottom: 24px;
            text-align: center;
        }
        .mup-banner h1 { margin: 0; font-size: 1.9rem; font-weight: 700; letter-spacing: 0.5px; }
        .mup-banner p  { margin: 6px 0 0 0; font-size: 0.95rem; opacity: 0.85; }

        /* ---- stat kartice na dashboardu ---- */
        div[data-testid="metric-container"] {
            background: #f8f9fc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 14px 18px;
        }

        /* ---- status badge (koristi se u my_requests) ---- */
        .status-badge {
            display: inline-block;
            padding: 3px 11px;
            border-radius: 12px;
            font-size: 0.78rem;
            font-weight: 600;
            line-height: 1.6;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


LOG_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("dms_portal")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_DIR / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)


def init_session_state() -> None:
    defaults = {
        "user": None,
        "session_token": None,
        "user_city": None,
        "user_email": None,
        "is_admin": False,
        "user_role": Role.CITIZEN.value,
        "current_view": "dashboard",
        "prefill_group": None,
        "prefill_request_type": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def is_admin_user(username: str) -> bool:
    return has_admin_access(username)


def restore_session() -> None:
    if st.session_state.user or not SESSION_FILE.exists():
        return
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        username = data.get("user")
        token = data.get("token")
        expires_at = data.get("expires_at")
        if username and token and expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at)
            except ValueError:
                clear_session(clear_all_tokens=False)
                return

            if datetime.now() > expires_dt:
                clear_session(clear_all_tokens=False)
                return

            if not validate_user_session(username, token):
                clear_session(clear_all_tokens=False)
                return

            st.session_state.user = username
            st.session_state.session_token = token
            st.session_state.user_city = get_user_city(username)
            st.session_state.user_email = get_user_email(username)
            st.session_state.user_role = get_effective_role(username).value
            st.session_state.is_admin = is_admin_user(username)
    except Exception:
        # Ignore stale or invalid session file to keep startup robust.
        logger.exception("Session restore failed")


def persist_session(username: str) -> None:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=REMEMBER_SESSION_DAYS)
    create_user_session(username, token, expires_at.isoformat())

    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as file:
        json.dump({"user": username, "token": token, "expires_at": expires_at.isoformat()}, file)

    st.session_state.session_token = token


def clear_session(clear_all_tokens: bool = True) -> None:
    current_user = st.session_state.get("user")
    current_token = st.session_state.get("session_token")

    if current_user and current_token:
        if clear_all_tokens:
            revoke_all_user_sessions(current_user)
        else:
            revoke_user_session(current_user, current_token)

    if SESSION_FILE.exists():
        SESSION_FILE.unlink()

    st.session_state.user = None
    st.session_state.session_token = None
    st.session_state.user_city = None
    st.session_state.user_email = None
    st.session_state.is_admin = False
    st.session_state.user_role = Role.CITIZEN.value
    st.session_state.current_view = "dashboard"
    st.session_state.prefill_group = None
    st.session_state.prefill_request_type = None


def bootstrap_data() -> None:
    init_db()
    deleted_sessions = cleanup_expired_sessions()
    if deleted_sessions:
        logger.info("Cleaned up %s expired sessions", deleted_sessions)

    db = SessionLocal()
    try:
        init_dms_database(db)
        has_templates = db.query(DocumentTemplate).count() > 0
        if not has_templates:
            init_dms_templates(
                db,
                mup_rules_path=str(BASE_DIR / "database" / "mup_rules.json"),
                turizam_path=str(BASE_DIR / "requirements_data" / "turizam_requirements.json"),
            )
    finally:
        db.close()


def _render_eid_login() -> None:
    """Mock eID flow — simulira odabir digitalnog sertifikata."""
    from dms_core.eid_mock import issue_session_token, list_demo_certificates

    st.info(
        "Demo eID prijava: izaberite digitalni sertifikat iz simuliranog čitača. "
        "U realnom sistemu bi se otvorio nativni prompt za PIN/biometriju."
    )

    certificates = list_demo_certificates()
    options = [f"{cert['subject_name']} ({cert['username']})" for cert in certificates]

    selected_idx = st.selectbox(
        "Sertifikat iz čitača",
        options=list(range(len(certificates))),
        format_func=lambda idx: options[idx],
        key="eid_cert_select",
    )

    if not st.button("Potpiši i prijavi se", use_container_width=True, type="primary"):
        return

    cert = certificates[selected_idx]
    username = cert.get("username")
    email = cert.get("email")
    city = cert.get("city") or "Podgorica"
    id_card = cert.get("id_card_number")
    role = cert.get("role", "citizen")

    # Auto-kreiraj nalog ako ne postoji (random password — eID je primarni mehanizam)
    if not get_user_email(username):
        random_password = secrets.token_urlsafe(24)
        created = create_user(
            username=username,
            password=random_password,
            email=email,
            city=city,
            id_card_number=id_card,
            role=role,
        )
        if not created:
            st.error("Auto-registracija preko eID-a nije uspjela.")
            return

    token = issue_session_token(cert)
    logger.info("eID mock login user=%s token=%s", username, token[:12])

    st.session_state.user = username
    st.session_state.user_city = get_user_city(username) or city
    st.session_state.user_email = get_user_email(username) or email
    st.session_state.user_role = get_effective_role(username).value
    st.session_state.is_admin = is_admin_user(username)
    persist_session(username)

    st.success(f"eID prijava uspješna kao {cert['subject_name']}.")
    st.rerun()


def render_auth_page() -> None:
    st.markdown(
        """
        <div class="mup-banner">
            <h1>🏛️ MUP CG — Digitalni portal</h1>
            <p>Upravljanje dokumentima i administrativnim zahtjevima | Crna Gora</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Diplomski MVP: DMS za polu-digitalne i potpuno digitalne administrativne servise")

    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "Prijava"

    auth_modes = ["Prijava", "Sign up", "eID (demo)"]
    if st.session_state.auth_mode not in auth_modes:
        st.session_state.auth_mode = "Prijava"

    st.session_state.auth_mode = st.radio(
        "Izaberite opciju",
        auth_modes,
        index=auth_modes.index(st.session_state.auth_mode),
        horizontal=True,
        label_visibility="collapsed",
    )

    if st.session_state.auth_mode == "Prijava":
        with st.form("login_form"):
            username = st.text_input("Korisnicko ime")
            password = st.text_input("Lozinka", type="password")
            remember = st.checkbox("Zapamti prijavu")
            logout_others = st.checkbox("Odjavi ostale aktivne sesije")
            submit = st.form_submit_button("Prijavi se", use_container_width=True)

            if submit:
                if not username or not password:
                    st.warning("Unesite korisnicko ime i lozinku.")
                else:
                    normalized_username = username.strip()
                    block_status = get_login_block_status(
                        normalized_username,
                        max_attempts=LOGIN_MAX_ATTEMPTS,
                        window_minutes=LOGIN_WINDOW_MINUTES,
                    )

                    if block_status["blocked"]:
                        retry_minutes = max(1, int((block_status["retry_after_seconds"] + 59) / 60))
                        st.error(
                            f"Previse neuspjelih pokusaja. Pokusajte ponovo za {retry_minutes} min."
                        )
                        return

                    if not authenticate_user(normalized_username, password):
                        record_login_failure(normalized_username)
                        refreshed = get_login_block_status(
                            normalized_username,
                            max_attempts=LOGIN_MAX_ATTEMPTS,
                            window_minutes=LOGIN_WINDOW_MINUTES,
                        )
                        if refreshed["blocked"]:
                            retry_minutes = max(1, int((refreshed["retry_after_seconds"] + 59) / 60))
                            st.error(
                                f"Previse neuspjelih pokusaja. Pokusajte ponovo za {retry_minutes} min."
                            )
                        else:
                            attempts_left = refreshed.get("attempts_left", 0)
                            st.error(f"Pogresni kredencijali. Preostalo pokusaja: {attempts_left}.")
                        return

                    clear_login_failures(normalized_username)
                    if logout_others:
                        revoke_all_user_sessions(normalized_username)

                    st.session_state.user = normalized_username
                    st.session_state.user_city = get_user_city(normalized_username)
                    st.session_state.user_email = get_user_email(normalized_username)
                    st.session_state.user_role = get_effective_role(normalized_username).value
                    st.session_state.is_admin = is_admin_user(normalized_username)
                    if remember:
                        persist_session(normalized_username)
                    st.success("Uspjesna prijava.")
                    st.rerun()

    elif st.session_state.auth_mode == "eID (demo)":
        _render_eid_login()

    else:
        with st.form("register_form"):
            username = st.text_input("Novo korisnicko ime")
            email = st.text_input("Email")
            municipality = st.selectbox("Opstina", get_all_municipalities())
            id_card_number = st.text_input("Broj licne karte (opciono)")
            password = st.text_input("Lozinka", type="password")
            password_repeat = st.text_input("Potvrda lozinke", type="password")
            submit = st.form_submit_button("Registruj nalog", use_container_width=True)

            if submit:
                if not username or not email or not password:
                    st.warning("Popunite sva obavezna polja.")
                elif not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username.strip()):
                    st.error("Korisnicko ime mora imati 3-32 karaktera (slova, brojevi, _, -, .).")
                elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
                    st.error("Email format nije validan.")
                elif password != password_repeat:
                    st.error("Lozinke se ne poklapaju.")
                elif len(password) < 6:
                    st.error("Lozinka mora imati najmanje 6 karaktera.")
                elif not validate_municipality(municipality):
                    st.error("Izabrana opstina nije validna.")
                elif not create_user(
                    username=username,
                    password=password,
                    email=email,
                    city=municipality,
                    id_card_number=id_card_number,
                ):
                    st.error("Registracija nije uspjela. Provjerite podatke ili izaberite drugo korisnicko ime/email.")
                else:
                    st.session_state.auth_mode = "Prijava"
                    st.success("Nalog je kreiran. Mozete se prijaviti.")
                    st.rerun()


def _open_submit_with_prefill(group: str, request_type: str) -> None:
    st.session_state.prefill_group = group
    st.session_state.prefill_request_type = request_type
    st.session_state.current_view = "submit"
    st.rerun()


def render_dashboard() -> None:
    st.title("Korisnicki portal")
    st.markdown("### Pregled digitalnih servisa")

    db = SessionLocal()
    dms = DmsManager(db)
    try:
        user_requests = dms.get_user_requests(st.session_state.user)
    finally:
        db.close()

    pending_action = [r for r in user_requests if r.status == RequestStatus.PENDING_USER]
    active = [
        r for r in user_requests
        if r.status not in {RequestStatus.COMPLETED, RequestStatus.REJECTED, RequestStatus.DRAFT}
    ]
    completed = [r for r in user_requests if r.status == RequestStatus.COMPLETED]

    if pending_action:
        for req in pending_action:
            req_label = req.request_type.value.replace("_", " ").title()
            st.warning(
                f"Zahtjev #{req.id} ({req_label}) čeka vašu dopunu dokumentacije. "
                "Otvorite 'Moji zahtjevi' da odgovorite.",
                icon="⚠️",
            )

    sc1, sc2, sc3 = st.columns(3)
    sc1.metric("Ukupno zahtjeva", len(user_requests))
    sc2.metric("Aktivni zahtjevi", len(active))
    sc3.metric("Čeka vašu akciju", len(pending_action))

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Polu-digitalne MUP usluge")
        st.write("- Licna karta")
        st.write("- Pasos")
        st.write("- Vozacka dozvola")
        st.info(
            "Online: dokumenta, prijava zahtjeva i pracenje statusa. "
            "Fizicki dolazak ostaje potreban za biometriju ili preuzimanje."
        )

    with col2:
        st.subheader("Potpuno digitalne turisticke usluge")
        st.write("- Registracija apartmana/nekretnine")
        st.write("- Turisticka licenca")
        st.write("- Dozvola za adaptaciju")
        st.success(
            "Kompletan tok je online: podnosenje, validacija, komunikacija i odluka bez dolaska."
        )

    st.markdown("### Brzi odabir usluge")
    st.caption("Klikni na uslugu i odmah otvori formu sa odabranim tipom zahtjeva.")

    mup1, mup2, mup3 = st.columns(3)
    with mup1:
        if st.button("Licna karta", use_container_width=True):
            _open_submit_with_prefill("MUP (polu-digitalno)", "licna_karta")
    with mup2:
        if st.button("Pasos", use_container_width=True):
            _open_submit_with_prefill("MUP (polu-digitalno)", "pasos")
    with mup3:
        if st.button("Vozacka dozvola", use_container_width=True):
            _open_submit_with_prefill("MUP (polu-digitalno)", "vozacka_dozvola")

    tur1, tur2, tur3 = st.columns(3)
    with tur1:
        if st.button("Registracija nekretnine", use_container_width=True):
            _open_submit_with_prefill("Turizam (potpuno digitalno)", "turizam_registracija")
    with tur2:
        if st.button("Turisticka licenca", use_container_width=True):
            _open_submit_with_prefill("Turizam (potpuno digitalno)", "turizam_licenca")
    with tur3:
        if st.button("Dozvola za adaptaciju", use_container_width=True):
            _open_submit_with_prefill("Turizam (potpuno digitalno)", "turizam_dozvola_gradnje")


def render_help_assistant() -> None:
    from dms_core.dms_ai import get_dms_aware_response_with_source

    st.title("Pomoc i FAQ")
    st.caption("AI chatbot za DMS pravila, dokumenta, takse i statuse")

    if "faq_chat_history" not in st.session_state:
        st.session_state.faq_chat_history = [
            {
                "role": "assistant",
                "content": (
                    "Tu sam da pomognem oko MUP i turizam zahtjeva. "
                    "Mozete pitati za dokumenta, takse, rokove ili pracenje statusa."
                ),
            }
        ]

    action_col, _ = st.columns([1, 4])
    with action_col:
        if st.button("Ocisti chat"):
            st.session_state.faq_chat_history = st.session_state.faq_chat_history[:1]
            st.rerun()

    for message in st.session_state.faq_chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("role") == "assistant" and message.get("source") in {"llm", "fallback"}:
                source_label = "LLM" if message["source"] == "llm" else "DMS fallback"
                st.caption(f"Izvor odgovora: {source_label}")

    prompt = st.chat_input("Postavite pitanje (npr. Sta mi treba za pasos?)")
    if not prompt:
        return

    st.session_state.faq_chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analiziram pitanje..."):
            db = SessionLocal()
            try:
                answer, source = get_dms_aware_response_with_source(
                    prompt.strip(),
                    db,
                    chat_history=st.session_state.faq_chat_history[:-1],
                )
                st.markdown(answer)
                source_label = "LLM" if source == "llm" else "DMS fallback"
                st.caption(f"Izvor odgovora: {source_label}")
                st.session_state.faq_chat_history.append(
                    {"role": "assistant", "content": answer, "source": source}
                )
            except Exception:
                logger.exception("FAQ assistant failed")
                fallback = "Trenutno nije moguce dobiti odgovor. Pokusajte ponovo."
                st.error(fallback)
                st.session_state.faq_chat_history.append({"role": "assistant", "content": fallback})
            finally:
                db.close()


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## DMS Navigacija")
        st.caption(f"Korisnik: {st.session_state.user}")

        role_label = {
            Role.CITIZEN.value: "Građanin",
            Role.OFFICER.value: "Službenik",
            Role.ADMIN.value: "Administrator",
        }.get(st.session_state.user_role, "Građanin")
        st.caption(f"Uloga: {role_label}")

        if st.session_state.user_city:
            st.caption(f"Opstina: {st.session_state.user_city}")

        unread = unread_count(st.session_state.user)
        inbox_label = "Obavjestenja"
        if unread:
            inbox_label = f"Obavjestenja ({unread})"

        options = [
            ("dashboard", "Dashboard"),
            ("submit", "Podnesi zahtjev"),
            ("requests", "Moji zahtjevi"),
            ("inbox", inbox_label),
            ("faq", "Pomoc/FAQ"),
        ]
        if st.session_state.user_role == Role.OFFICER.value:
            options.append(("admin", "Officer panel"))
        elif st.session_state.user_role == Role.ADMIN.value:
            options.append(("admin", "Admin panel"))

        labels = {value: label for value, label in options}
        reverse = {label: value for value, label in options}

        selected_label = st.radio(
            "Sekcije",
            options=[label for _, label in options],
            index=[value for value, _ in options].index(st.session_state.current_view)
            if st.session_state.current_view in labels
            else 0,
        )
        st.session_state.current_view = reverse[selected_label]

        if st.button("Odjava", use_container_width=True):
            clear_session()
            st.rerun()


def render_inbox() -> None:
    st.title("Obavještenja")
    if st.button("Označi sve kao pročitano"):
        mark_all_read(st.session_state.user)
        st.rerun()

    items = list_notifications(st.session_state.user, only_unread=False, limit=50)
    if not items:
        st.info("Nemate obavještenja.")
        return

    for item in items:
        is_unread = item.get("read_at") is None
        container = st.container(border=True)
        with container:
            badge = "🔵 " if is_unread else "⚪ "
            st.markdown(f"### {badge}{item['title']}")
            st.caption(item["created_at"])
            if item.get("body"):
                st.write(item["body"])
            if item.get("request_id"):
                st.caption(f"Predmet #{item['request_id']}")


def render_main_router() -> None:
    view = st.session_state.current_view
    if view == "dashboard":
        render_dashboard()
    elif view == "submit":
        dms_request_page()
    elif view == "requests":
        my_requests_page()
    elif view == "inbox":
        render_inbox()
    elif view == "faq":
        render_help_assistant()
    elif view == "admin":
        admin_dashboard()


def main() -> None:
    _inject_css()
    init_session_state()
    bootstrap_data()
    restore_session()

    if not st.session_state.user:
        render_auth_page()
        return

    render_sidebar()
    render_main_router()


if __name__ == "__main__":
    main()
