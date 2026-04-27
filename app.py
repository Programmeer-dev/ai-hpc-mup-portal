import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Set

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
    is_user_admin,
    init_db,
    record_login_failure,
    revoke_all_user_sessions,
    revoke_user_session,
    set_user_city,
    validate_user_session,
)
from dms_core.init_dms import init_dms_database, init_dms_templates
from dms_core.models import DocumentTemplate, SessionLocal
from municipality_utils import get_all_municipalities, validate_municipality
from pages.admin_panel import admin_dashboard
from pages.dms_requests import dms_request_page, my_requests_page


BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "data" / "session.json"
LOG_DIR = BASE_DIR / "logs"
DEFAULT_ADMIN_USERS = "admin,rapoz"
REMEMBER_SESSION_DAYS = 7
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_MINUTES = 15


load_dotenv()


st.set_page_config(
    page_title="DMS MUP Portal",
    page_icon="📋",
    layout="wide",
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
        "current_view": "dashboard",
        "prefill_group": None,
        "prefill_request_type": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_admin_users() -> Set[str]:
    raw = os.getenv("APP_ADMIN_USERS", DEFAULT_ADMIN_USERS)
    return {item.strip() for item in raw.split(",") if item.strip()}


def is_admin_user(username: str) -> bool:
    return is_user_admin(username) or username in get_admin_users()


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


def render_auth_page() -> None:
    st.title("Digitalizacija MUP usluga")
    st.caption("Diplomski MVP: DMS za polu-digitalne i potpuno digitalne administrativne servise")

    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "Prijava"

    st.session_state.auth_mode = st.radio(
        "Izaberite opciju",
        ["Prijava", "Sign up"],
        index=0 if st.session_state.auth_mode == "Prijava" else 1,
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
                    st.session_state.is_admin = is_admin_user(normalized_username)
                    if remember:
                        persist_session(normalized_username)
                    st.success("Uspjesna prijava.")
                    st.rerun()

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
        if st.session_state.user_city:
            st.caption(f"Opstina: {st.session_state.user_city}")

        options = [
            ("dashboard", "Dashboard"),
            ("submit", "Podnesi zahtjev"),
            ("requests", "Moji zahtjevi"),
            ("faq", "Pomoc/FAQ"),
        ]
        if st.session_state.is_admin:
            options.append(("admin", "Admin/Officer panel"))

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


def render_main_router() -> None:
    view = st.session_state.current_view
    if view == "dashboard":
        render_dashboard()
    elif view == "submit":
        dms_request_page()
    elif view == "requests":
        my_requests_page()
    elif view == "faq":
        render_help_assistant()
    elif view == "admin":
        admin_dashboard()


def main() -> None:
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
